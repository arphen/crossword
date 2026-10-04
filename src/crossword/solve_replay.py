"""Bounded Python boundary to the shared deterministic TypeScript replay."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANALYZER_SCRIPT = PROJECT_ROOT / "scripts" / "solve-analyzer.cjs"
MAX_REPLAY_BYTES = 16 * 1024 * 1024
_PUBLICATION_GATE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class SolveReplayUnavailable(RuntimeError):
    """The local Node/TypeScript analyzer cannot be started."""


class SolveReplayRejected(ValueError):
    """The shared solve analyzer rejected this session replay."""


def analyze_solve_session(session, puzzle):
    """Reconstruct validated per-entry observations from a frozen host puzzle."""
    return _analyze_solve_session("analyze", session, puzzle)


def analyze_solve_session_v2(session, puzzle):
    """Replay against a strict PuzzleDocumentV2 candidate or published document."""
    return _analyze_solve_session("analyze-v2-document", session, puzzle)


def validate_solve_puzzle_v2(puzzle):
    """Strictly validate an explicit V2 document without invoking V1 replay."""
    _run_analyzer(
        {"operation": "validate-v2-document", "puzzle": puzzle},
        result_key="validation",
    )
    return puzzle


def evaluate_puzzle_v2_publication_gate(candidate, packet):
    """Assess V2 publication evidence without authenticating or publishing it.

    The shared gate is deliberately structural: reviewer and evidence claims
    remain unverified until a trusted host verifier is implemented.
    """
    evaluation = _run_analyzer(
        {
            "operation": "evaluate-v2-publication",
            "candidate": candidate,
            "packet": packet,
        },
        result_key="evaluation",
    )
    if (
        type(evaluation) is not dict
        or set(evaluation) != {"gateVersion", "candidateDigest", "status", "reasons"}
        or evaluation.get("gateVersion") != "puzzle-v2-publication-gate-v1"
        or not isinstance(evaluation.get("status"), str)
        or evaluation["status"] not in {"blocked", "evidence-unverified"}
        or (
            evaluation.get("candidateDigest") is not None
            and (
                not isinstance(evaluation["candidateDigest"], str)
                or _PUBLICATION_GATE_DIGEST.fullmatch(evaluation["candidateDigest"]) is None
            )
        )
        or type(evaluation.get("reasons")) is not list
        or not evaluation["reasons"]
        or any(
            type(reason) is not dict
            or set(reason) != {"code", "path", "message"}
            or any(not isinstance(reason.get(field), str) for field in ("code", "path", "message"))
            for reason in evaluation["reasons"]
        )
        or (
            evaluation["status"] == "evidence-unverified"
            and any(
                reason["code"] != "reviewer-evidence-unverified"
                for reason in evaluation["reasons"]
            )
        )
    ):
        raise SolveReplayUnavailable("The local publication gate returned invalid output")
    return evaluation


def _analyze_solve_session(operation, session, puzzle):
    return _run_analyzer(
        {"operation": operation, "session": session, "puzzle": puzzle},
        result_key="analysis",
    )


def _run_analyzer(payload, *, result_key):
    node = shutil.which("node")
    if not node or not ANALYZER_SCRIPT.is_file():
        raise SolveReplayUnavailable("The local solve analyzer is unavailable")
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    if len(serialized.encode("utf-8")) > MAX_REPLAY_BYTES:
        raise SolveReplayRejected("Solve session exceeds the replay limit")
    try:
        result = subprocess.run(
            [node, str(ANALYZER_SCRIPT)],
            input=serialized,
            text=True,
            capture_output=True,
            timeout=10,
            cwd=PROJECT_ROOT,
            env={"PATH": os.environ.get("PATH", "")},
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SolveReplayUnavailable("The local solve analyzer did not respond") from error
    if result.returncode != 0:
        try:
            payload = json.loads(result.stderr)
        except (ValueError, AttributeError):
            raise SolveReplayUnavailable("The local solve analyzer could not start") from None
        message = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(message, str):
            raise SolveReplayUnavailable("The local solve analyzer could not start")
        raise SolveReplayRejected(message[:240])
    try:
        response = json.loads(result.stdout)
        if type(response) is not dict or set(response) != {result_key}:
            raise ValueError("Unexpected analyzer response envelope")
        result = response[result_key]
    except (ValueError, KeyError, TypeError) as error:
        raise SolveReplayUnavailable("The local solve analyzer returned invalid output") from error
    return result
