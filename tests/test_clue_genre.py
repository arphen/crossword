"""Tests for the closed genre census and v1 caps (Q05).

Genre asks what kind of boring a surface is, over a closed taxonomy that is
reported before it is enforced. The two v1 caps exist because the corpus
already found them: name-slot without a source-backed sense, and fill-blank
past one quarter of a board. All fixtures are hand-listed, offline, no model.
"""

from crossword.clue_genre import (
    GENRES,
    census_genres,
    observe_clue_genre,
)


def test_taxonomy_is_closed_and_ordered():
    assert GENRES == (
        "name-slot",
        "role-plus-name",
        "common-term",
        "x-e-g",
        "fill-blank",
        "quotational",
        "sound-or-action-cue",
        "abbreviation",
        "plain-definition",
    )


def test_anchored_name_shapes_are_name_slot():
    for clue in ["Famous singer's name", "Name of the singer", "Author's name, perhaps"]:
        assert observe_clue_genre(clue) == {"genre": "name-slot", "rule": "anchored-name-guard"}


def test_loose_name_shapes_are_name_slot():
    for clue in [
        "Name of the singer in a 1980s British band",
        "The name of a famous singer from the 1980s",
    ]:
        assert observe_clue_genre(clue) == {"genre": "name-slot", "rule": "loose-name-shape"}


def test_role_without_name_word_is_not_name_slot():
    assert observe_clue_genre("Singer's first big hit")["genre"] == "plain-definition"


def test_role_plus_capitalized_name():
    assert observe_clue_genre("Beatles drummer Ringo Starr")["genre"] == "role-plus-name"
    assert observe_clue_genre("Novelist Orwell's bleak future")["genre"] == "role-plus-name"


def test_common_term_templates():
    for clue in ["Common name", "A common name for a gas", "Usual synonym", "A thing"]:
        assert observe_clue_genre(clue)["genre"] == "common-term"


def test_xeg_fill_blank_quotational_sound_abbreviation():
    assert observe_clue_genre("Bird, e.g.")["genre"] == "x-e-g"
    assert observe_clue_genre("___ voyage")["genre"] == "fill-blank"
    assert observe_clue_genre("And so ...")["genre"] == "fill-blank"
    assert observe_clue_genre('"Hello"')["genre"] == "quotational"
    assert observe_clue_genre("[Loud sound]")["genre"] == "sound-or-action-cue"
    assert observe_clue_genre("A sudden loud noise")["genre"] == "sound-or-action-cue"
    assert observe_clue_genre("Doctor, briefly")["genre"] == "abbreviation"


def test_apostrophes_are_not_quotations():
    assert observe_clue_genre("Singer's first big hit")["genre"] == "plain-definition"
    assert observe_clue_genre("Don't stop")["genre"] == "plain-definition"


def test_plain_definitions_have_no_marker():
    assert observe_clue_genre("Without light")["genre"] == "plain-definition"
    assert observe_clue_genre("Yes in German")["genre"] == "plain-definition"


def test_name_slot_precedes_common_term():
    # A surface matching both reads as the more specific boring.
    assert observe_clue_genre("Common singer's name")["genre"] == "name-slot"


def test_census_counts_rates_and_totals():
    census = census_genres(
        [
            {"clue": "Famous singer's name"},
            {"clue": "Name of the singer in a 1980s British band"},
            {"clue": "___ voyage"},
            {"clue": "Without light"},
        ]
    )
    assert census["pairs"] == 4
    assert census["genreCounts"] == {"fill-blank": 1, "name-slot": 2, "plain-definition": 1}
    assert census["nameSlotCount"] == 2
    assert census["nameSlotRate"] == 0.5
    assert census["fillBlankRate"] == 0.25


def test_census_accepts_bare_surfaces_and_skips_garbage():
    census = census_genres(["___ voyage", None, 42, {"clue": "Without light"}])
    assert census["pairs"] == 2


def _entry(entry_id, answer="TESTA"):
    return {"id": entry_id, "answer": answer, "length": len(answer), "theme": False}


def test_name_slot_without_source_is_scaffolded():
    from crossword.private_puzzle_generation import _enforce_private_clue_safety

    entries = [_entry("1A", "ADELE")]
    clues = {"1A": "Name of the singer in a 1980s British band"}
    reasons = {}
    safe = _enforce_private_clue_safety(entries, clues, reviewed_by_id={}, fallback_reasons=reasons)
    assert safe["1A"].startswith("Entry supported by its crossings")
    # The factual-surface guard fires on the same source-free name claim;
    # the genre cap names the shape alongside it.
    assert reasons["1A"] == ["unsupported-factual-surface", "name-slot-without-source"]


def test_name_slot_with_source_backed_sense_is_kept():
    from crossword.private_puzzle_generation import _enforce_private_clue_safety

    entries = [_entry("1A", "ADELE")]
    clue = "Name of the singer in a 1980s British band"
    clues = {"1A": clue}
    reviewed = {"1A": {"text": clue, "senses": [{"gloss": "a singer"}]}}
    reasons = {}
    safe = _enforce_private_clue_safety(entries, clues, reviewed_by_id=reviewed, fallback_reasons=reasons)
    assert safe["1A"] == clue
    assert reasons == {}


def test_fill_blank_cap_keeps_first_quarter_in_entry_order():
    from crossword.private_puzzle_generation import _enforce_private_clue_safety

    entries = [_entry(f"{i}A", f"WORD{i}") for i in range(8)]
    clues = {f"{i}A": f"___ clue number {i}" for i in range(8)}
    reasons = {}
    safe = _enforce_private_clue_safety(entries, clues, reviewed_by_id={}, fallback_reasons=reasons)
    # Eight entries allow two fill-blanks; the rest are scaffolded.
    assert safe["0A"] == "___ clue number 0"
    assert safe["1A"] == "___ clue number 1"
    for i in range(2, 8):
        assert safe[f"{i}A"].startswith("Entry supported by its crossings")
        assert reasons[f"{i}A"] == ["fill-blank-over-cap"]


def test_reviewed_exact_fill_blank_is_exempt_from_cap():
    from crossword.private_puzzle_generation import _enforce_private_clue_safety

    entries = [_entry("1A", "BON"), _entry("2A", "VOY")]
    clues = {"1A": "___ voyage", "2A": "___ encore"}
    reviewed = {"1A": {"text": "___ voyage", "senses": [{"gloss": "a trip"}]}}
    reasons = {}
    safe = _enforce_private_clue_safety(entries, clues, reviewed_by_id=reviewed, fallback_reasons=reasons)
    # Two entries allow zero blanks, but the reviewed exact surface stands.
    assert safe["1A"] == "___ voyage"
    assert safe["2A"].startswith("Entry supported by its crossings")


def test_genre_cap_reasons_are_safe_mechanical_fallbacks():
    from crossword.clue_semantic_challenger import challenge_private_clue_pair

    for reason in ("name-slot-without-source", "fill-blank-over-cap"):
        verdict = challenge_private_clue_pair(
            {"answer": "ADELE"}, "Name of the singer", mechanical_issue=reason
        )
        assert verdict["classification"] == "safe-fallback"


def test_test_suite_never_writes_the_operator_corpus():
    import os
    from crossword.private_clue_corpus import corpus_path, CORPUS_FILENAME

    assert os.environ.get("CROSSWORD_CLUE_CORPUS_PATH", "") != ""
    assert str(corpus_path()).endswith("test-clue-corpus.local.json")
    assert CORPUS_FILENAME not in str(corpus_path())
