# Crossword Puzzle App

A web application for solving crossword puzzles that works both online and offline.

> **Next generation:** the audited product, architecture, original-construction,
> local-AI, quality, and migration roadmap starts at
> [docs/plans/README.md](docs/plans/README.md). The current Flask/NYT application
> is a private continuity bridge, not the planned public deployment.

## 🚀 Quick Start (Fresh Clone)

```bash
# Installs pinned Python/Node dependencies and builds shared assets plus React.
make bootstrap
```

The repository pins Python through `.python-version`, Node through
`.node-version`, npm through `packageManager` in `package.json`, and both
dependency graphs through `uv.lock` and `package-lock.json`. `uv sync
--all-extras` and `npm ci` are the canonical installation commands.

Then verify and run:
```bash
make doctor       # Check the pinned tools and project .venv
make run          # Build both frontends; React + Flask at http://127.0.0.1:5001/
make test         # Run local Python and JavaScript tests
make legacy-smoke # Mount check with a local synthetic puzzle (Chrome required)
```

React is served by Flask at `/` and `/mobile/<room>/<role>`. The Vue fallback
reference is at `/legacy/` and `/legacy/mobile/<room>/<role>` on the same
server. `make legacy-run` is an alias for `make run`; open `/legacy/` explicitly.

See [SETUP.md](SETUP.md) for the setup contract and troubleshooting.

## Generator development

React is now the private daily-driver frontend with the existing Flask/Socket.IO backend. Vue remains the fallback/parity reference, not the default frontend. The future public generator-backed frontend is not ready. Generation source is maintained separately in `../crossword-generator`; its previous React integration is preserved on `backup/react-generator-integration-ed519f5`, distinct from this private React parity port. This repository consumes versioned archives under `vendor/generator/`, so normal installation, solving tests, and builds do not require the sibling checkout. See [the integration guide](docs/generator-integration.md) for ownership and update commands.

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
make legacy-run  # Same server as make run; Vue at http://127.0.0.1:5001/legacy/
make test        # Run tests
make build       # Rebuild shared legacy assets and React
make react-assets # Rebuild only the Flask-served React bundle
make test-cov    # Run tests with coverage
make clean       # Clean cache files
make deps-update # Update dependencies
make npm-audit   # Record npm audit JSON; never upgrades dependencies
```

## Legacy browser assets

The Vue fallback page at `/legacy/` loads Vue, Axios, and Socket.IO from
`src/crossword/static/lib/`. Those files are generated (and intentionally
ignored) by `make legacy-assets` from the exact npm lockfile. Do not download
or hand-vendor replacement files. See
[docs/legacy-assets.md](docs/legacy-assets.md) for the asset provenance.

The browser smoke uses a synthetic local puzzle and never calls the private
provider. Private provider tests are marked `live_provider`, skipped by the
default suite, and available only through `make legacy-test-live` with an
explicit opt-in.
