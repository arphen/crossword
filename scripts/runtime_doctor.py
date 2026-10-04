"""Read-only readiness check for the local private-puzzle runtime.

This command intentionally never invokes Cargo, xfill generation, or
``ollama pull``.  It checks the files and loopback services that a normal
``make run`` private-puzzle job will need, so a missing dependency can be
fixed before spending a minute on model generation.

The output is deliberately small and stable enough to paste into a bug
report.  Use ``--json`` when another local tool needs the individual checks.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.crossword.private_domain_hints import load_private_domain_hints


RUNTIME_PACKAGE = ROOT / "node_modules" / "@crossword" / "local-runtime"
RUNTIME_CLI = RUNTIME_PACKAGE / "bin" / "local-runtime.mjs"
RUNTIME_ARCHIVE = ROOT / "vendor" / "generator" / "crossword-local-runtime-0.1.2.tgz"
RUNTIME_ARCHIVE_RESOLVED = "file:vendor/generator/crossword-local-runtime-0.1.2.tgz"
DEFAULT_XFILL_ROOT = ROOT.parent / "crossword-generator" / "vendor" / "xfill"
DEFAULT_MODEL_TAGS = (
    "gemma4:26b",
    "qwen3.8:27b",
    "gemma4:31b",
    "gemma3:27b",
    "llama3.2:3b",
    "gemma3:4b",
)
OLLAMA_TIMEOUT_SECONDS = 2.0
PROTOCOL_TIMEOUT_SECONDS = 5.0


def _preferred_model_tags(environ: dict[str, str] | None = None) -> list[str]:
    source = os.environ if environ is None else environ
    values = [
        source.get("CROSSWORD_PUZZLE_MODEL"),
        source.get("CROSSWORD_PROFILE_MODEL"),
        *DEFAULT_MODEL_TAGS,
    ]
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        tag = value.strip()
        if any(ord(char) < 0x20 or char.isspace() for char in tag):
            continue
        if tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result


def _sha512_integrity(path: Path) -> str:
    digest = hashlib.sha512()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha512-" + base64.b64encode(digest.digest()).decode("ascii")


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _check_runtime_archive() -> dict[str, Any]:
    lock = _load_json(ROOT / "package-lock.json")
    lock_entry = (
        (lock or {}).get("packages", {}).get("node_modules/@crossword/local-runtime")
    )
    if not isinstance(lock_entry, dict):
        return {"ready": False, "status": "lock-entry-missing"}
    if lock_entry.get("resolved") != RUNTIME_ARCHIVE_RESOLVED:
        return {"ready": False, "status": "lock-resolution-mismatch"}
    expected_version = lock_entry.get("version")
    if expected_version != "0.1.2":
        return {"ready": False, "status": "lock-version-mismatch"}
    integrity = lock_entry.get("integrity")
    if not isinstance(integrity, str) or not integrity.startswith("sha512-"):
        return {"ready": False, "status": "lock-integrity-missing"}
    if not RUNTIME_ARCHIVE.is_file():
        return {"ready": False, "status": "archive-missing"}
    try:
        actual_integrity = _sha512_integrity(RUNTIME_ARCHIVE)
    except OSError:
        return {"ready": False, "status": "archive-unreadable"}
    if actual_integrity != integrity:
        return {"ready": False, "status": "archive-integrity-mismatch"}
    package = _load_json(RUNTIME_PACKAGE / "package.json")
    if not isinstance(package, dict) or package.get("version") != expected_version:
        return {"ready": False, "status": "installed-package-mismatch"}
    if not (RUNTIME_PACKAGE / "dist" / "cli.js").is_file():
        return {"ready": False, "status": "installed-cli-module-missing"}
    return {
        "ready": True,
        "status": "ready",
        "version": expected_version,
        "archiveIntegrity": actual_integrity,
    }


def _check_runtime_cli() -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        return {"ready": False, "status": "node-missing"}
    if not RUNTIME_CLI.is_file():
        return {"ready": False, "status": "cli-missing"}
    # An intentionally invalid protocol version makes the CLI load its real
    # package imports while stopping before Cargo/xfill is ever invoked.
    try:
        result = subprocess.run(
            [node, str(RUNTIME_CLI)],
            input='{"version":0,"options":{}}\n',
            text=True,
            capture_output=True,
            cwd=ROOT,
            timeout=PROTOCOL_TIMEOUT_SECONDS,
            check=False,
        )
        response = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, UnicodeError, ValueError):
        return {"ready": False, "status": "protocol-smoke-failed"}
    error = response.get("error") if isinstance(response, dict) else None
    protocol_ok = (
        result.returncode != 0
        and response.get("version") == 1
        and isinstance(error, dict)
        and "Unsupported protocol version" in str(error.get("message", ""))
    )
    return {
        "ready": protocol_ok,
        "status": "ready" if protocol_ok else "protocol-smoke-failed",
        "protocolVersion": 1 if protocol_ok else None,
    }


def _configured_xfill_root(environ: dict[str, str] | None = None) -> Path:
    source = os.environ if environ is None else environ
    value = source.get("CROSSWORD_XFILL_ROOT")
    return (
        Path(value).expanduser()
        if isinstance(value, str) and value.strip()
        else DEFAULT_XFILL_ROOT
    )


def _check_xfill_engine(environ: dict[str, str] | None = None) -> dict[str, Any]:
    root = _configured_xfill_root(environ)
    required = (
        "Cargo.toml",
        "Cargo.lock",
        "crates/xfill-cli/src/bin/library.rs",
        "crates/xfill-cli/src/bin/theme.rs",
        "data/xwordlist.dict",
    )
    missing = [relative for relative in required if not (root / relative).is_file()]
    missing.extend(
        executable
        for executable in ("cargo", "rustc")
        if shutil.which(executable) is None
    )
    if missing:
        return {
            "ready": False,
            "status": "incomplete",
            "missing": missing,
        }
    return {"ready": True, "status": "ready"}


def _ollama_url(environ: dict[str, str] | None = None) -> str | None:
    source = os.environ if environ is None else environ
    value = source.get("CROSSWORD_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    if not isinstance(value, str) or not value.strip():
        return None
    base = value.strip().rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        return None
    return f"{base}/api/tags"


def _check_ollama(environ: dict[str, str] | None = None) -> dict[str, Any]:
    preferred = _preferred_model_tags(environ)
    url = _ollama_url(environ)
    if url is None:
        return {
            "ready": False,
            "status": "loopback-only-url-required",
            "preferredModels": preferred,
            "installedPreferredModels": [],
        }
    try:
        request = Request(url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read(2 * 1024 * 1024).decode("utf-8"))
    except (OSError, URLError, TimeoutError, UnicodeError, ValueError):
        return {
            "ready": False,
            "status": "unreachable",
            "preferredModels": preferred,
            "installedPreferredModels": [],
        }
    raw_models = payload.get("models") if isinstance(payload, dict) else None
    names = {
        item.get("name").strip()
        for item in raw_models or []
        if isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and item.get("name", "").strip()
    }
    installed = [tag for tag in preferred if tag in names]
    return {
        "ready": bool(installed),
        "status": "ready" if installed else "no-preferred-model",
        "preferredModels": preferred,
        "installedPreferredModels": installed,
    }


def _private_hint_fill_words(environ: dict[str, str] | None = None) -> set[str]:
    """Read the same bounded answer shapes the native runtime can place."""

    root = _configured_xfill_root(environ)
    words: set[str] = set()
    for filename in ("data/xwordlist.dict", "data/supplemental.txt"):
        try:
            raw = (root / filename).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for line in raw.splitlines():
            if not line or line.startswith("#"):
                continue
            word = line.split(";", 1)[0].strip().upper()
            if word.isalpha() and 3 <= len(word) <= 15 and len(word) != 12:
                words.add(word)
    return words


def _check_private_domain_hints(
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Report the optional private hint bridge without exposing its terms."""

    source = os.environ if environ is None else environ
    configured = source.get("CROSSWORD_PRIVATE_DOMAIN_HINTS")
    if not isinstance(configured, str) or not configured.strip():
        return {
            "ready": True,
            "status": "not-configured",
            "optional": True,
            "termCount": 0,
            "placeableCount": 0,
        }

    loaded = load_private_domain_hints(
        path=configured,
        fill_words=_private_hint_fill_words(environ),
    )
    result: dict[str, Any] = {
        "ready": loaded.get("status") == "loaded",
        "status": loaded.get("status", "unavailable"),
        "optional": True,
        "termCount": len(loaded.get("terms", [])),
        "placeableCount": len(loaded.get("placeableTerms", [])),
    }
    for key in ("domainId", "label", "reason", "artifactSha256"):
        if isinstance(loaded.get(key), str):
            result[key] = loaded[key]
    return result


def collect_report(environ: dict[str, str] | None = None) -> dict[str, Any]:
    components = {
        "localRuntimeArchive": _check_runtime_archive(),
        "localRuntimeCli": _check_runtime_cli(),
        "xfillEngine": _check_xfill_engine(environ),
        "ollama": _check_ollama(environ),
        "privateDomainHints": _check_private_domain_hints(environ),
    }
    return {
        "version": "runtime-doctor-v1",
        "readOnly": True,
        "modelPull": False,
        "ready": all(item["ready"] for item in components.values()),
        "components": components,
    }


def _print_report(report: dict[str, Any]) -> None:
    print("Runtime doctor (read-only; no model pulls)")
    components = report["components"]
    labels = (
        ("localRuntimeArchive", "xfill runtime archive"),
        ("localRuntimeCli", "xfill runtime CLI"),
        ("xfillEngine", "native xfill engine"),
        ("ollama", "Ollama model"),
        ("privateDomainHints", "private domain hints"),
    )
    for key, label in labels:
        component = components[key]
        suffix = component.get("status", "unknown")
        if key == "ollama" and component.get("installedPreferredModels"):
            suffix += ": " + ", ".join(component["installedPreferredModels"])
        if key == "privateDomainHints" and component.get("status") == "loaded":
            suffix += ": " + str(component.get("placeableCount", 0)) + " placeable"
        print(f"[{label}] {'ready' if component['ready'] else 'not ready'} ({suffix})")
    if report["ready"]:
        print("Runtime doctor: ready for make run-personal (or make run).")
    else:
        print("Runtime doctor: not ready; fix the checks above, then run make run-personal.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="emit the versioned report as JSON"
    )
    args = parser.parse_args(argv)
    report = collect_report()
    if args.json:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    else:
        _print_report(report)
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
