"""Deterministic, private construction evidence for a completed answer grid.

This module is intentionally smaller than the sibling construction simulator.
It can run in the Flask worker without importing or launching the generator
repository.  Its output is a provenance receipt for structural review only:
it does not estimate a player's chance of solving an entry, semantic clue
fairness, or learning outcomes.
"""

from __future__ import annotations

from collections import defaultdict, deque
import hashlib
import json
from typing import Any, Mapping


EVIDENCE_VERSION = "private-construction-evidence-v1"
FOOTHOLD_SEED_PLAN_VERSION = "private-foothold-seed-plan-v1"
BOARD_DIGEST_ALGORITHM = "sha256-canonical-board-v1"
SIBLING_EVALUATOR = "@crossword/construction"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _entry_id(raw: Mapping[str, Any]) -> str | None:
    number = raw.get("num")
    direction = raw.get("dir")
    if type(number) is not int or direction not in {"A", "D"}:
        return None
    return f"{number}{direction}"


def _entry_cells(raw: Mapping[str, Any]) -> tuple[tuple[int, int], ...] | None:
    row, col, length = raw.get("row"), raw.get("col"), raw.get("len")
    direction = raw.get("dir")
    if (
        type(row) is not int
        or type(col) is not int
        or type(length) is not int
        or length < 1
        or row < 0
        or col < 0
        or direction not in {"A", "D"}
    ):
        return None
    if direction == "A":
        return tuple((row, col + offset) for offset in range(length))
    return tuple((row + offset, col) for offset in range(length))


def _board_projection(grid: Mapping[str, Any]) -> dict[str, Any]:
    fill = grid.get("fill")
    entries = grid.get("entries")
    return {
        "fill": list(fill) if isinstance(fill, list) else None,
        "entries": [
            {
                key: raw.get(key)
                for key in ("num", "dir", "row", "col", "len", "answer", "theme")
            }
            for raw in entries
            if isinstance(raw, Mapping)
        ],
    }


def _round(value: float) -> float:
    return round(value, 3)


def _foothold_seed_plan(
    parsed: Mapping[str, tuple[Mapping[str, Any], tuple[tuple[int, int], ...]]],
    edge_cells: Mapping[tuple[str, str], list[tuple[int, int]]],
    support_ids: Mapping[str, set[str]],
    metrics: list[Mapping[str, Any]],
    clue_by_id: Mapping[str, Mapping[str, Any]],
    clue_quality: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Choose structural neighbors that can seed weak entries.

    This is deliberately topology-only.  A non-foothold neighbor is merely a
    better candidate for an early crossing than another weak entry; its clue
    may still be difficult, and the receipt never estimates solve probability.
    """

    metric_by_id = {
        item.get("entryId"): item
        for item in metrics
        if isinstance(item, Mapping) and isinstance(item.get("entryId"), str)
    }
    quality_entries = (
        clue_quality.get("grounding", {}).get("entries", [])
        if isinstance(clue_quality, Mapping)
        and isinstance(clue_quality.get("grounding"), Mapping)
        else []
    )
    quality_by_id = {
        item.get("id"): item
        for item in quality_entries
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    records: list[dict[str, Any]] = []
    weak_entries = [
        entry_id
        for entry_id in sorted(parsed)
        if clue_by_id.get(entry_id, {}).get("needsFoothold") is True
    ]
    for target_id in weak_entries:
        candidates = []
        for support_id in sorted(support_ids.get(target_id, set())):
            target_pair = tuple(sorted((target_id, support_id)))
            cells = sorted(set(edge_cells.get(target_pair, [])))
            support_clue = clue_by_id.get(support_id, {})
            support_metric = metric_by_id.get(support_id, {})
            support_quality = quality_by_id.get(support_id, {})
            risk_flags = support_quality.get("riskFlags", [])
            risk_count = len(risk_flags) if isinstance(risk_flags, list) else 0
            support_status = support_quality.get("status")
            fallback = support_status == "crossing-scaffold"
            candidates.append(
                {
                    "entryId": support_id,
                    "cells": cells,
                    "needsFoothold": support_clue.get("needsFoothold") is True,
                    "crossingScore": support_metric.get("crossingScore"),
                    "length": support_metric.get("length"),
                    "riskCount": risk_count,
                    "fallback": fallback,
                }
            )
        # Prefer a structurally ordinary neighbor, then more crossing cells,
        # then a shorter entry as a stable tie-breaker.  These are ordering
        # heuristics only; no clue or answer text is emitted.
        candidates.sort(
            key=lambda item: (
                item["needsFoothold"],
                item["fallback"],
                item["riskCount"],
                -len(item["cells"]),
                -float(item["crossingScore"] or 0),
                item["length"] if isinstance(item["length"], int) else 10**6,
                item["entryId"],
            )
        )
        selected = candidates[0] if candidates else None
        if selected is None:
            records.append(
                {
                    "targetEntryId": target_id,
                    "status": "unseeded-no-crossing-neighbor",
                    "supportEntryId": None,
                    "crossingCells": [],
                    "uncertainty": "no-structural-neighbor",
                }
            )
            continue
        records.append(
            {
                "targetEntryId": target_id,
                "status": (
                    "candidate-nonweak-neighbor"
                    if not selected["needsFoothold"]
                    else "candidate-weak-neighbor"
                ),
                "supportEntryId": selected["entryId"],
                "crossingCells": [
                    {"row": row, "col": col}
                    for row, col in selected["cells"]
                ],
                "supportNeedsFoothold": selected["needsFoothold"],
                "supportCrossingScore": selected["crossingScore"],
                "supportSurfaceRisk": (
                    "flagged"
                    if selected["riskCount"]
                    else "answer-free-scaffold"
                    if selected["fallback"]
                    else "unflagged-or-unavailable"
                ),
                "uncertainty": "structural-neighbor-only",
            }
        )
    seeded = sum(
        item.get("status") == "candidate-nonweak-neighbor" for item in records
    )
    return {
        "version": FOOTHOLD_SEED_PLAN_VERSION,
        "status": "measured",
        "targetCount": len(weak_entries),
        "seededTargetCount": seeded,
        "unseededTargetCount": len(records) - seeded,
        "entries": records,
        "uncertainty": [
            "structural-neighbor-only",
            "clue-ease-unverified",
            "player-support-unmeasured",
        ],
        "interpretation": (
            "Candidate crossing seeds for weak entries; a neighbor is not an "
            "easy clue and this receipt is not a solve-probability estimate."
        ),
    }


def evaluate_private_board(
    grid: Mapping[str, Any],
    clue_entries: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] = (),
    *,
    source_digest: str | None = None,
    clue_quality: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic structural report for one private board.

    ``clue_entries`` contributes only explicit construction flags such as
    ``needsFoothold``; clue text is deliberately excluded.  A caller can
    compare reports for the same board through ``boardDigest`` and retain this
    artifact in local provenance.  The `siblingEvaluator` field is an explicit
    integration boundary: this host report does not invoke the TypeScript
    simulator because that package has no stable host CLI contract.
    """

    projection = _board_projection(grid if isinstance(grid, Mapping) else {})
    board_digest = _digest(projection)
    raw_entries = grid.get("entries") if isinstance(grid, Mapping) else None
    raw_entries = raw_entries if isinstance(raw_entries, list) else []
    clue_by_id = {
        item.get("id"): item
        for item in clue_entries
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }

    cells: dict[tuple[int, int], list[tuple[str, int]]] = defaultdict(list)
    parsed: dict[str, tuple[Mapping[str, Any], tuple[tuple[int, int], ...]]] = {}
    errors: list[str] = []
    for raw in raw_entries:
        if not isinstance(raw, Mapping):
            errors.append("entry-not-an-object")
            continue
        entry_id = _entry_id(raw)
        entry_cells = _entry_cells(raw)
        if entry_id is None:
            errors.append("entry-identity-invalid")
            continue
        if entry_id in parsed:
            errors.append(f"duplicate-entry:{entry_id}")
            continue
        if entry_cells is None:
            errors.append(f"entry-cells-invalid:{entry_id}")
            continue
        parsed[entry_id] = (raw, entry_cells)
        for position, coordinate in enumerate(entry_cells):
            cells[coordinate].append((entry_id, position))

    # A crossing is a pair of entries sharing one open coordinate. Multiple
    # entries at a cell are retained as an invalid topology signal rather than
    # silently flattening the structure.
    edge_cells: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    crossing_cells: dict[str, set[tuple[int, int]]] = defaultdict(set)
    support_ids: dict[str, set[str]] = defaultdict(set)
    for coordinate, occupants in sorted(cells.items()):
        if len(occupants) > 2:
            errors.append(
                f"cell-has-more-than-two-entries:{coordinate[0]}:{coordinate[1]}"
            )
        if len(occupants) != 2:
            continue
        (left, left_position), (right, right_position) = sorted(occupants)
        pair = (left, right)
        edge_cells[pair].append(coordinate)
        crossing_cells[left].add(coordinate)
        crossing_cells[right].add(coordinate)
        support_ids[left].add(right)
        support_ids[right].add(left)

    metrics = []
    weak_without_crossing = []
    isolated_entries = []
    scores = []
    for entry_id in sorted(parsed):
        raw, coordinates = parsed[entry_id]
        length = len(coordinates)
        crossing_count = len(crossing_cells[entry_id])
        score = _round(crossing_count / length) if length else 0.0
        scores.append(score)
        clue = clue_by_id.get(entry_id, {})
        needs_foothold = clue.get("needsFoothold") is True
        if needs_foothold and crossing_count == 0:
            weak_without_crossing.append(entry_id)
        if crossing_count == 0:
            isolated_entries.append(entry_id)
        metrics.append(
            {
                "entryId": entry_id,
                "length": length,
                "crossingCellCount": crossing_count,
                "crossingScore": score,
                "supportEntryIds": sorted(support_ids[entry_id]),
                "needsFoothold": needs_foothold,
                "structurallyIsolated": crossing_count == 0,
            }
        )

    # Connected components are deterministic topology facts. They are useful
    # for finding an island without suggesting that any player would stall.
    adjacency: dict[str, set[str]] = {entry_id: set() for entry_id in parsed}
    for left, right in edge_cells:
        adjacency[left].add(right)
        adjacency[right].add(left)
    components = []
    remaining = set(adjacency)
    while remaining:
        start = min(remaining)
        queue = deque([start])
        remaining.remove(start)
        component = []
        while queue:
            current = queue.popleft()
            component.append(current)
            for neighbor in sorted(adjacency[current]):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    queue.append(neighbor)
        components.append(sorted(component))
    components.sort(key=lambda item: item[0] if item else "")

    if not parsed:
        status = "unavailable"
    elif errors:
        status = "invalid-topology"
    else:
        status = "measured"

    flags = []
    if weak_without_crossing:
        flags.append("weak-entry-without-crossing")
    if isolated_entries:
        flags.append("isolated-entry")
    if len(components) > 1:
        flags.append("disconnected-entry-components")
    if errors:
        flags.append("topology-validation-error")

    return {
        "version": EVIDENCE_VERSION,
        "status": status,
        "scope": "private-local-board",
        "boardDigest": board_digest,
        "boardDigestAlgorithm": BOARD_DIGEST_ALGORITHM,
        "sourceDigest": source_digest if isinstance(source_digest, str) else None,
        "entryCount": len(parsed),
        "crossingCellCount": sum(len(items) for items in edge_cells.values()),
        "crossingEdgeCount": len(edge_cells),
        "minimumCrossingScore": min(scores) if scores else None,
        "meanCrossingScore": _round(sum(scores) / len(scores)) if scores else None,
        "entryMetrics": metrics,
        "components": components,
        "weakWithoutCrossing": sorted(weak_without_crossing),
        "isolatedEntries": sorted(isolated_entries),
        "footholdSeedPlan": _foothold_seed_plan(
            parsed,
            edge_cells,
            support_ids,
            metrics,
            clue_by_id,
            clue_quality,
        ),
        "flags": flags,
        "errors": sorted(set(errors)),
        "uncertainty": {
            "playerSupport": "unmeasured",
            "semanticFairness": "unverified",
            "humanPlaytest": "not-run",
            "siblingEvaluator": "not-invoked",
        },
        "siblingEvaluator": {
            "package": SIBLING_EVALUATOR,
            "status": "not-invoked",
            "reason": "no-stable-host-cli-contract",
            "availableInputs": "requires-explicit-familiarity-difficulty-letter-support-estimates",
        },
        "interpretation": (
            "Deterministic structural evidence for private construction review; "
            "crossing counts and components are not human solve probabilities."
        ),
    }
