# React port parity — verified status

Status: **verified as documented below, as of this session.** Nothing on this
page is claimed beyond what the referenced, reproducible commands produced.

## Final test rerun

`npm test -- --runInBand && npm test --workspace @crossword/react-port`
completed with **exit 0**: root Jest **11/11**, React Vitest **22/22**.
No failing tests remained in these two suites. This did not run Python,
generator or other package suites. The initial port left Vue unchanged; the
requested follow-up below updates both frontends deliberately. The original
stash and generator repository remain untouched. Existing Flask and React dev
servers were left available for review.

## What was verified, and how

### 1. Behavior parity tests (React side)

Command: `npm test --workspace @crossword/react-port`

Result: **exit 0 — 3 files, 22/22 tests passed** (Vitest 3.2.4, jsdom).

`apps/react/src/mobile-render-parity.test.jsx` adds three mounted-component
comparisons: the original Vue template compiled by Vue versus the React view,
using real DOM inputs and render commits. Covers selection/input/backspace,
check colors and solved-clue reordering/refocus, and swap deny/accept/broadcast.
An initial synthetic-click focus discrepancy disappeared when button clicks
were modeled with their browser focus default; no production change was needed.

- `apps/react/src/parity.test.js` — 11 explicit controller contracts: grid /
  cell map / black squares, clue & mini-cell click focus, navigation and
  black-square skips, letter input/backspace, check colors/penalties/counters,
  reveals/rebus, persistence payloads, load cancellation, mobile input
  boundaries, disposal.
- `apps/react/src/behavior-parity.test.js` — 8 differential scenarios that load
  the **original** `src/crossword/static/main.js` / `mobile.js` via `?raw`,
  execute them under the **real Vue 2 runtime**, and compare against the React
  controller running the generated options: loading/cache requests, watchers &
  socket updates, focus/input, checks, rebus/persistence, load confirmation,
  mobile role-scoped behavior.

The suite before this session: 9 failed / 1 passed. The failures were broken
test harness assumptions (fake storage encoding, fake focus during ref
creation, missing flush, incorrect fixture expectations — e.g. cellMap size,
`clearChecks` semantics, `checksUsed` counting, `markPuzzleSolved` URL) — not
Vue bugs. The Vue reference was **not** modified to make tests pass.

### 2. Browser comparison of the running apps

Command: `node scripts/react-browser-parity.mjs` (requires Flask on :5001, Vite
on :5174; provider routes are intercepted with a synthetic 15×15 fixture, so no
real puzzle data is touched).

Result: **exit 0 — all 15 checkpoints `domEqual: true`, `passed: true`.**
(`reports/react-parity/results.json`, per-state PNGs and DOM JSON snapshots.)

Checkpoints: main board, clue click focus, letter input, check, clear checks,
mini-cell click, cell reveal, rebus open/save, dark mode, solved/cache/
multiplayer modals, cancelled weekday reload, and crossing-direction change.
Checkpoint 15 selects Down then presses Right: focus stays at (0,0), and
both the movement lane and selected word become Across, with the three Across
cells highlighted and three Down crossings affected (requested follow-up).

#### Targeted movement/highlight browser trace

`PARITY_TRACE=movement node scripts/react-browser-parity.mjs` — **exit 0,
11/11 matching DOM states**, 948–977 differing pixels per 1440×1000 capture
(within the same accepted tolerance). Output is separate:
`reports/react-movement-parity/results.json` and per-state DOM/PNG files.

The trace selects Across, presses Down twice, reaches the word end, skips a
black square, types Q, backspaces from an empty cell, clears the occupied Q
and moves backward over the black square, changes to Across using Right,
moves Right/Left, and tests the left grid boundary. Each state explicitly
asserts actual input focus and the destination word's highlight coordinates.
The requested selection-following behavior is implemented in both frontends;
this supersedes the initial port's intentionally preserved stale selection.
This trace does not verify filled-word automatic jumps, every grid edge,
rapid key repeat, IME/composition, or mobile touch/keyboard behavior.

#### Mobile rendered interactions and browser comparison

`node scripts/mobile-browser-parity.mjs` — **exit 0, 10/10 DOM matches,
zero differing pixels at every captured state** (Chromium 137, 390×844).
Artifacts: `reports/react-mobile-parity/`.

Uses each real mobile route, creates isolated in-memory rooms via the backend,
and receives initial state through real Socket.IO joins. Only puzzle HTTP data
is replaced with a synthetic fixture. Checks loaded Across clues, clue selection,
hidden-input focus, typing/backspace, correct-word checking, solved-clue
reordering, refocusing a solved clue, switching clues and final-cell input.
Rooms are ephemeral server memory; this harness does not write puzzle or
completion records. No room deletion endpoint is available.

This was mouse clicking plus Playwright keyboard input at a mobile viewport,
not touch emulation or a physical device/OS keyboard. Touch, IME, keyboard
viewport resizing, partner synchronization and actual server role swaps remain
unverified. No mobile production bug was reproduced in this round.

### 3. Production build

Command: `npm run build --workspace @crossword/react-port` — exit 0
(322 kB / 101 kB gzip bundle).

## Vue feature → React verification matrix

`P` = `apps/react/src/parity.test.js`; `D` =
`apps/react/src/behavior-parity.test.js`; `B` = checkpoint in
`scripts/react-browser-parity.mjs`. Line numbers identify test declarations.
Browser assertions compare the rendered `#app` tree, classes, selected
attributes, values, focus, direction and theme; whitespace/class order are
normalized. They do not compare every HTML attribute or CSS property.

| Vue feature / reference | React test evidence | Verified boundary |
| --- | --- | --- |
| Metadata, authors/notepad, three control bars, solution link (`newapp.html`) | B01 DOM and screenshots | One 15×15 fixture, one desktop viewport |
| Grid dimensions, black squares, clue numbering, intersections (`main.js`: `init`, `buildCellMap`) | P75, D148, B01 | Shared cells and grid layout; circled/shaded/rebus fixture rendering |
| Across/down clue lists, active/affected highlights | P85, D173, B02/B06 | Whole-clue focus and mini-cell stale-highlight quirk |
| Letter entry, arrows, backspace, black-square skipping, filled-word jump | P104/P130, D173, B03 | Method-level navigation; browser letter entry and focus |
| Check colors, score penalty, counters, completed-clue removal | P148, D196, B04/B05 | Wrong/correct/empty behavior; sticky completed words |
| Context-menu cell reveal | P167, D215, B07 | Empty-cell-only reveal and penalty |
| Rebus editor, save/cancel and focus | P167, D215, B08/B09 | Browser open/save; cancel at method level |
| Weekday persistence, load confirmation and acceptance | P215, D245, B14 | Browser cancel preserves progress and selected Friday; acceptance at method level |
| Puzzle retrieval, cached counts, completion lookup | D148 | Mocked HTTP contracts and local cache; not real provider integration |
| Local solved history and backend completion payload | P194, D215 | Storage round-trip/dedup and mocked POST |
| Timer and controller cleanup | P230 | Fake timers/subscription cleanup; browser timer intentionally paused |
| Light/dark switch | B10 | Actual label click, scheme and rendered DOM/screenshot |
| Solved, cache and multiplayer modal shells | B11/B12/B13 | Open/close buttons and empty/default contents; not populated history/QR/session flows |
| Desktop remote cell update | D148 | Mock socket callback; no live multi-client test |
| Mobile role-scoped check/clear and solved ordering (`mobile.js`) | P252, D286, mounted tests, mobile browser 06–08 | Rendered checking/reorder/refocus; broader roles at method level |
| Mobile hidden-input focus, last-character input/backspace | P271, D263, mounted tests, mobile browser 02–05/08–10 | Browser click/keyboard verified; touch and OS keyboards unverified |
| Mobile initial state, remote edits, role swap quirks | D306, mounted tests, mobile browser 01 | Real initial Socket.IO join; remote edits/swaps mocked |
| Reveal-all / mark-complete controls, fireworks and sound | No end-to-end test | Present in port; completion persistence is tested separately, full action paths unverified |
| Offline recovery, cache refill/manual caching, exhausted retries | Partial D148; no full scenario matrix | Unverified under failure, quota or reconnect conditions |
| Responsive layout, scroll extremes, populated modals, mobile CSS | No browser comparison | Unverified outside captured desktop states |

## One production fix made during verification

`apps/react/src/controller.js` — the observable-store proxy wrapped the fixed
`$refs` property, violating the JavaScript Proxy invariant for
non-configurable, non-writable properties (`TypeError: 'get' on proxy…`),
which crashed every clue-click focus in the browser. The `get` trap now returns
the exact value of fixed properties. Regression-tested in both test files and
exercised by checkpoints 02/03/06.

## Requested follow-up: stationary labels and selection synchronization

Implemented in both Vue and React after the initial parity port:

- Direction watermarks stay outside the scrolling clue lists and fit the lane.
  Inactive labels inherit black/white theme text at 0.3 opacity.
- Clicking a grid input selects its current-direction word without moving focus.
- Perpendicular arrows select the new direction's word; parallel movement,
  typing and backspace select the destination word. The arrow handler no longer
  overwrites a moved selection with the source coordinates.
- Existing orange Across / blue Down highlight rules now follow that selection;
  browser checks verify grid highlight borders match watermark RGB values.

Verified commands (all exit 0):

- `node scripts/watermark-browser-check.mjs`: stationary pseudo-element geometry
  while Down clues scroll, plus inactive visibility in light and dark themes.
- `node scripts/grid-click-browser-check.mjs`: both apps match on click/re-click,
  direction switches, within-word movement, and a black-square boundary from
  Down 1 to Down 25 at (4,0). Checks exact settled colors/opacity with real CSS
  transitions enabled. Artifacts: `reports/grid-click/`.
- Desktop comparison: 15/15; movement comparison: 11/11; Jest: 11/11;
  Vitest: 22/22; production React build passed (322.42 kB, 101.12 kB gzip).

The interactive React checks use Vite on :5174, not a production Flask React
route (none is configured in the Python sources). Build success alone does not
verify deployment of the generated assets.

Filled-word automatic jumps remain unverified in the browser. The new targeted
check uses the fixture generated by the desktop comparison, so run that first.

## Visual-diff status (explicitly NOT zero)

Screenshot pixel differences are small but **non-zero** and are **not claimed
as solved**:

| checkpoint | differing pixels (1440×1000) |
| --- | --- |
| main board / interactions | 520–591 (≈0.036–0.041 %) |
| dark mode / cancel reload | 473 |
| modals | 118 |
| crossing-direction change | 419 |

These are the final desktop rerun values. Earlier runs and the separate movement
run differ; the visual residual is not deterministic or fully explained.

Measured facts (`reports/react-parity/main-board-geometry.json`): captured
text boxes include x-position and width differences of 1/128 px. These are
measurements, not proof of glyph rounding or an environment-only cause.
The harness passes on **DOM equality + < 0.1 % pixel difference** (pixelmatch
color threshold 0.1, default antialias handling), a tolerance explicitly
accepted for this verification pass. The cause remains **unproven**.
Zero-pixel parity was **not** achieved and is not asserted.

## Verified-behavior notes (quirks intentionally preserved)

- A cancelled reload (progress + confirm-Cancel) suppresses the load but does
  **not** revert the weekday select — verified identical in both running apps
  by direct probe (dialogs fired, select stayed `friday`, `localStorage`
  `selectedWeekday` = `friday` in both).
- Mini-cell click refocuses a cell without updating the stale active-clue
  highlight (kept, test-covered).
- `checksUsed` increments per check run; `clearChecks` does not reset
  `completedWords`; completed words hide their clues until the next puzzle.

## Not verified / remaining limitations

- **Live multiplayer**: mobile initial Socket.IO join is browser-verified;
  partner cell synchronization, QR flows and server-driven role swaps remain
  unverified end-to-end. Desktop comparison blocks sockets.
- **Offline/cache/error matrix**: load retries, cache-fill limits, backend
  completion checks under network failure — covered only at unit level.
- **Fireworks/celebration audio**, canvas animation timing: not compared.
- **Visual parity**: see the pixel-difference section above; sub-pixel text
  rasterization residual stands, unexplained.
- **Content gate**: `npm run scan:content` currently reports 8 violations
  (`xwordinfo`, `legacy-provider-route`) in `apps/react/src/behavior/desktop.js`,
  its test, and `vite.config.js`. The legacy Flask page is exempt by policy
  (`docs/content-scan.md`), but **the React app is not yet exempted or
  remediated** — unresolved debt, not a pass.

## Reproduce

```bash
make run                                   # Flask (Vue) on :5001
npm run dev --workspace @crossword/react-port   # Vite (React) on :5174
npm test --workspace @crossword/react-port      # behavior + differential suites
node scripts/react-browser-parity.mjs           # 15-checkpoint desktop comparison
PARITY_TRACE=movement node scripts/react-browser-parity.mjs # 11 movement states
node scripts/mobile-browser-parity.mjs          # 10 mobile viewport states
```

Artifacts: `reports/react-parity/` (fixture, per-state DOM JSON, PNGs,
diff PNGs, `results.json`, `main-board-geometry.json`).
