"""Synthetic-only storage/read boundary tests for personalized V2 candidates."""

from __future__ import annotations

import json
from uuid import uuid4

from tests.test_api_isolated import api, no_network  # noqa: F401
from sqlalchemy.exc import SQLAlchemyError
from tests.test_future_grid_jobs import (
    _complete_synthetic_review_pack,
    _complete_synthetic_runtime_result,
    _add_episteme_control,
    _create_profile,
    _job_body,
    _personalized_profile_payload,
)
from src.crossword.future_grid_jobs import process_next_grid_draft
from src.crossword.future_puzzles import (
    FuturePuzzleManifestRecord,
    FuturePuzzleV2CandidateRecord,
)
from src.crossword.future_grid_jobs import FutureGridDraftPrivateSelection
import src.crossword.future_grid_jobs as grid_jobs_module


def _ready_candidate(api, monkeypatch):
    pack = _complete_synthetic_review_pack()
    monkeypatch.setattr(grid_jobs_module, "_load_pinned_pack", lambda: pack)
    client = api.app.test_client()
    profile = _personalized_profile_payload()
    _create_profile(client, profile)
    _add_episteme_control(client, profile["id"], "topic:synthetic", action="seek")
    created = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(profile["id"]),
    )
    assert created.status_code == 202, created.json

    def runtime(**kwargs):
        return _complete_synthetic_runtime_result(
            kwargs["seed"], kwargs["options"], kwargs["admitted_wordlist"]
        )

    assert process_next_grid_draft(api.app, generator=runtime)
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.json["state"] == "ready"
    assert "manifestCandidate" in saved.json["result"]["personalization"]
    manifest = saved.json["result"]["personalization"]["manifestCandidate"]["manifest"]
    return client, profile, created.json["id"], manifest


def test_v2_candidate_read_returns_valid_review_document_without_playable_claim(api, monkeypatch):
    client, profile, job_id, manifest = _ready_candidate(api, monkeypatch)
    candidate_hash = manifest["integrity"]["value"].removeprefix("sha256:")

    response = client.get(
        f"/api/future/puzzle-candidates/v2/{candidate_hash}",
        query_string={"profileId": profile["id"]},
    )

    assert response.status_code == 200, response.json
    assert response.cache_control.no_store
    assert response.json["status"] == "review"
    assert response.json["playable"] is False
    assert response.json["candidateId"] == manifest["id"]
    assert response.json["manifest"] == manifest
    with api.app.app_context():
        candidate = api.db.session.get(
            FuturePuzzleV2CandidateRecord,
            (profile["id"], candidate_hash),
        )
        assert candidate is not None
        assert candidate.job_id == job_id
        assert api.db.session.query(FuturePuzzleManifestRecord).count() == 0


def test_v2_candidate_read_revalidates_stored_digest_and_fails_closed(api, monkeypatch):
    client, profile, _job_id, manifest = _ready_candidate(api, monkeypatch)
    candidate_hash = manifest["integrity"]["value"].removeprefix("sha256:")
    with api.app.app_context():
        candidate = api.db.session.get(
            FuturePuzzleV2CandidateRecord,
            (profile["id"], candidate_hash),
        )
        changed = dict(candidate.manifest_json)
        changed["title"] = "Tampered after candidate admission"
        candidate.manifest_json = changed
        api.db.session.commit()

    response = client.get(
        f"/api/future/puzzle-candidates/v2/{candidate_hash}",
        query_string={"profileId": profile["id"]},
    )

    assert response.status_code == 503
    assert response.cache_control.no_store
    assert response.json["playable"] is False
    assert response.json["error"] == "Puzzle candidate failed integrity validation"


def test_candidate_storage_failure_keeps_the_answer_grid_ready_without_sidecar(api, monkeypatch):
    pack = _complete_synthetic_review_pack()
    monkeypatch.setattr(grid_jobs_module, "_load_pinned_pack", lambda: pack)

    def reject_storage(**_kwargs):
        raise SQLAlchemyError("synthetic storage unavailable")

    monkeypatch.setattr(grid_jobs_module, "stage_personalized_v2_review_candidate", reject_storage)
    client = api.app.test_client()
    profile = _personalized_profile_payload()
    _create_profile(client, profile)
    created = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(profile["id"]),
    )
    assert created.status_code == 202, created.json

    def runtime(**kwargs):
        return _complete_synthetic_runtime_result(
            kwargs["seed"], kwargs["options"], kwargs["admitted_wordlist"]
        )

    assert process_next_grid_draft(api.app, generator=runtime)
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.json["state"] == "ready"
    assert saved.json["playable"] is False
    assert saved.json["result"]["grid"]["fill"]
    assert "manifestCandidate" not in saved.json["result"]["personalization"]
    assert saved.json["result"]["personalization"]["manifestCandidateRejectionCode"] == (
        "manifest-candidate-storage-failed"
    )
    with api.app.app_context():
        assert api.db.session.query(FuturePuzzleV2CandidateRecord).count() == 0
        assert api.db.session.get(FutureGridDraftPrivateSelection, created.json["id"]) is None


def test_v2_candidate_read_is_profile_scoped_and_never_reads_private_sidecar(api, monkeypatch):
    client, profile, job_id, manifest = _ready_candidate(api, monkeypatch)
    candidate_hash = manifest["integrity"]["value"].removeprefix("sha256:")
    wrong_profile = str(uuid4())

    isolated = client.get(
        f"/api/future/puzzle-candidates/v2/{candidate_hash}",
        query_string={"profileId": wrong_profile},
    )
    assert isolated.status_code == 404
    assert isolated.cache_control.no_store

    owner = client.get(
        f"/api/future/puzzle-candidates/v2/{candidate_hash}",
        query_string={"profileId": profile["id"]},
    )
    assert owner.status_code == 200
    with api.app.app_context():
        from src.crossword.future_grid_jobs import FutureGridDraftPrivateSelection

        sidecar = api.db.session.get(FutureGridDraftPrivateSelection, job_id)
        assert sidecar is not None
        private_evidence_ids = {
            evidence_id
            for row in sidecar.selection_json
            for evidence_id in row["profileEvidenceIds"]
        }
    serialized_public_document = json.dumps(owner.json, ensure_ascii=False, sort_keys=True)
    assert all(evidence_id not in serialized_public_document for evidence_id in private_evidence_ids)
    assert "privateSelection" not in owner.json
    assert "selectionLog" not in owner.json


def test_v2_candidates_are_not_registered_in_v1_or_accepted_by_v1_session_creation(api, monkeypatch):
    client, profile, _job_id, manifest = _ready_candidate(api, monkeypatch)
    candidate_hash = manifest["integrity"]["value"].removeprefix("sha256:")
    initial_grid = [
        {"cellId": cell["id"], "token": None, "origin": "unknown"}
        for cell in manifest["cells"]
        if not cell["block"]
    ]

    response = client.post(
        "/api/future/sessions",
        json={
            "sessionId": str(uuid4()),
            "profileId": profile["id"],
            "puzzleHash": candidate_hash,
            "initialGrid": initial_grid,
            "writerToken": "synthetic-writer-token-that-is-long-enough",
        },
    )

    assert response.status_code == 422
    assert response.json["error"] == "Puzzle manifest is not registered on this host"
    assert response.cache_control.no_store
    with api.app.app_context():
        assert api.db.session.query(FuturePuzzleManifestRecord).count() == 0
