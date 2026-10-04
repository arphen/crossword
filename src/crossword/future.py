"""Local, capability-addressed starting profiles for the /future experiment.

Only catalog choices cross this boundary. Visual choices are recorded as
observations, not psychological traits or evidence of word knowledge.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
from uuid import UUID

from flask import Blueprint, jsonify, request
import requests
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, OperationalError

from .database import db

catalog = json.loads(Path(__file__).with_name("future_catalog.json").read_text())
future_api = Blueprint("future_api", __name__)
MODEL_PREFERENCE_CHOICES = {
    "automatic",
    "gemma4:26b",
    "qwen3.8:27b",
    "gemma4:31b",
    "gemma3:27b",
}


class StartingProfile(db.Model):
    __tablename__ = "future_starting_profiles"

    id = db.Column(db.String(36), primary_key=True)
    draft = db.Column(db.JSON, nullable=False)
    profile = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(db.String(40), nullable=False)


def validate_draft(value, profile_id):
    try:
        if not isinstance(profile_id, str) or str(UUID(profile_id)) != profile_id:
            raise ValueError("Invalid profile id")
    except (ValueError, AttributeError):
        raise ValueError("Invalid profile id") from None
    if not isinstance(value, dict) or value.get("version") != 1 or value.get("id") != profile_id:
        raise ValueError("Unsupported starting profile")
    if type(value.get("step")) is not int or not 0 <= value["step"] <= 5:
        raise ValueError("Invalid step")
    calibration_id = value.get("calibrationId")
    if calibration_id is not None:
        try:
            if not isinstance(calibration_id, str) or str(UUID(calibration_id)) != calibration_id:
                raise ValueError("Invalid calibration id")
        except (ValueError, AttributeError):
            raise ValueError("Invalid calibration id") from None
    presentation_mode = value.get("presentationMode", "visual")
    if presentation_mode not in ("visual", "monochrome", "text-equivalent"):
        raise ValueError("Invalid presentation mode")
    variation = value.get("variation")
    color_ids = {
        item["id"] for item in catalog.get("stimuli", {}).get("items", [])
        if item.get("kind") == "color"
    }
    if variation is not None and variation != "keep-original" and (
        not isinstance(variation, str) or variation not in color_ids
    ):
        raise ValueError("Invalid visual variation")
    objects = {item["id"]: item for item in catalog["objects"]}
    stimuli = {item["id"]: item for item in catalog.get("stimuli", {}).get("items", [])}
    selected = value.get("object")
    if selected is not None and (not isinstance(selected, str) or selected not in objects):
        raise ValueError("Unknown object")
    first_stimulus = value.get("firstStimulus")
    if first_stimulus is not None and (
        not isinstance(first_stimulus, str) or first_stimulus not in stimuli
    ):
        raise ValueError("Unknown first stimulus")
    if first_stimulus is None and selected is not None:
        first_stimulus = next(
            (item["id"] for item in stimuli.values() if selected in item.get("legacy_ids", [])),
            None,
        )
    companion = value.get("companion")
    companion_ids = {item["id"] for item in catalog["companions"]}
    if companion is not None and (
        not isinstance(companion, str)
        or companion not in companion_ids
        or (selected is not None and companion not in objects.get(selected, {}).get("companions", []))
    ):
        raise ValueError("Unknown companion")
    traces = value.get("traces")
    if not isinstance(traces, list) or len(traces) > 3 or any(word not in catalog["traces"] for word in traces):
        raise ValueError("Invalid traces")
    if len(set(traces)) != len(traces):
        raise ValueError("Duplicate traces")
    if value.get("weekday") not in [day["id"] for day in catalog["days"]]:
        raise ValueError("Invalid weekday")
    if value.get("learningLanguage") not in catalog["languages"]:
        raise ValueError("Invalid learning language")
    model_preference = value.get("modelPreference", "automatic")
    if model_preference not in MODEL_PREFERENCE_CHOICES:
        raise ValueError("Invalid model preference")
    excluded = value.get("excluded")
    if not isinstance(excluded, list) or len(excluded) > 24 or any(not isinstance(word, str) or len(word) > 40 for word in excluded):
        raise ValueError("Invalid excluded associations")
    if type(value.get("complete")) is not bool:
        raise ValueError("Invalid completion state")
    reflection = value.get("reflection")
    if reflection is not None:
        if not isinstance(reflection, dict) or not isinstance(reflection.get("model"), str) or len(reflection["model"]) > 100:
            raise ValueError("Invalid reflection")
        words = reflection.get("words")
        if not isinstance(words, list) or len(words) > 6 or any(not isinstance(word, str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z -]{1,28}", word) for word in words):
            raise ValueError("Invalid reflection words")
        reflection = {"words": list(dict.fromkeys(words)), "model": reflection["model"]}
    normalized = {
        **{key: value[key] for key in ("version", "id", "step", "object", "companion", "traces", "weekday", "learningLanguage", "excluded", "complete")},
        "reflection": reflection,
        "firstStimulus": first_stimulus,
        "modelPreference": model_preference,
    }
    if calibration_id is not None:
        normalized["calibrationId"] = calibration_id
    if variation is not None:
        normalized["variation"] = variation
    normalized["presentationMode"] = presentation_mode
    return normalized


def derive_profile(draft):
    selected = next((item for item in catalog["objects"] if item["id"] == draft["object"]), {})
    first_stimulus = next(
        (item for item in catalog.get("stimuli", {}).get("items", []) if item["id"] == draft.get("firstStimulus")),
        {},
    )
    companion = next((item for item in catalog["companions"] if item["id"] == draft["companion"]), {})
    reflection = draft.get("reflection") or {}
    candidates = list(dict.fromkeys(
        draft["traces"]
        + selected.get("words", [])
        + first_stimulus.get("association_seeds", [])
        + companion.get("words", [])
        + reflection.get("words", [])
    ))[:18]
    observations = [
        first_stimulus.get("accessible_label") or selected.get("label"),
        companion.get("label"),
    ]
    observations = [value for value in observations if value]
    prose = "An open beginning. Let the first puzzle be a place to discover what catches your attention."
    if observations:
        prose = " beside ".join(label if index == 0 else label[0].lower() + label[1:] for index, label in enumerate(observations)) + ". "
        if draft["traces"]:
            prose += "You kept " + ", ".join(f"“{word}”" for word in draft["traces"]) + ". "
        prose += "A few possible paths through words; nothing here has to stay."
    associations = [word for word in candidates if word not in draft["excluded"]]
    return {
        "version": 1, "prose": prose, "observations": observations,
        "associations": associations, "weekday": draft["weekday"],
        "learningLanguage": draft["learningLanguage"],
        "modelPreference": draft.get("modelPreference", "automatic"),
        "visualVariation": draft.get("variation"),
        "presentationMode": draft.get("presentationMode", "visual"),
        "source": "authored-associations", "reflection": reflection or None, "provisional": True, "knowledge": {},
        "generationBrief": {
            "seedWords": associations, "maximumSeedInfluence": 0.2,
            "difficulty": draft["weekday"], "puzzleLanguage": "English",
            "learningLanguage": draft["learningLanguage"],
            "modelPreference": draft.get("modelPreference", "automatic"),
            "visualVariation": draft.get("variation"),
            "instructions": "Treat seed words as optional thematic invitations. Infer neither personality nor knowledge. Give unfamiliar answers accessible crossings. Preserve clue grammar and the selected difficulty.",
        },
    }


def _profile_response(record, status=200):
    response = jsonify(profile=record.profile, updatedAt=record.updated_at)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    response.set_etag(record.updated_at)
    return response


def _profile_conflict(record, message="Profile changed since it was read; reload before saving"):
    response = jsonify(error=message, updatedAt=record.updated_at)
    response.status_code = 409
    response.headers["Cache-Control"] = "no-store"
    response.set_etag(record.updated_at)
    return response


def _next_updated_at(previous=None):
    current = datetime.now(timezone.utc)
    if previous:
        previous_time = datetime.fromisoformat(previous)
        if previous_time.tzinfo is None:
            previous_time = previous_time.replace(tzinfo=timezone.utc)
        if current <= previous_time:
            current = previous_time + timedelta(microseconds=1)
    return current.isoformat(timespec="microseconds")


def _has_version_precondition():
    """True for a specific strong If-Match token or the create sentinel."""
    if request.headers.get("If-None-Match", "").strip() == "*":
        return True
    match = request.if_match
    return not match.star_tag and bool(match.as_set())


def _same_profile_retry(record, draft, profile, *, allow_create_retry=False):
    """Return the saved response for an unchanged retried body, if authorized."""
    if record.draft != draft or not _has_version_precondition():
        return None
    if request.headers.get("If-None-Match", "").strip() == "*":
        return _profile_response(record) if allow_create_retry else None
    # A stale If-Match is safe only for a no-op retry: it cannot replace newer data.
    return _profile_response(record)


@future_api.route("/api/future/profile/<profile_id>", methods=["GET", "PUT"])
def starting_profile(profile_id):
    try:
        if str(UUID(profile_id)) != profile_id:
            raise ValueError
    except ValueError:
        return jsonify(error="Invalid profile id"), 400
    # No profile enumeration or shared global 'current user'. The random id is
    # a local bearer capability; do not put it in public links or telemetry.
    if request.method == "GET":
        record = db.session.get(StartingProfile, profile_id)
        if record is None:
            return jsonify(error="Profile not found"), 404
        response = jsonify(draft=record.draft, profile=record.profile, updatedAt=record.updated_at)
        response.headers["Cache-Control"] = "no-store"
        response.set_etag(record.updated_at)
        return response
    else:
        origin = request.headers.get("Origin")
        if origin and origin != request.host_url.rstrip("/"):
            return jsonify(error="Cross-origin profile writes are not allowed"), 403
        if (request.content_length or 0) > 16384:
            return jsonify(error="Profile too large"), 413
        try:
            draft = validate_draft(request.get_json(silent=True), profile_id)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        profile = derive_profile(draft)
        record = db.session.get(StartingProfile, profile_id)
        if record is None:
            if request.headers.get("If-None-Match", "").strip() != "*":
                response = jsonify(error="Profile creation requires If-None-Match: *")
                response.status_code = 409
                response.headers["Cache-Control"] = "no-store"
                return response
            record = StartingProfile(id=profile_id)
            record.draft = draft
            record.profile = profile
            record.updated_at = _next_updated_at()
            db.session.add(record)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                existing = db.session.get(StartingProfile, profile_id)
                if existing is None:
                    raise
                retry = _same_profile_retry(existing, draft, profile, allow_create_retry=True)
                return retry or _profile_conflict(existing, "A different profile was created first")
            except OperationalError:
                db.session.rollback()
                existing = db.session.get(StartingProfile, profile_id)
                if existing is None:
                    raise
                retry = _same_profile_retry(existing, draft, profile, allow_create_retry=True)
                return retry or _profile_conflict(existing, "A different profile was created first")
            return _profile_response(record)

        if record.draft == draft:
            retry = _same_profile_retry(record, draft, profile, allow_create_retry=True)
            if retry is not None:
                return retry

        if request.headers.get("If-None-Match", "").strip() == "*":
            return _profile_conflict(record)
        if request.if_match.star_tag or not request.if_match.as_set():
            return _profile_conflict(record, "Profile updates require the ETag from the latest read")
        expected_etag = record.updated_at
        if not request.if_match.contains(expected_etag):
            return _profile_conflict(record)

        updated_at = _next_updated_at(record.updated_at)
        try:
            changed = db.session.execute(
                update(StartingProfile)
                .where(
                    StartingProfile.id == profile_id,
                    StartingProfile.updated_at == expected_etag,
                )
                .values(draft=draft, profile=profile, updated_at=updated_at)
            )
            if changed.rowcount != 1:
                db.session.rollback()
                latest = db.session.get(StartingProfile, profile_id)
                if latest is None:
                    return jsonify(error="Profile not found"), 404
                retry = _same_profile_retry(latest, draft, profile)
                return retry or _profile_conflict(latest)
            db.session.commit()
        except OperationalError:
            db.session.rollback()
            latest = db.session.get(StartingProfile, profile_id)
            if latest is None:
                return jsonify(error="Profile not found"), 404
            retry = _same_profile_retry(latest, draft, profile)
            return retry or _profile_conflict(latest)
        record.draft = draft
        record.profile = profile
        record.updated_at = updated_at
        return _profile_response(record)


@future_api.post("/api/future/associations")
def expand_associations():
    """Optional bounded local imagination, with no writes or background jobs.

    Output is a word proposal, never an assertion about the player. The normal
    setup path is immediately usable when Ollama is missing or unavailable.
    """
    origin = request.headers.get("Origin")
    if origin and origin != request.host_url.rstrip("/"):
        return jsonify(error="Cross-origin requests are not allowed"), 403
    if (request.content_length or 0) > 16384:
        return jsonify(error="Profile too large"), 413
    value = request.get_json(silent=True)
    try:
        draft = validate_draft(value, value.get("id") if isinstance(value, dict) else None)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    seed = derive_profile(draft)
    try:
        tags = requests.get("http://127.0.0.1:11434/api/tags", timeout=(2, 3))
        tags.raise_for_status()
        installed = {item["name"] for item in tags.json().get("models", [])}
        preferred = [
            os.environ.get("CROSSWORD_PROFILE_MODEL", "qwen3.8:27b"),
            "gemma4:26b",
            "gemma4:31b",
            "gemma3:27b",
        ]
        model = next((name for name in preferred if name in installed), None)
        if model is None:
            return jsonify(error="No configured local writing model is installed"), 503
        response = requests.post("http://127.0.0.1:11434/api/chat", timeout=(2, 40), json={
            "model": model, "stream": False, "think": False,
            "format": {"type": "object", "properties": {"words": {"type": "array", "minItems": 1, "maxItems": 6, "items": {"type": "string"}}}, "required": ["words"], "additionalProperties": False},
            "options": {"temperature": 0.8, "num_predict": 160},
            "messages": [
                {"role": "system", "content": "Imagine six evocative English words or short phrases connected to these objects and signs, to seed future crossword themes. Follow surprising concrete associations across art, nature, science, sound and everyday life. Use ASCII letters, spaces or hyphens only, 2 to 29 characters each. Do not repeat the seeds. Do not infer personality, identity, beliefs, health or knowledge. These are invitations to words, not descriptions of a person. Return only JSON with a words array."},
                {"role": "user", "content": json.dumps({"objects": seed["observations"], "seeds": seed["associations"]})},
            ],
        })
        response.raise_for_status()
        words = json.loads(response.json()["message"]["content"])["words"]
        validated = validate_draft({**draft, "reflection": {"words": words, "model": model}}, draft["id"])
        return jsonify(validated["reflection"])
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return jsonify(error="Local imagination is unavailable; the starting profile is ready without it"), 503
