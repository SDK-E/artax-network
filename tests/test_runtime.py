"""Tests for Runtime core orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator

import pytest

from artax.actions.types import ActionResult
from artax.drivers.base import BaseDriver, DriverState
from artax.events.types import Event, EventFilter, EventType, SemanticEvent
from artax.runtime.core import Runtime, RuntimeConfig, RuntimeState, RuntimeStatus

# ---------------------------------------------------------------------------
# Stub Drivers
# ---------------------------------------------------------------------------


class OkDriver(BaseDriver):
    """Minimal driver that succeeds."""

    def __init__(self, name: str, driver_type: str = "test") -> None:
        """Initialize OkDriver."""
        super().__init__(name=name, driver_type=driver_type)

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

    def __init__(self, name: str, driver_type: str = "test") -> None:
        """Initialize FailConnectDriver."""
        super().__init__(name=name, driver_type=driver_type)

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
        d = OkDriver("d1", "test")
        runtime.register_driver(d)
        assert len(runtime.drivers) == 1

    async def test_register_duplicate_ignored(self) -> None:
        runtime = Runtime(RuntimeConfig())
        d1 = OkDriver("d1", "test")
        d2 = OkDriver("d1", "test")
        runtime.register_driver(d1)
        runtime.register_driver(d2)
        assert len(runtime.drivers) == 1

    async def test_driver_connected_on_start(self) -> None:
        runtime = Runtime(RuntimeConfig())
        d = OkDriver("d1", "test")
        runtime.register_driver(d)
        await runtime.start()
        assert d.state == DriverState.CONNECTED
        await runtime.stop()

    async def test_driver_disconnected_on_stop(self) -> None:
        runtime = Runtime(RuntimeConfig())
        d = OkDriver("d1", "test")
        runtime.register_driver(d)
        await runtime.start()
        await runtime.stop()
        assert d.state == DriverState.DISCONNECTED

    async def test_multiple_drivers(self) -> None:
        runtime = Runtime(RuntimeConfig())
        d1 = OkDriver("d1", "test")
        d2 = OkDriver("d2", "test")
        runtime.register_driver(d1)
        runtime.register_driver(d2)
        await runtime.start()
        assert d1.state == DriverState.CONNECTED
        assert d2.state == DriverState.CONNECTED
        status = runtime.status()
        assert status.drivers_connected == 2
        await runtime.stop()


# ---------------------------------------------------------------------------
# Failed Driver Handling
# ---------------------------------------------------------------------------


class TestFailedDriver:
    async def test_connect_failure_continues(self) -> None:
        runtime = Runtime(RuntimeConfig())
        ok = OkDriver("ok", "test")
        bad = FailConnectDriver("bad", "test")
        runtime.register_driver(bad)
        runtime.register_driver(ok)
        await runtime.start()
        assert ok.state == DriverState.CONNECTED
        assert bad.state == DriverState.ERROR
        await runtime.stop()


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class TestMetrics:
    async def test_status_after_start(self) -> None:
        runtime = Runtime(RuntimeConfig())
        d = OkDriver("d1", "test")
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
        d = OkDriver("d1", "test")
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
