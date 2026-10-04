"""Synthetic-only bounded-loader tests; no production content is bundled."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from crossword.admitted_pack import AdmittedPackError, SourcePin, canonical_json
from crossword.admitted_pack_loader import (
    MAX_ADMITTED_PACK_BYTES,
    AdmittedPackLoadError,
    load_admitted_pack_bytes,
    load_admitted_pack_file,
    load_admitted_pack_file_with_content,
)


_SYNTHETIC_SOURCE = b"Synthetic loader fixture only; CC0-1.0."
_SOURCE_ID = "synthetic-loader-source"
_PACK_ID = "synthetic-loader-pack"


def _fixture() -> tuple[dict[str, Any], dict[str, SourcePin]]:
    source_digest = hashlib.sha256(_SYNTHETIC_SOURCE).hexdigest()
    pack: dict[str, Any] = {
        "schemaVersion": "lexicon-pack-admission-v1",
        "packId": _PACK_ID,
        "manifestSha256": "1" * 64,
        "sources": [
            {
                "sourceId": _SOURCE_ID,
                "version": "fixture-v1",
                "artifactSha256": source_digest,
                "spdx": "CC0-1.0",
                "attribution": "Synthetic loader test data.",
                "contentClass": "synthetic",
            }
        ],
        "lexemes": [
            {
                "id": "lexeme-ewe",
                "headword": "EWE",
                "language": "en",
                "provenance": {
                    "source": {
                        "sourceId": _SOURCE_ID,
                        "version": "fixture-v1",
                        "artifactSha256": source_digest,
                        "spdx": "CC0-1.0",
                        "attribution": "Synthetic loader test data.",
                        "contentClass": "synthetic",
                    },
                    "evidenceRefs": ["synthetic:lexeme/EWE"],
                    "reviewerId": "synthetic-reviewer",
                    "reviewedAt": "2026-09-26",
                },
            }
        ],
        "senses": [],
        "facts": [],
        "clues": [],
        "quarantine": [],
    }
    _resign(pack)
    pins = {
        _SOURCE_ID: SourcePin(
            version="fixture-v1",
            artifact_sha256=source_digest,
            content_class="synthetic",
        )
    }
    return pack, pins


def _resign(pack: dict[str, Any]) -> None:
    pack["artifactSha256"] = hashlib.sha256(
        canonical_json({key: value for key, value in pack.items() if key != "artifactSha256"})
    ).hexdigest()


def _load_bytes(raw: bytes, pack: dict[str, Any], pins: dict[str, SourcePin]) -> list[dict[str, Any]]:
    return load_admitted_pack_bytes(
        raw,
        expected_pack_id=_PACK_ID,
        expected_artifact_sha256=pack["artifactSha256"],
        expected_sources=pins,
    )


def test_loads_a_valid_synthetic_pack_from_bytes_and_file(tmp_path: Path) -> None:
    pack, pins = _fixture()
    raw = canonical_json(pack)
    path = tmp_path / "synthetic-admitted-pack.json"
    path.write_bytes(raw)

    from_bytes = _load_bytes(raw, pack, pins)
    from_file = load_admitted_pack_file(
        path,
        expected_pack_id=_PACK_ID,
        expected_artifact_sha256=pack["artifactSha256"],
        expected_sources=pins,
    )

    assert from_bytes == from_file
    assert from_file[0]["candidateId"] == "lexeme-ewe"
    assert from_file[0]["pool"] == "broad"


def test_content_and_candidates_come_from_one_file_read_and_exact_pins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack, pins = _fixture()
    raw = canonical_json(pack)
    path = tmp_path / "synthetic-admitted-pack.json"
    path.write_bytes(raw)
    original_open = Path.open
    opened_paths: list[Path] = []

    def counted_open(self: Path, *args, **kwargs):
        if self == path:
            opened_paths.append(self)
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counted_open)

    loaded = load_admitted_pack_file_with_content(
        path,
        expected_pack_id=_PACK_ID,
        expected_artifact_sha256=pack["artifactSha256"],
        expected_sources=pins,
    )

    candidate = loaded.candidates[0]
    lexeme = loaded.content.lexemes[0]
    assert opened_paths == [path]
    assert loaded.content.pack_id == candidate["eligibility"]["packId"] == _PACK_ID
    assert loaded.content.pack_sha256 == candidate["eligibility"]["packVersion"] == pack[
        "artifactSha256"
    ]
    assert candidate["eligibility"]["sourceIds"] == [
        lexeme.provenance["source"]["sourceId"]
    ] == [_SOURCE_ID]
    assert lexeme.lexeme_id == candidate["candidateId"] == "lexeme-ewe"
    assert lexeme.answer == candidate["answer"] == "EWE"
    with pytest.raises((AttributeError, TypeError)):
        lexeme.provenance["source"]["sourceId"] = "changed"


def test_projection_uses_validated_bytes_if_file_changes_after_candidate_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import crossword.admitted_pack_loader as loader

    pack, pins = _fixture()
    original_raw = canonical_json(pack)
    path = tmp_path / "synthetic-admitted-pack.json"
    path.write_bytes(original_raw)
    original_resolve = loader.resolve_admitted_pack

    changed = json.loads(original_raw)
    changed["lexemes"][0]["headword"] = "NEW"
    _resign(changed)
    changed_raw = canonical_json(changed)
    assert changed["artifactSha256"] != pack["artifactSha256"]

    def resolve_then_replace(*args, **kwargs):
        candidates = original_resolve(*args, **kwargs)
        path.write_bytes(changed_raw)
        return candidates

    monkeypatch.setattr(loader, "resolve_admitted_pack", resolve_then_replace)

    loaded = load_admitted_pack_file_with_content(
        path,
        expected_pack_id=_PACK_ID,
        expected_artifact_sha256=pack["artifactSha256"],
        expected_sources=pins,
    )

    assert path.read_bytes() == changed_raw
    assert loaded.content.pack_sha256 == pack["artifactSha256"]
    assert loaded.content.lexemes[0].answer == "EWE"
    assert loaded.candidates[0]["answer"] == "EWE"


@pytest.mark.parametrize("loader", ["bytes", "file"])
def test_rejects_oversized_input_before_json_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, loader: str
) -> None:
    pack, pins = _fixture()
    monkeypatch.setattr("crossword.admitted_pack_loader.MAX_ADMITTED_PACK_BYTES", 8)
    raw = b"{" * 9

    def unexpected_parse(*_args, **_kwargs):
        raise AssertionError("oversized artifact reached JSON parsing")

    monkeypatch.setattr(json, "loads", unexpected_parse)
    if loader == "bytes":
        with pytest.raises(AdmittedPackLoadError, match="pack-size-limit-exceeded"):
            _load_bytes(raw, pack, pins)
    else:
        path = tmp_path / "oversized.json"
        path.write_bytes(raw)
        with pytest.raises(AdmittedPackLoadError, match="pack-size-limit-exceeded"):
            load_admitted_pack_file(
                path,
                expected_pack_id=_PACK_ID,
                expected_artifact_sha256=pack["artifactSha256"],
                expected_sources=pins,
            )


@pytest.mark.parametrize(
    ("raw", "error"),
    [
        (b"\xff", "pack-utf8-invalid"),
        (b"{bad json", "pack-json-invalid"),
        (b'{"outer":{"same":1,"same":2}}', "pack-json-duplicate-key"),
        (b'{"number":NaN}', "non-json-constant:NaN"),
    ],
)
def test_rejects_invalid_utf8_json_duplicate_keys_and_non_json_values(
    raw: bytes, error: str
) -> None:
    pack, pins = _fixture()

    with pytest.raises(AdmittedPackLoadError, match=error):
        _load_bytes(raw, pack, pins)


def test_requires_pack_and_complete_source_pins() -> None:
    pack, pins = _fixture()
    raw = canonical_json(pack)

    with pytest.raises(AdmittedPackLoadError, match="exact-source-pins-required"):
        load_admitted_pack_bytes(
            raw,
            expected_pack_id=_PACK_ID,
            expected_artifact_sha256=pack["artifactSha256"],
            expected_sources={},
        )


def test_rejects_wrong_expected_pack_digest_and_tampered_artifact() -> None:
    pack, pins = _fixture()
    raw = canonical_json(pack)
    with pytest.raises(AdmittedPackError, match="pack-artifact-digest-does-not-match-pin"):
        load_admitted_pack_bytes(
            raw,
            expected_pack_id=_PACK_ID,
            expected_artifact_sha256="0" * 64,
            expected_sources=pins,
        )

    tampered = dict(pack)
    tampered["lexemes"] = []
    tampered_raw = canonical_json(tampered)
    with pytest.raises(AdmittedPackError, match="pack-artifact-digest-mismatch"):
        _load_bytes(tampered_raw, pack, pins)


@pytest.mark.parametrize(
    ("source_change", "error"),
    [
        ({"sourceId": "not-pinned"}, "pack-source-id-not-pinned"),
        ({"artifactSha256": "0" * 64}, "pack-source-does-not-match-pin"),
    ],
)
def test_rejects_unpinned_or_wrong_source_identity(
    source_change: dict[str, str], error: str
) -> None:
    pack, pins = _fixture()
    changed = dict(pack)
    changed["sources"] = [dict(pack["sources"][0], **source_change)]
    _resign(changed)

    with pytest.raises(AdmittedPackError, match=error):
        load_admitted_pack_bytes(
            canonical_json(changed),
            expected_pack_id=_PACK_ID,
            expected_artifact_sha256=changed["artifactSha256"],
            expected_sources=pins,
        )


def test_cap_is_exactly_64_mib() -> None:
    assert MAX_ADMITTED_PACK_BYTES == 64 * 1024 * 1024
