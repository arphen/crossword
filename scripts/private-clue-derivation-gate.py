#!/usr/bin/env python3
"""Emit the derivation-leak gate receipt for private clue generation.

A clue such as ``more shady`` for ``SHADIER`` defines an answer by repeating
the answer's own comparative. The guard that rejects it lives in
``_clue_wordplay_issue``; this script is the evidence that it works, and just
as importantly, that it does not eat clues it should leave alone.

Every pair below is machine-checkable English morphology, not operator
judgement. The expected forms are hand-listed rather than computed from the
rule under test, so a change in the rule shows up here as a disagreement
instead of moving the goalposts. The receipt therefore proves coverage of a
stated scope; it proves nothing about clue quality on real boards, and it is
labelled ``synthetic`` for that reason.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.crossword.private_puzzle_generation import (  # noqa: E402
    _clue_wordplay_issue,
    _degree_forms,
)

RECEIPT_VERSION = "private-clue-derivation-gate-v1"

# base, comparative, superlative, a plain definition that must stay legal.
# Hand-listed from ordinary English, including the irregular doubling that the
# orthographic rule is expected to reproduce.
GRADABLE = (
    ("SHADY", "SHADIER", "SHADIEST", "dubious-looking"),
    ("NICE", "NICER", "NICEST", "pleasant enough"),
    ("LARGE", "LARGER", "LARGEST", "of great size"),
    ("DARK", "DARKER", "DARKEST", "without light"),
    ("OLD", "OLDER", "OLDEST", "long in the tooth"),
    ("ODD", "ODDER", "ODDEST", "out of the ordinary"),
    ("BRIGHT", "BRIGHTER", "BRIGHTEST", "full of light"),
    ("COOL", "COOLER", "COOLEST", "slightly cold"),
    ("DEEP", "DEEPER", "DEEPEST", "bottomless"),
    ("QUIET", "QUIETER", "QUIETEST", "silent"),
    ("SORRY", "SORRIER", "SORRIEST", "feeling bad"),
    ("HAPPY", "HAPPIER", "HAPPIEST", "full of joy"),
    ("EARLY", "EARLIER", "EARLIEST", "before the hour"),
    ("SIMPLE", "SIMPLER", "SIMPLEST", "plain and direct"),
    ("NOBLE", "NOBLER", "NOBLEST", "high-minded"),
    ("WISE", "WISER", "WISEST", "having judgement"),
    ("FAT", "FATTER", "FATTEST", "plump"),
    ("SWEET", "SWEETER", "SWEETEST", "like sugar"),
    ("FAST", "FASTER", "FASTEST", "swift"),
    ("SLOW", "SLOWER", "SLOWEST", "unhurried"),
    ("HIGH", "HIGHER", "HIGHEST", "lofty"),
    ("WIDE", "WIDER", "WIDEST", "broad"),
    ("NOISY", "NOISIER", "NOISIEST", "loud"),
    ("DIRTY", "DIRTIER", "DIRTIEST", "grubby"),
    ("HEAVY", "HEAVIER", "HEAVIEST", "of great weight"),
    ("COLD", "COLDER", "COLDEST", "freezing"),
    ("WARM", "WARMER", "WARMEST", "mild"),
    ("STRONG", "STRONGER", "STRONGEST", "powerful"),
    ("YOUNG", "YOUNGER", "YOUNGEST", "not yet old"),
    ("BOLD", "BOLDER", "BOLDEST", "fearless"),
    ("RICH", "RICHER", "RICHEST", "wealthy"),
    ("POOR", "POORER", "POOREST", "impoverished"),
    ("FIT", "FITTER", "FITTEST", "in good shape"),
    ("SILLY", "SILLIER", "SILLIEST", "foolish"),
    ("GRAND", "GRANDER", "GRANDEST", "magnificent"),
    ("WET", "WETTER", "WETTEST", "soaked"),
    ("BIG", "BIGGER", "BIGGEST", "of great bulk"),
    ("HOT", "HOTTER", "HOTTEST", "burning"),
    ("MEAN", "MEANER", "MEANEST", "unkind"),
    ("KEEN", "KEENER", "KEENEST", "sharp"),
    ("TALL", "TALLER", "TALLEST", "of great height"),
    ("SOFT", "SOFTER", "SOFTEST", "not hard"),
    ("CLEAN", "CLEANER", "CLEANEST", "spotless"),
    ("CRUEL", "CRUELER", "CRUELEST", "hard-hearted"),
    ("FAIR", "FAIRER", "FAIREST", "just"),
)

# Answers that only look like they carry a stem. Each surface must stay legal:
# a guard that rejects these is worse than one that misses a leak, because it
# silently removes good fill from the board instead of repairing one clue.
LOOK_ALIKE_CONTROLS = (
    ("CASHIER", "cash register operator"),
    ("PIONEER", "early settler"),
    ("MINER", "worker in a pit"),
    ("COVER", "protect with a lid"),
    ("BUTTER", "bread but not jam"),
    ("BITTER", "not sweet, but sharp"),
    ("EARLY", "ear of corn"),
    ("OPENED", "shut and locked again"),
    ("LEADER", "head of the team"),
    ("CARPET", "rug in the hall"),
    ("TABLE", "furniture for four"),
    ("MEN", "more manly"),
    ("BEST", "more good"),
    ("BETTER", "more well"),
)


def build_pairs():
    """Build every pair with the outcome the guard is supposed to produce."""
    pairs = []
    for index, (base, comparative, superlative, definition) in enumerate(GRADABLE):
        lower = base.lower()
        pairs.append(("comparative-phrase", comparative, f"more {lower}", "reject"))
        pairs.append(("superlative-phrase", superlative, f"most {lower}", "reject"))
        # Degree-form leaks are only in scope where _answer_lexical_forms
        # expands the base (len>=4). Shorter bases (OLD, ODD, FAT) are left
        # alone on purpose: expanding them would risk collisions with
        # unrelated words, so they are recorded as limits, not failures.
        degree_scope = "reject" if len(base) >= 4 else "left-alone"
        pairs.append(
            ("answer-degree-form", base, f"{comparative.lower()} than ever", degree_scope)
        )
        pairs.append(
            (
                "answer-superlative-form",
                base,
                f"the {superlative.lower()} of all",
                degree_scope,
            )
        )
        # A bare stem is only in scope where the guard can reverse the answer's
        # own suffix, which today means the -IER family. The rest are recorded
        # as left alone on purpose rather than counted as failures.
        scope = "reject" if base.endswith("Y") else "left-alone"
        pairs.append(("stem-of-comparative", comparative, f"{lower} business", scope))
        other = GRADABLE[(index * 7 + 3) % len(GRADABLE)]
        if base != other[0]:
            pairs.append(
                (
                    "unrelated-comparative",
                    comparative,
                    f"more {other[0].lower()}",
                    "legal",
                )
            )
        pairs.append(("plain-definition", comparative, definition, "legal"))
    for answer, clue in LOOK_ALIKE_CONTROLS:
        pairs.append(("look-alike", answer, clue, "legal"))
    return pairs


def evaluate(pairs):
    reasons: dict[str, int] = {}
    misses: list[dict] = []
    false_rejects: list[dict] = []
    caught_beyond_scope: list[dict] = []
    for family, answer, clue, expectation in pairs:
        reason = _clue_wordplay_issue({"answer": answer}, clue)
        key = reason or "accepted"
        reasons[key] = reasons.get(key, 0) + 1
        record = {"family": family, "answer": answer, "clue": clue, "reason": reason}
        if expectation == "reject" and reason is None:
            misses.append(record)
        elif expectation == "legal" and reason is not None:
            false_rejects.append(record)
        elif expectation == "left-alone" and reason is not None:
            caught_beyond_scope.append(record)
    return reasons, misses, false_rejects, caught_beyond_scope


def degree_rule_gaps():
    """Where the orthographic rule disagrees with hand-listed English."""
    gaps = []
    for base, comparative, superlative, _definition in GRADABLE:
        expected = {base, comparative, superlative}
        actual = set(_degree_forms(base))
        if actual != expected:
            gaps.append(
                {
                    "base": base,
                    "expected": sorted(expected),
                    "actual": sorted(actual),
                }
            )
    return gaps


def corpus_digest(pairs):
    lines = sorted(f"{row[0]}\t{row[1]}\t{row[2]}\t{row[3]}" for row in pairs)
    return "sha256-" + hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def real_corpus_status():
    """Report whether any answer-bearing clue corpus exists on this host."""
    relative = Path("docs") / "evidence" / "private-clue-corpus-v1.local.json"
    path = ROOT / relative
    if not path.is_file():
        return {
            "captured": False,
            "reason": (
                "no answer-bearing clue corpus on disk; published study "
                "receipts carry counters only"
            ),
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "captured": True,
        "path": str(relative),
        "digest": "sha256-" + hashlib.sha256(path.read_bytes()).hexdigest(),
        "pairs": payload.get("counts", {}).get("pairs"),
    }


def receipt_body(pairs):
    reasons, misses, false_rejects, caught_beyond_scope = evaluate(pairs)
    expected_rejects = sum(1 for row in pairs if row[3] == "reject")
    expected_legal = sum(1 for row in pairs if row[3] == "legal")
    return {
        "version": RECEIPT_VERSION,
        "kind": "synthetic",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "claim": (
            "the derivation-leak gate rejects clues that define an answer "
            "with the answer's own gradation or inflection, and leaves "
            "unrelated comparatives, look-alike stems and plain definitions "
            "alone"
        ),
        "environment": {
            "os": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "modelUsed": None,
            "networkUsed": False,
        },
        "corpus": {
            "pairs": len(pairs),
            "expectedRejects": expected_rejects,
            "expectedLegal": expected_legal,
            "families": sorted({row[0] for row in pairs}),
            "digest": corpus_digest(pairs),
            "expectationsSource": (
                "hand-listed English morphology, not the rule under test"
            ),
        },
        "results": {
            "inScopeLeaksCaught": expected_rejects - len(misses),
            "inScopeLeaksTotal": expected_rejects,
            "legalSurfacesKept": expected_legal - len(false_rejects),
            "legalSurfacesTotal": expected_legal,
            "misses": misses,
            "falseRejections": false_rejects,
            "caughtBeyondStatedScope": caught_beyond_scope,
        },
        "reasonCounts": dict(sorted(reasons.items())),
        "degreeRuleGaps": degree_rule_gaps(),
        "realCorpus": real_corpus_status(),
        "knownLimits": [
            "morphology only: a clue that restates the answer without using "
            "any of its forms is outside this gate and belongs to the "
            "challenger, not to a regex",
            "a bare stem of a doubled comparative (BIG inside BIGGER) is not "
            "reversed, because BUTTER would hand back the word BUT",
            "degree-form expansion applies only to bases of length >=4; "
            "short bases such as OLD/ODD/FAT are left alone to avoid "
            "collisions with unrelated words",
            "stress-dependent doubling (THIN -> THINNER) is not modelled",
            "irregular pairs such as GOOD -> BETTER are not invented",
            "no operator-judged specimen is consumed by this receipt",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "docs" / "evidence" / f"{RECEIPT_VERSION}.synthetic.json",
        help="where to write the receipt (default: docs/evidence)",
    )
    args = parser.parse_args()

    pairs = build_pairs()
    receipt = receipt_body(pairs)
    results = receipt["results"]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": os.path.relpath(args.out, ROOT),
                "pairs": receipt["corpus"]["pairs"],
                "inScopeLeaksCaught": results["inScopeLeaksCaught"],
                "inScopeLeaksTotal": results["inScopeLeaksTotal"],
                "legalSurfacesKept": results["legalSurfacesKept"],
                "legalSurfacesTotal": results["legalSurfacesTotal"],
                "misses": len(results["misses"]),
                "falseRejections": len(results["falseRejections"]),
                "caughtBeyondStatedScope": len(
                    results["caughtBeyondStatedScope"]
                ),
                "degreeRuleGaps": len(receipt["degreeRuleGaps"]),
                "corpusDigest": receipt["corpus"]["digest"],
            },
            indent=2,
        )
    )
    return 1 if results["misses"] or results["falseRejections"] else 0


if __name__ == "__main__":
    raise SystemExit(main())



