"""Working memory protocol and storage backends.

Working memory provides transient, queryable key-value storage for runtime
state. Multiple backends are supported: in-process dicts, SQLite for
persistence, and Redis for distributed coordination.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


class MemoryFilter:
    """Filter criteria for querying working memory entries.

    Attributes:
        prefix: If set, only keys starting with this prefix are returned.
        event_type: If set, only entries associated with this event type are returned.
        after: If set, only entries created after this datetime are returned.
        before: If set, only entries created before this datetime are returned.
        limit: Maximum number of entries to return. Zero means no limit.

    """

    def __init__(
        self,
        prefix: str | None = None,
        event_type: str | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int = 0,
    ) -> None:
        """Initialize the memory filter.

        Args:
            prefix: Key prefix filter.
            event_type: Event type association filter.
            after: Lower bound timestamp filter.
            before: Upper bound timestamp filter.
            limit: Maximum results to return.

        """
        self.prefix = prefix
        self.event_type = event_type
        self.after = after
        self.before = before
        self.limit = limit


@dataclass(frozen=True)
class MemoryEntry:
    """A single record in working memory.

    Attributes:
        key: The storage key (hierarchical keys use ``/`` separators).
        value: Arbitrary stored value.
        event_type: The event type that produced this entry, if any.
        timestamp: UTC timestamp of when this entry was stored.
        metadata: Additional annotations on this entry.

    """

    key: str
    value: Any
    event_type: str | None
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemorySnapshot:
    """Point-in-time copy of working memory state.

    Snapshots enable rollback and inspection without affecting the live store.

    Attributes:
        entries: All memory entries at snapshot time.
        created_at: UTC timestamp of snapshot creation.
        version: Monotonically increasing version counter.

    """

    entries: list[MemoryEntry]
    created_at: datetime
    version: int


class WorkingMemory(Protocol):
    """Structural protocol for working memory backends.

    The runtime interacts with memory exclusively through this interface,
    allowing backend swaps without code changes.
    """

    async def store(self, key: str, value: Any) -> None:
        """Store a value under the given key.

        If the key already exists, its value and metadata are overwritten.

        Args:
            key: The storage key.
            value: The value to store.

        """
        ...

    async def retrieve(self, key: str) -> Any | None:
        """Retrieve the value associated with a key.

        Args:
            key: The storage key to look up.

        Returns:
            The stored value, or None if the key does not exist.

        """
        ...

    async def query(self, filter: MemoryFilter) -> list[MemoryEntry]:
        """Query memory entries matching the given filter criteria.

        Args:
            filter: Filter to apply to the stored entries.

        Returns:
            A list of matching MemoryEntry instances, ordered by timestamp.

        """
        ...

    async def clear(self) -> None:
        """Remove all entries from working memory.

        This is a destructive operation and cannot be undone.
        """
        ...

    async def snapshot(self) -> MemorySnapshot:
        """Capture a point-in-time snapshot of the entire memory state.

        Returns:
            A MemorySnapshot containing all current entries.

        """
        ...

    async def restore(self, snapshot: MemorySnapshot) -> None:
        """Replace the current memory state with a previously captured snapshot.

        Args:
            snapshot: The snapshot to restore from.

        """
        ...


class InMemoryStore:
    """Dict-backed working memory for single-process operation.

    All data lives in process memory and is lost on restart. Suitable for
    development and testing.
    """

    def __init__(self) -> None:
        """Initialize an empty in-memory store."""

    async def store(self, key: str, value: Any) -> None:
        """Store a value under the given key.

        Args:
            key: The storage key.
            value: The value to store.

        """

    async def retrieve(self, key: str) -> Any | None:
        """Retrieve a value by key.

        Args:
            key: The storage key.

        Returns:
            The stored value or None.

        """

    async def query(self, filter: MemoryFilter) -> list[MemoryEntry]:
        """Query entries matching the filter.

        Args:
            filter: Filter criteria.

        Returns:
            Matching entries.

        """
        raise NotImplementedError

    async def clear(self) -> None:
        """Remove all entries."""
        raise NotImplementedError

    async def snapshot(self) -> MemorySnapshot:
        """Capture a snapshot of all entries.

        Returns:
            A MemorySnapshot.

        """
        raise NotImplementedError

    async def restore(self, snapshot: MemorySnapshot) -> None:
        """Restore from a snapshot.

        Args:
            snapshot: The snapshot to restore.

        """
        raise NotImplementedError


class SQLiteMemoryStore:
    """Persistent working memory backed by SQLite.

    Provides durable storage for single-machine deployments. Future work will
    implement the full WorkingMemory protocol with WAL-mode concurrency and
    automatic compaction.
    """

    def __init__(self, db_path: str) -> None:
        """Initialize the SQLite memory store.

        Args:
            db_path: Filesystem path to the SQLite database file.

        """

    async def store(self, key: str, value: Any) -> None:
        """Store a value under the given key.

        Args:
            key: The storage key.
            value: The value to store.

        """

    async def retrieve(self, key: str) -> Any | None:
        """Retrieve a value by key.

        Args:
            key: The storage key.

        Returns:
            The stored value or None.

        """

    async def query(self, filter: MemoryFilter) -> list[MemoryEntry]:
        """Query entries matching the filter.

        Args:
            filter: Filter criteria.

        Returns:
            Matching entries.

        """
        raise NotImplementedError

    async def clear(self) -> None:
        """Remove all entries."""
        raise NotImplementedError

    async def snapshot(self) -> MemorySnapshot:
        """Capture a snapshot of all entries.

        Returns:
            A MemorySnapshot.

        """
        raise NotImplementedError

    async def restore(self, snapshot: MemorySnapshot) -> None:
        """Restore from a snapshot.

        Args:
            snapshot: The snapshot to restore.

        """
        raise NotImplementedError


class RedisMemoryStore:
    """Distributed working memory backed by Redis.

    Enables shared state across multiple runtime instances. Future work will
    implement the full WorkingMemory protocol with pub/sub invalidation and
    cluster-aware key sharding.
    """

    def __init__(self, url: str) -> None:
        """Initialize the Redis memory store.

        Args:
            url: Redis connection URL (e.g. ``redis://localhost:6379/0``).

        """

    async def store(self, key: str, value: Any) -> None:
        """Store a value under the given key.

        Args:
            key: The storage key.
            value: The value to store.

        """

    async def retrieve(self, key: str) -> Any | None:
        """Retrieve a value by key.

        Args:
            key: The storage key.

        Returns:
            The stored value or None.

        """

    async def query(self, filter: MemoryFilter) -> list[MemoryEntry]:
        """Query entries matching the filter.

        Args:
            filter: Filter criteria.

        Returns:
            Matching entries.

        """
        raise NotImplementedError

    async def clear(self) -> None:
        """Remove all entries."""
        raise NotImplementedError

    async def snapshot(self) -> MemorySnapshot:
        """Capture a snapshot of all entries.

        Returns:
            A MemorySnapshot.

        """
        raise NotImplementedError

    async def restore(self, snapshot: MemorySnapshot) -> None:
        """Restore from a snapshot.

        Args:
            snapshot: The snapshot to restore.

        """
        raise NotImplementedError
