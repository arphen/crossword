"""Deterministic fixed-seed studies for the native private fill path.

The private constructor may compare a few native ``xfill`` retries before it
chooses a board.  This module turns those receipts into a small, repeatable
study artifact.  It deliberately measures only the fields reported by native
``xfill``: retry counts, entry counts, score summaries, and theme retention.
Those fields are useful for finding regressions in construction, but they are
not a proxy for clue fairness, human solve probability, or player enjoyment.

The evaluator accepts already captured records and an injected runner.  It
never starts Ollama or invokes a native runtime itself, which makes a study
safe to run in CI and lets a local operator run the same recipe against real
fixed seeds when desired.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import hashlib
import json
import math
from statistics import mean, median
from typing import Any


FILL_QUALITY_STUDY_VERSION = "private-fill-quality-study-v1"
FILL_QUALITY_STUDY_SCOPE = "fixed-seed-native-fill-study"
FILL_QUALITY_UNCERTAINTY = "xfill-heuristic-not-human-quality"
FILL_QUALITY_COMPARISON_VERSION = "private-fill-quality-comparison-v1"
MAX_STUDY_SEEDS = 32
MAX_ATTEMPTS_PER_CASE = 8
_SEED_LIMIT = 2_147_483_647


def canonical_fill_quality_json(value: Any) -> str:
    """Return the stable JSON representation used by study digests."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_fill_quality_json(value).encode("utf-8")
    ).hexdigest()


def _number(value: Any, path: str, *, integer: bool = False) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be a number")
    if not math.isfinite(float(value)) or float(value) < 0:
        raise ValueError(f"{path} must be finite and non-negative")
    if integer and not isinstance(value, int):
        raise ValueError(f"{path} must be an integer")
    return value


def _seed(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{path} must be an integer")
    if value < 0 or value > _SEED_LIMIT:
        raise ValueError(f"{path} must be between 0 and {_SEED_LIMIT}")
    return value


def _string(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be an object")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be an array")
    return value


def _rounded(value: float) -> float:
    return round(value, 3)


def _summary(values: list[float | int], total: int) -> dict[str, Any]:
    if not values:
        return {
            "observed": 0,
            "missing": total,
            "sum": 0,
            "mean": None,
            "median": None,
            "minimum": None,
            "maximum": None,
        }
    numbers = [float(value) for value in values]
    return {
        "observed": len(values),
        "missing": total - len(values),
        "sum": _rounded(sum(numbers)),
        "mean": _rounded(mean(numbers)),
        "median": _rounded(median(numbers)),
        "minimum": _rounded(min(numbers)),
        "maximum": _rounded(max(numbers)),
    }


def _quality(quality: Any, path: str) -> dict[str, Any]:
    raw = _mapping(quality, path)
    status = raw.get("status")
    if status not in {"measured", "unavailable"}:
        raise ValueError(f"{path}.status must be measured or unavailable")
    result: dict[str, Any] = {
        "status": status,
        "uncertainty": raw.get("uncertainty", FILL_QUALITY_UNCERTAINTY),
    }
    if not isinstance(result["uncertainty"], str) or not result["uncertainty"]:
        raise ValueError(f"{path}.uncertainty must be a non-empty string")
    for name in ("entryCount", "iffyCount", "weakCount", "themeCount"):
        if name in raw and raw[name] is not None:
            result[name] = int(_number(raw[name], f"{path}.{name}", integer=True))
    if "weakWithoutCrossingCount" in raw and raw["weakWithoutCrossingCount"] is not None:
        value = int(
            _number(
                raw["weakWithoutCrossingCount"],
                f"{path}.weakWithoutCrossingCount",
                integer=True,
            )
        )
        if value < 0:
            raise ValueError(f"{path}.weakWithoutCrossingCount must be non-negative")
        entry_count = result.get("entryCount")
        if entry_count is not None and value > entry_count:
            raise ValueError(
                f"{path}.weakWithoutCrossingCount cannot exceed entryCount"
            )
        result["weakWithoutCrossingCount"] = value
    for name in ("meanScore", "minimumScore"):
        if name in raw and raw[name] is not None:
            result[name] = float(_number(raw[name], f"{path}.{name}"))
    if status == "measured":
        required = ("entryCount", "iffyCount", "weakCount", "meanScore", "minimumScore")
        missing = [name for name in required if name not in result]
        if missing:
            raise ValueError(f"{path} is missing measured fields: {', '.join(missing)}")
    return result


def _attempt(raw: Any, path: str) -> dict[str, Any]:
    value = _mapping(raw, path)
    label = _string(value.get("label", value.get("option", "attempt")), f"{path}.label")
    seed = _seed(value.get("seed"), f"{path}.seed")
    status = value.get("status")
    if status not in {"candidate", "failed", "rejected", "unavailable"}:
        raise ValueError(
            f"{path}.status must be candidate, failed, rejected, or unavailable"
        )
    result: dict[str, Any] = {
        "label": label,
        "seed": seed,
        "status": status,
    }
    if "quality" in value:
        result["quality"] = _quality(value["quality"], f"{path}.quality")
    if "boardDigest" in value and value["boardDigest"] is not None:
        result["boardDigest"] = _string(value["boardDigest"], f"{path}.boardDigest")
    if "sourceDigest" in value and value["sourceDigest"] is not None:
        result["sourceDigest"] = _string(value["sourceDigest"], f"{path}.sourceDigest")
    if "reason" in value and value["reason"] is not None:
        result["reason"] = _string(value["reason"], f"{path}.reason")
    return result


def _case(raw: Any, index: int) -> dict[str, Any]:
    path = f"cases[{index}]"
    value = _mapping(raw, path)
    seed = _seed(value.get("seed"), f"{path}.seed")
    raw_attempts = _list(value.get("attempts"), f"{path}.attempts")
    if not raw_attempts:
        raise ValueError(f"{path}.attempts must not be empty")
    if len(raw_attempts) > MAX_ATTEMPTS_PER_CASE:
        raise ValueError(f"{path}.attempts may contain at most {MAX_ATTEMPTS_PER_CASE} items")
    attempts = [_attempt(item, f"{path}.attempts[{i}]") for i, item in enumerate(raw_attempts)]
    selected = value.get("selectedAttempt")
    if selected is not None:
        if not isinstance(selected, int) or isinstance(selected, bool):
            raise ValueError(f"{path}.selectedAttempt must be an integer")
        if selected < 1 or selected > len(attempts):
            raise ValueError(f"{path}.selectedAttempt is outside attempts")
        if attempts[selected - 1]["status"] not in {"candidate", "unavailable"}:
            raise ValueError(f"{path}.selectedAttempt must point to a usable attempt")
    recipe = value.get("recipe")
    result: dict[str, Any] = {"seed": seed, "attempts": attempts}
    if recipe is not None:
        result["recipe"] = _string(recipe, f"{path}.recipe")
    if selected is not None:
        result["selectedAttempt"] = selected
    return result


def _project_attempt(attempt: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: attempt[key] for key in ("label", "seed", "status")}
    if "quality" in attempt:
        result["quality"] = dict(attempt["quality"])
    for key in ("boardDigest", "sourceDigest", "reason"):
        if key in attempt:
            result[key] = attempt[key]
    return result


def evaluate_fill_quality_study(
    cases: Sequence[Mapping[str, Any]],
    *,
    study_id: str = "fixture",
    recipe_id: str = "private-local-v1",
    requested_seeds: Sequence[int] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic report from fixed-seed retry receipts.

    ``cases`` should contain one case per seed, with the same attempt records
    emitted by ``private_puzzle_generation``'s ``qualityPolicy``.  The report
    is intentionally bounded to 32 seeds so an accidental multi-hour runtime
    cannot turn into an unbounded artifact.
    """

    if not isinstance(study_id, str) or not study_id:
        raise ValueError("study_id must be a non-empty string")
    if not isinstance(recipe_id, str) or not recipe_id:
        raise ValueError("recipe_id must be a non-empty string")
    if len(cases) > MAX_STUDY_SEEDS:
        raise ValueError(f"study may contain at most {MAX_STUDY_SEEDS} seeds")
    normalized = [_case(case, index) for index, case in enumerate(cases)]
    observed_seeds = [case["seed"] for case in normalized]
    if len(set(observed_seeds)) != len(observed_seeds):
        raise ValueError("cases must contain one unique case per seed")
    if requested_seeds is None:
        requested = list(observed_seeds)
    else:
        requested = [_seed(seed, f"requested_seeds[{index}]") for index, seed in enumerate(requested_seeds)]
        if len(requested) > MAX_STUDY_SEEDS:
            raise ValueError(f"requested_seeds may contain at most {MAX_STUDY_SEEDS} seeds")
        if len(set(requested)) != len(requested):
            raise ValueError("requested_seeds must be unique")

    all_attempts = [attempt for case in normalized for attempt in case["attempts"]]
    measured = [
        attempt["quality"]
        for attempt in all_attempts
        if isinstance(attempt.get("quality"), Mapping)
        and attempt["quality"].get("status") == "measured"
    ]
    selected_qualities: list[Mapping[str, Any]] = []
    selected_cases = 0
    for case in normalized:
        selected_index = case.get("selectedAttempt")
        if isinstance(selected_index, int):
            selected_cases += 1
            selected = case["attempts"][selected_index - 1]
            if isinstance(selected.get("quality"), Mapping) and selected["quality"].get("status") == "measured":
                selected_qualities.append(selected["quality"])

    def values(name: str, rows: Sequence[Mapping[str, Any]]) -> list[int | float]:
        return [row[name] for row in rows if name in row and row[name] is not None]

    measured_total = len(measured)
    selected_total = len(selected_qualities)
    retry_counts = [len(case["attempts"]) for case in normalized]
    usable_attempts = sum(
        1 for attempt in all_attempts if attempt["status"] in {"candidate", "unavailable"}
    )
    failed_attempts = len(all_attempts) - usable_attempts
    report: dict[str, Any] = {
        "evaluationVersion": FILL_QUALITY_STUDY_VERSION,
        "kind": "private-fill-quality-study",
        "scope": FILL_QUALITY_STUDY_SCOPE,
        "studyId": study_id,
        "recipeId": recipe_id,
        "status": "observed" if normalized else "unavailable",
        "uncertainty": {
            "fillQuality": FILL_QUALITY_UNCERTAINTY,
            "humanSolveProbability": "unmeasured",
            "clueFairness": "unmeasured",
            "playerEnjoyment": "unmeasured",
        },
        "inputs": {
            "requestedSeeds": requested,
            "observedSeeds": observed_seeds,
            "missingSeeds": [seed for seed in requested if seed not in observed_seeds],
            "caseCount": len(normalized),
            "maxSeeds": MAX_STUDY_SEEDS,
        },
        "summary": {
            "caseCount": len(normalized),
            "selectedCaseCount": selected_cases,
            "measuredAttemptCount": measured_total,
            "unavailableAttemptCount": len(all_attempts) - measured_total,
            "usableAttemptCount": usable_attempts,
            "failedOrRejectedAttemptCount": failed_attempts,
            "retryCount": _summary(retry_counts, len(normalized)),
            "meanScore": _summary(values("meanScore", measured), measured_total),
            "minimumScore": _summary(values("minimumScore", measured), measured_total),
            "entryCount": _summary(values("entryCount", measured), measured_total),
            "iffyCount": _summary(values("iffyCount", measured), measured_total),
            "weakCount": _summary(values("weakCount", measured), measured_total),
            "themeCount": _summary(values("themeCount", measured), measured_total),
            "selectedMeanScore": _summary(values("meanScore", selected_qualities), selected_total),
            "selectedIffyCount": _summary(values("iffyCount", selected_qualities), selected_total),
            "selectedWeakCount": _summary(values("weakCount", selected_qualities), selected_total),
            "weakWithoutCrossingCount": _summary(
                values("weakWithoutCrossingCount", measured), measured_total
            ),
            "selectedWeakWithoutCrossingCount": _summary(
                values("weakWithoutCrossingCount", selected_qualities), selected_total
            ),
        },
        "acceptance": {
            "status": "observed" if measured else "unavailable",
            "policy": "fewest-iffy-then-theme-floor-then-isolated-weak-then-weak-then-mean-then-min",
            "humanQualityGate": "not-applied",
            "reason": "native scores compare fixed-seed retries; they do not gate private play",
        },
        "cases": [
            {
                "seed": case["seed"],
                **({"recipe": case["recipe"]} if "recipe" in case else {}),
                **({"selectedAttempt": case["selectedAttempt"]} if "selectedAttempt" in case else {}),
                "attempts": [_project_attempt(attempt) for attempt in case["attempts"]],
            }
            for case in normalized
        ],
    }
    if metadata is not None:
        report["metadata"] = dict(_mapping(metadata, "metadata"))
    unsigned = dict(report)
    report["studyDigest"] = _digest(unsigned)
    return report


def compare_fill_quality_studies(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    left_label: str = "policy",
    right_label: str = "baseline",
    expected_seeds: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Compare selected measured attempts for the same fixed seeds.

    The two inputs are reports returned by :func:`evaluate_fill_quality_study`.
    Only seeds present in both reports and with a measured selected attempt are
    paired.  Deltas are ``left - right``; negative iffy/weak deltas and
    positive score deltas are mechanically better under that convention.  The
    result deliberately reports no winner beyond those paired observations.
    """

    left_report = _mapping(left, "left")
    right_report = _mapping(right, "right")
    for name, report in (("left", left_report), ("right", right_report)):
        if report.get("evaluationVersion") != FILL_QUALITY_STUDY_VERSION:
            raise ValueError(f"{name} is not a {FILL_QUALITY_STUDY_VERSION} report")
        if not isinstance(report.get("cases"), list):
            raise ValueError(f"{name}.cases must be an array")
    if not isinstance(left_label, str) or not left_label:
        raise ValueError("left_label must be a non-empty string")
    if not isinstance(right_label, str) or not right_label:
        raise ValueError("right_label must be a non-empty string")

    def selected_by_seed(
        report: Mapping[str, Any], path: str
    ) -> dict[int, Mapping[str, Any]]:
        result: dict[int, Mapping[str, Any]] = {}
        for index, raw_case in enumerate(report["cases"]):
            case = _mapping(raw_case, f"{path}.cases[{index}]")
            seed = _seed(case.get("seed"), f"{path}.cases[{index}].seed")
            if seed in result:
                raise ValueError(f"{path}.cases contains duplicate seed {seed}")
            selected_index = case.get("selectedAttempt")
            attempts = _list(case.get("attempts"), f"{path}.cases[{index}].attempts")
            if not isinstance(selected_index, int) or isinstance(selected_index, bool):
                continue
            if selected_index < 1 or selected_index > len(attempts):
                raise ValueError(
                    f"{path}.cases[{index}].selectedAttempt is outside attempts"
                )
            selected = _mapping(
                attempts[selected_index - 1],
                f"{path}.cases[{index}].attempts[{selected_index - 1}]",
            )
            quality = selected.get("quality")
            if isinstance(quality, Mapping) and quality.get("status") == "measured":
                result[seed] = _quality(quality, f"{path}.cases[{index}].selectedAttempt.quality")
        return result

    left_selected = selected_by_seed(left_report, "left")
    right_selected = selected_by_seed(right_report, "right")
    if expected_seeds is None:
        expected = sorted(set(left_selected) | set(right_selected))
    else:
        expected = [
            _seed(seed, f"expected_seeds[{index}]")
            for index, seed in enumerate(expected_seeds)
        ]
        if len(set(expected)) != len(expected):
            raise ValueError("expected_seeds must be unique")
    paired_seeds = [seed for seed in expected if seed in left_selected and seed in right_selected]

    def paired_values(name: str) -> list[dict[str, Any]]:
        rows = []
        for seed in paired_seeds:
            left_value = left_selected[seed][name]
            right_value = right_selected[seed][name]
            delta = float(left_value) - float(right_value)
            rows.append(
                {
                    "seed": seed,
                    "left": left_value,
                    "right": right_value,
                    "delta": _rounded(delta),
                }
            )
        return rows

    def direction_summary(
        rows: Sequence[Mapping[str, Any]], *, lower_is_better: bool
    ) -> dict[str, Any]:
        left_wins = right_wins = ties = 0
        for row in rows:
            delta = row["delta"]
            if delta == 0:
                ties += 1
            elif (delta < 0) == lower_is_better:
                left_wins += 1
            else:
                right_wins += 1
        return {
            "leftWins": left_wins,
            "rightWins": right_wins,
            "ties": ties,
            "paired": len(rows),
        }

    if paired_seeds:
        metric_rows = {
            name: paired_values(name)
            for name in ("meanScore", "minimumScore", "iffyCount", "weakCount", "themeCount")
        }
        metric_summary = {
            name: {
                "paired": len(rows),
                "meanDelta": _rounded(mean(row["delta"] for row in rows)),
                "minimumDelta": _rounded(min(row["delta"] for row in rows)),
                "maximumDelta": _rounded(max(row["delta"] for row in rows)),
                "direction": direction_summary(
                    rows,
                    lower_is_better=name in {"iffyCount", "weakCount"},
                ),
            }
            for name, rows in metric_rows.items()
        }
    else:
        metric_rows = {
            name: []
            for name in (
                "meanScore",
                "minimumScore",
                "iffyCount",
                "weakCount",
                "themeCount",
            )
        }
        metric_summary = {
            name: {
                "paired": 0,
                "meanDelta": None,
                "minimumDelta": None,
                "maximumDelta": None,
                "direction": {"leftWins": 0, "rightWins": 0, "ties": 0, "paired": 0},
            }
            for name in metric_rows
        }

    report: dict[str, Any] = {
        "evaluationVersion": FILL_QUALITY_COMPARISON_VERSION,
        "kind": "private-fill-quality-comparison",
        "scope": FILL_QUALITY_STUDY_SCOPE,
        "status": "observed" if paired_seeds else "unavailable",
        "labels": {
            "left": left_label,
            "right": right_label,
            "delta": "left-minus-right",
        },
        "uncertainty": {
            "fillQuality": FILL_QUALITY_UNCERTAINTY,
            "humanSolveProbability": "unmeasured",
            "clueFairness": "unmeasured",
            "playerEnjoyment": "unmeasured",
            "winnerClaim": "none",
        },
        "inputs": {
            "expectedSeeds": expected,
            "leftMeasuredSelectedSeeds": sorted(left_selected),
            "rightMeasuredSelectedSeeds": sorted(right_selected),
            "pairedSeeds": paired_seeds,
            "leftOnlySeeds": [
                seed
                for seed in expected
                if seed in left_selected and seed not in right_selected
            ],
            "rightOnlySeeds": [
                seed
                for seed in expected
                if seed in right_selected and seed not in left_selected
            ],
        },
        "summary": metric_summary,
        "pairedRows": metric_rows,
        "policy": {
            "humanQualityGate": "not-applied",
            "interpretation": "paired native xfill receipts only; no human-quality winner",
        },
    }
    report["comparisonDigest"] = _digest(dict(report))
    return report


def run_fixed_seed_fill_study(
    seeds: Sequence[int],
    runner: Callable[[int], Mapping[str, Any]],
    *,
    study_id: str = "native-local",
    recipe_id: str = "private-local-v1",
) -> dict[str, Any]:
    """Run an injected fixed-seed receipt producer and evaluate its results.

    ``runner`` owns runtime setup and returns either a full generation-shaped
    object containing ``fillQuality.qualityPolicy`` or a direct
    ``{"qualityPolicy": ...}`` object.  Keeping the callback injected makes
    this helper useful for a real local study while keeping CI deterministic.
    """

    if not isinstance(seeds, Sequence) or isinstance(seeds, (str, bytes)):
        raise ValueError("seeds must be a sequence of integers")
    if len(seeds) > MAX_STUDY_SEEDS:
        raise ValueError(f"study may contain at most {MAX_STUDY_SEEDS} seeds")
    normalized = [_seed(seed, f"seeds[{index}]") for index, seed in enumerate(seeds)]
    if len(set(normalized)) != len(normalized):
        raise ValueError("seeds must be unique")
    cases: list[dict[str, Any]] = []
    for index, seed in enumerate(normalized):
        result = runner(seed)
        generated = _mapping(result, f"runner result for seed {seed}")
        quality_policy = generated.get("qualityPolicy")
        if quality_policy is None and isinstance(generated.get("fillQuality"), Mapping):
            quality_policy = generated["fillQuality"].get("qualityPolicy")
        policy = _mapping(quality_policy, f"runner result for seed {seed}.qualityPolicy")
        attempts = policy.get("attempts")
        if not isinstance(attempts, list):
            raise ValueError(
                f"runner result for seed {seed}.qualityPolicy.attempts must be an array"
            )
        cases.append(
            {
                "seed": seed,
                "attempts": attempts,
                "selectedAttempt": policy.get("selectedAttempt"),
            }
        )
    return evaluate_fill_quality_study(
        cases,
        study_id=study_id,
        recipe_id=recipe_id,
        requested_seeds=normalized,
    )
