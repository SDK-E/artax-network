# Event Designer

## Purpose

Expert in designing typed events for the Artax event bus. Events are the universal communication mechanism between all subsystems.

## Responsibilities

- Design event type taxonomies
- Define event payloads and metadata
- Create event filters and subscriptions
- Ensure event immutability and thread safety
- Document event semantics and usage

## Constraints

- **MUST** use `EventType` enum for all events
- **MUST** use `SemanticEvent` dataclass(frozen=True)
- **MUST** include id, type, source, timestamp, payload, metadata
- **MUST** keep events immutable after creation
- **MUST NOT** include mutable state in event payloads
- **MUST** design for all future drivers, not just Chromium

## Inputs

- System behavior to model
- Existing event types in `artax/events/types.py`
- Subsystem communication requirements
- Performance and memory constraints

## Outputs

- New event type definitions
- Event filter specifications
- Event documentation
- Usage examples

## Decision Process

1. Identify what behavior needs to be modeled
2. Determine event category (OBSERVATION, ACTION_REQUEST, etc.)
3. Design payload structure
4. Define metadata requirements
5. Create filter criteria
6. Document semantics

## Best Practices

- Use semantic naming (ButtonClicked, not DomEvent)
- Keep payloads focused and minimal
- Design for filtering and subscription
- Include trace IDs in metadata
- Version events when breaking changes are needed

## Anti-Patterns

- Mutable event payloads
- Raw HTML or DOM data in events
- Events that imply driver-specific behavior
- Missing timestamps or source information
- Overly complex event hierarchies

## Example

```python
# GOOD: Semantic event with focused payload
SemanticEvent.create(
    type=EventType.OBSERVATION,
    source="chromium",
    payload={
        "element": "button.submit",
        "label": "Submit Form",
        "visible": True
    }
)

# BAD: Raw DOM data
SemanticEvent.create(
    type=EventType.OBSERVATION,
    source="chromium",
    payload={
        "html": "<button class='submit'>Submit Form</button>",
        "xpath": "/html/body/div/form/button"
    }
)
```

## Related Skills

- `runtime-architect` — for event bus implementation
- `driver-creator` — for driver-specific events
- `memory-designer` — for event storage and retrieval
- `architecture-guardian` — for reviewing event design

## Invocation

Use when:
- Designing new event types
- Modifying event payloads or metadata
- Creating event filters or subscriptions
- Reviewing event usage patterns
