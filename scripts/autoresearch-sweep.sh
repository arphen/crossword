#!/usr/bin/env bash
# One AutoResearch sweep: single-variable mutations off the strict champion.
#
# Every arm is one iteration. Two arms repeat the champion config on fresh
# seeds first, because the Ollama tier sampling pins no seed (seed: None in
# _TIER_SAMPLING), so the same config does not reproduce. Those two arms are
# the noise floor: a mutation that does not clear the champion-to-champion
# spread is not a result.
set -uo pipefail
cd "$(dirname "$0")/.."

PY="uv run --no-sync python"
DAY="${DAY:-monday}"
JUDGE="${JUDGE:-gemma3:4b}"
STAMP="${STAMP:-$(date -u +%Y%m%d)}"
RESULTS="/tmp/autoresearch-${STAMP}.jsonl"
: > "$RESULTS"

run_arm() {
  local label="$1" seed="$2"; shift 2
  echo "=== ${label} (seed ${seed}) env: $* ==="
  # shellcheck disable=SC2086
  env "$@" CROSSWORD_STRICT_ADMISSION=1 $PY scripts/private-clue-benchmark.py \
      --label "$label" --seed "$seed" --weekday "$DAY" >/dev/null 2>&1
  local bench_rc=$?
  $PY scripts/clue-cold-solver.py \
      --log /tmp/clue-benchmark.json --judge "$JUDGE" \
      --out "docs/evidence/private-clue-cold-solver-v1.${STAMP}.json" \
      --verdicts-out "/tmp/verdicts-${label}.json" >/dev/null 2>&1
  local solver_rc=$?
  $PY - "$label" "$seed" "$bench_rc" "$solver_rc" "$RESULTS" "$STAMP" <<'PYTHON'
import json, sys
from pathlib import Path
label, seed, bench_rc, solver_rc, out, stamp = sys.argv[1:7]
bench = json.loads(Path("/tmp/clue-benchmark.json").read_text())["summary"]
solver_path = Path("docs/evidence") / f"private-clue-cold-solver-v1.{stamp}.json"
record = {
    "label": label,
    "seed": int(seed),
    "benchRc": int(bench_rc),
    "solverRc": int(solver_rc),
    "admitted": bench.get("admitted"),
    "scaffold": bench.get("scaffold"),
    "guardHits": bench.get("guardHits"),
    "families": bench.get("families"),
    "draftCalls": bench.get("draftCalls"),
    "wallSeconds": bench.get("wallSeconds"),
}
if solver_rc == 0 and solver_path.is_file():
    probe = json.loads(solver_path.read_text())["summary"]
    for key in ("goldRate", "trivialRate", "unfairRate", "unresolvedRate", "soundRate"):
        record[key] = probe.get(key)
    record["judged"] = probe.get("judged")
with open(out, "a") as handle:
    handle.write(json.dumps(record) + "\n")
print(json.dumps(record))
PYTHON
}

# --- noise floor: champion config, fresh seeds ---------------------------------
run_arm "arm-noise-1" 6201 CROSSWORD_REDRAFT_STEERING=1
run_arm "arm-noise-2" 6202 CROSSWORD_REDRAFT_STEERING=1

# --- single-variable mutations ------------------------------------------------
run_arm "arm-draft-rounds-6" 6200 CROSSWORD_CANDIDATE_DRAFT_ROUNDS=6
run_arm "arm-challenge-on"   6200 CROSSWORD_PRIVATE_CLUE_CHALLENGE=1
run_arm "arm-steering-off"   6200 CROSSWORD_REDRAFT_STEERING=0

echo "SWEEP DONE -> ${RESULTS}"
