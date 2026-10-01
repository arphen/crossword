#!/usr/bin/env python3
"""Emit the genre census for private clue surfaces (Q05).

The closed taxonomy — name-slot, role-plus-name, common-term, x-e-g,
fill-blank, quotational, sound-or-action-cue, abbreviation,
plain-definition — is measured per board before it is enforced. The surface
matrix below is hand-listed English, not computed from the rule under test.
The local answer-bearing corpus is censused when one exists on this host;
only counts and rates are committed, never clue text.

If the census cannot reproduce the complaint that name clues are still too
common, the taxonomy is wrong and that is the finding.
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

from src.crossword.clue_genre import (  # noqa: E402
    GENRE_VERSION,
    GENRES,
    census_genres,
    observe_clue_genre,
)
from src.crossword.private_clue_corpus import load_corpus  # noqa: E402

RECEIPT_VERSION = "private-clue-genre-census-v1"

# (surface id, clue, expected genre). Hand-listed, including the loose
# name shapes the anchored generic-template guards admit whole.
CENSUS_SURFACES = (
    ("name-anchored", "Famous singer's name", "name-slot"),
    ("name-loose-band", "Name of the singer in a 1980s British band", "name-slot"),
    ("name-loose-famous", "The name of a famous singer from the 1980s", "name-slot"),
    ("name-not-name-shape", "Singer's first big hit", "plain-definition"),
    ("role-plus-name", "Beatles drummer Ringo Starr", "role-plus-name"),
    ("role-plus-orwell", "Novelist Orwell's bleak future", "role-plus-name"),
    ("common-bare", "Common name", "common-term"),
    ("common-padded", "A common name for a gas", "common-term"),
    ("common-synonym", "Usual synonym", "common-term"),
    ("common-lowinfo", "A thing", "common-term"),
    ("xeg-emu", "Bird, e.g.", "x-e-g"),
    ("fill-voyage", "___ voyage", "fill-blank"),
    ("fill-forth", "And so ...", "fill-blank"),
    ("quote-bare", '"Hello"', "quotational"),
    ("sound-bracket", "[Loud sound]", "sound-or-action-cue"),
    ("sound-word", "A sudden loud noise", "sound-or-action-cue"),
    ("abbr-briefly", "Doctor, briefly", "abbreviation"),
    ("plain-dark", "Without light", "plain-definition"),
    ("plain-german", "Yes in German", "plain-definition"),
)


def audit_matrix():
    disagreements = []
    for surface_id, clue, expected in CENSUS_SURFACES:
        observed = observe_clue_genre(clue)["genre"]
        if observed != expected:
            disagreements.append(
                {"surface": surface_id, "clue": clue, "observed": observed, "expected": expected}
            )
    return disagreements


def audit_corpus():
    """Census the local corpus; counts and rates only, never clue text."""
    corpus = load_corpus()
    records = corpus["records"] if corpus["captured"] else []
    census = census_genres(records)
    anchored = 0
    loose = 0
    if corpus["captured"]:
        for record in records:
            if not isinstance(record, dict):
                continue
            verdict = observe_clue_genre(record.get("clue", ""))
            if verdict["genre"] == "name-slot":
                if verdict.get("rule") == "anchored-name-guard":
                    anchored += 1
                else:
                    loose += 1
    census["nameSlotAnchored"] = anchored
    census["nameSlotLoose"] = loose
    census["captured"] = corpus["captured"]
    return census


def receipt_body():
    disagreements = audit_matrix()
    corpus = audit_corpus()
    return {
        "version": RECEIPT_VERSION,
        "kind": "offline",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "claim": (
            "the closed genre taxonomy is measured per board before it is "
            "enforced; the loose-vs-anchored name split names the rate the "
            "anchored guards miss"
        ),
        "taxonomy": list(GENRES),
        "matrix": {
            "surfaces": len(CENSUS_SURFACES),
            "expectationsSource": "hand-listed English, not the rule under test",
            "disagreements": disagreements,
        },
        "corpus": corpus,
        "knownLimits": [
            "name-shape detection is closed-vocabulary plus role heuristics, not a semantic judge",
            "role-plus-name needs a capitalized name past the first word; lowercase names read as plain definitions",
            "sound-or-action-cue covers bracket spans plus a closed cue-word list",
            "no operator-judged specimen is consumed by this receipt",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "docs" / "evidence" / f"{RECEIPT_VERSION}.offline.json",
        help="where to write the receipt (default: docs/evidence)",
    )
    args = parser.parse_args()

    receipt = receipt_body()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": os.path.relpath(args.out, ROOT),
                "surfaces": receipt["matrix"]["surfaces"],
                "disagreements": len(receipt["matrix"]["disagreements"]),
                "corpusPairs": receipt["corpus"]["pairs"],
                "nameSlotRate": receipt["corpus"]["nameSlotRate"],
                "nameSlotLoose": receipt["corpus"]["nameSlotLoose"],
                "fillBlankRate": receipt["corpus"]["fillBlankRate"],
            },
            indent=2,
        )
    )
    return 1 if receipt["matrix"]["disagreements"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
