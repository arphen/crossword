"""Deterministic tests for the bounded paired-model structural report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from src.crossword.model_evaluation import (
    MODEL_EVALUATION_REPORT_VERSION,
    build_model_evaluation_report,
    build_model_evaluation_report_from_bytes,
    canonical_model_evaluation_json,
)


ROOT = Path(__file__).resolve().parents[1]


def _fixture() -> dict:
    generation = {
        "temperature": 0,
        "seed": 7,
        "maxOutputTokens": 128,
        "thinking": False,
        "responseFormat": "json",
        "streaming": False,
        "contextLimit": 4096,
        "contextPolicy": "pinned-test-context",
    }
    models = [
        ("alpha:1b", "sha256:" + "a" * 64, "A clue", "valid", []),
        (
            "beta:1b",
            "sha256:" + "b" * 64,
            "échec",
            "invalid",
            ["language cue missing"],
        ),
    ]
    observations = []
    for sequence, (model, digest, output, gate_status, issues) in enumerate(models):
        observations.append(
            {
                "outputId": f"output-{sequence}",
                "fixtureId": f"fixture-{sequence}",
                "task": "task-a" if sequence == 0 else "task-b",
                "fixtureHash": "fixture-hash",
                "promptHash": f"prompt-{sequence}",
                "mode": "fixture",
                "responseSource": "fake",
                "sequence": sequence,
                "identity": {
                    "requestedModel": model,
                    "returnedModel": model,
                    "tagDigest": digest,
                    "parameterSize": "1B",
                    "quantizationLevel": "Q4_K_M",
                    "verified": True,
                },
                "rawOutput": output,
                "rawOutputHash": hashlib.sha256(output.encode()).hexdigest(),
                "contract": {"status": "valid", "issues": []},
                "taskConstraints": {"status": gate_status, "issues": issues},
                "wallMs": 10.5 if sequence == 0 else 20.25,
                "providerMetrics": {
                    "totalDurationNs": 10_000_000 if sequence == 0 else 20_000_000,
                    "evalCount": 4 + sequence,
                },
            }
        )
    return {
        "schemaVersion": 1,
        "runId": "fixture-run",
        "mode": "fixture",
        "dataset": "holdout-fixture",
        "reportKind": "paired-blind-comparison",
        "comparative": True,
        "fixtureHash": "fixture-hash",
        "requestedModels": ["alpha:1b", "beta:1b"],
        "generation": generation,
        "runtime": {"runner": "test"},
        "identityVerification": "test identity receipt",
        "observations": observations,
    }


def test_structural_report_separates_schema_gate_latency_and_output_size():
    report = build_model_evaluation_report(_fixture())
    assert report["evaluationVersion"] == MODEL_EVALUATION_REPORT_VERSION
    assert report["comparison"]["winnerClaim"] == "none"
    assert report["comparison"]["decisionStatus"] == "undecided"
    assert report["context"]["contextLimit"] == 4096
    assert report["context"] == report["generation"]

    alpha, beta = report["models"]
    assert alpha["schema"] == {"valid": 1, "invalid": 0, "total": 1, "rate": 1.0}
    assert alpha["taskGate"]["passed"] == 1
    assert alpha["taskGate"]["failed"] == 0
    assert alpha["latency"]["sum"] == 10.5
    assert alpha["outputSize"]["sum"] == len("A clue".encode())
    assert beta["schema"]["valid"] == 1
    assert beta["taskGate"]["failed"] == 1
    assert beta["taskGate"]["failures"][0]["issues"] == ["language cue missing"]
    assert beta["taskGate"]["issueCounts"] == {"language cue missing": 1}
    assert beta["outputSize"]["sum"] == len("échec".encode())
    assert beta["identity"]["tagDigests"] == ["sha256:" + "b" * 64]
    assert beta["identity"]["exactReceipts"][0]["returnedModel"] == "beta:1b"
    assert report["integrity"]["status"] == "valid"

    pending = report["semanticEditorial"]
    assert pending["status"] == "pending"
    assert pending["humanRatings"] == "pending"
    assert pending["winnerClaim"] == "none"
    assert {item["status"] for item in pending["fields"].values()} == {"pending"}


def test_structural_report_digest_and_source_byte_binding_are_repeatable(tmp_path):
    source = json.dumps(_fixture(), ensure_ascii=False, indent=2).encode("utf-8")
    first = build_model_evaluation_report_from_bytes(source)
    second = build_model_evaluation_report_from_bytes(source)
    assert first == second
    assert (
        first["source"]["sourceReportSha256"]
        == "sha256:" + hashlib.sha256(source).hexdigest()
    )
    unsigned = dict(first)
    unsigned.pop("reportDigest")
    expected = (
        "sha256:"
        + hashlib.sha256(canonical_model_evaluation_json(unsigned).encode()).hexdigest()
    )
    assert first["reportDigest"] == expected

    source_path = tmp_path / "holdout.json"
    source_path.write_bytes(source)
    output_path = tmp_path / "structural.json"
    process = subprocess.run(
        [
            "uv",
            "run",
            "--no-sync",
            "python",
            "scripts/model-evaluation-report.py",
            str(source_path),
            "--out",
            str(output_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    cli_report = json.loads(process.stdout)
    assert cli_report == json.loads(output_path.read_text(encoding="utf-8"))
    assert cli_report == first
