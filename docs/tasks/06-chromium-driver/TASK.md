# Task 06: Chromium Driver — Gap Analysis

**Layer:** 3 (Chromium Driver)
**Subsystem:** `artax.drivers.chromium`
**Status:** Implemented with gaps
**PRD Reference:** `docs/prd/prd-browser-driver.md`

---

## Senior Product Manager Perspective

### What the Chromium Driver Is Supposed to Do

The Chromium driver is the first supported environment for Artax Network. It wraps Playwright's Chromium browser automation and translates between the browser's raw API and the runtime's semantic event model. It observes DOM mutations, user interactions, and page lifecycle events and emits them as `SemanticEvent` objects. It receives `Action` objects from the scheduler and translates them into Playwright commands.

The driver never exposes Playwright internals to the runtime. The runtime sees only the Driver protocol — connect, disconnect, observe, execute, health_check. Playwright is an implementation detail.

The Chromium driver must:

1. **Manage Chromium lifecycle** — Launch or connect to a Chromium browser instance. Support both launching a new browser and connecting to an existing one (via CDP URL). Browser lifecycle is independent of page lifecycle.

2. **Navigate pages** — Navigate to URLs and emit `PAGE_LOADED` events when navigation completes. Handle navigation errors and timeouts gracefully.

3. **Observe DOM changes** — Monitor the page's DOM for changes using MutationObserver. Emit `DOM_CHANGED` events when elements are added, removed, or modified. MutationObserver is the primary mechanism; polling is a fallback.

4. **Execute actions** — Translate runtime actions into Playwright commands:
   - `click(selector)`: Click an element matching the CSS selector.
   - `type(selector, text)`: Type text into an input element.
   - `navigate(url)`: Navigate to a URL.
   - `screenshot()`: Capture a screenshot of the current page.
   - `evaluate(js)`: Execute JavaScript in the page context and return the result.

5. **Capture screenshots** — Capture full-page or element-specific screenshots. Screenshots are emitted as `SCREENSHOT_TAKEN` events with base64-encoded image data.

6. **Handle errors gracefully** — Playwright errors (element not found, navigation timeout, page crash, browser disconnect) are emitted as `PAGE_ERROR` or `ACTION_FAILED` events.

7. **Health monitoring** — Report health (browser connected, page responsive, last event time) via `health_check()`. The runtime uses this to detect browser crashes or disconnections.

### What Currently Works

The `ChromiumDriver` implementation provides:

- **Full Playwright integration** — Launches Chromium via Playwright, connects to existing browsers via CDP URL, auto-launches system Chrome with remote debugging as a fallback when Playwright cannot install Chromium.

- **Page navigation** — Navigates to URLs with `wait_until="domcontentloaded"` and configurable timeout. Emits `PAGE_LOADED` events on page load.

- **DOM observation via MutationObserver** — Injects a MutationObserver script into every page that watches for childList and attribute changes. The observer tracks mutation counts and sets a flag when significant changes occur.

- **DOM polling fallback** — In addition to MutationObserver, the `observe()` method polls `window.__artax_dom_changed` every 0.5 seconds via `page.evaluate()`. This provides a fallback mechanism if MutationObserver events are missed.

- **Action execution** — Supports `navigate`, `click`, `fill`, `type`, `screenshot`, `evaluate`, `scroll`, and `wait_for` actions. Each action is translated to the corresponding Playwright command with configurable timeouts.

- **Screenshot capture** — Captures screenshots as base64-encoded PNG or JPEG data. Returns the data in `ActionResult`.

- **Error handling** — Handles Playwright errors gracefully: element not found, navigation timeout, page crash, browser disconnect. Errors are emitted as `PAGE_ERROR` or `ACTION_FAILED` events.

- **Health monitoring** — `health_check()` returns `DriverHealth` with current state and error count. Additional convenience methods: `current_url()`, `current_title()`, `page_html()`.

- **CDP support** — Can connect to an existing browser via CDP URL, which is essential for macOS 13+ where Playwright cannot install Chromium.

- **Auto-launch system Chrome** — When Playwright's Chromium launch fails, the driver auto-launches the system Chrome with remote debugging enabled.

### What Is Missing or Different From the Plan

**Gap 1: Polling fallback in observe() deviates from PRD's "MutationObserver only" design**

The PRD specifies that DOM observation should use MutationObserver exclusively — no polling. The implementation includes a `_poll_dom_changes()` fallback that polls `window.__artax_dom_changed` every 0.5 seconds within the `observe()` loop. The PRD says "DOM observation uses MutationObserver, not polling" as acceptance criterion #17. The polling fallback is a deviation from this requirement.

However, the polling fallback serves as a robustness mechanism — if MutationObserver events are missed (e.g., due to page navigation or observer disconnection), the polling ensures DOM changes are still detected. This is a reasonable engineering decision, but it is not aligned with the PRD.

**Gap 2: Extra actions beyond the PRD specification**

The PRD specifies 5 supported actions: `click`, `type`, `navigate`, `screenshot`, `evaluate`. The implementation adds 3 extra actions: `fill`, `scroll`, and `wait_for`. These are reasonable extensions for browser automation, but they are scope creep relative to the PRD's v0.1 action set.

**Gap 3: The PRD says MutationObserver should be injected before PAGE_LOADED, but the implementation injects it after navigation completes**

The PRD acceptance criterion #3 says "MutationObserver before PAGE_LOADED — capture mutations from the start. No missed events during page load." The implementation injects the MutationObserver script after `page.goto()` completes and the page is loaded. This means DOM mutations that occur during the page load itself (before the observer is attached) are not captured.

The implementation does have a `_navigate_and_inject()` method that navigates and injects the observer, but the observer is only active after navigation completes. Mutations during the navigation itself are missed.

**Gap 4: The PRD says DOM change events should be debounced (default 100ms), but the implementation does not implement debouncing**

The PRD acceptance criterion #18 says "DOM change events are debounced (default 100ms) to avoid flooding the EventBus." The implementation does not debounce DOM change events. Every MutationObserver callback or poll result that shows changes immediately emits a `DOM_CHANGED` event.

**Gap 5: The PRD says the driver should support `headless` and `headless=False` for visible windows, and the implementation does support this via `ChromiumConfig.headless`. No gap here.**

**Gap 6: The PRD says the driver should never expose Playwright objects through the Driver protocol. The implementation does not expose Playwright objects through the Driver protocol — it only exposes `current_url()`, `current_title()`, and `page_html()` as convenience methods. These are not Playwright objects. No gap here.**

**Gap 7: The PRD says `execute()` should handle element-not-found gracefully and return `ActionResult(success=False)`. The implementation does this by catching exceptions from Playwright and returning an error result. No gap here.**

**Gap 8: The PRD says `execute()` should handle navigation timeout gracefully and return `ActionResult(success=False)`. The implementation does this by catching `TimeoutError` and returning an error result. No gap here.**

### Acceptance Criteria (What Needs to Pass)

1. connect() launches a Chromium browser (or connects via CDP URL) and creates a page
2. disconnect() closes the browser and releases all Playwright resources
3. observe() yields PAGE_LOADED events when page.goto() completes
4. observe() yields DOM_CHANGED events when the page DOM changes (debounced) — MISSING: no debouncing
5. observe() yields PAGE_ERROR events when the page throws an error
6. observe() yields SCREENSHOT_TAKEN events when a screenshot is captured
7. execute(Action(name="click", target="#btn")) clicks the element and returns success
8. execute(Action(name="type", target="input", parameters={"text": "hello"})) fills the input
9. execute(Action(name="navigate", target="https://example.com")) navigates to the URL
10. execute(Action(name="screenshot")) captures a screenshot and returns base64 data
11. execute(Action(name="evaluate", target="document.title")) returns the page title
12. health_check() returns DriverHealth(state=CONNECTED) when browser is responsive
13. health_check() returns DriverHealth(state=UNHEALTHY) when browser is disconnected
14. connect() handles browser launch failure gracefully and raises DriverError
15. execute() handles element-not-found gracefully and returns ActionResult(success=False)
16. execute() handles navigation timeout gracefully and returns ActionResult(success=False)
17. DOM observation uses MutationObserver, not polling — PARTIALLY: MutationObserver is primary, but polling fallback exists
18. DOM change events are debounced (default 100ms) to avoid flooding the EventBus — MISSING
19. The driver never exposes Playwright objects through the Driver protocol
20. The driver never publishes events directly to subscribers — always through EventBus
21. headless=True launches Chromium without a visible window
22. headless=False launches Chromium with a visible window (for debugging)

---

## Senior Engineer Perspective

### Architecture Assessment

The Chromium driver is well-architected. It wraps Playwright cleanly, translates browser events into semantic events, and translates actions into Playwright commands. The driver follows the `BaseDriver` ABC pattern and implements all required protocol methods.

Key design decisions that were correctly implemented:

- Playwright async API with lazy import (only when connecting)
- CDP support for connecting to existing browsers
- Auto-launch system Chrome as fallback when Playwright cannot install Chromium
- MutationObserver injection for efficient DOM observation
- Action timeout via `asyncio.wait_for()` with configurable timeout
- Base64 encoding for screenshots
- Graceful error handling with `ActionResult(success=False)` for failures
- Event publication through EventBus, not directly to subscribers

### Critical Gaps

1. **Missing debouncing for DOM change events.** The PRD explicitly requires debouncing (default 100ms) to avoid flooding the EventBus. The current implementation emits a `DOM_CHANGED` event for every MutationObserver callback and every poll result without any debouncing. Under heavy DOM mutation (e.g., a SPA with frequent re-renders), this could flood the EventBus with events and degrade performance.

2. **Polling fallback violates PRD's "MutationObserver only" requirement.** The PRD acceptance criterion #17 explicitly states "DOM observation uses MutationObserver, not polling." The polling fallback in `observe()` contradicts this. While the fallback adds robustness, it is not aligned with the PRD.

3. **MutationObserver is injected after page load, not before.** The PRD acceptance criterion #3 says "MutationObserver before PAGE_LOADED — capture mutations from the start." The current implementation injects the observer after `page.goto()` completes, missing mutations during page load.

4. **Extra actions (fill, scroll, wait_for) are scope creep.** The PRD specifies 5 actions. The implementation adds 3 more. While these are useful, they are not part of the v0.1 specification.

### Recommended Actions

1. **Implement debouncing for DOM change events.** Add a debounce mechanism (e.g., `asyncio.sleep(dom_observer_debounce_ms / 1000)`) before emitting `DOM_CHANGED` events. If new mutations occur during the debounce period, reset the timer. This is the highest-priority gap.

2. **Remove the polling fallback** or make it configurable. The PRD explicitly says "not polling." If the fallback is kept, it should be behind a config flag (e.g., `dom_observer_threshold: str = "all" | "significant" | "none"` where `"none"` disables MutationObserver and uses polling only).

3. **Inject MutationObserver before page navigation.** Modify `_navigate_and_inject()` to inject the observer script before calling `page.goto()`, or inject it into the about:blank page first and then navigate. This ensures mutations during page load are captured.

4. **Document the extra actions as v0.1 extensions** or move them to a separate task if they should be part of a different scope.

### Gap Summary

| Gap | Severity | Description |
|-----|----------|-------------|
| Missing DOM change debouncing | HIGH | PRD requires 100ms debounce; implementation emits every mutation |
| Polling fallback violates PRD | MEDIUM | PRD says "not polling"; implementation polls every 0.5s |
| MutationObserver injected after page load | MEDIUM | PRD says observer should be before PAGE_LOADED |
| Extra actions (fill, scroll, wait_for) | LOW | Scope creep beyond PRD's 5 specified actions |
