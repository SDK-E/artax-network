# Development Guide

## Setting Up the Development Environment

### Prerequisites

- Python 3.12+
- Node.js 20+ (for dashboard development)
- Git

### Clone and Install

```bash
git clone https://github.com/artax-network/artax-network.git
cd artax-network
make install       # editable install with dev dependencies
make dev           # install + pre-commit hooks
```

### Verify

```bash
make check    # lint + typecheck + test
```

All three must pass before you start working.

## Project Structure

```
artax/
├── __init__.py              # Package version
├── core/                    # Protocol definitions, event types, data models
│   ├── __init__.py
│   ├── events.py            # Event type definitions
│   ├── protocols.py         # Driver, Memory, Scheduler protocols
│   └── models.py            # Shared data models (Action, Intent, etc.)
├── runtime/                 # Runtime core
│   ├── __init__.py          # CLI entry point
│   ├── loop.py              # Core event loop
│   ├── bus.py               # Event bus implementation
│   ├── memory/              # Working memory subsystem
│   │   ├── __init__.py
│   │   ├── base.py          # Memory Protocol
│   │   ├── memory.py        # In-memory backend
│   │   ├── sqlite.py        # SQLite backend
│   │   └── redis.py         # Redis backend
│   └── scheduler/           # Scheduler subsystem
│       ├── __init__.py
│       ├── base.py          # Scheduler Protocol
│       └── scheduler.py     # Default scheduler
├── drivers/                 # Environment drivers
│   └── chromium/            # Chromium driver (v0.1)
│       ├── __init__.py
│       └── driver.py
tests/
├── unit/                    # Unit tests (fast, no I/O)
├── integration/             # Integration tests (may use drivers)
└── e2e/                     # End-to-end tests (full runtime cycle)
docs/                        # Documentation
dashboard/                   # Next.js dashboard application
examples/                    # Usage examples
```

### Package Responsibilities

| Package | Responsibility | Dependencies |
|---|---|---|
| `artax/core/` | Protocols, events, models | None (dependency root) |
| `artax/runtime/` | Event loop, bus, memory, scheduler | `artax/core/` |
| `artax/drivers/` | Environment bridges | `artax/core/` (never `artax/runtime/`) |

### Dependency Direction

```
artax/core/     ← artax/runtime/
artax/core/     ← artax/drivers/*
artax/core/     ← tests/*
```

Dependencies flow inward toward `core/`. No package imports from a sibling or parent package. No circular dependencies.

## Running Tests

```bash
make test              # run all tests
make test-cov          # run with HTML coverage report
pytest tests/unit/     # unit tests only
pytest tests/integration/  # integration tests only
pytest tests/e2e/      # end-to-end tests only
```

### Test Configuration

- Framework: `pytest` with `pytest-asyncio`
- Async mode: `auto` (all async tests run without explicit markers)
- Coverage: `pytest-cov` with source in `artax/`
- Coverage report: terminal + HTML

### Writing Tests

**Unit tests** go in `tests/unit/`. They test individual components in isolation. No I/O, no network, no drivers. Mock external dependencies.

```python
# tests/unit/test_memory.py
from artax.core.events import SemanticEvent


async def test_memory_store():
    memory = InMemoryBackend(capacity=100)
    event = SemanticEvent(topic="test.event", data={"key": "value"})
    await memory.store(event)
    assert len(memory) == 1
```

**Integration tests** go in `tests/integration/`. They test subsystems working together. May use in-process drivers.

```python
# tests/integration/test_event_bus.py
async def test_bus_delivery():
    bus = EventBus()
    received = []
    bus.subscribe("test.topic", lambda e: received.append(e))
    await bus.publish(SemanticEvent(topic="test.topic", data={}))
    assert len(received) == 1
```

**End-to-end tests** go in `tests/e2e/`. They run the full runtime cycle. May use real drivers (Chromium in headless mode).

```python
# tests/e2e/test_runtime_cycle.py
async def test_full_cycle():
    runtime = Runtime()
    await runtime.start()
    # ... trigger events, verify actions ...
    await runtime.stop()
```

### Test Conventions

- Test files: `test_<module>.py`
- Test functions: `test_<behavior>()`
- Async tests: just make them `async def` — `pytest-asyncio` auto mode handles the rest.
- Fixtures: use `@pytest.fixture` for shared setup. Keep fixtures scoped narrowly.
- Assertions: use plain `assert`. No `self.assertEqual` — this is not unittest.

## Running Linters

```bash
make lint       # ruff check
make format     # ruff format + ruff check --fix
make typecheck  # mypy --strict
make check      # all three
```

### Linter Configuration

Ruff is configured in `pyproject.toml`:

- Line length: 100
- Target: Python 3.12
- Rules: `select = ["all"]` with specific ignores
- Per-file ignores for tests (allow `assert`, relax annotations)

mypy is configured in strict mode:

- `python_version = "3.12"`
- `strict = true`
- `warn_return_any = true`

### Fixing Lint Errors

```bash
make format     # auto-fix formatting
make lint       # see remaining errors
```

Most formatting issues are auto-fixed. Logic errors require manual fixes.

## Code Style

### General Rules

- 100-character line limit.
- Use Ruff format (Black-compatible).
- Full type annotations on all functions.
- No `# type: ignore` without a comment explaining why.
- No bare `except:` — catch specific exceptions.
- No mutable default arguments.
- No global mutable state.

### Naming

- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`
- Events: `PascalCase` (e.g., `ButtonClicked`, `TerminalOutput`)

### Imports

Order (enforced by Ruff):

1. Standard library
2. Third-party packages
3. Local imports

```python
from __future__ import annotations

import asyncio
from typing import Protocol

from artax.core.events import SemanticEvent
from artax.core.protocols import DriverProtocol
```

### Docstrings

Use Google-style docstrings for public APIs:

```python
async def store(self, event: SemanticEvent) -> None:
    """Store an event in working memory.

    Args:
        event: The event to store.

    Raises:
        MemoryFullError: If memory is at capacity and eviction fails.
    """
```

Private methods and internal functions do not require docstrings unless the behavior is non-obvious.

## Architecture for Contributors

### The Core Invariant

The runtime must never know which drivers are attached. If you find yourself importing a driver in the runtime, stop. The driver communicates through events. The runtime reacts to events. That is the only interface.

### Adding a New Event Type

1. Define the event class in `artax/core/events.py`.
2. Add it to the event type registry.
3. Publish it from the appropriate driver or subsystem.
4. Subscribe to it where needed.
5. Write tests for the new event.

### Adding a New Memory Backend

1. Create a new file in `artax/runtime/memory/`.
2. Implement the `MemoryBackend` Protocol from `artax/core/protocols.py`.
3. Register the backend in the memory factory.
4. Add configuration option in `.env.example`.
5. Write tests.

### Adding a New Driver

1. Create a new package in `artax/drivers/<name>/`.
2. Implement the `Driver` Protocol from `artax/core/protocols.py`.
3. Register the driver with the runtime.
4. Define event types for the driver's observations.
5. Define action types for the driver's operations.
6. Write unit, integration, and e2e tests.

## Debugging

### Logging

Artax uses Python's `logging` module. Set `ARTAX_LOG_LEVEL=debug` for verbose output.

```bash
ARTAX_LOG_LEVEL=debug make dev
```

### Event Logging

Events are logged to `ARTAX_EVENT_LOG_DIR` (default: `./logs/events/`). Each event is a JSON line. Use these logs for debugging event flow issues.

### Dashboard

The dashboard shows real-time event flow. Open `http://localhost:3000` while the runtime is running to see events as they happen.

### Breakpoints

Since the runtime is async, use `asyncio`-compatible debugging:

```python
import debugpy

debugpy.listen(5678)
debugpy.wait_for_client()
```

Or use `pdb` with `asyncio`:

```python
import pdb

pdb.set_trace()  # noqa: E702
```

Note: breakpoints in async code may require special handling depending on your editor.

## Performance Testing

Artax does not yet have a dedicated performance test suite. When adding performance-sensitive code:

1. Profile before optimizing. Use `cProfile` or `py-spy`.
2. Benchmark critical paths. Use `timeit` or `pytest-benchmark`.
3. Document performance characteristics in the code or ADR.
4. Avoid premature optimization. Correctness first, performance second.
