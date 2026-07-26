# Architecture Guardian

## Purpose

**MANDATORY** skill that reviews every proposed implementation against the constitutional rules in `AGENTS.md`. This skill prevents architectural violations before they occur.

## Responsibilities

- Review all implementations against AGENTS.md invariants
- Detect Runtime ↔ Driver coupling
- Prevent environment-specific leakage
- Ensure interface stability
- Recommend architectural improvements

## Constraints

- **MUST** be invoked before any implementation begins
- **MUST** reference all 10 architectural invariants
- **MUST** provide specific violation examples
- **MUST** recommend architectural improvements
- **MUST NOT** approve code that violates invariants
- **MUST NOT** allow shortcuts that increase coupling

## Inputs

- Proposed implementation plans
- Code changes and pull requests
- Architecture documents
- AGENTS.md invariants

## Outputs

- Architecture compliance reports
- Violation detection and warnings
- Improvement recommendations
- Approval or rejection decisions

## Detection Rules

### Runtime ↔ Driver Coupling
- Runtime imports driver code
- Runtime contains driver-specific logic
- Runtime depends on driver implementations

### Environment-Specific Leakage
- Browser assumptions in runtime
- Playwright types in runtime
- Chromium APIs in runtime
- Terminal-specific logic in runtime

### Interface Instability
- Breaking changes to public interfaces
- Missing backward compatibility
- Designing for one driver instead of all

### Dependency Direction Violations
- Drivers depending on runtime internals
- Runtime depending on drivers
- Circular dependencies between subsystems

### Semantic Memory Violations
- Storing raw HTML in working memory
- Storing DOM data in runtime state
- Missing semantic abstraction

### Scheduler Responsibility Creep
- Scheduler making decisions about actions
- Scheduler containing business logic
- Scheduler influencing runtime decisions

### Dashboard Influence
- Dashboard blocking runtime
- Dashboard making runtime decisions
- Dashboard importing runtime internals

## Decision Process

1. Read AGENTS.md architectural invariants
2. Identify which subsystems are affected
3. Check for coupling violations
4. Verify interface stability
5. Check dependency direction
6. Provide specific recommendations
7. Approve or reject implementation

## Best Practices

- Review before implementation begins
- Provide specific violation examples
- Recommend architectural improvements
- Document decisions in ADRs
- Track violation patterns over time

## Anti-Patterns

- Approving code that violates invariants
- Missing coupling violations
- Not checking for future driver impact
- Approving shortcuts that increase coupling
- Ignoring semantic memory violations

## Example

```python
# ARCHITECTURE GUARDIAN: VIOLATION DETECTED

## Violation: Runtime ↔ Driver Coupling
File: artax/runtime/core.py:15
```python
from artax.drivers.chromium import ChromiumDriver  # VIOLATION
```

## Recommendation
Remove driver import. Use Driver protocol instead:
```python
from artax.drivers.base import Driver  # CORRECT
```

## Impact
This change would prevent adding future drivers without
modifying runtime code.
```

## Related Skills

- `runtime-architect` — for understanding architecture
- `code-reviewer` — for code review integration
- `adr-writer` — for documenting decisions
- `refactoring-advisor` — for fixing violations

## Invocation

**MANDATORY** - Use when:
- Starting any implementation task
- Reviewing pull requests
- Planning architectural changes
- Before merging any code changes

This skill MUST be invoked before implementation begins. No exceptions.
