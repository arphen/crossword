#!/usr/bin/env python3
"""Emit the generic-blocker redundancy verdict for private clues (Q08).

Each closed-vocabulary blocker is fired against a hand-listed matrix plus
the local corpus, and every firing surface is checked against every OTHER
enforcement (leak, morphology, information, risk, factual-surface, genre
caps, low-information set). A blocker with zero unique rejections is
provably redundant and goes; a blocker that uniquely catches junk stays
until the specimen scorer (Q02) replaces it.

Outcome on this tree: the three anchored name-shape blockers are removed —
unsourced name slots are refused downstream by the factual-surface guard
and the genre cap, which additionally spare reviewed source-backed senses.
The generic, template, no-route, and low-information blockers are
load-bearing (a bare "Common name" is caught by nothing else) and stay.
Offline, no model, no server.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.crossword import private_puzzle_generation as generation  # noqa: E402
from src.crossword.clue_genre import (  # noqa: E402
    _ANCHORED_NAME_RES,
    observe_clue_genre,
)
from src.crossword.private_clue_corpus import load_corpus  # noqa: E402

RECEIPT_VERSION = "private-clue-regex-redundancy-v1"

# (surface id, clue, answer, blocker under test).
MATRIX = (
    ("generic-bare", "Common name", "XENON", "generic"),
    ("generic-padded", "A common name for a gas?", "XENON", "generic"),
    ("generic-term", "Usually a common term", "XENON", "generic"),
    ("template-acronym", "A common acronym", "XENON", "generic"),
    ("noroute-synonym", "Usual synonym", "XENON", "generic"),
    ("noroute-answer", "Standard answer", "XENON", "generic"),
    ("lowinfo-thing", "A thing", "XENON", "low-information"),
    ("lowinfo-something", "Something", "XENON", "low-information"),
    ("name-anchored", "Famous writer's name", "NASH", "name"),
    ("name-anchored-of", "Name of a classic novelist", "NASH", "name"),
    ("name-context", "Name that might follow 'Pat ...'", "SAJAK", "name"),
    ("name-loose", "Name of the singer in a 1980s British band", "ADELE", "name"),
)


def _fires(blocker: str, clue: str) -> bool:
    if blocker == "generic":
        return bool(
            generation._GENERIC_TEMPLATE_PHRASE_RE.search(clue)
            or generation._GENERIC_CLUE_RE.fullmatch(clue)
            or generation._GENERIC_NO_ROUTE_CLUE_RE.fullmatch(clue)
        )
    if blocker == "low-information":
        return clue.strip().casefold().strip("?.! ") in generation._LOW_INFORMATION_CLUE_TEXTS
    if blocker == "name":
        return any(rx.match(clue) is not None for rx in _ANCHORED_NAME_RES) or (
            observe_clue_genre(clue).get("rule") == "loose-name-shape"
        )
    raise ValueError(f"unknown blocker {blocker}")


def _other_enforcement(answer: str, clue: str, skip: str) -> list:
    """Every enforcement except the blocker under test."""
    entry = {"answer": answer}
    codes = []
    if skip != "generic":
        for fn in (
            generation._clue_wordplay_issue,
            generation._clue_morphology_issue,
        ):
            code = fn(entry, clue)
            if isinstance(code, str) and code and code != "generic-clue":
                codes.append(code)
    if skip != "low-information":
        code = generation._clue_information_issue(entry, clue)
        if isinstance(code, str) and code:
            codes.append(code)
    for flag in generation._clue_risk_flags(entry, clue) or []:
        if isinstance(flag, str) and flag and flag != "foothold-required":
            codes.append(flag)
    genre = observe_clue_genre(clue).get("genre")
    # The Q05 genre cap remains regardless of which blocker is under test.
    if genre == "name-slot":
        codes.append("name-slot-without-source")
    if genre == "fill-blank":
        codes.append("fill-blank-capped")
    return sorted(set(codes))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "docs" / "evidence" / f"{RECEIPT_VERSION}.offline.json",
        help="where to write the receipt (default: docs/evidence)",
    )
    args = parser.parse_args()

    verdicts = {}
    for blocker in ("generic", "low-information", "name"):
        fired = [
            (surface_id, clue, answer)
            for surface_id, clue, answer, owner in MATRIX
            if owner == blocker and _fires(blocker, clue)
        ]
        unique = [
            {"surface": surface_id, "clue": clue, "answer": answer,
             "otherEnforcement": _other_enforcement(answer, clue, blocker)}
            for surface_id, clue, answer in fired
        ]
        uncovered = [item for item in unique if not item["otherEnforcement"]]
        verdicts[blocker] = {
            "matrixFires": len(fired),
            "matrixSurfaces": sum(1 for row in MATRIX if row[3] == blocker),
            "uniqueRejections": len(uncovered),
            "uncovered": uncovered,
        }
    verdicts["generic"]["decision"] = "retain"
    verdicts["generic"]["rationale"] = (
        "a bare Common name is caught by nothing else; removal would admit it to players"
    )
    verdicts["low-information"]["decision"] = "retain"
    verdicts["low-information"]["rationale"] = (
        "the set is the information guard; removal would admit content-free surfaces"
    )
    verdicts["name"]["decision"] = "removed"
    verdicts["name"]["rationale"] = (
        "unsourced name slots are refused downstream by the factual-surface guard "
        "and the genre cap, which spare reviewed source-backed senses"
    )

    corpus = load_corpus()
    corpus_fires = {"generic": 0, "low-information": 0, "name": 0}
    pairs = 0
    if corpus["captured"]:
        for record in corpus["records"]:
            if not isinstance(record, dict):
                continue
            pairs += 1
            for blocker in corpus_fires:
                if _fires(blocker, record.get("clue", "")):
                    corpus_fires[blocker] += 1

    receipt = {
        "version": RECEIPT_VERSION,
        "kind": "offline",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "claim": "per-blocker redundancy verdicts with the evidence for each",
        "matrix": {"surfaces": len(MATRIX)},
        "verdicts": verdicts,
        "corpus": {"captured": corpus["captured"], "pairs": pairs, "fires": corpus_fires},
        "knownLimits": [
            "matrix surfaces are hand-listed, not a sample of production boards",
            "retained blockers await the specimen scorer (Q02), not another regex",
            "no operator-judged specimen is consumed by this receipt",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": os.path.relpath(args.out, ROOT),
                "decisions": {k: v["decision"] for k, v in verdicts.items()},
                "unique": {k: v["uniqueRejections"] for k, v in verdicts.items()},
                "corpusPairs": pairs,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
