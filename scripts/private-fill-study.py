#!/usr/bin/env python3
"""Run a fixed-seed fill study through a local private-puzzle server.

The server must already be running (``make run-personal`` is the normal
launcher), and the profile must be an existing local profile.  This command
uses only the same local HTTP endpoint as the browser, extracts the
``qualityPolicy`` receipt from each generated puzzle, and writes a
``private-fill-quality-study-v1`` report.  It never uploads a profile or
starts a model itself.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.crossword.fill_quality_evaluation import (  # noqa: E402
    evaluate_fill_quality_study,
)


def _request_puzzle(base_url: str, profile_id: str, seed: int, weekday: str, model: str | None, timeout: float) -> dict:
    body = {"profileId": profile_id, "seed": seed, "weekday": weekday}
    if model:
        body["model"] = model
    request = Request(
        f"{base_url.rstrip('/')}/api/future/private-puzzles",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": base_url.rstrip("/"),
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:240]
        raise RuntimeError(f"HTTP {error.code}: {detail or error.reason}") from error
    except URLError as error:
        raise RuntimeError(f"local server unavailable: {error.reason}") from error
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("local server returned invalid JSON") from error
    if not isinstance(value, dict):
        raise RuntimeError("local server returned a non-object response")
    return value


def _validate_local_base_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise SystemExit("--base-url must point to a loopback HTTP(S) server")
    return value.rstrip("/")


def _case_from_response(seed: int, response: dict) -> dict:
    provenance = response.get("provenance")
    if not isinstance(provenance, dict):
        raise RuntimeError("puzzle response did not include provenance")
    fill_quality = provenance.get("fillQuality")
    if not isinstance(fill_quality, dict):
        raise RuntimeError("puzzle response did not include fillQuality")
    policy = fill_quality.get("qualityPolicy")
    if not isinstance(policy, dict) or not isinstance(policy.get("attempts"), list):
        raise RuntimeError("puzzle response did not include qualityPolicy attempts")
    return {
        "seed": seed,
        "attempts": policy["attempts"],
        "selectedAttempt": policy.get("selectedAttempt"),
        "recipe": provenance.get("weekdayRecipe", {}).get("id")
        if isinstance(provenance.get("weekdayRecipe"), dict)
        else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--weekday", choices=("monday", "wednesday", "thursday", "sunday"), default="wednesday")
    parser.add_argument("--seed", action="append", type=int, dest="seeds", required=True)
    parser.add_argument("--model", help="explicit installed Ollama tag")
    parser.add_argument("--base-url", default="http://127.0.0.1:5001")
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--study-id", default="local-private-fill-study")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if len(args.seeds) > 32 or len(set(args.seeds)) != len(args.seeds):
        raise SystemExit("provide between 1 and 32 unique --seed values")
    args.base_url = _validate_local_base_url(args.base_url)
    cases = []
    for seed in args.seeds:
        try:
            response = _request_puzzle(
                args.base_url,
                args.profile_id,
                seed,
                args.weekday,
                args.model,
                args.timeout,
            )
            cases.append(_case_from_response(seed, response))
            print(f"seed {seed}: captured", file=sys.stderr)
        except RuntimeError as error:
            cases.append(
                {
                    "seed": seed,
                    "attempts": [
                        {
                            "label": "private-puzzle-request",
                            "seed": seed,
                            "status": "failed",
                            "reason": str(error)[:240],
                        }
                    ],
                }
            )
            print(f"seed {seed}: {error}", file=sys.stderr)
    report = evaluate_fill_quality_study(
        cases,
        study_id=args.study_id,
        recipe_id=f"private-{args.weekday}-v1",
        requested_seeds=args.seeds,
        metadata={
            "transport": "loopback-http",
            "baseUrl": args.base_url,
            "weekday": args.weekday,
            "model": args.model or "profile-saved-model",
            "seedCount": len(args.seeds),
        },
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
