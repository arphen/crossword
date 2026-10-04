"""Read-only local runtime doctor checks."""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

from scripts import runtime_doctor


def _engine(root: Path) -> None:
    for relative in (
        "Cargo.toml",
        "Cargo.lock",
        "crates/xfill-cli/src/bin/library.rs",
        "crates/xfill-cli/src/bin/theme.rs",
        "data/xwordlist.dict",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")


def test_runtime_archive_matches_lock_and_installed_cli():
    result = runtime_doctor._check_runtime_archive()

    assert result["ready"] is True
    assert result["status"] == "ready"
    assert result["version"] == "0.1.2"
    assert result["archiveIntegrity"].startswith("sha512-")


def test_protocol_smoke_loads_cli_without_invoking_generation(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            returncode=1,
            stdout='{"version":1,"error":{"message":"Unsupported protocol version; expected 1"}}\n',
            stderr="",
        )

    monkeypatch.setattr(
        runtime_doctor.shutil,
        "which",
        lambda command: "/usr/bin/node" if command == "node" else None,
    )
    monkeypatch.setattr(runtime_doctor.subprocess, "run", fake_run)

    result = runtime_doctor._check_runtime_cli()

    assert result == {"ready": True, "status": "ready", "protocolVersion": 1}
    assert calls[0][0][0][0] == "/usr/bin/node"
    assert '"version":0' in calls[0][1]["input"]


def test_xfill_engine_check_is_file_only_and_reports_missing_parts(
    monkeypatch, tmp_path
):
    root = tmp_path / "xfill"
    _engine(root)
    monkeypatch.setattr(
        runtime_doctor.shutil, "which", lambda command: "/usr/bin/" + command
    )

    ready = runtime_doctor._check_xfill_engine({"CROSSWORD_XFILL_ROOT": str(root)})
    assert ready == {"ready": True, "status": "ready"}

    (root / "Cargo.lock").unlink()
    missing = runtime_doctor._check_xfill_engine({"CROSSWORD_XFILL_ROOT": str(root)})
    assert missing["ready"] is False
    assert missing["status"] == "incomplete"
    assert missing["missing"] == ["Cargo.lock"]


def test_ollama_probe_only_reads_loopback_tags_and_keeps_preferred_order(monkeypatch):
    calls = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, timeout))
        return Response(
            json.dumps(
                {"models": [{"name": "qwen3.8:27b"}, {"name": "other"}]}
            ).encode()
        )

    monkeypatch.setattr(runtime_doctor, "urlopen", fake_urlopen)
    result = runtime_doctor._check_ollama(
        {
            "CROSSWORD_PUZZLE_MODEL": "qwen3.8:27b",
            "CROSSWORD_PROFILE_MODEL": "gemma4:26b",
        }
    )

    assert result["ready"] is True
    assert result["installedPreferredModels"] == ["qwen3.8:27b"]
    assert calls == [("http://127.0.0.1:11434/api/tags", 2.0)]


def test_ollama_probe_rejects_non_loopback_without_network(monkeypatch):
    called = False

    def fail(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("remote Ollama endpoint must not be contacted")

    monkeypatch.setattr(runtime_doctor, "urlopen", fail)
    result = runtime_doctor._check_ollama(
        {"CROSSWORD_OLLAMA_BASE_URL": "https://example.test"}
    )

    assert result["ready"] is False
    assert result["status"] == "loopback-only-url-required"
    assert called is False


def test_private_domain_hints_are_optional_when_unconfigured():
    result = runtime_doctor._check_private_domain_hints({})

    assert result == {
        "ready": True,
        "status": "not-configured",
        "optional": True,
        "termCount": 0,
        "placeableCount": 0,
    }


def test_private_domain_hints_report_loaded_metadata_without_terms(tmp_path):
    hints = tmp_path / "physics.json"
    hints.write_text(
        json.dumps(
            {
                "version": "private-domain-hints-v1",
                "domainId": "physics",
                "label": "Physics",
                "terms": ["BOHR", "ENTROPY", "QUARK"],
            }
        ),
        encoding="utf-8",
    )
    xfill = tmp_path / "xfill"
    (xfill / "data").mkdir(parents=True)
    (xfill / "data" / "xwordlist.dict").write_text(
        "BOHR;90\nENTROPY;90\nOTHER;90\n", encoding="utf-8"
    )

    result = runtime_doctor._check_private_domain_hints(
        {
            "CROSSWORD_PRIVATE_DOMAIN_HINTS": str(hints),
            "CROSSWORD_XFILL_ROOT": str(xfill),
        }
    )

    assert result["ready"] is True
    assert result["status"] == "loaded"
    assert result["domainId"] == "physics"
    assert result["label"] == "Physics"
    assert result["termCount"] == 3
    assert result["placeableCount"] == 2
    assert "terms" not in result


def test_private_domain_hints_make_malformed_configuration_visible(tmp_path):
    hints = tmp_path / "broken.json"
    hints.write_text("{\"version\":\"wrong\"}", encoding="utf-8")

    result = runtime_doctor._check_private_domain_hints(
        {"CROSSWORD_PRIVATE_DOMAIN_HINTS": str(hints)}
    )

    assert result["ready"] is False
    assert result["status"] == "unavailable"
    assert result["reason"] == "document-version-unsupported"
    assert result["termCount"] == 0
    assert result["placeableCount"] == 0
