"""The local API runs the shared reducer and commits one revision per bundle."""
from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

from tests.test_api_isolated import api, no_network  # noqa: F401
from tests.test_future_api import draft
from src.crossword.episteme_store import EpistemeProfileRecord
from werkzeug.test import EnvironBuilder


def explicit_control(evidence_id=None):
    return {
        "evidenceId": evidence_id or str(uuid4()),
        "recordedAt": "2026-09-26T10:00:00.000Z",
        "type": "explicit-preference",
        "concept": {"conceptId": "us-officeholders", "label": "US officeholders", "language": "en"},
        "kind": "context",
        "action": "exclude",
        "scope": {"mode": "play", "language": "en"},
        "supersedesEvidenceIds": [],
        "userText": "Fewer US political officeholder clues",
    }


def update_body(evidence=None, *, revision=0, update_id=None):
    return {
        "expectedRevision": revision,
        "updateId": update_id or str(uuid4()),
        "recordedAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "evidence": [evidence or explicit_control()],
        "evidenceActions": [],
    }


def ready_profile(client):
    value = draft()
    assert client.put(
        f"/api/future/profile/{value['id']}",
        json=value,
        headers={"If-None-Match": "*"},
    ).status_code == 200
    return value["id"]


def test_episteme_revision_runs_shared_reducer_and_replays_idempotently(api):
    client = api.app.test_client()
    profile_id = ready_profile(client)

    initial = client.get(f"/api/future/profile/{profile_id}/episteme")
    assert initial.status_code == 200
    assert initial.json["revision"] == 0
    assert initial.json["profile"]["projection"]["claims"] == []

    empty = update_body()
    empty["evidence"] = []
    assert client.post(
        f"/api/future/profile/{profile_id}/episteme/updates", json=empty
    ).status_code == 422

    body = update_body()
    first = client.post(f"/api/future/profile/{profile_id}/episteme/updates", json=body)
    assert first.status_code == 200, first.json
    assert first.json["revision"] == 1
    assert first.json["changed"] is True
    assert first.json["profile"]["projection"]["policies"][0]["mode"] == "exclude"
    assert first.json["profile"]["projection"]["claims"][0]["stance"] == "avoid"

    retry = client.post(f"/api/future/profile/{profile_id}/episteme/updates", json=body)
    assert retry.status_code == 200, retry.json
    assert retry.json["replayed"] is True
    assert retry.json["changed"] is False
    assert retry.json["revision"] == 1
    with api.app.app_context():
        stored = api.db.session.get(EpistemeProfileRecord, profile_id)
        assert stored.revision == stored.profile_json["revision"] == 1


def test_simultaneous_duplicate_that_loses_cas_replays_the_winner(api):
    client = api.app.test_client()
    profile_id = ready_profile(client)
    initial = client.get(f"/api/future/profile/{profile_id}/episteme").json["profile"]
    body = update_body()
    assert client.post(f"/api/future/profile/{profile_id}/episteme/updates", json=body).status_code == 200

    # Model the second request having read revision zero before the first one
    # committed. Its compare-and-swap misses, then the store sees the exact
    # idempotency receipt and returns the winner instead of a false conflict.
    from src.crossword.episteme_store import apply_episteme_command

    command = {
        "updateId": body["updateId"],
        "profileId": profile_id,
        "baseRevision": body["expectedRevision"],
        "recordedAt": body["recordedAt"],
        "evidence": body["evidence"],
        "evidenceActions": body["evidenceActions"],
    }
    with api.app.app_context():
        result, changed = apply_episteme_command(profile_id, 0, initial, command)
        stored = api.db.session.get(EpistemeProfileRecord, profile_id)
        assert result["replayed"] is True
        assert changed is False
        assert stored.revision == 1


def test_episteme_rejects_stale_untrusted_session_analysis_and_cross_origin(api):
    client = api.app.test_client()
    profile_id = ready_profile(client)
    initial = client.get(f"/api/future/profile/{profile_id}/episteme")
    assert initial.status_code == 200

    first = update_body(revision=0)
    assert client.post(f"/api/future/profile/{profile_id}/episteme/updates", json=first).status_code == 200
    stale = update_body(explicit_control(), revision=0)
    conflict = client.post(f"/api/future/profile/{profile_id}/episteme/updates", json=stale)
    assert conflict.status_code == 409

    reused_key = update_body(revision=1, update_id=first["updateId"])
    assert client.post(
        f"/api/future/profile/{profile_id}/episteme/updates", json=reused_key
    ).status_code == 409

    forged = update_body({"evidenceId": str(uuid4()), "type": "session-analysis"}, revision=1)
    assert client.post(f"/api/future/profile/{profile_id}/episteme/updates", json=forged).status_code == 422
    assert client.post(
        f"/api/future/profile/{profile_id}/episteme/updates",
        json=update_body(revision=1),
        headers={"Origin": "https://other.invalid"},
    ).status_code == 403


def test_episteme_api_requires_a_known_profile_and_bounded_body(api):
    client = api.app.test_client()
    missing = str(uuid4())
    assert client.get(f"/api/future/profile/{missing}/episteme").status_code == 404
    assert client.post(f"/api/future/profile/{missing}/episteme/updates", json={}).status_code == 404
    profile_id = ready_profile(client)
    oversized = client.post(
        f"/api/future/profile/{profile_id}/episteme/updates",
        data=b"{" + b" " * (256 * 1024) + b"}",
        content_type="application/json",
    )
    assert oversized.status_code == 413


def test_episteme_read_refreshes_expiring_hypotheses_without_mutating_the_ledger(api, monkeypatch):
    import src.crossword.episteme_api as episteme_api_module
    from src.crossword.episteme_store import apply_episteme_command

    client = api.app.test_client()
    profile_id = ready_profile(client)
    created = client.get(f"/api/future/profile/{profile_id}/episteme").json
    recorded_at = "2026-09-26T14:00:00.000Z"
    proposal = {
        "evidenceId": "calibration-proposal-read-time",
        "recordedAt": recorded_at,
        "type": "association-proposal",
        "associationId": "calibration-association-read-time",
        "phrase": "a door made of echoes",
        "language": "en",
        "relation": "metaphor",
        "parentConceptIds": ["stimulus:echo"],
        "explanation": "A sound and a threshold may meet in language.",
        "origin": "calibration-proposal",
        "calibrationId": str(uuid4()),
        "sourceObservationIds": ["observation-1"],
        "sourceStimulusIds": ["stimulus:echo"],
        "expiresAt": "2026-10-10T14:00:00.000Z",
        "expireAfterSessions": 5,
    }
    response_event = {
        "evidenceId": "calibration-response-read-time",
        "recordedAt": recorded_at,
        "type": "association-response",
        "associationId": proposal["associationId"],
        "proposalEvidenceId": proposal["evidenceId"],
        "response": "keep",
    }
    with api.app.app_context():
        record, changed = apply_episteme_command(
            profile_id,
            0,
            created["profile"],
            {
                "updateId": str(uuid4()),
                "profileId": profile_id,
                "baseRevision": 0,
                "recordedAt": recorded_at,
                "evidence": [proposal, response_event],
                "evidenceActions": [],
            },
        )
        assert changed is True
        assert record["profile"]["projection"]["associations"][0]["calibrationProvenance"]["expired"] is False

    monkeypatch.setattr(episteme_api_module, "now_utc_iso", lambda: "2026-10-11T14:00:00.000Z")
    projected = client.get(f"/api/future/profile/{profile_id}/episteme")
    assert projected.status_code == 200
    association = projected.json["profile"]["projection"]["associations"][0]
    assert association["calibrationProvenance"]["expired"] is True
    assert association["explorationWeight"] == 0

    with api.app.app_context():
        stored = api.db.session.get(EpistemeProfileRecord, profile_id)
        assert stored.profile_json["projection"]["associations"][0]["calibrationProvenance"]["expired"] is False
        assert stored.revision == 1


def test_episteme_storage_ceiling_is_enforced_before_commit(api, monkeypatch):
    import src.crossword.episteme_store as store

    client = api.app.test_client()
    profile_id = ready_profile(client)
    assert client.get(f"/api/future/profile/{profile_id}/episteme").json["revision"] == 0
    monkeypatch.setattr(store, "MAX_PROFILE_BYTES", 128)
    response = client.post(
        f"/api/future/profile/{profile_id}/episteme/updates", json=update_body()
    )
    assert response.status_code == 422
    with api.app.app_context():
        stored = api.db.session.get(EpistemeProfileRecord, profile_id)
        assert stored.revision == 0


def test_episteme_request_limit_applies_without_content_length(api):
    client = api.app.test_client()
    profile_id = ready_profile(client)
    environ = EnvironBuilder(
        path=f"/api/future/profile/{profile_id}/episteme/updates",
        method="POST",
        content_type="application/json",
    ).get_environ()
    environ["wsgi.input"] = BytesIO(b"{" + b" " * (256 * 1024) + b"}")
    environ.pop("CONTENT_LENGTH", None)
    environ["wsgi.input_terminated"] = True
    response = client.open(environ)
    assert response.status_code == 413
