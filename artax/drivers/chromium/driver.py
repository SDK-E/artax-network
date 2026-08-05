"""Chromium browser driver implementation.

Wraps Playwright to provide browser automation capabilities. Observes page
state as Artax events and translates actions (click, type, navigate, etc.)
into Playwright commands.

Playwright is an optional dependency. Import errors are caught and surfaced
as connection errors.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import shutil
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from ...actions.types import Action, ActionResult
from ...drivers.base import BaseDriver, DriverError, DriverHealth
from ...events.bus import EventBus
from ...events.types import Event, EventType, SemanticEvent
from .config import ChromiumConfig

logger = logging.getLogger(__name__)

MUTATION_OBSERVER_SCRIPT = """
window.__artax_dom_changed = false;
window.__artax_dom_mutations = 0;
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
    attributes: true,
});
"""

DOM_CLEANUP_SCRIPT = "() => { if (window.__artax_observer) window.__artax_observer.disconnect(); }"

POLL_DOM_SCRIPT = (
    "(() => { const changed = window.__artax_dom_changed || false; "
    "const mutations = window.__artax_dom_mutations || 0; "
    "window.__artax_dom_changed = false; "
    "window.__artax_dom_mutations = 0; "
    "return {changed, mutations}; })()"
)


async def _get_playwright() -> Any:
    """Import and start Playwright.

    Returns:
        A Playwright instance.

    Raises:
        DriverError: If Playwright is not installed.

    """
    try:
        from playwright.async_api import (
            async_playwright,
        )
    except ImportError as exc:
        raise DriverError(
            "chromium",
            "Playwright not installed. "
            "Install with: pip install playwright && playwright install chromium",
        ) from exc

    return await async_playwright().start()


_CHROME_PATHS: tuple[str, ...] = (
    "Google Chrome",
    "Google Chrome Canary",
    "Chromium",
    "google-chrome",
    "chromium",
)


def _find_chrome() -> str | None:
    """Find a Chrome/Chromium binary on the system.

    Checks common installation paths and the system PATH.

    Returns:
        Path to the Chrome/Chromium binary, or None if not found.

    """
    app_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/opt/homebrew/bin/chromium",
        "/usr/local/bin/chromium",
    ]
    candidates: list[str] = [found for name in _CHROME_PATHS if (found := shutil.which(name))]
    candidates.extend(p for p in app_paths if Path(p).is_file() and os.access(p, os.X_OK))
    env_path = os.environ.get("ARTAX_CHROME_PATH")
    if env_path and Path(env_path).is_file() and os.access(env_path, os.X_OK):
        candidates.insert(0, env_path)

    return candidates[0] if candidates else None


class ChromiumDriver(BaseDriver):
    """Chromium browser driver.

    Wraps Playwright's Chromium launcher to provide environment interaction
    for the Artax runtime. Translates between browser DOM events and Artax
    SemanticEvents.

    Attributes:
        config: Configuration for this driver instance.

    """

    def __init__(
        self,
        config: ChromiumConfig,
        event_bus: EventBus | None = None,
    ) -> None:
        """Initialize the Chromium driver.

        Args:
            config: Chromium-specific configuration parameters.
            event_bus: Event bus to publish action/input events on.
                If None, events are only yielded via ``observe()``.

        """
        super().__init__(name="chromium", config=config)
        self.config = config
        self._event_bus = event_bus
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._event_queue: asyncio.Queue[SemanticEvent] = asyncio.Queue()
        self._launched_chrome_process: asyncio.subprocess.Process | None = None

    async def _do_connect(self) -> None:
        """Launch or connect to the Chromium browser."""
        self._playwright = await _get_playwright()

        if self.config.cdp_url is not None:
            try:
                await self._connect_via_cdp(self.config.cdp_url)
                await self._setup_page()
            except (RuntimeError, OSError, DriverError) as exc:
                logger.warning(
                    "CDP connection to %s failed (%s), attempting to auto-launch Chrome",
                    self.config.cdp_url,
                    exc,
                )
                await self._close_browser()
            else:
                return

        try:
            await self._launch_via_playwright()
            await self._setup_page()
        except (RuntimeError, OSError, DriverError) as exc:
            logger.warning(
                "Playwright Chromium launch failed (%s), attempting to auto-launch system Chrome",
                exc,
            )
            await self._close_browser()
            cdp_url = await self._launch_chrome_cdp()
            await self._connect_via_cdp(cdp_url)
            await self._setup_page()

    async def _launch_chrome_cdp(self) -> str:
        """Launch system Chrome with remote debugging and return the CDP URL.

        Raises:
            DriverError: If Chrome cannot be found or launched.

        """
        chrome_path = self.config.browser_path or _find_chrome()
        if chrome_path is None:
            raise DriverError(
                "chromium",
                "No Chrome/Chromium binary found. "
                "Set browser_path in config or install Chrome. "
                "On macOS 13+, Playwright cannot install Chromium; "
                "the driver will auto-launch system Chrome with CDP.",
            )

        port = self.config.cdp_port
        args = [
            chrome_path,
            f"--remote-debugging-port={port}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            "--no-sandbox",
        ]
        if self.config.headless and "--headless" not in args:
            args.append("--headless=new")
        if self.config.user_data_dir:
            args.append(f"--user-data-dir={self.config.user_data_dir}")

        self._launched_chrome_process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        logger.info(
            "Auto-launched Chrome (pid=%s) on port %d",
            self._launched_chrome_process.pid,
            port,
        )

        cdp_url = f"http://127.0.0.1:{port}"
        for _ in range(50):
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", port),
                    timeout=1.0,
                )
                writer.close()
                await writer.wait_closed()
            except (ConnectionRefusedError, TimeoutError, OSError):
                await asyncio.sleep(0.2)
                continue
            return cdp_url

        raise DriverError(
            "chromium",
            f"Chrome auto-launch failed: CDP port {port} not responding",
        )

    async def _launch_via_playwright(self) -> None:
        """Launch Chromium via Playwright's bundled binary."""
        launch_args = list(self.config.launch_args)
        launch_kwargs: dict[str, Any] = {
            "headless": self.config.headless,
            "args": launch_args,
        }
        if self.config.browser_path is not None:
            launch_kwargs["executable_path"] = self.config.browser_path

        self._browser = await self._playwright.chromium.launch(
            **launch_kwargs,
        )
        self._context = await self._browser.new_context(
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
        )
        self._page = await self._context.new_page()

    async def _connect_via_cdp(self, cdp_url: str) -> None:
        """Connect to an existing browser via CDP URL."""
        self._browser = await self._playwright.chromium.connect_over_cdp(
            cdp_url,
        )
        contexts = self._browser.contexts
        if contexts:
            self._context = contexts[0]
            pages = self._context.pages
            if pages:
                self._page = pages[0]
            else:
                self._page = await self._context.new_page()
        else:
            self._context = await self._browser.new_context(
                viewport={
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                },
            )
            self._page = await self._context.new_page()

    async def _setup_page(self) -> None:
        """Register event handlers and initialize the page."""
        assert self._page is not None
        self._page.on("load", self._on_page_loaded)
        self._page.on("pageerror", self._on_page_error)
        self._page.on("console", self._on_console)
        self._page.on("framenavigated", self._on_frame_navigated)

        await self._navigate_and_inject()
        logger.info("Chromium connected to %s", self.config.initial_url)

    async def _navigate_and_inject(self) -> None:
        """Navigate to initial URL and inject MutationObserver."""
        assert self._page is not None
        try:
            await self._page.goto(
                self.config.initial_url,
                wait_until="domcontentloaded",
                timeout=self.config.navigation_timeout_ms,
            )
            await self._page.evaluate(MUTATION_OBSERVER_SCRIPT)
        except (RuntimeError, OSError):
            logger.warning("Initial navigation or injection failed")

    async def _close_browser(self) -> None:
        """Close browser resources without state management."""
        if self._page is not None:
            try:
                await self._page.evaluate(DOM_CLEANUP_SCRIPT)
            except (RuntimeError, OSError):
                pass
            try:
                await self._page.close()
            except (RuntimeError, OSError, AttributeError):
                pass

        if self._context is not None:
            try:
                await self._context.close()
            except (RuntimeError, OSError):
                pass

        if self._browser is not None:
            try:
                await self._browser.close()
            except (RuntimeError, OSError):
                pass

        self._page = None
        self._context = None
        self._browser = None

    async def _do_disconnect(self) -> None:
        """Close the browser and clean up resources."""
        await self._close_browser()

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except (RuntimeError, OSError):
                pass
            self._playwright = None

        if self._launched_chrome_process is not None:
            try:
                self._launched_chrome_process.terminate()
                await asyncio.wait_for(
                    self._launched_chrome_process.wait(),
                    timeout=5.0,
                )
            except (TimeoutError, ProcessLookupError, OSError):
                try:
                    self._launched_chrome_process.kill()
                except (ProcessLookupError, OSError):
                    pass
            self._launched_chrome_process = None

    async def _publish(self, event: SemanticEvent) -> None:
        """Publish an event to the bus (if available) and internal queue."""
        self._event_queue.put_nowait(event)
        if self._event_bus is not None:
            await self._event_bus.publish(event)

    async def _publish_action_result(
        self,
        action: Action,
        result: ActionResult,
    ) -> None:
        if self._event_bus is None:
            return
        event_type = EventType.ACTION_COMPLETED if result.success else EventType.ACTION_FAILED
        event = SemanticEvent.create(
            type=event_type,
            source="chromium",
            payload={
                "action_name": action.name,
                "action_id": action.action_id,
                "target": action.target,
                "duration_ms": result.duration_ms,
                "error": result.error,
            },
        )
        await self._event_bus.publish(event)

    def _publish_user_event(self, action: Action) -> None:
        if self._event_bus is None:
            return
        if action.name in ("click", "type"):
            event = SemanticEvent.create(
                type=EventType.USER_INPUT,
                source="chromium",
                payload={
                    "action_name": action.name,
                    "action_id": action.action_id,
                    "target": action.target,
                },
            )
            asyncio.ensure_future(self._event_bus.publish(event))
        elif action.name == "screenshot":
            event = SemanticEvent.create(
                type=EventType.SCREENSHOT_TAKEN,
                source="chromium",
                payload={
                    "action_id": action.action_id,
                },
            )
            asyncio.ensure_future(self._event_bus.publish(event))

    def _on_page_loaded(self) -> None:
        """Handle page load event from Playwright."""
        url = ""
        if self._page is not None:
            try:
                url = self._page.url
            except (AttributeError, RuntimeError):
                pass

        event = SemanticEvent.create(
            type=EventType.PAGE_LOADED,
            source="chromium",
            payload={"url": url},
        )
        self._event_queue.put_nowait(event)
        if self._event_bus is not None:
            asyncio.ensure_future(self._event_bus.publish(event))

    def _on_page_error(self, error: Any) -> None:
        """Handle page error event from Playwright."""
        event = SemanticEvent.create(
            type=EventType.PAGE_ERROR,
            source="chromium",
            payload={"error": str(error)},
        )
        self._event_queue.put_nowait(event)
        if self._event_bus is not None:
            asyncio.ensure_future(self._event_bus.publish(event))

    def _on_console(self, msg: Any) -> None:
        """Handle console event from Playwright."""
        event = SemanticEvent.create(
            type=EventType.USER_INPUT,
            source="chromium",
            payload={
                "type": "console",
                "text": str(msg.text) if hasattr(msg, "text") else "",
            },
        )
        self._event_queue.put_nowait(event)
        if self._event_bus is not None:
            asyncio.ensure_future(self._event_bus.publish(event))

    def _on_frame_navigated(self, frame: Any) -> None:
        """Handle frame navigation event from Playwright."""
        event = SemanticEvent.create(
            type=EventType.DOM_CHANGED,
            source="chromium",
            payload={"reason": "framenavigated"},
        )
        self._event_queue.put_nowait(event)
        if self._event_bus is not None:
            asyncio.ensure_future(self._event_bus.publish(event))

    async def observe(self) -> AsyncIterator[Event]:  # type: ignore[override,misc]
        """Yield events from the browser.

        Emits PAGE_LOADED, PAGE_ERROR, DOM_CHANGED events as they occur.
        Yields from an internal queue populated by Playwright event handlers.
        """
        while self._state.value == "connected":
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=0.5,
                )
                yield event
            except TimeoutError:
                dom_changes = await self._poll_dom_changes()
                if dom_changes is not None and _has_dom_changes(dom_changes):
                    event = SemanticEvent.create(
                        type=EventType.DOM_CHANGED,
                        source="chromium",
                        payload=dom_changes,
                    )
                    await self._publish(event)
                    yield event

    async def _poll_dom_changes(self) -> dict[str, int] | None:
        """Poll the browser for accumulated DOM mutation summaries."""
        if self._page is None:
            return None
        try:
            result: dict[str, int] | None = await self._page.evaluate(
                POLL_DOM_SCRIPT,
            )
            if result is None:
                return None
            if result.get("changed"):
                return {
                    "added": result.get("mutations", 0),
                    "removed": 0,
                    "modified": 0,
                }
        except (RuntimeError, OSError):
            pass
        return None

    async def execute(self, action: Action) -> ActionResult:
        """Execute an action against the browser.

        Supported actions: navigate, click, type, screenshot, evaluate.
        """
        start = time.monotonic()
        if self._page is None or self._state.value != "connected":
            return ActionResult(
                action_id=action.action_id,
                success=False,
                error="Driver not connected",
            )

        try:
            result_data = await self._execute_action(action)
        except (RuntimeError, OSError, TimeoutError, ValueError) as exc:
            duration_ms = (time.monotonic() - start) * 1000
            result = ActionResult(
                action_id=action.action_id,
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
            )
            await self._publish_action_result(action, result)
            return result
        else:
            duration_ms = (time.monotonic() - start) * 1000
            result = ActionResult(
                action_id=action.action_id,
                success=True,
                data=result_data,
                duration_ms=duration_ms,
            )
            await self._publish_action_result(action, result)
            self._publish_user_event(action)
            return result

    async def _execute_action(self, action: Action) -> Any:  # noqa: PLR0911
        """Dispatch a single action to the appropriate Playwright method."""
        assert self._page is not None
        action_timeout = self.config.action_timeout_ms / 1000
        pw_timeout = self.config.action_timeout_ms

        if action.name == "navigate":
            await asyncio.wait_for(
                self._page.goto(
                    action.target or "about:blank",
                    wait_until="domcontentloaded",
                    timeout=self.config.navigation_timeout_ms,
                ),
                timeout=action_timeout,
            )
            return None

        if action.name == "click":
            await asyncio.wait_for(
                self._page.click(action.target or "", timeout=pw_timeout),
                timeout=action_timeout,
            )
            return None

        if action.name == "fill":
            value = action.parameters.get("value", "")
            await asyncio.wait_for(
                self._page.fill(
                    action.target or "",
                    str(value),
                    timeout=pw_timeout,
                ),
                timeout=action_timeout,
            )
            return None

        if action.name == "type":
            text = action.parameters.get("text", "")
            await asyncio.wait_for(
                self._page.type(
                    action.target or "",
                    str(text),
                    timeout=pw_timeout,
                ),
                timeout=action_timeout,
            )
            return None

        if action.name == "screenshot":
            full_page = action.parameters.get("full_page", False)
            screenshot_kwargs: dict[str, Any] = {
                "full_page": full_page,
                "type": self.config.screenshot_format,
                "timeout": self.config.screenshot_timeout_ms,
            }
            raw = await asyncio.wait_for(
                self._page.screenshot(**screenshot_kwargs),
                timeout=action_timeout,
            )
            return base64.b64encode(raw).decode("ascii")

        if action.name == "evaluate":
            return await asyncio.wait_for(
                self._page.evaluate(action.target or ""),
                timeout=action_timeout,
            )

        if action.name == "scroll":
            x = action.parameters.get("x", 0)
            y = action.parameters.get("y", 0)
            await asyncio.wait_for(
                self._page.evaluate(
                    f"window.scrollBy({x}, {y})",
                ),
                timeout=action_timeout,
            )
            return None

        if action.name == "wait_for":
            await asyncio.wait_for(
                self._page.wait_for_selector(
                    action.target or "",
                    timeout=pw_timeout,
                ),
                timeout=action_timeout,
            )
            return None

        msg = f"Unknown action: {action.name}"
        raise ValueError(msg)

    async def health_check(self) -> DriverHealth:
        """Check browser health."""
        return DriverHealth(
            state=self._state,
            error_count=self._error_count,
            last_event_at=self._last_event_at,
        )

    async def current_url(self) -> str:
        """Return the current page URL."""
        if self._page is None:
            return ""
        try:
            return str(self._page.url)
        except (AttributeError, RuntimeError):
            return ""

    async def current_title(self) -> str:
        """Return the current page title."""
        if self._page is None:
            return ""
        try:
            return str(await self._page.title())
        except (RuntimeError, OSError):
            return ""

    async def page_html(self) -> str:
        """Return the current page's outer HTML."""
        if self._page is None:
            return ""
        try:
            return str(await self._page.content())
        except (RuntimeError, OSError):
            return ""


def _has_dom_changes(changes: dict[str, int]) -> bool:
    """Check if DOM changes dict has any non-zero values."""
    return changes.get("added", 0) + changes.get("removed", 0) + changes.get("modified", 0) > 0
