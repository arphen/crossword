# Reproducible private daily-driver setup

The React frontend and Flask/Socket.IO backend are the private daily driver
during migration, served on port `5001`. Vue remains the fallback reference at
`/legacy/`; this is not the future public generator frontend.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/)
- a Node version manager that reads `.node-version` (Node `24.20.0`)

The repository pins npm as `npm@11.19.0` in `package.json`. If your Node
installation does not provide that npm version, use Corepack or your version
manager to activate the pinned package manager before running `make doctor`.

## First-time setup

The one-time bootstrap command installs uv when it is not already available,
then performs the same clean setup used by CI:

```bash
make bootstrap
make doctor
```

`make setup` is the non-bootstrap form when uv is already installed. It runs:

```bash
uv sync --all-extras --frozen
npm ci --ignore-scripts
make build
```

`make build` runs `make legacy-assets` and `make react-assets`. Shared Vue,
Axios and Socket.IO files under `src/crossword/static/lib/` are recreated from
`package-lock.json`; the React bundle is generated under
`src/crossword/static/react/`. Both asset directories are generated, not source.

## Daily commands

```bash
make run            # build both frontends; private React + Flask on port 5001
make legacy-run     # same server; open http://127.0.0.1:5001/legacy/
make legacy-test    # local Python + JavaScript suite; no provider calls
make legacy-smoke   # browser mount check using a synthetic local puzzle
make build          # rebuild generated browser assets
make npm-audit      # write reports/npm-audit.json; does not fix or upgrade
make clean          # remove generated caches and legacy/shared browser assets
```

The live-provider tests are deliberately separate:

```bash
make legacy-test-live
```

That target sets `CROSSWORD_ALLOW_LIVE_PROVIDER=1` and selects only tests
marked `live_provider`. It is a private, manually initiated diagnostic and is
not part of CI or the default test suite.

## React daily driver and Vue fallback

Run `make run` and open **http://127.0.0.1:5001/**. It builds the legacy/shared
Vue, Axios and Socket.IO assets plus React, then starts `run.py` with the
existing Flask/Socket.IO backend. React serves the main page at `/` and mobile
rooms at `/mobile/<room>/<role>`.

`make legacy-run` starts the same server; open **http://127.0.0.1:5001/legacy/**
for the Vue fallback/reference. Vue mobile rooms use
`/legacy/mobile/<room>/<role>`. API and Socket.IO endpoints remain on the
origin, not under `/legacy/`. `make web-dev` and `npm run web:dev` are aliases
for `make run`.

## Optional React development server (private, not publicly deployed)

For Vite development, run `npm run dev --workspace @crossword/react-port`
(port 5174) alongside Flask. It proxies the same local backend; set
`REACT_PARITY_URL=http://127.0.0.1:5174/` to compare it with Vue. By default,
the browser harnesses compare both Flask-served frontends on port 5001.

The private React app under `apps/react` retains the backend/provider behavior
for daily use, not just parity verification. It is not a public deployment;
the scanner exemptions in `scripts/forbidden-content.json` cover this private
surface. The future public generator-backed frontend without provider
integration is not ready. The generator repository and vendored packages are
preserved. Do not apply or drop the existing stash without reviewing it.

## Browser smoke prerequisites

`make legacy-smoke` starts `scripts/legacy-smoke-server.py`, which serves the
Vue page at `/legacy/` and a tiny provider-neutral puzzle entirely on localhost.
It then runs a headless Chrome/Chromium executable, checking that Vue has compiled the
template and no `[[ ... ]]` or Vue directive markers remain in the live DOM.

Set `CHROME_BIN` when the browser is not in a standard location. The target
prints a skip message on machines without a browser; CI can use a controlled
Chrome runner for this gate.
