"""Future profiles use disposable SQLite and mocked local inference only."""
from uuid import uuid4
from unittest.mock import Mock

import pytest

from tests.test_api_isolated import api, no_network  # noqa: F401


def draft():
    return {"version": 1, "id": str(uuid4()), "step": 4, "object": "thread",
            "companion": "fork", "traces": ["echo", "moss"], "weekday": "thursday",
            "learningLanguage": "German", "excluded": ["tension"], "complete": True}


def test_profile_is_persistent_isolated_and_provisional(api):
    client = api.app.test_client()
    value = draft()
    url = f"/api/future/profile/{value['id']}"
    assert client.get(url).status_code == 404
    response = client.put(url, json=value)
    assert response.status_code == 200
    assert response.cache_control.no_store
    profile = response.json["profile"]
    assert profile["weekday"] == "thursday"
    assert profile["knowledge"] == {}
    assert profile["provisional"] is True
    assert profile["associations"][:2] == ["echo", "moss"]
    assert "tension" not in profile["associations"]
    assert "resonance" in profile["associations"]
    assert profile["generationBrief"]["maximumSeedInfluence"] == 0.2
    with api.app.app_context():
        api.db.session.remove()
        api.db.engine.dispose()
    restored = api.app.test_client().get(url)
    assert restored.json["profile"] == profile
    assert client.get(f"/api/future/profile/{uuid4()}").status_code == 404
    assert client.get("/api/completed_puzzles").json == []
    assert client.put(url, json={**value, "weekday": "wednesday"}).status_code == 200
    assert client.get(url).json["profile"]["weekday"] == "wednesday"


@pytest.mark.parametrize("patch", [
    {"object": "unknown"}, {"object": []}, {"companion": "shell"},
    {"traces": ["echo"] * 4}, {"traces": ["echo", "echo"]}, {"traces": [{}]},
    {"step": True}, {"weekday": "never"}, {"excluded": "echo"},
    {"learningLanguage": "invented"}, {"complete": "true"},
    {"reflection": {"model": "test", "words": ["<script>"]}},
])
def test_profile_validation_does_not_write(api, patch):
    value = draft()
    url = f"/api/future/profile/{value['id']}"
    client = api.app.test_client()
    assert client.put(url, json={**value, **patch}).status_code == 400
    assert client.get(url).status_code == 404


def test_profile_limits_and_origin(api):
    value = draft()
    client = api.app.test_client()
    url = f"/api/future/profile/{value['id']}"
    assert client.put(url, json=value, headers={"Origin": "https://other.invalid"}).status_code == 403
    assert client.put(url, json={**value, "padding": "a" * 17000}).status_code == 413
    assert client.put(url, data="not json", content_type="application/json").status_code == 400
    assert client.get("/api/future/profile/invalid").status_code == 400


def test_skipping_is_a_valid_empty_profile(api):
    value = {**draft(), "object": None, "companion": None, "traces": [], "excluded": []}
    response = api.app.test_client().put(f"/api/future/profile/{value['id']}", json=value)
    assert response.json["profile"]["associations"] == []
    assert response.json["profile"]["observations"] == []


def test_optional_ollama_associations_are_bounded_and_never_persist_implicitly(api, monkeypatch):
    from src.crossword import future

    monkeypatch.setenv("CROSSWORD_PROFILE_MODEL", "test-model")
    tags = Mock(return_value=Mock(json=lambda: {"models": [{"name": "test-model"}]}))
    chat = Mock(return_value=Mock(json=lambda: {"message": {"content": '{"words":["harmonics","warp and weft"]}'}}))
    monkeypatch.setattr(future.requests, "get", tags)
    monkeypatch.setattr(future.requests, "post", chat)
    value = draft()
    client = api.app.test_client()
    response = client.post("/api/future/associations", json=value)
    assert response.status_code == 200
    assert response.json == {"words": ["harmonics", "warp and weft"], "model": "test-model"}
    assert chat.call_args.args[0] == "http://127.0.0.1:11434/api/chat"
    assert chat.call_args.kwargs["json"]["stream"] is False
    assert client.get(f"/api/future/profile/{value['id']}").status_code == 404
    assert client.put(f"/api/future/profile/{value['id']}", json={**value, "reflection": response.json}).status_code == 200
    chat.return_value.json = lambda: {"message": {"content": '{"words":["bad <markup>"]}'}}
    assert client.post("/api/future/associations", json=value).status_code == 503


def test_optional_inference_missing_model_is_recoverable(api, monkeypatch):
    from src.crossword import future

    monkeypatch.setattr(future.requests, "get", Mock(return_value=Mock(json=lambda: {"models": []})))
    assert api.app.test_client().post("/api/future/associations", json=draft()).status_code == 503
    assert api.app.test_client().post("/api/future/associations", json={}).status_code == 400
