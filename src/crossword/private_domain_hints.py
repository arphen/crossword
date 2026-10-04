"""Bounded local domain hints for private puzzle generation.

This is deliberately separate from the admitted lexicon-pack path.  A player
may point a local install at a small hand-curated list to invite a subject into
private generation, but the list is never treated as a source of meaning,
truth, licensing, or publication eligibility.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


PRIVATE_DOMAIN_HINTS_VERSION = "private-domain-hints-v1"
PRIVATE_DOMAIN_HINTS_ENV = "CROSSWORD_PRIVATE_DOMAIN_HINTS"
MAX_DOMAIN_HINT_BYTES = 64 * 1024
MAX_DOMAIN_HINT_TERMS = 96
MAX_DOMAIN_ID_LENGTH = 64
MAX_DOMAIN_LABEL_LENGTH = 120
_DOMAIN_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_ANSWER = re.compile(r"^[A-Z]{3,15}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PrivateDomainHintsError(ValueError):
    """The optional private hint file is malformed or exceeds its bounds."""


class _DuplicateKey(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateKey(key)
        value[key] = item
    return value


def _reject_constant(_value: str) -> None:
    raise ValueError("non-json constant")


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise PrivateDomainHintsError("domain-hints-not-canonical-json") from error


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "version": PRIVATE_DOMAIN_HINTS_VERSION,
        "status": "unavailable",
        "reason": reason,
        "terms": [],
        "placeableTerms": [],
        "semanticStatus": "not-established",
        "admissionStatus": "private-unadmitted",
        "uncertainty": [
            "local-hint-file-unreviewed",
            "semantic-sense-unverified",
            "factual-support-unverified",
        ],
    }


def _validate_source(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {
        "id",
        "version",
        "artifactSha256",
    }:
        raise PrivateDomainHintsError("source-metadata-invalid")
    source_id = value.get("id")
    version = value.get("version")
    digest = value.get("artifactSha256")
    if (
        not isinstance(source_id, str)
        or not source_id.strip()
        or len(source_id) > 200
        or not isinstance(version, str)
        or not version.strip()
        or len(version) > 100
        or not isinstance(digest, str)
        or _SHA256.fullmatch(digest) is None
    ):
        raise PrivateDomainHintsError("source-metadata-invalid")
    return {
        "id": source_id.strip(),
        "version": version.strip(),
        "artifactSha256": digest,
    }


def _validate_document(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PrivateDomainHintsError("document-not-object")
    if set(value) - {"version", "domainId", "label", "terms", "source"}:
        raise PrivateDomainHintsError("document-unknown-field")
    if value.get("version") != PRIVATE_DOMAIN_HINTS_VERSION:
        raise PrivateDomainHintsError("document-version-unsupported")
    domain_id = value.get("domainId")
    if (
        not isinstance(domain_id, str)
        or _DOMAIN_ID.fullmatch(domain_id) is None
        or len(domain_id) > MAX_DOMAIN_ID_LENGTH
    ):
        raise PrivateDomainHintsError("domain-id-invalid")
    label = value.get("label")
    if (
        not isinstance(label, str)
        or not label.strip()
        or len(label.strip()) > MAX_DOMAIN_LABEL_LENGTH
    ):
        raise PrivateDomainHintsError("domain-label-invalid")
    terms = value.get("terms")
    if not isinstance(terms, list) or not 1 <= len(terms) <= MAX_DOMAIN_HINT_TERMS:
        raise PrivateDomainHintsError("domain-terms-invalid")
    normalized: list[str] = []
    for term in terms:
        if not isinstance(term, str):
            raise PrivateDomainHintsError("domain-term-invalid")
        answer = term.strip().upper()
        if not _ANSWER.fullmatch(answer) or len(answer) == 12:
            raise PrivateDomainHintsError("domain-term-shape-invalid")
        if answer in normalized:
            raise PrivateDomainHintsError("domain-term-duplicate")
        normalized.append(answer)
    source = _validate_source(value.get("source"))
    return {
        "version": PRIVATE_DOMAIN_HINTS_VERSION,
        "domainId": domain_id,
        "label": label.strip(),
        "terms": sorted(normalized),
        **({"source": source} if source is not None else {}),
    }


def load_private_domain_hints(
    *,
    path: str | os.PathLike[str] | None = None,
    fill_words: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Load an optional local hint file and return a bounded model receipt.

    Missing configuration is normal.  Any configured-file failure is reported
    as unavailable and never falls back to a guessed or bundled domain list.
    ``fill_words`` is an optional host view of the exact native xfill vocabulary;
    when supplied, only placeable terms are offered as theme candidates.
    """

    configured = path if path is not None else os.environ.get(PRIVATE_DOMAIN_HINTS_ENV)
    if not isinstance(configured, (str, os.PathLike)) or not str(configured).strip():
        return {
            "version": PRIVATE_DOMAIN_HINTS_VERSION,
            "status": "not-configured",
            "terms": [],
            "placeableTerms": [],
            "semanticStatus": "not-established",
            "admissionStatus": "private-unadmitted",
            "uncertainty": ["local-hint-file-not-configured"],
        }
    try:
        source_path = Path(configured)
        with source_path.open("rb") as handle:
            raw = handle.read(MAX_DOMAIN_HINT_BYTES + 1)
        if len(raw) > MAX_DOMAIN_HINT_BYTES:
            raise PrivateDomainHintsError("document-size-limit-exceeded")
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        document = _validate_document(parsed)
    except (OSError, UnicodeError, json.JSONDecodeError, PrivateDomainHintsError, RecursionError, _DuplicateKey) as error:
        reason = str(error) if isinstance(error, PrivateDomainHintsError) else "document-unreadable"
        return _unavailable(reason)

    available = (
        {
            str(item).upper()
            for item in fill_words
            if isinstance(item, str) and _ANSWER.fullmatch(item.upper())
        }
        if fill_words is not None
        else None
    )
    terms = list(document["terms"])
    placeable = (
        list(terms)
        if available is None
        else [term for term in terms if term in available]
    )
    raw_digest = _digest(raw)
    result = {
        **document,
        "status": "loaded",
        "artifactSha256": raw_digest,
        "placeableTerms": placeable,
        "semanticStatus": "not-established",
        "admissionStatus": "private-unadmitted",
        "uncertainty": [
            "local-hint-file-unreviewed",
            "semantic-sense-unverified",
            "factual-support-unverified",
        ],
    }
    return result


def private_domain_hint_receipt(value: Any) -> dict[str, Any]:
    """Project a hint load into answer-free provenance."""

    if not isinstance(value, Mapping):
        return {"version": PRIVATE_DOMAIN_HINTS_VERSION, "status": "not-configured"}
    result: dict[str, Any] = {
        "version": PRIVATE_DOMAIN_HINTS_VERSION,
        "status": value.get("status", "not-configured"),
        "semanticStatus": "not-established",
        "admissionStatus": "private-unadmitted",
        "termCount": len(value.get("terms", [])) if isinstance(value.get("terms"), list) else 0,
        "placeableCount": len(value.get("placeableTerms", [])) if isinstance(value.get("placeableTerms"), list) else 0,
        "uncertainty": ["local-hint-file-unreviewed", "semantic-sense-unverified"],
    }
    for key in ("domainId", "label", "artifactSha256", "reason"):
        if isinstance(value.get(key), str):
            result[key] = value[key]
    source = value.get("source")
    if isinstance(source, Mapping):
        result["source"] = {
            key: source[key]
            for key in ("id", "version", "artifactSha256")
            if isinstance(source.get(key), str)
        }
    return result
