"""Local capability-scoped revision API for explicit episteme controls."""
from uuid import UUID

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from .database import db
from .episteme_store import (
    MAX_COMMAND_BYTES,
    EpistemeCommandRejected,
    EpistemeProfileRecord,
    EpistemeRevisionConflict,
    EpistemeRuntimeUnavailable,
    apply_episteme_command,
    get_or_create_episteme_profile,
    now_utc_iso,
    project_episteme_profile,
)
from .future import StartingProfile

episteme_api = Blueprint("episteme_api", __name__)


def _error(message, status):
    response = jsonify(error=message)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _valid_uuid(value):
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _local_origin():
    origin = request.headers.get("Origin")
    return not origin or origin == request.host_url.rstrip("/")


def _get_starting_profile(profile_id):
    if not _valid_uuid(profile_id):
        return None, _error("Invalid profile id", 400)
    record = db.session.get(StartingProfile, profile_id)
    if record is None:
        return None, _error("Profile not found", 404)
    return record, None


@episteme_api.get("/api/future/profile/<profile_id>/episteme")
def read_episteme(profile_id):
    starting, error = _get_starting_profile(profile_id)
    if error:
        return error
    try:
        record = get_or_create_episteme_profile(profile_id, starting.updated_at or now_utc_iso())
        profile = project_episteme_profile(record.profile_json, now_utc_iso())
    except EpistemeRuntimeUnavailable:
        db.session.rollback()
        return _error("The local profile reducer is unavailable", 503)
    except EpistemeCommandRejected as error:
        db.session.rollback()
        return _error(str(error), 422)
    response = jsonify(profile=profile, revision=record.revision, updatedAt=record.updated_at)
    response.headers["Cache-Control"] = "no-store"
    return response


@episteme_api.post("/api/future/profile/<profile_id>/episteme/updates")
def update_episteme(profile_id):
    if not _local_origin():
        return _error("Cross-origin profile writes are not allowed", 403)
    if (request.content_length or 0) > MAX_COMMAND_BYTES:
        return _error("Episteme update is too large", 413)
    # A missing Content-Length must not cause an unbounded body to be buffered.
    request.max_content_length = MAX_COMMAND_BYTES
    try:
        body = request.get_data(cache=True)
    except RequestEntityTooLarge:
        return _error("Episteme update is too large", 413)
    if len(body) > MAX_COMMAND_BYTES:
        return _error("Episteme update is too large", 413)
    starting, error = _get_starting_profile(profile_id)
    if error:
        return error
    value = request.get_json(silent=True)
    fields = {"expectedRevision", "updateId", "recordedAt", "evidence", "evidenceActions"}
    if not isinstance(value, dict) or set(value) != fields:
        return _error("Invalid episteme update", 422)
    if (
        type(value["expectedRevision"]) is not int
        or value["expectedRevision"] < 0
        or not _valid_uuid(value["updateId"])
        or not isinstance(value["recordedAt"], str)
        or len(value["recordedAt"]) > 40
        or not isinstance(value["evidence"], list)
        or len(value["evidence"]) > 100
        or not isinstance(value["evidenceActions"], list)
        or len(value["evidenceActions"]) > 100
        or (not value["evidence"] and not value["evidenceActions"])
    ):
        return _error("Invalid episteme update", 422)
    # Until reflection/calibration manifests are host-verified, only direct
    # player controls may enter this route. Browser-supplied solve analyses and
    # model proposals need separate evidence-linking gates.
    if any(not isinstance(item, dict) or item.get("type") != "explicit-preference" for item in value["evidence"]):
        return _error("Only explicit player controls are accepted on this route", 422)

    try:
        record = get_or_create_episteme_profile(profile_id, starting.updated_at or now_utc_iso())
        profile = record.profile_json
        explicit_ids = {
            item["evidenceId"]
            for item in profile.get("evidence", [])
            if item.get("type") == "explicit-preference"
        }
        explicit_ids.update(item.get("evidenceId") for item in value["evidence"] if isinstance(item, dict))
        if any(
            not isinstance(action, dict) or action.get("targetEvidenceId") not in explicit_ids
            for action in value["evidenceActions"]
        ):
            return _error("An evidence action must refer to an explicit player control", 422)
        command = {
            "updateId": value["updateId"],
            "profileId": profile_id,
            "baseRevision": value["expectedRevision"],
            "recordedAt": value["recordedAt"],
            "evidence": value["evidence"],
            "evidenceActions": value["evidenceActions"],
        }
        result, changed = apply_episteme_command(
            profile_id,
            record.revision,
            profile,
            command,
        )
    except EpistemeRuntimeUnavailable:
        db.session.rollback()
        return _error("The local profile reducer is unavailable", 503)
    except EpistemeRevisionConflict as error:
        db.session.rollback()
        return _error(str(error), 409)
    except EpistemeCommandRejected as error:
        db.session.rollback()
        return _error(str(error), 422)

    response = jsonify(
        profile=result["profile"],
        receipt=result["receipt"],
        revision=result["profile"]["revision"],
        replayed=result["replayed"],
        changed=changed,
    )
    response.headers["Cache-Control"] = "no-store"
    return response
