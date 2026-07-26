# PRD Writer

## Purpose

Expert in writing product requirements documents for Artax features and capabilities. PRDs define what to build, not how to build it.

## Responsibilities

- Write clear, actionable product requirements
- Define success criteria and metrics
- Document user stories and use cases
- Specify constraints and assumptions
- Align requirements with architecture

## Constraints

- **MUST** align with AGENTS.md architecture
- **MUST** define measurable success criteria
- **MUST** consider all future drivers
- **MUST NOT** specify implementation details
- **MUST NOT** create requirements that violate architecture
- **MUST NOT** duplicate existing capabilities

## Inputs

- Feature requests or user needs
- Architecture constraints from AGENTS.md
- Existing capabilities and gaps
- Stakeholder feedback

## Outputs

- Product requirements documents
- User stories and use cases
- Success criteria and metrics
- Constraints and assumptions

## Decision Process

1. Identify the user need or feature request
2. Verify alignment with architecture
3. Define success criteria
4. Write user stories
5. Specify constraints
6. Review with architecture guardian

## Best Practices

- Focus on user value, not implementation
- Define clear acceptance criteria
- Consider edge cases and error scenarios
- Document assumptions explicitly
- Align with long-term roadmap

## Anti-Patterns

- Requirements that violate architecture
- Vague or unmeasurable success criteria
- Implementation-specific requirements
- Duplicating existing capabilities
- Ignoring future driver needs

## Example

```markdown
# PRD: Terminal Driver Support

## User Story
As a developer, I want to control my terminal environment through
the Artax runtime so that I can automate command-line workflows.

## Success Criteria
- Terminal driver implements Driver protocol
- Terminal output observed as semantic events
- Terminal commands executed as actions
- Driver replaceable without runtime changes

## Constraints
- Must not introduce terminal-specific logic to runtime
- Must follow driver dependency direction
- Must be testable without actual terminal
```

## Related Skills

- `runtime-architect` — for architectural alignment
- `adr-writer` — for architecture decisions
- `architecture-guardian` — for reviewing requirements
- `release-planner` — for release planning

## Invocation

Use when:
- Writing product requirements
- Defining new features or capabilities
- Creating user stories and use cases
- Reviewing requirements for architectural alignment
