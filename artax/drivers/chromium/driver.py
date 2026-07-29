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
import time
from collections.abc import AsyncGenerator
from typing import Any

from ...actions.types import Action, ActionResult
from ...drivers.base import BaseDriver, DriverError, DriverHealth
from ...events.types import Event, EventType, SemanticEvent
from .config import ChromiumConfig

logger = logging.getLogger(__name__)

MUTATION_OBSERVER_SCRIPT = """
window.__artax_dom_changes = [];
const observer = new MutationObserver((mutations) => {
    const summary = {added: 0, removed: 0, modified: 0};
    for (const m of mutations) {
        if (m.type === 'childList') {
            summary.added += m.addedNodes.length;
            summary.removed += m.removedNodes.length;
        } else if (m.type === 'attributes') {
            summary.modified += 1;
        }
    }
    if (summary.added + summary.removed + summary.modified > 0) {
        window.__artax_dom_changes.push(summary);
    }
});
observer.observe(document.documentElement, {
    childList: true,
    attributes: true,
    subtree: true,
})
"""

DOM_CLEANUP_SCRIPT = "() => { if (window.__artax_observer) window.__artax_observer.disconnect(); }"

POLL_DOM_SCRIPT = (
    "(() => { const c = window.__artax_dom_changes || []; "
    "window.__artax_dom_changes = []; return c; })()"
)


async def _get_playwright() -> Any:
    """Import and start Playwright.

    Returns:
        A Playwright instance.

    Raises:
        DriverError: If Playwright is not installed.

    """
    try:
        from playwright.async_api import (  # type: ignore[import-not-found]
            async_playwright,
        )
    except ImportError as exc:
        raise DriverError(
            "chromium",
            "Playwright not installed. "
            "Install with: pip install playwright && playwright install chromium",
            recoverable=False,
        ) from exc

    return await async_playwright().start()


class ChromiumDriver(BaseDriver):
    """Chromium browser driver.

    Wraps Playwright's Chromium launcher to provide environment interaction
    for the Artax runtime. Translates between browser DOM events and Artax
    SemanticEvents.

    Attributes:
        config: Configuration for this driver instance.

    """

    def __init__(self, config: ChromiumConfig) -> None:
        """Initialize the Chromium driver.

        Args:
            config: Chromium-specific configuration parameters.

        """
        super().__init__(name="chromium", driver_type="chromium")
        self.config = config
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._event_queue: asyncio.Queue[SemanticEvent] = asyncio.Queue()

    async def _do_connect(self) -> None:
        """Launch or connect to the Chromium browser."""
        self._playwright = await _get_playwright()

        if self.config.cdp_url is not None:
            self._browser = await self._playwright.chromium.connect_over_cdp(
                self.config.cdp_url,
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
        else:
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

        self._page.on("load", self._on_page_loaded)
        self._page.on("pageerror", self._on_page_error)

        await self._page.goto(
            self.config.initial_url,
            wait_until="domcontentloaded",
            timeout=self.config.navigation_timeout_ms,
        )

        await self._page.evaluate(MUTATION_OBSERVER_SCRIPT)
        logger.info("Chromium connected to %s", self.config.initial_url)

    async def _do_disconnect(self) -> None:
        """Close the browser and clean up resources."""
        if self._page is not None:
            try:
                await self._page.evaluate(DOM_CLEANUP_SCRIPT)
            except (RuntimeError, OSError):
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

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except (RuntimeError, OSError):
                pass

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

    def _on_page_loaded(self) -> None:
        """Handle page load event from Playwright."""
        url = ""
        title: str | asyncio.Future[str] = ""
        if self._page is not None:
            try:
                url = self._page.url
            except (AttributeError, RuntimeError):
                pass
            try:
                title = asyncio.ensure_future(self._page.title())
            except (AttributeError, RuntimeError):
                pass

        event = SemanticEvent.create(
            type=EventType.PAGE_LOADED,
            source="chromium",
            payload={"url": url, "title": title},
        )
        self._event_queue.put_nowait(event)

    def _on_page_error(self, error: Any) -> None:
        """Handle page error event from Playwright."""
        event = SemanticEvent.create(
            type=EventType.PAGE_ERROR,
            source="chromium",
            payload={"error": str(error)},
        )
        self._event_queue.put_nowait(event)

    async def observe(self) -> AsyncGenerator[Event, None]:  # type: ignore[override]
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
                    yield SemanticEvent.create(
                        type=EventType.DOM_CHANGED,
                        source="chromium",
                        payload=dom_changes,
                    )

    async def _poll_dom_changes(self) -> dict[str, int] | None:
        """Poll the browser for accumulated DOM mutation summaries."""
        if self._page is None:
            return None
        try:
            changes: list[dict[str, int]] = await self._page.evaluate(
                POLL_DOM_SCRIPT,
            )
            if changes:
                total: dict[str, int] = {
                    "added": 0,
                    "removed": 0,
                    "modified": 0,
                }
                for item in changes:
                    total["added"] += item.get("added", 0)
                    total["removed"] += item.get("removed", 0)
                    total["modified"] += item.get("modified", 0)
                return total
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
            duration_ms = (time.monotonic() - start) * 1000
            return ActionResult(
                action_id=action.action_id,
                success=True,
                data=result_data,
                duration_ms=duration_ms,
            )
        except (RuntimeError, OSError, TimeoutError, ValueError) as exc:
            duration_ms = (time.monotonic() - start) * 1000
            return ActionResult(
                action_id=action.action_id,
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
            )

    async def _execute_action(self, action: Action) -> Any:
        """Dispatch a single action to the appropriate Playwright method."""
        assert self._page is not None
        timeout = self.config.action_timeout_ms

        if action.name == "navigate":
            await self._page.goto(
                action.target or "about:blank",
                wait_until="domcontentloaded",
                timeout=self.config.navigation_timeout_ms,
            )
            return None

        if action.name == "click":
            await self._page.click(action.target or "", timeout=timeout)
            return None

        if action.name == "type":
            text = action.parameters.get("text", "")
            await self._page.fill(
                action.target or "",
                str(text),
                timeout=timeout,
            )
            return None

        if action.name == "screenshot":
            full_page = action.parameters.get("full_page", False)
            screenshot_kwargs: dict[str, Any] = {
                "full_page": full_page,
                "type": self.config.screenshot_format,
                "timeout": 5000,
            }
            raw = await self._page.screenshot(**screenshot_kwargs)
            return base64.b64encode(raw).decode("ascii")

        if action.name == "evaluate":
            return await self._page.evaluate(action.target or "")

        msg = f"Unknown action: {action.name}"
        raise ValueError(msg)

    async def health_check(self) -> DriverHealth:
        """Check browser health."""
        return DriverHealth(
            state=self._state,
            error_count=self._error_count,
            last_event_at=self._last_event_at,
        )


def _has_dom_changes(changes: dict[str, int]) -> bool:
    """Check if DOM changes dict has any non-zero values."""
    return changes.get("added", 0) + changes.get("removed", 0) + changes.get("modified", 0) > 0
