#!/usr/bin/env python3
"""Compare two fixed-seed private fill-study reports.

The command pairs measured selected attempts by seed and reports native xfill
deltas. It never interprets those deltas as human solve quality.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.crossword.fill_quality_evaluation import compare_fill_quality_studies  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path, help="left/policy study report")
    parser.add_argument("right", type=Path, help="right/baseline study report")
    parser.add_argument("--left-label", default="policy")
    parser.add_argument("--right-label", default="baseline")
    parser.add_argument("--expected-seed", action="append", type=int, dest="expected_seeds")
    parser.add_argument("--out", type=Path, help="write the report to this path as well as stdout")
    args = parser.parse_args()
    left = json.loads(args.left.read_text(encoding="utf-8"))
    right = json.loads(args.right.read_text(encoding="utf-8"))
    report = compare_fill_quality_studies(
        left,
        right,
        left_label=args.left_label,
        right_label=args.right_label,
        expected_seeds=args.expected_seeds,
    )
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized, encoding="utf-8")
    sys.stdout.write(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

