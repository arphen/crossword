import json
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRIDGE = PROJECT_ROOT / "scripts" / "episteme-reducer.cjs"


def run_bridge(payload):
    node = shutil.which("node")
    assert node is not None, "Node.js is required for the local reducer bridge test"
    result = subprocess.run(
        [node, str(BRIDGE)],
        input=json.dumps(payload, separators=(",", ":")),
        text=True,
        capture_output=True,
        cwd=PROJECT_ROOT,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_brief_operation_uses_fixed_compiler_and_is_deterministic():
    profile_id = "brief-bridge-profile"
    created_at = "2026-09-26T12:00:00.000Z"
    profile = run_bridge(
        {"operation": "create", "profileId": profile_id, "createdAt": created_at}
    )["profile"]
    evidence = {
        "evidenceId": "evidence:constellation-favorite",
        "recordedAt": created_at,
        "type": "explicit-preference",
        "concept": {"conceptId": "constellation", "label": "constellation"},
        "kind": "taste",
        "action": "seek",
        "scope": {},
        "supersedesEvidenceIds": [],
    }
    profile = run_bridge(
        {
            "operation": "apply",
            "profile": profile,
            "command": {
                "updateId": "update:constellation-favorite",
                "profileId": profile_id,
                "baseRevision": 0,
                "recordedAt": created_at,
                "evidence": [evidence],
                "evidenceActions": [],
            },
        }
    )["profile"]

    request = {
        "operation": "brief",
        "profile": profile,
        "candidates": [
            {
                "candidateId": "word:orion",
                "answer": "ORION",
                "language": "en",
                "conceptIds": ["constellation"],
                "knowledgeTaskIds": [],
                "associationIds": [],
                "pool": "exploration",
                "eligibility": {
                    "status": "eligible",
                    "packId": "synthetic-pack",
                    "packVersion": "test-v1",
                    "sourceIds": ["source:synthetic-orion"],
                },
            }
        ],
        "options": {
            "asOf": created_at,
            "mode": "play",
            "language": "en",
            "selectionLimit": 1,
        },
    }

    first = run_bridge(request)["brief"]
    second = run_bridge(request)["brief"]

    assert first == second
    assert first["profileId"] == profile_id
    assert first["profileRevision"] == 1
    assert len(first["selected"]) == 1
    selected = first["selected"][0]
    assert selected["candidate"]["candidateId"] == "word:orion"
    assert selected["selectedLane"] == "explicit-preference"
    assert selected["sourceIds"] == ["source:synthetic-orion"]
    assert selected["evidenceIds"] == ["evidence:constellation-favorite"]
    assert first["selectionLog"][0]["decision"] == "selected-ranked"


def test_brief_bridge_still_rejects_unknown_operations_and_input_paths():
    node = shutil.which("node")
    assert node is not None, "Node.js is required for the local reducer bridge test"
    result = subprocess.run(
        [node, str(BRIDGE)],
        input=json.dumps(
            {"operation": "require", "path": "../../outside.cjs", "code": "process.exit(0)"}
        ),
        text=True,
        capture_output=True,
        cwd=PROJECT_ROOT,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stderr) == {"error": "Unsupported operation"}
    assert result.stdout == ""
