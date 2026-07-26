# =============================================================================
# Artax Network — Makefile
# =============================================================================
# Prefer native commands. Make targets are a convenience dashboard.
# Run `make help` for full command list.
# =============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash

# Resolve venv Python/pip relative to project root.
# Works on any platform where make + bash are available.
VENV     := .venv
VENV_PY  := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
VENV_BIN := $(VENV)/bin

# -----------------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------------

.PHONY: venv install install-all dev hooks hooks-update

venv: ## Create virtual environment in .venv/
	@if [ ! -d "$(VENV)" ]; then \
		echo "Creating virtual environment..."; \
		python3 -m venv "$(VENV)"; \
		"$(VENV_PIP)" install --upgrade pip setuptools; \
		echo "Virtual environment ready at $(VENV)/"; \
	else \
		echo "Virtual environment already exists at $(VENV)/"; \
	fi

install: venv ## Install package in editable mode with dev deps
	"$(VENV_PIP)" install -e ".[dev]"

install-all: venv ## Install with all optional deps (chromium, dashboard)
	"$(VENV_PIP)" install -e ".[dev,chromium,dashboard]"

dev: install hooks ## Full dev setup (venv + install + hooks)
	@echo "Ready — activate with: source $(VENV)/bin/activate"

hooks: ## Install git pre-commit + pre-push hooks
	"$(VENV_BIN)/pre-commit" install
	"$(VENV_BIN)/pre-commit" install --hook-type pre-push
	@echo "Git hooks installed (pre-commit + pre-push)"

hooks-update: ## Update pre-commit hooks to latest versions
	"$(VENV_BIN)/pre-commit" autoupdate
	@echo "Hooks updated"

# -----------------------------------------------------------------------------
# Quality
# -----------------------------------------------------------------------------

.PHONY: lint format typecheck check fix

lint: ## Run ruff linter (check only)
	"$(VENV_BIN)/ruff" check artax/ tests/

format: ## Format code with ruff (format + lint fix)
	"$(VENV_BIN)/ruff" format artax/ tests/
	"$(VENV_BIN)/ruff" check --fix artax/ tests/

typecheck: ## Run mypy type checker on artax/
	"$(VENV_BIN)/mypy" artax/

fix: format typecheck ## Auto-fix lint + format + typecheck

check: lint typecheck test ## Run all checks (lint + typecheck + test)

# -----------------------------------------------------------------------------
# Testing
# -----------------------------------------------------------------------------

.PHONY: test test-cov test-fast test-verbose

test: ## Run full test suite
	"$(VENV_BIN)/pytest"

test-cov: ## Run tests with HTML coverage report
	"$(VENV_BIN)/pytest" --cov-report=html
	@if command -v open >/dev/null 2>&1; then \
		open htmlcov/index.html; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open htmlcov/index.html; \
	fi

test-fast: ## Run tests, stop on first failure
	"$(VENV_BIN)/pytest" -x -q --tb=short --no-header

test-verbose: ## Run tests with verbose output
	"$(VENV_BIN)/pytest" -v --tb=long

# -----------------------------------------------------------------------------
# Dashboard
# -----------------------------------------------------------------------------

.PHONY: dashboard dashboard-install dashboard-build

dashboard: ## Start dashboard dev server
	cd dashboard && npm run dev

dashboard-install: ## Install dashboard npm deps
	cd dashboard && npm install

dashboard-build: ## Build dashboard for production
	cd dashboard && npm run build

# -----------------------------------------------------------------------------
# Docker
# -----------------------------------------------------------------------------

.PHONY: docker-up docker-down docker-build docker-logs

docker-up: ## Start services in background
	docker compose up -d

docker-down: ## Stop and remove services
	docker compose down

docker-build: ## Build docker images
	docker compose build

docker-logs: ## Tail service logs
	docker compose logs -f

# -----------------------------------------------------------------------------
# Cleanup
# -----------------------------------------------------------------------------

.PHONY: clean clean-all

clean: ## Remove build artifacts and caches
	"$(VENV_PY)" -c "import shutil,glob; [shutil.rmtree(d,True) for d in glob.glob('__pycache__',recursive=True)]+glob.glob('.pytest_cache')+glob.glob('.mypy_cache')+glob.glob('.ruff_cache')+['dist','build']+glob.glob('*.egg-info')+['htmlcov','.coverage','coverage.xml']"
	@cd dashboard 2>/dev/null && rm -rf node_modules .next out 2>/dev/null || true
	@true

clean-all: clean ## Remove everything including venv
	rm -rf "$(VENV)"

# -----------------------------------------------------------------------------
# Help
# -----------------------------------------------------------------------------

.PHONY: help

help: ## Show this help message
	@echo ""
	@echo "Artax Network — Available Commands"
	@echo "==================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		 awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Native commands (use directly):"
	@echo "    ruff check artax/ tests/"
	@echo "    ruff format artax/ tests/"
	@echo "    mypy artax/"
	@echo "    pytest"
	@echo "    pre-commit run --all-files"
	@echo ""
