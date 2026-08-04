"""Driver protocol, base class, and lifecycle management.

Drivers encapsulate environment interaction (browsers, terminals, APIs) and
translate between raw environment state and Artax events. The runtime never
imports concrete driver code directly; all interaction is via the Driver
protocol or BaseDriver ABC.
"""

from __future__ import annotations

import enum
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from ..actions.types import Action, ActionResult
from ..events.bus import EventBus
from ..events.types import Event

logger = logging.getLogger(__name__)


class DriverState(enum.Enum):
    """Lifecycle states of a driver instance."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    UNHEALTHY = "unhealthy"
    ERROR = "error"


@dataclass
class DriverHealth:
    """Health status returned by driver.health_check().

    Attributes:
        state: Current driver lifecycle state.
        message: Human-readable health status message.
        latency_ms: Latency of the health check in milliseconds (measured by runtime).
        last_event_at: Monotonic timestamp of the last event emitted by this driver.
        error_count: Cumulative error count since last connect.

    """

    state: DriverState
    message: str = ""
    latency_ms: float = 0.0
    last_event_at: float | None = None
    error_count: int = 0


class DriverError(Exception):
    """Base exception for driver errors."""


class DriverConnectionError(DriverError):
    """Driver failed to connect."""


class DriverTimeoutError(DriverError):
    """Driver operation timed out."""


class DriverActionError(DriverError):
    """Driver action execution failed."""


class DriverConfig(Protocol):
    """Structural protocol for driver-specific configuration objects.

    Each driver implementation defines its own concrete config dataclass
    that satisfies this protocol.
    """

    @property
    def driver_type(self) -> str:
        """Identifier for the driver implementation (e.g., 'chromium', 'terminal')."""
        ...


class Driver(Protocol):
    """Structural protocol for environment drivers.

    Each driver wraps a specific environment (Chromium, terminal, API, etc.)
    and translates low-level observations and actions into Artax events.
    Drivers register themselves with the runtime; they are never hard-coded
    as imports.
    """

    @property
    def name(self) -> str:
        """Unique name for this driver instance."""
        ...

    @property
    def environment(self) -> str:
        """Identifier for the driver implementation (e.g., 'chromium', 'terminal')."""
        ...

    @property
    def is_connected(self) -> bool:
        """Whether the driver is currently connected."""
        ...

    async def connect(self, event_bus: EventBus) -> None:
        """Connect to the environment. Raise DriverError on failure."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from the environment. Clean up resources."""
        ...

    async def observe(self) -> AsyncIterator[Event]:
        """Yield events from the environment. Runs continuously while connected."""
        ...

    async def execute(self, action: Action) -> ActionResult:
        """Execute an action in the environment. Return result or error."""
        ...

    async def health_check(self) -> DriverHealth:
        """Check driver and environment health. Return health status."""
        ...


class BaseDriver(ABC):
    """Abstract base class providing common driver functionality.

    Subclasses must implement _do_connect, _do_disconnect, observe, and execute.
    The base class manages state transitions, error counting, and health checks.
    """

    def __init__(self, name: str, config: DriverConfig) -> None:
        """Initialize the base driver.

        Args:
            name: Unique name for this driver instance.
            config: Driver configuration satisfying the DriverConfig protocol.

        """
        self._name = name
        self._config = config
        self._state = DriverState.DISCONNECTED
        self._event_bus: EventBus | None = None
        self._error_count = 0
        self._last_event_at: float | None = None

    @property
    def name(self) -> str:
        """Return the unique name of this driver instance."""
        return self._name

    @property
    def environment(self) -> str:
        """Return the driver type identifier."""
        return self._config.driver_type

    @property
    def is_connected(self) -> bool:
        """Return whether the driver is currently connected."""
        return self._state == DriverState.CONNECTED

    @property
    def state(self) -> DriverState:
        """Return the current lifecycle state."""
        return self._state

    @property
    def error_count(self) -> int:
        """Return the cumulative error count since last connect."""
        return self._error_count

    async def connect(self, event_bus: EventBus) -> None:
        """Connect to the environment. Manages state transitions."""
        self._state = DriverState.CONNECTING
        self._event_bus = event_bus
        try:
            await self._do_connect()
            self._state = DriverState.CONNECTED
            logger.info("Driver '%s' connected", self._name)
        except DriverError:
            self._state = DriverState.ERROR
            self._error_count += 1
            raise
        except Exception as exc:
            self._state = DriverState.ERROR
            self._error_count += 1
            raise DriverError(self._name, str(exc)) from exc

    async def disconnect(self) -> None:
        """Disconnect from the environment. Safe to call multiple times."""
        if self._state == DriverState.DISCONNECTED:
            return
        try:
            await self._do_disconnect()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Driver '%s' disconnect error: %s", self._name, exc)
        finally:
            self._state = DriverState.DISCONNECTED
            self._event_bus = None
            logger.info("Driver '%s' disconnected", self._name)

    async def health_check(self) -> DriverHealth:
        """Return current health status. Runtime wraps this to measure latency_ms."""
        return DriverHealth(
            state=self._state,
            error_count=self._error_count,
            last_event_at=self._last_event_at,
        )

    async def _publish_event(self, event: Event) -> None:
        """Publish an event to the bus if connected."""
        if self._event_bus is not None:
            await self._event_bus.publish(event)

    @abstractmethod
    async def _do_connect(self) -> None:
        """Environment-specific connection logic."""
        ...

    @abstractmethod
    async def _do_disconnect(self) -> None:
        """Environment-specific disconnection logic."""
        ...

    @abstractmethod
    async def observe(self) -> AsyncIterator[Event]:
        """Yield events from the environment."""
        ...

    @abstractmethod
    async def execute(self, action: Action) -> ActionResult:
        """Execute an action in the environment."""
        ...
