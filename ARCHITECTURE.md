# Architecture

Artax is a runtime, not a framework. Components communicate exclusively through events. No component imports another component's internals — they subscribe to events and emit events. The runtime owns nothing except the bus, the memory, and the scheduler.

## Core Components

```
┌─────────────────────────────────────────────┐
│                  Runtime                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │ EventBus │  │ Memory   │  │ Scheduler │ │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘ │
│       └──────────────┼──────────────┘       │
│              ┌───────┴───────┐              │
│              │   Core Loop   │              │
│              └───────┬───────┘              │
└──────────────────────┼──────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   ┌────┴────┐  ┌──────┴──┐  ┌───────┴───────┐
   │Chromium │  │Terminal │  │    Future     │
   │ Driver  │  │ Driver  │  │   Drivers     │
   └─────────┘  └─────────┘  └───────────────┘
```

The runtime contains exactly five subsystems:

1. **EventBus** — pub/sub channel for all events
2. **Memory** — bounded working memory store
3. **Scheduler** — timing and priority management
4. **Core Loop** — the continuous cycle that ties everything together
5. **Driver API** — the interface contract drivers implement

Everything else — drivers, the dashboard, external tools — lives outside the runtime and communicates through events or WebSocket.

## Event Flow

The event flow is unidirectional and continuous:

```
Driver observes environment
    → emits SemanticEvent to EventBus
        → Scheduler picks up event
            → WorkingMemory updates
                → Core Loop runs reasoning cycle
                    → produces Action
                        → EventBus dispatches Action
                            → Driver executes Action in environment
                                → Driver observes result
                                    → cycle repeats
```

There is no "call and wait." The runtime never blocks on a driver. The driver never blocks on the runtime. Events flow continuously, and the agent reasons over the accumulated stream.

### Event Flow in Detail

1. **Observation.** A driver detects a change in its environment. A Chromium driver sees a DOM mutation. A terminal driver sees new stdout output. A robotics driver sees a sensor reading.

2. **Semantic Event.** The driver translates the raw observation into a typed semantic event. Raw DOM coordinates become `ButtonClicked(label="Submit")`. Raw text becomes `TerminalOutput(text="...")`. The driver decides what the event means — the runtime does not interpret environment data.

3. **Event Bus.** The semantic event enters the bus. Subscribers receive it: the working memory stores it, the scheduler evaluates it, the dashboard displays it.

4. **Working Memory Update.** The memory subsystem incorporates the new event into the agent's current context. Old events may be evicted based on attention scope or priority.

5. **Reasoning Cycle.** The core loop triggers. The agent examines working memory and produces an action — what to do next given everything it has observed.

6. **Action Dispatch.** The action enters the event bus and is routed to the target driver.

7. **Execution.** The driver receives the action and executes it in the environment. The Chromium driver clicks a button. The terminal driver types a command. The robotics driver moves a joint.

8. **Cycle.** The driver observes the result of the action and the cycle begins again.

## Dependency Rules

These rules are enforced architecturally and must never be violated:

| Rule | Rationale |
|---|---|
| Runtime **never** imports driver code | Runtime must not know which drivers exist. Drivers are pluggable. |
| Drivers depend on runtime **interfaces only** | Drivers implement protocols defined by the runtime. They never import runtime internals. |
| Dashboard communicates via **WebSocket only** | Dashboard is a separate process. No shared memory, no direct imports. |
| **No circular dependencies** between subsystems | EventBus, Memory, and Scheduler are independent. The Core Loop coordinates them but none depends on the others. |
| Drivers are **self-contained** modules | A driver can be installed, removed, or replaced without affecting the runtime or other drivers. |

### Dependency Graph

```
drivers/chromium/ ──→ artax/core/interfaces.py (protocols)
drivers/terminal/ ──→ artax/core/interfaces.py (protocols)
dashboard/         ──→ WebSocket ──→ artax/runtime/ (server)
artax/runtime/     ──→ artax/core/interfaces.py (protocols)
artax/core/        ──→ (no internal dependencies)
```

The `artax/core/` package contains only Protocol definitions, event types, and data models. It has zero imports from `artax/runtime/` or any driver. This is the dependency root.

## Subsystems

### Runtime Core

The runtime core is the orchestrator. It:

- Owns the event loop (`asyncio` based)
- Coordinates subsystem initialization and shutdown
- Provides the top-level API for starting, stopping, and introspecting the runtime
- Manages driver registration and lifecycle

The core does **not** contain business logic for any specific environment. It does not interpret events. It does not decide what actions mean. It is pure coordination.

### Event System

The event system is a typed, topic-based pub/sub bus. Key properties:

- **Typed events.** Every event has a Python type with fields. No untyped dictionaries.
- **Topic routing.** Events are published to topics (e.g., `chromium.dom.click`, `scheduler.tick`). Subscribers filter by topic.
- **Async delivery.** All delivery is non-blocking. Subscribers receive events as they arrive, never polled.
- **Replay.** Events can be logged and replayed for debugging and testing.

The event bus is the **only** communication channel between subsystems. There are no direct method calls between the event bus and drivers, between the scheduler and drivers, or between memory and the dashboard.

### Working Memory

Working memory is the agent's short-term context. It holds the events the agent is currently reasoning over.

Key properties:

- **Bounded.** Memory has a fixed capacity. When full, the least-relevant events are evicted.
- **Attention-scoped.** The agent specifies which event types and time ranges are relevant to the current task. Memory filters accordingly.
- **Swappable backends.** The default backend is in-memory (fast, no persistence). SQLite and Redis backends are available for persistence and shared state.
- **Snapshot/restore.** Memory can be serialized to a snapshot and restored later. This enables checkpointing, debugging, and session resumption.

Memory is a Protocol — any backend that implements the interface works. The runtime never knows which backend is active.

### Scheduler

The scheduler controls timing and priority. It determines:

- When the core loop runs (tick-based)
- Which events get processed first (priority queue)
- When the agent should pause and wait for more input
- How to handle high-frequency event streams (throttling, debouncing)

The scheduler does **not** make decisions about what to do — that is the agent's job. The scheduler only decides **when** things happen.

### Driver API

The driver API is a set of Protocol classes that every driver must implement. This is the only contract between drivers and the runtime.

The protocol defines:

- **Lifecycle methods:** `connect()`, `disconnect()`, `health_check()`
- **Observation methods:** `observe()` — called by the runtime to poll or subscribe
- **Action methods:** `execute(action)` — called by the runtime when an action targets this driver
- **Metadata:** `driver_id`, `driver_type`, `supported_action_types`

Drivers implement these protocols. The runtime calls them through the protocol interface. The runtime never reaches into driver internals.

### Actions

Actions are typed data objects that represent what the agent wants to do. Each action has:

- **Target driver.** Which driver should execute this action.
- **Action type.** What kind of operation (click, type, navigate, move, etc.).
- **Parameters.** Environment-specific data the driver needs.

Actions flow through the event bus. They are dispatched to the target driver, executed, and the result is emitted as an event. There is no return value — the agent observes the result as a new event.

## Extension Points

Artax is designed to be extended without modifying the core:

| Extension Point | How to Extend |
|---|---|
| **New driver** | Implement the Driver Protocol in a new package. Register with the runtime. |
| **New memory backend** | Implement the Memory Protocol. Swap via configuration. |
| **New event type** | Define a new event class. Publish to the bus. No runtime changes needed. |
| **Custom scheduler policy** | Implement the Scheduler Protocol. Replace via configuration. |
| **Dashboard widgets** | Connect to the WebSocket API. Render custom views. |

## Technology Stack

| Component | Technology |
|---|---|
| Runtime core | Python 3.12+, `asyncio` |
| Event system | Custom typed pub/sub over `asyncio.Queue` |
| Memory | In-memory (default), SQLite, Redis |
| Scheduler | Custom priority queue over `asyncio` |
| Dashboard | Node.js, Next.js, WebSocket |
| Chromium driver | Playwright (for browser protocol access) |
| Testing | `pytest`, `pytest-asyncio`, `pytest-cov` |
| Linting | Ruff (lint + format), mypy (strict) |
| CI | GitHub Actions |
| Containerization | Docker, Docker Compose |
