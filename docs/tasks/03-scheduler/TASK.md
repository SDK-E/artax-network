# Task 03: Implement Scheduler

## Objective

Implement the event scheduler for Artax Network. The scheduler manages priority queuing, delayed event delivery, and tick-based processing. It ensures events are processed with appropriate priorities and timing.

## Reference Documents

- **PRD**: `../../prd/prd-scheduler.md` — all resolved design decisions
- **Existing scaffolding**: `../../../artax/scheduler/core.py`
- **Depends on**: `../../../artax/events/types.py` (EventType, SemanticEvent, EventBus) — must be implemented first
- **Scheduler design**: `../../scheduler.md`

## Resolved Design Decisions

1. **Log warning + drop on full queue** — no exception, prevent blocking
2. **Runtime calls `tick()`** — unified event loop, not own asyncio.Task
3. **Deliver ALL pending events on stop** — clean shutdown, nothing lost
4. **Delayed events respect priority when ready** — re-enter priority queue
5. **Emit `scheduler.queue.depth` event** — threshold-triggered, dashboard monitoring
6. **`tick_interval_ms` configurable at runtime** — tuning without restart
7. **Support cooperative cancellation** — `asyncio.CancelledError` for long handlers
8. **`queue_status()` is a method** — on-demand, dashboard polls

## Current State

Existing scaffolding is a stub. Key gaps:

- `Priority` enum values don't match PRD (LOW/NORMAL/HIGH/CRITICAL vs URGENT/HIGH/MEDIUM/LOW)
- `ScheduleEntry` missing `deliver_at`, `status` fields
- `Scheduler` Protocol missing `queue_status()` method, `schedule()` missing `priority` param
- `SchedulerConfig`, `SchedulerStatus`, `ScheduleStatus` dataclasses missing entirely
- `MemoryScheduler` is empty stub

## Implementation Steps

### Step 1: Reconcile `../../../artax/scheduler/core.py`

Update types to match PRD:

```python
class Priority(IntEnum):
    URGENT = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class ScheduleStatus(Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class ScheduleEntry:
    entry_id: str  # UUID hex string
    event: Event
    deliver_at: float  # time.monotonic() timestamp
    created_at: float
    priority: Priority
    status: ScheduleStatus


class SchedulerConfig:
    tick_interval_ms: int = 100
    max_queue_size: int = 10000
    emergency_drain: bool = True  # deliver all on shutdown
    queue_depth_threshold: int = 1000  # emit event when exceeded


class SchedulerStatus:
    paused: bool
    pending_count: int  # total across all priorities
    urgent_count: int
    high_count: int
    medium_count: int
    low_count: int
    total_scheduled: int
    total_delivered: int
    total_cancelled: int
    tick_count: int


class Scheduler(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def schedule(
        self, event: Event, priority: Priority = Priority.MEDIUM, delay: float | None = None
    ) -> str: ...
    async def cancel(self, entry_id: str) -> bool: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    async def tick(self) -> None: ...
    def queue_status(self) -> SchedulerStatus: ...
    @property
    def pending_count(self) -> int: ...
```

### Step 2: Implement `MemoryScheduler`

Full production implementation:

- **Constructor**: `__init__(self, config: SchedulerConfig, event_bus: EventBus)`
- **Storage**: `dict[str, ScheduleEntry]` for all entries + `heapq` based priority queue for ready events
- **Priority queue**: list of tuples `(deliver_at, priority_value, entry_id)` — heapq sorts by deliver_at first, then priority
- **`start()`**: reset stats, emit RUNTIME_STARTED event
- **`stop()`**: if `emergency_drain`, deliver all remaining events; cancel all pending
- **`schedule(event, priority, delay)`**:
  1. Check queue size — if full, log warning and return empty string
  2. Calculate `deliver_at = time.monotonic() + (delay or 0)`
  3. Create ScheduleEntry with UUID hex ID
  4. Push to heapq with `(deliver_at, priority.value, entry_id)`
  5. Store in entries dict
  6. Increment stats
  7. Return entry_id
- **`cancel(entry_id)`**:
  1. Find entry, set status to CANCELLED
  2. Remove from entries dict (heapq removal is lazy — skip during tick)
  3. Return True if found, False otherwise
- **`pause()`**: set paused flag, stop tick processing
- **`resume()`**: clear paused flag
- **`tick()`**:
  1. If paused, return
  2. Peek at heapq top — if deliver_at <= now, pop and deliver
  3. Publish event to EventBus
  4. Set status to DELIVERED
  5. Repeat for all ready entries
  6. If queue depth exceeds threshold, emit scheduler.queue.depth event
  7. Increment tick_count
- **`queue_status()`**: compute and return SchedulerStatus from current state

### Step 3: Write tests

Create `tests/test_scheduler_types.py`:
- Test Priority enum ordering (URGENT < HIGH < MEDIUM < LOW)
- Test ScheduleEntry creation
- Test SchedulerConfig defaults
- Test SchedulerStatus fields

Create `tests/test_memory_scheduler.py`:
- Schedule event with default priority
- Schedule event with specific priority
- Schedule event with delay (not immediately deliverable)
- Tick delivers ready events
- Tick skips future events
- Priority ordering (higher priority delivered first when ready at same time)
- Cancel pending entry returns True
- Cancel non-existent entry returns False
- Cancelled entries not delivered on tick
- Pause stops tick delivery
- Resume allows tick delivery again
- Queue full logs warning and returns empty string
- Stop with emergency_drain delivers all
- Stop without emergency_drain cancels low priority
- queue_status returns accurate counts
- Stats tracking (scheduled, delivered, cancelled counts)
- Tick count increments
- Concurrent schedule from multiple coroutines
- Large number of entries (performance)

## Technical Constraints

- `heapq` for priority queue (efficient O(log n) push/pop)
- Lazy cancellation: mark entries as CANCELLED, skip during tick (no heapq removal)
- `time.monotonic()` for all timestamps
- `uuid.uuid4().hex` for entry IDs
- All methods async except `pause()`, `resume()`, `queue_status()`, `pending_count`
- Strict typing for `mypy --strict`

## Quality Gates

```bash
python3 -m py_compile artax/scheduler/core.py
python3 -c "from artax.scheduler.core import MemoryScheduler, SchedulerConfig; print('OK')"
pytest tests/test_scheduler_types.py tests/test_memory_scheduler.py -v
```

## Files

| Action | File |
|--------|------|
| MODIFY | `../../../artax/scheduler/core.py` |
| CREATE | `tests/test_scheduler_types.py` |
| CREATE | `tests/test_memory_scheduler.py` |
