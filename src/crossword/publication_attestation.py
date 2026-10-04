"""Append-only receipts for authenticated human V2 publication claims.

An attestation receipt records that one configured local reviewer credential
was used to attest one exact, sealed packet claim and its resolved evidence
manifest. It does not establish that the claim is true, that reviewers are
independent humans, that the evidence is sufficient, or that the database
cannot be changed directly. Receipts never change publication state and this
module exposes no update, delete, or receipt-read endpoint.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from uuid import UUID, uuid4

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .database import db
from .publication_evidence import (
    MAX_PUBLICATION_REVIEW_PACKET_BYTES,
    PublicationEvidenceRejected,
    _candidate_digest,
    _validated_candidate,
    resolve_publication_packet_evidence,
)
from .publication_review import (
    PublicationReviewDiagnostic,
    PublicationReviewRejected,
    _snapshot_packet,
    review_publication_packet,
)
from .solve_replay import evaluate_puzzle_v2_publication_gate
from .reviewer_auth import (
    ReviewerAuthenticationError,
    ReviewerAuthConfigError,
    ReviewerPrincipal,
    resolve_reviewer_principal,
)


publication_attestation_api = Blueprint(
    "publication_attestation_api", __name__
)

PUBLICATION_ATTESTATION_PROTOCOL = "puzzle-v2-human-claim-attestation-v1"
_PACKET_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_RAW_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CLAIM_PATH = re.compile(
    r"^(?:sourceAttestations|clueAdjudications|crossingReview\.certificates|"
    r"weekdayReview\.blindClassifications)\[(0|[1-9][0-9]{0,3})\]$"
)
_RECEIPT_PATHS = frozenset({"weekdayReview"})
_MAX_REQUEST_OVERHEAD = 64 * 1024


class PublicationAttestationRejected(ValueError):
    """A claim, packet, or stored attestation failed closed validation."""


class PublicationClaimAttestation(db.Model):
    """Immutable host receipt for one authenticated human packet claim."""

    __tablename__ = "future_publication_attestation_v2"
    __table_args__ = (
        UniqueConstraint(
            "candidate_digest",
            "packet_digest",
            "claim_path",
            "reviewer_id",
            name="uq_future_publication_attestation_claim_v2",
        ),
    )

    attestation_id = db.Column(db.String(36), primary_key=True)
    protocol_version = db.Column(db.String(64), nullable=False)
    candidate_digest = db.Column(db.String(71), nullable=False, index=True)
    packet_digest = db.Column(db.String(71), nullable=False, index=True)
    claim_path = db.Column(db.String(128), nullable=False)
    claim_digest = db.Column(db.String(71), nullable=False)
    evidence_digest = db.Column(db.String(71), nullable=False)
    # Canonical JSON of the ordered manifest. Retaining it makes the digest
    # auditable by the internal coverage resolver without a public read API.
    evidence_manifest_json = db.Column(db.Text, nullable=False)
    reviewer_id = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.String(40), nullable=False)


@dataclass(frozen=True, slots=True)
class HumanPublicationClaim:
    """Pure projection of a human claim root and its packet-bound evidence."""

    claim_path: str
    claim_digest: str
    reviewer_id: str
    # Each entry is (packet artifact-claim path, artifact ID, raw SHA-256, kind).
    evidence_refs: tuple[tuple[str, str, str, str], ...]


@dataclass(frozen=True, slots=True)
class PublicationAttestationCoverage:
    """Read-only completeness result; never an approval or eligibility token."""

    complete: bool
    expected_claim_count: int
    attested_claim_count: int
    missing_claim_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Receipt:
    id: str
    protocolVersion: str
    candidateDigest: str
    packetDigest: str
    claimPath: str
    claimDigest: str
    evidenceDigest: str
    reviewerId: str
    createdAt: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _canonical_json(value: object) -> str:
    """Encode the domain's canonical JSON (sorted keys, stable array order)."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError, UnicodeError):
        raise PublicationAttestationRejected("canonical-json-invalid") from None


def _sha256(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _declared_packet_digest(packet: dict) -> str:
    """Read the digest; the shared TypeScript gate performs canonical hashing.

    Python and JavaScript use different number-to-string rules for some legal
    JSON numbers, so a Python serialization must not re-hash a sealed packet.
    """
    supplied = packet.get("packetDigest")
    if not isinstance(supplied, str) or _PACKET_DIGEST.fullmatch(supplied) is None:
        raise PublicationAttestationRejected("packet-digest-invalid")
    return supplied


def _object(value: object, reason: str) -> dict:
    if type(value) is not dict:
        raise PublicationAttestationRejected(reason)
    return value


def _human_refs(claim: dict, claim_path: str) -> tuple[tuple[str, str, str, str], ...]:
    """Extract only evidence belonging to the selected human claim root."""
    if claim_path.startswith("crossingReview.certificates["):
        refs = claim.get("evidenceRefs")
        topology = claim.get("topologyConstraint")
        if topology is not None:
            topology = _object(topology, "human-claim-invalid")
            topology_refs = topology.get("evidenceRefs")
            if type(topology_refs) is not list:
                raise PublicationAttestationRejected("human-claim-invalid")
            refs = refs + topology_refs if type(refs) is list else None
    elif claim_path.startswith("weekdayReview.blindClassifications["):
        refs = [claim.get("rationale")]
        base_path = claim_path + ".rationale"
        return (_validated_manifest_ref(refs[0], base_path),)
    else:
        refs = claim.get("evidenceRefs")

    if type(refs) is not list or not refs:
        raise PublicationAttestationRejected("human-claim-evidence-invalid")

    output: list[tuple[str, str, str, str]] = []
    if claim_path == "weekdayReview":
        evidence_base = "weekdayReview.evidenceRefs"
    else:
        evidence_base = claim_path + ".evidenceRefs"

    # A certificate may carry evidence on its topology constraint. Preserve
    # the packet resolver's order: direct certificate refs, then nested refs.
    direct_refs = claim.get("evidenceRefs")
    direct_len = len(direct_refs) if type(direct_refs) is list else 0
    for index, reference in enumerate(refs):
        path = f"{evidence_base}[{index}]"
        if claim_path.startswith("crossingReview.certificates[") and index >= direct_len:
            path = claim_path + f".topologyConstraint.evidenceRefs[{index - direct_len}]"
        output.append(_validated_manifest_ref(reference, path))
    return tuple(output)


def _validated_manifest_ref(value: object, path: str) -> tuple[str, str, str, str]:
    if type(value) is not dict or set(value) != {"artifactId", "sha256", "kind"}:
        raise PublicationAttestationRejected("human-claim-evidence-invalid")
    artifact_id = value.get("artifactId")
    digest = value.get("sha256")
    kind = value.get("kind")
    if (
        not isinstance(artifact_id, str)
        or not _canonical_uuid(artifact_id)
        or not isinstance(digest, str)
        or _RAW_SHA256.fullmatch(digest) is None
        or not isinstance(kind, str)
        or not kind
        or len(kind) > 40
    ):
        raise PublicationAttestationRejected("human-claim-evidence-invalid")
    return (path, artifact_id, digest, kind)


def _canonical_uuid(value: str) -> bool:
    try:
        return str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def human_claims_for_packet(packet: object) -> tuple[HumanPublicationClaim, ...]:
    """Return the exact human claim roots, canonical digests, actors, and refs.

    This helper is pure: it reads only the supplied JSON-compatible packet and
    does not consult authentication, database state, or publication status.
    The clue human projection omits ``challenger``; the weekday human
    projection omits ``blindClassifications`` and ``mechanicRoute`` because
    blind classifications have separate actor receipts and the mechanic
    route remains machine/route-owned. Machine-owned simulation evidence is
    never projected as a human claim.
    """
    root = _object(packet, "packet-invalid")
    claims: list[tuple[str, dict]] = []

    for field in ("sourceAttestations", "clueAdjudications"):
        items = root.get(field)
        if type(items) is not list or len(items) > 4096:
            raise PublicationAttestationRejected("human-claims-invalid")
        for index, item in enumerate(items):
            path = f"{field}[{index}]"
            claim = _object(item, "human-claim-invalid")
            if field == "clueAdjudications":
                claim = {key: value for key, value in claim.items() if key != "challenger"}
            claims.append((path, claim))

    crossing = _object(root.get("crossingReview"), "human-claims-invalid")
    certificates = crossing.get("certificates")
    if type(certificates) is not list or len(certificates) > 4096:
        raise PublicationAttestationRejected("human-claims-invalid")
    for index, item in enumerate(certificates):
        claims.append(
            (
                f"crossingReview.certificates[{index}]",
                _object(item, "human-claim-invalid"),
            )
        )

    weekday_full = _object(root.get("weekdayReview"), "human-claims-invalid")
    weekday = {
        key: value
        for key, value in weekday_full.items()
        if key not in {"blindClassifications", "mechanicRoute"}
    }
    claims.append(("weekdayReview", weekday))
    classifications = weekday_full.get("blindClassifications")
    if type(classifications) is not list or len(classifications) > 4096:
        raise PublicationAttestationRejected("human-claims-invalid")
    for index, item in enumerate(classifications):
        claims.append(
            (
                f"weekdayReview.blindClassifications[{index}]",
                _object(item, "human-claim-invalid"),
            )
        )

    if not claims:
        raise PublicationAttestationRejected("human-claims-invalid")
    output = []
    for claim_path, claim in claims:
        reviewer_id = claim.get("reviewerId")
        if (
            not isinstance(reviewer_id, str)
            or not reviewer_id
            or len(reviewer_id) > 128
            or reviewer_id != reviewer_id.strip()
        ):
            raise PublicationAttestationRejected("human-claim-reviewer-invalid")
        output.append(
            HumanPublicationClaim(
                claim_path=claim_path,
                claim_digest=_sha256(_canonical_json(claim)),
                reviewer_id=reviewer_id,
                evidence_refs=_human_refs(claim, claim_path),
            )
        )
    return tuple(output)


def _manifest(claim: HumanPublicationClaim) -> list[dict[str, str]]:
    return [
        {
            "claimPath": claim_path,
            "artifactId": artifact_id,
            "sha256": digest,
            "kind": kind,
        }
        for claim_path, artifact_id, digest, kind in claim.evidence_refs
    ]


def _receipt_from_row(row: PublicationClaimAttestation) -> _Receipt:
    if (
        row.protocol_version != PUBLICATION_ATTESTATION_PROTOCOL
        or not _canonical_uuid(row.attestation_id)
        or not isinstance(row.candidate_digest, str)
        or _PACKET_DIGEST.fullmatch(row.candidate_digest) is None
        or not isinstance(row.packet_digest, str)
        or _PACKET_DIGEST.fullmatch(row.packet_digest) is None
        or not isinstance(row.claim_digest, str)
        or _PACKET_DIGEST.fullmatch(row.claim_digest) is None
        or not isinstance(row.evidence_digest, str)
        or _PACKET_DIGEST.fullmatch(row.evidence_digest) is None
        or not isinstance(row.claim_path, str)
        or row.claim_path not in _RECEIPT_PATHS and _CLAIM_PATH.fullmatch(row.claim_path) is None
        or not isinstance(row.reviewer_id, str)
        or not row.reviewer_id
        or not isinstance(row.created_at, str)
    ):
        raise PublicationAttestationRejected("stored-attestation-invalid")
    try:
        created = datetime.fromisoformat(row.created_at)
    except ValueError:
        raise PublicationAttestationRejected("stored-attestation-invalid") from None
    if created.tzinfo is None:
        raise PublicationAttestationRejected("stored-attestation-invalid")
    return _Receipt(
        id=row.attestation_id,
        protocolVersion=row.protocol_version,
        candidateDigest=row.candidate_digest,
        packetDigest=row.packet_digest,
        claimPath=row.claim_path,
        claimDigest=row.claim_digest,
        evidenceDigest=row.evidence_digest,
        reviewerId=row.reviewer_id,
        createdAt=row.created_at,
    )


def _row_matches_claim(
    row: PublicationClaimAttestation,
    claim: HumanPublicationClaim,
    candidate_digest: str,
    packet_digest: str,
) -> _Receipt:
    expected_manifest_json = _canonical_json(_manifest(claim))
    expected_evidence_digest = _sha256(expected_manifest_json)
    if (
        row.candidate_digest != candidate_digest
        or row.packet_digest != packet_digest
        or row.claim_path != claim.claim_path
        or row.reviewer_id != claim.reviewer_id
        or row.claim_digest != claim.claim_digest
        or row.evidence_manifest_json != expected_manifest_json
        or row.evidence_digest != expected_evidence_digest
    ):
        raise PublicationAttestationRejected("stored-attestation-mismatch")
    return _receipt_from_row(row)


def resolve_publication_packet_attestations(
    packet: object, candidate_digest: str, validated_packet_digest: str
) -> PublicationAttestationCoverage:
    """Verify stored receipt coverage without changing any database state.

    Missing rows are reported as incomplete. A present row with a malformed
    receipt, wrong digest, wrong actor, or changed evidence manifest raises a
    closed validation error. Completeness only means every packet-declared
    human root has a matching local credential receipt; it does not verify the
    truth of those claims or make the packet eligible for publication.
    ``validated_packet_digest`` remains a consistency assertion for callers
    that already ran the gate. This resolver independently runs the shared
    TypeScript gate against the frozen candidate and packet before accepting
    it, so a future caller cannot bless an arbitrary declared digest merely by
    passing a matching string.
    """
    try:
        exact_digest, _ = _candidate_digest(candidate_digest)
        snapshot = _snapshot_packet(_object(packet, "packet-invalid"))
        if snapshot.get("candidateDigest") != exact_digest:
            raise PublicationAttestationRejected("candidate-binding-mismatch")
        packet_digest = _declared_packet_digest(snapshot)
        if (
            not isinstance(validated_packet_digest, str)
            or _PACKET_DIGEST.fullmatch(validated_packet_digest) is None
            or packet_digest != validated_packet_digest
        ):
            raise PublicationAttestationRejected("packet-digest-binding-mismatch")
        # Resolve the exact candidate and re-run the shared gate at this
        # boundary. The gate owns canonical packet hashing (including JS
        # number formatting), while this module owns receipt coverage.
        candidate_record = _validated_candidate(exact_digest)
        if candidate_record is None:
            raise PublicationAttestationRejected("candidate-not-found")
        from .future_puzzles import validate_personalized_v2_review_candidate

        candidate = validate_personalized_v2_review_candidate(
            candidate_record.manifest_json
        )
        evaluation = evaluate_puzzle_v2_publication_gate(candidate, snapshot)
        if (
            type(evaluation) is not dict
            or evaluation.get("candidateDigest") != exact_digest
            or evaluation.get("status") != "evidence-unverified"
            or type(evaluation.get("reasons")) is not list
            or len(evaluation["reasons"]) != 1
            or evaluation["reasons"][0].get("code")
            != "reviewer-evidence-unverified"
        ):
            raise PublicationAttestationRejected("packet-gate-invalid")

        # Re-run the established byte resolver so a complete result also means
        # the currently stored artifact bytes still match the sealed refs.
        resolved = resolve_publication_packet_evidence(snapshot, exact_digest)
        if type(resolved) is not tuple:
            raise PublicationAttestationRejected("evidence-resolution-invalid")
        claims = human_claims_for_packet(snapshot)
    except PublicationAttestationRejected:
        raise
    except (PublicationEvidenceRejected, Exception):
        raise PublicationAttestationRejected("packet-evidence-invalid") from None

    missing: list[str] = []
    found_count = 0
    for claim in claims:
        rows = (
            db.session.query(PublicationClaimAttestation)
            .filter_by(
                candidate_digest=exact_digest,
                packet_digest=packet_digest,
                claim_path=claim.claim_path,
                reviewer_id=claim.reviewer_id,
            )
            .limit(2)
            .all()
        )
        if not rows:
            missing.append(claim.claim_path)
            continue
        if len(rows) != 1:
            raise PublicationAttestationRejected("stored-attestation-conflict")
        _row_matches_claim(rows[0], claim, exact_digest, packet_digest)
        found_count += 1
    return PublicationAttestationCoverage(
        complete=not missing,
        expected_claim_count=len(claims),
        attested_claim_count=found_count,
        missing_claim_paths=tuple(missing),
    )


def _find_claim(claims: tuple[HumanPublicationClaim, ...], path: str) -> HumanPublicationClaim:
    for claim in claims:
        if claim.claim_path == path:
            return claim
    raise PublicationAttestationRejected("human-claim-path-invalid")


def _load_existing_receipt(
    claim: HumanPublicationClaim, candidate_digest: str, packet_digest: str
) -> PublicationClaimAttestation | None:
    rows = (
        db.session.query(PublicationClaimAttestation)
        .filter_by(
            candidate_digest=candidate_digest,
            packet_digest=packet_digest,
            claim_path=claim.claim_path,
            reviewer_id=claim.reviewer_id,
        )
        .limit(2)
        .all()
    )
    if len(rows) > 1:
        raise PublicationAttestationRejected("stored-attestation-conflict")
    return rows[0] if rows else None


def _same_existing_receipt(
    row: PublicationClaimAttestation,
    claim: HumanPublicationClaim,
    candidate_digest: str,
    packet_digest: str,
) -> _Receipt | None:
    # A valid-but-different attestation is the natural-key conflict described
    # by the API contract. Corrupt storage instead fails closed as unavailable.
    try:
        receipt = _receipt_from_row(row)
    except PublicationAttestationRejected:
        raise
    if (
        row.candidate_digest != candidate_digest
        or row.packet_digest != packet_digest
        or row.claim_path != claim.claim_path
        or row.reviewer_id != claim.reviewer_id
    ):
        raise PublicationAttestationRejected("stored-attestation-key-invalid")
    manifest_json = _canonical_json(_manifest(claim))
    evidence_digest = _sha256(manifest_json)
    if (
        row.claim_digest == claim.claim_digest
        and row.evidence_digest == evidence_digest
        and row.evidence_manifest_json == manifest_json
    ):
        return receipt
    return None


def attest_publication_claim(
    packet: object, claim_path: str, principal: ReviewerPrincipal
) -> tuple[_Receipt, bool]:
    """Record one configured principal's append-only attestation receipt.

    Returns ``(receipt, created)``. Repeating the same sealed claim is
    idempotent and returns the original receipt. A changed claim or evidence
    manifest under the same natural key is a conflict.
    """
    try:
        exact_packet = _snapshot_packet(_object(packet, "packet-invalid"))
    except PublicationReviewRejected as error:
        raise PublicationAttestationRejected("packet-invalid") from error
    try:
        candidate_digest, _ = _candidate_digest(exact_packet.get("candidateDigest"))
    except PublicationEvidenceRejected:
        raise PublicationAttestationRejected("candidate-digest-invalid") from None
    packet_digest = _declared_packet_digest(exact_packet)

    if (
        not isinstance(claim_path, str)
        or claim_path not in _RECEIPT_PATHS and _CLAIM_PATH.fullmatch(claim_path) is None
    ):
        raise PublicationAttestationRejected("human-claim-path-invalid")

    try:
        diagnostic = review_publication_packet(exact_packet)
    except PublicationReviewRejected as error:
        if str(error) == "attestation-resolution-failed":
            # A same-key receipt with changed stored claim/evidence content is
            # an idempotency conflict, not a malformed incoming review packet.
            raise PublicationAttestationRejected("attestation-conflict") from None
        raise PublicationAttestationRejected("packet-review-invalid") from None
    diagnostic_reasons = (
        diagnostic.reason_codes
        if type(diagnostic) is PublicationReviewDiagnostic
        else ()
    )
    if (
        type(diagnostic) is not PublicationReviewDiagnostic
        or diagnostic.status != "evidence-unverified"
        or diagnostic.gate_candidate_digest != candidate_digest
        or diagnostic.packet_digest != packet_digest
        or type(diagnostic_reasons) is not tuple
        or any(not isinstance(code, str) for code in diagnostic_reasons)
        or "reviewer-evidence-unverified" not in diagnostic_reasons
        or len(diagnostic_reasons) != len(set(diagnostic_reasons))
        or not set(diagnostic_reasons).issubset(
            {"reviewer-evidence-unverified", "human-attestation-incomplete"}
        )
    ):
        raise PublicationAttestationRejected("packet-review-incomplete")

    try:
        candidate = _validated_candidate(candidate_digest)
        if candidate is None:
            raise PublicationAttestationRejected("candidate-not-found")
        resolved = resolve_publication_packet_evidence(exact_packet, candidate_digest)
        if type(resolved) is not tuple:
            raise PublicationAttestationRejected("evidence-resolution-invalid")
    except PublicationAttestationRejected:
        raise
    except Exception:
        raise PublicationAttestationRejected("packet-evidence-invalid") from None

    claims = human_claims_for_packet(exact_packet)
    claim = _find_claim(claims, claim_path)
    if type(principal) is not ReviewerPrincipal:
        raise PublicationAttestationRejected("authenticated-reviewer-invalid")
    reviewer_id = principal.reviewer_id
    if claim.reviewer_id != reviewer_id:
        raise PublicationAttestationRejected("authenticated-reviewer-mismatch")

    manifest_json = _canonical_json(_manifest(claim))
    evidence_digest = _sha256(manifest_json)
    existing = _load_existing_receipt(claim, candidate_digest, packet_digest)
    if existing is not None:
        receipt = _same_existing_receipt(
            existing, claim, candidate_digest, packet_digest
        )
        if receipt is not None:
            return receipt, False
        raise PublicationAttestationRejected("attestation-conflict")

    row = PublicationClaimAttestation(
        attestation_id=str(uuid4()),
        protocol_version=PUBLICATION_ATTESTATION_PROTOCOL,
        candidate_digest=candidate_digest,
        packet_digest=packet_digest,
        claim_path=claim.claim_path,
        claim_digest=claim.claim_digest,
        evidence_digest=evidence_digest,
        evidence_manifest_json=manifest_json,
        reviewer_id=reviewer_id,
        created_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    )

    # Clear read-side work before writing, including under SQLite's deferred
    # transaction mode. The composite unique key arbitrates concurrent retries.
    db.session.rollback()
    try:
        db.session.add(row)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        try:
            raced = _load_existing_receipt(claim, candidate_digest, packet_digest)
        except SQLAlchemyError:
            db.session.rollback()
            raise PublicationAttestationRejected("attestation-storage-unavailable") from None
        if raced is None:
            raise PublicationAttestationRejected("attestation-storage-unavailable") from None
        receipt = _same_existing_receipt(raced, claim, candidate_digest, packet_digest)
        if receipt is not None:
            return receipt, False
        raise PublicationAttestationRejected("attestation-conflict")
    except SQLAlchemyError:
        db.session.rollback()
        raise PublicationAttestationRejected("attestation-storage-unavailable") from None
    return _receipt_from_row(row), True


def _response(payload: dict, status: int):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _principal() -> ReviewerPrincipal:
    principal = resolve_reviewer_principal(
        current_app.config, request.headers.get("Authorization")
    )
    return principal


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("duplicate JSON key")
        output[key] = value
    return output


def _reject_non_json_constant(_value: str):
    raise ValueError("non-JSON numeric constant")


@publication_attestation_api.post("/api/future/evidence/v2/attestations")
def attest_publication_claim_route():
    """Attest one sealed human claim using only the configured Bearer actor."""
    try:
        principal = _principal()
    except ReviewerAuthConfigError:
        return _response({"error": "Reviewer authentication is unavailable"}, 503)
    except ReviewerAuthenticationError:
        response = _response({"error": "Reviewer authentication required"}, 401)
        response.headers["WWW-Authenticate"] = "Bearer"
        return response

    if request.mimetype != "application/json":
        return _response({"error": "A JSON request body is required"}, 415)
    content_length = request.content_length
    if content_length is None:
        return _response({"error": "Content-Length is required"}, 411)
    if content_length > MAX_PUBLICATION_REVIEW_PACKET_BYTES + _MAX_REQUEST_OVERHEAD:
        return _response({"error": "Attestation request exceeds the size limit"}, 413)
    try:
        max_request_bytes = MAX_PUBLICATION_REVIEW_PACKET_BYTES + _MAX_REQUEST_OVERHEAD
        raw_body = request.stream.read(max_request_bytes + 1)
        if len(raw_body) > max_request_bytes:
            return _response({"error": "Attestation request exceeds the size limit"}, 413)
        if len(raw_body) != content_length:
            return _response({"error": "Request body length is invalid"}, 400)
        body = json.loads(
            raw_body,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except (ValueError, UnicodeError, RecursionError):
        return _response({"error": "Invalid JSON request body"}, 400)
    if type(body) is not dict or set(body) != {"packet", "claimPath"}:
        return _response({"error": "Request must contain packet and claimPath"}, 400)

    try:
        receipt, created = attest_publication_claim(
            body["packet"], body["claimPath"], principal
        )
    except PublicationAttestationRejected as error:
        code = str(error)
        if code == "attestation-conflict":
            return _response({"error": "A different attestation exists for this claim"}, 409)
        if code in {"packet-review-incomplete", "packet-review-invalid"}:
            return _response({"error": "Packet has not passed the required review gate"}, 422)
        if code == "authenticated-reviewer-mismatch":
            return _response({"error": "Authenticated reviewer does not match this claim"}, 403)
        if code in {"attestation-storage-unavailable"}:
            return _response({"error": "Attestation storage is unavailable"}, 503)
        if code.startswith("stored-"):
            return _response({"error": "Stored attestation failed integrity checks"}, 503)
        return _response({"error": "Packet or human claim failed validation"}, 400)
    except (PublicationEvidenceRejected, SQLAlchemyError):
        db.session.rollback()
        return _response({"error": "Packet evidence could not be verified"}, 503)

    return _response(
        {"attestation": receipt.to_dict()},
        201 if created else 200,
    )
