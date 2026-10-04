# ADR 0001: Static React Solver Boundary

Status: partially superseded, 25 September 2026, by [ADR 0003](0003-local-ollama-native-runtime.md). The static-only deployment and `apps/web` requirements no longer apply. The pure domain, immutable puzzle, and UI separation principles remain applicable. The original decision is retained below as history.

## Context

The legacy Flask/Vue application remains a private continuity bridge. The new
solver must work offline, keep puzzle/session truth independent from rendering,
and leave room for local construction workers and IndexedDB adapters without
putting those dependencies into the domain package.

## Decision

Use a React 19 + TypeScript + Vite application in `apps/web`, with pure domain
values and use cases in `packages/domain`. The deployable artifact is static.
The application shell registers a cache-first service worker in production;
model inference, fill search, and persistence adapters are future boundaries,
not imports into the domain.

Puzzle manifests are validated at the domain boundary and serialized as JSON.
The fixture is provider-neutral and remains explicitly marked synthetic until a
local construction receipt exists.

## Consequences

- The solver can be hosted as static assets and continue reading a cached shell
  without a Flask application server.
- Domain tests run without a DOM, while the web package owns browser interaction
  tests.
- IndexedDB, local-model, and worker protocols can be added behind ports without
  changing puzzle/session invariants.
- The service worker caches immutable shell assets at runtime; it never owns
  model files or mutates an active solve session.
