"""Delayed language recall remains separate from unreviewed exposure."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from tests.test_api_isolated import api, no_network  # noqa: F401
from src.crossword.database import db
from src.crossword.episteme_store import EpistemeProfileRecord
from src.crossword.future import StartingProfile
from src.crossword.future_puzzles import FuturePuzzleManifestRecord
from src.crossword.learning_review import (
    FutureLearningReviewRecord,
    _adaptive_interval_hours,
    _fit_forgetting_model,
)
from src.crossword.session_journal import PersonalSolveSession


# A bounded, deterministic study trace for the provisional scheduler.  The
# timestamps are expressed as days after exposure so the same trace can be
# materialized against any test clock.  Assisted responses are deliberately
# present in the trace but are excluded from the forgetting-fit observations.
# This fixture describes scheduler transitions only; it is not a mastery label.
DELAYED_RECALL_STUDY_FIXTURE = (
    {"daysAfterExposure": 10, "response": "remembered", "mode": "independent"},
    {"daysAfterExposure": 20, "response": "remembered", "mode": "independent"},
    {"daysAfterExposure": 30, "response": "remembered", "mode": "assisted"},
    {"daysAfterExposure": 40, "response": "not-yet", "mode": "independent"},
    {"daysAfterExposure": 50, "response": "remembered", "mode": "independent"},
    {"daysAfterExposure": 60, "response": "remembered", "mode": "independent"},
    {"daysAfterExposure": 70, "response": "not-yet", "mode": "independent"},
    {"daysAfterExposure": 80, "response": "remembered", "mode": "independent"},
    {"daysAfterExposure": 88, "response": "not-yet", "mode": "independent"},
)


def _stamp(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _seed(module, count=1, exposure_age_days=2):
    profile_id = str(uuid4())
    session_id = str(uuid4())
    puzzle_hash = "a" * 64
    exposure = datetime.now(timezone.utc) - timedelta(days=exposure_age_days)
    answers = [
        "JA",
        "NEIN",
        "GUT",
        "ROT",
        "BLAU",
        "GRUEN",
        "HALLO",
        "DANKE",
        "BITTE",
        "HAUS",
        "WASSER",
        "SONNE",
    ][:count]
    entries = [
        {
            "id": f"across-{index}",
            "answer": answer,
            "clue": "Yes, in German" if index == 1 else f"German clue {index}",
            "number": index,
            "direction": "across",
        }
        for index, answer in enumerate(answers, start=1)
    ]
    task_links = [
        {
            "entryId": f"across-{index}",
            "tasks": [
                {
                    "taskId": f"private-answer-form:{answer}",
                    "taskKind": "answer-form",
                    "direction": "clue-to-answer",
                    "language": "de",
                    "clueFamily": "language-recurrence",
                    "contentReview": "unreviewed",
                }
            ],
        }
        for index, answer in enumerate(answers, start=1)
    ]
    with module.app.app_context():
        db.session.add_all(
            [
                StartingProfile(
                    id=profile_id,
                    draft={"id": profile_id, "version": 1},
                    profile={"profileId": profile_id, "learningLanguage": "German"},
                    updated_at=_stamp(exposure),
                ),
                PersonalSolveSession(
                    id=session_id,
                    profile_id=profile_id,
                    puzzle_hash=puzzle_hash,
                    initial_grid=[],
                    writer_digest="b" * 64,
                    accepted_seq=0,
                    status="finished",
                    created_at=_stamp(exposure),
                    updated_at=_stamp(exposure),
                ),
                FuturePuzzleManifestRecord(
                    puzzle_hash=puzzle_hash,
                    puzzle_id="private-review-puzzle",
                    manifest_json={"entries": entries},
                    created_at=_stamp(exposure),
                ),
                EpistemeProfileRecord(
                    id=profile_id,
                    revision=1,
                    profile_json={
                        "profileId": profile_id,
                        "revision": 1,
                        "evidence": [
                            {
                                "evidenceId": f"session-analysis:{session_id}:v1",
                                "recordedAt": _stamp(exposure),
                                "type": "session-analysis",
                                "analysis": {"sessionId": session_id},
                                "taskLinks": task_links,
                            }
                        ],
                    },
                    updated_at=_stamp(exposure),
                ),
            ]
        )
        db.session.commit()
    return profile_id


def _append_review(module, profile_id, item, response, mode, recorded_at):
    with module.app.app_context():
        db.session.add(
            FutureLearningReviewRecord(
                id=str(uuid4()),
                profile_id=profile_id,
                task_id=item["taskId"],
                language=item["language"],
                source_evidence_id=item["sourceEvidenceId"],
                response=response,
                input_mode=mode,
                recorded_at=_stamp(recorded_at),
            )
        )
        db.session.commit()


def test_due_language_review_is_clued_and_records_independent_response(api):
    profile_id = _seed(api)
    client = api.app.test_client()

    due = client.get(f"/api/future/profile/{profile_id}/learning-review")
    assert due.status_code == 200
    assert due.json["policy"]["delayHours"] == 24
    assert due.json["policy"]["intervalHours"] == [24, 168, 720]
    assert due.json["policy"]["maxItems"] == 12
    assert due.json["policy"]["schedulerVersion"] == "language-recall-scheduler-v2"
    assert due.json["policy"]["forgettingModel"] == {
        "version": "language-recall-forgetting-grid-v1",
        "method": "bounded-exponential-grid-v1",
        "status": "insufficient-data",
        "sampleCount": 0,
        "rememberedCount": 0,
        "notYetCount": 0,
        "minimumSamples": 8,
        "requiresMixedOutcomes": True,
        "schedulerCoupled": False,
    }
    assert due.json["remaining"] == 0
    assert len(due.json["due"]) == 1
    item = due.json["due"][0]
    assert item["clue"] == "Yes, in German"
    assert item["direction"] == "across"
    assert item["entryId"] == "across-1"
    assert item["language"] == "de"
    assert item["length"] == 2
    assert item["number"] == 1
    assert item["intervalHours"] == 24
    assert item["schedulerVersion"] == "language-recall-scheduler-v2"
    assert item["overdueHours"] >= 0
    assert item["schedulerPriority"] >= 1
    assert item["taskId"].startswith("language-review:")
    assert "JA" not in item["taskId"]
    assert "sourceTaskId" not in item
    assert item["taskPack"]["packId"] == "synthetic-local-language-pairs-v1"
    assert item["taskPack"]["pairId"] == "de-en-ja-v1"
    assert item["taskPack"]["sourceText"] == "yes"
    assert item["taskPack"]["reviewStatus"] == "synthetic-unadmitted"
    assert "targetText" not in item["taskPack"]
    answer = client.get(
        f"/api/future/profile/{profile_id}/learning-review/answer",
        query_string={"taskId": item["taskId"]},
    )
    assert answer.status_code == 200
    assert answer.json["answer"] == "JA"
    assert answer.json["taskPack"]["pairId"] == "de-en-ja-v1"
    assert answer.json["taskPack"]["grammar"]["version"] == "language-task-grammar-v1"
    response = client.post(
        f"/api/future/profile/{profile_id}/learning-review",
        json={
            "taskId": item["taskId"],
            "response": "remembered",
            "mode": "independent",
        },
    )
    assert response.status_code == 201
    assert response.json["mode"] == "independent"
    assert (
        client.get(f"/api/future/profile/{profile_id}/learning-review").json["due"]
        == []
    )
    with api.app.app_context():
        record = FutureLearningReviewRecord.query.filter_by(profile_id=profile_id).one()
        assert record.response == "remembered"


def test_due_review_preserves_the_stored_task_pack_receipt(api):
    profile_id = _seed(api)
    with api.app.app_context():
        profile = db.session.get(EpistemeProfileRecord, profile_id)
        profile.profile_json = deepcopy(profile.profile_json)
        evidence = profile.profile_json["evidence"][0]
        task = evidence["taskLinks"][0]["tasks"][0]
        task["taskPack"] = {
            "packId": "archived-pack-v1",
            "packVersion": "language-task-pairs-v1",
            "packDigest": "a" * 64,
            "pairId": "archived-de-ja-v1",
            "sourceLanguage": "en",
            "targetLanguage": "de",
            "sourceText": "archived yes",
            "direction": "source-to-target",
            "source": {"sourceId": "archived-source-v1"},
            "grammar": {"version": "language-task-grammar-v1"},
            "reviewStatus": "synthetic-unadmitted",
            "semanticStatus": "not-established",
            "masteryClaim": "none",
        }
        db.session.commit()

    response = api.app.test_client().get(
        f"/api/future/profile/{profile_id}/learning-review"
    )
    assert response.status_code == 200
    item = response.json["due"][0]
    assert item["taskPack"]["pairId"] == "archived-de-ja-v1"
    assert item["taskPack"]["sourceText"] == "archived yes"
    assert item["taskPack"]["packDigest"] == "a" * 64
    assert "targetText" not in item["taskPack"]


def test_learning_review_limits_are_explicit_and_bounded(api):
    profile_id = _seed(api)
    client = api.app.test_client()

    limited = client.get(f"/api/future/profile/{profile_id}/learning-review?limit=6")
    assert limited.status_code == 200
    assert limited.json["remaining"] == 0
    assert (
        client.get(
            f"/api/future/profile/{profile_id}/learning-review?limit=4"
        ).status_code
        == 400
    )
    assert (
        client.get(
            f"/api/future/profile/{profile_id}/learning-review?limit=3&limit=6"
        ).status_code
        == 400
    )


def test_scheduler_gently_lengthens_later_independent_streaks():
    assert _adaptive_interval_hours(0, 1) == 24
    assert _adaptive_interval_hours(1, 1) == 168
    assert _adaptive_interval_hours(2, 2) == 900
    assert _adaptive_interval_hours(2, 3) == 1080
    assert _adaptive_interval_hours(2, 5) == 1080


def test_delayed_recall_study_fixture_traces_spacing_and_assistance(api):
    """Exercise a bounded exposure-to-recall trace without a mastery claim."""
    profile_id = _seed(api, exposure_age_days=100)
    client = api.app.test_client()
    item = client.get(f"/api/future/profile/{profile_id}/learning-review").json["due"][
        0
    ]
    exposure_anchor = datetime.now(timezone.utc) - timedelta(days=100)
    transitions = []

    for observation in DELAYED_RECALL_STUDY_FIXTURE:
        _append_review(
            api,
            profile_id,
            item,
            observation["response"],
            observation["mode"],
            exposure_anchor + timedelta(days=observation["daysAfterExposure"]),
        )
        due = client.get(f"/api/future/profile/{profile_id}/learning-review").json[
            "due"
        ]
        assert len(due) == 1
        transitions.append(
            (due[0]["reviewStage"], due[0]["intervalHours"], due[0]["lastMode"])
        )

    assert transitions == [
        (2, 168, "independent"),
        (3, 900, "independent"),
        (1, 24, "assisted"),
        (1, 24, "independent"),
        (2, 168, "independent"),
        (3, 900, "independent"),
        (1, 24, "independent"),
        (2, 168, "independent"),
        (1, 24, "independent"),
    ]

    policy = client.get(f"/api/future/profile/{profile_id}/learning-review").json[
        "policy"
    ]
    forgetting_model = policy["forgettingModel"]
    # The assisted event is retained in the study trace but excluded from the
    # independent diagnostic sample.  The fit remains diagnostic-only.
    assert forgetting_model["status"] == "fitted"
    assert forgetting_model["sampleCount"] == 8
    assert forgetting_model["rememberedCount"] == 5
    assert forgetting_model["notYetCount"] == 3
    assert forgetting_model["schedulerCoupled"] is False


def test_forgetting_model_waits_for_enough_mixed_independent_outcomes():
    assert (
        _fit_forgetting_model([{"delayHours": 24, "outcome": "remembered"}] * 8)[
            "status"
        ]
        == "insufficient-data"
    )
    assert (
        _fit_forgetting_model(
            [
                {"delayHours": 24, "outcome": "remembered"},
                {"delayHours": 48, "outcome": "not-yet"},
            ]
            * 3
        )["status"]
        == "insufficient-data"
    )


def test_forgetting_model_is_deterministic_and_scheduler_independent():
    observations = [
        {"delayHours": 24, "outcome": "remembered"},
        {"delayHours": 48, "outcome": "remembered"},
        {"delayHours": 72, "outcome": "not-yet"},
        {"delayHours": 96, "outcome": "not-yet"},
    ] * 2
    first = _fit_forgetting_model(observations)
    second = _fit_forgetting_model(observations)
    assert first == second
    assert first["status"] == "fitted"
    assert first["schedulerCoupled"] is False
    assert first["method"] == "bounded-exponential-grid-v1"
    assert 0.01 <= first["decayPerDay"] <= 2.0
    assert first["halfLifeDays"] > 0


def test_learning_policy_exposes_fitted_model_without_using_it_for_due_dates(api):
    profile_id = _seed(api)
    client = api.app.test_client()
    item = client.get(f"/api/future/profile/{profile_id}/learning-review").json["due"][
        0
    ]
    exposure_time = datetime.now(timezone.utc) - timedelta(days=2)
    outcomes = [
        "remembered",
        "remembered",
        "remembered",
        "not-yet",
        "not-yet",
        "remembered",
        "not-yet",
        "remembered",
    ]
    with api.app.app_context():
        db.session.add_all(
            [
                FutureLearningReviewRecord(
                    id=str(uuid4()),
                    profile_id=profile_id,
                    task_id=item["taskId"],
                    language="de",
                    source_evidence_id=item["sourceEvidenceId"],
                    response=outcome,
                    input_mode="independent",
                    recorded_at=_stamp(exposure_time + timedelta(hours=index * 6)),
                )
                for index, outcome in enumerate(outcomes)
            ]
        )
        db.session.commit()

    policy = client.get(f"/api/future/profile/{profile_id}/learning-review").json[
        "policy"
    ]
    model = policy["forgettingModel"]
    assert model["status"] == "fitted"
    assert model["sampleCount"] == 8
    assert model["rememberedCount"] == 5
    assert model["notYetCount"] == 3
    assert model["schedulerCoupled"] is False


def test_learning_review_limit_defaults_to_three_and_reports_remaining(api):
    profile_id = _seed(api, count=8)
    client = api.app.test_client()
    path = f"/api/future/profile/{profile_id}/learning-review"

    first = client.get(path)
    assert first.status_code == 200
    assert len(first.json["due"]) == 3
    assert first.json["remaining"] == 5
    assert {item["entryId"] for item in first.json["due"]} <= {
        f"across-{index}" for index in range(1, 9)
    }

    second = client.get(path, query_string={"limit": "6"})
    assert len(second.json["due"]) == 6
    assert second.json["remaining"] == 2

    all_due = client.get(path, query_string={"limit": "12"})
    assert len(all_due.json["due"]) == 8
    assert all_due.json["remaining"] == 0


def test_learning_review_rejects_limits_outside_the_supported_budgets(api):
    profile_id = _seed(api)
    client = api.app.test_client()
    path = f"/api/future/profile/{profile_id}/learning-review"
    for limit in ("0", "2", "4", "13", "03", "many"):
        response = client.get(path, query_string={"limit": limit})
        assert response.status_code == 400
    duplicate = client.get(path + "?limit=3&limit=6")
    assert duplicate.status_code == 400


def test_independent_recall_moves_to_the_weekly_spacing_stage(api):
    profile_id = _seed(api)
    client = api.app.test_client()
    item = client.get(f"/api/future/profile/{profile_id}/learning-review").json["due"][
        0
    ]
    response = client.post(
        f"/api/future/profile/{profile_id}/learning-review",
        json={
            "taskId": item["taskId"],
            "response": "remembered",
            "mode": "independent",
        },
    )
    assert response.status_code == 201
    with api.app.app_context():
        record = FutureLearningReviewRecord.query.filter_by(profile_id=profile_id).one()
        record.recorded_at = _stamp(datetime.now(timezone.utc) - timedelta(days=8))
        api.db.session.commit()
    due_again = client.get(f"/api/future/profile/{profile_id}/learning-review")
    assert due_again.status_code == 200
    assert due_again.json["due"][0]["reviewStage"] == 2
    assert due_again.json["due"][0]["lastResponse"] == "remembered"
    assert due_again.json["due"][0]["lastMode"] == "independent"


def test_non_independent_response_resets_the_success_streak(api):
    profile_id = _seed(api)
    client = api.app.test_client()
    item = client.get(f"/api/future/profile/{profile_id}/learning-review").json["due"][
        0
    ]
    now = datetime.now(timezone.utc)
    with api.app.app_context():
        db.session.add_all(
            [
                FutureLearningReviewRecord(
                    id=str(uuid4()),
                    profile_id=profile_id,
                    task_id=item["taskId"],
                    language="de",
                    source_evidence_id=item["sourceEvidenceId"],
                    response="remembered",
                    input_mode="independent",
                    recorded_at=_stamp(now - timedelta(days=16)),
                ),
                FutureLearningReviewRecord(
                    id=str(uuid4()),
                    profile_id=profile_id,
                    task_id=item["taskId"],
                    language="de",
                    source_evidence_id=item["sourceEvidenceId"],
                    response="not-yet",
                    input_mode="independent",
                    recorded_at=_stamp(now - timedelta(days=9)),
                ),
                FutureLearningReviewRecord(
                    id=str(uuid4()),
                    profile_id=profile_id,
                    task_id=item["taskId"],
                    language="de",
                    source_evidence_id=item["sourceEvidenceId"],
                    response="remembered",
                    input_mode="independent",
                    recorded_at=_stamp(now - timedelta(days=8)),
                ),
            ]
        )
        db.session.commit()

    due = client.get(f"/api/future/profile/{profile_id}/learning-review")
    assert due.status_code == 200
    assert due.json["due"][0]["reviewStage"] == 2


def test_learning_review_rejects_cross_origin_and_unknown_tasks(api):
    profile_id = _seed(api)
    client = api.app.test_client()
    assert (
        client.post(
            f"/api/future/profile/{profile_id}/learning-review",
            headers={"Origin": "https://attacker.invalid"},
            json={
                "taskId": "language-review:unknown",
                "response": "remembered",
                "mode": "independent",
            },
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/future/profile/{profile_id}/learning-review",
            json={
                "taskId": "language-review:unknown",
                "response": "remembered",
                "mode": "independent",
            },
        ).status_code
        == 409
    )
