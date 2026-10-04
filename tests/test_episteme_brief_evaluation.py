"""The host report is deterministic, digest-bound, and explicitly non-evaluative."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def _stable_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def test_seek_avoid_report_emits_digest_bound_metrics(tmp_path):
    output = tmp_path / "brief-evaluation.json"
    process = subprocess.run(
        ["node", "scripts/episteme-brief-evaluation.cjs", "--out", str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(process.stdout)
    assert json.loads(output.read_text()) == report
    assert report["evaluationVersion"] == "episteme-brief-evaluation-v1"
    assert report["fixtureVersion"] == "seek-avoid-synthetic-pack-v1"
    assert report["comparison"]["selectionDivergence"] == 0.4
    assert [item["metrics"]["duplicateAnswerCount"] for item in report["profiles"]] == [
        0,
        0,
    ]
    assert all(item["metrics"]["broadFloorSatisfied"] for item in report["profiles"])
    assert report["profiles"][0]["metrics"]["laneCounts"]["explicit-preference"] == 2
    assert report["profiles"][1]["metrics"]["hardExclusionCount"] == 2
    assert all(
        "player preference accuracy" in limitation
        or "synthetic" in limitation.lower()
        or "broad-content floor" in limitation
        for limitation in report["limitations"]
    )

    unsigned = dict(report)
    unsigned.pop("reportDigest")
    expected = hashlib.sha256(_stable_json(unsigned)).hexdigest()
    assert report["reportDigest"] == f"sha256:{expected}"

    second = subprocess.run(
        ["node", "scripts/episteme-brief-evaluation.cjs"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(second.stdout)["reportDigest"] == report["reportDigest"]
