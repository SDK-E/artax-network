"""Tests for driver API types, protocol, and BaseDriver."""

from __future__ import annotations

import enum
from collections.abc import AsyncIterator
from typing import assert_type

import pytest

from artax.actions.types import Action, ActionResult
from artax.drivers.base import (
    BaseDriver,
    Driver,
    DriverActionError,
    DriverConfig,
    DriverConnectionError,
    DriverError,
    DriverHealth,
    DriverState,
    DriverTimeoutError,
)
from artax.events.bus import MemoryEventBus
from artax.events.types import Event, EventType, SemanticEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(source: str = "test") -> SemanticEvent:
    return SemanticEvent.create(type=EventType.CUSTOM, source=source, payload={})


async def _empty_events() -> AsyncIterator[Event]:
    return
    yield  # pragma: no cover


class StubConfig:
    """Minimal config satisfying DriverConfig protocol."""

    @property
    def driver_type(self) -> str:
        return "test"


class StubDriver(BaseDriver):
    """Minimal concrete driver for testing BaseDriver ABC."""

    def __init__(self, name: str) -> None:
        """Initialize the stub driver."""
        super().__init__(name=name, config=StubConfig())

    async def _do_connect(self) -> None:
        pass

    async def _do_disconnect(self) -> None:
        pass

    async def observe(self) -> AsyncIterator[Event]:
        return _empty_events()

    async def execute(self, action: Action) -> ActionResult:
        return ActionResult(action_id=action.action_id, success=True)


class FailingConnectDriver(BaseDriver):
    """Driver whose _do_connect raises."""

    def __init__(self, name: str) -> None:
        """Initialize the failing connect driver."""
        super().__init__(name=name, config=StubConfig())

    async def _do_connect(self) -> None:
        raise DriverConnectionError("stub", "cannot connect")

    async def _do_disconnect(self) -> None:
        pass

    async def observe(self) -> AsyncIterator[Event]:
        return _empty_events()

    async def execute(self, action: Action) -> ActionResult:
        return ActionResult(action_id=action.action_id, success=False)


class FailingRawConnectDriver(BaseDriver):
    """Driver whose _do_connect raises a non-DriverError."""

    def __init__(self, name: str) -> None:
        """Initialize the failing raw connect driver."""
        super().__init__(name=name, config=StubConfig())

    async def _do_connect(self) -> None:
        raise RuntimeError("something broke")

    async def _do_disconnect(self) -> None:
        pass

    async def observe(self) -> AsyncIterator[Event]:
        return _empty_events()

    async def execute(self, action: Action) -> ActionResult:
        return ActionResult(action_id=action.action_id, success=False)


class FailDisconnectDriver(BaseDriver):
    """Driver whose _do_disconnect raises."""

    def __init__(self, name: str) -> None:
        """Initialize the failing disconnect driver."""
        super().__init__(name=name, config=StubConfig())

    async def _do_connect(self) -> None:
        pass

    async def _do_disconnect(self) -> None:
        raise RuntimeError("disconnect boom")

    async def observe(self) -> AsyncIterator[Event]:
        return _empty_events()

    async def execute(self, action: Action) -> ActionResult:
        return ActionResult(action_id=action.action_id, success=True)


# ---------------------------------------------------------------------------
# DriverState
# ---------------------------------------------------------------------------


class TestDriverState:
    def test_all_values(self) -> None:
        expected = {"disconnected", "connecting", "connected", "unhealthy", "error"}
        assert {s.value for s in DriverState} == expected

    def test_is_enum(self) -> None:
        assert issubclass(DriverState, enum.Enum)

    def test_has_unhealthy(self) -> None:
        assert DriverState.UNHEALTHY.value == "unhealthy"


# ---------------------------------------------------------------------------
# DriverHealth
# ---------------------------------------------------------------------------


class TestDriverHealth:
    def test_defaults(self) -> None:
        h = DriverHealth(state=DriverState.CONNECTED)
        assert h.state == DriverState.CONNECTED
        assert h.message == ""
        assert h.latency_ms == 0.0
        assert h.last_event_at is None
        assert h.error_count == 0

    def test_all_fields(self) -> None:
        h = DriverHealth(
            state=DriverState.UNHEALTHY,
            message="slow",
            latency_ms=42.5,
            last_event_at=100.0,
            error_count=3,
        )
        assert h.state == DriverState.UNHEALTHY
        assert h.message == "slow"
        assert h.latency_ms == 42.5
        assert h.last_event_at == 100.0
        assert h.error_count == 3


# ---------------------------------------------------------------------------
# DriverError hierarchy
# ---------------------------------------------------------------------------


class TestDriverErrors:
    def test_driver_error(self) -> None:
        e = DriverError("my-driver", "something failed")
        assert "my-driver" in str(e)
        assert "something failed" in str(e)

    def test_connection_error(self) -> None:
        e = DriverConnectionError("d", "refused")
        assert isinstance(e, DriverError)

    def test_timeout_error(self) -> None:
        e = DriverTimeoutError("d", "timed out")
        assert isinstance(e, DriverError)

    def test_action_error(self) -> None:
        e = DriverActionError("d", "bad action")
        assert isinstance(e, DriverError)


# ---------------------------------------------------------------------------
# DriverConfig protocol
# ---------------------------------------------------------------------------


class TestDriverConfig:
    def test_protocol_accepts_matching_class(self) -> None:
        class MyConfig:
            @property
            def driver_type(self) -> str:
                return "chromium"

        def accept(cfg: DriverConfig) -> str:
            return cfg.driver_type

        assert accept(MyConfig()) == "chromium"


# ---------------------------------------------------------------------------
# Driver protocol
# ---------------------------------------------------------------------------


class TestDriverProtocol:
    def test_structural_subtyping(self) -> None:
        assert_type(Driver, type)
        assert hasattr(Driver, "name")
        assert hasattr(Driver, "environment")
        assert hasattr(Driver, "is_connected")
        assert hasattr(Driver, "connect")
        assert hasattr(Driver, "disconnect")
        assert hasattr(Driver, "observe")
        assert hasattr(Driver, "execute")
        assert hasattr(Driver, "health_check")


# ---------------------------------------------------------------------------
# BaseDriver
# ---------------------------------------------------------------------------


class TestBaseDriver:
    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            BaseDriver("test", StubConfig())  # type: ignore[abstract]

    def test_concrete_driver(self) -> None:
        d = StubDriver("stub")
        assert d.name == "stub"
        assert d.environment == "test"
        assert d.state == DriverState.DISCONNECTED
        assert d.is_connected is False
        assert d.error_count == 0

    async def test_connect_transitions(self) -> None:
        bus = MemoryEventBus()
        d = StubDriver("stub")
        assert d.state == DriverState.DISCONNECTED
        assert d.is_connected is False
        await d.connect(bus)
        assert d.state == DriverState.CONNECTED
        assert d.is_connected is True

    async def test_disconnect_transitions(self) -> None:
        bus = MemoryEventBus()
        d = StubDriver("stub")
        await d.connect(bus)
        await d.disconnect()
        assert d.state == DriverState.DISCONNECTED
        assert d.is_connected is False

    async def test_disconnect_when_already_disconnected(self) -> None:
        d = StubDriver("stub")
        await d.disconnect()
        assert d.state == DriverState.DISCONNECTED
        assert d.is_connected is False

    async def test_connect_failure_sets_error(self) -> None:
        bus = MemoryEventBus()
        d = FailingConnectDriver("fail")
        with pytest.raises(DriverConnectionError):
            await d.connect(bus)
        assert d.state == DriverState.ERROR
        assert d.error_count == 1
        assert d.is_connected is False

    async def test_raw_exception_wrapped(self) -> None:
        bus = MemoryEventBus()
        d = FailingRawConnectDriver("fail")
        with pytest.raises(DriverError):
            await d.connect(bus)
        assert d.state == DriverState.ERROR
        assert d.error_count == 1

    async def test_disconnect_error_still_disconnects(self) -> None:
        bus = MemoryEventBus()
        d = FailDisconnectDriver("fail")
        await d.connect(bus)
        await d.disconnect()
        assert d.state == DriverState.DISCONNECTED
        assert d.is_connected is False

    async def test_health_check(self) -> None:
        bus = MemoryEventBus()
        d = StubDriver("stub")
        await d.connect(bus)
        h = await d.health_check()
        assert h.state == DriverState.CONNECTED
        assert h.error_count == 0

    async def test_execute(self) -> None:
        d = StubDriver("stub")
        action = Action(name="click")
        result = await d.execute(action)
        assert result.success is True
        assert result.action_id == action.action_id

    async def test_observe_returns_async_iterator(self) -> None:
        d = StubDriver("stub")
        iterator = await d.observe()
        events = [e async for e in iterator]
        assert events == []

    async def test_publish_event_when_connected(self) -> None:
        bus = MemoryEventBus()
        d = StubDriver("stub")
        await d.connect(bus)
        event = _make_event()
        await d._publish_event(event)
        await bus.drain()
        assert bus.stats().events_published == 1

    async def test_publish_event_when_disconnected(self) -> None:
        d = StubDriver("stub")
        event = _make_event()
        await d._publish_event(event)  # should not raise

    async def test_event_bus_cleared_on_disconnect(self) -> None:
        bus = MemoryEventBus()
        d = StubDriver("stub")
        await d.connect(bus)
        await d.disconnect()
        assert d._event_bus is None
