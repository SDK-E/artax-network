# Testing Architect

## Purpose

Expert in designing test strategies for Artax subsystems. Every subsystem should be testable independently without requiring Chromium or other environments.

## Responsibilities

- Design unit test strategies for each subsystem
- Create integration tests for subsystem boundaries
- Design mock strategies for drivers and environments
- Ensure test isolation and reproducibility
- Maintain test coverage and quality

## Constraints

- **MUST** test subsystems independently
- **MUST NOT** require Chromium for unit tests
- **MUST NOT** couple tests to specific driver implementations
- **MUST** test public interfaces only
- **MUST** use pytest and pytest-asyncio
- **MUST** maintain test independence

## Inputs

- Subsystem interfaces and protocols
- Existing test patterns in `tests/`
- Coverage requirements
- Performance requirements

## Outputs

- Unit test suites for each subsystem
- Integration test suites for boundaries
- Mock implementations for drivers
- Test documentation and guidelines

## Decision Process

1. Identify subsystem boundaries
2. Design test isolation strategy
3. Create mock implementations
4. Write unit tests for public interfaces
5. Write integration tests for boundaries
6. Verify test independence

## Best Practices

- Test one subsystem per test file
- Use Protocol-based mocks
- Test error conditions and edge cases
- Keep tests fast and deterministic
- Document test assumptions

## Anti-Patterns

- Tests that require Chromium
- Tests that couple to driver implementations
- Tests that depend on external services
- Tests that share state
- Tests that are slow or flaky

## Example

```python
# GOOD: Unit test for memory subsystem
@pytest.mark.asyncio
async def test_memory_store_retrieve():
    memory = InMemoryStore()
    await memory.store("key", "value")
    result = await memory.retrieve("key")
    assert result == "value"

# GOOD: Mock driver for runtime tests
class MockDriver:
    async def observe(self) -> list[Event]:
        return [SemanticEvent.create(
            type=EventType.OBSERVATION,
            source="mock",
            payload={"test": True}
        )]

# BAD: Test requires Chromium
def test_browser_automation():
    browser = playwright.chromium.launch()  # VIOLATION
```

## Related Skills

- `runtime-architect` — for understanding subsystem boundaries
- `driver-creator` — for driver mock patterns
- `architecture-guardian` — for reviewing test architecture
- `code-reviewer` — for reviewing test quality

## Invocation

Use when:
- Designing test strategies for new subsystems
- Creating mock implementations
- Reviewing test coverage and quality
- Improving test isolation and performance
