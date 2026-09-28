"""Deterministic OEWN form projection for human-reviewed crossword fills.

This module accepts only the staged output of :mod:`oewn_import`. Its output
is a review queue: it does not verify word meaning, admit content, or produce
clues. A human source-terms/admission attestation is required to make the
review boundary explicit, but cannot approve semantic truth.
"""

from __future__ import annotations

import hashlib
import argparse
import json
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .oewn_import import EXPECTED_SHA256, SOURCE_ID, SOURCE_VERSION, import_archive


STAGED_SCHEMA_VERSION = "oewn-staged-import-v1"
SCHEMA_VERSION = "oewn-fill-candidate-review-v1"
MAX_GRID_LENGTH = 21
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GRID_ANSWER = re.compile(r"^[A-Z]{2,21}$")
MAX_ATTESTATION_BYTES = 16 * 1024


class CandidateProjectionError(ValueError):
    """The staged import or attestation is malformed or exceeds a hard limit."""


@dataclass(frozen=True)
class ProjectionLimits:
    """Fail-closed input and output bounds; no partial projections are emitted."""

    max_input_bytes: int = 256 * 1024 * 1024
    max_lexemes: int = 300_000
    max_forms: int = 600_000
    max_senses: int = 750_000
    max_quarantine_records: int = 750_000
    max_surface_codepoints: int = 4096
    max_output_bytes: int = 256 * 1024 * 1024
    expected_source_id: str = SOURCE_ID
    expected_source_version: str = SOURCE_VERSION
    expected_source_sha256: str = EXPECTED_SHA256


def canonical_json(value: Any) -> bytes:
    """Use the staged importer’s stable JSON encoding for reproducible hashes."""

    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError) as error:
        raise CandidateProjectionError("input-json-not-canonicalizable") from error


def _digest(value: Any, max_bytes: int, *, code: str) -> str:
    encoded = canonical_json(value)
    if len(encoded) > max_bytes:
        raise CandidateProjectionError(code)
    return hashlib.sha256(encoded).hexdigest()


def _required_text(value: Any, code: str, *, max_length: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise CandidateProjectionError(code)
    return value


def _validate_attestation(attestation: Any, source: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(attestation, dict):
        raise CandidateProjectionError("human-attestation-required")
    expected_keys = {
        "humanAttested",
        "reviewerId",
        "attestedAt",
        "sourceId",
        "sourceVersion",
        "sourceArtifactSha256",
        "sourceTermsReviewed",
        "admissionDecision",
        "semanticTruthReviewed",
    }
    if set(attestation) != expected_keys:
        raise CandidateProjectionError("human-attestation-shape-invalid")
    if attestation.get("humanAttested") is not True:
        raise CandidateProjectionError("human-attestation-required")
    if attestation.get("sourceTermsReviewed") is not True:
        raise CandidateProjectionError("source-terms-attestation-required")
    if attestation.get("admissionDecision") != "review-required-fill-only":
        raise CandidateProjectionError("admission-attestation-scope-invalid")
    if attestation.get("semanticTruthReviewed") is not False:
        raise CandidateProjectionError("semantic-truth-cannot-be-attested-here")

    reviewer = _required_text(attestation.get("reviewerId"), "attestation-reviewer-invalid", max_length=200)
    timestamp = _required_text(attestation.get("attestedAt"), "attestation-time-invalid", max_length=64)
    try:
        parsed_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise CandidateProjectionError("attestation-time-invalid") from error
    if parsed_time.tzinfo is None or parsed_time.utcoffset() is None:
        raise CandidateProjectionError("attestation-time-must-have-timezone")

    if attestation.get("sourceId") != source.get("id"):
        raise CandidateProjectionError("attestation-source-id-mismatch")
    if attestation.get("sourceVersion") != source.get("editionDate"):
        raise CandidateProjectionError("attestation-source-version-mismatch")
    if attestation.get("sourceArtifactSha256") != source.get("artifactSha256"):
        raise CandidateProjectionError("attestation-source-digest-mismatch")
    if not isinstance(attestation.get("sourceArtifactSha256"), str) or not _SHA256.fullmatch(
        attestation["sourceArtifactSha256"]
    ):
        raise CandidateProjectionError("attestation-source-digest-invalid")

    # Return a constrained copy; arbitrary caller-supplied fields must not
    # smuggle approval assertions into the resulting review artifact.
    return {
        "humanAttested": True,
        "reviewerId": reviewer,
        "attestedAt": timestamp,
        "sourceId": attestation["sourceId"],
        "sourceVersion": attestation["sourceVersion"],
        "sourceArtifactSha256": attestation["sourceArtifactSha256"],
        "sourceTermsReviewed": True,
        "admissionDecision": "review-required-fill-only",
        "semanticTruthReviewed": False,
    }


def _validate_staged(staged: Any, limits: ProjectionLimits) -> tuple[dict[str, Any], str]:
    if not isinstance(staged, dict):
        raise CandidateProjectionError("staged-import-not-object")
    input_digest = _digest(staged, limits.max_input_bytes, code="input-size-limit-exceeded")
    if staged.get("schemaVersion") != STAGED_SCHEMA_VERSION:
        raise CandidateProjectionError("staged-import-version-unsupported")
    if staged.get("status") != "staged-source-imported":
        raise CandidateProjectionError("staged-import-status-invalid")
    if staged.get("admissionStatus") != "not-admitted":
        raise CandidateProjectionError("staged-import-admission-status-invalid")
    if staged.get("semanticReviewStatus") != "unreviewed":
        raise CandidateProjectionError("staged-import-semantic-review-status-invalid")
    source = staged.get("source")
    if not isinstance(source, dict):
        raise CandidateProjectionError("staged-import-source-invalid")
    for key in ("id", "edition", "editionDate", "artifactFilename"):
        _required_text(source.get(key), f"staged-source-{key}-invalid")
    artifact_digest = source.get("artifactSha256")
    if not isinstance(artifact_digest, str) or not _SHA256.fullmatch(artifact_digest):
        raise CandidateProjectionError("staged-source-digest-invalid")
    if (
        source.get("id") != limits.expected_source_id
        or source.get("editionDate") != limits.expected_source_version
        or artifact_digest != limits.expected_source_sha256
    ):
        raise CandidateProjectionError("staged-source-not-pinned")

    declared_digest = staged.get("artifactSha256")
    if not isinstance(declared_digest, str) or not _SHA256.fullmatch(declared_digest):
        raise CandidateProjectionError("staged-import-digest-invalid")
    without_digest = {key: value for key, value in staged.items() if key != "artifactSha256"}
    actual_declared_digest = _digest(
        without_digest,
        limits.max_input_bytes,
        code="input-size-limit-exceeded",
    )
    if actual_declared_digest != declared_digest:
        raise CandidateProjectionError("staged-import-digest-mismatch")

    forms = staged.get("forms")
    lexemes = staged.get("lexemes")
    senses = staged.get("senses")
    quarantine = staged.get("quarantine")
    counts = staged.get("counts")
    if not isinstance(lexemes, list) or len(lexemes) > limits.max_lexemes:
        raise CandidateProjectionError("staged-lexemes-invalid-or-over-limit")
    if not isinstance(forms, list) or len(forms) > limits.max_forms:
        raise CandidateProjectionError("staged-forms-invalid-or-over-limit")
    if not isinstance(senses, list) or len(senses) > limits.max_senses:
        raise CandidateProjectionError("staged-senses-invalid-or-over-limit")
    if not isinstance(quarantine, list) or len(quarantine) > limits.max_quarantine_records:
        raise CandidateProjectionError("staged-quarantine-invalid-or-over-limit")

    lexeme_by_id: dict[str, dict[str, Any]] = {}
    for lexeme in lexemes:
        if not isinstance(lexeme, dict):
            raise CandidateProjectionError("staged-lexeme-record-invalid")
        lexeme_id = _required_text(lexeme.get("id"), "staged-lexeme-id-invalid", max_length=256)
        if lexeme_id in lexeme_by_id:
            raise CandidateProjectionError("staged-lexeme-id-duplicate")
        if lexeme.get("sourceId") != source.get("id"):
            raise CandidateProjectionError("staged-lexeme-source-reference-invalid")
        surface = _required_text(
            lexeme.get("sourceSurface"),
            "staged-lexeme-surface-invalid",
            max_length=limits.max_surface_codepoints,
        )
        if lexeme.get("normalizedSurface") != unicodedata.normalize("NFC", surface).casefold():
            raise CandidateProjectionError("staged-lexeme-normalization-invalid")
        _required_text(lexeme.get("language"), "staged-lexeme-language-invalid", max_length=64)
        _required_text(lexeme.get("lexicalPartOfSpeech"), "staged-lexeme-pos-invalid", max_length=32)
        lexeme_by_id[lexeme_id] = lexeme

    form_by_id: dict[str, dict[str, Any]] = {}
    for form in forms:
        if not isinstance(form, dict):
            raise CandidateProjectionError("staged-form-record-invalid")
        form_id = _required_text(form.get("id"), "staged-form-id-invalid", max_length=256)
        if form_id in form_by_id:
            raise CandidateProjectionError("staged-form-id-duplicate")
        lexeme_id = _required_text(form.get("lexemeId"), "staged-form-lexeme-id-invalid", max_length=256)
        if lexeme_id not in lexeme_by_id:
            raise CandidateProjectionError("staged-form-lexeme-reference-invalid")
        surface = _required_text(
            form.get("sourceSurface"),
            "staged-form-source-surface-invalid",
            max_length=limits.max_surface_codepoints,
        )
        if form.get("normalizedSurface") != unicodedata.normalize("NFC", surface).casefold():
            raise CandidateProjectionError("staged-form-normalization-invalid")
        form_by_id[form_id] = form

    sense_ids: set[str] = set()
    for sense in senses:
        if not isinstance(sense, dict):
            raise CandidateProjectionError("staged-sense-record-invalid")
        sense_id = _required_text(sense.get("id"), "staged-sense-id-invalid", max_length=256)
        if sense_id in sense_ids:
            raise CandidateProjectionError("staged-sense-id-duplicate")
        if sense.get("lexemeId") not in lexeme_by_id:
            raise CandidateProjectionError("staged-sense-lexeme-reference-invalid")
        _required_text(sense.get("sourceSenseKey"), "staged-sense-key-invalid", max_length=512)
        _required_text(sense.get("synsetId"), "staged-sense-synset-reference-invalid", max_length=64)
        glosses = sense.get("sourceGlosses")
        if not isinstance(glosses, list) or any(not isinstance(gloss, str) for gloss in glosses):
            raise CandidateProjectionError("staged-sense-glosses-invalid")
        sense_ids.add(sense_id)

    expected_counts = {
        "lexemes": len(lexemes),
        "forms": len(forms),
        "senses": len(senses),
        "quarantineRecords": len(quarantine),
    }
    if not isinstance(counts, dict) or any(
        type(counts.get(key)) is not int or counts[key] != count for key, count in expected_counts.items()
    ):
        raise CandidateProjectionError("staged-import-counts-mismatch")

    for record in quarantine:
        if not isinstance(record, dict):
            raise CandidateProjectionError("staged-quarantine-record-invalid")
        record_type = record.get("recordType")
        record_id = _required_text(record.get("recordId"), "staged-quarantine-id-invalid", max_length=256)
        _required_text(record.get("reasonCode"), "staged-quarantine-reason-invalid", max_length=128)
        if record_type == "form" and record_id not in form_by_id:
            raise CandidateProjectionError("staged-quarantine-form-reference-invalid")
        if record_type == "sense" and record_id not in sense_ids:
            raise CandidateProjectionError("staged-quarantine-sense-reference-invalid")
        if record_type == "sense-reference" and not re.fullmatch(
            r"oewn2025:(?:sense|invalid-sense-ref):[0-9a-f]{32}", record_id
        ):
            raise CandidateProjectionError("staged-quarantine-sense-reference-invalid")
        if record_type not in {"form", "sense", "sense-reference"}:
            raise CandidateProjectionError("staged-quarantine-type-unsupported")
    return source, input_digest


def _source_surface_grid_form(surface: Any, limits: ProjectionLimits) -> tuple[str | None, str | None]:
    if not isinstance(surface, str) or not surface:
        return None, "source-surface-invalid"
    if len(surface) > limits.max_surface_codepoints:
        return None, "source-surface-over-limit"
    if any(unicodedata.category(character).startswith("C") for character in surface):
        return None, "surface-contains-control-or-format-character"
    if len(surface) > MAX_GRID_LENGTH:
        return None, "grid-form-too-long"
    if len(surface) < 2:
        return None, "grid-form-too-short"
    # Only literal ASCII letters make it through. Do not transliterate or
    # strip punctuation: doing so would invent a different answer surface.
    if not surface.isascii() or not surface.isalpha():
        return None, "grid-form-not-ascii-letters-only"
    answer = surface.upper()
    if not _GRID_ANSWER.fullmatch(answer):
        return None, "grid-form-normalization-invalid"
    return answer, None


def project_candidates(
    staged: Any,
    attestation: Any,
    *,
    limits: ProjectionLimits = ProjectionLimits(),
) -> dict[str, Any]:
    """Project safe answer shapes into a human review queue, never a word pack.

    ``attestation`` records that a human reviewed the source terms and the
    fill-only admission scope. It does not assert that any projected answer
    has a true meaning, acceptable clue, or content admission.
    """

    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in (
            limits.max_input_bytes,
            limits.max_lexemes,
            limits.max_forms,
            limits.max_senses,
            limits.max_quarantine_records,
            limits.max_surface_codepoints,
            limits.max_output_bytes,
        )
    ):
        raise CandidateProjectionError("projection-limits-invalid")
    source, input_digest = _validate_staged(staged, limits)
    attested = _validate_attestation(attestation, source)
    forms = staged["forms"]
    staged_quarantine = staged["quarantine"]

    reasons_by_form: dict[str, set[str]] = {}
    for record in staged_quarantine:
        if not isinstance(record, dict):
            raise CandidateProjectionError("staged-quarantine-record-invalid")
        if record.get("recordType") != "form":
            continue
        record_id = _required_text(record.get("recordId"), "staged-quarantine-id-invalid", max_length=256)
        reason = _required_text(
            record.get("reasonCode"), "staged-quarantine-reason-invalid", max_length=128
        )
        reasons_by_form.setdefault(record_id, set()).add(reason)

    candidates_by_answer: dict[str, dict[str, Any]] = {}
    excluded: list[dict[str, Any]] = []
    seen_form_ids: set[str] = set()
    for form in forms:
        if not isinstance(form, dict):
            raise CandidateProjectionError("staged-form-record-invalid")
        form_id = _required_text(form.get("id"), "staged-form-id-invalid", max_length=256)
        if form_id in seen_form_ids:
            raise CandidateProjectionError("staged-form-id-duplicate")
        seen_form_ids.add(form_id)
        lexeme_id = _required_text(form.get("lexemeId"), "staged-form-lexeme-id-invalid", max_length=256)
        source_surface = form.get("sourceSurface")
        if (
            not isinstance(source_surface, str)
            or not source_surface
            or len(source_surface) > limits.max_surface_codepoints
        ):
            raise CandidateProjectionError("staged-form-source-surface-invalid")
        form_kind = _required_text(form.get("formKind"), "staged-form-kind-invalid", max_length=32)
        if form_kind not in {"lemma", "inflection"}:
            raise CandidateProjectionError("staged-form-kind-unsupported")

        answer, shape_reason = _source_surface_grid_form(source_surface, limits)
        grid_shape_status = form.get("gridShapeStatus")
        if not isinstance(grid_shape_status, str) or grid_shape_status not in {"candidate", "quarantined"}:
            raise CandidateProjectionError("staged-form-grid-status-invalid")
        imported_grid_form = form.get("gridForm")
        if imported_grid_form is not None and not isinstance(imported_grid_form, str):
            raise CandidateProjectionError("staged-form-grid-form-invalid")
        if grid_shape_status == "candidate":
            if shape_reason is not None or imported_grid_form != answer:
                excluded.append(
                    {
                        "sourceFormId": form_id,
                        "sourceLexemeId": lexeme_id,
                        "sourceSurface": source_surface,
                        "reasonCodes": [shape_reason or "staged-grid-form-mismatch"],
                    }
                )
                continue
            candidate = candidates_by_answer.setdefault(
                answer,
                {
                    "answer": answer,
                    "sourceFormIds": [],
                    "sourceLexemeIds": [],
                    "sourceReferences": [],
                    "clueEligible": False,
                },
            )
            candidate["sourceFormIds"].append(form_id)
            candidate["sourceLexemeIds"].append(lexeme_id)
            reference = {
                "sourceFormId": form_id,
                "sourceLexemeId": lexeme_id,
                "sourceSurface": source_surface,
                "formKind": form_kind,
            }
            lexical_pos = form.get("lexicalPartOfSpeech")
            if isinstance(lexical_pos, str) and lexical_pos:
                reference["lexicalPartOfSpeech"] = lexical_pos
            candidate["sourceReferences"].append(reference)
            continue

        reasons = sorted(reasons_by_form.get(form_id, set()))
        if shape_reason is not None:
            reasons.append(shape_reason)
        elif not reasons:
            reasons.append("staged-form-quarantined")
        excluded.append(
            {
                "sourceFormId": form_id,
                "sourceLexemeId": lexeme_id,
                "sourceSurface": source_surface,
                "reasonCodes": sorted(set(reasons)),
            }
        )

    candidates: list[dict[str, Any]] = []
    for answer in sorted(candidates_by_answer):
        candidate = candidates_by_answer[answer]
        candidate["sourceFormIds"] = sorted(set(candidate["sourceFormIds"]))
        candidate["sourceLexemeIds"] = sorted(set(candidate["sourceLexemeIds"]))
        candidate["sourceReferences"] = sorted(
            candidate["sourceReferences"],
            key=lambda row: (row["sourceFormId"], row["sourceLexemeId"]),
        )
        candidate["id"] = "oewn-fill:" + hashlib.sha256(answer.encode("ascii")).hexdigest()[:32]
        candidates.append(candidate)
    excluded.sort(key=lambda row: (row["sourceFormId"], row["sourceLexemeId"], row["reasonCodes"]))

    result_without_digest: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "status": "review-required-fill-only",
        "admissionStatus": "not-admitted",
        "semanticReviewStatus": "unreviewed",
        "clueEligible": False,
        "approved": False,
        "source": {
            "id": source["id"],
            "edition": source["edition"],
            "editionDate": source["editionDate"],
            "artifactFilename": source["artifactFilename"],
            "artifactSha256": source["artifactSha256"],
            "artifactSizeBytes": source.get("artifactSizeBytes"),
            "artifactUrl": source.get("artifactUrl"),
            "licenseSpdx": source.get("licenseSpdx"),
            "licenseEvidenceUrl": source.get("licenseEvidenceUrl"),
            "licenseUrl": source.get("licenseUrl"),
            "attribution": source.get("attribution"),
        },
        "inputDigest": input_digest,
        "humanAttestation": attested,
        "normalization": {
            "answerForm": (
                "Preserve source surface exactly; accept only 2–21 ASCII letters and uppercase them."
            ),
            "deduplication": (
                "Equal ASCII grid answers share one candidate with every source form reference retained."
            ),
            "semanticStatus": (
                "Shape eligibility is not evidence of meaning, clue suitability, approval, or admission."
            ),
        },
        "counts": {
            "sourceForms": len(forms),
            "fillCandidates": len(candidates),
            "excludedForms": len(excluded),
        },
        "candidates": candidates,
        "quarantine": excluded,
    }
    projection_digest = _digest(
        result_without_digest,
        limits.max_output_bytes,
        code="output-size-limit-exceeded",
    )
    return {**result_without_digest, "projectionDigest": projection_digest}


def build_review_from_archive(
    archive_path: Path,
    attestation_path: Path,
    *,
    limits: ProjectionLimits = ProjectionLimits(),
) -> dict[str, Any]:
    """Import the pinned archive and project it in one trusted local pipeline."""

    try:
        attestation_bytes = attestation_path.read_bytes()
    except OSError as error:
        raise CandidateProjectionError("attestation-file-unavailable") from error
    if len(attestation_bytes) > MAX_ATTESTATION_BYTES:
        raise CandidateProjectionError("attestation-file-over-limit")
    try:
        attestation = json.loads(
            attestation_bytes.decode("utf-8"),
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("non-finite-number")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        raise CandidateProjectionError("attestation-json-invalid") from error
    staged = import_archive(archive_path)
    return project_candidates(staged, attestation, limits=limits)


def write_review_from_archive(
    archive_path: Path,
    attestation_path: Path,
    output_path: Path,
    *,
    limits: ProjectionLimits = ProjectionLimits(),
) -> dict[str, Any]:
    """Build without partial outputs; atomically replace only after validation."""

    result = build_review_from_archive(archive_path, attestation_path, limits=limits)
    output = canonical_json(result) + b"\n"
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(output)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, output_path)
    except OSError as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise CandidateProjectionError("review-output-write-failed") from error
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a bounded OEWN fill-only human review queue")
    parser.add_argument("archive", type=Path, help="the exact pinned OEWN 2025 ZIP archive")
    parser.add_argument("attestation", type=Path, help="a real human source-terms review JSON record")
    parser.add_argument("output", type=Path, help="destination review JSON path")
    args = parser.parse_args(argv)
    try:
        result = write_review_from_archive(args.archive, args.attestation, args.output)
    except CandidateProjectionError as error:
        parser.error(str(error))
    except ValueError as error:
        # Preserve the importer’s stable rejection code without a traceback.
        parser.error(str(error))
    print(f"wrote {len(result['candidates'])} fill-only review candidates ({result['projectionDigest']})")
    return 0


__all__ = [
    "CandidateProjectionError",
    "ProjectionLimits",
    "SCHEMA_VERSION",
    "canonical_json",
    "build_review_from_archive",
    "write_review_from_archive",
    "main",
    "project_candidates",
]


if __name__ == "__main__":
    raise SystemExit(main())
