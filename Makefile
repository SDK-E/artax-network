# =============================================================================
# Artax Network — Makefile
# =============================================================================
# Prefer native commands. Make targets are a convenience dashboard.
# Run `make help` for full command list.
# =============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash

# -----------------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------------

.PHONY: install install-all dev hooks hooks-update

install: ## Install package in editable mode with dev deps
	pip install -e ".[dev]"

install-all: ## Install with all optional deps (chromium, dashboard)
	pip install -e ".[dev,chromium,dashboard]"

dev: install hooks ## Full dev setup (install + hooks)
	@echo "Ready"

hooks: ## Install git pre-commit + pre-push hooks
	pre-commit install
	pre-commit install --hook-type pre-push
	@echo "Git hooks installed (pre-commit + pre-push)"

hooks-update: ## Update pre-commit hooks to latest versions
	pre-commit autoupdate
	@echo "Hooks updated"

# -----------------------------------------------------------------------------
# Quality
# -----------------------------------------------------------------------------

.PHONY: lint format typecheck check fix

lint: ## Run ruff linter (check only)
	ruff check artax/ tests/

format: ## Format code with ruff (format + lint fix)
	ruff format artax/ tests/
	ruff check --fix artax/ tests/

typecheck: ## Run mypy type checker on artax/
	mypy artax/

fix: format typecheck ## Auto-fix lint + format + typecheck

check: lint typecheck test ## Run all checks (lint + typecheck + test)

# -----------------------------------------------------------------------------
# Testing
# -----------------------------------------------------------------------------

.PHONY: test test-cov test-fast test-verbose

test: ## Run full test suite
	pytest

test-cov: ## Run tests with HTML coverage report
	pytest --cov-report=html
	@if command -v open >/dev/null 2>&1; then \
		open htmlcov/index.html; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open htmlcov/index.html; \
	fi

test-fast: ## Run tests, stop on first failure
	pytest -x -q --tb=short --no-header

test-verbose: ## Run tests with verbose output
	pytest -v --tb=long

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
	python -c "import shutil,glob; [shutil.rmtree(d,True) for d in glob.glob('__pycache__',recursive=True)]+glob.glob('.pytest_cache')+glob.glob('.mypy_cache')+glob.glob('.ruff_cache')+['dist','build']+glob.glob('*.egg-info')+['htmlcov','.coverage','coverage.xml']"
	@cd dashboard 2>/dev/null && rm -rf node_modules .next out 2>/dev/null || true
	@true

clean-all: clean ## Remove everything including venv
	rm -rf .venv

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
