.PHONY: install install-all dev test test-cov lint format typecheck check docs dashboard dashboard-install dashboard-build clean docker-up docker-down docker-build help

install:
	pip install -e ".[dev]"

install-all:
	pip install -e ".[dev,chromium,dashboard]"

dev: install
	pre-commit install
	@echo "Ready"

test:
	pytest

test-cov:
	pytest --cov-report=html
	@if command -v open >/dev/null 2>&1; then \
		open htmlcov/index.html; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open htmlcov/index.html; \
	fi

lint:
	ruff check artax/ tests/

format:
	ruff format artax/ tests/
	ruff check --fix artax/ tests/

typecheck:
	mypy artax/

check: lint typecheck test

docs:
	@echo "Documentation build command"

dashboard:
	cd dashboard && npm run dev

dashboard-install:
	cd dashboard && npm install

dashboard-build:
	cd dashboard && npm run build

clean:
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@rm -rf dist build *.egg-info .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	@cd dashboard && rm -rf node_modules .next out 2>/dev/null || true
	@true

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker compose build

help:
	@printf "Available commands:\n  install, install-all, dev, test, test-cov, lint, format, typecheck, check, docs, dashboard, dashboard-install, dashboard-build, clean, docker-up, docker-down, docker-build\n"
