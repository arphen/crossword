"""Tests for answer-derivation leaks in private clues.

These cover the case the earlier guards could not see: a clue that defines an
answer using the answer's own morphology. ``more shady`` for ``SHADIER`` is not
a near miss that happens to be close to the answer, it is the answer's own
comparative folded into its own definition, and no convention marker is
present for the marker-based morphology guard to find.
"""

import pytest

from crossword.clue_semantic_challenger import challenge_private_clue_pair
from crossword.private_puzzle_generation import (
    _answer_lexical_forms,
    _clue_degree_issue,
    _clue_wordplay_issue,
    _degree_forms,
)

# Surfaces observed in local boards or built to the same shape: the clue states
# the answer's meaning by gradating the answer's own base.
TAUTOLOGICAL = [
    ("SHADIER", "more shady"),
    ("SHADIER", "More shady than a noir detective"),
    ("SHADIER", "less shady"),
    ("SHADIEST", "most shady"),
    ("NICER", "more nice"),
    ("OLDER", "more old"),
    ("ODDER", "more odd"),
    ("BRIGHTER", "more bright"),
    ("DARKER", "most dark"),
    ("COOLER", "more cool"),
    ("DEEPER", "more deep"),
    ("QUIETER", "most quiet"),
    ("SORRIER", "more sorry"),
    ("HAPPIER", "more happy"),
    ("EARLIER", "more early"),
    ("LARGER", "most large"),
    ("SIMPLER", "more simple"),
    ("NOBLER", "more noble"),
    ("WISER", "most wise"),
    ("FATTER", "more fat"),
    ("SWEETER", "more sweet"),
    ("FASTER", "more fast"),
    ("SLOWER", "most slow"),
    ("HIGHER", "more high"),
    ("WIDER", "more wide"),
    ("NOISIER", "more noisy"),
    ("DIRTIER", "most dirty"),
    ("HEAVIER", "more heavy"),
    ("COLDER", "most cold"),
    ("WARMER", "more warm"),
    ("STRONGER", "more strong"),
    ("YOUNGER", "more young"),
    ("BOLDER", "more bold"),
    ("RICHER", "more rich"),
    ("POORER", "most poor"),
    ("FITTER", "more fit"),
    ("SILLIER", "more silly"),
    ("GRANDER", "more grand"),
    ("WETTER", "most wet"),
    ("BIGGER", "more big"),
    ("HOTTER", "most hot"),
    ("MEANER", "more mean"),
    ("KEENER", "more keen"),
]

# Known limit of the orthographic rule, recorded rather than hidden: doubling
# past three letters depends on stress (THIN -> THINNER, but OPEN -> OPENER),
# which this guard deliberately does not attempt. Such a clue is still caught
# if it prints the answer itself.
STRESS_DEPENDENT = ("THIN", "THINNER")

# The same answers with clues that gradate an unrelated base, or do not
# gradate at all. Every one of these must stay legal: a guard that rejects
# them is a guard that will quietly starve the generator.
UNRELATED_COMPARATIVE = [
    ("SHADIER", "more bright"),
    ("SHADIER", "dubious, equivocally dark"),
    ("SHADIER", "suspicious-looking"),
    ("NICER", "more dull"),
    ("OLDER", "more young"),
    ("LARGER", "more tiny"),
    ("DARKER", "more pale"),
    ("QUIETER", "more shrill"),
    ("HAPPIER", "more grim"),
    ("EARLIER", "more later"),
    ("SIMPLER", "more ornate"),
    ("WISER", "more foolish"),
    ("FASTER", "quick runner"),
    ("BEST", "more good"),
    ("BEST", "more well"),
    ("BETTER", "more good"),
    ("MEN", "more manly"),
    ("COVER", "cove by the sea"),
    ("EARLY", "ear of corn"),
    ("QUIET", "hush falls"),
    ("ODD", "stranger than fiction"),
    ("DEEP", "bottom of the sea"),
    ("COOLER", "more hot"),
    ("HEAVIER", "more light"),
    ("BOLDER", "more timid"),
    ("RICHER", "more poor"),
    ("SILLIER", "more wise"),
    ("FASTER", "more slow"),
    ("HIGHER", "more low"),
    ("YOUNGER", "more old"),
    ("FATTER", "more thin"),
    ("SWEETER", "more sour"),
    ("GREATER", "more small"),
    ("WISER", "more silly"),
    ("ODDER", "more even"),
    ("DEEPER", "more shallow"),
    ("LOUDER", "more quiet"),
    ("NICER", "more harsh"),
    ("FORMER", "more formal"),
    ("LATTER", "more formal"),
    ("POORER", "more wealthy"),
    ("GRANDER", "more humble"),
]

# Degree forms of the answer appearing anywhere in the surface are a leak in
# the same way the plain answer is.
DERIVATION_LEAKS = [
    ("SHADY", "shadier character"),
    ("SHADY", "shady, but not shadier"),
    ("SHADY", "shadiest of all"),
    ("NICE", "nicer alternative"),
    ("LARGE", "larger than life"),
    ("SORRY", "sorrier excuse"),
    ("DARK", "darker shade"),
    ("QUIET", "quieter room"),
    ("STRANGE", "stranger things"),
    ("CLEAN", "cleaner air"),
    ("SHADIER", "shady business"),
    ("SHADIEST", "shady business"),
    ("SORRIER", "sorry excuse"),
    ("HAPPIER", "happy camper"),
    ("SORRIEST", "sorry excuse"),
]

# A bare stem of a doubled comparative, with nothing else in the surface to
# show it is a comparison. Reversing these would mean rejecting every clue for
# BUTTER that contains the word "but", so the guard leaves them and waits for
# comparative context instead. Recorded as a limit, not an oversight.
BARE_STEM_LEFT_ALONE = [
    ("BIGGER", "big opportunity"),
    ("HOTTER", "hot weather"),
    ("FATTER", "fat chance"),
    ("BUTTER", "bread but not jam"),
    ("BITTER", "not sweet, but sharp"),
    ("THINNER", "slim chance"),
]

# Shapes that look like a reversal but are not: an -IER word whose base would
# be invented, and an -ER word whose plain base is an unrelated word. These
# must survive, because a guard that eats them turns the generator away from
# perfectly good fill.
NON_REVERSALS = [
    ("CASHIER", "clerk at a till"),
    ("CASHIER", "cash register operator"),
    ("PIONEER", "early settler"),
    ("MINER", "worker in a pit"),
    ("COVER", "protect with a lid"),
    ("BIGGER", "large in scope"),
    ("LEADER", "head of the team"),
    ("CARPET", "rug in the hall"),
]


# The leak family. Which member fires depends on how much of the answer's
# morphology the surface exposes, and any of them is a rejection.
LEAK_REASONS = {"answer-giveaway", "answer-form-in-clue", "tautological-degree-form"}


@pytest.mark.parametrize("answer,clue", TAUTOLOGICAL)
def test_comparative_phrase_that_restates_the_answer_is_rejected(answer, clue):
    assert _clue_degree_issue({"answer": answer}, clue) == "tautological-degree-form"
    assert _clue_wordplay_issue({"answer": answer}, clue) in LEAK_REASONS


@pytest.mark.parametrize("answer,clue", UNRELATED_COMPARATIVE)
def test_unrelated_comparatives_and_plain_definitions_stay_legal(answer, clue):
    assert _clue_degree_issue({"answer": answer}, clue) is None
    assert _clue_wordplay_issue({"answer": answer}, clue) is None


@pytest.mark.parametrize("answer,clue", DERIVATION_LEAKS)
def test_answer_degree_form_in_clue_is_a_leak(answer, clue):
    assert _clue_wordplay_issue({"answer": answer}, clue) == "answer-form-in-clue"


@pytest.mark.parametrize("answer,clue", NON_REVERSALS)
def test_words_that_only_look_like_a_reversal_stay_legal(answer, clue):
    assert _clue_wordplay_issue({"answer": answer}, clue) is None


@pytest.mark.parametrize("answer,clue", BARE_STEM_LEFT_ALONE)
def test_bare_stem_without_comparative_context_is_not_guessed(answer, clue):
    assert _clue_wordplay_issue({"answer": answer}, clue) is None


def test_comparative_context_catches_a_doubled_comparative():
    assert _clue_degree_issue({"answer": "BIGGER"}, "more big") == (
        "tautological-degree-form"
    )
    assert _clue_degree_issue({"answer": "HOTTER"}, "most hot") == (
        "tautological-degree-form"
    )
    assert _clue_degree_issue({"answer": "FATTER"}, "more fat") == (
        "tautological-degree-form"
    )


def test_tautological_degree_form_is_a_safe_mechanical_fallback():
    verdict = challenge_private_clue_pair(
        {"answer": "SHADIER"},
        "more shady",
        mechanical_issue="tautological-degree-form",
    )
    assert verdict["classification"] == "safe-fallback"
    assert "mechanical-check-failed:tautological-degree-form" in verdict["reasons"]


def test_degree_forms_follow_ordinary_orthography_only():
    assert _degree_forms("SHADY") == {"SHADY", "SHADIER", "SHADIEST"}
    assert _degree_forms("NICE") == {"NICE", "NICER", "NICEST"}
    assert _degree_forms("LARGE") == {"LARGE", "LARGER", "LARGEST"}
    # Irregular pairs are not invented: a wrong degree pair would reject an
    # unrelated clue, which is a worse failure than missing one.
    assert "BETTER" not in _degree_forms("GOOD")
    assert _degree_forms("OX") == set()
    base, doubled = STRESS_DEPENDENT
    assert doubled not in _degree_forms(base)
    assert "FATTER" in _degree_forms("FAT") and "WETTER" in _degree_forms("WET")


def test_lexical_forms_include_degree_without_losing_tense_coverage():
    forms = _answer_lexical_forms("SHADY")
    assert {"SHADIER", "SHADIEST"} <= forms
    assert {"SHADYS", "SHADYED", "SHADYING"} <= forms
    # Short fill is kept out of the degree expansion on purpose.
    assert "OXER" not in _answer_lexical_forms("OX")


def test_malformed_input_is_ignored_rather_than_raising():
    assert _clue_degree_issue(None, "more shady") is None
    assert _clue_degree_issue({"answer": "SHADIER"}, None) is None
    assert _clue_degree_issue({"answer": ""}, "more shady") is None
    assert _clue_degree_issue({"answer": "SHADIER"}, "") is None
