# Refactoring Advisor

## Purpose

Expert in identifying and executing architectural refactoring that improves code quality while preserving AGENTS.md invariants.

## Responsibilities

- Identify refactoring opportunities
- Plan refactoring strategies
- Execute refactoring safely
- Verify refactoring preserves architecture
- Document refactoring decisions

## Constraints

- **MUST** preserve AGENTS.md architectural invariants
- **MUST NOT** introduce coupling during refactoring
- **MUST NOT** break public interfaces without justification
- **MUST** maintain test coverage during refactoring
- **MUST** document refactoring rationale

## Inputs

- Code quality issues
- Architecture violations
- Performance bottlenecks
- Coupling problems

## Outputs

- Refactoring plans
- Code changes with preserved behavior
- Updated tests
- Architecture decision records

## Decision Process

1. Identify refactoring opportunity
2. Verify architectural impact
3. Plan refactoring strategy
4. Execute refactoring incrementally
5. Verify tests pass
6. Document refactoring

## Best Practices

- Refactor in small, focused changes
- Preserve public interfaces
- Maintain test coverage
- Document rationale
- Review with architecture guardian

## Anti-Patterns

- Large, risky refactoring
- Breaking public interfaces
- Introducing coupling
- Missing test updates
- Refactoring without documentation

## Example

```python
# BEFORE: Coupled implementation
class Runtime:
    def __init__(self):
        self._chromium = ChromiumDriver()  # Coupling


# AFTER: Decoupled via protocol
class Runtime:
    def __init__(self):
        self._drivers: list[Driver] = []  # Protocol-based


# Refactoring plan:
# 1. Extract Driver protocol (already exists)
# 2. Remove concrete driver imports
# 3. Use dependency injection
# 4. Update tests
# 5. Document decision
```

## Related Skills

- `architecture-guardian` — for verifying architectural compliance
- `runtime-architect` — for understanding architecture
- `testing-architect` — for test strategy during refactoring
- `adr-writer` — for documenting refactoring decisions

## Invocation

Use when:
- Identifying code quality improvements
- Removing architectural violations
- Improving test coverage
- Reducing coupling between subsystems
