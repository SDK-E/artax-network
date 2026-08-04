---
name: scheduler-designer
description: Expert in designing scheduler policies and priority management. The Scheduler controls when cognition executes, like an operating system interrupt scheduler.
---
# Scheduler Designer

## Purpose

Expert in designing scheduler policies and priority management. The Scheduler controls when cognition executes, like an operating system interrupt scheduler.

## Responsibilities

- Design scheduling policies (priority, timing, throttling)
- Implement the `Scheduler` protocol
- Manage event dispatch timing
- Handle high-frequency event streams
- Design pause/resume capabilities

## Constraints

- **MUST** implement the `Scheduler` protocol from `artax/scheduler/core.py`
- **MUST** decide WHEN things happen, not WHAT to do
- **MUST** support priority-based dispatch
- **MUST** support delayed scheduling
- **MUST** support pause/resume
- **MUST NOT** make decisions about what actions to take
- **MUST NOT** contain business logic or reasoning

## Inputs

- Timing requirements (tick frequency, delays)
- Priority levels and dispatch order
- Throttling and debouncing needs
- Performance requirements

## Outputs

- Scheduler implementations
- Priority policy designs
- Throttling/debouncing configurations
- Performance benchmarks

## Decision Process

1. Identify timing requirements
2. Design priority levels and dispatch order
3. Implement Scheduler protocol
4. Add throttling/debouncing if needed
5. Test with unit tests (no environment required)
6. Document timing guarantees

## Best Practices

- Keep scheduler logic minimal
- Support priority inversion prevention
- Design for high-frequency event streams
- Provide clear pause/resume semantics
- Document timing guarantees

## Anti-Patterns

- Adding business logic to scheduler
- Making decisions about what actions to take
- Blocking the event loop
- Unbounded priority queues
- Missing pause/resume support

## Example

```python
# GOOD: Scheduler dispatches events in priority order
await scheduler.schedule(event=high_priority_event, delay=timedelta(seconds=0))

# GOOD: Throttled dispatch for high-frequency events
await scheduler.schedule(event=dom_change_event, delay=timedelta(milliseconds=100))


# BAD: Scheduler decides what to do
class BadScheduler:
    async def tick(self):
        # VIOLATION: Scheduler is reasoning
        if self._should_prioritize():
            self._adjust_priorities()
```

## Related Skills

- `runtime-architect` — for scheduler subsystem integration
- `event-designer` — for event prioritization
- `architecture-guardian` — for reviewing scheduler design
- `testing-architect` — for scheduler testing

## Invocation

Use when:
- Implementing new scheduler policies
- Modifying priority or timing logic
- Designing throttling/debouncing
- Reviewing scheduler behavior
