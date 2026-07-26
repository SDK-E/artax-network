"""Driver protocol and lifecycle management.

Drivers encapsulate environment interaction (browsers, terminals, APIs) and
translate between raw environment state and Artax events. The runtime never
imports concrete driver code directly; all interaction is via the Driver
protocol.
"""
from __future__ import annotations

import enum
from typing import Protocol

from ..actions.types import Action, ActionResult
from ..events.types import Event


class DriverState(enum.Enum):
    """Lifecycle states of a driver instance."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class Driver(Protocol):
    """Structural protocol for environment drivers.

    Each driver wraps a specific environment (Chromium, terminal, API, etc.)
    and translates low-level observations and actions into Artax events.
    Drivers register themselves with the runtime; they are never hard-coded
    as imports.
    """

    @property
    def name(self) -> str:
        """Human-readable name of this driver instance."""
        ...

    @property
    def environment(self) -> str:
        """Identifier for the environment this driver manages (e.g. 'chromium')."""
        ...

    @property
    def is_connected(self) -> bool:
        """Whether the driver is currently connected to its environment."""
        ...

    async def connect(self) -> None:
        """Establish a connection to the underlying environment.

        Raises:
            ConnectionError: If the environment cannot be reached.
        """
        ...

    async def disconnect(self) -> None:
        """Tear down the connection to the underlying environment.

        Safe to call multiple times; subsequent calls are no-ops.
        """
        ...

    async def observe(self) -> list[Event]:
        """Capture the current state of the environment as a list of events.

        Returns:
            A list of Observation events representing the environment state.
        """
        ...

    async def execute(self, action: Action) -> ActionResult:
        """Execute an action against the environment.

        Args:
            action: The action to perform.

        Returns:
            The result of the action execution.
        """
        ...

    async def health_check(self) -> bool:
        """Probe whether the driver is healthy and responsive.

        Returns:
            True if the driver is operational, False otherwise.
        """
        ...


class DriverConfig(Protocol):
    """Structural protocol for driver-specific configuration objects.

    Each driver implementation defines its own concrete config dataclass
    that satisfies this protocol.
    """

    @property
    def driver_name(self) -> str:
        """Canonical name for this driver configuration."""
        ...
