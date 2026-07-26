"""Tests for artax.events.types module."""

from __future__ import annotations

import time
import uuid

import pytest

from artax.events.types import (
    Event,
    EventBusConfig,
    EventBusStats,
    EventFilter,
    EventType,
    SemanticEvent,
)


class TestEventType:
    """Tests for the EventType enum."""

    def test_all_values_exist(self) -> None:
        expected = {
            "dom_changed",
            "page_loaded",
            "page_error",
            "user_input",
            "screenshot_taken",
            "action_requested",
            "action_completed",
            "action_failed",
            "memory_updated",
            "schedule_tick",
            "health_check",
            "runtime_started",
            "runtime_stopping",
            "runtime_error",
            "driver_connected",
            "driver_disconnected",
            "driver_unhealthy",
            "custom",
        }
        actual = {e.value for e in EventType}
        assert actual == expected

    def test_is_str_enum(self) -> None:
        assert isinstance(EventType.DOM_CHANGED, str)
        assert EventType.DOM_CHANGED == "dom_changed"

    def test_serializable(self) -> None:
        assert str(EventType.PAGE_LOADED) == "EventType.PAGE_LOADED"
        assert EventType.PAGE_LOADED.value == "page_loaded"


class TestSemanticEvent:
    """Tests for the SemanticEvent dataclass."""

    def test_create_factory(self) -> None:
        event = SemanticEvent.create(
            type=EventType.DOM_CHANGED,
            source="chromium",
            payload={"selector": "button"},
        )
        assert isinstance(event.event_id, uuid.UUID)
        assert event.type == EventType.DOM_CHANGED
        assert event.source == "chromium"
        assert event.payload == {"selector": "button"}
        assert isinstance(event.timestamp, float)
        assert event.timestamp > 0
        assert event.metadata == {}
        assert event.correlation_id is None

    def test_create_with_metadata(self) -> None:
        meta = {"trace_id": "abc123"}
        event = SemanticEvent.create(
            type=EventType.PAGE_LOADED,
            source="chromium",
            payload={},
            metadata=meta,
        )
        assert event.metadata == meta

    def test_create_with_correlation_id(self) -> None:
        cid = uuid.uuid4()
        event = SemanticEvent.create(
            type=EventType.ACTION_REQUESTED,
            source="scheduler",
            payload={},
            correlation_id=cid,
        )
        assert event.correlation_id == cid

    def test_frozen(self) -> None:
        event = SemanticEvent.create(
            type=EventType.CUSTOM,
            source="test",
            payload={},
        )
        with pytest.raises(AttributeError):
            event.type = EventType.PAGE_LOADED  # type: ignore[misc]

    def test_unique_ids(self) -> None:
        e1 = SemanticEvent.create(type=EventType.CUSTOM, source="test", payload={})
        e2 = SemanticEvent.create(type=EventType.CUSTOM, source="test", payload={})
        assert e1.event_id != e2.event_id

    def test_satisfies_event_protocol(self) -> None:
        event = SemanticEvent.create(
            type=EventType.CUSTOM,
            source="test",
            payload={"key": "value"},
        )
        assert hasattr(event, "event_id")
        assert hasattr(event, "type")
        assert hasattr(event, "source")
        assert hasattr(event, "timestamp")
        assert hasattr(event, "payload")
        assert hasattr(event, "metadata")
        assert hasattr(event, "correlation_id")

    def test_manual_construction(self) -> None:
        eid = uuid.uuid4()
        ts = time.time()
        event = SemanticEvent(
            event_id=eid,
            type=EventType.HEALTH_CHECK,
            source="runtime",
            timestamp=ts,
            payload={"status": "ok"},
            metadata={"v": 1},
            correlation_id=None,
        )
        assert event.event_id == eid
        assert event.timestamp == ts


class TestEventFilter:
    """Tests for EventFilter.matches()."""

    @pytest.fixture
    def dom_event(self) -> SemanticEvent:
        return SemanticEvent.create(
            type=EventType.DOM_CHANGED,
            source="chromium",
            payload={"selector": "button"},
        )

    @pytest.fixture
    def page_event(self) -> SemanticEvent:
        return SemanticEvent.create(
            type=EventType.PAGE_LOADED,
            source="chromium",
            payload={"url": "https://example.com"},
        )

    @pytest.fixture
    def terminal_event(self) -> SemanticEvent:
        return SemanticEvent.create(
            type=EventType.CUSTOM,
            source="terminal",
            payload={"output": "hello"},
        )

    async def test_no_filter_matches_all(self, dom_event: SemanticEvent) -> None:
        f = EventFilter()
        assert await f.matches(dom_event)

    async def test_type_filter_match(self, dom_event: SemanticEvent) -> None:
        f = EventFilter(type=EventType.DOM_CHANGED)
        assert await f.matches(dom_event)

    async def test_type_filter_no_match(self, dom_event: SemanticEvent) -> None:
        f = EventFilter(type=EventType.PAGE_LOADED)
        assert not await f.matches(dom_event)

    async def test_source_exact_match(self, dom_event: SemanticEvent) -> None:
        f = EventFilter(source="chromium")
        assert await f.matches(dom_event)

    async def test_source_exact_no_match(self, dom_event: SemanticEvent) -> None:
        f = EventFilter(source="terminal")
        assert not await f.matches(dom_event)

    async def test_source_wildcard_match(self, dom_event: SemanticEvent) -> None:
        f = EventFilter(source="chromium.*")
        dom_event_source = SemanticEvent.create(
            type=EventType.DOM_CHANGED, source="chromium.dom", payload={}
        )
        assert await f.matches(dom_event_source)

    async def test_source_wildcard_star(self, terminal_event: SemanticEvent) -> None:
        f = EventFilter(source="*")
        assert await f.matches(terminal_event)

    async def test_source_wildcard_no_match(self, terminal_event: SemanticEvent) -> None:
        f = EventFilter(source="chromium.*")
        assert not await f.matches(terminal_event)

    async def test_after_filter_match(self, dom_event: SemanticEvent) -> None:
        f = EventFilter(after=dom_event.timestamp - 1)
        assert await f.matches(dom_event)

    async def test_after_filter_no_match(self, dom_event: SemanticEvent) -> None:
        f = EventFilter(after=dom_event.timestamp + 1)
        assert not await f.matches(dom_event)

    async def test_sync_predicate(self, dom_event: SemanticEvent) -> None:
        f = EventFilter(predicate=lambda e: "button" in e.payload.get("selector", ""))
        assert await f.matches(dom_event)

    async def test_sync_predicate_reject(self, dom_event: SemanticEvent) -> None:
        f = EventFilter(predicate=lambda e: "input" in e.payload.get("selector", ""))
        assert not await f.matches(dom_event)

    async def test_async_predicate(self, dom_event: SemanticEvent) -> None:
        async def check(event: Event) -> bool:
            return event.source == "chromium"

        f = EventFilter(predicate=check)
        assert await f.matches(dom_event)

    async def test_multiple_criteria_and_semantics(
        self, dom_event: SemanticEvent, page_event: SemanticEvent
    ) -> None:
        f = EventFilter(type=EventType.DOM_CHANGED, source="chromium")
        assert await f.matches(dom_event)
        assert not await f.matches(page_event)

    async def test_correlation_id_propagation(self) -> None:
        cid = uuid.uuid4()
        e1 = SemanticEvent.create(
            type=EventType.ACTION_REQUESTED,
            source="scheduler",
            payload={},
            correlation_id=cid,
        )
        e2 = SemanticEvent.create(
            type=EventType.ACTION_COMPLETED,
            source="chromium",
            payload={},
            correlation_id=cid,
        )
        assert e1.correlation_id == e2.correlation_id == cid


class TestEventBusConfig:
    def test_defaults(self) -> None:
        c = EventBusConfig()
        assert c.history_size == 1000
        assert c.max_queue_size == 10000
        assert c.dispatch_timeout == 1.0

    def test_custom(self) -> None:
        c = EventBusConfig(history_size=50, max_queue_size=100, dispatch_timeout=0.5)
        assert c.history_size == 50
        assert c.max_queue_size == 100
        assert c.dispatch_timeout == 0.5


class TestEventBusStats:
    def test_defaults(self) -> None:
        s = EventBusStats()
        assert s.events_published == 0
        assert s.events_delivered == 0
        assert s.subscriptions_active == 0
        assert s.subscriptions_dropped == 0
        assert s.queue_depth == 0

    def test_custom(self) -> None:
        s = EventBusStats(
            events_published=10,
            events_delivered=8,
            subscriptions_active=2,
            subscriptions_dropped=1,
            queue_depth=3,
        )
        assert s.events_published == 10
        assert s.events_delivered == 8
        assert s.subscriptions_active == 2
        assert s.subscriptions_dropped == 1
        assert s.queue_depth == 3
