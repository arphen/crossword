"""Tests for witness-based clue family admission (Q04).

A claimed family comes from punctuation; a witnessed family needs the
witness the family requires. A trailing ``?`` alone is ``pseudo-pun``,
never ``pun``. Where no witness exists the witnessed family is
``definition`` and says so. All fixtures are hand-listed English, offline,
no model.
"""

from crossword.clue_witness import (
    HOMOGRAPH_LEDGER,
    SENSE_SOURCE_ID,
    ledger_senses,
    witness_clue_family,
    witness_factual_relation,
    witness_fill_blank,
    witness_hidden_word_span,
    witness_metalinguistic,
    witness_nonverbal_expression,
    witness_pun,
    witness_spoken_equivalent,
)


def test_ledger_lists_distinct_senses_per_pivot():
    assert len(HOMOGRAPH_LEDGER) >= 40
    pivots = [pivot for pivot, _, _ in HOMOGRAPH_LEDGER]
    assert len(set(pivots)) == len(pivots)
    for pivot, sense_a, sense_b in HOMOGRAPH_LEDGER:
        assert pivot == pivot.upper() and len(pivot) >= 3
        assert sense_a and sense_b and sense_a != sense_b


def test_ledger_lookup_is_case_insensitive():
    senses = ledger_senses("lot")
    assert senses is not None and len(senses) == 2
    assert ledger_senses("NOTAPIVOT") is None
    assert ledger_senses(None) is None


def test_pun_needs_question_mark_pivot_and_other_answer():
    verdict = witness_pun("One with a lot to say?", "AUCTIONEER")
    assert verdict == {
        "witnessed": True,
        "family": "pun",
        "pivot": "LOT",
        "senses": list(ledger_senses("LOT")),
        "senseSource": SENSE_SOURCE_ID,
    }


def test_pun_pivot_match_is_case_insensitive():
    assert witness_pun("Branch SPECIALIST?", "TELLER")["family"] == "pun"


def test_bare_question_mark_is_pseudo_pun_never_pun():
    for clue, answer in [
        ("Suspicious character?", "SHADIER"),
        ("A quiet room?", "DEN"),
        ("More shady?", "SHADIER"),
    ]:
        verdict = witness_pun(clue, answer)
        assert verdict["witnessed"] is False
        assert verdict["family"] == "pseudo-pun"


def test_pun_pivot_that_is_the_answer_is_refused():
    verdict = witness_pun("A sale item, reportedly?", "LOT")
    assert verdict["witnessed"] is False
    assert verdict["family"] == "pseudo-pun"


def test_no_question_mark_is_not_a_pun_claim():
    assert witness_pun("Suspicious-looking", "SHADY")["family"] == "definition"


def test_fill_blank_witness_is_the_marked_blank():
    verdict = witness_fill_blank( "___ voyage")
    assert verdict["witnessed"] is True
    assert verdict["family"] == "fill-blank"
    assert verdict["span"] == {"start": 0, "end": 3}
    assert witness_fill_blank("Without light")["family"] == "definition"


def test_spoken_equivalent_needs_utterance_and_label():
    labeled = witness_spoken_equivalent('"Hello there" (Spoken equivalent)')
    assert labeled["witnessed"] is True
    assert labeled["family"] == "spoken-equivalent"
    assert labeled["utterance"] == "Hello there"
    unlabeled = witness_spoken_equivalent('"To be or not to be"')
    assert unlabeled["witnessed"] is False
    assert unlabeled["family"] == "definition"
    assert unlabeled["reason"] == "utterance-without-label"


def test_nonverbal_witness_is_the_bracket_span():
    verdict = witness_nonverbal_expression("[Sound heard nearby]")
    assert verdict["witnessed"] is True
    assert verdict["family"] == "nonverbal-expression"
    assert witness_nonverbal_expression("Loud sound")["family"] == "definition"


def test_metalinguistic_witness_is_the_abbreviation_indicator():
    verdict = witness_metalinguistic("Doctor, briefly")
    assert verdict["witnessed"] is True
    assert verdict["family"] == "metalinguistic"
    assert witness_metalinguistic("Doctor")["family"] == "definition"


def test_factual_relation_witness_is_the_language_indicator():
    verdict = witness_factual_relation("Yes in German")
    assert verdict["witnessed"] is True
    assert verdict["family"] == "factual-relation"
    assert verdict["language"] == "german"
    assert witness_factual_relation("Without light")["family"] == "definition"


def test_factual_relation_accepts_caller_attested_pattern():
    verdict = witness_factual_relation("Some surface", relation_pattern_matched=True)
    assert verdict["witnessed"] is True
    assert verdict["family"] == "factual-relation"


def test_hidden_word_needs_cue_and_span():
    probe = witness_hidden_word_span('Found inside "cabin door"')
    assert probe["witnessed"] is True
    assert probe["source"] == "cabin door"
    assert witness_hidden_word_span("Without light")["witnessed"] is False
    assert witness_hidden_word_span('"cabin door"')["witnessed"] is False


def test_dispatch_returns_exactly_one_witnessed_family():
    verdict = witness_clue_family("pun", "One with a lot to say?", "AUCTIONEER")
    assert verdict == {
        "claimed": "pun",
        "witnessed": True,
        "family": "pun",
        "witness": {
            "pivot": "LOT",
            "senses": list(ledger_senses("LOT")),
            "senseSource": SENSE_SOURCE_ID,
        },
        "senseSource": SENSE_SOURCE_ID,
    }
    bare = witness_clue_family("pun", "A quiet room?", "DEN")
    assert bare["witnessed"] is False and bare["family"] == "pseudo-pun"
    assert bare["senseSource"] is None
    assert witness_clue_family("definition", "Without light")["family"] == "definition"
    assert witness_clue_family("unknown-family", "Without light")["family"] == "definition"


def test_observation_carries_claimed_and_witnessed_families():
    from crossword.private_puzzle_generation import _clue_family_observation

    observed = _clue_family_observation("Branch specialist?", "TELLER")
    assert observed["family"] == "pun"
    assert observed["witnessedFamily"] == "pun"
    assert observed["senseSource"] == SENSE_SOURCE_ID
    assert observed["confidence"] == "surface-signal-only"

    bare = _clue_family_observation("A quiet room?", "DEN")
    assert bare["family"] == "pun"
    assert bare["witnessedFamily"] == "pseudo-pun"

    unlabeled = _clue_family_observation('"To be or not to be"', "HAMLET")
    assert unlabeled["family"] == "spoken-equivalent"
    assert unlabeled["witnessedFamily"] == "definition"


def test_diversity_report_splits_claimed_and_witnessed():
    from crossword.private_puzzle_generation import _clue_diversity_report

    entries = [{"id": f"E{i}"} for i in range(4)]
    clues = {
        "E0": "Branch specialist?",
        "E1": "A quiet room?",
        "E2": "___ voyage",
        "E3": "Without light",
    }
    report = _clue_diversity_report(entries, clues)
    assert report["familyCountsClaimed"] == {
        "definition": 1,
        "fill-blank": 1,
        "pun": 2,
    }
    assert report["familyCountsWitnessed"] == {
        "definition": 1,
        "fill-blank": 1,
        "pseudo-pun": 1,
        "pun": 1,
    }
    assert report["witnessGap"] == {"pun": 1, "pseudo-pun": -1}
    # Floors stay on claimed counts: measurement never gates play.
    assert report["familyCounts"] == report["familyCountsClaimed"]


def test_bridge_reports_witness_without_changing_validity():
    from crossword.clue_grammar_bridge import validate_surface_clue_family
    from crossword.private_puzzle_generation import _clue_family_observation

    bare = validate_surface_clue_family(
        "A quiet room?", _clue_family_observation("A quiet room?", "DEN")
    )
    assert bare["valid"] is True
    assert bare["witness"]["family"] == "pseudo-pun"

    good = validate_surface_clue_family(
        "Branch specialist?", _clue_family_observation("Branch specialist?", "TELLER")
    )
    assert good["valid"] is True
    assert good["witness"]["family"] == "pun"


def test_evaluation_aggregates_witnessed_counts_and_gap():
    from crossword.clue_quality_evaluation import evaluate_clue_quality_study

    def case(seed, claimed, witnessed):
        return {
            "seed": seed,
            "entryCount": sum(claimed.values()),
            "grammarCheckedCount": sum(claimed.values()),
            "grammarIssueCount": 0,
            "fallbackCount": 0,
            "familyCounts": claimed,
            "familyCountsWitnessed": witnessed,
            "nonDefinitionCount": sum(v for k, v in claimed.items() if k != "definition"),
            "nonDefinitionFamilies": sorted(k for k in claimed if k != "definition"),
            "floorMet": True,
        }

    report = evaluate_clue_quality_study(
        [
            case(1, {"definition": 2, "pun": 2}, {"definition": 2, "pseudo-pun": 1, "pun": 1}),
            case(2, {"definition": 3, "pun": 1}, None),
        ],
        study_id="witness-fixture",
    )
    summary = report["summary"]
    assert summary["familyCountsWitnessed"] == {"definition": 2, "pseudo-pun": 1, "pun": 1}
    assert summary["witnessedCases"] == 1
    # The gap spans every family: witnessed counts exist for one case only,
    # so definition shows the unscored remainder rather than hiding it.
    assert summary["witnessGap"] == {"definition": 3, "pseudo-pun": -1, "pun": 2}


def test_evaluation_tolerates_receipts_without_witnessed_counts():
    from crossword.clue_quality_evaluation import evaluate_clue_quality_study

    report = evaluate_clue_quality_study(
        [
            {
                "seed": 1,
                "entryCount": 2,
                "grammarCheckedCount": 2,
                "grammarIssueCount": 0,
                "fallbackCount": 0,
                "familyCounts": {"definition": 1, "pun": 1},
                "nonDefinitionCount": 1,
                "nonDefinitionFamilies": ["pun"],
                "floorMet": True,
            }
        ],
        study_id="legacy-fixture",
    )
    assert report["summary"]["familyCountsWitnessed"] is None
    assert report["summary"]["witnessGap"] is None
