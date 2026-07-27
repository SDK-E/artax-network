"""Tests for action type definitions."""

from __future__ import annotations

import time

import pytest

from artax.actions.types import Action, ActionResult, Intent
from artax.scheduler.core import Priority


class TestAction:
    def test_create_with_defaults(self) -> None:
        action = Action(name="click")
        assert action.name == "click"
        assert isinstance(action.action_id, str)
        assert len(action.action_id) == 32  # uuid4 hex
        assert action.target is None
        assert action.parameters == {}
        assert isinstance(action.timestamp, float)

    def test_create_with_all_fields(self) -> None:
        action = Action(
            name="navigate",
            action_id="abc123",
            target="https://example.com",
            parameters={"wait_until": "load"},
            timestamp=1.0,
        )
        assert action.action_id == "abc123"
        assert action.target == "https://example.com"
        assert action.parameters == {"wait_until": "load"}
        assert action.timestamp == 1.0

    def test_free_form_names(self) -> None:
        for name in ("click", "type", "scroll", "screenshot", "my_custom_action", ""):
            action = Action(name=name)
            assert action.name == name

    def test_frozen(self) -> None:
        action = Action(name="click")
        with pytest.raises(AttributeError):
            action.name = "other"  # type: ignore[misc]

    def test_unique_ids(self) -> None:
        a1 = Action(name="click")
        a2 = Action(name="click")
        assert a1.action_id != a2.action_id


class TestActionResult:
    def test_success(self) -> None:
        result = ActionResult(action_id="abc", success=True, data={"url": "x"})
        assert result.success is True
        assert result.data == {"url": "x"}
        assert result.error is None
        assert result.duration_ms == 0.0

    def test_failure(self) -> None:
        result = ActionResult(action_id="abc", success=False, error="not found", duration_ms=123.4)
        assert result.success is False
        assert result.error == "not found"
        assert result.duration_ms == 123.4

    def test_frozen(self) -> None:
        result = ActionResult(action_id="abc", success=True)
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]


class TestIntent:
    def test_create(self) -> None:
        a1 = Action(name="click", target="#btn")
        a2 = Action(name="type", target="#input", parameters={"text": "hello"})
        intent = Intent(
            description="Login flow",
            actions=[a1, a2],
            priority=Priority.HIGH,
        )
        assert intent.description == "Login flow"
        assert len(intent.actions) == 2
        assert intent.priority == Priority.HIGH

    def test_defaults(self) -> None:
        intent = Intent(description="test")
        assert intent.actions == []
        assert intent.priority == Priority.MEDIUM

    def test_timestamp_is_monotonic(self) -> None:
        t0 = time.monotonic()
        action = Action(name="click")
        t1 = time.monotonic()
        assert t0 <= action.timestamp <= t1
