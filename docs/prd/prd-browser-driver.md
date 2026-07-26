# PRD: Chromium Driver

**Subsystem:** `artax.drivers.chromium`
**Version:** 0.1
**Status:** Draft

---

## 1. Problem Statement

The first supported environment for Artax Network is the Chromium web browser. AI agents need to interact with web pages — navigate to URLs, observe DOM changes, click elements, type text, take screenshots. Without a Chromium driver, the runtime has no way to perceive or act in the web environment.

The Chromium driver wraps Playwright's Chromium browser automation and translates between the browser's raw API and the runtime's semantic event model. It observes DOM mutations, user interactions, and page lifecycle events and emits them as `SemanticEvent` objects. It receives `Action` objects from the scheduler and translates them into Playwright commands (click, type, navigate, screenshot).

The driver never exposes Playwright internals to the runtime. The runtime sees only the Driver protocol — connect, disconnect, observe, execute, health_check. Playwright is an implementation detail.

---

## 2. Goals

1. **Chromium lifecycle.** The driver manages a Chromium browser instance: launch, connect, and close. It supports both launching a new browser and connecting to an existing one (via CDP URL). Browser lifecycle is independent of page lifecycle.

2. **Page navigation.** The driver navigates to URLs and emits `PAGE_LOADED` events when navigation completes. It supports both initial navigation and subsequent navigations. It handles navigation errors and timeouts.

3. **DOM observation.** The driver monitors the page's DOM for changes. It emits `DOM_CHANGED` events when elements are added, removed, or modified. Observation uses MutationObserver for efficient, event-driven detection rather than polling.

4. **Action execution.** The driver executes actions dispatched by the runtime:
   - `click(selector)`: Click an element matching the CSS selector.
   - `type(selector, text)`: Type text into an input element.
   - `navigate(url)`: Navigate to a URL.
   - `screenshot()`: Capture a screenshot of the current page.
   - `evaluate(js)`: Execute JavaScript in the page context and return the result.

5. **Screenshot capture.** The driver captures full-page or element-specific screenshots. Screenshots are emitted as `SCREENSHOT_TAKEN` events with base64-encoded image data.

6. **Error handling.** The driver handles Playwright errors gracefully: element not found, navigation timeout, page crash, browser disconnect. Errors are emitted as `PAGE_ERROR` or `ACTION_FAILED` events.

7. **Health monitoring.** The driver reports its health (browser connected, page responsive, last event time) via the `health_check()` method. The runtime uses this to detect browser crashes or disconnections.

---

## 3. Non-Goals

1. **Multi-tab management.** v0.1 supports a single active page. Multi-tab and multi-frame support is v0.2.

2. **Network interception.** The driver does not intercept, modify, or mock network requests. Network control is a v0.2 concern.

3. **File downloads.** The driver does not handle file downloads or upload dialogs. File handling is a future concern.

4. **Authentication handling.** The driver does not manage login flows, cookies, or session persistence. Authentication is application-level.

5. **Mobile emulation.** The driver runs Chromium in desktop mode. Device emulation is a future concern.

6. **PDF generation.** The driver does not export pages as PDF. This is a future concern.

7. **Performance profiling.** The driver does not collect performance metrics (LCP, FID, CLS). Profiling is a future concern.

---

## 4. Architecture

```
┌──────────────────────────────────────────────────────┐
│              Chromium Driver                         │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │  Playwright API                                │ │
│  │  - browser.launch() / browser.connect()        │ │
│  │  - page.goto()                                 │ │
│  │  - page.click()                                │ │
│  │  - page.fill()                                 │ │
│  │  - page.screenshot()                           │ │
│  │  - page.evaluate()                             │ │
│  │  - page.on("click", callback)                  │ │
│  └────────────────────┬───────────────────────────┘ │
│                       │                              │
│  ┌────────────────────┴───────────────────────────┐ │
│  │  Translation Layer                             │ │
│  │  - Playwright events → SemanticEvents          │ │
│  │  - Actions → Playwright commands               │ │
│  │  - Page state → Memory entries                 │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │  MutationObserver (in-page)                    │ │
│  │  - Watches DOM changes                        │ │
│  │  - Sends change summaries to driver           │ │
│  └────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

### Event Translation

| Playwright Event                          | SemanticEvent Type | Payload                                                 |
|-------------------------------------------|--------------------|---------------------------------------------------------|
| `page.load`                               | `PAGE_LOADED`      | `{url, title, load_time_ms}`                            |
| `page.error`                              | `PAGE_ERROR`       | `{message, stack, url}`                                 |
| `page.click` (injected observer)          | `USER_INPUT`       | `{type: "click", selector, x, y}`                       |
| `page.keyboard.press` (injected observer) | `USER_INPUT`       | `{type: "keypress", key, code}`                         |
| `MutationObserver` callback               | `DOM_CHANGED`      | `{summary, added_count, removed_count, modified_count}` |
| Screenshot complete                       | `SCREENSHOT_TAKEN` | `{image_base64, width, height, format}`                 |
| Action success                            | `ACTION_COMPLETED` | `{action_id, result, duration_ms}`                      |
| Action failure                            | `ACTION_FAILED`    | `{action_id, error, duration_ms}`                       |

### Action Translation

| Action Name  | Playwright Command                         | Notes                                           |
|--------------|--------------------------------------------|-------------------------------------------------|
| `click`      | `page.click(selector, timeout=5000)`       | Waits for element, clicks, returns after action |
| `type`       | `page.fill(selector, text)`                | Clears input first, then fills                  |
| `navigate`   | `page.goto(url, wait_until="networkidle")` | Waits for network idle                          |
| `screenshot` | `page.screenshot(full_page=True)`          | Returns base64 PNG                              |
| `evaluate`   | `page.evaluate(js_expression)`             | Returns evaluated result                        |

### MutationObserver Injection

On page load, the driver injects a JavaScript MutationObserver into the page:

```javascript
const observer = new MutationObserver((mutations) => {
    const summary = {
        added: mutations.filter(m => m.type === 'childList').reduce((c, m) => c + m.addedNodes.length, 0),
        removed: mutations.filter(m => m.type === 'childList').reduce((c, m) => c + m.removedNodes.length, 0),
        modified: mutations.filter(m => m.type === 'attributes' || m.type === 'characterData').length
    };
    window.__artax_dom_changed(summary);
});
observer.observe(document.body, {
    childList: true,
    attributes: true,
    characterData: true,
    subtree: true
});
```

The driver registers a handler for `__artax_dom_changed` that translates the summary into a `DOM_CHANGED` SemanticEvent and publishes it to the EventBus.

### Configuration

```python
@dataclass
class ChromiumConfig(DriverConfig):
    driver_type: str = "chromium"
    headless: bool = True
    cdp_url: str | None = None  # Connect to existing browser via CDP
    launch_args: list[str] = field(default_factory=lambda: ["--no-sandbox"])
    viewport_width: int = 1280
    viewport_height: int = 720
    navigation_timeout_ms: int = 30000
    action_timeout_ms: int = 10000
    screenshot_format: str = "png"
    dom_observer_debounce_ms: int = 100
    initial_url: str | None = None  # Navigate to this URL on connect
```

---

## 5. Interfaces

### ChromiumDriver

```python
class ChromiumDriver:
    def __init__(self, name: str, config: ChromiumConfig, event_bus: EventBus) -> None: ...

    @property
    def name(self) -> str: ...

    @property
    def state(self) -> DriverState: ...

    async def connect(self) -> None:
        """Launch or connect to Chromium. Navigate to initial_url if configured."""

    async def disconnect(self) -> None:
        """Close the browser. Clean up Playwright resources."""

    async def observe(self) -> AsyncIterator[SemanticEvent]:
        """Yield semantic events from the browser. Runs continuously while connected."""

    async def execute(self, action: Action) -> ActionResult:
        """Execute a browser action. Returns result or error."""

    async def health_check(self) -> DriverHealth:
        """Check browser connection and page responsiveness."""

    def config(self) -> ChromiumConfig: ...

    async def current_url(self) -> str:
        """Return the current page URL."""

    async def current_title(self) -> str:
        """Return the current page title."""

    async def page_html(self) -> str:
        """Return the current page's outer HTML."""
```

### Supported Actions

```python
# Click an element
Action(name="click", target="#submit-button")

# Type text into an input
Action(name="type", target="input[name=email]", parameters={"text": "user@example.com"})

# Navigate to a URL
Action(name="navigate", target="https://example.com")

# Take a screenshot
Action(name="screenshot", parameters={"full_page": True})

# Execute JavaScript
Action(name="evaluate", target="document.title")
```

### Driver Protocol Compliance

`ChromiumDriver` implements the `Driver` protocol defined in `prd-driver-api.md`. It satisfies:
- `name` → configured driver name
- `state` → current `DriverState`
- `connect()` → launches/connects to Chromium
- `disconnect()` → closes browser
- `observe()` → yields browser events as SemanticEvents
- `execute(action)` → translates and executes via Playwright
- `health_check()` → checks browser and page status

---

## 6. Acceptance Criteria

1. `connect()` launches a Chromium browser (or connects via CDP URL) and creates a page.
2. `disconnect()` closes the browser and releases all Playwright resources.
3. `observe()` yields `PAGE_LOADED` events when `page.goto()` completes.
4. `observe()` yields `DOM_CHANGED` events when the page DOM changes (debounced).
5. `observe()` yields `PAGE_ERROR` events when the page throws an error.
6. `observe()` yields `SCREENSHOT_TAKEN` events when a screenshot is captured.
7. `execute(Action(name="click", target="#btn"))` clicks the element and returns success.
8. `execute(Action(name="type", target="input", parameters={"text": "hello"}))` fills the input.
9. `execute(Action(name="navigate", target="https://example.com"))` navigates to the URL.
10. `execute(Action(name="screenshot"))` captures a screenshot and returns base64 data.
11. `execute(Action(name="evaluate", target="document.title"))` returns the page title.
12. `health_check()` returns `DriverHealth(state=CONNECTED)` when browser is responsive.
13. `health_check()` returns `DriverHealth(state=UNHEALTHY)` when browser is disconnected.
14. `connect()` handles browser launch failure gracefully and raises `DriverError`.
15. `execute()` handles element-not-found gracefully and returns `ActionResult(success=False)`.
16. `execute()` handles navigation timeout gracefully and returns `ActionResult(success=False)`.
17. DOM observation uses MutationObserver, not polling.
18. DOM change events are debounced (default 100ms) to avoid flooding the EventBus.
19. The driver never exposes Playwright objects through the Driver protocol.
20. The driver never publishes events directly to subscribers — always through EventBus.
21. `headless=True` launches Chromium without a visible window.
22. `headless=False` launches Chromium with a visible window (for debugging).

---

## 7. Future Extensions

1. **Multi-tab management.** Support multiple open pages. Route actions to specific tabs. Emit tab lifecycle events.

2. **Network interception.** Intercept and modify network requests. Mock API responses. Block requests.

3. **File downloads.** Handle download dialogs. Save files to configurable directory.

4. **Cookie management.** Persist and restore cookies across sessions. Support cookie-based authentication.

5. **Performance metrics.** Collect Core Web Vitals (LCP, FID, CLS) and emit performance events.

6. **Accessibility tree.** Extract the page's accessibility tree and emit it as a structured event. Useful for screen-reader-like AI interaction.

7. **Element highlighting.** Visually highlight elements before clicking or typing (for debugging).

8. **Action replay.** Record a sequence of actions and replay them. Useful for testing and demonstrations.

9. **Browser profiles.** Support Chromium profiles with persistent state (cookies, localStorage, cache).

10. **Element selection strategies.** Support CSS selectors, XPath, text content, and role-based element selection.

11. **iFrame support.** Observe and interact with elements inside iFrames.

12. **Shadow DOM support.** Observe and interact with elements inside Shadow DOM boundaries.

---

## 8. Resolved Decisions

| # | Question                                       | Decision                       | Rationale                                                                             |
|---|------------------------------------------------|--------------------------------|---------------------------------------------------------------------------------------|
| 1 | `observe()` uses Playwright events or polling? | **Playwright events directly** | Real-time, event-driven. Consistent with Artax event philosophy. No polling overhead. |
| 2 | `screenshot()` returns base64 or memory key?   | **Base64 in ActionResult**     | Simple, self-contained. Memory handles persistence. No indirection.                   |
| 3 | MutationObserver before or after PAGE_LOADED?  | **Before PAGE_LOADED**         | Capture mutations from the start. No missed events during page load.                  |
| 4 | `evaluate()` has timeout?                      | **Driver default timeout**     | Safety net with configurable default via `ChromiumConfig`. Prevents hung scripts.     |
| 5 | Support Chrome as alternative?                 | **Chromium only for now**      | Simpler. Chrome path configurable via `ChromiumConfig` for future extension.          |
| 6 | `headless` default?                            | **`headless=True` default**    | Production-safe by default. Override for development via config.                      |
| 7 | DOM mutation scope?                            | **Configurable threshold**     | Balance between noise and completeness. Developer controls granularity.               |
| 8 | Multiple CSS selectors per action?             | **Yes, fallback chain**        | More resilient selectors. Common pattern in test frameworks.                          |

---

*Document created: 2026-07-26*
*Last updated: 2026-07-26*
