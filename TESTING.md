# Testing Guide

This repository runs a staged CI pipeline (`.github/workflows/ci.yml`). Every stage
must pass before the next one starts (`needs:`), so cheap checks fail fast before
expensive ones run.

## Stages

| Stage | Job(s) | What runs | Gate |
| --- | --- | --- | --- |
| 1 | `static` | `tsc --noEmit` (TS packages + React checkJs), ESLint, Prettier, Ruff, `compileall` | All later stages |
| 2 | `frontend-tests`, `backend-tests` (parallel) | Vitest + coverage; pytest with `pytest-cov` (unit + isolated API) | Stage 3 |
| 3 | `e2e` | Playwright against real backend + built React preview | Stage 4 |
| 4 | `mutation` | Stryker mutation testing on the domain core | — |

Stage 4 runs only on pushes to `main`/`develop` and on the nightly cron
(`schedule`), never on pull requests, so PR feedback stays fast.

## What each stage does

### Stage 1 — Static analysis (fast gate)

- `npm run typecheck` — strict `tsc --noEmit` for `packages/*` and a checkJs
  pass over the React app (see Known debt below).
- `npm run lint` — ESLint 9 flat config with `--max-warnings 0`.
- `npm run format:check` — Prettier over an explicit allowlist
  (`.prettierignore` documents what is excluded and why).
- `uv run --no-sync ruff check .` — backend correctness lint (legacy style
  cleanup is intentionally out of scope).
- `uv run --no-sync python -m compileall -q src scripts tests` — catches syntax
  errors in files pytest never imports.

### Stage 2 — Unit & component tests

- Frontend: `npm run test:coverage` runs Vitest over `apps/react` and
  `packages/*` with v8 coverage (`coverage/frontend/`, thresholds enforced).
- Backend: pytest with `--cov=src --cov-branch`, JUnit + HTML + XML reports in
  `coverage/backend/`. Live-provider tests are skipped; `tests/test_api_isolated.py`
  exercises the real Flask/SQLAlchemy stack against a disposable SQLite file with
  all outbound sockets monkeypatched off.
- Both jobs upload their reports as workflow artifacts.

### Stage 3 — E2E (Playwright)

- `scripts/ci-server.py` boots the real Flask/Socket.IO app on
  `127.0.0.1:5002` with a disposable SQLite database (env
  `CROSSWORD_DATABASE_URI`), original synthetic puzzles, and outbound network
  blocked (`requests` + `socket.connect` raise). `/api/health` verifies the
  database actually answers before tests start.
- `vite preview` serves the *built* React app on `127.0.0.1:4173` and proxies
  `/api`, `/static`, puzzle and socket routes to the backend — one origin, real
  HTTP.
- `playwright.config.ts` starts both via `webServer`, waits for the health
  endpoint and the preview URL, then runs `tests/e2e`.
- The fixture in `tests/e2e/fixtures.ts` aborts any request outside the local
  origin and fails the test if the page throws, so the suite cannot silently
  depend on third-party hosts.
- On failure, CI uploads `playwright-report/` (HTML report) and
  `test-results/e2e/` (traces, screenshots, browser logs).

No external database is needed: the backend uses file-backed SQLite. On GitHub
runners the E2E backend listens on 5002 (free there).

### Stage 4 — Mutation testing

- `npm run test:mutation` runs Stryker with the Vitest runner over
  `packages/domain/src/{puzzle,session}.ts` (`stryker.config.mjs`).
- HTML + JSON reports land in `reports/mutation/`; CI uploads them.
- Thresholds: break at 60% mutation score.

## Running locally

Prereqs: Node 24 (`.node-version`), npm 11.19 (`packageManager`), uv with
Python 3.13 (`.python-version`).

```bash
make setup                 # uv sync + npm ci + legacy assets
npx playwright install chromium   # once, for E2E

# Full pipeline, same commands as CI:
npm run ci                 # typecheck → lint → format → coverage → e2e → mutation

# Or per stage:
npm run typecheck
npm run lint
npm run format:check
npm run test:coverage                       # frontend coverage
uv run --no-sync python -m pytest tests/ -m "not live_provider" --cov=src   # backend
CROSSWORD_E2E_BACKEND_PORT=15002 npx playwright test    # E2E (see port note)
npm run test:mutation                       # mutation (minutes)

uv run --no-sync ruff check .               # backend lint
uv run --no-sync python -m pytest tests/test_api_isolated.py -v  # isolated API
```

Note: existing Jest suites (`npm test`), workspace Vitest suites
(`npm --workspace @crossword/domain run test`, etc.) and `make test` keep
working; `test:coverage` is the aggregated Vitest coverage entry point.

## Debugging CI failures

Artifacts appear on the workflow run page under "Artifacts"
(`gh run view <id> --repo arphen/crossword --log-failed` shows the log):

| Artifact | When | How to use |
| --- | --- | --- |
| `frontend-coverage` | always | `coverage/frontend/index.html` shows uncovered code |
| `backend-coverage` | always | `junit.xml` per-test results; `html/index.html` for misses |
| `playwright-failure-diagnostics` | on E2E failure | Open `playwright-report/index.html` (`npx playwright show-report playwright-report`); a failing test's folder in `test-results/e2e/` has `trace.zip` (`npx playwright show-trace trace.zip`), `browser.log`, and screenshots |
| `mutation-report` | nightly/main runs | `reports/mutation/index.html` lists survived/killed mutants |

Retention: 14 days (30 for mutation reports).

## Known debt (documented, not hidden)

- The React pass typechecks production JS/JSX with `strict` but without
  `noImplicitAny`/`strictNullChecks`; the dynamic legacy controller and the
  mechanically snapshotted `behavior/*.js` are consumed through explicit
  `.d.ts` boundaries instead of full typechecking.
- `format:check` covers the new configs only; legacy sources are excluded in
  `.prettierignore` until a formatting pass is scheduled.
- The legacy `scripts/*browser*.mjs` harnesses and vendored tarball packages
  are lint-exempt for the same reason; correctness rules still apply to all
  other sources.
- Socket.IO's dev proxy can log EPIPE noise during browser teardown in E2E;
  tests still pass and no page errors are recorded.
- `apps/web` referenced in the old lockfile was stale; it is no longer a
  workspace and the lockfile no longer lists it.
