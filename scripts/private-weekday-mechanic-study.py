#!/usr/bin/env python3
"""Evaluate Thursday mechanic receipts from a local private-puzzle server.

The server must already be running and the profile must be local.  This
command uses the same private puzzle endpoint as the browser, keeps only the
final board shape and the structural mechanic receipt, and writes an
answer-bearing local study artifact.  It never uploads a profile, starts
Ollama, or treats the result as a fairness or solve-probability claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.crossword.weekday_mechanics_evaluation import (  # noqa: E402
    evaluate_thursday_mechanic_board,
)


STUDY_VERSION = "private-weekday-mechanic-study-v1"


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _validate_loopback(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise SystemExit("--base-url must point to a loopback HTTP(S) server")
    return value.rstrip("/")


def _request(base_url: str, profile_id: str, seed: int, timeout: float) -> dict:
    body = {"profileId": profile_id, "seed": seed, "weekday": "thursday"}
    request = Request(
        f"{base_url}/api/future/private-puzzles",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": base_url,
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


def _evaluate(seed: int, response: dict) -> dict:
    provenance = response.get("provenance")
    if not isinstance(provenance, dict):
        raise RuntimeError("puzzle response did not include provenance")
    if str(provenance.get("weekday", "")).lower() != "thursday":
        raise RuntimeError("puzzle response was not a Thursday board")
    # The legacy playable response intentionally omits answers from its
    # ``entries`` projection.  The owner-scoped manifest is the replay source
    # that carries them, so reconstruct only the structural evaluator shape
    # from that manifest and mark theme answers from the frozen receipt.
    manifest = response.get("puzzleManifest")
    if isinstance(manifest, dict) and isinstance(manifest.get("entries"), list):
        declared = {
            answer
            for answer in (
                provenance.get("themeMechanic", {}).get("themeAnswers", [])
                if isinstance(provenance.get("themeMechanic"), dict)
                else []
            )
            if isinstance(answer, str)
        }
        entries = []
        for raw in manifest["entries"]:
            if not isinstance(raw, dict):
                continue
            direction = raw.get("direction")
            entries.append(
                {
                    "num": raw.get("number"),
                    "dir": "A" if direction == "across" else "D" if direction == "down" else direction,
                    "answer": raw.get("answer"),
                    "theme": raw.get("answer") in declared,
                }
            )
        board = {"entries": entries}
    else:
        board = response
    report = evaluate_thursday_mechanic_board(
        board,
        provenance,
        board_id=f"thursday-{seed}",
    )
    return {
        "seed": seed,
        "status": report["status"],
        "mechanicStatus": provenance.get("themeMechanic", {}).get("status")
        if isinstance(provenance.get("themeMechanic"), dict)
        else None,
        "report": report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--seed", action="append", type=int, dest="seeds", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:5001")
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--study-id", default="local-thursday-mechanic-study")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if len(args.seeds) > 32 or len(set(args.seeds)) != len(args.seeds):
        raise SystemExit("provide between 1 and 32 unique --seed values")
    if any(seed < 0 or seed > 2_147_483_647 for seed in args.seeds):
        raise SystemExit("seeds must be safe non-negative 31-bit integers")
    base_url = _validate_loopback(args.base_url)
    cases = []
    for seed in args.seeds:
        try:
            cases.append(_evaluate(seed, _request(base_url, args.profile_id, seed, args.timeout)))
            print(f"seed {seed}: evaluated", file=sys.stderr)
        except RuntimeError as error:
            cases.append({"seed": seed, "status": "request-failed", "error": str(error)[:240]})
            print(f"seed {seed}: {error}", file=sys.stderr)

    counts = {
        "pass": sum(item.get("status") == "pass" for item in cases),
        "fallbackSafe": sum(item.get("status") == "fallback-safe" for item in cases),
        "fail": sum(item.get("status") == "fail" for item in cases),
        "requestFailed": sum(item.get("status") == "request-failed" for item in cases),
        "boardCount": len(cases),
    }
    report = {
        "version": STUDY_VERSION,
        "scope": "loopback-private-thursday-boards",
        "status": "observed" if cases else "empty",
        "studyId": args.study_id,
        "profileId": args.profile_id,
        "requestedSeeds": args.seeds,
        "summary": counts,
        "cases": cases,
        "uncertainty": {
            "semanticFairness": "unverified",
            "modelQuality": "not-measured",
            "playerSolveProbability": "unmeasured",
            "humanPlaytest": "not-run",
        },
        "metadata": {
            "transport": "loopback-http",
            "baseUrl": base_url,
            "weekday": "thursday",
        },
    }
    report["studyDigest"] = _digest(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
