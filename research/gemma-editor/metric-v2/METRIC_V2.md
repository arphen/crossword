# Critic metric v2 — Friday-anchored (paradigm shift support)

Prototype scope. New files only: this dir + `/tmp/friday_metric.py` +
`/tmp/friday_anchors.json`. `src/`, `tests/`, `docs/`, `research.md`,
`evaluate.py` untouched. Promotion to the evaluator is a main-agent decision.

## 1. Formula

```
score_v2 = 0.30*A + 0.35*T + 0.10*W + 0.25*D_fri   (weights sum to 1.0)
D_fri    = 1 - min(1, L1_friday / 0.5), L1 over the 7 families in anchors.json
A = admitted/15, T = 1 - trivial/judged, W = gold/judged (unchanged defs)
```

Target: **score_v2 >= 0.78** with admitted >= 13/15 and guardHits == 0.
Keep-policy (min_delta 0.02, 3 noise runs) unchanged; next-keep bar is
0.7825 + 0.02 = **0.8025**. The iter4r KEEP (0.6818, v1 scale) is grandfathered:
under v1 weights + Friday anchor it rescores 0.6735 (below the old 0.68 line),
which is exactly why the target is recalibrated rather than carried over.

## 2. Why the weights change

- **D 0.15 -> 0.25, anchor Monday -> Friday-combined.** The Monday anchor
  (definition 0.91963, tricky 0.00636) compresses scores: every 3b board is
  87-100% definition, so D sits in a 0.50-0.71 band and the gap between an
  all-definition board and a 1-tricky board is 0.0245 (0.6785 vs 0.7030).
  Friday-combined (definition 0.90588, tricky 0.02877, 296,632 pairs) widens
  that gap to 0.1101 (0.6235 vs 0.7336) — 4.5x decompression — while
  penalising all-definition boards (0.6785 -> 0.6235) and rewarding the one
  board shape closer to hard-NYT (0.7030 -> 0.7336). Friday-only shares differ
  by <0.002 per family; combined is used for the larger denominator.
- **T 0.30 -> 0.35.** Non-triviality is the only behavioural signal that moves
  (0.7857-0.9333 across judged runs). The `/tmp/friday_metric.py` Q01
  synonym-distance gate (token-overlap + answer-stem comparative check:
  more shady/SHADIER flags tautological-comparative, WOES/Misfortunes does
  not; 6/6 self-test + 5/5 anchor checks pass) feeds T, so T carries more.
- **W 0.25 -> 0.10.** The gold instrument is broken: 0 gold over 71+ judged
  entries and 0.000 on known-good controls. A 0.25 dead weight caps the
  achievable max at 0.75 and gates the target on a signal that never fires.
  W stays nonzero so future gold registers; restore to 0.25 (and rescale the
  target) once known-witty controls score gold.
- **A stays 0.30.** Admission is saturated (0.93-1.0) and already floored by
  the admitted>=13/15 guard; no reweight needed.

## 3. Target derivation (from the Friday reference, not carried over)

Reference good-hard board: A=1.0, T=0.85 (~2 trivial/15), W=0.05
(aspirational until the instrument is fixed), D_fri=0.75 (L1 0.125 from the
Friday mix ~= 2 tricky/15, rest definition):
0.30 + 0.35*0.85 + 0.10*0.05 + 0.25*0.75 = 0.30+0.2975+0.005+0.1875 = **0.79**.
Rounded down one noise point -> **0.78**. Cross-check: max achievable with
W=0 is 0.90; 0.78 is 86.7% of it, vs old 0.68 = 90.7% of 0.75 — slightly
easier in relative terms, justified because D_fri punishes the reigning
all-definition champion shape.

## 4. Baseline rescore (seed 6200, A=1.0 T=0.8 W=0)

The published D=0.703 at 15/15 is uniquely consistent with a 14-definition +
1-pseudo-pun board (reproduces 0.7030 against MONDAY_SHARE; all other 15-mixes
miss by >=0.01; verified in `/tmp/friday_metric.py`). Under Friday anchoring:

| board (seed 6200)              | Dmon  | Dfri  | v1+Mon (publ.) | v1+Fri | v2+Fri |
|--------------------------------|-------|-------|----------------|--------|--------|
| B0 baseline 14+1pseudo         | 0.7030| 0.7336| **0.6455**     | 0.6500 | 0.7634 |
| iter4r KEEP 15def              | 0.6785| 0.6235| 0.6818         | 0.6735 | 0.7825 |
| iter3-routes 15def             | 0.6785| 0.6235| 0.6618         | 0.6535 | 0.7592 |
| iter2 13def+1meta (n=14)       | 0.6821| 0.6302| 0.6394         | 0.6317 | 0.7375 |
| iter5 13def+2factual           | 0.5013| 0.4991| 0.6152         | 0.6149 | 0.7048 |
| iter3-relax 13def+1fact (n=14) | 0.7131| 0.6559| 0.6227         | 0.6141 | 0.7190 |

Reading: re-anchoring alone (+0.0045 on B0, -0.0083 on iter4r) moves the old
target's pass/fail line — iter4r falls below 0.68 — so v2 must be read on its
own 0.78 scale, where B0 (0.7634) fails, iter4r (0.7825) passes by 0.0025
(thin: next keep needs 0.8025), and the rank order is preserved. Honest
caveat unchanged from the log: W=0 everywhere, so v2 still scores A+T+D_fri;
the gold-instrument fix remains the real next step.

## 5. Files

- `anchors.json` (this dir): Friday-combined shares + superseded Monday map.
- `/tmp/friday_metric.py`: D_fri, v1/v2 scorers, Q01 stem gate, self-test
  (6/6 pairs, 5/5 anchor reproductions), `baseline_rescore()`.
- `/tmp/friday_anchors.json`: /tmp-owned mirror of `anchors.json`.
