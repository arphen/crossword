"""Synthetic-only tests for host-authenticated V2 claim attestations.

These tests establish receipt identity and immutable packet/evidence bindings.
They do not establish that a reviewer is truthful or that a puzzle is safe to
publish. The content fixture is synthetic, and the one positive gate path is
stubbed to the existing ``reviewer-evidence-unverified`` residual state.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from tests.test_api_isolated import api, no_network  # noqa: F401
from tests.test_publication_evidence import (
    REVIEWER_ID,
    TOKEN,
    _ref,
    _review_packet,
    _store_rows,
)
from src.crossword.future_puzzles import (
    FuturePuzzleManifestRecord,
    FuturePuzzleV2CandidateRecord,
    validate_personalized_v2_review_candidate,
)
from src.crossword.publication_attestation import (
    PublicationAttestationRejected,
    PublicationClaimAttestation,
)
from src.crossword.publication_attestation import (
    human_claims_for_packet,
    resolve_publication_packet_attestations,
)
from src.crossword.v2_session_journal import FuturePuzzleV2PublishedRecord


ATTESTATION_PATH = "/api/future/evidence/v2/attestations"
CLAIM_PATH = "sourceAttestations[0]"
CLAIM_EVIDENCE_PATH = "sourceAttestations[0].evidenceRefs[0]"
REVIEWER_ID_OTHER = "synthetic-other-reviewer"
TOKEN_OTHER = "synthetic-other-reviewer-credential-for-tests"
BLIND_REVIEWER_IDS = ("synthetic-blind-rater-1", "synthetic-blind-rater-2")
BLIND_REVIEWER_TOKENS = (
    "synthetic-blind-rater-one-credential-for-tests",
    "synthetic-blind-rater-two-credential-for-tests",
)


def _packet_digest(packet: dict) -> str:
    unsigned = {key: value for key, value in packet.items() if key != "packetDigest"}
    encoded = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _seal(packet: dict) -> dict:
    packet["packetDigest"] = _packet_digest(packet)
    return packet


def _digest_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _residual_evaluation(candidate, _packet):
    if _packet.get("packetDigest") != _packet_digest(_packet):
        return {
            "gateVersion": "puzzle-v2-publication-gate-v1",
            "candidateDigest": candidate["integrity"]["value"],
            "status": "blocked",
            "reasons": [
                {
                    "code": "packet-digest-invalid",
                    "path": "packet.packetDigest",
                    "message": "Synthetic gate rejects a stale packet seal.",
                }
            ],
        }
    return {
        "gateVersion": "puzzle-v2-publication-gate-v1",
        "candidateDigest": candidate["integrity"]["value"],
        "status": "evidence-unverified",
        "reasons": [
            {
                "code": "reviewer-evidence-unverified",
                "path": "publicationReview",
                "message": "Synthetic fixture: a configured reviewer assertion is required.",
            }
        ],
    }


@pytest.fixture
def attestation_case(api, monkeypatch):
    manifest = json.loads(
        (Path(__file__).parent / "fixtures/personalized-review-v2.json").read_text()
    )
    candidate = validate_personalized_v2_review_candidate(manifest)
    candidate_digest = candidate["integrity"]["value"]
    with api.app.app_context():
        api.db.session.add(
            FuturePuzzleV2CandidateRecord(
                profile_id=str(uuid4()),
                candidate_hash=candidate_digest.removeprefix("sha256:"),
                candidate_id=candidate["id"],
                job_id=str(uuid4()),
                manifest_json=candidate,
                created_at="2026-09-26T12:00:00.000+00:00",
            )
        )
        api.db.session.commit()

    api.app.config["CROSSWORD_REVIEWER_TOKEN"] = TOKEN
    api.app.config["CROSSWORD_REVIEWER_ID"] = REVIEWER_ID
    api.app.config["CROSSWORD_ADDITIONAL_REVIEWERS_JSON"] = json.dumps(
        [
            {"reviewerId": REVIEWER_ID_OTHER, "token": TOKEN_OTHER},
            *[
                {"reviewerId": reviewer_id, "token": token}
                for reviewer_id, token in zip(
                    BLIND_REVIEWER_IDS, BLIND_REVIEWER_TOKENS, strict=True
                )
            ],
        ]
    )

    packet, rows, _refs = _review_packet(candidate_digest)
    _seal(packet)
    _store_rows(api, rows)

    # The only synthetic success is the documented residual state. The real
    # TypeScript gate remains independently exercised by publication-review
    # tests against blocked candidates and packets.
    import src.crossword.publication_review as review_module
    import src.crossword.publication_attestation as attestation_module

    monkeypatch.setattr(
        review_module, "evaluate_puzzle_v2_publication_gate", _residual_evaluation
    )
    monkeypatch.setattr(
        attestation_module, "evaluate_puzzle_v2_publication_gate", _residual_evaluation
    )
    return candidate_digest, packet, rows


def _post(api, packet, claim_path=CLAIM_PATH, *, token=TOKEN, extra=None):
    body = {"packet": deepcopy(packet), "claimPath": claim_path}
    if extra:
        body.update(extra)
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    return api.app.test_client().post(ATTESTATION_PATH, json=body, headers=headers)


def _assert_no_publication(api):
    with api.app.app_context():
        assert api.db.session.query(FuturePuzzleManifestRecord).count() == 0
        assert api.db.session.query(FuturePuzzleV2PublishedRecord).count() == 0


def _assert_attestation_count(api, expected):
    with api.app.app_context():
        assert api.db.session.query(PublicationClaimAttestation).count() == expected


def _attestation(response):
    assert response.status_code == 201, response.get_data(as_text=True)
    assert response.cache_control.no_store
    assert set(response.json) == {"attestation"}
    value = response.json["attestation"]
    assert set(value) == {
        "id",
        "protocolVersion",
        "candidateDigest",
        "packetDigest",
        "claimPath",
        "claimDigest",
        "evidenceDigest",
        "reviewerId",
        "createdAt",
    }
    return value


def test_attestation_is_host_authored_and_binds_packet_claim_evidence_and_principal(
    api, attestation_case
):
    candidate_digest, packet, _rows = attestation_case

    response = _post(api, packet)
    receipt = _attestation(response)

    assert UUID(receipt["id"])
    assert isinstance(receipt["protocolVersion"], str) and receipt["protocolVersion"]
    assert receipt["candidateDigest"] == candidate_digest
    assert receipt["packetDigest"] == packet["packetDigest"]
    assert receipt["claimPath"] == CLAIM_PATH
    assert receipt["claimDigest"] == _digest_json(packet["sourceAttestations"][0])
    refs = packet["sourceAttestations"][0]["evidenceRefs"]
    manifest = [
        {
            "claimPath": f"{CLAIM_PATH}.evidenceRefs[{index}]",
            "artifactId": reference["artifactId"],
            "sha256": reference["sha256"],
            "kind": reference["kind"],
        }
        for index, reference in enumerate(refs)
    ]
    assert receipt["evidenceDigest"] == _digest_json(manifest)
    assert receipt["reviewerId"] == REVIEWER_ID
    parsed_time = datetime.fromisoformat(receipt["createdAt"].replace("Z", "+00:00"))
    assert parsed_time.tzinfo is not None
    assert abs((datetime.now(parsed_time.tzinfo) - parsed_time).total_seconds()) < 60
    _assert_attestation_count(api, 1)
    _assert_no_publication(api)


def test_exact_attestation_retry_returns_the_same_append_only_receipt(
    api, attestation_case
):
    _digest, packet, _rows = attestation_case

    first_response = _post(api, packet)
    first = _attestation(first_response)
    retry = _post(api, packet)

    assert retry.status_code == 200, retry.get_data(as_text=True)
    assert retry.cache_control.no_store
    assert retry.json == {"attestation": first}
    _assert_attestation_count(api, 1)
    _assert_no_publication(api)


def test_review_evaluator_counts_exact_human_receipts_but_never_clears_unverified(
    api, attestation_case
):
    from src.crossword.publication_attestation import human_claims_for_packet
    from src.crossword.publication_review import review_publication_packet

    _candidate_digest, packet, _rows = attestation_case
    blind_tokens = {
        "synthetic-blind-rater-1": "synthetic-blind-rater-token-one-for-tests",
        "synthetic-blind-rater-2": "synthetic-blind-rater-token-two-for-tests",
    }
    api.app.config["CROSSWORD_ADDITIONAL_REVIEWERS_JSON"] = json.dumps(
        [
            {"reviewerId": REVIEWER_ID_OTHER, "token": TOKEN_OTHER},
            *(
                {"reviewerId": reviewer_id, "token": token}
                for reviewer_id, token in blind_tokens.items()
            ),
        ]
    )

    with api.app.app_context():
        before = review_publication_packet(packet)
    assert before.status == "evidence-unverified"
    assert "human-attestation-incomplete" in before.reason_codes
    assert before.human_attestation_expected_count == 6
    assert before.human_attestation_verified_count == 0

    for claim in human_claims_for_packet(packet):
        token = blind_tokens.get(claim.reviewer_id, TOKEN)
        response = _post(api, packet, claim.claim_path, token=token)
        _attestation(response)

    with api.app.app_context():
        after = review_publication_packet(packet)

    assert after.status == "evidence-unverified"
    assert after.reason_codes == ("reviewer-evidence-unverified",)
    assert after.human_attestation_expected_count == 6
    assert after.human_attestation_verified_count == 6
    assert after.declared_blind_reviewer_count == 2
    _assert_no_publication(api)


def test_changed_resealed_claim_gets_a_distinct_packet_bound_receipt_and_manifest(
    api, attestation_case
):
    candidate_digest, packet, _rows = attestation_case
    first = _attestation(_post(api, packet))

    # Replace one nested evidence byte manifest with a second authentic,
    # immutable upload assigned to the same evidence slot. The revised claim
    # remains structurally valid and is sealed as a new packet.
    new_ref, new_row = _ref(
        "source-artifact",
        candidate_digest,
        CLAIM_EVIDENCE_PATH,
        body=b"different synthetic source evidence bytes",
    )
    new_row._claim_path = CLAIM_EVIDENCE_PATH
    _store_rows(api, [new_row])
    revised_packet = deepcopy(packet)
    revised_claim = revised_packet["sourceAttestations"][0]
    revised_claim["evidenceRefs"][0] = new_ref
    revised_claim["artifactSha256"] = new_ref["sha256"]
    _seal(revised_packet)

    second = _attestation(_post(api, revised_packet))

    assert revised_packet["packetDigest"] != packet["packetDigest"]
    assert second["id"] != first["id"]
    assert second["candidateDigest"] == first["candidateDigest"] == candidate_digest
    assert second["packetDigest"] == revised_packet["packetDigest"]
    assert second["packetDigest"] != first["packetDigest"]
    assert second["claimPath"] == first["claimPath"] == CLAIM_PATH
    assert second["claimDigest"] != first["claimDigest"]
    assert second["evidenceDigest"] != first["evidenceDigest"]
    assert first["packetDigest"] == packet["packetDigest"]
    assert first["evidenceDigest"] != second["evidenceDigest"]
    _assert_attestation_count(api, 2)
    _assert_no_publication(api)


def test_conflicting_existing_natural_key_fails_closed(api, attestation_case):
    candidate_digest, packet, _rows = attestation_case
    first = _attestation(_post(api, packet))
    with api.app.app_context():
        row = api.db.session.query(PublicationClaimAttestation).one()
        row.claim_digest = _digest_json({"conflicting": True})
        api.db.session.commit()

    conflict = _post(api, packet)

    assert conflict.status_code == 409, conflict.get_data(as_text=True)
    assert conflict.cache_control.no_store
    assert conflict.json == {"error": "A different attestation exists for this claim"}
    assert first["candidateDigest"] == candidate_digest
    _assert_attestation_count(api, 1)
    _assert_no_publication(api)


def test_service_requires_a_resolved_reviewer_principal_object(api, attestation_case):
    from src.crossword.publication_attestation import (
        PublicationAttestationRejected,
        attest_publication_claim,
    )

    _digest, packet, _rows = attestation_case
    with api.app.app_context():
        with pytest.raises(
            PublicationAttestationRejected, match="authenticated-reviewer-invalid"
        ):
            attest_publication_claim(packet, CLAIM_PATH, REVIEWER_ID)
    _assert_attestation_count(api, 0)
    _assert_no_publication(api)


def test_attestation_route_has_no_read_update_or_delete_api(api, attestation_case):
    _digest, packet, _rows = attestation_case
    client = api.app.test_client()
    headers = {"Authorization": f"Bearer {TOKEN}"}

    assert client.get(ATTESTATION_PATH).status_code == 405
    assert client.put(ATTESTATION_PATH, json={"packet": packet}, headers=headers).status_code == 405
    assert client.delete(ATTESTATION_PATH, headers=headers).status_code == 405
    _assert_attestation_count(api, 0)


def test_human_claim_projection_excludes_machine_or_separately_reviewed_subclaims(
    attestation_case,
):
    _digest, packet, _rows = attestation_case

    claims = {claim.claim_path: claim for claim in human_claims_for_packet(packet)}
    clue_path = "clueAdjudications[0]"
    weekday_path = "weekdayReview"
    crossing_path = "crossingReview.certificates[0]"

    clue_claim = deepcopy(packet["clueAdjudications"][0])
    challenger = clue_claim.pop("challenger")
    assert claims[clue_path].claim_digest == _digest_json(clue_claim)
    assert [reference[1] for reference in claims[clue_path].evidence_refs] == [
        item["artifactId"] for item in packet["clueAdjudications"][0]["evidenceRefs"]
    ]
    assert all("challenger" not in reference[0] for reference in claims[clue_path].evidence_refs)
    assert challenger["evidenceRefs"][0]["artifactId"] not in {
        reference[1] for reference in claims[clue_path].evidence_refs
    }

    weekday_claim = {
        key: value
        for key, value in packet["weekdayReview"].items()
        if key not in {"blindClassifications", "mechanicRoute"}
    }
    assert claims[weekday_path].claim_digest == _digest_json(weekday_claim)
    assert [reference[1] for reference in claims[weekday_path].evidence_refs] == [
        item["artifactId"] for item in packet["weekdayReview"]["evidenceRefs"]
    ]
    assert all(
        "blindClassifications" not in reference[0] and "mechanicRoute" not in reference[0]
        for reference in claims[weekday_path].evidence_refs
    )
    assert all(
        f"{weekday_path}.blindClassifications[{index}]" in claims
        for index in range(len(packet["weekdayReview"]["blindClassifications"]))
    )

    crossing_refs = claims[crossing_path].evidence_refs
    assert [reference[0] for reference in crossing_refs] == [
        f"{crossing_path}.evidenceRefs[0]",
        f"{crossing_path}.topologyConstraint.evidenceRefs[0]",
    ]
    assert [reference[1] for reference in crossing_refs] == [
        packet["crossingReview"]["certificates"][0]["evidenceRefs"][0]["artifactId"],
        packet["crossingReview"]["certificates"][0]["topologyConstraint"]["evidenceRefs"][0]["artifactId"],
    ]


def test_attestation_coverage_moves_from_incomplete_to_complete(api, attestation_case):
    candidate_digest, packet, _rows = attestation_case
    with api.app.app_context():
        incomplete = resolve_publication_packet_attestations(
            packet, candidate_digest, packet["packetDigest"]
        )

    assert incomplete.complete is False
    assert incomplete.expected_claim_count == 6
    assert incomplete.attested_claim_count == 0
    assert set(incomplete.missing_claim_paths) == {
        "sourceAttestations[0]",
        "clueAdjudications[0]",
        "crossingReview.certificates[0]",
        "weekdayReview",
        "weekdayReview.blindClassifications[0]",
        "weekdayReview.blindClassifications[1]",
    }

    claim_reviewers = [
        ("sourceAttestations[0]", TOKEN),
        ("clueAdjudications[0]", TOKEN),
        ("crossingReview.certificates[0]", TOKEN),
        ("weekdayReview", TOKEN),
        *[
            (f"weekdayReview.blindClassifications[{index}]", token)
            for index, token in enumerate(BLIND_REVIEWER_TOKENS)
        ],
    ]
    for claim_path, token in claim_reviewers:
        response = _post(api, packet, claim_path, token=token)
        assert response.status_code == 201, response.get_data(as_text=True)

    with api.app.app_context():
        complete = resolve_publication_packet_attestations(
            packet, candidate_digest, packet["packetDigest"]
        )

    assert complete.complete is True
    assert complete.expected_claim_count == 6
    assert complete.attested_claim_count == 6
    assert complete.missing_claim_paths == ()
    _assert_attestation_count(api, 6)
    _assert_no_publication(api)


def test_coverage_rechecks_the_shared_gate_when_caller_reuses_a_stale_seal(
    api, attestation_case
):
    candidate_digest, packet, _rows = attestation_case
    tampered = deepcopy(packet)
    tampered["reviewId"] = "caller-mutated-without-resealing"
    with api.app.app_context(), pytest.raises(
        PublicationAttestationRejected, match="packet-gate-invalid"
    ):
        resolve_publication_packet_attestations(
            tampered,
            candidate_digest,
            packet["packetDigest"],
        )
    _assert_attestation_count(api, 0)
    _assert_no_publication(api)


@pytest.mark.parametrize(
    ("claim_path", "extra", "token"),
    [
        (CLAIM_PATH, {"reviewerId": "forged-caller-reviewer"}, TOKEN),
        (CLAIM_PATH, None, TOKEN_OTHER),
        (CLAIM_EVIDENCE_PATH, None, TOKEN),
    ],
    ids=["forged-request-identity", "wrong-authenticated-principal", "machine-only-path"],
)
def test_forged_identity_wrong_principal_and_machine_path_fail_closed_without_writes(
    api, attestation_case, claim_path, extra, token
):
    _digest, packet, _rows = attestation_case

    response = _post(api, packet, claim_path, token=token, extra=extra)

    assert response.status_code >= 400
    assert response.status_code < 500
    _assert_attestation_count(api, 0)
    _assert_no_publication(api)


def test_packet_content_tamper_fails_before_receipt_or_registry_write(
    api, attestation_case
):
    _digest, packet, _rows = attestation_case
    tampered = deepcopy(packet)
    tampered["sourceAttestations"][0]["spdx"] = "MIT"
    # Preserve the prior packet digest, so the host must reject the stale seal.

    response = _post(api, tampered)

    assert response.status_code >= 400
    assert response.status_code < 500
    _assert_attestation_count(api, 0)
    _assert_no_publication(api)


@pytest.mark.parametrize("tamper", ["missing", "bytes"], ids=["missing-artifact", "tampered-artifact"])
def test_missing_or_tampered_evidence_fails_closed_without_receipt(
    api, attestation_case, tamper
):
    from src.crossword.publication_evidence import (
        PublicationEvidenceArtifact,
        PublicationEvidenceArtifactClaim,
    )

    _digest, packet, _rows = attestation_case
    artifact_id = packet["sourceAttestations"][0]["evidenceRefs"][0]["artifactId"]
    with api.app.app_context():
        stored = api.db.session.get(PublicationEvidenceArtifact, artifact_id)
        assert stored is not None
        if tamper == "missing":
            api.db.session.delete(
                api.db.session.get(PublicationEvidenceArtifactClaim, artifact_id)
            )
            api.db.session.delete(stored)
        else:
            # Simulate out-of-band storage corruption. Application APIs do not
            # expose byte mutation, and the resolver must detect the mismatch.
            stored.artifact_bytes = b"corrupted stored bytes"
        api.db.session.commit()

    response = _post(api, packet)

    assert response.status_code >= 400
    assert response.status_code < 500
    _assert_attestation_count(api, 0)
    _assert_no_publication(api)


def test_malformed_and_oversized_requests_fail_closed(api, attestation_case):
    _digest, packet, _rows = attestation_case
    client = api.app.test_client()

    malformed = client.post(
        ATTESTATION_PATH,
        data=b"{not-json",
        content_type="application/json",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert malformed.status_code >= 400

    # Exercise the host's bounded request body before JSON parsing or any write.
    api.app.config["MAX_CONTENT_LENGTH"] = 256
    oversized = client.post(
        ATTESTATION_PATH,
        data=json.dumps({"packet": packet, "claimPath": CLAIM_PATH, "padding": "x" * 512}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert oversized.status_code == 413
    _assert_attestation_count(api, 0)
    _assert_no_publication(api)
