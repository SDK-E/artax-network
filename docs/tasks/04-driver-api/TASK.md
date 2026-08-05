# Task 04: Driver API — Gap Analysis

**Layer:** 1c (Driver API)
**Subsystem:** `artax.drivers`
**Status:** Implemented with gaps
**PRD Reference:** `docs/prd/prd-driver-api.md`

---

## Senior Product Manager Perspective

### What the Driver API Is Supposed to Do

The Driver API defines the contract between the runtime and environment drivers. Every driver (Chromium, terminal, future robotics, etc.) implements this protocol. The runtime never imports driver modules directly — it interacts with drivers exclusively through the Driver protocol. This means the runtime can manage any driver using the same lifecycle methods, event emission pattern, and action execution interface.

The Driver API must:

1. **Define a Driver protocol** — A Python `Protocol` class that specifies all methods a driver must implement. The protocol is the single source of truth for driver behavior.

2. **Lifecycle management** — Drivers have a clear lifecycle: instantiate → connect → running → disconnect. The runtime controls transitions. Drivers must handle each transition gracefully and report errors.

3. **Health checks** — Drivers implement a `health_check()` method that returns their current status as a `DriverHealth` dataclass. The runtime calls health checks periodically (configurable interval, default 30s). Unhealthy drivers are flagged but not automatically disconnected.

4. **Action execution** — Drivers accept actions from the runtime via `execute(action)`. Actions are typed objects with a name and parameters. The driver translates actions into environment-specific operations and returns results or errors.

5. **Event emission** — Drivers publish `SemanticEvent` objects to the EventBus when something happens in their environment. Drivers never emit events directly to subscribers — they always publish through the EventBus.

6. **Configuration protocol** — Each driver type defines a `DriverConfig` dataclass that specifies its configuration parameters. The runtime passes config to drivers at instantiation time.

7. **State reporting** — Drivers maintain a `DriverState` enum (disconnected, connecting, connected, unhealthy, error) that reflects their current status. The runtime reads state but does not set it — drivers own their state transitions.

### What Currently Works

The implementation provides:

- **Driver protocol** — A `Protocol` class with `name`, `environment`, `is_connected`, `connect()`, `disconnect()`, `observe()`, `execute()`, `health_check()` methods.

- **DriverState enum** — Five states: DISCONNECTED, CONNECTING, CONNECTED, UNHEALTHY, ERROR.

- **DriverHealth dataclass** — Contains `state`, `message`, `latency_ms`, `last_event_at`, `error_count`.

- **DriverError hierarchy** — `DriverError` (base), `DriverConnectionError`, `DriverTimeoutError`, `DriverActionError`.

- **DriverConfig protocol** — Structural protocol with `driver_type` property.

- **BaseDriver ABC** — Abstract base class providing common driver functionality: state transition management, error counting, health check baseline, `_publish_event()` helper. Subclasses must implement `_do_connect()`, `_do_disconnect()`, `observe()`, `execute()`.

- **Action types** — `Action` (name, action_id, target, parameters, timestamp), `ActionResult` (action_id, success, data, error, duration_ms), `Intent` (description, actions, priority).

### What Is Missing or Different From the Plan

**Gap 1: `DriverHealth.latency_ms` type and default differ from PRD**

The PRD specifies `latency_ms: float | None = None` (nullable, default None). The implementation has `latency_ms: float = 0.0` (non-nullable, default 0.0). The PRD says latency should be measured by the runtime, not the driver. A value of `0.0` is misleading — it implies the health check was instantaneous, when in reality the runtime should measure the round-trip latency. The correct type is `float | None` with a default of `None`, meaning "not yet measured."

**Gap 2: `DriverError` missing `recoverable` parameter**

The PRD specifies `DriverError.__init__(self, driver: str, message: str, recoverable: bool = True)`. The implementation's `DriverError` is a plain `Exception` subclass with no `recoverable` field. The PRD says: "DriverError with recoverable=True marks the driver as unhealthy; recoverable=False marks it as error." This distinction is important for the runtime's error handling strategy — recoverable errors should trigger a health state transition, while non-recoverable errors should put the driver in an error state.

**Gap 3: `Driver.connect()` takes `event_bus` parameter, which is correct per the resolved design decision, but the PRD protocol interface shows `connect()` without parameters.**

The PRD protocol shows:
```
async def connect(self) -> None:
```
But the resolved design decision #4 says "EventBus passed at connect time." The implementation correctly passes `event_bus` to `connect()`. This is a deliberate deviation from the PRD protocol interface, resolved by the design decision. However, the protocol definition itself does not reflect this, creating a documentation mismatch.

**Gap 4: The PRD says `Driver.observe()` returns `AsyncIterator[Event]` but the implementation's `BaseDriver.observe()` is abstract and returns `AsyncIterator[Event]`. This matches. No gap here.**

**Gap 5: The PRD says `DriverHealth` should have `latency_ms` measured by the runtime, but the current `BaseDriver.health_check()` returns `DriverHealth` without measuring latency. The runtime wraps this call to measure latency, but the `BaseDriver.health_check()` implementation does not include latency measurement itself.**

The PRD says "Runtime wraps this call to measure latency_ms." The `BaseDriver.health_check()` returns a `DriverHealth` with `latency_ms=0.0`. The runtime is supposed to wrap the call and measure the actual latency. This is a design where the runtime is responsible for latency measurement, not the driver. The current implementation has `latency_ms=0.0` as a placeholder — the runtime should measure and set the actual latency when it calls `health_check()`.

### Acceptance Criteria (What Needs to Pass)

1. Any class implementing the Driver protocol can be registered with the runtime
2. connect() transitions the driver from DISCONNECTED to CONNECTED
3. disconnect() transitions the driver from CONNECTED to DISCONNECTED
4. observe() yields SemanticEvent objects continuously while the driver is connected
5. execute(action) returns an ActionResult with success=True on successful execution
6. execute(action) returns an ActionResult with success=False and error message on failure
7. health_check() returns current state, latency, and error count
8. DriverState transitions follow the documented state machine
9. Drivers never publish events directly to subscribers — always through EventBus
10. Drivers never import or reference other drivers
11. DriverError with recoverable=True marks the driver as unhealthy; recoverable=False marks it as error (MISSING)
12. The runtime calls health_check() at the configured interval and logs results
13. Drivers handle disconnect() cleanly even if observe() is mid-iteration
14. The Driver API contains no environment-specific logic, imports, or conditionals

---

## Senior Engineer Perspective

### Architecture Assessment

The driver API is well-architected. The `Driver` Protocol defines the interface, `BaseDriver` ABC provides common functionality, and the `ChromiumDriver` implements the concrete driver. The separation of concerns is clean — the runtime never imports driver-specific code.

Key design decisions that were correctly implemented:

- `observe()` returns `AsyncIterator` — Pythonic, supports backpressure
- Driver handles timeouts internally — driver knows best
- `health_check()` is required — always know if driver is alive
- EventBus passed at connect time — clean lifecycle
- `DriverConfig` is a Protocol — flexible, duck-typing friendly
- Runtime passes through any action name — runtime agnostic
- `BaseDriver` manages state transitions, error counting, and health check baseline

### Critical Gaps

1. **`DriverError` missing `recoverable` parameter.** This is a significant gap because the runtime's error handling depends on knowing whether an error is recoverable. Without this field, the runtime cannot distinguish between transient errors (which should trigger a health state transition) and fatal errors (which should put the driver in an error state). The fix is to add `recoverable: bool = True` to `DriverError.__init__()`.

2. **`DriverHealth.latency_ms` should be `float | None` with default `None`.** The current `float = 0.0` is misleading. The runtime should measure latency and set it on the `DriverHealth` object after calling `health_check()`.

### Recommended Actions

1. **Add `recoverable` to `DriverError`.** This is the highest-priority gap. Modify `DriverError` to accept and store a `recoverable` parameter. Update the runtime's error handling to check this field and transition the driver state accordingly.

2. **Change `DriverHealth.latency_ms` to `float | None = None`.** Update the type annotation and default value. Have the runtime measure latency when calling `health_check()` and set it on the returned `DriverHealth`.

3. **Update the `Driver` protocol's `connect()` signature to include `event_bus` parameter** to match the resolved design decision and the implementation.

### Gap Summary

| Gap | Severity | Description |
|-----|----------|-------------|
| DriverError missing recoverable parameter | HIGH | Runtime cannot distinguish recoverable vs fatal errors |
| DriverHealth.latency_ms type mismatch | MEDIUM | Should be float | None, not float = 0.0 |
| Driver.connect() protocol signature mismatch | LOW | Protocol shows no params, implementation passes event_bus |
| Runtime does not measure latency_ms | MEDIUM | BaseDriver returns 0.0; runtime should measure actual latency |
