"""Artax runtime - core event loop and orchestration."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import tomllib
from pathlib import Path
from typing import Any

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
    rc = toml_cfg.get("runtime", {})
    return RuntimeConfig(
        shutdown_timeout=rc.get("shutdown_timeout", 5.0),
    )


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

    async def _run() -> None:
        await runtime.run_forever()

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
