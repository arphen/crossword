"""Closed specimen ledger for clue verdicts (Q02).

Measurement needs a denominator no code can produce: human verdicts on
real clue/answer pairs. The ledger holds 60–100 pairs with exactly one
closed verdict each — ``leak``, ``tautology``, ``name-slot``,
``pseudo-pun``, ``acceptable``, ``better-of-pair`` — plus the worked
examples every later scorer is scored against (``more shady``/``SHADIER``
first). ``better-of-pair`` marks the winner of a linked pair only.

The ledger is answer-bearing and lives outside the evidence tree at
``private-clue-specimens-v1.local.json`` (repo root, gitignored, never
committed). Only counts plus a digest are committed, via
``scripts/private-clue-specimen-label.py attest``. Later claims (Q01/Q03/Q04
rules, candidate comparisons) report agreement or disagreement against these
stable ids and verdicts.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import os

SPECIMEN_VERSION = "private-clue-specimen-ledger-v1"
SPECIMEN_FILENAME = "private-clue-specimens-v1.local.json"
SPECIMEN_ENV = "CROSSWORD_CLUE_SPECIMEN_PATH"

VERDICTS = (
    "leak",
    "tautology",
    "name-slot",
    "pseudo-pun",
    "acceptable",
    "better-of-pair",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ledger_path() -> Path:
    """Local ledger location; override with CROSSWORD_CLUE_SPECIMEN_PATH in tests."""
    override = os.environ.get(SPECIMEN_ENV, "").strip()
    if override:
        return Path(override)
    return _repo_root() / SPECIMEN_FILENAME


def _text(value) -> str:
    return value if isinstance(value, str) else ""


def make_record(
    record_id,
    answer,
    clue,
    *,
    source="hand-listed",
    weekday=None,
    seed=None,
    model_tag=None,
    pair_id=None,
    note=None,
) -> dict:
    """Build one unlabeled ledger record; the operator supplies the verdict."""
    return {
        "id": _text(record_id),
        "answer": _text(answer),
        "clue": _text(clue),
        "weekday": _text(weekday) or None,
        "seed": seed if isinstance(seed, int) else None,
        "modelTag": _text(model_tag) or None,
        "source": _text(source) or "hand-listed",
        "verdict": None,
        "pairId": _text(pair_id) or None,
        "note": _text(note) or None,
        "labeledAt": None,
    }


def validate_ledger(records) -> list:
    """Return a list of ledger problems; empty means the ledger is closed."""
    problems = []
    if not isinstance(records, list):
        return ["ledger must be a list of records"]
    seen = set()
    pairs: dict = {}
    for index, record in enumerate(records):
        where = f"records[{index}]"
        if not isinstance(record, dict):
            problems.append(f"{where} must be an object")
            continue
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            problems.append(f"{where} needs a non-empty id")
        elif record_id in seen:
            problems.append(f"duplicate id {record_id!r}")
        else:
            seen.add(record_id)
        if not record.get("answer") or not record.get("clue"):
            problems.append(f"{where} ({record_id}) needs an answer and a clue")
        verdict = record.get("verdict")
        if verdict is not None and verdict not in VERDICTS:
            problems.append(f"{where} ({record_id}) has verdict {verdict!r} outside {list(VERDICTS)}")
        pair_id = record.get("pairId")
        if pair_id is not None:
            if not isinstance(pair_id, str) or not pair_id:
                problems.append(f"{where} ({record_id}) has a malformed pairId")
            else:
                pairs.setdefault(pair_id, []).append(record_id)
        if verdict == "better-of-pair" and pair_id is None:
            problems.append(f"{where} ({record_id}) is better-of-pair with no pair")
    for pair_id, members in pairs.items():
        if len(members) != 2:
            problems.append(f"pair {pair_id!r} links {len(members)} records, need exactly 2")
            continue
        winners = [
            record_id
            for record in records
            if record.get("id") in members and record.get("verdict") == "better-of-pair"
        ]
        if len(winners) > 1:
            problems.append(f"pair {pair_id!r} names {len(winners)} winners, need at most 1")
    return problems


def load_ledger(path=None) -> dict:
    """Load the local ledger; a missing file is an empty ledger, not an error."""
    target = Path(path) if path is not None else ledger_path()
    if not target.is_file():
        return {"version": SPECIMEN_VERSION, "records": [], "present": False}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": SPECIMEN_VERSION, "records": [], "present": False, "corrupt": True}
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        return {"version": SPECIMEN_VERSION, "records": [], "present": False, "corrupt": True}
    return {"version": SPECIMEN_VERSION, "records": records, "present": True}


def save_ledger(records, path=None) -> Path:
    """Write the ledger atomically; validates shape, not verdicts."""
    target = Path(path) if path is not None else ledger_path()
    payload = {"version": SPECIMEN_VERSION, "records": list(records or [])}
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return target


def _canonical_digest(records) -> str:
    canonical = json.dumps(
        {"version": SPECIMEN_VERSION, "records": records},
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    )
    return "sha256-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def ledger_attestation(records) -> dict:
    """Answer-free counts plus digest for the committed attestation."""
    counts: dict = {}
    unlabeled = 0
    for record in records or []:
        verdict = record.get("verdict") if isinstance(record, dict) else None
        if verdict is None:
            unlabeled += 1
        else:
            counts[verdict] = counts.get(verdict, 0) + 1
    return {
        "version": SPECIMEN_VERSION,
        "pairs": len(records or []),
        "labeled": sum(counts.values()),
        "unlabeled": unlabeled,
        "verdictCounts": dict(sorted(counts.items())),
        "digest": _canonical_digest(list(records or [])),
    }


def agreement_report(records, judgments) -> dict:
    """Score rule judgments against ledger verdicts, by stable id.

    ``judgments`` maps record id to a claimed verdict string. Returns
    agreement counts plus per-id disagreements, so later claims (leak gate,
    witness admission, candidate comparison) report against the ledger
    instead of redefining it.
    """
    ledger = {
        record["id"]: record.get("verdict")
        for record in (records or [])
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }
    agreed = 0
    disagreements = []
    unknown = 0
    for record_id, claimed in (judgments or {}).items():
        expected = ledger.get(record_id)
        if expected is None:
            unknown += 1
        elif claimed == expected:
            agreed += 1
        else:
            disagreements.append(
                {"id": record_id, "expected": expected, "claimed": claimed}
            )
    scored = agreed + len(disagreements)
    return {
        "scored": scored,
        "agreed": agreed,
        "disagreed": len(disagreements),
        "unknownIds": unknown,
        "agreementRate": round(agreed / scored, 4) if scored else 0.0,
        "disagreements": sorted(disagreements, key=lambda item: item["id"]),
    }
