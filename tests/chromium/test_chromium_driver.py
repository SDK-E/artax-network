"""Tests for ChromiumDriver.

All Playwright interactions are mocked. Tests verify the driver translates
between Playwright APIs and Artax's event/action model correctly.
"""

from __future__ import annotations

import asyncio
import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from artax.actions.types import Action, ActionResult
from artax.drivers.base import DriverError, DriverState
from artax.drivers.chromium.config import ChromiumConfig
from artax.drivers.chromium.driver import MUTATION_OBSERVER_SCRIPT, ChromiumDriver
from artax.events.bus import MemoryEventBus
from artax.events.types import EventType, SemanticEvent


def _make_mock_page() -> AsyncMock:
    """Create a mock Playwright Page."""
    page = AsyncMock()
    page.url = "about:blank"
    page.title = AsyncMock(return_value="Test Page")
    page.content = AsyncMock(return_value="<html><body></body></html>")
    page.evaluate = AsyncMock(return_value=None)
    page.goto = AsyncMock()
    page.click = AsyncMock()
    page.fill = AsyncMock()
    page.type = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n fake_png_data")
    page.wait_for_selector = AsyncMock()
    page.on = MagicMock()
    return page


def _make_mock_browser() -> AsyncMock:
    """Create a mock Playwright Browser."""
    browser = AsyncMock()
    browser.close = AsyncMock()
    return browser


def _make_mock_context() -> AsyncMock:
    """Create a mock Playwright BrowserContext."""
    context = AsyncMock()
    context.new_page = AsyncMock()
    context.close = AsyncMock()
    return context


def _make_mock_playwright() -> MagicMock:
    """Create a mock Playwright instance."""
    pw = MagicMock()
    pw.chromium = AsyncMock()
    pw.chromium.launch = AsyncMock()
    pw.chromium.connect_over_cdp = AsyncMock()
    return pw


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


class TestChromiumDriverInstantiation:
    def test_creates_with_config(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        assert driver.name == "chromium"
        assert driver.environment == "chromium"

    def test_initial_state_disconnected(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        assert driver.state == DriverState.DISCONNECTED

    def test_config_accessible(self) -> None:
        config = ChromiumConfig(headless=False)
        driver = ChromiumDriver(config)
        assert driver.config.headless is False


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------


class TestChromiumDriverHealth:
    async def test_health_when_disconnected(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        health = await driver.health_check()
        assert health.state == DriverState.DISCONNECTED
        assert health.error_count == 0

    async def test_health_when_connected(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._browser = _make_mock_browser()
        driver._page = _make_mock_page()
        health = await driver.health_check()
        assert health.state == DriverState.CONNECTED


# ---------------------------------------------------------------------------
# Connect / Disconnect
# ---------------------------------------------------------------------------


class TestChromiumDriverConnect:
    async def test_connect_launches_browser(self) -> None:
        config = ChromiumConfig(headless=True)
        driver = ChromiumDriver(config)

        mock_pw = _make_mock_playwright()
        mock_browser = _make_mock_browser()
        mock_context = _make_mock_context()
        mock_page = _make_mock_page()

        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch("artax.drivers.chromium.driver._get_playwright", return_value=mock_pw):
            await driver.connect(MemoryEventBus())

        assert driver.state == DriverState.CONNECTED
        mock_pw.chromium.launch.assert_called_once()

    async def test_connect_with_cdp_url(self) -> None:
        config = ChromiumConfig(cdp_url="http://localhost:9222")
        driver = ChromiumDriver(config)

        mock_pw = _make_mock_playwright()
        mock_browser = _make_mock_browser()
        mock_context = _make_mock_context()
        mock_page = _make_mock_page()

        mock_pw.chromium.connect_over_cdp.return_value = mock_browser
        mock_browser.contexts = [mock_context]
        mock_context.pages = [mock_page]

        with patch("artax.drivers.chromium.driver._get_playwright", return_value=mock_pw):
            await driver.connect(MemoryEventBus())

        assert driver.state == DriverState.CONNECTED
        mock_pw.chromium.connect_over_cdp.assert_called_once_with("http://localhost:9222")

    async def test_connect_navigates_to_initial_url(self) -> None:
        config = ChromiumConfig(initial_url="https://example.com")
        driver = ChromiumDriver(config)

        mock_pw = _make_mock_playwright()
        mock_browser = _make_mock_browser()
        mock_context = _make_mock_context()
        mock_page = _make_mock_page()

        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch("artax.drivers.chromium.driver._get_playwright", return_value=mock_pw):
            await driver.connect(MemoryEventBus())

        mock_page.goto.assert_called_once_with(
            "https://example.com",
            wait_until="domcontentloaded",
            timeout=30000,
        )

    async def test_connect_injects_mutation_observer(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)

        mock_pw = _make_mock_playwright()
        mock_browser = _make_mock_browser()
        mock_context = _make_mock_context()
        mock_page = _make_mock_page()

        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch("artax.drivers.chromium.driver._get_playwright", return_value=mock_pw):
            await driver.connect(MemoryEventBus())

        # Should have called page.evaluate to inject MutationObserver
        calls = mock_page.evaluate.call_args_list
        inject_calls = [c for c in calls if "MutationObserver" in str(c)]
        assert len(inject_calls) > 0

    async def test_connect_failure_sets_error_state(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)

        mock_pw = _make_mock_playwright()
        mock_pw.chromium.launch.side_effect = RuntimeError("Browser not found")

        with (
            patch("artax.drivers.chromium.driver._get_playwright", return_value=mock_pw),
            patch("artax.drivers.chromium.driver._find_chrome", return_value=None),
            pytest.raises(DriverError),
        ):
            await driver.connect(MemoryEventBus())

        assert driver.state == DriverState.ERROR
        assert driver.error_count == 1


class TestChromiumDriverDisconnect:
    async def test_disconnect_closes_browser(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)

        # Simulate connected state
        driver._state = DriverState.CONNECTED
        driver._browser = _make_mock_browser()
        driver._page = _make_mock_page()
        driver._context = _make_mock_context()

        await driver.disconnect()
        assert driver.state == DriverState.DISCONNECTED

    async def test_disconnect_when_already_disconnected(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        assert driver.state == DriverState.DISCONNECTED
        # Should not raise
        await driver.disconnect()
        assert driver.state == DriverState.DISCONNECTED


# ---------------------------------------------------------------------------
# Execute Actions
# ---------------------------------------------------------------------------


class TestChromiumDriverExecute:
    def _connected_driver(self) -> ChromiumDriver:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()
        driver._browser = _make_mock_browser()
        return driver

    async def test_navigate_action(self) -> None:
        driver = self._connected_driver()
        action = Action(name="navigate", target="https://example.com")
        result = await driver.execute(action)
        assert result.success is True
        driver._page.goto.assert_called_once_with(
            "https://example.com",
            wait_until="domcontentloaded",
            timeout=30000,
        )

    async def test_click_action(self) -> None:
        driver = self._connected_driver()
        action = Action(name="click", target="#submit")
        result = await driver.execute(action)
        assert result.success is True
        driver._page.click.assert_called_once_with("#submit", timeout=10000)

    async def test_type_action(self) -> None:
        driver = self._connected_driver()
        action = Action(
            name="type",
            target="input[name=email]",
            parameters={"text": "user@example.com"},
        )
        result = await driver.execute(action)
        assert result.success is True
        driver._page.type.assert_called_once_with(
            "input[name=email]", "user@example.com", timeout=10000
        )

    async def test_screenshot_action(self) -> None:
        driver = self._connected_driver()
        action = Action(name="screenshot")
        result = await driver.execute(action)
        assert result.success is True
        assert result.data is not None
        # Should be base64 encoded
        decoded = base64.b64decode(result.data)
        assert b"fake_png_data" in decoded

    async def test_screenshot_full_page(self) -> None:
        driver = self._connected_driver()
        action = Action(name="screenshot", parameters={"full_page": True})
        result = await driver.execute(action)
        assert result.success is True
        driver._page.screenshot.assert_called_once_with(full_page=True, type="png", timeout=5000)

    async def test_evaluate_action(self) -> None:
        driver = self._connected_driver()
        driver._page.evaluate = AsyncMock(return_value="Test Page")
        action = Action(name="evaluate", target="document.title")
        result = await driver.execute(action)
        assert result.success is True
        assert result.data == "Test Page"

    async def test_unknown_action_returns_error(self) -> None:
        driver = self._connected_driver()
        action = Action(name="nonexistent_action")
        result = await driver.execute(action)
        assert result.success is False
        assert result.error is not None

    async def test_execute_when_not_connected(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        action = Action(name="click", target="#btn")
        result = await driver.execute(action)
        assert result.success is False

    async def test_click_element_not_found(self) -> None:
        driver = self._connected_driver()
        driver._page.click.side_effect = RuntimeError("Element not found")
        action = Action(name="click", target="#missing")
        result = await driver.execute(action)
        assert result.success is False
        assert "Element not found" in (result.error or "")

    async def test_navigate_timeout(self) -> None:
        driver = self._connected_driver()
        driver._page.goto.side_effect = TimeoutError("Navigation timed out")
        action = Action(name="navigate", target="https://slow.example.com")
        result = await driver.execute(action)
        assert result.success is False


# ---------------------------------------------------------------------------
# Observe Events
# ---------------------------------------------------------------------------


class TestChromiumDriverObserve:
    async def test_observe_yields_page_loaded(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()
        driver._browser = _make_mock_browser()

        # Simulate a PAGE_LOADED event
        event = SemanticEvent.create(
            type=EventType.PAGE_LOADED,
            source="chromium",
            payload={"url": "https://example.com", "title": "Example"},
        )
        driver._event_queue.put_nowait(event)

        events = []
        async for ev in driver.observe():
            events.append(ev)
            if len(events) >= 1:
                break

        assert len(events) >= 1
        assert events[0].type == EventType.PAGE_LOADED

    async def test_observe_yields_dom_changed(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()
        driver._browser = _make_mock_browser()

        event = SemanticEvent.create(
            type=EventType.DOM_CHANGED,
            source="chromium",
            payload={"added": 1, "removed": 0, "modified": 0},
        )
        driver._event_queue.put_nowait(event)

        events = []
        async for ev in driver.observe():
            events.append(ev)
            if len(events) >= 1:
                break

        assert events[0].type == EventType.DOM_CHANGED

    async def test_observe_stops_when_disconnected(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()
        driver._browser = _make_mock_browser()

        # Disconnect after a short delay
        async def _disconnect_later() -> None:
            await asyncio.sleep(0.05)
            driver._state = DriverState.DISCONNECTED

        asyncio.create_task(_disconnect_later())

        async for _ in driver.observe():
            pass

        assert driver.state == DriverState.DISCONNECTED

    async def test_observe_skips_empty_queue(self) -> None:
        """Observe loop handles empty queue and stops when disconnected."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = None

        async def _stop_later() -> None:
            await asyncio.sleep(0.1)
            driver._state = DriverState.DISCONNECTED

        asyncio.create_task(_stop_later())

        events = [ev async for ev in driver.observe()]

        assert isinstance(events, list)

    async def test_observe_handles_page_none(self) -> None:
        """Observe handles page=None gracefully during DOM polling."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = None

        async def _stop_later() -> None:
            await asyncio.sleep(0.1)
            driver._state = DriverState.DISCONNECTED

        asyncio.create_task(_stop_later())

        events = [ev async for ev in driver.observe()]

        assert isinstance(events, list)


# ---------------------------------------------------------------------------
# Publish Methods
# ---------------------------------------------------------------------------


class TestPublishMethods:
    async def test_publish_to_bus(self) -> None:
        """_publish sends event to both queue and bus."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        bus = MemoryEventBus()
        driver._event_bus = bus
        driver._page = _make_mock_page()

        event = SemanticEvent.create(
            type=EventType.CUSTOM,
            source="chromium",
            payload={"test": True},
        )
        await driver._publish(event)

        assert driver._event_queue.qsize() == 1

    async def test_publish_without_bus(self) -> None:
        """_publish should not raise when event_bus is None."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()

        event = SemanticEvent.create(
            type=EventType.CUSTOM,
            source="chromium",
            payload={"test": True},
        )
        await driver._publish(event)

        assert driver._event_queue.qsize() == 1

    async def test_publish_action_result_success(self) -> None:
        """_publish_action_result publishes ACTION_COMPLETED on success."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        bus = MemoryEventBus()
        driver._event_bus = bus
        driver._page = _make_mock_page()

        action = Action(name="click", target="#btn")
        result = ActionResult(action_id=action.action_id, success=True)
        await driver._publish_action_result(action, result)

        await bus.drain()
        assert bus.stats().events_published == 1

    async def test_publish_action_result_failure(self) -> None:
        """_publish_action_result publishes ACTION_FAILED on failure."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        bus = MemoryEventBus()
        driver._event_bus = bus
        driver._page = _make_mock_page()

        action = Action(name="click", target="#btn")
        result = ActionResult(
            action_id=action.action_id,
            success=False,
            error="timeout",
        )
        await driver._publish_action_result(action, result)

        await bus.drain()
        assert bus.stats().events_published == 1

    async def test_publish_action_result_no_bus(self) -> None:
        """_publish_action_result should not raise when event_bus is None."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()

        action = Action(name="click", target="#btn")
        result = ActionResult(action_id=action.action_id, success=True)
        await driver._publish_action_result(action, result)  # should not raise

    async def test_publish_user_event_click(self) -> None:
        """_publish_user_event publishes USER_INPUT for click actions."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        bus = MemoryEventBus()
        driver._event_bus = bus
        driver._page = _make_mock_page()

        action = Action(name="click", target="#btn")
        driver._publish_user_event(action)

    async def test_publish_user_event_type(self) -> None:
        """_publish_user_event publishes USER_INPUT for type actions."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        bus = MemoryEventBus()
        driver._event_bus = bus
        driver._page = _make_mock_page()

        action = Action(name="type", target="#input", parameters={"text": "hello"})
        driver._publish_user_event(action)

    async def test_publish_user_event_screenshot(self) -> None:
        """_publish_user_event publishes SCREENSHOT_TAKEN for screenshot actions."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        bus = MemoryEventBus()
        driver._event_bus = bus
        driver._page = _make_mock_page()

        action = Action(name="screenshot")
        driver._publish_user_event(action)

    async def test_publish_user_event_unknown_action(self) -> None:
        """_publish_user_event ignores unknown action types."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        bus = MemoryEventBus()
        driver._event_bus = bus
        driver._page = _make_mock_page()

        action = Action(name="unknown_action")
        driver._publish_user_event(action)  # should not raise

    async def test_publish_user_event_no_bus(self) -> None:
        """_publish_user_event should not raise when event_bus is None."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()

        action = Action(name="click", target="#btn")
        driver._publish_user_event(action)  # should not raise


# ---------------------------------------------------------------------------
# Page Event Handlers
# ---------------------------------------------------------------------------


class TestPageEventHandlers:
    async def test_on_page_loaded_publishes_event(self) -> None:
        """_on_page_loaded creates and queues PAGE_LOADED event."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()
        bus = MemoryEventBus()
        driver._event_bus = bus

        driver._on_page_loaded()

        assert driver._event_queue.qsize() >= 1

    async def test_on_page_loaded_no_page(self) -> None:
        """_on_page_loaded should not raise when page is None."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = None

        driver._on_page_loaded()  # should not raise

    async def test_on_page_error_publishes_event(self) -> None:
        """_on_page_error creates and queues PAGE_ERROR event."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()
        bus = MemoryEventBus()
        driver._event_bus = bus

        driver._on_page_error("Test error message")

        assert driver._event_queue.qsize() >= 1

    async def test_on_page_error_no_page(self) -> None:
        """_on_page_error should not raise when page is None."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = None

        driver._on_page_error("Test error")  # should not raise


# ---------------------------------------------------------------------------
# DOM Polling
# ---------------------------------------------------------------------------


class TestDomPolling:
    async def test_poll_dom_changes_no_page(self) -> None:
        """_poll_dom_changes returns None when page is None."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._page = None

        result = await driver._poll_dom_changes()
        assert result is None

    async def test_poll_dom_changes_exception(self) -> None:
        """_poll_dom_changes returns None when page.evaluate raises."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._page = _make_mock_page()
        driver._page.evaluate.side_effect = RuntimeError("Browser closed")

        result = await driver._poll_dom_changes()
        assert result is None

    def test_has_dom_changes_all_zero(self) -> None:
        """_has_dom_changes returns False when all counts are zero."""
        from artax.drivers.chromium.driver import _has_dom_changes

        assert _has_dom_changes({"added": 0, "removed": 0, "modified": 0}) is False

    def test_has_dom_changes_nonzero(self) -> None:
        """_has_dom_changes returns True when any count is non-zero."""
        from artax.drivers.chromium.driver import _has_dom_changes

        assert _has_dom_changes({"added": 1, "removed": 0, "modified": 0}) is True
        assert _has_dom_changes({"added": 0, "removed": 1, "modified": 0}) is True
        assert _has_dom_changes({"added": 0, "removed": 0, "modified": 1}) is True


# ---------------------------------------------------------------------------
# Playwright Import Error
# ---------------------------------------------------------------------------


class TestPlaywrightImportError:
    async def test_connect_handles_playwright_missing(self) -> None:
        """Connect raises DriverError when playwright is not installed."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)

        with (
            patch(
                "artax.drivers.chromium.driver._get_playwright",
                side_effect=ImportError("No module named 'playwright'"),
            ),
            pytest.raises(DriverError),
        ):
            await driver.connect(MemoryEventBus())

        assert driver.state == DriverState.ERROR


# ---------------------------------------------------------------------------
# Chrome Auto-Launch
# ---------------------------------------------------------------------------


class TestFindChrome:
    def test_find_chrome_returns_path(self) -> None:
        from artax.drivers.chromium.driver import _find_chrome

        result = _find_chrome()
        if result is not None:
            assert isinstance(result, str)

    def test_find_chrome_returns_none(self) -> None:
        from artax.drivers.chromium.driver import _find_chrome

        with (
            patch("shutil.which", return_value=None),
            patch("pathlib.Path.is_file", return_value=False),
        ):
            assert _find_chrome() is None

    def test_find_chrome_respects_env_var(self) -> None:
        from artax.drivers.chromium.driver import _find_chrome

        with (
            patch.dict("os.environ", {"ARTAX_CHROME_PATH": "/custom/chrome"}),
            patch("pathlib.Path.is_file", return_value=True),
            patch("os.access", return_value=True),
        ):
            assert _find_chrome() == "/custom/chrome"

    def test_find_chrome_prioritizes_env_var(self) -> None:
        from artax.drivers.chromium.driver import _find_chrome

        with (
            patch.dict("os.environ", {"ARTAX_CHROME_PATH": "/custom/chrome"}),
            patch("shutil.which", return_value="/system/chrome"),
            patch("pathlib.Path.is_file", return_value=True),
            patch("os.access", return_value=True),
        ):
            assert _find_chrome() == "/custom/chrome"


class TestChromeAutoLaunch:
    async def test_cdp_failure_falls_back_to_playwright(self) -> None:
        config = ChromiumConfig(cdp_url="http://127.0.0.1:9222")
        driver = ChromiumDriver(config)

        mock_pw = _make_mock_playwright()
        mock_browser = _make_mock_browser()
        mock_context = _make_mock_context()
        mock_page = _make_mock_page()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_pw.chromium.launch.return_value = mock_browser

        with (
            patch("artax.drivers.chromium.driver._get_playwright", return_value=mock_pw),
            patch.object(driver, "_connect_via_cdp", side_effect=RuntimeError("CDP refused")),
            patch.object(driver, "_close_browser", new=AsyncMock()),
        ):
            await driver.connect(MemoryEventBus())

        assert driver.state == DriverState.CONNECTED
        mock_pw.chromium.launch.assert_called_once()

    async def test_playwright_failure_falls_back_to_chrome_autolaunch(self) -> None:
        config = ChromiumConfig(cdp_url=None)
        driver = ChromiumDriver(config)

        mock_pw = _make_mock_playwright()
        mock_pw.chromium.launch.side_effect = RuntimeError("Browser not found")

        mock_browser = _make_mock_browser()
        mock_context = _make_mock_context()
        mock_page = _make_mock_page()
        mock_pw.chromium.connect_over_cdp.return_value = mock_browser
        mock_browser.contexts = [mock_context]
        mock_context.pages = [mock_page]

        mock_launch = AsyncMock(return_value="http://127.0.0.1:9222")
        with (
            patch("artax.drivers.chromium.driver._get_playwright", return_value=mock_pw),
            patch.object(driver, "_launch_chrome_cdp", new=mock_launch),
            patch.object(driver, "_close_browser", new=AsyncMock()),
        ):
            await driver.connect(MemoryEventBus())

        assert driver.state == DriverState.CONNECTED
        mock_launch.assert_called_once()
        mock_pw.chromium.connect_over_cdp.assert_called_once_with(
            "http://127.0.0.1:9222",
        )

    async def test_chrome_not_found_raises_driver_error(self) -> None:
        config = ChromiumConfig(cdp_url=None)
        driver = ChromiumDriver(config)

        mock_pw = _make_mock_playwright()
        mock_pw.chromium.launch.side_effect = RuntimeError("Browser not found")

        with (
            patch("artax.drivers.chromium.driver._get_playwright", return_value=mock_pw),
            patch("artax.drivers.chromium.driver._find_chrome", return_value=None),
            pytest.raises(DriverError),
        ):
            await driver.connect(MemoryEventBus())

        assert driver.state == DriverState.ERROR


class TestHealthCheckAnomalies:
    async def test_health_when_unhealthy(self) -> None:
        """Health check reflects UNHEALTHY state."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.UNHEALTHY
        driver._error_count = 5

        health = await driver.health_check()
        assert health.state == DriverState.UNHEALTHY
        assert health.error_count == 5

    async def test_health_error_count_increments(self) -> None:
        """Health check preserves error_count across calls."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.ERROR
        driver._error_count = 3

        health = await driver.health_check()
        assert health.state == DriverState.ERROR
        assert health.error_count == 3


# ---------------------------------------------------------------------------
# Execute Anomalies
# ---------------------------------------------------------------------------


class TestExecuteAnomalies:
    async def test_execute_unknown_action_returns_error(self) -> None:
        """Executing an unknown action returns failure with error message."""
        driver = self._connected_driver()
        action = Action(name="nonexistent_action")
        result = await driver.execute(action)
        assert result.success is False
        assert result.error is not None

    async def test_execute_when_not_connected(self) -> None:
        """Executing when not connected returns failure."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        action = Action(name="click", target="#btn")
        result = await driver.execute(action)
        assert result.success is False
        assert result.error is not None

    async def test_execute_page_error_returns_failure(self) -> None:
        """Executing when page raises returns failure."""
        driver = self._connected_driver()
        driver._page.click.side_effect = RuntimeError("Element not found")
        action = Action(name="click", target="#missing")
        result = await driver.execute(action)
        assert result.success is False
        assert "Element not found" in (result.error or "")

    def _connected_driver(self) -> ChromiumDriver:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()
        driver._browser = _make_mock_browser()
        return driver


# ---------------------------------------------------------------------------
# Disconnect Anomalies
# ---------------------------------------------------------------------------


class TestDisconnectAnomalies:
    async def test_disconnect_when_never_connected(self) -> None:
        """Disconnecting when never connected is a safe no-op."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        assert driver.state == DriverState.DISCONNECTED

        await driver.disconnect()  # should not raise

        assert driver.state == DriverState.DISCONNECTED

    async def test_disconnect_with_page_close_error(self) -> None:
        """Disconnect handles page close errors gracefully."""
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()
        driver._page.close.side_effect = RuntimeError("Already closed")
        driver._browser = _make_mock_browser()

        await driver.disconnect()  # should not raise
        assert driver.state == DriverState.DISCONNECTED


# ---------------------------------------------------------------------------
# Fill / Scroll / Wait-For Actions
# ---------------------------------------------------------------------------


class TestFillAction:
    def _connected_driver(self) -> ChromiumDriver:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()
        driver._browser = _make_mock_browser()
        return driver

    async def test_fill_action(self) -> None:
        driver = self._connected_driver()
        action = Action(
            name="fill",
            target="input[name=email]",
            parameters={"value": "user@example.com"},
        )
        result = await driver.execute(action)
        assert result.success is True
        driver._page.fill.assert_called_once_with(
            "input[name=email]", "user@example.com", timeout=10000
        )

    async def test_fill_action_not_connected(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        action = Action(
            name="fill",
            target="input[name=email]",
            parameters={"value": "user@example.com"},
        )
        result = await driver.execute(action)
        assert result.success is False


class TestScrollAction:
    def _connected_driver(self) -> ChromiumDriver:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()
        driver._browser = _make_mock_browser()
        return driver

    async def test_scroll_action(self) -> None:
        driver = self._connected_driver()
        action = Action(
            name="scroll",
            parameters={"x": 100, "y": 200},
        )
        result = await driver.execute(action)
        assert result.success is True
        driver._page.evaluate.assert_called_once_with("window.scrollBy(100, 200)")

    async def test_scroll_action_default_zero(self) -> None:
        driver = self._connected_driver()
        action = Action(name="scroll")
        result = await driver.execute(action)
        assert result.success is True
        driver._page.evaluate.assert_called_once_with("window.scrollBy(0, 0)")


class TestWaitForAction:
    def _connected_driver(self) -> ChromiumDriver:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()
        driver._browser = _make_mock_browser()
        return driver

    async def test_wait_for_action(self) -> None:
        driver = self._connected_driver()
        action = Action(name="wait_for", target="#loaded")
        result = await driver.execute(action)
        assert result.success is True
        driver._page.wait_for_selector.assert_called_once()

    async def test_wait_for_action_not_connected(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        action = Action(name="wait_for", target="#loaded")
        result = await driver.execute(action)
        assert result.success is False


# ---------------------------------------------------------------------------
# Page State Methods
# ---------------------------------------------------------------------------


class TestPageStateMethods:
    def _connected_driver(self) -> ChromiumDriver:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()
        driver._browser = _make_mock_browser()
        return driver

    async def test_current_url(self) -> None:
        driver = self._connected_driver()
        url = await driver.current_url()
        assert url == "about:blank"

    async def test_current_title(self) -> None:
        driver = self._connected_driver()
        title = await driver.current_title()
        assert title == "Test Page"

    async def test_page_html(self) -> None:
        driver = self._connected_driver()
        html = await driver.page_html()
        assert html == "<html><body></body></html>"

    async def test_current_url_when_no_page(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._page = None
        url = await driver.current_url()
        assert url == ""

    async def test_current_title_when_no_page(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._page = None
        title = await driver.current_title()
        assert title == ""

    async def test_page_html_when_no_page(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._page = None
        html = await driver.page_html()
        assert html == ""


# ---------------------------------------------------------------------------
# Console and Frame Navigated Handlers
# ---------------------------------------------------------------------------


class TestConsoleHandler:
    async def test_on_console_publishes_user_input(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()
        bus = MemoryEventBus()
        driver._event_bus = bus

        mock_msg = MagicMock()
        mock_msg.text = "hello world"
        driver._on_console(mock_msg)

        assert driver._event_queue.qsize() >= 1

    async def test_on_console_no_bus(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()

        mock_msg = MagicMock()
        mock_msg.text = "hello world"
        driver._on_console(mock_msg)  # should not raise


class TestFrameNavigatedHandler:
    async def test_on_framenavigated_publishes_dom_changed(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()
        bus = MemoryEventBus()
        driver._event_bus = bus

        driver._on_frame_navigated(MagicMock())

        assert driver._event_queue.qsize() >= 1

    async def test_on_framenavigated_no_bus(self) -> None:
        config = ChromiumConfig()
        driver = ChromiumDriver(config)
        driver._state = DriverState.CONNECTED
        driver._page = _make_mock_page()

        driver._on_frame_navigated(MagicMock())  # should not raise


# ---------------------------------------------------------------------------
# Config New Fields
# ---------------------------------------------------------------------------


class TestChromiumConfigNewFields:
    def test_screenshot_timeout_ms_default(self) -> None:
        config = ChromiumConfig()
        assert config.screenshot_timeout_ms == 5000

    def test_dom_observer_threshold_default(self) -> None:
        config = ChromiumConfig()
        assert config.dom_observer_threshold == "significant"

    def test_user_data_dir_default(self) -> None:
        config = ChromiumConfig()
        assert config.user_data_dir is None

    def test_screenshot_quality_default(self) -> None:
        config = ChromiumConfig()
        assert config.screenshot_quality == 80

    def test_cdp_port_default(self) -> None:
        config = ChromiumConfig()
        assert config.cdp_port == 9222

    def test_custom_screenshot_timeout(self) -> None:
        config = ChromiumConfig(screenshot_timeout_ms=8000)
        assert config.screenshot_timeout_ms == 8000

    def test_custom_dom_observer_threshold(self) -> None:
        config = ChromiumConfig(dom_observer_threshold="all")
        assert config.dom_observer_threshold == "all"

    def test_custom_user_data_dir(self) -> None:
        config = ChromiumConfig(user_data_dir="/home/user/profile")
        assert config.user_data_dir == "/home/user/profile"

    def test_custom_screenshot_quality(self) -> None:
        config = ChromiumConfig(screenshot_quality=90)
        assert config.screenshot_quality == 90


# ---------------------------------------------------------------------------
# MutationObserver Script
# ---------------------------------------------------------------------------


class TestMutationObserver:
    def test_inject_script_contains_observer(self) -> None:
        assert "MutationObserver" in MUTATION_OBSERVER_SCRIPT
        assert "childList" in MUTATION_OBSERVER_SCRIPT
        assert "attributes" in MUTATION_OBSERVER_SCRIPT
        assert "subtree" in MUTATION_OBSERVER_SCRIPT
