"""Capability-scoped immutable solve-event journal for personal sessions.

The daily crossword routes do not use this API. A random per-session writer
capability authorizes one browser journal to append a bounded sequence; event
IDs and sequence numbers make retries safe after a lost response.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
import unicodedata
from uuid import NAMESPACE_URL, UUID, uuid5

from flask import Blueprint, jsonify, request
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import RequestEntityTooLarge

from .database import db
from .future import StartingProfile
from .episteme_store import (
    EpistemeCommandRejected,
    EpistemeRevisionConflict,
    EpistemeRuntimeUnavailable,
    apply_episteme_command,
    get_or_create_episteme_profile,
    now_utc_iso,
)
from .future_puzzles import FuturePuzzleManifestRecord, FutureSolveAnalysisRecord
from .language_signals import has_explicit_language_signal
from .language_task_pack import task_pair_for_review
from .legacy_manifest import verify_integrity
from .solve_replay import (
    SolveReplayRejected,
    SolveReplayUnavailable,
    analyze_solve_session,
)

session_journal_api = Blueprint("session_journal_api", __name__)

MAX_BODY_BYTES = 256 * 1024
MAX_EVENTS = 200
MAX_CELLS = 400
MAX_SESSION_EVENTS = 50_000
_HEX_256 = re.compile(r"^[0-9a-f]{64}$")
_ISO_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$"
)
_PRIVATE_LANGUAGE_THREAD = re.compile(r"\blanguage thread:\s*([A-Za-z]+)\b", re.IGNORECASE)
_LANGUAGE_CODES = {
    "french": "fr",
    "german": "de",
    "spanish": "es",
    "italian": "it",
    "portuguese": "pt",
    "japanese": "ja",
    "dutch": "nl",
}
_ANNOTATED_SPOKEN_SURFACE = re.compile(
    r'^[\"“\'‘].+[\"”\'’]\s*[\[(]\s*(?:spoken(?:\s+equivalent)?|utterance|said\s+aloud)\s*[\])]$',
    re.IGNORECASE,
)


def _private_surface_clue_family(clue):
    """Classify only visible clue conventions for local fatigue accounting.

    This deliberately mirrors the private observer's surface boundary rather
    than claiming that a clue really means a particular thing. The value is
    stored beside the historical task family so older evidence remains
    readable and language recurrence stays its own explicit lane.
    """
    text = clue.strip() if isinstance(clue, str) else ""
    if len(text) >= 2 and text[0] in {'"', "“", "'", "‘"} and text[-1] in {
        '"', "”", "'", "’"
    }:
        return "spoken-equivalent"
    if _ANNOTATED_SPOKEN_SURFACE.fullmatch(text):
        return "spoken-equivalent"
    if re.search(r"(?:_{2,}|\b(?:and|or|to|of)\s+___\b)", text, re.IGNORECASE):
        return "fill-blank"
    if re.search(r"(?:\[\s*abbr\.?\s*\]|\(\s*abbr\.?\s*\)|\bbriefly\b)", text, re.IGNORECASE):
        return "metalinguistic"
    if (
        text.startswith("[")
        and text.endswith("]")
        and not re.fullmatch(r"\[\s*(?:pl|plural)\.?\s*\]", text, re.IGNORECASE)
    ):
        return "nonverbal-expression"
    if text.endswith("?"):
        return "pun"
    return "definition"


class PersonalSolveSession(db.Model):
    __tablename__ = "future_solve_sessions"

    id = db.Column(db.String(36), primary_key=True)
    profile_id = db.Column(db.String(36), nullable=False, index=True)
    puzzle_hash = db.Column(db.String(64), nullable=False)
    initial_grid = db.Column(db.JSON, nullable=False)
    writer_digest = db.Column(db.String(64), nullable=False)
    accepted_seq = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(16), nullable=False, default="active")
    created_at = db.Column(db.String(40), nullable=False)
    updated_at = db.Column(db.String(40), nullable=False)


class PersonalSolveEvent(db.Model):
    __tablename__ = "future_solve_events"
    __table_args__ = (
        db.UniqueConstraint("session_id", "seq", name="uq_future_solve_event_seq"),
        db.UniqueConstraint("event_id", name="uq_future_solve_event_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    seq = db.Column(db.Integer, nullable=False)
    event_id = db.Column(db.String(36), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    payload_hash = db.Column(db.String(64), nullable=False)
    recorded_at = db.Column(db.String(40), nullable=False)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _canonical_uuid(value):
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _origin_is_local():
    origin = request.headers.get("Origin")
    return not origin or origin == request.host_url.rstrip("/")


def _error(message, status, *, retryable=False):
    response = jsonify(error=message, **({"retryable": True} if retryable else {}))
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _bounded_json_body(message):
    request.max_content_length = MAX_BODY_BYTES
    try:
        body = request.get_data(cache=True)
    except RequestEntityTooLarge:
        return None, _error(message, 413)
    if len(body) > MAX_BODY_BYTES:
        return None, _error(message, 413)
    return request.get_json(silent=True), None


def _uuid_list(value, *, maximum, label):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"Invalid {label}")
    if any(not _canonical_uuid(item) for item in value):
        raise ValueError(f"Invalid {label}")
    if len(set(value)) != len(value):
        raise ValueError(f"Duplicate {label}")
    return value


def _token(value, *, nullable):
    if value is None and nullable:
        return True
    return (
        isinstance(value, str)
        and 0 < len(value) <= 24
        and value.strip() == value
        and value == unicodedata.normalize("NFC", value)
    )


def _normalized_token(value):
    return unicodedata.normalize("NFC", value).upper()


def _cell_id(value, cell_ids):
    return isinstance(value, str) and value in cell_ids


def _is_iso_datetime(value):
    if (
        not isinstance(value, str)
        or len(value) > 40
        or not _ISO_TIMESTAMP.fullmatch(value)
    ):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _validate_initial_grid(value):
    if not isinstance(value, list) or len(value) > MAX_CELLS:
        raise ValueError("Invalid initial grid")
    ids = set()
    for cell in value:
        if not isinstance(cell, dict) or set(cell) != {"cellId", "token", "origin"}:
            raise ValueError("Invalid initial grid cell")
        cell_id = cell["cellId"]
        if (
            not isinstance(cell_id, str)
            or not 1 <= len(cell_id) <= 160
            or cell_id in ids
        ):
            raise ValueError("Invalid or duplicate initial grid cell id")
        if not _token(cell["token"], nullable=True) or cell["origin"] != "unknown":
            raise ValueError("Initial grid tokens must have unknown provenance")
        ids.add(cell_id)
    return ids


_COMMON = {
    "schemaVersion",
    "eventId",
    "sessionId",
    "segmentId",
    "seq",
    "elapsedMs",
    "recordedAt",
    "puzzleHash",
    "type",
}
_PAYLOAD_FIELDS = {
    "session-started": {"reason"},
    "session-resumed": {"reason", "snapshotSeq"},
    "session-finished": {"reason"},
    "visibility-changed": {"visibility"},
    "paused": {"reason"},
    "resumed": {"reason"},
    "entry-focused": {"entryId", "variantId", "reason", "visiblePattern"},
    "cell-written": {
        "cellId",
        "beforeToken",
        "afterToken",
        "activeEntryId",
        "actionId",
        "source",
    },
    "cell-cleared": {"cellId", "beforeToken", "activeEntryId", "actionId", "source"},
    "batch-entered": {"activeEntryId", "actionId", "source", "edits"},
    "check-result-shown": {"scope", "entryId", "results"},
    "answer-revealed": {"scope", "entryId", "cells"},
    "hint-shown": {"entryId", "hintId", "assistanceTier", "affectedCellIds"},
}


def _manifest_indexes(manifest):
    if not verify_integrity(manifest):
        raise ValueError("Puzzle manifest integrity check failed")
    cells = manifest.get("cells")
    entries = manifest.get("entries")
    if not isinstance(cells, list) or not isinstance(entries, list):
        raise ValueError("Puzzle manifest is incomplete")
    open_cell_ids = []
    for cell in cells:
        if not isinstance(cell, dict) or not isinstance(cell.get("id"), str):
            raise ValueError("Puzzle manifest contains an invalid cell")
        if cell.get("block") is False:
            open_cell_ids.append(cell["id"])
    entry_cells = {}
    answers_by_cell = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError("Puzzle manifest contains an invalid entry")
        cell_ids = entry.get("cellIds")
        answer = entry.get("answer")
        if not isinstance(cell_ids, list) or not isinstance(answer, str):
            raise ValueError("Puzzle manifest entry is incomplete")
        declared_tokens = entry.get("answerTokens")
        if declared_tokens is not None:
            if (
                not isinstance(declared_tokens, list)
                or any(
                    not isinstance(token, str)
                    or not token
                    or not re.fullmatch(r"[A-Z]{1,8}", token)
                    for token in declared_tokens
                )
            ):
                raise ValueError("Puzzle manifest entry has invalid answer tokens")
            tokens = declared_tokens
        else:
            tokens = list(answer)
        if len(tokens) != len(cell_ids) or entry["id"] in entry_cells:
            raise ValueError("Puzzle manifest entry has invalid answer coverage")
        entry_cells[entry["id"]] = cell_ids
        for cell_id, token in zip(cell_ids, tokens, strict=True):
            previous = answers_by_cell.setdefault(cell_id, token)
            if previous != token:
                raise ValueError("Puzzle manifest crossing answers disagree")
    if set(answers_by_cell) != set(open_cell_ids):
        raise ValueError("Puzzle manifest entries do not cover its open cells")
    return open_cell_ids, entry_cells, answers_by_cell


def _private_task_links(manifest, analysis):
    """Link local generated answer forms as exposure-only profile evidence."""
    metadata = manifest.get("metadata") if isinstance(manifest, dict) else None
    notepad = metadata.get("notepad") if isinstance(metadata, dict) else None
    if not isinstance(notepad, str) and isinstance(manifest, dict):
        # The legacy manifest keeps the source notepad as its subtitle rather
        # than copying the parser's metadata object into the public document.
        notepad = manifest.get("subtitle")
    if not isinstance(notepad, str) or not notepad.startswith(
        "Private local generation"
    ):
        return []
    entries = manifest.get("entries") if isinstance(manifest, dict) else None
    observations = analysis.get("observations") if isinstance(analysis, dict) else None
    if not isinstance(entries, list) or not isinstance(observations, list):
        return []
    language_name = None
    language_code = None
    if isinstance(notepad, str):
        language_match = _PRIVATE_LANGUAGE_THREAD.search(notepad)
        language_name = language_match.group(1) if language_match else None
        language_code = _LANGUAGE_CODES.get(language_name.casefold()) if language_name else None
    by_id = {
        entry.get("id"): entry
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    links = []
    for observation in observations:
        entry_id = observation.get("entryId") if isinstance(observation, dict) else None
        entry = by_id.get(entry_id)
        answer = entry.get("answer") if isinstance(entry, dict) else None
        if not isinstance(entry_id, str) or not isinstance(answer, str) or not answer:
            continue
        clue = entry.get("clue") if isinstance(entry, dict) else None
        clue_language = language_code if (
            isinstance(clue, str)
            and language_name
            and has_explicit_language_signal(clue, language_name)
        ) else "en"
        is_language_task = clue_language != "en"
        task = {
            "taskId": f"private-answer-form:{answer}",
            "taskKind": "answer-form",
            "direction": "clue-to-answer",
            "language": clue_language,
            "clueFamily": (
                "language-recurrence" if is_language_task else "private-local-generated"
            ),
            # Literal surface observation for reversible rotation hints. Keep
            # it separate from clueFamily, which identifies the learning lane.
            "surfaceFamily": (
                "language-recurrence"
                if is_language_task
                else _private_surface_clue_family(clue)
            ),
            "contentReview": "unreviewed",
        }
        if is_language_task:
            task_pack = task_pair_for_review(clue_language, answer)
            if isinstance(task_pack, dict):
                # This projection deliberately omits targetText. The answer
                # remains behind the opaque task handle in delayed review;
                # source identity and semantic/admission status survive.
                task["taskPack"] = task_pack
        links.append({"entryId": entry_id, "tasks": [task]})
    return links


def _record_final_analysis(profile_id, session_id, analysis, finished_at, manifest):
    """Link one host-replayed analysis to the profile's evidence ledger."""
    profile_record = get_or_create_episteme_profile(profile_id, now_utc_iso())
    evidence = {
        "evidenceId": f"session-analysis:{session_id}:v1",
        "recordedAt": finished_at,
        "type": "session-analysis",
        "analysis": analysis,
        # Local generated answers are exposure-only until a reviewed content
        # record exists. The reducer therefore retains the history without
        # turning a typed or revealed answer into a mastery claim.
        "taskLinks": _private_task_links(manifest, analysis),
    }
    command = {
        "updateId": str(
            uuid5(NAMESPACE_URL, f"crossword-session-analysis:{session_id}:v1")
        ),
        "profileId": profile_id,
        "baseRevision": profile_record.revision,
        "recordedAt": finished_at,
        "evidence": [evidence],
        "evidenceActions": [],
    }
    return apply_episteme_command(
        profile_id,
        profile_record.revision,
        profile_record.profile_json,
        command,
    )


def _validate_event(
    value, session_id, profile_id, puzzle_hash, cell_ids, entry_cells, answers_by_cell
):
    if not isinstance(value, dict):
        raise ValueError("Event must be an object")
    event_type = value.get("type")
    fields = _PAYLOAD_FIELDS.get(event_type)
    allowed = _COMMON | {"profileId"} | (fields or set())
    required = _COMMON | fields if fields else _COMMON
    if not fields or set(value) - allowed or not required.issubset(value):
        raise ValueError("Event does not match a supported schema")
    if value.get("schemaVersion") != 2 or not _canonical_uuid(value.get("eventId")):
        raise ValueError("Invalid event identity or version")
    if (
        value.get("sessionId") != session_id
        or value.get("profileId", profile_id) != profile_id
    ):
        raise ValueError("Event session/profile does not match the journal")
    if value.get("puzzleHash") != puzzle_hash or not _HEX_256.fullmatch(puzzle_hash):
        raise ValueError("Event puzzle hash does not match the journal")
    if (
        not isinstance(value.get("segmentId"), str)
        or not 1 <= len(value["segmentId"]) <= 80
    ):
        raise ValueError("Invalid event segment")
    if (
        type(value.get("seq")) is not int
        or not 1 <= value["seq"] <= 9_007_199_254_740_991
    ):
        raise ValueError("Invalid event sequence")
    elapsed = value.get("elapsedMs")
    if (
        isinstance(elapsed, bool)
        or not isinstance(elapsed, (int, float))
        or not 0 <= elapsed <= 86_400_000
    ):
        raise ValueError("Invalid event elapsed time")
    if not _is_iso_datetime(value.get("recordedAt")):
        raise ValueError("Invalid event timestamp")

    if event_type == "session-started" and value.get("reason") != "fresh":
        raise ValueError("Invalid session start reason")
    if event_type == "session-resumed":
        if (
            value.get("reason") not in {"reload", "handoff"}
            or type(value.get("snapshotSeq")) is not int
            or value["snapshotSeq"] < 0
        ):
            raise ValueError("Invalid session resume")
    if event_type == "session-finished" and value.get("reason") not in {
        "complete",
        "stopped",
        "abandoned",
    }:
        raise ValueError("Invalid session finish reason")
    if event_type == "visibility-changed" and value.get("visibility") not in {
        "visible",
        "hidden",
    }:
        raise ValueError("Invalid visibility state")
    if event_type in {"paused", "resumed"} and value.get("reason") not in {
        "user",
        "background",
        "system",
    }:
        raise ValueError("Invalid pause reason")
    if event_type == "entry-focused":
        if (
            not isinstance(value.get("entryId"), str)
            or not 1 <= len(value["entryId"]) <= 160
        ):
            raise ValueError("Invalid focused entry")
        if value.get("variantId") is not None and (
            not isinstance(value["variantId"], str) or len(value["variantId"]) > 160
        ):
            raise ValueError("Invalid clue variant")
        if value.get("reason") not in {"pointer", "keyboard", "programmatic"}:
            raise ValueError("Invalid focus reason")
        pattern = value.get("visiblePattern")
        if not isinstance(pattern, list) or len(pattern) > MAX_CELLS:
            raise ValueError("Invalid visible pattern")
        for item in pattern:
            expected = {"cellId", "token", "origin", "sourceEntryId"}
            if (
                not isinstance(item, dict)
                or set(item) != expected
                or not isinstance(item.get("cellId"), str)
                or not 1 <= len(item["cellId"]) <= 160
            ):
                raise ValueError("Invalid visible pattern cell")
            if not _token(item["token"], nullable=True) or item["origin"] not in {
                "player",
                "crossing",
                "reveal",
                "unknown",
            }:
                raise ValueError("Invalid visible token provenance")
            source = item["sourceEntryId"]
            if source is not None and (
                not isinstance(source, str) or not 1 <= len(source) <= 160
            ):
                raise ValueError("Invalid crossing source")
            if (item["origin"] in {"player", "crossing"}) != (source is not None):
                raise ValueError("Visible token provenance requires its source entry")
            if not _cell_id(item["cellId"], cell_ids):
                raise ValueError(
                    "Visible pattern references a cell outside the session grid"
                )
        if len({item["cellId"] for item in pattern}) != len(pattern):
            raise ValueError("Duplicate visible pattern cell")
        entry_cell_ids = entry_cells.get(value["entryId"])
        if (
            entry_cell_ids is None
            or [item["cellId"] for item in pattern] != entry_cell_ids
        ):
            raise ValueError("Visible pattern does not match a puzzle entry")
        for item in pattern:
            source = item["sourceEntryId"]
            if source is not None and (
                source not in entry_cells or item["cellId"] not in entry_cells[source]
            ):
                raise ValueError("Visible token source does not contain its cell")
    if event_type in {"cell-written", "cell-cleared"}:
        if not _cell_id(value.get("cellId"), cell_ids) or not _token(
            value.get("beforeToken"), nullable=True
        ):
            raise ValueError("Invalid cell edit")
        if event_type == "cell-written" and not _token(
            value.get("afterToken"), nullable=False
        ):
            raise ValueError("Invalid written token")
        if value.get("activeEntryId") is not None and (
            not isinstance(value["activeEntryId"], str)
            or len(value["activeEntryId"]) > 160
        ):
            raise ValueError("Invalid active entry")
        active_entry = value.get("activeEntryId")
        if active_entry is not None and (
            active_entry not in entry_cells
            or value["cellId"] not in entry_cells[active_entry]
        ):
            raise ValueError("Edited cell is outside the active entry")
        if (
            not isinstance(value.get("actionId"), str)
            or not 1 <= len(value["actionId"]) <= 160
        ):
            raise ValueError("Invalid edit action")
        allowed_sources = {
            "keyboard",
            "touch",
            "accessibility",
            "composition",
            "unknown",
        }
        if value.get("source") not in allowed_sources:
            raise ValueError("Invalid edit source")
    if event_type == "batch-entered":
        if value.get("source") not in {"paste", "composition", "unknown"}:
            raise ValueError("Invalid batch source")
        if (
            not isinstance(value.get("actionId"), str)
            or not 1 <= len(value["actionId"]) <= 160
        ):
            raise ValueError("Invalid batch action")
        active = value.get("activeEntryId")
        if active is not None and (not isinstance(active, str) or len(active) > 80):
            raise ValueError("Invalid active entry")
        if active is not None and active not in entry_cells:
            raise ValueError("Invalid active entry")
        edits = value.get("edits")
        if not isinstance(edits, list) or not 1 <= len(edits) <= MAX_CELLS:
            raise ValueError("Invalid batch edits")
        for edit in edits:
            if not isinstance(edit, dict) or set(edit) != {
                "cellId",
                "beforeToken",
                "afterToken",
            }:
                raise ValueError("Invalid batch edit")
            if (
                not _cell_id(edit["cellId"], cell_ids)
                or not _token(edit["beforeToken"], nullable=True)
                or not _token(edit["afterToken"], nullable=False)
            ):
                raise ValueError("Invalid batch edit")
            if active is not None and edit["cellId"] not in entry_cells[active]:
                raise ValueError("Batch edit is outside the active entry")
        if len({edit["cellId"] for edit in edits}) != len(edits):
            raise ValueError("Duplicate batch edit cell")
    if event_type in {"check-result-shown", "answer-revealed"}:
        if value.get("scope") not in {"cell", "entry", "puzzle"}:
            raise ValueError("Invalid evidence scope")
        entry_id = value.get("entryId")
        if entry_id is not None and (
            not isinstance(entry_id, str) or len(entry_id) > 80
        ):
            raise ValueError("Invalid evidence entry")
        if (value["scope"] == "puzzle") != (entry_id is None):
            raise ValueError("Puzzle scope and entry id do not agree")
        if entry_id is not None and entry_id not in entry_cells:
            raise ValueError("Evidence references an unknown entry")
        field = "results" if event_type == "check-result-shown" else "cells"
        entries = value.get(field)
        if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_CELLS:
            raise ValueError("Invalid evidence cells")
        if event_type == "check-result-shown":
            for item in entries:
                if (
                    not isinstance(item, dict)
                    or set(item) != {"cellId", "token", "classification"}
                    or not _cell_id(item.get("cellId"), cell_ids)
                ):
                    raise ValueError("Invalid check result")
                if not _token(item["token"], nullable=True) or item[
                    "classification"
                ] not in {"correct", "incorrect", "blank"}:
                    raise ValueError("Invalid check result")
                if (item["classification"] == "blank") != (item["token"] is None):
                    raise ValueError("Blank check results must have null tokens")
            if len({item["cellId"] for item in entries}) != len(entries):
                raise ValueError("Duplicate checked cell")
            if value["scope"] == "cell" and len(entries) != 1:
                raise ValueError("A cell check must contain exactly one result")
            if (
                value["scope"] == "entry"
                and [item["cellId"] for item in entries] != entry_cells[entry_id]
            ):
                raise ValueError("Entry check does not cover the complete entry")
            for item in entries:
                token = item["token"]
                expected = (
                    "blank"
                    if token is None
                    else (
                        "correct"
                        if _normalized_token(token)
                        == _normalized_token(answers_by_cell[item["cellId"]])
                        else "incorrect"
                    )
                )
                if item["classification"] != expected:
                    raise ValueError(
                        "Check classification disagrees with the puzzle answer"
                    )
        else:
            for item in entries:
                if (
                    not isinstance(item, dict)
                    or set(item) != {"cellId", "beforeToken", "token"}
                    or not _cell_id(item.get("cellId"), cell_ids)
                ):
                    raise ValueError("Invalid revealed cell")
                if not _token(item["beforeToken"], nullable=True) or not _token(
                    item["token"], nullable=False
                ):
                    raise ValueError("Invalid revealed cell")
            if len({item["cellId"] for item in entries}) != len(entries):
                raise ValueError("Duplicate revealed cell")
            if value["scope"] == "cell" and len(entries) != 1:
                raise ValueError("A cell reveal must contain exactly one cell")
            if (
                value["scope"] == "entry"
                and [item["cellId"] for item in entries] != entry_cells[entry_id]
            ):
                raise ValueError("Entry reveal does not cover the complete entry")
            for item in entries:
                if _normalized_token(item["token"]) != _normalized_token(
                    answers_by_cell[item["cellId"]]
                ):
                    raise ValueError("Revealed token disagrees with the puzzle answer")
    if event_type == "hint-shown":
        entry_id = value.get("entryId")
        if (
            not isinstance(entry_id, str)
            or not 1 <= len(entry_id) <= 160
            or entry_id not in entry_cells
        ):
            raise ValueError("Hint references an unknown entry")
        hint_id = value.get("hintId")
        if not isinstance(hint_id, str) or not 1 <= len(hint_id) <= 160:
            raise ValueError("Invalid hint id")
        if value.get("assistanceTier") not in {
            "clue-reading",
            "context",
            "crossing",
            "letter",
            "answer",
        }:
            raise ValueError("Invalid assistance tier")
        affected = value.get("affectedCellIds")
        if not isinstance(affected, list) or len(affected) > MAX_CELLS:
            raise ValueError("Invalid affected hint cells")
        if len(set(affected)) != len(affected) or any(
            not _cell_id(cell_id, cell_ids) for cell_id in affected
        ):
            raise ValueError("Hint references an invalid cell")
        if any(cell_id not in entry_cells[entry_id] for cell_id in affected):
            raise ValueError("Hint cell is outside its entry")
    return value


@session_journal_api.post("/api/future/sessions")
def create_solve_session():
    if not _origin_is_local():
        return _error("Cross-origin session writes are not allowed", 403)
    value, size_error = _bounded_json_body("Session request is too large")
    if size_error:
        return size_error
    if not isinstance(value, dict) or set(value) != {
        "sessionId",
        "profileId",
        "puzzleHash",
        "initialGrid",
        "writerToken",
    }:
        return _error("Invalid session request", 422)
    session_id, profile_id, puzzle_hash, writer_token = (
        value.get(key)
        for key in ("sessionId", "profileId", "puzzleHash", "writerToken")
    )
    if (
        not _canonical_uuid(session_id)
        or not _canonical_uuid(profile_id)
        or not _HEX_256.fullmatch(puzzle_hash or "")
    ):
        return _error("Invalid session identity", 422)
    if (
        not isinstance(writer_token, str)
        or len(writer_token) < 32
        or len(writer_token) > 128
    ):
        return _error("Invalid writer capability", 422)
    try:
        cell_ids = _validate_initial_grid(value.get("initialGrid"))
    except ValueError as error:
        return _error(str(error), 422)
    manifest_record = db.session.get(FuturePuzzleManifestRecord, puzzle_hash)
    if manifest_record is None:
        return _error("Puzzle manifest is not registered on this host", 422)
    try:
        open_cell_ids, _, _ = _manifest_indexes(manifest_record.manifest_json)
    except ValueError as error:
        return _error(str(error), 422)
    if [cell["cellId"] for cell in value["initialGrid"]] != open_cell_ids:
        return _error("Initial grid does not exactly match the frozen puzzle", 422)
    if db.session.get(StartingProfile, profile_id) is None:
        return _error("Starting profile not found", 404)
    writer_digest = hashlib.sha256(writer_token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    record = db.session.get(PersonalSolveSession, session_id)
    if record is not None:
        same = (
            record.profile_id == profile_id
            and record.puzzle_hash == puzzle_hash
            and record.initial_grid == value["initialGrid"]
            and hmac.compare_digest(record.writer_digest, writer_digest)
        )
        if not same:
            return _error("Session id already belongs to another journal", 409)
    else:
        record = PersonalSolveSession(
            id=session_id,
            profile_id=profile_id,
            puzzle_hash=puzzle_hash,
            initial_grid=value["initialGrid"],
            writer_digest=writer_digest,
            accepted_seq=0,
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.session.add(record)
        db.session.commit()
    response = jsonify(
        sessionId=session_id,
        acceptedSeq=record.accepted_seq,
        status=record.status,
        cellCount=len(cell_ids),
    )
    response.headers["Cache-Control"] = "no-store"
    return response, 201 if record.accepted_seq == 0 else 200


@session_journal_api.post("/api/future/sessions/<session_id>/events")
def append_solve_events(session_id):
    if not _origin_is_local():
        return _error("Cross-origin session writes are not allowed", 403)
    value, size_error = _bounded_json_body("Event batch is too large")
    if size_error:
        return size_error
    if not _canonical_uuid(session_id):
        return _error("Invalid session id", 400)
    if not isinstance(value, dict) or set(value) != {
        "expectedSeq",
        "writerToken",
        "events",
    }:
        return _error("Invalid event batch", 422)
    events = value.get("events")
    if not isinstance(events, list) or not 1 <= len(events) <= MAX_EVENTS:
        return _error("Event batch must contain 1 to 200 events", 422)
    if type(value.get("expectedSeq")) is not int or value["expectedSeq"] < 0:
        return _error("Invalid expected sequence", 422)
    writer_token = value.get("writerToken")
    if (
        not isinstance(writer_token, str)
        or len(writer_token) < 32
        or len(writer_token) > 128
    ):
        return _error("Invalid writer capability", 403)
    record = db.session.get(PersonalSolveSession, session_id)
    if record is None:
        return _error("Session not found", 404)
    candidate_digest = hashlib.sha256(writer_token.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(record.writer_digest, candidate_digest):
        return _error("Invalid writer capability", 403)
    try:
        cell_ids = _validate_initial_grid(record.initial_grid)
        manifest_record = db.session.get(FuturePuzzleManifestRecord, record.puzzle_hash)
        if manifest_record is None:
            return _error("Puzzle manifest is not registered on this host", 422)
        open_cell_ids, entry_cells, answers_by_cell = _manifest_indexes(
            manifest_record.manifest_json
        )
        if [cell["cellId"] for cell in record.initial_grid] != open_cell_ids:
            return _error("Initial grid does not exactly match the frozen puzzle", 422)
        if len(events) > MAX_EVENTS:
            raise ValueError("Too many events")
        for event in events:
            _validate_event(
                event,
                session_id,
                record.profile_id,
                record.puzzle_hash,
                cell_ids,
                entry_cells,
                answers_by_cell,
            )
        if len({event["eventId"] for event in events}) != len(events):
            raise ValueError("Duplicate event id in batch")
        seqs = [event["seq"] for event in events]
        if seqs != list(range(seqs[0], seqs[0] + len(seqs))):
            raise ValueError("Event sequences must be contiguous")
    except (ValueError, TypeError, KeyError) as error:
        return _error(str(error), 422)

    event_rows = (
        db.session.query(PersonalSolveEvent)
        .filter_by(session_id=session_id)
        .filter(PersonalSolveEvent.seq.in_(seqs))
        .all()
    )
    by_seq = {row.seq: row for row in event_rows}
    new_events = []
    duplicate_ids = []
    for event in events:
        payload_hash = _digest(event)
        existing = by_seq.get(event["seq"])
        if existing is not None:
            if (
                existing.event_id != event["eventId"]
                or existing.payload_hash != payload_hash
            ):
                return _error("Sequence conflicts with accepted event", 409)
            duplicate_ids.append(event["eventId"])
            continue
        other = (
            db.session.query(PersonalSolveEvent)
            .filter_by(event_id=event["eventId"])
            .first()
        )
        if other is not None:
            return _error("Event id was already used", 409)
        new_events.append((event, payload_hash))

    if new_events:
        expected_seq = value["expectedSeq"]
        if expected_seq > record.accepted_seq or seqs[0] != expected_seq + 1:
            return _error("Accepted sequence changed; reload before retrying", 409)
        if any(
            seq not in by_seq
            for seq in range(expected_seq + 1, record.accepted_seq + 1)
        ):
            return _error("Retry does not include the full accepted prefix", 409)
        if record.status != "active":
            return _error("Session is already finished", 409)
        fresh = [event for event, _ in new_events]
        if new_events[-1][0]["seq"] > MAX_SESSION_EVENTS:
            return _error("Session has reached its event limit", 413)
        if record.accepted_seq == 0 and (
            fresh[0]["seq"] != 1 or fresh[0]["type"] != "session-started"
        ):
            return _error("First event must start the session", 422)
        if any(event["type"] == "session-started" for event in fresh[1:]):
            return _error("Session can only be started once", 422)
        if any(
            event["type"] == "session-resumed"
            and event["snapshotSeq"] > record.accepted_seq
            for event in fresh
        ):
            return _error("Resume snapshot is ahead of accepted history", 422)
        finish_positions = [
            position
            for position, event in enumerate(fresh)
            if event["type"] == "session-finished"
        ]
        if finish_positions and finish_positions != [len(fresh) - 1]:
            return _error("Session-finished must be the final event in a batch", 422)
        first_new_seq = new_events[0][0]["seq"]
        if first_new_seq != record.accepted_seq + 1 or any(
            event["seq"] <= record.accepted_seq for event, _ in new_events
        ):
            return _error("New events must continue the accepted sequence", 409)
        # Appends are atomic. Duplicate prefixes can only precede fresh events.
        if any(
            event["seq"] > record.accepted_seq
            for event in events[: len(events) - len(new_events)]
        ):
            return _error("Event retry order is inconsistent", 409)

    accepted_ids = []
    if new_events:
        base_seq = record.accepted_seq
        finished = new_events[-1][0]["type"] == "session-finished"
        persisted_events = (
            db.session.query(PersonalSolveEvent)
            .filter_by(session_id=session_id)
            .order_by(PersonalSolveEvent.seq)
            .all()
        )
        candidate_events = [row.payload for row in persisted_events] + [
            event for event, _ in new_events
        ]
        candidate_session = {
            "schemaVersion": 2,
            "sessionId": session_id,
            "profileId": record.profile_id,
            "puzzleHash": record.puzzle_hash,
            "initialGrid": record.initial_grid,
            "events": candidate_events,
        }
        try:
            analysis = analyze_solve_session(
                candidate_session, manifest_record.manifest_json
            )
        except SolveReplayRejected as error:
            db.session.rollback()
            return _error(f"Solve replay rejected: {error}", 422)
        except SolveReplayUnavailable as error:
            db.session.rollback()
            return _error(str(error), 503)
        if finished:
            try:
                get_or_create_episteme_profile(record.profile_id, now_utc_iso())
            except EpistemeRuntimeUnavailable:
                db.session.rollback()
                return _error("The local profile reducer is unavailable", 503)
            except EpistemeCommandRejected as error:
                db.session.rollback()
                return _error(str(error), 422)
        try:
            cas = db.session.execute(
                update(PersonalSolveSession)
                .where(
                    PersonalSolveSession.id == session_id,
                    PersonalSolveSession.accepted_seq == base_seq,
                    PersonalSolveSession.status == "active",
                )
                .values(
                    accepted_seq=new_events[-1][0]["seq"],
                    status="finished" if finished else "active",
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            if cas.rowcount != 1:
                db.session.rollback()
                return _error("Accepted sequence changed; reload before retrying", 409)
            for event, payload_hash in new_events:
                db.session.add(
                    PersonalSolveEvent(
                        session_id=session_id,
                        seq=event["seq"],
                        event_id=event["eventId"],
                        payload=event,
                        payload_hash=payload_hash,
                        recorded_at=event["recordedAt"],
                    )
                )
                accepted_ids.append(event["eventId"])
            analysis_record = db.session.get(FutureSolveAnalysisRecord, session_id)
            if analysis_record is None:
                analysis_record = FutureSolveAnalysisRecord(
                    session_id=session_id,
                    puzzle_hash=record.puzzle_hash,
                    analysis_version=analysis["analysisVersion"],
                    analysis_json=analysis,
                    finalized=finished,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
                db.session.add(analysis_record)
            else:
                analysis_record.analysis_version = analysis["analysisVersion"]
                analysis_record.analysis_json = analysis
                analysis_record.finalized = analysis_record.finalized or finished
                analysis_record.updated_at = datetime.now(timezone.utc).isoformat()
            if finished:
                _record_final_analysis(
                    record.profile_id,
                    session_id,
                    analysis,
                    fresh[-1]["recordedAt"],
                    manifest_record.manifest_json,
                )
            db.session.commit()
            record.accepted_seq = new_events[-1][0]["seq"]
            if finished:
                record.status = "finished"
        except IntegrityError:
            db.session.rollback()
            return _error("Accepted sequence changed; reload before retrying", 409)
        except EpistemeRevisionConflict as error:
            db.session.rollback()
            stale_revision = str(error).startswith("Stale profile revision")
            return _error(str(error), 409, retryable=stale_revision)
        except EpistemeRuntimeUnavailable:
            db.session.rollback()
            return _error("The local profile reducer is unavailable", 503)
        except EpistemeCommandRejected as error:
            db.session.rollback()
            return _error(str(error), 422)
        except Exception:
            db.session.rollback()
            raise

    response = jsonify(
        sessionId=session_id,
        acceptedSeq=record.accepted_seq,
        acceptedEventIds=accepted_ids,
        duplicateEventIds=duplicate_ids,
        status=record.status,
    )
    response.headers["Cache-Control"] = "no-store"
    return response
