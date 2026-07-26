# Working Memory Deep Dive

Working memory is the agent's short-term context. It holds the events the agent is currently reasoning over. It is bounded, filtered, and ephemeral — designed for the present decision cycle, not for long-term storage.

## What is Working Memory

Working memory is not a database. It is not a cache. It is the agent's attention window — the slice of the event stream that matters right now.

Think of it as a sliding window over the event stream. New events enter at the front. Old events exit at the back. The agent sees only what is in the window. The window moves as events arrive and time passes.

This is different from long-term storage. Long-term storage persists across sessions and grows unbounded. Working memory is bounded, volatile, and optimized for fast reads. When the runtime shuts down, working memory is gone (unless explicitly snapshotted).

## Memory as Interface

Working memory is defined as a Protocol class in `artax/core/protocols.py`. The runtime interacts with memory through this interface. The actual implementation — in-memory dict, SQLite, Redis — is a configuration choice.

```python
class MemoryBackend(Protocol):
    """Protocol for working memory backends."""

    async def store(self, event: SemanticEvent) -> None:
        """Store an event in memory."""
        ...

    async def retrieve(self, event_id: str) -> SemanticEvent | None:
        """Retrieve a specific event by ID."""
        ...

    async def query(
        self,
        topic: str | None = None,
        time_range: tuple[float, float] | None = None,
        priority_min: int | None = None,
        limit: int = 100,
    ) -> list[SemanticEvent]:
        """Query events matching filters."""
        ...

    async def snapshot(self) -> MemorySnapshot:
        """Capture a snapshot of current memory state."""
        ...

    async def restore(self, snapshot: MemorySnapshot) -> None:
        """Restore memory from a snapshot."""
        ...

    async def clear(self) -> None:
        """Remove all events from memory."""
        ...

    @property
    def size(self) -> int:
        """Number of events currently in memory."""
        ...
```

### Why a Protocol

Any class that implements these methods satisfies the memory interface. The runtime does not care whether the backend is a dict, a SQLite database, or a Redis cluster. This means:

- You can swap backends by changing one configuration variable.
- You can test with an in-memory backend and deploy with SQLite.
- Third-party backends can be developed without modifying the runtime.

## Memory Operations

### Store

Add an event to working memory. If memory is at capacity, the eviction policy removes the least-relevant event to make room.

```python
await memory.store(SemanticEvent(
    topic="chromium.dom.click",
    data={"selector": "button#submit"},
    source="chromium",
    timestamp=time.time(),
    event_id=str(uuid4()),
    priority=5,
))
```

**Eviction policy:** When capacity is reached, the event with the lowest priority is evicted first. If priorities are equal, the oldest event is evicted. This ensures high-priority events persist longer.

### Retrieve

Fetch a specific event by its unique ID. Returns `None` if the event is not in memory.

```python
event = await memory.retrieve("evt-abc-123")
if event:
    print(f"Found: {event.topic}")
```

### Query

Search for events matching one or more filters. All filters are combined with AND logic.

```python
# All chromium DOM events in the last 60 seconds
events = await memory.query(
    topic="chromium.dom.*",
    time_range=(time.time() - 60, time.time()),
)

# High-priority events only
events = await memory.query(priority_min=7)

# Most recent 10 events
events = await memory.query(limit=10)
```

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| `topic` | `str \| None` | Topic pattern (supports `*` wildcard) |
| `time_range` | `tuple[float, float] \| None` | (start, end) timestamps |
| `priority_min` | `int \| None` | Minimum priority (inclusive) |
| `limit` | `int` | Maximum events returned (default: 100) |

### Snapshot

Capture the entire state of working memory as a serializable object. Useful for checkpointing, debugging, and session resumption.

```python
snapshot = await memory.snapshot()
# snapshot contains all events, metadata, and configuration
```

### Restore

Rebuild working memory from a snapshot. Replaces the current contents entirely.

```python
await memory.restore(snapshot)
```

### Clear

Remove all events from memory. Used during runtime reset or fresh start.

```python
await memory.clear()
```

## Memory Backends

### In-Memory (Default)

The default backend stores events in a Python dictionary. Fast, no external dependencies, no persistence.

```python
from artax.runtime.memory.memory import InMemoryBackend

memory = InMemoryBackend(capacity=1000)
```

**Pros:** Fastest option. No setup. No external services.
**Cons:** Volatile. Lost on process restart. No sharing across processes.

### SQLite

Stores events in a SQLite database. Provides persistence across restarts and basic querying via SQL.

```python
from artax.runtime.memory.sqlite import SQLiteBackend

memory = SQLiteBackend(
    db_path="./data/memory.db",
    capacity=10000,
)
```

**Pros:** Persistent. No external services. SQL queries. Atomic writes.
**Cons:** Slower than in-memory. Single-process access. File-based.

### Redis

Stores events in Redis. Provides persistence, sharing across processes, and fast reads.

```python
from artax.runtime.memory.redis import RedisBackend

memory = RedisBackend(
    url="redis://localhost:6379",
    capacity=50000,
    prefix="artax:memory",
)
```

**Pros:** Fast. Persistent. Shared across processes. Supports pub/sub.
**Cons:** Requires Redis server. Network overhead. Serialization cost.

### Choosing a Backend

| Use Case | Backend |
|---|---|
| Development, testing | `memory` (default) |
| Single-process production | `sqlite` |
| Multi-process or distributed | `redis` |
| Performance-critical | `memory` |
| Session persistence required | `sqlite` or `redis` |

## Memory Filtering

The agent can adjust its attention scope — which events it is currently interested in. Filtering narrows the events the agent reasons over without removing them from memory.

### Attention Scope

The agent defines an attention scope as a set of topic patterns and time ranges:

```python
scope = AttentionScope(
    topics=["chromium.dom.*", "scheduler.tick"],
    time_range=(time.time() - 300, time.time()),  # last 5 minutes
    min_priority=3,
)
```

### Filtered Retrieval

When the agent queries working memory, the attention scope is applied:

```python
relevant_events = await memory.query(
    topic=scope.topics[0],  # simplified; actual implementation merges topics
    time_range=scope.time_range,
    priority_min=scope.min_priority,
)
```

### Dynamic Scoping

The agent can change its attention scope at any time. During a navigation task, it focuses on `chromium.navigation` events. During a form-fill task, it focuses on `chromium.dom.input` events. The memory contents do not change — only the agent's view of them.

## Memory Snapshots

Snapshots capture the complete state of working memory at a point in time.

### What a Snapshot Contains

```python
@dataclass(frozen=True)
class MemorySnapshot:
    events: list[SemanticEvent]    # all events in memory
    capacity: int                  # maximum capacity
    timestamp: float               # when the snapshot was taken
    metadata: dict[str, Any]       # additional context
```

### Use Cases

| Use Case | How |
|---|---|
| **Debugging** | Snapshot memory, inspect contents offline |
| **Session resumption** | Snapshot before shutdown, restore on startup |
| **State persistence** | Periodic snapshots to disk or database |
| **Testing** | Snapshot before test, restore after test |
| **Checkpointing** | Snapshot before risky operation, restore if it fails |

### Creating a Snapshot

```python
snapshot = await memory.snapshot()
```

### Saving a Snapshot

```python
import json

with open("./snapshots/memory_001.json", "w") as f:
    json.dump(asdict(snapshot), f)
```

### Restoring a Snapshot

```python
with open("./snapshots/memory_001.json") as f:
    snapshot_data = json.load(f)

snapshot = MemorySnapshot(**snapshot_data)
await memory.restore(snapshot)
```

## Memory and the Event Loop

The memory subsystem integrates with the core loop as follows:

```
Event arrives on bus
    → Memory stores the event
        → Agent queries memory with attention scope
            → Agent reasons over filtered events
                → Agent produces action
                    → Action flows through bus
```

Memory is always up-to-date by the time the agent reasons. There is no stale read. The agent always sees the latest events that match its attention scope.

### Eviction During Reasoning

If an event is evicted while the agent is reasoning over it, the agent sees a consistent snapshot. Eviction happens between reasoning cycles, not during them. This prevents the agent from seeing partially-updated memory.
