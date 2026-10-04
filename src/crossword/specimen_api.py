"""Same-origin specimen labeling API for the closed clue-verdict ledger (Q02).

The ledger is answer-bearing and lives on this host only; the browser on
the same host judges the blind queue through these routes. Spec reference
records are read-only (decided by the spec, never voted on); scaffold
placeholders never enter the ledger. Nothing here leaves the loopback
device: every mutating route requires a local origin, bodies are
size-bounded, and the attestation writes to a fixed dated filename under
docs/evidence (counts plus digest only, never clue text).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from .clue_specimens import (
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
from .private_clue_corpus import load_corpus

specimen_api = Blueprint("specimen_api", __name__)

MAX_BODY_BYTES = 8 * 1024
ATTESTATION_VERSION = "private-clue-specimen-attestation-v1"
ATTESTATION_ENV = "CROSSWORD_SPECIMEN_ATTEST_DIR"

_RECORD_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,120}$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _attest_dir() -> Path:
    override = os.environ.get(ATTESTATION_ENV, "").strip()
    if override:
        return Path(override)
    return _repo_root() / "docs" / "evidence"


def _error(message, status):
    response = jsonify(error=message)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _local_origin():
    origin = request.headers.get("Origin")
    return not origin or origin == request.host_url.rstrip("/")


def _read_body(allowed: set):
    request.max_content_length = MAX_BODY_BYTES
    try:
        raw = request.get_data(cache=True)
    except RequestEntityTooLarge:
        return None, _error("Specimen request is too large", 413)
    if len(raw) > MAX_BODY_BYTES:
        return None, _error("Specimen request is too large", 413)
    if not raw:
        return {}, None
    try:
        value = json.loads(raw)
    except ValueError:
        return None, _error("Specimen request must be valid JSON", 400)
    if not isinstance(value, dict) or set(value) - allowed:
        return None, _error("Specimen request has unexpected fields", 422)
    return value, None


def _ledger_or_missing():
    ledger = load_ledger()
    if ledger.get("corrupt"):
        return None, _error("Specimen ledger is corrupt; restore it before labeling", 500)
    if not ledger["present"]:
        return None, _error("No specimen ledger on this host yet; seed it first", 404)
    return ledger["records"], None


def _summary(records):
    counts: dict = {}
    unlabeled = 0
    blind = 0
    blind_unlabeled = 0
    for record in records:
        verdict = record.get("verdict") if isinstance(record, dict) else None
        is_blind = not isinstance(record, dict) or record.get("origin") != "spec"
        if is_blind:
            blind += 1
        if verdict is None:
            unlabeled += 1
            if is_blind:
                blind_unlabeled += 1
        else:
            counts[verdict] = counts.get(verdict, 0) + 1
    return {
        "records": len(records),
        "reference": len(records) - blind,
        "blind": blind,
        "blindLabeled": blind - blind_unlabeled,
        "blindUnlabeled": blind_unlabeled,
        "labeled": sum(counts.values()),
        "unlabeled": blind_unlabeled,
        "verdictCounts": dict(sorted(counts.items())),
        "problems": validate_ledger(records),
    }


@specimen_api.get("/api/future/specimens")
def list_specimens():
    """Read the local ledger with its labeling progress."""
    records, error = _ledger_or_missing()
    if error is not None:
        return error
    return jsonify(
        {
            "version": SPECIMEN_VERSION,
            "verdicts": list(VERDICTS),
            "records": records,
            "summary": _summary(records),
        }
    )


@specimen_api.get("/api/future/specimens/status")
def specimen_status():
    """Labeling progress without the answer-bearing records."""
    records, error = _ledger_or_missing()
    if error is not None:
        return error
    return jsonify({"version": SPECIMEN_VERSION, "summary": _summary(records)})


@specimen_api.post("/api/future/specimens/seed")
def seed_specimens():
    """Build the ledger: spec reference plus the blind queue."""
    if not _local_origin():
        return _error("Cross-origin specimen writes are not allowed", 403)
    body, error = _read_body({"corpusN", "harvestN", "force"})
    if error is not None:
        return error
    corpus_n = body.get("corpusN", 48)
    if not isinstance(corpus_n, int) or not 0 <= corpus_n <= 200:
        return None, _error("corpusN must be an integer 0-200", 422)
    harvest_n = body.get("harvestN", 48)
    if not isinstance(harvest_n, int) or not 0 <= harvest_n <= 200:
        return None, _error("harvestN must be an integer 0-200", 422)
    target = ledger_path()
    if target.is_file() and body.get("force") is not True:
        return _error("Specimen ledger exists; pass force true to rebuild", 409)
    corpus = load_corpus()
    harvest = load_harvest()
    records, report = seed_records(
        corpus_n, corpus.get("records") or [], harvest.get("records") or [], harvest_n
    )
    save_ledger(records, target)
    summary = _summary(records)
    summary["seed"] = report
    return jsonify({"version": SPECIMEN_VERSION, "summary": summary})


@specimen_api.post("/api/future/specimens/<record_id>/verdict")
def record_verdict(record_id):
    """Record one closed verdict for one blind ledger record."""
    if not _local_origin():
        return _error("Cross-origin specimen writes are not allowed", 403)
    if not _RECORD_ID.fullmatch(record_id or ""):
        return _error("Invalid specimen id", 400)
    body, error = _read_body({"verdict", "note"})
    if error is not None:
        return error
    verdict = body.get("verdict")
    if verdict not in VERDICTS:
        return _error(f"verdict must be one of {list(VERDICTS)}", 422)
    note = body.get("note")
    if note is not None and (not isinstance(note, str) or len(note) > 280):
        return _error("note must be at most 280 characters", 422)
    records, load_error = _ledger_or_missing()
    if load_error is not None:
        return load_error
    for record in records:
        if record.get("id") == record_id:
            if record.get("origin") == "spec":
                return _error(
                    "Reference records are decided by the spec; judge the blind queue",
                    422,
                )
            record["verdict"] = verdict
            record["note"] = note if isinstance(note, str) and note else record.get("note")
            record["labeledAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            save_ledger(records)
            return jsonify({"id": record_id, "verdict": verdict, "summary": _summary(records)})
    return _error(f"no specimen {record_id!r} in the ledger", 404)


@specimen_api.post("/api/future/specimens/pairs")
def link_pair():
    """Link two records for better-of-pair judging."""
    if not _local_origin():
        return _error("Cross-origin specimen writes are not allowed", 403)
    body, error = _read_body({"a", "b"})
    if error is not None:
        return error
    first, second = body.get("a"), body.get("b")
    if not _RECORD_ID.fullmatch(first or "") or not _RECORD_ID.fullmatch(second or ""):
        return _error("pair members must be valid specimen ids", 422)
    if first == second:
        return _error("pair members must differ", 422)
    records, load_error = _ledger_or_missing()
    if load_error is not None:
        return load_error
    found = {record.get("id"): record for record in records}
    if first not in found or second not in found:
        return _error("both pair members must exist in the ledger", 404)
    if found[first].get("origin") == "spec" or found[second].get("origin") == "spec":
        return _error("reference records keep their spec pairs; link blind records", 422)
    pair_id = f"pair-{first}-{second}"
    for record in records:
        if record.get("id") in (first, second):
            record["pairId"] = pair_id
    save_ledger(records)
    return jsonify({"pairId": pair_id, "members": [first, second], "summary": _summary(records)})


@specimen_api.post("/api/future/specimens/attest")
def attest_specimens():
    """Validate the closed blind queue and write the committed attestation."""
    if not _local_origin():
        return _error("Cross-origin specimen writes are not allowed", 403)
    body, error = _read_body(set())
    if error is not None:
        return error
    records, load_error = _ledger_or_missing()
    if load_error is not None:
        return load_error
    blind = [record for record in records if record.get("origin") != "spec"]
    if not blind:
        return (
            jsonify(
                {
                    "attested": False,
                    "error": "no blind queue; seed real surfaces first",
                    "problems": [],
                    "unlabeled": 0,
                    "summary": _summary(records),
                }
            ),
            422,
        )
    problems = validate_ledger(records)
    attestation = ledger_attestation(records)
    if problems or attestation["blindUnlabeled"]:
        return (
            jsonify(
                {
                    "attested": False,
                    "problems": problems,
                    "unlabeled": attestation["blindUnlabeled"],
                    "summary": _summary(records),
                }
            ),
            422,
        )
    stamped = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = _attest_dir() / f"{ATTESTATION_VERSION}.{stamped}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
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
                    "verdicts judge the clue/answer relation, not semantic truth",
                    "reference verdicts are spec-defined worked examples, not independent judgment",
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return jsonify(
        {
            "attested": True,
            "out": out.name,
            "pairs": attestation["pairs"],
            "digest": attestation["digest"],
            "summary": _summary(records),
        }
    )
