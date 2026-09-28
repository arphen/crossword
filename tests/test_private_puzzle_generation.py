"""The local experimental puzzle endpoint returns solver-ready puzzles."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from tests.test_api_isolated import api, no_network  # noqa: F401
from src.crossword.future_grid_jobs import FutureGridDraftJob, process_next_grid_draft
from src.crossword.database import db
from src.crossword.future import StartingProfile
from src.crossword.future_puzzles import register_legacy_puzzle
from src.crossword.learning_review import FutureLearningReviewRecord, _review_task_id
from src.crossword.models import Crossword
import src.crossword.learning_review as learning_review
import src.crossword.private_puzzle_generation as private_generation


@pytest.mark.parametrize(
    ("clue", "family", "signal"),
    [
        ("“Not a chance!”", "spoken-equivalent", "quote"),
        ("[Sigh of relief]", "nonverbal-expression", "brackets"),
        ("Safe and ___", "fill-blank", "fill-blank"),
        ("Thank you, in German", "factual-relation", "language-indicator"),
        ("Estimated arrival, briefly", "metalinguistic", "abbreviation-indicator"),
        ("Branch specialist?", "pun", "question-mark"),
        ("Felines (pl.)", "definition", "plural-marker"),
        ("Past tense of run", "definition", "tense-marker"),
        ("Purring pets", "definition", None),
    ],
)
def test_clue_family_observation_records_visible_signals_without_claiming_semantics(
    clue, family, signal
):
    observation = private_generation._clue_family_observation(clue)

    assert observation["family"] == family
    assert observation["confidence"] == "surface-signal-only"
    assert observation["uncertainty"] == ["semantic-family-unverified"]
    if signal is None:
        assert observation["signals"] == []
    else:
        assert observation["signals"][0]["kind"] == signal


def test_model_context_uses_soft_opening_associations_and_current_episteme():
    starting = SimpleNamespace(
        profile={
            "associations": ["echo", "moss"],
            "observations": ["A red thread", "A tuning fork"],
            "learningLanguage": "German",
        },
        draft={"firstStimulus": "thread-knot", "excluded": ["tension"]},
    )
    episteme = {
        "projection": {
            "associations": [
                {
                    "phrase": "afterglow",
                    "response": "kept",
                    "origin": "calibration-proposal",
                }
            ],
            "claims": [],
            "knowledge": [],
        }
    }

    context = private_generation._profile_context(starting, episteme)

    assert context["opening_associations"] == ["echo", "moss"]
    assert context["opening_observations"] == ["A red thread", "A tuning fork"]
    assert context["language_interest"] == "German"
    assert context["active_associations"][0]["phrase"] == "afterglow"


def test_association_steering_receipt_excludes_expired_or_rejected_paths():
    starting = SimpleNamespace(profile={"associations": [], "observations": []}, draft={})
    context = private_generation._profile_context(
        starting,
        {
            "projection": {
                "associations": [
                    {
                        "phrase": "kept thread",
                        "response": "kept",
                        "origin": "calibration-proposal",
                        "relation": "sound",
                        "calibrationProvenance": {"expired": False},
                    },
                    {
                        "phrase": "old thread",
                        "response": "kept",
                        "origin": "model-proposal",
                        "relation": "metaphor",
                        "modelProvenance": {"expired": True},
                    },
                    {
                        "phrase": "passed thread",
                        "response": "passed",
                        "origin": "model-proposal",
                        "relation": "sound",
                    },
                ],
                "claims": [],
                "knowledge": [],
            },
            "evidence": [],
        },
    )

    assert [item["phrase"] for item in context["active_associations"]] == ["kept thread"]
    assert context["association_steering"] == {
        "version": "private-association-steering-v1",
        "projectionCount": 3,
        "eligibleCount": 1,
        "expiredCount": 1,
        "excludedResponseCount": 1,
        "responseCounts": {"kept": 2, "passed": 1},
        "originCounts": {"calibration-proposal": 1, "model-proposal": 2},
        "relationCounts": {"metaphor": 1, "sound": 2},
        "diversity": {"uniqueRelations": 2, "status": "varied"},
        "reversible": True,
        "interpretation": "bounded-association-steering-not-a-personality-claim",
    }


def test_model_context_turns_explicit_clue_feedback_into_reversible_family_steering():
    starting = SimpleNamespace(
        profile={"associations": [], "observations": []},
        draft={},
    )
    context = private_generation._profile_context(
        starting,
        {
            "projection": {
                "claims": [
                    {
                        "concept": {
                            "conceptId": "association:en:clue%20surfaces%3A%20factual%20surface%20is%20unverified",
                            "label": "clue surfaces: factual surface is unverified",
                        },
                        "stance": "avoid",
                        "strength": 0.42,
                        "evidenceIds": ["explicit-clue-feedback-1"],
                    }
                ],
                "associations": [],
                "knowledge": [],
            },
            "evidence": [],
        },
    )

    assert context["clue_family_targets"] == [
        {
            "family": "factual-relation",
            "direction": "avoid",
            "strength": 0.42,
            "evidenceCount": 1,
            "source": "explicit-clue-feedback",
            "reversible": True,
        }
    ]


def test_model_context_maps_explicit_challenger_note_flags_to_closed_families():
    starting = SimpleNamespace(
        profile={"associations": [], "observations": []},
        draft={},
    )
    context = private_generation._profile_context(
        starting,
        {
            "projection": {
                "claims": [
                    {
                        "concept": {
                            "conceptId": "association:en:clue%20surfaces%3A%20local%20challenger%20recommends%20a%20safer%20foothold",
                            "label": "clue surfaces: local challenger recommends a safer foothold",
                        },
                        "stance": "seek",
                        "strength": 0.6,
                        "evidenceIds": ["explicit-challenger-note-1"],
                    }
                ],
                "associations": [],
                "knowledge": [],
            },
            "evidence": [],
        },
    )

    assert context["clue_family_targets"] == [
        {
            "family": "discovery",
            "direction": "include",
            "strength": 0.6,
            "evidenceCount": 1,
            "source": "explicit-clue-feedback",
            "reversible": True,
        }
    ]


def test_model_context_includes_recent_private_answer_exposure_without_claiming_mastery():
    starting = SimpleNamespace(
        profile={"associations": [], "observations": []},
        draft={},
    )
    context = private_generation._profile_context(
        starting,
        {
            "evidence": [
                {
                    "type": "session-analysis",
                    "taskLinks": [
                        {
                            "entryId": "across-1",
                            "tasks": [
                                {
                                    "taskId": "private-answer-form:RESONANCE",
                                    "contentReview": "unreviewed",
                                }
                            ],
                        }
                    ],
                }
            ],
            "projection": {"claims": [], "associations": [], "knowledge": []},
        },
    )

    assert context["recent_private_answers"] == ["RESONANCE"]


def test_model_context_turns_recent_solve_evidence_into_bounded_difficulty_calibration():
    starting = SimpleNamespace(profile={"associations": []}, draft={})
    context = private_generation._profile_context(
        starting,
        {
            "evidence": [
                {
                    "type": "session-analysis",
                    "analysis": {
                        "observations": [
                            {
                                "finalState": "correct",
                                "outcome": "independent-retrieval",
                                "incorrectAttemptCount": 0,
                            },
                            {
                                "finalState": "correct",
                                "outcome": "supported-retrieval",
                                "incorrectAttemptCount": 1,
                            },
                            {
                                "finalState": "incorrect",
                                "outcome": "incorrect-attempt",
                                "incorrectAttemptCount": 2,
                            },
                        ]
                    },
                }
            ],
            "projection": {"claims": [], "associations": [], "knowledge": []},
        },
    )

    assert context["play_calibration"] == {
        "status": "calibrated",
        "source": "solve-behavior",
        "interpretation": "difficulty-only",
        "reversible": True,
        "sessions": 1,
        "completionRate": 0.667,
        "independentRate": 0.333,
        "supportRate": 0.333,
        "mistakeRate": 1.0,
        "recommendation": "balanced",
        "recent": [
            {
                "completionRate": 0.667,
                "independentRate": 0.333,
                "supportRate": 0.333,
                "mistakeRate": 1.0,
                "entryCount": 3,
            }
        ],
    }


def test_play_calibration_is_more_footholds_for_heavy_support_or_low_completion():
    calibration = private_generation._play_calibration(
        [
            {
                "type": "session-analysis",
                "analysis": {
                    "observations": [
                        {
                            "finalState": "correct",
                            "outcome": "reveal-assisted-correction",
                            "incorrectAttemptCount": 0,
                        },
                        {
                            "finalState": "incomplete",
                            "outcome": "untouched",
                            "incorrectAttemptCount": 0,
                        },
                    ]
                },
            }
        ]
    )

    assert calibration["recommendation"] == "more-footholds"
    assert calibration["interpretation"] == "difficulty-only"


def test_playtest_pulse_is_a_bounded_difficulty_signal_and_not_a_taste_claim():
    calibration = private_generation._play_calibration(
        [
            {
                "type": "session-analysis",
                "analysis": {
                    "observations": [
                        {
                            "finalState": "correct",
                            "outcome": "independent-retrieval",
                            "incorrectAttemptCount": 0,
                        }
                    ]
                },
            },
            {
                "type": "performance",
                "evidenceId": "playtest-pulse:11111111-1111-4111-8111-111111111111:worth",
                "sessionId": "session-1",
                "measure": "playtest-worth",
                "value": "yes",
            },
            {
                "type": "performance",
                "evidenceId": "playtest-pulse:11111111-1111-4111-8111-111111111111:return",
                "sessionId": "session-1",
                "measure": "playtest-return",
                "value": "more-footholds",
            },
            {
                "type": "performance",
                "evidenceId": "playtest-pulse:11111111-1111-4111-8111-111111111111:rough-edge",
                "sessionId": "session-1",
                "measure": "playtest-rough-edge",
                "value": "too-opaque",
            },
        ]
    )

    assert calibration["source"] == "solve-behavior+playtest-pulse"
    assert calibration["recommendation"] == "more-footholds"
    assert calibration["playtest"] == {
        "sessionCount": 1,
        "worthCounts": {"yes": 1},
        "returnIntentCounts": {"more-footholds": 1},
        "roughEdgeCounts": {"too-opaque": 1},
        "interpretation": "game-specific-calibration-only",
        "reversible": True,
    }
    assert "taste" not in str(calibration).casefold()


def test_model_context_builds_a_small_reversible_language_review_lane():
    starting = SimpleNamespace(
        profile={"associations": [], "observations": [], "learningLanguage": "German"},
        draft={},
    )
    context = private_generation._profile_context(
        starting,
        {
            "evidence": [
                {
                    "type": "session-analysis",
                    "taskLinks": [
                        {
                            "entryId": "across-1",
                            "tasks": [
                                {
                                    "taskId": "private-answer-form:JA",
                                    "language": "de",
                                    "contentReview": "unreviewed",
                                },
                                {
                                    "taskId": "private-answer-form:THREAD",
                                    "language": "en",
                                    "contentReview": "unreviewed",
                                },
                            ],
                        }
                    ],
                }
            ],
            "projection": {"claims": [], "associations": [], "knowledge": []},
        },
    )

    assert context["language_learning"] == {
        "language": "German",
        "code": "de",
        "mode": "gentle-recurrence",
        "reviewDue": True,
        "reviewForms": ["JA"],
        "exposureCount": 1,
        "source": "explicit-setup",
        "masteryClaim": "none",
        "reversible": True,
        "eligibleReviewForms": [],
    }


def test_model_context_offers_one_private_language_starter_when_fill_supports_it(
    monkeypatch,
):
    monkeypatch.setattr(
        private_generation, "_local_fill_word_set", lambda: frozenset({"NEIN"})
    )
    starting = SimpleNamespace(
        profile={"associations": [], "observations": [], "learningLanguage": "German"},
        draft={},
    )

    context = private_generation._profile_context(
        starting,
        {"evidence": [], "projection": {"claims": [], "associations": [], "knowledge": []}},
    )

    learning = context["language_learning"]
    assert learning["reviewDue"] is False
    assert learning["starterForms"] == ["NEIN"]
    assert learning["candidateForms"] == ["NEIN"]
    assert learning["eligibleReviewForms"] == ["NEIN"]
    assert learning["starterPolicy"] == "private-language-starter-v1"
    assert learning["starterStatus"] == "synthetic-unadmitted-not-established"
    assert learning["exposureCount"] == 0


def test_model_context_uses_delayed_recall_outcomes_for_the_next_brief(api):
    profile_id = str(uuid4())
    starting = SimpleNamespace(
        id=profile_id,
        profile={"associations": [], "observations": [], "learningLanguage": "German"},
        draft={},
    )
    evidence_id = f"session-analysis:{uuid4()}:v1"
    tasks = [
        ("JA", "remembered", "independent"),
        ("NEIN", "remembered", "assisted"),
        ("OUI", "not-yet", "independent"),
        ("HALLO", None, None),
    ]
    evidence = {
        "evidenceId": evidence_id,
        "type": "session-analysis",
        "taskLinks": [
            {
                "entryId": "across-1",
                "tasks": [
                    {
                        "taskId": f"private-answer-form:{answer}",
                        "language": "de",
                        "contentReview": "unreviewed",
                    }
                    for answer, _response, _mode in tasks
                ],
            }
        ],
    }
    with api.app.app_context():
        for answer, response, mode in tasks:
            if response is None:
                continue
            source_task_id = f"private-answer-form:{answer}"
            db_record = FutureLearningReviewRecord(
                id=str(uuid4()),
                profile_id=profile_id,
                task_id=_review_task_id(profile_id, evidence_id, source_task_id),
                language="de",
                source_evidence_id=evidence_id,
                response=response,
                input_mode=mode,
                recorded_at="2026-09-27T00:00:00Z",
            )
            api.db.session.add(db_record)
        api.db.session.commit()

        context = private_generation._profile_context(
            starting,
            {
                "evidence": [evidence],
                "projection": {"claims": [], "associations": [], "knowledge": []},
            },
        )

    learning = context["language_learning"]
    assert learning["rememberedForms"] == ["JA"]
    assert learning["assistedForms"] == ["NEIN"]
    assert learning["notYetForms"] == ["OUI"]
    assert learning["pendingForms"] == ["HALLO"]
    assert learning["reviewForms"] == ["OUI", "NEIN", "HALLO"]
    assert learning["reviewDue"] is True


def test_model_context_puts_scheduler_due_forms_first_without_making_them_locks(
    api, monkeypatch
):
    profile_id = str(uuid4())
    starting = SimpleNamespace(
        id=profile_id,
        profile={"associations": [], "observations": [], "learningLanguage": "German"},
        draft={},
    )
    evidence_id = f"session-analysis:{uuid4()}:v1"
    evidence = {
        "evidenceId": evidence_id,
        "type": "session-analysis",
        "taskLinks": [
            {
                "entryId": "across-1",
                "tasks": [
                    {
                        "taskId": "private-answer-form:HALLO",
                        "language": "de",
                        "contentReview": "unreviewed",
                    },
                    {
                        "taskId": "private-answer-form:WASSER",
                        "language": "de",
                        "contentReview": "unreviewed",
                    },
                ],
            }
        ],
    }
    monkeypatch.setattr(
        learning_review,
        "_due",
        lambda _profile_id: [
            {
                "taskId": "language-review:due-ja",
                "sourceTaskId": "private-answer-form:HALLO",
            }
        ],
    )

    with api.app.app_context():
        context = private_generation._profile_context(
            starting,
            {
                "evidence": [evidence],
                "projection": {
                    "claims": [],
                    "associations": [],
                    "knowledge": [],
                },
            },
        )

    learning = context["language_learning"]
    assert learning["dueForms"] == ["HALLO"]
    assert learning["candidateForms"] == ["HALLO", "WASSER"]
    assert learning["candidateWeights"] == [
        {"form": "HALLO", "weight": 1.0, "reason": "due"},
        {"form": "WASSER", "weight": 0.65, "reason": "pending"},
    ]
    assert learning["reviewForms"] == ["HALLO", "WASSER"]
    assert learning["reviewDue"] is True


def test_scheduler_history_prioritizes_due_forms_without_changing_category_weight():
    weighted = private_generation._language_candidate_weights(
        {
            "candidateForms": ["HALLO", "WASSER", "NEIN"],
            "dueForms": ["HALLO", "WASSER"],
            "notYetForms": ["HALLO"],
            "rememberedForms": ["WASSER"],
            "pendingForms": ["NEIN"],
            "dueDetails": [
                {
                    "form": "HALLO",
                    "reviewStage": 2,
                    "intervalHours": 168,
                    "lastResponse": "not-yet",
                    "lastMode": "independent",
                },
                {
                    "form": "WASSER",
                    "reviewStage": 1,
                    "intervalHours": 24,
                    "lastResponse": "remembered",
                    "lastMode": "independent",
                },
            ],
        }
    )

    assert [item["form"] for item in weighted] == ["HALLO", "WASSER", "NEIN"]
    assert weighted[0]["weight"] == weighted[1]["weight"] == 1.0
    assert weighted[0]["priority"] > weighted[1]["priority"]
    assert weighted[0]["priorityReason"] == "scheduler-history"
    assert "priority" not in weighted[2]


def test_overdue_scheduler_history_adds_only_a_bounded_optional_bonus():
    weighted = private_generation._language_candidate_weights(
        {
            "candidateForms": ["HALLO"],
            "dueForms": ["HALLO"],
            "notYetForms": ["HALLO"],
            "dueDetails": [
                {
                    "form": "HALLO",
                    "reviewStage": 1,
                    "intervalHours": 24,
                    "lastResponse": "not-yet",
                    "lastMode": "independent",
                    "overdueHours": 48,
                    "schedulerPriority": 2.0,
                }
            ],
        }
    )

    assert weighted[0]["weight"] == 1.0
    assert weighted[0]["priorityReason"] == "scheduler-history-and-overdue"
    assert weighted[0]["overdueBonus"] == 0.15
    assert weighted[0]["priority"] <= 1.4


def test_theme_planning_avoids_recent_exposure_when_fresh_choices_exist(monkeypatch):
    monkeypatch.setattr(
        private_generation,
        "_chat",
        lambda *_args, **_kwargs: {"themes": ["ECHO", "MOSS", "THREAD", "FORK"]},
    )

    themes = private_generation._make_themes(
        "qwen3.8:27b",
        {"recent_private_answers": ["ECHO", "MOSS"]},
        "wednesday",
    )

    assert themes == ["THREAD", "FORK"]


def test_theme_exposure_receipt_counts_only_theme_entries_and_hides_forms():
    receipt = private_generation._theme_exposure_receipt(
        {"recent_private_answers": ["ECHO", "MOSS"]},
        [
            {"answer": "ECHO", "theme": True},
            {"answer": "THREAD", "theme": True},
            {"answer": "MOSS", "theme": False},
        ],
    )

    assert receipt["recentExposureCount"] == 2
    assert receipt["themeAnswerCount"] == 2
    assert receipt["freshThemeCount"] == 1
    assert receipt["repeatedThemeCount"] == 1
    assert "ECHO" not in receipt and "MOSS" not in receipt


def test_model_context_exposes_avoid_topics_as_steering_without_personality_claims():
    starting = SimpleNamespace(profile={"associations": []}, draft={})
    context = private_generation._profile_context(
        starting,
        {
            "projection": {
                "claims": [
                    {
                        "concept": {"label": "US officeholders"},
                        "kind": "topic",
                        "stance": "avoid",
                    },
                    {
                        "concept": {"label": "sound textures"},
                        "kind": "topic",
                        "stance": "seek",
                    },
                ],
                "associations": [],
                "knowledge": [],
            }
        },
    )

    assert context["avoid_topics"] == ["US officeholders"]
    assert context["preference_tensions"][1]["stance"] == "seek"


def test_model_context_derives_reversible_clue_family_targets_only_from_reflection_evidence():
    starting = SimpleNamespace(profile={"associations": []}, draft={})
    context = private_generation._profile_context(
        starting,
        {
            "evidence": [
                {
                    "evidenceId": "reflection-response:wordplay",
                    "type": "preference-signal",
                    "source": "reflection-card",
                },
                {
                    "evidenceId": "explicit:wordplay",
                    "type": "explicit-preference",
                },
            ],
            "projection": {
                "claims": [
                    {
                        "concept": {
                            "conceptId": "clue-wordplay",
                            "label": "wordplay and misdirection",
                        },
                        "stance": "seek",
                        "strength": 0.24,
                        "evidenceIds": ["reflection-response:wordplay"],
                    },
                    {
                        "concept": {
                            "conceptId": "crossing-supported-discovery",
                            "label": "crossing-supported discovery",
                        },
                        "stance": "seek",
                        "strength": 1,
                        "evidenceIds": ["explicit:discovery"],
                    },
                ],
                "associations": [],
                "knowledge": [],
            },
        },
    )

    assert context["clue_family_targets"] == [
        {
            "family": "wordplay",
            "direction": "include",
            "strength": 0.24,
            "evidenceCount": 1,
            "source": "reviewed-reflection",
            "reversible": True,
        }
    ]


def test_theme_prompt_carries_reviewed_clue_family_targets(monkeypatch):
    captured = {}

    def fake_chat(_model, messages, _schema, **_kwargs):
        captured["messages"] = messages
        return {"themes": ["ECHO", "MOSS"]}

    monkeypatch.setattr(private_generation, "_chat", fake_chat)
    private_generation._make_themes(
        "qwen3.8:27b",
        {
            "recent_private_answers": [],
            "clue_family_targets": [
                {
                    "family": "wordplay",
                    "direction": "include",
                    "strength": 0.24,
                    "evidenceCount": 1,
                    "source": "reviewed-reflection",
                    "reversible": True,
                }
            ],
        },
        "wednesday",
    )

    assert "clue_family_targets" in captured["messages"][0]["content"]
    assert "wordplay" in captured["messages"][1]["content"]


def test_theme_prompt_allows_invited_proper_names_with_fair_support(monkeypatch):
    captured = {}

    def fake_chat(_model, messages, _schema, **_kwargs):
        captured["system"] = messages[0]["content"]
        return {"themes": ["ECHO", "MOSS"]}

    monkeypatch.setattr(private_generation, "_chat", fake_chat)
    private_generation._make_themes(
        "gemma4:26b",
        {
            "recent_private_answers": [],
            "opening_associations": ["KOFFI", "COFFEE"],
        },
        "wednesday",
    )

    assert "small minority of proper names" in captured["system"]
    assert "fair crossing support" in captured["system"]


def test_clue_token_budget_is_bounded_and_host_overridable(monkeypatch):
    monkeypatch.delenv("CROSSWORD_PRIVATE_CLUE_TOKENS_PER_ENTRY", raising=False)
    assert private_generation._clue_token_budget(74) == 4144

    monkeypatch.setenv("CROSSWORD_PRIVATE_CLUE_TOKENS_PER_ENTRY", "120")
    assert private_generation._clue_token_budget(74) == 5200

    monkeypatch.setenv("CROSSWORD_PRIVATE_CLUE_TOKENS_PER_ENTRY", "not-a-number")
    assert private_generation._clue_token_budget(1) == 1800


def test_private_fill_violations_only_reject_known_construction_artefacts():
    assert private_generation._private_fill_violations(
        {"entries": [{"answer": "FUCCBOIS"}, {"answer": "OREO"}]}
    ) == ["FUCCBOIS"]
    assert (
        private_generation._private_fill_violations(
            {"entries": [{"answer": "FUCKBOY"}, {"answer": "OREO"}]}
        )
        == []
    )


def test_fill_quality_report_keeps_native_scores_separate_from_human_quality():
    report = private_generation._fill_quality_report(
        {
            "entries": [
                {"answer": "CAT", "theme": True},
                {"answer": "ARE", "theme": False},
            ],
            "mean_score": 75.4,
            "min_score": 50,
            "iffy": 13,
            "weak": 38,
        }
    )

    assert report == {
        "version": "private-fill-quality-policy-v1",
        "status": "measured",
        "entryCount": 2,
        "meanScore": 75.4,
        "minimumScore": 50,
        "iffyCount": 13,
        "weakCount": 38,
        "themeCount": 1,
        "source": "native-xfill-reported",
        "uncertainty": "xfill-heuristic-not-human-quality",
    }


def test_fill_quality_policy_selects_a_better_retry_without_rejecting_weak_fallbacks():
    attempts = [
        {
            "attempt": 1,
            "status": "candidate",
            "quality": private_generation._fill_quality_report(
                {
                    "entries": [{"theme": True}],
                    "mean_score": 75.4,
                    "min_score": 50,
                    "iffy": 13,
                    "weak": 38,
                }
            ),
        },
        {
            "attempt": 2,
            "status": "candidate",
            "quality": private_generation._fill_quality_report(
                {
                    "entries": [{"theme": True}, {"theme": True}],
                    "mean_score": 74.1,
                    "min_score": 55,
                    "iffy": 0,
                    "weak": 23,
                }
            ),
        },
    ]
    selected = min(
        enumerate(attempts),
        key=lambda item: private_generation._fill_quality_selection_key(
            item[1]["quality"], item[0]
        ),
    )
    policy = private_generation._fill_quality_policy(attempts, selected[0])

    assert selected[0] == 1
    assert policy["selectedAttempt"] == 2
    assert policy["selectionBasis"].startswith("fewest-iffy")
    assert policy["uncertainty"] == "xfill-heuristic-not-human-quality"


def test_fill_quality_selection_preserves_two_themes_within_weak_band():
    theme_candidate = private_generation._fill_quality_report(
        {
            "entries": [
                {"theme": True},
                {"theme": True},
                {"theme": True},
                {"theme": False},
            ],
            "mean_score": 73,
            "min_score": 50,
            "iffy": 0,
            "weak": 1,
        }
    )
    open_candidate = private_generation._fill_quality_report(
        {
            "entries": [{"theme": False}] * 4,
            "mean_score": 88,
            "min_score": 75,
            "iffy": 0,
            "weak": 0,
        }
    )

    selected = min(
        enumerate(
            [
                {"quality": theme_candidate},
                {"quality": open_candidate},
            ]
        ),
        key=lambda item: private_generation._fill_quality_selection_key(
            item[1]["quality"], item[0], theme_floor=2
        ),
    )

    assert selected[0] == 0


def test_tuesday_theme_floor_preserves_one_theme_within_weak_band():
    theme_candidate = private_generation._fill_quality_report(
        {
            "entries": [{"theme": True}, {"theme": False}] * 10,
            "mean_score": 74,
            "min_score": 50,
            "iffy": 0,
            "weak": 10,
        }
    )
    open_candidate = private_generation._fill_quality_report(
        {
            "entries": [{"theme": False}] * 20,
            "mean_score": 84,
            "min_score": 65,
            "iffy": 0,
            "weak": 0,
        }
    )

    selected = min(
        enumerate(
            [
                {"quality": theme_candidate},
                {"quality": open_candidate},
            ]
        ),
        key=lambda item: private_generation._fill_quality_selection_key(
            item[1]["quality"], item[0], theme_floor=1
        ),
    )

    assert selected[0] == 0


def test_thursday_theme_floor_preserves_three_instances_outside_ordinary_weak_band():
    mechanic_candidate = private_generation._fill_quality_report(
        {
            "entries": [{"theme": True}] * 4 + [{"theme": False}] * 6,
            "mean_score": 72,
            "min_score": 45,
            "iffy": 0,
            "weak": 22,
        }
    )
    open_candidate = private_generation._fill_quality_report(
        {
            "entries": [{"theme": False}] * 10,
            "mean_score": 80,
            "min_score": 55,
            "iffy": 0,
            "weak": 4,
        }
    )

    selected = min(
        enumerate(
            [
                {"quality": mechanic_candidate},
                {"quality": open_candidate},
            ]
        ),
        key=lambda item: private_generation._fill_quality_selection_key(
            item[1]["quality"], item[0], theme_floor=3
        ),
    )

    assert selected[0] == 0


def test_thursday_mechanic_priority_stays_inside_the_iffy_budget():
    themed = private_generation._fill_quality_report(
        {
            "entries": [{"theme": True}] * 4,
            "mean_score": 70,
            "min_score": 45,
            "iffy": private_generation.THURSDAY_MECHANIC_MAX_IFFY,
            "weak": 30,
        }
    )
    open_grid = private_generation._fill_quality_report(
        {
            "entries": [{"theme": False}] * 4,
            "mean_score": 82,
            "min_score": 60,
            "iffy": 0,
            "weak": 2,
        }
    )
    selected = min(
        enumerate([{"quality": themed}, {"quality": open_grid}]),
        key=lambda item: private_generation._fill_quality_selection_key(
            item[1]["quality"], item[0], theme_floor=3
        ),
    )
    assert selected[0] == 0

    too_risky = {**themed, "iffyCount": private_generation.THURSDAY_MECHANIC_MAX_IFFY + 1}
    selected = min(
        enumerate([{"quality": too_risky}, {"quality": open_grid}]),
        key=lambda item: private_generation._fill_quality_selection_key(
            item[1]["quality"], item[0], theme_floor=3
        ),
    )
    assert selected[0] == 1


def test_fill_retry_options_are_bounded_and_reproducible():
    options = {
        "seed": 42,
        "candidates": 75,
        "time": 2,
        "keepMean": 50,
        "minScore": 40,
        "maxIffy": 20,
        "themes": ["ECHO", "MOSS"],
    }

    first = private_generation._fill_retry_options(42, options)
    second = private_generation._fill_retry_options(42, options)

    assert first == second
    assert len(first) == 4
    assert first[0]["label"] == "theme-locked-primary"
    assert first[1]["label"] == "reduced-theme-fallback"
    assert first[-1]["options"]["themes"] == []


def test_crossing_support_summary_reports_structural_access_and_uncertainty():
    summary = private_generation._crossing_support_summary(
        {
            "fill": ["A" * 15] * 15,
            "entries": [
                {"num": 1, "dir": "A", "row": 0, "col": 0, "len": 3},
                {"num": 1, "dir": "D", "row": 0, "col": 1, "len": 3},
                {"num": 2, "dir": "A", "row": 4, "col": 0, "len": 3},
            ],
        },
        [
            {"id": "1A", "needsFoothold": True},
            {"id": "1D", "needsFoothold": False},
            {"id": "2A", "needsFoothold": True},
        ],
    )

    assert summary["status"] == "measured"
    assert summary["weakWithoutCrossing"] == ["2A"]
    assert summary["uncertainty"] == "player-support-unmeasured"
    first = next(item for item in summary["edges"] if item["entryId"] == "1A")
    assert first["crossingCellCount"] == 1
    assert first["supportEntryIds"] == ["1D"]


def test_clue_wordplay_guard_catches_false_reversals_anagrams_and_translations():
    assert (
        private_generation._clue_wordplay_issue(
            {"answer": "ETENIM"}, '"MIND" spelled backward'
        )
        == "reversal-mismatch"
    )
    assert (
        private_generation._clue_wordplay_issue({"answer": "OERME"}, "Anagram of ENORM")
        == "anagram-mismatch"
    )
    assert (
        private_generation._clue_wordplay_issue({"answer": "ISSO"}, "Italian 'yes'")
        == "language-answer-mismatch"
    )
    assert (
        private_generation._clue_wordplay_issue(
            {"answer": "ECHO"}, "Sound that bounces back"
        )
        is None
    )


def test_clue_guard_rejects_answer_roots_inflections_and_generic_templates():
    assert (
        private_generation._clue_wordplay_issue(
            {"answer": "REDS"}, "Shades of red"
        )
        == "answer-form-in-clue"
    )
    assert (
        private_generation._clue_wordplay_issue(
            {"answer": "CAT"}, "Cats, informally"
        )
        == "answer-form-in-clue"
    )
    assert (
        private_generation._clue_wordplay_issue(
            {"answer": "XENON"}, "Common name"
        )
        == "generic-clue"
    )
    assert (
        private_generation._clue_wordplay_issue(
            {"answer": "XENON"}, "Common male name"
        )
        == "generic-clue"
    )
    assert (
        private_generation._clue_wordplay_issue(
            {"answer": "XENON"}, "A usual term?"
        )
        == "generic-clue"
    )
    assert (
        private_generation._clue_wordplay_issue(
            {"answer": "XENON"}, "A common name for a gas?"
        )
        == "generic-clue"
    )
    assert (
        private_generation._clue_wordplay_issue(
            {"answer": "XENON"}, "Usually a common term"
        )
        == "generic-clue"
    )
    assert (
        private_generation._clue_wordplay_issue(
            {"answer": "NASH"}, "Famous writer's name"
        )
        == "generic-clue"
    )
    assert (
        private_generation._clue_wordplay_issue(
            {"answer": "TONI"}, "Italian singer's name, perhaps"
        )
        == "generic-clue"
    )
    assert (
        private_generation._clue_wordplay_issue(
            {"answer": "TONI"}, "Artist's name"
        )
        == "generic-clue"
    )
    assert (
        private_generation._clue_wordplay_issue(
            {"answer": "NASH"}, "Name of a classic novelist"
        )
        == "generic-clue"
    )


def test_malformed_clue_model_response_falls_back_to_answer_free_scaffolds(monkeypatch):
    def malformed_chat(*_args, **_kwargs):
        raise ValueError("invalid clue text")

    monkeypatch.setattr(private_generation, "_chat", malformed_chat)
    context = {}
    title, clues = private_generation._make_clues(
        "gemma4:26b",
        [
            {"id": "1A", "answer": "ECHO", "length": 4},
            {"id": "2D", "answer": "MOSS", "length": 4},
        ],
        context,
        "tuesday",
    )

    assert title == "Tuesday Clues"
    assert clues == {
        "1A": "Entry supported by its crossings (4 letters)",
        "2D": "Entry supported by its crossings (4 letters)",
    }
    assert context["_clue_generation_fallback"] == "ValueError: invalid clue text"
    assert context["_clue_safety_fallbacks"] == {
        "1A": ["model-response-invalid"],
        "2D": ["model-response-invalid"],
    }


def test_tuesday_recipe_has_a_real_step_up_from_monday():
    monday = private_generation._weekday_recipe("monday")
    tuesday = private_generation._weekday_recipe("tuesday")

    assert tuesday["id"] == "tuesday-private-v1"
    assert tuesday["themeAnswerCount"] > monday["themeAnswerCount"]
    assert "second reading" in tuesday["clueDirection"]
    assert tuesday["themeAnswerCount"] == 5
    assert tuesday["minimumNonDefinitionFamilies"] == 5
    assert tuesday["minimumNonDefinitionCount"] == 10
    assert private_generation._DIFFICULTY["tuesday"]["candidates"] > private_generation._DIFFICULTY["monday"]["candidates"]
    assert private_generation._DIFFICULTY["tuesday"]["time"] > private_generation._DIFFICULTY["monday"]["time"]


def test_clue_quality_summary_keeps_semantic_review_separate_from_mechanical_checks():
    summary = private_generation._clue_quality_summary(
        [
            {"id": "1A", "answer": "ETENIM"},
            {"id": "2D", "answer": "ECHO"},
        ],
        {"1A": '"MIND" spelled backward', "2D": "Sound that bounces back"},
    )

    assert summary["checkedCount"] == 2
    assert summary["issueCount"] == 1
    assert summary["issueCounts"] == {"reversal-mismatch": 1}
    assert summary["grounding"]["statusCounts"] == {
        "mechanical-relation-failed": 1,
        "semantic-unverified": 1,
    }
    assert summary["grounding"]["relationCounts"] == {"reversal": 1}


def test_optional_model_clue_challenge_is_disabled_by_default(monkeypatch):
    def unexpected_chat(*args, **kwargs):
        raise AssertionError("disabled advisory pass must not call Ollama")

    monkeypatch.delenv(private_generation.PRIVATE_CLUE_CHALLENGE_ENV, raising=False)
    monkeypatch.setattr(private_generation, "_chat", unexpected_chat)

    result = private_generation._challenge_private_clues(
        "gemma4:26b",
        [{"id": "1A", "answer": "ECHO"}],
        {"1A": "Sound that bounces back"},
        {},
        "wednesday",
    )

    assert result["status"] == "disabled"
    assert result["checkedCount"] == 0
    assert result["byId"] == {}


def test_optional_model_clue_challenge_is_advisory_and_fail_open(monkeypatch):
    monkeypatch.setenv(private_generation.PRIVATE_CLUE_CHALLENGE_ENV, "1")

    def fake_chat(*args, **kwargs):
        return {
            "checks": [
                {
                    "id": "1A",
                    "disposition": "review",
                    "confidence": "medium",
                    "reason": "Definition has no source ledger.",
                }
            ]
        }

    monkeypatch.setattr(private_generation, "_chat", fake_chat)
    entries = [{"id": "1A", "answer": "ECHO"}]
    result = private_generation._challenge_private_clues(
        "gemma4:26b",
        entries,
        {"1A": "Sound that bounces back"},
        {"opening_associations": ["sound"]},
        "wednesday",
    )

    assert result["status"] == "completed"
    assert result["checkedCount"] == 1
    assert result["byId"]["1A"]["disposition"] == "review"
    summary = private_generation._clue_quality_summary(
        entries,
        {"1A": "Sound that bounces back"},
        model_challenges=result["byId"],
    )
    challenge = summary["grounding"]["entries"][0]["semanticChallenge"]
    assert challenge["classification"] == "needs-review"
    assert challenge["modelRecommendation"]["status"] == "accepted-advisory"
    assert challenge["playPolicy"] == "never-gates-private-play"

    def failing_chat(*args, **kwargs):
        raise RuntimeError("Ollama unavailable")

    monkeypatch.setattr(private_generation, "_chat", failing_chat)
    failed = private_generation._challenge_private_clues(
        "gemma4:26b", entries, {"1A": "Sound that bounces back"}, {}, "wednesday"
    )
    assert failed["status"] == "failed"
    assert failed["enabled"] is True
    assert failed["byId"] == {}


def test_large_model_clue_challenge_scopes_to_deterministic_risk(monkeypatch):
    monkeypatch.setenv(private_generation.PRIVATE_CLUE_CHALLENGE_ENV, "1")
    seen = []

    def fake_chat(_model, messages, _schema, **_kwargs):
        payload = json.loads(messages[1]["content"])
        seen.append([item["id"] for item in payload["entries"]])
        return {
            "checks": [
                {
                    "id": "1A",
                    "disposition": "review",
                    "confidence": "medium",
                    "reason": "Relation needs a source check.",
                }
            ]
        }

    monkeypatch.setattr(private_generation, "_chat", fake_chat)
    entries = [
        {
            "id": f"{index}A",
            "answer": "ECHO",
            "needsFoothold": index == 1,
        }
        for index in range(1, 21)
    ]
    result = private_generation._challenge_private_clues(
        "gemma4:26b",
        entries,
        {entry["id"]: "Singer with a hit" if entry["id"] == "1A" else "Sound" for entry in entries},
        {},
        "wednesday",
    )

    assert result["status"] == "completed"
    assert result["scope"] == "deterministic-risk-selection"
    assert result["checkedCount"] == 1
    assert seen == [["1A"]]


def test_clue_grounding_reports_structure_without_claiming_semantic_facts():
    grounding = private_generation._clue_grounding(
        {"answer": "MOMENT"}, "Entry supported by its crossings (6 letters)"
    )

    assert grounding["status"] == "crossing-scaffold"
    assert grounding["answerLength"] == 6
    assert grounding["answerShape"] == "letters-only"
    assert grounding["repeatedLetterCount"] == 1
    assert grounding["relation"] is None
    assert grounding["riskFlags"] == []
    assert grounding["uncertainty"] == [
        "semantic-meaning-unverified",
        "factual-support-unverified",
    ]


def test_clue_grounding_labels_mechanical_and_surface_conventions_separately():
    anagram = private_generation._clue_grounding({"answer": "ECHO"}, "Anagram of HOCE")
    plural = private_generation._clue_grounding({"answer": "CATS"}, "Felines (pl.)")

    assert anagram["status"] == "mechanically-consistent"
    assert anagram["relation"] == "anagram"
    assert anagram["relationVerification"] == "consistent"
    assert plural["status"] == "surface-convention-only"
    assert plural["relation"] == "plural-label"
    assert plural["morphology"] == "plural-marker-present; answer morphology unverified"
    assert plural["relationVerification"] == "surface-only"


def test_private_clue_safety_catches_explicit_plural_marker_mismatch():
    mismatch = private_generation._clue_grounding(
        {"answer": "CAT", "needsFoothold": False}, "Felines (pl.)"
    )

    assert mismatch["status"] == "morphology-check-failed"
    assert mismatch["morphologyIssue"] == "plural-marker-with-singular-shape"
    assert private_generation._enforce_private_clue_safety(
        [{"id": "1A", "answer": "CAT", "length": 3, "needsFoothold": False}],
        {"1A": "Felines (pl.)"},
    )["1A"] == "Entry supported by its crossings (3 letters)"


def test_private_clue_safety_catches_explicit_past_tense_marker_mismatch():
    assert (
        private_generation._clue_morphology_issue(
            {"answer": "RAN"}, "Past tense"
        )
        is None
    )
    mismatch = private_generation._clue_grounding(
        {"answer": "RUN", "needsFoothold": False}, "Past tense"
    )

    assert mismatch["status"] == "morphology-check-failed"
    assert mismatch["morphologyIssue"] == "past-tense-marker-with-nonpast-shape"
    assert private_generation._enforce_private_clue_safety(
        [{"id": "1A", "answer": "RUN", "length": 3, "needsFoothold": False}],
        {"1A": "Past tense"},
    )["1A"] == "Entry supported by its crossings (3 letters)"


def test_clue_grounding_exposes_risk_flags_for_local_inspection():
    grounding = private_generation._clue_grounding(
        {"id": "1A", "answer": "EVAN", "needsFoothold": False},
        "Singer with a hit song?",
    )

    assert grounding["riskFlags"] == ["unsupported-factual-surface"]


def test_reviewed_clue_pack_projection_matches_exact_answers_and_keeps_receipt():
    configured = SimpleNamespace(
        pack_id="pack-v1",
        pack_sha256="a" * 64,
        content=SimpleNamespace(
            lexemes=(
                SimpleNamespace(
                    lexeme_id="lexeme-cat",
                    answer="CAT",
                    senses=(
                        SimpleNamespace(
                            sense_id="sense-cat-gloss",
                            gloss="a small domesticated feline",
                            resolution_status="reviewed",
                        ),
                    ),
                    facts=(
                        SimpleNamespace(
                            fact_id="fact-cat",
                            statement="Cats are mammals",
                        ),
                    ),
                    clues=(
                        SimpleNamespace(
                            clue_id="clue-cat",
                            text="Feline, familiarly",
                            evidence_type="sense",
                            evidence_id="sense-cat",
                            grammar={"grammarVersion": "clue-grammar-v1"},
                            provenance={
                                "source": {
                                    "sourceId": "source-v1",
                                    "version": "2026",
                                    "artifactSha256": "b" * 64,
                                },
                                "evidenceRefs": ["fixture:sense/CAT"],
                                "reviewerId": "reviewer",
                                "reviewedAt": "2026-09-28",
                            },
                        ),
                    ),
                ),
            ),
        ),
    )

    projection = private_generation._reviewed_clue_pack_projection(
        [{"id": "1A", "answer": "CAT"}, {"id": "2D", "answer": "DOG"}],
        configured,
    )

    assert projection["status"] == "configured"
    assert projection["byId"]["1A"]["text"] == "Feline, familiarly"
    assert projection["byId"]["1A"]["evidenceId"] == "sense-cat"
    assert projection["byId"]["1A"]["sourceId"] == "source-v1"
    assert projection["byId"]["1A"]["senses"] == [
        {
            "senseId": "sense-cat-gloss",
            "gloss": "a small domesticated feline",
            "resolutionStatus": "reviewed",
        }
    ]
    assert projection["byId"]["1A"]["facts"] == [
        {"factId": "fact-cat", "statement": "Cats are mammals"}
    ]
    assert "2D" not in projection["byId"]
    assert private_generation._reviewed_clue_pack_summary(projection) == {
        "version": "private-reviewed-clue-pack-v1",
        "status": "configured",
        "matchedCount": 1,
        "contextCount": 1,
        "uncertainty": "reviewed-source-provenance-is-not-a-publication-claim",
        "packId": "pack-v1",
        "packSha256": "a" * 64,
    }


def test_reviewed_clue_pack_treats_empty_app_defaults_as_not_configured(
    api, monkeypatch
):
    keys = (
        "FUTURE_ADMITTED_PACK_PATH",
        "FUTURE_ADMITTED_PACK_ID",
        "FUTURE_ADMITTED_PACK_SHA256",
        "FUTURE_ADMITTED_SOURCE_PINS_JSON",
    )
    with api.app.app_context():
        for key in keys:
            monkeypatch.setitem(api.app.config, key, None)
        projection = private_generation._load_reviewed_clue_pack([])

    assert projection == {
        "version": "private-reviewed-clue-pack-v1",
        "status": "not-configured",
        "byId": {},
    }


def test_make_clues_preserves_exact_reviewed_text(monkeypatch):
    monkeypatch.setattr(
        private_generation,
        "_chat",
        lambda *args, **kwargs: {
            "title": "A small board",
            "clues": [{"id": "1A", "text": "Model paraphrase"}],
        },
    )
    monkeypatch.setattr(
        private_generation,
        "_repair_risky_clues",
        lambda model, entries, clues, context, weekday: clues,
    )
    title, clues = private_generation._make_clues(
        "gemma4:26b",
        [{"id": "1A", "answer": "CAT", "length": 3, "theme": False}],
        {},
        "wednesday",
        reviewed_pack={
            "byId": {
                "1A": {
                    "text": "Feline, familiarly",
                    "evidenceType": "sense",
                    "evidenceId": "sense-cat",
                }
            }
        },
    )

    assert title == "A small board"
    assert clues == {"1A": "Feline, familiarly"}


def test_make_clues_repairs_language_starter_to_explicit_signal(monkeypatch):
    monkeypatch.setattr(
        private_generation,
        "_chat",
        lambda *args, **kwargs: {
            "title": "A language thread",
            "clues": [{"id": "1A", "text": "German refusal"}],
        },
    )
    monkeypatch.setattr(
        private_generation,
        "_repair_risky_clues",
        lambda model, entries, clues, context, weekday: clues,
    )

    _, clues = private_generation._make_clues(
        "gemma4:26b",
        [{"id": "1A", "answer": "NEIN", "length": 4, "theme": False}],
        {
            "language_learning": {
                "language": "German",
                "eligibleReviewForms": ["NEIN"],
            }
        },
        "wednesday",
    )

    assert clues == {"1A": "German for refusal"}


def test_make_clues_uses_the_local_task_pair_source_text(monkeypatch):
    monkeypatch.setattr(
        private_generation,
        "_chat",
        lambda *args, **kwargs: {
            "title": "A language thread",
            "clues": [{"id": "1A", "text": "French refusal"}],
        },
    )
    monkeypatch.setattr(
        private_generation,
        "_repair_risky_clues",
        lambda model, entries, clues, context, weekday: clues,
    )

    _, clues = private_generation._make_clues(
        "gemma4:26b",
        [{"id": "1A", "answer": "OUI", "length": 3, "theme": False}],
        {
            "language_learning": {
                "language": "French",
                "eligibleReviewForms": ["OUI"],
            }
        },
        "wednesday",
    )

    assert clues == {"1A": "French for yes"}


def test_make_clues_passes_bounded_reviewed_context(monkeypatch):
    captured = {}

    def fake_chat(*args, **kwargs):
        captured["messages"] = args[1]
        return {
            "title": "A contextual board",
            "clues": [{"id": "1A", "text": "Small domesticated animal"}],
        }

    monkeypatch.setattr(private_generation, "_chat", fake_chat)
    monkeypatch.setattr(
        private_generation,
        "_repair_risky_clues",
        lambda model, entries, clues, context, weekday: clues,
    )
    private_generation._make_clues(
        "gemma4:26b",
        [{"id": "1A", "answer": "CAT", "length": 3, "theme": False}],
        {},
        "wednesday",
        reviewed_pack={
            "byId": {
                "1A": {
                    "text": None,
                    "senses": [
                        {
                            "senseId": "sense-cat",
                            "gloss": "a small domesticated feline",
                            "resolutionStatus": "reviewed",
                        }
                    ],
                    "facts": [
                        {"factId": "fact-cat", "statement": "Cats are mammals"}
                    ],
                }
            }
        },
    )

    payload = json.loads(captured["messages"][1]["content"])
    assert payload["reviewedClues"] == []
    assert payload["reviewedContent"] == [
        {
            "id": "1A",
            "senses": [
                {
                    "senseId": "sense-cat",
                    "gloss": "a small domesticated feline",
                    "resolutionStatus": "reviewed",
                }
            ],
            "facts": [{"factId": "fact-cat", "statement": "Cats are mammals"}],
        }
    ]


def test_make_clues_receives_the_answer_free_foothold_seed_plan(monkeypatch):
    captured = {}

    def fake_chat(*args, **kwargs):
        captured["messages"] = args[1]
        return {
            "title": "Seeded crossings",
            "clues": [{"id": "1A", "text": "A small animal"}],
        }

    monkeypatch.setattr(private_generation, "_chat", fake_chat)
    monkeypatch.setattr(
        private_generation,
        "_repair_risky_clues",
        lambda model, entries, clues, context, weekday: clues,
    )
    plan = {
        "version": "private-foothold-seed-plan-v1",
        "targetCount": 1,
        "seededTargetCount": 1,
        "entries": [
            {
                "targetEntryId": "1A",
                "supportEntryId": "1D",
                "crossingCells": [{"row": 0, "col": 0}],
            }
        ],
    }
    private_generation._make_clues(
        "gemma4:26b",
        [{"id": "1A", "answer": "CAT", "length": 3, "theme": False}],
        {"_foothold_seed_plan": plan},
        "wednesday",
    )

    payload = json.loads(captured["messages"][1]["content"])
    assert payload["footholdSeedPlan"] == plan
    assert "_foothold_seed_plan" not in payload["wordField"]


def test_large_definition_heavy_board_gets_bounded_surface_diversity_repair(monkeypatch):
    entries = [
        {"id": f"{index}A", "answer": "CAT", "length": 3, "theme": False}
        for index in range(1, 31)
    ]
    calls = []

    def fake_chat(_model, messages, schema, **_kwargs):
        calls.append(messages)
        ids = schema["properties"]["clues"]["items"]["properties"]["id"]["enum"]
        if len(calls) == 1:
            return {
                "title": "A definition-heavy board",
                "clues": [{"id": entry["id"], "text": "A thing"} for entry in entries],
            }
        surfaces = {
            ids[0]: "Branch, perhaps?",
            ids[1]: "Safe and ___",
            ids[2]: "[Sound heard nearby]",
            ids[3]: "“Not a chance!”",
        }
        return {
            "title": "A varied board",
            "clues": [{"id": clue_id, "text": surfaces[clue_id]} for clue_id in ids],
        }

    monkeypatch.setattr(private_generation, "_chat", fake_chat)
    monkeypatch.setattr(
        private_generation,
        "_repair_risky_clues",
        lambda model, entries, clues, context, weekday: clues,
    )
    context = {}

    _, clues = private_generation._make_clues(
        "gemma4:26b", entries, context, "wednesday"
    )

    assert len(calls) == 2
    assert context["_clue_diversity_repair"] == {
        "version": "private-clue-diversity-repair-v1",
        "status": "repaired",
        "attempted": True,
        "selectedCount": 4,
        "rewrittenCount": 4,
        "minimumFamilies": 2,
        "achievedFamilies": 4,
        "reason": "definition-heavy-board",
    }
    report = private_generation._clue_diversity_report(entries, clues)
    assert report["status"] == "varied"
    assert report["familyCounts"] == {
        "definition": 26,
        "fill-blank": 1,
        "nonverbal-expression": 1,
        "pun": 1,
        "spoken-equivalent": 1,
    }


def test_tuesday_recipe_raises_the_surface_family_floor(monkeypatch):
    entries = [
        {"id": f"{index}A", "answer": "BARK", "length": 4, "theme": False}
        for index in range(1, 31)
    ]
    calls = []

    def fake_chat(_model, messages, schema, **_kwargs):
        calls.append(messages)
        ids = schema["properties"]["clues"]["items"]["properties"]["id"]["enum"]
        if len(calls) == 1:
            return {
                "title": "A Tuesday board",
                "clues": [{"id": entry["id"], "text": "A thing"} for entry in entries],
            }
        surfaces = {
            ids[0]: "Branch, perhaps?",
            ids[1]: "Safe and ___",
            ids[2]: "[Sound heard nearby]",
            ids[3]: "“Not a chance!”",
            ids[4]: "Briefly, perhaps",
            ids[5]: "Aha?",
        }
        return {
            "title": "A Tuesday board",
            "clues": [
                {"id": clue_id, "text": text}
                for clue_id, text in surfaces.items()
            ],
        }

    monkeypatch.setattr(private_generation, "_chat", fake_chat)
    monkeypatch.setattr(
        private_generation,
        "_repair_risky_clues",
        lambda model, entries, clues, context, weekday: clues,
    )
    context = {}

    _, clues = private_generation._make_clues(
        "gemma4:26b", entries, context, "tuesday"
    )

    assert len(calls) == 3
    assert context["_clue_diversity_repair"]["reason"] == "weekday-surface-floor"
    assert context["_clue_diversity_repair"]["selectedCount"] == 6
    report = private_generation._clue_diversity_report(
        entries, clues, repair=context["_clue_diversity_repair"]
    )
    assert len(report["nonDefinitionFamilies"]) >= 5
    assert report["status"] == "varied"
    assert report["nonDefinitionCount"] == 12
    assert report["floorMet"] is True


def test_tuesday_surface_floor_uses_one_extra_bounded_repair_batch(monkeypatch):
    entries = [
        {"id": f"{index}A", "answer": "BARK", "length": 4, "theme": False}
        for index in range(1, 31)
    ]
    calls = []
    surfaces = [
        "Branch, perhaps?",
        "Safe and ___",
        "[Sound heard nearby]",
        "“Not a chance!”",
        "Briefly, perhaps",
    ]

    def fake_chat(_model, messages, schema, **_kwargs):
        calls.append(messages)
        ids = schema["properties"]["clues"]["items"]["properties"]["id"]["enum"]
        if len(calls) == 1:
            return {
                "title": "A Tuesday board",
                "clues": [{"id": entry["id"], "text": "A thing"} for entry in entries],
            }
        batch_size = {2: 3, 3: 3, 4: 5}[len(calls)]
        return {
            "title": "A Tuesday board",
            "clues": [
                {"id": clue_id, "text": surfaces[index % len(surfaces)]}
                for index, clue_id in enumerate(ids[:batch_size])
            ],
        }

    monkeypatch.setattr(private_generation, "_chat", fake_chat)
    monkeypatch.setattr(
        private_generation,
        "_repair_risky_clues",
        lambda model, entries, clues, context, weekday: clues,
    )
    context = {}

    _, clues = private_generation._make_clues(
        "gemma4:26b", entries, context, "tuesday"
    )

    assert len(calls) == 4
    assert context["_clue_diversity_repair"]["attemptCount"] == 3
    assert len(context["_clue_diversity_repair"]["attempts"]) == 3
    report = private_generation._clue_diversity_report(
        entries, clues, repair=context["_clue_diversity_repair"]
    )
    assert report["nonDefinitionCount"] == 11
    assert report["floorMet"] is True


def test_clue_surface_checks_and_normalization_preserve_the_answer_free_surface():
    assert private_generation._clue_surface_issues("[Sound? that bounces back") == [
        "unbalanced-brackets",
        "question-mark-placement",
    ]
    assert private_generation._clue_surface_issues("A [sound] that bounces back") == [
        "bracket-scope",
    ]
    assert (
        private_generation._normalize_clue_surface("[Sound? that bounces back")
        == "Sound that bounces back"
    )
    grounding = private_generation._clue_grounding(
        {"answer": "ECHO"}, "A [sound] that bounces back"
    )
    assert grounding["status"] == "surface-convention-invalid"
    assert grounding["surfaceIssues"] == ["bracket-scope"]


def test_clue_risk_flags_only_specific_factual_surfaces_and_tracks_footholds():
    weak_entry = {"id": "1A", "answer": "EVAN", "needsFoothold": True}
    assert private_generation._clue_risk_flags(
        weak_entry, "Singer with a hit song?"
    ) == ["unsupported-factual-surface", "foothold-required"]
    assert private_generation._clue_risk_flags(
        weak_entry, "Sound that bounces back"
    ) == ["foothold-required"]


@pytest.mark.parametrize(
    "clue",
    ["Representative Alexandria", "Italian city", "French film director"],
)
def test_clue_risk_flags_source_free_identity_surfaces(clue):
    assert private_generation._clue_risk_flags(
        {"id": "1A", "answer": "XXXX"}, clue
    ) == ["unsupported-factual-surface"]


def test_private_clue_safety_replaces_unresolved_trivia_for_ordinary_entries():
    entries = [
        {"id": "1A", "answer": "EVAN", "length": 4, "needsFoothold": True},
        {"id": "2D", "answer": "RESONANCE", "length": 9, "needsFoothold": False},
    ]
    clues = {
        "1A": "Singer with a hit song?",
        "2D": "Singer with a hit song?",
    }

    fallback_reasons = {}
    safe = private_generation._enforce_private_clue_safety(
        entries, clues, fallback_reasons=fallback_reasons
    )

    assert safe["1A"] == "Entry supported by its crossings (4 letters)"
    assert safe["2D"] == "Entry supported by its crossings (9 letters)"
    assert "EVAN" not in safe["1A"]
    assert fallback_reasons == {
        "1A": ["unsupported-factual-surface"],
        "2D": ["unsupported-factual-surface"],
    }


def test_private_clue_safety_replaces_source_free_identity_surfaces():
    entries = [{"id": "1A", "answer": "AOC", "length": 3, "needsFoothold": False}]
    safe = private_generation._enforce_private_clue_safety(
        entries, {"1A": "Representative Alexandria"}
    )

    assert safe["1A"] == "Entry supported by its crossings (3 letters)"


def test_private_clue_safety_preserves_an_exact_reviewed_factual_surface():
    entries = [
        {"id": "1A", "answer": "ASHE", "length": 4, "needsFoothold": False}
    ]
    clues = {"1A": "Singer of 'Smooth'"}

    safe = private_generation._enforce_private_clue_safety(
        entries,
        clues,
        reviewed_by_id={"1A": {"text": "Singer of 'Smooth'"}},
    )

    assert safe == clues


def test_grounded_bundle_preserves_the_original_reason_for_a_safety_scaffold():
    entries = [{"id": "1A", "answer": "ASHE", "length": 4}]
    clues = {"1A": "Entry supported by its crossings (4 letters)"}
    safety_fallbacks = {"1A": ["unsupported-factual-surface"]}

    bundle = private_generation._grounded_clue_bundle(
        entries,
        clues,
        safety_fallbacks=safety_fallbacks,
    )

    assert bundle["safetyFallbacks"] == safety_fallbacks
    assert bundle["fallbacks"] == [
        {
            "id": "1A",
            "kind": "crossing-scaffold",
            "reasonCodes": ["unsupported-factual-surface"],
            "answerDisclosure": "none",
            "semanticStatus": "not-established",
        }
    ]


def test_private_clue_safety_keeps_a_repaired_themed_name_surface():
    entries = [
        {
            "id": "1A",
            "answer": "EVAN",
            "length": 4,
            "needsFoothold": True,
            "theme": True,
        }
    ]
    clues = {"1A": "Singer with a hit song?"}

    safe = private_generation._enforce_private_clue_safety(entries, clues)

    assert safe["1A"] == clues["1A"]


def test_private_clue_safety_replaces_giveaways_and_false_wordplay_for_any_entry():
    entries = [
        {"id": "1A", "answer": "ECHO", "length": 4, "needsFoothold": False},
        {"id": "2D", "answer": "ECHO", "length": 4, "needsFoothold": False},
    ]
    clues = {
        "1A": "ECHO, repeated sound",
        "2D": "Anagram of MIND",
    }

    safe = private_generation._enforce_private_clue_safety(entries, clues)

    assert safe == {
        "1A": "Entry supported by its crossings (4 letters)",
        "2D": "Entry supported by its crossings (4 letters)",
    }


def test_private_clue_safety_replaces_answer_root_and_generic_clues():
    entries = [
        {"id": "1A", "answer": "REDS", "length": 4, "needsFoothold": False},
        {"id": "2D", "answer": "XENON", "length": 5, "needsFoothold": False},
    ]
    clues = {"1A": "Shades of red", "2D": "Common name"}

    safe = private_generation._enforce_private_clue_safety(entries, clues)

    assert safe == {
        "1A": "Entry supported by its crossings (4 letters)",
        "2D": "Entry supported by its crossings (5 letters)",
    }


def test_clue_quality_summary_reports_source_less_factual_surface():
    summary = private_generation._clue_quality_summary(
        [{"id": "1A", "answer": "EVAN", "needsFoothold": True}],
        {"1A": "Singer with a hit song?"},
    )

    assert summary["issueCounts"] == {"unsupported-factual-surface": 1}
    assert summary["issueCount"] == 1


def test_grounded_clue_bundle_marks_proper_name_risk_and_source_free_fallback():
    entries = [
        {
            "id": "1A",
            "answer": "EVAN",
            "length": 4,
            "fillScore": 42,
            "needsFoothold": True,
            "cluePolicy": "source-free-foothold",
        },
        {
            "id": "2D",
            "answer": "ECHO",
            "length": 4,
            "fillScore": 88,
            "needsFoothold": False,
        },
    ]
    bundle = private_generation._grounded_clue_bundle(
        entries,
        {
            "1A": "Entry supported by its crossings (4 letters)",
            "2D": "Sound that bounces back",
        },
    )

    weak = next(item for item in bundle["entries"] if item["id"] == "1A")
    assert bundle["version"] == "private-grounded-clue-bundle-v1"
    assert bundle["semanticStatus"] == "not-established"
    assert weak["supportBand"] == "weak"
    assert weak["factRisk"]["truth"] == "not-established"
    assert weak["fallback"] == {
        "used": True,
        "kind": "crossing-scaffold",
        "reasonCodes": ["weak-or-obscure-fill"],
        "answerDisclosure": "none",
        "semanticStatus": "not-established",
        "textPolicy": "source-free-and-answer-free",
    }
    assert bundle["fallbacks"] == [
        {
            "id": "1A",
            "kind": "crossing-scaffold",
            "reasonCodes": ["weak-or-obscure-fill"],
            "answerDisclosure": "none",
            "semanticStatus": "not-established",
        }
    ]


def test_grounded_clue_bundle_separates_fact_risk_from_visible_family_signals():
    bundle = private_generation._grounded_clue_bundle(
        [
            {
                "id": "1A",
                "answer": "EVAN",
                "length": 4,
                "fillScore": 78,
                "needsFoothold": False,
            },
            {
                "id": "2D",
                "answer": "CATS",
                "length": 4,
                "fillScore": 78,
                "needsFoothold": False,
            },
        ],
        {
            "1A": "Singer with a hit song?",
            "2D": "Felines (pl.)",
        },
    )

    factual = next(item for item in bundle["entries"] if item["id"] == "1A")
    plural = next(item for item in bundle["entries"] if item["id"] == "2D")
    assert factual["factRisk"]["category"] == "proper-name-or-biography"
    assert factual["semanticStatus"] == "not-established"
    assert plural["familyObservation"]["family"] == "definition"
    assert plural["relation"] == "plural-label"
    assert plural["relationVerification"] == "surface-only"
    assert bundle["factRiskCounts"] == {
        "proper-name-or-biography": 1,
        "none-observed": 1,
    }


def test_grounded_clue_bundle_counts_literal_surface_signals():
    bundle = private_generation._grounded_clue_bundle(
        [
            {"id": "1A", "answer": "NO WAY", "length": 5},
            {"id": "2D", "answer": "PHEW", "length": 4},
            {"id": "3A", "answer": "SOUND", "length": 5},
            {"id": "4D", "answer": "EST", "length": 3},
            {"id": "5A", "answer": "BRANCH", "length": 6},
            {"id": "6D", "answer": "CATS", "length": 4},
            {"id": "7D", "answer": "RAN", "length": 3},
        ],
        {
            "1A": "“Not a chance!”",
            "2D": "[Sigh of relief]",
            "3A": "Safe and ___",
            "4D": "Estimated arrival, briefly",
            "5A": "Branch specialist?",
            "6D": "Felines (pl.)",
            "7D": "Past tense of run",
        },
    )

    assert bundle["signalCounts"] == {
        "abbreviation-indicator": 1,
        "brackets": 1,
        "fill-blank": 1,
        "plural-marker": 1,
        "question-mark": 1,
        "quote": 1,
        "tense-marker": 1,
    }


def test_grounded_clue_bundle_marks_exact_reviewed_sense_join_without_promoting_model_text():
    entries = [
        {"id": "1A", "answer": "CAT", "length": 3, "fillScore": 88},
        {"id": "2D", "answer": "DOG", "length": 3, "fillScore": 88},
    ]
    clues = {"1A": "Mammal", "2D": "Animal friend"}
    reviewed_pack = {
        "packId": "pack-synthetic",
        "packSha256": "a" * 64,
        "byId": {
            "1A": {
                "text": "Mammal",
                "lexemeId": "lexeme-cat",
                "clueId": "clue-cat-mammal",
                "evidenceType": "sense",
                "evidenceId": "sense-cat",
                "senses": [{"senseId": "sense-cat", "gloss": "A small mammal"}],
                "facts": [],
                "packId": "pack-synthetic",
                "packSha256": "a" * 64,
            }
        },
    }

    bundle = private_generation._grounded_clue_bundle(
        entries,
        clues,
        reviewed_pack=reviewed_pack,
    )
    reviewed = next(item for item in bundle["entries"] if item["id"] == "1A")
    ordinary = next(item for item in bundle["entries"] if item["id"] == "2D")

    assert bundle["sourcePolicy"] == "private-model-with-reviewed-source"
    assert bundle["reviewedCount"] == 1
    assert bundle["semanticStatus"] == "reviewed-source-present"
    assert reviewed["semanticStatus"] == "reviewed-source"
    assert reviewed["reviewedSource"]["senseIds"] == ["sense-cat"]
    assert reviewed["reviewedSource"]["packId"] == "pack-synthetic"
    assert ordinary["semanticStatus"] == "not-established"


def test_clue_generation_bundle_exposes_shape_and_forbids_fact_inference():
    bundle = private_generation._clue_generation_bundle(
        [
            {
                "id": "1A",
                "answer": "MOMENT",
                "fillScore": 55,
                "needsFoothold": True,
                "cluePolicy": "source-free-foothold",
                "theme": False,
            }
        ]
    )

    record = bundle["entries"][0]
    assert record["answerLength"] == 6
    assert record["answerShape"] == "letters-only"
    assert record["supportBand"] == "weak"
    assert record["factRisk"]["status"] == "unassessed-before-clue-surface"
    assert "proper-name-from-short-answer" in record["forbiddenInference"]
    assert bundle["uncertainty"] == [
        "semantic-sense-unverified",
        "factual-support-unverified",
        "player-support-unmeasured",
    ]


def test_generation_retries_after_a_private_fill_artefact(monkeypatch):
    monkeypatch.setattr(private_generation, "_installed_model", lambda: "qwen3.8:27b")
    monkeypatch.setattr(
        private_generation, "_make_themes", lambda *_args: ["ECHO", "MOSS"]
    )
    calls = []

    def fake_fill(*, seed, options):
        calls.append(options["themes"])
        answer = "FUCCBOIS" if len(calls) == 1 else "ECHO"
        return {
            "grid": {
                "entries": [
                    {
                        "num": 1,
                        "dir": "A",
                        "answer": answer,
                        "len": len(answer),
                        "row": 0,
                        "col": 0,
                        "theme": True,
                    }
                ]
            }
        }

    monkeypatch.setattr(private_generation, "generate_full_size_draft", fake_fill)
    monkeypatch.setattr(
        private_generation,
        "_make_clues",
        lambda *_args: ("Echoes in the Morning", {"1A": "Sound that bounces back"}),
    )
    monkeypatch.setattr(
        private_generation,
        "_legacy_puzzle",
        lambda *_args: ("solver-ready puzzle", {"registered": True}),
    )

    starting = SimpleNamespace(profile={"associations": []}, draft={})
    episteme = SimpleNamespace(profile_json={"projection": {}})
    _generate = private_generation._generate
    _crossword, _manifest, _provenance = _generate(42, "monday", starting, episteme)

    assert calls == [["ECHO", "MOSS"], ["ECHO"]]


@pytest.mark.parametrize(
    ("weekday", "theme_count", "recipe_id", "theme_mode"),
    [
        ("monday", 3, "monday-private-v1", "approachable-cluster"),
        ("wednesday", 4, "wednesday-private-v1", "inferable-cluster"),
        ("thursday", 5, "thursday-private-v1", "standard-theme"),
    ],
)
def test_selected_weekday_recipe_changes_theme_locks_and_provenance(
    monkeypatch, weekday, theme_count, recipe_id, theme_mode
):
    themes = ["ECHO", "MOSS", "TUNING", "STITCH", "LORE", "THREAD"]
    fill_options = []
    monkeypatch.setattr(private_generation, "_installed_model", lambda: "local-model")
    monkeypatch.setattr(private_generation, "_make_themes", lambda *_args: themes)
    if weekday == "thursday":
        monkeypatch.setattr(
            private_generation,
            "_make_thursday_theme_proposal",
            lambda *_args: (_ for _ in ()).throw(ValueError("invalid proposal")),
        )

    def fake_fill(*, seed, options):
        fill_options.append(options)
        return {
            "grid": {
                "entries": [
                    {
                        "num": 1,
                        "dir": "A",
                        "answer": "ECHO",
                        "len": 4,
                        "row": 0,
                        "col": 0,
                        "theme": True,
                        "score": 80,
                    }
                ]
            }
        }

    monkeypatch.setattr(private_generation, "generate_full_size_draft", fake_fill)
    monkeypatch.setattr(
        private_generation,
        "_make_clues",
        lambda *_args: ("Echoes", {"1A": "Sound that bounces back"}),
    )
    monkeypatch.setattr(
        private_generation,
        "_legacy_puzzle",
        lambda *_args: ("solver-ready puzzle", {"registered": True}),
    )

    starting = SimpleNamespace(profile={"associations": []}, draft={})
    episteme = SimpleNamespace(profile_json={"projection": {}})
    _puzzle, _manifest, provenance = private_generation._generate(
        42, weekday, starting, episteme
    )

    assert fill_options[0]["themes"] == themes[:theme_count]
    assert provenance["weekdayRecipe"] == {
        "id": recipe_id,
        "intent": private_generation._weekday_recipe(weekday)["intent"],
        "themeMode": theme_mode,
        "themeAnswerTarget": theme_count,
        "themeLocksUsed": theme_count,
        "themeEntriesUsed": 1,
        "gridMechanic": "ordinary-letter-grid",
    }


def test_personalization_receipt_binds_one_episteme_revision_without_profile_text():
    episteme = {
        "profileId": "profile-1",
        "revision": 4,
        "projection": {
            "claims": [{"concept": {"label": "wordplay"}}],
            "associations": [{"phrase": "river clock"}],
            "knowledge": [{"task": {"taskId": "answer-form:river"}}],
        },
        "evidence": [{"type": "preference-signal"}],
    }
    receipt = private_generation._personalization_receipt(
        episteme,
        {
            "clue_family_targets": [{"family": "wordplay"}],
            "recent_private_answers": ["RIVER"],
            "language_learning": {"code": "de"},
            "play_calibration": {"recommendation": "balanced"},
        },
        seed=42,
        weekday="wednesday",
        model="gemma4:26b",
    )
    assert receipt["version"] == "private-personalization-receipt-v1"
    assert receipt["epistemeRevision"] == 4
    assert len(receipt["epistemeDigest"]) == 64
    assert receipt["associationSteering"]["projectionCount"] == 1
    assert receipt["associationSteering"]["eligibleCount"] == 1
    assert receipt["inputs"] == {
        "claimCount": 1,
        "associationCount": 1,
        "knowledgeItemCount": 1,
        "evidenceCount": 1,
        "clueFamilyTargetCount": 1,
        "recentExposureCount": 1,
        "languageThread": True,
        "difficultyRecommendation": "balanced",
    }
    assert "wordplay" not in receipt


def test_sunday_retry_policy_has_fast_personal_probe_and_playable_anchor():
    options = {
        "seed": 42,
        "candidates": 200,
        "time": 5,
        "keepMean": 50,
        "minScore": 40,
        "maxIffy": 20,
        "themes": ["RESONANCE", "FREQUENCY", "ECHO", "SOUND"],
        "gridSize": 21,
    }

    attempts = private_generation._fill_retry_options(42, options)

    assert attempts[0]["label"] == "theme-locked-primary"
    assert attempts[0]["options"]["candidates"] == 10
    assert attempts[0]["options"]["time"] == 0.25
    anchor = next(item for item in attempts if item["label"] == "sunday-anchor-fallback")
    assert anchor["seed"] == private_generation._SUNDAY_FALLBACK_SEED
    assert anchor["options"]["themes"] == private_generation._SUNDAY_FALLBACK_THEMES
    assert anchor["options"]["maxIffy"] == 100


def test_shared_affix_mechanic_validator_requires_every_theme_answer_to_match():
    mechanic = {"type": "shared-affix", "affix": "AT", "position": "suffix"}
    assert (
        private_generation._validate_shared_affix_mechanic(
            ["CAT", "BAT", "HAT"], mechanic
        )
        == mechanic
    )
    assert (
        private_generation._validate_shared_affix_mechanic(
            ["CAT", "BAT", "DOG"], mechanic
        )
        is None
    )
    assert (
        private_generation._validate_shared_affix_mechanic(["CAT", "BAT"], mechanic)
        is None
    )
    assert (
        private_generation._validate_shared_affix_mechanic(
            ["CAT", "BAT", "HAT"], {**mechanic, "position": "middle"}
        )
        is None
    )


def test_local_shared_affix_groups_use_the_native_fill_dictionary(
    monkeypatch, tmp_path
):
    data = tmp_path / "data"
    data.mkdir()
    (data / "xwordlist.dict").write_text(
        "CAT;80\nBAT;80\nHAT;80\nDOG;80\n", encoding="utf-8"
    )
    (data / "supplemental.txt").write_text("# no extra words\n", encoding="utf-8")
    monkeypatch.setenv("CROSSWORD_XFILL_ROOT", str(tmp_path))
    private_generation._local_shared_affix_groups.cache_clear()

    groups = private_generation._local_shared_affix_groups()

    assert any(
        group["position"] == "suffix"
        and group["affix"] == "AT"
        and set(group["answers"]) == {"BAT", "CAT", "HAT"}
        for group in groups
    )
    private_generation._local_shared_affix_groups.cache_clear()


def test_language_review_forms_are_optional_local_fill_candidates(
    monkeypatch, tmp_path
):
    data = tmp_path / "data"
    data.mkdir()
    (data / "xwordlist.dict").write_text("HALLO;80\nNEIN;80\nJA;80\n", encoding="utf-8")
    (data / "supplemental.txt").write_text("# no extra words\n", encoding="utf-8")
    monkeypatch.setenv("CROSSWORD_XFILL_ROOT", str(tmp_path))
    private_generation._local_fill_word_set.cache_clear()

    assert private_generation._eligible_language_review_forms(
        ["HALLO", "NEIN", "JA", "MISSING"]
    ) == ["HALLO", "NEIN"]

    private_generation._local_fill_word_set.cache_clear()


def test_language_learning_generation_records_used_and_unplaced_forms():
    context = {
        "language_learning": {
            "language": "German",
            "reviewForms": ["HALLO", "NEIN"],
            "eligibleReviewForms": ["HALLO", "NEIN"],
        }
    }
    record = private_generation._language_learning_generation_record(
        context,
        [
            {"id": "1A", "answer": "HALLO"},
            {"id": "2D", "answer": "NEIN"},
        ],
        {"1A": "Hello, in German", "2D": "No, in German"},
    )

    assert record["usedForms"] == ["HALLO", "NEIN"]
    assert record["unplacedForms"] == []
    assert record["candidatePolicy"] == "optional-local-fill"


def test_language_learning_generation_records_task_pair_provenance():
    record = private_generation._language_learning_generation_record(
        {
            "language_learning": {
                "language": "French",
                "reviewForms": ["OUI"],
                "eligibleReviewForms": ["OUI"],
            }
        },
        [{"id": "1A", "number": 1, "direction": "across", "answer": "OUI"}],
        {"1A": "French for yes"},
    )

    source = record["taskPairSources"]
    assert len(source) == 1
    assert source[0]["entryId"] == "across-1"
    assert source[0]["pairId"] == "fr-en-oui-v1"
    assert source[0]["packId"] == "synthetic-local-language-pairs-v1"
    assert len(source[0]["packDigest"]) == 64
    assert all(character in "0123456789abcdef" for character in source[0]["packDigest"])
    assert source[0]["sourceText"] == "yes"
    assert source[0]["semanticStatus"] == "not-established"
    assert source[0]["reviewStatus"] == "synthetic-unadmitted"


@pytest.mark.parametrize(
    "clue",
    ["German for yes", "German word for no", "Yes in German"],
)
def test_language_learning_generation_accepts_explicit_generated_clue_wording(clue):
    context = {
        "language_learning": {
            "language": "German",
            "reviewForms": ["HALLO"],
            "eligibleReviewForms": ["HALLO"],
        }
    }

    record = private_generation._language_learning_generation_record(
        context,
        [{"id": "1A", "answer": "HALLO"}],
        {"1A": clue},
    )

    assert record["usedForms"] == ["HALLO"]
    assert record["unplacedForms"] == []


def test_language_learning_generation_emits_explicit_display_token_hints(
    monkeypatch,
):
    monkeypatch.setattr(
        private_generation,
        "private_display_text_for_review",
        lambda language, answer: ("CAFÉ", "reviewed-admitted")
        if language == "French" and answer == "CAFE"
        else (None, None),
    )
    record = private_generation._language_learning_generation_record(
        {
            "language_learning": {
                "language": "French",
                "reviewForms": ["CAFE"],
                "eligibleReviewForms": ["CAFE"],
            }
        },
        [
            {
                "id": "1A",
                "number": 1,
                "direction": "across",
                "answer": "CAFE",
            }
        ],
        {"1A": "Coffee, in French"},
    )

    assert record["usedForms"] == ["CAFE"]
    assert record["tokenHints"] == [
        {"entryId": "across-1", "cellIndex": 3, "displayToken": "É"}
    ]
    assert record["tokenHintSource"] == "reviewed-admitted"


def test_language_learning_generation_can_emit_a_local_synthetic_display_hint():
    record = private_generation._language_learning_generation_record(
        {
            "language_learning": {
                "language": "French",
                "reviewForms": ["CAFE"],
                "eligibleReviewForms": ["CAFE"],
            }
        },
        [
            {
                "id": "1A",
                "number": 1,
                "direction": "across",
                "answer": "CAFE",
            }
        ],
        {"1A": "Coffee, in French"},
    )

    assert record["tokenHints"] == [
        {"entryId": "across-1", "cellIndex": 3, "displayToken": "É"}
    ]
    assert record["tokenHintSource"] == "synthetic-unadmitted"


def test_generation_decorates_explicit_language_hint_into_token_construction(
    monkeypatch,
):
    monkeypatch.setattr(private_generation, "_installed_model", lambda: "local-model")
    monkeypatch.setattr(
        private_generation,
        "_profile_context",
        lambda *_args: {
            "language_interest": "French",
            "language_learning": {
                "language": "French",
                "reviewForms": ["CAFE"],
                "eligibleReviewForms": ["CAFE"],
            },
        },
    )
    monkeypatch.setattr(private_generation, "_make_themes", lambda *_args: ["CAFE"])
    monkeypatch.setattr(
        private_generation,
        "generate_full_size_draft",
        lambda **_kwargs: {
            "grid": {
                "fill": ["A" * 15 for _ in range(15)],
                "entries": [
                    {"num": 1, "dir": "A", "answer": "CAFE", "len": 4, "row": 0, "col": 0, "theme": True},
                    *[
                        {"num": index + 1, "dir": "D", "answer": letter, "len": 1, "row": 0, "col": index}
                        for index, letter in enumerate("CAFE")
                    ],
                ],
            }
        },
    )
    monkeypatch.setattr(
        private_generation,
        "_make_clues",
        lambda _model, entries, _context, _weekday: (
            "Cafe",
            {entry["id"]: ("Coffee, in French" if entry["id"] == "1A" else "Letter") for entry in entries},
        ),
    )
    monkeypatch.setattr(
        private_generation,
        "_legacy_puzzle",
        lambda *_args: ("solver-ready puzzle", {"registered": True}),
    )

    starting = SimpleNamespace(
        profile={"associations": [], "observations": [], "learningLanguage": "French"},
        draft={},
    )
    episteme = SimpleNamespace(
        profile_json={
            "evidence": [
                {
                    "type": "session-analysis",
                    "taskLinks": [
                        {"entryId": "across-1", "tasks": [{"taskId": "private-answer-form:CAFE", "language": "fr"}]}
                    ],
                }
            ],
            "projection": {},
        }
    )

    _puzzle, _manifest, provenance = private_generation._generate(
        42, "monday", starting, episteme
    )

    assert provenance["tokenConstruction"]["status"] == "accepted"
    assert provenance["tokenConstruction"]["cells"][0]["displayToken"] == "É"
    assert provenance["tokenConstruction"]["cells"][0]["source"] == "private-language-decorator-v1"


def test_thursday_theme_proposal_returns_answers_with_a_typed_mechanic(monkeypatch):
    request = {}
    proposal = {
        "themes": ["CAT", "BAT", "HAT"],
        "mechanic": {"type": "shared-affix", "affix": "AT", "position": "suffix"},
    }

    def fake_chat(_model, messages, schema, **_kwargs):
        request["messages"] = messages
        request["schema"] = schema
        return proposal

    monkeypatch.setattr(private_generation, "_chat", fake_chat)

    themes, mechanic = private_generation._make_thursday_theme_proposal(
        "local-model", {"recent_private_answers": []}
    )

    assert themes == ["CAT", "BAT", "HAT"]
    assert mechanic == proposal["mechanic"]
    assert request["schema"]["required"] == ["themes", "mechanic"]
    assert request["schema"]["properties"]["mechanic"]["properties"]["type"][
        "enum"
    ] == ["shared-affix"]
    assert "exact same 2-4 letter A-Z affix" in request["messages"][0]["content"]


def test_thursday_theme_proposal_rejects_an_unmatched_mechanic(monkeypatch):
    monkeypatch.setattr(
        private_generation,
        "_chat",
        lambda *_args, **_kwargs: {
            "themes": ["CAT", "BAT", "DOG"],
            "mechanic": {
                "type": "shared-affix",
                "affix": "AT",
                "position": "suffix",
            },
        },
    )

    with pytest.raises(ValueError, match="did not match"):
        private_generation._make_thursday_theme_proposal(
            "local-model", {"recent_private_answers": []}
        )


def test_thursday_mechanic_is_passed_to_clue_generation_and_provenance(
    monkeypatch,
):
    themes = ["CAT", "BAT", "HAT"]
    mechanic = {"type": "shared-affix", "affix": "AT", "position": "suffix"}
    monkeypatch.setattr(private_generation, "_installed_model", lambda: "local-model")
    monkeypatch.setattr(
        private_generation,
        "_make_thursday_theme_proposal",
        lambda *_args: (themes, mechanic),
    )
    monkeypatch.setattr(
        private_generation,
        "generate_full_size_draft",
        lambda **_kwargs: {
            "grid": {
                "entries": [
                    {
                        "num": number,
                        "dir": "A",
                        "answer": answer,
                        "len": len(answer),
                        "row": 0,
                        "col": number - 1,
                        "theme": True,
                        "score": 80,
                    }
                    for number, answer in enumerate(themes, start=1)
                ]
            }
        },
    )
    received = {}

    def fake_clues(_model, entries, context, _weekday):
        received["mechanic"] = context.get("_weekday_theme_mechanic")
        return "Pattern", {entry["id"]: "An ordinary answer clue" for entry in entries}

    monkeypatch.setattr(private_generation, "_make_clues", fake_clues)
    monkeypatch.setattr(
        private_generation,
        "_legacy_puzzle",
        lambda *_args: ("solver-ready puzzle", {"registered": True}),
    )
    starting = SimpleNamespace(profile={"associations": []}, draft={})
    episteme = SimpleNamespace(profile_json={"projection": {}})

    _puzzle, _manifest, provenance = private_generation._generate(
        42, "thursday", starting, episteme
    )

    assert received["mechanic"] == mechanic
    assert provenance["themeMechanic"] == {
        "status": "validated",
        **mechanic,
        "themeAnswers": themes,
    }
    assert provenance["mechanicEvaluation"]["status"] == "pass"
    assert provenance["mechanicEvaluation"]["instanceCount"] == 3
    assert provenance["weekdayRecipe"]["themeMode"] == "shared-affix"


@pytest.mark.parametrize(
    ("themes", "mechanic"),
    [
        (
            ["CAT", "BAT", "HAT"],
            {"type": "shared-affix", "affix": "AT", "position": "suffix"},
        ),
        (
            ["RECAP", "REACT", "REBEL"],
            {"type": "shared-affix", "affix": "RE", "position": "prefix"},
        ),
    ],
    ids=["suffix-at", "prefix-re"],
)
def test_thursday_shared_affix_fixture_boards_keep_truthful_provenance_and_letter_cells(
    monkeypatch, themes, mechanic
):
    """Two deterministic mechanic fixtures stay ordinary letter-grid puzzles."""
    monkeypatch.setattr(private_generation, "_installed_model", lambda: "local-model")
    monkeypatch.setattr(
        private_generation,
        "_make_thursday_theme_proposal",
        lambda *_args: (themes, mechanic),
    )
    monkeypatch.setattr(
        private_generation,
        "generate_full_size_draft",
        lambda **_kwargs: {
            "grid": {
                "entries": [
                    {
                        "num": number,
                        "dir": "A",
                        "answer": answer,
                        "len": len(answer),
                        "row": (number - 1) * 2,
                        "col": 0,
                        "theme": True,
                        "score": 80,
                    }
                    for number, answer in enumerate(themes, start=1)
                ]
            },
            "sourceDigest": "sha256:fixture",
        },
    )
    monkeypatch.setattr(
        private_generation,
        "_make_clues",
        lambda _model, entries, _context, _weekday: (
            "Fixture Thursday",
            {entry["id"]: "Ordinary answer clue" for entry in entries},
        ),
    )

    def fake_legacy_puzzle(
        grid, _themes, title, clues, _model, _weekday, _seed, *_args
    ):
        return (
            Crossword.model_validate(
                {
                    "metadata": {
                        "date": "260101",
                        "title": title,
                        "authors": ["fixture"],
                        "width": 15,
                        "height": 15,
                    },
                    "entries": [
                        {
                            "clue_number": raw["num"],
                            "clue_text": clues[f"{raw['num']}{raw['dir']}"],
                            "direction": "across",
                            "start_x": raw["col"],
                            "start_y": raw["row"],
                            "characters": [
                                {"letters": letter} for letter in raw["answer"]
                            ],
                        }
                        for raw in grid["entries"]
                    ],
                }
            ),
            {"registered": True},
        )

    monkeypatch.setattr(private_generation, "_legacy_puzzle", fake_legacy_puzzle)
    starting = SimpleNamespace(profile={"associations": []}, draft={})
    episteme = SimpleNamespace(profile_json={"projection": {}})

    # The fixture conversion intentionally stops before registry validation;
    # this checks the mechanic output itself never turns a normal letter answer
    # into a rebus/special cell.
    _puzzle, _manifest, provenance = private_generation._generate(
        42, "thursday", starting, episteme
    )

    assert provenance["themeMechanic"] == {
        "status": "validated",
        **mechanic,
        "themeAnswers": themes,
    }
    assert provenance["weekdayRecipe"] == {
        "id": "thursday-private-v1",
        "intent": private_generation._weekday_recipe("thursday")["intent"],
        "themeMode": "shared-affix",
        "themeAnswerTarget": 5,
        "themeLocksUsed": 3,
        "themeEntriesUsed": 3,
        "gridMechanic": "ordinary-letter-grid",
    }
    assert provenance["mechanicEvaluation"]["status"] == "pass"
    assert provenance["mechanicEvaluation"]["boardId"] == "thursday-42"
    assert all(
        all(len(character.letters) == 1 for character in entry.characters)
        for entry in _puzzle.entries
    )


def test_invalid_thursday_mechanic_falls_back_to_standard_theme_generation(
    monkeypatch,
):
    monkeypatch.setattr(private_generation, "_installed_model", lambda: "local-model")
    monkeypatch.setattr(
        private_generation,
        "_make_thursday_theme_proposal",
        lambda *_args: (_ for _ in ()).throw(ValueError("invalid proposal")),
    )
    monkeypatch.setattr(
        private_generation, "_make_themes", lambda *_args: ["ECHO", "MOSS"]
    )
    monkeypatch.setattr(
        private_generation,
        "generate_full_size_draft",
        lambda **_kwargs: {
            "grid": {
                "entries": [
                    {
                        "num": 1,
                        "dir": "A",
                        "answer": "ECHO",
                        "len": 4,
                        "row": 0,
                        "col": 0,
                        "theme": True,
                    }
                ]
            }
        },
    )
    received = {}

    def fake_clues(_model, _entries, context, _weekday):
        received["mechanic"] = context.get("_weekday_theme_mechanic")
        return "Ordinary theme", {"1A": "Sound that bounces back"}

    monkeypatch.setattr(private_generation, "_make_clues", fake_clues)
    monkeypatch.setattr(
        private_generation,
        "_legacy_puzzle",
        lambda *_args: ("solver-ready puzzle", {"registered": True}),
    )
    starting = SimpleNamespace(profile={"associations": []}, draft={})
    episteme = SimpleNamespace(profile_json={"projection": {}})

    _puzzle, _manifest, provenance = private_generation._generate(
        42, "thursday", starting, episteme
    )

    assert received["mechanic"] is None
    assert provenance["themeMechanic"] == {
        "status": "unavailable",
        "type": "shared-affix",
        "reason": "proposal-unavailable",
    }
    assert provenance["mechanicEvaluation"]["status"] == "fallback-safe"
    assert provenance["weekdayRecipe"]["themeMode"] == "standard-theme"


def test_thursday_uses_a_checked_local_affix_group_when_model_proposal_breaks(
    monkeypatch,
):
    monkeypatch.setattr(private_generation, "_installed_model", lambda: "local-model")
    monkeypatch.setattr(
        private_generation,
        "_make_thursday_theme_proposal",
        lambda *_args: (_ for _ in ()).throw(ValueError("malformed model proposal")),
    )
    monkeypatch.setattr(
        private_generation,
        "_local_shared_affix_groups",
        lambda: [
            {
                "type": "shared-affix",
                "affix": "AT",
                "position": "suffix",
                "answers": ["CAT", "BAT", "HAT"],
                "count": 3,
            }
        ],
    )
    monkeypatch.setattr(
        private_generation,
        "generate_full_size_draft",
        lambda **_kwargs: {
            "grid": {
                "entries": [
                    {
                        "num": number,
                        "dir": "A",
                        "answer": answer,
                        "len": len(answer),
                        "row": 0,
                        "col": number - 1,
                        "theme": True,
                        "score": 80,
                    }
                    for number, answer in enumerate(["CAT", "BAT", "HAT"], start=1)
                ]
            }
        },
    )
    monkeypatch.setattr(
        private_generation,
        "_make_clues",
        lambda _model, entries, _context, _weekday: (
            "Local Thursday",
            {entry["id"]: "Ordinary answer clue" for entry in entries},
        ),
    )
    monkeypatch.setattr(
        private_generation,
        "_legacy_puzzle",
        lambda *_args: ("solver-ready puzzle", {"registered": True}),
    )
    starting = SimpleNamespace(profile={"associations": []}, draft={})
    episteme = SimpleNamespace(profile_json={"projection": {}})

    _puzzle, _manifest, provenance = private_generation._generate(
        42, "thursday", starting, episteme
    )

    assert provenance["themeProposal"] == {
        "source": "deterministic-local-affix-group",
        "mechanicRequested": True,
    }
    assert provenance["themeMechanic"]["status"] == "validated"
    assert provenance["mechanicEvaluation"]["status"] == "pass"


def test_thursday_mechanic_is_disabled_when_filled_theme_answers_do_not_match(
    monkeypatch,
):
    mechanic = {"type": "shared-affix", "affix": "AT", "position": "suffix"}
    monkeypatch.setattr(private_generation, "_installed_model", lambda: "local-model")
    monkeypatch.setattr(
        private_generation,
        "_make_thursday_theme_proposal",
        lambda *_args: (["CAT", "BAT", "HAT"], mechanic),
    )
    monkeypatch.setattr(
        private_generation,
        "generate_full_size_draft",
        lambda **_kwargs: {
            "grid": {
                "entries": [
                    {
                        "num": number,
                        "dir": "A",
                        "answer": answer,
                        "len": len(answer),
                        "row": 0,
                        "col": number - 1,
                        "theme": True,
                    }
                    for number, answer in enumerate(["CAT", "BAT", "DOG"], start=1)
                ]
            }
        },
    )
    received = {}

    def fake_clues(_model, entries, context, _weekday):
        received["mechanic"] = context.get("_weekday_theme_mechanic")
        return "Ordinary theme", {entry["id"]: "An ordinary clue" for entry in entries}

    monkeypatch.setattr(private_generation, "_make_clues", fake_clues)
    monkeypatch.setattr(
        private_generation,
        "_legacy_puzzle",
        lambda *_args: ("solver-ready puzzle", {"registered": True}),
    )
    starting = SimpleNamespace(profile={"associations": []}, draft={})
    episteme = SimpleNamespace(profile_json={"projection": {}})

    _puzzle, _manifest, provenance = private_generation._generate(
        42, "thursday", starting, episteme
    )

    assert received["mechanic"] is None
    assert provenance["themeMechanic"] == {
        "status": "unavailable",
        "type": "shared-affix",
        "reason": "fill-pattern-mismatch",
    }
    assert provenance["weekdayRecipe"]["themeMode"] == "standard-theme"
    assert provenance["weekdayRecipe"]["gridMechanic"] == "ordinary-letter-grid"
    assert provenance["mechanicEvaluation"]["status"] == "fallback-safe"
    assert provenance["themeAnswers"] == ["CAT", "BAT", "DOG"]


def test_risky_clue_repair_replaces_an_unverified_factual_surface(monkeypatch):
    entries = [
        {
            "id": "1A",
            "answer": "EVAN",
            "length": 4,
            "theme": False,
            "fillScore": 48,
            "needsFoothold": True,
        },
        {
            "id": "2D",
            "answer": "RESONANCE",
            "length": 9,
            "theme": True,
            "fillScore": 90,
            "needsFoothold": False,
        },
    ]
    monkeypatch.setattr(
        private_generation,
        "_chat",
        lambda *_args, **_kwargs: {
            "clues": [
                {"id": "1A", "text": "Singer with a hit song?"},
            ]
        },
    )

    repaired = private_generation._repair_risky_clues(
        "qwen3.8:27b",
        entries,
        {"1A": "Singer with Uptown Funk fame", "2D": "Vibrational continuity"},
        {"opening_associations": []},
        "wednesday",
    )

    assert repaired["1A"] == "Singer with a hit song?"
    assert repaired["2D"] == "Vibrational continuity"


def test_generation_provenance_reports_monotonic_stage_timings(monkeypatch):
    clock_values = iter([10.0, 10.1, 10.6, 11.0, 13.5, 14.0, 17.25, 17.5])
    monkeypatch.setattr(private_generation, "monotonic", lambda: next(clock_values))
    monkeypatch.setattr(private_generation, "_installed_model", lambda: "qwen3.8:27b")
    monkeypatch.setattr(
        private_generation, "_make_themes", lambda *_args: ["ECHO", "MOSS"]
    )
    monkeypatch.setattr(
        private_generation,
        "generate_full_size_draft",
        lambda **_kwargs: {
            "grid": {
                "entries": [
                    {
                        "num": 1,
                        "dir": "A",
                        "answer": "ECHO",
                        "len": 4,
                        "row": 0,
                        "col": 0,
                        "theme": True,
                    }
                ]
            }
        },
    )
    monkeypatch.setattr(
        private_generation,
        "_make_clues",
        lambda *_args: ("Echoes in the Morning", {"1A": "Sound that bounces back"}),
    )
    monkeypatch.setattr(
        private_generation,
        "_legacy_puzzle",
        lambda *_args: ("solver-ready puzzle", {"registered": True}),
    )

    starting = SimpleNamespace(
        profile={"associations": ["private opening phrase"], "observations": []},
        draft={"object": "thread", "traces": ["echo"]},
    )
    episteme = SimpleNamespace(profile_json={"projection": {}})

    stages = []
    _crossword, _manifest, provenance = private_generation._generate(
        42, "monday", starting, episteme, stage_callback=stages.append
    )

    timings = provenance["timingsSeconds"]
    assert list(timings) == [
        "themeProposal",
        "nativeXfill",
        "clueGeneration",
        "total",
    ]
    assert timings == {
        "themeProposal": 0.5,
        "nativeXfill": 2.5,
        "clueGeneration": 3.25,
        "total": 7.5,
    }
    assert timings["total"] >= sum(
        timings[key] for key in ("themeProposal", "nativeXfill", "clueGeneration")
    )
    assert provenance["clueQuality"]["checkedCount"] == 1
    assert provenance["clueQuality"]["issueCount"] == 0
    assert provenance["clueQuality"]["issueCounts"] == {}
    assert provenance["clueQuality"]["grounding"]["statusCounts"] == {
        "semantic-unverified": 1
    }
    assert provenance["clueFamilyTargets"] == []
    assert stages == [
        "theme-proposal",
        "native-xfill",
        "clue-generation",
        "finalizing",
    ]
    assert "private opening phrase" not in str(provenance)


def _profile():
    return {
        "version": 1,
        "id": str(uuid4()),
        "step": 4,
        "object": "thread",
        "companion": "fork",
        "traces": ["echo", "moss"],
        "weekday": "thursday",
        "learningLanguage": "None for now",
        "excluded": [],
        "complete": True,
    }


def _crossword():
    rows = ["CAT", "ARE", "TEN"]
    entries = []
    across_numbers = [1, 4, 5]
    for row, answer in enumerate(rows):
        entries.append(
            {
                "clue_number": across_numbers[row],
                "clue_text": f"Synthetic across clue {row + 1}",
                "direction": "across",
                "start_x": 0,
                "start_y": row,
                "characters": [{"letters": letter} for letter in answer],
            }
        )
    for column in range(3):
        answer = "".join(row[column] for row in rows)
        entries.append(
            {
                "clue_number": column + 1,
                "clue_text": f"Synthetic down clue {column + 1}",
                "direction": "down",
                "start_x": column,
                "start_y": 0,
                "characters": [{"letters": letter} for letter in answer],
            }
        )
    return Crossword.model_validate(
        {
            "metadata": {
                "date": "260927",
                "title": "Synthetic local puzzle",
                "authors": ["Test fixture"],
                "width": 3,
                "height": 3,
            },
            "entries": entries,
        }
    )


@pytest.fixture
def saved_profile(api):
    profile = _profile()
    response = api.app.test_client().put(
        f"/api/future/profile/{profile['id']}",
        json=profile,
        headers={"If-None-Match": "*"},
    )
    assert response.status_code == 200, response.json
    return profile


def test_private_generation_returns_a_solver_puzzle_and_registers_its_manifest(
    api, monkeypatch, saved_profile
):
    crossword = _crossword()
    with api.app.app_context():
        manifest = register_legacy_puzzle(crossword)
    provenance = {
        "source": "local-ollama-xfill",
        "model": "gemma4:26b",
        "engine": "xfill",
        "seed": 42,
        "weekday": "thursday",
        "themeAnswers": ["CAT"],
        "generatedAt": "2026-09-27T12:00:00+00:00",
        "experimental": True,
    }
    monkeypatch.setattr(
        private_generation,
        "_generate",
        lambda *args: (crossword, manifest, provenance),
    )

    response = api.app.test_client().post(
        "/api/future/private-puzzles",
        json={"profileId": saved_profile["id"], "seed": 42, "weekday": "thursday"},
        headers={"Origin": "http://localhost"},
    )

    assert response.status_code == 200, response.json
    assert response.json["metadata"]["title"] == "Synthetic local puzzle"
    assert len(response.json["entries"]) == 6
    assert response.json["puzzleManifest"] == manifest
    assert response.json["provenance"] == provenance
    assert response.cache_control.no_store

    frozen = response.json["puzzleManifest"]
    session_id = str(uuid4())
    started = api.app.test_client().post(
        "/api/future/sessions",
        json={
            "sessionId": session_id,
            "profileId": saved_profile["id"],
            "puzzleHash": frozen["integrity"]["value"],
            "writerToken": "a" * 64,
            "initialGrid": [
                {"cellId": cell["id"], "token": None, "origin": "unknown"}
                for cell in frozen["cells"]
                if not cell["block"]
            ],
        },
        headers={"Origin": "http://localhost"},
    )
    assert started.status_code == 201, started.json
    receipt = api.app.test_client().get(
        f"/api/future/sessions/{session_id}/private-provenance?profileId={saved_profile['id']}"
    )
    assert receipt.status_code == 200, receipt.json
    assert receipt.json["provenance"] == provenance


def test_private_generation_job_freezes_profile_and_returns_playable_result(
    api, monkeypatch, saved_profile
):
    crossword = _crossword()
    with api.app.app_context():
        manifest = register_legacy_puzzle(crossword)
    provenance = {
        "source": "local-ollama-xfill",
        "model": "gemma4:26b",
        "engine": "xfill",
        "seed": 42,
        "weekday": "thursday",
        "themeAnswers": ["CAT"],
        "experimental": True,
    }
    captured = {}

    def fake_generate(*args, **kwargs):
        captured["starting"] = args[2]
        return crossword, manifest, provenance

    monkeypatch.setattr(private_generation, "_generate", fake_generate)
    idempotency_key = str(uuid4())
    client = api.app.test_client()
    created = client.post(
        "/api/future/private-puzzle-jobs",
        json={
            "profileId": saved_profile["id"],
            "idempotencyKey": idempotency_key,
            "seed": 42,
            "weekday": "thursday",
        },
        headers={"Origin": "http://localhost"},
    )

    assert created.status_code == 202, created.json
    job_id = created.json["id"]
    assert created.json["state"] == "queued"
    assert created.json["playable"] is False

    duplicate = client.post(
        "/api/future/private-puzzle-jobs",
        json={
            "profileId": saved_profile["id"],
            "idempotencyKey": idempotency_key,
            "seed": 42,
            "weekday": "thursday",
        },
        headers={"Origin": "http://localhost"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json["id"] == job_id

    assert process_next_grid_draft(api.app) is True
    ready = client.get(
        f"/api/future/private-puzzle-jobs/{job_id}?profileId={saved_profile['id']}"
    )
    assert ready.status_code == 200, ready.json
    assert ready.json["state"] == "ready"
    assert ready.json["playable"] is True
    assert (
        ready.json["result"]["puzzle"]["metadata"]["title"] == "Synthetic local puzzle"
    )
    assert ready.json["result"]["provenance"] == provenance
    assert captured["starting"].id == saved_profile["id"]
    durable_session_id = str(uuid4())
    durable_manifest = ready.json["result"]["puzzleManifest"]
    started = client.post(
        "/api/future/sessions",
        json={
            "sessionId": durable_session_id,
            "profileId": saved_profile["id"],
            "puzzleHash": durable_manifest["integrity"]["value"],
            "writerToken": "c" * 64,
            "initialGrid": [
                {"cellId": cell["id"], "token": None, "origin": "unknown"}
                for cell in durable_manifest["cells"]
                if not cell["block"]
            ],
        },
        headers={"Origin": "http://localhost"},
    )
    assert started.status_code == 201, started.json
    receipt = client.get(
        f"/api/future/sessions/{durable_session_id}/private-provenance?profileId={saved_profile['id']}"
    )
    assert receipt.status_code == 200, receipt.json
    assert receipt.json["provenance"] == provenance


def test_private_generation_passes_a_selected_local_model_to_sync_generator(
    api, monkeypatch, saved_profile
):
    crossword = _crossword()
    with api.app.app_context():
        manifest = register_legacy_puzzle(crossword)
    captured = {}

    monkeypatch.setattr(
        private_generation, "_ollama_installed_models", lambda: {"qwen3.8:27b"}
    )

    def fake_generate(*args, **kwargs):
        captured["model"] = kwargs.get("model_override")
        return crossword, manifest, {
            "source": "local-ollama-xfill",
            "model": "qwen3.8:27b",
            "engine": "xfill",
        }

    monkeypatch.setattr(private_generation, "_generate", fake_generate)
    response = api.app.test_client().post(
        "/api/future/private-puzzles",
        json={
            "profileId": saved_profile["id"],
            "seed": 42,
            "weekday": "wednesday",
            "model": "qwen3.8:27b",
        },
        headers={"Origin": "http://localhost"},
    )

    assert response.status_code == 200, response.json
    assert captured["model"] == "qwen3.8:27b"


def test_private_generation_uses_saved_model_preference_when_request_omits_model(
    api, monkeypatch, saved_profile
):
    with api.app.app_context():
        record = db.session.get(StartingProfile, saved_profile["id"])
        record.profile = {**record.profile, "modelPreference": "qwen3.8:27b"}
        db.session.commit()

    crossword = _crossword()
    with api.app.app_context():
        manifest = register_legacy_puzzle(crossword)
    captured = {}
    monkeypatch.setattr(
        private_generation, "_ollama_installed_models", lambda: {"qwen3.8:27b"}
    )

    def fake_generate(*args, **kwargs):
        captured["model"] = kwargs.get("model_override")
        return crossword, manifest, {
            "source": "local-ollama-xfill",
            "model": "qwen3.8:27b",
            "engine": "xfill",
        }

    monkeypatch.setattr(private_generation, "_generate", fake_generate)
    response = api.app.test_client().post(
        "/api/future/private-puzzles",
        json={
            "profileId": saved_profile["id"],
            "seed": 42,
            "weekday": "wednesday",
        },
        headers={"Origin": "http://localhost"},
    )

    assert response.status_code == 200, response.json
    assert captured["model"] == "qwen3.8:27b"


def test_private_generation_job_freezes_selected_model_for_worker(
    api, monkeypatch, saved_profile
):
    monkeypatch.setattr(
        private_generation, "_ollama_installed_models", lambda: {"gemma4:26b"}
    )
    key = str(uuid4())
    response = api.app.test_client().post(
        "/api/future/private-puzzle-jobs",
        json={
            "profileId": saved_profile["id"],
            "idempotencyKey": key,
            "seed": 42,
            "weekday": "wednesday",
            "model": "gemma4:26b",
        },
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 202, response.json
    with api.app.app_context():
        job = db.session.get(FutureGridDraftJob, response.json["id"])
        assert job.request_json["model"] == "gemma4:26b"


def test_private_generation_job_freezes_saved_model_preference_when_request_omits_model(
    api, monkeypatch, saved_profile
):
    with api.app.app_context():
        record = db.session.get(StartingProfile, saved_profile["id"])
        record.profile = {**record.profile, "modelPreference": "gemma4:26b"}
        db.session.commit()
    monkeypatch.setattr(
        private_generation, "_ollama_installed_models", lambda: {"gemma4:26b"}
    )
    response = api.app.test_client().post(
        "/api/future/private-puzzle-jobs",
        json={
            "profileId": saved_profile["id"],
            "idempotencyKey": str(uuid4()),
            "seed": 42,
            "weekday": "wednesday",
        },
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 202, response.json
    with api.app.app_context():
        job = db.session.get(FutureGridDraftJob, response.json["id"])
        assert job.request_json["model"] == "gemma4:26b"


def test_private_generation_rejects_unlisted_model_before_generation(
    api, monkeypatch, saved_profile
):
    monkeypatch.setattr(
        private_generation, "_generate", lambda *args, **kwargs: pytest.fail("called")
    )
    response = api.app.test_client().post(
        "/api/future/private-puzzles",
        json={
            "profileId": saved_profile["id"],
            "seed": 42,
            "weekday": "wednesday",
            "model": "made-up:model",
        },
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    assert response.json["error"] == "Unsupported local writing model"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"profileId": "not-a-profile", "seed": 1, "weekday": "wednesday"},
        {"profileId": str(uuid4()), "seed": True, "weekday": "wednesday"},
        {"profileId": str(uuid4()), "seed": 1, "weekday": "not-a-day"},
    ],
)
def test_private_generation_rejects_invalid_requests_without_model_work(
    api, monkeypatch, body
):
    monkeypatch.setattr(
        private_generation, "_generate", lambda *args: pytest.fail("called")
    )
    response = api.app.test_client().post(
        "/api/future/private-puzzles",
        json=body,
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    assert "error" in response.json


def test_private_generation_is_same_origin_only(api):
    response = api.app.test_client().post(
        "/api/future/private-puzzles",
        json={"profileId": str(uuid4()), "seed": 1, "weekday": "wednesday"},
        headers={"Origin": "https://example.invalid"},
    )
    assert response.status_code == 403
