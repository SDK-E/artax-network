"""Tests for DashboardServer.

Defines the expected behaviour of the dashboard: WebSocket event streaming,
health endpoint, event history queries, and state snapshots.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from artax.dashboard.config import DashboardConfig
from artax.dashboard.server import DashboardServer
from artax.drivers.base import DriverError
from artax.events.types import EventType, SemanticEvent


class _EmptyAsyncIterator:
    """Mock async iterator that yields nothing."""

    def __aiter__(self) -> AsyncIterator[str]:
        return self

    async def __anext__(self) -> str:
        raise StopAsyncIteration


# ---------------------------------------------------------------------------
# DashboardConfig
# ---------------------------------------------------------------------------


class TestDashboardConfig:
    def test_defaults(self) -> None:
        config = DashboardConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 8080
        assert config.ws_port == 8081
        assert config.event_history_size == 100
        assert config.broadcast_interval_ms == 250

    def test_custom_values(self) -> None:
        config = DashboardConfig(
            host="0.0.0.0",
            port=9000,
            ws_port=9001,
            event_history_size=500,
            broadcast_interval_ms=100,
        )
        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.ws_port == 9001
        assert config.event_history_size == 500
        assert config.broadcast_interval_ms == 100


# ---------------------------------------------------------------------------
# DashboardServer Instantiation
# ---------------------------------------------------------------------------


class TestDashboardServerInstantiation:
    def test_creates_with_config(self) -> None:
        config = DashboardConfig()
        server = DashboardServer(config=config)
        assert server.host == "127.0.0.1"
        assert server.port == 8080
        assert server.ws_port == 8081

    def test_initial_state_not_running(self) -> None:
        config = DashboardConfig()
        server = DashboardServer(config=config)
        assert server.running is False

    def test_client_count_zero_initially(self) -> None:
        config = DashboardConfig()
        server = DashboardServer(config=config)
        assert server.client_count == 0


# ---------------------------------------------------------------------------
# Start / Stop Lifecycle
# ---------------------------------------------------------------------------


class TestDashboardServerLifecycle:
    async def test_start_and_stop(self) -> None:
        config = DashboardConfig()
        server = DashboardServer(config=config)

        mock_ws_server = AsyncMock()
        with (
            patch.object(
                type(server),
                "_start_ws_server",
                new_callable=AsyncMock,
                return_value=mock_ws_server,
            ),
            patch("artax.dashboard.server.websockets", MagicMock()),
        ):
            await server.start()
            assert server.running is True

        with patch.object(type(server), "_stop_ws_server", new_callable=AsyncMock):
            await server.stop()
            assert server.running is False

    async def test_start_binds_websocket_server(self) -> None:
        config = DashboardConfig(ws_port=9001)
        server = DashboardServer(config=config)

        with (
            patch.object(type(server), "_start_ws_server", new_callable=AsyncMock) as mock_start,
            patch("artax.dashboard.server.websockets", MagicMock()),
        ):
            mock_start.return_value = AsyncMock()
            await server.start()
            mock_start.assert_called_once()

    async def test_stop_when_not_started(self) -> None:
        config = DashboardConfig()
        server = DashboardServer(config=config)
        await server.stop()
        assert server.running is False

    async def test_stop_closes_websocket_server(self) -> None:
        config = DashboardConfig()
        server = DashboardServer(config=config)

        mock_ws_server = AsyncMock()
        mock_ws_server.close = MagicMock()
        server._ws_server = mock_ws_server
        server._running = True

        await server.stop()
        mock_ws_server.close.assert_called_once()
        assert server.running is False


# ---------------------------------------------------------------------------
# Event Reception (from EventBus)
# ---------------------------------------------------------------------------


class TestDashboardEventReception:
    async def test_receive_event_stores_in_history(self) -> None:
        config = DashboardConfig(event_history_size=5)
        server = DashboardServer(config=config)

        event = SemanticEvent.create(
            type=EventType.PAGE_LOADED,
            source="chromium",
            payload={"url": "https://example.com"},
        )
        await server.receive_event(event)
        assert len(server.event_history) == 1

    async def test_event_history_bounded(self) -> None:
        config = DashboardConfig(event_history_size=3)
        server = DashboardServer(config=config)

        for i in range(5):
            event = SemanticEvent.create(
                type=EventType.DOM_CHANGED,
                source="chromium",
                payload={"iteration": i},
            )
            await server.receive_event(event)

        assert len(server.event_history) == 3

    async def test_receive_event_broadcasts_to_clients(self) -> None:
        config = DashboardConfig()
        server = DashboardServer(config=config)

        mock_ws = AsyncMock()
        server._clients.add(mock_ws)

        event = SemanticEvent.create(
            type=EventType.PAGE_LOADED,
            source="chromium",
            payload={"url": "https://example.com"},
        )
        await server.receive_event(event)

        mock_ws.send.assert_called_once()
        sent_data = json.loads(mock_ws.send.call_args[0][0])
        assert sent_data["type"] == "page_loaded"
        assert sent_data["source"] == "chromium"

    async def test_receive_event_handles_broken_client(self) -> None:
        config = DashboardConfig()
        server = DashboardServer(config=config)

        mock_ws = AsyncMock()
        mock_ws.send.side_effect = OSError("Connection reset")
        server._clients.add(mock_ws)

        event = SemanticEvent.create(
            type=EventType.PAGE_LOADED,
            source="chromium",
            payload={},
        )
        await server.receive_event(event)

    async def test_event_history_returns_recent_events(self) -> None:
        config = DashboardConfig(event_history_size=100)
        server = DashboardServer(config=config)

        for i in range(3):
            event = SemanticEvent.create(
                type=EventType.PAGE_LOADED,
                source="chromium",
                payload={"i": i},
            )
            await server.receive_event(event)

        history = server.get_event_history(limit=2)
        assert len(history) == 2
        assert history[-1]["payload"]["i"] == 2


# ---------------------------------------------------------------------------
# Client Handling
# ---------------------------------------------------------------------------


class TestDashboardClientHandling:
    async def test_client_connect_increments_count(self) -> None:
        config = DashboardConfig()
        server = DashboardServer(config=config)

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = MagicMock(return_value=_EmptyAsyncIterator())
        await server._handle_client(mock_ws)
        assert server.client_count == 0

    async def test_client_receives_event_history_on_connect(self) -> None:
        config = DashboardConfig(event_history_size=10)
        server = DashboardServer(config=config)

        event = SemanticEvent.create(
            type=EventType.PAGE_LOADED,
            source="chromium",
            payload={},
        )
        await server.receive_event(event)

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = MagicMock(return_value=_EmptyAsyncIterator())
        await server._handle_client(mock_ws)

        # First message is "state", second is "history"
        assert mock_ws.send.await_count == 2
        history_data = json.loads(mock_ws.send.call_args_list[1][0][0])
        assert history_data["type"] == "history"
        assert len(history_data["events"]) == 1

    async def test_disconnect_removes_client(self) -> None:
        config = DashboardConfig()
        server = DashboardServer(config=config)

        mock_ws = AsyncMock()
        server._clients.add(mock_ws)
        assert server.client_count == 1

        server._remove_client(mock_ws)
        assert server.client_count == 0


# ---------------------------------------------------------------------------
# State Queries
# ---------------------------------------------------------------------------


class TestDashboardStateQueries:
    async def test_get_runtime_state_returns_snapshot(self) -> None:
        config = DashboardConfig()
        server = DashboardServer(config=config)

        state = await server.get_runtime_state()
        assert "uptime" in state
        assert "client_count" in state
        assert "event_count" in state

    def test_health_endpoint_returns_ok(self) -> None:
        config = DashboardConfig()
        server = DashboardServer(config=config)

        health = server.get_health()
        assert health["status"] == "ok"
        assert "client_count" in health
        assert "event_count" in health
        assert health["running"] is False


# ---------------------------------------------------------------------------
# WebSocket Server Start/Stop (Real websockets)
# ---------------------------------------------------------------------------


class TestDashboardWebSocketIntegration:
    async def test_start_calls_websockets_serve(self) -> None:
        config = DashboardConfig(ws_port=9001)
        server = DashboardServer(config=config)

        mock_ws_server = AsyncMock()
        mock_ws_module = MagicMock()
        mock_ws_module.serve = AsyncMock(return_value=mock_ws_server)

        with patch("artax.dashboard.server.websockets", mock_ws_module):
            await server.start()
            mock_ws_module.serve.assert_called_once()
            # serve(handler, host, port)
            args = mock_ws_module.serve.call_args
            assert args[0][2] == 9001

    async def test_stop_closes_server(self) -> None:
        config = DashboardConfig()
        server = DashboardServer(config=config)

        mock_ws_server = AsyncMock()
        mock_ws_server.close = MagicMock()
        server._ws_server = mock_ws_server
        server._running = True

        await server.stop()
        mock_ws_server.close.assert_called_once()
        assert server.running is False


# ---------------------------------------------------------------------------
# Error Paths
# ---------------------------------------------------------------------------


class TestDashboardErrorPaths:
    """Error handling paths in DashboardServer."""

    async def test_start_raises_when_websockets_missing(self) -> None:
        """Start raises DriverError when websockets is not installed."""
        config = DashboardConfig()
        server = DashboardServer(config=config)

        with (
            patch("artax.dashboard.server.websockets", None),
            pytest.raises(DriverError, match="websockets not installed"),
        ):
            await server.start()

    async def test_stop_closes_all_client_connections(self) -> None:
        """Stop closes all connected client sockets."""
        config = DashboardConfig()
        server = DashboardServer(config=config)

        mock_ws = AsyncMock()
        server._clients.add(mock_ws)
        server._running = True

        await server.stop()
        mock_ws.close.assert_awaited_once()
        assert server.client_count == 0

    async def test_stop_handles_client_close_error(self) -> None:
        """Stop handles errors when closing client connections."""
        config = DashboardConfig()
        server = DashboardServer(config=config)

        mock_ws = AsyncMock()
        mock_ws.close.side_effect = OSError("Connection reset")
        server._clients.add(mock_ws)
        server._running = True

        await server.stop()
        assert server.client_count == 0

    async def test_handle_client_sends_history_on_connect(self) -> None:
        """Handle client sends event history when a client connects."""
        config = DashboardConfig(event_history_size=10)
        server = DashboardServer(config=config)

        event = SemanticEvent.create(
            type=EventType.PAGE_LOADED,
            source="chromium",
            payload={"url": "https://example.com"},
        )
        await server.receive_event(event)

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = MagicMock(return_value=_EmptyAsyncIterator())
        await server._handle_client(mock_ws)

        assert mock_ws.send.await_count == 2
        # First message: state snapshot; Second message: history
        state_data = json.loads(mock_ws.send.call_args_list[0][0][0])
        assert state_data["type"] == "state"
        assert state_data["drivers_connected"] == 0

        history_data = json.loads(mock_ws.send.call_args_list[1][0][0])
        assert history_data["type"] == "history"
        assert len(history_data["events"]) == 1

    async def test_handle_client_handles_disconnect_gracefully(self) -> None:
        """Handle client handles disconnect without error."""
        config = DashboardConfig()
        server = DashboardServer(config=config)

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = MagicMock(side_effect=OSError("Connection reset"))

        await server._handle_client(mock_ws)
        assert server.client_count == 0


# ---------------------------------------------------------------------------
# Driver Tracking
# ---------------------------------------------------------------------------


class TestDashboardDriverTracking:
    """Verify the dashboard server tracks connected drivers from events."""

    async def test_tracks_driver_connected(self) -> None:
        """DRIVER_CONNECTED events add the driver to the tracked set."""
        config = DashboardConfig()
        server = DashboardServer(config=config)

        event = SemanticEvent.create(
            type=EventType.DRIVER_CONNECTED,
            source="runtime",
            payload={"driver": "chromium"},
        )
        await server.receive_event(event)

        assert server.connected_drivers == ["chromium"]

    async def test_tracks_driver_disconnected(self) -> None:
        """DRIVER_DISCONNECTED events remove the driver from the tracked set."""
        config = DashboardConfig()
        server = DashboardServer(config=config)

        await server.receive_event(
            SemanticEvent.create(
                type=EventType.DRIVER_CONNECTED,
                source="runtime",
                payload={"driver": "chromium"},
            )
        )
        await server.receive_event(
            SemanticEvent.create(
                type=EventType.DRIVER_DISCONNECTED,
                source="runtime",
                payload={"driver": "chromium"},
            )
        )

        assert server.connected_drivers == []

    async def test_handles_unknown_driver_name(self) -> None:
        """Driver events without a 'driver' payload key default to 'unknown'."""
        config = DashboardConfig()
        server = DashboardServer(config=config)

        await server.receive_event(
            SemanticEvent.create(
                type=EventType.DRIVER_CONNECTED,
                source="runtime",
                payload={},
            )
        )

        assert server.connected_drivers == ["unknown"]

    async def test_state_message_includes_driver_count(self) -> None:
        """_handle_client sends a 'state' message with driver count."""
        config = DashboardConfig()
        server = DashboardServer(config=config)

        await server.receive_event(
            SemanticEvent.create(
                type=EventType.DRIVER_CONNECTED,
                source="runtime",
                payload={"driver": "chromium"},
            )
        )

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = MagicMock(return_value=_EmptyAsyncIterator())
        await server._handle_client(mock_ws)

        assert mock_ws.send.await_count == 2
        state_data = json.loads(mock_ws.send.call_args_list[0][0][0])
        assert state_data["type"] == "state"
        assert state_data["drivers_connected"] == 1
        assert state_data["connected_drivers"] == ["chromium"]

    async def test_runtime_state_includes_drivers(self) -> None:
        """get_runtime_state returns driver count and names."""
        config = DashboardConfig()
        server = DashboardServer(config=config)

        await server.receive_event(
            SemanticEvent.create(
                type=EventType.DRIVER_CONNECTED,
                source="runtime",
                payload={"driver": "chromium"},
            )
        )

        state = await server.get_runtime_state()
        assert state["drivers_connected"] == 1
        assert state["connected_drivers"] == ["chromium"]

    async def test_health_includes_driver_count(self) -> None:
        """get_health returns the connected driver count."""
        config = DashboardConfig()
        server = DashboardServer(config=config)

        await server.receive_event(
            SemanticEvent.create(
                type=EventType.DRIVER_CONNECTED,
                source="runtime",
                payload={"driver": "terminal"},
            )
        )

        health = server.get_health()
        assert health["drivers_connected"] == 1

    async def test_memory_keys_counted_from_history(self) -> None:
        """_count_memory_keys counts unique keys from memory_updated events."""
        config = DashboardConfig()
        server = DashboardServer(config=config)

        await server.receive_event(
            SemanticEvent.create(
                type=EventType.MEMORY_UPDATED,
                source="runtime",
                payload={"key": "foo", "value": 1},
            )
        )
        await server.receive_event(
            SemanticEvent.create(
                type=EventType.MEMORY_UPDATED,
                source="runtime",
                payload={"key": "foo", "value": 2},
            )
        )
        await server.receive_event(
            SemanticEvent.create(
                type=EventType.MEMORY_UPDATED,
                source="runtime",
                payload={"key": "bar", "value": "baz"},
            )
        )

        assert server._count_memory_keys() == 2

    async def test_tracks_driver_unhealthy(self) -> None:
        """DRIVER_UNHEALTHY events track the driver as unhealthy."""
        config = DashboardConfig()
        server = DashboardServer(config=config)

        await server.receive_event(
            SemanticEvent.create(
                type=EventType.DRIVER_UNHEALTHY,
                source="runtime",
                payload={"driver": "chromium"},
            )
        )

        assert server.unhealthy_drivers == ["chromium"]
        assert server.connected_drivers == []

    async def test_driver_recovers_from_unhealthy(self) -> None:
        """DRIVER_CONNECTED removes a driver from the unhealthy set."""
        config = DashboardConfig()
        server = DashboardServer(config=config)

        await server.receive_event(
            SemanticEvent.create(
                type=EventType.DRIVER_UNHEALTHY,
                source="runtime",
                payload={"driver": "chromium"},
            )
        )
        await server.receive_event(
            SemanticEvent.create(
                type=EventType.DRIVER_CONNECTED,
                source="runtime",
                payload={"driver": "chromium"},
            )
        )

        assert server.connected_drivers == ["chromium"]
        assert server.unhealthy_drivers == []
