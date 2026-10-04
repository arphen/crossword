# 17. Render performance: keep the look, lose the lag

Status: plan, 4 October 2026. Nothing here has been implemented. The causes in
§2 are suspects from reading the code, not measurements; §3 measures them
first.

## 1. Goal and the one rule

The desktop solver (`apps/react`) looks right and now feels laggy: typing,
scrolling the clue lanes and solving words stutter. Make it smooth **without
changing how it looks**.

**The one rule: no visible change.** Do not touch colours, hue arcs,
lightness contours, spacing, sizes, timings that a person can see, or the
libido/remainder behaviour. If a change cannot be done without a visible
difference, stop and report it instead of doing it. Every step ends with the
screenshot comparison in §3.3.

Do not rewrite the board in canvas or WebGPU. That is §7, and it needs the
owner's approval first.

## 2. Suspects

Ordered by expected cost. File paths are relative to `apps/react/src/`.

| # | Suspect | Where | Why it costs |
| --- | --- | --- | --- |
| S1 | Live glass blur | `desktop.css`, the rule for `:is(#menu-top, .action-bar, #menu-bottom)` (`backdrop-filter: blur(14px) saturate(140%)`) | The browser re-blurs everything beneath these three panels whenever any of it repaints, which is every keystroke and every glow frame. |
| S2 | Animated backlight | `vision.css` section 10: `:is(.board-glow, .grid)` transitions four registered `--territory-*` properties over 900ms; `.board-glow` paints four `radial-gradient`s plus a mask; `.grid` paints a `conic-gradient` `border-image` | Each scroll of a clue lane restarts a 900ms transition. Every frame of it recomputes the corner colours and repaints a layer bigger than the board, at device pixel ratio. |
| S3 | Layout read after every render | `CrosswordView.jsx`, the territory `useEffect` (search `scheduleTerritory`), plus the effect right after it with **no dependency array** | After every render (every keystroke) it calls `getBoundingClientRect()` on every clue `li` in both lanes, which forces a synchronous layout. It also re-sets the custom properties even when they did not change. |
| S4 | Custom-property animations on the main thread | `vision.css`: `@keyframes clue-ignite` (animates `--glow-pulse`, used in three rules), `@keyframes solved-settle` (animates `--settle`, which drives an inset `box-shadow` on every solved cell for 1800ms) | Animating a registered property cannot run on the compositor. Every frame repaints the shadows and gradients that use it. |
| S5 | Whole-grid re-render | `CrosswordView.jsx`, the `grid.map(...)` that renders every cell through `gridCellProps`; the controller (`behavior/desktop.js`) calls `$forceUpdate()` | Each keystroke re-renders all 225 cells and both clue lists. This is probably small next to S1–S4, which is why it is gated behind measurement (§5). |

Not suspects; leave them alone:
- The two blurs in `celebration.css`, which only run during the finale.
- The lane smoke in `desktop.css` (`.clue-column[data-label=...]`), which is a plain gradient with no blur.

## 3. Measure before touching anything

### 3.1 Setup

```
make setup                      # once
make run                        # Flask on :5001, rebuilds React
```

Or use `npm --workspace @crossword/react-port run dev` against a running
backend. Use a 1440×1000 window, dark theme, a 15×15 puzzle.

### 3.2 Frame probe

Paste this into the browser console (or `page.evaluate` it from Playwright). It
records how long each frame takes during an interaction:

```js
window.__frames = [];
(function tick(last) {
  requestAnimationFrame(now => { window.__frames.push(now - last); tick(now); });
})(performance.now());
// ...interact...
const f = window.__frames.slice(2).sort((a, b) => a - b);
({ n: f.length, p50: f[f.length >> 1], p95: f[Math.floor(f.length * 0.95)], max: f.at(-1),
   over20: f.filter(x => x > 20).length });
```

Record these four scenarios, each starting from a fresh probe:

1. **Typing:** click a clue, type 10 letters quickly.
2. **Lane scroll:** scroll the Across lane top to bottom with the wheel over about 2 s.
3. **Solve:** type the last letter of a word so it solves and the settle glow plays.
4. **Idle:** do nothing for 3 s; this checks that nothing animates forever.

Write the numbers into a table in the PR description: p50, p95, max and the
count over 20 ms for each scenario.

If you have Chrome DevTools, also open the Performance panel and record
scenarios 1 and 2. Note how much time goes to "Recalculate Style", "Layout",
"Paint" and "Scripting". Turn on Rendering → Paint flashing and note what
flashes while typing.

A headless or GPU-less browser gives pessimistic numbers. Compare before and
after on the same machine, and never compare across machines.

### 3.3 Screenshot parity

Before the first change, take baseline screenshots at 1440×1000, deviceScaleFactor 2:

- dark theme and light theme
- with one word selected mid-entry
- with several words solved (the remainder notches visible)
- with the Across lane scrolled to the bottom (the backlight shifts)

After each step, retake the same shots and compare them. Any difference you
can see by eye is a failure. Tiny anti-aliasing noise is fine.

## 4. Phase 1: cheap fixes, one commit each

Do these in order. After each: run the probe for the affected scenario, retake
the screenshots, run the tests in §6, then commit. The commit message says
what changed and the before/after p95.

### 4.1 Glass without live blur (S1)

In `desktop.css`, replace `backdrop-filter` and `-webkit-backdrop-filter` on
`:is(#menu-top, .action-bar, #menu-bottom)` with `none`. Then make
`--glass` more opaque until the panels look as they did. It is defined in
`desktop.css` as `color-mix(in oklab, var(--react-panel) 76%, transparent)`:
raise the `76%` in steps (try `88%`, then `94%`) and compare screenshots. Do the same in light mode if `--glass`
is redefined there.

Acceptance: screenshots match by eye; typing p95 improves or stays the same.

### 4.2 Measure the lanes only when they can have changed (S3)

In `CrosswordView.jsx`:

1. Inside `publish`, skip `setProperty` when the new value equals the current
   one: read it with `getPropertyValue` and compare as strings.
2. Round the published rank to two decimals (`Math.round(v * 100) / 100`).
   The eye cannot see the difference, and fewer distinct values means fewer
   transitions restart.
3. Replace the no-dependency `useEffect(() => { scheduleTerritory.current(); })`
   with one that depends only on what can move rows without a scroll:
   `[completedWords.size]`. Check how `completedWords` is defined in this file
   and use its real size expression.

Acceptance: typing a letter no longer shows a "Layout" entry from this effect
in the Performance panel. The backlight still follows the lanes when you
scroll, and still updates when a check solves words.

### 4.3 Calmer backlight transitions (S2)

Keep the visuals; reduce how often and how much is repainted.

1. Add `will-change: transform` to `.board-glow` so it sits on its own
   compositor layer and its repaints don't spread to the board.
2. Re-run the lane-scroll probe. If p95 is still over 20 ms, shorten the four
   `--territory-*` transitions in `vision.css` from `900ms` to `600ms` and
   compare by eye. If the backlight now visibly snaps, revert to 900ms and
   write the numbers down for §7. That is the case for moving the light to a
   canvas.

Do not remove the transition, and do not change the gradient geometry.

### 4.4 Settle glow on the compositor (S4, solved-settle)

The settle glow is an inset `box-shadow` whose strength is
`58% * var(--settle)`, animated from 1 to 0 over 1800ms. Rebuild it so only
`opacity` animates:

1. Check that `.grid-cell::after` is unused (search `vision.css` and
   `desktop.css` for `grid-cell` rules with `::after`). If it is used, stop
   and report.
2. Give `.grid-cell[data-solved]` (same selector as today) an `::after`
   covering the cell (`position:absolute; inset:0; pointer-events:none;
   border-radius:inherit`) with the inset shadow at full strength,
   `58%` instead of `calc(58% * var(--settle))`.
3. Animate that pseudo-element's `opacity` from 1 to 0 over the same 1800ms
   and easing, and remove the `--settle` keyframes and box-shadow from the
   cell itself. Keep the `inset 0 1px 0 var(--cell-glint)` part on the cell.
4. Keep the reduced-motion rule working: search for `animation: none` near
   the `prefers-reduced-motion` block and make it also cover the new
   `::after`.

Acceptance: a solving word looks the same frame to frame (take a short
screen recording before and after). The solve-scenario p95 improves.

### 4.5 The ignite pulse (S4, clue-ignite)

`clue-ignite` animates `--glow-pulse` from 2 to 1 over 640ms. Three rules
multiply a glow alpha by it. Leave it as it is unless the Performance panel
shows its frames over 16 ms. If it does, apply the same overlay-and-opacity
pattern as 4.4. That is harder here, so report first and don't improvise.

### 4.6 Contain the lanes

Add `contain: layout paint;` to `#app.react-desktop-app :is(#across, #down)`
in `desktop.css`. Do not use `content-visibility`: the territory measurement
needs real row boxes.

Acceptance: the lanes still scroll and the last clues still clear the dock.

## 5. Phase 2: only if typing is still slow

Only if the typing p95 is still over 16 ms after Phase 1 **and** the
Performance panel shows "Scripting" (React) as the largest share:

- Extract the grid cell into a `React.memo` component whose props are plain
  values: the letter, the class string, the data attributes from
  `gridCellProps`, and the style variables. Compute them in the parent as
  today. The controller mutates state in place, so never pass `app` or a
  mutable object as a prop, or memo will show stale cells.
- Then verify by typing, checking, revealing, solving and switching
  direction: every cell must update exactly as before. Run the full Playwright
  suite.

If any cell goes stale, revert the memo. Correctness beats a few
milliseconds.

## 6. Tests and gates for every commit

```
npm --workspace @crossword/react-port test
npm run typecheck && npm run lint && npm run format:check
uv run --no-sync ruff check .
make build && make test        # the pre-push gate runs this too
```

The git hooks run most of these. Never use `--no-verify`. Before pushing,
`make build` must have run, because `tests/test_run_prod.py` serves the built
bundle. Never commit anything under `src/crossword/static/react/`; it is build
output and ignored.

Work on a fresh branch from `master`, one commit per step, one PR. The PR
description contains the §3.2 table before and after each step, and the
screenshot comparison.

## 7. Later, needs owner approval: a light canvas

Only consider this if Phase 1 leaves the backlight or notch glow
measurably janky (§4.3 numbers), or the owner wants richer light.

Keep letters, inputs, focus and clue lanes in the DOM. Move only the *light*
into one WebGL2 canvas behind the board, and optionally one above it with
`pointer-events: none`:

- the four corner backlights
- the notch glows and their spill
- the libido and remainder intensities
- the finale bursts

The canvas reads the same inputs the CSS reads today:

- `--territory-*` per lane
- `--remaining` and `--libido` on `#app`
- the solved words
- the ramp hues, via the same OKLCH maths in `vision.css` §0

It draws additive glows in a fragment shader. WebGL2 is enough; WebGPU adds
nothing at this scale and has weaker browser support. This is a separate
design task: write a short proposal first, and don't start it from this plan.
