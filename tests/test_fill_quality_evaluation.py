"""Deterministic contract tests for fixed-seed fill studies."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from src.crossword.fill_quality_evaluation import (
    FILL_QUALITY_COMPARISON_VERSION,
    FILL_QUALITY_STUDY_SCOPE,
    FILL_QUALITY_STUDY_VERSION,
    canonical_fill_quality_json,
    compare_fill_quality_studies,
    evaluate_fill_quality_study,
    run_fixed_seed_fill_study,
)


ROOT = Path(__file__).resolve().parents[1]


def _quality(*, mean_score=80, minimum=55, iffy=1, weak=4, theme=2):
    return {
        "status": "measured",
        "entryCount": 70,
        "meanScore": mean_score,
        "minimumScore": minimum,
        "iffyCount": iffy,
        "weakCount": weak,
        "weakWithoutCrossingCount": 0,
        "themeCount": theme,
        "uncertainty": "xfill-heuristic-not-human-quality",
    }


def _cases():
    return [
        {
            "seed": 7,
            "selectedAttempt": 2,
            "attempts": [
                {"label": "theme", "seed": 7, "status": "candidate", "quality": _quality(iffy=3, weak=8)},
                {"label": "reseed", "seed": 1007, "status": "candidate", "quality": _quality(iffy=1, weak=4)},
            ],
        },
        {
            "seed": 9,
            "selectedAttempt": 1,
            "attempts": [
                {"label": "theme", "seed": 9, "status": "candidate", "quality": _quality(iffy=0, weak=2, theme=3)},
                {"label": "open", "seed": 2009, "status": "failed", "reason": "timeout"},
            ],
        },
    ]


def test_study_is_repeatable_and_reports_selection_without_human_claims():
    first = evaluate_fill_quality_study(_cases(), study_id="study-a", requested_seeds=[7, 9, 11])
    second = evaluate_fill_quality_study(_cases(), study_id="study-a", requested_seeds=[7, 9, 11])

    assert first == second
    assert first["evaluationVersion"] == FILL_QUALITY_STUDY_VERSION
    assert first["scope"] == FILL_QUALITY_STUDY_SCOPE
    assert first["inputs"]["missingSeeds"] == [11]
    assert first["summary"]["measuredAttemptCount"] == 3
    assert first["summary"]["failedOrRejectedAttemptCount"] == 1
    assert first["summary"]["selectedIffyCount"]["mean"] == 0.5
    assert first["acceptance"]["humanQualityGate"] == "not-applied"
    assert first["uncertainty"]["humanSolveProbability"] == "unmeasured"
    assert first["studyDigest"].startswith("sha256:")


def test_unavailable_scores_are_counted_without_inventing_metrics():
    report = evaluate_fill_quality_study(
        [
            {
                "seed": 1,
                "attempts": [
                    {
                        "label": "legacy",
                        "seed": 1,
                        "status": "unavailable",
                        "quality": {"status": "unavailable", "reason": "old-runtime"},
                    }
                ],
            }
        ]
    )
    assert report["status"] == "observed"
    assert report["summary"]["measuredAttemptCount"] == 0
    assert report["summary"]["unavailableAttemptCount"] == 1
    assert report["summary"]["meanScore"]["mean"] is None
    assert report["acceptance"]["status"] == "unavailable"


def test_weak_without_crossing_count_round_trips_and_rejects_invalid_values():
    cases = [
        {
            "seed": 1,
            "selectedAttempt": 1,
            "attempts": [
                {
                    "label": "native",
                    "seed": 1,
                    "status": "candidate",
                    "quality": _quality(),
                }
            ],
        }
    ]
    cases[0]["attempts"][0]["quality"]["weakWithoutCrossingCount"] = 2
    report = evaluate_fill_quality_study(cases)
    assert report["summary"]["weakWithoutCrossingCount"]["mean"] == 2
    assert report["summary"]["selectedWeakWithoutCrossingCount"]["mean"] == 2

    invalid = _quality()
    invalid["weakWithoutCrossingCount"] = -1
    with pytest.raises(ValueError, match="weakWithoutCrossingCount"):
        evaluate_fill_quality_study(
            [
                {
                    "seed": 1,
                    "attempts": [
                        {
                            "label": "native",
                            "seed": 1,
                            "status": "candidate",
                            "quality": invalid,
                        }
                    ],
                }
            ]
        )


def test_runner_accepts_generation_shaped_quality_policy():
    calls = []

    def runner(seed):
        calls.append(seed)
        return {"fillQuality": {"qualityPolicy": {"selectedAttempt": 1, "attempts": [
            {"label": "primary", "seed": seed, "status": "candidate", "quality": _quality()}
        ]}}}

    report = run_fixed_seed_fill_study([3, 4], runner, study_id="native")
    assert calls == [3, 4]
    assert report["inputs"]["observedSeeds"] == [3, 4]
    assert report["summary"]["selectedCaseCount"] == 2


def test_duplicate_and_invalid_seeds_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        evaluate_fill_quality_study(_cases(), requested_seeds=[7, 7])
    with pytest.raises(ValueError, match="between"):
        evaluate_fill_quality_study([{"seed": -1, "attempts": []}])


def test_paired_comparison_reports_deltas_and_never_declares_a_winner():
    baseline_cases = _cases()
    policy_cases = _cases()
    policy_cases[0]["attempts"][1]["quality"]["iffyCount"] = 0
    policy_cases[0]["attempts"][1]["quality"]["weakCount"] = 3
    baseline = evaluate_fill_quality_study(baseline_cases, study_id="baseline")
    policy = evaluate_fill_quality_study(policy_cases, study_id="policy")

    comparison = compare_fill_quality_studies(
        policy,
        baseline,
        left_label="support-aware",
        right_label="baseline",
        expected_seeds=[7, 9, 11],
    )

    assert comparison["evaluationVersion"] == FILL_QUALITY_COMPARISON_VERSION
    assert comparison["status"] == "observed"
    assert comparison["inputs"]["pairedSeeds"] == [7, 9]
    assert comparison["summary"]["iffyCount"]["meanDelta"] == -0.5
    assert comparison["summary"]["iffyCount"]["direction"] == {
        "leftWins": 1,
        "rightWins": 0,
        "ties": 1,
        "paired": 2,
    }
    assert comparison["uncertainty"]["winnerClaim"] == "none"
    assert comparison["comparisonDigest"].startswith("sha256:")


def test_cli_emits_same_digest_as_library(tmp_path):
    source = tmp_path / "cases.json"
    source.write_text(json.dumps({"cases": _cases(), "requestedSeeds": [7, 9]}), encoding="utf-8")
    process = subprocess.run(
        [".venv/bin/python", "scripts/fill-quality-study.py", str(source)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(process.stdout)
    unsigned = dict(report)
    digest = unsigned.pop("studyDigest")
    assert digest == "sha256:" + __import__("hashlib").sha256(
        canonical_fill_quality_json(unsigned).encode("utf-8")
    ).hexdigest()


def test_comparison_cli_round_trips_report(tmp_path):
    source = tmp_path / "study.json"
    source.write_text(
        json.dumps({"cases": _cases(), "requestedSeeds": [7, 9]}),
        encoding="utf-8",
    )
    study_path = tmp_path / "study-report.json"
    subprocess.run(
        [
            ".venv/bin/python",
            "scripts/fill-quality-study.py",
            str(source),
            "--out",
            str(study_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    process = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/fill-quality-compare.py",
            str(study_path),
            str(study_path),
            "--expected-seed",
            "7",
            "--expected-seed",
            "9",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(process.stdout)
    assert report["inputs"]["pairedSeeds"] == [7, 9]
    assert report["uncertainty"]["winnerClaim"] == "none"
