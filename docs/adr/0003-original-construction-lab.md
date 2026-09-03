# ADR 0003: Original construction laboratory (LACUNA pipeline)

Status: accepted (laboratory stage, per docs/plans/02 graduation path)

## Context

The product needs original, full-sized (15x15) NYT-style construction as a
drop-in replacement for the household solve flow. The LACUNA spike (nontext/)
sketched the right shape — model supplies soul, deterministic engine owns the
grid — but its implementation was not production-grade. The plans gate
Rust/WASM on benchmark evidence and gate each weekday on recipe-specific
quality evidence.

## Decision

1. **Deterministic engine first, in TypeScript.** `packages/construction`
   implements a bitset CSP with:
   - letter-domain bitset propagation (26 letters x bitset words per
     intersection), maintained arc consistency from a worklist (MAC);
   - word-level undo trail (one entry per modified 32-bit word, popcount
     deltas), eliminating clone-per-node;
   - preference-sorted candidate indexes (sort once; per-node value order is
     ascending index order);
   - assignment-time all-different and seeded restarts;
   - `lockedWords` for model-supplied theme entries.
   The engine boundary (`PuzzleFillGrid`) stays a port; a Rust/WASM port
   requires the benchmark evidence gate from the plans and remains open.

2. **Measured template bank over synthetic search.** Random topology search
   produced structurally valid but fill-hostile masks. The bank is instead
   seeded from a proven human mask (`human-15x15`, the legacy reference grid:
   fills in ~2s at 79 nodes) and — in progress — from fill-judged structural
   patterns extracted from the household's local published-puzzle archive
   (`scripts/extract-nyt-topology.py`, `scripts/judge-nyt-templates.mjs`).
   Masks derived from the local archive are private-household construction
   inputs; no clue or answer text enters any artifact, and the content scan
   stays green.

3. **Lab lexicon with two artifacts**, both built deterministically and
   digest-pinned:
   - `fill-lexicon-v1` — public-domain Webster's Second word list, normalized
     (227,485 words, lengths 3-15);
   - `freq-prior-v1` — top-6000 answer-frequency prior derived from the
     household-local published corpus, lifting crossword staples in the
     preference score. Eligibility stays with web2 membership; the prior
     never grants eligibility.

4. **Adaptive learner layer** per `docs/crossword research.md`:
   `packages/construction/src/adaptive.ts` implements FSRS-style
   retrievability, ZPD surprisal alignment with crossing-aware decay,
   intersection affordance, and recency fatigue. Scores blend with base
   crossword quality (`blendScore`) as a preference multiplier. The learner
   profile is local household data.

5. **Day recipes Mon-Sat, Sunday gated.** `packages/application/src/recipes.ts`
   pins per-day template lists, quality thresholds, theme-lock counts, clue
   mechanism mixes, and search budgets. Sunday reports `recipe-unavailable`
   honestly (21x21 bank and resource gates do not exist yet).

6. **Manifest assembly is validator-gated.** `assemblePuzzleManifest` runs
   `assertValidPuzzle` before returning; integrity digest is finalized
   asynchronously with real SHA-256 (`finalizeIntegrity`) and re-validated.
   Failed candidates are typed diagnostics; no half-puzzle can publish.

7. **App wiring.** More menu gains a Construct control (day selector +
   button). It loads the lexicon artifacts from the app origin, requires the
   model-loaded state, and drops the constructed manifest straight into the
   existing solve flow via `replacePuzzle`. Browser-external `node:crypto`
   was removed from the loader; the runtime digest is a documented FNV-1a
   correlation hash while the build manifests pin authoritative sha256.

## Consequences

- The engine fills the proven human mask with the full lab lexicon in ~2s
  (79 nodes), and the whole model-to-manifest pipeline runs in ~6s under the
  fake adapter.
- Per-length local index classes (2026-09-03) cut real-mask fill time by
  ~16-26x with identical node counts and scores (same search, smaller
  bitsets): Monday masks that took 22-65s now fill in 1.4-2.5s. The judge
  harness over the household archive confirms 40/40 sampled Monday and
  Tuesday grids solve with the lab lexicon (best 1.4s / 79 nodes), which
  keeps construction inside a background-queue budget on the TypeScript
  engine and keeps the Rust/WASM gate open rather than urgent.
- Synthetic random topology search is retired as a bank source: only
  fill-measured templates (human mask now, corpus-judged survivors as they
  land) enter the bank, each with measured fill evidence in its notes.
- The frequency prior is derived from the household's local archive: it is a
  private artifact, word-frequency statistics only, no clue/answer strings,
  and is excluded from public-release claims until the M2.1 owner review.
- Known limitation (honest): themed long entries that are phrases (multi-word)
  need the model candidate bag as locks (Thursday recipe already reserves
  this); web2-only fills prefer templates whose long slots are single words.
