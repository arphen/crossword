"""Destructive local profile lifecycle operations for the /future lane.

The profile id is a local bearer capability.  Deletion removes every
profile-owned journal, episteme record, reflection, job, and private candidate
in one SQLite transaction.  Shared puzzle manifests are deliberately retained:
they may be referenced by other local sessions and contain no profile id.
"""

from uuid import UUID

from flask import Blueprint, jsonify, request

from .calibration_api import CalibrationSessionRecord
from .calibration_hypothesis_api import (
    CalibrationHypothesisActionRecord,
    CalibrationHypothesisDeckRecord,
    CalibrationHypothesisResponseRecord,
)
from .database import db
from .episteme_store import EpistemeProfileRecord
from .future import StartingProfile
from .future_grid_jobs import FutureGridDraftJob, FutureGridDraftPrivateSelection
from .future_puzzles import FuturePuzzleV2CandidateRecord, FutureSolveAnalysisRecord
from .learning_review import FutureLearningReviewRecord
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


profile_lifecycle_api = Blueprint("profile_lifecycle_api", __name__)


def _valid_uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (AttributeError, ValueError):
        return False


def _same_origin():
    origin = request.headers.get("Origin")
    return not origin or origin == request.host_url.rstrip("/")


def _error(message, status):
    response = jsonify(error=message)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _profile_calibration_ids(profile_id):
    records = CalibrationSessionRecord.query.all()
    return [
        record.id
        for record in records
        if isinstance(record.payload, dict)
        and isinstance(record.payload.get("scope"), dict)
        and record.payload["scope"].get("kind") == "profile"
        and record.payload["scope"].get("profileId") == profile_id
    ]


@profile_lifecycle_api.delete("/api/future/profile/<profile_id>")
def delete_profile(profile_id):
    if not _same_origin():
        return _error("Cross-origin profile deletion is not allowed", 403)
    if not _valid_uuid(profile_id):
        return _error("Invalid profile id", 400)
    if db.session.get(StartingProfile, profile_id) is None:
        return _error("Profile not found", 404)

    calibration_ids = _profile_calibration_ids(profile_id)
    sessions = PersonalSolveSession.query.filter_by(profile_id=profile_id).all()
    session_ids = [record.id for record in sessions]
    jobs = FutureGridDraftJob.query.filter_by(profile_id=profile_id).all()
    job_ids = [record.id for record in jobs]

    # Remove children first.  There are intentionally no cross-profile foreign
    # keys in the local schema, so explicit scopes keep this safe on SQLite and
    # make the deletion auditable in tests.
    if session_ids:
        PostgameAssociationResponseRecord.query.filter(
            PostgameAssociationResponseRecord.session_id.in_(session_ids)
        ).delete(synchronize_session=False)
        PostgameAssociationRunRecord.query.filter(
            PostgameAssociationRunRecord.session_id.in_(session_ids)
        ).delete(synchronize_session=False)
        FutureReflectionActionRecord.query.filter(
            FutureReflectionActionRecord.session_id.in_(session_ids)
        ).delete(synchronize_session=False)
        FutureReflectionResponseRecord.query.filter(
            FutureReflectionResponseRecord.session_id.in_(session_ids)
        ).delete(synchronize_session=False)
        FutureReflectionDeckRecord.query.filter(
            FutureReflectionDeckRecord.session_id.in_(session_ids)
        ).delete(synchronize_session=False)
        FutureSolveAnalysisRecord.query.filter(
            FutureSolveAnalysisRecord.session_id.in_(session_ids)
        ).delete(synchronize_session=False)
        PersonalSolveEvent.query.filter(
            PersonalSolveEvent.session_id.in_(session_ids)
        ).delete(synchronize_session=False)
        PersonalSolveSession.query.filter(
            PersonalSolveSession.id.in_(session_ids)
        ).delete(synchronize_session=False)

    if calibration_ids:
        CalibrationHypothesisActionRecord.query.filter(
            CalibrationHypothesisActionRecord.calibration_id.in_(calibration_ids)
        ).delete(synchronize_session=False)
        CalibrationHypothesisResponseRecord.query.filter(
            CalibrationHypothesisResponseRecord.calibration_id.in_(calibration_ids)
        ).delete(synchronize_session=False)
        CalibrationHypothesisDeckRecord.query.filter(
            CalibrationHypothesisDeckRecord.calibration_id.in_(calibration_ids)
        ).delete(synchronize_session=False)
        CalibrationSessionRecord.query.filter(
            CalibrationSessionRecord.id.in_(calibration_ids)
        ).delete(synchronize_session=False)

    if job_ids:
        FutureGridDraftPrivateSelection.query.filter(
            FutureGridDraftPrivateSelection.job_id.in_(job_ids)
        ).delete(synchronize_session=False)
        FuturePuzzleV2CandidateRecord.query.filter(
            FuturePuzzleV2CandidateRecord.job_id.in_(job_ids),
            FuturePuzzleV2CandidateRecord.profile_id == profile_id,
        ).delete(synchronize_session=False)
        FutureGridDraftJob.query.filter(
            FutureGridDraftJob.id.in_(job_ids)
        ).delete(synchronize_session=False)

    FutureLearningReviewRecord.query.filter_by(profile_id=profile_id).delete(
        synchronize_session=False
    )
    ProfileNarrativeRecord.query.filter_by(profile_id=profile_id).delete(
        synchronize_session=False
    )

    EpistemeProfileRecord.query.filter_by(id=profile_id).delete(
        synchronize_session=False
    )
    StartingProfile.query.filter_by(id=profile_id).delete(
        synchronize_session=False
    )
    db.session.commit()

    response = jsonify(
        {
            "deleted": True,
            "profileId": profile_id,
            "sharedPuzzleManifests": "retained",
        }
    )
    response.headers["Cache-Control"] = "no-store"
    return response
