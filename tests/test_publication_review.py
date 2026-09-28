"""Read-only host composition of the V2 publication gate and evidence store."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

import pytest

from tests.test_api_isolated import api, no_network  # noqa: F401
from tests.test_publication_evidence import _review_packet, _store_rows
from src.crossword.future_puzzles import (
    FuturePuzzleV2CandidateRecord,
    FuturePuzzleManifestRecord,
    validate_personalized_v2_review_candidate,
)
from src.crossword.publication_evidence import (
    PublicationEvidenceArtifact,
    PublicationEvidenceArtifactClaim,
    resolve_publication_packet_evidence,
)
from src.crossword.v2_session_journal import FuturePuzzleV2PublishedRecord
from src.crossword.publication_review import (
    PublicationReviewDiagnostic,
    PublicationReviewRejected,
    _snapshot_packet,
    review_publication_packet,
)


@pytest.fixture
def review_case(api):
    manifest = json.loads(
        (Path(__file__).parent / "fixtures/personalized-review-v2.json").read_text()
    )
    candidate = validate_personalized_v2_review_candidate(manifest)
    digest = candidate["integrity"]["value"]
    with api.app.app_context():
        api.db.session.add(
            FuturePuzzleV2CandidateRecord(
                profile_id=str(uuid4()),
                candidate_hash=digest.removeprefix("sha256:"),
                candidate_id=candidate["id"],
                job_id=str(uuid4()),
                manifest_json=candidate,
                created_at="2026-09-26T12:00:00.000+00:00",
            )
        )
        api.db.session.commit()
    packet, rows, _refs = _review_packet(digest)
    packet["packetDigest"] = _packet_digest(packet)
    return digest, packet, rows


def _packet_digest(packet):
    unsigned = {key: value for key, value in packet.items() if key != "packetDigest"}
    canonical = json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def _residual_evaluation(candidate, packet):
    return {
        "gateVersion": "puzzle-v2-publication-gate-v1",
        "candidateDigest": candidate["integrity"]["value"],
        "status": "evidence-unverified",
        "reasons": [
            {
                "code": "reviewer-evidence-unverified",
                "path": "publicationReview",
                "message": "Synthetic gate fixture: host evidence is still semantically unverified.",
            }
        ],
    }


def _enable_residual_gate(monkeypatch):
    import src.crossword.publication_review as review_module
    import src.crossword.publication_attestation as attestation_module

    monkeypatch.setattr(
        review_module, "evaluate_puzzle_v2_publication_gate", _residual_evaluation
    )
    monkeypatch.setattr(
        attestation_module, "evaluate_puzzle_v2_publication_gate", _residual_evaluation
    )


def _claim_rows(rows):
    return {row._claim_path: row for row in rows}


def _review(api, packet):
    with api.app.app_context():
        return review_publication_packet(packet)


def test_blocked_shared_gate_returns_without_resolving_artifacts(
    api, review_case, monkeypatch
):
    import src.crossword.publication_review as review_module

    digest, packet, _rows = review_case

    def unexpected_resolution(*_args, **_kwargs):
        raise AssertionError("blocked packets must not resolve artifacts")

    monkeypatch.setattr(
        review_module, "resolve_publication_packet_evidence", unexpected_resolution
    )
    packet["packetDigest"] = "sha256:" + "0" * 64
    diagnostic = _review(api, packet)

    assert diagnostic.status == "blocked"
    assert diagnostic.gate_candidate_digest == digest
    assert "packet-digest-invalid" in diagnostic.reason_codes
    assert diagnostic.packet_digest is None
    assert diagnostic.evidence_artifact_count == 0


def test_composes_gate_and_resolver_on_the_exact_packet_and_candidate(
    api, review_case, monkeypatch
):
    digest, packet, rows = review_case
    _store_rows(api, rows)
    _enable_residual_gate(monkeypatch)
    import src.crossword.publication_review as review_module

    seen = {}
    actual_resolver = resolve_publication_packet_evidence

    def capture_gate(candidate, gate_packet):
        seen["candidate"] = candidate
        seen["gate_packet"] = gate_packet
        evaluation = _residual_evaluation(candidate, gate_packet)
        # Simulate a caller mutating its original object after the gate has
        # assessed it but before evidence resolution begins.
        packet["reviewId"] = "caller-mutated-after-gate"
        return evaluation

    def capture_resolver(resolver_packet, resolver_digest):
        seen["resolver_packet"] = resolver_packet
        seen["resolver_digest"] = resolver_digest
        return actual_resolver(resolver_packet, resolver_digest)

    monkeypatch.setattr(review_module, "evaluate_puzzle_v2_publication_gate", capture_gate)
    monkeypatch.setattr(review_module, "resolve_publication_packet_evidence", capture_resolver)

    diagnostic = _review(api, packet)

    assert seen["gate_packet"] is seen["resolver_packet"]
    assert seen["gate_packet"] is not packet
    assert packet["reviewId"] == "caller-mutated-after-gate"
    assert seen["resolver_digest"] == digest
    assert seen["candidate"]["integrity"]["value"] == digest
    assert isinstance(diagnostic, PublicationReviewDiagnostic)
    assert diagnostic.status == "evidence-unverified"
    assert diagnostic.gate_candidate_digest == digest
    assert diagnostic.packet_digest == packet["packetDigest"]
    assert diagnostic.evidence_artifact_count == len(rows)
    assert diagnostic.authenticated_uploader_count == 3
    assert diagnostic.declared_blind_reviewer_count == 2
    assert diagnostic.human_attestation_expected_count > 0
    assert diagnostic.human_attestation_verified_count == 0
    assert "human-attestation-incomplete" in diagnostic.reason_codes
    assert not hasattr(diagnostic, "artifacts")
    assert "reviewerId" not in diagnostic.to_dict()
    with api.app.app_context():
        assert api.db.session.query(FuturePuzzleManifestRecord).count() == 0
        assert api.db.session.query(FuturePuzzleV2PublishedRecord).count() == 0


def test_packet_content_tamper_is_blocked_before_artifact_resolution(
    api, review_case, monkeypatch
):
    import src.crossword.publication_review as review_module

    _digest, packet, _rows = review_case

    def unexpected_resolution(*_args, **_kwargs):
        raise AssertionError("tampered packet must not resolve artifacts")

    monkeypatch.setattr(
        review_module, "resolve_publication_packet_evidence", unexpected_resolution
    )
    packet["reviewId"] = "changed-after-sealing"
    diagnostic = _review(api, packet)

    assert diagnostic.status == "blocked"
    assert "packet-digest-invalid" in diagnostic.reason_codes


@pytest.mark.parametrize("failure", ["missing", "substituted", "cross-claim"])
def test_unresolved_or_reassigned_artifact_fails_closed(
    api, review_case, monkeypatch, failure
):
    digest, packet, rows = review_case
    indexed = _claim_rows(rows)
    row_values = {
        path: (row.artifact_id, row.sha256, row.kind)
        for path, row in indexed.items()
    }
    _store_rows(api, rows)
    _enable_residual_gate(monkeypatch)
    source_path = "sourceAttestations[0].evidenceRefs[0]"
    blind_path = "weekdayReview.blindClassifications[0].rationale"

    if failure == "missing":
        artifact_id, _sha256, _kind = row_values[source_path]
        with api.app.app_context():
            api.db.session.delete(
                api.db.session.get(PublicationEvidenceArtifactClaim, artifact_id)
            )
            api.db.session.delete(
                api.db.session.get(PublicationEvidenceArtifact, artifact_id)
            )
            api.db.session.commit()
    elif failure == "substituted":
        # A valid existing artifact of another kind cannot stand in for the
        # required source artifact at this packet location.
        artifact_id, sha256, kind = row_values[
            "crossingReview.certificates[0].evidenceRefs[0]"
        ]
        packet["sourceAttestations"][0]["evidenceRefs"][0] = {
            "artifactId": artifact_id,
            "sha256": sha256,
            "kind": kind,
        }
    else:
        # Same evidence kind, wrong cryptographic claim path.
        artifact_id, sha256, kind = row_values[blind_path]
        packet["weekdayReview"]["evidenceRefs"][0] = {
            "artifactId": artifact_id,
            "sha256": sha256,
            "kind": kind,
        }

    with pytest.raises(PublicationReviewRejected, match="evidence-resolution-failed"):
        _review(api, packet)


def test_packet_reviewer_must_match_authenticated_upload_identity(
    api, review_case, monkeypatch
):
    _digest, packet, rows = review_case
    _store_rows(api, rows)
    _enable_residual_gate(monkeypatch)
    packet["sourceAttestations"][0]["reviewerId"] = "different-packet-reviewer"

    with pytest.raises(PublicationReviewRejected, match="evidence-resolution-failed"):
        _review(api, packet)


def test_real_gate_blocks_duplicate_blind_raters_and_no_registry_row_is_written(
    api, review_case
):
    _digest, packet, _rows = review_case
    packet["weekdayReview"]["blindClassifications"][1]["reviewerId"] = packet[
        "weekdayReview"
    ]["blindClassifications"][0]["reviewerId"]
    packet["packetDigest"] = _packet_digest(packet)

    diagnostic = _review(api, packet)

    assert diagnostic.status == "blocked"
    assert "weekday-classification-failed" in diagnostic.reason_codes
    with api.app.app_context():
        assert api.db.session.query(FuturePuzzleManifestRecord).count() == 0


def test_mismatched_or_malformed_gate_output_is_rejected(api, review_case, monkeypatch):
    import src.crossword.publication_review as review_module

    digest, packet, _rows = review_case
    monkeypatch.setattr(
        review_module,
        "evaluate_puzzle_v2_publication_gate",
        lambda candidate, _packet: {
            **_residual_evaluation(candidate, _packet),
            "candidateDigest": "sha256:" + "f" * 64,
        },
    )
    with pytest.raises(PublicationReviewRejected, match="gate-output-invalid"):
        _review(api, packet)

    monkeypatch.setattr(
        review_module, "evaluate_puzzle_v2_publication_gate", lambda *_args: {"status": "blocked"}
    )
    with pytest.raises(PublicationReviewRejected, match="gate-output-invalid"):
        _review(api, packet)

    assert re.fullmatch(r"sha256:[0-9a-f]{64}", digest)


def test_service_does_not_accept_caller_candidate_or_extra_authority(api, review_case):
    _digest, packet, _rows = review_case
    with pytest.raises(TypeError):
        with api.app.app_context():
            review_publication_packet(packet, verified=True)


def test_snapshot_rejects_oversize_before_building_a_serialized_copy(monkeypatch):
    import src.crossword.publication_review as review_module

    monkeypatch.setattr(review_module, "MAX_PUBLICATION_REVIEW_PACKET_BYTES", 32)

    def unexpected_serialization(*_args, **_kwargs):
        raise AssertionError("oversized packet must fail during preflight")

    monkeypatch.setattr(review_module.json, "dumps", unexpected_serialization)

    with pytest.raises(PublicationReviewRejected, match="packet-size-limit-exceeded"):
        _snapshot_packet({"payload": "x" * 64})
