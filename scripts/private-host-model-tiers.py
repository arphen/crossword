#!/usr/bin/env python3
"""Measure the model tiers reachable on this host (Q06).

Probes every installed registry tag with a warmed ``/api/generate`` call for
decode tok/s, reads resident size from ``ollama ps``, and records the tier
registry (tiers, memory ceilings, sampling) beside the measurements. An
optional saved playable-board job is summarized alongside. The receipt is
mechanical: tok/s and bytes, never a quality claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.crossword.private_puzzle_generation import (  # noqa: E402
    _MODEL_MEMORY_CEILINGS,
    _MODEL_TIERS,
    _TIER_SAMPLING,
)

RECEIPT_VERSION = "private-host-model-tiers-v1"
OLLAMA_URL = "http://127.0.0.1:11434"


def _get(path: str, timeout: float = 5.0):
    import urllib.request

    with urllib.request.urlopen(OLLAMA_URL + path, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post(path: str, payload: dict, timeout: float = 120.0):
    import urllib.request

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL + path, data=data, headers={"Content-Type": "application/json"}
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body, round(time.monotonic() - started, 3)


def _installed_models():
    try:
        return _get("/api/tags").get("models", [])
    except (OSError, ValueError):
        return []


def _probe_tag(tag: str) -> dict:
    """Warmed short decode: first call loads, second is measured."""
    probe = {
        "model": tag,
        "prompt": "Reply with exactly: READY",
        "stream": False,
        "options": {"num_predict": 16, "temperature": 0},
    }
    try:
        _post("/api/generate", probe)
        body, wall = _post("/api/generate", probe)
        eval_count = body.get("eval_count") or 0
        eval_ns = body.get("eval_duration") or 0
        tok_per_sec = round(eval_count / (eval_ns / 1e9), 2) if eval_ns else None
        return {
            "measured": True,
            "wallSeconds": wall,
            "evalCount": eval_count,
            "tokPerSec": tok_per_sec,
            "response": (body.get("response") or "")[:32],
        }
    except (OSError, ValueError) as error:
        return {"measured": False, "error": str(error)[:160]}


def _parse_size(text: str):
    match = re.fullmatch(r"\s*([\d.]+)\s*([KMGT]?B)\s*", (text or "").upper())
    if not match:
        return None
    value, unit = float(match.group(1)), match.group(2)
    return int(value * {"B": 1, "KB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12}[unit])


def _resident_bytes():
    """Resident per-model bytes from `ollama ps`, best effort."""
    try:
        completed = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    lines = (completed.stdout or "").splitlines()
    if len(lines) < 2:
        return {}
    header = re.split(r"\s{2,}", lines[0].strip())
    try:
        name_idx = next(i for i, col in enumerate(header) if col == "NAME")
        size_idx = next(i for i, col in enumerate(header) if col == "SIZE")
    except StopIteration:
        return {}
    resident = {}
    for line in lines[1:]:
        cols = re.split(r"\s{2,}", line.strip())
        if len(cols) > max(name_idx, size_idx):
            size = _parse_size(cols[size_idx])
            if size is not None:
                resident[cols[name_idx]] = size
    return resident


def _host():
    total_ram = None
    try:
        if sys.platform == "darwin":
            total_ram = int(
                subprocess.run(
                    ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=10
                ).stdout.strip()
            )
        else:
            with open("/proc/meminfo", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("MemTotal:"):
                        total_ram = int(line.split()[1]) * 1024
                        break
    except (OSError, ValueError, subprocess.TimeoutExpired):
        total_ram = None
    try:
        free_disk = shutil.disk_usage(str(ROOT)).free
    except OSError:
        free_disk = None
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "totalRamBytes": total_ram,
        "freeDiskBytes": free_disk,
    }


def _board_summary(path: Path | None):
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    result = payload.get("result") if isinstance(payload.get("result"), dict) else payload
    puzzle = result.get("puzzle") or {}
    entries = puzzle.get("entries", []) if isinstance(puzzle, dict) else []
    provenance = result.get("provenance", {}) if isinstance(result, dict) else {}
    quality = provenance.get("clueQuality", {}) if isinstance(provenance, dict) else {}
    return {
        "model": provenance.get("model"),
        "seed": provenance.get("seed"),
        "weekday": provenance.get("weekday"),
        "entries": len(entries),
        "issueCount": quality.get("issueCount"),
        "fallbackCount": quality.get("fallbackCount"),
        "timingsSeconds": provenance.get("timingsSeconds"),
        "source": str(path),
    }


def receipt_body(board_path: Path | None):
    installed = {item.get("name"): item for item in _installed_models() if isinstance(item, dict)}
    host = _host()
    lanes = []
    registry_tags = [tag for tags in _MODEL_TIERS.values() for tag in tags]
    for tag in registry_tags:
        info = installed.get(tag)
        if info is None:
            lanes.append({"tag": tag, "installed": False})
            continue
        tier = next(name for name, tags in _MODEL_TIERS.items() if tag in tags)
        ceiling = _MODEL_MEMORY_CEILINGS.get(tag)
        probe = _probe_tag(tag)
        # Single model slot: capture residency right after this tag's probe,
        # before the next probe evicts it.
        resident = _resident_bytes()
        lane = {
            "tag": tag,
            "tier": tier,
            "installed": True,
            "installedBytes": info.get("size"),
            "digest": (info.get("digest") or "")[:19],
            "residentBytes": resident.get(tag),
            "memoryCeilingBytes": ceiling,
            "admissibleOnThisHost": ceiling is not None
            and (host["totalRamBytes"] or 0) >= ceiling,
            "sampling": _TIER_SAMPLING.get(tier),
            "probe": probe,
        }
        lanes.append(lane)
    receipt = {
        "version": RECEIPT_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "claim": "measured decode tok/s and resident bytes per installed tag; never a quality claim",
        "host": host,
        "registry": {
            "tiers": {name: list(tags) for name, tags in _MODEL_TIERS.items()},
            "memoryCeilingsBytes": dict(_MODEL_MEMORY_CEILINGS),
            "sampling": {name: dict(params) for name, params in _TIER_SAMPLING.items()},
        },
        "lanes": lanes,
        "playableBoard": _board_summary(board_path),
        "knownLimits": [
            "tok/s is one warmed 16-token probe, not a generation benchmark",
            "resident size is best-effort ollama ps parsing at measure time",
            "admissibility compares the ceiling to total RAM, not live pressure",
        ],
    }
    digest = hashlib.sha256(
        json.dumps(receipt, sort_keys=True).encode("utf-8")
    ).hexdigest()
    receipt["receiptDigest"] = "sha256:" + digest
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT
        / "docs"
        / "evidence"
        / f"{RECEIPT_VERSION}.m3-16gb-{datetime.now(timezone.utc).strftime('%Y%m%d')}.json",
        help="where to write the receipt (default: docs/evidence)",
    )
    parser.add_argument(
        "--playable-board",
        type=Path,
        default=None,
        help="saved ready-job JSON from an end-to-end board on this host",
    )
    args = parser.parse_args()
    receipt = receipt_body(args.playable_board)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": os.path.relpath(args.out, ROOT),
                "lanes": [
                    {
                        "tag": lane["tag"],
                        "installed": lane["installed"],
                        "tokPerSec": lane.get("probe", {}).get("tokPerSec"),
                        "residentBytes": lane.get("residentBytes"),
                    }
                    for lane in receipt["lanes"]
                ],
                "playableBoard": receipt["playableBoard"] is not None,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
