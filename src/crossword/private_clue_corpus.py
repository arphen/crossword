"""Local answer-bearing clue corpus for private generation.

Every study receipt in ``docs/evidence/`` carries counters only — no clue
text — so no guard or scorer can be re-examined against the case that
produced it. This module captures every clue surface a generation produces
into a local corpus that lives OUTSIDE the evidence tree and is never
committed (see ``.gitignore`` for ``*.local.json``).

Each record carries the clue, the answer, and which deterministic guard
admitted or rejected it, so Q04/Q05/Q07 claims have a denominator. The
committed artifact is only counts plus a digest (see
``scripts/private-clue-corpus.py``).

All entry points are fail-open: corpus capture must never break or delay a
private puzzle. Any I/O or shape problem returns a receipt with ``appended``
0 and an ``error`` string instead of raising.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

CORPUS_VERSION = "private-clue-corpus-v1"
CORPUS_FILENAME = "private-clue-corpus-v1.local.json"
CORPUS_ENV = "CROSSWORD_CLUE_CORPUS_PATH"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def corpus_path() -> Path:
    """Local corpus location; override with CROSSWORD_CLUE_CORPUS_PATH in tests."""
    override = os.environ.get(CORPUS_ENV, "").strip()
    if override:
        return Path(override)
    return _repo_root() / "docs" / "evidence" / CORPUS_FILENAME


def _text(value) -> str:
    return value if isinstance(value, str) else ""


def _string_list(value) -> list:
    if not isinstance(value, (list, tuple)):
        return []
    return sorted({item for item in value if isinstance(item, str) and item})


def build_corpus_records(
    entries,
    clues,
    *,
    weekday,
    seed,
    model_tag,
    issues_by_id=None,
    fallback_ids=(),
    reviewed_ids=(),
    challenge_by_id=None,
):
    """Build one answer-bearing record per entry.

    ``issues_by_id`` maps entry id to the deterministic issue codes observed
    for its final surface (empty means every deterministic guard admitted
    it). ``fallback_ids`` holds entries served the answer-free crossing
    scaffold; ``reviewed_ids`` holds entries preserved verbatim from the
    reviewed pack. ``challenge_by_id`` maps entry id to the challenger
    classification (``safe-fallback`` / ``needs-review`` /
    ``mechanically-supported``) where one ran.
    """
    issues = issues_by_id if isinstance(issues_by_id, dict) else {}
    challenges = challenge_by_id if isinstance(challenge_by_id, dict) else {}
    fallback = set(fallback_ids or ())
    reviewed = set(reviewed_ids or ())
    records = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            continue
        clue = clues.get(entry_id) if isinstance(clues, dict) else ""
        challenge = challenges.get(entry_id)
        records.append(
            {
                "id": entry_id,
                "answer": _text(entry.get("answer")),
                "clue": _text(clue),
                "weekday": _text(weekday),
                "seed": seed if isinstance(seed, int) else None,
                "modelTag": _text(model_tag),
                "theme": entry.get("theme") is True,
                "cluePolicy": _text(entry.get("cluePolicy")),
                "issues": _string_list(issues.get(entry_id)),
                "fallback": entry_id in fallback,
                "reviewed": entry_id in reviewed,
                "challenge": challenge if isinstance(challenge, str) else None,
                "recordedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )
    records.sort(key=lambda item: item["id"])
    return records


def _payload_digest(payload) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return "sha256-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_corpus(path=None) -> dict:
    """Load the local corpus; a missing file is an empty corpus, not an error."""
    target = Path(path) if path is not None else corpus_path()
    if not target.is_file():
        return {"version": CORPUS_VERSION, "records": [], "captured": False}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": CORPUS_VERSION, "records": [], "captured": False, "corrupt": True}
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        return {"version": CORPUS_VERSION, "records": [], "captured": False, "corrupt": True}
    return {"version": CORPUS_VERSION, "records": records, "captured": True}


def append_corpus_records(records, path=None) -> dict:
    """Append records to the local corpus. Never raises; fails open."""
    try:
        target = Path(path) if path is not None else corpus_path()
        records = [item for item in (records or []) if isinstance(item, dict)]
        if target.is_file():
            try:
                payload = json.loads(target.read_text(encoding="utf-8"))
                existing = payload.get("records")
                existing = existing if isinstance(existing, list) else []
            except (OSError, ValueError):
                existing = []
        else:
            existing = []
        combined = [*existing, *records]
        payload = {"version": CORPUS_VERSION, "records": combined}
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
        return {
            "appended": len(records),
            "totalPairs": len(combined),
            "digest": _payload_digest(payload),
            "version": CORPUS_VERSION,
        }
    except (OSError, ValueError, TypeError) as error:
        return {"appended": 0, "totalPairs": None, "digest": None, "error": str(error)}


def corpus_counts_attestation(path=None) -> dict:
    """Answer-free counts plus digest for the committed attestation."""
    corpus = load_corpus(path)
    records = corpus["records"]
    return {
        "version": CORPUS_VERSION,
        "captured": corpus["captured"],
        "pairs": len(records),
        "digest": _payload_digest({"version": CORPUS_VERSION, "records": records})
        if corpus["captured"]
        else None,
        "weeks": sorted({item.get("weekday") for item in records if isinstance(item.get("weekday"), str)}),
        "models": sorted({item.get("modelTag") for item in records if isinstance(item.get("modelTag"), str)}),
        "withIssues": sum(1 for item in records if item.get("issues")),
        "fallbacks": sum(1 for item in records if item.get("fallback") is True),
        "reviewed": sum(1 for item in records if item.get("reviewed") is True),
    }


def reresolve_counters(artifacts) -> dict:
    """Re-aggregate surviving counters from existing study artifacts.

    ``artifacts`` is a sequence of ``(name, digest, payload)`` triples. Only
    counters are summed — the artifacts carry no clue text, so this is all
    the surviving evidence permits. It is what surfaced the ``fill-blank:
    57 of 74`` finding, and it cannot say anything about clue quality.
    """
    family_totals: dict = {}
    signal_totals: dict = {}
    issue_totals: dict = {}
    files = []
    max_fill_blank = None
    for name, digest, payload in artifacts:
        entry = {"name": name, "digest": digest}
        sources = []
        if isinstance(payload, dict):
            summary = payload.get("summary")
            if isinstance(summary, dict) and isinstance(
                summary.get("familyCounts"), dict
            ):
                # The summary already aggregates the cases; prefer it so
                # boards are not counted twice.
                sources.append(("summary", summary))
            else:
                cases = payload.get("cases")
                if isinstance(cases, list):
                    for index, case in enumerate(cases):
                        if isinstance(case, dict) and isinstance(
                            case.get("familyCounts"), dict
                        ):
                            sources.append((f"cases[{index}]", case))
                if not sources and isinstance(payload.get("familyCounts"), dict):
                    sources.append(("top", payload))
        if not sources:
            entry["note"] = "no familyCounts; counters not re-resolvable"
        for scope, source in sources:
            counts = source.get("familyCounts")
            for family, total in counts.items():
                if isinstance(family, str) and isinstance(total, (int, float)):
                    family_totals[family] = family_totals.get(family, 0) + total
            entry.setdefault("scopes", []).append(scope)
            entry.setdefault("families", [])
            for family in counts:
                if family not in entry["families"]:
                    entry["families"].append(family)
            entry["families"].sort()
            entry_count = source.get("entryCount")
            if isinstance(entry_count, (int, float)) and entry_count > 0:
                share = (counts.get("fill-blank") or 0) / entry_count
                entry["entryCount"] = entry.get("entryCount", 0) + entry_count
                if max_fill_blank is None or share > max_fill_blank["share"]:
                    max_fill_blank = {
                        "name": f"{name}#{scope}",
                        "share": round(share, 4),
                        "fillBlank": counts.get("fill-blank"),
                        "entryCount": entry_count,
                    }
        for key, totals in (
            ("signalCounts", signal_totals),
            ("issueCounts", issue_totals),
        ):
            for scope, source in sources:
                values = source.get(key)
                if isinstance(values, dict):
                    for label, total in values.items():
                        if isinstance(label, str) and isinstance(total, (int, float)):
                            totals[label] = totals.get(label, 0) + total
        files.append(entry)
    return {
        "version": "private-clue-counter-reresolution-v1",
        "files": files,
        "familyTotals": dict(sorted(family_totals.items())),
        "signalTotals": dict(sorted(signal_totals.items())),
        "issueTotals": dict(sorted(issue_totals.items())),
        "maxFillBlankShare": max_fill_blank,
    }
