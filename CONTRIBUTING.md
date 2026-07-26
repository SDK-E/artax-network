# Contributing to Artax Network

Welcome. Artax Network is an event-driven runtime for embodied AI, and we are building it in the open. Your contributions — code, documentation, bug reports, architecture proposals — are how this project becomes real.

## Code of Conduct

This project follows the [Contributor Covenant v2.1](CODE_OF_CONDUCT.md). By participating, you agree to its terms. Report unacceptable behavior to conduct@artax-network.dev.

## How to Contribute

### Reporting Bugs

Open an issue on GitHub. Include:

- **What you expected** to happen.
- **What actually** happened.
- **Steps to reproduce** the issue.
- **Environment details** (OS, Python version, Artax version).

Bug reports with minimal reproductions get fixed faster.

### Suggesting Features

Open an issue with the `feature` label. Describe:

- **The problem** you are trying to solve.
- **Your proposed solution** at a high level.
- **Alternatives** you considered.

Feature requests that align with the project's vision and architecture are more likely to be accepted. Read [VISION.md](VISION.md) and [DESIGN.md](DESIGN.md) before proposing.

### Architecture Proposals

Major changes — new subsystems, protocol changes, architectural shifts — require an Architecture Decision Record (ADR). See [docs/development.md](docs/development.md) for the ADR template.

Open an issue with the `architecture` label. Describe the problem, the proposed change, trade-offs, and alternatives. Architecture proposals are discussed openly before implementation begins.

### Pull Requests

1. Fork the repository.
2. Create a branch from `main` (see Branch Naming below).
3. Make your changes.
4. Write or update tests.
5. Ensure all checks pass (`make check`).
6. Open a pull request.

## Development Setup

### Prerequisites

- Python 3.12 or later
- Node.js 20 or later
- Git

### Getting Started

```bash
git clone https://github.com/your-fork/artax-network.git
cd artax-network
make install       # install package in editable mode with dev deps
make dev           # install + set up pre-commit hooks
make check         # lint + typecheck + test
```

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`. They check:

- Ruff lint and formatting
- mypy type checking
- YAML/TOML syntax
- Trailing whitespace and end-of-file fixes
- Debug statements (bare `print`, `pdb`, etc.)

If a hook fails, fix the issue before committing. Do not skip hooks with `--no-verify`.

## Branch Naming

Use the following prefixes:

| Prefix | Use For |
|---|---|
| `feature/*` | New features |
| `fix/*` | Bug fixes |
| `docs/*` | Documentation changes |
| `release/*` | Release preparation |

Examples: `feature/terminal-driver`, `fix/memory-eviction`, `docs/architecture-update`, `release/v0.2.0`.

## Pull Request Process

### Requirements

1. **Link to an issue.** Every PR should address an open issue or be linked to a discussion.
2. **Describe the change.** Explain what changed, why it changed, and how it works.
3. **Add or update tests.** New features get new tests. Bug fixes get regression tests.
4. **All checks pass.** `make check` must succeed. CI must pass.
5. **Review required.** At least one maintainer must approve before merge.

### What We Review

- **Correctness.** Does the code do what it claims?
- **Tests.** Are there tests? Do they cover edge cases?
- **Types.** Is the code fully typed? Does mypy pass?
- **Style.** Does the code follow the project's conventions?
- **Architecture.** Does the change respect the dependency rules? Does it introduce circular imports?

### What We Do Not Review

- Style nits (Ruff handles this).
- Formatting (Ruff handles this).
- Argument over design philosophy (open an issue or ADR instead).

## Coding Standards

- **Line length:** 100 characters maximum.
- **Formatter:** Ruff format (compatible with Black).
- **Linter:** Ruff with `select = ["all"]`.
- **Type checker:** mypy strict mode.
- **Import order:** standard library, third-party, local (Ruff enforces this).
- **No `# type: ignore` without a comment explaining why.**
- **No bare `except:` clauses.** Catch specific exceptions.
- **No mutable default arguments.**
- **No global mutable state.**

See `pyproject.toml` for the complete linter and type checker configuration.

## Commit Messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/). Format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type | Use For |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Code style change (no logic change) |
| `refactor` | Code restructuring (no feature or fix) |
| `test` | Adding or updating tests |
| `chore` | Build, CI, tooling |

### Examples

```
feat(chromium): add navigation event handling
fix(memory): correct eviction priority ordering
docs: add architecture decision record for event bus
refactor(scheduler): extract priority queue into separate module
test(chromium): add test for DOM mutation events
chore(ci): add Python 3.14 to test matrix
```

## Architecture Decision Records

Major design decisions are documented as ADRs in `docs/adr/`. Each ADR follows this template:

```markdown
# ADR-NNN: Title

## Status

Proposed | Accepted | Deprecated | Superseded by ADR-XXX

## Context

What is the issue that motivates this decision?

## Decision

What did we decide?

## Consequences

What are the positive and negative outcomes?
```

Number ADRs sequentially. Do not reuse numbers. Do not edit ADRs after acceptance — create a new one that supersedes it.

## Getting Help

- Open an issue for bugs and feature requests.
- Start a discussion for architecture and design conversations.
- Read the documentation in `docs/` for detailed guides.

Thank you for contributing to Artax Network.
