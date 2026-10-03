# Rescore: all judged boards under the restored metric (Friday anchor, W restored)

- Formula: `score = 0.30*A + 0.30*T + 0.25*W + 0.15*D_fri`
- `D_fri = 1 - min(1, L1_Friday/0.5)` over the 7 families in
  `research/gemma-editor/metric-v2/anchors.json` (Friday-combined, 296,632 pairs).
- Method: recompute `D_fri` from admitted-family census only; **reuse**
  published `A/T/W` verbatim (buckets in `/tmp/*-buckets.json` + History rows in
  `research/gemma-editor/research.md`). **Nothing re-judged; W stays 0** for all
  old runs (gold instrument fired 0/71+ pre-fix).
- `T` denominators are judged non-scaffold counts as published
  (14 for 14-admitted boards, 15 for 15-admitted boards).
- Counts-only: no clue text.

## Restored scores (seed 6200 unless noted)

| rank | board | A | T | W | families (n) | D_fri | restored | published (Mon) |
|------|-------|---|---|---|--------------|-------|----------|-----------------|
| 1 | iter4r-diverge (ROUTE_DIVERGE+CONTEXT) | 1.0 | 0.9333 | 0 | 15 definition (n=15) | 0.6235 | **0.6735** | 0.6818 |
| 2 | iter3r-routes (ROUTE_CONTEXT) | 1.0 | 0.8667 | 0 | 15 definition (n=15) | 0.6235 | **0.6535** | 0.6618 |
| 3 | baseline (strict champ) | 1.0 | 0.8 | 0 | 14 definition + 1 pseudo-pun (n=15) | 0.7336 | **0.6500** | 0.6455 |
| 4 | iter2 (WEEKDAY_EXEMPLARS) | 0.9333 | 0.8571 | 0 | 13 definition + 1 metalinguistic (n=14) | 0.6302 | **0.6317** | 0.6394 |
| 5 | iter5 (k-draft breadth, env-only) | 1.0 | 0.8 | 0 | 13 definition + 2 factual-relation (n=15) | 0.4991 | **0.6149** | 0.6152 |
| 6 | iter3-relax (RELAX_FOR_SOME) | 0.9333 | 0.7857 | 0 | 13 definition + 1 factual-relation (n=14) | 0.6559 | **0.6141** | 0.6227 |
| 7 | iter1 (DELIMITED_DRAFTS) | 0.9333 | 0.7857 | 0 | 14 definition (n=14) | 0.6235 | **0.6092** | 0.6175 |
| -- | Q01 stem-gate (judge PENDING) | 0.9333 | -- | -- | 13 definition + 1 factual-relation (n=14) | 0.6559 | **--** | -- |

Bucket sources: iter1 `A/T/W` + families from History row 2 + `/tmp/iter1b-receipt.json`;
iter2 buckets `/tmp/iter2-buckets.json` + families `/tmp/iter2-receipt.json`;
iter3-relax buckets/families from History row 4 (no surviving bucket file; D=0.7131
anchor-check fixes the 13+1factual shape); iter3r `/tmp/iter3-buckets.json`
(T=0.8667 reused as published over 15: trivial 2/unresolved 6/unfair 7) + families
`/tmp/iter3-receipt.json`; iter4r `/tmp/iter4-buckets.json` + families
`/tmp/iter4-receipt.json`; iter5 `/tmp/iter5-buckets.json` + `/tmp/iter5-gen-log.json`;
Q01 families `/tmp/q01-seed6200-log.json` (14/15 admitted, guardHits 0).

## New ranking vs old

Old (Monday) order: iter4r > iter3r > baseline > iter2 > relax > iter1 > iter5.
New (Friday, restored) order: iter4r > iter3r > baseline > iter2 > iter5 > relax > iter1.
Top-4 order preserved; only the bottom three reshuffle (all-definition iter1 sinks
below the factual-relation boards once Friday punishes pure-definition mass).

## Keep bar

Best restored = iter4r 0.6735. Keep bar = best + 0.02 = **0.6935**
(admitted >= 13/15, guardHits == 0 unchanged).
Target note: under the restored metric the best board (0.6735) sits **below**
the 0.68 target line (target was met 0.6818 on the Monday scale only) — no
judged board currently passes; Q01 judging is the next scorer input, not a
re-judge of old boards.
