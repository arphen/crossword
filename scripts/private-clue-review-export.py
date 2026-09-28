#!/usr/bin/env python3
"""Export one generated private response as an answer-bearing local review bundle.

This command is deliberately offline.  It never starts Ollama, writes a user
profile, registers a puzzle, or marks a clue reviewed.  The output is for a
human/editorial or model review pass before any future admitted-pack work.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.crossword.clue_review_bundle import (  # noqa: E402
    build_clue_review_bundle,
    canonical_review_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="saved /api/future/private-puzzles JSON response")
    parser.add_argument("--out", type=Path, required=True, help="local answer-bearing review bundle path")
    args = parser.parse_args()
    try:
        response = json.loads(args.input.read_text(encoding="utf-8"))
        bundle = build_clue_review_bundle(response)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(canonical_review_json(bundle) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"bundleDigest": bundle["bundleDigest"], "entries": len(bundle["entries"]), "out": str(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
