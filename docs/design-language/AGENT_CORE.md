# Afterglow: agent core (condensed)

A condensed extract of `DESIGN_LANGUAGE.md`, sized for agents with a small context window (about 12k tokens). It keeps the section numbers of the full guide, so "§6.4" here means the same thing there. Read this completely. Open the full guide only for the section you are working on.

**What this is.** A design language in which *what a thing is can be read from how it looks*: every item has a colour that is its name, the screen glows where something is still open, and finished things leave an afterglow. It scales from the whole composition (macro) down to a glyph's weight (nano).

**Files to copy into the project** (the `starter/` folder next to this file, tested in headless Chromium and under Playwright 1.55): `afterglow.css`, `view-settings.js`, `view-panel.js`, `territory.js`, `fit-contour.mjs`, `demo.html`; the test suite in `e2e/` (config, helpers, design and journey specs, `JOURNEYS.md`); `ui/audit-static.mjs`; and the CI workflows in `ci/`.

**Your acceptance test is `npm run design:check` plus a green `design-e2e` job in CI. Your first move is §16.1, not code.**

---

## 0. Instructions to the agent (read first)

You are being asked to give an existing application a distinctive visual language, not to "make it look nice". The language has one governing idea: **what a thing is should be legible from how it looks, and the screen should feel like it wants something.**

### 0.1 What you must do, in order

1. **Read this whole file.** Do not skim to the code. The code is meaningless without §3, §5 and §10.
2. **Fill in the Content Identity Brief (§16.2)** for the project you are in. Show it to the user. Wait for corrections.
3. **List the non-negotiable keeps (§16.3).** These are the existing things users already rely on. You evolve them; you do not replace them. A previous agent that flattened a well-loved layout was reverted entirely.
4. **Work in slices (§16.4).** Each slice is small, ends green (tests, lint, typecheck), and ends with a screenshot.
5. **Prove it with the test suite (§17).** Playwright journeys, design contracts and screenshots, in CI. Never assume CSS landed: in the source project, two stray `}` silently disabled a whole feature until a visual review caught it.
6. **Write the why-comments (§12.1).** Future agents, including weaker ones, learn the language from the comments you leave.
7. **Report only with the words DONE, INCOMPLETE or BLOCKED (§17.1).** DONE means `npm run design:check` exits 0 and CI is green. A list of remaining debt is INCOMPLETE: keep working. "No browser tooling" is BLOCKED or an install, never done.

### 0.2 Things you must never do

- Never invent a colour by hand-picking hex values per item. Colours come from the ramp (§6).
- Never add an animation that loops. (§9)
- Never put `backdrop-filter` on list rows, cells, cards in a grid, or anything repeated. (§7)
- Never use colour as decoration. If a hue does not name something, remove it. (R1)
- Never report the work as done while any gate is red, any core slice is missing, or any screenshot is unlooked-at. (R28, §17.1)
- Never skip or `fixme` a test, or run `--update-snapshots` blindly, to get green. (§17.6)
- Never rewrite the whole stylesheet in one pass. Never replace the existing layout. (R30)
- Never use `!important` to win an argument you could win with a token. (The source leans on it where later sheets override earlier ones, which is a cost of layering stylesheets, not a model to copy. Layer deliberately, or keep one sheet.)

### 0.3 If you are stuck or the project is unlike a crossword

You do not need a crossword. You need: **a set of N things that each have an identity (a number, a name, an index), arranged in two kinds (two poles), some of which are open and some of which are closed.** Almost everything is that: tasks (open/closed) in two lanes, files in two panes, log lines in two streams, notes in two categories, experiments in two arms. Map your project onto §16.2 and proceed. If it genuinely has no such structure, apply only §6 (colour), §7 (material), §9 (motion), §12 (why-comments), §17 (testing), and skip §10.

---

## 1. The 32 rules

Cite these by number in your commit messages (`applies R5, R14`). They are ordered by how often a weaker agent will break them.

### Identity and colour
- **R1. Colour is a name, not decoration.** Every hue must trace to a data value (a rank) and must appear in at least two places on screen.
- **R2. Assign colour by rank, not by value.** Sort the distinct identities, divide by (count − 1), get 0..1. A 70-item list and a 12-item list both reach both ends of the arc.
- **R3. Two poles own two halves of the hue wheel.** Never overlap. The source gives its first pole OKLCH hues 2°→142° (warm) and its second 183°→323° (cool).
- **R4. Pole is value, item is hue, interaction is saturation.** The pole an item belongs to lifts or lowers *lightness*. The item's identity is the *hue*. Interaction (rest, hover, working, cursor) spends *chroma* and light.
- **R5. Legibility is lightness alone.** Hold lightness constant across a highlighted group and fade *chroma* with distance instead.
- **R6. Use OKLCH, and fit a contour.** One lightness per arc clips the tight hues. Use the quadratic offset `l0 + l1·r + l2·r²` (§6.3).
- **R7. Verdict colours are reserved and win.** Right/wrong (green/red) override selection, including the cursor, and they paint with a fill, an ink and no glow.

### Material and ground
- **R8. Figure is lighter than ground.** The surface where work happens is the lightest surface on screen. In the source it is a step above the panel *and* the bezel around it.
- **R9. Matte at rest.** A 1px top glint, a seam darker than the surface, no blur.
- **R10. Glass only on a few large floating instruments.** Never per item. (§7.3)
- **R11. A ground casts no shadow.** Only things that sit above something cast one.
- **R12. One radius system.** Inner radius = panel radius − padding. The data lattice itself is square.

### Light and motion
- **R13. Keep a light budget.** At rest an item carries an *ember* (about 14% alpha, mostly inside its border). The thing being worked carries a *flame*. One cursor is the deepest, strongest element. (§9.2)
- **R14. Nothing loops.** Every animation is finite: 60–260 ms for feedback, 640 ms for ignition, ≤1.8 s for afterglow, ≤3.2 s for celebration.
- **R15. Animate `transform`, `opacity`, `filter`, or a registered custom property that only feeds a `box-shadow`/gradient.** Never animate layout properties.
- **R16. Same event, same animation name.** If moving a cursor along a lit word must not re-light it, give the cursor and the word the *same* `animation-name`; the browser then does not restart it.
- **R17. Reduced motion removes motion, not light.** The state stays; only the transition goes.
- **R18. Every light has a low-bloom tier.** Dim and Veil take the glow away and keep structure and hue.

### Scales and settings
- **R19. Four scales: macro, mini, micro, nano.** Each answers a different question (§5). A setting lives on exactly one scale.
- **R20. Settings are `data-*` attributes on the root. CSS owns appearance; JS owns state.** JS never writes a colour, size or shadow into a style (it may publish unitless numbers like `--rank`).
- **R21. A stored choice beats a media hint; unknown stored values fall back.** Never trust storage.
- **R22. Every setting is undoable by a single Reset.**

### Desire and honesty
- **R23. A screen has one visible desire.** What is *open* emits light; what is *closed* recedes and leaves a small remainder. (§10)
- **R24. Light is conserved.** What a closed thing gives up flows to what is still open.
- **R25. Help has a cost, and the cost is visible and honest.** Checks and reveals drain the charge. Never quietly change the object the user is wrestling with.
- **R26. Every mark is checked by a crossing.** A decoration that answers to nothing else on screen is an unchecked cell. Delete it, or give it a second place to appear.
- **R27. Hue never says anything the reader must unlearn.** The same rank is the same hue everywhere, in every state, in every theme.

### Proof and process
- **R28. Prove it.** Done means the static audit passes, the Playwright suite (every journey, every design contract, every screenshot) is green locally and in CI, and every changed screenshot was looked at. "Cannot verify" is BLOCKED; a debt list is INCOMPLETE. Neither is done. (§17)
- **R29. Comment the *why*:** intent, the rejected alternative, and the measured number.
- **R30. Evolve, don't replace.** List the keeps before you touch anything.
- **R31. Verify computed styles and screenshots.** If you did not measure it, it did not land.
- **R32. Work in slices.** Every slice ends green with a screenshot.

---

## 2. Cheat sheet: the numbers

Copy these; do not invent new ones until the language is working.

| Thing | Value | Notes |
| --- | --- | --- |
| Dark ground | `#0c1015` | panel `#1a2027`, panel-light `#252b33`, panel edge `#3a414b` |
| Work surface ("paper") | `#343a45` | grout (seam) `#1e232a`, well (black cell) `#0d1218`, bezel `#151b21` |
| Ink / muted | `#f2f2f6` / `#aeb6c2` | |
| Poles | warm `#ffad32`, cool `#8dc7ff` | verdicts: ok `#8fe4b1`, bad `#ff9c9c` |
| Light ground | `#f3f3ef` | paper `#fdfdf9`, ink `#263430`, poles `#995c10` / `#306b9e` |
| Ramp arcs (OKLCH hue °) | pole A 2→142, pole B 183→323 | full sweep 46→332 is used only by confetti and the finale rule; the progress bar runs both arcs end to end |
| Ramp lightness / chroma | 0.82 / 0.14 (dark), 0.42 / 0.12 (light) | |
| Pole as value | A **+0.07**, B **−0.07** lightness | highlight split: A **+0.11**, B **−0.10** |
| Interaction as chroma | ember ×0.7, flame ×1.75 | alphas: ember 14%, hover/cross 22%, flame 34%, cursor 46%, halo 18% |
| Vibrance dial | soft c 0.095 · vivid 0.14 · bold 0.18 | alphas scale with it (§14.1) |
| Lit group (dark) | L 0.84 (A) / 0.75 (B), chroma 0.105, far-end floor 18% | ink L 0.25 c 0.055; cursor L 0.57 / 0.50, c 0.15 |
| Backlight | 36% dark · 14% light · 20% dim · 12% veil | glow chroma ×1.3; edge light 85% |
| Easing | `cubic-bezier(0.22, 1, 0.36, 1)` | one curve for all controls |
| Durations | quick **140 ms**, settle **260 ms** | press 60 ms; letter arrives 160 ms; focus ring 180 ms |
| Ignition | **640 ms**, `cubic-bezier(.2,.7,.2,1)` | `--glow-pulse` 2→1, once |
| Afterglow | **1800 ms** settle; **900 ms** territory drift; **1100/900 ms** notch contraction | |
| Hover / press | lift `translateY(-1px)`; press `scale(0.97)` (icons 0.94) | |
| Glass | `blur(14px) saturate(140%)`, 76% panel tint, 1px edge at 10% ink | masthead, dock, notes only |
| Chip | 42×32, radius 8, 1.12rem bold tabular | |
| Row | min-height 100px; ladder offset ±25px | the zig-zag |
| Letter track cell | 25px square, seams 1px, major seam 2px, word tear 9px | runs ≤5, balanced (11 → 4/4/3) |
| Light budget | spill gone by the 3rd square; sparks flat, never glowing | |
| Celebration tiers | 0 none · 1 green lift · 2 sparks · 3 sparks+note · 4 wash · 5 clean sweep | |

---

## Excerpts from §3 to §12 (same numbers as the full guide)

### 3.2 The five channels

Use each visual channel for exactly one kind of meaning. Never overload one, and never let two channels say the same thing.

| Channel | Carries | Example in the source | Never use it for |
| --- | --- | --- | --- |
| **Hue** | which item (identity, by rank) | clue 34's yellow-green, everywhere | state, category, importance |
| **Lightness** | which pole/direction, and legibility | Across brighter, Down quieter | identity |
| **Chroma / light** | interaction (rest → hover → working → cursor) | ember → flame → halo | identity |
| **Position & distance** | place within a group | chroma fades along a lit word; light spills 3 squares from the notch | emphasis |
| **Form (notch, seam, tick)** | the *address*: where something begins or opens | gate ticks on black squares, torn strips, major seams every 5 | colour |

If a screen of yours needs a sixth channel, you are probably encoding something that does not need encoding.

### 3.3 Learn once, find everywhere

- One rank per distinct identity, **shared by every lane that shows it** (a number that exists in both lists wears each pole's hue in turn; a number that exists in one list keeps one fixed colour).
- The rank travels as a unitless `--rank` (0..1) published on **every element that wears the colour**: row, chip, track boxes, grid square. CSS custom properties are substituted where they are *declared*, so each element must compute its own hue where that hue is shown.
- Colour is computed in CSS, not JS. JS names the rank; CSS owns the palette, the themes, and the dim tiers.

### 5.1 One question per scale

| Scale | Question it answers | Who owns it | Where it lives | Examples in the source |
| --- | --- | --- | --- | --- |
| **Macro** | *What is the scene, and what is ground vs figure?* | The designer | Layout, composition, ambient light | The grid is the ground; lanes lie over its edge as light smoke; masthead and dock float as glass; four-corner backlight; lane watermarks; one charge of light over the whole board |
| **Mini** | *Is this comfortable on my eyes and my screen?* | The reader (a dial) | `data-luma`, `data-scale` | Brightness: Standard / Dim / Veil. Board size: S / M / L |
| **Micro** | *Do I want the reading aids?* | The reader (a dial) | `data-ramp`, `data-vibrance`, `data-grouping`, `data-rail` | Number colours on/off, colour intensity Soft / Vivid / Bold, letter track grouping Words / 5s / Solid, clue rail on/off |
| **Nano** | *Do I want the finest cues?* | The reader (a dial) | `data-cues`, `data-glyph` | Square notches on/off, letter weight Regular / Firm |

**Progressive disclosure is the point.** A reader can stop at Mini and never see the rest. Smaller scales are smaller *surfaces*: Mini changes the whole screen's comfort; Nano changes the weight of a glyph.

### 5.2 Rules for placing a change

1. **Start at macro.** If the composition is wrong, no dial will fix it. Decide ground, figure and instruments first. (§7.2)
2. **A mini setting changes tokens, not structure.** Brightness changes `--ink`, `--paper`, and the bloom alphas. It never moves anything.
3. **A micro setting changes what is *added* to the structure.** Turning number colours Off "keeps the structure and drops the pigment, so the option is usable by readers who only want the rails".
4. **A nano setting changes marks smaller than an item.** Notches, ticks, glyph weight.
5. **Every dial has an Off or lowest state that remains usable.** Ramp off = rails only. Cues off = plain squares.
6. **Dials compose.** The cursor must remain readable at Dim + Soft + Compact + Cues Off. Test the corners of the matrix, not only the default.
7. **Never add a fifth scale.** If something does not fit, it is probably two settings or no setting.

### 5.3 The data-attribute contract (R20)

The whole contract between JS and CSS is a flat set of attributes on the app root:

```html
<div class="afterglow"
     data-luma="standard"      <!-- mini  -->
     data-scale="normal"       <!-- mini  -->
     data-ramp="on"            <!-- micro -->
     data-vibrance="vivid"     <!-- micro -->
     data-rail="on"            <!-- micro -->
     data-cues="on"            <!-- nano  -->
     data-glyph="regular"      <!-- nano  -->
     data-direction="across"   <!-- state: which pole is being worked -->
     data-glow="on">           <!-- state: best-effort glow gate -->
```

- JS normalises, persists and publishes. CSS keys off the attributes. See `view-settings.js` in §14.2.
- Booleans become `on`/`off`.
- **First-visit defaults come from media queries**: `prefers-contrast: less` or `prefers-reduced-transparency: reduce` selects Dim, because displays that bloom or wash out are usually reported that way. A stored choice always beats the hint (R21).
- Use `data-theme="light"` on the root for the light theme. (The source uses `:root[style*="color-scheme: light"]`, which is a workaround. Do not copy it.)

### 6.1 The ramp

1. **Rank.** Collect distinct identities, sort, rank = index / (count − 1). Rounded to 3 decimals. (§14.2 `createRamp`.) Rank, not value: a 70-item puzzle still reaches both ends of the arc. Shared identities share a rank.
2. **Arc.** Each pole gets half of the OKLCH hue wheel: pole A 2→142 (pink → orange → yellow → green), pole B 183→323 (teal → blue → violet → magenta). The arcs never overlap.
3. **Hue** = `arcStart + rank × (arcEnd − arcStart)`.
4. **Pole lightness.** Pole A = base + 0.07, pole B = base − 0.07. *Direction reads as value, never as a second hue.*
5. **Contour** (next section) adds a per-rank lightness offset.
6. **Colour** = `oklch(L C hue)` with base L 0.82 and C 0.14 on a dark ground; L 0.42 and C 0.12 on paper.

### 6.3 The contour

Each arc carries a small per-rank lightness offset `l0 + l1·r + l2·r²`. It lowers the tight hues just enough for the ramp chroma to fit in sRGB and lifts the generous ones back.

| Theme | Pole A (warm) | Pole B (cool) |
| --- | --- | --- |
| Dark | l0 −0.115, l1 0, l2 0.105 | l0 0.035, l1 −0.24, l2 0.24 |
| Light | l0 −0.02, l1 0.44, l2 −0.44 | l0 0.23, l1 −0.36, l2 0.18 |

On paper the narrow places move: yellows and cyans hold colour only when *lifted*, so pole A bulges through its yellow middle and pole B starts high in cyan and settles toward violet.

**If you change the arcs, the chroma or the base lightness**, run `fit-contour.mjs` (§14.3) for a first draft and then judge by eye. Check the ramp on a strip of 12 chips in both themes.

### 6.4 Interaction as saturation: ember, flame, halo

Three lights, one hue:

| Light | Meaning | How it is made | Alpha |
| --- | --- | --- | --- |
| **Ember** | an item at rest | same hue, chroma × 0.7, light mostly *inside* the border | 14% |
| **Hover / cross** | attention, or a crossing item | ember at higher alpha; for a crossing item the chip *fills* with its flame at 26% | 22% |
| **Flame** | the item being worked | same hue, chroma × 1.75, solid fill on the chip, inner glow | 34% |
| **Cursor** | where you type | the deepest, most saturated square, pale lettering, ringed in the word's light | 46% |
| **Halo** | *names the pole*, not the item | the pole's own colour, outside the border | 18% |

So: **the flame names the item, the halo names the pole.** Inside says *which*, outside says *which side*.

The resting light lives mostly *inside* the border. Tracks sit 3px apart with text 10px above; positioned boxes paint over static text, so an outer bloom at rest would smear both.

### 6.5 The lit group: constant lightness, fading chroma (R5)

*Whether a letter can be read is a question of lightness alone. Hue never helps or hurts.*

- A highlighted run of cells (the active word) holds **one lightness** from first cell to last: L 0.84 for pole A, 0.75 for pole B.
- It spends its *position fade in chroma*: the first cell wears the colour at full strength (chroma 0.105), the last wears the same hue at 18% of it.
- The ink is the word's own hue taken deep: `oklch(0.25 0.055 hue)`. One ink reads at every position.
- The **cursor** is the one deep square: `oklch(0.57 0.15 hue)` (A) or `0.50` (B) under `oklch(0.98 0.012 hue)` lettering, ringed in `oklch(L+0.06 …)`.
- The earlier version faded lightness from a light tint to a dark fill, and the lettering's contrast fell from about 10:1 to 2.7:1 along every word.

### 9.1 The motion contract

1. **Nothing loops.** The earliest version ran eight infinite `box-shadow` pulses (2.9 s and 2.1 s periods that drifted in and out of phase) repainting blurred shadows every frame while the reader was only reading. Removed.
2. **Nothing moves while the reader is just reading.** Interaction causes motion; stillness causes none.
3. **Transform, opacity, filter; or a registered number that feeds a shadow/gradient.**
4. **Durations:** feedback 60–260 ms, ignition 640 ms, afterglow ≤1800 ms, drift 900 ms, celebration ≤3200 ms.
5. **One easing curve for all controls:** `cubic-bezier(0.22, 1, 0.36, 1)`.
6. **Reduced motion:** `animation: none; transition: none` for the whole tree, and *the light stays* (R17). Restate it next to the animations it governs so the contract lives with the code even if a blanket switch moves.
7. **No canvas.** The sparks are flat dots "so a bright screen has nothing to bloom".

### 9.2 The light budget

How much light each state may spend. "Quiet by design: dozens of answers carry it at once."

| State | Light |
| --- | --- |
| Rest | ember: chroma ×0.7, 14% alpha, mostly inside the border |
| Hover | the same hue at 22%; lift 1px |
| Crossing item | chip fills with its flame at 26%; track at half strength |
| Active item | flame 34% + halo 18%; ignites once |
| Lit squares | position-faded chroma; ink deep |
| Cursor | 46%; the single strongest element |
| Solved | flares once (58% of tint), rests as clean paper with a trace in the ink |
| Dim / Veil | ember and cross to 0%, flame to 11%, cursor 15%, halo 6% |

### 9.3 Ignition (a thing lights once)

```css
@property --glow-pulse { syntax: '<number>'; inherits: true; initial-value: 1; }
@keyframes ignite { from { --glow-pulse: 2; } to { --glow-pulse: 1; } }
.is-selected > .chip {
  box-shadow: inset 0 0 7px color-mix(in oklab, var(--flame) calc(var(--flame-alpha) * var(--glow-pulse, 1)), transparent);
  animation: ignite 640ms cubic-bezier(0.2, 0.7, 0.2, 1) both;
}
```

- The light flares once (640 ms) as a word lights, then settles to its resting light.
- **Nothing translates.** Only the glow's alpha moves. "Reading and clicking stay perfectly still."
- Lit squares, the cursor and the selected chip **share the animation name** (R16): moving the cursor along the word re-lights nothing, so typing stays calm. The letters carry their own arrival.
- Without `@property` support the fallback is `--glow-pulse: 1` (no flare, full light).

### 10.1 The model

- A **notch** is the open address of something not yet done. It emits a short, specific filament of light, in that item's own hue, on the edge where it opens.
- The board holds **one charge** of light and shares it among the notches still open.
- **At the start** the charge is spread thin over every notch and the short spills overlap into a soft, smudged board.
- **Each closure** puts its notch out (it contracts to a point), the cell flares once as it settles, and "the charge a word gave up flows into the notches still open".
- **At the end** "the board clears from smudge into a few intense lights, and the last notch carries nearly all of it".
- **Help drains the whole charge.** Every check and reveal lowers the score and dims *every light at once, backlight included*: "the board loses its desire along with the points".

### 12.1 The why-comment

The source's stylesheets carry long comments that read like design notes. They are why a later agent could extend the language without breaking it. **Write them.** Every non-obvious rule gets a comment with three parts:

1. **Intent**: what the reader should experience.
2. **The rejected alternative**: what you tried or considered and why it failed.
3. **The measured number**: the contrast ratio, OKLab L, px, ms or percentage that justifies the value.

Template:

```css
/* <What it is, in the reader's terms.>
   <Why it is this way: the failed attempt, and what it did to the reader.>
   <The number: "L 0.35 vs 0.33", "28% not 55%", "640ms once".> */
```

Section banners (the source's format):

```css
/* ==========================================================================
   N. Title in plain words.
   Two to six sentences: the problem, the idea, the constraints it must honour
   (performance, themes, reduced motion), what it deliberately does NOT do.
   ========================================================================== */
```

Also: the **file header** names what it keeps intact ("Kept intact: the two-column zigzag, the watermarks, blue/orange, matte surfaces") and states the motion contract once.

---

## §16 Applying it to a new project (excerpt)

### 16.1 Kickoff protocol (paste this to your local agent)

> Read `docs/DESIGN_LANGUAGE.md` in full before doing anything.
>
> **Your acceptance test is `npm run design:check` plus a green `design-e2e` job in CI (guide 17).** You are not finished until both pass. Do not stop to report progress, ask whether to continue, or summarise "remaining debt": that is your to-do list, so keep going. Report only with the words DONE, INCOMPLETE or BLOCKED (guide 17.1).
>
> Do exactly this, in order:
>
> 1. Fill in the **Content Identity Brief** (§16.2) for this project. No code. Show it to me and wait.
> 2. List the **non-negotiable keeps** (§16.3) and the **journey inventory** (§17.3, `JOURNEYS.md`). Show both.
> 3. Set up Playwright and the suite from §17.13 (install the browser; if that is impossible, report BLOCKED with the error). Generate baselines **before** changing any styling, so there is a "before" for every journey.
> 4. Propose slices S1 to S10 (§16.4) for this codebase, naming the files each will touch. S1 to S6 are mandatory.
> 5. Work test-first, slice by slice: write or extend the failing tests, paste the red output into `design-evidence.md`, implement until green, **open every changed screenshot and describe it**, commit with the rule numbers (`applies R4, R14`). Do not combine slices. Do not invent colours; use the ramp. Nothing loops.
> 6. If anything in the guide conflicts with an existing product behaviour, ask me. Skipping a skippable slice needs my written approval.

### 16.2 The Content Identity Brief (fill every field)

```
PROJECT: <one sentence: what is it for, and who uses it, in what posture?>

1. ITEMS      What are the N things that have identities? How is each identified
              (number, name, id)? Typical N? Max N?
2. POLES      What are the two kinds (A/B)? What distinguishes them in the user's mind?
3. STATES     What states can an item be in? What is "open"? What is "closed"?
              Is there a finishing event for the whole?
4. ADDRESSES  Where does an item *begin* or *open*? (these become notches/ticks)
5. CROSSINGS  Name at least 3 places where the same item appears on screen twice
              (list + detail, list + map, row + minimap...). These carry the colour.
6. HELP       What help/shortcut/auto-fix exists? What should it cost? What is the
              honest verdict state?
7. GLANCED    The two numbers a user glances at while working (these go in the masthead).
8. GROUND     What is the ground (the surface everything else stands on)?
9. FIGURE     What is the work surface (must be the lightest surface)?
10. INSTRUMENTS  What floats over it (top/bottom)? (≤ 4 glass surfaces)
11. SCALES    macro: composition decisions.  mini: which comfort dials?
              micro: which reading aids?  nano: which fine cues?
12. KEEPS     Non-negotiable existing things (see §16.3).
13. JOURNEYS   Every user journey, by the checklist in §17.3 (routes, modals, data states,
              settings that persist, success/abandon/failure paths). This becomes JOURNEYS.md.
14. RISK      Where could this language fail here? (e.g. N = 3, or N = 10,000.)
```

**Sizing check.** The ramp wants N from about 8 to a few hundred. At N < 6 use fewer, bolder anchor hues (skip the contour). At N in the thousands, rank *visible groups* (a section, a page), not items.

### 16.3 Non-negotiable keeps and the agent brief

Before changing anything, write a "keeps" list: every layout, colour, interaction and behaviour that works. The source's brief for a redesign said it plainly: *"This language works. It was carefully built and it survived a revert for a reason… Your job is to deepen and polish the existing language, not to redesign it."* A good brief has these sections; reuse the skeleton:

1. **The product reality that drives every decision.** One paragraph: who uses it, how, at what speed. Name the single most important property ("the clue spine is priority #1; scannability of numbers; if a trade-off forces beauty vs scannability, scannability wins").
2. **Baseline: the language you are evolving, not replacing.** What stays: layout, accents, base.
3. **What to change.** Numbered, each with a *why* and a *what must still work*.
4. **Motion contract (hard).** No loops, no canvas, transform/opacity/filter, 150–300 ms, reduced motion.
5. **Hard boundaries.** Directories and behaviours not to touch; "presentation only, preserve all interaction behaviour".
6. **Verification gates.** The exact commands that must exit 0; the screenshot size.
7. **Working discipline.** Small slices, each green; verify computed styles and screenshots; "when in doubt, cut the animation".

### 16.4 Slices (in this order; each is test-first, ends green, and is looked at)

**Core slices are mandatory: S1 to S6.** S7 and S8 are required unless the brief records why the project has no open/closed items or no finishing event *and* the user approves in writing (`--skip economy="..."`, §17.8). Surface-by-surface polish (landing screens, modals, emoji) comes **after** the core, never instead of it.

| Slice | Do | Acceptance (all are executable) |
| --- | --- | --- |
| **S0** | Brief, keeps, `JOURNEYS.md`, Playwright set up, baselines made **before** any styling change. No styling. | `design:check` runs; the audit's red checks are listed. |
| **S1 Tokens** | Add the token block (§14.1 section 0) and the light theme; map existing surface colours onto them. | Audit: `tokens`, `registered-glow`. Suite green; baselines show no unintended change. |
| **S2 Material** | Figure/ground by lightness; seams; 1px glints; matte controls; glass on ≤ 4 floating instruments. | Audit and probe: `glass-budget`. |
| **S3 Identity** (core) | Publish `--rank`; ramp; contour; wearers coloured; ember at rest. | Audit: `identity-ramp`. Probes: `identity-*`, `contrast`. |
| **S4 Interaction** (core) | Flame, halo, ignition; hover/press/arrive; cursor; verdict colours. | Audit: `no-infinite`, `reduced-motion`. Probe: `no-infinite-animations`; test `[D3]`. |
| **S5 View settings** (core) | `data-*` contract, mini/micro/nano **panel UI**, persistence, low-bloom tiers, media hints. | Audit: `view-tiers`. Probe: `low-bloom-tier`. The `[D1]` matrix and a "setting persists after reload" journey. |
| **S6 Territory** (core) | Four-corner backlight; conic edge; scroll publishing. | Audit: `territory`. A journey that scrolls and asserts the corner ranks change. |
| **S7 Economy** | Notches, charge, remainder. | Audit: `economy` (or an approved skip). A journey that closes an item and asserts its notch contracts. |
| **S8 Celebration** | Tiers, note, finale from the last notch. | Audit: `celebration` (or an approved skip). A journey that reaches the finish. |
| **S9 Comments** | Why-comments and section banners (§12.1). | Every non-obvious rule has intent, rejected alternative and number. |
| **S10 Final** | Anti-slop checklist (§18); evidence ledger complete; CI green. | `design:check` exits 0; `design-e2e` green on the branch head; status DONE. |

### 16.5 Verification

Verification is §17: Playwright journeys, design contracts, screenshots and CI, with a static audit in front. Nothing in this guide counts as verified until `npm run design:check` exits 0 and the CI job is green. Read §17.1 before you report anything.

### 16.6 If the agent stalls, or goes off the rails

| Symptom | Say this |
| --- | --- |
| It starts coding immediately | "Stop. Show me the filled §16.2 brief first. No code." |
| It reports "Done" with a list of remaining debt | "That is INCOMPLETE. The list is your to-do list. Run `npm run design:check`, quote the failing checks, and continue until it exits 0." |
| It says it has no browser tooling | "That is an install or BLOCKED, never done. Run `npm i -D @playwright/test && npx playwright install chromium`. If it fails, report BLOCKED with the exact error." |
| It cites a pre-existing failure (formatter, lint, tests) | "Prove it on a clean checkout, then make every file you touched pass. Format untouched-but-unformatted files in their own earlier commit." |
| It did a cosmetic screen first and left S3, S5, S6 | "Core before cosmetic. Do S3, then S5, then S6. The audit stays red until they exist." |
| It rewrites everything | "Revert to the last green commit. Do only slice S<n>. List the files you will touch before touching them." |
| It invents hex colours | "Which rank is that colour? Show me the `--rank` and the ramp it came from, or delete it. (R1, R6)" |
| It adds a pulsing glow | "Nothing loops. Make it ignite once (§9.3). (R14)" |
| It adds blur to cards | "Blur only on ≤ 4 large floating instruments. (R10)" |
| It claims success | "Show the `design:check` output, the CI run, and the ledger entry for each changed screenshot. (R28)" |
| It ran `--update-snapshots` to get green | "Revert the baselines. Update only the affected tests, open every changed image, and describe each in the ledger (§17.6)." |
| It stalls on ambiguity | "Pick the option the guide's §3 prefers; record the choice in a comment with the rejected alternative. (R29)" |
| It forgets the guide | "Quote the rule numbers you are applying in this commit message." |
| It stops early for any reason | "Status? Quote the last `design:check` output and the failing check names, then continue." |

---

## §17 UI testing (excerpt)

### 17.1 The contract (read this twice)

The work is **finished** only when the acceptance command exits 0 *and* CI is green on the branch. Until then the status is one of three words, and the agent must use exactly these:

```
STATUS: DONE | INCOMPLETE | BLOCKED

DONE        every one of these is true:
            1. `npm run design:check` exits 0 locally (static audit + the whole Playwright suite)
            2. the CI job `design-e2e` is green on the head commit of the branch
            3. every SKIP the audit printed carries a reason the user has approved in writing
            4. every changed screenshot was opened and described in the evidence ledger (17.9)
INCOMPLETE  anything else. Keep working. A list of "remaining debt" means INCOMPLETE.
BLOCKED     you need a human decision or an environment you cannot obtain. Say exactly which,
            with the exact error or the exact question.
```

What this rules out, because each of these has already happened:

- **"Done" followed by a debt list.** The debt list is the to-do list. Do it.
- **"No browser tooling here, so no screenshots."** There is always a way: `npm i -D @playwright/test && npx playwright install chromium`. If that is truly impossible (no network), the status is BLOCKED, with the error, and the agent stops. It does not proceed without evidence. (17.10)
- **"That check was already failing at HEAD."** Prove it on a clean checkout (`git stash`), then still make the files *you touched* pass. If a file was unformatted before you came, format it in its own preceding commit so your diff stays reviewable.
- **Skipping the core slices.** S3 (identity ramp on content), S5 (View settings including the panel UI) and S6 (territory) are what the language *is*. A cosmetic pass over a landing screen or a modal is not a substitute, and must come after them.
- **Skipping tests to get green.** `test.skip`, `test.fixme`, `test.only` and `--update-snapshots` run blindly are all failures (17.6, 17.8).

### 17.2 What gets built

| Piece | File | Job |
| --- | --- | --- |
| Runner config | `e2e/playwright.config.mjs` | projects = viewport × theme; screenshot settings; CI behaviour; web server |
| The only project-specific file | `e2e/design.config.mjs` | your selectors, tokens, thresholds |
| Helpers | `e2e/design-helpers.mjs` | console guard on every test; `applyView`; `settle`; the design probes as assertions |
| Design contracts | `e2e/design.spec.mjs` | view matrix (brightness × intensity), keyboard focus, reduced motion; each with a screenshot |
| User journeys | `e2e/journeys.spec.mjs` | one test per journey, titled `[J1] ...`, each ending in a screenshot |
| Journey inventory | `e2e/JOURNEYS.md` | the complete list of what a user can do |
| Static audit | `ui/audit-static.mjs` | source rules + "every journey is tested, with screenshots, in CI" |
| CI | `ci/design-e2e.yml`, `ci/update-screenshots.yml` | run it on every PR; upload the report |

The whole thing is verified at the browser level, so it works for any framework (Vue, React, Svelte, plain HTML).

**One command.** In `package.json`:

```json
"design:check": "node <<tests/design>>/audit-static.mjs --src src --e2e-dir <<tests/e2e>> && playwright test -c <<tests/e2e>>/playwright.config.mjs"
```

### 17.3 The journey inventory (all user journeys)

`JOURNEYS.md` is the source of truth for coverage. Every row `| J<n> |` must have a Playwright test whose title contains `[J<n>]`, and every `[J<n>]` tag in a test must have a row. The audit fails on a gap in either direction.

Build the inventory by doing **all** of these before declaring it complete:

1. Every route or page in the router.
2. Every `data-testid`, button, link and form in the templates.
3. Every modal, drawer, menu, toast and tooltip, opened *and* dismissed.
4. Every data state of every screen: **loading, empty, one item, many items, error, offline**.
5. First run vs returning user; signed out vs signed in; permission denied.
6. Every setting a user can change, and that it **persists after a reload**.
7. The success path, the abandon path and the failure path of each task.
8. Destructive actions and their confirmations.
9. Any multi-step flow, with a screenshot at each *beat* (use `test.step`), not only at the end.

Each journey test runs once per Playwright project, so a journey is automatically captured at **desktop/dark, desktop/light and phone/dark**. Name screenshots after the beat: `j2-selected.png`, `j3-panel-dim.png`.

Design contracts get ids `D1…` and are not journeys. They are checked on every project too.

### 17.4 Screenshots that do not flake

A screenshot test that flakes gets disabled, and then there is no test. Rules:

1. **Generate baselines in the same environment CI uses (Linux).** Fonts and anti-aliasing differ per OS, so a baseline made on a Mac fails in CI. Use the `update-screenshots` workflow, or locally:
   `docker run --rm -v "$PWD":/work -w /work mcr.microsoft.com/playwright:v1.55.0-noble npx playwright test --update-snapshots` (match the tag to your `@playwright/test` version, and **pin that version**).
2. **Finite animations are fast-forwarded** to their end state (`animations: 'disabled'`). That is why the language's rule "nothing loops" matters twice: infinite animations are cancelled in screenshots, and the design probe fails if any exist.
3. **Never `sleep`.** Wait for a condition: `settle(page)` waits until every finite animation and transition has finished; `expect.poll` and web-first assertions do the rest.
4. **Control the data.** Seed random generators, freeze time (`page.clock.install({ time })`), use fixed fixtures or a seeded backend, and `mask` anything that is genuinely dynamic (`toHaveScreenshot({ mask: [page.locator('.timestamp')] })`).
5. **Tighten the pixel tolerance.** Playwright's default per-pixel `threshold` (0.2) waved through a visible recolour of the tiles in this guide's own mutation test. The config sets `threshold: 0.05` with `maxDiffPixelRatio: 0.002`. It stayed stable across repeated runs in one environment, and it failed a 29,176-pixel recolour.
6. **One baseline per project**: viewport × theme. The path template is `__screenshots__/{projectName}/{testFilePath}/{arg}.png`. **Commit the PNGs.** The audit fails if there are fewer baselines than journeys.
7. **Screenshot what matters.** Viewport screenshots for composition; element screenshots (`locator.toHaveScreenshot`) for a component's states. Do not full-page a long scrolling list.

### 17.6 Updating baselines (never blindly)

`--update-snapshots` overwrites the evidence. The protocol:

1. Run the suite. Read every failure. A screenshot diff is either a **bug** (fix the code) or an **intended change** (update the baseline).
2. For an intended change, update only the affected tests: `npx playwright test -g "J3" --update-snapshots`, not the whole suite.
3. **Open every changed image** (and the diff in `playwright-report`). Describe each in one sentence in the ledger: what changed and why that is intended. A weaker agent that cannot view images must say so, and the user reviews the diffs.
4. Commit the new PNGs in the *same* commit as the code that changed them, so review shows both.
5. Never run a blanket `--update-snapshots` to turn a red run green.

### 17.8 The static audit (`audit-static.mjs`)

Fast, no browser, runs first in CI. **Core checks fail until the slice exists**, which makes it the to-do list for S3–S8:

| Check | Fails until |
| --- | --- |
| `no-infinite`, `glass-budget`, `reduced-motion`, `tokens`, `registered-glow` | the foundations (S1, S2, S4) exist |
| `identity-ramp` | `--rank` is published on items *and* read by the ramp (S3) |
| `view-tiers` | `data-luma`/`data-vibrance` tiers exist in CSS, are published and persisted, a media hint picks the first-visit tier, **and a View panel UI is mounted** (S5) |
| `territory` | the corner ranks are registered and published (S6) |
| `economy`, `celebration` | S7, S8 exist, **or** are skipped with a written reason: `--skip economy="no open/closed items (brief 16.2 #3)"` |
| `e2e-playwright` | Playwright is a dependency with a config and specs |
| `e2e-journeys` | every journey row has a `[J<n>]` test and every tag has a row |
| `e2e-screenshots` | at least one `toHaveScreenshot` per journey, and committed baselines |
| `e2e-no-skips` | no `test.skip`, `test.fixme` or `test.only` |
| `e2e-reduced-motion` | reduced motion is emulated through `contextOptions` or `emulateMedia` |
| `e2e-ci` | a CI workflow installs the browser, runs `playwright test` and uploads the report |

Standard checks (hex literals outside tokens, `!important` count, emoji in markup, layout transitions) warn, and fail under `--strict`.

**Skips.** Only `economy` and `celebration` can be skipped, and only with a reason of 15+ characters. The report prints every skip and tells the agent to report them verbatim. The user decides whether each reason holds. Skipping any other check exits 2.

### 17.9 Test-first, slice by slice, with a ledger

For **every** slice in §16.4:

1. **Red.** Add or extend the journey or contract tests that express the slice, and run them. Paste the failing output into the ledger. (For S3, S5, S6, S7, S8 the audit is already red: paste that.)
2. **Green.** Implement until the slice's tests pass and the whole suite stays green.
3. **Look.** Open every new or changed screenshot. Write one sentence per image.
4. **Commit** with the rule numbers it applies (`applies R4, R6, R14`) and the images.
5. **Next slice.** Do not stop here to report.

The ledger (`design-evidence.md`, committed) is a table the user can read in a minute:

```
| Slice | Commit | Red (before) | Green (after) | Screenshots opened and what they show | Rules |
| S3 Identity | abc1234 | audit: identity-ramp FAIL | 37/37 pass | j1-first-view (3 projects): chips now a warm-to-cool ramp, selected row ignites | R1 R2 R6 |
```

### 17.10 Getting a browser, and the Playwright traps already hit

- **Install:** `npm i -D @playwright/test && npx playwright install chromium` (add `--with-deps` on a bare Linux box). Already installed elsewhere? Set `CHROME_PATH=/path/to/chrome` (the config reads it). If the install is blocked, the status is **BLOCKED**, with the error. It is never a reason to skip.
- **`reducedMotion` is not a top-level `use` option in Playwright 1.55.** It is silently ignored. Use `contextOptions: { reducedMotion: 'reduce' }` (or `page.emulateMedia`). The `[D3]` test first asserts that the media query is really on, because a reduced-motion test that does not emulate reduced motion proves nothing. The audit also checks this.
- **A phone's layout viewport grows to fit overflowing content**, so `window.innerWidth` can never reveal horizontal overflow (it read 442 on a 390px device). Compare `scrollWidth` with the *configured* viewport width. The helpers do.
- **The backlight layer reached 4rem past its box and made a phone page wider**, so the layout viewport grew and taps missed their targets. Clip the root with `overflow-x: clip` (not `hidden`, which makes a scroller).
- **A pseudo-element can widen a phone page, and `overflow-x: clip` then hides it from `scrollWidth`.** Measure every element's right edge as well (the `no-horizontal-overflow` probe does both).
- **`position: fixed` inside an element with `backdrop-filter` or `transform` is positioned against that element**, not the viewport (known CSS behaviour; the starter avoids it by centring its phone panel with absolute positioning against its trigger).
- **Playwright's default screenshot tolerance is too loose** (17.4 #5).
- **Pin the Playwright version** and the CI image, or baselines shift under you.
- **Light-theme contrast:** a solid flame fill under text measured 3.6 to 4.45:1 on paper, below 4.5. Use a tinted ground with ink text there (guide 14.1). The contrast probe is how this was found.

### 17.12 Making an agent just do it

The failure to prevent is an agent that stops early and calls it done. What works, in order of strength:

1. **Give it an executable acceptance test.** "Make `npm run design:check` exit 0" is a to-do list the machine keeps for you. The core audit checks stay red while S3, S5, S6 are missing, so there is nowhere to hide.
2. **Forbid the early stop in the prompt.** Paste this at the top of the task:

   > Your acceptance test is `npm run design:check`, plus a green `design-e2e` job in CI. You are not finished until both pass. Do not stop to report progress, ask whether to continue, or summarise "remaining debt": that is your to-do list, so keep going. Report only with the status words DONE, INCOMPLETE or BLOCKED (guide 17.1). Work test-first: for each slice write or extend the failing tests, paste the red output into `design-evidence.md`, implement until green, then open every changed screenshot and describe it. Skipping any core slice needs the user's written approval. "No browser tooling" is BLOCKED, not done: install Playwright.
3. **Make the order hard to game.** Foundations (S1, S2), then the core (S3, S4, S5, S6), then optional (S7, S8 with a recorded reason), and only then surface-by-surface polish (landing screens, modals, emoji).
4. **Review the evidence, not the claims.** Read the audit's SKIP list and the ledger, and open a few screenshots yourself. A capable model will usually tell you the truth about gaps; the point is that the truth has a name (INCOMPLETE) and a consequence (keep going).
5. **If it still stops early,** reply with one line: *"Status? Quote the last `design:check` output and the failing check names, then continue."*

---

## 18. Anti-slop checklist

Tick every box before calling the work finished. If you cannot tick it, say so.

- [ ] Every colour on screen can be named: I can say which data value it stands for. (R1)
- [ ] The same item has the same hue in at least two places. (R26)
- [ ] There is exactly one rank ramp; no hand-picked hex per item. (R2, R6)
- [ ] Pole is lightness, item is hue, interaction is chroma. (R4)
- [ ] The lit/selected group holds one lightness and fades chroma. (R5)
- [ ] The work surface is the lightest surface; seams are darker than it. (R8, R9)
- [ ] `backdrop-filter` appears on ≤ 4 large floating surfaces and nowhere repeated. (R10)
- [ ] The ground casts no shadow. (R11)
- [ ] No animation loops. No canvas. Nothing moves while the user is just reading. (R14)
- [ ] Every animation is `transform`, `opacity`, `filter`, or a registered number feeding a shadow. (R15)
- [ ] Reduced motion removes motion but keeps light. (R17)
- [ ] Dim and Veil tiers exist and remove bloom. (R18)
- [ ] There are at most four scales and each setting is on exactly one. (R19)
- [ ] Settings are `data-*` attributes; JS never writes colours. (R20)
- [ ] A stored choice beats a media hint; corrupt storage falls back; Reset works. (R21, R22)
- [ ] Closing an item leaves a remainder; help visibly costs. (R23–R25)
- [ ] Hue never contradicts structure. (R27)
- [ ] Every non-obvious rule has a why-comment with intent, rejected alternative, number. (R29)
- [ ] I listed the keeps before I changed anything, and none is broken. (R30)
- [ ] `npm run design:check` exits 0 and `design-e2e` is green in CI on the branch head. (R28)
- [ ] Every user journey in `JOURNEYS.md` has a test and a committed baseline; nothing is skipped. (§17.3)
- [ ] I opened every changed screenshot and described it in the evidence ledger. (§17.6, §17.9)
- [ ] I report one of DONE, INCOMPLETE or BLOCKED, and it is true. (§17.1)

**Things to refuse on sight:** purple-to-blue gradient backgrounds; glassmorphism on every card; neon glows at rest; rainbow with no ranking; emoji in UI; bouncy springs on controls; confetti on every action; pulsing "notification" dots; tooltips on everything; decorative blobs; a legend explaining what colours mean (the colour should teach itself by use); borders on every box; boxes inside boxes.
