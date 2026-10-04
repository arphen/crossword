#!/usr/bin/env python3
"""Label the closed specimen ledger for clue verdicts (Q02).

The ledger is answer-bearing and stays on this host
(``private-clue-specimens-v1.local.json``, gitignored, never committed).
Only counts plus a digest are committed, via ``attest``.

The 14 hand-listed §0 surfaces are spec reference: pre-labeled by the
spec, read-only, never judged. Scaffold placeholders are skipped at seed
by string match. The operator judges only the blind queue — real model
surfaces with genuinely unknown verdicts.

Workflow for the labeling session:
  seed    build the ledger: spec reference + blind queue (corpus + harvest)
  status  show blind/reference counts and open blind ids
  label   record one blind verdict: label --id <id> --verdict <verdict>
  pair    link two blind records for better-of-pair: pair --ids <a> <b>
  attest  validate the closed blind queue and write the attestation

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
    load_harvest,
    load_ledger,
    save_ledger,
    seed_records,
    validate_ledger,
)
from src.crossword.private_clue_corpus import load_corpus  # noqa: E402

ATTESTATION_VERSION = "private-clue-specimen-attestation-v1"


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
    harvest = load_harvest()
    records, report = seed_records(
        args.corpus_n,
        (load_corpus().get("records") or []),
        (harvest.get("records") or []),
        args.harvest_n,
    )
    save_ledger(records, target)
    print(
        json.dumps(
            {
                "out": os.path.relpath(target, ROOT) if _is_relative(target) else str(target),
                **report,
                "harvestPresent": harvest["present"],
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
            if record.get("origin") == "spec":
                raise SystemExit(
                    f"{args.id!r} is spec reference, decided by the spec — "
                    "judge the blind queue instead"
                )
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
    found = {record.get("id"): record for record in records}
    if first not in found or second not in found:
        raise SystemExit("both ids must exist in the ledger")
    if found[first].get("origin") == "spec" or found[second].get("origin") == "spec":
        raise SystemExit("reference records keep their spec pairs; link blind records")
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
    blind = [record for record in records if record.get("origin") != "spec"]
    unlabeled = [record.get("id") for record in blind if record.get("verdict") is None]
    for record in records:
        verdict = record.get("verdict")
        if verdict is not None:
            counts[verdict] = counts.get(verdict, 0) + 1
    problems = validate_ledger(records)
    print(
        json.dumps(
            {
                "records": len(records),
                "reference": len(records) - len(blind),
                "blind": len(blind),
                "blindLabeled": len(blind) - len(unlabeled),
                "blindUnlabeled": len(unlabeled),
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
    unlabeled = attestation["blindUnlabeled"]
    blind = sum(1 for r in records if r.get("origin") != "spec")
    if not blind:
        print(json.dumps({"attested": False, "error": "no blind queue; seed real surfaces first"}, indent=2))
        return 1
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
            "closed blind human verdicts on real clue/answer pairs, plus "
            "spec-defined reference; every later scorer reports blind "
            "agreement against these ids and verdicts"
        ),
        "ledger": attestation,
        "knownLimits": [
            "the ledger is answer-bearing, local-only, and never committed",
            "verdicts judge the clue/answer relation, not semantic truth or player difficulty",
            "reference verdicts are spec-defined worked examples, not independent judgment",
            "scaffold placeholders are excluded deterministically, never queued",
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
    seed.add_argument("--harvest-n", type=int, default=48)
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
