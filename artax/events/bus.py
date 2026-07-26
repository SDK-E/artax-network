"""Event bus protocol and in-memory implementation.

The event bus decouples producers from consumers, enabling asynchronous
publish-subscribe messaging throughout the runtime.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol

from .types import Event, EventBusConfig, EventBusStats, EventFilter, EventType, SemanticEvent

logger = logging.getLogger(__name__)


class Subscription(Protocol):
    """Handle returned when subscribing to an event bus.

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

    async def start(self) -> None:
        """Begin accepting publishes and dispatching events."""
        ...

    async def stop(self) -> None:
        """Drain pending events and stop dispatching."""
        ...

    async def publish(self, event: Event) -> asyncio.Future[None]:
        """Publish an event to all matching subscribers.

        Args:
            event: The event to publish.

        Returns:
            A Future that resolves when the event has been enqueued.

        """
        ...

    async def subscribe(
        self,
        filter: EventFilter,
        callback: Callable[[Event], Awaitable[None]],
    ) -> str:
        """Subscribe to events matching the filter.

        Args:
            filter: Criteria to match events against.
            callback: Async callable invoked with each matching event.

        Returns:
            A subscription ID string for later unsubscription.

        """
        ...

    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove a previously registered subscription.

        Args:
            subscription_id: The subscription ID returned by ``subscribe``.

        """
        ...

    async def drain(self) -> None:
        """Block until all pending events have been delivered to subscribers."""
        ...

    def history(self, limit: int | None = None) -> list[Event]:
        """Return events from the ring buffer.

        Args:
            limit: Maximum events to return. None returns all.

        Returns:
            List of events in chronological order.

        """
        ...

    def stats(self) -> EventBusStats:
        """Return current bus statistics."""
        ...


@dataclass
class _SubscriptionState:
    """Internal state for a single subscription."""

    id: str
    event_filter: EventFilter
    callback: Callable[[Event], Awaitable[None]]
    queue: asyncio.Queue[Event] = field(default_factory=lambda: asyncio.Queue())
    task: asyncio.Task[None] | None = None
    delivered: int = 0
    dropped: int = 0


class MemoryEventBus:
    """In-memory event bus implementation for single-process operation.

    Events are dispatched to subscribers via per-subscription asyncio queues,
    ensuring non-blocking delivery. A ring buffer retains recent history.
    """

    def __init__(self, config: EventBusConfig | None = None) -> None:
        """Initialize the event bus.

        Args:
            config: Bus configuration. Uses defaults if None.

        """
        self._config = config or EventBusConfig()
        self._history: deque[Event] = deque(maxlen=self._config.history_size)
        self._subscriptions: dict[str, _SubscriptionState] = {}
        self._running = False
        self._stopped = False
        self._started = False
        self._stats_task: asyncio.Task[None] | None = None
        self._published_count = 0
        self._delivered_count = 0
        self._dropped_count = 0
        self._lock = asyncio.Lock()
        self._drain_event = asyncio.Event()

    async def start(self) -> None:
        """Begin accepting publishes and dispatching events."""
        self._running = True
        self._stopped = False
        self._started = True
        self._stats_task = asyncio.create_task(self._stats_emitter())

    async def stop(self) -> None:
        """Drain pending events and stop dispatching."""
        self._stopped = True
        self._running = False
        if self._stats_task is not None:
            self._stats_task.cancel()
            try:
                await self._stats_task
            except asyncio.CancelledError:
                pass
            self._stats_task = None
        await self.drain()

    async def publish(self, event: Event) -> asyncio.Future[None]:
        """Publish an event to all matching subscribers.

        Appends to the ring buffer, then enqueues for each matching subscriber.
        If a subscriber queue is full, the event is dropped and a
        subscription.dropped event is emitted.

        Args:
            event: The event to publish.

        Returns:
            A resolved Future.

        """
        loop = asyncio.get_running_loop()
        if self._stopped:
            logger.warning("Publish to stopped bus dropped: %s", event.event_id)
            fut: asyncio.Future[None] = loop.create_future()
            fut.set_result(None)
            return fut

        self._history.append(event)
        self._published_count += 1

        async with self._lock:
            subscriptions = list(self._subscriptions.values())

        drop_events: list[SemanticEvent] = []
        for sub in subscriptions:
            if await sub.event_filter.matches(event):
                if sub.queue.full():
                    self._dropped_count += 1
                    sub.dropped += 1
                    drop_events.append(
                        SemanticEvent.create(
                            type=EventType.CUSTOM,
                            source="event_bus",
                            payload={
                                "event": "subscription.dropped",
                                "subscription_id": sub.id,
                                "dropped_event_id": str(event.event_id),
                            },
                        )
                    )
                else:
                    sub.queue.put_nowait(event)

        for drop_event in drop_events:
            asyncio.create_task(self.publish(drop_event))

        result: asyncio.Future[None] = loop.create_future()
        result.set_result(None)
        return result

    async def subscribe(
        self,
        filter: EventFilter,
        callback: Callable[[Event], Awaitable[None]],
    ) -> str:
        """Subscribe to events matching the filter.

        Creates a per-subscription queue and starts a consumer task.

        Args:
            filter: Criteria to match events against.
            callback: Async callable invoked with each matching event.

        Returns:
            A subscription ID string.

        """
        sub_id = uuid.uuid4().hex
        sub = _SubscriptionState(
            id=sub_id,
            event_filter=filter,
            callback=callback,
            queue=asyncio.Queue(maxsize=self._config.max_queue_size),
        )
        sub.task = asyncio.create_task(self._consumer(sub))
        async with self._lock:
            self._subscriptions[sub_id] = sub
        return sub_id

    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription. Cancels the consumer task.

        Args:
            subscription_id: The subscription ID to remove.

        """
        async with self._lock:
            sub = self._subscriptions.pop(subscription_id, None)
        if sub is not None and sub.task is not None:
            sub.task.cancel()
            try:
                await sub.task
            except asyncio.CancelledError:
                pass

    async def drain(self) -> None:
        """Deliver all queued events, then return.

        Waits for all subscription queues to empty. Consumer tasks remain
        alive and blocked on ``queue.get()``, ready for future events.
        """
        while True:
            async with self._lock:
                subscriptions = list(self._subscriptions.values())
            if not any(not sub.queue.empty() for sub in subscriptions):
                break
            self._drain_event.clear()
            try:
                await asyncio.wait_for(self._drain_event.wait(), timeout=0.05)
            except TimeoutError:
                pass

    def history(self, limit: int | None = None) -> list[Event]:
        """Return events from the ring buffer.

        Args:
            limit: Maximum events to return. None returns all.

        Returns:
            List of events in chronological order.

        """
        if limit is None:
            return list(self._history)
        return list(self._history)[-limit:]

    def stats(self) -> EventBusStats:
        """Return current bus statistics."""
        queue_depth = sum(sub.queue.qsize() for sub in self._subscriptions.values())
        return EventBusStats(
            events_published=self._published_count,
            events_delivered=self._delivered_count,
            subscriptions_active=len(self._subscriptions),
            subscriptions_dropped=self._dropped_count,
            queue_depth=queue_depth,
        )

    async def _consumer(self, sub: _SubscriptionState) -> None:
        """Consume events from a subscription's queue and invoke the callback."""
        try:
            while True:
                event = await sub.queue.get()
                try:
                    await sub.callback(event)
                except Exception:
                    logger.exception(
                        "Subscriber %s raised exception handling event %s",
                        sub.id,
                        event.event_id,
                    )
                finally:
                    sub.delivered += 1
                    self._delivered_count += 1
                    sub.queue.task_done()
                    self._drain_event.set()
        except asyncio.CancelledError:
            return

    async def _stats_emitter(self) -> None:
        """Periodically emit EventBusStats as a bus event."""
        try:
            while self._running:
                await asyncio.sleep(5.0)
                if not self._running:
                    break
                current_stats = self.stats()
                stat_event = SemanticEvent.create(
                    type=EventType.HEALTH_CHECK,
                    source="event_bus",
                    payload={
                        "event": "event_bus.stats",
                        "published": current_stats.events_published,
                        "delivered": current_stats.events_delivered,
                        "active": current_stats.subscriptions_active,
                        "dropped": current_stats.subscriptions_dropped,
                        "queue_depth": current_stats.queue_depth,
                    },
                )
                await self.publish(stat_event)
        except asyncio.CancelledError:
            return
