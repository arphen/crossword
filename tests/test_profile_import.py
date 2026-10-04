"""Profile archives can be restored without overwriting local data."""

import json
from uuid import uuid4

from tests.test_api_isolated import api, no_network  # noqa: F401
from src.crossword.calibration_api import CalibrationSessionRecord
from src.crossword.database import db
from src.crossword.episteme_store import EpistemeProfileRecord
from src.crossword.future import StartingProfile
from src.crossword.profile_export import archive_integrity_digest
from src.crossword.session_journal import PersonalSolveSession


def _draft(profile_id):
    return {
        "version": 1,
        "id": profile_id,
        "calibrationId": str(uuid4()),
        "step": 0,
        "object": None,
        "firstStimulus": None,
        "companion": None,
        "variation": None,
        "presentationMode": "visual",
        "traces": [],
        "weekday": "wednesday",
        "learningLanguage": "None for now",
        "excluded": [],
        "reflection": None,
        "complete": False,
    }


def _create_and_export(client, profile_id):
    created = client.put(
        f"/api/future/profile/{profile_id}",
        headers={"If-None-Match": "*"},
        json=_draft(profile_id),
    )
    assert created.status_code in (200, 201)
    exported = client.get(f"/api/future/profile/{profile_id}/export")
    assert exported.status_code == 200
    return exported.data


def test_profile_archive_round_trips_after_local_delete(api):
    profile_id = str(uuid4())
    client = api.app.test_client()
    archive = _create_and_export(client, profile_id)

    calibration_id = str(uuid4())
    session_id = str(uuid4())
    archive_value = json.loads(archive)
    archive_value["episteme"] = {
        "recordId": profile_id,
        "revision": 1,
        "profile": {"profileId": profile_id, "revision": 1, "evidence": []},
        "updatedAt": "2026-09-27T00:00:00Z",
    }
    archive_value["calibrations"] = [
        {
            "recordId": calibration_id,
            "revision": 1,
            "payload": {
                "calibrationId": calibration_id,
                "scope": {"kind": "profile", "profileId": profile_id},
                "observations": [],
                "actions": [],
            },
        }
    ]
    archive_value["solveSessions"] = [
        {
            "sessionId": session_id,
            "puzzle": {"puzzleId": None, "puzzleHash": "a" * 64},
            "initialGrid": [],
            "acceptedSequence": 0,
            "status": "finished",
            "createdAt": "2026-09-27T00:00:00Z",
            "updatedAt": "2026-09-27T00:00:00Z",
            "events": [],
            "analysis": None,
            "reflections": {"deck": None, "responses": [], "actions": []},
        }
    ]
    archive_value["integrity"]["value"] = archive_integrity_digest(archive_value)
    archive = json.dumps(archive_value).encode()

    assert client.delete(f"/api/future/profile/{profile_id}").status_code == 200
    restored = client.post(
        f"/api/future/profile/{profile_id}/import",
        data=archive,
        content_type="application/json",
    )

    assert restored.status_code == 201
    assert restored.json == {
        "historicalSolveSessions": 1,
        "imported": True,
        "profileId": profile_id,
        "sharedPuzzleManifests": "referenced-by-id-only",
    }
    with api.app.app_context():
        record = db.session.get(StartingProfile, profile_id)
        assert record is not None
        assert record.draft["id"] == profile_id
        assert db.session.get(EpistemeProfileRecord, profile_id) is not None
        assert db.session.get(CalibrationSessionRecord, calibration_id) is not None
        assert db.session.get(PersonalSolveSession, session_id) is not None

    # Re-import is an explicit no-overwrite boundary.
    assert (
        client.post(
            f"/api/future/profile/{profile_id}/import",
            data=archive,
            content_type="application/json",
        ).status_code
        == 409
    )


def test_profile_archive_import_checks_origin_identity_and_is_atomic(api):
    profile_id = str(uuid4())
    client = api.app.test_client()
    archive = json.loads(_create_and_export(client, profile_id))
    assert client.delete(f"/api/future/profile/{profile_id}").status_code == 200

    assert (
        client.post(
            f"/api/future/profile/{profile_id}/import",
            data=json.dumps(archive),
            content_type="application/json",
            headers={"Origin": "https://attacker.invalid"},
        ).status_code
        == 403
    )

    mismatched = str(uuid4())
    assert (
        client.post(
            f"/api/future/profile/{mismatched}/import",
            data=json.dumps(archive),
            content_type="application/json",
        ).status_code
        == 422
    )


def test_profile_archive_integrity_rejects_tampering_before_restore(api):
    profile_id = str(uuid4())
    client = api.app.test_client()
    archive = json.loads(_create_and_export(client, profile_id))
    archive["startingProfile"]["draft"]["traces"] = ["tampered"]
    assert client.delete(f"/api/future/profile/{profile_id}").status_code == 200

    response = client.post(
        f"/api/future/profile/{profile_id}/import",
        data=json.dumps(archive),
        content_type="application/json",
    )

    assert response.status_code == 422
    assert response.json["error"] == "Profile archive integrity check failed"
    with api.app.app_context():
        assert db.session.get(StartingProfile, profile_id) is None

    archive["calibrations"] = [
        {
            "recordId": str(uuid4()),
            "revision": 1,
            "payload": {"scope": {"kind": "profile", "profileId": str(uuid4())}},
        }
    ]
    rejected = client.post(
        f"/api/future/profile/{profile_id}/import",
        data=json.dumps(archive),
        content_type="application/json",
    )
    assert rejected.status_code == 422
    with api.app.app_context():
        assert db.session.get(StartingProfile, profile_id) is None


def test_profile_archive_rejects_narrative_with_unbound_evidence(api):
    profile_id = str(uuid4())
    client = api.app.test_client()
    archive = json.loads(_create_and_export(client, profile_id))
    archive["episteme"] = {
        "recordId": profile_id,
        "revision": 0,
        "profile": {"profileId": profile_id, "revision": 0, "evidence": []},
        "updatedAt": "2026-09-27T00:00:00Z",
    }
    archive["profileNarratives"] = [{
        "narrativeId": str(uuid4()),
        "epistemeRevision": 0,
        "sourceDigest": "a" * 64,
        "narrative": {
            "version": "private-profile-narrative-v1",
            "paragraphs": [{"text": "A saved note.", "evidenceIds": ["missing-evidence"]}],
            "openQuestions": [],
        },
        "generation": {},
        "status": "ready",
        "createdAt": "2026-09-27T00:00:00Z",
        "updatedAt": "2026-09-27T00:00:00Z",
    }]
    archive["integrity"]["value"] = archive_integrity_digest(archive)
    assert client.delete(f"/api/future/profile/{profile_id}").status_code == 200
    response = client.post(
        f"/api/future/profile/{profile_id}/import",
        data=json.dumps(archive),
        content_type="application/json",
    )
    assert response.status_code == 422
    assert response.json["error"] == "Profile archive failed validation"
    with api.app.app_context():
        assert db.session.get(StartingProfile, profile_id) is None
