# Crossword Puzzle App

A web application for solving crossword puzzles that works both online and offline.

> **Next generation:** the audited product, architecture, original-construction,
> local-AI, quality, and migration roadmap starts at
> [docs/plans/README.md](docs/plans/README.md). The current Flask/NYT application
> is a private continuity bridge, not the planned public deployment.

## 🚀 Quick Start (Fresh Clone)

```bash
# Installs the pinned Python and Node dependencies and builds legacy assets.
make bootstrap
```

The repository pins Python through `.python-version`, Node through
`.node-version`, npm through `packageManager` in `package.json`, and both
dependency graphs through `uv.lock` and `package-lock.json`. `uv sync
--all-extras` and `npm ci` are the canonical installation commands.

Then verify and run:
```bash
make doctor       # Check the pinned tools and project .venv
make legacy-run   # Start the private bridge on http://127.0.0.1:5001
make web-dev      # Start the React replacement solver (separate terminal)
make test         # Run local Python and JavaScript tests
make legacy-smoke # Mount check with a local synthetic puzzle (Chrome required)
```


## v2 web app (React replica of the legacy solver)

The next-generation client currently **replicates the legacy crossword
exactly** (ADR 0003) on the new architecture: domain solve engine, IndexedDB
persistence, in-browser model runtime, and a Playwright/e2e regression net.

```bash
make web-dev        # React replica on http://localhost:5173
npm run e2e         # browser journeys, paint guards, visual baselines
npm run e2e:install # once: Chromium into .browsers/
npm run scan:content
```

Night mode is the moon/sun switch in the bottom menu; Export/Import live on
the same row. Known gaps vs legacy are listed in
[docs/adr/0003-legacy-replica-pivot.md](docs/adr/0003-legacy-replica-pivot.md).
See [SETUP.md](SETUP.md) for the setup contract and troubleshooting.

## 📋 Manual Setup

If you prefer manual setup or already have uv installed:

```bash
# Install uv using the official instructions, then:
make setup
```

See [SETUP.md](SETUP.md) for detailed documentation.

## 🛠️ Development Commands

```bash
make help        # Show all available commands
make legacy-run  # Run development server on port 5001
make test        # Run tests
make test-js-cov  # Run V8 coverage for maintained TypeScript packages
make e2e-ci       # Run CI-safe Playwright journeys and paint guards
make mutation-test # Enforce the deterministic construction mutation floor
make build       # Rebuild ignored legacy browser assets
make test-cov    # Run tests with coverage
make clean       # Clean cache files
make deps-update # Update dependencies
make npm-audit   # Record npm audit JSON; never upgrades dependencies
```

## Legacy browser assets

The private continuity page loads Vue, Axios, and Socket.IO from
`src/crossword/static/lib/`. Those files are generated (and intentionally
ignored) by `make legacy-assets` from the exact npm lockfile. Do not download
or hand-vendor replacement files. See
[docs/legacy-assets.md](docs/legacy-assets.md) for the asset provenance.

The browser smoke uses a synthetic local puzzle and never calls the private
provider. Private provider tests are marked `live_provider`, skipped by the
default suite, and available only through `make legacy-test-live` with an
explicit opt-in.
