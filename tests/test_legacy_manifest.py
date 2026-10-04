"""Contract tests for adapting parsed legacy entries to replay manifests."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from src.crossword.legacy_manifest import to_puzzle_document, verify_integrity
from src.crossword.models import Character, Crossword, CrosswordMetadata, Entry


ROOT = Path(__file__).resolve().parents[1]
ROWS = ("CAT", "ARE", "TEN")


def synthetic_mapping() -> dict:
    """The same original 3x3 word-square fixture used by the CI server."""
    entries = []
    for index, word in enumerate(ROWS):
        for direction in ("across", "down"):
            clue_number = (
                (1 if index == 0 else index + 3)
                if direction == "across"
                else index + 1
            )
            entries.append(
                {
                    "clue_number": clue_number,
                    "clue_text": f"Synthetic {direction} row {index + 1}: {word}",
                    "direction": direction,
                    "start_x": 0 if direction == "across" else index,
                    "start_y": index if direction == "across" else 0,
                    "characters": [{"letters": letter} for letter in word],
                }
            )
    return {
        "metadata": {
            "date": "240101",
            "title": "Synthetic CI word square",
            "authors": ["CI fixture author"],
            "width": 3,
            "height": 3,
        },
        "entries": entries,
    }


def synthetic_model() -> Crossword:
    source = synthetic_mapping()
    return Crossword(
        metadata=CrosswordMetadata(**source["metadata"]),
        entries=[Entry(**entry) for entry in source["entries"]],
    )


def domain_validate(document: dict) -> dict:
    """Run the shared TypeScript validator and browser-style digest calculation."""
    bridge = r"""
const fs = require('node:fs');
const crypto = require('node:crypto');
const ts = require('typescript');
require.extensions['.ts'] = (module, filename) => {
  const source = fs.readFileSync(filename, 'utf8');
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
    },
    fileName: filename,
  });
  module._compile(output.outputText, filename);
};
const { validatePuzzle } = require('./packages/domain/src/puzzle.ts');
const puzzle = JSON.parse(fs.readFileSync(0, 'utf8'));
const { integrity, ...body } = puzzle;
function stableJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) =>
      `${JSON.stringify(key)}:${stableJson(value[key])}`
    ).join(',')}}`;
  }
  return JSON.stringify(value);
}
const digest = crypto.createHash('sha256').update(stableJson(body), 'utf8').digest('hex');
process.stdout.write(JSON.stringify({ valid: validatePuzzle(puzzle), digest }));
"""
    completed = subprocess.run(
        ["node", "-e", bridge],
        cwd=ROOT,
        input=json.dumps(document),
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_converts_legacy_model_and_dump_to_stable_valid_manifest():
    from_model = to_puzzle_document(synthetic_model())
    model_dump = synthetic_model().model_dump()
    from_dump = to_puzzle_document(model_dump)
    reordered = copy.deepcopy(model_dump)
    reordered["entries"].reverse()

    assert from_model == from_dump
    assert from_model == to_puzzle_document(reordered)
    assert from_model["schemaVersion"] == 1
    assert from_model["id"].startswith("legacy-")
    assert from_model["width"] == from_model["height"] == 3
    assert [cell["id"] for cell in from_model["cells"]] == [
        f"r{row}c{column}" for row in range(3) for column in range(3)
    ]
    assert from_model["topology"]["blockedCellIds"] == []
    assert [
        (entry["number"], entry["direction"], entry["answer"])
        for entry in from_model["entries"]
    ] == [
        (1, "across", "CAT"),
        (1, "down", "CAT"),
        (2, "down", "ARE"),
        (3, "down", "TEN"),
        (4, "across", "ARE"),
        (5, "across", "TEN"),
    ]
    assert len(from_model["clues"]) == len(from_model["entries"]) == 6
    validation = domain_validate(from_model)
    assert validation["valid"]
    assert validation["digest"] == from_model["integrity"]["value"]


def test_manifest_digest_uses_sorted_compact_utf8_json_without_integrity():
    document = to_puzzle_document(synthetic_mapping())
    body = {key: value for key, value in document.items() if key != "integrity"}
    canonical = json.dumps(
        body,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    assert document["integrity"] == {
        "algorithm": "sha256",
        "value": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    assert verify_integrity(document)
    document["entries"][0]["clue"] += " changed"
    assert not verify_integrity(document)


def test_converts_real_parsed_15_by_15_puzzle_to_domain_manifest():
    from src.crossword.parser import NYTFormatParser
    from tests.test_parser import PUZZLE_250520

    document = to_puzzle_document(NYTFormatParser.parse(PUZZLE_250520))
    validation = domain_validate(document)

    assert document["width"] == document["height"] == 15
    assert len(document["topology"]["blockedCellIds"]) == 38
    assert validation["valid"]
    assert validation["digest"] == document["integrity"]["value"]


@pytest.mark.parametrize(
    ("width", "height", "message"),
    [
        (51, 1, "dimensions exceed"),
        (25, 21, "grid exceeds"),
        (1_000_000, 1, "dimensions exceed"),
    ],
)
def test_rejects_oversized_dimensions_before_grid_allocation(width, height, message):
    source = synthetic_mapping()
    source["metadata"].update(width=width, height=height)

    with pytest.raises(ValueError, match=message):
        to_puzzle_document(source)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda puzzle: puzzle["entries"][0]["characters"][0].update(letters="CA"),
            "single A-Z cell",
        ),
        (lambda puzzle: puzzle["entries"].pop(), "lacks an across or down entry"),
        (
            lambda puzzle: puzzle["entries"][1]["characters"][0].update(letters="X"),
            "crossing answers disagree",
        ),
        (lambda puzzle: puzzle["metadata"].update(width=2), "extends outside"),
        (lambda puzzle: puzzle["entries"][4].update(clue_number=4), "duplicate across clue number"),
    ],
)
def test_rejects_rebus_or_malformed_crossword_topology(mutate, message):
    source = copy.deepcopy(synthetic_mapping())
    mutate(source)

    with pytest.raises(ValueError, match=message):
        to_puzzle_document(source)


def test_private_token_manifest_preserves_cell_token_sequences():
    source = copy.deepcopy(synthetic_mapping())
    for entry in source["entries"]:
        if (entry["direction"], entry["start_x"], entry["start_y"]) in {
            ("across", 0, 1),
            ("down", 1, 0),
        }:
            entry["characters"][1]["letters"] = "SS"

    with pytest.raises(ValueError, match="single A-Z cell"):
        to_puzzle_document(source)

    document = to_puzzle_document(source, allow_token_cells=True)

    token_entries = [
        entry for entry in document["entries"] if entry.get("answerTokens")
    ]
    assert len(token_entries) == 2
    assert all(entry["answerTokens"] == ["A", "SS", "E"] for entry in token_entries)
    assert verify_integrity(document)
