"""Tests for artax.memory.base type definitions."""

from __future__ import annotations

import time

import pytest

from artax.memory.base import (
    MemoryConfig,
    MemoryEntry,
    MemoryFilter,
    MemorySnapshot,
)


class TestMemoryConfig:
    """Tests for the MemoryConfig dataclass."""

    def test_defaults(self) -> None:
        c = MemoryConfig()
        assert c.backend == "memory"
        assert c.max_entries == 10000
        assert c.default_ttl is None
        assert c.cleanup_interval == 60.0
        assert c.sqlite_path == "artax_memory.db"
        assert c.redis_url == "redis://localhost:6379"

    def test_custom(self) -> None:
        c = MemoryConfig(
            backend="sqlite",
            max_entries=500,
            default_ttl=30.0,
            cleanup_interval=10.0,
            sqlite_path="data/test.db",
            redis_url="redis://remote:6380",
        )
        assert c.backend == "sqlite"
        assert c.max_entries == 500
        assert c.default_ttl == 30.0
        assert c.cleanup_interval == 10.0
        assert c.sqlite_path == "data/test.db"
        assert c.redis_url == "redis://remote:6380"

    def test_mutable(self) -> None:
        c = MemoryConfig()
        c.max_entries = 999
        assert c.max_entries == 999


class TestMemoryEntry:
    """Tests for the MemoryEntry frozen dataclass."""

    def test_creation(self) -> None:
        now = time.monotonic()
        e = MemoryEntry(
            key="dom.title",
            value="Example",
            namespace="chromium",
            created_at=now,
            updated_at=now,
            ttl=None,
        )
        assert e.key == "dom.title"
        assert e.value == "Example"
        assert e.namespace == "chromium"
        assert e.created_at == now
        assert e.updated_at == now
        assert e.ttl is None

    def test_creation_with_ttl(self) -> None:
        now = time.monotonic()
        e = MemoryEntry(
            key="k",
            value=42,
            namespace="ns",
            created_at=now,
            updated_at=now,
            ttl=now + 60.0,
        )
        assert e.ttl == now + 60.0

    def test_frozen(self) -> None:
        e = MemoryEntry(
            key="k",
            value="v",
            namespace="ns",
            created_at=0.0,
            updated_at=0.0,
            ttl=None,
        )
        with pytest.raises(AttributeError):
            e.key = "other"  # type: ignore[misc]

    def test_value_types(self) -> None:
        now = time.monotonic()
        for val in ["str", 42, 3.14, True, None, [1, 2], {"a": 1}]:
            e = MemoryEntry(
                key="k",
                value=val,
                namespace="ns",
                created_at=now,
                updated_at=now,
                ttl=None,
            )
            assert e.value == val


class TestMemoryFilter:
    """Tests for the MemoryFilter frozen dataclass."""

    def test_defaults(self) -> None:
        f = MemoryFilter()
        assert f.namespace is None
        assert f.key_prefix is None
        assert f.value_type is None
        assert f.predicate is None
        assert f.after is None
        assert f.limit is None

    def test_with_values(self) -> None:
        def check(entry: MemoryEntry) -> bool:
            return entry.key.startswith("dom")

        f = MemoryFilter(
            namespace="chromium",
            key_prefix="dom.",
            value_type=dict,
            predicate=check,
            after=100.0,
            limit=5,
        )
        assert f.namespace == "chromium"
        assert f.key_prefix == "dom."
        assert f.value_type is dict
        assert f.predicate is check
        assert f.after == 100.0
        assert f.limit == 5

    def test_frozen(self) -> None:
        f = MemoryFilter()
        with pytest.raises(AttributeError):
            f.limit = 10  # type: ignore[misc]


class TestMemorySnapshot:
    """Tests for the MemorySnapshot frozen dataclass."""

    def test_fields(self) -> None:
        s = MemorySnapshot(
            version="0.1",
            timestamp=1234567890.0,
            entries={
                "chromium": {
                    "dom.title": {
                        "value": "Example",
                        "created_at": 1.0,
                        "ttl": None,
                        "namespace": "chromium",
                    }
                }
            },
        )
        assert s.version == "0.1"
        assert s.timestamp == 1234567890.0
        assert "chromium" in s.entries
        assert "dom.title" in s.entries["chromium"]

    def test_empty_entries(self) -> None:
        s = MemorySnapshot(version="0.1", timestamp=0.0, entries={})
        assert s.entries == {}

    def test_frozen(self) -> None:
        s = MemorySnapshot(version="0.1", timestamp=0.0, entries={})
        with pytest.raises(AttributeError):
            s.version = "0.2"  # type: ignore[misc]

    def test_nested_mutation_possible(self) -> None:
        """Frozen only prevents field reassignment, not dict mutation."""
        s = MemorySnapshot(version="0.1", timestamp=0.0, entries={})
        s.entries["ns"] = {"key": {"value": "v"}}
        assert s.entries["ns"]["key"]["value"] == "v"
