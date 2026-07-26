# Task 02: Implement Working Memory

## Objective

Implement the working memory subsystem for Artax Network. Memory provides persistent context across events — the AI reasons over working memory of events instead of making stateless tool calls.

## Reference Documents

- **PRD**: `../../prd/prd-memory.md` — all resolved design decisions
- **Existing scaffolding**: `../../../artax/memory/base.py`
- **Depends on**: `../../../artax/events/types.py` (EventType, SemanticEvent) — must be implemented first
- **Memory design**: `../../memory.md`

## Resolved Design Decisions

1. **All backends async** — consistent interface, InMemory wraps dict in coroutine trivially
2. **Lazy TTL enforcement** — check on access, no background cleanup task
3. **Include TTL in snapshots** — faithful state capture, restored snapshots preserve original TTL semantics
4. **Events for significant changes only** — new key, eviction, clear emit events; reduce noise
5. **OrderedDict for LRU** — built-in eviction ordering in InMemory backend
6. **Full MemoryEntry in predicates** — more context for filtering decisions
7. **SQLite WAL mode** — standard for concurrent read/write (future implementation)
8. **Redis pool size 10** — standard practice (future implementation)

## Current State

Existing scaffolding is a stub. Key gaps:

- `WorkingMemory` Protocol missing `start()`, `stop()`, `delete()`, `keys()`, `size()` methods
- `store()` missing `ttl` parameter
- `query()` returns `list[MemoryEntry]` but PRD wants `dict[str, Any]`
- `clear()` missing namespace param and return value
- `MemoryEntry` missing `created_at`, `updated_at`, `ttl`, `namespace` fields
- `MemoryFilter` missing `namespace`, `key_prefix`, `value_type`, `predicate` fields
- `MemoryConfig` dataclass missing entirely
- All backend stubs are empty

## Implementation Steps

### Step 1: Reconcile `../../../artax/memory/base.py`

Update types to match PRD:

```python
class MemoryConfig:
    backend: str = "memory"  # "memory" | "sqlite" | "redis"
    max_entries: int = 10000
    default_ttl: float | None = None  # seconds
    cleanup_interval: float = 60.0  # seconds (for future eager cleanup)
    sqlite_path: str = "artax_memory.db"
    redis_url: str = "redis://localhost:6379"


class MemoryEntry:
    key: str
    value: Any
    namespace: str
    created_at: float  # time.monotonic()
    updated_at: float
    ttl: float | None  # absolute monotonic time when expired, or None


class MemoryFilter:
    namespace: str | None = None
    key_prefix: str | None = None
    value_type: type | None = None
    predicate: Callable[[MemoryEntry], bool | Awaitable[bool]] | None = None
    after: float | None = None  # created_at threshold
    limit: int | None = None


class MemorySnapshot:
    version: str
    timestamp: float
    entries: dict[str, dict[str, Any]]  # namespace -> {key: serialized_entry}


class WorkingMemory(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def store(
        self, key: str, value: Any, namespace: str = "default", ttl: float | None = None
    ) -> None: ...
    async def retrieve(self, key: str, namespace: str = "default") -> Any | None: ...
    async def delete(self, key: str, namespace: str = "default") -> bool: ...
    async def query(self, filter: MemoryFilter) -> dict[str, Any]: ...
    async def clear(self, namespace: str | None = None) -> int: ...  # returns count
    async def keys(self, namespace: str = "default") -> list[str]: ...
    async def size(self, namespace: str | None = None) -> int: ...
    async def snapshot(self) -> MemorySnapshot: ...
    async def restore(self, snapshot: MemorySnapshot) -> None: ...
```

### Step 2: Implement `InMemoryStore`

Full production implementation:

- **Constructor**: `__init__(self, config: MemoryConfig, event_bus: EventBus | None = None)`
- **Storage**: `dict[str, OrderedDict[str, MemoryEntry]]` — namespace -> key -> entry (OrderedDict for LRU)
- **`start()`**: no-op (memory is always ready)
- **`stop()`**: clear all data
- **`store(key, value, namespace, ttl)`**:
  1. Calculate expiry: `time.monotonic() + ttl` if ttl else None
  2. Create MemoryEntry with timestamps
  3. If key exists: update (move to end of OrderedDict for LRU)
  4. If key is new and at capacity: evict LRU (first item in OrderedDict)
  5. Emit MEMORY_UPDATED event if event_bus provided and key is new
- **`retrieve(key, namespace)`**:
  1. Look up entry
  2. If expired (lazy TTL): delete and return None
  3. Move to end of OrderedDict (access updates LRU position)
  4. Return value
- **`delete(key, namespace)`**: remove from OrderedDict, return True if existed
- **`query(filter)`**:
  1. Iterate entries matching namespace/prefix/type
  2. Apply async predicate if provided
  3. Respect limit
  4. Return dict[str, Any]
- **`clear(namespace)`**: if namespace given, clear only that namespace; otherwise clear all. Return count of removed entries. Emit event.
- **`keys(namespace)`**: return list of keys
- **`size(namespace)`**: return count
- **`snapshot()`**: serialize all entries including TTL info
- **`restore(snapshot)`**: deserialize and populate storage

### Step 3: Write tests

Create `tests/test_memory_types.py`:
- Test MemoryEntry creation with all fields
- Test MemoryFilter defaults
- Test MemorySnapshot serialization round-trip

Create `tests/test_inmemory_store.py`:
- Store and retrieve basic value
- Store overwrites existing key (update timestamps)
- Retrieve non-existent key returns None
- Lazy TTL expiration (store with short TTL, wait, retrieve returns None)
- Namespace isolation (same key in different namespaces)
- LRU eviction (fill to capacity, add one more, oldest evicted)
- Query with namespace filter
- Query with key_prefix filter
- Query with async predicate
- Query respects limit
- Delete existing key returns True
- Delete non-existent key returns False
- Clear specific namespace returns correct count
- Clear all namespaces returns correct count
- Keys returns correct keys per namespace
- Size returns correct count
- Snapshot captures full state including TTLs
- Restore populates from snapshot
- Event emitted on new key store (with event_bus)
- Event emitted on eviction
- Event emitted on clear
- Start/stop lifecycle
- Concurrent store/retrieve from multiple coroutines

## Technical Constraints

- All operations async (even InMemory — wraps sync dict in `await asyncio.coroutine`)
- Use `time.monotonic()` for TTL timestamps (not `time.time()`)
- OrderedDict access: `move_to_end(key)` on retrieve for LRU
- Evict: `popitem(last=False)` removes oldest (FIFO = least recently used)
- Frozen dataclasses for MemoryEntry, MemoryFilter, MemorySnapshot
- Strict typing for `mypy --strict`

## Quality Gates

```bash
python3 -m py_compile artax/memory/base.py
python3 -c "from artax.memory.base import InMemoryStore, WorkingMemory; print('OK')"
pytest tests/test_memory_types.py tests/test_inmemory_store.py -v
```

## Files

| Action | File |
|--------|------|
| MODIFY | `../../../artax/memory/base.py` |
| CREATE | `tests/test_memory_types.py` |
| CREATE | `tests/test_inmemory_store.py` |
