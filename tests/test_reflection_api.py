"""Postgame reflection endpoint tests against the real local Flask stack."""

from datetime import datetime, timezone
import json
from uuid import uuid4

import pytest

from tests.test_api_isolated import api, no_network  # noqa: F401
from tests.test_future_api import draft
from src.crossword.episteme_store import EpistemeProfileRecord
import src.crossword.reflection_api as reflection_module
import src.crossword.private_puzzle_generation as private_generation
from src.crossword.future_puzzles import (
    FuturePuzzleManifestRecord,
    FutureSolveAnalysisRecord,
)
from src.crossword.reflection_api import (
    FutureReflectionActionRecord,
    FutureReflectionDeckRecord,
    FutureReflectionResponseRecord,
    _authored_cards,
    _analysis_summary,
    _hash,
    _history_generation_runtime,
    _reflection_model_cards,
    reflection_api,
    validate_authored_cards,
)
from src.crossword.session_journal import PersonalSolveSession


@pytest.fixture
def reflection_app(api):
    if "reflection_api" not in api.app.blueprints:
        api.app.register_blueprint(reflection_api)
    with api.app.app_context():
        api.db.create_all()
    return api, api.app.test_client()


def finished_session(reflection_app, *, finished=True, finalized=True):
    api, client = reflection_app
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
    puzzle_hash = "a" * 64
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    with api.app.app_context():
        api.db.session.add(
            PersonalSolveSession(
                id=session_id,
                profile_id=profile_id,
                puzzle_hash=puzzle_hash,
                initial_grid=[],
                writer_digest="b" * 64,
                accepted_seq=1,
                status="finished" if finished else "active",
                created_at=now,
                updated_at=now,
            )
        )
        api.db.session.add(
            FutureSolveAnalysisRecord(
                session_id=session_id,
                puzzle_hash=puzzle_hash,
                analysis_version="knowledge-reducer-v1",
                analysis_json={
                    "analysisVersion": "knowledge-reducer-v1",
                    "observations": [],
                },
                finalized=finalized,
                updated_at=now,
            )
        )
        api.db.session.commit()
    return client, profile_id, session_id


def get_deck(client, session_id):
    response = client.get(f"/api/future/sessions/{session_id}/reflections")
    assert response.status_code == 200, response.json
    return response.json["deck"]


def response_body(session_id, card, position, choice="keep", response_id=None):
    return {
        "schemaVersion": 1,
        "responseId": response_id or str(uuid4()),
        "sessionId": session_id,
        "cardId": card["cardId"],
        "cardVersion": card["version"],
        "shownPosition": position,
        "recordedAt": "2026-09-26T12:00:00.000Z",
        "response": choice,
    }


def post_response(client, session_id, card, position, value):
    return client.post(
        f"/api/future/sessions/{session_id}/reflections/{card['cardId']}/response",
        json=value,
        headers={"Origin": "http://localhost"},
    )


def pulse_body(session_id, *, pulse_id=None, worth="yes"):
    return {
        "schemaVersion": 1,
        "pulseId": pulse_id or str(uuid4()),
        "sessionId": session_id,
        "recordedAt": "2026-09-28T12:00:00.000Z",
        "worth": worth,
        "returnIntent": "same-world-new-angle",
        "roughEdge": "none",
    }


def test_playtest_pulse_is_bounded_idempotent_and_answer_free(reflection_app):
    client, profile_id, session_id = finished_session(reflection_app)
    value = pulse_body(session_id)
    url = f"/api/future/sessions/{session_id}/playtest-pulse"
    first = client.post(url, json=value, headers={"Origin": "http://localhost"})
    assert first.status_code == 200, first.json
    assert first.json["pulse"] == value
    assert first.json["replayed"] is False
    assert first.json["revision"] == 1
    assert len(first.json["evidenceIds"]) == 3

    replay = client.post(url, json=value, headers={"Origin": "http://localhost"})
    assert replay.status_code == 200
    assert replay.json["replayed"] is True
    assert replay.json["revision"] == 1

    conflicting = {**value, "worth": "no"}
    assert (
        client.post(url, json=conflicting, headers={"Origin": "http://localhost"}).status_code
        == 409
    )
    deck = client.get(f"/api/future/sessions/{session_id}/reflections")
    assert deck.status_code == 200
    assert deck.json["playtestPulse"]["worth"] == "yes"
    assert deck.json["playtestPulse"]["sessionId"] == session_id
    assert "answer" not in json.dumps(deck.json["playtestPulse"]).casefold()
    history = client.get(f"/api/future/profile/{profile_id}/history?limit=1")
    assert history.status_code == 200
    assert history.json["history"][0]["playtest"]["returnIntent"] == (
        "same-world-new-angle"
    )
    assert history.json["calibration"]["playtest"]["pulseCount"] == 1
    assert history.json["calibration"]["playtest"]["worthCounts"] == {"yes": 1}

    api = reflection_app[0]
    with api.app.app_context():
        profile = api.db.session.get(EpistemeProfileRecord, profile_id)
        performance = [
            item
            for item in profile.profile_json["evidence"]
            if item.get("type") == "performance"
        ]
        assert {item["measure"] for item in performance} == {
            "playtest-worth",
            "playtest-return",
            "playtest-rough-edge",
        }


def test_playtest_pulse_requires_finished_session_and_exact_contract(reflection_app):
    client, _, session_id = finished_session(reflection_app, finished=False)
    url = f"/api/future/sessions/{session_id}/playtest-pulse"
    assert (
        client.post(
            url,
            json=pulse_body(session_id),
            headers={"Origin": "http://localhost"},
        ).status_code
        == 409
    )

    client, _, session_id = finished_session(reflection_app)
    malformed = pulse_body(session_id)
    malformed["extra"] = "ignored"
    response = client.post(
        f"/api/future/sessions/{session_id}/playtest-pulse",
        json=malformed,
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 422


def test_reflections_require_finished_finalized_host_replay(reflection_app):
    unfinished_client, _, session_id = finished_session(reflection_app, finished=False)
    response = unfinished_client.get(f"/api/future/sessions/{session_id}/reflections")
    assert response.status_code == 409

    client, _, finalized_session_id = finished_session(reflection_app, finalized=False)
    response = client.get(f"/api/future/sessions/{finalized_session_id}/reflections")
    assert response.status_code == 409
    assert client.get(f"/api/future/sessions/{uuid4()}/reflections").status_code == 404


def test_profile_history_projects_finished_games_without_answers(reflection_app):
    client, profile_id, session_id = finished_session(reflection_app)
    api = reflection_app[0]
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    with api.app.app_context():
        manifest = FuturePuzzleManifestRecord(
            puzzle_hash="a" * 64,
            puzzle_id="private-history-fixture",
            manifest_json={
                "metadata": {"title": "A remembered thread"},
                "provenance": {
                    "model": "gemma4:26b",
                    "weekdayRecipe": {"id": "wednesday"},
                    "personalizationReceipt": {
                        "version": "private-personalization-receipt-v1",
                        "epistemeRevision": 4,
                        "epistemeDigest": "f" * 64,
                        "inputs": {
                            "claimCount": 2,
                            "associationCount": 1,
                            "recentExposureCount": 3,
                            "languageThread": True,
                            "difficultyRecommendation": "balanced",
                        },
                        "associationSteering": {
                            "projectionCount": 2,
                            "eligibleCount": 1,
                            "expiredCount": 1,
                            "excludedResponseCount": 0,
                            "diversity": {"uniqueRelations": 2, "status": "varied"},
                        },
                    },
                    "clueDiversity": {
                        "status": "varied",
                        "nonDefinitionFamilies": ["pun", "spoken-equivalent"],
                        "repair": {"rewrittenCount": 2},
                    },
                },
                "entries": [{"id": "1A", "answer": "SECRET", "clue": "Hidden word"}],
            },
            created_at=now,
        )
        api.db.session.add(manifest)
        api.db.session.commit()

    response = client.get(f"/api/future/profile/{profile_id}/history?limit=1")
    assert response.status_code == 200
    assert response.json["profileId"] == profile_id
    assert response.json["limit"] == 1
    assert response.json["history"] == [
        {
            "sessionId": session_id,
            "status": "finished",
            "createdAt": response.json["history"][0]["createdAt"],
            "updatedAt": response.json["history"][0]["updatedAt"],
            "finished": True,
            "title": "A remembered thread",
            "weekday": "wednesday",
            "model": "gemma4:26b",
            "analysis": response.json["history"][0]["analysis"],
            "personalization": {
                "version": "private-history-personalization-v1",
                "epistemeRevision": 4,
                "claimCount": 2,
                "associationCount": 1,
                "recentExposureCount": 3,
                "languageThread": True,
                "difficultyRecommendation": "balanced",
                "associationSteering": {
                    "projectionCount": 2,
                    "eligibleCount": 1,
                    "expiredCount": 1,
                    "excludedResponseCount": 0,
                    "uniqueRelations": 2,
                    "diversityStatus": "varied",
                },
                "clueDiversity": {
                    "status": "varied",
                    "nonDefinitionFamilyCount": 2,
                    "repairRewrittenCount": 2,
                },
                "interpretation": "answer-free-generation-lane-summary",
            },
        }
    ]
    assert "SECRET" not in response.get_data(as_text=True)
    assert response.json["calibration"]["version"] == "private-play-calibration-report-v1"
    assert response.json["calibration"]["status"] == "insufficient-observations"
    assert response.json["calibration"]["sessionCount"] == 1
    assert client.get(f"/api/future/profile/{profile_id}/history?limit=0").status_code == 400
    assert client.get(f"/api/future/profile/{uuid4()}/history").status_code == 404


def test_history_projects_bounded_durable_generation_receipt_without_answers(reflection_app):
    client, profile_id, _ = finished_session(reflection_app)
    api = reflection_app[0]
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    with api.app.app_context():
        manifest = FuturePuzzleManifestRecord(
            puzzle_hash="a" * 64,
            puzzle_id="private-history-runtime-fixture",
            manifest_json={
                "metadata": {"title": "A durable thread"},
                "provenance": {
                    "jobRuntime": {
                        "version": "private-job-runtime-v1",
                        "durable": True,
                        "attempt": 2,
                        "recovery": "reclaimed",
                        "elapsedSeconds": 142.7894,
                        "profileId": profile_id,
                        "request": {"answers": ["SECRET"]},
                    }
                },
                "entries": [{"id": "1A", "answer": "SECRET", "clue": "Hidden word"}],
            },
            created_at=now,
        )
        api.db.session.add(manifest)
        api.db.session.commit()

    response = client.get(f"/api/future/profile/{profile_id}/history?limit=1")
    assert response.status_code == 200
    assert response.json["history"][0]["generation"] == {
        "version": "private-history-generation-v1",
        "durable": True,
        "attempt": 2,
        "recovery": "reclaimed",
        "elapsedSeconds": 142.789,
        "interpretation": "answer-free-durable-generation-summary",
    }
    body = response.get_data(as_text=True)
    assert "SECRET" not in body
    assert profile_id not in json.dumps(response.json["history"][0]["generation"])


@pytest.mark.parametrize(
    "runtime",
    [
        None,
        {"version": "private-job-runtime-v0", "durable": True, "attempt": 1, "recovery": "first-attempt"},
        {"version": "private-job-runtime-v1", "durable": True, "attempt": 0, "recovery": "first-attempt"},
        {"version": "private-job-runtime-v1", "durable": True, "attempt": 1, "recovery": "reclaimed"},
        {"version": "private-job-runtime-v1", "durable": True, "attempt": 9, "recovery": "reclaimed"},
        {"version": "private-job-runtime-v1", "durable": False, "attempt": 1, "recovery": "first-attempt"},
    ],
)
def test_history_generation_projection_fails_open_for_invalid_receipts(runtime):
    assert _history_generation_runtime({"jobRuntime": runtime}) is None


def test_profile_calibration_export_is_bounded_and_content_free(reflection_app):
    client, profile_id, _ = finished_session(reflection_app)
    api = reflection_app[0]
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    with api.app.app_context():
        manifest = FuturePuzzleManifestRecord(
            puzzle_hash="a" * 64,
            puzzle_id="private-calibration-fixture",
            manifest_json={
                "metadata": {"title": "A title that is not exported"},
                "provenance": {
                    "model": "gemma4:26b",
                    "weekdayRecipe": {"id": "thursday"},
                },
                "entries": [{"id": "1A", "answer": "SECRET", "clue": "Hidden word"}],
            },
            created_at=now,
        )
        api.db.session.add(manifest)
        api.db.session.commit()

    response = client.get(
        f"/api/future/profile/{profile_id}/calibration-export?limit=1"
    )
    assert response.status_code == 200
    assert response.headers["Content-Disposition"].startswith("attachment;")
    payload = response.json
    assert payload["version"] == "private-play-calibration-export-v1"
    assert payload["profileId"] == profile_id
    assert payload["historyLimit"] == 1
    assert payload["traceCount"] == 1
    integrity = payload.pop("integrity")
    assert integrity["algorithm"] == "sha256"
    assert integrity["value"] == _hash(payload)
    assert len(payload["traces"]) == 1
    assert payload["traces"][0]["analysis"]["version"] == (
        "private-session-analysis-summary-v1"
    )
    assert "SECRET" not in response.get_data(as_text=True)
    assert "Hidden word" not in response.get_data(as_text=True)
    assert "A title that is not exported" not in response.get_data(as_text=True)
    assert "answers" in payload["redactions"]
    assert client.get(
        f"/api/future/profile/{profile_id}/calibration-export?limit=0"
    ).status_code == 400
    assert client.get(
        f"/api/future/profile/{uuid4()}/calibration-export"
    ).status_code == 404


def test_profile_calibration_report_groups_observed_outcomes_without_answers():
    history = [
        {
            "finished": True,
            "weekday": "wednesday",
            "model": "gemma4:26b",
            "analysis": {
                "version": "private-session-analysis-summary-v1",
                "entryCount": 4,
                "correctCount": 3,
                "independentCount": 2,
                "supportedCount": 1,
                "assistedCount": 0,
                "incorrectCount": 1,
                "untouchedCount": 0,
                "incorrectAttemptCount": 1,
            },
        },
        {
            "finished": True,
            "weekday": "thursday",
            "model": "qwen3.8:27b",
            "analysis": {
                "version": "private-session-analysis-summary-v1",
                "entryCount": 4,
                "correctCount": 4,
                "independentCount": 4,
                "supportedCount": 0,
                "assistedCount": 0,
                "incorrectCount": 0,
                "untouchedCount": 0,
                "incorrectAttemptCount": 0,
            },
        },
        {
            "finished": True,
            "weekday": "wednesday",
            "model": "gemma4:26b",
            "analysis": {
                "version": "private-session-analysis-summary-v1",
                "entryCount": 4,
                "correctCount": 2,
                "independentCount": 1,
                "supportedCount": 1,
                "assistedCount": 1,
                "incorrectCount": 2,
                "untouchedCount": 1,
                "incorrectAttemptCount": 2,
            },
        },
    ]

    report = reflection_module._profile_calibration_report(history, limit=12)

    assert report["status"] == "observational"
    assert report["sessionCount"] == 3
    assert report["totals"]["entryCount"] == 12
    assert report["totals"]["completionRate"] == 0.75
    assert report["totals"]["supportRate"] == 0.25
    assert report["byWeekday"]["wednesday"]["sessionCount"] == 2
    assert report["byModel"]["qwen3.8:27b"]["independentCount"] == 4
    assert "answer" not in str(report).casefold()


def test_finished_session_get_returns_one_immutable_authored_deck(reflection_app):
    api = reflection_app[0]
    client, _, session_id = finished_session(reflection_app)
    first = client.get(f"/api/future/sessions/{session_id}/reflections")
    second = client.get(f"/api/future/sessions/{session_id}/reflections")
    assert first.status_code == second.status_code == 200
    assert first.json == second.json
    assert first.json["responses"] == []
    assert first.json["analysisSummary"]["version"] == "private-session-analysis-summary-v1"
    deck = first.json["deck"]
    assert deck["sessionId"] == session_id
    assert deck["deckVersion"] == 1
    assert len(deck["cards"]) == 3
    assert all(
        card["source"] == "authored" and card["status"] == "approved"
        for card in deck["cards"]
    )
    assert all(card["generationReceipt"] is None for card in deck["cards"])
    assert [
        card["cardId"]
        for card in _authored_cards(
            "2026-09-26T12:00:00.000Z", "00000000-0000-4000-8000-000000000001"
        )
    ] != [
        card["cardId"]
        for card in _authored_cards(
            "2026-09-26T12:00:00.000Z", "00000000-0000-4000-8000-000000000002"
        )
    ]
    with reflection_app[0].app.app_context():
        record = reflection_app[0].db.session.get(
            FutureReflectionDeckRecord, session_id
        )
        assert record.deck_json == deck


def test_optional_model_reflection_rewrite_keeps_authored_mappings_and_contract(
    monkeypatch,
):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "message": {
                    "content": json.dumps(
                        {
                            "cards": [
                                {
                                    "category": category,
                                    "text": f"I may enjoy a {category} turn here.",
                                    "keep": f"More {category} moments could fit.",
                                    "notForMe": f"Fewer {category} moments for now.",
                                    "pass": f"Leave {category} undecided.",
                                }
                                for category in reflection_module.CARD_BANK
                            ]
                        }
                    )
                }
            }

    monkeypatch.setenv("CROSSWORD_REFLECTION_MODEL_CARDS", "1")
    monkeypatch.setattr(
        reflection_module, "_reflection_model_name", lambda *_args: "gemma4:26b"
    )
    monkeypatch.setattr(reflection_module.requests, "post", lambda *args, **kwargs: FakeResponse())
    cards = _reflection_model_cards(
        "2026-09-26T12:00:00.000Z",
        "00000000-0000-4000-8000-000000000001",
        {"hasWordplay": True, "hasDiscovery": True},
        _authored_cards(
            "2026-09-26T12:00:00.000Z",
            "00000000-0000-4000-8000-000000000001",
        ),
    )

    assert len(cards) == 3
    assert all(card["source"] == "model" for card in cards)
    assert all(card["generationReceipt"]["model"] == "gemma4:26b" for card in cards)
    assert all(card["generationReceipt"]["reviewStatus"] == "approved" for card in cards)
    assert validate_authored_cards(cards)


def test_reflection_model_follows_frozen_puzzle_model_without_env_override(monkeypatch):
    monkeypatch.delenv("CROSSWORD_REFLECTION_MODEL", raising=False)
    monkeypatch.setattr(
        private_generation,
        "_resolve_model_override",
        lambda value: value,
    )
    monkeypatch.setattr(
        private_generation,
        "_installed_model",
        lambda: "gemma4:26b",
    )

    assert reflection_module._reflection_model_name("qwen3.8:27b") == "qwen3.8:27b"
    assert reflection_module._reflection_model_name() == "gemma4:26b"


def test_analysis_summary_is_answer_free_and_separates_recall_paths():
    summary = _analysis_summary(
        {
            "observations": [
                {
                    "finalState": "correct",
                    "outcome": "independent-retrieval",
                    "correctnessShownCellIds": [],
                    "revealedCellIds": [],
                    "incorrectAttemptCount": 1,
                },
                {
                    "finalState": "correct",
                    "outcome": "supported-retrieval",
                    "correctnessShownCellIds": [],
                    "revealedCellIds": [],
                    "incorrectAttemptCount": 0,
                },
                {
                    "finalState": "correct",
                    "outcome": "reveal-assisted-correction",
                    "correctnessShownCellIds": [],
                    "revealedCellIds": ["r1c1"],
                    "incorrectAttemptCount": 2,
                },
                {
                    "finalState": "incomplete",
                    "outcome": "untouched",
                    "correctnessShownCellIds": [],
                    "revealedCellIds": [],
                    "incorrectAttemptCount": 0,
                },
            ]
        }
    )

    assert summary == {
        "version": "private-session-analysis-summary-v1",
        "entryCount": 4,
        "correctCount": 3,
        "incompleteCount": 1,
        "incorrectCount": 0,
        "independentCount": 1,
        "supportedCount": 1,
        "assistedCount": 1,
        "exposureCount": 0,
        "untouchedCount": 1,
        "checkedCount": 0,
        "revealedCount": 1,
        "incorrectAttemptCount": 3,
        "interpretation": "difficulty-and-recall-signal-only",
        "masteryClaim": "none",
    }


def test_finished_session_deck_uses_frozen_puzzle_context(reflection_app):
    api = reflection_app[0]
    client, _, session_id = finished_session(reflection_app)
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    manifest = {
        "entries": [
            {"id": "across-1", "answer": "CAT", "clue": "A turn?"},
            {"id": "down-2", "answer": "LONGANSWER", "clue": "A less familiar term"},
        ]
    }
    with api.app.app_context():
        api.db.session.add(
            FuturePuzzleManifestRecord(
                puzzle_hash="a" * 64,
                puzzle_id="contextual-fixture",
                manifest_json=manifest,
                created_at=now,
            )
        )
        api.db.session.commit()

    deck = get_deck(client, session_id)
    contextual = [card for card in deck["cards"] if card["relatedEntryIds"]]
    assert contextual
    assert all(card["source"] == "authored" for card in contextual)
    assert all("reflection-context-v1" in card["groundingRefs"] for card in contextual)
    assert any(
        "puzzle:" in reference
        for card in contextual
        for reference in card["groundingRefs"]
    )
    assert any(card["relatedEntryIds"] == ["across-1"] for card in contextual)


def test_reflection_context_recognizes_generated_language_clue_wording(reflection_app):
    api = reflection_app[0]
    client, _, session_id = finished_session(reflection_app)
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    manifest = {
        "metadata": {
            "notepad": "Private local generation · language thread: German"
        },
        "entries": [
            {"id": "across-1", "answer": "HALLO", "clue": "German for hello"},
            {"id": "down-2", "answer": "ECHO", "clue": "Sound that returns"},
        ],
    }
    with api.app.app_context():
        api.db.session.add(
            FuturePuzzleManifestRecord(
                puzzle_hash="a" * 64,
                puzzle_id="language-context-fixture",
                manifest_json=manifest,
                created_at=now,
            )
        )
        api.db.session.commit()

    deck = get_deck(client, session_id)

    language_card = next(
        card for card in deck["cards"] if card["relatedEntryIds"] == ["across-1"]
    )
    assert language_card["text"] == (
        "A small foreign-language doorway feels welcome when the clue tells me how to enter it."
    )
    assert deck["languageLearning"] == {
        "language": "German",
        "code": "de",
        "state": "review",
        "reviewDue": True,
        "relatedEntryIds": ["across-1"],
        "source": "explicit-setup",
        "masteryClaim": "none",
    }


def test_all_sixty_authored_cards_pass_shared_domain_validation():
    authored = []
    for number in range(1, 129):
        session_id = f"00000000-0000-4000-8000-{number:012d}"
        authored.extend(_authored_cards("2026-09-26T12:00:00.000Z", session_id))
    unique = {card["cardId"]: card for card in authored}
    assert len(unique) == 60
    assert validate_authored_cards(list(unique.values()))


@pytest.mark.parametrize(
    ("choice", "expected_key", "expected_stance"),
    [
        ("keep", "keep", "seek"),
        ("not-for-me", "not-for-me", "avoid"),
        ("pass", None, None),
    ],
)
def test_response_maps_only_the_selected_stance_and_replays(
    choice, expected_key, expected_stance, reflection_app
):
    api = reflection_app[0]
    client, profile_id, session_id = finished_session(reflection_app)
    deck = get_deck(client, session_id)
    card = deck["cards"][0]
    body = response_body(session_id, card, 0, choice)
    first = post_response(client, session_id, card, 0, body)
    assert first.status_code == 200, first.json
    evidence = first.json["evidence"]
    assert evidence["type"] == "preference-signal"
    assert evidence["source"] == "reflection-card"
    assert evidence["sessionId"] == session_id
    assert evidence["response"] == choice
    assert list(evidence["mappings"]) == (
        [] if expected_key is None else [expected_key]
    )
    if expected_key is not None:
        assert evidence["mappings"][expected_key][0]["stance"] == expected_stance
    retry = post_response(client, session_id, card, 0, body)
    assert retry.status_code == 200, retry.json
    assert retry.json["replayed"] is True
    assert retry.json["evidence"] == evidence
    assert retry.json["revision"] == first.json["revision"]
    with api.app.app_context():
        stored = api.db.session.get(FutureReflectionResponseRecord, body["responseId"])
        profile = api.db.session.get(EpistemeProfileRecord, profile_id)
        assert stored.status == "complete"
        assert profile.revision == 1
        if choice == "pass":
            assert profile.profile_json["projection"]["claims"] == []
        else:
            assert len(profile.profile_json["projection"]["claims"]) == 1
            assert (
                profile.profile_json["projection"]["claims"][0]["stance"]
                == expected_stance
            )


def test_reflection_response_requires_same_origin_exact_card_position_and_schema(
    reflection_app,
):
    client, _, session_id = finished_session(reflection_app)
    deck = get_deck(client, session_id)
    card = deck["cards"][1]
    body = response_body(session_id, card, 1)
    url = f"/api/future/sessions/{session_id}/reflections/{card['cardId']}/response"
    assert (
        client.post(
            url, json=body, headers={"Origin": "https://other.invalid"}
        ).status_code
        == 403
    )
    assert client.post(url, json=body).status_code == 403
    assert (
        post_response(
            client, session_id, card, 1, {**body, "surprise": True}
        ).status_code
        == 422
    )
    assert (
        post_response(
            client, session_id, card, 1, {**body, "shownPosition": 0}
        ).status_code
        == 422
    )
    other_card = deck["cards"][0]
    assert (
        client.post(
            f"/api/future/sessions/{session_id}/reflections/{other_card['cardId']}/response",
            json=body,
            headers={"Origin": "http://localhost"},
        ).status_code
        == 422
    )
    stale_version = {**body, "cardVersion": 99}
    assert post_response(client, session_id, card, 1, stale_version).status_code == 422
    wrong_session = {**body, "sessionId": str(uuid4())}
    assert post_response(client, session_id, card, 1, wrong_session).status_code == 422


def test_reflection_card_and_response_id_conflicts_are_rejected(reflection_app):
    client, _, session_id = finished_session(reflection_app)
    deck = get_deck(client, session_id)
    card = deck["cards"][0]
    first_body = response_body(session_id, card, 0, "keep")
    assert post_response(client, session_id, card, 0, first_body).status_code == 200

    different_choice = {**first_body, "response": "not-for-me"}
    conflict = post_response(client, session_id, card, 0, different_choice)
    assert conflict.status_code == 409

    other_card = deck["cards"][1]
    reused_id = response_body(
        session_id, other_card, 1, "keep", first_body["responseId"]
    )
    conflict = post_response(client, session_id, other_card, 1, reused_id)
    assert conflict.status_code == 409


def test_shared_validation_failure_does_not_reserve_the_card(reflection_app):
    api = reflection_app[0]
    client, _, session_id = finished_session(reflection_app)
    card = get_deck(client, session_id)["cards"][0]
    invalid = response_body(session_id, card, 0)
    invalid["recordedAt"] = "2026-09-26 12:00:00+00:00"
    # Python's fromisoformat accepts the space separator, but the shared
    # domain contract requires its canonical `T` separator.
    assert datetime.fromisoformat(invalid["recordedAt"])
    rejected = post_response(client, session_id, card, 0, invalid)
    assert rejected.status_code == 422
    with api.app.app_context():
        assert (
            api.db.session.query(FutureReflectionResponseRecord)
            .filter_by(session_id=session_id, card_id=card["cardId"])
            .count()
            == 0
        )

    corrected = {**invalid, "recordedAt": "2026-09-26T12:00:00.000Z"}
    accepted = post_response(client, session_id, card, 0, corrected)
    assert accepted.status_code == 200, accepted.json
    assert accepted.json["response"]["responseId"] == invalid["responseId"]


def test_response_retries_same_update_after_a_competing_profile_revision(
    reflection_app, monkeypatch
):
    api = reflection_app[0]
    client, profile_id, session_id = finished_session(reflection_app)
    cards = get_deck(client, session_id)["cards"]
    card, competing_card = cards[0], cards[1]
    body = response_body(session_id, card, 0, "keep")
    original_apply = reflection_module.apply_episteme_command
    calls = []

    def competing_profile_update(target_profile_id, current_revision, profile, command):
        calls.append((command["updateId"], command["baseRevision"]))
        if len(calls) == 1:
            competing_response = response_body(session_id, competing_card, 1, "keep")
            competing_evidence = reflection_module.convert_response_to_evidence(
                competing_card, competing_response
            )
            competing_command = {
                "updateId": str(uuid4()),
                "profileId": target_profile_id,
                "baseRevision": current_revision,
                "recordedAt": competing_response["recordedAt"],
                "evidence": [competing_evidence],
                "evidenceActions": [],
            }
            original_apply(
                target_profile_id,
                current_revision,
                profile,
                competing_command,
            )
            raise reflection_module.EpistemeRevisionConflict(
                "Stale profile revision: another response won the commit"
            )
        return original_apply(target_profile_id, current_revision, profile, command)

    monkeypatch.setattr(
        reflection_module, "apply_episteme_command", competing_profile_update
    )
    response = post_response(client, session_id, card, 0, body)
    assert response.status_code == 200, response.json
    assert len(calls) == 2
    assert calls[0][0] == calls[1][0]
    assert [revision for _, revision in calls] == [0, 1]
    assert response.json["revision"] == 2
    with api.app.app_context():
        stored_profile = api.db.session.get(EpistemeProfileRecord, profile_id)
        stored_response = api.db.session.get(
            FutureReflectionResponseRecord, body["responseId"]
        )
        assert stored_profile.revision == 2
        assert stored_response.status == "complete"


def test_reflection_retract_and_restore_are_immutable_idempotent_actions(
    reflection_app,
):
    api = reflection_app[0]
    client, profile_id, session_id = finished_session(reflection_app)
    card = get_deck(client, session_id)["cards"][0]
    response_value = response_body(session_id, card, 0, "keep")
    saved = post_response(client, session_id, card, 0, response_value)
    assert saved.status_code == 200
    snapshot = client.get(f"/api/future/sessions/{session_id}/reflections").json
    assert snapshot["deck"] == get_deck(client, session_id)
    assert snapshot["responses"][0]["response"] == response_value
    assert snapshot["responses"][0]["evidence"] == saved.json["evidence"]
    assert snapshot["responses"][0]["epistemeRevision"] == saved.json["revision"]
    assert snapshot["responses"][0]["state"] == "active"

    route = (
        f"/api/future/sessions/{session_id}/reflections/{card['cardId']}"
        f"/responses/{response_value['responseId']}/actions"
    )
    retract = {
        "schemaVersion": 1,
        "actionId": str(uuid4()),
        "targetResponseId": response_value["responseId"],
        "recordedAt": "2026-09-26T12:01:00.000Z",
        "action": "retract",
    }
    assert client.post(route, json=retract).status_code == 403
    assert (
        client.post(
            route,
            json={**retract, "unexpected": True},
            headers={"Origin": "http://localhost"},
        ).status_code
        == 422
    )
    wrong_target = {**retract, "targetResponseId": str(uuid4())}
    assert (
        client.post(
            route, json=wrong_target, headers={"Origin": "http://localhost"}
        ).status_code
        == 422
    )

    first = client.post(route, json=retract, headers={"Origin": "http://localhost"})
    assert first.status_code == 200, first.json
    assert (
        first.json["evidenceAction"]["targetEvidenceId"] == response_value["responseId"]
    )
    assert first.json["evidenceAction"]["action"] == "retract"
    snapshot = client.get(f"/api/future/sessions/{session_id}/reflections").json
    assert snapshot["responses"][0]["state"] == "retracted"
    assert (
        snapshot["responses"][0]["latestActionEpistemeRevision"]
        == first.json["revision"]
    )
    assert snapshot["responses"][0]["actions"] == [first.json["action"]]
    assert first.json["action"]["recordedAt"] != retract["recordedAt"]
    with api.app.app_context():
        profile = api.db.session.get(EpistemeProfileRecord, profile_id)
        assert profile.revision == 2
        assert profile.profile_json["projection"]["claims"] == []
    retry = client.post(route, json=retract, headers={"Origin": "http://localhost"})
    assert retry.status_code == 200
    assert retry.json["replayed"] is True
    assert retry.json["revision"] == 2
    conflict = client.post(
        route,
        json={**retract, "action": "restore"},
        headers={"Origin": "http://localhost"},
    )
    assert conflict.status_code == 409

    restore = {
        **retract,
        "actionId": str(uuid4()),
        "recordedAt": "2026-09-26T12:02:00.000Z",
        "action": "restore",
    }
    restored = client.post(route, json=restore, headers={"Origin": "http://localhost"})
    assert restored.status_code == 200, restored.json
    snapshot = client.get(f"/api/future/sessions/{session_id}/reflections").json
    assert snapshot["responses"][0]["state"] == "active"
    assert snapshot["responses"][0]["actions"] == [
        first.json["action"],
        restored.json["action"],
    ]
    assert datetime.fromisoformat(
        first.json["action"]["recordedAt"].replace("Z", "+00:00")
    ) < datetime.fromisoformat(
        restored.json["action"]["recordedAt"].replace("Z", "+00:00")
    )
    with api.app.app_context():
        profile = api.db.session.get(EpistemeProfileRecord, profile_id)
        actions = (
            api.db.session.query(FutureReflectionActionRecord)
            .filter_by(session_id=session_id)
            .all()
        )
        assert profile.revision == 3
        assert len(profile.profile_json["evidenceActions"]) == 2
        assert len(actions) == 2
        assert len(profile.profile_json["projection"]["claims"]) == 1


def test_reflection_action_validation_happens_before_reservation(reflection_app):
    api = reflection_app[0]
    client, _, session_id = finished_session(reflection_app)
    card = get_deck(client, session_id)["cards"][0]
    response_value = response_body(session_id, card, 0, "keep")
    assert post_response(client, session_id, card, 0, response_value).status_code == 200
    route = (
        f"/api/future/sessions/{session_id}/reflections/{card['cardId']}"
        f"/responses/{response_value['responseId']}/actions"
    )
    invalid = {
        "schemaVersion": 1,
        "actionId": str(uuid4()),
        "targetResponseId": response_value["responseId"],
        "recordedAt": "2026-09-26 12:01:00+00:00",
        "action": "retract",
    }
    rejected = client.post(route, json=invalid, headers={"Origin": "http://localhost"})
    assert rejected.status_code == 422
    with api.app.app_context():
        assert (
            api.db.session.query(FutureReflectionActionRecord)
            .filter_by(session_id=session_id)
            .count()
            == 0
        )

    corrected = {**invalid, "recordedAt": "2026-09-26T12:01:00.000Z"}
    accepted = client.post(
        route, json=corrected, headers={"Origin": "http://localhost"}
    )
    assert accepted.status_code == 200, accepted.json
    assert accepted.json["action"]["actionId"] == invalid["actionId"]


def test_corrected_action_recovers_legacy_invalid_pending_reservation(reflection_app):
    api = reflection_app[0]
    client, _, session_id = finished_session(reflection_app)
    card = get_deck(client, session_id)["cards"][0]
    response_value = response_body(session_id, card, 0, "keep")
    assert post_response(client, session_id, card, 0, response_value).status_code == 200
    route = (
        f"/api/future/sessions/{session_id}/reflections/{card['cardId']}"
        f"/responses/{response_value['responseId']}/actions"
    )
    invalid = {
        "schemaVersion": 1,
        "actionId": str(uuid4()),
        "targetResponseId": response_value["responseId"],
        "recordedAt": "2026-09-26 12:01:00+00:00",
        "action": "retract",
    }
    with api.app.app_context():
        api.db.session.add(
            FutureReflectionActionRecord(
                action_id=invalid["actionId"],
                session_id=session_id,
                card_id=card["cardId"],
                target_response_id=response_value["responseId"],
                action_hash=reflection_module._hash(invalid),
                action_json=invalid,
                evidence_action_json=None,
                episteme_revision=None,
                status="pending",
                recorded_at=invalid["recordedAt"],
            )
        )
        api.db.session.commit()

    corrected = {**invalid, "recordedAt": "2026-09-26T12:01:00.000Z"}
    accepted = client.post(
        route, json=corrected, headers={"Origin": "http://localhost"}
    )
    assert accepted.status_code == 200, accepted.json
    assert accepted.json["action"]["actionId"] == invalid["actionId"]
    assert accepted.json["action"]["recordedAt"] != corrected["recordedAt"]
    with api.app.app_context():
        actions = (
            api.db.session.query(FutureReflectionActionRecord)
            .filter_by(session_id=session_id)
            .all()
        )
        assert len(actions) == 1
        assert actions[0].status == "complete"
        assert actions[0].action_hash == reflection_module._hash(corrected)


def test_reflection_actions_use_host_order_and_reject_illegal_repeats(reflection_app):
    api = reflection_app[0]
    client, _, session_id = finished_session(reflection_app)
    card = get_deck(client, session_id)["cards"][0]
    response_value = response_body(session_id, card, 0, "keep")
    assert post_response(client, session_id, card, 0, response_value).status_code == 200
    route = (
        f"/api/future/sessions/{session_id}/reflections/{card['cardId']}"
        f"/responses/{response_value['responseId']}/actions"
    )
    restore_first = {
        "schemaVersion": 1,
        "actionId": str(uuid4()),
        "targetResponseId": response_value["responseId"],
        "recordedAt": "2099-01-01T00:00:00.000Z",
        "action": "restore",
    }
    conflict = client.post(
        route, json=restore_first, headers={"Origin": "http://localhost"}
    )
    assert conflict.status_code == 409

    actions = [
        {
            **restore_first,
            "actionId": str(uuid4()),
            "recordedAt": "2099-01-01T00:00:00.000Z",
            "action": "retract",
        },
        {
            **restore_first,
            "actionId": str(uuid4()),
            "recordedAt": "2098-01-01T00:00:00.000Z",
            "action": "restore",
        },
        {
            **restore_first,
            "actionId": str(uuid4()),
            "recordedAt": "1900-01-01T00:00:00.000Z",
            "action": "retract",
        },
    ]
    accepted = [
        client.post(route, json=value, headers={"Origin": "http://localhost"})
        for value in actions
    ]
    assert [response.status_code for response in accepted] == [200, 200, 200]
    host_actions = [response.json["action"] for response in accepted]
    host_times = [
        datetime.fromisoformat(item["recordedAt"].replace("Z", "+00:00"))
        for item in host_actions
    ]
    assert host_times == sorted(host_times)
    assert all(
        host_action["recordedAt"] != client_action["recordedAt"]
        for host_action, client_action in zip(host_actions, actions, strict=True)
    )

    duplicate = {**actions[-1], "actionId": str(uuid4())}
    rejected = client.post(
        route, json=duplicate, headers={"Origin": "http://localhost"}
    )
    assert rejected.status_code == 409
    snapshot = client.get(f"/api/future/sessions/{session_id}/reflections").json
    assert snapshot["responses"][0]["state"] == "retracted"
    assert [item["action"] for item in snapshot["responses"][0]["actions"]] == [
        "retract",
        "restore",
        "retract",
    ]


def test_pending_reflection_action_replays_after_profile_commit(
    reflection_app, monkeypatch
):
    api = reflection_app[0]
    client, profile_id, session_id = finished_session(reflection_app)
    card = get_deck(client, session_id)["cards"][0]
    response_value = response_body(session_id, card, 0, "keep")
    assert post_response(client, session_id, card, 0, response_value).status_code == 200
    route = (
        f"/api/future/sessions/{session_id}/reflections/{card['cardId']}"
        f"/responses/{response_value['responseId']}/actions"
    )
    body = {
        "schemaVersion": 1,
        "actionId": str(uuid4()),
        "targetResponseId": response_value["responseId"],
        "recordedAt": "2099-01-01T00:00:00.000Z",
        "action": "retract",
    }
    original_apply = reflection_module.apply_episteme_command
    failed = False

    def commit_then_drop_receipt(*args, **kwargs):
        nonlocal failed
        result = original_apply(*args, **kwargs)
        if not failed and args[3]["updateId"] == str(
            reflection_module.uuid5(
                reflection_module.NAMESPACE_URL,
                f"crossword-reflection-action:{session_id}:{body['actionId']}:v1",
            )
        ):
            failed = True
            raise RuntimeError("injected crash after profile commit")
        return result

    monkeypatch.setattr(
        reflection_module, "apply_episteme_command", commit_then_drop_receipt
    )
    with pytest.raises(RuntimeError, match="after profile commit"):
        client.post(route, json=body, headers={"Origin": "http://localhost"})
    monkeypatch.setattr(reflection_module, "apply_episteme_command", original_apply)

    retry = client.post(route, json=body, headers={"Origin": "http://localhost"})
    assert retry.status_code == 200, retry.json
    assert retry.json["replayed"] is True
    assert retry.json["action"]["recordedAt"] != body["recordedAt"]
    snapshot = client.get(f"/api/future/sessions/{session_id}/reflections").json
    assert snapshot["responses"][0]["state"] == "retracted"
    with api.app.app_context():
        actions = (
            api.db.session.query(FutureReflectionActionRecord)
            .filter_by(session_id=session_id)
            .all()
        )
        profile = api.db.session.get(EpistemeProfileRecord, profile_id)
        assert len(actions) == 1
        assert actions[0].status == "complete"
        assert len(profile.profile_json["evidenceActions"]) == 1
