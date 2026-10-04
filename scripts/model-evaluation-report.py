#!/usr/bin/env python3
"""Emit structural metrics from an existing paired local-model holdout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.crossword.model_evaluation import build_model_evaluation_report_from_bytes  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input", type=Path, help="full JSON output from the paired holdout harness"
    )
    parser.add_argument(
        "--out", type=Path, help="write the report to this path as well as stdout"
    )
    args = parser.parse_args()
    raw = args.input.read_bytes()
    report = build_model_evaluation_report_from_bytes(raw)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized, encoding="utf-8")
    sys.stdout.write(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
