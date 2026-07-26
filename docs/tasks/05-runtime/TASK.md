# Task 05: Implement Runtime Core

## Objective

Implement the core runtime for Artax Network. The runtime is the central orchestrator that manages the lifecycle of all subsystems (EventBus, Memory, Scheduler, Drivers) and coordinates event flow between them. It must never contain driver-specific logic.

## Reference Documents

- **PRD**: `../../prd/prd-runtime.md` — all resolved design decisions
- **Existing scaffolding**: `../../../artax/runtime/core.py`
- **Depends on**: ALL Layer 0 and Layer 1 tasks (Events, Memory, Scheduler, Driver API)
- **Architecture**: `../../../ARCHITECTURE.md` — runtime component diagram

## Resolved Design Decisions

1. **Multi-backend memory** — InMemory for hot data, SQLite for persistence
2. **Hard shutdown timeout** (default 5s) — prevents hung shutdown
3. **127.0.0.1 binding only** — local dev tool, no auth for v0.1
4. **Concurrent driver processing** — no order guarantee
5. **Basic metrics to dashboard** — events/sec, queue depth, memory usage
6. **Config composition** — base config with field overrides
7. **CLI `artax status`** — check if runtime instance is running

## Current State

Existing scaffolding is a stub. Key gaps:

- `RuntimeConfig` is flat (missing subsystem configs, shutdown_timeout)
- `Runtime` class has no actual lifecycle management
- No startup/shutdown sequencing
- No driver registration with EventBus
- No WebSocket server integration
- No metrics collection
- No CLI implementation

## Implementation Steps

### Step 1: Reconcile `../../../artax/runtime/core.py`

```python
class RuntimeConfig:
    # Composition: base configs + overrides
    log_level: str = "info"
    host: str = "127.0.0.1"
    port: int = 8080
    ws_port: int = 8081
    shutdown_timeout: float = 5.0
    event_bus: EventBusConfig = field(default_factory=EventBusConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    dashboard_enabled: bool = True

class RuntimeState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

class Runtime:
    def __init__(self, config: RuntimeConfig) -> None: ...
    @property
    def event_bus(self) -> EventBus: ...
    @property
    def memory(self) -> WorkingMemory: ...
    @property
    def scheduler(self) -> Scheduler: ...
    @property
    def drivers(self) -> dict[str, Driver]: ...
    @property
    def state(self) -> RuntimeState: ...
    def register_driver(self, driver: Driver) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def run_forever(self) -> None: ...
    def status(self) -> RuntimeStatus: ...

class RuntimeStatus:
    state: RuntimeState
    uptime: float
    events_published: int
    events_delivered: int
    drivers_connected: int
    memory_entries: int
    scheduler_pending: int
```

### Step 2: Implement Runtime Lifecycle

**Startup sequence** (order matters):
1. Set state to STARTING
2. Configure logging
3. Create and start EventBus
4. Create and start Memory (subscribe to MEMORY_UPDATED events)
5. Create and start Scheduler (connect to EventBus)
6. For each registered driver: connect to EventBus, publish DRIVER_CONNECTED
7. Set state to RUNNING
8. Publish RUNTIME_STARTED event
9. If dashboard enabled: start WebSocket server

**Shutdown sequence** (reverse order, with timeout):
1. Set state to STOPPING
2. Publish RUNTIME_STOPPING event
3. Stop accepting new events
4. Scheduler.stop() — deliver all pending (emergency_drain)
5. Disconnect all drivers (with timeout)
6. EventBus.drain() — deliver all queued events
7. Stop Memory
8. Stop EventBus
9. Set state to STOPPED
10. If shutdown takes > shutdown_timeout: force exit with warning

**`run_forever()`**:
1. Call start()
2. Enter asyncio event loop
3. On SIGINT/SIGTERM: call stop(), exit
4. Keep loop alive until stopped

### Step 3: Implement Metrics Collection

The runtime collects metrics and makes them available:

```python
class RuntimeMetrics:
    events_published: int
    events_delivered: int
    uptime: float
    drivers_connected: int
    memory_entries: int
    scheduler_pending: int
    event_bus_stats: EventBusStats
```

- Track events_published by counting EventBus.publish() calls (wrap event bus)
- Track uptime from start time
- Query subsystems for their stats

### Step 4: Implement CLI

```python
def cli() -> None:
    """Entry point for `artax` command."""
    parser = argparse.ArgumentParser(description="Artax Network Runtime")
    parser.add_argument("--config", type=str, help="Config file path")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--no-dashboard", action="store_true")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "status"])
    args = parser.parse_args()

    if args.command == "run":
        config = RuntimeConfig(...)
        runtime = Runtime(config)
        asyncio.run(runtime.run_forever())
    elif args.command == "status":
        # Try to connect to running instance
        ...
```

### Step 5: Write tests

Create `tests/test_runtime.py`:
- Test RuntimeConfig creation with defaults
- Test RuntimeConfig composition (override fields)
- Test Runtime lifecycle: start → running → stop → stopped
- Test register_driver adds to drivers dict
- Test startup order (EventBus before Memory before Drivers)
- Test shutdown order (reverse of startup)
- Test shutdown timeout (force exit)
- Test run_forever responds to stop signal
- Test RuntimeStatus returns accurate data
- Test multiple drivers registered and connected
- Test metrics collection
- Test CLI argument parsing (run, status, --config, --log-level)

## Technical Constraints

- `asyncio.run()` for entry point
- `signal.signal(SIGINT, ...)` and `signal.signal(SIGTERM, ...)` for graceful shutdown
- `asyncio.wait_for(coro, timeout)` for shutdown timeout
- Config loading from TOML file with env var overrides
- All subsystem creation in runtime (dependency injection)
- Strict typing for `mypy --strict`
- Runtime MUST NOT import any driver-specific code

## Quality Gates

```bash
python3 -m py_compile artax/runtime/core.py
python3 -c "from artax.runtime.core import Runtime, RuntimeConfig; print('OK')"
pytest tests/test_runtime.py -v
```

## Files

| Action | File |
|--------|------|
| MODIFY | `../../../artax/runtime/core.py` |
| CREATE | `tests/test_runtime.py` |
