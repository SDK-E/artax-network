---
name: driver-creator
description: Expert in creating new environment drivers that implement the Driver protocol. Drivers translate between external systems and Artax Events without introducing reasoning or planning.
---
# Driver Creator

## Purpose

Expert in creating new environment drivers that implement the Driver protocol. Drivers translate between external systems and Artax Events without introducing reasoning or planning.

## Responsibilities

- Implement the `Driver` protocol for new environments
- Design environment-specific event types
- Handle driver lifecycle (connect, disconnect, health_check)
- Translate raw observations into semantic events
- Execute actions against the environment

## Constraints

- **MUST** implement the `Driver` protocol from `artax/drivers/base.py`
- **MUST NOT** contain planning, reasoning, or prompts
- **MUST NOT** depend on runtime internals
- **MUST** translate only — no business logic
- **MUST** be self-contained and replaceable
- **MUST** follow dependency direction: drivers → runtime interfaces

## Inputs

- Environment specification (what system to interact with)
- Supported action types for the environment
- Observation formats and patterns
- Connection and authentication requirements

## Outputs

- Driver implementation (`artax/drivers/{name}/`)
- Driver configuration protocol
- Environment-specific event types
- Unit tests that don't require the actual environment

## Decision Process

1. Identify the external system (browser, terminal, API, robot, etc.)
2. Define what observations become semantic events
3. Define what actions the driver supports
4. Implement lifecycle methods (connect, disconnect, health_check)
5. Implement observe() and execute() methods
6. Ensure no runtime dependencies

## Best Practices

- Keep driver logic minimal — translate only
- Use typed events for all observations
- Handle errors gracefully without blocking runtime
- Support graceful disconnection
- Provide health checks for monitoring

## Anti-Patterns

- Adding reasoning or planning to drivers
- Importing runtime internals
- Storing state that belongs in working memory
- Blocking the event loop
- Creating environment-specific logic in runtime

## Example

```python
# GOOD: Driver translates terminal output to semantic events
class TerminalDriver:
    async def observe(self) -> list[Event]:
        raw_output = await self._process.stdout.read()
        return [
            SemanticEvent.create(
                type=EventType.OBSERVATION,
                source=self.name,
                payload={"terminal_output": raw_output},
            )
        ]


# BAD: Driver contains reasoning
class BadDriver:
    async def observe(self) -> list[Event]:
        # VIOLATION: Driver is thinking about what to do
        if self._should_wait():
            return []
        return [self._create_event()]
```

## Related Skills

- `runtime-architect` — for understanding runtime interfaces
- `event-designer` — for designing event types
- `chromium-developer` — for the Chromium Driver reference implementation
- `architecture-guardian` — for reviewing driver compliance

## Invocation

Use when:
- Creating a new driver (Terminal, Desktop, VS Code, Robotics, etc.)
- Modifying existing driver implementations
- Designing environment-specific event types
- Reviewing driver architecture
