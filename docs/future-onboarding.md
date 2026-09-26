# The `/future` opening

`/future` and `/future/` serve the existing React application with a separate,
lazy-loaded onboarding route. `/` remains the daily solver. Build with
`make react-assets`; the normal Flask server serves both routes on port 5001.

## Experience

1. **Encounter:** choose an original illustrated object or sign. A red thread,
   river stone, glass cube, brass key, unfinished circle, or zero.
2. **Company:** the first object determines four possible companions. The chosen
   object stays visible. Choices can be revised or passed over.
3. **Resonance:** keep up to three words, symbols, or numerals.
4. **Rhythm:** explicitly choose Monday–Sunday difficulty, independent of the
   calendar. Optionally record a language-learning interest. A small expandable
   note introduces clue conventions.
5. **Beginning:** inspect the provisional word field, remove individual
   associations, optionally invite local AI to extend it, and enter the puzzle.

There is also a direct path from the first scene to difficulty selection. The
layout is responsive, choices are native keyboard-operable buttons, step headings
receive focus, and reduced-motion preferences disable entrance animation.
Illustrations are original inline SVGs; there are no external image/font requests.

The existing solver is mounted after setup, so it cannot intercept onboarding
input. Its view, selection presentation, keyboard methods, check/reveal behavior,
and multiplayer handlers are reused. A small header opens an accessible native
dialog for the starting profile without unmounting the puzzle. Restarting setup
explicitly warns that the active puzzle's unsaved letters will be lost.

## State and personalization

- `src/crossword/future_catalog.json` is the shared, versioned stimulus catalog.
- `apps/react/src/future/episteme.js` derives a provisional seed from actual
  choices. Word associations are invitations; the initial knowledge map is empty.
- `crossword.future.v1` in browser storage retains the setup position and choices.
  Invalid persisted state starts a fresh draft. Storage failures are visible.
- Finishing setup sends the choices to
  `PUT /api/future/profile/<random-uuid>`. Flask independently validates them and
  derives the durable profile in SQLite's new `future_starting_profiles` table.
  This is additive: existing puzzle/completion tables are untouched.
- `GET` at the same URL retrieves the durable record. There is no profile-listing
  endpoint or shared global current profile. The random id is a local capability;
  keep it out of public links and analytics. This experiment uses the existing
  local application's trust boundary, not an Internet account/authentication model.
- Profile writes are bounded to 16 KiB; cross-origin browser writes are rejected.
  A failed server save leaves the browser copy usable, with an explicit retry in
  the profile dialog. Editing is immediate locally; **Save changes** persists the
  new version to the server.
- The server includes a `generationBrief` with seed words, explicit difficulty,
  language interest, and a 20% maximum initial seed influence. It prohibits
  converting aesthetic choices into claims about personality or knowledge.

## Optional Ollama extension

**Let these words wander** calls `POST /api/future/associations`. It uses the local
Ollama endpoint at `127.0.0.1:11434`, discovers installed models, and requests at
most six associative words using a bounded JSON schema. The endpoint itself does
not write a profile; the user can discard its proposals before saving.

The preferred model is `qwen3.8:27b`. Set `CROSSWORD_PROFILE_MODEL` to an installed
Ollama tag to choose another model. Installed `gemma4:31b` and `gemma3:27b` are
fallback candidates. Models are never downloaded automatically. Local inference
is optional, has a 40-second read timeout, and malformed output is rejected. The
browser remains usable while it runs; entering the crossword abandons the pending
client request. Output can finish on the server but cannot change saved state.

## Current scope

**The selected weekday affects the puzzle loaded now.** Associations and language
preferences are saved for the personalized generator integration described in
[the implementation plan](plans/06_PERSONAL_EPISTEME.md). The current solver still
loads its daily collection. The UI explicitly says so; it does not present the
daily puzzle as a newly generated personal crossword. Foreign-language puzzle
generation, play-event learning, post-game statements, and profile evolution are
subsequent work.

The opening is responsive. Once it enters the puzzle it uses the existing desktop
solver layout; this change does not redesign the mobile solver.

## Validation

Run the React suite, typecheck, and isolated Flask tests:

```sh
npm --workspace @crossword/react-port test
npm run typecheck
uv run --no-sync python -m pytest tests/test_api_isolated.py tests/test_future_api.py -m 'not live_provider'
```

The new tests cover dependent choices, corrupted or unavailable storage, complete
and skipped flows, three-choice limits, resume, exclusions, weekday isolation,
SQLite persistence, request validation, origin/size limits, and mocked Ollama
success/failure. Existing selection and behavior parity suites remain applicable.

For safe browser verification, `scripts/ci-server.py` serves original synthetic
puzzles with a disposable database and outbound networking disabled. Choose an
unused port with `CROSSWORD_E2E_BACKEND_PORT`. Browser checks compare identical grid
interactions on `/` and `/future`; their selection classes, computed colors and
focus destinations must match.
