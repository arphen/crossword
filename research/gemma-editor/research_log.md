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

## Iter4 — CROSSWORD_PLAIN_DEF_CAP ablation (REVERT, guard fail, no judge)
- Change: `CROSSWORD_PLAIN_DEF_CAP=1` extends the Q05 over-cap scaffold
  pattern to plain-definition (keep first half in entry order, scaffold
  the rest as `plain-definition-over-cap`; reviewed-exact exempt).
  Unit test drives `_enforce_private_clue_safety` directly: cap off keeps
  all 4 synthetic plain surfaces; cap on keeps the first 2 and scaffolds
  the last 2 with the reason code.
- Generation seed 6200 strict: admitted 7/15, guardHits 0, A=0.4667,
  families definition 7 (plain genre 6 + sound-cue 1), draftCalls 6,
  gen wall 116s. Cap binds as designed (6 plain admitted <= cap 7).
- Guard floor is admitted>=13/15: 7/15 fails -> keep impossible, judge
  skipped (no T/W/D computed) -> REVERT src + tests to champion.
- Reading: plain definition is the bulk surface (13/14 in replicates), so
  any binding cap costs ~7 admission. Genre variety must come from
  drafting livelier surfaces (k-draft rounds), not from scaffolding plain
  ones. Log /tmp/iter4-gen-log.json (clue text stays in /tmp).

## Iter5 — k-draft breadth env-only probe (REVERT, nothing in tree)
- Change: none in src (rounds already env-wired at ~:5610-5630). Measured
  with `CROSSWORD_CANDIDATE_DRAFT_ROUNDS=6 CROSSWORD_CANDIDATE_REDRAFT_ROUNDS=2`
  (champion defaults 4/1). A code attempt raising the llama3.2:3b tier
  defaults was tried first and abandoned: 3 champion-pinned redraft tests
  assert the 4/1 schedule, so the default change ships only on a keep.
- Generation seed 6200 strict: admitted 15/15, guardHits 0, draftCalls 9,
  compareCalls 12, families definition 13 + factual-relation 2
  (plain-definition genre 13), gen wall 85s. Full admission at 6 rounds.
- Behavioural critic (15 judged, no scaffolds): trivial 3, unresolved 6,
  unfair 6, gold 0 => T=0.8, W=0.0. D=0.5013 (factual 2/15 overshoots
  the Monday 0.00866 share).
- Score 0.30*1.0+0.30*0.8+0+0.15*0.5013 = 0.6152, delta -0.030 vs best
  0.6455, below keep 0.6655 -> REVERT (env-only; src+tests untouched,
  champion tree intact).
- Loop-level reading (iters 2-5 + sibling 3r): W=0 in all five judged
  verdicts (0 gold over 71 non-scaffold entries) while unfair absorbs the
  misses (5,5,5,7,6). Either the 4b blind judge's gold bar (solve-attempt-2
  or fair+aha) is unreachable for 3b drafts, or small-model wit genuinely
  never lands misdirection-with-recovery. Next loop should calibrate the
  gold instrument first (known-witty control clues must score gold) before
  further draft-lane mutations. Best stays 0.6455 (baseline seed 6200).

## Iter4r — CROSSWORD_ROUTE_DIVERGE (KEEP, 0.6818, TARGET MET)
- Change: none in src (env-only on committed code): ROUTE_CONTEXT=1 +
  ROUTE_DIVERGE=1 — divergent route collision in prompt, verbatim copies
  blocked as duplicate-drafts, regenerate via normal redraft.
- Seed 6200 strict: 15/15 admitted, guardHits 0, draftCalls 4 (fewest yet),
  A=1.0 T=0.9333 W=0.0 D=0.6785 -> score 0.6818 vs bar 0.6655 -> KEEP.
- Paced probe /tmp/iter4-probe.py: trivial 1, unresolved 6, unfair 8,
  2 judge-500 artifacts (9A reveal, 10A attempt2) individually retried to
  unfair/unresolved, 0 errors remaining. Only 1 trivial in 15.
- Noise seeds: 6201 15/15 draftCalls 6; 6202 15/15 draftCalls 4 with a
  witnessed pun + fill-blank — full admission on all 3 seeds, guardHits 0.
- TARGET (score>=0.68 with admitted>=13) MET: 0.6818 with 15/15. Loop stops
  per mission; my planned iter5 (draft depth) skipped.
- Honest caveat: W=0.0 again, unfair 8/15 (worst fairness yet). The critic
  gain is A+T (admit everything, rarely trivial), not gold. Do not mistake
  for harder-but-fair; the gold-instrument fix the sibling log calls for
  stays the priority.

## Gold-recalibration — clue-cold-solver elicitation fix (KEEP, 8/10)
- Change: `scripts/clue-cold-solver.py` — attempt-2 must give a different
  entry (temp 0.2->0.7); reveal judges fair-path generously (hindsight
  counts, unsure kept separate) and aha as makes-sense-in-hindsight
  (temp 0.0->0.2); classify gold on second-solve OR fair (aha no longer
  required), unsure->unresolved.
- Recalibration probe, 10 known-witty controls (`gemma3:4b`, 8s pacing,
  90s timeouts, 2 retries, per-entry error isolation): pre-fix baseline
  0 gold (7 unfair, 3 unresolved) -> post-fix 7 gold, 1 unfair, 2 errors
  (judge-500 artifacts, same flake class as iter4r). Individual retry of
  the 2 error controls: 1 -> gold, 1 -> error again (judge 500s) =>
  final 8 gold, 1 unfair, 1 error. Criterion gold>=2/10 MET.
- Solver tests green (22 passed: solve_replay + clue_quality_evaluation +
  reference_solver); ruff clean. Logs: /tmp/gold-recalibration-buckets.json
  (clue text local-only, never stored).
- Honest caveat: gold is now carried by generous fair-path alone (aha 0/8,
  sound unsound 9/9 judged) — the instrument detects candidate wit but
  still cannot separate fair-witty from stretched. METRIC-V2 NOTE: W
  0.10->0.25 restoration is now due (per METRIC_V2.md s2: known-witty
  controls score gold) with target rescale; promotion stays a main-agent
  decision.

## Q01 — answer-stem gate (KEEP, 14/15 admitted, guardHits 0)
- Change: `_derivational_stem_set` + `_clue_answer_stem_issue` in
  `private_puzzle_generation._clue_wordplay_issue` (Q01 chain, no judging):
  suffix strip NESS/MENT/TION/LESS/FUL/IVE/LY/AL/EST/ER/ED/ING/ES/S
  (remainder>=3, bare S skips SS), IER/IEST->Y, trailing I->Y, prefix
  strip UN-/DIS-/MIS-/IM-/IN-/NON-/RE- (len>=7, remainder>=5); full-token
  guard + len>=4 keeps short-word controls legal. New reasons
  `answer-stem-in-clue` / `tautological-comparative`.
- Unit tests: 40 leak pairs rejected with the new reasons, 40 controls
  stay legal (81 Q01 cases incl. the WOES/Misfortunes PMID check); full
  file 263 passed, ruff clean.
- Generation seed 6200 strict (`llama3.2:3b`, Monday): admitted 14/15,
  guardHits 0, draftCalls 6, compareCalls 10, families definition 13 +
  factual-relation 1 (plain-definition genre 12/14), gen wall 404s.
  Criterion admitted>=13/15 with guardHits==0 MET -> KEEP.
- Honest caveat: plain-definition still dominates (12/14 admitted); the
  gate binds only on derivation leaks, so variety still depends on
  drafting livelier surfaces. Logs: /tmp/q01-benchmark-out.json,
  /tmp/q01-seed6200-log.json (clue text stays in /tmp, never committed).