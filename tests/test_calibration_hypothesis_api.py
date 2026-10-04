"""Host-owned, source-bound calibration hypothesis API checks."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

import pytest
import requests

from tests.test_api_isolated import api as isolated_api, no_network  # noqa: F401
from src.crossword.calibration_api import CalibrationSessionRecord
from src.crossword.calibration_hypothesis_api import (
    CalibrationHypothesisActionRecord,
    CalibrationHypothesisDeckRecord,
    CalibrationHypothesisResponseRecord,
    _active_chosen_source,
    _validate_model_paths,
    calibration_hypothesis_api,
)
from src.crossword.episteme_store import EpistemeProfileRecord
from src.crossword.future import StartingProfile


def _stimuli():
    catalog_path = Path(__file__).resolve().parents[1] / "src/crossword/future_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    return catalog["stimuli"]["items"]


def _ready_session(*, status="in-progress", cursor=5, profile_id=None, calibration_id=None):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    created = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    stamp = (now + timedelta(seconds=1)).isoformat(timespec="seconds").replace("+00:00", "Z")
    profile_id = profile_id or str(uuid4())
    calibration_id = calibration_id or str(uuid4())
    stimuli = _stimuli()
    observations = []
    selected = []
    for movement in range(1, 5):
        first = stimuli[(movement - 1) * 2]
        second = stimuli[(movement - 1) * 2 + 1]
        chosen = [first["id"]]
        offered = [first, second]
        relation = None
        if movement == 2:
            chosen = [first["id"]]
            offered = [first, second]
            relation = {
                "kind": "place-beside",
                "fromStimulusId": selected[0],
                "toStimulusId": first["id"],
            }
        selected.extend(item for item in chosen if item not in selected)
        observation = {
            "sequence": movement,
            "observationId": str(uuid4()),
            "trialId": str(uuid4()),
            "movement": movement,
            "offered": [
                {"stimulusId": item["id"], "stimulusVersion": str(item["version"]), "position": index}
                for index, item in enumerate(offered)
            ],
            "response": {"kind": "choose", "chosenIds": chosen},
            "elapsedMs": 240 + movement,
            "presentedAt": created,
            "recordedAt": stamp,
        }
        if relation:
            observation["relation"] = relation
        observations.append(observation)

    # An inactive retracted choice proves the model source is based on active
    # selections rather than the append-only raw history.
    inactive_stimulus = stimuli[12]
    inactive = {
        "sequence": 5,
        "observationId": str(uuid4()),
        "trialId": str(uuid4()),
        "movement": 1,
        "offered": [
            {"stimulusId": inactive_stimulus["id"], "stimulusVersion": str(inactive_stimulus["version"]), "position": 0},
            {"stimulusId": stimuli[13]["id"], "stimulusVersion": str(stimuli[13]["version"]), "position": 1},
        ],
        "response": {"kind": "choose", "chosenIds": [inactive_stimulus["id"]]},
        "elapsedMs": 99_999,
        "presentedAt": created,
        "recordedAt": stamp,
    }
    observations.append(inactive)
    session = {
        "schemaVersion": 1,
        "calibrationId": calibration_id,
        "scope": {"kind": "profile", "profileId": profile_id},
        "bankVersion": "1",
        "selectorVersion": "selector-v1",
        "seed": 42,
        "presentationMode": "visual",
        "currentMovement": cursor,
        "observations": observations,
        "actions": [{
            "sequence": 6,
            "actionId": str(uuid4()),
            "targetObservationId": inactive["observationId"],
            "action": "retract",
            "recordedAt": stamp,
        }],
        "setup": {"weekday": "Wednesday", "language": "en"},
        "status": status,
        "createdAt": created,
        "updatedAt": stamp,
    }
    if status == "completed":
        session["completedAt"] = (now + timedelta(seconds=2)).isoformat(timespec="seconds").replace("+00:00", "Z")
    return session


def _starting_profile(session, *, calibration_id=None):
    profile_id = session.get("_profileId", session["scope"].get("profileId"))
    assert profile_id is not None
    return StartingProfile(
        id=profile_id,
        draft={
            "version": 1,
            "id": profile_id,
            "step": 5,
            "object": "thread",
            "firstStimulus": "thread-knot",
            "companion": "fork",
            "traces": [],
            "weekday": "wednesday",
            "learningLanguage": "en",
            "excluded": [],
            "complete": True,
            "calibrationId": calibration_id or session["calibrationId"],
        },
        profile={"version": 1},
        updated_at=session["updatedAt"],
    )


@pytest.fixture
def hypothesis_host(isolated_api):
    if calibration_hypothesis_api.name not in isolated_api.app.blueprints:
        isolated_api.app.register_blueprint(calibration_hypothesis_api)
    with isolated_api.app.app_context():
        isolated_api.db.create_all()
    return isolated_api, isolated_api.app.test_client()


def _store_session(api, session, *, current_profile_calibration=None):
    with api.app.app_context():
        api.db.session.add(_starting_profile(session, calibration_id=current_profile_calibration))
        api.db.session.add(CalibrationSessionRecord(
            id=session["calibrationId"],
            revision=1,
            payload=session,
        ))
        api.db.session.commit()


def _local_headers():
    return {"Origin": "http://localhost"}


def _model_path(source, *, observation_ids=None, phrase="river-clock", connection="A possible bridge between return and time.", ambiguity="Several readings remain open."):
    ids = observation_ids or [source[0]["observationId"]]
    return {
        "phrase": phrase,
        "language": "en",
        "relation": "metaphor",
        "sourceObservationIds": ids,
        "connection": connection,
        "ambiguity": ambiguity,
    }


def _stub_generation(monkeypatch, *, paths_factory=None):
    import src.crossword.calibration_hypothesis_api as module

    calls = []

    def generate(source, language):
        calls.append((source, language))
        paths = paths_factory(source) if paths_factory else [_model_path(source)]
        try:
            paths = _validate_model_paths({"paths": paths}, source, language)
        except ValueError as error:
            from src.crossword.calibration_hypothesis_api import HypothesisRuntimeUnavailable
            raise HypothesisRuntimeUnavailable("invalid local model response") from error
        return paths, {"provider": "ollama-loopback", "requestedModel": "qwen3.8:27b", "returnedModel": "qwen3.8:27b", "digest": "local-test-digest", "format": "calibration-association-paths-v1"}

    monkeypatch.setattr(module, "_generate_paths", generate)
    return calls


def _create_deck(client, session):
    return client.post(
        f"/api/future/calibrations/{session['calibrationId']}/hypotheses",
        json={},
        headers=_local_headers(),
    )


def _supersede_calibration_source(api, calibration_id):
    with api.app.app_context():
        record = api.db.session.get(CalibrationSessionRecord, calibration_id)
        changed = dict(record.payload)
        observations = [dict(item) for item in changed["observations"]]
        observations[0] = dict(observations[0])
        observations[0]["response"] = {
            "kind": "choose",
            "chosenIds": [observations[0]["offered"][1]["stimulusId"]],
        }
        changed["observations"] = observations
        record.payload = changed
        api.db.session.commit()


def test_bodyless_preview_request_is_accepted_as_empty_object(hypothesis_host, monkeypatch):
    api, client = hypothesis_host
    session = _ready_session()
    _store_session(api, session)
    calls = _stub_generation(monkeypatch)

    created = client.post(
        f"/api/future/calibrations/{session['calibrationId']}/hypotheses",
        headers=_local_headers(),
    )

    assert created.status_code == 201, created.json
    assert len(calls) == 1


def test_ready_preview_generates_one_immutable_deck_from_active_selected_data(hypothesis_host, monkeypatch):
    api, client = hypothesis_host
    session = _ready_session()
    _store_session(api, session)
    calls = _stub_generation(
        monkeypatch,
        paths_factory=lambda source: [_model_path(
            source,
            observation_ids=[source[0]["observationId"], source[1]["observationId"]],
        )],
    )

    created = _create_deck(client, session)
    assert created.status_code == 201, created.json
    body = created.json
    assert set(body) >= {"deck", "responses", "profileRevision"}
    deck = body["deck"]
    assert deck["calibrationId"] == session["calibrationId"]
    assert deck["profileId"] == session["scope"]["profileId"]
    assert deck["expired"] is False
    assert len(deck["items"]) == 1
    item = deck["items"][0]
    assert item["sourceObservationIds"] == [calls[0][0][0]["observationId"], calls[0][0][1]["observationId"]]
    assert item["sourceStimulusIds"] == item["parentConceptIds"]
    delta = datetime.fromisoformat(deck["expiresAt"].replace("Z", "+00:00")) - datetime.fromisoformat(deck["createdAt"].replace("Z", "+00:00"))
    assert delta == timedelta(days=14)

    model_source, model_language = calls[0]
    assert model_language == "en"
    assert len(model_source) == 4
    assert session["observations"][-1]["observationId"] not in {row["observationId"] for row in model_source}
    assert all("elapsedMs" not in row and "movement" not in row and "recordedAt" not in row for row in model_source)
    assert all(set(stimulus) == {"stimulusId", "stimulusVersion", "label"} for row in model_source for stimulus in row["stimuli"])
    assert model_source[1]["relation"]["kind"] == "place-beside"

    retried = _create_deck(client, session)
    assert retried.status_code == 200, retried.json
    assert retried.json["deck"] == body["deck"]
    assert len(calls) == 1
    fetched = client.get(f"/api/future/calibrations/{session['calibrationId']}/hypotheses")
    assert fetched.status_code == 200
    assert fetched.json["deck"]["deckId"] == deck["deckId"]

    with api.app.app_context():
        stored = api.db.session.get(EpistemeProfileRecord, session["scope"]["profileId"])
        assert stored.revision == 1
        assert stored.profile_json["projection"]["claims"] == []
        assert stored.profile_json["projection"]["knowledge"] == []
        proposals = [item for item in stored.profile_json["evidence"] if item["type"] == "association-proposal"]
        assert len(proposals) == 1
        assert proposals[0]["origin"] == "calibration-proposal"
        assert proposals[0]["calibrationId"] == session["calibrationId"]
        assert proposals[0]["expireAfterSessions"] == 5
        assert proposals[0]["sourceStimulusIds"] == proposals[0]["parentConceptIds"]
        deck_record = api.db.session.query(CalibrationHypothesisDeckRecord).one()
        assert deck_record.generation_metadata["returnedModel"] == "qwen3.8:27b"


def test_preview_deck_survives_terminal_status_change_and_revision_creates_new_source_deck(hypothesis_host, monkeypatch):
    api, client = hypothesis_host
    session = _ready_session()
    _store_session(api, session)
    calls = _stub_generation(monkeypatch)
    first = _create_deck(client, session)
    assert first.status_code == 201

    with api.app.app_context():
        record = api.db.session.get(CalibrationSessionRecord, session["calibrationId"])
        finalized = dict(record.payload)
        finalized["status"] = "completed"
        finalized["completedAt"] = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat(timespec="seconds").replace("+00:00", "Z")
        finalized["updatedAt"] = finalized["completedAt"]
        record.payload = finalized
        api.db.session.commit()

    fetched = client.get(f"/api/future/calibrations/{session['calibrationId']}/hypotheses")
    assert fetched.status_code == 200
    assert fetched.json["deck"]["deckId"] == first.json["deck"]["deckId"]
    assert len(calls) == 1

    # A newly appended active calibration choice produces another frozen deck;
    # the first deck/evidence remains available as immutable history.
    with api.app.app_context():
        record = api.db.session.get(CalibrationSessionRecord, session["calibrationId"])
        changed = dict(record.payload)
        added = dict(changed["observations"][0])
        added["observationId"] = str(uuid4())
        added["trialId"] = str(uuid4())
        added["sequence"] = 7
        added["recordedAt"] = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat(timespec="seconds").replace("+00:00", "Z")
        changed["observations"] = [*changed["observations"], added]
        changed["updatedAt"] = added["recordedAt"]
        record.payload = changed
        api.db.session.commit()
    second = _create_deck(client, session)
    assert second.status_code == 201, second.json
    assert second.json["deck"]["deckId"] != first.json["deck"]["deckId"]
    assert second.json["deck"]["sourceDigest"] != first.json["deck"]["sourceDigest"]
    with api.app.app_context():
        assert api.db.session.query(CalibrationHypothesisDeckRecord).count() == 2
        stored = api.db.session.get(EpistemeProfileRecord, session["scope"]["profileId"])
        assert len([item for item in stored.profile_json["evidence"] if item["type"] == "association-proposal"]) == 2


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda value: value.update(status="skipped", skip={"movement": 5}), 409),
        (lambda value: value.update(status="in-progress", currentMovement=3), 409),
        (lambda value: (value.update(_profileId=value["scope"]["profileId"]), value.update(scope={"kind": "guest", "guestId": str(uuid4())})), 403),
        (lambda value: value.update(bankVersion="unknown-bank"), 409),
    ],
    ids=["skipped", "incomplete", "guest-scope", "wrong-bank-version"],
)
def test_hypothesis_generation_rejects_ineligible_or_mismatched_calibration(hypothesis_host, monkeypatch, mutate, expected):
    api, client = hypothesis_host
    session = _ready_session()
    mutate(session)
    _store_session(api, session)
    calls = _stub_generation(monkeypatch)
    response = _create_deck(client, session)
    assert response.status_code == expected, response.json
    assert calls == []


def test_hypothesis_generation_accepts_sparse_choices_when_other_movements_pass(hypothesis_host, monkeypatch):
    api, client = hypothesis_host
    session = _ready_session()
    for observation in session["observations"]:
        if observation["movement"] != 1:
            observation["response"] = {"kind": "pass"}
            observation.pop("relation", None)
    _store_session(api, session)
    calls = _stub_generation(monkeypatch)

    created = _create_deck(client, session)

    assert created.status_code == 201, created.json
    assert len(calls) == 1
    assert len(calls[0][0]) == 1
    assert calls[0][0][0]["observationId"] == session["observations"][0]["observationId"]


def test_hypothesis_generation_rejects_an_all_pass_opening_without_calling_model(hypothesis_host, monkeypatch):
    api, client = hypothesis_host
    session = _ready_session()
    for observation in session["observations"]:
        observation["response"] = {"kind": "pass"}
        observation.pop("relation", None)
    _store_session(api, session)
    calls = _stub_generation(monkeypatch)

    response = _create_deck(client, session)

    assert response.status_code == 409
    assert "active opening choices" in response.json["error"]
    assert calls == []


def test_hypothesis_generation_rejects_profile_calibration_mismatch_and_invalid_origin(hypothesis_host, monkeypatch):
    api, client = hypothesis_host
    session = _ready_session()
    _store_session(api, session, current_profile_calibration=str(uuid4()))
    calls = _stub_generation(monkeypatch)
    mismatch = _create_deck(client, session)
    assert mismatch.status_code == 409
    assert calls == []

    # Restore a matching profile pointer for origin/body checks.
    with api.app.app_context():
        record = api.db.session.get(StartingProfile, session["scope"]["profileId"])
        record.draft = {**record.draft, "calibrationId": session["calibrationId"]}
        api.db.session.commit()
    url = f"/api/future/calibrations/{session['calibrationId']}/hypotheses"
    assert client.post(url, json={}, headers={"Origin": "https://elsewhere.invalid"}).status_code == 403
    assert client.post(url, json={}).status_code == 403
    assert client.post(url, json={"evidence": []}, headers=_local_headers()).status_code == 422
    assert calls == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda item, source: item.update(relation="invented"),
        lambda item, source: item.update(sourceObservationIds=[str(uuid4())]),
        lambda item, source: item.update(connection="Your selection reveals you are anxious."),
        lambda item, source: item.update(ambiguity="This suggests your beliefs are unusual."),
        lambda item, source: item.update(phrase="your secret identity"),
        lambda item, source: item.update(extra="client evidence"),
    ],
    ids=["bad-relation", "forged-observation", "personality-health-claim", "belief-claim", "identity-claim", "extra-field"],
)
def test_malformed_or_personalizing_model_output_fails_closed_without_deck(hypothesis_host, monkeypatch, mutate):
    api, client = hypothesis_host
    session = _ready_session()
    _store_session(api, session)

    def malformed(source):
        item = _model_path(source)
        mutate(item, source)
        return [item]

    _stub_generation(monkeypatch, paths_factory=malformed)
    response = _create_deck(client, session)
    assert response.status_code == 503, response.json
    assert client.get(f"/api/future/calibrations/{session['calibrationId']}/hypotheses").status_code == 404
    with api.app.app_context():
        assert api.db.session.query(CalibrationHypothesisDeckRecord).count() == 0
        assert api.db.session.get(EpistemeProfileRecord, session["scope"]["profileId"]) is None


def test_response_and_action_events_are_host_authored_idempotent_and_reversible(hypothesis_host, monkeypatch):
    api, client = hypothesis_host
    session = _ready_session()
    _store_session(api, session)
    _stub_generation(monkeypatch)
    created = _create_deck(client, session)
    assert created.status_code == 201
    deck = created.json["deck"]
    proposal = deck["items"][0]
    response_id = str(uuid4())
    response_body = {"responseId": response_id, "deckId": deck["deckId"], "response": "keep"}
    url = f"/api/future/calibrations/{session['calibrationId']}/hypotheses/{proposal['proposalId']}/response"
    first = client.post(url, json=response_body, headers=_local_headers())
    assert first.status_code == 200, first.json
    assert first.json["replayed"] is False
    assert first.json["responses"][proposal["proposalId"]] == {"response": "keep", "responseId": response_id, "active": True}
    assert first.json["profileRevision"] == 2

    retry = client.post(url, json=response_body, headers=_local_headers())
    assert retry.status_code == 200
    assert retry.json["replayed"] is True
    assert retry.json["profileRevision"] == 2
    assert client.post(url, json={**response_body, "response": "not-for-me"}, headers=_local_headers()).status_code == 409
    assert client.post(url, json={**response_body, "clientEvidence": {}}, headers=_local_headers()).status_code == 422

    with api.app.app_context():
        stored = api.db.session.get(EpistemeProfileRecord, session["scope"]["profileId"])
        response_evidence = [item for item in stored.profile_json["evidence"] if item["type"] == "association-response"]
        assert len(response_evidence) == 1
        assert response_evidence[0]["proposalEvidenceId"] == proposal["evidenceId"]
        assert response_evidence[0]["associationId"] == proposal["associationId"]
        assert "recordedAt" in response_evidence[0]

    actions_url = f"/api/future/calibrations/{session['calibrationId']}/hypotheses/{proposal['proposalId']}/responses/{response_id}/actions"
    retract_body = {"actionId": str(uuid4()), "action": "retract"}
    retracted = client.post(actions_url, json=retract_body, headers=_local_headers())
    assert retracted.status_code == 200, retracted.json
    assert retracted.json["responses"][proposal["proposalId"]]["active"] is False
    assert retracted.json["profileRevision"] == 3
    assert client.post(actions_url, json=retract_body, headers=_local_headers()).json["replayed"] is True
    assert client.post(actions_url, json={"actionId": str(uuid4()), "action": "retract"}, headers=_local_headers()).status_code == 409

    restore_body = {"actionId": str(uuid4()), "action": "restore"}
    restored = client.post(actions_url, json=restore_body, headers=_local_headers())
    assert restored.status_code == 200, restored.json
    assert restored.json["responses"][proposal["proposalId"]]["active"] is True
    assert restored.json["profileRevision"] == 4
    assert client.post(actions_url, json=restore_body, headers=_local_headers()).json["replayed"] is True
    assert client.post(actions_url, json={"actionId": str(uuid4()), "action": "restore"}, headers=_local_headers()).status_code == 409
    with api.app.app_context():
        stored = api.db.session.get(EpistemeProfileRecord, session["scope"]["profileId"])
        response_actions = [item for item in stored.profile_json["evidenceActions"] if item["targetEvidenceId"] == response_evidence[0]["evidenceId"]]
        assert [item["action"] for item in sorted(response_actions, key=lambda item: item["recordedAt"])] == ["retract", "restore"]
        assert api.db.session.query(CalibrationHypothesisResponseRecord).count() == 1
        assert api.db.session.query(CalibrationHypothesisActionRecord).count() == 2


def test_responses_cannot_cross_decks_or_proposals_and_replays_survive_expiry(hypothesis_host, monkeypatch):
    api, client = hypothesis_host
    session = _ready_session()
    _store_session(api, session)
    _stub_generation(monkeypatch)
    created = _create_deck(client, session)
    deck = created.json["deck"]
    proposal = deck["items"][0]
    url = f"/api/future/calibrations/{session['calibrationId']}/hypotheses/{proposal['proposalId']}/response"
    response_id = str(uuid4())
    body = {"responseId": response_id, "deckId": deck["deckId"], "response": "pass"}
    assert client.post(url, json={**body, "deckId": str(uuid4())}, headers=_local_headers()).status_code == 404
    assert client.post(url, json={**body, "responseId": "not-a-uuid"}, headers=_local_headers()).status_code == 422
    assert client.post(f"/api/future/calibrations/{session['calibrationId']}/hypotheses/{str(uuid4())}/response", json=body, headers=_local_headers()).status_code == 404
    accepted = client.post(url, json=body, headers=_local_headers())
    assert accepted.status_code == 200

    with api.app.app_context():
        record = api.db.session.query(CalibrationHypothesisDeckRecord).one()
        record.deck_json = {**record.deck_json, "expiresAt": "2000-01-01T00:00:00.000Z"}
        # Update the integrity hash because this test simulates the passage of
        # time, not a corrupted persisted deck.
        from src.crossword.calibration_hypothesis_api import _hash
        record.deck_hash = _hash(record.deck_json)
        api.db.session.commit()
    replay = client.post(url, json=body, headers=_local_headers())
    assert replay.status_code == 200
    assert replay.json["replayed"] is True
    new_response = client.post(url, json={**body, "responseId": str(uuid4())}, headers=_local_headers())
    assert new_response.status_code == 410


def test_superseded_deck_allows_only_exact_replay_and_retraction(hypothesis_host, monkeypatch):
    api, client = hypothesis_host
    session = _ready_session()
    _store_session(api, session)
    _stub_generation(monkeypatch)
    created = _create_deck(client, session)
    deck = created.json["deck"]
    proposal = deck["items"][0]
    response_url = f"/api/future/calibrations/{session['calibrationId']}/hypotheses/{proposal['proposalId']}/response"
    response_body = {"responseId": str(uuid4()), "deckId": deck["deckId"], "response": "keep"}
    accepted = client.post(response_url, json=response_body, headers=_local_headers())
    assert accepted.status_code == 200

    # Change an active choice while preserving calibration/profile identity.
    # This makes the immutable source digest stale without deleting its audit.
    _supersede_calibration_source(api, session["calibrationId"])

    get_url = f"/api/future/calibrations/{session['calibrationId']}/hypotheses"
    assert client.get(get_url).status_code == 404
    # A completed exact receipt is an idempotent replay; a fresh signal is not.
    replay = client.post(response_url, json=response_body, headers=_local_headers())
    assert replay.status_code == 200 and replay.json["replayed"] is True
    fresh = {**response_body, "responseId": str(uuid4())}
    assert client.post(response_url, json=fresh, headers=_local_headers()).status_code == 409

    actions_url = f"/api/future/calibrations/{session['calibrationId']}/hypotheses/{proposal['proposalId']}/responses/{response_body['responseId']}/actions"
    retract = {"actionId": str(uuid4()), "action": "retract"}
    assert client.post(actions_url, json=retract, headers=_local_headers()).status_code == 200
    restore = {"actionId": str(uuid4()), "action": "restore"}
    assert client.post(actions_url, json=restore, headers=_local_headers()).status_code == 409
    assert client.post(actions_url, json=retract, headers=_local_headers()).json["replayed"] is True


def test_pending_response_receipt_recovers_after_source_change(hypothesis_host, monkeypatch):
    import src.crossword.calibration_hypothesis_api as module

    api, client = hypothesis_host
    session = _ready_session()
    _store_session(api, session)
    _stub_generation(monkeypatch)
    deck = _create_deck(client, session).json["deck"]
    proposal = deck["items"][0]
    body = {"responseId": str(uuid4()), "deckId": deck["deckId"], "response": "keep"}
    route = f"/api/future/calibrations/{session['calibrationId']}/hypotheses/{proposal['proposalId']}/response"
    original_apply = module.apply_episteme_command
    failed = False

    def commit_then_drop_receipt(*args, **kwargs):
        nonlocal failed
        result = original_apply(*args, **kwargs)
        if not failed and args[3]["updateId"] == str(module.uuid5(
            module.NAMESPACE_URL,
            f"crossword-calibration-response-update:{body['responseId']}:v1",
        )):
            failed = True
            raise RuntimeError("injected crash after profile commit")
        return result

    monkeypatch.setattr(module, "apply_episteme_command", commit_then_drop_receipt)
    with pytest.raises(RuntimeError, match="after profile commit"):
        client.post(route, json=body, headers=_local_headers())
    monkeypatch.setattr(module, "apply_episteme_command", original_apply)
    _supersede_calibration_source(api, session["calibrationId"])

    retry = client.post(route, json=body, headers=_local_headers())
    assert retry.status_code == 200, retry.json
    assert retry.json["replayed"] is True
    assert retry.json["response"]["responseId"] == body["responseId"]
    with api.app.app_context():
        receipt = api.db.session.get(CalibrationHypothesisResponseRecord, body["responseId"])
        profile = api.db.session.get(EpistemeProfileRecord, session["scope"]["profileId"])
        assert receipt.status == "complete"
        assert receipt.episteme_revision == 2
        assert len([item for item in profile.profile_json["evidence"] if item["type"] == "association-response"]) == 1


def test_pending_action_receipt_recovers_after_source_change(hypothesis_host, monkeypatch):
    import src.crossword.calibration_hypothesis_api as module

    api, client = hypothesis_host
    session = _ready_session()
    _store_session(api, session)
    _stub_generation(monkeypatch)
    deck = _create_deck(client, session).json["deck"]
    proposal = deck["items"][0]
    response_body = {"responseId": str(uuid4()), "deckId": deck["deckId"], "response": "keep"}
    response_route = f"/api/future/calibrations/{session['calibrationId']}/hypotheses/{proposal['proposalId']}/response"
    assert client.post(response_route, json=response_body, headers=_local_headers()).status_code == 200
    action_route = f"/api/future/calibrations/{session['calibrationId']}/hypotheses/{proposal['proposalId']}/responses/{response_body['responseId']}/actions"
    assert client.post(action_route, json={"actionId": str(uuid4()), "action": "retract"}, headers=_local_headers()).status_code == 200

    body = {"actionId": str(uuid4()), "action": "restore"}
    update_id = str(module.uuid5(module.NAMESPACE_URL, f"crossword-calibration-action-update:{body['actionId']}:v1"))
    original_apply = module.apply_episteme_command
    failed = False

    def commit_then_drop_receipt(*args, **kwargs):
        nonlocal failed
        result = original_apply(*args, **kwargs)
        if not failed and args[3]["updateId"] == update_id:
            failed = True
            raise RuntimeError("injected crash after profile commit")
        return result

    monkeypatch.setattr(module, "apply_episteme_command", commit_then_drop_receipt)
    with pytest.raises(RuntimeError, match="after profile commit"):
        client.post(action_route, json=body, headers=_local_headers())
    monkeypatch.setattr(module, "apply_episteme_command", original_apply)
    _supersede_calibration_source(api, session["calibrationId"])

    retry = client.post(action_route, json=body, headers=_local_headers())
    assert retry.status_code == 200, retry.json
    assert retry.json["replayed"] is True
    assert retry.json["responses"][proposal["proposalId"]]["active"] is True
    with api.app.app_context():
        receipt = api.db.session.get(CalibrationHypothesisActionRecord, body["actionId"])
        profile = api.db.session.get(EpistemeProfileRecord, session["scope"]["profileId"])
        assert receipt.status == "complete"
        assert receipt.episteme_revision == 4
        assert len(profile.profile_json["evidenceActions"]) == 2


def test_episteme_cas_conflict_retries_with_fresh_revision(hypothesis_host, monkeypatch):
    import src.crossword.calibration_hypothesis_api as module

    api, client = hypothesis_host
    session = _ready_session()
    _store_session(api, session)
    _stub_generation(monkeypatch)
    original = module.apply_episteme_command
    calls = []

    def conflict_once(*args, **kwargs):
        calls.append(args[1])
        if len(calls) == 1:
            raise module.EpistemeRevisionConflict("Stale profile revision: injected test race")
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "apply_episteme_command", conflict_once)
    response = _create_deck(client, session)
    assert response.status_code == 201, response.json
    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert response.json["profileRevision"] == 1


class _StreamResponse:
    def __init__(self, body, *, status_code=200, headers=None, chunk_size=3072):
        self.body = body
        self.status_code = status_code
        self.headers = headers or {"Content-Length": str(len(body))}
        self.chunk_size = chunk_size
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.body), min(self.chunk_size, chunk_size)):
            yield self.body[offset : offset + min(self.chunk_size, chunk_size)]

    def close(self):
        self.closed = True


class _FakeOllamaSession:
    def __init__(self, tags, generated, post_tags=None):
        self.trust_env = True
        self.tags = tags
        self.generated = generated
        self.post_tags = post_tags if post_tags is not None else tags
        self.get_count = 0
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, url, **options):
        self.calls.append(("GET", url, options, self.trust_env))
        tags = self.tags if self.get_count == 0 else self.post_tags
        self.get_count += 1
        return _StreamResponse(json.dumps(tags).encode("utf-8"))

    def post(self, url, **options):
        self.calls.append(("POST", url, options, self.trust_env))
        return _StreamResponse(json.dumps(self.generated).encode("utf-8"))


def _ollama_fixture(
    source,
    monkeypatch,
    *,
    model_names=("qwen3.8:27b",),
    raw_paths=None,
    oversized=False,
    include_model=True,
    response_model=None,
    digest="a" * 64,
    include_digest=True,
    post_tags=None,
    hypothesis_model="qwen3.8:27b",
    profile_model=None,
):
    import src.crossword.calibration_hypothesis_api as module

    paths = raw_paths if raw_paths is not None else [_model_path(source)]
    content = json.dumps({"paths": paths})
    if oversized:
        content = " " * (module.MAX_MODEL_RESPONSE_BYTES + 10)
    model_tags = []
    for name in model_names:
        tag = {"name": name}
        if include_digest:
            tag["digest"] = digest
        model_tags.append(tag)
    generated = {"message": {"content": content}}
    if include_model:
        generated["model"] = response_model if response_model is not None else model_names[0]
    session = _FakeOllamaSession(
        {"models": model_tags},
        generated,
        post_tags=post_tags,
    )
    if hypothesis_model is None:
        monkeypatch.delenv("CROSSWORD_HYPOTHESIS_MODEL", raising=False)
    else:
        monkeypatch.setenv("CROSSWORD_HYPOTHESIS_MODEL", hypothesis_model)
    if profile_model is None:
        monkeypatch.delenv("CROSSWORD_PROFILE_MODEL", raising=False)
    else:
        monkeypatch.setenv("CROSSWORD_PROFILE_MODEL", profile_model)
    monkeypatch.setattr(module, "_new_ollama_session", lambda: _trust_env_false(session))
    return session


def _trust_env_false(session):
    session.trust_env = False
    return session


def test_local_ollama_is_pinned_to_loopback_without_proxy_and_uses_exact_fallbacks(monkeypatch):
    import src.crossword.calibration_hypothesis_api as module

    source = [{"observationId": str(uuid4()), "stimuli": [{"stimulusId": "stone", "stimulusVersion": "1", "label": "A stone"}]}]
    fake = _ollama_fixture(source, monkeypatch, model_names=("gemma4:31b",))
    paths, metadata = module._generate_paths(source, "en")
    assert paths[0]["phrase"] == "river-clock"
    assert metadata["requestedModel"] == "gemma4:31b"
    assert metadata["returnedModel"] == "gemma4:31b"
    assert metadata["identityVerified"] is True
    expected_identity = {"tag": "gemma4:31b", "digest": "sha256:" + "a" * 64}
    assert metadata["preInferenceIdentity"] == expected_identity
    assert metadata["postInferenceIdentity"] == expected_identity
    assert all(call[1].startswith("http://127.0.0.1:11434/") for call in fake.calls)
    assert all(call[2]["stream"] is True and call[2]["allow_redirects"] is False for call in fake.calls)
    assert all(call[3] is False for call in fake.calls)
    assert fake.calls[1][2]["json"]["model"] == "gemma4:31b"
    assert "gemma3:27b" not in [call[2].get("json", {}).get("model") for call in fake.calls]
    assert [call[0] for call in fake.calls] == ["GET", "POST", "GET"]


def test_local_ollama_prefers_gemma26_by_default_when_both_candidates_are_installed(monkeypatch):
    import src.crossword.calibration_hypothesis_api as module

    source = [{"observationId": str(uuid4()), "stimuli": [{"stimulusId": "stone", "stimulusVersion": "1", "label": "A stone"}]}]
    fake = _ollama_fixture(
        source,
        monkeypatch,
        model_names=("qwen3.8:27b", "gemma4:26b"),
        hypothesis_model=None,
        profile_model=None,
        response_model="gemma4:26b",
    )
    _, metadata = module._generate_paths(source, "en")

    assert metadata["requestedModel"] == "gemma4:26b"
    assert fake.calls[1][2]["json"]["model"] == "gemma4:26b"


@pytest.mark.parametrize("override_env", ["hypothesis_model", "profile_model"])
def test_explicit_qwen_override_remains_first_when_gemma_is_also_installed(monkeypatch, override_env):
    import src.crossword.calibration_hypothesis_api as module

    source = [{"observationId": str(uuid4()), "stimuli": [{"stimulusId": "stone", "stimulusVersion": "1", "label": "A stone"}]}]
    overrides = {"hypothesis_model": None, "profile_model": None}
    overrides[override_env] = "qwen3.8:27b"
    fake = _ollama_fixture(
        source,
        monkeypatch,
        model_names=("qwen3.8:27b", "gemma4:26b"),
        **overrides,
    )
    _, metadata = module._generate_paths(source, "en")

    assert metadata["requestedModel"] == "qwen3.8:27b"
    assert fake.calls[1][2]["json"]["model"] == "qwen3.8:27b"


@pytest.mark.parametrize(
    ("fixture_options", "message"),
    [
        ({"include_model": False}, "different model tag"),
        ({"response_model": "qwen3.8:latest"}, "different model tag"),
    ],
    ids=["missing-model", "mismatched-model"],
)
def test_local_ollama_requires_exact_returned_model_tag(monkeypatch, fixture_options, message):
    import src.crossword.calibration_hypothesis_api as module

    source = [{"observationId": str(uuid4()), "stimuli": [{"stimulusId": "stone", "stimulusVersion": "1", "label": "A stone"}]}]
    fake = _ollama_fixture(source, monkeypatch, **fixture_options)
    with pytest.raises(module.HypothesisRuntimeUnavailable, match="unavailable"):
        module._generate_paths(source, "en")
    assert [call[0] for call in fake.calls] == ["GET", "POST", "GET"]


@pytest.mark.parametrize(
    "fixture_options",
    [
        {"include_digest": False},
        {"digest": "not-a-sha256"},
        {"digest": "A" * 64},
    ],
    ids=["missing-digest", "malformed-digest", "uppercase-digest"],
)
def test_local_ollama_rejects_missing_or_malformed_tag_digest_before_inference(monkeypatch, fixture_options):
    import src.crossword.calibration_hypothesis_api as module

    source = [{"observationId": str(uuid4()), "stimuli": [{"stimulusId": "stone", "stimulusVersion": "1", "label": "A stone"}]}]
    fake = _ollama_fixture(source, monkeypatch, **fixture_options)
    with pytest.raises(module.HypothesisRuntimeUnavailable, match="unavailable"):
        module._generate_paths(source, "en")
    assert [call[0] for call in fake.calls] == ["GET"]


@pytest.mark.parametrize(
    "post_tags",
    [
        {"models": [{"name": "qwen3.8:27b", "digest": "b" * 64}]},
        {"models": []},
    ],
    ids=["changed-digest", "disappeared-tag"],
)
def test_local_ollama_rejects_model_identity_change_after_inference(monkeypatch, post_tags):
    import src.crossword.calibration_hypothesis_api as module

    source = [{"observationId": str(uuid4()), "stimuli": [{"stimulusId": "stone", "stimulusVersion": "1", "label": "A stone"}]}]
    fake = _ollama_fixture(source, monkeypatch, post_tags=post_tags)
    with pytest.raises(module.HypothesisRuntimeUnavailable, match="unavailable"):
        module._generate_paths(source, "en")
    assert [call[0] for call in fake.calls] == ["GET", "POST", "GET"]


def test_streamed_model_response_is_capped_before_full_buffer_and_redirects_fail(monkeypatch):
    import src.crossword.calibration_hypothesis_api as module

    oversized = _StreamResponse(b"x" * (module.MAX_MODEL_RESPONSE_BYTES + 1), headers={})
    with pytest.raises(ValueError, match="too large"):
        module._read_model_response(oversized, module.MAX_MODEL_RESPONSE_BYTES)
    assert oversized.closed is True
    redirect = _StreamResponse(b"{}", status_code=302, headers={})
    with pytest.raises(ValueError, match="redirect"):
        module._read_model_response(redirect, 10)


def test_model_runtime_malformed_forged_or_oversized_output_fails_without_writing(hypothesis_host, monkeypatch):
    api, client = hypothesis_host
    session = _ready_session()
    _store_session(api, session)
    source = _active_chosen_source(session)
    forged = _model_path(source)
    forged["sourceObservationIds"] = [str(uuid4())]
    _ollama_fixture(source, monkeypatch, raw_paths=[forged])
    unavailable = _create_deck(client, session)
    assert unavailable.status_code == 503
    assert client.get(f"/api/future/calibrations/{session['calibrationId']}/hypotheses").status_code == 404

    source = _active_chosen_source(session)
    _ollama_fixture(source, monkeypatch, oversized=True)
    oversized = _create_deck(client, session)
    assert oversized.status_code == 503
    with api.app.app_context():
        assert api.db.session.query(CalibrationHypothesisDeckRecord).count() == 0


def test_cited_relation_requires_both_endpoint_observations_to_be_cited(hypothesis_host):
    api, _ = hypothesis_host
    source = _active_chosen_source(_ready_session())
    relation_index = next(index for index, item in enumerate(source) if item.get("relation"))
    relation = source[relation_index]["relation"]
    endpoint_id = relation["from"]["stimulusId"]
    endpoint_observation = next(
        item for item in source
        if any(stimulus["stimulusId"] == endpoint_id for stimulus in item["stimuli"])
    )
    too_short = _model_path(source, observation_ids=[source[relation_index]["observationId"]])
    with pytest.raises(ValueError, match="relation endpoint"):
        _validate_model_paths({"paths": [too_short]}, source, "en")
    valid = _model_path(source, observation_ids=[source[relation_index]["observationId"], endpoint_observation["observationId"]])
    result = _validate_model_paths({"paths": [valid]}, source, "en")
    assert endpoint_id in result[0]["sourceStimulusIds"]
