# Puzzle-intelligence and construction plan

> **25 September 2026 supersession notice:** Read the [active personal crossword plan](06_PERSONAL_EPISTEME.md) and [ADR 0003](../adr/0003-local-ollama-native-runtime.md) first. The owner has selected the current React/Flask application, Ollama and native construction. Browser-only, backend-free, new-static-workspace and conflicting delivery instructions below are historical. The active plan also governs initial visual calibration, weekday recipes and clue grammar.

Status: target technical and editorial contract.

## The central rule

Original puzzle construction requires a local LLM. The model supplies semantic
breadth, theme material, clue language, and personalized associations. It does
not get to declare a grid valid, invent an unsupported fact, override a banned
answer, or smuggle an unlicensed source into the product.

The deterministic system owns topology, crossings, answer eligibility,
uniqueness, reproducibility, scoring, and final validation. This is not a
non-AI fallback: the LLM and the deterministic engine are two required halves
of the constructor.

```text
audience + day recipe + seed
             |
             v
    local LLM candidate planner
             |
             v
 licensed lexicon/sense resolution
             |
             v
 topology -> constraint fill -> quality search
             |
             v
 grounded local LLM clue ladder
             |
             v
 deterministic + editorial validators
             |
             v
 immutable puzzle manifest
```

Generation may run ahead to create a small local queue. The model is then
unloaded during normal solving. A generated puzzle never changes underneath a
player, even if the profile or installed model changes later.

## Domain documents

Treat these as versioned domain values, not arbitrary JSON blobs:

```ts
type PuzzleManifest = {
  schemaVersion: number;
  puzzleId: PuzzleId;
  seed: string;
  recipe: RecipeRef;
  topology: Topology;
  entries: readonly Entry[];
  cells: readonly Cell[];
  clues: readonly ClueSet[];
  provenance: ProvenanceLedger;
  generation: GenerationReceipt;
  quality: QualityReport;
  integrity: IntegrityDigest;
};
```

An `Entry` refers to a stable `LexemeId` and `SenseId`, not only answer text. A
clue refers to that sense and records its mechanism, difficulty estimate,
grounding evidence, generator version, and validation result. Cell and entry
IDs are topology-derived and stable across display modes. No identity depends
on a clue string, date, DOM index, or provider.

`GenerationReceipt` records the model manifest, prompt-template version,
lexicon snapshot, recipe, solver version, seed, restart count, timing, and
validator versions. The same exact result need not be reproducible by future
GPU kernels, but every shipped puzzle is explainable and replayable against its
frozen manifest and inputs.

## Content foundation

### Lexicon layers

The lexicon is an editorial asset with several layers:

1. **Core language**: normalized surface forms, inflections, frequency bands,
   part of speech, locale, and usage flags.
2. **Crossword fill**: short connectors and common crossword vocabulary such as
   EWE, YEW, OLE, EVE, and AWE, with an explicit repetition budget.
3. **Knowledge concepts**: people, places, discoveries, works, species,
   chemical terms, philosophical concepts, and historical events linked to
   stable senses and facts.
4. **Editorial policy**: obscurity, datedness, offensiveness, abbreviation,
   variant spelling, proper-name, brand, politician, and locale flags.
5. **Household overlay**: learned familiarity, recent exposure, aversion, and
   personal exclusions. It never edits the canonical source record.

Candidate source families include WordNet, Wikidata, Wiktionary, and SCOWL.
Each must pass a license and transformation review before adoption. Keep a
machine-readable source ledger containing source version, retrieval date,
license/SPDX identifier, attribution requirements, transformation pipeline,
and the exact records emitted into a release. Do not scrape commercial puzzle
corpora or infer permission from public availability.

Build artifacts should be compact positional indexes, not the raw source dump:

- answer IDs partitioned by grapheme length;
- position/letter bitsets per length;
- prefix indexes for diagnostics and alternate engines;
- scores and policy flags in typed arrays;
- lexeme/sense/fact records loaded lazily;
- integrity hashes and source-ledger references.

All normalization is explicit: Unicode form, punctuation, spaces, diacritics,
rebus policy, locale variants, and display form are separate fields. The fill
form is never reverse-engineered later into a display form.

### The LLM candidate bag

The local model receives a structured, bounded request containing the audience
projection, day recipe, recent-answer exclusions, desired semantic spread, and
theme constraints. It returns arrays rather than prose:

```ts
type CandidateSuggestion = {
  surface: string;
  intendedSense: string;
  associations: readonly string[];
  role: "theme" | "long" | "general" | "glue" | "stretch";
  confidence: number;
};
```

Every suggestion must resolve to an eligible lexeme and sense or be rejected.
Model output expands the search neighborhood; it never inserts a word directly
into the grid. Token generation is deliberately broad and cheap, while the
expensive rigor remains deterministic.

Long, themed, and domain-specific vocabulary may use several bounded model
requests. Each batch receives a deterministic seed and the accepted surfaces
from earlier batches as exclusions, while focus and target answer lengths are
explicit request fields. Batch output still passes through lexicon resolution,
policy checks, and the deterministic fill engine; it is not a second lexicon.

The initial semantic mix for a personalized puzzle is a recipe, not a hidden
recommendation loop:

- 15% direct reinforcement of recently learned material;
- 20% adjacent concepts around demonstrated interests;
- 45% broad language, culture, science, history, and playful word intelligence;
- 15% controlled crossword glue;
- 5% deliberate stretch outside the established profile.

These are starting priors. Offline evaluations and household feedback can
change them. Hard exclusions always win; a narrow interest vector never turns
the puzzle into a chemistry exam.

## Topology before fill

Topology and answer fill are separate problems. Versioned day recipes constrain:

- dimensions and rotational symmetry;
- block density and distribution;
- connected white-cell graph;
- minimum answer length (three by default);
- unchecked-cell and two-letter-entry policy;
- word count and average answer length;
- long-entry/theme positions;
- openness, choke points, and corner isolation;
- permitted special mechanics.

Start with a curated bank of human-reviewed, parameterized 15x15 templates.
This makes the first quality problem difficult but bounded. Add a topology
generator only after the fill engine reliably meets quality and latency gates.
Thursday mechanics and 21x21 Sunday grids are separate capabilities; they are
not accepted because a generic grid happened to fit.

Every topology passes independent invariants before the word solver sees it.
Every accepted template has a stable ID, recipe compatibility list, difficulty
statistics, fill-success history, and test fixtures.

## Fill engine

Implement the first production engine in TypeScript in a dedicated Web Worker.
Use an engine port so Rust/WASM, CP-SAT, or another implementation can be
introduced after evidence, not aspiration.

### Search representation

- one variable per entry slot;
- a candidate bitset for each slot;
- positional letter bitsets for crossing propagation;
- explicit all-different and duplicate-root policies;
- hard constraints separated from quality terms;
- incremental score bounds for branch-and-bound.

### Search strategy

1. Seed slot candidates from the lexicon, recipe, LLM suggestions, audience,
   recent-answer exclusions, and any theme locks.
2. Propagate fixed letters and crossing intersections.
3. Choose the next slot by minimum remaining values, then crossing pressure and
   editorial importance.
4. Order values by least-constraining effect plus a deterministic quality score.
5. Maintain arc consistency/forward checking after assignment.
6. Backtrack with bounded nogood recording and cancellation checks.
7. Use seeded restarts and keep the best complete candidates until the quality
   threshold or resource budget is met.
8. Emit structured progress; never expose partially valid grids as puzzles.

Hard constraints include crossings, answer uniqueness, eligibility policy,
theme locks, topology rules, and banned/recent limits. Soft objectives include
lexical quality, semantic mix, answer familiarity distribution, glue budget,
long-answer interest, abbreviation density, repetition, and estimated crossing
fairness.

The abandoned PuLP experiment's pairwise incompatible-word constraints are not
the production formulation. Keep a small independent Python reference solver
(OR-Tools CP-SAT or straightforward backtracking) for tiny grids and
differential tests. It is a correctness oracle and offline analysis tool, not a
browser dependency.

### Rust/WASM decision gate

Do not begin with a rewrite. A Rust/WASM engine is justified only if the typed
array/bitset TypeScript worker misses an agreed p95 construction budget on the
reference devices after profiling. The port contract, fixtures, and quality
scorer remain unchanged. Benchmark identical seeds and dictionaries, including
WASM startup and transfer cost.

## Clue construction after fill

Answers are frozen before final clues are composed. For each entry the local
model receives the resolved sense, safe facts, crossing context, recipe,
audience familiarity, allowed mechanisms, and nearby clues to avoid repetition.
It returns a ladder:

- `direct`: clear definition or grounded fact;
- `standard`: expected day-level clue;
- `oblique`: misdirection, playful surface, or wordplay;
- `nudge`: an easier alternate used only on request;
- optional explanation/fact card shown after solve.

This lets one excellent fill support different clue difficulty without lying
about the answer. Difficulty is constrained by the day's contract; it does not
silently escalate forever with the user.

### Clue validators

Before a clue enters a manifest, validate:

- exact answer and intended-sense agreement;
- no answer string, trivial morphological leak, enumeration error, or crossing
  leak unless the mechanism explicitly permits it;
- no unsupported proper-name or factual assertion;
- no duplicate surface or excessive mechanism repetition nearby;
- punctuation, abbreviation, tense, plural, and locale fairness;
- day-appropriate obscurity and clue-language difficulty;
- safety and household exclusion policy;
- a unique or editorially defensible intended answer in context.

Factual clues may only use facts carried in the provenance ledger. The LLM may
paraphrase them but may not create new evidence. Definition and wordplay clues
still receive sense and leakage checks.

## User model

Do not collapse a person into one embedding. Maintain a composite,
human-readable local profile:

```ts
type PlayerProfile = {
  explicitPreferences: PreferencePolicy;
  semanticInterests: SparseConceptVector;
  lexicalFamiliarity: FamiliarityModel;
  clueMechanisms: MechanismSkillModel;
  localeTolerance: LocalePolicy;
  solvePace: PaceByContext;
  assistancePatterns: AssistanceModel;
  noveltyPreference: number;
  gridPreferences: GridPreferenceModel;
};
```

Events include clue focus, first entry, edits, solve, crossings present at
solve, active duration, revisit, nudge, check, reveal, pause, abandonment, and
completion. Record stable IDs and monotonic timing; never infer knowledge from
wall time alone. Aggregate locally and allow raw-event expiration after the
profile has been rebuilt.

Update familiarity conservatively. Fast solve with few crossings is stronger
evidence than filling the last crossing letter; a reveal is exposure, not
mastery. Preserve uncertainty and cap the impact of any one puzzle. Users can
inspect examples behind an inferred tendency and correct or reset it.

Household puzzles combine named profiles through an explicit policy. Default
cooperative blending takes the union of interests, respects either player's
hard exclusions, and targets a challenge range both can enter. Never merge raw
histories into an irreversible anonymous vector.

## Required local-model runtime

Use one model broker and one long-lived generation worker. Pin a model manifest
with model ID, quantization, shards, expected hashes, runtime version, minimum
capabilities, memory estimate, and prompt/evaluation versions. Do not hard-code
the current fashionable model throughout the application.

The first-run gate checks:

1. WebGPU/runtime compatibility;
2. free storage and quota behavior;
3. model and shard integrity;
4. structured JSON output adherence;
5. a small candidate/sense/clue evaluation;
6. cancellation, unload, and recovery behavior.

Model weights are downloaded once from an explicitly disclosed host and cached
locally. Prompts, solve events, profiles, and generated content never leave the
device. There is no transparent cloud-inference fallback. On an unsupported
device, explain what failed and preserve export/import options; do not pretend
that an unrelated deterministic clue bank is the same product.

Generation is cancellable and power-aware. It runs on explicit request or when
the configured queue is low and conditions permit. It never begins while the
player is typing, never occupies the service worker, and exposes model-loaded,
generating, validating, cooling-down, and unloaded states.

## Construction quality gates

A puzzle is publishable to the local queue only if all of these pass:

- topology and crossing invariants;
- every answer has an eligible lexeme/sense and source record;
- every clue passes its mechanism and grounding validators;
- no answer, clue, or fact violates household policy;
- day-recipe thresholds and a global minimum quality score pass;
- seeded manifest, hashes, and generation receipt are complete;
- independent solve/serialize/deserialize validation passes;
- no duplicate against the recent manifest window;
- construction fits the current resource budget or is labeled an offline batch;
- required human-editor gates pass for any recipe not yet graduated.

Failed candidates are diagnostic artifacts, not playable puzzles. Keep bounded,
privacy-safe failure summaries for tuning; do not retain entire prompt histories
by default.

## Graduation path

1. **Laboratory**: 5x5 and 7x7 differential fixtures, licensed mini lexicon,
   mandatory local model, reproducible manifests.
2. **Monday alpha**: curated 15x15 templates, human-reviewed local puzzles,
   fill and clue scorecards.
3. **Monday/Tuesday household beta**: generated queue with explicit feedback,
   event-based profiles, import/export, no NYT dependence for those days.
4. **Wednesday/Thursday**: broader mechanisms and special-cell schema after
   their own evaluation suites.
5. **Friday/Saturday**: open themeless quality after long-fill and crossing
   fairness targets are proven.
6. **Sunday**: 21x21 only after quality, memory, and latency gates pass on real
   devices.

The legacy source remains a local continuity bridge during these gates. It is
never part of the public artifact and never supplies training or evaluation
content for the original constructor.
