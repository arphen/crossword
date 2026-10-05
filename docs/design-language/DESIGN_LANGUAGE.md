# Afterglow: a portable design language

Distilled from the Crossword app's styling (its stylesheets, view-settings code, commit history and design notes). Written so that a less capable AI agent can apply it to a different project and still land on something coherent, rather than on generic gradient-and-glass "AI slop".

**Version 2 · for humans: how to use this file**

1. Copy this file into the target project (any path; `docs/DESIGN_LANGUAGE.md` is fine). It is self-contained: all starter code and the whole test suite are inlined in §14 and §17.13. If your agent can copy files, also copy the `starter/` folder beside it.
2. For an agent with a small context window, give it `AGENT_CORE.md` instead (a condensed extract of this guide, about 12k tokens).
3. Tell your agent: *"Read `docs/DESIGN_LANGUAGE.md` completely, then do §16.1. Your acceptance test is `npm run design:check` plus a green `design-e2e` job in CI (§17). Do not write code until you have shown me the filled-in Content Identity Brief."*

Everything here is a **design lens plus engineering recipes**. The psychoanalytic reading in §4 explains *why* the choices feel the way they do. Each rule is also stated in plain terms, so the design survives if you delete the philosopher.

---

## Table of contents

0. [Instructions to the agent (read first)](#0-instructions-to-the-agent-read-first)
1. [The 32 rules](#1-the-32-rules)
2. [Cheat sheet: the numbers](#2-cheat-sheet-the-numbers)
3. [The idea: content identity through visual identity](#3-the-idea-content-identity-through-visual-identity)
4. [The psychoanalytic spine](#4-the-psychoanalytic-spine)
5. [The four scales: macro, mini, micro, nano](#5-the-four-scales-macro-mini-micro-nano)
6. [Colour: the ramp, the contour, the three lights](#6-colour-the-ramp-the-contour-the-three-lights)
7. [Material, depth and the ground](#7-material-depth-and-the-ground)
8. [Type and number craft](#8-type-and-number-craft)
9. [Motion: ignition, afterglow, vibration](#9-motion-ignition-afterglow-vibration)
10. [The economy of light (libido, notches, remainder)](#10-the-economy-of-light-libido-notches-remainder)
11. [Celebration and the finale](#11-celebration-and-the-finale)
12. [Prose in the code: why-comments and commits](#12-prose-in-the-code-why-comments-and-commits)
13. [The second register: the salon](#13-the-second-register-the-salon)
14. [Recipes and tested starter code](#14-recipes-and-tested-starter-code)
15. [Lessons learned: the bug museum](#15-lessons-learned-the-bug-museum)
16. [Applying it to a new project](#16-applying-it-to-a-new-project)
17. [UI testing: Playwright journeys, screenshots and CI](#17-ui-testing-playwright-journeys-screenshots-and-ci)
18. [Anti-slop checklist](#18-anti-slop-checklist)
19. [Accessibility, adaptivity and phones](#19-accessibility-adaptivity-and-phones)
20. [Glossary](#20-glossary)
21. [Provenance](#21-provenance)

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

## 3. The idea: content identity through visual identity

### 3.1 The thesis

Most interfaces separate *what a thing is* from *how it looks*. This language fuses them. **A number (or name, or index) has a colour, and that colour is its name.** The reader learns the colour of 34 once, on its chip in a list, and then recognises the same colour on the square in the grid where 34 begins, on the tick that opens it, on the track under its clue, on the light on the far side of the board, in the confetti. The colour is learned *by use*, not by a legend.

That is "establishing content identity via visual identity". It is also why the interface feels like a place rather than a skin: the screen has a **territory** the reader navigates by colour ("I'm in the yellow and the purple").

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

### 3.4 Two things the design refuses

- **A rainbow with no ranking** (colour for variety). It teaches nothing and breaks R1.
- **A second semantic layer in the same hue family.** "Orange means error" and "orange is Across" cannot both be true. The source stopped colouring its five stats orange and blue "which said nothing about direction"; colour was kept for things that mean something.

---

## 4. The psychoanalytic spine

### 4.0 Guardrails (read before using any of this)

The source project's own design notes are explicit, and so should you be:

- These are **interpretive design lenses**, not claims that a UI measures the unconscious. Do not label a failed guess "repression", a reveal "castration", or a blank "the Real".
- Every rule below is also stated in plain terms. **If the philosopher is deleted, the rule must survive.**
- The vocabulary belongs in comments, commit messages and design notes. Keep it out of product text.

### 4.1 Table: concept, reading, rule, CSS

| Concept | Reading for design | Plain rule | CSS expression | Never |
| --- | --- | --- | --- | --- |
| **Signifier / chain** | A mark means nothing alone; it means by differing from the others. A letter in a grid "signifies nothing and distinguishes everything". | Colour has no intrinsic meaning; it means *rank within the set*. | Ranked ramp; `--rank` on every wearer | Colour for "feeling" |
| **The Other (the rules that do not negotiate)** | The symbolic order is a system that refuses us on principle. A principled "no" invites investment; an arbitrary one makes it precarious. | The UI must be unyielding but fair: same signals mean the same everywhere. | Verdict colours win over selection; stable conventions | Quietly changing the object to suit the user |
| **Objet a / the notch** | The cause of desire is not the thing wanted but the *lack* that opens it. "Each notch is the open address of a word not yet said." | Mark where a thing *begins* or is *open* with a small, bright, specific mark. | Gate ticks (2px filaments), spill of light 3 cells | A glowing blob on everything |
| **Libido / economy** | Desire is a finite charge that moves, not a supply that grows. | One charge of light shared among what is still open; closure frees it. | `--charge = libido × remaining^-0.5`, clamped | Adding glow as things complete |
| **Retroactive determination (après-coup)** | A later event changes what the earlier one meant. | What happens now leaves a trace that *recolours* what came before. | Afterglow: a solved square flares once then rests with a trace of its hue in its ink | Instant, total reset after completion |
| **Metonymy / displacement** | Satisfaction is displaced onto the next signifier; "an aim attained and immediately found not to be the aim". | Closure relocates the light; it does not spend it. | The last open notch carries nearly all the charge; confetti fires from it | A dead, flat "done" state |
| **Drive / jouissance** | Return around an obstacle; enjoyment inside resistance. | Friction is the product. Do not optimise it away. | Checks and reveals drain the charge; no instant solve | Frictionless "help" that dissolves the interval |
| **Imaginary** | The recognised image: gestalt, colour, "this is me, here". | Let the reader locate themselves by colour (territory). | Four-corner backlight; conic bezel edge | Using the image to override structure |
| **Symbolic** | Rules, conventions, grammar. | Tokens, consistent signals, learnable conventions. | The ramp, the grammar of ticks, seams, runs | Inconsistent signals between screens |
| **Real** | What resists symbolisation: the letter that does not fit. | Let error be a plain, honest verdict, not decoration. | Red/green as fill+ink, no glow | Dramatising errors; "unknown" as a mystery blank |
| **Unmarked / unchecked cell** | A cell that belongs to no crossing is "a signifier with no Other". | Every mark must be checked by another mark. | Colour appears in ≥2 places | Orphan decoration |
| **Mise-en-scène** | Placing an object so a relation to it becomes a question. | Compose the screen as a scene: ground, figure, instruments floating over. | The grid is the ground; lanes lie over its edge; instruments float as glass | A stack of framed boxes |

### 4.2 The three registers as a layered design check

Use as a review lens, not a mandate:

- **Symbolic layer** (structure and convention): do the tokens, the signals, the conventions agree everywhere? *Test: pick any colour on screen. Can you name the one data value it stands for?*
- **Imaginary layer** (image and identity): can the reader locate themselves by looking? *Test: squint. Do the four corners of the screen have different colours that drift with scrolling?*
- **Real layer** (friction and verdict): is the error state honest and the help costly? *Test: does pressing Check change anything except truthfully?*

**Hard rule between layers: the Imaginary never overwrites the Symbolic.** The colour must never contradict the structure. The source puts it as: *"Hue always stays the clue's own, value carries the lane, and how much colour is spent carries the interaction, so the rainbow never says anything the reader must unlearn."* (R27)

### 4.3 The seven questions to ask of any screen

1. **What is open here?** (Name the one or two things the screen wants.) Make *those* emit light. (R23)
2. **What does closing it leave behind?** Design the remainder, not an empty state. (§10.3)
3. **Where does the freed light go?** To what is still open. (R24)
4. **What does help cost?** Make the price visible. (R25)
5. **What is each colour a name of?** If nothing, delete it. (R1)
6. **What answers to what?** Every mark needs a crossing: a second place it appears. (R26)
7. **What would be unprincipled here?** Anything that changes the rules mid-game, or says something the reader must unlearn. (R27)

### 4.4 Why friction is a design value

The source's own critique: the crossword is "one of the few contemporary forms in which friction is the product, and almost every affordance competing with you (hints, instant checks, adaptive rescue, infinite generation, chat) is a machine for dissolving friction". Therefore *help is editorial policy, not a support feature*. In UI terms:

- Help affordances are present but **priced** (they reduce the score, which reduces the light on the whole board).
- A reveal is not hidden or softened; a check shows an honest verdict.
- The product sells the *interval* between asking and answering. Never remove the interval.

---

## 5. The four scales: macro, mini, micro, nano

The source adjusts its interface at several scales, from the whole composition down to a single glyph's weight. In the source's own code, the reader-facing *View* panel has three tiers named **Mini, Micro, Nano**. The *macro* scale is the composition itself, which the designer owns. This guide names all four so you can place any change on the right one.

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

### 5.4 The View panel pattern

- A native `<details>`/`<summary>` gives keyboard and screen-reader behaviour for free.
- One fieldset per tier; its legend has a title ("Mini") and a quiet hint ("Comfort").
- Each row is a label and a segmented group of `button[aria-pressed]`.
- The pressed button takes its **tier's own accent** so a row is recognisable by colour alone: Mini green, Micro orange, Nano blue.
- A single `Reset to defaults` text-button at the foot (R22).
- The panel opens **upward** from the dock (the board owns the space above it); it scrolls rather than running off a short window (`max-height: min(72dvh, 620px)`).

---

## 6. Colour: the ramp, the contour, the three lights

### 6.1 The ramp

1. **Rank.** Collect distinct identities, sort, rank = index / (count − 1). Rounded to 3 decimals. (§14.2 `createRamp`.) Rank, not value: a 70-item puzzle still reaches both ends of the arc. Shared identities share a rank.
2. **Arc.** Each pole gets half of the OKLCH hue wheel: pole A 2→142 (pink → orange → yellow → green), pole B 183→323 (teal → blue → violet → magenta). The arcs never overlap.
3. **Hue** = `arcStart + rank × (arcEnd − arcStart)`.
4. **Pole lightness.** Pole A = base + 0.07, pole B = base − 0.07. *Direction reads as value, never as a second hue.*
5. **Contour** (next section) adds a per-rank lightness offset.
6. **Colour** = `oklch(L C hue)` with base L 0.82 and C 0.14 on a dark ground; L 0.42 and C 0.12 on paper.

### 6.2 The rationale (what the stylesheet says, condensed)

- A numeral needs a certain lightness on a dark ground. At that lightness, yellow and green hold a vivid chroma, while pink, orange and violet "run out of colour well before it".
- So with one lightness per arc, the tight hues clip (paler, shifted off their rank) while easy ones stay vivid, and the rainbow steps unevenly.

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

### 6.6 Verdict colours (R7)

- Green `#8fe4b1`/red `#ff9c9c` (dark), `#246a43`/`#ad313d` (light).
- Each is a *fill + ink + border*, with the glow switched off: "a checked letter keeps the verdict to itself: right or wrong, the box drops its glow while the check is on the board".
- **Validation wins over selection, including the cursor at an intersection.**
- When a verdict sits inside a lit word, make sure the small index/number remains legible (a dark index on dark red once vanished).

### 6.7 Territory: the ground is lit by what is on screen

- The reader has four corners of colour on screen: the top and bottom of the first lane on the left, of the second lane on the right. "The reader learns where they are by them."
- Publish the ranks of the items showing in those four corners (`--ta-top`, `--ta-bottom`, `--tb-top`, `--tb-bottom`). Compute the four corner colours *from exactly those ranks*. Light the ground's four corners with them as radial gradients on their own layer behind it, and sweep a conic gradient around the bezel's hairline edge.
- **The light must be exactly the hue of the clue showing there.** An earlier version widened the hue gap "to read as four colours" and the light disagreed with the lanes: green glowing under orange clues. It was reverted. The light spends a little more chroma (×1.3) than numerals so hues a screen apart still read apart once blurred.
- Register the four ranks with `@property` (`<number>`, `inherits: false`) and transition them over 900 ms, so the hue glides while the lists scroll. Because they do **not** inherit, a drifting corner repaints only the grid's own edge and glow, never restyles a square.
- On paper, light from behind reads as a stain: keep it at 14%.

### 6.8 The ramp, reused

The same ramp appears in: chips, square indices, edge ticks, track notches, the spill of light from a notch, springs between chips (gradients from one chip's colour to the next), the progress bar (both arcs end to end, uncovered as work is done), the finale rule under the title (the full 46→332 sweep), the finale rule under the title, and the confetti. That is R26 in action: the colour is *checked by a crossing* on every surface.

---

## 7. Material, depth and the ground

### 7.1 Figure and ground by lightness (R8)

- Measured in OKLab, the empty squares sat *below* the panel's lit corner (L 0.31 vs 0.33), so the board had no figure: the frame was as bright as what it framed. Fix: squares rose to L 0.35 and the panel highlight dropped to L 0.29. The squares became the **lightest surface in the console**, "the board's paper".
- Order, darkest to lightest: well (black cell) < bezel < grout < panel < **paper**.

### 7.2 The ground and the instruments (macro)

- The board is **the ground** everything else stands on. It is sized by the window's *height*. It is *wider* than its column by about a notch on each side, so its outer edge runs on beneath the lanes.
- The lanes lie over that edge **as light smoke**: thickest at the board's rim, gone a little way past the notches, so what lies under them still reads as a notch and the lane still reads as on top. "The map laid over the territory; neither owns the overlap."
- The masthead (top) and the dock (bottom) **float over the board's edges as glass**. Lanes keep scroll room (`padding-bottom: bottom-band + 8px`) so their last items can always rise above the dock.
- The lanes are where the solver lives: they keep at least 390px before the board may grow.
- The rounded console panel was removed. Nothing frames the board but its own square bezel: "a square bezel: the grid of reality has no soft corners".
- **The ground casts no shadow (R11).** A large drop shadow showed as a "dark vertical band beside it, a shadow cast onto nothing".

### 7.3 Glass, and where it is allowed (R10)

```css
.glass {
  border: 1px solid color-mix(in oklab, var(--ink) 10%, transparent);
  background: color-mix(in oklab, var(--panel) 76%, transparent);
  backdrop-filter: blur(14px) saturate(140%);
  box-shadow: inset 0 1px 0 var(--glint), 0 18px 40px -18px #00000038, 0 2px 6px #00000030;
}
```

- **Allowed on:** the masthead, the dock capsules, the transient note, the finale card. Four or five elements, all large, all floating.
- **Forbidden on:** rows, cells, track boxes, chips, list items, anything repeated. "That is a battery and jank disaster."
- Everything else is **matte**: flat fill, a 1px top glint (`inset 0 1px 0 var(--glint)`), a hairline border and a soft contact shadow.
- Controls are quiet glyphs on the panel until the pointer finds them (`color-mix(var(--ink) 8%)` background on hover).

### 7.4 Seams, grout and tiles

- Cell edges were a lighter grey than the squares, "a seam faint enough that a run of empty squares read as one bar". Fix: **near-black grout** between squares and a slightly stronger top glint, so squares read as separate tiles. Black squares stay darker than the grout.
- **Answer tracks are strips torn from the board**: square cells in the *board's own* fill and grout, touching edge to edge, no rounding, 25px. "An empty track frames its gap the way the grid does and a finished one could be laid straight back into it." The track sits a hair above the lane on a soft shadow.
- Inside a word a new run joins on a **heavier seam** (2px, the board ruler's major tick); the strip only *tears open* (9px) where the answer has a real gap between words.
- Runs are balanced, never orphaned: 11 becomes 4/4/3, not 5/5/1, "so the eye can count a run from either end".
- On paper the heavier seam mixed 55% black into the grout and a wrapped strip started with what read as a black bar. At 28% it still groups the count and no longer looks like an edge.
- The board's bezel carries a **ruler**: a tick at every column and row, longer every fifth, drawn as four static `repeating-linear-gradient` layers on the one board element, so it costs nothing per cell.

### 7.5 Radii and the lattice (R12)

- One panel radius minus its padding sets the radius of everything in its corners. The lattice (grid) is square.
- Chip radius 8, controls 10, glass capsules 14, masthead 16, finale card 26.

### 7.6 The ladder (an optional macro idiom)

The source's lists run in a two-column *zig-zag*: odd rows have the number on the right, even rows on the left, with ±25px of vertical offset so consecutive anchors form a diagonal chain. Springs (a prolate trochoid, drawn from *measured* chip rectangles) connect chips, and pull taut (the coil opens out and flattens) when solved clues between them leave. It is the single best "scannability" device in the source: **the typist's eye lands on the number first, the clue second, the letter track third.** Adopt it only if your content is a list that people address by number or name aloud. Otherwise skip to §7.7.

### 7.7 Performance rules that made the material possible

- Cache measured geometry; re-measuring every chip on every selection change forces a synchronous layout.
- Static gradients for rulers, backlights, and notches. Static paint carries colour; **nothing on the board moves while the reader is just reading.**
- Blurred shadows are expensive to repaint. That is why the infinite pulses were removed (§9.1) and why the **best-effort glow gate** exists (`data-glow="off"` for a frame or two after the selection changes; the cursor keeps its full chrome throughout because it is one element and must never blink).
- The registered territory ranks do not inherit (§6.7).

---

## 8. Type and number craft

### 8.1 Faces

- **Instrument face:** `'Avenir Next', 'SF Pro Rounded', 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif`. "A rounded-geometric sans reads faster in capitals than a monospace, and its tabular figures still keep columns." Use it for letters, numerals, chips, buttons, stats.
- **Mono** (`ui-monospace…`): only for tiny technical eyebrows and marginal captions.
- **Serif** (`Georgia`): only in the *salon* register (§13): headlines and marginalia.

### 8.2 Numerals

- Always `font-variant-numeric: tabular-nums lining-nums` on anything that changes or aligns: chips, clocks, scores, progress.
- Chip numeral: 1.12rem, weight 700. Stat value: 1.4rem, 600, `letter-spacing: -0.01em`, `line-height: 1`.

### 8.3 Labels

- Micro-labels: 0.6–0.62rem, weight 600–700, `letter-spacing: 0.14em`, `text-transform: uppercase`, muted ink.
- Eyebrows (salon): 9px mono, uppercase, `letter-spacing: 0.16em`.

### 8.4 The letter in a square

- The capital sits slightly **below** centre (padding-top ≈ 14% of the cell; font ≈ 50% of the cell), "the way a printed grid sets it", leaving the corner number air. Dead centre at 52% made a two-digit number (20 against D, 34 against M) touch the letter.
- Rebus/long values drop to 28% of the cell.
- The corner index: `clamp(8px, 0.21 × cell, 11px)`, weight 650.

### 8.5 Emphasis without moving text

Highlighted and crossing clues once switched to bold, rewrapping text so rows changed height on every cursor move. **Emphasis thickens strokes without changing metrics:** `-webkit-text-stroke: 0.032em currentColor`. The clue text size is `clamp(15px, 1.04vw, 20px) × scale`. Row height must not change when the selection moves.

### 8.6 Firm letters

An optional nano dial: weight 700 and `letter-spacing: 0.02em`: "which is what survives a bright screen behind smudged lenses".

### 8.7 Wordplay signals (a pattern worth stealing)

Grammar signals inside text get *typographic* treatment first: a dotted underline with a help cursor for any signal; italic for tense; small-caps for plural; a letter-spaced blank. Two signals also take a muted colour (amber for a question mark, blue for a bracket) that stays well away from the identity ramp. Typography encodes grammar and colour encodes identity (channel discipline, §3.2).

---

## 9. Motion: ignition, afterglow, vibration

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

### 9.4 Afterglow (what a finished thing leaves behind)

This is the "afterglow here and there" the product feels like. It has five forms; use at most two or three per project:

1. **The solved settle.** A finished cell flares from inside (an inset glow of 55% of the cell size at 58% of its tint, driven by `--settle` 1→0 over 1800 ms), then rests as clean paper with the letters carrying a trace: `color: color-mix(in oklab, var(--ink) 80%, var(--solved-tint))`.
2. **The notch's remainder.** A solved word's open-end tick contracts to a single point (`scaleY(0.09)`, opacity 0.85, 1100 ms) instead of vanishing. A finished board is "a dark, whole lattice dotted with these leftovers".
3. **Territory drift.** Corner hues glide over 900 ms as lists scroll.
4. **The flow of charge.** Light drains and gathers (transitions, never jumps) as items close (§10).
5. **The row that leaves.** A solved row lifts (translateY −44px over 1000 ms), dissolves, leaves a ring (scale 0.9→1.7, 700 ms), and a green band; the rows below slide up and settle while the springs follow (§11).

### 9.5 Vibration (micro feedback on contact)

Not a literal vibration. In the source "vibration" is a **single, finite, tiny response to contact**:

| Event | Response |
| --- | --- |
| Hover a control | `translateY(-1px)`, border brightens, 140 ms |
| Press | `translateY(0) scale(0.97)`, **60 ms**; icons `scale(0.94)` |
| A letter is committed | arrives: opacity .35→1, `translateY(2px) scale(.94)`→rest, 160 ms |
| A verdict appears | the same arrival at 220 ms |
| A cell receives focus | an inner ring scales .9→1 in 180 ms |
| A score detail opens | opacity + `translateY(-4px)`→0 in 140/260 ms |
| A spring is created | fades in over 240 ms |
| The progress bar advances | `scaleX` over 700 ms on the cover layer |

Press is *shorter* than hover (60 vs 140 ms) so the control feels like it gives under the finger and returns.

### 9.6 Easing vocabulary

- `--ease-out: cubic-bezier(0.22, 1, 0.36, 1)`: everything interactive.
- Ignition `cubic-bezier(0.2, 0.7, 0.2, 1)`.
- Overshoot only for arrivals of a *note* or a *card*: `cubic-bezier(0.2, 1.3, 0.4, 1)` (note) and `(0.2, 1.35, 0.4, 1)` (card). Never for controls.

---

## 10. The economy of light (libido, notches, remainder)

This is the most original idea in the source and the one most worth transplanting. It applies whenever your screen has *open things that close*.

### 10.1 The model

- A **notch** is the open address of something not yet done. It emits a short, specific filament of light, in that item's own hue, on the edge where it opens.
- The board holds **one charge** of light and shares it among the notches still open.
- **At the start** the charge is spread thin over every notch and the short spills overlap into a soft, smudged board.
- **Each closure** puts its notch out (it contracts to a point), the cell flares once as it settles, and "the charge a word gave up flows into the notches still open".
- **At the end** "the board clears from smudge into a few intense lights, and the last notch carries nearly all of it".
- **Help drains the whole charge.** Every check and reveal lowers the score and dims *every light at once, backlight included*: "the board loses its desire along with the points".

### 10.2 The formulas

```css
--remaining: 1;   /* 1 → 0: fraction of items still open  */
--libido: 1;      /* 0 → 1: (score/100)^1.25, rounded      */
--charge: clamp(0.18, calc(var(--libido) * pow(max(var(--remaining), 0.05), -0.5)), 2.6);
--tick-glow:       calc(6px * var(--charge));
--tick-glow-alpha: min(96%, calc(62% * var(--charge)));
--tick-core:       min(78%, calc(44% * var(--charge)));
--spill-alpha:     min(30%, calc(var(--spot-alpha) * var(--charge)));
```

- Inverse *square root* of what remains: the last notch is bright but not blinding; capped at 2.6.
- Backlight uses `max(var(--libido), 0.3)` so a bad score dims it but never extinguishes it.
- JS only publishes `--remaining` and `--libido` on the root and names which cells/openings are solved (`data-solved`, `data-gate-solved`). CSS spends the light.

### 10.3 Designing the remainder (the "what remains")

Every closed thing must leave something: a point of light, a trace of hue in the ink, a seam. Never an empty state. The *last* open notch is the origin of the finale (§11.4).

### 10.4 The spill

Each answer projects its notch's light along itself, eastward for pole A, southward for pole B, fading **linearly** and gone by the third square.

- First attempt: decay as `1/(1 + 0.45d)`. The tail reached across the whole word; with an A and a B tail on most squares the hues mixed into **olive and mauve**.
- Each square holds its own level *flat across its width* so neighbours step down visibly instead of averaging out (a fade-to-transparent inside every square would average them).
- Quiet by design: a whole board wears it at once; the selection's flame speaks over it where they meet.

### 10.5 Gate ticks

A black (inert) square that opens a slot carries a 2px filament on the edge facing it, bright-cored (`color-mix(white var(--tick-core), tint)`) and softly bleeding (`box-shadow: 0 0 var(--tick-glow)`), in the hue of the word it opens. East tick = the A-pole word starting east; south tick = the B-pole word starting south, each in its pole's value. The ticks of the direction being solved sit brighter. A stub that opens no word keeps a quiet pole colour.

### 10.6 Transplanting it

| Your thing | Notch | Closure | Remainder |
| --- | --- | --- | --- |
| Task board | an unchecked task's edge | task done | a dot on the column rule |
| Log viewer | an unresolved error line's gutter | acknowledged | a faint mark in the minimap |
| Reading list | an unread entry's spine | read | a hue trace in the title ink |
| Dataset review | an unlabelled row's left edge | labelled | a tick in the progress bar |

---

## 11. Celebration and the finale

How much happens scales with *how much was solved* and *whether any letter is wrong*. All of it is finite, on transform/opacity, with no canvas and no glow.

### 11.1 Tiers (pure arithmetic, testable)

| Tier | When | What |
| --- | --- | --- |
| 0 | nothing solved | nothing |
| 1 | one item | a quiet green lift. "One clue is progress, not an occasion" |
| 2 | 2–4 items | a few sparks |
| 3 | 5–9 items | sparks and a note |
| 4 | 10+ items | a board-wide wash |
| 5 | a clean sweep: 4+ with no mistakes (adds one tier, capped at 5) | everything |

Sparks per item `[0, 0, 3, 6, 9, 13]`, with a global budget of 160 shared across the batch, so a hundred-item sweep stays cheap. Sparks leave the number chip, drift up and out, size 2–5px, flat dots in three tones.

### 11.2 The note

A transient glass note at the top: *"{n} clues"* and either *"No mistakes"* or *"{m} letters to fix"*. **Honest about what is still wrong.**

### 11.3 The finale card

A glass card (26px radius, blur 18px) with a drawn checkmark (stroke-dashoffset, 700 ms then 420 ms), a title with a 3px **rainbow rule** under it (the full ramp; opacity .55, or 1.0 and wider for flawless), and four stats. The title and one honest line are chosen from *how it was reached* (reveals, checks, score), not from who the user is:

| Grade | Condition | Title |
| --- | --- | --- |
| flawless | no reveals, ≤1 check, score ≥ 90 | *Flawless* |
| strong | no reveals, score ≥ 70 | *Solved* |
| steady | ≤ 2 reveals | *Solved* |
| finished | otherwise | *Finished* |

### 11.4 Fire the finale from the last notch

When the last item closes, "the light the board gathered into its final notch becomes the fireworks". The board remembers which items were still open; on completion the confetti flares out of the opening of the last of them, then falls. Each piece leaves at its own angle and reach. Confetti is the ramp itself: `oklch(0.8 0.11 hue)` across the full 46→332 sweep, **so the colours the reader has been learning are the ones that fall.**

### 11.5 Reduced motion

The celebration hook does not start at all; the finale card still appears; the checkmark is drawn (`stroke-dashoffset: 0 !important`).

---

## 12. Prose in the code: why-comments and commits

The source's stylesheets carry long comments that read like design notes, and its commits read as short lessons. That prose is how a later agent, including a weaker one, learns the language without breaking it. Write it.

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

### 12.2 Sentences from the stylesheets worth keeping in your head

These are the language's constitution, quoted or tightly condensed:

- *"Direction reads as value, never as a second hue."*
- *"Interaction reads as saturation. The ember is the clue at rest, the flame is the clue being worked."*
- *"The flame names the clue, the halo names the lane."*
- *"A board that kept pulsing would never let the eye rest, and would repaint its blurred shadows every frame."*
- *"Nothing on the board moves while the reader is just reading."*
- *"Hue always stays the clue's own, value carries the lane, and how much colour is spent carries the interaction, so the rainbow never says anything the reader must unlearn."*
- *"Whether a letter can be read is a question of lightness alone: hue never helps or hurts."*
- *"The notches are where the board wants: each one the open address of a word not yet said."*
- *"The board loses its desire along with the points."*
- *"A finished board is a dark, whole lattice dotted with these leftovers."*
- *"The squares are the paper: the lightest surface in the console."*
- *"A square bezel: the grid of reality has no soft corners."*
- *"The map laid over the territory; the overlap where neither owns the screen."*
- *"Only these large surfaces blur what lies beneath them."*
- *"Learn the colour on a chip, find the same colour on the square."*
- *"Number colours Off keeps the structure and drops the pigment, so the option is usable by readers who only want the rails."*
- *"The spill falls off linearly and is gone by the third square, so the notch's light stays where the notch is."*
- *"Emphasis thickens the strokes without changing the face's metrics: a real weight change rewraps the clue, and every cursor move would resize rows and shove the lane under the reader's eye."*
- *"One selection, one hue, on both surfaces."*
- *"Sparks are flat dots so a bright screen has nothing to bloom."*

### 12.3 Commit messages as lessons

Commits in the source are small and read as **symptom, cause, fix, number**. Copy the shape:

```
Hold the lit word at one lightness and fade its chroma instead

Legibility on a coloured square depends on lightness alone. The lit word
faded from a light tint at its first square to the dark direction fill at
its last, so its dark lettering fell from ~10:1 contrast to ~2.7:1 along
every Across word. The position fade now moves chroma at constant
lightness ...
```

---

## 13. The second register: the salon

The solver (the "instrument") is dense, bright with data, and quiet at rest. The onboarding and reflection screens (the "salon") share its poles and ground but speak differently. If your project has an *arrival*, a *reflection*, an *empty state*, or a *reading* screen, use this register there.

| Aspect | Instrument | Salon |
| --- | --- | --- |
| Ground | `#0c1015` | `#0c1015` (same), surface `#141a21`, edge `#2b333d` |
| Ink | `#f2f2f6` | warmer `#eeeae2`; muted `#9aa4af` |
| Poles | orange `#ffad32`, blue `#8dc7ff` | amber `#e8b76e`, blue `#8dc7ff` (same blue) |
| Headline | rounded sans, 1.12rem | **Georgia 400**, `clamp(34px, 3.45vw, 54px)`, line-height 1.13, `letter-spacing: -1.7px`, an `<em>` tail in amber |
| Body | 14–16px | 13px / 1.7, `#a1aab4`, `max-width: 450px` |
| Eyebrow | | 9px mono, uppercase, `letter-spacing: 0.16em`, muted |
| Marginalia | | Georgia italic 18px/1.7, `#9ca8b4`, `max-width: 150px`, in a side rail |
| Rail words | ACROSS/DOWN watermarks at 190px, 6–45% opacity | vertical (`writing-mode: vertical-rl`) 105px weight 800, **3% alpha** amber / blue |
| Primary button | matte glass, 10px radius | amber `#e8bc7c`, 3px radius, dark ink, `inset 0 1px #fff3` |
| Cards | tiles with seams | 4px radius, radial `#222b3545 → #141a2155`, hairline `#ffffff0f`, selected = amber hairline and a warm wash |
| Motion | ignite, press | scene arrives 400 ms; objects hover `translateY(-4px) rotate(-2deg)` 450 ms; chosen `translateY(-3px)` |
| Layout | 3 columns, ground + lanes | 3 columns `minmax(165px,1fr) minmax(500px,820px) minmax(165px,1fr)` with a left rail (chapters) and right rail (marginalia) |

**Chapters and steps.** Progress is a mono list of chapter names (Encounter, Relation, Variation, Traces, Setup, Preview) with the current one amber and a 4px dot, and `4px` step dots. Past chapters are brighter than future ones.

**Objects, not icons.** The opening screen is "an unusual small arrangement of things": hand-built vector objects (a knotted thread, a dark stone, a transparent cube, a brass key, an open circle, a zero, a fork, a folded map, two dots, a seed, a shell, an orbit). Each is an original SVG with a gradient *material* (gold, glass, stone, silver, pearl) and a soft ellipse shadow. They are **a balanced composition, not a symbolic codebook**: the key does not mean ambition. All options are matched in visual weight, so a large glowing one cannot "win" the choice.

**The salon's rules**
- No interest checklist, no personality categories, no opening question about desire, no mandatory text field.
- Pass/skip on every screen.
- Neutral accessible labels; a monochrome/shape alternative; reduced motion. Accessibility choices never become evidence about the person.
- Keep the whole thing 45–90 seconds. The player sets the pace.

---

## 14. Recipes and tested starter code

All the files below were run in headless Chromium 141 while this guide was written. `starter.css` was rendered in dark, light and dim; computed colours were read back (for example the first chip computes to `oklch(0.775 0.14 2)` and the selected one to `oklch(0.7836 0.245 42.04)`); ignition ran once for 640 ms; the settle ran once for 1800 ms; no animation was infinite; the territory script was exercised with real scrolling. Bugs in the starter, its demo and the test suite were found and fixed during that testing (§15, items 29 to 37).

**Real files.** Every file below also exists in `starter/` next to this guide, byte for byte, and `starter/demo.html` assembles them into one page (serve the folder with `python3 -m http.server`, open `demo.html`, try `?theme=light`, `?luma=dim`, `?vibrance=soft`, `?open=1`). If an agent can copy files, have it copy `starter/`; the inlined copies are for agents that can only read this document.

**Token root.** Everything that uses the tokens must live *inside* the `.afterglow` element (or you must declare the tokens on `:root`). Portals, modals and tooltips mounted on `<body>` will otherwise render without them (§15, item 31).

**How to use them.** Rename `.afterglow`, `.lane`, `.chip`, `.slot`, `.tile`, `.ground` to your project's nouns if you like; keep the *variable names and the logic*. Add `style="--rank:0.43"` to every element that should wear an identity colour.

### 14.1 `afterglow.css`: tokens, ramp, material, light, motion, tiers

```css
/* ==========================================================================
   afterglow.css — starter tokens and mechanisms.
   Rename .afterglow / .lane / .chip / .tile to your own nouns; keep the
   variable names and the logic. Every rule here is explained in the guide.
   ========================================================================== */

/* Registered numbers can be eased by transitions and animations. Without
   @property a custom property jumps; with it, light can gather and drain. */
@property --glow-pulse { syntax: '<number>'; inherits: true;  initial-value: 1; }
@property --settle     { syntax: '<number>'; inherits: false; initial-value: 0; }
@property --ta-top     { syntax: '<number>'; inherits: false; initial-value: 0; }
@property --ta-bottom  { syntax: '<number>'; inherits: false; initial-value: 1; }
@property --tb-top     { syntax: '<number>'; inherits: false; initial-value: 0; }
@property --tb-bottom  { syntax: '<number>'; inherits: false; initial-value: 1; }

/* --- 0. Tokens ----------------------------------------------------------- */
.afterglow {
  /* Surfaces. Figure is lighter than ground: tile > bezel > bg. */
  --bg: #0c1015;
  --panel: #1a2027;
  --panel-light: #252b33;
  --panel-edge: #3a414b;
  --bezel: #151b21;
  --paper: #343a45;       /* the lightest surface: where the work is done */
  --grout: #1e232a;       /* seams between paper tiles; darker than paper */
  --well: #0d1218;        /* a recess; darker than the grout */
  --ink: #f2f2f6;
  --muted: #aeb6c2;
  --glint: #ffffff13;     /* 1px top-edge highlight on raised things */
  --paper-glint: #ffffff0d;

  /* Two poles: the two things your content comes in two kinds of. */
  --pole-a: #ffad32;      /* warm */
  --pole-b: #8dc7ff;      /* cool */
  --ok: #8fe4b1;
  --bad: #ff9c9c;

  /* The colour ramp. Each pole owns half of the hue wheel (OKLCH degrees),
     so the two gradients never overlap. Pole A runs warm, pole B runs cool. */
  --a-start: 2;   --a-end: 142;
  --b-start: 183; --b-end: 323;
  --ramp-l: 0.82;           /* base lightness on a dark ground */
  --ramp-c: 0.14;           /* base chroma */
  /* Contour: lightness offset l0 + l1*r + l2*r^2 per rank r (0..1) so tight
     hues (pink, orange, violet) are lowered enough to fit sRGB at this
     chroma, and generous ones (green, yellow) are lifted back. */
  --a-l0: -0.115; --a-l1: 0;     --a-l2: 0.105;
  --b-l0: 0.035;  --b-l1: -0.24; --b-l2: 0.24;
  /* Direction reads as VALUE, never as a second hue. */
  --a-lift: 0.07;
  --b-drop: 0.07;

  /* Interaction reads as SATURATION. Ember = at rest, flame = being worked,
     halo = names the pole (not the item). Alphas decide how much light each
     state may make on this display. */
  --ember-chroma: 0.7;
  --flame-chroma: 1.75;
  --ember-alpha: 14%;
  --cross-alpha: 22%;
  --flame-alpha: 34%;
  --halo-alpha: 18%;
  /* Light from behind (section 6). Tiers and themes tune it HERE, on the
     root: a token declared on the element that uses it cannot be overridden
     by a tier that sits above it. */
  --backlight: 36%;
  --glow-chroma: 1.3;  /* the light spends a little more chroma than numerals */

  /* One curve, three durations. */
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
  --dur-quick: 140ms;
  --dur-settle: 260ms;
  --dur-ignite: 640ms;

  --face: 'Avenir Next', 'SF Pro Rounded', 'Segoe UI Variable Text',
    'Segoe UI', system-ui, sans-serif;

  background: var(--bg);
  color: var(--ink);
  font-family: var(--face);
  color-scheme: dark;
  /* The backlight layer reaches past its box; clip it here or it widens the page (a phone's
     layout viewport silently grows to fit it). `clip`, unlike `hidden`, makes no scroller. */
  overflow-x: clip;
}

/* Light theme = paper and ink. Same structure, inverted material: the ramp
   sits deeper, the contour moves (on paper the narrow places are yellow and
   cyan), and light-from-behind turns faint so it does not read as a stain. */
.afterglow[data-theme='light'] {
  --bg: #f3f3ef; --panel: #e5e8e6; --panel-light: #f9faf8; --panel-edge: #cbd1ce;
  --bezel: #d7ded8; --paper: #fdfdf9; --grout: #c8cfcd; --well: #34433e;
  --ink: #263430; --muted: #64716b;
  --glint: #ffffffd9; --paper-glint: #fff;
  --pole-a: #995c10; --pole-b: #306b9e; --ok: #246a43; --bad: #ad313d;
  --ramp-l: 0.42; --ramp-c: 0.12; --backlight: 14%;
  --a-l0: -0.02; --a-l1: 0.44;  --a-l2: -0.44;
  --b-l0: 0.23;  --b-l1: -0.36; --b-l2: 0.18;
  color-scheme: light;
}

/* --- 1. A pole (lane) says which half of the wheel its items live on ------ */
.lane {
  --rail: var(--pole-a);
  --arc-start: var(--a-start);
  --arc-end: var(--a-end);
  --is-b: 0;
  --lane-l: calc(var(--ramp-l) + var(--a-lift));
}
.lane[data-lane='b'] {
  --rail: var(--pole-b);
  --arc-start: var(--b-start);
  --arc-end: var(--b-end);
  --is-b: 1;
  --lane-l: calc(var(--ramp-l) - var(--b-drop));
}

/* --- 2. Identity: rank -> hue ---------------------------------------------
   Declare --rank (0..1) on EVERY element that wears the colour (the row, the
   chip, the slots, the tile). Custom properties are substituted where they
   are declared, so each place computes its own hue where that hue is shown. */
.lane > li, .chip, .slot, .tile {
  --hue: calc(var(--arc-start) + var(--rank, 0) * (var(--arc-end) - var(--arc-start)));
  --contour: calc(
    (1 - var(--is-b)) * (var(--a-l0) + var(--a-l1) * var(--rank, 0) + var(--a-l2) * var(--rank, 0) * var(--rank, 0)) +
    var(--is-b)       * (var(--b-l0) + var(--b-l1) * var(--rank, 0) + var(--b-l2) * var(--rank, 0) * var(--rank, 0))
  );
  --l: calc(var(--lane-l) + var(--contour));
  --tint:  oklch(var(--l) var(--ramp-c) var(--hue));
  --ember: oklch(var(--l) calc(var(--ramp-c) * var(--ember-chroma)) var(--hue));
  --flame: oklch(var(--l) calc(var(--ramp-c) * var(--flame-chroma)) var(--hue));
}

/* --- 3. Material ----------------------------------------------------------- */
/* Glass: ONLY on a few large floating instruments. Never per item. */
.glass {
  border: 1px solid color-mix(in oklab, var(--ink) 10%, transparent);
  background: color-mix(in oklab, var(--panel) 76%, transparent);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  backdrop-filter: blur(14px) saturate(140%);
  box-shadow: inset 0 1px 0 var(--glint), 0 18px 40px -18px #00000038, 0 2px 6px #00000030;
}

/* The chip: numeral wears the item's colour; frame wears the pole's. */
.chip {
  display: inline-grid;
  place-items: center;
  width: 42px;
  height: 32px;
  box-sizing: border-box;
  border: 1px solid color-mix(in oklab, var(--rail) 50%, var(--bg));
  border-radius: 8px;
  background: linear-gradient(180deg, color-mix(in oklab, var(--rail) 10%, var(--bg)), var(--bg));
  color: var(--tint);
  font: 700 1.12rem var(--face);
  font-variant-numeric: tabular-nums lining-nums;
  /* Ember: the resting light, mostly inside the border. */
  box-shadow:
    inset 0 1px 0 var(--glint),
    0 3px 8px -4px #000c,
    inset 0 0 6px color-mix(in oklab, var(--ember) var(--ember-alpha), transparent),
    0 0 9px color-mix(in oklab, var(--ember) var(--ember-alpha), transparent);
  transition: transform var(--dur-quick) var(--ease-out);
}
/* Hover is attention, not selection: more light, same hue. */
li:hover > .chip {
  box-shadow:
    inset 0 1px 0 var(--glint),
    0 3px 8px -4px #000c,
    inset 0 0 6px color-mix(in oklab, var(--ember) var(--cross-alpha), transparent),
    0 0 10px color-mix(in oklab, var(--ember) var(--cross-alpha), transparent);
}
/* Flame: the same hue, saturated and solid. Halo: the pole's own colour. */
li.is-selected > .chip {
  background: var(--flame);
  border-color: var(--flame);
  color: var(--bg);
  box-shadow:
    inset 0 1px 0 var(--glint),
    inset 0 0 7px color-mix(in oklab, var(--flame) calc(var(--flame-alpha) * var(--glow-pulse, 1)), transparent),
    0 0 13px color-mix(in oklab, var(--rail) var(--halo-alpha), transparent),
    0 4px 12px -4px #000c;
  animation: ignite var(--dur-ignite) cubic-bezier(0.2, 0.7, 0.2, 1) both;
}

/* On paper a solid flame fill cannot carry text at 4.5:1 (measured 3.6 to 4.45). The
   selected chip keeps the item's colour as a tinted ground, a flame border and the glow,
   with ink for the numeral. */
.afterglow[data-theme='light'] li.is-selected > .chip {
  background: color-mix(in oklab, var(--flame) 22%, var(--paper));
  border-color: var(--flame);
  color: var(--ink);
}

/* Ignition: the light flares ONCE as something is selected, then settles.
   Nothing translates; only the glow's alpha moves; it never loops. */
@keyframes ignite { from { --glow-pulse: 2; } to { --glow-pulse: 1; } }

/* --- 4. Vibration: micro-feedback on contact -------------------------------- */
.press { transition: transform var(--dur-quick) var(--ease-out), border-color var(--dur-quick) var(--ease-out); }
.press:hover  { transform: translateY(-1px); }
.press:active { transform: translateY(0) scale(0.97); transition-duration: 60ms; }

/* A letter (any committed input) arrives, it does not appear. */
.arrive { animation: arrive 160ms ease-out; }
@keyframes arrive {
  from { opacity: 0.35; transform: translateY(2px) scale(0.94); }
  to   { opacity: 1;    transform: translateY(0)   scale(1); }
}

/* --- 5. Afterglow: what a finished thing leaves behind ----------------------
   The tile flares once from inside in its own hue, then rests as clean paper
   with only a trace of the hue left in its ink. */
.tile {
  --cell: 3rem;
  width: var(--cell); height: var(--cell);
  box-sizing: border-box;
  display: inline-grid; place-items: center;
  background: var(--paper);
  border: 1px solid var(--grout);
  box-shadow: inset 0 1px 0 var(--paper-glint);
  font: 600 1.4rem var(--face);
  text-transform: uppercase;
}
.tile[data-done] {
  box-shadow:
    inset 0 1px 0 var(--paper-glint),
    inset 0 0 calc(var(--cell) * 0.55) color-mix(in oklab, var(--tint) calc(58% * var(--settle)), transparent);
  color: color-mix(in oklab, var(--ink) 80%, var(--tint));
  animation: settle 1800ms var(--ease-out) both;
}
@keyframes settle { from { --settle: 1; } to { --settle: 0; } }

/* --- 6. Territory: the ground is lit by what is on screen -------------------
   Publish the ranks of the items visible in the four screen corners as
   --ta-top / --ta-bottom / --tb-top / --tb-bottom (0..1) on .ground. The four
   corner colours are exactly the hues of those items. Registered numbers
   transition, so the light drifts as the lists scroll. */
.ground {
  --remaining: 1;   /* 1 -> 0 as the work is finished */
  --libido: 1;      /* 0..1: how much of the desire the session has kept */
  /* One charge of light shared among what is still open. */
  --charge: clamp(0.18, calc(var(--libido) * pow(max(var(--remaining), 0.05), -0.5)), 2.6);
  position: relative;
  isolation: isolate;
  transition:
    --ta-top 900ms var(--ease-out), --ta-bottom 900ms var(--ease-out),
    --tb-top 900ms var(--ease-out), --tb-bottom 900ms var(--ease-out);
  --c-tl: oklch(calc(var(--ramp-l) + var(--a-lift) + var(--a-l0) + var(--a-l1) * var(--ta-top) + var(--a-l2) * var(--ta-top) * var(--ta-top)) calc(var(--ramp-c) * var(--glow-chroma)) calc(var(--a-start) + var(--ta-top) * (var(--a-end) - var(--a-start))));
  --c-bl: oklch(calc(var(--ramp-l) + var(--a-lift) + var(--a-l0) + var(--a-l1) * var(--ta-bottom) + var(--a-l2) * var(--ta-bottom) * var(--ta-bottom)) calc(var(--ramp-c) * var(--glow-chroma)) calc(var(--a-start) + var(--ta-bottom) * (var(--a-end) - var(--a-start))));
  --c-tr: oklch(calc(var(--ramp-l) - var(--b-drop) + var(--b-l0) + var(--b-l1) * var(--tb-top) + var(--b-l2) * var(--tb-top) * var(--tb-top)) calc(var(--ramp-c) * var(--glow-chroma)) calc(var(--b-start) + var(--tb-top) * (var(--b-end) - var(--b-start))));
  --c-br: oklch(calc(var(--ramp-l) - var(--b-drop) + var(--b-l0) + var(--b-l1) * var(--tb-bottom) + var(--b-l2) * var(--tb-bottom) * var(--tb-bottom)) calc(var(--ramp-c) * var(--glow-chroma)) calc(var(--b-start) + var(--tb-bottom) * (var(--b-end) - var(--b-start))));
}
.ground::before {
  content: '';
  position: absolute;
  z-index: -1;
  inset: -4rem;
  pointer-events: none;
  --a: calc(var(--backlight) * max(var(--libido), 0.3));
  background:
    radial-gradient(50% 46% at 4rem 4rem,                       color-mix(in oklab, var(--c-tl) var(--a), transparent), transparent),
    radial-gradient(50% 46% at calc(100% - 4rem) 4rem,          color-mix(in oklab, var(--c-tr) var(--a), transparent), transparent),
    radial-gradient(50% 46% at 4rem calc(100% - 4rem),          color-mix(in oklab, var(--c-bl) var(--a), transparent), transparent),
    radial-gradient(50% 46% at calc(100% - 4rem) calc(100% - 4rem), color-mix(in oklab, var(--c-br) var(--a), transparent), transparent);
  /* The layer fades to nothing at its rim, so no light is cut by a box edge. */
  -webkit-mask-image:
    linear-gradient(90deg, transparent, #000 4rem, #000 calc(100% - 4rem), transparent),
    linear-gradient(180deg, transparent, #000 4rem, #000 calc(100% - 4rem), transparent);
  -webkit-mask-composite: source-in;
  mask-image:
    linear-gradient(90deg, transparent, #000 4rem, #000 calc(100% - 4rem), transparent),
    linear-gradient(180deg, transparent, #000 4rem, #000 calc(100% - 4rem), transparent);
  mask-composite: intersect;
}

/* --- 7. View tiers: the reader's own dials --------------------------------
   JS publishes settings as data-* on the root; CSS owns every appearance.
   mini = comfort, micro = reading aids, nano = fine cues. */
.afterglow[data-vibrance='soft'] {
  --ramp-c: 0.095; --ember-chroma: 0.55; --flame-chroma: 1.4;
  --ember-alpha: 10%; --cross-alpha: 16%; --flame-alpha: 26%; --halo-alpha: 14%;
}
.afterglow[data-vibrance='bold'] {
  --ramp-c: 0.18; --ember-chroma: 0.8; --flame-chroma: 1.9;
  --ember-alpha: 17%; --cross-alpha: 26%; --flame-alpha: 39%; --halo-alpha: 24%;
}
.afterglow[data-ramp='off'] { --ramp-c: 0; --ramp-l: 0.72; }
.afterglow[data-scale='compact'] { --scale: 0.9; }
.afterglow[data-scale='full']    { --scale: 1.16; }

/* Low-bloom: a dim or smudged screen blooms at highlights, not midtones. Take
   the bloom away; keep the structure and the hue. Lower the plane, keep the ink. */
.afterglow:is([data-luma='dim'], [data-luma='veil']) {
  --ember-alpha: 0%; --cross-alpha: 0%; --flame-alpha: 11%; --halo-alpha: 6%;
  --ink: #e3e8ee; --muted: #9ba5b1; --paper: #262b33; --grout: #4f5863;
  --backlight: 20%;
}
.afterglow[data-luma='veil'] { --bg: #10151b; --panel: #191f26; --backlight: 12%; }
.afterglow:is([data-luma='dim'], [data-luma='veil']) :is(.chip, .tile) { text-shadow: none; }

/* Best-effort glow: set data-glow="off" for a frame or two after the selection
   changes, so blurred shadows are not painted on the expensive first frame. */
.afterglow[data-glow='off'] li.is-selected > .chip { box-shadow: none !important; animation: none !important; }

/* --- 8. The View panel -------------------------------------------------------
   A native <details>: keyboard and screen-reader correct for free. Opens UPWARD
   from the dock (the ground owns the space above it) and scrolls rather than
   running past a short window. The pressed choice takes its tier's accent so a
   row is recognisable by colour alone: comfort green, reading amber, cues blue. */
.view-cluster { position: relative; }
.view-cluster-summary {
  display: inline-flex; align-items: center; height: 40px; padding: 0 10px;
  border-radius: 8px; color: var(--muted); font-size: 0.78rem; font-weight: 600;
  letter-spacing: 0.04em; list-style: none; cursor: pointer;
  transition: color var(--dur-quick) var(--ease-out), background-color var(--dur-quick) var(--ease-out), transform var(--dur-quick) var(--ease-out);
}
.view-cluster-summary::-webkit-details-marker { display: none; }
.view-cluster-summary:hover, .view-cluster[open] .view-cluster-summary {
  background: color-mix(in oklab, var(--ink) 8%, transparent); color: var(--ink);
}
.view-cluster-summary:active { transform: scale(0.96); transition-duration: 60ms; }
.view-cluster-panel {
  position: absolute; z-index: 30; right: 0; bottom: calc(100% + 8px);
  display: grid; gap: 9px; width: 300px; padding: 12px; box-sizing: border-box;
  border: 1px solid var(--panel-edge); border-radius: 12px;
  background: linear-gradient(180deg, var(--panel-light), var(--panel));
  box-shadow: 0 14px 34px -12px rgba(0, 0, 0, 0.8);
  max-height: min(72dvh, 620px); overflow: auto;
}
.view-tier { display: grid; gap: 6px; margin: 0; padding: 8px; border: 1px solid color-mix(in oklab, var(--ink) 7%, transparent); border-radius: 10px; }
.view-tier legend { display: flex; align-items: baseline; gap: 6px; padding: 0 4px; color: var(--muted); font-size: 0.62rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; }
.view-tier-hint { letter-spacing: 0.04em; text-transform: none; opacity: 0.75; }
.view-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.view-row-label { font-size: 0.76rem; }
.view-choices { display: inline-flex; gap: 4px; }
.view-choice {
  min-height: 28px; padding: 2px 9px; border: 1px solid var(--panel-edge); border-radius: 8px;
  background: var(--panel-light); color: var(--muted); font: inherit; font-size: 0.72rem; font-weight: 600; cursor: pointer;
}
.view-choice:hover { border-color: var(--muted); color: var(--ink); }
.view-choice[aria-pressed='true'] { border-color: currentColor; color: var(--ink); box-shadow: inset 0 1px 0 var(--glint); }
.view-tier[data-tier='mini']  .view-choice[aria-pressed='true'] { color: var(--ok); }
.view-tier[data-tier='micro'] .view-choice[aria-pressed='true'] { color: var(--pole-a); }
.view-tier[data-tier='nano']  .view-choice[aria-pressed='true'] { color: var(--pole-b); }
.view-reset { justify-self: start; padding: 2px 0; border: 0; background: none; color: var(--muted); font: inherit; font-size: 0.7rem; text-decoration: underline; cursor: pointer; }
.view-reset:hover { color: var(--ink); }
/* On a phone the panel is centred on its button so it cannot fall off the screen. (Do not use
   position: fixed here: a parent with backdrop-filter or transform becomes its containing block.) */
@media (max-width: 700px) {
  .view-cluster-panel { right: auto; left: 50%; transform: translateX(-50%); width: min(300px, calc(100vw - 16px)); }
}
.afterglow :is(button, a, summary, select):focus-visible { outline: 2px solid var(--pole-b); outline-offset: 3px; }

@media (prefers-contrast: more) { .afterglow { --grout: #6b7480; --panel-edge: #78818c; } }

/* Finite motion only, and only if the reader allows it. The light stays. */
@media (prefers-reduced-motion: reduce) {
  .afterglow *, .afterglow *::before, .afterglow *::after {
    animation: none !important;
    transition: none !important;
  }
}
```

### 14.2 `view-settings.js`: the JS side of the contract

```js
// view-settings.js — the whole contract between JS and CSS.
// Three tiers, smallest surface first. Everything is presentation only,
// persisted locally, and published as data-* attributes on the root element.
// JS never sets colours, sizes or shadows; it only names a state.

export const VIEW_SETTINGS_KEY = 'myapp.view.v1';

export const TIERS = [
  { key: 'mini', title: 'Mini', hint: 'Comfort', rows: [
    { key: 'luma', label: 'Brightness', options: ['standard', 'dim', 'veil'] },
    { key: 'scale', label: 'Size', options: ['compact', 'normal', 'full'] },
  ] },
  { key: 'micro', title: 'Micro', hint: 'Reading aids', rows: [
    { key: 'ramp', label: 'Item colours', options: [false, true] },
    { key: 'vibrance', label: 'Colour intensity', options: ['soft', 'vivid', 'bold'] },
  ] },
  { key: 'nano', title: 'Nano', hint: 'Fine cues', rows: [
    { key: 'cues', label: 'Edge cues', options: [false, true] },
    { key: 'glyph', label: 'Letter weight', options: ['regular', 'firm'] },
  ] },
];

export const VIEW_DEFAULTS = {
  luma: 'standard', scale: 'normal', ramp: true, vibrance: 'vivid',
  cues: true, glyph: 'regular',
};

const OPTIONS = Object.fromEntries(
  TIERS.flatMap((tier) => tier.rows).map((row) => [row.key, row.options]),
);

// Never trust storage: unknown values fall back to the default.
export function normalizeViewSettings(value, defaults = VIEW_DEFAULTS) {
  const stored = value && typeof value === 'object' ? value : {};
  return Object.fromEntries(
    Object.keys(defaults).map((key) => [
      key,
      OPTIONS[key].includes(stored[key]) ? stored[key] : defaults[key],
    ]),
  );
}

// A display that reports reduced contrast or transparency usually blooms or
// washes out: pick the dim tier on a first visit. A stored choice always wins.
export function prefersLowBloom(media = globalThis.matchMedia?.bind(globalThis)) {
  if (typeof media !== 'function') return false;
  return ['(prefers-contrast: less)', '(prefers-reduced-transparency: reduce)']
    .some((query) => media(query)?.matches === true);
}

export function readViewSettings({ storage = globalThis.localStorage, media } = {}) {
  const defaults = { ...VIEW_DEFAULTS, luma: prefersLowBloom(media) ? 'dim' : 'standard' };
  let stored = null;
  try { stored = JSON.parse(storage?.getItem?.(VIEW_SETTINGS_KEY) ?? 'null'); } catch { stored = null; }
  return normalizeViewSettings(stored, defaults);
}

export function writeViewSettings(settings, { storage = globalThis.localStorage } = {}) {
  try { storage?.setItem?.(VIEW_SETTINGS_KEY, JSON.stringify(settings)); } catch { /* private mode must not break the app */ }
}

// booleans become 'on' | 'off' so CSS can write [data-ramp='off'].
export function viewAttributes(settings) {
  return Object.fromEntries(
    Object.entries(settings).map(([key, value]) => [
      `data-${key}`,
      typeof value === 'boolean' ? (value ? 'on' : 'off') : value,
    ]),
  );
}

export function applyViewSettings(root, settings) {
  for (const [name, value] of Object.entries(viewAttributes(settings))) root.setAttribute(name, value);
}

// The rank -> colour mapping: rank, not value, so any list length spreads evenly
// across the whole arc. Items that share an identity (the same number in two
// lists) share one rank, so a colour learned in one place is found in the other.
export function createRamp(ids) {
  const unique = [...new Set(ids)].sort((a, b) => a - b);
  const span = unique.length > 1 ? unique.length - 1 : 1;
  return new Map(unique.map((id, rank) => [id, Math.round((rank / span) * 1000) / 1000]));
}
```

### 14.3 `fit-contour.mjs`: fit the contour for your own arcs

Run when you change the arcs, chroma or base lightness.

```js
// fit-contour.mjs — fit the lightness contour (l0, l1, l2) for one hue arc.
//
// Why: at a fixed lightness, sRGB holds very different chroma at different
// hues (yellow/green generous; pink/orange/violet/blue tight). One lightness
// per arc therefore clips the tight hues (paler, shifted off their rank) while
// the easy ones stay vivid, and the rainbow steps unevenly. The fix is a small
// per-rank lightness offset  l0 + l1*r + l2*r^2.
//
// Usage:  node fit-contour.mjs <hueStart> <hueEnd> <chroma> <baseL> [margin]
//   e.g.  node fit-contour.mjs 2 142 0.14 0.89        (warm arc, dark ground)
//         node fit-contour.mjs 183 323 0.14 0.75      (cool arc, dark ground)
// Paste the three printed numbers into --a-l0/--a-l1/--a-l2 (or --b-*).
// The crossword's own values were tuned by eye; this reproduces their shape
// (light mode matches closely) and is meant as a first draft to judge by eye.
// baseL is the lane's lightness INCLUDING its lift/drop: ramp-l + a-lift, or
// ramp-l - b-drop. Treat the result as a starting point and judge it by eye.

const [, , hs, he, cs, bl, mg = '0.02'] = process.argv;
const hueStart = Number(hs), hueEnd = Number(he), chroma = Number(cs), baseL = Number(bl), margin = Number(mg);
if ([hueStart, hueEnd, chroma, baseL].some(Number.isNaN)) {
  console.error('usage: node fit-contour.mjs <hueStart> <hueEnd> <chroma> <baseL> [margin]');
  process.exit(1);
}

// OKLCH -> linear sRGB (Björn Ottosson's matrices).
function inGamut(L, C, hDeg) {
  const h = (hDeg * Math.PI) / 180;
  const a = C * Math.cos(h), b = C * Math.sin(h);
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = L - 0.0894841775 * a - 1.2914855480 * b;
  const l = l_ ** 3, m = m_ ** 3, s = s_ ** 3;
  const r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s;
  const g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s;
  const bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s;
  const eps = 1e-4;
  return [r, g, bb].every((v) => v >= -eps && v <= 1 + eps);
}

// For one rank: the lightness closest to baseL that keeps the colour in gamut
// with `margin` to spare. Scan outward from baseL in small steps.
function bestL(r) {
  const hue = hueStart + r * (hueEnd - hueStart);
  for (let d = 0; d <= 0.6; d += 0.005) {
    for (const L of d === 0 ? [baseL] : [baseL - d, baseL + d]) {
      if (L > 0.05 && L < 0.98 && inGamut(L - margin, chroma, hue) && inGamut(L + margin, chroma, hue)) return L;
    }
  }
  return baseL;
}

const samples = Array.from({ length: 41 }, (_, i) => i / 40);
const offsets = samples.map((r) => bestL(r) - baseL);

// Least-squares quadratic fit: offset ~ l0 + l1*r + l2*r^2 (normal equations).
const S = (f) => samples.reduce((acc, r, i) => acc + f(r, offsets[i]), 0);
const A = [
  [samples.length, S((r) => r), S((r) => r * r)],
  [S((r) => r), S((r) => r * r), S((r) => r ** 3)],
  [S((r) => r * r), S((r) => r ** 3), S((r) => r ** 4)],
];
const B = [S((r, y) => y), S((r, y) => r * y), S((r, y) => r * r * y)];
for (let i = 0; i < 3; i++) {
  const p = A[i][i];
  for (let j = i; j < 3; j++) A[i][j] /= p;
  B[i] /= p;
  for (let k = 0; k < 3; k++) {
    if (k === i) continue;
    const f = A[k][i];
    for (let j = i; j < 3; j++) A[k][j] -= f * A[i][j];
    B[k] -= f * B[i];
  }
}
const [l0, l1, l2] = B.map((v) => Math.round(v * 1000) / 1000);

// Report how well the fitted curve keeps the arc in gamut.
let clipped = 0;
for (const r of samples) {
  const hue = hueStart + r * (hueEnd - hueStart);
  if (!inGamut(baseL + l0 + l1 * r + l2 * r * r, chroma, hue)) clipped += 1;
}
console.log(`l0: ${l0}   l1: ${l1}   l2: ${l2}`);
console.log(`ranks still outside sRGB with this fit: ${clipped} of ${samples.length}`);
console.log('Browsers gamut-map the remainder by quietly lowering chroma, so a few is fine.');
console.log('If more than a quarter are outside, lower the chroma, shorten the arc, or move baseL.');
```

### 14.4 `territory.js`: publish what is in the four corners

```js
// territory.js — publish the ranks of the items showing in the four corners of
// the screen, so the ground's light is exactly the hue of what is on screen.
// Call once per page; it re-publishes (rAF-throttled) whenever a lane scrolls.
// Each item must carry its rank as an inline custom property: style="--rank:0.43".

function edgeRanks(lane) {
  const box = lane.getBoundingClientRect();
  const visible = [...lane.querySelectorAll(':scope > li')].filter((li) => {
    const r = li.getBoundingClientRect();
    return r.bottom > box.top && r.top < box.bottom;
  });
  if (!visible.length) return null;
  const rank = (li) => parseFloat(li.style.getPropertyValue('--rank')) || 0;
  return { top: rank(visible[0]), bottom: rank(visible[visible.length - 1]) };
}

export function publishTerritory(ground, laneA, laneB) {
  let queued = false;
  const publish = () => {
    queued = false;
    const a = edgeRanks(laneA);
    const b = edgeRanks(laneB);
    if (a) { ground.style.setProperty('--ta-top', a.top); ground.style.setProperty('--ta-bottom', a.bottom); }
    if (b) { ground.style.setProperty('--tb-top', b.top); ground.style.setProperty('--tb-bottom', b.bottom); }
  };
  const schedule = () => { if (!queued) { queued = true; requestAnimationFrame(publish); } };
  laneA.addEventListener('scroll', schedule, { passive: true });
  laneB.addEventListener('scroll', schedule, { passive: true });
  addEventListener('resize', schedule);
  schedule();
  return () => {
    laneA.removeEventListener('scroll', schedule);
    laneB.removeEventListener('scroll', schedule);
    removeEventListener('resize', schedule);
  };
}
```

### 14.5 Markup skeleton

```html
<main class="afterglow" id="root" data-theme="dark">
  <div class="glass" id="masthead"><!-- name, the two numbers you glance at, a progress line --></div>

  <div class="stage">
    <ul class="lane" data-lane="a" id="lane-a">
      <li style="--rank:0">
        <b class="chip" style="--rank:0">1</b>
        <div class="content">
          <span class="text">…</span>
          <div class="slots"><i class="slot" style="--rank:0"></i> …</div>
        </div>
      </li>
      <!-- more rows; .is-selected on the active row -->
    </ul>

    <div class="ground" id="ground" style="--ta-top:0;--ta-bottom:1;--tb-top:0;--tb-bottom:1">
      <!-- the work surface: tiles/cells with --rank where they begin an item -->
    </div>

    <ul class="lane" data-lane="b" id="lane-b"> … </ul>
  </div>

  <nav class="glass" id="dock">
    <!-- 3 equal commands (Check, Reveal, Complete) and a quiet tray of glyphs, incl. the View <details> -->
  </nav>
</main>
```

### 14.6 `view-panel.js`: the View panel (vanilla, built from `TIERS`)

```js
import { TIERS, readViewSettings, writeViewSettings, applyViewSettings, VIEW_DEFAULTS } from './view-settings.js';

export function mountViewPanel(root, host) {
  let settings = readViewSettings();
  applyViewSettings(root, settings);
  host.innerHTML = `
    <details class="view-cluster"><summary class="view-cluster-summary" title="Adjust how this reads">View</summary>
      <div class="view-cluster-panel">${TIERS.map((t) => `
        <fieldset class="view-tier" data-tier="${t.key}">
          <legend><span>${t.title}</span><span class="view-tier-hint">${t.hint}</span></legend>
          ${t.rows.map((r) => `
            <div class="view-row"><span class="view-row-label">${r.label}</span>
              <span class="view-choices" role="group" aria-label="${r.label}">
                ${r.options.map((o) => `<button type="button" class="view-choice" data-key="${r.key}" data-value="${o}" aria-pressed="${settings[r.key] === o}">${typeof o === 'boolean' ? (o ? 'On' : 'Off') : o}</button>`).join('')}
              </span></div>`).join('')}
        </fieldset>`).join('')}
        <button type="button" class="view-reset">Reset to defaults</button>
      </div>
    </details>`;
  const sync = () => { applyViewSettings(root, settings); writeViewSettings(settings);
    host.querySelectorAll('.view-choice').forEach((b) => b.setAttribute('aria-pressed', String(String(settings[b.dataset.key]) === b.dataset.value))); };
  host.addEventListener('click', (e) => {
    const b = e.target.closest('.view-choice'); const r = e.target.closest('.view-reset');
    if (b) { const cur = settings[b.dataset.key]; settings = { ...settings, [b.dataset.key]: typeof cur === 'boolean' ? b.dataset.value === 'true' : b.dataset.value }; sync(); }
    if (r) { settings = { ...VIEW_DEFAULTS }; sync(); }
  });
}
```

Style the panel with: a matte panel (`linear-gradient(var(--panel-light), var(--panel))`, 12px radius, 1px edge), tier fieldsets with a 7% white hairline and 10px radius, segmented buttons (28px min-height, 8px radius), the pressed button taking the tier accent (`mini` green `--ok`, `micro` orange `--pole-a`, `nano` blue `--pole-b`), and `max-height: min(72dvh, 620px); overflow: auto`.

### 14.7 Publishing state from React (what the source does)

```jsx
<div id="app" className="afterglow"
     data-direction={activeDirection}
     data-glow={glowOn ? 'on' : 'off'}
     {...viewAttributes(settings)}
     style={{
       '--remaining': String(open / total),
       '--libido': String(Math.round(Math.pow(Math.min(1, Math.max(0, score / 100)), 1.25) * 1000) / 1000),
       ...(activeRank != null ? { '--active-rank': String(activeRank) } : {}),
     }}>
```

- Row, chip, slots and cells each get `style={{ '--rank': ramp.get(id) }}` **only when `settings.ramp` is on**.
- JS only *names* things (`data-solved`, `data-start`, `data-gate-solved`, `data-entry-index`). The look belongs to CSS.
- The source derives "solved squares" and "solved openings" from the controller's completed set on every render and stores nothing.

---

## 15. Lessons learned: the bug museum

Each row is something that actually went wrong in the source (items 29 to 37 went wrong while building this guide's starter and test suite). Read the "rule" column before you write the corresponding CSS.

| # | Symptom | Cause | Rule |
| --- | --- | --- | --- |
| 1 | The "Bold" colour setting did nothing; light mode lost its deeper number colours | Two stray closing braces: the browser dropped the rule after each | Lint CSS. Verify computed styles (R31). |
| 2 | "Board size L" clipped the 15th column by ~31px | Rules targeted classes the markup never renders | Check selectors match the real DOM; measure the result. |
| 3 | Rows changed height on every cursor move | Active/crossing clues switched to bold, rewrapping | Emphasis by `-webkit-text-stroke`, never by weight (§8.5). |
| 4 | A check verdict hid the clue number | A dark index on dark red fill | Re-check legibility in every state combination. |
| 5 | Dangling separator after the weekday; View button shorter than the other buttons | Layout drift | Visual review at 1440×1000 after each slice. |
| 6 | Eight looping pulses repainted blurred shadows every frame | Infinite `box-shadow` animations at different periods | Nothing loops; ignite once (R14, §9.3). |
| 7 | A run of empty squares read as one bar | Seams were *lighter* than the squares | Seams are darker than the surface (grout) (R9). |
| 8 | The board had no figure: the frame was as bright as what it framed | Squares L 0.31 below the panel's highlight L 0.33 | Work surface is the lightest surface (R8). |
| 9 | Lettering contrast fell from ~10:1 to ~2.7:1 along a word | The lit word faded *lightness* | Hold lightness, fade chroma (R5). |
| 10 | Pink, orange and violet looked pale and drifted off their rank | One lightness per arc clipped sRGB at the tight hues | Contour offset (R6, §6.3). |
| 11 | Hues mixed to olive and mauve across the board | The spill's `1/(1+0.45d)` tail reached the whole word | Linear falloff, gone by the 3rd square (§10.4). |
| 12 | A wrapped strip started with a "black bar" in light mode | Heavy seam mixed 55% black | 28%; judge in both themes. |
| 13 | A two-digit corner number touched the capital | Letter dead-centre at 52% | Letter sits slightly low at 50% (§8.4). |
| 14 | The backlight read as two tones, salmon left and teal right | Corner glows were offset box-shadows of the whole board | Four separate radial layers on a layer behind (§6.7). |
| 15 | Clues' hues were 40° apart at the top and bottom of one screen, too close to tell apart once blurred | Only about a third of a lane is on screen | The light uses exactly the on-screen hues, ×1.3 chroma. |
| 16 | The widened-gap fix made green glow under orange clues | The light disagreed with the lanes | R27: the light is exactly the hue of what is on screen. |
| 17 | A dark vertical band beside the board | A large drop shadow cast "onto nothing" | A ground casts no shadow (R11). |
| 18 | Five equal stats coloured orange and blue | Colour that said nothing about direction | R1: remove colour that names nothing. |
| 19 | A previous agent flattened the zig-zag clue layout to a single column; fully reverted | It replaced a loved language instead of deepening it | R30: list keeps, then evolve. |
| 20 | The agent could not tell an answered box from an empty one by CSS | React keeps an empty text node in every box, so `:empty` never matches | Let ink carry the state; or change the DOM deliberately, not by selector tricks. |
| 21 | A negative-z-index stroke painted *above* its element's background | The `translateY` that creates the zig-zag makes a stacking context | Draw only the visible stub; don't rely on negative z-index inside a transformed parent. |
| 22 | A hue didn't update where it was shown | Custom properties substitute where *declared* | Declare `--rank` on every wearer (§3.3). |
| 23 | Ramp stepped unevenly on a short puzzle | Ramp by value, not by rank | Rank by index / (n − 1) (R2). |
| 24 | A track broke 5/5/1 | Naive chunking | Balanced runs 4/4/3 (§7.4). |
| 25 | Cursor glow bloomed on a dim or bright smudged screen | Highlights bloom, not midtones | Low-bloom tiers: lower the plane, keep the ink (R18). |
| 26 | The first frame after a selection janked | Blurred shadows painted at once | Best-effort glow gate (`data-glow="off"`) for a frame (§7.7). |
| 27 | Every direction switch forced a synchronous layout | Re-measuring every chip | Cache measured geometry; re-measure only on resize/font/row change. |
| 28 | A whole screen read as "a stack of framed boxes" | The old console panel was a rounded frame | The ground and floating instruments (macro, §7.2). |
| 29 | *(this guide's starter)* The Dim tier did not dim the backlight | `--backlight` was declared on `.ground`, so the tier on the root could not override it | A token must be declared on the root; elements *consume*, tiers *set*. |
| 30 | *(this guide's starter)* The backlight showed hard rectangular edges | The gradient layer had no rim mask | Fade the light layer to nothing at its rim with a two-axis `mask-image` (intersect). |
| 31 | *(this guide's starter)* The View panel rendered black serif text on a dark ground | The panel was mounted outside the element that declares the tokens, so it inherited none of them | Tokens live on a root. Anything mounted elsewhere (portals, modals, tooltips on `<body>`) must be mounted *inside* the root, or the tokens must be declared on `:root`. |
| 32 | *(this guide's starter)* The selected chip's text was under 4.5:1 on paper | A solid flame fill with dark text measured 3.6 to 4.45:1 in the light theme | A tinted ground with ink text on paper. Measure contrast, do not eyeball it (R5). |
| 33 | *(this guide's test suite)* A "reduced motion" test ran with motion on | `reducedMotion` is not a top-level `use` option in Playwright 1.55; it is silently ignored | `contextOptions: { reducedMotion }`, and assert the media query is really on (§17.10). |
| 34 | *(this guide's starter)* A phone page was wider than the screen and taps missed their targets | The backlight pseudo-element reached 4rem past its box, so the layout viewport grew | `overflow-x: clip` on the root; compare `scrollWidth` with the configured viewport width, never `innerWidth`. |
| 35 | *(this guide's test suite)* The overflow check passed while content was cut off | The `overflow-x: clip` that fixed item 34 hides overflow from `scrollWidth` | Also measure every element's right edge. A fix can blind the check that found the bug. |
| 36 | *(this guide's test suite)* A visible recolour passed the screenshot test | Playwright's default per-pixel `threshold` is 0.2 | `threshold: 0.05` with `maxDiffPixelRatio: 0.002` (§17.4). |
| 37 | *(this guide's starter)* A journey that scrolls a lane could not scroll | The lane was shorter than its container | Give the lane a fixed `max-height` in the demo, and let the journey fail loudly when nothing moves. |

---

## 16. Applying it to a new project

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

## 17. UI testing: Playwright journeys, screenshots and CI

This section turns "does it match the design language?" from an opinion into a command that exits 0 or does not. It is also what stops an agent from declaring victory early.

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

### 17.5 Design contracts as assertions

`expectContracts(page, cfg, { luma, reduced })` runs these inside the page and reports **all** failures at once (soft assertions). They are the measurable half of the guide:

| Probe id | Asserts | Rule |
| --- | --- | --- |
| `no-infinite-animations` | no animation or transition with infinite iterations | R14 |
| `reduced-motion-stops-motion` | with reduced motion emulated, nothing runs | R17 |
| `tokens-resolve` | required custom properties resolve on the root | 14.1 |
| `low-bloom-tier` | on Dim/Veil the bloom tokens are lowered | R18 |
| `identity-ranks-published` | at least 4 distinct `--rank` values on items | R1, R2 |
| `identity-on-two-surfaces` | a rank appears on 2+ different surfaces | R26 |
| `identity-colour-follows-rank` | same rank and pole produce the same colour everywhere | R27 |
| `identity-colours-vary` | the ramp actually produces different colours | R2, R6 |
| `contrast <selector>` | measured WCAG contrast of text on its (solid) background | R5 |
| `glass-budget` | at most N elements use `backdrop-filter`, none repeated 3+ times | R10 |
| `no-horizontal-overflow` | page is no wider than the true viewport | layout |

Plus, on every test: **no uncaught exception and no `console.error`**, and **keyboard focus is visible** (`[D2]`).

**The view matrix** (`[D1]`) crosses brightness (`lumas`) × colour intensity (`vibrances`) with every project's viewport × theme, asserts the probes and takes a screenshot of each. That is the "test the corners of the dial matrix" rule (§5.2) made executable.

### 17.6 Updating baselines (never blindly)

`--update-snapshots` overwrites the evidence. The protocol:

1. Run the suite. Read every failure. A screenshot diff is either a **bug** (fix the code) or an **intended change** (update the baseline).
2. For an intended change, update only the affected tests: `npx playwright test -g "J3" --update-snapshots`, not the whole suite.
3. **Open every changed image** (and the diff in `playwright-report`). Describe each in one sentence in the ledger: what changed and why that is intended. A weaker agent that cannot view images must say so, and the user reviews the diffs.
4. Commit the new PNGs in the *same* commit as the code that changed them, so review shows both.
5. Never run a blanket `--update-snapshots` to turn a red run green.

### 17.7 CI

- `ci/design-e2e.yml` runs on every pull request and on pushes to the default branch: install, static audit, install browser, `playwright test`, **upload the HTML report and screenshot diffs even on failure**.
- Make `design-e2e` a **required status check** so a failing journey, contract or screenshot cannot merge.
- `forbidOnly` is on in CI; retries are 1 (a retry that passes is reported as **flaky**, and a flaky test must be fixed, not tolerated).
- Do not parallelise across tests that share server state; if your app has one database, set `workers: 1` or isolate data per test.
- The same OS as the baselines (`ubuntu-24.04`).

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

### 17.11 Evidence: what this suite catches (it was mutation-tested)

Each defect below was injected into a working copy of the starter, one at a time, and the suite was run. Each was caught, by the test shown:

| Injected defect | Caught by |
| --- | --- |
| A chip animation set to `infinite` | `no-infinite-animations` (journey J1 and every D1) |
| `backdrop-filter` added to every row | `glass-budget` ("21 elements, repeated: LI") |
| The reduced-motion CSS rule deleted | `[D3]` `reduced-motion-stops-motion` ("9 still running") |
| A `console.error` on load | the console guard, on every test |
| A phone layout forced 800px wide | `no-horizontal-overflow` ("14 elements extend past 390px: div.stage ends at 812") and the screenshot diff. The first version of this probe **missed it** because the root clips overflow; it now measures element edges too |
| Tiles recoloured to a slightly different blue | screenshot diff (29,176 px at threshold 0.05; **missed at Playwright's default 0.2**) |
| Light-theme selected chip text at 3.6:1 | `contrast li.is-selected > .chip` |
| The backlight overflowed a phone page, so the layout viewport grew and the dock drifted from its tap target | `[J3]` and `[J4]` click timeouts ("`<li>` intercepts pointer events"), found before the overflow probe was fixed |
| A lane too short to scroll | `[J5]` |
| `reducedMotion` set at the top level of `use` | the `[D3]` emulation assertion, and the audit |

And for the audit: a journey row with no test; a renamed journey tag; a `test.skip`; deleted baselines; a CI workflow without artifact upload; and a top-level `reducedMotion`. All fail the audit.

The suite ran green twice in a row on identical screenshots: 37 tests across 4 projects in about 50 seconds locally.

### 17.12 Making an agent just do it

The failure to prevent is an agent that stops early and calls it done. What works, in order of strength:

1. **Give it an executable acceptance test.** "Make `npm run design:check` exit 0" is a to-do list the machine keeps for you. The core audit checks stay red while S3, S5, S6 are missing, so there is nowhere to hide.
2. **Forbid the early stop in the prompt.** Paste this at the top of the task:

   > Your acceptance test is `npm run design:check`, plus a green `design-e2e` job in CI. You are not finished until both pass. Do not stop to report progress, ask whether to continue, or summarise "remaining debt": that is your to-do list, so keep going. Report only with the status words DONE, INCOMPLETE or BLOCKED (guide 17.1). Work test-first: for each slice write or extend the failing tests, paste the red output into `design-evidence.md`, implement until green, then open every changed screenshot and describe it. Skipping any core slice needs the user's written approval. "No browser tooling" is BLOCKED, not done: install Playwright.
3. **Make the order hard to game.** Foundations (S1, S2), then the core (S3, S4, S5, S6), then optional (S7, S8 with a recorded reason), and only then surface-by-surface polish (landing screens, modals, emoji).
4. **Review the evidence, not the claims.** Read the audit's SKIP list and the ledger, and open a few screenshots yourself. A capable model will usually tell you the truth about gaps; the point is that the truth has a name (INCOMPLETE) and a consequence (keep going).
5. **If it still stops early,** reply with one line: *"Status? Quote the last `design:check` output and the failing check names, then continue."*

### 17.13 The files, inlined

These are byte-for-byte the files in `starter/e2e`, `starter/ui` and `starter/ci`.

#### `e2e/playwright.config.mjs`

```js
// Playwright config for the Afterglow e2e suite.
//
// One project per (viewport x theme), so every journey and every design contract
// is screenshotted in each. A separate project replays the reduced-motion tests.
// Baselines live in __screenshots__/ and are COMMITTED. Generate them in the same
// environment CI uses (Linux), not on a laptop: see guide 17.4.
import { fileURLToPath } from 'node:url';
import { defineConfig, devices } from '@playwright/test';

const here = fileURLToPath(new URL('.', import.meta.url));
const port = Number(process.env.E2E_PORT ?? 4173);
const baseURL = process.env.E2E_BASE_URL ?? `http://127.0.0.1:${port}`;
// Use a system Chromium when Playwright's own build is not installed:
//   CHROME_PATH=/usr/bin/chromium npx playwright test
const executablePath = process.env.CHROME_PATH || undefined;

const desktop = { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } };
const phone = { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 1 };
const project = (name, base, theme, extra = {}) => ({
  name,
  metadata: { theme },
  grepInvert: /@reduced/,
  use: { ...base, colorScheme: theme, ...extra },
});

export default defineConfig({
  testDir: '.',
  testMatch: /.*\.spec\.mjs$/,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,          // a stray test.only must fail CI
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI
    ? [['list'], ['github'], ['html', { open: 'never', outputFolder: 'playwright-report' }]]
    : [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  outputDir: 'test-results',
  snapshotPathTemplate: '{testDir}/__screenshots__/{projectName}/{testFilePath}/{arg}{ext}',
  expect: {
    timeout: 10_000,
    // Finite CSS animations are fast-forwarded to their end state; infinite ones are
    // cancelled (and the design probes fail separately if any exist).
    // `threshold` is the per-pixel colour tolerance. Playwright's default (0.2) waves through a
    // visible hue shift: a mutation that recoloured the tiles slipped past it. 0.05 catches it and
    // stays stable across repeated runs in the same environment. `maxDiffPixelRatio` then allows
    // a few anti-aliased pixels, never a recoloured surface.
    toHaveScreenshot: { animations: 'disabled', caret: 'hide', scale: 'css', threshold: 0.05, maxDiffPixelRatio: 0.002 },
  },
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    serviceWorkers: 'block',
    launchOptions: { executablePath },
  },
  projects: [
    project('desktop-dark', desktop, 'dark'),
    project('desktop-light', desktop, 'light'),
    project('phone-dark', phone, 'dark'),
    {
      name: 'reduced-motion',
      metadata: { theme: 'dark' },
      grep: /@reduced/,
      // NOTE: `reducedMotion` is not a top-level `use` option in Playwright 1.55; it is silently
      // ignored. It must go through contextOptions. The D3 test asserts the emulation is on.
      use: { ...desktop, colorScheme: 'dark', contextOptions: { reducedMotion: 'reduce' } },
    },
  ],
  webServer: {
    command: 'node serve.mjs',
    cwd: here,
    url: `${baseURL}/demo.html`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    env: { E2E_PORT: String(port) },
  },
});
```

#### `e2e/design.config.mjs` (the only project-specific file)

```js
// The ONLY file that knows your selectors. Replace every value for your project.
export default {
  page: '/demo.html',
  rootSelector: '#root',
  attrs: { theme: 'data-theme', luma: 'data-luma', vibrance: 'data-vibrance' },
  lumas: ['standard', 'dim'],
  vibrances: ['vivid', 'soft', 'bold'],
  // Elements that carry --rank (identity is published, and shown on 2+ surfaces).
  rankWearers: ['.chip', '.lane > li', '.tile'],
  // Elements whose computed `color` IS the identity colour, and the attribute naming their pole.
  colorWearers: ['.chip'],
  poleAttr: 'data-lane',
  // Text that must stay legible (WCAG contrast ratio), measured on solid backgrounds.
  textPairs: [
    { text: 'li.is-selected > .chip', min: 4.5 },
    { text: '.tile', min: 4.5 },
  ],
  requiredTokens: ['--ramp-l', '--ramp-c', '--ember-alpha', '--flame-alpha', '--halo-alpha', '--ease-out'],
  // Must hold on the dim and veil tiers: bloom is gone.
  lowBloom: { '--ember-alpha': '0%' },
  maxGlass: 5,
  // Optional: runs after every page.goto (log in, seed data, pick a puzzle...).
  setup: async () => {},
};
```

#### `e2e/design-helpers.mjs`

```js
// Shared helpers: a console guard on every test, view-setting helpers, and the design
// contracts (the measurable half of the guide) expressed as Playwright assertions.
import { expect, test as base } from '@playwright/test';

export { expect };

// Every test fails if the page throws or logs a console error.
export const test = base.extend({
  consoleGuard: [
    async ({ page }, use) => {
      const errors = [];
      page.on('pageerror', (e) => errors.push(String(e)));
      page.on('console', (m) => {
        if (m.type() === 'error' && !m.location().url.includes('favicon')) errors.push(m.text());
      });
      await use();
      expect(errors, 'console errors during the test').toEqual([]);
    },
    { auto: true },
  ],
});

/** Set the view attributes on the root element (the data-* contract, guide 5.3). */
export async function applyView(page, cfg, view) {
  await page.evaluate(({ root, attrs, view }) => {
    const el = document.querySelector(root);
    for (const [key, attr] of Object.entries(attrs)) if (view[key] != null) el.setAttribute(attr, view[key]);
  }, { root: cfg.rootSelector, attrs: cfg.attrs, view });
}

/** Wait until every finite animation and transition has finished. Never use sleeps. */
export async function settle(page) {
  await page.waitForFunction(() => document.getAnimations().every((a) => a.playState !== 'running' || a.effect?.getComputedTiming().iterations === Infinity));
  await page.evaluate(() => document.fonts?.ready);
}

/** Runs inside the page: serialised by Playwright, so it must not reference anything outside. */
function probe(c) {
  const out = [];
  const add = (id, ok, detail) => out.push({ id, ok, detail });
  const toRGB = (css) => {
    const cv = document.createElement('canvas'); cv.width = cv.height = 1;
    const x = cv.getContext('2d', { willReadFrequently: true });
    x.clearRect(0, 0, 1, 1); x.fillStyle = '#000'; x.fillStyle = css; x.fillRect(0, 0, 1, 1);
    const d = x.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], d[3] / 255];
  };
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const ratio = (a, b) => { const [hi, lo] = [lum(a), lum(b)].sort((p, q) => q - p); return (hi + 0.05) / (lo + 0.05); };
  const over = (top, under) => [0, 1, 2].map((i) => top[i] * top[3] + under[i] * (1 - top[3])).concat(1);
  const effectiveBg = (el) => {
    const layers = [];
    for (let n = el; n; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.backgroundImage.includes('gradient')) return { gradient: true };
      const bg = toRGB(cs.backgroundColor);
      if (bg[3] > 0) layers.push(bg);
      if (bg[3] >= 0.99) break;
    }
    let acc = [255, 255, 255, 1];
    for (const l of layers.reverse()) acc = over(l, acc);
    return { rgb: acc };
  };
  const root = document.querySelector(c.rootSelector);
  if (!root) { add('root', false, `no element matches rootSelector ${c.rootSelector}`); return out; }

  // R14: nothing loops
  const infinite = document.getAnimations().filter((a) => a.effect?.getComputedTiming().iterations === Infinity);
  add('no-infinite-animations', infinite.length === 0, infinite.length ? `${infinite.length} infinite: ${infinite.map((a) => a.animationName || a.transitionProperty).join(', ')}` : 'none');

  // R17: reduced motion removes motion but keeps light
  if (c.reduced) {
    const running = document.getAnimations().filter((a) => a.playState === 'running' && (a.effect?.getComputedTiming().activeDuration ?? 0) > 0);
    add('reduced-motion-stops-motion', running.length === 0, running.length ? `${running.length} still running: ${running.map((a) => a.animationName || a.transitionProperty).slice(0, 5).join(', ')}` : 'no running animations');
  }

  // Tokens resolve on the root
  const rs = getComputedStyle(root);
  const missing = (c.requiredTokens ?? []).filter((t) => rs.getPropertyValue(t).trim() === '');
  add('tokens-resolve', missing.length === 0, missing.length ? `unset on root: ${missing.join(', ')}` : `${(c.requiredTokens ?? []).length} resolve`);

  // R18: low-bloom tiers remove bloom
  if (c.luma && c.luma !== 'standard' && c.lowBloom) {
    const bad = Object.entries(c.lowBloom).filter(([k, v]) => rs.getPropertyValue(k).trim() !== v).map(([k, v]) => `${k} is "${rs.getPropertyValue(k).trim()}", want "${v}"`);
    add('low-bloom-tier', bad.length === 0, bad.length ? bad.join('; ') : 'bloom tokens lowered');
  }

  // R1/R2/R26/R27: identity is published, shown on 2+ surfaces, and colour follows rank
  const rankOf = (el) => el.style.getPropertyValue('--rank').trim() || getComputedStyle(el).getPropertyValue('--rank').trim();
  const bySel = (c.rankWearers ?? []).map((s) => [...document.querySelectorAll(s)].map(rankOf).filter((r) => r !== ''));
  if ((c.rankWearers ?? []).length) {
    const distinct = new Set(bySel.flat());
    add('identity-ranks-published', distinct.size >= 4, `${distinct.size} distinct ranks published (need 4+)`);
    const shared = [...distinct].filter((r) => bySel.filter((list) => list.includes(r)).length >= 2);
    add('identity-on-two-surfaces', shared.length > 0 || bySel.length < 2, bySel.length < 2 ? 'only one wearer selector configured' : `${shared.length} rank(s) appear on 2+ surfaces`);
  }
  if ((c.colorWearers ?? []).length) {
    const groups = new Map();
    for (const s of c.colorWearers) for (const el of document.querySelectorAll(s)) {
      const r = rankOf(el); if (r === '') continue;
      const pole = c.poleAttr ? (el.closest(`[${c.poleAttr}]`)?.getAttribute(c.poleAttr) ?? '') : '';
      const key = `${r}|${pole}`;
      groups.set(key, [...(groups.get(key) ?? []), toRGB(getComputedStyle(el).color).slice(0, 3).map(Math.round).join(',')]);
    }
    const bad = [...groups].filter(([, v]) => new Set(v).size > 1).map(([k]) => k);
    add('identity-colour-follows-rank', bad.length === 0, bad.length ? `same rank and pole, different colour: ${bad.slice(0, 4).join('; ')}` : `${groups.size} rank groups consistent`);
    const colours = new Set([...groups.values()].map((v) => v[0]));
    add('identity-colours-vary', colours.size >= Math.min(4, groups.size), `${colours.size} distinct identity colours across ${groups.size} groups`);
  }

  // R5: legibility is lightness. Measured contrast on solid backgrounds.
  for (const p of c.textPairs ?? []) {
    const els = [...document.querySelectorAll(p.text)].slice(0, 40);
    if (!els.length) { add(`contrast ${p.text}`, false, 'selector matched nothing'); continue; }
    let worst = Infinity; let checked = 0; let skipped = 0;
    for (const el of els) {
      const bg = effectiveBg(el);
      if (bg.gradient) { skipped++; continue; }
      worst = Math.min(worst, ratio(over(toRGB(getComputedStyle(el).color), bg.rgb), bg.rgb)); checked++;
    }
    add(`contrast ${p.text}`, checked > 0 && worst >= (p.min ?? 4.5), checked ? `worst ${worst.toFixed(2)}:1 over ${checked}, need ${p.min ?? 4.5}${skipped ? ` (${skipped} on gradients not measured)` : ''}` : 'every element sat on a gradient: test a solid surface');
  }

  // R10: glass budget; no repeated blur
  const glass = [...document.querySelectorAll('*')].filter((el) => { const b = getComputedStyle(el).backdropFilter; return b && b !== 'none'; });
  const sig = new Map();
  for (const el of glass) { const k = `${el.tagName}.${el.className}`; sig.set(k, (sig.get(k) ?? 0) + 1); }
  const repeated = [...sig].filter(([, n]) => n >= 3).map(([k]) => k);
  add('glass-budget', glass.length <= c.maxGlass && repeated.length === 0, `${glass.length} elements with backdrop-filter (limit ${c.maxGlass})${repeated.length ? `; repeated: ${repeated.join(', ')}` : ''}`);

  // No horizontal overflow at this viewport. Two measurements, because either alone can lie:
  //  1. scrollWidth against the REAL viewport width. On a phone the layout viewport grows to fit
  //     overflow, so innerWidth can never reveal it.
  //  2. every visible element's right edge. A root with overflow-x: clip (used to hide the
  //     backlight layer) clips overflowing content instead of making a scrollbar, so scrollWidth
  //     stays small while content is cut off. Elements inside their own horizontal scroller are fine.
  const vw = c.viewportWidth ?? window.innerWidth;
  const wide = document.documentElement.scrollWidth - vw;
  const cut = [];
  for (const el of root.querySelectorAll('*')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0 || r.right <= vw + 1) continue;
    if (getComputedStyle(el).visibility === 'hidden') continue;
    let scrolls = false;
    for (let p = el.parentElement; p && p !== root; p = p.parentElement) if (getComputedStyle(p).overflowX !== 'visible') { scrolls = true; break; }
    if (!scrolls) cut.push(`${el.tagName.toLowerCase()}${el.className ? '.' + String(el.className).split(' ')[0] : ''} ends at ${Math.round(r.right)}`);
  }
  add('no-horizontal-overflow', wide <= 1 && cut.length === 0,
    wide > 1 ? `page is ${wide}px wider than the ${vw}px viewport` : cut.length ? `${cut.length} element(s) extend past ${vw}px: ${cut.slice(0, 3).join('; ')}` : 'fits');
  return out;
}

/** Assert every design contract. Uses soft assertions so one run reports all failures. */
export async function expectContracts(page, cfg, state = {}) {
  const results = await page.evaluate(probe, { ...cfg, setup: undefined, viewportWidth: page.viewportSize()?.width, ...state });
  for (const r of results) expect.soft(r.ok, `${r.id}: ${r.detail}`).toBe(true);
}

/** Keyboard users must see where focus is. */
export async function expectFocusRing(page) {
  await page.keyboard.press('Tab');
  const ring = await page.evaluate(() => {
    const e = document.activeElement;
    if (!e || e === document.body) return { ok: false, detail: 'Tab focused nothing' };
    const s = getComputedStyle(e);
    const ok = (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || (s.boxShadow && s.boxShadow !== 'none');
    return { ok: !!ok, detail: ok ? 'ring present' : `${e.tagName}.${e.className} has no outline or ring` };
  });
  expect(ring.ok, `focus ring: ${ring.detail}`).toBe(true);
}
```

#### `e2e/design.spec.mjs`

```js
// Design contracts: the measurable half of the guide, checked in every project
// (viewport x theme) and across the mini/micro view tiers, each with a screenshot.
import cfg from './design.config.mjs';
import { applyView, expect, expectContracts, expectFocusRing, settle, test } from './design-helpers.mjs';

const theme = () => test.info().project.metadata.theme ?? 'dark';

test.describe('design contracts', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(cfg.page);
    await cfg.setup?.(page);
  });

  for (const luma of cfg.lumas) {
    for (const vibrance of cfg.vibrances) {
      test(`[D1] view matrix: ${luma} / ${vibrance}`, async ({ page }) => {
        await applyView(page, cfg, { theme: theme(), luma, vibrance });
        await settle(page);
        await expectContracts(page, cfg, { luma });
        await expect(page).toHaveScreenshot(`view-${luma}-${vibrance}.png`);
      });
    }
  }

  test('[D2] keyboard focus is visible', async ({ page }) => {
    await settle(page);
    await expectFocusRing(page);
  });

  // Runs only in the reduced-motion project (see playwright.config.mjs).
  test('[D3] reduced motion removes motion and keeps light', { tag: '@reduced' }, async ({ page }) => {
    const emulated = await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
    expect(emulated, 'prefers-reduced-motion must be emulated, or this test proves nothing').toBe(true);
    await applyView(page, cfg, { theme: 'dark', luma: 'standard', vibrance: 'vivid' });
    await page.locator('.lane > li').nth(2).click();
    await page.waitForTimeout(400);
    await expectContracts(page, cfg, { luma: 'standard', reduced: true });
    // The light stays: the selected chip still carries its flame.
    const shadow = await page.locator('li.is-selected > .chip').first().evaluate((el) => getComputedStyle(el).boxShadow);
    expect(shadow, 'the selection keeps its glow when motion is off').not.toBe('none');
    await expect(page).toHaveScreenshot('reduced-motion-selected.png');
  });
});
```

#### `e2e/journeys.spec.mjs`

```js
// User journeys. EVERY journey in JOURNEYS.md has a test here whose title starts with
// its id, "[J1]", and ends in at least one screenshot. The static audit enforces that.
// Replace these demo journeys with your product's.
import cfg from './design.config.mjs';
import { applyView, expect, expectContracts, settle, test } from './design-helpers.mjs';

const theme = () => test.info().project.metadata.theme ?? 'dark';
const root = (page) => page.locator(cfg.rootSelector);

test.beforeEach(async ({ page }) => {
  await page.goto(cfg.page);
  await applyView(page, cfg, { theme: theme() });
  await cfg.setup?.(page);
});

test('[J1] First view: lanes, ground and tiles at rest', async ({ page }) => {
  await test.step('the page settles with nothing looping', async () => {
    await settle(page);
    await expectContracts(page, cfg, {});
  });
  await test.step('the resting state is captured', async () => {
    await expect(page).toHaveScreenshot('j1-first-view.png');
  });
});

test('[J2] Select a clue: the flame ignites once and settles', async ({ page }) => {
  const row = page.locator('#lane-a > li').nth(2);
  await test.step('click an item', async () => {
    await row.click();
    await expect(row).toHaveClass(/is-selected/);
    await expect(root(page)).toHaveAttribute('data-direction', 'across');
  });
  await test.step('the glow flare returns to rest (--glow-pulse is 1)', async () => {
    await settle(page);
    const pulse = await row.locator('.chip').evaluate((el) => getComputedStyle(el).getPropertyValue('--glow-pulse').trim());
    expect(pulse).toBe('1');
  });
  await test.step('only one item in the lane is selected, and contracts hold', async () => {
    await expect(page.locator('#lane-a > li.is-selected')).toHaveCount(1);
    await expectContracts(page, cfg, {});
    await expect(page).toHaveScreenshot('j2-selected.png');
  });
});

test('[J3] Dim the screen from the View panel: bloom drops and the choice persists', async ({ page }) => {
  await test.step('open the panel and choose Dim', async () => {
    await page.locator('.view-cluster-summary').click();
    await page.locator('.view-choice[data-key="luma"][data-value="dim"]').click();
    await expect(root(page)).toHaveAttribute(cfg.attrs.luma, 'dim');
    await settle(page);
    await expectContracts(page, cfg, { luma: 'dim' });
    await expect(page).toHaveScreenshot('j3-panel-dim.png');
  });
  await test.step('the choice survives a reload (stored beats the default)', async () => {
    await page.reload();
    await expect(root(page)).toHaveAttribute(cfg.attrs.luma, 'dim');
  });
});

test('[J4] Reset restores the defaults', async ({ page }) => {
  await page.locator('.view-cluster-summary').click();
  await page.locator('.view-choice[data-key="luma"][data-value="veil"]').click();
  await expect(root(page)).toHaveAttribute(cfg.attrs.luma, 'veil');
  await page.locator('.view-reset').click();
  await expect(root(page)).toHaveAttribute(cfg.attrs.luma, 'standard');
  await settle(page);
  await expect(page).toHaveScreenshot('j4-reset.png');
});

test('[J5] Scrolling a lane moves the territory light', async ({ page }) => {
  const ground = page.locator('#ground');
  const before = await ground.evaluate((el) => el.style.getPropertyValue('--ta-top'));
  await page.locator('#lane-a').evaluate((el) => { el.scrollTop = el.scrollHeight; });
  await expect.poll(() => ground.evaluate((el) => el.style.getPropertyValue('--ta-top'))).not.toBe(before);
  await settle(page);
  await expect(page).toHaveScreenshot('j5-scrolled.png');
});
```

#### `e2e/JOURNEYS.md`

```md
# User journeys

The complete inventory of what a user can do. **Every row has a Playwright test titled
`[<ID>] ...` that ends in at least one `toHaveScreenshot`.** The static audit
(`audit-static.mjs`) fails if a row has no test, and fails if a test has no row.

How to find every journey (do all of these before declaring the list complete):

- Every route or page in the router.
- Every `data-testid` and every button, link and form in the templates.
- Every modal, drawer, menu and toast, opened and closed.
- Every data state of every screen: loading, empty, one item, many items, error, offline.
- First run vs returning user; signed out vs signed in; any destructive confirmation.
- Each setting a user can change, and that it persists after a reload.
- The finish (success) path, the abandon path, and the failure path.

| ID | Journey | Starts at, ends at | States that are screenshotted |
| --- | --- | --- | --- |
| J1 | First view | open the app, rest state | lanes, ground, tiles |
| J2 | Select a clue | click a row, glow settles | one row selected |
| J3 | Dim the screen | open View panel, choose Dim, reload | panel open, dim applied, persisted |
| J4 | Reset the view | choose Veil, press Reset | defaults restored |
| J5 | Scroll a lane | scroll lane A to the end | territory light moved |

Design contracts (viewport x theme x view tier, keyboard focus, reduced motion) live in
`design.spec.mjs` with ids `D1` to `D3`; they are not journeys.
```

#### `e2e/serve.mjs` (demo only; delete it and point `webServer` at your own server)

```js
// A tiny static server for the demo. In a real project delete this and point
// `webServer` in playwright.config.mjs at your dev or preview server instead.
import { createServer } from 'node:http';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json' };
createServer((req, res) => {
  const path = join(root, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!path.startsWith(root) || !existsSync(path) || !statSync(path).isFile()) { res.writeHead(404).end('not found'); return; }
  res.writeHead(200, { 'content-type': types[extname(path)] ?? 'application/octet-stream' }).end(readFileSync(path));
}).listen(Number(process.env.E2E_PORT ?? 4173), '127.0.0.1');
```

#### `ui/audit-static.mjs`

```js
#!/usr/bin/env node
// audit-static.mjs: a static audit of a project's source against the Afterglow
// design language. No dependencies, no browser. Node 18+.
//
//   node audit-static.mjs --src src
//   node audit-static.mjs --src src --skip economy="no open/closed items (brief 16.2 #3)"
//   node audit-static.mjs --config design-check.config.json --json audit.json
//   node audit-static.mjs --src . --ignore ui     (skip a directory or file by name)
//   node audit-static.mjs --src src --e2e-dir tests/e2e --workflows .github/workflows
//
// The e2e checks enforce "every user journey is tested, with screenshots, in CI":
//   JOURNEYS.md rows "| J1 |" must each have a Playwright test titled "[J1] ..."; every tag must
//   have a row; there must be screenshot assertions and committed baselines; no skipped, fixme or
//   only tests; reducedMotion must go through contextOptions; a CI workflow must run
//   `playwright test` and upload the report.
//
// Exit codes: 0 pass · 1 one or more FAIL · 2 misuse (for example skipping a core check).
//
// CORE checks cannot be skipped. Only `economy` and `celebration` can be skipped,
// and only with a written reason, which is printed loudly so the user can overrule it.
// A report with SKIPs or WARNs is not "done" until the user has seen the reasons.

import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { extname, join, relative } from 'node:path';

// ---------------------------------------------------------------- arguments
const argv = process.argv.slice(2);
const opt = (name) => { const i = argv.indexOf(name); return i === -1 ? undefined : argv[i + 1]; };
const all = (name) => argv.flatMap((a, i) => (a === name ? [argv[i + 1]] : []));
let config = {};
if (opt('--config')) config = JSON.parse(readFileSync(opt('--config'), 'utf8'));
const src = opt('--src') ?? config.src ?? 'src';
const strict = argv.includes('--strict');
const e2eDir = opt('--e2e-dir') ?? config.e2eDir ?? 'tests/e2e';
const workflowsDir = opt('--workflows') ?? config.workflows ?? '.github/workflows';
const journeysFile = opt('--journeys') ?? config.journeys ?? join(e2eDir, 'JOURNEYS.md');
const maxGlass = Number(opt('--max-glass') ?? config.maxGlass ?? 5);
const maxImportant = Number(config.maxImportant ?? 20);
const maxHex = Number(config.maxHex ?? 60);
const requiredTokens = (opt('--tokens')?.split(',') ?? config.tokens ?? [
  '--ramp-l', '--ramp-c', '--ember-alpha', '--flame-alpha', '--halo-alpha',
  '--glow-pulse', '--ease-out', '--dur-quick',
]);
const skips = { ...(config.skip ?? {}) };
for (const s of all('--skip')) {
  const eq = s.indexOf('=');
  if (eq === -1) { console.error(`--skip needs id="reason", got "${s}"`); process.exit(2); }
  skips[s.slice(0, eq)] = s.slice(eq + 1).replace(/^"|"$/g, '');
}
const SKIPPABLE = new Set(['economy', 'celebration']);
for (const [id, reason] of Object.entries(skips)) {
  if (!SKIPPABLE.has(id)) { console.error(`Check "${id}" is core and cannot be skipped. Skippable: ${[...SKIPPABLE].join(', ')}.`); process.exit(2); }
  if (reason.trim().length < 15) { console.error(`Skip "${id}" needs a real reason (15+ characters), got "${reason}".`); process.exit(2); }
}

// -------------------------------------------------------------------- files
const EXT = new Set(['.css', '.scss', '.less', '.vue', '.svelte', '.astro', '.html', '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']);
const STYLE_EXT = new Set(['.css', '.scss', '.less']);
const IGNORE = new Set(['node_modules', '.git', 'dist', 'build', 'coverage', '.next', '.nuxt', '.svelte-kit', '.output', ...all('--ignore'), ...(config.ignore ?? [])]);
const files = [];
(function walk(dir) {
  for (const name of readdirSync(dir)) {
    if (IGNORE.has(name)) continue;
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) walk(p);
    else if (EXT.has(extname(name))) files.push(p);
  }
})(src);

// Blank out comments but keep line numbers, so matches point at real code.
function stripComments(text, ext) {
  const blank = (m) => m.replace(/[^\n]/g, ' ');
  let out = text.replace(/\/\*[\s\S]*?\*\//g, blank).replace(/<!--[\s\S]*?-->/g, blank);
  if (ext !== '.css') out = out.replace(/(^|[^:'"`\\])\/\/[^\n]*/g, (m, p) => p + ' '.repeat(m.length - p.length));
  return out;
}
const docs = files.map((file) => {
  const ext = extname(file);
  const raw = readFileSync(file, 'utf8');
  return { file: relative('.', file), ext, raw, code: stripComments(raw, ext), isStyle: STYLE_EXT.has(ext) };
});
// "css-ish" text: style sheets plus the <style> blocks of components.
const cssText = docs.map((d) => (d.isStyle ? d.code : (d.code.match(/<style[\s\S]*?<\/style>/g) ?? []).join('\n'))).join('\n');
const nonStyle = docs.filter((d) => !d.isStyle);

function hits(regex, list = docs) {
  const found = [];
  for (const d of list) {
    d.code.split('\n').forEach((line, i) => { if (regex.test(line)) found.push(`${d.file}:${i + 1}  ${line.trim().slice(0, 110)}`); });
  }
  return found;
}
const anyIn = (regex, list = nonStyle) => list.some((d) => regex.test(d.code));

// ------------------------------------------------------------------- checks
const results = [];
const add = (id, level, status, summary, detail = []) => results.push({ id, level, status, summary, detail });
const pass = (cond) => (cond ? 'PASS' : 'FAIL');

// C1 no looping motion (R14)
{
  const re = /animation[^;{}]*\binfinite\b|animation-iteration-count\s*:\s*infinite|iterations\s*:\s*(Infinity|['"]infinite)|repeat\s*:\s*-1|\bloop\s*:\s*true/;
  const found = hits(re);
  add('no-infinite', 'core', pass(!found.length), found.length ? `${found.length} looping animation(s). Nothing loops (R14).` : 'No looping animations.', found);
}

// C2 glass budget (R10)
{
  const blocks = [];
  // `backdrop-filter: none` is a reset, not glass.
  for (const m of cssText.matchAll(/([^{}]+)\{([^{}]*backdrop-filter\s*:(?!\s*none)[^{}]*)\}/g)) blocks.push(m[1].trim().replace(/\s+/g, ' '));
  const selectors = [...new Set(blocks)];
  const repeated = selectors.filter((s) => /\b(li|tr|td|row|cell|tile|item|chip|slot)\b|[-_.](row|cell|tile|item|chip|slot|list-item)\b/i.test(s));
  const status = selectors.length > maxGlass ? 'FAIL' : repeated.length ? 'WARN' : 'PASS';
  add('glass-budget', 'core', status,
    `${selectors.length} rule(s) use backdrop-filter (limit ${maxGlass}).${repeated.length ? ' Some selectors look like repeated surfaces (R10).' : ''}`,
    [...selectors.map((s) => `  ${s}`), ...repeated.map((s) => `  REPEATED? ${s}`)]);
}

// C3 reduced motion (R17)
add('reduced-motion', 'core', pass(/prefers-reduced-motion\s*:\s*reduce/.test(cssText)),
  /prefers-reduced-motion\s*:\s*reduce/.test(cssText) ? 'A prefers-reduced-motion block exists.' : 'No @media (prefers-reduced-motion: reduce) block (R17).');

// C4 tokens
{
  const missing = requiredTokens.filter((t) => !new RegExp(`${t.replace(/[-]/g, '\\-')}\\s*:`).test(cssText));
  add('tokens', 'core', pass(!missing.length), missing.length ? `Missing tokens: ${missing.join(', ')}. Keep the variable names (guide 14.1).` : `All ${requiredTokens.length} required tokens are declared.`);
}

// C5 registered properties
add('registered-glow', 'core', pass(/@property\s+--glow-pulse/.test(cssText)),
  /@property\s+--glow-pulse/.test(cssText) ? '@property --glow-pulse is registered.' : '@property --glow-pulse is missing: the ignition cannot ease (guide 9.3).');

// C6 identity ramp (S3, R1, R2, R6)
{
  const miss = [];
  if (!/oklch\(/.test(cssText)) miss.push('CSS never uses oklch()');
  if (!/var\(\s*--rank/.test(cssText)) miss.push('CSS never reads var(--rank)');
  if (!anyIn(/['"`]?--rank['"`]?\s*[:,)]|setProperty\(\s*['"]--rank/)) miss.push('no markup or script publishes --rank on items');
  add('identity-ramp', 'core', pass(!miss.length), miss.length ? `Content identity is not wired (S3): ${miss.join('; ')}.` : 'The rank is published and read by the ramp.', miss.map((m) => `  ${m}`));
}

// C7 view tiers (S5, R19-R22)
{
  const miss = [];
  if (!/\[data-luma/.test(cssText)) miss.push('CSS has no [data-luma] tier');
  if (!/\[data-vibrance/.test(cssText)) miss.push('CSS has no [data-vibrance] tier');
  if (!anyIn(/data-luma|data-\$\{|setAttribute\(\s*`data-|dataset\.luma/)) miss.push('no code publishes the data-* settings on the root');
  if (!anyIn(/localStorage/) ) miss.push('settings are not persisted');
  if (!anyIn(/prefers-contrast|prefers-reduced-transparency/)) miss.push('no media hint chooses the first-visit brightness');
  if (!anyIn(/view-tier|data-tier|view-cluster/)) miss.push('no View panel UI is mounted');
  add('view-tiers', 'core', pass(!miss.length), miss.length ? `The mini/micro/nano settings are incomplete (S5): ${miss.join('; ')}.` : 'Settings contract, persistence, media hint and panel are present.', miss.map((m) => `  ${m}`));
}

// C8 territory (S6)
{
  const miss = [];
  if (!/@property\s+--(ta|territory)-?[a-z-]*/.test(cssText)) miss.push('no registered territory properties (@property --ta-top ...)');
  if (!anyIn(/--ta-top|--territory-/)) miss.push('no code publishes the corner ranks');
  add('territory', 'core', pass(!miss.length), miss.length ? `The ground is not lit by what is on screen (S6): ${miss.join('; ')}.` : 'Territory properties are registered and published.', miss.map((m) => `  ${m}`));
}

// C9 economy of light (S7), skippable with a reason
{
  const miss = [];
  if (!/--charge/.test(cssText)) miss.push('no --charge in CSS');
  if (!anyIn(/--remaining\s*[:'"]|['"]--remaining['"]/)) miss.push('no code publishes --remaining');
  if (skips.economy) add('economy', 'skippable', 'SKIP', `SKIPPED. Reason given: ${skips.economy}`);
  else add('economy', 'skippable', pass(!miss.length), miss.length ? `The economy of light is absent (S7): ${miss.join('; ')}. If the project has no open/closed items, skip with --skip economy="reason".` : 'Charge and remainder are wired.');
}

// C10 celebration (S8), skippable with a reason
{
  const ok = anyIn(/celebrat|rapture|finale|confetti/i) && anyIn(/\btier\b/i);
  if (skips.celebration) add('celebration', 'skippable', 'SKIP', `SKIPPED. Reason given: ${skips.celebration}`);
  else add('celebration', 'skippable', pass(ok), ok ? 'Tiered celebration is present.' : 'No tiered celebration (S8). If there is no finishing event, skip with --skip celebration="reason".');
}

// ---- E2E: Playwright, journeys, screenshots, CI (core, cannot be skipped)
function listFiles(dir, keep) {
  const found = [];
  try {
    for (const name of readdirSync(dir)) {
      if (name === 'node_modules' || name === '.git') continue;
      const p = join(dir, name);
      if (statSync(p).isDirectory()) found.push(...listFiles(p, keep)); else if (keep(p)) found.push(p);
    }
  } catch { /* directory missing: reported by the checks below */ }
  return found;
}
{
  const specs = listFiles(e2eDir, (p) => /\.spec\.(m?[jt]s|[jt]sx)$/.test(p));
  const specText = specs.map((f) => ({ file: f, text: stripComments(readFileSync(f, 'utf8'), '.js') }));
  const configs = [...listFiles(e2eDir, (p) => /playwright\.config\.(m?[jt]s)$/.test(p)), ...['playwright.config.ts', 'playwright.config.js', 'playwright.config.mjs'].filter((f) => { try { return statSync(f).isFile(); } catch { return false; } })];

  // E1 Playwright is the runner
  {
    const miss = [];
    if (!configs.length) miss.push(`no playwright.config.* under ${e2eDir} or at the root`);
    if (!specs.length) miss.push(`no *.spec.* files under ${e2eDir}`);
    let pkg = ''; try { pkg = readFileSync('package.json', 'utf8'); } catch { /* none */ }
    if (!/@playwright\/test/.test(pkg)) miss.push('@playwright/test is not in package.json');
    add('e2e-playwright', 'core', pass(!miss.length), miss.length ? `Playwright e2e is not set up: ${miss.join('; ')}. Install: npm i -D @playwright/test && npx playwright install chromium` : `Playwright config and ${specs.length} spec file(s) present.`, miss.map((m) => `  ${m}`));
  }

  // E2 every journey has a test, and every test tag has a journey
  {
    let rows = [];
    try { rows = [...readFileSync(journeysFile, 'utf8').matchAll(/^\|\s*(J\d+)\s*\|/gm)].map((m) => m[1]); } catch { /* reported below */ }
    const tagged = new Set(specText.flatMap((d) => [...d.text.matchAll(/\[(J\d+)\]/g)].map((m) => m[1])));
    const miss = [];
    if (!rows.length) miss.push(`${journeysFile} is missing or has no "| J1 |" rows`);
    for (const r of rows) if (!tagged.has(r)) miss.push(`${r} is in the inventory but no test is titled "[${r}] ..."`);
    for (const t of tagged) if (!rows.includes(t)) miss.push(`a test is tagged [${t}] but ${journeysFile} has no row for it`);
    add('e2e-journeys', 'core', pass(!miss.length), miss.length ? `Journey coverage is incomplete: ${miss.length} gap(s).` : `${rows.length} journeys, each with a test.`, miss.map((m) => `  ${m}`));
    globalThis.__journeyCount = rows.length;
  }

  // E3 screenshots asserted and baselines committed
  {
    const shots = specText.reduce((n, d) => n + (d.text.match(/toHaveScreenshot\(/g) ?? []).length, 0);
    const baselines = listFiles(e2eDir, (p) => /(__screenshots__|-snapshots)/.test(p) && p.endsWith('.png')).length;
    const need = globalThis.__journeyCount || 1;
    const miss = [];
    if (shots < need) miss.push(`${shots} toHaveScreenshot() call(s) for ${need} journeys: every journey needs at least one`);
    if (baselines < need) miss.push(`${baselines} committed baseline PNG(s) for ${need} journeys: generate and COMMIT them (guide 17.4)`);
    add('e2e-screenshots', 'core', pass(!miss.length), miss.length ? 'Screenshot coverage is incomplete.' : `${shots} screenshot assertions, ${baselines} committed baselines.`, miss.map((m) => `  ${m}`));
  }

  // E4 hygiene: skipped tests are debt, not green
  {
    const found = [];
    for (const d of specText) d.text.split('\n').forEach((l, i) => { if (/\b(test|it|describe)\.(skip|fixme|only)\s*\(|\btest\.slow\(\)|\.skip\(\s*\)/.test(l)) found.push(`${d.file}:${i + 1}  ${l.trim().slice(0, 100)}`); });
    add('e2e-no-skips', 'core', pass(!found.length), found.length ? `${found.length} skipped/fixme/only test(s). A skipped test is unfinished work, not a pass.` : 'No skipped, fixme or only tests.', found);
  }

  // E5 the Playwright 1.55 trap: top-level `reducedMotion` is silently ignored
  {
    // Comments are stripped first, and the structure is required (not just the word), so an
    // explanatory comment cannot satisfy the check.
    const cfgText = configs.map((f) => ({ f, t: stripComments(readFileSync(f, 'utf8'), '.js') }));
    const bad = cfgText.filter(({ t }) => /reducedMotion/.test(t) && !/contextOptions\s*:\s*\{[^}]*reducedMotion/.test(t)).map(({ f }) => f);
    const has = cfgText.some(({ t }) => /reducedMotion/.test(t)) || specText.some((d) => /emulateMedia\([^)]*reducedMotion/.test(d.text));
    const miss = [];
    if (bad.length) miss.push(`reducedMotion set outside contextOptions in ${bad.join(', ')}: Playwright ignores it silently`);
    if (!has) miss.push('no reduced-motion test (set contextOptions.reducedMotion or call page.emulateMedia)');
    add('e2e-reduced-motion', 'core', pass(!miss.length), miss.length ? `Reduced motion is not really tested: ${miss.join('; ')}.` : 'Reduced motion is emulated through contextOptions or emulateMedia.', miss.map((m) => `  ${m}`));
  }

  // E6 CI runs it and keeps the evidence
  {
    const wf = [...listFiles(workflowsDir, (p) => /\.ya?ml$/.test(p)), ...['.gitlab-ci.yml', '.circleci/config.yml'].filter((f) => { try { return statSync(f).isFile(); } catch { return false; } })];
    const text = wf.map((f) => readFileSync(f, 'utf8')).join('\n');
    const miss = [];
    if (!wf.length) miss.push(`no CI workflow found under ${workflowsDir}`);
    else {
      if (!/playwright\s+test/.test(text)) miss.push('no CI step runs `playwright test`');
      if (!/playwright\s+install/.test(text)) miss.push('no CI step installs the browser (`playwright install`)');
      if (!/upload-artifact|artifacts:/.test(text)) miss.push('CI does not upload the report and screenshot diffs');
    }
    add('e2e-ci', 'core', pass(!miss.length), miss.length ? `CI does not run the e2e suite: ${miss.join('; ')}.` : 'CI installs the browser, runs playwright test and uploads the report.', miss.map((m) => `  ${m}`));
  }
}

// Standard checks (WARN, or FAIL under --strict)
{
  const hexLines = [];
  for (const d of docs) {
    const text = d.isStyle ? d.code : (d.code.match(/<style[\s\S]*?<\/style>/g) ?? []).join('\n');
    text.split('\n').forEach((line, i) => { if (/#[0-9a-fA-F]{3,8}\b/.test(line) && !/^\s*--/.test(line)) hexLines.push(`${d.file}:${i + 1}`); });
  }
  add('hex-literals', 'standard', hexLines.length > maxHex ? 'WARN' : 'PASS', `${hexLines.length} hex colour literal(s) outside token declarations (limit ${maxHex}). Colours come from the ramp (R6).`, hexLines.length > maxHex ? hexLines.slice(0, 15).map((l) => `  ${l}`) : []);
  const important = (cssText.match(/!important/g) ?? []).length;
  add('important', 'standard', important > maxImportant ? 'WARN' : 'PASS', `${important} use(s) of !important (limit ${maxImportant}).`);
  const emoji = [];
  for (const d of docs.filter((x) => ['.vue', '.jsx', '.tsx', '.html', '.svelte', '.astro'].includes(x.ext))) {
    d.raw.split('\n').forEach((line, i) => { if (/\p{Extended_Pictographic}/u.test(line)) emoji.push(`${d.file}:${i + 1}  ${line.trim().slice(0, 90)}`); });
  }
  add('emoji', 'standard', emoji.length ? 'WARN' : 'PASS', emoji.length ? `${emoji.length} line(s) with emoji in markup. Anti-slop list (guide 18).` : 'No emoji in markup.', emoji.slice(0, 15).map((l) => `  ${l}`));
  const layout = cssText.split('\n').filter((l) => /transition[^;]*\b(width|height|top|left|right|bottom|margin|padding)\b|transition\s*:\s*all\b/.test(l));
  add('layout-motion', 'standard', layout.length ? 'WARN' : 'PASS', layout.length ? `${layout.length} transition(s) on layout properties or "all" (R15).` : 'No layout transitions.', layout.slice(0, 10).map((l) => `  ${l.trim().slice(0, 110)}`));
}

// ------------------------------------------------------------------- report
if (strict) for (const r of results) if (r.status === 'WARN') r.status = 'FAIL';
const mark = { PASS: 'PASS', FAIL: 'FAIL', WARN: 'WARN', SKIP: 'SKIP' };
console.log(`\nAfterglow static audit: ${docs.length} files under ${src}\n`);
for (const r of results) {
  console.log(`${mark[r.status].padEnd(4)}  ${r.id.padEnd(16)} [${r.level}]  ${r.summary}`);
  if (r.status !== 'PASS') for (const d of r.detail) console.log(`      ${d}`);
}
const failed = results.filter((r) => r.status === 'FAIL');
const skipped = results.filter((r) => r.status === 'SKIP');
const warned = results.filter((r) => r.status === 'WARN');
console.log(`\n${results.length - failed.length - skipped.length - warned.length} passed, ${failed.length} failed, ${warned.length} warnings, ${skipped.length} skipped.`);
if (skipped.length) console.log('SKIPS NEED THE USER\'S APPROVAL. Report them verbatim:\n' + skipped.map((s) => `  - ${s.id}: ${s.summary}`).join('\n'));
if (failed.length) console.log('\nNOT DONE. Fix every FAIL and run this again. Do not report completion while any check fails.');
if (opt('--json')) writeFileSync(opt('--json'), JSON.stringify({ src, results }, null, 2));
process.exit(failed.length ? 1 : 0);
```

#### `ci/design-e2e.yml`

```yaml
# Copy to .github/workflows/design-e2e.yml and adjust the paths marked  <<like this>>.
# Make this job a REQUIRED status check on the default branch, so a design that fails the
# journeys, the contracts or the screenshots cannot merge.
name: design-e2e
on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:
concurrency:
  group: design-e2e-${{ github.ref }}
  cancel-in-progress: true
jobs:
  design:
    runs-on: ubuntu-24.04          # baselines must be generated on the same OS as this runner
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
      - run: npm ci
      - name: Static design audit (fast; fails while a core slice is missing)
        run: node <<docs/design-language>>/starter/ui/audit-static.mjs --src <<src>> --e2e-dir <<tests/e2e>>
      - name: Install the browser Playwright expects
        run: npx playwright install --with-deps chromium
      - name: Journeys, design contracts and screenshots
        run: npx playwright test -c <<tests/e2e>>/playwright.config.mjs
      - name: Upload the report and screenshot diffs, even on failure
        if: ${{ !cancelled() }}
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: |
            <<tests/e2e>>/playwright-report/
            <<tests/e2e>>/test-results/
          retention-days: 14
```

#### `ci/update-screenshots.yml`

```yaml
# Copy to .github/workflows/update-screenshots.yml. Run it by hand from the Actions tab on
# the branch whose screenshots you intend to change. Baselines come from CI's own OS, so they
# match what design-e2e compares against. A human must LOOK at every changed image in the diff.
name: update-screenshots
on:
  workflow_dispatch:
permissions:
  contents: write
jobs:
  update:
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.ref_name }}
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
      - run: npm ci
      - run: npx playwright install --with-deps chromium
      - run: npx playwright test -c <<tests/e2e>>/playwright.config.mjs --update-snapshots
      - name: Commit changed baselines
        run: |
          git config user.name "design-bot"
          git config user.email "design-bot@users.noreply.github.com"
          git add -A <<tests/e2e>>/__screenshots__
          git diff --cached --quiet || git commit -m "Update design screenshots (review every changed image)"
          git push
```

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

---

## 19. Accessibility, adaptivity and phones

### 19.1 What the source already does

- **Keyboard and focus:** `:focus-visible` gets a 2px solid blue outline with 3px offset on every interactive element; the active cell shows an inner ring (`react-focus-in`, 180 ms).
- **Semantic controls:** `<details>/<summary>`, `fieldset/legend`, `button[aria-pressed]`, labelled groups (`role="group" aria-label`).
- **Visually hidden labels:** `position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%)`: for assistive tech when a glyph stands alone.
- **Hue is never the only carrier.** The number is always printed; colour is a second channel (R26).
- **Reduced motion:** blanket `animation: none; transition: none`, restated beside the animations. The celebration hook does not start. The finale mark is still drawn.
- **Low bloom:** Dim and Veil raise the black level, lower the lit plane, remove glows and text-shadows, lower watermarks and the spine, switch the cursor's pure white to ink. The `html` background is set too, so overscroll never flashes the unlit canvas.
- **`prefers-contrast: more`:** harder edges, *not* brighter ink.
- **Firm letters** and **Board size** are accessibility dials as much as taste.
- **Salon:** neutral labels, a monochrome alternative, no drag-only interaction, and accessibility choices never recorded as evidence about the person.

### 19.2 What to add in a new project (not in the source; verify yourself)

- `@media (forced-colors: active)`: restore borders and outlines; drop gradients.
- A text equivalent for any information carried only by light (for example "3 left" next to the remaining-light indicator).
- Test with at least one screen reader and keyboard-only.

### 19.3 Phones: an honest note

The source's *macro* composition (ground + two lanes + floating instruments) is built for wide screens (it holds a 1180px minimum width and was verified at 1440×1000). Its phone layout is an older, plain stylesheet, not this language. **The language is not yet resolved for phones in the source.** Everything *below* macro carries over unchanged: tokens, ramp, ember/flame/halo, ignition, view tiers, low-bloom, voice. For macro on a phone (an extrapolation, untested here), a sensible reading is:

- The ground becomes a **top band**, carrying the four-corner backlight at reduced size.
- The two lanes become **segments** (a two-state switch), not columns; the pole colours remain the switch's accents.
- Instruments stay glass but collapse into one **bottom dock**.
- The View panel opens upward as a sheet.
- Tap targets ≥ 40px; the chip stays 42×32.
- Re-run the screenshot matrix at 390×844 and 360×740.

---

## 20. Glossary

**Design terms**
- **Ramp**: the rank → hue mapping. **Rank**: an item's 0..1 position among distinct identities. **Arc**: the hue range a pole owns. **Contour**: the per-rank lightness offset that lets the arc fit sRGB evenly.
- **Pole**: one of the two kinds of item (the source: Across, Down). **Lane**: a list of one pole's items.
- **Ember / flame / halo**: the three lights (§6.4). **Light budget**: how much light each state may spend (§9.2).
- **Ground / figure / instruments**: the macro composition (§7.2). **Bezel**: the thin frame of the ground. **Paper**: the work surface. **Grout**: the seams between paper tiles.
- **Notch / gate tick**: the open address of an item, drawn as a short filament. **Spill**: the short fall of light from a notch along its item.
- **Strip / track / run**: the answer slots under a clue, torn from the board; balanced groups of ≤ 5.
- **Charge / libido / remaining**: the economy of light (§10). **Remainder**: what a closed item leaves.
- **Ignition**: a light that flares once. **Afterglow**: what a finished thing leaves. **Vibration**: tiny finite feedback on contact.
- **Territory**: the screen's four corners of colour. **Backlight**: the ground lit by territory.
- **Salon**: the second register for arrival, reflection and reading.
- **Scales**: macro (composition), mini (comfort), micro (reading aids), nano (fine cues).

**Theory terms (use in comments and notes only)**
- **Signifier**: a mark that means by differing from other marks.
- **The Other (symbolic order)**: the system of rules that does not negotiate.
- **Objet petit a**: not the thing desired but the lack that causes desire; here, the notch.
- **Jouissance / drive**: enjoyment that includes resistance; repetition around an obstacle.
- **Après-coup / retroactive determination**: a later event determines what the earlier one was. Here taken as a *semiotic* regularity, requiring no subject of the unconscious.
- **Metonymy**: displacement along a chain; an aim attained and immediately found not to be the aim.
- **Imaginary / Symbolic / Real**: image and recognition / rules and convention / what resists symbolisation.
- **Unmarked (unchecked) cell**: a position that belongs to no crossing: "a signifier with no Other".
- **Sublation**: a form is abolished, its content preserved and its level changed. Here: the first misreading is preserved in the resolution.
- **Mise-en-scène**: placing an object so that a relation to it becomes a question.

**A warning from the source:** "negation of the negation" has an unfortunate habit of licensing any two-step optimism ("failure leads to success!"). Wherever a design rationale could be summarised as "the problem is actually good", it has been misread.

---

## 21. Provenance

This guide was distilled from the Crossword app repository: the React app's stylesheets, its view-settings code and view cluster, the board-cue and celebration logic, the onboarding ("salon") screens, the planning notes on signification, clue grammar and the critique of the concept, and the commit history (where most of the lessons live).

For a human who wants to trace a rule to its source:

| Topic | Where it lives in the Crossword repo |
| --- | --- |
| Tokens, surfaces, ladder, glass, controls, light theme, motion contract | `apps/react/src/desktop.css` |
| Ramp, contour, ember/flame/halo, lit group, tracks, notches, tiers, view panel, territory, libido | `apps/react/src/vision.css` |
| Zig-zag chain, depth pass | `apps/react/src/lattice.css` |
| Row-that-leaves, sparks, wash, note, confetti, finale | `apps/react/src/celebration.css`, `celebration.js` |
| Settings contract | `apps/react/src/viewSettings.js`, `ViewControls.jsx` |
| Ranks, runs, spotlight, gate cues | `apps/react/src/boardCues.js` |
| Springs | `apps/react/src/ClueSpring.jsx`, `springGeometry.js` |
| Salon register | `apps/react/src/future/future.css`, `FutureApp.jsx`, `Signifier.jsx` |
| An example agent brief | `LIQUID_GLASS_PROMPT.md` |
| Theory | `docs/plans/09_SIGNIFICATION_AND_THE_AHA.md`, `14_CLUE_GRAMMAR_MEANING_AND_ENJOYMENT.md`, `15_THE_SELF_CRITIQUE_OF_THE_CONCEPT.md` |
| Lessons | `git log -- apps/react/src/vision.css apps/react/src/desktop.css` |

**What is tested and what is not.** The starter code in section 14 was run in headless Chromium 141: dark, light and dim renders, computed colours read back, ignition and settle durations and iteration counts, no infinite animations, territory publishing under real scrolling, the View panel by clicking (persist, pressed state, reset, corrupt storage falling back). The e2e suite in section 17 was run under Playwright 1.55: 37 tests across 4 projects, green twice in a row on identical screenshots, then **mutation-tested** with injected defects (section 17.11), which exposed and fixed real gaps in the starter and in the tests themselves (section 15, items 29 to 37). The static audit was run against the starter, against a negative control (the Crossword app's own sources, which predate the portable token names) and against seeded violations.

**Not tested:** phones beyond a 390px layout check (section 19.3 is extrapolation), forced-colors, screen readers, GitHub Actions itself (the workflows are valid YAML but were not executed here), a Vue/Svelte/React app other than the plain-HTML demo, and the dark-mode contour fit, which gives a first draft near, not equal to, the source's hand-tuned values.
