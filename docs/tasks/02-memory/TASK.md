# Task 02: Working Memory — Gap Analysis

**Layer:** 1a (Memory)
**Subsystem:** `artax.memory`
**Status:** Implemented with gaps
**PRD Reference:** `docs/prd/prd-memory.md`

---

## Senior Product Manager Perspective

### What Working Memory Is Supposed to Do

Working memory is the agent's short-term context — the scratchpad that holds the current page's DOM summary, the last action's result, the active intent, and whatever else is relevant right now. It is not a database; it is a bounded, attention-scoped store that persists across events within a single runtime session.

The memory subsystem must:

1. **Store and retrieve key-value pairs** — Keys are namespaced (e.g., `chromium.dom.title`, `scheduler.active_intent`). Values are JSON-serializable. Namespaces isolate data by subsystem.

2. **Query by filter** — Memory supports querying stored entries by key prefix, value type, namespace, or custom predicate. Queries return matching entries without iterating the entire store.

3. **Support TTL (Time-To-Live)** — Entries can have a time-to-live. Expired entries are evicted on access (lazy enforcement) or during periodic cleanup sweeps. TTL enables automatic context decay — old observations fade without explicit eviction.

4. **LRU eviction** — When memory reaches capacity (`max_entries`, default 10000), the least-recently-accessed entry is evicted to make room for new ones. Eviction emits a `memory.evicted` event.

5. **Event-driven updates** — Memory subscribes to events on the EventBus and updates itself based on event content. Configuration specifies which events map to which memory operations (e.g., `PAGE_LOADED` → store page title, `ACTION_COMPLETED` → store action result).

6. **Snapshots for state persistence** — Memory supports `snapshot()` which captures the entire current state as a serializable object, and `restore(snapshot)` which replaces the current state from a snapshot. Snapshots enable checkpointing and debugging.

7. **Pluggable backends** — Memory supports three backends: InMemory (dict-based, fastest, lost on restart), SQLite (file-based, persistent), and Redis (network-based, shared). The backend is selected at config time.

8. **Emit meaningful events** — Memory emits `MEMORY_UPDATED` events when entries are stored, deleted, or cleared. It emits `memory.evicted` events when entries are evicted due to capacity.

### What Currently Works

The implementation provides:

- **InMemoryStore** — Dict-backed working memory using `OrderedDict` for LRU eviction. Supports all operations: store, retrieve, delete, query, clear, keys, size, snapshot, restore. TTL enforcement is lazy (checked on access). Periodic TTL cleanup sweeps run in a background task. Emits `MEMORY_UPDATED` events for new keys, evictions, and clears.

- **SQLiteMemoryStore** — Persistent working memory backed by SQLite with WAL mode. Same full interface as InMemoryStore. Uses `asyncio.to_thread` for non-blocking I/O. LRU eviction via `accessed_at` column. Periodic TTL cleanup in background task.

- **RedisMemoryStore** — Stub with all methods raising `NotImplementedError`. This is expected — Redis support is a future concern.

- **MemoryConfig** — Configuration dataclass with backend selection, max entries, default TTL, cleanup interval, SQLite path, and Redis URL.

- **MemoryEntry, MemoryFilter, MemorySnapshot** — Full data model with all fields specified in the PRD.

### What Is Missing or Different From the Plan

**Gap 1: Event-driven updates (event mapping) are not implemented**

The PRD specifies that memory should subscribe to the EventBus and process events according to a configured mapping. For example, `PAGE_LOADED` → store page title, `ACTION_COMPLETED` → store action result. The `MemoryConfig` has no `event_mapping` field, and neither `InMemoryStore` nor `SQLiteMemoryStore` subscribes to the EventBus to process event-driven updates. The memory store emits events (MEMORY_UPDATED) but does not consume them.

**Gap 2: `query()` returns `dict[str, Any]` but the PRD interface says it should return `dict[str, Any]` — this matches. However, the PRD's `MemoryFilter.predicate` signature differs from the implementation.**

The PRD says `predicate: Callable[[str, Any], bool]` (receives key and value). The implementation uses `predicate: Callable[[MemoryEntry], bool | Awaitable[bool]]` (receives full MemoryEntry). The task file resolved this to use `MemoryEntry` in predicates, which is the more powerful approach. This is a deliberate design decision, not a bug, but it differs from the PRD's original interface.

**Gap 3: `snapshot()` returns a `MemorySnapshot` dataclass, not a plain `dict[str, Any]` as the PRD interface specifies.**

The PRD's `WorkingMemory` protocol says `snapshot()` returns `dict[str, Any]`. The implementation returns a `MemorySnapshot` dataclass. This is a type mismatch with the protocol definition. The `MemorySnapshot` dataclass is more structured and type-safe, but it does not satisfy the protocol as written.

**Gap 4: `restore()` expects a `MemorySnapshot` dataclass, not a plain `dict[str, Any]` as the PRD interface specifies.**

Same issue as Gap 3 — the protocol says `restore(snapshot: dict[str, Any])` but the implementation expects `MemorySnapshot`.

**Gap 5: The PRD says `store()` should have a simple signature `store(key, value, ttl=None)` without a namespace parameter, but the implementation includes `namespace` as a parameter with default "default".**

The PRD's `WorkingMemory` protocol shows `store(self, key: str, value: Any, ttl: float | None = None)`. The implementation has `store(self, key: str, value: Any, namespace: str = "default", ttl: float | None = None)`. The namespace parameter is a useful extension but is not in the PRD's protocol definition.

**Gap 6: The PRD says `retrieve()` should have signature `retrieve(self, key: str)` without namespace, but the implementation includes `namespace: str = "default"`.**

Same pattern as Gap 5.

**Gap 7: The PRD says `delete()` should have signature `delete(self, key: str)` without namespace, but the implementation includes `namespace: str = "default"`.**

Same pattern as Gap 5.

**Gap 8: The PRD says `keys()` should have signature `keys(self, namespace: str | None = None)` but the implementation has `keys(self, namespace: str = "default")`.**

The PRD allows `None` to mean "all namespaces" but the implementation defaults to `"default"` and does not support `None`.

**Gap 9: The PRD says `size()` should have signature `size(self)` without namespace, but the implementation has `size(self, namespace: str | None = None)`.**

The implementation supports namespace-scoped size counting, which is a useful extension beyond the PRD's protocol.

### Acceptance Criteria (What Needs to Pass)

1. Store and retrieve basic values works correctly
2. TTL expiration works — after TTL expires, retrieve returns None
3. Namespace isolation — same key in different namespaces does not conflict
4. LRU eviction — filling to capacity evicts the least-recently-accessed entry
5. Query with namespace filter works
6. Query with key_prefix filter works
7. Query with async predicate works
8. Query respects limit
9. Delete existing key returns True, non-existent key returns False
10. Clear specific namespace returns correct count
11. Clear all namespaces returns correct count
12. Keys returns correct keys per namespace (including None for all namespaces)
13. Size returns correct count (including namespace-scoped counting)
14. Snapshot captures full state including TTLs
15. Restore populates from snapshot
16. Event emitted on new key store (with event_bus)
17. Event emitted on eviction
18. Event emitted on clear
19. Start/stop lifecycle works
20. Concurrent store/retrieve from multiple coroutines works
21. Event-driven updates process configured event mappings (MISSING)
22. `snapshot()` and `restore()` satisfy the `WorkingMemory` protocol signatures (MISSING)

---

## Senior Engineer Perspective

### Architecture Assessment

The memory subsystem is well-architected with a clean protocol interface (`WorkingMemory`) and three backend implementations. The `InMemoryStore` and `SQLiteMemoryStore` are production-quality. The `RedisMemoryStore` is a stub, which is acceptable for v0.1.

Key design decisions that were correctly implemented:

- All backends are async (consistent interface)
- Lazy TTL enforcement on access (no background cleanup needed for correctness)
- OrderedDict for LRU tracking in InMemoryStore
- Full MemoryEntry in predicates (more context for filtering)
- SQLite WAL mode for concurrent read/write
- Event emission for significant changes only (new key, eviction, clear)

### Critical Gaps

1. **Event-driven updates are completely missing.** The PRD specifies that memory should subscribe to the EventBus and update itself based on event content. This is a first-class feature in the PRD, not an optional extension. The `MemoryConfig` has no `event_mapping` field, and neither store subscribes to the EventBus. Without this, memory is purely manual — the agent or runtime must explicitly call `store()` for every piece of state. The PRD envisions memory being updated automatically by processing events.

2. **Protocol signature mismatches.** The `WorkingMemory` protocol defines `snapshot()` returning `dict[str, Any]` and `restore()` accepting `dict[str, Any]`, but the implementation uses `MemorySnapshot` dataclass. This means any code that creates a mock or stub following the protocol will return a dict, but the real implementation expects a dataclass. This is a type compatibility issue.

3. **Namespace handling differs from PRD protocol.** The PRD protocol does not include `namespace` parameters in `store()`, `retrieve()`, or `delete()`, but the implementation adds them. This is a design decision that goes beyond the PRD. If the protocol is meant to be the source of truth, these extra parameters are out of spec.

### Recommended Actions

1. **Implement event-driven updates.** Add an `event_mapping` field to `MemoryConfig`. Have `InMemoryStore` and `SQLiteMemoryStore` subscribe to the EventBus on `start()` and process events according to the mapping. This is a significant feature that enables the memory subsystem to be truly event-driven as the PRD intends.

2. **Align protocol signatures.** Either update the `WorkingMemory` protocol to accept/return `MemorySnapshot` (recommended, since it's more type-safe), or make `snapshot()` and `restore()` work with plain dicts as the PRD specifies.

3. **Decide on namespace parameters.** If namespace is a core concept (which it is, given the data model), it should be in the protocol. If it's an implementation detail, it should not be in the protocol signature. The current state is ambiguous.

4. **Add `keys(namespace=None)` support** for listing keys across all namespaces.

### Gap Summary

| Gap | Severity | Description |
|-----|----------|-------------|
| Event-driven updates missing | HIGH | Memory does not subscribe to EventBus or process event mappings |
| Protocol signature mismatch (snapshot/restore) | MEDIUM | Protocol says dict, implementation uses MemorySnapshot dataclass |
| Namespace params beyond PRD protocol | LOW | store/retrieve/delete include namespace param not in PRD protocol |
| keys() does not support None for all namespaces | LOW | PRD says namespace=None means all, implementation defaults to "default" |
| RedisMemoryStore is a stub | PLANNED | Expected for v0.1; Redis is a future concern |
