"""The private clue bridge checks visible grammar signals only."""

from src.crossword.clue_grammar_bridge import (
    CLUE_GRAMMAR_BRIDGE_VERSION,
    summarize_surface_clue_families,
    validate_surface_clue_family,
)
from src.crossword.private_puzzle_generation import _clue_family_observation


def _check(clue: str):
    return validate_surface_clue_family(clue, _clue_family_observation(clue))


def test_bridge_accepts_observer_signals_and_preserves_semantic_boundary():
    cases = {
        '"Not a chance!"': "spoken-equivalent",
        "[Sigh of relief]": "nonverbal-expression",
        "Safe and ___": "fill-blank",
        "Estimated arrival, briefly": "metalinguistic",
        "Branch specialist?": "pun",
        "Purring pets": "definition",
        "Thank you, in German": "factual-relation",
    }

    for clue, family in cases.items():
        result = _check(clue)
        assert result["version"] == CLUE_GRAMMAR_BRIDGE_VERSION
        assert result["houseGrammarVersion"] == "clue-grammar-v1"
        assert result["family"] == family
        assert result["valid"] is True
        assert result["semanticStatus"] == "not-established"
        assert "semantic-family-unverified" in result["uncertainty"]


def test_bridge_reports_surface_drift_without_blocking_or_claiming_meaning():
    observation = _clue_family_observation("A spoken line")
    observation = {
        **observation,
        "family": "spoken-equivalent",
        "signals": [],
    }
    result = validate_surface_clue_family("A spoken line", observation)

    assert result["valid"] is False
    assert {issue["code"] for issue in result["issues"]} == {
        "missing-observed-signal",
        "surface-family-mismatch",
    }
    assert result["semanticStatus"] == "not-established"


def test_bridge_checks_optional_surface_spans_and_summarizes_diagnostics():
    observation = _clue_family_observation("[Sigh]")
    signal = {**observation["signals"][0], "text": "wrong"}
    invalid = validate_surface_clue_family(
        "[Sigh]", {**observation, "signals": [signal]}
    )
    valid = _check("Purring pets")
    summary = summarize_surface_clue_families(
        [{"grammarBridge": invalid}, {"grammarBridge": valid}]
    )

    assert invalid["valid"] is False
    assert "invalid-signal-span" in {issue["code"] for issue in invalid["issues"]}
    assert summary["checkedCount"] == 2
    assert summary["validCount"] == 1
    assert summary["invalidCount"] == 1
    assert summary["semanticStatus"] == "not-established"
