"""Validate optional native token cells for the private puzzle lane.

The pinned xfill runtime still emits an ordinary ASCII grid.  A later native
constructor may emit a ``tokenCells`` sidecar for a language or rebus cell,
where one geometric cell carries an explicit display token and a canonical
fill sequence (for example ``ß`` / ``SS``).  A token-aware entry may therefore
carry a lexical ``answer`` plus an explicit ``cellTokens`` sequence whose
concatenation is that answer. This module keeps that extension strict and
local: it never folds accents, infers a token from an answer, or changes the
ordinary grid geometry.
"""

from __future__ import annotations

from collections import defaultdict
import unicodedata
from typing import Any, Mapping

from .language_task_pack import single_cell_fill_token


TOKEN_CONSTRUCTION_VERSION = "native-token-construction-v1"
_DIRECTIONS = {"A": "across", "D": "down"}


class NativeTokenConstructionRejected(ValueError):
    """The optional native token envelope is malformed or inconsistent."""


def _entry_id(raw: Mapping[str, Any]) -> str:
    return f"{raw.get('num')}{raw.get('dir')}"


def _entry_cells(raw: Mapping[str, Any]) -> tuple[tuple[int, int], ...]:
    row, column, length, direction = (
        raw.get("row"), raw.get("col"), raw.get("len"), raw.get("dir")
    )
    if (
        type(row) is not int
        or type(column) is not int
        or type(length) is not int
        or length < 1
        or row < 0
        or column < 0
        or direction not in _DIRECTIONS
    ):
        raise NativeTokenConstructionRejected("native-token-entry-geometry-invalid")
    if direction == "A":
        return tuple((row, column + index) for index in range(length))
    return tuple((row + index, column) for index in range(length))


def _bounded_text(value: Any, *, maximum: int) -> str:
    if not isinstance(value, str) or not value:
        raise NativeTokenConstructionRejected("native-token-text-invalid")
    normalized = unicodedata.normalize("NFC", value)
    if len(normalized) > maximum or any(character.isspace() or ord(character) < 32 for character in normalized):
        raise NativeTokenConstructionRejected("native-token-text-invalid")
    return normalized


def _grid_dimensions(grid: Mapping[str, Any]) -> tuple[int, int]:
    fill = grid.get("fill")
    if not isinstance(fill, list) or not fill or any(not isinstance(row, str) for row in fill):
        raise NativeTokenConstructionRejected("native-token-grid-invalid")
    size = len(fill)
    if size not in {15, 21} or any(len(row) != size for row in fill):
        raise NativeTokenConstructionRejected("native-token-grid-invalid")
    return size, size


def construct_native_token_grid(grid: Mapping[str, Any]) -> dict[str, Any]:
    """Expand explicit multi-unit cells into entry token sequences.

    A token-aware constructor emits ordinary one-letter geometry plus an
    explicit ``tokenCells`` sidecar.  For a cell whose fill token is ``SS``,
    this adapter turns the affected across/down entries into sequences such as
    ``["C", "SS", "T"]`` and updates their lexical answers.  It never infers
    a token from an answer: the sidecar, the ordinary fill's first letter, and
    every crossing entry must agree.  One-unit display aliases stay on the
    existing decorator path so ordinary manifests do not gain unnecessary
    answer-token arrays.
    """
    if not isinstance(grid, Mapping):
        raise NativeTokenConstructionRejected("native-token-grid-invalid")
    if "tokenCells" not in grid:
        return dict(grid)
    raw_cells = grid.get("tokenCells")
    if not isinstance(raw_cells, list) or len(raw_cells) > 256:
        raise NativeTokenConstructionRejected("native-token-cells-invalid")
    width, height = _grid_dimensions(grid)
    fill = grid["fill"]
    entries = grid.get("entries")
    if not isinstance(entries, list) or not entries:
        raise NativeTokenConstructionRejected("native-token-entries-invalid")

    by_coordinate: dict[tuple[int, int], dict[str, Any]] = {}
    for raw_cell in raw_cells:
        if not isinstance(raw_cell, Mapping) or set(raw_cell) != {
            "row",
            "column",
            "displayToken",
            "fillToken",
            "source",
        }:
            raise NativeTokenConstructionRejected("native-token-cell-shape-invalid")
        row, column = raw_cell.get("row"), raw_cell.get("column")
        if (
            type(row) is not int
            or type(column) is not int
            or not (0 <= row < height and 0 <= column < width)
            or fill[row][column] == "#"
        ):
            raise NativeTokenConstructionRejected("native-token-cell-coordinate-invalid")
        display = _bounded_text(raw_cell.get("displayToken"), maximum=16)
        fill_token = raw_cell.get("fillToken")
        if (
            not isinstance(fill_token, str)
            or not 1 <= len(fill_token) <= 4
            or not fill_token.isascii()
            or not fill_token.isupper()
            or not fill_token.isalpha()
        ):
            raise NativeTokenConstructionRejected("native-token-fill-invalid")
        source = raw_cell.get("source")
        if source not in {
            "native-constructor-v1",
            "reviewed-admitted-v1",
            "private-language-decorator-v1",
        }:
            raise NativeTokenConstructionRejected("native-token-source-invalid")
        coordinate = (row, column)
        if coordinate in by_coordinate:
            raise NativeTokenConstructionRejected("native-token-cell-duplicate")
        # The ordinary grid still has one canonical letter in this geometric
        # cell.  A multi-unit token may expand from that letter, but cannot
        # contradict it or silently change the geometry.
        if len(fill_token) > 1 and fill[row][column] != fill_token[0]:
            raise NativeTokenConstructionRejected("native-token-fill-base-mismatch")
        by_coordinate[coordinate] = {
            "row": row,
            "column": column,
            "displayToken": display,
            "fillToken": fill_token,
            "source": source,
        }

    if not any(len(cell["fillToken"]) > 1 for cell in by_coordinate.values()):
        return dict(grid)

    normalized_entries: list[dict[str, Any]] = []
    for raw_entry in entries:
        if not isinstance(raw_entry, Mapping):
            raise NativeTokenConstructionRejected("native-token-entry-invalid")
        coordinates = _entry_cells(raw_entry)
        answer = raw_entry.get("answer")
        if not isinstance(answer, str) or len(answer) != len(coordinates):
            raise NativeTokenConstructionRejected("native-token-answer-invalid")
        existing = raw_entry.get("cellTokens")
        if existing is not None and (
            not isinstance(existing, list)
            or len(existing) != len(coordinates)
            or any(
                not isinstance(token, str)
                or not 1 <= len(token) <= 8
                or not token.isascii()
                or not token.isupper()
                or not token.isalpha()
                for token in existing
            )
            or answer != "".join(existing)
        ):
            raise NativeTokenConstructionRejected("native-token-entry-sequence-invalid")
        sequence = list(existing) if existing is not None else []
        if existing is None:
            for index, (row, column) in enumerate(coordinates):
                cell = by_coordinate.get((row, column))
                if cell is None:
                    if len(answer[index]) != 1 or not answer[index].isupper() or not answer[index].isascii():
                        raise NativeTokenConstructionRejected("native-token-answer-invalid")
                    sequence.append(answer[index])
                else:
                    if answer[index] != cell["fillToken"][0]:
                        raise NativeTokenConstructionRejected("native-token-answer-base-mismatch")
                    sequence.append(cell["fillToken"])
        for index, coordinate in enumerate(coordinates):
            cell = by_coordinate.get(coordinate)
            if cell is not None and sequence[index] != cell["fillToken"]:
                raise NativeTokenConstructionRejected("native-token-crossing-mismatch")
        normalized = dict(raw_entry)
        normalized["cellTokens"] = sequence
        normalized["answer"] = "".join(sequence)
        normalized_entries.append(normalized)

    normalized_grid = dict(grid)
    normalized_grid["entries"] = normalized_entries
    normalized_grid["tokenCells"] = list(by_coordinate.values())
    # Reuse the strict crossing and envelope validator as the final authority.
    validate_native_token_cells(normalized_grid)
    return normalized_grid


def validate_native_token_cells(grid: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize ``grid.tokenCells`` without changing the grid.

    The native envelope is optional.  A missing field returns an explicit
    ``absent`` status so provenance can distinguish ordinary ASCII output from
    a constructor that was asked to emit tokens but failed validation.
    """

    if not isinstance(grid, Mapping):
        raise NativeTokenConstructionRejected("native-token-grid-invalid")
    if "tokenCells" not in grid:
        return {
            "version": TOKEN_CONSTRUCTION_VERSION,
            "status": "absent",
            "cells": [],
            "reasons": [],
        }
    raw_cells = grid.get("tokenCells")
    if not isinstance(raw_cells, list) or len(raw_cells) > 256:
        raise NativeTokenConstructionRejected("native-token-cells-invalid")
    width, height = _grid_dimensions(grid)
    fill = grid["fill"]
    entries = grid.get("entries")
    if not isinstance(entries, list) or not entries:
        raise NativeTokenConstructionRejected("native-token-entries-invalid")

    entry_by_coordinate: dict[
        tuple[int, int], list[tuple[Mapping[str, Any], int, tuple[str, ...]]]
    ] = defaultdict(list)
    entry_ids: set[str] = set()
    for raw_entry in entries:
        if not isinstance(raw_entry, Mapping):
            raise NativeTokenConstructionRejected("native-token-entry-invalid")
        entry_id = _entry_id(raw_entry)
        if entry_id in entry_ids:
            raise NativeTokenConstructionRejected("native-token-entry-duplicate")
        entry_ids.add(entry_id)
        coordinates = _entry_cells(raw_entry)
        cell_tokens = raw_entry.get("cellTokens")
        if cell_tokens is None:
            answer = raw_entry.get("answer")
            if not isinstance(answer, str) or len(answer) != len(coordinates):
                raise NativeTokenConstructionRejected("native-token-answer-invalid")
            sequence = tuple(answer)
        else:
            if (
                not isinstance(cell_tokens, list)
                or len(cell_tokens) != len(coordinates)
                or any(
                    not isinstance(token, str)
                    or not 1 <= len(token) <= 8
                    or not token.isascii()
                    or not token.isupper()
                    or not token.isalpha()
                    for token in cell_tokens
                )
            ):
                raise NativeTokenConstructionRejected("native-token-entry-sequence-invalid")
            answer = raw_entry.get("answer")
            if not isinstance(answer, str) or answer != "".join(cell_tokens):
                raise NativeTokenConstructionRejected("native-token-answer-sequence-mismatch")
            sequence = tuple(cell_tokens)
        for index, (row, column) in enumerate(coordinates):
            if not (0 <= row < height and 0 <= column < width):
                raise NativeTokenConstructionRejected("native-token-entry-out-of-bounds")
            if fill[row][column] == "#":
                raise NativeTokenConstructionRejected("native-token-cell-is-block")
            entry_by_coordinate[(row, column)].append((raw_entry, index, sequence))

    normalized: dict[tuple[int, int], dict[str, Any]] = {}
    for raw_cell in raw_cells:
        if not isinstance(raw_cell, Mapping) or set(raw_cell) != {
            "row",
            "column",
            "displayToken",
            "fillToken",
            "source",
        }:
            raise NativeTokenConstructionRejected("native-token-cell-shape-invalid")
        row, column = raw_cell.get("row"), raw_cell.get("column")
        if type(row) is not int or type(column) is not int or not (0 <= row < height and 0 <= column < width):
            raise NativeTokenConstructionRejected("native-token-cell-coordinate-invalid")
        coordinate = (row, column)
        if coordinate in normalized:
            raise NativeTokenConstructionRejected("native-token-cell-duplicate")
        if fill[row][column] == "#" or coordinate not in entry_by_coordinate:
            raise NativeTokenConstructionRejected("native-token-cell-not-in-grid")
        display = _bounded_text(raw_cell.get("displayToken"), maximum=16)
        fill_token = raw_cell.get("fillToken")
        if not isinstance(fill_token, str) or not 1 <= len(fill_token) <= 4 or not fill_token.isascii() or not fill_token.isupper() or not fill_token.isalpha():
            raise NativeTokenConstructionRejected("native-token-fill-invalid")
        source = raw_cell.get("source")
        if source not in {
            "native-constructor-v1",
            "reviewed-admitted-v1",
            "private-language-decorator-v1",
        }:
            raise NativeTokenConstructionRejected("native-token-source-invalid")

        occupants = entry_by_coordinate[coordinate]
        for entry, index, sequence in occupants:
            cell_tokens = entry.get("cellTokens")
            expected = sequence[index]
            if cell_tokens is None:
                if len(fill_token) > 1 or expected != fill_token:
                    raise NativeTokenConstructionRejected("native-token-entry-sequence-required")
            elif cell_tokens[index] != fill_token:
                raise NativeTokenConstructionRejected("native-token-crossing-mismatch")
        normalized[coordinate] = {
            "id": f"r{row}c{column}",
            "row": row,
            "column": column,
            "displayToken": display,
            "fillToken": fill_token,
            "source": source,
            "entryIds": sorted(
                {_entry_id(entry) for entry, _index, _sequence in occupants}
            ),
        }

    # Every explicit cell must agree with all of its crossing occupants.  This
    # catches a constructor that emits one direction's token but leaves the
    # crossing answer sequence ordinary.
    for coordinate, cell in normalized.items():
        for entry, index, _sequence in entry_by_coordinate[coordinate]:
            cell_tokens = entry.get("cellTokens")
            if cell_tokens is not None and cell_tokens[index] != cell["fillToken"]:
                raise NativeTokenConstructionRejected("native-token-crossing-mismatch")

    return {
        "version": TOKEN_CONSTRUCTION_VERSION,
        "status": "accepted" if normalized else "empty",
        "cells": [normalized[key] for key in sorted(normalized)],
        "reasons": [],
    }


def emit_single_cell_language_tokens(
    grid: Mapping[str, Any],
    hints: Any,
    *,
    language: str | None,
    source: str | None,
) -> list[dict[str, Any]]:
    """Project explicit one-cell language hints into native token cells.

    This conservative decorator is for the current ASCII xfill runtime. It
    emits only a display grapheme whose canonical fill is already the one
    letter occupying that grid cell. Multi-unit spellings are left for a
    token-aware constructor and never squeezed into ordinary geometry here.
    """
    if (
        not isinstance(language, str)
        or not language.strip()
        or not isinstance(hints, list)
        or source not in {"reviewed-admitted", "synthetic-unadmitted"}
    ):
        return []
    entries = grid.get("entries") if isinstance(grid, Mapping) else None
    if not isinstance(entries, list):
        return []
    by_id = {
        f"{'across' if entry.get('dir') == 'A' else 'down'}-{entry.get('num')}": entry
        for entry in entries
        if isinstance(entry, Mapping) and entry.get("dir") in {"A", "D"}
    }
    cells: dict[tuple[int, int], dict[str, Any]] = {}
    for hint in hints:
        if not isinstance(hint, Mapping) or set(hint) != {
            "entryId",
            "cellIndex",
            "displayToken",
        }:
            continue
        entry = by_id.get(hint.get("entryId"))
        index = hint.get("cellIndex")
        length = entry.get("len") if isinstance(entry, Mapping) else None
        row = entry.get("row") if isinstance(entry, Mapping) else None
        column = entry.get("col") if isinstance(entry, Mapping) else None
        direction = entry.get("dir") if isinstance(entry, Mapping) else None
        display_token = hint.get("displayToken")
        if (
            entry is None
            or type(index) is not int
            or index < 0
            or type(length) is not int
            or index >= length
            or type(row) is not int
            or type(column) is not int
            or direction not in {"A", "D"}
            or not isinstance(display_token, str)
            or not isinstance(entry.get("answer"), str)
            or len(entry["answer"]) != length
        ):
            continue
        display = unicodedata.normalize("NFC", display_token)
        fill_token = single_cell_fill_token(language, display)
        if fill_token is None or fill_token != entry["answer"][index]:
            continue
        cell_row = row + (index if direction == "D" else 0)
        cell_column = column + (index if direction == "A" else 0)
        coordinate = (cell_row, cell_column)
        candidate = {
            "row": cell_row,
            "column": cell_column,
            "displayToken": display,
            "fillToken": fill_token,
            "source": (
                "reviewed-admitted-v1"
                if source == "reviewed-admitted"
                else "private-language-decorator-v1"
            ),
        }
        prior = cells.get(coordinate)
        if prior is None:
            cells[coordinate] = candidate
        elif prior != candidate:
            cells.pop(coordinate, None)
    return [cells[key] for key in sorted(cells)]


def native_token_hints(grid: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project accepted native cells to the future producer hint contract."""

    report = validate_native_token_cells(grid)
    if report["status"] not in {"accepted", "empty"}:
        return []
    entries = [entry for entry in grid.get("entries", []) if isinstance(entry, Mapping)]
    by_id = {_entry_id(entry): entry for entry in entries}
    hints = []
    for cell in report["cells"]:
        for entry_id in cell["entryIds"]:
            entry = by_id[entry_id]
            coordinates = _entry_cells(entry)
            row_column = (cell["row"], cell["column"])
            hints.append(
                {
                    "entryId": f"{_DIRECTIONS[entry['dir']]}-{entry['num']}",
                    "cellIndex": coordinates.index(row_column),
                    "displayToken": cell["displayToken"],
                }
            )
    return hints
