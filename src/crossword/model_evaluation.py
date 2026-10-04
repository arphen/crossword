"""Bounded structural reporting for the local model comparison harness.

The paired holdout runner already records the raw model receipts.  This module
projects that report into a small, deterministic artifact that can be checked
into an experiment directory or regenerated from a private holdout result.
It deliberately computes only mechanical measurements.  A valid JSON response
and a passing task gate are not a judgment about clue fairness, meaning,
language quality, or player enjoyment.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import math
from statistics import mean, median
from typing import Any


MODEL_EVALUATION_REPORT_VERSION = "model-evaluation-report-v1"
MODEL_EVALUATION_ARTIFACT_KIND = "private-model-structural-evaluation"
_MISSING = object()

SEMANTIC_EDITORIAL_FIELDS = (
    "semanticCoherence",
    "clueFairness",
    "sourceGrounding",
    "languageAccuracy",
    "playerResonance",
    "editorialPreference",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical(value)).hexdigest()}"


def canonical_model_evaluation_json(value: Any) -> str:
    """Return the stable serialization used for report digest checks."""

    return _canonical(value).decode("utf-8")


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be an array")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _status(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path}.status must be a non-empty string")
    return value


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be a number")
    if not math.isfinite(float(value)) or float(value) < 0:
        raise ValueError(f"{path} must be a finite non-negative number")
    return float(value)


def _rounded(value: float) -> float:
    """Keep reports readable while retaining sub-millisecond determinism."""

    return round(value, 3)


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "observed": 0,
            "missing": 0,
            "sum": 0,
            "mean": None,
            "median": None,
            "minimum": None,
            "maximum": None,
        }
    return {
        "observed": len(values),
        "missing": 0,
        "sum": _rounded(sum(values)),
        "mean": _rounded(mean(values)),
        "median": _rounded(median(values)),
        "minimum": _rounded(min(values)),
        "maximum": _rounded(max(values)),
    }


def _size_summary(values: list[int]) -> dict[str, Any]:
    if not values:
        return {
            "observed": 0,
            "missing": 0,
            "sum": 0,
            "mean": None,
            "median": None,
            "minimum": None,
            "maximum": None,
        }
    return {
        "observed": len(values),
        "missing": 0,
        "sum": sum(values),
        "mean": _rounded(mean(values)),
        "median": _rounded(median(values)),
        "minimum": min(values),
        "maximum": max(values),
    }


def _with_missing(summary: dict[str, Any], total: int) -> dict[str, Any]:
    result = dict(summary)
    result["missing"] = total - int(result["observed"])
    return result


def _provider_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counters = (
        "totalDurationNs",
        "loadDurationNs",
        "promptEvalCount",
        "promptEvalDurationNs",
        "evalCount",
        "evalDurationNs",
    )
    totals: dict[str, int] = {}
    observed = 0
    for row in rows:
        metrics = row.get("providerMetrics")
        if not isinstance(metrics, dict):
            continue
        observed += 1
        for name in counters:
            value = metrics.get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if not math.isfinite(float(value)) or float(value) < 0:
                continue
            totals[name] = totals.get(name, 0) + int(value)
    return {"observed": observed, "totals": totals}


def _identity_receipt(row: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    """Keep every identity field from the harness, with no digest rewriting."""

    return {
        "outputId": row["outputId"],
        "fixtureId": row["fixtureId"],
        "sequence": row.get("sequence"),
        "requestedModel": identity.get("requestedModel"),
        "returnedModel": identity.get("returnedModel"),
        "tagDigest": identity.get("tagDigest"),
        "parameterSize": identity.get("parameterSize"),
        "quantizationLevel": identity.get("quantizationLevel"),
        "verified": identity.get("verified"),
    }


def _model_order(requested: list[Any], observed: set[str]) -> list[str]:
    ordered: list[str] = []
    for value in requested:
        if isinstance(value, str) and value and value not in ordered:
            ordered.append(value)
    for value in sorted(observed):
        if value not in ordered:
            ordered.append(value)
    return ordered


def _semantic_editorial_pending() -> dict[str, Any]:
    return {
        "status": "pending",
        "fields": {
            name: {
                "status": "pending",
                "evidence": "independent-blind-editorial-or-player-review",
            }
            for name in SEMANTIC_EDITORIAL_FIELDS
        },
        "humanRatings": "pending",
        "winnerClaim": "none",
    }


def build_model_evaluation_report(
    full_report: dict[str, Any], *, source_report_sha256: str | None = None
) -> dict[str, Any]:
    """Build a digest-bound structural projection of a paired holdout report.

    ``full_report`` is the JSON object written by the existing paired harness.
    The optional source hash should be the SHA-256 of the exact source file
    bytes.  When omitted, the canonical JSON digest is used, which makes small
    in-memory fixtures convenient and still keeps the provenance explicit.
    """

    source = _object(full_report, "full_report")
    observations = _list(source.get("observations"), "full_report.observations")
    if not observations:
        raise ValueError("full_report.observations must not be empty")
    generation = deepcopy(_object(source.get("generation"), "full_report.generation"))
    runtime = deepcopy(_object(source.get("runtime"), "full_report.runtime"))
    requested_models = source.get("requestedModels", [])
    if not isinstance(requested_models, list):
        raise ValueError("full_report.requestedModels must be an array")

    source_digest = source_report_sha256
    if source_digest is None:
        source_digest = _digest(source)
    elif not isinstance(source_digest, str) or not source_digest:
        raise ValueError("source_report_sha256 must be a non-empty string")

    rows_by_model: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    observed_model_names: set[str] = set()
    duplicate_output_ids: list[str] = []
    output_ids: set[str] = set()
    raw_hash_mismatches: list[str] = []

    for index, raw_row in enumerate(observations):
        row = _object(raw_row, f"full_report.observations[{index}]")
        output_id = _string(row.get("outputId"), f"observations[{index}].outputId")
        if output_id in output_ids:
            duplicate_output_ids.append(output_id)
        output_ids.add(output_id)
        fixture_id = _string(row.get("fixtureId"), f"observations[{index}].fixtureId")
        identity = _object(row.get("identity"), f"observations[{index}].identity")
        requested_model = _string(
            identity.get("requestedModel"),
            f"observations[{index}].identity.requestedModel",
        )
        observed_model_names.add(requested_model)
        # The structural report is intentionally independent of any aggregate
        # task-gate summary shipped alongside the source artifact.
        contract = _object(row.get("contract"), f"observations[{index}].contract")
        _status(contract.get("status"), f"observations[{index}].contract")
        task_constraints = _object(
            row.get("taskConstraints"), f"observations[{index}].taskConstraints"
        )
        _status(
            task_constraints.get("status"), f"observations[{index}].taskConstraints"
        )
        raw_output = row.get("rawOutput")
        if not isinstance(raw_output, str):
            raise ValueError(f"observations[{index}].rawOutput must be a string")
        raw_output_hash = row.get("rawOutputHash")
        if isinstance(raw_output_hash, str):
            actual_hash = hashlib.sha256(raw_output.encode("utf-8")).hexdigest()
            if raw_output_hash.removeprefix("sha256:") != actual_hash:
                raw_hash_mismatches.append(output_id)
        # Retain the source row for metric calculation without mutating the
        # caller's object.  The report itself only carries bounded metadata.
        rows_by_model[requested_model].append(
            {
                **row,
                "_identity": deepcopy(identity),
                "_fixtureId": fixture_id,
                "_rawOutputBytes": len(raw_output.encode("utf-8")),
            }
        )

    models: list[dict[str, Any]] = []
    for model_name in _model_order(requested_models, observed_model_names):
        rows = rows_by_model.get(model_name, [])
        schema_valid_rows = [
            row
            for row in rows
            if _object(row["contract"], "contract").get("status") == "valid"
        ]
        gate_valid_rows = [
            row
            for row in rows
            if _object(row["taskConstraints"], "taskConstraints").get("status")
            == "valid"
        ]
        gate_failures = []
        issue_counts: Counter[str] = Counter()
        for row in rows:
            constraints = _object(row["taskConstraints"], "taskConstraints")
            if constraints.get("status") == "valid":
                continue
            issues = constraints.get("issues", [])
            if not isinstance(issues, list):
                raise ValueError(
                    f"taskConstraints.issues for {row['_fixtureId']} must be an array"
                )
            clean_issues = [issue for issue in issues if isinstance(issue, str)]
            issue_counts.update(clean_issues)
            gate_failures.append(
                {
                    "outputId": row["outputId"],
                    "fixtureId": row["_fixtureId"],
                    "task": row.get("task"),
                    "status": constraints.get("status"),
                    "issues": clean_issues,
                }
            )

        wall_values = []
        size_values: list[int] = []
        by_task: defaultdict[str, list[float]] = defaultdict(list)
        by_task_size: defaultdict[str, list[int]] = defaultdict(list)
        for row in rows:
            if row.get("wallMs") is not None:
                value = _number(row["wallMs"], f"observations.{row['outputId']}.wallMs")
                wall_values.append(value)
                if isinstance(row.get("task"), str):
                    by_task[row["task"]].append(value)
            size = row["_rawOutputBytes"]
            size_values.append(size)
            if isinstance(row.get("task"), str):
                by_task_size[row["task"]].append(size)

        latency = _with_missing(_summary(wall_values), len(rows))
        latency["metric"] = "runnerWallMs"
        latency["byTask"] = {task: _summary(by_task[task]) for task in sorted(by_task)}
        output_size = _size_summary(size_values)
        output_size["unit"] = "utf8Bytes"
        output_size["byTask"] = {
            task: _size_summary(by_task_size[task]) for task in sorted(by_task_size)
        }

        receipts = [_identity_receipt(row, row["_identity"]) for row in rows]
        returned_models = sorted(
            {
                receipt["returnedModel"]
                for receipt in receipts
                if isinstance(receipt["returnedModel"], str)
            }
        )
        tag_digests = sorted(
            {
                receipt["tagDigest"]
                for receipt in receipts
                if isinstance(receipt["tagDigest"], str)
            }
        )
        models.append(
            {
                "requestedModel": model_name,
                "observationCount": len(rows),
                "identity": {
                    "returnedModels": returned_models,
                    "tagDigests": tag_digests,
                    "allReturnedNamesMatchRequested": all(
                        receipt["returnedModel"] == model_name for receipt in receipts
                    ),
                    "allVerified": all(
                        receipt["verified"] is True for receipt in receipts
                    ),
                    "exactReceipts": receipts,
                },
                "schema": {
                    "valid": len(schema_valid_rows),
                    "invalid": len(rows) - len(schema_valid_rows),
                    "total": len(rows),
                    "rate": (len(schema_valid_rows) / len(rows)) if rows else None,
                },
                "taskGate": {
                    "passed": len(gate_valid_rows),
                    "failed": len(rows) - len(gate_valid_rows),
                    "total": len(rows),
                    "rate": (len(gate_valid_rows) / len(rows)) if rows else None,
                    "failures": gate_failures,
                    "issueCounts": {
                        issue: issue_counts[issue] for issue in sorted(issue_counts)
                    },
                },
                "latency": latency,
                "outputSize": output_size,
                "providerMetrics": _provider_summary(rows),
            }
        )

    unsigned: dict[str, Any] = {
        "schemaVersion": 1,
        "artifactKind": MODEL_EVALUATION_ARTIFACT_KIND,
        "evaluationVersion": MODEL_EVALUATION_REPORT_VERSION,
        "source": {
            "runId": source.get("runId"),
            "dataset": source.get("dataset"),
            "reportKind": source.get("reportKind"),
            "fixtureHash": source.get("fixtureHash"),
            "sourceReportSha256": source_digest,
            "observations": len(observations),
        },
        "comparison": {
            "paired": source.get("comparative") is True,
            "requestedModels": deepcopy(requested_models),
            "modelsObserved": len(models),
            "winnerClaim": "none",
            "decisionStatus": "undecided",
        },
        # Keep generation/context/runtime objects exactly as the harness wrote
        # them.  In particular, null contextLimit remains visible rather than
        # being turned into a false default.
        "generation": generation,
        "context": deepcopy(generation),
        "runtime": runtime,
        "identityVerification": source.get("identityVerification"),
        "models": models,
        "integrity": {
            "duplicateOutputIds": sorted(set(duplicate_output_ids)),
            "rawOutputHashesChecked": sum(
                1
                for row in observations
                if isinstance(row, dict) and isinstance(row.get("rawOutputHash"), str)
            ),
            "rawOutputHashMismatches": sorted(raw_hash_mismatches),
            "status": "valid"
            if not duplicate_output_ids and not raw_hash_mismatches
            else "needs-attention",
        },
        "semanticEditorial": _semantic_editorial_pending(),
        "limitations": [
            "Structural metrics are independent of semantic, editorial, and player judgments.",
            "Schema validity does not establish a correct answer, coherent theme, fair clue, source truth, language accuracy, or educational value.",
            "Task-gate failures are deterministic fixture failures, not a complete measure of model quality.",
            "Runner wall time is exploratory and depends on model load state, batching order, hardware, and the unpinned runtime context.",
            "Output size is measured from the returned UTF-8 text and does not measure model memory or GPU use.",
            "No semantic/editorial ratings or model winner are declared by this artifact.",
        ],
    }
    return {**unsigned, "reportDigest": _digest(unsigned)}


def build_model_evaluation_report_from_bytes(raw: bytes) -> dict[str, Any]:
    """Parse exact source bytes and bind the report to their byte digest."""

    if not isinstance(raw, bytes):
        raise TypeError("raw must be bytes")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("source report must be UTF-8 JSON") from error
    source_digest = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    return build_model_evaluation_report(value, source_report_sha256=source_digest)
