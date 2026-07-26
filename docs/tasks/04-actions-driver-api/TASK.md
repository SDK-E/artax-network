# Task 04: Implement Actions + Driver API

## Objective

Implement the action type system and driver protocol for Artax Network. The Driver API defines how environments (drivers) interact with the runtime. Actions are the commands the runtime sends to drivers; driver protocol defines the interface drivers must implement.

## Reference Documents

- **PRD**: `../../prd/prd-driver-api.md` — all resolved design decisions
- **Existing scaffolding**: `../../../artax/drivers/base.py`, `../../../artax/actions/types.py`
- **Depends on**: `../../../artax/events/types.py` — must be implemented first
- **Driver model**: `../../driver-model.md`

## Resolved Design Decisions

1. **`observe()` returns `AsyncIterator`** — Pythonic, supports backpressure via `async for`
2. **Driver handles timeouts internally** — driver knows best, simpler API
3. **`health_check()` is required** — always know if driver is alive, simple bool return
4. **EventBus passed at connect time** — clean lifecycle, bus exists before driver uses it
5. **`DriverConfig` is a Protocol** — flexible, duck-typing friendly
6. **Runtime passes through any action name** — runtime agnostic, driver decides what it supports
7. **Backpressure mechanism in `observe()`** — prevents memory issues with fast drivers
8. **Runtime measures `latency_ms`** — more accurate end-to-end latency

## Current State

Existing scaffolding has mismatches with PRD:

- `Driver.observe()` returns `list[Event]` instead of `AsyncIterator[Event]`
- `Driver.health_check()` returns `bool` instead of `DriverHealth` dataclass
- `DriverState` missing `UNHEALTHY` value
- `DriverConfig` has `driver_name` instead of `driver_type`
- `DriverHealth` dataclass missing entirely
- `DriverError` exception class missing
- `Action` uses `ActionType` enum (PRD says any action name string)
- `Action` has `id` (UUID) instead of `action_id` (str)
- `Action` has `timeout` (timedelta) — PRD says driver handles timeouts

## Implementation Steps

### Step 1: Reconcile `../../../artax/actions/types.py`

```python
class Action:
    action_id: str  # UUID hex string
    name: str  # action name (NOT enum — any string)
    target: str | None = None  # CSS selector, URL, etc.
    parameters: dict[str, Any] = field(default_factory=dict)
    timestamp: float  # time.monotonic()

class ActionResult:
    action_id: str
    success: bool
    data: Any = None
    error: str | None = None
    duration_ms: float = 0.0

class Intent:
    description: str
    actions: list[Action]
    priority: str = "medium"  # or use Priority from scheduler
```

Remove `ActionType` enum — actions use free-form string names. Remove `timeout` from Action.

### Step 2: Reconcile `../../../artax/drivers/base.py`

```python
class DriverState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    UNHEALTHY = "unhealthy"
    ERROR = "error"

class DriverHealth:
    state: DriverState
    message: str = ""
    latency_ms: float = 0.0  # measured by runtime
    last_event_at: float | None = None
    error_count: int = 0

class DriverConfig(Protocol):
    @property
    def driver_type(self) -> str: ...

class Driver(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def environment(self) -> str: ...
    @property
    def is_connected(self) -> bool: ...
    async def connect(self, event_bus: EventBus) -> None: ...
    async def disconnect(self) -> None: ...
    async def observe(self) -> AsyncIterator[Event]: ...
    async def execute(self, action: Action) -> ActionResult: ...
    async def health_check(self) -> DriverHealth: ...

class DriverError(Exception):
    """Base exception for driver errors."""
    pass

class DriverConnectionError(DriverError):
    """Driver failed to connect."""
    pass

class DriverTimeoutError(DriverError):
    """Driver operation timed out."""
    pass

class DriverActionError(DriverError):
    """Driver action execution failed."""
    pass
```

### Step 3: Implement `BaseDriver`

Create an abstract base class in `../../../artax/drivers/base.py` that provides common driver functionality:

```python
class BaseDriver(ABC):
    """Base class providing common driver functionality."""

    def __init__(self, name: str, config: DriverConfig) -> None:
        self._name = name
        self._config = config
        self._state = DriverState.DISCONNECTED
        self._event_bus: EventBus | None = None
        self._error_count = 0
        self._last_event_at: float | None = None

    @property
    def name(self) -> str: ...
    @property
    def environment(self) -> str: ...
    @property
    def is_connected(self) -> bool: ...

    async def connect(self, event_bus: EventBus) -> None:
        # Set state to CONNECTING, call _do_connect(), set CONNECTED
        # On error: set ERROR, increment error_count
        ...

    async def disconnect(self) -> None:
        # Set state to DISCONNECTED, call _do_disconnect()
        ...

    async def health_check(self) -> DriverHealth:
        # Runtime wraps this call to measure latency_ms
        # Default: return DriverHealth(state=self._state)
        ...

    @abstractmethod
    async def _do_connect(self) -> None: ...
    @abstractmethod
    async def _do_disconnect(self) -> None: ...
    @abstractmethod
    async def observe(self) -> AsyncIterator[Event]: ...
    @abstractmethod
    async def execute(self, action: Action) -> ActionResult: ...

    async def _publish_event(self, event: Event) -> None:
        # Helper to publish event to bus if connected
        ...
```

### Step 4: Write tests

Create `tests/test_actions.py`:
- Test Action creation with all fields
- Test Action default values
- Test ActionResult creation
- Test Intent creation
- Test free-form action names (not restricted to enum)

Create `tests/test_driver_api.py`:
- Test DriverState enum values (including UNHEALTHY)
- Test DriverHealth dataclass
- Test DriverError hierarchy
- Test BaseDriver connect/disconnect lifecycle
- Test BaseDriver health_check returns DriverState
- Test BaseDriver _publish_event helper
- Test that BaseDriver enforces abstract methods (cannot instantiate directly)
- Test action passthrough (any string name accepted)

## Technical Constraints

- `AsyncIterator` return type for `observe()` — use `async def observe(self) -> AsyncIterator[Event]` with `yield`
- ABC for `BaseDriver` — `@abstractmethod` for `_do_connect`, `_do_disconnect`, `observe`, `execute`
- `uuid.uuid4().hex` for action IDs
- `time.monotonic()` for timestamps
- Strict typing for `mypy --strict`
- No driver-specific logic in base classes

## Quality Gates

```bash
python3 -m py_compile artax/actions/types.py
python3 -m py_compile artax/drivers/base.py
python3 -c "from artax.actions.types import Action, ActionResult, Intent; print('OK')"
python3 -c "from artax.drivers.base import Driver, BaseDriver, DriverHealth; print('OK')"
pytest tests/test_actions.py tests/test_driver_api.py -v
```

## Files

| Action | File |
|--------|------|
| MODIFY | `../../../artax/actions/types.py` |
| MODIFY | `../../../artax/drivers/base.py` |
| CREATE | `tests/test_actions.py` |
| CREATE | `tests/test_driver_api.py` |
