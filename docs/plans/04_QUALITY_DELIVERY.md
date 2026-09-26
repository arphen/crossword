# Quality, security, and delivery plan

> **25 September 2026 supersession notice:** Read the [active personal crossword plan](06_PERSONAL_EPISTEME.md) and [ADR 0003](../adr/0003-local-ollama-native-runtime.md) first. The owner has selected the current React/Flask application, Ollama and native construction. Browser-only, backend-free, new-static-workspace and conflicting delivery instructions below are historical. The active plan also governs initial visual calibration, weekday recipes and clue grammar.

Status: release engineering contract.

## Quality philosophy

Tests should make design mistakes expensive and refactoring safe. Line coverage
is evidence that code ran; it is not evidence that the important assertions can
detect a fault. The target is a small, fast core suite, strong generative and
mutation checks on policy, realistic browser journeys, and explicit evaluation
of the probabilistic model boundary.

Production generation is AI-required. Production correctness is not
probabilistic: an LLM draft is accepted only through schemas, source resolution,
and deterministic validators.

## Test portfolio

### Domain unit tests

Pure, table-driven tests cover:

- topology numbering, intersections, symmetry, connectivity, and special cells;
- selection/direction/navigation and pattern projection;
- entering, clearing, checking, revealing, nudging, timing, and completion;
- recipe and editorial policy;
- profile reduction and household blending;
- clue and answer eligibility;
- scoring, manifests, hashes, import/export, and migrations.

Use fake clocks, seeded randomness, and in-memory ports. These tests should run
in seconds and contain no browser, model, storage, or network dependency.

### Property and metamorphic tests

Use `fast-check` for broad invariants:

- serialize/deserialize and export/import round trips preserve meaning;
- numbering and intersections are consistent for valid generated topologies;
- every white cell belongs to the expected entries;
- every accepted fill agrees at every crossing and honors all-different policy;
- rotations preserve symmetry rules;
- seeded requests are stable within a pinned engine fixture;
- cancelling any search leaves no published puzzle;
- profile updates are bounded and hard exclusions remain hard;
- event replay yields the same session/profile projection;
- corrupt and oversized inputs fail without partial persistence.

Metamorphic checks change one condition at a time: tightening a hard policy
cannot introduce a prohibited answer; adding a fixed crossing cannot increase a
slot's candidate set; an easier clue variant cannot expose solution characters.

### Differential and reference tests

For tiny dictionaries and grids, compare the TypeScript worker with an
independent Python reference solver. Compare satisfiable/unsatisfiable status,
constraint adherence, and complete solution sets where bounded. The reference
implementation should be deliberately simple enough to review.

Run every engine adapter against the same conformance suite. If Rust/WASM is
added, it does not receive a separate interpretation of the rules.

### Seeded golden manifests

Keep a compact, licensed/synthetic corpus that exercises:

- ordinary, rebus, circled, shaded, and combined cells;
- duplicate clue surfaces and repeated roots;
- hard locale/proper-name exclusions;
- all day recipes currently shipped;
- unsatisfiable and below-quality generations;
- model malformed output, retry, cancellation, and unload;
- every released storage/import schema.

Goldens pin semantic outcomes and receipts, not incidental whitespace or search
progress. Updating one requires a reviewed reason and a diffable quality report.

### Component and accessibility tests

Use Testing Library against public behavior. Cover grid focus, clue/pattern
linkage, stable clue lanes, compact dock, commands, dialogs, setup, generation,
offline/error states, and result review. Run `axe` for automated checks and keep
manual screen-reader scripts for the composite grid and live announcements.

No component test reaches IndexedDB/WebLLM directly; use contract fakes through
the composition boundary.

### Browser journeys

Playwright runs Chromium, Firefox, and WebKit for critical paths:

- first-run capability/model setup with a deterministic model adapter;
- start, type, navigate, change direction, close/reopen, and resume;
- check, nudge, reveal, complete, and review;
- keyboard-only, touch-sized, and 200% zoom use;
- panorama two-lane spine, standard rails, and compact dock;
- offline reload and service-worker upgrade with an in-progress puzzle;
- export, reset, import, and migration recovery;
- generation cancellation, quota failure, corrupt model response, and retry.

Real WebGPU/model smoke tests run on a controlled supported runner or scheduled
device lab, not on every pull request. They cannot be replaced by fakes in the
release candidate gate.

### Visual regression

Snapshot a fixed legal puzzle in light, dark, high-contrast, reduced-motion,
and forced-color modes at empty, half-solved, checked, and completed states.
Mask the clock and other nondeterministic surfaces. Review intentional changes;
never auto-approve a baseline from the same change that caused it.

### AI evaluation

Maintain a versioned evaluation set of lexeme/sense/fact packets and audience
recipes. Score:

- structured-output success and retry rate;
- lexicon/sense resolution rate;
- factual grounding and contradiction;
- answer leakage and morphological leakage;
- clue uniqueness, fairness, mechanism, grammar, locale, and day fit;
- semantic breadth versus profile reinforcement;
- harmful or excluded material;
- latency, tokens, memory, cancellation, and recovery.

Automated graders can triage but do not grade themselves. Deterministic checks
own objective failures. A blinded human panel samples clues and whole puzzles,
including both household players, with an editorial rubric. Pin the model,
runtime, prompts, lexicon, and evaluator versions for every report.

## Mutation testing

Use Stryker for TypeScript domain/application/construction policy. The initial
ratchet is:

- mutation score at least 80% on changed core modules;
- no surviving mutant in hard constraints, answer/clue eligibility, import
  integrity, profile exclusions, or completion correctness;
- equivalent/time-out mutants reviewed and documented, not silently ignored;
- UI/CSS, generated codecs, vendor adapters, and logging excluded only with an
  explicit rationale.

Run a changed-file mutation job on pull requests and the full core campaign
nightly or before promotion. Never weaken an assertion merely to make a mutant
run faster.

Use `mutmut` for substantive Python reference/build policy and `cargo-mutants`
if a Rust engine graduates. Do not mutation-test trivial CLI glue. The purpose
is to meta-test specifications at the risk-bearing seams.

## Coverage and static analysis

- strict TypeScript, no unchecked indexed access, exact optional properties;
- ESLint including hooks, accessibility, boundaries, and import cycles;
- formatting checked but not confused with correctness;
- dependency and dead-code analysis;
- Python lint/type checks for maintained tools;
- coverage at least 90% branch for domain/application policy, ratcheted rather
  than used as a repository-wide vanity number;
- every production dependency licensed, pinned by lockfile, and reviewed for
  browser/runtime necessity.

## Performance and energy verification

Measure production builds on named reference devices. Track distributions and
artifact versions, not one developer's best run.

### Solve path budgets

- p95 key-to-paint under 50 ms;
- no interaction long task above 50 ms;
- zero continuous animation loop or socket/network traffic in solo solve;
- no layout shift when clues complete or change variant;
- idle CPU close to an empty app tab with the clock visible;
- bounded heap/listeners/timers across a ten-minute synthetic solve;
- no model inference while typing.

### Construction budgets

Define separate targets for model load, candidate generation, fill, clueing, and
validation on each supported recipe. Report time-to-first-progress, p50/p95,
peak memory, cancellation latency, and thermal/energy observations. A slow
background batch is acceptable only when the UI says so and remains cancellable.

Use Chrome traces, React profiling, Lighthouse, browser memory observations,
and long-task/performance observers. Validate Safari/WebKit separately because
WebGPU and storage behavior are product gates. Effects use compositor-friendly
properties, bounded particles, reduced-motion branches, and explicit cleanup.

## Privacy and security

The threat model includes malicious imports, compromised static/model assets,
prompt injection inside source content, cache poisoning, dependency compromise,
XSS through clues/facts, model denial of service, and accidental inclusion of
legacy copyrighted material.

Required controls:

- text rendering by default; sanitization for any deliberately supported rich
  clue markup;
- strict schema/size/depth limits at imports, storage, worker, and model edges;
- content-addressed model/lexicon artifacts and integrity verification;
- restrictive CSP with no arbitrary remote scripts or `eval` escape hatch;
- minimal Permissions Policy and no analytics/telemetry SDK by default;
- explicit network allowlist and a test that ordinary solving makes no request;
- worker cancellation/resource limits and bounded model retries;
- transactional migrations and recoverable reset/export;
- dependency audit, lockfile review, SBOM, secret scan, and signed release
  provenance where the host supports it;
- no raw prompt/profile/event upload and no hidden cloud fallback.

Run a security-focused review before the first public staging release and after
any import format, hosting header, model runtime, or multiplayer change.

## Content and legal release gate

The public artifact must contain only original or appropriately licensed
content. Before promotion:

1. generate the source/license ledger and required attributions;
2. scan source, bundles, fixtures, caches, maps, and service-worker precache for
   forbidden NYT endpoints, XWord Info links, provider IDs, and known legacy
   clue/answer samples;
3. ensure no live integration test or build step contacts the NYT service;
4. verify imported licensed data matches the approved transformation and
   distribution terms;
5. review the project license, especially before borrowing any GPL LACUNA code;
6. record the tested artifact digest and content manifest.

The local legacy bridge may continue privately during migration. It is built by
a separate command, excluded from the deployable workspace graph, and cannot
contribute caches or fixtures to a release artifact.

## CI pipeline

Every pull request runs:

1. lockfile and repository policy checks;
2. formatting, lint, type, boundary, and license checks;
3. unit, property, component, migration, and differential tests;
4. production build and forbidden-content scan;
5. changed-core mutation campaign;
6. Chromium critical browser journeys, accessibility, and budget smoke checks.

Merge queue/main runs the full browser matrix and coverage ratchet. Nightly runs
the full mutation campaign, dependency audit, larger solver corpus, AI fake-
adapter evaluation, and extended performance tests. Scheduled supported-device
runs exercise the pinned real local model.

Do not call a live copyrighted provider from CI. Do not allow a flaky network
test to define build health.

## Release and Cloudflare flow

Use trunk-based, small reviewed changes and conventional changesets/ADRs for
schema or architecture decisions. Produce one immutable static artifact:

1. clean install from lockfile;
2. run release gates;
3. create artifact, SBOM, source ledger, and digest;
4. deploy that artifact to Cloudflare staging;
5. run CSP/header, asset-integrity, offline, update, route, model-host, and real
   browser smoke tests against staging;
6. manually promote the same digest;
7. run production smoke without generating or uploading personal data;
8. retain rollback to the preceding artifact and schema-compatibility window.

Never rebuild between staging and production. A service-worker release defines
its update/rollback behavior and preserves sessions created by the immediately
previous supported schema.

## Definition of done

A change is done when:

- its behavior and failure modes are represented in tests;
- relevant mutants are killed;
- accessibility and keyboard behavior are preserved;
- persistence/import compatibility is handled;
- workers cancel and clean up;
- performance/security/content budgets do not regress;
- docs/ADR and source ledger change when the contract changes;
- a clean checkout can install, test, build, and run using the pinned toolchain;
- no user-owned data or unrelated working-tree change is overwritten.

## Current baseline captured during this audit

On 2026-08-29, after installing the standardized toolchain, `make setup` and
`make test` completed with 50 Python and 6 JavaScript tests passing. npm reported
13 legacy dependency vulnerabilities (9 high). A real browser launch still
failed functionally because `static/lib/vue.js`, `axios.min.js`, and
`socket.io.min.js` are ignored/untracked and return 404, leaving raw Vue
expressions in the page. The current green suite therefore does not constitute
a runnable-product gate.
