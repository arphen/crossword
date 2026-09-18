"""Real Flask/SQLAlchemy integration, isolated from user DBs and live providers."""
import importlib.util
from pathlib import Path
import socket
from unittest.mock import Mock

import pytest
import requests
from sqlalchemy import text


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Live outbound network is disabled in isolated API tests")

    monkeypatch.setattr(requests.sessions.Session, "request", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture
def api(tmp_path, monkeypatch, no_network):
    database_path = tmp_path / "integration.sqlite"
    monkeypatch.setenv("CROSSWORD_DATABASE_URI", f"sqlite:///{database_path}")
    # Execute a fresh app module, even if another test has imported the normal
    # singleton already. Relative imports share models but bind a NEW Flask app.
    path = Path(__file__).resolve().parents[1] / "src/crossword/app.py"
    spec = importlib.util.spec_from_file_location("src.crossword._isolated_api", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.config.update(TESTING=True)
    with module.app.app_context():
        assert Path(module.db.engine.url.database) == database_path
        assert module.db.session.execute(text("SELECT count(*) FROM completed_puzzles")).scalar_one() == 0
    yield module
    with module.app.app_context():
        module.db.session.remove()
        module.db.engine.dispose()


def original_puzzle_text(date="240101"):
    return "\n\n".join([
        "SYNTHETIC", date, "Original integration word square", "CI fixture author",
        "3", "3", "3", "3", "CAT\nARE\nTEN",
        "Synthetic feline\nSynthetic plural verb\nSynthetic number after nine",
        "Synthetic down feline\nSynthetic down plural verb\nSynthetic down number",
    ])


def test_completion_crud_persists_across_clients(api):
    first = api.app.test_client()
    payload = {"puzzle_date": "240101", "title": "Original CI square",
               "authors": ["CI fixture author"], "weekday": "monday",
               "time_taken": 42, "score": 700}
    assert first.get("/api/completed_puzzles").json == []
    assert first.get("/api/completed_puzzles/240101").json == {"completed": False}
    created = first.post("/api/completed_puzzles", json=payload)
    assert created.status_code == 201
    record = created.json["data"]
    assert {key: record[key] for key in payload} == payload
    assert record["id"] > 0 and record["completed_at"]

    # Remove the ORM identity map and connection pool: a new request must read
    # the committed file-backed SQLite data, not a mock or a pending session.
    with api.app.app_context():
        api.db.session.remove()
        api.db.engine.dispose()
    second = api.app.test_client()
    assert second.get("/api/completed_puzzles/240101").json == {"completed": True, "data": record}
    assert second.get("/api/completed_puzzles").json == [record]
    duplicate = second.post("/api/completed_puzzles", json={**payload, "score": 999})
    assert duplicate.status_code == 200
    assert duplicate.json["data"] == record
    assert len(second.get("/api/completed_puzzles").json) == 1
    assert second.delete("/api/completed_puzzles/240101").status_code == 200
    assert first.get("/api/completed_puzzles/240101").json == {"completed": False}
    assert first.get("/api/completed_puzzles").json == []
    assert second.delete("/api/completed_puzzles/240101").status_code == 404


def test_completion_requires_date_without_writing(api):
    client = api.app.test_client()
    for payload in ({}, {"title": "Missing date"}):
        response = client.post("/api/completed_puzzles", json=payload)
        assert response.status_code == 400
        assert response.json == {"error": "puzzle_date is required"}
    assert client.get("/api/completed_puzzles").json == []


def test_by_date_uses_mock_provider_but_real_parser(api, monkeypatch):
    fetch = Mock(return_value=original_puzzle_text())
    monkeypatch.setattr(api.DataReader, "_fetch_data", fetch)
    response = api.app.test_client().get("/crossword_by_date/240101")
    assert response.status_code == 200
    fetch.assert_called_once_with("240101")
    puzzle = response.json
    assert puzzle["metadata"]["date"] == "240101"
    assert puzzle["metadata"]["authors"] == ["CI fixture author"]
    assert (puzzle["metadata"]["width"], puzzle["metadata"]["height"]) == (3, 3)
    assert len(puzzle["entries"]) == 6
    for direction in ("across", "down"):
        entries = [entry for entry in puzzle["entries"] if entry["direction"] == direction]
        assert ["".join(char["letters"] for char in entry["characters"]) for entry in entries] == ["CAT", "ARE", "TEN"]


def test_random_route_validates_weekday_and_parses_mock_provider(api, monkeypatch):
    from datetime import datetime

    fetch = Mock(return_value=original_puzzle_text())
    monkeypatch.setattr(api.DataReader, "_fetch_data", fetch)
    monkeypatch.setattr(api.random, "choice", lambda dates: datetime(2024, 1, 1))
    client = api.app.test_client()
    invalid = client.get("/random_crossword/not-a-day")
    assert invalid.status_code == 400
    fetch.assert_not_called()
    response = client.get("/random_crossword/monday")
    assert response.status_code == 200
    assert response.json["metadata"]["date"] == "240101"
    assert len(response.json["entries"]) == 6
    fetch.assert_called_once_with("240101")


def test_provider_failure_returns_error_without_completion(api, monkeypatch):
    monkeypatch.setattr(api.DataReader, "_fetch_data", Mock(side_effect=RuntimeError("synthetic provider unavailable")))
    client = api.app.test_client()
    response = client.get("/crossword_by_date/240101")
    assert response.status_code == 400
    assert response.json == {"error": "synthetic provider unavailable"}
    assert client.get("/api/completed_puzzles").json == []


@pytest.mark.parametrize("route", ["/", "/mobile/test/across", "/mobile/test/down"])
def test_react_shell_and_assets(api, tmp_path, monkeypatch, route):
    dist = tmp_path / "react"
    (dist / "assets").mkdir(parents=True)
    shell = '<div id="react-root"></div><script src="/assets/test.js"></script>'
    (dist / "index.html").write_text(shell)
    (dist / "assets/test.js").write_text('console.log("test");')
    monkeypatch.setattr(api, "REACT_DIST", str(dist))
    client = api.app.test_client()
    response = client.get(route)
    assert response.status_code == 200
    assert response.get_data(as_text=True) == shell
    assert response.cache_control.no_cache
    bundle = client.get("/assets/test.js")
    assert bundle.status_code == 200
    assert bundle.cache_control.immutable
    assert bundle.cache_control.max_age == 31536000
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/assets/../index.html").status_code == 404


@pytest.mark.parametrize("route", ["/", "/mobile/test/across"])
def test_missing_react_build_is_explicit(api, tmp_path, monkeypatch, route):
    monkeypatch.setattr(api, "REACT_DIST", str(tmp_path / "missing"))
    response = api.app.test_client().get(route)
    assert response.status_code == 503
    assert b"make react-assets" in response.data


def test_explicit_vue_fallbacks(api):
    client = api.app.test_client()
    for route in ("/legacy/", "/legacy/mobile/test/across"):
        response = client.get(route)
        assert response.status_code == 200
        assert b"react-root" not in response.data
        assert b"vue.js" in response.data


def test_harness_rejects_live_http():
    with pytest.raises(AssertionError, match="Live outbound network"):
        requests.get("https://example.invalid/never-contacted")
