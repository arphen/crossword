#!/usr/bin/env python3
"""Emit the Q03 corpus attestation and the counter re-resolution receipt.

The local answer-bearing corpus (``docs/evidence/private-clue-corpus-v1.local.json``,
gitignored, never committed) is summarized here as counts plus a digest, which
is the only thing that enters ``docs/evidence/``. Separately, the surviving
counters in the existing study artifacts are re-aggregated into
``private-clue-counter-reresolution-v1.offline.json`` — which is all those
counter-only receipts permit, and which is what surfaced the ``fill-blank:
57 of 74`` finding.

Both commands are offline. Neither starts Ollama, and neither reads or writes
a user profile.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.crossword.private_clue_corpus import (  # noqa: E402
    CORPUS_VERSION,
    corpus_counts_attestation,
    reresolve_counters,
)

ATTESTATION_VERSION = "private-clue-corpus-attestation-v1"
RERESOLUTION_VERSION = "private-clue-counter-reresolution-v1"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _file_digest(path: Path) -> str:
    return "sha256-" + hashlib.sha256(path.read_bytes()).hexdigest()


def attest_body() -> dict:
    counts = corpus_counts_attestation()
    return {
        "version": ATTESTATION_VERSION,
        "kind": "counts-only",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "claim": (
            "the local answer-bearing clue corpus holds this many pairs "
            "under this digest; only counts and the digest are committed"
        ),
        "corpus": counts,
        "knownLimits": [
            "the attestation proves a denominator exists, not that any clue is good",
            "answer-bearing records stay on this host and are never committed",
        ],
    }


def collect_study_artifacts() -> list:
    """Load every private study artifact that may carry counters."""
    artifacts = []
    for path in sorted((ROOT / "docs" / "evidence").glob("private-*.json")):
        if path.name.endswith(".local.json"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        artifacts.append((path.name, _file_digest(path), payload))
    return artifacts


def reresolve_body() -> dict:
    receipt = reresolve_counters(collect_study_artifacts())
    receipt["generatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    receipt["kind"] = "offline"
    receipt["interpretation"] = (
        "surface-and-mechanical counters only; the artifacts carry no clue "
        "text, so no quality claim follows"
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--attest-out",
        type=Path,
        default=ROOT / "docs" / "evidence" / f"{ATTESTATION_VERSION}.{_today()}.json",
        help="where to write the counts-plus-digest attestation",
    )
    parser.add_argument(
        "--reresolve-out",
        type=Path,
        default=ROOT / "docs" / "evidence" / f"{RERESOLUTION_VERSION}.offline.json",
        help="where to write the counter re-resolution receipt",
    )
    args = parser.parse_args()

    attestation = attest_body()
    args.attest_out.parent.mkdir(parents=True, exist_ok=True)
    args.attest_out.write_text(json.dumps(attestation, indent=2) + "\n", encoding="utf-8")

    reresolution = reresolve_body()
    args.reresolve_out.parent.mkdir(parents=True, exist_ok=True)
    args.reresolve_out.write_text(json.dumps(reresolution, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "attestation": str(args.attest_out.relative_to(ROOT)),
                "corpusCaptured": attestation["corpus"]["captured"],
                "corpusPairs": attestation["corpus"]["pairs"],
                "corpusDigest": attestation["corpus"]["digest"],
                "reresolution": str(args.reresolve_out.relative_to(ROOT)),
                "files": len(reresolution["files"]),
                "families": reresolution["familyTotals"],
                "maxFillBlankShare": reresolution["maxFillBlankShare"],
            },
            indent=2,
        )
    )
    return 0 if attestation["corpus"]["captured"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
