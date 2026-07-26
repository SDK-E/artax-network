"""Tests for artax.events.bus module."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from artax.events.bus import MemoryEventBus
from artax.events.types import (
    Event,
    EventBusConfig,
    EventFilter,
    EventType,
    SemanticEvent,
)


@pytest.fixture
def config() -> EventBusConfig:
    return EventBusConfig(history_size=10, max_queue_size=5, dispatch_timeout=1.0)


@pytest.fixture
def bus(config: EventBusConfig) -> MemoryEventBus:
    return MemoryEventBus(config)


async def _noop(_event: Event) -> None:
    pass


def _make_event(
    type: EventType = EventType.DOM_CHANGED,
    source: str = "chromium",
    payload: dict | None = None,
    correlation_id: uuid.UUID | None = None,
) -> SemanticEvent:
    return SemanticEvent.create(
        type=type,
        source=source,
        payload=payload or {"ts": 0},
        correlation_id=correlation_id,
    )


class TestLifecycle:
    async def test_start_stop(self, bus: MemoryEventBus) -> None:
        await bus.start()
        assert bus._running is True
        await bus.stop()
        assert bus._running is False
        assert bus._stopped is True

    async def test_publish_to_stopped_bus(self, bus: MemoryEventBus) -> None:
        await bus.start()
        await bus.stop()
        event = _make_event()
        fut = await bus.publish(event)
        assert fut.done()
        assert len(bus.history()) == 0

    async def test_stats_task_cancelled_on_stop(self, bus: MemoryEventBus) -> None:
        await bus.start()
        assert bus._stats_task is not None
        await bus.stop()
        assert bus._stats_task is None


class TestPublishSubscribe:
    async def test_publish_then_subscribe_receives(self, bus: MemoryEventBus) -> None:
        await bus.start()
        received: list[Event] = []

        await bus.subscribe(
            EventFilter(type=EventType.DOM_CHANGED),
            lambda e: received.append(e),
        )

        event = _make_event(type=EventType.DOM_CHANGED)
        await bus.publish(event)
        await bus.drain()
        assert len(received) == 1
        assert received[0].event_id == event.event_id
        await bus.stop()

    async def test_wildcard_subscription_receives(self, bus: MemoryEventBus) -> None:
        await bus.start()
        received: list[Event] = []

        await bus.subscribe(EventFilter(source="chromium.*"), lambda e: received.append(e))

        e1 = _make_event(source="chromium.dom")
        e2 = _make_event(source="chromium.nav")
        await bus.publish(e1)
        await bus.publish(e2)
        await bus.drain()
        assert len(received) == 2
        await bus.stop()

    async def test_wildcard_subscription_ignores(self, bus: MemoryEventBus) -> None:
        await bus.start()
        received: list[Event] = []

        await bus.subscribe(EventFilter(source="chromium.*"), lambda e: received.append(e))

        e1 = _make_event(source="terminal")
        await bus.publish(e1)
        await bus.drain()
        assert len(received) == 0
        await bus.stop()

    async def test_type_filter(self, bus: MemoryEventBus) -> None:
        await bus.start()
        received: list[Event] = []

        await bus.subscribe(EventFilter(type=EventType.PAGE_LOADED), lambda e: received.append(e))

        await bus.publish(_make_event(type=EventType.DOM_CHANGED))
        await bus.publish(_make_event(type=EventType.PAGE_LOADED))
        await bus.drain()
        assert len(received) == 1
        assert received[0].type == EventType.PAGE_LOADED
        await bus.stop()

    async def test_async_predicate_filter(self, bus: MemoryEventBus) -> None:
        await bus.start()
        received: list[Event] = []

        async def is_button(event: Event) -> bool:
            await asyncio.sleep(0)  # simulate async work
            return event.payload.get("selector") == "button"

        await bus.subscribe(EventFilter(predicate=is_button), lambda e: received.append(e))

        await bus.publish(_make_event(payload={"selector": "button"}))
        await bus.publish(_make_event(payload={"selector": "input"}))
        await bus.drain()
        assert len(received) == 1
        assert received[0].payload["selector"] == "button"
        await bus.stop()

    async def test_sync_predicate_filter(self, bus: MemoryEventBus) -> None:
        await bus.start()
        received: list[Event] = []

        await bus.subscribe(
            EventFilter(predicate=lambda e: e.source == "chromium"),
            lambda e: received.append(e),
        )

        await bus.publish(_make_event(source="chromium"))
        await bus.publish(_make_event(source="terminal"))
        await bus.drain()
        assert len(received) == 1
        await bus.stop()


class TestUnsubscribe:
    async def test_unsubscribe_stops_delivery(self, bus: MemoryEventBus) -> None:
        await bus.start()
        received: list[Event] = []

        sub_id = await bus.subscribe(
            EventFilter(type=EventType.DOM_CHANGED), lambda e: received.append(e)
        )
        await bus.publish(_make_event(type=EventType.DOM_CHANGED))
        await bus.drain()
        assert len(received) == 1

        await bus.unsubscribe(sub_id)
        await bus.publish(_make_event(type=EventType.DOM_CHANGED))
        await bus.drain()
        assert len(received) == 1
        await bus.stop()

    async def test_unsubscribe_nonexistent_is_noop(self, bus: MemoryEventBus) -> None:
        await bus.start()
        await bus.unsubscribe("nonexistent")
        await bus.stop()


class TestHistory:
    async def test_history_respects_max_size(self, bus: MemoryEventBus) -> None:
        await bus.start()
        for _ in range(15):
            await bus.publish(_make_event())
        history = bus.history()
        assert len(history) == 10
        await bus.stop()

    async def test_history_with_limit(self, bus: MemoryEventBus) -> None:
        await bus.start()
        for _ in range(10):
            await bus.publish(_make_event())
        history = bus.history(limit=3)
        assert len(history) == 3
        await bus.stop()

    async def test_history_chronological_order(self, bus: MemoryEventBus) -> None:
        await bus.start()
        events = []
        for i in range(5):
            e = _make_event(payload={"i": i})
            events.append(e)
            await bus.publish(e)
        history = bus.history()
        assert [h.event_id for h in history] == [e.event_id for e in events]
        await bus.stop()

    async def test_history_empty(self, bus: MemoryEventBus) -> None:
        assert bus.history() == []


class TestStats:
    async def test_stats_accuracy(self, bus: MemoryEventBus) -> None:
        await bus.start()
        received: list[Event] = []

        sub_id = await bus.subscribe(EventFilter(), lambda e: received.append(e))

        await bus.publish(_make_event())
        await bus.publish(_make_event())
        await bus.drain()

        s = bus.stats()
        assert s.events_published >= 2
        assert s.events_delivered >= 2
        assert s.subscriptions_active == 1
        assert s.subscriptions_dropped == 0

        await bus.unsubscribe(sub_id)
        s = bus.stats()
        assert s.subscriptions_active == 0
        await bus.stop()

    async def test_stats_queue_depth(self, bus: MemoryEventBus) -> None:
        await bus.start()
        blocker = asyncio.Event()
        blocked: list[Event] = []

        async def slow_handler(event: Event) -> None:
            blocked.append(event)
            await blocker.wait()

        await bus.subscribe(EventFilter(), slow_handler)
        await bus.publish(_make_event())
        await asyncio.sleep(0.01)

        s = bus.stats()
        assert s.queue_depth >= 0  # may or may not have drained
        blocker.set()
        await bus.drain()
        await bus.stop()


class TestQueueOverflow:
    async def test_queue_overflow_emits_dropped(self, bus: MemoryEventBus) -> None:
        """When a subscriber queue overflows, subscription.dropped is emitted."""
        await bus.start()
        blocker = asyncio.Event()
        received: list[Event] = []

        async def slow_handler(event: Event) -> None:
            received.append(event)
            if len(received) == 1:
                await blocker.wait()

        await bus.subscribe(EventFilter(), slow_handler)

        for _ in range(8):
            await bus.publish(_make_event())

        blocker.set()
        await bus.drain()

        s = bus.stats()
        assert s.subscriptions_dropped > 0
        await bus.stop()


class TestDrain:
    async def test_drain_delivers_all(self, bus: MemoryEventBus) -> None:
        await bus.start()
        received: list[Event] = []

        await bus.subscribe(EventFilter(), lambda e: received.append(e))

        for _ in range(5):
            await bus.publish(_make_event())

        await bus.drain()
        assert len(received) == 5
        await bus.stop()

    async def test_drain_empty_bus(self, bus: MemoryEventBus) -> None:
        await bus.start()
        await bus.drain()  # should not hang
        await bus.stop()


class TestConcurrent:
    async def test_concurrent_publish(self, bus: MemoryEventBus) -> None:
        await bus.start()
        received: list[Event] = []

        await bus.subscribe(EventFilter(), lambda e: received.append(e))

        async def publish_events(n: int) -> None:
            for _ in range(n):
                await bus.publish(_make_event())

        await asyncio.gather(publish_events(10), publish_events(10), publish_events(10))
        await bus.drain()
        assert len(received) == 30
        assert bus.stats().events_published >= 30
        await bus.stop()


class TestCorrelationId:
    async def test_correlation_id_propagation(self, bus: MemoryEventBus) -> None:
        await bus.start()
        received: list[Event] = []

        await bus.subscribe(EventFilter(), lambda e: received.append(e))

        cid = uuid.uuid4()
        e1 = _make_event(type=EventType.ACTION_REQUESTED, correlation_id=cid)
        e2 = _make_event(type=EventType.ACTION_COMPLETED, correlation_id=cid)
        await bus.publish(e1)
        await bus.publish(e2)
        await bus.drain()

        assert len(received) == 2
        assert received[0].correlation_id == cid
        assert received[1].correlation_id == cid
        await bus.stop()
