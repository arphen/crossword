"""Postgame local-model association paths are bounded and replayable."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from tests.test_api_isolated import api, no_network  # noqa: F401
from tests.test_session_journal import registered_manifest
from src.crossword.episteme_store import EpistemeProfileRecord, get_or_create_episteme_profile
from src.crossword.future_puzzles import FutureSolveAnalysisRecord
from src.crossword.postgame_associations_api import PostgameAssociationRunRecord, _diversity_receipt, _generate_paths
from src.crossword.postgame_associations_api import PostgameAssociationRuntimeUnavailable
from src.crossword.session_journal import PersonalSolveSession


def _finished(api):
    profile_id = str(uuid4())
    session_id = str(uuid4())
    with api.app.app_context():
        manifest = registered_manifest(api)
        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        get_or_create_episteme_profile(profile_id, now)
        api.db.session.add(
            PersonalSolveSession(
                id=session_id,
                profile_id=profile_id,
                puzzle_hash=manifest["integrity"]["value"],
                initial_grid=[],
                writer_digest="a" * 64,
                accepted_seq=3,
                status="finished",
                created_at=now,
                updated_at=now,
            )
        )
        api.db.session.add(
            FutureSolveAnalysisRecord(
                session_id=session_id,
                puzzle_hash=manifest["integrity"]["value"],
                analysis_version="knowledge-reducer-v1",
                analysis_json={
                    "analysisVersion": "knowledge-reducer-v1",
                    "entryCount": 6,
                    "observations": [],
                },
                finalized=True,
                updated_at=now,
            )
        )
        api.db.session.commit()
    return profile_id, session_id, manifest


def test_postgame_paths_are_generated_once_and_responses_become_evidence(api, monkeypatch):
    profile_id, session_id, manifest = _finished(api)
    entry_id = manifest["entries"][0]["id"]
    monkeypatch.setattr(
        "src.crossword.postgame_associations_api._generate_paths",
        lambda source, seed_ids, language: (
            [
                {
                    "phrase": "river clock",
                    "language": "en",
                    "relation": "metaphor",
                    "parentConceptIds": [f"puzzle-entry:{entry_id}"],
                    "explanation": "A possible meeting of movement and measure.",
                }
            ],
            {"provider": "test", "digest": "sha256:" + "a" * 64},
        ),
    )
    client = api.app.test_client()
    url = f"/api/future/sessions/{session_id}/episteme-associations"
    first = client.post(url, json={"requestId": str(uuid4())}, headers={"Origin": "http://localhost"})
    assert first.status_code == 200, first.json
    assert first.json["status"] == "generated"
    assert len(first.json["paths"]) == 1
    second = client.post(url, json={"requestId": str(uuid4())}, headers={"Origin": "http://localhost"})
    assert second.status_code == 200
    assert second.json["status"] == "replayed"
    assert second.json["paths"] == first.json["paths"]

    path = first.json["paths"][0]
    response_url = f"{url}/{path['associationId']}/response"
    response_id = str(uuid4())
    saved = client.post(
        response_url,
        json={"responseId": response_id, "response": "keep"},
        headers={"Origin": "http://localhost"},
    )
    assert saved.status_code == 200, saved.json
    retry = client.post(
        response_url,
        json={"responseId": response_id, "response": "keep"},
        headers={"Origin": "http://localhost"},
    )
    assert retry.status_code == 200
    assert retry.json["replayed"] is True
    expanded = client.post(
        f"{url}/{path['associationId']}/expand",
        json={"requestId": str(uuid4())},
        headers={"Origin": "http://localhost"},
    )
    assert expanded.status_code == 200, expanded.json
    assert expanded.json["status"] == "expanded"
    assert expanded.json["expansions"][path["associationId"]][0]["depth"] == 1
    replayed_expansion = client.post(
        f"{url}/{path['associationId']}/expand",
        json={"requestId": str(uuid4())},
        headers={"Origin": "http://localhost"},
    )
    assert replayed_expansion.status_code == 200
    assert replayed_expansion.json["replayed"] is True
    with api.app.app_context():
        profile = api.db.session.get(EpistemeProfileRecord, profile_id)
        proposals = [item for item in profile.profile_json["evidence"] if item["type"] == "association-proposal"]
        responses = [item for item in profile.profile_json["evidence"] if item["type"] == "association-response"]
        assert len(proposals) == 2
        assert len(responses) == 1
        assert responses[0]["proposalEvidenceId"] in {
            item["evidenceId"] for item in proposals
        }
        assert api.db.session.query(PostgameAssociationRunRecord).count() == 1


def test_postgame_diversity_receipt_is_deterministic_and_non_psychometric():
    receipt = _diversity_receipt([
        {"relation": "sound", "parentConceptIds": ["a"]},
        {"relation": "metaphor", "parentConceptIds": ["a", "b"]},
        {"relation": "etymology", "parentConceptIds": ["c"]},
    ])
    assert receipt == {
        "format": "postgame-association-diversity-v1",
        "pathCount": 3,
        "uniqueRelations": 3,
        "uniqueParents": 3,
        "relationCounts": {"etymology": 1, "metaphor": 1, "sound": 1},
        "maxRelationCount": 1,
        "maxParentCount": 2,
        "status": "varied",
    }



def test_postgame_model_failure_is_fail_open(api, monkeypatch):
    _, session_id, _ = _finished(api)
    monkeypatch.setattr(
        "src.crossword.postgame_associations_api._generate_paths",
        lambda source, seed_ids, language: (_ for _ in ()).throw(
            PostgameAssociationRuntimeUnavailable("model offline")
        ),
    )
    response = api.app.test_client().post(
        f"/api/future/sessions/{session_id}/episteme-associations",
        json={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    assert response.json["status"] == "unavailable"
    with api.app.app_context():
        record = api.db.session.get(PostgameAssociationRunRecord, session_id)
        assert record.status == "unavailable"


def test_postgame_network_denial_is_normalized_to_unavailable(api):
    with pytest.raises(PostgameAssociationRuntimeUnavailable, match="unavailable"):
        _generate_paths(
            {"entries": [], "profileConcepts": []},
            {"association:en:example"},
            "en",
        )
