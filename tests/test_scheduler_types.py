"""Tests for scheduler type definitions."""

from __future__ import annotations

from artax.scheduler.core import (
    Priority,
    SchedulerConfig,
    SchedulerStatus,
    ScheduleStatus,
)


class TestPriority:
    def test_ordering(self) -> None:
        assert Priority.URGENT < Priority.HIGH < Priority.MEDIUM < Priority.LOW

    def test_int_values(self) -> None:
        assert Priority.URGENT == 0
        assert Priority.HIGH == 1
        assert Priority.MEDIUM == 2
        assert Priority.LOW == 3

    def test_is_int_enum(self) -> None:
        assert isinstance(Priority.URGENT, int)


class TestScheduleStatus:
    def test_values(self) -> None:
        assert ScheduleStatus.PENDING == "pending"
        assert ScheduleStatus.DELIVERED == "delivered"
        assert ScheduleStatus.CANCELLED == "cancelled"

    def test_is_str_enum(self) -> None:
        assert isinstance(ScheduleStatus.PENDING, str)


class TestSchedulerConfig:
    def test_defaults(self) -> None:
        c = SchedulerConfig()
        assert c.tick_interval_ms == 10
        assert c.max_queue_size == 10000
        assert c.emergency_drain is True
        assert c.queue_depth_threshold == 1000

    def test_custom(self) -> None:
        c = SchedulerConfig(tick_interval_ms=50, max_queue_size=500, emergency_drain=False)
        assert c.tick_interval_ms == 50
        assert c.max_queue_size == 500
        assert c.emergency_drain is False


class TestSchedulerStatus:
    def test_defaults(self) -> None:
        s = SchedulerStatus()
        assert s.paused is False
        assert s.total_pending == 0
        assert s.total_scheduled == 0
        assert s.total_delivered == 0
        assert s.total_cancelled == 0
        assert s.tick_count == 0
