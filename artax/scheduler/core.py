"""Scheduler protocol and in-memory implementation.

The scheduler manages priority queuing, delayed event delivery, and
tick-based processing. It ensures events are processed with appropriate
priorities and timing.
"""

from __future__ import annotations

import enum
import heapq
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Protocol

from ..events.bus import EventBus
from ..events.types import Event, EventType, SemanticEvent

logger = logging.getLogger(__name__)


class Priority(enum.IntEnum):
    """Priority levels for scheduled events.

    Lower numeric values indicate higher priority. URGENT events are
    dispatched before HIGH, HIGH before MEDIUM, MEDIUM before LOW.
    """

    URGENT = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class ScheduleStatus(str, enum.Enum):
    """Lifecycle status of a scheduled entry."""

    PENDING = "pending"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ScheduleEntry:
    """A single item in the scheduler's pending queue.

    Attributes:
        entry_id: Unique identifier (UUID hex string).
        event: The event to deliver when the entry matures.
        priority: Dispatch priority.
        scheduled_at: Monotonic timestamp when this entry was scheduled.
        deliver_at: Monotonic timestamp when this entry becomes eligible.
        status: Current lifecycle status.

    """

    entry_id: str
    event: Event
    priority: Priority
    scheduled_at: float
    deliver_at: float
    status: ScheduleStatus = ScheduleStatus.PENDING


@dataclass
class SchedulerConfig:
    """Configuration for a Scheduler instance.

    Attributes:
        tick_interval_ms: Milliseconds between ticks (informational for callers).
        max_queue_size: Maximum pending entries before dropping new ones.
        emergency_drain: Deliver all pending events on stop().
        queue_depth_threshold: Emit scheduler.queue.depth when exceeded.

    """

    tick_interval_ms: int = 10
    max_queue_size: int = 10000
    emergency_drain: bool = True
    queue_depth_threshold: int = 1000


@dataclass
class SchedulerStatus:
    """Point-in-time snapshot of scheduler state.

    Attributes:
        paused: Whether the scheduler is paused.
        pending_urgent: Count of pending URGENT entries.
        pending_high: Count of pending HIGH entries.
        pending_medium: Count of pending MEDIUM entries.
        pending_low: Count of pending LOW entries.
        total_pending: Total pending entries across all priorities.
        total_scheduled: Total entries scheduled since start.
        total_delivered: Total entries delivered since start.
        total_cancelled: Total entries cancelled since start.
        tick_count: Number of ticks processed since start.

    """

    paused: bool = False
    pending_urgent: int = 0
    pending_high: int = 0
    pending_medium: int = 0
    pending_low: int = 0
    total_pending: int = 0
    total_scheduled: int = 0
    total_delivered: int = 0
    total_cancelled: int = 0
    tick_count: int = 0


class Scheduler(Protocol):
    """Structural protocol for scheduler implementations.

    The runtime interacts with scheduling exclusively through this interface.
    """

    async def start(self) -> None:
        """Begin the tick loop."""
        ...

    async def stop(self) -> None:
        """Stop the tick loop. Deliver remaining events if emergency_drain."""
        ...

    def schedule(
        self,
        event: Event,
        priority: Priority = Priority.MEDIUM,
        delay: float = 0.0,
    ) -> str:
        """Schedule an event for future delivery.

        Args:
            event: The event to schedule.
            priority: Dispatch priority.
            delay: Seconds to wait before delivery. 0 = immediate.

        Returns:
            Entry ID string for cancellation, or empty string if queue full.

        """
        ...

    def cancel(self, entry_id: str) -> bool:
        """Cancel a scheduled event.

        Args:
            entry_id: The entry ID returned by schedule().

        Returns:
            True if found and cancelled, False otherwise.

        """
        ...

    def pause(self) -> None:
        """Pause event processing. Events continue to queue."""
        ...

    def resume(self) -> None:
        """Resume event processing from where it was paused."""
        ...

    async def tick(self) -> None:
        """Process one tick: deliver all matured events in priority order."""
        ...

    def queue_status(self) -> SchedulerStatus:
        """Return current queue state."""
        ...

    @property
    def is_paused(self) -> bool:
        """Whether the scheduler is currently paused."""
        ...

    @property
    def pending_count(self) -> int:
        """Total pending entries across all priorities."""
        ...


class MemoryScheduler:
    """In-memory scheduler backed by a heapq priority queue.

    Events are held in memory and lost on restart. The runtime calls
    ``tick()`` on each loop iteration to deliver matured events.
    """

    def __init__(self, config: SchedulerConfig, event_bus: EventBus) -> None:
        """Initialize the scheduler.

        Args:
            config: Scheduler configuration.
            event_bus: EventBus for publishing delivered events.

        """
        self._config = config
        self._event_bus = event_bus
        self._paused = False
        self._entries: dict[str, ScheduleEntry] = {}
        self._heap: list[tuple[float, int, str]] = []
        self._counter = 0
        self._total_scheduled = 0
        self._total_delivered = 0
        self._total_cancelled = 0
        self._tick_count = 0

    async def start(self) -> None:
        """Initialize the scheduler. No background tasks — runtime calls tick()."""

    async def stop(self) -> None:
        """Stop the scheduler. Deliver remaining events if emergency_drain."""
        if self._config.emergency_drain:
            await self._deliver_all_pending()

    def schedule(
        self,
        event: Event,
        priority: Priority = Priority.MEDIUM,
        delay: float = 0.0,
    ) -> str:
        """Schedule an event for delivery.

        If the queue is full, logs a warning and returns an empty string.
        """
        if len(self._entries) >= self._config.max_queue_size:
            logger.warning(
                "Scheduler queue full (%d entries), dropping event %s",
                len(self._entries),
                getattr(event, "event_id", "unknown"),
            )
            return ""

        entry_id = uuid.uuid4().hex
        now = time.monotonic()
        deliver_at = now + delay

        entry = ScheduleEntry(
            entry_id=entry_id,
            event=event,
            priority=priority,
            scheduled_at=now,
            deliver_at=deliver_at,
        )

        self._entries[entry_id] = entry
        heapq.heappush(self._heap, (deliver_at, self._counter, entry_id))
        self._counter += 1
        self._total_scheduled += 1

        return entry_id

    def cancel(self, entry_id: str) -> bool:
        """Cancel a scheduled event. Returns True if found and cancelled."""
        entry = self._entries.get(entry_id)
        if entry is None or entry.status != ScheduleStatus.PENDING:
            return False

        self._entries[entry_id] = ScheduleEntry(
            entry_id=entry.entry_id,
            event=entry.event,
            priority=entry.priority,
            scheduled_at=entry.scheduled_at,
            deliver_at=entry.deliver_at,
            status=ScheduleStatus.CANCELLED,
        )
        self._total_cancelled += 1

        return True

    def pause(self) -> None:
        """Pause event processing."""
        self._paused = True

    def resume(self) -> None:
        """Resume event processing."""
        self._paused = False

    async def tick(self) -> None:
        """Process one tick: deliver all matured events in priority order."""
        if self._paused:
            return

        now = time.monotonic()
        delivered_this_tick = 0

        # Collect ready entries from the heap
        ready: list[str] = []
        while self._heap:
            deliver_at, _counter, entry_id = self._heap[0]
            if deliver_at > now:
                break
            heapq.heappop(self._heap)
            entry = self._entries.get(entry_id)
            if entry is None or entry.status != ScheduleStatus.PENDING:
                continue
            ready.append(entry_id)

        # Deliver in priority order (IntEnum sorts naturally)
        ready.sort(key=lambda eid: self._entries[eid].priority.value)

        for entry_id in ready:
            entry = self._entries.get(entry_id)
            if entry is None or entry.status != ScheduleStatus.PENDING:
                continue

            # Mark delivered
            self._entries[entry_id] = ScheduleEntry(
                entry_id=entry.entry_id,
                event=entry.event,
                priority=entry.priority,
                scheduled_at=entry.scheduled_at,
                deliver_at=entry.deliver_at,
                status=ScheduleStatus.DELIVERED,
            )

            # Publish to EventBus
            await self._event_bus.publish(entry.event)
            self._total_delivered += 1
            delivered_this_tick += 1

            # Emit delivery event
            delivery_event = SemanticEvent.create(
                type=EventType.CUSTOM,
                source="scheduler",
                payload={
                    "event": "scheduler.event.delivered",
                    "entry_id": entry_id,
                    "priority": entry.priority.name,
                },
            )
            await self._event_bus.publish(delivery_event)

        self._tick_count += 1

        # Emit tick event
        if delivered_this_tick > 0:
            tick_event = SemanticEvent.create(
                type=EventType.SCHEDULE_TICK,
                source="scheduler",
                payload={
                    "event": "scheduler.tick",
                    "delivered": delivered_this_tick,
                    "tick_count": self._tick_count,
                },
            )
            await self._event_bus.publish(tick_event)

        # Emit queue depth if threshold exceeded
        pending = self._count_pending()
        if pending > self._config.queue_depth_threshold:
            depth_event = SemanticEvent.create(
                type=EventType.CUSTOM,
                source="scheduler",
                payload={
                    "event": "scheduler.queue.depth",
                    "pending": pending,
                    "threshold": self._config.queue_depth_threshold,
                },
            )
            await self._event_bus.publish(depth_event)

    def queue_status(self) -> SchedulerStatus:
        """Return current queue state."""
        counts = self._count_by_priority()
        total = sum(counts.values())
        return SchedulerStatus(
            paused=self._paused,
            pending_urgent=counts[Priority.URGENT],
            pending_high=counts[Priority.HIGH],
            pending_medium=counts[Priority.MEDIUM],
            pending_low=counts[Priority.LOW],
            total_pending=total,
            total_scheduled=self._total_scheduled,
            total_delivered=self._total_delivered,
            total_cancelled=self._total_cancelled,
            tick_count=self._tick_count,
        )

    @property
    def is_paused(self) -> bool:
        """Whether the scheduler is currently paused."""
        return self._paused

    @property
    def pending_count(self) -> int:
        """Total pending entries across all priorities."""
        return self._count_pending()

    def _count_pending(self) -> int:
        """Count entries with PENDING status."""
        return sum(1 for e in self._entries.values() if e.status == ScheduleStatus.PENDING)

    def _count_by_priority(self) -> dict[Priority, int]:
        """Count pending entries by priority level."""
        counts = dict.fromkeys(Priority, 0)
        for entry in self._entries.values():
            if entry.status == ScheduleStatus.PENDING:
                counts[entry.priority] += 1
        return counts

    async def _deliver_all_pending(self) -> None:
        """Deliver all remaining pending events (emergency drain)."""
        pending = [e for e in self._entries.values() if e.status == ScheduleStatus.PENDING]
        pending.sort(key=lambda e: (e.deliver_at, e.priority.value))

        for entry in pending:
            self._entries[entry.entry_id] = ScheduleEntry(
                entry_id=entry.entry_id,
                event=entry.event,
                priority=entry.priority,
                scheduled_at=entry.scheduled_at,
                deliver_at=entry.deliver_at,
                status=ScheduleStatus.DELIVERED,
            )
            await self._event_bus.publish(entry.event)
            self._total_delivered += 1

        if pending:
            logger.info("Emergency drain delivered %d pending events", len(pending))
