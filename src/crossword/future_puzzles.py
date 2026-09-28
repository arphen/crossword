"""Separate V1 replay and V2 review-candidate persistence boundaries."""
from datetime import datetime, timezone
import hashlib
import json
import re
from uuid import UUID

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from .database import db
from .legacy_manifest import to_puzzle_document, verify_integrity
from .personalized_manifest import validate_personalized_manifest


future_puzzle_candidates_api = Blueprint("future_puzzle_candidates_api", __name__)
_V2_DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")
_V2_CANDIDATE_ID = re.compile(r"^personalized-[0-9a-f]{32}$")
_PRIVATE_PROVENANCE_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_LEGACY_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
PRIVATE_PROVENANCE_VERSION = "private-puzzle-provenance-v1"
MAX_PRIVATE_PROVENANCE_BYTES = 512 * 1024


class FuturePuzzleManifestRecord(db.Model):
    __tablename__ = "future_puzzle_manifests"

    puzzle_hash = db.Column(db.String(64), primary_key=True)
    puzzle_id = db.Column(db.String(160), nullable=False, unique=True)
    manifest_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.String(40), nullable=False)


class FuturePuzzleProvenanceRecord(db.Model):
    """Owner-scoped clue/fill provenance for a playable private manifest.

    The legacy manifest remains the immutable replay contract.  This separate
    table preserves the experimental model receipt without widening that
    contract or exposing profile evidence through daily-puzzle routes.
    """

    __tablename__ = "future_puzzle_provenance"

    puzzle_hash = db.Column(db.String(64), primary_key=True)
    profile_id = db.Column(db.String(36), primary_key=True)
    provenance_json = db.Column(db.JSON, nullable=False)
    provenance_digest = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.String(40), nullable=False)


class FutureSolveAnalysisRecord(db.Model):
    __tablename__ = "future_solve_analyses"

    session_id = db.Column(db.String(36), primary_key=True)
    puzzle_hash = db.Column(db.String(64), nullable=False, index=True)
    analysis_version = db.Column(db.String(80), nullable=False)
    analysis_json = db.Column(db.JSON, nullable=False)
    finalized = db.Column(db.Boolean, nullable=False, default=False)
    updated_at = db.Column(db.String(40), nullable=False)


class FuturePuzzleV2CandidateRecord(db.Model):
    """Profile-scoped immutable storage for non-playable V2 review candidates.

    This table is intentionally separate from ``future_puzzle_manifests``:
    the V1 solve-session API only consults the legacy registry.
    """

    __tablename__ = "future_puzzle_v2_candidates"
    __table_args__ = (
        db.Index("ix_future_puzzle_v2_candidate_id", "candidate_id"),
        db.Index("ix_future_puzzle_v2_candidate_job", "job_id"),
    )

    profile_id = db.Column(db.String(36), primary_key=True)
    candidate_hash = db.Column(db.String(64), primary_key=True)
    candidate_id = db.Column(db.String(160), nullable=False)
    job_id = db.Column(db.String(36), nullable=False)
    manifest_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.String(40), nullable=False)


def canonical_manifest_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _private_provenance_projection(value):
    """Canonicalize one bounded private receipt before it enters SQLite."""
    if not isinstance(value, dict):
        raise ValueError("private provenance must be an object")
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError) as error:
        raise ValueError("private provenance is not canonical JSON") from error
    if len(encoded) > MAX_PRIVATE_PROVENANCE_BYTES:
        raise ValueError("private provenance exceeds the storage limit")
    return json.loads(encoded.decode("utf-8")), encoded


def _private_manifest_identity(manifest):
    if not isinstance(manifest, dict):
        raise ValueError("private puzzle manifest must be an object")
    integrity = manifest.get("integrity")
    value = integrity.get("value") if isinstance(integrity, dict) else None
    if not isinstance(value, str) or not (
        _V2_DIGEST.fullmatch(value) or _LEGACY_DIGEST.fullmatch(value)
    ):
        raise ValueError("private puzzle manifest digest is invalid")
    return value.removeprefix("sha256:")


def stage_private_puzzle_provenance(*, profile_id, manifest, provenance):
    """Stage a profile-owned private receipt in the caller's transaction."""
    if not isinstance(profile_id, str) or not _UUID.fullmatch(profile_id):
        raise ValueError("private provenance profile id is invalid")
    try:
        if str(UUID(profile_id)) != profile_id:
            raise ValueError
    except ValueError as error:
        raise ValueError("private provenance profile id is invalid") from error
    puzzle_hash = _private_manifest_identity(manifest)
    projection, encoded = _private_provenance_projection(provenance)
    digest = hashlib.sha256(encoded).hexdigest()
    existing = db.session.get(FuturePuzzleProvenanceRecord, (puzzle_hash, profile_id))
    if existing is not None:
        if existing.provenance_digest != digest or canonical_manifest_json(existing.provenance_json) != canonical_manifest_json(projection):
            raise ValueError("private provenance identity conflict")
        return existing
    record = FuturePuzzleProvenanceRecord(
        puzzle_hash=puzzle_hash,
        profile_id=profile_id,
        provenance_json=projection,
        provenance_digest=digest,
        created_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    )
    db.session.add(record)
    return record


def store_private_puzzle_provenance(*, profile_id, manifest, provenance):
    """Persist one private receipt, safely replaying an identical write."""
    record = stage_private_puzzle_provenance(
        profile_id=profile_id,
        manifest=manifest,
        provenance=provenance,
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        puzzle_hash = _private_manifest_identity(manifest)
        existing = db.session.get(FuturePuzzleProvenanceRecord, (puzzle_hash, profile_id))
        if existing is None:
            raise
        return existing
    return record


class PersonalizedV2CandidateRejected(ValueError):
    """A candidate failed the strict V2 review-candidate persistence gate."""


def _canonical_v2(value):
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError, UnicodeError) as error:
        raise PersonalizedV2CandidateRejected("v2-candidate-not-canonicalizable") from error


def validate_personalized_v2_review_candidate(value):
    """Return a JSON copy after strict shape, semantics, and digest validation."""
    try:
        encoded = _canonical_v2(value)
        candidate = json.loads(encoded)
    except (PersonalizedV2CandidateRejected, json.JSONDecodeError) as error:
        raise PersonalizedV2CandidateRejected("v2-candidate-not-json") from error
    if (
        not isinstance(candidate, dict)
        or candidate.get("schemaVersion") != 2
        or not isinstance(candidate.get("id"), str)
        or not _V2_CANDIDATE_ID.fullmatch(candidate["id"])
        or not isinstance(candidate.get("quality"), dict)
        or candidate["quality"].get("verdict") != "review"
        or not isinstance(candidate.get("integrity"), dict)
    ):
        raise PersonalizedV2CandidateRejected("v2-review-candidate-required")
    integrity = candidate["integrity"].get("value")
    if not isinstance(integrity, str) or not _V2_DIGEST.fullmatch(integrity):
        raise PersonalizedV2CandidateRejected("v2-candidate-digest-invalid")
    try:
        validate_personalized_manifest(candidate)
    except (TypeError, ValueError, KeyError, RecursionError) as error:
        raise PersonalizedV2CandidateRejected("v2-candidate-validation-failed") from error
    return candidate


def stage_personalized_v2_review_candidate(*, job_id, profile_id, manifest):
    """Stage one strictly checked candidate in the caller's transaction.

    This function never commits. The grid worker stages it together with the
    result/state update, so cancellation and stale-lease fencing roll it back.
    """
    candidate = validate_personalized_v2_review_candidate(manifest)
    integrity = candidate["integrity"]["value"]
    candidate_hash = integrity.removeprefix("sha256:")
    existing = db.session.get(FuturePuzzleV2CandidateRecord, (profile_id, candidate_hash))
    if existing is not None:
        if (
            existing.candidate_id != candidate["id"]
            or canonical_manifest_json(existing.manifest_json) != canonical_manifest_json(candidate)
        ):
            raise PersonalizedV2CandidateRejected("v2-candidate-identity-conflict")
        return existing
    record = FuturePuzzleV2CandidateRecord(
        profile_id=profile_id,
        candidate_hash=candidate_hash,
        candidate_id=candidate["id"],
        job_id=job_id,
        manifest_json=candidate,
        created_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    )
    db.session.add(record)
    return record


def _candidate_error(message, status):
    response = jsonify(error=message, playable=False)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


@future_puzzle_candidates_api.get("/api/future/puzzle-candidates/v2/<candidate_hash>")
def get_personalized_v2_candidate(candidate_hash):
    """Read one owner-scoped review candidate; this route cannot start a solve."""
    profile_id = request.args.get("profileId")
    if not re.fullmatch(r"[0-9a-f]{64}", candidate_hash or ""):
        return _candidate_error("Invalid V2 candidate digest", 400)
    if not isinstance(profile_id, str) or not _UUID.fullmatch(profile_id):
        return _candidate_error("Invalid profile id", 400)
    try:
        if str(UUID(profile_id)) != profile_id:
            return _candidate_error("Invalid profile id", 400)
    except ValueError:
        return _candidate_error("Invalid profile id", 400)

    record = db.session.get(FuturePuzzleV2CandidateRecord, (profile_id, candidate_hash))
    if record is None:
        return _candidate_error("Puzzle candidate not found", 404)
    try:
        manifest = validate_personalized_v2_review_candidate(record.manifest_json)
        if (
            manifest["integrity"]["value"] != f"sha256:{record.candidate_hash}"
            or manifest["id"] != record.candidate_id
        ):
            raise PersonalizedV2CandidateRejected("v2-candidate-storage-digest-mismatch")
        body = {
            "candidateId": record.candidate_id,
            "candidateHash": record.candidate_hash,
            "status": "review",
            "playable": False,
            "manifest": manifest,
        }
        serialized = _canonical_v2(body)
    except (PersonalizedV2CandidateRejected, TypeError, ValueError, KeyError, RecursionError):
        return _candidate_error("Puzzle candidate failed integrity validation", 503)
    response = jsonify(json.loads(serialized))
    response.headers["Cache-Control"] = "no-store"
    return response


@future_puzzle_candidates_api.get("/api/future/sessions/<session_id>/private-provenance")
def get_private_puzzle_provenance(session_id):
    """Return the owner-scoped experimental receipt for a finished/private game."""
    profile_id = request.args.get("profileId")
    if not isinstance(session_id, str) or not _UUID.fullmatch(session_id):
        return _candidate_error("Invalid session id", 400)
    if not isinstance(profile_id, str) or not _UUID.fullmatch(profile_id):
        return _candidate_error("Invalid profile id", 400)
    try:
        if str(UUID(session_id)) != session_id or str(UUID(profile_id)) != profile_id:
            return _candidate_error("Invalid session or profile id", 400)
    except ValueError:
        return _candidate_error("Invalid session or profile id", 400)
    # Import lazily to keep the V1 manifest module independent of the journal
    # module at import time.
    from .session_journal import PersonalSolveSession

    session = db.session.get(PersonalSolveSession, session_id)
    if session is None or session.profile_id != profile_id:
        return _candidate_error("Private provenance not found", 404)
    record = db.session.get(
        FuturePuzzleProvenanceRecord,
        (session.puzzle_hash, profile_id),
    )
    if record is None:
        return _candidate_error("Private provenance not found", 404)
    try:
        projection, encoded = _private_provenance_projection(record.provenance_json)
        digest = hashlib.sha256(encoded).hexdigest()
        if digest != record.provenance_digest or not _PRIVATE_PROVENANCE_DIGEST.fullmatch(digest):
            raise ValueError
    except (TypeError, ValueError, RecursionError, UnicodeError):
        return _candidate_error("Private provenance failed integrity validation", 503)
    response = jsonify(
        {
            "version": PRIVATE_PROVENANCE_VERSION,
            "sessionId": session_id,
            "puzzleHash": session.puzzle_hash,
            "provenanceDigest": f"sha256:{record.provenance_digest}",
            "provenance": projection,
        }
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def register_legacy_puzzle(crossword, *, allow_token_cells=False):
    """Freeze one server-parsed legacy puzzle; identical replays are harmless."""
    manifest = to_puzzle_document(crossword, allow_token_cells=allow_token_cells)
    if not verify_integrity(manifest):
        raise ValueError("Puzzle manifest failed its canonical digest check")
    digest = manifest["integrity"]["value"]
    record = db.session.get(FuturePuzzleManifestRecord, digest)
    if record is not None:
        if canonical_manifest_json(record.manifest_json) != canonical_manifest_json(manifest):
            raise ValueError("Puzzle digest already identifies a different manifest")
        return manifest

    record = FuturePuzzleManifestRecord(
        puzzle_hash=digest,
        puzzle_id=manifest["id"],
        manifest_json=manifest,
        created_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    )
    db.session.add(record)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = db.session.get(FuturePuzzleManifestRecord, digest)
        if existing is None or canonical_manifest_json(existing.manifest_json) != canonical_manifest_json(manifest):
            raise ValueError("Puzzle digest conflicts with an existing manifest") from None
    return manifest
