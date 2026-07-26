# PRD: Scheduler

**Subsystem:** `artax.scheduler`
**Version:** 0.1
**Status:** Draft

---

## 1. Problem Statement

Events in an embodied AI runtime need to be processed with varying priorities and timing constraints. A high-priority DOM change event from a critical page element should be processed before a low-priority screenshot capture event. An action that must be retried after 2 seconds should not block immediate event processing. Without a scheduler, all events are processed FIFO — the first event in is the first event out regardless of importance or timing.

The scheduler solves this by providing priority queuing, delayed execution, and tick-based processing. It sits between the EventBus and the agent loop, determining which events are processed now, which are deferred, and in what order. The scheduler is the runtime's traffic controller — it decides what goes where and when.

---

## 2. Goals

1. **Priority queuing.** Events can be scheduled with a priority level (urgent, high, medium, low). The scheduler processes urgent events before high, high before medium, medium before low. Within the same priority, events are processed FIFO.

2. **Delayed execution.** Events can be scheduled to be delivered after a specified delay. The scheduler holds the event and delivers it when the delay expires. Delayed events respect priority ordering when multiple events become eligible simultaneously.

3. **Pause/resume.** The scheduler can be paused (stops processing events) and resumed (restarts processing). Paused events queue up and are processed in order when resumed. Useful for debugging and checkpointing.

4. **Tick-based processing.** The scheduler operates on a configurable tick interval (default 10ms). Each tick, it drains all eligible events from the priority queue and dispatches them to the EventBus. Ticks are the scheduler's heartbeat.

5. **Cancel.** Scheduled events can be cancelled by ID before they are delivered. Cancelled events are removed from the queue without delivery.

6. **Event scheduling.** Any subsystem can schedule an event: `scheduler.schedule(event, priority=Priority.HIGH, delay=0.5)`. The scheduler accepts the event and manages its delivery.

7. **Queue visibility.** The scheduler exposes its current queue state: how many events are pending, their priorities, and their scheduled delivery times. Used by the dashboard and for debugging.

---

## 3. Non-Goals

1. **Distributed scheduling.** The scheduler runs within a single runtime process. It does not coordinate schedules across machines. Distributed scheduling is a future concern.

2. **Cron-like recurring tasks.** The scheduler does not support periodic or recurring schedules. Each scheduled event is a one-shot. Recurring tasks are implemented by re-scheduling from event handlers.

3. **Rate limiting.** The scheduler does not enforce rate limits on event delivery. It processes all eligible events every tick. Rate limiting is a v0.2 concern.

4. **Dependency-based scheduling.** Events cannot depend on other events (e.g., "deliver event B only after event A is delivered"). Dependencies are handled by the agent loop.

5. **Persistent schedules.** Scheduled events are in-memory only. A runtime restart loses all pending schedules. Persistence is a v0.2 concern.

6. **Priority inversion prevention.** The scheduler does not detect or prevent priority inversion (low-priority event holding a resource needed by a high-priority event). This is an advanced concern.

---

## 4. Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Scheduler                           │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │           Priority Queue                       │ │
│  │                                                │ │
│  │  Urgent: [event_1, event_2]                   │ │
│  │  High:   [event_3]                            │ │
│  │  Medium: [event_4, event_5, event_6]          │ │
│  │  Low:    [event_7]                            │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │           Tick Loop                            │ │
│  │  every N ms:                                   │ │
│  │    1. check delayed events (ready?)            │ │
│  │    2. move ready events to priority queue      │ │
│  │    3. dequeue highest priority event           │ │
│  │    4. publish to EventBus                      │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │           State                                │ │
│  │  paused: bool                                  │ │
│  │  tick_interval: float                          │ │
│  │  total_scheduled: int                          │ │
│  │  total_delivered: int                          │ │
│  └────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

### ScheduleEntry

```python
@dataclass
class ScheduleEntry:
    entry_id: str
    event: SemanticEvent
    priority: Priority
    scheduled_at: float          # when it was scheduled
    deliver_at: float            # when it should be delivered
    status: ScheduleStatus       # pending, delivered, cancelled
```

### Tick Algorithm

```
on_tick():
    if paused:
        return

    now = current_time()

    # 1. Move delayed events that are ready into priority buckets
    for entry in delayed_queue:
        if entry.deliver_at <= now:
            move entry to priority_queue[entry.priority]

    # 2. Process priority queue (highest priority first)
    for priority in [URGENT, HIGH, MEDIUM, LOW]:
        while priority_queue[priority] is not empty:
            entry = priority_queue[priority].popleft()
            if entry.status == CANCELLED:
                continue
            event_bus.publish(entry.event)
            entry.status = DELIVERED
            total_delivered += 1

    # 3. Log if events were processed
    if total_delivered_this_tick > 0:
        log(f"Tick delivered {total_delivered_this_tick} events")
```

---

## 5. Interfaces

### Scheduler

```python
class Scheduler:
    def __init__(self, config: SchedulerConfig, event_bus: EventBus) -> None: ...

    async def start(self) -> None:
        """Begin the tick loop."""

    async def stop(self) -> None:
        """Stop the tick loop. Deliver any remaining urgent events."""

    def schedule(
        self,
        event: SemanticEvent,
        priority: Priority = Priority.MEDIUM,
        delay: float = 0.0,
    ) -> str:
        """Schedule an event for delivery. Returns entry ID for cancellation."""

    def cancel(self, entry_id: str) -> bool:
        """Cancel a scheduled event. Returns True if found and cancelled."""

    def pause(self) -> None:
        """Pause event processing. Events continue to queue."""

    def resume(self) -> None:
        """Resume event processing from where it was paused."""

    def tick(self) -> None:
        """Process one tick manually. Usually called by the tick loop."""

    def queue_status(self) -> SchedulerStatus:
        """Return current queue state: pending counts, paused status, totals."""

    @property
    def is_paused(self) -> bool:
        """Whether the scheduler is currently paused."""
```

### Priority

```python
class Priority(int, Enum):
    URGENT = 0    # Process immediately, before all others
    HIGH = 1      # Process before medium and low
    MEDIUM = 2    # Default priority
    LOW = 3       # Process last
```

### ScheduleStatus

```python
class ScheduleStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
```

### SchedulerStatus

```python
@dataclass
class SchedulerStatus:
    paused: bool
    pending_urgent: int
    pending_high: int
    pending_medium: int
    pending_low: int
    total_pending: int
    total_scheduled: int
    total_delivered: int
    total_cancelled: int
    tick_count: int
```

### SchedulerConfig

```python
@dataclass
class SchedulerConfig:
    tick_interval_ms: int = 10
    max_queue_size: int = 10000
    emergency_drain: bool = True
```

---

## 6. Acceptance Criteria

1. `scheduler.schedule(event, priority=Priority.URGENT)` delivers the event before any HIGH, MEDIUM, or LOW events.
2. `scheduler.schedule(event, delay=1.0)` delivers the event approximately 1 second after scheduling.
3. `scheduler.cancel(entry_id)` prevents the event from being delivered.
4. `scheduler.pause()` stops event delivery. Events continue to queue.
5. `scheduler.resume()` restarts delivery. Queued events are delivered in priority order.
6. `scheduler.tick()` processes one tick's worth of events without waiting for the next interval.
7. Events within the same priority level are delivered in FIFO order.
8. The scheduler never exceeds `max_queue_size`. Scheduling beyond the limit raises or logs an error.
9. `queue_status()` returns accurate counts for each priority level.
10. The scheduler emits `scheduler.tick` events on the EventBus after each tick (with count of delivered events).
11. The scheduler emits `scheduler.event.delivered` for each event delivered.
12. The scheduler emits `scheduler.event.cancelled` for each event cancelled.
13. Pausing and resuming does not lose any queued events.
14. Stopping the scheduler delivers all URGENT pending events before shutting down.
15. The scheduler contains no driver-specific, memory-specific, or runtime-specific logic.

---

## 7. Future Extensions

1. **Recurring schedules.** Support periodic execution: `scheduler.schedule_repeating(event, interval=5.0, priority=Priority.LOW)`.

2. **Rate limiting.** Enforce maximum delivery rate per event type or priority level. Prevents event floods.

3. **Persistent schedules.** Write pending schedules to SQLite or Redis. Restore on runtime restart.

4. **Dependency chains.** Schedule event B to be delivered only after event A is delivered. Useful for multi-step workflows.

5. **Priority inheritance.** Detect and resolve priority inversion by temporarily boosting low-priority event priority.

6. **Distributed scheduling.** Coordinate schedules across runtime instances via a shared queue (Redis, NATS).

7. **Adaptive tick rate.** Adjust tick interval based on queue depth. Faster ticks when queue is deep; slower when idle.

8. **Schedule analytics.** Track delivery latency, queue depth over time, and priority distribution for dashboard visualization.

9. **Batch delivery.** Deliver multiple events in a single dispatch to reduce overhead for high-throughput scenarios.

---

## 8. Open Questions

1. Should `schedule()` raise an exception when the queue is full, or log a warning and drop the event?

2. Should `tick()` be called by the runtime's event loop, or does the scheduler manage its own `asyncio.Task`?

3. Should `stop()` deliver all pending events (including LOW) or only URGENT and HIGH?

4. Should delayed events respect priority when becoming ready, or use a separate "ready" queue with FIFO order?

5. Should the scheduler emit a `scheduler.queue.depth` event when queue exceeds a threshold?

6. Should `tick_interval_ms` be configurable at runtime, or fixed at startup?

7. Should the scheduler support cooperative cancellation (asyncio.CancelledEvent) for long-running event handlers?

8. Should `queue_status()` be a method or an event emitted periodically?

---

*Document created: 2026-07-26*
*Last updated: 2026-07-26*
