"""Tests for ChromiumConfig."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

from artax.drivers.chromium.config import ChromiumConfig


class TestChromiumConfigDefaults:
    def test_headless_default(self) -> None:
        config = ChromiumConfig()
        assert config.headless is True

    def test_browser_path_default(self) -> None:
        config = ChromiumConfig()
        assert config.browser_path is None

    def test_cdp_url_default(self) -> None:
        config = ChromiumConfig()
        assert config.cdp_url is None

    def test_viewport_width_default(self) -> None:
        config = ChromiumConfig()
        assert config.viewport_width == 1280

    def test_viewport_height_default(self) -> None:
        config = ChromiumConfig()
        assert config.viewport_height == 720

    def test_navigation_timeout_ms_default(self) -> None:
        config = ChromiumConfig()
        assert config.navigation_timeout_ms == 30000

    def test_action_timeout_ms_default(self) -> None:
        config = ChromiumConfig()
        assert config.action_timeout_ms == 10000

    def test_screenshot_timeout_ms_default(self) -> None:
        config = ChromiumConfig()
        assert config.screenshot_timeout_ms == 5000

    def test_screenshot_format_default(self) -> None:
        config = ChromiumConfig()
        assert config.screenshot_format == "png"

    def test_screenshot_quality_default(self) -> None:
        config = ChromiumConfig()
        assert config.screenshot_quality == 80

    def test_dom_observer_debounce_ms_default(self) -> None:
        config = ChromiumConfig()
        assert config.dom_observer_debounce_ms == 100

    def test_dom_observer_threshold_default(self) -> None:
        config = ChromiumConfig()
        assert config.dom_observer_threshold == "significant"

    def test_user_data_dir_default(self) -> None:
        config = ChromiumConfig()
        assert config.user_data_dir is None

    def test_initial_url_default(self) -> None:
        config = ChromiumConfig()
        assert config.initial_url == "about:blank"

    def test_launch_args_default(self) -> None:
        config = ChromiumConfig()
        assert config.launch_args == ()

    def test_cdp_port_default(self) -> None:
        config = ChromiumConfig()
        assert config.cdp_port == 9222


class TestChromiumConfigCustom:
    def test_custom_values(self) -> None:
        config = ChromiumConfig(
            headless=False,
            browser_path="/usr/bin/chromium",
            cdp_url="http://localhost:9222",
            cdp_port=9223,
            viewport_width=1920,
            viewport_height=1080,
            navigation_timeout_ms=60000,
            action_timeout_ms=15000,
            screenshot_timeout_ms=8000,
            screenshot_format="jpeg",
            screenshot_quality=90,
            dom_observer_debounce_ms=200,
            dom_observer_threshold="all",
            user_data_dir="/home/user/chromium-profile",
            initial_url="https://example.com",
            launch_args=("--no-sandbox", "--disable-gpu"),
        )
        assert config.headless is False
        assert config.browser_path == "/usr/bin/chromium"
        assert config.cdp_url == "http://localhost:9222"
        assert config.cdp_port == 9223
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
        assert config.navigation_timeout_ms == 60000
        assert config.action_timeout_ms == 15000
        assert config.screenshot_timeout_ms == 8000
        assert config.screenshot_format == "jpeg"
        assert config.screenshot_quality == 90
        assert config.dom_observer_debounce_ms == 200
        assert config.dom_observer_threshold == "all"
        assert config.user_data_dir == "/home/user/chromium-profile"
        assert config.initial_url == "https://example.com"
        assert config.launch_args == ("--no-sandbox", "--disable-gpu")


class TestChromiumConfigFrozen:
    def test_frozen(self) -> None:
        config = ChromiumConfig()
        try:
            config.headless = False  # type: ignore[misc]
            raise AssertionError("Should have raised FrozenInstanceError")
        except FrozenInstanceError:
            pass

    def test_driver_type_property(self) -> None:
        config = ChromiumConfig()
        assert config.driver_type == "chromium"
