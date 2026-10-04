"""The personal export is stable, read-only, and profile-isolated."""

import sqlite3
from uuid import uuid4

from sqlalchemy import event

from tests.test_api_isolated import api, no_network  # noqa: F401
from src.crossword.calibration_api import CalibrationSessionRecord
from src.crossword.calibration_hypothesis_api import (
    CalibrationHypothesisActionRecord,
    CalibrationHypothesisDeckRecord,
    CalibrationHypothesisResponseRecord,
)
from src.crossword.episteme_store import EpistemeProfileRecord
from src.crossword.future import StartingProfile
from src.crossword.future_grid_jobs import (
    FutureGridDraftJob,
    FutureGridDraftPrivateSelection,
)
from src.crossword.future_puzzles import (
    FuturePuzzleManifestRecord,
    FutureSolveAnalysisRecord,
)
from src.crossword import profile_export
from src.crossword.reflection_api import (
    FutureReflectionActionRecord,
    FutureReflectionDeckRecord,
    FutureReflectionResponseRecord,
)
from src.crossword.session_journal import PersonalSolveEvent, PersonalSolveSession


def _seed_profile_data(module):
    first_id, second_id = str(uuid4()), str(uuid4())
    calibration_id, other_calibration_id = str(uuid4()), str(uuid4())
    session_id, other_session_id = str(uuid4()), str(uuid4())
    deck_id, proposal_id, response_id = str(uuid4()), str(uuid4()), str(uuid4())
    action_id, reflection_response_id, reflection_action_id = (
        str(uuid4()),
        str(uuid4()),
        str(uuid4()),
    )
    first_grid_job_id, second_grid_job_id = str(uuid4()), str(uuid4())
    puzzle_hash, other_puzzle_hash = "a" * 64, "b" * 64

    with module.app.app_context():
        module.db.session.add_all(
            [
                StartingProfile(
                    id=first_id,
                    draft={"object": "thread", "rawChoice": "first-user-choice"},
                    profile={"associations": ["echo"], "profileOwner": first_id},
                    updated_at="2026-09-01T00:00:00Z",
                ),
                StartingProfile(
                    id=second_id,
                    draft={"object": "stone", "rawChoice": "other-user-choice"},
                    profile={"associations": ["granite"], "profileOwner": second_id},
                    updated_at="2026-09-02T00:00:00Z",
                ),
                EpistemeProfileRecord(
                    id=first_id,
                    revision=3,
                    profile_json={
                        "profileId": first_id,
                        "evidence": [{"phrase": "first-personal-evidence"}],
                    },
                    updated_at="2026-09-03T00:00:00Z",
                ),
                CalibrationSessionRecord(
                    id=calibration_id,
                    revision=2,
                    payload={
                        "schemaVersion": 1,
                        "calibrationId": calibration_id,
                        "scope": {"kind": "profile", "profileId": first_id},
                        "observations": [
                            {
                                "stimulusId": "word-hush",
                                "raw": "first-calibration-observation",
                            }
                        ],
                        "actions": [],
                    },
                ),
                CalibrationSessionRecord(
                    id=other_calibration_id,
                    revision=1,
                    payload={
                        "schemaVersion": 1,
                        "calibrationId": other_calibration_id,
                        "scope": {"kind": "profile", "profileId": second_id},
                        "observations": [
                            {
                                "stimulusId": "word-hush",
                                "raw": "second-calibration-observation",
                            }
                        ],
                        "actions": [],
                    },
                ),
                CalibrationHypothesisDeckRecord(
                    calibration_id=calibration_id,
                    source_digest="c" * 64,
                    deck_id=deck_id,
                    profile_id=first_id,
                    deck_json={
                        "deckId": deck_id,
                        "calibrationId": calibration_id,
                        "sourceDigest": "private-deck-source-digest",
                        "items": [
                            {
                                "proposalId": proposal_id,
                                "phrase": "first-generated-path",
                            }
                        ],
                    },
                    deck_hash="d" * 64,
                    generation_metadata={
                        "provider": "ollama-loopback",
                        "requestedModel": "qwen-test",
                        "returnedModel": "qwen-test",
                        "digest": "private-model-weight-digest",
                        "format": "calibration-association-paths-v1",
                    },
                    created_at="2026-09-04T00:00:00Z",
                    status="complete",
                    profile_revision=4,
                ),
                CalibrationHypothesisResponseRecord(
                    response_id=response_id,
                    calibration_id=calibration_id,
                    deck_id=deck_id,
                    proposal_id=proposal_id,
                    request_hash="e" * 64,
                    response_json={
                        "response": "keep",
                        "authored": "first-hypothesis-response",
                    },
                    evidence_json={
                        "type": "association-proposal",
                        "phrase": "first-hypothesis-evidence",
                    },
                    episteme_revision=4,
                    status="complete",
                    recorded_at="2026-09-04T00:01:00Z",
                ),
                CalibrationHypothesisActionRecord(
                    action_id=action_id,
                    calibration_id=calibration_id,
                    deck_id=deck_id,
                    proposal_id=proposal_id,
                    response_id=response_id,
                    request_hash="f" * 64,
                    action_json={
                        "action": "retract",
                        "authored": "first-hypothesis-action",
                    },
                    evidence_action_json={
                        "type": "withdrawal",
                        "authored": "first-hypothesis-correction",
                    },
                    episteme_revision=5,
                    status="complete",
                    recorded_at="2026-09-04T00:02:00Z",
                ),
                FuturePuzzleManifestRecord(
                    puzzle_hash=puzzle_hash,
                    puzzle_id="shared-puzzle-240101",
                    manifest_json={
                        "answer": "shared-answer-must-not-export",
                        "clue": "shared-clue-must-not-export",
                    },
                    created_at="2026-09-01T00:00:00Z",
                ),
                FuturePuzzleManifestRecord(
                    puzzle_hash=other_puzzle_hash,
                    puzzle_id="other-shared-puzzle",
                    manifest_json={"answer": "other-answer-must-not-export"},
                    created_at="2026-09-02T00:00:00Z",
                ),
                PersonalSolveSession(
                    id=session_id,
                    profile_id=first_id,
                    puzzle_hash=puzzle_hash,
                    initial_grid=[{"cellId": "r0c0", "value": "A"}],
                    writer_digest="private-writer-capability-digest",
                    accepted_seq=1,
                    status="finished",
                    created_at="2026-09-05T00:00:00Z",
                    updated_at="2026-09-05T00:01:00Z",
                ),
                PersonalSolveSession(
                    id=other_session_id,
                    profile_id=second_id,
                    puzzle_hash=other_puzzle_hash,
                    initial_grid=[{"cellId": "r0c0", "value": "B"}],
                    writer_digest="other-private-writer-capability-digest",
                    accepted_seq=0,
                    status="active",
                    created_at="2026-09-06T00:00:00Z",
                    updated_at="2026-09-06T00:00:00Z",
                ),
                PersonalSolveEvent(
                    session_id=session_id,
                    seq=1,
                    event_id=str(uuid4()),
                    payload={
                        "type": "cell-written",
                        "afterToken": "A",
                        "authored": "first-solve-event",
                    },
                    payload_hash="1" * 64,
                    recorded_at="2026-09-05T00:00:30Z",
                ),
                PersonalSolveEvent(
                    session_id=other_session_id,
                    seq=1,
                    event_id=str(uuid4()),
                    payload={
                        "type": "cell-written",
                        "afterToken": "B",
                        "authored": "second-solve-event",
                    },
                    payload_hash="2" * 64,
                    recorded_at="2026-09-06T00:00:30Z",
                ),
                FutureSolveAnalysisRecord(
                    session_id=session_id,
                    puzzle_hash=puzzle_hash,
                    analysis_version="knowledge-reducer-v1",
                    analysis_json={
                        "observations": [
                            {
                                "outcome": "supported-retrieval",
                                "authored": "first-analysis",
                            }
                        ]
                    },
                    finalized=True,
                    updated_at="2026-09-05T00:02:00Z",
                ),
                FutureSolveAnalysisRecord(
                    session_id=other_session_id,
                    puzzle_hash=other_puzzle_hash,
                    analysis_version="knowledge-reducer-v1",
                    analysis_json={"observations": [{"authored": "second-analysis"}]},
                    finalized=False,
                    updated_at="2026-09-06T00:02:00Z",
                ),
                FutureReflectionDeckRecord(
                    session_id=session_id,
                    deck_version=1,
                    deck_json={
                        "cards": [{"id": "card-one", "text": "first-reflection-card"}]
                    },
                    deck_hash="3" * 64,
                    created_at="2026-09-05T00:03:00Z",
                ),
                FutureReflectionResponseRecord(
                    response_id=reflection_response_id,
                    session_id=session_id,
                    card_id="card-one",
                    response_hash="4" * 64,
                    response_json={
                        "response": "keep",
                        "authored": "first-reflection-response",
                    },
                    evidence_json={
                        "type": "preference-signal",
                        "authored": "first-reflection-evidence",
                    },
                    episteme_revision=6,
                    status="complete",
                    recorded_at="2026-09-05T00:04:00Z",
                ),
                FutureReflectionActionRecord(
                    action_id=reflection_action_id,
                    session_id=session_id,
                    card_id="card-one",
                    target_response_id=reflection_response_id,
                    action_hash="5" * 64,
                    action_json={
                        "action": "retract",
                        "authored": "first-reflection-action",
                    },
                    evidence_action_json={
                        "target": "response",
                        "authored": "first-reflection-action-evidence",
                    },
                    episteme_revision=7,
                    status="complete",
                    recorded_at="2026-09-05T00:05:00Z",
                ),
                FutureGridDraftJob(
                    id=first_grid_job_id,
                    profile_id=first_id,
                    idempotency_key=str(uuid4()),
                    request_digest="6" * 64,
                    request_json={
                        "seed": 31,
                        "profileDigest": "private-profile-digest",
                        "lease_token": "nested-capability-secret",
                        "recipe": "xfill-wide-v1",
                    },
                    state="ready",
                    attempt=1,
                    lease_token="private-worker-lease-capability",
                    lease_until="2026-09-05T00:10:00Z",
                    cancel_requested=False,
                    result_json={
                        "sourceDigest": "private-worker-source-digest",
                        "grid": {"fill": ["first-generated-grid"]},
                    },
                    error=None,
                    created_at="2026-09-05T00:06:00Z",
                    updated_at="2026-09-05T00:07:00Z",
                ),
                FutureGridDraftJob(
                    id=second_grid_job_id,
                    profile_id=second_id,
                    idempotency_key=str(uuid4()),
                    request_digest="7" * 64,
                    request_json={"seed": 99, "profileDigest": "other-profile-digest"},
                    state="queued",
                    attempt=0,
                    lease_token=None,
                    lease_until=None,
                    cancel_requested=False,
                    result_json=None,
                    error=None,
                    created_at="2026-09-06T00:06:00Z",
                    updated_at="2026-09-06T00:06:00Z",
                ),
                FutureGridDraftPrivateSelection(
                    job_id=first_grid_job_id,
                    profile_id=first_id,
                    selection_json={
                        "profileEvidenceIds": ["first-private-evidence-id"],
                        "selectedClueIds": ["clue-first-user"],
                        "lease_token": "private-sidecar-lease-secret",
                    },
                    created_at="2026-09-05T00:07:30Z",
                ),
                FutureGridDraftPrivateSelection(
                    job_id=second_grid_job_id,
                    profile_id=second_id,
                    selection_json={
                        "profileEvidenceIds": ["second-private-evidence-id"],
                        "selectedClueIds": ["clue-second-user"],
                    },
                    created_at="2026-09-06T00:07:30Z",
                ),
            ]
        )
        module.db.session.commit()

    return first_id, second_id


def test_export_is_complete_stable_profile_scoped_and_redacts_worker_secrets(api):
    first_id, second_id = _seed_profile_data(api)
    client = api.app.test_client()
    url = f"/api/future/profile/{first_id}/export"

    first = client.get(url)
    second = client.get(url)

    assert first.status_code == second.status_code == 200
    assert first.cache_control.no_store
    assert first.data == second.data
    exported = first.get_json()
    assert exported["format"] == "crossword-personal-episteme-export"
    assert exported["schemaVersion"] == 2
    assert exported["profileId"] == first_id
    assert exported["startingProfile"]["draft"]["rawChoice"] == "first-user-choice"
    assert exported["episteme"]["revision"] == 3
    assert (
        exported["episteme"]["profile"]["evidence"][0]["phrase"]
        == "first-personal-evidence"
    )
    assert (
        exported["calibrations"][0]["payload"]["observations"][0]["raw"]
        == "first-calibration-observation"
    )

    hypotheses = exported["calibrationHypotheses"]
    assert (
        hypotheses["decks"][0]["deck"]["items"][0]["phrase"] == "first-generated-path"
    )
    assert hypotheses["decks"][0]["generation"]["requestedModel"] == "qwen-test"
    assert (
        hypotheses["responses"][0]["response"]["authored"]
        == "first-hypothesis-response"
    )
    assert hypotheses["actions"][0]["action"]["authored"] == "first-hypothesis-action"

    assert len(exported["solveSessions"]) == 1
    session = exported["solveSessions"][0]
    assert session["puzzle"] == {
        "puzzleId": "shared-puzzle-240101",
        "puzzleHash": "a" * 64,
    }
    assert session["events"][0]["payload"]["authored"] == "first-solve-event"
    assert (
        session["analysis"]["analysis"]["observations"][0]["authored"]
        == "first-analysis"
    )
    assert session["reflections"]["deck"]["cards"][0]["text"] == "first-reflection-card"
    assert (
        session["reflections"]["responses"][0]["response"]["authored"]
        == "first-reflection-response"
    )
    assert (
        session["reflections"]["actions"][0]["action"]["authored"]
        == "first-reflection-action"
    )

    assert len(exported["gridDraftJobs"]) == 1
    job = exported["gridDraftJobs"][0]
    assert job["result"]["grid"]["fill"] == ["first-generated-grid"]
    assert job["result"]["sourceDigest"] == "private-worker-source-digest"
    assert job["request"]["profileDigest"] == "private-profile-digest"
    assert job["requestDigest"] == "6" * 64
    assert job["privateSelection"] == {
        "selection": {
            "profileEvidenceIds": ["first-private-evidence-id"],
            "selectedClueIds": ["clue-first-user"],
        },
        "createdAt": "2026-09-05T00:07:30Z",
        "provenance": {"table": "future_grid_draft_private_selections"},
    }
    assert (
        "future_grid_draft_private_selections" in exported["provenance"]["collections"]
    )
    assert hypotheses["decks"][0]["sourceDigest"] == "c" * 64
    assert (
        hypotheses["decks"][0]["deck"]["sourceDigest"] == "private-deck-source-digest"
    )
    assert (
        hypotheses["decks"][0]["generation"]["digest"] == "private-model-weight-digest"
    )

    serialized = first.get_data(as_text=True)
    for excluded in (
        second_id,
        "second-user-choice",
        "second-calibration-observation",
        "second-solve-event",
        "second-analysis",
        "private-writer-capability-digest",
        "private-worker-lease-capability",
        "nested-capability-secret",
        "private-sidecar-lease-secret",
        "second-private-evidence-id",
        "clue-second-user",
        "shared-answer-must-not-export",
        "shared-clue-must-not-export",
        "other-answer-must-not-export",
    ):
        assert excluded not in serialized

    other_export = client.get(f"/api/future/profile/{second_id}/export")
    assert other_export.status_code == 200
    other_jobs = other_export.json["gridDraftJobs"]
    assert len(other_jobs) == 1
    assert other_jobs[0]["privateSelection"]["selection"]["profileEvidenceIds"] == [
        "second-private-evidence-id"
    ]
    assert "first-private-evidence-id" not in other_export.get_data(as_text=True)


def test_export_errors_are_canonical_origin_checked_bounded_and_read_only(api):
    first_id, _ = _seed_profile_data(api)
    client = api.app.test_client()

    assert client.get("/api/future/profile/not-a-uuid/export").status_code == 400
    assert (
        client.get(f"/api/future/profile/{first_id.upper()}/export").status_code == 400
    )
    assert client.get(f"/api/future/profile/{uuid4()}/export").status_code == 404
    foreign = client.get(
        f"/api/future/profile/{first_id}/export",
        headers={"Origin": "https://attacker.invalid"},
    )
    assert foreign.status_code == 403
    assert foreign.cache_control.no_store

    large_profile_id = str(uuid4())
    with api.app.app_context():
        api.db.session.add(
            StartingProfile(
                id=large_profile_id,
                draft={"large": "x" * (9 * 1024 * 1024)},
                profile={},
                updated_at="2026-09-07T00:00:00Z",
            )
        )
        api.db.session.commit()
        assert api.db.session.get(EpistemeProfileRecord, large_profile_id) is None

    large = client.get(f"/api/future/profile/{large_profile_id}/export")
    assert large.status_code == 200
    assert large.json["startingProfile"]["draft"]["large"] == "x" * (9 * 1024 * 1024)
    with api.app.app_context():
        assert api.db.session.get(EpistemeProfileRecord, large_profile_id) is None

    small_id = str(uuid4())
    with api.app.app_context():
        api.db.session.add(
            StartingProfile(
                id=small_id,
                draft={"object": "bell"},
                profile={},
                updated_at="2026-09-08T00:00:00Z",
            )
        )
        api.db.session.commit()
    small = client.get(f"/api/future/profile/{small_id}/export")
    assert small.status_code == 200
    assert small.json["episteme"] is None
    with api.app.app_context():
        assert api.db.session.get(EpistemeProfileRecord, small_id) is None


def test_export_holds_one_sqlite_snapshot_while_a_writer_attempts_an_update(api):
    profile_id = str(uuid4())
    with api.app.app_context():
        api.db.session.add(
            StartingProfile(
                id=profile_id,
                draft={"epoch": 1},
                profile={"epoch": 1},
                updated_at="2026-09-09T00:00:00Z",
            )
        )
        api.db.session.add(
            EpistemeProfileRecord(
                id=profile_id,
                revision=1,
                profile_json={"epoch": 1},
                updated_at="2026-09-09T00:00:00Z",
            )
        )
        api.db.session.commit()

    writer_was_blocked = []
    with api.app.app_context():
        engine = api.db.engine
        database_path = engine.url.database

    def try_concurrent_update(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ):
        if "FROM future_episteme_profiles" not in statement:
            return
        connection = sqlite3.connect(database_path, timeout=0.01, isolation_level=None)
        try:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE future_starting_profiles SET profile = ? WHERE id = ?",
                    ('{"epoch":2}', profile_id),
                )
                connection.execute(
                    "UPDATE future_episteme_profiles SET profile_json = ?, revision = 2 WHERE id = ?",
                    ('{"epoch":2}', profile_id),
                )
                connection.commit()
            except sqlite3.OperationalError as error:
                connection.rollback()
                writer_was_blocked.append("locked" in str(error).lower())
        finally:
            connection.close()

    event.listen(engine, "before_cursor_execute", try_concurrent_update)
    try:
        response = api.app.test_client().get(f"/api/future/profile/{profile_id}/export")
    finally:
        event.remove(engine, "before_cursor_execute", try_concurrent_update)

    assert response.status_code == 200
    assert writer_was_blocked == [True]
    assert response.json["startingProfile"]["profile"]["epoch"] == 1
    assert response.json["episteme"]["profile"]["epoch"] == 1


def test_export_preflights_size_before_building_large_archive(api, monkeypatch):
    """An over-cap profile is rejected before the nested export is materialized."""
    profile_id = str(uuid4())
    with api.app.app_context():
        api.db.session.add(
            StartingProfile(
                id=profile_id,
                draft={"large": "x" * (17 * 1024 * 1024)},
                profile={},
                updated_at="2026-09-10T00:00:00Z",
            )
        )
        api.db.session.commit()

    def should_not_build(_profile_id):
        raise AssertionError(
            "the bounded preflight must reject before archive construction"
        )

    monkeypatch.setattr(profile_export, "_export_profile", should_not_build)
    response = api.app.test_client().get(f"/api/future/profile/{profile_id}/export")

    assert response.status_code == 413
    assert response.json["sizeCheck"] == "preflight"
    assert response.json["estimatedBytes"] > response.json["maxBytes"]
