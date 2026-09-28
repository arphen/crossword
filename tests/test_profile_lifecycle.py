"""Profile deletion removes owned history and fences late worker writes."""

from uuid import uuid4

from tests.test_api_isolated import api, no_network  # noqa: F401
from src.crossword.calibration_api import CalibrationSessionRecord
from src.crossword.database import db
from src.crossword.episteme_store import EpistemeProfileRecord
from src.crossword.future import StartingProfile
from src.crossword.future_grid_jobs import FutureGridDraftJob, process_next_grid_draft
from src.crossword.future_puzzles import FuturePuzzleManifestRecord
from src.crossword.session_journal import PersonalSolveSession


def _seed(module):
    profile_id = str(uuid4())
    calibration_id = str(uuid4())
    session_id = str(uuid4())
    job_id = str(uuid4())
    with module.app.app_context():
        db.session.add_all(
            [
                StartingProfile(
                    id=profile_id,
                    draft={"id": profile_id, "version": 1},
                    profile={"profileId": profile_id},
                    updated_at="2026-09-27T00:00:00Z",
                ),
                EpistemeProfileRecord(
                    id=profile_id,
                    revision=1,
                    profile_json={"profileId": profile_id, "evidence": []},
                    updated_at="2026-09-27T00:00:00Z",
                ),
                # The calibration payload is scoped explicitly so the delete
                # route cannot accidentally remove guest journals.
                CalibrationSessionRecord(
                    id=calibration_id,
                    revision=1,
                    payload={
                        "scope": {"kind": "profile", "profileId": profile_id}
                    },
                ),
                PersonalSolveSession(
                    id=session_id,
                    profile_id=profile_id,
                    puzzle_hash="a" * 64,
                    initial_grid=[],
                    writer_digest="b" * 64,
                    accepted_seq=0,
                    status="active",
                    created_at="2026-09-27T00:00:00Z",
                    updated_at="2026-09-27T00:00:00Z",
                ),
                FutureGridDraftJob(
                    id=job_id,
                    profile_id=profile_id,
                    idempotency_key=str(uuid4()),
                    request_digest="c" * 64,
                    request_json={"mode": "private-puzzle", "profileId": profile_id},
                    state="running",
                    attempt=1,
                    lease_token=str(uuid4()),
                    lease_until="2099-09-27T00:00:00Z",
                    cancel_requested=False,
                    result_json=None,
                    error=None,
                    created_at="2026-09-27T00:00:00Z",
                    updated_at="2026-09-27T00:00:00Z",
                ),
                FuturePuzzleManifestRecord(
                    puzzle_hash="a" * 64,
                    puzzle_id="shared-puzzle",
                    manifest_json={"id": "shared-puzzle"},
                    created_at="2026-09-27T00:00:00Z",
                ),
            ]
        )
        db.session.commit()
    return profile_id, calibration_id, session_id, job_id


def test_delete_profile_removes_owned_records_and_retains_shared_manifest(api):
    profile_id, calibration_id, session_id, job_id = _seed(api)
    client = api.app.test_client()

    response = client.delete(f"/api/future/profile/{profile_id}")

    assert response.status_code == 200
    assert response.json == {
        "deleted": True,
        "profileId": profile_id,
        "sharedPuzzleManifests": "retained",
    }
    with api.app.app_context():
        assert db.session.get(StartingProfile, profile_id) is None
        assert db.session.get(EpistemeProfileRecord, profile_id) is None
        assert db.session.get(PersonalSolveSession, session_id) is None
        assert db.session.get(FutureGridDraftJob, job_id) is None
        assert db.session.get(CalibrationSessionRecord, calibration_id) is None
        assert db.session.get(FuturePuzzleManifestRecord, "a" * 64) is not None

    # A worker that was already in-flight observes the missing job through its
    # lease fence and cannot recreate a profile-owned result after deletion.
    assert process_next_grid_draft(api.app, generator=lambda **_: {}) is False


def test_delete_profile_is_origin_checked_and_idempotent_boundary(api):
    profile_id, *_ = _seed(api)
    client = api.app.test_client()

    assert client.delete(
        f"/api/future/profile/{profile_id}",
        headers={"Origin": "https://attacker.invalid"},
    ).status_code == 403
    assert client.delete("/api/future/profile/not-a-uuid").status_code == 400
    assert client.delete(f"/api/future/profile/{profile_id}").status_code == 200
    assert client.delete(f"/api/future/profile/{profile_id}").status_code == 404
