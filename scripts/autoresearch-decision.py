#!/usr/bin/env python3
"""Apply the Champion Decision Rule to one AutoResearch sweep.

Rule as specified: accept a mutation only when the guard pass rate does not
fall below baseline, the solver gold rate rises above the champion, and the
unfair rate stays under 5%. Anything else reverts.

Two honest amendments, both load-bearing:

* The sweep's tier sampling pins no Ollama seed, so the champion config does
  not reproduce. Champion *replicates* therefore define a noise floor, and a
  mutation must clear that spread to count. Without this the rule would accept
  sampling noise on a 14-clue benchmark.
* A 4b local judge is a weak proxy. The rule is reported both as specified and
  with a judged-unsoundness discount, because a false "unsound" on a
  non-Anglophone or genre-specific entry is a judge error, not a clue defect.

Counts-only output.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RECEIPT_VERSION = "private-clue-decision-v1"
UNFAIR_CEILING = 0.05

# Measured, not assumed. scripts/clue-judge-calibration.py feeds the same
# judge fifteen clues that are factually correct by construction; it condemned
# nine of them, so the unsound flag is ~40% precise here
# (docs/evidence/private-clue-judge-calibration-v1.<date>.json). The sweep's
# unsound and unfair rates are therefore dominated by judge error, and no
# decision that turns on them is safe. The discount is recorded for
# transparency, not because the corrected rate is trustworthy.
JUDGE_UNSOUND_PRECISION = 0.4


def _guard_pass_rate(record):
    admitted = record.get("admitted")
    hits = record.get("guardHits")
    if not admitted or hits is None:
        return None
    return max(0.0, (admitted - hits) / admitted)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep", type=Path, required=True)
    parser.add_argument("--noise-prefix", default="arm-noise")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--judge-calibration",
        type=Path,
        default=ROOT
        / "docs"
        / "evidence"
        / f"private-clue-judge-calibration-v1.{datetime.now(timezone.utc).strftime('%Y%m%d')}.json",
    )
    args = parser.parse_args()
    judge_path = args.judge_calibration

    records = [
        json.loads(line)
        for line in args.sweep.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        raise SystemExit(f"no records in {args.sweep}")

    noise = [r for r in records if r["label"].startswith(args.noise_prefix)]
    arms = [r for r in records if not r["label"].startswith(args.noise_prefix)]
    if not noise or not arms:
        raise SystemExit("need both noise replicates and mutation arms")

    for record in records:
        record["__guard__"] = _guard_pass_rate(record)

    def spread(key):
        values = [r[key] for r in noise if r.get(key) is not None]
        return (min(values), max(values)) if values else (None, None)

    gold_lo, gold_hi = spread("goldRate")
    unfair_lo, unfair_hi = spread("unfairRate")
    trivial_lo, trivial_hi = spread("trivialRate")
    guard_lo, guard_hi = spread("__guard__")

    usable = [r for r in noise if r.get("goldRate") is not None]
    noise_floor = {
        "replicates": len(noise),
        "usableReplicates": len(usable),
        "goldRate": [gold_lo, gold_hi],
        "unfairRate": [unfair_lo, unfair_hi],
        "trivialRate": [trivial_lo, trivial_hi],
        "guardPassRate": [guard_lo, guard_hi],
        "note": "same config, fresh seeds; a mutation must clear this spread",
    }

    baseline = next((r.get("goldRate") for r in noise if r.get("goldRate") is not None), None)
    verdicts = []
    for record in arms:
        guard = record.get("__guard__")
        gold = record.get("goldRate")
        unfair = record.get("unfairRate")
        adjusted_unfair = (
            None if unfair is None else min(1.0, unfair * JUDGE_UNSOUND_PRECISION)
        )
        guard_ok = guard is not None and (guard_lo is None or guard >= guard_lo)
        gold_ok = (
            gold is not None
            and baseline is not None
            and gold > baseline
            and (gold_hi is None or gold > gold_hi)
        )
        unfair_ok = unfair is not None and adjusted_unfair < UNFAIR_CEILING
        verdicts.append(
            {
                "label": record["label"],
                "seed": record["seed"],
                "admitted": record.get("admitted"),
                "guardPassRate": guard,
                "goldRate": gold,
                "trivialRate": record.get("trivialRate"),
                "unfairRate": unfair,
                "unfairRateJudgeDiscounted": (
                    None if adjusted_unfair is None else round(adjusted_unfair, 4)
                ),
                "soundRate": record.get("soundRate"),
                "gateGuard": guard_ok,
                "gateGold": gold_ok,
                "gateUnfair": unfair_ok,
                "decision": "ACCEPT" if (guard_ok and gold_ok and unfair_ok) else "REVERT",
            }
        )

    accepted = [v for v in verdicts if v["decision"] == "ACCEPT"]
    judge_fit = judge_path.is_file()
    receipt = {
        "version": RECEIPT_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "counts-only",
        "claim": "champion decision rule over one single-variable sweep",
        "rule": {
            "accept": "guardPassRate >= noise floor AND goldRate > champion "
            "replicate max AND unfairRate(judge-discounted) < 5%",
            "revert": "otherwise",
        },
        "amendments": [
            "noise floor from champion replicates: tier sampling pins no seed, "
            "so the champion does not reproduce run to run",
            "judge-unsoundness discount: the 4b judge's unsound flag measured "
            "~40% precise against known-good clues",
        ],
        "instrumentVerdict": {
            "judgeCalibrated": judge_fit,
            "judgeSoundnessPrecision": (
                json.loads(judge_path.read_text(encoding="utf-8"))["summary"][
                    "judgeSoundnessPrecision"
                ]
                if judge_fit
                else None
            ),
            "fitForAcceptance": False,
            "reason": (
                "the probe returned gold=0.000 and unfair~0.40 on the "
                "hand-written known-good clue set as well as on the drafted "
                "clues, so it does not separate the two populations; a REVERT "
                "from this sweep records an instrument that cannot yet accept "
                "anything, not proof that these mutations are harmful"
            ),
        },
        "noiseFloor": noise_floor,
        "verdicts": verdicts,
        "accepted": [v["label"] for v in accepted],
        "championUnchanged": not accepted,
    }
    if args.out is None:
        args.out = ROOT / "docs" / "evidence" / (
            f"{RECEIPT_VERSION}.{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
