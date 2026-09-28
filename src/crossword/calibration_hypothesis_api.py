"""Host-owned associations proposed from a ready nonverbal calibration.

The model sees only active choices, catalog labels/versions, and recorded
relations.  Its output remains a short, reversible association proposal; it
does not become a claim about the player or evidence of knowledge.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import unicodedata
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import requests
from flask import Blueprint, jsonify, request
from sqlalchemy import and_, update
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.exceptions import RequestEntityTooLarge

from .calibration_api import CalibrationSessionRecord, CATALOG_PATH
from .database import db
from .episteme_store import (
    MAX_PROFILE_BYTES,
    EpistemeCommandRejected,
    EpistemeProfileRecord,
    EpistemeRevisionConflict,
    EpistemeRuntimeUnavailable,
    apply_episteme_command,
    episteme_profile_size,
    get_or_create_episteme_profile,
    now_utc_iso,
)
from .future import StartingProfile
from .future_puzzles import FutureSolveAnalysisRecord
from .session_journal import PersonalSolveSession

calibration_hypothesis_api = Blueprint("calibration_hypothesis_api", __name__)

MAX_BODY_BYTES = 16 * 1024
MAX_DECK_BYTES = 64 * 1024
MAX_MODEL_RESPONSE_BYTES = 32 * 1024
MAX_CAS_ATTEMPTS = 4
DECK_DAYS = 14
DECK_SESSIONS = 5
OLLAMA_TAG_DIGEST = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_RELATIONS = {"adjacent", "contrast", "metaphor", "sound", "etymology"}
LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")
PERSON_INFERENCE = re.compile(
    r"\b(?:you|your|the player|player's|a player|this player)\b.{0,100}\b(?:"
    r"are|is|seem|seems|seemed|appear|appears|might|may|must|probably|likely|"
    r"know|knowledge|like|likes|prefer|prefers|believe|believes|desire|desires|"
    r"want|wants|fear|fears|need|needs|feel|feels|think|thinks|trust|distrust|"
    r"chose|choose|picked|pick|selected|selection|personality|identity|beliefs?|"
    r"health|familiarity|interests?|curiosity|taste|values?|preferences?|emotions?)\b",
    re.IGNORECASE | re.DOTALL,
)


class CalibrationHypothesisDeckRecord(db.Model):
    """Frozen model output and generation receipt, keyed by calibration."""

    __tablename__ = "future_calibration_hypothesis_decks"

    calibration_id = db.Column(db.String(36), primary_key=True)
    source_digest = db.Column(db.String(64), primary_key=True)
    deck_id = db.Column(db.String(36), nullable=False, unique=True)
    profile_id = db.Column(db.String(36), nullable=False, index=True)
    deck_json = db.Column(db.JSON, nullable=False)
    deck_hash = db.Column(db.String(64), nullable=False)
    generation_metadata = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="pending")
    profile_revision = db.Column(db.Integer, nullable=True)


class CalibrationHypothesisResponseRecord(db.Model):
    """One host-authored response evidence event; IDs make retries exact."""

    __tablename__ = "future_calibration_hypothesis_responses"

    response_id = db.Column(db.String(36), primary_key=True)
    calibration_id = db.Column(db.String(36), nullable=False, index=True)
    deck_id = db.Column(db.String(36), nullable=False, index=True)
    proposal_id = db.Column(db.String(36), nullable=False, index=True)
    request_hash = db.Column(db.String(64), nullable=False)
    response_json = db.Column(db.JSON, nullable=False)
    evidence_json = db.Column(db.JSON, nullable=False)
    episteme_revision = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="pending")
    recorded_at = db.Column(db.String(40), nullable=False)


class CalibrationHypothesisActionRecord(db.Model):
    """Immutable retract/restore events for one response evidence item."""

    __tablename__ = "future_calibration_hypothesis_actions"

    action_id = db.Column(db.String(36), primary_key=True)
    calibration_id = db.Column(db.String(36), nullable=False, index=True)
    deck_id = db.Column(db.String(36), nullable=False, index=True)
    proposal_id = db.Column(db.String(36), nullable=False, index=True)
    response_id = db.Column(db.String(36), nullable=False, index=True)
    request_hash = db.Column(db.String(64), nullable=False)
    action_json = db.Column(db.JSON, nullable=False)
    evidence_action_json = db.Column(db.JSON, nullable=False)
    episteme_revision = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="pending")
    recorded_at = db.Column(db.String(40), nullable=False)


class HypothesisRuntimeUnavailable(RuntimeError):
    """Local Ollama or the local episteme reducer is unavailable."""


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _valid_uuid(value):
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _local_origin():
    origin = request.headers.get("Origin")
    return origin is not None and origin == request.host_url.rstrip("/")


def _error(message, status):
    response = jsonify(error=message)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _read_json(limit=MAX_BODY_BYTES, *, allow_empty_object=False):
    request.max_content_length = limit
    if (request.content_length or 0) > limit:
        return None, _error("Hypothesis request is too large", 413)
    try:
        raw = request.get_data(cache=True)
    except RequestEntityTooLarge:
        return None, _error("Hypothesis request is too large", 413)
    if len(raw) > limit:
        return None, _error("Hypothesis request is too large", 413)
    if not raw and allow_empty_object:
        return {}, None
    try:
        value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON number")))
    except (ValueError, UnicodeDecodeError):
        return None, _error("Hypothesis request must be valid JSON", 400)
    if not isinstance(value, dict):
        return None, _error("Hypothesis request must be an object", 422)
    return value, None


def _catalog():
    try:
        value = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        stimulus_bank = value.get("stimuli", {})
        items = stimulus_bank.get("items")
        if not isinstance(items, list):
            raise ValueError("missing stimuli")
        version = stimulus_bank.get("version")
        if type(version) is not int and not isinstance(version, str):
            raise ValueError("missing stimulus bank version")
        return str(version), {item["id"]: item for item in items if isinstance(item, dict)}
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise HypothesisRuntimeUnavailable("The local calibration catalog is unavailable") from error


def _calibration_and_profile(calibration_id, *, require_current=True):
    if not _valid_uuid(calibration_id):
        return None, None, _error("Invalid calibration id", 400)
    calibration = db.session.get(CalibrationSessionRecord, calibration_id)
    if calibration is None:
        return None, None, _error("Calibration not found", 404)
    payload = calibration.payload
    scope = payload.get("scope") if isinstance(payload, dict) else None
    if not isinstance(scope, dict) or scope.get("kind") != "profile" or not _valid_uuid(scope.get("profileId")):
        return None, None, _error("Hypotheses require a profile-scoped calibration", 403)
    profile = db.session.get(StartingProfile, scope["profileId"])
    if profile is None:
        return None, None, _error("Calibration profile not found", 404)
    if require_current and profile.draft.get("calibrationId") != calibration_id:
        return None, None, _error("Calibration does not match the profile's current calibration", 409)
    if payload.get("calibrationId") != calibration_id:
        return None, None, _error("Calibration identity mismatch", 422)
    if "skip" in payload or payload.get("status") == "skipped":
        return None, None, _error("Association hypotheses are unavailable after a skipped calibration", 409)
    if payload.get("status") not in ("completed", "in-progress"):
        return None, None, _error("Calibration is not ready for association hypotheses", 409)
    if not isinstance(payload.get("setup"), dict):
        return None, None, _error("Calibration setup is not complete", 409)
    if payload.get("status") == "in-progress" and payload.get("currentMovement") != 5:
        return None, None, _error("Association hypotheses are available after the opening movements", 409)
    if payload.get("status") == "completed" and (
        payload.get("currentMovement") != 5
        or not isinstance(payload.get("completedAt"), str)
    ):
        return None, None, _error("Completed calibration state is invalid", 409)
    return calibration, profile, None


def _active_chosen_source(payload):
    """Make a compact model input from active selected catalog stimuli only."""
    bank_version, items = _catalog()
    if payload.get("bankVersion") != bank_version:
        raise ValueError("Calibration stimulus bank version does not match the local catalog")
    observations = payload.get("observations")
    actions = payload.get("actions")
    if not isinstance(observations, list) or not isinstance(actions, list):
        raise ValueError("Calibration history is malformed")

    action_state = {}
    for action in actions:
        if not isinstance(action, dict) or action.get("action") not in ("retract", "restore"):
            raise ValueError("Calibration action history is malformed")
        action_state[action.get("targetObservationId")] = action["action"]

    active = []
    for observation in observations:
        response = observation.get("response") if isinstance(observation, dict) else None
        if not isinstance(observation, dict) or not isinstance(response, dict) or response.get("kind") != "choose":
            continue
        if action_state.get(observation.get("observationId")) == "retract":
            continue
        chosen_ids = response.get("chosenIds")
        if not isinstance(chosen_ids, list) or not chosen_ids:
            raise ValueError("Calibration choice is malformed")
        stimuli = []
        for stimulus_id in chosen_ids:
            presentation = next(
                (entry for entry in observation.get("offered", []) if entry.get("stimulusId") == stimulus_id),
                None,
            )
            catalog_item = items.get(stimulus_id)
            if presentation is None or catalog_item is None or str(catalog_item.get("version")) != presentation.get("stimulusVersion"):
                raise ValueError("Calibration references a changed catalog stimulus")
            stimuli.append({
                "stimulusId": stimulus_id,
                "stimulusVersion": presentation["stimulusVersion"],
                "label": catalog_item.get("accessible_label") or catalog_item.get("label"),
            })
        row = {
            "observationId": observation["observationId"],
            "movement": observation["movement"],
            "stimuli": stimuli,
        }
        relation = observation.get("relation")
        if relation is not None:
            relation_value = {"kind": relation.get("kind")}
            if relation.get("kind") == "keep-original":
                stimulus_id = relation.get("stimulusId")
                relation_value["stimulus"] = {
                    "stimulusId": stimulus_id,
                    "label": next((item["label"] for item in stimuli if item["stimulusId"] == stimulus_id), None),
                }
            else:
                for side in ("from", "to"):
                    stimulus_id = relation.get(f"{side}StimulusId")
                    catalog_item = items.get(stimulus_id)
                    relation_value[side] = {
                        "stimulusId": stimulus_id,
                        "label": (catalog_item or {}).get("accessible_label") or (catalog_item or {}).get("label"),
                    }
            row["relation"] = relation_value
        active.append(row)

    active_stimulus_ids = {
        stimulus["stimulusId"]
        for observation in active
        for stimulus in observation["stimuli"]
    }
    for observation in active:
        relation = observation.get("relation")
        if relation is None:
            continue
        if relation["kind"] == "keep-original":
            source_ids = [relation.get("stimulus", {}).get("stimulusId")]
        else:
            source_ids = [relation.get(side, {}).get("stimulusId") for side in ("from", "to")]
        if not source_ids or any(stimulus_id not in active_stimulus_ids for stimulus_id in source_ids):
            observation.pop("relation", None)

    if not active:
        raise ValueError("Calibration does not contain any active opening choices")
    active.sort(key=lambda item: (item["movement"], item["observationId"]))
    return active


def _text(value, max_chars, label, *, minimum=1):
    if (
        not isinstance(value, str)
        or len(value) < minimum
        or len(value) > max_chars
        or value != value.strip()
        or value != unicodedata.normalize("NFC", value)
        or any(unicodedata.category(char).startswith("C") for char in value)
    ):
        raise ValueError(f"Invalid {label}")
    return value


def _reject_player_inference(value):
    if PERSON_INFERENCE.search(value):
        raise ValueError("Association text must not make claims about a player's traits, health, beliefs, preferences, or knowledge")
    return value


def _validate_model_paths(value, source, language):
    if not isinstance(value, dict) or set(value) != {"paths"}:
        raise ValueError("The local model returned an invalid association deck")
    paths = value["paths"]
    if not isinstance(paths, list) or not 1 <= len(paths) <= 6:
        raise ValueError("The local model must return between one and six association paths")
    allowed_observations = {item["observationId"]: item for item in source}
    seen_phrases = set()
    normalized = []
    for path in paths:
        required = {"phrase", "language", "relation", "sourceObservationIds", "connection", "ambiguity"}
        if not isinstance(path, dict) or set(path) != required:
            raise ValueError("The local model returned an invalid association path")
        phrase = _text(path["phrase"], 80, "association phrase")
        _reject_player_inference(phrase)
        if len(phrase.split()) > 6:
            raise ValueError("Association phrases must be short")
        phrase_key = phrase.casefold()
        if phrase_key in seen_phrases:
            raise ValueError("The local model repeated an association phrase")
        seen_phrases.add(phrase_key)
        item_language = path["language"]
        if not isinstance(item_language, str) or not LANGUAGE_TAG.fullmatch(item_language):
            raise ValueError("The local model returned an invalid language tag")
        if item_language.casefold() not in {language.casefold(), "en"}:
            raise ValueError("The local model returned an unrequested language")
        relation = path["relation"]
        if relation not in ALLOWED_RELATIONS:
            raise ValueError("The local model returned an unsupported relation")
        observation_ids = path["sourceObservationIds"]
        if (
            not isinstance(observation_ids, list)
            or not 1 <= len(observation_ids) <= 4
            or len(set(observation_ids)) != len(observation_ids)
            or any(not isinstance(item, str) or item not in allowed_observations for item in observation_ids)
        ):
            raise ValueError("The local model referenced an inactive or unknown calibration observation")
        connection = _text(path["connection"], 280, "association connection")
        ambiguity = _text(path["ambiguity"], 240, "association ambiguity")
        _reject_player_inference(connection)
        _reject_player_inference(ambiguity)
        source_stimulus_ids = []
        cited_stimulus_ids = set()
        for observation_id in observation_ids:
            observation = allowed_observations[observation_id]
            chosen_ids = [item["stimulusId"] for item in observation["stimuli"]]
            source_stimulus_ids.extend(chosen_ids)
            cited_stimulus_ids.update(chosen_ids)
        for observation_id in observation_ids:
            observation = allowed_observations[observation_id]
            relation_value = observation.get("relation")
            if relation_value:
                if relation_value["kind"] == "keep-original":
                    relation_ids = [relation_value["stimulus"]["stimulusId"]]
                else:
                    relation_ids = [relation_value[side]["stimulusId"] for side in ("from", "to")]
                if any(stimulus_id not in cited_stimulus_ids for stimulus_id in relation_ids):
                    raise ValueError("A cited relation endpoint needs its own cited active observation")
        source_stimulus_ids = list(dict.fromkeys(source_stimulus_ids))
        if not source_stimulus_ids:
            raise ValueError("An association path must cite a chosen stimulus")
        normalized.append({
            "phrase": phrase,
            "language": item_language,
            "relation": relation,
            "sourceObservationIds": observation_ids,
            "sourceStimulusIds": source_stimulus_ids,
            "connection": connection,
            "ambiguity": ambiguity,
        })
    return normalized


def _read_model_response(response, limit):
    try:
        response.raise_for_status()
        status = getattr(response, "status_code", 200)
        if 300 <= status < 400:
            raise ValueError("Ollama must not redirect requests away from loopback")
        length = getattr(response, "headers", {}).get("Content-Length")
        if length is not None and int(length) > limit:
            raise ValueError("The local model response is too large")
        if callable(getattr(response, "iter_content", None)):
            chunks = []
            size = 0
            for chunk in response.iter_content(chunk_size=min(8192, limit + 1)):
                if not chunk:
                    continue
                size += len(chunk)
                if size > limit:
                    raise ValueError("The local model response is too large")
                chunks.append(chunk)
            content = b"".join(chunks)
        else:
            content = getattr(response, "content", b"")
            if not isinstance(content, bytes) or len(content) > limit:
                raise ValueError("The local model response is too large or invalid")
        return json.loads(content)
    finally:
        if callable(getattr(response, "close", None)):
            response.close()


def _association_prompt_source(source):
    """Omit movement position and every timing/debug field from model context."""
    return [
        {
            "observationId": observation["observationId"],
            "stimuli": [
                {key: stimulus[key] for key in ("stimulusId", "stimulusVersion", "label")}
                for stimulus in observation["stimuli"]
            ],
            **({"relation": observation["relation"]} if observation.get("relation") else {}),
        }
        for observation in source
    ]


def _new_ollama_session():
    session = requests.Session()
    session.trust_env = False
    return session


def _ollama_model_identity(tags, model):
    """Return one exact installed tag identity, requiring a real SHA-256."""
    installed = tags.get("models") if isinstance(tags, dict) else None
    if not isinstance(installed, list):
        raise ValueError("Invalid Ollama model list")
    matches = [
        item for item in installed
        if isinstance(item, dict) and item.get("name") == model
    ]
    if len(matches) != 1:
        raise ValueError("Ollama model tag is missing or ambiguous")
    digest = matches[0].get("digest")
    if not isinstance(digest, str) or not OLLAMA_TAG_DIGEST.fullmatch(digest):
        raise ValueError("Ollama model tag has no valid SHA-256 digest")
    # Ollama's tags endpoint returns the SHA-256 hex without an algorithm
    # prefix. Keep a canonical prefixed form in durable generation metadata.
    return {"tag": model, "digest": f"sha256:{digest}"}


def _generate_paths(source, language):
    """Use only loopback Ollama and keep the model receipt beside the deck."""
    source = _association_prompt_source(source)
    try:
        with _new_ollama_session() as ollama:
            tags_response = ollama.get(
                "http://127.0.0.1:11434/api/tags",
                timeout=(2, 3),
                stream=True,
                allow_redirects=False,
            )
            tags = _read_model_response(tags_response, 64 * 1024)
        installed = tags.get("models", []) if isinstance(tags, dict) else []
        if not isinstance(installed, list):
            raise ValueError("Invalid Ollama model list")
        installed_names = {
            item["name"] for item in installed
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        configured = os.environ.get("CROSSWORD_HYPOTHESIS_MODEL") or os.environ.get("CROSSWORD_PROFILE_MODEL")
        # Gemma 4 26B is the provisional no-override local default after two
        # Qwen timeouts and one successful Gemma route. Explicit configuration
        # stays first; remaining candidates preserve the existing fallback set.
        preferred = list(dict.fromkeys([
            configured or "gemma4:26b",
            "qwen3.8:27b",
            "gemma4:26b",
            "gemma4:31b",
        ]))
        model = next((name for name in preferred if name in installed_names), None)
        if model is None:
            raise RuntimeError("No configured local association model is installed")
        pre_identity = _ollama_model_identity(tags, model)
        schema = {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array", "minItems": 1, "maxItems": 6,
                    "items": {
                        "type": "object",
                        "properties": {
                            "phrase": {"type": "string"},
                            "language": {"type": "string"},
                            "relation": {"type": "string", "enum": sorted(ALLOWED_RELATIONS)},
                            "sourceObservationIds": {"type": "array", "minItems": 1, "maxItems": 4, "items": {"type": "string"}},
                            "connection": {"type": "string"},
                            "ambiguity": {"type": "string"},
                        },
                        "required": ["phrase", "language", "relation", "sourceObservationIds", "connection", "ambiguity"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["paths"],
            "additionalProperties": False,
        }
        with _new_ollama_session() as ollama:
            response = ollama.post(
                "http://127.0.0.1:11434/api/chat",
                timeout=(2, 45),
                stream=True,
                allow_redirects=False,
                json={
                "model": model,
                "stream": False,
                "think": False,
                "format": schema,
                "options": {"temperature": 0.8, "num_predict": 900},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Offer up to six short word-association paths for a crossword player. "
                            "Use only the selected objects/signs and relations supplied. Each path must cite one to four exact observationId values from the input. "
                            "Choose only an allowed relation. Use the requested language (English is also allowed). "
                            "A connection is an imaginative possibility, not a conclusion about the player. "
                            "Do not infer personality, identity, beliefs, health, desire, familiarity, or knowledge. "
                            "In ambiguity, say briefly what remains open or uncertain. Return only the requested JSON object."
                        ),
                    },
                    {"role": "user", "content": json.dumps({"requestedLanguage": language, "observations": source}, ensure_ascii=False)},
                ],
                },
            )
            generated = _read_model_response(response, MAX_MODEL_RESPONSE_BYTES)
        # Record the post-inference registry state even when the response later
        # fails validation. A selected tag may be retagged or removed while the
        # request is running, so the response cannot be attributed by name alone.
        with _new_ollama_session() as ollama:
            tags_response = ollama.get(
                "http://127.0.0.1:11434/api/tags",
                timeout=(2, 3),
                stream=True,
                allow_redirects=False,
            )
            post_tags = _read_model_response(tags_response, 64 * 1024)
        post_identity = _ollama_model_identity(post_tags, model)
        if post_identity["digest"] != pre_identity["digest"]:
            raise ValueError("Ollama model tag changed during inference")
        if not isinstance(generated, dict) or not isinstance(generated.get("message"), dict):
            raise ValueError("Invalid local model response")
        returned_model = generated.get("model")
        if not isinstance(returned_model, str) or returned_model != model:
            raise ValueError("Ollama returned a different model tag")
        content = generated["message"].get("content")
        if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_MODEL_RESPONSE_BYTES:
            raise ValueError("Invalid local model output")
        model_json = json.loads(content)
        paths = _validate_model_paths(model_json, source, language)
        metadata = {
            "provider": "ollama-loopback",
            "requestedModel": model,
            "returnedModel": returned_model,
            "digest": pre_identity["digest"],
            "identityVerified": True,
            "preInferenceIdentity": pre_identity,
            "postInferenceIdentity": post_identity,
            "format": "calibration-association-paths-v1",
        }
        return paths, metadata
    except (requests.RequestException, ValueError, KeyError, TypeError, RuntimeError) as error:
        raise HypothesisRuntimeUnavailable(
            "Local Ollama association generation is unavailable; the calibration and crossword remain playable"
        ) from error


def _make_deck(calibration_id, profile_id, payload, source, source_digest):
    language = payload.get("setup", {}).get("language", "en")
    paths, metadata = _generate_paths(_association_prompt_source(source), language)
    created_at = _utc_now()
    expires_at = (datetime.fromisoformat(created_at.replace("Z", "+00:00")) + timedelta(days=DECK_DAYS)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    deck_id = str(uuid4())
    items = []
    for path in paths:
        proposal_id = str(uuid4())
        evidence_id = str(uuid5(NAMESPACE_URL, f"crossword-calibration-proposal:{calibration_id}:{proposal_id}:v1"))
        association_id = proposal_id
        item = {
            "proposalId": proposal_id,
            "evidenceId": evidence_id,
            "associationId": association_id,
            "phrase": path["phrase"],
            "language": path["language"],
            "relation": path["relation"],
            "sourceObservationIds": path["sourceObservationIds"],
            "sourceStimulusIds": path["sourceStimulusIds"],
            "connection": path["connection"],
            "ambiguity": path["ambiguity"],
            "parentConceptIds": path["sourceStimulusIds"],
        }
        items.append(item)
    deck = {
        "deckId": deck_id,
        "calibrationId": calibration_id,
        "profileId": profile_id,
        "createdAt": created_at,
        "expiresAt": expires_at,
        "sourceDigest": source_digest,
        "items": items,
    }
    if len(_canonical(deck).encode("utf-8")) > MAX_DECK_BYTES:
        raise ValueError("Generated association deck exceeds its storage limit")
    return deck, metadata


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _utc_after(previous):
    now = datetime.now(timezone.utc)
    if previous:
        prior = datetime.fromisoformat(previous.replace("Z", "+00:00"))
        if now <= prior:
            now = prior + timedelta(milliseconds=1)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _update_episteme_with_cas(profile_id, created_at, update_id, recorded_at, evidence, evidence_actions, before_apply=None):
    for attempt in range(MAX_CAS_ATTEMPTS):
        profile = get_or_create_episteme_profile(profile_id, created_at)
        if before_apply is not None:
            before_apply()
        command = {
            "updateId": update_id,
            "profileId": profile_id,
            "baseRevision": profile.revision,
            "recordedAt": recorded_at,
            "evidence": evidence,
            "evidenceActions": evidence_actions,
        }
        try:
            return apply_episteme_command(profile_id, profile.revision, profile.profile_json, command)
        except EpistemeRevisionConflict as error:
            db.session.rollback()
            if not str(error).startswith("Stale profile revision") or attempt + 1 == MAX_CAS_ATTEMPTS:
                raise
    raise EpistemeRevisionConflict("Stale profile revision: retry limit reached")


def _current_profile_revision(profile_id):
    record = db.session.get(EpistemeProfileRecord, profile_id)
    return record.revision if record is not None else 0


def _profile_has_update(profile_id, update_id):
    record = db.session.get(EpistemeProfileRecord, profile_id)
    return bool(record and any(item.get("updateId") == update_id for item in record.profile_json.get("updates", [])))


def _active_session_count(profile_id, deck_created_at):
    rows = db.session.query(FutureSolveAnalysisRecord.session_id).join(
        PersonalSolveSession,
        PersonalSolveSession.id == FutureSolveAnalysisRecord.session_id,
    ).filter(
        and_(
            PersonalSolveSession.profile_id == profile_id,
            FutureSolveAnalysisRecord.finalized.is_(True),
            FutureSolveAnalysisRecord.updated_at > deck_created_at,
        )
    ).distinct().all()
    return len(rows)


def _deck_expired(record):
    try:
        expired_at = datetime.fromisoformat(record.deck_json["expiresAt"].replace("Z", "+00:00")) <= datetime.now(timezone.utc)
    except (ValueError, KeyError, TypeError):
        expired_at = True
    return expired_at or _active_session_count(record.profile_id, record.created_at) >= DECK_SESSIONS


def _responses_for_deck(record):
    saved = db.session.query(CalibrationHypothesisResponseRecord).filter_by(
        calibration_id=record.calibration_id,
        deck_id=record.deck_id,
        status="complete",
    ).all()
    values = {}
    for proposal in record.deck_json["items"]:
        proposal_responses = [item for item in saved if item.proposal_id == proposal["proposalId"]]
        latest = None
        for response in proposal_responses:
            actions = db.session.query(CalibrationHypothesisActionRecord).filter_by(
                response_id=response.response_id,
                status="complete",
            ).order_by(CalibrationHypothesisActionRecord.recorded_at, CalibrationHypothesisActionRecord.action_id).all()
            if latest is None or (response.recorded_at, response.response_id) > (latest[0].recorded_at, latest[0].response_id):
                latest = (response, actions)
        if latest:
            response, actions = latest
            values[proposal["proposalId"]] = {
                "response": response.response_json["response"],
                "responseId": response.response_id,
                "active": not actions or actions[-1].action_json["action"] != "retract",
            }
    return values


def _result(record):
    deck = dict(record.deck_json)
    deck["expired"] = _deck_expired(record)
    return {
        "deck": deck,
        "responses": _responses_for_deck(record),
        "profileRevision": _current_profile_revision(record.profile_id),
    }


def _stored_deck(calibration_id, *, source_digest=None, deck_id=None):
    query = db.session.query(CalibrationHypothesisDeckRecord).filter_by(calibration_id=calibration_id)
    if source_digest is not None:
        query = query.filter_by(source_digest=source_digest)
    if deck_id is not None:
        query = query.filter_by(deck_id=deck_id)
    record = query.order_by(CalibrationHypothesisDeckRecord.created_at.desc()).first()
    if record is None:
        return None, None
    if not hmac.compare_digest(record.deck_hash, _hash(record.deck_json)):
        return None, _error("Stored association deck integrity check failed", 500)
    return record, None


def _ensure_deck_evidence(record):
    if record.status == "complete":
        return record
    evidence = [
        {
            "evidenceId": item["evidenceId"],
            "recordedAt": record.deck_json["createdAt"],
            "type": "association-proposal",
            "associationId": item["associationId"],
            "phrase": item["phrase"],
            "language": item["language"],
            "relation": item["relation"],
            "parentConceptIds": item["parentConceptIds"],
            "explanation": item["connection"],
            "origin": "calibration-proposal",
            "calibrationId": record.calibration_id,
            "sourceObservationIds": item["sourceObservationIds"],
            "sourceStimulusIds": item["sourceStimulusIds"],
            "expiresAt": record.deck_json["expiresAt"],
            "expireAfterSessions": DECK_SESSIONS,
        }
        for item in record.deck_json["items"]
    ]
    update_id = str(uuid5(NAMESPACE_URL, f"crossword-calibration-deck:{record.deck_id}:v1"))
    try:
        result, _ = _update_episteme_with_cas(
            record.profile_id,
            record.created_at,
            update_id,
            record.created_at,
            evidence,
            [],
        )
    except (EpistemeRuntimeUnavailable, EpistemeCommandRejected):
        db.session.rollback()
        raise
    profile = result["profile"]
    if episteme_profile_size(profile) > MAX_PROFILE_BYTES:
        raise EpistemeCommandRejected("Episteme profile exceeds the storage limit")
    record.status = "complete"
    record.profile_revision = profile["revision"]
    try:
        db.session.commit()
    except OperationalError:
        db.session.rollback()
        latest = db.session.query(CalibrationHypothesisDeckRecord).filter_by(
            calibration_id=record.calibration_id,
            source_digest=record.source_digest,
        ).first()
        if latest is None:
            raise
        if latest.status == "complete":
            return latest
        raise
    return record


def _get_or_create_deck(calibration_id, source_digest, source, profile_record, calibration_record):
    existing, error = _stored_deck(calibration_id, source_digest=source_digest)
    if error:
        return None, error
    if existing is not None:
        try:
            return _ensure_deck_evidence(existing), None
        except EpistemeRuntimeUnavailable:
            return None, _error("The local profile reducer is unavailable; retry to finish saving this deck", 503)
        except EpistemeRevisionConflict as error:
            return None, _error(str(error), 409)
        except EpistemeCommandRejected as error:
            return None, _error(str(error), 422)

    try:
        deck, metadata = _make_deck(calibration_id, profile_record.id, calibration_record.payload, source, source_digest)
    except HypothesisRuntimeUnavailable as error:
        return None, _error(str(error), 503)
    except (ValueError, KeyError, TypeError) as error:
        return None, _error(str(error), 422)
    record = CalibrationHypothesisDeckRecord(
        calibration_id=calibration_id,
        source_digest=source_digest,
        deck_id=deck["deckId"],
        profile_id=profile_record.id,
        deck_json=deck,
        deck_hash=_hash(deck),
        generation_metadata=metadata,
        created_at=deck["createdAt"],
        status="pending",
    )
    db.session.add(record)
    try:
        db.session.commit()
    except (IntegrityError, OperationalError):
        db.session.rollback()
        winner, error = _stored_deck(calibration_id, source_digest=source_digest)
        if error:
            return None, error
        if winner is None:
            raise
        record = winner
    try:
        record = _ensure_deck_evidence(record)
    except EpistemeRuntimeUnavailable:
        return None, _error("The local profile reducer is unavailable; retry to finish saving this deck", 503)
    except EpistemeRevisionConflict as error:
        return None, _error(str(error), 409)
    except EpistemeCommandRejected as error:
        return None, _error(str(error), 422)
    return record, None


def _source_digest(calibration_id, calibration_payload, source):
    # Binds this frozen offer to active choices, relation edits and the
    # explicit language setup, while excluding timings and inactive history.
    return _hash({
        "calibrationId": calibration_id,
        "scope": calibration_payload["scope"],
        "bankVersion": calibration_payload["bankVersion"],
        "selectorVersion": calibration_payload["selectorVersion"],
        "seed": calibration_payload["seed"],
        "presentationMode": calibration_payload["presentationMode"],
        "setup": calibration_payload["setup"],
        "observations": source,
    })


def _saved_deck_profile(calibration_id, deck_record):
    calibration = db.session.get(CalibrationSessionRecord, calibration_id)
    if calibration is None:
        return None, _error("Calibration not found", 404)
    scope = calibration.payload.get("scope", {}) if isinstance(calibration.payload, dict) else {}
    if scope.get("kind") != "profile" or scope.get("profileId") != deck_record.profile_id:
        return None, _error("Saved association deck profile mismatch", 409)
    profile = db.session.get(StartingProfile, deck_record.profile_id)
    if profile is None:
        return None, _error("Association deck profile not found", 404)
    return profile, None


def _deck_matches_current_source(record):
    calibration = db.session.get(CalibrationSessionRecord, record.calibration_id)
    if calibration is None or not isinstance(calibration.payload, dict):
        return False
    payload = calibration.payload
    if (
        payload.get("scope", {}).get("kind") != "profile"
        or payload["scope"].get("profileId") != record.profile_id
        or payload.get("status") not in ("in-progress", "completed")
        or "skip" in payload
        or not isinstance(payload.get("setup"), dict)
        or (payload.get("status") == "in-progress" and payload.get("currentMovement") != 5)
    ):
        return False
    try:
        source = _active_chosen_source(payload)
        return _source_digest(record.calibration_id, payload, source) == record.source_digest
    except (ValueError, KeyError, TypeError, HypothesisRuntimeUnavailable):
        return False


def _response_request(value, deck_id):
    if not isinstance(value, dict) or set(value) != {"responseId", "deckId", "response"}:
        raise ValueError("Association response must contain responseId, deckId, and response only")
    if not _valid_uuid(value["responseId"]) or value["deckId"] != deck_id or value["response"] not in ("keep", "not-for-me", "pass"):
        raise ValueError("Invalid association response fields")
    return value


def _action_request(value):
    if not isinstance(value, dict) or set(value) != {"actionId", "action"}:
        raise ValueError("Association action must contain actionId and action only")
    if not _valid_uuid(value["actionId"]) or value["action"] not in ("retract", "restore"):
        raise ValueError("Invalid association action fields")
    return value


def _proposal(record, proposal_id):
    return next((item for item in record.deck_json["items"] if item["proposalId"] == proposal_id), None)


def _save_response_evidence(session_profile_id, record, proposal, request_value):
    response_id = request_value["responseId"]
    request_hash = _hash(request_value)
    existing = db.session.get(CalibrationHypothesisResponseRecord, response_id)
    if existing is not None:
        if (
            existing.request_hash != request_hash
            or existing.calibration_id != record.calibration_id
            or existing.deck_id != record.deck_id
            or existing.proposal_id != proposal["proposalId"]
        ):
            return None, _error("Response id was reused with different proposal data", 409), False
        if existing.status == "complete":
            return existing, None, True
        # An exact retry of a persisted pending receipt must be allowed to
        # finish even if the deck expired while its reducer write was pending.
    else:
        if _deck_expired(record):
            return None, _error("This association deck has expired", 410), False
        latest = db.session.query(CalibrationHypothesisResponseRecord).filter_by(
            calibration_id=record.calibration_id,
            deck_id=record.deck_id,
            proposal_id=proposal["proposalId"],
        ).order_by(CalibrationHypothesisResponseRecord.recorded_at.desc()).first()
        recorded_at = _utc_after(latest.recorded_at if latest is not None else None)
        evidence_id = str(uuid5(NAMESPACE_URL, f"crossword-calibration-response:{response_id}:v1"))
        evidence = {
            "evidenceId": evidence_id,
            "recordedAt": recorded_at,
            "type": "association-response",
            "associationId": proposal["associationId"],
            "proposalEvidenceId": proposal["evidenceId"],
            "response": request_value["response"],
        }
        existing = CalibrationHypothesisResponseRecord(
            response_id=response_id,
            calibration_id=record.calibration_id,
            deck_id=record.deck_id,
            proposal_id=proposal["proposalId"],
            request_hash=request_hash,
            response_json={**request_value, "recordedAt": recorded_at},
            evidence_json=evidence,
            episteme_revision=None,
            status="pending",
            recorded_at=recorded_at,
        )
        db.session.add(existing)
        try:
            db.session.commit()
        except (IntegrityError, OperationalError):
            db.session.rollback()
            existing = db.session.get(CalibrationHypothesisResponseRecord, response_id)
            if existing is None or existing.request_hash != request_hash:
                return None, _error("A conflicting association response won the retry race", 409), False
            if existing.status == "complete":
                return existing, None, True

    update_id = str(uuid5(NAMESPACE_URL, f"crossword-calibration-response-update:{response_id}:v1"))
    profile_record = db.session.get(EpistemeProfileRecord, session_profile_id)
    committed_update = bool(profile_record and any(
        item.get("updateId") == update_id for item in profile_record.profile_json.get("updates", [])
    ))
    if committed_update:
        result = {"profile": profile_record.profile_json, "replayed": True}
    else:
        try:
            result, _ = _update_episteme_with_cas(
                session_profile_id,
                existing.recorded_at,
                update_id,
                existing.recorded_at,
                [existing.evidence_json],
                [],
            )
        except EpistemeRuntimeUnavailable:
            db.session.rollback()
            return None, _error("The local profile reducer is unavailable; retry to finish saving this response", 503), False
        except EpistemeRevisionConflict as error:
            db.session.rollback()
            return None, _error(str(error), 409), False
        except EpistemeCommandRejected as error:
            db.session.rollback()
            return None, _error(str(error), 422), False
    profile = result["profile"]
    if episteme_profile_size(profile) > MAX_PROFILE_BYTES:
        return None, _error("Episteme profile exceeds the storage limit", 422), False
    existing.episteme_revision = profile["revision"]
    existing.status = "complete"
    db.session.commit()
    return existing, None, bool(result.get("replayed"))


def _response_actions(response_id):
    return db.session.query(CalibrationHypothesisActionRecord).filter_by(
        response_id=response_id,
        status="complete",
    ).order_by(CalibrationHypothesisActionRecord.recorded_at, CalibrationHypothesisActionRecord.action_id).all()


def _validate_action_transition(response_id, action, action_id=None, candidate=None):
    response_record = db.session.get(CalibrationHypothesisResponseRecord, response_id)
    if response_record is None:
        raise ValueError("Association response evidence is missing")
    deck_record = db.session.query(CalibrationHypothesisDeckRecord).filter_by(deck_id=response_record.deck_id).first()
    profile_record = db.session.get(EpistemeProfileRecord, deck_record.profile_id) if deck_record else None
    ledger_actions = []
    if profile_record is not None:
        ledger_actions = [
            item for item in profile_record.profile_json.get("evidenceActions", [])
            if item.get("targetEvidenceId") == response_record.evidence_json["evidenceId"]
        ]
    if action_id is not None:
        match = next((item for item in ledger_actions if item.get("actionId") == action_id), None)
        if match is not None:
            if candidate is not None and _canonical(match) == _canonical(candidate):
                return
            raise ValueError("Action id was already used with different episteme evidence")
    actions = _response_actions(response_id)
    latest = max(
        ledger_actions + [item.evidence_action_json for item in actions],
        key=lambda item: (item["recordedAt"], item["actionId"]),
        default=None,
    )
    expected = "retract" if latest is None or latest["action"] == "restore" else "restore"
    if action != expected:
        participle = {"retract": "retracted", "restore": "restored"}[expected]
        raise ValueError(f"This response can only be {participle} next")


def _save_action_evidence(record, proposal, response_record, action_value):
    action_id = action_value["actionId"]
    request_hash = _hash(action_value)
    existing = db.session.get(CalibrationHypothesisActionRecord, action_id)
    if existing is not None:
        if (
            existing.request_hash != request_hash
            or existing.calibration_id != record.calibration_id
            or existing.deck_id != record.deck_id
            or existing.proposal_id != proposal["proposalId"]
            or existing.response_id != response_record.response_id
        ):
            return None, _error("Action id was reused with different proposal data", 409), False
        if existing.status == "complete":
            return existing, None, True
        # An exact pending reservation is already admitted. It must be able to
        # finish even after expiry/source replacement, including when the
        # reducer committed but the final receipt update did not.
    else:
        if action_value["action"] == "restore" and _deck_expired(record):
            return None, _error("This association deck has expired", 410), False
        try:
            _validate_action_transition(response_record.response_id, action_value["action"])
        except ValueError as error:
            return None, _error(str(error), 409), False
        actions = _response_actions(response_record.response_id)
        latest_recorded_at = actions[-1].recorded_at if actions else response_record.recorded_at
        recorded_at = _utc_after(latest_recorded_at)
        evidence_action = {
            "actionId": action_id,
            "recordedAt": recorded_at,
            "targetEvidenceId": response_record.evidence_json["evidenceId"],
            "action": action_value["action"],
            "reason": "player-correction",
        }
        existing = CalibrationHypothesisActionRecord(
            action_id=action_id,
            calibration_id=record.calibration_id,
            deck_id=record.deck_id,
            proposal_id=proposal["proposalId"],
            response_id=response_record.response_id,
            request_hash=request_hash,
            action_json={**action_value, "recordedAt": recorded_at},
            evidence_action_json=evidence_action,
            episteme_revision=None,
            status="pending",
            recorded_at=recorded_at,
        )
        db.session.add(existing)
        try:
            db.session.commit()
        except (IntegrityError, OperationalError):
            db.session.rollback()
            existing = db.session.get(CalibrationHypothesisActionRecord, action_id)
            if existing is None or existing.request_hash != request_hash:
                return None, _error("A conflicting association action won the retry race", 409), False
            if existing.status == "complete":
                return existing, None, True

    def transition_gate():
        _validate_action_transition(
            response_record.response_id,
            action_value["action"],
            action_id=action_id,
            candidate=existing.evidence_action_json,
        )

    update_id = str(uuid5(NAMESPACE_URL, f"crossword-calibration-action-update:{action_id}:v1"))
    profile_record = db.session.get(EpistemeProfileRecord, record.profile_id)
    committed_update = bool(profile_record and any(
        item.get("updateId") == update_id for item in profile_record.profile_json.get("updates", [])
    ))
    if committed_update:
        result = {"profile": profile_record.profile_json, "replayed": True}
    else:
        try:
            result, _ = _update_episteme_with_cas(
                record.profile_id,
                existing.recorded_at,
                update_id,
                existing.recorded_at,
                [],
                [existing.evidence_action_json],
                before_apply=transition_gate,
            )
        except ValueError as error:
            db.session.rollback()
            return None, _error(str(error), 409), False
        except EpistemeRuntimeUnavailable:
            db.session.rollback()
            return None, _error("The local profile reducer is unavailable; retry to finish saving this action", 503), False
        except EpistemeRevisionConflict as error:
            db.session.rollback()
            return None, _error(str(error), 409), False
        except EpistemeCommandRejected as error:
            db.session.rollback()
            return None, _error(str(error), 422), False
    profile = result["profile"]
    if episteme_profile_size(profile) > MAX_PROFILE_BYTES:
        return None, _error("Episteme profile exceeds the storage limit", 422), False
    existing.episteme_revision = profile["revision"]
    existing.status = "complete"
    db.session.commit()
    return existing, None, bool(result.get("replayed"))


@calibration_hypothesis_api.get("/api/future/calibrations/<calibration_id>/hypotheses")
def get_calibration_hypotheses(calibration_id):
    calibration, _, error = _calibration_and_profile(calibration_id)
    if error:
        return error
    try:
        source = _active_chosen_source(calibration.payload)
        digest = _source_digest(calibration_id, calibration.payload, source)
    except HypothesisRuntimeUnavailable as error:
        return _error(str(error), 503)
    except (ValueError, KeyError, TypeError) as error:
        return _error(str(error), 409)
    record, error = _stored_deck(calibration_id, source_digest=digest)
    if error:
        return error
    if record is None or record.status != "complete":
        return _error("No saved association deck exists for this calibration", 404)
    response = jsonify(**_result(record))
    response.headers["Cache-Control"] = "no-store"
    return response


@calibration_hypothesis_api.post("/api/future/calibrations/<calibration_id>/hypotheses")
def create_calibration_hypotheses(calibration_id):
    if not _local_origin():
        return _error("Same-origin association writes are required", 403)
    value, error = _read_json(allow_empty_object=True)
    if error:
        return error
    if value:
        return _error("Association deck creation does not accept client-authored data", 422)
    calibration, profile, error = _calibration_and_profile(calibration_id)
    if error:
        return error
    try:
        source = _active_chosen_source(calibration.payload)
        digest = _source_digest(calibration_id, calibration.payload, source)
    except HypothesisRuntimeUnavailable as error:
        return _error(str(error), 503)
    except (ValueError, KeyError, TypeError) as error:
        return _error(str(error), 409)
    existed, error = _stored_deck(calibration_id, source_digest=digest)
    if error:
        return error
    record, error = _get_or_create_deck(calibration_id, digest, source, profile, calibration)
    if error:
        return error
    response = jsonify(**_result(record))
    response.status_code = 200 if existed is not None else 201
    response.headers["Cache-Control"] = "no-store"
    return response


@calibration_hypothesis_api.post("/api/future/calibrations/<calibration_id>/hypotheses/<proposal_id>/response")
def respond_to_calibration_hypothesis(calibration_id, proposal_id):
    if not _local_origin():
        return _error("Same-origin association writes are required", 403)
    value, error = _read_json()
    if error:
        return error
    if not isinstance(value, dict) or set(value) != {"responseId", "deckId", "response"} or not _valid_uuid(value.get("deckId")):
        return _error("Association response must contain responseId, deckId, and response only", 422)
    record, error = _stored_deck(calibration_id, deck_id=value["deckId"])
    if error:
        return error
    if record is None or record.status != "complete":
        return _error("Association deck not found", 404)
    profile, error = _saved_deck_profile(calibration_id, record)
    if error:
        return error
    proposal = _proposal(record, proposal_id)
    if proposal is None:
        return _error("Association proposal not found", 404)
    try:
        request_value = _response_request(value, record.deck_id)
    except (ValueError, TypeError, KeyError) as error:
        return _error(str(error), 422)
    prior = db.session.get(CalibrationHypothesisResponseRecord, request_value["responseId"])
    prior_is_exact_reservation = (
        prior is not None
        and prior.status in {"pending", "complete"}
        and prior.request_hash == _hash(request_value)
        and prior.calibration_id == record.calibration_id
        and prior.deck_id == record.deck_id
        and prior.proposal_id == proposal_id
    )
    if not prior_is_exact_reservation and not _deck_matches_current_source(record):
        return _error("This association deck was superseded by newer calibration choices", 409)
    saved, error, replayed = _save_response_evidence(profile.id, record, proposal, request_value)
    if error:
        return error
    response = jsonify(**_result(record), response=saved.response_json, evidence=saved.evidence_json, replayed=replayed)
    response.headers["Cache-Control"] = "no-store"
    return response


@calibration_hypothesis_api.post("/api/future/calibrations/<calibration_id>/hypotheses/<proposal_id>/responses/<response_id>/actions")
def act_on_calibration_hypothesis_response(calibration_id, proposal_id, response_id):
    if not _local_origin():
        return _error("Same-origin association writes are required", 403)
    value, error = _read_json()
    if error:
        return error
    if not _valid_uuid(response_id):
        return _error("Invalid response id", 400)
    response_record = db.session.get(CalibrationHypothesisResponseRecord, response_id)
    if (
        response_record is None
        or response_record.status != "complete"
        or response_record.calibration_id != calibration_id
        or response_record.proposal_id != proposal_id
    ):
        return _error("Saved response not found for this calibration and proposal", 404)
    record, error = _stored_deck(calibration_id, deck_id=response_record.deck_id)
    if error:
        return error
    if record is None or record.status != "complete":
        return _error("Association deck not found", 404)
    _, error = _saved_deck_profile(calibration_id, record)
    if error:
        return error
    proposal = _proposal(record, proposal_id)
    if proposal is None:
        return _error("Association proposal not found", 404)
    try:
        action_value = _action_request(value)
    except (ValueError, TypeError, KeyError) as error:
        return _error(str(error), 422)
    prior_action = db.session.get(CalibrationHypothesisActionRecord, action_value["actionId"])
    prior_is_exact_reservation = (
        prior_action is not None
        and prior_action.status in {"pending", "complete"}
        and prior_action.request_hash == _hash(action_value)
        and prior_action.calibration_id == record.calibration_id
        and prior_action.deck_id == record.deck_id
        and prior_action.proposal_id == proposal_id
        and prior_action.response_id == response_id
    )
    if not prior_is_exact_reservation and action_value["action"] != "retract" and not _deck_matches_current_source(record):
        return _error("Only retraction is available for a superseded association deck", 409)
    saved, error, replayed = _save_action_evidence(record, proposal, response_record, action_value)
    if error:
        return error
    response = jsonify(**_result(record), action=saved.action_json, evidenceAction=saved.evidence_action_json, replayed=replayed)
    response.headers["Cache-Control"] = "no-store"
    return response
