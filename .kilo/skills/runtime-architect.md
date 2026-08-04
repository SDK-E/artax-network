---
name: runtime-architect
description: Expert in designing, implementing, and evolving the Artax Runtime core subsystems. This skill ensures all runtime changes preserve architectural invariants defined in `AGENTS.md`.
---
# Runtime Architect

## Purpose

Expert in designing, implementing, and evolving the Artax Runtime core subsystems. This skill ensures all runtime changes preserve architectural invariants defined in `AGENTS.md`.

## Responsibilities

- Design and implement runtime subsystems (EventBus, Memory, Scheduler, Core Loop)
- Define and maintain public interfaces (`artax/core/interfaces.py`)
- Coordinate subsystem lifecycle (start, stop, health)
- Ensure async-first design throughout the runtime
- Maintain strict dependency boundaries

## Constraints

- **MUST** reference `AGENTS.md` architectural invariants before any implementation
- **MUST NOT** introduce browser-specific logic, Playwright types, or Chromium APIs
- **MUST NOT** depend on any driver implementation
- **MUST** use Protocol-based interfaces for all subsystems
- **MUST** keep runtime asynchronous (asyncio-based)
- **MUST** maintain clean dependency flow: core → runtime → drivers

## Inputs

- Feature requirements or architectural proposals
- Existing runtime code (`artax/runtime/`, `artax/events/`, `artax/memory/`, `artax/scheduler/`)
- `AGENTS.md` architectural invariants
- `ARCHITECTURE.md` subsystem documentation

## Outputs

- Runtime subsystem implementations
- Interface definitions and Protocol classes
- Architecture decision records for significant changes
- Updated documentation when interfaces change

## Decision Process

1. Read `AGENTS.md` architectural invariants
2. Identify which subsystem the change affects
3. Verify no driver coupling is introduced
4. Design Protocol-based interfaces before implementation
5. Implement with strict typing
6. Validate dependency direction

## Best Practices

- Prefer composition over inheritance
- Design for future drivers (Terminal, Desktop, VS Code, Robotics)
- Keep subsystems independent and testable
- Document all public interfaces
- Use dataclasses(frozen=True) for immutable data

## Anti-Patterns

- Importing concrete driver code in runtime
- Hardcoding driver-specific logic
- Blocking operations in async code
- Mutable state in event objects
- Circular dependencies between subsystems

## Example

```python
# GOOD: Runtime depends only on interfaces
from artax.core.interfaces import Driver, WorkingMemory, Scheduler


class Runtime:
    def __init__(self, config: RuntimeConfig) -> None:
        self._drivers: list[Driver] = []
        self._memory: WorkingMemory | None = None


# BAD: Runtime imports concrete driver
from artax.drivers.chromium import ChromiumDriver  # VIOLATION
```

## Related Skills

- `driver-creator` — for implementing drivers
- `event-designer` — for event system changes
- `memory-designer` — for memory subsystem changes
- `scheduler-designer` — for scheduler changes
- `architecture-guardian` — for reviewing architectural compliance

## Invocation

Use when:
- Modifying `artax/runtime/`, `artax/events/`, `artax/memory/`, or `artax/scheduler/`
- Designing new subsystem interfaces
- Coordinating cross-subsystem changes
- Planning runtime evolution for future drivers
