"""Clue-model adapters (G1): one call shape, local first, cloud optional.

The generation host talks to a model through ``resolve_adapter(tag)``:

* a plain tag (``llama3.2:3b``) is the local Ollama runtime, unchanged;
* ``local:<name>`` is a local OpenAI-compatible server (llama.cpp, MLX,
  LM Studio) at ``CROSSWORD_LOCAL_OPENAI_URL``;
* ``cloud:<name>`` is the optional cloud extension, an OpenAI-compatible
  gateway that is **off unless explicitly enabled** and that refuses any call
  whose purpose or payload is not a clue-writing request;
* ``fixture:<name>`` is a registered in-process double for tests.

Nothing in the default path reaches a cloud adapter: ``_installed_model`` never
selects one and the browser override only admits registry tags. A cloud
failure (network, auth, a retired model) surfaces as the same
``requests.RequestException`` / ``ValueError`` family the callers already
handle, so a dead provider degrades to the existing scaffold path rather than
breaking generation.

The call trace records sampling and timing, never message content: prompts
carry answers, and answer-bearing text stays out of receipts.
"""

from __future__ import annotations

import json
import os
import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol
from urllib.parse import urlparse

import requests

CLOUD_PREFIX = "cloud:"
LOCAL_OPENAI_PREFIX = "local:"
FIXTURE_PREFIX = "fixture:"

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_LOCAL_OPENAI_URL = "http://127.0.0.1:8080/v1"
MAX_RESPONSE_BYTES = 1024 * 1024
TRACE_LIMIT = 512

# A cloud call may only be a clue-writing request. ``None`` is refused so a
# new call site cannot reach the cloud by forgetting to say what it is for.
CLOUD_PURPOSES = frozenset({"clue-draft", "clue-compare", "clue-judge", "bakeoff"})
# Top-level keys a cloud payload may carry. This is a fail-closed tripwire, not
# a proof of privacy: it exists so profile, journal and reflection fields cannot
# ride along by accident.
CLOUD_PAYLOAD_KEYS = frozenset(
    {
        "entries",
        "candidates",
        "entry",
        "answer",
        "answers",
        "angle",
        "angles",
        "lane",
        "weekday",
        "exemplars",
        "avoid",
        "signifiers",
        "instruction",
        "id",
        "length",
    }
)

_TRUE = {"1", "true", "yes", "on"}


class AdapterError(ValueError):
    """A configuration or request problem. Subclasses ``ValueError`` so the
    existing clue-call handlers degrade to scaffolds instead of crashing."""


class CloudDisabled(AdapterError):
    """The cloud extension was selected while it is off or unconfigured."""


class CloudPrivacyRefusal(AdapterError):
    """A cloud call was refused for its purpose or payload."""


@dataclass(frozen=True)
class ChatCall:
    model: str
    messages: list
    schema: Any
    timeout: float
    tokens: int
    temperature: float
    seed: int | None = None
    top_p: float | None = None
    num_ctx: int | None = None
    purpose: str | None = None


class NormalizedResponse:
    """A requests-shaped response whose JSON is Ollama's ``message.content``."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.content = text.encode("utf-8")

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"message": {"content": self._text}}


class ClueModelAdapter(Protocol):
    name: str
    kind: str

    def chat(self, call: ChatCall) -> Any: ...

    def receipt(self) -> dict: ...


class OllamaAdapter:
    """The local runtime. The request is byte-for-byte what ``_chat`` always sent."""

    name = "ollama"
    kind = "local"

    def chat(self, call: ChatCall) -> Any:
        options: dict[str, Any] = {
            "temperature": call.temperature,
            "num_predict": call.tokens,
        }
        if call.top_p is not None:
            options["top_p"] = call.top_p
        if call.num_ctx is not None:
            options["num_ctx"] = call.num_ctx
        if call.seed is not None:
            options["seed"] = call.seed
        return requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            timeout=(2, call.timeout),
            json={
                "model": call.model,
                "stream": False,
                "think": False,
                "format": call.schema,
                "options": options,
                "messages": call.messages,
            },
        )

    def receipt(self) -> dict:
        return {"adapter": self.name, "kind": self.kind, "endpointHost": "127.0.0.1:11434"}


def _host(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.rsplit("@", 1)[-1]


def _is_loopback(url: str) -> bool:
    return (urlparse(url).hostname or "") in {"127.0.0.1", "localhost", "::1"}


def _validated_base_url(url: str, *, allow_plain_loopback: bool) -> str:
    cleaned = (url or "").strip().rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AdapterError("model endpoint must be an http(s) URL")
    if parsed.username or parsed.password:
        raise AdapterError("model endpoint must not embed credentials")
    if parsed.query or parsed.fragment:
        raise AdapterError("model endpoint must not carry a query or fragment")
    if parsed.scheme == "http" and not (allow_plain_loopback and _is_loopback(cleaned)):
        raise AdapterError("model endpoint must be https unless it is loopback")
    return cleaned


def _payload_keys(messages: list) -> set[str] | None:
    """Top-level keys of every JSON user message, or None when one is not JSON."""
    keys: set[str] = set()
    for message in messages:
        if not isinstance(message, Mapping) or message.get("role") != "user":
            continue
        try:
            value = json.loads(message.get("content", ""))
        except (TypeError, ValueError):
            return None
        if not isinstance(value, dict):
            return None
        keys.update(str(key) for key in value)
    return keys


class OpenAICompatAdapter:
    """An OpenAI-compatible ``/chat/completions`` endpoint, local or cloud."""

    name = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        model_name: str,
        *,
        kind: str,
        api_key: str = "",
    ) -> None:
        if kind not in {"local", "cloud"}:
            raise AdapterError("unknown adapter kind")
        self.kind = kind
        self.base_url = _validated_base_url(base_url, allow_plain_loopback=True)
        self.model_name = model_name
        self._api_key = api_key

    def _guard(self, call: ChatCall) -> None:
        if self.kind != "cloud":
            return
        if call.purpose not in CLOUD_PURPOSES:
            raise CloudPrivacyRefusal(
                "cloud calls must declare a clue-writing purpose"
            )
        keys = _payload_keys(call.messages)
        if keys is None or not keys <= CLOUD_PAYLOAD_KEYS:
            raise CloudPrivacyRefusal(
                "cloud payload must be JSON with only clue-writing fields"
            )

    def chat(self, call: ChatCall) -> Any:
        self._guard(call)
        body: dict[str, Any] = {
            "model": self.model_name,
            "messages": call.messages,
            "temperature": call.temperature,
            "max_tokens": call.tokens,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        if call.seed is not None:
            body["seed"] = call.seed
        if call.top_p is not None:
            body["top_p"] = call.top_p
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        response = requests.post(
            f"{self.base_url}/chat/completions",
            timeout=(2, call.timeout),
            json=body,
            headers=headers,
        )
        response.raise_for_status()
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise ValueError("Model response is too large")
        data = response.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ValueError("Model response had no message content") from None
        if not isinstance(text, str):
            raise ValueError("Model response had no message content")
        return NormalizedResponse(text)

    def receipt(self) -> dict:
        return {
            "adapter": self.name,
            "kind": self.kind,
            "endpointHost": _host(self.base_url),
            "model": self.model_name,
            "keyPresent": bool(self._api_key),
        }


_FIXTURES: dict[str, Callable[[ChatCall], str]] = {}


class FixtureAdapter:
    """An in-process double. The responder returns the model's JSON text."""

    name = "fixture"
    kind = "fixture"

    def __init__(self, label: str, responder: Callable[[ChatCall], str]) -> None:
        self.label = label
        self._responder = responder

    def chat(self, call: ChatCall) -> Any:
        return NormalizedResponse(self._responder(call))

    def receipt(self) -> dict:
        return {"adapter": self.name, "kind": self.kind, "model": self.label}


def register_fixture(label: str, responder: Callable[[ChatCall], str]) -> None:
    _FIXTURES[label] = responder


def clear_fixtures() -> None:
    _FIXTURES.clear()


def _env(environ: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if environ is None else environ


def cloud_adapter(name: str, environ: Mapping[str, str] | None = None) -> OpenAICompatAdapter:
    source = _env(environ)
    if source.get("CROSSWORD_CLOUD_CLUE_ENABLED", "").strip().casefold() not in _TRUE:
        raise CloudDisabled(
            "The cloud clue extension is off. Set CROSSWORD_CLOUD_CLUE_ENABLED=1 "
            "to use a cloud: model."
        )
    url = source.get("CROSSWORD_CLOUD_CLUE_URL", "").strip()
    if not url:
        raise CloudDisabled("CROSSWORD_CLOUD_CLUE_URL is not set")
    if not name.strip():
        raise CloudDisabled("a cloud: model needs a model name")
    return OpenAICompatAdapter(
        url,
        name.strip(),
        kind="cloud",
        api_key=source.get("CROSSWORD_CLOUD_CLUE_API_KEY", "").strip(),
    )


def local_openai_adapter(
    name: str, environ: Mapping[str, str] | None = None
) -> OpenAICompatAdapter:
    source = _env(environ)
    url = source.get("CROSSWORD_LOCAL_OPENAI_URL", "").strip() or DEFAULT_LOCAL_OPENAI_URL
    if not _is_loopback(url):
        raise AdapterError("the local OpenAI-compatible server must be on loopback")
    if not name.strip():
        raise AdapterError("a local: model needs a model name")
    return OpenAICompatAdapter(url, name.strip(), kind="local")


def resolve_adapter(
    model: str | None, environ: Mapping[str, str] | None = None
) -> ClueModelAdapter:
    tag = model if isinstance(model, str) else ""
    if tag.startswith(CLOUD_PREFIX):
        return cloud_adapter(tag[len(CLOUD_PREFIX) :], environ)
    if tag.startswith(LOCAL_OPENAI_PREFIX):
        return local_openai_adapter(tag[len(LOCAL_OPENAI_PREFIX) :], environ)
    if tag.startswith(FIXTURE_PREFIX):
        label = tag[len(FIXTURE_PREFIX) :]
        responder = _FIXTURES.get(label)
        if responder is None:
            raise AdapterError(f"no fixture registered as {label!r}")
        return FixtureAdapter(label, responder)
    return OllamaAdapter()


_TRACE: deque[dict] = deque(maxlen=TRACE_LIMIT)
_TRACE_LOCK = Lock()


def recent_calls(limit: int | None = None) -> list[dict]:
    """Sampling and timing of recent calls; never prompts, answers or clues."""
    with _TRACE_LOCK:
        items = list(_TRACE)
    return items if limit is None else items[-limit:]


def clear_trace() -> None:
    with _TRACE_LOCK:
        _TRACE.clear()


def run_chat(adapter: ClueModelAdapter, call: ChatCall) -> Any:
    """Run one call and record its sampling parameters and outcome."""
    started = time.monotonic()
    outcome = "ok"
    try:
        return adapter.chat(call)
    except Exception as error:
        outcome = type(error).__name__
        raise
    finally:
        record = {
            **adapter.receipt(),
            "model": call.model,
            "purpose": call.purpose,
            "seed": call.seed,
            "temperature": call.temperature,
            "topP": call.top_p,
            "numCtx": call.num_ctx,
            "maxTokens": call.tokens,
            "seconds": round(time.monotonic() - started, 3),
            "outcome": outcome,
        }
        with _TRACE_LOCK:
            _TRACE.append(record)
