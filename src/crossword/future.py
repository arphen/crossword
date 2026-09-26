"""Local, capability-addressed starting profiles for the /future experiment.

Only catalog choices cross this boundary. Visual choices are recorded as
observations, not psychological traits or evidence of word knowledge.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from uuid import UUID

from flask import Blueprint, jsonify, request
import requests

from .database import db

catalog = json.loads(Path(__file__).with_name("future_catalog.json").read_text())
future_api = Blueprint("future_api", __name__)


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
    if type(value.get("step")) is not int or not 0 <= value["step"] <= 4:
        raise ValueError("Invalid step")
    objects = {item["id"]: item for item in catalog["objects"]}
    selected = value.get("object")
    if selected is not None and (not isinstance(selected, str) or selected not in objects):
        raise ValueError("Unknown object")
    companion = value.get("companion")
    if companion is not None and companion not in objects.get(selected, {}).get("companions", []):
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
    return {**{key: value[key] for key in ("version", "id", "step", "object", "companion", "traces", "weekday", "learningLanguage", "excluded", "complete")}, "reflection": reflection}


def derive_profile(draft):
    selected = next((item for item in catalog["objects"] if item["id"] == draft["object"]), {})
    companion = next((item for item in catalog["companions"] if item["id"] == draft["companion"]), {})
    reflection = draft.get("reflection") or {}
    candidates = list(dict.fromkeys(draft["traces"] + selected.get("words", []) + companion.get("words", []) + reflection.get("words", [])))[:18]
    observations = [item["label"] for item in (selected, companion) if item]
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
        "source": "authored-associations", "reflection": reflection or None, "provisional": True, "knowledge": {},
        "generationBrief": {
            "seedWords": associations, "maximumSeedInfluence": 0.2,
            "difficulty": draft["weekday"], "puzzleLanguage": "English",
            "learningLanguage": draft["learningLanguage"],
            "instructions": "Treat seed words as optional thematic invitations. Infer neither personality nor knowledge. Give unfamiliar answers accessible crossings. Preserve clue grammar and the selected difficulty.",
        },
    }


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
            record = StartingProfile(id=profile_id)
            db.session.add(record)
        record.draft = draft
        record.profile = profile
        record.updated_at = datetime.now(timezone.utc).isoformat()
        db.session.commit()
        response = jsonify(profile=profile, updatedAt=record.updated_at)
    response.headers["Cache-Control"] = "no-store"
    return response


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
        preferred = [os.environ.get("CROSSWORD_PROFILE_MODEL", "qwen3.8:27b"), "gemma4:31b", "gemma3:27b"]
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
