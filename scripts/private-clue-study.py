#!/usr/bin/env python3
"""Collect an answer-free clue-quality study from a running local server.

The server must already be running (``make run-personal`` is the normal
launcher). The collector uses the same loopback private-puzzle endpoint as the
browser, projects only provenance counters, and never starts Ollama or writes
profile data.
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

from src.crossword.clue_quality_evaluation import (  # noqa: E402
    clue_case_from_provenance,
    evaluate_clue_quality_study,
)


# Keep the answer-free error case aligned with the live Tuesday recipe. A
# failed request must not silently create a receipt that claims the former
# 32-surface contract while successful jobs report the current 40-surface
# target from their provenance.
_TUESDAY_REQUIRED_NON_DEFINITION_CLUES = 40


def _base_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise SystemExit("--base-url must point to a loopback HTTP(S) server")
    return value.rstrip("/")


def _request(base_url: str, profile_id: str, seed: int, weekday: str, model: str | None, timeout: float) -> dict:
    body = {"profileId": profile_id, "seed": seed, "weekday": weekday}
    if model:
        body["model"] = model
    request = Request(
        f"{base_url}/api/future/private-puzzles",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json", "Origin": base_url},
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument(
        "--weekday",
        choices=("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"),
        default="wednesday",
    )
    parser.add_argument("--seed", action="append", type=int, dest="seeds", required=True)
    parser.add_argument("--model", help="explicit installed Ollama tag")
    parser.add_argument("--base-url", default="http://127.0.0.1:5001")
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--study-id", default="local-private-clue-study")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if len(args.seeds) > 32 or len(set(args.seeds)) != len(args.seeds):
        raise SystemExit("provide between 1 and 32 unique --seed values")
    base_url = _base_url(args.base_url)
    cases = []
    for seed in args.seeds:
        try:
            response = _request(base_url, args.profile_id, seed, args.weekday, args.model, args.timeout)
            provenance = response.get("provenance")
            if not isinstance(provenance, dict):
                raise RuntimeError("puzzle response did not include provenance")
            cases.append(clue_case_from_provenance(provenance, seed))
            print(f"seed {seed}: captured", file=sys.stderr)
        except (RuntimeError, ValueError) as error:
            required_families = (
                [
                    "pun",
                    "fill-blank",
                    "nonverbal-expression",
                    "spoken-equivalent",
                    "metalinguistic",
                ]
                if args.weekday == "tuesday"
                else []
            )
            cases.append({
                "seed": seed,
                "entryCount": 0,
                "grammarCheckedCount": 0,
                "grammarIssueCount": 0,
                "fallbackCount": 0,
                "semanticStatus": "not-established",
                "familyCounts": {},
                "nonDefinitionCount": 0,
                "nonDefinitionFamilies": [],
                "floorMet": False,
                "requiredNonDefinitionFamilies": len(required_families),
                "requiredNonDefinitionFamilySet": required_families,
                "missingNonDefinitionFamilies": required_families,
                "requiredNonDefinitionClues": (
                    _TUESDAY_REQUIRED_NON_DEFINITION_CLUES
                    if args.weekday == "tuesday"
                    else 0
                ),
                "signalCounts": {},
                "issueCounts": {},
                "semanticChallenge": {},
                "repair": {"status": "unavailable", "reason": str(error)[:240]},
                "timingsSeconds": {},
            })
            print(f"seed {seed}: {error}", file=sys.stderr)
    report = evaluate_clue_quality_study(
        cases,
        study_id=args.study_id,
        recipe_id=f"private-{args.weekday}-v1",
        requested_seeds=args.seeds,
        metadata={"transport": "loopback-http", "weekday": args.weekday, "model": args.model or "profile-saved-model", "seedCount": len(args.seeds)},
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
