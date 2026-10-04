from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from src.crossword.clue_review_bundle import (
    build_clue_review_bundle,
    verify_clue_review_bundle,
)
from src.crossword.legacy_manifest import to_puzzle_document


def _response():
    crossword = {
        "metadata": {
            "date": "2026-09-28",
            "title": "Synthetic review board",
            "authors": ["local"],
            "width": 3,
            "height": 3,
        },
        "entries": [],
    }
    rows = ["CAT", "ARE", "TEN"]
    numbers = [1, 4, 5]
    for row, answer in enumerate(rows):
        crossword["entries"].append(
            {
                "clue_number": numbers[row],
                "clue_text": "Feline pet",
                "direction": "across",
                "start_x": 0,
                "start_y": row,
                "characters": [{"letters": letter} for letter in answer],
            }
        )
    for column in range(3):
        answer = "".join(row[column] for row in rows)
        crossword["entries"].append(
            {
                "clue_number": [1, 2, 3][column],
                "clue_text": "Letter sequence",
                "direction": "down",
                "start_x": column,
                "start_y": 0,
                "characters": [{"letters": letter} for letter in answer],
            }
        )
    manifest = to_puzzle_document(crossword)
    entries = []
    for item in manifest["entries"]:
        entries.append(
            {
                "id": item["id"],
                "answerLength": len(item["answer"]),
                "answerShape": "all-unique",
                "familyObservation": {"family": "definition"},
                "grammarBridge": {"valid": True, "issues": []},
                "surfaceIssues": [],
                "riskFlags": [],
                "mechanicalIssue": None,
                "morphologyIssue": None,
                "semanticChallenge": {"classification": "needs-review"},
                "semanticStatus": "not-established",
                "supportBand": "ordinary",
            }
        )
    return {
        "puzzleManifest": manifest,
        "provenance": {
            "weekday": "tuesday",
            "seed": 7,
            "model": "gemma4:26b",
            "clueQuality": {
                "issueCount": 0,
                "groundedClueBundle": {"entries": entries},
            },
            "clueDiversity": {"nonDefinitionRate": 0.0},
            "timingsSeconds": {"total": 1.25},
        },
    }


def test_review_bundle_is_digest_bound_and_explicitly_local():
    bundle = build_clue_review_bundle(_response())

    assert bundle["schemaVersion"] == "private-clue-review-bundle-v1"
    assert bundle["scope"] == "local-answer-bearing-editorial-review"
    assert bundle["publishable"] is False
    assert len(bundle["entries"]) == 6
    assert bundle["entries"][0]["review"]["status"] == "unreviewed"
    assert verify_clue_review_bundle(bundle)

    changed = deepcopy(bundle)
    changed["entries"][0]["clue"] = "Changed clue"
    assert not verify_clue_review_bundle(changed)


def test_review_bundle_requires_every_grounding_record():
    response = _response()
    response["provenance"]["clueQuality"]["groundedClueBundle"]["entries"].pop()

    with pytest.raises(ValueError, match="missing grounding record"):
        build_clue_review_bundle(response)


def test_review_bundle_rejects_tampered_manifest():
    response = _response()
    response["puzzleManifest"]["entries"][0]["answer"] = "DOG"

    with pytest.raises(ValueError, match="integrity check"):
        build_clue_review_bundle(response)
