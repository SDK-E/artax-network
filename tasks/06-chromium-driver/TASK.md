# Task 06: Implement Chromium Driver

## Objective

Implement the Chromium browser driver for Artax Network. This is the first supported environment — wraps Playwright to drive a Chromium browser and translate browser events into semantic events that the runtime understands.

## Reference Documents

- **PRD**: `docs/prd/prd-browser-driver.md` — all resolved design decisions
- **Existing scaffolding**: `artax/drivers/chromium/driver.py`, `artax/drivers/chromium/config.py`
- **Depends on**: Task 04 (Driver API, Actions) — must be implemented first
- **Driver model**: `docs/driver-model.md`
- **Future drivers**: `docs/future-drivers.md`

## Resolved Design Decisions

1. **Playwright events directly** — real-time, event-driven, no polling
2. **Base64 in ActionResult** for screenshots — simple, self-contained
3. **MutationObserver before PAGE_LOADED** — capture mutations from the start
4. **Driver default timeout** — configurable via ChromiumConfig
5. **Chromium only for now** — Chrome path configurable for future
6. **`headless=True` default** — production-safe by default
7. **Configurable mutation threshold** — balance noise vs completeness
8. **Multi-selector fallback chain** — more resilient selectors

## Current State

Existing scaffolding is a stub. Key gaps:

- `ChromiumConfig` missing most PRD fields (cdp_url, navigation_timeout_ms, action_timeout_ms, etc.)
- `ChromiumDriver` is completely empty
- No Playwright integration
- No event translation layer
- No action translation layer
- No MutationObserver injection
- No DOM debouncing

## Implementation Steps

### Step 1: Reconcile `artax/drivers/chromium/config.py`

```python
@dataclass(frozen=True)
class ChromiumConfig:
    # Connection
    headless: bool = True
    browser_path: str | None = None
    cdp_url: str | None = None  # connect to existing browser

    # Viewport
    viewport_width: int = 1280
    viewport_height: int = 720

    # Timeouts (ms)
    navigation_timeout_ms: int = 30000
    action_timeout_ms: int = 10000
    screenshot_timeout_ms: int = 5000

    # DOM observation
    dom_observer_debounce_ms: int = 100
    dom_observer_threshold: str = "significant"  # "all" | "significant" | "none"

    # Launch
    user_data_dir: str | None = None
    launch_args: tuple[str, ...] = ()
    initial_url: str = "about:blank"

    # Screenshot
    screenshot_format: str = "png"  # "png" | "jpeg"
    screenshot_quality: int = 80  # for jpeg

    @property
    def driver_type(self) -> str:
        return "chromium"
```

### Step 2: Implement `ChromiumDriver`

Full implementation wrapping Playwright:

```python
class ChromiumDriver(BaseDriver):
    def __init__(self, name: str, config: ChromiumConfig) -> None:
        super().__init__(name, config)
        self._browser = None  # Playwright Browser
        self._page = None     # Playwright Page
        self._context = None  # Playwright BrowserContext

    async def _do_connect(self) -> None:
        # 1. Import playwright async API
        # 2. Launch browser or connect to CDP
        # 3. Create browser context with viewport
        # 4. Create new page
        # 5. Inject MutationObserver script
        # 6. Navigate to initial_url
        ...

    async def _do_disconnect(self) -> None:
        # 1. Close page
        # 2. Close context
        # 3. Close browser (if we launched it)
        ...

    async def observe(self) -> AsyncIterator[Event]:
        # Yield events from Playwright event listeners:
        # - page.on("load") → PAGE_LOADED
        # - page.on("pageerror") → PAGE_ERROR
        # - page.on("console") → USER_INPUT (if console.log)
        # - page.on("framenavigated") → DOM_CHANGED
        # - MutationObserver callback → DOM_CHANGED (debounced)
        # - Custom action result events
        ...

    async def execute(self, action: Action) -> ActionResult:
        # Match action.name to Playwright command:
        # "navigate" → page.goto(action.target)
        # "click" → page.click(action.target)
        # "fill" → page.fill(action.target, action.parameters["value"])
        # "type" → page.type(action.target, action.parameters["text"])
        # "screenshot" → page.screenshot() → base64
        # "scroll" → page.evaluate("window.scrollBy(...)")
        # "wait_for" → page.wait_for_selector(action.target)
        # "evaluate" → page.evaluate(action.parameters["script"])
        ...

    async def health_check(self) -> DriverHealth:
        # Check page is not closed
        # Check browser is connected
        # Return DriverHealth with state
        ...

    async def current_url(self) -> str: ...
    async def current_title(self) -> str: ...
    async def page_html(self) -> str: ...
```

### Step 3: MutationObserver Injection

Inject JavaScript into every page to observe DOM mutations:

```javascript
// Injected before PAGE_LOADED
const observer = new MutationObserver((mutations) => {
    const significant = mutations.filter(m =>
        m.type === 'childList' && m.addedNodes.length > 0 ||
        m.type === 'attributes'
    );
    if (significant.length > 0) {
        window.__artax_dom_changed = true;
        window.__artax_dom_mutations = significant.length;
    }
});
observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true
});
```

The driver polls `window.__artax_dom_changed` periodically (debounced) and emits DOM_CHANGED events.

### Step 4: Write tests

Create `tests/chromium/test_chromium_config.py`:
- Test ChromiumConfig defaults
- Test driver_type property
- Test frozen dataclass

Create `tests/chromium/test_chromium_driver.py`:
- Test driver instantiation
- Test name and environment properties
- Test initial state is DISCONNECTED
- Test health_check when disconnected returns DISCONNECTED state
- Mock Playwright for connect/disconnect tests
- Mock Playwright for execute tests (click, fill, screenshot)
- Mock Playwright for observe tests (event emission)
- Test action name mapping (navigate, click, fill, type, screenshot, scroll, wait_for, evaluate)
- Test unknown action name returns error
- Test screenshot returns base64 data
- Test timeout handling
- Test error handling (element not found, navigation timeout)
- Test MutationObserver injection script

## Technical Constraints

- Playwright async API (`playwright.async_api`)
- `import playwright.async_api as pw` — lazy import (only when connecting)
- Base64 encoding for screenshots: `base64.b64encode(bytes).decode()`
- Debouncing via `asyncio.sleep(config.dom_observer_debounce_ms / 1000)`
- Action timeout: `asyncio.wait_for(coro, timeout=config.action_timeout_ms / 1000)`
- Strict typing for `mypy --strict`
- Playwright is an optional dependency (in `[chromium]` extra)

## Quality Gates

```bash
python3 -m py_compile artax/drivers/chromium/config.py
python3 -m py_compile artax/drivers/chromium/driver.py
python3 -c "from artax.drivers.chromium.driver import ChromiumDriver; print('OK')"
pytest tests/chromium/ -v
```

**Note**: Playwright tests may need mocking since Chromium is not available in CI. Use `unittest.mock.AsyncMock` for Playwright objects.

## Files

| Action | File |
|--------|------|
| MODIFY | `artax/drivers/chromium/config.py` |
| MODIFY | `artax/drivers/chromium/driver.py` |
| CREATE | `tests/chromium/__init__.py` |
| CREATE | `tests/chromium/test_chromium_config.py` |
| CREATE | `tests/chromium/test_chromium_driver.py` |
