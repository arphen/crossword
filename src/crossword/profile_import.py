"""Validated restore of a local personal-episteme archive.

Archives are host exports, not credentials.  Restore therefore keeps the
profile capability id from the archive, refuses to overwrite an existing
profile, and recreates the profile-owned journal rows in one transaction.
Shared puzzle manifests are intentionally not imported: the export contains
only their hashes and ids, and a later solve can use a manifest already
registered on this host.
"""

from hashlib import sha256
import json
import secrets
from uuid import UUID

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from .calibration_api import CalibrationSessionRecord
from .calibration_hypothesis_api import (
    CalibrationHypothesisActionRecord,
    CalibrationHypothesisDeckRecord,
    CalibrationHypothesisResponseRecord,
)
from .database import db
from .episteme_store import EpistemeProfileRecord
from .future import StartingProfile, derive_profile, validate_draft
from .future_grid_jobs import FutureGridDraftJob, FutureGridDraftPrivateSelection
from .future_puzzles import FuturePuzzleV2CandidateRecord, FutureSolveAnalysisRecord
from .learning_review import FutureLearningReviewRecord
from .postgame_associations_api import (
    PostgameAssociationResponseRecord,
    PostgameAssociationRunRecord,
)
from .profile_narrative_api import ProfileNarrativeRecord, _validate_narrative
from .profile_export import (
    EXPORT_INTEGRITY_VERSION,
    EXPORT_SCHEMA_VERSION,
    MAX_EXPORT_BYTES,
    archive_integrity_digest,
)
from .reflection_api import (
    FutureReflectionActionRecord,
    FutureReflectionDeckRecord,
    FutureReflectionResponseRecord,
)
from .session_journal import PersonalSolveEvent, PersonalSolveSession


profile_import_api = Blueprint("profile_import_api", __name__)
MAX_IMPORT_BYTES = MAX_EXPORT_BYTES
_SHA256 = set("0123456789abcdef")


def _valid_uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (AttributeError, ValueError):
        return False


def _same_origin():
    origin = request.headers.get("Origin")
    return not origin or origin == request.host_url.rstrip("/")


def _error(message, status, **extra):
    response = jsonify(error=message, **extra)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _read_archive():
    request.max_content_length = MAX_IMPORT_BYTES
    if (request.content_length or 0) > MAX_IMPORT_BYTES:
        return None, _error("Profile archive is too large", 413)
    try:
        raw = request.get_data(cache=True)
    except RequestEntityTooLarge:
        return None, _error("Profile archive is too large", 413)
    if len(raw) > MAX_IMPORT_BYTES:
        return None, _error("Profile archive is too large", 413)
    try:
        archive = json.loads(
            raw,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite")),
        )
    except (UnicodeDecodeError, ValueError):
        return None, _error("Profile archive must be valid JSON", 400)
    if not isinstance(archive, dict):
        return None, _error("Profile archive must be an object", 422)
    integrity = archive.get("integrity")
    if integrity is not None:
        if (
            not isinstance(integrity, dict)
            or set(integrity) != {"version", "algorithm", "value"}
            or integrity.get("version") != EXPORT_INTEGRITY_VERSION
            or integrity.get("algorithm") != "sha256"
            or not isinstance(integrity.get("value"), str)
            or len(integrity["value"]) != 64
            or any(char not in _SHA256 for char in integrity["value"].lower())
            or integrity["value"].lower() != archive_integrity_digest(archive)
        ):
            return None, _error("Profile archive integrity check failed", 422)
    return archive, None


def _id(value, label):
    if not _valid_uuid(value):
        raise ValueError(f"Invalid {label}")
    return value


def _text(value, label, maximum=512):
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError(f"Invalid {label}")
    return value


def _hash(value, label):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in _SHA256 for char in value.lower())
    ):
        raise ValueError(f"Invalid {label}")
    return value


def _timestamp(value, label):
    return _text(value, label, 80)


def _dict(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"Invalid {label}")
    return value


def _list(value, label):
    if not isinstance(value, list):
        raise ValueError(f"Invalid {label}")
    return value


def _archive_rows(archive, profile_id):
    """Validate and normalize an archive before any database mutation."""
    if archive.get("format") != "crossword-personal-episteme-export":
        raise ValueError("Unsupported profile archive format")
    if archive.get("schemaVersion") != EXPORT_SCHEMA_VERSION:
        raise ValueError("Unsupported profile archive schema")
    if archive.get("profileId") != profile_id:
        raise ValueError("Archive profile id does not match the import target")

    starting = _dict(archive.get("startingProfile"), "starting profile")
    draft = _dict(starting.get("draft"), "starting profile draft")
    if draft.get("id") != profile_id:
        raise ValueError("Starting profile id does not match the archive")
    try:
        normalized_draft = validate_draft(draft, profile_id)
    except (TypeError, ValueError) as error:
        raise ValueError("Starting profile draft is invalid") from error
    starting_id = _id(starting.get("recordId"), "starting profile record id")
    updated_at = _timestamp(starting.get("updatedAt"), "starting profile timestamp")
    starting_profile = StartingProfile(
        id=profile_id,
        draft=normalized_draft,
        # Re-derive the provisional profile from the shared catalog.  The
        # archive's prose is user-editable JSON and is not a host contract.
        profile=derive_profile(normalized_draft),
        updated_at=updated_at,
    )

    episteme_value = archive.get("episteme")
    episteme = None
    if episteme_value is not None:
        episteme_value = _dict(episteme_value, "episteme")
        if episteme_value.get("recordId") != profile_id:
            raise ValueError("Episteme record id does not match the archive")
        profile_json = _dict(episteme_value.get("profile"), "episteme profile")
        if profile_json.get("profileId") != profile_id:
            raise ValueError("Episteme profile id does not match the archive")
        revision = episteme_value.get("revision")
        if type(revision) is not int or revision < 0:
            raise ValueError("Invalid episteme revision")
        episteme = EpistemeProfileRecord(
            id=profile_id,
            revision=revision,
            profile_json=profile_json,
            updated_at=_timestamp(
                episteme_value.get("updatedAt"), "episteme timestamp"
            ),
        )

    calibrations = []
    calibration_ids = set()
    for value in _list(archive.get("calibrations", []), "calibrations"):
        value = _dict(value, "calibration")
        calibration_id = _id(value.get("recordId"), "calibration id")
        if calibration_id in calibration_ids:
            raise ValueError("Duplicate calibration id")
        calibration_ids.add(calibration_id)
        revision = value.get("revision")
        payload = _dict(value.get("payload"), "calibration payload")
        scope = _dict(payload.get("scope"), "calibration scope")
        if scope.get("kind") != "profile" or scope.get("profileId") != profile_id:
            raise ValueError("Calibration is not scoped to the archive profile")
        if payload.get("calibrationId") != calibration_id:
            raise ValueError("Calibration id does not match its payload")
        if type(revision) is not int or revision < 1:
            raise ValueError("Invalid calibration revision")
        calibrations.append(
            CalibrationSessionRecord(
                id=calibration_id, revision=revision, payload=payload
            )
        )

    hypotheses = _dict(
        archive.get("calibrationHypotheses", {}), "calibration hypotheses"
    )
    decks = []
    deck_ids = set()
    deck_by_calibration = {}
    for value in _list(hypotheses.get("decks", []), "hypothesis decks"):
        value = _dict(value, "hypothesis deck")
        calibration_id = _id(value.get("calibrationId"), "hypothesis calibration id")
        deck_id = _id(value.get("deckId"), "hypothesis deck id")
        if calibration_id not in calibration_ids or deck_id in deck_ids:
            raise ValueError("Hypothesis deck references an unknown or duplicate id")
        deck_ids.add(deck_id)
        deck_by_calibration[calibration_id] = deck_id
        profile_revision = value.get("profileRevision")
        if profile_revision is not None and (
            type(profile_revision) is not int or profile_revision < 0
        ):
            raise ValueError("Invalid hypothesis profile revision")
        decks.append(
            CalibrationHypothesisDeckRecord(
                calibration_id=calibration_id,
                source_digest=_hash(
                    value.get("sourceDigest"), "hypothesis source digest"
                ),
                deck_id=deck_id,
                profile_id=profile_id,
                deck_json=_dict(value.get("deck"), "hypothesis deck body"),
                deck_hash=_hash(value.get("deckHash"), "hypothesis deck hash"),
                generation_metadata=_dict(
                    value.get("generation"), "hypothesis generation metadata"
                ),
                created_at=_timestamp(
                    value.get("createdAt"), "hypothesis deck timestamp"
                ),
                status=_text(value.get("status"), "hypothesis deck status", 32),
                profile_revision=profile_revision,
            )
        )

    responses = []
    response_ids = set()
    response_by_id = set()
    for value in _list(hypotheses.get("responses", []), "hypothesis responses"):
        value = _dict(value, "hypothesis response")
        response_id = _id(value.get("responseId"), "hypothesis response id")
        calibration_id = _id(value.get("calibrationId"), "hypothesis calibration id")
        deck_id = _id(value.get("deckId"), "hypothesis deck id")
        if (
            response_id in response_ids
            or calibration_id not in calibration_ids
            or deck_id not in deck_ids
        ):
            raise ValueError(
                "Hypothesis response references an unknown or duplicate id"
            )
        response_ids.add(response_id)
        response_by_id.add(response_id)
        responses.append(
            CalibrationHypothesisResponseRecord(
                response_id=response_id,
                calibration_id=calibration_id,
                deck_id=deck_id,
                proposal_id=_id(value.get("proposalId"), "hypothesis proposal id"),
                request_hash=sha256(
                    json.dumps(value.get("response"), sort_keys=True).encode()
                ).hexdigest(),
                response_json=_dict(value.get("response"), "hypothesis response body"),
                evidence_json=_dict(
                    value.get("evidence"), "hypothesis response evidence"
                ),
                episteme_revision=value.get("epistemeRevision"),
                status=_text(value.get("status"), "hypothesis response status", 32),
                recorded_at=_timestamp(
                    value.get("recordedAt"), "hypothesis response timestamp"
                ),
            )
        )

    actions = []
    action_ids = set()
    for value in _list(hypotheses.get("actions", []), "hypothesis actions"):
        value = _dict(value, "hypothesis action")
        action_id = _id(value.get("actionId"), "hypothesis action id")
        calibration_id = _id(value.get("calibrationId"), "hypothesis calibration id")
        deck_id = _id(value.get("deckId"), "hypothesis deck id")
        response_id = _id(value.get("responseId"), "hypothesis response id")
        if (
            action_id in action_ids
            or calibration_id not in calibration_ids
            or deck_id not in deck_ids
            or response_id not in response_by_id
        ):
            raise ValueError("Hypothesis action references an unknown or duplicate id")
        action_ids.add(action_id)
        action = _dict(value.get("action"), "hypothesis action body")
        actions.append(
            CalibrationHypothesisActionRecord(
                action_id=action_id,
                calibration_id=calibration_id,
                deck_id=deck_id,
                proposal_id=_id(value.get("proposalId"), "hypothesis proposal id"),
                response_id=response_id,
                request_hash=sha256(
                    json.dumps(action, sort_keys=True).encode()
                ).hexdigest(),
                action_json=action,
                evidence_action_json=_dict(
                    value.get("evidenceAction"), "hypothesis action evidence"
                ),
                episteme_revision=value.get("epistemeRevision"),
                status=_text(value.get("status"), "hypothesis action status", 32),
                recorded_at=_timestamp(
                    value.get("recordedAt"), "hypothesis action timestamp"
                ),
            )
        )

    sessions = []
    session_ids = set()
    event_ids = set()
    analyses = []
    reflection_decks = []
    reflection_responses = []
    reflection_actions = []
    postgame_runs = []
    postgame_responses = []
    postgame_response_ids = set()
    jobs = []
    private_selections = []
    learning_reviews = []
    narratives = []
    events = []
    job_ids = set()
    for value in _list(archive.get("solveSessions", []), "solve sessions"):
        value = _dict(value, "solve session")
        session_id = _id(value.get("sessionId"), "solve session id")
        if session_id in session_ids:
            raise ValueError("Duplicate solve session id")
        session_ids.add(session_id)
        puzzle = _dict(value.get("puzzle"), "solve puzzle reference")
        puzzle_hash = _hash(puzzle.get("puzzleHash"), "solve puzzle hash")
        initial_grid = _list(value.get("initialGrid"), "solve initial grid")
        if len(initial_grid) > 2000:
            raise ValueError("Solve initial grid is too large")
        accepted_seq = value.get("acceptedSequence")
        if type(accepted_seq) is not int or accepted_seq < 0:
            raise ValueError("Invalid solve accepted sequence")
        sessions.append(
            PersonalSolveSession(
                id=session_id,
                profile_id=profile_id,
                puzzle_hash=puzzle_hash,
                initial_grid=initial_grid,
                # Writer capabilities are deliberately omitted from exports.
                # Imported sessions are historical until a new local session
                # is created, so use an unreachable random digest here.
                writer_digest=secrets.token_hex(32),
                accepted_seq=accepted_seq,
                status=_text(value.get("status"), "solve session status", 32),
                created_at=_timestamp(
                    value.get("createdAt"), "solve session timestamp"
                ),
                updated_at=_timestamp(
                    value.get("updatedAt"), "solve session timestamp"
                ),
            )
        )
        for event in _list(value.get("events", []), "solve events"):
            event = _dict(event, "solve event")
            event_id = _id(event.get("eventId"), "solve event id")
            sequence = event.get("sequence")
            if event_id in event_ids or type(sequence) is not int or sequence < 1:
                raise ValueError("Invalid or duplicate solve event")
            event_ids.add(event_id)
            payload = _dict(event.get("payload"), "solve event payload")
            sessions[-1].accepted_seq = max(sessions[-1].accepted_seq, sequence)
            db_event = PersonalSolveEvent(
                session_id=session_id,
                seq=sequence,
                event_id=event_id,
                payload=payload,
                payload_hash=sha256(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
                recorded_at=_timestamp(
                    event.get("recordedAt"), "solve event timestamp"
                ),
            )
            events.append(db_event)
        analysis = value.get("analysis")
        if analysis is not None:
            analysis = _dict(analysis, "solve analysis")
            analyses.append(
                FutureSolveAnalysisRecord(
                    session_id=session_id,
                    puzzle_hash=puzzle_hash,
                    analysis_version=_text(
                        analysis.get("version"), "analysis version", 120
                    ),
                    analysis_json=_dict(analysis.get("analysis"), "analysis body"),
                    finalized=bool(analysis.get("finalized")),
                    updated_at=_timestamp(
                        analysis.get("updatedAt"), "analysis timestamp"
                    ),
                )
            )
        reflections = _dict(value.get("reflections", {}), "solve reflections")
        deck = reflections.get("deck")
        if deck is not None:
            reflection_decks.append(
                FutureReflectionDeckRecord(
                    session_id=session_id,
                    deck_version=1,
                    deck_json=_dict(deck, "reflection deck"),
                    deck_hash=sha256(
                        json.dumps(deck, sort_keys=True).encode()
                    ).hexdigest(),
                    created_at=_timestamp(
                        value.get("updatedAt"), "reflection deck timestamp"
                    ),
                )
            )
        for response in _list(reflections.get("responses", []), "reflection responses"):
            response = _dict(response, "reflection response")
            reflection_responses.append(
                FutureReflectionResponseRecord(
                    response_id=_id(
                        response.get("responseId"), "reflection response id"
                    ),
                    session_id=session_id,
                    card_id=_text(response.get("cardId"), "reflection card id", 160),
                    response_hash=sha256(
                        json.dumps(response.get("response"), sort_keys=True).encode()
                    ).hexdigest(),
                    response_json=_dict(
                        response.get("response"), "reflection response body"
                    ),
                    evidence_json=response.get("evidence"),
                    episteme_revision=response.get("epistemeRevision"),
                    status=_text(
                        response.get("status"), "reflection response status", 32
                    ),
                    recorded_at=_timestamp(
                        response.get("recordedAt"), "reflection response timestamp"
                    ),
                )
            )
        for action in _list(reflections.get("actions", []), "reflection actions"):
            action = _dict(action, "reflection action")
            reflection_actions.append(
                FutureReflectionActionRecord(
                    action_id=_id(action.get("actionId"), "reflection action id"),
                    session_id=session_id,
                    card_id=_text(action.get("cardId"), "reflection card id", 160),
                    target_response_id=_id(
                        action.get("targetResponseId"), "reflection response id"
                    ),
                    action_hash=sha256(
                        json.dumps(action.get("action"), sort_keys=True).encode()
                    ).hexdigest(),
                    action_json=_dict(action.get("action"), "reflection action body"),
                    evidence_action_json=action.get("evidenceAction"),
                    episteme_revision=action.get("epistemeRevision"),
                    status=_text(action.get("status"), "reflection action status", 32),
                    recorded_at=_timestamp(
                        action.get("recordedAt"), "reflection action timestamp"
                    ),
                )
            )
        postgame = value.get("postgameAssociations")
        if postgame is not None:
            postgame = _dict(postgame, "postgame associations")
            if postgame.get("sessionId") != session_id:
                raise ValueError("Postgame association session id does not match")
            postgame_runs.append(
                PostgameAssociationRunRecord(
                    session_id=session_id,
                    profile_id=profile_id,
                    request_hash=_hash(postgame.get("requestHash"), "postgame request hash"),
                    status=_text(postgame.get("status"), "postgame association status", 32),
                    paths_json=_list(postgame.get("paths", []), "postgame association paths"),
                    evidence_json=_list(postgame.get("evidence", []), "postgame association evidence"),
                    generation_metadata=_dict(postgame.get("generation", {}), "postgame generation metadata"),
                    episteme_revision=postgame.get("epistemeRevision"),
                    created_at=_timestamp(postgame.get("createdAt"), "postgame association timestamp"),
                    updated_at=_timestamp(postgame.get("updatedAt"), "postgame association timestamp"),
                )
            )
            for response in _list(postgame.get("responses", []), "postgame association responses"):
                response = _dict(response, "postgame association response")
                response_id = _id(response.get("responseId"), "postgame association response id")
                if response_id in postgame_response_ids:
                    raise ValueError("Duplicate postgame association response id")
                postgame_response_ids.add(response_id)
                postgame_responses.append(
                    PostgameAssociationResponseRecord(
                        response_id=response_id,
                        session_id=session_id,
                        profile_id=profile_id,
                        association_id=_id(response.get("associationId"), "postgame association id"),
                        request_hash=sha256(
                            json.dumps(response.get("response"), sort_keys=True).encode()
                        ).hexdigest(),
                        response_json=_dict(response.get("response"), "postgame association response body"),
                        evidence_json=_dict(response.get("evidence"), "postgame association response evidence"),
                        episteme_revision=response.get("epistemeRevision"),
                        status=_text(response.get("status"), "postgame association response status", 32),
                        recorded_at=_timestamp(response.get("recordedAt"), "postgame association response timestamp"),
                    )
                )

    for value in _list(archive.get("gridDraftJobs", []), "grid draft jobs"):
        value = _dict(value, "grid draft job")
        job_id = _id(value.get("jobId"), "grid job id")
        if job_id in job_ids:
            raise ValueError("Duplicate grid job id")
        job_ids.add(job_id)
        idempotency_key = _id(value.get("idempotencyKey"), "grid idempotency key")
        attempt = value.get("attempt")
        if type(attempt) is not int or attempt < 0:
            raise ValueError("Invalid grid job attempt")
        jobs.append(
            FutureGridDraftJob(
                id=job_id,
                profile_id=profile_id,
                idempotency_key=idempotency_key,
                request_digest=_hash(value.get("requestDigest"), "grid request digest"),
                request_json=_dict(value.get("request"), "grid request"),
                state=_text(value.get("state"), "grid job state", 32),
                attempt=attempt,
                cancel_requested=bool(value.get("cancelRequested")),
                result_json=value.get("result"),
                error=value.get("error"),
                created_at=_timestamp(value.get("createdAt"), "grid job timestamp"),
                updated_at=_timestamp(value.get("updatedAt"), "grid job timestamp"),
            )
        )
        selection = value.get("privateSelection")
        if selection is not None:
            selection = _dict(selection, "grid private selection")
            private_selections.append(
                FutureGridDraftPrivateSelection(
                    job_id=job_id,
                    profile_id=profile_id,
                    selection_json=_dict(
                        selection.get("selection"), "grid private selection body"
                    ),
                    created_at=_timestamp(
                        selection.get("createdAt"), "grid selection timestamp"
                    ),
                )
            )

    review_ids = set()
    for value in _list(archive.get("learningReviews", []), "learning reviews"):
        value = _dict(value, "learning review")
        review_id = _id(value.get("reviewId"), "learning review id")
        if review_id in review_ids:
            raise ValueError("Duplicate learning review id")
        review_ids.add(review_id)
        language = value.get("language")
        response = value.get("response")
        mode = value.get("mode")
        if (
            not isinstance(language, str)
            or not 1 <= len(language) <= 16
            or response not in {"remembered", "not-yet", "pass"}
            or mode not in {"independent", "assisted"}
        ):
            raise ValueError("Invalid learning review")
        learning_reviews.append(
            FutureLearningReviewRecord(
                id=review_id,
                profile_id=profile_id,
                task_id=_text(value.get("taskId"), "learning review task id", 240),
                language=language,
                source_evidence_id=_text(
                    value.get("sourceEvidenceId"), "learning review evidence id", 240
                ),
                response=response,
                input_mode=mode,
                recorded_at=_timestamp(
                    value.get("recordedAt"), "learning review timestamp"
                ),
            )
        )

    narrative_ids = set()
    for value in _list(archive.get("profileNarratives", []), "profile narratives"):
        value = _dict(value, "profile narrative")
        narrative_id = _id(value.get("narrativeId"), "profile narrative id")
        if narrative_id in narrative_ids:
            raise ValueError("Duplicate profile narrative id")
        narrative_ids.add(narrative_id)
        revision = value.get("epistemeRevision")
        if type(revision) is not int or revision < 0:
            raise ValueError("Invalid profile narrative episteme revision")
        source_digest = _hash(value.get("sourceDigest"), "profile narrative source digest")
        narrative = value.get("narrative")
        if narrative is not None:
            if not isinstance(narrative, dict):
                raise ValueError("Invalid profile narrative body")
            evidence_ids = {"starting-profile"}
            if episteme is not None:
                evidence_ids.update(
                    item.get("evidenceId")
                    for item in episteme.profile_json.get("evidence", [])
                    if isinstance(item, dict) and isinstance(item.get("evidenceId"), str)
                )
            try:
                narrative = _validate_narrative(narrative, evidence_ids)
            except (TypeError, ValueError) as error:
                raise ValueError("Profile narrative is not evidence-bound") from error
        status = _text(value.get("status"), "profile narrative status", 32)
        narratives.append(
            ProfileNarrativeRecord(
                id=narrative_id,
                profile_id=profile_id,
                episteme_revision=revision,
                source_digest=source_digest,
                narrative_json=narrative,
                generation_metadata=_dict(value.get("generation", {}), "profile narrative generation metadata"),
                status=status,
                created_at=_timestamp(value.get("createdAt"), "profile narrative timestamp"),
                updated_at=_timestamp(value.get("updatedAt"), "profile narrative timestamp"),
            )
        )

    return {
        "starting": starting_profile,
        "episteme": episteme,
        "calibrations": calibrations,
        "decks": decks,
        "responses": responses,
        "actions": actions,
        "sessions": sessions,
        "events": events,
        "analyses": analyses,
        "reflectionDecks": reflection_decks,
        "reflectionResponses": reflection_responses,
        "reflectionActions": reflection_actions,
        "jobs": jobs,
        "privateSelections": private_selections,
        "learningReviews": learning_reviews,
        "narratives": narratives,
        "postgameRuns": postgame_runs,
        "postgameResponses": postgame_responses,
        "ids": {
            "calibrations": calibration_ids,
            "decks": deck_ids,
            "responses": response_ids,
            "actions": action_ids,
            "sessions": session_ids,
            "events": event_ids,
            "jobs": job_ids,
            "learningReviews": review_ids,
            "postgameResponses": postgame_response_ids,
            "narratives": narrative_ids,
        },
        "startingId": starting_id,
    }


def _existing_ids(rows):
    """Return whether any imported global identity is already occupied."""
    checks = (
        (
            CalibrationSessionRecord,
            CalibrationSessionRecord.id,
            rows["ids"]["calibrations"],
        ),
        (
            CalibrationHypothesisDeckRecord,
            CalibrationHypothesisDeckRecord.deck_id,
            rows["ids"]["decks"],
        ),
        (
            CalibrationHypothesisResponseRecord,
            CalibrationHypothesisResponseRecord.response_id,
            rows["ids"]["responses"],
        ),
        (
            CalibrationHypothesisActionRecord,
            CalibrationHypothesisActionRecord.action_id,
            rows["ids"]["actions"],
        ),
        (PersonalSolveSession, PersonalSolveSession.id, rows["ids"]["sessions"]),
        (PersonalSolveEvent, PersonalSolveEvent.event_id, rows["ids"]["events"]),
        (
            FutureReflectionResponseRecord,
            FutureReflectionResponseRecord.response_id,
            {record.response_id for record in rows["reflectionResponses"]},
        ),
        (
            FutureReflectionActionRecord,
            FutureReflectionActionRecord.action_id,
            {record.action_id for record in rows["reflectionActions"]},
        ),
        (
            PostgameAssociationResponseRecord,
            PostgameAssociationResponseRecord.response_id,
            rows["ids"]["postgameResponses"],
        ),
        (FutureGridDraftJob, FutureGridDraftJob.id, rows["ids"]["jobs"]),
        (
            FutureLearningReviewRecord,
            FutureLearningReviewRecord.id,
            rows["ids"]["learningReviews"],
        ),
        (
            ProfileNarrativeRecord,
            ProfileNarrativeRecord.id,
            rows["ids"]["narratives"],
        ),
    )
    for model, column, values in checks:
        if not values:
            continue
        if db.session.query(model).filter(column.in_(values)).first() is not None:
            return True
    return False


@profile_import_api.post("/api/future/profile/<profile_id>/import")
def import_profile(profile_id):
    if not _same_origin():
        return _error("Cross-origin profile import is not allowed", 403)
    if not _valid_uuid(profile_id):
        return _error("Invalid profile id", 400)
    archive, read_error = _read_archive()
    if read_error:
        return read_error
    if db.session.get(StartingProfile, profile_id) is not None:
        return _error(
            "Profile already exists; delete it before importing this archive", 409
        )
    try:
        rows = _archive_rows(archive, profile_id)
    except (TypeError, ValueError, KeyError, RecursionError):
        db.session.rollback()
        return _error("Profile archive failed validation", 422)
    if _existing_ids(rows):
        db.session.rollback()
        return _error(
            "Profile archive contains records already present on this host", 409
        )

    try:
        db.session.add(rows["starting"])
        if rows["episteme"] is not None:
            db.session.add(rows["episteme"])
        db.session.add_all(
            rows["calibrations"] + rows["decks"] + rows["responses"] + rows["actions"]
        )
        db.session.add_all(rows["sessions"] + rows["events"] + rows["analyses"])
        db.session.add_all(
            rows["reflectionDecks"]
            + rows["reflectionResponses"]
            + rows["reflectionActions"]
        )
        db.session.add_all(rows["postgameRuns"] + rows["postgameResponses"])
        db.session.add_all(rows["jobs"] + rows["privateSelections"])
        db.session.add_all(rows["learningReviews"])
        db.session.add_all(rows["narratives"])
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _error("Profile archive could not be restored", 409)
    response = jsonify(
        {
            "imported": True,
            "profileId": profile_id,
            "sharedPuzzleManifests": "referenced-by-id-only",
            "historicalSolveSessions": len(rows["sessions"]),
        }
    )
    response.headers["Cache-Control"] = "no-store"
    return response, 201
