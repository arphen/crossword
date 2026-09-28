"""Synthetic-only tests for the unresolved public-reseal assessment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from tests.test_api_isolated import api, no_network  # noqa: F401
from tests.test_publication_evidence import _review_packet, _store_rows
from src.crossword.future_puzzles import FuturePuzzleV2CandidateRecord
from src.crossword.publication_review import PublicationReviewDiagnostic
from src.crossword.publication_lineage import (
    MAX_PUBLICATION_LINEAGE_ARTIFACT_REFERENCES,
    MAX_PUBLICATION_LINEAGE_ARTIFACTS,
    MAX_PUBLICATION_LINEAGE_AUDIT_BYTES,
    MAX_PUBLICATION_LINEAGE_RECEIPTS,
    PublicationLineageAuditShapeRejected,
    assess_public_document_reseal,
    validate_publication_lineage_audit_shape_v1,
    verify_publication_lineage_audit_digest_self_consistency_v1,
)
from src.crossword.publication_attestation import PublicationClaimAttestation
from src.crossword.publication_evidence import (
    PublicationEvidenceArtifact,
    PublicationEvidenceArtifactClaim,
)
from src.crossword.v2_session_journal import FuturePuzzleV2PublishedRecord


@pytest.fixture
def reseal_case(api):
    manifest = json.loads(
        (Path(__file__).parent / "fixtures/personalized-review-v2.json").read_text(
            encoding="utf-8"
        )
    )
    digest = manifest["integrity"]["value"]
    with api.app.app_context():
        api.db.session.add(
            FuturePuzzleV2CandidateRecord(
                profile_id=str(uuid4()),
                candidate_hash=digest.removeprefix("sha256:"),
                candidate_id=manifest["id"],
                job_id=str(uuid4()),
                manifest_json=manifest,
                created_at="2026-09-26T12:00:00.000+00:00",
            )
        )
        api.db.session.commit()
    packet, rows, _refs = _review_packet(digest)
    unsigned = {key: value for key, value in packet.items() if key != "packetDigest"}
    encoded = json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    packet["packetDigest"] = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
    return digest, manifest, packet, rows


def _enable_synthetic_residual_gate(monkeypatch):
    import src.crossword.publication_review as review_module

    def synthetic_unresolved_gate(candidate, _packet):
        return {
            "gateVersion": "puzzle-v2-publication-gate-v1",
            "candidateDigest": candidate["integrity"]["value"],
            "status": "evidence-unverified",
            "reasons": [
                {
                    "code": "reviewer-evidence-unverified",
                    "path": "publicationReview",
                    "message": "Synthetic CI input remains semantically unverified.",
                }
            ],
        }

    monkeypatch.setattr(
        review_module, "evaluate_puzzle_v2_publication_gate", synthetic_unresolved_gate
    )


def _assessment(api, digest, packet):
    with api.app.app_context():
        return assess_public_document_reseal(digest, packet)


def test_valid_looking_synthetic_packet_stays_unresolved_without_publication(
    api, reseal_case, monkeypatch
):
    digest, original_manifest, packet, rows = reseal_case
    _store_rows(api, rows)
    _enable_synthetic_residual_gate(monkeypatch)

    before_manifest = json.loads(json.dumps(original_manifest))
    assessment = _assessment(api, digest, packet)
    result = assessment.to_dict()

    assert assessment.status == "evidence-unverified"
    assert assessment.candidate_digest == digest
    assert assessment.packet_digest == packet["packetDigest"]
    assert "public-reseal-not-performed" in assessment.reason_codes
    assert set(result) == {
        "status",
        "candidate_digest",
        "packet_digest",
        "reason_codes",
    }
    assert result["status"] in {"blocked", "evidence-unverified"}
    assert not (
        {
            "publicDocument",
            "document",
            "auditReceipt",
            "authorization",
            "eligible",
            "pass",
        }
        & set(result)
    )

    with api.app.app_context():
        candidate = api.db.session.query(FuturePuzzleV2CandidateRecord).one()
        assert candidate.manifest_json == before_manifest
        assert api.db.session.query(FuturePuzzleV2PublishedRecord).count() == 0


def test_real_shared_gate_keeps_synthetic_fixture_unresolved_and_read_only(
    api, reseal_case
):
    digest, original_manifest, packet, rows = reseal_case
    _store_rows(api, rows)

    def storage_snapshot():
        artifacts = api.db.session.query(PublicationEvidenceArtifact).order_by(
            PublicationEvidenceArtifact.artifact_id
        )
        claims = api.db.session.query(PublicationEvidenceArtifactClaim).order_by(
            PublicationEvidenceArtifactClaim.artifact_id
        )
        attestations = api.db.session.query(PublicationClaimAttestation).order_by(
            PublicationClaimAttestation.attestation_id
        )
        return {
            "artifacts": [
                (
                    row.artifact_id,
                    row.sha256,
                    row.kind,
                    row.candidate_digest,
                    row.media_type,
                    row.reviewer_id,
                    row.recorded_at,
                    bytes(row.artifact_bytes),
                )
                for row in artifacts
            ],
            "artifact_claims": [(row.artifact_id, row.claim_path) for row in claims],
            "attestations": [
                (
                    row.attestation_id,
                    row.protocol_version,
                    row.candidate_digest,
                    row.packet_digest,
                    row.claim_path,
                    row.claim_digest,
                    row.evidence_digest,
                    row.evidence_manifest_json,
                    row.reviewer_id,
                    row.created_at,
                )
                for row in attestations
            ],
        }

    with api.app.app_context():
        candidate_row = api.db.session.query(FuturePuzzleV2CandidateRecord).one()
        before_candidate_identity = (
            candidate_row.profile_id,
            candidate_row.candidate_hash,
            candidate_row.candidate_id,
            candidate_row.job_id,
            candidate_row.created_at,
        )
        before_candidate = json.loads(json.dumps(candidate_row.manifest_json))
        before_storage = storage_snapshot()
        before_counts = {
            "published": api.db.session.query(FuturePuzzleV2PublishedRecord).count(),
            "artifacts": len(before_storage["artifacts"]),
            "artifact_claims": len(before_storage["artifact_claims"]),
            "attestations": len(before_storage["attestations"]),
        }

    # No gate patch: this exercises the actual shared TypeScript structural gate.
    assessment = _assessment(api, digest, packet)
    result = assessment.to_dict()

    assert assessment.status in {"blocked", "evidence-unverified"}
    assert assessment.status == "blocked"
    assert "candidate-has-synthetic-source" in assessment.reason_codes
    assert assessment.candidate_digest == digest
    assert set(result) == {
        "status",
        "candidate_digest",
        "packet_digest",
        "reason_codes",
    }
    assert not (
        {
            "publicDocument",
            "document",
            "auditReceipt",
            "authorization",
            "eligible",
            "pass",
        }
        & set(result)
    )
    with api.app.app_context():
        after_candidate = api.db.session.query(FuturePuzzleV2CandidateRecord).one()
        after_candidate_identity = (
            after_candidate.profile_id,
            after_candidate.candidate_hash,
            after_candidate.candidate_id,
            after_candidate.job_id,
            after_candidate.created_at,
        )
        after_counts = {
            "published": api.db.session.query(FuturePuzzleV2PublishedRecord).count(),
            "artifacts": api.db.session.query(PublicationEvidenceArtifact).count(),
            "artifact_claims": api.db.session.query(
                PublicationEvidenceArtifactClaim
            ).count(),
            "attestations": api.db.session.query(PublicationClaimAttestation).count(),
        }
        after_storage = storage_snapshot()
        assert after_candidate_identity == before_candidate_identity
        assert after_candidate.manifest_json == before_candidate == original_manifest
        assert after_counts == before_counts
        assert after_storage == before_storage


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        ("candidate-mismatch", "candidate-digest-mismatch"),
        ("client-verdict", "packet-shape-invalid"),
        ("client-document-digest", "packet-shape-invalid"),
        ("client-authorization", "packet-shape-invalid"),
    ],
)
def test_candidate_mismatch_and_success_shaped_claims_block_before_review(
    api, reseal_case, monkeypatch, mutation, expected_reason
):
    digest, _manifest, packet, _rows = reseal_case
    packet = json.loads(json.dumps(packet))
    if mutation == "candidate-mismatch":
        packet["candidateDigest"] = f"sha256:{'0' * 64}"
    elif mutation == "client-verdict":
        packet["verdict"] = "accept"
    elif mutation == "client-document-digest":
        packet["publicDocumentDigest"] = f"sha256:{'1' * 64}"
    else:
        packet["authorization"] = True

    import src.crossword.publication_lineage as lineage_module

    def review_must_not_run(_packet):
        raise AssertionError("invalid binding/shape must fail before packet review")

    monkeypatch.setattr(
        lineage_module, "review_publication_packet", review_must_not_run
    )
    assessment = _assessment(api, digest, packet)

    assert assessment.status == "blocked"
    assert assessment.candidate_digest is None
    assert assessment.packet_digest is None
    assert assessment.reason_codes == (expected_reason,)
    with api.app.app_context():
        assert api.db.session.query(FuturePuzzleV2PublishedRecord).count() == 0


@pytest.mark.parametrize(
    ("digest", "packet", "reason"),
    [
        ("not-a-digest", {}, "candidate-digest-invalid"),
        (f"sha256:{'a' * 64}", None, "packet-invalid"),
    ],
)
def test_invalid_inputs_have_only_blocked_diagnostics(api, digest, packet, reason):
    assessment = _assessment(api, digest, packet)

    assert assessment.status == "blocked"
    assert assessment.candidate_digest is None
    assert assessment.packet_digest is None
    assert assessment.reason_codes == (reason,)


def _lineage_audit_shape() -> dict[str, object]:
    candidate_digest = f"sha256:{'a' * 64}"
    packet_digest = f"sha256:{'b' * 64}"
    receipt_id = str(uuid4())
    artifact_id = str(uuid4())
    artifact = {
        "artifactId": artifact_id,
        "sha256": "c" * 64,
        "kind": "clue-semantic-review",
        "candidateDigest": candidate_digest,
        "packetDigest": packet_digest,
        "claimPath": "clueAdjudications[0].evidenceRefs[0]",
        "uploaderId": "reviewer-a",
        "reviewerClaimReceiptId": receipt_id,
    }
    manifest = [
        {
            "claimPath": artifact["claimPath"],
            "artifactId": artifact_id,
            "sha256": artifact["sha256"],
            "kind": artifact["kind"],
        }
    ]
    evidence_manifest_digest = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
    )
    audit: dict[str, object] = {
        "schema": "publication-lineage-audit-shape-v1",
        "sourceCandidateDigest": candidate_digest,
        "reviewPacketDigest": packet_digest,
        "reviewPacketCandidateDigest": candidate_digest,
        "sanitizedDocumentDigest": f"sha256:{'d' * 64}",
        "claimedGateVerifier": {
            "gateVersion": "puzzle-v2-gate-v1",
            "verifierId": "host-gate-1",
        },
        "claimedReviewerReceipts": [
            {
                "receiptId": receipt_id,
                "reviewerId": "reviewer-a",
                "claimPath": "clueAdjudications[0]",
                "claimDigest": f"sha256:{'e' * 64}",
                "candidateDigest": candidate_digest,
                "packetDigest": packet_digest,
                "evidenceManifestDigest": evidence_manifest_digest,
                "recordedAt": "2026-09-27T11:00:00.000+00:00",
                "evidenceArtifactIds": [artifact_id],
            }
        ],
        "claimedEvidenceArtifacts": [artifact],
        "claimedPublisher": {
            "principalId": "local-publisher",
            "authenticatedAt": "2026-09-27T11:01:00Z",
        },
    }
    unsigned = json.dumps(
        audit, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    audit["auditDigest"] = "sha256:" + hashlib.sha256(unsigned).hexdigest()
    return audit


def test_lineage_audit_shape_and_digest_are_only_self_consistent_claims():
    audit = _lineage_audit_shape()

    assert validate_publication_lineage_audit_shape_v1(audit) is None
    assert verify_publication_lineage_audit_digest_self_consistency_v1(audit)
    assert "pass" not in audit and "accepted" not in audit

    # A caller can recompute this digest. It is not an authenticated signature.
    audit["claimedPublisher"] = {
        "principalId": "caller-invented",
        "authenticatedAt": "2026-09-27T11:01:00Z",
    }
    unsigned = {key: value for key, value in audit.items() if key != "auditDigest"}
    audit["auditDigest"] = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
    )
    assert verify_publication_lineage_audit_digest_self_consistency_v1(audit)


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("unexpected-key", "audit-keys-invalid"),
        ("wrong-schema", "audit-schema-invalid"),
        ("packet-candidate", "packet-candidate-misbinding"),
        ("receipt-packet", "reviewer-receipt-misbinding"),
        ("artifact-candidate", "evidence-artifact-misbinding"),
        ("artifact-manifest", "reviewer-evidence-manifest-misbinding"),
        ("artifact-claim", "reviewer-evidence-claim-misbinding"),
        ("artifact-uploader", "reviewer-evidence-uploader-misbinding"),
        ("receipt-duplicate", "duplicate-reviewer-receipt-id"),
        ("artifact-duplicate", "duplicate-evidence-artifact-id"),
    ],
)
def test_lineage_audit_rejects_malformed_duplicate_and_misbound_values(
    mutation, reason
):
    audit = _lineage_audit_shape()
    if mutation == "unexpected-key":
        audit["pass"] = True
    elif mutation == "wrong-schema":
        audit["schema"] = "publication-lineage-audit-v2"
    elif mutation == "packet-candidate":
        audit["reviewPacketCandidateDigest"] = f"sha256:{'f' * 64}"
    elif mutation == "receipt-packet":
        audit["claimedReviewerReceipts"][0]["packetDigest"] = f"sha256:{'f' * 64}"
    elif mutation == "artifact-candidate":
        audit["claimedEvidenceArtifacts"][0]["candidateDigest"] = f"sha256:{'f' * 64}"
    elif mutation == "artifact-manifest":
        audit["claimedEvidenceArtifacts"][0]["sha256"] = "f" * 64
    elif mutation == "artifact-claim":
        audit["claimedReviewerReceipts"][0]["claimPath"] = "clueAdjudications[1]"
    elif mutation == "artifact-uploader":
        audit["claimedEvidenceArtifacts"][0]["uploaderId"] = "reviewer-b"
    elif mutation == "receipt-duplicate":
        audit["claimedReviewerReceipts"].append(
            json.loads(json.dumps(audit["claimedReviewerReceipts"][0]))
        )
    else:
        audit["claimedEvidenceArtifacts"].append(
            json.loads(json.dumps(audit["claimedEvidenceArtifacts"][0]))
        )

    with pytest.raises(PublicationLineageAuditShapeRejected) as error:
        validate_publication_lineage_audit_shape_v1(audit)
    assert error.value.code == reason
    assert not verify_publication_lineage_audit_digest_self_consistency_v1(audit)


def test_lineage_audit_rejects_oversized_collections_and_noncanonical_time():
    audit = _lineage_audit_shape()
    audit["claimedEvidenceArtifacts"] = [{}] * (MAX_PUBLICATION_LINEAGE_ARTIFACTS + 1)
    with pytest.raises(PublicationLineageAuditShapeRejected) as error:
        validate_publication_lineage_audit_shape_v1(audit)
    assert error.value.code == "evidence-artifacts-invalid"
    assert not verify_publication_lineage_audit_digest_self_consistency_v1(audit)

    audit = _lineage_audit_shape()
    audit["claimedPublisher"]["authenticatedAt"] = "2026-09-27T13:01:00+02:00"
    with pytest.raises(PublicationLineageAuditShapeRejected) as error:
        validate_publication_lineage_audit_shape_v1(audit)
    assert error.value.code == "publisher-time-invalid"


def test_lineage_audit_rejects_serialized_payload_over_byte_cap():
    audit = _lineage_audit_shape()
    candidate_digest = audit["sourceCandidateDigest"]
    packet_digest = audit["reviewPacketDigest"]
    reviewer_id = "reviewer_" + "a" * 119
    receipts = []
    artifacts = []
    for index in range(MAX_PUBLICATION_LINEAGE_RECEIPTS):
        claim_path = f"sourceAttestations[{index}]"
        receipt_id = str(uuid4())
        artifact_id = str(uuid4())
        evidence_path = claim_path + ".evidenceRefs[0]"
        artifact = {
            "artifactId": artifact_id,
            "sha256": "c" * 64,
            "kind": "source-artifact",
            "candidateDigest": candidate_digest,
            "packetDigest": packet_digest,
            "claimPath": evidence_path,
            "uploaderId": reviewer_id,
            "reviewerClaimReceiptId": receipt_id,
        }
        manifest = [
            {
                "claimPath": evidence_path,
                "artifactId": artifact_id,
                "sha256": "c" * 64,
                "kind": "source-artifact",
            }
        ]
        manifest_digest = (
            "sha256:"
            + hashlib.sha256(
                json.dumps(
                    manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
        )
        receipts.append(
            {
                "receiptId": receipt_id,
                "reviewerId": reviewer_id,
                "claimPath": claim_path,
                "claimDigest": f"sha256:{'e' * 64}",
                "candidateDigest": candidate_digest,
                "packetDigest": packet_digest,
                "evidenceManifestDigest": manifest_digest,
                "recordedAt": "2026-09-27T11:00:00Z",
                "evidenceArtifactIds": [artifact_id],
            }
        )
        artifacts.append(artifact)
    audit["claimedReviewerReceipts"] = receipts
    audit["claimedEvidenceArtifacts"] = artifacts

    encoded_size = len(
        json.dumps(
            audit, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )
    assert encoded_size > MAX_PUBLICATION_LINEAGE_AUDIT_BYTES
    with pytest.raises(PublicationLineageAuditShapeRejected) as error:
        validate_publication_lineage_audit_shape_v1(audit)
    assert error.value.code == "audit-size-exceeded"


def test_lineage_audit_bounds_aggregate_nested_artifact_references():
    audit = _lineage_audit_shape()
    references = [
        str(uuid4()) for _ in range(MAX_PUBLICATION_LINEAGE_ARTIFACT_REFERENCES)
    ]
    receipts = []
    for index in range(2):
        receipt = json.loads(json.dumps(audit["claimedReviewerReceipts"][0]))
        receipt["receiptId"] = str(uuid4())
        receipt["reviewerId"] = f"reviewer-{index}"
        receipt["claimPath"] = f"sourceAttestations[{index}]"
        receipt["evidenceArtifactIds"] = references
        receipts.append(receipt)
    receipts[1]["evidenceArtifactIds"] = references[:1]
    audit["claimedReviewerReceipts"] = receipts

    with pytest.raises(PublicationLineageAuditShapeRejected) as error:
        validate_publication_lineage_audit_shape_v1(audit)
    assert error.value.code == "reviewer-receipt-reference-limit-exceeded"


def test_lineage_audit_digest_mismatch_is_not_shape_or_trust_evidence():
    audit = _lineage_audit_shape()
    audit["auditDigest"] = f"sha256:{'0' * 64}"

    assert validate_publication_lineage_audit_shape_v1(audit) is None
    assert not verify_publication_lineage_audit_digest_self_consistency_v1(audit)
