"""Event type definitions for the Artax runtime.

Provides the canonical event taxonomy, concrete event implementation, and
filtering primitives used across all subsystems.
"""
from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


class EventType(enum.Enum):
    """Enumeration of all recognized event types in the Artax runtime.

    Each variant maps to a distinct category of runtime activity, enabling
    type-safe filtering and subscription on the event bus.
    """

    OBSERVATION = "observation"
    ACTION_REQUEST = "action_request"
    ACTION_RESULT = "action_result"
    STATE_CHANGE = "state_change"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    DRIVER_CONNECTED = "driver_connected"
    DRIVER_DISCONNECTED = "driver_disconnected"
    ENVIRONMENT_READY = "environment_ready"


class Event(Protocol):
    """Structural protocol for all events flowing through the runtime.

    Any object satisfying this protocol can be published to the event bus.
    Concrete implementations should freeze their fields after construction.
    """

    @property
    def id(self) -> uuid.UUID:
        """Unique identifier for this event instance."""
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
    def timestamp(self) -> datetime:
        """UTC timestamp of when this event was created."""
        ...

    @property
    def payload(self) -> dict[str, Any]:
        """Arbitrary structured data carried by this event."""
        ...

    @property
    def metadata(self) -> dict[str, Any]:
        """Non-essential annotations (trace IDs, version tags, etc.)."""
        ...


@dataclass(frozen=True)
class SemanticEvent:
    """Concrete event implementation carrying typed semantic data.

    Instances are created via the ``create`` classmethod which auto-generates
    the event ID and timestamps.

    Attributes:
        id: Globally unique event identifier.
        type: The category of this event.
        source: Subsystem or driver that produced this event.
        timestamp: UTC timestamp of event creation.
        payload: Arbitrary structured data carried by the event.
        metadata: Non-essential annotations.
    """

    id: uuid.UUID
    type: EventType
    source: str
    timestamp: datetime
    payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        type: EventType,
        source: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> SemanticEvent:
        """Construct a new SemanticEvent with auto-generated id and timestamp.

        Args:
            type: The event category.
            source: The originating subsystem or driver name.
            payload: Structured event data.
            metadata: Optional annotations; defaults to an empty dict.

        Returns:
            A new frozen SemanticEvent instance.
        """
        return cls(
            id=uuid.uuid4(),
            type=type,
            source=source,
            timestamp=datetime.now(timezone.utc),
            payload=payload,
            metadata=metadata or {},
        )


@dataclass(frozen=True)
class EventFilter:
    """Filter criteria for querying or subscribing to events.

    All fields are optional. A ``None`` value means the field is not
    considered when matching.

    Attributes:
        type: If set, only events of this type are matched.
        source: If set, only events from this source are matched.
        after: If set, only events timestamped after this datetime are matched.
        limit: Maximum number of matching events to return. Zero means no limit.
    """

    type: EventType | None = None
    source: str | None = None
    after: datetime | None = None
    limit: int = 0
