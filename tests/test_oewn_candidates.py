"""Synthetic-only tests for OEWN fill-candidate review projection."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from tools.lexicon.oewn_candidates import (
    CandidateProjectionError,
    ProjectionLimits,
    canonical_json,
    project_candidates,
)
import tools.lexicon.oewn_candidates as candidates_module


SOURCE = {
    "id": "synthetic-oewn-shape-fixture",
    "edition": "Synthetic OEWN fixture",
    "editionDate": "2026-09-26",
    "artifactFilename": "synthetic.zip",
    "artifactSha256": "a" * 64,
    "artifactSizeBytes": 128,
    "artifactUrl": "https://example.invalid/synthetic.zip",
    "licenseSpdx": None,
    "licenseEvidenceUrl": "https://example.invalid/terms",
    "licenseUrl": "",
    "attribution": "Synthetic hand-authored test data.",
}


def _form(
    form_id: str,
    lexeme_id: str,
    surface: str,
    *,
    form_kind: str = "lemma",
    status: str | None = None,
    grid_form: str | None = None,
) -> dict[str, Any]:
    shape_safe = surface.isascii() and surface.isalpha() and 2 <= len(surface) <= 21
    if status is None:
        status = "candidate" if shape_safe else "quarantined"
    if grid_form is None and status == "candidate":
        grid_form = surface.upper()
    return {
        "id": form_id,
        "lexemeId": lexeme_id,
        "sourceSurface": surface,
        "normalizedSurface": surface.casefold(),
        "formKind": form_kind,
        "gridForm": grid_form,
        "gridShapeStatus": status,
    }


def _staged(forms: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    form_rows = forms if forms is not None else [
        _form("form-a", "lex-a", "Ewe"),
        _form("form-b", "lex-b", "EWE", form_kind="inflection"),
        _form("form-c", "lex-c", "OPEC"),
        _form("form-d", "lex-d", "New York"),
        _form("form-e", "lex-e", "éclair"),
        _form("form-f", "lex-f", "x"),
        _form("form-g", "lex-g", "bad\u202eform"),
    ]
    lexeme_ids = sorted({form["lexemeId"] for form in form_rows if isinstance(form, dict)})
    quarantine_rows = [
        {"recordType": "form", "recordId": "form-d", "reasonCode": "grid-form-not-ascii-letters-only"},
        {"recordType": "form", "recordId": "form-e", "reasonCode": "grid-form-not-ascii-letters-only"},
        {"recordType": "form", "recordId": "form-f", "reasonCode": "grid-form-too-short"},
        {
            "recordType": "form",
            "recordId": "form-g",
            "reasonCode": "surface-contains-control-or-format-character",
        },
    ]
    quarantine_rows = [row for row in quarantine_rows if row["recordId"] in {form.get("id") for form in form_rows}]
    staged: dict[str, Any] = {
        "schemaVersion": "oewn-staged-import-v1",
        "status": "staged-source-imported",
        "admissionStatus": "not-admitted",
        "semanticReviewStatus": "unreviewed",
        "source": dict(SOURCE),
        "lexemes": [
            {
                "id": lexeme_id,
                "sourceId": SOURCE["id"],
                "sourceSurface": lexeme_id,
                "normalizedSurface": lexeme_id.casefold(),
                "language": "en",
                "lexicalPartOfSpeech": "n",
            }
            for lexeme_id in lexeme_ids
        ],
        "forms": form_rows,
        "senses": [],
        "quarantine": quarantine_rows,
        "counts": {
            "lexemes": len(lexeme_ids),
            "forms": len(form_rows),
            "senses": 0,
            "quarantineRecords": len(quarantine_rows),
        },
    }
    staged["artifactSha256"] = hashlib.sha256(canonical_json(staged)).hexdigest()
    return staged


def _limits(**overrides: Any) -> ProjectionLimits:
    return ProjectionLimits(
        expected_source_id=SOURCE["id"],
        expected_source_version=SOURCE["editionDate"],
        expected_source_sha256=SOURCE["artifactSha256"],
        **overrides,
    )


def _attestation(**overrides: Any) -> dict[str, Any]:
    value = {
        "humanAttested": True,
        "reviewerId": "reviewer-fixture",
        "attestedAt": "2026-09-26T12:00:00Z",
        "sourceId": SOURCE["id"],
        "sourceVersion": SOURCE["editionDate"],
        "sourceArtifactSha256": SOURCE["artifactSha256"],
        "sourceTermsReviewed": True,
        "admissionDecision": "review-required-fill-only",
        "semanticTruthReviewed": False,
    }
    value.update(overrides)
    return value


def _project(
    staged: dict[str, Any] | None = None,
    attestation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return project_candidates(staged or _staged(), attestation or _attestation(), limits=_limits())


def test_projection_is_deterministic_deduplicates_answers_and_retains_form_ids() -> None:
    staged = _staged()
    first = _project(staged)
    second = _project(staged)

    assert canonical_json(first) == canonical_json(second)
    assert first["projectionDigest"] == second["projectionDigest"]
    assert [row["answer"] for row in first["candidates"]] == ["EWE", "OPEC"]
    ewe = first["candidates"][0]
    assert ewe["sourceFormIds"] == ["form-a", "form-b"]
    assert ewe["sourceLexemeIds"] == ["lex-a", "lex-b"]
    assert {row["sourceFormId"] for row in ewe["sourceReferences"]} == {"form-a", "form-b"}


def test_projection_quarantines_unsafe_shapes_with_reasons() -> None:
    result = _project()
    excluded = {row["sourceFormId"]: row["reasonCodes"] for row in result["quarantine"]}

    assert excluded["form-d"] == ["grid-form-not-ascii-letters-only"]
    assert excluded["form-e"] == ["grid-form-not-ascii-letters-only"]
    assert excluded["form-f"] == ["grid-form-too-short"]
    assert excluded["form-g"] == ["surface-contains-control-or-format-character"]
    assert result["counts"] == {"sourceForms": 7, "fillCandidates": 2, "excludedForms": 4}


def test_projection_retains_source_terms_attestation_and_complete_provenance() -> None:
    result = _project()

    assert result["source"]["id"] == SOURCE["id"]
    assert result["source"]["editionDate"] == SOURCE["editionDate"]
    assert result["source"]["artifactSha256"] == SOURCE["artifactSha256"]
    assert result["source"]["licenseSpdx"] is None
    assert result["inputDigest"] == hashlib.sha256(canonical_json(_staged())).hexdigest()
    assert result["humanAttestation"]["sourceTermsReviewed"] is True
    assert result["humanAttestation"]["admissionDecision"] == "review-required-fill-only"


def test_projection_never_marks_words_or_clues_approved_or_semantically_reviewed() -> None:
    result = _project()

    assert result["status"] == "review-required-fill-only"
    assert result["admissionStatus"] == "not-admitted"
    assert result["semanticReviewStatus"] == "unreviewed"
    assert result["approved"] is False
    assert result["clueEligible"] is False
    assert "clues" not in result and "senses" not in result and "facts" not in result
    assert all(row["clueEligible"] is False for row in result["candidates"])
    assert "sourceGlosses" not in canonical_json(result).decode("ascii")


def test_projection_rejects_missing_or_overreaching_human_attestations() -> None:
    staged = _staged()
    with pytest.raises(CandidateProjectionError, match="human-attestation-required"):
        project_candidates(staged, None, limits=_limits())
    with pytest.raises(CandidateProjectionError, match="source-terms-attestation-required"):
        project_candidates(staged, _attestation(sourceTermsReviewed=False), limits=_limits())
    with pytest.raises(CandidateProjectionError, match="semantic-truth-cannot-be-attested-here"):
        project_candidates(staged, _attestation(semanticTruthReviewed=True), limits=_limits())
    with pytest.raises(CandidateProjectionError, match="admission-attestation-scope-invalid"):
        project_candidates(staged, _attestation(admissionDecision="approved"), limits=_limits())
    with pytest.raises(CandidateProjectionError, match="attestation-source-digest-mismatch"):
        project_candidates(staged, _attestation(sourceArtifactSha256="b" * 64), limits=_limits())


def test_projection_rejects_tampered_staging_malformed_forms_and_limits() -> None:
    tampered = _staged()
    tampered["forms"][0]["sourceSurface"] = "NOT WHAT WAS DIGESTED"
    with pytest.raises(CandidateProjectionError, match="staged-import-digest-mismatch"):
        _project(tampered)

    duplicate_id = _staged([_form("same", "lex-a", "Ewe"), _form("same", "lex-b", "OPEC")])
    with pytest.raises(CandidateProjectionError, match="staged-form-id-duplicate"):
        _project(duplicate_id)

    invalid_candidate = _staged(
        [_form("form-a", "lex-a", "New York", status="candidate", grid_form="NEWYORK")]
    )
    result = _project(invalid_candidate)
    assert result["candidates"] == []
    assert result["quarantine"][0]["reasonCodes"] == ["grid-form-not-ascii-letters-only"]

    with pytest.raises(CandidateProjectionError, match="staged-forms-invalid-or-over-limit"):
        project_candidates(_staged(), _attestation(), limits=_limits(max_forms=1))

    empty = _staged([])
    empty_result = _project(empty)
    assert empty_result["candidates"] == []
    assert empty_result["quarantine"] == []

    malformed_surface = _staged([_form("form-a", "lex-a", "Ewe")])
    malformed_surface["forms"][0]["sourceSurface"] = ["Ewe"]
    malformed_surface["artifactSha256"] = hashlib.sha256(
        canonical_json({key: value for key, value in malformed_surface.items() if key != "artifactSha256"})
    ).hexdigest()
    with pytest.raises(CandidateProjectionError, match="staged-form-source-surface-invalid"):
        _project(malformed_surface)


def test_projection_rejects_dangling_or_wrong_source_references() -> None:
    dangling = _staged([_form("form-a", "lex-a", "Ewe")])
    dangling["forms"][0]["lexemeId"] = "missing-lexeme"
    dangling["artifactSha256"] = hashlib.sha256(
        canonical_json({key: value for key, value in dangling.items() if key != "artifactSha256"})
    ).hexdigest()
    with pytest.raises(CandidateProjectionError, match="staged-form-lexeme-reference-invalid"):
        _project(dangling)

    wrong_source = _staged()
    wrong_source["lexemes"][0]["sourceId"] = "another-source"
    wrong_source["artifactSha256"] = hashlib.sha256(
        canonical_json({key: value for key, value in wrong_source.items() if key != "artifactSha256"})
    ).hexdigest()
    with pytest.raises(CandidateProjectionError, match="staged-lexeme-source-reference-invalid"):
        _project(wrong_source)

    wrong_pinned_source = _staged()
    wrong_pinned_source["source"]["artifactSha256"] = "b" * 64
    wrong_pinned_source["artifactSha256"] = hashlib.sha256(
        canonical_json({key: value for key, value in wrong_pinned_source.items() if key != "artifactSha256"})
    ).hexdigest()
    with pytest.raises(CandidateProjectionError, match="staged-source-not-pinned"):
        _project(wrong_pinned_source)


def test_archive_build_uses_importer_and_writes_only_validated_review(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    archive = tmp_path / "pinned-oewn.zip"
    archive.write_bytes(b"fixture source archive")
    attestation_path = tmp_path / "actual-human-attestation.json"
    attestation_path.write_bytes(canonical_json(_attestation()))
    output = tmp_path / "review-queue.json"
    imported = _staged()

    def fixture_import(path):
        assert path == archive
        return imported

    monkeypatch.setattr(candidates_module, "import_archive", fixture_import)
    result = candidates_module.write_review_from_archive(archive, attestation_path, output, limits=_limits())
    assert result["counts"]["fillCandidates"] == 2
    assert output.read_bytes() == canonical_json(result) + b"\n"
    assert not list(tmp_path.glob("*.tmp"))
