"""Tests for the local answer-bearing clue corpus (Q03).

The corpus gives every later guard and scorer a denominator: one record per
generated surface with the answer and the deterministic guard outcome. Records
stay on this host (``*.local.json``, gitignored); only counts plus a digest
are committed. All tests are synthetic and offline.
"""

import json

import pytest

from crossword.private_clue_corpus import (
    CORPUS_VERSION,
    append_corpus_records,
    build_corpus_records,
    corpus_counts_attestation,
    corpus_path,
    load_corpus,
    reresolve_counters,
)


def _entries():
    return [
        {"id": "2D", "answer": "NOISIER", "theme": False, "cluePolicy": "ordinary-definition-or-signalled-wordplay"},
        {"id": "1A", "answer": "SHADIER", "theme": True, "cluePolicy": "ordinary-definition-or-signalled-wordplay"},
        {"not": "an entry"},
        {"id": "", "answer": "EMPTY"},
    ]


def _clues():
    return {"1A": "more shady", "2D": "loud room"}


def test_records_carry_answer_guard_outcome_and_provenance():
    records = build_corpus_records(
        _entries(),
        _clues(),
        weekday="tuesday",
        seed=20470420,
        model_tag="gemma4:26b",
        issues_by_id={"1A": ["tautological-degree-form"]},
        fallback_ids=[],
        reviewed_ids=["2D"],
        challenge_by_id={"1A": "safe-fallback", "2D": {"not": "a string"}},
    )
    assert [item["id"] for item in records] == ["1A", "2D"]
    first = records[0]
    assert first["answer"] == "SHADIER"
    assert first["clue"] == "more shady"
    assert first["weekday"] == "tuesday"
    assert first["seed"] == 20470420
    assert first["modelTag"] == "gemma4:26b"
    assert first["theme"] is True
    assert first["issues"] == ["tautological-degree-form"]
    assert first["fallback"] is False
    assert first["reviewed"] is False
    assert first["challenge"] == "safe-fallback"
    second = records[1]
    assert second["issues"] == []
    assert second["reviewed"] is True
    assert second["challenge"] is None


def test_append_and_load_round_trip_in_tmp(tmp_path):
    target = tmp_path / "corpus.local.json"
    assert load_corpus(target)["captured"] is False
    first = append_corpus_records(
        build_corpus_records(_entries(), _clues(), weekday="wednesday", seed=7, model_tag="llama3.2:3b"),
        target,
    )
    assert first["appended"] == 2
    assert first["totalPairs"] == 2
    assert first["digest"].startswith("sha256-")
    second = append_corpus_records(
        build_corpus_records(_entries(), _clues(), weekday="wednesday", seed=8, model_tag="llama3.2:3b"),
        target,
    )
    assert second["totalPairs"] == 4
    assert second["digest"] != first["digest"]
    loaded = load_corpus(target)
    assert loaded["captured"] is True
    assert len(loaded["records"]) == 4


def test_corrupt_corpus_fails_open_and_recovers(tmp_path):
    target = tmp_path / "corpus.local.json"
    target.write_text("{not json", encoding="utf-8")
    assert load_corpus(target)["captured"] is False
    receipt = append_corpus_records(
        build_corpus_records(_entries(), _clues(), weekday="wednesday", seed=7, model_tag="x"),
        target,
    )
    assert receipt["appended"] == 2
    assert receipt["totalPairs"] == 2
    assert load_corpus(target)["captured"] is True


def test_env_override_selects_corpus_path(tmp_path, monkeypatch):
    target = tmp_path / "override.local.json"
    monkeypatch.setenv("CROSSWORD_CLUE_CORPUS_PATH", str(target))
    assert corpus_path() == target


def test_attestation_is_counts_plus_digest_only(tmp_path, monkeypatch):
    target = tmp_path / "corpus.local.json"
    monkeypatch.setenv("CROSSWORD_CLUE_CORPUS_PATH", str(target))
    empty = corpus_counts_attestation()
    assert empty["captured"] is False
    assert empty["digest"] is None
    append_corpus_records(
        build_corpus_records(_entries(), _clues(), weekday="tuesday", seed=1, model_tag="m"),
    )
    attestation = corpus_counts_attestation()
    assert attestation["version"] == CORPUS_VERSION
    assert attestation["captured"] is True
    assert attestation["pairs"] == 2
    assert attestation["digest"].startswith("sha256-")
    assert attestation["weeks"] == ["tuesday"]
    assert attestation["models"] == ["m"]
    serialised = json.dumps(attestation, sort_keys=True)
    assert "more shady" not in serialised
    assert "SHADIER" not in serialised


def test_reresolve_sums_counters_and_names_fill_blank_peak():
    receipt = reresolve_counters(
        [
            ("v5.json", "sha256-aaa", {"entryCount": 74, "familyCounts": {"definition": 8, "fill-blank": 57, "pun": 9}}),
            ("v1.json", "sha256-bbb", {"entryCount": 78, "familyCounts": {"definition": 58, "fill-blank": 14, "pun": 2}, "signalCounts": {"question-mark": 2}}),
            ("study.json", "sha256-ddd", {"cases": [{"seed": 1, "entryCount": 72, "familyCounts": {"definition": 4, "fill-blank": 21, "pun": 19}}], "summary": {"entryCount": 72, "familyCounts": {"definition": 4, "fill-blank": 21, "pun": 19}}}),
            ("notes.json", "sha256-ccc", {"interpretation": "prose only"}),
        ]
    )
    assert receipt["version"] == "private-clue-counter-reresolution-v1"
    assert receipt["familyTotals"] == {"definition": 70, "fill-blank": 92, "pun": 30}
    assert receipt["signalTotals"] == {"question-mark": 2}
    assert receipt["maxFillBlankShare"]["name"] == "v5.json#top"
    assert receipt["maxFillBlankShare"]["fillBlank"] == 57
    assert receipt["files"][3]["note"].startswith("no familyCounts")


def test_reresolve_rejects_nothing_and_counts_nothing_without_counters():
    receipt = reresolve_counters([])
    assert receipt["familyTotals"] == {}
    assert receipt["maxFillBlankShare"] is None


def test_generation_wires_corpus_capture_and_provenance():
    """The generation path must keep every surface and report counts only."""
    import crossword.private_puzzle_generation as generation
    from pathlib import Path

    assert callable(generation.build_corpus_records)
    assert callable(generation.append_corpus_records)
    source = Path(generation.__file__).read_text(encoding="utf-8")
    assert "build_corpus_records(" in source
    assert '"clueCorpus": clue_corpus_receipt' in source
