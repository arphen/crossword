"""Deterministic evaluation helpers for private weekday recipes.

This module is deliberately narrower than an editorial or player study.  It
checks the mechanical contract emitted by private Thursday generation and
keeps the unsupported Sunday format behind an explicit size/runtime gate.  It
does not infer semantic fairness, model quality, or solve probability.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


MECHANIC_EVALUATION_VERSION = "private-weekday-mechanic-evaluation-v1"
SUNDAY_SIZE_GATE_VERSION = "private-sunday-size-gate-v1"
TARGET_SUNDAY_WIDTH = 21
TARGET_SUNDAY_HEIGHT = 21


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _ordinary_answer(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.upper()
        and value.isalpha()
        and value.isascii()
    )


def _board_and_provenance(
    board: Mapping[str, Any], provenance: Mapping[str, Any] | None
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Accept either a generation-shaped object or its two direct parts."""
    nested_grid = board.get("grid")
    grid = nested_grid if isinstance(nested_grid, Mapping) else board
    nested_provenance = board.get("provenance")
    resolved_provenance = (
        provenance
        if isinstance(provenance, Mapping)
        else nested_provenance
        if isinstance(nested_provenance, Mapping)
        else {}
    )
    return grid, resolved_provenance


def _theme_entries(
    grid: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], list[str]]:
    raw_entries = grid.get("entries")
    if not isinstance(raw_entries, list):
        return [], ["grid-entries-missing"]
    entries: list[Mapping[str, Any]] = []
    errors: list[str] = []
    for index, raw in enumerate(raw_entries):
        if not isinstance(raw, Mapping):
            errors.append(f"entry-not-an-object:{index}")
            continue
        if raw.get("theme") is True:
            entries.append(raw)
    return entries, errors


def _mechanic_base(mechanic: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: mechanic.get(key)
        for key in ("status", "type", "affix", "position", "reason")
        if key in mechanic
    }


def evaluate_thursday_mechanic_board(
    board: Mapping[str, Any],
    provenance: Mapping[str, Any] | None = None,
    *,
    board_id: str = "fixture",
) -> dict[str, Any]:
    """Check one generated-style Thursday board against its typed mechanic.

    A validated mechanic must name every themed entry, contain at least two
    instances, and satisfy the declared shared prefix/suffix for every one.
    An unavailable mechanic is accepted only when the recipe explicitly
    falls back to an ordinary letter grid.  This function consumes structural
    provenance only; clue text and fill scores are intentionally ignored.
    """
    if not isinstance(board, Mapping):
        return {
            "version": MECHANIC_EVALUATION_VERSION,
            "scope": "private-local-evaluation",
            "boardId": board_id,
            "status": "fail",
            "reasonCodes": ["board-not-an-object"],
            "instances": [],
            "uncertainty": _uncertainty(),
        }

    grid, resolved_provenance = _board_and_provenance(board, provenance)
    mechanic = resolved_provenance.get("themeMechanic")
    recipe = resolved_provenance.get("weekdayRecipe")
    theme_entries, errors = _theme_entries(grid)
    if not isinstance(mechanic, Mapping):
        errors.append("theme-mechanic-missing")
        mechanic = {}
    if not isinstance(recipe, Mapping):
        errors.append("weekday-recipe-missing")
        recipe = {}

    board_digest = _digest(
        {
            "entries": [
                {
                    key: entry.get(key)
                    for key in ("num", "dir", "row", "col", "len", "answer", "theme")
                }
                for entry in theme_entries
            ],
            "recipe": dict(recipe),
            "mechanic": dict(mechanic),
        }
    )
    mechanic_status = mechanic.get("status")
    if mechanic_status == "unavailable":
        return _evaluate_fallback(
            board_id,
            board_digest,
            theme_entries,
            recipe,
            mechanic,
            errors,
        )
    if mechanic_status != "validated":
        errors.append("mechanic-status-not-validated")
        return _report(
            board_id,
            board_digest,
            "fail",
            _mechanic_base(mechanic),
            [],
            errors,
            recipe,
        )

    expected_type = mechanic.get("type")
    affix = mechanic.get("affix")
    position = mechanic.get("position")
    declared = mechanic.get("themeAnswers")
    if expected_type != "shared-affix":
        errors.append("unsupported-mechanic-type")
    if not (
        isinstance(affix, str)
        and 2 <= len(affix) <= 4
        and affix.isascii()
        and affix.isalpha()
        and affix == affix.upper()
    ):
        errors.append("affix-invalid")
    if position not in {"prefix", "suffix"}:
        errors.append("affix-position-invalid")
    if not isinstance(declared, list) or not declared:
        errors.append("declared-theme-answers-missing")
        declared_answers: list[str] = []
    else:
        declared_answers = [answer for answer in declared if isinstance(answer, str)]
        if len(declared_answers) != len(declared):
            errors.append("declared-theme-answer-invalid")
        if len(set(declared_answers)) != len(declared_answers):
            errors.append("declared-theme-answer-duplicate")
    if len(declared_answers) < 2:
        errors.append("fewer-than-two-mechanic-instances")

    actual_answers = [entry.get("answer") for entry in theme_entries]
    if len(actual_answers) != len(set(actual_answers)):
        errors.append("theme-entry-answer-duplicate")
    if set(actual_answers) != set(declared_answers):
        errors.append("declared-and-filled-theme-answers-differ")

    instances = []
    for answer in declared_answers:
        matching_entries = [
            entry for entry in theme_entries if entry.get("answer") == answer
        ]
        answer_valid = _ordinary_answer(answer)
        affix_valid = False
        if isinstance(affix, str) and position in {"prefix", "suffix"}:
            affix_valid = (
                answer.startswith(affix)
                if position == "prefix"
                else answer.endswith(affix)
            )
        if not answer_valid:
            errors.append(f"non-ordinary-theme-answer:{answer}")
        if not affix_valid:
            errors.append(f"affix-mismatch:{answer}")
        if not matching_entries:
            errors.append(f"theme-answer-not-in-grid:{answer}")
        instances.append(
            {
                "answer": answer,
                "entryIds": sorted(_entry_id(entry) for entry in matching_entries),
                "ordinaryLetterAnswer": answer_valid,
                "affixMatches": affix_valid,
            }
        )

    if recipe.get("themeMode") != "shared-affix":
        errors.append("recipe-theme-mode-mismatch")
    if recipe.get("gridMechanic") != "ordinary-letter-grid":
        errors.append("grid-mechanic-mismatch")
    status = "pass" if not errors else "fail"
    return _report(
        board_id,
        board_digest,
        status,
        _mechanic_base(mechanic) | {"themeAnswers": declared_answers},
        instances,
        errors,
        recipe,
    )


def _evaluate_fallback(
    board_id: str,
    board_digest: str,
    theme_entries: Sequence[Mapping[str, Any]],
    recipe: Mapping[str, Any],
    mechanic: Mapping[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    """Accept only the explicit ordinary-grid fallback contract."""
    instances = []
    for entry in theme_entries:
        answer = entry.get("answer")
        ordinary = _ordinary_answer(answer)
        if not ordinary:
            errors.append(f"fallback-non-ordinary-theme-answer:{answer}")
        instances.append(
            {
                "answer": answer,
                "entryIds": [_entry_id(entry)],
                "ordinaryLetterAnswer": ordinary,
                "affixMatches": None,
            }
        )
    if recipe.get("themeMode") != "standard-theme":
        errors.append("fallback-theme-mode-mismatch")
    if recipe.get("gridMechanic") != "ordinary-letter-grid":
        errors.append("fallback-grid-mechanic-mismatch")
    if not mechanic.get("reason"):
        errors.append("fallback-reason-missing")
    status = "fallback-safe" if not errors else "fail"
    return _report(
        board_id,
        board_digest,
        status,
        _mechanic_base(mechanic),
        instances,
        errors,
        recipe,
    )


def _entry_id(entry: Mapping[str, Any]) -> str:
    return f"{entry.get('num')}{entry.get('dir')}"


def _uncertainty() -> dict[str, str]:
    return {
        "semanticFairness": "unverified",
        "modelQuality": "not-measured",
        "playerSolveProbability": "unmeasured",
        "humanPlaytest": "not-run",
    }


def _report(
    board_id: str,
    board_digest: str,
    status: str,
    mechanic: Mapping[str, Any],
    instances: Sequence[Mapping[str, Any]],
    errors: Sequence[str],
    recipe: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "version": MECHANIC_EVALUATION_VERSION,
        "scope": "private-local-evaluation",
        "boardId": board_id,
        "boardDigest": board_digest,
        "status": status,
        "mechanic": dict(mechanic),
        "instanceCount": len(instances),
        "instances": list(instances),
        "recipe": {
            key: recipe.get(key)
            for key in ("id", "themeMode", "gridMechanic")
            if key in recipe
        },
        "reasonCodes": sorted(set(errors)),
        "uncertainty": _uncertainty(),
    }


def evaluate_thursday_mechanic_suite(
    boards: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Evaluate a stable, multi-instance fixture/generated board collection."""
    reports = [
        evaluate_thursday_mechanic_board(
            board,
            board_id=str(board.get("id", index))
            if isinstance(board, Mapping)
            else str(index),
        )
        for index, board in enumerate(boards)
    ]
    reports.sort(key=lambda report: report["boardId"])
    passed = sum(report["status"] == "pass" for report in reports)
    fallback_safe = sum(report["status"] == "fallback-safe" for report in reports)
    failed = len(reports) - passed - fallback_safe
    summary = {
        "pass": passed,
        "fallbackSafe": fallback_safe,
        "fail": failed,
        "boardCount": len(reports),
    }
    return {
        "version": MECHANIC_EVALUATION_VERSION,
        "scope": "private-local-evaluation",
        "status": "pass" if failed == 0 and reports else "fail",
        "summary": summary,
        "reports": reports,
        "suiteDigest": _digest(reports),
        "uncertainty": _uncertainty(),
    }


def evaluate_sunday_size_gate(
    weekday: str,
    width: int,
    height: int,
    capabilities: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail closed until native 21x21 construction and UI are both ready."""
    capabilities = capabilities if isinstance(capabilities, Mapping) else {}
    requested = {
        "weekday": weekday,
        "width": width,
        "height": height,
    }
    base = {
        "version": SUNDAY_SIZE_GATE_VERSION,
        "scope": "private-local-evaluation",
        "requested": requested,
        "target": {"width": TARGET_SUNDAY_WIDTH, "height": TARGET_SUNDAY_HEIGHT},
        "requiredCapabilities": ["nativeConstruction21x21", "solverUi21x21"],
    }
    if weekday != "sunday":
        return {**base, "status": "not-applicable", "enabled": True, "reasonCodes": []}
    if type(width) is not int or type(height) is not int or width < 1 or height < 1:
        return {
            **base,
            "status": "blocked",
            "enabled": False,
            "reasonCodes": ["invalid-grid-size"],
        }
    if (width, height) != (TARGET_SUNDAY_WIDTH, TARGET_SUNDAY_HEIGHT):
        return {
            **base,
            "status": "blocked",
            "enabled": False,
            "reasonCodes": ["sunday-requires-21x21"],
        }
    missing = [
        key
        for key in ("nativeConstruction21x21", "solverUi21x21")
        if capabilities.get(key) is not True
    ]
    if missing:
        return {
            **base,
            "status": "blocked",
            "enabled": False,
            "reasonCodes": ["sunday-size-engine-ui-gate-incomplete"],
            "missingCapabilities": missing,
        }
    return {**base, "status": "enabled", "enabled": True, "reasonCodes": []}
