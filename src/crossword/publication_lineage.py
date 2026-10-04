"""Fail-closed public-copy assessment contract.

This module is intentionally diagnostic only. It does not create a public
PuzzleDocumentV2, an audit receipt, or a publication authorization. Until the
trusted human and machine evidence paths exist, even a structurally complete
review packet can yield no result beyond ``evidence-unverified``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import hmac
import json
import re
from typing import Literal
from uuid import UUID

from .publication_review import (
    PublicationReviewDiagnostic,
    PublicationReviewRejected,
    review_publication_packet,
)


_CANDIDATE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_PACKET_KEYS = frozenset(
    {
        "schema",
        "reviewId",
        "candidateDigest",
        "createdAt",
        "sourceAttestations",
        "clueAdjudications",
        "crossingReview",
        "weekdayReview",
        "packetDigest",
    }
)

# Future audit records have a deliberately narrow shape. These constants only
# constrain serialization and cross-field consistency; they are not trust,
# authorization, eligibility, or publication policy.
PUBLICATION_LINEAGE_AUDIT_SCHEMA_V1 = "publication-lineage-audit-shape-v1"
MAX_PUBLICATION_LINEAGE_AUDIT_BYTES = 2 * 1024 * 1024
MAX_PUBLICATION_LINEAGE_RECEIPTS = 4096
MAX_PUBLICATION_LINEAGE_ARTIFACTS = 4096
# Every artifact can be bound to at most one reviewer receipt, so any valid
# receipt manifest needs no more references than the artifact budget.
MAX_PUBLICATION_LINEAGE_ARTIFACT_REFERENCES = MAX_PUBLICATION_LINEAGE_ARTIFACTS
_AUDIT_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_AUDIT_IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_AUDIT_GATE_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$")
_AUDIT_ARTIFACT_KINDS = frozenset(
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
_AUDIT_HUMAN_CLAIM_PATH = re.compile(
    r"^(?:sourceAttestations|clueAdjudications|"
    r"crossingReview\.certificates|weekdayReview\.blindClassifications)"
    r"\[(0|[1-9][0-9]{0,3})\]$|^weekdayReview$"
)
_AUDIT_PACKET_EVIDENCE_PATHS = (
    re.compile(
        r"^sourceAttestations\[(?:0|[1-9][0-9]{0,3})\]\.evidenceRefs"
        r"\[(?:0|[1-9][0-9]{0,3})\]$"
    ),
    re.compile(
        r"^clueAdjudications\[(?:0|[1-9][0-9]{0,3})\]\.evidenceRefs"
        r"\[(?:0|[1-9][0-9]{0,3})\]$"
    ),
    re.compile(
        r"^clueAdjudications\[(?:0|[1-9][0-9]{0,3})\]\.challenger"
        r"\.evidenceRefs\[(?:0|[1-9][0-9]{0,3})\]$"
    ),
    re.compile(
        r"^crossingReview\.certificates\[(?:0|[1-9][0-9]{0,3})\]"
        r"\.evidenceRefs\[(?:0|[1-9][0-9]{0,3})\]$"
    ),
    re.compile(
        r"^crossingReview\.certificates\[(?:0|[1-9][0-9]{0,3})\]"
        r"\.topologyConstraint\.evidenceRefs\[(?:0|[1-9][0-9]{0,3})\]$"
    ),
    re.compile(
        r"^crossingReview\.simulation\.evidenceRefs"
        r"\[(?:0|[1-9][0-9]{0,3})\]$"
    ),
    re.compile(r"^weekdayReview\.evidenceRefs\[(?:0|[1-9][0-9]{0,3})\]$"),
    re.compile(
        r"^weekdayReview\.blindClassifications\[(?:0|[1-9][0-9]{0,3})\]"
        r"\.rationale$"
    ),
    re.compile(
        r"^weekdayReview\.mechanicRoute\.evidenceRefs"
        r"\[(?:0|[1-9][0-9]{0,3})\]$"
    ),
)


class PublicationLineageAuditShapeRejected(ValueError):
    """A proposed future lineage audit value is outside its bounded shape."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


_AUDIT_TOP_LEVEL_KEYS = frozenset(
    {
        "schema",
        "sourceCandidateDigest",
        "reviewPacketDigest",
        "reviewPacketCandidateDigest",
        "sanitizedDocumentDigest",
        "claimedGateVerifier",
        "claimedReviewerReceipts",
        "claimedEvidenceArtifacts",
        "claimedPublisher",
        "auditDigest",
    }
)
_AUDIT_GATE_KEYS = frozenset({"gateVersion", "verifierId"})
_AUDIT_RECEIPT_KEYS = frozenset(
    {
        "receiptId",
        "reviewerId",
        "claimPath",
        "claimDigest",
        "candidateDigest",
        "packetDigest",
        "evidenceManifestDigest",
        "recordedAt",
        "evidenceArtifactIds",
    }
)
_AUDIT_ARTIFACT_KEYS = frozenset(
    {
        "artifactId",
        "sha256",
        "kind",
        "candidateDigest",
        "packetDigest",
        "claimPath",
        "uploaderId",
        "reviewerClaimReceiptId",
    }
)
_AUDIT_PUBLISHER_KEYS = frozenset({"principalId", "authenticatedAt"})


def validate_publication_lineage_audit_shape_v1(value: object) -> None:
    """Validate the proposed immutable lineage record's exact bounded shape.

    This checks only JSON shape, cross-field digest/identity consistency, and a
    self-contained evidence-manifest hash. The value and every identity/time
    remain untrusted claims: this function does not prove authorship, truth,
    authorization, eligibility, or publication. It creates no record and
    returns no success-shaped value; malformed input raises a coded error.
    """
    root = _audit_object(value, "audit-object-invalid")
    if set(root) != _AUDIT_TOP_LEVEL_KEYS:
        _audit_reject("audit-keys-invalid")
    if root["schema"] != PUBLICATION_LINEAGE_AUDIT_SCHEMA_V1:
        _audit_reject("audit-schema-invalid")

    candidate_digest = _audit_digest(root["sourceCandidateDigest"])
    packet_digest = _audit_digest(root["reviewPacketDigest"])
    packet_candidate_digest = _audit_digest(root["reviewPacketCandidateDigest"])
    _audit_digest(root["sanitizedDocumentDigest"])
    _audit_digest(root["auditDigest"])
    if packet_candidate_digest != candidate_digest:
        _audit_reject("packet-candidate-misbinding")

    gate = _audit_object(root["claimedGateVerifier"], "gate-verifier-invalid")
    if set(gate) != _AUDIT_GATE_KEYS:
        _audit_reject("gate-verifier-keys-invalid")
    if (
        _audit_string(gate["gateVersion"], _AUDIT_GATE_VERSION) is None
        or _audit_string(gate["verifierId"], _AUDIT_IDENTITY) is None
    ):
        _audit_reject("gate-verifier-invalid")

    receipts = _audit_array(
        root["claimedReviewerReceipts"],
        maximum=MAX_PUBLICATION_LINEAGE_RECEIPTS,
        minimum=1,
        reason="reviewer-receipts-invalid",
    )
    artifacts = _audit_array(
        root["claimedEvidenceArtifacts"],
        maximum=MAX_PUBLICATION_LINEAGE_ARTIFACTS,
        minimum=1,
        reason="evidence-artifacts-invalid",
    )

    receipt_ids: set[str] = set()
    reviewer_claims: set[tuple[str, str]] = set()
    receipts_by_id: dict[str, dict[str, object]] = {}
    receipt_artifact_ids: dict[str, tuple[str, ...]] = {}
    artifact_reference_count = 0
    for receipt_value in receipts:
        receipt = _audit_object(receipt_value, "reviewer-receipt-invalid")
        if set(receipt) != _AUDIT_RECEIPT_KEYS:
            _audit_reject("reviewer-receipt-keys-invalid")
        receipt_id = _audit_uuid(receipt["receiptId"], "receipt-id-invalid")
        reviewer_id = _audit_identity(receipt["reviewerId"], "reviewer-id-invalid")
        claim_path = _audit_string(receipt["claimPath"], _AUDIT_HUMAN_CLAIM_PATH)
        if claim_path is None:
            _audit_reject("reviewer-claim-path-invalid")
        _audit_digest(receipt["claimDigest"])
        if (
            _audit_digest(receipt["candidateDigest"]) != candidate_digest
            or _audit_digest(receipt["packetDigest"]) != packet_digest
        ):
            _audit_reject("reviewer-receipt-misbinding")
        _audit_digest(receipt["evidenceManifestDigest"])
        _audit_timestamp(receipt["recordedAt"], "reviewer-receipt-time-invalid")
        artifact_ids = _audit_array(
            receipt["evidenceArtifactIds"],
            maximum=MAX_PUBLICATION_LINEAGE_ARTIFACTS,
            minimum=1,
            reason="reviewer-receipt-artifacts-invalid",
        )
        artifact_reference_count += len(artifact_ids)
        if artifact_reference_count > MAX_PUBLICATION_LINEAGE_ARTIFACT_REFERENCES:
            _audit_reject("reviewer-receipt-reference-limit-exceeded")
        normalized_artifact_ids = tuple(
            _audit_uuid(item, "reviewer-receipt-artifact-id-invalid")
            for item in artifact_ids
        )
        if len(set(normalized_artifact_ids)) != len(normalized_artifact_ids):
            _audit_reject("duplicate-reviewer-receipt-artifact")
        if receipt_id in receipt_ids:
            _audit_reject("duplicate-reviewer-receipt-id")
        if (reviewer_id, claim_path) in reviewer_claims:
            _audit_reject("duplicate-reviewer-claim")
        receipt_ids.add(receipt_id)
        reviewer_claims.add((reviewer_id, claim_path))
        receipts_by_id[receipt_id] = receipt
        receipt_artifact_ids[receipt_id] = normalized_artifact_ids

    artifacts_by_id: dict[str, dict[str, object]] = {}
    attached_artifacts: dict[str, set[str]] = {
        receipt_id: set() for receipt_id in receipt_ids
    }
    for artifact_value in artifacts:
        artifact = _audit_object(artifact_value, "evidence-artifact-invalid")
        if set(artifact) != _AUDIT_ARTIFACT_KEYS:
            _audit_reject("evidence-artifact-keys-invalid")
        artifact_id = _audit_uuid(artifact["artifactId"], "artifact-id-invalid")
        if artifact_id in artifacts_by_id:
            _audit_reject("duplicate-evidence-artifact-id")
        raw_digest = artifact["sha256"]
        if (
            type(raw_digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", raw_digest) is None
        ):
            _audit_reject("evidence-artifact-digest-invalid")
        kind = artifact["kind"]
        if type(kind) is not str or kind not in _AUDIT_ARTIFACT_KINDS:
            _audit_reject("evidence-artifact-kind-invalid")
        if (
            _audit_digest(artifact["candidateDigest"]) != candidate_digest
            or _audit_digest(artifact["packetDigest"]) != packet_digest
        ):
            _audit_reject("evidence-artifact-misbinding")
        claim_path = _audit_string(artifact["claimPath"], _AUDIT_PACKET_EVIDENCE_PATHS)
        if claim_path is None:
            _audit_reject("evidence-artifact-claim-path-invalid")
        _audit_identity(artifact["uploaderId"], "evidence-uploader-invalid")
        receipt_ref = artifact["reviewerClaimReceiptId"]
        if receipt_ref is not None:
            receipt_id = _audit_uuid(receipt_ref, "artifact-receipt-id-invalid")
            if receipt_id not in receipts_by_id:
                _audit_reject("evidence-artifact-receipt-unresolved")
            attached_artifacts[receipt_id].add(artifact_id)
        artifacts_by_id[artifact_id] = artifact

    for receipt_id, receipt in receipts_by_id.items():
        ordered_ids = receipt_artifact_ids[receipt_id]
        if set(ordered_ids) != attached_artifacts[receipt_id]:
            _audit_reject("reviewer-receipt-artifact-binding-invalid")
        manifest = []
        for artifact_id in ordered_ids:
            artifact = artifacts_by_id.get(artifact_id)
            if artifact is None or artifact["reviewerClaimReceiptId"] != receipt_id:
                _audit_reject("reviewer-receipt-artifact-binding-invalid")
            if artifact["uploaderId"] != receipt["reviewerId"]:
                _audit_reject("reviewer-evidence-uploader-misbinding")
            if not _audit_evidence_belongs_to_claim(
                artifact["claimPath"], receipt["claimPath"]
            ):
                _audit_reject("reviewer-evidence-claim-misbinding")
            manifest.append(
                {
                    "claimPath": artifact["claimPath"],
                    "artifactId": artifact_id,
                    "sha256": artifact["sha256"],
                    "kind": artifact["kind"],
                }
            )
        if _audit_canonical_digest(manifest) != receipt["evidenceManifestDigest"]:
            _audit_reject("reviewer-evidence-manifest-misbinding")

    publisher = _audit_object(root["claimedPublisher"], "publisher-invalid")
    if set(publisher) != _AUDIT_PUBLISHER_KEYS:
        _audit_reject("publisher-keys-invalid")
    _audit_identity(publisher["principalId"], "publisher-identity-invalid")
    _audit_timestamp(publisher["authenticatedAt"], "publisher-time-invalid")

    # This fixed-depth, fixed-key projection contains only validated bounded
    # JSON values. Enforce the serialized cap after semantic limits are checked.
    try:
        canonical = json.dumps(
            root,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError):
        _audit_reject("audit-json-invalid")
    if len(canonical) > MAX_PUBLICATION_LINEAGE_AUDIT_BYTES:
        _audit_reject("audit-size-exceeded")


def verify_publication_lineage_audit_digest_self_consistency_v1(
    value: object,
) -> bool:
    """Return whether a bounded value's audit digest matches its own contents.

    ``True`` means only that canonical SHA-256 recomputation is self-consistent
    after shape validation. An untrusted party can create such a value, so this
    is not a signature, proof of authorship or time, verified evidence, an
    authorization token, an eligibility result, or a publication decision.
    The verifier neither writes nor constructs an audit record.
    """
    try:
        validate_publication_lineage_audit_shape_v1(value)
    except PublicationLineageAuditShapeRejected:
        return False
    unsigned = {key: item for key, item in value.items() if key != "auditDigest"}
    expected = _audit_canonical_digest(unsigned)
    return hmac.compare_digest(value["auditDigest"], expected)


def _audit_reject(code: str) -> None:
    raise PublicationLineageAuditShapeRejected(code)


def _audit_object(value: object, reason: str) -> dict:
    if type(value) is not dict:
        _audit_reject(reason)
    return value


def _audit_array(value: object, *, maximum: int, minimum: int, reason: str) -> list:
    if type(value) is not list or not minimum <= len(value) <= maximum:
        _audit_reject(reason)
    return value


def _audit_string(
    value: object, pattern: re.Pattern[str] | tuple[re.Pattern[str], ...]
) -> str | None:
    patterns = pattern if isinstance(pattern, tuple) else (pattern,)
    if type(value) is str and any(item.fullmatch(value) for item in patterns):
        return value
    return None


def _audit_digest(value: object) -> str:
    if type(value) is not str or _AUDIT_DIGEST.fullmatch(value) is None:
        _audit_reject("digest-invalid")
    return value


def _audit_identity(value: object, reason: str) -> str:
    identity = _audit_string(value, _AUDIT_IDENTITY)
    if identity is None:
        _audit_reject(reason)
    return identity


def _audit_uuid(value: object, reason: str) -> str:
    if type(value) is not str or len(value) != 36:
        _audit_reject(reason)
    try:
        if str(UUID(value)) != value:
            _audit_reject(reason)
    except (ValueError, AttributeError):
        _audit_reject(reason)
    return value


def _audit_timestamp(value: object, reason: str) -> str:
    if (
        type(value) is not str
        or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)",
            value,
        )
        is None
    ):
        _audit_reject(reason)
    try:
        parsed = datetime.fromisoformat(
            value.removesuffix("Z") + ("+00:00" if value.endswith("Z") else "")
        )
    except ValueError:
        _audit_reject(reason)
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        _audit_reject(reason)
    return value


def _audit_canonical_digest(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _audit_evidence_belongs_to_claim(evidence_path: object, claim_path: object) -> bool:
    if type(evidence_path) is not str or type(claim_path) is not str:
        return False
    if claim_path.startswith("crossingReview.certificates["):
        return evidence_path.startswith(
            claim_path + ".evidenceRefs["
        ) or evidence_path.startswith(claim_path + ".topologyConstraint.evidenceRefs[")
    if claim_path.startswith("weekdayReview.blindClassifications["):
        return evidence_path == claim_path + ".rationale"
    if claim_path == "weekdayReview":
        return evidence_path.startswith("weekdayReview.evidenceRefs[")
    return evidence_path.startswith(claim_path + ".evidenceRefs[")


@dataclass(frozen=True, slots=True)
class PublicationResealAssessmentV1:
    """Redacted unresolved assessment; never a document, receipt, or authority."""

    status: Literal["blocked", "evidence-unverified"]
    candidate_digest: str | None
    packet_digest: str | None
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return only the bounded unresolved diagnostic fields."""
        return asdict(self)


def assess_public_document_reseal(
    candidate_digest: object,
    packet: object,
) -> PublicationResealAssessmentV1:
    """Assess whether a public-copy reseal could proceed, without resealing.

    The existing review service owns the single bounded JSON snapshot used by
    the shared structural gate, immutable evidence resolver, and attestation
    resolver. This wrapper enforces the intended candidate binding and packet
    envelope before delegating, then accepts only that service's redacted
    unresolved diagnostic. It never constructs or returns a public document.
    """
    if type(candidate_digest) is not str or not _CANDIDATE_DIGEST.fullmatch(
        candidate_digest
    ):
        return _blocked("candidate-digest-invalid")
    if type(packet) is not dict:
        return _blocked("packet-invalid")
    if set(packet) != _PACKET_KEYS:
        # This also rejects client-supplied verdicts, document/audit digests,
        # authorization, or eligibility claims before they can be interpreted.
        return _blocked("packet-shape-invalid")
    if packet.get("candidateDigest") != candidate_digest:
        return _blocked("candidate-digest-mismatch")

    try:
        diagnostic = review_publication_packet(packet)
    except PublicationReviewRejected as error:
        code = str(error)
        if not re.fullmatch(r"[a-z0-9-]{1,80}", code):
            code = "publication-review-rejected"
        return _blocked(code)
    except Exception:
        # Keep analyzer, DB, resolver, and unexpected exception details private.
        return _blocked("publication-review-unavailable")

    if (
        type(diagnostic) is not PublicationReviewDiagnostic
        or diagnostic.status not in {"blocked", "evidence-unverified"}
        or diagnostic.gate_candidate_digest != candidate_digest
        or type(diagnostic.reason_codes) is not tuple
        or not diagnostic.reason_codes
        or any(
            not isinstance(code, str) or not re.fullmatch(r"[a-z0-9-]{1,80}", code)
            for code in diagnostic.reason_codes
        )
        or (
            diagnostic.packet_digest is not None
            and (
                not isinstance(diagnostic.packet_digest, str)
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", diagnostic.packet_digest)
            )
        )
    ):
        return _blocked("publication-review-output-invalid")

    reasons = tuple(diagnostic.reason_codes)
    if diagnostic.status == "evidence-unverified":
        reasons += ("public-reseal-not-performed",)
    return PublicationResealAssessmentV1(
        status=diagnostic.status,
        candidate_digest=candidate_digest,
        # The review service returns this only after verifying the packet's
        # immutable digest and resolving it against the exact stored candidate.
        packet_digest=diagnostic.packet_digest,
        reason_codes=reasons,
    )


def _blocked(reason_code: str) -> PublicationResealAssessmentV1:
    return PublicationResealAssessmentV1(
        status="blocked",
        candidate_digest=None,
        packet_digest=None,
        reason_codes=(reason_code,),
    )
