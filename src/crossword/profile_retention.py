"""Bounded local retention for the /future profile lane.

Retention is deliberately narrower than profile deletion.  It removes only
expired durable-job rows and their private, non-playable generation artefacts.
Solve sessions, solve events, reflections, calibration journals, episteme
records, and shared puzzle manifests are never selected by this policy.

The endpoint is same-origin and profile-scoped.  A dry run is available so a
host can show the exact audit before committing the cleanup.
"""

from datetime import datetime, timedelta, timezone
import json
from uuid import UUID

from flask import Blueprint, jsonify, request
from sqlalchemy import delete, text

from .database import db
from .future import StartingProfile
from .future_grid_jobs import FutureGridDraftJob, FutureGridDraftPrivateSelection
from .future_puzzles import FuturePuzzleV2CandidateRecord


profile_retention_api = Blueprint("profile_retention_api", __name__)

RETENTION_POLICY_VERSION = "future-local-retention-v1"
TRANSIENT_JOB_RETENTION_DAYS = 7
PRIVATE_ARTIFACT_RETENTION_DAYS = 30
_MAX_BODY_BYTES = 1024
_TRANSIENT_STATES = frozenset({"queued", "failed", "cancelled"})


def _now():
    return datetime.now(timezone.utc)


def _valid_uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (AttributeError, ValueError):
        return False


def _same_origin():
    origin = request.headers.get("Origin")
    return origin is None or origin == request.host_url.rstrip("/")


def _error(message, status):
    response = jsonify(error=message)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _timestamp(value):
    """Parse the host's canonical ISO timestamp, returning UTC or None."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _policy(now):
    transient_cutoff = now - timedelta(days=TRANSIENT_JOB_RETENTION_DAYS)
    artifact_cutoff = now - timedelta(days=PRIVATE_ARTIFACT_RETENTION_DAYS)
    return {
        "version": RETENTION_POLICY_VERSION,
        "transientJobRetentionDays": TRANSIENT_JOB_RETENTION_DAYS,
        "privateArtifactRetentionDays": PRIVATE_ARTIFACT_RETENTION_DAYS,
        "transientCutoff": transient_cutoff.isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        ),
        "privateArtifactCutoff": artifact_cutoff.isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z"),
    }


def _mode(job):
    request_json = job.request_json
    return request_json.get("mode") if isinstance(request_json, dict) else None


def _empty_audit(profile_id, *, now, dry_run):
    return {
        "profileId": profile_id,
        "dryRun": dry_run,
        "policy": _policy(now),
        "examined": {"jobs": 0, "v2Candidates": 0},
        "selected": {
            "transientJobs": 0,
            "privateReadyJobs": 0,
            "privateSelections": 0,
            "v2Candidates": 0,
        },
        "deleted": {
            "jobs": 0,
            "privateSelections": 0,
            "v2Candidates": 0,
        },
        "skipped": {
            "runningJobs": 0,
            "freshJobs": 0,
            "unsupportedStates": 0,
            "invalidTimestamps": 0,
        },
        "preserved": [
            "solve sessions and events",
            "reflection history",
            "calibration journals",
            "episteme records",
            "shared puzzle manifests",
        ],
    }


def retain_profile(profile_id, *, now=None, dry_run=False):
    """Return an audit and optionally delete expired profile-owned artefacts.

    ``now`` exists for deterministic tests and local operators.  Only terminal
    transient jobs and terminal ``private-puzzle`` jobs are eligible.  A
    running row is always preserved, even after its lease expires; the worker's
    own lease recovery remains the authority for active work.
    """
    now = now or _now()
    audit = _empty_audit(profile_id, now=now, dry_run=dry_run)
    jobs = (
        FutureGridDraftJob.query.filter_by(profile_id=profile_id)
        .order_by(FutureGridDraftJob.created_at, FutureGridDraftJob.id)
        .all()
    )
    candidates = FuturePuzzleV2CandidateRecord.query.filter_by(
        profile_id=profile_id
    ).all()
    audit["examined"]["jobs"] = len(jobs)
    audit["examined"]["v2Candidates"] = len(candidates)

    transient_cutoff = now - timedelta(days=TRANSIENT_JOB_RETENTION_DAYS)
    artifact_cutoff = now - timedelta(days=PRIVATE_ARTIFACT_RETENTION_DAYS)
    deleted_job_ids = set()

    for job in jobs:
        if job.state == "running":
            audit["skipped"]["runningJobs"] += 1
            continue
        if job.state not in _TRANSIENT_STATES and not (
            job.state == "ready" and _mode(job) == "private-puzzle"
        ):
            audit["skipped"]["unsupportedStates"] += 1
            continue
        updated = _timestamp(job.updated_at)
        if updated is None:
            audit["skipped"]["invalidTimestamps"] += 1
            continue
        if job.state in _TRANSIENT_STATES:
            if updated < transient_cutoff:
                deleted_job_ids.add(job.id)
                audit["selected"]["transientJobs"] += 1
            else:
                audit["skipped"]["freshJobs"] += 1
            continue
        if updated < artifact_cutoff:
            deleted_job_ids.add(job.id)
            audit["selected"]["privateReadyJobs"] += 1
        else:
            audit["skipped"]["freshJobs"] += 1

    selections = (
        FutureGridDraftPrivateSelection.query.filter(
            FutureGridDraftPrivateSelection.profile_id == profile_id,
            FutureGridDraftPrivateSelection.job_id.in_(deleted_job_ids),
        ).all()
        if deleted_job_ids
        else []
    )
    candidates_to_delete = [
        candidate
        for candidate in candidates
        if candidate.job_id in deleted_job_ids
    ]
    # A prior interrupted cleanup can leave a candidate whose job row has
    # already gone.  It is safe to remove only after the same private-artifact
    # age check; a candidate with a surviving job remains untouched.
    existing_job_ids = {job.id for job in jobs}
    for candidate in candidates:
        if candidate in candidates_to_delete or candidate.job_id in existing_job_ids:
            continue
        created = _timestamp(candidate.created_at)
        if created is not None and created < artifact_cutoff:
            candidates_to_delete.append(candidate)

    audit["selected"]["privateSelections"] = len(selections)
    audit["selected"]["v2Candidates"] = len(candidates_to_delete)
    if dry_run:
        return audit

    # All rows are profile-scoped and children are removed before jobs.  No
    # solve/history tables are touched by this transaction.
    if selections:
        db.session.execute(
            delete(FutureGridDraftPrivateSelection).where(
                FutureGridDraftPrivateSelection.job_id.in_(
                    [selection.job_id for selection in selections]
                ),
                FutureGridDraftPrivateSelection.profile_id == profile_id,
            )
        )
    if candidates_to_delete:
        db.session.execute(
            delete(FuturePuzzleV2CandidateRecord).where(
                FuturePuzzleV2CandidateRecord.profile_id == profile_id,
                FuturePuzzleV2CandidateRecord.candidate_hash.in_(
                    [candidate.candidate_hash for candidate in candidates_to_delete]
                ),
            )
        )
    if deleted_job_ids:
        db.session.execute(
            delete(FutureGridDraftJob).where(
                FutureGridDraftJob.profile_id == profile_id,
                FutureGridDraftJob.id.in_(deleted_job_ids),
                # Recheck terminal state in the write so a concurrently
                # claimed job cannot be removed by a stale audit.
                FutureGridDraftJob.state.in_(
                    [*sorted(_TRANSIENT_STATES), "ready"]
                ),
            )
        )
    db.session.commit()
    audit["deleted"] = {
        "jobs": len(deleted_job_ids),
        "privateSelections": len(selections),
        "v2Candidates": len(candidates_to_delete),
    }
    return audit


@profile_retention_api.post("/api/future/profile/<profile_id>/retention")
def profile_retention(profile_id):
    if not _same_origin():
        return _error("Cross-origin profile retention is not allowed", 403)
    if not _valid_uuid(profile_id):
        return _error("Invalid profile id", 400)
    if db.session.get(StartingProfile, profile_id) is None:
        return _error("Profile not found", 404)
    request.max_content_length = _MAX_BODY_BYTES
    body = request.get_json(silent=True)
    if body is None:
        body = {}
    if not isinstance(body, dict) or set(body) - {"dryRun"}:
        return _error("Retention request may include only dryRun", 400)
    dry_run = body.get("dryRun", False)
    if type(dry_run) is not bool:
        return _error("dryRun must be a boolean", 400)
    try:
        # Serialize the audit and deletion with local worker claims.  The
        # profile existence query above may have opened a read transaction;
        # reset it before taking SQLite's local write lock.
        db.session.rollback()
        if db.engine.dialect.name == "sqlite":
            db.session.execute(text("BEGIN IMMEDIATE"))
        audit = retain_profile(profile_id, dry_run=dry_run)
    except (TypeError, ValueError, RecursionError, json.JSONDecodeError):
        db.session.rollback()
        return _error("Profile retention could not be completed", 500)
    response = jsonify(audit)
    response.headers["Cache-Control"] = "no-store"
    return response
