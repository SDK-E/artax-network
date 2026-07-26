# Artax Network — Implementation Tasks

Each subdirectory contains a task prompt for implementing one subsystem of the Artax Network runtime.

## Execution Order

Tasks MUST be executed in dependency order. Layers 1a/1b/1c can run in parallel after Layer 0 completes.

```
Layer 0 ─── 01-events
              │
    ┌─────────┼─────────┐
    │         │         │
Layer 1a   Layer 1b   Layer 1c
02-memory  03-sched   04-driver-api
    │         │         │
    └─────────┼─────────┘
              │
Layer 2 ─── 05-runtime
              │
Layer 3 ─── 06-chromium-driver
              │
Layer 4 ─── 07-dashboard
```

| # | Task | PRD | Layer | Depends On |
|---|------|-----|-------|------------|
| 01 | Event System | `../prd/prd-events.md` | 0 | — |
| 02 | Working Memory | `../prd/prd-memory.md` | 1a | 01 |
| 03 | Scheduler | `../prd/prd-scheduler.md` | 1b | 01 |
| 04 | Actions + Driver API | `../prd/prd-driver-api.md` | 1c | 01 |
| 05 | Runtime Core | `../prd/prd-runtime.md` | 2 | 01–04 |
| 06 | Chromium Driver | `../prd/prd-browser-driver.md` | 3 | 04 |
| 07 | Dashboard Server | `../prd/prd-dashboard.md` | 4 | 05 |

## How to Use

1. Open the `TASK.md` for the subsystem you want to implement
2. Copy the entire content as a prompt to a new OpenCode session
3. The session will read the PRD, reconcile interfaces, implement, and test
4. Verify quality gates before moving to the next layer

## Important

- Each task reconciles existing scaffolding with PRD decisions before implementing
- The existing `../../artax` stubs have DIFFERENT interfaces than the PRDs — PRDs are source of truth
- All code must pass `mypy --strict`, `ruff check`, and `pytest`
- No implementation logic in the runtime for driver-specific concerns
