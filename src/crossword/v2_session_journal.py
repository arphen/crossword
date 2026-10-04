"""V2 session boundary for published puzzles and profile-owned review play.

Public puzzle reads require the published registry. A session may also resolve
an exact ``quality.verdict=review`` candidate owned by its canonical profile;
that path stays in the private solve journal and does not publish or promote
the candidate.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
import unicodedata
from flask import Blueprint, jsonify, request
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from .database import db
from .future import StartingProfile
from .future_puzzles import (
    FuturePuzzleV2CandidateRecord,
    PersonalizedV2CandidateRejected,
    validate_personalized_v2_review_candidate,
)
from .session_journal import (
    MAX_EVENTS,
    MAX_SESSION_EVENTS,
    _bounded_json_body,
    _canonical_uuid,
    _digest,
    _error,
    _is_iso_datetime,
    _origin_is_local,
    _token,
    _validate_event,
    _validate_initial_grid,
)
from .solve_replay import (
    SolveReplayRejected,
    SolveReplayUnavailable,
    analyze_solve_session_v2,
    validate_solve_puzzle_v2,
)

v2_session_journal_api = Blueprint("v2_session_journal_api", __name__)

_RAW_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_V2_DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")
_RECEIPT_VERSION = "puzzle-v2-publication-receipt-v1"
_REVIEWER_ID = re.compile(r"^[^\s\x00-\x1f\x7f][^\x00-\x1f\x7f]{0,159}$")


class FuturePuzzleV2PublishedRecord(db.Model):
    """Immutable host publication registry row, keyed by the raw SHA-256.

    This table intentionally has no insert route or production insertion
    helper. A future publication transaction must establish the host trust
    boundary before adding rows.
    """

    __tablename__ = "future_puzzle_v2_published"

    candidate_hash = db.Column(db.String(64), primary_key=True)
    puzzle_id = db.Column(db.String(160), nullable=False, unique=True)
    puzzle_json = db.Column(db.JSON, nullable=False)
    publication_receipt = db.Column(db.JSON, nullable=False)
    published_at = db.Column(db.String(40), nullable=False)


class FuturePuzzleV2SolveSession(db.Model):
    __tablename__ = "future_puzzle_v2_solve_sessions"

    id = db.Column(db.String(36), primary_key=True)
    profile_id = db.Column(db.String(36), nullable=False, index=True)
    puzzle_hash = db.Column(db.String(71), nullable=False)
    puzzle_id = db.Column(db.String(160), nullable=False)
    initial_grid = db.Column(db.JSON, nullable=False)
    writer_digest = db.Column(db.String(64), nullable=False)
    accepted_seq = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(16), nullable=False, default="active")
    created_at = db.Column(db.String(40), nullable=False)
    updated_at = db.Column(db.String(40), nullable=False)


class FuturePuzzleV2SolveEvent(db.Model):
    __tablename__ = "future_puzzle_v2_solve_events"
    __table_args__ = (
        db.UniqueConstraint(
            "session_id", "seq", name="uq_future_puzzle_v2_solve_event_seq"
        ),
        db.UniqueConstraint("event_id", name="uq_future_puzzle_v2_solve_event_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    seq = db.Column(db.Integer, nullable=False)
    event_id = db.Column(db.String(36), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    payload_hash = db.Column(db.String(64), nullable=False)
    recorded_at = db.Column(db.String(40), nullable=False)


class FuturePuzzleV2SolveAnalysis(db.Model):
    __tablename__ = "future_puzzle_v2_solve_analyses"

    session_id = db.Column(db.String(36), primary_key=True)
    puzzle_hash = db.Column(db.String(71), nullable=False, index=True)
    analysis_version = db.Column(db.String(80), nullable=False)
    analysis_json = db.Column(db.JSON, nullable=False)
    finalized = db.Column(db.Boolean, nullable=False, default=False)
    updated_at = db.Column(db.String(40), nullable=False)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _v2_envelope_error(message, status):
    response = jsonify(error=message)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _validate_publication_receipt(receipt, candidate_digest):
    """Validate exact receipt shape; trust comes only from registry membership."""
    if not isinstance(receipt, dict) or set(receipt) != {
        "version",
        "candidateDigest",
        "publishedAt",
        "reviewerId",
    }:
        raise ValueError("Published puzzle receipt is missing or malformed")
    if (
        receipt["version"] != _RECEIPT_VERSION
        or receipt["candidateDigest"] != candidate_digest
    ):
        raise ValueError("Published puzzle receipt does not match its document")
    if not _is_iso_datetime(receipt["publishedAt"]):
        raise ValueError("Published puzzle receipt timestamp is invalid")
    reviewer = receipt["reviewerId"]
    if not isinstance(reviewer, str) or not _REVIEWER_ID.fullmatch(reviewer):
        raise ValueError("Published puzzle receipt reviewer is invalid")
    return receipt


def _validated_published_record(candidate_hash):
    record = db.session.get(FuturePuzzleV2PublishedRecord, candidate_hash)
    if record is None:
        return None, _v2_envelope_error("Published V2 puzzle not found", 404)
    candidate_digest = f"sha256:{candidate_hash}"
    try:
        puzzle = validate_solve_puzzle_v2(record.puzzle_json)
        receipt = _validate_publication_receipt(
            record.publication_receipt, candidate_digest
        )
        if (
            puzzle["integrity"]["value"] != candidate_digest
            or puzzle["id"] != record.puzzle_id
            or puzzle["quality"]["verdict"] != "accept"
            or record.candidate_hash != candidate_hash
            or not _is_iso_datetime(record.published_at)
            or receipt["publishedAt"] != record.published_at
        ):
            raise ValueError("Published V2 registry row does not match its document")
    except (
        SolveReplayRejected,
        SolveReplayUnavailable,
        TypeError,
        ValueError,
        KeyError,
        RecursionError,
    ):
        return None, _v2_envelope_error(
            "Published V2 puzzle failed host integrity validation", 503
        )
    return (record, puzzle, receipt), None


def _validated_profile_candidate(profile_id, candidate_hash):
    """Resolve one exact owner-scoped review candidate for private play."""
    if not _canonical_uuid(profile_id):
        return None, _session_error("Invalid profile id", 400)
    record = db.session.get(FuturePuzzleV2CandidateRecord, (profile_id, candidate_hash))
    if record is None:
        return None, _session_error("Published V2 puzzle not found", 404)
    try:
        puzzle = validate_personalized_v2_review_candidate(record.manifest_json)
        puzzle = validate_solve_puzzle_v2(puzzle)
        if (
            record.profile_id != profile_id
            or record.candidate_hash != candidate_hash
            or puzzle["integrity"]["value"] != f"sha256:{candidate_hash}"
            or puzzle["id"] != record.candidate_id
            or puzzle["quality"]["verdict"] != "review"
        ):
            raise ValueError(
                "Profile-owned V2 candidate does not match its stored identity"
            )
    except (
        PersonalizedV2CandidateRejected,
        SolveReplayRejected,
        SolveReplayUnavailable,
        TypeError,
        ValueError,
        KeyError,
        RecursionError,
    ):
        return None, _session_error(
            "V2 review candidate failed host integrity validation", 503
        )
    return (record, puzzle), None


def _validated_session_puzzle(record):
    """Re-resolve a session's published or exact profile-owned puzzle row."""
    match = _V2_DIGEST.fullmatch(record.puzzle_hash or "")
    if match is None or not _canonical_uuid(record.profile_id):
        raise ValueError("Invalid stored V2 session identity")
    resolved, error = _validated_published_record(match.group(1))
    if error is not None:
        if error.status_code != 404:
            raise ValueError("Published V2 puzzle is missing or invalid")
        resolved, error = _validated_profile_candidate(
            record.profile_id, match.group(1)
        )
        if error is not None:
            raise ValueError("Profile-owned V2 candidate is missing or invalid")
        _candidate, puzzle = resolved
    else:
        _published, puzzle, _receipt = resolved
    if (
        puzzle["integrity"]["value"] != record.puzzle_hash
        or puzzle["id"] != record.puzzle_id
    ):
        raise ValueError("V2 session puzzle binding is invalid")
    return puzzle


def _indexes(puzzle):
    cells = puzzle.get("cells")
    entries = puzzle.get("entries")
    if not isinstance(cells, list) or not isinstance(entries, list):
        raise ValueError("PuzzleDocumentV2 is incomplete")
    open_cell_ids = []
    for cell in cells:
        if (
            not isinstance(cell, dict)
            or not isinstance(cell.get("id"), str)
            or type(cell.get("block")) is not bool
        ):
            raise ValueError("PuzzleDocumentV2 contains an invalid cell")
        if not cell["block"]:
            open_cell_ids.append(cell["id"])
    entry_cells = {}
    answers_by_cell = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError("PuzzleDocumentV2 contains an invalid entry")
        cell_ids, answer = entry.get("cellIds"), entry.get("answer")
        if not isinstance(cell_ids, list) or not isinstance(answer, str):
            raise ValueError("PuzzleDocumentV2 entry is incomplete")
        tokens = list(unicodedata.normalize("NFC", answer))
        if len(tokens) != len(cell_ids) or entry["id"] in entry_cells:
            raise ValueError("PuzzleDocumentV2 entry has invalid answer coverage")
        entry_cells[entry["id"]] = cell_ids
        for cell_id, token in zip(cell_ids, tokens, strict=True):
            previous = answers_by_cell.setdefault(cell_id, token)
            if previous != token:
                raise ValueError("PuzzleDocumentV2 crossing answers disagree")
    if set(answers_by_cell) != set(open_cell_ids):
        raise ValueError("PuzzleDocumentV2 entries do not cover its open cells")
    return open_cell_ids, entry_cells, answers_by_cell


def _validate_event_v2(
    value, session_id, profile_id, puzzle_hash, cell_ids, entry_cells, answers_by_cell
):
    if not isinstance(value, dict) or value.get("puzzleHash") != puzzle_hash:
        raise ValueError("Event puzzle digest does not match the V2 journal")
    match = _V2_DIGEST.fullmatch(puzzle_hash or "")
    if not match:
        raise ValueError("Invalid V2 puzzle digest")
    # Reuse the established event schema and cell/answer checks after replacing
    # only the hash in a validation copy. Persist and analyze the original
    # sha256:-prefixed event untouched; this never routes through V1 storage.
    validation_copy = {**value, "puzzleHash": match.group(1)}
    return _validate_event(
        validation_copy,
        session_id,
        profile_id,
        match.group(1),
        cell_ids,
        entry_cells,
        answers_by_cell,
    )


def _validate_v2_initial_grid(value, open_cell_ids):
    cell_ids = _validate_initial_grid(value)
    if [cell["cellId"] for cell in value] != open_cell_ids:
        raise ValueError("Initial grid does not exactly match the published V2 puzzle")
    return cell_ids


def _writer_matches(record, writer_token):
    if not isinstance(writer_token, str) or not 32 <= len(writer_token) <= 128:
        return False
    candidate = hashlib.sha256(writer_token.encode("utf-8")).hexdigest()
    return hmac.compare_digest(record.writer_digest, candidate)


def _session_error(message, status, *, retryable=False):
    return _error(message, status, retryable=retryable)


def _recompute_final_v2_analysis(record, cached):
    """Revalidate every durable binding before exposing finalized analysis."""
    match = _V2_DIGEST.fullmatch(record.puzzle_hash or "")
    if (
        match is None
        or not _canonical_uuid(record.profile_id)
        or type(record.accepted_seq) is not int
        or not 1 <= record.accepted_seq <= MAX_SESSION_EVENTS
    ):
        raise ValueError("Invalid stored V2 session identity or sequence")
    puzzle = _validated_session_puzzle(record)

    open_cell_ids, entry_cells, answers_by_cell = _indexes(puzzle)
    cell_ids = _validate_v2_initial_grid(record.initial_grid, open_cell_ids)
    rows = (
        db.session.query(FuturePuzzleV2SolveEvent)
        .filter_by(session_id=record.id)
        .order_by(FuturePuzzleV2SolveEvent.seq)
        .all()
    )
    if len(rows) != record.accepted_seq:
        raise ValueError("V2 session event history is incomplete")
    events = []
    seen_ids = set()
    for expected_seq, row in enumerate(rows, start=1):
        event = row.payload
        if (
            row.seq != expected_seq
            or not isinstance(event, dict)
            or row.event_id != event.get("eventId")
            or row.seq != event.get("seq")
            or row.recorded_at != event.get("recordedAt")
            or row.payload_hash != _digest(event)
            or event.get("eventId") in seen_ids
        ):
            raise ValueError("V2 session event history failed integrity validation")
        _validate_event_v2(
            event,
            record.id,
            record.profile_id,
            record.puzzle_hash,
            cell_ids,
            entry_cells,
            answers_by_cell,
        )
        seen_ids.add(event["eventId"])
        events.append(event)
    if not events or events[-1].get("type") != "session-finished":
        raise ValueError("V2 session is missing its terminal event")

    replayed = analyze_solve_session_v2(
        {
            "schemaVersion": 2,
            "sessionId": record.id,
            "profileId": record.profile_id,
            "puzzleHash": record.puzzle_hash,
            "initialGrid": record.initial_grid,
            "events": events,
        },
        puzzle,
    )
    if (
        cached is None
        or cached.finalized is not True
        or cached.puzzle_hash != record.puzzle_hash
        or cached.analysis_version != replayed.get("analysisVersion")
        or not isinstance(cached.analysis_json, dict)
        or _canonical(cached.analysis_json) != _canonical(replayed)
    ):
        raise ValueError("Cached V2 analysis does not match replayed session history")
    return replayed


@v2_session_journal_api.get("/api/future/puzzles/v2/<candidate_hash>")
def get_published_v2_puzzle(candidate_hash):
    if not _RAW_DIGEST.fullmatch(candidate_hash or ""):
        return _v2_envelope_error("Invalid V2 puzzle digest", 400)
    result, error = _validated_published_record(candidate_hash)
    if error:
        return error
    record, puzzle, receipt = result
    response = jsonify(
        status="published",
        candidateDigest=f"sha256:{candidate_hash}",
        puzzle=puzzle,
        publicationReceipt=receipt,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@v2_session_journal_api.post("/api/future/sessions/v2")
def create_v2_solve_session():
    if not _origin_is_local():
        return _session_error("Cross-origin session writes are not allowed", 403)
    value, size_error = _bounded_json_body("Session request is too large")
    if size_error:
        return size_error
    if not isinstance(value, dict) or set(value) != {
        "sessionId",
        "profileId",
        "puzzleHash",
        "puzzleId",
        "initialGrid",
        "writerToken",
    }:
        return _session_error("Invalid V2 session request", 422)
    session_id, profile_id, puzzle_hash, puzzle_id, writer_token = (
        value.get(key)
        for key in ("sessionId", "profileId", "puzzleHash", "puzzleId", "writerToken")
    )
    match = _V2_DIGEST.fullmatch(puzzle_hash or "")
    if (
        not _canonical_uuid(session_id)
        or not _canonical_uuid(profile_id)
        or match is None
        or not isinstance(puzzle_id, str)
        or not 1 <= len(puzzle_id) <= 160
    ):
        return _session_error("Invalid V2 session identity", 422)
    if not isinstance(writer_token, str) or not 32 <= len(writer_token) <= 128:
        return _session_error("Invalid writer capability", 422)
    result, error = _validated_published_record(match.group(1))
    if error is not None and error.status_code == 404:
        result, error = _validated_profile_candidate(profile_id, match.group(1))
        if error is not None:
            return error
        _candidate, puzzle = result
    elif error is not None:
        return error
    else:
        _published, puzzle, _receipt = result
    if puzzle_hash != puzzle["integrity"]["value"] or puzzle_id != puzzle["id"]:
        return _session_error(
            "V2 puzzle identity does not match the resolved document", 422
        )
    try:
        open_cell_ids, _entry_cells, _answers_by_cell = _indexes(puzzle)
        cell_ids = _validate_v2_initial_grid(value.get("initialGrid"), open_cell_ids)
    except (ValueError, TypeError, KeyError) as error:
        return _session_error(str(error), 422)
    if db.session.get(StartingProfile, profile_id) is None:
        return _session_error("Starting profile not found", 404)
    writer_digest = hashlib.sha256(writer_token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    record = db.session.get(FuturePuzzleV2SolveSession, session_id)
    created = record is None
    if record is not None:
        same = (
            record.profile_id == profile_id
            and record.puzzle_hash == puzzle_hash
            and record.puzzle_id == puzzle_id
            and record.initial_grid == value["initialGrid"]
            and hmac.compare_digest(record.writer_digest, writer_digest)
        )
        if not same:
            return _session_error(
                "Session id already belongs to another V2 journal", 409
            )
    else:
        record = FuturePuzzleV2SolveSession(
            id=session_id,
            profile_id=profile_id,
            puzzle_hash=puzzle_hash,
            puzzle_id=puzzle_id,
            initial_grid=value["initialGrid"],
            writer_digest=writer_digest,
            accepted_seq=0,
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.session.add(record)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return _session_error(
                "Session id already belongs to another V2 journal", 409
            )
    response = jsonify(
        sessionId=session_id,
        acceptedSeq=record.accepted_seq,
        status=record.status,
        cellCount=len(cell_ids),
        puzzleHash=record.puzzle_hash,
        puzzleId=record.puzzle_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return response, 201 if created else 200


@v2_session_journal_api.post("/api/future/sessions/v2/<session_id>/events")
def append_v2_solve_events(session_id):
    if not _origin_is_local():
        return _session_error("Cross-origin session writes are not allowed", 403)
    value, size_error = _bounded_json_body("Event batch is too large")
    if size_error:
        return size_error
    if not _canonical_uuid(session_id):
        return _session_error("Invalid session id", 400)
    if not isinstance(value, dict) or set(value) != {
        "expectedSeq",
        "writerToken",
        "events",
    }:
        return _session_error("Invalid V2 event batch", 422)
    events = value.get("events")
    if not isinstance(events, list) or not 1 <= len(events) <= MAX_EVENTS:
        return _session_error("Event batch must contain 1 to 200 events", 422)
    if type(value.get("expectedSeq")) is not int or value["expectedSeq"] < 0:
        return _session_error("Invalid expected sequence", 422)
    writer_token = value.get("writerToken")
    if not isinstance(writer_token, str) or not 32 <= len(writer_token) <= 128:
        return _session_error("Invalid writer capability", 403)
    record = db.session.get(FuturePuzzleV2SolveSession, session_id)
    if record is None:
        return _session_error("V2 session not found", 404)
    if not _writer_matches(record, writer_token):
        return _session_error("Invalid writer capability", 403)
    try:
        puzzle = _validated_session_puzzle(record)
    except (
        SolveReplayRejected,
        SolveReplayUnavailable,
        PersonalizedV2CandidateRejected,
        TypeError,
        ValueError,
        KeyError,
        RecursionError,
    ):
        return _session_error("V2 session puzzle is unavailable or invalid", 503)
    try:
        open_cell_ids, entry_cells, answers_by_cell = _indexes(puzzle)
        cell_ids = _validate_v2_initial_grid(record.initial_grid, open_cell_ids)
        for event in events:
            _validate_event_v2(
                event,
                session_id,
                record.profile_id,
                record.puzzle_hash,
                cell_ids,
                entry_cells,
                answers_by_cell,
            )
        if len({event["eventId"] for event in events}) != len(events):
            raise ValueError("Duplicate event id in batch")
        seqs = [event["seq"] for event in events]
        if seqs != list(range(seqs[0], seqs[0] + len(seqs))):
            raise ValueError("Event sequences must be contiguous")
    except (ValueError, TypeError, KeyError) as error:
        return _session_error(str(error), 422)

    existing_rows = (
        db.session.query(FuturePuzzleV2SolveEvent)
        .filter_by(session_id=session_id)
        .filter(FuturePuzzleV2SolveEvent.seq.in_(seqs))
        .all()
    )
    by_seq = {row.seq: row for row in existing_rows}
    new_events = []
    duplicate_ids = []
    for event in events:
        payload_hash = _digest(event)
        existing = by_seq.get(event["seq"])
        if existing is not None:
            if (
                existing.event_id != event["eventId"]
                or existing.payload_hash != payload_hash
            ):
                return _session_error("Sequence conflicts with accepted event", 409)
            duplicate_ids.append(event["eventId"])
            continue
        other = (
            db.session.query(FuturePuzzleV2SolveEvent)
            .filter_by(event_id=event["eventId"])
            .first()
        )
        if other is not None:
            return _session_error("Event id was already used", 409)
        new_events.append((event, payload_hash))

    if new_events:
        expected_seq = value["expectedSeq"]
        if expected_seq > record.accepted_seq or seqs[0] != expected_seq + 1:
            return _session_error(
                "Accepted sequence changed; reload before retrying", 409
            )
        if any(
            seq not in by_seq
            for seq in range(expected_seq + 1, record.accepted_seq + 1)
        ):
            return _session_error(
                "Retry does not include the full accepted prefix", 409
            )
        if record.status != "active":
            return _session_error("V2 session is already finished", 409)
        fresh = [event for event, _ in new_events]
        if fresh[-1]["seq"] > MAX_SESSION_EVENTS:
            return _session_error("V2 session has reached its event limit", 413)
        if record.accepted_seq == 0 and (
            fresh[0]["seq"] != 1 or fresh[0]["type"] != "session-started"
        ):
            return _session_error("First event must start the V2 session", 422)
        if any(event["type"] == "session-started" for event in fresh[1:]):
            return _session_error("V2 session can only be started once", 422)
        if any(
            event["type"] == "session-resumed"
            and event["snapshotSeq"] > record.accepted_seq
            for event in fresh
        ):
            return _session_error(
                "Resume snapshot is ahead of accepted V2 history", 422
            )
        finish_positions = [
            position
            for position, event in enumerate(fresh)
            if event["type"] == "session-finished"
        ]
        if finish_positions and finish_positions != [len(fresh) - 1]:
            return _session_error(
                "Session-finished must be the final event in a batch", 422
            )
        if new_events[0][0]["seq"] != record.accepted_seq + 1 or any(
            event["seq"] <= record.accepted_seq for event, _ in new_events
        ):
            return _session_error(
                "New events must continue the accepted V2 sequence", 409
            )
        if any(
            event["seq"] > record.accepted_seq
            for event in events[: len(events) - len(new_events)]
        ):
            return _session_error("Event retry order is inconsistent", 409)

    accepted_ids = []
    if new_events:
        base_seq = record.accepted_seq
        finished = new_events[-1][0]["type"] == "session-finished"
        persisted = (
            db.session.query(FuturePuzzleV2SolveEvent)
            .filter_by(session_id=session_id)
            .order_by(FuturePuzzleV2SolveEvent.seq)
            .all()
        )
        candidate_session = {
            "schemaVersion": 2,
            "sessionId": session_id,
            "profileId": record.profile_id,
            "puzzleHash": record.puzzle_hash,
            "initialGrid": record.initial_grid,
            "events": [row.payload for row in persisted]
            + [event for event, _ in new_events],
        }
        try:
            analysis = analyze_solve_session_v2(candidate_session, puzzle)
        except SolveReplayRejected as error:
            db.session.rollback()
            return _session_error(f"V2 solve replay rejected: {error}", 422)
        except SolveReplayUnavailable as error:
            db.session.rollback()
            return _session_error(str(error), 503)
        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        try:
            cas = db.session.execute(
                update(FuturePuzzleV2SolveSession)
                .where(
                    FuturePuzzleV2SolveSession.id == session_id,
                    FuturePuzzleV2SolveSession.accepted_seq == base_seq,
                    FuturePuzzleV2SolveSession.status == "active",
                )
                .values(
                    accepted_seq=new_events[-1][0]["seq"],
                    status="finished" if finished else "active",
                    updated_at=now,
                )
            )
            if cas.rowcount != 1:
                db.session.rollback()
                return _session_error(
                    "Accepted V2 sequence changed; reload before retrying", 409
                )
            for event, payload_hash in new_events:
                db.session.add(
                    FuturePuzzleV2SolveEvent(
                        session_id=session_id,
                        seq=event["seq"],
                        event_id=event["eventId"],
                        payload=event,
                        payload_hash=payload_hash,
                        recorded_at=event["recordedAt"],
                    )
                )
                accepted_ids.append(event["eventId"])
            analysis_record = db.session.get(FuturePuzzleV2SolveAnalysis, session_id)
            if analysis_record is None:
                analysis_record = FuturePuzzleV2SolveAnalysis(
                    session_id=session_id,
                    puzzle_hash=record.puzzle_hash,
                    analysis_version=analysis["analysisVersion"],
                    analysis_json=analysis,
                    finalized=finished,
                    updated_at=now,
                )
                db.session.add(analysis_record)
            else:
                analysis_record.analysis_version = analysis["analysisVersion"]
                analysis_record.analysis_json = analysis
                analysis_record.finalized = analysis_record.finalized or finished
                analysis_record.updated_at = now
            db.session.commit()
            record.accepted_seq = new_events[-1][0]["seq"]
            if finished:
                record.status = "finished"
        except IntegrityError:
            db.session.rollback()
            return _session_error(
                "Accepted V2 sequence changed; reload before retrying", 409
            )

    response = jsonify(
        sessionId=session_id,
        acceptedSeq=record.accepted_seq,
        acceptedEventIds=accepted_ids,
        duplicateEventIds=duplicate_ids,
        status=record.status,
        puzzleHash=record.puzzle_hash,
        puzzleId=record.puzzle_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@v2_session_journal_api.get("/api/future/sessions/v2/<session_id>/analysis")
def get_v2_session_analysis(session_id):
    if not _canonical_uuid(session_id):
        return _session_error("Invalid session id", 400)
    profile_id = request.args.get("profileId")
    writer_token = request.headers.get("X-Future-Session-Writer", "")
    if not _canonical_uuid(profile_id):
        return _session_error("Invalid profile id", 400)
    record = db.session.get(FuturePuzzleV2SolveSession, session_id)
    if record is None or record.profile_id != profile_id:
        return _session_error("V2 session not found", 404)
    if not _writer_matches(record, writer_token):
        return _session_error("Invalid writer capability", 403)
    if record.status == "active":
        return _session_error(
            "V2 session analysis is available after the session finishes", 409
        )
    if record.status != "finished":
        return _session_error("V2 session state failed integrity validation", 503)
    analysis = db.session.get(FuturePuzzleV2SolveAnalysis, session_id)
    if analysis is None:
        return _session_error("V2 session analysis failed integrity validation", 503)
    try:
        verified_analysis = _recompute_final_v2_analysis(record, analysis)
    except (
        SolveReplayRejected,
        SolveReplayUnavailable,
        TypeError,
        ValueError,
        KeyError,
        RecursionError,
    ):
        return _session_error("Finalized V2 analysis failed integrity validation", 503)
    response = jsonify(
        sessionId=session_id,
        profileId=record.profile_id,
        puzzleHash=record.puzzle_hash,
        puzzleId=record.puzzle_id,
        finalized=True,
        analysis=verified_analysis,
    )
    response.headers["Cache-Control"] = "no-store"
    return response
