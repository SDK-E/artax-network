"""Chromium driver for Artax Network.

Provides browser automation via Playwright. The driver translates between
Chrome DevTools Protocol events and Artax events.
"""

from .config import ChromiumConfig as DriverConfig
from .driver import ChromiumDriver as Driver

__all__ = ["ChromiumConfig", "ChromiumDriver", "Driver", "DriverConfig"]
