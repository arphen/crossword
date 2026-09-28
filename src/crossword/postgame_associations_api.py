"""Bounded local-model association paths produced after a completed game.

The route is deliberately separate from solve replay.  Replay owns truth about
what happened in the grid; this module only turns a small, frozen slice of the
finished puzzle plus the existing profile projection into reversible
``association-proposal`` evidence.  Model output is never a claim about the
player and an unavailable local model leaves the game fully usable.
"""

import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

import requests
from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import RequestEntityTooLarge

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
from .future_puzzles import FuturePuzzleManifestRecord, FutureSolveAnalysisRecord
from .legacy_manifest import verify_integrity
from .session_journal import PersonalSolveSession

postgame_associations_api = Blueprint("postgame_associations_api", __name__)

MAX_BODY_BYTES = 8 * 1024
MAX_MODEL_RESPONSE_BYTES = 32 * 1024
MAX_PATHS = 6
MAX_CAS_ATTEMPTS = 4
ALLOWED_RELATIONS = {"adjacent", "contrast", "metaphor", "sound", "etymology"}
LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
OLLAMA_DIGEST = re.compile(r"^[0-9a-f]{64}$")
PERSON_INFERENCE = re.compile(
    r"\b(?:you|your|the player|player's|this player)\b.{0,120}\b(?:"
    r"are|is|seem|seems|appear|appears|might|may|must|probably|likely|"
    r"know|knowledge|like|likes|prefer|prefers|believe|believes|desire|"
    r"desires|want|wants|fear|fears|need|needs|feel|feels|think|thinks|"
    r"trust|distrust|personality|identity|beliefs?|health|familiarity|"
    r"interests?|curiosity|taste|values?|preferences?|emotions?)\b",
    re.IGNORECASE | re.DOTALL,
)


class PostgameAssociationRuntimeUnavailable(RuntimeError):
    """Ollama or the fixed local reducer is unavailable."""


class PostgameAssociationRunRecord(db.Model):
    __tablename__ = "future_postgame_association_runs"

    session_id = db.Column(db.String(36), primary_key=True)
    profile_id = db.Column(db.String(36), nullable=False, index=True)
    request_hash = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="pending")
    paths_json = db.Column(db.JSON, nullable=True)
    evidence_json = db.Column(db.JSON, nullable=True)
    generation_metadata = db.Column(db.JSON, nullable=True)
    episteme_revision = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.String(40), nullable=False)
    updated_at = db.Column(db.String(40), nullable=False)


class PostgameAssociationResponseRecord(db.Model):
    __tablename__ = "future_postgame_association_responses"

    response_id = db.Column(db.String(36), primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    profile_id = db.Column(db.String(36), nullable=False, index=True)
    association_id = db.Column(db.String(36), nullable=False, index=True)
    request_hash = db.Column(db.String(64), nullable=False)
    response_json = db.Column(db.JSON, nullable=False)
    evidence_json = db.Column(db.JSON, nullable=False)
    episteme_revision = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="pending")
    recorded_at = db.Column(db.String(40), nullable=False)


def _canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _hash(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _valid_uuid(value):
    return isinstance(value, str) and bool(UUID_PATTERN.fullmatch(value)) and str(UUID(value)) == value


def _local_origin():
    origin = request.headers.get("Origin")
    return origin is not None and origin == request.host_url.rstrip("/")


def _error(message, status):
    response = jsonify(error=message)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _read_json():
    request.max_content_length = MAX_BODY_BYTES
    try:
        raw = request.get_data(cache=True)
    except RequestEntityTooLarge:
        return None, _error("Association request is too large", 413)
    if len(raw) > MAX_BODY_BYTES:
        return None, _error("Association request is too large", 413)
    if not raw:
        return {}, None
    try:
        value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeDecodeError):
        return None, _error("Association request must be valid JSON", 400)
    if not isinstance(value, dict):
        return None, _error("Association request must be an object", 422)
    return value, None


def _text(value, maximum, label, *, minimum=1):
    if (
        not isinstance(value, str)
        or not minimum <= len(value) <= maximum
        or value != value.strip()
        or value != unicodedata.normalize("NFC", value)
        or any(unicodedata.category(char).startswith("C") for char in value)
    ):
        raise ValueError(f"Invalid {label}")
    return value


def _reject_inference(value):
    if PERSON_INFERENCE.search(value):
        raise ValueError("Association text must not make claims about a player's traits, preferences, or knowledge")


def _model_identity(tags, model):
    models = tags.get("models") if isinstance(tags, dict) else None
    matches = [item for item in models or [] if isinstance(item, dict) and item.get("name") == model]
    if len(matches) != 1:
        raise ValueError("Ollama model tag is missing or ambiguous")
    digest = matches[0].get("digest")
    if not isinstance(digest, str) or not OLLAMA_DIGEST.fullmatch(digest):
        raise ValueError("Ollama model tag has no valid SHA-256 digest")
    return {"tag": model, "digest": f"sha256:{digest}"}


def _read_response(response, limit):
    try:
        response.raise_for_status()
        if getattr(response, "status_code", 200) >= 300:
            raise ValueError("Ollama must not redirect requests away from loopback")
        length = getattr(response, "headers", {}).get("Content-Length")
        if length is not None and int(length) > limit:
            raise ValueError("The local model response is too large")
        content = getattr(response, "content", b"")
        if not isinstance(content, bytes) or len(content) > limit:
            raise ValueError("The local model response is too large or invalid")
        return json.loads(content)
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


def _ollama_session():
    session = requests.Session()
    session.trust_env = False
    return session


def _validate_paths(value, seed_ids, language="en"):
    if not isinstance(value, dict) or set(value) != {"paths"}:
        raise ValueError("The local model returned an invalid association response")
    paths = value["paths"]
    if not isinstance(paths, list) or not 1 <= len(paths) <= MAX_PATHS:
        raise ValueError("The local model must return between one and six association paths")
    seen = set()
    normalized = []
    for path in paths:
        required = {"phrase", "language", "relation", "parentConceptIds", "explanation"}
        if not isinstance(path, dict) or set(path) != required:
            raise ValueError("The local model returned an invalid association path")
        phrase = _text(path["phrase"], 80, "association phrase")
        if len(phrase.split()) > 8:
            raise ValueError("Association phrases must be short")
        _reject_inference(phrase)
        key = phrase.casefold()
        if key in seen:
            raise ValueError("The local model repeated an association phrase")
        seen.add(key)
        item_language = path["language"]
        if not isinstance(item_language, str) or not LANGUAGE_TAG.fullmatch(item_language):
            raise ValueError("The local model returned an invalid language tag")
        if item_language.casefold() not in {language.casefold(), "en"}:
            raise ValueError("The local model returned an unrequested language")
        relation = path["relation"]
        if relation not in ALLOWED_RELATIONS:
            raise ValueError("The local model returned an unsupported relation")
        parents = path["parentConceptIds"]
        if (
            not isinstance(parents, list)
            or not 1 <= len(parents) <= 3
            or len(set(parents)) != len(parents)
            or any(not isinstance(item, str) or item not in seed_ids for item in parents)
        ):
            raise ValueError("The local model referenced an unknown parent concept")
        explanation = _text(path["explanation"], 280, "association explanation")
        _reject_inference(explanation)
        normalized.append(
            {
                "phrase": phrase,
                "language": item_language,
                "relation": relation,
                "parentConceptIds": parents,
                "explanation": explanation,
            }
        )
    return normalized


def _diversity_receipt(paths):
    """Describe association variety without pretending it is a taste metric."""
    relation_counts = {}
    parent_counts = {}
    for path in paths:
        relation = path.get("relation")
        relation_counts[relation] = relation_counts.get(relation, 0) + 1
        for parent in path.get("parentConceptIds", []):
            parent_counts[parent] = parent_counts.get(parent, 0) + 1
    max_relation = max(relation_counts.values(), default=0)
    max_parent = max(parent_counts.values(), default=0)
    return {
        "format": "postgame-association-diversity-v1",
        "pathCount": len(paths),
        "uniqueRelations": len(relation_counts),
        "uniqueParents": len(parent_counts),
        "relationCounts": dict(sorted(relation_counts.items())),
        "maxRelationCount": max_relation,
        "maxParentCount": max_parent,
        "status": "varied" if len(paths) < 3 or len(relation_counts) >= 2 else "narrow",
    }


def _manifest_context(manifest, analysis, profile):
    if not verify_integrity(manifest):
        raise ValueError("Puzzle manifest integrity check failed")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Puzzle manifest entries are unavailable")
    projection = profile.profile_json.get("projection", {}) if profile else {}
    seed = []
    for claim in projection.get("claims", []) if isinstance(projection, dict) else []:
        concept = claim.get("concept") if isinstance(claim, dict) else None
        if isinstance(concept, dict) and _valid_concept(concept):
            seed.append(dict(concept))
    for association in projection.get("associations", []) if isinstance(projection, dict) else []:
        if not isinstance(association, dict):
            continue
        for concept_id in association.get("parentConceptIds", []):
            if isinstance(concept_id, str) and concept_id not in {item["conceptId"] for item in seed}:
                seed.append({"conceptId": concept_id, "label": concept_id, "language": "en"})
    # The puzzle itself supplies a small, deterministic vocabulary when the
    # profile is still empty.  This is a source anchor, not a knowledge claim.
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            continue
        answer = entry.get("answer")
        if not isinstance(answer, str) or not answer:
            continue
        concept_id = f"puzzle-entry:{entry['id']}"
        if concept_id not in {item["conceptId"] for item in seed}:
            seed.append({"conceptId": concept_id, "label": answer, "language": "en"})
        if len(seed) >= 18:
            break
    seed = seed[:18]
    if not seed:
        raise ValueError("The completed puzzle has no association seeds")
    seed_ids = {item["conceptId"] for item in seed}
    selected_entries = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            continue
        answer = entry.get("answer")
        clue = entry.get("clue")
        if not isinstance(answer, str) or not isinstance(clue, str):
            continue
        selected_entries.append(
            {
                "entryId": entry["id"],
                "answer": answer,
                "clue": clue[:180],
                "theme": entry.get("theme") is True,
            }
        )
    selected_entries.sort(key=lambda item: (not item["theme"], item["entryId"]))
    analysis_summary = {}
    if isinstance(analysis, dict):
        for key in ("analysisVersion", "entryCount", "independentCount", "supportedCount", "assistedCount", "incorrectAttemptCount"):
            if key in analysis and isinstance(analysis[key], (str, int, float)):
                analysis_summary[key] = analysis[key]
    source = {
        "title": str(manifest.get("title") or "Personal crossword")[:160],
        "subtitle": str(manifest.get("subtitle") or "")[:180],
        "entries": selected_entries[:12],
        "analysis": analysis_summary,
        "profileConcepts": seed[:12],
    }
    return source, seed_ids


def _valid_concept(value):
    return (
        isinstance(value, dict)
        and isinstance(value.get("conceptId"), str)
        and 1 <= len(value["conceptId"]) <= 200
        and isinstance(value.get("label"), str)
        and 1 <= len(value["label"]) <= 200
    )


def _generate_paths(source, seed_ids, language="en"):
    try:
        with _ollama_session() as ollama:
            tags_response = ollama.get(
                "http://127.0.0.1:11434/api/tags",
                timeout=(2, 3),
                allow_redirects=False,
            )
            tags = _read_response(tags_response, 64 * 1024)
        installed = tags.get("models", []) if isinstance(tags, dict) else []
        names = {item.get("name") for item in installed if isinstance(item, dict)}
        configured = os.environ.get("CROSSWORD_POSTGAME_MODEL")
        model = next((name for name in dict.fromkeys([configured, "gemma4:26b", "qwen3.8:27b"] if configured else ["gemma4:26b", "qwen3.8:27b"]) if name in names), None)
        if model is None:
            raise RuntimeError("No configured local association model is installed")
        identity = _model_identity(tags, model)
        schema = {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": MAX_PATHS,
                    "items": {
                        "type": "object",
                        "properties": {
                            "phrase": {"type": "string"},
                            "language": {"type": "string"},
                            "relation": {"type": "string", "enum": sorted(ALLOWED_RELATIONS)},
                            "parentConceptIds": {"type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "string", "enum": sorted(seed_ids)}},
                            "explanation": {"type": "string"},
                        },
                        "required": ["phrase", "language", "relation", "parentConceptIds", "explanation"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["paths"],
            "additionalProperties": False,
        }
        with _ollama_session() as ollama:
            response = ollama.post(
                "http://127.0.0.1:11434/api/chat",
                timeout=(2, 90),
                allow_redirects=False,
                json={
                    "model": model,
                    "stream": False,
                    "think": False,
                    "format": schema,
                    "options": {"temperature": 0.8, "num_predict": 700},
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Offer one to six short, evocative word-association paths from this finished crossword. "
                                "Use only the supplied entries and profile concepts. Parent concept IDs must be copied exactly. "
                                "These are imaginative possibilities, never conclusions about the player. Do not infer personality, "
                                "identity, beliefs, health, desire, familiarity, taste, or knowledge. Return only the JSON object."
                            ),
                        },
                        {"role": "user", "content": json.dumps({"requestedLanguage": language, "source": source}, ensure_ascii=False)},
                    ],
                },
            )
            generated = _read_response(response, MAX_MODEL_RESPONSE_BYTES)
        if not isinstance(generated, dict) or not isinstance(generated.get("message"), dict):
            raise ValueError("Invalid local model response")
        if generated.get("model") != model:
            raise ValueError("Ollama returned a different model tag")
        content = generated["message"].get("content")
        if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_MODEL_RESPONSE_BYTES:
            raise ValueError("Invalid local model output")
        paths = _validate_paths(json.loads(content), seed_ids, language)
        return paths, {
            "provider": "ollama-loopback",
            "requestedModel": model,
            "returnedModel": model,
            "digest": identity["digest"],
            "identityVerified": True,
            "format": "postgame-association-paths-v1",
            "diversity": _diversity_receipt(paths),
        }
    except (
        requests.RequestException,
        AssertionError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
        json.JSONDecodeError,
    ) as error:
        raise PostgameAssociationRuntimeUnavailable("Local association generation is unavailable; the completed game remains saved") from error


def _update_episteme(profile_id, recorded_at, update_id, evidence):
    for attempt in range(MAX_CAS_ATTEMPTS):
        profile = get_or_create_episteme_profile(profile_id, recorded_at)
        command = {
            "updateId": update_id,
            "profileId": profile_id,
            "baseRevision": profile.revision,
            "recordedAt": recorded_at,
            "evidence": evidence,
            "evidenceActions": [],
        }
        try:
            return apply_episteme_command(profile_id, profile.revision, profile.profile_json, command)
        except EpistemeRevisionConflict:
            db.session.rollback()
            if attempt + 1 == MAX_CAS_ATTEMPTS:
                raise
    raise EpistemeRevisionConflict("Stale profile revision: retry limit reached")


def _finished_context(session_id):
    if not _valid_uuid(session_id):
        return None, _error("Invalid session id", 400)
    session = db.session.get(PersonalSolveSession, session_id)
    if session is None:
        return None, _error("Session not found", 404)
    if session.status != "finished":
        return None, _error("Association paths are available after the game is complete", 409)
    analysis = db.session.get(FutureSolveAnalysisRecord, session_id)
    manifest_record = db.session.get(FuturePuzzleManifestRecord, session.puzzle_hash)
    if analysis is None or not analysis.finalized or manifest_record is None:
        return None, _error("The finished game has no replayable analysis", 409)
    profile = db.session.get(EpistemeProfileRecord, session.profile_id)
    if profile is None:
        return None, _error("The local episteme is not ready", 409)
    return (session, analysis, manifest_record, profile), None


def _response_map(record):
    rows = db.session.query(PostgameAssociationResponseRecord).filter_by(
        session_id=record.session_id, status="complete"
    ).all()
    return {
        item.association_id: {
            "response": item.response_json["response"],
            "responseId": item.response_id,
            "active": True,
        }
        for item in rows
    }


def _result(record, *, status=None, replayed=False):
    stored_paths = record.paths_json or []
    paths = [item for item in stored_paths if isinstance(item, dict) and not item.get("expansionOf")]
    expansions = {}
    for item in stored_paths:
        if isinstance(item, dict) and isinstance(item.get("expansionOf"), str):
            expansions.setdefault(item["expansionOf"], []).append(item)
    payload = {
        "sessionId": record.session_id,
        "status": status or record.status,
        "paths": paths,
        "expansions": expansions,
        "responses": _response_map(record),
        "profileRevision": record.episteme_revision,
        "replayed": replayed,
    }
    response = jsonify(payload)
    response.headers["Cache-Control"] = "no-store"
    return response


@postgame_associations_api.post("/api/future/sessions/<session_id>/episteme-associations")
def create_postgame_associations(session_id):
    if not _local_origin():
        return _error("Cross-origin association writes are not allowed", 403)
    body, error = _read_json()
    if error:
        return error
    if body and set(body) != {"requestId"}:
        return _error("Association request may contain only requestId", 422)
    if body and not _valid_uuid(body.get("requestId")):
        return _error("Invalid request id", 422)
    context, error = _finished_context(session_id)
    if error:
        return error
    session, analysis, manifest_record, profile = context
    source, seed_ids = _manifest_context(manifest_record.manifest_json, analysis.analysis_json, profile)
    request_hash = _hash({"sessionId": session_id, "puzzleHash": session.puzzle_hash, "source": source})
    existing = db.session.get(PostgameAssociationRunRecord, session_id)
    if existing is not None and existing.request_hash != request_hash:
        return _error("This session's association source changed", 409)
    if existing is not None and existing.status == "complete":
        return _result(existing, status="replayed", replayed=True)
    now = now_utc_iso()
    if existing is None:
        existing = PostgameAssociationRunRecord(
            session_id=session_id,
            profile_id=session.profile_id,
            request_hash=request_hash,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        db.session.add(existing)
    else:
        existing.status = "pending"
        existing.updated_at = now
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = db.session.get(PostgameAssociationRunRecord, session_id)
        if existing is not None and existing.status == "complete":
            return _result(existing, status="replayed", replayed=True)
        return _error("Another association pass is already running; retry shortly", 409)

    try:
        paths, metadata = _generate_paths(source, seed_ids, "en")
    except PostgameAssociationRuntimeUnavailable as unavailable:
        existing.status = "unavailable"
        existing.updated_at = now_utc_iso()
        db.session.commit()
        response = jsonify({"sessionId": session_id, "status": "unavailable", "paths": [], "error": str(unavailable)})
        response.headers["Cache-Control"] = "no-store"
        return response

    evidence = []
    public_paths = []
    expires_at = (datetime.fromisoformat(now.replace("Z", "+00:00")) + timedelta(days=30)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    for path in paths:
        path_hash = _hash(path)
        association_id = str(uuid5(NAMESPACE_URL, f"crossword-session-association:{session_id}:{path_hash}:v1"))
        evidence_id = str(uuid5(NAMESPACE_URL, f"crossword-session-association-evidence:{association_id}:v1"))
        evidence.append({
            "evidenceId": evidence_id,
            "recordedAt": now,
            "type": "association-proposal",
            "associationId": association_id,
            "phrase": path["phrase"],
            "language": path["language"],
            "relation": path["relation"],
            "parentConceptIds": path["parentConceptIds"],
            "explanation": path["explanation"],
            "origin": "model-proposal",
            "expiresAt": expires_at,
            "expireAfterSessions": 10,
        })
        public_paths.append({**path, "associationId": association_id, "evidenceId": evidence_id})
    update_id = str(uuid5(NAMESPACE_URL, f"crossword-session-associations:{session_id}:{request_hash}:v1"))
    try:
        result, _ = _update_episteme(session.profile_id, now, update_id, evidence)
        updated_profile = result["profile"]
        if episteme_profile_size(updated_profile) > MAX_PROFILE_BYTES:
            raise EpistemeCommandRejected("Episteme profile exceeds the storage limit")
    except EpistemeRuntimeUnavailable:
        db.session.rollback()
        existing.status = "unavailable"
        existing.updated_at = now_utc_iso()
        db.session.commit()
        return jsonify(sessionId=session_id, status="unavailable", paths=[])
    except (EpistemeRevisionConflict, EpistemeCommandRejected) as update_error:
        db.session.rollback()
        existing.status = "unavailable"
        existing.updated_at = now_utc_iso()
        db.session.commit()
        return _error(str(update_error), 409 if isinstance(update_error, EpistemeRevisionConflict) else 422)

    existing.status = "complete"
    existing.paths_json = public_paths
    existing.evidence_json = evidence
    existing.generation_metadata = metadata
    existing.episteme_revision = updated_profile["revision"]
    existing.updated_at = now_utc_iso()
    db.session.commit()
    return _result(existing, status="generated")


@postgame_associations_api.post("/api/future/sessions/<session_id>/episteme-associations/<association_id>/expand")
def expand_postgame_association(session_id, association_id):
    """Generate one bounded second-generation path from an explicitly kept path."""
    if not _local_origin():
        return _error("Cross-origin association writes are not allowed", 403)
    body, error = _read_json()
    if error:
        return error
    if set(body) != {"requestId"} or not _valid_uuid(body.get("requestId")):
        return _error("Association expansion requires requestId", 422)
    context, error = _finished_context(session_id)
    if error:
        return error
    session, analysis, manifest_record, profile = context
    record = db.session.get(PostgameAssociationRunRecord, session_id)
    if record is None or record.status != "complete":
        return _error("Association paths are not ready", 409)
    stored_paths = record.paths_json or []
    parent = next((item for item in stored_paths if isinstance(item, dict) and item.get("associationId") == association_id and not item.get("expansionOf")), None)
    if parent is None:
        return _error("Association path not found", 404)
    existing_children = [item for item in stored_paths if isinstance(item, dict) and item.get("expansionOf") == association_id]
    if existing_children:
        return _result(record, status="replayed", replayed=True)
    response_row = PostgameAssociationResponseRecord.query.filter_by(
        session_id=session_id, association_id=association_id, status="complete"
    ).order_by(PostgameAssociationResponseRecord.recorded_at.desc()).first()
    if response_row is None or response_row.response_json.get("response") != "keep":
        return _error("Keep a path before following it", 409)
    source, seed_ids = _manifest_context(manifest_record.manifest_json, analysis.analysis_json, profile)
    expansion_concept_id = f"association:{association_id}"
    seed_ids = set(seed_ids)
    seed_ids.add(expansion_concept_id)
    source = dict(source)
    source["profileConcepts"] = [
        *source.get("profileConcepts", []),
        {"conceptId": expansion_concept_id, "label": parent["phrase"], "language": parent.get("language", "en")},
    ][:18]
    try:
        paths, metadata = _generate_paths(source, seed_ids, "en")
    except PostgameAssociationRuntimeUnavailable as unavailable:
        return _error(str(unavailable), 503)
    now = now_utc_iso()
    expires_at = (datetime.fromisoformat(now.replace("Z", "+00:00")) + timedelta(days=30)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    evidence = []
    public_paths = []
    for path in paths:
        path_hash = _hash(path)
        child_id = str(uuid5(NAMESPACE_URL, f"crossword-session-association-expansion:{session_id}:{association_id}:{path_hash}:v1"))
        evidence_id = str(uuid5(NAMESPACE_URL, f"crossword-session-association-expansion-evidence:{child_id}:v1"))
        evidence.append({
            "evidenceId": evidence_id,
            "recordedAt": now,
            "type": "association-proposal",
            "associationId": child_id,
            "phrase": path["phrase"],
            "language": path["language"],
            "relation": path["relation"],
            "parentConceptIds": path["parentConceptIds"],
            "explanation": path["explanation"],
            "origin": "model-proposal",
            "expiresAt": expires_at,
            "expireAfterSessions": 10,
        })
        public_paths.append({**path, "associationId": child_id, "evidenceId": evidence_id, "expansionOf": association_id, "depth": 1})
    update_id = str(uuid5(NAMESPACE_URL, f"crossword-session-association-expansion:{session_id}:{association_id}:update-v1"))
    try:
        result, _ = _update_episteme(session.profile_id, now, update_id, evidence)
    except EpistemeRevisionConflict as conflict:
        db.session.rollback()
        return _error(str(conflict), 409)
    except (EpistemeRuntimeUnavailable, EpistemeCommandRejected) as failure:
        db.session.rollback()
        return _error(str(failure), 503)
    record.paths_json = [*stored_paths, *public_paths]
    record.evidence_json = [*(record.evidence_json or []), *evidence]
    generation = dict(record.generation_metadata or {})
    expansion_receipts = list(generation.get("expansions", [])) if isinstance(generation.get("expansions", []), list) else []
    expansion_receipts.append({"parentAssociationId": association_id, "pathCount": len(public_paths), "metadata": metadata})
    generation["expansions"] = expansion_receipts
    record.generation_metadata = generation
    record.episteme_revision = result["profile"]["revision"]
    record.updated_at = now
    db.session.commit()
    return _result(record, status="expanded")


@postgame_associations_api.post("/api/future/sessions/<session_id>/episteme-associations/<association_id>/response")
def respond_to_postgame_association(session_id, association_id):
    if not _local_origin():
        return _error("Cross-origin association writes are not allowed", 403)
    body, error = _read_json()
    if error:
        return error
    if set(body) != {"responseId", "response"} or not _valid_uuid(body.get("responseId")) or body.get("response") not in {"keep", "not-for-me", "pass"}:
        return _error("Association response must contain responseId and response", 422)
    context, error = _finished_context(session_id)
    if error:
        return error
    session, _, _, _ = context
    record = db.session.get(PostgameAssociationRunRecord, session_id)
    if record is None or record.status != "complete":
        return _error("Association paths are not ready", 409)
    path = next((item for item in record.paths_json or [] if item.get("associationId") == association_id), None)
    if path is None:
        return _error("Association path not found", 404)
    response_id = body["responseId"]
    request_hash = _hash(body)
    existing = db.session.get(PostgameAssociationResponseRecord, response_id)
    if existing is not None:
        if existing.request_hash != request_hash or existing.session_id != session_id or existing.association_id != association_id:
            return _error("Response id was reused with different association data", 409)
        return jsonify(responseId=response_id, associationId=association_id, response=existing.response_json["response"], profileRevision=existing.episteme_revision, replayed=True)
    recorded_at = now_utc_iso()
    evidence_id = str(uuid5(NAMESPACE_URL, f"crossword-session-association-response:{response_id}:v1"))
    evidence = {
        "evidenceId": evidence_id,
        "recordedAt": recorded_at,
        "type": "association-response",
        "associationId": association_id,
        "proposalEvidenceId": path["evidenceId"],
        "response": body["response"],
    }
    row = PostgameAssociationResponseRecord(
        response_id=response_id,
        session_id=session_id,
        profile_id=session.profile_id,
        association_id=association_id,
        request_hash=request_hash,
        response_json={**body, "recordedAt": recorded_at},
        evidence_json=evidence,
        status="pending",
        recorded_at=recorded_at,
    )
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        winner = db.session.get(PostgameAssociationResponseRecord, response_id)
        if winner is not None and winner.request_hash == request_hash:
            return jsonify(responseId=response_id, associationId=association_id, response=winner.response_json["response"], profileRevision=winner.episteme_revision, replayed=True)
        return _error("A conflicting association response won the retry race", 409)
    update_id = str(uuid5(NAMESPACE_URL, f"crossword-session-association-response-update:{response_id}:v1"))
    try:
        result, _ = _update_episteme(session.profile_id, recorded_at, update_id, [evidence])
        row.episteme_revision = result["profile"]["revision"]
        row.status = "complete"
        db.session.commit()
    except EpistemeRevisionConflict as conflict:
        db.session.rollback()
        return _error(str(conflict), 409)
    except (EpistemeRuntimeUnavailable, EpistemeCommandRejected) as failure:
        db.session.rollback()
        return _error(str(failure), 503)
    response = jsonify(responseId=response_id, associationId=association_id, response=body["response"], profileRevision=row.episteme_revision, replayed=bool(result.get("replayed")))
    response.headers["Cache-Control"] = "no-store"
    return response
