"""Synthetic-only tests for host-authenticated V2 evidence artifact storage."""

from __future__ import annotations

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest

from tests.test_api_isolated import api, no_network  # noqa: F401
from src.crossword.future_puzzles import FuturePuzzleV2CandidateRecord
from src.crossword.publication_evidence import (
    MAX_CANDIDATE_ROWS_PER_DIGEST,
    MAX_EVIDENCE_CLAIM_PATH_LENGTH,
    MAX_PUBLICATION_EVIDENCE_BYTES,
    MAX_PUBLICATION_REVIEW_PACKET_BYTES,
    PublicationEvidenceArtifact,
    PublicationEvidenceArtifactClaim,
    PublicationEvidenceStorageQuota,
    PublicationEvidenceRejected,
    resolve_publication_packet_evidence,
)


TOKEN = "synthetic-reviewer-credential-for-publication-tests"
REVIEWER_ID = "configured-test-reviewer"


@pytest.fixture
def candidate(api):
    manifest = json.loads(
        (Path(__file__).parent / "fixtures/personalized-review-v2.json").read_text()
    )
    digest = manifest["integrity"]["value"]
    candidate_hash = digest.removeprefix("sha256:")
    with api.app.app_context():
        api.db.session.add(
            FuturePuzzleV2CandidateRecord(
                profile_id=str(uuid4()),
                candidate_hash=candidate_hash,
                candidate_id=manifest["id"],
                job_id=str(uuid4()),
                manifest_json=manifest,
                created_at="2026-09-26T12:00:00.000+00:00",
            )
        )
        api.db.session.commit()
    return digest


@pytest.fixture
def reviewer_config(api):
    api.app.config["CROSSWORD_REVIEWER_TOKEN"] = TOKEN
    api.app.config["CROSSWORD_REVIEWER_ID"] = REVIEWER_ID


_DEFAULT_CLAIM_PATHS = {
    "source-artifact": "sourceAttestations[0].evidenceRefs[0]",
    "license-terms-review": "sourceAttestations[0].evidenceRefs[1]",
    "clue-semantic-review": "clueAdjudications[0].evidenceRefs[0]",
    "clue-editorial-review": "clueAdjudications[0].evidenceRefs[1]",
    "challenger-run": "clueAdjudications[0].challenger.evidenceRefs[0]",
    "crossing-certificate": "crossingReview.certificates[0].evidenceRefs[0]",
    "solve-simulation": "crossingReview.simulation.evidenceRefs[0]",
    "weekday-review": "weekdayReview.evidenceRefs[0]",
    "mechanic-route": "weekdayReview.mechanicRoute.evidenceRefs[0]",
}


def _headers(candidate_digest, kind="source-artifact", *, token=TOKEN, claim_path=None):
    headers = {
        "X-Candidate-Digest": candidate_digest,
        "X-Evidence-Kind": kind,
        "X-Evidence-Claim-Path": (
            claim_path
            if claim_path is not None
            else _DEFAULT_CLAIM_PATHS.get(
                kind, "sourceAttestations[0].evidenceRefs[0]"
            )
        ),
        "Content-Type": "application/pdf",
    }
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _ref(kind, candidate_digest, claim_path, body=None, reviewer_id=REVIEWER_ID):
    artifact_bytes = body if body is not None else f"fixture:{kind}".encode()
    digest = hashlib.sha256(artifact_bytes).hexdigest()
    artifact_id = str(uuid4())
    return (
        {"artifactId": artifact_id, "sha256": digest, "kind": kind},
        PublicationEvidenceArtifact(
            artifact_id=artifact_id,
            sha256=digest,
            kind=kind,
            candidate_digest=candidate_digest,
            media_type="text/plain",
            reviewer_id=reviewer_id,
            recorded_at="2026-09-26T12:00:00.000+00:00",
            artifact_bytes=artifact_bytes,
        ),
    )


def _review_packet(candidate_digest):
    claims = [
        ("source-artifact", "sourceAttestations[0].evidenceRefs[0]", REVIEWER_ID),
        ("license-terms-review", "sourceAttestations[0].evidenceRefs[1]", REVIEWER_ID),
        ("clue-semantic-review", "clueAdjudications[0].evidenceRefs[0]", REVIEWER_ID),
        ("clue-editorial-review", "clueAdjudications[0].evidenceRefs[1]", REVIEWER_ID),
        ("challenger-run", "clueAdjudications[0].challenger.evidenceRefs[0]", REVIEWER_ID),
        ("crossing-certificate", "crossingReview.certificates[0].evidenceRefs[0]", REVIEWER_ID),
        ("crossing-certificate", "crossingReview.certificates[0].topologyConstraint.evidenceRefs[0]", REVIEWER_ID),
        ("solve-simulation", "crossingReview.simulation.evidenceRefs[0]", REVIEWER_ID),
        ("weekday-review", "weekdayReview.evidenceRefs[0]", REVIEWER_ID),
        ("weekday-review", "weekdayReview.blindClassifications[0].rationale", "synthetic-blind-rater-1"),
        ("weekday-review", "weekdayReview.blindClassifications[1].rationale", "synthetic-blind-rater-2"),
        ("mechanic-route", "weekdayReview.mechanicRoute.evidenceRefs[0]", REVIEWER_ID),
    ]
    refs, rows = [], []
    for kind, claim_path, reviewer_id in claims:
        ref, row = _ref(kind, candidate_digest, claim_path, reviewer_id=reviewer_id)
        row._claim_path = claim_path
        refs.append(ref)
        rows.append(row)
    packet = {
        "schema": "puzzle-v2-publication-review-v1",
        "reviewId": "synthetic-review",
        "candidateDigest": candidate_digest,
        "createdAt": "2026-09-26",
        "sourceAttestations": [{
            "sourceId": "synthetic-source",
            "artifactSha256": rows[0].sha256,
            "spdx": "CC0-1.0",
            "decision": "approved",
            "reviewerId": REVIEWER_ID,
            "reviewedAt": "2026-09-26",
            "evidenceRefs": refs[0:2],
        }],
        "clueAdjudications": [
            {
                "clueVariantId": "synthetic-clue@1a",
                "semanticDecision": "pass",
                "editorialDecision": "pass",
                "reviewerId": REVIEWER_ID,
                "reviewedAt": "2026-09-26",
                "evidenceRefs": refs[2:4],
                "challenger": {
                    "methodId": "synthetic-challenger",
                    "methodVersion": "1",
                    "independentOfGenerator": True,
                    "answerHiddenDuringChallenge": True,
                    "decision": "no-unresolved-alternative",
                    "evidenceRefs": refs[4:5],
                },
            }
        ],
        "crossingReview": {
            "candidateDigest": candidate_digest,
            "evaluatorId": "synthetic-crossing-evaluator",
            "evaluatorVersion": "1",
            "allEntriesReviewed": True,
            "unresolvedDualObscurityCells": 0,
            "certificates": [
                {
                    "targetEntryId": "1a",
                    "supportLayer": 0,
                    "targetClass": "ordinary",
                    "routeOutcome": "retrieval",
                    "targetExcludedFromSupportSearch": True,
                    "supportAssignments": [],
                    "unresolvedDualObscurityCells": 0,
                    "reviewerId": REVIEWER_ID,
                    "reviewedAt": "2026-09-26",
                    "evidenceRefs": refs[5:6],
                    "topologyConstraint": {
                        "rationale": "Synthetic topology fixture.",
                        "evidenceRefs": refs[6:7],
                    },
                }
            ],
            "simulation": {
                "simulatorId": "synthetic-simulator",
                "simulatorVersion": "1",
                "policyId": "synthetic-policy",
                "policyVersion": "1",
                "seed": "synthetic-seed",
                "trajectoryCount": 64,
                "completionRate": 0.5,
                "maxNonAnswerNudges": 4,
                "directAnswerReveals": 0,
                "decision": "pass",
                "evidenceRefs": refs[7:8],
            },
        },
        "weekdayReview": {
            "candidateDigest": candidate_digest,
            "recipeId": "synthetic-recipe",
            "recipeVersion": "1",
            "weekday": "Wednesday",
            "decision": "pass",
            "ordinaryFootholdEntryIds": ["1a"],
            "reviewerId": REVIEWER_ID,
            "reviewedAt": "2026-09-26",
            "evidenceRefs": refs[8:9],
            "blindClassifications": [
                {
                    "reviewerId": "synthetic-blind-rater-1",
                    "classifiedWeekday": "Wednesday",
                    "rationale": refs[9],
                },
                {
                    "reviewerId": "synthetic-blind-rater-2",
                    "classifiedWeekday": "Wednesday",
                    "rationale": refs[10],
                },
            ],
            "mechanicRoute": {
                "mechanicId": "synthetic-mechanic",
                "affectedEntryIds": ["1a", "1d"],
                "independentRouteCount": 2,
                "discoverable": True,
                "evidenceRefs": refs[11:12],
            },
        },
        "packetDigest": "0" * 64,
    }
    return packet, rows, refs


def _store_rows(api, rows):
    with api.app.app_context():
        api.db.session.add_all(rows)
        api.db.session.add_all(
            [
                PublicationEvidenceArtifactClaim(
                    artifact_id=row.artifact_id,
                    claim_path=row._claim_path,
                )
                for row in rows
            ]
        )
        api.db.session.commit()


def test_upload_authenticates_host_reviewer_ignores_caller_identity_and_persists(
    api, candidate, reviewer_config
):
    body = b"synthetic review evidence bytes"
    client = api.app.test_client()
    response = client.post(
        "/api/future/evidence/v2/artifacts?reviewerId=caller-controlled&profileId=ignored",
        data=body,
        headers=_headers(candidate, "clue-semantic-review"),
    )

    assert response.status_code == 201, response.json
    assert response.cache_control.no_store
    assert set(response.json) == {"artifact", "ref"}
    artifact = response.json["artifact"]
    assert artifact["sha256"] == hashlib.sha256(body).hexdigest()
    assert artifact["candidateDigest"] == candidate
    assert artifact["claimPath"] == _DEFAULT_CLAIM_PATHS["clue-semantic-review"]
    assert artifact["reviewerId"] == REVIEWER_ID
    assert artifact["kind"] == "clue-semantic-review"
    assert artifact["mediaType"] == "application/pdf"
    assert response.json["ref"] == {
        "artifactId": artifact["artifactId"],
        "sha256": artifact["sha256"],
        "kind": artifact["kind"],
    }
    assert UUID(artifact["artifactId"])
    assert body.decode() not in response.get_data(as_text=True)

    with api.app.app_context():
        saved = api.db.session.get(PublicationEvidenceArtifact, artifact["artifactId"])
        assert saved is not None
        assert saved.artifact_bytes == body
        assert saved.candidate_digest == candidate
        assert saved.reviewer_id == REVIEWER_ID
        claim = api.db.session.get(
            PublicationEvidenceArtifactClaim, artifact["artifactId"]
        )
        assert claim is not None
        assert claim.claim_path == artifact["claimPath"]
        api.db.session.remove()
        api.db.engine.dispose()
    with api.app.app_context():
        persisted = api.db.session.get(PublicationEvidenceArtifact, artifact["artifactId"])
        assert persisted is not None and persisted.artifact_bytes == body


def test_upload_requires_auth_and_fails_closed_when_host_config_is_missing(
    api, candidate
):
    client = api.app.test_client()
    api.app.config["CROSSWORD_REVIEWER_TOKEN"] = TOKEN
    api.app.config["CROSSWORD_REVIEWER_ID"] = REVIEWER_ID
    unauthenticated = client.post(
        "/api/future/evidence/v2/artifacts",
        data=b"evidence",
        headers=_headers(candidate, token=None),
    )
    assert unauthenticated.status_code == 401
    assert unauthenticated.cache_control.no_store
    assert unauthenticated.headers["WWW-Authenticate"] == "Bearer"

    api.app.config["CROSSWORD_REVIEWER_TOKEN"] = None
    unavailable = client.post(
        "/api/future/evidence/v2/artifacts",
        data=b"evidence",
        headers=_headers(candidate),
    )
    assert unavailable.status_code == 503
    assert unavailable.cache_control.no_store
    assert TOKEN not in unavailable.get_data(as_text=True)


@pytest.mark.parametrize(
    ("digest", "kind", "body", "expected_status"),
    [
        ("sha256:" + "A" * 64, "source-artifact", b"x", 400),
        ("not-a-digest", "source-artifact", b"x", 400),
        ("sha256:" + "0" * 64, "source-artifact", b"x", 404),
        ("sha256:" + "0" * 64, "invented-kind", b"x", 400),
        ("sha256:" + "0" * 64, "source-artifact", b"", 411),
    ],
)
def test_upload_rejects_invalid_digest_kind_and_missing_candidate(
    api, reviewer_config, digest, kind, body, expected_status
):
    response = api.app.test_client().post(
        "/api/future/evidence/v2/artifacts",
        data=body,
        headers=_headers(digest, kind),
    )
    assert response.status_code == expected_status
    assert response.cache_control.no_store


def test_upload_caps_body_before_persisting(api, candidate, reviewer_config, monkeypatch):
    import src.crossword.publication_evidence as evidence_module

    monkeypatch.setattr(evidence_module, "MAX_PUBLICATION_EVIDENCE_BYTES", 4)
    response = api.app.test_client().post(
        "/api/future/evidence/v2/artifacts",
        data=b"12345",
        headers=_headers(candidate),
    )
    assert response.status_code == 413
    assert response.cache_control.no_store
    with api.app.app_context():
        assert api.db.session.query(PublicationEvidenceArtifact).count() == 0


def test_upload_enforces_aggregate_capacity_and_returns_stable_error(
    api, candidate, reviewer_config, monkeypatch
):
    import src.crossword.publication_evidence as evidence_module

    monkeypatch.setattr(evidence_module, "MAX_TOTAL_PUBLICATION_EVIDENCE_BYTES", 10)
    client = api.app.test_client()
    first = client.post(
        "/api/future/evidence/v2/artifacts",
        data=b"123456",
        headers=_headers(candidate),
    )
    over_capacity = client.post(
        "/api/future/evidence/v2/artifacts",
        data=b"abcde",
        headers=_headers(candidate, "license-terms-review"),
    )

    assert first.status_code == 201, first.json
    assert over_capacity.status_code == 507
    assert over_capacity.json == {
        "error": "Publication evidence storage capacity reached"
    }
    assert over_capacity.cache_control.no_store
    with api.app.app_context():
        assert api.db.session.query(PublicationEvidenceArtifact).count() == 1
        quota = api.db.session.get(PublicationEvidenceStorageQuota, 1)
        assert quota is not None and quota.bytes_used == 6


def test_quota_initialization_counts_immutable_artifacts_already_on_disk(
    api, candidate, reviewer_config, monkeypatch
):
    import src.crossword.publication_evidence as evidence_module

    monkeypatch.setattr(evidence_module, "MAX_TOTAL_PUBLICATION_EVIDENCE_BYTES", 10)
    legacy_ref, legacy_row = _ref(
        "source-artifact",
        candidate,
        _DEFAULT_CLAIM_PATHS["source-artifact"],
        body=b"legacy",
    )
    legacy_row._claim_path = _DEFAULT_CLAIM_PATHS["source-artifact"]
    _store_rows(api, [legacy_row])

    response = api.app.test_client().post(
        "/api/future/evidence/v2/artifacts",
        data=b"12345",
        headers=_headers(candidate, "license-terms-review"),
    )

    assert legacy_ref["sha256"] == hashlib.sha256(b"legacy").hexdigest()
    assert response.status_code == 507
    with api.app.app_context():
        assert api.db.session.query(PublicationEvidenceArtifact).count() == 1
        quota = api.db.session.get(PublicationEvidenceStorageQuota, 1)
        assert quota is not None and quota.bytes_used == len(b"legacy")


def test_concurrent_upload_reservations_cannot_overcommit_aggregate_capacity(
    api, candidate, reviewer_config, monkeypatch
):
    import src.crossword.publication_evidence as evidence_module

    monkeypatch.setattr(evidence_module, "MAX_TOTAL_PUBLICATION_EVIDENCE_BYTES", 10)
    # Seed the singleton so this specifically exercises simultaneous atomic
    # conditional UPDATEs instead of first-request initialization.
    with api.app.app_context():
        api.db.session.add(PublicationEvidenceStorageQuota(id=1, bytes_used=0))
        api.db.session.commit()

    original_store = evidence_module._store_artifact_with_quota
    reservation_barrier = Barrier(2)

    def synchronize_before_reservation(record, claim):
        reservation_barrier.wait(timeout=5)
        return original_store(record, claim)

    monkeypatch.setattr(
        evidence_module, "_store_artifact_with_quota", synchronize_before_reservation
    )

    def upload(body, kind):
        return api.app.test_client().post(
            "/api/future/evidence/v2/artifacts",
            data=body,
            headers=_headers(candidate, kind),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda args: upload(*args),
                [(b"123456", "source-artifact"), (b"abcdef", "license-terms-review")],
            )
        )

    assert sorted(response.status_code for response in results) == [201, 507]
    rejected = next(response for response in results if response.status_code == 507)
    assert rejected.json == {"error": "Publication evidence storage capacity reached"}
    with api.app.app_context():
        assert api.db.session.query(PublicationEvidenceArtifact).count() == 1
        quota = api.db.session.get(PublicationEvidenceStorageQuota, 1)
        assert quota is not None and quota.bytes_used == 6


@pytest.mark.parametrize(
    "claim_path",
    [
        "",
        "sourceAttestations.evidenceRefs[0]",
        "sourceAttestations[00].evidenceRefs[0]",
        "sourceAttestations[4096].evidenceRefs[0]",
        "sourceAttestations[0].evidenceRefs[4096]",
        "sourceAttestations[0].evidenceRefs[0].extra",
        "../sourceAttestations[0].evidenceRefs[0]",
        "x" * (MAX_EVIDENCE_CLAIM_PATH_LENGTH + 1),
    ],
)
def test_upload_rejects_invalid_or_unbounded_claim_path(
    api, candidate, reviewer_config, claim_path
):
    response = api.app.test_client().post(
        "/api/future/evidence/v2/artifacts",
        data=b"evidence",
        headers=_headers(candidate, claim_path=claim_path),
    )

    assert response.status_code == 400
    assert response.cache_control.no_store
    with api.app.app_context():
        assert api.db.session.query(PublicationEvidenceArtifact).count() == 0


def test_upload_requires_claim_path_header(api, candidate, reviewer_config):
    headers = _headers(candidate)
    headers.pop("X-Evidence-Claim-Path")

    response = api.app.test_client().post(
        "/api/future/evidence/v2/artifacts", data=b"evidence", headers=headers
    )

    assert response.status_code == 400
    assert response.cache_control.no_store
    with api.app.app_context():
        assert api.db.session.query(PublicationEvidenceArtifact).count() == 0


def test_upload_rejects_kind_not_allowed_at_claim_path(api, candidate, reviewer_config):
    response = api.app.test_client().post(
        "/api/future/evidence/v2/artifacts",
        data=b"evidence",
        headers=_headers(
            candidate,
            "challenger-run",
            claim_path="sourceAttestations[0].evidenceRefs[0]",
        ),
    )

    assert response.status_code == 400
    assert response.cache_control.no_store
    with api.app.app_context():
        assert api.db.session.query(PublicationEvidenceArtifact).count() == 0


@pytest.mark.parametrize(
    ("kind", "claim_path"),
    [
        ("source-artifact", "sourceAttestations[0].evidenceRefs[0]"),
        ("clue-semantic-review", "clueAdjudications[0].evidenceRefs[0]"),
        (
            "challenger-run",
            "clueAdjudications[0].challenger.evidenceRefs[0]",
        ),
        (
            "crossing-certificate",
            "crossingReview.certificates[0].evidenceRefs[0]",
        ),
        (
            "crossing-certificate",
            "crossingReview.certificates[0].topologyConstraint.evidenceRefs[0]",
        ),
        ("solve-simulation", "crossingReview.simulation.evidenceRefs[0]"),
        ("weekday-review", "weekdayReview.evidenceRefs[0]"),
        (
            "weekday-review",
            "weekdayReview.blindClassifications[0].rationale",
        ),
        ("mechanic-route", "weekdayReview.mechanicRoute.evidenceRefs[0]"),
    ],
)
def test_upload_accepts_each_supported_claim_path_form(
    api, candidate, reviewer_config, kind, claim_path
):
    response = api.app.test_client().post(
        "/api/future/evidence/v2/artifacts",
        data=b"evidence",
        headers=_headers(candidate, kind, claim_path=claim_path),
    )

    assert response.status_code == 201, response.json
    assert response.json["artifact"]["claimPath"] == claim_path


def test_resolver_walks_every_packet_evidence_location(api, candidate):
    packet, rows, refs = _review_packet(candidate)
    _store_rows(api, rows)

    with api.app.app_context():
        resolved = resolve_publication_packet_evidence(packet, candidate)

    assert len(resolved) == 12
    assert [row.artifact_id for row in resolved] == [ref["artifactId"] for ref in refs]
    with api.app.app_context():
        claims = {
            claim.artifact_id: claim.claim_path
            for claim in api.db.session.query(PublicationEvidenceArtifactClaim).all()
        }
    assert [claims[row.artifact_id] for row in resolved] == [
        row._claim_path for row in rows
    ]
    assert {row.kind for row in resolved} == {
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


def test_resolver_enforces_reference_budget_before_walking_later_locations(
    api, candidate, monkeypatch
):
    import src.crossword.publication_evidence as evidence_module

    packet, _rows, _refs = _review_packet(candidate)
    monkeypatch.setattr(evidence_module, "MAX_PACKET_EVIDENCE_REFS", 13)
    # The first collection alone exceeds the aggregate budget. A malformed
    # later section makes the assertion distinguish early rejection from the
    # former behavior that only checked the total after collecting everything.
    packet["sourceAttestations"] = [
        {"evidenceRefs": [{}, {}]},
        *({"evidenceRefs": [{}]} for _ in range(12)),
    ]
    packet["crossingReview"]["certificates"] = None

    with pytest.raises(
        PublicationEvidenceRejected, match="packet-reference-invalid:total"
    ):
        evidence_module._collect_refs(packet)


def test_resolver_rejects_packet_over_serialized_size_budget(api, candidate, monkeypatch):
    import src.crossword.publication_evidence as evidence_module

    packet, _rows, _refs = _review_packet(candidate)
    monkeypatch.setattr(
        evidence_module, "MAX_PUBLICATION_REVIEW_PACKET_BYTES", 256
    )
    packet["extension"] = "x" * 257

    with pytest.raises(
        PublicationEvidenceRejected, match="packet-size-limit-exceeded"
    ):
        evidence_module._collect_refs(packet)


@pytest.mark.parametrize("mutation", ["wrong-id", "wrong-kind", "wrong-hash", "extra-key"])
def test_resolver_rejects_wrong_id_kind_hash_and_nonexact_ref_shape(
    api, candidate, mutation
):
    packet, rows, refs = _review_packet(candidate)
    _store_rows(api, rows)
    changed = deepcopy(packet)
    target = changed["sourceAttestations"][0]["evidenceRefs"][0]
    if mutation == "wrong-id":
        target["artifactId"] = str(uuid4())
    elif mutation == "wrong-kind":
        target["kind"] = "license-terms-review"
    elif mutation == "wrong-hash":
        target["sha256"] = "A" * 64
    else:
        target["unexpected"] = "not allowed"

    with api.app.app_context(), pytest.raises(PublicationEvidenceRejected):
        resolve_publication_packet_evidence(changed, candidate)


def test_resolver_rejects_same_candidate_same_kind_artifact_at_wrong_claim_path(
    api, candidate
):
    packet, rows, _refs = _review_packet(candidate)
    _store_rows(api, rows)
    changed = deepcopy(packet)
    certificate_refs = changed["crossingReview"]["certificates"][0]["evidenceRefs"]
    topology_refs = changed["crossingReview"]["certificates"][0]["topologyConstraint"]["evidenceRefs"]
    assert certificate_refs[0]["kind"] == topology_refs[0]["kind"]
    certificate_refs[0], topology_refs[0] = topology_refs[0], certificate_refs[0]

    with api.app.app_context(), pytest.raises(PublicationEvidenceRejected):
        resolve_publication_packet_evidence(changed, candidate)


def test_resolver_rejects_authenticated_actor_mismatch_for_human_claim(api, candidate):
    packet, rows, _refs = _review_packet(candidate)
    _store_rows(api, rows)
    changed = deepcopy(packet)
    changed["sourceAttestations"][0]["reviewerId"] = "different-reviewer"

    with api.app.app_context(), pytest.raises(PublicationEvidenceRejected):
        resolve_publication_packet_evidence(changed, candidate)


def test_resolver_rejects_claim_row_path_tampering(api, candidate):
    packet, rows, _refs = _review_packet(candidate)
    artifact_id = rows[0].artifact_id
    _store_rows(api, rows)
    with api.app.app_context():
        claim = api.db.session.get(
            PublicationEvidenceArtifactClaim, artifact_id
        )
        claim.claim_path = "sourceAttestations[0].evidenceRefs[1]"
        api.db.session.commit()
        with pytest.raises(PublicationEvidenceRejected):
            resolve_publication_packet_evidence(packet, candidate)


def test_resolver_rejects_wrong_candidate_binding_and_candidate_tampering(api, candidate):
    packet, rows, _refs = _review_packet(candidate)
    _store_rows(api, rows)
    wrong_candidate = deepcopy(packet)
    wrong_candidate["candidateDigest"] = "sha256:" + "f" * 64
    with api.app.app_context(), pytest.raises(PublicationEvidenceRejected):
        resolve_publication_packet_evidence(wrong_candidate, candidate)

    with api.app.app_context():
        candidate_record = (
            api.db.session.query(FuturePuzzleV2CandidateRecord).one()
        )
        tampered = dict(candidate_record.manifest_json)
        tampered["title"] = "tampered after staging"
        candidate_record.manifest_json = tampered
        api.db.session.commit()
        with pytest.raises(PublicationEvidenceRejected):
            resolve_publication_packet_evidence(packet, candidate)


def test_candidate_lookup_bounds_duplicate_profile_rows(api, candidate):
    with api.app.app_context():
        original = api.db.session.query(FuturePuzzleV2CandidateRecord).one()
        api.db.session.add_all(
            [
                FuturePuzzleV2CandidateRecord(
                    profile_id=str(uuid4()),
                    candidate_hash=original.candidate_hash,
                    candidate_id=original.candidate_id,
                    job_id=str(uuid4()),
                    manifest_json=original.manifest_json,
                    created_at=original.created_at,
                )
                for _ in range(MAX_CANDIDATE_ROWS_PER_DIGEST)
            ]
        )
        api.db.session.commit()

        packet, _rows, _refs = _review_packet(candidate)
        with pytest.raises(PublicationEvidenceRejected, match="candidate-identity-conflict"):
            resolve_publication_packet_evidence(packet, candidate)


def test_resolver_recomputes_bytes_digest_to_detect_database_tampering(api, candidate):
    packet, rows, _refs = _review_packet(candidate)
    artifact_id = rows[0].artifact_id
    _store_rows(api, rows)
    with api.app.app_context():
        artifact = api.db.session.get(PublicationEvidenceArtifact, artifact_id)
        artifact.artifact_bytes = b"changed behind the resolver"
        api.db.session.commit()
        with pytest.raises(PublicationEvidenceRejected):
            resolve_publication_packet_evidence(packet, candidate)


def test_resolver_rejects_artifact_bound_to_a_different_candidate(api, candidate):
    packet, rows, _refs = _review_packet(candidate)
    rows[0].candidate_digest = "sha256:" + "f" * 64
    _store_rows(api, rows)
    with api.app.app_context(), pytest.raises(PublicationEvidenceRejected):
        resolve_publication_packet_evidence(packet, candidate)


def test_resolver_requires_exact_candidate_digest_and_nested_bindings(api, candidate):
    packet, rows, _refs = _review_packet(candidate)
    _store_rows(api, rows)
    malformed = deepcopy(packet)
    malformed["crossingReview"]["candidateDigest"] = "wrong"
    with api.app.app_context(), pytest.raises(PublicationEvidenceRejected):
        resolve_publication_packet_evidence(malformed, candidate)

    with api.app.app_context(), pytest.raises(PublicationEvidenceRejected):
        resolve_publication_packet_evidence(packet, candidate.upper())


def test_artifact_endpoint_has_no_public_read_or_delete_route(api):
    client = api.app.test_client()
    assert client.get("/api/future/evidence/v2/artifacts").status_code == 405
    assert client.delete("/api/future/evidence/v2/artifacts").status_code == 405
    for method in (client.get, client.put, client.patch, client.delete):
        response = method(
            "/api/future/evidence/v2/artifacts/00000000-0000-0000-0000-000000000001"
        )
        assert response.status_code == 404
        assert not 200 <= response.status_code < 300
