"""Synthetic-only coverage for the deterministic OEWN source importer."""

from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from tools.lexicon.oewn_import import (
    ImportLimits,
    OEWNImportError,
    _import_archive_bytes,
    canonical_json,
    import_archive,
)


TEST_SOURCE = {
    "id": "synthetic-oewn-shape-fixture",
    "title": "Hand-authored synthetic importer fixture",
    "publisher": "Repository tests",
    "edition": "fixture-v1",
    "editionDate": "2026-09-26",
    "artifactFilename": "synthetic.zip",
    "artifactUrl": "",
    "licenseSpdx": None,
    "licenseEvidence": "Synthetic fixture; no external content or license claim.",
    "licenseEvidenceUrl": "",
    "licenseUrl": "",
    "attribution": "Synthetic hand-authored test data.",
    "status": "synthetic-test-fixture",
}


def _entries() -> dict[str, Any]:
    return {
        "Alpha": {
            "n-1": {
                "sense": [{"id": "alpha%1:00:00::", "synset": "00000001-n"}],
                "form": ["Alphas", "A"],
            }
        },
        "New York": {"n": {"sense": [{"id": "new_york%1:00:00::", "synset": "00000002-n"}]}},
        "Café": {"n": {"sense": [{"id": "cafe%1:00:00::", "synset": "00000003-n"}]}},
        "x": {"n": {"sense": [{"id": "x%1:00:00::", "synset": "00000004-n"}]}},
        "longwordthatcannotfitx": {
            "n": {"sense": [{"id": "long%1:00:00::", "synset": "00000005-n"}]}
        },
        "bad\u202eform": {
            "n": {"sense": [{"id": "bad%1:00:00::", "synset": "00000006-n"}]}
        },
        "Ghost": {"n": {"sense": [{"id": "ghost%1:00:00::", "synset": "00000007-n"}]}},
        "NoGloss": {"n": {"sense": [{"id": "nogloss%1:00:00::", "synset": "00000008-n"}]}},
    }


def _synsets() -> dict[str, Any]:
    return {
        "00000001-n": {"partOfSpeech": "n", "definition": ["An exact synthetic gloss."]},
        "00000002-n": {"partOfSpeech": "n", "definition": ["A place with a space."]},
        "00000003-n": {"partOfSpeech": "n", "definition": ["A Unicode surface fixture."]},
        "00000004-n": {"partOfSpeech": "n", "definition": ["A too-short fixture."]},
        "00000005-n": {"partOfSpeech": "n", "definition": ["A long-form fixture."]},
        "00000006-n": {"partOfSpeech": "n", "definition": ["An unsafe-character fixture."]},
        "00000008-n": {"partOfSpeech": "n", "definition": []},
    }


def _zip_bytes(
    *,
    entries: dict[str, Any] | None = None,
    synsets: dict[str, Any] | None = None,
    extra_members: dict[str, bytes] | None = None,
) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "entries-a.json",
            json.dumps(_entries() if entries is None else entries, ensure_ascii=False, separators=(",", ":")),
        )
        archive.writestr(
            "noun.synthetic.json",
            json.dumps(_synsets() if synsets is None else synsets, ensure_ascii=False, separators=(",", ":")),
        )
        for name, value in (extra_members or {}).items():
            archive.writestr(name, value)
    return buffer.getvalue()


def _import_fixture(tmp_path: Path, archive_bytes: bytes | None = None, **kwargs: Any) -> dict[str, Any]:
    source_bytes = _zip_bytes() if archive_bytes is None else archive_bytes
    archive_path = tmp_path / "synthetic.zip"
    archive_path.write_bytes(source_bytes)
    return _import_archive_bytes(
        source_bytes,
        hashlib.sha256(source_bytes).hexdigest(),
        TEST_SOURCE,
        **kwargs,
    )


def _lexeme(result: dict[str, Any], surface: str) -> dict[str, Any]:
    return next(row for row in result["lexemes"] if row["sourceSurface"] == surface)


def _forms_for(result: dict[str, Any], source_surface: str) -> list[dict[str, Any]]:
    return [row for row in result["forms"] if row["sourceSurface"] == source_surface]


def test_import_is_deterministic_source_linked_and_never_admits_content(tmp_path: Path) -> None:
    first = _import_fixture(tmp_path)
    second = _import_fixture(tmp_path)

    assert canonical_json(first) == canonical_json(second)
    assert first["status"] == "staged-source-imported"
    assert first["admissionStatus"] == "not-admitted"
    assert first["source"]["id"] == TEST_SOURCE["id"]
    assert first["source"]["licenseSpdx"] is None
    assert "clues" not in first and "facts" not in first
    assert all("reviewerId" not in row for bucket in ("lexemes", "forms", "senses") for row in first[bucket])
    assert first["counts"]["lexemes"] == len(first["lexemes"])
    assert first["counts"]["forms"] == len(first["forms"])
    assert first["counts"]["senses"] == len(first["senses"])

    alpha = _lexeme(first, "Alpha")
    assert alpha["lexicalPartOfSpeech"] == "n-1"
    assert alpha["sourceId"] == TEST_SOURCE["id"]
    assert first["admissionStatus"] == "not-admitted"
    assert first["semanticReviewStatus"] == "unreviewed"
    alpha_forms = [row for row in first["forms"] if row["lexemeId"] == alpha["id"]]
    assert {(row["sourceSurface"], row["formKind"]) for row in alpha_forms} == {
        ("Alpha", "lemma"),
        ("Alphas", "inflection"),
        ("A", "inflection"),
    }
    assert next(row for row in alpha_forms if row["sourceSurface"] == "Alphas")["gridForm"] == "ALPHAS"
    assert next(row for row in alpha_forms if row["sourceSurface"] == "Alphas")["gridShapeStatus"] == "candidate"

    alpha_sense = next(row for row in first["senses"] if row["lexemeId"] == alpha["id"])
    assert alpha_sense["sourceSenseKey"] == "alpha%1:00:00::"
    assert alpha_sense["synsetId"] == "00000001-n"
    assert alpha_sense["synsetPartOfSpeech"] == "n"
    assert alpha_sense["sourceGlosses"] == ["An exact synthetic gloss."]
    assert first["semanticReviewStatus"] == "unreviewed"


def test_grid_shape_quarantines_non_grid_unsafe_short_and_long_forms(tmp_path: Path) -> None:
    result = _import_fixture(tmp_path)
    status_by_surface = {
        row["sourceSurface"]: row["gridShapeStatus"]
        for row in result["forms"]
        if row["formKind"] == "lemma"
    }

    assert status_by_surface["Alpha"] == "candidate"
    assert status_by_surface["New York"] == "quarantined"
    assert status_by_surface["Café"] == "quarantined"
    assert status_by_surface["x"] == "quarantined"
    assert status_by_surface["longwordthatcannotfitx"] == "quarantined"
    assert status_by_surface["bad\u202eform"] == "quarantined"
    reasons_by_surface = {
        row["sourceSurface"]: row["reasonCode"]
        for row in result["quarantine"]
        if row["recordType"] == "form"
    }
    assert reasons_by_surface["New York"] == "grid-form-not-ascii-letters-only"
    assert reasons_by_surface["Café"] == "grid-form-not-ascii-letters-only"
    assert reasons_by_surface["x"] == "grid-form-too-short"
    assert reasons_by_surface["longwordthatcannotfitx"] == "grid-form-too-long"
    assert reasons_by_surface["bad\u202eform"] == "surface-contains-control-or-format-character"
    assert any(row["sourceSurface"] == "New York" for row in result["quarantine"])


def test_unresolved_synsets_and_missing_glosses_remain_staged_and_quarantined(tmp_path: Path) -> None:
    result = _import_fixture(tmp_path)
    ghost = _lexeme(result, "Ghost")
    missing_synset = next(row for row in result["senses"] if row["lexemeId"] == ghost["id"])
    assert missing_synset["synsetId"] == "00000007-n"
    assert missing_synset["sourceGlosses"] == []
    assert any(
        row["recordId"] == missing_synset["id"] and row["reasonCode"] == "source-synset-unresolved"
        for row in result["quarantine"]
    )

    no_gloss_lexeme = _lexeme(result, "NoGloss")
    no_gloss = next(row for row in result["senses"] if row["lexemeId"] == no_gloss_lexeme["id"])
    assert no_gloss["synsetId"] == "00000008-n"
    assert no_gloss["sourceGlosses"] == []
    assert any(
        row["recordId"] == no_gloss["id"] and row["reasonCode"] == "source-gloss-missing"
        for row in result["quarantine"]
    )
    assert result["admissionStatus"] == "not-admitted"


def test_unicode_surface_original_is_preserved_while_key_is_normalized(tmp_path: Path) -> None:
    result = _import_fixture(tmp_path)
    cafe = _lexeme(result, "Café")
    assert cafe["sourceSurface"] == "Café"
    assert cafe["normalizedSurface"] == "café"
    assert _forms_for(result, "Café")[0]["sourceSurface"] == "Café"


def test_archive_rejects_path_traversal_unexpected_files_duplicate_json_keys_and_bad_json(
    tmp_path: Path,
) -> None:
    bad_path = _zip_bytes(extra_members={"../escape.json": b"{}"})
    with pytest.raises(OEWNImportError, match="archive-member-path-unsafe"):
        _import_fixture(tmp_path, bad_path)

    unexpected = _zip_bytes(extra_members={"LICENSE.txt": b"test"})
    with pytest.raises(OEWNImportError, match="archive-member-name-unsupported"):
        _import_fixture(tmp_path, unexpected)

    duplicate_key = BytesIO()
    with zipfile.ZipFile(duplicate_key, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("entries-a.json", '{"Alpha":{},"Alpha":{}}')
        archive.writestr("noun.synthetic.json", "{}")
    with pytest.raises(OEWNImportError, match="json-duplicate-key"):
        _import_fixture(tmp_path, duplicate_key.getvalue())

    malformed = BytesIO()
    with zipfile.ZipFile(malformed, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("entries-a.json", "{")
        archive.writestr("noun.synthetic.json", "{}")
    with pytest.raises(OEWNImportError, match="json-member-invalid"):
        _import_fixture(tmp_path, malformed.getvalue())


def test_import_limits_fail_closed_without_silent_truncation(tmp_path: Path) -> None:
    with pytest.raises(OEWNImportError, match="lexeme-limit-exceeded"):
        _import_fixture(tmp_path, limits=ImportLimits(max_lexemes=1))
    with pytest.raises(OEWNImportError, match="output-size-limit-exceeded"):
        _import_fixture(tmp_path, limits=ImportLimits(max_output_bytes=64))


def test_public_import_requires_the_exact_pinned_official_archive(tmp_path: Path) -> None:
    fixture_path = tmp_path / "fixture.zip"
    fixture_path.write_bytes(_zip_bytes())
    with pytest.raises(OEWNImportError, match="archive-sha256-mismatch"):
        import_archive(fixture_path)
