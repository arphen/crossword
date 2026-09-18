# Luna delegation prompts

Paste-ready work packages for implementation agents (Copilot in VS Code or any
equivalent). One agent per package; never two agents on the same files.

Coordination status 2026-09-02: **Luna 1, Luna 2, Luna 3, MR-1, SCAN-1 are
in flight repo-side.** Before delegating one of them, check `git log --oneline`
— if its integration commit has landed, the package is done; do not re-run it.
**Luna 4 and Luna 5 are assigned repo-side** (GLM subagents) and run chained
after Luna 1–3 integrate — do not delegate them. Copilot stays available for
future new packages, not for these.

## Ground rules for every prompt (prepend to any paste)

> You are working in the repo at `/Users/arphen/projectc/crossword`.
> Read `AGENTS.md`, `docs/plans/README.md`, and the relevant quiet-glass
> reference assets under `design/quiet-glass/` before editing.
> You own ONLY the files listed; do not edit anything else. Do not run
> `npm install`, do not change lockfiles, do not `git commit` — the
> coordinator reviews and commits. Run the acceptance commands and include
> their exact output, your decisions, and residual risks in your report.
> Do not weaken tests to make them pass.

## Luna 1 — Visual harness and fixtures (IN FLIGHT repo-side)

Ownership: `apps/web/src/harness/**` (new) and `apps/web/src/main.tsx` only.

1. Add a harness route selectable by URL (for example `/harness?fixture=…`),
   rendering the existing solver components against deterministic fixture
   puzzles and sessions. No network, no model, no randomness at render time.
2. Build the fixture set from the quiet-glass references under
   `design/quiet-glass/` and the current solver state matrix: empty 15×15; active Across with affected Down;
   active Down with typed crossings; check error; half complete with collapsed
   clues; long clue + 15-letter answer; rebus + circled + shaded; dark mode;
   forced colors; 200% zoom. States the current components cannot yet express
   get a documented placeholder, not a fake.
3. Deterministic session snapshots (fixed clock, fixed selection) per fixture.
4. Do not style the production solver; do not touch `App.tsx`, `ClueSpine.tsx`,
   or `styles.css`.

Acceptance: every fixture reachable by URL and listed in one index fixture;
`npm --workspace @crossword/web run test` and `npm run web:build` pass; report
lists fixture IDs and the data attributes each exercises.

## Luna 2 — Clue topology and linkage (IN FLIGHT repo-side)

Ownership: `apps/web/src/components/ClueSpine.tsx`, new
`apps/web/src/cluePlacement.ts`, new
`apps/web/src/components/ClueSpine.test.tsx`, plus additive-only helpers in
`packages/domain/src/` if the index lacks a crossing lookup.

1. Keep the stable lane/row placement projection (`index % 2` outer/inner,
   `Math.floor(index / 2)` row) in a dedicated module; completion, filtering,
   and nudges must never mutate placement (`docs/plans/06…` §6).
2. Implement the linked-state contract §7: derive affected (crossing) entries
   and shared cell IDs from `PuzzleIndex` — never a second selection model.
   Active entry strong; crossings quiet; exact shared answer cell marked.
3. Add the required hooks/semantics §15: `data-direction` on the field,
   `data-entry-id` and `data-state` (`active|affected|solved|idle|error`) on
   rows, `data-lane`/`data-row` on placed clues, `data-cell-id` on answer-cell
   controls; accessible names include number, direction, clue, length, pattern.
4. Completion policy `visible | collapsed (default) | hidden` per §6.3; a row
   shrinks only when both paired entries are collapsed.
5. Keep the exported props backward-compatible (add optional props only) —
   `App.tsx` is another agent's file. Do not restyle beyond keeping existing
   class names working.

Acceptance: component tests cover placement stability, crossing propagation,
direction-toggle linkage, pattern-cell click selecting the exact grid cell, and
the three completion policies; `npm --workspace @crossword/web run test` passes.

## Luna 3 — Center-stage composition (IN FLIGHT repo-side)

Ownership: `apps/web/src/App.tsx`,
`apps/web/src/components/ActiveClueDock.tsx` (may rename to
`ActiveClueBridge.tsx`), `apps/web/src/components/SessionCommands.tsx` (may
rename to `SolveCommands.tsx`), new `apps/web/src/components/SolveClock.tsx`.

1. Remove the hero composition (`play-header` oversized title region) and
   replace with the utility rail + puzzle identity rail of `docs/plans/06…`
   §9: wordmark, save state, active time, settings; title at 22–32 px with
   weekday/size/provenance metadata. No development copy ("Local workspace /
   offline ready") in the production surface.
2. Center stage holds grid + active-clue bridge + command strip reachable
   without scrolling (§8). The bridge shows number, direction, clue, live
   answer cells, Nudge, and the crossing clue subordinate.
3. Fix the timer re-render: `App.tsx` currently calls `setSession` every
   second and re-renders the whole tree. Move the visible clock into
   `SolveClock` with its own state/subscription so a tick does not re-render
   the grid or clue spines (prove it with a render-count test).
4. Do not change domain or persistence behavior; do not edit `ClueSpine.tsx`
   (another agent owns it) — consume its existing props.

Acceptance: composition test asserts regions and command reachability; the
timer-isolation test passes; full web suite and `npm run web:build` pass.

## Luna 4 — Visual tokens and CSS (repo-side after Luna 1–3 land)

Ownership: `apps/web/src/styles.css` and token definitions only.

1. Implement the quiet-glass design language against the Luna 1 harness:
   bilateral seam-facing alignment, semantic states from the
   §7.3 matrix, panorama/standard/compact modes (container queries preferred),
   light/dark, forced colors, reduced motion, reduced transparency.
2. Forbidden: `transition: all`, infinite animation, animated filters or
   shadows, backdrop filters on the solver surface, one-off hex values.
3. The grid gets the one strong static elevation; panels use borders first;
   max routine radius 7 px; grid cells stay square.
4. Compare every visual decision against the harness fixtures, not against
   the live solver.

Acceptance: the §16 visual-composition criteria pass at 1920×1080 / 1440 /
1280 / 200% zoom; the §16 fixture matrix snapshots render sensibly; idle page
settles to browser-baseline CPU (document how you measured).

## Luna 5 — Accessibility, visual regression, energy gates (repo-side after Luna 4)

Ownership: browser tests, axe checks, screenshot baselines, performance
instrumentation; production code changes limited to defects the suite finds
and must be reported.

1. Playwright journeys: keyboard-only solve, direction toggle, clue and
   pattern selection, check/reveal/nudge, pause/resume, complete, reload and
   resume offline.
2. axe: no serious/critical violations; state matrix §7.3 verified to have
   non-color cues; forced-colors and reduced-motion screenshots intelligible;
   screen-reader announcement includes active + crossing clue context.
3. Visual baselines for the §16 fixture matrix; mask the clock; never
   auto-approve a baseline from the change that broke it.
4. Record key-to-paint, long tasks, layout shift, and 60 s idle behavior in a
   concise evidence report.

## MR-1 — Model runtime swap to in-browser WebLLM (IN FLIGHT repo-side)

Ownership: `packages/model-runtime/src/**`,
`apps/web/src/workers/modelWorker.ts`, `apps/web/src/workers/modelClient.ts`,
`apps/web/src/modelConfig.ts`, and their tests.

1. Implement ADR `docs/adr/0002-in-browser-model-runtime.md`: remove the
   Ollama adapter and `VITE_LOCAL_MODEL_URL`; add a WebLLM adapter
   (`@mlc-ai/web-llm` is installed in `packages/model-runtime`, 0.2.84) behind
   the existing `LocalModelAdapter` port, loaded by dynamic import inside the
   model worker (`CreateWebWorkerMLCEngine`).
2. Keep the deterministic fake adapter for tests; keep the broker state
   machine (uninstalled → installed → loaded → generating → unloaded) and
   cancellation semantics intact.
3. `modelConfig.ts`: `distribution: 'webllm-mlc'`, a pinned dev-default MLC
   model ID (small, e.g. a 1B q4f16_1 model from `prebuiltAppConfig`), and a
   `browserRuntimeProbe()` that reports WebGPU availability. Final model pin
   stays an open owner decision — note it, do not decide it.
4. No fetch to any localhost inference endpoint anywhere in `apps/` or
   `packages/`.

Acceptance: both suites pass, `npm run web:build` passes, and
`grep -ri ollama apps packages` returns nothing; report includes the dev
model ID chosen and why.

## SCAN-1 — Forbidden-content scan skeleton (IN FLIGHT repo-side)

Ownership: `scripts/scan-forbidden-content.mjs` (new), a `scan:content` script
entry in the root `package.json`, `docs/content-scan.md` (new).

1. Scan the deployable graph only (`apps/`, `packages/`, `apps/web/dist/` if
   present) for: NYT/syndication endpoints and hostnames, xwordinfo links,
   `ollama`, `127.0.0.1:11434`, and a starter list of legacy clue/answer
   sample strings from `docs/plans/00_LEGACY_AUDIT.md`. `src/crossword` (the
   private Flask bridge) is explicitly exempt — document that.
2. Patterns live in a committed JSON config so the list can grow without code
   edits; exit non-zero on any find; `--report <file>` writes JSON evidence.
3. Do not wire it into CI yet — skeleton plus docs, per backlog PR 3.

Acceptance: running `npm run scan:content` on the current tree passes with a
clean report, and deliberately adding a banned string to a scratch file makes
it fail (show both outputs, then delete the scratch file).
