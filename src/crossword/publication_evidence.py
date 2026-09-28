"""Authenticated, immutable-byte evidence artifacts for future V2 review.

Artifacts are integrity-bound to an existing review candidate and to the
reviewer identity configured by the local host. Their presence and hashes do
not prove that the bytes are truthful, that a reviewer authored them, or that
the candidate is ready for publication. This module deliberately has no
publication writer and exposes no artifact read, update, or delete route.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from uuid import UUID, uuid4

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import CheckConstraint, ForeignKey, LargeBinary, func, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .database import db
from .future_puzzles import (
    FuturePuzzleV2CandidateRecord,
    PersonalizedV2CandidateRejected,
    validate_personalized_v2_review_candidate,
)
from .reviewer_auth import (
    ReviewerAuthenticationError,
    ReviewerAuthConfigError,
    resolve_reviewer_principal,
)


publication_evidence_api = Blueprint("publication_evidence_api", __name__)

PUBLICATION_EVIDENCE_KINDS = frozenset(
    {
        "source-artifact",
        "license-terms-review",
        "clue-semantic-review",
        "clue-editorial-review",
        "challenger-run",
        "crossing-certificate",
        "solve-simulation",
        "weekday-review",
        "mechanic-route",
    }
)
_CANDIDATE_DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")
_RAW_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MIME_TYPE = re.compile(r"^[a-z0-9!#$&^_.+-]{1,64}/[a-z0-9!#$&^_.+-]{1,64}$")
MAX_PUBLICATION_EVIDENCE_BYTES = 8 * 1024 * 1024
# Immutable review material is retained by design. Cap aggregate storage to
# bound disk consumption even when every individual upload is within its limit.
MAX_TOTAL_PUBLICATION_EVIDENCE_BYTES = 256 * 1024 * 1024
MAX_PACKET_EVIDENCE_REFS = 4096
MAX_PUBLICATION_REVIEW_PACKET_BYTES = 16 * 1024 * 1024
MAX_CANDIDATE_ROWS_PER_DIGEST = 16
MAX_EVIDENCE_CLAIM_PATH_LENGTH = 128
_PACKET_INDEX = r"(?:0|[1-9][0-9]{0,3})"
_EVIDENCE_CLAIM_PATH_PATTERNS = (
    re.compile(rf"^sourceAttestations\[{_PACKET_INDEX}\]\.evidenceRefs\[{_PACKET_INDEX}\]$"),
    re.compile(rf"^clueAdjudications\[{_PACKET_INDEX}\]\.evidenceRefs\[{_PACKET_INDEX}\]$"),
    re.compile(rf"^clueAdjudications\[{_PACKET_INDEX}\]\.challenger\.evidenceRefs\[{_PACKET_INDEX}\]$"),
    re.compile(rf"^crossingReview\.certificates\[{_PACKET_INDEX}\]\.evidenceRefs\[{_PACKET_INDEX}\]$"),
    re.compile(rf"^crossingReview\.certificates\[{_PACKET_INDEX}\]\.topologyConstraint\.evidenceRefs\[{_PACKET_INDEX}\]$"),
    re.compile(rf"^crossingReview\.simulation\.evidenceRefs\[{_PACKET_INDEX}\]$"),
    re.compile(rf"^weekdayReview\.evidenceRefs\[{_PACKET_INDEX}\]$"),
    re.compile(rf"^weekdayReview\.blindClassifications\[{_PACKET_INDEX}\]\.rationale$"),
    re.compile(r"^weekdayReview\.mechanicRoute\.evidenceRefs\[(?:0|[1-9][0-9]{0,3})\]$"),
)
_INDEXED_CLAIM_PATH = re.compile(r"\[(0|[1-9][0-9]{0,3})\]")
_SOURCE_CLAIM_PATH = re.compile(r"^sourceAttestations\[")
_CLUE_CLAIM_PATH = re.compile(r"^clueAdjudications\[")
_CROSSING_CERTIFICATE_CLAIM_PATH = re.compile(r"^crossingReview\.certificates\[")
_WEEKDAY_CLAIM_PATH = re.compile(r"^weekdayReview\.")


class PublicationEvidenceRejected(ValueError):
    """Evidence metadata or packet references failed a closed validation."""


class PublicationEvidenceArtifact(db.Model):
    """Immutable host metadata and exact uploaded bytes for one review file."""

    __tablename__ = "future_publication_evidence_v2"

    artifact_id = db.Column(db.String(36), primary_key=True)
    sha256 = db.Column(db.String(64), nullable=False, index=True)
    kind = db.Column(db.String(40), nullable=False)
    candidate_digest = db.Column(db.String(71), nullable=False, index=True)
    media_type = db.Column(db.String(129), nullable=False)
    reviewer_id = db.Column(db.String(128), nullable=False)
    recorded_at = db.Column(db.String(40), nullable=False)
    artifact_bytes = db.Column(LargeBinary, nullable=False)


class PublicationEvidenceArtifactClaim(db.Model):
    """One immutable packet-location assignment for a stored artifact.

    A separate table lets existing local databases gain this requirement via
    ``create_all`` without rebuilding the evidence-byte table. Its primary key
    also prevents one upload from being assigned to multiple claims.
    """

    __tablename__ = "future_publication_evidence_claim_v2"

    artifact_id = db.Column(
        db.String(36),
        ForeignKey("future_publication_evidence_v2.artifact_id"),
        primary_key=True,
    )
    claim_path = db.Column(db.String(MAX_EVIDENCE_CLAIM_PATH_LENGTH), nullable=False)


class PublicationEvidenceStorageQuota(db.Model):
    """Atomic aggregate byte counter for immutable evidence uploads.

    The singleton is seeded from any artifacts written before this quota was
    introduced. Every new artifact reserves capacity by conditional SQL update
    in the same transaction that stores its bytes.
    """

    __tablename__ = "future_publication_evidence_quota_v2"
    __table_args__ = (
        CheckConstraint(
            "id = 1", name="ck_future_publication_evidence_quota_singleton"
        ),
        CheckConstraint(
            "bytes_used >= 0", name="ck_future_publication_evidence_quota_nonnegative"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    bytes_used = db.Column(db.BigInteger, nullable=False)


def _response(payload: dict, status: int):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _candidate_digest(value: object) -> tuple[str, str]:
    if not isinstance(value, str):
        raise PublicationEvidenceRejected("candidate-digest-invalid")
    match = _CANDIDATE_DIGEST.fullmatch(value)
    if match is None:
        raise PublicationEvidenceRejected("candidate-digest-invalid")
    return value, match.group(1)


def _validated_candidate(candidate_digest: str):
    """Find and strictly revalidate a candidate without profile-scoped input."""
    exact_digest, candidate_hash = _candidate_digest(candidate_digest)
    records = (
        db.session.query(FuturePuzzleV2CandidateRecord)
        .filter(FuturePuzzleV2CandidateRecord.candidate_hash == candidate_hash)
        .limit(MAX_CANDIDATE_ROWS_PER_DIGEST + 1)
        .all()
    )
    if not records:
        return None
    if len(records) > MAX_CANDIDATE_ROWS_PER_DIGEST:
        raise PublicationEvidenceRejected("candidate-identity-conflict")

    canonical = None
    candidate_id = None
    for record in records:
        try:
            manifest = validate_personalized_v2_review_candidate(record.manifest_json)
            encoded = json.dumps(
                manifest,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (PersonalizedV2CandidateRejected, TypeError, ValueError, RecursionError, UnicodeError):
            raise PublicationEvidenceRejected("candidate-integrity-invalid") from None
        if (
            record.candidate_hash != candidate_hash
            or manifest["integrity"]["value"] != exact_digest
            or record.candidate_id != manifest["id"]
            or manifest["quality"]["verdict"] != "review"
        ):
            raise PublicationEvidenceRejected("candidate-integrity-invalid")
        if canonical is None:
            canonical = encoded
            candidate_id = record.candidate_id
        elif canonical != encoded or candidate_id != record.candidate_id:
            # The profile-scoped candidate key may have equivalent duplicates,
            # but a shared digest that resolves to conflicting rows is unsafe.
            raise PublicationEvidenceRejected("candidate-identity-conflict")
    return records[0]


def _request_reviewer():
    return resolve_reviewer_principal(
        current_app.config, request.headers.get("Authorization")
    )


@publication_evidence_api.post("/api/future/evidence/v2/artifacts")
def upload_publication_evidence_artifact():
    """Store raw evidence bytes after host authentication and candidate checks."""
    try:
        principal = _request_reviewer()
    except ReviewerAuthConfigError:
        return _response({"error": "Reviewer authentication is unavailable"}, 503)
    except ReviewerAuthenticationError:
        response = _response({"error": "Reviewer authentication required"}, 401)
        response.headers["WWW-Authenticate"] = "Bearer"
        return response

    exact_digest = request.headers.get("X-Candidate-Digest")
    kind = request.headers.get("X-Evidence-Kind")
    claim_path = request.headers.get("X-Evidence-Claim-Path")
    try:
        exact_digest, _candidate_hash = _candidate_digest(exact_digest)
    except PublicationEvidenceRejected:
        return _response({"error": "Invalid candidate digest"}, 400)
    if not isinstance(kind, str) or kind not in PUBLICATION_EVIDENCE_KINDS:
        return _response({"error": "Invalid publication evidence kind"}, 400)
    try:
        claim_path = _validated_claim_path(claim_path)
    except PublicationEvidenceRejected:
        return _response({"error": "Invalid evidence claim path"}, 400)
    if kind not in _claim_path_allowed_kinds(claim_path):
        return _response({"error": "Evidence kind does not match claim path"}, 400)

    content_length = request.content_length
    if content_length is None:
        return _response({"error": "Content-Length is required"}, 411)
    if content_length < 1:
        return _response({"error": "Evidence artifact must not be empty"}, 400)
    if content_length > MAX_PUBLICATION_EVIDENCE_BYTES:
        return _response({"error": "Evidence artifact exceeds the upload limit"}, 413)

    media_type = request.mimetype
    if (
        not isinstance(media_type, str)
        or _MIME_TYPE.fullmatch(media_type.lower()) is None
    ):
        return _response({"error": "A valid media type is required"}, 415)
    media_type = media_type.lower()

    try:
        candidate = _validated_candidate(exact_digest)
    except PublicationEvidenceRejected:
        return _response({"error": "Candidate failed host validation"}, 503)
    except SQLAlchemyError:
        db.session.rollback()
        return _response({"error": "Candidate lookup is unavailable"}, 503)
    if candidate is None:
        return _response({"error": "Review candidate not found"}, 404)

    try:
        artifact_bytes = request.stream.read(MAX_PUBLICATION_EVIDENCE_BYTES + 1)
    except (OSError, ValueError):
        return _response({"error": "Evidence upload could not be read"}, 400)
    if len(artifact_bytes) != content_length:
        return _response({"error": "Evidence body length does not match Content-Length"}, 400)
    if len(artifact_bytes) > MAX_PUBLICATION_EVIDENCE_BYTES:
        return _response({"error": "Evidence artifact exceeds the upload limit"}, 413)

    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    artifact_id = str(uuid4())
    digest = hashlib.sha256(artifact_bytes).hexdigest()
    record = PublicationEvidenceArtifact(
        artifact_id=artifact_id,
        sha256=digest,
        kind=kind,
        candidate_digest=exact_digest,
        media_type=media_type,
        reviewer_id=principal.reviewer_id,
        recorded_at=now,
        artifact_bytes=artifact_bytes,
    )
    claim = PublicationEvidenceArtifactClaim(
        artifact_id=artifact_id,
        claim_path=claim_path,
    )
    # End the candidate lookup's read transaction before beginning the
    # write-side reservation. This avoids holding a stale SQLite read snapshot
    # while concurrent reviewers contend for the singleton quota row.
    db.session.rollback()
    try:
        stored = _store_artifact_with_quota(record, claim)
    except (IntegrityError, SQLAlchemyError):
        db.session.rollback()
        return _response({"error": "Evidence artifact could not be stored"}, 503)
    if not stored:
        return _response({"error": "Publication evidence storage capacity reached"}, 507)

    ref = {"artifactId": artifact_id, "sha256": digest, "kind": kind}
    metadata = {
        **ref,
        "candidateDigest": exact_digest,
        "claimPath": claim_path,
        "mediaType": media_type,
        "reviewerId": principal.reviewer_id,
        "recordedAt": now,
    }
    return _response({"artifact": metadata, "ref": ref}, 201)


def _store_artifact_with_quota(
    record: PublicationEvidenceArtifact,
    claim: PublicationEvidenceArtifactClaim,
) -> bool:
    """Reserve total capacity atomically with immutable artifact insertion.

    The conditional ``UPDATE`` serializes reservations at the database row,
    so simultaneous requests cannot both pass a Python-side sum check. The
    row is initialized once from existing blob lengths for compatibility with
    databases that already contain evidence artifacts.
    """
    incoming_bytes = len(record.artifact_bytes)
    if incoming_bytes < 1 or incoming_bytes > MAX_PUBLICATION_EVIDENCE_BYTES:
        raise ValueError("artifact byte length is outside the upload bounds")

    quota = db.session.get(PublicationEvidenceStorageQuota, 1)
    if quota is None:
        existing_bytes = (
            db.session.query(
                func.coalesce(
                    func.sum(func.length(PublicationEvidenceArtifact.artifact_bytes)), 0
                )
            ).scalar()
        )
        db.session.add(
            PublicationEvidenceStorageQuota(id=1, bytes_used=int(existing_bytes or 0))
        )
        # Persist initialization independently: if this upload is denied for
        # capacity, the seeded accounting row must still include legacy blobs.
        # A concurrent first request may win the singleton insert; after that
        # conflict, re-read its committed row and reserve through the same
        # conditional update below.
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            if db.session.get(PublicationEvidenceStorageQuota, 1) is None:
                raise

    reservation = db.session.execute(
        update(PublicationEvidenceStorageQuota)
        .where(
            PublicationEvidenceStorageQuota.id == 1,
            PublicationEvidenceStorageQuota.bytes_used
            <= MAX_TOTAL_PUBLICATION_EVIDENCE_BYTES - incoming_bytes,
        )
        .values(
            bytes_used=PublicationEvidenceStorageQuota.bytes_used + incoming_bytes
        )
    )
    if reservation.rowcount != 1:
        db.session.rollback()
        return False

    db.session.add(record)
    db.session.add(claim)
    db.session.commit()
    return True


def _require_record(value: object, *, path: str) -> dict:
    if type(value) is not dict:
        raise PublicationEvidenceRejected(f"packet-reference-invalid:{path}")
    return value


def _require_list(value: object, *, path: str, nonempty: bool = True) -> list:
    if (
        type(value) is not list
        or (nonempty and not value)
        or len(value) > MAX_PACKET_EVIDENCE_REFS
    ):
        raise PublicationEvidenceRejected(f"packet-reference-invalid:{path}")
    return value


def _collect_refs(packet: object) -> list[tuple[str, dict]]:
    root = _require_record(packet, path="packet")
    _check_packet_size(root)
    if root.get("schema") != "puzzle-v2-publication-review-v1":
        raise PublicationEvidenceRejected("packet-schema-invalid")
    source_attestations = _require_list(
        root.get("sourceAttestations"), path="sourceAttestations"
    )
    clue_adjudications = _require_list(
        root.get("clueAdjudications"), path="clueAdjudications"
    )
    crossing_review = _require_record(root.get("crossingReview"), path="crossingReview")
    weekday_review = _require_record(root.get("weekdayReview"), path="weekdayReview")

    refs: list[tuple[str, dict]] = []

    def append_ref(path: str, reference: object) -> None:
        # Enforce the aggregate budget before adding a reference. Checking only
        # after all nested arrays were copied allowed oversized packets to
        # allocate an arbitrarily large intermediate list.
        if len(refs) >= MAX_PACKET_EVIDENCE_REFS:
            raise PublicationEvidenceRejected("packet-reference-invalid:total")
        refs.append((path, reference))

    def add_many(value: object, path: str) -> None:
        for index, reference in enumerate(_require_list(value, path=path)):
            append_ref(f"{path}[{index}]", reference)

    for index, raw in enumerate(source_attestations):
        item = _require_record(raw, path=f"sourceAttestations[{index}]")
        add_many(item.get("evidenceRefs"), f"sourceAttestations[{index}].evidenceRefs")

    for index, raw in enumerate(clue_adjudications):
        item = _require_record(raw, path=f"clueAdjudications[{index}]")
        add_many(item.get("evidenceRefs"), f"clueAdjudications[{index}].evidenceRefs")
        challenger = _require_record(
            item.get("challenger"), path=f"clueAdjudications[{index}].challenger"
        )
        add_many(
            challenger.get("evidenceRefs"),
            f"clueAdjudications[{index}].challenger.evidenceRefs",
        )

    certificates = _require_list(
        crossing_review.get("certificates"), path="crossingReview.certificates"
    )
    for index, raw in enumerate(certificates):
        item = _require_record(raw, path=f"crossingReview.certificates[{index}]")
        add_many(item.get("evidenceRefs"), f"crossingReview.certificates[{index}].evidenceRefs")
        if "topologyConstraint" in item:
            topology = _require_record(
                item["topologyConstraint"],
                path=f"crossingReview.certificates[{index}].topologyConstraint",
            )
            add_many(
                topology.get("evidenceRefs"),
                f"crossingReview.certificates[{index}].topologyConstraint.evidenceRefs",
            )

    simulation = _require_record(
        crossing_review.get("simulation"), path="crossingReview.simulation"
    )
    add_many(simulation.get("evidenceRefs"), "crossingReview.simulation.evidenceRefs")

    add_many(weekday_review.get("evidenceRefs"), "weekdayReview.evidenceRefs")
    blind_classifications = _require_list(
        weekday_review.get("blindClassifications"),
        path="weekdayReview.blindClassifications",
    )
    for index, raw in enumerate(blind_classifications):
        item = _require_record(raw, path=f"weekdayReview.blindClassifications[{index}]")
        append_ref(
            f"weekdayReview.blindClassifications[{index}].rationale",
            item.get("rationale"),
        )

    if "mechanicRoute" in weekday_review:
        mechanic = _require_record(
            weekday_review["mechanicRoute"], path="weekdayReview.mechanicRoute"
        )
        add_many(mechanic.get("evidenceRefs"), "weekdayReview.mechanicRoute.evidenceRefs")

    if not refs or len(refs) > MAX_PACKET_EVIDENCE_REFS:
        raise PublicationEvidenceRejected("packet-reference-invalid:total")
    return refs


def _check_packet_size(packet: dict) -> None:
    """Reject a serialized packet beyond the bounded review-packet budget."""
    encoder = json.JSONEncoder(
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    total_bytes = 0
    try:
        for fragment in encoder.iterencode(packet):
            if len(fragment) > MAX_PUBLICATION_REVIEW_PACKET_BYTES - total_bytes:
                raise PublicationEvidenceRejected("packet-size-limit-exceeded")
            total_bytes += len(fragment.encode("utf-8"))
            if total_bytes > MAX_PUBLICATION_REVIEW_PACKET_BYTES:
                raise PublicationEvidenceRejected("packet-size-limit-exceeded")
    except PublicationEvidenceRejected:
        raise
    except (TypeError, ValueError, RecursionError, UnicodeError):
        raise PublicationEvidenceRejected("packet-serialization-invalid") from None


def resolve_publication_packet_evidence(packet: object, candidate_digest: str):
    """Resolve every packet artifact ref to candidate-bound, hash-checked rows.

    The returned tuple follows the packet's reference order. Every artifact is
    re-read from the host database and its digest is recomputed from the stored
    bytes. A digest verifies byte consistency only; it is not source truth,
    reviewer authorship, licensing, or publication approval. This resolver does
    not validate the packet digest, exact packet schema, or claim outcomes.
    It matches the authenticated uploader to packet-declared reviewer IDs only
    for human-owned evidence locations; that narrow check is not a complete
    reviewer-identity or publication authorization boundary. Any future
    publication call site must run the shared TypeScript gate and independently
    verify all reviewer identities and claims before considering its residual
    ``reviewer-evidence-unverified`` result.
    """
    exact_digest, _candidate_hash = _candidate_digest(candidate_digest)
    root = _require_record(packet, path="packet")
    if root.get("candidateDigest") != exact_digest:
        raise PublicationEvidenceRejected("candidate-binding-mismatch")
    for name in ("crossingReview", "weekdayReview"):
        nested = _require_record(root.get(name), path=name)
        if nested.get("candidateDigest") != exact_digest:
            raise PublicationEvidenceRejected(f"candidate-binding-mismatch:{name}")
    candidate = _validated_candidate(exact_digest)
    if candidate is None:
        raise PublicationEvidenceRejected("candidate-not-found")

    resolved = []
    for path, raw_ref in _collect_refs(packet):
        path = _validated_claim_path(path)
        ref = _require_record(raw_ref, path=path)
        if set(ref) != {"artifactId", "sha256", "kind"}:
            raise PublicationEvidenceRejected(f"artifact-reference-shape-invalid:{path}")
        artifact_id = ref.get("artifactId")
        digest = ref.get("sha256")
        kind = ref.get("kind")
        if (
            not isinstance(artifact_id, str)
            or not _valid_canonical_uuid(artifact_id)
            or not isinstance(digest, str)
            or _RAW_SHA256.fullmatch(digest) is None
            or not isinstance(kind, str)
            or kind not in PUBLICATION_EVIDENCE_KINDS
            or kind not in _claim_path_allowed_kinds(path)
        ):
            raise PublicationEvidenceRejected(f"artifact-reference-invalid:{path}")
        record = db.session.get(PublicationEvidenceArtifact, artifact_id)
        claim = db.session.get(PublicationEvidenceArtifactClaim, artifact_id)
        if (
            record is None
            or record.artifact_id != artifact_id
            or record.candidate_digest != exact_digest
            or record.sha256 != digest
            or record.kind != kind
            or type(record.artifact_bytes) is not bytes
            or hashlib.sha256(record.artifact_bytes).hexdigest() != digest
            or claim is None
            or claim.claim_path != path
            or not _reviewer_binding_matches(
                root, path, record.reviewer_id if record is not None else None
            )
        ):
            raise PublicationEvidenceRejected(f"artifact-unresolved-or-corrupt:{path}")
        resolved.append(record)
    return tuple(resolved)


def _valid_canonical_uuid(value: str) -> bool:
    try:
        return str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _validated_claim_path(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > MAX_EVIDENCE_CLAIM_PATH_LENGTH
        or not any(pattern.fullmatch(value) for pattern in _EVIDENCE_CLAIM_PATH_PATTERNS)
    ):
        raise PublicationEvidenceRejected("evidence-claim-path-invalid")
    for index_text in _INDEXED_CLAIM_PATH.findall(value):
        if int(index_text) >= MAX_PACKET_EVIDENCE_REFS:
            raise PublicationEvidenceRejected("evidence-claim-path-invalid")
    return value


def _claim_path_allowed_kinds(claim_path: str) -> frozenset[str]:
    if _SOURCE_CLAIM_PATH.match(claim_path):
        return frozenset({"source-artifact", "license-terms-review"})
    if _CLUE_CLAIM_PATH.match(claim_path):
        if ".challenger." in claim_path:
            return frozenset({"challenger-run"})
        return frozenset({"clue-semantic-review", "clue-editorial-review"})
    if _CROSSING_CERTIFICATE_CLAIM_PATH.match(claim_path):
        return frozenset({"crossing-certificate"})
    if claim_path.startswith("crossingReview.simulation."):
        return frozenset({"solve-simulation"})
    if claim_path.startswith("weekdayReview.blindClassifications["):
        return frozenset({"weekday-review"})
    if claim_path.startswith("weekdayReview.mechanicRoute."):
        return frozenset({"mechanic-route"})
    if _WEEKDAY_CLAIM_PATH.match(claim_path):
        return frozenset({"weekday-review"})
    return frozenset()


def _packet_reviewer_for_claim(root: dict, claim_path: str) -> str | None:
    """Get the packet-declared actor for a human-owned evidence location."""
    indices = [int(index) for index in _INDEXED_CLAIM_PATH.findall(claim_path)]
    if _SOURCE_CLAIM_PATH.match(claim_path):
        collection = root.get("sourceAttestations")
        owner = collection[indices[0]] if type(collection) is list and indices[0] < len(collection) else None
    elif _CLUE_CLAIM_PATH.match(claim_path):
        collection = root.get("clueAdjudications")
        owner = collection[indices[0]] if type(collection) is list and indices[0] < len(collection) else None
        if ".challenger." in claim_path:
            return None
    elif _CROSSING_CERTIFICATE_CLAIM_PATH.match(claim_path):
        crossing = root.get("crossingReview")
        collection = crossing.get("certificates") if type(crossing) is dict else None
        owner = collection[indices[0]] if type(collection) is list and indices[0] < len(collection) else None
    elif claim_path.startswith("weekdayReview.blindClassifications["):
        weekday = root.get("weekdayReview")
        collection = weekday.get("blindClassifications") if type(weekday) is dict else None
        owner = collection[indices[0]] if type(collection) is list and indices[0] < len(collection) else None
    elif claim_path.startswith("weekdayReview.evidenceRefs["):
        owner = root.get("weekdayReview")
    else:
        # Challenger, simulator, and mechanic-route evidence are machine- or
        # route-owned artifacts. They remain claim-bound but have no human actor.
        return None
    if type(owner) is not dict:
        return ""
    reviewer_id = owner.get("reviewerId")
    return reviewer_id if isinstance(reviewer_id, str) else ""


def _reviewer_binding_matches(
    packet: dict, claim_path: str, stored_reviewer_id: str | None
) -> bool:
    """Match the authenticated uploader to a declared human reviewer claim."""
    packet_reviewer_id = _packet_reviewer_for_claim(packet, claim_path)
    if packet_reviewer_id is None:
        return True
    return bool(packet_reviewer_id) and packet_reviewer_id == stored_reviewer_id
