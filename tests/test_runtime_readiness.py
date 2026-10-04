"""Focused contract tests for the advisory local /future readiness report."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from tests.test_api_isolated import api, no_network  # noqa: F401
from src.crossword import runtime_readiness as readiness


def _heartbeat(
    path: Path, *, pid: int | None = None, age_seconds: float = 0, state="idle"
):
    stamp = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "pid": os.getpid() if pid is None else pid,
                "state": state,
                "heartbeatAt": stamp.isoformat().replace("+00:00", "Z"),
            }
        ),
        encoding="utf-8",
    )


def _tags_response(names):
    response = Mock()
    response.json.return_value = {"models": [{"name": name} for name in names]}
    response.raise_for_status.return_value = None
    return response


def test_readiness_reports_local_dependencies_without_leaking_paths_or_environment(
    api, monkeypatch, tmp_path
):
    root = tmp_path / "xfill-root"
    (root / "data").mkdir(parents=True)
    for filename in ("xwordlist.dict", "supplemental.txt"):
        (root / "data" / filename).write_text("CAT;90\n", encoding="utf-8")
    heartbeat = tmp_path / "worker-heartbeat.json"
    _heartbeat(heartbeat)
    monkeypatch.setenv("CROSSWORD_XFILL_ROOT", str(root))
    monkeypatch.setenv("CROSSWORD_FUTURE_WORKER_HEARTBEAT", str(heartbeat))
    monkeypatch.setenv("CROSSWORD_PROFILE_MODEL", "qwen3.8:27b")
    monkeypatch.setattr(
        readiness.requests, "get", Mock(return_value=_tags_response(["qwen3.8:27b", "unrelated-local-model"]))
    )

    response = api.app.test_client().get("/api/future/runtime-readiness")

    assert response.status_code == 200
    payload = response.json
    assert payload["version"] == "future-runtime-readiness-v1"
    assert payload["ready"] is True
    assert payload["process"] == {"ready": True, "databaseReachable": True}
    assert payload["ollama"]["reachable"] is True
    assert payload["ollama"]["status"] == "ready"
    assert payload["ollama"]["installedPreferredModels"] == ["qwen3.8:27b"]
    assert payload["xfill"] == {
        "configured": True,
        "available": True,
        "status": "ready",
        "runtimeCliAvailable": True,
        "wordlistAvailable": True,
        "supplementalAvailable": True,
    }
    assert payload["worker"]["status"] == "ready"
    assert payload["worker"]["available"] is True
    assert payload["queue"] == {"reachable": True, "queued": 0, "running": 0}
    serialized = response.get_data(as_text=True)
    assert str(root) not in serialized
    assert "CROSSWORD_PROFILE_MODEL" not in serialized
    assert "unrelated-local-model" not in serialized
    assert response.cache_control.no_store


def test_readiness_is_advisory_when_ollama_and_worker_are_unavailable(
    api, monkeypatch, tmp_path
):
    monkeypatch.delenv("CROSSWORD_XFILL_ROOT", raising=False)
    monkeypatch.setenv(
        "CROSSWORD_FUTURE_WORKER_HEARTBEAT", str(tmp_path / "missing.json")
    )
    failure = Mock(side_effect=readiness.requests.RequestException("offline"))
    monkeypatch.setattr(readiness.requests, "get", failure)

    response = api.app.test_client().get("/api/future/runtime-readiness")

    assert response.status_code == 200
    payload = response.json
    assert payload["ready"] is False
    assert payload["ollama"] == {
        "reachable": False,
        "status": "unreachable",
        "preferredModels": [
            "gemma4:26b",
            "qwen3.8:27b",
            "gemma4:31b",
            "gemma3:27b",
            "llama3.2:3b",
            "gemma3:4b",
        ],
        "installedPreferredModels": [],
    }
    assert payload["xfill"]["status"] == "not-configured"
    assert payload["xfill"]["available"] is False
    assert payload["worker"] == {
        "available": False,
        "status": "missing",
        "heartbeatFresh": False,
    }
    # No readiness probe creates or mutates a queue row.
    assert payload["queue"] == {"reachable": True, "queued": 0, "running": 0}


def test_readiness_marks_an_old_worker_heartbeat_stale(api, monkeypatch, tmp_path):
    heartbeat = tmp_path / "worker-heartbeat.json"
    _heartbeat(heartbeat, age_seconds=120, pid=999_999)
    monkeypatch.setenv("CROSSWORD_FUTURE_WORKER_HEARTBEAT", str(heartbeat))
    monkeypatch.setenv("CROSSWORD_XFILL_ROOT", str(tmp_path / "missing-xfill"))
    monkeypatch.setattr(
        readiness.requests, "get", Mock(return_value=_tags_response(["gemma4:26b"]))
    )

    payload = api.app.test_client().get("/api/future/runtime-readiness").json

    assert payload["worker"]["status"] == "stale"
    assert payload["worker"]["available"] is False
    assert payload["worker"]["heartbeatFresh"] is False
    assert payload["worker"]["processAlive"] is False


def test_readiness_guidance_names_installable_tags(api, monkeypatch, tmp_path):
    monkeypatch.delenv("CROSSWORD_XFILL_ROOT", raising=False)
    monkeypatch.setenv(
        "CROSSWORD_FUTURE_WORKER_HEARTBEAT", str(tmp_path / "missing.json")
    )
    monkeypatch.delenv("CROSSWORD_PUZZLE_MODEL", raising=False)
    monkeypatch.delenv("CROSSWORD_PROFILE_MODEL", raising=False)
    monkeypatch.setattr(
        readiness.requests, "get", Mock(return_value=_tags_response([]))
    )

    payload = api.app.test_client().get("/api/future/runtime-readiness").json

    assert payload["ollama"]["status"] == "no-preferred-model"
    assert payload["ollama"]["installedPreferredModels"] == []
    assert "ollama pull" in payload["ollama"]["guidance"]
    assert "llama3.2:3b" in payload["ollama"]["guidance"]
