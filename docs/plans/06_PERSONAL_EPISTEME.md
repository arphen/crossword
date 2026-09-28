# The personal crossword: implementation plan

**Status:** the first private, locally generated play path is implemented and exercised in the browser. After a host-replayed game finishes, a deferred loopback Ollama pass can now propose bounded, source-anchored association paths, persist them as replayable episteme evidence, and let the player keep, set aside, or pass each path without delaying solve completion. `/future` starts without fetching the daily feed and offers an explicit local-generation action. Flask combines the starting profile and episteme with Ollama-generated theme words and clues, native 15×15 xfill, a registered solve manifest, the existing solver, and the solve journal. Private preparation now runs through a durable SQLite job and local worker: the browser submits an idempotent request, polls truthful `theme-proposal`, `native-xfill`, `clue-generation`, and `finalizing` stages behind the active lease, and can stop waiting while keeping the current puzzle. Real Gemma runs produced 15×15 Wednesday and Thursday-style puzzles with 70–78 entries in roughly 59–86 seconds; a browser run restored its exact board and typed letter after reload. The saved thread/fork/echo/moss opening repeatedly shaped themes such as TUNING / STITCH / RESONANCE / PATTERN. Private generation now retries accidental xfill artefacts, avoids repeating recent exposed answer forms when fresh theme candidates exist, passes fill-quality/foothold signals into clue writing, performs a bounded conservative repair pass for likely factual hallucinations, and records mechanical plus explicitly uncertain grounding diagnostics in `clueQuality`; visible malformed brackets, quotes, and question-mark placement are normalized without inserting answers, and a final guard replaces answer giveaways, answer roots/inflections, generic templates such as “common name,” or mechanically false wordplay with an answer-free crossing scaffold. Each generated board also receives a local `private-construction-evidence-v1` topology receipt bound to a canonical board digest; it records structural gaps and the sibling-evaluator boundary without claiming player support. Finished private sessions now link generated answer forms as explicitly unreviewed exposure evidence, feed recent exposures into the next local theme prompt without claiming mastery, and select authored reflection variants from the frozen puzzle's clue signals. The solver assistance ladder now progresses from clue reading and context through suggested crossings to opt-in letter and entry reveals, with each step recorded in the solve journal. Flagged local clue surfaces can now become explicit, reversible narrow episteme controls from the collapsed clue-notes panel. Delayed language recall now follows a 24-hour → 7-day → 30-day local spacing ladder; its independent/assisted outcomes steer the next bounded recurrence brief without becoming mastery claims. The profile panel now reads the revisioned host projection after reload and shows saved signals, open associations, learning-thread count, and the exact episteme revision without turning that projection into a personality verdict. Contradictory and ambivalent claims now have a separate Tensions lane with support/counter-signal context. Projected claims now have Keep, Set aside, and Release lock correction controls that write scoped explicit-preference evidence through the same CAS reducer. It can also request and persist a private-profile-narrative-v1 field note from a frozen source digest; invalid model output fails open, Qwen 3.8 27B has now produced a verified evidence-linked note with its Ollama digest and runtime counters, and the note round-trips through profile archives and deletion. The creation panel now lets the player select Automatic, Gemma 4 26B, Qwen 3.8 27B, Gemma 4 31B, or Gemma 3 27B; the durable job validates the exact installed tag and freezes it into worker provenance rather than silently substituting a model. That allowlisted choice is also stored in the profile draft and round-trips through the existing constellation **Save changes** action. The host also uses that saved choice for older clients that omit a per-request model, while Automatic retains installed-model ordering. The ready-board controls also expose a bounded personalization receipt with episteme revision and input-lane counts, while withholding the profile digest and any personality or mastery interpretation. Browser tests now cover finishing, reflection, reload, episteme exposure history, a durable second “one more” generation with stale reflection cleanup, and unchanged daily play at `/`. Publication remains disabled and belongs to a separate future lane. A note may offer at most three evidence-linked seek/exclude paths; these remain inert until the player explicitly keeps one, then the host binds it to the stored narrative and current revision before sending an ordinary explicit-preference command through the reducer. Acceptance is idempotent and stale notes are rejected. “Write a fresh field note” now uses a request-scoped rebuild identity, so same-evidence regeneration produces a new source-bound snapshot while retrying the same request replays safely. The optional postgame reflection mirror is live against the installed `gemma4:26b` tag: a real loopback call returned three structurally valid first-person cards in 13.4 seconds, while preserving the authored response mappings and fail-open fallback.

**Prepared and revised:** 28 September 2026. Continue from the player-focused implementation handoff in [§22](#22-private-game-implementation-handoff-for-luna).

**Latest live checkpoint:** the current source tree and installed `gemma4:26b`
completed a fresh loopback Tuesday job on seed `20470391` through
`theme-proposal → native-xfill → clue-generation → ready` in 231.738 seconds.
It returned a playable 78-entry board; the selected local-anchor fill retained
two themed entries with zero iffy and zero weak entries, and the final clue
receipt met the stronger five-family/24-surface recipe with 36 signalled
surfaces (46.2%), one answer-free fallback, and zero deterministic grammar
issues. The answer-free receipt is
[`private-tuesday-clue-quality-study-v2.real-gemma4-26b-20260928.json`](../evidence/private-tuesday-clue-quality-study-v2.real-gemma4-26b-20260928.json).

The clue gate now rejects answer lexical leakage, including exact multiword
surfaces and obvious roots and inflections (`REDS` cannot receive “shades of
red”; `NO WAY` cannot receive “No way!”), and rejects short generic
templates such as “common name,” “common term,” or an unspecified “famous
writer's name.” Unresolved cases fall back to
an answer-free crossing scaffold and remain visible in clue-quality provenance.
The same answer-safety rule now covers the common irregular counterparts that
ordinary suffix rules miss (`MICE`/“mouse”, `CHILDREN`/“child”, and the other
small reviewed list shared by the Python private route and the TypeScript
admission validator), so a clue cannot reveal an answer through a singular
root while avoiding an exact or regular inflection match.
The generic-template guard also rejects those phrases when they appear inside a
longer surface (for example, “a common name for a gas”), so padding the template
with a weak qualifier cannot bypass the same rule.
Explicit `(pl.)` and plain-language plural markers now receive the narrow
plural-shape check. Past-tense markers accept common irregular past forms (such
as `RAN` and `SLEPT`) or regular `-ED` answers, while present- and
future-tense markers reject an obviously past-shaped answer. This is a
visible-convention guard, not a general part-of-speech or semantic parser. The
collapsed `/future` clue-quality panel now projects those deterministic
morphology and mechanical failures into the same reversible note/flag surface,
so an issue count cannot be hidden behind an empty “no issue” state.
Tuesday has an explicit recipe between Monday and Wednesday: a bounded increase
in fill search/time plus alternate senses and fair second readings, while still
requiring approachable footholds. The domain-wordlist direction in
[plan 11](11_DOMAIN_LEXICONS_AND_SOURCES.md) remains the later source/admission
slice; this change deliberately improves the private clue contract without
pretending an unreviewed corpus is production content.

A fresh real Gemma Tuesday run after the bounded repair widened to 36
eligible entries reached the stronger floor: 76 entries, 44 signalled surfaces
(57.9%) across five non-definition families, five answer-free fallbacks, and
zero deterministic grammar issues in 227.940 seconds. The answer-free receipt
is [`private-tuesday-clue-quality-study-v4.real-gemma4-26b-20260928.json`](../evidence/private-tuesday-clue-quality-study-v4.real-gemma4-26b-20260928.json).
The wider batch is still fail-open and bounded; it improves the observed
Tuesday floor without claiming semantic fairness or player difficulty.

The Tuesday recipe lets the model propose up to five theme locks, then submits
at most four to the native runtime. The current bounded diversity repair asks
for at least five safe non-definition clue families and 24 signalled clue
surfaces, targets 48% on a full board, and can consider eighteen ordinary
entries per batch; the writer gets up to three follow-up batches plus one final
post-safety pass when cleanup lowers the visible count. The earlier v3 Gemma
receipt remains a useful pre-change baseline; the prior v2 receipt above
shows the former recipe reaching 36 surfaces across five families; the current
48% policy is covered by the v3 receipt below. This is a
visible generation requirement, not a claim that clue semantics are reviewed:
every receipt retains fallback and `semanticStatus=not-established` fields.
Model failure still leaves the board playable and records the repair status.
The receipt records `requiredNonDefinitionFamilies`,
`requiredNonDefinitionClues`, the proportional target, and `floorMet`, and the
clue-notes panel distinguishes a varied board from one that remained playable
but fell below its weekday surface floor. Fill retries also try the shortest
model-proposed theme answer already present in the local xfill dictionary
before releasing the theme and using an open grid.

The Tuesday calibration keeps the runtime-compatible 75-candidate search and
2.5-second native budget, while the current clue recipe requires a five-family,
24-surface floor and a 48% full-board target. The retry adapter caps primary and
reseeded native submissions at four theme locks while keeping the full proposal
available to the local-anchor retry, so a five-lock model proposal cannot create
an avoidable invalid native request. The repair remains bounded and fail-open:
it can use at most eighteen ordinary entries per pass and three follow-up batches
plus the existing post-safety check. Focused generation tests and the fresh
real-model receipt cover the stronger floor and exact answer-leakage cases.

A fresh loopback Gemma 4 26B run after the earlier proportional-target change used seed
`20470390` and produced a 74-entry Tuesday board in 231.36 seconds. It reached
28 non-definition surfaces (37.8%) across four families, zero deterministic
grammar issues, one answer-free fallback, and `floorMet=true` under the then-current
35%/four-family policy; the answer-free report is
`docs/evidence/private-tuesday-clue-quality-study-v1.real-gemma4-26b-20260928-target.json`.
This remains a local-model surface receipt only: semantic fairness and player
challenge are unreviewed, and it is a pre-change baseline for the stronger Tuesday recipe.

The evaluator now also reports grammar-clean rate, family-floor rate,
target-rate coverage, and aggregate observed non-definition rate across a
study, while retaining the explicit no-semantic-claim interpretation.

The current Tuesday calibration raises the proportional target to 48% visible
non-definition surfaces on full boards, keeps the count floor at 24 clues, and
keeps the family minimum at five. The repair pass can consider eighteen ordinary entries
per bounded batch and explicitly prefers safe pun, fill-in, bracket, quotation,
and abbreviation conventions over unsupported factual relations. The target is
advisory and fail-open: a board records its observed rate, target count, and
floor result without claiming semantic fairness or player difficulty. The
former 42% Gemma receipt remains the pre-change baseline. A fresh live
Gemma 4 26B run with seed `20470392` reaches 36 non-definition surfaces
(48.6%) across six families on a 74-entry board, with zero deterministic
grammar issues, four answer-free fallbacks, and `floorMet=true`; its answer-free
receipt is `docs/evidence/private-tuesday-clue-quality-study-v3.real-gemma4-26b-20260928.json`.
This confirms the stronger surface target under one seed, while semantic fairness
and player challenge remain unreviewed.

### Documents 7–12 implementation audit (28 September 2026)

The adjacent concept notes are now mapped to the running `/future` path rather
than treated as separate promises:

| Note | Live implementation | Boundary that remains explicit |
| --- | --- | --- |
| [07 — Expertise](07_EXPERTISE_AND_THE_GENERAL_CROSSWORD.md) | Opening objects, traces, reflection responses, recent exposure, and broad-content floors give a player several ways into unfamiliar material. Skill evidence is kept separate from taste signals. | There is no source-backed expert pool or trusted familiarity estimate yet. A difficult answer remains a private synthetic exposure until a later review lane establishes its sense and usefulness. |
| [08 — International audience](08_AN_INTERNATIONAL_AUDIENCE.md) | The setup can select a learning language; generated clues use explicit language labels, starter/review forms, delayed recall, and token-aware local rendering. | The current engine is an English ASCII grid with a small reviewed language task bridge. Native-speaker review, broader scripts, and richer transliteration policy remain future work. |
| [09 — Signification and the aha](09_SIGNIFICATION_AND_THE_AHA.md) | Calibration, reversible association cards, clue-family feedback, crossings, assistance, and postgame reflection let a player mark routes that felt useful without turning them into a diagnosis. | The system records a route into a word, not an “aha” score or a spiritual interpretation. Semantic resonance and long-answer discovery still need player studies. |
| [10 — Evolving relation](10_EPISTEME_AS_AN_EVOLVING_RELATION.md) | The CAS episteme reducer, revisioned projections, tensions, release/keep controls, evidence rebuilds, profile archives, and session analyses provide a durable reversible history. | Longitudinal calibration, contradiction editing at larger scale, and independent evidence that the profile improves play remain open evaluation work. |
| [11 — Domain lexicons](11_DOMAIN_LEXICONS_AND_SOURCES.md) | Strict pack loading, source pins, OEWN staging, candidate projection, clue-grammar admission, retrieval/job contracts, and an opt-in local `private-domain-hints-v1` bridge are ready as plumbing. The bridge intersects a player-owned hint file with the exact xfill vocabulary and records its digest without admitting its terms. | No external corpus is silently active: there is no production domain pack, source-terms attestation, semantic/factual review, or licensed bulk derivative in the private route. Admitted domain wordlists still require an explicit source, license, sense/fact review, and release receipt. |
| [12 — Editorial intelligence](12_EDITORIAL_INTELLIGENCE_AND_LLMs.md) | Local Gemma/Qwen generation, weekday recipes, deterministic answer-safety, visible clue-family signals, bounded challenge/repair, and answer-bearing private review bundles are live. | Model fluency is still advisory. A clue is not admitted as true or fair without independent sense/fact evidence and editorial review; private play remains fail-open with uncertainty receipts. |

This audit is the handoff order for the next implementation pass: preserve the
private generated path and its clue gate; the opt-in player-owned domain-hint
bridge can now invite placeable terms, while an admitted domain selection still
requires an explicit source/pack receipt, human sense/fact review, and player
calibration. None of the six notes authorizes the model to invent a source, a
user's expertise, or a mastery claim.

The private safety pass now treats an unsupported factual relation as unsafe for
an ordinary non-theme entry even when its fill score is strong. It keeps exact
clue text from a configured reviewed pack and preserves intentional theme
surfaces, while replacing the unresolved ordinary relation with an answer-free
crossing scaffold. The quality receipt now binds each scaffold to answer-free
structural crossing counts and support-entry IDs, and the `/future` clue panel
explains how many fallback surfaces still have a crossing route after reload.
The receipt and panel retain the source/semantic uncertainty; private play
remains fail-open and no source-free text is promoted to a truth claim.
The same detector now covers source-free identity/domain surfaces such as
representative, city, director, team, agency, and middle-name prompts, so an
obscure proper-name route is not treated as grounded merely because it sounds
specific.
The receipt also preserves the original fallback reason (for example,
`unsupported-factual-surface`) after the visible clue has been replaced, so a
safe surface does not erase the diagnostic that caused it.

The postgame loop now includes an optional `playtest-pulse-v1`: after the
reflection cards, the player can leave three bounded signals about this game
(`worth`, the direction for a next board, and one rough edge). The host checks
the shared domain contract, binds the pulse to a finished session, and records
it as answer-free performance evidence through the same CAS episteme ledger.
It is idempotent, appears again after reload and in the answer-free history
projection, and is included automatically in profile archives through the
existing episteme export. It does not create a taste claim, mastery estimate,
or automatic preference; its bounded `more-footholds` / `harder-stretch`
signals can only adjust the next difficulty recommendation. It is the first
direct playtest-calibration trace for the human evaluation program in §20.

Private generation now applies explicit Monday through Saturday recipe v1 settings through the existing weekday request. Monday asks for three approachable theme locks and direct footholds; Tuesday asks for up to five locks, a bounded search/time increase, alternate senses, fair second readings, and a five-family/24-surface clue-language floor with a 48% full-board target; Wednesday uses four inferable theme locks with varied, fair misdirection; Thursday proposes three to five theme answers plus a typed shared-prefix or shared-suffix rule; Friday uses a looser long-form cluster with indirect but precise clues; Saturday uses a compact cluster with the most oblique fair wording and a few deliberate footholds. The host enables that Thursday rule only when every proposed answer and at least three actual filled theme entries match it, then passes the validated rule to clue generation and records it with those answers in provenance. If proposal, validation, or filled-entry matching fails, the maker continues with the ordinary-letter-grid theme path and records the mechanic as unavailable. The chosen recipe ID, intent, requested and used theme counts, actual themed-entry count, clue floor, and grid mechanic are recorded in provenance. The controls explain each day's aim before generation. These are generation directions, not guarantees of editorial quality; rebus and special-cell mechanics remain unsupported.

The private fill path now applies `private-fill-quality-policy-v1`: it evaluates at most four deterministic native-xfill candidates (theme-locked, reduced-theme, reseeded, and open-grid variants), ranks measured candidates by fewer iffy entries, then a bounded two-theme retention floor within a 25%-weak-entry band, then fewer weak entries, mean score, and score floor, and records every successful or failed attempt with option, seed, source, board digest, and score receipt provenance. The local-theme-anchor attempt now retains the two shortest model-proposed invitations already present in the local xfill dictionary, so a placeable pair can survive construction instead of being reduced to one anchor. A bounded native smoke with a two-word anchor produced two themed entries on both seeds; the answer-free receipt is `docs/evidence/private-two-theme-anchor-smoke-v1.json`. A weak but structurally usable board remains playable when no stronger candidate exists; missing native score fields produce an explicit unavailable diagnostic rather than an invented score or a new play gate. The policy improves selection for the latest 70-entry/13-iffy/38-weak result while preserving local availability; human quality, clue fairness, and player support remain unmeasured. `src/crossword/fill_quality_evaluation.py` and `scripts/fill-quality-study.py` now turn bounded receipts into `private-fill-quality-study-v1`: a fixed-seed report records requested/observed/missing seeds, attempt and retry summaries, selected-attempt metrics, measured/unavailable fields, optional loopback/model metadata, and a SHA-256 study digest. `scripts/private-fill-study.py` collects the same receipts through a running local private-puzzle API for explicit seeds; it does not start Ollama or export profile data. A real Gemma 4 26B Wednesday run through that collector is preserved at `docs/evidence/private-fill-quality-study-v1.real-gemma4-26b-wednesday-20260928.json`: four attempts were captured, the selected theme-locked primary had zero iffy entries and mean score 79.45, and the report retains the weaker alternatives and one failed retry. `compare_fill_quality_studies` and `scripts/fill-quality-compare.py` pair selected measured attempts by seed and report policy-minus-baseline deltas without declaring a human-quality winner. The runner is injected and receipt-only, so CI cannot accidentally start Ollama; the report's acceptance policy is explicitly heuristic and never a human-quality gate. Synthetic checked artifacts live at `docs/evidence/private-fill-quality-study-v1.synthetic.json` and `docs/evidence/private-fill-quality-comparison-v1.synthetic.json`.

An additional live rerun on 28 September 2026 used Gemma 4 26B, the saved thread/fork/echo/moss profile, Wednesday, and seed 137 through the actual loopback private-puzzle route. The theme-locked primary selected 78 entries with mean score 79.45, zero iffy entries, and 17 weak entries; a reduced-theme attempt failed at native xfill, while a reseed and an open-grid reseed supplied two measured alternatives. The digest-bound receipt is preserved at `docs/evidence/private-fill-quality-study-v1.real-gemma4-26b-wednesday-recovery-20260928.json`. This is evidence that the original local path works on current sources, not a human fairness, solve-probability, or enjoyment claim.

The private generator now attaches `private-weekday-mechanic-evaluation-v1`
to every Thursday provenance receipt. The evaluator rechecks the final theme
entries after fill selection, records `pass` for a valid shared prefix/suffix,
or records `fallback-safe` when the mechanic was explicitly unavailable and the
board stayed an ordinary themed grid. The UI exposes that status in the
postgame receipt. This closes the live-board structural inspection gap while
leaving human Thursday fairness and player-solving evaluation open.

Thursday selection now treats three retained mechanic instances as a stronger
day-specific objective: a validated theme candidate wins while its measured
iffy count stays within the bounded 12-entry budget, even if its weak-entry
band is wider than the ordinary retry policy. If every themed candidate exceeds
that budget, the open-grid candidate remains playable and the mechanic is
reported unavailable.

The new `scripts/private-weekday-mechanic-study.py` command collects those
receipts through the same loopback endpoint as the browser. The latest two
real Gemma 4 26B Thursday runs (seeds 137 and 271) completed successfully:
seed 137 produced four validated `NG` suffix instances (`WHALESONG`, `ACTING`,
`BELONG`, `BORING`), while seed 271 correctly recorded a `fallback-safe`
ordinary-grid result because too few themed entries survived. The digest-bound
artifact is preserved at
`docs/evidence/private-weekday-mechanic-study-v1.real-gemma4-26b-thursday-20260928.json`.
This proves both the validated mechanic path and its fail-safe fallback on
current model boards; it remains a structural receipt, not a human fairness or
solve-probability result.

The seed-144 receipt also exposed the selector tradeoff: its real attempts
included a four-entry themed candidate at 11 iffy entries and an open-grid
candidate at zero. Replaying that captured receipt through the patched
Thursday selector chooses the themed candidate under the new 12-entry budget;
this is a deterministic policy replay, not a second model generation.

The mechanic continuation passes 100 focused Python tests across private
generation and weekday evaluation, 3 focused React receipt tests, script
compilation, formatting, and diff checks.

The private clue receipt now distinguishes exact admitted-source joins from model-only text. When a configured pack supplies the same visible clue plus at least one reviewed sense or fact, `clueQuality.grounding` and `clueBundle` mark that entry `semanticStatus=reviewed-source`, retain the pack digest and evidence IDs, and reduce its uncertainty to the still-unmeasured player-support dimension. Any paraphrase, unmatched answer, or absent pack remains `not-established`; private generation remains fail-open and experimental. This advances the E10 grounding contract without pretending the synthetic pack is a production corpus.

The local language lane now carries Dutch (`nl`) end to end through setup, generation briefs, reflection/session language signals, admitted-retrieval metadata, and delayed review. Its three compact pairs (`JA`, `HUIS`, `WATER`) are deliberately synthetic and unadmitted, so this expands the contract and personalization surface without making a translation, grammar, or native-speaker quality claim.

The delayed-review lane now carries a bounded overdue signal from the host
scheduler into both the review card and the next private-generation brief.
Overdue hours can raise an optional candidate within a capped one-interval
bonus, and the UI names the delay directly. This is a queue-ordering aid only;
it does not alter the 24-hour/7-day/30-day schedule, estimate recall
probability, or claim mastery.

Private provenance now also carries `private-theme-exposure-receipt-v1`. It
reports bounded counts for recent answer-form exposure, fresh theme answers,
and repeated theme answers after the cooling policy, and the postgame receipt
shows the fresh-theme count without exposing answer history. This turns a
previously implicit episteme effect into an inspectable generation signal while
keeping the underlying exposure evidence unreviewed.

Thursday private boards now carry a `private-weekday-mechanic-evaluation-v1`
receipt beside the shared-affix declaration. It rechecks the final filled theme
entries against the exact prefix/suffix instances, or records an explicit
ordinary-grid fallback, and the postgame receipt exposes the bounded result.
The check is structural and digest-bound; it does not establish clue fairness,
player support, or solve probability.

The richer private generation receipt now survives the replay boundary as
`private-puzzle-provenance-v1`. Synchronous generation stores it beside the
immutable manifest, and the durable worker stages it in the same ready-job
transaction. The owner-scoped session route revalidates a canonical digest
before returning it; the `/future` post-game view reopens bounded model, fill,
clue, and challenger counts after reload. Storage remains fail-open for local
play, while conflicting or tampered receipts are rejected. This closes the
gap where clue-quality evidence existed only in the immediate generation
response.

When the optional local semantic challenger runs, its non-keep recommendations are now visible in the collapsed clue-quality panel as advisory, unverified notes; only an explicit player flag enters the reversible clue-family steering path.

The answer-free profile history now also returns `private-play-calibration-report-v1`: finalized sessions are aggregated by weekday and local model into observed completion, independent, crossing/assistance, and mistake counts. It requires three sessions before calling the report observational, keeps an explicit non-probability/non-mastery uncertainty envelope, and is surfaced in the profile panel as a difficulty-only trace. It is evidence for a future human calibration study, not a synthetic simulator claim.

**Product repository:** `crossword`. **Construction repository:** `../crossword-generator`.
**Scope:** the complete path from a player's first puzzle to a durable, expressive personal vocabulary, including construction, inference, learning, interaction, runtime, evaluation, and delivery.

**Review map:** [nonverbal opening](#initial-calibration-five-short-movements) · [weekday recipes](#weekday-difficulty-is-an-editorial-contract) · [clue language](#a-language-the-player-can-learn-and-trust) · [experience](#3-the-experience-from-the-first-game-onward) · [the prose profile and open semantic space](#4-episteme-three-things-that-must-remain-distinct) · [game-to-profile updates](#7-turning-a-game-into-an-episteme-update) · [reflection cards](#9-reflection-cards-desire-expressed-indirectly) · [crossing algorithm](#13-crossing-scaffolding-the-central-construction-algorithm) · [Gemma/Qwen and runtime](#17-qwen-gemma-and-the-actual-runtime-decision) · [execution backlog](#21-execution-sequence-and-bounded-work-packages) · [review decisions](#23-risks-decisions-for-review-and-chosen-defaults).

**Owner direction for implementation:** Private play is explicitly authorized. Do not hold a locally generated puzzle behind human review, source-license attestation, publication receipts, a curator worksheet, or synthetic-fixture rejection. Mark it experimental and keep it local. Apply those evidence gates only if a puzzle is prepared for sharing or public release. A real Gemma 4 26B + xfill browser run generated a 15×15, 78-entry puzzle in 58 seconds; the solver opened it, retained a typed letter and restored the same board and solve journal after reload. A separate browser suite covers onboarding, explicit generation, solving, reflection, reload, and the unchanged daily route.

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

The private generator also carries a bounded `playCalibration` summary from recent finished solve analyses. It averages completion, independent retrieval, supported or assisted retrieval, and incorrect-attempt rates over at most six sessions, then emits only `more-footholds`, `balanced`, or `gentle-stretch`. This is recorded as reversible, difficulty-only provenance; it cannot become a taste, identity, intelligence, or mastery claim. Theme and clue prompts use it only to adjust accessibility within the selected weekday recipe.

### Non-negotiable product contracts

- The grid, answer senses, and clue bundle are frozen when a session starts. Assistance selects prepared hints; it does not secretly replace the puzzle.
- Every unusual answer has an editorial reason to exist and a credible route to discovery for the intended player.
- Knowing a word, liking its subject, liking its clue, and wanting more of it are separate signals.
- The profile can contain prose and open-ended associations. Claims about the player retain evidence, uncertainty, scope, and an undo path.
- For private experimental play, the model may write original clues that are played after grid, answer, and session-shape checks; label them local and let players flag them. Source/fact adjudication is a requirement for sharing, not a private-play gate.
- Personalization changes answers, senses, clue surfaces, difficulty, recurrence, and theme selection. Merely inserting favorite topics into generic clues is insufficient.
- The default experience runs on the player’s local application host, supports cached solving after preparation, and remains complete without reflection cards.
- Weekday names are selectable editorial contracts: Wednesday must feel like Wednesday; Thursday must offer a fair mechanical or thematic discovery. A full-size crossword remains the core experience. Small test grids and optional short sessions support it; they do not replace the ambition.

## 2. What exists, and what this plan changes

The following is based on source inspected on 26 September, rather than assuming earlier planning documents describe shipped behavior.

| Area                   | Observed implementation                                                                                                                          | Consequence                                                                                                                            |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| Active UI              | `apps/react/src/main.jsx` mounts desktop/mobile behavior through a compatibility controller.                                                     | Preserve its solving behavior and distinctive Across/grid/Down composition while moving session truth into typed use cases.            |
| Previous static target | ADR 0001 specified `apps/web`, which is not an active source workspace.                                                                          | Superseded by ADR 0003: extend `apps/react`; no static-workspace restoration is required.                                              |
| Puzzle domain          | `packages/domain/src/puzzle.ts` has immutable-style values, clue variants, provenance, quality, and integrity fields; document schema is v1.     | Extend with sense identities, assistance provenance, and generation receipts through explicit schema migration.                        |
| V2 puzzle candidate   | `packages/domain/src/puzzleV2.ts` defines the strict 15×15 one-letter V2 contract, canonical SHA-256, semantic-review gate and public-copy redaction. `src/crossword/personalized_manifest.py` binds a host-selected fill to exact admitted source/sense/fact/clue records and returns a separate private profile-evidence sidecar. The personalized worker emits review candidates when every entry has an exact admitted clue join, stores them in a profile-scoped V2 table, and serves them from a read-only V2 route after digest revalidation. A separate published-V2 table is empty by default; its GET envelope uses strict published-record resolution. | Candidates remain review-only (`quality.verdict=review`, `playable=false`) and are rejected by the published registry. Candidate and sidecar writes share the lease/cancel-fenced job transaction; raw profile evidence IDs remain private. The pure `published` UI adapter has been reviewed and has 8 tests. Flask supports a bounded configured reviewer roster, while no production insert/publication writer exists. No published fixture or live original content exists. Structural letter agreement remains zero support/confidence and `unknown` uncertainty. |
| Publication review    | `packages/domain/src/publicationV2.ts` defines a candidate-digest-bound immutable review packet and strict checks for source/license review, clue adjudication/challenger outcomes, support routes, seeded simulation, weekday/foothold distribution, and Thursday mechanics. The host has a read-only Node gate bridge, authenticated immutable evidence uploads, a human claim-attestation endpoint and SQLAlchemy model/table, and an internal evaluator for the same stored candidate/packet. | Authenticated host receipts bind exact TS-gate-validated candidate/packet digests, a logical human claim and projection digest, an ordered artifact ID/hash/kind/path manifest digest, configured principal, host time and protocol. Artifact records remain candidate- and array-index-bound; the receipt adds sealed-packet and semantic human-claim binding. The natural key `(candidate, packet, path, principal)` makes exact retries return the same receipt and rejects conflicting content; callers do not supply an idempotency key. Receipt coverage adds expected/verified counts and `human-attestation-incomplete`; the evaluator remains `blocked` or `evidence-unverified` and never writes publication state. Human projections omit clue `.challenger`, weekday `.blindClassifications`, and `.mechanicRoute`; each blind classification requires its own configured-principal receipt. Machine claims remain unverified. A receipt proves credential attestation only, not truth, evidence sufficiency, distinct real people, actual blinding, rotation/reassignment resistance, or direct-DB immutability. Independent review found no current publication/actor/evidence bypass and confirmed there is no registry write path. The former P2 future-use guard is now closed: `resolve_publication_packet_attestations` reruns the shared TypeScript publication gate against the frozen candidate and packet before accepting a declared digest, so future callers cannot bless a stale or caller-mutated seal by passing the matching string. Receipt coverage alone is never publication authorization. No machine receipt, publication writer, accepted document, or published content exists. |
| Session domain         | The legacy `packages/domain/src/session.ts` remains; `packages/domain/src/solveV2.ts` adds a validated V2 solve-event/session contract and deterministic replay analysis. The host now has V2 session, event, and analysis routes, separate from V1. | V2 create/append/replay/finalize resolve only records in the published registry, require prefixed `sha256:` digests, and revalidate the published envelope on replay and finalized-analysis reads. Nineteen V2 journal tests pass (37 combined with V1/replay tests). The V2 analyzer remains a distinct explicit document operation. Receipt checks are shape/integrity only. CAS and event-payload hashes detect ordinary corruption, but do not prevent a coordinated rewrite by someone with direct SQLite access; externally anchored/cryptographic append-only history remains later hardening. |
| Persistence            | Browser IndexedDB v3 holds a bounded `/future` solve-event outbox. Flask/SQLite has additive manifest, session/event, replay-analysis, revisioned episteme, publication-evidence, publication-attestation, and V2 published-puzzle tables; the published table starts empty. Profile writes use ETag compare-and-swap, with sequence/revision compare-and-swap and idempotent retries for journal and evidence writes. | This is still a local experimental persistence layer, not the complete profile/evidence/job system. Current CAS and payload digests do not resist a coordinated direct-database rewrite. `create_all()` adds new evidence tables but does not migrate existing columns; legacy evidence rows without claim locations remain unresolved and must be re-uploaded. Schema migration ownership and externally anchored append-only history remain. A bounded same-origin retention endpoint now removes only expired transient jobs and old private generated artefacts, with dry-run audit output; it never selects active solve history or authored calibration. Profile archive import now validates and atomically restores a fresh local profile without overwriting an existing one. |
| App integration        | `/future` reuses the React solver with focus, edit, check, reveal, visibility, finish, and local-host sync instrumentation. It starts with a blank local board and an explicit create action; `/` keeps the daily feed. The local route uses the profile and episteme to generate theme answers and clues with Ollama, builds a native 15×15 fill, registers its manifest, and initializes it through the shared solver. | Real Gemma/xfill generation, private session creation, browser letter entry, reload recovery, finish, reflection, episteme exposure history, a durable second-board handoff that clears stale postgame surfaces, and the unchanged `/` route are exercised. Human clue feedback and richer repeated-play/profile-update studies remain open. Private play does not require publication approval. |
| Personal episteme       | `packages/domain/src/episteme.ts` supplies a deterministic evidence reducer for open-vocabulary claims, knowledge estimates, associations, evidence actions, and revision receipts. Flask runs it through a fixed local Node bridge; association-field controls, finished host-replayed analysis, private generated answer-form exposure, host-authored calibration proposal/response evidence, reversible reflection-derived clue-family targets, and language-thread evidence enter the profile ledger and next private generation brief. | Generated answer forms remain `contentReview=unreviewed`, so recorded exposure does not claim vocabulary mastery. The local generator reads bounded recent exposures, reviewed include/avoid targets for wordplay/discovery/challenge, a gentle language recurrence lane that can revisit at most two explicitly signalled forms, a capped `playCalibration` difficulty-only summary from at most six finished sessions, and optional due language forms already present in the native xfill dictionary. A 24-hour delayed recall queue now records opaque-task independent versus answer-assisted responses, and its outcome categories steer the next local brief without becoming mastery claims; due forms are ordered first as optional candidates, including remembered forms only after the scheduler marks them due. Records travel through profile export/import/deletion. Ordered calibration observations remain a separate journal; adaptive scheduler fitting and richer next-puzzle use remain; a finished `/future` session now offers a contextual “Make one more personal crossword” action wired to the same durable generator. |
| Initial calibration     | `packages/domain/src/calibration.ts` defines a bounded five-movement append-only contract; the catalog contains 64 versioned stimuli; `/future` records deterministic, positioned offers to IndexedDB and the host's `future_calibration_sessions` table. | The opening is implemented with an optional, host-derived hypothesis deck linked to active observations; this remains interpretation of selected stimuli, not profile synthesis, personality inference, or a personalized puzzle. |
| Clue language           | `packages/domain/src/clueGrammar.ts` supplies versioned structural clue-family, signal-span, grammar-witness, and mechanic checks. The private generator now adds deterministic answer-shape, relation, convention-surface, punctuation-scope, and fallback-crossing diagnostics with an explicit `semantic-meaning-unverified` status per entry; malformed brackets, quotes, and question-mark placement receive a final answer-free normalization. | These diagnostics and repairs make uncertainty inspectable and keep the visible NYT-style punctuation language coherent, but they do not prove semantic fact/sense grounding or replace a production clue-writing pipeline; those still require content and editorial gates. |
| Crossing support        | Sibling `../crossword-generator/packages/construction/src/scaffolding.ts` evaluates crossing reachability and emits deterministic support certificates. `solveSimulation.ts` reports finalist routes, stalls, circular supports, and islands from explicit estimates. `reportAnswerPositionInformationGain` now reports exact-letter candidate-mass discrimination only when alternatives are declared complete and reviewed; otherwise every position remains unknown. The distinct seeded trajectory screen now has a local lab panel (see §13.5). | The older scaffolding, finalist-proxy, and information-gain reports remain unwired to candidate search, clue validation, or lab review. Candidate-mass discrimination is not human solve probability or calibrated player support. The V2 builder still reports zero player-support estimate with unknown uncertainty; any numeric support estimate needs versioned familiarity/difficulty/letter-support inputs and play calibration. |
| Reflection contract     | `packages/domain/src/reflection.ts` validates approved card versions, fixed keep/not-for-me mappings, pass, and undo/restore evidence actions. Flask freezes three reviewed cards from a 60-card authored pool per finalized session, stores responses beside the immutable deck, and writes response/retraction evidence through the shared converter and reducer. The deck now uses deterministic authored variants grounded to exact manifest entry IDs when clue turns, language signals, or longer/less familiar entries are present; legacy sessions retain generic wording. `/future` displays the cards and offers keep, turn away, pass, undo, and restore. The saved response state now also returns the exact evidence and episteme revision, so the UI can show which seek/avoid mapping was recorded and which revision received it after reload; retraction receipts show the revision that removed the signal while preserving the original response. `make run` can enable a bounded local mirror that follows the finished puzzle's frozen model provenance unless an explicit reflection-model override is supplied; it rewrites only card wording/interpretation while preserving authored IDs, scopes, mappings, and response contracts. Exact model/prompt receipts are visible and invalid output fails open to authored cards. | The bank remains authored and explainable; the local mirror is wording assistance rather than semantic discovery or a profile claim. Contextual semantic proposals, exposure-fatigue evaluation, and richer next-puzzle use remain. |
| Portable generator     | Three packages expose a TypeScript CSP, model broker/WebLLM adapter, and orchestration.                                                          | Keep deterministic construction independent of UI and model runtime.                                                                   |
| Full-size lab          | `apps/lab/server.ts` shares native Rust `xfill` through the extracted `packages/local-runtime/`; the package archive is installed in the product checkout. The product has a SQLite-backed leased queue, same-origin create/poll/cancel APIs, and a separate worker for profile-pinned answer grids with an optional V2 review-candidate stage. A real offline Flask→SQLite worker→Node CLI→xfill smoke stored a 78-entry draft in 40.5 seconds, mean fill score 80.04, minimum 55, and zero iffy entries, with a source digest. The review reproduced cancellation races; they have since been fixed with conditional state transitions, expired-cancel recovery, shutdown requeue, and lease fencing. `private-fill-quality-study-v1` now provides a deterministic fixed-seed receipt evaluator and CLI over captured native attempts; the synthetic artifact is checked in, with missing/unavailable metrics represented honestly. | Keep semantic review, crossing/difficulty and weekday gates, publication, and playable-puzzle APIs behind their own evidence gates; real admitted-content runs and human fill acceptance still need evaluation. |
| Current model evidence | Paired `holdout-v1` ran against exact Qwen 3.8 27B and Gemma 4 26B artifacts; both were schema-valid 4/4, deterministic task gates were Qwen 2/4 and Gemma 4 4/4. `src/crossword/model_evaluation.py` and `scripts/model-evaluation-report.py` now derive a digest-bound structural report from the existing harness output, preserving exact model/tag-digest/quantization/context receipts and independently recomputing schema, task-gate, runner-latency, UTF-8 output-size, and provider-counter metrics. The generated snapshot is `docs/evidence/model-evaluation-holdout-v1.structural.json`. | Gemma is a provisional local runtime default for route operability, not a quality winner. The holdout is four tasks/model, context was not pinned, blind ratings and all semantic/editorial fields remain explicitly pending, and no winner is declared. Preserve exact artifacts and the configurable model override. |
| Runtime                | **Accepted:** existing React/Flask app, canonical host SQLite, durable worker, Ollama and native `xfill`.                                        | Owner instruction supersedes browser-only requirements; later ports use preserved contracts.                                           |
| Profile export         | `GET /api/future/profile/:id/export` returns a stable-order, read-only JSON export covering current host collections, with an explicit SQLite snapshot and source/model digests. It includes the matching job’s private profile-evidence selection sidecar, scoped to that profile. `POST /api/future/profile/:id/import` validates the schema, profile scope, record identities, and capability redaction before restoring a fresh profile in one transaction; `DELETE /api/future/profile/:id` removes profile-owned calibration, episteme, solve, reflection, job, and private-candidate rows in one local transaction while retaining shared puzzle manifests and fencing late workers. `POST /api/future/profile/:id/retention` applies explicit seven-day transient-job and 30-day private-artifact windows with dry-run audit output. The `/future` constellation panel exposes archive download, restore, and deletion. | The 80 MiB export cap is still checked after materializing the export. Import deliberately refuses to overwrite an existing profile and does not recreate shared puzzle manifests or worker capabilities. Retention skips all running jobs and preserves solve history, calibration, episteme and shared manifests. The cross-record consistency, import atomicity, deletion/late-job and retention regressions are covered by tests; see §22. |
| Content admission      | `pack_builder.py` creates a reviewed pack; `admitted_pack.py`, the strict byte/file loader and `admitted_pack_config.py` validate exact pack/source pins. The content projection emits reviewed sense/fact/clue fields with provenance while omitting raw/quarantined data. `/api/future/profile/:id/retrieval-brief` uses environment-configured pins and fails closed when absent or invalid. | Synthetic content only. No human-attested production pack exists; structural grammar checks do not establish semantic truth. |
| Retrieval brief        | V4 durable personalized answer-grid jobs freeze profile/episteme snapshots, weekday, language, pack/source pins, seed/options, recipe, the exact `compiledBrief`, `compilerVersion`, and `compiledBriefDigest` at reservation. The worker validates the brief schema and digest before use; v3 jobs remain readable and recompile in the worker from their frozen inputs. | This remains answer-grid only (`playable:false`); profile evidence IDs remain distinct from content sense/fact support. No human-attested pack exists; ranking/exposure/diversity still need evaluation. |
| Source ledger          | The product's older lexicon ledger still marks one source `NOASSERTION`; the generator lab documents a separately licensed Crossword Nexus list. | The new gate rejects the unasserted source; reconcile the exact external artifact and license before admitting a production pack.          |

Both checkouts contain unrelated work in progress. Implementation must record the starting state and preserve it. This document does not authorize resetting either checkout.

### Implementation snapshot (26 September 2026)

The foundation is now in source for parts of E01–E09, E12–E14, E16, E19–E20, and E22, but these are partial work packages, not completed product milestones. The `/future` route records a solve-event outbox and syncs it to the same local Flask host. Supported legacy puzzles receive immutable host-owned manifests; session creation verifies exact open-cell coverage, and appends are validated and replayed by the shared analyzer. Host-derived check/reveal truth and finalized analysis are persisted, with that analysis linked into the profile evidence ledger. Browser-supplied analysis remains rejected. The daily collection is now isolated to `/`; `/future` has a profile-seeded local generation path described in the current status above.

Two additional content foundations now exist. The lexicon pack builder admits only records tied to pinned, hashed source artifacts and explicit license/admission review; unresolved senses remain fill-only, and clues need source evidence plus a pass from the structural grammar validator. Synthetic CC0 fixtures exercise that gate, but no production corpus has been admitted and the assertions do not prove a fact or sense is true. The pinned OEWN importer and `oewn_candidates.py` provide a separate, unadmitted fill-review projection with reference validation and a bounded queue-building command; no queue is admitted until a human attests the source terms. The episteme brief compiler ranks only caller-supplied candidates carrying an admission/source contract; it records score reasons, selection lanes, evidence IDs, and source IDs, and lets hard exclusions override every lane. A separate durable personalized answer-grid worker resolves the pinned content projection, compiles a brief from frozen profile/episteme/job inputs, and constrains native fill with its eligible wordlist. Synthetic fixtures verify this connection; v4 freezes the compiled brief, compiler version and digest, while v3 retains worker-time recompilation. The worker now joins each fill entry to an exact admitted clue/sense/fact record when available and stores a cross-language V2 review candidate in a profile-scoped table. Its read route revalidates integrity; the candidate, private evidence sidecar, and ready job are committed behind the same lease/cancel fence. Public job JSON omits raw profile evidence IDs, and the private profile export includes the owner-scoped sidecar. Structural crossing records still report zero solve-support score/confidence and `unknown` uncertainty. No production pack exists, and ranking weights still need evaluation.

The first working calibration slice is now in place. `future_catalog.json` retains the original legacy catalog and adds 64 versioned stimuli across seven kinds. `/future` presents a mixed twelve-item opening, relation, color variation, mixed traces, and explicit weekday/language setup, followed by a separate profile preview. The shared `CalibrationSessionV1` contract records five movements, stable seeded offer order, exact stimulus IDs/versions/positions, choose/pass responses, relations, setup, and terminal state. New journals pin selector-v2's unbiased bounded shuffle; restored selector-v1 journals keep their original offer order. A deterministic 6,000-UUID × six-movement cohort check covers item-position distribution, but it is not a human salience study. Corrections append retract/restore actions; they do not erase earlier responses. A dedicated IndexedDB journal retries to a same-origin Flask endpoint backed by SQLite, which checks catalog references, body/sequence bounds, append-only history, and ETag compare-and-swap. The browser draft and raw calibration journal are distinct from the provisional starting profile.

An optional, user-requested hypothesis path now consumes a compact source projection from the validated host journal: only active choices, pinned stimulus labels/versions, and valid relations reach loopback Ollama. One active choice is enough; players may pass the remaining movements, while a skipped or all-pass opening cannot request paths. The host freezes up to six competing paths against a digest of that source, stores their exact observation/stimulus links as provisional association evidence, and exposes keep/not-for-me/pass plus retract/restore in Preview and the later profile panel. Untested paths have no retrieval weight; a kept path contributes at most 0.05 exploration weight and expires after 14 days or five later sessions. Output checks screen direct player-directed identity, health, belief, preference, and knowledge claims; this heuristic does not guarantee that every indirect personal claim will be caught. The path uses local Ollama only and remains optional. This is not an unrestricted prose portrait or a personalized-puzzle compiler. The selected weekday is explicit and retained, but the existing feed still supplies the crossword; it does not construct a puzzle to the selected day's recipe.

The deterministic episteme reducer and reflection-card contract now run through the local host. Direct profile controls, finalized solve analyses, calibration responses, and postgame reflection responses share a revisioned evidence ledger. A finished, host-replayed session receives three frozen cards selected deterministically from a 60-card authored pool; when its frozen manifest is available, authored wording and exact related entry IDs respond to clue turns, language signals, and longer/less familiar answers. Keep, turn away, pass, retract, and restore are recorded through exact versioned contracts; a refresh restores previous card responses. Reviewed reflection responses now feed bounded, reversible clue-family targets into the next private generation brief. Language-selected private sessions also create explicitly unreviewed language-thread evidence, and the next local generation may gently revisit at most two matching forms with a clear language signal; this is recurrence, not a mastery claim. A 24-hour delayed review queue now gives the player a clue-only recall prompt and records independent versus answer-assisted responses under an opaque task handle; response categories steer the next local brief toward pending/not-yet or assisted forms while recent independent recall is allowed to cool. The records are exported/imported with the profile and deleted with it, but they do not assert mastery; a diagnostic-only forgetting fit is reported after a minimum mixed sample and remains separate from scheduling. The contextual slice remains authored and does not claim that a model has discovered the player's desires. Imported daily clues still lack reviewed learning-task links, so the ledger does not claim their answers as learned vocabulary. Lexicon grounding of calibration hypotheses, reviewed task links, richer recall scheduling, and exposure-fatigue evaluation remain incomplete; the finished-session loop now has a contextual next-puzzle action, while richer next-puzzle selection still remains. Postgame model associations now have a bounded generation receipt, evidence/response persistence, export/import coverage, and a non-blocking `/future` surface; model output remains a proposal and does not become a claim without a player response. Profiles are capped at 64 MiB. The read-only host export now includes the owning profile’s private candidate-selection sidecar, with a coherent SQLite snapshot, preserved content digests, and an 80 MiB response cap; a conservative SQL preflight rejects oversized archives before materialization, with a final serialized-body check as defense in depth. A profile deletion route now removes all profile-owned rows in one transaction, retains shared manifests, and fences late jobs; the browser panel clears its journals. Profile archive import now restores a validated fresh profile atomically while refusing overwrite and leaving shared manifests/capabilities out of the archive; a bounded same-origin retention endpoint applies seven-day transient-job and 30-day private-artifact defaults, supports dry-run audits, and never removes active solve history or authored calibration. The sibling generator has deterministic crossing certificates and finalist solve simulation; private generation now invokes a versioned lab-only adapter when explicit familiarity/difficulty/letter-support estimates are present, while ordinary jobs record `not-invoked` and never substitute fill scores. Those estimates remain assumptions, not measurements of this player. The product has a leased SQLite queue and worker for profile-pinned full-size answer grids. Reservation freezes profile/episteme inputs, weekday/language, exact pack/source pins, `asOf`, seed/options, recipe, and for v4 the compiled brief/compiler version/digest; v3 still recompiles from frozen inputs. A strict private wordlist constrains xfill and returned answers, themes, and candidate/source links are checked. When every slot has an admitted clue join, the worker builds and atomically stores a V2 review candidate alongside its private evidence sidecar. The V2 route is profile-scoped, revalidates integrity on read, and remains separate from V1 manifest/session replay. The candidate is not publishable: semantic truth, human source admission, crossing/difficulty and weekday/fairness gates remain. The structural crossing receipt reports no calibrated solve support. The `/future` UI now has a private profile-seeded generation path. The human-attested production corpus, real admitted-content fixed-seed fill acceptance run, grounded clue review, weekday construction, reviewed learning-task links, richer recurrence scheduling, evaluation, and release hardening remain active work.

Earlier verification after the v4 reservation-receipt change: product Python **362 passed, 3 skipped** (one existing SQLAlchemy `datetime.utcnow()` deprecation warning); `tests/test_future_grid_jobs.py` passed **22 tests**. Root Jest **2 suites / 11 tests**, product typecheck, ESLint and Prettier passed. Product Playwright passed **6/6** with `CROSSWORD_E2E_BACKEND_PORT=5014` because port 5002 was occupied; these synthetic tests do not exercise a published original puzzle. Generator workspaces passed **116 tests** (construction 32, generator 10, local-runtime 25, model-runtime 18, lab 31), plus build, ESLint and Prettier. Product and generator repo-map checks passed at that earlier checkpoint. The Python tests exercise synthetic pack/runtime stubs; no native xfill generation with a human-attested admitted pack was run. No calibration-validity, sustained fill-acceptance, comparative model-quality, or learning-outcome claim follows from these counts.

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

**Implemented V1 boundary:** `packages/domain/src/calibration.ts` now defines the bounded session, observation, relation, setup, skip, and retract/restore contracts. The active `/future` UI records five calibration movements across six screens (the preview is separate), deterministically orders each spread from a retained seed, and stores the exact stimulus version and offer position. Its append-only journal commits to a dedicated IndexedDB store and syncs to `GET`/`PUT /api/future/calibrations/:id`; the host validates the shared contract against the 64-record catalog and protects writes with ETag compare-and-swap. If local IndexedDB is empty, the UI reads the host journal, verifies its profile scope, restores the snapshot with its host revision/ETag, and reconstructs the opening draft. If a write reports conflict after a lost response, it retries automatically only when the host snapshot is a valid append-only prefix of the local branch with matching immutable identity/settings. An incompatible branch remains intact locally and is marked conflict; the current UI does not merge it, and now presents recovery actions to keep it local or start a new calibration branch without rewriting the old journal. Movement changes can revisit a screen without editing evidence; changed earlier answers retract dependent evidence. Client runtime and host both reject cursor advances greater than one movement. The host permits a one-step advance only if the candidate journal retains an active choose/pass response for the current movement; a same-response revisit remains valid, while retracting its only response blocks the advance. Backward cursor movement remains valid. Completion requires a current response (choose or pass) for movements 1–4, explicit setup, and movement 5; skip remains valid without those responses. The UI currently does not send elapsed time.

The selected weekday and language are stored as explicit setup, outside associative traces. The ordered raw journal is never inserted into the episteme reducer. After an explicit player action, the host selects active choices from the opening, verifies the pinned stimulus-bank version, strips position and timing, and sends a compact source projection to loopback Ollama. At least one active choice is needed; the player can pass other movements, and a skipped or all-pass opening leaves the action unavailable. Authored seeds from selected signs remain in the separate provisional profile. The model produces source-linked associations, not inferred taste or knowledge claims; a player's response controls whether an association receives bounded exploration weight.

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

These are configurable starting values, not scientifically optimized intervals. Store task, interval stage, last outcome, assistance, due date, and scheduler version. The local host now exposes a diagnostic-only forgetting-model fit once a profile has at least eight independent remembered/not-yet observations with both outcomes represented. It uses a fixed pure-Python grid search over a bounded exponential decay curve, reports the sample counts, decay rate, half-life, and fit loss with an explicit model version, and never changes due dates or creates a mastery claim. Compare it to this baseline using delayed retrieval rather than fitting it on its own training history.

The shipped local queue uses a calm default budget of three due items. The host accepts only cumulative budgets of three, six, or twelve and reports the remaining due count; `/future` can expand the view without changing opaque task IDs or response semantics. Independent successes advance only as a contiguous streak, so a not-yet or assisted response resets the provisional stage. Later independent streaks receive a bounded interval extension, while assisted or failed recall returns to the short interval. The policy envelope also exposes a diagnostic-only bounded forgetting fit after its minimum mixed sample; this remains separate from the transparent scheduler heuristic and never changes its interval calculation.

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

The current lab accepts A–Z single-character rows and validates ordinary 15×15 and 21×21 grids; it does **not** already support this representation. E21 below extends the native engine/adapter or supplies a dedicated constrained rebus construction path. Do not strip letters from a completed ordinary fill and call the result a rebus. Multi-token crossing equality and reconstructed lexical answers must pass independent validators before a rebus recipe is enabled.

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

**Implementation status (27 September 2026).** The sibling generator now has a separate uncalibrated screen with 64–256 deterministic seeded trajectories, balanced over the 16 combinations of four familiarity strata and four navigation policies. It holds one latent draw per entry (or per topic in the explicit perfect-correlation stress stratum), only reevaluates after a changed mask/hint/check state, and records the evaluation ledger, hint/check/wrong-entry actions, opening entries, unresolved entries/cells, and stalled component sizes. Fully supplied patterns count as exposure. The result calls its aggregate a synthetic scenario fraction, not a human completion probability. Exact answer sequences in hints are rejected across whitespace and punctuation, but this syntactic guard cannot establish that a hint is semantically non-answer-bearing; human editorial review remains required.

The local generator lab's `FullSizeApp` now includes `SolveDiagnosticPanel`, backed by `solveDiagnostic.ts`. Before running, it requires a final clue for every entry and checks the 15×15 template/fill agreement, answer paths, duplicate entry IDs, and across/down coverage of every open cell; it derives crossings from the live geometry. Editors choose one of three displayed, globally applied assumption presets, 64–256 trajectories, a seed, and wrong-entry/check rates. The report presents all 16 stratum/navigation cells and an inspectable worst incomplete trace. It fingerprints the grid snapshot and each exact clue string. Its downloadable request/result JSON is explicitly not a verified replay artifact; the screen remains ephemeral and is not connected to a profile, construction job, persistence, or publication path.

This panel still verifies only the supplied editor grid and clues. It cannot establish published-candidate completeness or resolve estimate, implementation, or source provenance. All familiarity/difficulty/support values are editor assumptions, never xfill scores; clues are unreviewed; entries have singleton topics, `nonInferable=false`, no prepared hints, and therefore no shared-topic group in the correlated stress stratum or available nudges. The Node-only replay artifact's candidate/build/provenance digests remain opaque equality pins. An independent artifact audit found no canonicalization or replay defect (25 focused artifact tests pass), but those bindings still need external resolution. Neither simulator nor artifact is a publication receipt, machine-evidence claim, calibrated difficulty promise, or learning claim. Add trusted candidate, estimate-provenance, and running-build resolution plus real-player calibration before considering machine claims or probability-based difficulty promises.

The lab panel and adapter passed independent reviews after adding exact slot/number validation and stale-run invalidation. Verification on 27 September: full generator `npm test` passed **197 tests** (construction 105, generator 10, local-runtime 25, model-runtime 18, lab 39); `npm run build`, `npm run lint`, `npm run format:check`, `npm run map:check`, and `git diff --check` passed. No product route, profile estimate, construction job, or publication state consumes this diagnostic.

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

The `make run-personal` target now checks the pinned Node/Python tools and read-only native/Ollama readiness, starts/reaps Flask plus the durable worker, and prints the personal `/future` URL. It does not pull models; installation remains an explicit host setup action. Model installation is an explicit host setup action with exact ID/size/progress; do not silently pull several large models. Keep a ready sample available if inference is absent.

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
| `google/gemma-4-26B-A4B-it` | Closest published Gemma 4 workstation size to the requested “27B” experiment; use the actual 26B MoE artifact. | Ollama publishes `gemma4:26b` (25.2B total, 3.8B active); it is not a fictional `gemma4:27b` tag. [Ollama Gemma 4 catalog](https://ollama.com/library/gemma4), [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4). |

“Gemma 4 27B” should not become a fabricated model identifier. The current Ollama Gemma 4 catalog exposes a 26B A4B MoE artifact and a 31B dense artifact; the provisional product default is now `gemma4:26b` because it completed one actual proposal-route request while the configured Qwen default timed out twice. Explicit `CROSSWORD_HYPOTHESIS_MODEL` or `CROSSWORD_PROFILE_MODEL` settings still take precedence. This is an operational choice only; do not silently substitute Gemma 3 in a Gemma 4 comparison or call Gemma a writing-quality winner. The exact paired run and its limitations are recorded in §22.

### First benchmark in the existing private lab

Extend the lab with an experiment runner that consumes the same frozen tasks for every model. Discover installed tags, map them to exact upstream identities where possible, and record the resolved artifact digest, quantization, chat template, runtime version, context limit, sampling parameters, thinking configuration, hardware, and peak memory. A mutable tag is insufficient provenance.

Use runtime-supported schema-constrained output and still validate every response. Ollama supports supplying JSON Schema through the `format` field. [Ollama structured-output documentation](https://docs.ollama.com/capabilities/structured-outputs). The lab harness currently uses JSON mode through `/api/generate`; the product hypothesis route separately uses `/api/chat` with its own schema. A shared typed Node-only local-runtime adapter remains an architectural task, not current behavior. The browser talks only to the product API.

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
| E03 | **Solve instrumentation:** product application commands and active `apps/react` behavior adapter                                  | E02                     | Actual typing/check/reveal/focus emits replayable events exactly once; immediate solving stays responsive. The pure published-V2 adapter is reviewed (8 tests). Host V2 session/event/analysis routes are separate from V1, accept only published-registry records, enforce prefixed digests, and revalidate replay/finalized analysis (19 V2 tests; 37 with V1/replay tests). Flask reviewer credentials and the host-created packet-claim receipt route now exist, but configured identities and receipts do not establish independent raters or actual blinding. Receipt coverage is evaluated without clearing publication status. Independent review found no current bypass; the former P2 future-use guard is now closed by the resolver-side shared-gate check. Reproducible machine evidence remains outstanding. No published-V2 UI handoff or published content exists; the private experimental `/future` solver handoff is implemented separately, and there is no production publication writer. |
| E04 | **Content foundation:** product `tools/lexicon/`, content schemas/build tooling                                                   | E01                     | **Partial:** fail-closed deterministic pack admission; synthetic tests; pinned OEWN 2025 offline importer and staged count/hash ledger (135,969 lexemes, 185,129 sense links); foreign-key checked fill-review projection and bounded archive-to-review CLI; plus a read-only resolver that requires exact out-of-band pack/source pins and revalidates provenance, references, strict answer-safe clue grammar, and optional explicit personalization IDs with focused synthetic coverage. A 131.7 MB normalized import remains in `/tmp`, not in the repository or admitted pack. No source-terms attestation or production review queue has been created. Pack-builder tags are plumbing for a future reviewed domain pack; they do not admit a domain wordlist or infer profile links. Still required: actual license/source-terms review, clue/sense evidence, coverage report, factual review, and 100% release-candidate provenance. |
| E05 | **Model comparison:** generator `apps/lab/` experiment runner and fixtures                                                        | E01                     | **Partial:** opt-in paired and one-model smoke runner records exact tags/digests, prompt/output hashes and runtime observations. Paired `holdout-v1` run: Qwen and Gemma were each 4/4 schema-valid; deterministic task gates were Qwen 2/4 and Gemma 4/4. `model-evaluation-report-v1` (`src/crossword/model_evaluation.py`, `scripts/model-evaluation-report.py`) now independently derives schema validity, task-gate failures/issues, runner latency, UTF-8 output size, provider counters, exact model/digest/quantization/context metadata, and integrity checks from the existing full report; the checked structural snapshot is `docs/evidence/model-evaluation-holdout-v1.structural.json`. A current exact-tag live replay using `scripts/live-model-holdout.py` is preserved at `docs/evidence/live-model-smoke-holdout-v1.20260928.json`: both models completed all four frozen prompts with valid JSON and shallow shape gates, with 174.603 seconds total Qwen wall time and 25.320 seconds total Gemma wall time. Semantic coherence, clue fairness, source grounding, language accuracy, player resonance, and editorial preference are separate explicit `pending` fields, and both artifacts declare no winner. Still required: independent editorial scoring and broader fixtures for writing, structured updates, latency, and memory across exact artifacts. |
| E06 | **Native runtime extraction:** generator `packages/local-runtime/`, lab adapters and product runner protocol                      | E01, E05 smoke          | **Partial:** package `@crossword/local-runtime` 0.1.2 adds a strict pinned admitted-wordlist receipt, bounded digest-checked read, private per-job copy, `--wordlist` handoff, answer-membership fence, requested-theme check, and pack/wordlist provenance. The archive is installed in the product and its lockfile integrity is now checked against the current 0.1.2 tarball. Synthetic bridge tests and native-runtime unit tests pass; no native xfill run with a human-attested admitted pack has occurred. The product now exposes advisory `/api/future/runtime-readiness` diagnostics for preferred Ollama tags, xfill/runtime availability, database reachability, queue counts, and a privacy-preserving worker heartbeat; `make runtime-doctor` adds a deterministic read-only preflight that verifies the lockfile archive/integrity, CLI protocol imports, native xfill source/toolchain, and loopback model tags without running Cargo, generating a grid, or pulling a model. On the current machine the full doctor is green: archive, CLI, native engine, and both local Ollama tags are ready. It never gates generation or `/`. Still required: clean-install confirmation on a fresh checkout, representative memory/timing/acceptance report, and a published-quality fill report. No browser-port gate. |
| E07 | **Deterministic analysis:** product `packages/domain/src/observations.ts`, `packages/application/src/analyzeSession.ts` (new)     | E02, E03                | Hand-labeled trace fixtures produce expected retrieval/support/exposure outcomes and uncertainty; no taste changes from timing/errors.                                                            |
| E08 | **Content retrieval and briefs:** product application projection compiler; generator `constructionUseCases.ts` and resolver port  | E01, E04, E07           | **Partial:** deterministic compiler applies hard exclusions, preserves profile-evidence/source links, and maintains a broad-content floor. V4 durable jobs freeze the exact compiled brief, compiler version and digest at reservation; the worker validates schema and integrity before consuming it. V3 jobs remain compatible and recompile at worker time. An immutable validated content projection carries reviewed sense/fact/clue provenance plus explicit admitted personalization IDs and pool, so a future domain pack cannot lose its links at the resolver boundary. The bounded `episteme-brief-evaluation-v1` fixture and `scripts/episteme-brief-evaluation.cjs` compare synthetic `seek-sound` and `avoid-sound` profiles, report lane counts, duplicate answers/candidates, answer diversity, broad-floor satisfaction, hard exclusions, and selection divergence, and bind the JSON report plus each brief/profile fixture to SHA-256 over stable canonical bytes. The report explicitly does not claim player preference accuracy, enjoyment, solve probability, source truth, or semantic quality. Focused domain/host tests exercise the metrics and digest. Still required: human-attested production pack, broader fixed-seed ranking/diversity evaluation over admitted content, human/player comparisons, and integration into a playable clue-and-publication pipeline. |
| E09 | **Scaffolding evaluator:** generator `packages/construction/src/scaffolding.ts`, `solveSimulation.ts`                            | E04, E08                | **Partial:** deterministic certificates and a finalist simulator report routes, stalls, circular pairs, and disconnected islands; fixtures cover an easy clue unlocking PEKOE and obscure/obscure support. The private generator emits structural crossing access plus a local `private-construction-evidence-v1` receipt bound to a canonical board digest. It now also emits `private-foothold-seed-plan-v1`, which chooses an answer-free structural neighbor for each weak entry when one exists, prefers neighbors with fewer deterministic clue-risk flags, and records the exact crossing cells; this is a seed candidate, never a solve-probability or clue-ease claim. A new lab-only `sibling-construction-adapter-v1` accepts explicit board geometry, clue text, and caller-supplied familiarity/difficulty/letter-support estimates, computes request/result digests, and invokes the pinned sibling source when available. Explicit estimates now require a typed `sibling-estimate-provenance-v1` envelope: it records caller attestation, an uncalibrated status, the exact estimate fields, and an excluded list of fill-derived signals; envelope, estimate, and board/source bindings receive separate SHA-256 digests. Private generation wires its receipt without defaulting fill scores into player estimates: incomplete estimates are `not-invoked`, unavailable Node/package state is `failed`, and neither state affects play. Adapter output retains the simulator's uncalibrated-assumption boundary. Still required: independent hand-reviewed cases, trusted external estimate provenance, and calibration against playtests. |
| E10 | **Grounded clue pipeline:** generator language jobs/orchestration and lab review UI                                               | E04, E05, E20           | **Partial:** private generation now records uncertainty-labeled answer shape, visible clue-family/signal observations, literal signal counts, deterministic fact/proper-name risk, mechanical relation checks, punctuation scope, and an explicit `private-grounded-clue-bundle-v1` with answer-free fallback reasons, plus a `private-clue-grammar-bridge-v1` surface-only validator. The new `private-clue-grounding-validators-v1` adds literal typed spans and narrow deterministic witnesses for anagrams, reversals, quoted hidden-word clues, and the supported yes-translation table; every result retains `semanticStatus=not-established` and does not gate private play. A failed hidden-word witness is downgraded to the same answer-free fallback path as other mechanically false wordplay. `private-clue-semantic-challenger-v1` projects each pair into `safe-fallback`, `needs-review`, or `mechanically-supported`, with stable reasons and an explicit never-gates-private-play policy. The `make run` and `make run-personal` launchers enable a bounded local-model keep/fallback/review pass by default, while `CROSSWORD_PRIVATE_CLUE_CHALLENGE=0` opts out; malformed, missing, or unavailable responses fail open, remain advisory, and are retained in provenance without changing deterministic classifications. The private generator now consumes an optional verified `private-reviewed-clue-pack-v1`: exact matched clue text is preserved with compact pack/source/evidence receipts, reviewed senses/facts are supplied as bounded context for uncovered model clues, while an absent/unavailable pack remains an honest local fallback. Large definition-heavy boards now receive one bounded, fail-open `private-clue-diversity-repair-v1` pass over at most four unreviewed/non-weak surfaces, requesting visible quote, bracket, blank, or pun conventions; accepted rewrites still pass the existing surface, mechanical, and answer-safety guards, and the final receipt/UI labels the result as advisory. The UI/provenance exposes these diagnostics, literal marker counts, and reversible flags. The new `private-clue-quality-study-v1` evaluator and `scripts/private-clue-study.py` project only answer-free grammar/fallback/family/signal/repair/timing receipts from loopback jobs, with stable study digests and no semantic or player-quality claim. A `private-clue-review-bundle-v1` exporter and owner-scoped finished-session route now bind the exact manifest digest to every answer/clue pair, deterministic grammar and semantic-challenge receipts, explicit unreviewed fields, and a `publishable=false` local-review policy. The `/future` clue-quality panel can download that handoff after a finished game; it fails closed on tampered manifests or missing grounding records and never changes playable state. Still required: an attested production sense/fact pack, broader per-family validators and independent human challengers, and a complete reviewed clue/hint/explanation bundle. |
| E11 | **Integrated personal construction:** generator pipeline, native fill/repair, day-aware validators                                | E06, E08–E10, E21       | **Review candidate only:** durable jobs constrain xfill to the pinned eligible wordlist and build/store an immutable `PuzzleDocumentV2` review candidate when every entry has an exact admitted clue/sense/fact join. A digest-bound publication packet and structural gate remain non-publishing. The host has immutable candidate/array-index evidence artifacts and authenticated, append-only human claim receipts bound to the exact sealed packet and projected human claim. The reviewer roster does not prove real-person independence or blinding; receipts do not prove truth or evidence sufficiency, and machine claims remain unverified. The evaluator reports expected/verified human receipt counts and `human-attestation-incomplete`, but always remains `blocked` or `evidence-unverified`. Independent review found no current publication/actor/evidence bypass and confirmed there is no registry write path; the attestation resolver now reruns the shared gate itself before accepting a packet seal. No production writer, calibrated support estimate, human-attested content, reviewed/publication playable artifact, or published fixture exists; private experimental boards are playable through the separate `/future` path. The generator now has a replay-verified deterministic proxy artifact and a separate balanced seeded editorial screen with an exact-request replay artifact. Both bind opaque external digests and are not integrated into an app/job or persistence. The seeded output is not a player probability or machine receipt. The local answer-bearing review bundle now gives that lab pass a digest-bound handoff with per-entry grammar, semantic uncertainty, and difficulty-review slots while keeping publication and admission separate. Next: review and surface failures in the local lab; resolve candidate/build/estimate provenance and calibrate on real traces before any machine claim. |
| E12 | **Profile synthesis:** application update/validation code, Node runner, host revision repository                                  | E05, E07, E22           | Partial: the deterministic episteme reducer, revisioned host projection, explicit controls, solve/reflection/calibration/postgame evidence, CAS/idempotency, rebuild and deletion paths are live. `/future` exposes that projection and can request a local-only `private-profile-narrative-v1` field note from a frozen source digest; paragraphs, questions, and bounded seek/exclude proposals carry allowed evidence IDs, Qwen 3.8 27B has produced a verified local receipt with model digest/runtime counters, current-revision/stale state, replayable persistence, archive round-trip, and profile deletion coverage. A proposal is accepted only through a narrative-bound, current-revision route that writes standard explicit-preference evidence, with idempotent replay and stale-note rejection. Request-scoped rebuilds create a new source-bound narrative candidate without changing the episteme revision. The living episteme also exposes a separate Tensions lane for contradictory/ambivalent claims, plus Keep, Set aside, and Release lock controls for projected claims; each correction is a scoped explicit-preference event and refreshes the projection, so an explicit lock can be revised without editing the ledger directly. The living episteme now expands contradictory claims into a bounded support/counter-signal explanation while keeping the history intact. Tension claims now also accept an optional player-authored correction note; the note is stored as explicit preference evidence through the existing CAS reducer and remains reversible in the ledger. Narrative lifecycle coverage now includes a generated note becoming stale after a revision and rejecting a subsequent suggestion acceptance, with matching browser behavior that keeps the note visible but disables stale controls. Still required: broader contradiction editing beyond the bounded tension controls. The field-note generator now prefers the saved profile model choice when that exact local tag is installed, records `private-profile-narrative-prompt-v1`, and exposes the model/prompt receipt in the panel. |
| E13 | **Associative field:** product association repository/projection code; generator language jobs                                    | E08, E12                | Partial: calibration proposals and postgame loopback proposals now use strict source IDs, bounded relation/path schemas, model receipts, replayable evidence, and player keep/not-for-me/pass responses. Generated repetition never becomes a claim; postgame model proposals now carry a 30-day/10-session expiry envelope and the projection exposes expired provenance so the brief excludes stale paths. Their generated run metadata now carries a deterministic relation/parent diversity receipt without turning variety into a user trait. The private puzzle receipt now adds `private-association-steering-v1`: it records bounded eligible/expired/rejected counts, source and relation diversity, and reversible steering status without copying association phrases or answer text; expired and explicitly rejected/passed paths are removed from the active generation context. A player-kept postgame path can now open one durable second-generation path, bound to `association:<parentId>`, stored in the existing run archive, and answered with the same keep/set-aside/pass controls. The postgame cards also accept a touch right-swipe for keep and left-swipe for set-aside while preserving the explicit button/keyboard path. Lexicon resolution and broader diversity evaluation remain. |
| E14 | **Reflection deck:** product authored-card pack, `ReflectionDeck` UI and response use cases                                       | E12                     | Accessible keep/not-for-me/pass/undo; fixed pre-response mappings; 60–100 reviewed cards; skipped cards have no preference effect. The host response snapshot also returns the exact evidence and episteme revision, and the UI exposes the seek/avoid mapping plus immutable retract/restore revision receipts after reload. Touch users can keep a statement with a right-swipe or turn away with a left-swipe; pass remains an explicit button so an undecided gesture has no preference effect. |
| E15 | **Existing-app integration:** `apps/react`, Flask original-puzzle API and setup targets                                           | E03, E11, E19, E22      | Calibration→weekday→host preparation→solve→reflection→optional postgame association paths now runs in the current app; model synthesis starts after reflection readiness and never blocks solve completion. The delayed language-review panel waits for the same host-profile readiness promise as private puzzle/session sync, avoiding a first-load 404 race before the profile is created. The future solver header now uses the selected personal recipe label instead of deriving a weekday from the generated board’s calendar date; the daily route keeps its existing date-derived label. Optional postgame associations now still load when the authored reflection deck is unavailable. Cached play, cancellation, and restart recovery are implemented; the idempotent durable-job request and its polling path now perform bounded abort-aware retries after transient network failures and expose a reconnecting state. `/api/future/reviewed-samples/sator-square-v1` now returns a host-registered, authored CC0 warm-up through the same solver/session path when Ollama is unavailable, and the controls label it as non-personalized sample content. Broader host-restart acceptance remains. Finished reflection recovery is now bound to the restored puzzle identity, so a new board cannot inherit the previous board’s cards or association paths after reload. The postgame “Make one more personal crossword” action is now browser-covered end to end: it creates a second durable job/session and clears the prior reflection deck, receipt, and finished-session binding before the replacement board opens. The pure V2 adapter and backend published-only session APIs exist; `/future` uses its separate private V1 generation/session path and does not depend on published V2 content. Human claim receipts now exist; independent review found no current bypass; the former P2 future-use guard is now closed by the resolver-side shared-gate check. Machine evidence, real-person independence and actual blinding remain unresolved. The private control bar now surfaces the bounded generated theme thread after a local puzzle is ready, so the player can see how the current board was personalized without exposing hidden profile evidence. Its personalization receipt also reports the bounded theme invitations and whether any survived fill-quality selection, so a released theme is visible as an honest construction outcome rather than a silent disappearance. The answer-free game-history route and panel now retain the generated episteme revision, bounded input lanes, association steering counts, and clue-surface diversity for each saved game, making the profile-to-board and construction trace inspectable after reload. No new `apps/web` migration. |
| E16 | **Your words and portability:** product profile editor, evidence UI, continuity archive v2, deletion/retention jobs               | E12–E15                 | **Partial:** read-only export now includes postgame association receipts/responses and revisioned profile narrative snapshots alongside the profile-scoped private candidate evidence sidecar, using one coherent SQLite snapshot. `EXPORT_INTEGRITY_VERSION=profile-export-integrity-v1` adds a canonical SHA-256 envelope receipt to new archives; import verifies it before row validation while continuing to accept older archives without the optional receipt. Narrative rows are now revalidated against the imported episteme evidence IDs, including bounded proposal links, before any restore transaction. `DELETE /api/future/profile/:id` removes profile-owned calibration, episteme, narrative, solve, reflection, queue, and private-candidate rows atomically while retaining shared manifests; the `/future` panel clears browser journals and the bounded local shelf of recent private puzzles; that shelf now stores a compact board plus bounded provenance projection, dropping large per-clue model transcripts so full-size generated boards survive browser reload. A late-worker regression covers no resurrection. The profile panel reads the same projection after reload, so the user can inspect live signals, open threads, and the latest field note before exporting. `POST /api/future/profile/:id/retention` now provides a same-origin, dry-run-capable bounded policy: seven-day transient jobs, 30-day ready private-puzzle artefacts, no running-job deletion, and no solve/calibration/episteme/manifest deletion. A SQL-aggregate preflight now rejects over-cap archives before materializing the nested export graph, while the final serialized-body check remains as a second defense. Still required: broader retention/backup policy and evaluation. |
| E17 | **Learning pack and scheduler:** product domain scheduler, content pack tooling, input-token support, learning UI                 | E04, E07, E11, E15      | **Partial:** selected-language exposure creates a local recall queue with clue/length prompts, opaque task handles, explicit answer reveal, separate independent/assisted response records, a 24-hour → 7-day → 30-day baseline spacing ladder, contiguous-streak resets, bounded later-streak interval extension, and a calm three-item default due budget with bounded six/twelve-item expansion; records survive profile export/import/deletion. The delayed-review cards now offer an optional local recall field so a player can type and submit an independent attempt before revealing the answer; the text never leaves the browser and the existing assisted/independent response contract remains unchanged. A first-time language selection now offers at most one private, synthetic starter form when the local fill dictionary can place it; it is explicitly marked `synthetic-unadmitted-not-established`, does not increment exposure or mastery, and only enters recurrence after a generated clue creates exposure evidence. Due language forms now lead the optional local-fill candidate order in both synchronous and durable queued private generation (the worker preserves the frozen profile ID), with deterministic candidate weights (`due` 1.0, `not-yet` 0.9, `assisted` 0.8, `pending` 0.65, optional 0.5), and due forms with scheduler history now receive a separate bounded priority signal (stage and last response) so equally due candidates are ordered by need without becoming locks or mastery claims. A shared explicit-language signal detector recognizes generated clue forms such as `Yes in German`, `German for yes`, and `German word for yes` in learning provenance, finished-session task links, and the contextual reflection deck; if a local model emits an ambiguous starter surface such as `German refusal`, the private clue pass repairs it to an explicit form such as `German for refusal` before session linking. It does not infer a language from unrelated clue text. A previously remembered form can re-enter only after its scheduler interval expires; no form becomes a hard grid lock or mastery claim. The ready-board controls now show a bounded language-recurrence receipt (count, review stage, and overdue count) without exposing task forms or converting the schedule into a mastery claim. The policy envelope now exposes a diagnostic-only, fixed-grid exponential forgetting fit after eight mixed independent outcomes, with explicit sample counts, decay/half-life, model version, and scheduler-coupling false; it does not alter due dates. A deterministic delayed-recall study fixture now covers exposure, independent successes, assisted recall, not-yet reset, spaced transitions, and exclusion of assisted events from the diagnostic sample. A future-only accented input adapter now normalizes NFC/combining accents and explicit fill aliases for German, French, Spanish, Italian, Portuguese, and Dutch without changing `/`; multi-character aliases are accepted through the existing future-only rebus cell path and expose answer-free display/fill metadata, while the strict journal persists canonical fill strings. The new versioned `future-token-manifest-v1` sidecar binds each private solver cell to display and canonical fill units, validates crossing equality and puzzle-digest binding, and is consumed on private save/restore without widening `PuzzleDocumentV2`. `future-token-producer-v1` now supplies a concrete future-only adapter for an explicit language task: it accepts only a declared entry/cell display hint whose canonical fill already equals the generated cell token, propagates that token across crossings, seals the sidecar, and renders the display grapheme while the controller/journal retain canonical fill; shared check/reveal now also compares and writes those canonical fill tokens, so displayed accents/rebus forms do not register as false errors. It never collapses two ordinary ASCII cells or guesses accents; native xfill therefore remains ASCII-only until a producer emits cell-level token sequences. The future-only delayed-review lane now has a deterministic 22-pair German/French/Spanish/Italian/Portuguese/Japanese/Dutch fixture contract in `src/crossword/language_task_pack.py`: every pair carries source metadata, `language-task-grammar-v1` metadata, a pack digest, and explicit `synthetic`/`unadmitted`/`not-established` statuses. An optional `CROSSWORD_REVIEWED_LANGUAGE_TASK_PACK` loader now accepts only an explicitly `reviewed-admitted` pack with artifact SHA-256, license, reviewer, admission and grammar metadata; due items expose `Reviewed task` or `Local fixture · meaning unverified` so provenance is visible. Invalid or absent configuration never upgrades synthetic content. A reviewed pair may also declare a one-cell display spelling such as `CAFÉ` for canonical fill `CAFE`; when no reviewed pack is configured, the private experimental lane can use the same explicit one-cell spelling from a tiny synthetic map and labels its provenance `synthetic-unadmitted`; in either case generation emits an exact `across-N`/`down-N` token hint, so the future-only producer can render the grapheme without changing xfill geometry or guessing accents. Matching private answer-form exposures receive answer-free pack metadata in the due item and answer metadata in the local reveal response; the host solve-session task link now carries the same bounded pair ID, pack digest, source text, and synthetic/admitted status without copying the target form into the ledger, and delayed review prefers that stored receipt over a later pack re-resolution. Unmatched forms retain the existing clue-only review behavior. Generated language clues now use the local task pair's explicit source text (for example, `French for yes`) when a candidate form matches the pack, and `languageLearning.taskPairSources` records the pair ID, pack digest, source text, and synthetic/admitted status; exact reviewed clue text still takes precedence. No reviewed pack is bundled here: the loader is contract infrastructure, not native-speaker validation, semantic truth, or mastery evidence, and it is not wired into `/`, ordinary construction, publication, or the episteme reducer. Explicit native multi-unit construction is now wired through the private token envelope; still required: genuinely reviewed language content/task pairs, richer reviewed task links, and broader multi-instance language/play evaluation. |
| E18 | **Pilot and hardening:** both repos’ evaluation tools, tests and docs                                                             | E11–E17, E19–E22        | **Partial:** the E08 synthetic seek/avoid report is now a repeatable retrieval/diversity harness with digest-bound output and explicit non-quality limitations. The bounded `model-evaluation-report-v1` adds a deterministic structural projection of the paired holdout, with schema/task-gate/latency/output-size/integrity metrics and exact runtime context; it leaves semantic/editorial/player fields pending and makes no winner claim. `private-fill-quality-study-v1` now evaluates fixed-seed native retry receipts, reports measured versus unavailable score fields and selected-attempt summaries, and binds the artifact to a canonical digest; `private-fill-quality-comparison-v1` pairs policy and baseline reports at shared seeds and reports mechanical deltas without a winner claim. These tools make no human solve-probability or enjoyment claim and do not gate private play. The checked synthetic artifacts and seven contract tests establish the evaluator shape. It is still an exploratory artifact, not a powered pilot. A real Gemma Tuesday receipt is reproducible through `private-clue-quality-study-v1` at `docs/evidence/private-tuesday-clue-quality-study-v1.real-gemma4-26b-20260928.json` (the earlier 18-surface floor) and the pre-change target receipt at `docs/evidence/private-tuesday-clue-quality-study-v1.real-gemma4-26b-20260928-target.json`, which records 74 checked entries, 0 deterministic grammar issues, 1 fallback, 28 non-definition surfaces (37.8%), and four families without claiming semantic fairness. The stronger Tuesday policy now has live answer-free receipts: the former 42% run at `docs/evidence/private-tuesday-clue-quality-study-v2.real-gemma4-26b-20260928.json` and the current 48% run at `docs/evidence/private-tuesday-clue-quality-study-v3.real-gemma4-26b-20260928.json` (seed `20470392`, 74 entries, 36 non-definition surfaces (48.6%), six families, zero deterministic grammar issues, four fallbacks, and `floorMet=true`). The evaluator now also emits grammar-clean, family-floor, target-rate, and aggregate observed-rate metrics for each bounded study. Still required: real admitted-content runs, blinded human/player resonance and convention-learning measures, per-family grammar/Thursday review, and host/client reliability plus release reports. |
| E19 | **Calibration interpretation and lifecycle:** `apps/react/src/future/`, `packages/domain/src/calibration.ts`, calibration and hypothesis host APIs, stimulus catalog | E01, E02, E12, E13 | Delivered slices: 64 versioned stimuli, five append-only movements, deterministic positioned offers, selector-v2 rejection sampling with selector-v1 replay stability and fixed-seed cohort tests, accessibility modes, separate explicit setup, local/host CAS journals, host restoration, prefix-only retry and conflict preservation, cursor-progression guards, and opt-in source-digest-frozen local-model proposals with exact provenance, keep/not-for-me/pass, undo/restore, bounded influence, expiry and later profile review. Incompatible branches now receive explicit onboarding recovery copy and two safe actions through `apps/react/src/future/calibrationRecovery.js`: keep the local branch (without mutating its journal) or start a fresh calibration id while preserving the prior IndexedDB record; `calibrationRecovery.test.js` and the FutureApp conflict fixture cover the presentation, setup preservation, new-branch pointer, and raw-record retention. Calibration hypothesis cards now also accept a touch right-swipe for keep and left-swipe for set-aside while preserving explicit pass and keyboard/button controls. Remaining: human salience/accessibility and skip-vs-calibration evaluation; repeated-deck fatigue; richer proposal diversity and lexicon grounding. Raw choices remain distinct from explicit preference, knowledge, and solve evidence. |
| E20 | **House clue grammar:** domain `clueGrammar.ts`, `tools/clue-grammar/`, model schemas and renderer spans                          | E01, E04                | **Partial:** versioned family/role/grammar distinction and structural morphology, punctuation, cross-reference, mechanic, language, abbreviation, fill-blank, and signal-span checks now have an exported original 200-case matrix (`10 accepted + 10 rejected` for each of the 10 current families). The authored release pack covers additional morphology, abbreviation, punctuation, linked-reference, wordplay, and mechanic variants; every fixture records its intended reading, defect/reason, repair, and expected issue codes, with exported per-family counts. The matrix test keeps structural validity separate from `semanticStatus=not-established`. An explicit Unicode-aware admission-mode safety option now rejects answer roots/inflections, dead-end templates such as `common name`, and visibly mismatched plural/past markers while leaving legacy structural V2 fixtures compatible; the pack builder always enables that option. The private semantic challenger now gives the local diagnostics a typed fallback/review/mechanical-support projection, but it intentionally does not count as a semantic validator or independent challenger. The private witness layer now adds a quoted hidden-word comparison as a narrow mechanical relation, with a safe fallback on mismatch. The future assistance ladder now gives answer-free contextual explanations for question marks, quotations, brackets, abbreviations, plural and explicit tense markers, explicit language labels, and fill-in-the-blank surfaces, while preserving the existing clue-reading journal event. `/future` now opts into renderer-only clue-surface annotations for those signals (with hover explanations and keyboard/screen-reader labels) while the daily `/` route keeps the exact existing clue text and behavior. Still required: sense/fact-bound validators and independent human challengers, familiarity evidence, and broader renderer/import coverage. |
| E21 | **Weekday recipes and mechanics:** generator recipe/mechanic registry, native adapter, token model, solver input/rendering        | E01, E04, E06, E09, E10 | **Partial, with a working Sunday lane:** day-specific ordinary-letter-grid recipes and the typed shared-affix fallback are implemented. The private fill selector now retains at least two requested theme locks when a measured candidate stays within a bounded 25%-weak-entry band, while preserving the open-grid fallback when no such candidate exists. Two deterministic Thursday fixture boards (suffix `AT` and prefix `RE`) now assert validated mechanic provenance, exact themed answers, and one-letter solver cells; a mismatch fixture asserts `unavailable` / `fill-pattern-mismatch`, ordinary-letter-grid provenance, and no mechanic passed into clue generation. `src/crossword/weekday_mechanics_evaluation.py` adds `private-weekday-mechanic-evaluation-v1`: deterministic multi-instance reports require every declared themed answer to obey the shared prefix/suffix, reject inconsistent instances, and accept only the explicit ordinary-grid fallback; the six-test `tests/test_weekday_mechanics_evaluation.py` slice covers both generated-shaped fixture boards, mismatch/fallback safety, deterministic suite output, and uncertainty labels. The same module adds `private-sunday-size-gate-v1`, which blocks Sunday unless the requested grid is exactly 21×21 and both native-construction and solver-UI capabilities are explicitly true; non-Sunday recipes are not relabeled. The native xfill adapter now carries an explicit `gridSize: 21` through the host/runtime boundary, dynamically validates 21×21 symmetry and entry bounds, filters impossible long slots before Rust fill, and uses a bounded personalized-theme probe followed by a deterministic Sunday anchor with retained weak-fill uncertainty. A real current-source native smoke returned a playable 21×21 board with 136 entries (mean score 68.76, 20 iffy, 66 weak) in the anchor lane; the full Flask-context generator reached finalization with dynamic 21×21 metadata and clue construction. The future-only `future-token-manifest-v1` adapter now carries explicit display graphemes plus ASCII fill-unit sequences (including `ß` → `SS`) through validation, private storage, and solver restore; `future-token-producer-v1` can adapt a native-shaped future task when the constructor explicitly emits a cell-level `SS`/`OE`/etc. token and a display hint, propagating crossing equality and showing display tokens in `/future` while preserving canonical fill and journal behavior. Reviewed language pairs can now emit one-cell accent hints into the producer path without changing xfill geometry; the private generator decorates those exact hints into a validated `tokenCells` receipt (`private-language-decorator-v1` for synthetic local forms, `reviewed-admitted-v1` for admitted forms) before private manifest registration. Shared controller check/reveal compares and writes canonical fill, so those displayed tokens are not marked false. A token-aware native result may now carry a lexical answer plus explicit `cellTokens`; the validator and private legacy adapter preserve those sequences and register replayable `answerTokens` while checking both crossings, so a future constructor can emit multi-unit cells without being rejected as malformed one-letter data. A two-cell `SS` sequence still cannot be collapsed after ordinary xfill because that would change geometry; the producer rejects that case. The private host now accepts an optional `native-token-construction-v1` `tokenCells` envelope from a future constructor: it validates display/fill sequences, crossing agreement, and explicit per-entry cell token sequences, projects accepted cells into the existing future token producer hints, and records accepted/absent provenance without changing ordinary xfill. Private legacy manifests can now carry per-cell `answerTokens` for those accepted multi-unit cells; the browser descriptor and host journal use that sequence for replay/check truth, while the ordinary `/` manifest path remains unchanged. The future journal also canonicalizes a display-token reveal such as `ß` back to `SS` before recording it, so assistance and reveal events cannot become false wrong letters. The future-only rebus editor now keeps the display grapheme in the input while storing the canonical fill token underneath, and the assistance ladder calls a multi-unit reveal a token rather than a letter. The strict V2 publication schema and `/` remain single-token. The private host now includes `construct_native_token_grid`: an explicit `native-token-construction-v1` envelope can expand a declared multi-unit cell such as `ß`/`SS` into crossing `cellTokens`, register replayable `answerTokens`, and preserve ordinary one-cell aliases without widening `/`. The future solver now marks declared token cells with a bounded visual/accessible token marker and keeps the display grapheme visible in the input while canonical fill remains journal truth. Still required: reviewed multi-instance mechanic evaluation on real model boards and human evaluation of Sunday fill thresholds. |
| E22 | **Host API and durable jobs:** Flask `api_v1/`, `jobs/`, product Node runner and process setup                                    | E01, E02, E06           | **Partial:** same-origin job APIs use conditionally fenced SQLite leases; V4 jobs freeze the compiled brief and receipt, with V3 compatibility. The worker constrains xfill to a private eligible wordlist and stores review candidates with private sidecars. A separate V2 published table starts empty and has a GET envelope; published-only V2 session/event/analysis routes enforce strict registry resolution, `sha256:` prefixes, replay/final-analysis revalidation (19 V2 tests; 37 including V1/replay), and a reviewed pure UI adapter (8 tests). Flask requires a reviewer credential and supports an optional configured roster (40 auth/config tests). The host now stores immutable candidate-bound artifacts plus authenticated human claim-attestation receipts at `/api/future/evidence/v2/attestations`; natural-key retries are idempotent and conflicting content is rejected. Receipt resolution is tied to exact packet digests and semantic human-claim projections, while the underlying artifacts remain candidate/array-index bound. The evaluator reports expected/verified human receipt counts and missing-claim status, but always remains `blocked` or `evidence-unverified` and never writes publication state. Independent review found no current publication/actor/evidence bypass and confirmed no registry write path. The former P2 future-use guard is now closed: `resolve_publication_packet_attestations` reruns the shared TypeScript publication gate against the frozen candidate and packet before it accepts a declared digest, so future callers cannot bless a stale or caller-mutated seal by passing the matching string. Coverage alone still never authorizes publication. Machine evidence and publication do not exist. Removing private `profileProjection` changes the `quality=review` digest; any eventual publication must derive/reseal a public `quality=accept` puzzle and retain source-candidate and review-packet digests in immutable audit data. The next safe milestone is reproducible machine evidence, not publication. No production writer or content exists. |

E05, the remaining E19 interpretation work, and contract/content work are independent enough to execute concurrently if a later implementation owner chooses multiple agents. File ownership must be assigned explicitly and shared contracts agreed first. This plan itself does not require spawning agents or creating tasks before review.

### Effort and uncertainty

Budget provisionally 55–95 focused engineering days plus editorial/language review and several weeks of overlapping playtest time for the expanded initial release scope, including a real Wednesday/Thursday experience and the associative opening. This is a planning range, not a measured estimate or delivery commitment. Corpus cleanup, native mechanism support, reliable multi-token input and host/outbox reconciliation can materially expand it; browser porting and a new static UI are removed from the critical path. Re-estimate after E06 and E11, using actual preparation speed, fill acceptance rate, and human editing time per puzzle.

Do not parallelize away unknown interfaces. The critical path is **trustworthy events/content → viable runtime → fair grounded full-size construction → meaningful personalization evaluation**. A future business model, account-based cross-device sync, public sharing network, attributed multiplayer, every language, cryptics and Sunday-scale special grids are later capabilities with separate acceptance criteria. Wednesday and a genuine Thursday are core early proof points, not deferred indefinitely behind Monday.

## 22. Private-game implementation handoff for Luna

**Updated:** 28 September 2026. Private local play is the immediate product. Publication evidence, curator work, and source licensing are explicitly later concerns; they do not gate private puzzles.

The working route is now connected end to end: `/future` starts without a daily-feed request, the player chooses a weekday and explicitly creates a personal crossword, Flask freezes the profile/episteme snapshot into a durable private job, the local worker uses Gemma/Qwen and native xfill, and the existing solver records play and reflections. A real Gemma 4 26B browser run opened a **15×15 / 78-entry** board in about **58 seconds**; later live Wednesday and Thursday requests produced 70–76 and 74 entries in roughly 70–86 seconds. The latest Wednesday request took **70.553 seconds** (theme 6.500s, xfill 11.865s, clues 51.927s) and reported `clueQuality.issueCount=0`. Polling now exposes the worker’s actual `theme-proposal`, `native-xfill`, `clue-generation`, and `finalizing` transitions behind the active lease, with no fabricated percentage progress. The browser job path normalizes the worker envelope into the shared solver format, creates the host session, accepts typed letters, and restores the same puzzle and saved journal after reload. The CI Playwright path exercises the same queue/poll/session handoff with an isolated synthetic fixture; its six tests pass. `/` retains its daily crossword behavior. The generated result is private experimental content.

Local persistence stores the exact returned board plus a bounded provenance projection per profile in browser storage; the existing IndexedDB solve journal retains progress. `POST /api/future/private-puzzle-jobs` is the normal path, with idempotency, profile snapshotting, queue state, polling, cancellation, and a compatibility fallback to `POST /api/future/private-puzzles` for older local hosts and test fixtures. The local worker can take a minute or two without blocking the web process; cancellation stops waiting immediately and fences any late result from replacing the active board. Generated puzzles are still experimental: semantic fact grounding and richer clue editorial quality remain the next product tasks. A current `make run-personal` smoke on 28 September rebuilt the React bundle, passed the read-only runtime doctor, served both `/future/` and `/` with HTTP 200, and returned `runtime-readiness-v1` with both preferred Ollama tags, native xfill, database, queue, and a fresh worker heartbeat ready. The personal solver header now receives the selected recipe label explicitly, and the browser shelf compacts large clue provenance before local persistence so a full-size board stays under the storage budget. A fresh current-source Gemma 4 26B run then exercised profile creation, durable queue polling, native xfill, clue generation, and cleanup: the Wednesday job reached a playable 15×15 board with 72 entries in 190 seconds, retained one `clueQuality` issue for player-visible inspection, and deleted its temporary profile with HTTP 200.

The latest pushed slice (`15335fa`) makes the optional private-domain bridge discoverable at setup time: `make runtime-doctor` reports only the configured label and placeable-term count, never the terms, treats an absent hint file as optional, and fails visibly on a malformed configured file. The focused doctor/domain-hint tests pass, and the existing six-test Playwright browser gate still passes after the change.

The current full local gate also passes: `make test` selected 872 Python tests (three live-provider tests deselected), 11 legacy Jest tests, 146 domain tests, 8 persistence tests, 243 React tests, and 8 application tests. The only output requiring follow-up is the existing SQLAlchemy UTC deprecation warning and React `act(...)` warnings in tests; neither failed the gate.

The private clue morphology guard now also preserves valid invariant plural answers (`SHEEP`, `DEER`, `FISH`, `MOOSE`, `SALMON`) when a clue explicitly marks a plural, while continuing to replace singular-shaped answers such as `CAT` under the same marker.

That guard also covers explicit comparative and superlative markers, including irregular forms such as `BETTER` and `BEST`; mismatched forms are surfaced in the same reversible clue-quality notes and fall back to an answer-free crossing scaffold.

### Existing foundations and archived implementation notes

The following 26 September assessment describes the system before private generation was connected. Its statements that `/future` still loads a daily puzzle or that no playable path exists are historical and superseded by the current status above. The opening records offers and reversible choices; the host replays solve events against frozen manifests; profile controls, reflection responses, and calibration hypotheses enter a revisioned ledger. Continue to preserve these working foundations and `/` parity.

### 26 September follow-up after implementation review

- The generator now exports `reportAnswerPositionInformationGain`, a per-position exact-letter candidate-mass report. It emits numeric pruning only when alternatives are declared complete and reviewed; incomplete sets remain unknown. It is a candidate-mass proxy, not human solve probability or calibrated familiarity. Existing reachability/scaffolding remains a separate concern and is not yet integrated into candidate search or lab review.
- `publicationV2.ts` adds an immutable candidate-digest-bound review packet for source/license terms, each clue's semantic/editorial decision and independent challenger, crossing certificates and seeded simulation, weekday/foothold classification, and Thursday mechanic routes. It checks packet digest, exact candidate links, plain-object ownership, a strictly descending support-layer DAG, and Monday's available quadrant footholds. It always marks reviewer/evidence claims unverified; no trusted reviewer identity service, evidence-artifact resolver, host publication record, or playable transition exists. Its hash detects edits but does not authenticate authorship. Remaining Plan §13 work includes independent/brittle-support analysis, masks and familiarity-aware estimates, verified simulation output, and real play calibration; §14 still needs actual source, clue, fact, and challenger review.
- An independent survey of the current host/authentication surface found no authenticated principal, admin role, CSRF framework, or reviewer credential. Localhost binding, origin checks, profile IDs, and session-writer capabilities do not authenticate a reviewer. There is no production writer for a published registry; any future journal API must resolve published records only after an explicitly implemented trusted publication boundary exists. Before publication can be enabled, add a server-trusted authenticated principal or a genuinely host-authenticated offline receipt-import path, plus evidence resolution and the atomic publication transaction. Keep production publication disabled until then.
- `analyzeSessionV2Document` is a separate async replay entry point, selected by explicit `analyze-v2-document` Node/Python bridge operation. It validates the V2 digest and session hash, checks contiguous event ordering with one initial start and terminal finish, and reuses the deterministic reducer. Its V2 runtime import is deferred so existing V1 episteme/reflection bridges still work. This enables analysis only: no V2 session can be created or appended, and review candidates remain non-playable.
- Verification after these changes: serial `make test` passed **397 Python tests** (3 provider tests deselected), **11 Jest**, **128 domain**, **8 persistence**, **117 React**, and **8 application** tests. Product typecheck, ESLint, and Prettier passed. The sibling generator's full `npm test` passed **122 tests** across construction, generator, local-runtime, model-runtime, and lab workspaces; its construction build, lint, and formatting also passed. No production source attestation, human review packet, or positive publication fixture was created.

### Published-V2 adapter and journal continuation (26 September)

- The pure published-V2 adapter is complete and independently reviewed (**8 tests**). It validates the full V2 document and digest, requires a `published` envelope with a digest-bound receipt, preserves entry/clue IDs and maps the grid and clue text. Its synthetic fixtures test the contract only; no published fixture or live content exists, and the adapter is not a production publication path.
- The host now has a separate published-V2 table, empty by default, a GET envelope, and V2 session/event/analysis routes. Resolution is strict and accept-only against that registry; V2 digests must retain the `sha256:` prefix. Create/replay and finalized-analysis reads revalidate the published record/receipt. Focused coverage is **19 V2 journal tests** and **37 combined V2 plus V1/replay tests**. V2 does not use the V1 manifest registry.
- At the earlier V2 journal checkpoint there was no production insert/publication writer or Flask-wired reviewer identity. The current receipt proves only shape/integrity, not reviewer authorship or evidence truth; no live content or published fixture is being claimed. The current CAS and event-payload hashes detect ordinary corruption, but a person with direct SQLite access could coordinate a rewrite of records and hashes. Cryptographic or externally anchored append-only history is later hardening, outside this slice.
- At this earlier checkpoint, `src/crossword/reviewer_auth.py` and its **22 tests** implemented the pure single-reviewer credential resolver. It strictly parses a Bearer credential, compares the configured token with `compare_digest`, takes reviewer ID only from server configuration, and fails closed when configuration or credentials are missing, malformed, or mismatched; request-supplied IDs are not trusted. Flask app configuration wiring was then outstanding; see the newer checkpoint below for completion and the current active slice.

### Reviewer configuration and publication-boundary follow-up (26 September)

- Flask resolves the required `CROSSWORD_REVIEWER_TOKEN` / `CROSSWORD_REVIEWER_ID` pair plus a strict optional `CROSSWORD_ADDITIONAL_REVIEWERS_JSON` roster. The server derives each principal, ignores caller-supplied IDs, compares every configured token without early success, rejects duplicate identities/tokens and malformed roster JSON, and fails closed. Resolver plus app-config coverage: **40 tests**. This supports separate configured blind raters for the local installation; it is not general account authentication or credential rotation.
- The shared TypeScript gate is callable through `evaluate_puzzle_v2_publication_gate`; its Node bridge accepts exactly candidate and packet and has no verification or publication flag. The Python boundary now accepts only the exact result envelope and exact gate-result shape, known statuses, digest form, and reason records. Focused replay suite: **13 tests**. The gate can return only `blocked` or `evidence-unverified` and cannot publish.
- The immutable evidence store is implemented at `POST /api/future/evidence/v2/artifacts`. It authenticates the configured reviewer, requires a strict existing review-candidate digest, computes host artifact IDs and SHA-256, and exposes no byte-read/update/delete route. Uploads are capped at 8 MiB per artifact and by an atomic 256 MiB global quota; packet resolution has a 16 MiB serialized-packet bound and an early 4,096-reference budget. Each artifact is assigned a candidate-bound array-index claim path and allowed kind; the resolver rechecks candidate, bytes, hash, path, and authenticated uploader ID for human-owned claims. These paths do not yet bind to the sealed packet digest or canonical complete-claim digest. The source attestation's declared `artifactSha256` is checked against its source-artifact evidence hash by the shared gate. The focused evidence suite passes **46 tests**.
- `src/crossword/publication_review.py` composes the shared gate, artifact resolver, and human receipt resolver for the exact candidate and packet. It preflights packet size, node count and depth, passes one bounded detached snapshot through all resolvers, and returns a frozen redacted diagnostic with expected/verified human claim counts. It adds `human-attestation-incomplete` for missing receipts, but even complete human coverage cannot move the status beyond `blocked` or `evidence-unverified`; it does not touch either publication registry. The existing candidate fixture is synthetic and the real gate correctly blocks it. Independent review found no current publication/actor/evidence bypass and confirmed no registry write path. The former P2 future-use guard is closed: `resolve_publication_packet_attestations` reruns the shared gate against the frozen candidate and packet before accepting a declared digest; receipt coverage alone is not publication authorization. Uploaded artifacts remain candidate/array-index-bound, while receipts add semantic claim and sealed-packet binding.
- The independent review at this pre-attestation checkpoint confirmed the resolver is not itself a packet verifier: it did not verify packet schema/digest/outcomes, machine provenance, evidence sufficiency, or claim truth. The then-next safe vertical slice was a host-created human claim-attestation receipt. That slice has since been implemented as described below; the receipt still does not establish claim truth or authorize publication.
- The additive claim and quota tables initialize through the current `db.create_all()` startup path. Existing artifact bytes survive; their unrecorded claim paths cannot be safely inferred, so they fail closed during resolution and require re-upload/reassignment. Quota initialization counts pre-existing blob bytes. A file-backed legacy-SQLite regression covers the additive table/FK and fail-closed legacy behavior.
- A review candidate has `quality.verdict=review`; removing its private `profileProjection` changes the public document and its digest. Only a trusted host transition may derive and reseal a public `quality.verdict=accept` document after every required gate passes. An eventual atomic publication transaction must retain source-candidate, review-packet, final public-document, reviewer and resolved-evidence identities. Never accept a client-selected verdict or digest.
- No production publication writer, published fixture, human-attested production content, or played personalized puzzle exists; the published table remains empty. Keep publication disabled until every required human and machine evidence gate is implemented and independently reviewed.
- Pre-attestation verification only: focused auth/evidence/schema/bridge suites passed (**100 tests**) and the evaluator suite passed (**11 tests**); before the human receipt code, `uv run pytest -q` passed **522 tests**, skipped **3**, with one existing datetime deprecation warning, and `make test` exited 0 with root Jest **11**, domain **129**, persistence **8**, React **125**, and application **8**. These full-suite counts do not include the receipt implementation below.

### Human claim-attestation implementation (26 September)

- `src/crossword/publication_attestation.py` adds the SQLAlchemy `PublicationClaimAttestation` model/table and authenticated `POST /api/future/evidence/v2/attestations`; the model is registered from `app.py`. Receipts are stored outside the sealed packet. The host requires an authenticated configured principal and validates the exact TS-gate-accepted candidate and packet digests before resolving the requested human claim and its stored evidence.
- Each immutable receipt binds the logical claim path and canonical projected-claim digest to an ordered artifact manifest containing artifact IDs, SHA-256 hashes, kinds, and paths, plus the manifest digest, configured principal, host-created timestamp, and protocol version. Human projections intentionally omit clue `.challenger`, weekday `.blindClassifications`, and `.mechanicRoute`; each blind classification is instead its own logical human claim and requires its own configured-principal receipt.
- Idempotency uses the database natural key `(candidate_digest, packet_digest, claim_path, principal_id)`, not a caller-supplied key. An exact retry returns the same immutable receipt; different claim or evidence content at that natural key fails closed. The underlying uploaded evidence artifacts remain candidate- and array-index-bound; the receipt adds the sealed-packet and semantic human-claim binding.
- `publication_review.py` reports expected and verified human receipt counts and adds `human-attestation-incomplete` when coverage is missing. Its status remains `blocked` or `evidence-unverified` even when all human receipts are present; it does not write a published puzzle, accepted document, or other publication state. Machine claims remain unverified.
- These receipts prove only that a configured credential attested to the exact packet claim and artifact manifest. They do not prove truth, evidence sufficiency, distinct real people, actual blinding, resistance to credential rotation/reassignment, or immutability against direct database access. Independent review found no current publication/actor/evidence bypass and confirmed there is no registry write path; the former P2 future-use guard is now closed by the resolver-side shared-gate check. No machine receipt, publication writer, accepted document, human-attested production puzzle, or live personalized crossword exists.
- After the receipt implementation, `uv run pytest -q` passed **538 tests** and skipped **3**. The focused attestation/review/evidence/reviewer-auth suites account for **112 passing tests**. Root Jest passed **11**, domain **129**, persistence **8**, React **125**, and application **8**. Typecheck, lint, Prettier, Ruff, and `git diff --check` passed. All receipt fixtures are synthetic.

### Generator solve-proxy and seeded-screen replay artifacts (27 September 2026)

- The sibling generator's `packages/construction/src/solveSimulation.ts` is a pure deterministic editorial proxy: it accepts clue familiarity, entry difficulty, letter-support estimates, crossings, and an optional accessibility threshold, then emits one greedy route plus stalled entries/components and circular-support diagnostics. Its own contract says those caller-provided scores are uncalibrated assumptions, not measurements or predictions of a player's behavior. It has no random seed, trajectory loop/count, simulator or policy identity/version, completion probability, nudge/reveal action log, publication decision, or evidence receipt. Reordering inputs is tested to preserve the same route.
- This does not satisfy `PuzzleV2SolveSimulationReceipt` in `packages/domain/src/publicationV2.ts`: that schema requires `simulatorId`/`simulatorVersion`, `policyId`/`policyVersion`, `seed`, at least 64 `trajectoryCount`, `completionRate`, `maxNonAnswerNudges`, `directAnswerReveals`, a `pass|fail|unresolved` decision, and `solve-simulation` evidence refs. The gate currently applies a Monday 90% completion/three-nudge threshold and zero reveal rule. The existing proxy provides no honest values for those metrics, so wrapping one route with `trajectoryCount: 64`, a derived rate, zero nudges/reveals, or `decision: pass` would fabricate a machine claim. The candidate also has no per-entry calibrated familiarity/retrieval/letter-support estimates or adapter that supplies them.
- `packages/construction/src/solveSimulationArtifact.ts` implements the safe intermediate step as a pure creator/verifier, with no UI or persistence integration. It normalizes and stores the full deterministic request and result, protocol/simulator IDs and versions, scope, candidate digest, implementation digest, an estimate-provenance digest, and canonical input/result digests. Verification replays the request and checks those digests against out-of-band expected bindings. It enforces fixed entry/crossing/text/serialization bounds, rejects invalid Unicode and non-ASCII answers, and has a golden digest vector. The Node-only module is exposed through the explicit `@crossword/construction/solve-simulation-artifact` subpath and is not exported from the browser-safe root barrel. This is a reproducible editorial artifact, not a publication receipt.
- The bindings establish equality to caller-supplied expected digests; they do not independently resolve the candidate, prove that the request was derived from that candidate, or verify that the implementation digest names the code actually executing. The estimate-provenance digest likewise binds an opaque value but does not resolve or validate its external provenance. A trusted adapter/build system must supply and validate those bindings before describing the artifact as candidate/build-bound. The request still contains caller estimates and labels them `caller-supplied-editorial-assumptions`.
- `packages/construction/src/solveTrajectories.ts` adds a distinct deterministic, uncalibrated screen over 64–256 trajectories, balanced across four familiarity strata and four navigation policies. The protocol pins the seeded PRNG and sorted draw order; each clue/topic latent draw stays fixed while only a changed crossing mask, prepared-hint stage, or explicit check can create a new evaluation. It logs synthetic threshold evaluations, hint/check/wrong-entry actions, openings, unresolved entries and unique grid cells, and stalled component sizes. Fully supplied patterns count as exposure. The topic-correlated stratum deliberately reuses one latent draw for every entry in a topic; that is a perfect-correlation stress scenario, not an empirical estimate. A `prepared-hint` route means a hint was seen, not that it was causally necessary.
- The screen accepts only supplied-entry geometry and editorial familiarity/difficulty/support assumptions. It checks crossings against those entries' positions and letters, but cannot prove that the request contains every candidate entry or matches the source candidate. The direct-reveal count records explicit simulator reveal actions, of which there are none; exact answer strings and sequences separated by punctuation/space are rejected in prepared hints, but semantic hint quality still needs human review. The simulator's fractions are scenario outputs, never estimates of player completion likelihood, learning, or publication readiness.
- `packages/construction/src/solveTrajectoryArtifact.ts` binds the exact request (including seed and interaction policy) and full replay output with canonical input/result SHA-256 digests and simulator/random-algorithm identities. Its verifier recomputes the screen and rejects changed requests, traces, policy or protocol fields. The Node-only API is exposed through `@crossword/construction/solve-trajectory-artifact`, not the browser-safe package barrel. As with the deterministic proxy artifact above, candidate, implementation and estimate-provenance digests are opaque equality pins: the artifact does not resolve the candidate, prove candidate completeness, establish that input estimates came from the named source, or verify that an implementation digest identifies the executing build. It is a local editorial diagnostic, not a `PuzzleV2SolveSimulationReceipt` or publication evidence.
- This does not complete the machine-evidence contract in `PuzzleV2SolveSimulationReceipt`. The protocol does not provide an independently validated `policyId`/`policyVersion`, candidate resolver, calibrated familiarity evidence, trusted build identity, or a publication decision. Do not promote these summaries into a receipt, use the synthetic fraction as a human completion probability, or set a machine claim to `pass`. No app route, construction job, or persistence layer runs or stores either simulation artifact. The host publication gate, machine-receipt status and publication state remain unchanged.
- Independent artifact audit found no canonicalization/replay defect (25 focused tests pass); it confirmed that candidate, implementation and provenance digests are only equality pins until trusted external resolvers validate them. Next, expose the screen to editors as a diagnostic in the local generator lab with candidate and estimate provenance visibly unresolved. Before any receipt use, add a trusted adapter that resolves the exact full candidate, estimate evidence and running build; separately validate the model against real player traces and review decision thresholds. Keep machine receipts and publication disabled until those sources, the policy identity, calibration basis, and evidence binding have passed review.
- Verification for the trajectory slice: full generator `npm test` passed **189 tests** across construction (**105**), generator (**10**), local-runtime (**25**), model-runtime (**18**), and lab (**31**); trajectory plus replay-artifact tests passed **41**. `npm run build`, `npm run lint`, and `npm run format:check` passed. No product runtime code, publication schema/gate, machine receipt, or publication state changed in this slice. The focused tests verify reproducibility and bounded diagnostic behavior only, not human difficulty or candidate/source truth.

The 64-item stimulus bank is a content foundation, not evidence that every item is offered adaptively. The opening currently uses an authored twelve-item subset with seeded position shuffling; later pools are authored too. It does not yet select a personalized sequence of successor spreads. Preserve this as an honest first version, and evaluate salience/skip behavior before adding stronger inference or more elaborate symbols. A model output should open several plausible paths; the user’s response and subsequent play supply the evidence.

### Confirmed defects and narrowly scoped review risks

“Reproduced” below means an isolated temporary database or an actual model run, not production user data. The evidence-state defects R3–R4 were the highest-priority fixes and now have regressions. The table records each original trigger, its correction and any remaining release risk; completed rows should not be reassigned as new work.

| ID | Finding and trigger | Evidence / current consequence | Required correction and acceptance |
| --- | --- | --- | --- |
| R1 | Grid cancellation and finalization are not atomic. `future_grid_jobs.py`, `_claim_next_job`, `process_next_grid_draft`. | **Fixed and regression-tested:** cancel-before-claim and cancel-before-finalize are serialized through conditional SQL updates; expired cancelled leases become terminal, and stale leases cannot publish. Worker regression suite passed 31 tests. | Retain state/lease/cancel predicates in each write and keep interleaving tests when integrating publication. |
| R2 | Worker shutdown and idempotent create were incomplete. `construction_runtime.py`, `future_worker.py`, `future_grid_jobs.py:create_grid_draft_job`. | **Fixed with focused tests:** POSIX child process groups are terminated/reaped; shutdown requeues an unfinished job; idempotency hashes immutable client intent and exact retries return the original job after profile edits. A process-group descendant test passed. Full worker-executable SIGTERM, Windows descendant cleanup and SIGKILL recovery remain unverified; lease fencing handles stale completion. | Keep graceful cleanup and immutable intent behavior. Verify actual worker shutdown on supported platforms before release. |
| R3 | Pending calibration-response/action receipts can become unrecoverable after their source changes. `calibration_hypothesis_api.py` response/action reservation and source guards. | **Reproduced, fixed and regression-tested:** exact retries reconcile their existing reservation after source expiry/supersession, while new stale responses remain rejected; stable reducer IDs preserve one evidence contribution and the undo path. Covered by the full Python suite (**394 passed, 3 skipped**); the focused hypothesis API suite passed **36 tests** at the earlier checkpoint. | Preserve exact-request identity and reservation reconciliation; keep failure-injection and source-change regressions. |
| R4 | Reflection actions reserve an ID before shared validation and trust client chronology. `reflection_api.py:_action_body`, `post_reflection_action`; contrast the host-authored calibration-action sequence. | **Reproduced, fixed and regression-tested:** validation precedes reservation, and host-authored ordering/legal transitions prevent client-supplied future or backdated timestamps from dominating. Covered by the full Python suite. | Preserve host ordering and validate legal action transitions before durable reservation. |
| R5 | A transient profile CAS loss is surfaced as a terminal journal conflict. `session_journal.py:_record_final_analysis` and `apps/react/src/future/sessionJournal.js` 409 handling. | **Injected conflict reproduced, fixed and regression-tested:** retryable profile revision races retain the active session and can complete through bounded client retry; genuine event/sequence conflicts stay terminal. Duplicate finish remains idempotent. React session-journal regressions (17 tests), typecheck, and the full Python suite pass. | Preserve the distinction between retryable profile conflicts and terminal event conflicts; verify browser recovery in the end-to-end journey. |
| R6 | Export consistency and size handling. `profile_export.py:_export_profile`, `export_profile`. | **Reproduced and fixed:** an isolated second SQLite connection previously yielded starting-profile epoch 1 plus episteme epoch 2. The route now opens one explicit SQLite transaction before reading; a writer-interleaving regression passes. The 80 MiB response cap supports the 64 MiB episteme ceiling and a 9 MiB profile export. Data and JSON are still materialized before the cap check, so memory is not bounded by that cap. No import/roundtrip exists. | Replace materialize-then-check with bounded streaming/chunks or a bounded export job before supporting long histories. Keep one coherent snapshot, integrity manifest and explicit absence of client-unsynced events. Retention/deletion remain separate deliverables. |
| R7 | Export provenance and capability redaction. `profile_export.py:_without_capability_fields`, `_safe_generation_metadata`. | **Fixed and regression-tested:** source, profile, request, deck and model-weight digests are retained. Writer/lease capability columns are not serialized; credential-like token fields are removed by an exact allowlist. Shared puzzle manifests remain referenced by ID/hash only. | Preserve this exact distinction in future fields and test every newly exported credential. Do not recursively remove fields merely because their names contain “digest.” |
| R8 | The OEWN review projection accepted broken source references. `oewn_candidates.py:_validate_staged`, `project_candidates`. | **Reproduced and fixed in the projection path:** staged lexemes/forms/senses/counts/quarantine references are now validated against each other and the pinned source identity/hash. An executable bounded command re-imports the pinned archive, requires a separate real human source-terms attestation, and atomically writes only a fill-only review queue. Synthetic regressions cover dangling and wrong-source references. No full production review queue or attestation has been created. | Use the command only after a human has actually reviewed the pinned source terms. Keep source admission, semantic review, sense/fact support and clue eligibility as separate gates. |
| R9 | Native source provenance could change during a run. Generator `packages/local-runtime/src/runtime.ts:generateFullSizeDraft`. | **Fixed and regression-tested:** source digest is rechecked after build and fill; changed inputs discard the draft. Runtime/Node/Cargo/Rust versions are recorded separately, with `admittedPack: null` until an approved corpus is wired in. Local-runtime tests passed 18; TypeScript build passed. | Preserve digest fencing and report admitted-pack identity only after a real pack is integrated. |

The session-finish transaction itself was reviewed: pending session/event/analysis ORM writes and the episteme update share the session commit, so the review did **not** establish a partial-commit defect there. Preserve that atomicity while addressing R5. Do not replace it with independent commits merely to simplify retries.

### Strict admitted-pack loading added after review

`src/crossword/admitted_pack_loader.py` provides byte and file entry points that require an exact out-of-band pack ID/digest and complete source pins. It enforces the 64 MiB limit before parsing, strict UTF-8/JSON, duplicate-key rejection at every level, and rejects NaN/Infinity before passing data to `resolve_admitted_pack`. The paired synthetic loader/resolver suite passed **23 tests** in the prior review; the current durable retrieval/job bridge now invokes the pinned loader/configuration path and builds an immutable validated content projection. No source-term attestation or production pack exists, so this invocation and the answer-grid path remain synthetic-tested.

### What the live Qwen smoke changed

The in-flight single-model smoke completed during review. Exact artifact: `qwen3.8:27b`, reported 27.3B, `Q4_K_M`, digest `sha256:22130167c4c20e20c7b71454612966ca8e8171e9b3cc8ab6ce8aa6cbfec79643`. Seed 20260926, temperature 0, 512-token cap; the request also set `think:false`. Fixture hash: `57c061ef0e41a29ea8dbe068d0c1d9f1e42d51eca5f26e509f2fc71c8a20c0fc`. Full synthetic report: `/tmp/crossword-model-eval/qwen-27b-20260926.smoke.json` (temporary local artifact; preserve it intentionally before cleanup).

| Task | Observed wall time | Review result |
| --- | --- | --- |
| Three tentative associations | 84.2 s, including 15.2 s model load | Valid output shape; several alternatives were supplied. Prose was long and abstract for the proposed UI. No player-resonance or calibration-quality measurement. |
| Four themed answers, 7–14 letters | 65.6 s | Shape check passed, but `LOOKUP`, `SPOTIT`, and `GLANCE` have six letters. Only `EYEBALL` meets the requested length. The prose describes a topic; it does not demonstrate a consistent wordplay mechanism. |
| Clue for `ARE` | 4.7 s | Returned “They ___ here”. A plausible single smoke output, not a clue-family benchmark. |
| Spanish clues for `CASA`, `GATO`, `LLUVIA` | 22.7 s | Shape and answer set passed; every clue was in English despite the explicit Spanish requirement. |

Consequences for E05/E06/E10:

- Keep separate result fields for schema validity, deterministic task constraints, grounded content, editorial quality and runtime. A green JSON shape check must never be presented as “the task passed.” Add exact lengths/counts/answer sets/source-ID checks; evaluate language and semantic fairness with suitable independent review rather than claiming a superficial detector proves them.
- The actual product hypothesis request uses `/api/chat`, a different prompt/schema, up to 900 output tokens and a 45-second read timeout. Two isolated Qwen requests returned 503 at 45,027.0 ms and 45,026.7 ms. The first Gemma request returned generic 503 after 32,490.8 ms; a follow-up diagnostic found that an identity-check patch expected a prefixed digest while Ollama returns bare lowercase hex. The gate was corrected to normalize that exact digest. A final real Gemma route request then returned **HTTP 201 in 8,587.7 ms**, persisted a complete deck with one association item and profile revision 1, and verified the exact digest before and after. Artifact: `/tmp/crossword-model-eval/product-hypothesis-route-gemma-final-20260926.json`. This is one successful local route smoke, not a reliability or quality benchmark; Qwen's two timeouts remain real failures.
- The product model identity path now checks the exact normalized pre/post tag digest and exact returned model; focused mocked regressions pass (33 tests). The local default is Gemma 4 26B for route operability, while `CROSSWORD_HYPOTHESIS_MODEL` and `CROSSWORD_PROFILE_MODEL` remain explicit overrides. This is not a model-quality decision. Record runtime/context/thinking settings and failure/truncation status in persisted receipts, not only in source code. The current report's RSS delta is the Node client, not model/GPU memory.
- **Completed with the owner's prior authorization:** `gemma4:26b` was pulled and verified as 25.2B, `Q4_K_M`, digest `sha256:08ae7ec1744bd7f451c4a530afb39d2673ad9d07a8369b8a33a3613b41212a68`. The paired holdout also verified Qwen `qwen3.8:27b`, 27.3B, `Q4_K_M`, digest `sha256:22130167c4c20e20c7b71454612966ca8e8171e9b3cc8ab6ce8aa6cbfec79643`. Do not silently substitute another model tag. The benchmark used Ollama's default context (not explicitly pinned); retain this as a limitation.
- The four original prompts remain Qwen smoke fixtures, not a model decision. Keep failed outputs and report the denominator; never tune the fixture away or relabel the English clues as success.

### Paired `holdout-v1` run (26 September 2026)

The separately authored fixture set was run serially through the existing paired harness with seed `20260926`, temperature `0`, a 512-token cap, thinking disabled, JSON output, and Ollama's default (un-pinned) context. Each installed tag and digest was checked before and after its model run; every response's returned model name was checked. Across four tasks per model, both were schema-valid on all four. The deterministic task gate passed Qwen on 2/4 and Gemma on 4/4:

| Task | Qwen 3.8 27B | Gemma 4 26B | Limit of this result |
| --- | --- | --- | --- |
| Three tentative associations | Pass, 104.7 s | Pass, 16.7 s | Shape/constraint checks only; no human resonance or calibration measurement. |
| Four themed answers | Fail: two answers under 7 letters, 50.7 s | Pass hard checks, 5.2 s | The checker does not determine whether the four answers share one coherent wordplay mechanism; the Gemma rationale needs editorial review. |
| Clue for `WAS` | Pass, 5.4 s | Pass, 0.7 s | One clue per model; no fairness or clue-family evaluation. |
| Spanish clues for `CASA`, `PERRO`, `AGUA` | Fail: `PERRO` and `AGUA` lacked deterministic Spanish-language cues, 23.7 s | Pass deterministic cues, 2.4 s | The heuristic is not a native-speaker language or clue review. |

The measured totals were 184.5 s for Qwen and 25.0 s for Gemma on this run; generation lengths and initial model load differed, and the context limit was not explicitly pinned, so this is not a controlled general latency result. Blind human ratings remain pending. The run is not a model-quality winner and provides no evidence of improved player outcomes. Preserve the blind key separately from the response/ratings artifacts:

- `/tmp/crossword-model-eval/qwen-gemma-20260926/holdout-v1.full.json`
- `docs/evidence/model-evaluation-holdout-v1.structural.json` (digest-bound structural projection; generated without rerunning a model)
- `/tmp/crossword-model-eval/qwen-gemma-20260926/holdout-v1.blind.json`
- `/tmp/crossword-model-eval/qwen-gemma-20260926/holdout-v1.ratings-template.json` (blank rating fields; the separate evaluation summary records human ratings as pending)
- `/tmp/crossword-model-eval/qwen-gemma-20260926/holdout-v1.blind-key.json` (keep separate)

The existing Qwen-only smoke artifact remains `/tmp/crossword-model-eval/qwen-27b-20260926.smoke.json`; its task audit is a separate file. The actual Flask product-hypothesis route has separate Qwen, Gemma and direct-diagnostic artifacts because its `/api/chat` prompt/schema differs from this lab harness.

### Current exact-tag live smoke (28 September 2026)

`scripts/live-model-holdout.py` replays the four frozen holdout prompts against
the exact loopback tags currently installed, serially, with JSON mode, thinking
disabled, seed `20260928`, and a 768-token cap. The digest-bound receipt is
`docs/evidence/live-model-smoke-holdout-v1.20260928.json`. Both Qwen 3.8 27B
and Gemma 4 26B completed all four prompts with valid JSON and valid shallow
shape gates. Qwen's total wall time was 174.603 seconds; Gemma's was 25.320
seconds. The artifact retains the exact tag digests and provider counters.
Those gates check response shape only; semantic coherence, clue fairness,
language accuracy, source grounding, and player resonance remain pending, and
the report declares no winner.

### Current-source personalized durable smoke (28 September 2026)

The current source tree was launched with `make run-personal` prerequisites,
the runtime doctor and production React build both passed, and a disposable
profile was created through the real Flask API. A durable Wednesday request
using the exact `gemma4:26b` tag and seed `137` traversed
`theme-proposal` → `native-xfill` → `clue-generation` → `ready` in 186.577
seconds. The returned original board is 15×15 with 78 entries and theme forms
`WEAVE`, `STITCH`, `RESONANCE`, and `ECHO`; it is playable and includes the
full puzzle manifest, personalization receipt, fill-quality receipt, clue
diagnostics, construction topology receipt, and semantic-challenge receipt.
The selected fill attempt had mean score 80.69, minimum 55, zero iffy
entries, and 15 footholds; deterministic clue checks found zero issues. This
is a local runtime receipt, not a claim of semantic truth, human fairness, or
player-quality acceptance: xfill scores remain heuristic, the reviewed clue
pack was not configured, and the profile/database were disposable. The
digest-bound evidence is
`docs/evidence/private-current-source-live-smoke-v1.20260928.json`.

A newer current-source same-origin smoke on 28 September 2026 exercised the
same profile → durable-job → local worker path with Gemma 4 26B and a German
language preference. It reached `ready` after `theme-proposal` → `native-xfill`
→ `clue-generation`, returned a playable 15×15 board with 78 entries in
203.475 seconds, and reported zero deterministic clue issues. The current
provenance contained 15 abbreviation markers and one explicit language marker;
the temporary profile was deleted after the run. The digest-bound receipt is
`docs/evidence/private-current-source-live-smoke-v2.20260928.json`.

The clue-quality panel now surfaces the resulting `private-foothold-seed-plan-v1`
summary beside structural crossing diagnostics. The selector prefers a
non-foothold neighbor with fewer deterministic clue-risk flags when that
evidence exists. It names only weak-entry IDs, neighbor IDs, and crossing
coordinates; answer text, clue text, and player ability remain outside the
receipt. The focused construction slice passes four Python tests, the
private-generation slice passes 94, and the focused React clue-quality slice
passes seven.

The same structural plan is now supplied to the clue-writing prompt before
clues are generated, asking the model to make candidate support clues more
transparent while preserving the no-answer-giveaway policy; the final receipt
is recomputed after clue diagnostics so risk-aware selection remains visible.

Applying the receipt to the completed Gemma board above yields 15 structural
seed candidates for all 15 weak entries; the derived, board-digest-bound
projection is
`docs/evidence/private-foothold-seed-plan-smoke-v1.20260928.json`.

The private clue witness layer also checks quoted hidden-word relations through
a literal contiguous-substring comparison; mismatches fall back to an
answer-free scaffold and remain explicitly `semanticStatus=not-established`.
The focused grounding/private-generation command passes 104 Python tests.

### Next implementation run: make the private game feel better

Do not restart a publication review, license audit, or curator worksheet. The private play loop is now implemented and exercised. Continue with the player's experience and concrete model/runtime problems:

1. **Inspect and improve actual generated boards.** The first real browser run produced a 78-entry Wednesday puzzle (SCENE / STAGED / ACT / PROPS); later runs produced 70–76 entries and TUNING / STITCH / RESONANCE / PATTERN from the thread/fork/echo/moss opening. The Thursday repair-pass run produced 74 entries in 85.398 seconds with STITCH / RESONANCE / PATTERN / TUNING. The private route now catches false anagrams, reversals, answer giveaways, common-language translation mismatches, answer-shape facts, convention surfaces, and crossing fallback status; `clueQuality.grounding` marks every semantic meaning as unverified. Theme planning now permits a small minority of proper-name or culturally specific answers when the word-field invites them and the grid can provide fair crossings, while weak non-theme factual surfaces still fall back to answer-free scaffolds. This remains diagnostic and private: plausible source-less factual clues such as `ISART` / “French Alpine river” and `LEO` / “Zodiac lion” still need reviewed sources or safe replacement. The next pass should improve grounded clue choices and distinguish valid obscure facts from model invention rather than treating deterministic metadata as semantic review. Preserve recognizable crossword clue grammar: answer/clue part of speech, tense, number, quote/bracket/abbreviation conventions, wordplay signals, and crossing footholds for unfamiliar entries; `/future` now exposes those signals as renderer-only hover annotations while `/` remains unchanged. Do not make a source-attestation gate for private use.
2. **Make the wait understandable and shorten it where possible.** The latest Wednesday request took 70.553 seconds (theme proposal 6.500s, native xfill 11.865s, clue generation 51.927s); a Thursday request took about 86 seconds. The durable private job now exposes queued/running/ready/failed/cancelled states, honest preparation copy, idempotent retries, and a stop-waiting action. The worker preserves monotonic `provenance.timingsSeconds`, including xfill retries and total time; `fillQuality` reports entry count, score floor, iffy/weak counts, foothold count, and the bounded retry-selection receipt; `clueQuality` reports only mechanically detectable clue issues. A minute or two is acceptable for local play, so the next improvement should be semantic clue grounding and stage-level observability rather than speculative token shaving. Do not display fabricated progress.
3. **Let the episteme affect the game, then learn from play.** The generator now receives opening associations, saved language preference, active preference tensions, an explicit bounded avoid-topic list, and a bounded list of answer forms exposed in finished private sessions; those forms are explicitly unreviewed and do not become mastery claims. When at least two fresh model theme candidates exist, exact recently exposed forms are filtered from the next theme set; deliberate review remains possible when the word-field calls for it. Clue prompting now labels a selected learning language explicitly and keeps most of the board in clear English, with the chosen language recorded in provenance. Finished sessions now choose authored reflection variants from exact manifest signals (wordplay, language, longer/less familiar entries, and challenge) and link them to the related entry IDs; sessions without a manifest retain the generic authored deck. Delayed language-review responses now steer the next brief toward pending/not-yet or assisted forms and allow recently remembered forms to cool, while keeping the no-mastery boundary. Recent finished-session task links now also carry a literal `surfaceFamily`; the next brief receives a capped `private-clue-family-fatigue-v1` count as a reversible rotation hint, with explicit clue-family targets taking precedence and no family being suppressed. Continue using keep/turn-away/pass responses to choose the next themes and clue balance. Keep profile text inspectable and revisable; do not infer a fixed personality or claim learning from exposure alone. The bounded local reflection mirror now supplies optional first-person wording while preserving authored mappings and fail-open behavior; its receipt is visible in the postgame UI. Semantic content grounding, human exposure-fatigue evaluation, and fitted recall scheduling remain future work.
4. **Keep `/` and solving behavior stable.** Retain regression coverage for the normal daily route, highlighting, keyboard, check/reveal, and completion. The private route should continue through the same solver controller and recover board plus progress after reload.
5. **Leave public sharing as a separate future goal.** Source, attribution, editorial and publication safeguards matter when puzzles are shared. None belongs in front of local private play.

Current verification: the latest focused private-generation slice passes **132** Python tests; the clue-grammar bridge slice passes **26** domain tests; CI-scoped Vitest passes **401** tests across 53 files; the new local review-bundle slice passes **3** tests. The broader application gate `make test` completed with **854** Python tests selected (three live-provider tests deselected), plus the JavaScript workspace suites. The broader historical `make test` totals remain recorded below where applicable; the current runtime doctor is green and the latest real Tuesday Gemma receipt remains answer-free. This continuation adds the private clue-safety guard, uncertainty-labeled clue-family observations, collapsed clue-quality notes with reversible player flags, the full assistance ladder (crossing, letter, and entry reveal) with solve-journal events, answer-free contextual convention hints for punctuation, number, abbreviations, language labels, and fill blanks, a first-time private language starter lane with no-exposure/no-mastery semantics, explicit language-signal repair before session linking, explicit Monday/Wednesday/Thursday recipe directions with provenance, a validated Thursday shared-affix mechanic with a safe fallback, a bounded solve-behavior difficulty calibration signal, a calm three/six/twelve-item recall budget, an optional local-fill candidate lane for due language forms with explicit used/unplaced provenance, scheduler-owned due-first candidate ordering without hard locks, structural crossing-access provenance with explicit player-support uncertainty, contiguous-streak recall scheduling with bounded later-streak interval extension, the focused `private-construction-evidence-v1` topology receipt plus the invoked lab-only sibling adapter with caller-attested estimate provenance, the `private-grounded-clue-bundle-v1` and `private-clue-grammar-bridge-v1` provenance contracts, deterministic due-language candidate weighting plus scheduler-history priority, future-only token-aware rebus metadata, canonical SHA-256 profile-archive integrity receipts, preflighted bounded profile export, the advisory runtime-readiness endpoint with privacy-preserving worker heartbeat, the read-only runtime doctor, the `make run-personal` launcher, guided calibration branch recovery, the digest-bound structural Qwen/Gemma evaluation snapshot with no-winner status, an original 200-case `clue-grammar-v1` fixture matrix (10 accepted and 10 rejected examples for each of 10 families), `private-fill-quality-policy-v1` bounded retry selection with a bounded two-theme retention floor, `private-clue-semantic-challenger-v1`, the opt-in `private-clue-model-challenge-v1` fail-open advisory pass, `future-token-producer-v1`, six explicit accented language input packs, a 22-pair synthetic delayed-review fixture across seven learning languages, bounded reviewed-pack sense/fact context for uncovered model clues, a corrected 0.1.2 runtime-archive lock/integrity check, and truthful `not-configured` handling for an absent optional reviewed pack. `make runtime-doctor` is green on the current machine, `npm ci --ignore-scripts --dry-run` accepts the lockfile, and a real durable Wednesday run produced a playable 15×15/76-entry Gemma board in 168 seconds with measured fill, zero deterministic clue issues, and preserved stage transitions. The durable private worker now preserves the frozen profile ID when rebuilding its starting context, so queued puzzles can resolve scheduler-owned due language forms just like the synchronous path. When a new board replaces a finished one, `/future` now clears the prior reflection and association state at the session boundary so postgame cards cannot bleed into the next puzzle.

The constellation panel now exposes editable next-crossword difficulty and learning-thread settings while a game is open; saving them updates the profile for the next generated board without restarting calibration or mutating the current board. The same panel now reads a bounded answer-free history projection from the host, showing saved titles, weekday/model provenance, and replay analysis counts without exposing puzzle answers.

The history panel now also offers a `private-play-calibration-export-v1`
download. It is intentionally narrower than the profile archive: it contains
bounded session metadata, aggregate replay analysis, and the observational
calibration report, while omitting titles, answers, clues, grids, raw solve
events, profile prose, and model prompt material. The artifact declares its
redactions and is suitable for local tuning or later evaluation without
silently becoming a research export or a mastery claim. Its canonical SHA-256
receipt makes the trace independently checkable after download.

The `make run` and `make run-personal` launchers now enable the existing local
clue challenger by default, with `CROSSWORD_PRIVATE_CLUE_CHALLENGE=0` as an
explicit opt-out. On full boards the pass is bounded to deterministic risk,
foothold, and mechanical-warning entries; small fixtures remain exhaustive.
The normal local path therefore records a second-pass
keep/fallback/review recommendation where it is most useful while preserving
the same fail-open policy: the challenger can inform provenance and player
flags, but cannot gate play or establish semantic truth.

Explicit clue-surface flags now travel through a strict allowlist into the next private generation brief as reversible clue-family targets; clearing a flag removes that steering signal without changing the finished board.

The current full Vitest suite passes **401** tests across 53 files, with the legacy Jest and Playwright suites remaining on their existing runners. The latest private-generation slice passes **132** Python tests, the private provenance/review route slice passes **3** tests, and the shared clue-grammar focus passes **26** TypeScript tests, including exact multiword answer-surface rejection. `npm run typecheck`, ESLint, Prettier, and `git diff --check` pass. The model-free reviewed-sample slice adds two backend contract tests and two browser recovery tests: the endpoint registers a hand-authored CC0 word square through the immutable manifest registry, and `/future` offers it when the local model is unavailable while preserving the same solver journal and reload shelf. The sample is explicitly marked `reviewed-authored`, `not personalized`, and `semanticStatus=authored-sample`; it does not enter the episteme or domain lexicon. The reflection endpoint now also returns an answer-free `private-session-analysis-summary-v1` trace for every finished private game, and the `/future` postgame view presents independent, crossing-supported, assisted, wrong-turn, and untouched counts without turning them into a mastery or preference verdict. Durable private-job polling now includes measured elapsed seconds for the current worker stage, and the control bar displays that timing beside the honest stage copy without fabricating completion percentages. The private clue guard now detects plural/past marker mismatches, exact answer roots/inflections, exact multiword surfaces, and dead-end generic templates, then falls back to an answer-free crossing scaffold. The optional `private-reviewed-clue-pack-v1` path preserves exact matched reviewed clue text plus compact pack/source/evidence receipts, and the collapsed clue-quality panel tells the player how many surfaces came from that pack. No pack keeps the normal local-model path. The uncertainty remains visible in `clueQuality` rather than becoming a semantic truth claim. The fresh real Tuesday receipt is `docs/evidence/private-tuesday-clue-quality-study-v3.real-gemma4-26b-20260928.json`: 74 entries, 36 signalled surfaces (48.6%) across six non-definition families, four answer-free fallbacks, and zero deterministic grammar issues in 241.651 seconds. The current runtime-compatible Tuesday policy uses a 24-surface/five-family floor and a 48% full-board target for non-definition surfaces; the repair path now records the observed/target rate, and `/future` surfaces that receipt in the clue-quality panel without calling it semantic quality or player difficulty. A fresh post-change Gemma receipt now also covers a 36-entry Tuesday repair batch and meets the floor at 44/76 signalled surfaces. Native theme submissions remain capped at four locks while preserving the model proposal for anchor selection. The remaining product work is semantic fact/sense grounding, reviewed language/input coverage, trusted simulator estimate provenance and playtest calibration, broader Thursday mechanic cohorts and human fairness review, human evaluation of fill-acceptance thresholds beyond the deterministic retry policy, and broader evaluation rather than the ability to wait for a puzzle. The clue-quality evaluator has four focused Python tests and the real Tuesday report is answer-free and digest-bound.

The local model runtime now carries an explicit `private-model-runtime-policy-v1`
receipt. Gemma keeps the full Tuesday repair budget; Qwen 3.8 27B uses shorter
stage timeouts and at most one Tuesday follow-up batch, while deterministic
clue safety still runs after every model response. This bounds a slow optional
repair/challenger path without turning a model timeout into a puzzle failure or
making any model-quality claim. The receipt is attached to generated
provenance so a later latency study can distinguish model execution time from
construction and clue-quality outcomes.

An explicit `gentle-stretch` play-calibration recommendation now changes
Tuesday's construction target instead of only changing prompt wording: it asks
for at least 28 visible non-definition surfaces and a 56% target, with the
variant recorded in the weekday recipe receipt. The ordinary Tuesday recipe,
other weekdays, and the no-history path remain unchanged. This makes a player's
`harder-stretch` pulse causally visible in the next board while keeping the
signal reversible and difficulty-only.

A real Qwen 3.8 27B Tuesday request now confirms the bounded failure behavior:
seed `20470403` returned a playable 76-entry board in 201.32 seconds. Theme
proposal and native xfill completed; the primary clue call reached its
120-second Qwen budget and the board used answer-free crossing scaffolds rather
than hanging or exposing an unverified clue. The answer-free receipt is
`docs/evidence/private-tuesday-qwen-runtime-smoke-v1.20260928.json`. It is
runtime evidence only and does not claim clue quality, fairness, or player
support; the zero-surface-diversity result is retained as the next Qwen clue
optimization target.

The follow-up `private-qwen-clue-batching-v1` slice now bounds large Qwen clue
requests to 24-entry light-schema batches (1,400 output tokens maximum per
batch) and records attempted, completed, or failed batch status in provenance.
The host still applies the exact entry-id, length, answer-leakage, morphology,
and clue-family guards after a successful batch; optional model repair and
challenger passes are skipped only for a batched writer because they would
duplicate the same slow decode. A failed batch never contributes partial text:
the whole board falls back to the answer-free crossing scaffold. On this host,
the first 24-entry Qwen batch still reached its 60-second timeout on full
74–76-entry Tuesday boards, so long Qwen generation remains a documented
runtime limitation rather than a quality success. A small eight-entry probe
returned structured clues, but took roughly 95 seconds including the bounded
post-processing path; that result is useful for profiling only and does not
establish semantic or editorial quality. Gemma remains the practical default
for complete local boards while this Qwen path is optimized further.
The batching slice's focused Python suite passes **140** tests, including
exact-batch composition and failed-batch provenance coverage.

The latest replay-boundary slice adds **2** Python provenance tests and **2** React receipt tests. The focused Python command covering postgame associations, provenance, fill-study evaluation, and private generation passes **104 tests**; the focused React solver/app/reflection/history/receipt command passes **23 tests**. The receipt is owner-scoped, canonical-digest checked, and fail-open when storage is absent. A browser gate initially found that the durable response body was being consumed twice, which prevented a ready job from reaching the solver; the client now reuses the already parsed `202` payload, and `CROSSWORD_E2E_BACKEND_PORT=5015 npm run test:e2e` passes all **6** tests through calibration, worker polling, private play, reflection, reload, and the unchanged daily routes.

The E12 narrative lifecycle slice adds one Python API regression and one React
panel regression: a field note is marked stale after an episteme revision and
its suggestion cannot be accepted until a fresh note is written. The focused
narrative API suite passes **7 tests**, and the focused panel suite passes **3**.

The durable browser job now has a profile-scoped pending record while it is
queued or running. A reloaded `/future` view reattaches to the same job and
continues stage polling; a ready board still uses the existing replacement
confirmation before touching current letters. Cancellation, terminal failure,
and successful application clear the record. The controls slice now covers 25
tests, including helper validation and reload recovery.

The optional postgame association lane now normalizes the local runtime's
offline/network-denial failure to its documented `unavailable` response rather
than leaking an HTTP 500. The browser journey still keeps the completed game,
reflection cards, and receipt available when association generation is absent.

The authored reflection bank now contains 60 cards across the existing wordplay, discovery, and challenge categories; each game still freezes three cards, and the 58-test focused Python run covers both generation and the reflection contract. Existing decks remain immutable because selection is frozen at deck creation.

### Evidence returned by the 26 September implementation pass

- Product Python full suite after v4 receipt validation: `uv run --no-sync python -m pytest -q` — **362 passed, 3 skipped**, with one existing `datetime.utcnow()` deprecation warning. `tests/test_future_grid_jobs.py` passed **22 tests**.
- Product JavaScript: root Jest **2 suites / 11 tests**, typecheck, ESLint, Prettier, and app build passed. Playwright: `CROSSWORD_E2E_BACKEND_PORT=5014 npm run test:e2e` — **6 passed**. Port 5002 was occupied, so the run used 5014; these tests use synthetic puzzles and do not cover original personalized-puzzle publication/solve.
- Generator: `npm test` passed **116 tests** across its workspaces (construction 32, generator 10, local-runtime 25, model-runtime 18, lab 31); `npm run build`, ESLint and Prettier passed. The product durable-job/API/pack/runtime-bridge tests are included in the Python total. These synthetic fixtures validate the profile-aware answer-grid path; no production pack is admitted and no native xfill run with a human-attested pack or playable original puzzle was produced. Product and generator repo-map checks passed.
- Product-route smoke: Gemma `HTTP 201 / 8,587.7 ms`; Qwen `HTTP 503 / 45,027.0 ms` and `HTTP 503 / 45,026.7 ms`. The model identity regressions and default/override tests pass: `uv run --no-sync python -m pytest -q tests/test_calibration_hypothesis_api.py` — **36 passed**. The final Gemma artifact is `/tmp/crossword-model-eval/product-hypothesis-route-gemma-final-20260926.json` (owner-only local output). The paired blind key remains separate at `/tmp/crossword-model-eval/qwen-gemma-20260926/holdout-v1.blind-key.json`.
- Host launcher smoke used `CROSSWORD_DATABASE_URI=sqlite:// uv run --no-sync python run.py` on loopback. It is Werkzeug development-only; this is not deployment-server validation.

### Archived V2 candidate integration continuation, 26 September

- The strict `PuzzleDocumentV2` contract, public-copy redaction helper, and host builder now operate together. The builder derives 15×15 topology and binds each entry to exact admitted source, sense/fact, clue, and frozen profile-evidence IDs; it returns an immutable `quality.verdict=review` candidate and a separate private sidecar. TypeScript now rejects impossible calendar dates (for example `2026-02-30`), and the Python builder rejects extra/malformed nested receipt fields so it cannot emit a candidate that the TypeScript validator rejects. The synthetic golden fixture still verifies SHA-256 parity at `1e-7`; structural letter agreement records zero solve-support score/confidence and unknown uncertainty.
- The personalized worker now invokes the builder when every slot has an exact admitted clue join. It stores candidate JSON in `future_puzzle_v2_candidates`, separate from the V1 manifest registry, and serves it through `GET /api/future/puzzle-candidates/v2/:sha256?profileId=...` after strict shape and digest revalidation. Candidate, private selection sidecar, and ready job are staged in the same lease/cancel-fenced transaction; storage rejection falls back to a ready answer grid without the candidate or sidecar. Public job JSON omits the compiled brief and its raw profile evidence IDs; the read-only profile export includes the matching private sidecar only for its owning profile. V1 solve-session creation still rejects the V2 candidate.
- Verification on this continuation: product Python **394 passed, 3 skipped**, with one existing SQLAlchemy datetime deprecation warning. Focused candidate API, grid-job, and session-journal tests passed (**43**); focused profile API/export tests passed (**30**). Domain TypeScript tests passed (**114**), persistence tests (**8**), application tests (**8**), React tests (**117**), and root Jest tests (**11**). Typecheck, ESLint, Prettier, and `make build` passed; `py_compile` passed. Ruff is not installed in the environment. Repo-map regeneration/freshness and final `git diff --check` remain to run after this documentation update.
- This is a stored review artifact, not publication or solver support. All integrated candidate tests use synthetic records; no source terms have been attested, no production pack exists, and no human has reviewed a real candidate. V2 session/replay, explicit publication, semantic clue/fact review, weekday/fairness gates, and `/future` handoff remain unimplemented. The `/future` solver still opens the daily collection, and `/` remains unchanged.

This is the historical profile-aware answer-grid checkpoint from 26 September, before the private-play path above was implemented. Its generated job result was an answer-grid draft with `playable:false`; it is not the status of the current `/future` route.

### Archived 26 September acceptance note (superseded)

- Use a temporary database and the real local Ollama/xfill route in a browser. Show that `/future` does not request a daily puzzle, can create a profile-seeded original grid, and can enter letters, check/reveal, finish, and save the solve session/reflection. Confirm `/` still behaves as the daily solver.
- Report the actual model tag, generation time, grid/entry count, themed answers, and any failure or malformed clue. Keep the “experimental/local model” label visible; do not claim measured learning or general clue quality.
- Keep the setup command simple: `make run` defaults `CROSSWORD_XFILL_ROOT` to the sibling native engine, starts the private-generation worker beside Flask, and cleans it up with the server; Ollama must already be running with Gemma 4 26B or Qwen 3.8 27B installed. A separately managed worker is unnecessary for the normal private path.
- Run the focused Python and React tests plus app typecheck/lint/format/build after any edits. List only real remaining blockers to playing a puzzle.

The separate future publication lane still needs exact source/license evidence, semantic/clue evaluation and required human receipts before a puzzle can be shared or presented as vetted. Those conditions are intentionally not part of private play.

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

The owner has already authorized the local Ollama/native architecture, nonverbal setup direction and weekday/convention priorities. The active React `/future` route now has a five-movement calibration journal with a 64-item bank, explicit setup, separate raw/local/host persistence, an optional source-bound proposal review loop, and guided recovery for incompatible local/host branches. The next calibration work is selector-bias and skip-comparison evaluation, repeated-deck fatigue, and lexicon grounding, not a new onboarding shell. Trusted solve replay, a usable profile-to-content brief, reviewed content, original-puzzle runtime integration, and day-specific quality proof remain necessary. Public release and empirical learning claims still require their stated evidence. Numerical settings are versioned initial defaults to validate and improve.

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
