"""Private puzzle clue/fill receipts survive the replay boundary."""

from datetime import datetime, timezone
from uuid import uuid4

from tests.test_api_isolated import api, no_network  # noqa: F401
from tests.test_api_isolated import original_puzzle_text
from tests.test_future_api import draft
from src.crossword.future_puzzles import (
    FuturePuzzleProvenanceRecord,
    stage_private_puzzle_provenance,
    store_private_puzzle_provenance,
)
from src.crossword.session_journal import PersonalSolveSession


def private_game(api, client):
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
    with api.app.app_context():
        puzzle = api.NYTFormatParser.parse(original_puzzle_text("260928"))
        manifest = api.register_legacy_puzzle(puzzle)
        puzzle_hash = manifest["integrity"]["value"].removeprefix("sha256:")
        session_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        api.db.session.add(
            PersonalSolveSession(
                id=session_id,
                profile_id=profile_id,
                puzzle_hash=puzzle_hash,
                initial_grid=[],
                writer_digest="b" * 64,
                accepted_seq=0,
                status="finished",
                created_at=now,
                updated_at=now,
            )
        )
        api.db.session.commit()
    return profile_id, session_id, manifest


def test_private_provenance_is_idempotent_and_owner_scoped(api):
    client = api.app.test_client()
    profile_id, session_id, manifest = private_game(api, client)
    provenance = {
        "version": "private-puzzle-provenance-v1",
        "model": "gemma4:26b",
        "weekday": "wednesday",
        "quality": {"mean": 78.1, "weakEntries": 19},
        "clueReceipt": {"checked": 78, "challenger": "bounded"},
    }
    with api.app.app_context():
        first = store_private_puzzle_provenance(
            profile_id=profile_id, manifest=manifest, provenance=provenance
        )
        second = store_private_puzzle_provenance(
            profile_id=profile_id, manifest=manifest, provenance=provenance
        )
        assert first.puzzle_hash == second.puzzle_hash
        assert (
            api.db.session.query(FuturePuzzleProvenanceRecord).count() == 1
        )

    response = client.get(
        f"/api/future/sessions/{session_id}/private-provenance?profileId={profile_id}"
    )
    assert response.status_code == 200, response.json
    assert response.json["version"] == "private-puzzle-provenance-v1"
    assert response.json["provenance"] == provenance
    assert response.json["provenanceDigest"].startswith("sha256:")
    assert response.cache_control.no_store
    assert client.get(
        f"/api/future/sessions/{session_id}/private-provenance?profileId={uuid4()}"
    ).status_code == 404


def test_finished_private_game_exposes_digest_bound_local_review_bundle(api):
    client = api.app.test_client()
    profile_id, session_id, manifest = private_game(api, client)
    grounding_entries = [
        {
            "id": entry["id"],
            "grammarBridge": {"valid": True, "issues": []},
            "surfaceIssues": [],
            "riskFlags": [],
            "mechanicalIssue": None,
            "morphologyIssue": None,
            "semanticChallenge": {"classification": "needs-review"},
            "semanticStatus": "not-established",
            "supportBand": "ordinary",
        }
        for entry in manifest["entries"]
    ]
    provenance = {
        "model": "gemma4:26b",
        "weekday": "wednesday",
        "seed": 42,
        "clueQuality": {
            "issueCount": 0,
            "groundedClueBundle": {"entries": grounding_entries},
        },
    }
    with api.app.app_context():
        store_private_puzzle_provenance(
            profile_id=profile_id, manifest=manifest, provenance=provenance
        )

    response = client.get(
        f"/api/future/sessions/{session_id}/private-review-bundle?profileId={profile_id}"
    )
    assert response.status_code == 200, response.json
    assert response.json["schemaVersion"] == "private-clue-review-bundle-v1"
    assert response.json["publishable"] is False
    assert response.json["manifestDigest"] == manifest["integrity"]["value"]
    assert len(response.json["entries"]) == len(manifest["entries"])
    assert response.json["entries"][0]["answer"]
    assert response.json["entries"][0]["review"]["status"] == "unreviewed"
    assert response.cache_control.no_store
    assert client.get(
        f"/api/future/sessions/{session_id}/private-review-bundle?profileId={uuid4()}"
    ).status_code == 404


def test_private_provenance_rejects_conflict_and_detects_tampering(api):
    client = api.app.test_client()
    profile_id, session_id, manifest = private_game(api, client)
    original = {"model": "qwen3.8:27b", "attempts": 4}
    with api.app.app_context():
        stage_private_puzzle_provenance(
            profile_id=profile_id, manifest=manifest, provenance=original
        )
        api.db.session.commit()
        try:
            stage_private_puzzle_provenance(
                profile_id=profile_id,
                manifest=manifest,
                provenance={"model": "different"},
            )
        except ValueError as error:
            assert "identity conflict" in str(error)
        else:
            raise AssertionError("conflicting provenance should be rejected")
        record = api.db.session.get(
            FuturePuzzleProvenanceRecord,
            (manifest["integrity"]["value"].removeprefix("sha256:"), profile_id),
        )
        record.provenance_json = {"model": "tampered"}
        api.db.session.commit()
    response = client.get(
        f"/api/future/sessions/{session_id}/private-provenance?profileId={profile_id}"
    )
    assert response.status_code == 503
    assert response.json["playable"] is False
