#!/usr/bin/env python3
"""Cold-solver proxy: guess answers from clues like a solver would (insights).

A DIFFERENT model family than the clue writer (default gemma3:4b solves,
llama3.2:3b writes) gets the clue, the answer length, and a crossing
pattern — never the answer. Attempt 1 is a direct guess; attempt 2 adds
surface analysis with the same pattern. Results are difficulty telemetry,
never admission gates: a solver that cannot solve real Monday clues is a
broken instrument, not a strict judge.

Modes:
  calibrate  run the protocol over sampled archive pairs with known
             answers; measures whether the instrument works at all.
  solve      run the protocol over generated clues in a JSON log
             ({answer: clue}); the caller compares.

Clue text in logs stays local (/tmp). Offline apart from Ollama.
"""

from __future__ import annotations

import argparse
import glob
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARCHIVE_DEFAULT = Path.home() / "projects" / "crossword_clue_answer_examples"

PROTOCOL_VERSION = "private-cold-solver-v1"


def pattern_for(answer, revealed=(0,)):
    letters = []
    for index, char in enumerate(answer):
        letters.append(char if index in revealed else "_")
    return "".join(letters)


def reveal_indices(answer):
    return (0, len(answer) // 2)


def ask_solver(model, clue, length, pattern, attempt, timeout=120):
    if attempt == 1:
        user = (
            f"Crossword clue: {clue!r}. The answer has {length} letters. "
            'Guess the answer. Reply JSON {"guess": "<YOUR GUESS>"} only.'
        )
    else:
        user = (
            f"Crossword clue: {clue!r}. The answer has {length} letters and "
            f"fits the pattern {pattern!r} (_ is unknown). Analyze the clue "
            "surface briefly, then guess. "
            'Reply JSON {"analysis": "<one sentence>", "guess": "<YOUR GUESS>"} only.'
        )
    response = requests.post(
        "http://127.0.0.1:11434/api/chat",
        timeout=(2, timeout),
        json={
            "model": model,
            "stream": False,
            "think": False,
            "format": {"type": "object"},
            "options": {"temperature": 0.2, "num_predict": 200},
            "messages": [{"role": "user", "content": user}],
        },
    )
    response.raise_for_status()
    content = response.json()["message"]["content"]
    try:
        payload = json.loads(content)
    except (ValueError, TypeError):
        return None
    guess = payload.get("guess") if isinstance(payload, dict) else None
    if not isinstance(guess, str):
        return None
    return "".join(ch for ch in guess.upper() if ch.isalpha())


def solve_one(model, clue, length, pattern):
    first = ask_solver(model, clue, length, pattern, attempt=1)
    second = ask_solver(model, clue, length, pattern, attempt=2) if first is None else first
    return first, second


def calibrate(args) -> int:
    files = sorted(glob.glob(str(ARCHIVE_DEFAULT / "[12]*" / "*" / "*.json")))
    rng = random.Random(args.seed)
    pairs = []
    for path in files:
        if len(pairs) >= args.puzzles * 4:
            break
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if str(payload.get("dow", "")).lower() != "monday":
            continue
        answers = payload.get("answers") or {}
        clues = payload.get("clues") or {}
        for side in ("across", "down"):
            for answer, clue in zip(answers.get(side) or [], clues.get(side) or []):
                if (
                    isinstance(answer, str)
                    and isinstance(clue, str)
                    and answer.isalpha()
                    and 4 <= len(answer) <= 9
                ):
                    text = clue.strip()
                    if text and len(pairs) < args.puzzles:
                        pairs.append((answer.upper(), text))
            if len(pairs) >= args.puzzles:
                break
    rng.shuffle(pairs)
    pairs = pairs[: args.puzzles]
    results = []
    solved1 = solved2 = unparseable = 0
    started = time.monotonic()
    for answer, clue in pairs:
        pattern = pattern_for(answer, reveal_indices(answer))
        try:
            first, second = solve_one(args.solver, clue, len(answer), pattern)
        except requests.RequestException:
            first, second = None, None
        if first is None and second is None:
            unparseable += 1
        if first == answer:
            solved1 += 1
        if (second or first) == answer:
            solved2 += 1
        results.append(
            {"answer": answer, "solved1": first == answer, "solved2": (second or first) == answer}
        )
        print(f"  {answer:12s} a1={first == answer} a2={(second or first) == answer}", flush=True)
    wall = round(time.monotonic() - started, 1)
    report = {
        "version": PROTOCOL_VERSION,
        "mode": "calibrate",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "solver": args.solver,
        "puzzles": len(pairs),
        "solvedAttempt1": solved1,
        "solvedAttempt2": solved2,
        "unparseable": unparseable,
        "solveRate1": round(solved1 / len(pairs), 4) if pairs else 0.0,
        "solveRate2": round(solved2 / len(pairs), 4) if pairs else 0.0,
        "wallSeconds": wall,
        "interpretation": (
            "instrument check: real Monday clues with two crossings; "
            "a usable solver clears a majority by attempt 2"
        ),
    }
    print(json.dumps(report, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solver", default="gemma3:4b")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--puzzles", type=int, default=50)
    sub = parser.add_subparsers(dest="command", required=True)
    cal = sub.add_parser("calibrate")
    cal.set_defaults(run=calibrate)
    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
