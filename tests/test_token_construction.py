import pytest

from tests.test_api_isolated import api, no_network  # noqa: F401
import src.crossword.private_puzzle_generation as private_generation
from src.crossword.token_construction import (
    NativeTokenConstructionRejected,
    construct_native_token_grid,
    emit_single_cell_language_tokens,
    native_token_hints,
    validate_native_token_cells,
)


def _grid(*, token_cells=None, cell_tokens=None):
    entries = [
        {
            "num": 1,
            "dir": "A",
            "row": 0,
            "col": 0,
            "len": 3,
            "answer": "CAT",
        },
        {
            "num": 1,
            "dir": "D",
            "row": 0,
            "col": 1,
            "len": 3,
            "answer": "AAA",
        },
    ]
    if cell_tokens is not None:
        entries[0]["cellTokens"] = list(cell_tokens[0])
        entries[1]["cellTokens"] = list(cell_tokens[1])
        entries[0]["answer"] = "".join(entries[0]["cellTokens"])
        entries[1]["answer"] = "".join(entries[1]["cellTokens"])
    fill = ["A" * 15 for _ in range(15)]
    return {"fill": fill, "entries": entries, **({"tokenCells": token_cells} if token_cells is not None else {})}


def _full_token_grid():
    fill = ["A" * 15 for _ in range(15)]
    entries = []
    for row in range(15):
        entry = {
            "num": 1 if row == 0 else 15 + row,
            "dir": "A",
            "row": row,
            "col": 0,
            "len": 15,
            "answer": "A" * 15,
        }
        if row == 0:
            entry["cellTokens"] = ["A", "SS", *(["A"] * 13)]
            entry["answer"] = "".join(entry["cellTokens"])
        entries.append(entry)
    for column in range(15):
        entry = {
            "num": column + 1,
            "dir": "D",
            "row": 0,
            "col": column,
            "len": 15,
            "answer": "A" * 15,
        }
        if column == 1:
            entry["cellTokens"] = ["SS", *(["A"] * 14)]
            entry["answer"] = "".join(entry["cellTokens"])
        entries.append(entry)
    return {
        "fill": fill,
        "entries": entries,
        "tokenCells": [
            {
                "row": 0,
                "column": 1,
                "displayToken": "ß",
                "fillToken": "SS",
                "source": "native-constructor-v1",
            }
        ],
    }


def test_language_hint_emits_one_cell_token_but_rejects_multi_unit_expansion():
    grid = {
        "fill": ["A" * 15 for _ in range(15)],
        "entries": [
            {"num": 1, "dir": "A", "row": 0, "col": 0, "len": 4, "answer": "CAFE"},
            *[
                {"num": index + 1, "dir": "D", "row": 0, "col": index, "len": 1, "answer": letter}
                for index, letter in enumerate("CAFE")
            ],
        ],
    }

    emitted = emit_single_cell_language_tokens(
        grid,
        [{"entryId": "across-1", "cellIndex": 3, "displayToken": "É"}],
        language="French",
        source="synthetic-unadmitted",
    )

    assert emitted == [
        {
            "row": 0,
            "column": 3,
            "displayToken": "É",
            "fillToken": "E",
            "source": "private-language-decorator-v1",
        }
    ]
    assert (
        emit_single_cell_language_tokens(
            grid,
            [{"entryId": "across-1", "cellIndex": 3, "displayToken": "ß"}],
            language="German",
            source="synthetic-unadmitted",
        )
        == []
    )


def test_missing_native_token_envelope_is_explicitly_ordinary():
    assert validate_native_token_cells(_grid()) == {
        "version": "native-token-construction-v1",
        "status": "absent",
        "cells": [],
        "reasons": [],
    }


def test_accepts_one_cell_display_alias_and_projects_crossing_hints():
    grid = _grid(
        token_cells=[
            {
                "row": 0,
                "column": 1,
                "displayToken": "É",
                "fillToken": "A",
                "source": "reviewed-admitted-v1",
            }
        ]
    )

    report = validate_native_token_cells(grid)

    assert report["status"] == "accepted"
    assert report["cells"][0]["id"] == "r0c1"
    assert native_token_hints(grid) == [
        {"entryId": "across-1", "cellIndex": 1, "displayToken": "É"},
        {"entryId": "down-1", "cellIndex": 0, "displayToken": "É"},
    ]


def test_accepts_multi_unit_token_only_with_explicit_entry_sequences():
    grid = _grid(
        token_cells=[
            {
                "row": 0,
                "column": 1,
                "displayToken": "ß",
                "fillToken": "SS",
                "source": "native-constructor-v1",
            }
        ],
        cell_tokens=(("C", "SS", "T"), ("SS", "A", "A")),
    )

    report = validate_native_token_cells(grid)

    assert report["status"] == "accepted"
    assert report["cells"][0]["fillToken"] == "SS"


def test_token_aware_constructor_expands_explicit_crossings():
    grid = {
        "fill": ["CST" + "A" * 12, "A" * 15, "A" * 15, *(["A" * 15] * 12)],
        "entries": [
            {"num": 1, "dir": "A", "row": 0, "col": 0, "len": 3, "answer": "CST"},
            {"num": 1, "dir": "D", "row": 0, "col": 1, "len": 3, "answer": "SAA"},
        ],
        "tokenCells": [
            {
                "row": 0,
                "column": 1,
                "displayToken": "ß",
                "fillToken": "SS",
                "source": "native-constructor-v1",
            }
        ],
    }

    constructed = construct_native_token_grid(grid)

    assert constructed["entries"][0]["cellTokens"] == ["C", "SS", "T"]
    assert constructed["entries"][1]["cellTokens"] == ["SS", "A", "A"]
    assert constructed["entries"][0]["answer"] == "CSST"
    assert validate_native_token_cells(constructed)["status"] == "accepted"


def test_rejects_multi_unit_token_without_native_entry_sequences():
    grid = _grid(
        token_cells=[
            {
                "row": 0,
                "column": 1,
                "displayToken": "ß",
                "fillToken": "SS",
                "source": "native-constructor-v1",
            }
        ]
    )

    with pytest.raises(NativeTokenConstructionRejected, match="sequence"):
        validate_native_token_cells(grid)


def test_rejects_crossing_sequence_mismatch():
    grid = _grid(
        token_cells=[
            {
                "row": 0,
                "column": 1,
                "displayToken": "ß",
                "fillToken": "SS",
                "source": "native-constructor-v1",
            }
        ],
        cell_tokens=(("C", "SS", "T"), ("S", "A", "A")),
    )

    with pytest.raises(NativeTokenConstructionRejected, match="crossing"):
        validate_native_token_cells(grid)


def test_private_solver_projection_keeps_canonical_multi_unit_cell(monkeypatch):
    grid = _grid(
        token_cells=[
            {
                "row": 0,
                "column": 1,
                "displayToken": "ß",
                "fillToken": "SS",
                "source": "native-constructor-v1",
            }
        ],
        cell_tokens=(("C", "SS", "T"), ("SS", "A", "A")),
    )
    monkeypatch.setattr(
        private_generation,
        "register_legacy_puzzle",
        lambda crossword, **_kwargs: {"registered": True},
    )

    crossword, manifest = private_generation._legacy_puzzle(
        grid,
        [],
        "Native token fixture",
        {"1A": "Across", "1D": "Down"},
        "local-model",
        "wednesday",
        7,
    )

    assert manifest == {"registered": True}
    assert crossword.entries[0].characters[1].letters == "SS"
    assert crossword.entries[1].characters[0].letters == "SS"
    assert crossword.entries[0].answer_text == "CSST"
    assert crossword.entries[0].length == 3


def test_private_token_projection_registers_a_replayable_manifest(api):
    grid = _full_token_grid()

    with api.app.app_context():
        crossword, manifest = private_generation._legacy_puzzle(
            grid,
            [],
            "Native token fixture",
            {
                f"{entry['num']}{entry['dir']}": "Token"
                for entry in grid["entries"]
            },
            "local-model",
            "wednesday",
            7,
        )

    assert crossword.entries[0].characters[1].letters == "SS"
    assert manifest["entries"][0]["answerTokens"][1] == "SS"
