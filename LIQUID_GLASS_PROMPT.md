# Agent Brief: Liquid Glass Refactor — Crossword React UI

You are refactoring the UI/UX, styling, and micro-interactions of a crossword
application. You have full technical agency over the presentation layer. Your
taste is trusted: make stylish, current (2026), restrained decisions — no
generic "AI slop" gradient-noise design, no decorative gimmicks. Every visual
choice must serve one of the goals below and must survive the verification
gates at the end of this brief.

## The product reality that drives every decision

Two people solve the puzzle together, out loud, at speed. One person has the
keyboard. The other reads clues aloud: *"34 Across — [answer]"*. The typist
must find entry 34 in the Across list in under a second and start typing.
This means:

- **The clue spine is priority #1.** Scannability of clue numbers is the single
  most important property of this UI. Every other aesthetic decision yields to
  it.
- The typist's eye lands on the number first, the clue second, the letter
  track third. Design for that order of attention.

## Baseline: the visual language you are evolving, not replacing

The app currently renders a dark theme with a **two-column zigzag layout per
lane** (Across left, Down right), a large vertical **ACROSS/DOWN watermark**
behind each lane's center, blue/orange direction colors, and bordered clue
cards. This language works. It was carefully built and it survived a revert
for a reason.

**The previous agent failed by replacing this language** — it flattened the
two-column zigzag into a single-column list, which destroyed the spine the
users loved. It was fully reverted. Do not repeat that. Your job is to deepen
and polish the existing language, not to redesign it.

Non-negotiable keeps:

- The **two-column zigzag** clue layout per lane stays. It is the spine.
- The **ACROSS/DOWN watermarks** stay, in the background, as orientation.
  They must remain visually quiet and never compete with clue text.
- The blue (Down) / orange (Across) directionality stays; slight palette
  variation is fine, a rebrand is not.
- The dark base stays. More depth and material richness is welcome.

## What to change (the actual brief)

1. **The state boxes are the first target.** The bordered boxes that surround
   each clue and each letter of the in-spine answer preview (the "two-way
   bound" ones showing the current answer state) read as artifacts of limited
   CSS, not as design. Replace them with something that serves the spine:
   quieter letter-track segments (e.g. soft underlines, tinted track slots, or
   whatever you decide is better) that show the same live answer state and the
   same per-letter check/crossing states, without boxing in either the clue
   text or the numbers. The current answer state, the green/red check states,
   and the intersection highlighting must all still work — restyle them, don't
   remove them.

2. **Spine emphasis and readability.** Pull more focus onto the central spine:
   the numbers should be instantly locatable anchors. Consider a stronger
   number treatment (weight, tabular figures, subtle badge or marker), the
   slight alternating offset already present pushed further if it helps
   scanning, and a clear visual spine line/binding per lane. Letter counts or
   word structure may be integrated subtly, but must never clutter the number
   anchor or shout over the clue text.

3. **Liquid glass depth.** Push the material toward smooth, layered,
   three-dimensional: translucent surfaces, 1px inner edge highlights, soft
   multi-layer shadows, tasteful `backdrop-filter: blur()` on the large
   surfaces only. **Never** apply blur or heavy filters per grid cell or per
   clue row — that is a battery and jank disaster. The grid cells especially
   must stay cheap.

4. **Check & reveal is the big moment.** When checking, the palette shifts to
   green (correct) / red (incorrect) with translucent glass tints. Make this
   feel great: a smooth color/state transition, a small tactile acknowledgment
   (e.g. a subtle scale pulse on entry or validation), and when check markers
   clear, let them **dissolve smoothly via opacity** — no layout jumps, no
   popping. When the puzzle completes, a fluid, elegant moment is welcome.

5. **Grid & selection.** Active cell gets a crisp 2px outline/glow in the
  active direction color; the shared word path gets a subtle tinted glass
  overlay; cell typography uses crisp monospace / tabular numerals and stays
  legible on the wide desktop solver at 1440×1000.

6. **Motion contract (hard constraint).** No infinite or looping CSS
   animations. CSS transitions run on `transform`, `opacity`, or `filter`
   only, 150–300ms, hardware-accompanied and non-blocking. Continuous or
   looping motion is allowed only in a canvas/GPU layer (such as the optional
   WebGPU glass layer) that renders on demand, pauses when the tab is hidden
   and goes static under `prefers-reduced-motion`. Respect
   `prefers-reduced-motion` everywhere. The app must feel fluid but never
   laggy or battery-hungry; when in doubt, cut the animation.

## Hard boundaries

- **Target is the React app** (`apps/react/src/`). The shelved Vue
  frontend (git history only) is out of scope: do **not** recreate
  `src/crossword/templates/newapp.html`, `src/crossword/static/main.js`,
  or any Vue-only assets. Note that `src/crossword/static/styles.css`
  is shared infrastructure — either scope your changes under a
  React-only wrapper (imported by `CrosswordView.jsx`, e.g. a dedicated
  stylesheet with a root scope class) or, if you must touch the shared
  sheet, verify after every change that unrelated pages are visually
  unchanged. When in doubt, prefer the React-scoped stylesheet.
- Preserve all puzzle logic and interaction behavior (selection, focus,
  keyboard handling, check/reveal scoring, completion persistence). This is a
  presentation refactor only.
- Read `AGENTS.md` and `docs/REPO_MAP.md` before touching anything. Respect
  the listed directory boundaries and the staged working tree: commit only the
  files you changed, never the user's unrelated staged work. Pre-commit hooks
  are strict — no `--no-verify`, no weakening checks.

## Verification gates (all must exit 0)

Run from the repo root:

- `npm --workspace @crossword/react-port test` (React behavior/render tests)
- `npm test -- --runInBand` (root Jest gate; currently zero suites)
- `npm run typecheck && npm run lint && npx prettier --check .`

Visual verification: serve the app (`make run` for the Flask backend on :5001,
plus `npm --workspace @crossword/react-port run dev` for the React dev server
on :5174, which proxies to it). Capture a full-page Playwright screenshot at
1440×1000 (dark scheme) as the desktop baseline and after each change. Compare
the wide composition — the spine layout, watermark orientation, and overall
language must remain recognizably the same app, only better. Do not consider
any slice done until tests and screenshots agree.

## Working discipline

- Work in small slices. Suggested order: (1) de-box the letter tracks and clue
  cards, (2) spine emphasis pass, (3) glass depth/material pass, (4)
  check/reveal moment, (5) grid polish. Keep every slice green.
- Verify computed styles and rendered screenshots — never assume CSS landed.
- You have full design agency within this brief. Decide, verify, and show
  before/after screenshots in your summary. If a tradeoff forces you to choose
  between beauty and the spine's scannability, the spine wins.
