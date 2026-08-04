# Artax Network — AI Skills Index

## Overview

This directory contains specialized AI skills for the Artax Network project. Each skill is designed to help AI contributors behave like senior software architects while following the constitutional rules defined in `AGENTS.md`.

## Architecture Invariants

All skills reference and enforce the following invariants from `AGENTS.md`:

1. Runtime contains no browser-specific logic
2. Runtime contains no Playwright types
3. Runtime contains no Chromium APIs
4. Drivers translate only
5. Working Memory stores semantic state
6. Scheduler decides when cognition executes
7. Dashboard observes only
8. Runtime is asynchronous
9. Layers communicate through stable interfaces
10. Environment implementations remain replaceable

## Skill Categories

### Core Architecture Skills

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `runtime-architect` | Design and implement runtime subsystems | Modifying core runtime components |
| `driver-creator` | Create new environment drivers | Implementing new drivers (Terminal, Desktop, etc.) |
| `event-designer` | Design typed events for the event bus | Creating or modifying event types |
| `memory-designer` | Design working memory backends | Implementing memory storage solutions |
| `scheduler-designer` | Design scheduling policies | Implementing timing and priority logic |

### Implementation Skills

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `chromium-developer` | Implement Chromium Driver | Working on browser automation |
| `dashboard-architect` | Design observational dashboard | Building UI components |
| `testing-architect` | Design test strategies | Creating tests for subsystems |

### Process Skills

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `doc-writer` | Write technical documentation | Updating docs and guides |
| `prd-writer` | Write product requirements | Defining features and capabilities |
| `adr-writer` | Write architecture decisions | Documenting significant decisions |
| `code-reviewer` | Review code against architecture | Reviewing pull requests |
| `architecture-guardian` | **MANDATORY** - Review all implementations | Before any implementation begins |
| `refactoring-advisor` | Identify and execute refactoring | Improving code quality |
| `repo-maintainer` | Maintain repository health | CI/CD, dependencies, DX |
| `release-planner` | Plan releases and roadmap | Coordinating development cycles |

## Dependency Flow

```
AGENTS.md (constitutional truth)
    ↓
architecture-guardian (mandatory review)
    ↓
Core Architecture Skills (runtime-architect, driver-creator, etc.)
    ↓
Implementation Skills (chromium-developer, dashboard-architect, etc.)
    ↓
Process Skills (doc-writer, code-reviewer, etc.)
```

## Usage Guidelines

1. **Always start with `architecture-guardian`** before any implementation
2. **Reference `AGENTS.md`** in all architectural decisions
3. **Use Protocol-based interfaces** for all subsystem communication
4. **Maintain dependency direction** (core → runtime → drivers)
5. **Test subsystems independently** without requiring environments

## Skill Structure

Each skill follows this structure:

- **Purpose**: What the skill does
- **Responsibilities**: What the skill is accountable for
- **Constraints**: What the skill must not do (references AGENTS.md)
- **Inputs**: What the skill needs to operate
- **Outputs**: What the skill produces
- **Decision Process**: How the skill makes decisions
- **Best Practices**: What the skill should do
- **Anti-Patterns**: What the skill must avoid
- **Examples**: Concrete code examples
- **Related Skills**: Skills that work together
- **Invocation**: When to use the skill

## Success Criteria

The `.kilo` workspace is successful when:

- `AGENTS.md` remains the single source of architectural truth
- `.kilo` provides specialized expert capabilities layered on top
- Future AI contributors naturally follow Artax architecture
- Architectural violations are caught before implementation
- Code reviews consistently enforce architectural principles
