"""Profile-scoped retention removes only expired local generation artefacts."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from tests.test_api_isolated import api, no_network  # noqa: F401
from src.crossword.calibration_api import CalibrationSessionRecord
from src.crossword.database import db
from src.crossword.episteme_store import EpistemeProfileRecord
from src.crossword.future import StartingProfile
from src.crossword.future_grid_jobs import (
    FutureGridDraftJob,
    FutureGridDraftPrivateSelection,
)
from src.crossword.future_puzzles import FuturePuzzleV2CandidateRecord
from src.crossword.profile_retention import retain_profile
from src.crossword.session_journal import PersonalSolveSession


def _stamp(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _job(profile_id, *, state, mode, updated_at):
    return FutureGridDraftJob(
        id=str(uuid4()),
        profile_id=profile_id,
        idempotency_key=str(uuid4()),
        request_digest="a" * 64,
        request_json={"mode": mode, "profileId": profile_id},
        state=state,
        attempt=1,
        lease_token=str(uuid4()) if state == "running" else None,
        lease_until=_stamp(updated_at + timedelta(days=1)) if state == "running" else None,
        cancel_requested=False,
        result_json={"puzzle": "local"} if state == "ready" else None,
        error=None,
        created_at=_stamp(updated_at),
        updated_at=_stamp(updated_at),
    )


def _candidate(profile_id, job_id, created_at):
    return FuturePuzzleV2CandidateRecord(
        profile_id=profile_id,
        candidate_hash="b" * 64,
        candidate_id="personalized-" + "c" * 32,
        job_id=job_id,
        manifest_json={"schemaVersion": 2, "quality": {"verdict": "review"}},
        created_at=_stamp(created_at),
    )


def _seed(module):
    now = datetime.now(timezone.utc)
    profile_id = str(uuid4())
    old = now - timedelta(days=45)
    old_transient = _job(profile_id, state="failed", mode="private-puzzle", updated_at=old)
    old_private = _job(profile_id, state="ready", mode="private-puzzle", updated_at=old)
    old_queued = _job(profile_id, state="queued", mode="personalized", updated_at=now - timedelta(days=10))
    old_running = _job(profile_id, state="running", mode="private-puzzle", updated_at=old)
    fresh_failed = _job(profile_id, state="failed", mode="private-puzzle", updated_at=now - timedelta(days=1))
    fresh_private = _job(profile_id, state="ready", mode="private-puzzle", updated_at=now - timedelta(days=1))
    preserved_review = _job(profile_id, state="ready", mode="personalized", updated_at=old)
    ids = {
        "profile": profile_id,
        "oldTransient": old_transient.id,
        "oldPrivate": old_private.id,
        "oldQueued": old_queued.id,
        "oldRunning": old_running.id,
        "freshFailed": fresh_failed.id,
        "freshPrivate": fresh_private.id,
        "preservedReview": preserved_review.id,
    }
    with module.app.app_context():
        db.session.add_all(
            [
                StartingProfile(
                    id=profile_id,
                    draft={"id": profile_id, "version": 1},
                    profile={"profileId": profile_id},
                    updated_at=_stamp(now),
                ),
                EpistemeProfileRecord(
                    id=profile_id,
                    revision=0,
                    profile_json={"profileId": profile_id, "revision": 0},
                    updated_at=_stamp(now),
                ),
                CalibrationSessionRecord(
                    id=str(uuid4()),
                    revision=1,
                    payload={"scope": {"kind": "profile", "profileId": profile_id}},
                ),
                PersonalSolveSession(
                    id=str(uuid4()),
                    profile_id=profile_id,
                    puzzle_hash="d" * 64,
                    initial_grid=[],
                    writer_digest="e" * 64,
                    accepted_seq=0,
                    status="finished",
                    created_at=_stamp(old),
                    updated_at=_stamp(old),
                ),
                old_transient,
                old_private,
                old_queued,
                old_running,
                fresh_failed,
                fresh_private,
                preserved_review,
                FutureGridDraftPrivateSelection(
                    job_id=old_private.id,
                    profile_id=profile_id,
                    selection_json={"candidate": "private"},
                    created_at=_stamp(old),
                ),
                _candidate(profile_id, old_private.id, old),
                # An orphan from an interrupted cleanup is also expired and
                # should be removed, while a candidate with a surviving job
                # must remain untouched.
                FuturePuzzleV2CandidateRecord(
                    profile_id=profile_id,
                    candidate_hash="f" * 64,
                    candidate_id="personalized-" + "a" * 32,
                    job_id=str(uuid4()),
                    manifest_json={"schemaVersion": 2},
                    created_at=_stamp(old),
                ),
                FuturePuzzleV2CandidateRecord(
                    profile_id=profile_id,
                    candidate_hash="1" * 64,
                    candidate_id="personalized-" + "2" * 32,
                    job_id=preserved_review.id,
                    manifest_json={"schemaVersion": 2},
                    created_at=_stamp(old),
                ),
            ]
        )
        db.session.commit()
    return ids


def test_retention_dry_run_and_commit_preserve_history(api):
    seeded = _seed(api)
    client = api.app.test_client()
    profile_id = seeded["profile"]

    preview = client.post(
        f"/api/future/profile/{profile_id}/retention",
        json={"dryRun": True},
    )
    assert preview.status_code == 200
    assert preview.json["dryRun"] is True
    assert preview.json["policy"]["version"] == "future-local-retention-v1"
    assert preview.json["selected"] == {
        "transientJobs": 2,
        "privateReadyJobs": 1,
        "privateSelections": 1,
        "v2Candidates": 2,
    }
    assert preview.json["deleted"]["jobs"] == 0

    result = client.post(f"/api/future/profile/{profile_id}/retention", json={})
    assert result.status_code == 200
    assert result.json["deleted"] == {
        "jobs": 3,
        "privateSelections": 1,
        "v2Candidates": 2,
    }

    with api.app.app_context():
        assert db.session.get(StartingProfile, profile_id) is not None
        assert db.session.get(EpistemeProfileRecord, profile_id) is not None
        assert PersonalSolveSession.query.filter_by(profile_id=profile_id).count() == 1
        assert CalibrationSessionRecord.query.count() == 1
        assert db.session.get(FutureGridDraftJob, seeded["oldTransient"]) is None
        assert db.session.get(FutureGridDraftJob, seeded["oldPrivate"]) is None
        assert db.session.get(FutureGridDraftJob, seeded["oldQueued"]) is None
        assert db.session.get(FutureGridDraftJob, seeded["oldRunning"]) is not None
        assert db.session.get(FutureGridDraftJob, seeded["freshFailed"]) is not None
        assert db.session.get(FutureGridDraftJob, seeded["freshPrivate"]) is not None
        assert db.session.get(FutureGridDraftJob, seeded["preservedReview"]) is not None
        assert FutureGridDraftPrivateSelection.query.count() == 0
        assert FuturePuzzleV2CandidateRecord.query.filter_by(
            profile_id=profile_id
        ).count() == 1
        assert db.session.get(
            FuturePuzzleV2CandidateRecord, (profile_id, "1" * 64)
        ) is not None


def test_retention_is_origin_and_input_checked(api):
    seeded = _seed(api)
    client = api.app.test_client()
    profile_id = seeded["profile"]
    assert client.post(
        f"/api/future/profile/{profile_id}/retention",
        headers={"Origin": "https://attacker.invalid"},
        json={},
    ).status_code == 403
    assert client.post(
        f"/api/future/profile/{profile_id}/retention",
        json={"unexpected": True},
    ).status_code == 400
    assert client.post(
        "/api/future/profile/not-a-uuid/retention", json={}
    ).status_code == 400
