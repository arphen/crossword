"""Synthetic-only tests for the fail-closed lexicon pack admission gate."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from tools.lexicon import pack_builder
from tools.lexicon.pack_builder import PackBuildError, build_from_file, build_pack


SYNTHETIC_SOURCE = (
    "Synthetic hand-authored lexicon fixture; CC0-1.0.\n"
    "lexeme:CATS = invented test surface\n"
    "sense:CATS-PLURAL = invented test gloss\n"
    "clue:CATS-1 = Purring pets\n"
).encode("utf-8")


def _grammar(*, clue_id: str = "clue-cats", text: str = "Purring pets") -> dict[str, Any]:
    return {
        "grammarVersion": "clue-grammar-v1",
        "clueId": clue_id,
        "entryId": "entry-1a",
        "clueText": text,
        "answer": "CATS",
        "variantRole": "standard",
        "primaryFamily": "definition",
        "morphology": {
            "clue": {"partOfSpeech": "noun", "number": "plural"},
            "answer": {"partOfSpeech": "noun", "number": "plural"},
            "substitutionWitness": {
                "frame": "We heard {0} outside.",
                "cluePhrase": text,
                "answerPhrase": "CATS",
                "editorialNote": "Both phrases are plural noun expressions.",
                "reviewerId": "synthetic-reviewer",
            },
        },
        "signalSpans": [],
    }


def _review(*references: str) -> dict[str, Any]:
    return {
        "admissionStatus": "reviewed",
        "reviewerId": "synthetic-reviewer",
        "reviewedAt": "2026-09-26",
        "evidenceRefs": list(references),
    }


def _manifest(tmp_path: Path) -> dict[str, Any]:
    (tmp_path / "synthetic-source.txt").write_bytes(SYNTHETIC_SOURCE)
    source = {
        "id": "synthetic-fixture",
        "version": "fixture-v1",
        "artifactPath": "synthetic-source.txt",
        "artifactSha256": hashlib.sha256(SYNTHETIC_SOURCE).hexdigest(),
        "spdx": "CC0-1.0",
        "licenseReview": "approved",
        "redistribution": "permitted",
        "admissionStatus": "approved",
        "attribution": "Hand-authored synthetic fixture; no attribution required.",
        "contentClass": "synthetic",
        "isPrivate": False,
        "historicalPrivate": False,
    }
    lexeme = {
        "id": "lexeme-cats",
        "headword": "CATS",
        "language": "en",
        "sourceId": source["id"],
        **_review("fixture:lexeme/CATS"),
    }
    sense = {
        "id": "sense-cats-plural",
        "lexemeId": lexeme["id"],
        "gloss": "More than one invented feline companion.",
        "resolutionStatus": "resolved",
        "sourceId": source["id"],
        **_review("fixture:sense/CATS-PLURAL"),
    }
    clue = {
        "id": "clue-cats",
        "text": "Purring pets",
        "senseId": sense["id"],
        "sourceId": source["id"],
        "grammar": _grammar(),
        **_review("fixture:clue/CATS-1"),
    }
    return {
        "schemaVersion": 1,
        "packId": "synthetic-cc0-test-pack",
        "admissionStatus": "approved",
        "sources": [source],
        "records": {
            "lexemes": [lexeme],
            "senses": [sense],
            "facts": [],
            "clues": [clue],
        },
    }


def test_admits_grounded_clue_with_complete_pinned_provenance(tmp_path: Path) -> None:
    pack = build_pack(_manifest(tmp_path), tmp_path)

    assert [item["id"] for item in pack["lexemes"]] == ["lexeme-cats"]
    assert [item["id"] for item in pack["senses"]] == ["sense-cats-plural"]
    assert [item["id"] for item in pack["clues"]] == ["clue-cats"]
    clue = pack["clues"][0]
    assert clue["evidence"] == {"type": "sense", "id": "sense-cats-plural"}
    assert clue["provenance"]["sources"] == [
        {
            "sourceId": "synthetic-fixture",
            "version": "fixture-v1",
            "artifactSha256": hashlib.sha256(SYNTHETIC_SOURCE).hexdigest(),
            "spdx": "CC0-1.0",
            "attribution": "Hand-authored synthetic fixture; no attribution required.",
            "contentClass": "synthetic",
        }
    ]
    assert clue["provenance"]["evidenceRefs"] == ["fixture:clue/CATS-1"]
    assert clue["provenance"]["evidenceProvenance"]["evidenceRefs"] == [
        "fixture:sense/CATS-PLURAL"
    ]
    assert clue["provenance"]["semanticTruthStatus"] == "not-established-by-grammar-validator"
    assert pack["quarantine"] == []


def test_build_hash_and_serialized_output_are_repeatable(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)

    first = build_pack(manifest, tmp_path)
    second = build_pack(copy.deepcopy(manifest), tmp_path)

    assert first == second
    assert first["artifactSha256"] == second["artifactSha256"]


def test_unresolved_sense_is_fill_only_and_cannot_ground_a_clue(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    sense = manifest["records"]["senses"][0]
    sense["resolutionStatus"] = "unresolved"
    sense["gloss"] = None

    pack = build_pack(manifest, tmp_path)

    assert pack["senses"][0]["fillOnly"] is True
    assert pack["senses"][0]["clueEligible"] is False
    assert pack["clues"] == []
    assert {
        (row["recordType"], row["recordId"], row["reasonCode"])
        for row in pack["quarantine"]
    } == {("clue", "clue-cats", "clue-sense-unresolved")}


@pytest.mark.parametrize(
    ("patch", "reason"),
    [
        ({"spdx": "NOASSERTION"}, "source-spdx-unasserted"),
        ({"licenseReview": "pending"}, "source-license-not-approved"),
        ({"redistribution": "unknown"}, "source-redistribution-not-permitted"),
        ({"historicalPrivate": True}, "source-historical-private-content"),
        ({"isPrivate": True}, "source-private-content"),
    ],
)
def test_source_policy_failures_quarantine_all_dependent_records(
    tmp_path: Path, patch: dict[str, Any], reason: str
) -> None:
    manifest = _manifest(tmp_path)
    manifest["sources"][0].update(patch)

    pack = build_pack(manifest, tmp_path)

    assert pack["sources"] == []
    assert pack["lexemes"] == []
    assert pack["clues"] == []
    assert {
        (row["recordType"], row["recordId"], row["reasonCode"])
        for row in pack["quarantine"]
    } >= {("source", "synthetic-fixture", reason)}


def test_pinned_artifact_digest_mismatch_blocks_records(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["sources"][0]["artifactSha256"] = "0" * 64

    pack = build_pack(manifest, tmp_path)

    assert pack["sources"] == []
    assert any(row["reasonCode"] == "source-artifact-sha256-mismatch" for row in pack["quarantine"])


def test_clue_must_link_to_eligible_reviewed_evidence(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["records"]["clues"][0]["senseId"] = "not-a-sense"

    pack = build_pack(manifest, tmp_path)

    assert pack["clues"] == []
    assert any(row["reasonCode"] == "clue-sense-ineligible" for row in pack["quarantine"])


def test_existing_clue_grammar_validator_is_a_hard_admission_gate(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    clue = manifest["records"]["clues"][0]
    clue["grammar"]["morphology"]["answer"]["number"] = "singular"

    pack = build_pack(manifest, tmp_path)

    assert pack["clues"] == []
    invalid = next(row for row in pack["quarantine"] if row["recordType"] == "clue")
    assert invalid["reasonCode"] == "clue-grammar-invalid"
    assert "morphology-mismatch" in invalid["details"]


def test_clue_can_be_grounded_in_a_reviewed_fact(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["records"]["facts"].append(
        {
            "id": "fact-cats",
            "lexemeId": "lexeme-cats",
            "statement": "The synthetic answer is written in plural form.",
            "sourceId": "synthetic-fixture",
            **_review("fixture:fact/CATS"),
        }
    )
    clue = manifest["records"]["clues"][0]
    clue.pop("senseId")
    clue["factId"] = "fact-cats"

    pack = build_pack(manifest, tmp_path)

    assert [item["id"] for item in pack["facts"]] == ["fact-cats"]
    assert pack["clues"][0]["evidence"] == {"type": "fact", "id": "fact-cats"}


def test_missing_grammar_runtime_fails_closed_for_clues_but_keeps_fill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pack_builder, "_run_clue_grammar", lambda _items: None)

    pack = build_pack(_manifest(tmp_path), tmp_path)

    assert [item["id"] for item in pack["lexemes"]] == ["lexeme-cats"]
    assert pack["clues"] == []
    assert any(
        row["reasonCode"] == "clue-grammar-validator-unavailable"
        for row in pack["quarantine"]
    )


def test_build_from_file_resolves_pinned_artifacts_relative_to_manifest(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    pack = build_from_file(path)

    assert len(pack["clues"]) == 1


def test_cli_refuses_to_overwrite_a_pinned_source_artifact(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    before = (tmp_path / "synthetic-source.txt").read_bytes()

    result = pack_builder.main([str(manifest_path), str(tmp_path / "synthetic-source.txt")])

    assert result == 2
    assert (tmp_path / "synthetic-source.txt").read_bytes() == before


def test_manifest_must_be_globally_approved() -> None:
    with pytest.raises(PackBuildError, match="manifest-not-approved"):
        build_pack(
            {"schemaVersion": 1, "packId": "x", "admissionStatus": "draft", "sources": [], "records": {"lexemes": [], "senses": [], "facts": [], "clues": []}},
            Path.cwd(),
        )
