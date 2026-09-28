"""Host-owned, immutable postgame reflection decks and response evidence."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from uuid import NAMESPACE_URL, UUID, uuid5

import requests
from flask import Blueprint, jsonify, request
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import RequestEntityTooLarge

from .database import db
from .episteme_store import (
    MAX_PROFILE_BYTES,
    EpistemeCommandRejected,
    EpistemeProfileRecord,
    EpistemeRevisionConflict,
    EpistemeRuntimeUnavailable,
    apply_episteme_command,
    episteme_profile_size,
    get_or_create_episteme_profile,
)
from .future import StartingProfile
from .future_puzzles import FuturePuzzleManifestRecord, FutureSolveAnalysisRecord
from .language_signals import has_explicit_language_signal
from .session_journal import PersonalSolveSession

reflection_api = Blueprint("reflection_api", __name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_SCRIPT = PROJECT_ROOT / "scripts" / "reflection-bridge.cjs"
MAX_BODY_BYTES = 32 * 1024
MAX_DECK_BYTES = 128 * 1024
DECK_VERSION = 1
REFLECTION_MODEL_ENV = "CROSSWORD_REFLECTION_MODEL_CARDS"
REFLECTION_MODEL_VERSION = "private-reflection-model-card-v1"
REFLECTION_MODEL_PROMPT_VERSION = "private-reflection-mirror-prompt-v1"
_LANGUAGE_CODES = {
    "french": "fr",
    "german": "de",
    "spanish": "es",
    "italian": "it",
    "portuguese": "pt",
    "japanese": "ja",
    "dutch": "nl",
}
_LANGUAGE_THREAD = re.compile(r"\blanguage thread:\s*([A-Za-z]+)\b", re.IGNORECASE)
CARD_BANK = {
    "wordplay": (
        {
            "id": "reflection-wordplay-turn-v1",
            "text": "I enjoy a clue that makes a familiar phrase turn in a new direction.",
            "tone": "wry",
            "concept": ("clue-wordplay", "wordplay and misdirection"),
            "keep": ("taste", 0.12),
            "avoid": ("clue-wordplay", "wordplay-heavy clueing", "taste", 0.10),
            "interpretation": (
                "More playful turns of phrase.",
                "Fewer clues built mainly around wordplay.",
                "Leave this impression undecided.",
            ),
        },
        {
            "id": "reflection-wordplay-double-take-v1",
            "text": "I like when a clue lets me read it one way, then catches me reading it another.",
            "tone": "curious",
            "concept": ("clue-wordplay", "wordplay and misdirection"),
            "keep": ("taste", 0.12),
            "avoid": ("clue-wordplay", "wordplay-heavy clueing", "taste", 0.10),
            "interpretation": (
                "More clues with a satisfying second reading.",
                "Fewer clues that depend on a trick of phrasing.",
                "Leave this impression undecided.",
            ),
        },
        {
            "id": "reflection-wordplay-language-v1",
            "text": "A playful use of language can be as satisfying as a fact I already know.",
            "tone": "plain",
            "concept": ("clue-wordplay", "wordplay and misdirection"),
            "keep": ("taste", 0.12),
            "avoid": ("clue-wordplay", "wordplay-heavy clueing", "taste", 0.10),
            "interpretation": (
                "More clues where language itself is the play.",
                "Fewer clues built mainly around wordplay.",
                "Leave this impression undecided.",
            ),
        },
    ),
    "discovery": (
        {
            "id": "reflection-discovery-crossings-v1",
            "text": "I like meeting an unfamiliar word when the crossings give me a fair way in.",
            "tone": "curious",
            "concept": ("crossing-supported-discovery", "crossing-supported discovery"),
            "keep": ("goal", 0.12),
            "avoid": (
                "obscure-vocabulary",
                "unsupported obscure vocabulary",
                "context",
                0.10,
            ),
            "interpretation": (
                "More unfamiliar words with generous crossings.",
                "Fewer obscure answers that depend on outside knowledge.",
                "Let another puzzle speak for this one.",
            ),
        },
        {
            "id": "reflection-discovery-new-corner-v1",
            "text": "I enjoy a puzzle that sends me away knowing one small thing I did not know before.",
            "tone": "lyrical",
            "concept": ("crossing-supported-discovery", "crossing-supported discovery"),
            "keep": ("goal", 0.12),
            "avoid": (
                "obscure-vocabulary",
                "unsupported obscure vocabulary",
                "context",
                0.10,
            ),
            "interpretation": (
                "More fair chances to discover new words and ideas.",
                "Fewer answers that rely on hard-to-reach outside knowledge.",
                "Let another puzzle speak for this one.",
            ),
        },
        {
            "id": "reflection-discovery-context-v1",
            "text": "A new name or term feels welcome when its clue gives me enough context to approach it.",
            "tone": "plain",
            "concept": ("crossing-supported-discovery", "crossing-supported discovery"),
            "keep": ("goal", 0.12),
            "avoid": (
                "obscure-vocabulary",
                "unsupported obscure vocabulary",
                "context",
                0.10,
            ),
            "interpretation": (
                "More new vocabulary with clear context and crossings.",
                "Fewer answers that require prior familiarity with a name.",
                "Let another puzzle speak for this one.",
            ),
        },
    ),
    "challenge": (
        {
            "id": "reflection-challenge-click-v1",
            "text": "A square is most satisfying when I pause, then feel the small click of getting there.",
            "tone": "lyrical",
            "concept": ("earned-crossword-challenge", "earned crossword challenge"),
            "keep": ("style", 0.10),
            "avoid": ("high-friction-clueing", "high-friction clueing", "style", 0.10),
            "interpretation": (
                "Keep a little room for satisfying resistance.",
                "Make the challenge feel more inviting and less grinding.",
                "Keep the difficulty dial where it is for now.",
            ),
        },
        {
            "id": "reflection-challenge-stretch-v1",
            "text": "I like a puzzle that asks a little more of me, as long as the crossings stay fair.",
            "tone": "curious",
            "concept": ("earned-crossword-challenge", "earned crossword challenge"),
            "keep": ("style", 0.10),
            "avoid": ("high-friction-clueing", "high-friction clueing", "style", 0.10),
            "interpretation": (
                "Leave room for fair stretches of difficulty.",
                "Keep more puzzles comfortably within reach.",
                "Keep the difficulty dial where it is for now.",
            ),
        },
        {
            "id": "reflection-challenge-aha-v1",
            "text": "I would rather earn an 'aha' than have every answer arrive at once.",
            "tone": "wry",
            "concept": ("earned-crossword-challenge", "earned crossword challenge"),
            "keep": ("style", 0.10),
            "avoid": ("high-friction-clueing", "high-friction clueing", "style", 0.10),
            "interpretation": (
                "Keep some satisfying moments of discovery.",
                "Offer a gentler path through the puzzle.",
                "Keep the difficulty dial where it is for now.",
            ),
        },
    ),
}

# Keep the visible deck small (one card from each category per session) while
# giving repeated play a real authored bank.  These are deliberately
# declarative statements rather than preference questions; the existing
# mappings remain fixed and reversible.  The cards are versioned as content,
# so an already-created deck stays byte-for-byte stable when this bank grows.
_REFLECTION_VARIANTS = {
    "wordplay": (
        ("A clue can be a small joke without requiring a private dictionary.", "plain"),
        ("I like words that sound ordinary until the clue tilts them.", "curious"),
        ("A quotation mark should feel like a change of room.", "lyrical"),
        ("I enjoy a question that knows exactly why it is asking.", "wry"),
        ("A good pun leaves a clean path back to the answer.", "plain"),
        ("The best misdirection is visible in retrospect.", "curious"),
        ("I like clues that make me notice a second meaning.", "curious"),
        ("A familiar phrase can still hide a fresh answer.", "lyrical"),
        ("I enjoy a clue that plays with spelling rather than trivia.", "plain"),
        ("A tiny grammatical signal can change the whole solve.", "wry"),
        ("I like when the clue's tone is part of its mechanism.", "curious"),
        ("A wordplay clue should reward attention more than guesswork.", "plain"),
        ("I enjoy an answer that arrives through sound.", "lyrical"),
        ("A bracket or abbreviation can be a helpful little door.", "plain"),
        ("I like language that refuses to sit still.", "wry"),
        ("The turn in a clue should feel earned.", "curious"),
        ("I enjoy seeing how much a few exact words can do.", "lyrical"),
    ),
    "discovery": (
        (
            "A new word feels generous when the crossings offer its first foothold.",
            "plain",
        ),
        ("I enjoy learning a term through its texture before its history.", "curious"),
        (
            "A name is easier to welcome when the clue gives it a small world.",
            "lyrical",
        ),
        ("I like leaving a puzzle with one useful new word in my pocket.", "plain"),
        ("A fair crossing can turn unfamiliarity into curiosity.", "curious"),
        ("I enjoy a clue that gives context without doing all the work.", "wry"),
        (
            "A new corner of language is worth visiting when there is a way in.",
            "lyrical",
        ),
        ("I like discovering a word by its shape, sound, and neighbors.", "plain"),
        (
            "An unfamiliar answer feels good when it becomes obvious afterward.",
            "curious",
        ),
        (
            "I enjoy a small fact more when it belongs to the puzzle's fabric.",
            "lyrical",
        ),
        ("A clue can make a distant subject feel briefly close.", "plain"),
        ("I like the moment a strange-looking answer starts to make sense.", "curious"),
        ("A new term should arrive with a handle I can hold.", "wry"),
        ("I enjoy being surprised by a word the grid has prepared me for.", "lyrical"),
        ("A little context can make an obscure answer feel less arbitrary.", "plain"),
        ("I like puzzles that widen the map without demanding a passport.", "wry"),
        ("A new word is welcome when the route to it feels fair.", "curious"),
    ),
    "challenge": (
        (
            "A hard clue is welcome when its exactness becomes visible afterward.",
            "plain",
        ),
        (
            "I like the puzzle to keep one door closed until the room appears.",
            "lyrical",
        ),
        ("A little resistance makes a correct square feel more present.", "curious"),
        ("I enjoy a clue that asks for patience rather than obscure facts.", "plain"),
        (
            "The best stretch is difficult enough to remember and fair enough to repeat.",
            "wry",
        ),
        (
            "I like finding the answer after the crossings have quietly changed it.",
            "curious",
        ),
        ("A puzzle can be demanding without becoming hostile.", "plain"),
        ("I enjoy a long route when each turn leaves a sign.", "lyrical"),
        ("A stubborn corner is satisfying when there is a real way through.", "wry"),
        ("I like an aha that arrives because I stayed with the clue.", "curious"),
        ("A challenge should sharpen attention, not punish inexperience.", "plain"),
        ("I enjoy when the final few squares ask for one last re-reading.", "lyrical"),
        ("A fair puzzle can make uncertainty feel playful.", "wry"),
        ("I like earning a pattern instead of being handed one.", "curious"),
        ("A difficult clue is kind when its wording stays exact.", "plain"),
        ("I enjoy a puzzle that leaves a little work for tomorrow.", "lyrical"),
        ("The right amount of friction makes the next turn tempting.", "wry"),
    ),
}


def _extend_authored_reflection_bank():
    for category, variants in _REFLECTION_VARIANTS.items():
        base = CARD_BANK[category][0]
        cards = list(CARD_BANK[category])
        for offset, (text, tone) in enumerate(variants, start=4):
            if category == "wordplay":
                interpretation = (
                    "More clues where language itself is the play.",
                    "Fewer clues built mainly around a turn of wording.",
                    "Leave this impression undecided.",
                )
            elif category == "discovery":
                interpretation = (
                    "More new words with clear context and crossings.",
                    "Fewer answers that require outside familiarity.",
                    "Let another puzzle speak for this one.",
                )
            else:
                interpretation = (
                    "Leave room for fair resistance.",
                    "Make the next puzzle more inviting.",
                    "Keep the difficulty dial where it is for now.",
                )
            cards.append(
                {
                    **base,
                    "id": f"reflection-{category}-{offset:02d}-v1",
                    "text": text,
                    "tone": tone,
                    "interpretation": interpretation,
                }
            )
        CARD_BANK[category] = tuple(cards)


_extend_authored_reflection_bank()
CARD_IDS = tuple(card["id"] for cards in CARD_BANK.values() for card in cards)
MAX_EPISTEME_CAS_ATTEMPTS = 4
_REFLECTION_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$"
)


class FutureReflectionDeckRecord(db.Model):
    __tablename__ = "future_reflection_decks"

    session_id = db.Column(db.String(36), primary_key=True)
    deck_version = db.Column(db.Integer, nullable=False)
    deck_json = db.Column(db.JSON, nullable=False)
    deck_hash = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.String(40), nullable=False)


class FutureReflectionResponseRecord(db.Model):
    __tablename__ = "future_reflection_responses"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "card_id", name="uq_future_reflection_session_card"
        ),
    )

    response_id = db.Column(db.String(36), primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    card_id = db.Column(db.String(160), nullable=False)
    response_hash = db.Column(db.String(64), nullable=False)
    response_json = db.Column(db.JSON, nullable=False)
    evidence_json = db.Column(db.JSON, nullable=True)
    episteme_revision = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="pending")
    recorded_at = db.Column(db.String(40), nullable=False)


class FutureReflectionActionRecord(db.Model):
    __tablename__ = "future_reflection_actions"

    action_id = db.Column(db.String(36), primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    card_id = db.Column(db.String(160), nullable=False)
    target_response_id = db.Column(db.String(36), nullable=False, index=True)
    action_hash = db.Column(db.String(64), nullable=False)
    action_json = db.Column(db.JSON, nullable=False)
    evidence_action_json = db.Column(db.JSON, nullable=True)
    episteme_revision = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="pending")
    recorded_at = db.Column(db.String(40), nullable=False)


class ReflectionRuntimeUnavailable(RuntimeError):
    """The local Node/TypeScript conversion bridge is unavailable."""


class ReflectionConversionRejected(ValueError):
    """The shared reflection contracts rejected a card/response pair."""


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _valid_uuid(value):
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _error(message, status):
    response = jsonify(error=message)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _same_origin():
    origin = request.headers.get("Origin")
    return origin is not None and origin == request.host_url.rstrip("/")


def _utc_now():
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _mapping(
    card_id,
    suffix,
    concept_id,
    label,
    kind,
    stance,
    weight,
    created_at,
    *,
    negative=False,
):
    scope = {"mode": "future-crossword", "language": "en"}
    if negative:
        expiry = datetime.fromisoformat(created_at.replace("Z", "+00:00")) + timedelta(
            days=30
        )
        scope["expiresAt"] = expiry.isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        )
    return {
        "mappingId": f"{card_id}:{suffix}:v1",
        "concept": {"conceptId": concept_id, "label": label, "language": "en"},
        "kind": kind,
        "stance": stance,
        "weight": weight,
        "scope": scope,
    }


def _language_learning_signal(manifest, language_entry_ids):
    """Expose a compact review cue for an explicitly selected language.

    This is a scheduling/presentation signal only. Generated answer forms are
    still unreviewed, and no response here is interpreted as vocabulary
    mastery.
    """
    metadata = manifest.get("metadata") if isinstance(manifest, dict) else None
    notepad = metadata.get("notepad") if isinstance(metadata, dict) else None
    if not isinstance(notepad, str) and isinstance(manifest, dict):
        notepad = manifest.get("subtitle")
    match = _LANGUAGE_THREAD.search(notepad) if isinstance(notepad, str) else None
    language = match.group(1) if match else None
    code = _LANGUAGE_CODES.get(language.casefold()) if language else None
    if not language or not code:
        return None
    entry_ids = language_entry_ids[:4] if isinstance(language_entry_ids, list) else []
    return {
        "language": language,
        "code": code,
        "state": "review" if entry_ids else "introduced",
        "reviewDue": bool(entry_ids),
        "relatedEntryIds": entry_ids,
        "source": "explicit-setup",
        "masteryClaim": "none",
    }


def _reflection_context(session_id):
    """Derive small, explainable cues from the frozen played puzzle.

    These cues choose among authored sentences; they never infer a personality
    or create a new preference mapping. Missing/legacy manifests simply retain
    the generic deck.
    """
    session = db.session.get(PersonalSolveSession, session_id)
    if session is None:
        return {}
    manifest_record = db.session.get(FuturePuzzleManifestRecord, session.puzzle_hash)
    manifest = manifest_record.manifest_json if manifest_record is not None else None
    entries = manifest.get("entries", []) if isinstance(manifest, dict) else []
    if not isinstance(entries, list):
        return {}
    normalized = [entry for entry in entries if isinstance(entry, dict)]
    if not normalized:
        return {}
    by_id = {
        entry.get("id"): entry
        for entry in normalized
        if isinstance(entry.get("id"), str)
    }
    wordplay_ids = [
        entry_id
        for entry_id, entry in by_id.items()
        if any(
            signal in str(entry.get("clue", "")).casefold()
            for signal in ("?", "anagram", "reverse", "backward", "(abbr.)", "[sound")
        )
    ]
    metadata = manifest.get("metadata") if isinstance(manifest, dict) else None
    notepad = metadata.get("notepad") if isinstance(metadata, dict) else None
    if not isinstance(notepad, str) and isinstance(manifest, dict):
        notepad = manifest.get("subtitle")
    provenance = manifest.get("provenance") if isinstance(manifest, dict) else None
    model = provenance.get("model") if isinstance(provenance, dict) else None
    language_match = _LANGUAGE_THREAD.search(notepad) if isinstance(notepad, str) else None
    language_name = language_match.group(1) if language_match else None
    language_ids = [
        entry_id
        for entry_id, entry in by_id.items()
        if language_name
        and has_explicit_language_signal(str(entry.get("clue", "")), language_name)
    ]
    discovery_ids = [
        entry_id
        for entry_id, entry in by_id.items()
        if len(str(entry.get("answer", ""))) >= 9
        or any(
            term in str(entry.get("clue", "")).casefold()
            for term in (
                "river",
                "botanical",
                "surname",
                "zodiac",
                "nickname",
                "in ",
            )
        )
    ]
    discovery_ids = list(dict.fromkeys(discovery_ids + language_ids))
    challenge_ids = [
        entry_id
        for entry_id, entry in by_id.items()
        if len(str(entry.get("answer", ""))) >= 8
    ]
    return {
        "wordplay": wordplay_ids[:4],
        "language": language_ids[:4],
        "discovery": discovery_ids[:4],
        "challenge": challenge_ids[:4],
        "hasWordplay": bool(wordplay_ids),
        "hasLanguage": bool(language_ids),
        "hasDiscovery": bool(discovery_ids),
        "hasChallenge": bool(challenge_ids),
        "languageLearning": _language_learning_signal(manifest, language_ids),
        "puzzleHash": session.puzzle_hash,
        **({"model": model} if isinstance(model, str) and model else {}),
    }


def _analysis_summary(analysis):
    """Project the replay ledger into a small, answer-free postgame trace.

    The full event stream stays in the host journal.  Reflections only need a
    bounded explanation of how the game was solved, so this projection never
    exposes answers, cell contents, or a mastery judgment.
    """
    raw = analysis.get("observations") if isinstance(analysis, dict) else None
    observations = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    outcomes = [item.get("outcome") for item in observations]
    final_states = [item.get("finalState") for item in observations]
    assisted_outcomes = {"check-assisted-correction", "reveal-assisted-correction"}
    return {
        "version": "private-session-analysis-summary-v1",
        "entryCount": len(observations),
        "correctCount": sum(state == "correct" for state in final_states),
        "incompleteCount": sum(state == "incomplete" for state in final_states),
        "incorrectCount": sum(state == "incorrect" for state in final_states),
        "independentCount": sum(outcome == "independent-retrieval" for outcome in outcomes),
        "supportedCount": sum(outcome == "supported-retrieval" for outcome in outcomes),
        "assistedCount": sum(outcome in assisted_outcomes for outcome in outcomes),
        "exposureCount": sum(outcome == "exposure" for outcome in outcomes),
        "untouchedCount": sum(outcome == "untouched" for outcome in outcomes),
        "checkedCount": sum(
            bool(item.get("correctnessShownCellIds")) for item in observations
        ),
        "revealedCount": sum(bool(item.get("revealedCellIds")) for item in observations),
        "incorrectAttemptCount": sum(
            item.get("incorrectAttemptCount", 0)
            for item in observations
            if isinstance(item.get("incorrectAttemptCount", 0), int)
            and item.get("incorrectAttemptCount", 0) >= 0
        ),
        "interpretation": "difficulty-and-recall-signal-only",
        "masteryClaim": "none",
    }


def _history_limit(value):
    """Parse the small, owner-facing history window without widening the route."""
    try:
        limit = int(value) if value is not None else 12
    except (TypeError, ValueError):
        return None
    return limit if 1 <= limit <= 50 else None


def _history_personalization(provenance):
    """Project generated-board personalization without profile text or digests."""
    receipt = provenance.get("personalizationReceipt") if isinstance(provenance, dict) else None
    if (
        not isinstance(receipt, dict)
        or receipt.get("version") != "private-personalization-receipt-v1"
        or not isinstance(receipt.get("epistemeRevision"), int)
        or isinstance(receipt.get("epistemeRevision"), bool)
    ):
        return None
    inputs = receipt.get("inputs") if isinstance(receipt.get("inputs"), dict) else {}
    bounded_counts = {}
    for key in ("claimCount", "associationCount", "knowledgeItemCount", "recentExposureCount"):
        value = inputs.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 64:
            bounded_counts[key] = value
    if isinstance(inputs.get("languageThread"), bool):
        bounded_counts["languageThread"] = inputs["languageThread"]
    recommendation = inputs.get("difficultyRecommendation")
    if isinstance(recommendation, str) and recommendation in {
        "more-footholds",
        "balanced",
        "gentle-stretch",
    }:
        bounded_counts["difficultyRecommendation"] = recommendation
    steering = receipt.get("associationSteering")
    if isinstance(steering, dict):
        steering_projection = {}
        for key in ("projectionCount", "eligibleCount", "expiredCount", "excludedResponseCount"):
            value = steering.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 24:
                steering_projection[key] = value
        diversity = steering.get("diversity")
        if isinstance(diversity, dict):
            unique_relations = diversity.get("uniqueRelations")
            status = diversity.get("status")
            if isinstance(unique_relations, int) and not isinstance(unique_relations, bool) and 0 <= unique_relations <= 8:
                steering_projection["uniqueRelations"] = unique_relations
            if status in {"none", "narrow", "varied"}:
                steering_projection["diversityStatus"] = status
        if steering_projection:
            bounded_counts["associationSteering"] = steering_projection
    clue_diversity = provenance.get("clueDiversity")
    if isinstance(clue_diversity, dict):
        diversity_projection = {}
        status = clue_diversity.get("status")
        if status in {"empty", "definition-heavy", "varied"}:
            diversity_projection["status"] = status
        families = clue_diversity.get("nonDefinitionFamilies")
        if isinstance(families, list):
            family_count = sum(1 for item in families if isinstance(item, str))
            if family_count <= 8:
                diversity_projection["nonDefinitionFamilyCount"] = family_count
        repair = clue_diversity.get("repair")
        if isinstance(repair, dict):
            rewritten = repair.get("rewrittenCount")
            if isinstance(rewritten, int) and not isinstance(rewritten, bool) and 0 <= rewritten <= 4:
                diversity_projection["repairRewrittenCount"] = rewritten
        if diversity_projection:
            bounded_counts["clueDiversity"] = diversity_projection
    return {
        "version": "private-history-personalization-v1",
        "epistemeRevision": receipt["epistemeRevision"],
        **bounded_counts,
        "interpretation": "answer-free-generation-lane-summary",
    }


def _profile_game_history(profile_id, limit):
    """Project finished/private play into an answer-free profile timeline."""
    sessions = (
        PersonalSolveSession.query.filter_by(profile_id=profile_id)
        .order_by(PersonalSolveSession.updated_at.desc(), PersonalSolveSession.id.desc())
        .limit(limit)
        .all()
    )
    history = []
    for session in sessions:
        manifest_record = db.session.get(
            FuturePuzzleManifestRecord, session.puzzle_hash
        )
        manifest = (
            manifest_record.manifest_json
            if manifest_record is not None
            and isinstance(manifest_record.manifest_json, dict)
            else {}
        )
        metadata = manifest.get("metadata") if isinstance(manifest, dict) else {}
        provenance = manifest.get("provenance") if isinstance(manifest, dict) else {}
        metadata = metadata if isinstance(metadata, dict) else {}
        provenance = provenance if isinstance(provenance, dict) else {}
        analysis_record = db.session.get(FutureSolveAnalysisRecord, session.id)
        analysis = (
            analysis_record.analysis_json
            if analysis_record is not None
            and isinstance(analysis_record.analysis_json, dict)
            else None
        )
        recipe = provenance.get("weekdayRecipe")
        weekday = provenance.get("weekday")
        if not isinstance(weekday, str) and isinstance(recipe, dict):
            weekday = recipe.get("id")
        summary = _analysis_summary(analysis) if analysis is not None else None
        item = {
            "sessionId": session.id,
            "status": session.status,
            "createdAt": session.created_at,
            "updatedAt": session.updated_at,
            "finished": session.status == "finished"
            and bool(analysis_record and analysis_record.finalized),
            "title": metadata.get("title")
            if isinstance(metadata.get("title"), str)
            else "Personal crossword",
            "weekday": weekday if isinstance(weekday, str) else None,
            "model": provenance.get("model")
            if isinstance(provenance.get("model"), str)
            else None,
            "analysis": summary,
        }
        personalization = _history_personalization(provenance)
        if personalization is not None:
            item["personalization"] = personalization
        history.append(item)
    return history


def _calibration_bucket():
    return {
        "sessionCount": 0,
        "entryCount": 0,
        "correctCount": 0,
        "independentCount": 0,
        "supportedCount": 0,
        "assistedCount": 0,
        "incorrectCount": 0,
        "untouchedCount": 0,
        "incorrectAttemptCount": 0,
    }


def _finish_calibration_bucket(bucket):
    entry_count = bucket["entryCount"]
    denominator = max(1, entry_count)
    return {
        **bucket,
        "completionRate": round(bucket["correctCount"] / denominator, 3),
        "independentRate": round(bucket["independentCount"] / denominator, 3),
        "supportRate": round(
            (bucket["supportedCount"] + bucket["assistedCount"]) / denominator,
            3,
        ),
        "mistakeRate": round(
            min(1.0, bucket["incorrectAttemptCount"] / denominator), 3
        ),
    }


def _profile_calibration_report(history, *, limit):
    """Aggregate observed private play without presenting a solve probability."""
    report = _calibration_bucket()
    by_weekday = {}
    by_model = {}
    finished = 0
    for item in history if isinstance(history, list) else []:
        if not isinstance(item, dict) or item.get("finished") is not True:
            continue
        analysis = item.get("analysis")
        if not isinstance(analysis, dict) or analysis.get("version") != (
            "private-session-analysis-summary-v1"
        ):
            continue
        finished += 1
        target_buckets = [report]
        weekday = item.get("weekday") if isinstance(item.get("weekday"), str) else "unknown"
        model = item.get("model") if isinstance(item.get("model"), str) else "unknown"
        by_weekday.setdefault(weekday, _calibration_bucket())
        by_model.setdefault(model, _calibration_bucket())
        target_buckets.extend((by_weekday[weekday], by_model[model]))
        for bucket in target_buckets:
            bucket["sessionCount"] += 1
            for key in (
                "entryCount",
                "correctCount",
                "independentCount",
                "supportedCount",
                "assistedCount",
                "incorrectCount",
                "untouchedCount",
                "incorrectAttemptCount",
            ):
                value = analysis.get(key, 0)
                if type(value) is int and value >= 0:
                    bucket[key] += value
    return {
        "version": "private-play-calibration-report-v1",
        "status": "observational" if finished >= 3 else "insufficient-observations",
        "profileId": None,
        "limit": limit,
        "sessionCount": finished,
        "requiredSessions": 3,
        "totals": _finish_calibration_bucket(report),
        "byWeekday": {
            key: _finish_calibration_bucket(value)
            for key, value in sorted(by_weekday.items())
        },
        "byModel": {
            key: _finish_calibration_bucket(value)
            for key, value in sorted(by_model.items())
        },
        "interpretation": "observed-private-play-only",
        "uncertainty": [
            "not-a-solve-probability",
            "not-a-mastery-claim",
            "not-human-calibrated",
        ],
    }


def _profile_calibration_export(profile_id, *, limit):
    """Build the bounded, answer-free artifact used for local tuning.

    This is intentionally smaller than the full profile archive.  It gives a
    researcher or a future local evaluator the observed route through recent
    games without copying manifests, clues, grids, raw journal events, or
    profile prose into a portable file.
    """
    history = _profile_game_history(profile_id, limit)
    traces = []
    for item in history:
        if not isinstance(item, dict):
            continue
        traces.append(
            {
                key: item[key]
                for key in (
                    "sessionId",
                    "status",
                    "createdAt",
                    "updatedAt",
                    "finished",
                    "weekday",
                    "model",
                    "analysis",
                )
                if key in item
            }
        )
    report = _profile_calibration_report(history, limit=limit)
    report["profileId"] = profile_id
    payload = {
        "version": "private-play-calibration-export-v1",
        "profileId": profile_id,
        "historyLimit": limit,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "kind": "profile-history",
            "route": "/api/future/profile/:id/calibration-export",
            "analysisVersion": "private-session-analysis-summary-v1",
        },
        "traceCount": len(traces),
        "traces": traces,
        "calibration": report,
        "redactions": [
            "answers",
            "clues",
            "grids",
            "raw-solve-events",
            "profile-prose",
        ],
        "interpretation": "local-tuning-artifact-only",
        "uncertainty": [
            "not-a-solve-probability",
            "not-a-mastery-claim",
            "not-a-human-evaluation",
        ],
    }
    payload["integrity"] = {
        "version": "private-play-calibration-integrity-v1",
        "algorithm": "sha256",
        "value": _hash(payload),
    }
    return payload


def _authored_cards(created_at, session_id, context=None):
    """Select one authored card per reviewed category, frozen by session identity."""
    context = context or {}
    cards = []
    for category, options in CARD_BANK.items():
        selector = hashlib.sha256(
            f"reflection-deck-v{DECK_VERSION}:{session_id}:{category}".encode("utf-8")
        ).digest()
        spec = options[int.from_bytes(selector[:4], "big") % len(options)]
        card_id = spec["id"]
        concept_id, label = spec["concept"]
        keep_kind, keep_weight = spec["keep"]
        avoid_id, avoid_label, avoid_kind, avoid_weight = spec["avoid"]
        keep_text, not_for_me_text, pass_text = spec["interpretation"]
        card = {
            "schemaVersion": 1,
            "cardId": card_id,
            "version": 1,
            "createdAt": created_at,
            "text": spec["text"],
            "language": "en",
            "relatedEntryIds": [],
            "source": "authored",
            "status": "approved",
            "tone": spec["tone"],
            "ambiguity": "clear",
            "interpretation": {
                "keep": keep_text,
                "notForMe": not_for_me_text,
                "pass": pass_text,
            },
            "keepMappings": [
                _mapping(
                    card_id,
                    "keep",
                    concept_id,
                    label,
                    keep_kind,
                    "seek",
                    keep_weight,
                    created_at,
                )
            ],
            "notForMeMappings": [
                _mapping(
                    card_id,
                    "not-for-me",
                    avoid_id,
                    avoid_label,
                    avoid_kind,
                    "avoid",
                    avoid_weight,
                    created_at,
                    negative=True,
                )
            ],
            "groundingRefs": ["editorial-reflection-deck-v1"],
            "generationReceipt": None,
        }
        related = context.get(category, [])
        if isinstance(related, list) and related:
            card["relatedEntryIds"] = related[:12]
            card["groundingRefs"] = [
                "editorial-reflection-deck-v1",
                "reflection-context-v1",
                f"puzzle:{context.get('puzzleHash', '')}",
            ]
            if category == "wordplay" and context.get("hasWordplay"):
                card["text"] = (
                    "I liked when this puzzle let language itself become part of the mechanism."
                )
                card["interpretation"] = {
                    "keep": "More clues where language itself is the play.",
                    "notForMe": "Fewer clues that depend on a turn of wording.",
                    "pass": "Leave this particular kind of turn undecided.",
                }
            elif category == "discovery" and context.get("hasLanguage"):
                card["text"] = (
                    "A small foreign-language doorway feels welcome when the clue tells me how to enter it."
                )
                card["interpretation"] = {
                    "keep": "More clearly signalled language-learning moments.",
                    "notForMe": "Fewer foreign-language answers in the next puzzle.",
                    "pass": "Leave the language balance undecided.",
                }
            elif category == "discovery" and context.get("hasDiscovery"):
                card["text"] = (
                    "I like meeting a longer or less familiar answer when the crossings give me a fair way in."
                )
                card["interpretation"] = {
                    "keep": "More discoveries with generous crossings and context.",
                    "notForMe": "Fewer answers that depend on hard-to-reach outside knowledge.",
                    "pass": "Let another puzzle speak for this kind of discovery.",
                }
            elif category == "challenge" and context.get("hasChallenge"):
                card["text"] = (
                    "This puzzle asked me to hold a little more in mind before the click; I may want that stretch again."
                )
                card["interpretation"] = {
                    "keep": "Leave room for satisfying stretches of difficulty.",
                    "notForMe": "Make the challenge feel more inviting and less grinding.",
                    "pass": "Keep the difficulty dial where it is for now.",
                }
        cards.append(card)
    return cards


def _reflection_model_enabled():
    return os.environ.get(REFLECTION_MODEL_ENV, "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _reflection_model_name(preferred_model=None):
    """Resolve the exact installed local tag, never a similarly named model."""
    from .private_puzzle_generation import _installed_model, _resolve_model_override

    configured = os.environ.get("CROSSWORD_REFLECTION_MODEL")
    if configured:
        return _resolve_model_override(configured)
    if isinstance(preferred_model, str) and preferred_model:
        return _resolve_model_override(preferred_model)
    return _installed_model()


def _reflection_model_cards(created_at, session_id, context, authored):
    """Optionally rewrite authored prompts while retaining their mappings.

    The local model supplies only first-person wording and interpretations. The
    category, concept mapping, scope, response budget, and reversible reducer
    behavior remain host-authored. Any unavailable, malformed, or unsafe model
    result returns the original authored deck unchanged.
    """
    if not _reflection_model_enabled() or not authored:
        return authored
    try:
        model = _reflection_model_name(context.get("model"))
        categories = list(CARD_BANK)
        schema = {
            "type": "object",
            "properties": {
                "cards": {
                    "type": "array",
                    "minItems": len(categories),
                    "maxItems": len(categories),
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "enum": categories},
                            "text": {"type": "string", "minLength": 12, "maxLength": 180},
                            "keep": {"type": "string", "minLength": 8, "maxLength": 180},
                            "notForMe": {"type": "string", "minLength": 8, "maxLength": 180},
                            "pass": {"type": "string", "minLength": 8, "maxLength": 180},
                        },
                        "required": ["category", "text", "keep", "notForMe", "pass"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["cards"],
            "additionalProperties": False,
        }
        response = requests.post(
            "http://127.0.0.1:11434/api/chat",
            timeout=(2, 75),
            json={
                "model": model,
                "stream": False,
                "think": False,
                "format": schema,
                "options": {"temperature": 0.65, "num_predict": 900},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Rewrite three crossword reflection cards in first-person language. "
                            "They are invitations, not facts about a player. Do not diagnose, identify, "
                            "politicize, sexualize, or claim anything about the player's personality, "
                            "health, beliefs, identity, intelligence, relationships, or knowledge. "
                            "Keep each category distinct and concrete. Preserve uncertainty and make "
                            "keep, turn-away, and pass interpretations independently meaningful. "
                            "Return exactly one card for each supplied category and JSON only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "categories": categories,
                                "puzzleSignals": {
                                    key: value
                                    for key, value in context.items()
                                    if key
                                    in {
                                        "hasWordplay",
                                        "hasLanguage",
                                        "hasDiscovery",
                                        "hasChallenge",
                                    }
                                },
                                "task": "Offer a more personal-sounding mirror while leaving desire undecided.",
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    },
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
        message = payload.get("message") if isinstance(payload, dict) else None
        raw = message.get("content") if isinstance(message, dict) else None
        value = json.loads(raw) if isinstance(raw, str) else None
        rows = value.get("cards") if isinstance(value, dict) else None
        if not isinstance(rows, list) or {row.get("category") for row in rows if isinstance(row, dict)} != set(categories):
            return authored
        forbidden = (
            "diagnos",
            "mental health",
            "politic",
            "religion",
            "trauma",
            "disorder",
            "your personality",
            "you are",
            "you must",
        )
        by_category = {}
        for row in rows:
            if not isinstance(row, dict) or row.get("category") in by_category:
                return authored
            values = {key: row.get(key) for key in ("text", "keep", "notForMe", "pass")}
            if any(
                not isinstance(text, str)
                or text.strip() != text
                or not 8 <= len(text) <= 180
                or "\n" in text
                or any(term in text.casefold() for term in forbidden)
                for text in values.values()
            ):
                return authored
            by_category[row["category"]] = values
        generated_at = _utc_now()
        generation_id = _hash({"sessionId": session_id, "model": model, "cards": by_category})
        result = []
        for category, card in zip(categories, authored):
            values = by_category[category]
            result.append(
                {
                    **card,
                    "text": values["text"],
                    "source": "model",
                    "interpretation": {
                        "keep": values["keep"],
                        "notForMe": values["notForMe"],
                        "pass": values["pass"],
                    },
                    "groundingRefs": [
                        *card["groundingRefs"],
                        REFLECTION_MODEL_VERSION,
                    ],
                    "generationReceipt": {
                        "generationId": generation_id,
                        "model": model,
                        "promptVersion": REFLECTION_MODEL_PROMPT_VERSION,
                        "generatedAt": generated_at,
                        "reviewStatus": "approved",
                        "reviewedAt": generated_at,
                    },
                }
            )
        return result
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, requests.RequestException):
        return authored


def _create_deck(session_id):
    record = db.session.get(FutureReflectionDeckRecord, session_id)
    if record is not None:
        return record
    created_at = _utc_now()
    context = _reflection_context(session_id)
    authored = _authored_cards(created_at, session_id, context)
    deck = {
        "schemaVersion": 1,
        "sessionId": session_id,
        "deckVersion": DECK_VERSION,
        "createdAt": created_at,
        "cards": _reflection_model_cards(created_at, session_id, context, authored),
        "languageLearning": context.get("languageLearning"),
    }
    if (
        _run_reflection_bridge("validate-cards", {"cards": deck["cards"]}, "valid")
        is not True
    ):
        raise ReflectionConversionRejected(
            "Authored reflection deck failed shared validation"
        )
    if len(_canonical(deck).encode("utf-8")) > MAX_DECK_BYTES:
        raise ValueError("Authored reflection deck exceeds its storage limit")
    record = FutureReflectionDeckRecord(
        session_id=session_id,
        deck_version=DECK_VERSION,
        deck_json=deck,
        deck_hash=_hash(deck),
        created_at=created_at,
    )
    db.session.add(record)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = db.session.get(FutureReflectionDeckRecord, session_id)
        if existing is None:
            raise
        return existing
    return record


def _finished_session(session_id):
    session = db.session.get(PersonalSolveSession, session_id)
    if session is None:
        return None, None, _error("Session not found", 404)
    if session.status != "finished":
        return (
            None,
            None,
            _error("Reflections are available after the session is finished", 409),
        )
    analysis = db.session.get(FutureSolveAnalysisRecord, session_id)
    if (
        analysis is None
        or not analysis.finalized
        or analysis.puzzle_hash != session.puzzle_hash
    ):
        return None, None, _error("Host replay is not finalized for this session", 409)
    if db.session.get(StartingProfile, session.profile_id) is None:
        return None, None, _error("Session profile not found", 404)
    return session, analysis, None


def _node_path():
    return shutil.which("node")


def _run_reflection_bridge(operation, payload, result_key):
    node = _node_path()
    if not node or not BRIDGE_SCRIPT.is_file():
        raise ReflectionRuntimeUnavailable(
            "The local reflection converter is unavailable"
        )
    serialized = json.dumps(
        {"operation": operation, **payload},
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    if len(serialized.encode("utf-8")) > MAX_DECK_BYTES:
        raise ReflectionConversionRejected(
            "Reflection evidence exceeds the conversion limit"
        )
    try:
        result = subprocess.run(
            [node, str(BRIDGE_SCRIPT)],
            input=serialized,
            text=True,
            capture_output=True,
            timeout=5,
            cwd=PROJECT_ROOT,
            env={"PATH": os.environ.get("PATH", "")},
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ReflectionRuntimeUnavailable(
            "The local reflection converter did not respond"
        ) from error
    if result.returncode != 0:
        try:
            payload = json.loads(result.stderr)
        except (ValueError, AttributeError):
            raise ReflectionRuntimeUnavailable(
                "The local reflection converter could not start"
            ) from None
        message = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(message, str):
            raise ReflectionRuntimeUnavailable(
                "The local reflection converter could not start"
            )
        raise ReflectionConversionRejected(message[:240])
    try:
        value = json.loads(result.stdout)[result_key]
    except (ValueError, KeyError, TypeError) as error:
        raise ReflectionRuntimeUnavailable(
            "The local reflection converter returned invalid output"
        ) from error
    return value


def convert_response_to_evidence(card, response):
    """Use the shared TypeScript domain conversion as the evidence trust gate."""
    return _run_reflection_bridge(
        "convert-response", {"card": card, "response": response}, "evidence"
    )


def convert_action_to_evidence_action(action):
    """Use the shared TypeScript domain conversion for an immutable correction."""
    return _run_reflection_bridge("convert-action", {"action": action}, "action")


def validate_authored_cards(cards):
    """Validate authored card contracts against the same shared domain types."""
    return _run_reflection_bridge("validate-cards", {"cards": cards}, "valid") is True


def _apply_reflection_update_with_cas_retry(
    profile_id,
    created_at,
    update_id,
    recorded_at,
    evidence,
    evidence_actions,
    before_apply=None,
):
    """Retry only stale-revision conflicts using one stable idempotency key."""
    for attempt in range(MAX_EPISTEME_CAS_ATTEMPTS):
        profile = get_or_create_episteme_profile(profile_id, created_at)
        if before_apply is not None:
            before_apply()
        command = {
            "updateId": update_id,
            "profileId": profile_id,
            "baseRevision": profile.revision,
            "recordedAt": recorded_at,
            "evidence": evidence,
            "evidenceActions": evidence_actions,
        }
        try:
            return apply_episteme_command(
                profile_id,
                profile.revision,
                profile.profile_json,
                command,
            )
        except EpistemeRevisionConflict as error:
            db.session.rollback()
            if (
                not str(error).startswith("Stale profile revision")
                or attempt + 1 == MAX_EPISTEME_CAS_ATTEMPTS
            ):
                raise
    raise EpistemeRevisionConflict("Stale profile revision: retry limit reached")


def _response_body(value, session_id, deck):
    required = {
        "schemaVersion",
        "responseId",
        "sessionId",
        "cardId",
        "cardVersion",
        "shownPosition",
        "recordedAt",
        "response",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("Reflection response does not match the exact schema")
    if (
        value["schemaVersion"] != 1
        or not _valid_uuid(value["responseId"])
        or value["sessionId"] != session_id
        or type(value["cardVersion"]) is not int
        or type(value["shownPosition"]) is not int
        or value["shownPosition"] not in (0, 1, 2)
        or value["response"] not in {"keep", "not-for-me", "pass"}
        or not isinstance(value["recordedAt"], str)
        or len(value["recordedAt"]) > 40
    ):
        raise ValueError("Invalid reflection response fields")
    try:
        parsed = datetime.fromisoformat(value["recordedAt"].replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Invalid reflection response timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError("Reflection response timestamp requires a timezone")
    cards = deck["cards"]
    position = value["shownPosition"]
    card = cards[position]
    if value["cardId"] != card["cardId"] or value["cardVersion"] != card["version"]:
        raise ValueError(
            "Response card, version, and shown position must match the frozen deck"
        )
    return value, card


def _response_result(record, *, replayed):
    return jsonify(
        response=record.response_json,
        evidence=record.evidence_json,
        revision=record.episteme_revision,
        replayed=replayed,
    )


def _action_result(record, *, replayed):
    return jsonify(
        action=record.action_json,
        evidenceAction=record.evidence_action_json,
        revision=record.episteme_revision,
        replayed=replayed,
    )


def _saved_response_state(session_id, deck):
    responses = (
        db.session.query(FutureReflectionResponseRecord)
        .filter_by(session_id=session_id, status="complete")
        .all()
    )
    by_card = {record.card_id: record for record in responses}
    values = []
    for card in deck["cards"]:
        saved = by_card.get(card["cardId"])
        if saved is None:
            continue
        actions = (
            db.session.query(FutureReflectionActionRecord)
            .filter_by(
                session_id=session_id,
                card_id=card["cardId"],
                target_response_id=saved.response_id,
                status="complete",
            )
            .all()
        )
        actions.sort(key=lambda item: (item.recorded_at, item.action_id))
        latest_action = actions[-1].action_json if actions else None
        values.append(
            {
                "response": saved.response_json,
                "evidence": saved.evidence_json,
                "epistemeRevision": saved.episteme_revision,
                "state": "retracted"
                if latest_action and latest_action["action"] == "retract"
                else "active",
                "latestAction": latest_action,
                "latestActionEpistemeRevision": (
                    actions[-1].episteme_revision if actions else None
                ),
                "actions": [item.action_json for item in actions],
            }
        )
    return values


def _action_body(value, session_id, response_id):
    required = {"schemaVersion", "actionId", "targetResponseId", "recordedAt", "action"}
    optional = {"reason"}
    if (
        not isinstance(value, dict)
        or not required.issubset(value)
        or set(value) - required - optional
    ):
        raise ValueError("Reflection action does not match the exact schema")
    if (
        type(value["schemaVersion"]) is not int
        or value["schemaVersion"] != 1
        or not _valid_uuid(value["actionId"])
        or value["targetResponseId"] != response_id
        or value["action"] not in {"retract", "restore"}
        or not isinstance(value["recordedAt"], str)
        or len(value["recordedAt"]) > 40
        or not _REFLECTION_TIMESTAMP.fullmatch(value["recordedAt"])
        or (
            "reason" in value
            and (
                not isinstance(value["reason"], str)
                or not value["reason"].strip()
                or len(value["reason"]) > 240
            )
        )
    ):
        raise ValueError("Invalid reflection action fields")
    try:
        parsed = datetime.fromisoformat(value["recordedAt"].replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Invalid reflection action timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError("Reflection action timestamp requires a timezone")
    if not _valid_uuid(session_id):
        raise ValueError("Invalid session id")
    return value


def _utc_after(previous):
    now = datetime.now(timezone.utc)
    prior = None
    if previous:
        prior = datetime.fromisoformat(previous.replace("Z", "+00:00"))
        if now <= prior:
            now = prior + timedelta(milliseconds=1)
        # Keep the predecessor's zone so the reducer's stable lexical
        # timestamp ordering agrees with this host-authored chronology.
        now = now.astimezone(prior.tzinfo)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _action_order(item):
    parsed = datetime.fromisoformat(item["recordedAt"].replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc), item["actionId"]


def _reflection_action_history(session_id, response_id, profile_id):
    """Merge host reservations with reducer actions, deduplicated by action id."""
    profile = db.session.get(EpistemeProfileRecord, profile_id)
    ledger_actions = []
    if profile is not None:
        ledger_actions = [
            item
            for item in profile.profile_json.get("evidenceActions", [])
            if item.get("targetEvidenceId") == response_id
        ]
    reservations = (
        db.session.query(FutureReflectionActionRecord)
        .filter_by(
            session_id=session_id,
            target_response_id=response_id,
        )
        .all()
    )
    by_action_id = {item["actionId"]: item for item in ledger_actions}
    for reservation in reservations:
        item = reservation.evidence_action_json or {
            "actionId": reservation.action_id,
            "recordedAt": reservation.action_json["recordedAt"],
            "targetEvidenceId": response_id,
            "action": reservation.action_json["action"],
            **(
                {"reason": reservation.action_json["reason"]}
                if "reason" in reservation.action_json
                else {}
            ),
        }
        try:
            if not _REFLECTION_TIMESTAMP.fullmatch(item["recordedAt"]):
                continue
            _action_order(item)
        except (AttributeError, KeyError, TypeError, ValueError):
            # Ignore pre-validation pending rows left by older hosts. They
            # never reached the reducer and cannot define the response state.
            continue
        # The reducer is authoritative if the action has already committed.
        by_action_id.setdefault(item["actionId"], item)
    return sorted(by_action_id.values(), key=_action_order)


def _validate_reflection_action_transition(
    session_id, response_id, profile_id, action, *, action_id=None, candidate=None
):
    profile = db.session.get(EpistemeProfileRecord, profile_id)
    ledger_actions = (
        profile.profile_json.get("evidenceActions", []) if profile is not None else []
    )
    if action_id is not None:
        committed = next(
            (
                item
                for item in ledger_actions
                if item.get("targetEvidenceId") == response_id
                and item.get("actionId") == action_id
            ),
            None,
        )
        if committed is not None:
            if candidate is not None and _canonical(committed) == _canonical(candidate):
                return
            raise ValueError(
                "Action id was already used with different episteme evidence"
            )

    history = _reflection_action_history(session_id, response_id, profile_id)
    if action_id is not None and candidate is not None:
        reserved = next(
            (item for item in history if item["actionId"] == action_id), None
        )
        if reserved is not None:
            if _canonical(reserved) != _canonical(candidate):
                raise ValueError(
                    "Action id was already used with different episteme evidence"
                )
            predecessors = [
                item
                for item in history
                if _action_order(item) < _action_order(reserved)
            ]
            previous = predecessors[-1] if predecessors else None
            expected = (
                "restore" if previous and previous["action"] == "retract" else "retract"
            )
            if reserved["action"] != expected:
                raise ValueError(f"This response can only be {expected} next")
            return

    previous = history[-1] if history else None
    expected = "restore" if previous and previous["action"] == "retract" else "retract"
    if action != expected:
        raise ValueError(f"This response can only be {expected} next")


def _next_reflection_action_time(session_id, response_id, profile_id):
    history = _reflection_action_history(session_id, response_id, profile_id)
    return _utc_after(history[-1]["recordedAt"] if history else None)


def _repairable_legacy_action(
    action_record, request_action, session_id, card_id, response_id, profile_id
):
    """Allow the corrected retry of an old invalid reservation, exactly once."""
    if (
        action_record.status != "pending"
        or action_record.evidence_action_json is not None
        or action_record.session_id != session_id
        or action_record.card_id != card_id
        or action_record.target_response_id != response_id
    ):
        return False
    prior = action_record.action_json
    if not isinstance(prior, dict) or not isinstance(prior.get("recordedAt"), str):
        return False
    if _REFLECTION_TIMESTAMP.fullmatch(prior["recordedAt"]):
        return False
    try:
        legacy_time = datetime.fromisoformat(prior["recordedAt"].replace("Z", "+00:00"))
    except ValueError:
        return False
    if legacy_time.tzinfo is None:
        return False
    if {key: value for key, value in prior.items() if key != "recordedAt"} != {
        key: value for key, value in request_action.items() if key != "recordedAt"
    }:
        return False
    profile = db.session.get(EpistemeProfileRecord, profile_id)
    if profile is None:
        return True
    if any(
        item.get("actionId") == action_record.action_id
        and item.get("targetEvidenceId") == response_id
        for item in profile.profile_json.get("evidenceActions", [])
    ):
        return False
    update_id = str(
        uuid5(
            NAMESPACE_URL,
            f"crossword-reflection-action:{session_id}:{action_record.action_id}:v1",
        )
    )
    return not any(
        item.get("updateId") == update_id
        for item in profile.profile_json.get("updates", [])
    )


@reflection_api.get("/api/future/sessions/<session_id>/reflections")
def get_reflections(session_id):
    if not _valid_uuid(session_id):
        return _error("Invalid session id", 400)
    _, analysis, error = _finished_session(session_id)
    if error:
        return error
    try:
        record = _create_deck(session_id)
    except ReflectionRuntimeUnavailable:
        db.session.rollback()
        return _error("The local reflection validator is unavailable", 503)
    except ValueError as error:
        db.session.rollback()
        return _error(str(error), 500)
    if not hmac.compare_digest(record.deck_hash, _hash(record.deck_json)):
        return _error("Stored reflection deck integrity check failed", 500)
    response = jsonify(
        deck=record.deck_json,
        responses=_saved_response_state(session_id, record.deck_json),
        analysisSummary=_analysis_summary(analysis.analysis_json),
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@reflection_api.get("/api/future/profile/<profile_id>/history")
def get_profile_game_history(profile_id):
    """Return a bounded, answer-free timeline for the owning local profile."""
    if not _valid_uuid(profile_id):
        return _error("Invalid profile id", 400)
    if db.session.get(StartingProfile, profile_id) is None:
        return _error("Profile not found", 404)
    limit = _history_limit(request.args.get("limit"))
    if limit is None:
        return _error("History limit must be between 1 and 50", 400)
    history = _profile_game_history(profile_id, limit)
    calibration = _profile_calibration_report(history, limit=limit)
    calibration["profileId"] = profile_id
    response = jsonify(
        profileId=profile_id,
        limit=limit,
        history=history,
        calibration=calibration,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@reflection_api.get("/api/future/profile/<profile_id>/calibration-export")
def export_profile_calibration(profile_id):
    """Download recent play signals without puzzle content or profile prose."""
    if not _valid_uuid(profile_id):
        return _error("Invalid profile id", 400)
    if db.session.get(StartingProfile, profile_id) is None:
        return _error("Profile not found", 404)
    limit = _history_limit(request.args.get("limit", "50"))
    if limit is None:
        return _error("Calibration export limit must be between 1 and 50", 400)
    payload = _profile_calibration_export(profile_id, limit=limit)
    response = jsonify(payload)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="personal-calibration-{profile_id}.json"'
    )
    return response


@reflection_api.post("/api/future/sessions/<session_id>/reflections/<card_id>/response")
def post_reflection_response(session_id, card_id):
    if not _same_origin():
        return _error("Same-origin reflection writes are required", 403)
    if not _valid_uuid(session_id):
        return _error("Invalid session id", 400)
    request.max_content_length = MAX_BODY_BYTES
    if (request.content_length or 0) > MAX_BODY_BYTES:
        return _error("Reflection response is too large", 413)
    try:
        body = request.get_data(cache=True)
    except RequestEntityTooLarge:
        return _error("Reflection response is too large", 413)
    if len(body) > MAX_BODY_BYTES:
        return _error("Reflection response is too large", 413)
    value = request.get_json(silent=True)
    session, _, error = _finished_session(session_id)
    if error:
        return error
    deck_record = db.session.get(FutureReflectionDeckRecord, session_id)
    if deck_record is None or not hmac.compare_digest(
        deck_record.deck_hash, _hash(deck_record.deck_json)
    ):
        return _error("Reflection deck has not been issued for this session", 409)
    if card_id not in CARD_IDS:
        return _error("Unknown reflection card", 404)
    try:
        response_value, card = _response_body(value, session_id, deck_record.deck_json)
    except (ValueError, TypeError, KeyError, IndexError) as error:
        return _error(str(error), 422)
    if card_id != card["cardId"]:
        return _error("URL card does not match the response position", 422)
    response_digest = _hash(response_value)
    existing_by_id = db.session.get(
        FutureReflectionResponseRecord, response_value["responseId"]
    )
    existing_by_card = (
        db.session.query(FutureReflectionResponseRecord)
        .filter_by(session_id=session_id, card_id=card_id)
        .first()
    )
    existing = existing_by_id or existing_by_card
    if existing is not None:
        if existing.response_hash != response_digest:
            return _error(
                "A different response already exists for this card or response id", 409
            )
        if existing.status == "complete":
            response = _response_result(existing, replayed=True)
            response.headers["Cache-Control"] = "no-store"
            return response
    try:
        # Run the strict shared TypeScript contract before creating the durable
        # per-card reservation. Python's ISO parser accepts forms (for example
        # a space instead of `T`) that the domain intentionally rejects; a bad
        # request must not permanently occupy this card's unique slot.
        evidence = convert_response_to_evidence(card, response_value)
    except ReflectionRuntimeUnavailable:
        db.session.rollback()
        return _error("The local reflection converter is unavailable", 503)
    except ReflectionConversionRejected as error:
        db.session.rollback()
        return _error(str(error), 422)
    if existing is None:
        # Reserve the response identity before touching the episteme. This
        # makes two different swipes for one card serialize on the unique
        # (session, card) constraint. A pending reservation is safe to replay
        # after a process interruption because the reducer update ID is stable.
        existing = FutureReflectionResponseRecord(
            response_id=response_value["responseId"],
            session_id=session_id,
            card_id=card_id,
            response_hash=response_digest,
            response_json=response_value,
            evidence_json=None,
            episteme_revision=None,
            status="pending",
            recorded_at=response_value["recordedAt"],
        )
        db.session.add(existing)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            existing = db.session.get(
                FutureReflectionResponseRecord, response_value["responseId"]
            )
            if existing is None:
                existing = (
                    db.session.query(FutureReflectionResponseRecord)
                    .filter_by(session_id=session_id, card_id=card_id)
                    .first()
                )
            if existing is None or existing.response_hash != response_digest:
                return _error("A different response won the card response race", 409)
            if existing.status == "complete":
                response = _response_result(existing, replayed=True)
                response.headers["Cache-Control"] = "no-store"
                return response
    try:
        result, _ = _apply_reflection_update_with_cas_retry(
            session.profile_id,
            session.created_at,
            str(
                uuid5(
                    NAMESPACE_URL,
                    f"crossword-reflection-response:{session_id}:{response_value['responseId']}:v1",
                )
            ),
            response_value["recordedAt"],
            [evidence],
            [],
        )
        updated_profile = result["profile"]
        if episteme_profile_size(updated_profile) > MAX_PROFILE_BYTES:
            raise EpistemeCommandRejected("Episteme profile exceeds the storage limit")
    except EpistemeRuntimeUnavailable:
        db.session.rollback()
        return _error("The local profile reducer is unavailable", 503)
    except EpistemeRevisionConflict as error:
        db.session.rollback()
        return _error(str(error), 409)
    except EpistemeCommandRejected as error:
        db.session.rollback()
        return _error(str(error), 422)

    existing.evidence_json = evidence
    existing.episteme_revision = updated_profile["revision"]
    existing.status = "complete"
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        winner = db.session.get(
            FutureReflectionResponseRecord, response_value["responseId"]
        )
        if (
            winner is None
            or winner.response_hash != response_digest
            or winner.status != "complete"
        ):
            return _error("The response could not be committed", 409)
        existing = winner
        replayed = True
    else:
        replayed = bool(result.get("replayed"))
    response = _response_result(existing, replayed=replayed)
    response.headers["Cache-Control"] = "no-store"
    return response


@reflection_api.post(
    "/api/future/sessions/<session_id>/reflections/<card_id>/responses/<response_id>/actions"
)
def post_reflection_action(session_id, card_id, response_id):
    if not _same_origin():
        return _error("Same-origin reflection writes are required", 403)
    if not _valid_uuid(session_id) or not _valid_uuid(response_id):
        return _error("Invalid session or response id", 400)
    request.max_content_length = MAX_BODY_BYTES
    if (request.content_length or 0) > MAX_BODY_BYTES:
        return _error("Reflection action is too large", 413)
    try:
        body = request.get_data(cache=True)
    except RequestEntityTooLarge:
        return _error("Reflection action is too large", 413)
    if len(body) > MAX_BODY_BYTES:
        return _error("Reflection action is too large", 413)
    value = request.get_json(silent=True)
    session, _, error = _finished_session(session_id)
    if error:
        return error
    response_record = db.session.get(FutureReflectionResponseRecord, response_id)
    if (
        response_record is None
        or response_record.session_id != session_id
        or response_record.card_id != card_id
        or response_record.status != "complete"
    ):
        return _error("Saved response not found for this session and card", 404)
    try:
        action_value = _action_body(value, session_id, response_id)
    except (ValueError, TypeError, KeyError) as error:
        return _error(str(error), 422)
    request_action = action_value
    action_digest = _hash(request_action)
    action_record = db.session.get(
        FutureReflectionActionRecord, request_action["actionId"]
    )
    if action_record is not None:
        if action_record.action_hash != action_digest:
            if not _repairable_legacy_action(
                action_record,
                request_action,
                session_id,
                card_id,
                response_id,
                session.profile_id,
            ):
                return _error("Action id was reused with different evidence", 409)
            # Older hosts reserved the ID before the shared converter rejected
            # a noncanonical timestamp. Repair only that uncommitted malformed
            # reservation, after validating the corrected request fully.
            try:
                client_evidence_action = convert_action_to_evidence_action(
                    request_action
                )
            except ReflectionRuntimeUnavailable:
                return _error("The local reflection converter is unavailable", 503)
            except ReflectionConversionRejected as error:
                return _error(str(error), 422)
            try:
                _validate_reflection_action_transition(
                    session_id,
                    response_id,
                    session.profile_id,
                    request_action["action"],
                )
            except ValueError as error:
                return _error(str(error), 409)
            recorded_at = _next_reflection_action_time(
                session_id, response_id, session.profile_id
            )
            action_value = {**request_action, "recordedAt": recorded_at}
            evidence_action = {**client_evidence_action, "recordedAt": recorded_at}
            action_record.action_hash = action_digest
            action_record.action_json = action_value
            action_record.evidence_action_json = evidence_action
            action_record.recorded_at = recorded_at
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                return _error(
                    "The corrected pending action could not be recovered", 409
                )
        if action_record.status == "complete":
            response = _action_result(action_record, replayed=True)
            response.headers["Cache-Control"] = "no-store"
            return response
        # A pending reservation owns its original host timestamp. Reusing it
        # also makes recovery deterministic if the reducer committed but the
        # final receipt status did not.
        action_value = action_record.action_json
        try:
            evidence_action = convert_action_to_evidence_action(action_value)
        except ReflectionRuntimeUnavailable:
            return _error("The local reflection converter is unavailable", 503)
        except ReflectionConversionRejected as error:
            return _error(str(error), 422)
    else:
        # The shared domain converter is the trust gate and must run before an
        # ID is reserved. The client timestamp is validated as part of this
        # contract, then replaced for host ordering below.
        try:
            client_evidence_action = convert_action_to_evidence_action(request_action)
        except ReflectionRuntimeUnavailable:
            return _error("The local reflection converter is unavailable", 503)
        except ReflectionConversionRejected as error:
            return _error(str(error), 422)
        try:
            _validate_reflection_action_transition(
                session_id,
                response_id,
                session.profile_id,
                request_action["action"],
            )
        except ValueError as error:
            return _error(str(error), 409)
        recorded_at = _next_reflection_action_time(
            session_id, response_id, session.profile_id
        )
        action_value = {**request_action, "recordedAt": recorded_at}
        evidence_action = {**client_evidence_action, "recordedAt": recorded_at}
        action_record = FutureReflectionActionRecord(
            action_id=request_action["actionId"],
            session_id=session_id,
            card_id=card_id,
            target_response_id=response_id,
            action_hash=action_digest,
            action_json=action_value,
            evidence_action_json=evidence_action,
            episteme_revision=None,
            status="pending",
            recorded_at=recorded_at,
        )
        db.session.add(action_record)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            action_record = db.session.get(
                FutureReflectionActionRecord, request_action["actionId"]
            )
            if action_record is None or action_record.action_hash != action_digest:
                return _error("A conflicting action won the retry race", 409)
            if action_record.status == "complete":
                response = _action_result(action_record, replayed=True)
                response.headers["Cache-Control"] = "no-store"
                return response
            action_value = action_record.action_json
            try:
                evidence_action = convert_action_to_evidence_action(action_value)
            except ReflectionRuntimeUnavailable:
                return _error("The local reflection converter is unavailable", 503)
            except ReflectionConversionRejected as error:
                return _error(str(error), 422)

    def transition_gate():
        _validate_reflection_action_transition(
            session_id,
            response_id,
            session.profile_id,
            action_value["action"],
            action_id=action_value["actionId"],
            candidate=evidence_action,
        )

    try:
        transition_gate()
        update_id = str(
            uuid5(
                NAMESPACE_URL,
                f"crossword-reflection-action:{session_id}:{action_value['actionId']}:v1",
            )
        )
        profile_record = db.session.get(EpistemeProfileRecord, session.profile_id)
        committed_update = bool(
            profile_record
            and any(
                item.get("updateId") == update_id
                for item in profile_record.profile_json.get("updates", [])
            )
        )
        if committed_update:
            result = {"profile": profile_record.profile_json, "replayed": True}
        else:
            result, _ = _apply_reflection_update_with_cas_retry(
                session.profile_id,
                session.created_at,
                update_id,
                action_value["recordedAt"],
                [],
                [evidence_action],
                before_apply=transition_gate,
            )
        updated_profile = result["profile"]
        if episteme_profile_size(updated_profile) > MAX_PROFILE_BYTES:
            raise EpistemeCommandRejected("Episteme profile exceeds the storage limit")
    except EpistemeRuntimeUnavailable:
        db.session.rollback()
        return _error("The local profile reducer is unavailable", 503)
    except EpistemeRevisionConflict as error:
        db.session.rollback()
        return _error(str(error), 409)
    except EpistemeCommandRejected as error:
        db.session.rollback()
        return _error(str(error), 422)
    except ValueError as error:
        db.session.rollback()
        return _error(str(error), 409)

    action_record.evidence_action_json = evidence_action
    action_record.episteme_revision = updated_profile["revision"]
    action_record.status = "complete"
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        winner = db.session.get(FutureReflectionActionRecord, action_value["actionId"])
        if (
            winner is None
            or winner.action_hash != action_digest
            or winner.status != "complete"
        ):
            return _error("The reflection action could not be committed", 409)
        action_record = winner
        replayed = True
    else:
        replayed = bool(result.get("replayed"))
    response = _action_result(action_record, replayed=replayed)
    response.headers["Cache-Control"] = "no-store"
    return response
