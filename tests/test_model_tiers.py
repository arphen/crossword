"""Tests for the model tier registry (Q06).

Large tags exceed a 16 GB host; local-small tags are the lane this host can
run. Selection prefers large where installed and falls through to
local-small; sampling parameters are explicit per tier; failures name the
installable tags instead of demanding a 26 B model. Offline, no model.
"""

import json

import pytest

from crossword import private_puzzle_generation as generation
from crossword.runtime_readiness import preferred_model_tags


def test_tier_mapping():
    assert generation._model_tier("gemma4:26b") == "large"
    assert generation._model_tier("QWEN3.8:27B") == "large"
    assert generation._model_tier("llama3.2:3b") == "local-small"
    assert generation._model_tier("gemma3:4b") == "local-small"
    assert generation._model_tier("local-model") == "unlisted"
    assert generation._model_tier(None) == "unlisted"


def test_memory_ceilings_mark_large_inadmissible_here():
    ceilings = generation._MODEL_MEMORY_CEILINGS
    assert ceilings["llama3.2:3b"] < 4_000_000_000
    assert ceilings["gemma3:4b"] < 5_000_000_000
    for tag in ("gemma4:26b", "qwen3.8:27b", "gemma4:31b", "gemma3:27b"):
        assert ceilings[tag] > 10_000_000_000


def test_selection_prefers_large_then_falls_through_to_small(monkeypatch):
    monkeypatch.setattr(
        generation, "_ollama_installed_models", lambda: {"gemma4:26b", "llama3.2:3b"}
    )
    assert generation._installed_model() == "gemma4:26b"
    monkeypatch.setattr(
        generation, "_ollama_installed_models", lambda: {"llama3.2:3b", "gemma3:4b"}
    )
    assert generation._installed_model() == "llama3.2:3b"


def test_empty_registry_names_installable_tags(monkeypatch):
    monkeypatch.setattr(generation, "_ollama_installed_models", lambda: set())
    with pytest.raises(RuntimeError) as error:
        generation._installed_model()
    message = str(error.value)
    assert "ollama pull" in message
    assert "llama3.2:3b" in message
    assert "Install Gemma 4 26B" not in message


def test_small_tags_have_explicit_policies():
    default_keys = set(generation._model_generation_policy("unlisted-tag").keys())
    for tag in ("llama3.2:3b", "gemma3:4b"):
        assert set(generation._model_generation_policy(tag).keys()) == default_keys


def _fake_chat_response(payload):
    class FakeResponse:
        content = json.dumps(payload).encode("utf-8")

        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": json.dumps(payload)}}

    return FakeResponse()


def test_chat_sends_tier_num_ctx_only_for_small_tags(monkeypatch):
    calls = []

    def fake_post(url, timeout, json):
        calls.append(json)
        return _fake_chat_response({"ok": True})

    monkeypatch.setattr(generation.requests, "post", fake_post)
    schema = {"type": "object"}
    generation._chat("gemma4:26b", [], schema, timeout=5, tokens=10, temperature=0.5)
    generation._chat("llama3.2:3b", [], schema, timeout=5, tokens=10, temperature=0.5)
    large_options, small_options = (call["options"] for call in calls)
    assert large_options == {"temperature": 0.5, "num_predict": 10}
    assert small_options["num_ctx"] == 8192
    assert small_options["temperature"] == 0.5
    assert "seed" not in small_options


def test_chat_honors_explicit_seed_override(monkeypatch):
    calls = []

    def fake_post(url, timeout, json):
        calls.append(json)
        return _fake_chat_response({"ok": True})

    monkeypatch.setattr(generation.requests, "post", fake_post)
    generation._chat(
        "llama3.2:3b", [], {"type": "object"}, timeout=5, tokens=10, temperature=0.5, seed=42
    )
    assert calls[0]["options"]["seed"] == 42


def test_policy_receipt_carries_tier_and_sampling():
    receipt = generation._model_runtime_policy_receipt("llama3.2:3b")
    assert receipt["tier"] == "local-small"
    assert receipt["memoryCeilingBytes"] == 3_000_000_000
    assert receipt["sampling"]["numCtx"] == 8192
    large = generation._model_runtime_policy_receipt("gemma4:26b")
    assert large["tier"] == "large"
    assert "num_ctx" not in str(large) or large["sampling"]["numCtx"] is None


def test_readiness_lists_small_tags_after_large():
    tags = preferred_model_tags({})
    assert tags[:4] == ["gemma4:26b", "qwen3.8:27b", "gemma4:31b", "gemma3:27b"]
    assert tags[4:] == ["llama3.2:3b", "gemma3:4b"]
