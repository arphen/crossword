"""Read-only, stable-order export for the /future personal episteme."""

import json
from hashlib import sha256
from uuid import UUID

from flask import Blueprint, Response, request
from sqlalchemy import LargeBinary, String, cast, func, select

from .calibration_api import CalibrationSessionRecord
from .calibration_hypothesis_api import (
    CalibrationHypothesisActionRecord,
    CalibrationHypothesisDeckRecord,
    CalibrationHypothesisResponseRecord,
)
from .database import db
from .episteme_store import MAX_PROFILE_BYTES, EpistemeProfileRecord
from .future import StartingProfile
from .future_grid_jobs import FutureGridDraftJob, FutureGridDraftPrivateSelection
from .future_puzzles import FuturePuzzleManifestRecord, FutureSolveAnalysisRecord
from .learning_review import FutureLearningReviewRecord, exported_learning_reviews
from .postgame_associations_api import (
    PostgameAssociationResponseRecord,
    PostgameAssociationRunRecord,
)
from .profile_narrative_api import ProfileNarrativeRecord
from .reflection_api import (
    FutureReflectionActionRecord,
    FutureReflectionDeckRecord,
    FutureReflectionResponseRecord,
)
from .session_journal import PersonalSolveEvent, PersonalSolveSession


profile_export_api = Blueprint("profile_export_api", __name__)
EXPORT_SCHEMA_VERSION = 2
EXPORT_INTEGRITY_VERSION = "profile-export-integrity-v1"
# The episteme record is allowed to reach 64 MiB. Leave room for journal and
# export-envelope metadata while keeping one response bounded.
MAX_EXPORT_BYTES = 80 * 1024 * 1024
# Every exported row adds a small amount of envelope/provenance metadata that
# is not present in its source columns.  The preflight deliberately rounds up
# this allowance so a request that fails the bound is rejected before the
# profile-sized Python export graph is built.
_EXPORT_ROW_OVERHEAD = 4096
_EXPORT_ENVELOPE_OVERHEAD = 16 * 1024


def _canonical_archive_bytes(value):
    """Serialize an archive envelope without runtime-dependent whitespace."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def archive_integrity_digest(value):
    """Digest an archive body while excluding its self-referential receipt."""
    body = dict(value) if isinstance(value, dict) else {}
    body.pop("integrity", None)
    return sha256(_canonical_archive_bytes(body)).hexdigest()


def _valid_uuid(value):
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _same_origin():
    origin = request.headers.get("Origin")
    return origin is None or origin == request.host_url.rstrip("/")


def _error(message, status, **extra):
    response = Response(
        json.dumps({"error": message, **extra}, separators=(",", ":")),
        status=status,
        mimetype="application/json",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def _calibrations_for_profile(profile_id):
    # Profile scope lives inside the immutable calibration JSON contract.
    # Filtering in SQL avoids loading unrelated guest and profile journals.
    return (
        CalibrationSessionRecord.query.filter(
            CalibrationSessionRecord.payload["scope"]["kind"].as_string() == "profile",
            CalibrationSessionRecord.payload["scope"]["profileId"].as_string()
            == profile_id,
        )
        .order_by(CalibrationSessionRecord.id)
        .all()
    )


def _safe_generation_metadata(value):
    """Retain reproducibility identifiers without exporting runtime secrets."""
    if not isinstance(value, dict):
        return {}
    return {
        key: value[key]
        for key in ("provider", "requestedModel", "returnedModel", "format", "digest")
        if key in value
    }


def _without_capability_fields(value):
    """Copy exportable JSON while omitting exact credential field names only."""
    if isinstance(value, dict):
        return {
            key: _without_capability_fields(item)
            for key, item in value.items()
            if key.casefold().replace("_", "").replace("-", "")
            not in {
                "writertoken",
                "leasetoken",
                "authorizationtoken",
                "writercredential",
                "leasecredential",
            }
        }
    if isinstance(value, list):
        return [_without_capability_fields(item) for item in value]
    return value


def _export_size_preflight(profile_id):
    """Return a conservative byte bound without loading export rows.

    The export endpoint historically built the complete nested archive and
    only then measured ``json.dumps``.  A profile can contain many immutable
    journal rows, so that ordering could temporarily use several times the
    configured response cap.  This pass uses SQL aggregates over the source
    columns instead.  It reads lengths and counts only; the full ORM rows are
    not materialized unless this bound is below the cap.

    JSON values are stored as text by SQLite.  ``BLOB`` length gives their
    actual UTF-8 byte length there; PostgreSQL's ``octet_length`` provides the
    same measurement.  The fallback multiplies character length by four,
    the maximum UTF-8 width, so other local SQL backends remain safe.
    """

    dialect = db.session.get_bind().dialect.name

    def byte_length(column):
        if dialect == "sqlite":
            return func.length(cast(column, LargeBinary))
        if dialect == "postgresql":
            return func.octet_length(cast(column, String))
        return 4 * func.length(cast(column, String))

    total_bytes = 0
    total_rows = 0

    def measure(model, columns, *filters):
        nonlocal total_bytes, total_rows
        expressions = [
            func.coalesce(func.sum(byte_length(column)), 0) for column in columns
        ]
        row = db.session.execute(
            select(func.count(), *expressions).select_from(model).where(*filters)
        ).one()
        total_rows += int(row[0] or 0)
        # A capability field may be removed during export, but including it in
        # the bound is intentional: this keeps the preflight conservative.
        total_bytes += sum(int(value or 0) for value in row[1:])

    measure(
        StartingProfile,
        (
            StartingProfile.id,
            StartingProfile.draft,
            StartingProfile.profile,
            StartingProfile.updated_at,
        ),
        StartingProfile.id == profile_id,
    )
    # The reducer already enforces this per-profile ceiling.  Reserve the
    # entire ceiling instead of issuing a second read against the episteme
    # table: the export's SQLite snapshot test intentionally detects the
    # single episteme read performed by the actual archive builder.
    total_bytes += MAX_PROFILE_BYTES

    calibration_ids = select(CalibrationSessionRecord.id).where(
        CalibrationSessionRecord.payload["scope"]["kind"].as_string() == "profile",
        CalibrationSessionRecord.payload["scope"]["profileId"].as_string()
        == profile_id,
    )
    measure(
        CalibrationSessionRecord,
        (CalibrationSessionRecord.id, CalibrationSessionRecord.payload),
        CalibrationSessionRecord.id.in_(calibration_ids),
    )
    hypothesis_calibration_ids = (
        select(CalibrationHypothesisDeckRecord.calibration_id)
        .where(CalibrationHypothesisDeckRecord.profile_id == profile_id)
        .union(calibration_ids)
    )
    measure(
        CalibrationHypothesisDeckRecord,
        (
            CalibrationHypothesisDeckRecord.calibration_id,
            CalibrationHypothesisDeckRecord.source_digest,
            CalibrationHypothesisDeckRecord.deck_id,
            CalibrationHypothesisDeckRecord.deck_json,
            CalibrationHypothesisDeckRecord.deck_hash,
            CalibrationHypothesisDeckRecord.generation_metadata,
            CalibrationHypothesisDeckRecord.created_at,
            CalibrationHypothesisDeckRecord.status,
        ),
        CalibrationHypothesisDeckRecord.profile_id == profile_id,
    )
    measure(
        CalibrationHypothesisResponseRecord,
        (
            CalibrationHypothesisResponseRecord.response_id,
            CalibrationHypothesisResponseRecord.calibration_id,
            CalibrationHypothesisResponseRecord.deck_id,
            CalibrationHypothesisResponseRecord.proposal_id,
            CalibrationHypothesisResponseRecord.request_hash,
            CalibrationHypothesisResponseRecord.response_json,
            CalibrationHypothesisResponseRecord.evidence_json,
            CalibrationHypothesisResponseRecord.status,
            CalibrationHypothesisResponseRecord.recorded_at,
        ),
        CalibrationHypothesisResponseRecord.calibration_id.in_(
            hypothesis_calibration_ids
        ),
    )
    measure(
        CalibrationHypothesisActionRecord,
        (
            CalibrationHypothesisActionRecord.action_id,
            CalibrationHypothesisActionRecord.calibration_id,
            CalibrationHypothesisActionRecord.deck_id,
            CalibrationHypothesisActionRecord.proposal_id,
            CalibrationHypothesisActionRecord.response_id,
            CalibrationHypothesisActionRecord.request_hash,
            CalibrationHypothesisActionRecord.action_json,
            CalibrationHypothesisActionRecord.evidence_action_json,
            CalibrationHypothesisActionRecord.status,
            CalibrationHypothesisActionRecord.recorded_at,
        ),
        CalibrationHypothesisActionRecord.calibration_id.in_(
            hypothesis_calibration_ids
        ),
    )

    session_ids = select(PersonalSolveSession.id).where(
        PersonalSolveSession.profile_id == profile_id
    )
    measure(
        PersonalSolveSession,
        (
            PersonalSolveSession.id,
            PersonalSolveSession.profile_id,
            PersonalSolveSession.puzzle_hash,
            PersonalSolveSession.initial_grid,
            PersonalSolveSession.writer_digest,
            PersonalSolveSession.status,
            PersonalSolveSession.created_at,
            PersonalSolveSession.updated_at,
        ),
        PersonalSolveSession.profile_id == profile_id,
    )
    measure(
        PersonalSolveEvent,
        (
            PersonalSolveEvent.session_id,
            PersonalSolveEvent.event_id,
            PersonalSolveEvent.payload,
            PersonalSolveEvent.payload_hash,
            PersonalSolveEvent.recorded_at,
        ),
        PersonalSolveEvent.session_id.in_(session_ids),
    )
    measure(
        FutureSolveAnalysisRecord,
        (
            FutureSolveAnalysisRecord.session_id,
            FutureSolveAnalysisRecord.puzzle_hash,
            FutureSolveAnalysisRecord.analysis_version,
            FutureSolveAnalysisRecord.analysis_json,
            FutureSolveAnalysisRecord.updated_at,
        ),
        FutureSolveAnalysisRecord.session_id.in_(session_ids),
    )
    measure(
        FutureReflectionDeckRecord,
        (
            FutureReflectionDeckRecord.session_id,
            FutureReflectionDeckRecord.deck_json,
            FutureReflectionDeckRecord.deck_hash,
            FutureReflectionDeckRecord.created_at,
        ),
        FutureReflectionDeckRecord.session_id.in_(session_ids),
    )
    measure(
        FutureReflectionResponseRecord,
        (
            FutureReflectionResponseRecord.response_id,
            FutureReflectionResponseRecord.session_id,
            FutureReflectionResponseRecord.card_id,
            FutureReflectionResponseRecord.response_hash,
            FutureReflectionResponseRecord.response_json,
            FutureReflectionResponseRecord.evidence_json,
            FutureReflectionResponseRecord.status,
            FutureReflectionResponseRecord.recorded_at,
        ),
        FutureReflectionResponseRecord.session_id.in_(session_ids),
    )
    measure(
        FutureReflectionActionRecord,
        (
            FutureReflectionActionRecord.action_id,
            FutureReflectionActionRecord.session_id,
            FutureReflectionActionRecord.card_id,
            FutureReflectionActionRecord.target_response_id,
            FutureReflectionActionRecord.action_hash,
            FutureReflectionActionRecord.action_json,
            FutureReflectionActionRecord.evidence_action_json,
            FutureReflectionActionRecord.status,
            FutureReflectionActionRecord.recorded_at,
        ),
        FutureReflectionActionRecord.session_id.in_(session_ids),
    )
    measure(
        PostgameAssociationRunRecord,
        (
            PostgameAssociationRunRecord.session_id,
            PostgameAssociationRunRecord.profile_id,
            PostgameAssociationRunRecord.request_hash,
            PostgameAssociationRunRecord.status,
            PostgameAssociationRunRecord.paths_json,
            PostgameAssociationRunRecord.evidence_json,
            PostgameAssociationRunRecord.generation_metadata,
            PostgameAssociationRunRecord.episteme_revision,
            PostgameAssociationRunRecord.created_at,
            PostgameAssociationRunRecord.updated_at,
        ),
        PostgameAssociationRunRecord.profile_id == profile_id,
        PostgameAssociationRunRecord.session_id.in_(session_ids),
    )
    measure(
        PostgameAssociationResponseRecord,
        (
            PostgameAssociationResponseRecord.response_id,
            PostgameAssociationResponseRecord.session_id,
            PostgameAssociationResponseRecord.profile_id,
            PostgameAssociationResponseRecord.association_id,
            PostgameAssociationResponseRecord.request_hash,
            PostgameAssociationResponseRecord.response_json,
            PostgameAssociationResponseRecord.evidence_json,
            PostgameAssociationResponseRecord.episteme_revision,
            PostgameAssociationResponseRecord.status,
            PostgameAssociationResponseRecord.recorded_at,
        ),
        PostgameAssociationResponseRecord.profile_id == profile_id,
        PostgameAssociationResponseRecord.session_id.in_(session_ids),
    )

    grid_job_ids = select(FutureGridDraftJob.id).where(
        FutureGridDraftJob.profile_id == profile_id
    )
    measure(
        FutureGridDraftJob,
        (
            FutureGridDraftJob.id,
            FutureGridDraftJob.profile_id,
            FutureGridDraftJob.idempotency_key,
            FutureGridDraftJob.request_digest,
            FutureGridDraftJob.request_json,
            FutureGridDraftJob.state,
            FutureGridDraftJob.lease_token,
            FutureGridDraftJob.lease_until,
            FutureGridDraftJob.error,
            FutureGridDraftJob.created_at,
            FutureGridDraftJob.updated_at,
            FutureGridDraftJob.result_json,
        ),
        FutureGridDraftJob.profile_id == profile_id,
    )
    measure(
        FutureGridDraftPrivateSelection,
        (
            FutureGridDraftPrivateSelection.job_id,
            FutureGridDraftPrivateSelection.profile_id,
            FutureGridDraftPrivateSelection.selection_json,
            FutureGridDraftPrivateSelection.created_at,
        ),
        FutureGridDraftPrivateSelection.profile_id == profile_id,
        FutureGridDraftPrivateSelection.job_id.in_(grid_job_ids),
    )
    measure(
        FutureLearningReviewRecord,
        (
            FutureLearningReviewRecord.id,
            FutureLearningReviewRecord.profile_id,
            FutureLearningReviewRecord.task_id,
            FutureLearningReviewRecord.language,
            FutureLearningReviewRecord.source_evidence_id,
            FutureLearningReviewRecord.response,
            FutureLearningReviewRecord.input_mode,
            FutureLearningReviewRecord.recorded_at,
        ),
        FutureLearningReviewRecord.profile_id == profile_id,
    )
    measure(
        ProfileNarrativeRecord,
        (
            ProfileNarrativeRecord.id,
            ProfileNarrativeRecord.profile_id,
            ProfileNarrativeRecord.episteme_revision,
            ProfileNarrativeRecord.source_digest,
            ProfileNarrativeRecord.narrative_json,
            ProfileNarrativeRecord.generation_metadata,
            ProfileNarrativeRecord.status,
            ProfileNarrativeRecord.created_at,
            ProfileNarrativeRecord.updated_at,
        ),
        ProfileNarrativeRecord.profile_id == profile_id,
    )

    return _EXPORT_ENVELOPE_OVERHEAD + total_bytes + total_rows * _EXPORT_ROW_OVERHEAD


def _export_profile(profile_id):
    starting = db.session.get(StartingProfile, profile_id)
    if starting is None:
        return None

    episteme = db.session.get(EpistemeProfileRecord, profile_id)
    calibration_records = _calibrations_for_profile(profile_id)
    calibration_ids = {record.id for record in calibration_records}
    hypothesis_decks = (
        CalibrationHypothesisDeckRecord.query.filter_by(profile_id=profile_id)
        .order_by(
            CalibrationHypothesisDeckRecord.calibration_id,
            CalibrationHypothesisDeckRecord.created_at,
            CalibrationHypothesisDeckRecord.deck_id,
        )
        .all()
    )
    hypothesis_deck_ids = {record.deck_id for record in hypothesis_decks}
    hypothesis_calibration_ids = calibration_ids | {
        record.calibration_id for record in hypothesis_decks
    }
    hypothesis_responses = []
    hypothesis_actions = []
    if hypothesis_calibration_ids:
        hypothesis_responses = (
            CalibrationHypothesisResponseRecord.query.filter(
                CalibrationHypothesisResponseRecord.calibration_id.in_(
                    hypothesis_calibration_ids
                )
            )
            .order_by(
                CalibrationHypothesisResponseRecord.recorded_at,
                CalibrationHypothesisResponseRecord.response_id,
            )
            .all()
        )
        hypothesis_actions = (
            CalibrationHypothesisActionRecord.query.filter(
                CalibrationHypothesisActionRecord.calibration_id.in_(
                    hypothesis_calibration_ids
                )
            )
            .order_by(
                CalibrationHypothesisActionRecord.recorded_at,
                CalibrationHypothesisActionRecord.action_id,
            )
            .all()
        )

    sessions = (
        PersonalSolveSession.query.filter_by(profile_id=profile_id)
        .order_by(PersonalSolveSession.created_at, PersonalSolveSession.id)
        .all()
    )
    session_ids = [record.id for record in sessions]
    events = []
    analyses = []
    reflection_decks = []
    reflection_responses = []
    reflection_actions = []
    postgame_runs = []
    postgame_responses = []
    puzzle_ids = {}
    if session_ids:
        events = (
            PersonalSolveEvent.query.filter(
                PersonalSolveEvent.session_id.in_(session_ids)
            )
            .order_by(
                PersonalSolveEvent.session_id,
                PersonalSolveEvent.seq,
                PersonalSolveEvent.id,
            )
            .all()
        )
        analyses = (
            FutureSolveAnalysisRecord.query.filter(
                FutureSolveAnalysisRecord.session_id.in_(session_ids)
            )
            .order_by(FutureSolveAnalysisRecord.session_id)
            .all()
        )
        reflection_decks = (
            FutureReflectionDeckRecord.query.filter(
                FutureReflectionDeckRecord.session_id.in_(session_ids)
            )
            .order_by(FutureReflectionDeckRecord.session_id)
            .all()
        )
        reflection_responses = (
            FutureReflectionResponseRecord.query.filter(
                FutureReflectionResponseRecord.session_id.in_(session_ids)
            )
            .order_by(
                FutureReflectionResponseRecord.session_id,
                FutureReflectionResponseRecord.recorded_at,
                FutureReflectionResponseRecord.response_id,
            )
            .all()
        )
        reflection_actions = (
            FutureReflectionActionRecord.query.filter(
                FutureReflectionActionRecord.session_id.in_(session_ids)
            )
            .order_by(
                FutureReflectionActionRecord.session_id,
                FutureReflectionActionRecord.recorded_at,
                FutureReflectionActionRecord.action_id,
            )
            .all()
        )
        postgame_runs = (
            PostgameAssociationRunRecord.query.filter(
                PostgameAssociationRunRecord.session_id.in_(session_ids)
            )
            .order_by(PostgameAssociationRunRecord.session_id)
            .all()
        )
        postgame_responses = (
            PostgameAssociationResponseRecord.query.filter(
                PostgameAssociationResponseRecord.session_id.in_(session_ids)
            )
            .order_by(
                PostgameAssociationResponseRecord.session_id,
                PostgameAssociationResponseRecord.recorded_at,
                PostgameAssociationResponseRecord.response_id,
            )
            .all()
        )
        hashes = sorted({record.puzzle_hash for record in sessions})
        manifests = (
            db.session.execute(
                select(
                    FuturePuzzleManifestRecord.puzzle_hash,
                    FuturePuzzleManifestRecord.puzzle_id,
                ).where(FuturePuzzleManifestRecord.puzzle_hash.in_(hashes))
            ).all()
            if hashes
            else []
        )
        puzzle_ids = {puzzle_hash: puzzle_id for puzzle_hash, puzzle_id in manifests}

    grid_jobs = (
        FutureGridDraftJob.query.filter_by(profile_id=profile_id)
        .order_by(FutureGridDraftJob.created_at, FutureGridDraftJob.id)
        .all()
    )
    narratives = (
        ProfileNarrativeRecord.query.filter_by(profile_id=profile_id)
        .order_by(ProfileNarrativeRecord.created_at, ProfileNarrativeRecord.id)
        .all()
    )
    private_selections = {}
    grid_job_ids = [record.id for record in grid_jobs]
    if grid_job_ids:
        private_selections = {
            record.job_id: record
            for record in FutureGridDraftPrivateSelection.query.filter(
                FutureGridDraftPrivateSelection.job_id.in_(grid_job_ids),
                FutureGridDraftPrivateSelection.profile_id == profile_id,
            )
            .order_by(FutureGridDraftPrivateSelection.job_id)
            .all()
        }

    by_session_events = {session_id: [] for session_id in session_ids}
    for event in events:
        by_session_events[event.session_id].append(
            {
                "sequence": event.seq,
                "eventId": event.event_id,
                "payload": event.payload,
                "recordedAt": event.recorded_at,
            }
        )
    by_session_analysis = {record.session_id: record for record in analyses}
    by_session_reflection_deck = {
        record.session_id: record for record in reflection_decks
    }
    by_session_reflection_responses = {session_id: [] for session_id in session_ids}
    for record in reflection_responses:
        by_session_reflection_responses[record.session_id].append(
            {
                "responseId": record.response_id,
                "cardId": record.card_id,
                "response": record.response_json,
                "evidence": record.evidence_json,
                "epistemeRevision": record.episteme_revision,
                "status": record.status,
                "recordedAt": record.recorded_at,
            }
        )
    by_session_reflection_actions = {session_id: [] for session_id in session_ids}
    for record in reflection_actions:
        by_session_reflection_actions[record.session_id].append(
            {
                "actionId": record.action_id,
                "cardId": record.card_id,
                "targetResponseId": record.target_response_id,
                "action": record.action_json,
                "evidenceAction": record.evidence_action_json,
                "epistemeRevision": record.episteme_revision,
                "status": record.status,
                "recordedAt": record.recorded_at,
            }
        )
    by_session_postgame_run = {record.session_id: record for record in postgame_runs}
    by_session_postgame_responses = {session_id: [] for session_id in session_ids}
    for record in postgame_responses:
        by_session_postgame_responses[record.session_id].append(
            {
                "responseId": record.response_id,
                "associationId": record.association_id,
                "response": record.response_json,
                "evidence": record.evidence_json,
                "epistemeRevision": record.episteme_revision,
                "status": record.status,
                "recordedAt": record.recorded_at,
            }
        )

    export = {
        "format": "crossword-personal-episteme-export",
        "schemaVersion": EXPORT_SCHEMA_VERSION,
        "profileId": profile_id,
        "provenance": {
            "storage": "local-host-profile-store",
            "collections": [
                "future_starting_profiles",
                "future_episteme_profiles",
                "future_calibration_sessions",
                "future_calibration_hypothesis_decks",
                "future_calibration_hypothesis_responses",
                "future_calibration_hypothesis_actions",
                "future_solve_sessions",
                "future_solve_events",
                "future_solve_analyses",
                "future_reflection_decks",
                "future_reflection_responses",
                "future_reflection_actions",
                "future_postgame_association_runs",
                "future_postgame_association_responses",
                "future_grid_draft_jobs",
                "future_grid_draft_private_selections",
                "future_learning_review_records",
                "future_profile_narratives",
            ],
            "sharedPuzzleManifests": "referenced-by-id-only; puzzle content is not exported",
        },
        "startingProfile": {
            "recordId": starting.id,
            "draft": starting.draft,
            "profile": starting.profile,
            "updatedAt": starting.updated_at,
        },
        "episteme": None
        if episteme is None
        else {
            "recordId": episteme.id,
            "revision": episteme.revision,
            "profile": episteme.profile_json,
            "updatedAt": episteme.updated_at,
        },
        "calibrations": [
            {
                "recordId": record.id,
                "revision": record.revision,
                "payload": record.payload,
                "provenance": {"table": "future_calibration_sessions"},
            }
            for record in calibration_records
        ],
        "calibrationHypotheses": {
            "decks": [
                {
                    "deckId": record.deck_id,
                    "calibrationId": record.calibration_id,
                    "sourceDigest": record.source_digest,
                    "deckHash": record.deck_hash,
                    "deck": _without_capability_fields(record.deck_json),
                    "generation": _safe_generation_metadata(record.generation_metadata),
                    "createdAt": record.created_at,
                    "status": record.status,
                    "profileRevision": record.profile_revision,
                    "provenance": {"table": "future_calibration_hypothesis_decks"},
                }
                for record in hypothesis_decks
            ],
            "responses": [
                {
                    "responseId": record.response_id,
                    "calibrationId": record.calibration_id,
                    "deckId": record.deck_id,
                    "proposalId": record.proposal_id,
                    "response": record.response_json,
                    "evidence": record.evidence_json,
                    "epistemeRevision": record.episteme_revision,
                    "status": record.status,
                    "recordedAt": record.recorded_at,
                    "provenance": {"table": "future_calibration_hypothesis_responses"},
                }
                for record in hypothesis_responses
                if record.calibration_id in hypothesis_calibration_ids
            ],
            "actions": [
                {
                    "actionId": record.action_id,
                    "calibrationId": record.calibration_id,
                    "deckId": record.deck_id,
                    "proposalId": record.proposal_id,
                    "responseId": record.response_id,
                    "action": record.action_json,
                    "evidenceAction": record.evidence_action_json,
                    "epistemeRevision": record.episteme_revision,
                    "status": record.status,
                    "recordedAt": record.recorded_at,
                    "provenance": {"table": "future_calibration_hypothesis_actions"},
                }
                for record in hypothesis_actions
                if record.calibration_id in hypothesis_calibration_ids
            ],
        },
        "solveSessions": [
            {
                "sessionId": record.id,
                "puzzle": {
                    "puzzleId": puzzle_ids.get(record.puzzle_hash),
                    "puzzleHash": record.puzzle_hash,
                },
                "initialGrid": record.initial_grid,
                "acceptedSequence": record.accepted_seq,
                "status": record.status,
                "createdAt": record.created_at,
                "updatedAt": record.updated_at,
                "events": by_session_events[record.id],
                "analysis": None
                if record.id not in by_session_analysis
                else {
                    "version": by_session_analysis[record.id].analysis_version,
                    "analysis": by_session_analysis[record.id].analysis_json,
                    "finalized": by_session_analysis[record.id].finalized,
                    "updatedAt": by_session_analysis[record.id].updated_at,
                },
                "reflections": {
                    "deck": None
                    if record.id not in by_session_reflection_deck
                    else by_session_reflection_deck[record.id].deck_json,
                    "responses": by_session_reflection_responses[record.id],
                    "actions": by_session_reflection_actions[record.id],
                },
                "postgameAssociations": None
                if record.id not in by_session_postgame_run
                else {
                    "sessionId": record.id,
                    "requestHash": by_session_postgame_run[record.id].request_hash,
                    "status": by_session_postgame_run[record.id].status,
                    "paths": _without_capability_fields(by_session_postgame_run[record.id].paths_json or []),
                    "evidence": _without_capability_fields(by_session_postgame_run[record.id].evidence_json or []),
                    "generation": _safe_generation_metadata(by_session_postgame_run[record.id].generation_metadata),
                    "epistemeRevision": by_session_postgame_run[record.id].episteme_revision,
                    "createdAt": by_session_postgame_run[record.id].created_at,
                    "updatedAt": by_session_postgame_run[record.id].updated_at,
                    "responses": by_session_postgame_responses[record.id],
                },
                "provenance": {"table": "future_solve_sessions"},
            }
            for record in sessions
        ],
        "gridDraftJobs": [
            {
                "jobId": record.id,
                "idempotencyKey": record.idempotency_key,
                "requestDigest": record.request_digest,
                "request": _without_capability_fields(record.request_json),
                "state": record.state,
                "attempt": record.attempt,
                "cancelRequested": record.cancel_requested,
                "result": _without_capability_fields(record.result_json),
                "privateSelection": None
                if record.id not in private_selections
                else {
                    "selection": _without_capability_fields(
                        private_selections[record.id].selection_json
                    ),
                    "createdAt": private_selections[record.id].created_at,
                    "provenance": {"table": "future_grid_draft_private_selections"},
                },
                "error": record.error,
                "createdAt": record.created_at,
                "updatedAt": record.updated_at,
                "provenance": {"table": "future_grid_draft_jobs", "playable": False},
            }
            for record in grid_jobs
        ],
        "learningReviews": exported_learning_reviews(profile_id),
        "profileNarratives": [
            {
                "narrativeId": record.id,
                "epistemeRevision": record.episteme_revision,
                "sourceDigest": record.source_digest,
                "narrative": _without_capability_fields(record.narrative_json),
                "generation": _safe_generation_metadata(record.generation_metadata),
                "status": record.status,
                "createdAt": record.created_at,
                "updatedAt": record.updated_at,
                "provenance": {"table": "future_profile_narratives"},
            }
            for record in narratives
        ],
    }
    # Keep the row for every hypothesis deck even if its source calibration was
    # later unavailable; responses/actions can only be joined through those
    # deck-owned calibration identifiers.
    del hypothesis_deck_ids
    export["integrity"] = {
        "version": EXPORT_INTEGRITY_VERSION,
        "algorithm": "sha256",
        "value": archive_integrity_digest(export),
    }
    return export


@profile_export_api.get("/api/future/profile/<profile_id>/export")
def export_profile(profile_id):
    if not _same_origin():
        return _error("Cross-origin profile export is not allowed", 403)
    if not _valid_uuid(profile_id):
        return _error("Invalid profile id", 400)
    # SQLite's default deferred transactions don't necessarily establish a
    # read snapshot until the first write. BEGIN IMMEDIATE obtains the reserved
    # lock before SELECTs, so another local writer cannot produce a mixed
    # starting-profile/episteme export between queries.
    connection = db.session.connection()
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    try:
        estimated_bytes = _export_size_preflight(profile_id)
        if estimated_bytes > MAX_EXPORT_BYTES:
            db.session.rollback()
            return _error(
                "Profile export exceeds the response size limit",
                413,
                estimatedBytes=estimated_bytes,
                maxBytes=MAX_EXPORT_BYTES,
                sizeCheck="preflight",
            )
        value = _export_profile(profile_id)
        if value is None:
            db.session.rollback()
            return _error("Profile not found", 404)
        body = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        if len(body.encode("utf-8")) > MAX_EXPORT_BYTES:
            db.session.rollback()
            return _error("Profile export exceeds the response size limit", 413)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    response = Response(body, mimetype="application/json")
    response.headers["Cache-Control"] = "no-store"
    return response
