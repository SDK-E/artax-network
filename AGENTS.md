# Artax Network — AGENTS.md

# Purpose

This document defines the permanent engineering constitution for Artax Network.

Every AI assistant contributing to this repository MUST read and follow this document before making any code changes.

This document has higher priority than implementation convenience.

If implementation and architecture conflict, architecture wins.

---

# Mission

Artax Network is an event-driven runtime for embodied intelligence.

Artax is **not**:

* an agent framework
* a browser automation framework
* an LLM wrapper
* a workflow orchestrator
* a Playwright abstraction

Artax is a runtime where intelligent processes inhabit persistent environments instead of interacting with them through synchronous tool calls.

---

# Core Vision

Everything is an Environment.

Every Environment is represented by a Driver.

The Runtime never knows which Driver is attached.

The Runtime only understands:

* Events
* Working Memory
* Scheduling
* Intent
* Actions

Nothing else.

---

# Architecture Invariants

These rules MUST NOT be violated.

1. Runtime contains no browser-specific logic.
2. Runtime contains no Playwright types.
3. Runtime contains no Chromium APIs.
4. Drivers translate only.
5. Working Memory stores semantic state.
6. Scheduler decides when cognition executes.
7. Dashboard observes only.
8. Runtime is asynchronous.
9. Layers communicate through stable interfaces.
10. Environment implementations remain replaceable.

---

# Dependency Rules

Dependencies always flow inward.

Drivers may depend on Runtime interfaces.

Runtime must never depend on Drivers.

Dashboard communicates only through public APIs.

No circular dependencies.

No hidden coupling.

---

# Runtime Responsibilities

Runtime owns:

* lifecycle
* event bus
* scheduler
* working memory
* action queue
* cognition interface

Runtime does NOT own:

* browser logic
* UI rendering
* network automation
* DOM parsing
* screenshots

---

# Driver Responsibilities

Drivers are translators.

A Driver converts an external system into Artax Events and converts Artax Actions into environment-specific operations.

Drivers contain no planning.

Drivers contain no reasoning.

Drivers contain no prompts.

Drivers should be replaceable without Runtime modifications.

---

# Working Memory

Working Memory represents semantic world state.

It should answer:

What exists?

What changed?

What is the current goal?

What deserves attention?

What is predicted to happen next?

Working Memory should avoid storing implementation details such as raw HTML unless there is a compelling architectural reason.

---

# Scheduler

The Scheduler behaves like an operating system interrupt scheduler.

Low-priority events update Working Memory silently.

High-priority events interrupt cognition.

Reasoning should never wake unnecessarily.

---

# Cognition

Reasoning operates over Working Memory.

Reasoning does not interact directly with Drivers.

Reasoning produces Intent rather than environment-specific commands.

---

# Dashboard

Dashboard exists for humans.

Dashboard must never block Runtime execution.

Dashboard is observational only.

Dashboard should visualize:

* live environment
* event timeline
* working memory
* runtime state
* attention
* logs

---

# Coding Principles

Prefer clarity over cleverness.

Prefer composition to inheritance.

Prefer interfaces to concrete implementations.

Prefer explicitness to magic.

Prefer immutable data where practical.

Prefer deterministic behavior.

Optimize for maintainability.

---

# File Size

Avoid large source files.

Split responsibilities early.

Functions should generally perform one logical task.

---

# Interfaces

Public interfaces should remain stable.

Breaking interface changes require architectural justification.

Design interfaces for future Drivers.

---

# Typing

Use strict typing.

Avoid Any unless unavoidable.

Document all public interfaces.

---

# Async

Runtime is async-first.

Avoid blocking operations.

Never block the event loop.

---

# Logging

Logs should explain system behavior.

Avoid noisy logs.

Avoid hiding errors.

Structured logging preferred.

---

# Error Handling

Errors should be recoverable whenever possible.

Fail clearly.

Never silently ignore failures.

---

# Testing

Every subsystem should be testable independently.

Unit tests should not require Chromium.

Drivers should be tested separately from Runtime.

Integration tests should verify boundaries.

---

# Documentation

Documentation is part of the implementation.

Update documentation whenever architecture changes.

README should remain accurate.

Architecture documents should remain synchronized.

---

# Performance

Optimize after measuring.

Do not prematurely optimize.

Maintain architectural clarity.

---

# Security

Validate external input.

Avoid unnecessary privileges.

Protect public interfaces.

Never embed secrets.

---

# Pull Requests

Prefer small focused changes.

Avoid mixing refactoring with new features.

Explain architectural decisions.

---

# Code Reviews

Review architecture before reviewing syntax.

Review boundaries before reviewing implementation.

Reject shortcuts that increase coupling.

---

# Decision-Making

When multiple solutions exist, choose the one that:

1. preserves architectural boundaries
2. improves readability
3. improves maintainability
4. reduces coupling
5. simplifies future Drivers

---

# Chromium Driver

Chromium is only the first Driver.

Its implementation must not influence Runtime architecture.

Future Drivers should require minimal Runtime changes.

---

# Long-Term Roadmap

Current:

Chromium Driver

Future:

Terminal Driver

Desktop Driver

VS Code Driver

Robotics Driver

Simulation Driver

Game Driver

The Runtime should remain fundamentally unchanged as these Drivers are introduced.

---

# AI Behaviour

Before implementing anything, ask:

Does this belong in Runtime?

Does this belong in a Driver?

Does this introduce coupling?

Can this become an interface instead?

Would a future Driver benefit?

If the answer is uncertain, prefer the more general abstraction.

---

# Definition of Success

Success is not measured by features.

Success is measured by whether a second environment can be added without changing the Runtime.
