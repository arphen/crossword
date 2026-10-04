"""Delayed, local-only recall probes for explicitly selected learning languages.

Private crossword exposure is not mastery.  This module keeps a small host
record of independent or assisted recall responses and derives due prompts from
the immutable session-analysis evidence already stored in the episteme.
"""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from math import exp, isfinite, log
from uuid import UUID, uuid4

from flask import Blueprint, jsonify, request

from .database import db
from .episteme_store import EpistemeProfileRecord
from .future import StartingProfile
from .future_puzzles import FuturePuzzleManifestRecord
from .language_task_pack import language_task_pack_summary, task_pair_for_review
from .session_journal import PersonalSolveSession


learning_review_api = Blueprint("learning_review_api", __name__)
REVIEW_VERSION = "language-recall-v1"
SCHEDULER_VERSION = "language-recall-scheduler-v2"
REVIEW_DELAY_HOURS = 24
REVIEW_INTERVAL_HOURS = (24, 168, 720)
MAX_DUE_ITEMS = 12
DEFAULT_DUE_LIMIT = 3
ALLOWED_DUE_LIMITS = frozenset({3, 6, 12})
ALLOWED_DUE_LIMIT_STRINGS = frozenset(str(value) for value in ALLOWED_DUE_LIMITS)
_TASK_PREFIX = "private-answer-form:"
_TASK_PACK_FIELDS = (
    "packId",
    "packVersion",
    "packDigest",
    "pairId",
    "sourceLanguage",
    "targetLanguage",
    "sourceText",
    "direction",
    "source",
    "grammar",
    "reviewStatus",
    "semanticStatus",
    "masteryClaim",
)
_LANGUAGE_CODES = {"en", "fr", "de", "es", "it", "pt", "ja", "nl"}
_RESPONSES = {"remembered", "not-yet", "pass"}
_MODES = {"independent", "assisted"}
FORGETTING_MODEL_VERSION = "language-recall-forgetting-grid-v1"
FORGETTING_MODEL_METHOD = "bounded-exponential-grid-v1"
FORGETTING_MODEL_MIN_SAMPLES = 8
FORGETTING_MODEL_MAX_DELAY_HOURS = 24 * 365
FORGETTING_MODEL_GRID_PER_DAY = tuple(
    round(0.01 + index * 0.01, 2) for index in range(200)
)


def _adaptive_interval_hours(stage, independent_streak):
    """Return a bounded interval derived from the baseline stage and streak."""
    base = REVIEW_INTERVAL_HOURS[min(stage, len(REVIEW_INTERVAL_HOURS) - 1)]
    if stage < 2 or independent_streak <= 1:
        return base
    multiplier = min(1.5, 1 + 0.25 * (independent_streak - 1))
    return int(round(base * multiplier))


def _fit_forgetting_model(observations):
    """Fit a bounded exponential recall curve without changing scheduling.

    ``observations`` contains small dictionaries with ``delayHours`` and an
    outcome of ``remembered`` or ``not-yet``.  This deliberately remains a
    diagnostic rather than a scheduler input: it is an interpretable local
    reference that only becomes available after enough independent, mixed
    recall outcomes exist.  A fixed pure-Python grid keeps the result
    reproducible on hosts without numerical dependencies.
    """
    clean = []
    for observation in observations if isinstance(observations, (list, tuple)) else ():
        if not isinstance(observation, dict):
            continue
        delay = observation.get("delayHours")
        outcome = observation.get("outcome")
        if (
            isinstance(delay, bool)
            or not isinstance(delay, (int, float))
            or not isfinite(delay)
            or outcome not in {"remembered", "not-yet"}
        ):
            continue
        clean.append(
            (
                min(FORGETTING_MODEL_MAX_DELAY_HOURS, max(0.0, float(delay))),
                outcome == "remembered",
            )
        )
    remembered = sum(1 for _, success in clean if success)
    not_yet = len(clean) - remembered
    base = {
        "version": FORGETTING_MODEL_VERSION,
        "method": FORGETTING_MODEL_METHOD,
        "status": "insufficient-data",
        "sampleCount": len(clean),
        "rememberedCount": remembered,
        "notYetCount": not_yet,
        "minimumSamples": FORGETTING_MODEL_MIN_SAMPLES,
        "requiresMixedOutcomes": True,
        "schedulerCoupled": False,
    }
    if len(clean) < FORGETTING_MODEL_MIN_SAMPLES or remembered == 0 or not_yet == 0:
        return base

    # p(recall | delay) = exp(-decay_per_day * delay_days).  The epsilon
    # avoids taking log(0) at zero delay while preserving the deterministic
    # ordering of candidates.
    epsilon = 1e-9
    best_rate = None
    best_loss = None
    for rate in FORGETTING_MODEL_GRID_PER_DAY:
        loss = 0.0
        for delay_hours, success in clean:
            probability = max(
                epsilon,
                min(
                    1.0 - epsilon,
                    exp(-rate * delay_hours / 24.0),
                ),
            )
            loss -= log(probability if success else 1.0 - probability)
        if best_loss is None or loss < best_loss - 1e-12:
            best_rate = rate
            best_loss = loss
    return {
        **base,
        "status": "fitted",
        "decayPerDay": best_rate,
        "halfLifeDays": round(log(2.0) / best_rate, 6),
        "negativeLogLikelihood": round(best_loss, 6),
        "gridMinPerDay": FORGETTING_MODEL_GRID_PER_DAY[0],
        "gridMaxPerDay": FORGETTING_MODEL_GRID_PER_DAY[-1],
    }


class FutureLearningReviewRecord(db.Model):
    __tablename__ = "future_learning_review_records"
    __table_args__ = (
        db.Index("ix_future_learning_review_profile_task", "profile_id", "task_id"),
    )

    id = db.Column(db.String(36), primary_key=True)
    profile_id = db.Column(db.String(36), nullable=False, index=True)
    task_id = db.Column(db.String(240), nullable=False)
    language = db.Column(db.String(16), nullable=False)
    source_evidence_id = db.Column(db.String(240), nullable=False)
    response = db.Column(db.String(16), nullable=False)
    input_mode = db.Column(db.String(16), nullable=False)
    recorded_at = db.Column(db.String(40), nullable=False)


def _now():
    return datetime.now(timezone.utc)


def _iso(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _stamp(value=None):
    return (value or _now()).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _valid_uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (AttributeError, ValueError):
        return False


def _same_origin():
    origin = request.headers.get("Origin")
    return not origin or origin == request.host_url.rstrip("/")


def _error(message, status):
    response = jsonify(error=message)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _analysis_session_id(evidence):
    analysis = evidence.get("analysis") if isinstance(evidence, dict) else None
    session_id = analysis.get("sessionId") if isinstance(analysis, dict) else None
    if _valid_uuid(session_id):
        return session_id
    evidence_id = evidence.get("evidenceId") if isinstance(evidence, dict) else None
    if isinstance(evidence_id, str) and evidence_id.startswith("session-analysis:"):
        candidate = evidence_id.split(":", 2)[1]
        return candidate if _valid_uuid(candidate) else None
    return None


def _source_entry(session_id, entry_id):
    if not session_id or not entry_id:
        return {}
    session = db.session.get(PersonalSolveSession, session_id)
    if session is None:
        return {}
    manifest = db.session.get(FuturePuzzleManifestRecord, session.puzzle_hash)
    body = manifest.manifest_json if manifest is not None else {}
    entries = body.get("entries", []) if isinstance(body, dict) else []
    return next(
        (
            {
                "clue": entry.get("clue"),
                "length": len(entry.get("answer", "")),
                "number": entry.get("number"),
                "direction": entry.get("direction"),
            }
            for entry in entries
            if isinstance(entry, dict) and entry.get("id") == entry_id
        ),
        {},
    )


def _review_task_id(profile_id, evidence_id, source_task_id):
    """Return an opaque handle so the due queue cannot leak the answer."""
    digest = sha256(
        f"{profile_id}|{evidence_id}|{source_task_id}".encode()
    ).hexdigest()[:32]
    return f"language-review:{digest}"


def _public_item(item):
    return {key: value for key, value in item.items() if key != "sourceTaskId"}


def _exposures(profile_id):
    record = db.session.get(EpistemeProfileRecord, profile_id)
    profile = record.profile_json if record is not None else {}
    evidence = profile.get("evidence", []) if isinstance(profile, dict) else []
    latest = {}
    for item in evidence if isinstance(evidence, list) else []:
        if not isinstance(item, dict) or item.get("type") != "session-analysis":
            continue
        recorded_at = item.get("recordedAt")
        recorded_dt = _iso(recorded_at)
        if recorded_dt is None:
            continue
        source_session_id = _analysis_session_id(item)
        links = item.get("taskLinks", [])
        for link in links if isinstance(links, list) else []:
            if not isinstance(link, dict):
                continue
            entry_id = link.get("entryId")
            source = _source_entry(source_session_id, entry_id)
            for task in (
                link.get("tasks", []) if isinstance(link.get("tasks"), list) else []
            ):
                if not isinstance(task, dict):
                    continue
                language = task.get("language")
                task_id = task.get("taskId")
                if (
                    not isinstance(language, str)
                    or language == "en"
                    or language not in _LANGUAGE_CODES
                    or task.get("clueFamily") != "language-recurrence"
                    or task.get("contentReview") != "unreviewed"
                    or not isinstance(task_id, str)
                    or not task_id.startswith(_TASK_PREFIX)
                ):
                    continue
                answer = task_id[len(_TASK_PREFIX) :]
                if not answer:
                    continue
                source_evidence_id = item.get("evidenceId")
                if not isinstance(source_evidence_id, str) or not source_evidence_id:
                    continue
                key = f"{language}:{task_id}"
                due_at = recorded_dt + timedelta(hours=REVIEW_DELAY_HOURS)
                candidate = {
                    "taskId": _review_task_id(profile_id, source_evidence_id, task_id),
                    "sourceTaskId": task_id,
                    "language": language,
                    "sourceEvidenceId": source_evidence_id,
                    "sourceSessionId": source_session_id,
                    "entryId": entry_id,
                    "clue": source.get("clue")
                    or "Recall the language-thread answer from that crossword.",
                    "length": source.get("length") or len(answer),
                    "number": source.get("number"),
                    "direction": source.get("direction"),
                    "dueAt": _stamp(due_at),
                    "exposedAt": _stamp(recorded_dt),
                }
                stored_task_pack = task.get("taskPack") if isinstance(task, dict) else None
                task_pack = (
                    {
                        key: stored_task_pack[key]
                        for key in _TASK_PACK_FIELDS
                        if key in stored_task_pack
                    }
                    if isinstance(stored_task_pack, dict)
                    and isinstance(stored_task_pack.get("pairId"), str)
                    and isinstance(stored_task_pack.get("packDigest"), str)
                    and isinstance(stored_task_pack.get("sourceText"), str)
                    and "targetText" not in stored_task_pack
                    else task_pair_for_review(language, answer)
                )
                if task_pack is not None:
                    # This metadata is only for the local delayed-review UI.
                    # The target form remains behind the opaque task handle.
                    candidate["taskPack"] = task_pack
                previous = latest.get(key)
                if previous is None or recorded_dt > _iso(previous["exposedAt"]):
                    latest[key] = candidate
    return latest


def _forgetting_model_observations(profile_id):
    """Return independent recall intervals for the profile's current tasks."""
    exposures = _exposures(profile_id)
    if not exposures:
        return []
    exposure_by_task = {item["taskId"]: item for item in exposures.values()}
    records = (
        FutureLearningReviewRecord.query.filter_by(profile_id=profile_id)
        .order_by(
            FutureLearningReviewRecord.recorded_at,
            FutureLearningReviewRecord.id,
        )
        .all()
    )
    previous_at = {}
    observations = []
    for record in records:
        if record.input_mode != "independent" or record.response not in {
            "remembered",
            "not-yet",
        }:
            continue
        exposure = exposure_by_task.get(record.task_id)
        recorded_at = _iso(record.recorded_at)
        if exposure is None or recorded_at is None:
            continue
        anchor = previous_at.get(record.task_id) or _iso(exposure["exposedAt"])
        if anchor is None:
            continue
        delay_hours = max(0.0, (recorded_at - anchor).total_seconds() / 3600.0)
        observations.append({"delayHours": delay_hours, "outcome": record.response})
        # Assisted responses and passes are intentionally ignored as labeled
        # observations and do not reset the independent recall clock.
        previous_at[record.task_id] = recorded_at
    return observations


def _forgetting_model_diagnostic(profile_id):
    return _fit_forgetting_model(_forgetting_model_observations(profile_id))


def _due(profile_id, *, now=None):
    now = now or _now()
    exposures = _exposures(profile_id)
    responses = (
        FutureLearningReviewRecord.query.filter_by(profile_id=profile_id)
        .order_by(FutureLearningReviewRecord.recorded_at.desc())
        .all()
    )
    response_history = {}
    for response in responses:
        response_history.setdefault(response.task_id, []).append(response)
    due = []
    for item in exposures.values():
        due_at = _iso(item["dueAt"])
        history = response_history.get(item["taskId"], [])
        if history:
            history.sort(
                key=lambda record: (record.recorded_at, record.id), reverse=True
            )
            latest = history[0]
            if latest.response == "pass":
                continue
            independent_successes = 0
            for record in history:
                if (
                    record.response != "remembered"
                    or record.input_mode != "independent"
                ):
                    break
                independent_successes += 1
            if latest.response == "remembered" and latest.input_mode == "independent":
                stage = min(independent_successes, len(REVIEW_INTERVAL_HOURS) - 1)
            else:
                stage = 0
            latest_at = _iso(latest.recorded_at)
            if latest_at is None:
                continue
            interval_hours = (
                _adaptive_interval_hours(stage, independent_successes)
                if latest.response == "remembered"
                and latest.input_mode == "independent"
                else REVIEW_DELAY_HOURS
            )
            due_at = latest_at + timedelta(hours=interval_hours)
            item = {
                **item,
                "dueAt": _stamp(due_at),
                "reviewStage": stage + 1,
                "lastResponse": latest.response,
                "lastMode": latest.input_mode,
                "intervalHours": interval_hours,
                "schedulerVersion": SCHEDULER_VERSION,
            }
        else:
            if due_at is None:
                continue
            item = {
                **item,
                "reviewStage": 0,
                "intervalHours": REVIEW_DELAY_HOURS,
                "schedulerVersion": SCHEDULER_VERSION,
            }
        if due_at is None or due_at > now:
            continue
        interval = item.get("intervalHours")
        interval = interval if type(interval) is int and interval > 0 else REVIEW_DELAY_HOURS
        overdue_hours = max(0.0, (now - due_at).total_seconds() / 3600.0)
        # This is an ordering signal for a calm optional queue, not a recall
        # probability or a mastery estimate.  A very late thread gets at most
        # one extra interval of priority so one neglected card cannot crowd
        # every other language thread out of the next puzzle.
        item["overdueHours"] = round(overdue_hours, 3)
        item["schedulerPriority"] = round(
            min(2.0, 1.0 + overdue_hours / interval),
            3,
        )
        due.append(item)
    due.sort(
        key=lambda item: (
            -item.get("schedulerPriority", 1.0),
            item["dueAt"],
            item["taskId"],
        )
    )
    return due[:MAX_DUE_ITEMS]


@learning_review_api.get("/api/future/profile/<profile_id>/learning-review")
def list_learning_reviews(profile_id):
    if not _valid_uuid(profile_id):
        return _error("Invalid profile id", 400)
    if db.session.get(StartingProfile, profile_id) is None:
        return _error("Profile not found", 404)
    requested_limits = request.args.getlist("limit")
    if not requested_limits:
        limit = DEFAULT_DUE_LIMIT
    elif (
        len(requested_limits) != 1
        or requested_limits[0] not in ALLOWED_DUE_LIMIT_STRINGS
    ):
        return _error("Learning review limit must be 3, 6 or 12", 400)
    else:
        limit = int(requested_limits[0])
    due = _due(profile_id)
    response = jsonify(
        {
            "profileId": profile_id,
            "version": REVIEW_VERSION,
            "policy": {
                "delayHours": REVIEW_DELAY_HOURS,
                "intervalHours": list(REVIEW_INTERVAL_HOURS),
                "maxItems": MAX_DUE_ITEMS,
                "schedulerVersion": SCHEDULER_VERSION,
                "forgettingModel": _forgetting_model_diagnostic(profile_id),
                "taskPack": language_task_pack_summary(),
            },
            "due": [_public_item(item) for item in due[:limit]],
            "remaining": max(0, len(due) - limit),
        }
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@learning_review_api.get("/api/future/profile/<profile_id>/learning-review/answer")
def reveal_learning_review_answer(profile_id):
    if not _valid_uuid(profile_id):
        return _error("Invalid profile id", 400)
    if db.session.get(StartingProfile, profile_id) is None:
        return _error("Profile not found", 404)
    task_id = request.args.get("taskId")
    item = next((item for item in _due(profile_id) if item["taskId"] == task_id), None)
    if item is None:
        return _error("Learning review is not due or no longer available", 409)
    source_task_id = item.get("sourceTaskId", "")
    answer = (
        source_task_id[len(_TASK_PREFIX) :]
        if isinstance(source_task_id, str) and source_task_id.startswith(_TASK_PREFIX)
        else ""
    )
    payload = {"taskId": task_id, "answer": answer, "language": item["language"]}
    if item.get("taskPack") is not None:
        payload["taskPack"] = item["taskPack"]
    response = jsonify(payload)
    response.headers["Cache-Control"] = "no-store"
    return response


@learning_review_api.post("/api/future/profile/<profile_id>/learning-review")
def respond_learning_review(profile_id):
    if not _same_origin():
        return _error("Cross-origin learning review is not allowed", 403)
    if not _valid_uuid(profile_id):
        return _error("Invalid profile id", 400)
    if db.session.get(StartingProfile, profile_id) is None:
        return _error("Profile not found", 404)
    body = request.get_json(silent=True)
    if (
        not isinstance(body, dict)
        or set(body) != {"taskId", "response", "mode"}
        or not isinstance(body.get("taskId"), str)
        or len(body["taskId"]) > 240
        or body.get("response") not in _RESPONSES
        or body.get("mode") not in _MODES
    ):
        return _error("Invalid learning review response", 422)
    due = {item["taskId"]: item for item in _due(profile_id)}
    item = due.get(body["taskId"])
    if item is None:
        return _error("Learning review is not due or no longer available", 409)
    record = FutureLearningReviewRecord(
        id=str(uuid4()),
        profile_id=profile_id,
        task_id=item["taskId"],
        language=item["language"],
        source_evidence_id=item["sourceEvidenceId"],
        response=body["response"],
        input_mode=body["mode"],
        recorded_at=_stamp(),
    )
    db.session.add(record)
    db.session.commit()
    response = jsonify(
        {
            "recorded": True,
            "reviewId": record.id,
            "taskId": record.task_id,
            "response": record.response,
            "mode": record.input_mode,
            "sourceEvidenceId": record.source_evidence_id,
        }
    )
    response.headers["Cache-Control"] = "no-store"
    return response, 201


def exported_learning_reviews(profile_id):
    return [
        {
            "reviewId": record.id,
            "taskId": record.task_id,
            "language": record.language,
            "sourceEvidenceId": record.source_evidence_id,
            "response": record.response,
            "mode": record.input_mode,
            "recordedAt": record.recorded_at,
        }
        for record in FutureLearningReviewRecord.query.filter_by(profile_id=profile_id)
        .order_by(FutureLearningReviewRecord.recorded_at, FutureLearningReviewRecord.id)
        .all()
    ]
