"""Synthetic language-pair fixtures for the private delayed-recall lane.

This is deliberately smaller and weaker than an admitted language-content
pack.  It exists so the local future review path has a stable task-pair
contract to exercise source cues, target forms, and grammar metadata.  The
records are locally authored fixtures; ``contentClass=synthetic`` and
``admissionStatus=unadmitted`` are part of the contract and must remain
visible to callers.  No record here establishes a fact, native-speaker
review, or vocabulary mastery.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata
from typing import Any, Mapping


LANGUAGE_TASK_PACK_SCHEMA_VERSION = "language-task-pairs-v1"
LANGUAGE_TASK_PACK_ID = "synthetic-local-language-pairs-v1"
LANGUAGE_TASK_PACK_STATUS = "synthetic-unadmitted"
LANGUAGE_TASK_SOURCE_ID = "synthetic-local-language-source-v1"
LANGUAGE_TASK_GRAMMAR_VERSION = "language-task-grammar-v1"
REVIEWED_LANGUAGE_TASK_PACK_STATUS = "reviewed-admitted"
REVIEWED_LANGUAGE_TASK_PACK_ENV = "CROSSWORD_REVIEWED_LANGUAGE_TASK_PACK"
REVIEWED_LANGUAGE_TASK_PACK_MAX_BYTES = 512 * 1024
_SUPPORTED_LANGUAGES = frozenset({"de", "es", "fr", "it", "ja", "nl", "pt"})
_LANGUAGE_CODE_ALIASES = {
    "german": "de",
    "deutsch": "de",
    "spanish": "es",
    "español": "es",
    "french": "fr",
    "français": "fr",
    "italian": "it",
    "italiano": "it",
    "portuguese": "pt",
    "português": "pt",
    "japanese": "ja",
    "dutch": "nl",
    "nederlands": "nl",
}
_REQUIRED_PAIR_KEYS = frozenset(
    {
        "pairId",
        "language",
        "sourceLanguage",
        "sourceText",
        "targetText",
        "direction",
        "source",
        "grammar",
        "reviewStatus",
    }
)
_REVIEWED_PAIR_KEYS = _REQUIRED_PAIR_KEYS | {"displayText"}
_SINGLE_CELL_DISPLAY_ALIASES = {
    "fr": {"À": "A", "Â": "A", "Ç": "C", "É": "E", "È": "E", "Ê": "E", "Ë": "E", "Î": "I", "Ï": "I", "Ô": "O", "Ù": "U", "Û": "U", "Ü": "U", "Ÿ": "Y"},
    "es": {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U", "Ñ": "N"},
    "it": {"À": "A", "È": "E", "É": "E", "Ì": "I", "Ò": "O", "Ù": "U"},
    "pt": {"Á": "A", "Â": "A", "Ã": "A", "À": "A", "Ç": "C", "É": "E", "Ê": "E", "Í": "I", "Ó": "O", "Ô": "O", "Õ": "O", "Ú": "U", "Ü": "U"},
}
# A deliberately tiny local display layer lets the private experimental path
# demonstrate explicit one-cell accents even when no external reviewed pack is
# configured. These are display spellings only; the corresponding task pairs
# remain synthetic and unadmitted, so callers must retain that uncertainty.
_SYNTHETIC_DISPLAY_TEXT = {
    ("fr", "CAFE"): "CAFÉ",
}
_REVIEWED_SOURCE_KEYS = frozenset(
    {
        "sourceId",
        "version",
        "contentClass",
        "admissionStatus",
        "attribution",
        "semanticStatus",
        "artifactSha256",
        "license",
        "reviewerId",
        "reviewedAt",
    }
)


class LanguageTaskPackError(ValueError):
    """The local synthetic task-pair pack is malformed or inconsistent."""


@dataclass(frozen=True)
class LanguageTaskPair:
    """One source-cue/target-form fixture in the private review lane."""

    pair_id: str
    language: str
    source_language: str
    source_text: str
    target_text: str
    direction: str
    source: Mapping[str, Any]
    grammar: Mapping[str, Any]
    review_status: str = LANGUAGE_TASK_PACK_STATUS

    def as_record(self) -> dict[str, Any]:
        return {
            "pairId": self.pair_id,
            "language": self.language,
            "sourceLanguage": self.source_language,
            "sourceText": self.source_text,
            "targetText": self.target_text,
            "direction": self.direction,
            "source": deepcopy(dict(self.source)),
            "grammar": deepcopy(dict(self.grammar)),
            "reviewStatus": self.review_status,
        }


_SOURCE_METADATA = {
    "sourceId": LANGUAGE_TASK_SOURCE_ID,
    "version": "fixture-2026-09-27",
    "contentClass": "synthetic",
    "admissionStatus": "unadmitted",
    "attribution": "Locally authored fixture for private contract tests",
    "semanticStatus": "not-established",
}


def _grammar(part_of_speech: str, *, number: str = "invariant") -> dict[str, str]:
    return {
        "version": LANGUAGE_TASK_GRAMMAR_VERSION,
        "partOfSpeech": part_of_speech,
        "number": number,
        "inflection": "fixture-metadata-only",
        "semanticStatus": "not-established",
    }


# These are intentionally familiar, compact forms so the delayed-review
# contract can be exercised without importing a public or licensed corpus.
# Their presence is not an assertion that the translations or grammar have
# been independently reviewed.
_LANGUAGE_TASK_PAIRS = (
    LanguageTaskPair(
        "nl-en-ja-v1",
        "nl",
        "en",
        "yes",
        "JA",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("interjection"),
    ),
    LanguageTaskPair(
        "nl-en-huis-v1",
        "nl",
        "en",
        "house",
        "HUIS",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("noun", number="singular"),
    ),
    LanguageTaskPair(
        "nl-en-water-v1",
        "nl",
        "en",
        "water",
        "WATER",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("noun", number="mass"),
    ),
    LanguageTaskPair(
        "de-en-ja-v1",
        "de",
        "en",
        "yes",
        "JA",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("interjection"),
    ),
    LanguageTaskPair(
        "de-en-haus-v1",
        "de",
        "en",
        "house",
        "HAUS",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("noun", number="singular"),
    ),
    LanguageTaskPair(
        "de-en-wasser-v1",
        "de",
        "en",
        "water",
        "WASSER",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("noun", number="mass"),
    ),
    LanguageTaskPair(
        "fr-en-oui-v1",
        "fr",
        "en",
        "yes",
        "OUI",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("interjection"),
    ),
    LanguageTaskPair(
        "fr-en-chat-v1",
        "fr",
        "en",
        "cat",
        "CHAT",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("noun", number="singular"),
    ),
    LanguageTaskPair(
        "fr-en-eau-v1",
        "fr",
        "en",
        "water",
        "EAU",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("noun", number="mass"),
    ),
    LanguageTaskPair(
        "fr-en-cafe-v1",
        "fr",
        "en",
        "coffee",
        "CAFE",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("noun", number="mass"),
    ),
    LanguageTaskPair(
        "es-en-si-v1",
        "es",
        "en",
        "yes",
        "SI",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("interjection"),
    ),
    LanguageTaskPair(
        "es-en-casa-v1",
        "es",
        "en",
        "house",
        "CASA",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("noun", number="singular"),
    ),
    LanguageTaskPair(
        "es-en-agua-v1",
        "es",
        "en",
        "water",
        "AGUA",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("noun", number="mass"),
    ),
    LanguageTaskPair(
        "it-en-si-v1",
        "it",
        "en",
        "yes",
        "SI",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("interjection"),
    ),
    LanguageTaskPair(
        "it-en-casa-v1",
        "it",
        "en",
        "house",
        "CASA",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("noun", number="singular"),
    ),
    LanguageTaskPair(
        "it-en-acqua-v1",
        "it",
        "en",
        "water",
        "ACQUA",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("noun", number="mass"),
    ),
    LanguageTaskPair(
        "pt-en-sim-v1",
        "pt",
        "en",
        "yes",
        "SIM",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("interjection"),
    ),
    LanguageTaskPair(
        "pt-en-casa-v1",
        "pt",
        "en",
        "house",
        "CASA",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("noun", number="singular"),
    ),
    LanguageTaskPair(
        "pt-en-agua-v1",
        "pt",
        "en",
        "water",
        "AGUA",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("noun", number="mass"),
    ),
    LanguageTaskPair(
        "ja-en-hai-v1",
        "ja",
        "en",
        "yes",
        "HAI",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("interjection"),
    ),
    LanguageTaskPair(
        "ja-en-neko-v1",
        "ja",
        "en",
        "cat",
        "NEKO",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("noun", number="singular"),
    ),
    LanguageTaskPair(
        "ja-en-mizu-v1",
        "ja",
        "en",
        "water",
        "MIZU",
        "source-to-target",
        _SOURCE_METADATA,
        _grammar("noun", number="mass"),
    ),
)


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise LanguageTaskPackError("task-pack-not-canonicalizable") from error


def _digest(pack_without_digest: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(pack_without_digest)).hexdigest()


def _pack_without_digest() -> dict[str, Any]:
    return {
        "schemaVersion": LANGUAGE_TASK_PACK_SCHEMA_VERSION,
        "packId": LANGUAGE_TASK_PACK_ID,
        "status": LANGUAGE_TASK_PACK_STATUS,
        "sourceId": LANGUAGE_TASK_SOURCE_ID,
        "grammarVersion": LANGUAGE_TASK_GRAMMAR_VERSION,
        "pairs": [pair.as_record() for pair in _LANGUAGE_TASK_PAIRS],
    }


def build_synthetic_language_task_pack() -> dict[str, Any]:
    """Return a fresh, deterministic copy of the local fixture pack."""
    pack = _pack_without_digest()
    pack["packDigest"] = _digest(pack)
    return pack


SYNTHETIC_LANGUAGE_TASK_PACK = build_synthetic_language_task_pack()


def _nonempty_text(value: Any, maximum: int = 200) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _validate_pair(pair: Any, *, source_id: str) -> dict[str, Any]:
    if not isinstance(pair, dict) or set(pair) != _REQUIRED_PAIR_KEYS:
        raise LanguageTaskPackError("task-pair-shape-invalid")
    for field in ("pairId", "sourceLanguage", "sourceText", "targetText", "direction"):
        if not _nonempty_text(pair.get(field)):
            raise LanguageTaskPackError(f"task-pair-{field}-invalid")
    language = pair.get("language")
    if language not in _SUPPORTED_LANGUAGES:
        raise LanguageTaskPackError("task-pair-language-unsupported")
    if pair["sourceLanguage"] != "en" or pair["direction"] != "source-to-target":
        raise LanguageTaskPackError("task-pair-direction-invalid")
    if pair["targetText"] != unicodedata.normalize("NFC", pair["targetText"]).upper():
        raise LanguageTaskPackError("task-pair-target-not-canonical")
    if not isinstance(pair["source"], dict):
        raise LanguageTaskPackError("task-pair-source-invalid")
    source = pair["source"]
    if set(source) != set(_SOURCE_METADATA):
        raise LanguageTaskPackError("task-pair-source-shape-invalid")
    if source.get("sourceId") != source_id:
        raise LanguageTaskPackError("task-pair-source-id-mismatch")
    if source.get("contentClass") != "synthetic":
        raise LanguageTaskPackError("task-pair-source-not-synthetic")
    if source.get("admissionStatus") != "unadmitted":
        raise LanguageTaskPackError("task-pair-source-admission-invalid")
    if source.get("semanticStatus") != "not-established":
        raise LanguageTaskPackError("task-pair-source-semantic-status-invalid")
    grammar = pair["grammar"]
    if not isinstance(grammar, dict):
        raise LanguageTaskPackError("task-pair-grammar-invalid")
    expected_grammar_keys = {
        "version",
        "partOfSpeech",
        "number",
        "inflection",
        "semanticStatus",
    }
    if set(grammar) != expected_grammar_keys:
        raise LanguageTaskPackError("task-pair-grammar-shape-invalid")
    if grammar.get("version") != LANGUAGE_TASK_GRAMMAR_VERSION:
        raise LanguageTaskPackError("task-pair-grammar-version-invalid")
    if grammar.get("semanticStatus") != "not-established":
        raise LanguageTaskPackError("task-pair-grammar-semantic-status-invalid")
    if not all(
        _nonempty_text(grammar.get(key), 80)
        for key in ("partOfSpeech", "number", "inflection")
    ):
        raise LanguageTaskPackError("task-pair-grammar-field-invalid")
    if pair.get("reviewStatus") != LANGUAGE_TASK_PACK_STATUS:
        raise LanguageTaskPackError("task-pair-review-status-invalid")
    return pair


def validate_language_task_pack(pack: Any) -> dict[str, Any]:
    """Validate the complete deterministic pack and return a deep copy.

    This validator checks contract integrity and explicit synthetic/unadmitted
    boundaries.  It is not semantic, native-speaker, source, or mastery
    validation.
    """
    if not isinstance(pack, dict):
        raise LanguageTaskPackError("task-pack-not-object")
    expected_keys = {
        "schemaVersion",
        "packId",
        "status",
        "sourceId",
        "grammarVersion",
        "pairs",
        "packDigest",
    }
    if set(pack) != expected_keys:
        raise LanguageTaskPackError("task-pack-envelope-shape-invalid")
    if pack.get("schemaVersion") != LANGUAGE_TASK_PACK_SCHEMA_VERSION:
        raise LanguageTaskPackError("task-pack-version-invalid")
    if pack.get("packId") != LANGUAGE_TASK_PACK_ID:
        raise LanguageTaskPackError("task-pack-id-invalid")
    if pack.get("status") != LANGUAGE_TASK_PACK_STATUS:
        raise LanguageTaskPackError("task-pack-status-invalid")
    if pack.get("sourceId") != LANGUAGE_TASK_SOURCE_ID:
        raise LanguageTaskPackError("task-pack-source-id-invalid")
    if pack.get("grammarVersion") != LANGUAGE_TASK_GRAMMAR_VERSION:
        raise LanguageTaskPackError("task-pack-grammar-version-invalid")
    pairs = pack.get("pairs")
    if not isinstance(pairs, list) or not pairs or len(pairs) > 24:
        raise LanguageTaskPackError("task-pack-pairs-invalid")
    pair_ids: set[str] = set()
    language_counts = {language: 0 for language in _SUPPORTED_LANGUAGES}
    normalized_pairs = []
    for pair in pairs:
        pair = _validate_pair(pair, source_id=pack["sourceId"])
        if pair["pairId"] in pair_ids:
            raise LanguageTaskPackError("task-pair-id-duplicate")
        pair_ids.add(pair["pairId"])
        language_counts[pair["language"]] += 1
        normalized_pairs.append(deepcopy(pair))
    if any(count == 0 for count in language_counts.values()):
        raise LanguageTaskPackError("task-pack-language-missing")
    without_digest = deepcopy(pack)
    without_digest.pop("packDigest")
    if pack["packDigest"] != _digest(without_digest):
        raise LanguageTaskPackError("task-pack-digest-mismatch")
    result = deepcopy(pack)
    result["pairs"] = normalized_pairs
    return result


def task_pair_for_review(language: str, target_text: str) -> dict[str, Any] | None:
    """Return answer-free metadata for one private delayed-recall item."""
    if not isinstance(language, str) or not isinstance(target_text, str):
        return None
    raw_code = language.strip().casefold()
    code = _LANGUAGE_CODE_ALIASES.get(raw_code, raw_code)
    canonical_target = unicodedata.normalize("NFC", target_text).upper()
    try:
        validated = load_reviewed_language_task_pack()
    except LanguageTaskPackError:
        # A configured pack is optional. An invalid one must never become a
        # source of review metadata, so private play falls back to the
        # explicitly labelled synthetic fixture instead.
        validated = None
    if validated is None:
        validated = validate_language_task_pack(SYNTHETIC_LANGUAGE_TASK_PACK)
    pair = next(
        (
            candidate
            for candidate in validated["pairs"]
            if candidate["language"] == code
            and candidate["targetText"] == canonical_target
        ),
        None,
    )
    if pair is None:
        return None
    # Do not pass targetText to the due queue.  The answer endpoint still uses
    # the existing opaque source task handle when the player requests it.
    return {
        "packId": validated["packId"],
        "packVersion": validated["schemaVersion"],
        "packDigest": validated["packDigest"],
        "pairId": pair["pairId"],
        "sourceLanguage": pair["sourceLanguage"],
        "targetLanguage": pair["language"],
        "sourceText": pair["sourceText"],
        "direction": pair["direction"],
        "source": deepcopy(pair["source"]),
        "grammar": deepcopy(pair["grammar"]),
        "reviewStatus": pair["reviewStatus"],
        "semanticStatus": (
            "reviewed"
            if validated["status"] == REVIEWED_LANGUAGE_TASK_PACK_STATUS
            else "not-established"
        ),
        "masteryClaim": "none",
    }


def reviewed_display_text_for_review(language: str, target_text: str) -> str | None:
    """Return an explicit one-cell display spelling from the reviewed pack.

    This stays separate from ``task_pair_for_review`` so due-card metadata
    remains answer-free. It is called only after a generated board has an
    exact canonical answer and can therefore emit token hints without
    guessing accents or rebus geometry.
    """
    try:
        validated = load_reviewed_language_task_pack()
    except LanguageTaskPackError:
        return None
    if validated is None:
        return None
    raw_code = language.strip().casefold() if isinstance(language, str) else ""
    code = _LANGUAGE_CODE_ALIASES.get(raw_code, raw_code)
    canonical_target = (
        unicodedata.normalize("NFC", target_text).upper()
        if isinstance(target_text, str)
        else ""
    )
    pair = next(
        (
            candidate
            for candidate in validated["pairs"]
            if candidate["language"] == code
            and candidate["targetText"] == canonical_target
        ),
        None,
    )
    display = pair.get("displayText") if isinstance(pair, dict) else None
    return display if isinstance(display, str) else None


def private_display_text_for_review(
    language: str, target_text: str
) -> tuple[str | None, str | None]:
    """Return a display spelling plus its local provenance class.

    A configured reviewed pack wins. With no valid reviewed pack, a tiny
    synthetic map keeps the private language lane usable while making the
    unadmitted boundary explicit to generation provenance and the UI.
    """
    raw_code = language.strip().casefold() if isinstance(language, str) else ""
    code = _LANGUAGE_CODE_ALIASES.get(raw_code, raw_code)
    canonical_target = (
        unicodedata.normalize("NFC", target_text).upper()
        if isinstance(target_text, str)
        else ""
    )
    try:
        reviewed_pack = load_reviewed_language_task_pack()
    except LanguageTaskPackError:
        reviewed_pack = None
    if reviewed_pack is not None:
        display = reviewed_display_text_for_review(code, canonical_target)
        return (display, "reviewed-admitted") if display else (None, None)
    display = _SYNTHETIC_DISPLAY_TEXT.get((code, canonical_target))
    return (display, "synthetic-unadmitted") if display else (None, None)


def single_cell_fill_token(language: str, display_token: str) -> str | None:
    """Return the canonical A-Z fill for one explicit display grapheme.

    The private token decorator is deliberately limited to one geometric cell.
    It may use a reviewed or synthetic display spelling, but it must never
    guess a multi-unit expansion such as ``ß`` → ``SS``. The explicit alias
    table remains the authority; a decomposed accent is accepted only when it
    reduces to exactly one ASCII letter.
    """
    raw_code = language.strip().casefold() if isinstance(language, str) else ""
    code = _LANGUAGE_CODE_ALIASES.get(raw_code, raw_code)
    if not isinstance(display_token, str):
        return None
    normalized = unicodedata.normalize("NFC", display_token).upper()
    if len(normalized) != 1:
        return None
    if "A" <= normalized <= "Z":
        return normalized
    explicit = _SINGLE_CELL_DISPLAY_ALIASES.get(code, {}).get(normalized)
    if explicit:
        return explicit
    decomposed = unicodedata.normalize("NFD", normalized)
    base = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return base if len(base) == 1 and "A" <= base <= "Z" else None


def _validate_reviewed_pair(pair: Any, *, source_id: str) -> dict[str, Any]:
    """Validate one externally supplied, already-admitted task pair.

    This is a provenance gate, not a translation or native-speaker judge. The
    caller must provide an artifact hash, license/admission marker, reviewer
    identity, and review timestamp; the loader merely refuses malformed or
    incomplete records.
    """
    if not isinstance(pair, dict) or set(pair) != _REVIEWED_PAIR_KEYS:
        raise LanguageTaskPackError("reviewed-task-pair-shape-invalid")
    for field in ("pairId", "sourceLanguage", "sourceText", "targetText", "direction"):
        if not _nonempty_text(pair.get(field)):
            raise LanguageTaskPackError(f"reviewed-task-pair-{field}-invalid")
    language = pair.get("language")
    if language not in _SUPPORTED_LANGUAGES:
        raise LanguageTaskPackError("reviewed-task-pair-language-unsupported")
    if pair["sourceLanguage"] != "en" or pair["direction"] != "source-to-target":
        raise LanguageTaskPackError("reviewed-task-pair-direction-invalid")
    if pair["targetText"] != unicodedata.normalize("NFC", pair["targetText"]).upper():
        raise LanguageTaskPackError("reviewed-task-pair-target-not-canonical")
    display_text = pair.get("displayText")
    if not _nonempty_text(display_text, 200):
        raise LanguageTaskPackError("reviewed-task-pair-display-invalid")
    display_text = unicodedata.normalize("NFC", display_text).upper()
    aliases = _SINGLE_CELL_DISPLAY_ALIASES.get(language, {})
    display_fill = "".join(
        character if "A" <= character <= "Z" else aliases.get(character, "")
        for character in display_text
    )
    if not display_fill or display_fill != pair["targetText"]:
        raise LanguageTaskPackError("reviewed-task-pair-display-fill-mismatch")
    pair["displayText"] = display_text
    source = pair.get("source")
    if not isinstance(source, dict) or set(source) != _REVIEWED_SOURCE_KEYS:
        raise LanguageTaskPackError("reviewed-task-pair-source-shape-invalid")
    if source.get("sourceId") != source_id:
        raise LanguageTaskPackError("reviewed-task-pair-source-id-mismatch")
    if source.get("contentClass") != "reviewed":
        raise LanguageTaskPackError("reviewed-task-pair-source-class-invalid")
    if source.get("admissionStatus") != "admitted":
        raise LanguageTaskPackError("reviewed-task-pair-source-admission-invalid")
    if source.get("semanticStatus") != "reviewed":
        raise LanguageTaskPackError("reviewed-task-pair-source-semantic-status-invalid")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", str(source.get("artifactSha256", ""))):
        raise LanguageTaskPackError("reviewed-task-pair-artifact-digest-invalid")
    for field in ("version", "attribution", "license", "reviewerId", "reviewedAt"):
        if not _nonempty_text(source.get(field), 240):
            raise LanguageTaskPackError(f"reviewed-task-pair-source-{field}-invalid")
    if not _valid_timestamp(source["reviewedAt"]):
        raise LanguageTaskPackError("reviewed-task-pair-source-reviewedAt-invalid")
    grammar = pair.get("grammar")
    if not isinstance(grammar, dict):
        raise LanguageTaskPackError("reviewed-task-pair-grammar-invalid")
    if set(grammar) != {
        "version",
        "partOfSpeech",
        "number",
        "inflection",
        "semanticStatus",
    }:
        raise LanguageTaskPackError("reviewed-task-pair-grammar-shape-invalid")
    if grammar.get("version") != LANGUAGE_TASK_GRAMMAR_VERSION:
        raise LanguageTaskPackError("reviewed-task-pair-grammar-version-invalid")
    if grammar.get("semanticStatus") != "reviewed":
        raise LanguageTaskPackError("reviewed-task-pair-grammar-semantic-status-invalid")
    if not all(
        _nonempty_text(grammar.get(key), 80)
        for key in ("partOfSpeech", "number", "inflection")
    ):
        raise LanguageTaskPackError("reviewed-task-pair-grammar-field-invalid")
    if pair.get("reviewStatus") != REVIEWED_LANGUAGE_TASK_PACK_STATUS:
        raise LanguageTaskPackError("reviewed-task-pair-review-status-invalid")
    return deepcopy(pair)


def validate_reviewed_language_task_pack(pack: Any) -> dict[str, Any]:
    """Validate a local reviewed language pack without trusting its claims.

    The pack is intentionally separate from the bundled synthetic fixture. A
    valid result means the supplied provenance envelope is complete and its
    digest matches; it does not independently prove translation quality.
    """
    if not isinstance(pack, dict):
        raise LanguageTaskPackError("reviewed-task-pack-not-object")
    expected_keys = {
        "schemaVersion",
        "packId",
        "status",
        "sourceId",
        "grammarVersion",
        "pairs",
        "packDigest",
    }
    if set(pack) != expected_keys:
        raise LanguageTaskPackError("reviewed-task-pack-envelope-shape-invalid")
    if pack.get("schemaVersion") != LANGUAGE_TASK_PACK_SCHEMA_VERSION:
        raise LanguageTaskPackError("reviewed-task-pack-version-invalid")
    if not _nonempty_text(pack.get("packId"), 160) or pack.get("packId") == LANGUAGE_TASK_PACK_ID:
        raise LanguageTaskPackError("reviewed-task-pack-id-invalid")
    if pack.get("status") != REVIEWED_LANGUAGE_TASK_PACK_STATUS:
        raise LanguageTaskPackError("reviewed-task-pack-status-invalid")
    if not _nonempty_text(pack.get("sourceId"), 160):
        raise LanguageTaskPackError("reviewed-task-pack-source-id-invalid")
    if pack.get("grammarVersion") != LANGUAGE_TASK_GRAMMAR_VERSION:
        raise LanguageTaskPackError("reviewed-task-pack-grammar-version-invalid")
    pairs = pack.get("pairs")
    if not isinstance(pairs, list) or not pairs or len(pairs) > 200:
        raise LanguageTaskPackError("reviewed-task-pack-pairs-invalid")
    pair_ids: set[str] = set()
    languages: set[str] = set()
    normalized_pairs = []
    for pair in pairs:
        pair = _validate_reviewed_pair(pair, source_id=pack["sourceId"])
        if pair["pairId"] in pair_ids:
            raise LanguageTaskPackError("reviewed-task-pair-id-duplicate")
        pair_ids.add(pair["pairId"])
        languages.add(pair["language"])
        normalized_pairs.append(pair)
    if not languages:
        raise LanguageTaskPackError("reviewed-task-pack-language-missing")
    without_digest = deepcopy(pack)
    without_digest.pop("packDigest")
    if pack.get("packDigest") != _digest(without_digest):
        raise LanguageTaskPackError("reviewed-task-pack-digest-mismatch")
    result = deepcopy(pack)
    result["pairs"] = normalized_pairs
    return result


def load_reviewed_language_task_pack(path: str | os.PathLike[str] | None = None) -> dict[str, Any] | None:
    """Load the optional reviewed pack configured for this local host.

    Missing configuration is normal and returns ``None``. Once a path is
    configured, malformed JSON, oversized files, or an invalid provenance
    envelope raise ``LanguageTaskPackError`` so callers can fail closed.
    """
    raw_path = path if path is not None else os.environ.get(REVIEWED_LANGUAGE_TASK_PACK_ENV)
    if raw_path is None or not str(raw_path).strip():
        return None
    candidate = Path(raw_path).expanduser()
    try:
        size = candidate.stat().st_size
    except OSError as error:
        raise LanguageTaskPackError("reviewed-task-pack-unavailable") from error
    if size <= 0 or size > REVIEWED_LANGUAGE_TASK_PACK_MAX_BYTES:
        raise LanguageTaskPackError("reviewed-task-pack-size-invalid")
    try:
        value = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise LanguageTaskPackError("reviewed-task-pack-json-invalid") from error
    return validate_reviewed_language_task_pack(value)


def language_task_pack_summary() -> dict[str, Any]:
    """Return bounded provenance for the pack currently used by review.

    The summary is safe to expose to the local UI: it contains no target
    answers and distinguishes absent/invalid configuration from an admitted
    pack. Invalid configuration deliberately reports the synthetic fallback
    rather than pretending the broken pack was accepted.
    """
    configured = os.environ.get(REVIEWED_LANGUAGE_TASK_PACK_ENV)
    if configured and configured.strip():
        try:
            pack = load_reviewed_language_task_pack(configured)
        except LanguageTaskPackError as error:
            return {
                "packId": LANGUAGE_TASK_PACK_ID,
                "status": LANGUAGE_TASK_PACK_STATUS,
                "packDigest": SYNTHETIC_LANGUAGE_TASK_PACK["packDigest"],
                "sourceId": LANGUAGE_TASK_SOURCE_ID,
                "languages": sorted(_SUPPORTED_LANGUAGES),
                "configuration": "invalid-fell-back-to-synthetic",
                "error": str(error),
                "uncertainty": "synthetic-unadmitted-not-established",
            }
        if pack is not None:
            return {
                "packId": pack["packId"],
                "status": pack["status"],
                "packDigest": pack["packDigest"],
                "sourceId": pack["sourceId"],
                "languages": sorted({pair["language"] for pair in pack["pairs"]}),
                "configuration": "configured",
                "uncertainty": "source-receipt-present-semantic-quality-not-independently-proven",
            }
    return {
        "packId": LANGUAGE_TASK_PACK_ID,
        "status": LANGUAGE_TASK_PACK_STATUS,
        "packDigest": SYNTHETIC_LANGUAGE_TASK_PACK["packDigest"],
        "sourceId": LANGUAGE_TASK_SOURCE_ID,
        "languages": sorted(_SUPPORTED_LANGUAGES),
        "configuration": "default-synthetic",
        "uncertainty": "synthetic-unadmitted-not-established",
    }


# Validate the bundled fixture at import time so a locally edited record cannot
# silently enter the delayed-review path with a different schema or digest.
validate_language_task_pack(SYNTHETIC_LANGUAGE_TASK_PACK)
