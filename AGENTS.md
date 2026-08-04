# AGENTS.md

# Artax Network

This file tells AI agents how to work in this repository.

Follow these rules before making any change.

---

# Mission

Artax Network is an event-driven runtime for embodied AI.

The goal is to build a runtime that lets AI live inside environments instead of calling them as tools.

The first environment is Chromium.

More environments will be added later.

---

# Think First

Before changing code:

* Understand the request.
* Read the related files.
* Understand the current design.
* Make a plan.
* Then make changes.

Never rush into writing code.

---

# Workflow Enforcement

The workflow below is mechanically enforced. No code changes are committed without completing each step.

## Required Plan File

Before implementing any non-trivial change, a plan file must exist at `.kilo/plan.md` with:

1. **What** is changing (file paths, what is modified/created)
2. **Why** it is changing (reference to PRD, task spec, or anomaly)
3. **How** it will be implemented (approach, not code)
4. **What could go wrong** (anomalies, edge cases, failure modes)

The plan must be read and acknowledged before implementation begins.

## Required Quality Gates

Every change must pass all of these before being considered done:

1. `make lint` — zero lint errors
2. `make typecheck` — zero type errors
3. `make test` — all tests pass, zero failures
4. Coverage for changed files must not decrease

## Required Test Quality

Tests must cover:

- Happy path behavior
- Anomaly paths (errors, timeouts, missing resources, invalid inputs)
- Edge cases (empty inputs, boundary values, concurrent access)
- State transitions (connecting → connected → disconnecting → disconnected)

Tests that only verify happy paths are insufficient. Tests that do not assert behavior are not tests.

## Pre-Commit Checklist

Before committing, verify:

- [ ] Plan file exists and was followed
- [ ] `make lint` passes
- [ ] `make typecheck` passes
- [ ] `make test` passes
- [ ] Coverage for changed files is not degraded
- [ ] No new warnings introduced

---

# Always Follow a Workflow

Do not skip steps.

Always work like this:

1. Understand the task.
2. Read the existing code.
3. Understand the architecture.
4. Make a short plan.
5. Make the smallest reasonable change.
6. Check your work.
7. Update documentation if needed.

Never jump directly to implementation.

---

# Runtime Rules

The Runtime must never know about Chromium.

The Runtime must never know about Playwright.

The Runtime must never know about browser APIs.

If browser code reaches the Runtime, stop and rethink the design.

---

# Driver Rules

Drivers connect Artax to the outside world.

Drivers translate.

Drivers do not think.

Drivers do not plan.

Drivers do not contain business logic.

---

# Working Memory Rules

Working Memory stores meaning.

Do not store unnecessary implementation details.

Prefer semantic information over raw data.

---

# Dashboard Rules

The Dashboard exists for humans.

The Dashboard watches the Runtime.

The Dashboard does not control the Runtime.

---

# Architecture Rules

Everything is an Environment.

Every Environment has a Driver.

The Runtime should work with any Driver.

Do not build special cases for Chromium.

Future Drivers should work without changing the Runtime.

---

# Before Writing Code

Always ask yourself:

Does this belong in the Runtime?

Does this belong in a Driver?

Can this become an interface?

Will this make adding a Terminal Driver harder?

If unsure, stop and rethink.

---

# Keep Things Small

Prefer small files.

Prefer small functions.

Prefer simple classes.

Avoid large modules.

Avoid unnecessary abstractions.

---

# Do Not Guess

If you do not know how something works:

Read the code.

Read the documentation.

Understand it first.

Never invent behaviour.

---

# Keep Changes Focused

One change should solve one problem.

Do not mix refactoring with new features.

Do not rewrite unrelated code.

---

# Documentation

Keep documentation updated.

If architecture changes, update the architecture docs.

If behaviour changes, update the README when needed.

Do not leave documentation behind.

---

# Testing

New behaviour should have tests.

Do not break existing tests.

If something cannot easily be tested, explain why.

---

# Quality Gates

Before committing, all checks must pass:

```bash
make check        # runs: lint + typecheck + test
```

Or individually:

```bash
make lint         # ruff check
make format       # ruff format + fix
make typecheck    # mypy --strict
make test         # pytest
```

Pre-commit hooks run automatically on `git commit`:

- ruff (lint + format)
- mypy (type check)
- yaml/toml/json validation
- trailing whitespace, end-of-file
- debug statement detection

Pre-push hook runs the full test suite.

Use `make` targets, not raw commands. This keeps behaviour consistent across platforms.

All tools run from `.venv/bin/` — never rely on system Python.

Run `make help` to see all available commands.

---

# Decision Order

When making decisions, follow this order:

1. Correctness
2. Architecture
3. Simplicity
4. Readability
5. Performance

Never sacrifice architecture for convenience.

---

# Definition of Done

A task is only finished when:

* The solution is correct.
* The architecture is still clean.
* Documentation is updated if needed.
* Tests pass.
* No unnecessary complexity was introduced.

---

# Workflows

## New Feature

Always follow this order:

Understand

↓

Plan

↓

Implement

↓

Test

↓

Document

---

## Refactoring

Understand

↓

Verify behaviour

↓

Refactor

↓

Run tests

↓

Update documentation

---

## Bug Fix

Reproduce

↓

Find the root cause

↓

Fix the cause

↓

Test

↓

Document if needed

Never patch symptoms without understanding the cause.

---

# Things to Avoid

Do not add shortcuts.

Do not introduce tight coupling.

Do not add browser logic to the Runtime.

Do not duplicate code.

Do not over-engineer.

Do not optimize early.

Do not leave TODOs without explanation.

---

# Long-Term Goal

Chromium is only the beginning.

One day Artax should support:

* Terminal
* Desktop
* VS Code
* Robotics
* Simulations
* Games

The Runtime should not need major changes to support them.

Every decision made today should make that future easier.

---

# Final Rule

Leave the repository in a better state than you found it and always commit your work.
