"""Logging configuration for the Artax runtime.

Provides centralized log setup and logger retrieval for all artax submodules.
"""
from __future__ import annotations

import logging


def configure_logging(level: str = "info") -> None:
    """Configure the root artax logger with the given verbosity level.

    Sets up a standard formatter with timestamp, level, module, and message.
    This should be called once at runtime startup before any subsystem logging.

    Args:
        level: Log level string (debug, info, warning, error, critical).
    """
    pass


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under the artax hierarchy.

    The returned logger is pre-configured with the ``artax.`` prefix so that
    all runtime log output is grouped under a single namespace.

    Args:
        name: The logger name, which will be prefixed with ``artax.``.

    Returns:
        A configured logging.Logger instance.
    """
    return logging.getLogger(f"artax.{name}")
