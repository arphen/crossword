.DEFAULT_GOAL := help
.SHELL := /bin/sh

.PHONY: help check-uv check-node doctor runtime-doctor install dev sync venv setup \
	test test-js test-live core-test legacy-test legacy-test-live build react-assets \
	mutation-test \
	legacy-run web-dev run future-worker future-worker-once test-cov test-watch lint format clean \
	run-personal run-prod shell docker-build docker-run deps-update deps-list deps-tree \
	npm-audit hooks-install map-update map-check check bootstrap all

BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m

CROSSWORD_XFILL_ROOT ?= ../crossword-generator/vendor/xfill

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

runtime-doctor: check-uv check-node ## Read-only check for xfill, the runtime archive, and Ollama
	uv run --no-sync python scripts/runtime_doctor.py

install: check-uv ## Install runtime Python dependencies from uv.lock
	uv sync --frozen

dev: check-uv ## Install Python dependencies, including the dev extra
	uv sync --all-extras --frozen

sync: dev ## Alias for the canonical all-extras uv sync

venv: check-uv ## Ensure the project uv environment exists
	@if [ -d .venv ]; then echo "$(YELLOW).venv already exists; uv sync owns it.$(NC)"; else uv venv --python "$$(sed -e 's/[[:space:]]*#.*//' .python-version | sed '/^[[:space:]]*$$/d' | head -n 1); fi

react-assets: check-node ## Build the React frontend served by Flask
	npm run build --workspace @crossword/react-port

hooks-install: ## Install the tracked local Git hooks
	@git config core.hooksPath .githooks
	@chmod +x .githooks/pre-commit .githooks/pre-push
	@echo "Git hooks installed from .githooks."

map-update: ## Regenerate and stage the repository map
	bash .scripts/generate-repo-map.sh
	git add docs/REPO_MAP.md

map-check: ## Verify the generated repository map is current
	bash .scripts/generate-repo-map.sh --check

setup: check-uv check-node hooks-install ## Clean-clone setup using both pinned lockfiles
	uv sync --all-extras --frozen
	npm ci --ignore-scripts
	$(MAKE) build
	@echo "$(GREEN)Setup complete. Run make doctor, make run, or make test.$(NC)"

build: react-assets ## Build the React frontend

test: check-uv check-node ## Run local Python and JavaScript tests without live provider calls
	uv run python -m pytest tests/ -m "not live_provider" -v
	npm test -- --runInBand
	npm --workspace @crossword/domain run test
	npm --workspace @crossword/persistence run test
	npm --workspace @crossword/react-port run test
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

legacy-run: run ## Same server; React at http://127.0.0.1:5001/

web-dev: run ## Alias for the React/Flask development server

run: check-uv build ## Build React; run it and the local puzzle worker at http://127.0.0.1:5001/
	@set -eu; \
	worker_log="$${TMPDIR:-/tmp}/crossword-future-worker.$$$$.log"; \
	CROSSWORD_PRIVATE_CLUE_CHALLENGE="$${CROSSWORD_PRIVATE_CLUE_CHALLENGE:-1}" CROSSWORD_XFILL_ROOT="$(CROSSWORD_XFILL_ROOT)" uv run --no-sync python -c 'from src.crossword.app import app; assert app'; \
	CROSSWORD_PRIVATE_CLUE_CHALLENGE="$${CROSSWORD_PRIVATE_CLUE_CHALLENGE:-1}" CROSSWORD_XFILL_ROOT="$(CROSSWORD_XFILL_ROOT)" uv run --no-sync python -m src.crossword.future_worker --poll-seconds 1 >"$$worker_log" 2>&1 & \
	worker_pid=$$!; \
	cleanup() { kill "$$worker_pid" 2>/dev/null || true; wait "$$worker_pid" 2>/dev/null || true; }; \
	trap cleanup EXIT INT TERM; \
	sleep 0.5; \
	if ! kill -0 "$$worker_pid" 2>/dev/null; then cat "$$worker_log"; exit 1; fi; \
	CROSSWORD_PRIVATE_CLUE_CHALLENGE="$${CROSSWORD_PRIVATE_CLUE_CHALLENGE:-1}" CROSSWORD_REFLECTION_MODEL_CARDS="$${CROSSWORD_REFLECTION_MODEL_CARDS:-1}" CROSSWORD_XFILL_ROOT="$(CROSSWORD_XFILL_ROOT)" uv run --no-sync python run.py

run-personal: check-uv check-node build runtime-doctor ## Check the local personal runtime, then start Flask and its durable worker
	@set -eu; \
	worker_log="$${TMPDIR:-/tmp}/crossword-future-worker.$$$$.log"; \
	CROSSWORD_PRIVATE_CLUE_CHALLENGE="$${CROSSWORD_PRIVATE_CLUE_CHALLENGE:-1}" CROSSWORD_XFILL_ROOT="$(CROSSWORD_XFILL_ROOT)" uv run --no-sync python -c 'from src.crossword.app import app; assert app'; \
	CROSSWORD_PRIVATE_CLUE_CHALLENGE="$${CROSSWORD_PRIVATE_CLUE_CHALLENGE:-1}" CROSSWORD_XFILL_ROOT="$(CROSSWORD_XFILL_ROOT)" uv run --no-sync python -m src.crossword.future_worker --poll-seconds 1 >"$$worker_log" 2>&1 & \
	worker_pid=$$!; \
	cleanup() { kill "$$worker_pid" 2>/dev/null || true; wait "$$worker_pid" 2>/dev/null || true; rm -f "$$worker_log"; }; \
	trap cleanup EXIT INT TERM; \
	sleep 0.5; \
	if ! kill -0 "$$worker_pid" 2>/dev/null; then cat "$$worker_log"; exit 1; fi; \
	echo "Personal runtime ready at http://127.0.0.1:5001/future/ (Ctrl-C to stop)."; \
	CROSSWORD_PRIVATE_CLUE_CHALLENGE="$${CROSSWORD_PRIVATE_CLUE_CHALLENGE:-1}" CROSSWORD_REFLECTION_MODEL_CARDS="$${CROSSWORD_REFLECTION_MODEL_CARDS:-1}" CROSSWORD_XFILL_ROOT="$(CROSSWORD_XFILL_ROOT)" uv run --no-sync python run.py

future-worker: check-uv check-node ## Process durable /future answer-grid draft jobs
	CROSSWORD_XFILL_ROOT="$(CROSSWORD_XFILL_ROOT)" uv run --no-sync python -m src.crossword.future_worker

future-worker-once: check-uv check-node ## Process one queued /future answer-grid draft job
	CROSSWORD_XFILL_ROOT="$(CROSSWORD_XFILL_ROOT)" uv run --no-sync python -m src.crossword.future_worker --once

test-cov: check-uv ## Run Python coverage for the local test suite
	uv run python -m pytest tests/ -m "not live_provider" --cov=src --cov-report=term-missing --cov-report=html

test-watch: check-uv ## Run Python tests in watch mode when pytest-watch is installed
	uv run python -m pytest_watch tests/ -m "not live_provider"

lint: ## Placeholder for the legacy lint gate
	@echo "$(YELLOW)No legacy linter is configured yet; see the quality plan.$(NC)"

format: ## Placeholder for the legacy formatter gate
	@echo "$(YELLOW)No legacy formatter is configured yet; see the quality plan.$(NC)"

clean: ## Remove generated caches and browser assets
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf .coverage htmlcov .uv_cache src/crossword/static/lib src/crossword/static/react
	@echo "$(GREEN)Generated files cleaned; lockfiles and source are unchanged.$(NC)"

run-prod: check-uv ## Serve the built app with a production WSGI server (CROSSWORD_PORT, default 5001)
	uv run --no-sync gunicorn -w 1 --threads 4 --bind "0.0.0.0:$${CROSSWORD_PORT:-5001}" src.crossword.app:app

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
