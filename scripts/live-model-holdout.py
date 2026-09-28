#!/usr/bin/env python3
"""Run a small exact-tag Qwen/Gemma holdout against loopback Ollama.

The source fixture supplies frozen prompts.  This runner records exact model
identity, raw output hashes, provider timings, and deliberately shallow shape
checks.  It does not score semantics, clue fairness, language accuracy, or
player enjoyment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_SOURCE = Path("/tmp/crossword-model-eval/qwen-gemma-20260926/holdout-v1.full.json")
DEFAULT_MODELS = ("qwen3.8:27b", "gemma4:26b")
REPORT_VERSION = "live-model-smoke-holdout-v1"


class _Response:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self._body = body

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise OSError(f"http-status-{self.status}")

    def json(self) -> Any:
        return json.loads(self._body.decode("utf-8"))


class _Session:
    def request(self, method: str, url: str, *, payload: Any = None, timeout: float) -> _Response:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = _canonical(payload)
            headers["Content-Type"] = "application/json"
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                return _Response(response.status, response.read())
        except HTTPError as error:
            return _Response(error.code, error.read())
        except URLError as error:
            raise OSError(str(error.reason)) from error

    def get(self, url: str, *, timeout: float) -> _Response:
        return self.request("GET", url, timeout=timeout)

    def post(self, url: str, *, json: Any, timeout: float) -> _Response:
        return self.request("POST", url, payload=json, timeout=timeout)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _shape_gate(task: str, value: Any) -> dict[str, Any]:
    """Check only response shape; semantic/editorial review remains pending."""

    issues: list[str] = []
    if task == "calibration-association":
        paths = value.get("paths") if isinstance(value, dict) else None
        if not isinstance(paths, list) or len(paths) != 3:
            issues.append("paths-must-contain-exactly-three-items")
        else:
            for index, path in enumerate(paths):
                if not isinstance(path, dict):
                    issues.append(f"path-{index}-not-object")
                    continue
                if not isinstance(path.get("signifiers"), list) or len(path["signifiers"]) < 2:
                    issues.append(f"path-{index}-needs-two-signifiers")
                if not _text(path.get("connection")):
                    issues.append(f"path-{index}-missing-connection")
                if not _text(path.get("alternative")):
                    issues.append(f"path-{index}-missing-alternative")
    elif task == "theme-answers":
        answers = value.get("answers") if isinstance(value, dict) else None
        if not isinstance(answers, list) or not 3 <= len(answers) <= 6:
            issues.append("answers-must-contain-three-to-six-items")
        else:
            for index, item in enumerate(answers):
                if not isinstance(item, dict) or not _text(item.get("answer")):
                    issues.append(f"answer-{index}-missing-answer")
                if not isinstance(item, dict) or not _text(item.get("mechanism")):
                    issues.append(f"answer-{index}-missing-mechanism")
        if not isinstance(value, dict) or not _text(value.get("theme")):
            issues.append("missing-theme")
    elif task == "crossword-clue":
        if not isinstance(value, dict) or not _text(value.get("clue")):
            issues.append("missing-clue")
    elif task == "language-learning":
        items = value.get("items") if isinstance(value, dict) else None
        if not isinstance(items, list) or len(items) != 3:
            issues.append("items-must-contain-exactly-three-items")
        else:
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    issues.append(f"item-{index}-not-object")
                    continue
                for key in ("answer", "clue", "gloss"):
                    if not _text(item.get(key)):
                        issues.append(f"item-{index}-missing-{key}")
    else:
        issues.append("unknown-task")
    return {
        "status": "valid" if not issues else "invalid",
        "issues": issues,
        "scope": "shape-only-no-semantic-claim",
    }


def _tags(session: _Session, base_url: str) -> dict[str, dict[str, Any]]:
    response = session.get(f"{base_url}/api/tags", timeout=20)
    response.raise_for_status()
    payload = response.json()
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        raise RuntimeError("ollama-tags-malformed")
    return {
        item["name"]: item
        for item in models
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def _observation(
    session: _Session,
    *,
    base_url: str,
    model: str,
    fixture: dict[str, Any],
    sequence: int,
    identity: dict[str, Any],
    seed: int,
) -> dict[str, Any]:
    prompt = fixture.get("prompt")
    task = fixture.get("task")
    started = time.perf_counter()
    row: dict[str, Any] = {
        "fixtureId": fixture.get("fixtureId"),
        "task": task,
        "sequence": sequence,
        "requestedModel": model,
        "identity": identity,
        "promptHash": _sha256(str(prompt).encode("utf-8")),
        "status": "failed",
    }
    try:
        response = session.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "format": "json",
                "stream": False,
                "think": False,
                "keep_alive": "5m",
                "options": {"temperature": 0, "seed": seed, "num_predict": 768},
            },
            timeout=240,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload.get("message") if isinstance(payload, dict) else None
        raw = message.get("content") if isinstance(message, dict) else payload.get("response")
        if not isinstance(raw, str):
            raise ValueError("ollama-response-content-missing")
        row["rawOutput"] = raw
        row["rawOutputHash"] = _sha256(raw.encode("utf-8"))
        try:
            parsed = json.loads(raw)
            row["jsonStatus"] = "valid"
        except (json.JSONDecodeError, TypeError):
            parsed = None
            row["jsonStatus"] = "invalid"
        row["shapeGate"] = _shape_gate(str(task), parsed)
        row["providerMetrics"] = {
            key: payload.get(key)
            for key in (
                "total_duration",
                "load_duration",
                "prompt_eval_count",
                "prompt_eval_duration",
                "eval_count",
                "eval_duration",
            )
            if isinstance(payload.get(key), (int, float))
            and not isinstance(payload.get(key), bool)
        }
        row["status"] = "complete"
    except (OSError, ValueError, TypeError, KeyError) as error:
        row["error"] = type(error).__name__
        row["errorCode"] = str(error)[:200]
    row["wallMs"] = round((time.perf_counter() - started) * 1000, 3)
    row["outputId"] = _sha256(_canonical({k: row.get(k) for k in ("fixtureId", "requestedModel", "sequence", "rawOutputHash", "status")}))
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--seed", type=int, default=20260928)
    parser.add_argument("--model", action="append", dest="models")
    args = parser.parse_args()
    source_raw = args.source.read_bytes()
    source = json.loads(source_raw)
    observations = source.get("observations") if isinstance(source, dict) else None
    if not isinstance(observations, list) or not observations:
        raise SystemExit("source fixture has no observations")
    fixtures: dict[str, dict[str, Any]] = {}
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        fixture_id = observation.get("fixtureId")
        if isinstance(fixture_id, str) and fixture_id not in fixtures:
            fixtures[fixture_id] = {
                "fixtureId": fixture_id,
                "task": observation.get("task"),
                "prompt": observation.get("prompt"),
            }
    if not fixtures:
        raise SystemExit("source fixture has no prompts")
    models = tuple(args.models or DEFAULT_MODELS)
    session = _Session()
    tag_map = _tags(session, args.base_url.rstrip("/"))
    rows: list[dict[str, Any]] = []
    for model in models:
        tag = tag_map.get(model)
        identity = {
            "requestedModel": model,
            "returnedModel": model if tag else None,
            "tagDigest": tag.get("digest") if isinstance(tag, dict) else None,
            "parameterSize": (tag.get("details") or {}).get("parameter_size") if isinstance(tag, dict) else None,
            "quantizationLevel": (tag.get("details") or {}).get("quantization_level") if isinstance(tag, dict) else None,
            "contextLength": (tag.get("details") or {}).get("context_length") if isinstance(tag, dict) else None,
            "verified": bool(tag),
        }
        if not tag:
            rows.extend(
                {
                    "fixtureId": fixture["fixtureId"],
                    "task": fixture["task"],
                    "sequence": index,
                    "requestedModel": model,
                    "identity": identity,
                    "status": "missing-model",
                    "outputId": _sha256(_canonical({"model": model, "fixture": fixture["fixtureId"]})),
                }
                for index, fixture in enumerate(fixtures.values())
            )
            continue
        for index, fixture in enumerate(fixtures.values()):
            rows.append(
                _observation(
                    session,
                    base_url=args.base_url.rstrip("/"),
                    model=model,
                    fixture=fixture,
                    sequence=index,
                    identity=identity,
                    seed=args.seed,
                )
            )
    summary: dict[str, Any] = {}
    for model in models:
        selected = [row for row in rows if row.get("requestedModel") == model]
        summary[model] = {
            "requested": len(selected),
            "complete": sum(row.get("status") == "complete" for row in selected),
            "jsonValid": sum(row.get("jsonStatus") == "valid" for row in selected),
            "shapeValid": sum(row.get("shapeGate", {}).get("status") == "valid" for row in selected),
            "wallMs": round(sum(float(row.get("wallMs", 0)) for row in selected), 3),
        }
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "reportKind": REPORT_VERSION,
        "comparative": len(models) > 1,
        "sourceFixture": str(args.source),
        "sourceFixtureSha256": _sha256(source_raw),
        "requestedModels": list(models),
        "generation": {
            "seed": args.seed,
            "temperature": 0,
            "maxOutputTokens": 768,
            "format": "json",
            "streaming": False,
        },
        "runtime": {"provider": "ollama-loopback", "baseUrl": args.base_url, "tagDigests": {model: tag_map.get(model, {}).get("digest") for model in models}},
        "observations": rows,
        "summary": summary,
        "semanticEditorial": {"status": "pending", "winnerClaim": "none"},
        "caveats": [
            "Shape checks do not establish semantic correctness, clue fairness, language accuracy, or enjoyment.",
            "Models ran serially on the current machine; cold/warm loading and hardware contention affect latency.",
            "The exact quantized Ollama tag digest is retained for reproducibility.",
        ],
    }
    report["artifactSha256"] = _sha256(_canonical(report))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "summary": summary, "artifactSha256": report["artifactSha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
