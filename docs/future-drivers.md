# Future Driver Plans

Artax v0.1 ships with a single driver: Chromium. The architecture is designed so that adding new drivers requires zero changes to the runtime core. This document describes planned drivers and how to create your own.

## Planned Drivers

### Terminal Driver (v0.2)

Interact with shell processes and command-line environments.

**Capabilities:**

- Execute shell commands
- Read stdout and stderr in real time
- Send input to interactive processes
- Manage working directory
- Handle signals (SIGINT, SIGTERM)

**Event Topics:**

| Topic | Description |
|---|---|
| `terminal.output` | Command produced output |
| `terminal.error` | Command produced stderr output |
| `terminal.exit` | Process exited |
| `terminal.prompt` | Shell prompt detected |

**Action Types:**

| Action Type | Parameters |
|---|---|
| `execute` | `command: str, cwd: str` |
| `send_input` | `text: str` |
| `send_signal` | `signal: int` |
| `resize` | `cols: int, rows: int` |

**Use Cases:** CLI automation, server management, build system interaction, DevOps workflows.

### VS Code Driver (v0.3)

Integrate with Visual Studio Code for code intelligence.

**Capabilities:**

- Open and navigate files
- Read and edit code
- Run terminal commands within VS Code
- Access workspace structure
- Execute code actions (refactoring, formatting)

**Event Topics:**

| Topic | Description |
|---|---|
| `vscode.file.opened` | File opened in editor |
| `vscode.file.changed` | File content modified |
| `vscode.cursor.moved` | Cursor position changed |
| `vscode.diagnostic` | Linter/compiler diagnostic |
| `vscode.terminal.output` | Integrated terminal output |

**Action Types:**

| Action Type | Parameters |
|---|---|
| `open_file` | `path: str` |
| `edit` | `path: str, range: str, replacement: str` |
| `run_command` | `command: str, args: list[str]` |
| `format` | `path: str` |
| `refactor` | `action: str, range: str` |

**Use Cases:** Code editing automation, automated refactoring, linting workflows, code review assistance.

### Desktop Driver (v0.4)

Interact with desktop GUI environments across platforms.

**Capabilities:**

- Window management (find, focus, resize, move)
- Mouse movement and clicks
- Keyboard input
- Screen capture
- Clipboard access
- Accessible tree inspection

**Event Topics:**

| Topic | Description |
|---|---|
| `desktop.window.created` | New window appeared |
| `desktop.window.focused` | Window gained focus |
| `desktop.window.closed` | Window closed |
| `desktop.input.click` | Mouse click |
| `desktop.input.key` | Keyboard event |
| `desktop.screen.capture` | Screenshot captured |

**Action Types:**

| Action Type | Parameters |
|---|---|
| `click` | `x: int, y: int, button: str` |
| `type` | `text: str` |
| `hotkey` | `keys: list[str]` |
| `screenshot` | `region: str` (optional) |
| `window_find` | `title: str` |
| `window_move` | `window_id: str, x: int, y: int` |

**Use Cases:** GUI automation, desktop testing, accessibility tooling, cross-platform input simulation.

### Unity Driver (v0.5)

Interact with Unity game engine simulations.

**Capabilities:**

- Read game state (objects, positions, physics)
- Control characters and objects
- Access sensor data (cameras, colliders)
- Execute physics queries (raycasts, overlaps)
- Modify scene hierarchy

**Event Topics:**

| Topic | Description |
|---|---|
| `unity.scene.loaded` | Scene loaded |
| `unity.physics.collision` | Collision detected |
| `unity.object.spawned` | Object instantiated |
| `unity.object.destroyed` | Object destroyed |
| `unity.sensor.data` | Sensor reading received |

**Action Types:**

| Action Type | Parameters |
|---|---|
| `move` | `object_id: str, direction: vec3` |
| `interact` | `object_id: str, action: str` |
| `raycast` | `origin: vec3, direction: vec3` |
| `spawn` | `prefab: str, position: vec3` |
| `destroy` | `object_id: str` |

**Use Cases:** Game AI training, simulation-based testing, reinforcement learning, procedural generation.

### Unreal Engine Driver (v0.5)

Similar to the Unity driver but for Unreal Engine.

**Capabilities:**

- Blueprint interaction
- Actor control
- Physics simulation access
- Level streaming
- Niagara particle system control

**Event Topics and Action Types** mirror the Unity driver's structure with Unreal-specific naming.

**Use Cases:** High-fidelity simulation, AAA game AI, architectural visualization, digital twins.

### ROS 2 Driver (v0.6)

Integrate with Robot Operating System 2 for physical and simulated robots.

**Capabilities:**

- Publish and subscribe to ROS 2 topics
- Call ROS 2 services
- Access ROS 2 parameters
- Manage ROS 2 nodes
- Handle TF transforms

**Event Topics:**

| Topic | Description |
|---|---|
| `ros2.topic.<name>` | Message on a ROS 2 topic |
| `ros2.service.response` | Service call response |
| `ros2.parameter.changed` | Parameter value changed |
| `ros2.node.discovered` | New node discovered |
| `ros2.tf.update` | Transform updated |

**Action Types:**

| Action Type | Parameters |
|---|---|
| `publish` | `topic: str, message_type: str, data: dict` |
| `service_call` | `service: str, type: str, args: dict` |
| `set_parameter` | `node: str, name: str, value: any` |
| `send_goal` | `action: str, goal: dict` |

**Use Cases:** Robotics control, autonomous navigation, manipulation, sensor fusion.

## How to Create a New Driver

### Prerequisites

- Understanding of the environment you are bridging.
- Python 3.12+.
- Familiarity with Artax's event model (read [docs/event-model.md](event-model.md)).

### Step-by-Step

1. **Define the driver's scope.** What observations will it emit? What actions will it execute? What is the minimum viable feature set?

2. **Create the package.** Create a directory under `artax/drivers/<name>/` with `__init__.py`, `driver.py`, `config.py`, and `events.py`.

3. **Define event types.** What semantic events will this driver produce? Define them in `events.py`.

4. **Define action types.** What actions can this driver execute? Define them as supported action types in the driver.

5. **Implement the Driver Protocol.** See [docs/driver-model.md](driver-model.md) for the full protocol specification.

6. **Write tests.** Unit tests for internal logic. Integration tests for event emission. End-to-end tests for full cycles.

7. **Register the driver.** Add the driver to the runtime's driver registry. This can be done through configuration or programmatic registration.

8. **Document the driver.** Add a README to the driver package describing its capabilities, configuration, and usage.

### Driver Checklist

- [ ] Implements `DriverProtocol` from `artax/core/protocols.py`.
- [ ] Has a unique `driver_id`.
- [ ] `connect()` and `disconnect()` are implemented and tested.
- [ ] `health_check()` returns correct status.
- [ ] `observe()` emits semantic events to the bus.
- [ ] `execute()` handles all supported action types.
- [ ] Error handling is robust (connection failures, timeouts, invalid actions).
- [ ] Unit tests cover all public methods.
- [ ] Integration tests verify event emission.
- [ ] Configuration is documented.
- [ ] The driver does not import from `artax/runtime/`.

### Testing Your Driver

```bash
# Unit tests
pytest tests/unit/test_mydriver.py

# Integration tests
pytest tests/integration/test_mydriver.py

# End-to-end tests (requires environment)
pytest tests/e2e/test_mydriver.py

# Full check
make check
```

### Publishing a Third-Party Driver

Third-party drivers are packages that implement the Driver Protocol without depending on `artax/runtime/`. They depend only on `artax/core/` for protocol definitions and event types.

To publish a third-party driver:

1. Create a separate repository.
2. Depend on `artax-network` (or just the protocol definitions).
3. Implement the Driver Protocol.
4. Publish to PyPI.
5. Document installation and configuration.

The runtime discovers third-party drivers through entry points or configuration.
