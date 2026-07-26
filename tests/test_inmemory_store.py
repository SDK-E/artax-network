"""Tests for InMemoryStore working memory backend."""

from __future__ import annotations

import asyncio
import time

from artax.events.bus import MemoryEventBus
from artax.events.types import EventFilter, EventType
from artax.memory.base import (
    InMemoryStore,
    MemoryConfig,
    MemoryEntry,
    MemoryFilter,
    MemorySnapshot,
)


class TestStoreAndRetrieve:
    """Basic store/retrieve round-trip."""

    async def test_store_and_retrieve(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("key1", "hello")
        assert await store.retrieve("key1") == "hello"

    async def test_store_various_types(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("str", "text")
        await store.store("int", 42)
        await store.store("float", 3.14)
        await store.store("bool", value=True)
        await store.store("list", [1, 2, 3])
        await store.store("dict", {"a": 1})
        assert await store.retrieve("str") == "text"
        assert await store.retrieve("int") == 42
        assert await store.retrieve("float") == 3.14
        assert await store.retrieve("bool") is True
        assert await store.retrieve("list") == [1, 2, 3]
        assert await store.retrieve("dict") == {"a": 1}

    async def test_retrieve_nonexistent_returns_none(self) -> None:
        store = InMemoryStore()
        await store.start()
        assert await store.retrieve("nope") is None

    async def test_retrieve_wrong_namespace_returns_none(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k", "v", namespace="a")
        assert await store.retrieve("k", namespace="b") is None


class TestOverwrite:
    """Store overwrites existing key, updates timestamps."""

    async def test_overwrite_updates_value(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k", "v1")
        await store.store("k", "v2")
        assert await store.retrieve("k") == "v2"

    async def test_overwrite_preserves_created_at(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k", "v1")
        ns = store._storage["default"]
        original_created = ns["k"].created_at
        await asyncio.sleep(0.01)
        await store.store("k", "v2")
        assert ns["k"].created_at == original_created
        assert ns["k"].updated_at > original_created


class TestTTL:
    """Lazy TTL expiration."""

    async def test_entry_with_ttl_expires(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k", "v", ttl=0.05)
        assert await store.retrieve("k") == "v"
        await asyncio.sleep(0.1)
        assert await store.retrieve("k") is None

    async def test_entry_without_ttl_never_expires(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k", "v")
        assert await store.retrieve("k") == "v"

    async def test_expired_entry_removed_from_storage(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k", "v", ttl=0.05)
        await asyncio.sleep(0.1)
        await store.retrieve("k")
        assert await store.size() == 0


class TestNamespaces:
    """Namespace isolation."""

    async def test_same_key_different_namespaces(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k", "v1", namespace="a")
        await store.store("k", "v2", namespace="b")
        assert await store.retrieve("k", namespace="a") == "v1"
        assert await store.retrieve("k", namespace="b") == "v2"

    async def test_delete_one_namespace_does_not_affect_other(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k", "v1", namespace="a")
        await store.store("k", "v2", namespace="b")
        await store.delete("k", namespace="a")
        assert await store.retrieve("k", namespace="a") is None
        assert await store.retrieve("k", namespace="b") == "v2"


class TestLRUEviction:
    """LRU eviction when at capacity."""

    async def test_evicts_oldest_on_capacity(self) -> None:
        config = MemoryConfig(max_entries=3)
        store = InMemoryStore(config=config)
        await store.start()
        await store.store("a", 1)
        await store.store("b", 2)
        await store.store("c", 3)
        await store.store("d", 4)  # should evict "a"
        assert await store.retrieve("a") is None
        assert await store.size() == 3

    async def test_access_refreshes_lru_position(self) -> None:
        config = MemoryConfig(max_entries=3)
        store = InMemoryStore(config=config)
        await store.start()
        await store.store("a", 1)
        await store.store("b", 2)
        await store.store("c", 3)
        await store.retrieve("a")  # refresh "a" to end
        await store.store("d", 4)  # should evict "b" (oldest untouched)
        assert await store.retrieve("a") == 1
        assert await store.retrieve("b") is None

    async def test_overwrite_does_not_count_as_new(self) -> None:
        config = MemoryConfig(max_entries=3)
        store = InMemoryStore(config=config)
        await store.start()
        await store.store("a", 1)
        await store.store("b", 2)
        await store.store("c", 3)
        await store.store("a", 10)  # overwrite, not new — no eviction
        assert await store.size() == 3
        assert await store.retrieve("a") == 10


class TestQuery:
    """Query with various filters."""

    async def test_query_namespace_filter(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k1", "v1", namespace="a")
        await store.store("k2", "v2", namespace="b")
        result = await store.query(MemoryFilter(namespace="a"))
        assert result == {"k1": "v1"}

    async def test_query_key_prefix_filter(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("dom.title", "Page", namespace="chromium")
        await store.store("dom.url", "http://x", namespace="chromium")
        await store.store("scheduler.intent", "nav", namespace="scheduler")
        result = await store.query(MemoryFilter(key_prefix="dom."))
        assert result == {"dom.title": "Page", "dom.url": "http://x"}

    async def test_query_value_type_filter(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("s", "text")
        await store.store("i", 42)
        await store.store("l", [1, 2])
        await store.store("d", {"a": 1})
        result = await store.query(MemoryFilter(value_type=str))
        assert result == {"s": "text"}

    async def test_query_sync_predicate(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k1", "hello")
        await store.store("k2", "world")
        result = await store.query(MemoryFilter(predicate=lambda e: e.value.startswith("h")))
        assert result == {"k1": "hello"}

    async def test_query_async_predicate(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k1", "hello")
        await store.store("k2", "world")

        async def check(entry: MemoryEntry) -> bool:
            return entry.value == "world"

        result = await store.query(MemoryFilter(predicate=check))
        assert result == {"k2": "world"}

    async def test_query_after_filter(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("old", "v1")
        # Use the entry's own updated_at to avoid monotonic clock resolution issues
        old_entry = store._storage["default"]["old"]
        ts = old_entry.updated_at
        await asyncio.sleep(0.1)
        await store.store("new", "v2")
        result = await store.query(MemoryFilter(after=ts))
        assert result == {"new": "v2"}

    async def test_query_limit(self) -> None:
        store = InMemoryStore()
        await store.start()
        for i in range(10):
            await store.store(f"k{i}", i)
        result = await store.query(MemoryFilter(limit=3))
        assert len(result) == 3

    async def test_query_combined_filters(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("dom.title", "Page", namespace="chromium")
        await store.store("dom.url", "http://x", namespace="chromium")
        await store.store("sched.intent", "nav", namespace="scheduler")
        result = await store.query(MemoryFilter(namespace="chromium", key_prefix="dom."))
        assert len(result) == 2
        assert "dom.title" in result
        assert "dom.url" in result

    async def test_query_empty(self) -> None:
        store = InMemoryStore()
        await store.start()
        result = await store.query(MemoryFilter())
        assert result == {}

    async def test_query_excludes_expired(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k", "v", ttl=0.05)
        await asyncio.sleep(0.1)
        result = await store.query(MemoryFilter())
        assert result == {}


class TestDelete:
    """Delete operations."""

    async def test_delete_existing(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k", "v")
        assert await store.delete("k") is True
        assert await store.retrieve("k") is None

    async def test_delete_nonexistent(self) -> None:
        store = InMemoryStore()
        await store.start()
        assert await store.delete("nope") is False


class TestClear:
    """Clear operations."""

    async def test_clear_specific_namespace(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k1", "v1", namespace="a")
        await store.store("k2", "v2", namespace="a")
        await store.store("k3", "v3", namespace="b")
        count = await store.clear(namespace="a")
        assert count == 2
        assert await store.size() == 1
        assert await store.retrieve("k3", namespace="b") == "v3"

    async def test_clear_all(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k1", "v1", namespace="a")
        await store.store("k2", "v2", namespace="b")
        count = await store.clear()
        assert count == 2
        assert await store.size() == 0

    async def test_clear_empty_returns_zero(self) -> None:
        store = InMemoryStore()
        await store.start()
        assert await store.clear() == 0

    async def test_clear_nonexistent_namespace_returns_zero(self) -> None:
        store = InMemoryStore()
        await store.start()
        assert await store.clear(namespace="nope") == 0


class TestKeys:
    """Keys listing."""

    async def test_keys_returns_correct_keys(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("a", 1, namespace="ns")
        await store.store("b", 2, namespace="ns")
        keys = await store.keys(namespace="ns")
        assert sorted(keys) == ["a", "b"]

    async def test_keys_empty_namespace(self) -> None:
        store = InMemoryStore()
        await store.start()
        keys = await store.keys(namespace="nope")
        assert keys == []


class TestSize:
    """Size counting."""

    async def test_size_per_namespace(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("a", 1, namespace="ns1")
        await store.store("b", 2, namespace="ns1")
        await store.store("c", 3, namespace="ns2")
        assert await store.size(namespace="ns1") == 2
        assert await store.size(namespace="ns2") == 1

    async def test_size_total(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("a", 1, namespace="ns1")
        await store.store("b", 2, namespace="ns2")
        assert await store.size() == 2

    async def test_size_empty(self) -> None:
        store = InMemoryStore()
        await store.start()
        assert await store.size() == 0


class TestSnapshot:
    """Snapshot and restore."""

    async def test_snapshot_captures_state(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k1", "v1", namespace="ns")
        snap = await store.snapshot()
        assert isinstance(snap, MemorySnapshot)
        assert snap.version == "0.1"
        assert isinstance(snap.timestamp, float)
        assert "ns" in snap.entries
        assert "k1" in snap.entries["ns"]
        assert snap.entries["ns"]["k1"]["value"] == "v1"

    async def test_snapshot_includes_ttl(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k", "v", ttl=60.0)
        snap = await store.snapshot()
        assert snap.entries["default"]["k"]["ttl"] is not None

    async def test_restore_populates_state(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k", "v", namespace="ns")
        snap = await store.snapshot()

        store2 = InMemoryStore()
        await store2.start()
        await store2.restore(snap)
        assert await store2.retrieve("k", namespace="ns") == "v"
        assert await store2.size() == 1

    async def test_restore_clears_previous_state(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("old", "data")
        snap = MemorySnapshot(
            version="0.1",
            timestamp=time.monotonic(),
            entries={},
        )
        await store.restore(snap)
        assert await store.size() == 0


class TestEvents:
    """Event emission on significant changes."""

    async def test_event_emitted_on_new_key(self) -> None:
        bus = MemoryEventBus()
        await bus.start()
        received: list = []

        async def handler(event: object) -> None:
            received.append(event)

        await bus.subscribe(EventFilter(type=EventType.MEMORY_UPDATED), handler)

        store = InMemoryStore(event_bus=bus)
        await store.start()
        await store.store("k", "v")
        await bus.drain()

        assert len(received) >= 1
        payload = received[0].payload  # type: ignore[union-attr]
        assert payload["event"] == "memory_updated"
        assert payload["key"] == "k"
        await bus.stop()

    async def test_event_emitted_on_eviction(self) -> None:
        bus = MemoryEventBus()
        await bus.start()
        received: list = []

        async def handler(event: object) -> None:
            received.append(event)

        await bus.subscribe(EventFilter(type=EventType.MEMORY_UPDATED), handler)

        config = MemoryConfig(max_entries=2)
        store = InMemoryStore(config=config, event_bus=bus)
        await store.start()
        await store.store("a", 1)
        await store.store("b", 2)
        received.clear()
        await store.store("c", 3)  # evicts "a"
        await bus.drain()

        eviction_events = [
            e
            for e in received
            if e.payload.get("event") == "memory_evicted"  # type: ignore[union-attr]
        ]
        assert len(eviction_events) == 1
        await bus.stop()

    async def test_event_emitted_on_clear(self) -> None:
        bus = MemoryEventBus()
        await bus.start()
        received: list = []

        async def handler(event: object) -> None:
            received.append(event)

        await bus.subscribe(EventFilter(type=EventType.MEMORY_UPDATED), handler)

        store = InMemoryStore(event_bus=bus)
        await store.start()
        await store.store("k", "v")
        await bus.drain()  # let the initial store event finish
        received.clear()
        await store.clear()
        await bus.drain()

        assert len(received) >= 1
        payload = received[0].payload  # type: ignore[union-attr]
        assert payload["event"] == "memory_updated"
        assert payload["operation"] == "clear"
        await bus.stop()


class TestLifecycle:
    """Start/stop lifecycle."""

    async def test_stop_clears_data(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.store("k", "v")
        await store.stop()
        assert await store.size() == 0

    async def test_start_is_noop(self) -> None:
        store = InMemoryStore()
        await store.start()
        await store.start()  # double start is fine
        assert await store.size() == 0


class TestConcurrency:
    """Concurrent operations from multiple coroutines."""

    async def test_concurrent_store_retrieve(self) -> None:
        store = InMemoryStore()
        await store.start()

        async def writer(n: int) -> None:
            await store.store(f"k{n}", n)

        async def reader(n: int) -> int | None:
            return await store.retrieve(f"k{n}")

        await asyncio.gather(*(writer(i) for i in range(50)))
        results = await asyncio.gather(*(reader(i) for i in range(50)))
        assert all(results[i] == i for i in range(50))

    async def test_concurrent_mixed_ops(self) -> None:
        store = InMemoryStore()
        await store.start()

        async def op(i: int) -> None:
            await store.store(f"k{i}", i)
            await store.retrieve(f"k{i}")
            await store.delete(f"k{i}")

        await asyncio.gather(*(op(i) for i in range(20)))
        assert await store.size() == 0
