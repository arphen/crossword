#!/usr/bin/env python3
"""Asymmetric critic evaluator: 3b generates, 4b judges behaviour only.

Score = 0.30*A + 0.30*T + 0.25*W + 0.15*D, higher-is-better.
Outputs {"pass": bool, "score": float} plus diagnostics.
Fail-closed: any exception/timeout -> pass False.
"""

from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

GEN = "llama3.2:3b"
JUDGE = "gemma3:4b"
MONDAY_SHARE = {
    "definition": 0.91963,
    "factual-relation": 0.00866,
    "fill-blank": 0.06432,
    "metalinguistic": 0.00090,
    "nonverbal-expression": 0.00014,
    "pseudo-pun": 0.00613,
    "pun": 0.00023,
}


def census_L1(fams, n):
    return sum(abs(fams.get(k, 0) / max(n, 1) - v) for k, v in MONDAY_SHARE.items())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=6200)
    ap.add_argument("--t-judge", type=float, default=20.0)
    args = ap.parse_args()
    t0 = time.monotonic()
    try:
        import importlib.util

        def _load(name, path):
            spec = importlib.util.spec_from_file_location(name, ROOT / path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod

        B = _load("private_clue_benchmark", "scripts/private-clue-benchmark.py")
        S = _load("clue_cold_solver", "scripts/clue-cold-solver.py")
        summary, clues = B.run_iteration("eval", GEN, "monday", args.seed)
        n = sum(v for k, v in summary["families"].items() if not k.startswith("genre:"))
        D = 1 - min(1.0, census_L1(summary["families"], n) / 0.5)
        A = summary["admitted"] / 15.0
        guard_ok = summary["guardHits"] == 0
        ids = list(B.BENCHMARK_ANSWERS)
        c = {f"{i}A": clues.get(f"{i}A", "") for i in range(len(ids))}
        _, buckets, _, _ = S.probe(ids, c, JUDGE, args.t_judge, None)
        j = sum(v for k, v in buckets.items() if k != "scaffold") or 1
        T = 1 - buckets.get("trivial", 0) / j
        W = buckets.get("gold", 0) / j
        score = round(0.30 * A + 0.30 * T + 0.25 * W + 0.15 * D, 4)
        wall = round(time.monotonic() - t0, 1)
        ok = guard_ok and summary["admitted"] >= 13 and wall < 300 and score >= 0.68
        print(
            json.dumps(
                {
                    "pass": ok,
                    "score": score,
                    "A": round(A, 4),
                    "T": round(T, 4),
                    "W": round(W, 4),
                    "D": round(D, 4),
                    "admitted": summary["admitted"],
                    "guardHits": summary["guardHits"],
                    "gen": GEN,
                    "judge": JUDGE,
                    "seed": args.seed,
                    "wall": wall,
                }
            )
        )
        return 0
    except Exception as e:
        print(
            json.dumps(
                {"pass": False, "score": 0.0, "error": f"{type(e).__name__}: {e}"}
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
