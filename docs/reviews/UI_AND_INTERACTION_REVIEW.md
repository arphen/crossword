# UI and Interaction Review

**Review state:** Living review — useful first pass, visual verification in progress  
**Review snapshot:** `v2@ccd3450`, including the uncommitted UI/E2E work present on 2026-09-03  
**Audience:** Agents implementing React UI, CSS, interaction, accessibility, responsive behavior, and browser tests

## Product experience to preserve and elevate

The distinguishing idea is not merely “a crossword next to clues.” On desktop, the grid is the visual and interaction hinge, with two clue spines arranged concentrically around it. The clue display must keep answer length and entered-letter state perceptually attached to the relevant clue. The experience should feel immediate, calm, legible, and crafted at long solving sessions—not like a dashboard and not like a generic NYT clone.

The recent legacy-replica commit is a useful fidelity reset: it protects the working interactions and proportions that made the original app loved. The next UI step should build a coherent contemporary design system around that interaction grammar, not replace it with fashionable decoration.

## Provisional executive finding

The repository now contains a dedicated legacy presentation layer, browser harnesses, Playwright journeys, visual baselines, paint guards, day/night palettes, responsive work, and an accessibility spec in progress. That is the right evidence-oriented direction.

The key review question is still open: does the current app preserve the concentric clue–grid relationship at real desktop and laptop sizes while making active answer length and typed letters effortless to parse? Snapshot coverage alone cannot answer that. The live browser and keyboard/a11y pass below must be completed before declaring the UI refreshed.

No claim in this document marked **VERIFY** should be treated as passed until its viewport/input evidence is recorded.

## Experience principles

1. **Grid as hinge.** Across and Down spines should feel anchored to the corresponding sides of the grid, with balanced seam geometry.
2. **Relevant state at a glance.** Active clue, enumeration, current pattern, conflict/completion state, and direction must be legible without searching.
3. **Quiet depth.** Use color, borders, typography, and restrained highlights before blur, glow, or large shadows. Battery/paint cost is a product constraint.
4. **Keyboard truth.** Arrow keys, typing, Backspace/Delete, Space/direction switching, Tab behavior, and clue clicks must be predictable.
5. **Responsive recomposition.** Narrow screens should intentionally change hierarchy; they should not be a squeezed desktop.
6. **Accessible equivalence.** Focus, selection, errors, completion, and progress require non-color signals and useful announcements.
7. **Legacy continuity.** Solving muscle memory and daily operational continuity take priority over visual novelty.

## UI release matrix

| Area | Required evidence | Current state |
|---|---|---|
| Desktop composition | Screenshots and interaction at 1440×900 and 1280×720 | **VERIFY** |
| Laptop pressure | No clipped controls/clues at 1024×768 | **VERIFY** |
| Mobile portrait | Intentional grid/clue flow at 390×844 | **VERIFY** |
| Mobile landscape/tablet | Usable at 844×390 and 768×1024 | **VERIFY** |
| Keyboard | Complete solve/edit/navigation journey without pointer | **VERIFY** |
| Screen reader semantics | Grid/clue labels, active state, announcements, landmark order | **VERIFY** |
| Zoom/reflow | 200% zoom without loss of content/function | **VERIFY** |
| Themes/contrast | Day/night plus forced-colors and reduced-motion | **VERIFY** |
| Performance | No continuous expensive paint; stable interaction during long solve | **VERIFY** |
| Persistence/error UX | Refresh/resume, generation progress/cancel/failure/retry | **VERIFY** |

## First findings and risks

### P1 — Treat the concentric clue spines as a tested layout invariant

This is the product's signature interaction. Encode it as more than a screenshot. At desktop breakpoints, the inner edges of the Across and Down clue columns should visually terminate at the grid seams, their active rows should remain discoverable, and neither column should become a remote scrolling pane whose active item disappears.

**Agent acceptance criteria**

- At supported desktop sizes, grid center and seam spacing remain within named design-token tolerances.
- Activating a grid entry reveals/highlights its clue in the appropriate spine without disorienting scroll jumps.
- Clicking a clue activates the correct entry and returns a visible, meaningful grid focus state.
- Long clue text, long enumerations, and near-complete answer patterns do not break the seam.

### P1 — Define one canonical active-answer presentation

The active clue needs one unmistakable visual treatment shared by clue row, grid cells, and the linked pattern/enumeration. Avoid competing “selected,” “active,” “related,” and “current” colors with ambiguous priority.

A robust hierarchy is:

- active cell: strongest local focus marker;
- active answer cells: restrained continuous track;
- active clue row: matching accent edge/background plus semantic state;
- crossing clue/entry: secondary indication only;
- confirmed error and completion: separate icon/pattern/text semantics, never just a hue.

### P1 — Keep the legacy replica as a behavioral oracle, not the final architecture

`apps/web/src/components/legacy/` and `legacy.css` make continuity explicit, which is valuable. Before layering a new system on top, extract the behavioral contract into interaction tests and identify which visual values become tokens. Otherwise “legacy” can turn into a permanent parallel application with duplicated rules and inaccessible custom behavior.

**Agent acceptance criteria**

- React components receive semantic puzzle/view state rather than recomputing crossword rules.
- No duplicate keyboard/navigation implementation exists between legacy and future surfaces.
- Tokens cover palette, type, cell scale, seams, borders, elevation, motion, and responsive density.
- Migration happens component by component behind the same behavioral journeys.

### P1 — Accessibility must test behavior, not only axe output

The uncommitted `apps/web/e2e/accessibility.spec.ts` is welcome. Automated rule scanning is necessary but insufficient for a crossword grid. The team must test the accessible name/state of cells and clues, focus movement, typed-letter announcements, direction changes, errors, and completion.

**Agent acceptance criteria**

- Each cell exposes coordinate/number, block/open state, entered letter, and active direction without unbearably verbose repeated output.
- The active clue can be reached and understood without reading the full DOM twice.
- Direction toggles and puzzle completion use a polite live region.
- Focus remains visible in both themes and forced-colors mode.
- Reduced-motion removes nonessential animation; interaction never depends on hover.

### P2 — Add explicit paint and battery budgets

The prior design attempt reportedly consumed excessive battery with glows and shadows. Keep the existing paint guards, then turn this concern into enforceable constraints:

- no infinite decorative animation during solve;
- no large-area animated blur/filter/backdrop-filter;
- no filter-based glow on every grid cell or clue row;
- shadows limited by token count and painted area;
- scroll and keypress handlers do not force layout repeatedly;
- measure a representative 20-minute idle/solve trace before release.

Static gradients and small, non-animated shadows are usually cheap; the guard should target actual compositing/paint hazards rather than banning all depth.

### P2 — Responsive behavior needs a product decision per breakpoint

Recommended hierarchy:

- wide desktop: `Across spine | grid | Down spine` with concentric alignment;
- compact desktop/tablet landscape: grid remains primary, spines narrow or use a coordinated active-clue rail;
- portrait/mobile: grid first, sticky active clue/pattern, then direction tabs or a single virtualized clue list;
- very short landscape: protect grid size and active clue; move secondary chrome out of the first viewport.

Do not render both full desktop clue columns below the point where they can preserve readable line lengths.

### P2 — Generation states belong in the same design language

An LLM-required app needs deliberate states for model unavailable, model loading/download, artifact loading, ideation, fill attempts, clue writing, validation, cancellation, retry, and a retained last playable puzzle. Avoid a generic spinner: show the deterministic stages and meaningful progress without exposing noisy chain-of-thought or fake precision.

## Verified source and baseline findings (2026-09-03 pass 1)

### P1 — The committed 1136px baseline is visibly below a playable clue-width floor

The baseline `apps/web/e2e/visual.spec.ts-snapshots/standard-1136-chromium-darwin.png` shows both clue spines still beside a 600px grid. Because each spine also wraps its clues into two inner columns, many clues render nearly one word per line. The test calls this “stacked mode,” but the stylesheet has no stacking query at that width.

This is not polish: 1136px is a normal laptop window and clue scanning is core gameplay. Introduce a measured compact-desktop composition before either clue half falls below its readable line-length/token floor. A baseline is evidence of appearance, not evidence that the appearance is acceptable.

### P1 — The current mobile layout is mathematically wider than the viewport and then clips it

At `max-width: 768px`, `--cell-size` becomes `2rem`, so the grid alone is 480px before borders/padding. `#notmenu` remains a single three-column flex row; the two clue columns remain present; `body` hides horizontal overflow (`apps/web/src/legacy.css:71-101, 1579-1623`). On a 390px viewport, essential content therefore cannot fit or reflow.

The new forced-colors E2E test uses 390×844 but checks only axe results, so it cannot catch this. Add geometry assertions (grid/clue/control bounding boxes within the visual viewport), then implement a portrait hierarchy rather than another shrink factor.

### P1 — Grid entry relies on physical-key `keydown`, not the input editing model

Every white cell is a controlled `<input value={letter}>` with no `onChange`, `onInput`, or paste/composition handling (`apps/web/src/components/legacy/LegacyGrid.tsx:131-146`). State changes only for single Latin letters observed in `keydown`. This excludes paste, dictation, IME/composition, and can fail with mobile virtual keyboards. It also advertises rebus length up to ten while the handler accepts only one letter.

Retain the fast desktop key path, but add a tested input/composition contract and a deliberate rebus mode. The same journeys must pass with Playwright `fill`/input events and a mobile browser project, not only `page.keyboard.type`.

### P1 — Clue and pattern interactions are pointer-only despite an extra tab stop

Clue rows use clickable `<li>` elements and answer cells use clickable `<span>` elements without button/link semantics or keyboard handlers (`ClueColumn.tsx:69-105`). The current uncommitted change adds `tabIndex=0` to the outer column, which creates a focus stop but exposes no action and does not make its children operable.

Use semantic buttons or an intentional composite/listbox pattern with roving focus and documented keys. Do not rely on axe alone: the accessibility suite currently filters out all moderate violations and exercises no keyboard access to clue selection.

### P1 — Down selection never reaches the CSS direction switch

Down-grid highlighting depends on `body[data-active-direction="down"]` (`legacy.css:1841-1848`), but the application never writes that attribute. The active grid answer therefore keeps the Across/orange treatment even when Down is selected. Existing paint tests exercise only Across.

Prefer a semantic `data-direction` on the solver root derived directly from React state, and add paired Across/Down computed-style assertions.

### P1 — Two prominent actions are misleading or inert

The `Solution` button has no handler (`App.tsx:351-353`). The `Complete` button opens the solved-puzzles/history modal without completing or checking the puzzle (`App.tsx:354-355`). These controls must either perform the labeled action with confirmation/assistance accounting or be removed until implemented.

### P1 — Dialog behavior is visually modal but not semantically modal

Both overlays are generic `<div>` trees without `role="dialog"`, `aria-modal`, labelled-by wiring, initial focus, focus containment, Escape handling, or focus restoration (`App.tsx:425-493`). The close button is announced only as the multiplication character. Add behavioral screen-reader/keyboard tests; an axe scan cannot prove modal focus management.

### P2 — CSS is still an append-only legacy sheet, not a governed design system

`legacy.css` is now over 2,000 lines, contains obsolete selectors, repeated overrides, multiple `transition: all` declarations, hidden-scrollbar rules, large watermark text shadows, and blur effects. The good news is that the formerly infinite highlight animation is no longer applied. The file has no reduced-motion or forced-colors rules, however, and the new “phase 2” rules are appended after the legacy layers rather than replacing them.

First characterize and tokenise; then delete dead/conflicting rules in small visual-baseline-backed slices. Add a CSS lint/test rule for infinite animation, large-area filters, `transition: all`, invisible focus, and unreviewed z-index/elevation values.

### P2 — Several state/semantics mismatches deserve regression tests

- Completed clues are removed from the DOM rather than collapsed (`ClueColumn.tsx:60`), causing the spine to reflow throughout a solve and making completed clue review impossible.
- The grid receives `session.checkedCellIds` while clue columns receive the `checking`-gated set (`App.tsx:280-283, 360-363`), so check paint can diverge.
- Cell accessible names are zero-based coordinates only and omit number, direction, value, and block/crossing context (`LegacyGrid.tsx:133`).
- The dark-mode initializer reads `localStorage` without the error handling used for solved history, so restricted storage can prevent first render (`App.tsx:56`).
- The stylesheet hides document and clue scrollbars, weakening overflow discoverability.

### Verification note — the unit suite confirms the controlled-input defect

`npm run web:test` passes 6 files / 16 tests, but React emits the “value prop without an onChange handler” warning once for every open grid input across App/harness mounts, producing a very large stderr stream. Treat console warnings as test failures after fixing the input contract; otherwise real React warnings will remain invisible in noise.

### Verification note — build passes, but the local-model surface is heavy

`npm run web:build` passes. The output includes two approximately 6MB model worker/runtime assets in addition to the main UI bundle. Confirm they are lazy, deduplicate where possible, and display honest model download/storage progress. A frontend-only architecture still needs transfer, cache, and update budgets.

### Verification note — live review caught an in-flight broken tree

At the 2026-09-03 live-review checkpoint, Vite could not render because the actively edited `apps/web/src/harness/fixtures.ts` was missing a comma before the new `rebus` fixture (`:130`). That same edit mutates a readonly puzzle/cell via JSON casting. This may be transient concurrent work, but the branch should not be handed off as reviewable until the web build is rerun after all UI agents stop writing.

The corresponding new rebus E2E is also disconnected from state: the harness passes `onEnterRebus={noop}`, while the test expects the prompt to change the input. Separate static visual fixtures from interactive test hosts, or explicitly give this harness a reducer/session owner.

## Agent action queue

| Order | Owner | Deliverable | Done when |
|---:|---|---|---|
| 1 | UI test agent | Viewport/keyboard baseline matrix | Evidence exists for every row in the release matrix |
| 2 | Interaction agent | Canonical selection/navigation state model | Grid and clues share one tested state machine |
| 3 | CSS/design-system agent | Tokenize the proven legacy geometry and refreshed visual language | No one-off active/seam/theme values remain in component CSS |
| 4 | Accessibility agent | Manual semantic/focus review plus automated checks | Keyboard and screen-reader journeys pass in both directions/themes |
| 5 | Responsive agent | Intentional wide/compact/portrait layouts | No squeeze/clipping and active clue remains visible |
| 6 | Performance agent | Paint/compositing budget and trace | No continuous paint hazard; budget recorded in CI/docs |
| 7 | UI agent | Model-generation progress/error/cancel surfaces | Every construction terminal state is recoverable and comprehensible |

## Visual-review checklist

- [ ] The first glance lands on the grid and active clue, not toolbar chrome.
- [ ] Across and Down read as two halves of one solving instrument.
- [ ] Answer length and entered-letter pattern remain attached to the active clue.
- [ ] Typography distinguishes clue number, clue prose, enumeration, and pattern without visual noise.
- [ ] Empty, filled, active, related, error, checked, revealed, and complete cells are distinct in both themes.
- [ ] Grid lines remain crisp at common device-pixel ratios.
- [ ] Long translated/non-English UI strings do not collide or truncate essential controls.
- [ ] Scrollbars and sticky regions do not obscure clue text.
- [ ] Day and night feel designed, not merely inverted.
- [ ] Decorative effects are static or bounded and do not punish battery life.

## Evidence log

| Evidence | Result |
|---|---|
| Git snapshot and UI/test inventory | Recorded 2026-09-03 |
| Source/DOM/CSS audit | Pass 1 complete; blocking findings above |
| Existing committed visual baselines | Inspected at 1440×900, 1136×900, and half-complete harness |
| Web TypeScript/Vite build | PASS |
| Web unit/component tests | PASS (16), with high-volume controlled-input warnings |
| Live 1440×900 review | Blocked at checkpoint by Vite parse error in active fixture edit |
| Live compact/mobile review | Not run yet |
| Keyboard journey | Not run yet |
| Accessibility semantics | Not run yet |
| Theme/forced-colors/reduced-motion | Not run yet |
| Paint/performance review | Not run yet |

## Instructions to implementing agents

- Preserve solve behavior first; attach each visual refactor to an existing or new browser journey.
- Prefer CSS variables and semantic state attributes over component-local style calculations.
- Do not approve UI from a single full-page screenshot. Inspect active, partially solved, wrong, complete, loading, and failed states.
- Record viewport, theme, fixture, and commit with every visual baseline.
- Update this document's evidence log with links to exact specs/screenshots/traces when closing an item.

## Status update — 2026-09-03, implementing agent (post-review pass)

Findings addressed in one verified pass (unit 16, build clean, e2e 30 — including new
geometry/paint/dialog journeys; baselines regenerated where composition changed).
Commit: see `git log` after this file's date; branch v2, pushed.

- **Down direction paint (P1)** — fixed: the app writes `body[data-active-direction]`
  from React state; new e2e asserts the blue grid highlight under Down selection.
- **Compact-desktop composition (P1)** — fixed: 769–1180px stacks grid-first with
  full-width readable clue lanes; new geometry e2e at 1136 (grid above clues, lanes
  >= 700px, nothing outside the viewport). Baseline regenerated with this rationale.
- **Mobile 390px clip (P1)** — fixed: `--cell-size` is fluid
  (`min(2rem, (100vw - 48px) / 15)`); new e2e asserts grid width <= 390 and no
  horizontal scroll.
- **Input editing model (P1)** — fixed: grid inputs gained `onChange` (paste,
  dictation, IME, autofill) and `onPaste` multi-letter entry; the controlled-input
  console-warning flood is gone at source; `fill()`-based e2e added.
- **Keyboard operability (P1)** — partial: clue rows and answer cells are
  tabbable with Enter/Space handlers and labels; list semantics preserved
  (li stays listitem; only answer spans are role=button). Full roving-focus
  composite remains open.
- **Misleading buttons (P1)** — fixed: Solution removed (no NYT links in the
  deployable app); Complete records the solve and opens the solved modal.
- **Dialog semantics (P1)** — fixed: role=dialog, aria-modal, labelled-by,
  autofocus close, Escape closes (e2e journey added). Focus containment and
  restoration remain open.
- **Checked-set divergence (P2)** — fixed: grid and clue columns receive the
  same checking-gated sets.
- **Dark init restricted storage (P2)** — fixed: try/catch on read and write.
- **Richer cell names (P2)** — partial: grid inputs announce number/row/column/
  letter/selection; clue-row labels announce number, direction, clue text.
- **Scanner FAIL (from the generation review, apps/web/e2e scope)** — fixed:
  reviewed exemption for negative-network specs (test-only, until M4.1).
- **Rebus harness noop (from the generation review)** — noted; the interactive
  replica (App) owns real state and the rebus journey passes against it; making
  the *harness* stateful is queued with the harness rework.

Open (not yet addressed): roving-focus composite for clue rows, focus
containment/restoration in modals, CSS governance/tokenization slices,
paint-budget trace, generation progress surfaces (generation agent).
