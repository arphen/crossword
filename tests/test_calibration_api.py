"""Host persistence checks for the append-only calibration contract."""
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

import pytest

from tests.test_api_isolated import api as isolated_api, no_network  # noqa: F401
from src.crossword.calibration_api import CalibrationSessionRecord, calibration_api


@pytest.fixture
def calibration_host(isolated_api):
    if "calibration_api" not in isolated_api.app.blueprints:
        isolated_api.app.register_blueprint(calibration_api)
    with isolated_api.app.app_context():
        isolated_api.db.create_all()
    return isolated_api, isolated_api.app.test_client()


def _stimuli():
    catalog_path = Path(__file__).resolve().parents[1] / "src/crossword/future_catalog.json"
    return json.loads(catalog_path.read_text(encoding="utf-8"))["stimuli"]["items"]


def _session(calibration_id=None):
    return {
        "schemaVersion": 1,
        "calibrationId": calibration_id or str(uuid4()),
        "scope": {"kind": "profile", "profileId": str(uuid4())},
        "bankVersion": "opening-bank-v1",
        "selectorVersion": "selector-v1",
        "seed": 42,
        "presentationMode": "visual",
        "currentMovement": 1,
        "observations": [],
        "actions": [],
        "status": "in-progress",
        "createdAt": "2026-10-01T10:00:00.000Z",
        "updatedAt": "2026-10-01T10:00:00.000Z",
    }


def _observation(sequence, *, response=None, recorded_at=None):
    stimuli = _stimuli()
    first, second = stimuli[:2]
    offered = [first, second]
    return {
        "sequence": sequence,
        "observationId": str(uuid4()),
        "trialId": str(uuid4()),
        "movement": 1,
        "offered": [
            {"stimulusId": item["id"], "stimulusVersion": str(item["version"]), "position": index}
            for index, item in enumerate(offered)
        ],
        "response": response or {"kind": "choose", "chosenIds": [first["id"]]},
        "presentedAt": "2026-10-01T10:00:00.000Z",
        "recordedAt": recorded_at or "2026-10-01T10:00:01.000Z",
    }


def _put(client, session, *, headers=None):
    return client.put(
        f"/api/future/calibrations/{session['calibrationId']}",
        json=session,
        headers=headers or {},
    )


def test_calibration_create_read_retry_and_profile_can_precede_profile_record(calibration_host):
    _, client = calibration_host
    session = _session()
    created = _put(client, session, headers={"If-None-Match": "*"})
    assert created.status_code == 201, created.json
    assert created.headers["ETag"] == '"calibration-1"'
    fetched = client.get(f"/api/future/calibrations/{session['calibrationId']}")
    assert fetched.status_code == 200
    assert fetched.json["calibration"] == session
    assert fetched.headers["ETag"] == created.headers["ETag"]

    # Exact retry with the create precondition is safe after a lost response.
    retried = _put(client, session, headers={"If-None-Match": "*"})
    assert retried.status_code == 200
    assert retried.json["calibration"] == session


def test_create_requires_precondition_and_invalid_ids_are_rejected(calibration_host):
    _, client = calibration_host
    session = _session()
    assert _put(client, session).status_code == 409
    invalid = client.get("/api/future/calibrations/not-a-uuid")
    assert invalid.status_code == 400
    mismatch = deepcopy(session)
    mismatch["calibrationId"] = str(uuid4())
    rejected = client.put(
        f"/api/future/calibrations/{session['calibrationId']}",
        json=mismatch,
        headers={"If-None-Match": "*"},
    )
    assert rejected.status_code == 422
    assert "calibration id" in rejected.json["error"].lower()


def test_update_appends_with_etag_and_stale_writer_conflicts(calibration_host):
    _, client = calibration_host
    session = _session()
    created = _put(client, session, headers={"If-None-Match": "*"})
    assert created.status_code == 201
    initial_etag = created.headers["ETag"]

    first_update = deepcopy(session)
    first_update["observations"].append(_observation(1))
    first_update["currentMovement"] = 2
    first_update["updatedAt"] = "2026-10-01T10:00:02.000Z"
    saved = _put(client, first_update, headers={"If-Match": initial_etag})
    assert saved.status_code == 200, saved.json
    assert saved.headers["ETag"] == '"calibration-2"'

    # A retry of that exact accepted body remains idempotent with its old ETag.
    assert _put(client, first_update, headers={"If-Match": initial_etag}).status_code == 200

    stale_update = deepcopy(session)
    stale_update["observations"].append(_observation(1))
    stale_update["currentMovement"] = 2
    stale_update["updatedAt"] = "2026-10-01T10:00:03.000Z"
    conflict = _put(client, stale_update, headers={"If-Match": initial_etag})
    assert conflict.status_code == 409
    assert conflict.json["revision"] == 2
    assert client.get(f"/api/future/calibrations/{session['calibrationId']}").json["calibration"] == first_update


def test_movement_cursor_can_move_back_without_rewriting_evidence(calibration_host):
    _, client = calibration_host
    session = _session()
    session["currentMovement"] = 4
    created = _put(client, session, headers={"If-None-Match": "*"})
    assert created.status_code == 201
    moved_back = deepcopy(session)
    moved_back["currentMovement"] = 2
    moved_back["updatedAt"] = "2026-10-01T10:00:01.000Z"
    saved = _put(client, moved_back, headers={"If-Match": created.headers["ETag"]})
    assert saved.status_code == 200, saved.json
    assert saved.json["calibration"]["currentMovement"] == 2


@pytest.mark.parametrize(
    "response",
    [None, {"kind": "pass"}],
    ids=["active-choice", "pass"],
)
def test_cursor_can_advance_after_an_existing_active_response(calibration_host, response):
    _, client = calibration_host
    session = _session()
    observation = _observation(1, response=response)
    session["observations"] = [observation]
    session["updatedAt"] = "2026-10-01T10:00:01.000Z"
    created = _put(client, session, headers={"If-None-Match": "*"})
    assert created.status_code == 201, created.json

    revisited = deepcopy(session)
    revisited["currentMovement"] = 2
    revisited["updatedAt"] = "2026-10-01T10:00:02.000Z"
    saved = _put(client, revisited, headers={"If-Match": created.headers["ETag"]})

    assert saved.status_code == 200, saved.json
    assert saved.json["calibration"]["currentMovement"] == 2


@pytest.mark.parametrize(
    "cursor, add_observation, expected_error",
    [
        (3, True, "cannot skip a movement"),
        (2, False, "needs a response before the cursor can advance"),
    ],
    ids=["forward-jump", "unrecorded-advance"],
)
def test_cursor_rejects_jumps_and_advance_without_a_current_response(
    calibration_host, cursor, add_observation, expected_error
):
    _, client = calibration_host
    session = _session()
    created = _put(client, session, headers={"If-None-Match": "*"})
    assert created.status_code == 201

    candidate = deepcopy(session)
    candidate["currentMovement"] = cursor
    candidate["updatedAt"] = "2026-10-01T10:00:02.000Z"
    if add_observation:
        candidate["observations"].append(_observation(1))
    rejected = _put(client, candidate, headers={"If-Match": created.headers["ETag"]})

    assert rejected.status_code == 422
    assert expected_error in rejected.json["error"].lower()


def test_cursor_cannot_advance_after_retracting_its_only_active_response(calibration_host):
    _, client = calibration_host
    session = _session()
    prior = _observation(1)
    session["observations"] = [prior]
    session["updatedAt"] = prior["recordedAt"]
    created = _put(client, session, headers={"If-None-Match": "*"})
    assert created.status_code == 201, created.json

    candidate = deepcopy(session)
    candidate["currentMovement"] = 2
    candidate["actions"] = [{
        "sequence": 2,
        "actionId": str(uuid4()),
        "targetObservationId": prior["observationId"],
        "action": "retract",
        "recordedAt": "2026-10-01T10:00:03.000Z",
    }]
    candidate["updatedAt"] = "2026-10-01T10:00:03.000Z"
    rejected = _put(client, candidate, headers={"If-Match": created.headers["ETag"]})

    assert rejected.status_code == 422
    assert "needs a response" in rejected.json["error"].lower()


def test_skipped_calibration_is_terminal(calibration_host):
    _, client = calibration_host
    session = _session()
    session["status"] = "skipped"
    session["skip"] = {
        "movement": 1,
        "reason": "skip-calibration",
        "skippedAt": "2026-10-01T10:00:01.000Z",
    }
    created = _put(client, session, headers={"If-None-Match": "*"})
    assert created.status_code == 201
    changed = deepcopy(session)
    changed["status"] = "in-progress"
    changed.pop("skip")
    changed["updatedAt"] = "2026-10-01T10:00:02.000Z"
    rejected = _put(client, changed, headers={"If-Match": created.headers["ETag"]})
    assert rejected.status_code == 422
    assert "terminal calibration" in rejected.json["error"].lower()


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda value: value["observations"].__setitem__(0, {**value["observations"][0], "response": {"kind": "pass"}}), "immutable"),
        (lambda value: value["observations"][0]["offered"][1].update(stimulusId="not-in-catalog"), "stimulus"),
        (lambda value: value["observations"][0]["offered"][1].update(stimulusVersion="999"), "version"),
        (lambda value: value["observations"][0]["response"].update(chosenIds=["not-offered"]), "invalid"),
    ],
)
def test_invalid_catalog_choice_and_rewritten_history_are_rejected(calibration_host, mutate, message):
    _, client = calibration_host
    session = _session()
    session["observations"] = [_observation(1)]
    session["updatedAt"] = "2026-10-01T10:00:02.000Z"
    created = _put(client, session, headers={"If-None-Match": "*"})
    assert created.status_code == 201, created.json
    candidate = deepcopy(session)
    candidate["observations"][0]["recordedAt"] = "2026-10-01T10:00:01.500Z"
    candidate["updatedAt"] = "2026-10-01T10:00:03.000Z"
    mutate(candidate)
    rejected = _put(client, candidate, headers={"If-Match": created.headers["ETag"]})
    assert rejected.status_code == 422
    assert message.lower() in rejected.json["error"].lower()


def test_global_sequence_and_origin_are_enforced(calibration_host):
    _, client = calibration_host
    session = _session()
    session["observations"] = [_observation(2)]
    session["updatedAt"] = "2026-10-01T10:00:02.000Z"
    rejected = _put(client, session, headers={"If-None-Match": "*"})
    assert rejected.status_code == 422
    assert "globally contiguous" in rejected.json["error"]

    session = _session()
    rejected = client.put(
        f"/api/future/calibrations/{session['calibrationId']}",
        json=session,
        headers={"If-None-Match": "*", "Origin": "https://attacker.example"},
    )
    assert rejected.status_code == 403


def test_oversized_body_is_rejected_before_json_decode(calibration_host):
    _, client = calibration_host
    calibration_id = str(uuid4())
    response = client.put(
        f"/api/future/calibrations/{calibration_id}",
        data=b" " * (1024 * 1024 + 1),
        content_type="application/json",
        headers={"If-None-Match": "*"},
    )
    assert response.status_code == 413


def test_calibration_record_is_a_single_json_document(calibration_host):
    api, client = calibration_host
    session = _session()
    assert _put(client, session, headers={"If-None-Match": "*"}).status_code == 201
    with api.app.app_context():
        record = api.db.session.get(CalibrationSessionRecord, session["calibrationId"])
        assert record.revision == 1
        assert record.payload == session
