from src.crossword.clue_grounding_validators import validate_private_clue_witnesses
from src.crossword.clue_semantic_challenger import (
    CLUE_SEMANTIC_CHALLENGER_VERSION,
    challenge_private_clue_pair,
    summarize_challenge_classifications,
)
from src.crossword import private_puzzle_generation as private_generation


def _bridge(clue):
    return private_generation._clue_grounding({"id": "1A", "answer": "ECHO"}, clue)[
        "grammarBridge"
    ]


def test_answer_free_scaffold_is_a_safe_fallback_and_never_a_semantic_claim():
    result = challenge_private_clue_pair(
        {"id": "1A", "answer": "MOMENT"},
        "Entry supported by its crossings (6 letters)",
        fallback_used=True,
    )

    assert result["version"] == CLUE_SEMANTIC_CHALLENGER_VERSION
    assert result["classification"] == "safe-fallback"
    assert "answer-free-crossing-scaffold" in result["reasons"]
    assert result["semanticStatus"] == "not-established"
    assert result["playPolicy"] == "never-gates-private-play"


def test_passed_anagram_witness_is_mechanically_supported_but_not_semantically_proven():
    entry = {"id": "1A", "answer": "ECHO"}
    clue = "Anagram of HOCE"
    result = challenge_private_clue_pair(
        entry,
        clue,
        mechanical_issue=None,
        risk_flags=[],
        surface_issues=[],
        witness_validators=validate_private_clue_witnesses(entry, clue),
        grammar_bridge=_bridge(clue),
    )

    assert result["classification"] == "mechanically-supported"
    assert result["mechanicalStatuses"] == ["passed"]
    assert result["semanticStatus"] == "not-established"


def test_failed_mechanical_witness_is_sent_to_answer_free_fallback():
    entry = {"id": "1A", "answer": "ETENIM"}
    clue = '"MIND" spelled backward'
    result = challenge_private_clue_pair(
        entry,
        clue,
        mechanical_issue="reversal-mismatch",
        witness_validators=validate_private_clue_witnesses(entry, clue),
    )

    assert result["classification"] == "safe-fallback"
    assert result["reasons"] == ["mechanical-check-failed:reversal-mismatch"]
    assert result["semanticStatus"] == "not-established"


def test_ordinary_or_factual_surface_needs_review_without_a_ledger():
    result = challenge_private_clue_pair(
        {"id": "1A", "answer": "EVAN"},
        "Singer with a hit song?",
        risk_flags=["unsupported-factual-surface"],
        surface_issues=[],
        witness_validators={"status": "not-observed", "validators": {}},
    )

    assert result["classification"] == "needs-review"
    assert result["reasons"] == ["risk:unsupported-factual-surface"]
    assert result["semanticStatus"] == "not-established"


def test_model_recommendation_is_bounded_advisory_data_and_cannot_promote_a_pair():
    result = challenge_private_clue_pair(
        {"id": "1A", "answer": "ECHO"},
        "Sound that bounces back",
        model_response={
            "disposition": "keep",
            "confidence": "high",
            "reason": "The local model recognizes a likely ordinary definition.",
        },
    )

    assert result["classification"] == "needs-review"
    assert result["modelRecommendation"] == {
        "status": "accepted-advisory",
        "semanticStatus": "not-established",
        "uncertainty": ["model-judgment-unverified"],
        "disposition": "keep",
        "confidence": "high",
        "reason": "The local model recognizes a likely ordinary definition.",
        "source": "local-model",
    }


def test_invalid_model_response_is_not_persisted_as_evidence():
    result = challenge_private_clue_pair(
        {"id": "1A", "answer": "ECHO"},
        "Sound that bounces back",
        model_response={"disposition": "pass", "reason": "maybe"},
    )

    assert result["modelRecommendation"]["status"] == "ignored-invalid"
    assert result["modelRecommendation"]["reason"] == "response-shape-unaccepted"
    assert result["semanticStatus"] == "not-established"


def test_classification_summary_is_stable_and_keeps_play_boundary():
    records = [
        challenge_private_clue_pair({}, ""),
        challenge_private_clue_pair({"answer": "ECHO"}, "Sound that bounces back"),
    ]
    summary = summarize_challenge_classifications(records)

    assert summary == {
        "version": CLUE_SEMANTIC_CHALLENGER_VERSION,
        "checkedCount": 2,
        "classificationCounts": {
            "mechanically-supported": 0,
            "needs-review": 1,
            "safe-fallback": 1,
        },
        "semanticStatus": "not-established",
        "uncertainty": [
            "semantic-sense-unverified",
            "factual-support-unverified",
        ],
        "playPolicy": "never-gates-private-play",
    }


def test_private_grounding_exposes_the_challenge_projection():
    grounding = private_generation._clue_grounding(
        {"id": "1A", "answer": "ECHO"}, "Anagram of HOCE"
    )

    assert grounding["semanticChallenge"]["classification"] == (
        "mechanically-supported"
    )
    bundle = private_generation._grounded_clue_bundle(
        [{"id": "1A", "answer": "ECHO"}], {"1A": "Anagram of HOCE"}
    )
    assert bundle["semanticChallenge"]["classificationCounts"] == {
        "mechanically-supported": 1,
        "needs-review": 0,
        "safe-fallback": 0,
    }
    assert bundle["entries"][0]["semanticChallenge"]["semanticStatus"] == (
        "not-established"
    )
