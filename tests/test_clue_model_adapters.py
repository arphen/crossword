"""Tests for the clue-model adapters (G1).

Offline: ``requests.post`` is replaced everywhere. The properties that matter
are that the local request is unchanged, the cloud extension is off and
fail-closed by default, a dead provider degrades like any other failure, and
nothing answer-bearing or secret reaches the call trace.
"""

import json

import pytest
import requests

from crossword import clue_model as cm

ANSWER_MARKER = "XYLOPHONE"
SECRET = "sk-test-secret-value"
CLOUD_ENV = {
    "CROSSWORD_CLOUD_CLUE_ENABLED": "1",
    "CROSSWORD_CLOUD_CLUE_URL": "https://gateway.example.test/v1",
    "CROSSWORD_CLOUD_CLUE_API_KEY": SECRET,
}


class FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status = status
        self.content = json.dumps(body).encode("utf-8")

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"{self.status} error")

    def json(self):
        return self._body


def clue_messages(answer=ANSWER_MARKER):
    return [
        {"role": "system", "content": "Write one clue per entry."},
        {
            "role": "user",
            "content": json.dumps({"entries": [{"id": "1A", "answer": answer}]}),
        },
    ]


def call(**overrides):
    values = {
        "model": "llama3.2:3b",
        "messages": clue_messages(),
        "schema": {"type": "object"},
        "timeout": 5,
        "tokens": 10,
        "temperature": 0.5,
    }
    values.update(overrides)
    return cm.ChatCall(**values)


@pytest.fixture(autouse=True)
def _clean_state():
    cm.clear_trace()
    cm.clear_fixtures()
    yield
    cm.clear_trace()
    cm.clear_fixtures()


def test_plain_tags_resolve_to_the_local_runtime():
    assert isinstance(cm.resolve_adapter("llama3.2:3b"), cm.OllamaAdapter)
    assert isinstance(cm.resolve_adapter(None), cm.OllamaAdapter)
    assert isinstance(cm.resolve_adapter("gemma3:12b", {}), cm.OllamaAdapter)


def test_ollama_request_is_exactly_what_chat_always_sent(monkeypatch):
    seen = []

    def fake_post(url, timeout, json):
        seen.append((url, timeout, json))
        return FakeResponse({"message": {"content": "{}"}})

    monkeypatch.setattr(cm.requests, "post", fake_post)
    cm.OllamaAdapter().chat(call(seed=7, top_p=0.9, num_ctx=8192))
    url, timeout, body = seen[0]
    assert url == "http://127.0.0.1:11434/api/chat"
    assert timeout == (2, 5)
    assert body == {
        "model": "llama3.2:3b",
        "stream": False,
        "think": False,
        "format": {"type": "object"},
        "options": {
            "temperature": 0.5,
            "num_predict": 10,
            "top_p": 0.9,
            "num_ctx": 8192,
            "seed": 7,
        },
        "messages": clue_messages(),
    }
    cm.OllamaAdapter().chat(call())
    assert seen[1][2]["options"] == {"temperature": 0.5, "num_predict": 10}


def test_default_path_never_contacts_anything_but_loopback_ollama(monkeypatch):
    urls = []

    def fake_post(url, **_kwargs):
        urls.append(url)
        return FakeResponse({"message": {"content": "{}"}})

    monkeypatch.setattr(cm.requests, "post", fake_post)
    # Cloud variables set in the environment must not change what a plain tag does.
    for key, value in CLOUD_ENV.items():
        monkeypatch.setenv(key, value)
    adapter = cm.resolve_adapter("llama3.2:3b")
    cm.run_chat(adapter, call())
    assert urls == ["http://127.0.0.1:11434/api/chat"]


def test_cloud_is_off_unless_enabled_and_configured():
    with pytest.raises(cm.CloudDisabled):
        cm.resolve_adapter("cloud:muse", {})
    with pytest.raises(cm.CloudDisabled):
        cm.resolve_adapter("cloud:muse", {"CROSSWORD_CLOUD_CLUE_ENABLED": "0"})
    with pytest.raises(cm.CloudDisabled):
        cm.resolve_adapter("cloud:muse", {"CROSSWORD_CLOUD_CLUE_ENABLED": "1"})
    with pytest.raises(cm.CloudDisabled):
        cm.resolve_adapter("cloud:   ", CLOUD_ENV)
    assert isinstance(cm.resolve_adapter("cloud:muse", CLOUD_ENV), cm.OpenAICompatAdapter)


def test_configuration_errors_are_value_errors_so_callers_degrade():
    assert issubclass(cm.AdapterError, ValueError)
    assert issubclass(cm.CloudDisabled, cm.AdapterError)
    assert issubclass(cm.CloudPrivacyRefusal, cm.AdapterError)


@pytest.mark.parametrize(
    "url",
    [
        "http://gateway.example.test/v1",
        "https://user:pass@gateway.example.test/v1",
        "https://gateway.example.test/v1?token=abc",
        "ftp://gateway.example.test/v1",
        "not a url",
    ],
)
def test_cloud_endpoint_validation(url):
    env = {**CLOUD_ENV, "CROSSWORD_CLOUD_CLUE_URL": url}
    with pytest.raises(cm.AdapterError):
        cm.resolve_adapter("cloud:muse", env)


def test_cloud_call_requires_a_clue_purpose(monkeypatch):
    monkeypatch.setattr(cm.requests, "post", lambda *a, **k: pytest.fail("posted"))
    adapter = cm.resolve_adapter("cloud:muse", CLOUD_ENV)
    for purpose in (None, "theme", "profile-narrative", "reflection"):
        with pytest.raises(cm.CloudPrivacyRefusal):
            adapter.chat(call(model="cloud:muse", purpose=purpose))


def test_cloud_payload_must_be_clue_shaped(monkeypatch):
    monkeypatch.setattr(cm.requests, "post", lambda *a, **k: pytest.fail("posted"))
    adapter = cm.resolve_adapter("cloud:muse", CLOUD_ENV)
    leaky = [
        {"role": "user", "content": json.dumps({"entries": [], "profile": {"x": 1}})},
    ]
    prose = [{"role": "user", "content": "Tell me about the solver's week"}]
    listy = [{"role": "user", "content": json.dumps(["entries"])}]
    for messages in (leaky, prose, listy):
        with pytest.raises(cm.CloudPrivacyRefusal):
            adapter.chat(call(model="cloud:muse", purpose="clue-draft", messages=messages))


def test_cloud_call_posts_openai_shape_and_normalizes(monkeypatch):
    seen = []

    def fake_post(url, timeout, json, headers):
        seen.append((url, timeout, json, headers))
        return FakeResponse(
            {"choices": [{"message": {"content": '{"clues": []}'}}]}
        )

    monkeypatch.setattr(cm.requests, "post", fake_post)
    adapter = cm.resolve_adapter("cloud:muse", CLOUD_ENV)
    response = adapter.chat(
        call(model="cloud:muse", purpose="clue-draft", seed=3, top_p=0.8)
    )
    url, timeout, body, headers = seen[0]
    assert url == "https://gateway.example.test/v1/chat/completions"
    assert timeout == (2, 5)
    assert body["model"] == "muse"
    assert body["max_tokens"] == 10
    assert body["seed"] == 3 and body["top_p"] == 0.8
    assert body["response_format"] == {"type": "json_object"}
    assert headers["Authorization"] == f"Bearer {SECRET}"
    assert response.json() == {"message": {"content": '{"clues": []}'}}
    assert response.content == b'{"clues": []}'


@pytest.mark.parametrize(
    "body",
    [{}, {"choices": []}, {"choices": [{"message": {}}]}, {"choices": [{"message": {"content": 5}}]}],
)
def test_malformed_cloud_responses_are_value_errors(monkeypatch, body):
    monkeypatch.setattr(cm.requests, "post", lambda *a, **k: FakeResponse(body))
    adapter = cm.resolve_adapter("cloud:muse", CLOUD_ENV)
    with pytest.raises(ValueError):
        adapter.chat(call(model="cloud:muse", purpose="clue-draft"))


def test_oversized_cloud_response_is_refused(monkeypatch):
    big = {"choices": [{"message": {"content": "x" * (cm.MAX_RESPONSE_BYTES + 1)}}]}
    monkeypatch.setattr(cm.requests, "post", lambda *a, **k: FakeResponse(big))
    adapter = cm.resolve_adapter("cloud:muse", CLOUD_ENV)
    with pytest.raises(ValueError):
        adapter.chat(call(model="cloud:muse", purpose="clue-draft"))


def test_a_dead_provider_raises_the_errors_callers_already_handle(monkeypatch):
    def down(*_args, **_kwargs):
        raise requests.ConnectionError("network unavailable")

    monkeypatch.setattr(cm.requests, "post", down)
    adapter = cm.resolve_adapter("cloud:muse", CLOUD_ENV)
    with pytest.raises(requests.RequestException):
        cm.run_chat(adapter, call(model="cloud:muse", purpose="clue-draft"))
    monkeypatch.setattr(
        cm.requests, "post", lambda *a, **k: FakeResponse({"error": "gone"}, status=410)
    )
    with pytest.raises(requests.RequestException):
        cm.run_chat(adapter, call(model="cloud:muse", purpose="clue-draft"))
    assert [item["outcome"] for item in cm.recent_calls()] == ["ConnectionError", "HTTPError"]


def test_local_openai_server_must_be_loopback(monkeypatch):
    adapter = cm.resolve_adapter("local:mlx-clue", {})
    assert adapter.kind == "local"
    assert adapter.receipt()["endpointHost"] == "127.0.0.1:8080"
    with pytest.raises(cm.AdapterError):
        cm.resolve_adapter("local:x", {"CROSSWORD_LOCAL_OPENAI_URL": "https://example.test/v1"})
    # A local server is not subject to the cloud payload guard.
    monkeypatch.setattr(
        cm.requests,
        "post",
        lambda *a, **k: FakeResponse({"choices": [{"message": {"content": "{}"}}]}),
    )
    prose = [{"role": "user", "content": "plain text"}]
    assert adapter.chat(call(model="local:mlx-clue", messages=prose)).json()


def test_fixture_adapter_runs_without_a_network(monkeypatch):
    monkeypatch.setattr(cm.requests, "post", lambda *a, **k: pytest.fail("network used"))
    cm.register_fixture("echo", lambda c: json.dumps({"clues": [], "model": c.model}))
    adapter = cm.resolve_adapter("fixture:echo")
    response = cm.run_chat(adapter, call(model="fixture:echo"))
    assert json.loads(response.json()["message"]["content"])["model"] == "fixture:echo"
    with pytest.raises(cm.AdapterError):
        cm.resolve_adapter("fixture:missing")


def test_trace_records_sampling_but_never_content_or_secrets(monkeypatch):
    monkeypatch.setattr(
        cm.requests,
        "post",
        lambda *a, **k: FakeResponse({"choices": [{"message": {"content": "{}"}}]}),
    )
    adapter = cm.resolve_adapter("cloud:muse", CLOUD_ENV)
    cm.run_chat(adapter, call(model="cloud:muse", purpose="clue-draft", seed=11))
    (record,) = cm.recent_calls()
    assert record["seed"] == 11
    assert record["purpose"] == "clue-draft"
    assert record["keyPresent"] is True
    assert record["endpointHost"] == "gateway.example.test"
    dumped = json.dumps(record)
    assert SECRET not in dumped
    assert ANSWER_MARKER not in dumped
    assert "gateway.example.test/v1" not in dumped


def test_trace_is_bounded():
    cm.register_fixture("quiet", lambda _c: "{}")
    adapter = cm.resolve_adapter("fixture:quiet")
    for _ in range(cm.TRACE_LIMIT + 20):
        cm.run_chat(adapter, call(model="fixture:quiet"))
    assert len(cm.recent_calls()) == cm.TRACE_LIMIT
    assert len(cm.recent_calls(3)) == 3
