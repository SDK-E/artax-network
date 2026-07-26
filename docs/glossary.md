# Glossary

## Runtime

The core execution engine that manages the event loop, coordinates drivers, and orchestrates agent behavior. The runtime is the single process that owns the event bus, memory subsystem, and scheduler. It is the substrate on which embodied agents operate. The runtime never knows which drivers are attached — it communicates exclusively through events.

## Event

A discrete occurrence within the runtime, represented as a typed data object. Events are the fundamental unit of communication between all subsystems. Every action, observation, and internal signal flows as an event. Events are immutable once created. They carry a topic, source, timestamp, priority, and payload.

## Semantic Event

An event that carries parsed, structured meaning extracted from raw environment data. For example, a semantic event from the Chromium driver might represent "user clicked the submit button" rather than raw DOM coordinates. Semantic events are what the agent reasons about. The driver is responsible for converting raw observations into semantic events. The runtime never interprets raw data.

## Event Bus

The internal pub/sub channel through which all events flow. The event bus decouples producers (drivers, memory, scheduler) from consumers (the agent loop, logging, diagnostics). Events are routed by topic using dot-notation hierarchy. The event bus is the only communication channel between subsystems — there are no direct method calls between components.

## Event Loop

The continuous cycle within the runtime that polls for new events, dispatches them to registered handlers, and triggers the next decision cycle. The event loop is asynchronous and non-blocking — it never waits on a single driver or subsystem. It runs on Python's `asyncio` event loop.

## Driver

A module that bridges the runtime to an external environment. Drivers translate environment-specific signals into runtime events and translate runtime actions into environment-specific operations. Drivers implement the Driver Protocol and are pluggable — they can be added, removed, or replaced without modifying the runtime. Examples: Chromium driver, terminal driver, ROS 2 driver.

## Driver API

The interface contract (defined as Protocol classes in `artax/core/protocols.py`) that every driver must implement. The Driver API defines how drivers register with the runtime, emit events, accept actions, and report status. All drivers implement the same interface regardless of their target environment. The runtime interacts with drivers only through this API.

## Driver Lifecycle

The sequence of states a driver passes through: Created → Connected → Observing → Disconnecting → Disconnected. A driver starts in the Created state, establishes a connection to its environment, begins observing and emitting events, and shuts down cleanly when the runtime stops. Each transition is managed by the runtime's driver coordination system.

## Environment

Any external system or world that an agent interacts with through a driver. Environments include web browsers, terminals, desktop GUIs, game simulations, and physical robots. Environments are persistent, continuous, and concurrent — they do not wait for the agent to ask what happened. They emit observations on their own schedule. Artax treats every environment as an event source.

## Working Memory

A bounded, attention-scoped store that holds the agent's current context. Working memory contains the events the agent is reasoning over right now. It is updated every tick based on incoming events. Old events are evicted when capacity is reached, based on priority and age. Working memory has swappable backends (in-memory, SQLite, Redis) and supports snapshot/restore for state persistence.

## Memory Backend

The underlying storage implementation for working memory. The runtime interacts with memory through the MemoryBackend Protocol. Backend choices include in-memory (fast, volatile), SQLite (persistent, single-process), and Redis (fast, persistent, distributed). Swapping backends requires only a configuration change.

## Memory Snapshot

A serializable representation of working memory at a point in time. Snapshots capture all events, capacity, and metadata. They are used for debugging, session resumption, checkpointing, and testing. Snapshots can be saved to disk and restored later.

## Scheduler

The subsystem that determines the timing and priority of agent actions. The scheduler decides when the agent processes events, when it acts, and when it waits. It supports immediate dispatch, deferred execution, periodic tasks, and priority queuing. The scheduler does not make decisions about what to do — it only decides when things happen.

## Priority Queue

The scheduler's internal data structure for ordering events. Events are dequeued by priority (0-9, highest first), with FIFO ordering within the same priority level. High-priority events are processed before low-priority ones. Priority is set by the event creator and can be adjusted by the scheduler through aging.

## Tick

One cycle of the core loop: dequeue an event, update working memory, let the agent reason, produce an action (or wait), dispatch the action. Ticks are not periodic — they happen as fast as events arrive and the agent can process them. The scheduler enforces tick limits to prevent infinite loops.

## Action

A concrete operation the runtime sends to a driver for execution. Actions are the output side of the agent loop — they represent what the agent chose to do. Each action targets a specific driver and carries parameters the driver understands. Actions flow through the event bus and are dispatched to the target driver.

## Action Result

The outcome of an action executed by a driver. An action result indicates success or failure and may carry additional data (e.g., a screenshot path, a command's output). Action results are emitted as events so the agent can observe the consequences of its actions.

## Action Type

A string identifier for the kind of operation an action performs. Examples: `click`, `type`, `navigate`, `execute`, `move`. Each driver defines which action types it supports. The runtime validates action types before dispatching.

## Intent

A high-level goal or objective that the agent is pursuing. Intents are decomposed into sequences of actions by the runtime's planning layer. Intents persist across multiple event cycles until satisfied or abandoned. An intent represents what the agent is trying to accomplish, while actions represent what it is doing right now.

## Embodied AI

AI agents that interact with environments through sensors and actuators rather than purely through text. An embodied agent perceives, decides, and acts within a world — whether that world is a web browser, a terminal, or a robot. Embodied AI requires continuous, event-driven interaction, not synchronous tool calls.

## Tool Call

A pattern where an LLM generates structured function invocations that an external runtime executes. The agent calls a function, waits for the result, then calls another function. This is a synchronous request-response model. Artax does not use tool calls. Instead, events flow bidirectionally: the runtime pushes observations to the agent, and the agent emits actions back. There is no request-response round-trip — the agent is always embedded in the event stream.

## State

The complete internal configuration of the runtime at a point in time, including working memory contents, active intents, scheduled tasks, and driver statuses. State is serializable for checkpointing and debugging. State can be reconstructed from the event log by replaying events.

## Observation

A raw signal from an environment before it has been processed into a semantic event. Observations are the unfiltered input — screenshots, keystroke logs, sensor readings. The driver normalizes observations into semantic events for the agent. The runtime never sees raw observations — it only sees semantic events.

## Agent

The decision-making entity within the runtime. The agent observes events, updates its working memory, evaluates intents, and produces actions. The agent is not a language model — it is the full loop of perception, reasoning, and action. The agent lives inside the runtime as a participant in the event stream, not as a caller outside it.

## Core Loop

The continuous cycle within the runtime that ties together the event bus, working memory, scheduler, and agent. On each iteration, the loop dequeues events, updates memory, lets the agent reason, and dispatches actions. The core loop is the heartbeat of the runtime.

## Heartbeat

A periodic signal emitted by a driver or subsystem indicating its health status. Heartbeats are used by the dashboard for display and by the scheduler for detecting stalled drivers. A missing heartbeat indicates a driver may be unhealthy or disconnected.

## Topic

A hierarchical string that classifies events for routing on the event bus. Topics follow dot-notation: `<driver>.<subsystem>.<event>`. Subscribers filter by topic patterns (exact match, prefix match, or wildcard). Topics enable selective event delivery without tight coupling between publishers and subscribers.

## Backpressure

A flow control mechanism where the scheduler limits event processing when events arrive faster than they can be handled. Backpressure prevents memory exhaustion and ensures the runtime remains responsive. It may involve dropping low-priority events, throttling drivers, or pausing processing.

## Aging

A scheduler mechanism that increases the priority of events that have waited too long. Aging prevents starvation of low-priority events — events that would never be processed if only priority mattered. After a configurable threshold, an event's priority is bumped up by a fixed increment.

## Snapshot

See Memory Snapshot. Also used informally to refer to any serialized representation of runtime state at a point in time.

## Protocol

A Python typing construct (`typing.Protocol`) that defines a structural interface. Classes that implement the methods defined in a Protocol satisfy it without explicit inheritance. Artax uses Protocol classes for all interfaces (Driver, Memory, Scheduler) to enable duck typing and reduce coupling.

## Conventional Commits

A commit message specification used by Artax. Format: `<type>(<scope>): <description>`. Types include `feat`, `fix`, `docs`, `refactor`, `test`, `chore`. This standard makes commit history readable and enables automated changelog generation.
