# Task 01: Event System — Gap Analysis

**Layer:** 0 (Foundation)
**Subsystem:** `artax.events`
**Status:** Implemented with gaps
**PRD Reference:** `docs/prd/prd-events.md`

---

## Senior Product Manager Perspective

### What the Event System Is Supposed to Do

The event system is the nervous system of Artax. Every subsystem — drivers, memory, scheduler, dashboard — communicates exclusively through typed, async events published to a central EventBus. Nothing bypasses it. The event system must:

1. **Create and publish events** — Any subsystem can create a typed event with a source, payload, and optional correlation ID, then publish it to the bus. Publishing is fire-and-forget: the publisher does not block waiting for subscribers to process the event.

2. **Subscribe and filter** — Any subsystem can subscribe to events by type, source pattern (wildcards like `chromium.*`), or custom async predicate. Multiple subscribers can listen to the same event independently. Filters combine with AND semantics.

3. **Maintain event history** — A bounded ring buffer (default 1000 events) retains the most recent events for the dashboard and debugging. Oldest events are evicted when capacity is exceeded.

4. **Deliver events asynchronously** — Each subscriber gets its own asyncio queue. Events are dispatched to subscribers without blocking the publisher or other subscribers. Slow subscribers do not affect fast ones.

5. **Track statistics** — The bus tracks published count, delivered count, dropped count (due to queue overflow), active subscription count, and current queue depth.

6. **Handle backpressure gracefully** — When a subscriber's queue is full, the event is dropped, a `subscription.dropped` event is emitted, and the publisher continues without error.

7. **Support lifecycle management** — The bus can be started and stopped cleanly. When stopped, publishing is rejected and a warning is logged.

### What Currently Works

All of the above is implemented and working. The `MemoryEventBus` provides:

- Full publish-subscribe with `EventFilter` supporting type, source (wildcard), predicate, after timestamp, and limit filters
- Per-subscription asyncio queues with configurable max size
- Ring buffer history with configurable size
- Statistics tracking (published, delivered, dropped, active subscriptions, queue depth)
- Periodic stats emission on the event bus (every 5 seconds)
- Graceful start/stop lifecycle
- `correlation_id` support on events for tracing related events across subsystems
- `drain()` method that waits for all queued events to be delivered
- `unsubscribe()` that cancels consumer tasks and removes subscriptions

### What Is Missing or Different From the Plan

**None significant.** The event system is the most complete subsystem and aligns closely with the PRD. The implementation actually exceeds the PRD in several areas (correlation_id, limit in EventFilter, wildcard source matching, subscription.dropped events, periodic stats emitter) — all of which were explicitly resolved design decisions in the PRD.

### Acceptance Criteria (All Pass)

- Publish adds events to the ring buffer and enqueues them for matching subscribers
- Wildcard subscription (`source="chromium.*"`) works correctly
- Async predicate filters work
- Queue overflow emits `subscription.dropped` events
- Ring buffer respects `history_size` config
- Stats accuracy
- Drain delivers all queued events
- Start/stop lifecycle works
- Concurrent publish from multiple coroutines works
- Unsubscribe stops delivery

---

## Senior Engineer Perspective

### Architecture Assessment

The event system is well-architected. The `EventBus` Protocol defines the interface that all implementations must satisfy, allowing for future Redis-backed or distributed implementations. The `MemoryEventBus` is a production-quality in-memory implementation.

Key design decisions that were correctly implemented per PRD resolved decisions:

- `publish()` returns a `Future` — caller decides whether to await
- Thread-safe ring buffer using `collections.deque` with `asyncio.Lock`
- Wildcard subscription support via `fnmatch.fnmatch()`
- Async-capable filter predicates
- `subscription.dropped` event emission on queue overflow
- UUID4 event IDs for global uniqueness
- Periodic `EventBusStats` events emitted on the bus
- Events carry `correlation_id` for cross-subsystem tracing

### Potential Concerns

1. **Stats emitter task lifecycle** — The `_stats_emitter` task is created in `start()` and cancelled in `stop()`. If `start()` is called twice without `stop()`, a second stats task will be created, leading to duplicate stat events. The implementation does not guard against double-start.

2. **`_matched_count` in `EventFilter`** — The limit counter is mutable state on a frozen dataclass, managed via `object.__setattr__`. This works but is fragile — if `EventFilter` is ever used in a concurrent context (shared between coroutines), the counter could race. Currently each subscription gets its own filter copy, so this is safe.

3. **Drop event recursion risk** — When a subscriber queue overflows, a `subscription.dropped` event is published via `asyncio.create_task(self.publish(drop_event))`. If the bus is already under heavy load and many subscriptions are full, this could create a cascade of drop events. In practice this is unlikely because drop events go to a separate "event_bus" source and are unlikely to trigger further drops.

4. **No event persistence** — Per PRD non-goals, events are not persisted. This is correct for v0.1 but will be a gap when event replay or sourcing is needed in v0.2.

### Gap Summary

| Gap | Severity | Description |
|-----|----------|-------------|
| Double-start protection | LOW | No guard against calling `start()` twice; creates duplicate stats task |
| Event persistence | PLANNED | Not implemented — per PRD non-goals for v0.1 |
| Event replay | PLANNED | Not implemented — per PRD non-goals for v0.1 |

### Recommended Actions

1. Add a guard in `start()` that raises `RuntimeError` if the bus is already running, or is a no-op if already started.
2. Document the double-start behaviour clearly so downstream consumers don't accidentally trigger it.
3. No immediate action needed for the PRD gaps — event persistence and replay are v0.2 concerns.

---

## Gap Detail: Event System

### Current Behaviour

- Events are created as `SemanticEvent` dataclasses with `event_id` (UUID4), `type` (EventType enum), `source` (string), `timestamp` (epoch float), `payload` (dict), `metadata` (dict), and `correlation_id` (UUID or None).
- The `MemoryEventBus` stores events in a `collections.deque` ring buffer and dispatches them to per-subscription asyncio queues.
- Subscribers receive events asynchronously via async callbacks. Each subscriber has its own queue with configurable max size.
- When a subscriber's queue is full, the event is dropped and a `subscription.dropped` event is emitted.
- The bus emits periodic `HEALTH_CHECK` events with statistics every 5 seconds.
- Filtering supports type matching, source wildcard matching (fnmatch), async predicates, timestamp filtering, and result limits.

### Missing Behaviour

- **Double-start protection**: Calling `start()` twice creates a second stats emitter task, causing duplicate stat events. No error or warning is raised.

### Expected Behaviour

- Calling `start()` on an already-running bus should either raise a `RuntimeError` or be a silent no-op. The PRD does not specify which, but the former is safer for debugging.
- All other PRD acceptance criteria are met.

### Priority

Low — the event system is functionally complete. The double-start edge case is unlikely in production and easy to work around.
