"""Read-only local runtime readiness for the private ``/future`` lane.

The endpoint reports whether the local ingredients for a private puzzle are
reachable.  It is deliberately advisory: generation and the daily ``/`` lane
do not depend on this response, and the response never includes environment
values, request URLs, process arguments, model metadata, or exception text.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from threading import Lock
from typing import Any

import requests
from flask import Blueprint, current_app, jsonify
from sqlalchemy import func

from .construction_runtime import RUNTIME_CLI
from .database import db
from .future_grid_jobs import FutureGridDraftJob


runtime_readiness_api = Blueprint("runtime_readiness_api", __name__)

READINESS_VERSION = "future-runtime-readiness-v1"
HEARTBEAT_VERSION = 1
WORKER_HEARTBEAT_STALE_SECONDS = 10.0
OLLAMA_CONNECT_TIMEOUT_SECONDS = 1.0
OLLAMA_READ_TIMEOUT_SECONDS = 2.0

# Kept in a single helper so the readiness report and the private generation
# lane can be compared without serializing a configured model or host value.
_DEFAULT_MODEL_TAGS = (
    "gemma4:26b",
    "qwen3.8:27b",
    "gemma4:31b",
    "gemma3:27b",
)
_HEARTBEAT_WRITE_LOCK = Lock()


def preferred_model_tags(environ: dict[str, str] | None = None) -> list[str]:
    """Return the ordered model tags the local future lane is willing to use."""
    source = os.environ if environ is None else environ
    values = [
        source.get("CROSSWORD_PUZZLE_MODEL"),
        source.get("CROSSWORD_PROFILE_MODEL"),
        *_DEFAULT_MODEL_TAGS,
    ]
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        tag = value.strip()
        # Ollama model tags are intentionally kept opaque to this endpoint,
        # but reject control/whitespace characters so an accidentally supplied
        # environment value cannot become an injection-shaped response field.
        if any(ord(char) < 0x20 or char.isspace() for char in tag):
            continue
        if tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result


def _ollama_tags_url() -> str:
    """Return the private loopback tags endpoint without exposing it to clients."""
    configured = current_app.config.get("FUTURE_OLLAMA_BASE_URL")
    if isinstance(configured, str) and configured.strip():
        base = configured.strip().rstrip("/")
    else:
        base = "http://127.0.0.1:11434"
    # The current generation path is local-only.  Keep this helper limited to
    # loopback URLs even if a test or an operator supplies a base URL.
    if base not in {
        "http://127.0.0.1:11434",
        "http://localhost:11434",
        "http://[::1]:11434",
    }:
        return "http://127.0.0.1:11434/api/tags"
    return f"{base}/api/tags"


def _ollama_status() -> dict[str, Any]:
    preferred = preferred_model_tags()
    try:
        response = requests.get(
            _ollama_tags_url(),
            timeout=(OLLAMA_CONNECT_TIMEOUT_SECONDS, OLLAMA_READ_TIMEOUT_SECONDS),
        )
        response.raise_for_status()
        payload = response.json()
        raw_models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(raw_models, list):
            return {
                "reachable": True,
                "status": "invalid-response",
                "preferredModels": preferred,
                "installedPreferredModels": [],
            }
        installed: set[str] = set()
        for item in raw_models:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                name = item["name"].strip()
                if name and not any(ord(char) < 0x20 for char in name):
                    installed.add(name)
        installed_preferred = [tag for tag in preferred if tag in installed]
        return {
            "reachable": True,
            "status": "ready" if installed_preferred else "no-preferred-model",
            "preferredModels": preferred,
            "installedPreferredModels": installed_preferred,
            "installedPreferredCount": len(installed_preferred),
        }
    except requests.RequestException:
        return {
            "reachable": False,
            "status": "unreachable",
            "preferredModels": preferred,
            "installedPreferredModels": [],
        }
    except (TypeError, ValueError, AttributeError):
        return {
            "reachable": True,
            "status": "invalid-response",
            "preferredModels": preferred,
            "installedPreferredModels": [],
        }


def _configured_xfill_root() -> Path | None:
    value = os.environ.get("CROSSWORD_XFILL_ROOT")
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return Path(value).expanduser()
    except (TypeError, ValueError):
        return None


def _xfill_status() -> dict[str, Any]:
    root = _configured_xfill_root()
    if root is None:
        return {
            "configured": False,
            "available": False,
            "status": "not-configured",
            "runtimeCliAvailable": RUNTIME_CLI.is_file(),
        }
    try:
        is_directory = root.is_dir()
        data_files = {
            filename: (root / "data" / filename).is_file()
            for filename in ("xwordlist.dict", "supplemental.txt")
        }
        runtime_cli_available = RUNTIME_CLI.is_file()
    except OSError:
        return {
            "configured": True,
            "available": False,
            "status": "unavailable",
            "runtimeCliAvailable": False,
        }
    available = is_directory and all(data_files.values()) and runtime_cli_available
    return {
        "configured": True,
        "available": available,
        "status": "ready" if available else "incomplete",
        "runtimeCliAvailable": runtime_cli_available,
        "wordlistAvailable": data_files["xwordlist.dict"],
        "supplementalAvailable": data_files["supplemental.txt"],
    }


def _heartbeat_path() -> Path:
    configured = os.environ.get("CROSSWORD_FUTURE_WORKER_HEARTBEAT")
    if isinstance(configured, str) and configured.strip():
        return Path(configured).expanduser()
    # A digest separates parallel local checkouts and test databases without
    # exposing the database URI in the filesystem or readiness response.
    database_uri = str(current_app.config.get("SQLALCHEMY_DATABASE_URI", "default"))
    digest = hashlib.sha256(database_uri.encode("utf-8", errors="replace")).hexdigest()[
        :16
    ]
    return Path(tempfile.gettempdir()) / f"crossword-future-worker-{digest}.json"


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _pid_is_alive(value: Any) -> bool:
    if type(value) is not int or value <= 0:
        return False
    try:
        os.kill(value, 0)
    except (OSError, ProcessLookupError):
        return False
    except PermissionError:
        # A local process can be alive while the Flask user cannot signal it.
        return True
    return True


def _worker_status() -> dict[str, Any]:
    path = _heartbeat_path()
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, UnicodeError, ValueError, TypeError):
        return {
            "available": False,
            "status": "missing",
            "heartbeatFresh": False,
        }
    if not isinstance(payload, dict) or payload.get("version") != HEARTBEAT_VERSION:
        return {
            "available": False,
            "status": "invalid",
            "heartbeatFresh": False,
        }
    heartbeat_at = _parse_timestamp(payload.get("heartbeatAt"))
    now = datetime.now(timezone.utc)
    age = (
        None if heartbeat_at is None else max(0.0, (now - heartbeat_at).total_seconds())
    )
    fresh = age is not None and age <= WORKER_HEARTBEAT_STALE_SECONDS
    pid_alive = _pid_is_alive(payload.get("pid"))
    if not fresh:
        status = "stale"
    elif not pid_alive:
        status = "process-exited"
    elif payload.get("state") == "working":
        status = "working"
    else:
        status = "ready"
    result: dict[str, Any] = {
        "available": fresh and pid_alive,
        "status": status,
        "heartbeatFresh": fresh,
        "processAlive": pid_alive,
    }
    if age is not None:
        result["heartbeatAgeSeconds"] = round(age, 3)
    return result


def _queue_status() -> dict[str, Any]:
    try:
        counts = dict(
            db.session.query(
                FutureGridDraftJob.state, func.count(FutureGridDraftJob.id)
            )
            .group_by(FutureGridDraftJob.state)
            .all()
        )
    except Exception:  # pragma: no cover - defensive: readiness must stay read-only
        db.session.rollback()
        return {"reachable": False}
    return {
        "reachable": True,
        "queued": int(counts.get("queued", 0)),
        "running": int(counts.get("running", 0)),
    }


def _readiness_payload() -> dict[str, Any]:
    ollama = _ollama_status()
    xfill = _xfill_status()
    worker = _worker_status()
    queue = _queue_status()
    process = {
        "ready": True,
        "databaseReachable": queue.get("reachable") is True,
    }
    return {
        "version": READINESS_VERSION,
        "ready": bool(
            process["ready"]
            and process["databaseReachable"]
            and ollama["reachable"]
            and ollama.get("installedPreferredCount", 0) > 0
            and xfill["available"]
            and worker["available"]
        ),
        "process": process,
        "ollama": ollama,
        "xfill": xfill,
        "worker": worker,
        "queue": queue,
    }


@runtime_readiness_api.get("/api/future/runtime-readiness")
def runtime_readiness():
    """Return advisory local runtime readiness without gating any future route."""
    response = jsonify(_readiness_payload())
    response.headers["Cache-Control"] = "no-store"
    return response


# Keep heartbeat writes in this module so the worker and endpoint share one
# bounded, versioned file contract.  They intentionally return no filesystem
# path or exception to callers.
def worker_heartbeat_path(*, app=None) -> Path:
    """Resolve the worker heartbeat location from the same local settings."""
    if app is None:
        return _heartbeat_path()
    with app.app_context():
        return _heartbeat_path()


def write_worker_heartbeat(*, state: str, pid: int | None = None) -> None:
    if state not in {"idle", "working"}:
        raise ValueError("Unsupported worker heartbeat state")
    target = _heartbeat_path()
    payload = {
        "version": HEARTBEAT_VERSION,
        "pid": os.getpid() if pid is None else pid,
        "state": state,
        "heartbeatAt": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }
    serialized = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    temporary: Path | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with _HEARTBEAT_WRITE_LOCK:
            temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
            temporary.write_text(serialized, encoding="utf-8")
            os.chmod(temporary, 0o600)
            os.replace(temporary, target)
    except OSError:
        # Runtime telemetry must never prevent local puzzle generation.
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def clear_worker_heartbeat(*, pid: int | None = None) -> None:
    target = _heartbeat_path()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        expected_pid = os.getpid() if pid is None else pid
        if isinstance(payload, dict) and payload.get("pid") != expected_pid:
            return
        target.unlink(missing_ok=True)
    except (OSError, UnicodeError, ValueError, TypeError):
        return
