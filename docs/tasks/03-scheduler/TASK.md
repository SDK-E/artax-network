# Task 03: Scheduler — Gap Analysis

**Layer:** 1b (Scheduler)
**Subsystem:** `artax.scheduler`
**Status:** Implemented with gaps
**PRD Reference:** `docs/prd/prd-scheduler.md`

---

## Senior Product Manager Perspective

### What the Scheduler Is Supposed to Do

The scheduler is the runtime's traffic controller. It decides which events are processed now, which are deferred, and in what order. Without a scheduler, all events are processed FIFO — the first event in is the first event out regardless of importance or timing.

The scheduler must:

1. **Priority queuing** — Events can be scheduled with a priority level (urgent, high, medium, low). The scheduler processes urgent events before high, high before medium, medium before low. Within the same priority, events are processed FIFO.

2. **Delayed execution** — Events can be scheduled to be delivered after a specified delay. The scheduler holds the event and delivers it when the delay expires. Delayed events respect priority ordering when multiple events become eligible simultaneously.

3. **Pause/resume** — The scheduler can be paused (stops processing events) and resumed (restarts processing). Paused events queue up and are processed in order when resumed. Useful for debugging and checkpointing.

4. **Tick-based processing** — The scheduler operates on a configurable tick interval (default 10ms). Each tick, it drains all eligible events from the priority queue and dispatches them to the EventBus. Ticks are the scheduler's heartbeat.

5. **Cancel** — Scheduled events can be cancelled by ID before they are delivered. Cancelled events are removed from the queue without delivery.

6. **Event scheduling** — Any subsystem can schedule an event: `scheduler.schedule(event, priority=Priority.HIGH, delay=0.5)`. The scheduler accepts the event and manages its delivery.

7. **Queue visibility** — The scheduler exposes its current queue state: how many events are pending, their priorities, and their scheduled delivery times. Used by the dashboard and for debugging.

8. **Emergency drain on stop** — When the scheduler is stopped, it delivers all pending events (not just urgent ones) before shutting down. Nothing is lost.

### What Currently Works

The `MemoryScheduler` implementation provides:

- Full priority queuing using `heapq` with `(deliver_at, counter, entry_id)` tuples
- Four priority levels: URGENT (0), HIGH (1), MEDIUM (2), LOW (3)
- Delayed execution — events with a `delay` parameter are not delivered until `deliver_at` time
- Pause/resume functionality
- Tick-based processing — `tick()` delivers all matured events in priority order
- Cancel by entry ID — marks entries as CANCELLED and skips them during tick
- Queue size limit with warning log on overflow (returns empty string)
- Emergency drain on stop — delivers all pending events
- Statistics tracking: total scheduled, delivered, cancelled, tick count
- Queue status reporting via `queue_status()` returning `SchedulerStatus`
- Periodic emission of `SCHEDULE_TICK` events after each tick
- Queue depth threshold monitoring — emits `scheduler.queue.depth` event when pending exceeds threshold
- Per-event delivery events — emits `scheduler.event.delivered` for each event delivered

### What Is Missing or Different From the Plan

**Gap 1: Missing `scheduler.event.cancelled` event emission**

The PRD acceptance criterion #12 states: "The scheduler emits `scheduler.event.cancelled` for each event cancelled." The `MemoryScheduler.cancel()` method increments `_total_cancelled` and marks the entry as CANCELLED, but it does **not** publish a cancellation event to the EventBus. This means the dashboard and other subscribers cannot observe when events are cancelled.

**Gap 2: The PRD says `schedule()` returns `str` (entry ID), and the implementation does this correctly. However, the PRD says `schedule()` should return an empty string if the queue is full, and the implementation does this correctly too. No gap here — this is working as specified.**

**Gap 3: The PRD says `stop()` should deliver all URGENT pending events, but the implementation delivers ALL pending events (emergency_drain=True by default). The PRD says "Stop with emergency_drain delivers all" which is what the implementation does. However, the PRD's acceptance criterion #14 says "Stopping the scheduler delivers all URGENT pending events before shutting down." The implementation delivers ALL pending events, which is more than the PRD requires. This is a design decision that exceeds the PRD — it's an improvement, not a gap.**

**Gap 4: The PRD's `Scheduler` protocol shows `schedule()` as `async` but the implementation has it as a regular (non-async) method. The task file specifies `schedule()` as non-async, which matches the implementation. The PRD protocol is slightly different. This is a resolved design decision — the implementation is correct per the task file.**

**Gap 5: The PRD says the scheduler should emit `scheduler.event.cancelled` for each cancelled event. The implementation does not do this.**

### Acceptance Criteria (What Needs to Pass)

1. Schedule event with default priority — delivered before lower priority events
2. Schedule event with specific priority — respects priority ordering
3. Schedule event with delay — not delivered until delay expires
4. Tick delivers ready events — events with deliver_at <= now are delivered
5. Tick skips future events — events with deliver_at > now are not delivered
6. Priority ordering — higher priority delivered first when ready at same time
7. Cancel pending entry returns True
8. Cancel non-existent entry returns False
9. Cancelled entries not delivered on tick
10. Pause stops tick delivery
11. Resume allows tick delivery again
12. Queue full logs warning and returns empty string
13. Stop with emergency_drain delivers all pending events
14. Stop without emergency_drain cancels low priority
15. queue_status returns accurate counts
16. Stats tracking (scheduled, delivered, cancelled counts)
17. Tick count increments
18. Concurrent schedule from multiple coroutines
19. Large number of entries (performance)
20. **scheduler.event.cancelled emitted for each cancelled event (MISSING)**

---

## Senior Engineer Perspective

### Architecture Assessment

The scheduler is well-architected. It uses a heapq-based priority queue with lazy cancellation (marking entries as CANCELLED and skipping them during tick). This is the standard approach for priority queues with cancellation support.

Key design decisions that were correctly implemented:

- `heapq` for priority queue (efficient O(log n) push/pop)
- Lazy cancellation: mark entries as CANCELLED, skip during tick (no heapq removal)
- `time.monotonic()` for all timestamps
- `uuid.uuid4().hex` for entry IDs
- All methods async except `pause()`, `resume()`, `queue_status()`, `pending_count`
- Emergency drain on stop for clean shutdown

### Critical Gap

**Missing cancelled event emission.** When `cancel()` is called, the scheduler should publish a `scheduler.event.cancelled` event to the EventBus so that subscribers (especially the dashboard) can observe cancellations. This is explicitly listed as a PRD acceptance criterion and is currently not implemented.

The fix is straightforward: in `cancel()`, after marking the entry as CANCELLED and incrementing `_total_cancelled`, publish a `SemanticEvent` with type `EventType.CUSTOM` (or a new `SCHEDULE_CANCELLED` event type), source `"scheduler"`, and payload containing the `entry_id`, `priority`, and `event_id` of the cancelled event.

### Gap Summary

| Gap | Severity | Description |
|-----|----------|-------------|
| Missing cancelled event emission | HIGH | `cancel()` does not publish `scheduler.event.cancelled` to EventBus |
| PRD says stop() delivers only URGENT, implementation delivers ALL | LOW | Implementation exceeds PRD — delivers all pending events on stop |
| `schedule()` is sync but PRD protocol says async | LOW | Deliberate design decision per task file; protocol mismatch |

### Recommended Actions

1. **Implement cancelled event emission in `cancel()`.** This is the highest-priority gap. Add a `SemanticEvent.create()` call in `cancel()` after marking the entry as CANCELLED, publishing it to the EventBus if available.

2. **Consider adding a `SCHEDULE_CANCELLED` event type to `EventType`** instead of using `CUSTOM`. This would make cancellation events first-class and filterable.

3. **No action needed for the stop() behaviour** — delivering all pending events on stop is an improvement over the PRD's minimum requirement.
