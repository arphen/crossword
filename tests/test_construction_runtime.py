"""Host boundary checks for the extracted local full-size fill runtime."""

import json
import os
import subprocess
import sys
import time

import pytest

from src.crossword import construction_runtime as runtime


def _success(options):
    return {
        "version": 1,
        "result": {
            "engine": "xfill",
            "options": options,
            "durationMs": 12,
            "sourceDigest": "sha256:" + "a" * 64,
            "grid": {
                "fill": ["A" * 15 for _ in range(15)],
                "entries": [{"answer": "CAT"} for _ in range(50)],
            },
        },
    }


def _completed(stdout, returncode=0):
    return subprocess.CompletedProcess(
        args=["node", "local-runtime.mjs"],
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


def _configure_cli(monkeypatch, tmp_path):
    cli = tmp_path / "local-runtime.mjs"
    cli.write_text("", encoding="utf-8")
    monkeypatch.setattr(runtime, "RUNTIME_CLI", cli)
    monkeypatch.setattr(runtime.shutil, "which", lambda name: "/usr/bin/node")
    return cli


def test_host_invokes_fixed_cli_with_bounded_json_and_offline_environment(monkeypatch, tmp_path):
    cli = _configure_cli(monkeypatch, tmp_path)
    monkeypatch.setenv("HTTP_PROXY", "http://must-not-cross-runtime-boundary.invalid")
    calls = []
    options = {**runtime.DEFAULT_OPTIONS, "seed": 42}

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return _completed(json.dumps(_success(options), separators=(",", ":")))

    monkeypatch.setattr(runtime.subprocess, "run", run)
    result = runtime.generate_full_size_draft(seed=42)

    assert result["engine"] == "xfill"
    assert calls[0][0] == ["/usr/bin/node", str(cli)]
    assert json.loads(calls[0][1]["input"]) == {"version": 1, "options": options}
    assert calls[0][1]["env"]["CARGO_NET_OFFLINE"] == "true"
    assert "HTTP_PROXY" not in calls[0][1]["env"]
    assert calls[0][1]["timeout"] == runtime.RUNTIME_TIMEOUT_SECONDS


def test_host_accepts_explicit_sunday_21_by_21_options(monkeypatch, tmp_path):
    _configure_cli(monkeypatch, tmp_path)
    options = {**runtime.DEFAULT_OPTIONS, "seed": 42, "gridSize": 21}
    response = _success(options)
    response["result"]["grid"]["fill"] = ["A" * 21 for _ in range(21)]
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return _completed(json.dumps(response, separators=(",", ":")))

    monkeypatch.setattr(runtime.subprocess, "run", run)
    result = runtime.generate_full_size_draft(
        seed=42,
        options={"gridSize": 21},
    )

    assert result["options"]["gridSize"] == 21
    request = json.loads(calls[0][1]["input"])
    assert request["options"]["gridSize"] == 21


def test_host_accepts_relaxed_sunday_fill_uncertainty_budget(monkeypatch, tmp_path):
    _configure_cli(monkeypatch, tmp_path)
    options = {
        **runtime.DEFAULT_OPTIONS,
        "seed": 42,
        "gridSize": 21,
        "maxIffy": 100,
    }
    response = _success(options)
    response["result"]["grid"]["fill"] = ["A" * 21 for _ in range(21)]
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *args, **kwargs: _completed(json.dumps(response)),
    )

    result = runtime.generate_full_size_draft(
        seed=42, options={"gridSize": 21, "maxIffy": 100}
    )

    assert result["options"]["maxIffy"] == 100


def test_host_passes_only_configured_engine_root(monkeypatch, tmp_path):
    _configure_cli(monkeypatch, tmp_path)
    options = {**runtime.DEFAULT_OPTIONS, "seed": 9}
    calls = []
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda command, **kwargs: calls.append(kwargs) or _completed(json.dumps(_success(options))),
    )

    runtime.generate_full_size_draft(seed=9, engine_root="/opt/crossword/xfill")

    assert json.loads(calls[0]["input"])["engineRoot"] == "/opt/crossword/xfill"


@pytest.mark.parametrize("seed", [True, -1, 2_147_483_648, "42"])
def test_host_rejects_invalid_seed_before_launch(monkeypatch, seed):
    run = pytest.MonkeyPatch()
    try:
        run.setattr(runtime.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not launch"))
        with pytest.raises(runtime.FullSizeDraftRejected):
            runtime.generate_full_size_draft(seed=seed)
    finally:
        run.undo()


@pytest.mark.parametrize(
    "options",
    [
        {"candidates": 401},
        {"time": True},
        {"minScore": 90},
        {"maxIffy": -1},
        {"themes": ["TOO-LONG"]},
        {"unrecognized": 1},
    ],
)
def test_host_rejects_out_of_bounds_generation_options(monkeypatch, options):
    monkeypatch.setattr(runtime.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not launch"))
    with pytest.raises(runtime.FullSizeDraftRejected):
        runtime.generate_full_size_draft(seed=10, options=options)


def test_host_reports_missing_runtime_without_falling_back_to_lab_or_remote(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "RUNTIME_CLI", tmp_path / "missing.mjs")
    monkeypatch.setattr(runtime.shutil, "which", lambda name: "/usr/bin/node")

    with pytest.raises(runtime.FullSizeRuntimeUnavailable, match="unavailable"):
        runtime.generate_full_size_draft()


def test_host_handles_timeout_and_structured_runtime_failure(monkeypatch, tmp_path):
    _configure_cli(monkeypatch, tmp_path)

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(runtime.subprocess, "run", timeout)
    with pytest.raises(runtime.FullSizeRuntimeUnavailable, match="did not respond"):
        runtime.generate_full_size_draft()

    error_output = json.dumps({"version": 1, "error": {"message": "No fill met quality gates"}})
    monkeypatch.setattr(runtime.subprocess, "run", lambda *args, **kwargs: _completed(error_output, 1))
    with pytest.raises(runtime.FullSizeRuntimeUnavailable, match="No fill met quality gates"):
        runtime.generate_full_size_draft()


def test_cancellation_terminates_the_owned_runtime_process(monkeypatch, tmp_path):
    cli = _configure_cli(monkeypatch, tmp_path)

    class Process:
        pid = 444
        returncode = None

        def __init__(self):
            self.signals = []

        def poll(self):
            return self.returncode

        def send_signal(self, value):
            self.signals.append(value)
            self.returncode = -value

        def communicate(self, input=None, timeout=None):
            return "", ""

    process = Process()
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *args, **kwargs: process)
    signals = []
    if os.name == "posix":
        monkeypatch.setattr(runtime.os, "killpg", lambda pid, signal_number: signals.append((pid, signal_number)))

    with pytest.raises(runtime.FullSizeDraftCancelled):
        runtime.generate_full_size_draft(seed=17, cancel_requested=lambda: True)

    if os.name == "posix":
        assert [signal_number for _pid, signal_number in signals] == [
            runtime.signal.SIGTERM,
            runtime.signal.SIGKILL,
        ]
    else:
        assert process.signals == [runtime.signal.SIGTERM]


@pytest.mark.skipif(os.name != "posix", reason="POSIX process groups are required")
def test_host_cancellation_kills_real_runtime_descendants(tmp_path):
    marker = tmp_path / "child-marker.txt"
    child_script = "\n".join(
        [
            "import time",
            "from pathlib import Path",
            f"Path({str(marker)!r}).write_text('spawned')",
            "time.sleep(0.7)",
            f"Path({str(marker)!r}).write_text('survived')",
        ]
    )
    parent_script = "\n".join(
        [
            "import subprocess, sys, time",
            f"subprocess.Popen([sys.executable, '-c', {child_script!r}], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)",
            "while True: time.sleep(1)",
        ]
    )

    with pytest.raises(runtime.FullSizeDraftCancelled):
        runtime._run_cancellable(
            [sys.executable, "-c", parent_script],
            serialized="",
            environment=os.environ.copy(),
            cancel_requested=marker.exists,
        )

    time.sleep(0.8)
    assert marker.read_text(encoding="utf-8") == "spawned"


@pytest.mark.parametrize(
    "response",
    [
        "not json",
        json.dumps({"version": 2, "result": {}}),
        json.dumps({"version": 1, "result": {"engine": "xfill"}}),
    ],
)
def test_host_rejects_malformed_or_untrusted_runtime_output(monkeypatch, tmp_path, response):
    _configure_cli(monkeypatch, tmp_path)
    monkeypatch.setattr(runtime.subprocess, "run", lambda *args, **kwargs: _completed(response))

    with pytest.raises(runtime.FullSizeRuntimeUnavailable):
        runtime.generate_full_size_draft()


def test_host_rejects_oversized_runtime_output(monkeypatch, tmp_path):
    _configure_cli(monkeypatch, tmp_path)
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *args, **kwargs: _completed("x" * (runtime.MAX_RESPONSE_BYTES + 1)),
    )

    with pytest.raises(runtime.FullSizeRuntimeUnavailable, match="too large"):
        runtime.generate_full_size_draft()


def test_host_rejects_malformed_optional_native_token_cells(monkeypatch, tmp_path):
    _configure_cli(monkeypatch, tmp_path)
    options = {**runtime.DEFAULT_OPTIONS, "seed": 1}
    response = _success(options)
    response["result"]["grid"]["tokenCells"] = [{"displayToken": "ß"}]
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *args, **kwargs: _completed(json.dumps(response)),
    )

    with pytest.raises(runtime.FullSizeRuntimeUnavailable, match="token cells"):
        runtime.generate_full_size_draft()


def test_host_preserves_lexical_answers_with_explicit_cell_token_sequences(
    monkeypatch, tmp_path
):
    _configure_cli(monkeypatch, tmp_path)
    options = {**runtime.DEFAULT_OPTIONS, "seed": 1}
    entries = [
        {
            "num": 1,
            "dir": "A",
            "row": 0,
            "col": 0,
            "len": 3,
            "answer": "CSST",
            "cellTokens": ["C", "SS", "T"],
        }
    ]
    entries.extend(
        {
            "num": number,
            "dir": "D",
            "row": 0,
            "col": 14,
            "len": 1,
            "answer": "A",
        }
        for number in range(2, 51)
    )
    response = _success(options)
    response["result"]["grid"]["entries"] = entries
    response["result"]["grid"]["tokenCells"] = [
        {
            "row": 0,
            "column": 1,
            "displayToken": "ß",
            "fillToken": "SS",
            "source": "native-constructor-v1",
        }
    ]
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *args, **kwargs: _completed(json.dumps(response)),
    )

    result = runtime.generate_full_size_draft(seed=1)

    assert result["grid"]["entries"][0]["answer"] == "CSST"
    assert result["grid"]["entries"][0]["cellTokens"] == ["C", "SS", "T"]
