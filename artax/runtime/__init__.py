"""Artax runtime - core event loop and orchestration."""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import importlib
import logging
import os
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

from ..dashboard.config import DashboardConfig
from ..drivers.base import Driver
from ..events.types import EventBusConfig
from ..memory.base import MemoryConfig
from ..scheduler.core import SchedulerConfig
from .core import Runtime, RuntimeConfig

logger = logging.getLogger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="artax",
        description="Event-driven runtime for embodied AI",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=os.getenv("ARTAX_CONFIG", "artax.toml"),
        help="Path to TOML config file (default: artax.toml, env: ARTAX_CONFIG)",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("ARTAX_LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO, env: ARTAX_LOG_LEVEL)",
    )
    return parser.parse_args(argv)


def _load_config(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if config_path.is_file():
        with config_path.open("rb") as f:
            return tomllib.load(f)
    if os.getenv("ARTAX_CONFIG"):
        logger.error("Config file not found: %s", path)
        sys.exit(1)
    return {}


def _apply_env_overrides(cfg: dict[str, Any]) -> dict[str, Any]:
    timeout = os.getenv("ARTAX_SHUTDOWN_TIMEOUT")
    if timeout is not None:
        cfg.setdefault("runtime", {})["shutdown_timeout"] = float(timeout)
    log_level = os.getenv("ARTAX_LOG_LEVEL")
    if log_level is not None:
        cfg.setdefault("runtime", {})["log_level"] = log_level
    return cfg


def _build_runtime_config(toml_cfg: dict[str, Any]) -> RuntimeConfig:
    def _dc(key: str, cls: type) -> dict[str, Any]:
        cfg = toml_cfg.get(key, {})
        keys = {f.name for f in dataclasses.fields(cls)}
        return {k: v for k, v in cfg.items() if k in keys}

    dashboard = DashboardConfig(**_dc("dashboard", DashboardConfig))

    return RuntimeConfig(
        shutdown_timeout=toml_cfg.get("runtime", {}).get("shutdown_timeout", 5.0),
        event_bus=EventBusConfig(**_dc("event_bus", EventBusConfig)),
        memory=MemoryConfig(**_dc("memory", MemoryConfig)),
        scheduler=SchedulerConfig(**_dc("scheduler", SchedulerConfig)),
        dashboard=dashboard,
    )


_DRIVER_MODULES: dict[str, str] = {
    "chromium": "artax.drivers.chromium",
}


def _load_driver(driver_type: str, config: dict[str, Any]) -> Driver | None:
    """Instantiate a single driver from config.

    Uses dynamic import so the runtime CLI can support any driver
    without hardcoding imports at module level.

    Args:
        driver_type: Driver type string (e.g. "chromium").
        config: Driver-specific config fields.

    Returns:
        A Driver instance, or None if the driver type is unknown or
        its dependencies are not installed.

    """
    module_path = _DRIVER_MODULES.get(driver_type)
    if module_path is None:
        logger.warning("Unknown driver type: %s", driver_type)
        return None

    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        logger.warning("Driver '%s' dependencies not installed: %s", driver_type, e)
        return None

    config_cls: type | None = getattr(module, "DriverConfig", None)
    driver_cls: type | None = getattr(module, "Driver", None)
    if config_cls is None or driver_cls is None:
        logger.warning("Driver module '%s' incomplete", module_path)
        return None

    config_keys = {f.name for f in dataclasses.fields(config_cls)}
    config_kwargs = {k: v for k, v in config.items() if k in config_keys}
    cfg = config_cls(**config_kwargs)
    driver = driver_cls(config=cfg)
    return cast("Driver", driver)


def _load_drivers(toml_cfg: dict[str, Any]) -> list[Driver]:
    """Load and instantiate drivers from TOML configuration.

    Expects a ``[[drivers]]`` section in the config file:
    ```toml
    [[drivers]]
    type = "chromium"
    headless = true
    initial_url = "https://example.com"
    ```
    """
    drivers: list[Driver] = []
    driver_configs = toml_cfg.get("drivers", [])

    if isinstance(driver_configs, dict):
        driver_configs = [driver_configs]

    if not isinstance(driver_configs, list):
        return drivers

    for dc in driver_configs:
        if not isinstance(dc, dict):
            continue
        driver_type = str(dc.get("type", ""))
        if not driver_type:
            logger.warning("Driver config missing 'type' field, skipping")
            continue
        driver = _load_driver(driver_type, dc)
        if driver is not None:
            drivers.append(driver)

    return drivers


def cli(argv: list[str] | None = None) -> None:
    """CLI entry point for the Artax runtime."""
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    toml_cfg = _load_config(args.config)
    toml_cfg = _apply_env_overrides(toml_cfg)
    rt_config = _build_runtime_config(toml_cfg)
    runtime = Runtime(rt_config)

    for driver in _load_drivers(toml_cfg):
        runtime.register_driver(driver)
        logger.info("Loaded driver: %s", driver.name)

    async def _run() -> None:
        await runtime.run_forever()

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
