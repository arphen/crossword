.DEFAULT_GOAL := help
.SHELL := /bin/sh

.PHONY: help check-uv check-node doctor install dev sync venv setup \
	test test-js test-live core-test legacy-test legacy-test-live build legacy-assets \
	mutation-test \
	legacy-run web-dev run legacy-smoke test-cov test-watch lint format clean \
	run-prod shell docker-build docker-run deps-update deps-list deps-tree \
	npm-audit check bootstrap all

BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m

SMOKE_HOST ?= 127.0.0.1
SMOKE_PORT ?= 5001

help: ## Show the reproducible developer commands
	@echo "$(BLUE)Crossword legacy continuity bridge$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:[^=].*## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-19s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)First-time setup: make bootstrap$(NC)"

check-uv: ## Check that uv is available
	@command -v uv >/dev/null 2>&1 || { \
		echo "$(RED)uv is required. Install it from https://docs.astral.sh/uv/getting-started/$(NC)"; \
		exit 1; \
	}

check-node: ## Check that the pinned Node/npm tools are available
	@command -v node >/dev/null 2>&1 || { \
		echo "$(RED)Node.js is required. Use a Node version manager with .node-version.$(NC)"; \
		exit 1; \
	}
	@command -v npm >/dev/null 2>&1 || { \
		echo "$(RED)npm is required. It is shipped with the pinned Node.js toolchain.$(NC)"; \
		exit 1; \
	}

doctor: check-uv check-node ## Verify pinned tool versions and the uv environment
	uv run python scripts/doctor.py

install: check-uv ## Install runtime Python dependencies from uv.lock
	uv sync --frozen

dev: check-uv ## Install Python dependencies, including the dev extra
	uv sync --all-extras --frozen

sync: dev ## Alias for the canonical all-extras uv sync

venv: check-uv ## Ensure the project uv environment exists
	@if [ -d .venv ]; then echo "$(YELLOW).venv already exists; uv sync owns it.$(NC)"; else uv venv --python "$$(sed -e 's/[[:space:]]*#.*//' .python-version | sed '/^[[:space:]]*$$/d' | head -n 1); fi

legacy-assets: check-node ## Generate ignored legacy browser assets from package-lock.json
	npm run build

setup: check-uv check-node ## Clean-clone setup using both pinned lockfiles
	uv sync --all-extras --frozen
	npm ci --ignore-scripts
	$(MAKE) legacy-assets
	$(MAKE) hooks-install
	@echo "$(GREEN)Setup complete. Run make doctor, make run, or make test.$(NC)"

.PHONY: hooks-install precommit
hooks-install: check-uv ## Install the tracked commit hook (never overwrite another manager)
	uv run --no-sync python scripts/install-hooks.py

precommit: check-uv check-node ## Check staged changes without committing or auto-fixing
	sh .githooks/pre-commit

build: legacy-assets ## Build reproducible legacy browser assets

test: check-uv check-node ## Run local Python and JavaScript tests without live provider calls
	uv run python -m pytest tests/ -m "not live_provider" -v
	npm test -- --runInBand
	npm --workspace @crossword/domain run test
	npm --workspace @crossword/persistence run test
	$(MAKE) core-test

core-test: check-node ## Run the new domain/application suites
	npm --workspace @crossword/application run test

mutation-test: check-node ## Mutation-test the deterministic construction core
	npm run test:mutation

test-js: check-node ## Run the JavaScript unit suite
	npm test -- --runInBand

test-live: check-uv ## Explicitly run private live-provider tests (opt-in only)
	CROSSWORD_ALLOW_LIVE_PROVIDER=1 uv run python -m pytest tests/ -m live_provider -v

legacy-test: test ## Named legacy test entrypoint used by the continuity gate

legacy-test-live: test-live ## Named opt-in live-provider test entrypoint

legacy-run: check-uv legacy-assets ## Run the Vue app on port 5001 (rebuild browser assets)
	uv run --no-sync python run.py

web-dev: run ## Alias for the Vue development server

run: legacy-run ## Run the Vue crossword app at http://127.0.0.1:5001

legacy-smoke: check-uv check-node legacy-assets ## Mount the legacy page on a local synthetic fixture
	@set -eu; \
	log_file=$$(mktemp "$${TMPDIR:-/tmp}/crossword-legacy-smoke.XXXXXX"); \
	uv run python scripts/legacy-smoke-server.py --host "$(SMOKE_HOST)" --port "$(SMOKE_PORT)" >"$$log_file" 2>&1 & \
	server_pid=$$!; \
	cleanup() { kill "$$server_pid" 2>/dev/null || true; rm -f "$$log_file"; }; \
	trap cleanup EXIT INT TERM; \
	ready=0; \
	for attempt in $$(seq 1 50); do \
		if node -e 'fetch(process.argv[1]).then((r) => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))' "http://$(SMOKE_HOST):$(SMOKE_PORT)/"; then ready=1; break; fi; \
		sleep 0.2; \
	done; \
	if [ "$$ready" -ne 1 ]; then cat "$$log_file"; echo "$(RED)Smoke server did not become ready.$(NC)"; exit 1; fi; \
	set +e; node scripts/legacy-browser-smoke.mjs "http://$(SMOKE_HOST):$(SMOKE_PORT)/"; smoke_status=$$?; set -e; \
	if [ "$$smoke_status" -eq 77 ]; then echo "$(YELLOW)Browser smoke skipped; set CHROME_BIN to a Chrome/Chromium executable.$(NC)"; \
	elif [ "$$smoke_status" -ne 0 ]; then cat "$$log_file"; exit "$$smoke_status"; fi

test-cov: check-uv ## Run Python coverage for the local test suite
	uv run python -m pytest tests/ -m "not live_provider" --cov=src --cov-report=term-missing --cov-report=html

test-watch: check-uv ## Run Python tests in watch mode when pytest-watch is installed
	uv run python -m pytest_watch tests/ -m "not live_provider"

lint: ## Placeholder for the legacy lint gate
	@echo "$(YELLOW)No legacy linter is configured yet; see the quality plan.$(NC)"

format: ## Placeholder for the legacy formatter gate
	@echo "$(YELLOW)No legacy formatter is configured yet; see the quality plan.$(NC)"

clean: ## Remove generated caches and legacy browser assets
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf .coverage htmlcov .uv_cache src/crossword/static/lib
	@echo "$(GREEN)Generated files cleaned; lockfiles and source are unchanged.$(NC)"

run-prod: check-uv ## Run the WSGI app on the continuity port (5001)
	uv run uvicorn src.crossword.app:app --host 0.0.0.0 --port 5001

shell: check-uv ## Open a Python shell inside the uv environment
	uv run python

docker-build: ## Build the reproducible legacy container
	docker build -t crossword-app .

docker-run: ## Run the legacy container on port 5001
	docker run -p 5001:5001 crossword-app

deps-update: check-uv ## Update Python lockfile intentionally
	uv lock --upgrade

deps-list: check-uv ## List Python dependencies in the uv environment
	uv pip list

deps-tree: check-uv ## Show the Python dependency tree
	uv pip tree

npm-audit: check-node ## Record npm audit JSON without applying upgrades
	@mkdir -p reports; set +e; npm audit --json > reports/npm-audit.json; status=$$?; set -e; \
	echo "npm audit report written to reports/npm-audit.json (status $$status)"; exit $$status

check: test lint ## Run local tests and legacy lint gate

bootstrap: ## Install uv if needed, then run the canonical setup
	@set -eu; \
	if command -v uv >/dev/null 2>&1; then echo "$(GREEN)uv is already installed.$(NC)"; \
	elif command -v brew >/dev/null 2>&1; then echo "$(BLUE)Installing uv with Homebrew...$(NC)"; brew install uv; \
	elif command -v curl >/dev/null 2>&1; then echo "$(BLUE)Installing uv with the official installer...$(NC)"; curl -LsSf https://astral.sh/uv/install.sh | sh; uv_path="$${HOME:-}/.local/bin"; PATH="$$uv_path:$$PATH"; export PATH; \
	else echo "$(RED)Install uv first: https://docs.astral.sh/uv/getting-started/$(NC)"; exit 1; fi; \
	command -v uv >/dev/null 2>&1 || { echo "$(RED)uv was installed but is not on PATH; open a new shell and rerun make bootstrap.$(NC)"; exit 1; }; \
	$(MAKE) setup

all: clean setup test ## Clean, install, and test the local baseline
