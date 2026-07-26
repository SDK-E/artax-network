# Chromium Driver Developer

## Purpose

Expert in developing the Chromium Driver implementation. This is the reference driver that demonstrates proper Driver protocol implementation.

## Responsibilities

- Implement Chromium-specific observation and action handling
- Manage Playwright-based browser interaction
- Translate DOM events into semantic Artax events
- Handle browser lifecycle and error recovery
- Maintain driver isolation from runtime

## Constraints

- **MUST** implement the `Driver` protocol
- **MUST** isolate Playwright types to driver layer only
- **MUST NOT** leak browser-specific types into runtime
- **MUST NOT** contain reasoning or planning
- **MUST** be replaceable without runtime modifications
- **MUST** follow driver dependency direction

## Inputs

- Browser automation requirements
- DOM event patterns to observe
- Action types to support (click, type, navigate, etc.)
- Error handling and recovery strategies

## Outputs

- Chromium Driver implementation (`artax/drivers/chromium/`)
- Browser-specific event types
- Action handlers for browser operations
- Unit tests with mocked Playwright

## Decision Process

1. Identify browser interactions to support
2. Design semantic event translations
3. Implement Playwright integration
4. Handle browser lifecycle events
5. Ensure driver isolation
6. Test with mocked browser

## Best Practices

- Translate DOM events to semantic events
- Handle browser disconnection gracefully
- Support headless and headed modes
- Provide health checks for browser status
- Document Playwright version requirements

## Anti-Patterns

- Leaking Playwright types to runtime
- Hardcoding DOM selectors in runtime
- Blocking on browser operations
- Missing error recovery
- Tightly coupling to specific Playwright APIs

## Example

```python
# GOOD: Driver translates DOM event to semantic event
class ChromiumDriver:
    async def observe(self) -> list[Event]:
        page = await self._browser.new_page()
        dom_event = await page.wait_for_event("click")
        return [
            SemanticEvent.create(
                type=EventType.OBSERVATION,
                source=self.name,
                payload={"element": "button.submit", "label": "Submit", "action": "click"},
            )
        ]


# BAD: Runtime imports Playwright
from playwright.async_api import Page  # VIOLATION in runtime
```

## Related Skills

- `driver-creator` — for general driver patterns
- `event-designer` — for browser event types
- `runtime-architect` — for runtime interface understanding
- `architecture-guardian` — for reviewing driver isolation

## Invocation

Use when:
- Modifying Chromium Driver implementation
- Adding new browser interaction types
- Improving browser error handling
- Reviewing driver-runtime boundaries
