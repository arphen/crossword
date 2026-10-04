#!/usr/bin/env python3
"""Build a local-only answer-to-routes index from the sibling NYT archive.

For each answer, keeps up to 4 sampled historical clues spread across
weekdays: the sense material and route shapes editors actually used.
Read-only on the archive; the index is answer-bearing and gitignored,
never committed. Draft prompts may sample it as context (never copied
verbatim into committed artifacts).

Offline.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARCHIVE_ENV = "CROSSWORD_NYT_ARCHIVE_PATH"
ARCHIVE_DEFAULT = Path.home() / "projects" / "crossword_clue_answer_examples"

INDEX_VERSION = "private-clue-routes-v1"
INDEX_ENV = "CROSSWORD_CLUE_ROUTE_INDEX_PATH"
INDEX_FILENAME = "private-clue-routes-v1.local.json"
PER_ANSWER = 4


def index_path() -> Path:
    override = os.environ.get(INDEX_ENV, "").strip()
    if override:
        return Path(override)
    return ROOT / INDEX_FILENAME


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--per-answer", type=int, default=PER_ANSWER)
    args = parser.parse_args()
    target = args.out or index_path()

    override = os.environ.get(ARCHIVE_ENV, "").strip()
    archive = Path(override) if override else ARCHIVE_DEFAULT
    files = sorted(glob.glob(str(archive / "[12]*" / "*" / "*.json")))
    if not files:
        raise SystemExit(f"no archive puzzles under {archive}")

    routes: dict = defaultdict(list)
    puzzles = 0
    started = time.monotonic()
    for path in files:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        weekday = str(payload.get("dow", "")).lower()
        answers = payload.get("answers") or {}
        clues = payload.get("clues") or {}
        puzzles += 1
        for side in ("across", "down"):
            for answer, clue in zip(answers.get(side) or [], clues.get(side) or []):
                if (
                    not isinstance(answer, str)
                    or not isinstance(clue, str)
                    or not answer.isalpha()
                    or not 3 <= len(answer) <= 15
                ):
                    continue
                key = answer.upper()
                slot = routes[key]
                if len(slot) >= args.per_answer:
                    continue
                if any(entry["weekday"] == weekday for entry in slot) and len(slot) >= 2:
                    continue
                # Strip the archive's "NN. " numbering: signifiers are
                # surfaces, and the number is not part of the clue.
                slot.append({"clue": re.sub(r"^\d+\.\s*", "", clue.strip()), "weekday": weekday})
    wall = round(time.monotonic() - started, 1)
    payload_out = {
        "version": INDEX_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "local-only",
        "puzzles": puzzles,
        "answers": len(routes),
        "routes": {answer: entries for answer, entries in sorted(routes.items())},
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload_out, ensure_ascii=False) + "\n", encoding="utf-8")
    pairs = sum(len(v) for v in routes.values())
    print(
        json.dumps(
            {
                "out": str(target),
                "puzzles": puzzles,
                "answers": len(routes),
                "routes": pairs,
                "seconds": wall,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
