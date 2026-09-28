"""Durable local queue for personalized answer grids and review candidates.

When a fill can be joined to exact admitted clues and evidence, a job may also
return a non-playable PuzzleDocumentV2 review candidate. Jobs never register a
puzzle or create a playable session.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
import tempfile
from types import SimpleNamespace
from uuid import UUID, uuid4

from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import or_, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .database import db
from .future import StartingProfile, catalog
from .episteme_store import (
    EpistemeCommandRejected,
    EpistemeProfileRecord,
    EpistemeRuntimeUnavailable,
    get_or_create_episteme_profile,
)
from .construction_runtime import DEFAULT_OPTIONS, generate_full_size_draft
from .admitted_pack_config import AdmittedPackConfigError, load_configured_admitted_pack
from .admitted_retrieval_api import (
    EXPECTED_BRIEF_VERSION,
    MAX_RETRIEVAL_CANDIDATES,
    _LEARNING_LANGUAGE_CODES_V1,
    _valid_compiled_brief,
)
from .episteme_store import run_reducer
from .personalized_manifest import (
    PersonalizedManifestRejected,
    build_personalized_manifest,
)
from .future_puzzles import (
    PersonalizedV2CandidateRejected,
    stage_private_puzzle_provenance,
    stage_personalized_v2_review_candidate,
)


future_grid_jobs_api = Blueprint("future_grid_jobs_api", __name__)
JOB_LEASE_SECONDS = 300
MAX_JOB_BODY_BYTES = 16 * 1024
MAX_GRID_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_PERSONALIZED_RESULT_BYTES = 15 * 1024 * 1024
GRID_DRAFT_RECIPE = "xfill-wide-v1"
PERSONALIZED_GRID_DRAFT_RECIPE = "admitted-xfill-wide-v1"
PERSONALIZED_BRIEF_COMPILER_VERSION = "compile-episteme-brief-v1"
_SOURCE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_RAW_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ANSWER = re.compile(r"^[A-Z]{3,15}$")
_MAX_WORDLIST_BYTES = 2 * 1024 * 1024
_MAX_COMPILED_BRIEF_BYTES = 8 * 1024 * 1024


class FutureGridDraftJob(db.Model):
    __tablename__ = "future_grid_draft_jobs"
    __table_args__ = (
        db.UniqueConstraint(
            "profile_id", "idempotency_key", name="uq_future_grid_job_idempotency"
        ),
    )

    id = db.Column(db.String(36), primary_key=True)
    profile_id = db.Column(db.String(36), nullable=False, index=True)
    idempotency_key = db.Column(db.String(36), nullable=False)
    request_digest = db.Column(db.String(64), nullable=False)
    request_json = db.Column(db.JSON, nullable=False)
    state = db.Column(db.String(16), nullable=False, default="queued", index=True)
    attempt = db.Column(db.Integer, nullable=False, default=0)
    lease_token = db.Column(db.String(36), nullable=True)
    lease_until = db.Column(db.String(40), nullable=True, index=True)
    cancel_requested = db.Column(db.Boolean, nullable=False, default=False)
    result_json = db.Column(db.JSON, nullable=True)
    error = db.Column(db.String(240), nullable=True)
    created_at = db.Column(db.String(40), nullable=False)
    updated_at = db.Column(db.String(40), nullable=False)


class FutureGridDraftPrivateSelection(db.Model):
    """Host-only profile evidence selected for a non-playable manifest candidate.

    Kept outside ``FutureGridDraftJob.result_json`` so the public job response
    never serializes the candidate-to-profile evidence join.
    """

    __tablename__ = "future_grid_draft_private_selections"

    job_id = db.Column(db.String(36), primary_key=True)
    profile_id = db.Column(db.String(36), nullable=False, index=True)
    selection_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.String(40), nullable=False)


def _now():
    return datetime.now(timezone.utc)


def _stamp(value=None):
    return (value or _now()).isoformat(timespec="milliseconds")


def _elapsed_seconds(stamp):
    """Return a bounded, honest elapsed time for an operational stage."""
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        started = datetime.fromisoformat(stamp)
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        return round(max(0.0, (_now() - started).total_seconds()), 1)
    except (TypeError, ValueError, OverflowError):
        return None


def _canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _uuid(value):
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _response(job, status=200):
    frozen_mode = (
        job.request_json.get("mode") if isinstance(job.request_json, dict) else None
    )
    private_play = frozen_mode == "private-puzzle"
    runtime_stage = (
        job.request_json.get("runtimeStage")
        if isinstance(job.request_json, dict)
        else None
    )
    runtime_stage_elapsed = (
        _elapsed_seconds(job.request_json.get("runtimeStageStartedAt"))
        if private_play and job.state == "running"
        and isinstance(runtime_stage, str)
        else None
    )
    payload = {
        "id": job.id,
        "state": job.state,
        "stage": "queued"
        if job.state == "queued"
        else (
            runtime_stage
            if private_play and job.state == "running" and isinstance(runtime_stage, str)
            else (
                "generating"
                if private_play and job.state == "running"
                else ("filling" if job.state == "running" else job.state)
            )
        ),
        "attempt": job.attempt,
        # Attempt count is the only durable evidence available here. A
        # second-or-later claim means the worker reclaimed or replayed the
        # job after an interruption; it does not identify the cause.
        "recovery": "reclaimed" if job.attempt > 1 else "first-attempt",
        "cancelRequested": job.cancel_requested,
        "createdAt": job.created_at,
        "updatedAt": job.updated_at,
        "stageElapsedSeconds": runtime_stage_elapsed,
        "result": job.result_json,
        "error": job.error,
        "playable": private_play
        and job.state == "ready"
        and isinstance(job.result_json, dict),
    }
    try:
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        serialized_bytes = serialized.encode("utf-8", errors="strict")
    except (TypeError, ValueError, RecursionError, UnicodeError):
        serialized = None
    if serialized is None:
        response = jsonify(error="Grid draft response is unavailable", playable=False)
        response.status_code = 503
        response.headers["Cache-Control"] = "no-store"
        return response
    if len(serialized_bytes) > MAX_GRID_RESPONSE_BYTES:
        response = jsonify(
            error="Grid draft response exceeds the size limit", playable=False
        )
        response.status_code = 503
        response.headers["Cache-Control"] = "no-store"
        return response
    response = Response(serialized, status=status, mimetype="application/json")
    response.headers["Cache-Control"] = "no-store"
    return response


def _job_error(message, status):
    response = jsonify(error=message, playable=False)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _local_origin():
    origin = request.headers.get("Origin")
    return not origin or origin == request.host_url.rstrip("/")


def _valid_seed(value):
    return type(value) is int and 0 <= value <= 2_147_483_647


def _stamp_z(value=None):
    return (value or _now()).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _json_copy(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _pack_receipt(pack):
    return {
        "packId": pack.pack_id,
        "packSha256": pack.pack_sha256,
        "sourcePins": [dict(pin) for pin in pack.source_pins],
    }


def _load_pinned_pack():
    pack = load_configured_admitted_pack(current_app.config)
    if len(pack.candidates) > MAX_RETRIEVAL_CANDIDATES:
        raise AdmittedPackConfigError
    return pack


def _personalized_frozen_request(profile_id, profile, episteme, pack, seed):
    draft = profile.draft
    weekday = draft.get("weekday") if isinstance(draft, dict) else None
    allowed_weekdays = {
        day["id"]
        for day in catalog.get("days", [])
        if isinstance(day, dict) and isinstance(day.get("id"), str)
    }
    learning_language = (
        draft.get("learningLanguage") if isinstance(draft, dict) else None
    )
    puzzle_language = _LEARNING_LANGUAGE_CODES_V1.get(learning_language)
    if weekday not in allowed_weekdays or puzzle_language is None:
        raise ValueError("The selected language or weekday is invalid")
    starting_profile = _json_copy(profile.profile)
    starting_draft = _json_copy(draft)
    episteme_profile = _json_copy(episteme.profile_json)
    now = _now()
    return {
        "version": 4,
        "mode": "personalized",
        "profileId": profile_id,
        "profileUpdatedAt": profile.updated_at,
        "profileDigest": _digest(starting_profile),
        "startingDraftDigest": _digest(starting_draft),
        "startingProfile": starting_profile,
        "startingDraft": starting_draft,
        "weekdayDifficulty": weekday,
        "learningLanguage": learning_language,
        "puzzleLanguage": puzzle_language,
        "languageMapVersion": "learning-language-code-v1",
        "epistemeRevision": episteme.revision,
        "epistemeUpdatedAt": episteme.updated_at,
        "epistemeDigest": _digest(episteme_profile),
        "epistemeDigestAlgorithm": "sha256-canonical-json-v1",
        "epistemeProfile": episteme_profile,
        **_pack_receipt(pack),
        "asOf": _stamp_z(now),
        "seed": seed,
        "recipe": PERSONALIZED_GRID_DRAFT_RECIPE,
        "options": {**DEFAULT_OPTIONS, "seed": seed},
        "stage": "answer-grid-draft",
    }


@future_grid_jobs_api.post("/api/future/personalized/grid-draft-jobs")
def create_personalized_grid_draft_job():
    """Queue a host-pinned, profile-aware answer-grid draft.

    The client can choose only its profile capability, idempotency key and
    deterministic seed. All profile snapshots, source pins, vocabulary and
    paths are read or materialized by the trusted host.
    """
    if not _local_origin():
        return _job_error("Cross-origin job creation is not allowed", 403)
    request.max_content_length = MAX_JOB_BODY_BYTES
    if (
        request.content_length is not None
        and request.content_length > MAX_JOB_BODY_BYTES
    ):
        return _job_error("Job request is too large", 413)
    try:
        body = request.get_json(silent=True)
    except Exception:
        return _job_error("Job request is too large or malformed", 413)
    if not isinstance(body, dict) or set(body) != {
        "profileId",
        "idempotencyKey",
        "seed",
    }:
        return _job_error(
            "Job request must include profileId, idempotencyKey and seed", 400
        )
    profile_id = body["profileId"]
    idempotency_key = body["idempotencyKey"]
    if (
        not _uuid(profile_id)
        or not _uuid(idempotency_key)
        or not _valid_seed(body["seed"])
    ):
        return _job_error("Invalid profile, idempotency key or seed", 400)

    intent = {"profileId": profile_id, "seed": body["seed"], "mode": "personalized"}
    request_digest = _digest(intent)
    existing = FutureGridDraftJob.query.filter_by(
        profile_id=profile_id,
        idempotency_key=idempotency_key,
    ).one_or_none()
    if existing is not None:
        if existing.request_digest != request_digest:
            return _job_error(
                "Idempotency key was already used for a different request", 409
            )
        return _response(existing)

    try:
        pinned_pack = _load_pinned_pack()
    except AdmittedPackConfigError:
        return _job_error("A valid pinned admitted-content pack is not configured", 503)

    db.session.rollback()
    profile = db.session.get(StartingProfile, profile_id)
    if profile is None:
        return _job_error("Profile not found", 404)
    try:
        get_or_create_episteme_profile(profile_id, profile.updated_at)
    except EpistemeRuntimeUnavailable:
        db.session.rollback()
        return _job_error(
            "The local episteme runtime is unavailable; retry to create this draft", 503
        )
    except EpistemeCommandRejected:
        db.session.rollback()
        return _job_error("The local episteme snapshot could not be initialized", 503)

    # Freeze both local profiles and the verified content trust pins while
    # excluding concurrent profile/evidence edits from this snapshot.
    db.session.rollback()
    if db.engine.dialect.name == "sqlite":
        db.session.execute(text("BEGIN IMMEDIATE"))
    existing = FutureGridDraftJob.query.filter_by(
        profile_id=profile_id,
        idempotency_key=idempotency_key,
    ).one_or_none()
    if existing is not None:
        db.session.rollback()
        if existing.request_digest != request_digest:
            return _job_error(
                "Idempotency key was already used for a different request", 409
            )
        return _response(existing)
    profile = (
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
    if profile is None:
        db.session.rollback()
        return _job_error("Profile not found", 404)
    if (
        episteme is None
        or type(episteme.revision) is not int
        or episteme.revision < 0
        or not isinstance(episteme.profile_json, dict)
        or type(episteme.profile_json.get("revision")) is not int
        or episteme.profile_json.get("revision") != episteme.revision
        or episteme.profile_json.get("profileId") != profile_id
        or episteme.profile_json.get("updatedAt") != episteme.updated_at
    ):
        db.session.rollback()
        return _job_error(
            "The stored host episteme snapshot is unavailable or inconsistent", 409
        )
    try:
        frozen = _personalized_frozen_request(
            profile_id, profile, episteme, pinned_pack, body["seed"]
        )
        as_of = frozen["asOf"]
        brief = _compile_frozen_brief(frozen, profile_id, pinned_pack, as_of)
        frozen["briefCompilerVersion"] = PERSONALIZED_BRIEF_COMPILER_VERSION
        frozen["compiledBrief"] = brief
        frozen["compiledBriefDigest"] = _digest(brief)
    except (EpistemeCommandRejected, EpistemeRuntimeUnavailable):
        db.session.rollback()
        return _job_error(
            "The local retrieval compiler is unavailable; retry to create this draft",
            503,
        )
    except (TypeError, ValueError, RecursionError):
        db.session.rollback()
        return _job_error("The selected profile snapshot is invalid", 409)

    now = _stamp()
    job = FutureGridDraftJob(
        id=str(uuid4()),
        profile_id=profile_id,
        idempotency_key=idempotency_key,
        request_digest=request_digest,
        request_json=frozen,
        state="queued",
        created_at=now,
        updated_at=now,
    )
    db.session.add(job)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = FutureGridDraftJob.query.filter_by(
            profile_id=profile_id,
            idempotency_key=idempotency_key,
        ).one_or_none()
        if existing is None:
            raise
        if existing.request_digest != request_digest:
            return _job_error(
                "Idempotency key was already used for a different request", 409
            )
        return _response(existing)
    return _response(job, 202)


@future_grid_jobs_api.post("/api/future/grid-draft-jobs")
def create_grid_draft_job():
    if not _local_origin():
        return jsonify(error="Cross-origin job creation is not allowed"), 403
    request.max_content_length = MAX_JOB_BODY_BYTES
    if (
        request.content_length is not None
        and request.content_length > MAX_JOB_BODY_BYTES
    ):
        return jsonify(error="Job request is too large"), 413
    try:
        body = request.get_json(silent=True)
    except Exception:
        return jsonify(error="Job request is too large or malformed"), 413
    if not isinstance(body, dict) or set(body) != {
        "profileId",
        "idempotencyKey",
        "seed",
    }:
        return jsonify(
            error="Job request must include profileId, idempotencyKey and seed"
        ), 400
    profile_id = body["profileId"]
    idempotency_key = body["idempotencyKey"]
    if (
        not _uuid(profile_id)
        or not _uuid(idempotency_key)
        or not _valid_seed(body["seed"])
    ):
        return jsonify(error="Invalid profile, idempotency key or seed"), 400

    # Idempotency follows the immutable client request. A lost-response retry
    # must resolve to the original frozen job even if the profile changed since
    # that job was created.
    client_intent = {"profileId": profile_id, "seed": body["seed"]}
    request_digest = _digest(client_intent)
    existing = FutureGridDraftJob.query.filter_by(
        profile_id=profile_id,
        idempotency_key=idempotency_key,
    ).one_or_none()
    if existing is not None:
        if existing.request_digest != request_digest:
            return jsonify(
                error="Idempotency key was already used for a different request"
            ), 409
        return _response(existing)

    # Initialize missing host episteme state through the shared reducer. A
    # revision-zero snapshot is valid only when this call created that profile;
    # never synthesize zero around a stored revision. The creation helper may
    # commit, so take the actual profile/episteme pair again afterward.
    db.session.rollback()
    profile = db.session.get(StartingProfile, profile_id)
    if profile is None:
        return jsonify(error="Profile not found"), 404
    try:
        get_or_create_episteme_profile(profile_id, profile.updated_at)
    except EpistemeRuntimeUnavailable:
        db.session.rollback()
        return jsonify(
            error="The local episteme runtime is unavailable; retry to create this draft"
        ), 503
    except EpistemeCommandRejected:
        db.session.rollback()
        return jsonify(
            error="The local episteme snapshot could not be initialized"
        ), 503

    # This is a local SQLite queue. BEGIN IMMEDIATE serializes job creation
    # with profile/evidence writers while the source reads and job insert run.
    # Other SQL backends lock the two existing source rows separately; avoid
    # FOR UPDATE on the nullable side of an outer join.
    db.session.rollback()
    if db.engine.dialect.name == "sqlite":
        db.session.execute(text("BEGIN IMMEDIATE"))
    existing = FutureGridDraftJob.query.filter_by(
        profile_id=profile_id,
        idempotency_key=idempotency_key,
    ).one_or_none()
    if existing is not None:
        db.session.rollback()
        if existing.request_digest != request_digest:
            return jsonify(
                error="Idempotency key was already used for a different request"
            ), 409
        return _response(existing)
    profile = (
        db.session.query(StartingProfile)
        .filter_by(
            id=profile_id,
        )
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if profile is None:
        db.session.rollback()
        return jsonify(error="Profile not found"), 404
    episteme = (
        db.session.query(EpistemeProfileRecord)
        .filter_by(
            id=profile_id,
        )
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if episteme is None:
        db.session.rollback()
        return jsonify(
            error="The host episteme snapshot is unavailable; retry to create this draft"
        ), 503
    episteme_profile = episteme.profile_json
    if (
        type(episteme.revision) is not int
        or episteme.revision < 0
        or not isinstance(episteme_profile, dict)
        or type(episteme_profile.get("revision")) is not int
        or episteme_profile.get("revision") != episteme.revision
        or episteme_profile.get("profileId") != profile_id
        or episteme_profile.get("updatedAt") != episteme.updated_at
    ):
        db.session.rollback()
        return jsonify(error="The stored host episteme snapshot is inconsistent"), 409
    weekday = profile.draft.get("weekday") if isinstance(profile.draft, dict) else None
    if not isinstance(weekday, str) or not weekday:
        db.session.rollback()
        return jsonify(error="The selected weekday difficulty is missing"), 409

    # Freeze a minimal, non-identifying input receipt. Current xfill can create
    # an answer grid only; profile content is not passed to it as fake clues.
    frozen_request = {
        "version": 2,
        "profileUpdatedAt": profile.updated_at,
        "profileDigest": _digest(profile.profile),
        "weekdayDifficulty": weekday,
        "epistemeRevision": episteme.revision,
        "epistemeUpdatedAt": episteme.updated_at,
        "epistemeDigest": _digest(episteme_profile),
        "epistemeDigestAlgorithm": "sha256-canonical-json-v1",
        "seed": body["seed"],
        "recipe": GRID_DRAFT_RECIPE,
        "options": {**DEFAULT_OPTIONS, "seed": body["seed"]},
        "stage": "answer-grid-draft",
    }
    now = _stamp()
    job = FutureGridDraftJob(
        id=str(uuid4()),
        profile_id=profile_id,
        idempotency_key=idempotency_key,
        request_digest=request_digest,
        request_json=frozen_request,
        state="queued",
        created_at=now,
        updated_at=now,
    )
    db.session.add(job)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = FutureGridDraftJob.query.filter_by(
            profile_id=profile_id,
            idempotency_key=idempotency_key,
        ).one_or_none()
        if existing is None:
            raise
        if existing.request_digest != request_digest:
            return jsonify(
                error="Idempotency key was already used for a different request"
            ), 409
        return _response(existing)
    return _response(job, 202)


@future_grid_jobs_api.get("/api/future/grid-draft-jobs/<job_id>")
@future_grid_jobs_api.get("/api/future/private-puzzle-jobs/<job_id>")
def get_grid_draft_job(job_id):
    if not _uuid(job_id):
        return jsonify(error="Invalid job id"), 400
    profile_id = request.args.get("profileId")
    if not _uuid(profile_id):
        return jsonify(error="Invalid profile id"), 400
    job = db.session.get(FutureGridDraftJob, job_id)
    if job is None or job.profile_id != profile_id:
        return jsonify(error="Job not found"), 404
    return _response(job)


@future_grid_jobs_api.post("/api/future/grid-draft-jobs/<job_id>/cancel")
@future_grid_jobs_api.post("/api/future/private-puzzle-jobs/<job_id>/cancel")
def cancel_grid_draft_job(job_id):
    if not _local_origin():
        return jsonify(error="Cross-origin job cancellation is not allowed"), 403
    if not _uuid(job_id):
        return jsonify(error="Invalid job id"), 400
    body = request.get_json(silent=True)
    profile_id = body.get("profileId") if isinstance(body, dict) else None
    if not _uuid(profile_id):
        return jsonify(error="Invalid profile id"), 400
    for _attempt in range(4):
        job = db.session.get(FutureGridDraftJob, job_id, populate_existing=True)
        if job is None or job.profile_id != profile_id:
            return jsonify(error="Job not found"), 404
        if job.state == "queued":
            changed = db.session.execute(
                update(FutureGridDraftJob)
                .where(
                    FutureGridDraftJob.id == job_id,
                    FutureGridDraftJob.profile_id == profile_id,
                    FutureGridDraftJob.state == "queued",
                )
                .values(
                    state="cancelled",
                    cancel_requested=False,
                    result_json=None,
                    error="Cancelled before construction started",
                    updated_at=_stamp(),
                )
            )
        elif job.state == "running" and not job.cancel_requested:
            # Setting the cancellation bit is conditional on the job still
            # being owned by a running worker; finalization checks this same
            # bit in its own atomic UPDATE.
            changed = db.session.execute(
                update(FutureGridDraftJob)
                .where(
                    FutureGridDraftJob.id == job_id,
                    FutureGridDraftJob.profile_id == profile_id,
                    FutureGridDraftJob.state == "running",
                    FutureGridDraftJob.cancel_requested.is_(False),
                )
                .values(cancel_requested=True, updated_at=_stamp())
            )
        else:
            return _response(job)
        if changed.rowcount == 1:
            db.session.commit()
            current = db.session.get(FutureGridDraftJob, job_id, populate_existing=True)
            return _response(current)
        db.session.rollback()
    current = db.session.get(FutureGridDraftJob, job_id, populate_existing=True)
    if current is None or current.profile_id != profile_id:
        return jsonify(error="Job not found"), 404
    return _response(current)


def _claim_next_job():
    now = _now()
    now_text = _stamp(now)
    # A worker may have died after cancellation was requested. Once its lease
    # expires, finish cancellation here instead of leaving an unclaimable
    # running row forever.
    expired_cancelled = db.session.execute(
        update(FutureGridDraftJob)
        .where(
            FutureGridDraftJob.state == "running",
            FutureGridDraftJob.cancel_requested.is_(True),
            FutureGridDraftJob.lease_until <= now_text,
        )
        .values(
            state="cancelled",
            result_json=None,
            lease_token=None,
            lease_until=None,
            error="Cancelled after the worker lease expired",
            updated_at=now_text,
        )
    )
    if expired_cancelled.rowcount:
        db.session.commit()
    candidate = (
        FutureGridDraftJob.query.filter(
            or_(
                FutureGridDraftJob.state == "queued",
                (FutureGridDraftJob.state == "running")
                & (FutureGridDraftJob.lease_until <= now_text),
            ),
            FutureGridDraftJob.cancel_requested.is_(False),
        )
        .order_by(FutureGridDraftJob.created_at)
        .first()
    )
    if candidate is None:
        return None
    token = str(uuid4())
    old_state = candidate.state
    predicates = [
        FutureGridDraftJob.id == candidate.id,
        FutureGridDraftJob.state == old_state,
        FutureGridDraftJob.cancel_requested.is_(False),
    ]
    if old_state == "running":
        predicates.append(FutureGridDraftJob.lease_until <= now_text)
        predicates.append(FutureGridDraftJob.lease_token == candidate.lease_token)
    claim_request = _json_copy(candidate.request_json)
    claim_request.pop("runtimeStage", None)
    claim_request.pop("runtimeStageStartedAt", None)
    changed = db.session.execute(
        update(FutureGridDraftJob)
        .where(*predicates)
        .values(
            state="running",
            attempt=FutureGridDraftJob.attempt + 1,
            lease_token=token,
            lease_until=_stamp(now + timedelta(seconds=JOB_LEASE_SECONDS)),
            updated_at=now_text,
            error=None,
            request_json=claim_request,
        )
    )
    if changed.rowcount != 1:
        db.session.rollback()
        return None
    db.session.commit()
    claimed = db.session.get(FutureGridDraftJob, candidate.id)
    return claimed.id, token, dict(claimed.request_json)


def _private_job_runtime_receipt(attempt, started_at):
    """Return the bounded, answer-free receipt for one durable private job.

    The generated puzzle's provenance remains the model/content receipt.  This
    sibling object records only how the durable host job reached completion so
    postgame history can explain a reclaimed wait without carrying request,
    profile, clue, or answer material across the private boundary.
    """
    recovery = "reclaimed" if attempt > 1 else "first-attempt"
    receipt = {
        "version": "private-job-runtime-v1",
        "durable": True,
        "attempt": attempt,
        "recovery": recovery,
    }
    elapsed = _elapsed_seconds(started_at)
    if elapsed is not None:
        receipt["elapsedSeconds"] = round(elapsed, 3)
    return receipt


def _set_runtime_stage(app, job_id, token, stage):
    """Publish a truthful private-generation stage behind the current lease.

    The frozen request fields are copied unchanged; ``runtimeStage`` is an
    operational annotation used only by polling responses. A stale worker
    cannot overwrite a later lease because the update requires the same token.
    Stage reporting is best effort and never turns a playable job into a
    failure when the host is shutting down.
    """
    if stage not in {
        "theme-proposal",
        "native-xfill",
        "clue-generation",
        "finalizing",
    }:
        return
    with app.app_context():
        job = db.session.get(FutureGridDraftJob, job_id, populate_existing=True)
        if (
            job is None
            or job.state != "running"
            or job.lease_token != token
            or job.cancel_requested
        ):
            db.session.rollback()
            return
        try:
            request_json = _json_copy(job.request_json)
            request_json["runtimeStage"] = stage
            request_json["runtimeStageStartedAt"] = _stamp()
            job.request_json = request_json
            job.updated_at = _stamp()
            db.session.commit()
        except (TypeError, ValueError, RecursionError, SQLAlchemyError):
            db.session.rollback()


def _release_claim_for_shutdown(job_id, token):
    """Requeue an interrupted worker, or finish an accepted cancellation."""
    now_text = _stamp()
    requeued = db.session.execute(
        update(FutureGridDraftJob)
        .where(
            FutureGridDraftJob.id == job_id,
            FutureGridDraftJob.state == "running",
            FutureGridDraftJob.lease_token == token,
            FutureGridDraftJob.cancel_requested.is_(False),
        )
        .values(
            state="queued",
            lease_token=None,
            lease_until=None,
            result_json=None,
            error=None,
            updated_at=now_text,
        )
    )
    if requeued.rowcount == 1:
        db.session.commit()
        return
    db.session.rollback()
    cancelled = db.session.execute(
        update(FutureGridDraftJob)
        .where(
            FutureGridDraftJob.id == job_id,
            FutureGridDraftJob.state == "running",
            FutureGridDraftJob.lease_token == token,
            FutureGridDraftJob.cancel_requested.is_(True),
        )
        .values(
            state="cancelled",
            lease_token=None,
            lease_until=None,
            result_json=None,
            error="Cancelled while the worker was shutting down",
            updated_at=now_text,
        )
    )
    if cancelled.rowcount == 1:
        db.session.commit()
    else:
        db.session.rollback()


def _verify_personalized_snapshot(frozen, profile_id, pack):
    if (
        not isinstance(frozen, dict)
        or frozen.get("version") not in {3, 4}
        or frozen.get("mode") != "personalized"
    ):
        raise ValueError("The personalized job snapshot is malformed")
    if frozen.get("profileId") != profile_id:
        raise ValueError("The personalized job profile receipt is inconsistent")
    starting_profile = frozen.get("startingProfile")
    starting_draft = frozen.get("startingDraft")
    episteme_profile = frozen.get("epistemeProfile")
    if (
        not isinstance(starting_profile, dict)
        or not isinstance(starting_draft, dict)
        or not isinstance(episteme_profile, dict)
        or _digest(starting_profile) != frozen.get("profileDigest")
        or _digest(starting_draft) != frozen.get("startingDraftDigest")
        or _digest(episteme_profile) != frozen.get("epistemeDigest")
        or type(frozen.get("epistemeRevision")) is not int
        or frozen["epistemeRevision"] < 0
        or episteme_profile.get("revision") != frozen.get("epistemeRevision")
        or episteme_profile.get("profileId") != profile_id
        or episteme_profile.get("updatedAt") != frozen.get("epistemeUpdatedAt")
    ):
        raise ValueError("The personalized profile snapshot failed integrity checks")
    weekday = frozen.get("weekdayDifficulty")
    valid_weekdays = {
        day["id"]
        for day in catalog.get("days", [])
        if isinstance(day, dict) and isinstance(day.get("id"), str)
    }
    language = frozen.get("learningLanguage")
    if (
        weekday not in valid_weekdays
        or starting_draft.get("weekday") != weekday
        or starting_draft.get("learningLanguage") != language
        or _LEARNING_LANGUAGE_CODES_V1.get(language) != frozen.get("puzzleLanguage")
        or frozen.get("languageMapVersion") != "learning-language-code-v1"
    ):
        raise ValueError("The personalized language or difficulty snapshot is invalid")
    if (
        frozen.get("recipe") != PERSONALIZED_GRID_DRAFT_RECIPE
        or frozen.get("stage") != "answer-grid-draft"
        or not _valid_seed(frozen.get("seed"))
        or frozen.get("options") != {**DEFAULT_OPTIONS, "seed": frozen.get("seed")}
    ):
        raise ValueError("The personalized construction recipe is invalid")
    try:
        as_of = datetime.fromisoformat(frozen["asOf"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, TypeError, ValueError) as error:
        raise ValueError("The personalized retrieval timestamp is invalid") from error
    if as_of.tzinfo is None or frozen["asOf"] != _stamp_z(as_of):
        raise ValueError("The personalized retrieval timestamp is invalid")
    if (
        pack.pack_id != frozen.get("packId")
        or pack.pack_sha256 != frozen.get("packSha256")
        or _canonical(list(pack.source_pins)) != _canonical(frozen.get("sourcePins"))
    ):
        raise ValueError("The pinned admitted-content pack changed after job creation")
    return as_of.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _validate_compiled_brief(frozen, profile_id, pack, as_of, brief):
    candidates = pack.candidates
    if not candidates or len(candidates) > MAX_RETRIEVAL_CANDIDATES:
        raise ValueError("The pinned admitted-content pack has no usable candidates")
    candidate_ids = {
        candidate.get("candidateId")
        for candidate in candidates
        if isinstance(candidate, dict)
    }
    if len(candidate_ids) != len(candidates) or None in candidate_ids:
        raise ValueError(
            "The pinned content pack has inconsistent candidate identities"
        )
    limit = min(100, len(candidates))
    if len(_canonical(brief).encode("utf-8")) > _MAX_COMPILED_BRIEF_BYTES:
        raise ValueError("The compiled retrieval brief exceeds the job size limit")
    if not _valid_compiled_brief(
        brief,
        profile_id=profile_id,
        profile_revision=frozen["epistemeRevision"],
        as_of=as_of,
        language=frozen["puzzleLanguage"],
        selection_limit=limit,
        candidates_by_id={
            candidate["candidateId"]: candidate for candidate in candidates
        },
    ):
        raise ValueError("The retrieval compiler returned a malformed or stale brief")
    return brief


def _compile_frozen_brief(frozen, profile_id, pack, as_of):
    candidates = pack.candidates
    if not candidates or len(candidates) > MAX_RETRIEVAL_CANDIDATES:
        raise ValueError("The pinned admitted-content pack has no usable candidates")
    limit = min(100, len(candidates))
    result = run_reducer(
        {
            "operation": "brief",
            "profile": frozen["epistemeProfile"],
            "candidates": candidates,
            "options": {
                "asOf": as_of,
                "mode": "play",
                "language": frozen["puzzleLanguage"],
                "selectionLimit": limit,
            },
        }
    )
    brief = result.get("brief") if isinstance(result, dict) else None
    return _validate_compiled_brief(frozen, profile_id, pack, as_of, brief)


def _frozen_compiled_brief(frozen, profile_id, pack, as_of):
    if frozen.get("version") < 4:
        # Durable version-3 jobs predate reservation-time brief freezing. Keep
        # those queued local jobs processable while all new jobs use v4.
        return _compile_frozen_brief(frozen, profile_id, pack, as_of)
    brief = frozen.get("compiledBrief")
    if (
        frozen.get("briefCompilerVersion") != PERSONALIZED_BRIEF_COMPILER_VERSION
        or not isinstance(brief, dict)
        or _digest(brief) != frozen.get("compiledBriefDigest")
    ):
        raise ValueError(
            "The personalized job's compiled brief failed its integrity check"
        )
    return _validate_compiled_brief(frozen, profile_id, pack, as_of, brief)


def _wordlist_for_brief(pack, brief, language):
    log_by_id = {row["candidateId"]: row for row in brief["selectionLog"]}
    selected_rank = {
        row["candidate"]["candidateId"]: row["rank"] for row in brief["selected"]
    }
    by_answer = {}
    for candidate in pack.candidates:
        candidate_id = candidate["candidateId"]
        log_row = log_by_id.get(candidate_id)
        if log_row is None:
            raise ValueError("The retrieval brief omitted a pinned candidate")
        if (
            log_row["decision"] in {"hard-exclusion", "language-mismatch"}
            or candidate["language"] != language
        ):
            continue
        answer = candidate["answer"]
        if not isinstance(answer, str) or not _ANSWER.fullmatch(answer):
            # xfill accepts only ASCII A-Z answers; preserve the verified
            # source value and never silently transliterate or rewrite it.
            continue
        source_ids = candidate.get("eligibility", {}).get("sourceIds")
        if (
            not isinstance(source_ids, list)
            or not source_ids
            or log_row.get("sourceIds") != source_ids
        ):
            raise ValueError("The brief source map does not match the pinned candidate")
        record = by_answer.setdefault(answer, {"candidates": {}, "rank": None})
        record["candidates"][candidate_id] = sorted(set(source_ids))
        rank = selected_rank.get(candidate_id)
        if rank is not None and (record["rank"] is None or rank < record["rank"]):
            record["rank"] = rank
    if not by_answer:
        raise ValueError(
            "The pinned pack has no eligible xfill answers in this language"
        )

    ordered_selected = sorted(
        (answer for answer, item in by_answer.items() if item["rank"] is not None),
        key=lambda answer: (by_answer[answer]["rank"], answer),
    )
    ordered_remaining = sorted(
        answer for answer, item in by_answer.items() if item["rank"] is None
    )
    answer_order = ordered_selected + ordered_remaining
    lines = [
        f"{answer};{'100' if answer in ordered_selected else '50'}"
        for answer in answer_order
    ]
    raw = ("\n".join(lines) + "\n").encode("ascii")
    if len(raw) > _MAX_WORDLIST_BYTES:
        raise ValueError("The admitted xfill wordlist exceeds the host limit")

    is_theme = lambda answer: 8 <= len(answer) <= 15 and len(answer) != 12
    long_answers = [answer for answer in ordered_selected if is_theme(answer)]
    long_answers.extend(
        answer
        for answer in sorted(
            (word for word in ordered_remaining if is_theme(word)),
            key=lambda word: (-len(word), word),
        )
    )
    themes = list(dict.fromkeys(long_answers))[:4]
    return raw, by_answer, answer_order, ordered_selected, themes


def _validate_personalized_runtime_result(
    result, options, admitted_receipt, answer_map
):
    if (
        not isinstance(result, dict)
        or result.get("engine") != "xfill"
        or result.get("options") != options
        or type(result.get("durationMs")) is not int
        or not 0 <= result["durationMs"] <= 240_000
        or not isinstance(result.get("sourceDigest"), str)
        or not _SOURCE_DIGEST.fullmatch(result["sourceDigest"])
    ):
        raise ValueError(
            "The personalized construction runtime returned an invalid draft"
        )
    provenance = result.get("provenance")
    actual_receipt = (
        provenance.get("admittedPack") if isinstance(provenance, dict) else None
    )
    expected_receipt = {
        "packId": admitted_receipt["packId"],
        "packSha256": admitted_receipt["packSha256"],
        "wordlistSha256": admitted_receipt["sha256"],
    }
    if actual_receipt != expected_receipt:
        raise ValueError(
            "The construction runtime provenance does not match the pinned pack"
        )
    grid = result.get("grid")
    if (
        not isinstance(grid, dict)
        or not isinstance(grid.get("fill"), list)
        or len(grid["fill"]) != 15
        or any(
            not isinstance(row, str) or not re.fullmatch(r"[A-Z#]{15}", row)
            for row in grid["fill"]
        )
        or not isinstance(grid.get("entries"), list)
        or not 50 <= len(grid["entries"]) <= 78
        or not _runtime_template_matches_fill(grid.get("template"), grid["fill"])
    ):
        raise ValueError(
            "The personalized construction runtime returned an invalid answer grid"
        )
    requested_themes = set(options["themes"])
    generated_themes = {
        entry["answer"]
        for entry in grid["entries"]
        if isinstance(entry, dict) and entry.get("theme") is True
    }
    if not requested_themes.issubset(generated_themes):
        raise ValueError("The construction runtime omitted a requested theme answer")
    links = []
    for entry in grid["entries"]:
        if not isinstance(entry, dict):
            raise ValueError("The construction runtime returned a malformed entry")
        answer = entry.get("answer")
        number = entry.get("num")
        direction = entry.get("dir")
        if (
            type(number) is not int
            or not 1 <= number <= 78
            or direction not in {"A", "D"}
            or not isinstance(entry.get("theme"), bool)
        ):
            raise ValueError("The construction runtime returned a malformed entry")
        if not isinstance(answer, str) or answer not in answer_map:
            raise ValueError(
                "The construction runtime generated an answer outside the pinned pack"
            )
        item = answer_map[answer]
        links.append(
            {
                "entryNumber": number,
                "direction": "across" if direction == "A" else "down",
                "answer": answer,
                "candidateIds": sorted(item["candidates"]),
                "sourceIds": sorted(
                    {
                        source
                        for values in item["candidates"].values()
                        for source in values
                    }
                ),
            }
        )
    return links


def _runtime_template_matches_fill(template, fill):
    """Require the native template's block mask to agree with the answer fill."""
    return (
        isinstance(template, list)
        and len(template) == 15
        and all(
            isinstance(row, str) and re.fullmatch(r"[.#A-Z]{15}", row)
            for row in template
        )
        and all(
            (template[row][column] == "#") == (fill[row][column] == "#")
            for row in range(15)
            for column in range(15)
        )
    )


def _manifest_links_for_grid(links, content, brief):
    """Add only exact admitted clue and profile-evidence IDs for the V2 join."""
    lexemes_by_id = {lexeme.lexeme_id: lexeme for lexeme in content.lexemes}
    evidence_by_candidate = {
        row["candidateId"]: tuple(row["evidenceIds"]) for row in brief["selectionLog"]
    }
    enriched = []
    for link in links:
        candidate_ids = link.get("candidateIds")
        if not isinstance(candidate_ids, list) or len(candidate_ids) != 1:
            raise PersonalizedManifestRejected("entry-candidate-ambiguous")
        candidate_id = candidate_ids[0]
        lexeme = lexemes_by_id.get(candidate_id)
        if lexeme is None or candidate_id not in evidence_by_candidate:
            raise PersonalizedManifestRejected("entry-candidate-not-in-pinned-content")

        # Prefer an exact clue linked to an eligible resolved sense. A fact
        # clue may be used only with a separately pinned eligible sense, as
        # required by the V2 contract; the builder checks that relationship.
        eligible_senses = {
            sense.sense_id
            for sense in lexeme.senses
            if sense.clue_eligible is True
            and sense.fill_only is False
            and sense.resolution_status == "resolved"
        }
        sense_clues = sorted(
            (
                clue
                for clue in lexeme.clues
                if clue.evidence_type == "sense"
                and clue.evidence_id in eligible_senses
                and clue.answer_lexeme_id == lexeme.lexeme_id
            ),
            key=lambda clue: clue.clue_id,
        )
        selected_clue = sense_clues[0] if sense_clues else None
        selected_sense_id = (
            selected_clue.evidence_id if selected_clue is not None else None
        )
        selected_fact_id = None
        if selected_clue is None:
            fact_clues = sorted(
                (
                    clue
                    for clue in lexeme.clues
                    if clue.evidence_type == "fact"
                    and clue.answer_lexeme_id == lexeme.lexeme_id
                ),
                key=lambda clue: clue.clue_id,
            )
            if fact_clues and eligible_senses:
                selected_clue = fact_clues[0]
                selected_sense_id = min(eligible_senses)
                selected_fact_id = selected_clue.evidence_id
        if selected_clue is None:
            raise PersonalizedManifestRejected("entry-clue-not-available")

        enriched.append(
            {
                **link,
                "clueId": selected_clue.clue_id,
                "senseId": selected_sense_id,
                "factId": selected_fact_id,
                "profileEvidenceIds": list(evidence_by_candidate[candidate_id]),
            }
        )
    return enriched


def _manifest_grid_projection(grid):
    """Project a validated runtime grid onto the manifest adapter's input.

    The pinned native runtime emits template, score, and search diagnostics in
    addition to the answer grid. Those fields are useful to the editor, but are
    not trusted inputs to candidate geometry or crossing confidence. The
    manifest derives geometry from ``fill`` and entries, so pass only the
    runtime fields the host has already validated for that purpose.
    """
    if (
        not isinstance(grid, dict)
        or not isinstance(grid.get("fill"), list)
        or not isinstance(grid.get("entries"), list)
    ):
        raise ValueError(
            "The personalized construction runtime returned an invalid answer grid"
        )

    entries = []
    for entry in grid["entries"]:
        if not isinstance(entry, dict) or not {
            "num",
            "dir",
            "answer",
            "theme",
        }.issubset(entry):
            raise ValueError(
                "The personalized construction runtime returned a malformed entry"
            )
        entries.append({key: entry[key] for key in ("num", "dir", "answer", "theme")})
    return {"fill": list(grid["fill"]), "entries": entries}


def _build_manifest_candidate(result, links, frozen, brief, pack):
    """Return a public review candidate, private sidecar, or stable reject code."""
    try:
        manifest_job = dict(frozen)
        # Version-3 jobs did not persist a brief; pass the exact worker-time
        # recompilation through the same strict adapter with an explicit receipt.
        manifest_job["compiledBrief"] = brief
        manifest_job["compiledBriefDigest"] = _digest(brief)
        if frozen.get("version") < 4:
            manifest_job["briefCompilerVersion"] = "worker-recompiled-v1"
        manifest_job["weekdayDifficulty"] = str(frozen["weekdayDifficulty"]).title()
        manifest_links = _manifest_links_for_grid(links, pack.content, brief)
        runtime_digest = result["sourceDigest"].removeprefix("sha256:")
        built = build_personalized_manifest(
            _manifest_grid_projection(result["grid"]),
            manifest_links,
            content=pack.content,
            frozen_job=manifest_job,
            version_inputs={
                "generatedAt": _stamp_z(),
                "recipe": {
                    "id": frozen["recipe"],
                    "version": "1",
                    "weekday": manifest_job["weekdayDifficulty"],
                },
                "runtime": {
                    "id": "xfill",
                    "version": "result-source-digest-v1",
                    "artifactDigest": runtime_digest,
                },
                "validators": [
                    {"id": "personalized-manifest-v2-host", "version": "1"},
                    {"id": "admitted-pack-content", "version": "1"},
                ],
            },
        )
        return (
            {
                "status": "review",
                "playable": False,
                "manifest": _json_copy(_plain_json(built.manifest)),
            },
            _json_copy(_plain_json(built.private_selection)),
            None,
        )
    except PersonalizedManifestRejected as error:
        code = str(error)
        if not re.fullmatch(r"[a-z0-9-]{1,80}", code):
            code = "manifest-candidate-rejected"
        return None, None, code
    except (KeyError, TypeError, ValueError, RecursionError, UnicodeError):
        return None, None, "manifest-candidate-invalid"
    except Exception:
        # Candidate assembly is opportunistic. A contract mismatch must not
        # turn an otherwise valid answer-grid job into a failed job.
        return None, None, "manifest-candidate-unavailable"


def _plain_json(value):
    """Convert immutable mappings/tuples returned by the V2 adapter to JSON."""
    if isinstance(value, dict) or hasattr(value, "items"):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    return value


def _run_personalized_generation(app, frozen, profile_id, generator, cancelled):
    with app.app_context():
        try:
            pack = _load_pinned_pack()
            as_of = _verify_personalized_snapshot(frozen, profile_id, pack)
            brief = _frozen_compiled_brief(frozen, profile_id, pack, as_of)
            raw, answer_map, answers, selected, themes = _wordlist_for_brief(
                pack, brief, frozen["puzzleLanguage"]
            )
        except (
            AdmittedPackConfigError,
            EpistemeCommandRejected,
            EpistemeRuntimeUnavailable,
        ) as error:
            raise ValueError(
                "The pinned pack or retrieval compiler is unavailable"
            ) from error

    wordlist_sha256 = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory(prefix="crossword-admitted-grid-") as directory:
        os.chmod(directory, 0o700)
        path = os.path.join(directory, "admitted-answers.dict")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as wordlist_file:
            wordlist_file.write(raw)
            wordlist_file.flush()
            os.fsync(wordlist_file.fileno())
        os.chmod(path, 0o400)
        with open(path, "rb") as wordlist_file:
            if (
                hashlib.sha256(wordlist_file.read(_MAX_WORDLIST_BYTES + 1)).hexdigest()
                != wordlist_sha256
            ):
                raise ValueError(
                    "The temporary admitted wordlist failed its digest check"
                )

        options = {**frozen["options"], "themes": themes}
        receipt = {
            "path": os.path.abspath(path),
            "sha256": wordlist_sha256,
            "packId": pack.pack_id,
            "packSha256": pack.pack_sha256,
        }
        result = generator(
            seed=frozen["seed"],
            options=options,
            admitted_wordlist=receipt,
            cancel_requested=cancelled,
        )
        links = _validate_personalized_runtime_result(
            result, options, receipt, answer_map
        )
        manifest_candidate, private_selection, rejection_code = (
            _build_manifest_candidate(result, links, frozen, brief, pack)
        )
        serialized = _json_copy(result)
        serialized["personalization"] = {
            "stage": "answer-grid-draft",
            "playable": False,
            "receipt": {
                "profileId": profile_id,
                "profileUpdatedAt": frozen["profileUpdatedAt"],
                "profileDigest": frozen["profileDigest"],
                "startingDraftDigest": frozen["startingDraftDigest"],
                "weekdayDifficulty": frozen["weekdayDifficulty"],
                "learningLanguage": frozen["learningLanguage"],
                "puzzleLanguage": frozen["puzzleLanguage"],
                "languageMapVersion": frozen["languageMapVersion"],
                "epistemeRevision": frozen["epistemeRevision"],
                "epistemeUpdatedAt": frozen["epistemeUpdatedAt"],
                "epistemeDigest": frozen["epistemeDigest"],
                "epistemeDigestAlgorithm": frozen["epistemeDigestAlgorithm"],
                "packId": frozen["packId"],
                "packSha256": frozen["packSha256"],
                "sourcePins": frozen["sourcePins"],
                "asOf": frozen["asOf"],
                "briefVersion": EXPECTED_BRIEF_VERSION,
                "briefCompilerVersion": frozen.get(
                    "briefCompilerVersion", "worker-recompiled-v1"
                ),
                "compiledBriefDigest": frozen.get(
                    "compiledBriefDigest", _digest(brief)
                ),
            },
            "wordlistReceipt": {
                "sha256": wordlist_sha256,
                "answerCount": len(answers),
                "selectedAnswerCount": len(selected),
                "selectedAnswers": selected,
                "themeAnswers": themes,
            },
            "entrySourceLinks": links,
            "evidenceScope": (
                "entrySourceLinks establish answer-vocabulary provenance only; when a manifestCandidate "
                "is present it carries exact admitted clue, sense, and fact provenance, with semantic "
                "truth still awaiting review."
            ),
        }
        if manifest_candidate is not None:
            serialized["personalization"]["manifestCandidate"] = manifest_candidate
        else:
            serialized["personalization"]["manifestCandidateRejectionCode"] = (
                rejection_code
            )
        return serialized, private_selection


def _run_private_puzzle_generation(app, frozen, *, stage_callback=None):
    """Build one playable local puzzle from the worker's frozen profile view."""
    # Import lazily so the Flask app can register both blueprints without a
    # module cycle. The private route and this worker share the same generator
    # implementation; only the execution boundary changes.
    from .private_puzzle_generation import _generate

    starting = SimpleNamespace(
        # Preserve the owner identity across the frozen worker boundary. The
        # private generator uses it to resolve due language-review records;
        # omitting it silently downgraded queued jobs to exposure-only briefs.
        id=frozen["profileId"],
        profile=frozen["startingProfile"],
        draft=frozen["startingDraft"],
    )
    episteme = SimpleNamespace(profile_json=frozen["epistemeProfile"])
    with app.app_context():
        try:
            generation_kwargs = {"stage_callback": stage_callback}
            if frozen.get("model") is not None:
                generation_kwargs["model_override"] = frozen["model"]
            crossword, manifest, provenance = _generate(
                frozen["seed"],
                frozen["weekday"],
                starting,
                episteme,
                **generation_kwargs,
            )
        except TypeError as error:
            # Keep older local extensions/test doubles callable while the
            # optional progress hook rolls out. Only fall back for the
            # signature mismatch; generation TypeErrors still surface.
            if stage_callback is None or "stage_callback" not in str(error):
                raise
            fallback_kwargs = {}
            if frozen.get("model") is not None:
                fallback_kwargs["model_override"] = frozen["model"]
            crossword, manifest, provenance = _generate(
                frozen["seed"], frozen["weekday"], starting, episteme, **fallback_kwargs
            )
    return {
        "puzzle": crossword.model_dump(exclude={"across_entries", "down_entries"}),
        "puzzleManifest": manifest,
        "provenance": provenance,
    }


def _remove_public_manifest_candidate(serialized, rejection_code):
    """Keep a completed answer grid if the optional candidate cannot persist."""
    personalization = serialized.get("personalization")
    if isinstance(personalization, dict):
        personalization.pop("manifestCandidate", None)
        personalization["manifestCandidateRejectionCode"] = rejection_code


def _finalize_grid_result(
    job_id,
    token,
    frozen,
    state,
    serialized,
    error,
    private_selection,
    private_runtime=None,
):
    """Atomically stage optional candidate/private evidence and fence the job write."""
    # ``runtimeStage`` and its timestamp are polling annotations, not part of
    # the immutable request receipt.  A worker may have written one after the
    # claim (including ``finalizing``), so restore the frozen request on the
    # terminal write.  This also removes a stale stage left by a worker that
    # died after publishing progress and before committing its result.
    terminal_request = _json_copy(frozen)
    terminal_request.pop("runtimeStage", None)
    terminal_request.pop("runtimeStageStartedAt", None)
    common = (
        FutureGridDraftJob.id == job_id,
        FutureGridDraftJob.state == "running",
        FutureGridDraftJob.lease_token == token,
    )
    candidate_manifest = None
    personalization = (
        serialized.get("personalization") if isinstance(serialized, dict) else None
    )
    if isinstance(personalization, dict) and isinstance(
        personalization.get("manifestCandidate"), dict
    ):
        candidate_manifest = personalization["manifestCandidate"].get("manifest")
    if state == "ready" and candidate_manifest is not None:
        stage_personalized_v2_review_candidate(
            job_id=job_id,
            profile_id=frozen["profileId"],
            manifest=candidate_manifest,
        )
    if state == "ready" and frozen.get("mode") == "private-puzzle":
        private_manifest = (
            serialized.get("puzzleManifest")
            if isinstance(serialized, dict)
            else None
        )
        private_provenance = (
            serialized.get("provenance") if isinstance(serialized, dict) else None
        )
        if isinstance(private_manifest, dict) and isinstance(private_provenance, dict):
            try:
                if isinstance(private_runtime, dict):
                    # Keep the response-scoped generator provenance stable for
                    # existing clients while persisting the operational
                    # receipt beside it for owner-scoped replay/history.
                    private_provenance = {
                        **private_provenance,
                        "jobRuntime": private_runtime,
                    }
                stage_private_puzzle_provenance(
                    profile_id=frozen["profileId"],
                    manifest=private_manifest,
                    provenance=private_provenance,
                )
            except (ValueError, TypeError, KeyError, RecursionError):
                # The private puzzle remains playable if this optional receipt
                # cannot be staged; the job result still carries its own
                # response-scoped provenance for the current browser.
                pass
    if (
        state == "ready"
        and private_selection is not None
        and candidate_manifest is not None
    ):
        db.session.add(
            FutureGridDraftPrivateSelection(
                job_id=job_id,
                profile_id=frozen["profileId"],
                selection_json=private_selection,
                created_at=_stamp(),
            )
        )
    finalized = db.session.execute(
        update(FutureGridDraftJob)
        .where(*common, FutureGridDraftJob.cancel_requested.is_(False))
        .values(
            state=state,
            result_json=serialized,
            error=error,
            request_json=terminal_request,
            lease_token=None,
            lease_until=None,
            updated_at=_stamp(),
        )
    )
    if finalized.rowcount != 1:
        db.session.rollback()
        return False
    db.session.commit()
    return True


def process_next_grid_draft(
    app,
    *,
    generator=generate_full_size_draft,
    shutdown_requested=lambda: False,
):
    """Claim and process at most one durable job; return whether one was found."""
    with app.app_context():
        claim = _claim_next_job()
        if claim is None:
            return False
        job_id, token, frozen = claim
        claimed = db.session.get(FutureGridDraftJob, job_id)
        # Read the lease facts before removing this session.  They are
        # operational metadata, not part of the frozen profile request, and
        # preserve the historical three-item _claim_next_job contract.
        attempt = claimed.attempt
        claim_started_at = claimed.updated_at
        db.session.remove()

    def cancelled():
        if shutdown_requested():
            return True
        with app.app_context():
            current = db.session.get(FutureGridDraftJob, job_id)
            return (
                current is None
                or current.state != "running"
                or current.lease_token != token
                or current.cancel_requested
            )

    try:
        private_selection = None
        private_play = frozen.get("mode") == "private-puzzle"
        if private_play:
            result = _run_private_puzzle_generation(
                app,
                frozen,
                stage_callback=lambda stage: _set_runtime_stage(
                    app, job_id, token, stage
                ),
            )
        elif frozen.get("mode") == "personalized":
            result, private_selection = _run_personalized_generation(
                app,
                frozen,
                frozen.get("profileId"),
                generator,
                cancelled,
            )
        else:
            result = generator(
                seed=frozen["seed"],
                options=frozen["options"],
                cancel_requested=cancelled,
            )
        if not isinstance(result, dict) or (
            not private_play
            and not _SOURCE_DIGEST.fullmatch(
                result.get("sourceDigest", "")
                if isinstance(result.get("sourceDigest"), str)
                else ""
            )
        ):
            raise ValueError("Construction runtime returned an invalid source receipt")
        serialized = _json_copy(result)
        if private_play:
            _set_runtime_stage(app, job_id, token, "finalizing")
        if (
            frozen.get("mode") == "personalized"
            and len(_canonical(serialized).encode("utf-8"))
            > MAX_PERSONALIZED_RESULT_BYTES
        ):
            # The optional V2 document is expendable; the underlying grid is
            # still ready when only candidate material crosses its bound.
            personalization = serialized.get("personalization")
            if (
                isinstance(personalization, dict)
                and "manifestCandidate" in personalization
            ):
                personalization.pop("manifestCandidate")
                personalization["manifestCandidateRejectionCode"] = (
                    "manifest-candidate-size-limit"
                )
                private_selection = None
            if (
                len(_canonical(serialized).encode("utf-8"))
                > MAX_PERSONALIZED_RESULT_BYTES
            ):
                raise ValueError(
                    "The personalized answer-grid result exceeds the size limit"
                )
        error = None
        state = "ready"
        private_runtime = (
            _private_job_runtime_receipt(attempt, claim_started_at)
            if private_play
            else None
        )
    except Exception as exc:  # Persist failure for the UI; worker remains available.
        serialized = None
        error = str(exc).strip()[:240] or "Full-size answer-grid construction failed"
        if frozen.get("mode") == "personalized" and ("/" in error or "\\" in error):
            error = "The personalized answer-grid draft failed local validation"
        state = "failed"
        private_runtime = None

    with app.app_context():
        if shutdown_requested():
            _release_claim_for_shutdown(job_id, token)
            return True
        try:
            if _finalize_grid_result(
                job_id,
                token,
                frozen,
                state,
                serialized,
                error,
                private_selection,
                private_runtime,
            ):
                return True
        except PersonalizedV2CandidateRejected:
            db.session.rollback()
            _remove_public_manifest_candidate(
                serialized, "manifest-candidate-validation-failed"
            )
            private_selection = None
            try:
                if _finalize_grid_result(
                    job_id,
                    token,
                    frozen,
                    state,
                    serialized,
                    error,
                    None,
                    private_runtime,
                ):
                    return True
            except Exception:
                db.session.rollback()
                raise
        except SQLAlchemyError:
            # A candidate uniqueness/storage race is optional. Roll back the
            # whole staged unit, then persist the answer grid alone under the
            # same lease and cancellation predicates.
            db.session.rollback()
            if state == "ready" and isinstance(serialized, dict):
                _remove_public_manifest_candidate(
                    serialized, "manifest-candidate-storage-failed"
                )
                private_selection = None
                try:
                    if _finalize_grid_result(
                        job_id,
                        token,
                        frozen,
                        state,
                        serialized,
                        error,
                        None,
                        private_runtime,
                    ):
                        return True
                except Exception:
                    db.session.rollback()
                    raise
            else:
                raise
        db.session.rollback()
        common = (
            FutureGridDraftJob.id == job_id,
            FutureGridDraftJob.state == "running",
            FutureGridDraftJob.lease_token == token,
        )
        cancelled = db.session.execute(
            update(FutureGridDraftJob)
            .where(*common, FutureGridDraftJob.cancel_requested.is_(True))
            .values(
                state="cancelled",
                result_json=None,
                error="Cancelled; the completed draft was discarded",
                lease_token=None,
                lease_until=None,
                updated_at=_stamp(),
            )
        )
        if cancelled.rowcount == 1:
            db.session.commit()
        else:
            # A different worker now owns the row, or another path already
            # completed it. The old result is discarded by its lease fence.
            db.session.rollback()
    return True
