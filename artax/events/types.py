"""Event type definitions for the Artax runtime.

Provides the canonical event taxonomy, concrete event implementation, and
filtering primitives used across all subsystems.
"""

from __future__ import annotations

import enum
import fnmatch
import inspect
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


class EventType(str, enum.Enum):
    """Enumeration of all recognized event types in the Artax runtime.

    Each variant maps to a distinct category of runtime activity, enabling
    type-safe filtering and subscription on the event bus.
    """

    # Browser events
    DOM_CHANGED = "dom_changed"
    PAGE_LOADED = "page_loaded"
    PAGE_ERROR = "page_error"
    USER_INPUT = "user_input"
    SCREENSHOT_TAKEN = "screenshot_taken"

    # Action events
    ACTION_REQUESTED = "action_requested"
    ACTION_COMPLETED = "action_completed"
    ACTION_FAILED = "action_failed"

    # Memory events
    MEMORY_UPDATED = "memory_updated"

    # Scheduler events
    SCHEDULE_TICK = "schedule_tick"

    # Health events
    HEALTH_CHECK = "health_check"

    # Runtime events
    RUNTIME_STARTED = "runtime_started"
    RUNTIME_STOPPING = "runtime_stopping"
    RUNTIME_ERROR = "runtime_error"

    # Driver events
    DRIVER_CONNECTED = "driver_connected"
    DRIVER_DISCONNECTED = "driver_disconnected"
    DRIVER_UNHEALTHY = "driver_unhealthy"

    # Generic
    CUSTOM = "custom"


class Event(Protocol):
    """Structural protocol for all events flowing through the runtime.

    Any object satisfying this protocol can be published to the event bus.
    Concrete implementations should freeze their fields after construction.
    """

    @property
    def event_id(self) -> uuid.UUID:
        """Globally unique event identifier."""
        ...

    @property
    def type(self) -> EventType:
        """The category of this event."""
        ...

    @property
    def source(self) -> str:
        """Identifier of the subsystem or driver that produced this event."""
        ...

    @property
    def timestamp(self) -> float:
        """Epoch timestamp of when this event was created."""
        ...

    @property
    def payload(self) -> dict[str, Any]:
        """Arbitrary structured data carried by this event."""
        ...

    @property
    def metadata(self) -> dict[str, Any]:
        """Non-essential annotations (trace IDs, version tags, etc.)."""
        ...

    @property
    def correlation_id(self) -> uuid.UUID | None:
        """Optional correlation ID linking related events across subsystems."""
        ...


@dataclass(frozen=True)
class SemanticEvent:
    """Concrete event implementation carrying typed semantic data.

    Instances are created via the ``create`` classmethod which auto-generates
    the event ID and timestamp.

    Attributes:
        event_id: Globally unique event identifier (UUID4).
        type: The category of this event.
        source: Subsystem or driver that produced this event.
        timestamp: Epoch timestamp of event creation.
        payload: Arbitrary structured data carried by the event.
        metadata: Non-essential annotations.
        correlation_id: Optional UUID linking related events.

    """

    event_id: uuid.UUID
    type: EventType
    source: str
    timestamp: float
    payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: uuid.UUID | None = None

    @classmethod
    def create(
        cls,
        type: EventType,
        source: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        correlation_id: uuid.UUID | None = None,
    ) -> SemanticEvent:
        """Construct a new SemanticEvent with auto-generated id and timestamp.

        Args:
            type: The event category.
            source: The originating subsystem or driver name.
            payload: Structured event data.
            metadata: Optional annotations; defaults to an empty dict.
            correlation_id: Optional UUID linking related events.

        Returns:
            A new frozen SemanticEvent instance.

        """
        return cls(
            event_id=uuid.uuid4(),
            type=type,
            source=source,
            timestamp=time.time(),
            payload=payload,
            metadata=metadata or {},
            correlation_id=correlation_id,
        )


@dataclass(frozen=True)
class EventFilter:
    """Filter criteria for subscribing to events.

    All fields are optional. A ``None`` value means the field is not
    considered when matching. Supports wildcard source matching via
    fnmatch patterns (e.g. ``source="chromium.*"``).

    Attributes:
        type: If set, only events of this type are matched.
        source: If set, only events matching this source pattern are matched.
            Supports fnmatch wildcards (``*``, ``?``).
        predicate: Optional callable (sync or async) that receives an event
            and returns True if the event should be delivered.
        after: If set, only events timestamped after this value are matched.
        limit: Maximum number of matching events. None means no limit.
            Enforced during subscription matching — once matched events
            reach this count, subsequent events are rejected.

    """

    type: EventType | None = None
    source: str | None = None
    predicate: Callable[[Event], bool | Awaitable[bool]] | None = None
    after: float | None = None
    limit: int | None = None
    _matched_count: int = field(default=0, init=False, compare=False, repr=False)

    def reset_counter(self) -> None:
        """Reset the internal match counter."""
        object.__setattr__(self, "_matched_count", 0)

    async def matches(self, event: Event) -> bool:
        """Check if an event passes this filter.

        All specified fields must match (AND semantics). Source matching
        uses fnmatch for wildcard support. Predicate evaluation supports
        both sync and async callables. The ``limit`` field is enforced
        — once this many events have matched, all subsequent calls
        return False.

        Args:
            event: The event to test.

        Returns:
            True if the event matches all filter criteria and limit not reached.

        """
        if self.limit is not None and self._matched_count >= self.limit:
            return False

        if self.type is not None and event.type != self.type:
            return False

        if self.source is not None:
            if not fnmatch.fnmatch(event.source, self.source):
                return False

        if self.after is not None and event.timestamp <= self.after:
            return False

        if self.predicate is not None:
            result = self.predicate(event)
            if inspect.isawaitable(result):
                result = await result
            if not result:
                return False

        object.__setattr__(self, "_matched_count", self._matched_count + 1)
        return True


@dataclass
class EventBusConfig:
    """Configuration for an EventBus instance.

    Attributes:
        history_size: Maximum number of events kept in the ring buffer.
        max_queue_size: Maximum events queued per subscriber before dropping.
        dispatch_timeout: Seconds to wait when dispatching before timing out.

    """

    history_size: int = 1000
    max_queue_size: int = 10000
    dispatch_timeout: float = 1.0


@dataclass
class EventBusStats:
    """Point-in-time statistics for the EventBus.

    Attributes:
        events_published: Total events published since start.
        events_delivered: Total event deliveries (across all subscribers).
        subscriptions_active: Number of active subscriptions.
        subscriptions_dropped: Total events dropped due to queue overflow.
        queue_depth: Current total queued events across all subscribers.

    """

    events_published: int = 0
    events_delivered: int = 0
    subscriptions_active: int = 0
    subscriptions_dropped: int = 0
    queue_depth: int = 0
