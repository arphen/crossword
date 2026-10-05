# Afterglow: agent core (condensed)

A condensed extract of `DESIGN_LANGUAGE.md`, sized for agents with a small context window (about 9k tokens). It keeps the section numbers of the full guide, so "§6.4" here means the same thing there. Read this completely. Open the full guide only for the section you are working on.

**What this is.** A design language in which *what a thing is can be read from how it looks*: every item has a colour that is its name, the screen glows where something is still open, and finished things leave an afterglow. It scales from the whole composition (macro) down to a glyph's weight (nano).

**The files you can copy** (in `starter/`, tested in headless Chromium): `afterglow.css` (tokens, ramp, material, light, motion, view tiers), `view-settings.js` (settings contract and `createRamp`), `view-panel.js` (the View panel), `territory.js` (publishes corner ranks), `fit-contour.mjs` (fits the lightness contour), `demo.html` (everything assembled).

**Your first move is §16.1, not code.**

---

## 0. Instructions to the agent (read first)

You are being asked to give an existing application a distinctive visual language, not to "make it look nice". The language has one governing idea: **what a thing is should be legible from how it looks, and the screen should feel like it wants something.**

### 0.1 What you must do, in order

1. **Read this whole file.** Do not skim to the code. The code is meaningless without §3, §5 and §10.
2. **Fill in the Content Identity Brief (§16.2)** for the project you are in. Show it to the user. Wait for corrections.
3. **List the non-negotiable keeps (§16.3).** These are the existing things users already rely on. You evolve them; you do not replace them. A previous agent that flattened a well-loved layout was reverted entirely.
4. **Work in slices (§16.4).** Each slice is small, ends green (tests, lint, typecheck), and ends with a screenshot.
5. **Verify with measurement (§16.5).** Read computed styles. Take screenshots. Never assume CSS landed. In the source project, two stray `}` silently disabled a whole feature until a visual review caught it.
6. **Write the why-comments (§12.3).** Future agents, including weaker ones, learn the language from the comments you leave.

### 0.2 Things you must never do

- Never invent a colour by hand-picking hex values per item. Colours come from the ramp (§6).
- Never add an animation that loops. (§9)
- Never put `backdrop-filter` on list rows, cells, cards in a grid, or anything repeated. (§7)
- Never use colour as decoration. If a hue does not name something, remove it. (R1)
- Never write UI copy that tells the user who they are, what they secretly want, or what they feel. (§12)
- Never rewrite the whole stylesheet in one pass. Never replace the existing layout. (R30)
- Never use `!important` to win an argument you could win with a token. (The source leans on it where later sheets override earlier ones, which is a cost of layering stylesheets, not a model to copy. Layer deliberately, or keep one sheet.)

### 0.3 If you are stuck or the project is unlike a crossword

You do not need a crossword. You need: **a set of N things that each have an identity (a number, a name, an index), arranged in two kinds (two poles), some of which are open and some of which are closed.** Almost everything is that: tasks (open/closed) in two lanes, files in two panes, log lines in two streams, notes in two categories, experiments in two arms. Map your project onto §16.2 and proceed. If it genuinely has no such structure, apply only §6 (colour), §7 (material), §9 (motion), §12 (voice), and skip §10.

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

### Voice and process
- **R28. Plain, concrete, honest copy.** No diagnosing the user. No Lacan in UI text (comments are fine).
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

### 12.1 UI copy rules

1. **Short, declarative, concrete nouns.** "No mistakes." "3 letters to fix." Not "Great job! You're crushing it!"
2. **Honest about what is still wrong.** A celebration note states the remaining errors.
3. **Describe how the outcome was reached, not how the user is.** "Solved with no help and no slips." / "That one fought back, and you got it anyway."
4. **Never diagnose.** No "you are…", "your desire…", "you secretly…". A colour or object choice is never a personality finding. The source asserts this in a test.
5. **An exit on every screen.** "Skip", "Take one", "Nothing here has to stay". Choosing one option is never framed as rejecting the others.
6. **No countdowns; no interpretation of hesitation.** The player controls pace.
7. **No exclamation marks, no emoji, no gamified praise inflation, no streak pressure.**
8. **Tell the user what the assistance costs, before they use it.** The score receipt waits behind the score on hover or focus.
9. **Plain words for the Lacan.** The vocabulary of §4 never reaches the screen.

---

## §16 Applying it to a new project (excerpt)

### 16.1 Kickoff protocol (paste this to your local agent)

> Read `docs/DESIGN_LANGUAGE.md` in full before doing anything. Then do exactly this, in order, and stop after each numbered step to show me the result:
>
> 1. Fill in the **Content Identity Brief** (§16.2) for this project. No code.
> 2. List the **non-negotiable keeps** (§16.3): the layouts, colours and interactions users already rely on.
> 3. Take baseline screenshots: desktop 1440×1000 dark, desktop light, and a 390×844 phone. Save them under `design/baseline/`.
> 4. Propose slices S1–S10 (§16.4) tailored to this codebase, naming the files each will touch.
> 5. Only then implement **S1**, run the project's tests, lint and typecheck, take an after-screenshot, and show me a before/after.
>
> Cite rule numbers (R1…R32) in each commit message. Do not combine slices. Do not invent colours; use the ramp. Nothing loops. If anything in the guide conflicts with an existing product behaviour, ask me.

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
13. VOICE     Write: a headline, a description, a finish message for each of 3
              outcomes, and one line the product will never say.
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

### 16.4 Slices (do them in this order; each ends green with a screenshot)

| Slice | Do | Acceptance |
| --- | --- | --- |
| **S0** | Brief, keeps, baseline screenshots. No code. | Brief shown and approved. |
| **S1 Tokens** | Add the token block (§14.1 section 0) and the light theme; map the existing surface colours onto them. | App looks the same or slightly deeper; tests green. |
| **S2 Material** | Figure/ground by lightness; seams; 1px glints; matte controls; glass on ≤ 4 floating instruments. | `grep backdrop-filter` shows ≤ 5 hits, none repeated. |
| **S3 Identity** | Publish `--rank`; ramp; contour; chips and wearers coloured; ember at rest. | The same item has the same hue in ≥ 2 places (R1). |
| **S4 Interaction** | Flame, halo, ignition; hover/press/arrive; cursor; verdict colours. | `document.getAnimations()` has no infinite; reduced motion kills motion and keeps light. |
| **S5 View settings** | `data-*` contract, mini/micro/nano panel, persistence, low-bloom tiers, media hints. | Corners of the dial matrix are legible; Reset works; unknown stored values fall back. |
| **S6 Territory** | Four-corner backlight; conic edge; scroll publishing. | Light hue equals the on-screen item hue (R27). |
| **S7 Economy** (only if the project has open/closed items) | Notches, charge, remainder. | Closing an item contracts its notch; help dims the whole. |
| **S8 Celebration** (optional) | Tiers, note, finale from the last notch. | Finite; honest about errors. |
| **S9 Voice** | Copy pass; why-comments; comment banners. | No diagnosing language; every non-obvious rule has intent/rejection/number. |
| **S10 Audit** | The anti-slop checklist (§17); the verification matrix (§16.5). | All boxes ticked, screenshots attached. |

### 16.5 Verification (R31)

**Measure, never assume.**

```bash
# No looping motion anywhere
grep -rn "infinite" src/ --include=*.css --include=*.js --include=*.jsx    # expect: no hits
# Blur is rare and large
grep -rn "backdrop-filter" src/ --include=*.css                             # expect: ≤ 5 selectors; none on rows/cells
# Hand-picked colours that bypass the ramp (review each hit)
grep -rnE "#[0-9a-fA-F]{6}" src/ --include=*.css | grep -v "^src/.*tokens"
```

**In a real browser** (Playwright or Chrome DevTools Protocol), for a selected item:

- Read `getComputedStyle(chip).color` and the background; confirm they are `oklch(...)` values from the ramp.
- `document.getAnimations().filter(a => a.effect.getComputedTiming().iterations === Infinity).length === 0`.
- Read `--glow-pulse` after 1 s: it is `1`.
- Scroll a lane and confirm the territory properties on the ground change.

**Screenshot matrix** at 1440×1000 (and 390×844 once macro is adapted): dark/light × standard/dim × vivid/soft, plus (a) nothing selected, (b) an item selected, (c) cursor in an item, (d) a verdict showing, (e) one item solved, (f) all solved, (g) `prefers-reduced-motion: reduce`.

**Quick contrast proxy:** keep the OKLab/OKLCH lightness difference between text and its background at **0.40 or more** for working text, then confirm with a real contrast checker. Remember R5: lightness is what makes text legible.

**Unit tests worth writing**
- `normalizeViewSettings`: unknown values fall back; booleans stay booleans.
- `readViewSettings`: a stored value beats a media hint; corrupt JSON falls back; no storage works.
- `createRamp`: shared ids share a rank; 1 item → rank 0; ranks span 0..1.
- Celebration tiers: 0, 1, 2, 5, 10 solved × with/without mistakes.
- No UI string matches `/you are|your desire|you secretly/i`.

### 16.6 If the agent stalls, or goes off the rails

| Symptom | Say this |
| --- | --- |
| It starts coding immediately | "Stop. Show me the filled §16.2 brief first. No code." |
| It rewrites everything | "Revert to the last green commit. Do only slice S<n>. List the files you will touch before touching them." |
| It invents hex colours | "Which rank is that colour? Show me the `--rank` and the ramp it came from, or delete it. (R1, R6)" |
| It adds a pulsing glow | "Nothing loops. Make it ignite once (§9.3). (R14)" |
| It adds blur to cards | "Blur only on ≤ 4 large floating instruments. (R10)" |
| It claims success | "Show the screenshot and the computed style. (R31)" |
| It writes 'delightful' copy | "Rewrite in the voice of §12.1: short, concrete, honest, no praise." |
| It stalls on ambiguity | "Pick the option the guide's §3 prefers; record the choice in a comment with the rejected alternative. (R29)" |
| It forgets the guide | "Quote the rule numbers you are applying in this commit message." |

---

## 17. Anti-slop checklist

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
- [ ] Copy is plain, concrete, honest, and never diagnoses. (R28)
- [ ] Every non-obvious rule has a why-comment with intent, rejected alternative, number. (R29)
- [ ] I listed the keeps before I changed anything, and none is broken. (R30)
- [ ] I have screenshots and computed styles for the final state. (R31)

**Things to refuse on sight:** purple-to-blue gradient backgrounds; glassmorphism on every card; neon glows at rest; rainbow with no ranking; emoji in UI; bouncy springs on controls; confetti on every action; pulsing "notification" dots; tooltips on everything; decorative blobs; a legend explaining what colours mean (the colour should teach itself by use); borders on every box; boxes inside boxes.
