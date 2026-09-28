"""Bounded answer-free studies for generated clue surfaces.

The private generator already records deterministic grammar, fallback, family,
signal, and timing receipts.  This module turns those receipts into a stable
study artifact without copying answers or clue text.  It deliberately reports
surface/mechanical observations only; semantic truth, editorial fairness, and
player support remain unmeasured.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
import math
from statistics import mean
from typing import Any


CLUE_QUALITY_STUDY_VERSION = "private-clue-quality-study-v1"
CLUE_QUALITY_STUDY_SCOPE = "answer-free-clue-surface-study"
CLUE_QUALITY_UNCERTAINTY = "clue-semantics-unreviewed"
MAX_STUDY_SEEDS = 32
MAX_FAMILY_COUNT = 32
_SEED_LIMIT = 2_147_483_647


def canonical_clue_quality_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_clue_quality_json(value).encode("utf-8")
    ).hexdigest()


def _seed(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= _SEED_LIMIT:
        raise ValueError(f"{path} must be between 0 and {_SEED_LIMIT}")
    return value


def _count(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{path} must be a non-negative integer")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be an object")
    return value


def _counts(value: Any, path: str) -> dict[str, int]:
    raw = _mapping(value, path)
    if len(raw) > MAX_FAMILY_COUNT:
        raise ValueError(f"{path} has too many keys")
    result: dict[str, int] = {}
    for key, item in raw.items():
        if not isinstance(key, str) or not key:
            raise ValueError(f"{path} keys must be non-empty strings")
        result[key] = _count(item, f"{path}.{key}")
    return dict(sorted(result.items()))


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
        raise ValueError(f"{path} must be finite and non-negative")
    return round(float(value), 3)


def clue_case_from_provenance(provenance: Mapping[str, Any], seed: int) -> dict[str, Any]:
    """Project one generated response into an answer-free study case."""

    source = _mapping(provenance, "provenance")
    quality = _mapping(source.get("clueQuality"), "provenance.clueQuality")
    diversity = _mapping(quality.get("diversity"), "provenance.clueQuality.diversity")
    bundle = _mapping(
        quality.get("groundedClueBundle"),
        "provenance.clueQuality.groundedClueBundle",
    )
    grammar = _mapping(
        bundle.get("grammarBridge"),
        "provenance.clueQuality.groundedClueBundle.grammarBridge",
    )
    entry_count = _count(
        bundle.get("entryCount"),
        "provenance.clueQuality.groundedClueBundle.entryCount",
    )
    family_counts = _counts(
        diversity.get("familyCounts", bundle.get("familyCounts")),
        "provenance.clueQuality.diversity.familyCounts",
    )
    non_definition = _count(
        diversity.get("nonDefinitionCount"),
        "provenance.clueQuality.diversity.nonDefinitionCount",
    )
    if sum(family_counts.values()) != entry_count:
        raise ValueError("clue family counts must add up to entryCount")
    if non_definition > entry_count:
        raise ValueError("nonDefinitionCount cannot exceed entryCount")
    observed_rate = (
        _number(
            diversity.get("nonDefinitionRate"),
            "provenance.clueQuality.diversity.nonDefinitionRate",
        )
        if "nonDefinitionRate" in diversity
        else round(non_definition / entry_count, 3) if entry_count else 0.0
    )
    families = diversity.get("nonDefinitionFamilies", [])
    if not isinstance(families, list) or not all(isinstance(item, str) and item for item in families):
        raise ValueError("nonDefinitionFamilies must be a list of names")
    if len(set(families)) != len(families):
        raise ValueError("nonDefinitionFamilies must not repeat names")
    required_family_set = diversity.get("requiredNonDefinitionFamilySet", [])
    if not isinstance(required_family_set, list) or not all(
        isinstance(item, str) and item for item in required_family_set
    ):
        raise ValueError("requiredNonDefinitionFamilySet must be a list of names")
    if len(set(required_family_set)) != len(required_family_set):
        raise ValueError("requiredNonDefinitionFamilySet must not repeat names")
    raw_missing_families = diversity.get("missingNonDefinitionFamilies")
    missing_families = raw_missing_families if raw_missing_families is not None else []
    if not isinstance(missing_families, list) or not all(
        isinstance(item, str) and item for item in missing_families
    ):
        raise ValueError("missingNonDefinitionFamilies must be a list of names")
    if len(set(missing_families)) != len(missing_families):
        raise ValueError("missingNonDefinitionFamilies must not repeat names")
    derived_missing_families = [
        family for family in required_family_set if family not in families
    ]
    if raw_missing_families is None:
        missing_families = derived_missing_families
    elif set(missing_families) != set(derived_missing_families):
        raise ValueError("missingNonDefinitionFamilies does not match the required family set")
    timings = source.get("timingsSeconds", {})
    timing_projection: dict[str, float] = {}
    if isinstance(timings, Mapping):
        for key in ("themeProposal", "nativeXfill", "clueGeneration", "clueChallenge", "total"):
            if key in timings:
                timing_projection[key] = _number(timings[key], f"provenance.timingsSeconds.{key}")
    clue_timings = source.get("clueGenerationTiming", {})
    clue_timing_projection: dict[str, float] = {}
    if isinstance(clue_timings, Mapping):
        for key in ("primaryWriter", "riskRepair", "diversityRepair", "safetyNormalization"):
            if key in clue_timings:
                clue_timing_projection[key] = _number(
                    clue_timings[key], f"provenance.clueGenerationTiming.{key}"
                )
    repair = diversity.get("repair", {})
    repair_projection = {}
    if isinstance(repair, Mapping):
        for key in ("attempted", "attemptCount", "selectedCount", "rewrittenCount", "postSafetyRepair", "minimumFamilies", "minimumClueCount"):
            if key in repair:
                value = repair[key]
                if isinstance(value, bool):
                    repair_projection[key] = value
                else:
                    repair_projection[key] = _count(value, f"provenance.clueQuality.diversity.repair.{key}")
        unavailable = repair.get("unavailableFamilies")
        if unavailable is not None:
            if (
                not isinstance(unavailable, list)
                or not unavailable
                or not all(isinstance(item, str) and item for item in unavailable)
                or len(set(unavailable)) != len(unavailable)
            ):
                raise ValueError(
                    "provenance.clueQuality.diversity.repair.unavailableFamilies "
                    "must be a non-empty list of unique names"
                )
            repair_projection["unavailableFamilies"] = sorted(unavailable)
        retry_status = repair.get("familyRetryStatus")
        if retry_status is not None:
            if retry_status != "bounded-exhausted":
                raise ValueError(
                    "provenance.clueQuality.diversity.repair.familyRetryStatus "
                    "must be bounded-exhausted"
                )
            repair_projection["familyRetryStatus"] = retry_status
    return {
        "seed": _seed(seed, "seed"),
        "entryCount": entry_count,
        "grammarCheckedCount": _count(grammar.get("checkedCount"), "grammarBridge.checkedCount"),
        "grammarIssueCount": _count(quality.get("issueCount"), "clueQuality.issueCount"),
        # Older private receipts omitted an explicit zero. Treat that legacy
        # shape as zero while requiring all present values to remain strict.
        "fallbackCount": _count(
            quality.get("fallbackCount", 0), "clueQuality.fallbackCount"
        ),
        "semanticStatus": _text(quality.get("diversity", {}).get("semanticStatus", "not-established"), "diversity.semanticStatus"),
        "familyCounts": family_counts,
        "nonDefinitionCount": non_definition,
        "nonDefinitionRate": observed_rate,
        "nonDefinitionFamilies": sorted(set(families)),
        "floorMet": diversity.get("floorMet") is True,
        "requiredNonDefinitionFamilies": _count(diversity.get("requiredNonDefinitionFamilies", 0), "diversity.requiredNonDefinitionFamilies"),
        "requiredNonDefinitionFamilySet": sorted(set(required_family_set)),
        "missingNonDefinitionFamilies": sorted(set(missing_families)),
        "requiredNonDefinitionClues": _count(diversity.get("requiredNonDefinitionClues", 0), "diversity.requiredNonDefinitionClues"),
        "targetNonDefinitionRate": (
            _number(
                diversity.get("targetNonDefinitionRate"),
                "provenance.clueQuality.diversity.targetNonDefinitionRate",
            )
            if "targetNonDefinitionRate" in diversity
            else None
        ),
        "targetNonDefinitionClues": (
            _count(
                diversity.get("targetNonDefinitionClues"),
                "provenance.clueQuality.diversity.targetNonDefinitionClues",
            )
            if "targetNonDefinitionClues" in diversity
            else None
        ),
        "signalCounts": _counts(quality.get("signalCounts", {}), "clueQuality.signalCounts"),
        "issueCounts": _counts(quality.get("issueCounts", {}), "clueQuality.issueCounts"),
        "semanticChallenge": _counts(
            _mapping(bundle.get("semanticChallenge", {}), "groundedClueBundle.semanticChallenge").get("classificationCounts", {}),
            "groundedClueBundle.semanticChallenge.classificationCounts",
        ),
        "repair": repair_projection,
        "timingsSeconds": timing_projection,
        "clueGenerationTimingSeconds": clue_timing_projection,
    }


def evaluate_clue_quality_study(
    cases: Sequence[Mapping[str, Any]],
    *,
    study_id: str = "fixture",
    recipe_id: str = "private-local-v1",
    requested_seeds: Sequence[int] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(study_id, str) or not study_id:
        raise ValueError("study_id must be a non-empty string")
    if not isinstance(recipe_id, str) or not recipe_id:
        raise ValueError("recipe_id must be a non-empty string")
    if len(cases) == 0 or len(cases) > MAX_STUDY_SEEDS:
        raise ValueError(f"cases must contain 1 to {MAX_STUDY_SEEDS} items")
    normalized = []
    seen: set[int] = set()
    for index, raw in enumerate(cases):
        value = _mapping(raw, f"cases[{index}]")
        seed = _seed(value.get("seed"), f"cases[{index}].seed")
        if seed in seen:
            raise ValueError("case seeds must be unique")
        seen.add(seed)
        normalized.append(dict(value))
    normalized.sort(key=lambda item: item["seed"])
    requested = [_seed(seed, "requestedSeeds") for seed in (requested_seeds or [item["seed"] for item in normalized])]
    if len(requested) > MAX_STUDY_SEEDS or len(set(requested)) != len(requested):
        raise ValueError("requestedSeeds must be unique and bounded")
    family_totals: Counter[str] = Counter()
    signal_totals: Counter[str] = Counter()
    issue_totals: Counter[str] = Counter()
    totals = Counter()
    total_times: list[float] = []
    floor_met_cases = 0
    grammar_clean_cases = 0
    target_rate_met_cases = 0
    target_rate_cases = 0
    family_floor_met_cases = 0
    for item in normalized:
        family_totals.update(item.get("familyCounts", {}))
        signal_totals.update(item.get("signalCounts", {}))
        issue_totals.update(item.get("issueCounts", {}))
        for key in ("entryCount", "grammarCheckedCount", "grammarIssueCount", "fallbackCount", "nonDefinitionCount"):
            totals[key] += int(item.get(key, 0))
        if item.get("floorMet") is True:
            floor_met_cases += 1
        if int(item.get("grammarIssueCount", 0)) == 0:
            grammar_clean_cases += 1
        required_families = item.get("requiredNonDefinitionFamilies")
        required_family_set = item.get("requiredNonDefinitionFamilySet", [])
        observed_families = item.get("nonDefinitionFamilies", [])
        if isinstance(observed_families, list):
            if isinstance(required_family_set, list) and required_family_set:
                if set(required_family_set).issubset(set(observed_families)):
                    family_floor_met_cases += 1
            elif isinstance(required_families, int) and len(observed_families) >= required_families:
                family_floor_met_cases += 1
        target_rate = item.get("targetNonDefinitionRate")
        if isinstance(target_rate, (int, float)) and not isinstance(target_rate, bool):
            target_rate_cases += 1
            if float(item.get("nonDefinitionRate", 0.0)) >= float(target_rate):
                target_rate_met_cases += 1
        total = item.get("timingsSeconds", {}).get("total")
        if total is not None:
            total_times.append(float(total))
    report = {
        "version": CLUE_QUALITY_STUDY_VERSION,
        "scope": CLUE_QUALITY_STUDY_SCOPE,
        "studyId": study_id,
        "recipeId": recipe_id,
        "requestedSeeds": requested,
        "observedSeeds": [item["seed"] for item in normalized],
        "missingSeeds": [seed for seed in requested if seed not in seen],
        "cases": normalized,
        "summary": {
            **dict(totals),
            "caseCount": len(normalized),
            "floorMetCases": floor_met_cases,
            "floorMetRate": round(floor_met_cases / len(normalized), 3),
            "grammarCleanCases": grammar_clean_cases,
            "grammarCleanRate": round(grammar_clean_cases / len(normalized), 3),
            "familyFloorMetCases": family_floor_met_cases,
            "targetRateCases": target_rate_cases,
            "targetRateMetCases": target_rate_met_cases,
            "observedNonDefinitionRate": round(
                totals["nonDefinitionCount"] / totals["entryCount"], 3
            )
            if totals["entryCount"]
            else 0.0,
            "familyCounts": dict(sorted(family_totals.items())),
            "signalCounts": dict(sorted(signal_totals.items())),
            "issueCounts": dict(sorted(issue_totals.items())),
            "totalTimingSeconds": round(sum(total_times), 3),
            "meanTimingSeconds": round(mean(total_times), 3) if total_times else None,
        },
        "metadata": dict(metadata or {}),
        "interpretation": "surface-and-mechanical-receipts-only; no semantic-or-player-quality-claim",
        "uncertainty": [
            CLUE_QUALITY_UNCERTAINTY,
            "player-support-unmeasured",
            "local-model-output",
        ],
    }
    report["studyDigest"] = _digest(report)
    return report
