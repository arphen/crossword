"""Evidence-bound, local-only narrative snapshots for a personal profile.

The narrative is a regenerable interpretation of the current episteme
projection. It is deliberately stored outside the reducer: model prose is a
versioned view of evidence, never a new claim or a replacement for the
append-only ledger.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
import re
from uuid import NAMESPACE_URL, UUID, uuid5

import requests
from flask import Blueprint, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from .database import db
from .episteme_store import (
    EpistemeCommandRejected,
    EpistemeRuntimeUnavailable,
    EpistemeRevisionConflict,
    apply_episteme_command,
    get_or_create_episteme_profile,
    now_utc_iso,
    project_episteme_profile,
)
from .future import StartingProfile

profile_narrative_api = Blueprint("profile_narrative_api", __name__)

MAX_BODY_BYTES = 8 * 1024
MAX_MODEL_RESPONSE_BYTES = 32 * 1024
MAX_SOURCE_BYTES = 24 * 1024
MODEL_TIMEOUT = (2, 120)
MODEL_DIGEST = re.compile(r"^[0-9a-f]{64}$")
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
UNSAFE_NARRATIVE = re.compile(
    r"\b(?:you are|you seem|you appear|your personality|your identity|your health|"
    r"your politics|your beliefs?|your diagnosis|the player is|the user is|"
    r"knows? that|likes? to|prefers? to|wants? to|desires? to|must be|is a type of)\b",
    re.IGNORECASE,
)

NARRATIVE_FORMAT = "private-profile-narrative-v1"
NARRATIVE_PROMPT_VERSION = "private-profile-narrative-prompt-v1"
NARRATIVE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["paragraphs", "openQuestions"],
    "properties": {
        "paragraphs": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "evidenceIds"],
                "properties": {
                    "text": {"type": "string", "minLength": 1, "maxLength": 700},
                    "evidenceIds": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {"type": "string", "maxLength": 240},
                    },
                },
            },
        },
        "openQuestions": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "evidenceIds"],
                "properties": {
                    "text": {"type": "string", "minLength": 1, "maxLength": 240},
                    "evidenceIds": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {"type": "string", "maxLength": 240},
                    },
                },
            },
        },
        "suggestions": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["conceptId", "label", "kind", "action", "rationale", "evidenceIds"],
                "properties": {
                    "conceptId": {"type": "string", "minLength": 1, "maxLength": 240},
                    "label": {"type": "string", "minLength": 1, "maxLength": 160},
                    "kind": {"type": "string", "enum": ["taste", "goal", "style", "context"]},
                    "action": {"type": "string", "enum": ["seek", "exclude"]},
                    "rationale": {"type": "string", "minLength": 1, "maxLength": 360},
                    "evidenceIds": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 8,
                        "items": {"type": "string", "maxLength": 240},
                    },
                },
            },
        },
    },
}


class ProfileNarrativeRuntimeUnavailable(RuntimeError):
    """The local model or profile reducer is unavailable."""


class ProfileNarrativeRecord(db.Model):
    __tablename__ = "future_profile_narratives"

    id = db.Column(db.String(36), primary_key=True)
    profile_id = db.Column(db.String(36), nullable=False, index=True)
    episteme_revision = db.Column(db.Integer, nullable=False)
    source_digest = db.Column(db.String(64), nullable=False, index=True)
    narrative_json = db.Column(db.JSON, nullable=True)
    generation_metadata = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="pending")
    created_at = db.Column(db.String(40), nullable=False)
    updated_at = db.Column(db.String(40), nullable=False)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _valid_uuid(value):
    return isinstance(value, str) and bool(UUID_PATTERN.fullmatch(value)) and str(UUID(value)) == value


def _same_origin():
    origin = request.headers.get("Origin")
    return origin is None or origin == request.host_url.rstrip("/")


def _error(message, status):
    response = jsonify(error=message)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _read_body():
    request.max_content_length = MAX_BODY_BYTES
    try:
        raw = request.get_data(cache=True)
    except RequestEntityTooLarge:
        return None, _error("Narrative request is too large", 413)
    if len(raw) > MAX_BODY_BYTES:
        return None, _error("Narrative request is too large", 413)
    if not raw:
        return {}, None
    try:
        value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeDecodeError):
        return None, _error("Narrative request must be valid JSON", 400)
    if not isinstance(value, dict) or set(value) - {"requestId"}:
        return None, _error("Narrative request must contain only requestId", 422)
    if "requestId" in value and not _valid_uuid(value["requestId"]):
        return None, _error("Invalid narrative request id", 422)
    return value, None


def _profile(profile_id):
    if not _valid_uuid(profile_id):
        return None, _error("Invalid profile id", 400)
    starting = db.session.get(StartingProfile, profile_id)
    if starting is None:
        return None, _error("Profile not found", 404)
    try:
        episteme = get_or_create_episteme_profile(profile_id, starting.updated_at or now_utc_iso())
        projection = project_episteme_profile(episteme.profile_json, now_utc_iso())
    except EpistemeRuntimeUnavailable:
        db.session.rollback()
        return None, _error("The local profile reducer is unavailable", 503)
    except EpistemeCommandRejected as error:
        db.session.rollback()
        return None, _error(str(error), 422)
    return (starting, episteme, projection), None


def _source(starting, episteme, projection):
    claims = []
    evidence_ids = {"starting-profile"}
    for claim in projection.get("claims", [])[:18]:
        if not isinstance(claim, dict) or not isinstance(claim.get("concept"), dict):
            continue
        concept = claim["concept"]
        if not isinstance(concept.get("conceptId"), str) or not isinstance(concept.get("label"), str):
            continue
        links = [item for item in claim.get("evidenceIds", []) if isinstance(item, str)][:8]
        evidence_ids.update(links)
        claims.append({
            "conceptId": concept["conceptId"],
            "label": concept["label"],
            "kind": claim.get("kind"),
            "stance": claim.get("stance"),
            "strength": claim.get("strength"),
            "evidenceIds": links,
        })
    associations = []
    for item in projection.get("associations", [])[:18]:
        if not isinstance(item, dict) or not isinstance(item.get("phrase"), str):
            continue
        links = [
            link
            for link in [*item.get("supportEvidenceIds", []), *item.get("counterEvidenceIds", [])]
            if isinstance(link, str)
        ][:8]
        evidence_ids.update(links)
        associations.append({
            "phrase": item["phrase"],
            "relation": item.get("relation"),
            "response": item.get("response"),
            "origin": item.get("origin"),
            "evidenceIds": links,
        })
    knowledge = []
    for item in projection.get("knowledge", [])[:18]:
        if not isinstance(item, dict) or not isinstance(item.get("task"), dict):
            continue
        task = item["task"]
        knowledge.append({
            "language": task.get("language"),
            "clueFamily": task.get("clueFamily"),
            "taskKind": task.get("taskKind"),
            "evidenceCount": item.get("independent", {}).get("evidenceCount", 0),
        })
    profile = starting.profile if isinstance(starting.profile, dict) else {}
    source = {
        "format": "private-profile-narrative-source-v1",
        "profileId": starting.id,
        "epistemeRevision": episteme.revision,
        "claims": claims,
        "associations": associations,
        "knowledge": knowledge,
        "opening": {
            "weekday": starting.draft.get("weekday") if isinstance(starting.draft, dict) else None,
            "learningLanguage": starting.draft.get("learningLanguage") if isinstance(starting.draft, dict) else None,
            "modelPreference": starting.draft.get("modelPreference") if isinstance(starting.draft, dict) else None,
            "prose": profile.get("prose") if isinstance(profile.get("prose"), str) else "",
            "associations": [item for item in profile.get("associations", []) if isinstance(item, str)][:12],
        },
        "evidenceIds": sorted(evidence_ids)[:96],
    }
    serialized = _canonical(source).encode("utf-8")
    if len(serialized) > MAX_SOURCE_BYTES:
        raise ValueError("Narrative source is too large")
    return source


def _model_identity(tags, model):
    models = tags.get("models") if isinstance(tags, dict) else None
    matches = [item for item in models or [] if isinstance(item, dict) and item.get("name") == model]
    if len(matches) != 1:
        raise ProfileNarrativeRuntimeUnavailable("Ollama model tag is missing or ambiguous")
    digest = matches[0].get("digest")
    if not isinstance(digest, str) or not MODEL_DIGEST.fullmatch(digest):
        raise ProfileNarrativeRuntimeUnavailable("Ollama model tag has no valid digest")
    return {"tag": model, "digest": f"sha256:{digest}"}


def _response_json(response):
    try:
        response.raise_for_status()
        if getattr(response, "status_code", 200) >= 300:
            raise ProfileNarrativeRuntimeUnavailable("The local model redirected the request")
        body = getattr(response, "content", b"")
        if not isinstance(body, bytes) or len(body) > MAX_MODEL_RESPONSE_BYTES:
            raise ProfileNarrativeRuntimeUnavailable("The local model response is too large")
        return json.loads(body)
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise ProfileNarrativeRuntimeUnavailable("The local model returned invalid JSON") from error
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


def _validate_narrative(value, evidence_ids):
    if (
        not isinstance(value, dict)
        or not {"paragraphs", "openQuestions"}.issubset(value)
        or not set(value).issubset({"version", "paragraphs", "openQuestions", "suggestions"})
        or ("version" in value and value["version"] != NARRATIVE_FORMAT)
    ):
        raise ValueError("The local model returned an invalid narrative shape")
    allowed = set(evidence_ids)
    paragraphs = value["paragraphs"]
    questions = value["openQuestions"]
    if not isinstance(paragraphs, list) or not 1 <= len(paragraphs) <= 3:
        raise ValueError("The local model must return one to three narrative paragraphs")
    if not isinstance(questions, list) or len(questions) > 3:
        raise ValueError("The local model returned too many narrative questions")

    def validate_item(item, maximum):
        if not isinstance(item, dict) or set(item) != {"text", "evidenceIds"}:
            raise ValueError("Narrative items must include text and evidenceIds")
        text = item["text"]
        links = item["evidenceIds"]
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= maximum or text != text.strip():
            raise ValueError("Narrative text is invalid")
        if UNSAFE_NARRATIVE.search(text):
            raise ValueError("Narrative text contains an unsupported personal inference")
        if not isinstance(links, list) or len(links) > 8 or len(set(links)) != len(links) or any(link not in allowed for link in links):
            raise ValueError("Narrative evidence links are invalid")
        return {"text": text, "evidenceIds": links}

    suggestions = []
    raw_suggestions = value.get("suggestions", [])
    if not isinstance(raw_suggestions, list) or len(raw_suggestions) > 3:
        raise ValueError("Narrative suggestions are invalid")
    for item in raw_suggestions:
        if not isinstance(item, dict) or set(item) != {"conceptId", "label", "kind", "action", "rationale", "evidenceIds"}:
            raise ValueError("Narrative suggestions have an invalid shape")
        concept_id, label, kind, action, rationale, links = (
            item["conceptId"], item["label"], item["kind"], item["action"], item["rationale"], item["evidenceIds"]
        )
        if not isinstance(concept_id, str) or not 1 <= len(concept_id.strip()) <= 240 or concept_id != concept_id.strip():
            raise ValueError("Narrative suggestion concept id is invalid")
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 160 or label != label.strip():
            raise ValueError("Narrative suggestion label is invalid")
        if kind not in {"taste", "goal", "style", "context"} or action not in {"seek", "exclude"}:
            raise ValueError("Narrative suggestion reducer operation is invalid")
        if not isinstance(rationale, str) or not 1 <= len(rationale.strip()) <= 360 or rationale != rationale.strip() or UNSAFE_NARRATIVE.search(rationale):
            raise ValueError("Narrative suggestion rationale is invalid")
        if not isinstance(links, list) or not 1 <= len(links) <= 8 or len(set(links)) != len(links) or any(link not in allowed for link in links):
            raise ValueError("Narrative suggestion evidence links are invalid")
        suggestions.append({
            "conceptId": concept_id,
            "label": label,
            "kind": kind,
            "action": action,
            "rationale": rationale,
            "evidenceIds": links,
        })

    return {
        "version": NARRATIVE_FORMAT,
        "paragraphs": [validate_item(item, 700) for item in paragraphs],
        "openQuestions": [validate_item(item, 240) for item in questions],
        "suggestions": suggestions,
    }


def _decode_model_json(content):
    """Accept a JSON object wrapped in the markdown some local tags emit."""
    candidate = content.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(candidate[start : end + 1])


def _generate(source):
    session = requests.Session()
    session.trust_env = False
    try:
        tags = _response_json(session.get("http://127.0.0.1:11434/api/tags", timeout=(2, 8)))
        prompt = (
            "Write a short private crossword field note from the supplied evidence. "
            "This is an interpretation of a word field, never a psychological diagnosis. "
            "Use only the source and cite evidenceIds for every paragraph or question. "
            "Keep uncertainty visible; do not state that a person is, likes, prefers, wants, "
            "believes, knows, or has any identity, health, political, or personality trait. "
            "Do not address the player as you. You may offer zero to three possible paths as "
            "suggestions, but each must be a narrow seek/exclude operation grounded in the cited "
            "evidence and phrased as a proposal, never as a claim. Return JSON matching the supplied schema.\n\n"
            f"SOURCE:\n{_canonical(source)}"
        )
        installed = {
            item.get("name")
            for item in tags.get("models", [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        configured = os.environ.get("CROSSWORD_PROFILE_NARRATIVE_MODEL")
        preferred = source.get("opening", {}).get("modelPreference")
        profile_choice = preferred if isinstance(preferred, str) and preferred != "automatic" else None
        candidates = [
            name
            for name in dict.fromkeys(
                [configured, profile_choice, "qwen3.8:27b", "gemma4:26b"]
                if configured
                else [profile_choice, "qwen3.8:27b", "gemma4:26b"]
            )
            if name and name in installed
        ]
        if not candidates:
            raise ProfileNarrativeRuntimeUnavailable("No configured local profile model is installed")
        last_error = None
        for model in candidates:
            try:
                identity = _model_identity(tags, model)
                response = session.post(
                    "http://127.0.0.1:11434/api/chat",
                    json={
                        "model": model,
                        "stream": False,
                        "think": False,
                        "format": NARRATIVE_SCHEMA,
                        "options": {"temperature": 0.35, "num_predict": 1100},
                        "messages": [
                            {"role": "system", "content": "You produce strict JSON only."},
                            {"role": "user", "content": prompt},
                        ],
                    },
                    timeout=MODEL_TIMEOUT,
                )
                payload = _response_json(response)
                message = payload.get("message") if isinstance(payload, dict) else None
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, str):
                    raise ProfileNarrativeRuntimeUnavailable("The local model returned no narrative content")
                narrative = _validate_narrative(_decode_model_json(content), source["evidenceIds"])
                returned = payload.get("model") if isinstance(payload.get("model"), str) else model
                metadata = {
                    "provider": "ollama-loopback",
                    "requestedModel": model,
                    "returnedModel": returned,
                    "digest": identity["digest"],
                    "format": NARRATIVE_FORMAT,
                    "promptVersion": NARRATIVE_PROMPT_VERSION,
                    "sourceDigest": _digest(source),
                }
                for key in (
                    "total_duration",
                    "load_duration",
                    "prompt_eval_count",
                    "prompt_eval_duration",
                    "eval_count",
                    "eval_duration",
                ):
                    if type(payload.get(key)) is int and payload[key] >= 0:
                        metadata[key] = payload[key]
                return narrative, metadata
            except (requests.RequestException, ProfileNarrativeRuntimeUnavailable, ValueError, TypeError) as error:
                last_error = error
                continue
        raise ProfileNarrativeRuntimeUnavailable("Installed local models returned unusable narrative output") from last_error
    except requests.RequestException as error:
        raise ProfileNarrativeRuntimeUnavailable("The local profile model is unavailable") from error
    except (ValueError, TypeError) as error:
        # A local tag can still ignore the JSON schema. Keep the profile path
        # usable and record an unavailable narrative rather than surfacing a
        # model-format exception as a server error.
        raise ProfileNarrativeRuntimeUnavailable("The local profile model returned an unusable narrative") from error
    finally:
        session.close()


def _payload(record, current_revision):
    return {
        "status": record.status,
        "stale": record.episteme_revision != current_revision,
        "narrative": record.narrative_json,
        "receipt": {
            "narrativeId": record.id,
            "profileId": record.profile_id,
            "epistemeRevision": record.episteme_revision,
            "sourceDigest": record.source_digest,
            "generation": record.generation_metadata,
            "createdAt": record.created_at,
            "updatedAt": record.updated_at,
        },
    }


@profile_narrative_api.get("/api/future/profile/<profile_id>/narrative")
def read_profile_narrative(profile_id):
    context, error = _profile(profile_id)
    if error:
        return error
    _, episteme, _ = context
    record = (
        ProfileNarrativeRecord.query.filter_by(profile_id=profile_id)
        .order_by(ProfileNarrativeRecord.created_at.desc(), ProfileNarrativeRecord.id.desc())
        .first()
    )
    body = {"status": "empty", "stale": False, "narrative": None, "receipt": None}
    if record is not None:
        body = _payload(record, episteme.revision)
    response = jsonify(body)
    response.headers["Cache-Control"] = "no-store"
    return response


@profile_narrative_api.post("/api/future/profile/<profile_id>/narrative")
def create_profile_narrative(profile_id):
    if not _same_origin():
        return _error("Cross-origin narrative generation is not allowed", 403)
    body, error = _read_body()
    if error:
        return error
    context, error = _profile(profile_id)
    if error:
        return error
    starting, episteme, projection = context
    try:
        source = _source(starting, episteme, projection)
    except ValueError as cause:
        db.session.rollback()
        return _error(str(cause), 422)
    source_digest = _digest(source)
    request_id = body.get("requestId")
    narrative_key = f"crossword-profile-narrative:{profile_id}:{source_digest}:{request_id or 'canonical'}"
    narrative_id = str(uuid5(NAMESPACE_URL, narrative_key))
    existing = db.session.get(ProfileNarrativeRecord, narrative_id)
    if existing is not None:
        response = jsonify({**_payload(existing, episteme.revision), "replayed": True})
        response.headers["Cache-Control"] = "no-store"
        return response
    now = now_utc_iso()
    try:
        narrative, metadata = _generate(source)
        if request_id:
            metadata = {**metadata, "rebuild": True, "rebuildRequestId": request_id}
        status = "ready"
    except ProfileNarrativeRuntimeUnavailable as cause:
        narrative = None
        metadata = {
            "provider": "ollama-loopback",
            "format": NARRATIVE_FORMAT,
            "sourceDigest": source_digest,
            "unavailable": str(cause)[:180],
        }
        status = "unavailable"
    record = ProfileNarrativeRecord(
        id=narrative_id,
        profile_id=profile_id,
        episteme_revision=episteme.revision,
        source_digest=source_digest,
        narrative_json=narrative,
        generation_metadata=metadata,
        status=status,
        created_at=now,
        updated_at=now,
    )
    db.session.add(record)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        existing = db.session.get(ProfileNarrativeRecord, narrative_id)
        if existing is None:
            return _error("The profile narrative could not be saved", 409)
        record = existing
    response = jsonify({**_payload(record, episteme.revision), "replayed": record is existing})
    response.headers["Cache-Control"] = "no-store"
    return response


@profile_narrative_api.post("/api/future/profile/<profile_id>/narrative/<narrative_id>/suggestions/<int:index>/accept")
def accept_profile_narrative_suggestion(profile_id, narrative_id, index):
    """Promote one stored model proposal only after an explicit player action."""
    if not _same_origin():
        return _error("Cross-origin profile writes are not allowed", 403)
    request.max_content_length = MAX_BODY_BYTES
    try:
        body = request.get_json(silent=True)
    except RequestEntityTooLarge:
        return _error("Narrative request is too large", 413)
    if not isinstance(body, dict):
        return _error("A suggestion acceptance must be a JSON object", 422)
    if set(body) != {"expectedRevision", "updateId"}:
        return _error("A suggestion acceptance needs expectedRevision and updateId", 422)
    if type(body["expectedRevision"]) is not int or body["expectedRevision"] < 0 or not _valid_uuid(body["updateId"]):
        return _error("Invalid suggestion acceptance", 422)
    if not _valid_uuid(narrative_id) or index < 0 or index > 2:
        return _error("Invalid narrative suggestion", 400)
    context, error = _profile(profile_id)
    if error:
        return error
    _, episteme, _ = context
    record = db.session.get(ProfileNarrativeRecord, narrative_id)
    if record is None or record.profile_id != profile_id or record.status != "ready":
        return _error("Narrative suggestion not found", 404)
    suggestions = record.narrative_json.get("suggestions", []) if isinstance(record.narrative_json, dict) else []
    if not isinstance(suggestions, list) or index >= len(suggestions) or not isinstance(suggestions[index], dict):
        return _error("Narrative suggestion not found", 404)
    suggestion = suggestions[index]
    if (
        set(suggestion) != {"conceptId", "label", "kind", "action", "rationale", "evidenceIds"}
        or not isinstance(suggestion.get("conceptId"), str)
        or not isinstance(suggestion.get("label"), str)
        or suggestion.get("kind") not in {"taste", "goal", "style", "context"}
        or suggestion.get("action") not in {"seek", "exclude"}
        or not isinstance(suggestion.get("rationale"), str)
        or not isinstance(suggestion.get("evidenceIds"), list)
    ):
        return _error("Narrative suggestion is malformed", 422)
    known_evidence = {
        item.get("evidenceId") for item in episteme.profile_json.get("evidence", [])
        if isinstance(item, dict) and isinstance(item.get("evidenceId"), str)
    } | {"starting-profile"}
    if not suggestion["evidenceIds"] or any(item not in known_evidence for item in suggestion["evidenceIds"]):
        return _error("Narrative suggestion is not bound to saved evidence", 422)
    marker = f"field-note:{narrative_id}:{index}"
    existing = next(
        (
            item for item in episteme.profile_json.get("evidence", [])
            if isinstance(item, dict) and item.get("type") == "explicit-preference" and item.get("userText") == marker
        ),
        None,
    )
    if existing is not None:
        response = jsonify({"replayed": True, "revision": episteme.revision, "evidenceId": existing.get("evidenceId")})
        response.headers["Cache-Control"] = "no-store"
        return response
    if record.episteme_revision != episteme.revision or body["expectedRevision"] != episteme.revision:
        return _error("The profile changed; reopen the field note before accepting this path", 409)
    existing_ids = {
        item.get("evidenceId") for item in episteme.profile_json.get("evidence", [])
        if isinstance(item, dict) and item.get("type") == "explicit-preference"
        and isinstance(item.get("concept"), dict)
        and item["concept"].get("conceptId") == suggestion.get("conceptId")
    }
    evidence = {
        "evidenceId": str(uuid5(NAMESPACE_URL, f"crossword-profile-suggestion:{narrative_id}:{index}")),
        "recordedAt": now_utc_iso(),
        "type": "explicit-preference",
        "concept": {"conceptId": suggestion["conceptId"], "label": suggestion["label"], "language": "en"},
        "kind": suggestion["kind"],
        "action": suggestion["action"],
        "scope": {"mode": "field-note", "language": "en"},
        "supersedesEvidenceIds": sorted(item for item in existing_ids if isinstance(item, str)),
        "userText": marker,
    }
    command = {
        "updateId": body["updateId"],
        "profileId": profile_id,
        "baseRevision": body["expectedRevision"],
        "recordedAt": now_utc_iso(),
        "evidence": [evidence],
        "evidenceActions": [],
    }
    try:
        result, _ = apply_episteme_command(profile_id, episteme.revision, episteme.profile_json, command)
    except EpistemeRuntimeUnavailable:
        db.session.rollback()
        return _error("The local profile reducer is unavailable", 503)
    except EpistemeRevisionConflict as cause:
        db.session.rollback()
        return _error(str(cause), 409)
    except EpistemeCommandRejected as cause:
        db.session.rollback()
        return _error(str(cause), 422)
    response = jsonify({
        "replayed": result.get("replayed", False),
        "revision": result["profile"]["revision"],
        "evidenceId": evidence["evidenceId"],
        "receipt": result["receipt"],
    })
    response.headers["Cache-Control"] = "no-store"
    return response
