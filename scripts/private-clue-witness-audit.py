#!/usr/bin/env python3
"""Emit the witness-based family audit for private clue generation.

A claimed family comes from visible punctuation; a witnessed family needs the
witness the family requires (a ledger pivot for puns, a marked blank, a
quoted utterance plus its label, a bracket span, an abbreviation indicator, a
language indicator). A trailing ``?`` alone yields ``pseudo-pun``, never
``pun``. The receipt reports claimed and witnessed counts side by side; the
gap is reported, never reconciled by assumption.

The surface matrix below is hand-listed English, not computed from the rule
under test, so a change in the rule shows up as a disagreement. The local
answer-bearing corpus is re-scored when one exists on this host; the current
corpus is empty and the receipt says so instead of inventing a denominator.
Offline, no model, no server.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.crossword.clue_witness import (  # noqa: E402
    WITNESS_VERSION,
    witness_clue_family,
    witness_hidden_word_span,
)
from src.crossword.private_clue_corpus import load_corpus  # noqa: E402
from src.crossword.private_puzzle_generation import (  # noqa: E402
    _clue_family_observation,
)

RECEIPT_VERSION = "private-clue-witness-audit-v1"

# (surface id, clue, answer, expected claimed family, expected witnessed family).
# Hand-listed from ordinary English, including the pivot ledger the witness
# rule is expected to consult.
AUDIT_SURFACES = (
    ("pun-auctioneer", "One with a lot to say?", "AUCTIONEER", "pun", "pun"),
    ("pun-teller", "Branch specialist?", "TELLER", "pun", "pun"),
    ("pun-coil", "Spring forward?", "COIL", "pun", "pun"),
    ("pun-case", "Branch SPECIALIST?", "TELLER", "pun", "pun"),
    ("pseudo-shady", "Suspicious character?", "SHADIER", "pun", "pseudo-pun"),
    ("pseudo-den", "A quiet room?", "DEN", "pun", "pseudo-pun"),
    ("pseudo-answer-is-pivot", "A sale item, reportedly?", "LOT", "pun", "pseudo-pun"),
    ("pseudo-tautology", "More shady?", "SHADIER", "pun", "pseudo-pun"),
    ("fill-voyage", "___ voyage", "BON", "fill-blank", "fill-blank"),
    ("fill-forth", "And so ...", "FORTH", "fill-blank", "fill-blank"),
    ("spoken-labeled", '"Hello there" (Spoken equivalent)', "GREETING", "spoken-equivalent", "spoken-equivalent"),
    ("spoken-unlabeled", '"To be or not to be"', "HAMLET", "spoken-equivalent", "definition"),
    ("nonverbal-rustle", "[Sound heard nearby]", "RUSTLE", "nonverbal-expression", "nonverbal-expression"),
    ("metalinguistic-dr", "Doctor, briefly", "DR", "metalinguistic", "metalinguistic"),
    ("factual-german", "Yes in German", "JA", "factual-relation", "factual-relation"),
    ("definition-shady", "Suspicious-looking", "SHADY", "definition", "definition"),
    ("definition-dark", "Without light", "DARK", "definition", "definition"),
)


def audit_matrix():
    disagreements = []
    claimed_counts: dict = {}
    witnessed_counts: dict = {}
    for surface_id, clue, answer, expected_claimed, expected_witnessed in AUDIT_SURFACES:
        observed = _clue_family_observation(clue, answer)
        claimed = observed.get("family", "definition")
        verdict = witness_clue_family(claimed, clue, answer)
        witnessed = verdict["family"]
        claimed_counts[claimed] = claimed_counts.get(claimed, 0) + 1
        witnessed_counts[witnessed] = witnessed_counts.get(witnessed, 0) + 1
        if claimed != expected_claimed or witnessed != expected_witnessed:
            disagreements.append(
                {
                    "surface": surface_id,
                    "clue": clue,
                    "answer": answer,
                    "claimed": claimed,
                    "expectedClaimed": expected_claimed,
                    "witnessed": witnessed,
                    "expectedWitnessed": expected_witnessed,
                }
            )
    return claimed_counts, witnessed_counts, disagreements


def audit_corpus():
    """Re-score the local corpus surfaces; an empty corpus is an honest zero."""
    corpus = load_corpus()
    records = corpus["records"] if corpus["captured"] else []
    claimed_counts: dict = {}
    witnessed_counts: dict = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        observed = _clue_family_observation(record.get("clue", ""), record.get("answer"))
        claimed = observed.get("family", "definition")
        witnessed = witness_clue_family(claimed, record.get("clue", ""), record.get("answer"))["family"]
        claimed_counts[claimed] = claimed_counts.get(claimed, 0) + 1
        witnessed_counts[witnessed] = witnessed_counts.get(witnessed, 0) + 1
    return {
        "captured": corpus["captured"],
        "pairs": len(records),
        "familyCountsClaimed": dict(sorted(claimed_counts.items())),
        "familyCountsWitnessed": dict(sorted(witnessed_counts.items())),
    }


def hidden_word_probe():
    probe = witness_hidden_word_span('Found inside "cabin door"')
    return {
        "surface": 'Found inside "cabin door"',
        "witnessed": probe["witnessed"] is True,
        "span": probe.get("span"),
    }


def receipt_body():
    claimed, witnessed, disagreements = audit_matrix()
    corpus = audit_corpus()
    claimed_pun = claimed.get("pun", 0)
    witnessed_pun = witnessed.get("pun", 0)
    return {
        "version": RECEIPT_VERSION,
        "kind": "offline",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "claim": (
            "a claimed family is punctuation; a witnessed family carries the "
            "witness the family requires, and the gap is reported"
        ),
        "matrix": {
            "surfaces": len(AUDIT_SURFACES),
            "expectationsSource": "hand-listed English, not the rule under test",
            "familyCountsClaimed": dict(sorted(claimed.items())),
            "familyCountsWitnessed": dict(sorted(witnessed.items())),
            "disagreements": disagreements,
        },
        "punInflation": {
            "claimedPun": claimed_pun,
            "witnessedPun": witnessed_pun,
            "pseudoPun": witnessed.get("pseudo-pun", 0),
            "unwitnessedPun": claimed_pun - witnessed_pun,
        },
        "corpus": corpus,
        "hiddenWordProbe": hidden_word_probe(),
        "knownLimits": [
            "the ledger is 50 curated homographs labeled sense-source curated-v1, not a sense inventory",
            "a pivot that is the answer itself is refused; bare stems of doubled comparatives are not reversed",
            "stress-dependent doubling and irregular degree pairs are not modeled",
            "the corpus rescore is empty until a generation populates the local corpus",
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
                "claimedPun": receipt["punInflation"]["claimedPun"],
                "witnessedPun": receipt["punInflation"]["witnessedPun"],
                "disagreements": len(receipt["matrix"]["disagreements"]),
                "corpusPairs": receipt["corpus"]["pairs"],
            },
            indent=2,
        )
    )
    return 1 if receipt["matrix"]["disagreements"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
