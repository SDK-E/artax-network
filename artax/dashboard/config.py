"""Dashboard server configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardConfig:
    """Configuration for the Dashboard server.

    Attributes:
        host: Bind address for the dashboard server.
        port: HTTP port for the dashboard.
        ws_port: WebSocket port for real-time updates.
        event_history_size: Maximum number of events retained in history.
        broadcast_interval_ms: Interval in milliseconds for state broadcasts.

    """

    host: str = "127.0.0.1"
    port: int = 8080
    ws_port: int = 8081
    event_history_size: int = 100
    broadcast_interval_ms: int = 250
