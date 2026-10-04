"""Host replay must use the shared TypeScript analyzer and frozen manifest."""
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.crossword.legacy_manifest import to_puzzle_document
from src.crossword.solve_replay import (
    SolveReplayRejected,
    SolveReplayUnavailable,
    _run_analyzer,
    analyze_solve_session,
    analyze_solve_session_v2,
    evaluate_puzzle_v2_publication_gate,
)


V2_FIXTURE = Path(__file__).parent / "fixtures" / "personalized-review-v2.json"


def word_square():
    rows = ("CAT", "ARE", "TEN")
    entries = []
    for index, word in enumerate(rows):
        for direction in ("across", "down"):
            entries.append({
                "clue_number": (1 if index == 0 else index + 3) if direction == "across" else index + 1,
                "clue_text": f"Synthetic {direction} row {index + 1}: {word}",
                "direction": direction,
                "start_x": 0 if direction == "across" else index,
                "start_y": index if direction == "across" else 0,
                "characters": [{"letters": letter} for letter in word],
            })
    return {
        "metadata": {
            "date": "240101",
            "title": "Synthetic CI word square",
            "authors": ["CI fixture author"],
            "width": 3,
            "height": 3,
        },
        "entries": entries,
    }


def start_session(manifest):
    session_id = str(uuid4())
    profile_id = str(uuid4())
    puzzle_hash = manifest["integrity"]["value"]
    event = {
        "schemaVersion": 2,
        "eventId": str(uuid4()),
        "sessionId": session_id,
        "profileId": profile_id,
        "segmentId": str(uuid4()),
        "seq": 1,
        "elapsedMs": 0,
        "recordedAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "puzzleHash": puzzle_hash,
        "type": "session-started",
        "reason": "fresh",
    }
    return {
        "schemaVersion": 2,
        "sessionId": session_id,
        "profileId": profile_id,
        "puzzleHash": puzzle_hash,
        "initialGrid": [
            {"cellId": cell["id"], "token": None, "origin": "unknown"}
            for cell in manifest["cells"]
            if not cell["block"]
        ],
        "events": [event],
    }


def test_host_bridge_replays_session_against_the_shared_manifest():
    manifest = to_puzzle_document(word_square())
    analysis = analyze_solve_session(start_session(manifest), manifest)

    assert analysis["schemaVersion"] == 1
    assert analysis["analysisVersion"] == "knowledge-reducer-v1"
    assert analysis["observations"]
    assert {item["outcome"] for item in analysis["observations"]} == {"untouched"}


def test_host_bridge_rejects_mismatched_puzzle_digest():
    manifest = to_puzzle_document(word_square())
    session = start_session(manifest)
    session["puzzleHash"] = "0" * 64
    session["events"][0]["puzzleHash"] = session["puzzleHash"]

    with pytest.raises(SolveReplayRejected, match="puzzle hash does not match"):
        analyze_solve_session(session, manifest)


def test_v2_host_bridge_uses_explicit_document_operation_and_shared_reducer():
    document = json.loads(V2_FIXTURE.read_text(encoding="utf-8"))
    analysis = analyze_solve_session_v2(start_session(document), document)

    assert analysis["schemaVersion"] == 1
    assert analysis["analysisVersion"] == "knowledge-reducer-v1"
    assert analysis["puzzleHash"] == document["integrity"]["value"]
    assert len(analysis["observations"]) == len(document["entries"])
    assert {item["outcome"] for item in analysis["observations"]} == {"untouched"}


def test_v2_host_bridge_rejects_content_with_a_stale_digest():
    document = json.loads(V2_FIXTURE.read_text(encoding="utf-8"))
    session = start_session(document)
    document["title"] += " edited"

    with pytest.raises(SolveReplayRejected, match="integrity-mismatch"):
        analyze_solve_session_v2(session, document)


def test_v1_host_bridge_does_not_infer_v2_document_from_session_schema():
    document = json.loads(V2_FIXTURE.read_text(encoding="utf-8"))
    session = start_session(document)

    with pytest.raises(SolveReplayRejected, match="Invalid puzzle document"):
        analyze_solve_session(session, document)


def test_v2_publication_gate_returns_shared_blocked_evaluation_shape():
    document = json.loads(V2_FIXTURE.read_text(encoding="utf-8"))

    evaluation = evaluate_puzzle_v2_publication_gate(document, None)

    assert set(evaluation) == {"gateVersion", "candidateDigest", "status", "reasons"}
    assert evaluation["gateVersion"] == "puzzle-v2-publication-gate-v1"
    assert evaluation["candidateDigest"] == document["integrity"]["value"]
    assert evaluation["status"] == "blocked"
    assert evaluation["reasons"]
    assert all(set(reason) == {"code", "path", "message"} for reason in evaluation["reasons"])
    assert any(reason["code"] == "packet-missing-or-invalid" for reason in evaluation["reasons"])
    assert "playable" not in evaluation
    assert "publicationReceipt" not in evaluation


def test_v2_publication_gate_blocks_a_packet_for_a_different_candidate():
    document = json.loads(V2_FIXTURE.read_text(encoding="utf-8"))
    packet = {
        "schema": "puzzle-v2-publication-review-v1",
        "reviewId": "mismatched-review",
        "candidateDigest": f"sha256:{'2' * 64}",
        "createdAt": "2026-09-26",
        "sourceAttestations": [],
        "clueAdjudications": [],
        "crossingReview": None,
        "weekdayReview": None,
        "packetDigest": f"sha256:{'3' * 64}",
    }

    evaluation = evaluate_puzzle_v2_publication_gate(document, packet)

    assert evaluation["status"] == "blocked"
    assert any(reason["code"] == "candidate-digest-mismatch" for reason in evaluation["reasons"])


def test_v2_publication_gate_api_does_not_accept_client_verified_flag():
    document = json.loads(V2_FIXTURE.read_text(encoding="utf-8"))

    with pytest.raises(TypeError):
        evaluate_puzzle_v2_publication_gate(document, None, verified=True)

    with pytest.raises(SolveReplayRejected, match="accepts only candidate and packet"):
        _run_analyzer(
            {
                "operation": "evaluate-v2-publication",
                "candidate": document,
                "packet": None,
                "verified": True,
            },
            result_key="evaluation",
        )


def test_analyzer_bridge_rejects_unexpected_sibling_output(monkeypatch):
    import src.crossword.solve_replay as solve_replay

    monkeypatch.setattr(solve_replay.shutil, "which", lambda _name: "/usr/bin/node")
    monkeypatch.setattr(
        solve_replay.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout='{"evaluation":{},"extra":true}',
            stderr="",
        ),
    )

    with pytest.raises(SolveReplayUnavailable, match="invalid output"):
        _run_analyzer({"operation": "evaluate-v2-publication"}, result_key="evaluation")


@pytest.mark.parametrize(
    "evaluation",
    [
        {"gateVersion": "puzzle-v2-publication-gate-v1", "candidateDigest": None,
         "status": "blocked", "reasons": [], "extra": True},
        {"gateVersion": "puzzle-v2-publication-gate-v1", "candidateDigest": None,
         "status": ["blocked"], "reasons": [{"code": "x", "path": "", "message": "x"}]},
        {"gateVersion": "puzzle-v2-publication-gate-v1", "candidateDigest": None,
         "status": "published", "reasons": [{"code": "x", "path": "", "message": "x"}]},
        {"gateVersion": "puzzle-v2-publication-gate-v1", "candidateDigest": None,
         "status": "evidence-unverified",
         "reasons": [{"code": "packet-missing-or-invalid", "path": "packet", "message": "x"}]},
    ],
)
def test_v2_publication_gate_rejects_malformed_shared_evaluation(monkeypatch, evaluation):
    import src.crossword.solve_replay as solve_replay

    monkeypatch.setattr(solve_replay.shutil, "which", lambda _name: "/usr/bin/node")
    monkeypatch.setattr(
        solve_replay.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"evaluation": evaluation}),
            stderr="",
        ),
    )
    document = json.loads(V2_FIXTURE.read_text(encoding="utf-8"))

    with pytest.raises(SolveReplayUnavailable, match="invalid output"):
        evaluate_puzzle_v2_publication_gate(document, None)
