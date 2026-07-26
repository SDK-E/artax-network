# Installation and Overview

## Prerequisites

- **Python 3.12** or later (3.12, 3.13, 3.14 supported)
- **Node.js 20** or later (for the dashboard)
- **Chromium browser** (for the v0.1 Chromium driver)
- **Git**

Verify your prerequisites:

```bash
python3 --version   # 3.12+
node --version      # 20+
chromium --version  # or google-chrome --version
git --version
```

## Installation from Source

```bash
git clone https://github.com/artax-network/artax-network.git
cd artax-network
make install
```

This installs the `artax-network` package in editable mode with development dependencies.

To install with all optional dependencies (Chromium driver, dashboard):

```bash
make install-all
```

## Installation from PyPI

```bash
pip install artax-network
```

To include the Chromium driver extras:

```bash
pip install "artax-network[chromium]"
```

## Configuration

Copy the example environment file and adjust for your setup:

```bash
cp .env.example .env
```

Key configuration variables:

| Variable | Default | Description |
|---|---|---|
| `ARTAX_LOG_LEVEL` | `info` | Logging verbosity: `debug`, `info`, `warning`, `error` |
| `ARTAX_RUNTIME_HOST` | `0.0.0.0` | Runtime bind address |
| `ARTAX_RUNTIME_PORT` | `8080` | Runtime HTTP port |
| `ARTAX_DASHBOARD_PORT` | `3000` | Dashboard dev server port |
| `ARTAX_WS_PORT` | `8081` | WebSocket port for dashboard communication |
| `ARTAX_MEMORY_BACKEND` | `memory` | Working memory backend: `memory`, `sqlite`, `redis` |
| `ARTAX_SCHEDULER_BACKEND` | `memory` | Scheduler persistence backend |
| `ARTAX_CHROMIUM_PATH` | `/usr/bin/chromium` | Path to Chromium binary |
| `ARTAX_CHROMIUM_HEADLESS` | `true` | Run Chromium without GUI |
| `ARTAX_EVENT_LOG_DIR` | `./logs/events` | Directory for event log files |
| `ARTAX_SECRET_KEY` | `change-me-in-production` | Secret key for production deployments |

## First Run

Start the runtime:

```bash
make dev
```

This installs dependencies, configures pre-commit hooks, and starts the runtime. On first run, the runtime initializes the event bus, working memory, scheduler, and connects available drivers.

You should see output indicating:

1. Runtime core started
2. Event bus initialized
3. Working memory ready (backend: memory)
4. Scheduler started
5. Chromium driver connected (if Chromium is available)

## Dashboard Access

The dashboard is available at `http://localhost:3000` when the runtime is running.

The dashboard provides:

- Real-time event stream visualization
- Working memory inspector
- Driver status and health monitoring
- Scheduler state

To start only the dashboard (without the runtime):

```bash
make dashboard
```

To build the dashboard for production:

```bash
make dashboard-install
make dashboard-build
```

## Docker

Artax can run in Docker for isolated environments:

```bash
make docker-build    # build images
make docker-up       # start services
make docker-down     # stop services
```

The `docker-compose.yml` defines a `artax-dev` bridge network. Additional services (Redis, Chromium) can be uncommented in the compose file.

## Verifying the Installation

Run the test suite to verify everything is working:

```bash
make test
```

Run the full check (lint + typecheck + tests):

```bash
make check
```

## Troubleshooting

### Python version errors

Artax requires Python 3.12 or later. If you have multiple Python versions, ensure you are using the correct one:

```bash
python3 --version
which python3
```

Use `pyenv` or `conda` to manage Python versions if needed.

### Chromium not found

If the Chromium driver cannot find the browser:

1. Verify Chromium is installed: `chromium --version`
2. Check the path in `.env`: `ARTAX_CHROMIUM_PATH`
3. Set `ARTAX_CHROMIUM_HEADLESS=true` for headless environments

### Pre-commit hooks failing

Install pre-commit and run manually:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

### Port conflicts

If ports 8080, 8081, or 3000 are in use, update the corresponding variables in `.env`:

```
ARTAX_RUNTIME_PORT=8090
ARTAX_WS_PORT=8091
ARTAX_DASHBOARD_PORT=3001
```

### Import errors

Ensure the package is installed in editable mode:

```bash
pip install -e ".[dev]"
```

### Memory backend issues

The default `memory` backend requires no external services. If using `redis`, ensure Redis is running:

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

If using `sqlite`, ensure the `ARTAX_EVENT_LOG_DIR` directory is writable.
