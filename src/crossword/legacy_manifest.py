"""Convert the parsed legacy crossword model into a replayable domain manifest.

The old model has no explicit grid: its entries are the source of truth for cell
occupancy. This adapter therefore only publishes a manifest when those entries
describe a complete, internally consistent crossword topology. Ordinary
callers deliberately reject rebus cells; the private future lane can opt into
explicit per-cell token sequences, stored as ``answerTokens`` for replay
without widening the public single-letter document contract.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any


_DIRECTIONS = ("across", "down")
_SINGLE_LETTER = re.compile(r"^[A-Z]$")
MAX_GRID_DIMENSION = 50
MAX_GRID_CELL_COUNT = 500


def _canonical_json(value: Any) -> str:
    """Serialize using the stable UTF-8 JSON contract shared by the browser."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _as_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, Mapping):
            return dumped
    raise ValueError(f"{label} must be a mapping or Pydantic model")


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _coordinate(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _character(
    value: Any, *, entry_index: int, cell_index: int, allow_token_cells: bool = False
) -> tuple[str, bool, bool]:
    character = _as_mapping(value, f"entry {entry_index} character {cell_index}")
    letters = character.get("letters")
    if not isinstance(letters, str):
        raise ValueError(f"entry {entry_index} character {cell_index} has invalid letters")
    answer = letters.upper()
    if allow_token_cells:
        if not re.fullmatch(r"[A-Z]{1,8}", answer):
            raise ValueError(
                f"entry {entry_index} character {cell_index} has invalid token letters"
            )
    elif not _SINGLE_LETTER.fullmatch(answer):
        raise ValueError(
            f"entry {entry_index} character {cell_index} is not a single A-Z "
            "cell; rebus and other cells are unsupported"
        )
    if character.get("is_rebus") is True and not allow_token_cells:
        raise ValueError(f"entry {entry_index} character {cell_index} is a rebus cell")
    circled = character.get("is_circled", False)
    shaded = character.get("is_shaded", False)
    if not isinstance(circled, bool) or not isinstance(shaded, bool):
        raise ValueError(f"entry {entry_index} character {cell_index} has invalid cell styling")
    return answer, circled, shaded


def to_puzzle_document(
    crossword: Any, *, allow_token_cells: bool = False
) -> dict[str, Any]:
    """Build a deterministic domain ``PuzzleDocument`` from a legacy crossword.

    ``crossword`` may be a ``Crossword`` Pydantic object or its ``model_dump``
    mapping. Cell IDs are coordinate-derived; entry IDs are direction/number-
    derived. All white cells must belong to exactly one answer in each direction,
    crossings must agree, and supplied clue numbering must match grid order.
    """
    root = _as_mapping(crossword, "crossword")
    metadata = _as_mapping(root.get("metadata"), "metadata")
    date = _required_text(metadata.get("date"), "metadata.date")
    title = _required_text(metadata.get("title"), "metadata.title")
    width = metadata.get("width")
    height = metadata.get("height")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 1
        for value in (width, height)
    ):
        raise ValueError("metadata dimensions must be positive integers")
    if width > MAX_GRID_DIMENSION or height > MAX_GRID_DIMENSION:
        raise ValueError("metadata dimensions exceed the legacy manifest limit")
    if width * height > MAX_GRID_CELL_COUNT:
        raise ValueError("metadata grid exceeds the legacy manifest cell limit")

    authors_value = metadata.get("authors", [])
    if not isinstance(authors_value, list) or any(
        not isinstance(author, str) for author in authors_value
    ):
        raise ValueError("metadata.authors must be a list of strings")
    authors = [author.strip() for author in authors_value if author.strip()]
    notepad = metadata.get("notepad")
    if notepad is not None and not isinstance(notepad, str):
        raise ValueError("metadata.notepad must be a string or null")
    subtitle = (
        notepad.strip()
        if isinstance(notepad, str) and notepad.strip()
        else (f"By {' / '.join(authors)}" if authors else "Imported crossword")
    )

    source_entries = root.get("entries")
    if not isinstance(source_entries, list) or not source_entries:
        raise ValueError("crossword.entries must be a non-empty list")
    if len(source_entries) > MAX_GRID_CELL_COUNT * len(_DIRECTIONS):
        raise ValueError("crossword.entries exceeds the legacy manifest entry limit")

    # First capture each entry and its occupied cells. This grid is derived only
    # from actual entry cells; there is no inferred answer or repaired topology.
    entries: list[dict[str, Any]] = []
    occupied: dict[tuple[int, int], dict[str, Any]] = {}
    seen_direction_numbers: set[tuple[str, int]] = set()
    starts: dict[tuple[int, int], int] = {}
    normalized_source_entries: list[dict[str, Any]] = []

    for entry_index, raw_entry in enumerate(source_entries):
        entry = _as_mapping(raw_entry, f"entry {entry_index}")
        direction = entry.get("direction")
        if direction not in _DIRECTIONS:
            raise ValueError(f"entry {entry_index} has unsupported direction")
        number = entry.get("clue_number")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise ValueError(f"entry {entry_index} has invalid clue_number")
        number_key = (direction, number)
        if number_key in seen_direction_numbers:
            raise ValueError(f"duplicate {direction} clue number {number}")
        seen_direction_numbers.add(number_key)
        clue = _required_text(entry.get("clue_text"), f"entry {entry_index}.clue_text")
        start_x = _coordinate(entry.get("start_x"), f"entry {entry_index}.start_x")
        start_y = _coordinate(entry.get("start_y"), f"entry {entry_index}.start_y")
        raw_characters = entry.get("characters")
        if not isinstance(raw_characters, list) or not raw_characters:
            raise ValueError(f"entry {entry_index}.characters must be a non-empty list")
        max_entry_length = width if direction == "across" else height
        if len(raw_characters) > max_entry_length:
            raise ValueError(f"entry {entry_index} extends outside metadata dimensions")

        parsed_characters = [
            _character(
                character,
                entry_index=entry_index,
                cell_index=cell_index,
                allow_token_cells=allow_token_cells,
            )
            for cell_index, character in enumerate(raw_characters)
        ]
        coordinates: list[tuple[int, int]] = []
        for offset, (answer, circled, shaded) in enumerate(parsed_characters):
            row = start_y + (offset if direction == "down" else 0)
            column = start_x + (offset if direction == "across" else 0)
            if row >= height or column >= width:
                raise ValueError(f"entry {entry_index} extends outside metadata dimensions")
            coordinate = (row, column)
            coordinates.append(coordinate)
            cell = occupied.setdefault(
                coordinate, {"letters": {}, "circled": False, "shaded": False}
            )
            if direction in cell["letters"]:
                raise ValueError(f"two {direction} entries occupy cell {row}:{column}")
            cell["letters"][direction] = answer
            # Styling belongs to the cell; one direction cannot silently
            # overwrite a different crossing's styling.
            if cell["letters"] and len(cell["letters"]) > 1:
                if cell["circled"] != circled or cell["shaded"] != shaded:
                    raise ValueError(f"crossing styling disagrees at cell {row}:{column}")
            else:
                cell["circled"] = circled
                cell["shaded"] = shaded

        start = (start_y, start_x)
        previous_number = starts.setdefault(start, number)
        if previous_number != number:
            raise ValueError(
                f"entries beginning at cell {start_y}:{start_x} disagree on clue number"
            )
        answer_tokens = [character[0] for character in parsed_characters]
        answer = "".join(answer_tokens)
        entry_record = {
            "id": f"{direction}-{number}",
            "number": number,
            "direction": direction,
            "cellIds": [f"r{row}c{column}" for row, column in coordinates],
            "answer": answer,
            "clue": clue,
            "_coordinates": coordinates,
        }
        if allow_token_cells and any(len(token) > 1 for token in answer_tokens):
            entry_record["answerTokens"] = answer_tokens
        entries.append(entry_record)
        normalized_source_entries.append({
            "clue_number": number,
            "clue_text": clue,
            "direction": direction,
            "start_x": start_x,
            "start_y": start_y,
            "characters": [
                {"letters": letter, "is_circled": circled, "is_shaded": shaded}
                for letter, circled, shaded in parsed_characters
            ],
        })

    if not occupied:
        raise ValueError("crossword contains no open cells")

    # A cell's two clue representations must encode the same character and each
    # open cell must be fully represented in both directions.
    for (row, column), cell in occupied.items():
        if set(cell["letters"]) != set(_DIRECTIONS):
            raise ValueError(f"open cell {row}:{column} lacks an across or down entry")
        if cell["letters"]["across"] != cell["letters"]["down"]:
            raise ValueError(f"crossing answers disagree at cell {row}:{column}")

    ordered_starts = sorted(starts)
    expected_numbers = {coordinate: index + 1 for index, coordinate in enumerate(ordered_starts)}
    if any(starts[coordinate] != expected_numbers[coordinate] for coordinate in ordered_starts):
        raise ValueError("clue numbers do not match row-major crossword numbering")

    # Treat unoccupied positions as blocks, then reject any entry that fails to
    # cover its entire contiguous run in its direction.
    for entry in entries:
        coordinates = entry.pop("_coordinates")
        first_row, first_column = coordinates[0]
        last_row, last_column = coordinates[-1]
        if entry["direction"] == "across":
            before = (first_row, first_column - 1)
            after = (last_row, last_column + 1)
        else:
            before = (first_row - 1, first_column)
            after = (last_row + 1, last_column)
        if before in occupied or after in occupied:
            raise ValueError(
                f"{entry['direction']} entry {entry['number']} "
                "does not cover its complete run"
            )

    cells: list[dict[str, Any]] = []
    blocked_cell_ids: list[str] = []
    for row in range(height):
        for column in range(width):
            cell_id = f"r{row}c{column}"
            open_cell = occupied.get((row, column))
            if open_cell is None:
                blocked_cell_ids.append(cell_id)
                cells.append({
                    "id": cell_id,
                    "row": row,
                    "column": column,
                    "block": True,
                    "circled": False,
                    "shaded": False,
                })
            else:
                cells.append({
                    "id": cell_id,
                    "row": row,
                    "column": column,
                    "block": False,
                    "circled": open_cell["circled"],
                    "shaded": open_cell["shaded"],
                })

    entries.sort(key=lambda entry: (entry["number"], 0 if entry["direction"] == "across" else 1))
    clues = [
        {
            "entryId": entry["id"],
                "variants": [
                    {
                        "mechanism": "standard",
                        "text": entry["clue"],
                        "difficulty": 0.5,
                    }
                ],
        }
        for entry in entries
    ]
    normalized_source_entries.sort(
        key=lambda entry: (
            entry["start_y"],
            entry["start_x"],
            0 if entry["direction"] == "across" else 1,
            entry["clue_number"],
        )
    )
    imported = {
        "metadata": {
            "date": date,
            "title": title,
            "authors": authors,
            "width": width,
            "height": height,
            "notepad": notepad,
        },
        "entries": normalized_source_entries,
    }
    source_digest = _digest(imported)
    puzzle_id = f"legacy-{source_digest[:32]}"
    document: dict[str, Any] = {
        "schemaVersion": 1,
        "id": puzzle_id,
        "seed": source_digest,
        "title": title,
        "subtitle": subtitle,
        "width": width,
        "height": height,
        "cells": cells,
        "entries": entries,
        "clues": clues,
        "provenance": {
            "source": "import",
            "recipeId": "legacy-crossword-import-v1",
            # Legacy exports do not carry source/license records. An empty list
            # preserves that uncertainty instead of inventing provenance.
            "records": [],
        },
        "generation": {
            "modelId": "legacy-parser",
            "promptVersion": "not-applicable",
            "lexiconVersion": "not-recorded",
            "solverVersion": "legacy-manifest-v1",
            "generatedAt": "unknown",
            "restartCount": 0,
        },
        "quality": {
            "score": 1,
            "thresholds": {"structuralIntegrity": 1},
            "validators": ["legacy-topology", "crossing-consistency", "clue-numbering"],
        },
        "topology": {
            "width": width,
            "height": height,
            "blockedCellIds": blocked_cell_ids,
            "minEntryLength": 1,
        },
        "createdBy": "import",
    }
    document["integrity"] = {"algorithm": "sha256", "value": _digest(document)}
    return document


def verify_integrity(document: Mapping[str, Any]) -> bool:
    """Return whether a manifest carries its canonical SHA-256 body digest."""
    integrity = document.get("integrity")
    if not isinstance(integrity, Mapping) or integrity.get("algorithm") != "sha256":
        return False
    body = {key: value for key, value in document.items() if key != "integrity"}
    try:
        return integrity.get("value") == _digest(body)
    except (TypeError, ValueError):
        return False
