# Design Principles and Decisions

## Design Principles

### 1. Events First

Everything is an event. Observations are events. Actions are events. State changes are events. Errors are events. There are no exceptions — every interaction within the runtime flows through the event bus.

This is not a communication preference. It is an architectural constraint. When everything is an event, every interaction is observable, replayable, and testable. There are no hidden side effects, no undocumented call chains, no implicit coupling.

### 2. Driver Agnostic

The runtime never knows which drivers are attached. It does not import driver code. It does not check driver types. It does not special-case any driver. Drivers are anonymous event sources and sinks.

This means adding a new driver requires zero changes to the runtime. Removing a driver requires zero changes. Replacing a driver requires zero changes. The runtime is permanent; drivers are transient.

### 3. Memory as Interface

Memory backends are Protocol classes, not concrete implementations. The runtime interacts with memory through a defined interface. The actual storage — in-memory dict, SQLite, Redis, or something else — is a configuration choice, not an architectural decision.

Swapping backends should take one configuration change, not a code refactor.

### 4. Minimal Core

The runtime does exactly five things:

1. Manages the event bus
2. Stores working memory
3. Schedules events and actions
4. Coordinates drivers
5. Runs the core loop

It does not interpret events. It does not decide what actions mean. It does not manage agent state beyond working memory. It does not provide logging, monitoring, or dashboards — those are separate concerns connected through events.

Every line of code in the runtime must justify its existence against these five responsibilities. If it does not directly support one of them, it does not belong in the core.

### 5. Async Native

All I/O is asynchronous from day one. There are no synchronous code paths wrapped in `asyncio.run()`. There are no blocking calls hidden behind `await`. Every operation that touches the outside world — network, disk, process — is async.

This is not optional. Environments are continuous and concurrent. A synchronous runtime cannot keep up with a browser, a terminal, and a sensor stream simultaneously.

### 6. Type Safe

Strict typing throughout. Every function signature, every return type, every data structure is fully typed. `mypy --strict` is the baseline, not the aspiration.

Typed events mean the compiler catches missing fields. Typed actions mean the compiler catches wrong parameters. Typed protocols mean the compiler catches broken driver implementations.

Type safety is not bureaucracy. It is the safety net that lets the runtime evolve without breaking drivers.

## Key Design Decisions

### Protocol Classes over ABCs

**Decision:** All interfaces are defined as `typing.Protocol` classes, not `abc.ABC` base classes.

**Rationale:** Protocol classes enable structural subtyping. A driver author does not need to inherit from anything. If their class has the right methods with the right signatures, it satisfies the protocol. This means:

- Drivers can be written in any style — inheritance, composition, functions.
- Drivers do not depend on Artax at import time. They can be developed and tested independently.
- Third-party drivers do not need `artax` as a runtime dependency — only the protocol definitions.

ABCs enforce nominal subtyping: you must inherit from the base class. This creates coupling. A driver author must import the base class, must call `super()`, and must navigate the class hierarchy. Protocols eliminate all of this.

### Event-Driven over Tool-Call

**Decision:** The runtime uses a continuous event stream, not a request-response tool-call model.

**Rationale:** Tool calls assume the agent is the caller and the environment is the callee. The agent asks "click this button," the environment responds "done." This works for stateless APIs. It breaks for environments.

Environments are continuous. A browser does not wait for the agent to ask "what changed?" — it emits changes as they happen. A terminal does not wait for the agent to read its output — output appears continuously. A robot does not wait for the agent to query its sensors — sensors stream data.

The tool-call model forces the agent to poll. The event model lets the agent react. This is the difference between "ask what happened" and "be told what happened."

### Separate Event Bus from Runtime

**Decision:** The event bus is a standalone subsystem, not embedded in the runtime class.

**Rationale:** Separation of concerns. The event bus has one job: deliver events. The runtime has a different job: coordinate subsystems. Mixing them creates a god class that does too many things.

Separation also enables testing. You can test the event bus without the runtime. You can test the runtime with a mock event bus. You can replace the event bus implementation without touching the runtime.

### WebSocket for Dashboard Communication

**Decision:** The dashboard connects to the runtime exclusively through WebSocket, not HTTP REST, not shared memory, not IPC.

**Rationale:** The dashboard needs real-time data. HTTP polling is wasteful and introduces latency. WebSocket provides bidirectional, low-latency communication. The dashboard can subscribe to events in real time and send commands back without establishing new connections.

WebSocket also enforces process isolation. The dashboard and runtime are separate processes. They cannot share memory, cannot import each other's code, cannot create hidden coupling. This is the same dependency discipline that keeps drivers decoupled.

### Protocol-Based Driver Interface

**Decision:** Drivers implement Protocol classes defined by the runtime, not concrete base classes.

**Rationale:** See "Protocol Classes over ABCs" above. The additional benefit for drivers is that the same Protocol can be implemented in other languages through FFI or interop. A TypeScript driver that satisfies the same structural contract could, in theory, communicate with the runtime through a bridge.

More practically, Protocol-based drivers can be developed without Artax installed. The protocol definitions are just type annotations. A driver author can type-check their implementation against the protocol without running the runtime.

## Anti-Patterns to Avoid

### Putting Browser Logic in Runtime

The runtime must never import Playwright, Selenium, or any browser-specific library. The runtime must never reference DOM, CSS selectors, or browser-specific APIs. The runtime must never special-case the Chromium driver.

If the runtime needs to know about browsers, the architecture is wrong. Browsers are environments. Environments are drivers. Drivers are outside the runtime.

### Synchronous Tool Calls

Never implement a synchronous call-and-response pattern. Never have the runtime block while waiting for a driver to complete an action. Never have the driver block while waiting for the runtime to send the next command.

All communication is event-based and non-blocking. If you find yourself writing `result = await driver.do_something()` in the runtime core, stop. The driver should emit an event when the operation completes. The runtime should react to that event.

### Global State

Never use module-level mutable state. Never use singletons. Never use global variables for configuration, connection pools, or shared data.

Configuration goes through the runtime config object. Connections go through dependency injection. Shared data goes through the event bus.

Global state creates hidden coupling. It makes testing unreliable. It makes concurrency dangerous. It makes refactoring painful.

### Circular Imports

Never create circular imports between packages. The dependency graph must be a DAG (directed acyclic graph).

If you find yourself importing from a package that imports from your package, the abstraction boundary is wrong. Extract the shared interface into a third package that both can import from. That third package is `artax/core/`.

### Runtime Awareness in Drivers

Drivers must never import from `artax/runtime/`. Drivers depend only on `artax/core/` — the protocol definitions and event types.

If a driver needs a runtime service (configuration, logging, state), it should receive it through dependency injection or event subscriptions, not by importing the runtime module.

### Reaching into Driver Internals

The runtime must never call a method on a driver that is not part of the Driver Protocol. The runtime must never access driver attributes that are not defined in the protocol. The runtime must never assume a driver's internal implementation.

The protocol is the contract. Anything outside the protocol does not exist.
