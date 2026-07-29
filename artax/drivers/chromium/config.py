"""Chromium driver configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChromiumConfig:
    """Configuration for the Chromium browser driver.

    Attributes:
        headless: Whether to run the browser without a visible window.
        browser_path: Optional path to a custom Chromium binary.
        cdp_url: Optional Chrome DevTools Protocol URL for connecting to an
            existing browser instance instead of launching a new one.
        viewport_width: Browser viewport width in pixels.
        viewport_height: Browser viewport height in pixels.
        navigation_timeout_ms: Timeout in milliseconds for page navigation.
        action_timeout_ms: Timeout in milliseconds for individual actions.
        screenshot_format: Image format for screenshots ('png' or 'jpeg').
        screenshot_quality: JPEG quality (1-100), ignored for PNG.
        dom_observer_debounce_ms: Debounce interval in milliseconds for DOM
            mutation observations.
        initial_url: URL to navigate to after launching the browser.
        launch_args: Additional command-line arguments for the browser process.

    """

    headless: bool = True
    browser_path: str | None = None
    cdp_url: str | None = None
    viewport_width: int = 1280
    viewport_height: int = 720
    navigation_timeout_ms: int = 30000
    action_timeout_ms: int = 10000
    screenshot_format: str = "png"
    screenshot_quality: int = 100
    dom_observer_debounce_ms: int = 100
    initial_url: str = "about:blank"
    launch_args: tuple[str, ...] = ()

    @property
    def driver_type(self) -> str:
        """Return the driver type identifier."""
        return "chromium"
