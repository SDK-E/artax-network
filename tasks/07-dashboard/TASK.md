# Task 07: Implement Dashboard Server

## Objective

Implement the WebSocket dashboard server for Artax Network. The dashboard provides real-time visibility into runtime state, events, memory, and driver status. It communicates with the runtime exclusively over WebSockets.

## Reference Documents

- **PRD**: `docs/prd/prd-dashboard.md` — all resolved design decisions
- **Existing scaffolding**: `artax/dashboard/server.py`
- **Depends on**: Task 05 (Runtime) — must be implemented first
- **Dashboard design**: `docs/dashboard.md`

## Resolved Design Decisions

1. **`websockets` library** — lightweight, battle-tested, minimal overhead
2. **Bundled with Python package** — static build included in package
3. **`/health` endpoint** — standard practice, useful for monitoring
4. **Multiple concurrent clients** — standard WebSocket pattern
5. **Auto-scroll with user override** — best UX, pause on scroll up
6. **JSON with collapsible tree** — standard for dev tools
7. **No compression for v0.1** — local tool, bandwidth not a concern
8. **Pause events button** — essential UX for debugging

## Current State

Existing scaffolding is a stub. Key gaps:

- `DashboardServer` takes only host/port/ws_port (missing EventBus, Memory, Scheduler, Drivers)
- No WebSocket protocol defined
- No actual WebSocket server
- No event broadcasting
- No state query handling
- No health endpoint

## Implementation Steps

### Step 1: Reconcile `artax/dashboard/server.py`

```python
class DashboardConfig:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8081
    broadcast_interval_ms: int = 100  # how often to broadcast events
    event_buffer_size: int = 1000  # events to buffer for new clients
    state_broadcast_interval_ms: int = 1000  # how often to broadcast state

class DashboardServer:
    def __init__(
        self,
        config: DashboardConfig,
        event_bus: EventBus,
        memory: WorkingMemory,
        scheduler: Scheduler,
        drivers: dict[str, Driver],
    ) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def health(self) -> dict[str, Any]: ...
```

### Step 2: Define WebSocket Protocol

JSON message protocol between server and dashboard:

**Server → Client messages:**

```python
# Event broadcast
{"type": "event", "data": {"event_id": "...", "type": "...", "source": "...", "timestamp": ..., "payload": {...}}}

# State update (periodic)
{"type": "state", "data": {"runtime": {...}, "memory": {...}, "scheduler": {...}, "drivers": {...}}}

# Driver status
{"type": "driver_status", "data": {"name": "...", "state": "...", "health": {...}}}

# Response to query
{"type": "query_result", "data": {...}}

# Error
{"type": "error", "data": {"message": "..."}}
```

**Client → Server messages:**

```python
# Query memory
{"type": "query_memory", "data": {"namespace": "...", "key_prefix": "..."}}

# Query events (history)
{"type": "query_events", "data": {"limit": 100, "type": "..."}}

# Pause/resume events
{"type": "control", "data": {"action": "pause" | "resume"}}

# Get driver status
{"type": "query_drivers", "data": {}}
```

### Step 3: Implement WebSocket Server

Using `websockets` library:

```python
class DashboardServer:
    def __init__(self, config, event_bus, memory, scheduler, drivers):
        self._config = config
        self._event_bus = event_bus
        self._memory = memory
        self._scheduler = scheduler
        self._drivers = drivers
        self._clients: set[websockets.WebSocketServerProtocol] = set()
        self._event_buffer: collections.deque[Event] = collections.deque(maxlen=config.event_buffer_size)
        self._subscription_id: str | None = None
        self._server = None

    async def start(self) -> None:
        # 1. Subscribe to EventBus for all events
        # 2. Start broadcast task (periodic state updates)
        # 3. Start WebSocket server on config.port
        ...

    async def stop(self) -> None:
        # 1. Unsubscribe from EventBus
        # 2. Cancel broadcast task
        # 3. Close all client connections
        # 4. Stop server
        ...

    async def _handle_client(self, websocket: WebSocket) -> None:
        # 1. Add to clients set
        # 2. Send event buffer (catch up)
        # 3. Send initial state
        # 4. Listen for client messages
        # 5. On disconnect: remove from clients
        ...

    async def _on_event(self, event: Event) -> None:
        # 1. Add to event buffer
        # 2. Broadcast to all non-paused clients
        ...

    async def _broadcast_state(self) -> None:
        # Periodic state broadcast to all clients
        # Include: runtime state, memory size, scheduler status, driver health
        ...

    async def _handle_message(self, client: WebSocket, message: str) -> None:
        # Parse JSON, route to handler based on type
        ...

    async def _handle_query_memory(self, data: dict) -> dict: ...
    async def _handle_query_events(self, data: dict) -> dict: ...
    async def _handle_query_drivers(self, data: dict) -> dict: ...
    async def _handle_control(self, data: dict) -> None: ...

    async def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "clients": len(self._clients),
            "uptime": time.monotonic() - self._start_time,
        }
```

### Step 4: Write tests

Create `tests/dashboard/__init__.py`
Create `tests/dashboard/test_dashboard_server.py`:
- Test DashboardConfig defaults
- Test server instantiation
- Test health endpoint returns correct format
- Mock WebSocket clients for:
  - Client connects and receives event buffer
  - Client receives state broadcast
  - Client sends query_memory and receives result
  - Client sends query_events and receives result
  - Client sends query_drivers and receives result
  - Client sends control pause and stops receiving events
  - Client sends control resume and starts receiving again
  - Client disconnect removes from clients set
- Test event buffering (new client gets buffered events)
- Test concurrent client connections
- Test server start/stop lifecycle

## Technical Constraints

- `websockets` library (add to dependencies in pyproject.toml)
- JSON serialization with `json.dumps()`/`json.loads()`
- `asyncio.Queue` for per-client message queues (optional, for backpressure)
- `asyncio.create_task()` for broadcast loop
- `collections.deque(maxlen=N)` for event buffer
- Async context manager for WebSocket server
- All clients receive events concurrently (asyncio tasks)
- Strict typing for `mypy --strict`

## Dependency Note

Add `websockets` to the `[project] dependencies` in `pyproject.toml`:
```toml
dependencies = [
    "websockets>=12.0",
]
```

## Quality Gates

```bash
python3 -m py_compile artax/dashboard/server.py
python3 -c "from artax.dashboard.server import DashboardServer, DashboardConfig; print('OK')"
pytest tests/dashboard/ -v
```

## Files

| Action | File |
|--------|------|
| MODIFY | `artax/dashboard/server.py` |
| MODIFY | `pyproject.toml` (add websockets dependency) |
| CREATE | `tests/dashboard/__init__.py` |
| CREATE | `tests/dashboard/test_dashboard_server.py` |
