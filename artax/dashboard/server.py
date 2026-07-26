"""Developer dashboard server for the Artax runtime.

Provides a web-based UI for inspecting runtime state, events, and driver
status. Communicates with the runtime via WebSocket for real-time updates.
"""

from __future__ import annotations


class DashboardServer:
    """Stub web dashboard server.

    Serves a single-page application and maintains WebSocket connections for
    live runtime telemetry. Future implementation will use an ASGI framework
    (e.g. FastAPI or BlackSheep) to serve the dashboard.

    Attributes:
        host: Bind address for the dashboard server.
        port: HTTP port for the dashboard.
        ws_port: WebSocket port for real-time updates.

    """

    def __init__(self, host: str, port: int, ws_port: int) -> None:
        """Initialize the dashboard server.

        Args:
            host: Bind address.
            port: HTTP port number.
            ws_port: WebSocket port number.

        """
        self._host = host
        self._port = port
        self._ws_port = ws_port

    async def start(self) -> None:
        """Start the dashboard HTTP and WebSocket servers.

        Future implementation will bind an ASGI application and begin
        accepting connections.
        """
        raise NotImplementedError

    async def stop(self) -> None:
        """Gracefully shut down the dashboard servers.

        Closes all WebSocket connections and releases the bound ports.
        """
        raise NotImplementedError
