"""Published V2 registry and solve-journal boundary integration tests.

The only publication rows created here are explicitly synthetic direct DB
fixtures. Production code in this slice has no writer for that registry.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4
import hashlib

import pytest

from tests.test_api_isolated import api, no_network  # noqa: F401
from tests.test_future_grid_jobs import _create_profile, _personalized_profile_payload
from tests.test_session_journal import registered_manifest
from src.crossword.future_puzzles import FuturePuzzleV2CandidateRecord
from src.crossword.solve_replay import SolveReplayRejected, validate_solve_puzzle_v2
from src.crossword.v2_session_journal import (
    FuturePuzzleV2PublishedRecord,
    FuturePuzzleV2SolveAnalysis,
    FuturePuzzleV2SolveEvent,
    FuturePuzzleV2SolveSession,
)


V2_FIXTURE = Path(__file__).parent / "fixtures" / "personalized-review-v2.json"
RECEIPT_VERSION = "puzzle-v2-publication-receipt-v1"


def _synthetic_review_document():
    # This checked-in puzzle is a synthetic quality=review candidate, never a
    # real approved puzzle. Tests may insert it into the host registry only to
    # exercise the mechanics of a hypothetical trusted publication row.
    return json.loads(V2_FIXTURE.read_text(encoding="utf-8"))


def _synthetic_structural_accept_document():
    """Build a fake, test-only schema-accept document for journal mechanics.

    This intentionally relabels the checked-in synthetic source pins as
    structurally public and adds a synthetic semantic-attestation shape. It is
    not evidence that the content is public, true, reviewed, or publishable;
    no production writer can insert it into the registry.
    """
    puzzle = _synthetic_review_document()

    def label_synthetic_pins_as_structurally_public(value):
        if isinstance(value, dict):
            if value.get("sourceId") == "synthetic-source" and "contentClass" in value:
                value["contentClass"] = "public"
            for nested in value.values():
                label_synthetic_pins_as_structurally_public(nested)
        elif isinstance(value, list):
            for nested in value:
                label_synthetic_pins_as_structurally_public(nested)

    label_synthetic_pins_as_structurally_public(puzzle["provenance"])
    # The fixture's unknown structural-only estimate is intentionally changed
    # to the minimal accepted quality shape; this is still synthetic and not a
    # calibrated or human-reviewed support claim.
    puzzle["crossingSupport"]["version"] = "synthetic-test-support-v1"
    puzzle["crossingSupport"]["uncertainty"] = {
        "level": "medium",
        "notes": "Synthetic test fixture only; not a calibrated estimate.",
    }
    clue_ids = sorted(clue["clueVariantId"] for clue in puzzle["clues"])
    puzzle["quality"] = {
        "verdict": "accept",
        "reasons": [],
        "semanticAttestation": {
            "reviewerId": "synthetic-structural-test-only",
            "reviewedAt": "2026-09-26",
            "clueVariantIds": clue_ids,
            "sourceIds": ["synthetic-source"],
            "evidenceRefs": ["synthetic-test-attestation-shape"],
        },
    }
    content = {key: value for key, value in puzzle.items() if key != "integrity"}
    canonical = json.dumps(
        content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    puzzle["integrity"]["value"] = (
        "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    )
    return puzzle


def _insert_synthetic_published_row(api, puzzle=None, receipt=None):
    puzzle = deepcopy(puzzle or _synthetic_structural_accept_document())
    raw_digest = puzzle["integrity"]["value"].removeprefix("sha256:")
    published_at = "2026-09-26T12:00:00.000Z"
    receipt = deepcopy(
        receipt
        or {
            "version": RECEIPT_VERSION,
            "candidateDigest": puzzle["integrity"]["value"],
            "publishedAt": published_at,
            # This is a shape fixture, not reviewer authentication or trust.
            "reviewerId": "synthetic-test-reviewer",
        }
    )
    with api.app.app_context():
        api.db.session.add(
            FuturePuzzleV2PublishedRecord(
                candidate_hash=raw_digest,
                puzzle_id=puzzle["id"],
                puzzle_json=puzzle,
                publication_receipt=receipt,
                published_at=published_at,
            )
        )
        api.db.session.commit()
    return puzzle, raw_digest, receipt


def _insert_synthetic_review_candidate(api, profile_id, puzzle=None):
    puzzle = deepcopy(puzzle or _synthetic_review_document())
    raw_digest = puzzle["integrity"]["value"].removeprefix("sha256:")
    with api.app.app_context():
        api.db.session.add(
            FuturePuzzleV2CandidateRecord(
                profile_id=profile_id,
                candidate_hash=raw_digest,
                candidate_id=puzzle["id"],
                job_id=str(uuid4()),
                manifest_json=puzzle,
                created_at="2026-09-26T12:00:00.000Z",
            )
        )
        api.db.session.commit()
    return puzzle, raw_digest


def _profile(client):
    value = _personalized_profile_payload()
    _create_profile(client, value)
    return value["id"]


def _initial_grid(puzzle):
    return [
        {"cellId": cell["id"], "token": None, "origin": "unknown"}
        for cell in puzzle["cells"]
        if not cell["block"]
    ]


def _new_session(
    client, puzzle, profile_id, *, session_id=None, writer_token=None, grid=None
):
    session_id = session_id or str(uuid4())
    writer_token = writer_token or f"v2-session-capability-{uuid4()}"
    body = {
        "sessionId": session_id,
        "profileId": profile_id,
        "puzzleHash": puzzle["integrity"]["value"],
        "puzzleId": puzzle["id"],
        "initialGrid": _initial_grid(puzzle) if grid is None else grid,
        "writerToken": writer_token,
    }
    return client.post("/api/future/sessions/v2", json=body), body


def _event(session, profile_id, puzzle_hash, seq, event_type, **payload):
    return {
        "schemaVersion": 2,
        "eventId": str(uuid4()),
        "sessionId": session,
        "profileId": profile_id,
        "segmentId": str(uuid4()),
        "seq": seq,
        "elapsedMs": seq * 100,
        "recordedAt": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "puzzleHash": puzzle_hash,
        "type": event_type,
        **payload,
    }


def _append(client, session_id, writer_token, events, *, expected_seq=0):
    return client.post(
        f"/api/future/sessions/v2/{session_id}/events",
        json={
            "expectedSeq": expected_seq,
            "writerToken": writer_token,
            "events": events,
        },
    )


def _finalized_session(api, client):
    puzzle, raw_digest, _receipt = _insert_synthetic_published_row(api)
    profile_id = _profile(client)
    created, body = _new_session(client, puzzle, profile_id)
    assert created.status_code == 201
    start = _event(
        body["sessionId"],
        profile_id,
        body["puzzleHash"],
        1,
        "session-started",
        reason="fresh",
    )
    finish = _event(
        body["sessionId"],
        profile_id,
        body["puzzleHash"],
        2,
        "session-finished",
        reason="stopped",
    )
    appended = _append(client, body["sessionId"], body["writerToken"], [start, finish])
    assert appended.status_code == 200, appended.json
    return puzzle, raw_digest, profile_id, body


def _analysis_response(client, session):
    return client.get(
        f"/api/future/sessions/v2/{session['sessionId']}/analysis",
        query_string={"profileId": session["profileId"]},
        headers={"X-Future-Session-Writer": session["writerToken"]},
    )


def test_published_v2_registry_starts_empty_and_returns_adapter_envelope(api):
    client = api.app.test_client()
    puzzle = _synthetic_review_document()
    raw_digest = puzzle["integrity"]["value"].removeprefix("sha256:")

    absent = client.get(f"/api/future/puzzles/v2/{raw_digest}")
    assert absent.status_code == 404
    assert absent.cache_control.no_store

    puzzle, raw_digest, receipt = _insert_synthetic_published_row(api)
    response = client.get(f"/api/future/puzzles/v2/{raw_digest}")
    assert response.status_code == 200, response.json
    assert response.cache_control.no_store
    assert set(response.json) == {
        "status",
        "candidateDigest",
        "puzzle",
        "publicationReceipt",
    }
    assert response.json == {
        "status": "published",
        "candidateDigest": puzzle["integrity"]["value"],
        "puzzle": puzzle,
        "publicationReceipt": receipt,
    }
    assert validate_solve_puzzle_v2(response.json["puzzle"])["id"] == puzzle["id"]


@pytest.mark.parametrize("corruption", ["missing", "digest", "timestamp"])
def test_published_v2_read_fails_closed_on_missing_or_mismatched_receipt(
    api, corruption
):
    client = api.app.test_client()
    puzzle, raw_digest, receipt = _insert_synthetic_published_row(api)
    with api.app.app_context():
        row = api.db.session.get(FuturePuzzleV2PublishedRecord, raw_digest)
        changed = dict(receipt)
        if corruption == "missing":
            changed = {"version": RECEIPT_VERSION}
        elif corruption == "digest":
            changed["candidateDigest"] = "sha256:" + "0" * 64
        else:
            changed["publishedAt"] = "2026-09-27T12:00:00.000Z"
        row.publication_receipt = changed
        api.db.session.commit()

    response = client.get(f"/api/future/puzzles/v2/{raw_digest}")
    assert response.status_code == 503
    assert response.cache_control.no_store
    assert (
        response.json["error"] == "Published V2 puzzle failed host integrity validation"
    )


def test_published_v2_read_and_session_creation_reject_tampered_document(api):
    client = api.app.test_client()
    puzzle, raw_digest, _receipt = _insert_synthetic_published_row(api)
    with api.app.app_context():
        row = api.db.session.get(FuturePuzzleV2PublishedRecord, raw_digest)
        row.puzzle_json = {
            **row.puzzle_json,
            "title": "Tampered after test publication",
        }
        api.db.session.commit()

    get_response = client.get(f"/api/future/puzzles/v2/{raw_digest}")
    assert get_response.status_code == 503
    profile_id = _profile(client)
    create_response, _body = _new_session(client, puzzle, profile_id)
    assert create_response.status_code == 503
    with api.app.app_context():
        assert api.db.session.query(FuturePuzzleV2SolveSession).count() == 0


def test_review_quality_cannot_be_resolved_from_published_registry(api):
    client = api.app.test_client()
    review = _synthetic_review_document()
    review, raw_digest, _receipt = _insert_synthetic_published_row(api, puzzle=review)
    profile_id = _profile(client)

    read = client.get(f"/api/future/puzzles/v2/{raw_digest}")
    assert read.status_code == 503
    create, _ = _new_session(client, review, profile_id)
    assert create.status_code == 503
    with api.app.app_context():
        assert api.db.session.query(FuturePuzzleV2SolveSession).count() == 0


def test_v2_registry_fails_closed_when_strict_validator_is_unavailable(
    api, monkeypatch
):
    import src.crossword.v2_session_journal as journal

    client = api.app.test_client()
    puzzle, raw_digest, _receipt = _insert_synthetic_published_row(api)
    profile_id = _profile(client)
    created, body = _new_session(client, puzzle, profile_id)
    assert created.status_code == 201

    def unavailable(_puzzle):
        raise journal.SolveReplayUnavailable("synthetic validator runtime unavailable")

    monkeypatch.setattr(journal, "validate_solve_puzzle_v2", unavailable)
    read = client.get(f"/api/future/puzzles/v2/{raw_digest}")
    assert read.status_code == 503
    assert read.cache_control.no_store

    retry_create, _ = _new_session(
        client,
        puzzle,
        profile_id,
        session_id=body["sessionId"],
        writer_token=body["writerToken"],
    )
    assert retry_create.status_code == 503

    event = _event(
        body["sessionId"],
        profile_id,
        body["puzzleHash"],
        1,
        "session-started",
        reason="fresh",
    )
    append = _append(client, body["sessionId"], body["writerToken"], [event])
    assert append.status_code == 503
    with api.app.app_context():
        assert (
            api.db.session.query(FuturePuzzleV2SolveEvent)
            .filter_by(session_id=body["sessionId"])
            .count()
            == 0
        )


def test_active_v2_session_does_not_expose_partial_analysis(api):
    client = api.app.test_client()
    puzzle, _raw_digest, _receipt = _insert_synthetic_published_row(api)
    profile_id = _profile(client)
    created, body = _new_session(client, puzzle, profile_id)
    assert created.status_code == 201
    response = _analysis_response(client, {**body, "profileId": profile_id})
    assert response.status_code == 409
    assert response.cache_control.no_store
    assert (
        response.json["error"]
        == "V2 session analysis is available after the session finishes"
    )


@pytest.mark.parametrize("corruption", ["removed", "receipt", "document"])
def test_finalized_analysis_requires_exact_published_registry_row(api, corruption):
    client = api.app.test_client()
    _puzzle, raw_digest, profile_id, body = _finalized_session(api, client)
    with api.app.app_context():
        published = api.db.session.get(FuturePuzzleV2PublishedRecord, raw_digest)
        if corruption == "removed":
            api.db.session.delete(published)
        else:
            if corruption == "receipt":
                published.publication_receipt = {
                    **published.publication_receipt,
                    "candidateDigest": "sha256:" + "0" * 64,
                }
            else:
                published.puzzle_json = {
                    **published.puzzle_json,
                    "title": "Edited after finalization",
                }
        api.db.session.commit()

    response = _analysis_response(client, {**body, "profileId": profile_id})
    assert response.status_code == 503
    assert response.cache_control.no_store
    assert response.json["error"] == "Finalized V2 analysis failed integrity validation"


def test_finalized_analysis_rejects_tampered_cached_analysis(api):
    client = api.app.test_client()
    _puzzle, _raw_digest, profile_id, body = _finalized_session(api, client)
    with api.app.app_context():
        saved = api.db.session.get(FuturePuzzleV2SolveAnalysis, body["sessionId"])
        saved.analysis_json = {
            **saved.analysis_json,
            "analysisVersion": "forged-analysis",
        }
        api.db.session.commit()

    response = _analysis_response(client, {**body, "profileId": profile_id})
    assert response.status_code == 503
    assert response.cache_control.no_store
    assert response.json["error"] == "Finalized V2 analysis failed integrity validation"


@pytest.mark.parametrize("corruption", ["payload", "missing"])
def test_finalized_analysis_rejects_tampered_or_incomplete_event_history(
    api, corruption
):
    client = api.app.test_client()
    _puzzle, _raw_digest, profile_id, body = _finalized_session(api, client)
    with api.app.app_context():
        start = (
            api.db.session.query(FuturePuzzleV2SolveEvent)
            .filter_by(session_id=body["sessionId"], seq=1)
            .one()
        )
        if corruption == "missing":
            api.db.session.delete(start)
        else:
            start.payload = {**start.payload, "reason": "altered-after-finalization"}
        api.db.session.commit()

    response = _analysis_response(client, {**body, "profileId": profile_id})
    assert response.status_code == 503
    assert response.cache_control.no_store
    assert response.json["error"] == "Finalized V2 analysis failed integrity validation"


def test_finalized_analysis_maps_replay_runtime_unavailability_to_503(api, monkeypatch):
    import src.crossword.v2_session_journal as journal

    client = api.app.test_client()
    _puzzle, _raw_digest, profile_id, body = _finalized_session(api, client)

    def unavailable(_session, _puzzle):
        raise journal.SolveReplayUnavailable("synthetic replay runtime unavailable")

    monkeypatch.setattr(journal, "analyze_solve_session_v2", unavailable)
    response = _analysis_response(client, {**body, "profileId": profile_id})
    assert response.status_code == 503
    assert response.cache_control.no_store


def test_review_candidate_private_play_does_not_publish_and_v1_v2_are_isolated(api):
    client = api.app.test_client()
    puzzle = _synthetic_review_document()
    raw_digest = puzzle["integrity"]["value"].removeprefix("sha256:")
    profile_id = _profile(client)
    # The candidate table is intentionally distinct. This test-only row mirrors
    # an actual review candidate and does not populate the published registry.
    with api.app.app_context():
        api.db.session.add(
            FuturePuzzleV2CandidateRecord(
                profile_id=profile_id,
                candidate_hash=raw_digest,
                candidate_id=puzzle["id"],
                job_id=str(uuid4()),
                manifest_json=puzzle,
                created_at="2026-09-26T12:00:00.000Z",
            )
        )
        api.db.session.commit()

    candidate = client.get(
        f"/api/future/puzzle-candidates/v2/{raw_digest}",
        query_string={"profileId": profile_id},
    )
    assert candidate.status_code == 200
    assert candidate.json["status"] == "review"
    assert candidate.json["playable"] is False
    assert (
        client.post(f"/api/future/puzzles/v2/{raw_digest}", json={}).status_code == 405
    )

    create_response, _body = _new_session(client, puzzle, profile_id)
    assert create_response.status_code == 201
    assert create_response.json["puzzleHash"] == puzzle["integrity"]["value"]
    assert client.get(f"/api/future/puzzles/v2/{raw_digest}").status_code == 404
    with api.app.app_context():
        assert api.db.session.query(FuturePuzzleV2PublishedRecord).count() == 0

    # V1 does not strip the prefix and cannot resolve a V2 candidate.
    v1_response = client.post(
        "/api/future/sessions",
        json={
            "sessionId": str(uuid4()),
            "profileId": profile_id,
            "puzzleHash": puzzle["integrity"]["value"],
            "initialGrid": _initial_grid(puzzle),
            "writerToken": "v1-session-capability-that-is-long-enough",
        },
    )
    assert v1_response.status_code == 422
    assert v1_response.json["error"] == "Invalid session identity"

    # Even a real V1-registered puzzle cannot be resolved through the V2 table.
    legacy_manifest = registered_manifest(api)
    legacy_hash = legacy_manifest["integrity"]["value"]
    legacy_in_v2 = client.post(
        "/api/future/sessions/v2",
        json={
            "sessionId": str(uuid4()),
            "profileId": profile_id,
            "puzzleHash": legacy_hash,
            "puzzleId": "legacy-id",
            "initialGrid": [],
            "writerToken": "v2-session-capability-that-is-long-enough",
        },
    )
    assert legacy_in_v2.status_code == 422
    assert legacy_in_v2.json["error"] == "Invalid V2 session identity"


def test_owner_review_candidate_can_be_played_privately_without_publication(api):
    client = api.app.test_client()
    profile_id = _profile(client)
    puzzle, raw_digest = _insert_synthetic_review_candidate(api, profile_id)
    public_path = f"/api/future/puzzles/v2/{raw_digest}"
    assert client.get(public_path).status_code == 404

    other_profile = _profile(client)
    denied, _ = _new_session(client, puzzle, other_profile)
    assert denied.status_code == 404
    noncanonical, _ = _new_session(client, puzzle, profile_id.upper())
    assert noncanonical.status_code == 422

    created, body = _new_session(client, puzzle, profile_id)
    assert created.status_code == 201, created.json
    assert body["profileId"] == profile_id
    assert body["puzzleHash"] == puzzle["integrity"]["value"]
    assert body["puzzleId"] == puzzle["id"]

    started = _event(
        body["sessionId"],
        profile_id,
        body["puzzleHash"],
        1,
        "session-started",
        reason="fresh",
    )
    finished = _event(
        body["sessionId"],
        profile_id,
        body["puzzleHash"],
        2,
        "session-finished",
        reason="stopped",
    )
    appended = _append(
        client, body["sessionId"], body["writerToken"], [started, finished]
    )
    assert appended.status_code == 200, appended.json
    analysis = _analysis_response(client, {**body, "profileId": profile_id})
    assert analysis.status_code == 200, analysis.json
    assert analysis.json["finalized"] is True
    assert analysis.json["puzzleHash"] == puzzle["integrity"]["value"]

    v1_response = client.post(
        "/api/future/sessions",
        json={
            "sessionId": str(uuid4()),
            "profileId": profile_id,
            "puzzleHash": puzzle["integrity"]["value"],
            "initialGrid": _initial_grid(puzzle),
            "writerToken": "v1-session-capability-that-is-long-enough",
        },
    )
    assert v1_response.status_code == 422
    assert v1_response.json["error"] == "Invalid session identity"
    assert client.get(public_path).status_code == 404

    with api.app.app_context():
        assert api.db.session.query(FuturePuzzleV2PublishedRecord).count() == 0
        candidate = api.db.session.get(
            FuturePuzzleV2CandidateRecord, (profile_id, raw_digest)
        )
        assert candidate is not None
        assert candidate.candidate_id == body["puzzleId"]


def test_candidate_session_fails_closed_when_candidate_is_tampered(api):
    client = api.app.test_client()
    profile_id = _profile(client)
    puzzle, raw_digest = _insert_synthetic_review_candidate(api, profile_id)
    created, body = _new_session(client, puzzle, profile_id)
    assert created.status_code == 201

    with api.app.app_context():
        candidate = api.db.session.get(
            FuturePuzzleV2CandidateRecord, (profile_id, raw_digest)
        )
        candidate.manifest_json = {
            **candidate.manifest_json,
            "title": "Tampered after staging",
        }
        api.db.session.commit()

    started = _event(
        body["sessionId"],
        profile_id,
        body["puzzleHash"],
        1,
        "session-started",
        reason="fresh",
    )
    response = _append(client, body["sessionId"], body["writerToken"], [started])
    assert response.status_code == 503
    assert response.json["error"] == "V2 session puzzle is unavailable or invalid"
    with api.app.app_context():
        assert (
            api.db.session.query(FuturePuzzleV2SolveEvent)
            .filter_by(session_id=body["sessionId"])
            .count()
            == 0
        )


def test_final_candidate_replay_fails_closed_when_owner_row_is_missing(api):
    client = api.app.test_client()
    profile_id = _profile(client)
    puzzle, raw_digest = _insert_synthetic_review_candidate(api, profile_id)
    created, body = _new_session(client, puzzle, profile_id)
    assert created.status_code == 201
    started = _event(
        body["sessionId"],
        profile_id,
        body["puzzleHash"],
        1,
        "session-started",
        reason="fresh",
    )
    finished = _event(
        body["sessionId"],
        profile_id,
        body["puzzleHash"],
        2,
        "session-finished",
        reason="stopped",
    )
    assert (
        _append(
            client, body["sessionId"], body["writerToken"], [started, finished]
        ).status_code
        == 200
    )

    with api.app.app_context():
        candidate = api.db.session.get(
            FuturePuzzleV2CandidateRecord, (profile_id, raw_digest)
        )
        api.db.session.delete(candidate)
        api.db.session.commit()

    analysis = _analysis_response(client, {**body, "profileId": profile_id})
    assert analysis.status_code == 503
    assert analysis.json["error"] == "Finalized V2 analysis failed integrity validation"


def test_v2_creation_checks_exact_ordered_grid_identity_and_profile_scope(api):
    client = api.app.test_client()
    puzzle, _raw_digest, _receipt = _insert_synthetic_published_row(api)
    profile_id = _profile(client)

    reversed_grid = list(reversed(_initial_grid(puzzle)))
    wrong_grid, _ = _new_session(client, puzzle, profile_id, grid=reversed_grid)
    assert wrong_grid.status_code == 422
    assert "exactly match" in wrong_grid.json["error"]

    wrong_puzzle_id, body = _new_session(client, puzzle, profile_id)
    assert wrong_puzzle_id.status_code == 201
    collision, _ = _new_session(
        client,
        puzzle,
        str(uuid4()),
        session_id=body["sessionId"],
        writer_token=body["writerToken"],
    )
    assert collision.status_code == 404
    assert collision.json["error"] == "Starting profile not found"

    other_profile = _profile(client)
    collision, _ = _new_session(
        client,
        puzzle,
        other_profile,
        session_id=body["sessionId"],
        writer_token=body["writerToken"],
    )
    assert collision.status_code == 409
    assert collision.json["error"] == "Session id already belongs to another V2 journal"


def test_v2_session_keeps_prefixed_digest_idempotency_lifecycle_and_analysis(api):
    client = api.app.test_client()
    puzzle, raw_digest, _receipt = _insert_synthetic_published_row(api)
    profile_id = _profile(client)
    created, body = _new_session(client, puzzle, profile_id)
    assert created.status_code == 201, created.json
    assert created.json["puzzleHash"] == puzzle["integrity"]["value"]
    assert created.json["puzzleHash"] == f"sha256:{raw_digest}"

    # Idempotent create returns the existing V2 record only for the same
    # profile, puzzle, snapshot and writer capability.
    retried, _ = _new_session(
        client,
        puzzle,
        profile_id,
        session_id=body["sessionId"],
        writer_token=body["writerToken"],
    )
    assert retried.status_code == 200

    start = _event(
        body["sessionId"],
        profile_id,
        body["puzzleHash"],
        1,
        "session-started",
        reason="fresh",
    )
    bad_digest = {**start, "puzzleHash": raw_digest}
    rejected = _append(client, body["sessionId"], body["writerToken"], [bad_digest])
    assert rejected.status_code == 422
    assert "V2 journal" in rejected.json["error"]

    wrong_writer = _append(
        client, body["sessionId"], "wrong-writer-capability-xxxxxxxx", [start]
    )
    assert wrong_writer.status_code == 403
    wrong_profile_event = {**start, "eventId": str(uuid4()), "profileId": str(uuid4())}
    wrong_profile = _append(
        client, body["sessionId"], body["writerToken"], [wrong_profile_event]
    )
    assert wrong_profile.status_code == 422

    accepted = _append(client, body["sessionId"], body["writerToken"], [start])
    assert accepted.status_code == 200, accepted.json
    replay = _append(client, body["sessionId"], body["writerToken"], [start])
    assert replay.status_code == 200
    assert replay.json["duplicateEventIds"] == [start["eventId"]]
    assert replay.json["acceptedEventIds"] == []

    finish = _event(
        body["sessionId"],
        profile_id,
        body["puzzleHash"],
        2,
        "session-finished",
        reason="stopped",
    )
    terminal = _append(
        client, body["sessionId"], body["writerToken"], [finish], expected_seq=1
    )
    assert terminal.status_code == 200
    assert terminal.json["status"] == "finished"
    after_finish = _event(
        body["sessionId"], profile_id, body["puzzleHash"], 3, "paused", reason="user"
    )
    terminal_write = _append(
        client, body["sessionId"], body["writerToken"], [after_finish], expected_seq=2
    )
    assert terminal_write.status_code == 409
    assert terminal_write.json["error"] == "V2 session is already finished"

    analysis = client.get(
        f"/api/future/sessions/v2/{body['sessionId']}/analysis",
        query_string={"profileId": profile_id},
        headers={"X-Future-Session-Writer": body["writerToken"]},
    )
    assert analysis.status_code == 200
    assert analysis.json["finalized"] is True
    assert analysis.json["puzzleHash"] == puzzle["integrity"]["value"]
    assert analysis.json["analysis"]["puzzleHash"] == puzzle["integrity"]["value"]
    assert len(analysis.json["analysis"]["observations"]) == len(puzzle["entries"])
    assert (
        client.get(
            f"/api/future/sessions/v2/{body['sessionId']}/analysis",
            query_string={"profileId": str(uuid4())},
            headers={"X-Future-Session-Writer": body["writerToken"]},
        ).status_code
        == 404
    )

    with api.app.app_context():
        session = api.db.session.get(FuturePuzzleV2SolveSession, body["sessionId"])
        events = (
            api.db.session.query(FuturePuzzleV2SolveEvent)
            .filter_by(session_id=body["sessionId"])
            .order_by(FuturePuzzleV2SolveEvent.seq)
            .all()
        )
        saved_analysis = api.db.session.get(
            FuturePuzzleV2SolveAnalysis, body["sessionId"]
        )
        assert session.puzzle_hash.startswith("sha256:")
        assert [row.seq for row in events] == [1, 2]
        assert all(row.payload["puzzleHash"].startswith("sha256:") for row in events)
        assert saved_analysis.finalized is True


def test_puzzle_document_validation_operation_is_v2_only_and_fail_closed(api):
    puzzle = _synthetic_review_document()
    assert validate_solve_puzzle_v2(puzzle)["id"] == puzzle["id"]
    tampered = deepcopy(puzzle)
    tampered["title"] += " altered"
    with pytest.raises(SolveReplayRejected, match="integrity-mismatch"):
        validate_solve_puzzle_v2(tampered)

    # A legacy manifest is not inferred as a V2 document by the new operation.
    legacy = registered_manifest(api)
    with pytest.raises(SolveReplayRejected, match="Invalid PuzzleDocumentV2"):
        validate_solve_puzzle_v2(legacy)
