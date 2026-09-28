from src.crossword.clue_grounding_validators import (
    CLUE_GROUNDING_VALIDATORS_VERSION,
    validate_private_clue_witnesses,
)
from src.crossword import private_puzzle_generation


def test_anagram_witness_has_literal_typed_spans_and_a_narrow_pass():
    result = validate_private_clue_witnesses({"answer": "ECHO"}, "Anagram of HOCE")

    assert result["version"] == CLUE_GROUNDING_VALIDATORS_VERSION
    assert result["status"] == "passed"
    assert result["semanticStatus"] == "not-established"
    assert result["validators"]["anagram"] == {
        "version": CLUE_GROUNDING_VALIDATORS_VERSION,
        "kind": "anagram",
        "status": "passed",
        "semanticStatus": "not-established",
        "truth": "not-established",
        "uncertainty": [
            "semantic-sense-unverified",
            "factual-support-unverified",
        ],
        "comparison": "multiset-equality",
        "sourceLength": 4,
        "answerLength": 4,
        "sourceShape": "letters-only",
        "answerShape": "letters-only",
        "observedInput": "HOCE",
    }
    source = next(
        span for span in result["typedSpans"] if span["role"] == "source-letters"
    )
    assert source["kind"] == "mechanic-input"
    assert source["text"] == "HOCE"
    assert "Anagram of HOCE"[source["start"] : source["end"]] == source["text"]


def test_reversal_witness_fails_only_the_mechanical_comparison():
    result = validate_private_clue_witnesses(
        {"answer": "ETENIM"}, '"MIND" spelled backward'
    )

    assert result["status"] == "failed"
    assert result["validators"]["reversal"]["status"] == "failed"
    assert result["validators"]["reversal"]["comparison"] == "reverse-string"
    assert result["semanticStatus"] == "not-established"


def test_hidden_word_witness_checks_a_quoted_contiguous_source():
    result = validate_private_clue_witnesses(
        {"answer": "ECHO"}, 'Hidden in "THE ECHO CHAMBER"'
    )

    assert result["status"] == "passed"
    validator = result["validators"]["hidden-word"]
    assert validator["status"] == "passed"
    assert validator["comparison"] == "contiguous-substring"
    source = next(
        span for span in result["typedSpans"] if span["role"] == "source-letters"
    )
    assert source["text"] == "THE ECHO CHAMBER"

    mismatch = validate_private_clue_witnesses(
        {"answer": "MINT"}, 'Hidden in "THE ECHO CHAMBER"'
    )
    assert mismatch["status"] == "failed"
    assert mismatch["validators"]["hidden-word"]["status"] == "failed"


def test_supported_translation_witness_is_answer_checked_without_claiming_fact():
    result = validate_private_clue_witnesses({"answer": "OUI"}, "French yes")

    assert result["status"] == "passed"
    validator = result["validators"]["language-translation"]
    assert validator["status"] == "passed"
    assert validator["language"] == "french"
    assert validator["target"] == "yes"
    assert validator["comparison"] == "small-local-translation-map"
    assert validator["semanticStatus"] == "not-established"
    assert any(
        span["kind"] == "language-indicator" and span["text"] == "French"
        for span in result["typedSpans"]
    )
    assert any(
        span["kind"] == "translation-target" and span["text"] == "yes"
        for span in result["typedSpans"]
    )


def test_unrecognized_translation_target_remains_unresolved_and_answer_free():
    result = validate_private_clue_witnesses(
        {"answer": "DANKE"}, "Thank you, in German"
    )

    assert result["status"] == "unresolved"
    assert result["validators"]["language-translation"]["status"] == "not-observed"
    assert result["validators"]["language-translation"]["reason"] == (
        "no-supported-translation-target"
    )
    assert result["semanticStatus"] == "not-established"


def test_private_grounding_and_bundle_persist_the_witness_contract():
    grounding = private_puzzle_generation._clue_grounding(
        {"id": "1A", "answer": "OUI"}, "French yes"
    )
    assert grounding["familyObservation"]["family"] == "factual-relation"
    assert grounding["relation"] == "language-label"
    assert grounding["witnessValidators"]["status"] == "passed"
    assert (
        grounding["witnessValidators"]["validators"]["language-translation"]["status"]
        == "passed"
    )

    bundle = private_puzzle_generation._grounded_clue_bundle(
        [{"id": "1A", "answer": "OUI"}], {"1A": "French yes"}
    )
    record = bundle["entries"][0]
    assert record["witnessValidators"]["version"] == CLUE_GROUNDING_VALIDATORS_VERSION
    assert record["semanticStatus"] == "not-established"


def test_hidden_word_mismatch_is_safe_fallback_diagnostic():
    assert private_puzzle_generation._clue_wordplay_issue(
        {"answer": "MINT"}, 'Hidden in "THE ECHO CHAMBER"'
    ) == "hidden-word-mismatch"
    challenge = private_puzzle_generation._clue_grounding(
        {"id": "1A", "answer": "MINT"}, 'Hidden in "THE ECHO CHAMBER"'
    )
    assert challenge["semanticChallenge"]["classification"] == "safe-fallback"
