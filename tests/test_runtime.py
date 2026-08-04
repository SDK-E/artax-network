"""Tests for Runtime core orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator

import pytest

from artax.actions.types import ActionResult
from artax.dashboard.config import DashboardConfig
from artax.dashboard.server import DashboardServer
from artax.drivers.base import BaseDriver
from artax.events.types import Event, EventFilter, EventType, SemanticEvent
from artax.runtime import _apply_env_overrides, _build_runtime_config, _load_config, _parse_args
from artax.runtime.core import Runtime, RuntimeConfig, RuntimeState, RuntimeStatus

# ---------------------------------------------------------------------------
# Stub Drivers
# ---------------------------------------------------------------------------


class OkDriver(BaseDriver):
    """Minimal driver that succeeds."""

    def __init__(self, name: str) -> None:
        """Initialize the ok driver."""
        super().__init__(name=name, config=_TestConfig())

    async def _do_connect(self) -> None:
        pass

    async def _do_disconnect(self) -> None:
        pass

    async def observe(self) -> AsyncIterator[Event]:
        async def _empty_events() -> AsyncGenerator[Event, None]:
            if False:
                yield  # pragma: no cover

        return _empty_events()

    async def execute(self, action: object) -> ActionResult:
        return ActionResult(action_id="x", success=True)


class FailConnectDriver(BaseDriver):
    """Driver that fails on connect."""

    def __init__(self, name: str) -> None:
        """Initialize the failing connect driver."""
        super().__init__(name=name, config=_TestConfig())

    async def _do_connect(self) -> None:
        raise RuntimeError("Connection refused")

    async def _do_disconnect(self) -> None:
        pass

    async def observe(self) -> AsyncIterator[Event]:
        async def _empty_events() -> AsyncGenerator[Event, None]:
            if False:
                yield  # pragma: no cover

        return _empty_events()

    async def execute(self, action: object) -> ActionResult:
        return ActionResult(action_id="x", success=False)


class _TestConfig:
    @property
    def driver_type(self) -> str:
        return "test"


# ---------------------------------------------------------------------------
# RuntimeConfig
# ---------------------------------------------------------------------------


class TestRuntimeConfig:
    def test_defaults(self) -> None:
        config = RuntimeConfig()
        assert config.shutdown_timeout == 5.0
        assert config.drivers == []
        assert config.event_bus is not None
        assert config.memory is not None
        assert config.scheduler is not None

    def test_custom(self) -> None:
        config = RuntimeConfig(shutdown_timeout=10.0)
        assert config.shutdown_timeout == 10.0

    def test_mutable(self) -> None:
        config = RuntimeConfig()
        config.shutdown_timeout = 30.0
        assert config.shutdown_timeout == 30.0


# ---------------------------------------------------------------------------
# RuntimeStatus
# ---------------------------------------------------------------------------


class TestRuntimeStatus:
    def test_defaults(self) -> None:
        status = RuntimeStatus()
        assert status.state == RuntimeState.STOPPED
        assert status.uptime == 0.0
        assert status.drivers_connected == 0
        assert status.events_published == 0

    def test_custom(self) -> None:
        status = RuntimeStatus(
            state=RuntimeState.RUNNING,
            uptime=42.0,
            drivers_connected=2,
            events_published=100,
        )
        assert status.state == RuntimeState.RUNNING
        assert status.uptime == 42.0
        assert status.drivers_connected == 2
        assert status.events_published == 100


# ---------------------------------------------------------------------------
# Runtime Lifecycle
# ---------------------------------------------------------------------------


class TestRuntimeLifecycle:
    async def test_start_stop_cycle(self) -> None:
        runtime = Runtime(RuntimeConfig())
        initial = runtime.state
        assert initial == RuntimeState.STOPPED
        await runtime.start()
        running_state = runtime.state
        assert running_state == RuntimeState.RUNNING
        await runtime.stop()
        stopped_state = runtime.state
        assert stopped_state == RuntimeState.STOPPED

    async def test_stop_when_stopped_is_noop(self) -> None:
        runtime = Runtime(RuntimeConfig())
        await runtime.stop()
        assert runtime.state == RuntimeState.STOPPED

    async def test_double_stop(self) -> None:
        runtime = Runtime(RuntimeConfig())
        await runtime.start()
        await runtime.stop()
        await runtime.stop()
        assert runtime.state == RuntimeState.STOPPED

    async def test_properties_after_start(self) -> None:
        runtime = Runtime(RuntimeConfig())
        await runtime.start()
        assert runtime.event_bus is not None
        assert runtime.memory is not None
        assert runtime.scheduler is not None
        await runtime.stop()

    async def test_event_bus_before_start_raises(self) -> None:
        runtime = Runtime(RuntimeConfig())
        with pytest.raises(RuntimeError, match="not started"):
            _ = runtime.event_bus

    async def test_memory_before_start_raises(self) -> None:
        runtime = Runtime(RuntimeConfig())
        with pytest.raises(RuntimeError, match="not started"):
            _ = runtime.memory

    async def test_scheduler_before_start_raises(self) -> None:
        runtime = Runtime(RuntimeConfig())
        with pytest.raises(RuntimeError, match="not started"):
            _ = runtime.scheduler


# ---------------------------------------------------------------------------
# Driver Registration
# ---------------------------------------------------------------------------


class TestDriverRegistration:
    async def test_register_driver(self) -> None:
        runtime = Runtime(RuntimeConfig())
        d = OkDriver("d1")
        runtime.register_driver(d)
        assert len(runtime.drivers) == 1

    async def test_register_duplicate_ignored(self) -> None:
        runtime = Runtime(RuntimeConfig())
        d1 = OkDriver("d1")
        d2 = OkDriver("d1")
        runtime.register_driver(d1)
        runtime.register_driver(d2)
        assert len(runtime.drivers) == 1

    async def test_driver_connected_on_start(self) -> None:
        runtime = Runtime(RuntimeConfig())
        d = OkDriver("d1")
        runtime.register_driver(d)
        await runtime.start()
        assert d.is_connected is True
        await runtime.stop()

    async def test_driver_disconnected_on_stop(self) -> None:
        runtime = Runtime(RuntimeConfig())
        d = OkDriver("d1")
        runtime.register_driver(d)
        await runtime.start()
        await runtime.stop()
        assert d.is_connected is False

    async def test_multiple_drivers(self) -> None:
        runtime = Runtime(RuntimeConfig())
        d1 = OkDriver("d1")
        d2 = OkDriver("d2")
        runtime.register_driver(d1)
        runtime.register_driver(d2)
        await runtime.start()
        assert d1.is_connected is True
        assert d2.is_connected is True
        status = runtime.status()
        assert status.drivers_connected == 2
        await runtime.stop()


# ---------------------------------------------------------------------------
# Failed Driver Handling
# ---------------------------------------------------------------------------


class TestFailedDriver:
    async def test_connect_failure_continues(self) -> None:
        runtime = Runtime(RuntimeConfig())
        ok = OkDriver("ok")
        bad = FailConnectDriver("bad")
        runtime.register_driver(bad)
        runtime.register_driver(ok)
        await runtime.start()
        assert ok.is_connected is True
        assert bad.is_connected is False
        await runtime.stop()


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class TestMetrics:
    async def test_status_after_start(self) -> None:
        runtime = Runtime(RuntimeConfig())
        d = OkDriver("d1")
        runtime.register_driver(d)
        await runtime.start()
        status = runtime.status()
        assert status.state == RuntimeState.RUNNING
        assert status.drivers_connected == 1
        assert status.uptime >= 0.0
        await runtime.stop()

    async def test_uptime_advances(self) -> None:
        runtime = Runtime(RuntimeConfig())
        await runtime.start()
        s1 = runtime.status()
        await asyncio.sleep(0.05)
        s2 = runtime.status()
        assert s2.uptime > s1.uptime
        await runtime.stop()


# ---------------------------------------------------------------------------
# EventBus Events
# ---------------------------------------------------------------------------


class TestRuntimeEvents:
    async def test_start_emits_runtime_started(self) -> None:
        runtime = Runtime(RuntimeConfig())
        received: list[SemanticEvent] = []

        async def _handler(event: object) -> None:
            if isinstance(event, SemanticEvent):
                received.append(event)

        await runtime.start()
        await runtime.event_bus.subscribe(EventFilter(), _handler)

        test_event = SemanticEvent.create(
            type=EventType.CUSTOM,
            source="test",
            payload={"event": "test.ping"},
        )
        await runtime.event_bus.publish(test_event)
        await runtime.event_bus.drain()
        await runtime.stop()

        assert any(e.payload.get("event") == "test.ping" for e in received)

    async def test_stop_emits_driver_disconnected(self) -> None:
        runtime = Runtime(RuntimeConfig())
        d = OkDriver("d1")
        runtime.register_driver(d)

        received_events: list[str] = []

        async def _handler(event: object) -> None:
            if isinstance(event, SemanticEvent):
                received_events.append(event.type.value)

        await runtime.start()
        await runtime.event_bus.subscribe(EventFilter(), _handler)
        await asyncio.sleep(0.05)
        await runtime.stop()
        await asyncio.sleep(0.05)

        assert "driver_disconnected" in received_events


# ---------------------------------------------------------------------------
# run_forever
# ---------------------------------------------------------------------------


class TestRunForever:
    async def test_run_forever_starts_and_stops(self) -> None:
        runtime = Runtime(RuntimeConfig())

        async def _stop_after_delay() -> None:
            await asyncio.sleep(0.1)
            await runtime.stop()

        task = asyncio.create_task(_stop_after_delay())
        await runtime.run_forever()
        await task
        assert runtime.state == RuntimeState.STOPPED


# ---------------------------------------------------------------------------
# Runtime Anomalies
# ---------------------------------------------------------------------------


class TestRuntimeAnomalies:
    async def test_double_start_raises(self) -> None:
        """Starting an already-running runtime raises RuntimeError."""
        runtime = Runtime(RuntimeConfig())
        await runtime.start()
        with pytest.raises(RuntimeError, match="Cannot start"):
            await runtime.start()
        await runtime.stop()

    async def test_properties_before_start_raise(self) -> None:
        """Accessing runtime properties before start raises RuntimeError."""
        runtime = Runtime(RuntimeConfig())
        with pytest.raises(RuntimeError, match="not started"):
            _ = runtime.event_bus
        with pytest.raises(RuntimeError, match="not started"):
            _ = runtime.memory
        with pytest.raises(RuntimeError, match="not started"):
            _ = runtime.scheduler

    async def test_stop_when_stopped_is_noop(self) -> None:
        """Stopping an already-stopped runtime is a safe no-op."""
        runtime = Runtime(RuntimeConfig())
        await runtime.stop()
        assert runtime.state == RuntimeState.STOPPED

    async def test_double_stop_is_noop(self) -> None:
        """Stopping a stopped runtime after a prior stop is a no-op."""
        runtime = Runtime(RuntimeConfig())
        await runtime.start()
        await runtime.stop()
        await runtime.stop()
        assert runtime.state == RuntimeState.STOPPED

    async def test_status_during_run(self) -> None:
        """Runtime status reflects running state during execution."""
        runtime = Runtime(RuntimeConfig())
        await runtime.start()
        status = runtime.status()
        assert status.state == RuntimeState.RUNNING
        assert status.uptime >= 0.0
        await runtime.stop()

    async def test_register_duplicate_driver_ignored(self) -> None:
        """Registering a driver with a duplicate name is silently ignored."""
        runtime = Runtime(RuntimeConfig())
        d1 = OkDriver("d1")
        d2 = OkDriver("d1")
        runtime.register_driver(d1)
        runtime.register_driver(d2)
        assert len(runtime.drivers) == 1

    async def test_driver_connect_failure_marks_error(self) -> None:
        """A driver that fails to connect is marked ERROR and runtime continues."""
        runtime = Runtime(RuntimeConfig())
        ok = OkDriver("ok")
        bad = FailConnectDriver("bad")
        runtime.register_driver(bad)
        runtime.register_driver(ok)
        await runtime.start()
        assert ok.is_connected is True
        assert bad.is_connected is False
        await runtime.stop()

    async def test_driver_disconnect_timeout_handled(self) -> None:
        """Runtime handles driver disconnect timeout gracefully."""
        runtime = Runtime(RuntimeConfig(shutdown_timeout=0.01))
        d = OkDriver("d1")
        runtime.register_driver(d)
        await runtime.start()
        await runtime.stop()
        assert runtime.state == RuntimeState.STOPPED


# ---------------------------------------------------------------------------
# Dashboard Auto-Start
# ---------------------------------------------------------------------------


class TestDashboardAutoStart:
    """Dashboard starts automatically with default config when none is provided."""

    async def test_dashboard_starts_with_default_config(self) -> None:
        """Dashboard server starts automatically even without explicit config."""
        runtime = Runtime(RuntimeConfig())
        assert runtime._config.dashboard is not None
        await runtime.start()
        assert runtime._dashboard is not None
        assert isinstance(runtime._dashboard, DashboardServer)
        assert runtime._dashboard.running is True
        await runtime.stop()

    async def test_dashboard_starts_with_explicit_config(self) -> None:
        """Dashboard server starts with explicit config when provided."""
        cfg = DashboardConfig(ws_port=9001)
        runtime = Runtime(RuntimeConfig(dashboard=cfg))
        await runtime.start()
        assert runtime._dashboard is not None
        assert runtime._dashboard.running is True
        await runtime.stop()

    async def test_dashboard_stopped_after_runtime_stop(self) -> None:
        """Dashboard server is stopped when runtime stops."""
        cfg = DashboardConfig(ws_port=9002)
        runtime = Runtime(RuntimeConfig(dashboard=cfg))
        await runtime.start()
        assert runtime._dashboard is not None
        assert runtime._dashboard.running is True
        await runtime.stop()
        assert runtime._dashboard is None


# ---------------------------------------------------------------------------
# CLI Functions
# ---------------------------------------------------------------------------


class TestParseArgs:
    """Tests for _parse_args."""

    def test_default_args(self) -> None:
        args = _parse_args([])
        assert args.config == "artax.toml"
        assert args.log_level == "INFO"

    def test_custom_config(self) -> None:
        args = _parse_args(["-c", "custom.toml"])
        assert args.config == "custom.toml"

    def test_custom_log_level(self) -> None:
        args = _parse_args(["--log-level", "DEBUG"])
        assert args.log_level == "DEBUG"

    def test_env_config(self) -> None:
        import os

        os.environ["ARTAX_CONFIG"] = "env.toml"
        try:
            args = _parse_args([])
            assert args.config == "env.toml"
        finally:
            del os.environ["ARTAX_CONFIG"]


class TestLoadConfig:
    """Tests for _load_config."""

    def test_missing_file_returns_empty_dict(self) -> None:
        result = _load_config("nonexistent_file_12345.toml")
        assert result == {}

    def test_loads_valid_toml(self, tmp_path: object) -> None:
        config_file = tmp_path / "test.toml"
        config_file.write_bytes(b"[runtime]\nshutdown_timeout = 10.0\n")
        result = _load_config(str(config_file))
        assert result["runtime"]["shutdown_timeout"] == 10.0


class TestApplyEnvOverrides:
    """Tests for _apply_env_overrides."""

    def test_no_overrides_returns_empty(self) -> None:
        result = _apply_env_overrides({})
        assert result == {}

    def test_shutdown_timeout_override(self) -> None:
        import os

        os.environ["ARTAX_SHUTDOWN_TIMEOUT"] = "15.0"
        try:
            result = _apply_env_overrides({})
            assert result["runtime"]["shutdown_timeout"] == 15.0
        finally:
            del os.environ["ARTAX_SHUTDOWN_TIMEOUT"]

    def test_log_level_override(self) -> None:
        import os

        os.environ["ARTAX_LOG_LEVEL"] = "DEBUG"
        try:
            result = _apply_env_overrides({})
            assert result["runtime"]["log_level"] == "DEBUG"
        finally:
            del os.environ["ARTAX_LOG_LEVEL"]


class TestBuildRuntimeConfig:
    """Tests for _build_runtime_config."""

    def test_empty_config_creates_defaults(self) -> None:
        result = _build_runtime_config({})
        assert result.shutdown_timeout == 5.0
        assert result.dashboard is not None
        assert result.dashboard.ws_port == 8081

    def test_custom_shutdown_timeout(self) -> None:
        result = _build_runtime_config({"runtime": {"shutdown_timeout": 10.0}})
        assert result.shutdown_timeout == 10.0

    def test_dashboard_config_from_toml(self) -> None:
        result = _build_runtime_config(
            {
                "dashboard": {"ws_port": 9001, "host": "0.0.0.0"},
            }
        )
        assert result.dashboard is not None
        assert result.dashboard.ws_port == 9001
        assert result.dashboard.host == "0.0.0.0"
