# PRD: Driver API

**Subsystem:** `artax.drivers`
**Version:** 0.1
**Status:** Draft

---

## 1. Problem Statement

Embodied AI agents interact with many different environments — web browsers, terminals, desktop GUIs, simulation engines, robots. Each environment has unique APIs, data formats, and interaction patterns. Without a standardized interface, every driver would invent its own integration contract, coupling the runtime to specific environment implementations and making it impossible to add new environments without modifying the runtime core.

The Driver API solves this by defining a protocol-based interface that all drivers implement. The runtime never imports driver modules directly — it interacts with drivers exclusively through the Driver protocol. This means the runtime can manage a Chromium driver, a terminal driver, or a ROS 2 driver using the same lifecycle methods, the same event emission pattern, and the same action execution interface.

The Driver API is the contract between the runtime and the world. Drivers implement it; the runtime consumes it. Nothing in between.

---

## 2. Goals

1. **Driver protocol.** Define a `Driver` protocol (Python `Protocol` class) that specifies all methods a driver must implement. The protocol is the single source of truth for driver behavior.

2. **Lifecycle management.** Drivers have a clear lifecycle: instantiate → connect → running → disconnect. The runtime controls transitions. Drivers must handle each transition gracefully and report errors.

3. **Health checks.** Drivers implement a `health_check()` method that returns their current status. The runtime calls health checks periodically (configurable interval, default 30s). Unhealthy drivers are flagged but not automatically disconnected.

4. **Action execution.** Drivers accept actions from the runtime via `execute(action)`. Actions are typed objects with a name and parameters. The driver translates actions into environment-specific operations and returns results or errors.

5. **Event emission.** Drivers publish `SemanticEvent` objects to the EventBus when something happens in their environment. Drivers never emit events directly to subscribers — they always publish through the EventBus.

6. **Configuration protocol.** Each driver type defines a `DriverConfig` dataclass that specifies its configuration parameters. The runtime passes config to drivers at instantiation time.

7. **State reporting.** Drivers maintain a `DriverState` enum (disconnected, connecting, connected, unhealthy, error) that reflects their current status. The runtime reads state but does not set it — drivers own their state transitions.

---

## 3. Non-Goals

1. **Any specific driver implementation.** This PRD defines the interface only. The Chromium driver, terminal driver, and all others are separate PRDs.

2. **Driver discovery.** Drivers are not auto-discovered via entry points or directory scanning in v0.1. They are explicitly listed in configuration.

3. **Hot-swapping.** Drivers cannot be replaced at runtime. Changing a driver requires restarting the runtime.

4. **Driver-to-driver communication.** Drivers never communicate with each other directly. All inter-driver coordination flows through the EventBus.

5. **Driver versioning.** There is no version negotiation between runtime and driver. The runtime and all drivers are deployed together as a single package.

6. **Driver marketplace.** There is no external driver registry, installation mechanism, or third-party driver support in v0.1.

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Runtime                          │
│                                                     │
│  ┌───────────────────────────────────────────────┐ │
│  │              Driver Registry                   │ │
│  │                                               │ │
│  │  ┌─────────────────────────────────────────┐ │ │
│  │  │  Driver Protocol (interface)            │ │ │
│  │  │  ─────────────────────────────────────  │ │ │
│  │  │  connect() → None                       │ │ │
│  │  │  disconnect() → None                    │ │ │
│  │  │  observe() → AsyncIterator[Event]       │ │ │
│  │  │  execute(action) → ActionResult         │ │ │
│  │  │  health_check() → DriverHealth          │ │ │
│  │  └─────────────────────────────────────────┘ │ │
│  │                                               │ │
│  │  ┌──────────────┐  ┌──────────────┐          │ │
│  │  │ ChromiumDriver│  │ TerminalDriver│  ...    │ │
│  │  └──────────────┘  └──────────────┘          │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  ┌───────────────┐    ┌───────────────┐            │
│  │  EventBus      │    │  Scheduler    │            │
│  └───────────────┘    └───────────────┘            │
└─────────────────────────────────────────────────────┘
```

### Driver Lifecycle

```
                ┌──────────────┐
                │  Instantiated│
                └──────┬───────┘
                       │ connect()
                       ▼
                ┌──────────────┐
                │  Connecting  │
                └──────┬───────┘
                       │ success
                       ▼
                ┌──────────────┐
         ┌──────│  Connected   │──────┐
         │      └──────────────┘      │
         │ health_check() fail        │ disconnect()
         ▼                            ▼
  ┌──────────────┐           ┌──────────────┐
  │  Unhealthy   │           │ Disconnecting │
  └──────┬───────┘           └──────┬───────┘
         │ recovery                  │ success
         ▼                           ▼
  ┌──────────────┐           ┌──────────────┐
  │  Connected   │           │ Disconnected │
  └──────────────┘           └──────────────┘
```

### Action Flow

```
1. Scheduler dispatches ACTION_REQUESTED event
2. Runtime receives event, identifies target driver
3. Runtime calls driver.execute(action)
4. Driver translates action to environment operation
5. Driver returns ActionResult(success=True, data={...})
6. Runtime publishes ACTION_COMPLETED event
7. Memory stores result via event mapping
```

### Event Flow

```
1. Environment state changes (e.g., DOM mutation)
2. Driver detects change (via observation loop)
3. Driver creates SemanticEvent with type, source, payload
4. Driver calls event_bus.publish(event)
5. EventBus routes event to all matching subscribers
6. Memory, Scheduler, Dashboard receive the event
```

---

## 5. Interfaces

### Driver Protocol

```python
class Driver(Protocol):
    @property
    def name(self) -> str:
        """Unique name for this driver instance."""

    @property
    def state(self) -> DriverState:
        """Current lifecycle state."""

    async def connect(self) -> None:
        """Connect to the environment. Raise DriverError on failure."""

    async def disconnect(self) -> None:
        """Disconnect from the environment. Clean up resources."""

    async def observe(self) -> AsyncIterator[SemanticEvent]:
        """Yield events from the environment. Runs continuously while connected."""

    async def execute(self, action: Action) -> ActionResult:
        """Execute an action in the environment. Return result or error."""

    async def health_check(self) -> DriverHealth:
        """Check driver and environment health. Return health status."""

    def config(self) -> DriverConfig:
        """Return the driver's configuration."""
```

### DriverState

```python
class DriverState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    UNHEALTHY = "unhealthy"
    ERROR = "error"
```

### DriverHealth

```python
@dataclass
class DriverHealth:
    state: DriverState
    message: str = ""
    latency_ms: float | None = None
    last_event_at: float | None = None
    error_count: int = 0
```

### Action

```python
@dataclass
class Action:
    name: str  # "click", "type", "navigate", "screenshot"
    target: str | None = None  # CSS selector, URL, etc.
    parameters: dict[str, Any] = field(default_factory=dict)
    action_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=time.time)
```

### ActionResult

```python
@dataclass
class ActionResult:
    action_id: str
    success: bool
    data: Any = None
    error: str | None = None
    duration_ms: float = 0.0
```

### DriverConfig Protocol

```python
class DriverConfig(Protocol):
    @property
    def driver_type(self) -> str:
        """Identifier for the driver implementation (e.g., 'chromium', 'terminal')."""
```

### DriverError

```python
class DriverError(Exception):
    def __init__(self, driver: str, message: str, recoverable: bool = True) -> None: ...
```

---

## 6. Acceptance Criteria

1. Any class implementing the `Driver` protocol can be registered with the runtime.
2. `connect()` transitions the driver from DISCONNECTED to CONNECTED.
3. `disconnect()` transitions the driver from CONNECTED to DISCONNECTED.
4. `observe()` yields `SemanticEvent` objects continuously while the driver is connected.
5. `execute(action)` returns an `ActionResult` with `success=True` on successful execution.
6. `execute(action)` returns an `ActionResult` with `success=False` and error message on failure.
7. `health_check()` returns current state, latency, and error count.
8. `DriverState` transitions follow the documented state machine.
9. Drivers never publish events directly to subscribers — always through EventBus.
10. Drivers never import or reference other drivers.
11. `DriverError` with `recoverable=True` marks the driver as unhealthy; `recoverable=False` marks it as error.
12. The runtime calls `health_check()` at the configured interval and logs results.
13. Drivers handle `disconnect()` cleanly even if `observe()` is mid-iteration.
14. The Driver API contains no environment-specific logic, imports, or conditionals.

---

## 7. Future Extensions

1. **Driver discovery.** Auto-discover drivers via Python entry points. Allow third-party packages to register drivers.

2. **Hot-swapping.** Replace a running driver with a new instance without restarting the runtime. Requires state migration.

3. **Driver composition.** Allow drivers to wrap other drivers (e.g., a logging driver that wraps a Chromium driver).

4. **Driver capabilities.** Advertise which actions a driver supports. Runtime validates actions before calling `execute()`.

5. **Driver telemetry.** Drivers emit performance metrics (action latency, event throughput) that the dashboard visualizes.

6. **Driver versioning.** Negotiate API versions between runtime and driver for backward compatibility.

7. **Driver marketplace.** Curated registry of community drivers with install, update, and remove commands.

8. **Driver sandboxing.** Run drivers in separate processes for fault isolation. Communicate via IPC.

---

## 8. Resolved Decisions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | `observe()` returns AsyncIterator or callback? | **AsyncIterator** | Pythonic, supports backpressure via `async for`. Natural async iteration pattern. |
| 2 | `execute()` has timeout param? | **No, driver handles** | Driver knows best how to timeout its operations. Simpler API surface. |
| 3 | `health_check()` optional or required? | **Required** | Always know if driver is alive. Simple `bool` return. No silent failures. |
| 4 | EventBus passed at connect or instantiation? | **At connect time** | Driver gets EventBus when it needs it. Clean lifecycle, bus exists before driver uses it. |
| 5 | `DriverConfig` Protocol or dataclass? | **Protocol** | Flexible, duck-typing friendly. Drivers can use any data structure. |
| 6 | Runtime validates action names? | **Pass through** | Runtime agnostic. Driver decides what it supports. Decoupled architecture. |
| 7 | `observe()` backpressure mechanism? | **Yes** | Prevents memory issues with fast drivers. Standard async backpressure. |
| 8 | `latency_ms` measured by driver or runtime? | **Runtime measures** | More accurate end-to-end latency. Driver cannot measure round-trip accurately. |

---

*Document created: 2026-07-26*
*Last updated: 2026-07-26*
