"""Strict Flask-config boundary tests; all pack content is synthetic."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from crossword.admitted_pack import AdmittedPackContent, canonical_json
from crossword.admitted_pack_config import (
    MAX_SOURCE_PINS_JSON_BYTES,
    AdmittedPackConfigError,
    load_configured_admitted_candidates,
    load_configured_admitted_pack,
)
from crossword.admitted_pack_loader import LoadedAdmittedPack


_PACK_ID = "config-synthetic-pack"
_SOURCE_ID = "config-synthetic-source"
_SOURCE_BYTES = b"synthetic configuration loader fixture only"


def _fixture(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    source_digest = hashlib.sha256(_SOURCE_BYTES).hexdigest()
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
                "attribution": "Synthetic configuration-loader test data.",
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
                        "attribution": "Synthetic configuration-loader test data.",
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
    pack["artifactSha256"] = hashlib.sha256(
        canonical_json({key: value for key, value in pack.items() if key != "artifactSha256"})
    ).hexdigest()
    path = tmp_path / "synthetic-admitted-pack.json"
    path.write_bytes(canonical_json(pack))
    config = {
        "FUTURE_ADMITTED_PACK_PATH": str(path),
        "FUTURE_ADMITTED_PACK_ID": _PACK_ID,
        "FUTURE_ADMITTED_PACK_SHA256": pack["artifactSha256"],
        "FUTURE_ADMITTED_SOURCE_PINS_JSON": json.dumps(
            {
                _SOURCE_ID: {
                    "version": "fixture-v1",
                    "artifactSha256": source_digest,
                    "contentClass": "synthetic",
                }
            }
        ),
    }
    return pack, config


def _assert_config_unavailable(call) -> None:
    with pytest.raises(AdmittedPackConfigError) as error:
        call()
    assert error.value.code == "future-admitted-pack-unavailable"
    assert str(error.value) == error.value.code


def test_loads_candidates_from_exact_synthetic_flask_config(tmp_path: Path) -> None:
    _, config = _fixture(tmp_path)

    candidates = load_configured_admitted_candidates(config)

    assert len(candidates) == 1
    assert candidates[0]["candidateId"] == "lexeme-ewe"
    assert candidates[0]["answer"] == "EWE"
    assert candidates[0]["eligibility"]["packId"] == _PACK_ID


def test_candidate_compatibility_loader_does_not_require_content_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, config = _fixture(tmp_path)
    candidates = [{"candidateId": "legacy-candidate"}]
    calls = []

    def fake_load(path, *, expected_pack_id, expected_artifact_sha256, expected_sources):
        calls.append((path, expected_pack_id, expected_artifact_sha256, expected_sources))
        return candidates

    def unexpected_projection(*_args, **_kwargs):
        raise AssertionError("candidate-only compatibility path projected content")

    monkeypatch.setattr("crossword.admitted_pack_config.load_admitted_pack_file", fake_load)
    monkeypatch.setattr(
        "crossword.admitted_pack_config.load_admitted_pack_file_with_content",
        unexpected_projection,
    )

    assert load_configured_admitted_candidates(config) is candidates
    assert len(calls) == 1


def test_configured_pack_returns_content_from_same_pinned_artifact(tmp_path: Path) -> None:
    pack, config = _fixture(tmp_path)

    receipt = load_configured_admitted_pack(config)

    candidate = receipt.candidates[0]
    lexeme = receipt.content.lexemes[0]
    assert receipt.content.pack_id == receipt.pack_id == candidate["eligibility"]["packId"]
    assert receipt.content.pack_sha256 == receipt.pack_sha256 == candidate["eligibility"]["packVersion"]
    assert receipt.content.pack_sha256 == pack["artifactSha256"]
    assert receipt.source_pins == (
        {
            "sourceId": _SOURCE_ID,
            "version": "fixture-v1",
            "artifactSha256": hashlib.sha256(_SOURCE_BYTES).hexdigest(),
            "contentClass": "synthetic",
        },
    )
    assert candidate["eligibility"]["sourceIds"] == [
        lexeme.provenance["source"]["sourceId"]
    ] == [_SOURCE_ID]
    assert lexeme.lexeme_id == candidate["candidateId"]
    assert lexeme.answer == candidate["answer"]


def test_returns_sorted_config_receipt_with_candidates_from_one_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, config = _fixture(tmp_path)
    config["FUTURE_ADMITTED_SOURCE_PINS_JSON"] = json.dumps(
        {
            "zulu-source": {
                "version": "v2",
                "artifactSha256": "b" * 64,
                "contentClass": "public",
            },
            "alpha-source": {
                "version": "v1",
                "artifactSha256": "a" * 64,
                "contentClass": "synthetic",
            },
        }
    )
    candidates = [{"candidateId": "mock-candidate"}]
    content = AdmittedPackContent(
        pack_id=_PACK_ID,
        pack_sha256=config["FUTURE_ADMITTED_PACK_SHA256"],
        lexemes=(),
    )
    calls = []

    def fake_load(path, *, expected_pack_id, expected_artifact_sha256, expected_sources):
        calls.append((path, expected_pack_id, expected_artifact_sha256, expected_sources))
        return LoadedAdmittedPack(candidates=candidates, content=content)

    monkeypatch.setattr(
        "crossword.admitted_pack_config.load_admitted_pack_file_with_content", fake_load
    )

    receipt = load_configured_admitted_pack(config)

    assert receipt.candidates is candidates
    assert receipt.content is content
    assert receipt.pack_id == _PACK_ID
    assert receipt.pack_sha256 == config["FUTURE_ADMITTED_PACK_SHA256"]
    assert receipt.source_pins == (
        {
            "sourceId": "alpha-source",
            "version": "v1",
            "artifactSha256": "a" * 64,
            "contentClass": "synthetic",
        },
        {
            "sourceId": "zulu-source",
            "version": "v2",
            "artifactSha256": "b" * 64,
            "contentClass": "public",
        },
    )
    assert len(calls) == 1
    assert not hasattr(receipt, "path")


@pytest.mark.parametrize("config", [{}, {"FUTURE_ADMITTED_PACK_PATH": "/missing"}])
def test_missing_or_incomplete_settings_fail_with_stable_code(config: dict[str, Any]) -> None:
    _assert_config_unavailable(lambda: load_configured_admitted_candidates(config))


def test_wrong_pack_digest_pin_fails_closed(tmp_path: Path) -> None:
    _, config = _fixture(tmp_path)
    config["FUTURE_ADMITTED_PACK_SHA256"] = "0" * 64

    _assert_config_unavailable(lambda: load_configured_admitted_candidates(config))


def test_wrong_source_pin_fails_closed(tmp_path: Path) -> None:
    _, config = _fixture(tmp_path)
    config["FUTURE_ADMITTED_SOURCE_PINS_JSON"] = json.dumps(
        {
            _SOURCE_ID: {
                "version": "fixture-v1",
                "artifactSha256": "0" * 64,
                "contentClass": "synthetic",
            }
        }
    )

    _assert_config_unavailable(lambda: load_configured_admitted_candidates(config))


def test_duplicate_source_pin_json_key_fails_closed(tmp_path: Path) -> None:
    _, config = _fixture(tmp_path)
    pin = '{"version":"fixture-v1","artifactSha256":"' + "0" * 64 + '","contentClass":"synthetic"}'
    config["FUTURE_ADMITTED_SOURCE_PINS_JSON"] = (
        '{"' + _SOURCE_ID + '":' + pin + ',"' + _SOURCE_ID + '":' + pin + "}"
    )

    _assert_config_unavailable(lambda: load_configured_admitted_candidates(config))


def test_oversized_source_pin_json_fails_before_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, config = _fixture(tmp_path)
    config["FUTURE_ADMITTED_SOURCE_PINS_JSON"] = " " * (MAX_SOURCE_PINS_JSON_BYTES + 1)

    def unexpected_parse(*_args, **_kwargs):
        raise AssertionError("oversized pin JSON reached the parser")

    monkeypatch.setattr("crossword.admitted_pack_config.json.loads", unexpected_parse)
    _assert_config_unavailable(lambda: load_configured_admitted_candidates(config))


def test_source_pin_entries_require_exact_fields(tmp_path: Path) -> None:
    _, config = _fixture(tmp_path)
    config["FUTURE_ADMITTED_SOURCE_PINS_JSON"] = json.dumps(
        {
            _SOURCE_ID: {
                "version": "fixture-v1",
                "artifactSha256": "a" * 64,
                "contentClass": "synthetic",
                "unreviewedFallback": True,
            }
        }
    )

    _assert_config_unavailable(lambda: load_configured_admitted_candidates(config))
