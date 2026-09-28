"""Contract tests for the local synthetic language review fixtures."""

from copy import deepcopy
import hashlib
import json

import pytest

from src.crossword.language_task_pack import (
    LANGUAGE_TASK_PACK_ID,
    LANGUAGE_TASK_PACK_SCHEMA_VERSION,
    LANGUAGE_TASK_PACK_STATUS,
    SYNTHETIC_LANGUAGE_TASK_PACK,
    LanguageTaskPackError,
    REVIEWED_LANGUAGE_TASK_PACK_STATUS,
    build_synthetic_language_task_pack,
    language_task_pack_summary,
    load_reviewed_language_task_pack,
    private_display_text_for_review,
    reviewed_display_text_for_review,
    task_pair_for_review,
    validate_reviewed_language_task_pack,
    validate_language_task_pack,
)


def reviewed_pack_fixture():
    pair = deepcopy(
        next(
            pair
            for pair in SYNTHETIC_LANGUAGE_TASK_PACK["pairs"]
            if pair["language"] == "de"
        )
    )
    source_id = "reviewed-language-source-fixture-v1"
    pair["reviewStatus"] = REVIEWED_LANGUAGE_TASK_PACK_STATUS
    pair["displayText"] = pair["targetText"]
    pair["source"] = {
        "sourceId": source_id,
        "version": "fixture-review-2026-09-28",
        "contentClass": "reviewed",
        "admissionStatus": "admitted",
        "attribution": "Test-only reviewed language fixture",
        "semanticStatus": "reviewed",
        "artifactSha256": "a" * 64,
        "license": "CC0-1.0",
        "reviewerId": "reviewer-fixture",
        "reviewedAt": "2026-09-28T00:00:00.000Z",
    }
    pair["grammar"] = {
        **pair["grammar"],
        "semanticStatus": "reviewed",
    }
    pack = {
        "schemaVersion": LANGUAGE_TASK_PACK_SCHEMA_VERSION,
        "packId": "reviewed-language-fixture-v1",
        "status": REVIEWED_LANGUAGE_TASK_PACK_STATUS,
        "sourceId": source_id,
        "grammarVersion": "language-task-grammar-v1",
        "pairs": [pair],
    }
    pack["packDigest"] = hashlib.sha256(
        json.dumps(
            pack,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return pack


def test_synthetic_pack_is_deterministic_and_carries_unadmitted_provenance():
    first = build_synthetic_language_task_pack()
    second = build_synthetic_language_task_pack()
    assert first == second == SYNTHETIC_LANGUAGE_TASK_PACK
    assert first["schemaVersion"] == LANGUAGE_TASK_PACK_SCHEMA_VERSION
    assert first["packId"] == LANGUAGE_TASK_PACK_ID
    assert first["status"] == LANGUAGE_TASK_PACK_STATUS == "synthetic-unadmitted"
    assert {pair["language"] for pair in first["pairs"]} == {
        "de",
        "es",
        "fr",
        "it",
        "ja",
        "nl",
        "pt",
    }
    assert len(first["pairs"]) == 22
    assert all(
        pair["source"]["contentClass"] == "synthetic"
        and pair["source"]["admissionStatus"] == "unadmitted"
        and pair["grammar"]["semanticStatus"] == "not-established"
        for pair in first["pairs"]
    )


def test_validator_rejects_digest_or_metadata_mutation():
    malformed = deepcopy(SYNTHETIC_LANGUAGE_TASK_PACK)
    malformed["pairs"][0]["grammar"]["number"] = "plural"
    with pytest.raises(LanguageTaskPackError, match="digest-mismatch"):
        validate_language_task_pack(malformed)

    malformed = deepcopy(SYNTHETIC_LANGUAGE_TASK_PACK)
    malformed["packDigest"] = "0" * 64
    with pytest.raises(LanguageTaskPackError, match="digest-mismatch"):
        validate_language_task_pack(malformed)


def test_review_projection_is_answer_free_and_keeps_source_grammar_metadata():
    item = task_pair_for_review("de", "ja")
    assert item is not None
    assert item["pairId"] == "de-en-ja-v1"
    assert item["sourceText"] == "yes"
    assert item["targetLanguage"] == "de"
    assert item["reviewStatus"] == "synthetic-unadmitted"
    assert item["source"]["sourceId"]
    assert item["grammar"]["version"] == "language-task-grammar-v1"
    assert "targetText" not in item
    named = task_pair_for_review("French", "OUI")
    assert named is not None
    assert named["pairId"] == "fr-en-oui-v1"
    assert named["sourceText"] == "yes"
    assert task_pair_for_review("fr", "not-in-fixture") is None
    spanish = task_pair_for_review("es", "SI")
    assert spanish is not None
    assert spanish["sourceText"] == "yes"
    assert spanish["targetLanguage"] == "es"
    japanese = task_pair_for_review("ja", "HAI")
    assert japanese is not None
    assert japanese["targetLanguage"] == "ja"
    dutch = task_pair_for_review("nl", "HUIS")
    assert dutch is not None
    assert dutch["sourceText"] == "house"
    assert dutch["targetLanguage"] == "nl"


def test_reviewed_pack_requires_explicit_admission_provenance_and_can_be_loaded(
    tmp_path, monkeypatch
):
    pack = reviewed_pack_fixture()
    assert validate_reviewed_language_task_pack(pack) == pack
    path = tmp_path / "reviewed-language-pack.json"
    path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CROSSWORD_REVIEWED_LANGUAGE_TASK_PACK", str(path))
    assert load_reviewed_language_task_pack() == pack
    item = task_pair_for_review("de", "JA")
    assert item is not None
    assert item["packId"] == "reviewed-language-fixture-v1"
    assert item["reviewStatus"] == REVIEWED_LANGUAGE_TASK_PACK_STATUS
    assert item["source"]["admissionStatus"] == "admitted"
    assert item["grammar"]["semanticStatus"] == "reviewed"
    assert "targetText" not in item


def test_invalid_configured_reviewed_pack_falls_back_to_explicit_synthetic_fixture(
    tmp_path, monkeypatch
):
    path = tmp_path / "invalid-language-pack.json"
    path.write_text("{\"status\": \"reviewed-admitted\"}", encoding="utf-8")
    monkeypatch.setenv("CROSSWORD_REVIEWED_LANGUAGE_TASK_PACK", str(path))
    with pytest.raises(LanguageTaskPackError):
        load_reviewed_language_task_pack()
    item = task_pair_for_review("de", "JA")
    assert item is not None
    assert item["packId"] == LANGUAGE_TASK_PACK_ID
    assert item["reviewStatus"] == LANGUAGE_TASK_PACK_STATUS


def test_pack_summary_reports_reviewed_or_safe_fallback_state(tmp_path, monkeypatch):
    monkeypatch.delenv("CROSSWORD_REVIEWED_LANGUAGE_TASK_PACK", raising=False)
    default = language_task_pack_summary()
    assert default["configuration"] == "default-synthetic"
    assert default["status"] == LANGUAGE_TASK_PACK_STATUS

    pack = reviewed_pack_fixture()
    path = tmp_path / "reviewed-language-pack.json"
    path.write_text(json.dumps(pack), encoding="utf-8")
    monkeypatch.setenv("CROSSWORD_REVIEWED_LANGUAGE_TASK_PACK", str(path))
    reviewed = language_task_pack_summary()
    assert reviewed["configuration"] == "configured"
    assert reviewed["status"] == REVIEWED_LANGUAGE_TASK_PACK_STATUS
    assert reviewed["languages"] == ["de"]


def test_reviewed_display_spelling_is_explicit_and_one_cell_compatible(
    tmp_path, monkeypatch
):
    pack = reviewed_pack_fixture()
    pair = pack["pairs"][0]
    pair.update(
        {
            "pairId": "fr-en-cafe-v1",
            "language": "fr",
            "sourceText": "coffee",
            "targetText": "CAFE",
            "displayText": "CAFÉ",
        }
    )
    without_digest = deepcopy(pack)
    without_digest.pop("packDigest")
    pack["packDigest"] = hashlib.sha256(
        json.dumps(
            without_digest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    path = tmp_path / "reviewed-language-pack.json"
    path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CROSSWORD_REVIEWED_LANGUAGE_TASK_PACK", str(path))
    assert reviewed_display_text_for_review("fr", "CAFE") == "CAFÉ"
    # The due-card projection deliberately does not leak this display answer.
    item = task_pair_for_review("fr", "CAFE")
    assert item is not None
    assert "displayText" not in item


def test_private_display_spelling_has_an_explicit_synthetic_fallback(monkeypatch):
    monkeypatch.delenv("CROSSWORD_REVIEWED_LANGUAGE_TASK_PACK", raising=False)
    assert private_display_text_for_review("French", "cafe") == (
        "CAFÉ",
        "synthetic-unadmitted",
    )
    assert private_display_text_for_review("German", "HAUS") == (None, None)
