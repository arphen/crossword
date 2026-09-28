#!/usr/bin/env python3
"""Evaluate a fixed-seed native fill receipt JSON file.

The input is a JSON object with ``cases`` (one case per seed), or a bare JSON
array of cases.  This command evaluates captured receipts only; it does not
start Ollama or run native xfill by itself.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.crossword.fill_quality_evaluation import evaluate_fill_quality_study  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON object or array of fixed-seed cases")
    parser.add_argument("--out", type=Path, help="write the report to this path as well as stdout")
    parser.add_argument("--study-id", default="fixture")
    parser.add_argument("--recipe-id", default="private-local-v1")
    args = parser.parse_args()
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        cases = raw.get("cases")
        requested = raw.get("requestedSeeds")
    else:
        cases = raw
        requested = None
    if not isinstance(cases, list):
        raise SystemExit("input must contain a cases array")
    report = evaluate_fill_quality_study(
        cases,
        study_id=args.study_id,
        recipe_id=args.recipe_id,
        requested_seeds=requested,
    )
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized, encoding="utf-8")
    sys.stdout.write(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

