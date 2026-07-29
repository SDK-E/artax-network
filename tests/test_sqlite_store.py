"""Tests for SQLiteMemoryStore working memory backend."""

from __future__ import annotations

import asyncio
import os
import tempfile
import time

import pytest

from artax.events.bus import MemoryEventBus
from artax.events.types import EventFilter, EventType
from artax.memory.base import (
    MemoryConfig,
    MemoryFilter,
    MemorySnapshot,
    SQLiteMemoryStore,
)


def _tmp_db() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)  # noqa: SIM115
    tmp.close()
    return tmp.name


def _cleanup(path: str) -> None:
    os.unlink(path)  # noqa: PTH108


def _make_store(**kwargs: object) -> SQLiteMemoryStore:
    path = _tmp_db()
    config = MemoryConfig(sqlite_path=path, **kwargs)
    store = SQLiteMemoryStore(config=config)
    store._tmp_path = path
    return store


class TestStoreAndRetrieve:
    async def test_store_and_retrieve(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("key1", "hello")
        assert await store.retrieve("key1") == "hello"
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_store_various_types(self) -> None:
        store = _make_store()
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
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_retrieve_nonexistent_returns_none(self) -> None:
        store = _make_store()
        await store.start()
        assert await store.retrieve("nope") is None
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_retrieve_wrong_namespace_returns_none(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k", "v", namespace="a")
        assert await store.retrieve("k", namespace="b") is None
        await store.stop()
        _cleanup(store._tmp_path)


class TestOverwrite:
    async def test_overwrite_updates_value(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k", "v1")
        await store.store("k", "v2")
        assert await store.retrieve("k") == "v2"
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_overwrite_preserves_created_at(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k", "v1")

        def _get_created() -> float:
            cur = store._conn.execute(
                "SELECT created_at FROM memory_entries WHERE namespace='default' AND key='k'"
            )
            return cur.fetchone()[0]

        original_created = await asyncio.to_thread(_get_created)
        await asyncio.sleep(0.01)
        await store.store("k", "v2")

        def _get_times() -> tuple[float, float]:
            cur = store._conn.execute(
                "SELECT created_at, updated_at FROM memory_entries "
                "WHERE namespace='default' AND key='k'"
            )
            row = cur.fetchone()
            return row[0], row[1]

        created, updated = await asyncio.to_thread(_get_times)
        assert created == original_created
        assert updated > original_created
        await store.stop()
        _cleanup(store._tmp_path)


class TestTTL:
    async def test_entry_with_ttl_expires(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k", "v", ttl=0.05)
        assert await store.retrieve("k") == "v"
        await asyncio.sleep(0.1)
        assert await store.retrieve("k") is None
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_entry_without_ttl_never_expires(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k", "v")
        assert await store.retrieve("k") == "v"
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_expired_entry_removed_from_storage(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k", "v", ttl=0.05)
        await asyncio.sleep(0.1)
        await store.retrieve("k")
        assert await store.size() == 0
        await store.stop()
        _cleanup(store._tmp_path)


class TestNamespaces:
    async def test_same_key_different_namespaces(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k", "v1", namespace="a")
        await store.store("k", "v2", namespace="b")
        assert await store.retrieve("k", namespace="a") == "v1"
        assert await store.retrieve("k", namespace="b") == "v2"
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_delete_one_namespace_does_not_affect_other(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k", "v1", namespace="a")
        await store.store("k", "v2", namespace="b")
        await store.delete("k", namespace="a")
        assert await store.retrieve("k", namespace="a") is None
        assert await store.retrieve("k", namespace="b") == "v2"
        await store.stop()
        _cleanup(store._tmp_path)


class TestLRUEviction:
    async def test_evicts_oldest_on_capacity(self) -> None:
        store = _make_store(max_entries=3)
        await store.start()
        await store.store("a", 1)
        await store.store("b", 2)
        await store.store("c", 3)
        await store.store("d", 4)
        assert await store.retrieve("a") is None
        assert await store.size() == 3
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_access_refreshes_lru_position(self) -> None:
        store = _make_store(max_entries=3)
        await store.start()
        await store.store("a", 1)
        await store.store("b", 2)
        await store.store("c", 3)
        await store.retrieve("a")
        await store.store("d", 4)
        assert await store.retrieve("a") == 1
        assert await store.retrieve("b") is None
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_overwrite_does_not_count_as_new(self) -> None:
        store = _make_store(max_entries=3)
        await store.start()
        await store.store("a", 1)
        await store.store("b", 2)
        await store.store("c", 3)
        await store.store("a", 10)
        assert await store.size() == 3
        assert await store.retrieve("a") == 10
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_eviction_per_namespace(self) -> None:
        store = _make_store(max_entries=2)
        await store.start()
        await store.store("a", 1, namespace="ns1")
        await store.store("b", 2, namespace="ns1")
        await store.store("c", 3, namespace="ns2")
        await store.store("d", 4, namespace="ns1")
        assert await store.retrieve("a", namespace="ns1") is None
        assert await store.retrieve("b", namespace="ns1") == 2
        assert await store.retrieve("c", namespace="ns2") == 3
        await store.stop()
        _cleanup(store._tmp_path)


class TestQuery:
    async def test_query_namespace_filter(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k1", "v1", namespace="a")
        await store.store("k2", "v2", namespace="b")
        result = await store.query(MemoryFilter(namespace="a"))
        assert result == {"k1": "v1"}
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_query_key_prefix_filter(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("dom.title", "Page", namespace="chromium")
        await store.store("dom.url", "http://x", namespace="chromium")
        await store.store("scheduler.intent", "nav", namespace="scheduler")
        result = await store.query(MemoryFilter(key_prefix="dom."))
        assert result == {"dom.title": "Page", "dom.url": "http://x"}
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_query_value_type_filter(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("s", "text")
        await store.store("i", 42)
        await store.store("l", [1, 2])
        await store.store("d", {"a": 1})
        result = await store.query(MemoryFilter(value_type=str))
        assert result == {"s": "text"}
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_query_sync_predicate(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k1", "hello")
        await store.store("k2", "world")
        result = await store.query(MemoryFilter(predicate=lambda e: e.value.startswith("h")))
        assert result == {"k1": "hello"}
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_query_after_filter(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("old", "v1")

        def _get_ts() -> float:
            cur = store._conn.execute(
                "SELECT updated_at FROM memory_entries WHERE key='old' AND namespace='default'"
            )
            return cur.fetchone()[0]

        ts = await asyncio.to_thread(_get_ts)
        await asyncio.sleep(0.1)
        await store.store("new", "v2")
        result = await store.query(MemoryFilter(after=ts))
        assert result == {"new": "v2"}
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_query_limit(self) -> None:
        store = _make_store()
        await store.start()
        for i in range(10):
            await store.store(f"k{i}", i)
        result = await store.query(MemoryFilter(limit=3))
        assert len(result) == 3
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_query_combined_filters(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("dom.title", "Page", namespace="chromium")
        await store.store("dom.url", "http://x", namespace="chromium")
        await store.store("sched.intent", "nav", namespace="scheduler")
        result = await store.query(MemoryFilter(namespace="chromium", key_prefix="dom."))
        assert len(result) == 2
        assert "dom.title" in result
        assert "dom.url" in result
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_query_empty(self) -> None:
        store = _make_store()
        await store.start()
        result = await store.query(MemoryFilter())
        assert result == {}
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_query_excludes_expired(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k", "v", ttl=0.05)
        await asyncio.sleep(0.1)
        result = await store.query(MemoryFilter())
        assert result == {}
        await store.stop()
        _cleanup(store._tmp_path)


class TestDelete:
    async def test_delete_existing(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k", "v")
        assert await store.delete("k") is True
        assert await store.retrieve("k") is None
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_delete_nonexistent(self) -> None:
        store = _make_store()
        await store.start()
        assert await store.delete("nope") is False
        await store.stop()
        _cleanup(store._tmp_path)


class TestClear:
    async def test_clear_specific_namespace(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k1", "v1", namespace="a")
        await store.store("k2", "v2", namespace="a")
        await store.store("k3", "v3", namespace="b")
        count = await store.clear(namespace="a")
        assert count == 2
        assert await store.size() == 1
        assert await store.retrieve("k3", namespace="b") == "v3"
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_clear_all(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k1", "v1", namespace="a")
        await store.store("k2", "v2", namespace="b")
        count = await store.clear()
        assert count == 2
        assert await store.size() == 0
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_clear_empty_returns_zero(self) -> None:
        store = _make_store()
        await store.start()
        assert await store.clear() == 0
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_clear_nonexistent_namespace_returns_zero(self) -> None:
        store = _make_store()
        await store.start()
        assert await store.clear(namespace="nope") == 0
        await store.stop()
        _cleanup(store._tmp_path)


class TestKeys:
    async def test_keys_returns_correct_keys(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("a", 1, namespace="ns")
        await store.store("b", 2, namespace="ns")
        keys = await store.keys(namespace="ns")
        assert sorted(keys) == ["a", "b"]
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_keys_empty_namespace(self) -> None:
        store = _make_store()
        await store.start()
        keys = await store.keys(namespace="nope")
        assert keys == []
        await store.stop()
        _cleanup(store._tmp_path)


class TestSize:
    async def test_size_per_namespace(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("a", 1, namespace="ns1")
        await store.store("b", 2, namespace="ns1")
        await store.store("c", 3, namespace="ns2")
        assert await store.size(namespace="ns1") == 2
        assert await store.size(namespace="ns2") == 1
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_size_total(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("a", 1, namespace="ns1")
        await store.store("b", 2, namespace="ns2")
        assert await store.size() == 2
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_size_empty(self) -> None:
        store = _make_store()
        await store.start()
        assert await store.size() == 0
        await store.stop()
        _cleanup(store._tmp_path)


class TestSnapshot:
    async def test_snapshot_captures_state(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k1", "v1", namespace="ns")
        snap = await store.snapshot()
        assert isinstance(snap, MemorySnapshot)
        assert snap.version == "0.1"
        assert isinstance(snap.timestamp, float)
        assert "ns" in snap.entries
        assert "k1" in snap.entries["ns"]
        assert snap.entries["ns"]["k1"]["value"] == "v1"
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_snapshot_includes_ttl(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k", "v", ttl=60.0)
        snap = await store.snapshot()
        assert snap.entries["default"]["k"]["ttl"] is not None
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_restore_populates_state(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("k", "v", namespace="ns")
        snap = await store.snapshot()
        await store.stop()
        _cleanup(store._tmp_path)

        store2 = _make_store()
        await store2.start()
        await store2.restore(snap)
        assert await store2.retrieve("k", namespace="ns") == "v"
        assert await store2.size() == 1
        await store2.stop()
        _cleanup(store2._tmp_path)

    async def test_restore_clears_previous_state(self) -> None:
        store = _make_store()
        await store.start()
        await store.store("old", "data")
        snap = MemorySnapshot(
            version="0.1",
            timestamp=time.monotonic(),
            entries={},
        )
        await store.restore(snap)
        assert await store.size() == 0
        await store.stop()
        _cleanup(store._tmp_path)


class TestEvents:
    async def test_event_emitted_on_new_key(self) -> None:
        bus = MemoryEventBus()
        await bus.start()
        received: list = []

        async def handler(event: object) -> None:
            received.append(event)

        await bus.subscribe(EventFilter(type=EventType.MEMORY_UPDATED), handler)

        store = _make_store()
        store._event_bus = bus
        await store.start()
        await store.store("k", "v")
        await bus.drain()

        assert len(received) >= 1
        payload = received[0].payload
        assert payload["event"] == "memory_updated"
        assert payload["key"] == "k"
        await store.stop()
        _cleanup(store._tmp_path)
        await bus.stop()

    async def test_event_emitted_on_eviction(self) -> None:
        bus = MemoryEventBus()
        await bus.start()
        received: list = []

        async def handler(event: object) -> None:
            received.append(event)

        await bus.subscribe(EventFilter(type=EventType.MEMORY_UPDATED), handler)

        store = _make_store(max_entries=2)
        store._event_bus = bus
        await store.start()
        await store.store("a", 1)
        await store.store("b", 2)
        received.clear()
        await store.store("c", 3)
        await bus.drain()

        eviction_events = [e for e in received if e.payload.get("event") == "memory_evicted"]
        assert len(eviction_events) == 1
        await store.stop()
        _cleanup(store._tmp_path)
        await bus.stop()

    async def test_event_emitted_on_clear(self) -> None:
        bus = MemoryEventBus()
        await bus.start()
        received: list = []

        async def handler(event: object) -> None:
            received.append(event)

        await bus.subscribe(EventFilter(type=EventType.MEMORY_UPDATED), handler)

        store = _make_store()
        store._event_bus = bus
        await store.start()
        await store.store("k", "v")
        await bus.drain()
        received.clear()
        await store.clear()
        await bus.drain()

        assert len(received) >= 1
        payload = received[0].payload
        assert payload["event"] == "memory_updated"
        assert payload["operation"] == "clear"
        await store.stop()
        _cleanup(store._tmp_path)
        await bus.stop()


class TestLifecycle:
    async def test_stop_closes_connection(self) -> None:
        store = _make_store()
        await store.start()
        assert store._conn is not None
        await store.stop()
        assert store._conn is None

    async def test_stop_cancels_cleanup_task(self) -> None:
        store = _make_store()
        await store.start()
        assert store._cleanup_task is not None
        assert not store._cleanup_task.done()
        await store.stop()
        assert store._cleanup_task is None

    async def test_cleanup_removes_expired_entries(self) -> None:
        path = _tmp_db()
        config = MemoryConfig(cleanup_interval=0.05, sqlite_path=path)
        store = SQLiteMemoryStore(config=config)
        await store.start()
        await store.store("expires", "v", ttl=0.01)
        await store.store("persists", "v")
        await asyncio.sleep(0.15)
        assert await store.retrieve("expires") is None
        assert await store.size() == 1
        await store.stop()
        _cleanup(path)

    async def test_not_started_raises(self) -> None:
        store = SQLiteMemoryStore()
        cases = [
            ("store", ("x", "y")),
            ("retrieve", ("x",)),
            ("delete", ("x",)),
            ("clear", (None,)),
            ("keys", ("x",)),
            ("size", (None,)),
        ]
        for method, args in cases:
            with pytest.raises(RuntimeError):
                await getattr(store, method)(*args)
        with pytest.raises(RuntimeError):
            await store.query(MemoryFilter())
        with pytest.raises(RuntimeError):
            await store.snapshot()
        snap = MemorySnapshot(version="0.1", timestamp=0.0, entries={})
        with pytest.raises(RuntimeError):
            await store.restore(snap)


class TestPersistence:
    async def test_data_survives_restart(self) -> None:
        path = _tmp_db()
        store = SQLiteMemoryStore(config=MemoryConfig(sqlite_path=path))
        await store.start()
        await store.store("k", "hello", namespace="ns")
        await store.stop()

        store2 = SQLiteMemoryStore(config=MemoryConfig(sqlite_path=path))
        await store2.start()
        assert await store2.retrieve("k", namespace="ns") == "hello"
        await store2.stop()
        _cleanup(path)

    async def test_ttl_reenforced_on_restart(self) -> None:
        path = _tmp_db()
        store = SQLiteMemoryStore(config=MemoryConfig(sqlite_path=path))
        await store.start()
        await store.store("ephemeral", "v", ttl=0.05)
        await store.stop()

        await asyncio.sleep(0.1)

        store2 = SQLiteMemoryStore(config=MemoryConfig(sqlite_path=path))
        await store2.start()
        assert await store2.retrieve("ephemeral") is None
        await store2.stop()
        _cleanup(path)


class TestConcurrency:
    async def test_concurrent_store_retrieve(self) -> None:
        store = _make_store()
        await store.start()

        async def writer(n: int) -> None:
            await store.store(f"k{n}", n)

        async def reader(n: int) -> int | None:
            return await store.retrieve(f"k{n}")

        await asyncio.gather(*(writer(i) for i in range(50)))
        results = await asyncio.gather(*(reader(i) for i in range(50)))
        assert all(results[i] == i for i in range(50))
        await store.stop()
        _cleanup(store._tmp_path)

    async def test_concurrent_mixed_ops(self) -> None:
        store = _make_store()
        await store.start()

        async def op(i: int) -> None:
            await store.store(f"k{i}", i)
            await store.retrieve(f"k{i}")
            await store.delete(f"k{i}")

        await asyncio.gather(*(op(i) for i in range(20)))
        assert await store.size() == 0
        await store.stop()
        _cleanup(store._tmp_path)
