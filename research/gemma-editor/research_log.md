# Gemma-editor research log (counts only — never commit clue text)

## Iter1 — CROSSWORD_DELIMITED_DRAFTS gate (REVERT)
- Change: `ID|ANSWER|clue` line wire format in `run_draft_round`
  (plain-text chat, per-line validate via prototype logic, same records shape,
  line errors mapped to `malformed-draft*`, admit/compare/safety untouched).
- Ablation seed 6200 strict (`llama3.2:3b` gen, `gemma3:4b` critic):
  JSON: admitted 14/15, guardHits 0, A=0.9333 T=0.7857 W=0.0 D=0.6785,
  score 0.6175, wall 192s.
  Delimited: admitted 14/15, guardHits 0, identical A/T/W/D,
  score 0.6175, wall 221s, draftCalls 6/6.
- Lane verified engaged via receipt flag + reason mix
  (answer-giveaway 6 vs 16, duplicate-draft 2 vs 0, compareCalls 13 vs 11).
- Delta 0.00 < min_delta 0.02 -> REVERT src + tests to champion.
- Observation: same-seed replicate spread is real (published baseline 0.6455
  at 15/15 vs this replicate 0.6175 at 14/15); keep-policy correctly refuses
  to keep a no-gain lane. Logs: /tmp/iter1-json6200.json,
  /tmp/iter1-delim6200.json, /tmp/iter1-verify.out.
