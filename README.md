# Artax Network

<!-- badges-start -->
[![CI](https://github.com/sdk-e/artax-network/actions/workflows/ci.yml/badge.svg)](https://github.com/sdk-e/artax-network/actions)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)
<!-- badges-end -->

**Event-driven runtime for embodied AI.**

---

## What is Artax Network

AI should not interact with the world through synchronous tool calls. Tool calls assume a request-response loop: the agent asks, the environment answers, the agent asks again. This breaks down the moment the environment is continuous, concurrent, or stateful — which is every real environment.

Artax Network takes the opposite approach. Environments emit semantic events into a shared runtime. The reasoning engine operates over a working memory of events. Actions flow back to environments as consequences of reasoning, not as responses to function calls.

The runtime is the substrate. It manages the event bus, working memory, scheduling, and driver coordination. The agent — the decision-making entity — lives inside the runtime as a participant, not as a caller.

This is not a framework. This is a runtime. Think operating system, not application library.

## Philosophy

Artax Network is **not**:

- **An agent framework.** Frameworks dictate how you write agents. Artax provides a runtime that agents live inside.
- **A browser automation library.** Artax can drive a browser, but it is not limited to browsers.
- **A Playwright wrapper.** Playwright is a tool. Artax is an environment that happens to include a Chromium driver.

Artax Network **is**:

- An event-driven runtime for environments that agents inhabit.
- A system where observations flow in as events and actions flow out as consequences.
- An architecture designed from day one to support Chromium, terminals, desktops, simulations, and robots — through the same interface.

## Key Concepts

| Concept            | Description                                                                                                                                                          |
|--------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Runtime**        | The core engine that owns the event bus, memory, and scheduler. Components communicate exclusively through events.                                                   |
| **Events**         | Typed data objects representing everything that happens — observations, actions, state changes, errors. The only communication channel.                              |
| **Working Memory** | Bounded, attention-scoped store of events the agent is reasoning over right now. Swappable backends (in-memory, SQLite, Redis).                                      |
| **Scheduler**      | Determines when the agent processes events, acts, or waits. Supports priorities, pausing, and tick-based processing.                                                 |
| **Drivers**        | Bridge the runtime to external environments. Drivers emit events when they observe the environment and accept actions to execute. v0.1 ships with a Chromium driver. |
| **Actions**        | Concrete operations sent to drivers. Actions are the output of agent reasoning, not responses to function calls.                                                     |

## Quick Start

### Prerequisites

- Python 3.12 or later
- Node.js 20 or later (for the dashboard)
- Chromium browser (for v0.1 driver)

### Install

```bash
git clone https://github.com/artax-network/artax-network.git
cd artax-network
make install
```

### Run

```bash
make dev
```

This installs dependencies, sets up pre-commit hooks, and starts the runtime. The dashboard is available at `http://localhost:3000`.

## Architecture

Artax has a layered architecture: the runtime core communicates with drivers through events, never through direct imports. The dashboard connects over WebSocket.

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

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full architecture reference.

## Dashboard

Artax ships with a developer dashboard for real-time visibility into the runtime:

- Live event stream
- Working memory inspector
- Driver status and health
- Scheduler state

```bash
make dashboard          # start dashboard dev server
make dashboard-build    # build for production
```

## Configuration

Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

| Variable                  | Default                   | Description                                         |
|---------------------------|---------------------------|-----------------------------------------------------|
| `ARTAX_LOG_LEVEL`         | `info`                    | Logging level (`debug`, `info`, `warning`, `error`) |
| `ARTAX_RUNTIME_HOST`      | `0.0.0.0`                 | Runtime bind address                                |
| `ARTAX_RUNTIME_PORT`      | `8080`                    | Runtime HTTP port                                   |
| `ARTAX_DASHBOARD_PORT`    | `3000`                    | Dashboard dev server port                           |
| `ARTAX_WS_PORT`           | `8081`                    | WebSocket port for dashboard                        |
| `ARTAX_MEMORY_BACKEND`    | `memory`                  | Memory backend (`memory`, `sqlite`, `redis`)        |
| `ARTAX_SCHEDULER_BACKEND` | `memory`                  | Scheduler backend                                   |
| `ARTAX_CHROMIUM_PATH`     | `/usr/bin/chromium`       | Chromium binary path                                |
| `ARTAX_CHROMIUM_HEADLESS` | `true`                    | Run Chromium headless                               |
| `ARTAX_EVENT_LOG_DIR`     | `./logs/events`           | Event log directory                                 |
| `ARTAX_SECRET_KEY`        | `change-me-in-production` | Secret key for production                           |

## Development

```bash
make install      # install package in editable mode with dev deps
make dev          # install + pre-commit hooks
make test         # run test suite
make test-cov     # run tests with HTML coverage report
make lint         # ruff linter
make format       # ruff formatter
make typecheck    # mypy strict type checking
make check        # lint + typecheck + test
make clean        # remove build artifacts
```

See [docs/development.md](docs/development.md) for the full development guide.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request.

## License

MIT Licence. See [LICENCE](LICENSE) for details.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the project roadmap through v1.0.
