"""Read-only, pinned-pack retrieval preview for the /future profile.

The returned brief is a frozen input proposal, not a crossword or a playable
manifest. Candidate eligibility comes only from the pinned pack loader; the
shared TypeScript compiler applies the host-owned episteme evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from uuid import UUID

from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import text

from .admitted_pack_config import AdmittedPackConfigError, load_configured_admitted_pack
from .database import db
from .episteme_store import (
    EpistemeCommandRejected,
    EpistemeProfileRecord,
    EpistemeRuntimeUnavailable,
    run_reducer,
)
from .future import StartingProfile, catalog


admitted_retrieval_api = Blueprint("admitted_retrieval_api", __name__)
MAX_RETRIEVAL_CANDIDATES = 5_000
MAX_RETRIEVAL_RESPONSE_BYTES = 16 * 1024 * 1024
EXPECTED_BRIEF_VERSION = "episteme-brief-v1"
# Keep this pinned to EPISTEME_BRIEF_VERSION in packages/domain/src/epistemeBrief.ts.
_BRIEF_LANES = {
    "explicit-preference",
    "inferred-preference",
    "confirmed-knowledge",
    "provisional-association",
    "broad",
    "exploration",
}
_BRIEF_SCORE_COMPONENTS = {
    "explicitPreference",
    "inferredPreference",
    "confirmedKnowledge",
    "provisionalAssociation",
    "poolDiversity",
    "total",
}
_BRIEF_DECISIONS = {
    "selected-broad-floor",
    "selected-ranked",
    "hard-exclusion",
    "language-mismatch",
    "ranked-out",
}
_LEARNING_LANGUAGE_CODES_V1 = {
    "None for now": "en",
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Italian": "it",
    "Portuguese": "pt",
    "Japanese": "ja",
    "Dutch": "nl",
}


def _error(message: str, status: int) -> Response:
    response = jsonify(error=message)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _valid_uuid(value: str) -> bool:
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _local_origin() -> bool:
    origin = request.headers.get("Origin")
    return not origin or origin == request.host_url.rstrip("/")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _canonical_digest(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_snapshot(profile_id: str) -> tuple[dict | None, dict | None, Response | None]:
    """Read the starting-profile and episteme pair under one host snapshot."""
    db.session.rollback()
    if db.engine.dialect.name == "sqlite":
        db.session.execute(text("BEGIN IMMEDIATE"))
    starting = (
        db.session.query(StartingProfile)
        .filter_by(id=profile_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    episteme = (
        db.session.query(EpistemeProfileRecord)
        .filter_by(id=profile_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if starting is None:
        db.session.rollback()
        return None, None, _error("Profile not found", 404)
    profile = episteme.profile_json if episteme is not None else None
    if (
        episteme is None
        or type(episteme.revision) is not int
        or episteme.revision < 0
        or not isinstance(profile, dict)
        or type(profile.get("revision")) is not int
        or profile.get("revision") != episteme.revision
        or profile.get("profileId") != profile_id
        or profile.get("updatedAt") != episteme.updated_at
    ):
        db.session.rollback()
        return None, None, _error("The stored host episteme snapshot is unavailable or inconsistent", 503)
    draft = starting.draft
    weekday = draft.get("weekday") if isinstance(draft, dict) else None
    learning_language = draft.get("learningLanguage") if isinstance(draft, dict) else None
    allowed_weekdays = {day["id"] for day in catalog.get("days", []) if isinstance(day, dict) and isinstance(day.get("id"), str)}
    if not isinstance(weekday, str) or weekday not in allowed_weekdays:
        db.session.rollback()
        return None, None, _error("The selected weekday difficulty is invalid", 409)
    puzzle_language = _LEARNING_LANGUAGE_CODES_V1.get(learning_language)
    if puzzle_language is None:
        db.session.rollback()
        return None, None, _error("The selected learning language is invalid", 409)

    snapshot = {
        "weekdayDifficulty": weekday,
        "learningLanguage": learning_language,
        "puzzleLanguage": puzzle_language,
        "languageMapVersion": "learning-language-code-v1",
        "profileUpdatedAt": starting.updated_at,
        "startingProfileDigest": _canonical_digest(starting.profile),
        "startingDraftDigest": _canonical_digest(draft),
        "epistemeRevision": episteme.revision,
        "epistemeUpdatedAt": episteme.updated_at,
        "epistemeDigest": _canonical_digest(profile),
        "epistemeDigestAlgorithm": "sha256-canonical-json-v1",
    }
    frozen_profile = json.loads(json.dumps(profile, ensure_ascii=False, allow_nan=False))
    db.session.rollback()
    return frozen_profile, snapshot, None


def _selection_limit() -> int | None:
    if set(request.args.keys()) - {"limit"}:
        return None
    values = request.args.getlist("limit")
    if not values:
        return 30
    raw = values[0]
    if len(values) != 1 or not raw.isascii() or not raw.isdecimal() or len(raw) > 3:
        return None
    value = int(raw)
    return value if 1 <= value <= 100 else None


def _is_record(value: object) -> bool:
    return isinstance(value, dict)


def _finite_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _valid_id_list(value: object, *, required: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (not required or bool(value))
        and all(isinstance(item, str) and 0 < len(item.strip()) <= 200 for item in value)
        and len(value) == len(set(value))
    )


def _valid_score_components(value: object) -> bool:
    return (
        _is_record(value)
        and set(value) == _BRIEF_SCORE_COMPONENTS
        and all(_finite_number(component) for component in value.values())
    )


def _valid_candidate(value: object) -> bool:
    if not _is_record(value):
        return False
    eligibility = value.get("eligibility")
    return (
        isinstance(value.get("candidateId"), str)
        and 0 < len(value["candidateId"].strip()) <= 200
        and isinstance(value.get("answer"), str)
        and 0 < len(value["answer"].strip()) <= 500
        and isinstance(value.get("language"), str)
        and 0 < len(value["language"].strip()) <= 63
        and isinstance(value.get("pool"), str)
        and value.get("pool") in {"broad", "exploration"}
        and _valid_id_list(value.get("conceptIds"))
        and _valid_id_list(value.get("knowledgeTaskIds"))
        and _valid_id_list(value.get("associationIds"))
        and _is_record(eligibility)
        and eligibility.get("status") == "eligible"
        and isinstance(eligibility.get("packId"), str)
        and bool(eligibility["packId"].strip())
        and isinstance(eligibility.get("packVersion"), str)
        and bool(eligibility["packVersion"].strip())
        and _valid_id_list(eligibility.get("sourceIds"), required=True)
    )


def _valid_compiled_brief(
    brief: object,
    *,
    profile_id: str,
    profile_revision: int,
    as_of: str,
    language: str,
    selection_limit: int,
    candidates_by_id: dict[str, dict],
) -> bool:
    """Fail closed if the local compiler result differs from its versioned contract."""
    if not _is_record(brief):
        return False
    if (
        brief.get("briefVersion") != EXPECTED_BRIEF_VERSION
        or brief.get("profileId") != profile_id
        or type(brief.get("profileRevision")) is not int
        or brief.get("profileRevision") != profile_revision
        or brief.get("asOf") != as_of
        or brief.get("mode") != "play"
        or brief.get("language") != language
        or type(brief.get("selectionLimit")) is not int
        or brief.get("selectionLimit") != selection_limit
    ):
        return False

    selected = brief.get("selected")
    selection_log = brief.get("selectionLog")
    candidate_ids = set(candidates_by_id)
    if (
        not isinstance(selected, list)
        or len(selected) > selection_limit
        or not isinstance(selection_log, list)
        or len(selection_log) != len(candidate_ids)
    ):
        return False

    selected_by_id: dict[str, dict] = {}
    for rank, row in enumerate(selected, start=1):
        if not _is_record(row) or not _valid_candidate(row.get("candidate")):
            return False
        candidate = row["candidate"]
        candidate_id = candidate["candidateId"]
        if (
            candidate_id not in candidate_ids
            or candidate != candidates_by_id[candidate_id]
            or candidate_id in selected_by_id
            or type(row.get("rank")) is not int
            or row.get("rank") != rank
            or not isinstance(row.get("selectedLane"), str)
            or row.get("selectedLane") not in _BRIEF_LANES
            or not isinstance(row.get("matchedLanes"), list)
            or any(not isinstance(lane, str) or lane not in _BRIEF_LANES for lane in row["matchedLanes"])
            or len(row["matchedLanes"]) != len(set(row["matchedLanes"]))
            or not _finite_number(row.get("score"))
            or not _valid_score_components(row.get("scoreComponents"))
            or row["score"] != row["scoreComponents"]["total"]
            or not _valid_id_list(row.get("sourceIds"), required=True)
            or not _valid_id_list(row.get("evidenceIds"))
            or set(row["sourceIds"]) != set(candidate["eligibility"]["sourceIds"])
        ):
            return False
        selected_by_id[candidate_id] = row

    logged_by_id: dict[str, dict] = {}
    for row in selection_log:
        if not _is_record(row):
            return False
        candidate_id = row.get("candidateId")
        if (
            not isinstance(candidate_id, str)
            or candidate_id not in candidate_ids
            or candidate_id in logged_by_id
            or type(row.get("selected")) is not bool
            or not isinstance(row.get("decision"), str)
            or row.get("decision") not in _BRIEF_DECISIONS
            or not isinstance(row.get("reason"), str)
            or not row["reason"].strip()
            or not isinstance(row.get("matchedLanes"), list)
            or any(not isinstance(lane, str) or lane not in _BRIEF_LANES for lane in row["matchedLanes"])
            or len(row["matchedLanes"]) != len(set(row["matchedLanes"]))
            or not _valid_id_list(row.get("sourceIds"), required=True)
            or not _valid_id_list(row.get("evidenceIds"))
            or not _valid_id_list(row.get("hardExcludedConceptIds"))
        ):
            return False
        score = row.get("score")
        components = row.get("scoreComponents")
        if score is not None and not _finite_number(score):
            return False
        if components is not None and not _valid_score_components(components):
            return False
        if (score is None) != (components is None):
            return False
        selected_row = selected_by_id.get(candidate_id)
        if selected_row is None:
            if row.get("selected") or row.get("selectedRank") is not None or row.get("selectedLane") is not None:
                return False
        elif (
            not row["selected"]
            or row.get("decision") not in {"selected-broad-floor", "selected-ranked"}
            or type(row.get("selectedRank")) is not int
            or row.get("selectedRank") != selected_row["rank"]
            or row.get("selectedLane") != selected_row["selectedLane"]
            or row.get("matchedLanes") != selected_row["matchedLanes"]
            or row.get("score") != selected_row["score"]
            or row.get("scoreComponents") != selected_row["scoreComponents"]
            or row.get("evidenceIds") != selected_row["evidenceIds"]
            or row.get("sourceIds") != selected_row["sourceIds"]
        ):
            return False
        logged_by_id[candidate_id] = row

    return set(logged_by_id) == candidate_ids and set(selected_by_id).issubset(logged_by_id)


@admitted_retrieval_api.get("/api/future/profile/<profile_id>/retrieval-brief")
def read_retrieval_brief(profile_id: str):
    """Compile an explainable candidate selection from an exact pinned pack."""
    if not _local_origin():
        return _error("Cross-origin retrieval is not allowed", 403)
    if not _valid_uuid(profile_id):
        return _error("Invalid profile id", 400)
    limit = _selection_limit()
    if limit is None:
        return _error("Invalid retrieval limit or query parameter", 400)

    profile, snapshot, error = _read_snapshot(profile_id)
    if error is not None:
        return error
    try:
        admitted = load_configured_admitted_pack(current_app.config)
    except AdmittedPackConfigError:
        return _error("A valid pinned admitted-content pack is not configured", 503)
    candidates = admitted.candidates
    if len(candidates) > MAX_RETRIEVAL_CANDIDATES:
        return _error("The pinned content pack exceeds the retrieval candidate limit", 503)
    language = snapshot["puzzleLanguage"]

    as_of = _now()
    try:
        result = run_reducer(
            {
                "operation": "brief",
                "profile": profile,
                "candidates": candidates,
                "options": {
                    "asOf": as_of,
                    "mode": "play",
                    "language": language,
                    "selectionLimit": limit,
                },
            }
        )
    except EpistemeRuntimeUnavailable:
        return _error("The local retrieval compiler is unavailable", 503)
    except EpistemeCommandRejected:
        return _error("The host episteme or admitted candidates failed retrieval validation", 409)
    brief = result.get("brief") if isinstance(result, dict) else None
    if not _valid_compiled_brief(
        brief,
        profile_id=profile_id,
        profile_revision=snapshot["epistemeRevision"],
        as_of=as_of,
        language=language,
        selection_limit=limit,
        candidates_by_id={candidate["candidateId"]: candidate for candidate in candidates},
    ):
        return _error("The local retrieval compiler returned an inconsistent brief", 503)

    receipt = {
        **snapshot,
        "packId": admitted.pack_id,
        "packSha256": admitted.pack_sha256,
        "sourcePins": admitted.source_pins,
        "briefVersion": brief.get("briefVersion"),
        "mode": "play",
        "asOf": as_of,
    }
    body = {
        "stage": "retrieval-brief",
        "playable": False,
        "evidenceScope": "brief.evidenceIds refer only to host episteme evidence; source sense/fact support is separate and not included in this preview",
        "receipt": receipt,
        "brief": brief,
    }
    try:
        serialized = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        return _error("The retrieval brief could not be serialized", 503)
    if len(serialized.encode("utf-8")) > MAX_RETRIEVAL_RESPONSE_BYTES:
        return _error("The retrieval brief exceeds the response size limit", 503)
    response = Response(serialized, status=200, mimetype="application/json")
    response.headers["Cache-Control"] = "no-store"
    return response
