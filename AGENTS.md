# Repository Agent Guide

## Overview

Crossword is an online/offline crossword-solving application with a Flask/Socket.IO backend, a legacy Vue interface, and a React port. TypeScript packages separate domain logic, application use cases, and persistence; the legacy provider integration remains a private continuity bridge.

## Tech Stack & Versions

- Python 3.13 (`.python-version`); uv + Hatchling. Declared minimums: Flask 3.0, Pydantic 2.5.2, Flask-SQLAlchemy 3.0, Flask-SocketIO 5.5.1; SQLite storage. Exact resolutions live in `uv.lock`.
- Node 24.20.0 (`.node-version`), npm 11.19.0; npm workspaces and JavaScript/TypeScript 5.9.2.
- Legacy Vue 2.7.16; React/React DOM 19.1.1 and Vite 7.1.4 in `apps/react`; Axios 1.13.2, Socket.IO client 4.8.3.
- pytest (declared >=7.4.3), Jest 29.7.0, Vitest 3.2.4, Playwright 1.55.0; Ruff 0.13.2, ESLint 9.36.0, Prettier 3.6.2.

## Critical Entry Points

1. `run.py` — starts the Flask/Socket.IO server on port 5001.
2. `src/crossword/app.py` — app initialization, HTTP routes, and multiplayer socket handlers.
3. `src/crossword/static/main.js` — legacy desktop Vue interface; mobile counterpart is `mobile.js`.
4. `apps/react/src/main.jsx` — mounts the React desktop/mobile interface and controller.
5. `packages/application/src/index.ts` — application package's public use-case entry point.

## Repository Map

Read `docs/REPO_MAP.md` immediately after this file. It contains a bounded path/symbol index, not source bodies. Regenerate with `bash .scripts/generate-repo-map.sh` after adding, removing, or renaming modules; verify freshness with `bash .scripts/generate-repo-map.sh --check`. Requires only Bash and Python 3 (override the interpreter with `PYTHON`). Python symbols use the standard-library AST; JS/TS symbols use a lightweight heuristic, not a complete parser.

STARTUP PROTOCOL: Do NOT perform recursive directory listings (`ls -R`, `find .`) on launch. Read `AGENTS.md` and `docs/REPO_MAP.md` immediately for codebase structure. Locate relevant modules using exact symbol names via `grep` or `ast-grep` rather than browsing file trees.

Scope symbol searches to the mapped file/package (or use the harness's grep tool); never run an unbounded root search. Treat map line numbers as navigation hints and verify the source. If the map is missing or stale, regenerate it instead of dumping the repository. Architecture/migration guidance starts at `docs/plans/README.md`.

## Operational Commands

Run from the repository root. Prefer existing Make targets; use direct commands where Make has no real gate.

| Task | Command |
| --- | --- |
| Install and build | `make setup` (uv frozen all-extras sync, npm ci, legacy assets, commit hook installation) |
| Check tools | `make doctor` |
| Git hooks | `make hooks-install` |
| Local tests, no live provider | `make test` |
| Python targeted tests | `uv run --no-sync python -m pytest tests/test_NAME.py -m 'not live_provider'` |
| React port tests | `npm --workspace @crossword/react-port test` |
| Lint | `uv run --no-sync ruff check .` and `npm run lint` (`make lint` is only a placeholder) |
| Type / format checks | `npm run typecheck` / `npm run format:check` |
| Legacy development server | `make run` (port 5001; rebuilds legacy assets) |
| Legacy build | `make build` |
| React development / build | `npm --workspace @crossword/react-port run dev` / `npm --workspace @crossword/react-port run build` |
| Update / check map | `make map-update` / `make map-check` |

Do not run live-provider tests without explicit opt-in. Generator source belongs to the separate `../crossword-generator` checkout; normal builds consume versioned archives, not that sibling's sources. `make setup` installs the tracked `.githooks` path; its pre-commit hook regenerates and stages `docs/REPO_MAP.md`, and its pre-push hook verifies that the committed map is current.

## Strict Boundaries

NEVER search, index, or manually modify these directories (names apply at any depth unless a full path is shown):

- Dependencies/VCS: `.git/`, `node_modules/`, `vendor/`, `.venv/`, `venv/`, `env/`.
- Build output: `dist/`, `build/`, `target/`, `src/crossword/static/lib/`, `src/crossword/static/react/`.
- Caches/reports: `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.uv_cache/`, `.cache/`, `.npm-cache/`, `.tox/`, `.hypothesis/`, `.stryker-tmp/`, `coverage/`, `htmlcov/`, `reports/`, `playwright-report/`, `test-results/`, `.shots/`, `.browsers/`.
- Local/private state: `instance/`, `.idea/`, `.vscode/`, `.claude/`; do not read secrets such as `.env` or `.envrc`.

Approved install/build/test tools may manage their own dependency/output directories; do not inspect or hand-edit their contents. Never hand-vendor browser libraries: use `make legacy-assets`. Exclude lockfiles, minified bundles, sourcemaps, binary assets, and fixtures/snapshots from indexing; lockfiles may only be updated intentionally through their package manager. Do not edit `docs/REPO_MAP.md` by hand; change its generator. Preserve unrelated working-tree changes.

## User communication

- Acknowledge new user messages immediately, before continuing long-running work.
