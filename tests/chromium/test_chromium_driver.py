"""Tests for ChromiumDriver.

All Playwright interactions are mocked. Tests verify the driver translates
between Playwright APIs and Artax's event/action model correctly.
"""

from __future__ import annotations

import asyncio
import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from artax.actions.types import Action
from artax.drivers.base import DriverError, DriverState
from artax.drivers.chromium.config import ChromiumConfig
from artax.drivers.chromium.driver import MUTATION_OBSERVER_SCRIPT, ChromiumDriver
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
        assert driver.driver_type == "chromium"

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
            await driver.connect()

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
            await driver.connect()

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
            await driver.connect()

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
            await driver.connect()

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
            pytest.raises(DriverError),
        ):
            await driver.connect()

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
        driver._page.fill.assert_called_once_with(
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

        events: list[SemanticEvent] = []
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

        events: list[SemanticEvent] = []
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


# ---------------------------------------------------------------------------
# MutationObserver Script
# ---------------------------------------------------------------------------


class TestMutationObserver:
    def test_inject_script_contains_observer(self) -> None:
        assert "MutationObserver" in MUTATION_OBSERVER_SCRIPT
        assert "childList" in MUTATION_OBSERVER_SCRIPT
        assert "attributes" in MUTATION_OBSERVER_SCRIPT
        assert "subtree" in MUTATION_OBSERVER_SCRIPT
