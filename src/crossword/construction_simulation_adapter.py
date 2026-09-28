"""Lab-only bridge to the sibling deterministic construction simulator.

The sibling simulator is an editorial diagnostic.  It consumes explicit,
caller-supplied familiarity/difficulty/letter-support estimates and does not
measure a player's behavior.  This adapter keeps that boundary visible in the
private product: incomplete estimates are ``not-invoked`` and unavailable
Node/package state is ``failed`` rather than being replaced with defaults.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Literal, Mapping, TypedDict, cast


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_SCRIPT = PROJECT_ROOT / "scripts" / "sibling-construction-simulation.cjs"
ADAPTER_VERSION = "sibling-construction-adapter-v1"
ESTIMATE_PROVENANCE_VERSION = "sibling-estimate-provenance-v1"
ESTIMATE_SOURCE = "caller-attested-assumptions"
ESTIMATE_UNCERTAINTY = "uncalibrated-assumptions-not-human-measurements"
ESTIMATE_FIELDS = ("clueFamiliarity", "entryDifficulty", "letterSupport")
# These fields are useful construction observations but are never allowed to
# become player estimates. Keep the list in the envelope so a later caller
# cannot silently blur the two evidence classes.
DERIVED_FILL_SIGNALS = (
    "fillScore",
    "needsFoothold",
    "meanScore",
    "minScore",
    "iffy",
    "weak",
)
SIMULATOR_PACKAGE = "@crossword/construction"
MAX_REQUEST_BYTES = 256 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
TIMEOUT_SECONDS = 8


class DerivedFillSignalEnvelope(TypedDict):
    status: Literal["excluded"]
    fields: list[str]
    reason: str


class EstimateProvenanceEnvelope(TypedDict):
    """Caller attestation for the three simulator inputs.

    This envelope records where the assumptions came from; it is not a
    verification of the caller or a calibration result. In particular, the
    excluded fill signals are named explicitly so construction scores cannot
    be smuggled into player estimates later.
    """

    version: Literal["sibling-estimate-provenance-v1"]
    sourceKind: Literal["caller-attested-assumptions"]
    sourceId: str
    attestedBy: str
    calibrationStatus: Literal["uncalibrated"]
    estimateFields: list[str]
    assumptions: dict[str, str]
    derivedFillSignals: DerivedFillSignalEnvelope


class EstimateProvenanceBinding(TypedDict):
    version: Literal["sibling-estimate-provenance-v1"]
    sourceKind: Literal["caller-attested-assumptions"]
    calibrationStatus: Literal["uncalibrated"]
    envelope: EstimateProvenanceEnvelope
    envelopeDigest: str
    estimateDigest: str
    bindingDigest: str
    uncertainty: Literal["uncalibrated-assumptions-not-human-measurements"]


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


def _probability(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0 <= value <= 1
    )


def _entry_cells(raw: Mapping[str, Any]) -> tuple[tuple[int, int], ...] | None:
    row, col, length, direction = (
        raw.get("row"),
        raw.get("col"),
        raw.get("len"),
        raw.get("dir"),
    )
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


def _crossings(
    grid: Mapping[str, Any], entry_ids: set[str]
) -> list[dict[str, Any]] | None:
    raw_entries = grid.get("entries")
    if not isinstance(raw_entries, list):
        return None
    occupants: dict[tuple[int, int], list[tuple[str, int]]] = defaultdict(list)
    for raw in raw_entries:
        if not isinstance(raw, Mapping):
            return None
        entry_id = f"{raw.get('num')}{raw.get('dir')}"
        cells = _entry_cells(raw)
        if entry_id not in entry_ids or cells is None:
            continue
        for position, coordinate in enumerate(cells):
            occupants[coordinate].append((entry_id, position))
    result = []
    for values in occupants.values():
        if len(values) != 2:
            continue
        (left, left_position), (right, right_position) = sorted(values)
        result.append(
            {
                "entryId": left,
                "position": left_position,
                "otherEntryId": right,
                "otherPosition": right_position,
            }
        )
    return sorted(
        result,
        key=lambda item: (
            item["entryId"],
            item["position"],
            item["otherEntryId"],
            item["otherPosition"],
        ),
    )


def _normalize_estimate_envelope(
    value: Mapping[str, Any] | None,
) -> EstimateProvenanceEnvelope | None:
    """Validate the typed source boundary without granting it trust.

    The caller must explicitly say that the three numbers are editorial
    assumptions. A fill score, foothold flag, or aggregate xfill statistic is
    recorded as excluded evidence and cannot satisfy this boundary.
    """
    if not isinstance(value, Mapping):
        return None
    expected_keys = {
        "version",
        "sourceKind",
        "sourceId",
        "attestedBy",
        "calibrationStatus",
        "estimateFields",
        "assumptions",
        "derivedFillSignals",
    }
    if set(value) != expected_keys:
        return None
    if (
        value.get("version") != ESTIMATE_PROVENANCE_VERSION
        or value.get("sourceKind") != ESTIMATE_SOURCE
        or value.get("calibrationStatus") != "uncalibrated"
    ):
        return None
    source_id = value.get("sourceId")
    attested_by = value.get("attestedBy")
    if (
        not isinstance(source_id, str)
        or not source_id.strip()
        or len(source_id) > 160
        or not isinstance(attested_by, str)
        or not attested_by.strip()
        or len(attested_by) > 160
    ):
        return None
    estimate_fields = value.get("estimateFields")
    if not isinstance(estimate_fields, list) or estimate_fields != list(
        ESTIMATE_FIELDS
    ):
        return None
    assumptions = value.get("assumptions")
    if (
        not isinstance(assumptions, Mapping)
        or not assumptions
        or any(
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(item, str)
            or not item.strip()
            for key, item in assumptions.items()
        )
    ):
        return None
    derived = value.get("derivedFillSignals")
    if not isinstance(derived, Mapping) or set(derived) != {
        "status",
        "fields",
        "reason",
    }:
        return None
    if derived.get("status") != "excluded" or derived.get("reason") != (
        "construction-signals-never-become-player-estimates"
    ):
        return None
    derived_fields = derived.get("fields")
    if not isinstance(derived_fields, list) or derived_fields != list(
        DERIVED_FILL_SIGNALS
    ):
        return None
    return cast(
        EstimateProvenanceEnvelope,
        {
            "version": ESTIMATE_PROVENANCE_VERSION,
            "sourceKind": ESTIMATE_SOURCE,
            "sourceId": source_id.strip(),
            "attestedBy": attested_by.strip(),
            "calibrationStatus": "uncalibrated",
            "estimateFields": list(ESTIMATE_FIELDS),
            "assumptions": dict(sorted(assumptions.items())),
            "derivedFillSignals": {
                "status": "excluded",
                "fields": list(DERIVED_FILL_SIGNALS),
                "reason": ("construction-signals-never-become-player-estimates"),
            },
        },
    )


def _estimate_provenance_binding(
    envelope: EstimateProvenanceEnvelope,
    entries: list[Mapping[str, Any]],
    *,
    board_digest: str | None,
    source_digest: str | None,
) -> EstimateProvenanceBinding:
    """Bind the attestation to exactly the values sent to the simulator."""
    estimate_projection = [
        {
            "id": item["id"],
            "clueFamiliarity": item["clueFamiliarity"],
            "entryDifficulty": item["entryDifficulty"],
            "letterSupport": item["letterSupport"],
        }
        for item in entries
    ]
    envelope_digest = _digest(envelope)
    estimate_digest = _digest(estimate_projection)
    binding_digest = _digest(
        {
            "version": ESTIMATE_PROVENANCE_VERSION,
            "envelopeDigest": envelope_digest,
            "estimateDigest": estimate_digest,
            "boardDigest": board_digest if isinstance(board_digest, str) else None,
            "sourceDigest": source_digest if isinstance(source_digest, str) else None,
        }
    )
    return {
        "version": ESTIMATE_PROVENANCE_VERSION,
        "sourceKind": ESTIMATE_SOURCE,
        "calibrationStatus": "uncalibrated",
        "envelope": envelope,
        "envelopeDigest": envelope_digest,
        "estimateDigest": estimate_digest,
        "bindingDigest": binding_digest,
        "uncertainty": ESTIMATE_UNCERTAINTY,
    }


def _verified_estimate_provenance(
    request: Mapping[str, Any],
) -> EstimateProvenanceBinding | None:
    """Recompute the binding before allowing an externally supplied request."""
    raw = request.get("estimateProvenance")
    if not isinstance(raw, Mapping):
        return None
    envelope = _normalize_estimate_envelope(raw.get("envelope"))
    entries = request.get("entries")
    if envelope is None or not isinstance(entries, list):
        return None
    if any(
        not isinstance(item, Mapping)
        or not isinstance(item.get("id"), str)
        or not all(_probability(item.get(key)) for key in ESTIMATE_FIELDS)
        for item in entries
    ):
        return None
    try:
        expected = _estimate_provenance_binding(
            envelope,
            entries,
            board_digest=(
                request.get("boardDigest")
                if isinstance(request.get("boardDigest"), str)
                else None
            ),
            source_digest=(
                request.get("sourceDigest")
                if isinstance(request.get("sourceDigest"), str)
                else None
            ),
        )
    except (KeyError, TypeError):
        return None
    return expected if dict(raw) == expected else None


def build_simulation_request(
    grid: Mapping[str, Any],
    clue_entries: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    clues: Mapping[str, str],
    *,
    board_digest: str | None = None,
    source_digest: str | None = None,
    solve_threshold: float = 0.5,
    estimate_envelope: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build a request only when every entry carries explicit estimates.

    Missing estimates deliberately return ``None``. The caller must also
    provide a typed, digest-bound estimate envelope. Fill scores and
    ``needsFoothold`` are construction signals, not safe substitutes for the
    simulator's three estimate fields.
    """
    if (
        not isinstance(grid, Mapping)
        or not isinstance(clues, Mapping)
        or not _probability(solve_threshold)
    ):
        return None
    raw_entries = grid.get("entries")
    if not isinstance(raw_entries, list):
        return None
    raw_by_id = {}
    for raw in raw_entries:
        if not isinstance(raw, Mapping):
            return None
        entry_id = f"{raw.get('num')}{raw.get('dir')}"
        cells = _entry_cells(raw)
        answer = raw.get("answer")
        if (
            cells is None
            or not isinstance(answer, str)
            or not answer
            or entry_id in raw_by_id
        ):
            return None
        raw_by_id[entry_id] = (raw, cells)
    estimate_by_id = {}
    for item in clue_entries:
        if not isinstance(item, Mapping) or not isinstance(item.get("id"), str):
            return None
        estimate_by_id[item["id"]] = item
    if set(raw_by_id) != set(estimate_by_id):
        return None
    entries = []
    for entry_id in sorted(raw_by_id):
        raw, _cells = raw_by_id[entry_id]
        estimate = estimate_by_id[entry_id]
        text = clues.get(entry_id)
        if not isinstance(text, str) or not text.strip():
            return None
        if not all(_probability(estimate.get(key)) for key in ESTIMATE_FIELDS):
            return None
        entries.append(
            {
                "id": entry_id,
                "clue": text.strip(),
                "answer": raw["answer"],
                "clueFamiliarity": estimate["clueFamiliarity"],
                "entryDifficulty": estimate["entryDifficulty"],
                "letterSupport": estimate["letterSupport"],
            }
        )
    envelope = _normalize_estimate_envelope(estimate_envelope)
    if envelope is None:
        return None
    crossing_values = _crossings(grid, set(raw_by_id))
    if crossing_values is None:
        return None
    estimate_provenance = _estimate_provenance_binding(
        envelope,
        entries,
        board_digest=board_digest,
        source_digest=source_digest,
    )
    request = {
        "version": 1,
        "boardDigest": board_digest if isinstance(board_digest, str) else None,
        "sourceDigest": source_digest if isinstance(source_digest, str) else None,
        "entries": entries,
        "crossings": crossing_values,
        "solveThreshold": solve_threshold,
        # The sibling ignores this metadata; the adapter and receipt retain it
        # so the simulator result cannot be mistaken for an unbound estimate.
        "estimateProvenance": estimate_provenance,
    }
    if len(_canonical(request).encode("utf-8")) > MAX_REQUEST_BYTES:
        return None
    return request


def _invoke_bridge(request: Mapping[str, Any]) -> dict[str, Any]:
    node = shutil.which("node")
    if not node or not BRIDGE_SCRIPT.is_file():
        return {"status": "unavailable", "reason": "node-or-bridge-missing"}
    try:
        completed = subprocess.run(
            [node, str(BRIDGE_SCRIPT)],
            input=_canonical(request),
            text=True,
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            cwd=PROJECT_ROOT,
            env={"PATH": os.environ.get("PATH", "")},
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "unavailable", "reason": "bridge-did-not-respond"}
    if (
        len(completed.stdout.encode("utf-8")) + len(completed.stderr.encode("utf-8"))
        > MAX_RESPONSE_BYTES
    ):
        return {"status": "unavailable", "reason": "bridge-response-too-large"}
    try:
        value = json.loads(completed.stdout)
    except (ValueError, UnicodeDecodeError):
        return {"status": "unavailable", "reason": "bridge-returned-invalid-json"}
    if not isinstance(value, dict):
        return {"status": "unavailable", "reason": "bridge-returned-invalid-response"}
    return value


def run_sibling_simulation(request: Mapping[str, Any] | None) -> dict[str, Any]:
    """Run the sibling proxy and return an inspectable, digest-bound receipt."""
    verified_provenance = (
        _verified_estimate_provenance(request) if isinstance(request, Mapping) else None
    )
    base = {
        "version": ADAPTER_VERSION,
        "scope": "lab-only-private",
        "simulatorPackage": SIMULATOR_PACKAGE,
        "simulatorProtocol": "explicit-estimates-greedy-v1",
        "estimateSource": (
            verified_provenance.get("sourceKind")
            if isinstance(verified_provenance, Mapping)
            else None
        ),
        "estimateProvenanceDigest": (
            verified_provenance.get("bindingDigest")
            if isinstance(verified_provenance, Mapping)
            else None
        ),
        "uncertainty": ESTIMATE_UNCERTAINTY,
        "requestDigest": _digest(request) if isinstance(request, Mapping) else None,
        "resultDigest": None,
    }
    if isinstance(verified_provenance, Mapping):
        base["estimateProvenance"] = dict(verified_provenance)
    if not isinstance(request, Mapping):
        return {
            **base,
            "status": "not-invoked",
            "reason": "explicit-estimates-required",
        }
    if verified_provenance is None:
        return {
            **base,
            "status": "failed",
            "reason": "estimate-provenance-invalid",
        }
    response = _invoke_bridge(request)
    if response.get("status") != "invoked" or not isinstance(
        response.get("result"), Mapping
    ):
        return {
            **base,
            "status": "failed",
            "reason": str(response.get("reason") or "simulator-unavailable")[:160],
        }
    result = dict(response["result"])
    return {
        **base,
        "status": "invoked",
        "resultDigest": _digest(result),
        "simulator": response.get("simulator")
        if isinstance(response.get("simulator"), Mapping)
        else None,
        "result": result,
    }


def evaluate_sibling_adapter(
    grid: Mapping[str, Any],
    clue_entries: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    clues: Mapping[str, str],
    *,
    board_digest: str | None = None,
    source_digest: str | None = None,
    estimate_envelope: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Private-generation hook; absent explicit estimates is a clean no-op."""
    request = build_simulation_request(
        grid,
        clue_entries,
        clues,
        board_digest=board_digest,
        source_digest=source_digest,
        estimate_envelope=estimate_envelope,
    )
    return run_sibling_simulation(request)
