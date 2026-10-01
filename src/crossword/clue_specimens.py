"""Closed specimen ledger for clue verdicts (Q02).

Measurement needs a denominator no code can produce: human verdicts on
real clue/answer pairs whose answers the operator cannot know in advance.
The ledger therefore separates three classes:

- ``spec`` reference: the 14 hand-listed §0 surfaces, pre-labeled by the
  spec itself. They are worked examples, never judging work; the operator
  does not vote on them and they are reported as calibration, not blind
  agreement.
- ``blind`` queue: real model surfaces the operator judges without hints.
  Only these attest the ledger and only these score rule agreement.
- scaffold: ``Entry supported by its crossings`` placeholders are detected
  deterministically and never queued — no human labels what code can see.

The ledger is answer-bearing and lives outside the evidence tree at
``private-clue-specimens-v1.local.json`` (repo root, gitignored, never
committed). Only counts plus a digest are committed, via
``scripts/private-clue-specimen-label.py attest``. Later claims (Q01/Q03/Q04
rules, candidate comparisons) report agreement or disagreement against the
blind ids and verdicts.
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

REAL_VERSION = "private-clue-real-v1"
REAL_FILENAME = "private-clue-real-v1.local.json"
REAL_ENV = "CROSSWORD_CLUE_REAL_PATH"


def real_path() -> Path:
    """Local harvest location; override with CROSSWORD_CLUE_REAL_PATH in tests."""
    override = os.environ.get(REAL_ENV, "").strip()
    if override:
        return Path(override)
    return _repo_root() / REAL_FILENAME


def load_harvest(path=None) -> dict:
    """Load the local real-surface harvest; missing file is empty, not error."""
    target = Path(path) if path is not None else real_path()
    if not target.is_file():
        return {"version": REAL_VERSION, "records": [], "present": False}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": REAL_VERSION, "records": [], "present": False, "corrupt": True}
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        return {"version": REAL_VERSION, "records": [], "present": False, "corrupt": True}
    return {"version": REAL_VERSION, "records": records, "present": True}

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

HAND_LISTED_PAIR_ID = "pair-bright-1"
HAND_LISTED_PAIR_MEMBERS = ("sp-pair-bright-a", "sp-pair-bright-b")

# Definitional verdicts for the hand-listed §0 surfaces. These are set by
# the spec, not by vote: each note already states the category. The
# operator's independent judgment applies only to the blind queue.
SPEC_VERDICTS = {
    "sp-tautology-shadier": "tautology",
    "sp-leak-shady": "leak",
    "sp-pun-auctioneer": "acceptable",
    "sp-pun-teller": "acceptable",
    "sp-pseudo-den": "pseudo-pun",
    "sp-name-singer": "name-slot",
    "sp-name-writer": "name-slot",
    "sp-fill-voyage": "acceptable",
    "sp-spoken-greeting": "acceptable",
    "sp-spoken-bare": "acceptable",
    "sp-plain-dark": "acceptable",
    "sp-plain-are": "acceptable",
    "sp-pair-bright-a": "tautology",
    "sp-pair-bright-b": "better-of-pair",
}

SCAFFOLD_PREFIX = "Entry supported by its crossings"


def is_scaffold_surface(clue) -> bool:
    """Detect the answer-free crossing scaffold deterministically.

    No human verdict is spent on what a string match can see.
    """
    return isinstance(clue, str) and clue.startswith(SCAFFOLD_PREFIX)


def _seeded_at() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(answer, index) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(answer))
    cleaned = "-".join(part for part in cleaned.split("-") if part)[:40]
    return f"real-{cleaned or 'entry'}-{index}"


def seed_records(corpus_n=48, corpus_records=None, harvest_records=None, harvest_n=48):
    """Build the ledger: spec reference plus the blind queue.

    Returns ``(records, report)``. Hand-listed §0 surfaces arrive
    pre-labeled with their definitional verdicts (origin ``spec``).
    Corpus records that are scaffold placeholders are skipped and counted,
    never queued. Real harvest surfaces seed blind singles, or blind
    same-answer pairs when both arms produced a distinct real surface.
    """
    records = []
    for record_id, answer, clue, note in HAND_LISTED:
        record = make_record(
            record_id, answer, clue, source="hand-listed §0", note=note, origin="spec"
        )
        if record_id in HAND_LISTED_PAIR_MEMBERS:
            record["pairId"] = HAND_LISTED_PAIR_ID
        record["verdict"] = SPEC_VERDICTS[record_id]
        record["labeledAt"] = _seeded_at()
        records.append(record)

    scaffold_skipped = 0
    corpus_sampled = 0
    for record in corpus_records or []:
        if corpus_sampled >= corpus_n or not isinstance(record, dict):
            continue
        answer, clue = record.get("answer"), record.get("clue")
        if not answer or not clue:
            continue
        if is_scaffold_surface(clue):
            scaffold_skipped += 1
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
                origin="blind",
            )
        )
        corpus_sampled += 1

    harvest_singles = 0
    harvest_pairs = 0
    by_answer: dict = {}
    for record in harvest_records or []:
        if not isinstance(record, dict):
            continue
        answer, clue = record.get("answer"), record.get("clue")
        if not answer or not clue or is_scaffold_surface(clue):
            continue
        by_answer.setdefault(str(answer), []).append(record)
    index = 0
    for answer in sorted(by_answer):
        if harvest_singles + harvest_pairs * 2 >= harvest_n:
            break
        surfaces = []
        seen = set()
        for record in by_answer[answer]:
            clue = record.get("clue")
            if clue in seen:
                continue
            seen.add(clue)
            surfaces.append(record)
        if len(surfaces) >= 2 and harvest_singles + harvest_pairs * 2 + 2 <= harvest_n:
            pair_id = f"pair-real-{_slug(answer, index)}"
            for surface in surfaces[:2]:
                records.append(
                    make_record(
                        f"{_slug(answer, index)}-{surface.get('arm', 'x')}",
                        answer,
                        surface.get("clue"),
                        source="real-harvest",
                        weekday=surface.get("weekday"),
                        model_tag=surface.get("modelTag"),
                        pair_id=pair_id,
                        note=f"arm {surface.get('arm')}; pick the better with Pair winner",
                        origin="blind",
                    )
                )
            harvest_pairs += 1
        elif surfaces:
            surface = surfaces[0]
            records.append(
                make_record(
                    f"{_slug(answer, index)}-{surface.get('arm', 'x')}",
                    answer,
                    surface.get("clue"),
                    source="real-harvest",
                    weekday=surface.get("weekday"),
                    model_tag=surface.get("modelTag"),
                    origin="blind",
                )
            )
            harvest_singles += 1
        index += 1

    report = {
        "records": len(records),
        "reference": sum(1 for r in records if r.get("origin") == "spec"),
        "blind": sum(1 for r in records if r.get("origin") != "spec"),
        "handListed": sum(1 for r in records if r["source"].startswith("hand-listed")),
        "corpusSampled": corpus_sampled,
        "scaffoldSkipped": scaffold_skipped,
        "harvestSingles": harvest_singles,
        "harvestPairs": harvest_pairs,
    }
    return records, report

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
    origin="blind",
    verdict=None,
) -> dict:
    """Build one ledger record.

    ``origin`` is ``spec`` for spec-defined reference (pre-labeled, never
    judged) or ``blind`` for genuine unknowns the operator judges. Blind
    records start unlabeled; the operator supplies the verdict.
    """
    if verdict is not None and verdict not in VERDICTS:
        raise ValueError(f"verdict {verdict!r} outside {list(VERDICTS)}")
    return {
        "id": _text(record_id),
        "answer": _text(answer),
        "clue": _text(clue),
        "weekday": _text(weekday) or None,
        "seed": seed if isinstance(seed, int) else None,
        "modelTag": _text(model_tag) or None,
        "source": _text(source) or "hand-listed",
        "origin": "spec" if origin == "spec" else "blind",
        "verdict": verdict,
        "pairId": _text(pair_id) or None,
        "note": _text(note) or None,
        "labeledAt": _seeded_at() if verdict is not None else None,
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
    origins: dict = {}
    unlabeled = 0
    blind_unlabeled = 0
    for record in records or []:
        if not isinstance(record, dict):
            continue
        verdict = record.get("verdict")
        origin = record.get("origin") or "unmarked"
        if verdict is None:
            unlabeled += 1
            if origin != "spec":
                blind_unlabeled += 1
        else:
            counts[verdict] = counts.get(verdict, 0) + 1
            origins[origin] = origins.get(origin, 0) + 1
    return {
        "version": SPECIMEN_VERSION,
        "pairs": len(records or []),
        "labeled": sum(counts.values()),
        "unlabeled": unlabeled,
        "blindUnlabeled": blind_unlabeled,
        "verdictCounts": dict(sorted(counts.items())),
        "origins": dict(sorted(origins.items())),
        "digest": _canonical_digest(list(records or [])),
    }


def agreement_report(records, judgments) -> dict:
    """Score rule judgments against ledger verdicts, by stable id.

    ``judgments`` maps record id to a claimed verdict string. Returns
    agreement counts plus per-id disagreements, so later claims (leak gate,
    witness admission, candidate comparison) report against the ledger
    instead of redefining it. ``byOrigin`` splits spec calibration from
    blind operator verdicts: only the blind split measures rules against
    independent human judgment.
    """
    ledger = {
        record["id"]: (record.get("verdict"), record.get("origin") or "unmarked")
        for record in (records or [])
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }
    agreed = 0
    disagreements = []
    unknown = 0
    by_origin: dict = {}

    def _bucket(origin):
        return by_origin.setdefault(
            origin, {"scored": 0, "agreed": 0, "disagreed": 0, "agreementRate": 0.0}
        )

    for record_id, claimed in (judgments or {}).items():
        expected, origin = ledger.get(record_id, (None, None))
        if expected is None:
            unknown += 1
        elif claimed == expected:
            agreed += 1
            slot = _bucket(origin)
            slot["scored"] += 1
            slot["agreed"] += 1
        else:
            disagreements.append(
                {"id": record_id, "expected": expected, "claimed": claimed}
            )
            slot = _bucket(origin)
            slot["scored"] += 1
            slot["disagreed"] += 1
    for slot in by_origin.values():
        if slot["scored"]:
            slot["agreementRate"] = round(slot["agreed"] / slot["scored"], 4)
    scored = agreed + len(disagreements)
    return {
        "scored": scored,
        "agreed": agreed,
        "disagreed": len(disagreements),
        "unknownIds": unknown,
        "agreementRate": round(agreed / scored, 4) if scored else 0.0,
        "byOrigin": {key: by_origin[key] for key in sorted(by_origin)},
        "disagreements": sorted(disagreements, key=lambda item: item["id"]),
    }
