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

## Iter2 — CROSSWORD_WEEKDAY_EXEMPLARS ablation (REVERT)
- Change: Monday style anchors in the draft prompt (`_weekday_exemplars`
  from pack `CROSSWORD_EXEMPLAR_PACK` w/ route-index fallback, verbatim
  copies rejected as duplicate drafts), off by default, measured with
  `CROSSWORD_WEEKDAY_EXEMPLARS=1`.
- Generation seed 6200 strict (`llama3.2:3b`): admitted 14/15, guardHits 0,
  draftCalls 5, compareCalls 12, families definition 13 + metalinguistic 1
  (plain-definition genre 11/14), D=0.6821, gen wall 62s.
- Behavioural critic (`gemma3:4b`, paced, 14 non-scaffold judged):
  trivial 2, unresolved 7, unfair 5, gold 0 => T=0.8571, W=0.0.
- Score 0.30*0.9333+0.30*0.8571+0.25*0+0.15*0.6821 = 0.6395, delta -0.006
  vs best 0.6455, below keep 0.6655 -> REVERT src + tests to champion.
- Reading: anchors made misses obscure rather than witty (unfair 5 vs
  gold 0); trivial rate fell (2/14) but W stays 0.0 — harder-but-fair
  still unsolved. Next mapped: for-some gate, genre caps, k-draft rounds.
- Probe ops: prior driver left two probes — a duplicate under system
  python (no flask, every entry error) killed before its end-of-run write
  could clobber the verdict file; the healthy probe died at 8/15 (cause
  unknown, judge tested healthy after). Remaining 13 entries resumed via
  /tmp/iter2-rerun.py (resume from buckets.json, 8s pacing, 90s timeouts,
  2 retries, per-entry error isolation, incremental writes), 0 errors,
  judge wall 706s. Logs: /tmp/iter2-gen-log.json, /tmp/iter2-buckets.json,
  /tmp/iter2-rerun.log.

## Iter3 — CROSSWORD_RELAX_FOR_SOME ablation (REVERT)
- Change: `CROSSWORD_RELAX_FOR_SOME=1` skips the strict `vague-for-some`
  rejection (drafts fall through to `admit_candidate`); receipt carries
  `forSomeRelaxed` flag. Unit test drives `_make_candidate_clues` with a
  mocked chat: strict rejects `... for some ...` as vague-for-some and
  scaffolds; relaxed admits it cleanly.
- Generation seed 6200 strict: admitted 14/15, guardHits 0, draftCalls 6,
  families definition 13 + factual-relation 1 (plain-definition genre 13),
  D=0.7131, gen wall 126s.
- Behavioural critic (14 judged): trivial 3, unresolved 6, unfair 5,
  gold 0 => T=0.7857, W=0.0.
- Score 0.30*0.9333+0.30*0.7857+0+0.15*0.7131 = 0.6227, delta -0.023
  vs best 0.6455 -> REVERT src + tests to champion.
- Reading: zero admitted clues use for-some tails, so the gate never binds
  at this seed — the ablation is uninformative rather than harmful, but
  keep-policy still refuses (no gain). For-some stays strict-only watch.
- Judge via reusable /tmp/judge15.py (resume-capable, incremental writes):
  clean 15/15, 0 errors, wall 606s.
