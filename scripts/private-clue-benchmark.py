#!/usr/bin/env python3
"""Run one AutoResearch benchmark iteration over the candidate lane.

Fixed 15-answer benchmark mixing ordinary fills with known-hard shapes
(names, multiword-joined answers, affix extensions, pseudo-pun bait,
obscure entries). Drives the real ``_make_candidate_clues`` path — no
personas, no chat judges — and scores with the deterministic guards plus
admission counts. The committed receipt is counts-only; clue text stays
in the local log.

Each run is one loop iteration: vary exactly one variable between runs
(env knobs only) and compare against the champion in the receipt.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BENCHMARK_VERSION = "private-clue-benchmark-v1"

BENCHMARK_ANSWERS = [
    "ECHO", "MOSS", "DARK",
    "SEATTLE", "BRAD", "ADS",
    "MAKESNICE", "ICANTGOON", "SEAMLESS",
    "SLEEPY", "NOTI", "KREME",
    "ALTA", "AREPO", "TROUSSEAU",
]


def run_iteration(label, model, weekday, seed):
    from src.crossword import private_puzzle_generation as generation  # noqa: E402
    from src.crossword.clue_genre import observe_clue_genre  # noqa: E402
    from src.crossword.clue_witness import witness_clue_family  # noqa: E402

    entries = [
        {"id": f"{index}A", "answer": answer, "length": len(answer)}
        for index, answer in enumerate(BENCHMARK_ANSWERS)
    ]
    context = {"_candidate_base_seed": seed}
    started = time.monotonic()
    title, clues = generation._make_clues(model, entries, context, weekday)
    wall = round(time.monotonic() - started, 3)
    admitted = 0
    guard_hits = 0
    families: dict = {}
    for entry in entries:
        text = clues.get(entry["id"], "")
        if text.startswith("Entry supported by its crossings"):
            continue
        admitted += 1
        hits = [
            code
            for code in (
                generation._clue_wordplay_issue(entry, text),
                generation._clue_morphology_issue(entry, text),
                generation._clue_information_issue(entry, text, weekday=weekday),
            )
            if isinstance(code, str) and code
        ]
        flags = [
            flag
            for flag in generation._clue_risk_flags(entry, text) or []
            if flag not in {"foothold-required", "unsupported-factual-surface"}
        ]
        guard_hits += len(hits) + len(flags)
        claimed = generation._clue_family_observation(text).get("family", "definition")
        family = witness_clue_family(claimed, text, entry["answer"])["family"]
        genre = observe_clue_genre(text).get("genre")
        families[family] = families.get(family, 0) + 1
        families[f"genre:{genre}"] = families.get(f"genre:{genre}", 0) + 1
    candidate = context.get("_candidate_generation") or {}
    return {
        "label": label,
        "entries": len(entries),
        "admitted": admitted,
        "scaffold": len(entries) - admitted,
        "admissionRate": round(admitted / len(entries), 4),
        "guardHits": guard_hits,
        "families": dict(sorted(families.items())),
        "draftCalls": candidate.get("draftCalls"),
        "compareCalls": candidate.get("compareCalls"),
        "redraftSteeringRounds": len(candidate.get("redraftSteering") or []),
        "wallSeconds": wall,
    }, clues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--weekday", default="monday")
    parser.add_argument("--seed", type=int, default=6200)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--log", type=Path, default=Path("/tmp/clue-benchmark.json"))
    args = parser.parse_args()
    if args.out is None:
        args.out = (
            ROOT / "docs" / "evidence" / f"{BENCHMARK_VERSION}.{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
        )

    summary, clues = run_iteration(args.label, args.model, args.weekday, args.seed)
    summary["model"] = args.model
    summary["weekday"] = args.weekday
    summary["seed"] = args.seed

    receipt = {
        "version": BENCHMARK_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "counts-only",
        "claim": "one AutoResearch iteration: fixed 15-answer benchmark, deterministic scoring only",
        "iterations": [],
        "knownLimits": [
            "counts only; clue text stays local and is never committed",
            "quality (wit) is not scored here; blind human verdicts score it",
        ],
    }
    if args.out.is_file():
        try:
            prior = json.loads(args.out.read_text(encoding="utf-8"))
            if isinstance(prior, dict) and isinstance(prior.get("iterations"), list):
                receipt["iterations"].extend(prior["iterations"])
        except (OSError, ValueError):
            pass
    receipt["iterations"].append(summary)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text(
        json.dumps({"label": args.label, "clues": clues, "summary": summary}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out": str(args.out), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
