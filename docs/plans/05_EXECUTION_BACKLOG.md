# Execution backlog and agent work packages

> **25 September 2026 supersession notice:** Read the [active personal crossword plan](06_PERSONAL_EPISTEME.md) and [ADR 0003](../adr/0003-local-ollama-native-runtime.md) first. The owner has selected the current React/Flask application, Ollama and native construction. Browser-only, backend-free, new-static-workspace and conflicting delivery instructions below are historical. The active plan also governs initial visual calibration, weekday recipes and clue grammar.

Status: sequenced implementation plan. Estimates are relative slices, not
calendar promises.

## How to use this backlog

Work in thin, releasable vertical slices. Every item below has a bounded
outcome, dependencies, and acceptance evidence. Prefer one agent per package or
non-overlapping file area. The coordinating agent owns architecture decisions,
integrates results, and runs the full gate; subagents do not make silent product
or license decisions.

Before each slice:

1. read the plan index and the documents relevant to the package;
2. inspect the current tree and user changes;
3. state the files/boundary owned and the acceptance command;
4. add or update tests before broad implementation;
5. report decisions, evidence, residual risk, and exact commands run.

Do not ask an agent to "modernize the app." Ask it to implement one explicit
port, use case, component, migration, or quality gate. Parallelize discovery,
fixtures, UI harness, and tool spikes; serialize schema decisions and changes to
shared composition/configuration files.

## Milestone 0 — trustworthy baseline

### M0.1 Toolchain contract

Outcome: a clean machine uses one documented tool path.

- pin Node LTS in `.nvmrc` or `.node-version` and `packageManager`;
- pin Python in `.python-version` and manage `.venv` with `uv`;
- make `uv sync --all-extras` and the selected JS lockfile install canonical;
- add `doctor`, clean setup, test, build, and run commands;
- remove documentation that proposes ad-hoc global Python packages.

Acceptance: clean checkout setup succeeds with `uv` and the pinned Node; doctor
prints actionable versions and no fallback interpreter search.

### M0.2 Repair the legacy developer loop

Outcome: the private continuity app actually starts from a clean checkout.

- replace ignored hand-vendored frontend files with a reproducible legacy asset
  install/build step;
- align README, Makefile, Docker/ignore files, modules, and port 5001;
- add a browser smoke that proves Vue mounted and no template delimiters remain;
- isolate live-provider integration tests behind an explicit local marker;
- record npm audit rather than applying an unreviewed forced upgrade.

Acceptance: `legacy:test` and `legacy:run` pass on a clean checkout; default CI
uses legal local fixtures and no live NYT request.

### M0.3 Characterization and legal fixtures

Outcome: signature behavior can survive replacement without shipping protected
content.

- build synthetic/provider-neutral fixtures for normal, rebus, circle, shade,
  duplicate clue, and combined cells;
- capture selection, direction, keyboard, checking, reveal, completion, and
  clue-spine lane behavior;
- document which legacy quirks are intentionally corrected;
- add a forbidden-content allowlist/scan skeleton.

Acceptance: fixture provenance is documented and behavior tests pass without a
network connection.

### M0.4 Versioned continuity export

Outcome: household history is recoverable before storage changes.

- define export v1 schema and integrity manifest;
- export settings, completion metadata, and in-progress state where available;
- exclude legacy puzzle bodies/solutions by default;
- implement preview, transactional import, validation, and round-trip tests.

Acceptance: export-reset-import restores the supported state; corrupt input
cannot partially write.

## Milestone 1 — static solving product

### M1.1 Workspace and fitness functions

Outcome: React/Vite shell with enforced inward dependencies.

- create `apps/web` and initial domain/application/ui/test-support packages;
- strict TypeScript, Vitest, Testing Library, Playwright, ESLint boundaries;
- production static build and Cloudflare staging adapter;
- ADR for React/Vite, storage, and deployment choice.

Acceptance: domain test runs without DOM; dependency-rule violation fixture
fails lint; static hello route passes build and offline smoke.

### M1.2 Provider-neutral puzzle domain

Outcome: immutable puzzle values and codecs cover all fixture mechanics.

- implement IDs, topology, entries, cells, clue sets, provenance, receipts;
- derive numbering/intersections/patterns;
- validate and serialize manifests;
- property-test invariants and round trips.

Acceptance: all legal fixtures load; malformed topology cannot be constructed;
core branch coverage and mutation targets pass.

### M1.3 Solve-session use cases

Outcome: one authoritative selection/direction/session model.

- navigation, entry, rebus, check, reveal, nudge, active timing, completion;
- domain events with monotonic timestamps and stable IDs;
- replay/snapshot tests and current-behavior characterization.

Acceptance: property tests cover event replay; no parallel `activeDirection`
truth exists; hard correctness mutants are killed.

### M1.4 Clue-spine design harness

Outcome: three visual explorations of the signature interface using one fixture.

- semantic tokens and type/spacing scales;
- explicit stable rail/lane/row projection;
- panorama, standard, and compact component modes;
- answer-pattern/grid linkage and solved-state policies;
- reduced motion, high contrast, forced colors, and 200% zoom.

Acceptance: one direction is selected with recorded rationale; visual,
keyboard, axe, and paint-cost evidence passes before integration.

### M1.5 Complete accessible solver

Outcome: static legal fixture is a polished offline crossword.

- integrate grid, clue spines, commands, dialogs, result, and learning review;
- roving focus/announcement contract and touch behavior;
- IndexedDB session repository with visibility-loss snapshot;
- PWA install/update/offline flow.

Acceptance: critical Playwright matrix, accessibility suite, visual baselines,
and solve performance budgets pass.

## Milestone 2 — local intelligence laboratory

### M2.1 Source and license decision

Outcome: approved small lexicon pipeline and project-license decision.

- evaluate WordNet/Wikidata/Wiktionary/SCOWL transformations;
- record license/attribution obligations and reject unsuitable sources;
- decide project licensing before any LACUNA code reuse;
- produce a tiny signed lexicon/index artifact and source ledger.

Acceptance: counsel/owner review is recorded; every emitted record traces to an
approved source and artifact hash.

### M2.2 Construction contracts and reference oracle

Outcome: stable recipe, topology, solver, scorer, and result ports.

- define 5x5/7x7 laboratory recipes and curated topologies;
- write independent Python reference solver with `uv` and OR-Tools if selected;
- create satisfiable/unsatisfiable differential corpus;
- specify cancellation/progress/resource protocols.

Acceptance: oracle is exhaustively checked on tiny fixtures; placeholder tests
and always-true validators are forbidden.

### M2.3 TypeScript fill worker

Outcome: deterministic bitset CSP produces quality-scored mini fills.

- positional indexes, MRV, value ordering, propagation, all-different;
- seeded restarts, branch-and-bound, cancellation, progress;
- hard/soft policy separation and diagnostic failure receipts.

Acceptance: differential/property/golden/mutation suites pass; no invalid grid
is published; p95 mini-grid budget passes.

### M2.4 Mandatory model broker

Outcome: one WebLLM worker can install, verify, evaluate, generate, cancel, and
unload the pinned model.

- versioned model manifest and shard integrity;
- capability/storage/onboarding use cases;
- structured candidate and clue schemas with bounded repair;
- privacy/network policy and power lifecycle;
- deterministic fake adapter plus scheduled real-device evaluation.

Acceptance: the original-construction use case fails with a typed capability
result when the model is not enabled; no generic non-AI generator exists; the
model unloads after queue preparation.

### M2.5 End-to-end mini constructor

Outcome: required LLM + deterministic solver publishes immutable mini puzzles.

- candidate bag, lexeme/sense resolution, fill, clue ladder, validation;
- receipts, hashes, failure diagnostics, local queue;
- AI evaluation and blinded human scorecard.

Acceptance: every answer and fact has provenance, every clue is validated,
identical published manifests survive reload, and rejected drafts are unplayable.

## Milestone 3 — personalized Monday alpha

### M3.1 Event and profile system

Outcome: local, inspectable learning signals replace score/time guesswork.

- event schema and privacy/retention policy;
- familiarity, clue mechanism, semantic, locale, pace, novelty projections;
- explicit controls, examples, correction, rebuild, reset;
- named-player and cooperative household blend.

Acceptance: crossing-aware evidence tests pass; one event cannot swing a
profile beyond bounds; export/delete/rebuild are verified.

### M3.2 Monday content bank and recipe

Outcome: curated 15x15 topology bank and editorial quality contract.

- template review tooling and fillability statistics;
- controlled glue/repetition, semantic mix, exclusions, recent-answer window;
- Monday clue/easier-nudge rubric;
- human review interface and failure taxonomy.

Acceptance: target corpus clears hard automated gates and blind household solve
panel thresholds; no unsupported day label is shown.

### M3.3 Ahead-of-play queue

Outcome: model works in bounded batches and play remains calm.

- configurable queue depth, generation scheduling, cancellation, unload;
- storage quota and corrupt/incompatible artifact recovery;
- construction state UI and battery/network disclosures.

Acceptance: no model activity or network request during active solve; queue and
session survive offline restart; generation never starts unexpectedly under
disallowed conditions.

### M3.4 Dual-run continuity

Outcome: household can choose original Monday or local legacy sessions during
the transition.

- explicit source badges and separate repositories/commands;
- no legacy material enters original profile evaluation fixtures or exports;
- collect structured feedback on originals without telemetry.

Acceptance: both local paths work; the public/static build graph cannot import
the legacy adapter.

## Milestone 4 — public privacy-first release

### M4.1 Release allowlist and security review

Outcome: deployable artifact is clean, static, and hardened.

- content/source/SBOM manifests and forbidden-content scan;
- CSP, isolation, permissions, cache, import, and model-host review;
- dependency remediation by controlled migration, not forced audit churn;
- threat model and external review findings resolved or explicitly accepted.

Acceptance: clean artifact scan and security suite; no Flask, SQLite,
Socket.IO, NYT, or XWord Info dependency in the artifact.

### M4.2 Staging and exact-artifact promotion

Outcome: reproducible Cloudflare deployment.

- immutable build, digest, staging deploy, smoke and offline/update tests;
- model shard/header/range/integrity verification;
- manual promotion of exact digest and tested rollback.

Acceptance: production digest equals staging digest; rollback preserves prior
sessions; public product performs no application-backend call.

### M4.3 Operational readiness

Outcome: maintainable public software without surveillance.

- user-facing diagnostics/export, privacy and content documentation;
- local crash/error report copy flow rather than automatic telemetry;
- support matrix, known capability failures, disaster and model-host recovery;
- release checklist and ownership.

Acceptance: a fresh supported device can install, generate, solve, update,
export, reset, and recover using the documented path.

## Milestone 5 — day graduation and experiments

Graduate Tuesday, Wednesday, Thursday, Friday, Saturday, and Sunday in that
order only when each recipe meets its specific automated and blinded-human
threshold. Thursday introduces mechanics; Friday/Saturday introduce open
themeless quality; Sunday introduces 21x21 resource pressure. Each is a product
release, not a configuration toggle.

Parallel research after Monday quality:

- Rust/WASM fill-engine benchmark against the same port and corpus;
- topology generation with fillability feedback;
- better factual grounding bundles and explanation cards;
- multilingual/locale-aware fill forms;
- same-device cooperative play;
- separately reviewed WebRTC/offline-exchange multiplayer.

None blocks a polished Monday static release.

## Suggested first ten pull requests

1. Plan index, ADR template, tool pins, and `doctor`.
2. Reproducible legacy assets plus clean-clone browser smoke.
3. Legal synthetic fixture pack and forbidden-content scanner skeleton.
4. Versioned legacy continuity export/import.
5. React/Vite workspace, strict boundaries, CI, and static staging shell.
6. Provider-neutral puzzle domain and codecs.
7. Solve-session reducer/events with property and mutation tests.
8. Clue-spine visual harness and design decision.
9. Accessible complete fixture solver with IndexedDB/PWA.
10. Approved mini lexicon plus reference-solver laboratory.

PRs 3 and 4 can proceed in parallel after schemas are coordinated. Visual
exploration can begin alongside domain work using the agreed fixture. Shared
workspace/configuration changes and persistent schemas stay coordinator-owned.

## Stop/go gates

- Do not remove the local legacy bridge until the household has an export and a
  reliable original queue.
- Do not publicly deploy while any legacy provider material can enter the
  artifact.
- Do not bundle or copy LACUNA GPL code until the project-license decision is
  explicit.
- Do not label a day available before its recipe and evaluation gates pass.
- Do not replace the TypeScript solver with Rust/WASM without benchmark proof.
- Do not add cloud inference to work around unsupported local AI.
- Do not add real-time multiplayer under the frontend-only milestone without a
  separate signaling/privacy decision.
- Do not optimize visual effects from intuition; trace first and enforce the
  idle/interaction budgets.
