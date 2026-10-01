#!/usr/bin/env python3
"""Run the candidate-lane A/B for private clue generation (Q07).

Arm A runs the legacy whole-board single draft; arm B runs the candidate
path (k shortlisted drafts per entry with distinct seeds, deterministic
admission, one comparison over the survivors). Both arms drive the real
``_make_clues`` code paths against the same fixed entry set on the same
model tag, and both are scored on deterministic rules only (leak, witness,
genre, grammar) via ``score_surface_set`` — no preference corpus exists, so
no quality winner beyond the rules is claimed.

The frozen 26 B counter receipts in docs/evidence supply context, not a
contender: no 26 B lives on this host. If the 3 B candidate lane does not
beat the 3 B single draft, that negative result is the deliverable and it
sends the registry toward a remote route instead of a rewrite.

Needs a running Ollama. Offline otherwise; no profile, no server.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.crossword.clue_candidate_admission import score_surface_set  # noqa: E402
from src.crossword.clue_genre import observe_clue_genre  # noqa: E402
from src.crossword.clue_witness import witness_clue_family  # noqa: E402
from src.crossword.private_clue_corpus import load_corpus  # noqa: E402
from src.crossword import private_puzzle_generation as generation  # noqa: E402

RECEIPT_VERSION = "private-clue-candidate-lane-v1"

FALLBACK_ANSWERS = [
    "CAT", "DOG", "ECHO", "MOSS", "TUNING", "STITCH", "RESONANCE", "PATTERN",
    "WEAVE", "LIGHT", "DARK", "BRIGHT", "QUIET", "NOISY", "HAPPY", "SORRY",
    "SHADY", "NICE", "LARGE", "WARM", "STRONG", "YOUNG", "BOLD", "RICH",
]


def entry_set(size=24):
    """Fixed entry set: first answers from the local corpus, else hand-listed."""
    corpus = load_corpus()
    answers = []
    if corpus["captured"]:
        seen = set()
        for record in corpus["records"]:
            answer = record.get("answer") if isinstance(record, dict) else None
            if isinstance(answer, str) and len(answer) >= 3 and answer not in seen:
                seen.add(answer)
                answers.append(answer)
            if len(answers) >= size:
                break
    if len(answers) < 12:
        answers = list(FALLBACK_ANSWERS[:size])
    answers = answers[:size]
    return [
        {"id": f"{index}A", "answer": answer, "length": len(answer)}
        for index, answer in enumerate(answers)
    ], ("corpus" if corpus["captured"] and len(answers) >= 12 else "hand-listed")


def diagnose(entries, clues):
    """Build deterministic per-surface diagnostics for scoring."""
    diagnostics = []
    for entry in entries:
        clue_id = entry.get("id")
        text = clues.get(clue_id, "") if isinstance(clues, dict) else ""
        issues = [
            code
            for code in (
                generation._clue_wordplay_issue(entry, text),
                generation._clue_morphology_issue(entry, text),
                generation._clue_information_issue(entry, text, weekday="monday"),
            )
            if isinstance(code, str) and code
        ]
        for flag in generation._clue_risk_flags(entry, text) or []:
            if isinstance(flag, str) and flag and flag != "foothold-required":
                issues.append(flag)
        claimed = generation._clue_family_observation(text).get("family", "definition")
        witnessed = witness_clue_family(claimed, text, entry.get("answer"))["family"]
        diagnostics.append(
            {
                "answer": entry.get("answer"),
                "clue": text,
                "issues": sorted(set(issues)),
                "witnessedFamily": witnessed,
                "genre": observe_clue_genre(text).get("genre"),
            }
        )
    return diagnostics


def run_arm(model, entries, candidate: bool):
    """Run one arm through the real _make_clues code path."""
    context = {"_candidate_base_seed": 6107}
    key = "CROSSWORD_CLUE_CANDIDATES"
    previous = os.environ.get(key)
    os.environ[key] = "1" if candidate else "0"
    started = time.monotonic()
    try:
        title, clues = generation._make_clues(model, entries, context, "monday")
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous
    wall = round(time.monotonic() - started, 3)
    candidate_receipt = context.get("_candidate_generation")
    return {
        "clues": clues,
        "title": title,
        "wallSeconds": wall,
        "candidateCalls": {
            "draft": (candidate_receipt or {}).get("draftCalls"),
            "compare": (candidate_receipt or {}).get("compareCalls"),
        }
        if candidate
        else None,
        "challengeEnabled": (candidate_receipt or {}).get("challengeEnabled"),
    }


def decide(single, candidate):
    """Stated winner rule: witnessed rate, then grammar-clean, then leak."""
    key = lambda report: (
        report["witnessedNonDefinitionRate"],
        report["grammarCleanRate"],
        -report["leakRate"],
    )
    if key(candidate) > key(single):
        return "candidate"
    if key(candidate) < key(single):
        return "single-draft"
    return "tie"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="llama3.2:3b", help="model tag for both arms")
    parser.add_argument("--entries", type=int, default=24, help="fixed entry set size")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="receipt path (default: docs/evidence/private-clue-candidate-lane-v1.<tag>-<date>.json)",
    )
    args = parser.parse_args()
    safe_tag = re.sub(r"[^A-Za-z0-9.]+", "-", args.model)
    if args.out is None:
        args.out = (
            ROOT
            / "docs"
            / "evidence"
            / f"{RECEIPT_VERSION}.{safe_tag}-{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
        )

    entries, source = entry_set(args.entries)
    arms = {}
    for name, candidate in (("single", False), ("candidate", True)):
        print(f"[{name}] running {len(entries)} entries on {args.model}…", flush=True)
        run = run_arm(args.model, entries, candidate)
        score = score_surface_set(diagnose(entries, run["clues"]))
        arms[name] = {**run, "score": score, "clueCount": len(run["clues"])}
        print(
            f"[{name}] {run['wallSeconds']}s witnessed={score['witnessedNonDefinitionRate']} "
            f"clean={score['grammarCleanRate']} leak={score['leakRate']}",
            flush=True,
        )
        del arms[name]["clues"]

    winner = decide(arms["single"]["score"], arms["candidate"]["score"])
    receipt = {
        "version": RECEIPT_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "live-model",
        "model": args.model,
        "entrySource": source,
        "entryCount": len(entries),
        "claim": "candidate selection vs single draft on one tag, deterministic rules only",
        "arms": arms,
        "winner": winner,
        "winnerRule": "witnessedNonDefinitionRate, then grammarCleanRate, then leakRate ascending",
        "interpretation": (
            "candidate lane beats single draft here" if winner == "candidate" else
            "negative result: selection does not beat single draft on this tag; "
            "registry advice leans remote rather than rewrite"
            if winner == "single-draft" else
            "tie on deterministic rules; no selection claim follows"
        ),
        "knownLimits": [
            "no preference corpus exists, so no quality winner is claimed",
            "frozen 26 B surfaces do not exist on this host; 26 B counter receipts supply context only",
            "challenge flag state is echoed per arm where the candidate path ran",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": os.path.relpath(args.out, ROOT), "winner": winner}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
