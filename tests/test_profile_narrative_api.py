"""Profile narrative snapshots stay bounded, replayable, and fail open."""

import json
from uuid import uuid4

from tests.test_api_isolated import api, no_network  # noqa: F401
from src.crossword.future import StartingProfile, derive_profile
from src.crossword.profile_narrative_api import (
    ProfileNarrativeRecord,
    ProfileNarrativeRuntimeUnavailable,
    _decode_model_json,
    _source,
)
from src.crossword.episteme_store import get_or_create_episteme_profile


def _profile(api):
    profile_id = str(uuid4())
    draft = {
        "version": 1,
        "id": profile_id,
        "object": "thread",
        "firstStimulus": "thread-knot",
        "companion": "fork",
        "variation": "keep-original",
        "traces": ["echo"],
        "weekday": "wednesday",
        "learningLanguage": "None for now",
        "excluded": [],
        "complete": True,
        "step": 5,
        "presentationMode": "visual",
        "calibrationId": str(uuid4()),
    }
    with api.app.app_context():
        api.db.session.add(
            StartingProfile(
                id=profile_id,
                draft=draft,
                profile=derive_profile(draft),
                updated_at="2026-09-28T00:00:00Z",
            )
        )
        api.db.session.commit()
    return profile_id


def test_profile_narrative_is_generated_once_and_replayed(api, monkeypatch):
    profile_id = _profile(api)
    narrative = {
        "version": "private-profile-narrative-v1",
        "paragraphs": [{"text": "A field of echoes remains open.", "evidenceIds": ["starting-profile"]}],
        "openQuestions": [{"text": "What crosses next?", "evidenceIds": []}],
    }
    monkeypatch.setattr(
        "src.crossword.profile_narrative_api._generate",
        lambda source: (narrative, {"provider": "test", "format": "private-profile-narrative-v1", "digest": "sha256:" + "a" * 64}),
    )
    client = api.app.test_client()
    url = f"/api/future/profile/{profile_id}/narrative"
    first = client.post(url, json={}, headers={"Origin": "http://localhost"})
    assert first.status_code == 200, first.json
    assert first.json["status"] == "ready"
    assert first.json["narrative"] == narrative
    second = client.post(url, json={}, headers={"Origin": "http://localhost"})
    assert second.status_code == 200
    assert second.json["replayed"] is True
    rebuild_id = str(uuid4())
    rebuilt = client.post(url, json={"requestId": rebuild_id}, headers={"Origin": "http://localhost"})
    assert rebuilt.status_code == 200
    assert rebuilt.json["replayed"] is False
    assert rebuilt.json["receipt"]["generation"]["rebuild"] is True
    retried = client.post(url, json={"requestId": rebuild_id}, headers={"Origin": "http://localhost"})
    assert retried.status_code == 200
    assert retried.json["replayed"] is True
    loaded = client.get(url)
    assert loaded.status_code == 200
    assert loaded.json["narrative"] == narrative
    with api.app.app_context():
        assert api.db.session.query(ProfileNarrativeRecord).count() == 2


def test_profile_narrative_accepts_markdown_wrapped_json_without_accepting_prose():
    assert _decode_model_json("```json\n{\"paragraphs\": [], \"openQuestions\": []}\n```") == {
        "paragraphs": [],
        "openQuestions": [],
    }


def test_profile_narrative_source_carries_saved_model_preference():
    class Starting:
        id = "profile-1"
        draft = {"modelPreference": "gemma4:26b"}
        profile = {"prose": "", "associations": []}

    class Episteme:
        revision = 4

    source = _source(Starting(), Episteme(), {"claims": [], "associations": [], "knowledge": []})
    assert source["opening"]["modelPreference"] == "gemma4:26b"


def test_profile_narrative_model_failure_is_available_without_mutating_episteme(api, monkeypatch):
    profile_id = _profile(api)
    monkeypatch.setattr(
        "src.crossword.profile_narrative_api._generate",
        lambda source: (_ for _ in ()).throw(ProfileNarrativeRuntimeUnavailable("offline")),
    )
    response = api.app.test_client().post(
        f"/api/future/profile/{profile_id}/narrative",
        json={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    assert response.json["status"] == "unavailable"
    assert response.json["narrative"] is None


def test_profile_narrative_becomes_stale_and_rejects_acceptance_after_revision_change(api, monkeypatch):
    profile_id = _profile(api)
    narrative = {
        "version": "private-profile-narrative-v1",
        "paragraphs": [{"text": "A reversible field note.", "evidenceIds": ["starting-profile"]}],
        "openQuestions": [],
        "suggestions": [{
            "conceptId": "association:en:acoustic",
            "label": "acoustic",
            "kind": "taste",
            "action": "seek",
            "rationale": "The saved field leaves a sound-adjacent path open.",
            "evidenceIds": ["starting-profile"],
        }],
    }
    monkeypatch.setattr(
        "src.crossword.profile_narrative_api._generate",
        lambda source: (narrative, {"provider": "test", "format": "private-profile-narrative-v1", "digest": "sha256:" + "d" * 64}),
    )
    client = api.app.test_client()
    base = f"/api/future/profile/{profile_id}"
    created = client.post(f"{base}/narrative", json={}, headers={"Origin": "http://localhost"})
    assert created.status_code == 200, created.json
    receipt = created.json["receipt"]
    update = {
        "expectedRevision": receipt["epistemeRevision"],
        "updateId": str(uuid4()),
        "recordedAt": "2026-09-28T00:00:01.000Z",
        "evidence": [{
            "evidenceId": str(uuid4()),
            "recordedAt": "2026-09-28T00:00:01.000Z",
            "type": "explicit-preference",
            "concept": {"conceptId": "acoustic", "label": "acoustic", "language": "en"},
            "kind": "taste",
            "action": "seek",
            "scope": {"mode": "field-note-test", "language": "en"},
            "supersedesEvidenceIds": [],
            "userText": "Keep a little more sound-adjacent material",
        }],
        "evidenceActions": [],
    }
    changed = client.post(f"{base}/episteme/updates", json=update)
    assert changed.status_code == 200, changed.json
    loaded = client.get(f"{base}/narrative")
    assert loaded.status_code == 200
    assert loaded.json["stale"] is True
    rejected = client.post(
        f"{base}/narrative/{receipt['narrativeId']}/suggestions/0/accept",
        json={"expectedRevision": changed.json["revision"], "updateId": str(uuid4())},
        headers={"Origin": "http://localhost"},
    )
    assert rejected.status_code == 409


def test_profile_narrative_suggestion_requires_player_acceptance_and_is_replayable(api):
    profile_id = _profile(api)
    narrative_id = str(uuid4())
    narrative = {
        "version": "private-profile-narrative-v1",
        "paragraphs": [{"text": "A narrow path is visible.", "evidenceIds": ["starting-profile"]}],
        "openQuestions": [],
        "suggestions": [{
            "conceptId": "association:en:acoustic",
            "label": "acoustic",
            "kind": "taste",
            "action": "seek",
            "rationale": "The saved field leaves a sound-adjacent path open.",
            "evidenceIds": ["starting-profile"],
        }],
    }
    with api.app.app_context():
        episteme = get_or_create_episteme_profile(profile_id, "2026-09-28T00:00:00Z")
        api.db.session.add(ProfileNarrativeRecord(
            id=narrative_id,
            profile_id=profile_id,
            episteme_revision=episteme.revision,
            source_digest="c" * 64,
            narrative_json=narrative,
            generation_metadata={"provider": "test"},
            status="ready",
            created_at="2026-09-28T00:00:00Z",
            updated_at="2026-09-28T00:00:00Z",
        ))
        api.db.session.commit()
        revision = episteme.revision
    client = api.app.test_client()
    url = f"/api/future/profile/{profile_id}/narrative/{narrative_id}/suggestions/0/accept"
    first = client.post(url, json={"expectedRevision": revision, "updateId": str(uuid4())}, headers={"Origin": "http://localhost"})
    assert first.status_code == 200, first.json
    assert first.json["replayed"] is False
    replay = client.post(url, json={"expectedRevision": first.json["revision"], "updateId": str(uuid4())}, headers={"Origin": "http://localhost"})
    assert replay.status_code == 200
    assert replay.json["replayed"] is True


def test_profile_narrative_round_trips_through_archive_and_deletion(api, monkeypatch):
    profile_id = _profile(api)
    narrative = {
        "version": "private-profile-narrative-v1",
        "paragraphs": [{"text": "A reversible field note.", "evidenceIds": ["starting-profile"]}],
        "openQuestions": [],
    }
    monkeypatch.setattr(
        "src.crossword.profile_narrative_api._generate",
        lambda source: (narrative, {"provider": "test", "format": "private-profile-narrative-v1", "digest": "sha256:" + "b" * 64}),
    )
    client = api.app.test_client()
    base = f"/api/future/profile/{profile_id}"
    assert client.post(f"{base}/narrative", json={}, headers={"Origin": "http://localhost"}).status_code == 200
    archive = client.get(f"{base}/export").get_json()
    assert archive["profileNarratives"][0]["narrative"] == narrative
    assert client.delete(base).status_code == 200
    restored = client.post(
        f"{base}/import",
        data=json.dumps(archive),
        content_type="application/json",
        headers={"Origin": "http://localhost"},
    )
    assert restored.status_code == 201, restored.json
    with api.app.app_context():
        assert api.db.session.query(ProfileNarrativeRecord).filter_by(profile_id=profile_id).count() == 1
