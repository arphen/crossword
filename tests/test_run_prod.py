"""The production launcher serves the built app: boot ``make run-prod`` and hit it.

Regression guard for the run-prod 500: uvicorn is an ASGI server and the app
is Flask (WSGI), so every route under ``make run-prod`` returned ``500`` with
``TypeError: Flask.__call__() missing 1 required positional argument:
'start_response'``. The target now serves the WSGI app with gunicorn; this
test boots that exact target on an ephemeral port against a temporary SQLite
database and asserts the built shell and its hashed assets load.
"""

import http.client
import os
import re
import signal
import socket
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def loopback_only(monkeypatch):
    """Block outbound network, but allow the loopback server under test."""
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_create_connection = socket.create_connection

    def is_loopback(address):
        host = address[0] if isinstance(address, tuple) else address
        return host in ("127.0.0.1", "::1", "localhost")

    def connect(self, address):
        if is_loopback(address):
            return real_connect(self, address)
        raise AssertionError(f"Live outbound network is disabled in run-prod tests: {address!r}")

    def connect_ex(self, address):
        if is_loopback(address):
            return real_connect_ex(self, address)
        raise AssertionError(f"Live outbound network is disabled in run-prod tests: {address!r}")

    def create_connection(address, *args, **kwargs):
        if is_loopback(address):
            return real_create_connection(address, *args, **kwargs)
        raise AssertionError(f"Live outbound network is disabled in run-prod tests: {address!r}")

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "create_connection", create_connection)


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def get(port, path, timeout=10):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, response.read().decode("utf-8", "replace")
    finally:
        connection.close()


def test_run_prod_serves_built_app(tmp_path, monkeypatch, loopback_only):
    """``make run-prod`` boots and serves / plus its hashed assets with 200s."""
    port = free_port()
    database_path = tmp_path / "run-prod.sqlite"
    monkeypatch.setenv("CROSSWORD_DATABASE_URI", f"sqlite:///{database_path}")
    monkeypatch.setenv("CROSSWORD_PORT", str(port))
    log_path = tmp_path / "run-prod.log"

    with open(log_path, "w") as log:
        server = subprocess.Popen(
            ["make", "run-prod"],
            cwd=str(ROOT),
            env={**os.environ, "CROSSWORD_DATABASE_URI": f"sqlite:///{database_path}", "CROSSWORD_PORT": str(port)},
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            status, body = 0, ""
            bad_responses = 0
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    break
                try:
                    status, body = get(port, "/")
                    if status == 200:
                        break
                    # A booting server refuses connections; a server that
                    # answers with an error is deterministically broken, so
                    # fail fast instead of polling until the deadline.
                    bad_responses += 1
                    if bad_responses >= 3:
                        break
                except OSError:
                    time.sleep(0.5)
            assert server.poll() is None, f"run-prod exited early:\n{log_path.read_text()[-4000:]}"
            assert status == 200, f"GET / returned {status}:\n{body[:2000]}\n--- server log ---\n{log_path.read_text()[-4000:]}"
            assert "react-root" in body, f"GET / did not serve the built shell:\n{body[:2000]}"
            asset = re.search(r'src="(/assets/[^"]+\.js)"', body)
            assert asset, f"built shell references no hashed bundle:\n{body[:2000]}"
            asset_status, _ = get(port, asset.group(1))
            assert asset_status == 200, f"GET {asset.group(1)} returned {asset_status}"
        finally:
            try:
                os.killpg(os.getpgid(server.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                server.wait(timeout=20)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=20)
