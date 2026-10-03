# Subagent-max mode (local override for autoresearch)

Applies to `research/gemma-editor/` only. Global skill files unchanged.

## Rule
Every loop iteration MUST fan out to subagents. Never run sequential-only.
Minimum concurrency: 2 background subagents active at all times during iterations 1-20.
Pause checkpoints (`pause_every: 5`) are the only idle-allowed state.

## Fan-out per iteration
1. **Understand** → 1 subagent: receipts + census + ledger diff (read-only)
2. **Hypothesize** → 1 subagent: single-variable change proposal with file:line + metric prediction (read-only)
3. **Experiment + Evaluate** → 1-2 subagents on non-overlapping scopes:
   - Parser/prompt prototype in `research/gemma-editor/` (new files only), OR
   - Noise-floor benchmark seeds writing only to `/tmp` (counts returned, clue text never committed)
4. Main agent: merges kept changes, runs `tests/test_private_puzzle_generation.py`, updates `research.md` History, commits.

## Non-overlap
Background subagents own their output paths. Main agent never edits those paths mid-flight.
Production edits (`src/crossword/private_puzzle_generation.py`) happen in foreground after subagent prototypes land.

## Visibility
Each fan-out posts sessionID + scope before starting. Completion posts metric delta + keep/revert.
