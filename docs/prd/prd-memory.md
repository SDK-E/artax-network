# PRD: Working Memory

**Subsystem:** `artax.memory`
**Version:** 0.1
**Status:** Draft

---

## 1. Problem Statement

AI agents need persistent context across events to make coherent decisions. Stateless function calls forget everything between invocations — the agent cannot reason about what happened three events ago, cannot track which actions succeeded, and cannot maintain a model of the environment. Without working memory, the agent is amnesiac: every event is processed in isolation.

Working memory solves this by providing a bounded, attention-scoped store that holds the agent's current context. Unlike long-term storage (which is unbounded and historical), working memory contains only what the agent needs for the present decision cycle. It is updated every tick based on incoming events, evicted when attention shifts, and snapshotted for state persistence.

The working memory is not a database. It is the agent's short-term context — the scratchpad that holds the current page's DOM summary, the last action's result, the active intent, and whatever else is relevant right now.

---

## 2. Goals

1. **Key-value store.** Working memory stores data as string keys mapping to typed values (dicts, lists, strings, numbers, booleans). Keys are namespaced by subsystem (e.g., `"chromium.dom.current"`, `"scheduler.active_intent"`).

2. **Query by filter.** Memory supports querying stored entries by key prefix, value type, or custom predicate. Queries return matching entries without iterating the entire store.

3. **Snapshots for state persistence.** Memory supports `snapshot()` which captures the entire current state as a serializable dict, and `restore(snapshot)` which replaces the current state from a snapshot. Snapshots are used for checkpointing and debugging.

4. **Pluggable backends.** Memory supports three backends in v0.1: InMemory (dict-based, fastest, lost on restart), SQLite (file-based, persistent, moderate speed), and Redis (network-based, shared, fastest for distributed). The backend is selected at config time and swapped via the WorkingMemory protocol.

5. **TTL support.** Entries can have a time-to-live. Expired entries are evicted on access or during periodic cleanup. TTL enables automatic context decay — old observations fade without explicit eviction.

6. **Event-driven updates.** Memory subscribes to events on the EventBus and updates itself based on event content. Configuration specifies which events map to which memory operations (e.g., `PAGE_LOADED` → store page title, `ACTION_COMPLETED` → store action result).

7. **Capacity bounds.** Memory enforces a maximum number of entries (configurable, default 10000). When capacity is exceeded, the eviction policy (LRU by default) removes the least-recently-accessed entry.

---

## 3. Non-Goals

1. **Vector embeddings.** Working memory does not store or query vector representations. Semantic similarity search is a v0.2 concern when LLM integration is added.

2. **Distributed memory.** In v0.1, memory exists within a single runtime process. Redis backend provides network access but is not a distributed consensus store.

3. **Memory compaction.** There is no background process that merges, compresses, or reorganizes memory entries. Entries are stored as-is until evicted or cleared.

4. **Full-text search.** Memory does not support full-text search across values. Key-prefix queries and type filters are sufficient for v0.1.

5. **Transactional operations.** Memory does not support multi-key transactions or atomic batch updates. Individual `store()` calls are atomic; sequences are not.

6. **Memory sharing across runtimes.** Two runtime instances cannot share a memory backend in v0.1. Redis provides the mechanism but coordination is not implemented.

---

## 4. Architecture

```
┌────────────────────────────────────────────────┐
│              Working Memory                     │
│                                                │
│  ┌──────────────┐    ┌──────────────────────┐ │
│  │   Protocol    │    │   MemoryFilter        │ │
│  │   (interface) │    │   (query builder)     │ │
│  └──────┬───────┘    └──────────────────────┘ │
│         │                                      │
│  ┌──────┴───────────────────────────────┐     │
│  │         Backend Selection             │     │
│  │  ┌──────────┐ ┌────────┐ ┌───────┐  │     │
│  │  │InMemory   │ │SQLite  │ │ Redis │  │     │
│  │  │(dict)     │ │(file)  │ │(net)  │  │     │
│  │  └──────────┘ └────────┘ └───────┘  │     │
│  └──────────────────────────────────────┘     │
│                                                │
│  ┌──────────────────────────────────────┐     │
│  │         Eviction Policy (LRU)        │     │
│  └──────────────────────────────────────┘     │
└────────────────────────────────────────────────┘
```

### Data Model

```python
@dataclass
class MemoryEntry:
    key: str                    # "chromium.dom.title"
    value: Any                  # JSON-serializable
    created_at: float           # epoch timestamp
    updated_at: float           # epoch timestamp
    ttl: float | None           # seconds, None = no expiry
    namespace: str              # "chromium", "scheduler", "runtime"
```

### Event-Driven Updates

Memory subscribes to the EventBus and processes events according to a configured mapping:

```toml
[memory.event_mapping]
"page_loaded" = { operation = "store", key = "current_page", field = "payload.url" }
"action_completed" = { operation = "store", key = "last_action_result", field = "payload.result" }
"dom_changed" = { operation = "store", key = "dom_snapshot", field = "payload.summary" }
```

### Eviction Strategy

When memory reaches capacity (`max_entries`):
1. Scan for expired entries (TTL exceeded) and remove them.
2. If still at capacity, evict the entry with the oldest `updated_at` timestamp (LRU).
3. Emit a `memory.evicted` event with the evicted key and reason.

### Snapshot Format

```python
{
    "version": "0.1",
    "timestamp": 1700000000.0,
    "entries": {
        "chromium.dom.title": {
            "value": "Example Page",
            "created_at": 1700000000.0,
            "ttl": null,
            "namespace": "chromium"
        },
        "scheduler.active_intent": {
            "value": {"goal": "submit_form", "progress": 0.5},
            "created_at": 1700000001.0,
            "ttl": 300.0,
            "namespace": "scheduler"
        }
    }
}
```

---

## 5. Interfaces

### WorkingMemory Protocol

```python
class WorkingMemory(Protocol):
    async def start(self) -> None:
        """Initialize the backend."""

    async def stop(self) -> None:
        """Flush pending writes and close the backend."""

    async def store(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a value under a key. Overwrites if exists."""

    async def retrieve(self, key: str) -> Any | None:
        """Retrieve a value by key. Returns None if not found or expired."""

    async def query(self, filter: MemoryFilter) -> dict[str, Any]:
        """Query entries matching the filter. Returns {key: value} pairs."""

    async def delete(self, key: str) -> bool:
        """Delete a key. Returns True if key existed."""

    async def clear(self, namespace: str | None = None) -> int:
        """Clear all entries, optionally within a namespace. Returns count removed."""

    async def snapshot(self) -> dict[str, Any]:
        """Capture current state as a serializable dict."""

    async def restore(self, snapshot: dict[str, Any]) -> None:
        """Replace current state from a snapshot."""

    async def keys(self, namespace: str | None = None) -> list[str]:
        """List all keys, optionally within a namespace."""

    async def size(self) -> int:
        """Return the number of entries currently stored."""
```

### MemoryFilter

```python
@dataclass
class MemoryFilter:
    namespace: str | None = None
    key_prefix: str | None = None
    value_type: type | None = None
    predicate: Callable[[str, Any], bool] | None = None

    def matches(self, key: str, value: Any) -> bool:
        """Check if an entry passes this filter."""
```

### MemoryConfig

```python
@dataclass
class MemoryConfig:
    backend: Literal["memory", "sqlite", "redis"] = "memory"
    max_entries: int = 10000
    default_ttl: float | None = None
    cleanup_interval: float = 60.0
    sqlite_path: str = "artax_memory.db"
    redis_url: str = "redis://localhost:6379/0"
    event_mapping: dict[str, dict[str, Any]] | None = None
```

### Backends

**InMemoryBackend** — dict-based, no persistence, fastest. Default for development.

**SQLiteBackend** — file-based persistence via `aiosqlite`. Stores entries in a single table with indexed key and namespace. Suitable for single-machine production.

**RedisBackend** — network-based via `redis.asyncio`. Stores entries as Redis hashes with TTL support via `EXPIRE`. Suitable for distributed or high-throughput scenarios.

---

## 6. Acceptance Criteria

1. `store("key", value)` followed by `retrieve("key")` returns the exact value.
2. `store("key", value, ttl=1.0)` — after 1.1 seconds, `retrieve("key")` returns `None`.
3. `query(MemoryFilter(namespace="chromium"))` returns only entries in the "chromium" namespace.
4. `query(MemoryFilter(key_prefix="dom."))` returns only keys starting with "dom.".
5. `query(MemoryFilter(value_type=list))` returns only entries where the value is a list.
6. `snapshot()` returns a dict containing all current entries with metadata.
7. `restore(snapshot)` replaces all current entries with those in the snapshot.
8. `clear()` removes all entries; `clear(namespace="chromium")` removes only chromium entries.
9. `delete("key")` returns `True` if key existed, `False` otherwise.
10. When `max_entries` is reached, LRU eviction frees space without error.
11. Expired entries are cleaned up during periodic cleanup (within `cleanup_interval` seconds).
12. InMemory backend loses all data on `stop()`.
13. SQLite backend persists data across `stop()`/`start()` cycles.
14. Redis backend connects and disconnects cleanly with configured `redis_url`.
15. Event-driven updates process configured event mappings and store extracted values.
16. Memory emits `memory.evicted` events when entries are evicted.
17. Memory emits `memory.updated` events when entries are stored or deleted.
18. The memory subsystem contains no driver-specific or scheduler-specific logic.

---

## 7. Future Extensions

1. **Vector embeddings.** Store embeddings alongside values. Support similarity queries via cosine distance. Integrate with embedding models for semantic memory.

2. **Memory compaction.** Background task that merges related entries, summarizes old entries via LLM, or compresses large payloads.

3. **Full-text search.** Index entry values for text search. Use SQLite FTS5 or Redisearch.

4. **Distributed memory.** Coordinate multiple memory instances via Redis pub/sub or CRDTs. Enable cross-runtime memory sharing.

5. **Memory priorities.** Assign priority levels to entries. High-priority entries survive eviction longer.

6. **Memory annotations.** Attach metadata to entries (e.g., "this value came from event X", "this is a user-provided fact").

7. **Memory export/import.** Export memory state as JSON or msgpack. Import from external sources (knowledge bases, config files).

8. **Pluggable eviction policies.** Support LRU, LFU (least frequently used), FIFO, and custom eviction strategies.

9. **Memory limits per namespace.** Set per-namespace capacity limits to prevent one subsystem from dominating memory.

---

## 8. Resolved Decisions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | `store()` async for all backends? | **Yes, all async** | Consistent interface. InMemory wraps dict in coroutine trivially. |
| 2 | TTL enforced lazy or eager? | **Lazy on access** | Simpler, no background task. Standard pattern for TTL caches. |
| 3 | `snapshot()` includes TTL? | **Yes, include TTL** | Faithful state capture. Restored snapshots preserve original TTL semantics. |
| 4 | Events for every operation or significant only? | **Significant changes only** | New key, eviction, clear emit events. Reduce noise, meaningful signals only. |
| 5 | InMemory uses dict or OrderedDict? | **OrderedDict** | Built-in LRU tracking. Supports eviction ordering without extra data structure. |
| 6 | `MemoryFilter.predicate` receives what? | **Full MemoryEntry** | More context for filtering decisions. Allows filtering on timestamp, type, metadata. |
| 7 | SQLite WAL mode? | **Yes, WAL mode** | Standard for concurrent read/write. Single config line. |
| 8 | Redis connection pooling? | **Yes, pool size 10** | Standard Redis practice. Avoids connection overhead. |

---

*Document created: 2026-07-26*
*Last updated: 2026-07-26*
