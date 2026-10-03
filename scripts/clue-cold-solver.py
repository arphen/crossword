#!/usr/bin/env python3
"""Blind cold-solver probe: a behaviour-based wit proxy for drafted clues.

The frozen benchmark already scores clue *form* with deterministic guards
(leaks, morphology, hedging, risk). It deliberately does not score wit: the
committed receipt records "blind human verdicts score it". This probe adds the
missing automation without asking any model to grade style on a numeric scale.

Method. A solver model is shown a clue, its length, and nothing else -- never
the answer. It gets two attempts (direct guess, then surface analysis). The
answer is revealed only afterwards, at which point the solver reports raw
facts about its own trajectory. The bucket is then computed in Python from
those facts, so no model ever emits a quality verdict:

* ``trivial``  -- solved on attempt 1 with high confidence. No misdirection.
* ``gold``     -- missed attempt 1, then solved on attempt 2, or recognised a
                  fair path on reveal. The surface misdirected and the entry
                  still resolved.
* ``unfair``   -- missed both attempts *and* reported no fair path, or a
                  factually unsound definition. Broken, not merely hard.
* ``unresolved`` -- missed both attempts but a fair path existed and no aha
                  landed. Reported separately so it never silently inflates
                  the gold rate.

The solver is a different model family from the drafter (gemma3:4b judging
llama3.2:3b) to blunt self-preference. Output is counts-only; clue text and
per-entry verdicts stay in the local log, never the committed receipt.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RECEIPT_VERSION = "private-clue-cold-solver-v1"

SCAFFOLD_PREFIX = "Entry supported by its crossings"

_ATTEMPT_SCHEMA = {
    "type": "object",
    "properties": {
        "guess": {"type": "string"},
        "reasoning": {"type": "string"},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["guess", "reasoning", "confidence"],
}

_REVEAL_SCHEMA = {
    "type": "object",
    "properties": {
        "fair_path_exists": {"type": "string", "enum": ["yes", "no", "unsure"]},
        "aha_on_reveal": {"type": "string", "enum": ["yes", "no"]},
        "definition_sound": {
            "type": "string",
            "enum": ["sound", "unsound", "unclear"],
        },
        "note": {"type": "string"},
    },
    "required": ["fair_path_exists", "aha_on_reveal", "definition_sound", "note"],
}

_SYSTEM = (
    "You are an experienced American crossword solver. You are precise, "
    "skeptical, and you never guess carelessly."
)


def _normalize(guess: str) -> str:
    return "".join(ch for ch in str(guess or "").upper() if ch.isalpha())


def _salvage(text: str) -> dict:
    """Recover a schema object from truncated or noisy model JSON.

    A local 4b model occasionally runs out of decode budget mid-string. The
    enum fields are short and appear early, so pulling the first
    ``"key": "value"`` pair per field recovers a usable record instead of
    discarding the whole call and silently counting it as a solver miss.
    """
    found: dict = {}
    for match in re.finditer(r'"([A-Za-z_]+)"\s*:\s*"([^"]*)"', text or ""):
        found.setdefault(match.group(1), match.group(2))
    return found


def _chat(model, messages, schema, *, timeout, tokens, temperature, attempts=3):
    """One structured judge call, resilient to host load races and bad JSON.

    Three host conditions are absorbed rather than scored as solver behaviour:
    a 500 while a tag is swapped in or out, ``prediction aborted, token repeat
    limit reached`` on the reveal prompt, and truncated JSON when the model
    overruns its decode budget. None of them say anything about the clue.
    """
    from src.crossword import private_puzzle_generation as generation

    sampling = generation._tier_sampling(model)
    num_ctx = sampling.get("numCtx")
    options = {
        "temperature": temperature,
        "num_predict": tokens,
        "repeat_penalty": 1.15,
    }
    if num_ctx is not None:
        options["num_ctx"] = num_ctx

    last = None
    for attempt in range(attempts):
        try:
            response = requests.post(
                "http://127.0.0.1:11434/api/chat",
                timeout=(2, timeout),
                json={
                    "model": model,
                    "stream": False,
                    "think": False,
                    "format": schema,
                    "options": options,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
            try:
                return json.loads(content)
            except ValueError:
                salvaged = _salvage(content)
                if salvaged:
                    return salvaged
                raise
        except Exception as error:  # noqa: BLE001 - retried below
            last = error
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"judge call failed after {attempts} attempts: {last}")


def _attempt_one(judge, clue, length, timeout):
    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": (
                f"Crossword clue: {clue}\n"
                f"Entry length: {length} letters, all letters used, no spaces.\n\n"
                "Give your single best guess for the answer. Reply with the "
                "entry, your reasoning, and how confident you are."
            ),
        },
    ]
    return _chat(judge, messages, _ATTEMPT_SCHEMA, timeout=timeout, tokens=320, temperature=0.0)


def _attempt_two(judge, clue, length, first_guess, timeout):
    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": (
                f"Crossword clue: {clue}\n"
                f"Entry length: {length} letters, all letters used, no spaces.\n"
                f"Your first guess '{first_guess}' is wrong.\n\n"
                "Work the surface of the clue -- wordplay, sound, double "
                "meaning, a hidden word, a joke. You MUST give a different "
                "entry from your first guess, even if unsure -- do not repeat "
                "it. Give a reconsidered answer."
            ),
        },
    ]
    return _chat(judge, messages, _ATTEMPT_SCHEMA, timeout=timeout, tokens=400, temperature=0.7)


def _reveal(judge, clue, answer, first_guess, second_guess, timeout):
    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": (
                f"Clue: {clue}\n"
                f"Answer: {answer}\n"
                f"Your guesses: '{first_guess}', then '{second_guess}'.\n\n"
                "Reply in the given fields. Keep note under 15 words.\n"
                "- fair_path_exists: yes if ANY grammatical path from this "
                "clue to that answer exists, even a stretched one -- judge "
                "generously, hindsight counts. Answer unsure only if truly "
                "uncertain.\n"
                "- aha_on_reveal: yes if the answer makes sense in hindsight, "
                "even partly -- hindsight counts, it need not feel inevitable.\n"
                "- definition_sound: unsound only if the clue states something "
                "factually false about the answer."
            ),
        },
    ]
    return _chat(judge, messages, _REVEAL_SCHEMA, timeout=timeout, tokens=300, temperature=0.2)


def _classify(first, second, reveal, answer):
    """Compute the bucket in Python from reported facts, never from a verdict."""
    first_ok = _normalize(first.get("guess")) == _normalize(answer)
    second_ok = _normalize(second.get("guess")) == _normalize(answer)
    fair = str(reveal.get("fair_path_exists", "unsure")).casefold() == "yes"
    unsure = str(reveal.get("fair_path_exists", "unsure")).casefold() == "unsure"
    aha = str(reveal.get("aha_on_reveal", "no")).casefold() == "yes"
    sound = str(reveal.get("definition_sound", "unclear")).casefold()
    confident = str(first.get("confidence", "low")).casefold() == "high"

    if first_ok and confident:
        bucket = "trivial"
    elif second_ok or fair:
        bucket = "gold"
    elif unsure:
        bucket = "unresolved"
    else:
        bucket = "unfair"
    return {
        "bucket": bucket,
        "solvedAttempt1": first_ok,
        "solvedAttempt2": second_ok,
        "fairPath": fair,
        "aha": aha,
        "sound": sound,
    }


def probe(answers, clues, judge, timeout, log_path):
    verdicts = {}
    buckets: Counter = Counter()
    soundness: Counter = Counter()
    started = time.monotonic()

    for index, answer in enumerate(answers):
        entry_id = f"{index}A"
        clue = clues.get(entry_id, "")
        if not clue or clue.startswith(SCAFFOLD_PREFIX):
            verdicts[entry_id] = {"bucket": "scaffold", "sound": "n/a"}
            buckets["scaffold"] += 1
            continue

        first = _attempt_one(judge, clue, len(answer), timeout)
        first_guess = first.get("guess", "")
        if _normalize(first_guess) == _normalize(answer):
            second = {"guess": first_guess}
        else:
            second = _attempt_two(judge, clue, len(answer), first_guess, timeout)
        second_guess = second.get("guess", "")
        reveal = _reveal(judge, clue, answer, first_guess, second_guess, timeout)

        verdict = _classify(first, second, reveal, answer)
        verdict["clue"] = clue
        verdicts[entry_id] = verdict
        buckets[verdict["bucket"]] += 1
        soundness[verdict["sound"]] += 1

    return verdicts, dict(buckets), dict(soundness), round(time.monotonic() - started, 3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=Path("/tmp/clue-benchmark.json"))
    parser.add_argument("--judge", default=os.environ.get("CROSSWORD_JUDGE_MODEL", "gemma3:4b"))
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--verdicts-out", type=Path, default=Path("/tmp/clue-cold-solver-verdicts.json"))
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "private_clue_benchmark", ROOT / "scripts" / "private-clue-benchmark.py"
    )
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    answers = benchmark.BENCHMARK_ANSWERS

    payload = json.loads(args.log.read_text(encoding="utf-8"))
    label = payload.get("label", "unknown")
    clues = payload.get("clues") or {}

    verdicts, buckets, soundness, wall = probe(
        answers, clues, args.judge, args.timeout, args.log
    )

    judged = sum(count for name, count in buckets.items() if name != "scaffold")
    summary = {
        "label": label,
        "judge": args.judge,
        "buckets": buckets,
        "judged": judged,
        "goldRate": round(buckets.get("gold", 0) / judged, 4) if judged else 0.0,
        "trivialRate": round(buckets.get("trivial", 0) / judged, 4) if judged else 0.0,
        "unfairRate": round(buckets.get("unfair", 0) / judged, 4) if judged else 0.0,
        "unresolvedRate": round(buckets.get("unresolved", 0) / judged, 4) if judged else 0.0,
        "definitionSoundness": soundness,
        "soundRate": (
            round(soundness.get("sound", 0) / judged, 4) if judged else 0.0
        ),
        "wallSeconds": wall,
    }

    receipt = {
        "version": RECEIPT_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "counts-only",
        "claim": "blind cold-solver solvability probe; behaviour-derived buckets, no style score",
        "method": {
            "blind": "solver sees clue + length only; answer revealed after both attempts",
            "judgeIndependence": "judge model family differs from the drafter",
            "bucketDerivation": "computed in Python from solver-reported facts",
            "noWitScale": "no model emits a numeric quality or wit score",
        },
        "knownLimits": [
            "length-only probe: a real solver also sees crossing letters, so "
            "trivial detection is conservative and gold detection is strict",
            "unresolved is reported separately and never counted as gold",
            "solver self-reports its own trajectory; a 4b local model is a "
            "weak proxy for a human solver and a blind human verdict still "
            "overrides this receipt",
        ],
        "summary": summary,
    }
    if args.out is None:
        args.out = ROOT / "docs" / "evidence" / (
            f"{RECEIPT_VERSION}.{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    args.verdicts_out.write_text(
        json.dumps({"label": label, "verdicts": verdicts}, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"out": str(args.out), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
