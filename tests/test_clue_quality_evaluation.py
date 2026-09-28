from __future__ import annotations

import copy

import pytest

from src.crossword.clue_quality_evaluation import (
    clue_case_from_provenance,
    evaluate_clue_quality_study,
)


def _provenance():
    return {
        "clueQuality": {
            "checkedCount": 4,
            "issueCount": 1,
            "fallbackCount": 1,
            "signalCounts": {"fill-blank": 2, "question-mark": 1},
            "issueCounts": {"answer-form-in-clue": 1},
            "diversity": {
                "entryCount": 4,
                "familyCounts": {"definition": 2, "fill-blank": 1, "pun": 1},
                "nonDefinitionCount": 2,
                "nonDefinitionRate": 0.5,
                "nonDefinitionFamilies": ["fill-blank", "pun"],
                "floorMet": True,
                "requiredNonDefinitionFamilies": 2,
                "requiredNonDefinitionFamilySet": ["fill-blank", "pun"],
                "missingNonDefinitionFamilies": [],
                "requiredNonDefinitionClues": 2,
                "targetNonDefinitionRate": 0.5,
                "targetNonDefinitionClues": 2,
                "semanticStatus": "not-established",
                "repair": {"attempted": True, "attemptCount": 1, "rewrittenCount": 1},
            },
            "groundedClueBundle": {
                "entryCount": 4,
                "familyCounts": {"definition": 2, "fill-blank": 1, "pun": 1},
                "grammarBridge": {"checkedCount": 4},
                "semanticChallenge": {
                    "classificationCounts": {"needs-review": 3, "safe-fallback": 1}
                },
            },
        },
        "timingsSeconds": {"total": 12.5, "clueGeneration": 9.25},
    }


def test_case_projection_is_answer_free_and_preserves_surface_receipts():
    case = clue_case_from_provenance(_provenance(), 7)
    assert case["entryCount"] == 4
    assert case["familyCounts"] == {"definition": 2, "fill-blank": 1, "pun": 1}
    assert case["nonDefinitionRate"] == 0.5
    assert case["requiredNonDefinitionFamilySet"] == ["fill-blank", "pun"]
    assert case["missingNonDefinitionFamilies"] == []
    assert case["issueCounts"] == {"answer-form-in-clue": 1}
    assert case["semanticChallenge"] == {"needs-review": 3, "safe-fallback": 1}
    assert case["timingsSeconds"]["total"] == 12.5
    assert not {"answer", "clueText", "entries", "clues"}.intersection(case)


def test_case_projection_accepts_legacy_zero_fallback_receipts():
    value = _provenance()
    value["clueQuality"].pop("fallbackCount")
    value["clueQuality"]["diversity"]["floorMet"] = False
    case = clue_case_from_provenance(value, 8)
    assert case["fallbackCount"] == 0
    assert case["floorMet"] is False


def test_study_digest_is_stable_and_reports_missing_requested_seed():
    case = clue_case_from_provenance(_provenance(), 7)
    report = evaluate_clue_quality_study(
        [case], requested_seeds=[7, 8], study_id="fixture", recipe_id="tuesday-private-v1"
    )
    again = evaluate_clue_quality_study(
        [copy.deepcopy(case)], requested_seeds=[7, 8], study_id="fixture", recipe_id="tuesday-private-v1"
    )
    assert report["studyDigest"] == again["studyDigest"]
    assert report["missingSeeds"] == [8]
    assert report["summary"]["grammarIssueCount"] == 1
    assert report["summary"]["floorMetCases"] == 1
    assert report["summary"]["floorMetRate"] == 1.0
    assert report["summary"]["grammarCleanCases"] == 0
    assert report["summary"]["familyFloorMetCases"] == 1
    assert report["summary"]["targetRateCases"] == 1
    assert report["summary"]["targetRateMetCases"] == 1
    assert report["summary"]["observedNonDefinitionRate"] == 0.5


def test_projection_rejects_family_count_mismatch():
    value = _provenance()
    value["clueQuality"]["diversity"]["familyCounts"]["pun"] = 9
    with pytest.raises(ValueError, match="add up"):
        clue_case_from_provenance(value, 7)


def test_study_rejects_duplicate_case_seeds():
    case = clue_case_from_provenance(_provenance(), 7)
    with pytest.raises(ValueError, match="unique"):
        evaluate_clue_quality_study([case, dict(case)])
