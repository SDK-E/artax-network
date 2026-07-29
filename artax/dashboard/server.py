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

from ..events.types import Event
from .config import DashboardConfig

logger = logging.getLogger(__name__)

try:
    import websockets  # type: ignore[import-not-found]
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
            raise DriverError("dashboard", msg, recoverable=False)

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
        }

    async def _handle_client(self, ws: Any) -> None:
        """Handle a single WebSocket client connection."""
        self._clients.add(ws)
        logger.info("Client connected (%d total)", self.client_count)

        try:
            # Send event history on connect
            history = self.get_event_history(limit=50)
            if history:
                await ws.send(
                    json.dumps({"type": "history", "events": history}),
                )

            # Keep connection alive, listen for close
            async for _ in ws:
                pass
        except (RuntimeError, OSError):
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
                if client.open:
                    await client.send(data)
            except (RuntimeError, OSError):
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
