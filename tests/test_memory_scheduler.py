"""Tests for MemoryScheduler implementation."""

from __future__ import annotations

from artax.events.bus import MemoryEventBus
from artax.events.types import EventFilter, EventType, SemanticEvent
from artax.scheduler.core import (
    MemoryScheduler,
    Priority,
    SchedulerConfig,
)


def _make_event(source: str = "test", **payload: object) -> SemanticEvent:
    return SemanticEvent.create(
        type=EventType.CUSTOM,
        source=source,
        payload=payload,
    )


class TestSchedule:
    def setup_method(self) -> None:
        self.bus = MemoryEventBus()
        self.config = SchedulerConfig()
        self.scheduler = MemoryScheduler(config=self.config, event_bus=self.bus)

    def test_schedule_returns_id(self) -> None:
        event = _make_event()
        entry_id = self.scheduler.schedule(event)
        assert isinstance(entry_id, str)
        assert len(entry_id) > 0

    def test_schedule_with_priority(self) -> None:
        event = _make_event()
        entry_id = self.scheduler.schedule(event, priority=Priority.HIGH)
        assert entry_id != ""

    def test_schedule_with_delay(self) -> None:
        event = _make_event()
        entry_id = self.scheduler.schedule(event, delay=1.0)
        assert entry_id != ""
        # Should not be deliverable immediately
        assert self.scheduler.pending_count == 1

    def test_pending_count(self) -> None:
        assert self.scheduler.pending_count == 0
        self.scheduler.schedule(_make_event())
        assert self.scheduler.pending_count == 1
        self.scheduler.schedule(_make_event())
        assert self.scheduler.pending_count == 2


class TestTick:
    def setup_method(self) -> None:
        self.bus = MemoryEventBus()
        self.config = SchedulerConfig()
        self.scheduler = MemoryScheduler(config=self.config, event_bus=self.bus)
        self.received: list = []

    async def _handler(self, event: object) -> None:
        self.received.append(event)

    async def test_tick_delivers_ready_events(self) -> None:
        await self.bus.start()
        await self.bus.subscribe(EventFilter(), self._handler)

        event = _make_event(val=1)
        self.scheduler.schedule(event)
        await self.scheduler.tick()
        await self.bus.drain()

        custom = [e for e in self.received if e.payload.get("val") == 1]  # type: ignore[union-attr]
        assert len(custom) == 1
        await self.bus.stop()

    async def test_tick_skips_future_events(self) -> None:
        await self.bus.start()
        await self.bus.subscribe(EventFilter(), self._handler)

        event = _make_event(val=1)
        self.scheduler.schedule(event, delay=10.0)
        await self.scheduler.tick()
        await self.bus.drain()

        custom = [e for e in self.received if e.payload.get("val") == 1]  # type: ignore[union-attr]
        assert len(custom) == 0
        await self.bus.stop()

    async def test_tick_priority_ordering(self) -> None:
        await self.bus.start()
        await self.bus.subscribe(EventFilter(), self._handler)

        low = _make_event(val="low")
        urgent = _make_event(val="urgent")
        med = _make_event(val="med")
        high = _make_event(val="high")

        self.scheduler.schedule(low, priority=Priority.LOW)
        self.scheduler.schedule(urgent, priority=Priority.URGENT)
        self.scheduler.schedule(med, priority=Priority.MEDIUM)
        self.scheduler.schedule(high, priority=Priority.HIGH)

        await self.scheduler.tick()
        await self.bus.drain()

        vals = [e.payload.get("val") for e in self.received if hasattr(e, "payload")]  # type: ignore[union-attr]
        custom_vals = [v for v in vals if v in ("urgent", "high", "med", "low")]
        assert custom_vals == ["urgent", "high", "med", "low"]
        await self.bus.stop()

    async def test_tick_when_paused_does_nothing(self) -> None:
        self.scheduler.schedule(_make_event())
        self.scheduler.pause()
        await self.scheduler.tick()
        assert self.scheduler.pending_count == 1

    async def test_tick_increments_count(self) -> None:
        await self.scheduler.tick()
        assert self.scheduler.queue_status().tick_count == 1
        await self.scheduler.tick()
        assert self.scheduler.queue_status().tick_count == 2


class TestCancel:
    def setup_method(self) -> None:
        self.bus = MemoryEventBus()
        self.config = SchedulerConfig()
        self.scheduler = MemoryScheduler(config=self.config, event_bus=self.bus)

    def test_cancel_existing(self) -> None:
        entry_id = self.scheduler.schedule(_make_event())
        assert self.scheduler.cancel(entry_id) is True

    def test_cancel_nonexistent(self) -> None:
        assert self.scheduler.cancel("nope") is False

    async def test_cancelled_not_delivered(self) -> None:
        entry_id = self.scheduler.schedule(_make_event())
        self.scheduler.cancel(entry_id)
        await self.scheduler.tick()
        assert self.scheduler.queue_status().total_delivered == 0

    def test_cancel_tracks_stats(self) -> None:
        entry_id = self.scheduler.schedule(_make_event())
        self.scheduler.cancel(entry_id)
        status = self.scheduler.queue_status()
        assert status.total_cancelled == 1


class TestPauseResume:
    def setup_method(self) -> None:
        self.bus = MemoryEventBus()
        self.config = SchedulerConfig()
        self.scheduler = MemoryScheduler(config=self.config, event_bus=self.bus)

    async def test_pause_stops_delivery(self) -> None:
        self.scheduler.schedule(_make_event())
        self.scheduler.pause()
        await self.scheduler.tick()
        assert self.scheduler.pending_count == 1

    async def test_resume_allows_delivery(self) -> None:
        self.scheduler.schedule(_make_event())
        self.scheduler.pause()
        await self.scheduler.tick()
        self.scheduler.resume()
        await self.scheduler.tick()
        assert self.scheduler.pending_count == 0
        assert self.scheduler.queue_status().total_delivered == 1

    async def test_pause_preserves_events(self) -> None:
        self.scheduler.schedule(_make_event(val=1))
        self.scheduler.schedule(_make_event(val=2))
        self.scheduler.pause()
        await self.scheduler.tick()
        self.scheduler.resume()
        await self.scheduler.tick()
        assert self.scheduler.pending_count == 0
        assert self.scheduler.queue_status().total_delivered == 2

    def test_is_paused_property(self) -> None:
        assert self.scheduler.is_paused is False
        self.scheduler.pause()
        assert self.scheduler.is_paused is True
        self.scheduler.resume()
        assert self.scheduler.is_paused is False


class TestQueueFull:
    def test_queue_full_returns_empty_string(self) -> None:
        bus = MemoryEventBus()
        config = SchedulerConfig(max_queue_size=2)
        scheduler = MemoryScheduler(config=config, event_bus=bus)
        scheduler.schedule(_make_event())
        scheduler.schedule(_make_event())
        result = scheduler.schedule(_make_event())
        assert result == ""


class TestEmergencyDrain:
    async def test_stop_delivers_all(self) -> None:
        bus = MemoryEventBus()
        config = SchedulerConfig(emergency_drain=True)
        scheduler = MemoryScheduler(config=config, event_bus=bus)
        scheduler.schedule(_make_event(val=1))
        scheduler.schedule(_make_event(val=2))
        scheduler.schedule(_make_event(val=3))
        await scheduler.stop()
        assert scheduler.queue_status().total_delivered == 3

    async def test_stop_without_drain_cancels(self) -> None:
        bus = MemoryEventBus()
        config = SchedulerConfig(emergency_drain=False)
        scheduler = MemoryScheduler(config=config, event_bus=bus)
        scheduler.schedule(_make_event())
        await scheduler.stop()
        assert scheduler.queue_status().total_delivered == 0


class TestQueueStatus:
    def test_status_accurate(self) -> None:
        bus = MemoryEventBus()
        config = SchedulerConfig()
        scheduler = MemoryScheduler(config=config, event_bus=bus)
        scheduler.schedule(_make_event(), priority=Priority.URGENT)
        scheduler.schedule(_make_event(), priority=Priority.HIGH)
        scheduler.schedule(_make_event(), priority=Priority.HIGH)
        scheduler.schedule(_make_event(), priority=Priority.LOW)

        status = scheduler.queue_status()
        assert status.pending_urgent == 1
        assert status.pending_high == 2
        assert status.pending_low == 1
        assert status.total_pending == 4
        assert status.total_scheduled == 4
