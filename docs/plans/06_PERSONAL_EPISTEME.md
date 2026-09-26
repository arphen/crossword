# The personal crossword: implementation plan

**Status:** revised implementation plan for owner review; the local Ollama/native runtime direction is accepted by owner instruction. Application implementation has not begun in this planning task.  
**Prepared and revised:** 25 September 2026.  
**Product repository:** `crossword`. **Construction repository:** `../crossword-generator`.  
**Scope:** the complete path from a player's first puzzle to a durable, expressive personal vocabulary, including construction, inference, learning, interaction, runtime, evaluation, and delivery.

**Review map:** [nonverbal opening](#initial-calibration-five-short-movements) · [weekday recipes](#weekday-difficulty-is-an-editorial-contract) · [clue language](#a-language-the-player-can-learn-and-trust) · [experience](#3-the-experience-from-the-first-game-onward) · [the prose profile and open semantic space](#4-episteme-three-things-that-must-remain-distinct) · [game-to-profile updates](#7-turning-a-game-into-an-episteme-update) · [reflection cards](#9-reflection-cards-desire-expressed-indirectly) · [crossing algorithm](#13-crossing-scaffolding-the-central-construction-algorithm) · [Gemma/Qwen and runtime](#17-qwen-gemma-and-the-actual-runtime-decision) · [execution backlog](#21-execution-sequence-and-bounded-work-packages) · [review decisions](#23-risks-decisions-for-review-and-chosen-defaults).

## 1. The product we are making

Make a crossword that gradually acquires the player's language while continuing to give them somewhere new to go.

The immediate promise is modest and concrete: **“This puzzle has ways in for me; the things I do not know become things I can discover.”** Over time, that can become a more unusual experience: words, images, subjects, and forms of wit recur in combinations that feel personally resonant. The player recognizes something of themselves, encounters something unfamiliar, and gets to decide whether to follow it.

The “void that stares back” is a useful artistic direction. Translate it into an instrument for association and discovery: a puzzle can reflect a fascination without explaining the person to themselves. The model supplies surprising connections; the player supplies their significance. Entertainment and education remain satisfying on their own. A player who only wants clever, fair crosswords should never have to participate in a personality exercise.

The aesthetic arc begins with signs before they have a task: an object, a mark, a color, an unexplained pair. Later, a bracket, a tense, or a crossing becomes something the player knows how to act on. Familiarity makes a new kind of strangeness available. Preserve the interval of uncertainty that makes discovery satisfying; the aim is worthwhile resistance followed by understanding, with the player choosing how much challenge to invite.

The distinctive unit of design is **the breakthrough**:

1. I recognize something and enter an answer.
2. That answer makes another clue more tractable.
3. A previously opaque pattern becomes a word, name, or idea.
4. I understand why it fits.
5. I want to see what the next crossing opens.

“One more” should emerge from these local discoveries and from worthwhile next puzzles. Completion rate alone is insufficient: a trivial puzzle and a puzzle solved by revealing every answer can both score 100%.

### Non-negotiable product contracts

- The grid, answer senses, and clue bundle are frozen when a session starts. Assistance selects prepared hints; it does not secretly replace the puzzle.
- Every unusual answer has an editorial reason to exist and a credible route to discovery for the intended player.
- Knowing a word, liking its subject, liking its clue, and wanting more of it are separate signals.
- The profile can contain prose and open-ended associations. Claims about the player retain evidence, uncertainty, scope, and an undo path.
- The LLM may invent associations and original language. It may not invent the facts that make a clue correct.
- Personalization changes answers, senses, clue surfaces, difficulty, recurrence, and theme selection. Merely inserting favorite topics into generic clues is insufficient.
- The default experience runs on the player’s local application host, supports cached solving after preparation, and remains complete without reflection cards.
- Weekday names are selectable editorial contracts: Wednesday must feel like Wednesday; Thursday must offer a fair mechanical or thematic discovery. A full-size crossword remains the core experience. Small test grids and optional short sessions support it; they do not replace the ambition.

## 2. What exists, and what this plan changes

The following is based on source inspected on 25 September, rather than assuming earlier planning documents describe shipped behavior.

| Area                   | Observed implementation                                                                                                                          | Consequence                                                                                                                            |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| Active UI              | `apps/react/src/main.jsx` mounts desktop/mobile behavior through a compatibility controller.                                                     | Preserve its solving behavior and distinctive Across/grid/Down composition while moving session truth into typed use cases.            |
| Previous static target | ADR 0001 specified `apps/web`, which is not an active source workspace.                                                                          | Superseded by ADR 0003: extend `apps/react`; no static-workspace restoration is required.                                              |
| Puzzle domain          | `packages/domain/src/puzzle.ts` has immutable-style values, clue variants, provenance, quality, and integrity fields; document schema is v1.     | Extend with sense identities, assistance provenance, and generation receipts through explicit schema migration.                        |
| Session domain         | `packages/domain/src/session.ts` records entry, clear, check, reveal, nudge, pause, and completion events.                                       | This is a useful starting point, but lacks the event detail required to infer who supplied a crossing or exactly what a check exposed. |
| Persistence            | Browser IndexedDB v3 and Flask/SQLite completion records already exist, but neither provides the new evidence/profile/job system.                | Use SQLite for canonical accepted state and IndexedDB for an offline journal/outbox; define migration and reconciliation explicitly.   |
| App integration        | Generator archives are versioned `file:` dependencies; original generation is not wired into the current React UI.                               | Deliver a bundling adapter and contracts; do not introduce a sibling-directory runtime dependency.                                     |
| Portable generator     | Three packages expose a TypeScript CSP, model broker/WebLLM adapter, and orchestration.                                                          | Keep deterministic construction independent of UI and model runtime.                                                                   |
| Full-size lab          | `apps/lab/server.ts` invokes native Rust `xfill` and local Ollama through Vite middleware.                                                       | Reuse its engine and model paths through an extracted Node runtime; add durable jobs and a product API.                                |
| Current model evidence | The lab's construction plan records a successful `qwen3.8:27b` clue draft.                                                                       | This is a smoke result, not a comparative writing-quality or personalization evaluation.                                               |
| Runtime                | **Accepted:** existing React/Flask app, canonical host SQLite, durable worker, Ollama and native `xfill`.                                        | Owner instruction supersedes browser-only requirements; later ports use preserved contracts.                                           |
| Source ledger          | The product's older lexicon ledger still marks one source `NOASSERTION`; the generator lab documents a separately licensed Crossword Nexus list. | Reconcile exact source artifacts before using them in a release. A filename or previous fill does not establish source eligibility.    |

Both checkouts contain unrelated work in progress. Implementation must record the starting state and preserve it. This document does not authorize resetting either checkout.

### Relationship to existing plans

The owner has explicitly withdrawn the frontend-only requirement. [ADR 0003](../adr/0003-local-ollama-native-runtime.md) supersedes the browser-only and static-workspace decisions. This plan now targets the existing React/Flask application, a durable local job worker, Ollama, and native `xfill`. Keep portable domain contracts so later ports are possible; do not make a future browser port a prerequisite for excellent puzzles now.

This revision also makes nonverbal initial calibration, selectable weekday recipes, and a rigorous learned clue language first-class deliverables. The remaining detailed design is reviewable; the runtime change does not need to be re-approved. Older plans remain historical/contextual references where they do not conflict with this plan or ADR 0003.

## 3. The experience, from the first game onward

### First visit: an encounter before an interview

The first screen is an unusual small arrangement of things. No interest checklist, personality categories, opening question about desire, or mandatory text field. A quiet instruction such as **“Take one.”** is sufficient. The player can also pass or go straight to a puzzle.

The setup should move from visual encounter, to relation, to a small amount of language, and finally to crossword play. It establishes a provisional associative starting point while separately establishing the practical information needed to play. It does not claim that a color or object can reveal someone's unconscious, knowledge, or identity.

The concrete calibration flow below is part of the first playable product. Model/runtime readiness can be checked quietly by the host during it. If a model is missing, the player can complete calibration and play a reviewed sample while the host setup surface explains the dependency. Do not interrupt the opening with GPU terminology or make the first aesthetic experience depend on a live model call.

### During a puzzle

- Preserve fast keyboard entry, crossing navigation, clue focus, linked answer patterns, mobile input, and resumability.
- Give visible progress through the grid rather than an incessant correctness signal. Auto-check is optional and its feedback is logged.
- Start with several likely entry points across the whole grid. A player should not need to discover the constructor's single intended first answer.
- Provide an assistance ladder: **another way to read the clue → a grounded context hint → a useful crossing to try → reveal a letter → reveal the answer**. Each step is available on request and recorded separately.
- A suggested crossing highlights a clue the player can solve; it does not silently insert the target letter.
- Allow explanation and “save this word” after an answer is confirmed or at the end. Do not spoil another unsolved answer in an explanation.
- Offer a quiet “help me find a way in” action for a stuck region. Do not automatically interrupt because a timer guessed that someone was frustrated.
- A player can pause, stop, or finish with assistance without losing the value of the session. Completion copy distinguishes finished, assisted, and revealed without moral ranking.

### After a game

The closing screen has three independent layers:

1. **Satisfaction:** the completed grid and a short, concrete observation: “You opened the northeast corner through three crossings.” No invented emotion or achievement.
2. **Discovery:** two or three optional word cards, chosen for actual novelty, requested interest, or future review. Each has a concise explanation and source access.
3. **Resonance:** up to three optional statements to keep, turn away from, or pass. Skipping closes the screen immediately; it does not reduce future quality or count as dislike.

Below this, offer a next puzzle, a saved-word view, or a natural stopping point. The next puzzle can carry one small connection forward, but should not be an endless re-skin of the last theme.

### Over several weeks

The player sees familiar words become easy, obscure filler become less frequent, enjoyable mechanisms recur, unwanted local trivia diminish, and new interests form bridges into new material. Repeated answers return through different senses or clues where appropriate. Learning mode deliberately revisits the same sense when retrieval is the goal.

An optional **“Your words”** view shows a readable portrait, recent changes, saved discoveries, and emerging associations. Every inferred preference has “why this appeared,” “less/more,” and “forget this.” The player can edit the portrait in ordinary prose. Its function is to steer future puzzles, not certify who the person is.

### Product modes

| Mode              | Principal objective                             | Default behavior                                                                   |
| ----------------- | ----------------------------------------------- | ---------------------------------------------------------------------------------- |
| Play              | Enjoyable, varied solving                       | Broad vocabulary, a few personal threads, restrained repetition.                   |
| Learn             | Durable acquisition in a chosen language/domain | Explicit learning goals, due-word budget, varied retrieval, useful explanations.   |
| Explore           | Serendipity and personal resonance              | More adjacent themes and optional associative cards, with the same fairness gates. |
| Guest / no memory | A good puzzle without a durable portrait        | Session data supports saving the game; no lasting personalization update.          |

These are adjustable modes over one engine. Monday through Saturday select the editorial challenge independently; Sunday selects a larger midweek-level themed experience when supported. Do not equate learning with easy, exploration with hard, or high ability with an appetite for obscurity.

### Initial calibration: five short movements

**Target duration:** 45–90 seconds for the associative opening; an optional practice fragment adds about two minutes. The player controls pace. There is no countdown and no interpretation of hesitation as a psychological signal.

| Movement                     | What the player sees/does                                                                                                                                       | What the system can legitimately retain                                                               |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| 1. Encounter                 | Six isolated, carefully composed objects/signs on a quiet field. Take one, pass, or enter the puzzle.                                                           | A preference for this presented stimulus over this offered set, under this presentation.              |
| 2. Relation                  | The selected object stays. Choose or place another beside it from four new objects.                                                                             | An authored relation between two chosen stimuli; its meaning remains open.                            |
| 3. Variation                 | A small visual transformation or contrast: the same form in different material/color, or a related object with a different form. Pick one or keep the original. | Weak evidence about this visual dimension when the comparison actually controls other dimensions.     |
| 4. A first trace of language | A small mixed spread such as a word, a number, a symbol and a drawn object. Keep one or two with the existing pair.                                             | Chosen representations and possible associations; still not mastery or a declared subject preference. |
| 5. Enter the crossword       | Select the visible weekday difficulty and puzzle language. Optionally try four crossing clues that introduce the puzzle's language.                             | Explicit challenge/language choice; actual solve evidence if the practice fragment is attempted.      |

A first scene might place a knotted red thread, a smooth dark stone, a transparent blue cube, a little brass key, an open incomplete circle, and `0` in a balanced composition. This is an authored design proposal. It is not a symbolic codebook in which the key means ambition and the stone means introversion.

After the thread is selected, the second spread might include a tuning fork, a folded paper map, two offset dots, and a white seed. A thread/fork pair could prompt candidate paths through vibration, tension, strings, weaving, and continuity. Those are several possibilities to try, not a conclusion about the person. If the player later chooses a number or an unexpectedly soft shape, preserve the contrast rather than forcing consistency.

The transition into words should feel like the same space acquiring names. Objects can settle into a small constellation; one or two become unobtrusive anchors for the first puzzle's theme or long entries. The first puzzle should not announce “you chose a key, so here is a locksmith puzzle.” A subtle connection is sufficient.

### Authored stimulus bank and presentation controls

Start with 48–72 reviewed stimuli across objects, abstract forms, textures/materials, colors, numerals, single words, and typographic marks. Use original/licensed raster assets or deliberately authored SVGs, with a coherent visual language. Do not generate arbitrary images during onboarding or make model-generated image interpretations authoritative.

Each `StimulusV1` stores stable ID/version, asset hash, kind, neutral visual description, intrinsic accessible label, language when relevant, curated descriptive facets, several possible association seeds, provenance, salience group, contrast family, and permitted transformations. Descriptive facets are open vocabulary; they are not personality dimensions. A first release can use a small authored library of forms and objects while retaining an extensible format.

Match display area, background, approximate visual weight and interaction affordance across options. Randomize position with a reproducible seed; record the offered alternatives and positions. Do not let a large glowing object “win” and call that an enduring preference. Color comparisons should preserve form; form comparisons should preserve color/material where possible. Mixed spreads intentionally remain ambiguous and receive lower evidence weight.

Every interaction works by keyboard/touch without drag. Provide neutral alt text, reduced motion, a monochrome/shape alternative, and a text-accessible equivalent without evocative interpretive labels. Record presentation mode so a choice of an alt-text description is not analyzed as a visual color choice. Audio is absent by default. Accessibility choices never become personality evidence.

### Adaptive selection without a hidden personality test

Use a constrained, seeded selector over the authored bank. Movement 1 is broadly varied. Later movements mix one continuity option, one visual contrast, one remote association, and one unrelated possibility. Keep all options equally available; include a pass/skip on every screen. Selecting one does not count as rejecting all the others.

A local LLM can propose a ranked shortlist for subsequent movements in parallel with interaction, using only asset descriptors and accumulated selections. The selector checks asset IDs, repetition, presentation balance, and branch limits. If a response is late, use a prepared next spread. Never make someone wait for the app to “understand” their last click.

Do not keep probing until a player fits a confident cluster. Stop at the movement limit or on “Start puzzle.” Calibration can resume later by invitation, and a player can revisit their first constellation. Do not hide a psychological assessment behind the visual form: its actual job is to choose worthwhile first directions for content.

### Calibration data and the first episteme

`CalibrationSessionV1` stores `calibrationId`, profile/guest scope, bank/selector versions, presentation mode, RNG seed, current movement, ordered observations, selected challenge/language, and completion/skip state. `CalibrationObservation` stores trial ID, presented stimulus versions/positions, chosen IDs or pass, relation action, and any reversal. Record elapsed time for usability/debugging only; exclude it from preference inference.

The compiler creates three outputs:

1. **Observed traces:** exact selections and relations, retained without interpretation.
2. **Tentative association seeds:** several competing readings tied to those traces, bounded in weight and lifetime.
3. **Practical setup:** the explicit weekday/language choices and optional practice observations, kept independent of the visual traces.

An LLM receives neutral descriptors and relations and returns at most 12 candidate semantic paths, each with observation IDs, a short connection, and a statement of what remains ambiguous. Validate IDs and scope using the same evidence system as later updates. Store these as `calibration-proposal` associations, not `explicit` taste claims. Extend the association origin union accordingly. Do not update lexical knowledge from visual/number selections.

Initial influence: at most 20% of the first puzzle's semantic-selection weight may come from these seeds, usually one long-answer/theme direction plus a few adjacent entries. The remaining material stays broadly accessible and varied. Each ambiguous trace contributes at most `0.05` to a tentative facet, and calibration contributes no more than `0.15` per facet overall. These scores tune exploration, not a diagnosis or a permanent category.

Unendorsed initial hypotheses expire after five completed puzzles or 14 days. Later genuine responses can create evidence-backed claims. The player can delete/restart calibration without resetting learned vocabulary. If the whole setup is skipped, use broad content, the player's selected weekday, and unknown familiarity priors; the application still works fully.

Do not write a 3,000-word portrait from six clicks. The initial record may be a 100–250-word private generation brief: “Selected thread with fork; possible bridge through tension/sound; other readings open. Chose Wednesday. Familiarity unknown.” Its user-facing form is the constellation and optional “Your first traces,” without an unsolicited psychological interpretation.

### Practical calibration through play

The weekday selector appears after the opening, remains available immediately via “Start puzzle,” and is always visible before generating. Default recommendation is Monday when no choice exists; retain any explicit Wednesday/Thursday/etc. choice. Do not infer difficulty preference, intelligence, or language knowledge from the objects.

Offer a short, original connected practice fragment with a straightforward fill, a grammatical agreement clue, a quoted utterance, and a signaled pun. It is optional and labeled a short introduction; experienced solvers can skip it. Teach one convention through a successful crossing and an optional explanation, then reuse that convention later with a different answer. Do not turn the opening into a disguised timed exam or silently downgrade the selected weekday after a mistake.

This separates three kinds of calibration: associative directions from the opening, crossword-convention familiarity from actual play, and the challenge the player explicitly wants. The app can support an unfamiliar convention while preserving the chosen Wednesday or Thursday contract.

## 4. Episteme: three things that must remain distinct

Use “episteme” in the product vision, but separate three concrete stores in code:

1. **World lexicon:** admissible words, senses, names, phrases, facts, forms, and relationships. This is the source material from which puzzles can be constructed.
2. **Player memory:** what the player has expressed, encountered, retrieved, requested, avoided, or left unresolved.
3. **Associative field:** model-generated possibilities extending from that memory into neighboring words, images, and themes.

The third is where the freer, literary part of the idea belongs. It can be expansive and surprising because its contents are candidates, not declarations of fact about the person.

### Can the profile be a few thousand words of LLM prose?

Yes—as a readable portrait and a generation input. It should not be the only state. A repeatedly rewritten paragraph loses negative preferences, exact learning history, the distinction between evidence and fantasy, and the ability to explain a change. It also tends to turn its own earlier inventions into apparent evidence.

Use a layered profile instead:

| Layer                 | Representation                                                                | Authority                                                        |
| --------------------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Explicit instructions | Versioned user-authored text plus structured policies                         | Highest: exclusions, languages, current goals, user corrections. |
| Evidence ledger       | Session summaries, card choices, saves, corrections, with stable IDs          | Source of truth for observed behavior and declarations.          |
| Knowledge memory      | Per sense/fact/retrieval-task statistics and uncertainty                      | Estimates retrieval under specified conditions.                  |
| Taste claims          | Open-vocabulary concepts, relations, stance, context, evidence links          | Hypotheses or explicit preferences, never assumed universal.     |
| Narrative portrait    | Approximately 1,500–3,000 words once enough evidence exists                   | A readable, regenerable interpretation; initially much shorter.  |
| Associative field     | Up to 2,000–5,000 active terms/phrases with weighted edges                    | A search and creativity cache, not knowledge or identity.        |
| Puzzle projection     | A bounded brief of roughly 800–1,500 tokens plus selected structured evidence | The task-specific material actually sent to the constructor.     |

The numerical budgets are starting implementation limits, not a claim that a particular word count can capture a person. Never pad an early portrait to fill a quota. Store old snapshots and compact evidence separately; do not stuff all historical text into every prompt.

### A vector space without a fixed personality taxonomy

The semantic vocabulary is open. Concepts can be “rain on railway windows,” “not another senator,” “etymology as a joke,” or a named musical work. Each gets a stable ID, language, text label, optional external concept link, and relations to other concepts. Merge synonyms cautiously; preserve polysemy and disputed merges.

Use three complementary representations:

- Sparse, growing concept weights for explicit policies and explainable retrieval.
- A graph for relations such as related-to, wants-to-learn, contrasts-with, evokes, and temporarily-avoids.
- Optional embeddings for nearest-neighbor retrieval and diversity. An embedding has a fixed numeric dimension for a given encoder; an open semantic space does not require changing that dimension every time a new interest appears.

Pin the embedding model/version. Never compare vectors from different encoders. Re-embedding is a rebuildable cache migration. Begin with lexical search, concept links, and sparse weights; add embeddings when a measured retrieval failure justifies their memory and runtime cost. The portrait works without them.

### Example of a useful portrait

> Often enjoys the point where ordinary objects acquire a second meaning. Has asked for fewer clues that require US political officeholders and has saved several words about sound and machines. Recent success on geography clues came with considerable crossing support; familiarity is still uncertain. The current language-learning goal is German everyday vocabulary. “Maps are more interesting when they stop being useful” resonated once; try a small bridge toward imagined places, without treating it as a settled preference. Keep botanical material broad until there is more evidence.

This describes observations, preferences, uncertainty, and a creative possibility. It does not infer nationality, religious identity, political ideology, or hidden psychological motives from crossword performance.

## 5. Domain contracts and identities

Introduce versioned schemas with runtime validators and bounded sizes before building inference. The names below are proposed public contracts; the implementation should export corresponding TypeScript types and JSON Schemas. Strings representing IDs are branded in TypeScript and validated at boundaries.

### Knowledge content

```ts
type Lexeme = {
  lexemeId: string;
  language: string; // BCP 47
  lemma: string;
  displayForms: string[];
  fillForms: FillForm[]; // token sequence + normalization policy
  senseIds: string[];
  sourceIds: string[];
  editorial: {
    frequencyBand: string;
    properName: boolean;
    abbreviation: boolean;
    glueClass?: string;
    localeTags: string[];
    topicIds: string[];
    publishable: boolean;
  };
};

type Sense = {
  senseId: string;
  lexemeId: string;
  gloss: string;
  partOfSpeech?: string;
  conceptIds: string[];
  factIds: string[];
  morphology?: Record<string, string>;
  sourceIds: string[];
};

type Fact = {
  factId: string;
  subjectId: string;
  predicate: string;
  object: string;
  qualifiers: Record<string, string>;
  validFrom?: string;
  validUntil?: string;
  verifiedAt: string;
  sourceIds: string[];
  review: 'verified' | 'quarantined' | 'retired';
};
```

`FillForm` separates displayed spelling, canonical token sequence, optional alternate input mappings, and the versioned language policy. A sense can admit several surface forms, but a published entry pins one form. Knowledge of an answer's spelling is not automatically knowledge of the particular biographical fact used to clue it.

### Player claims and associative candidates

```ts
type ProfileClaim = {
  claimId: string;
  text: string;
  conceptIds: string[];
  kind: 'taste' | 'goal' | 'style' | 'context';
  stance: 'seek' | 'avoid' | 'ambivalent';
  authority: 'explicit' | 'inferred';
  strength: number; // [0, 1], policy weight
  confidence: number; // [0, 1], evidence adequacy; not LLM certainty
  scope: { mode?: string; language?: string; expiresAt?: string };
  evidenceIds: string[];
  counterEvidenceIds: string[];
  lockedByUser: boolean;
  createdAt: string;
  updatedAt: string;
};

type Association = {
  associationId: string;
  phrase: string;
  language: string;
  parentIds: string[]; // claims/concepts, not fabricated observations
  relation: 'adjacent' | 'contrast' | 'metaphor' | 'sound' | 'etymology';
  origin: 'model-proposal' | 'calibration-proposal';
  explanation: string;
  evidenceStatus: 'untested' | 'responded-to';
  explorationWeight: number;
  expiresAfterPuzzle: number;
};
```

Generated associations do not become `ProfileClaim` evidence merely because they appeared in a puzzle. A subsequent player response can create a new evidence record pointing to both the presented stimulus and the response.

### Profile, session, and analysis envelopes

`PlayerProfileV1` contains `profileId`, `revision`, explicit policies, claim IDs, learning-goal IDs, narrative snapshot reference, association snapshot reference, reducer versions, and evidence watermark. Keep large histories in separate stores.

`SolveSessionV2` contains an independent `sessionId`, optional `profileId`, immutable puzzle/clue-bundle hash, input-policy version, mode, accessibility/assistance settings, current state, last committed event sequence, and timing segments. Different people and repeat attempts can use the same puzzle without overwriting one another.

`SessionAnalysisV1` contains one `EntryObservation` per encountered entry, a puzzle-experience summary, quality complaints, unresolved ambiguities, input event range/hash, analysis version, and a list of justified profile-update candidates. Every observation carries missing-data flags.

`ProfileUpdateV1` contains the base revision, immutable input evidence IDs/hash, bounded proposed operations, rejected operations/reasons, model/prompt versions, resulting revision, and a timestamp. It is a transaction record, not just the new portrait.

### Puzzle schema migration

Create `PuzzleDocumentV2` with:

- `lexemeId`, `senseId`, and optional `retrievalTaskId` on entries;
- distinct `clueVariantId`, `variantRole`, `primaryFamily`, grammar and surface-span fields, plus a separate puzzle-level mechanic reference;
- grounded fact/source references and approved assistance variants;
- cell token sequences, decorations, optional rebus/symbol reading rules, and a language/input policy; weekday recipe and clue-grammar versions;
- profile projection revision/hash in the **private generation receipt**;
- engine/model artifact digests, validator versions, recipe version, and construction seed;
- a crossing-support report with uncertainty and a final quality verdict.

Exporting a puzzle for another person strips private profile material and evidence IDs. Public puzzle content retains content provenance and a sanitized generation receipt. Hashes are integrity checks, not authentication or proof that a claim is true.

For each special entry store its underlying lexical answer, entered token sequence, mechanic reference and direction-specific reading if supported. Ordinary entries use the identity mapping. Length indexes use cell-token length for construction and lexical/grapheme length for content; do not confuse the two. Rebus hints/reveals must record whether they disclosed one token, the entire cell, or the mechanism.

Read v1 documents indefinitely. A v1 import can gain an analysis sidecar but must not invent missing senses or rewrite its original hash. Newly constructed puzzles use v2. The continuity archive gets a new outer version when it gains typed profiles and v2 events.

## 6. Gameplay telemetry: what happened, under which conditions

Capture semantic actions at the application command boundary. Do not build a second model of truth by scraping DOM changes. The same event contract covers keyboard, touch, paste, input method composition, hints, and later household play.

### Event envelope

Every new event contains:

```ts
type EventEnvelope = {
  schemaVersion: 2;
  eventId: string; // UUID, deduplication key
  sessionId: string;
  profileId?: string;
  segmentId: string; // one monotonic clock origin
  seq: number; // strictly increasing within the session writer
  elapsedMs: number; // performance-clock delta within segment
  recordedAt: string; // wall time, for display/day scheduling only
  puzzleHash: string;
  type: string; // discriminated payload union in schema
  payload: unknown;
};
```

`unknown` above is an envelope placeholder, not permission to persist arbitrary objects. Each event type has an exact payload schema, length limits, allowed IDs, and rejection behavior. Never subtract `performance.now()` values from separate page loads.

| Event                                          | Required payload / meaning                                                                                          |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `session-started`, `session-resumed`           | Model/profile/recipe refs, initial snapshot ref; resumed segments identify clock discontinuity.                     |
| `entry-focused`                                | Entry, variant, input direction, reason (`pointer`, `keyboard`, `programmatic`). Exposure is weaker than attention. |
| `cell-written`, `cell-cleared`                 | Cell, before/after canonical token, active entry, action ID, input source. Preserve the old value for replay.       |
| `batch-entered`                                | Ordered edits from paste/IME and a shared action ID; do not simulate independent letter deliberations.              |
| `check-requested` / `check-result-shown`       | Scope, exact cells evaluated, values at check, incorrect/blank/correct classifications actually displayed.          |
| `hint-shown`                                   | Entry, variant/hint ID, assistance tier, affected cells if any.                                                     |
| `answer-revealed`                              | Exact cells/tokens disclosed, previous values, scope.                                                               |
| `visibility-changed`, `paused`, `resumed`      | Pause reason and segment timing.                                                                                    |
| `entry-confirmed`                              | Derived from state; record confirmation mechanism without treating it as a player retrieval.                        |
| `session-finished`, `session-ended`            | Completion/stop reason, state hash, last sequence. Unfinished is not “disliked.”                                    |
| `word-saved`, `clue-rated`, `issue-reported`   | Explicit object and response; separate praise of subject, clue, and explanation.                                    |
| `reflection-presented`, `reflection-responded` | Card ID/version, display order, text hash, response, mapping version, undo linkage.                                 |

No external application activity, background keystrokes, or pointer trails are needed. Store only this application's puzzle actions. Imported/shared grids without attributable entry actions cannot provide equivalent mastery evidence.

### Reconstructing a retrieval attempt

An attempt starts when a clue is deliberately focused and the player begins engaging with its entry. It may span revisits. At each write, preserve:

- the visible pattern before the action;
- which tokens were entered while another entry was active;
- which tokens were revealed or correctness-confirmed;
- which clue/hint variants have already been shown;
- any earlier wrong attempts and subsequent check feedback;
- focus intervals and whether attention was interrupted.

Crossing tokens are **available pattern support**, even when typed by the same player. Their origin helps distinguish solving the active clue from receiving an already-complete answer through other entries. A word completed entirely by crossings is exposure, not independent retrieval of its clue.

The reducer may compare against the solution privately. This must not make undisclosed correctness visible in the UI or imply the player knew the letter was correct. Keep `actuallyCorrect` separate from `correctnessShown`.

### Timing interpretation

Accumulate focus time only while the app is visible and unpaused. Keep wall duration, observable focus duration, and uncertain idle duration separate. After 90 seconds without interaction, mark the interval uncertain; do not assume the player stopped thinking. Use a sensitivity check at 30/90/180 seconds during analysis research. Timing is a weak covariate and never the sole basis for a knowledge or preference update.

Do not assign negative evidence to unfocused entries. A navigation change, interruption, unfamiliar keyboard, typo, or accessibility setting can explain delay. Repeated wrong guesses followed by revealing are still useful exposure, not proof of low general ability.

### Persistence and delivery

The command reducer produces new state and events together. Persist event batches and the corresponding checkpoint in one IndexedDB transaction; mark the sequence locally durable only when committed; canonical host acknowledgment is separate, as specified in section 16. Buffer small navigation-only batches, but commit meaningful edits promptly. A browser crash can still lose the last uncommitted action; surface storage failure and recover from the last durable sequence without manufacturing events.

Use a host-issued writer lease per session with a fencing token; the browser also coordinates tabs locally. A second tab is read-only or explicitly takes over. Offline conflicting edits remain a recoverable branch, as specified in section 16. BroadcastChannel conveys notifications; it is not the source of truth. Deduplicate by `eventId` and `(sessionId, seq)`. Duplicate completion events must not apply a profile update twice.

## 7. Turning a game into an episteme update

Separate a deterministic analysis pass from model interpretation.

```text
committed session events + frozen puzzle + settings
    -> deterministic replay and attempt extraction
    -> conservative knowledge/assistance observations
    -> compact evidence bundle
    -> LLM proposes taste/portrait changes and possible associations
    -> schema/evidence/policy validator
    -> atomic profile revision and human-readable change record
```

### Knowledge reducer v1

Maintain retrieval evidence per `(sense or fact, task direction, language, clue family)`. Store answer-spelling exposure separately. Track support fraction, assistance tier, independent successes, supported successes, failed engaged attempts, last exposure, and last independent retrieval.

Use an explicit provisional evidence table before fitting a sophisticated model:

| Observation                                                                              | Initial update                                                                  |
| ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Correct entry, no reveal/check/hint, at most 20% prefilled, nontrivial player completion | Independent retrieval success, weight 1.0.                                      |
| Correct with 20–60% prefilled, no explicit answer disclosure                             | Supported retrieval success, weight 0.35; do not call it mastery.               |
| More than 60% prefilled, answer completed by crossings, or answer revealed               | Exposure only; zero independent-success weight.                                 |
| Wrong engaged attempt followed by relevant check/reveal                                  | Failure evidence at most 0.5, conditional on clue validity and input quality.   |
| Untouched/unfocused entry, timeout, ambiguous interruption, imported completion          | No knowledge update.                                                            |
| Confirmed bad/ambiguous clue                                                             | Quarantine its learning observations until reviewed; repair the content record. |

These thresholds are hypotheses, versioned as `knowledge-reducer-v1`, and tested against hand-labeled histories. A four-letter answer with one supplied letter can remain very difficult; the percentage rule is only an initial coarse feature. The crossing model in section 13 uses actual letter positions and candidate uncertainty.

For a simple estimator, keep separate Beta-style weighted success/failure counts for independent retrieval, with a conservative prior (initially 1,1) and a distinct supported-retrieval channel. Do not pool them into a confident mastery score. Return a mean, interval, evidence count, and `insufficient-evidence` flag. Use population/editorial priors when local data is sparse; never present initial estimates as calibrated probabilities.

Cap each item at one independent success and one bounded failure contribution per session. Repeated check-and-guess cycles must not generate dozens of learning trials. Corrections and replays recompute from source evidence, not from previously updated counts.

### Preference reducer v1

- An explicit “fewer clues about US officeholders” takes immediate effect at that scope.
- A saved word or positive subject rating is a moderate preference signal.
- Correctness and speed have **zero direct taste weight** in v1. They change scaffolding and familiarity, not what someone supposedly enjoys.
- A rejected reflection card changes only its predeclared narrow facets. It does not imply agreement with the opposite statement.
- One encounter cannot establish a broad dislike of a region, culture, or field.
- New explicit corrections override older inference. Conflicting explicit statements remain time/context scoped or are shown for editing; the LLM must not arbitrarily pick one.

Keep factual competence, aesthetic taste, desired learning, and current appetite separate. A person can know a great deal about politics and want none of it tonight; another can know little astronomy and want much more.

Implement these rules in a versioned configuration, rather than leaving every update to model discretion. For each open concept/facet and scope, maintain a soft signed score in `[-1, 1]`; the claim representation stores its absolute strength and seek/avoid stance. Initial event contributions are: explicit saved subject `+0.15`, an unambiguous kept card up to `+0.20`, an ambiguous associative card up to `+0.05`, and a negative response only the card's predefined negative mapping, with magnitude at most `0.20`. Pass and performance-only signals contribute zero. A card's total absolute contribution across facets cannot exceed its event budget.

Recompute the score from non-retracted evidence, clamp its final value, and cap the total inferred contribution per facet per session at `0.25`. Decay only inferred evidence with a provisional 90-day half-life. These are ranking weights, not psychometric measurements. Store positive and negative contributions separately so cancellation does not erase ambivalence. Explicit policy controls remain separate from the score and always win.

Use evidence adequacy labels (`single-signal`, `repeated`, `contradictory`, `explicit`) and provenance in the UI. If a numeric `confidence` is needed internally, derive it from a versioned mapping of those labels and distinct evidence counts; never treat it as a statistically calibrated probability. The LLM proposes labels/concept links and prose, while the reducer owns numerical updates and the validator checks that links do not broaden a narrow response. Persist proposed mappings so corrections can rebuild them.

### Model update contract

The model receives the current relevant claims, the narrative excerpt, new evidence summaries, explicit locks, and unresolved contradictions. It returns a bounded patch:

```json
{
  "baseRevision": 17,
  "addClaims": [],
  "reviseClaims": [],
  "retireClaimIds": [],
  "portraitParagraphs": [],
  "associationSeeds": [],
  "unresolved": [],
  "changeSummary": ""
}
```

Each added/revised claim and each factual portrait sentence must cite valid evidence IDs from the supplied bundle. Validators check ID membership, authority, scope, locks, size, and allowable operations. They cannot mechanically prove that prose accurately interprets evidence; evaluation and conservative acceptance remain necessary. Do not accept LLM-provided confidence as empirical calibration.

Model operations cannot edit knowledge counters, delete evidence, change hard exclusions, unlock user text, or promote an association into a fact. Use low-variance generation for updates and a separate creative request for association. Allow one schema repair, then keep the previous narrative and commit only deterministic evidence. Gameplay and future broad puzzles continue.

### Atomicity, late feedback, and replay

The update job key is `(profileId, evidenceBundleHash, reducerVersion, promptVersion)`. Commit with compare-and-swap on the base revision. If another game, card response, or user edit intervened, recompute against the new revision; never overwrite it. Model work happens outside any database transaction; canonical profile revisions commit on the host in a short SQLite transaction.

Immediate post-game summaries use deterministic analysis. Deferred model synthesis can run at the next preparation window. Card responses arriving after synthesis create a new evidence bundle and revision; they never require mutating the completed game.

Store accepted patches and relevant compact evidence so a later model can rebuild the portrait. Rebuilding with the same accepted patches is deterministic. Regenerating model prose is not guaranteed bit-for-bit reproducible; it creates a separately versioned candidate revision.

### Preventing narrative drift

- Keep user-authored anchors verbatim and outside model-editable fields.
- Preserve contrary evidence and time bounds.
- Treat speculation as speculation in prompts and storage.
- Rebuild the portrait from the evidence ledger periodically, initially every 10 completed sessions or after a major correction, rather than indefinitely summarizing summaries.
- Unendorsed associations expire after 10 puzzles or 30 days, whichever comes first.
- Decay weak inferred taste toward neutral over 90 days without relevant evidence. Never decay an explicit hard exclusion away.
- Deduplicate near-identical claims and cap the influence of one session/card batch.
- A user can delete a claim and optionally its supporting history. Tombstones prevent a later rebuild from resurrecting deleted material.

## 8. Free association as a controlled creative engine

Give the LLM real creative latitude, with a narrow consequence: it proposes possible future material.

### Association generation

After a meaningful profile change, select a varied group of evidence-backed seeds: one enduring preference, one recent discovery, one open question, and at most one previously endorsed associative direction. Ask for 30–60 terms/phrases, each with a relation and a short explanation. Use a 1,500–2,500 output-token ceiling. Do not demand an exact token count, which encourages padding and invalid JSON.

Generate distinct passes when useful:

1. Nearby factual/semantic connections.
2. Sound, spelling, etymology, and wordplay possibilities.
3. Literary or metaphorical bridges.
4. A small counterpoint: something different that shares one intelligible connection.

Resolve candidate words and factual relations against the world lexicon. A metaphor may remain as a theme idea; it does not become a factual relation. Unresolved strings may be queued for editorial/source enrichment but cannot become unchecked grid answers.

### Ranking and exposure

Use an initial score of relevance, freshness, lexical quality, distance/diversity, and usefulness to the current recipe. No association can bypass content eligibility, player exclusions, or crossing fairness. Keep at least 30% of a Play puzzle's semantic material broadly selected so the system continues to have new things to say.

Limit recursive association to two edges from evidence-backed seeds before a new user response is required. This prevents “likes railway words” from drifting through a long unobserved chain into an asserted private fascination. A candidate may recur as a low-weight exploration idea; recurrence itself does not increase its authority.

Log which candidates were considered and which were selected, along with their selection probabilities where randomized. This makes later preference interpretation possible: the system chose the exposure, so mere exposure is not evidence that the user chose it.

### Aesthetic target

A theme such as “things that hold an echo” can connect shells, rooms, memory, and recorded sound. Its long answers still need strong, ordinary crossword surfaces and precise clues. The theme should feel discovered through solving, not explained in an introductory essay. Titles and closing statements may be evocative; clue correctness remains exact.

## 9. Reflection cards: desire expressed indirectly

The cards are a small editorial form. They should feel like attractive thoughts encountered after a puzzle, while giving the system interpretable evidence. They are not a disguised questionnaire whose every sentence secretly maps to a psychological type.

### Interaction contract

Show at most three cards after a game, one at a time or in a compact spread. Provide **“Keep this,” “Not for me,” and “Pass”** as visible buttons, keyboard actions, and accessible labels. Swipes are an optional equivalent, never the only control. Allow undo; do not use swipe speed as preference strength.

The default set contains one subject direction, one clue/experience preference, and one optional exploratory association. Permit “more statements” only by deliberate action. Do not block the next puzzle while waiting for responses.

The player can inspect a small explanation such as “This will bring in more etymology.” The poetic surface can remain subtle without making the effect unknowable. A separate settings/editor surface supports precise commands such as “exclude US electoral trivia”; a vague swipe never silently becomes a permanent ban.

### Card examples and declared interpretations

| Statement                                                             | A positive response supports                                                           | A negative response supports                                               |
| --------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| “A word's journey can be more interesting than its destination.”      | A tentative interest in etymology/borrowings.                                          | Less of this particular etymological direction; no opposite worldview.     |
| “I would rather meet a city's cafés than memorize its officeholders.” | A scoped preference for everyday place/culture clues over officeholder trivia.         | No reliable inverse; retire this suggestion without favoring politicians.  |
| “The best clue makes an ordinary object briefly unfamiliar.”          | More semantic misdirection/wordplay, within the chosen difficulty.                     | Fewer clues of that mechanism, not less intelligence or curiosity.         |
| “I like a new word enough to meet it again.”                          | More optional learning/review material.                                                | Lower recurrence appetite; do not discard already explicit learning goals. |
| “Maps become interesting where their usefulness runs out.”            | One low-weight exploratory seed: imagined places, maps in art, metaphorical geography. | Discard that associative seed.                                             |
| “Tonight I want familiar things with one unexpected turn.”            | A session-scoped comfort/novelty recipe.                                               | No durable character claim.                                                |

These are authored examples, not production-validated stimuli. Multi-facet statements have lower confidence and bounded updates. A preference for one subject should not be inferred merely because the wording of a beautiful sentence was appealing.

### Card schema and selection

`ReflectionCardV1` stores ID, immutable text, language, related puzzle entries, source type (authored/model), tone, positive and negative interpretation mappings, scope, expiry, ambiguity level, grounding refs for any factual content, and generation receipt. A response stores the exact card version and shown position. Maps are fixed **before** the response arrives.

Begin with 60–100 authored, reviewed cards and approved paraphrase families. Select using puzzle relevance, uncertainty about an actionable preference, coverage across subject/style/novelty, and recent exposure. The initial selector is deterministic apart from seeded tie-breaking. Avoid asking three variants of the same thing.

Let the model propose cards from the just-played themes; validate them against the card schema, require a narrow declared interpretation, and review during alpha. Original model-generated cards graduate only after the model evaluation suite passes. If generation fails, select from the authored bank.

Track passes separately from “not for me.” An unanswered card is missing evidence. A negative card response can suppress that theme experiment without asserting a belief about the player. Do not derive religious identity, political allegiance, sexuality, or mental-health claims from subjects or swipes; these are unnecessary for constructing personally relevant puzzles. User-authored interests can still include any literary, cultural, religious, or political subject on their own terms.

### Learning which statements work

Optimize for whether the next few puzzles feel better, not the raw number of swipes. Evaluate card understanding, ambiguity, repetition fatigue, regret/undo rate, and resulting puzzle preference. Later use a bounded contextual bandit for choosing among eligible cards, with logged propensities and a fixed exploration budget. Do not start with reinforcement learning or use emotionally provocative statements merely because they attract responses.

## 10. Learning and recurrence

Retrieval practice and spacing justify a learning feature, but do not establish that crossword-assisted completion proves durable learning. The original testing-effect experiments found better delayed recall after retrieval practice than repeated study; the crossword application still needs its own validation. [Roediger and Karpicke, 2006](https://www.psychologicalscience.org/journals/psychological-science/j.1467-9280.2006.01693.x/).

Half-life regression provides a useful reference for tracking recall over time in language learning. Its data and tasks differ from crosswords, especially when crossings reveal part of the answer. Use it as a design reference rather than importing its reported gains or coefficients as our expected results. [Settles and Meeder, 2016](https://aclanthology.org/P16-1174.pdf).

### A review scheduler that can ship first

Implement a `ReviewScheduler` port and begin with an explicit, inspectable schedule:

- Newly saved or newly introduced target: first eligible review on a subsequent day/session, normally 1–2 days later.
- Independent successful retrieval: advance provisional intervals through 1, 3, 7, 14, 30, and 60 days.
- Supported retrieval: retain the stage and schedule another encounter sooner, with a different clue surface.
- Reveal or engaged failure: return to an earlier interval, without presenting it as lost progress.
- Skipped days do not create debt, penalties, or a queue that consumes the whole puzzle.

These are configurable starting values, not scientifically optimized intervals. Store task, interval stage, last outcome, assistance, due date, and scheduler version. Later fit a forgetting model only after adequate labeled recall observations exist; compare it to this baseline using delayed retrieval, not fit on its own training history.

Due words are weighted construction candidates, not mandatory locks. A grid must not become bad because a review schedule insists on an awkward answer. Carry unplaced items forward and optionally offer a separate tiny review interaction after the puzzle. Cap review content initially at 10–15% of entries in Play and 20–30% in Learn; cap genuinely new learning targets at three per full-size beginner learning puzzle.

### A language-learning task is more than a translated clue

Track `sourceLanguage`, `targetLanguage`, retrieval direction, lemma, exact sense, grammatical features, accepted inflection, and orthography. English-to-German production and German-to-English recognition are separate tasks. A bilingual clue that supplies the translation is recognition/exposure, not unassisted production.

Choose one audited language pair for the first learning release; use English↔German as the reference implementation unless owner review selects another pair. Do not infer a player's language goal from location. Add languages as content packs with native/editorial review, input tests, and enough eligible fill, rather than merely enabling a locale code.

Content requirements for each learning item:

- idiomatic gloss, context sentence, part of speech, article/gender where relevant, register, and sense;
- morphology-aware accepted answer and useful explanation;
- approved native-language clue and beginner scaffold;
- provenance and language-editor review state;
- optional pronunciation only when a validated local audio/TTS path is available.

Keep displayed accents. Define puzzle-specific fill tokens and input equivalence explicitly: for example, a pack can display `CAFÉ` while accepting `CAFE`. For the reference German pack, initially use the declared crossword fill mappings `Ä → AE`, `Ö → OE`, `Ü → UE`, and `ß → SS`, while showing ordinary German spelling in explanations and accepting either the original grapheme or the equivalent sequence through one normalized input action. These change cell counts and must be chosen before construction. Case expansion, combining marks, digraphs, and IME input invalidate the current `slice(0,1)`/`[A-Z]` entry logic; use grapheme/token-aware normalization with test fixtures. Never silently apply one English normalization rule to every language.

Mixed-language answers are explicitly marked in clues. Avoid a forced bilingual crossing where both sides are unknown. Crossings into new target-language words should usually come from established language knowledge or a clear clue, and explanations should expose the full correct spelling even if the fill convention differs.

### Demonstrating learning

Offer a voluntary delayed recall check after 7 and 30 days on a sampled subset of saved targets: a different clue/context, minimal or zero crossing support, recorded separately from ordinary play. Compare against similar exposures without scheduled review. Only claim learning improvement when this measure improves. Completion, elapsed time, and word exposure counts are useful product observations but are not learning outcomes.

## 11. The world lexicon and evidence pipeline

Personalization is constrained by the available source material. A beautifully written profile cannot rescue a narrow or unreliable word bank.

### Content pipeline

```text
pinned permitted source artifacts
  -> parsed records + source ledger
  -> normalization and sense/entity resolution
  -> editorial/frequency/locale metadata
  -> verified fact packs and clue families
  -> compact versioned indexes and content packs
  -> host content store / constructor and selected browser caches
```

Start with an approved broad English fill bank plus a smaller, deeply grounded core. A practical alpha target is 50,000–150,000 eligible fill forms and 3,000–10,000 well-described senses; exact counts are resource and quality targets, not observed inventory. Count coverage by answer length, crossing position, topic, locale, proper-name status, and factual grounding. High total count can hide unusable gaps.

Not every fill word needs a biographical record. Every shipped clue needs support appropriate to its type: a licensed lexical sense, a reviewed original language-use clue, or a verified fact. For declared theme transformations, ground the underlying lexical answer and validate its exact transformation into entry tokens; an encoded or playfully transformed fill need not be a standalone dictionary headword. It must have an explicit mechanic certificate and cannot enter through an unrestricted “made-up word” exception. If a common fill lacks a reliable sense, enrich it or exclude it from publishable construction.

### Source admission

Extend `tools/lexicon/source-ledger.json` into a release ledger covering exact input version/hash, terms/license identifier, attribution, permitted redistribution, transformation, emitted IDs, and audit status. Sources can include an approved scored fill list, lexical databases, knowledge graphs, and editorially authored records. Evaluate each source's actual terms before admission; no blanket claim about a whole source family suffices.

The lab reports a licensed Crossword Nexus list; reconcile the exact revision and notices through an approved import/build process. Do not carry the older `NOASSERTION` artifact into a public content pack. Keep private legacy-provider material outside training, benchmarks, generated packs, screenshots, and the deployment graph.

Maintain a deny/quarantine list for unsupported records, bad spellings, ambiguous names, and disputed facts. Withdrawal of a fact retires derived clue versions and queued puzzles; existing sessions remain reproducible with an explicit correction notice where needed.

### Grounding facts

Use bundled, dated fact records in ordinary generation. Do not make gameplay or each generated clue depend on a live website lookup. Content ingestion may verify facts from authoritative sources, cache only permitted material, and store a minimal statement plus provenance. The model receives those facts as data.

Current officeholders, “largest/latest,” changing records, and ambiguous superlatives are excluded from alpha unless the clue specifies a date and the fact pack has a freshness policy. Persistent historical relations are preferable. A model judging its own unsupported recollection is not independent verification.

### Cultural relevance

Store specificity at the clue/sense level: US electoral offices, Manhattan geography, a particular sports league, regional television, classical mythology, religious traditions, or any other subject can have explicit selection weights. General lexical familiarity and locale specificity are different dimensions.

The player can request fewer niche references of any kind, more references to a chosen culture, or a broader mix. Treat a complaint about unfamiliar trivia as a request about content usefulness and assumed knowledge; do not turn it into an inferred demographic identity or an indiscriminate exclusion of people. Keep culturally specific material when it is wanted, well introduced, or meaningfully learnable.

### Repetition policy

Track canonical answer, lexeme, sense, clue family, and semantic theme separately. Initial Play defaults:

- Avoid exact clue text for 90 days or the last 30 puzzles, whichever is a larger available window.
- Avoid ordinary answer reuse for five puzzles when fill feasibility permits.
- Allow glue answers earlier, but avoid the same glue answer in consecutive puzzles and cap designated glue at 15% of entries.
- Apply a rolling penalty to overused short fill such as EWE, OREO, and ETAL; the final recipe can relax the answer cooldown before exceeding a hard glue cap.
- Allow deliberate review to bypass answer cooldown, with a new clue surface and a recorded reason.
- Do not repeat a long marquee answer within 30 puzzles except an explicit revisit request.

Exact intervals are editorial defaults for calibration. A global corpus frequency score does not tell us whether this player has seen the answer eight times this week.

## 12. The generation pipeline

The constructor operates on a frozen `GenerationBrief`. It includes mode, selected weekday recipe and clue-grammar versions, calibration-seed provenance where relevant, languages, session length/size choice, explicit policies, relevant profile projection, due review items, recent exposure, content-pack versions, seed, and resource budget. It excludes unnecessary private narrative.

### Stages and outputs

| Stage                        | Output                                                    | Failure behavior                                                                                                    |
| ---------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| 1. Compile brief             | Validated targets, policies, content coverage check       | Explain incompatible requirements; retain current queue.                                                            |
| 2. Plan themes               | Several coherent long-answer sets and intended mechanisms | Try a different proposal within the selected weekday contract; do not silently substitute a different day/mechanic. |
| 3. Resolve candidates        | Eligible lexemes/senses/facts with rejection reasons      | Drop unresolved proposals; never insert invented answers.                                                           |
| 4. Construct candidate fills | Bounded set of fully valid grids                          | Retry seed/template/soft targets within budget.                                                                     |
| 5. Ground and draft clues    | Variants tied to pinned senses and facts                  | Retry a failed clue or choose a different sense/fill where allowed.                                                 |
| 6. Evaluate player route     | Support graph, simulated paths, ambiguous-crossing report | Repair clue/support region, then revalidate.                                                                        |
| 7. Editorial validation      | Publish/reject report and reasons                         | Reject any remaining hard failure.                                                                                  |
| 8. Freeze manifest           | Immutable puzzle, hints, explanations, provenance         | Atomic publication only after all required validators pass.                                                         |
| 9. Queue                     | Private ready-to-play entries with recipe/profile refs    | Solve remains available even when generation fails.                                                                 |

### Candidate selection

Retrieve a broad permitted fill domain by length/pattern first. Overlay LLM-suggested themes, personal phrases, due words, and semantic neighbors with bonuses. The final fill pool is the eligible lexicon **union** validated model candidates, not only the few thousand words in the portrait/association bag. The current orchestration's model-only candidate path is too restrictive for robust full-size personalized fill and must be extended explicitly.

Theme proposals include the shared mechanism and an explanation of why every member belongs. “Three words about music” is a topic set, not necessarily a theme. Prefer a few memorable long answers over saturating the whole grid with one interest.

### Weekday difficulty is an editorial contract

Offer **Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, and Sunday** as selectable puzzle recipes, independent of the calendar and of Play/Learn/Explore mode. A Wednesday can be requested on Saturday. Remember the last explicit choice, show it before generation, and never silently replace it with an easier day because the profile predicts struggle.

The familiar reference is a progression from Monday to Saturday; Sunday is larger with roughly midweek difficulty rather than a seventh difficulty rung. This distinction is also described in the publisher's help material. [The New York Times Crossword help](https://nytimes.zendesk.com/hc/en-us/articles/360052406391-The-New-York-Times-Crossword-Puzzle).

The specifications below are **our proposed recipes**, informed by that familiar rhythm. They are not a claim of exact numerical equivalence with another publisher's editorial judgments. Our answers and clues are original; conventions and craft provide the familiarity.

| Recipe    | Intended experience                                                        | Clue and theme behavior                                                                                                   | Initial format / likely foothold target                                        |
| --------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Monday    | Immediate ways in; clear success and discovery.                            | Direct senses, straightforward theme, clear signals, sparse gentle puns.                                                  | 15×15; at least 12 footholds.                                                  |
| Tuesday   | Familiar play with a little more indirection.                              | More alternate senses, conversational clues, a cohesive approachable theme.                                               | 15×15; at least 10 footholds.                                                  |
| Wednesday | A satisfying middle distance: real resistance with dependable paths.       | Varied clue types, compact surfaces, more semantic misdirection; theme takes a little inference.                          | 15×15; at least 8 footholds.                                                   |
| Thursday  | The rules acquire an extra dimension, and discovering it opens the puzzle. | One coherent transformation or special mechanic, an inferable/revealable explanation, clue grammar otherwise trustworthy. | 15×15; at least 6 ordinary footholds plus independent routes to the mechanism. |
| Friday    | Fluent language play in an open themeless grid.                            | Strong long entries, deceptive ordinary words, lateral definitions; no obligation to include a gimmick.                   | 15×15; at least 5 footholds; target ≤72 entries after constructor validation.  |
| Saturday  | Dense, elegant resistance for an experienced solver.                       | Economical ambiguous surfaces resolved by fair crossings; sustained inference and low obviousness.                        | 15×15; at least 4 footholds; target ≤72 entries.                               |
| Sunday    | A longer themed journey with breathing room.                               | Broad variety, a substantial theme, midweek clue difficulty; duration comes chiefly from size.                            | 21×21 after the size/engine/UI gate; no false Sunday label on a 15×15.         |

Foothold counts are provisional editorial screening settings, not guaranteed knowledge or targets for every future style. Calibrate them through day-specific playtests. Preserve the same grammar/source/crossing-correctness floor across all days. Increase difficulty through ambiguity, deduction, theme structure and expressive compression before increasing obscure facts. Saturday does not mean a database of unknown names.

Keep a difficulty vector rather than one opaque scalar: lexical rarity, clue indirection, mechanism familiarity, clue-language complexity, region openness, cross-reference dependency, theme inference, and expected duration. The selected day sets permitted ranges; the profile estimates how this particular player may encounter them. Regional trivia aversions still apply on every day.

Personalization can replace irrelevant trivia, choose an interesting sense, distribute footholds, or prepare a suitable nudge. It must not rewrite every clue into a direct definition and keep calling the result Thursday. Assistance is an explicit action during play; opting to change the challenge starts a separately versioned puzzle/clue edition before play, or a clearly labeled assisted edition if requested mid-session. Preserve the original session for analysis.

### Recipe schema and frozen clue language

`PuzzleRecipeV2` contains `weekday`, `editorialVersion`, `clueGrammarVersion`, dimensions, word-count/block bounds, clue-family mixture, ambiguity ranges, foothold policy, theme/mechanic family allowances, assistance bundle policy, and release status. A separate `CalendarAssignment` associates a puzzle with a date. `GenerationBrief` includes recipe ID/version, current mode, and the convention-familiarity projection; the resulting manifest pins them.

A basic clue mixture for 15×15 screening is shown below. These are soft ranges for the **primary clue family**, not punctuation quotas. Distinct signals and grammatical features are additional tags. Counts are chosen to sum to the actual entry count; overlapping ranges are not added as if all maxima apply simultaneously.

| Day band        | Direct definitions/factual access                                     | Conversational, fill-blank, phrase or usage | Semantic misdirection/pun/lateral clueing                             | Theme/meta dependencies                                                 |
| --------------- | --------------------------------------------------------------------- | ------------------------------------------- | --------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Monday/Tuesday  | 50–65%                                                                | 20–35%                                      | 5–15%                                                                 | A small coherent theme set.                                             |
| Wednesday       | 35–50%                                                                | 25–35%                                      | 20–35%                                                                | Usually 3–5 connected theme entries.                                    |
| Thursday        | Ordinary fill similar to Wednesday; target mechanism load separately. | A varied ordinary clue voice.               | Wordplay supports, but does not substitute for, the global discovery. | One reviewed mechanism with sufficient evidence and multiple instances. |
| Friday/Saturday | 20–40%, with more indirect access.                                    | 20–35%                                      | 35–55%                                                                | Usually none; long-answer quality carries the grid.                     |

Do not force a square-bracket clue or a quotation merely to meet a quota. Select senses/answers capable of supporting multiple natural clue families, then draft them. If a theme demands too many strained clues, choose a better theme. Every day should have a recognizable editorial voice and meaningful variety, including direct clues as punctuation between harder ones.

### Thursday mechanics are a system, not an adjective

Introduce a `MechanicRegistry` with typed, versioned implementations. Start with word/phrase transformations and circled/shaded extractions that the ordinary letter engine can support; then graduate true rebus cells. A normal themed grid does not count as a Thursday merely because a model calls the theme clever.

Each `MechanicSpec` defines:

- family/version and applicable entries/cells;
- lexical answers versus the token sequences actually entered;
- deterministic encoding/decoding and, if applicable, direction-specific reading;
- constraints needed during fill and crossing validation;
- how the mechanism can be inferred, and a pinned revealer/explanation;
- accessible presentation and input behavior;
- prepared hint stages that preserve discovery;
- validator IDs and valid/invalid fixtures.

For a first genuine rebus family, allow the same multi-letter token in both directions. A illustrative cell token `SUN` could be used by answers such as `SUNRISE` and `SUNBEAM`; a constructor still has to build a valid complete grid and a defensible theme. A blank cell must not reveal that it is special just by showing a different input box. Offer rebus entry for any playable cell through an accessible control. Once a player enters multiple letters, display them legibly and preserve them through navigation/save/check/export.

The current lab accepts A–Z single-character rows and validates 15×15 grids; it does **not** already support this representation. E21 below extends the native engine/adapter or supplies a dedicated constrained rebus construction path. Do not strip letters from a completed ordinary fill and call the result a rebus. Multi-token crossing equality and reconstructed lexical answers must pass independent validators before a rebus recipe is enabled.

Direction-dependent readings, numeric/symbol cells, paths crossing blocks, and unusual topology get separate future mechanic versions with explicit support. The parser never guesses them from punctuation. The existing private `SPECIAL_CHARACTERS.md` describes provider serialization; it is not the grammar for original clues or a reliable general mechanism API. Model special cells explicitly in the original manifest.

A Thursday should usually offer at least two accessible theme instances and an independent way to reach a revealer or supporting clue. The simulator includes a `mechanismUnknown/recognized/explained` state: discovery can make several entries suddenly tractable. Supply a tiered optional ladder—notice a pattern, compare two answers, explain the rule—rather than instantly revealing every transformed entry. Log rule explanation as assistance, and do not attribute later success to unaided mechanism discovery.

Once a rule is discovered, all declared instances must obey it. The delight comes from a new reliable reading of the grid. Random exceptions and inconsistent mechanics destroy that moment.

### Day graduation

Deliver a credible Wednesday and a real Thursday as early demonstrators alongside Monday, not only an easy puzzle with promises of later complexity. A shared pipeline can generate all recipes, but enable each recipe only after complete-grid editorial evaluation and input/support tests for its allowed mechanics. Show unsupported days honestly as forthcoming. Sunday requires native construction and UI validation at 21×21; do not conceal that work behind a size selector.

Maintain a blind day-classification benchmark using original puzzles and reviewers familiar with this style of crossword. Reviewers assign expected day, explain mismatch, and identify whether difficulty came from language, mechanism, or arbitrary knowledge. Check within-player challenge ratings and assistance patterns separately; exact time limits cannot define a weekday for everyone.

### Initial Monday 15×15 recipe

Retain connected, fully checked grids with minimum entry length three and reviewed symmetry/topology rules. The lab's 78-entry cap is an initial house style, not a law for every later format. Use a curated template bank for production readiness; generated topologies must pass the same tests and editorial review.

Use two distinct budgets, which may overlap:

| Budget                 | Initial targets                                                                                                                                                                                       |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Relationship to player | 30% demonstrated affinity, 20% adjacent interests, 30% broad material, 10% due review, 10% exploration; unused review share becomes broad material.                                                   |
| Solve accessibility    | At least 12 likely footholds, spread across regions; most entries reachable with moderate crossing support; at most three non-inferable unfamiliar proper-name/fact targets in the first easy recipe. |

Semantic percentages are soft targets with ±10 percentage-point tolerance and explicit reporting. Each entry has one primary semantic role to make counts auditable. Glue designation, language, and difficulty are orthogonal flags; do not double-count these as another partition of the same 100%.

Include approximately three or four standout long entries where feasible. Maintain a hard 15% glue cap, a conservative abbreviation budget, and zero unresolved factual clues. Start easy without depending on everyone knowing a particular sports league, politician, or acronym.

### Objective ordering

Use lexicographic priorities, not a single score that can buy its way out of correctness:

1. Grid validity, source eligibility, explicit exclusions, fact support, and input-policy compatibility.
2. Player-specific crossing fairness and reachable solve routes.
3. Minimum lexical/clue quality and repetition limits.
4. Theme coherence, satisfying long fill, variety, personal relevance, and learning opportunities.
5. Construction cost and latency among candidates meeting the preceding requirements.

Within level 4, start with normalized components for clue quality, novelty, relevance, semantic diversity, and planned learning value. Store all component scores and recipe weights. Avoid claiming that a hand-tuned weighted score measures fun; human comparisons calibrate it.

### Repair and fallback order

Try, in order: clearer grounded clue → better prepared context hint → different eligible clue sense with full revalidation → local fill repair with locked good entries → another template/seed → fewer optional theme/review locks while preserving the chosen weekday’s required mechanic → broader permitted semantic pool → curated template/previous ready puzzle.

Never relax a hard exclusion, source requirement, crossing correctness, or unsupported-fact check. Any relaxation of repetition/semantic soft targets is recorded. An active puzzle is never repaired in place. The player's next puzzle can improve; the current one remains an honest object.

## 13. Crossing scaffolding: the central construction algorithm

Counted seed letters are not enough. Their positions, information value, the clues supplying them, and the order in which those clues become solvable determine whether support actually works.

### 13.1 A player-relative solve model

Represent a filled puzzle as an entry graph. Nodes are entries with a chosen clue variant; edges are shared cells with token positions. For entry `e` and current visible mask `m`, estimate:

```text
pSolve(e, m, context) = probability of a correct attempt
                       given this clue, visible pattern, and player evidence
```

Return an estimate **and uncertainty**. Features initially include known sense/fact history, lexical frequency, clue mechanism experience, language level, regional specificity, answer length, support positions, help already shown, and ambiguity of alternatives. Use hand-authored conservative buckets at first. Later fit a regularized model against observed attempts, with player/item grouping and holdout evaluation. Model-written confidence is not a solve probability.

Separate these quantities:

- probability of recalling the clue relation;
- probability of recognizing/completing the answer from a pattern;
- probability that the entry will be fully supplied by other entries;
- probability of completing the region with available assistance.

A name can have near-zero unaided recall but high eventual fillability. That can be a fair encounter, while still contributing no evidence of independent knowledge.

### 13.2 Informative letters

For an entry's eligible alternatives, compute pattern-filtered candidate mass and an optional entropy proxy. A supplied letter is useful when it rules out plausible alternatives, not merely because it increments the filled-cell count. Preserve answer frequency and clue/sense plausibility weights; the entire raw word list is a poor model of what a person considers.

The true answer must always belong to the candidate set. Low entropy in a tiny/incomplete local lexicon is not proof that a human can infer an unfamiliar name. Proper-name/fact targets receive an additional non-inferability flag and conservative treatment.

Use the proxy to choose support positions and reveal hints. Do not let an entropy calculation override editorial review or claim the player experienced information gain.

### 13.3 Support certificates

For each target classified as difficult for this player, search for a support set of crossing entries that raises its estimated solvability or fills it fairly. A support certificate records:

- target entry/clue and initial estimate;
- supporting entries and the exact target positions they supply;
- lower-bound accessibility estimates for the supports;
- how the supports can be reached **without using the target**;
- resulting masks and the estimated change;
- whether the route ends in retrieval, recognition, exposure, or an explicit hint;
- outstanding ambiguous cells and model uncertainty.

For first-release Monday puzzles, require at least two independently reachable support entries for a non-inferable unfamiliar target when topology permits, and review all remaining positions. Two supports are a minimum route check, not a guarantee that two letters suffice. A difficult short name may require every letter to be fairly supplied.

Reject a crossing cell when both incident entries are unfamiliar non-inferable facts and neither has an independent route that resolves the shared token. This is the classic “I could never know that letter” failure, made player-specific. Lowering a generic difficulty score is not an adequate repair.

### 13.4 Reachability without circular reasoning

Build initial footholds using conservative solve estimates; provisional easy-recipe threshold is a lower estimate of 0.75. With sparse player data, use reviewed common-language priors, not an acronym presumed universal.

Run a deterministic expansion pass:

```text
reachable = reviewed initial footholds
repeat:
    for every entry outside reachable:
        mask = letters supplied by reachable entries only
        if target has an acceptable solve/recognition certificate under mask:
            add it in the next layer, recording its parents
until no new entries can be added
```

Use the previous layer's reachable set during each iteration. This produces a support DAG and prevents two same-layer hard entries from certifying one another. Test removal of each foothold and key support to identify brittle single-path regions. A fully supplied entry can enter as exposure, but cannot retroactively certify an impossible unknown shared cell.

Grid quadrants are an initial distribution check, not the definition of a region. Also partition the entry graph around narrow cuts and verify each component has accessible entry points or credible inbound support. Reject inaccessible islands and support chains that all depend on a single uncertain trivia clue.

### 13.5 Simulating realistic paths

After deterministic checks, run a cheap simulator over several player hypotheses:

- optimistic, central, and pessimistic familiarity estimates;
- across-first, down-first, opportunistic, and corner-first navigation;
- independent versus correlated uncertainty within a topic;
- occasional wrong entries, checking, and use of prepared hints.

Start with 64 seeded trajectories for candidate screening, then 256 for finalists if timing permits. Sample a latent player/item state once per trajectory; do not repeatedly reroll the same unchanged clue until it “succeeds.” A new attempt requires a changed mask, hint, or defined revisit behavior. A diagnostic model that sees the answer is not a human solver and cannot validate the route by intuition alone.

Report distributions for initial openings, unresolved cells, large stalled regions, assistance burden, worst reachable masks, and completion. The initial Monday gate targets at least 12 footholds, two geographically distinct footholds per quadrant where slots permit, zero unresolved dual-obscurity crossings, and at least 90% of simulated trajectories reaching completion within the configured assistance allowance. For this gate the allowance is at most three prepared non-answer nudges and **zero direct letter/answer reveals**; otherwise a simulator could “validate” any grid by revealing it. Run separate rescue-path diagnostics with reveals enabled, but never use them to satisfy this gate. Treat the simulation threshold as an engineering screen, not a promised human completion rate.

Calibrate before making probability-based difficulty promises. Until then, human-reviewed support certificates and actual playtests remain the stronger gate. A plot/report of failed routes belongs in the lab so editors can see what a high average score hides.

### 13.6 The Kofi Annan example

The intended answer to “Kofi Annan's middle name” is **ATTA**; a UN biographical record gives his full name. [United Nations biographical note, S/1996/1021](https://documents.un.org/api/symbol/access?l=en&s=S%2F1996%2F1021&t=pdf).

There is an instructive mechanical detail: **OPEC cannot cross ATTA, because the two answers share no letter.** Even when two answers do share a letter, OPEC's familiarity must be estimated for this player rather than assumed.

An illustrative support assignment is:

| ATTA position, 1-based | Crossing answer | Shared position in crossing | Possible straightforward clue |
| ---------------------- | --------------- | --------------------------- | ----------------------------- |
| 1: A                   | CAT             | 2                           | “Pet that purrs”              |
| 2: T                   | TEA             | 1                           | “Drink brewed from leaves”    |
| 3: T                   | WATER           | 3                           | “H₂O”                         |
| 4: A                   | RAIN            | 2                           | “Water falling from clouds”   |

This table is a letter-compatibility example, **not a valid finished grid**; the fill engine must find a topology in which the assignments and all other entries work. These clue drafts also require normal ambiguity and sense review.

For a player who has never encountered ATTA, even `_TTA` may remain opaque. The valid outcome may be an answer supplied through fair crossings and a memorable optional fact card. Record that as exposure. If the fact has little relevance, no compelling theme role, and no learning value the player wants, choose a better answer. Seeding should make worthwhile unfamiliar material accessible, not serve as an excuse to retain arbitrary trivia.

### 13.7 Integration with search

For the first implementation, rank and reject fully constructed candidates using the support evaluator. This is much simpler to verify than embedding an uncertain player model inside every CSP propagation step. Then add cached per-slot/candidate familiarity estimates to search ordering and lower-bound support penalties for partial fills. Hard grid constraints remain deterministic.

Add a local repair operation accepting locked entries, banned assignments, affected slots, and a budget. Preserve the good long answers while replacing a bad crossing region. Re-run all global validators after repair; locality of an edit does not imply locality of its effects.

## 14. Clue writing, verification, and editorial quality

A good clue offers pleasure in the relationship between its surface and the answer. The model's writing quality matters here more than general benchmark prestige.

### A language the player can learn and trust

The central pleasure includes becoming fluent in the puzzle's conventions. At first the player sees an opaque clue; later a quotation, tense, or question mark becomes a usable move. Personalization should preserve this common language so learning transfers between puzzles. It should not invent private punctuation rules for each person.

Adopt a versioned American-style house grammar, with NYT-like signals and clue variety. Publisher guidance supports the broad conventions of grammatical agreement, conversational quotations, abbreviations, wordplay signals and linked clues; below we specify our own production rules, examples, validators and teaching behavior. [Puzzazz guide by Parker Lewis and Roy Leban](https://www.puzzazz.com/how-to/crosswords). A constructor and Wordplay writer likewise describes learning these recognizable patterns as part of getting into crosswords. [Rachel Fabi interview](https://www.upstate.edu/informed/2021/121021-fabi-podcast.php).

The detailed NYT solving guide was inaccessible during this research. Do not present this document as a verified exhaustive NYT style manual. The table is our explicit house specification; original examples below are illustrative drafts, not borrowed publisher puzzle data.

| Feature / cue                             | Our house rule                                                                                                                   | Original illustrative example                                                                                 | Validation / teaching requirement                                                                                                                                   |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Number agreement                          | An ordinary plural definition requires the corresponding plural sense; irregular and invariant plurals are allowed.              | `Purring pets` → CATS; `More than one goose` → GEESE.                                                         | Match morphological number, not a final-S regex. Reject `Pet that purrs` → CATS.                                                                                    |
| Verb tense and agreement                  | Definition and answer must substitute grammatically in the intended reading.                                                     | `Devoured` → ATE; `Devours` → EATS.                                                                           | Record person/number/tense/aspect where relevant; reject a mismatched inflection. An ambiguous form needs a justified intended reading.                             |
| Part of speech                            | Direct synonym/definition clue and answer have compatible grammatical roles.                                                     | `Quietly` → SILENTLY.                                                                                         | Require a substitution/context witness for ambiguous phrases; reject unsupported noun/verb/adjective switches.                                                      |
| Whole quoted utterance                    | Seek a spoken equivalent with appropriate register, not necessarily a dictionary synonym.                                        | `“Not a chance!”` → NOWAY.                                                                                    | Tag as `spoken-equivalent`; explain the conversational substitution. Preserve quotes visually and accessibly.                                                       |
| Literal square brackets                   | Reserve whole-clue brackets for a nonverbal action, reaction, or sound to be verbalized/rendered in letters.                     | `[Shiver]` → BRR; `[Sigh of relief]` → PHEW.                                                                  | Tag `nonverbal-expression`; distinguish action/sound expression from a spoken paraphrase. Review ambiguity among sound spellings and crossings.                     |
| Final question mark                       | Signal a playful/nonliteral interpretation or pun when this family calls for it.                                                 | `Branch specialist?` → ARBORIST.                                                                              | Require a concise account of both the ordinary reading and intended twist. Do not append a question mark to rescue an inaccurate fact or strained definition.       |
| Ordinary ambiguity without `?`            | A defensible alternate sense can misdirect without being a pun.                                                                  | `Current unit` → AMP.                                                                                         | No rule that every indirect clue must carry `?`; still require sense agreement.                                                                                     |
| Abbreviation/initialism                   | License shortened fill through an explicit indication or genuinely applicable abbreviated clue language.                         | `Estimated arrival, briefly` → ETA.                                                                           | Record the actual indicator span. An incidental abbreviation elsewhere in a factual clue is not sufficient evidence. Conventional exceptions need registry entries. |
| Register                                  | Slang, informal, archaic, dialectal, or variant forms need matching register or a signal.                                        | A colloquial answer needs an appropriately conversational surface.                                            | Store register and exception rationale; do not make niche slang an unmarked Monday assumption.                                                                      |
| Fill in the blank                         | The answer completes a documented phrase, expression, or grounded quotation.                                                     | `Safe and ___` → SOUND.                                                                                       | Store the completed phrase and evidence; multiword fills are permitted and need not be universally labeled “2 wds.”                                                 |
| Example-to-category                       | A clue giving an example of its answer indicates that relation where required by the house style.                                | `Oak, for one` → TREE.                                                                                        | Check direction: example→category differs from category→example. Do not conflate `maybe`/`e.g.` with arbitrary uncertainty.                                         |
| Foreign-language answer                   | The surface signals the language through context or an explicit label.                                                           | `Thank you, in German` → DANKE.                                                                               | Pin language, sense and orthography; the learning mode can add richer explanation.                                                                                  |
| Quotes inside a longer clue               | They can identify a title, a cited word, or actual quotation rather than a spoken-equivalence clue.                              | `Word before “rain” in “acid rain”` → ACID; the quoted words are mentioned language, not a spoken paraphrase. | Store quote role by span; do not classify every quote character as the same mechanic.                                                                               |
| Cross-reference                           | Refer to actual numbered entries/directions; distinguish linked definitions from a multi-entry answer.                           | `With 18-Down, ...` references a defined shared answer object.                                                | Validate referential integrity, segment order and acyclic/supportable dependencies; renumber safely.                                                                |
| Asterisks, italics, circles and shading   | Mark theme membership or meaningful structure only under the puzzle's declared mechanism.                                        | A starred clue can be referenced by a revealer.                                                               | Typed spans/cell decorations and accessible descriptions; never flatten away information.                                                                           |
| Initial capitals / punctuation in answers | Initial clue capitalization is ordinary style and may permit ambiguity. Answer spaces/punctuation are separate from fill tokens. | An ordinary word at clue start need not be a proper noun.                                                     | Preserve display answer and fill form separately. Do not require an indicator for every multiword answer.                                                           |

Square brackets used by an article to quote **any** clue are not necessarily brackets actually printed in that clue. Store literal clue text and typed semantic spans; the UI must not wrap every clue in decorative brackets or quotes and erase this distinction. Likewise, an author's title quotation and the whole-clue speech convention must remain distinguishable.

### Schema: clue family, variant role, grammar, and special mechanics

The existing `ClueMechanism` values (`direct`, `standard`, `oblique`, `nudge`) describe variant roles, not a complete taxonomy of clue mechanisms. In v2 split:

- `variantRole`: standard, direct alternative, oblique alternative, context hint, convention hint;
- `primaryFamily`: definition, factual relation, fill-blank, spoken-equivalent, nonverbal-expression, semantic misdirection, pun, metalinguistic, linked, or theme-dependent;
- `grammar`: grammatical relation, answer morphology, register, language, exception ID if any;
- `surfaceSpans`: typed quotes, brackets, indicator text, emphasis and cross-reference spans;
- `interpretation`: the intended sense, concise semantic justification and, for wordplay, surface-versus-intended-reading explanation;
- `mechanicRef`: optional reference to a puzzle-level `MechanicSpec`, not an arbitrary instruction from the model;
- `teachingRefs`: convention IDs for optional help and familiarity tracking.

A JSON Schema-valid annotation can still be false. Validate consistency between annotation and the rendered text, compare morphology against the lexicon, check references structurally, and use a semantic challenger/editor for substitution and wordplay. Fail closed on unresolved factual or grammatical errors. Surface punctuation is a lossy clue to meaning; a regex alone cannot validate cluing.

Migrate old role-only records into `variantRole` and leave their actual family `unclassified` until reviewed; do not infer reliable historical grammar from an enum name. Keep the v1 renderer/import path. The new typed spans render as React nodes/text rather than arbitrary model-supplied HTML.

### Convention fluency is part of the episteme

Track tentative familiarity with conventions such as spoken-equivalent, nonverbal-expression, abbreviation signal, grammatical agreement, alternate sense, pun signal, cross-reference, and each special mechanic. These are a small versioned game-language vocabulary, not a fixed taxonomy of the person. Open-ended interests and associations remain unrestricted.

Evidence comes from solving varied examples under known support, or asking for a convention explanation. One correctly filled quoted clue does not establish fluency. A convention hint is different from a fact hint, and both differ from revealing letters. A player who learns a signal has gained a reusable move; the next puzzle should sometimes let them use that move on unfamiliar content.

Offer **“How to read this clue”** on request. Explain only the relevant convention first: for a whole quoted utterance, “Try another thing someone could say here.” Do not disclose the answer unless the player goes further. After a confirmed answer, show a short explanation of the move. Record these assistance tiers. Keep onboarding teaching sparse and contextual; do not demand reading a rulebook before play.

A useful recurring arc is: encounter an unfamiliar convention with strong crossing support → understand one instance → meet a different instance without the explanation → later combine it with another familiar move. This is where the player's growing language expands what they can enjoy. Keep some recognizable short fill as footholds; rotate its clue senses rather than eliminating every recurring word. The OREO can become a known step in the dance without consuming the whole dance.

### Required clue-grammar fixtures

Create an original `clue-grammar-v1` test pack with at least 20 valid and 20 invalid/ambiguous examples for each major family. Include plural irregulars, tense ambiguity, noun/verb alternate readings, title versus speech quotes, actual versus editorial brackets, abbreviated clues with unrelated acronyms, correct puns with and without signals under policy, false puns, foreign language signals, missing cross-reference targets and numbered-entry changes.

Tests must reject confidently wrong model annotations as well as malformed text. For each accepted fixture preserve the intended reading and an editor's reason; for each rejected one preserve the defect and repair. Extend blind model comparison to this pack and report failure rates by family, not only overall clue quality. The first Wednesday/Thursday demonstrations must pass grammar review on every clue and mechanic instance.

### Clue request

Supply the answer display/fill forms, pinned sense, allowed facts, selected weekday recipe, clue-grammar version, required primary family, language/locale, intended mechanism, estimated player familiarity, nearby clue surfaces, and requested difficulty range. Exclude the full player portrait unless a particular excerpt is necessary. Generate in small batches of 4–8 entries for coherence and bounded retry cost.

For each entry, request:

- a standard clue;
- a clear alternative or contextual nudge;
- an optional oblique version only when the recipe permits it;
- a short explanation;
- fact/sense IDs supporting the text;
- variant role, primary family, typed signal spans, morphological agreement, and any abbreviation/enumeration requirements.

Make standard and assistance versions meaningful alternatives. Merely adding more words to a bad clue does not create a good hint.

### Validation stack

1. **Structural:** valid schema, language, lengths, IDs, token/cell enumeration, answer leakage, duplicate text, known answer morphology.
2. **Semantic:** clue agrees with pinned sense, tense/number/register, clue language and allowed facts; no added unsupported assertion.
3. **Alternative-answer challenge:** retrieve plausible competing answers of the same length and ask a separate solving pass, without showing the target, to solve clue plus progressive masks. Disagreement triggers review; agreement is evidence, not proof.
4. **Mechanism:** abbreviations signaled; wordplay parsing available; factual specificity justified; any pun has a defensible reading.
5. **Puzzle editorial:** surface variety, theme consistency, rewarding long answers, no repetitive voice, no cluster of niche proper names, no unintentional answer giveaways across clues.
6. **Player route:** section 13's fairness gates pass on the actual selected clue set.

Use another model for a challenger when available, but do not call two related models independent factual sources. The facts come from content provenance. Human review is required for the initial release corpus and for promoting new model/recipe combinations.

### Multiple valid answers

A clue may admit several words before crossings; that can be normal. A completed valid crossing pattern must resolve the intended answer. If another answer of the same length fits the clue and every visible constraint and the cell cannot be reasonably disambiguated, flag it. Prefer rewriting the clue or changing the fill before publication.

During play, an alternative-looking submission can be reported. Do not punish the player's profile for a content defect. Keep feedback/correction history linked to clue versions so later analyses can retract bad evidence.

### Editorial acceptance rubric

Human reviewers score fairness, clarity, surface naturalness, freshness, satisfying misdirection, theme coherence, and “would I be happy to meet this answer?” A clue can be correct and still be poor. Any unsupported factual assertion, irreducible ambiguous letter, or inaccurate language-learning item is a release-blocking failure regardless of average score.

The easy recipe should usually make the player think “I can get this” rather than “I have already seen this clue.” Better language and better crossing support allow novelty without merely escalating trivia obscurity.

## 15. Software boundaries: the current application, made durable

Extend `apps/react` and Flask. Use native `xfill` and Ollama on the application host. Preserve pure TypeScript domain/application code, but stop making browser execution a prerequisite. The existing native lab becomes the source of production adapters rather than a parallel product.

```text
 React solver + calibration + weekday selector + profile UI
   pure local command reducer
   IndexedDB checkpoint / cached puzzles / durable outbox
             |
             v
 Flask product API, same origin, on the application host
   schema validation / access / version checks
   SQLite canonical journals, profiles, jobs, puzzle queue
             |
             v
 separately managed Python job worker with leases
   product Node runner: shared TS reducers + generator packages
      Ollama adapter -> installed local model
      native constructor adapter -> pinned xfill executable
      content packs / route simulation / clue validators
   bounded JSON Lines progress/results -> worker -> SQLite
```

The diagram shows responsibilities, not six separately deployed services. Start one Flask process, one Python job worker, and the existing Ollama service; the worker invokes bounded Node runner processes and the native fill executable. No Redis, distributed task queue, browser-model conversion, or new UI framework is required for the first working version.

### Repository and module ownership

| Location                                             | Responsibility                                                                                                                                     |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `crossword/apps/react/src/`                          | Extend the active solver with calibration, weekday selection, hints, reflection, preparation, and profile UI. Preserve current interaction parity. |
| `crossword/packages/domain/src/`                     | Pure puzzle/session/calibration/profile values, token rules, clue grammar, observations and reducers.                                              |
| `crossword/packages/application/src/`                | Analysis, profile-patch validation, brief compilation, queue and calibration use cases behind ports.                                               |
| `crossword/packages/persistence/src/`                | Browser cache/outbox, API-backed repositories, shared import/export logic; canonical storage is on the host.                                       |
| `crossword/src/crossword/api_v1/` (new)              | Flask routes and request schemas for original puzzles, profiles, sessions, calibration and jobs.                                                   |
| `crossword/src/crossword/jobs/` (new)                | Durable job queue, leases, cancellation, process management, retry and transaction publication.                                                    |
| `crossword/src/crossword/database.py` and migrations | SQLAlchemy canonical journal/profile/job tables; preserve existing completion data.                                                                |
| `crossword/tools/runtime/` (new)                     | Compiled Node entrypoint importing product TS use cases and generator packages; JSON Lines protocol, no duplicated intelligence logic in Python.   |
| `crossword/tools/lexicon/`                           | Content/source admission and versioned packs, including original stimulus and clue-grammar packs.                                                  |
| `crossword-generator/packages/local-runtime/` (new)  | Node-only Ollama and native `xfill` adapters extracted from lab server; versioned runner support, packaged native-artifact manifest.               |
| `crossword-generator/packages/construction/src/`     | Pure grid/support validators, route simulation and engine contracts; TypeScript CSP remains a reference/alternative.                               |
| `crossword-generator/packages/generator/src/`        | Staged generation, bounded repair/retry, receipts and publication gates.                                                                           |
| `crossword-generator/packages/model-runtime/src/`    | Runtime-neutral language-job contracts/fakes; browser-specific adapters remain isolated for possible later ports.                                  |
| `crossword-generator/apps/lab/`                      | Model comparison, native constructor controls, grammar/mechanic review, route inspector, calibration trace inspection.                             |

Keep Node APIs out of browser import graphs with separate exports/build targets. Define `AudienceProjection`, `GenerationBrief`, language jobs and engine results in dependency-neutral generator contracts. The product compiles its private history into a brief. The generator never imports the product repository. The product Node runner can import both, so the same TS reducer runs in tests, the browser, and host analysis without copying its rules into Python.

The current lab middleware has useful validation but request-scoped generation and an in-memory busy flag. Extract its functions into explicit services with injected paths, content manifests, budgets and abort signals. Retain a thin Vite adapter for the lab. Do not run Vite as the application's durable generation service.

### Application ports

Retain typed `SessionJournal`, `ProfileRepository`, `EpistemeService`, `PersonalPuzzleService`, and add `CalibrationService` and `RecipeCatalog`. Their interfaces separate domain operations from transport:

```ts
interface SessionJournal {
  appendLocal(command: SessionCommand): Promise<LocalCommit>;
  sync(sessionId: string): Promise<SyncResult>;
  read(sessionId: string, afterSeq?: number): Promise<JournalSlice>;
}
interface ProfileRepository {
  read(profileId: string): Promise<ProfileSnapshot>;
  commit(
    update: ValidatedProfileUpdate,
    expectedRevision: number,
  ): Promise<CommitResult>;
}
interface EpistemeService {
  analyze(sessionId: string): Promise<SessionAnalysis>;
  update(profileId: string, evidenceIds: string[]): Promise<JobReceipt>;
  project(profileId: string, recipe: Recipe): Promise<AudienceProjection>;
}
interface PersonalPuzzleService {
  prepare(brief: GenerationBrief, idempotencyKey: string): Promise<JobReceipt>;
  listReady(profileId: string): Promise<QueuedPuzzle[]>;
  start(puzzleId: string, profileId?: string): Promise<SolveSession>;
}
```

These interfaces are a design contract; referenced result schemas must be implemented in E01. Every result distinguishes local durability, host acknowledgment, and derived analysis readiness. Never show “saved to profile” while data exists only in an unsent browser outbox.

### Product HTTP contract

All new routes live under `/api/v1/`, separate from private legacy provider routes. Use JSON Schema-derived/Pydantic request validation and stable structured errors. The initial route set is:

| Route                                                        | Contract                                                                                                                           |
| ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| `GET /runtime`                                               | Approved installed model IDs/digests, worker/engine readiness and available recipes; never arbitrary filesystem paths or secrets.  |
| `POST /profiles` / `GET /profiles/:id`                       | Create/read a named local profile; return revision/epoch and inspectable projections.                                              |
| `PATCH /profiles/:id`                                        | Explicit edit with expected revision and idempotency key; mismatch returns 409.                                                    |
| `POST /calibrations` / `POST /calibrations/:id/observations` | Start and append versioned visual-choice observations; deduplicated IDs; completion schedules the initial brief.                   |
| `POST /sessions`                                             | Start a frozen puzzle edition and return session ID, writer epoch/lease and starting sequence.                                     |
| `POST /sessions/:id/events`                                  | Bounded event batch with expected accepted sequence, writer token and event IDs; acknowledgment identifies accepted IDs/sequence.  |
| `POST /sessions/:id/finalize`                                | Require committed terminal sequence/hash, then enqueue analysis once; allow partial-session analysis with an explicit stop reason. |
| `POST /preparations`                                         | Frozen recipe/profile/content refs and idempotency key; return 202 with job ID.                                                    |
| `GET /jobs/:id` / `GET /jobs/:id/events`                     | Snapshot and resumable progress; use numbered SSE events or bounded polling. Disconnect does not cancel.                           |
| `POST /jobs/:id/cancel`                                      | Request cancellation idempotently; returns actual job state, not a fictional instant stop.                                         |
| `GET /puzzles/:id` / `GET /profiles/:id/queue`               | Immutable manifest and ready queue with publication status.                                                                        |
| `POST /reflections/:id/responses`                            | Immutable card version, response/undo linkage and profile/session identity.                                                        |
| `POST /exports` / `POST /imports`                            | Scoped export and staged validated import; return job or preview handles for large archives.                                       |
| `DELETE /profiles/:id`                                       | Tombstone/increment epoch, revoke pending work, remove derived private data.                                                       |

Bound body sizes and event batches (initially 200 events or 256 KiB, whichever comes first). Use 409 for conflicts, 422 for schema/domain rejection, and an explicit retryable runtime-unavailable error. A generation failure is a job outcome, not an HTTP timeout with an ambiguous side effect. Client retries reuse the same idempotency key.

For canonical session ingestion, validate schema/references and sequence in Flask, replay bounded batches through the shared TS reducer in a warm/pool-limited Node validator, then commit events/checkpoint in a SQLite compare-and-swap transaction. Replay occurs outside the transaction; commit only if the base sequence/epoch is still current. This is quick deterministic work, separated from the long GPU job queue. Python owns transactions but does not reimplement the crossword reducer. A shared JSON conformance corpus checks Python/TS boundary agreement.

### Durable worker and runtime protocol

The Python worker claims one queued job atomically with a lease/fencing token, freezes inputs, and invokes the product Node entrypoint with an allowlisted operation. Use argument arrays and bounded stdin JSON; do not interpolate profile text, model IDs, or answer strings into shell commands. Each JSON Lines output has job ID, attempt ID, protocol version, monotonically increasing progress sequence, event type and bounded payload. Logs go to stderr without full private prompts by default.

Persist stage outputs by hash outside long database transactions. The worker is the only writer publishing jobs/results, and rejects late output whose lease, profile epoch, or frozen brief no longer matches. A restarted worker can resume a verified stage or retry idempotently; it cannot append two profile revisions for one evidence bundle. Lease expiry does not itself authorize two concurrent native/model processes: kill/reap an old owned process group before restarting on the same host.

Use discriminated language jobs: `plan-themes`, `draft-clues`, `propose-profile-patch`, `expand-associations`, `draft-reflections`, `challenge-clue`, and `propose-calibration-paths`. Each carries request/input/schema/prompt versions, budget and exact model artifact. Preserve current candidate/clue APIs through compatibility wrappers for one release. The adapters return parsed validated values and timing/usage, never executable model instructions.

### Access boundary and setup

Serve the UI/API from the same origin. Initial bind is loopback. Protect state-changing requests with host/origin checks and a session-bound anti-CSRF token; validate WebSocket origins if reused. Existing wildcard Socket.IO CORS is not an acceptable access boundary for profile APIs. Do not expose Ollama or the job runner directly to the browser, allow arbitrary model downloads from text input, or accept arbitrary runtime URLs/commands from a request.

Add a `make run-personal` target (proposed) that checks the pinned Node/Python tools, migrations, approved native artifact, content packs and Ollama readiness, starts/reaps Flask plus the worker, and reports which components need attention. Model installation is an explicit host setup action with exact ID/size/progress; do not silently pull several large models. Keep a ready sample available if inference is absent.

Package the fourth generator/local-runtime archive and an OS/architecture-specific native engine artifact with digests/licenses. Development can build it through approved tools from the generator checkout. A clean product install consumes versioned artifacts and does not require a sibling checkout. The existing `make run`/solver path remains useful during incremental integration.

## 16. Storage, recovery, privacy, and portability

### Canonical host state and browser working state

SQLite on the application host is authoritative for accepted history, profiles, jobs, prepared manifests and published analysis. IndexedDB is the local working journal/outbox and cache. An offline browser can continue solving a downloaded puzzle; it cannot perform fresh host inference or claim that an unsynced profile update is complete.

Use SQLAlchemy migrations (introduce a pinned Alembic migration workflow if needed) instead of extending `db.create_all()` as if it upgraded existing tables. Preserve the existing `completed_puzzles` table and legacy UI while adding the original-puzzle records. Shared host tables include:

| Table/group                                 | Key / essential constraints                                                  |
| ------------------------------------------- | ---------------------------------------------------------------------------- |
| `sessions` / `session_checkpoints`          | session UUID; profile/puzzle refs; accepted sequence; writer epoch; revision |
| `solve_events`                              | event UUID; unique session+sequence; immutable payload/hash and segment      |
| `calibrations` / `calibration_observations` | calibration/trial IDs; ordered presentation/response evidence                |
| `profiles` / `profile_revisions`            | profile UUID+revision; epoch/tombstone; explicit locks                       |
| `profile_evidence` / `knowledge_items`      | evidence UUID; profile+task key; source session and due date                 |
| `session_analyses`                          | unique session+analysis version+input hash                                   |
| `associations` / `reflection_responses`     | immutable stimulus/card versions; parent/evidence refs and expiry            |
| `jobs` / `job_events` / `job_stages`        | idempotency key; claim lease/fencing; frozen inputs; stage hashes            |
| `puzzles` / `puzzle_queue`                  | immutable manifest hash; profile/recipe/policy revision; ready/started state |
| `content_manifests` / `deletion_tombstones` | versioned artifacts and deleted subject IDs/epochs                           |

Enable foreign keys and configure SQLite locking/busy timeout for a small number of workers. Keep transactions short; no LLM call or fill search holds a database lock. Back up through a consistent SQLite backup operation and include referenced immutable blobs. Do not treat copying a live database file without its transactional state as a reliable backup.

Consolidate the browser's duplicated IndexedDB v3 open/upgrade code into one migration owner. Add session-ID-based checkpoints, event outbox, canonical acknowledgment cursors, cached manifests and lightweight profile projections. A server acknowledgment cannot evict unsynced events before the corresponding local checkpoint transaction commits. Never silently fall back to volatile memory for supposedly durable history.

### Synchronization and conflicts

The browser command reducer produces immediate UI state and event records in one local transaction. Send contiguous batches with an expected canonical sequence. The host deduplicates event IDs, verifies/replays them, commits events plus checkpoint, then acknowledges. Duplicate delivery has no extra learning effect. Partial failures keep unacknowledged events for retry.

A server-issued writer epoch/lease prevents two tabs/devices from silently interleaving one session. Use BroadcastChannel for same-browser awareness, backed by host fencing. Offline edits after a lease has been superseded remain a recoverable draft branch: show a conflict and offer a separate attempt or explicit takeover from the canonical checkpoint. Do not drop them, silently last-write-win, or merge contradictory letters into a single fictional solve history. Retained branches share provenance for their common prefix so analysis does not double-count inherited observations.

Profile edits use expected revision. Model synthesis runs against frozen evidence and commits only if revision/epoch checks pass. Cross-device account sync is not an initial feature; a second browser can read a host profile through the same access boundary and receive a writer lease. Wider network access requires the additional deployment controls noted in ADR 0003.

### Migration and retention

Migrate v1 browser snapshots on explicit adoption into stable sessions with `legacy-observation` provenance. Import host legacy completion records as completion metadata, not fabricated letter histories. Missing focus/check results stay missing. Keep old puzzle hashes and imports readable. Test populated SQLite/IndexedDB upgrades, interrupted migration, future schema versions, database busy conditions, quota/disk-full failures, service restart, and duplicate import/reconciliation.

Default raw event retention remains 90 days or 100 completed sessions, whichever reaches the limit first, excluding active and unsynced sessions. Commit compact source-linked evidence and reducer versions before compaction. Full keystroke replay is unavailable after raw events are pruned; state that in exports. A future reducer requiring discarded detail cannot reconstruct it. Keep compact learning/preferences evidence while the profile exists, unless the player deletes it.

### Export, deletion and privacy

Provide separate puzzle, word-list, and private profile/history exports with manifests, bounded chunks, integrity checks and import preview. Extend the existing 10 MiB continuity envelope intentionally rather than silently truncating richer histories. Validate into staging before adoption; re-import by stable IDs is idempotent. Independently edited profiles remain separate or require a reviewed merge.

Deleting a session/topic/profile removes its eligible evidence, derived claims, associations, learning records, queue metadata and stored private stage outputs, and invalidates in-flight jobs by epoch. Retain minimal tombstones that prevent re-creation on replay. Connected clients clear affected caches; disconnected clients receive tombstones on reconnect. Export files and offline devices cannot be remotely erased while absent; accurately disclose their scope and retention. Define backup expiration so a restore reapplies deletion records before publishing a profile.

Profiles and prompts stay on the local application host by default. The local Ollama adapter uses installed local weights, with no hosted inference fallback. A phone connected to a computer sends game data to that computer; do not call that browser-only or “never leaves this device.” Keep raw prompts/history out of URLs, normal logs, and public puzzle receipts. Optional research exports remain explicit, minimized and previewed.

Local files/SQLite and IndexedDB are not encryption against someone with access to the operating-system/browser profile. Private export encryption, if offered, uses established authenticated encryption and reviewed key handling. UI language should be accurate about storage without interrupting the aesthetic opening with infrastructure detail.

### Household scope

Support named local profiles. Attribute actions when known; otherwise update household exposure rather than individual mastery. Combined puzzles union interests, respect every participant's hard exclusions, and provide multiple entry routes. Keep individual histories separate. Existing Socket.IO multiplayer can remain available as a legacy feature, but integrating attribution into the new journal is a distinct tested task; do not infer who solved a word from a room's final grid.

## 17. Qwen, Gemma, and the actual runtime decision

### Verified identities, not approximate model names

As checked on 25 September 2026, the comparison should name exact candidates:

| Candidate                   | Why include it                                                                           | Current evidence                                                                                                                                       |
| --------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `Qwen/Qwen3.8-27B`          | Continuity with the lab's documented `qwen3.8:27b` experiment.                           | Official model card exists; our repo records one useful clue draft, not a benchmark. [Qwen model card](https://huggingface.co/Qwen/Qwen3.8-27B).       |
| `google/gemma-3-27b-it`     | Tests the literal 27B Gemma option if that is the model whose writing prompted the idea. | Official 27B instruction-tuned model. [Gemma 3 model card](https://huggingface.co/google/gemma-3-27b-it).                                              |
| `google/gemma-4-31B-it`     | Main Gemma 4 dense-model writing candidate.                                              | Listed in Google's official model collection. [Gemma 4 collection](https://huggingface.co/collections/google/gemma-4).                                 |
| `google/gemma-4-26B-A4B-it` | Gemma 4 efficiency candidate, evaluated for the same writing tasks.                      | Listed alongside the dense model; total and active parameters are different. [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4). |

“Gemma 4 27B” should not become a fabricated model identifier. Do not silently substitute Gemma 3 when the experiment is meant to test Gemma 4. If the locally installed Qwen artifact is another version or a modified derivative, record that and include it as a separately named baseline. Downloading/running these models is implementation work; it has not been performed for this plan.

### First benchmark in the existing private lab

Extend the lab with an experiment runner that consumes the same frozen tasks for every model. Discover installed tags, map them to exact upstream identities where possible, and record the resolved artifact digest, quantization, chat template, runtime version, context limit, sampling parameters, thinking configuration, hardware, and peak memory. A mutable tag is insufficient provenance.

Use runtime-supported schema-constrained output and still validate every response. Ollama supports supplying JSON Schema through the `format` field; this is used by the shared product/lab adapter. [Ollama structured-output documentation](https://docs.ollama.com/capabilities/structured-outputs). Put the Ollama adapter in the Node-only local-runtime package shared by the product worker and lab. The browser talks only to the product API.

Run models serially on the reference machine to avoid confusing memory pressure/model swapping with quality. Compare matched quantization classes, then evaluate the actual deployment artifact. Evaluate the exact installed quantized artifact; do not assume its writing or schema behavior matches a different precision or derivative.

### Evaluate roles separately

Gemma might win clue prose or reflection wording while Qwen wins reliable structured updates. That is a hypothesis. Score each role:

1. Grounded direct and oblique clues, including short fill and long phrases.
2. Coherent theme sets that resolve into the permitted lexicon.
3. Profile patches that retain negation, scope, uncertainty, and explicit corrections.
4. Associative expansion that is varied and evocative without asserting new player facts.
5. Reflection cards with attractive language and a defensible interpretation.
6. Bilingual clue/explanation correctness for the selected learning pack.
7. Resistance to malformed input, embedded instructions, and long-history distraction.

Do not pick a model from coding benchmarks or general prose preference alone. Do not make the model itself the sole judge of its output.

### Benchmark stages and decision rules

**Smoke:** 40 clue tasks, 8 update histories, 8 association/card tasks per candidate. Catch schema/grounding/runtime failures and establish token/latency costs.

**Blind quality comparison:** 240 stratified clue tasks, 24 history-update sequences, 30 association tasks, 30 card tasks, and 60 bilingual tasks. Run multiple samples for a selected variance subset, with sampling seeds/configuration logged. Use an equal prompt-tuning budget per model; keep a separate frozen holdout set. Randomize output order and conceal model names from reviewers.

**Integrated finalists:** at least 12 full puzzles per finalist across six contrasting profiles, including sparse histories and topic aversions. Review whole-grid routes and playability, not just individual clues. A good clue generator can still produce an incoherent or unfair puzzle.

Require zero hard policy/lock violations on deterministic fixtures, no unsupported facts in the accepted puzzle set, high schema adherence after at most one repair, and no degradation in clue fairness. Use paired human comparisons with confidence intervals for writing preference. If the comparison is inconclusive, retain the simpler/faster current model and document uncertainty rather than manufacture a winner.

Ship one default model initially to avoid multiple large downloads and repeated memory swaps. Add per-role routing only if its measured gain justifies load time, disk size, and cognitive complexity. The architecture supports several models; the normal player should not need to manage a model laboratory.

### Ollama is the primary runtime

Use installed local models through a configured, host-controlled Ollama endpoint, loopback by default. Discover installed artifacts through the model-list endpoint and resolve their metadata before scheduling. Do not select a similarly named model silently when an expected digest is missing. [Ollama model-list API](https://docs.ollama.com/api/tags).

The adapter sends typed chat requests with task-specific context/output limits and schema-constrained final responses. Record prompt/output token counts, load/prefill/decode durations, completion reason and exact options when the runtime supplies them. Detect truncation before parsing a result as successful. Configure thinking behavior only when supported by the selected artifact; never expose internal thought output as a clue or profile explanation. Keep the final structured response as the useful artifact. [Ollama chat API](https://docs.ollama.com/api/chat).

Start with one GPU inference job at a time and one default loaded model. Batch operations by model during preparation. Use an explicit context size, initially 8–16K when supported, because an advertised maximum is not the same as the runtime's selected context. Set a short keep-alive between nearby batches, then release memory after the idle window; allow a host preference to keep the model warm. Measure memory/throughput on the actual machine. [Ollama runtime configuration](https://docs.ollama.com/faq).

Memory arithmetic remains useful: 27 billion weights at four bits require about 13.5 GB decimal before quantization metadata, caches, buffers and other allocations; 31 billion require about 15.5 GB. MoE active parameter count is not its weight-storage requirement. These are rough lower-bound calculations, not hardware support claims. The benchmark report must state exact quantization, context, peak memory, GPU/CPU placement, warm/cold timings, and competing workload.

Timeout or cancellation aborts the HTTP request and marks the job accordingly. Verify runtime resource release empirically; cancelling an HTTP client is not proof that GPU work has already stopped. Never kill a shared Ollama service to cancel one request. The scheduler stops admitting dependent work and waits for a confirmed idle/timeout recovery before retrying a competing request. Native processes owned by the worker can be terminated and reaped within their process group.

If a model is unavailable, keep solving/calibration functional, retain accepted evidence, and show a setup/retry state for synthesis or generation. A lower-footprint local model can be selected explicitly after passing relevant quality tests. There is no automatic hosted-model fallback. Browser-model conversion, WebGPU support, and a WASM engine are no longer prerequisites.

### Native full-size construction

Use the current `xfill` path as the baseline. Extract path management, startup/build checks, request parsing, output validation, timeouts and process cancellation into the local-runtime adapter. Extend the lab's hard-coded parameters into a versioned recipe contract: dimensions where supported, word counts, thematic locks, score floors, resource budget, and locked-entry repair. The current executable/validator capability must be reflected honestly in the recipe catalog.

Native construction and clue writing are separate stages. Keep content/sense resolution and the support evaluator independent of the fill implementation. Benchmark accept/reject rate, fill time, repeat diversity, repair success and editor effort on the new content/profile/weekday recipes. Retain the TypeScript solver and small independent oracle for differential tests and future ports; do not rewrite the full-size engine merely to make all runtime code use one language.

Portability now means stable briefs, engine/model ports, token/grammar schemas and reproducible content artifacts. Once the local product is good, another runtime can implement those contracts and run the same quality suite. The product is not held hostage to proving that port first.

## 18. Prompt specifications and context budgeting

Store prompts as versioned templates with schemas and example fixtures; changing a prompt is a behavior change requiring relevant evaluation. These are the required instructions, to be adapted to the verified model's chat format.

### Profile-update prompt

```text
Task: propose a small update to a player's crossword preferences and portrait.
Inputs: explicit locked instructions; current relevant claims; new evidence;
        unresolved contradictions; current portrait excerpt; output schema.

Only claim what supplied evidence supports. Every claim and factual portrait
sentence must cite evidence IDs. Preserve uncertainty and context. Distinguish
knowing, enjoying, wanting to learn, and wanting more tonight. Solving speed
and errors are not evidence of taste. A rejected statement does not imply its
opposite. Never change knowledge counters or explicit locks. Do not infer
private identity or psychological diagnoses. Existing model associations are
untested proposals, not evidence. Return a bounded patch and unresolved items.
```

### Association prompt

```text
Task: propose vivid, varied vocabulary and theme directions that could be worth
trying in a future crossword. The supplied player portrait is partial.

Use the selected seed claims and examples. Explore semantic neighbors, sounds,
etymology, metaphors, and a few surprising contrasts. Explain the connection
briefly. Mark all results as proposals; do not assert the player likes them.
Respect explicit exclusions. Separate factual relations from poetic ones.
Return phrases and parent IDs under the output budget. Do not pad the list.
```

### Clue prompt

```text
Task: write a fair, natural crossword clue for the pinned answer and sense.
Use the pinned weekday recipe and house clue grammar. Declare actual clue
family separately from hint/variant role. Preserve typed punctuation and number,
tense, part-of-speech and register agreement. Explain the intended reading.
Use only supplied facts for factual assertions. Respect language, mechanism,
enumeration, abbreviation and difficulty instructions. Avoid answer leakage.
Give the requested variants, a concise explanation, and supporting source IDs.
If the supplied evidence is insufficient, return insufficient-evidence.
The player's taste may guide the surface, never the truth or grammatical fairness
of the clue. Harder days need richer inference, not broken conventions.
```

### Calibration prompt

```text
Task: propose possible semantic paths from a short sequence of selected objects,
forms, colors, numerals, symbols and words. Use the provided neutral asset
descriptions and presented alternatives. Preserve several possible readings.
Reference observation IDs. Do not infer personality, identity, intelligence,
knowledge or stable desire. Unselected options were not necessarily disliked.
Return at most twelve reversible exploration seeds. Respect explicit language
and weekday choices, which are separate from the visual observations.
```

### Reflection prompt

```text
Task: propose a small set of evocative statements related to this puzzle.
Each must support one narrow, useful content/style interpretation when kept.
State the limited consequence of rejection, or mark it uninterpretable.
Avoid claims about the player's hidden motives or beliefs. Do not flatter,
diagnose, guilt, or pressure the player. Include a reversible scope and expiry.
Statements should remain worthwhile sentences without the recommendation system.
```

### Initial job limits

| Operation                  | Typical input ceiling | Output ceiling | Repair/retry                                            |
| -------------------------- | --------------------- | -------------- | ------------------------------------------------------- |
| Initial calibration paths  | 2,500 tokens          | 1,000          | Use authored branches if late; never block a screen.    |
| Profile patch              | 6,000 tokens          | 1,500          | One schema repair, then retain prior narrative.         |
| Association pass           | 3,500                 | 2,500          | One retry, then reuse eligible unexpired candidates.    |
| Theme planning             | 2,500                 | 1,000          | Two alternative batches within job budget.              |
| Clues for 4–8 entries      | 4,000                 | 2,000          | Retry only failing entries once.                        |
| Three reflection proposals | 2,000                 | 1,000          | Fall back to authored bank.                             |
| Clue challenge             | 2,000                 | 800            | Disagreement becomes review/failure, not endless retry. |

These are configurable safety/resource ceilings, not a requirement to consume them. Set per-job wall time and total puzzle token budgets from smoke measurements; cancel on the aggregate budget even if individual requests remain within their limits. Persist usage and reasons for retry. Never reward verbosity with more profile influence.

## 19. Preparation, responsiveness, and operating cost

### Queue policy

Maintain one ready puzzle by default and at most three when the player explicitly prepares ahead. Run profile synthesis, associative refresh and preparation in host jobs to amortize model loading. Start with one inference request at a time, keep it warm briefly between related jobs, and honor the host’s memory/idle policy. Ordinary cell input never waits on inference. Each stage can be cancelled independently.

Closing the browser does not cancel a durable host job. Preparation continues while Flask’s separately managed worker and Ollama remain running and the host is awake. Persist progress and stage checkpoints; after sleep, service shutdown, or crash, reclaim interrupted work with leases and idempotency. Reopening the UI reconnects to the existing job. A service worker is neither the job owner nor the GPU runtime.

Each queued puzzle records profile revision, hard-policy revision, content version, and recipe. Soft taste changes may leave an already prepared puzzle valid. New hard exclusions invalidate incompatible unstarted queue entries immediately. A started session remains frozen, with an option to leave it. User edits take effect before the next brief even when an LLM portrait refresh is pending. A changed weekday creates a new brief/queue selection; never relabel a queued Monday as Wednesday.

### Job state machine

`queued → resolving → filling → clueing → validating → ready`, with terminal `failed` or `cancelled` states and a recoverable `interrupted` state. Stage outputs have digests; resuming cannot accidentally mix a new profile/content pack with an old fill. A changed brief creates a new job. Queue publication, receipt, and manifest are committed atomically.

### Initial engineering budgets

| Measure                      | Target / handling                                                                                                                                              |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cell input to visible update | p95 under 50 ms on reference devices; no model/fill work on the UI thread.                                                                                     |
| Saved puzzle resume          | p95 under 1 second after cached shell load.                                                                                                                    |
| Reflection screen ready      | Immediate authored/deterministic content; synthesis never blocks completion.                                                                                   |
| Event write overhead         | Bounded batches; measure p95 commit latency and recoverable failures.                                                                                          |
| Full puzzle preparation      | Aim for ≤5 minutes warm on the declared generation device; hard configurable ceiling initially 15 minutes. No readiness claim until measured.                  |
| Cancellation                 | UI acknowledges immediately; target ≤2 seconds to abort owned work. Verify Ollama release separately; never terminate a shared service to satisfy this metric. |
| Model unavailable            | Existing puzzles and editing/preferences work; generation displays an actionable capability state.                                                             |
| Memory/storage               | Publish measured headroom; handle quota/GPU failures without corrupting saved games.                                                                           |

For cost planning use measured quantities:

```text
prepareTime ≈ modelLoad + promptTokens / prefillRate
              + generatedTokens / decodeRate + fillSearch + validation
```

For illustration only, 8,000 output tokens at 30 tokens/second already take about 267 seconds before fill, loading, or retries. This is why a prepared queue and restrained context matter. Measure actual batch output lengths; do not price the product around advertised peak throughput.

Report content-pack/model storage, download bandwidth, elapsed compute, and optional energy estimates on the reference hardware. These costs fall on the application host in the selected local architecture. Artifact distribution, packaging and any later hosted application still have operating costs; calculate them from actual artifact sizes and expected installs before a public launch. Avoid introducing subscription/account infrastructure before content quality and runtime feasibility are established.

## 20. Evaluation: how we establish that this is better

There are four separate claims to test: the puzzle is valid; it is enjoyable; it feels personally relevant; it teaches something when learning is requested. Passing one does not establish the others.

### Automated contract suite

Add fixtures and tests for:

- grid connectivity, numbering, checking, crossing consistency, duplicate answers, token lengths, and immutable manifest integrity;
- impossible support cycles, isolated regions, no-common-letter pairs, and obscure/obscure unresolved cells;
- comparison of support-aware versus support-unaware fills under fixed seeds;
- exact event replay, check feedback, crossing provenance, paste/IME, resumed clocks, hidden tabs, undo, repeated checks, reveal-all, and multiple attempts;
- no mastery from fully crossing-supplied words; no dislike from slowness or abandonment; no inverse belief from a rejected card;
- idempotent analysis and profile commits, stale revision handling, late card responses, concurrent tabs, and deletion during a running model job;
- profile locks surviving repeated summarization, negations, contradictory preferences, and association expiry;
- corrupt/oversized imports, unavailable content packs, old schema upgrades, missing legacy evidence, and partial storage failure;
- model timeout, malformed/truncated JSON, invalid evidence IDs, unsupported facts, and embedded instructions;
- normalization and answer acceptance for the first supported language pair;
- product inference uses the approved host Ollama endpoint; no browser-to-Ollama call, arbitrary runtime URL, hosted-profile upload, or Node dependency in the UI bundle;
- calibration position/salience controls, skip/undo and accessible equivalents; no knowledge or fixed identity inferred from object choices;
- weekday recipe identity survives personalization and queue selection; Thursday mechanics are consistent and inferable; Sunday is not treated as the hardest day;
- clue-grammar agreement and typed punctuation survive generation, rendering, hints, exports and imports; reject morphology and signal defects per family.

Use deterministic fake model outputs in CI; do not download weights in ordinary test runs. Mutation-test changes to the deterministic construction core under the repository's existing rule. Real model benchmarks are separately versioned, opt-in runs with recorded artifacts.

### Human editorial benchmark

Create a legal, original benchmark including common fill, rare but worthwhile concepts, misleadingly familiar spellings, competing senses, localized trivia, long phrases, beginner foreign vocabulary, and excellent/bad examples of wordplay. Include at least six evaluation profiles:

1. English solver unfamiliar with US local politics/sports.
2. Solver who actively loves those topics.
3. Strong vocabulary with little crossword-convention knowledge.
4. Experienced crossword solver bored by habitual short fill.
5. Beginner in the selected foreign language.
6. Sparse/contradictory history with recent preference changes.

These are synthetic test conditions, not a permanent taxonomy for real users. Use domain/native-language reviewers for relevant items. Blind the model identities and preserve disagreements in reports rather than averaging away severe failures.

### Playtest program

**Formative alpha:** 8–12 consenting players over 5–10 puzzles each, deliberately varied in crossword experience and cultural familiarity. Observe where they get stuck and ask about a few specific crossings after play. Use this to correct mechanics and measurement, not to claim statistical superiority.

**Comparative pilot:** 30–50 players over several weeks with randomized puzzle order and within-player comparisons where practical. The unit of analysis is the player/puzzle, not each keystroke as an independent sample. Account for order, learning, novelty, and familiarity with the UI. Determine the confirmatory sample size from pilot variance and a predeclared effect of interest.

Compare:

- generic high-quality puzzles;
- preference-aware answer selection only;
- preference selection plus crossing scaffolding;
- the same system with optional reflection feedback;
- authored visual calibration versus skip/generic opening, controlling presentation balance and measuring first-puzzle relevance, drop-off, confusion and later correction;
- convention-aware contextual hints versus answer-only help, measuring transfer to new examples of the same clue family;
- an ablation using prose-only memory versus the proposed evidence-backed portrait, on synthetic histories and consenting pilot data.

Keep the same editorial floor across arms. To assess fairness, compare clue variants/support choices on matched or comparable grids. To assess full personalization, compare whole puzzles and accept that vocabulary differs. Do not pretend one experimental design isolates every mechanism.

### Measures and their interpretation

| Measure                                                            | What it supports                                       | What it cannot prove                            |
| ------------------------------------------------------------------ | ------------------------------------------------------ | ----------------------------------------------- |
| “Was this worth your time?” and “I would choose another like this” | Direct reported enjoyment and appetite.                | Long-term retention or learning.                |
| Fairness complaints and unresolved crossing review                 | Whether blockers feel arbitrary.                       | That every clue was equally easy.               |
| Supported breakthrough proxy                                       | A delayed entry solved after new crossing information. | A subjective “aha” without player confirmation. |
| Explicit relevance rating                                          | Whether the material feels interesting/personal.       | Accuracy of a psychological profile.            |
| Assistance and completion distribution                             | Challenge/support balance.                             | Pleasure, intelligence, or mastery.             |
| Voluntary next puzzle / return on another day                      | Behavioral willingness to continue.                    | Well-being or learning by itself.               |
| 7/30-day unassisted varied retrieval                               | Retention of selected learning targets.                | Transfer to unrestricted language proficiency.  |
| Profile corrections/undo/regret                                    | Whether interpretation is useful and controllable.     | That silent players endorse all inferences.     |

A breakthrough proxy requires a prior encounter, a new informative crossing, and a subsequent correct player action. Fully auto-completed entries and explicit reveals are excluded. Report it alongside direct player feedback so optimizing the proxy does not replace designing good puzzles.

### Release gates

For an initial supported-device alpha:

- Every published puzzle passes hard structural/source/policy validators.
- Zero unsupported factual clues and zero unresolved obscure/obscure crossing failures in the reviewed release set.
- At least 100 generated full-size candidates across the evaluation profiles and initial day recipes, with pass/reject reasons and generation success/latency distributions recorded; at least 30 accepted puzzles reviewed end-to-end, including at least 10 each for Monday, Wednesday and Thursday before claiming those recipes ready.
- At least 90% of independently reviewed accepted clues rated fair; **every** severe defect is repaired/rejected before use. Average fairness cannot excuse a known impossible letter.
- No critical failures in host/API access, data recovery, profile-lock, deletion or offline reconciliation tests; initial calibration remains optional and accessible.
- The chosen model/artifact meets runtime budgets on the named generation device and passes the frozen task suite.
- Pilot users find the experience worth playing; dissatisfaction patterns have a documented fix or an explicit constrained scope.

For public personalized generation, require a larger held-out editorial evaluation, supported-host/model/engine and client-browser evidence, accessible cached-solver verification, and a positive relevance/enjoyment comparison with confidence intervals. Set the confirmatory minimum effect and sample size after the pilot and before collecting confirmatory outcomes. Do not select a threshold after seeing a favorable result.

For the learning claim, require delayed-retrieval improvement. Until then, describe the feature as vocabulary practice and review.

## 21. Execution sequence and bounded work packages

Implement vertical slices with visible evidence. A task is complete when its acceptance artifact exists, not when an API stub or a model prompt exists. The IDs below can become issue titles after owner review.

### Milestones

| Milestone                          | Visible result                                                                                       | Exit condition                                                             |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| A. Evidence and runtime            | Replayable histories; Qwen/Gemma comparison; production-ready native adapters.                       | What happened in play is trustworthy and full-size host generation works.  |
| B. A fair personal puzzle          | Original Monday, Wednesday and Thursday demonstrations, with support/grammar/mechanic inspection.    | Good routes in; grammar is reliable; Thursday’s discovery is coherent.     |
| C. A memory that improves play     | Nonverbal setup, games and optional cards shape an inspectable next-puzzle brief.                    | Tentative traces remain reversible; corrections stick; relevance improves. |
| D. Learning with useful recurrence | One audited language/domain pack and scheduled review inside good puzzles.                           | Input/linguistic QA passes and delayed-retrieval evaluation is running.    |
| E. A deployable local product      | Current React/Flask app, managed worker/Ollama/native engine, durable queue, export/delete/recovery. | Editorial, runtime, client accessibility and content gates pass together.  |

Feasibility and content work start early. Reflection polish must not consume the schedule while the system cannot construct a good full-size puzzle. Conversely, instrumentation should not require waiting for a perfect production model.

### Backlog with ownership and acceptance

Paths listed as new are proposed additions. Preserve package public exports unless the task explicitly includes a compatibility migration.

| ID  | Scope / owner files                                                                                                               | Depends on              | Deliverable and acceptance                                                                                                                                                                        |
| --- | --------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E01 | **Baseline and contracts:** product `docs/adr/`, `packages/domain/src/`, generator public contract exports                        | Review                  | Record current source state; v2 event/session/puzzle schemas, profile/evidence schemas, compatibility matrix, and failure enums. Old fixtures validate; missing historical fields remain unknown. |
| E02 | **Host storage and browser outbox:** product SQLAlchemy/migrations, `packages/persistence/src/database.ts` and journal adapters   | E01                     | SQLite canonical records plus IndexedDB outbox/checkpoints; migration, idempotency, fencing and offline-conflict tests.                                                                           |
| E03 | **Solve instrumentation:** product application commands and active `apps/react` behavior adapter                                  | E02                     | Actual typing/check/reveal/focus emits replayable events exactly once; immediate solving stays responsive.                                                                                        |
| E04 | **Content foundation:** product `tools/lexicon/`, content schemas/build tooling                                                   | E01                     | Approved pinned English pack, source ledger, normalized senses, coverage report, factual quarantine, 100% provenance for release candidates.                                                      |
| E05 | **Model comparison:** generator `apps/lab/` experiment runner and fixtures                                                        | E01                     | Smoke and blind comparison across exact Qwen/Gemma artifacts; quality/latency/memory report; no unsubstantiated winner.                                                                           |
| E06 | **Native runtime extraction:** generator `packages/local-runtime/`, lab adapters and product runner protocol                      | E01, E05 smoke          | Ollama/native adapters shared by lab and product; model/artifact readiness, bounded cancellation, memory/timing and full-size fill acceptance report. No browser-port gate.                       |
| E07 | **Deterministic analysis:** product `packages/domain/src/observations.ts`, `packages/application/src/analyzeSession.ts` (new)     | E02, E03                | Hand-labeled trace fixtures produce expected retrieval/support/exposure outcomes and uncertainty; no taste changes from timing/errors.                                                            |
| E08 | **Content retrieval and briefs:** product application projection compiler; generator `constructionUseCases.ts` and resolver port  | E01, E04, E07           | Profile brief filters and ranks full eligible lexicon plus validated model candidates. Hard exclusions win; cold-start brief works.                                                               |
| E09 | **Scaffolding evaluator:** generator `packages/construction/src/scaffolding.ts`, `solveSimulation.ts` (new)                       | E04, E08                | Support DAG/certificates, cycle and island fixtures, no-common-letter test, finalist simulator, and lab inspector. Independent hand-reviewed cases agree.                                         |
| E10 | **Grounded clue pipeline:** generator language jobs/orchestration and lab review UI                                               | E04, E05, E20           | Sense/fact-bound variants with typed grammar/signal spans; per-family validators and challengers; complete reviewed clue/hint/explanation bundle.                                                 |
| E11 | **Integrated personal construction:** generator pipeline, native fill/repair, day-aware validators                                | E06, E08–E10, E21       | Full-size Monday, Wednesday and genuine Thursday examples across profiles; immutable receipts, support reports and honest failed-candidate reasons.                                               |
| E12 | **Profile synthesis:** application update/validation code, Node runner, host revision repository                                  | E05, E07, E22           | Evidence-bound patches, locks, contradictions, CAS/idempotency, rebuild and deletion tests; retains deterministic evidence when model fails.                                                      |
| E13 | **Associative field:** product association repository/projection code; generator language jobs                                    | E08, E12                | Varied proposal graph, bounded recursion, expiry, lexicon resolution, selection log. Generated repetition never becomes evidence.                                                                 |
| E14 | **Reflection deck:** product authored-card pack, `ReflectionDeck` UI and response use cases                                       | E12                     | Accessible keep/not-for-me/pass/undo; fixed pre-response mappings; 60–100 reviewed cards; skipped cards have no preference effect.                                                                |
| E15 | **Existing-app integration:** `apps/react`, Flask original-puzzle API and setup targets                                           | E03, E11, E19, E22      | Calibration→weekday→host preparation→solve→reflection in the current app; samples, cached play, reconnect, cancel and restart recovery. No new `apps/web` migration.                              |
| E16 | **Your words and portability:** product profile editor, evidence UI, continuity archive v2, deletion/retention jobs               | E12–E15                 | Readable profile with traceable changes; edits affect next brief; export/import round trip; full deletion and no resurrection under late jobs.                                                    |
| E17 | **Learning pack and scheduler:** product domain scheduler, content pack tooling, input-token support, learning UI                 | E04, E07, E11, E15      | One language pair reviewed; Unicode/input tests; due-word budget respected; assisted and independent recall separated; delayed recall study fixtures.                                             |
| E18 | **Pilot and hardening:** both repos’ evaluation tools, tests and docs                                                             | E11–E17, E19–E22        | Compare resonance and convention learning; blind day classification; per-family grammar/Thursday review; host/client reliability and release report.                                              |
| E19 | **Associative opening and initial calibration:** `apps/react/src/calibration/`, stimulus pack, calibration use cases/host records | E01, E02                | Five short movements with authored balanced stimuli; pass/undo/restart/accessibility; competing low-weight seeds; explicit weekday choice separate from convention practice.                      |
| E20 | **House clue grammar:** domain `clueGrammar.ts`, `tools/clue-grammar/`, model schemas and renderer spans                          | E01, E04                | Versioned family/role/grammar distinction; original valid/invalid fixtures; morphology, punctuation, cross-reference tests; contextual convention hints and familiarity evidence.                 |
| E21 | **Weekday recipes and mechanics:** generator recipe/mechanic registry, native adapter, token model, solver input/rendering        | E01, E04, E06, E09, E10 | Day-specific editorial targets; ordinary Monday/Wednesday and one genuine Thursday family; token-safe rebus support as a separate capability; explicit Sunday size gate.                          |
| E22 | **Host API and durable jobs:** Flask `api_v1/`, `jobs/`, product Node runner and process setup                                    | E01, E02, E06           | Same-origin API, leases, frozen inputs, persisted progress, CAS publication, worker restart/cancel, bounded runtime resources, no direct browser/Ollama coupling.                                 |

E05, the authored E19 opening, and contract/content work are independent enough to execute concurrently if a later implementation owner chooses multiple agents. File ownership must be assigned explicitly and shared contracts agreed first. This plan itself does not require spawning agents or creating tasks before review.

### Effort and uncertainty

Budget provisionally 55–95 focused engineering days plus editorial/language review and several weeks of overlapping playtest time for the expanded initial release scope, including a real Wednesday/Thursday experience and the associative opening. This is a planning range, not a measured estimate or delivery commitment. Corpus cleanup, native mechanism support, reliable multi-token input and host/outbox reconciliation can materially expand it; browser porting and a new static UI are removed from the critical path. Re-estimate after E06 and E11, using actual preparation speed, fill acceptance rate, and human editing time per puzzle.

Do not parallelize away unknown interfaces. The critical path is **trustworthy events/content → viable runtime → fair grounded full-size construction → meaningful personalization evaluation**. A future business model, account-based cross-device sync, public sharing network, attributed multiplayer, every language, cryptics and Sunday-scale special grids are later capabilities with separate acceptance criteria. Wednesday and a genuine Thursday are core early proof points, not deferred indefinitely behind Monday.

## 22. First implementation handoff

After review, the next agent should read this document, the two `AGENTS.md` files, their repository maps, the accepted ADRs, and the current working-tree status. It should not repeat the whole product-design exercise.

### First change: E01 plus a narrow E02/E07 walking skeleton

Implement the smallest slice that makes personalization evidence real:

1. Define `SolveEventV2`, `SolveSessionV2`, `EntryObservation`, and `SessionAnalysis` with runtime validators.
2. Add a pure replay/analysis reducer using synthetic, provenance-approved puzzles.
3. Add session-ID-based journal persistence with a single browser migration owner and canonical host migrations; fake the API port only in labeled tests.
4. Preserve v1 readers and mark unsupported historical observations explicitly.
5. Export one locally inspected analysis report from an actual instrumented solve path or a clearly labeled synthetic browser fixture.

Alongside this foundation, deliver the authored E19 opening in the existing React UI with a clearly labeled calibration trace/seed inspector and a reviewed sample puzzle. Use approved assets and deterministic branches before requiring model-generated interpretation; the experience should be reviewable early.

Do not start by asking an LLM to rewrite a paragraph from the existing incomplete events. The foundations must distinguish what a player supplied from what the grid supplied before a model can interpret either.

### Required trace fixtures

| Fixture                                                            | Expected interpretation                                                                   |
| ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| Player enters a correct answer from a blank pattern without checks | Independent retrieval candidate with its clue/sense/task ID.                              |
| Player solves two crossings, then fills the target                 | Supported retrieval with exact prefilled positions; no duplicate credit for shared cells. |
| All target letters arrive from other entries                       | Exposure only, even if completion animation fires.                                        |
| Wrong word → check → corrected word                                | Engaged failed attempt plus feedback-assisted correction, bounded per-session update.     |
| Reveal one letter and finish                                       | Correct assistance tier, no unassisted mastery claim.                                     |
| Paste entire answer                                                | One batch action with limited knowledge evidence; typing speed is uninterpretable.        |
| Long pause with tab hidden, followed by a fast answer              | Hidden time excluded; no delay-based dislike/ability inference.                           |
| Player leaves half the grid untouched                              | Unknown observations for unengaged entries; no domain aversion.                           |
| Duplicate finish event / job retry                                 | One analysis/evidence contribution and at most one accepted revision per bundle.          |
| Two tabs edit the same session                                     | Fenced single-writer behavior; no interleaved sequence corruption.                        |
| User corrects a preference while synthesis is running              | Stale proposal is rejected/rebased; correction survives.                                  |
| User deletes a profile while a generation job is running           | Late output cannot restore the profile or private queue.                                  |
| A reflection is passed or undone                                   | No lasting preference update for pass; undo retracts the response's contribution.         |
| Legacy v1 completed snapshot without focus history                 | Preserved solve state; no fabricated unaided retrieval.                                   |

### Example end-to-end acceptance story

Start with a profile whose explicit instruction is “fewer US officeholder clues,” whose saved words include some acoustic terms, and whose knowledge of a selected unfamiliar name is unknown. Create a puzzle containing a small number of relevant long entries and a worthwhile unfamiliar answer with verified support.

The player solves one region unaided, resolves the unfamiliar answer with crossings, checks a mistaken letter elsewhere, and finishes. The analysis records independent retrieval, supported exposure, and check-assisted correction separately. The next profile revision retains the explicit topic preference and does not infer dislike from the checked word. A card about etymology is kept; a metaphorical map card is passed.

The next generation brief includes a modest etymology direction, no learned preference from the pass, and no unsupported claim that the unfamiliar answer is mastered. The selected weekday is preserved, and any initial object associations remain tentative unless later endorsed. The completed puzzle remains byte-for-byte unchanged. Export/import preserves these distinctions. Deleting the first session removes its derived evidence on rebuild without removing unrelated user-authored instructions.

### Required implementation evidence

For each change, include affected contracts, migration behavior, deterministic test results, any actual browser verification, unresolved limitations, and relevant benchmark artifacts. Never present fake-adapter success as actual model quality.

Run the repository-prescribed checks appropriate to the change:

```sh
# In crossword: existing gates, plus targeted suites for changed packages.
make test
npm run typecheck
npm run lint
npm run format:check
bash .scripts/generate-repo-map.sh
bash .scripts/generate-repo-map.sh --check

# In crossword-generator: existing package/lab quality gates.
make check
npm run lab:test
npm run lab:build
# Required when changing the construction CSP or its tests:
make mutation-test
```

Do not run private live-provider tests without the existing explicit opt-in. Run the actual `apps/react` build/browser gates, new Flask API/worker tests, SQLite migration/restart/outbox reconciliation tests, and controlled native/Ollama smoke tests. A future `make run-personal` target must be tested from a clean setup. Real-model benchmarks are dedicated opt-in E05/E06 commands with documented prerequisites and budgets.

Release generator archives, including the Node-only local-runtime package and pinned native-artifact manifest, with new versions and update the product's declared file dependencies/lockfile through npm. Never overwrite an existing package archive version. Regenerate each repository's map after module additions. Do not commit unrelated local changes or reformat the entire codebase to deliver one slice.

## 23. Risks, decisions for review, and chosen defaults

### Risks with concrete responses

| Risk                                                               | Earliest detection | Response                                                                                                                   |
| ------------------------------------------------------------------ | ------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| Large models exceed host memory/latency budgets                    | E05/E06            | Benchmark exact local artifacts/context; run one model job at a time, prepare ahead, publish a supported host profile.     |
| Personalized pools destroy fill quality                            | E08/E11            | Preserve the broad eligible lexicon; limit theme locks; rerank and repair rather than forcing every answer to be personal. |
| Simulation approves puzzles people find unfair                     | E09/E18            | Review specific failed crossings; recalibrate conservative priors and reject unsupported probability claims.               |
| Portrait becomes repetitive or self-confirming                     | E12/E13            | Evidence rebuilds, separate speculative origins, expiry, diverse exposure and correction tests.                            |
| Reflection wording is loved but its mapped topic is not            | E14/E18            | Narrow/soft mappings, transparent effect preview, counterevidence, undo and follow-up puzzle evaluation.                   |
| Player is skilled at a disliked subject                            | E07/E12            | Keep skill and taste separate; explicit preference controls selection.                                                     |
| Crossings masquerade as vocabulary learning                        | E07/E17            | Distinct assisted/exposure channels and delayed unassisted probes.                                                         |
| Fact/clue verification is too expensive                            | E04/E10            | Use compact grounded packs and reusable reviewed clue families; reject uncertain candidates.                               |
| Good grids require excessive manual editing                        | E11/E18            | Measure edit minutes and acceptance rate; improve candidate/content quality before scaling generation.                     |
| Calibration reflects salience/accessibility rather than preference | E19/E18            | Balance presentation, record alternatives/mode, use weak initial weights, test against a skipped opening.                  |
| Models produce polished but grammatically dishonest clues          | E20/E10            | Original positive/negative grammar fixtures, morphology/semantic checks and per-family editorial review.                   |
| Thursday becomes an arbitrary trick or a disguised Wednesday       | E21/E18            | One coherent mechanic, multiple inferable instances, accessible input, blind day review; never silently relabel.           |
| Long preparation breaks “one more”                                 | E06/E15            | Ready queue, batching, one loaded model, bounded output, clear preparation timing.                                         |
| Small profile becomes narrow and monotonous                        | E08/E13            | Broad-content floor, diverse retrieval, expiry of weak hypotheses, distinct current mood and durable preference.           |
| Storage loss or model failure erases trust                         | E02/E16            | Atomic commits, honest failure UI, export, corruption tests, no silent in-memory fallback for durable profiles.            |

### Review decisions with recommendations

These are choices for reviewing the finished design, not unanswered questions that prevent building the schemas and experiments.

| Decision                 | Recommended default                                                                                                             | Why                                                                                          |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Initial product promise  | Excellent personal English 15×15 puzzles with an unusual nonverbal opening and credible Monday, Wednesday and Thursday recipes. | Proves the desired aesthetic and learned clue language early.                                |
| Initial calibration      | Five short visual/relational movements, optional practice and explicit weekday selection; no opening desire questionnaire.      | Establishes the tone while keeping early meanings open and reversible.                       |
| Clue language            | One versioned house grammar with morphology, signal spans, convention teaching and day-specific editorial review.               | Learning the language should carry forward across puzzles.                                   |
| Model experiment         | Qwen3.8 27B, Gemma 3 27B, Gemma 4 31B, Gemma 4 26B A4B.                                                                         | Resolves the naming ambiguity and tests writing, structure and runtime separately.           |
| Runtime                  | **Accepted:** existing React/Flask app, canonical host SQLite, durable worker, Ollama and native `xfill`.                       | Owner instruction supersedes browser-only requirements; later ports use preserved contracts. |
| Player representation    | Evidence-backed prose plus an open concept graph and separate speculative association field.                                    | Keeps expressive freedom, reliable updates, and useful learning history.                     |
| Reflection               | Three optional keep/not-for-me/pass cards, with visible controls and undo.                                                      | Invites resonance without turning every game into an interview.                              |
| Default tone             | Intelligent, playful, occasionally strange; deeper associative mode is optional.                                                | Entertainment remains complete while leaving room for more personal exploration.             |
| Challenge adaptation     | Explicit weekday recipe, with personal topics/support and optional convention hints inside its contract.                        | A requested Wednesday/Thursday stays recognizably that day.                                  |
| Privacy/research         | Local application-host profiles; accurate client/host disclosure; no account for local use; explicit research exports.          | Supports detailed memory without a hidden hosted inference requirement.                      |
| Learning launch language | English↔German reference pack, replaceable before content work.                                                                | Gives implementation a concrete test target without assuming every user's goal.              |
| Release standard         | Human-reviewed day/grammar/mechanic/model graduation and measured host performance/recovery.                                    | Filled grids must also deliver consistent language, fair discovery and reliable play.        |

### What approval means

The owner has already authorized the local Ollama/native architecture, nonverbal setup direction and weekday/convention priorities. Detailed design review refines the implementation backlog and editorial defaults; it does not reopen the abandoned browser-only constraint. Begin with the current-app calibration slice, trustworthy evidence, host/runtime integration and day-specific quality proof. Public release and empirical learning claims still require their stated evidence. Numerical settings are versioned initial defaults to validate and improve.

The outcome to aim for is concrete: a player repeatedly finds a way into something they did not know, sees their expressed tastes reflected without becoming trapped by them, and returns because the next puzzle promises another worthwhile discovery.

## 24. Sources and evidence boundaries

The design and numeric targets in this document are proposals. External sources establish the narrow facts cited in their sections; they do not validate the complete personalization system or guarantee model performance.

| Source                                                                                                                                                             | Used for                                                                                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| [Google Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4) and [official model collection](https://huggingface.co/collections/google/gemma-4) | Correct model family/variant identities and distinction between total and active parameters.                                               |
| [Google Gemma 3 27B card](https://huggingface.co/google/gemma-3-27b-it)                                                                                            | The distinct 27B Gemma candidate.                                                                                                          |
| [Qwen3.8 27B card](https://huggingface.co/Qwen/Qwen3.8-27B)                                                                                                        | Upstream baseline identity; not a crossword-writing endorsement.                                                                           |
| [Ollama chat API](https://docs.ollama.com/api/chat), [model list](https://docs.ollama.com/api/tags), [runtime configuration](https://docs.ollama.com/faq)          | Local runtime request/identity/options and measured resource setup.                                                                        |
| [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)                                                                               | JSON Schema support for the shared product/lab local model adapter.                                                                        |
| [Roediger and Karpicke, 2006](https://www.psychologicalscience.org/journals/psychological-science/j.1467-9280.2006.01693.x/)                                       | Retrieval practice motivation, not proof of crossword learning.                                                                            |
| [Settles and Meeder, 2016](https://aclanthology.org/P16-1174.pdf)                                                                                                  | Spaced repetition/recall modeling reference, with explicit task-transfer limitations.                                                      |
| [UN biographical note](https://documents.un.org/api/symbol/access?l=en&s=S%2F1996%2F1021&t=pdf)                                                                    | The ATTA worked example.                                                                                                                   |
| [NYT Crossword help](https://nytimes.zendesk.com/hc/en-us/articles/360052406391-The-New-York-Times-Crossword-Puzzle)                                               | Published weekday progression and the distinction between Sunday size and midweek difficulty; the detailed solving guide was inaccessible. |
| [Puzzazz solving guide](https://www.puzzazz.com/how-to/crosswords)                                                                                                 | Broad American clue conventions; our implementation grammar, examples and validators are original specifications.                          |
| [Rachel Fabi interview](https://www.upstate.edu/informed/2021/121021-fabi-podcast.php)                                                                             | Constructor/Wordplay writer's account of learning recurring clue signals.                                                                  |

Repository evidence: current `src/crossword/{app,database}.py`, `apps/react/src/main.jsx`, and `packages/domain/src/{puzzle,session}.ts`, `packages/persistence/src/{sessionRepository,puzzleRepository,archive}.ts`, `apps/react/src/main.jsx`, root workspace manifests, `tools/lexicon/source-ledger.json`, ADRs 0001/0002 and the superseding ADR 0003, and generator `apps/lab/server.ts`, `packages/{construction,model-runtime,generator}/src/`, and `docs/plans/FULL_SIZE_CONSTRUCTION.md`. The implementation owner must re-check changed interfaces at task start because both repositories are actively being edited.
