"""Future profiles use disposable SQLite and mocked local inference only."""
from uuid import uuid4
from unittest.mock import Mock

import pytest

from tests.test_api_isolated import api, no_network  # noqa: F401


def draft():
    return {"version": 1, "id": str(uuid4()), "step": 4, "object": "thread",
            "companion": "fork", "traces": ["echo", "moss"], "weekday": "thursday",
            "learningLanguage": "German", "excluded": ["tension"], "complete": True}


def create_profile(client, value):
    return client.put(
        f"/api/future/profile/{value['id']}",
        json=value,
        headers={"If-None-Match": "*"},
    )


def test_profile_is_persistent_isolated_and_provisional(api):
    client = api.app.test_client()
    value = draft()
    url = f"/api/future/profile/{value['id']}"
    assert client.get(url).status_code == 404
    response = create_profile(client, value)
    assert response.status_code == 200
    assert response.cache_control.no_store
    assert response.headers["ETag"] == f'"{response.json["updatedAt"]}"'
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
    assert restored.headers["ETag"] == response.headers["ETag"]
    assert client.get(f"/api/future/profile/{uuid4()}").status_code == 404
    assert client.get("/api/completed_puzzles").json == []
    update = client.put(
        url,
        json={**value, "weekday": "wednesday"},
        headers={"If-Match": response.headers["ETag"]},
    )
    assert update.status_code == 200
    assert update.headers["ETag"] != response.headers["ETag"]
    assert client.get(url).json["profile"]["weekday"] == "wednesday"


def test_profile_compare_and_swap_rejects_a_stale_writer_and_replays_exact_retries(api):
    client = api.app.test_client()
    value = draft()
    url = f"/api/future/profile/{value['id']}"

    created = create_profile(client, value)
    assert created.status_code == 200
    create_retry = create_profile(client, value)
    assert create_retry.status_code == 200
    assert create_retry.headers["ETag"] == created.headers["ETag"]

    snapshot = client.get(url)
    shared_etag = snapshot.headers["ETag"]
    writer_a = {**value, "weekday": "wednesday"}
    writer_b = {**value, "weekday": "monday"}
    winner = client.put(url, json=writer_a, headers={"If-Match": shared_etag})
    assert winner.status_code == 200

    stale_writer = client.put(url, json=writer_b, headers={"If-Match": shared_etag})
    assert stale_writer.status_code == 409
    assert stale_writer.headers["ETag"] == winner.headers["ETag"]
    assert stale_writer.json["updatedAt"] == winner.json["updatedAt"]

    update_retry = client.put(url, json=writer_a, headers={"If-Match": shared_etag})
    assert update_retry.status_code == 200
    assert update_retry.headers["ETag"] == winner.headers["ETag"]
    assert update_retry.json["profile"] == winner.json["profile"]
    assert client.get(url).json["profile"]["weekday"] == "wednesday"


def test_profile_writes_require_creation_or_revision_preconditions(api):
    client = api.app.test_client()
    value = draft()
    url = f"/api/future/profile/{value['id']}"

    missing_create_guard = client.put(url, json=value)
    assert missing_create_guard.status_code == 409
    assert client.get(url).status_code == 404

    created = create_profile(client, value)
    assert created.status_code == 200
    missing_update_guard = client.put(url, json={**value, "weekday": "monday"})
    wildcard_update_guard = client.put(
        url,
        json={**value, "weekday": "monday"},
        headers={"If-Match": "*"},
    )
    assert missing_update_guard.status_code == 409
    assert wildcard_update_guard.status_code == 409
    assert client.get(url).json["profile"]["weekday"] == value["weekday"]


@pytest.mark.parametrize("patch", [
    {"object": "unknown"}, {"object": []}, {"companion": "shell"},
    {"traces": ["echo"] * 4}, {"traces": ["echo", "echo"]}, {"traces": [{}]},
    {"step": True}, {"weekday": "never"}, {"excluded": "echo"},
    {"learningLanguage": "invented"}, {"complete": "true"},
    {"reflection": {"model": "test", "words": ["<script>"]}},
    {"calibrationId": "not-a-uuid"},
    {"variation": "not-a-catalog-color"},
    {"firstStimulus": "not-a-catalog-stimulus"},
    {"modelPreference": "untrusted:model"},
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
    response = create_profile(api.app.test_client(), value)
    assert response.json["profile"]["associations"] == []
    assert response.json["profile"]["observations"] == []


def test_non_legacy_first_stimulus_seeds_only_its_authored_associations(api):
    value = {
        **draft(),
        "object": None,
        "firstStimulus": "word-hush",
        "companion": None,
        "traces": [],
        "excluded": [],
    }

    response = create_profile(api.app.test_client(), value)

    assert response.status_code == 200
    profile = response.json["profile"]
    assert profile["observations"] == ["The English word hush."]
    assert profile["associations"] == ["quiet", "whisper", "pause", "sound", "silence"]
    assert profile["knowledge"] == {}
    assert profile["provisional"] is True


def test_calibration_identifier_and_explicit_visual_preferences_are_validated_and_saved(api):
    value = {
        **draft(),
        "calibrationId": str(uuid4()),
        "firstStimulus": "thread-knot",
        "variation": "color-cobalt",
        "presentationMode": "text-equivalent",
    }
    client = api.app.test_client()

    response = create_profile(client, value)

    assert response.status_code == 200
    saved = client.get(f"/api/future/profile/{value['id']}").json
    assert saved["draft"]["calibrationId"] == value["calibrationId"]
    assert "calibrationId" not in saved["profile"]
    assert saved["draft"]["variation"] == "color-cobalt"
    assert saved["draft"]["presentationMode"] == "text-equivalent"
    assert saved["profile"]["visualVariation"] == "color-cobalt"
    assert saved["profile"]["generationBrief"]["visualVariation"] == "color-cobalt"
    assert saved["profile"]["presentationMode"] == "text-equivalent"


def test_missing_visual_selection_does_not_become_an_explicit_preference(api):
    value = {
        **draft(),
        "object": None,
        "firstStimulus": None,
        "companion": None,
        "traces": [],
        "variation": None,
        "excluded": [],
    }

    response = create_profile(api.app.test_client(), value)

    assert response.status_code == 200
    profile = response.json["profile"]
    assert profile["observations"] == []
    assert profile["associations"] == []
    assert profile["visualVariation"] is None
    assert profile["generationBrief"]["visualVariation"] is None


def test_raw_calibration_payload_is_not_copied_into_the_episteme_profile(api):
    value = {
        **draft(),
        "calibrationEvents": [
            {
                "sequence": 1,
                "type": "observation",
                "stimulusId": "word-hush",
                "offered": [{"stimulusId": "word-hush", "position": 0}],
                "response": {"kind": "choose", "stimulusId": "word-hush"},
            }
        ],
    }
    client = api.app.test_client()

    response = create_profile(client, value)
    saved = client.get(f"/api/future/profile/{value['id']}").json

    assert response.status_code == 200
    assert "calibrationEvents" not in saved["draft"]
    assert "calibrationEvents" not in saved["profile"]
    assert "calibrationId" not in saved["profile"]
    assert "word-hush" not in saved["profile"]["associations"]
    assert saved["profile"]["observations"] == [
        "A red thread crossing itself in a loose curve.",
        "A tuning fork",
    ]


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
    assert create_profile(client, {**value, "reflection": response.json}).status_code == 200
    chat.return_value.json = lambda: {"message": {"content": '{"words":["bad <markup>"]}'}}
    assert client.post("/api/future/associations", json=value).status_code == 503


def test_gemma4_26b_is_the_first_fallback_when_qwen_is_unavailable(api, monkeypatch):
    from src.crossword import future

    monkeypatch.delenv("CROSSWORD_PROFILE_MODEL", raising=False)
    tags = Mock(return_value=Mock(json=lambda: {"models": [
        {"name": "gemma3:27b"}, {"name": "gemma4:26b"}, {"name": "gemma4:31b"},
    ]}))
    chat = Mock(return_value=Mock(json=lambda: {"message": {"content": '{"words":["weft"]}'}}))
    monkeypatch.setattr(future.requests, "get", tags)
    monkeypatch.setattr(future.requests, "post", chat)

    response = api.app.test_client().post("/api/future/associations", json=draft())

    assert response.status_code == 200
    assert chat.call_args.kwargs["json"]["model"] == "gemma4:26b"


def test_optional_inference_missing_model_is_recoverable(api, monkeypatch):
    from src.crossword import future

    monkeypatch.setattr(future.requests, "get", Mock(return_value=Mock(json=lambda: {"models": []})))
    assert api.app.test_client().post("/api/future/associations", json=draft()).status_code == 503
    assert api.app.test_client().post("/api/future/associations", json={}).status_code == 400
