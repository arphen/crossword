"""Focused E21 checks for Thursday mechanics and the Sunday size gate."""

from src.crossword.weekday_mechanics_evaluation import (
    evaluate_sunday_size_gate,
    evaluate_thursday_mechanic_board,
    evaluate_thursday_mechanic_suite,
)


def _board(board_id, answers, mechanic, *, theme_mode="shared-affix"):
    return {
        "id": board_id,
        "grid": {
            "entries": [
                {
                    "num": index,
                    "dir": "A",
                    "row": index - 1,
                    "col": 0,
                    "len": len(answer),
                    "answer": answer,
                    "theme": True,
                }
                for index, answer in enumerate(answers, start=1)
            ]
        },
        "provenance": {
            "weekdayRecipe": {
                "id": "thursday-private-v1",
                "themeMode": theme_mode,
                "gridMechanic": "ordinary-letter-grid",
            },
            "themeMechanic": mechanic,
        },
    }


def test_multi_instance_thursday_fixture_suite_is_deterministic_and_consistent():
    boards = [
        _board(
            "suffix-at",
            ["CAT", "BAT", "HAT"],
            {
                "status": "validated",
                "type": "shared-affix",
                "affix": "AT",
                "position": "suffix",
                "themeAnswers": ["CAT", "BAT", "HAT"],
            },
        ),
        _board(
            "prefix-re",
            ["RECAP", "REACT", "REBEL"],
            {
                "status": "validated",
                "type": "shared-affix",
                "affix": "RE",
                "position": "prefix",
                "themeAnswers": ["RECAP", "REACT", "REBEL"],
            },
        ),
    ]

    first = evaluate_thursday_mechanic_suite(boards)
    second = evaluate_thursday_mechanic_suite(boards)

    assert first == second
    assert first["status"] == "pass"
    assert first["summary"] == {
        "pass": 2,
        "fallbackSafe": 0,
        "fail": 0,
        "boardCount": 2,
    }
    assert [report["instanceCount"] for report in first["reports"]] == [3, 3]
    assert all(
        instance["affixMatches"]
        for report in first["reports"]
        for instance in report["instances"]
    )
    assert all(
        report["uncertainty"]["playerSolveProbability"] == "unmeasured"
        for report in first["reports"]
    )


def test_thursday_evaluator_rejects_one_inconsistent_declared_instance():
    board = _board(
        "mismatch",
        ["CAT", "BAT", "DOG"],
        {
            "status": "validated",
            "type": "shared-affix",
            "affix": "AT",
            "position": "suffix",
            "themeAnswers": ["CAT", "BAT", "DOG"],
        },
    )

    report = evaluate_thursday_mechanic_board(board)

    assert report["status"] == "fail"
    assert report["instanceCount"] == 3
    assert "affix-mismatch:DOG" in report["reasonCodes"]


def test_unavailable_thursday_mechanic_must_fall_back_to_an_ordinary_grid():
    board = _board(
        "fallback",
        ["ECHO", "MOSS"],
        {
            "status": "unavailable",
            "type": "shared-affix",
            "reason": "fill-pattern-mismatch",
        },
        theme_mode="standard-theme",
    )

    report = evaluate_thursday_mechanic_board(board)

    assert report["status"] == "fallback-safe"
    assert report["mechanic"]["status"] == "unavailable"
    assert report["reasonCodes"] == []
    assert all(instance["affixMatches"] is None for instance in report["instances"])


def test_invalid_fallback_cannot_smuggle_a_special_or_mismatched_grid():
    board = _board(
        "unsafe-fallback",
        ["ECHO", "MOSS"],
        {
            "status": "unavailable",
            "type": "shared-affix",
            "reason": "proposal-unavailable",
        },
        theme_mode="shared-affix",
    )
    board["grid"]["entries"][1]["answer"] = "MOSS!"

    report = evaluate_thursday_mechanic_board(board)

    assert report["status"] == "fail"
    assert "fallback-theme-mode-mismatch" in report["reasonCodes"]
    assert "fallback-non-ordinary-theme-answer:MOSS!" in report["reasonCodes"]


def test_sunday_requires_exact_size_and_both_runtime_capabilities():
    too_small = evaluate_sunday_size_gate("sunday", 15, 15)
    incomplete = evaluate_sunday_size_gate("sunday", 21, 21)
    enabled = evaluate_sunday_size_gate(
        "sunday",
        21,
        21,
        {"nativeConstruction21x21": True, "solverUi21x21": True},
    )

    assert too_small["status"] == "blocked"
    assert too_small["reasonCodes"] == ["sunday-requires-21x21"]
    assert incomplete["status"] == "blocked"
    assert incomplete["missingCapabilities"] == [
        "nativeConstruction21x21",
        "solverUi21x21",
    ]
    assert enabled["status"] == "enabled"
    assert enabled["enabled"] is True


def test_sunday_gate_does_not_relabel_other_weekdays_or_claim_player_quality():
    report = evaluate_sunday_size_gate("wednesday", 15, 15)

    assert report["status"] == "not-applicable"
    assert report["enabled"] is True
    assert report["reasonCodes"] == []
