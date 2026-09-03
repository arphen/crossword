# ADR 0003: Legacy-replica pivot for the v2 web app

Status: accepted, 2026-09-03 (owner directive during live review).

## Context

The "next generation" refresh (docs/plans/06) rebuilt the solver around a new
visual system (oklch tokens, de-boxed spine, panorama composition) while
reusing the domain core. Owner review of the running app rejected it twice:

1. the clue-field highlight was invisible (root cause: the base active-row
   rule painted through `var(--axis-whisper)`, which was never defined — the
   background silently computed to transparent in every browser);
2. the layout had no standard/compact modes, so at the owner's window size
   the grid was pushed off-screen into a sliver and every "cell" click landed
   on clue-spine answer cells that share `data-cell-id` with grid cells but
   carry no key handlers — typing and arrows appeared dead;
3. the overall look read as an inferior replica of the legacy product.

## Decision

1. The v2 React app replicates the legacy product **exactly**: components
   emit the legacy DOM structure (`newapp.html`) and the legacy stylesheet is
   ported verbatim (`apps/web/src/legacy.css`, 2029 lines).
2. Legacy interaction semantics are restored: real inputs per white cell,
   arrow/letter/backspace behavior (arrows switch direction at their family
   edge), wrapped mirrored clue columns with odd/even seam numbers, giant
   rotated watermarks, stats indicator bar, weekday random loading through
   the local bridge, and a color-scheme night toggle.
3. The rewrite's foundations are retained underneath: domain solve engine,
   application use cases, IndexedDB persistence, in-browser model runtime
   (ADR 0002), harness fixtures, and the Playwright/e2e suite — now written
   against legacy selectors with screenshot baselines of the legacy look.

## Consequences

- Visual parity is enforced by tests: paint guards assert legacy colors and
  scales; visual baselines are committed and reviewed by the owner.
- The next-generation look (docs/plans/06) is deferred until the owner
  chooses to evolve from the replica — the replica is the reference, not a
  placeholder for someone else's taste.
- Known simplifications vs legacy: the rebus context menu uses a prompt, the
  Solution button is a no-op (no NYT links in the deployable app), the cache
  and solved modals are merged into one locally backed list, and multiplayer
  remains out of scope.

## References

- `src/crossword/` — legacy app (behavioral oracle, untouched)
- `docs/plans/06_DESIGN_LANGUAGE_REFRESH.md` — deferred refresh spec
- `docs/e2e.md` — the test suite guarding this decision
