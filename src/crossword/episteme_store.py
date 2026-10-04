"""Host persistence boundary for the shared deterministic episteme reducer."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, OperationalError

from .database import db

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REDUCER_SCRIPT = PROJECT_ROOT / "scripts" / "episteme-reducer.cjs"
# This is a storage safety ceiling, not the expected lifetime size. A profile
# keeps its inspectable evidence and update receipts; 64 MiB leaves room for
# years of ordinary play while bounding a corrupted or abusive local record.
MAX_PROFILE_BYTES = 64 * 1024 * 1024
MAX_COMMAND_BYTES = 256 * 1024


class EpistemeProfileRecord(db.Model):
    __tablename__ = "future_episteme_profiles"

    id = db.Column(db.String(36), primary_key=True)
    revision = db.Column(db.Integer, nullable=False, default=0)
    profile_json = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(db.String(40), nullable=False)


class EpistemeRuntimeUnavailable(RuntimeError):
    """Node or the fixed reducer bridge is not available on this host."""


class EpistemeCommandRejected(ValueError):
    """The shared TypeScript reducer rejected an untrusted command."""


class EpistemeRevisionConflict(EpistemeCommandRejected):
    """The command is valid, but its idempotency key or base revision conflicts."""


def _as_conflict(error):
    message = str(error)
    if message.startswith("Stale profile revision") or message == "Episteme updateId was reused with different evidence":
        return EpistemeRevisionConflict(message)
    return error


def run_reducer(operation):
    """Run one bounded JSON operation through the same TS code used by tests/UI."""
    node = shutil.which("node")
    if not node or not REDUCER_SCRIPT.is_file():
        raise EpistemeRuntimeUnavailable("The local TypeScript reducer is unavailable")
    serialized = json.dumps(operation, ensure_ascii=False, separators=(",", ":"))
    if len(serialized.encode("utf-8")) > MAX_PROFILE_BYTES + MAX_COMMAND_BYTES:
        raise EpistemeCommandRejected("Episteme command is too large")
    try:
        result = subprocess.run(
            [node, str(REDUCER_SCRIPT)],
            input=serialized,
            text=True,
            capture_output=True,
            timeout=5,
            cwd=PROJECT_ROOT,
            env={"PATH": os.environ.get("PATH", "")},
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EpistemeRuntimeUnavailable("The local TypeScript reducer did not respond") from error
    if result.returncode != 0:
        try:
            error_value = json.loads(result.stderr)
        except (ValueError, AttributeError):
            # A stack trace here means Node could not load the fixed bridge or
            # its runtime dependencies; it is a host problem, not bad input.
            raise EpistemeRuntimeUnavailable("The local profile reducer could not start")
        message = error_value.get("error") if isinstance(error_value, dict) else None
        if not isinstance(message, str):
            raise EpistemeRuntimeUnavailable("The local profile reducer could not start")
        raise _as_conflict(EpistemeCommandRejected(message[:240]))
    try:
        value = json.loads(result.stdout)
    except ValueError as error:
        raise EpistemeRuntimeUnavailable("The local TypeScript reducer returned invalid JSON") from error
    return value


def episteme_profile_size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def get_or_create_episteme_profile(profile_id, created_at):
    record = db.session.get(EpistemeProfileRecord, profile_id)
    if record is not None:
        return record
    profile = run_reducer({"operation": "create", "profileId": profile_id, "createdAt": created_at})["profile"]
    record = EpistemeProfileRecord(
        id=profile_id,
        revision=profile["revision"],
        profile_json=profile,
        updated_at=created_at,
    )
    db.session.add(record)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = db.session.get(EpistemeProfileRecord, profile_id)
        if existing is None:
            raise
        return existing
    return record


def project_episteme_profile(profile, as_of):
    """Refresh derived fields at read time without rewriting the evidence ledger."""
    result = run_reducer({"operation": "project", "profile": profile, "asOf": as_of})
    projected = result.get("profile") if isinstance(result, dict) else None
    if not isinstance(projected, dict) or projected.get("profileId") != profile.get("profileId"):
        raise EpistemeRuntimeUnavailable("The local profile reducer returned an invalid projection")
    return projected


def apply_episteme_command(profile_id, current_revision, profile, command):
    try:
        result = run_reducer({"operation": "apply", "profile": profile, "command": command})
    except EpistemeCommandRejected as error:
        raise _as_conflict(error) from error
    updated = result["profile"]
    if episteme_profile_size(updated) > MAX_PROFILE_BYTES:
        raise EpistemeCommandRejected("Episteme profile exceeds the storage limit")
    if result.get("replayed"):
        return result, False
    try:
        changed = db.session.execute(
            update(EpistemeProfileRecord)
            .where(
                EpistemeProfileRecord.id == profile_id,
                EpistemeProfileRecord.revision == current_revision,
            )
            .values(
                revision=updated["revision"],
                profile_json=updated,
                updated_at=updated["updatedAt"],
            )
        )
        if changed.rowcount != 1:
            return replay_or_conflict_after_cas_loss(profile_id, current_revision, command)
        db.session.commit()
    except OperationalError:
        # SQLite can surface a simultaneous writer as a lock error instead of
        # a zero-row CAS. Resolve it the same way after releasing our snapshot.
        return replay_or_conflict_after_cas_loss(profile_id, current_revision, command)
    return result, True


def replay_or_conflict_after_cas_loss(profile_id, previous_revision, command):
    """Turn a losing duplicate request into success when its winner committed."""
    db.session.rollback()
    latest = db.session.get(EpistemeProfileRecord, profile_id)
    if latest is not None:
        try:
            result = run_reducer({"operation": "apply", "profile": latest.profile_json, "command": command})
        except EpistemeCommandRejected as error:
            conflict = _as_conflict(error)
            if conflict is not error:
                raise conflict from error
            if latest.revision != previous_revision:
                raise EpistemeRevisionConflict("Stale profile revision: another update won the commit") from error
            raise
        if result.get("replayed"):
            return result, False
        if latest.revision != previous_revision:
            raise EpistemeRevisionConflict("Stale profile revision: another update won the commit")
    raise EpistemeRevisionConflict("Stale profile revision: another update won the commit")


def now_utc_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
