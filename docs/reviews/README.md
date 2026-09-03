# Review docs

Drop-in reviews from review agents (and the owner) land in this folder as
markdown files. Naming: `TOPIC_REVIEW.md` (or a date prefix for one-off
notes).

## Contract

1. **Reviewer** drops a doc here (committed to v2 is ideal; a raw file also
   works) with concrete findings, severity (P1/P2), and — for each finding —
   acceptance criteria or a reproduction.
2. **Implementing agents** review new docs at the start of their next work
   session, triage ownership (UI / generation / content / tests), and act:
   fix, or write a reasoned objection in the doc itself.
3. Findings are never edited or deleted by implementing agents. Responses and
   closure go into the doc's evidence log (or a `Status update` section,
   append-only) with the commit hash and the exact verification command or
   journey.
4. Anything marked **VERIFY** in a review is treated as not passed until the
   evidence is recorded here.

## Processed so far

- `UI_AND_INTERACTION_REVIEW.md` — pass 1 addressed 2026-09-03 (see its
  Status update section; remaining open items listed there).
- `GENERATION_AND_TESTING_REVIEW.md` — generation items belong to the
  generation agent; the two apps/web items (content-scan FAIL, rebus harness
  noop) were addressed in the same pass.
