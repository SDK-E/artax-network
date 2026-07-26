"""Event bus protocol and in-memory implementation.

The event bus decouples producers from consumers, enabling asynchronous
publish-subscribe messaging throughout the runtime.
"""
from __future__ import annotations

from typing import Callable, Protocol

from .types import Event, EventType


class Subscription(Protocol):
    """Handle returned when subscribing to an event type.

    Callers retain this handle to unsubscribe later.

    Attributes:
        id: Unique identifier for this subscription.
        active: Whether the subscription is currently receiving events.
    """

    @property
    def id(self) -> str:
        """Unique subscription identifier."""
        ...

    @property
    def active(self) -> bool:
        """Whether this subscription is active."""
        ...


class EventBus(Protocol):
    """Structural protocol for event bus implementations.

    The runtime depends only on this protocol; concrete implementations
    (in-memory, Redis-backed, etc.) are injected at startup.
    """

    async def publish(self, event: Event) -> None:
        """Publish an event to all matching subscribers.

        Args:
            event: The event to publish.
        """
        ...

    async def subscribe(
        self, event_type: EventType, callback: Callable
    ) -> Subscription:
        """Register a callback to receive events of the given type.

        Args:
            event_type: The event type to subscribe to.
            callback: An async callable invoked with each matching event.

        Returns:
            A Subscription handle for later unsubscription.
        """
        ...

    async def unsubscribe(self, subscription: Subscription) -> None:
        """Remove a previously registered subscription.

        Args:
            subscription: The subscription handle returned by ``subscribe``.
        """
        ...

    async def drain(self) -> None:
        """Block until all pending events have been delivered to subscribers.

        Useful during shutdown to ensure no events are lost.
        """
        ...


class MemoryEventBus:
    """In-memory event bus implementation for single-process operation.

    Events are published synchronously to registered callbacks, ordered by
    subscription registration. This implementation is not suitable for
    distributed or multi-process deployments.
    """

    def __init__(self) -> None:
        """Initialize an empty event bus."""
        pass

    async def publish(self, event: Event) -> None:
        """Publish an event to all matching subscribers.

        Args:
            event: The event to publish.
        """
        pass

    async def subscribe(
        self, event_type: EventType, callback: Callable
    ) -> Subscription:
        """Register a callback for a specific event type.

        Args:
            event_type: The event type to filter on.
            callback: Async callable invoked with each matching event.

        Returns:
            A Subscription handle.
        """
        pass

    async def unsubscribe(self, subscription: Subscription) -> None:
        """Remove a subscription.

        Args:
            subscription: The handle to deactivate.
        """
        pass

    async def drain(self) -> None:
        """Wait for all pending events to be delivered."""
        pass
