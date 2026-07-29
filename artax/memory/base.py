"""Working memory protocol and storage backends.

Working memory provides transient, queryable key-value storage for runtime
state. Multiple backends are supported: in-process dicts, SQLite for
persistence, and Redis for distributed coordination.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import sqlite3
import threading
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from ..events.types import EventType, SemanticEvent

logger = logging.getLogger(__name__)


@dataclass
class MemoryConfig:
    """Configuration for a WorkingMemory backend instance.

    Attributes:
        backend: Backend type selector.
        max_entries: Maximum number of entries before LRU eviction.
        default_ttl: Default time-to-live in seconds. None means no expiry.
        cleanup_interval: Seconds between cleanup sweeps (future eager cleanup).
        sqlite_path: Filesystem path for the SQLite backend.
        redis_url: Connection URL for the Redis backend.

    """

    backend: Literal["memory", "sqlite", "redis"] = "memory"
    max_entries: int = 10000
    default_ttl: float | None = None
    cleanup_interval: float = 60.0
    sqlite_path: str = "artax_memory.db"
    redis_url: str = "redis://localhost:6379"


@dataclass(frozen=True)
class MemoryEntry:
    """A single record in working memory.

    Attributes:
        key: The storage key (hierarchical keys use ``.`` separators).
        value: Arbitrary stored value (JSON-serializable).
        namespace: Logical grouping (e.g. ``"chromium"``, ``"scheduler"``).
        created_at: Monotonic timestamp when the entry was created.
        updated_at: Monotonic timestamp of the last write.
        ttl: Absolute monotonic time when the entry expires, or None.

    """

    key: str
    value: Any
    namespace: str
    created_at: float
    updated_at: float
    ttl: float | None


@dataclass(frozen=True)
class MemoryFilter:
    """Filter criteria for querying working memory entries.

    All specified fields are combined with AND semantics.

    Attributes:
        namespace: If set, only entries in this namespace are returned.
        key_prefix: If set, only keys starting with this prefix are returned.
        value_type: If set, only entries whose value is an instance of this
            type are returned.
        predicate: Optional callable (sync or async) that receives a
            ``MemoryEntry`` and returns True if the entry should be included.
        after: If set, only entries created after this monotonic timestamp
            are returned.
        limit: Maximum number of entries to return. None means no limit.

    """

    namespace: str | None = None
    key_prefix: str | None = None
    value_type: type | None = None
    predicate: Callable[[MemoryEntry], bool | Awaitable[bool]] | None = None
    after: float | None = None
    limit: int | None = None


@dataclass(frozen=True)
class MemorySnapshot:
    """Point-in-time copy of working memory state.

    Snapshots enable rollback and inspection without affecting the live store.

    Attributes:
        version: Schema version string.
        timestamp: Monotonic timestamp when the snapshot was taken.
        entries: All memory entries organized as
            ``{namespace: {key: serialized_entry}}``.

    """

    version: str
    timestamp: float
    entries: dict[str, dict[str, Any]]


class WorkingMemory(Protocol):
    """Structural protocol for working memory backends.

    The runtime interacts with memory exclusively through this interface,
    allowing backend swaps without code changes.
    """

    async def start(self) -> None:
        """Initialize the backend."""
        ...

    async def stop(self) -> None:
        """Flush pending writes and close the backend."""
        ...

    async def store(
        self,
        key: str,
        value: Any,
        namespace: str = "default",
        ttl: float | None = None,
    ) -> None:
        """Store a value under a key. Overwrites if exists.

        Args:
            key: The storage key.
            value: The value to store.
            namespace: Logical grouping for the entry.
            ttl: Time-to-live in seconds from now, or None for no expiry.

        """
        ...

    async def retrieve(self, key: str, namespace: str = "default") -> Any | None:
        """Retrieve a value by key. Returns None if not found or expired.

        Args:
            key: The storage key to look up.
            namespace: Logical grouping to look in.

        Returns:
            The stored value, or None if the key does not exist or is expired.

        """
        ...

    async def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete a key. Returns True if key existed.

        Args:
            key: The storage key to delete.
            namespace: Logical grouping to delete from.

        """
        ...

    async def query(self, filter: MemoryFilter) -> dict[str, Any]:
        """Query entries matching the filter criteria.

        Args:
            filter: Filter to apply to the stored entries.

        Returns:
            A dict of ``{key: value}`` pairs for matching entries.

        """
        ...

    async def clear(self, namespace: str | None = None) -> int:
        """Clear all entries, optionally within a namespace.

        Args:
            namespace: If provided, only clear entries in this namespace.

        Returns:
            The number of entries removed.

        """
        ...

    async def keys(self, namespace: str = "default") -> list[str]:
        """List all keys in a namespace.

        Args:
            namespace: Logical grouping to list keys from.

        """
        ...

    async def size(self, namespace: str | None = None) -> int:
        """Return the number of entries currently stored.

        Args:
            namespace: If provided, count only entries in this namespace.

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

    All data lives in process memory and is lost on restart. Uses
    ``OrderedDict`` for LRU eviction ordering. When capacity is reached,
    the least-recently-accessed entry is evicted.

    Args:
        config: Backend configuration. Uses defaults if None.
        event_bus: Optional event bus for emitting memory events.

    """

    def __init__(
        self,
        config: MemoryConfig | None = None,
        event_bus: Any | None = None,
    ) -> None:
        """Initialize the in-memory store.

        Args:
            config: Backend configuration. Uses defaults if None.
            event_bus: Optional event bus for emitting memory events.

        """
        self._config = config or MemoryConfig()
        self._event_bus = event_bus
        self._storage: dict[str, OrderedDict[str, MemoryEntry]] = {}
        self._version: int = 0
        self._cleanup_task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start the store and spawn the TTL cleanup background task."""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the cleanup task and clear all data."""
        self._running = False
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        self._storage.clear()

    async def store(
        self,
        key: str,
        value: Any,
        namespace: str = "default",
        ttl: float | None = None,
    ) -> None:
        """Store a value under a key with optional TTL.

        If the key already exists, its value and timestamps are overwritten.
        If the namespace is at capacity, the least-recently-accessed entry
        is evicted. Emits a ``MEMORY_UPDATED`` event for new keys.
        """
        ns = self._storage.setdefault(namespace, OrderedDict())
        now = time.monotonic()
        expiry = now + ttl if ttl is not None else None
        is_new = key not in ns

        entry = MemoryEntry(
            key=key,
            value=value,
            namespace=namespace,
            created_at=ns[key].created_at if not is_new else now,
            updated_at=now,
            ttl=expiry,
        )

        if is_new:
            if len(ns) >= self._config.max_entries:
                evicted_key, _evicted_entry = ns.popitem(last=False)
                logger.debug(
                    "Evicted LRU entry %s/%s (capacity %d)",
                    namespace,
                    evicted_key,
                    self._config.max_entries,
                )
                await self._emit_event(
                    "memory_evicted",
                    {
                        "key": evicted_key,
                        "namespace": namespace,
                        "reason": "capacity",
                    },
                )
            ns[key] = entry
            ns.move_to_end(key)
            await self._emit_event(
                "memory_updated",
                {"key": key, "namespace": namespace, "operation": "store"},
            )
        else:
            ns[key] = entry
            ns.move_to_end(key)

    async def retrieve(self, key: str, namespace: str = "default") -> Any | None:
        """Retrieve a value by key.

        Performs lazy TTL enforcement: if the entry is expired it is deleted
        and None is returned. Access updates the entry's LRU position.
        """
        ns = self._storage.get(namespace)
        if ns is None or key not in ns:
            return None

        entry = ns[key]
        if entry.ttl is not None and time.monotonic() > entry.ttl:
            del ns[key]
            return None

        ns.move_to_end(key)
        return entry.value

    async def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete a key. Returns True if the key existed."""
        ns = self._storage.get(namespace)
        if ns is None or key not in ns:
            return False
        del ns[key]
        return True

    async def query(self, filter: MemoryFilter) -> dict[str, Any]:
        """Query entries matching the filter criteria.

        Iterates entries, applying namespace, prefix, type, and predicate
        filters. Supports both sync and async predicates. Respects the
        limit parameter.
        """
        result: dict[str, Any] = {}
        count = 0

        namespaces = (
            [filter.namespace] if filter.namespace is not None else list(self._storage.keys())
        )

        for ns_name in namespaces:
            ns = self._storage.get(ns_name)
            if ns is None:
                continue

            for entry in ns.values():
                if filter.limit is not None and count >= filter.limit:
                    break

                if not await self._matches_filter(entry, filter):
                    continue

                result[entry.key] = entry.value
                count += 1

        return result

    @staticmethod
    async def _matches_filter(entry: MemoryEntry, filter: MemoryFilter) -> bool:
        """Check if an entry passes all filter criteria."""
        if entry.ttl is not None and time.monotonic() > entry.ttl:
            return False
        if filter.namespace is not None and entry.namespace != filter.namespace:
            return False
        if filter.key_prefix is not None and not entry.key.startswith(filter.key_prefix):
            return False
        if filter.value_type is not None and not isinstance(entry.value, filter.value_type):
            return False
        if filter.after is not None and entry.created_at <= filter.after:
            return False
        result = True
        if filter.predicate is not None:
            pred_result = filter.predicate(entry)
            if inspect.isawaitable(pred_result):
                pred_result = await pred_result
            result = bool(pred_result)
        return result

    async def clear(self, namespace: str | None = None) -> int:
        """Clear entries. Returns the number of entries removed.

        If namespace is provided, only entries in that namespace are removed.
        """
        count = 0
        if namespace is not None:
            ns = self._storage.pop(namespace, None)
            if ns is not None:
                count = len(ns)
        else:
            for ns in self._storage.values():
                count += len(ns)
            self._storage.clear()

        if count > 0:
            await self._emit_event(
                "memory_updated",
                {
                    "namespace": namespace,
                    "operation": "clear",
                    "count": count,
                },
            )

        return count

    async def keys(self, namespace: str = "default") -> list[str]:
        """List all keys in a namespace."""
        ns = self._storage.get(namespace)
        if ns is None:
            return []
        return list(ns.keys())

    async def size(self, namespace: str | None = None) -> int:
        """Return the number of entries stored."""
        if namespace is not None:
            ns = self._storage.get(namespace)
            return len(ns) if ns is not None else 0
        return sum(len(ns) for ns in self._storage.values())

    async def snapshot(self) -> MemorySnapshot:
        """Capture a point-in-time snapshot of all entries.

        Returns a MemorySnapshot containing serialized entries with TTL info.
        """
        self._version += 1
        entries: dict[str, dict[str, Any]] = {}
        for ns_name, ns in self._storage.items():
            entries[ns_name] = {}
            for key, entry in ns.items():
                entries[ns_name][key] = {
                    "key": entry.key,
                    "value": entry.value,
                    "namespace": entry.namespace,
                    "created_at": entry.created_at,
                    "updated_at": entry.updated_at,
                    "ttl": entry.ttl,
                }
        return MemorySnapshot(
            version="0.1",
            timestamp=time.monotonic(),
            entries=entries,
        )

    async def restore(self, snapshot: MemorySnapshot) -> None:
        """Replace current state from a snapshot."""
        self._storage.clear()
        for ns_name, ns_entries in snapshot.entries.items():
            ns: OrderedDict[str, MemoryEntry] = OrderedDict()
            for key, data in ns_entries.items():
                ns[key] = MemoryEntry(
                    key=data["key"],
                    value=data["value"],
                    namespace=data["namespace"],
                    created_at=data["created_at"],
                    updated_at=data["updated_at"],
                    ttl=data["ttl"],
                )
            self._storage[ns_name] = ns

    async def _cleanup_loop(self) -> None:
        """Periodically sweep and remove expired entries."""
        try:
            while self._running:
                await asyncio.sleep(self._config.cleanup_interval)
                if not self._running:
                    break
                removed = 0
                now = time.monotonic()
                for ns_name in list(self._storage.keys()):
                    ns = self._storage.get(ns_name)
                    if ns is None:
                        continue
                    expired = [
                        k for k, entry in ns.items() if entry.ttl is not None and now > entry.ttl
                    ]
                    for k in expired:
                        del ns[k]
                        removed += 1
                    if not ns:
                        del self._storage[ns_name]
                if removed > 0:
                    logger.debug("TTL cleanup removed %d expired entries", removed)
                    await self._emit_event(
                        "memory_cleanup",
                        {"removed": removed},
                    )
        except asyncio.CancelledError:
            return

    async def _emit_event(self, operation: str, payload: dict[str, Any]) -> None:
        """Publish a memory event if an event bus is connected."""
        if self._event_bus is None:
            return
        try:
            event = SemanticEvent.create(
                type=EventType.MEMORY_UPDATED,
                source="memory",
                payload={"event": operation, **payload},
            )
            await self._event_bus.publish(event)
        except Exception:
            logger.exception("Failed to emit memory event: %s", operation)


class SQLiteMemoryStore:
    """Persistent working memory backed by SQLite.

    Provides durable storage for single-machine deployments using stdlib
    sqlite3 with WAL mode and asyncio.to_thread for non-blocking I/O.

    Args:
        config: Backend configuration. Uses defaults if None.
        event_bus: Optional event bus for emitting memory events.

    """

    def __init__(
        self,
        config: MemoryConfig | None = None,
        event_bus: Any | None = None,
    ) -> None:
        """Initialize the SQLite memory store.

        Args:
            config: Backend configuration. Uses defaults if None.
            event_bus: Optional event bus for emitting memory events.

        """
        self._config = config or MemoryConfig()
        self._event_bus = event_bus
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._cleanup_task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Initialize the SQLite connection and create table."""
        self._conn = await asyncio.to_thread(
            sqlite3.connect, self._config.sqlite_path, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        await asyncio.to_thread(self._conn.execute, "PRAGMA journal_mode=WAL")
        await asyncio.to_thread(self._conn.execute, "PRAGMA synchronous=NORMAL")
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS memory_entries (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                accessed_at REAL NOT NULL,
                ttl REAL,
                PRIMARY KEY (namespace, key)
            )
            """,
        )
        await asyncio.to_thread(self._conn.commit)
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the cleanup task and close the connection."""
        self._running = False
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        if self._conn is not None:
            await asyncio.to_thread(self._conn.close)
            self._conn = None

    async def store(
        self,
        key: str,
        value: Any,
        namespace: str = "default",
        ttl: float | None = None,
    ) -> None:
        """Store a value under a key with optional TTL.

        If the namespace is at capacity, the least-recently-accessed entry
        is evicted. Emits a MEMORY_UPDATED event for new keys.
        """
        conn = self._conn
        if conn is None:
            raise RuntimeError("SQLiteMemoryStore not started")

        now = time.monotonic()
        expiry = now + ttl if ttl is not None else None
        serialized = json.dumps(value, default=str)

        def _do_store() -> tuple[bool, str | None]:
            with self._lock:
                cur = conn.execute(
                    "SELECT 1 FROM memory_entries WHERE namespace=? AND key=?",
                    (namespace, key),
                )
                is_new = cur.fetchone() is None
                evicted_key: str | None = None

                if is_new:
                    cur = conn.execute(
                        "SELECT COUNT(*) FROM memory_entries WHERE namespace=?",
                        (namespace,),
                    )
                    count = cur.fetchone()[0]
                    if count >= self._config.max_entries:
                        cur = conn.execute(
                            """SELECT key FROM memory_entries
                               WHERE namespace=? ORDER BY accessed_at ASC LIMIT 1""",
                            (namespace,),
                        )
                        row = cur.fetchone()
                        if row is not None:
                            evicted_key = row["key"]
                            conn.execute(
                                "DELETE FROM memory_entries WHERE namespace=? AND key=?",
                                (namespace, evicted_key),
                            )
                            logger.debug(
                                "Evicted LRU entry %s/%s (capacity %d)",
                                namespace,
                                evicted_key,
                                self._config.max_entries,
                            )

                conn.execute(
                    """INSERT INTO memory_entries
                       (namespace, key, value, created_at, updated_at, accessed_at, ttl)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(namespace, key) DO UPDATE SET
                           value=excluded.value,
                           updated_at=excluded.updated_at,
                           accessed_at=excluded.updated_at,
                           ttl=excluded.ttl""",
                    (namespace, key, serialized, now, now, now, expiry),
                )
                conn.commit()
                return is_new, evicted_key

        is_new, evicted_key = await asyncio.to_thread(_do_store)

        if evicted_key is not None:
            await self._emit_event(
                "memory_evicted",
                {
                    "key": evicted_key,
                    "namespace": namespace,
                    "reason": "capacity",
                },
            )

        if is_new:
            await self._emit_event(
                "memory_updated",
                {"key": key, "namespace": namespace, "operation": "store"},
            )

    async def retrieve(self, key: str, namespace: str = "default") -> Any | None:
        """Retrieve a value by key.

        Performs lazy TTL enforcement: if the entry is expired it is deleted
        and None is returned. Access updates the LRU position.
        """
        conn = self._conn
        if conn is None:
            raise RuntimeError("SQLiteMemoryStore not started")

        def _do_retrieve() -> tuple[Any, bool] | None:
            with self._lock:
                cur = conn.execute(
                    "SELECT value, ttl FROM memory_entries WHERE namespace=? AND key=?",
                    (namespace, key),
                )
                row = cur.fetchone()
                if row is None:
                    return None

                now = time.monotonic()
                ttl = row["ttl"]
                if ttl is not None and now > ttl:
                    conn.execute(
                        "DELETE FROM memory_entries WHERE namespace=? AND key=?",
                        (namespace, key),
                    )
                    conn.commit()
                    return None

                conn.execute(
                    "UPDATE memory_entries SET accessed_at=? WHERE namespace=? AND key=?",
                    (now, namespace, key),
                )
                conn.commit()
                return json.loads(row["value"]), True

        result = await asyncio.to_thread(_do_retrieve)
        if result is None:
            return None
        return result[0]

    async def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete a key. Returns True if the key existed."""
        conn = self._conn
        if conn is None:
            raise RuntimeError("SQLiteMemoryStore not started")

        def _do_delete() -> bool:
            with self._lock:
                cur = conn.execute(
                    "SELECT 1 FROM memory_entries WHERE namespace=? AND key=?",
                    (namespace, key),
                )
                if cur.fetchone() is None:
                    return False
                conn.execute(
                    "DELETE FROM memory_entries WHERE namespace=? AND key=?",
                    (namespace, key),
                )
                conn.commit()
                return True

        return await asyncio.to_thread(_do_delete)

    async def query(self, filter: MemoryFilter) -> dict[str, Any]:  # noqa: C901
        """Query entries matching the filter criteria.

        Builds a SQL WHERE clause from filter fields, then applies
        value_type and predicate filtering in Python when needed.
        """
        conn = self._conn
        if conn is None:
            raise RuntimeError("SQLiteMemoryStore not started")

        can_use_sql_limit = filter.value_type is None and filter.predicate is None

        def _build_where() -> tuple[str, list[Any]]:
            clauses: list[str] = []
            params: list[Any] = []
            if filter.namespace is not None:
                clauses.append("namespace = ?")
                params.append(filter.namespace)
            if filter.key_prefix is not None:
                clauses.append("key LIKE ?")
                params.append(filter.key_prefix + "%")
            if filter.after is not None:
                clauses.append("created_at > ?")
                params.append(filter.after)
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            return where, params

        def _row_matches(row: sqlite3.Row, val: Any) -> bool:
            if filter.value_type is not None and not isinstance(val, filter.value_type):
                return False
            if filter.predicate is not None:
                ttl = row["ttl"]
                entry = MemoryEntry(
                    key=row["key"],
                    value=val,
                    namespace=row["namespace"],
                    created_at=0.0,
                    updated_at=0.0,
                    ttl=ttl,
                )
                pred_result = filter.predicate(entry)
                if inspect.isawaitable(pred_result):
                    raise RuntimeError("Async predicates not supported in SQLite query")
                if not pred_result:
                    return False
            return True

        def _do_query() -> list[dict[str, Any]]:
            with self._lock:
                where, params = _build_where()
                limit_clause = ""
                if filter.limit is not None and can_use_sql_limit:
                    limit_clause = f" LIMIT {filter.limit}"

                sql = "SELECT namespace, key, value, ttl FROM memory_entries" + where + limit_clause  # noqa: S608
                cur = conn.execute(sql, params)

                now = time.monotonic()
                results: list[dict[str, Any]] = []
                for row in cur.fetchall():
                    ttl = row["ttl"]
                    if ttl is not None and now > ttl:
                        conn.execute(
                            "DELETE FROM memory_entries WHERE namespace=? AND key=?",
                            (row["namespace"], row["key"]),
                        )
                        conn.commit()
                        continue
                    val = json.loads(row["value"])
                    if not _row_matches(row, val):
                        continue
                    results.append({"key": row["key"], "value": val})
                    if filter.limit is not None and len(results) >= filter.limit:
                        break
                return results

        rows = await asyncio.to_thread(_do_query)
        return {r["key"]: r["value"] for r in rows}

    async def clear(self, namespace: str | None = None) -> int:
        """Clear entries. Returns the number of entries removed."""
        conn = self._conn
        if conn is None:
            raise RuntimeError("SQLiteMemoryStore not started")

        def _do_clear() -> int:
            with self._lock:
                if namespace is not None:
                    cur = conn.execute(
                        "SELECT COUNT(*) FROM memory_entries WHERE namespace=?",
                        (namespace,),
                    )
                    row = cur.fetchone()
                    count: int = row[0] if row is not None else 0
                    conn.execute(
                        "DELETE FROM memory_entries WHERE namespace=?",
                        (namespace,),
                    )
                else:
                    cur = conn.execute("SELECT COUNT(*) FROM memory_entries")
                    row = cur.fetchone()
                    count = row[0] if row is not None else 0
                    conn.execute("DELETE FROM memory_entries")
                conn.commit()
                return count

        count = await asyncio.to_thread(_do_clear)

        if count > 0:
            await self._emit_event(
                "memory_updated",
                {
                    "namespace": namespace,
                    "operation": "clear",
                    "count": count,
                },
            )

        return count

    async def keys(self, namespace: str = "default") -> list[str]:
        """List all keys in a namespace."""
        conn = self._conn
        if conn is None:
            raise RuntimeError("SQLiteMemoryStore not started")

        def _do_keys() -> list[str]:
            with self._lock:
                cur = conn.execute(
                    "SELECT key FROM memory_entries WHERE namespace=?",
                    (namespace,),
                )
                return [row["key"] for row in cur.fetchall()]

        return await asyncio.to_thread(_do_keys)

    async def size(self, namespace: str | None = None) -> int:
        """Return the number of entries stored."""
        conn = self._conn
        if conn is None:
            raise RuntimeError("SQLiteMemoryStore not started")

        def _do_size() -> int:
            with self._lock:
                if namespace is not None:
                    cur = conn.execute(
                        "SELECT COUNT(*) FROM memory_entries WHERE namespace=?",
                        (namespace,),
                    )
                else:
                    cur = conn.execute("SELECT COUNT(*) FROM memory_entries")
                row = cur.fetchone()
                return row[0] if row is not None else 0

        return await asyncio.to_thread(_do_size)

    async def snapshot(self) -> MemorySnapshot:
        """Capture a point-in-time snapshot of all entries."""
        conn = self._conn
        if conn is None:
            raise RuntimeError("SQLiteMemoryStore not started")

        def _do_snapshot() -> MemorySnapshot:
            with self._lock:
                cur = conn.execute(
                    "SELECT namespace, key, value, created_at, updated_at, ttl FROM memory_entries",
                )
                entries: dict[str, dict[str, Any]] = {}
                for row in cur.fetchall():
                    ns = row["namespace"]
                    if ns not in entries:
                        entries[ns] = {}
                    entries[ns][row["key"]] = {
                        "key": row["key"],
                        "value": json.loads(row["value"]),
                        "namespace": ns,
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "ttl": row["ttl"],
                    }
            return MemorySnapshot(
                version="0.1",
                timestamp=time.monotonic(),
                entries=entries,
            )

        return await asyncio.to_thread(_do_snapshot)

    async def restore(self, snapshot: MemorySnapshot) -> None:
        """Replace current state from a snapshot."""
        conn = self._conn
        if conn is None:
            raise RuntimeError("SQLiteMemoryStore not started")

        def _do_restore() -> None:
            with self._lock:
                conn.execute("DELETE FROM memory_entries")
                now = time.monotonic()
                for ns_name, ns_entries in snapshot.entries.items():
                    for key, data in ns_entries.items():
                        val = data.get("value")
                        conn.execute(
                            """INSERT INTO memory_entries
                               (namespace, key, value, created_at, updated_at, accessed_at, ttl)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (
                                ns_name,
                                key,
                                json.dumps(val, default=str),
                                data.get("created_at", now),
                                data.get("updated_at", now),
                                now,
                                data.get("ttl"),
                            ),
                        )
                conn.commit()

        await asyncio.to_thread(_do_restore)

    async def _cleanup_loop(self) -> None:
        """Periodically sweep and remove expired entries."""
        conn = self._conn
        if conn is None:
            return
        try:
            while self._running:
                await asyncio.sleep(self._config.cleanup_interval)
                if not self._running or conn is None:
                    break

                def _do_cleanup() -> int:
                    with self._lock:
                        now = time.monotonic()
                        cur = conn.execute(
                            "DELETE FROM memory_entries WHERE ttl IS NOT NULL AND ttl < ?",
                            (now,),
                        )
                        conn.commit()
                        return cur.rowcount

                removed = await asyncio.to_thread(_do_cleanup)
                if removed > 0:
                    logger.debug("TTL cleanup removed %d expired entries", removed)
                    await self._emit_event(
                        "memory_cleanup",
                        {"removed": removed},
                    )
        except asyncio.CancelledError:
            return

    async def _emit_event(self, operation: str, payload: dict[str, Any]) -> None:
        """Publish a memory event if an event bus is connected."""
        if self._event_bus is None:
            return
        try:
            event = SemanticEvent.create(
                type=EventType.MEMORY_UPDATED,
                source="memory",
                payload={"event": operation, **payload},
            )
            await self._event_bus.publish(event)
        except Exception:
            logger.exception("Failed to emit memory event: %s", operation)


class RedisMemoryStore:
    """Distributed working memory backed by Redis.

    Enables shared state across multiple runtime instances. Future work will
    implement the full WorkingMemory protocol with pub/sub invalidation and
    cluster-aware key sharding.
    """

    def __init__(self, url: str = "redis://localhost:6379") -> None:
        """Initialize the Redis memory store.

        Args:
            url: Redis connection URL.

        """
        self._url = url

    async def start(self) -> None:
        """Connect to Redis."""
        raise NotImplementedError

    async def stop(self) -> None:
        """Disconnect from Redis."""
        raise NotImplementedError

    async def store(
        self,
        key: str,
        value: Any,
        namespace: str = "default",
        ttl: float | None = None,
    ) -> None:
        """Store a value under the given key."""
        raise NotImplementedError

    async def retrieve(self, key: str, namespace: str = "default") -> Any | None:
        """Retrieve a value by key."""
        raise NotImplementedError

    async def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete a key."""
        raise NotImplementedError

    async def query(self, filter: MemoryFilter) -> dict[str, Any]:
        """Query entries matching the filter."""
        raise NotImplementedError

    async def clear(self, namespace: str | None = None) -> int:
        """Remove all entries."""
        raise NotImplementedError

    async def keys(self, namespace: str = "default") -> list[str]:
        """List keys in a namespace."""
        raise NotImplementedError

    async def size(self, namespace: str | None = None) -> int:
        """Return the number of entries."""
        raise NotImplementedError

    async def snapshot(self) -> MemorySnapshot:
        """Capture a snapshot of all entries."""
        raise NotImplementedError

    async def restore(self, snapshot: MemorySnapshot) -> None:
        """Restore from a snapshot."""
        raise NotImplementedError
