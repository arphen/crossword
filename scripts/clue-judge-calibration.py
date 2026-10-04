#!/usr/bin/env python3
"""Calibrate the cold-solver judge against known-good hand-written clues.

The sweep's headline numbers come from a 4b local judge. Before those numbers
can carry a decision, the judge's failure mode has to be measured, not
assumed. This feeds the same judge fifteen clues that are factually correct by
construction -- one per frozen benchmark answer, written to the same entry set
-- and reports how often the judge still calls them unsound.

A false "unsound" here is a judge error on a fair clue, and it inflates the
unfair rate that the Champion Decision Rule gates on. The measured rate is the
discount the decision rule applies.

Offline apart from the judge calls. Counts-only receipt; clue text stays local.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RECEIPT_VERSION = "private-clue-judge-calibration-v1"

# One factually correct clue per frozen benchmark answer. Chosen to be
# unambiguously true, so any "unsound" verdict is a judge error rather than a
# clue defect. The last five are the entries the sweep judge flagged on the
# champion's own drafts, so they are the direct false-positive probe.
KNOWN_GOOD = {
    "ECHO": "Nymph whose only gift was repetition",
    "MOSS": "Green growth on the shady side of a tree",
    "DARK": "Lights-out condition",
    "SEATTLE": "Emerald City",
    "BRAD": "The Governor's brother on 'The Walking Dead'",
    "ADS": "Paid placements",
    "MAKESNICE": "Tidies up",
    "ICANTGOON": "Gym-session veto, in four words",
    "SEAMLESS": "No visible join",
    "SLEEPY": "Ready for the pillow",
    "NOTI": "Text-message shorthand for 'notification'",
    "KREME": "Half of the ice-cream chain",
    "ALTA": "Spanish for 'high'",
    "AREPO": "Enigmatic name in the Sator Square palindrome",
    "TROUSSEAU": "Newlywed's box of linens",
}


def _load_solvers():
    def _module(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    return (
        _module("private_clue_benchmark", ROOT / "scripts" / "private-clue-benchmark.py"),
        _module("clue_cold_solver", ROOT / "scripts" / "clue-cold-solver.py"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judge", default="gemma3:4b")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--verdicts-out", type=Path, default=Path("/tmp/judge-calibration-verdicts.json"))
    args = parser.parse_args()

    benchmark, solver = _load_solvers()
    answers = list(benchmark.BENCHMARK_ANSWERS)
    clues = {
        f"{index}A": KNOWN_GOOD[answer] for index, answer in enumerate(answers)
    }

    verdicts, buckets, soundness, wall = solver.probe(
        answers, clues, args.judge, args.timeout, None
    )

    judged = sum(1 for v in verdicts.values() if v.get("bucket") != "scaffold")
    false_unsound = [
        entry_id
        for entry_id, verdict in verdicts.items()
        if verdict.get("sound") == "unsound"
    ]
    precision = (
        round((judged - len(false_unsound)) / judged, 4) if judged else 0.0
    )

    summary = {
        "judge": args.judge,
        "knownGoodClues": judged,
        "judgedCorrectly": judged - len(false_unsound),
        "falseUnsound": len(false_unsound),
        "falseUnsoundRate": round(1 - precision, 4) if judged else 0.0,
        "judgeSoundnessPrecision": precision,
        "falseUnsoundIds": sorted(false_unsound),
        "buckets": buckets,
        "soundness": soundness,
        "goldRate": round(buckets.get("gold", 0) / judged, 4) if judged else 0.0,
        "trivialRate": round(buckets.get("trivial", 0) / judged, 4) if judged else 0.0,
        "unfairRate": round(buckets.get("unfair", 0) / judged, 4) if judged else 0.0,
        "wallSeconds": wall,
    }

    receipt = {
        "version": RECEIPT_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "counts-only",
        "claim": "judge false-unsound rate on fifteen factually correct clues",
        "knownLimits": [
            "these clues are correct by construction, so unsound verdicts are "
            "judge errors, not clue defects",
            "fifteen clues bound the error rate only loosely; the figure is a "
            "discount, not a precise correction factor",
        ],
        "summary": summary,
    }
    if args.out is None:
        args.out = ROOT / "docs" / "evidence" / (
            f"{RECEIPT_VERSION}.{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    args.verdicts_out.write_text(
        json.dumps({"verdicts": verdicts}, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"out": str(args.out), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
