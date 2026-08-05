"""Developer dashboard server for the Artax runtime.

Provides a web-based UI for inspecting runtime state, events, and driver
status. Communicates with clients via WebSocket for real-time updates.

websockets is an optional dependency. Import errors are caught and surfaced
during start().
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from typing import Any

from ..events.types import Event, EventType
from .config import DashboardConfig

logger = logging.getLogger(__name__)

try:
    import websockets
except ImportError:
    websockets = None


class DashboardServer:
    """WebSocket-based dashboard server.

    Accepts client connections over WebSocket and streams runtime events in
    real time. Provides event history queries and a health endpoint.

    Attributes:
        config: Dashboard configuration.

    """

    def __init__(self, config: DashboardConfig | None = None) -> None:
        """Initialize the dashboard server.

        Args:
            config: Dashboard configuration. Uses defaults if None.

        """
        self._config = config or DashboardConfig()
        self._event_history: deque[dict[str, Any]] = deque(
            maxlen=self._config.event_history_size,
        )
        self._clients: set[Any] = set()
        self._ws_server: Any = None
        self._running = False
        self._started_at: float = 0.0
        self._connected_drivers: set[str] = set()
        self._unhealthy_drivers: set[str] = set()

    @property
    def host(self) -> str:
        """Return the bind address."""
        return self._config.host

    @property
    def port(self) -> int:
        """Return the HTTP port."""
        return self._config.port

    @property
    def ws_port(self) -> int:
        """Return the WebSocket port."""
        return self._config.ws_port

    @property
    def running(self) -> bool:
        """Return whether the server is running."""
        return self._running

    @property
    def client_count(self) -> int:
        """Return the number of connected WebSocket clients."""
        return len(self._clients)

    @property
    def connected_drivers(self) -> list[str]:
        """Return the names of currently connected drivers."""
        return sorted(self._connected_drivers)

    @property
    def unhealthy_drivers(self) -> list[str]:
        """Return the names of unhealthy drivers."""
        return sorted(self._unhealthy_drivers)

    @property
    def event_history(self) -> list[dict[str, Any]]:
        """Return the event history as a list."""
        return list(self._event_history)

    async def start(self) -> None:
        """Start the WebSocket server.

        Raises:
            DriverError: If websockets is not installed.

        """
        if websockets is None:
            from ..drivers.base import DriverError

            msg = "websockets not installed. Install with: pip install websockets"
            raise DriverError(msg)

        self._ws_server = await self._start_ws_server()
        self._running = True
        self._started_at = time.monotonic()
        logger.info(
            "Dashboard server started on ws://%s:%d",
            self._config.host,
            self._config.ws_port,
        )

    async def _start_ws_server(self) -> Any:
        """Start the underlying WebSocket server."""
        assert websockets is not None
        return await websockets.serve(
            self._handle_client,
            self._config.host,
            self._config.ws_port,
        )

    async def stop(self) -> None:
        """Gracefully shut down the WebSocket server."""
        if not self._running:
            return

        self._running = False

        if self._ws_server is not None:
            await self._stop_ws_server()
            self._ws_server = None

        for client in list(self._clients):
            try:
                await client.close()
            except (RuntimeError, OSError):
                pass
        self._clients.clear()

        logger.info("Dashboard server stopped")

    async def _stop_ws_server(self) -> None:
        """Stop the underlying WebSocket server."""
        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()

    async def receive_event(self, event: Event) -> None:
        """Receive an event from the runtime's EventBus.

        Stores the event in history and broadcasts it to all connected clients.

        Args:
            event: A semantic event from the runtime.

        """
        event_dict = self._event_to_dict(event)
        self._event_history.append(event_dict)

        self._track_driver_event(event)

        await self._broadcast(event_dict)

    def get_event_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent events from history.

        Args:
            limit: Maximum number of events to return.

        Returns:
            List of event dictionaries, most recent last.

        """
        history = list(self._event_history)
        return history[-limit:]

    async def get_runtime_state(self) -> dict[str, Any]:
        """Return a snapshot of the runtime state.

        Returns:
            Dictionary with state information. The dashboard is read-only,
            so this returns whatever state has been received via events.

        """
        return {
            "uptime": (time.monotonic() - self._started_at if self._started_at else 0.0),
            "client_count": self.client_count,
            "event_count": len(self._event_history),
            "drivers_connected": len(self._connected_drivers),
            "connected_drivers": self.connected_drivers,
            "drivers_unhealthy": len(self._unhealthy_drivers),
            "unhealthy_drivers": self.unhealthy_drivers,
            "memory_keys": self._count_memory_keys(),
        }

    def get_health(self) -> dict[str, Any]:
        """Return dashboard health status.

        Returns:
            Dictionary with health information.

        """
        return {
            "status": "ok",
            "client_count": self.client_count,
            "event_count": len(self._event_history),
            "running": self._running,
            "drivers_connected": len(self._connected_drivers),
            "drivers_unhealthy": len(self._unhealthy_drivers),
        }

    def _track_driver_event(self, event: Event) -> None:
        """Update the connected-driver set from driver lifecycle events.

        Args:
            event: A semantic event from the runtime.

        """
        driver_name = event.payload.get("driver", "unknown")
        if event.type == EventType.DRIVER_CONNECTED:
            self._connected_drivers.add(driver_name)
            self._unhealthy_drivers.discard(driver_name)
        elif event.type == EventType.DRIVER_DISCONNECTED:
            self._connected_drivers.discard(driver_name)
        elif event.type == EventType.DRIVER_UNHEALTHY:
            self._unhealthy_drivers.add(driver_name)

    def _count_memory_keys(self) -> int:
        """Count unique memory keys seen across all history events."""
        keys: set[str] = set()
        for ev in self._event_history:
            if ev.get("type") == EventType.MEMORY_UPDATED.value:
                key = ev.get("payload", {}).get("key")
                if key is not None:
                    keys.add(str(key))
        return len(keys)

    async def _handle_client(self, ws: Any) -> None:
        """Handle a single WebSocket client connection."""
        self._clients.add(ws)
        logger.info("Client connected (%d total)", self.client_count)

        try:
            # Capture state and history before any await so they are
            # consistent — the EventBus consumer may process driver events
            # during an await, making _connected_drivers and _event_history
            # diverge between two separate sends.
            history = self.get_event_history(limit=50)
            drivers_connected = len(self._connected_drivers)
            connected_drivers = self.connected_drivers
            memory_keys = self._count_memory_keys()

            # Send current runtime state so the client has an accurate
            # snapshot of connected drivers even if they were connected
            # before the client joined.
            await ws.send(
                json.dumps(
                    {
                        "type": "state",
                        "uptime": (
                            time.monotonic() - self._started_at if self._started_at else 0.0
                        ),
                        "client_count": self.client_count,
                        "event_count": len(self._event_history),
                        "drivers_connected": drivers_connected,
                        "connected_drivers": connected_drivers,
                        "drivers_unhealthy": len(self._unhealthy_drivers),
                        "unhealthy_drivers": self.unhealthy_drivers,
                        "memory_keys": memory_keys,
                    }
                )
            )

            # Send event history on connect
            if history:
                await ws.send(
                    json.dumps({"type": "history", "events": history}),
                )

            # Keep connection alive, listen for close
            async for _ in ws:
                pass
        except (RuntimeError, OSError, websockets.ConnectionClosed):
            pass
        finally:
            self._remove_client(ws)
            logger.info(
                "Client disconnected (%d total)",
                self.client_count,
            )

    def _remove_client(self, ws: Any) -> None:
        """Remove a client from the connected set."""
        self._clients.discard(ws)

    async def _broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to all connected clients."""
        data = json.dumps(message)
        disconnected: list[Any] = []
        for client in self._clients:
            try:
                await client.send(data)
            except (RuntimeError, OSError, websockets.ConnectionClosed):
                disconnected.append(client)

        for client in disconnected:
            self._remove_client(client)

    @staticmethod
    def _event_to_dict(event: Event) -> dict[str, Any]:
        """Convert a SemanticEvent to a JSON-serializable dictionary."""
        return {
            "type": (event.type.value if hasattr(event.type, "value") else str(event.type)),
            "source": event.source,
            "timestamp": event.timestamp,
            "payload": event.payload,
            "event_id": str(event.event_id),
        }
