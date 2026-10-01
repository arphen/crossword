#!/usr/bin/env python3
"""Label the closed specimen ledger for clue verdicts (Q02).

The ledger is answer-bearing and stays on this host
(``private-clue-specimens-v1.local.json``, gitignored, never committed).
Only counts plus a digest are committed, via ``attest``.

Workflow for the labeling session (~40 minutes, 60-100 pairs):
  seed    build the ledger from hand-listed §0 surfaces plus a corpus sample
  status  show labeled/unlabeled counts and incomplete pairs
  label   record one verdict: label --id <id> --verdict <verdict> [--note ...]
  pair    link two records for better-of-pair: pair --ids <a> <b>
  attest  validate the closed ledger and write the committed attestation

Closed verdicts: leak, tautology, name-slot, pseudo-pun, acceptable,
better-of-pair (winner of a linked pair only).
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

from src.crossword.clue_specimens import (  # noqa: E402
    SPECIMEN_VERSION,
    VERDICTS,
    ledger_attestation,
    ledger_path,
    load_ledger,
    make_record,
    save_ledger,
    validate_ledger,
)
from src.crossword.private_clue_corpus import load_corpus  # noqa: E402

ATTESTATION_VERSION = "private-clue-specimen-attestation-v1"

HAND_LISTED = (
    # (id, answer, clue, note)
    ("sp-tautology-shadier", "SHADIER", "more shady", "§0: the comparative is the answer"),
    ("sp-leak-shady", "SHADY", "shadier character", "derivation leak: answer degree form in clue"),
    ("sp-pun-auctioneer", "AUCTIONEER", "One with a lot to say?", "witnessed pun, pivot LOT"),
    ("sp-pun-teller", "TELLER", "Branch specialist?", "witnessed pun, pivot BRANCH"),
    ("sp-pseudo-den", "DEN", "A quiet room?", "bare-? pseudo-pun"),
    ("sp-name-singer", "ADELE", "Famous singer's name", "name slot, no source"),
    ("sp-name-writer", "NASH", "Famous writer's name", "name slot, no source"),
    ("sp-fill-voyage", "BON", "___ voyage", "fill-blank with its mark"),
    ("sp-spoken-greeting", "GREETING", '"Hello there" (Spoken equivalent)', "utterance plus label"),
    ("sp-spoken-bare", "HAMLET", '"To be or not to be"', "utterance without label"),
    ("sp-plain-dark", "DARK", "Without light", "plain definition"),
    ("sp-plain-are", "ARE", "They ___ here", "fill-in definition"),
    ("sp-pair-bright-a", "BRIGHTER", "more bright", "pair: tautological comparative"),
    ("sp-pair-bright-b", "BRIGHTER", "Full of light", "pair: plain definition"),
)


def _read_ledger(path):
    ledger = load_ledger(path)
    if ledger.get("corrupt"):
        raise SystemExit("ledger file is corrupt; restore it before labeling")
    return ledger["records"]


def _write_ledger(records, path):
    save_ledger(records, path)
    problems = validate_ledger(records)
    return problems


def command_seed(args) -> int:
    target = Path(args.out) if args.out else ledger_path()
    if target.is_file() and not args.force:
        raise SystemExit(f"ledger exists at {target}; pass --force to rebuild")
    records = [
        make_record(record_id, answer, clue, source="hand-listed §0", note=note)
        for record_id, answer, clue, note in HAND_LISTED
    ]
    # Link the better-of-pair surfaces; the operator names the winner.
    pair_id = "pair-bright-1"
    for record in records:
        if record["id"] in ("sp-pair-bright-a", "sp-pair-bright-b"):
            record["pairId"] = pair_id
    corpus = load_corpus()
    sampled = 0
    if corpus["captured"]:
        for record in corpus["records"]:
            if not isinstance(record, dict) or sampled >= args.corpus_n:
                continue
            answer, clue = record.get("answer"), record.get("clue")
            if not answer or not clue:
                continue
            records.append(
                make_record(
                    f"corpus-{record.get('seed')}-{record.get('id')}",
                    answer,
                    clue,
                    source="local-corpus",
                    weekday=record.get("weekday"),
                    seed=record.get("seed"),
                    model_tag=record.get("modelTag"),
                )
            )
            sampled += 1
    save_ledger(records, target)
    print(
        json.dumps(
            {
                "out": os.path.relpath(target, ROOT) if _is_relative(target) else str(target),
                "records": len(records),
                "handListed": len(HAND_LISTED),
                "corpusSampled": sampled,
            },
            indent=2,
        )
    )
    return 0


def _is_relative(target: Path) -> bool:
    try:
        target.relative_to(ROOT)
        return True
    except ValueError:
        return False


def command_label(args) -> int:
    records = _read_ledger(args.ledger)
    if args.verdict not in VERDICTS:
        raise SystemExit(f"verdict must be one of {list(VERDICTS)}")
    for record in records:
        if record.get("id") == args.id:
            record["verdict"] = args.verdict
            if args.note:
                record["note"] = args.note
            record["labeledAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            save_ledger(records, args.ledger)
            print(json.dumps({"id": args.id, "verdict": args.verdict}, indent=2))
            return 0
    raise SystemExit(f"no record {args.id!r} in the ledger")


def command_pair(args) -> int:
    records = _read_ledger(args.ledger)
    first, second = args.ids
    found = {record.get("id") for record in records}
    if first not in found or second not in found:
        raise SystemExit("both ids must exist in the ledger")
    pair_id = f"pair-{first}-{second}"
    for record in records:
        if record.get("id") in (first, second):
            record["pairId"] = pair_id
    save_ledger(records, args.ledger)
    print(json.dumps({"pairId": pair_id, "members": [first, second]}, indent=2))
    return 0


def command_status(args) -> int:
    records = _read_ledger(args.ledger)
    counts: dict = {}
    unlabeled = [record.get("id") for record in records if record.get("verdict") is None]
    for record in records:
        verdict = record.get("verdict")
        if verdict is not None:
            counts[verdict] = counts.get(verdict, 0) + 1
    problems = validate_ledger(records)
    print(
        json.dumps(
            {
                "records": len(records),
                "labeled": sum(counts.values()),
                "unlabeled": len(unlabeled),
                "verdictCounts": dict(sorted(counts.items())),
                "unlabeledIds": sorted(i for i in unlabeled if isinstance(i, str)),
                "problems": problems,
            },
            indent=2,
        )
    )
    return 0


def command_attest(args) -> int:
    records = _read_ledger(args.ledger)
    problems = validate_ledger(records)
    attestation = ledger_attestation(records)
    unlabeled = attestation["unlabeled"]
    if problems or unlabeled:
        print(
            json.dumps(
                {"problems": problems, "unlabeled": unlabeled, "attested": False}, indent=2
            )
        )
        return 1
    out = Path(args.out) if args.out else (
        ROOT / "docs" / "evidence" / f"{ATTESTATION_VERSION}.{_today()}.json"
    )
    body = {
        "version": ATTESTATION_VERSION,
        "kind": "counts-only",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "claim": (
            "closed human verdicts on real clue/answer pairs; every later "
            "scorer is scored against these ids and verdicts"
        ),
        "ledger": attestation,
        "knownLimits": [
            "the ledger is answer-bearing, local-only, and never committed",
            "verdicts judge the clue/answer relation, not semantic truth or player difficulty",
        ],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"out": os.path.relpath(out, ROOT), "pairs": attestation["pairs"], "digest": attestation["digest"]},
            indent=2,
        )
    )
    return 0


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=None, help="ledger path (default: local ledger)")
    sub = parser.add_subparsers(dest="command", required=True)
    seed = sub.add_parser("seed", help="build the ledger")
    seed.add_argument("--out", type=Path, default=None)
    seed.add_argument("--corpus-n", type=int, default=48)
    seed.add_argument("--force", action="store_true")
    label = sub.add_parser("label", help="record one verdict")
    label.add_argument("--id", required=True)
    label.add_argument("--verdict", required=True, choices=list(VERDICTS))
    label.add_argument("--note", default=None)
    pair = sub.add_parser("pair", help="link two records for better-of-pair")
    pair.add_argument("--ids", nargs=2, required=True, metavar=("A", "B"))
    sub.add_parser("status", help="show labeling progress")
    attest = sub.add_parser("attest", help="validate and write the attestation")
    attest.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if args.ledger is None:
        args.ledger = ledger_path()
    else:
        args.ledger = Path(args.ledger)
    return {
        "seed": command_seed,
        "label": command_label,
        "pair": command_pair,
        "status": command_status,
        "attest": command_attest,
    }[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
