# Task 05: Runtime Core — Gap Analysis

**Layer:** 2 (Runtime)
**Subsystem:** `artax.runtime`
**Status:** Implemented with gaps
**PRD Reference:** `docs/prd/prd-runtime.md`

---

## Senior Product Manager Perspective

### What the Runtime Is Supposed to Do

The runtime is the central orchestrator for Artax Network. It manages the lifecycle of all subsystems (EventBus, Memory, Scheduler, Drivers) and coordinates event flow between them. It must never contain driver-specific logic — drivers register themselves and the runtime treats them as opaque implementations of the Driver protocol.

The runtime must:

1. **Own the event loop** — The runtime owns the primary async event loop. It polls for new events from the EventBus, dispatches them to registered handlers, and triggers the next decision cycle. The loop is non-blocking and never waits on a single driver or subsystem.

2. **Component registration** — Drivers, memory backends, and scheduler strategies register with the runtime at startup. Registration is explicit — no auto-discovery, no magic imports. The runtime maintains a registry of active components and enforces uniqueness constraints (one memory backend, one scheduler, N drivers).

3. **Lifecycle management** — The runtime exposes `start()` and `stop()` methods that cascade lifecycle events to all registered components. Startup order: EventBus → Memory → Scheduler → Drivers. Shutdown order: Drivers → Scheduler → Memory → EventBus. Each component must handle graceful shutdown with a configurable timeout (default 5 seconds).

4. **WebSocket server** — The runtime runs a WebSocket server on a configurable port (default 8765) that streams events, memory state, and driver status to the developer dashboard. The WebSocket server is a read-only observer — it never accepts commands that modify runtime state.

5. **Configuration management** — The runtime accepts a configuration object (`RuntimeConfig`) that specifies subsystem parameters, driver configurations, memory backend selection, and scheduler settings. Configuration is loaded once at startup and is immutable during runtime. Environment variables override config file values.

6. **Subsystem isolation** — Subsystems communicate only through the EventBus. The runtime never passes direct object references between subsystems. Memory never imports scheduler internals. Drivers never access memory directly. All inter-subsystem data flow is event-driven.

7. **CLI entry point** — The runtime exposes a CLI command (`artax`) that loads configuration, instantiates all subsystems, registers drivers, and enters the event loop. The CLI supports flags for config path, log level, and dashboard enable/disable.

### What Currently Works

The implementation provides:

- **Runtime class** — Central orchestrator with `start()`, `stop()`, `run_forever()`, `register_driver()`, `register_memory()`, `register_event_bus()`, `register_scheduler()` methods.

- **Lifecycle management** — Startup order: EventBus → Memory → Scheduler → Dashboard → Drivers. Shutdown order: Drivers → Scheduler → Dashboard → Memory → EventBus. Each component gets a configurable timeout (default 5s).

- **Driver registration** — Drivers are registered via `register_driver()` before `start()`. They are connected during `start()` and disconnected during `stop()`. Duplicate registrations are silently ignored. Failed connections are logged and the runtime continues with remaining drivers (degraded mode).

- **Dashboard auto-start** — The runtime automatically starts the dashboard if enabled. It subscribes to the EventBus to receive all events and forwards them to the dashboard server.

- **CLI entry point** — The `cli()` function in `runtime/__init__.py` parses arguments, loads TOML config, applies environment variable overrides, builds `RuntimeConfig`, instantiates the runtime, loads drivers, and enters the event loop.

- **Signal handling** — SIGINT and SIGTERM trigger graceful shutdown via `run_forever()`.

- **RuntimeStatus** — Returns point-in-time snapshot with state, uptime, events published, and drivers connected.

### What Is Missing or Different From the Plan

**Gap 1: RuntimeConfig diverges significantly from PRD spec**

The PRD specifies `RuntimeConfig` with fields: `event_bus`, `memory`, `scheduler`, `drivers: list[DriverConfig]`, `websocket_port: int = 8765`, `log_level: str = "INFO"`, `shutdown_timeout: float = 5.0`.

The implementation has: `shutdown_timeout`, `drivers: list[object]`, `event_bus`, `memory`, `scheduler`, `dashboard: DashboardConfig`.

Key differences:
- `drivers` is `list[object]` instead of `list[DriverConfig]` — the PRD says drivers are registered as config objects, but the implementation expects pre-instantiated driver objects
- `websocket_port` is not a field — the dashboard config is nested inside `dashboard: DashboardConfig`
- `log_level` is not a field in `RuntimeConfig` — it's handled only in the CLI function
- The `dashboard` field is a `DashboardConfig` dataclass instead of a `websocket_port` int

**Gap 2: Runtime.status() is missing fields from PRD spec**

The PRD's `RuntimeStatus` includes `events_delivered`, `memory_entries`, `scheduler_pending`. The implementation's `RuntimeStatus` only has `state`, `uptime`, `events_published`, `drivers_connected`. The missing fields mean the dashboard cannot display delivered event count, memory entry count, or scheduler pending count from the runtime status alone.

**Gap 3: register_driver() takes a pre-instantiated Driver instead of (name: str, config: DriverConfig)**

The PRD specifies `register_driver(self, name: str, config: DriverConfig)`. The implementation has `register_driver(self, driver: Driver)`. This means the runtime does not instantiate drivers itself — the caller must create and configure the driver before registering it. The PRD envisions the runtime instantiating drivers from config, which provides better isolation and configuration management.

**Gap 4: The runtime starts the Dashboard before connecting Drivers**

The PRD startup sequence is: EventBus → Memory → Scheduler → Drivers. The implementation adds Dashboard between Scheduler and Drivers: EventBus → Memory → Scheduler → Dashboard → Drivers. This is a design change — the dashboard is started before drivers are connected, which means the dashboard may not see driver status events until after drivers are connected. This is not necessarily wrong, but it differs from the PRD.

**Gap 5: The runtime does not implement the "run_forever() event loop" as described in the PRD**

The PRD says the runtime should own the primary async event loop and "poll for new events from the EventBus, dispatch them to registered handlers, and trigger the next decision cycle." The current `run_forever()` simply waits on a stop event — it does not actively poll the EventBus or dispatch events to handlers. The event loop is managed by asyncio, and events are dispatched by the EventBus's subscriber system. This is actually the correct architecture (the EventBus handles dispatch), but the PRD's description of the runtime "owning" the event loop and actively polling is misleading.

**Gap 6: No metrics collection as described in the PRD**

The PRD says the runtime should collect metrics (events/sec, queue depth, memory usage) and make them available to the dashboard. The current implementation does not have a `RuntimeMetrics` class or any metrics collection beyond what the EventBus and subsystems already provide.

**Gap 7: The CLI does not support --no-dashboard or --port flags**

The PRD CLI spec includes `--no-dashboard` and `--port` flags. The current CLI only supports `--config` and `--log-level`.

**Gap 8: The runtime does not halt on Memory failure as specified in the PRD**

The PRD says "If Memory fails, the runtime halts. Memory failure is unrecoverable — no event can be processed without context." The current implementation catches exceptions during memory startup and continues, which contradicts this requirement.

**Gap 9: The runtime does not halt on Scheduler failure as specified in the PRD**

Same as Gap 8 — the PRD says "If the Scheduler fails, the runtime halts." The current implementation catches exceptions during scheduler startup and continues.

### Acceptance Criteria (What Needs to Pass)

1. Runtime.start() initializes EventBus, Memory, Scheduler, and all registered drivers in correct order
2. Runtime.stop() shuts down all components in reverse order within the configured timeout
3. Arbitrary drivers implementing the Driver protocol can be registered and will receive events
4. The EventBus routes events from any producer to any subscriber without runtime coupling
5. The WebSocket server broadcasts events to connected clients in real-time
6. The WebSocket server is read-only — no client message modifies runtime state
7. RuntimeConfig loads from a TOML file with environment variable overrides
8. If a driver fails to connect, runtime continues in degraded mode and logs the error
9. If a driver throws during event handling, it is marked unhealthy and other drivers continue
10. Memory failure causes immediate halt with a logged error (MISSING — current implementation continues)
11. Scheduler failure causes immediate halt with a logged error (MISSING — current implementation continues)
12. CLI artax --config artax.toml starts the runtime with correct configuration
13. No subsystem directly imports or references another subsystem's internal modules — all communication flows through EventBus
14. Startup and shutdown sequences emit the correct lifecycle events
15. The runtime never contains any driver-specific logic, import, or conditional branch

---

## Senior Engineer Perspective

### Architecture Assessment

The runtime is well-architected. It owns all subsystem instances, wires them together, and delegates all work to them. The `Runtime` class is the central coordinator that manages lifecycle, registration, and event flow.

Key design decisions that were correctly implemented:

- Startup order: EventBus → Memory → Scheduler → Dashboard → Drivers
- Shutdown order: reverse of startup
- Graceful shutdown with configurable timeout
- Driver registration before start, connection during start
- Degraded mode when drivers fail to connect
- Dashboard auto-start with EventBus subscription
- CLI with TOML config loading and env var overrides

### Critical Gaps

1. **Memory and Scheduler failure handling.** The PRD explicitly states that Memory and Scheduler failures should halt the runtime. The current implementation catches exceptions and continues, which means the runtime can start in a broken state without the operator knowing. This is a correctness issue.

2. **RuntimeConfig diverges from PRD.** The config dataclass does not match the PRD spec. This means any code that creates a `RuntimeConfig` following the PRD will have field mismatches.

3. **Missing CLI flags.** The `--no-dashboard` and `--port` flags are specified in the PRD but not implemented.

4. **Missing metrics collection.** The PRD specifies a `RuntimeMetrics` class and metrics collection. This is not implemented.

### Recommended Actions

1. **Fix Memory and Scheduler failure handling.** In `start()`, after calling `_start_memory()` and `_start_scheduler()`, check if the subsystems started successfully and halt if they did not. Do not catch and continue — propagate the exception.

2. **Align RuntimeConfig with PRD spec.** Either update the implementation to match the PRD (using `websocket_port`, `log_level`, `drivers: list[DriverConfig]`) or update the PRD to match the implementation. The implementation's approach of using a nested `DashboardConfig` is arguably better, but it should be documented as a deliberate deviation.

3. **Add --no-dashboard and --port CLI flags.** These are straightforward additions to the argument parser.

4. **Implement RuntimeMetrics.** Add a metrics collection class that tracks events/sec, queue depth, memory usage, and scheduler pending count. Expose this via the runtime's `status()` method or a dedicated `metrics()` method.

### Gap Summary

| Gap | Severity | Description |
|-----|----------|-------------|
| Memory/Scheduler failure does not halt runtime | HIGH | PRD requires halt; implementation continues |
| RuntimeConfig diverges from PRD spec | MEDIUM | Field names and types differ |
| Missing CLI flags (--no-dashboard, --port) | MEDIUM | PRD specifies these; not implemented |
| Missing metrics collection | MEDIUM | PRD specifies RuntimeMetrics; not implemented |
| register_driver() takes Driver not (name, config) | LOW | PRD specifies name+config; implementation takes pre-instantiated driver |
| Dashboard starts before drivers | LOW | Design change from PRD startup order |
| run_forever() does not actively poll EventBus | LOW | PRD describes active polling; implementation uses asyncio event loop |
