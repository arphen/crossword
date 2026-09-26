# Product and solving-experience plan

> **25 September 2026 supersession notice:** Read the [active personal crossword plan](06_PERSONAL_EPISTEME.md) and [ADR 0003](../adr/0003-local-ollama-native-runtime.md) first. The owner has selected the current React/Flask application, Ollama and native construction. Browser-only, backend-free, new-static-workspace and conflicting delivery instructions below are historical. The active plan also governs initial visual calibration, weekday recipes and clue grammar.

Status: target product contract.

## Product promise

Build a private crossword companion that feels as polished and rhythmically
progressive as the best daily crossword products, but whose puzzles are
original, culturally configurable, locally generated, and shaped by how the
household actually solves.

The application is not an examination engine and not a topic quiz. It is a word
game first. Personalization should preserve broad linguistic surprise,
misdirection, playful clueing, familiar connective fill, and the satisfaction
of learning recurring crossword vocabulary.

## Experience invariants

The following behavior is part of the product identity:

1. The grid is the stable center of attention.
2. On panoramic desktops, Across and Down clues form mirrored fields around the
   grid.
3. Each field has two lanes meeting at a visible number spine.
4. Every clue displays its enumeration/pattern and the letters already entered.
5. Clue, pattern cell, grid entry, active cell, and crossing clue are linked in
   both directions.
6. Across and Down have distinct but accessible visual identities.
7. Monday through Sunday are recognizable modes with stable expectations.
8. Solving can be entirely keyboard-driven and remains excellent with touch,
   zoom, a screen reader, and reduced motion. Original-puzzle generation is
   available only when the required local AI capability is installed and
   enabled.
9. All personal history and profiling is local, inspectable, exportable, and
   resettable.
10. Effects celebrate meaningful moments and never create continuous background
    work during an ordinary solve.

## The clue spine, made explicit

The present implementation achieves the two-lane spine through wrapping and
`nth-child(odd/even)`. Removing a solved clue changes DOM parity and causes
later clues to jump sides. The redesign makes the layout a domain projection:

```text
outer edge      lane A     number spine     lane B      grid
                  clue 1   1   2   clue 2
                  clue 3   3   4   clue 4
                  clue 5   5   6   clue 6
```

Each entry receives a stable `rail`, `lane`, and `row` when the puzzle view is
created. Completion changes presentation, not placement. Users can choose:

- `visible`: keep solved clues with a quiet check;
- `collapsed`: retain the fixed numbered footprint and hide text/pattern;
- `hidden`: reclaim space, with the resulting reflow explicitly requested.

Default to `collapsed`. It preserves spatial memory while creating the pleasant
opening-up effect of the legacy app.

The active clue receives one strong treatment. Crossings receive a lighter
treatment. Other clues remain calm. The answer pattern is always legible and
clickable; blank, filled, checked, revealed, rebus, circled, and shaded states
are not represented by color alone.

## Responsive modes

Breakpoints are layout capabilities, not device labels. Use container queries
and measured grid/clue space, with these reference modes:

### Panorama

Approximate starting range: 1440 CSS pixels and wider.

- two-lane Across spine on the left;
- centered grid and minimal session rail;
- two-lane Down spine on the right;
- active clue scrolls into the nearest comfortable viewing band;
- rail scroll positions persist independently;
- metadata and puzzle actions stay visually subordinate to play.

### Standard desktop / landscape tablet

Approximate starting range: 1000–1439 CSS pixels.

- one Across rail and one Down rail around the grid;
- clue numbers align toward the grid;
- full linked patterns remain present;
- optional inspector replaces dense always-visible statistics.

### Compact

- grid first;
- sticky active-clue card with number, direction, clue, pattern, and crossing;
- tabbed or bottom-sheet clue browser;
- same solve-session core and same puzzle document as desktop;
- touch targets at least 44 CSS pixels even when visual cells are smaller;
- browser zoom remains enabled.

There is no separate mobile solver. The old multiplayer role page remains a
legacy-only experiment until multiplayer is redesigned.

## Interaction contract

### Selection

Use one state object:

```ts
type Selection = {
  cellId: CellId;
  direction: Direction;
  entryId: EntryId;
};
```

The active entry is derived from the active cell and direction. There is no
second `activeDirection` variable to drift out of sync.

- Click/tap an unselected cell: select it while retaining a valid direction.
- Click/tap the selected crossing cell: toggle direction.
- Click a clue: select its first unresolved cell, otherwise its first cell.
- Click a pattern position: select that exact grid cell and direction.
- Arrow keys: move spatially and update selection consistently.
- Tab/Shift+Tab: next/previous entry, not browser-focus entrapment.
- Space or a dedicated key: toggle direction without entering a letter.
- Backspace: clear current content or move backward according to the published
  solve-session rule; the rule is characterized before migration.
- Rebus entry: explicit command/menu plus paste support; never a hidden
  right-click-only feature.

### Checks, nudges, and reveals

- Check cell, entry, or puzzle are separate actions.
- Reveal cell, entry, or puzzle require increasing confirmation proportional to
  scope.
- A "nudge" can replace a clue with an easier grounded variant without revealing
  letters. This exploits the clue-ladder architecture and provides a better
  adaptive assist than arbitrary scoring penalties.
- Assistance is recorded for profile calibration but never used to shame or
  inflate a single public score.

### Timing

Track active solve time from monotonic timestamps. Pause when the page is hidden,
the puzzle is explicitly paused, or inactivity exceeds a configurable threshold.
Retain wall time only as optional diagnostic context. Never update the entire
solver tree once per second; isolate the visible clock.

### Completion

Completion is a short state transition:

1. grid and clue rails resolve into their completed state;
2. show a concise result card with active time, assists, and a human-readable
   insight;
3. offer another day, a review of newly learned words, or export;
4. run celebration motion only when permitted by the user's effect setting.

Provide `off`, `subtle`, and `full` celebration levels. Cap canvas work and
close any audio context when finished.

## Daily contracts

Weekday labels are recipes, not a global ladder that silently gets harder as
the model profiles the user. A player may lock a tier or tune it explicitly.

- **Monday:** 15x15, clean high-quality fill, direct clues, generous crossings,
  and an accessible theme.
- **Tuesday:** 15x15, broader vocabulary, light misdirection, and wordplay.
- **Wednesday:** 15x15, balanced general knowledge and word intelligence; the
  current household center.
- **Thursday:** 15x15, gimmicks, rebuses, transformations, and deceptive clue
  surfaces.
- **Friday:** 15x15 themeless/open style, longer answers, harder clueing, and
  little weak glue.
- **Saturday:** 15x15 themeless, the most oblique clueing and broadest
  vocabulary, with fair crossings.
- **Sunday:** 21x21 or another large format, deferred until 15x15 quality and
  latency gates pass.

Original construction will not perfectly reproduce a professional editorial
calendar in its first release. Ship modes only when their recipe passes a
human solve panel and automated quality gates. Before then, label unavailable
modes honestly rather than serving a Monday fill with Saturday clues.

## Personalization users can feel and control

### The local model is a product prerequisite

This product does not offer a non-AI original-construction mode. First-run
onboarding verifies WebGPU support, available storage, model download and
integrity, structured-output reliability, and a short warm-up evaluation. If
those gates fail, the application explains the missing capability instead of
quietly substituting generic clues or an inferior canned generator.

"AI enabled" does not mean "GPU occupied throughout the solve." Construction
runs in a dedicated worker and prepares a small, integrity-checked local queue
of puzzle manifests. Once a puzzle is fully generated and validated, the model
may be unloaded and the player can finish it offline without a hot model.
Creating the next original puzzle requires the enabled model again. This is the
energy and privacy contract: local intelligence at construction time, a calm
deterministic application at play time, and no cloud inference fallback.

Settings expose understandable controls:

- preferred locale(s) and language variants;
- explicit subject likes, dislikes, and hard exclusions;
- brand, celebrity, politician, abbreviation, foreignism, and proper-name
  tolerance;
- desired day/tier and challenge band;
- clue styles to encourage or reduce;
- novelty versus reinforcement;
- single-player profile or a named household blend;
- AI/model, storage, battery, motion, sound, and privacy controls.

The derived profile is inspectable as a set of tendencies and recent examples,
not an unexplained vector. Users can edit explicit preferences, delete raw
events, rebuild the profile, or reset it completely.

For a two-person household puzzle, build an `AudienceProfile` from both named
profiles. Default to a cooperative blend: avoid material strongly disliked by
either player, target a challenge band both can enter, and take interests from
the union so one player does not permanently dominate.

## Progress without streak coercion

Reimplement the useful idea from `origin/more-metadata` as a local learning
atlas rather than a GitHub clone:

- calendar of completed puzzles and active time;
- vocabulary encountered, reinforced, and newly mastered;
- clue mechanisms that are becoming comfortable;
- topic and locale breadth;
- recurrence of crossword glue;
- median time-to-insight by day, normalized for puzzle recipe;
- checks/reveals as neutral learning data, not failure badges.

Do not optimize for daily streak anxiety. The objective is a richer solving
practice with the user's partner.

## Visual system

The target is editorial clarity with a slightly uncanny technical edge—not
glass on every surface.

- Establish semantic tokens in OKLCH with light, dark, high-contrast, and
  reduced-transparency themes.
- Reserve the orange/blue pair for Across/Down relationships.
- Use one type family for editorial clue text and one restrained mono/numeric
  face for patterns, numbers, and instrumentation.
- Give the grid the strongest contrast and geometry.
- Keep background `ACROSS` / `DOWN` marks static, low opacity, and paint-cheap.
- Use one radius scale, one elevation scale, and one focus-ring system.
- Move checks, reveals, score, cache, and diagnostic detail into a quiet command
  surface rather than five permanent cards above the grid.
- Use opacity and transform for 120–240 ms event transitions. Avoid
  `transition: all`, animated filters, large animated shadows, and perpetual
  pulse.

Create visual explorations behind a component story/harness before restyling the
live solver. Compare at least three directions using the same fixture puzzle;
select one based on readability, identity, contrast, and measured paint cost.

## Accessibility contract

- Use a roving-focus ARIA grid (or an equivalent tested composite) rather than
  200 independently tabbed inputs.
- Announce clue number/direction, clue text, letter position, answer length,
  current pattern, and crossing clue.
- Every clue and pattern position is a keyboard-operable control.
- Dialogs have accessible names, focus containment, Escape handling, and focus
  restoration.
- Status changes use a restrained live region.
- Correct/error, Across/Down, selected/crossing, and revealed states have shape,
  text, or icon cues in addition to color.
- Honor reduced motion, forced colors, higher contrast, reduced transparency,
  200% zoom, and coarse pointers.
- Never disable viewport zoom.

## Performance and energy budgets

Budgets are measured on a representative mid-range laptop and phone, in a
production build:

- no continuous `requestAnimationFrame` during ordinary solving;
- no solo-mode socket or network connection after required assets are cached;
- no model inference while the user is actively typing;
- p95 key-to-paint below 50 ms and no interaction long task above 50 ms;
- layout shift effectively zero during a solve, including clue completion;
- idle CPU near browser baseline with the timer visible;
- no large-surface backdrop blur on the primary layout;
- no repeating shadow/filter animation;
- generation and AI workers are cancellable and expose their resource state;
- ten-minute solve trace shows bounded memory and no listener/timer growth;
- Lighthouse performance and accessibility at least 95 for the deployable
  representative route, supplemented by real interaction traces.

Battery optimization is measurement-led. A beautiful static shadow is not
automatically a problem; repeated paint, uncontrolled timers, persistent
connections, and inference are.

## Experience acceptance suite

Every release candidate is exercised with:

- panorama, standard, compact, light, dark, reduced-motion, and forced-color
  modes;
- 15x15 and 21x21 documents;
- long clue, duplicate clue text, rebus, circled, shaded, and combined cells;
- keyboard-only and touch-only solve journeys;
- screen-reader smoke tests and automated accessibility checks;
- start, resume, check, nudge, reveal, finish, export, import, offline reload,
  and PWA update flows;
- visual snapshots of the clue spine at empty, half-complete, and complete
  states;
- a bounded performance trace and console/network cleanliness check.
