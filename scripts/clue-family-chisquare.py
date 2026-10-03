#!/usr/bin/env python3
"""Chi-square divergence of our clue-family mix against the measured NYT mix.

The census over the sibling NYT archive is the only real target available:
1.23M published clue/answer pairs, binned by weekday, family, and genre. This
compares the drafted family mix on the frozen benchmark with the published
mix for the same weekday.

The asymptotic chi-square p-value is not valid here. The benchmark holds 14
admitted clues spread over seven families, so most expected cell counts are
far below the usual ``>= 5`` floor and the statistic is badly biased upward.
This reports the statistic *and* a Monte Carlo p-value, which stays valid at
low expected counts, plus a warning whenever any expected cell is under 5.

Output is counts-only.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RECEIPT_VERSION = "private-clue-family-chisquare-v1"
FAMILIES = (
    "definition",
    "factual-relation",
    "fill-blank",
    "metalinguistic",
    "nonverbal-expression",
    "pseudo-pun",
    "pun",
)


def _nyt_family(receipt_path: Path, weekday: str) -> dict:
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    families = (payload.get("weekdays") or {}).get(weekday, {}).get("family") or {}
    if not families:
        raise SystemExit(f"no family counts for weekday {weekday!r} in {receipt_path}")
    total = sum(families.values())
    if not total:
        raise SystemExit(f"empty family counts for weekday {weekday!r}")
    return {name: families.get(name, 0) / total for name in FAMILIES}


def _benchmark_family(benchmark_path: Path, label: str | None) -> tuple[dict, str]:
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
    iterations = payload.get("iterations") or []
    if not iterations:
        raise SystemExit(f"no iterations in {benchmark_path}")
    chosen = iterations[-1]
    if label:
        for candidate in iterations:
            if candidate.get("label") == label:
                chosen = candidate
                break
        else:
            raise SystemExit(f"label {label!r} not found in {benchmark_path}")
    observed = Counter(
        {
            name: count
            for name, count in (chosen.get("families") or {}).items()
            if name in FAMILIES
        }
    )
    return dict(observed), chosen.get("label", "unknown")


def _chi_square(observed: dict, expected_shares: dict) -> tuple[float, dict]:
    n = sum(observed.values())
    if not n:
        return 0.0, {}
    statistic = 0.0
    expected_counts = {}
    for name, share in expected_shares.items():
        expected = share * n
        expected_counts[name] = expected
        if expected <= 0:
            continue
        statistic += (observed.get(name, 0) - expected) ** 2 / expected
    return statistic, expected_counts


def _monte_carlo_pvalue(observed, expected_shares, observed_stat, trials=20000, seed=20261003):
    """Exact-ish p-value by simulating the multinomial under the target mix."""
    rng = random.Random(seed)
    n = sum(observed.values())
    names = [name for name, share in expected_shares.items() if share > 0]
    weights = [expected_shares[name] for name in names]
    at_least = 0
    for _ in range(trials):
        drawn = rng.choices(names, weights=weights, k=n)
        simulated = Counter(drawn)
        statistic = 0.0
        for name in names:
            expected = expected_shares[name] * n
            statistic += (simulated.get(name, 0) - expected) ** 2 / expected
        if statistic >= observed_stat - 1e-12:
            at_least += 1
    return (at_least + 1) / (trials + 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--nyt",
        type=Path,
        default=ROOT / "docs" / "evidence" / "private-clue-nyt-census-v1.20261002.json",
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=ROOT / "docs" / "evidence" / "private-clue-benchmark-v1.20261003.json",
    )
    parser.add_argument("--label", default=None, help="benchmark iteration label (default: last)")
    parser.add_argument("--weekday", default="monday")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    expected_shares = _nyt_family(args.nyt, args.weekday)
    observed, label = _benchmark_family(args.benchmark, args.label)
    statistic, expected_counts = _chi_square(observed, expected_shares)
    pvalue = _monte_carlo_pvalue(observed, expected_shares, statistic)
    thin = sorted(
        (name, round(count, 2))
        for name, count in expected_counts.items()
        if count < 5
    )

    summary = {
        "label": label,
        "weekday": args.weekday,
        "n": sum(observed.values()),
        "chiSquare": round(statistic, 4),
        "degreesOfFreedom": len([s for s in expected_shares.values() if s > 0]) - 1,
        "monteCarloPValue": round(pvalue, 4),
        "divergesAt95": pvalue < 0.05,
        "observed": {name: observed.get(name, 0) for name in expected_shares},
        "expectedShare": {name: round(value, 5) for name, value in expected_shares.items()},
        "thinExpectedCells": thin,
    }

    receipt = {
        "version": RECEIPT_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "counts-only",
        "claim": "family-mix divergence against the measured published mix, same weekday",
        "knownLimits": [
            "benchmark n is ~14, so the asymptotic chi-square p-value is "
            "invalid; the Monte Carlo p-value is the one to read",
            "expected cells under 5 are listed and make the statistic fragile",
            "a 15-entry benchmark cannot resolve a family mix to editorial "
            "precision; treat a non-significant result as inconclusive",
        ],
        "summary": summary,
    }
    if args.out is None:
        args.out = ROOT / "docs" / "evidence" / (
            f"{RECEIPT_VERSION}.{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
