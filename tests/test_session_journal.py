"""Journal API rejects invented provenance and accepts only idempotent appends."""

from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

import pytest
from werkzeug.test import EnvironBuilder

from tests.test_api_isolated import api, no_network  # noqa: F401
from tests.test_api_isolated import original_puzzle_text
from tests.test_future_api import draft
from src.crossword.session_journal import PersonalSolveEvent, _manifest_indexes
from src.crossword.future_puzzles import FutureSolveAnalysisRecord
from src.crossword.episteme_store import EpistemeProfileRecord
import src.crossword.session_journal as journal_module


def registered_manifest(api):
    puzzle = api.NYTFormatParser.parse(original_puzzle_text())
    with api.app.app_context():
        return api.register_legacy_puzzle(puzzle)


def event(session_id, profile_id, puzzle_hash, seq, event_type, **payload):
    return {
        "schemaVersion": 2,
        "eventId": str(uuid4()),
        "sessionId": session_id,
        "profileId": profile_id,
        "segmentId": str(uuid4()),
        "seq": seq,
        "elapsedMs": seq * 100,
        "recordedAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "puzzleHash": puzzle_hash,
        "type": event_type,
        **payload,
    }


def test_manifest_indexes_accept_private_multi_unit_answer_tokens():
    from src.crossword.legacy_manifest import to_puzzle_document

    source = {
        "metadata": {
            "date": "260928",
            "title": "Token fixture",
            "authors": ["local"],
            "width": 1,
            "height": 1,
        },
        "entries": [
            {
                "clue_number": 1,
                "clue_text": "Across token",
                "direction": "across",
                "start_x": 0,
                "start_y": 0,
                "characters": [{"letters": "SS"}],
            },
            {
                "clue_number": 1,
                "clue_text": "Down token",
                "direction": "down",
                "start_x": 0,
                "start_y": 0,
                "characters": [{"letters": "SS"}],
            },
        ],
    }
    manifest = to_puzzle_document(source, allow_token_cells=True)

    _open_cells, _entry_cells, answers_by_cell = _manifest_indexes(manifest)

    assert answers_by_cell == {"r0c0": "SS"}


def begin(api, client):
    profile = draft()
    profile_id = profile["id"]
    assert (
        client.put(
            f"/api/future/profile/{profile_id}",
            json=profile,
            headers={"If-None-Match": "*"},
        ).status_code
        == 200
    )
    session_id = str(uuid4())
    manifest = registered_manifest(api)
    puzzle_hash = manifest["integrity"]["value"]
    writer_token = "session-capability-" + str(uuid4())
    session = {
        "sessionId": session_id,
        "profileId": profile_id,
        "puzzleHash": puzzle_hash,
        "initialGrid": [
            {"cellId": cell["id"], "token": None, "origin": "unknown"}
            for cell in manifest["cells"]
            if not cell["block"]
        ],
        "writerToken": writer_token,
    }
    response = client.post("/api/future/sessions", json=session)
    assert response.status_code == 201
    return profile_id, session_id, puzzle_hash, writer_token


def test_session_journal_accepts_persisted_events_and_retries_idempotently(api):
    client = api.app.test_client()
    profile_id, session_id, puzzle_hash, writer_token = begin(api, client)
    start = event(
        session_id, profile_id, puzzle_hash, 1, "session-started", reason="fresh"
    )
    write = event(
        session_id,
        profile_id,
        puzzle_hash,
        2,
        "cell-written",
        cellId="r0c0",
        beforeToken=None,
        afterToken="C",
        activeEntryId="across-1",
        actionId=str(uuid4()),
        source="keyboard",
    )
    response = client.post(
        f"/api/future/sessions/{session_id}/events",
        json={
            "expectedSeq": 0,
            "writerToken": writer_token,
            "events": [start, write],
        },
    )
    assert response.status_code == 200, response.json
    assert response.json["acceptedSeq"] == 2
    assert response.json["acceptedEventIds"] == [start["eventId"], write["eventId"]]
    assert response.json["duplicateEventIds"] == []
    assert response.cache_control.no_store

    retry = client.post(
        f"/api/future/sessions/{session_id}/events",
        json={
            "expectedSeq": 0,
            "writerToken": writer_token,
            "events": [start, write],
        },
    )
    assert retry.status_code == 200
    assert retry.json["acceptedSeq"] == 2
    assert retry.json["acceptedEventIds"] == []
    assert retry.json["duplicateEventIds"] == [start["eventId"], write["eventId"]]
    with api.app.app_context():
        rows = (
            api.db.session.query(PersonalSolveEvent)
            .filter_by(session_id=session_id)
            .all()
        )
        assert [(row.seq, row.event_id) for row in rows] == [
            (1, start["eventId"]),
            (2, write["eventId"]),
        ]
        analysis = api.db.session.get(FutureSolveAnalysisRecord, session_id)
        assert analysis.analysis_version == "knowledge-reducer-v1"
        assert analysis.finalized is False
        assert len(analysis.analysis_json["observations"]) == 6


def test_session_journal_accepts_prepared_hint_evidence_and_validates_scope(api):
    client = api.app.test_client()
    profile_id, session_id, puzzle_hash, writer_token = begin(api, client)
    start = event(
        session_id, profile_id, puzzle_hash, 1, "session-started", reason="fresh"
    )
    hint = event(
        session_id,
        profile_id,
        puzzle_hash,
        2,
        "hint-shown",
        entryId="across-1",
        hintId="prepared-clue-reading-v1",
        assistanceTier="clue-reading",
        affectedCellIds=[],
    )
    response = client.post(
        f"/api/future/sessions/{session_id}/events",
        json={
            "expectedSeq": 0,
            "writerToken": writer_token,
            "events": [start, hint],
        },
    )
    assert response.status_code == 200, response.json
    assert response.json["acceptedSeq"] == 2

    invalid = {**hint, "eventId": str(uuid4()), "seq": 3, "affectedCellIds": ["r9c9"]}
    response = client.post(
        f"/api/future/sessions/{session_id}/events",
        json={
            "expectedSeq": 2,
            "writerToken": writer_token,
            "events": [invalid],
        },
    )
    assert response.status_code == 422
    assert "invalid cell" in response.json["error"].lower()


def test_session_journal_rejects_forgery_wrong_writer_and_sequence_conflicts(api):
    client = api.app.test_client()
    profile_id, session_id, puzzle_hash, writer_token = begin(api, client)
    start = event(
        session_id, profile_id, puzzle_hash, 1, "session-started", reason="fresh"
    )
    assert (
        client.post(
            f"/api/future/sessions/{session_id}/events",
            json={
                "expectedSeq": 0,
                "writerToken": "x" * 40,
                "events": [start],
            },
        ).status_code
        == 403
    )

    bad_profile = {**start, "eventId": str(uuid4()), "profileId": str(uuid4())}
    response = client.post(
        f"/api/future/sessions/{session_id}/events",
        json={
            "expectedSeq": 0,
            "writerToken": writer_token,
            "events": [bad_profile],
        },
    )
    assert response.status_code == 422

    assert (
        client.post(
            f"/api/future/sessions/{session_id}/events",
            json={
                "expectedSeq": 0,
                "writerToken": writer_token,
                "events": [start],
            },
        ).status_code
        == 200
    )
    conflicting = {**start, "eventId": str(uuid4())}
    response = client.post(
        f"/api/future/sessions/{session_id}/events",
        json={
            "expectedSeq": 0,
            "writerToken": writer_token,
            "events": [conflicting],
        },
    )
    assert response.status_code == 409
    assert response.json["error"] == "Sequence conflicts with accepted event"
    assert response.json.get("retryable") is not True
    assert (
        client.post(
            f"/api/future/sessions/{session_id}/events",
            json={
                "expectedSeq": 0,
                "writerToken": writer_token,
                "events": [start],
            },
            headers={"Origin": "https://other.invalid"},
        ).status_code
        == 403
    )


def test_session_journal_rebases_an_idempotent_prefix_with_new_events(api):
    client = api.app.test_client()
    profile_id, session_id, puzzle_hash, writer_token = begin(api, client)
    start = event(
        session_id, profile_id, puzzle_hash, 1, "session-started", reason="fresh"
    )
    write = event(
        session_id,
        profile_id,
        puzzle_hash,
        2,
        "cell-written",
        cellId="r0c0",
        beforeToken=None,
        afterToken="C",
        activeEntryId="across-1",
        actionId=str(uuid4()),
        source="keyboard",
    )
    first = client.post(
        f"/api/future/sessions/{session_id}/events",
        json={
            "expectedSeq": 0,
            "writerToken": writer_token,
            "events": [start],
        },
    )
    assert first.status_code == 200
    rebased = client.post(
        f"/api/future/sessions/{session_id}/events",
        json={
            "expectedSeq": 0,
            "writerToken": writer_token,
            "events": [start, write],
        },
    )
    assert rebased.status_code == 200, rebased.json
    assert rebased.json["acceptedSeq"] == 2
    assert rebased.json["duplicateEventIds"] == [start["eventId"]]
    assert rebased.json["acceptedEventIds"] == [write["eventId"]]


def test_session_journal_rejects_event_cells_outside_the_frozen_grid(api):
    client = api.app.test_client()
    profile_id, session_id, puzzle_hash, writer_token = begin(api, client)
    start = event(
        session_id, profile_id, puzzle_hash, 1, "session-started", reason="fresh"
    )
    write = event(
        session_id,
        profile_id,
        puzzle_hash,
        2,
        "cell-written",
        cellId="r9c9",
        beforeToken=None,
        afterToken="C",
        activeEntryId="across-1",
        actionId=str(uuid4()),
        source="keyboard",
    )
    response = client.post(
        f"/api/future/sessions/{session_id}/events",
        json={
            "expectedSeq": 0,
            "writerToken": writer_token,
            "events": [start, write],
        },
    )
    assert response.status_code == 422
    assert response.json["error"] == "Invalid cell edit"


def test_session_journal_rejects_client_forged_check_and_reveal_truth(api):
    client = api.app.test_client()
    profile_id, session_id, puzzle_hash, writer_token = begin(api, client)
    start = event(
        session_id, profile_id, puzzle_hash, 1, "session-started", reason="fresh"
    )
    forged_check = event(
        session_id,
        profile_id,
        puzzle_hash,
        2,
        "check-result-shown",
        scope="entry",
        entryId="across-1",
        results=[
            {"cellId": "r0c0", "token": "C", "classification": "incorrect"},
            {"cellId": "r0c1", "token": None, "classification": "blank"},
            {"cellId": "r0c2", "token": None, "classification": "blank"},
        ],
    )
    response = client.post(
        f"/api/future/sessions/{session_id}/events",
        json={
            "expectedSeq": 0,
            "writerToken": writer_token,
            "events": [start, forged_check],
        },
    )
    assert response.status_code == 422
    assert "classification disagrees" in response.json["error"]

    profile_id, session_id, puzzle_hash, writer_token = begin(api, client)
    start = event(
        session_id, profile_id, puzzle_hash, 1, "session-started", reason="fresh"
    )
    forged_reveal = event(
        session_id,
        profile_id,
        puzzle_hash,
        2,
        "answer-revealed",
        scope="cell",
        entryId="across-1",
        cells=[{"cellId": "r0c0", "beforeToken": None, "token": "X"}],
    )
    response = client.post(
        f"/api/future/sessions/{session_id}/events",
        json={
            "expectedSeq": 0,
            "writerToken": writer_token,
            "events": [start, forged_reveal],
        },
    )
    assert response.status_code == 422
    assert "Revealed token disagrees" in response.json["error"]


def test_finished_session_persists_manifest_replay_analysis(api):
    client = api.app.test_client()
    profile_id, session_id, puzzle_hash, writer_token = begin(api, client)
    entries = [
        event(
            session_id, profile_id, puzzle_hash, 1, "session-started", reason="fresh"
        ),
        event(
            session_id,
            profile_id,
            puzzle_hash,
            2,
            "entry-focused",
            entryId="across-1",
            variantId=None,
            reason="keyboard",
            visiblePattern=[
                {
                    "cellId": f"r0c{column}",
                    "token": None,
                    "origin": "unknown",
                    "sourceEntryId": None,
                }
                for column in range(3)
            ],
        ),
    ]
    for seq, (column, token) in enumerate(zip(range(3), "CAT", strict=True), start=3):
        entries.append(
            event(
                session_id,
                profile_id,
                puzzle_hash,
                seq,
                "cell-written",
                cellId=f"r0c{column}",
                beforeToken=None,
                afterToken=token,
                activeEntryId="across-1",
                actionId=str(uuid4()),
                source="keyboard",
            )
        )
    entries.append(
        event(
            session_id, profile_id, puzzle_hash, 6, "session-finished", reason="stopped"
        )
    )

    response = client.post(
        f"/api/future/sessions/{session_id}/events",
        json={"expectedSeq": 0, "writerToken": writer_token, "events": entries},
    )
    assert response.status_code == 200, response.json
    assert response.json["status"] == "finished"
    with api.app.app_context():
        analysis = api.db.session.get(FutureSolveAnalysisRecord, session_id)
        assert analysis.finalized is True
        across = next(
            item
            for item in analysis.analysis_json["observations"]
            if item["entryId"] == "across-1"
        )
        assert across["finalState"] == "correct"
        assert across["outcome"] == "independent-retrieval"
        profile = api.db.session.get(EpistemeProfileRecord, profile_id)
        assert profile.revision == 1
        assert len(profile.profile_json["evidence"]) == 1
        assert profile.profile_json["evidence"][0]["type"] == "session-analysis"
        assert profile.profile_json["evidence"][0]["analysis"] == analysis.analysis_json


def test_private_manifest_links_exposure_only_answer_tasks():
    manifest = {
        "subtitle": "Private local generation · Wednesday",
        "entries": [{"id": "across-1", "answer": "RESONANCE"}],
    }
    analysis = {"observations": [{"entryId": "across-1"}]}

    links = journal_module._private_task_links(manifest, analysis)

    assert links == [
        {
            "entryId": "across-1",
            "tasks": [
                {
                    "taskId": "private-answer-form:RESONANCE",
                    "taskKind": "answer-form",
                    "direction": "clue-to-answer",
                    "language": "en",
                    "clueFamily": "private-local-generated",
                    "contentReview": "unreviewed",
                }
            ],
        }
    ]
    assert (
        journal_module._private_task_links(
            {
                "subtitle": "Imported crossword",
                "entries": manifest["entries"],
            },
            analysis,
        )
        == []
    )


@pytest.mark.parametrize("clue", ["German for hello", "Hello in German"])
def test_private_manifest_links_explicit_language_clue_wording(clue):
    links = journal_module._private_task_links(
        {
            "subtitle": "Private local generation · language thread: German",
            "entries": [{"id": "across-1", "answer": "HALLO", "clue": clue}],
        },
        {"observations": [{"entryId": "across-1"}]},
    )

    assert links[0]["tasks"][0]["language"] == "de"
    assert links[0]["tasks"][0]["clueFamily"] == "language-recurrence"


def test_private_manifest_carries_task_pack_receipt_for_a_known_language_pair():
    links = journal_module._private_task_links(
        {
            "subtitle": "Private local generation · language thread: German",
            "entries": [{"id": "across-1", "answer": "JA", "clue": "German for yes"}],
        },
        {"observations": [{"entryId": "across-1"}]},
    )

    task_pack = links[0]["tasks"][0]["taskPack"]
    assert task_pack["pairId"] == "de-en-ja-v1"
    assert task_pack["sourceText"] == "yes"
    assert "targetText" not in task_pack
    assert task_pack["semanticStatus"] == "not-established"


def test_finish_profile_cas_conflict_is_retryable_and_atomic(api, monkeypatch):
    import src.crossword.session_journal as journal_module

    client = api.app.test_client()
    profile_id, session_id, puzzle_hash, writer_token = begin(api, client)
    batch = [
        event(
            session_id, profile_id, puzzle_hash, 1, "session-started", reason="fresh"
        ),
        event(
            session_id, profile_id, puzzle_hash, 2, "session-finished", reason="stopped"
        ),
    ]
    original = journal_module._record_final_analysis
    failed = False

    def stale_profile_once(*args):
        nonlocal failed
        if not failed:
            failed = True
            raise journal_module.EpistemeRevisionConflict(
                "Stale profile revision: injected finish race"
            )
        return original(*args)

    monkeypatch.setattr(journal_module, "_record_final_analysis", stale_profile_once)
    body = {"expectedSeq": 0, "writerToken": writer_token, "events": batch}
    conflict = client.post(f"/api/future/sessions/{session_id}/events", json=body)
    assert conflict.status_code == 409
    assert conflict.json["retryable"] is True
    with api.app.app_context():
        session = api.db.session.get(journal_module.PersonalSolveSession, session_id)
        assert session.status == "active"
        assert session.accepted_seq == 0
        assert (
            api.db.session.query(PersonalSolveEvent)
            .filter_by(session_id=session_id)
            .count()
            == 0
        )
        assert api.db.session.get(FutureSolveAnalysisRecord, session_id) is None

    monkeypatch.setattr(journal_module, "_record_final_analysis", original)
    recovered = client.post(f"/api/future/sessions/{session_id}/events", json=body)
    assert recovered.status_code == 200, recovered.json
    assert recovered.json["acceptedSeq"] == 2
    assert recovered.json["status"] == "finished"
    duplicate = client.post(f"/api/future/sessions/{session_id}/events", json=body)
    assert duplicate.status_code == 200
    assert duplicate.json["duplicateEventIds"] == [item["eventId"] for item in batch]
    with api.app.app_context():
        session = api.db.session.get(journal_module.PersonalSolveSession, session_id)
        rows = (
            api.db.session.query(PersonalSolveEvent)
            .filter_by(session_id=session_id)
            .all()
        )
        analysis = api.db.session.get(FutureSolveAnalysisRecord, session_id)
        profile = api.db.session.get(EpistemeProfileRecord, profile_id)
        assert session.status == "finished"
        assert session.accepted_seq == 2
        assert len(rows) == 2
        assert analysis.finalized is True
        assert (
            len(
                [
                    item
                    for item in profile.profile_json["evidence"]
                    if item["type"] == "session-analysis"
                ]
            )
            == 1
        )


@pytest.mark.parametrize(
    "path", ["/api/future/sessions", f"/api/future/sessions/{uuid4()}/events"]
)
def test_session_journal_request_limit_applies_without_content_length(api, path):
    environ = EnvironBuilder(
        path=path, method="POST", content_type="application/json"
    ).get_environ()
    environ["wsgi.input"] = BytesIO(b"{" + b" " * (256 * 1024) + b"}")
    environ.pop("CONTENT_LENGTH", None)
    environ["wsgi.input_terminated"] = True

    response = api.app.test_client().open(environ)

    assert response.status_code == 413


@pytest.mark.parametrize(
    "changes",
    [
        {
            "initialGrid": [
                {"cellId": "r0c0", "token": None, "origin": "unknown"},
                {"cellId": "r0c0", "token": None, "origin": "unknown"},
            ]
        },
        {"initialGrid": [{"cellId": "r0c0", "token": "A", "origin": "player"}]},
        {"puzzleHash": "bad"},
        {"sessionId": "not-a-uuid"},
    ],
)
def test_session_creation_validates_snapshot_and_origin(api, changes):
    client = api.app.test_client()
    profile = draft()
    client.put(
        f"/api/future/profile/{profile['id']}",
        json=profile,
        headers={"If-None-Match": "*"},
    )
    manifest = registered_manifest(api)
    initial_grid = [
        {"cellId": cell["id"], "token": None, "origin": "unknown"}
        for cell in manifest["cells"]
        if not cell["block"]
    ]
    value = {
        "sessionId": str(uuid4()),
        "profileId": profile["id"],
        "puzzleHash": manifest["integrity"]["value"],
        "initialGrid": initial_grid,
        "writerToken": "session-capability-" + str(uuid4()),
        **changes,
    }
    assert client.post("/api/future/sessions", json=value).status_code == 422
    assert (
        client.post(
            "/api/future/sessions",
            json={
                **value,
                **{
                    key: value[key]
                    for key in (
                        "sessionId",
                        "profileId",
                        "puzzleHash",
                        "initialGrid",
                        "writerToken",
                    )
                },
            },
            headers={"Origin": "http://elsewhere.invalid"},
        ).status_code
        == 403
    )
