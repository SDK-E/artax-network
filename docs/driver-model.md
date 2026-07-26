# Driver System Deep Dive

A driver bridges the runtime to an external environment. It translates environment-specific signals into runtime events and translates runtime actions into environment-specific operations. The runtime never knows what a driver does internally — it only sees events and actions.

## What is a Driver

A driver is a module that:

1. **Connects** to an external environment (browser, terminal, robot, etc.).
2. **Observes** the environment and emits semantic events.
3. **Executes** actions sent by the runtime.
4. **Reports** its health status.
5. **Disconnects** cleanly when the runtime shuts down.

Drivers are pluggable. They can be added, removed, or replaced without modifying the runtime. They are discovered and registered at runtime startup.

## Driver Lifecycle

A driver passes through five states:

```
Created → Connected → Observing → Disconnecting → Disconnected
```

### 1. Created

The driver is instantiated. Configuration is passed in. No connection to the environment exists yet.

```python
driver = ChromiumDriver(
    config=ChromiumConfig(path="/usr/bin/chromium", headless=True),
    bus=event_bus,
)
```

### 2. Connected

The driver establishes a connection to the environment. This may involve launching a process (Chromium), opening a socket (terminal), or connecting to an API (robotics).

```python
await driver.connect()
```

If connection fails, the driver emits a `SystemEvent` with `event_type="driver.connection.failed"` and remains in the Created state.

### 3. Observing

The driver actively monitors the environment and emits semantic events. It also listens for actions on the event bus and executes them.

This is the steady state. The driver stays here until the runtime shuts down or an error occurs.

```python
await driver.start_observing()
```

### 4. Disconnecting

The runtime signals the driver to shut down. The driver stops observing, completes any in-flight actions, and releases environment resources.

```python
await driver.disconnect()
```

### 5. Disconnected

The driver has fully released all resources. It can be garbage collected.

### State Diagram

```
           connect()
Created ──────────→ Connected
  │                    │
  │                    │ start_observing()
  │                    ↓
  │               Observing
  │                    │
  │                    │ disconnect() or error
  │                    ↓
  │              Disconnecting
  │                    │
  ↓                    ↓
Disconnected ←─────────┘
```

## Driver Protocol

Every driver must implement the `DriverProtocol` defined in `artax/core/protocols.py`:

```python
class DriverProtocol(Protocol):
    """Protocol that all drivers must implement."""

    @property
    def driver_id(self) -> str:
        """Unique identifier for this driver instance."""
        ...

    @property
    def driver_type(self) -> str:
        """Type of this driver (e.g., 'chromium', 'terminal')."""
        ...

    @property
    def supported_action_types(self) -> list[str]:
        """List of action types this driver can execute."""
        ...

    async def connect(self) -> None:
        """Establish connection to the environment."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from the environment and release resources."""
        ...

    async def health_check(self) -> DriverHealth:
        """Report current driver health."""
        ...

    async def execute(self, action: ActionEvent) -> ActionResult:
        """Execute an action in the environment."""
        ...

    async def observe(self) -> None:
        """Start observing the environment and emitting events."""
        ...
```

### Protocol Methods

#### `driver_id`

A unique string identifying this driver instance. Used for event routing — actions target a specific `driver_id`.

#### `driver_type`

A string identifying the kind of driver. Used for discovery and configuration. Examples: `"chromium"`, `"terminal"`, `"vscode"`.

#### `supported_action_types`

A list of action type strings this driver can execute. The runtime uses this to validate actions before dispatching them.

#### `connect()`

Establish a connection to the environment. This is called once during startup. If connection fails, raise an exception — the runtime will handle the failure.

#### `disconnect()`

Release all resources. Stop observing. Close connections. Clean up processes. This is called once during shutdown.

#### `health_check()`

Return the current health status. Called periodically by the scheduler. Return `DriverHealth.HEALTHY` if the driver is operating normally, `DriverHealth.DEGRADED` if partially functional, `DriverHealth.UNHEALTHY` if not functional.

#### `execute(action)`

Execute an action in the environment. Return an `ActionResult` indicating success or failure. Actions are dispatched to the target driver based on `action.target == driver.driver_id`.

#### `observe()`

Start monitoring the environment and publishing semantic events to the event bus. This method runs continuously until `disconnect()` is called. It should be implemented as an async loop.

## Creating a New Driver

### Step 1: Create the Package

```bash
mkdir -p artax/drivers/mydriver
touch artax/drivers/mydriver/__init__.py
touch artax/drivers/mydriver/driver.py
touch artax/drivers/mydriver/config.py
```

### Step 2: Define Configuration

```python
# artax/drivers/mydriver/config.py
from dataclasses import dataclass


@dataclass(frozen=True)
class MyDriverConfig:
    host: str = "localhost"
    port: int = 9090
    timeout: float = 30.0
```

### Step 3: Define Event Types

```python
# artax/drivers/mydriver/events.py
from dataclasses import dataclass


@dataclass(frozen=True)
class MyEnvironmentEvent:
    """An observation from the MyDriver environment."""

    event_type: str  # e.g., "state_changed", "output_received"
    data: dict
```

### Step 4: Implement the Driver

```python
# artax/drivers/mydriver/driver.py
import time
from uuid import uuid4

from artax.core.events import SemanticEvent
from artax.core.protocols import DriverProtocol
from artax.core.models import ActionResult, DriverHealth


class MyDriver:
    def __init__(self, config, bus):
        self._config = config
        self._bus = bus
        self._connected = False

    @property
    def driver_id(self) -> str:
        return "mydriver"

    @property
    def driver_type(self) -> str:
        return "mydriver"

    @property
    def supported_action_types(self) -> list[str]:
        return ["send_command", "read_state"]

    async def connect(self) -> None:
        # Establish connection to the environment
        self._connected = True

    async def disconnect(self) -> None:
        # Release resources
        self._connected = False

    async def health_check(self) -> DriverHealth:
        if not self._connected:
            return DriverHealth.UNHEALTHY
        return DriverHealth.HEALTHY

    async def execute(self, action) -> ActionResult:
        # Translate action to environment-specific operation
        try:
            # ... execute the action ...
            return ActionResult(success=True, data={})
        except Exception as e:
            return ActionResult(success=False, error=str(e))

    async def observe(self) -> None:
        # Main observation loop
        while self._connected:
            # ... poll or subscribe to environment ...
            event = SemanticEvent(
                topic="mydriver.state.changed",
                data={...},
                source=self.driver_id,
                timestamp=time.time(),
                event_id=str(uuid4()),
                priority=5,
            )
            await self._bus.publish(event)
```

### Step 5: Register the Driver

```python
# artax/drivers/mydriver/__init__.py
from artax.drivers.mydriver.driver import MyDriver

__all__ = ["MyDriver"]
```

### Step 6: Write Tests

Create tests in `tests/unit/test_mydriver.py`, `tests/integration/test_mydriver.py`, and optionally `tests/e2e/test_mydriver.py`.

## Driver Configuration

Drivers are configured through environment variables or the runtime config object. The naming convention is:

```
ARTAX_<DRIVER_TYPE>_<SETTING>
```

Examples:

| Variable | Description |
|---|---|
| `ARTAX_CHROMIUM_PATH` | Path to Chromium binary |
| `ARTAX_CHROMIUM_HEADLESS` | Run headless |
| `ARTAX_TERMINAL_SHELL` | Shell to use |
| `ARTAX_TERMINAL_COLS` | Terminal width |
| `ARTAX_TERMINAL_ROWS` | Terminal height |

Drivers read their configuration during `connect()`. Configuration is immutable after connection.

## Error Handling

Drivers handle errors at two levels:

### Connection Errors

If the driver cannot connect to the environment, it raises an exception from `connect()`. The runtime catches this and marks the driver as failed.

```python
async def connect(self) -> None:
    try:
        self._process = await asyncio.create_subprocess_exec(...)
    except FileNotFoundError:
        raise DriverConnectionError(f"Chromium not found at {self._config.path}")
```

### Execution Errors

If an action fails during execution, the driver returns a failed `ActionResult`. The runtime emits a `SystemEvent` with the error details.

```python
async def execute(self, action: ActionEvent) -> ActionResult:
    try:
        await self._do_action(action)
        return ActionResult(success=True)
    except TimeoutError:
        return ActionResult(success=False, error="Action timed out")
    except EnvironmentError as e:
        return ActionResult(success=False, error=str(e))
```

### Observation Errors

If the observation loop encounters an error, the driver should:

1. Emit a `SystemEvent` with `event_type="driver.error"`.
2. Continue observing if the error is recoverable.
3. Emit a `SystemEvent` with `event_type="driver.disconnected"` and stop observing if the error is fatal.

```python
async def observe(self) -> None:
    while self._connected:
        try:
            observation = await self._environment.read()
            await self._publish_event(observation)
        except ConnectionLost:
            await self._bus.publish(
                SystemEvent(
                    event_type="driver.disconnected",
                    data={"driver_id": self.driver_id, "reason": "connection lost"},
                    timestamp=time.time(),
                    event_id=str(uuid4()),
                )
            )
            break
        except Exception as e:
            await self._bus.publish(
                SystemEvent(
                    event_type="driver.error",
                    data={"driver_id": self.driver_id, "error": str(e)},
                    timestamp=time.time(),
                    event_id=str(uuid4()),
                )
            )
```

## Health Checks

The scheduler periodically calls `health_check()` on each driver. Health status is reported as:

| Status | Meaning |
|---|---|
| `DriverHealth.HEALTHY` | Driver is operating normally |
| `DriverHealth.DEGRADED` | Driver is partially functional (e.g., slow response) |
| `DriverHealth.UNHEALTHY` | Driver is not functional |

The dashboard displays driver health. The scheduler can use health status to pause actions to unhealthy drivers.

### Health Check Implementation

```python
async def health_check(self) -> DriverHealth:
    if not self._connected:
        return DriverHealth.UNHEALTHY

    try:
        # Lightweight ping or status check
        await asyncio.wait_for(
            self._environment.ping(),
            timeout=5.0,
        )
        return DriverHealth.HEALTHY
    except asyncio.TimeoutError:
        return DriverHealth.DEGRADED
    except Exception:
        return DriverHealth.UNHEALTHY
```

## Example: Chromium Driver (v0.1)

The Chromium driver is the first driver shipped with Artax. It bridges a Chromium browser to the runtime.

### Capabilities

- Navigate to URLs
- Click elements (by selector, coordinates, or text)
- Type text into inputs
- Take screenshots
- Inspect DOM elements
- Monitor DOM mutations
- Handle JavaScript dialogs

### Event Topics

| Topic | Data |
|---|---|
| `chromium.dom.click` | Element clicked |
| `chromium.dom.mutation` | DOM changed |
| `chromium.dom.input` | Input value changed |
| `chromium.navigation` | Page navigated |
| `chromium.screenshot` | Screenshot captured |
| `chromium.error` | Browser error |

### Action Types

| Action Type | Parameters |
|---|---|
| `navigate` | `url: str` |
| `click` | `selector: str` or `x: int, y: int` |
| `type` | `selector: str, text: str` |
| `screenshot` | `path: str` (optional) |
| `evaluate` | `script: str` |
| `wait_for` | `selector: str, timeout: float` |

### Implementation Note

The Chromium driver uses Playwright for browser protocol access. Playwright is a dependency of the driver, not of the runtime. The runtime never imports Playwright.
