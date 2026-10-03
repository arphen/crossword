# Research: Small-Gemma editor matching NYT clue grammar, fixing too-easy boards

## Goal
Train/use a small Gemma editor (local-small tier, M3 16GB) that drafts clues with NYT-level grammar/quality and non-trivial difficulty, re-auditing the reverted guards instead of re-adding regexes. Success is harder-but-fair boards, not higher admission alone.

## Success Metric
- **Metric:** critic_score in [0,1], higher-is-better. `0.30*A + 0.30*T + 0.25*W + 0.15*D` where A=admissionRate (15-answer benchmark), T=1-trivialRate, W=goldRate (cold-solver behavioural buckets, Python-classified), D=1-min(1,L1/0.5) vs NYT Monday family mix. Judge soundness excluded (40% precise, calibration-v1.20261003).
- **Target:** >= 0.68 with admitted>=13/15 and guardHits==0
- **Direction:** maximize

## Constraints
- **Max iterations:** 20
- **Time budget per experiment:** 5 minutes (`timeout 5m`)
- **Pause for review every:** never (fully unattended to max_iterations or target; progress noted, never blocked)
- **Evaluator:** (none — agent + subagents judge manually; research/gemma-editor/evaluate.py critic score advisory only)
- **Keep policy:** score_improvement (min_delta 0.02, noise_runs 3; mutation must clear champion-replicate spread)
- **Guard:** guardHits==0, admitted>=13/15, `tests/test_private_puzzle_generation.py` green, census disagreement vs NYT <0.5% new hits, no clue text committed to docs/evidence (counts-only per clue_review_bundle.py:20,147)
- **Noise runs:** 3
- **Min delta:** 0.02

## Current Approach
Strict champion admits 13-14/15 (41/45 over fresh seeds, 70-72/72 full boards) with zero pseudo-puns and zero guard hits, but families are 12-14/15 definition + 10-14/15 plain-definition (`benchmark-v1.20261003.json`). Cold-solver: 16% Monday, gold 0.000 on known-good controls (broken as gold instrument, kept as trivial/gold behavioural buckets only). Census baseline 4193 hit-cells over 1,231,048 NYT pairs (gerund 2006 + for-some 580 + baseline 1601). Generator `llama3.2:3b`, critic `gemma3:4b` (both installed; 26B tiers absent).

## Search Space
- **Allowed changes:** anything — MLX/LoRA small-Gemma edit pass on NYT subsets (Fri/Sat misdirection), prompt/divergence/delimited-draft lanes, k-draft + comparison ranking, critic admission (gemma3:4b over 3b drafts), weekday exemplars, guard restores strictly via census (gerund strict-only keep; for-some strict-only watch; 0-hit gates keep; broad hedge/filler/bloat/obscure-head stay reverted per 13a7e0a/089bc71/deb1940)
- **Forbidden changes:** hand-edit docs/REPO_MAP.md; commit answer-bearing clue text to docs/evidence; exceed host memory (no 26B pulls); live-provider data-gen without opt-in; break public package exports/worker schemas; weaken leak/duplicate-copy rejection

## Context & References
- Audit: 359 commits; revert chain c85e099->abf0ce3->ab39f30 (gerund/for-some operator override), 32c618d->deb1940 (identity 99:1 fair), 1a49bf7->089bc71 (vague-abstraction 11:1), 59f3d61->0afb376->13a7e0a (RIVER/vibe), 68b7bf6->a6b2d30 (hedge 12k->0 circles-only); finetuning-drop verdict 4c95e01 (portable core only); doctrine deletion 5c48f0a (code unchanged)
- Too-easy roots: definition needs no witness (`clue_witness.py:287`), pun needs only `?`+ledger token (`:144-152`), ledger ~50 entries misses SEE/WEB/COLD (`:44-97`), genre census report-only (`clue_genre.py:203-225`), single-draft no comparison (`16_CLUE_QUALITY_RECOVERY.md:12`)
- Harness: `scripts/private-clue-benchmark.py:40` run_iteration, `scripts/clue-cold-solver.py:231` probe + `:204` _classify, `scripts/autoresearch-decision.py:47` noise-floor rule, `scripts/autoresearch-loop.sh:1` loop, tiers `tiers-v1.m3-16gb-20261001.json:19-31`, calibration `judge-calibration-v1.20261003.json:10-17`
- Dataset: `crossword_clue_answer_examples/` 14547 files / 14545 puzzles / 1231048 pairs (not 10M)

---

## History
| # | Change | Metric | Result | Timestamp |
|---|--------|--------|--------|-----------|
| 0 | Baseline dry-run seed 6200: strict champ llama3.2:3b gen + gemma3:4b behavioural critic; A=1.0 (15/15), T=0.8, W=0.0, D=0.703, guardHits=0, wall 198s => score 0.6455, pass false (W=0 confirms too-easy) | 0.6455 | -- | 2026-10-03 |
| 1a | Noise floor seeds 6201/6202 strict: 14/15 + 15/15, guardHits 0, draftCalls 5-6; admitted ceiling saturated — mutations must match 15/15 and improve secondary (W/T/D, draftCalls). Logs /tmp/clue-benchmark-noise620*.json | -- | measured | 2026-10-03 |
| 1b | Prototypes (no src change): delimited parser research/gemma-editor/prototype_delimited.py self-test ok; exemplar pack /tmp/gemma-exemplars-20261003.json 12 items, dedupe 6/6 | -- | ready | 2026-10-03 |
| 2 | Iter1 CROSSWORD_DELIMITED_DRAFTS ablation seed 6200 strict, JSON vs delimited: both 14/15 admitted, guardHits 0, A=0.9333 T=0.7857 W=0.0 D=0.6785, score 0.6175 vs 0.6175, draftCalls 6/6; lane engaged (receipt flag, reason mix shifted: answer-giveaway 6 vs 16, duplicate-draft 2 vs 0). Delta 0.00 < 0.02 -> REVERT. Note replicate spread: published baseline 0.6455 (15/15) vs this replicate 0.6175 (14/15) — same seed, nondeterministic decode | 0.6175 vs 0.6175 | revert | 2026-10-03 |
| 3 | Iter2 CROSSWORD_WEEKDAY_EXEMPLARS (pack anchors in prompt + verbatim-copy reject-as-duplicate regenerates) seed 6200 strict: 14/15 admitted, guardHits 0, A=0.9333 T=0.8571 W=0.0 D=0.6821, score 0.6394 vs champion-best 0.6455, draftCalls 5 vs 6. Bar = 0.6455+0.02 = 0.6655; 0.6394 sits inside the champion-replicate band [0.6175, 0.6455], does not clear spread -> REVERT. Noise seeds (admission only): 6201 13/15, 6202 14/15, guardHits 0. Judge host-load caveat: tight-loop probe 500s, scored via paced probe (buckets trivial 2/unresolved 7/unfair 5/scaffold 1) | 0.6394 vs 0.6455 | revert | 2026-10-03 |
| 3 | Iter2 CROSSWORD_WEEKDAY_EXEMPLARS ablation seed 6200 strict (llama3.2:3b gen, gemma3:4b paced behavioural critic): admitted 14/15, guardHits 0, A=0.9333 T=0.8571 W=0.0 D=0.6821, score 0.6395, draftCalls 5, gen wall 62s. Buckets over 14 non-scaffold: trivial 2, unresolved 7, unfair 5, gold 0. Anchors shifted misses trivial->obscure (unfair 5) not trivial->gold (0); W still 0. Delta -0.006 vs best 0.6455, below keep 0.6655 -> REVERT. Probe ops: rogue dup probe (system python, no flask) killed pre-write; good probe died 8/15, remaining 13 resumed via /tmp/iter2-rerun.py (8s pace, 90s timeout, error isolation), judge wall 706s. Logs /tmp/iter2-gen-log.json, /tmp/iter2-buckets.json | 0.6395 | revert | 2026-10-03 |
| 4 | Iter3 CROSSWORD_RELAX_FOR_SOME ablation seed 6200 strict: admitted 14/15, guardHits 0, A=0.9333 T=0.7857 W=0.0 D=0.7131, score 0.6227, draftCalls 6, gen wall 126s. Buckets over 14: trivial 3, unresolved 6, unfair 5, gold 0. Zero admitted clues carry for-some tails — relaxation is a no-op at this seed (unit gate verified flipping; benchmark drafts never use the tail). Delta -0.023 vs best -> REVERT. Judge /tmp/judge15.py clean 15/15, wall 606s, 0 errors. Logs /tmp/iter3-gen-log.json, /tmp/iter3-buckets.json | 0.6227 | revert | 2026-10-03 |
| 5 | Iter4 CROSSWORD_PLAIN_DEF_CAP ablation (half-board cap on plain-definition, reviewed-exact exempt) seed 6200 strict: admitted 7/15, guardHits 0, A=0.4667. Cap binds as designed (6 plain admitted, remainder scaffolded plain-definition-over-cap) but admission collapses below guard floor 13/15 -> keep impossible, judge skipped -> REVERT. Finding: plain definition is the bulk surface; any binding cap costs ~7 admission — variety must come from drafting, not scaffolding. Gen wall 116s. Log /tmp/iter4-gen-log.json | A=0.4667 guard-fail | revert (guard) | 2026-10-03 |
| 5 | Iter3r CROSSWORD_ROUTE_CONTEXT=1 (signifier senses in prompt + verbatim block) seed 6200 strict, no src change: 15/15 admitted, guardHits 0, A=1.0 T=0.8667 W=0.0 D=0.6785, score 0.6618 vs bar 0.6655 -> REVERT (+0.0163 over best, misses min_delta). Numbered 5: sibling relax-for-some owns 4. Paced probe /tmp/iter3-probe.py: trivial 2/unresolved 6/unfair 7 (7A 500-artifact individually retried -> unfair, 0 errors), wall 672s. Reading: routes buy full admission + fewer trivial but add unfair misses, gold still 0 — obscurity without fair paths. Logs /tmp/iter3-receipt.json (label iter3-routes), /tmp/iter3-buckets.json | 0.6618 vs 0.6455 | revert | 2026-10-03 |
