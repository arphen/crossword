# Clean architecture and migration plan

> **25 September 2026 supersession notice:** Read the [active personal crossword plan](06_PERSONAL_EPISTEME.md) and [ADR 0003](../adr/0003-local-ollama-native-runtime.md) first. The owner has selected the current React/Flask application, Ollama and native construction. Browser-only, backend-free, new-static-workspace and conflicting delivery instructions below are historical. The active plan also governs initial visual calibration, weekday recipes and clue grammar.

Status: target system design and strangler strategy.

## Architecture decision

Build the new product as a static React 19 + TypeScript + Vite PWA. React is not
the architecture; it is the outer UI adapter. The deciding evidence is the
working `lalange` local-AI/PWA stack, the LACUNA interaction spike, current
testing support, and the opportunity to share operational patterns without
sharing product logic.

The domain and use cases must remain importable without React, IndexedDB,
WebLLM, Cloudflare, browser globals, or network access. This satisfies the
dependency rule and keeps a future renderer, solver, or host change bounded.

```text
                 React UI / PWA shell
                         |
                 application use cases
                         |
         crossword domain + policy + value objects
                    /             \
          required ports       domain events
             /    |    \
       IndexedDB solver  local-model broker
          adapter worker      worker adapter
```

Dependencies point inward. Domain code never imports an adapter. Use-case code
depends on narrow ports. The composition root chooses browser implementations.

## Proposed repository shape

Keep the migration in this repository so product decisions, fixtures, and
history stay together:

```text
apps/
  web/                    React shell, routes, PWA, composition root
packages/
  domain/                 puzzle, topology, solve, profile, recipe policies
  application/            use cases and ports
  ui/                     design tokens and accessible components
  construction/           fill search, scoring, deterministic validators
  model-runtime/          model manifest, broker protocol, WebLLM adapter
  persistence/            IndexedDB schemas, migrations, repositories
  formats/                import/export and immutable manifest codecs
  test-support/           builders, seeds, fixtures, fake clocks and ports
workers/
  constructor/            fill + validation worker entry
  model/                  local LLM worker entry
tools/
  lexicon/                licensed-source transforms and source ledger
  reference-solver/       Python/OR-Tools correctness oracle
legacy/
  flask-nyt/              local-only continuity app after extraction
docs/plans/               product and engineering source of truth
```

Begin as a workspace with package boundaries enforced by lint rules. Do not
publish packages merely to look modular. Split a package only when it protects a
dependency direction, execution boundary, or independently testable policy.

## Domain boundaries

### Puzzle document

Owns topology, cells, entries, clues, special mechanics, provenance,
construction receipt, and integrity. It is immutable after publication.

### Solve session

Owns selection, entered graphemes, checks, reveals, clue variants, active time,
completion, and emitted learning events. It has no DOM or storage knowledge.

### Construction

Owns recipes, candidate sets, constraint solving, quality scoring, clue
validation, and manifest publication. The LLM and fill engine implement
required ports; neither calls React or IndexedDB directly.

### Audience and learning

Owns explicit preferences, named profiles, household blending, event reduction,
familiarity, semantic breadth, and privacy policy.

### Library and continuity

Owns local puzzle queue, archive metadata, imports, exports, and legacy-source
boundaries. It does not make a provider's date the universal puzzle identity.

## Core ports

Keep interfaces small and named for application needs:

```ts
interface GenerateCandidates {
  generate(request: CandidateRequest, signal: AbortSignal): Promise<CandidateBag>;
}

interface ComposeClues {
  compose(request: ClueRequest, signal: AbortSignal): Promise<ClueDraftSet>;
}

interface FillGrid {
  solve(request: FillRequest, signal: AbortSignal): AsyncIterable<FillProgress>;
}

interface PuzzleRepository {
  get(id: PuzzleId): Promise<PuzzleManifest | undefined>;
  publish(puzzle: PuzzleManifest): Promise<void>;
}

interface SessionRepository {
  load(id: SessionId): Promise<SolveSessionSnapshot | undefined>;
  save(snapshot: SolveSessionSnapshot): Promise<void>;
}
```

Return typed results for expected failures: unsupported device, missing model,
storage quota, invalid model output, unsatisfiable topology, quality threshold,
cancelled generation, corrupt import, and schema too new. Exceptions are for
programmer errors and genuinely unexpected infrastructure failures.

Use runtime schemas (for example Zod) only at untrusted boundaries: model
output, storage, import, worker messages, and source transforms. Inside the
domain, validated types and constructors carry the invariant.

## Execution boundaries

### Main thread

The main thread owns rendering, user input, lightweight projections, and use
case orchestration. No inference, constraint search, large lexicon decode, or
bulk profile reduction runs there.

### Constructor worker

Owns indexed lexicon access, CSP state, quality search, and deterministic
validation. Protocol messages are versioned and transferable where practical.
It supports cancellation and emits bounded progress summaries.

### Model worker

Owns the mandatory local model, model lifecycle, candidate generation, clue
composition, and JSON repair/retry policy. There is one broker, not a model
instance per component. It can unload after the local puzzle queue is ready.

### Service worker

Owns the application shell and immutable static-asset update policy. It does
not host the model runtime or construction jobs. A service-worker update cannot
silently invalidate an in-progress puzzle or its model/lexicon receipt.

## Local persistence

Use IndexedDB behind repositories, with separate logical stores for:

- immutable puzzle manifests;
- solve-session snapshots;
- append-only recent solve events;
- reduced player and household profiles;
- preferences and capability decisions;
- model/lexicon/recipe metadata (not necessarily model bytes);
- migration receipts and bounded diagnostics.

Each record has a schema version. Migrations are forward-only, idempotent, and
tested against fixtures from every released schema. A failed migration leaves
the old database intact or creates a recoverable backup; it never partially
mutates the only copy.

Debounce session persistence after meaningful events and force a snapshot on
visibility loss. The UI updates from domain state first; storage latency does
not block typing.

### Portable export

Ship export before migrating user history. The archive is a versioned,
human-inspectable bundle with a manifest and hashes. It can contain settings,
profiles, reduced learning data, original puzzle manifests, and in-progress
sessions. Raw events are opt-in. Secrets and model files are never included.

Legacy NYT puzzle bodies, clues, answers, caches, and solution links are
excluded by default and are never accepted into the deployable release test
fixtures. Import performs schema, integrity, size, and content checks before a
transactional commit. Export/import round trips are golden-tested.

## Mandatory AI capability flow

First launch is an honest capability/onboarding state, not a broken empty app:

1. explain local-only inference, storage size, and power behavior;
2. check WebGPU/runtime compatibility and storage quota;
3. let the user install the pinned compatible model;
4. verify hashes and run the structured-output smoke evaluation;
5. build or import the lexicon artifacts;
6. generate and validate the first small puzzle;
7. show construction state and allow cancellation/retry.

There is no generic non-AI constructor and no cloud fallback. A completed
puzzle remains playable when the model has been unloaded. Capability policy,
model installation, model residency, and active inference are distinct states
in both code and UI.

## UI architecture

The solving page is a projection of `PuzzleManifest`, `SolveSession`, and
`Selection`. One reducer/use case owns direction and selection. The grid and
both clue spines consume stable entry and cell IDs; they do not search the
entire crossword during render.

Recommended component boundaries:

- `PuzzleWorkspace`: responsive layout only;
- `CrosswordGrid`: semantic grid and roving focus;
- `ClueSpine`: stable lane projection;
- `ClueCard` and `AnswerPattern`: linked controls;
- `ActiveClueDock`: compact-mode projection;
- `SessionCommands`: checks, reveals, pause, settings;
- `ResultCard` and `LearningReview`;
- `ModelSetup`, `GenerationQueue`, and `ConstructionDiagnostics`.

Keep rendering state close to its owner. Do not mirror domain state into a
global store by default. Use an external-store boundary only for shared session
snapshots and worker state. Derived view models are memoized by immutable input,
not maintained as a second truth.

Build the design system and clue-spine harness with a fixed legal fixture before
connecting construction. This allows visual and accessibility work without a
live provider or model download.

## Hosting and privacy

The deployable artifact is static. Prefer Cloudflare Workers Static Assets for
the first hosting spike because it is Cloudflare's current static deployment
path; retain the Lalange pattern of a staging deployment, verification, and
manual promotion of the exact tested artifact. A Pages adapter remains cheap if
the operational evidence favors it.

There is no application backend, server database, analytics SDK, cloud prompt,
or content API. Initial app, model, and licensed lexicon downloads are disclosed
network operations. Model weights are too large to assume they fit one ordinary
static-host asset; use verified, versioned shards from an explicit model host or
object store and cache them through the runtime. Prompts and profile data stay
local.

Set strict CSP, permissions policy, referrer policy, MIME protections, and
cross-origin isolation headers where WebGPU/runtime tests support them. Treat
service-worker scope, cache poisoning, model integrity, imports, and dependency
supply chain as security boundaries.

Real-time multiplayer is not smuggled through a fake "backend-free" claim. Keep
the current Flask/Socket.IO experiment local-only. A future workstream may test
WebRTC with minimal signaling, offline turn exchange, or same-device co-op,
each with an explicit privacy and hosting model.

## Strangler migration

Never rewrite the UI, storage, provider, solver, and content system in one cut.

### Phase 0 — freeze and characterize

- add the plan index and architecture decision records;
- capture legal synthetic fixtures for grid, spine, rebus, circle, shade, and
  combined cell behavior;
- restore a versioned local export path;
- record current keyboard and completion semantics in browser tests;
- label the legacy server local-only.

Exit: clean clone boots reproducibly and characterization tests protect the
signature behavior.

### Phase 1 — new shell and domain

- create the workspace, React shell, domain types, solve reducer, fixture
  adapter, design tokens, and responsive clue spine;
- add IndexedDB repositories behind ports;
- implement PWA/update and import/export contracts;
- keep the Flask app available via a separate legacy command.

Exit: a legal fixture is fully playable, accessible, durable, offline, and
visually approved in the static shell.

### Phase 2 — intelligence laboratory

- ingest a small licensed lexicon with a source ledger;
- implement the TS constraint worker and Python reference oracle;
- implement the required model broker and first-run gate;
- publish seeded 5x5/7x7 manifests with grounded clue ladders.

Exit: differential, mutation, AI-evaluation, privacy, and performance gates pass.

### Phase 3 — household Monday alpha

- curated 15x15 template bank and Monday recipe;
- event log, inspectable profiles, audience blending, and puzzle queue;
- human review scorecard and failure diagnostics;
- run legacy and original puzzles side-by-side locally, never mixing content.

Exit: enough original puzzles are enjoyable in blind household solves and meet
quality/latency thresholds.

### Phase 4 — remove public NYT dependence

- make original generation the default;
- build the release artifact from an explicit allowlist;
- prove no provider route, fixture, cache, clue, answer, or solution link is in
  the artifact;
- deploy staging, run smoke/offline/header checks, and promote the same digest.

Exit: public product works with no Flask process and no NYT material.

### Phase 5 — graduate day recipes

Add Tuesday onward only behind their own construction, clue, performance, and
human-evaluation gates. Decommission the legacy bridge when household continuity
no longer depends on it; retain only clean-room behavior fixtures and history.

## Architectural fitness functions

Automate these rules:

- domain packages cannot import React, browser APIs, adapters, or vendor SDKs;
- application packages cannot import concrete persistence/model/host modules;
- UI cannot call WebLLM or IndexedDB directly;
- workers exchange versioned messages and honor cancellation;
- no network call is possible during ordinary solve after assets are cached;
- no deployable bundle contains forbidden legacy/provider strings or fixtures;
- production imports contain no test-only data;
- every stored/imported/model value crosses a runtime schema boundary;
- bundle, model, lexicon, idle CPU, interaction, and memory budgets are checked;
- dependency cycles and unowned cross-package imports fail CI.

SOLID is a design pressure here, not a class-count target: give each module one
reason to change, hide volatile providers behind ports, compose small policies,
and prefer substitution tests over inheritance hierarchies.
