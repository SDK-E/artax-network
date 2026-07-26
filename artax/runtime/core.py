"""Core runtime orchestration for Artax Network.

The Runtime class serves as the central coordinator, managing the lifecycle of
drivers, memory stores, schedulers, and the event bus. It owns the main event
loop and wires subsystems together without implementing their internals.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass

from ..drivers.base import Driver
from ..events.bus import EventBus
from ..memory.base import WorkingMemory
from ..scheduler.core import Scheduler

logger = logging.getLogger(__name__)


class RuntimeState(enum.Enum):
    """Lifecycle states of the Artax runtime."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class RuntimeConfig:
    """Configuration for the Artax runtime instance.

    Attributes:
        log_level: Logging verbosity level (debug, info, warning, error, critical).
        host: Bind address for the HTTP API server.
        port: Port number for the HTTP API server.
        ws_port: Port number for the WebSocket server.

    """

    log_level: str = "info"
    host: str = "0.0.0.0"
    port: int = 8080
    ws_port: int = 8081


class Runtime:
    """Central orchestrator for the Artax event-driven runtime.

    The Runtime owns the core subsystems -- event bus, memory, scheduler, and
    driver registry -- and coordinates their lifecycle. Drivers register
    themselves after construction; they are never imported directly by the
    runtime module, preserving clean dependency direction.

    Attributes:
        config: Immutable runtime configuration.

    """

    def __init__(self, config: RuntimeConfig) -> None:
        """Initialize the runtime with the given configuration.

        Args:
            config: Runtime configuration parameters.

        """
        self._config = config
        self._state = RuntimeState.STOPPED
        self._drivers: list[Driver] = []
        self._memory: WorkingMemory | None = None
        self._scheduler: Scheduler | None = None
        self._event_bus: EventBus | None = None

    @property
    def event_bus(self) -> EventBus:
        """Return the runtime event bus instance.

        Raises:
            RuntimeError: If the event bus has not been initialized.

        """
        if self._event_bus is None:
            raise RuntimeError("Event bus not initialized")
        return self._event_bus

    @property
    def state(self) -> RuntimeState:
        """Return the current runtime lifecycle state."""
        return self._state

    def register_driver(self, driver: Driver) -> None:
        """Register a driver with the runtime.

        The driver will be connected during ``start()`` and disconnected during
        ``stop()``. Duplicate registrations are silently ignored.

        Args:
            driver: A driver instance conforming to the Driver protocol.

        """
        self._drivers.append(driver)
        logger.info("Registered driver: %s", driver.name)

    def register_memory(self, memory: WorkingMemory) -> None:
        """Register a working memory store with the runtime.

        Only one memory store may be active at a time; subsequent calls replace
        the previous store.

        Args:
            memory: A working memory instance conforming to the WorkingMemory protocol.

        """
        self._memory = memory
        logger.info("Registered memory store: %s", type(memory).__name__)

    def register_scheduler(self, scheduler: Scheduler) -> None:
        """Register a scheduler with the runtime.

        Only one scheduler may be active at a time; subsequent calls replace
        the previous scheduler.

        Args:
            scheduler: A scheduler instance conforming to the Scheduler protocol.

        """
        self._scheduler = scheduler
        logger.info("Registered scheduler: %s", type(scheduler).__name__)

    async def start(self) -> None:
        """Transition the runtime from STOPPED to RUNNING.

        Initializes the event bus, connects all registered drivers, and starts
        the main event loop. If any driver fails to connect, the runtime
        transitions to ERROR state.

        Raises:
            RuntimeError: If the runtime is already running or starting.

        """
        raise NotImplementedError

    async def stop(self) -> None:
        """Gracefully shut down the runtime.

        Drains the event bus, disconnects all drivers, and transitions to
        STOPPED. Safe to call multiple times; subsequent calls are no-ops.

        Raises:
            RuntimeError: If the runtime is not running.

        """
        raise NotImplementedError

    async def run_forever(self) -> None:
        """Block and process events until ``stop()`` is called.

        This is the main event loop. It calls ``start()`` if not already
        running, then loops on scheduler ticks and event bus processing until
        the runtime is stopped or encounters an error.
        """
        raise NotImplementedError


def cli() -> None:
    """Entry point for the ``artax`` command-line interface.

    Parses command-line arguments, constructs a RuntimeConfig, and starts
    the runtime. This function is intended to be referenced as a console
    script in ``pyproject.toml``.
    """
    raise NotImplementedError
