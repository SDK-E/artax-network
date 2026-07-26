# Scheduler Deep Dive

The scheduler controls timing and priority. It determines when the core loop runs, which events get processed first, and when the agent should pause. The scheduler does not make decisions about what to do — that is the agent's job. The scheduler only decides when things happen.

## What the Scheduler Does

The scheduler is the timing authority of the runtime. It answers three questions:

1. **When does the next tick happen?** (tick-based processing)
2. **Which events are processed first?** (priority queuing)
3. **Should the agent pause?** (flow control)

The scheduler does not interpret events. It does not decide what actions mean. It is a timing mechanism, not a decision-making engine.

## Event Scheduling

Events arrive on the bus at arbitrary times. The scheduler determines when they are processed.

### Priority Queue

Events are stored in a priority queue. Higher-priority events are processed before lower-priority ones. Priority is an integer from 0 (lowest) to 9 (highest).

| Priority | Use Case |
|---|---|
| 9 | Critical system events (runtime shutdown, driver crash) |
| 7-8 | High-priority actions (user-initiated clicks, navigation) |
| 5-6 | Normal events (DOM mutations, terminal output) |
| 3-4 | Low-priority observations (background state changes) |
| 0-2 | Informational events (heartbeats, diagnostics) |

### Queue Structure

```
Priority 9: [runtime.shutdown]
Priority 8: [chromium.navigation]
Priority 7: [chromium.dom.click]
Priority 6: [terminal.output]
Priority 5: [chromium.dom.mutation]
Priority 4: [scheduler.tick]
Priority 3: [chromium.heartbeat]
Priority 1: [diagnostics.ping]
```

Events at the same priority level are processed in FIFO order (first in, first out).

### Enqueuing Events

When an event is published to the bus, the scheduler enqueues it:

```python
await scheduler.enqueue(event)
```

The scheduler maintains the priority queue and triggers the core loop when events are available.

## Priorities

### How Priority is Assigned

Priority is set by the event creator (driver, runtime, or agent):

- **Drivers** assign priority based on event importance. A button click is higher priority than a DOM mutation.
- **The runtime** assigns priority to system events. Runtime shutdown is highest priority.
- **The agent** assigns priority to actions. User-initiated actions are higher priority than background tasks.

### Dynamic Priority Adjustment

The scheduler can adjust priorities based on context:

- **Aging:** Events that wait too long get their priority bumped up. This prevents starvation of low-priority events.
- **Deprioritization:** Events from unhealthy drivers can be deprioritized to prevent wasted processing.

### Priority in Working Memory

Priority affects working memory eviction. High-priority events persist longer. When memory is full and a new event arrives, the lowest-priority event is evicted first.

## Pause and Resume

The scheduler supports pausing and resuming the core loop.

### Pausing

The scheduler can pause processing when:

- No events are available (idle wait).
- The agent requests a pause (e.g., waiting for user input).
- A driver is reconnecting (avoid processing stale events).

```python
await scheduler.pause()
```

When paused, the scheduler still receives events and enqueues them. It does not trigger the core loop. Events accumulate in the queue until the scheduler resumes.

### Resuming

The scheduler resumes when:

- New events arrive that require immediate processing.
- The pause condition is resolved (driver reconnected, user input received).
- A timeout expires (forced resume).

```python
await scheduler.resume()
```

When resumed, the scheduler processes all queued events in priority order.

### Pause/Resume in Practice

```
Core loop running
    → No events for 10 seconds
        → Scheduler pauses
            → New event arrives
                → Scheduler resumes
                    → Core loop processes event
```

The agent never notices the pause. It simply stops receiving events until new ones arrive. This is efficient — the runtime does not waste CPU cycles polling empty queues.

## Tick-Based Processing

The scheduler operates on ticks. A tick is one cycle of the core loop:

1. Dequeue the highest-priority event.
2. Update working memory with the event.
3. Let the agent reason over memory.
4. The agent produces an action (or decides to wait).
5. If an action is produced, dispatch it through the event bus.
6. Return to step 1.

### Tick Timing

Ticks are not periodic. They happen as fast as events arrive and the agent can process them. If events arrive faster than the agent can reason, the scheduler queues them and processes them in priority order.

There is no fixed tick rate. The runtime is event-driven, not clock-driven.

### Tick Limits

To prevent infinite loops (an agent that always produces actions without pausing), the scheduler enforces tick limits:

- **Maximum ticks per event batch:** Process at most N ticks before yielding control.
- **Maximum action rate:** Limit how many actions the agent can produce per second.
- **Cool-down period:** After processing a batch of events, the scheduler yields for a brief period before processing the next batch.

These limits are configurable and can be adjusted per deployment.

### Tick Lifecycle

```
┌─────────────────────────────────────────┐
│                Tick                      │
│                                         │
│  1. Dequeue highest-priority event      │
│  2. Store event in working memory       │
│  3. Agent queries memory (attention)    │
│  4. Agent reasons over context          │
│  5. Agent produces action (or waits)    │
│  6. If action: dispatch through bus     │
│  7. Update metrics and diagnostics      │
│                                         │
└─────────────────────────────────────────┘
```

## Flow Control

The scheduler provides flow control mechanisms to prevent the runtime from being overwhelmed.

### Backpressure

When events arrive faster than they can be processed, the scheduler applies backpressure:

- **Queue depth monitoring:** If the queue exceeds a threshold, the scheduler drops low-priority events.
- **Driver throttling:** If a driver produces too many events, the scheduler can request it to slow down.
- **Memory pressure:** If working memory is full, new events must wait until space is available.

### Rate Limiting

The scheduler can rate-limit events by topic:

```python
scheduler.rate_limit(
    topic="chromium.dom.mutation",
    max_events_per_second=10,
)
```

This prevents high-frequency events (like rapid DOM mutations) from flooding the processing pipeline.

### Batching

Events can be batched for efficiency. Instead of processing one event at a time, the scheduler can collect a batch and process them together:

```python
batch = await scheduler.collect_batch(
    max_size=50,
    max_wait=0.1,  # 100ms
)
```

Batching reduces per-event overhead and allows the agent to reason over multiple events at once.

## Scheduler Configuration

| Setting | Default | Description |
|---|---|---|
| `max_queue_size` | 10000 | Maximum events in the priority queue |
| `tick_limit` | 100 | Maximum ticks before yielding |
| `action_rate_limit` | 50 | Maximum actions per second |
| `pause_timeout` | 30.0 | Seconds before forced resume |
| `aging_threshold` | 60.0 | Seconds before priority bump |
| `aging_increment` | 1 | Priority increase per aging cycle |

Configuration is passed to the scheduler at runtime startup:

```python
scheduler = Scheduler(
    max_queue_size=10000,
    tick_limit=100,
    action_rate_limit=50,
)
```

## Scheduler Integration

### With the Event Bus

The scheduler subscribes to all events on the bus and enqueues them. It also publishes scheduler events:

| Event | Description |
|---|---|
| `scheduler.tick` | A tick was processed |
| `scheduler.paused` | Scheduler paused |
| `scheduler.resumed` | Scheduler resumed |
| `scheduler.queue_overflow` | Queue exceeded max size |
| `scheduler.event_dropped` | Low-priority event dropped |

### With Working Memory

The scheduler triggers memory updates on each tick. It coordinates with the memory backend to ensure events are stored before the agent reasons over them.

### With Drivers

The scheduler calls `health_check()` on drivers at configured intervals. It uses health status to adjust priorities and pause actions to unhealthy drivers.

### With the Dashboard

The scheduler publishes tick and queue metrics to the bus. The dashboard subscribes and displays scheduler state in real time.

## Future: Distributed Scheduling

The v0.1 scheduler is single-process. Future versions will support distributed scheduling:

- **Multi-runtime coordination:** Multiple runtime instances share a scheduler.
- **Event partitioning:** Events are partitioned across instances by topic or driver.
- **Consensus:** Runtimes agree on tick timing through a consensus protocol.
- **Failover:** If one runtime instance fails, another takes over its scheduling responsibilities.

This is necessary for large-scale deployments where a single runtime cannot handle the event volume from dozens of drivers simultaneously.
