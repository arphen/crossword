"""Bounded, append-only host persistence for the nonverbal opening journal."""
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import UUID

from flask import Blueprint, jsonify, request
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.exceptions import RequestEntityTooLarge

from .database import db

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_SCRIPT = PROJECT_ROOT / "scripts" / "calibration-validator.cjs"
CATALOG_PATH = Path(__file__).with_name("future_catalog.json")
MAX_BODY_BYTES = 1024 * 1024

calibration_api = Blueprint("calibration_api", __name__)


class CalibrationSessionRecord(db.Model):
    """One bounded JSON journal per calibration capability."""

    __tablename__ = "future_calibration_sessions"

    id = db.Column(db.String(36), primary_key=True)
    revision = db.Column(db.Integer, nullable=False, default=1)
    payload = db.Column(db.JSON, nullable=False)


class CalibrationRuntimeUnavailable(RuntimeError):
    """Node or the fixed TypeScript calibration validator is unavailable."""


class CalibrationPayloadRejected(ValueError):
    """The shared TypeScript contract rejected an untrusted calibration."""


def _error(message, status):
    response = jsonify(error=message)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _valid_uuid(value):
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _same_origin():
    origin = request.headers.get("Origin")
    return not origin or origin == request.host_url.rstrip("/")


def _read_bounded_json():
    request.max_content_length = MAX_BODY_BYTES
    if (request.content_length or 0) > MAX_BODY_BYTES:
        return None, _error("Calibration payload is too large", 413)
    try:
        raw = request.get_data(cache=True)
    except RequestEntityTooLarge:
        return None, _error("Calibration payload is too large", 413)
    if len(raw) > MAX_BODY_BYTES:
        return None, _error("Calibration payload is too large", 413)
    try:
        value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON number")))
    except (ValueError, UnicodeDecodeError):
        return None, _error("Calibration payload must be valid JSON", 400)
    if not isinstance(value, dict):
        return None, _error("Calibration payload must be an object", 400)
    return value, None


def _catalog_stimuli():
    try:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CalibrationRuntimeUnavailable("The calibration catalog is unavailable") from error
    stimuli = catalog.get("stimuli") if isinstance(catalog, dict) else None
    items = stimuli.get("items") if isinstance(stimuli, dict) else None
    if not isinstance(items, list):
        raise CalibrationRuntimeUnavailable("The calibration stimulus catalog is unavailable")
    return items


def _run_validator(session):
    node = shutil.which("node")
    if not node or not BRIDGE_SCRIPT.is_file():
        raise CalibrationRuntimeUnavailable("The local calibration validator is unavailable")
    operation = {
        "operation": "validate",
        "session": session,
        "catalogStimuli": _catalog_stimuli(),
    }
    try:
        serialized = json.dumps(operation, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise CalibrationPayloadRejected("Calibration payload is not JSON-safe") from error
    if len(serialized.encode("utf-8")) > MAX_BODY_BYTES:
        raise CalibrationPayloadRejected("Calibration payload is too large")
    try:
        result = subprocess.run(
            [node, str(BRIDGE_SCRIPT)],
            input=serialized,
            text=True,
            capture_output=True,
            timeout=5,
            cwd=PROJECT_ROOT,
            env={"PATH": os.environ.get("PATH", "")},
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CalibrationRuntimeUnavailable("The local calibration validator did not respond") from error
    if result.returncode != 0:
        try:
            output = json.loads(result.stderr)
        except (ValueError, AttributeError):
            raise CalibrationRuntimeUnavailable("The local calibration validator could not start") from None
        message = output.get("error") if isinstance(output, dict) else None
        if not isinstance(message, str):
            raise CalibrationRuntimeUnavailable("The local calibration validator could not start")
        raise CalibrationPayloadRejected(message[:240])
    try:
        response = json.loads(result.stdout)
    except ValueError as error:
        raise CalibrationRuntimeUnavailable("The local calibration validator returned invalid JSON") from error
    if response != {"valid": True}:
        raise CalibrationRuntimeUnavailable("The local calibration validator returned an invalid result")


def _sequences(session):
    observations = session.get("observations")
    actions = session.get("actions")
    if not isinstance(observations, list) or not isinstance(actions, list):
        raise CalibrationPayloadRejected("Calibration observations and actions must be arrays")
    sequences = []
    for item in observations + actions:
        if not isinstance(item, dict) or type(item.get("sequence")) is not int or item["sequence"] < 1:
            raise CalibrationPayloadRejected("Calibration event sequence is invalid")
        sequences.append(item["sequence"])
    return sequences


def _has_active_response(session, movement):
    """Whether history has a response for this movement that is not retracted."""
    observations = {item["observationId"]: item for item in session["observations"]}
    active = {
        item["observationId"]
        for item in session["observations"]
        if item["response"]["kind"] == "choose"
    }
    for action in session["actions"]:
        if action["action"] == "retract":
            active.discard(action["targetObservationId"])
        else:
            active.add(action["targetObservationId"])
    return any(
        item["movement"] == movement
        and (
            item["response"]["kind"] == "pass"
            or item["observationId"] in active
        )
        for item in observations.values()
    )


def _validate_host_invariants(session, route_id):
    if not _valid_uuid(route_id) or session.get("calibrationId") != route_id:
        raise CalibrationPayloadRejected("Invalid calibration id")
    scope = session.get("scope")
    if not isinstance(scope, dict):
        raise CalibrationPayloadRejected("Invalid calibration scope")
    scope_id_key = {"profile": "profileId", "guest": "guestId"}.get(scope.get("kind"))
    if scope_id_key is None or not _valid_uuid(scope.get(scope_id_key)):
        raise CalibrationPayloadRejected("Invalid calibration scope id")
    sequences = _sequences(session)
    if sorted(sequences) != list(range(1, len(sequences) + 1)):
        raise CalibrationPayloadRejected("Observation and action sequences must be globally contiguous")


_IMMUTABLE_FIELDS = (
    "schemaVersion",
    "calibrationId",
    "scope",
    "bankVersion",
    "selectorVersion",
    "seed",
    "presentationMode",
    "createdAt",
)


def _validate_append(previous, candidate):
    for key in _IMMUTABLE_FIELDS:
        if previous[key] != candidate[key]:
            raise CalibrationPayloadRejected(f"Calibration field {key} cannot be changed")
    for key in ("observations", "actions"):
        old = previous[key]
        new = candidate[key]
        if len(new) < len(old) or new[: len(old)] != old:
            raise CalibrationPayloadRejected(f"Previously recorded calibration {key} are immutable")
    old_sequences = _sequences(previous)
    new_sequences = _sequences(candidate)
    old_max = max(old_sequences, default=0)
    appended = [sequence for sequence in new_sequences if sequence > old_max]
    if sorted(appended) != list(range(old_max + 1, len(new_sequences) + 1)):
        raise CalibrationPayloadRejected("New calibration events must append in sequence")
    old_cursor = previous["currentMovement"]
    new_cursor = candidate["currentMovement"]
    if new_cursor > old_cursor + 1:
        raise CalibrationPayloadRejected("The calibration cursor cannot skip a movement")
    if new_cursor == old_cursor + 1:
        if not _has_active_response(candidate, old_cursor):
            raise CalibrationPayloadRejected(
                "The current movement needs a response before the cursor can advance"
            )
    if previous["status"] != "in-progress":
        if candidate != previous:
            raise CalibrationPayloadRejected("A terminal calibration cannot be changed")
    elif candidate["status"] not in ("in-progress", "completed", "skipped"):
        raise CalibrationPayloadRejected("Invalid calibration status transition")
    if datetime.fromisoformat(candidate["updatedAt"].replace("Z", "+00:00")) < datetime.fromisoformat(previous["updatedAt"].replace("Z", "+00:00")):
        raise CalibrationPayloadRejected("Calibration updatedAt cannot move backwards")


def _etag(revision):
    return f"calibration-{revision}"


def _session_response(record, status=200):
    response = jsonify(calibration=record.payload, revision=record.revision)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    response.set_etag(_etag(record.revision))
    return response


def _conflict(record, message="Calibration changed since it was read"):
    response = jsonify(error=message, revision=record.revision)
    response.status_code = 409
    response.headers["Cache-Control"] = "no-store"
    response.set_etag(_etag(record.revision))
    return response


def _has_if_match():
    return not request.if_match.star_tag and bool(request.if_match.as_set())


def _same_body(record, candidate):
    return _canonical_json(record.payload) == _canonical_json(candidate)


@calibration_api.route("/api/future/calibrations/<calibration_id>", methods=["GET", "PUT"])
def calibration_session(calibration_id):
    if not _valid_uuid(calibration_id):
        return _error("Invalid calibration id", 400)
    if request.method == "GET":
        record = db.session.get(CalibrationSessionRecord, calibration_id)
        if record is None:
            return _error("Calibration not found", 404)
        return _session_response(record)

    if not _same_origin():
        return _error("Cross-origin calibration writes are not allowed", 403)
    candidate, error = _read_bounded_json()
    if error:
        return error
    try:
        _validate_host_invariants(candidate, calibration_id)
        _run_validator(candidate)
    except CalibrationRuntimeUnavailable as error:
        db.session.rollback()
        return _error(str(error), 503)
    except CalibrationPayloadRejected as error:
        db.session.rollback()
        return _error(str(error), 422)

    record = db.session.get(CalibrationSessionRecord, calibration_id)
    if record is None:
        if request.headers.get("If-None-Match", "").strip() != "*":
            return _error("Calibration creation requires If-None-Match: *", 409)
        record = CalibrationSessionRecord(id=calibration_id, revision=1, payload=candidate)
        db.session.add(record)
        try:
            db.session.commit()
        except (IntegrityError, OperationalError):
            db.session.rollback()
            current = db.session.get(CalibrationSessionRecord, calibration_id)
            if current is None:
                raise
            if _same_body(current, candidate):
                return _session_response(current)
            return _conflict(current, "A different calibration was created first")
        return _session_response(record, 201)

    if _same_body(record, candidate):
        if request.headers.get("If-None-Match", "").strip() == "*" or _has_if_match():
            return _session_response(record)
        return _conflict(record, "Calibration updates require If-Match from the latest read")
    if request.headers.get("If-None-Match", "").strip() == "*":
        return _conflict(record)
    if not _has_if_match():
        return _conflict(record, "Calibration updates require If-Match from the latest read")

    expected = _etag(record.revision)
    if not request.if_match.contains(expected):
        return _conflict(record)
    try:
        _validate_append(record.payload, candidate)
    except (CalibrationPayloadRejected, KeyError, TypeError, ValueError) as error:
        db.session.rollback()
        return _error(str(error), 422)

    new_revision = record.revision + 1
    changed = db.session.execute(
        update(CalibrationSessionRecord)
        .where(
            CalibrationSessionRecord.id == calibration_id,
            CalibrationSessionRecord.revision == record.revision,
        )
        .values(payload=candidate, revision=new_revision)
    )
    if changed.rowcount != 1:
        db.session.rollback()
        current = db.session.get(CalibrationSessionRecord, calibration_id)
        return _conflict(current) if current is not None else _error("Calibration not found", 404)
    db.session.commit()
    # Refresh because this identity may have been loaded before the CAS update.
    db.session.expire_all()
    saved = db.session.get(CalibrationSessionRecord, calibration_id)
    return _session_response(saved)
