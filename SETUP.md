# Reproducible legacy setup

The Flask application is a private continuity bridge during migration. Its
documented local port is `5001`.

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
make legacy-assets
```

The generated files under `src/crossword/static/lib/` are ignored by git and
can always be recreated from `package-lock.json`.

## Daily commands

```bash
make legacy-run     # private Flask/Socket.IO bridge on port 5001
make legacy-test    # local Python + JavaScript suite; no provider calls
make legacy-smoke   # browser mount check using a synthetic local puzzle
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

## Vue frontend

Run `make run` and open **http://127.0.0.1:5001**. It rebuilds the Vue,
Axios and Socket.IO assets before starting Flask. `make web-dev` and
`npm run web:dev` are aliases for the same Vue server.

## React parity port (private, not deployed)

The React port under `apps/react` mirrors this private bridge for parity
verification only. Start it with
`npm run dev --workspace @crossword/react-port` (port 5174) and run the
browser harnesses under `scripts/` against it. It proxies the local Flask
backend and is never deployed or published; the scanner exemptions in
`scripts/forbidden-content.json` cover exactly that private surface. The
future standalone frontend is a separate, generator-backed app without any
provider integration.

The Vue source matches `origin/rebuild` (`8523664`). The generator repository
and vendored packages are preserved; connecting them to the Vue UI is a
separate task. Do not apply or drop the existing stash without reviewing it.

## Browser smoke prerequisites

`make legacy-smoke` starts `scripts/legacy-smoke-server.py`, which serves the
page and a tiny provider-neutral puzzle entirely on localhost. It then runs a
headless Chrome/Chromium executable, checking that Vue has compiled the
template and no `[[ ... ]]` or Vue directive markers remain in the live DOM.

Set `CHROME_BIN` when the browser is not in a standard location. The target
prints a skip message on machines without a browser; CI can use a controlled
Chrome runner for this gate.
