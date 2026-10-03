#!/usr/bin/env python3
"""Census our deterministic guards over the sibling NYT archive (insights).

Reads the local-only ``crossword_clue_answer_examples`` checkout (read-only,
never modified, never copied into this repo) and runs this repo's own clue
guards over every real clue/answer pair: leak/wordplay, morphology,
information, surface issues, genre, and witnessed family, aggregated by
weekday. Real published clues are overwhelmingly fair, so every guard hit
is either a genuine editorial slip or — more usefully — a detector
false positive to fix.

Output is counts-only plus sampled local-only mismatch ids for inspection.
No clue text is committed; answer-bearing samples go to /tmp. Offline.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARCHIVE_ENV = "CROSSWORD_NYT_ARCHIVE_PATH"
ARCHIVE_DEFAULT = Path.home() / "projects" / "crossword_clue_answer_examples"

RECEIPT_VERSION = "private-clue-nyt-census-v1"
MAX_LOCAL_SAMPLES = 25

WEEKDAYS = {
    "monday": "monday",
    "tuesday": "tuesday",
    "wednesday": "wednesday",
    "thursday": "thursday",
    "friday": "friday",
    "saturday": "saturday",
    "sunday": "sunday",
}


def archive_path() -> Path:
    override = os.environ.get(ARCHIVE_ENV, "").strip()
    return Path(override) if override else ARCHIVE_DEFAULT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="max puzzles (0 = all)")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--samples-out", type=Path, default=Path("/tmp/nyt-census-samples.json"))
    args = parser.parse_args()

    from src.crossword import private_puzzle_generation as generation  # noqa: E402
    from src.crossword.clue_genre import observe_clue_genre  # noqa: E402
    from src.crossword.clue_witness import witness_clue_family  # noqa: E402

    files = sorted(glob.glob(str(archive_path() / "[12]*" / "*" / "*.json")))
    if args.limit:
        files = files[: args.limit]
    if not files:
        raise SystemExit(f"no archive puzzles under {archive_path()}")

    per_weekday: dict = {}
    puzzles = 0
    pairs = 0
    started = time.monotonic()
    samples: dict = {}

    def bucket(weekday):
        return per_weekday.setdefault(
            weekday,
            {
                "puzzles": 0,
                "pairs": 0,
                "family": Counter(),
                "genre": Counter(),
                "guardHits": Counter(),
            },
        )

    for path in files:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        weekday = WEEKDAYS.get(str(payload.get("dow", "")).lower())
        if weekday is None:
            continue
        answers = payload.get("answers") or {}
        clues = payload.get("clues") or {}
        stat = bucket(weekday)
        stat["puzzles"] += 1
        puzzles += 1
        for side in ("across", "down"):
            for number, (answer, clue) in enumerate(
                zip(answers.get(side) or [], clues.get(side) or [])
            ):
                if not answer or not clue:
                    continue
                entry = {"answer": answer, "length": len(answer)}
                # Strip the archive's "NN. " numbering: guards read surfaces,
                # and a leading number would fake bracket/quote imbalances.
                text = re.sub(r"^\d+\.\s*", "", str(clue))
                if not text:
                    continue
                pairs += 1
                stat["pairs"] += 1
                claimed = generation._clue_family_observation(text).get("family", "definition")
                witnessed = witness_clue_family(claimed, text, answer)["family"]
                stat["family"][witnessed] += 1
                stat["genre"][observe_clue_genre(text).get("genre")] += 1
                hits = [
                    code
                    for code in (
                        generation._clue_wordplay_issue(entry, text),
                        generation._clue_morphology_issue(entry, text),
                        generation._clue_information_issue(entry, text, weekday=weekday),
                    )
                    if isinstance(code, str) and code
                ]
                for flag in generation._clue_surface_issues(text):
                    hits.append(f"surface:{flag}")
                if generation._hedged_definition(text):
                    hits.append("hedged-definition")
                answer = entry.get("answer") if isinstance(entry, dict) else None
                if generation._gerund_agreement_issue(answer, text) is not None:
                    hits.append("gerund-without-gerund")
                for flag in generation._clue_risk_flags(entry, text) or []:
                    if flag not in {"foothold-required", "unsupported-factual-surface"}:
                        hits.append(f"risk:{flag}")
                for hit in set(hits):
                    stat["guardHits"][hit] += 1
                    key = f"{weekday}:{hit}"
                    slot = samples.setdefault(key, [])
                    if len(slot) < MAX_LOCAL_SAMPLES:
                        slot.append({"answer": answer, "clue": text})

    receipt = {
        "version": RECEIPT_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "counts-only",
        "archive": {"files": len(files), "puzzles": puzzles, "pairs": pairs},
        "claim": (
            "this repo's deterministic guards run over the sibling NYT archive; "
            "hit rates by weekday calibrate false positives, family/genre mixes "
            "set measured drafting targets"
        ),
        "weekdays": {
            day: {
                "puzzles": stat["puzzles"],
                "pairs": stat["pairs"],
                "family": dict(sorted(stat["family"].items())),
                "genre": dict(sorted(stat["genre"].items())),
                "guardHits": dict(sorted(stat["guardHits"].items())),
            }
            for day, stat in sorted(per_weekday.items())
        },
        "knownLimits": [
            "archive coverage ends ~2018 with known gaps; style drift since is unmeasured",
            "guard hits are detector disagreements with editors, not verdicts",
            "no clue text committed; samples are local-only",
        ],
    }
    out = args.out or (
        ROOT / "docs" / "evidence" / f"{RECEIPT_VERSION}.{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    args.samples_out.parent.mkdir(parents=True, exist_ok=True)
    args.samples_out.write_text(
        json.dumps({"generatedAt": receipt["generatedAt"], "samples": samples}, indent=2) + "\n",
        encoding="utf-8",
    )
    elapsed = round(time.monotonic() - started, 1)
    total_hits = sum(sum(s["guardHits"].values()) for s in receipt["weekdays"].values())
    print(
        json.dumps(
            {
                "out": str(out),
                "puzzles": puzzles,
                "pairs": pairs,
                "seconds": elapsed,
                "guardHitCells": total_hits,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
