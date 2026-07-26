# Vision

## The Problem

Current AI agent frameworks treat environments as tool-call targets. The agent generates a function call. The framework executes it against the environment. The agent generates another function call. This is a synchronous loop: think, call, wait, think again.

This model works for stateless APIs. It does not work for environments.

Environments are continuous. A web page changes without prompting. A terminal produces output at arbitrary times. A robot's sensors stream data constantly. A game simulation runs on its own clock. The agent cannot control when observations arrive. It can only react to them.

The tool-call model forces the agent to poll — to repeatedly ask "what changed?" — introducing latency, wasting compute, and missing observations that arrive between polls. The agent is not embedded in the environment. It is a spectator watching a firehose through a straw.

The fundamental problem is architectural. Tool-call frameworks place the agent outside the environment, looking in. Embodied intelligence requires the agent inside the environment, living in the event stream.

## The Vision

Artax Network is an operating system for AI.

Not an operating system in the traditional sense — there is no kernel, no filesystem, no process scheduler in the Unix sense. Artax is an operating system for the problem of embodied intelligence: how does an AI agent perceive, reason, and act within a world?

The answer is events. Environments are persistent systems that emit semantic events. The AI reasons over a working memory of these events. Actions flow back to environments as consequences of reasoning. The runtime coordinates this cycle continuously, without blocking, without polling, without artificial synchronization points.

Artax is the substrate on which embodied agents are built. It is not the agent itself. It is the world the agent inhabits.

## What Artax Is NOT

**Not an agent framework.** Frameworks dictate how you write agents. They provide base classes, decorators, and patterns that agents must follow. Artax provides a runtime. Agents live inside it, but Artax does not prescribe how they reason, plan, or decide.

**Not a browser automation library.** Artax can drive a Chromium browser, but it is not limited to browsers. It is not a Playwright wrapper, a Selenium helper, or a Puppeteer alternative. It is a runtime that happens to include a Chromium driver.

**Not a prompt engineering tool.** Artax does not generate prompts, manage conversations, or wrap language models. It provides the substrate — events, memory, scheduling — on which reasoning engines operate. The reasoning engine is a separate concern.

**Not a workflow engine.** Artax does not define DAGs, steps, or pipelines. It defines a continuous event loop where observations flow in and actions flow out. There is no predefined sequence. The agent decides what to do at every tick.

## What Artax IS

Artax Network is an event-driven runtime for embodied intelligence.

It is the system that:

- Receives observations from environments through drivers.
- Stores observations as events in working memory.
- Lets a reasoning engine examine working memory and produce actions.
- Sends actions back to environments through drivers.
- Manages the timing and priority of all the above.
- Does all of this continuously, asynchronously, and without blocking.

Artax is the bridge between the continuous, concurrent world and the discrete, sequential reasoning of an AI agent. The runtime handles continuity. The agent handles decisions.

## Long-Term Goals

### v0.1 — Chromium Environment

The first driver. A Chromium browser as an environment. The agent observes DOM mutations, user interactions, and page state. The agent can navigate, click, type, and inspect. This validates the architecture with a real, complex environment.

### v0.2 — Terminal and Persistence

A terminal driver for shell interaction. SQLite and Redis memory backends for persistence across sessions. The runtime begins to support long-running agents that maintain context.

### v0.3 — Code Intelligence

A VS Code driver for editor integration. A plugin system for extending drivers and memory backends. The runtime becomes a development platform, not just a runtime.

### v0.4 — Desktop Environment

A desktop driver for GUI interaction. Window management, input simulation, screen capture. The agent inhabits a full desktop environment, not just a browser.

### v0.5 — Simulation

Drivers for Unity and Unreal Engine. Physics-based action validation. The runtime supports agents that learn and plan in simulated worlds before acting in real ones.

### v0.6 — Robotics

ROS 2 integration. Hardware abstraction. Real-time constraints. The runtime drives physical robots, not just virtual ones.

### v1.0 — Production Ready

Stable API. Production-hardened runtime. Comprehensive documentation. Performance benchmarks. Artax v1.0 is the version you deploy, not the version you experiment with.

## The Name

Artax is the horse from *The Neverending Story*. The horse that sinks in the Swamp of Sadness — not because it is weak, but because it gives in to despair.

In the story, Atreyu's quest is driven by emotion — fear, grief, determination. Artax is not a tool. He is a participant. He feels the world and responds to it.

Artax Network takes the same view. The runtime is not a tool that the agent calls. It is a participant in a continuous event stream. It feels the environment through events and responds through actions. The agent is not the caller. It is the inhabitant.
