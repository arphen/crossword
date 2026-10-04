"""The retrieval endpoint applies only pinned synthetic packs and host episteme evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from tests.test_api_isolated import api, no_network  # noqa: F401
from tests.test_admitted_pack_loader import _fixture, _resign
from tests.test_future_api import draft
from src.crossword.admitted_pack import canonical_json
from src.crossword.episteme_store import EpistemeProfileRecord


def _configured_pack(api, tmp_path, *, animals: bool = False):
    pack, pins = _fixture()
    if animals:
        animal = dict(pack["lexemes"][0])
        animal["id"] = "lexeme-cat"
        animal["headword"] = "CAT"
        animal["personalization"] = {"conceptIds": ["topic:animals"], "pool": "exploration"}
        pack["lexemes"][0]["personalization"] = {"conceptIds": [], "pool": "broad"}
        pack["lexemes"].append(animal)
        _resign(pack)
    path = tmp_path / "synthetic-retrieval-pack.json"
    raw = canonical_json(pack)
    path.write_bytes(raw)
    source_pins = {
        source_id: {
            "version": pin.version,
            "artifactSha256": pin.artifact_sha256,
            "contentClass": pin.content_class,
        }
        for source_id, pin in pins.items()
    }
    api.app.config.update(
        FUTURE_ADMITTED_PACK_PATH=str(path),
        FUTURE_ADMITTED_PACK_ID=pack["packId"],
        FUTURE_ADMITTED_PACK_SHA256=pack["artifactSha256"],
        FUTURE_ADMITTED_SOURCE_PINS_JSON=json.dumps(source_pins, separators=(",", ":")),
    )
    return pack, path


def _create_profile(client, *, weekday="thursday"):
    profile = draft()
    profile["learningLanguage"] = "None for now"
    profile["weekday"] = weekday
    response = client.put(
        f"/api/future/profile/{profile['id']}",
        json=profile,
        headers={"If-None-Match": "*"},
    )
    assert response.status_code == 200, response.json
    return profile


def _initialize_episteme(client, profile_id):
    response = client.get(f"/api/future/profile/{profile_id}/episteme")
    assert response.status_code == 200, response.json
    return response.json


def _set_animal_preference(client, profile_id, action):
    current = client.get(f"/api/future/profile/{profile_id}/episteme")
    assert current.status_code == 200
    evidence = {
        "evidenceId": str(uuid4()),
        "recordedAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "type": "explicit-preference",
        "concept": {"conceptId": "topic:animals", "label": "animals", "language": "en"},
        "kind": "taste",
        "action": action,
        "scope": {"mode": "play", "language": "en"},
        "supersedesEvidenceIds": [],
        "userText": "More animal words" if action == "seek" else "Fewer animal words",
    }
    response = client.post(
        f"/api/future/profile/{profile_id}/episteme/updates",
        json={
            "expectedRevision": current.json["revision"],
            "updateId": str(uuid4()),
            "recordedAt": evidence["recordedAt"],
            "evidence": [evidence],
            "evidenceActions": [],
        },
    )
    assert response.status_code == 200, response.json
    return evidence["evidenceId"]


def test_missing_pack_fails_closed_and_does_not_mutate_an_uninitialized_profile(api):
    client = api.app.test_client()
    profile = _create_profile(client)
    response = client.get(f"/api/future/profile/{profile['id']}/retrieval-brief")
    assert response.status_code == 503
    assert response.cache_control.no_store
    with api.app.app_context():
        assert api.db.session.get(EpistemeProfileRecord, profile["id"]) is None


def test_missing_pins_after_profile_initialization_returns_unavailable_without_fallback(api):
    client = api.app.test_client()
    profile = _create_profile(client)
    _initialize_episteme(client, profile["id"])
    for key in (
        "FUTURE_ADMITTED_PACK_PATH",
        "FUTURE_ADMITTED_PACK_ID",
        "FUTURE_ADMITTED_PACK_SHA256",
        "FUTURE_ADMITTED_SOURCE_PINS_JSON",
    ):
        api.app.config.pop(key, None)

    response = client.get(f"/api/future/profile/{profile['id']}/retrieval-brief")

    assert response.status_code == 503
    assert response.cache_control.no_store
    assert "EWE" not in response.get_data(as_text=True)


def test_same_pinned_synthetic_pack_selects_differently_for_explicit_profile_preferences(api, tmp_path):
    client = api.app.test_client()
    pack, _path = _configured_pack(api, tmp_path, animals=True)
    seek_profile = _create_profile(client, weekday="wednesday")
    avoid_profile = _create_profile(client, weekday="thursday")
    _initialize_episteme(client, seek_profile["id"])
    _initialize_episteme(client, avoid_profile["id"])
    seek_evidence_id = _set_animal_preference(client, seek_profile["id"], "seek")
    avoid_evidence_id = _set_animal_preference(client, avoid_profile["id"], "exclude")

    seek = client.get(
        f"/api/future/profile/{seek_profile['id']}/retrieval-brief", query_string={"limit": 2}
    )
    avoid = client.get(
        f"/api/future/profile/{avoid_profile['id']}/retrieval-brief", query_string={"limit": 2}
    )

    assert seek.status_code == avoid.status_code == 200
    assert seek.cache_control.no_store and avoid.cache_control.no_store
    assert seek.json["playable"] is avoid.json["playable"] is False
    assert seek.json["receipt"]["packSha256"] == avoid.json["receipt"]["packSha256"] == pack["artifactSha256"]
    assert seek.json["receipt"]["weekdayDifficulty"] == "wednesday"
    assert avoid.json["receipt"]["weekdayDifficulty"] == "thursday"
    assert seek.json["receipt"]["puzzleLanguage"] == "en"
    assert seek.json["receipt"]["learningLanguage"] == "None for now"
    assert seek.json["receipt"]["sourcePins"][0]["contentClass"] == "synthetic"
    assert seek.json["evidenceScope"].startswith("brief.evidenceIds refer only to host episteme evidence")
    selected_cat = next(
        row for row in seek.json["brief"]["selected"] if row["candidate"]["answer"] == "CAT"
    )
    assert selected_cat["selectedLane"] == "explicit-preference"
    assert selected_cat["evidenceIds"] == [seek_evidence_id]
    assert selected_cat["sourceIds"] == ["synthetic-loader-source"]
    assert [row["candidate"]["answer"] for row in avoid.json["brief"]["selected"]] == ["EWE"]
    assert avoid.json["brief"]["selected"][0]["candidate"]["answer"] == "EWE"
    excluded = next(row for row in avoid.json["brief"]["selectionLog"] if row["candidateId"] == "lexeme-cat")
    assert excluded["decision"] == "hard-exclusion"
    assert excluded["evidenceIds"] == [avoid_evidence_id]
    assert excluded["sourceIds"] == [next(iter(_configured_source_ids(pack)))]


def _configured_source_ids(pack):
    return (source["sourceId"] for source in pack["sources"])


def test_rejects_bad_origin_query_and_missing_profile(api, monkeypatch, tmp_path):
    client = api.app.test_client()
    _configured_pack(api, tmp_path)
    profile = _create_profile(client)
    _initialize_episteme(client, profile["id"])

    cross_origin = client.get(
        f"/api/future/profile/{profile['id']}/retrieval-brief",
        headers={"Origin": "https://elsewhere.invalid"},
    )
    assert cross_origin.status_code == 403
    assert client.get(f"/api/future/profile/{profile['id']}/retrieval-brief?mode=play").status_code == 400
    assert client.get(f"/api/future/profile/{profile['id']}/retrieval-brief?limit=1&limit=2").status_code == 400
    assert client.get(f"/api/future/profile/not-a-uuid/retrieval-brief").status_code == 400
    assert client.get(f"/api/future/profile/{uuid4()}/retrieval-brief").status_code == 404


def test_invalid_pack_pin_and_candidate_overflow_return_unavailable_without_leaking_path(api, tmp_path, monkeypatch):
    client = api.app.test_client()
    pack, path = _configured_pack(api, tmp_path)
    profile = _create_profile(client)
    _initialize_episteme(client, profile["id"])
    api.app.config["FUTURE_ADMITTED_PACK_SHA256"] = "0" * 64

    import src.crossword.admitted_retrieval_api as retrieval_module
    monkeypatch.setattr(
        retrieval_module,
        "run_reducer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("bad pack reached reducer")),
    )
    wrong_pin = client.get(f"/api/future/profile/{profile['id']}/retrieval-brief")
    assert wrong_pin.status_code == 503
    assert str(path) not in wrong_pin.get_data(as_text=True)
    assert "EWE" not in wrong_pin.get_data(as_text=True)

    api.app.config["FUTURE_ADMITTED_PACK_SHA256"] = pack["artifactSha256"]
    monkeypatch.setattr(retrieval_module, "MAX_RETRIEVAL_CANDIDATES", 0)
    overflow = client.get(f"/api/future/profile/{profile['id']}/retrieval-brief")
    assert overflow.status_code == 503
    assert overflow.cache_control.no_store


def test_malformed_bridge_output_and_response_overflow_fail_closed(api, tmp_path, monkeypatch):
    client = api.app.test_client()
    _configured_pack(api, tmp_path)
    profile = _create_profile(client)
    _initialize_episteme(client, profile["id"])
    import src.crossword.admitted_retrieval_api as retrieval_module

    monkeypatch.setattr(retrieval_module, "run_reducer", lambda *_args, **_kwargs: {"unexpected": True})
    malformed = client.get(f"/api/future/profile/{profile['id']}/retrieval-brief")
    assert malformed.status_code == 503
    assert malformed.cache_control.no_store

    monkeypatch.undo()
    monkeypatch.setattr(retrieval_module, "MAX_RETRIEVAL_RESPONSE_BYTES", 0)
    oversized = client.get(f"/api/future/profile/{profile['id']}/retrieval-brief")
    assert oversized.status_code == 503
    assert oversized.cache_control.no_store


@pytest.mark.parametrize(
    "mismatch",
    [
        "version",
        "mode",
        "language",
        "selection-limit",
        "selected-evidence-shape",
        "candidate-source-shape",
        "selection-log-evidence-shape",
        "selected-log-consistency",
    ],
)
def test_incompatible_compiler_brief_contract_fails_closed(api, tmp_path, monkeypatch, mismatch):
    client = api.app.test_client()
    _configured_pack(api, tmp_path)
    profile = _create_profile(client)
    _initialize_episteme(client, profile["id"])

    import src.crossword.admitted_retrieval_api as retrieval_module

    original_run_reducer = retrieval_module.run_reducer

    def incompatible_result(operation):
        result = original_run_reducer(operation)
        brief = result["brief"]
        if mismatch == "version":
            brief["briefVersion"] = "episteme-brief-v2"
        elif mismatch == "mode":
            brief["mode"] = "learn"
        elif mismatch == "language":
            brief["language"] = "fr"
        elif mismatch == "selection-limit":
            brief["selectionLimit"] += 1
        elif mismatch == "selected-evidence-shape":
            brief["selected"][0]["evidenceIds"] = {"not": "an array"}
        elif mismatch == "candidate-source-shape":
            brief["selected"][0]["candidate"]["eligibility"]["sourceIds"] = []
        elif mismatch == "selection-log-evidence-shape":
            brief["selectionLog"][0]["evidenceIds"] = None
        elif mismatch == "selected-log-consistency":
            brief["selectionLog"][0]["selected"] = False
        return result

    monkeypatch.setattr(retrieval_module, "run_reducer", incompatible_result)

    response = client.get(f"/api/future/profile/{profile['id']}/retrieval-brief")

    assert response.status_code == 503
    assert response.cache_control.no_store
    assert response.json == {"error": "The local retrieval compiler returned an inconsistent brief"}


def test_endpoint_reuses_exact_old_receipt_after_later_profile_revision(api, tmp_path):
    client = api.app.test_client()
    _configured_pack(api, tmp_path)
    profile = _create_profile(client)
    _initialize_episteme(client, profile["id"])
    first = client.get(f"/api/future/profile/{profile['id']}/retrieval-brief")
    assert first.status_code == 200
    original_receipt = first.json["receipt"]

    _set_animal_preference(client, profile["id"], "seek")
    later = client.get(f"/api/future/profile/{profile['id']}/retrieval-brief")

    assert later.status_code == 200
    assert first.json["receipt"] == original_receipt
    assert later.json["receipt"]["epistemeRevision"] == original_receipt["epistemeRevision"] + 1
    assert later.json["receipt"]["epistemeDigest"] != original_receipt["epistemeDigest"]


def test_sqlite_snapshot_blocks_writer_between_starting_profile_and_episteme_reads(api, tmp_path):
    client = api.app.test_client()
    _configured_pack(api, tmp_path)
    profile = _create_profile(client)
    _initialize_episteme(client, profile["id"])
    original = client.get(f"/api/future/profile/{profile['id']}").json
    with api.app.app_context():
        engine = api.db.engine
    attempts = []
    attempted = False

    def try_interleaved_write(_connection, _cursor, statement, _parameters, _context, _many):
        nonlocal attempted
        if attempted or not statement.lstrip().upper().startswith("SELECT") or "future_starting_profiles" not in statement:
            return
        attempted = True
        with engine.connect() as writer:
            writer.exec_driver_sql("PRAGMA busy_timeout=25")
            try:
                writer.exec_driver_sql(
                    "UPDATE future_starting_profiles SET updated_at = ? WHERE id = ?",
                    ("2026-09-27T00:00:00.000Z", profile["id"]),
                )
            except OperationalError:
                attempts.append("blocked")
            else:
                attempts.append("committed")

    event.listen(engine, "before_cursor_execute", try_interleaved_write)
    try:
        response = client.get(f"/api/future/profile/{profile['id']}/retrieval-brief")
    finally:
        event.remove(engine, "before_cursor_execute", try_interleaved_write)

    assert response.status_code == 200, response.json
    assert attempts == ["blocked"]
    assert response.json["receipt"]["profileUpdatedAt"] == original["updatedAt"]
