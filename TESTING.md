# Testing Guide

This repository runs a staged CI pipeline (`.github/workflows/ci.yml`). Every stage
must pass before the next one starts (`needs:`), so cheap checks fail fast before
expensive ones run.

## Stages

| Stage | Job(s)                                       | What runs                                                                          | Gate             |
| ----- | -------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------- |
| 1     | `static`                                     | `tsc --noEmit` (TS packages + React checkJs), ESLint, Prettier, Ruff, `compileall` | All later stages |
| 2     | `frontend-tests`, `backend-tests` (parallel) | Vitest + coverage; pytest with `pytest-cov` (unit + isolated API)                  | Stage 3          |
| 3     | `e2e`                                        | Playwright against real backend + built React preview                              | Stage 4          |
| 4     | `mutation`                                   | Stryker mutation testing on the domain core                                        | —                |

Stage 4 runs on **relevant pull requests into `master`** and **manual CI runs**.
There are no nightly mutation runs and no mutation runs just because a PR merges.
Normal CI still runs on pushes to `master` as a post-merge check.

### Everyday process

1. Work on a feature branch and open a PR into `master` (no direct push needed).
2. Static checks, unit/component tests, and E2E run on every PR.
3. Mutation tests also run if the PR changes `packages/domain/**` (including tests),
   `vendor/generator/**`, root `package.json`/`package-lock.json`, `.npmrc`,
   `.node-version`, `stryker.config.*`, `vitest.mutation.config.*`, or this CI workflow.
   The filter checks the whole PR, including deleted/renamed files, on every update.
4. Unrelated PRs skip mutation testing. Merge when **CI quality gate** is green.

The final `CI quality gate` succeeds only when all normal checks pass and mutation
passes when required. It accepts an intentional mutation skip for unrelated changes,
not a skip caused by an earlier failure.

**One-time repository setting:** In Settings → Rules → Rulesets (or Branches →
Branch protection), protect `master`, require pull requests, and require the status
check **CI quality gate**. Workflow YAML reports checks; it does not itself prevent
merging a failed PR. This setting must be enabled separately by a maintainer.

### Run mutation tests manually

In GitHub, open **Actions → CI → Run workflow**, choose the branch, and click
**Run workflow**. A manual run always includes mutation after the normal gates pass.
The button becomes available once this `workflow_dispatch` definition is on the
repository's default branch (`master`). With GitHub CLI:

```bash
gh workflow run ci.yml --ref YOUR_BRANCH
```

For just mutation locally, use `npm run test:mutation`.

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
- `vite preview` serves the _built_ React app on `127.0.0.1:4173` and proxies
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
- Current baseline: fail below 55% mutation score (measured approximately 60%).
  Improve surviving mutations with useful assertions; do not lower the threshold
  just to make a failing PR green.

## Commit-time checks (pre-commit)

Every commit runs strict, fast checks on the **staged** content. Install with
`make setup` (or once per clone: `make hooks-install`). Check without committing:

```bash
make precommit
```

What the hook runs, in order (fail fast, first failure wins):

1. **Staged repository policy** — `scripts/commit_policy.py` on the staged
   snapshot. Blocks newly added test skips (`.skip`, `pytest.mark.skip`, `xit`, …),
   new suppressions (`eslint-disable`, `ts-ignore`, `# noqa`, `type: ignore`, …),
   conflict markers, private keys/known token formats (findings are redacted),
   generated outputs (`coverage/`, `reports/`, built `static/`, DB files), and
   changed blobs over 1 MiB. Deletions and pre-existing debt are allowed; only
   *added* lines are judged.
2. **Format changed files** — Prettier (JS/TS/JSON/YAML) and scoped `ruff format`
   on the exact files you touched. Check-only; nothing is auto-written. Scoped
   adoption: legacy mirrored sources (`src/crossword/static/*.js`,
   `apps/react/src/behavior/*.js`) and legacy `tools/`/`tests` are exempt.
3. **Full typecheck and lint** — same `typecheck`/`lint`/`format:check`/`ruff`
   commands as CI.
4. **Fast offline tests** — pytest (non-live), Jest, and the Vitest suites.
   E2E and mutation testing stay in CI.

The same policy runs in CI against the whole PR diff
(`--base <merge-base>`), so a bypassed hook (`--no-verify`, `SKIP`, a different
`core.hooksPath`) still fails the PR.

### When your commit is blocked

Fix the **cause the first failure names** — the message includes the file, line,
and reason (for example, `- 'f.py':2: new suppression directive`). Then:

1. Fix the code/test/config; do not delete assertions or add suppressions to pass.
2. `git add` the fix and rerun `make precommit`.
3. Formatting only: `node_modules/.bin/prettier --ignore-path /dev/null --write <file>`
   or `uv run --no-sync ruff format <file>`, inspect the diff, stage it.
4. Tooling or environment problem (missing uv, wrong Node): `make setup` after
   activating the pinned toolchain, then retry.

Do **not** use `--no-verify`, `SKIP=`, or another `core.hooksPath`. Do not weaken
thresholds, disable checks, or edit the policy to make a change pass: enforcement
changes (including `.pre-commit-config.yaml`, `scripts/commit_policy.py`, and lint
exceptions) require explicit human review in the PR — the guard prints an advisory
when you touch them, and a human must accept that change on purpose.

These checks are heuristic hygiene, not a security boundary: obfuscated secrets
or alias tricks can evade them. Human PR review and the CI mirror are the real
backstop.

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

| Artifact                         | When                         | How to use                                                                                                                                                                                                                   |
| -------------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend-coverage`              | always                       | `coverage/frontend/index.html` shows uncovered code                                                                                                                                                                          |
| `backend-coverage`               | always                       | `junit.xml` per-test results; `html/index.html` for misses                                                                                                                                                                   |
| `playwright-failure-diagnostics` | on E2E failure               | Open `playwright-report/index.html` (`npx playwright show-report playwright-report`); a failing test's folder in `test-results/e2e/` has `trace.zip` (`npx playwright show-trace trace.zip`), `browser.log`, and screenshots |
| `mutation-report`                | relevant PRs and manual runs | `reports/mutation/index.html` lists survived/killed mutants                                                                                                                                                                  |

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
