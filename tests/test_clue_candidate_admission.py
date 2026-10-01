"""Tests for deterministic candidate admission (Q07).

Admission rejects deterministic failures and duplicates only; witness and
genre steer survivor selection. Comparison picks must name the difference.
All fixtures are hand-listed, offline, no model.
"""

import pytest

from crossword.clue_candidate_admission import (
    admit_candidate,
    comparison_payload,
    score_surface_set,
    select_survivors,
    shape_admit,
    token_overlap,
    validate_comparison_response,
)


def test_shape_admit_accepts_exact_shape_only():
    assert shape_admit({"id": "1A", "text": "A clue"})["admitted"] is True
    assert shape_admit({"id": "1A"})["admitted"] is False
    assert shape_admit({"id": "1A", "text": "  "})["admitted"] is False
    assert shape_admit({"id": "1A", "text": "xy", "extra": 1})["admitted"] is True
    assert shape_admit({"id": "", "text": "A clue"})["admitted"] is False
    assert shape_admit({"id": "1A", "text": "has\nnewline"})["admitted"] is False
    assert shape_admit("not-a-dict")["admitted"] is False
    assert shape_admit(None)["admitted"] is False


def test_token_overlap_measures_word_bags():
    assert token_overlap("Fluffy feline", "Fluffy feline") == 1.0
    assert token_overlap("Fluffy feline", "Fluffy pet") == pytest.approx(1 / 3)
    assert token_overlap("abc", "def") == 0.0
    assert token_overlap("", "") == 1.0
    assert token_overlap("", "abc") == 0.0


def test_admission_rejects_deterministic_issues():
    decision = admit_candidate(
        "more shady", issue_codes=["tautological-degree-form"], witnessed_family="definition", admitted_texts=[]
    )
    assert decision == {"admitted": False, "reasons": ["tautological-degree-form"]}


def test_admission_rejects_near_duplicates():
    first = admit_candidate(
        "Fluffy feline", issue_codes=[], witnessed_family="definition", admitted_texts=[]
    )
    assert first["admitted"] is True
    second = admit_candidate(
        "Fluffy feline!",
        issue_codes=[],
        witnessed_family="definition",
        admitted_texts=["Fluffy feline"],
    )
    assert second == {"admitted": False, "reasons": ["duplicate-draft"]}
    distinct = admit_candidate(
        "Green moss",
        issue_codes=[],
        witnessed_family="definition",
        admitted_texts=["Fluffy feline"],
    )
    assert distinct["admitted"] is True


def test_admission_records_witness_without_gating_on_it():
    decision = admit_candidate(
        "Without light", issue_codes=[], witnessed_family="definition", admitted_texts=[]
    )
    assert decision == {"admitted": True, "reasons": [], "witnessedFamily": "definition"}


def test_survivors_prefer_witnessed_then_earliest_with_limit():
    candidates = [
        {"text": "plain one", "admitted": True, "witnessedFamily": "definition", "round": 0},
        {"text": "rejected", "admitted": False, "witnessedFamily": "definition", "round": 0},
        {"text": "Branch specialist?", "admitted": True, "witnessedFamily": "pun", "round": 2},
        {"text": "Spring forward?", "admitted": True, "witnessedFamily": "pun", "round": 1},
        {"text": "plain two", "admitted": True, "witnessedFamily": "definition", "round": 3},
    ]
    survivors = select_survivors(candidates, limit=3)
    assert [s["text"] for s in survivors] == [
        "Branch specialist?",
        "Spring forward?",
        "plain one",
    ]
    assert select_survivors([]) == []
    assert len(select_survivors(candidates, limit=1)) == 1


def test_comparison_payload_names_ids_and_difference_rule():
    payload = comparison_payload(
        "ECHO", 4, [{"draftId": "r0-0", "text": "Sound echo"}, {"draftId": "r1-0", "text": "Repeat?"}]
    )
    assert payload["answer"] == "ECHO"
    assert [c["id"] for c in payload["candidates"]] == ["r0-0", "r1-0"]
    assert "difference" in payload["instruction"]


def test_comparison_validation_accepts_only_surviving_pick_with_difference():
    good = validate_comparison_response(
        {"pick": "r1-0", "difference": "Names the sound, not the echo."}, ["r0-0", "r1-0"]
    )
    assert good == {"pick": "r1-0", "difference": "Names the sound, not the echo.", "valid": True, "reason": None}
    assert validate_comparison_response({"pick": "r9", "difference": "x"}, ["r0-0"])["valid"] is False
    assert validate_comparison_response({"pick": "r0-0", "difference": "  "}, ["r0-0"])["reason"] == "comparison-difference-missing"
    assert validate_comparison_response("nope", ["r0-0"])["reason"] == "comparison-unparseable"


def test_score_surface_set_reports_rule_rates_only():
    report = score_surface_set(
        [
            {"answer": "SHADIER", "clue": "more shady", "issues": ["tautological-degree-form"], "witnessedFamily": "definition", "genre": "plain-definition"},
            {"answer": "TELLER", "clue": "Branch specialist?", "issues": [], "witnessedFamily": "pun", "genre": "plain-definition"},
            {"answer": "DEN", "clue": "A quiet room?", "issues": [], "witnessedFamily": "pseudo-pun", "genre": "plain-definition"},
            {"answer": "BON", "clue": "___ voyage", "issues": [], "witnessedFamily": "fill-blank", "genre": "fill-blank"},
        ]
    )
    assert report["surfaces"] == 4
    assert report["leakCount"] == 1
    assert report["leakRate"] == 0.25
    assert report["grammarCleanRate"] == 0.75
    assert report["witnessedNonDefinitionCount"] == 2
    assert report["pseudoPunCount"] == 1
    assert report["genreCounts"] == {"fill-blank": 1, "plain-definition": 3}


def test_path_selection_is_tier_driven_with_env_override(monkeypatch):
    from crossword import private_puzzle_generation as generation

    assert generation._use_candidate_path("llama3.2:3b") is True
    assert generation._use_candidate_path("gemma4:26b") is False
    monkeypatch.setenv("CROSSWORD_CLUE_CANDIDATES", "1")
    assert generation._use_candidate_path("gemma4:26b") is True
    monkeypatch.setenv("CROSSWORD_CLUE_CANDIDATES", "0")
    assert generation._use_candidate_path("llama3.2:3b") is False


def test_draft_seeds_are_deterministic_and_scoped():
    from crossword.private_puzzle_generation import _candidate_draft_seed

    assert _candidate_draft_seed(6103, 0, 0) == _candidate_draft_seed(6103, 0, 0)
    assert _candidate_draft_seed(6103, 0, 0) != _candidate_draft_seed(6103, 1, 0)
    assert _candidate_draft_seed(6103, 0, 0) != _candidate_draft_seed(6103, 0, 1)
    assert _candidate_draft_seed(None, 0, 0) is None
    assert _candidate_draft_seed("nope", 0, 0) is None
