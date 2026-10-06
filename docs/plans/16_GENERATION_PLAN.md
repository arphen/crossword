# Generation plan: wordplay lanes, weekday voices, a learning lexicon, and a model we own

Execution plan, 6 October 2026. This note replaces the earlier note 16, *Clue quality recovery* (`16_CLUE_QUALITY_RECOVERY.md`, last present at `d59a3ab`; read it with `git show d59a3ab:docs/plans/16_CLUE_QUALITY_RECOVERY.md`). Its diagnosis still holds and is summarized in §1; its `Q01`–`Q09` queue was executed during 1–3 October and is closed by this note. [The active specification](06_PERSONAL_EPISTEME.md) keeps ownership of the backlog; the workstreams below are `G` rows that amend `E04`, `E05`, `E10`, `E12`, `E13`, `E17`, `E20` and `E21`. The completion rule is unchanged: *a task is complete when its acceptance artifact exists, not when an API stub or a model prompt exists.*

## 0. What the owner asked for (6 October)

1. **Local first.** Generation runs on the owner's Apple M3 Pro with 16 GB unified memory, with no network, and a full puzzle is ready in under ten minutes.
2. **Good clues.** The NYT clue grammar is the point: `?`, `"quoted speech"`, `[brackets]`, `___` blanks, `for short`, `e.g.`, language cues and the rest. Every grammar gets its own prompt with its own examples.
3. **Weekday personalities.** Monday to Saturday rise in difficulty as the NYT week does, and each day has a recognizable voice. The owners currently solve Wednesdays and are working up.
4. **Knowledge worth having.** World and European knowledge — Nobel laureates, scientists, philosophers, rivers, languages — over US senators and US associations. The solve should leave a satisfying, slightly addictive sense of having learned something.
5. **The episteme.** The puzzle as a Rorschach for the desire to know: the chain of signifiers slides, and the profile updates and understands each solver better over time.
6. **Multilingual.** The owners live in Berlin and between them speak English, German, Slovenian, Spanish and Polish. English is the everyday language; the other languages are an opportunity, not noise.
7. **Cloud as an extension.** A hosted model (for example through an OpenAI-compatible gateway such as OpenCode Zen) is welcome as an optional extension behind an adapter. Nothing may depend on it: models get deprecated, keys expire, and the product must keep working when they do.
8. **A model we own.** Fine-tuning a smaller model to be much better at crossword clues is a goal, not a rejected idea.

## 1. Where generation stands

The pipeline is now very good at not making mistakes and nearly incapable of making jokes. The 3 October benchmark runs (`private-clue-benchmark-v1.20261003.json`) admit 13–15 of 15 clues with zero guard hits, and 12–15 of those are plain definitions; the gold (wit) rate in `research/gemma-editor/rescore/table.md` is 0 on every judged board. Literal clues are not one bug. They are the equilibrium the system converged on, for three reasons.

1. **The models cannot do it, and the judge cannot see it.** The drafter is `llama3.2:3b` and the judge `gemma3:4b`, chosen to fit the host. A pun needs two senses plus a surface that reads naturally both ways, which is close to the hardest thing a 3 B model can be asked. The judge marked 9 of 15 known-good clues unsound (`private-clue-judge-calibration-v1.20261003.json`) and, after recalibration, still solved 0 of 20 controls. Keep/revert decisions taken against it were mostly noise.
2. **The objective rewarded safety.** Strict admission rejects any `?` clue the 50-entry homograph ledger cannot witness, so attempting wordplay is a risk and a definition always passes. The benchmark was 15 Monday answers — a day the published census puts at about 92 % definitions — on one seed, with unseeded decoding whose run-to-run spread is as large as the effects measured (`private-clue-decision-v1.20261003.json`).
3. **The model was asked to invent the mechanism.** The draft instruction is "Write original, lively crossword clues" over a batch of answers. Wordplay is mostly search — find the second sense, the reparse, the hidden word, the sound-alike — followed by phrasing. The pipeline gives the search to its weakest component.

**What carries over.** The Muse-era ideas were mostly right; their execution was not. Keep: witness-before-label (`clue_witness.py`), the candidate set with a comparison call (`clue_candidate_admission.py`), the local clue corpus (`private_clue_corpus.py`), the leak, derivation and grammar guards (Q01), the census against published clue shapes, steered redrafts, and the counts-only evidence discipline. The failures were procedural: nearly every idea shipped behind an env flag that is off by default; each was tested against an n = 15 Monday benchmark with a broken judge, so nothing could win; the owner-judged specimen ledger (Q02) was never filled; and `private_puzzle_generation.py` grew to about 8,100 lines.

**Stop doing.** Do not add another anchored regex or family floor. Do not run another acceptance decision on an automated judge that has not first agreed with owner labels. Do not ship a feature as a default-off flag; it either enters a weekday recipe or is deleted.

## 2. Principles

1. **Mechanism before prose.** Every non-definition clue starts as an *angle*: a concrete, checkable mechanism with its witness (two senses, a split, a span, a homophone). A model is asked to phrase an angle, never to invent one.
2. **Local is complete.** The full product — fill, clues, learning, profile — runs offline on the owner's machine. Cloud output is either cached data with provenance (it keeps working after the provider disappears) or an optional extra drafting/judging lane that the recipe can switch off without any other change.
3. **The profile never leaves the machine.** A cloud call may carry answers, senses and angles; it never carries profile, journal or reflection data. This keeps ADR 0003's default intact.
4. **Difficulty is indirection, not obscurity.** Later weekdays are harder because clues are more oblique, not because the fill is more trivial-pursuit. That is also what makes learning possible.
5. **People judge; machines are calibrated against them.** The preference signal comes from play, ten seconds per puzzle, not from labeling sessions.
6. **Recipes, not flags.** Behaviour lives in versioned weekday recipe and lane files that a receipt can name.

## 3. Pipeline and time budget

```text
profile + lexicon ──▶ per-user word weights ──▶ xfill fill (15×15)
                                                    │
        angle finder (deterministic, per entry) ◀───┘
                    │
   weekday recipe ──▶ lane router ──▶ lane drafts (k per entry, local model)
                                            │
         admission: leak/grammar/witness guards (existing)
                                            │
         selection: deterministic ranking, then one comparison per entry
                                            │
         board pass: lane mix, repeated pivots, clue-length rhythm
                                            │
                               prepared puzzle (receipt) ──▶ play ──▶ ratings + episteme signals
```

Puzzles are prepared ahead: while the owners solve one, the next is generated by the existing durable job path (`E22`). The ten-minute limit is therefore a ceiling for a cold start, not the experienced wait.

| Step (Wednesday, ~76 entries) | Estimate on M3 Pro | Basis |
| --- | --- | --- |
| Word weights + xfill fill | < 1 min | existing native runs |
| Angle finder | seconds | lookups, no model |
| ~170 short drafts (k = 3 wordplay, k = 2 definition) at ~20 tokens | 4–5 min | ~15 tok/s for a 12–14 B model at 4-bit; to be measured |
| Comparison + board pass | ~1 min | one short call per contested entry |

These are estimates from memory bandwidth (150 GB/s on the M3 Pro) and must be replaced by the `G1` receipt. On 16 GB the realistic ceiling is an 8–14 B model at 4-bit with `sysctl iogpu.wired_limit_mb` raised modestly; 26 B+ models and ~30 B mixture-of-experts models do not fit.

## 4. Workstreams

| ID | Scope | Depends on | Deliverable and acceptance |
| --- | --- | --- | --- |
| G1 | **Model adapters and host bake-off.** One `ClueModel` interface with a local runtime adapter (Ollama today; llama.cpp or MLX possible) and an optional OpenAI-compatible cloud adapter configured by URL, model name and key. Registry tiers `local` / `cloud-extension` / `fixture`. Seeds pinned and echoed in every receipt. Amends `E05`, `E06`. | — | `private-host-model-tiers-v2.m3pro-16gb-<date>.json`: tok/s, peak resident memory and schema-failure rate for three or four 8–14 B candidates. A full Wednesday generated end to end in under ten minutes on the chosen local model. The test suite proves generation with the cloud adapter unconfigured and the network unavailable. |
| G2 | **Play-time judgment.** After a solve, each player may tap a best and a worst clue, and mark a wordplay clue *loved* or *meh*. Stored locally, answer-bearing, outside the evidence tree; counts and digests commit. Loved clues may be promoted into lane exemplars. Replaces the Q02 labeling session. | — | Ratings captured from real solves; `private-clue-preference-attestation-v1.<date>.json` with counts. Any automated judge is admitted only after it agrees with these labels at a rate stated in its receipt. |
| G3 | **Angle finder.** Per entry, list angles with witnesses: multiple senses (admit the OEWN pack under `E04` in place of the 50-entry ledger), compound splits and reparses from the word list, hidden words, homophones from a pronunciation dictionary, capitonyms (*polish/Polish*), `-er` agent readings, Wikidata descriptions and aliases, and cross-language false friends (`G8`). Feeds `clue_witness.py`, so a `?` clue is witnessed by construction. | — | Angle coverage report over a fixed Wednesday word set: share of entries with at least one wordplay angle, by angle type. Unit tests per angle type. |
| G4 | **Grammar lanes.** One prompt file per lane, each with 4–6 exemplars, the witness it requires, and its admission check: `?` misdirection/pun, spoken equivalent `"…"`, nonverbal `[…]`, fill-in-the-blank, abbreviation (`for short`, `Abbr.`), category (`e.g.`, `for one`, `perhaps`), language cue, hidden word, cross-reference, plain definition, and *oblique definition* (fair but deliberately ambiguous). A router assigns each entry a lane from its angles and the weekday recipe. Prompt prefixes stay stable so the runtime can cache them. Supersedes the env-flag lanes (`ROUTE_*`, `ABBREV_LANE`, `GERUND_MATCH`, `DELIMITED_DRAFTS`, `WEEKDAY_EXEMPLARS`). Amends `E10`, `E20`. | G3 | Lane files under version control with exemplar provenance (owner, original, promoted from G2, or cloud-generated and cached). On the Wednesday benchmark: lane mix matches the recipe within one entry per lane, and the G2 loved-wordplay rate beats the current pipeline's on the same grids. |
| G5 | **Weekday voices.** A recipe per weekday: share of entries routed to wordplay lanes, allowed lanes, obscurity ceiling for fill, ambiguity level of definitions, clue length, and the Thursday trick slot. Monday friendly and literal; Wednesday playful; Thursday a trick; Friday and Saturday oblique and terse. Amends `E21`. | G4 | Recipe files for Monday–Saturday; Wednesday and Thursday validated first, the others as the owners move up. A blind owner check that adjacent weekdays are distinguishable on the same answers. |
| G6 | **World lexicon and adaptive weights.** A Wikidata extract (CC0) of people, places, works and concepts, ranked by the number of Wikipedia language editions per entity — a European-neutral notability signal that puts CURIE above a state senator. Domain packs per note 11 (Nobel laureates first). A penalty for entries notable only in one country's edition. Per-user weights recomputed before each fill: fill quality × global notability × the solver's affinity × learning value. Spaced repetition: an entry the solver revealed or struggled with returns days later with a different angle. New entries are placed where crossings the solver knows support them (`E09`). A short post-solve card names what was new. Amends `E04`, `E17`. | G1 | A Nobel/science pack and the US-only penalty in the fill path; a receipt comparing US-only entry rates before and after on fixed seeds; repetition scheduling visible in the puzzle receipt. |
| G7 | **Episteme loop.** Signals from solve instrumentation (`E03`): where the solve starts, dwell time, reveals, entries solved without crossings, post-solve cards opened, ratings. These update tentative *threads* (associative directions, never labels). Each puzzle seeds a few entries from live threads and a few wild ones, so the chain keeps sliding rather than closing into a profile. Threads stay inspectable, editable and resettable. Amends `E12`, `E13`. | G2, G6 | Thread updates recorded in the profile revision history with the evidence that moved them; one puzzle whose receipt shows which entries came from which thread and which were exploration. |
| G8 | **Multilingual.** Three steps. (1) Extend the NYT-native language-cue lane to German, Slovenian, Spanish and Polish answers in an English grid. (2) A false-friends lane where one spelling slides between languages (*Gift*: present in English, poison in German). (3) Mixed-language grids, which need a merged word list and an explicit diacritic-folding rule (Č→C, ß→SS, Ł→L, Ñ→N). Each solver's languages come from their profile. Amends `E04`, `E20`. | G3, G4 | Steps 1–2 as lanes with exemplars and witness checks; step 3 as a recipe once the folded word list passes fill-quality checks. |
| G9 | **A fine-tuned clue model.** LoRA/QLoRA on a 3–8 B base with MLX on the M3 Pro, for the narrow task *(answer, angle, lane, weekday) → clue*. Data: owner-loved and owner-edited clues (G2), admitted lane outputs, angle-and-witness records, and optionally cloud-teacher drafts cached under G1 where the provider's terms permit training on outputs. Later, preference tuning (DPO/ORPO) on G2 pairs. The adapter is a versioned local artifact: it survives any provider change, and a base-model swap retrains rather than breaks. | G2, G4 | `private-clue-finetune-v1.<base>-<date>.json`: base model, data counts by source, training time and memory on this host, and a blind G2-scored A/B against the same base without the adapter on the Wednesday benchmark. A loss is a valid deliverable. |
| G10 | **Cleanup.** Collapse env flags into recipe/lane files; move the clue pipeline out of `private_puzzle_generation.py` into modules; delete losing lanes; retire strict admission's blanket rejection of unwitnessed `?` once G3 supplies witnesses. Keep the leak, derivation and grammar guards. | — | No `CROSSWORD_*` clue-behaviour flags remain outside recipe files; the generation test suite stays green throughout; each move is its own commit. |

## 5. Sequencing

1. **Foundations:** `G1`, `G2` and the `G10` skeleton (recipe file format, module split). The first artifact is the bake-off: thirty Wednesday answers clued by the current pipeline, by the best local candidate using hand-picked angles and lane prompts, and by a cloud model through the extension adapter, judged blind by the owners. It settles how far local can go and what the cloud is actually for.
2. **Clue quality for Wednesday:** `G3`, `G4`, `G5` for Wednesday and Thursday.
3. **Learning and desire:** `G6`, then `G7`.
4. **Reach:** `G8` steps 1–2, then `G9` once G2 has a few hundred judgments and G4 produces clean lane outputs to learn from; `G8` step 3 last.

## 6. Measurement

- **Benchmark:** a fixed set of Wednesday grids (fixed fill seeds), at least three boards per arm, with model seeds pinned and echoed. Monday stays a regression check, not the target.
- **Primary metrics:** the owners' keep rate and loved-wordplay rate (G2), and lane mix against the recipe. **Secondary:** wall time, guard hits, schema failures, US-only entry rate.
- **Automated judges** (local or cloud) are instruments to be calibrated against G2 labels, never acceptance criteria on their own.
- **Evidence rules** from the earlier note stand: receipts are counts-only with `version`, `scope`, `interpretation`, `uncertainty` and `studyDigest`; anything answer-bearing (ratings, lane exemplars promoted from play, the clue corpus) stays outside `docs/evidence/` and commits only its counts and digest.

## 7. Open owner decisions

1. **The published-clue archive.** ADR 0003 §8 says the private provider corpus is not training or evaluation data, yet the census and route-context work used the local NYT archive (counts and local-only context). Mining it for angles, exemplars or fine-tuning data needs an explicit decision: either amend ADR 0003 for strictly private, never-distributed use, or keep it out and build exemplars and training data from original, owner and cached-cloud sources. Until decided, `G4` and `G9` use only the latter.
2. **One profile or two.** The owners solve together. Threads, weights and repetition can be per person, per couple, or both with a shared view.
3. **The local base model.** Chosen by the `G1` bake-off, not in advance.
4. **The cloud extension's credentials.** An API key and endpoint the app can call (not only a CLI login), stored outside the repository.

## 8. First action

`G1`: the adapter interface with the cloud adapter optional and off by default, the host receipt for three or four local candidates, and the thirty-answer blind bake-off. Everything after it is ordered by what that comparison shows.

### G1 status (6 October)

Built, offline-tested, and awaiting the owner's machine:

- `src/crossword/clue_model.py`: the `ClueModelAdapter` seam behind `_chat`. A plain tag is the unchanged local Ollama call; `local:<name>` is a loopback OpenAI-compatible server (llama.cpp, MLX); `cloud:<name>` is the optional extension, off unless `CROSSWORD_CLOUD_CLUE_ENABLED=1` and configured by `CROSSWORD_CLOUD_CLUE_URL` / `_API_KEY`. Cloud calls must declare a clue-writing purpose and a clue-shaped JSON payload or they are refused; `_chat` call sites that are not yet labelled therefore cannot reach the cloud. Failures surface as the exceptions callers already handle, so a retired provider degrades to scaffolds. A content-free call trace records seed, temperature, token budget and timing.
- `local-mid` registry tier (`llama3.1:8b`, `qwen3:8b`, `gemma3:12b`, `qwen3:14b`): admissible when named, deliberately last in the automatic order. The memory ceilings are estimates until the host receipt replaces them, and the list is a starting set to be checked against what is installed (including smaller Gemma 4 variants), not a recommendation.
- `scripts/clue-bakeoff.py` with `src/crossword/clue_bakeoff.py`: `pipeline` clues the answers with the current pipeline (placeholders left out as missing), `prepare` drafts further arms and writes a shuffled, unlabelled `sheet.html` plus a secret key, and `score` turns the owners' keep / enjoyed-the-wordplay / best marks into a counts-only attestation. Its lane prompts are a prototype that `G4` replaces.

Still to do for `G1`: run `scripts/private-host-model-tiers.py` on the M3 Pro for the host receipt (it already probes every installed registry tag), write the thirty answers with angles, run the bake-off, and thread the call trace into the puzzle receipt.
