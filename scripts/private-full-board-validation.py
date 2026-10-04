#!/usr/bin/env python3
"""Validate full-board clue generation per clue arm (salvage follow-up).

Runs the real production ``_generate`` end to end (grid fill plus clues)
once per clue arm on the local small-tier model: the legacy single draft
with salvage against the candidate lane. Reports scaffold vs real counts,
salvage receipts, and wall time. The committed receipt is counts-only;
clue text stays in the local log and the operator corpus capture that
``_generate`` already performs.

Needs the construction runtime, a running Ollama, and the sibling
generator checkout. Offline otherwise; no profile, no server.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Scratch database for puzzle registration; never the operator's instance DB.
os.environ.setdefault(
    "CROSSWORD_DATABASE_URI", "sqlite:////tmp/full-board-validation.sqlite"
)

from src.crossword import private_puzzle_generation as generation  # noqa: E402

RECEIPT_VERSION = "private-full-board-validation-v1"
SCAFFOLD_PREFIX = "Entry supported by its crossings"


def summarize_board(puzzle, manifest, provenance):
    entries = []
    clues = {}
    if isinstance(puzzle, dict):
        grid = (puzzle.get("grid", {}) or {}) if isinstance(puzzle, dict) else {}
        for entry in grid.get("entries", []) or []:
            if isinstance(entry, dict):
                entries.append(entry)
        for key in ("clues", "clueMap", "clueTexts"):
            section = puzzle.get(key)
            if isinstance(section, dict) and section:
                clues = section
                break
        if not clues:
            for key in ("across", "down"):
                section = puzzle.get(key) or {}
                if isinstance(section, dict):
                    for num, text in section.items():
                        clues[str(num)] = text
    else:
        for entry in getattr(puzzle, "entries", []) or []:
            answer = getattr(entry, "answer_text", None)
            text = getattr(entry, "clue_text", None)
            number = getattr(entry, "clue_number", None)
            direction = getattr(entry, "direction", None)
            if not isinstance(answer, str) or not isinstance(text, str):
                continue
            entries.append(entry)
            clues[f"{number}{str(direction)[:1].upper()}"] = text
    scaffold = sum(1 for text in clues.values() if str(text).startswith(SCAFFOLD_PREFIX))
    return {
        "entries": len(entries),
        "clues": len(clues),
        "scaffold": scaffold,
        "real": len(clues) - scaffold,
    }


def run_board(seed, weekday, model, candidate: bool):
    key = "CROSSWORD_CLUE_CANDIDATES"
    previous = os.environ.get(key)
    os.environ[key] = "1" if candidate else "0"
    starting = SimpleNamespace(profile={"associations": []}, draft={})
    episteme = SimpleNamespace(profile_json={"projection": {}})
    started = time.monotonic()
    try:
        from src.crossword.app import app  # noqa: E402

        with app.app_context():
            puzzle, manifest, provenance = generation._generate(
                seed, weekday, starting, episteme, model_override=model
            )
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous
    wall = round(time.monotonic() - started, 3)
    summary = summarize_board(puzzle, manifest, provenance)
    clue_context = ((provenance or {}).get("clueContext", {}) if isinstance(provenance, dict) else {})
    summary.update(
        {
            "wallSeconds": wall,
            "salvage": clue_context.get("_clue_generation_salvage"),
            "generationFallback": clue_context.get("_clue_generation_fallback"),
            "candidateCalls": (clue_context.get("_candidate_generation") or {}).get("draftCalls"),
        }
    )
    return summary, puzzle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=6110)
    parser.add_argument("--weekday", default="monday")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--arms", default="single,candidate")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--log", type=Path, default=Path("/tmp/full-board-validation.json"))
    args = parser.parse_args()
    if args.out is None:
        args.out = (
            ROOT
            / "docs"
            / "evidence"
            / f"{RECEIPT_VERSION}.{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
        )

    arms = {}
    full_log: dict = {}
    for name in [part.strip() for part in args.arms.split(",") if part.strip()]:
        candidate = name != "single"
        print(f"[{name}] full {args.weekday} board, seed {args.seed}, {args.model}…", flush=True)
        summary, puzzle = run_board(args.seed, weekday=args.weekday, model=args.model, candidate=candidate)
        arms[name] = summary
        full_log[name] = {
            "summary": summary,
            "puzzle": puzzle if isinstance(puzzle, dict) else str(type(puzzle)),
        }
        print(
            f"[{name}] {summary['wallSeconds']}s entries={summary['entries']} "
            f"real={summary['real']} scaffold={summary['scaffold']}",
            flush=True,
        )
    receipt = {
        "version": RECEIPT_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "live-model",
        "claim": "full production boards per clue arm: scaffold vs real counts only",
        "runs": [],
        "knownLimits": [
            "counts only; clue text stays local and is never committed",
            "single-arm variance is across runs (temperature 0.65, one shot each)",
            "boards also enter the operator corpus via the production capture",
        ],
    }
    if args.out.is_file():
        try:
            prior = json.loads(args.out.read_text(encoding="utf-8"))
            if isinstance(prior, dict):
                if isinstance(prior.get("runs"), list):
                    receipt["runs"].extend(prior["runs"])
                else:
                    # Migrate the original single-run receipt shape.
                    receipt["runs"].append(
                        {
                            "seed": prior.get("seed"),
                            "weekday": prior.get("weekday"),
                            "model": prior.get("model"),
                            "generatedAt": prior.get("generatedAt"),
                            "arms": prior.get("arms", {}),
                        }
                    )
        except (OSError, ValueError):
            pass
    receipt["runs"].append(
        {
            "seed": args.seed,
            "weekday": args.weekday,
            "model": args.model,
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "arms": arms,
        }
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text(json.dumps(full_log, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "arms": arms}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
