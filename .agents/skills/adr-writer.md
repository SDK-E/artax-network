# ADR Writer

## Purpose

Expert in writing architecture decision records (ADRs) that document significant architectural decisions and their rationale.

## Responsibilities

- Document architectural decisions with context and rationale
- Record trade-offs and alternatives considered
- Maintain decision history and evolution
- Ensure decisions align with AGENTS.md invariants
- Provide reference for future contributors

## Constraints

- **MUST** reference AGENTS.md architectural invariants
- **MUST** document context, decision, and consequences
- **MUST** consider impact on future drivers
- **MUST NOT** document trivial decisions
- **MUST NOT** contradict architectural invariants
- **MUST NOT** create decisions that increase coupling

## Inputs

- Architectural changes or proposals
- Trade-offs and alternatives considered
- Impact analysis on subsystems
- Stakeholder feedback

## Outputs

- Architecture decision records
- Decision history and timeline
- Impact analysis documentation
- Reference for future decisions

## Decision Process

1. Identify the architectural decision
2. Document context and problem
3. List alternatives considered
4. Record the decision and rationale
5. Document consequences and trade-offs
6. Review with architecture guardian

## Best Practices

- Write ADRs before implementation
- Include diagrams when helpful
- Document rejected alternatives
- Link to related ADRs
- Review ADRs in code reviews

## Anti-Patterns

- ADRs that contradict AGENTS.md
- Missing rationale for decisions
- Not documenting alternatives
- ADRs that become stale
- Documenting trivial decisions

## Example

```markdown
# ADR-001: Event Bus Implementation

## Status
Accepted

## Context
Artax needs a typed, async event bus for subsystem communication.
The bus must support pub/sub patterns and topic-based routing.

## Decision
Implement custom event bus over asyncio.Queue with typed events.

## Alternatives Considered
1. Use existing library (e.g., aio-pika) — Rejected: adds dependency
2. Use in-memory dict — Rejected: no async support

## Consequences
+ Full control over event types and routing
+ No external dependencies
- Must maintain custom implementation
```

## Related Skills

- `runtime-architect` — for architectural context
- `architecture-guardian` — for reviewing decisions
- `doc-writer` — for documenting decisions
- `release-planner` — for decision timeline

## Invocation

Use when:
- Making significant architectural decisions
- Documenting trade-offs and alternatives
- Reviewing architectural history
- Planning architectural evolution
