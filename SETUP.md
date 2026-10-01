# Reproducible private daily-driver setup

The React frontend and Flask/Socket.IO backend are the private daily driver,
served on port `5001`.

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

`make build` runs `make react-assets`. The React bundle is generated under
`src/crossword/static/react/`. Generated asset directories are not source.

## Daily commands

```bash
make run            # build React; private React + Flask on port 5001
make legacy-run     # alias for make run
make legacy-test    # local Python + JavaScript suite; no provider calls
make build          # rebuild generated browser assets
make npm-audit      # write reports/npm-audit.json; does not fix or upgrade
make clean          # remove generated caches and browser assets
```

The live-provider tests are deliberately separate:

```bash
make legacy-test-live
```

That target sets `CROSSWORD_ALLOW_LIVE_PROVIDER=1` and selects only tests
marked `live_provider`. It is a private, manually initiated diagnostic and is
not part of CI or the default test suite.

## React daily driver

Run `make run` and open **http://127.0.0.1:5001/**. It builds React, then
starts `run.py` with the existing Flask/Socket.IO backend. React serves the
main page at `/` and mobile rooms at `/mobile/<room>/<role>`.

## Optional React development server (private, not publicly deployed)

For Vite development, run `npm run dev --workspace @crossword/react-port`
(port 5174) alongside Flask. It proxies the same local backend.

The private React app under `apps/react` retains the backend/provider behavior
for daily use. It is not a public deployment;
the scanner exemptions in `scripts/forbidden-content.json` cover this private
surface. The future public generator-backed frontend without provider
integration is not ready. The generator repository and vendored packages are
preserved. Do not apply or drop the existing stash without reviewing it.

