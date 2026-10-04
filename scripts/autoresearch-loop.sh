#!/usr/bin/env bash
# Self-driving AutoResearch loop: benchmark, test, commit, repeat.
#
# Runs the strict champion across a seed list with no wake-ups needed:
# each iteration benchmarks, appends the counts-only receipt, runs the
# fast generation test slice, and commits on green. A red slice stops
# the loop loudly instead of committing past it.
#
# Usage: SEEDS="6210 6211 6212" bash scripts/autoresearch-loop.sh
#   LABEL_PREFIX defaults to "iter-loop".
set -uo pipefail
cd "$(dirname "$0")/.."

PY="uv run --no-sync python"
SEEDS="${SEEDS:-6210 6211 6212}"
LABEL_PREFIX="${LABEL_PREFIX:-iter-loop}"
LABEL_SEQ=0

commit_receipt() {
  bash .scripts/generate-repo-map.sh >/dev/null 2>&1
  git add docs/evidence/private-clue-benchmark-v1.20261003.json docs/REPO_MAP.md
  git commit -m "Loop ${LABEL_PREFIX}: strict sweep ${SEEDS}" >/dev/null 2>&1
}

for seed in $SEEDS; do
  LABEL_SEQ=$((LABEL_SEQ + 1))
  label="${LABEL_PREFIX}-seed-${seed}"
  echo "=== ${label} ==="
  if ! CROSSWORD_STRICT_ADMISSION=1 $PY scripts/private-clue-benchmark.py \
      --label "$label" --seed "$seed" --log "/tmp/clue-benchmark-${label}.json" \
      2>&1 | grep -E '"label"|admissionRate|scaffold|draftCalls'; then
    echo "BENCHMARK FAILED at ${label}; loop stops."
    exit 1
  fi
  if ! $PY -m pytest tests/test_private_puzzle_generation.py -q 2>&1 | tail -n 1; then
    echo "TEST SLICE RED at ${label}; loop stops without committing."
    exit 1
  fi
  if ! commit_receipt; then
    echo "COMMIT FAILED at ${label}; loop stops."
    exit 1
  fi
  echo "committed ${label}: $(git log --format=%h -1)"
done

echo "LOOP DONE: ${LABEL_SEQ} iterations committed."
git log --format="%h %s" -"${LABEL_SEQ}"
