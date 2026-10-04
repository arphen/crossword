"""Resolve trusted, admitted lexicon packs into episteme-brief candidates.

This is a read-only boundary. A pack's self-hash is an integrity check, not an
authenticity claim, so callers must pin the expected pack digest and the exact
source IDs, versions, and artifact digests out of band. This module never
turns raw fill vocabulary into admitted content and never invents profile or
evidence links.

The pack builder preserves optional, explicitly reviewed ``personalization``
metadata. Each lexeme may include the narrow object documented by
:func:`_personalization`; absent metadata always maps to a broad candidate with
empty links.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any, Mapping

from tools.lexicon.pack_builder import ALLOWED_SPDX, _run_clue_grammar


PACK_SCHEMA_VERSION = "lexicon-pack-admission-v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_PACK_RECORDS = 100_000
_MAX_PACK_BYTES = 64 * 1024 * 1024
_MAX_TEXT = 500
_MAX_ID = 200
_MAX_SOURCE_IDS = 8
_MAX_LINK_IDS = 32


class AdmittedPackError(ValueError):
    """The supplied artifact is not the exact trusted, internally valid pack."""


@dataclass(frozen=True)
class SourcePin:
    """Out-of-band source identity expected by this resolver deployment."""

    version: str
    artifact_sha256: str
    content_class: str


@dataclass(frozen=True)
class AdmittedSenseContent:
    """A reviewed sense projected for downstream clue construction."""

    sense_id: str
    gloss: str | None
    resolution_status: str
    clue_eligible: bool
    fill_only: bool
    provenance: Mapping[str, Any]


@dataclass(frozen=True)
class AdmittedFactContent:
    """A reviewed fact projected with its original evidence provenance."""

    fact_id: str
    statement: str
    provenance: Mapping[str, Any]


@dataclass(frozen=True)
class AdmittedClueContent:
    """A reviewed clue with validated grammar and exact evidence links."""

    clue_id: str
    text: str
    answer_lexeme_id: str
    evidence_type: str
    evidence_id: str
    grammar: Mapping[str, Any]
    provenance: Mapping[str, Any]


@dataclass(frozen=True)
class AdmittedLexemeContent:
    """Allowlisted content and reviewed child records for one answer."""

    lexeme_id: str
    answer: str
    language: str
    provenance: Mapping[str, Any]
    senses: tuple[AdmittedSenseContent, ...]
    facts: tuple[AdmittedFactContent, ...]
    clues: tuple[AdmittedClueContent, ...]
    concept_ids: tuple[str, ...] = ()
    knowledge_task_ids: tuple[str, ...] = ()
    association_ids: tuple[str, ...] = ()
    pool: str = "broad"


@dataclass(frozen=True)
class AdmittedPackContent:
    """Immutable, provenance-preserving content from one pinned pack."""

    pack_id: str
    pack_sha256: str
    lexemes: tuple[AdmittedLexemeContent, ...]


def canonical_json(value: Any) -> bytes:
    """Match the pack builder's canonical UTF-8 JSON representation."""

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError) as error:
        raise AdmittedPackError("pack-json-not-canonicalizable") from error


def _is_record(value: Any) -> bool:
    return isinstance(value, dict)


def _text(value: Any, *, maximum: int = _MAX_TEXT) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def _id(value: Any) -> bool:
    return _text(value, maximum=_MAX_ID)


def _digest(value: Any) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _unique_text_list(value: Any, *, maximum: int, required: bool = False) -> bool:
    return (
        isinstance(value, list)
        and len(value) <= maximum
        and (not required or bool(value))
        and all(_text(item, maximum=_MAX_ID) for item in value)
        and len(value) == len(set(value))
    )


def _source_projection(source: Any) -> dict[str, Any]:
    if not _is_record(source):
        raise AdmittedPackError("source-record-invalid")
    expected_keys = {"sourceId", "version", "artifactSha256", "spdx", "attribution", "contentClass"}
    if set(source) != expected_keys:
        raise AdmittedPackError("source-projection-shape-invalid")
    if not _id(source.get("sourceId")) or not _text(source.get("version"), maximum=_MAX_ID):
        raise AdmittedPackError("source-identity-invalid")
    if not _digest(source.get("artifactSha256")):
        raise AdmittedPackError("source-artifact-digest-invalid")
    spdx = source.get("spdx")
    if not isinstance(spdx, str) or spdx not in ALLOWED_SPDX:
        raise AdmittedPackError("source-license-invalid")
    if not _text(source.get("attribution")):
        raise AdmittedPackError("source-attribution-missing")
    content_class = source.get("contentClass")
    if not isinstance(content_class, str) or content_class not in {"public", "synthetic"}:
        raise AdmittedPackError("source-content-class-invalid")
    return source


def _reviewed_provenance(value: Any, source_by_id: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    if not _is_record(value) or set(value) != {"source", "evidenceRefs", "reviewerId", "reviewedAt"}:
        raise AdmittedPackError("record-provenance-shape-invalid")
    source = _source_projection(value.get("source"))
    if source["sourceId"] not in source_by_id or source_by_id[source["sourceId"]] != source:
        raise AdmittedPackError("record-source-reference-invalid")
    if not _unique_text_list(value.get("evidenceRefs"), maximum=256, required=True):
        raise AdmittedPackError("record-evidence-references-invalid")
    if not _text(value.get("reviewerId"), maximum=200):
        raise AdmittedPackError("record-reviewer-invalid")
    reviewed_at = value.get("reviewedAt")
    if not isinstance(reviewed_at, str):
        raise AdmittedPackError("record-review-date-invalid")
    try:
        if date.fromisoformat(reviewed_at).isoformat() != reviewed_at:
            raise ValueError
    except ValueError as error:
        raise AdmittedPackError("record-review-date-invalid") from error
    return value


def _personalization(value: Any) -> tuple[list[str], list[str], list[str], str]:
    """Read only explicit ID links; no prose-to-profile mapping is attempted.

    The optional pack field is ``personalization`` with only ``conceptIds``,
    ``knowledgeTaskIds``, ``associationIds`` and optional ``pool``. Each ID
    list is a reviewed link to an existing episteme identity. The default pool
    is broad; an exploration lane must be explicitly marked in the pack.
    """

    if value is None:
        return [], [], [], "broad"
    if not _is_record(value):
        raise AdmittedPackError("personalization-tags-invalid")
    allowed = {"conceptIds", "knowledgeTaskIds", "associationIds", "pool"}
    if not set(value).issubset(allowed):
        raise AdmittedPackError("personalization-tags-unknown-field")
    arrays: list[list[str]] = []
    for key in ("conceptIds", "knowledgeTaskIds", "associationIds"):
        items = value.get(key, [])
        if not _unique_text_list(items, maximum=_MAX_LINK_IDS):
            raise AdmittedPackError(f"personalization-{key}-invalid")
        arrays.append(sorted(items))
    pool = value.get("pool", "broad")
    if not isinstance(pool, str) or pool not in {"broad", "exploration"}:
        raise AdmittedPackError("personalization-pool-invalid")
    return arrays[0], arrays[1], arrays[2], pool


def _assert_record_list(pack: dict[str, Any], name: str) -> list[dict[str, Any]]:
    values = pack.get(name)
    if not isinstance(values, list) or len(values) > _MAX_PACK_RECORDS:
        raise AdmittedPackError(f"pack-{name}-invalid-or-over-limit")
    if any(not _is_record(item) for item in values):
        raise AdmittedPackError(f"pack-{name}-record-invalid")
    return values


def _unique_records(records: list[dict[str, Any]], kind: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in records:
        record_id = item.get("id")
        if not _id(record_id):
            raise AdmittedPackError(f"{kind}-id-invalid")
        if record_id in result:
            raise AdmittedPackError(f"{kind}-id-duplicate")
        result[record_id] = item
    return result


def _validate_pack(
    pack: Any,
    *,
    expected_pack_id: str,
    expected_artifact_sha256: str,
    expected_sources: Mapping[str, SourcePin],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    if not _is_record(pack):
        raise AdmittedPackError("pack-not-object")
    expected_keys = {
        "schemaVersion", "packId", "manifestSha256", "sources", "lexemes", "senses", "facts", "clues", "quarantine", "artifactSha256"
    }
    if set(pack) != expected_keys:
        raise AdmittedPackError("pack-envelope-shape-invalid")
    if pack.get("schemaVersion") != PACK_SCHEMA_VERSION:
        raise AdmittedPackError("pack-schema-version-unsupported")
    if not _id(pack.get("packId")) or pack["packId"] != expected_pack_id:
        raise AdmittedPackError("pack-id-does-not-match-pin")
    if not _digest(pack.get("manifestSha256")):
        raise AdmittedPackError("manifest-digest-invalid")
    if not _digest(expected_artifact_sha256) or pack.get("artifactSha256") != expected_artifact_sha256:
        raise AdmittedPackError("pack-artifact-digest-does-not-match-pin")
    without_digest = {key: value for key, value in pack.items() if key != "artifactSha256"}
    canonical_pack = canonical_json(without_digest)
    if len(canonical_pack) > _MAX_PACK_BYTES:
        raise AdmittedPackError("pack-size-limit-exceeded")
    actual_digest = hashlib.sha256(canonical_pack).hexdigest()
    if actual_digest != pack["artifactSha256"]:
        raise AdmittedPackError("pack-artifact-digest-mismatch")

    raw_sources = pack.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources or len(raw_sources) > 256:
        raise AdmittedPackError("pack-sources-invalid")
    source_by_id: dict[str, dict[str, Any]] = {}
    for raw_source in raw_sources:
        source = _source_projection(raw_source)
        source_id = source["sourceId"]
        if source_id in source_by_id:
            raise AdmittedPackError("pack-source-id-duplicate")
        pin = expected_sources.get(source_id)
        if pin is None:
            raise AdmittedPackError("pack-source-id-not-pinned")
        if not isinstance(pin, SourcePin):
            raise AdmittedPackError("trusted-source-pin-invalid")
        if (
            not _text(pin.version, maximum=_MAX_ID)
            or not _digest(pin.artifact_sha256)
            or not isinstance(pin.content_class, str)
            or pin.content_class not in {"public", "synthetic"}
        ):
            raise AdmittedPackError("trusted-source-pin-invalid")
        if (
            source["version"] != pin.version
            or source["artifactSha256"] != pin.artifact_sha256
            or source["contentClass"] != pin.content_class
        ):
            raise AdmittedPackError("pack-source-does-not-match-pin")
        source_by_id[source_id] = source
    if set(source_by_id) != set(expected_sources):
        raise AdmittedPackError("pack-source-set-does-not-match-pins")

    quarantine = pack.get("quarantine")
    if not isinstance(quarantine, list) or len(quarantine) > _MAX_PACK_RECORDS:
        raise AdmittedPackError("pack-quarantine-invalid")

    lexemes = _unique_records(_assert_record_list(pack, "lexemes"), "lexeme")
    senses = _unique_records(_assert_record_list(pack, "senses"), "sense")
    facts = _unique_records(_assert_record_list(pack, "facts"), "fact")
    clues = _unique_records(_assert_record_list(pack, "clues"), "clue")

    for lexeme_id, lexeme in lexemes.items():
        if set(lexeme) not in (
            {"id", "headword", "language", "provenance"},
            {"id", "headword", "language", "provenance", "personalization"},
        ):
            raise AdmittedPackError("lexeme-record-shape-invalid")
        if not _text(lexeme.get("headword")) or lexeme["headword"] != lexeme["headword"].strip():
            raise AdmittedPackError("lexeme-headword-invalid")
        if unicodedata.normalize("NFC", lexeme["headword"]) != lexeme["headword"]:
            raise AdmittedPackError("lexeme-headword-not-nfc")
        if not _text(lexeme.get("language"), maximum=63):
            raise AdmittedPackError("lexeme-language-invalid")
        _reviewed_provenance(lexeme.get("provenance"), source_by_id)
        _personalization(lexeme.get("personalization"))

    for sense_id, sense in senses.items():
        if set(sense) != {"id", "lexemeId", "gloss", "resolutionStatus", "clueEligible", "fillOnly", "provenance"}:
            raise AdmittedPackError("sense-record-shape-invalid")
        lexeme_ref = sense.get("lexemeId")
        if not _id(lexeme_ref) or lexeme_ref not in lexemes:
            raise AdmittedPackError("sense-lexeme-reference-invalid")
        resolution = sense.get("resolutionStatus")
        if not isinstance(resolution, str) or resolution not in {"resolved", "unresolved"}:
            raise AdmittedPackError("sense-resolution-status-invalid")
        resolved = resolution == "resolved"
        if sense.get("clueEligible") is not resolved or sense.get("fillOnly") is resolved:
            raise AdmittedPackError("sense-eligibility-flags-invalid")
        gloss = sense.get("gloss")
        if resolved and not _text(gloss):
            raise AdmittedPackError("sense-gloss-invalid")
        if not resolved and gloss is not None and not isinstance(gloss, str):
            raise AdmittedPackError("sense-gloss-invalid")
        _reviewed_provenance(sense.get("provenance"), source_by_id)

    for fact_id, fact in facts.items():
        if set(fact) != {"id", "lexemeId", "statement", "provenance"}:
            raise AdmittedPackError("fact-record-shape-invalid")
        lexeme_ref = fact.get("lexemeId")
        if not _id(lexeme_ref) or lexeme_ref not in lexemes:
            raise AdmittedPackError("fact-lexeme-reference-invalid")
        if not _text(fact.get("statement")):
            raise AdmittedPackError("fact-statement-invalid")
        _reviewed_provenance(fact.get("provenance"), source_by_id)

    grammar_batch: list[dict[str, Any]] = []
    for clue_id, clue in clues.items():
        if set(clue) != {"id", "text", "answerLexemeId", "evidence", "grammar", "provenance"}:
            raise AdmittedPackError("clue-record-shape-invalid")
        if not _text(clue.get("text")):
            raise AdmittedPackError("clue-text-invalid")
        answer_lexeme_id = clue.get("answerLexemeId")
        if not _id(answer_lexeme_id) or answer_lexeme_id not in lexemes:
            raise AdmittedPackError("clue-lexeme-reference-invalid")
        evidence = clue.get("evidence")
        if not _is_record(evidence) or set(evidence) != {"type", "id"}:
            raise AdmittedPackError("clue-evidence-link-invalid")
        evidence_type, evidence_id = evidence.get("type"), evidence.get("id")
        if not _id(evidence_id):
            raise AdmittedPackError("clue-evidence-link-invalid")
        if evidence_type == "sense":
            linked = senses.get(evidence_id)
            if linked is None or linked.get("lexemeId") != answer_lexeme_id or linked.get("clueEligible") is not True:
                raise AdmittedPackError("clue-sense-reference-invalid")
        elif evidence_type == "fact":
            linked = facts.get(evidence_id)
            if linked is None or linked.get("lexemeId") != answer_lexeme_id:
                raise AdmittedPackError("clue-fact-reference-invalid")
        else:
            raise AdmittedPackError("clue-evidence-type-invalid")
        grammar = clue.get("grammar")
        if (
            not _is_record(grammar)
            or grammar.get("grammarVersion") != "clue-grammar-v1"
            or grammar.get("clueId") != clue_id
            or grammar.get("clueText") != clue["text"]
            or not isinstance(grammar.get("answer"), str)
            or unicodedata.normalize("NFC", grammar["answer"]).casefold()
            != unicodedata.normalize("NFC", lexemes[answer_lexeme_id]["headword"]).casefold()
        ):
            raise AdmittedPackError("clue-grammar-metadata-invalid")
        provenance = clue.get("provenance")
        if not _is_record(provenance) or set(provenance) != {
            "sources", "evidenceRefs", "evidenceProvenance", "reviewerId", "reviewedAt", "semanticTruthStatus"
        }:
            raise AdmittedPackError("clue-provenance-shape-invalid")
        linked_provenance = linked["provenance"]
        if provenance.get("evidenceProvenance") != linked_provenance:
            raise AdmittedPackError("clue-evidence-provenance-mismatch")
        source_rows = provenance.get("sources")
        if not isinstance(source_rows, list) or not source_rows:
            raise AdmittedPackError("clue-source-provenance-invalid")
        source_ids: set[str] = set()
        for source_row in source_rows:
            projected = _source_projection(source_row)
            source_id = projected["sourceId"]
            if source_id in source_ids or source_by_id.get(source_id) != projected:
                raise AdmittedPackError("clue-source-reference-invalid")
            source_ids.add(source_id)
        evidence_source_id = linked_provenance["source"]["sourceId"]
        if evidence_source_id not in source_ids or len(source_ids) > 2:
            raise AdmittedPackError("clue-source-provenance-incomplete")
        if not _unique_text_list(provenance.get("evidenceRefs"), maximum=256, required=True):
            raise AdmittedPackError("clue-evidence-references-invalid")
        if not _text(provenance.get("reviewerId"), maximum=200):
            raise AdmittedPackError("clue-reviewer-invalid")
        reviewed_at = provenance.get("reviewedAt")
        try:
            if not isinstance(reviewed_at, str) or date.fromisoformat(reviewed_at).isoformat() != reviewed_at:
                raise ValueError
        except ValueError as error:
            raise AdmittedPackError("clue-review-date-invalid") from error
        if provenance.get("semanticTruthStatus") != "not-established-by-grammar-validator":
            raise AdmittedPackError("clue-semantic-truth-status-invalid")
        grammar_batch.append(
            {
                "annotation": grammar,
                "context": {"enforceAnswerSafety": True},
            }
        )

    grammar_results = _run_clue_grammar(grammar_batch)
    if grammar_results is None:
        raise AdmittedPackError("clue-grammar-validator-unavailable")
    if any(result.get("valid") is not True for result in grammar_results):
        raise AdmittedPackError("clue-grammar-invalid")
    return lexemes, senses, facts, clues, source_by_id


def resolve_admitted_pack(
    pack: Any,
    *,
    expected_pack_id: str,
    expected_artifact_sha256: str,
    expected_sources: Mapping[str, SourcePin],
) -> list[dict[str, Any]]:
    """Return domain ``EligibleLexiconCandidateV1`` records from a pinned pack.

    Every returned candidate gets its eligibility assertion from this verified
    boundary. Input eligibility fields are not read. No clues or source facts
    are converted to evidence links. Only explicit ``personalization`` ID lists
    are mapped; their evidence still comes from the profile compiler. A lexeme
    with no such field remains broad with empty links.
    """

    if not _id(expected_pack_id):
        raise AdmittedPackError("expected-pack-id-invalid")
    if not expected_sources:
        raise AdmittedPackError("trusted-source-pins-required")
    lexemes, _, _, _, _ = _validate_pack(
        pack,
        expected_pack_id=expected_pack_id,
        expected_artifact_sha256=expected_artifact_sha256,
        expected_sources=expected_sources,
    )
    pack_digest = pack["artifactSha256"]
    candidates: list[dict[str, Any]] = []
    for lexeme_id in sorted(lexemes):
        lexeme = lexemes[lexeme_id]
        provenance = lexeme["provenance"]
        source_id = provenance["source"]["sourceId"]
        concept_ids, task_ids, association_ids, pool = _personalization(lexeme.get("personalization"))
        candidates.append(
            {
                "candidateId": lexeme_id,
                "answer": lexeme["headword"],
                "language": lexeme["language"],
                "conceptIds": concept_ids,
                "knowledgeTaskIds": task_ids,
                "associationIds": association_ids,
                "pool": pool,
                "eligibility": {
                    "status": "eligible",
                    "packId": pack["packId"],
                    "packVersion": pack_digest,
                    "sourceIds": [source_id],
                },
            }
        )
    return candidates


def _freeze_json(value: Any) -> Any:
    """Copy validated JSON into recursively immutable containers."""

    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise AdmittedPackError("content-projection-json-value-invalid")


def project_admitted_pack_content(
    pack: Any,
    *,
    expected_pack_id: str,
    expected_artifact_sha256: str,
    expected_sources: Mapping[str, SourcePin],
) -> AdmittedPackContent:
    """Return immutable, allowlisted reviewed content from the pinned pack.

    This performs the same complete artifact, source-pin, cross-reference, and
    clue-grammar validation as :func:`resolve_admitted_pack`. It exposes only
    answer identity, explicit personalization IDs, and reviewed senses, facts,
    and clues; their exact record provenance, clue evidence links, and validated
    grammar annotations remain attached. Raw manifests, pack-level sources,
    quarantine entries, and other input fields are not copied. Surface
    collisions under NFC/strip/casefold are rejected because a downstream
    crossword could not safely disambiguate which lexeme a filled answer
    represents.

    The return value asserts structural admission against the supplied pins;
    it does not assert that the underlying source is authentic or that clue
    semantics have been independently established.
    """

    if not _id(expected_pack_id):
        raise AdmittedPackError("expected-pack-id-invalid")
    if not expected_sources:
        raise AdmittedPackError("trusted-source-pins-required")
    lexemes, senses, facts, clues, _ = _validate_pack(
        pack,
        expected_pack_id=expected_pack_id,
        expected_artifact_sha256=expected_artifact_sha256,
        expected_sources=expected_sources,
    )

    lexeme_by_surface: dict[str, str] = {}
    for lexeme_id, lexeme in lexemes.items():
        surface = unicodedata.normalize("NFC", lexeme["headword"]).strip().casefold()
        previous = lexeme_by_surface.get(surface)
        if previous is not None and previous != lexeme_id:
            raise AdmittedPackError("content-answer-normalization-ambiguous")
        lexeme_by_surface[surface] = lexeme_id

    senses_by_lexeme: dict[str, list[AdmittedSenseContent]] = {key: [] for key in lexemes}
    for sense_id, sense in senses.items():
        senses_by_lexeme[sense["lexemeId"]].append(
            AdmittedSenseContent(
                sense_id=sense_id,
                gloss=sense["gloss"],
                resolution_status=sense["resolutionStatus"],
                clue_eligible=sense["clueEligible"],
                fill_only=sense["fillOnly"],
                provenance=_freeze_json(sense["provenance"]),
            )
        )

    facts_by_lexeme: dict[str, list[AdmittedFactContent]] = {key: [] for key in lexemes}
    for fact_id, fact in facts.items():
        facts_by_lexeme[fact["lexemeId"]].append(
            AdmittedFactContent(
                fact_id=fact_id,
                statement=fact["statement"],
                provenance=_freeze_json(fact["provenance"]),
            )
        )

    clues_by_lexeme: dict[str, list[AdmittedClueContent]] = {key: [] for key in lexemes}
    for clue_id, clue in clues.items():
        evidence = clue["evidence"]
        clues_by_lexeme[clue["answerLexemeId"]].append(
            AdmittedClueContent(
                clue_id=clue_id,
                text=clue["text"],
                answer_lexeme_id=clue["answerLexemeId"],
                evidence_type=evidence["type"],
                evidence_id=evidence["id"],
                grammar=_freeze_json(clue["grammar"]),
                provenance=_freeze_json(clue["provenance"]),
            )
        )

    projected_lexemes = tuple(
        AdmittedLexemeContent(
            lexeme_id=lexeme_id,
            answer=lexeme["headword"],
            language=lexeme["language"],
            provenance=_freeze_json(lexeme["provenance"]),
            senses=tuple(sorted(senses_by_lexeme[lexeme_id], key=lambda row: row.sense_id)),
            facts=tuple(sorted(facts_by_lexeme[lexeme_id], key=lambda row: row.fact_id)),
            clues=tuple(sorted(clues_by_lexeme[lexeme_id], key=lambda row: row.clue_id)),
            concept_ids=tuple(_personalization(lexeme.get("personalization"))[0]),
            knowledge_task_ids=tuple(_personalization(lexeme.get("personalization"))[1]),
            association_ids=tuple(_personalization(lexeme.get("personalization"))[2]),
            pool=_personalization(lexeme.get("personalization"))[3],
        )
        for lexeme_id, lexeme in sorted(lexemes.items())
    )
    return AdmittedPackContent(
        pack_id=pack["packId"],
        pack_sha256=pack["artifactSha256"],
        lexemes=projected_lexemes,
    )
