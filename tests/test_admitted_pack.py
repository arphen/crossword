"""Synthetic-only tests for the product's admitted-pack resolver."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

import pytest

from crossword.admitted_pack import (
    AdmittedPackError,
    SourcePin,
    canonical_json,
    project_admitted_pack_content,
    resolve_admitted_pack,
)
from tools.lexicon.pack_builder import build_pack


_SOURCE_BYTES = b"Synthetic resolver test source only; CC0-1.0.\n"


def _grammar(clue_id: str = "clue-cats") -> dict[str, Any]:
    return {
        "grammarVersion": "clue-grammar-v1",
        "clueId": clue_id,
        "entryId": "entry-1a",
        "clueText": "Purring pets",
        "answer": "CATS",
        "variantRole": "standard",
        "primaryFamily": "definition",
        "morphology": {
            "clue": {"partOfSpeech": "noun", "number": "plural"},
            "answer": {"partOfSpeech": "noun", "number": "plural"},
            "substitutionWitness": {
                "frame": "We heard {0} outside.",
                "cluePhrase": "Purring pets",
                "answerPhrase": "CATS",
                "editorialNote": "Both phrases are plural noun expressions.",
                "reviewerId": "synthetic-reviewer",
            },
        },
        "signalSpans": [],
    }


def _review(reference: str) -> dict[str, Any]:
    return {
        "admissionStatus": "reviewed",
        "reviewerId": "synthetic-reviewer",
        "reviewedAt": "2026-09-26",
        "evidenceRefs": [reference],
    }


def _fixture(
    tmp_path: Path, *, include_fact: bool = False
) -> tuple[dict[str, Any], dict[str, SourcePin]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "synthetic.txt").write_bytes(_SOURCE_BYTES)
    source_digest = hashlib.sha256(_SOURCE_BYTES).hexdigest()
    source = {
        "id": "synthetic-resolver-source",
        "version": "fixture-v1",
        "artifactPath": "synthetic.txt",
        "artifactSha256": source_digest,
        "spdx": "CC0-1.0",
        "licenseReview": "approved",
        "redistribution": "permitted",
        "admissionStatus": "approved",
        "attribution": "Synthetic fixture only.",
        "contentClass": "synthetic",
        "isPrivate": False,
        "historicalPrivate": False,
    }
    manifest = {
        "schemaVersion": 1,
        "packId": "synthetic-resolver-pack",
        "admissionStatus": "approved",
        "sources": [source],
        "records": {
            "lexemes": [
                {
                    "id": "lexeme-cats",
                    "headword": "CATS",
                    "language": "en",
                    "sourceId": source["id"],
                    **_review("fixture:lexeme/CATS"),
                }
            ],
            "senses": [
                {
                    "id": "sense-cats",
                    "lexemeId": "lexeme-cats",
                    "gloss": "A synthetic plural animal word.",
                    "resolutionStatus": "resolved",
                    "sourceId": source["id"],
                    **_review("fixture:sense/CATS"),
                }
            ],
            "facts": (
                [
                    {
                        "id": "fact-cats",
                        "lexemeId": "lexeme-cats",
                        "statement": "A synthetic fact for projection testing.",
                        "sourceId": source["id"],
                        **_review("fixture:fact/CATS"),
                    }
                ]
                if include_fact
                else []
            ),
            "clues": [
                {
                    "id": "clue-cats",
                    "text": "Purring pets",
                    "senseId": "sense-cats",
                    "sourceId": source["id"],
                    "grammar": _grammar(),
                    **_review("fixture:clue/CATS"),
                },
                *(
                    [
                        {
                            "id": "clue-fact-cats",
                            "text": "Purring pets",
                            "factId": "fact-cats",
                            "grammar": _grammar("clue-fact-cats"),
                            "sourceId": source["id"],
                            **_review("fixture:clue/fact-CATS"),
                        }
                    ]
                    if include_fact
                    else []
                ),
            ],
        },
    }
    pack = build_pack(manifest, tmp_path)
    pins = {
        source["id"]: SourcePin(
            version=source["version"],
            artifact_sha256=source_digest,
            content_class="synthetic",
        )
    }
    return pack, pins


def _resign(pack: dict[str, Any]) -> None:
    pack["artifactSha256"] = hashlib.sha256(
        canonical_json({key: value for key, value in pack.items() if key != "artifactSha256"})
    ).hexdigest()


def _resolve(pack: dict[str, Any], pins: dict[str, SourcePin]) -> list[dict[str, Any]]:
    return resolve_admitted_pack(
        pack,
        expected_pack_id="synthetic-resolver-pack",
        expected_artifact_sha256=pack["artifactSha256"],
        expected_sources=pins,
    )


def test_resolves_only_pinned_admitted_lexemes_and_defaults_to_broad(tmp_path: Path) -> None:
    pack, pins = _fixture(tmp_path)

    candidates = _resolve(pack, pins)

    assert candidates == [
        {
            "candidateId": "lexeme-cats",
            "answer": "CATS",
            "language": "en",
            "conceptIds": [],
            "knowledgeTaskIds": [],
            "associationIds": [],
            "pool": "broad",
            "eligibility": {
                "status": "eligible",
                "packId": "synthetic-resolver-pack",
                "packVersion": pack["artifactSha256"],
                "sourceIds": ["synthetic-resolver-source"],
            },
        }
    ]


def test_maps_only_explicit_personalization_ids(tmp_path: Path) -> None:
    pack, pins = _fixture(tmp_path)
    pack["lexemes"][0]["personalization"] = {
        "conceptIds": ["concept:architecture"],
        "knowledgeTaskIds": ["task:german:haus"],
        "associationIds": ["association:blue-window"],
        "pool": "exploration",
    }
    _resign(pack)

    candidate = _resolve(pack, pins)[0]

    assert candidate["conceptIds"] == ["concept:architecture"]
    assert candidate["knowledgeTaskIds"] == ["task:german:haus"]
    assert candidate["associationIds"] == ["association:blue-window"]
    assert candidate["pool"] == "exploration"


def test_rejects_self_hashed_pack_without_matching_out_of_band_digest(tmp_path: Path) -> None:
    pack, pins = _fixture(tmp_path)
    pack["lexemes"][0]["headword"] = "DOGS"
    _resign(pack)

    with pytest.raises(AdmittedPackError, match="pack-artifact-digest-does-not-match-pin"):
        resolve_admitted_pack(
            pack,
            expected_pack_id="synthetic-resolver-pack",
            expected_artifact_sha256="0" * 64,
            expected_sources=pins,
        )


def test_rejects_bad_canonical_digest_even_when_expected_pin_matches(tmp_path: Path) -> None:
    pack, pins = _fixture(tmp_path)
    pack["lexemes"][0]["headword"] = "DOGS"

    with pytest.raises(AdmittedPackError, match="pack-artifact-digest-mismatch"):
        _resolve(pack, pins)


def test_resolver_reapplies_strict_answer_safety_to_stored_clue_artifacts(
    tmp_path: Path,
) -> None:
    pack, pins = _fixture(tmp_path)
    clue = pack["clues"][0]
    clue["text"] = "Shades of cat"
    clue["grammar"]["clueText"] = clue["text"]
    clue["grammar"]["morphology"]["substitutionWitness"]["cluePhrase"] = clue[
        "text"
    ]
    _resign(pack)

    with pytest.raises(AdmittedPackError, match="clue-grammar-invalid"):
        _resolve(pack, pins)


def test_rejects_wrong_source_hash_or_id(tmp_path: Path) -> None:
    pack, pins = _fixture(tmp_path)
    pack["sources"][0]["artifactSha256"] = "0" * 64
    _resign(pack)

    with pytest.raises(AdmittedPackError, match="pack-source-does-not-match-pin"):
        _resolve(pack, pins)

    pack, pins = _fixture(tmp_path / "next")
    pack["sources"][0]["sourceId"] = "untrusted-source"
    _resign(pack)
    with pytest.raises(AdmittedPackError, match="pack-source-id-not-pinned"):
        _resolve(pack, pins)


@pytest.mark.parametrize(
    ("collection", "field", "value", "reason"),
    [
        ("senses", "lexemeId", "missing-lexeme", "sense-lexeme-reference-invalid"),
        ("facts", "lexemeId", "missing-lexeme", "fact-lexeme-reference-invalid"),
        ("clues", "answerLexemeId", "missing-lexeme", "clue-lexeme-reference-invalid"),
        ("clues", "evidence", {"type": "sense", "id": "missing-sense"}, "clue-sense-reference-invalid"),
    ],
)
def test_rejects_dangling_cross_references(
    tmp_path: Path, collection: str, field: str, value: Any, reason: str
) -> None:
    pack, pins = _fixture(tmp_path)
    if collection == "facts":
        pack["facts"] = [
            {
                "id": "fact-orphan",
                "lexemeId": "lexeme-cats",
                "statement": "A synthetic fact.",
                "provenance": copy.deepcopy(pack["senses"][0]["provenance"]),
            }
        ]
    pack[collection][0][field] = value
    _resign(pack)

    with pytest.raises(AdmittedPackError, match=reason):
        _resolve(pack, pins)


def test_rejects_malformed_grammar_metadata_and_validator_failures(tmp_path: Path) -> None:
    pack, pins = _fixture(tmp_path)
    pack["clues"][0]["grammar"]["answer"] = "DOGS"
    _resign(pack)
    with pytest.raises(AdmittedPackError, match="clue-grammar-metadata-invalid"):
        _resolve(pack, pins)

    pack, pins = _fixture(tmp_path / "next")
    pack["clues"][0]["grammar"]["morphology"]["answer"]["number"] = "singular"
    _resign(pack)
    with pytest.raises(AdmittedPackError, match="clue-grammar-invalid"):
        _resolve(pack, pins)


def test_never_trusts_caller_eligibility_assertions(tmp_path: Path) -> None:
    pack, pins = _fixture(tmp_path)
    pack["lexemes"][0]["eligibility"] = {"status": "eligible", "sourceIds": ["fake"]}
    _resign(pack)

    with pytest.raises(AdmittedPackError, match="lexeme-record-shape-invalid"):
        _resolve(pack, pins)


def test_projects_only_reviewed_content_with_exact_immutable_provenance(tmp_path: Path) -> None:
    pack, pins = _fixture(tmp_path, include_fact=True)

    content = project_admitted_pack_content(
        pack,
        expected_pack_id="synthetic-resolver-pack",
        expected_artifact_sha256=pack["artifactSha256"],
        expected_sources=pins,
    )

    assert content.pack_id == "synthetic-resolver-pack"
    assert content.pack_sha256 == pack["artifactSha256"]
    assert len(content.lexemes) == 1
    lexeme = content.lexemes[0]
    assert (lexeme.lexeme_id, lexeme.answer, lexeme.language) == ("lexeme-cats", "CATS", "en")
    assert lexeme.senses[0].sense_id == "sense-cats"
    assert lexeme.senses[0].gloss == "A synthetic plural animal word."
    assert lexeme.senses[0].provenance["evidenceRefs"] == ("fixture:sense/CATS",)
    assert lexeme.facts[0].statement == "A synthetic fact for projection testing."
    assert lexeme.facts[0].provenance["source"]["sourceId"] == "synthetic-resolver-source"
    clue = next(row for row in lexeme.clues if row.clue_id == "clue-fact-cats")
    assert (clue.evidence_type, clue.evidence_id) == ("fact", "fact-cats")
    assert clue.grammar["morphology"]["answer"]["number"] == "plural"
    assert clue.provenance["evidenceProvenance"]["evidenceRefs"] == ("fixture:fact/CATS",)
    assert not hasattr(content, "quarantine")

    with pytest.raises(TypeError):
        clue.provenance["evidenceProvenance"]["source"]["sourceId"] = "rewritten"
    pack["facts"][0]["statement"] = "mutated after projection"
    assert lexeme.facts[0].statement == "A synthetic fact for projection testing."


def test_content_projection_preserves_explicit_personalization_links(tmp_path: Path) -> None:
    pack, pins = _fixture(tmp_path)
    pack["lexemes"][0]["personalization"] = {
        "conceptIds": ["topic:animals", "topic:zoology"],
        "knowledgeTaskIds": ["task:taxonomy"],
        "associationIds": ["assoc:field-notes"],
        "pool": "exploration",
    }
    _resign(pack)

    content = project_admitted_pack_content(
        pack,
        expected_pack_id="synthetic-resolver-pack",
        expected_artifact_sha256=pack["artifactSha256"],
        expected_sources=pins,
    )

    lexeme = content.lexemes[0]
    assert lexeme.concept_ids == ("topic:animals", "topic:zoology")
    assert lexeme.knowledge_task_ids == ("task:taxonomy",)
    assert lexeme.association_ids == ("assoc:field-notes",)
    assert lexeme.pool == "exploration"


def test_content_projection_rejects_unpinned_and_malformed_content(tmp_path: Path) -> None:
    pack, pins = _fixture(tmp_path)
    wrong_pins = {
        "synthetic-resolver-source": SourcePin(
            version="fixture-v1",
            artifact_sha256="0" * 64,
            content_class="synthetic",
        )
    }
    with pytest.raises(AdmittedPackError, match="pack-source-does-not-match-pin"):
        project_admitted_pack_content(
            pack,
            expected_pack_id="synthetic-resolver-pack",
            expected_artifact_sha256=pack["artifactSha256"],
            expected_sources=wrong_pins,
        )

    pack["clues"][0]["unreviewedPrompt"] = "Synthetic raw fixture field."
    _resign(pack)
    with pytest.raises(AdmittedPackError, match="clue-record-shape-invalid"):
        project_admitted_pack_content(
            pack,
            expected_pack_id="synthetic-resolver-pack",
            expected_artifact_sha256=pack["artifactSha256"],
            expected_sources=pins,
        )


def test_content_projection_rejects_casefold_answer_ambiguity(tmp_path: Path) -> None:
    pack, pins = _fixture(tmp_path)
    pack["lexemes"].append(
        {
            "id": "lexeme-cats-case-variant",
            "headword": "cats",
            "language": "en",
            "provenance": copy.deepcopy(pack["lexemes"][0]["provenance"]),
        }
    )
    _resign(pack)

    with pytest.raises(AdmittedPackError, match="content-answer-normalization-ambiguous"):
        project_admitted_pack_content(
            pack,
            expected_pack_id="synthetic-resolver-pack",
            expected_artifact_sha256=pack["artifactSha256"],
            expected_sources=pins,
        )
