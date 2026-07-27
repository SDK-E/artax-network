"""Tests for driver API types, protocol, and BaseDriver."""

from __future__ import annotations

import enum
from collections.abc import AsyncGenerator, AsyncIterator
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
from artax.events.types import Event, EventType, SemanticEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(source: str = "test") -> SemanticEvent:
    return SemanticEvent.create(type=EventType.CUSTOM, source=source, payload={})


async def _empty_events() -> AsyncGenerator[Event, None]:
    """Empty async iterator for test stubs."""
    return
    yield  # pragma: no cover


class StubDriver(BaseDriver):
    """Minimal concrete driver for testing BaseDriver ABC."""

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
        assert e.driver == "my-driver"
        assert e.recoverable is True
        assert "my-driver" in str(e)

    def test_driver_error_irrecoverable(self) -> None:
        e = DriverError("d", "boom", recoverable=False)
        assert e.recoverable is False

    def test_connection_error(self) -> None:
        e = DriverConnectionError("d", "refused")
        assert isinstance(e, DriverError)
        assert e.recoverable is False

    def test_timeout_error(self) -> None:
        e = DriverTimeoutError("d", "timed out")
        assert isinstance(e, DriverError)
        assert e.recoverable is True

    def test_action_error(self) -> None:
        e = DriverActionError("d", "bad action")
        assert isinstance(e, DriverError)
        assert e.recoverable is True


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
        # The Protocol itself can't be instantiated, but structural checks
        # confirm it exists as a typing.Protocol
        assert hasattr(Driver, "name")
        assert hasattr(Driver, "state")
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
            BaseDriver("test", "test")  # type: ignore[abstract]

    def test_concrete_driver(self) -> None:
        d = StubDriver("stub", "test")
        assert d.name == "stub"
        assert d.driver_type == "test"
        assert d.state == DriverState.DISCONNECTED
        assert d.error_count == 0

    async def test_connect_transitions(self) -> None:
        d = StubDriver("stub", "test")
        assert d.state == DriverState.DISCONNECTED
        await d.connect()
        assert d.state == DriverState.CONNECTED

    async def test_disconnect_transitions(self) -> None:
        d = StubDriver("stub", "test")
        await d.connect()
        await d.disconnect()
        assert d.state == DriverState.DISCONNECTED

    async def test_disconnect_when_already_disconnected(self) -> None:
        d = StubDriver("stub", "test")
        await d.disconnect()
        assert d.state == DriverState.DISCONNECTED

    async def test_connect_failure_sets_error(self) -> None:
        d = FailingConnectDriver("fail", "test")
        with pytest.raises(DriverConnectionError):
            await d.connect()
        assert d.state == DriverState.ERROR
        assert d.error_count == 1

    async def test_raw_exception_wrapped(self) -> None:
        d = FailingRawConnectDriver("fail", "test")
        with pytest.raises(DriverError):
            await d.connect()
        assert d.state == DriverState.ERROR
        assert d.error_count == 1

    async def test_disconnect_error_still_disconnects(self) -> None:
        d = FailDisconnectDriver("fail", "test")
        await d.connect()
        await d.disconnect()
        assert d.state == DriverState.DISCONNECTED

    async def test_health_check(self) -> None:
        d = StubDriver("stub", "test")
        await d.connect()
        h = await d.health_check()
        assert h.state == DriverState.CONNECTED
        assert h.error_count == 0

    async def test_execute(self) -> None:
        d = StubDriver("stub", "test")
        action = Action(name="click")
        result = await d.execute(action)
        assert result.success is True
        assert result.action_id == action.action_id

    async def test_observe_returns_async_iterator(self) -> None:
        d = StubDriver("stub", "test")
        iterator = await d.observe()
        events = [e async for e in iterator]
        assert events == []
