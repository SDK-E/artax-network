# Task 01: Implement Event System

## Objective

Implement the complete event system for Artax Network. This is the foundation layer (Layer 0) — all other subsystems depend on it. The event system enables environments to emit semantic events into a shared runtime.

## Reference Documents

- **PRD**: `docs/prd/prd-events.md` — contains all resolved design decisions
- **Existing scaffolding**: `artax/events/types.py`, `artax/events/bus.py`
- **Architecture**: `ARCHITECTURE.md` — event flow description
- **Event model**: `docs/event-model.md` — detailed event system design

## Resolved Design Decisions

These decisions were made during PRD review and are FINAL:

1. `publish()` returns `Future` — caller decides whether to await
2. Thread-safe ring buffer for EventBus history
3. Wildcard subscription support (`source="chromium.*"`)
4. Async-capable filter predicates
5. Emit `subscription.dropped` event when subscriber queue overflows
6. UUID4 event IDs (globally unique)
7. Periodic `EventBusStats` events emitted on the bus
8. Events carry `correlation_id` to link related events across subsystems

## Current State

The existing scaffolding has interfaces that **DO NOT** align with the PRD. You MUST reconcile them. Key mismatches:

- `EventType` enum has wrong values (OBSERVATION, ACTION_REQUEST, etc. instead of DOM_CHANGED, PAGE_LOADED, etc.)
- `SemanticEvent` missing `correlation_id` field
- `EventFilter` missing `predicate` callable and `matches()` method
- `EventBus` Protocol missing `history()`, `stats()`, `start()`, `stop()` methods
- `EventBusConfig`, `EventBusStats` dataclasses missing entirely
- `MemoryEventBus` is a stub with all `pass`

## Implementation Steps

### Step 1: Reconcile `artax/events/types.py`

Update the file to match PRD decisions:

```python
# EventType must include all values from the PRD:
class EventType(Enum):
    # Browser events
    DOM_CHANGED = "dom_changed"
    PAGE_LOADED = "page_loaded"
    PAGE_ERROR = "page_error"
    USER_INPUT = "user_input"
    SCREENSHOT_TAKEN = "screenshot_taken"
    # Action events
    ACTION_REQUESTED = "action_requested"
    ACTION_COMPLETED = "action_completed"
    ACTION_FAILED = "action_failed"
    # Memory events
    MEMORY_UPDATED = "memory_updated"
    # Scheduler events
    SCHEDULE_TICK = "schedule_tick"
    # Health events
    HEALTH_CHECK = "health_check"
    # Runtime events
    RUNTIME_STARTED = "runtime_started"
    RUNTIME_STOPPING = "runtime_stopping"
    RUNTIME_ERROR = "runtime_error"
    # Driver events
    DRIVER_CONNECTED = "driver_connected"
    DRIVER_DISCONNECTED = "driver_disconnected"
    DRIVER_UNHEALTHY = "driver_unhealthy"
    # Generic
    CUSTOM = "custom"
```

- `SemanticEvent`: frozen dataclass with `event_id` (UUID), `type` (EventType), `source` (str), `timestamp` (float, epoch), `payload` (dict), `metadata` (dict), `correlation_id` (UUID | None)
- `EventFilter`: frozen dataclass with `type` (EventType | None), `source` (str | None), `predicate` (Callable[[Event], bool | Awaitable[bool]] | None), `after` (float | None), `limit` (int | None). Include `async matches(self, event: Event) -> bool` method that checks all fields including wildcard source matching and predicate evaluation.
- `EventBusConfig`: dataclass with `history_size` (int = 1000), `max_queue_size` (int = 10000), `dispatch_timeout` (float = 1.0)
- `EventBusStats`: dataclass with `events_published` (int), `events_delivered` (int), `subscriptions_active` (int), `subscriptions_dropped` (int), `queue_depth` (int)
- Keep the `Event` Protocol, `Subscription` Protocol

### Step 2: Reconcile `artax/events/bus.py`

Update the `EventBus` Protocol:

```python
class EventBus(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def publish(self, event: Event) -> Future[None]: ...
    async def subscribe(self, filter: EventFilter, callback: Callable[[Event], Awaitable[None]]) -> str: ...
    async def unsubscribe(self, subscription_id: str) -> None: ...
    async def drain(self) -> None: ...
    def history(self, limit: int | None = None) -> list[Event]: ...
    def stats(self) -> EventBusStats: ...
```

### Step 3: Implement `MemoryEventBus`

Full production implementation:

- **Constructor**: takes `EventBusConfig`
- **Ring buffer**: `collections.deque(maxlen=config.history_size)` for event history
- **Subscriptions**: `dict[str, SubscriptionState]` where `SubscriptionState` holds the filter, callback, `asyncio.Queue`, and stats
- **`start()`**: set running flag, start stats emission task
- **`stop()`**: set stopped flag, cancel stats task, drain all queues
- **`publish(event)`**: 
  1. Append to history ring buffer
  2. For each subscription: check filter matches (source wildcards, type, predicate)
  3. If queue full: drop event, increment dropped count, emit `subscription.dropped` event
  4. Put event in subscription's asyncio.Queue
  5. Return completed Future
- **`subscribe(filter, callback)`**: create subscription with queue, start consumer task, return subscription ID
- **`unsubscribe(id)`**: cancel consumer task, remove subscription
- **`drain()`**: deliver all queued events, then stop
- **`history(limit)`**: return events from ring buffer
- **`stats()`**: return current EventBusStats

### Step 4: Write tests

Create `tests/test_event_types.py`:
- Test all EventType enum values exist
- Test SemanticEvent.create() factory
- Test EventFilter.matches() with type filter
- Test EventFilter.matches() with source exact match
- Test EventFilter.matches() with source wildcard
- Test EventFilter.matches() with async predicate
- Test EventFilter.matches() with after timestamp
- Test correlation_id propagation

Create `tests/test_event_bus.py`:
- Test publish then subscribe receives event
- Test wildcard subscription receives matching events
- Test wildcard subscription ignores non-matching events
- Test async predicate filter
- Test queue overflow emits subscription.dropped
- Test history ring buffer respects max size
- Test stats accuracy
- Test drain delivers all queued events
- Test start/stop lifecycle
- Test concurrent publish from multiple coroutines
- Test unsubscribe stops delivery

## Technical Constraints

- All code async (`asyncio`)
- Thread safety via `asyncio.Lock`
- `fnmatch.fnmatch()` for wildcard source matching
- `uuid.uuid4()` for event IDs
- `asyncio.Queue` for per-subscription queues
- `collections.deque(maxlen=N)` for ring buffer
- `time.time()` for epoch timestamps
- Strict type hints for `mypy --strict`

## Quality Gates

Run these after implementation:

```bash
python3 -m py_compile artax/events/types.py
python3 -m py_compile artax/events/bus.py
python3 -c "from artax.events.bus import MemoryEventBus; print('OK')"
pytest tests/test_event_types.py tests/test_event_bus.py -v
```

## Files

| Action | File |
|--------|------|
| MODIFY | `artax/events/types.py` |
| MODIFY | `artax/events/bus.py` |
| CREATE | `tests/test_event_types.py` |
| CREATE | `tests/test_event_bus.py` |
