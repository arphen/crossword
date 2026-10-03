#!/usr/bin/env python3
"""Dialectical iteration ledger for the AutoResearch loop.

Every loop turn is filed as thesis -> antithesis -> synthesis, examined at
filing time, with follow-ups scheduled as a result. The loop runner reads
due follow-ups to select the next arms; closing a follow-up requires the
outcome and the commit that records it.

Ledger entries are process, not evidence: no clue text, only ids, counts,
and interpretation. Appended as JSONL; never rewritten.

  record   file one examined iteration
  due      list open follow-ups, oldest first
  close    close a follow-up with its outcome and commit
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "evidence" / "private-loop-ledger-v1.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read() -> list:
    if not LEDGER.is_file():
        return []
    return [
        json.loads(line)
        for line in LEDGER.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def command_record(args) -> int:
    followups = []
    for spec in args.followup or []:
        label, _, condition = spec.partition("::")
        followups.append(
            {
                "id": uuid.uuid4().hex[:8],
                "label": label.strip(),
                "condition": condition.strip(),
                "status": "open",
                "openedAt": _now(),
                "closedAt": None,
                "outcome": None,
            }
        )
    entry = {
        "kind": "iteration",
        "filedAt": _now(),
        "thesis": args.thesis,
        "antithesis": args.antithesis,
        "synthesis": args.synthesis,
        "receipt": args.receipt,
        "commit": args.commit,
        "followups": followups,
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {"filed": True, "followups": [f["id"] for f in followups]}, indent=2
        )
    )
    return 0


def command_due(_args) -> int:
    open_items = []
    for entry in _read():
        for followup in entry.get("followups", []):
            if followup.get("status") == "open":
                open_items.append(
                    {
                        "id": followup["id"],
                        "label": followup["label"],
                        "condition": followup["condition"],
                        "openedAt": followup["openedAt"],
                        "fromThesis": entry.get("thesis", "")[:120],
                    }
                )
    open_items.sort(key=lambda item: item["openedAt"])
    print(json.dumps({"open": len(open_items), "followups": open_items}, indent=2))
    return 0


def command_close(args) -> int:
    lines = _read()
    found = False
    for entry in lines:
        for followup in entry.get("followups", []):
            if followup.get("id") == args.id and followup.get("status") == "open":
                followup["status"] = "closed"
                followup["closedAt"] = _now()
                followup["outcome"] = args.outcome
                followup["commit"] = args.commit
                found = True
    if not found:
        raise SystemExit(f"no open follow-up {args.id!r}")
    LEDGER.write_text(
        "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in lines),
        encoding="utf-8",
    )
    print(json.dumps({"closed": args.id}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser("record")
    record.add_argument("--thesis", required=True)
    record.add_argument("--antithesis", required=True)
    record.add_argument("--synthesis", required=True)
    record.add_argument("--receipt", default=None)
    record.add_argument("--commit", default=None)
    record.add_argument("--followup", action="append", default=[],
                        help="LABEL::CONDITION, repeatable")
    record.set_defaults(run=command_record)
    due = sub.add_parser("due")
    due.set_defaults(run=command_due)
    close = sub.add_parser("close")
    close.add_argument("--id", required=True)
    close.add_argument("--outcome", required=True)
    close.add_argument("--commit", default=None)
    close.set_defaults(run=command_close)
    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
