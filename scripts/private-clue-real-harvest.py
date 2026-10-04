#!/usr/bin/env python3
"""Harvest real candidate-lane clue surfaces for blind judging (Q02 round 2).

Runs the real ``_make_clues`` code path twice over one fixed entry set —
once as a single draft, once through the candidate lane — on the local
small-tier model, and saves the non-scaffold surfaces to an answer-bearing,
gitignored local file. The round-2 ledger seeds same-answer pairs from the
two arms, so the operator judges real unknowns blind: single vs candidate.

Needs a running Ollama. Offline otherwise; no profile, no server.
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

from src.crossword.private_clue_corpus import load_corpus  # noqa: E402
from src.crossword import private_puzzle_generation as generation  # noqa: E402

from src.crossword.clue_specimens import REAL_VERSION, real_path  # noqa: E402

FALLBACK_ANSWERS = [
    "CAT", "DOG", "ECHO", "MOSS", "TUNING", "STITCH", "RESONANCE", "PATTERN",
    "WEAVE", "LIGHT", "DARK", "BRIGHT", "QUIET", "NOISY", "HAPPY", "SORRY",
    "SHADY", "NICE", "LARGE", "WARM", "STRONG", "YOUNG", "BOLD", "RICH",
]


def harvest_path() -> Path:
    return real_path()


def entry_answers(size):
    """Distinct real-word answers; corpus answers are fine even though their
    corpus clues are scaffold — only the answer strings are reused."""
    corpus = load_corpus()
    answers = []
    if corpus["captured"]:
        seen = set()
        for record in corpus["records"]:
            answer = record.get("answer") if isinstance(record, dict) else None
            if isinstance(answer, str) and len(answer) >= 3 and answer not in seen:
                seen.add(answer)
                answers.append(answer)
            if len(answers) >= size:
                break
    if len(answers) < 12:
        answers = list(FALLBACK_ANSWERS[:size])
    return answers[:size]


def run_arm(model, entries, candidate: bool):
    context = {"_candidate_base_seed": 6107}
    key = "CROSSWORD_CLUE_CANDIDATES"
    previous = os.environ.get(key)
    os.environ[key] = "1" if candidate else "0"
    started = time.monotonic()
    try:
        title, clues = generation._make_clues(model, entries, context, "monday")
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous
    return clues, round(time.monotonic() - started, 3)


def is_real_surface(text) -> bool:
    return (
        isinstance(text, str)
        and bool(text.strip())
        and not text.startswith("Entry supported by its crossings")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--entries", type=int, default=24)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    target = args.out or harvest_path()

    answers = entry_answers(args.entries)
    entries = [
        {"id": f"{index}A", "answer": answer, "length": len(answer)}
        for index, answer in enumerate(answers)
    ]
    arms = {}
    for name, candidate in (("single", False), ("candidate", True)):
        print(f"[{name}] running {len(entries)} entries on {args.model}…", flush=True)
        clues, wall = run_arm(args.model, entries, candidate)
        arms[name] = {"clues": clues, "wallSeconds": wall}
        real = sum(1 for text in clues.values() if is_real_surface(text))
        print(f"[{name}] {wall}s surfaces={len(clues)} real={real}", flush=True)

    records = []
    for entry in entries:
        answer = entry["answer"]
        single = arms["single"]["clues"].get(entry["id"], "")
        cand = arms["candidate"]["clues"].get(entry["id"], "")
        for arm, text in (("single", single), ("candidate", cand)):
            if not is_real_surface(text):
                continue
            records.append(
                {
                    "answer": answer,
                    "clue": text,
                    "arm": arm,
                    "entryId": entry["id"],
                    "weekday": "monday",
                    "modelTag": args.model,
                }
            )
    payload = {
        "version": REAL_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "live-model",
        "model": args.model,
        "entryCount": len(entries),
        "records": records,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    by_arm: dict = {}
    for record in records:
        by_arm[record["arm"]] = by_arm.get(record["arm"], 0) + 1
    print(
        json.dumps(
            {"out": str(target), "realSurfaces": len(records), "byArm": by_arm},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
