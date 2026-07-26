.PHONY: install install-all dev hooks test test-cov lint format typecheck check docs dashboard dashboard-install dashboard-build clean docker-up docker-down docker-build help

install:
	pip install -e ".[dev]"

install-all:
	pip install -e ".[dev,chromium,dashboard]"

dev: install hooks
	@echo "Ready"

hooks:
	pre-commit install
	pre-commit install --hook-type pre-push
	@echo "Git hooks installed (pre-commit + pre-push)"

hooks-update:
	pre-commit autoupdate
	@echo "Hooks updated"

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
	python -c "import shutil,glob; [shutil.rmtree(d,True) for d in glob.glob('__pycache__',recursive=True)]+glob.glob('.pytest_cache')+glob.glob('.mypy_cache')+glob.glob('.ruff_cache')+['dist','build']+glob.glob('*.egg-info')+['htmlcov','.coverage','coverage.xml']"
	@cd dashboard 2>/dev/null && rm -rf node_modules .next out 2>/dev/null || true
	@true

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker compose build

help:
	@printf "Available commands:\n  install, install-all, dev, hooks, hooks-update, test, test-cov, lint, format, typecheck, check, docs, dashboard, dashboard-install, dashboard-build, clean, docker-up, docker-down, docker-build\n"
