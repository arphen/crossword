# The `/future` opening

`/future` and `/future/` serve the existing React application with a separate,
lazy-loaded onboarding experience. `/` remains the daily solver. Build with
`make react-assets`; the normal Flask server serves both routes on port 5001.

## The current experience

The opening has six screens. Five record calibration movements; the final
screen previews the provisional word field before entering the crossword.

1. **Encounter:** choose among twelve mixed objects, drawn forms, surfaces,
   numerals, and marks. The first spread supports color/form, monochrome, and
   words-only presentation.
2. **Relation:** keep the first sign visible and choose a companion from the
   available spread.
3. **Variation:** keep the chosen sign or choose one of eight color variations.
4. **Traces:** keep up to two words, numbers, or typographic marks.
5. **Setup:** choose any Monday–Sunday difficulty and optionally name a language
   to carry into future puzzles. A small expandable note introduces clue
   conventions.
6. **Preview:** inspect and remove provisional associations, optionally ask
   the local model to trace a few possible paths through the active choices,
   respond to any path or leave it open, then enter the crossword.

Each choice can be revised by returning to its screen. Passing individual
movements records a pass. The first screen can be bypassed to start with a broad
opening. The interface uses keyboard-operable buttons, focused scene headings,
reduced-motion support, inline artwork, and no external image or font requests.

The existing solver is mounted after setup. It reuses the same grid, selection
presentation, keyboard behavior, check/reveal behavior, and multiplayer
handlers. `/` gets no calibration or solve-journal callbacks, preserving the
daily solver's interactions. A small header opens an accessible native dialog
for the starting profile without unmounting the puzzle. Restarting setup warns
that unsaved puzzle letters will be lost.

## Calibration stimuli and what a choice means

`src/crossword/future_catalog.json` now contains 64 versioned `StimulusV1`
records across objects, abstract forms, material textures, colors, numerals,
words, and typographic marks. The original `objects`, `companions`, and `traces`
catalog entries remain for compatibility. Each calibration spread is
deterministically shuffled from the calibration ID and records the exact
stimulus IDs, versions, and zero-based positions shown. New journals use the
rejection-sampled `selector-v2`; pre-existing `selector-v1` journals retain
their exact original ordering when restored.

The selectable presentation mode is retained with the journal. A choice is
evidence only that the player chose one item among those items under that
presentation. It does not identify a personality, declare a topic preference,
or indicate word knowledge. The provisional starting profile separately uses
authored association seeds from the selected signs and explicit trace choices;
these are invitations for future content, not claims about the player. The UI
does not currently infer or present a narrative personality profile from the
raw calibration log.

After the episteme has evidence, the profile panel can request a separate
`private-profile-narrative-v1` field note. It is evidence-bound prose rather
than a personality inference; the saved model choice is preferred when that
tag is installed, and the panel shows the local model and prompt receipt.

## Local and host persistence

- `crossword.future.v1` in local storage retains the draft and current screen.
  Old v1 drafts are migrated when read to account for the added variation
  screen. Invalid saved drafts start a new opening.
- `CalibrationSessionV1` in `packages/domain/src/calibration.ts` is the shared
  bounded contract. It records the calibration/profile IDs, bank and selector
  versions, deterministic seed, presentation mode, current movement, selected
  weekday/language setup, exact presented offers, choose/pass responses,
  relation metadata, timestamps, and terminal status. It has no free-form
  personality claim or learned-word assertion.
- Observations are stored in the dedicated
  `crossword-calibration` IndexedDB database. Revisions use compare-and-swap;
  observations and retract/restore actions append rather than rewrite history.
  The UI reports local save, pending sync, host save, and conflicts separately.
- On startup, if IndexedDB has no journal and the host is online, `/future` reads
  `GET /api/future/calibrations/<calibration-id>`, checks that the record belongs
  to the current profile, restores it locally with the host ETag/revision, and
  rebuilds the opening draft from its active responses. A 404 starts an empty
  journal.
- The local Flask host persists the same session in SQLite's
  `future_calibration_sessions` table through `GET`/`PUT
  /api/future/calibrations/<calibration-id>`. Writes are same-origin, limited to
  1 MiB, checked by the shared TypeScript validator against catalog IDs and
  versions, and protected by `If-None-Match: *` on create and `If-Match` ETags
  on update. Host revisions use compare-and-swap; previously recorded events
  are immutable, and completed/skipped journals are terminal. A completed
  journal requires an active response (a choice or pass) for movements 1–4,
  explicit weekday/language setup, and the final setup cursor. A skip remains a
  valid terminal record without those responses. Both the client transition
  helpers and host reject cursor jumps of more than one movement. The host
  permits a one-movement advance only when the candidate journal still has an
  active choice or pass for the current movement. Revisiting a screen and
  advancing on its existing response is valid; retracting the only response
  removes that permission. Backward cursor movement remains valid.
- If a write fails after the host committed it, the client reads the host
  journal and automatically rebases/retries only when the host is a valid
  append-only prefix of the local session: identity/settings agree, event
  arrays match their prefix, and the remote timestamp is not newer. This
  recovers lost create/update responses without duplicating or discarding
  observations. An incompatible branch remains intact in IndexedDB and is
  marked as a conflict; the UI does not silently merge or overwrite it.
- Calibration is saved separately from the starting profile at
  `PUT /api/future/profile/<profile-id>`. Flask validates the explicit profile
  draft and derives the provisional associations and generation brief into
  SQLite's `future_starting_profiles` table. There is no profile-listing
  endpoint or shared global current profile. These random IDs are local
  capabilities; keep them out of public links and analytics. This experiment
  uses the existing local application's trust boundary, not an Internet
  account/authentication model.
- `GET` at the same profile URL retrieves the durable record. Profile conflict
  recovery can reload that version without unmounting the puzzle.
- Profile writes are bounded to 16 KiB; cross-origin browser writes are
  rejected. Creates and updates use ETag compare-and-swap. A profile conflict
  can load the latest server version without unmounting the active puzzle. The
  evidence ledger is capped at 64 MiB and reducer request bodies at 256 KiB.
  The constellation panel can download the stable host archive, restore it
  into a fresh local profile, and delete the complete local profile. Import
  validates the archive atomically, refuses overwrite, omits shared puzzle
  manifests and worker capabilities, and deletion removes profile-owned rows
  and browser journals while shared puzzle manifests remain available to other
  sessions.

The raw calibration journal stays separate from the starting profile. Only
after an explicit request does the local host select active choices from the
opening, verify them against the pinned stimulus bank, and send a compact form
of those choices to loopback Ollama. At least one active choice is required;
passed movements remain optional, while a skipped opening or one with no active
choices leaves path generation unavailable. The prompt contains the
selected catalog labels, their IDs and versions, and valid relations; it omits
movement positions and timing. The browser cannot author or edit the model's
interpretation. Each frozen path links back to the exact active observations
and stimuli that prompted it.

Generated paths are provisional associations, not personality descriptions,
knowledge claims, or explicit topic preferences. They expire after 14 days or
five later puzzle sessions. An unanswered path contributes no retrieval
weight; keeping one gives it at most a 0.05 exploration weight, while “Not for
me” remains counterevidence and “Pass” adds no preference. Every response can
be undone and restored without erasing its history. The deck is versioned to
the active calibration choices, so changing earlier answers creates a new
source snapshot rather than silently reusing stale interpretations. After
expiry, the interface closes new responses and restores while leaving an active
response available for retraction. The profile panel lets the player return to
the saved deck.

The local Ollama call is optional and uses no hosted inference fallback. If
Ollama or the host is unavailable, the interface explains that and still lets
the player use the onboarding/profile screens. `/future` now opens to a private
puzzle-creation panel rather than requesting a daily puzzle. After the opening
profile is saved, choose Monday through Sunday difficulty and select **Make a
new personal crossword**. The app sends the profile ID, weekday, fresh seed,
and an idempotency key to `POST /api/future/private-puzzle-jobs`. Flask freezes
the current profile and episteme, and the local worker runs Ollama theme/clue
generation plus native xfill from that snapshot. The browser polls the job,
shows queued, theme, crossing, clue-writing, and finalizing stages from the
worker’s active lease, and can stop waiting without replacing the current board.
When ready, the worker result is normalized into the shared solver’s
ordinary `{metadata, entries, puzzleManifest, provenance}` shape. The private
V1 solve journal then records play and supports post-game reflection. The exact
generated puzzle is saved per profile in browser storage, so a reload restores
the board before the journal replays the player’s current letters. The three most
recent personal manifests stay in a bounded local shelf; open “Recent personal
crosswords” to restore an older board before replacing the current one. `/` remains
on its normal daily feed. Older local hosts retain the synchronous
`POST /api/future/private-puzzles` route as a compatibility fallback.

The durable job identity is also kept in a profile-scoped browser record while
the worker is queued or running. If the tab reloads, `/future` reattaches to
that job and resumes the same stage polling; a ready result still asks before
replacing letters from another crossword. Failed, cancelled, superseded, and
successfully applied jobs clear the pending record.

When a private board is created, its bounded model, fill, clue, challenger,
and construction receipt is stored beside the frozen manifest under the owning
profile. After a finished game, the post-game view reopens that
`private-puzzle-provenance-v1` receipt through the session-scoped route
`GET /api/future/sessions/<sessionId>/private-provenance?profileId=...` and
shows construction counts without exposing the answer grid or turning them into
a player judgment. Missing receipt storage remains fail-open for play; a
tampered receipt is rejected by its digest check. After the session is finished,
the owner-scoped `GET /api/future/sessions/<sessionId>/private-review-bundle?profileId=...`
route joins the exact manifest and provenance into a `private-clue-review-bundle-v1`
file. The `/future` clue-quality panel offers that answer-bearing download only
for the finished session; it is marked `publishable=false`, every entry starts
`unreviewed`, and it never enters the episteme or publication tables.

The receipt also reports the exact-form exposure lane without listing the
player's answer history: how many recent forms were available, how many theme
answers were fresh, and how many repeated forms survived the bounded cooling
policy. This makes personalization inspectable while keeping exposure separate
from mastery.

While playing, the constellation panel also exposes the next-crossword difficulty
and learning-thread selectors. Saving those changes updates the local profile for
the next generated board without restarting calibration or changing the board
currently on screen.

The same creation panel exposes a local writing-model selector. **Automatic**
keeps the host's preferred installed model order (large tier first, then
local-small, then the 8–14 B local-mid tier); choosing any allowlisted tag —
Gemma 4 26B, Qwen 3.8 27B, Gemma 4 31B, Gemma 3 27B, Llama 3.2 3B, Gemma 3 4B,
Llama 3.1 8B, Qwen 3 8B, Gemma 3 12B, or Qwen 3 14B — sends that exact tag
through the durable job. The choice is part of the profile draft and is included when the
player uses the constellation panel's existing **Save changes** action, so a
later session restores the same preference. Flask checks the tag against this
device's Ollama installation before freezing it, and the worker records the
selected model in the resulting provenance. Older clients that omit `model`
still inherit the saved profile choice; Automatic keeps the host's installed
model order. A missing named model fails with an actionable local install
message; it never silently substitutes another model.

When a personal board is ready, its creation panel can expand a bounded
personalization receipt. It shows only the episteme revision and counts for
saved signals, open threads, recent exposures, language, and difficulty lanes;
it never exposes the profile digest or turns those inputs into a personality,
knowledge, or mastery claim.

The same panel now includes an answer-free history of the most recent personal
games. It shows each saved title, day, model, and bounded replay summary while
keeping answer cells and clue text inside the private session record.
That response also carries a bounded observational calibration report grouped by
weekday and local model. After three finalized games it shows completion and
crossing/assistance rates as descriptive play traces; before that it stays in an
insufficient-observations state. It is never presented as a solve probability,
mastery score, or human-calibrated difficulty claim.

The history panel can also download a `private-play-calibration-export-v1`
trace. This local-tuning artifact contains only bounded session metadata and
the aggregate replay signals used by the difficulty lane. It omits answers,
clues, grids, raw solve events, and profile prose, and declares those
redactions in the file itself. It is separate from the full profile archive so
an evaluator can inspect play calibration without carrying the user's episteme
or puzzle content along. The envelope includes a canonical SHA-256 integrity
receipt so a later local evaluator can detect edits without trusting a server.

Completed private sessions now contribute a bounded `playCalibration` signal to
the next local generation brief. The host averages completion, independent
retrieval, supported/assisted retrieval, and incorrect-attempt rates over at
most six recent analyses and chooses only `more-footholds`, `balanced`, or
`gentle-stretch`. This adjusts accessibility inside the selected weekday recipe;
it is reversible provenance and is never treated as a preference, identity, or
mastery claim.

Measured Gemma 4 26B generations take about 59–103 seconds depending on the
xfill search, theme proposal, and conservative clue-repair pass. It requires
Ollama plus Gemma 4 26B or Qwen 3.8 27B and the native xfill runtime (the
standard `make run` starts the Flask host and private worker, and passes the
sibling generator path by default). The “Locally made with Ollama” label
denotes experimental generated content, not source-checked clues or publication
readiness. Difficulty changes construction search settings and clue voice.
Monday, Wednesday, and Thursday also carry explicit recipe directions.
When a pinned admitted pack matches an answer, the clue-quality receipt marks
the exact reviewed clue/sense/fact join as `reviewed-source` and records the pack
digest; model-only clues remain `not-established`.
If the optional local challenger runs, non-keep recommendations are shown as
advisory notes in the same collapsed panel; they never become profile steering
unless the player explicitly keeps a note for future puzzles.
Thursday proposes a typed shared-prefix or shared-suffix pattern from the local
fill dictionary; the host validates it against the proposal and the actual
filled theme entries before clue writing sees it. Failed proposals fall back to
an ordinary themed grid and are marked unavailable in provenance. The finished
Thursday provenance now also carries a digest-bound
`private-weekday-mechanic-evaluation-v1` receipt, and the postgame receipt shows
whether the declared instances passed the structural check or safely fell back
to an ordinary grid. This is an inspection trace, not a fairness or solve-
probability claim. Calibrated weekday fairness and rebus/special-cell mechanics
remain future quality work.
When a validated Thursday candidate is available, the fill selector gives it
priority while its iffy count stays at or below 12; above that bounded budget,
ordinary fill quality still wins and the mechanic remains unavailable.
Private provenance also records structural crossing access for each entry and
which weak entries have no crossing foothold; this is a construction diagnostic
only and explicitly does not estimate player support.
Generation failure is shown in the panel and can be retried. No hosted
inference fallback is used.

Clue writing receives each entry's fill score and a small clue policy. Weak
entries are asked for source-free footholds: ordinary definitions, sounds,
spellings, functions, or clearly signalled wordplay rather than obscure trivia
or invented proper-name relationships. A bounded repair pass checks factual
surfaces and mechanical wordplay; if an unsupported factual surface survives
on a weak entry, the private route uses an answer-free crossing metaclue and
records the fallback in `provenance.clueQuality`. The final guard also replaces
answer giveaways and mechanically false anagrams, reversals, or translations
when the repair pass cannot fix them. This is a local-play safety net, not
semantic fact review or a publication gate; stronger entries may still carry
model-written factual surfaces and remain experimental.

`provenance.clueQuality.grounding` makes that boundary inspectable. For every
entry it records deterministic structure from the native fill (answer length,
letters-only shape, and repeated-letter count), the small set of explicit clue
conventions it recognized, a surface-only family observation with signal spans,
and an uncertainty label. Anagram and reversal
relations can be marked mechanically consistent or failed when their supplied
letters allow that check; labels such as `(pl.)`, `(abbr.)`, and `in German`
remain surface conventions only. The layer never treats a definition,
translation, biography, or other model-written meaning as verified. Crossing
scaffolds therefore remain explainable as structural assistance rather than
invented evidence about the answer.

The playing view keeps this quality record available in a collapsed **Local
clue notes** disclosure. It lists only entries with deterministic risk flags
and leaves the board and clue focus unchanged. The assistance ladder now
continues from clue-reading and context to a suggested crossing, an optional
single-letter reveal, and an optional entry reveal. Each step is opt-in, lowers
the local score in the same way as the solver's existing reveal behavior, and
is recorded as a separate journaled assistance/reveal event. A clean quality
pass still says that semantic meaning is unverified; it is an experimental
local puzzle, not an editorially sourced one.

Each flagged entry also offers **Flag for future puzzles**. That action is an
explicit, reversible narrow episteme control for the flagged clue surface; it
does not rewrite the finished puzzle or turn the flag into a claim about the
player. The profile archive keeps the resulting episteme revision, while
deleting the profile clears the browser-side flag cache.
The next private generation brief consumes the small allowlisted clue-family
mapping from that explicit control, so an avoided factual or punctuation surface
is actually downweighted on later boards; clearing the control removes the target.

Responses to the authored post-game cards also become bounded generation
signals. Keeping or turning away a wordplay, discovery, or challenge card can
include or avoid that clue family in a later private brief; the signal is
explicitly marked as reviewed, reversible, and separate from solve behavior or
vocabulary mastery.

When a player selects a learning language, clearly signalled language entries
are recorded as an explicitly unreviewed exposure thread. A later private
generation may revisit at most two matching forms when they fit the new fill,
with the language named in the clue. This is gentle recurrence rather than a
spaced-repetition claim: exposure, checking, and a crossing never become proof
of mastery. When a due form is present in the local xfill dictionary, the
generation brief also exposes it as an optional candidate; it is never forced
as a theme lock and unplaced forms remain review items.

The future solver also has a narrow language-input boundary in
`apps/react/src/future/languageInput.js`. The first explicit packs are German,
French, and Dutch. Dutch starts with the ASCII-safe forms `JA`, `HUIS`, and
`WATER`, while its explicit pack also normalises common accents. The packs
normalise NFC/combining accents for display and map accented
or ligatured forms to a documented fill token (for example `é` → `E`, `Ä` →
`AE`, `Ü` → `UE`, `ß` → `SS`, and `œ` → `OE`). Multi-character mappings are accepted only for rebus or
other explicitly multi-token cells; ordinary generated cells remain the
current ASCII one-token contract. Unknown language packs stay disabled rather
than silently receiving English accent-stripping rules. `/future` passes the
policy to the shared React view, while `/` does not pass it and keeps the
existing controller behavior unchanged. A future rebus cell now sends its
input through the same explicit adapter before the existing save/check path:
German `ß` becomes the fill token `SS`, and French `œ` becomes `OE`.
`describeLanguageToken()` exposes answer-free display units, fill units, alias
use, and pack/version metadata; the current journal continues to persist the
canonical fill string so its strict event contract remains intact. The private
host now accepts an explicit native-token construction envelope and carries
multi-unit `cellTokens` through construction, manifest registration, checking,
and reveal journaling. Ordinary xfill and the `/` route remain ASCII-only, and
no token is inferred without an explicit sidecar. The delayed-review endpoint also recognizes a small local
`language-task-pairs-v1` fixture for German, French, and Dutch answer forms. Its due
items carry only answer-free source/grammar metadata, with explicit
`synthetic-unadmitted` and `not-established` labels; the opaque reveal endpoint
keeps the target form behind the existing local review action. This fixture
exercises the contract and UI boundary only. It is not an admitted corpus, a
native-speaker review, a semantic truth claim, or a mastery signal, and it does
not participate in ordinary generation or the daily route. The future-only `future-token-manifest-v1` sidecar now provides that
contract when a producer supplies it: it binds the sidecar to the existing
puzzle-manifest digest, records display/fill units per geometric cell, checks
crossing equality, and adapts the private solver entries to canonical fill
strings on save and restore. The strict V2 publication document and ordinary
native generator remain unchanged; no token sidecar is synthesized from an
ordinary ASCII board.

After an exposure has aged for 24 hours, `/future` can surface a small local
recall queue beneath the solver. The prompt gives the original clue and length
without placing the answer in the browser-visible task handle. “I recalled it,”
“Not yet,” and “Pass” record an independent response; revealing the answer and
then choosing “Saw it” records an assisted response instead. An independent
success returns after seven days and then thirty days; assisted or not-yet
responses return after 24 hours, while Pass ends that exposure's queue. The host
serves three due items by default and exposes bounded six- and twelve-item
budgets; the player can ask for more without changing task identity or response
semantics. These
records are included in profile export/import and are removed with the owning
profile, but they do not claim mastery. Once a profile has at least eight mixed
independent remembered/not-yet outcomes, the host policy reports a bounded,
diagnostic-only exponential forgetting fit from those records; it remains
separate from the scheduler and never changes due dates. The next local brief
can use the categories to favor pending, not-yet, or assisted forms while
letting a recently remembered form cool.

Due items also carry bounded overdue hours and a scheduler priority. A thread
that has waited far beyond its interval can rise within the optional review
queue and the next private-generation candidate list, but its bonus is capped
at one extra interval so one neglected form cannot crowd out every other
thread. The UI states the delay directly (for example, “26h overdue”); this is
ordering metadata, never a recall probability or a mastery estimate.

The scheduler contract also has a bounded delayed-recall study fixture in
`tests/test_learning_review.py`. It replays one exposure through independent
successes, an answer-assisted response, not-yet responses, and later spaced
successes. The assertions cover the provisional 24-hour, 7-day, and extended
30-day transitions, contiguous-streak reset, and the diagnostic fit's mixed
independent sample counts. The fixture is a deterministic contract check, not
a learning or mastery claim.

For local use, install project dependencies with `make setup`, ensure Ollama
is running with one supported model installed. Small local-small tags
(`llama3.2:3b`, `gemma3:4b`) fit a 16 GB host; the local-mid tier
(`llama3.1:8b`, `qwen3:8b`, `gemma3:12b`, `qwen3:14b`) also fits but is never
chosen automatically (name it with `CROSSWORD_PUZZLE_MODEL` or the profile
preference), and the larger two may need a raised Metal wired limit; the large
tier (`gemma4:26b`, `qwen3.8:27b`, `gemma4:31b`, `gemma3:27b`) needs ~15-18 GB
and is selected first only where installed. An optional cloud clue model
(`cloud:<name>`) is off by default; see
[the generation plan](plans/16_GENERATION_PLAN.md). Before starting the server, use
the read-only runtime doctor:

```sh
make runtime-doctor
```

It checks the lockfile-pinned `@crossword/local-runtime` archive and CLI, the
native xfill source/toolchain, and the loopback Ollama `/api/tags` response. It
never runs Cargo, generates a grid, or downloads a model. A healthy machine
prints output in this form (the installed model name may be Qwen instead):

```text
Runtime doctor (read-only; no model pulls)
[xfill runtime archive] ready (ready)
[xfill runtime CLI] ready (ready)
[native xfill engine] ready (ready)
[Ollama model] ready (ready: gemma4:26b)
Runtime doctor: ready for make run-personal (or make run).
```

If `CROSSWORD_PRIVATE_DOMAIN_HINTS` is set, the same check also parses that
bounded local file and reports its domain label, total term count, and number
of terms present in the configured xfill vocabulary. It never prints the
terms. A missing file is an optional `not-configured` result; a malformed or
unreadable configured file is surfaced as `unavailable` and blocks
`make run-personal` until the path is corrected. This keeps private subject
invites discoverable without silently accepting a broken hint list.

If the check is not ready, start Ollama and install one of the preferred model
tags yourself (`ollama pull llama3.2:3b` fits a 16 GB host), or set
`CROSSWORD_PUZZLE_MODEL`/`CROSSWORD_PROFILE_MODEL` to an already installed local
tag. The command only reports this state; it does not pull it. Then run:

```sh
make run-personal
```

Open `http://127.0.0.1:5001/future`, complete/save the opening if needed, then
make a puzzle. `make run-personal` runs the read-only runtime doctor, builds the
frontend, starts the durable private worker, and passes
`CROSSWORD_XFILL_ROOT=../crossword-generator/vendor/xfill` to the host; override
that variable if the native checkout is elsewhere. `make run` remains the
compatibility launcher when the readiness check should stay advisory.

The personal launchers enable the bounded local clue challenger by default.
On a full board it selects only deterministic risk, foothold, or mechanical
warning entries; small contract fixtures can still exercise every clue. It
makes an additional answer-aware advisory pass and records
keep/fallback/review recommendations in provenance; it never gates a playable
board and never turns a model judgment into semantic evidence. Set
`CROSSWORD_PRIVATE_CLUE_CHALLENGE=0` when the extra pass is not wanted.

## Compatibility answer-grid draft worker

The older answer-grid-only route remains available for construction tooling and
review-candidate experiments. It is separate from the playable private route
above and does not return a crossword that `/future` can open. The loopback-only
Socket.IO/Werkzeug launcher is a development server; production must use a
Socket.IO-capable deployment server.

The compatibility queue records the selected profile's revision digest and
retains fill scores/source digests. It is not the source of the playable
profile-seeded puzzle, and its review-candidate output remains non-playable.

In a second terminal, provision the separately licensed xfill tree and start
the worker:

```sh
export CROSSWORD_XFILL_ROOT=../crossword-generator/vendor/xfill
make future-worker
```

`make future-worker-once` processes one queued job. The same-origin host API
creates a job with `profileId`, `idempotencyKey`, and a deterministic `seed`,
returns the durable state from `GET /api/future/grid-draft-jobs/<job-id>`, and
accepts cancellation at the matching `/cancel` route. SQLite leases make
interrupted work reclaimable; cancellation is forwarded to the owned native
process and its result is discarded. The `xfill-wide-v1` recipe intentionally
searches broadly to produce draft candidates. Its fill scores and source digest
are retained with the result; they are not an editorial acceptance decision.

## Solve history and the current episteme ledger

When the solver is opened from `/future`, it can also start a version-2 solve
session associated with the starting profile. It records entry focus and the
letters visible at that moment, typed/cleared/batched cells, check results,
answer reveals, visibility and pause/resume transitions, and completion. Events
are first stored in the browser's separate IndexedDB v3 `solve-events` store
under a bounded, namespaced session record. The outbox retries to the same local
Flask host and retains unacknowledged records when offline. Supported
single-letter puzzles include a frozen, host-registered manifest. The host
requires exact open-cell initial-grid coverage, validates clue/cell references,
derives check/reveal truth from that manifest, then runs the shared deterministic
analyzer before accepting a batch. Versioned replay analysis is stored alongside
immutable events. Unsupported formats remain playable, but do not sync trusted
personal history. `/` receives no journal callbacks.

`GET /api/future/profile/<id>/episteme` creates or reads an initially empty,
revisioned profile. `POST /api/future/profile/<id>/episteme/updates` runs the
shared deterministic TypeScript reducer on the local host and commits through a
revision compare-and-swap. Exact retries return the original receipt; competing
updates receive a conflict. Explicit association controls and host-replayed
session analyses can enter the evidence ledger. The endpoint rejects
browser-authored solve analyses, raw calibration observations, and reflection
responses. The separate calibration-hypothesis API records host-authored,
source-linked model proposals. Until a player responds, those proposals add no
retrieval weight and make no claim about the player.

After replay finalizes a completed session, `GET
/api/future/sessions/<id>/reflections` freezes three cards from a reviewed,
60-card authored pool and returns three selected cards plus saved responses/actions. The
selection remains deterministic by session, while cards are now lightly
grounded in the frozen manifest when it exposes clue turns, language signals,
or longer/less familiar entries; each contextual card carries exact related
entry IDs and a `reflection-context-v1` grounding reference. Legacy sessions
without a manifest retain the generic authored wording. When launched by
`make run` or `make run-personal`, the host may enable the bounded local mirror
with `CROSSWORD_REFLECTION_MODEL_CARDS=1`. Unless an explicit
`CROSSWORD_REFLECTION_MODEL` override is set, the mirror follows the exact
model frozen in the finished puzzle provenance. It can rewrite only the
first-person wording and interpretation; category mappings, card IDs, scopes,
and response contracts remain host-authored. A structural receipt records the
exact local model and prompt version, and the postgame card shows that receipt
beside the wording. Malformed, unsafe, unavailable, or timed-out output falls
back to the authored card set. The mirror is wording assistance, not a profile
fact or a desire diagnosis. Keep, turn away, and pass
use exact card/version/position contracts; a separate action route appends
retract/restore records without rewriting the original response. Pass
contributes no preference mapping, and refreshing the deck restores the prior
choice. Imported daily clues do not yet have reviewed learning-task links, so
replay does not assert vocabulary mastery. The ordered calibration journal is
never inserted into the episteme; the optional host path stores distinct
proposal and response evidence derived from validated active choices.

## Optional local calibration paths

The **Trace possible paths** action calls
`POST /api/future/calibrations/<id>/hypotheses` with an empty request body.
The host derives the source from its validated, synced calibration journal,
checks the pinned stimulus-bank version and current active-choice digest, and
freezes one deck for that snapshot. The browser can only read the deck and
submit keep/not-for-me/pass responses or retract/restore actions. Host-authored
timestamps and IDs, append-only records, idempotency, and episteme revision
compare-and-swap protect writes.

Generation runs through Ollama at `127.0.0.1:11434` with environment proxy
inheritance disabled, bounded streamed responses, and heuristic checks that
screen direct player-directed personality, identity, health, belief, or
knowledge claims. This cannot guarantee detection of every indirect claim. The
configured local candidate is tried first; supported fallback order is Qwen
followed by Gemma 4 26B and Gemma 4 31B. Gemma 3 is not a silent Gemma 4
substitute, and models are never downloaded automatically. Inference is
optional; absent models and malformed output leave the crossword playable.

## Remaining work

The opening's stimulus bank, deterministic presentations, five-movement
append-only calibration contract, browser journal, same-origin host validation,
host restoration, safe prefix-only rebase/retry, local conflict preservation,
and reviewable association-hypothesis loop are implemented. The loop verifies
the active source snapshot, uses local Ollama only, binds every proposal to
exact observations and stimuli, caps exploration influence, records expiry,
and supports response correction. Completion still requires a current
response (choose or pass) for movements 1–4 and explicit setup; skipping the
opening remains valid. A fixed-seed cohort test caught the old selector's
modulo-tail bias; new journals now use rejection-sampled selector-v2, while
existing selector-v1 journals replay their original offer order. This checks
item-position distribution, not human salience or accessibility. Incompatible
branches are preserved locally without a guided merge path. The selected
weekday now drives the private original-puzzle construction job; the separate
admitted-content/V2 route remains a review artifact and is not the private
solver path.

Other unfinished work includes reviewed learning-task links; semantic
fact/sense grounding for model-written clues; richer recall scheduling and
learning-task grounding; puzzle-grounded reflection selection; calibrated
Thursday fairness and rebus/special-cell mechanics; licensing reconciliation;
live comparative model evaluation, a production runtime, and human full-size
puzzle evaluation; and release hardening. A current two-seed Gemma study has
exercised both Thursday outcomes: one board validated four shared-suffix
instances and one safely fell back to an ordinary grid. Its structural receipt
is preserved in the plan evidence. The native constructor now has a receipt-only
`private-fill-quality-study-v1` evaluator (`scripts/fill-quality-study.py`)
for fixed-seed retry comparisons, plus `private-fill-quality-comparison-v1`
(`scripts/fill-quality-compare.py`) for policy-versus-baseline pairs.
`scripts/private-fill-study.py` can run the same receipt collection through a
running local `/api/future/private-puzzles` server for explicit seeds. It
records measured and unavailable xfill fields with a digest and never treats
them as solve probability or a play gate; the checked synthetic artifacts are
`docs/evidence/private-fill-quality-study-v1.synthetic.json` and
`docs/evidence/private-fill-quality-comparison-v1.synthetic.json`. Real
admitted-content runs and independent player/editorial evaluation remain
unfinished. A real local Gemma 4 26B Wednesday receipt is also retained at
`docs/evidence/private-fill-quality-study-v1.real-gemma4-26b-wednesday-20260928.json`;
it is construction evidence only and does not establish human quality. The sibling
generator lab now has a fixture-tested, opt-in Ollama comparison runner. A
current exact-tag live smoke is preserved at
`docs/evidence/live-model-smoke-holdout-v1.20260928.json`: Qwen 3.8 27B and
Gemma 4 26B each completed all four frozen prompts with valid JSON and valid
shape gates; Qwen took 174.6 seconds total and Gemma 25.3 seconds on this
machine. This is structural/runtime evidence only, not a live quality winner.
See
[the implementation plan](plans/06_PERSONAL_EPISTEME.md) for the full execution
sequence.

The opening is responsive. Once it enters the puzzle, it uses the existing
desktop solver layout; this change does not redesign the mobile solver.

## Validation

Run the focused suites and repository checks appropriate to the current change:

```sh
npm --workspace @crossword/react-port test
npm run typecheck
uv run --no-sync python -m pytest -q
CROSSWORD_E2E_BACKEND_PORT=5013 npm run test:e2e -- --reporter=line
```

The hypothesis host boundary can also be checked without installing or calling
an Ollama model:

```sh
uv run --no-sync python -m pytest -q tests/test_calibration_hypothesis_api.py
uv run --no-sync python -m pytest -q tests/test_lexicon_pack_builder.py
npm --workspace @crossword/react-port test -- src/future/FutureApp.test.jsx src/future/CalibrationHypotheses.test.jsx
```

Calibration contract, seeded-presentation, artwork, IndexedDB, host API, and
React onboarding tests cover bounded records, exact offer references, append
ordering, retractions, ETag conflicts, terminal immutability, and user flows.
Synthetic lexicon-pack tests cover pinned source hashes, admission metadata,
fill-only unresolved senses, evidence provenance, and grammar-validator
fail-closed behavior; they do not supply a production corpus.
For browser parity, `scripts/ci-server.py` serves original synthetic puzzles
with a disposable database and outbound networking disabled. Choose an unused
port with `CROSSWORD_E2E_BACKEND_PORT`; compare identical grid interactions on
`/` and `/future`.

For an opt-in native receipt study against a running local server, first create
or restore a `/future` profile, then run one or more explicit seeds:

```sh
.venv/bin/python scripts/private-fill-study.py \
  --profile-id "$PROFILE_ID" --weekday wednesday \
  --seed 7 --seed 19 --out /tmp/private-fill-study.json
.venv/bin/python scripts/fill-quality-compare.py \
  /tmp/private-fill-study.json /tmp/private-fill-baseline.json \
  --expected-seed 7 --expected-seed 19
```

The collector is restricted to loopback HTTP(S), sends only the profile ID and
requested seed, and writes fill receipts rather than puzzle answers or profile
prose.
