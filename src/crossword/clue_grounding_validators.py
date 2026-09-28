"""Bounded deterministic validators for the safest private clue surfaces.

The private clue writer has no reviewed sense ledger.  A few clue families do
have a small, literal witness that can be checked without pretending to prove
the whole clue: an anagram's source letters, a reversal's source letters, or a
supported ``yes`` translation.  This module records those witnesses as typed
spans and reports the narrow comparison result.

These records are diagnostic provenance.  They never establish a semantic
sense or factual truth, and an unavailable/failed check is handled by the
existing answer-free private fallback rather than by blocking local play.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


CLUE_GROUNDING_VALIDATORS_VERSION = "private-clue-grounding-validators-v1"

_ANAGRAM_RE = re.compile(
    r"\b(?:anagram|scramble|mixed[- ]up letters?)\s+of\s+[\"'“‘]?([A-Za-z]+)",
    re.IGNORECASE,
)
_REVERSE_RE = re.compile(
    r"[\"'“‘]?([A-Za-z]+)[\"'”’]?\s+(?:spelled|written)\s+"
    r"(?:backward|backwards|in reverse)|\b(?:reverse|backward|backwards)\s+of\s+"
    r"[\"'“‘]?([A-Za-z]+)",
    re.IGNORECASE,
)
_HIDDEN_RE = re.compile(
    r"\b(?:hidden|found|inside)\s+in\s+[\"“‘]([^\"”’\n]{2,96})[\"”’]",
    re.IGNORECASE,
)
_LANGUAGE_RE = re.compile(
    r"\b(Dutch|French|German|Italian|Portuguese|Spanish|Japanese)\b",
    re.IGNORECASE,
)
_TRANSLATION_TARGET_RE = re.compile(r"\b(yes|affirmative)\b", re.IGNORECASE)

# This deliberately remains the small set already supported by the private
# mechanical guard.  It is a comparison table, not a claim that every model
# translation is covered or that the answer is editorially fair.
_LANGUAGE_YES = {
    "dutch": {"JA"},
    "french": {"OUI"},
    "german": {"JA"},
    "italian": {"SI"},
    "japanese": {"HAI"},
    "portuguese": {"SIM"},
    "spanish": {"SI"},
}


def _letters_only(value: Any) -> str:
    return re.sub(r"[^A-Z]", "", str(value).upper())


def _span(
    span_id: str,
    kind: str,
    start: int,
    end: int,
    text: str,
    role: str,
    **extra: Any,
) -> dict[str, Any]:
    """Create a typed literal span with offsets into the stripped clue."""

    result: dict[str, Any] = {
        "id": span_id,
        "kind": kind,
        "start": start,
        "end": end,
        "text": text[start:end],
        "role": role,
    }
    result.update(extra)
    return result


def _validator_base(kind: str, status: str, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "version": CLUE_GROUNDING_VALIDATORS_VERSION,
        "kind": kind,
        "status": status,
        "semanticStatus": "not-established",
        "truth": "not-established",
        "uncertainty": [
            "semantic-sense-unverified",
            "factual-support-unverified",
        ],
    }
    result.update(extra)
    return result


def _mechanical_validator(
    *,
    kind: str,
    match: re.Match[str],
    source: str,
    answer: str,
    source_start: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized_source = _letters_only(source)
    if kind == "anagram":
        passes = bool(answer) and sorted(normalized_source) == sorted(answer)
        relation = "multiset-equality"
    elif kind == "reversal":
        passes = bool(answer) and normalized_source[::-1] == answer
        relation = "reverse-string"
    else:
        passes = bool(answer) and answer in normalized_source
        relation = "contiguous-substring"
    indicator_start = match.start()
    indicator_end = match.end()
    spans = [
        _span(
            f"{kind}-indicator-1",
            "mechanic-indicator",
            indicator_start,
            indicator_end,
            match.string,
            "mechanic-signal",
            mechanic=kind,
        ),
        _span(
            f"{kind}-input-1",
            "mechanic-input",
            source_start,
            source_start + len(source),
            match.string,
            "source-letters",
            mechanic=kind,
        ),
    ]
    validator = _validator_base(
        kind,
        "passed" if passes else "failed",
        comparison=relation,
        sourceLength=len(normalized_source),
        answerLength=len(answer) if answer else None,
        sourceShape="letters-only" if normalized_source else "unknown",
        answerShape="letters-only" if answer else "unknown",
        observedInput=normalized_source,
    )
    return spans, validator


def validate_private_clue_witnesses(entry: Any, clue: Any) -> dict[str, Any]:
    """Return typed spans and bounded validators for one private clue.

    ``status=not-observed`` is intentionally explicit when no supported
    witness occurs.  The output is safe to persist beside the existing
    ``semanticStatus=not-established`` bundle because it contains only
    literal clue text and narrow mechanical comparisons.
    """

    text = clue.strip() if isinstance(clue, str) else ""
    answer = (
        _letters_only(entry.get("answer", "")) if isinstance(entry, Mapping) else ""
    )
    spans: list[dict[str, Any]] = []
    validators: dict[str, dict[str, Any]] = {}

    anagram = _ANAGRAM_RE.search(text)
    if anagram:
        source = next((group for group in anagram.groups() if group), "")
        source_start = anagram.start(1) if anagram.group(1) else anagram.start(2)
        mechanical_spans, validator = _mechanical_validator(
            kind="anagram",
            match=anagram,
            source=source,
            answer=answer,
            source_start=source_start,
        )
        spans.extend(mechanical_spans)
        validators["anagram"] = validator

    reversal = _REVERSE_RE.search(text)
    if reversal:
        source = next((group for group in reversal.groups() if group), "")
        source_index = next(
            index for index, group in enumerate(reversal.groups(), start=1) if group
        )
        source_start = reversal.start(source_index)
        mechanical_spans, validator = _mechanical_validator(
            kind="reversal",
            match=reversal,
            source=source,
            answer=answer,
            source_start=source_start,
        )
        spans.extend(mechanical_spans)
        validators["reversal"] = validator

    hidden = _HIDDEN_RE.search(text)
    if hidden:
        source = hidden.group(1)
        mechanical_spans, validator = _mechanical_validator(
            kind="hidden-word",
            match=hidden,
            source=source,
            answer=answer,
            source_start=hidden.start(1),
        )
        spans.extend(mechanical_spans)
        validators["hidden-word"] = validator

    language = _LANGUAGE_RE.search(text)
    if language:
        spans.append(
            _span(
                "language-indicator-1",
                "language-indicator",
                language.start(),
                language.end(),
                text,
                "translation-language",
                language=language.group(1).casefold(),
            )
        )
        target = _TRANSLATION_TARGET_RE.search(text, language.end())
        if target:
            spans.append(
                _span(
                    "translation-target-1",
                    "translation-target",
                    target.start(),
                    target.end(),
                    text,
                    "source-sense-token",
                    token=target.group(1).casefold(),
                )
            )
            expected = _LANGUAGE_YES.get(language.group(1).casefold())
            if expected is None:
                validators["language-translation"] = _validator_base(
                    "language-translation",
                    "unsupported-language",
                    language=language.group(1).casefold(),
                    target=target.group(1).casefold(),
                )
            else:
                validators["language-translation"] = _validator_base(
                    "language-translation",
                    "passed" if answer in expected else "failed",
                    comparison="small-local-translation-map",
                    language=language.group(1).casefold(),
                    target=target.group(1).casefold(),
                    answerLength=len(answer) if answer else None,
                    expectedAnswerCount=len(expected),
                )
        else:
            validators["language-translation"] = _validator_base(
                "language-translation",
                "not-observed",
                language=language.group(1).casefold(),
                reason="no-supported-translation-target",
            )

    if not validators:
        status = "not-observed"
    elif any(item["status"] == "failed" for item in validators.values()):
        status = "failed"
    elif any(item["status"] == "passed" for item in validators.values()):
        status = "passed"
    else:
        status = "unresolved"
    return {
        "version": CLUE_GROUNDING_VALIDATORS_VERSION,
        "status": status,
        "typedSpans": spans,
        "validators": validators,
        "semanticStatus": "not-established",
        "uncertainty": [
            "semantic-sense-unverified",
            "factual-support-unverified",
        ],
    }
