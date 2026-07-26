# PRD: Runtime Core

**Subsystem:** `artax.runtime`
**Version:** 0.1
**Status:** Draft

---

## 1. Problem Statement

Artax Network needs a central orchestrator that manages the entire lifecycle of an embodied AI runtime. This orchestrator must coordinate event flow between drivers, memory, and the scheduler without coupling to any specific driver implementation. Without a well-defined runtime core, subsystems become entangled — drivers depend on memory internals, the scheduler reaches into event bus state, and configuration drifts across modules. The runtime must own all subsystem instances, enforce lifecycle contracts, and expose a minimal API surface that remains stable as drivers, memory backends, and scheduling strategies evolve independently.

The runtime is the single process boundary. Everything inside it shares a memory space. Everything outside it communicates through drivers. This boundary must be explicit and enforced.

---

## 2. Goals

1. **Event loop management.** The runtime owns the primary async event loop. It polls for new events from the EventBus, dispatches them to registered handlers, and triggers the next decision cycle. The loop is non-blocking and never waits on a single driver or subsystem.

2. **Component registration.** Drivers, memory backends, and scheduler strategies register with the runtime at startup. Registration is explicit — no auto-discovery, no magic imports. The runtime maintains a registry of active components and enforces uniqueness constraints (one memory backend, one scheduler, N drivers).

3. **Lifecycle management.** The runtime exposes `start()` and `stop()` methods that cascade lifecycle events to all registered components. Startup order: EventBus → Memory → Scheduler → Drivers. Shutdown order: Drivers → Scheduler → Memory → EventBus. Each component must handle graceful shutdown with a configurable timeout (default 5 seconds).

4. **WebSocket server.** The runtime runs a WebSocket server on a configurable port (default 8765) that streams events, memory state, and driver status to the developer dashboard. The WebSocket server is a read-only observer — it never accepts commands that modify runtime state.

5. **Configuration management.** The runtime accepts a configuration object (`RuntimeConfig`) that specifies subsystem parameters, driver configurations, memory backend selection, and scheduler settings. Configuration is loaded once at startup and is immutable during runtime. Environment variables override config file values.

6. **Subsystem isolation.** Subsystems communicate only through the EventBus. The runtime never passes direct object references between subsystems. Memory never imports scheduler internals. Drivers never access memory directly. All inter-subsystem data flow is event-driven.

7. **CLI entry point.** The runtime exposes a CLI command (`artax`) that loads configuration, instantiates all subsystems, registers drivers, and enters the event loop. The CLI supports flags for config path, log level, and dashboard enable/disable.

---

## 3. Non-Goals

1. **Any specific driver logic.** The runtime does not contain Chromium-specific, terminal-specific, or any other driver-specific code. Drivers register themselves; the runtime treats them as opaque implementations of the Driver protocol.

2. **LLM integration.** The runtime does not call language models, manage API keys, or handle prompt construction. The runtime provides the event infrastructure; the agent loop that decides actions is external to v0.1.

3. **Authentication and authorization.** The runtime does not authenticate users, drivers, or dashboard clients. All connections are trusted. Security is a v0.2 concern.

4. **Distributed deployment.** The runtime runs as a single process. It does not coordinate across machines, manage consensus, or shard state. Distributed mode is a future concern.

5. **Hot-reloading.** Drivers and configurations are fixed at startup. Changing a driver requires restarting the runtime. Hot-swap is a v0.3 concern.

6. **Metrics collection.** The runtime does not export Prometheus metrics, OpenTelemetry traces, or structured logs beyond standard Python logging. Observability instrumentation is a v0.2 concern.

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Runtime                          │
│                                                     │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐      │
│  │  EventBus  │  │  Memory   │  │ Scheduler │      │
│  │  (hub)     │◄─┤ (store)   │◄─┤ (queue)   │      │
│  └─────┬─────┘  └───────────┘  └───────────┘      │
│        │                                            │
│  ┌─────┴─────────────────────────────┐             │
│  │         Driver Registry           │             │
│  │  ┌─────────┐ ┌─────────┐ ┌─────┐│             │
│  │  │Driver A │ │Driver B │ │ ... ││             │
│  │  └─────────┘ └─────────┘ └─────┘│             │
│  └───────────────────────────────────┘             │
│                                                     │
│  ┌───────────────────────────────────┐             │
│  │      WebSocket Server (read-only) │             │
│  └───────────────────────────────────┘             │
└─────────────────────────────────────────────────────┘
```

### Startup Sequence

1. Parse CLI arguments and load `RuntimeConfig` from file + environment overrides.
2. Instantiate `EventBus`.
3. Instantiate `WorkingMemory` backend (selected by config: in-memory, SQLite, Redis).
4. Instantiate `Scheduler` with configured strategy.
5. Call `Runtime.register_driver()` for each driver specified in config. Drivers are instantiated but not yet connected.
6. Start `EventBus` — begins accepting publishes and dispatching to subscribers.
7. Start `Scheduler` — begins tick loop.
8. Call `connect()` on each registered driver in registration order.
9. Start WebSocket server.
10. Enter primary event loop.

### Shutdown Sequence

1. Receive SIGINT or SIGTERM.
2. Stop accepting new events on EventBus.
3. Call `disconnect()` on each driver (reverse registration order) with 5-second timeout.
4. Stop Scheduler.
5. Stop Memory (flush any pending writes).
6. Stop EventBus.
7. Stop WebSocket server.
8. Exit process.

### Error Handling

- If a driver fails to connect during startup, log the error and continue with remaining drivers. The runtime enters a degraded mode where missing drivers are marked unhealthy.
- If a driver throws during event handling, catch the exception, log it, mark the driver as unhealthy, and continue. Other drivers are unaffected.
- If Memory fails, the runtime halts. Memory failure is unrecoverable — no event can be processed without context.
- If the Scheduler fails, the runtime halts. Without scheduling, events pile up unbounded.

---

## 5. Interfaces

### RuntimeConfig

```python
@dataclass
class RuntimeConfig:
    event_bus: EventBusConfig
    memory: MemoryConfig
    scheduler: SchedulerConfig
    drivers: list[DriverConfig]
    websocket_port: int = 8765
    log_level: str = "INFO"
    shutdown_timeout: float = 5.0
```

### Runtime

```python
class Runtime:
    async def start(self) -> None:
        """Initialize all subsystems and enter the event loop."""

    async def stop(self) -> None:
        """Gracefully shut down all subsystems in reverse order."""

    def register_driver(self, name: str, config: DriverConfig) -> None:
        """Register a driver with the runtime. Must be called before start()."""

    def register_memory(self, backend: WorkingMemory) -> None:
        """Register a memory backend. Must be called before start(). Only one allowed."""

    @property
    def event_bus(self) -> EventBus:
        """Access the runtime's event bus."""

    @property
    def memory(self) -> WorkingMemory:
        """Access the runtime's working memory."""

    @property
    def scheduler(self) -> Scheduler:
        """Access the runtime's scheduler."""

    @property
    def drivers(self) -> dict[str, Driver]:
        """Access the registry of connected drivers."""
```

### CLI

```
Usage: artax [OPTIONS]

Options:
  --config PATH      Path to runtime config file (default: artax.toml)
  --log-level LEVEL  Log level: DEBUG, INFO, WARNING, ERROR (default: INFO)
  --no-dashboard     Disable WebSocket server
  --port PORT        WebSocket server port (default: 8765)
```

### Runtime Events

The runtime emits the following events on the EventBus:

| Event Type | Payload | Description |
|---|---|---|
| `runtime.started` | `{"timestamp": float}` | Runtime fully initialized and event loop entered |
| `runtime.stopping` | `{"timestamp": float}` | Shutdown sequence initiated |
| `runtime.driver.connected` | `{"driver": str}` | Driver successfully connected |
| `runtime.driver.disconnected` | `{"driver": str}` | Driver gracefully disconnected |
| `runtime.driver.unhealthy` | `{"driver": str, "error": str}` | Driver threw exception or failed health check |

---

## 6. Acceptance Criteria

1. `Runtime.start()` initializes EventBus, Memory, Scheduler, and all registered drivers in correct order.
2. `Runtime.stop()` shuts down all components in reverse order within the configured timeout.
3. Arbitrary drivers implementing the `Driver` protocol can be registered and will receive events.
4. The EventBus routes events from any producer to any subscriber without runtime coupling.
5. The WebSocket server broadcasts events to connected clients in real-time.
6. The WebSocket server is read-only — no client message modifies runtime state.
7. `RuntimeConfig` loads from a TOML file with environment variable overrides.
8. If a driver fails to connect, runtime continues in degraded mode and logs the error.
9. If a driver throws during event handling, it is marked unhealthy and other drivers continue.
10. Memory failure causes immediate halt with a logged error.
11. CLI `artax --config artax.toml` starts the runtime with correct configuration.
12. No subsystem directly imports or references another subsystem's internal modules — all communication flows through EventBus.
13. Startup and shutdown sequences emit the correct lifecycle events.
14. The runtime never contains any driver-specific logic, import, or conditional branch.

---

## 7. Future Extensions

1. **Hot driver reloading.** Add `Runtime.reload_driver(name)` that disconnects a driver, instantiates a new one with updated config, and reconnects without stopping the event loop.

2. **Subsystem health monitoring.** Periodic health checks for all subsystems. Emit `runtime.health.ok` or `runtime.health.degraded` events at a configurable interval.

3. **Graceful degradation strategies.** Allow config to specify fallback behavior when a driver fails — retry, ignore, or halt.

4. **Configuration hot-reloading.** Watch the config file for changes and apply updates without restart. Memory backend changes would still require restart.

5. **Plugin system.** Allow external packages to register subsystem extensions (custom memory backends, scheduler strategies, dashboard widgets) via entry points.

6. **Distributed mode.** Coordinate multiple runtime processes via a message broker. Each process owns a subset of drivers.

7. **Structured logging.** Emit JSON logs with correlation IDs that link events across subsystems.

8. **OpenTelemetry integration.** Trace event propagation through the runtime with spans for publish, dispatch, handle, and act phases.

---

## 8. Resolved Decisions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Multiple memory backends simultaneously? | **Yes, multi-backend** | InMemory for hot/cached data, SQLite for persistence. Consistent with architecture showing pluggable backends. |
| 2 | `Runtime.stop()` hard timeout or indefinite? | **Hard timeout (default 5s)** | Prevents hung shutdown. `RuntimeConfig.shutdown_timeout` controls duration. |
| 3 | WebSocket authentication in v0.1? | **127.0.0.1 binding only** | Local dev tool. No auth needed for v0.1. Add token auth later for remote use. |
| 4 | Driver registration order = event processing order? | **Concurrent, no order guarantee** | All drivers process events independently. Simpler, more scalable. Order is not semantically meaningful. |
| 5 | Emit event throughput metrics to dashboard? | **Yes, basic metrics** | events/sec, queue depth, memory usage. Dashboard needs this for status cards. |
| 6 | `RuntimeConfig` composition support? | **Base + override composition** | Flexible config layering. Base config can be imported and specific fields overridden. |
| 7 | CLI `artax status` command? | **Yes** | Simple status check. Useful for development and debugging. |

---

*Document created: 2026-07-26*
*Last updated: 2026-07-26*
