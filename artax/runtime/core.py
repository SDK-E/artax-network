"""Core runtime orchestration for Artax Network.

The Runtime class serves as the central coordinator, managing the lifecycle of
drivers, memory stores, schedulers, and the event bus. It owns the main event
loop and wires subsystems together without implementing their internals.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import signal
import time
from dataclasses import dataclass, field
from typing import Any

from ..dashboard.config import DashboardConfig
from ..drivers.base import Driver
from ..events.bus import EventBus, MemoryEventBus
from ..events.types import EventBusConfig, EventFilter, EventType, SemanticEvent
from ..memory.base import InMemoryStore, MemoryConfig, SQLiteMemoryStore, WorkingMemory
from ..scheduler.core import MemoryScheduler, Scheduler, SchedulerConfig

logger = logging.getLogger(__name__)


class RuntimeState(enum.Enum):
    """Lifecycle state of the Runtime."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class RuntimeConfig:
    """Configuration for the Runtime.

    Attributes:
        shutdown_timeout: Seconds to wait for each subsystem to stop
            before proceeding to the next.
        drivers: List of driver configurations (unused, drivers are
            registered directly).
        event_bus: Event bus configuration.
        memory: Memory store configuration.
        scheduler: Scheduler configuration.
        dashboard: Dashboard server configuration. Defaults to a basic
            configuration when not explicitly provided.

    """

    shutdown_timeout: float = 5.0
    drivers: list[object] = field(default_factory=list)
    event_bus: EventBusConfig = field(default_factory=EventBusConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)


@dataclass
class RuntimeStatus:
    """Point-in-time snapshot of runtime state.

    Attributes:
        state: Current lifecycle state.
        uptime: Seconds since the runtime entered the RUNNING state.
        drivers_connected: Number of drivers in the CONNECTED state.
        events_published: Total events published through the runtime's
            event bus since startup.

    """

    state: RuntimeState = RuntimeState.STOPPED
    uptime: float = 0.0
    drivers_connected: int = 0
    events_published: int = 0


class Runtime:
    """Central orchestrator for Artax Network.

    Manages the lifecycle of all subsystems in a defined order:

    - **Startup**: EventBus → Memory → Scheduler → Drivers
    - **Shutdown**: Drivers → Scheduler → Memory → EventBus

    The Runtime does not implement subsystem internals. It creates instances,
    wires them together, and delegates all work to them.

    Usage::

        runtime = Runtime(RuntimeConfig())
        runtime.register_driver(my_driver)
        await runtime.run_forever()

    """

    def __init__(
        self,
        config: RuntimeConfig | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Initialize the Runtime.

        Args:
            config: Runtime configuration. Uses defaults if None.
            event_bus: Event bus instance. Creates a MemoryEventBus if None.

        """
        self._config = config or RuntimeConfig()
        self._state = RuntimeState.STOPPED
        self._drivers: list[Driver] = []
        self._driver_names: dict[str, Driver] = {}
        self._event_bus: EventBus | None = event_bus
        self._memory: WorkingMemory | None = None
        self._scheduler: Scheduler | None = None
        self._dashboard: Any = None
        self._dashboard_task: asyncio.Task[None] | None = None
        self._started_at: float = 0.0
        self._run_task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None

    @property
    def state(self) -> RuntimeState:
        """Return the current runtime lifecycle state."""
        return self._state

    @property
    def event_bus(self) -> EventBus:
        """Return the event bus. Raises RuntimeError if not started."""
        if self._event_bus is None:
            msg = "EventBus not available: runtime not started"
            raise RuntimeError(msg)
        return self._event_bus

    @property
    def memory(self) -> WorkingMemory:
        """Return the memory store. Raises RuntimeError if not started."""
        if self._memory is None:
            msg = "Memory not available: runtime not started"
            raise RuntimeError(msg)
        return self._memory

    @property
    def scheduler(self) -> Scheduler:
        """Return the scheduler. Raises RuntimeError if not started."""
        if self._scheduler is None:
            msg = "Scheduler not available: runtime not started"
            raise RuntimeError(msg)
        return self._scheduler

    @property
    def drivers(self) -> list[Driver]:
        """Return the list of registered drivers."""
        return list(self._drivers)

    def register_driver(self, driver: Driver) -> None:
        """Register a driver with the runtime.

        The driver will be connected during ``start()`` and disconnected during
        ``stop()``. Duplicate registrations are silently ignored.

        Args:
            driver: A driver instance conforming to the Driver protocol.

        """
        if driver.name not in self._driver_names:
            self._drivers.append(driver)
            self._driver_names[driver.name] = driver
            logger.info("Registered driver: %s", driver.name)

    def register_memory(self, memory: WorkingMemory) -> None:
        """Register a working memory store with the runtime.

        Only one memory store may be active at a time; subsequent calls replace
        the previous store.

        Args:
            memory: A working memory instance.

        """
        self._memory = memory
        logger.info("Registered memory store: %s", type(memory).__name__)

    def register_event_bus(self, event_bus: EventBus) -> None:
        """Register an event bus with the runtime.

        Only one event bus may be active at a time; subsequent calls replace
        the previous event bus.

        Args:
            event_bus: An event bus instance.

        """
        self._event_bus = event_bus
        logger.info("Registered event bus: %s", type(event_bus).__name__)

    def register_scheduler(self, scheduler: Scheduler) -> None:
        """Register a scheduler with the runtime.

        Only one scheduler may be active at a time; subsequent calls replace
        the previous scheduler.

        Args:
            scheduler: A scheduler instance.

        """
        self._scheduler = scheduler
        logger.info("Registered scheduler: %s", type(scheduler).__name__)

    async def _start_dashboard(self) -> None:
        cfg = self._config.dashboard
        try:
            from ..dashboard.server import DashboardServer

            self._dashboard = DashboardServer(cfg)
            await self._dashboard.start()
            assert self._event_bus is not None
            await self._event_bus.subscribe(
                EventFilter(),
                self._dashboard.receive_event,
            )
            logger.info("Dashboard started on ws://%s:%d", cfg.host, cfg.ws_port)
        except Exception:
            logger.exception("Dashboard failed to start")
            self._dashboard = None

    async def _stop_dashboard(self) -> None:
        if self._dashboard is None:
            return
        try:
            if self._dashboard_task is not None:
                self._dashboard_task.cancel()
            await asyncio.wait_for(
                self._dashboard.stop(),
                timeout=self._config.shutdown_timeout,
            )
        except (TimeoutError, asyncio.CancelledError):
            logger.warning("Dashboard stop timed out or was cancelled")
        self._dashboard = None
        self._dashboard_task = None
        logger.info("Dashboard stopped")

    def status(self) -> RuntimeStatus:
        """Return a point-in-time snapshot of runtime state."""
        uptime = 0.0
        events_published = 0
        drivers_connected = 0

        if self._state == RuntimeState.RUNNING and self._started_at > 0:
            uptime = time.monotonic() - self._started_at

        if self._event_bus is not None:
            bus_stats = self._event_bus.stats()
            events_published = bus_stats.events_published

        for driver in self._drivers:
            if driver.is_connected:
                drivers_connected += 1

        return RuntimeStatus(
            state=self._state,
            uptime=uptime,
            events_published=events_published,
            drivers_connected=drivers_connected,
        )

    async def start(self) -> None:
        """Initialize all subsystems and enter the running state.

        Startup order: EventBus → Memory → Scheduler → Drivers.

        Raises:
            RuntimeError: If already running or starting.

        """
        if self._state not in (RuntimeState.STOPPED, RuntimeState.ERROR):
            msg = f"Cannot start: state is {self._state.value}"
            raise RuntimeError(msg)

        self._state = RuntimeState.STARTING
        logger.info("Runtime starting")

        try:
            await self._start_event_bus()
            await self._start_memory()
            await self._start_scheduler()
            await self._start_dashboard()
            await self._connect_drivers()

            self._state = RuntimeState.RUNNING
            self._started_at = time.monotonic()
            await self._publish_event(EventType.RUNTIME_STARTED)
            logger.info("Runtime started")
        except Exception:
            self._state = RuntimeState.ERROR
            logger.exception("Runtime failed to start")
            raise

    async def _start_event_bus(self) -> None:
        if self._event_bus is None:
            self._event_bus = MemoryEventBus(config=self._config.event_bus)
        await self._event_bus.start()
        logger.info("EventBus started")

    async def _start_memory(self) -> None:
        assert self._event_bus is not None
        backend_cls = {"sqlite": SQLiteMemoryStore}.get(self._config.memory.backend, InMemoryStore)
        memory = backend_cls(config=self._config.memory, event_bus=self._event_bus)
        await memory.start()
        self._memory = memory
        logger.info("Memory started (backend=%s)", self._config.memory.backend)

    async def _start_scheduler(self) -> None:
        assert self._event_bus is not None
        if self._scheduler is None:
            self._scheduler = MemoryScheduler(
                config=self._config.scheduler, event_bus=self._event_bus
            )
        await self._scheduler.start()
        logger.info("Scheduler started")

    async def _connect_drivers(self) -> None:
        assert self._event_bus is not None
        for driver in self._drivers:
            try:
                self._state = RuntimeState.STARTING
                await driver.connect(self._event_bus)
                event = SemanticEvent.create(
                    type=EventType.DRIVER_CONNECTED,
                    source="runtime",
                    payload={"driver": driver.name},
                )
                await self._event_bus.publish(event)
                logger.info("Driver '%s' connected", driver.name)
            except Exception:
                logger.exception("Driver '%s' failed to connect", driver.name)
                event = SemanticEvent.create(
                    type=EventType.DRIVER_UNHEALTHY,
                    source="runtime",
                    payload={"driver": driver.name},
                )
                await self._event_bus.publish(event)

    async def stop(self) -> None:
        """Gracefully shut down all subsystems in reverse order.

        Shutdown order: Drivers → Scheduler → Memory → EventBus.
        Safe to call multiple times; subsequent calls are no-ops.
        """
        if self._state in (RuntimeState.STOPPED, RuntimeState.STOPPING):
            return

        self._state = RuntimeState.STOPPING
        logger.info("Runtime stopping")

        if self._stop_event is not None:
            self._stop_event.set()

        try:
            await self._publish_event(EventType.RUNTIME_STOPPING)
            await self._disconnect_drivers()
            await self._stop_scheduler()
            await self._stop_dashboard()
            await self._stop_memory()
            await self._stop_event_bus()
        except Exception:
            logger.exception("Error during shutdown")

        self._state = RuntimeState.STOPPED
        logger.info("Runtime stopped")

    async def _publish_event(
        self,
        event_type: EventType,
        payload: dict[str, object] | None = None,
    ) -> None:
        if self._event_bus is not None:
            event = SemanticEvent.create(
                type=event_type,
                source="runtime",
                payload=payload or {"timestamp": time.monotonic()},
            )
            await self._event_bus.publish(event)

    async def _disconnect_drivers(self) -> None:
        for driver in reversed(self._drivers):
            try:
                await asyncio.wait_for(
                    driver.disconnect(),
                    timeout=self._config.shutdown_timeout,
                )
                if self._event_bus is not None:
                    event = SemanticEvent.create(
                        type=EventType.DRIVER_DISCONNECTED,
                        source="runtime",
                        payload={"driver": driver.name},
                    )
                    await self._event_bus.publish(event)
                logger.info("Driver '%s' disconnected", driver.name)
            except TimeoutError:
                logger.warning("Driver '%s' disconnect timed out", driver.name)
            except OSError as exc:
                logger.warning("Driver '%s' disconnect error: %s", driver.name, exc)

    async def _stop_scheduler(self) -> None:
        if self._scheduler is not None:
            try:
                await asyncio.wait_for(
                    self._scheduler.stop(),
                    timeout=self._config.shutdown_timeout,
                )
            except TimeoutError:
                logger.warning("Scheduler stop timed out")
            logger.info("Scheduler stopped")

    async def _stop_memory(self) -> None:
        if self._memory is not None:
            try:
                await asyncio.wait_for(
                    self._memory.stop(),
                    timeout=self._config.shutdown_timeout,
                )
            except TimeoutError:
                logger.warning("Memory stop timed out")
            logger.info("Memory stopped")

    async def _stop_event_bus(self) -> None:
        if self._event_bus is not None:
            try:
                await asyncio.wait_for(
                    self._event_bus.drain(),
                    timeout=self._config.shutdown_timeout,
                )
            except TimeoutError:
                logger.warning("EventBus drain timed out")
            try:
                await asyncio.wait_for(
                    self._event_bus.stop(),
                    timeout=self._config.shutdown_timeout,
                )
            except TimeoutError:
                logger.warning("EventBus stop timed out")
            logger.info("EventBus stopped")

    async def run_forever(self) -> None:
        """Start the runtime and block until ``stop()`` is called.

        Calls ``start()`` if not already running, then blocks on the asyncio
        event loop. On SIGINT/SIGTERM, initiates graceful shutdown.
        """
        if self._state != RuntimeState.RUNNING:
            await self.start()

        self._run_task = asyncio.current_task()
        self._stop_event = asyncio.Event()

        loop = asyncio.get_running_loop()

        def _signal_handler() -> None:
            logger.info("Received shutdown signal")
            assert self._stop_event is not None
            loop.call_soon_threadsafe(self._stop_event.set)

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)

        try:
            await self._stop_event.wait()
        finally:
            await self.stop()
