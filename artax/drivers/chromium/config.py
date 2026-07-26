"""Chromium driver configuration."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChromiumConfig:
    """Configuration for the Chromium browser driver.

    Attributes:
        headless: Whether to run the browser without a visible window.
        browser_path: Optional path to a custom Chromium binary.
        viewport_width: Browser viewport width in pixels.
        viewport_height: Browser viewport height in pixels.
        user_data_dir: Optional path to a persistent user data directory.
        args: Additional command-line arguments passed to the browser process.
    """

    headless: bool = True
    browser_path: str | None = None
    viewport_width: int = 1280
    viewport_height: int = 720
    user_data_dir: str | None = None
    args: list[str] = field(default_factory=list)
