# PRD: Event System

**Subsystem:** `artax.events`
**Version:** 0.1
**Status:** Draft

---

## 1. Problem Statement

AI agents operating in continuous environments need semantic understanding that persists and accumulates — not discrete tool-call responses that vanish between invocations. Current approaches treat environment interaction as request-response: send a tool call, get a result, forget the context. This breaks embodied AI, where the agent must continuously perceive, reason, and act within an evolving world.

The event system solves this by providing a continuous, typed, async communication channel between all runtime subsystems. Every observation from a driver, every state change in memory, every scheduled task completion, and every action dispatched to a driver flows as a typed event through a central EventBus. The agent never loses context because events are never dropped — they are published, routed to subscribers, and delivered asynchronously.

The event system is the nervous system of Artax. Everything connects through it. Nothing bypasses it.

---

## 2. Goals

1. **Event creation.** Any subsystem can create events with a defined type, source identifier, timestamp, and arbitrary payload. Events are Python dataclasses with type annotations. The base `SemanticEvent` type carries structured meaning — not raw strings.

2. **Publishing.** Any subsystem can publish events to the EventBus. Publishing is fire-and-forget — the publisher does not block until subscribers process the event. Publishing never raises exceptions to the caller.

3. **Subscription.** Any subsystem can subscribe to events by type, source, or custom filter. Subscribers receive events asynchronously through async callbacks. Multiple subscribers can listen to the same event without interference.

4. **Filtering.** The EventBus supports composable filters: type-based (`EventFilter(type=...)`), source-based (`EventFilter(source=...)`), and custom predicate-based (`EventFilter(predicate=...)`). Filters are AND-combined when multiple criteria are specified.

5. **Typed events.** All events carry their type as a Python enum or string literal. Subsystems can use type hints to declare which events they consume. The event system enforces type safety at subscription time where possible.

6. **Async delivery.** Events are delivered to subscribers through the asyncio event loop. Delivery is non-blocking — a slow subscriber does not block the publisher or other subscribers. Events are dispatched to concurrent tasks.

7. **Event history.** The EventBus maintains a bounded in-memory ring buffer of the most recent N events (configurable, default 1000). This buffer is used by the dashboard and for debugging, not for event replay or sourcing.

---

## 3. Non-Goals

1. **Event persistence.** Events are not written to disk or external storage in v0.1. A runtime restart loses all events. Persistence is a v0.2 concern.

2. **Event replay.** There is no mechanism to replay historical events to new subscribers. Once delivered, events are not re-sent. Replay is a v0.2 concern.

3. **Event sourcing.** The runtime state is not derived from an event log. Events are transient signals, not the source of truth for system state. Memory holds state; events trigger state transitions.

4. **Cross-process event delivery.** Events flow within a single runtime process. There is no network transport, serialization, or inter-process pub/sub. Distributed events are a future concern.

5. **Ordered delivery guarantees.** Events are delivered in publish order within a single subscriber. There is no global ordering guarantee across subscribers. Strict ordering is a future concern.

6. **Exactly-once delivery.** Events may be delivered once or may be dropped under backpressure. There is no acknowledgment protocol or retry mechanism. At-most-once semantics are sufficient for v0.1.

---

## 4. Architecture

```
┌──────────────────────────────────────────────────┐
│                  EventBus                        │
│                                                  │
│  ┌──────────────┐    ┌─────────────────────┐    │
│  │  Publishers   │    │  Subscribers        │    │
│  │  ──────────── │    │  ────────────────    │    │
│  │  Drivers      │───▶│  Memory (update)    │    │
│  │  Scheduler    │    │  Scheduler (tick)   │    │
│  │  Runtime      │    │  Dashboard (stream) │    │
│  │  Memory       │    │  Logger             │    │
│  └──────────────┘    └─────────────────────┘    │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │           Ring Buffer (history)           │   │
│  │  [e0, e1, e2, ..., eN]                  │   │
│  └──────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
```

### Event Lifecycle

1. **Creation.** A subsystem creates an event: `SemanticEvent(type=EventType.DOM_CHANGED, source="chromium", payload={...})`
2. **Publishing.** The subsystem calls `event_bus.publish(event)`.
3. **Filtering.** EventBus iterates active subscriptions, applies filters, determines matching subscribers.
4. **Enqueue.** Matching events are enqueued in each subscriber's async queue.
5. **Delivery.** Subscriber callbacks are invoked via `asyncio.create_task()`. Each subscriber runs independently.
6. **History.** The event is appended to the ring buffer.
7. **Cleanup.** When the ring buffer exceeds capacity, the oldest event is discarded.

### Event Types (v0.1)

| Type | Source | Description |
|---|---|---|
| `DOM_CHANGED` | Driver | DOM structure or attributes changed |
| `PAGE_LOADED` | Driver | Page navigation completed |
| `PAGE_ERROR` | Driver | Page threw an error |
| `USER_INPUT` | Driver | User provided keyboard/mouse input |
| `SCREENSHOT_TAKEN` | Driver | Screenshot captured |
| `ACTION_REQUESTED` | Scheduler | Agent wants to perform an action |
| `ACTION_COMPLETED` | Driver | Action execution finished |
| `ACTION_FAILED` | Driver | Action execution failed |
| `MEMORY_UPDATED` | Memory | Working memory state changed |
| `SCHEDULE_TICK` | Scheduler | Next scheduling tick |
| `HEALTH_CHECK` | Runtime | Driver health check triggered |
| `RUNTIME_STARTED` | Runtime | Runtime initialization complete |
| `RUNTIME_STOPPING` | Runtime | Runtime shutdown initiated |

---

## 5. Interfaces

### SemanticEvent

```python
@dataclass(frozen=True)
class SemanticEvent:
    type: EventType
    source: str
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    metadata: dict[str, Any] = field(default_factory=dict)
```

### EventType

```python
class EventType(str, Enum):
    DOM_CHANGED = "dom_changed"
    PAGE_LOADED = "page_loaded"
    PAGE_ERROR = "page_error"
    USER_INPUT = "user_input"
    SCREENSHOT_TAKEN = "screenshot_taken"
    ACTION_REQUESTED = "action_requested"
    ACTION_COMPLETED = "action_completed"
    ACTION_FAILED = "action_failed"
    MEMORY_UPDATED = "memory_updated"
    SCHEDULE_TICK = "schedule_tick"
    HEALTH_CHECK = "health_check"
    RUNTIME_STARTED = "runtime_started"
    RUNTIME_STOPPING = "runtime_stopping"
```

### EventBus

```python
class EventBus:
    def __init__(self, config: EventBusConfig) -> None: ...

    async def start(self) -> None:
        """Begin accepting publishes and dispatching events."""

    async def stop(self) -> None:
        """Drain pending events and stop dispatching."""

    def publish(self, event: SemanticEvent) -> None:
        """Publish an event. Non-blocking. Never raises."""

    def subscribe(
        self,
        callback: Callable[[SemanticEvent], Awaitable[None]],
        filter: EventFilter | None = None,
    ) -> str:
        """Subscribe to events matching the filter. Returns subscription ID."""

    def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription by ID."""

    def history(self, limit: int = 100) -> list[SemanticEvent]:
        """Return the most recent events from the ring buffer."""

    def stats(self) -> EventBusStats:
        """Return publish count, subscriber count, drop count."""
```

### EventFilter

```python
@dataclass
class EventFilter:
    type: EventType | None = None
    source: str | None = None
    predicate: Callable[[SemanticEvent], bool] | None = None

    def matches(self, event: SemanticEvent) -> bool:
        """Check if an event passes this filter."""
```

### EventBusConfig

```python
@dataclass
class EventBusConfig:
    history_size: int = 1000
    max_queue_size: int = 10000
    dispatch_timeout: float = 1.0
```

### EventBusStats

```python
@dataclass
class EventBusStats:
    published: int
    delivered: int
    dropped: int
    subscribers: int
    history_size: int
```

---

## 6. Acceptance Criteria

1. `EventBus.publish()` adds the event to the ring buffer and enqueues it for all matching subscribers.
2. `EventBus.subscribe()` with `EventFilter(type=EventType.DOM_CHANGED)` only receives DOM_CHANGED events.
3. `EventBus.subscribe()` with `EventFilter(source="chromium")` only receives events from the chromium source.
4. `EventBus.subscribe()` with both type and source filters receives only events matching both criteria.
5. `EventBus.unsubscribe()` removes the subscription — no further events are delivered to that callback.
6. Slow subscribers (awaiting >1s) do not block other subscribers or the publisher.
7. `EventBus.history(50)` returns the 50 most recent events in chronological order.
8. Ring buffer respects `history_size` config — oldest events are evicted when capacity is exceeded.
9. Publishing to a stopped EventBus logs a warning and drops the event.
10. `EventBus.stats()` returns accurate counts of published, delivered, and dropped events.
11. All events carry a unique `event_id` (UUID hex).
12. All events carry a `timestamp` (float, epoch seconds) at creation time.
13. Events are immutable after creation (frozen dataclass).
14. Subscribers receive events asynchronously — the callback is an `async def`.
15. The event system contains no driver-specific, memory-specific, or scheduler-specific logic.

---

## 7. Future Extensions

1. **Event persistence.** Write events to SQLite or Redis for post-mortem analysis. Configurable retention policy.

2. **Event replay.** Replay historical events to new subscribers. Useful for catching up a restarted subsystem or debugging.

3. **Event sourcing.** Derive runtime state from an event log. Enables snapshotting and state reconstruction.

4. **Dead letter queue.** Events that fail delivery (subscriber crashes, timeout) are moved to a dead letter queue for inspection.

5. **Priority events.** Allow events to carry a priority level. High-priority events are delivered before low-priority ones within a subscriber queue.

6. **Event batching.** Allow subscribers to request batched delivery (e.g., "give me events every 100ms" instead of one-by-one). Reduces overhead for high-throughput scenarios.

7. **Cross-process events.** Serialize events and transport them over ZeroMQ, Redis Streams, or NATS for distributed runtimes.

8. **Event ACLs.** Restrict which subsystems can publish certain event types. Prevents accidental misuse.

9. **Custom event types.** Allow drivers to define their own event types beyond the built-in set, with runtime validation.

---

## 8. Open Questions

1. Should `publish()` return a `Future` or stay truly fire-and-forget with logging for dropped events?

2. Should the ring buffer be thread-safe (for potential multi-threaded subscribers) or is asyncio single-thread sufficient?

3. Should event subscriptions support wildcards (e.g., `source="chromium.*"` for all chromium sub-sources)?

4. Should `EventFilter.predicate` be async-capable, or is a sync predicate sufficient given that filtering is fast?

5. Should the EventBus emit a `subscription.dropped` event when a subscriber queue overflows?

6. Should event IDs be UUIDs (globally unique, larger) or sequential integers (compact, process-local)?

7. Should `EventBusStats` be an event emitted periodically, or just a method call?

8. Should events carry a `correlation_id` to link related events across subsystems (e.g., action requested → action completed)?

---

*Document created: 2026-07-26*
*Last updated: 2026-07-26*
