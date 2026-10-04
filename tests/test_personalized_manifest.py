from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

from src.crossword.admitted_pack import (
    AdmittedClueContent,
    AdmittedLexemeContent,
    AdmittedPackContent,
    AdmittedSenseContent,
)
from src.crossword.personalized_manifest import (
    PersonalizedManifestRejected,
    _digest,
    _frozen_json_digest,
    build_personalized_manifest,
    derive_xfill_slots,
    validate_personalized_manifest,
)


SOURCE_ID = "synthetic-source"
SOURCE_DIGEST = "a" * 64
PACK_DIGEST = "b" * 64
SOURCE = {
    "sourceId": SOURCE_ID,
    "version": "synthetic-v1",
    "artifactSha256": SOURCE_DIGEST,
    "spdx": "CC0-1.0",
    "attribution": "Synthetic fixture only.",
    "contentClass": "synthetic",
}


def _provenance(reference: str) -> MappingProxyType:
    return MappingProxyType({
        "source": MappingProxyType(dict(SOURCE)),
        "evidenceRefs": (reference,),
        "reviewerId": "synthetic-reviewer",
        "reviewedAt": "2026-09-26",
    })


def _content() -> AdmittedPackContent:
    words = ("CAT", "ARE", "TEN")
    lexemes = []
    for word in words:
        lexeme_id = f"lexeme-{word.lower()}"
        sense_id = f"sense-{word.lower()}"
        sense_provenance = _provenance(f"fixture:sense/{word}")
        sense = AdmittedSenseContent(
            sense_id=sense_id,
            gloss=f"A synthetic sense for {word}.",
            resolution_status="resolved",
            clue_eligible=True,
            fill_only=False,
            provenance=sense_provenance,
        )
        grammar = MappingProxyType({
            "grammarVersion": "clue-grammar-v1",
            "clueId": f"clue-{word.lower()}",
            "entryId": "source-entry",
            "clueText": f"Synthetic word-square clue for {word}",
            "answer": word,
            "variantRole": "standard",
            "primaryFamily": "definition",
            "morphology": MappingProxyType({
                "clue": MappingProxyType({"partOfSpeech": "noun", "number": "singular"}),
                "answer": MappingProxyType({"partOfSpeech": "noun", "number": "singular"}),
                "substitutionWitness": MappingProxyType({
                    "frame": "A synthetic answer: {0}.",
                    "cluePhrase": f"Synthetic word-square clue for {word}",
                    "answerPhrase": word,
                    "editorialNote": "Synthetic manifest fixture only.",
                    "reviewerId": "synthetic-reviewer",
                }),
            }),
            "signalSpans": (),
        })
        clue_provenance = MappingProxyType({
            "sources": (MappingProxyType(dict(SOURCE)),),
            "evidenceRefs": (f"fixture:clue/{word}",),
            "evidenceProvenance": sense_provenance,
            "reviewerId": "synthetic-reviewer",
            "reviewedAt": "2026-09-26",
            "semanticTruthStatus": "not-established-by-grammar-validator",
        })
        clue = AdmittedClueContent(
            clue_id=f"clue-{word.lower()}",
            text=f"Synthetic word-square clue for {word}",
            answer_lexeme_id=lexeme_id,
            evidence_type="sense",
            evidence_id=sense_id,
            grammar=grammar,
            provenance=clue_provenance,
        )
        lexemes.append(AdmittedLexemeContent(
            lexeme_id=lexeme_id,
            answer=word,
            language="en",
            provenance=_provenance(f"fixture:lexeme/{word}"),
            senses=(sense,),
            facts=(),
            clues=(clue,),
        ))
    return AdmittedPackContent(
        pack_id="synthetic-pack",
        pack_sha256=PACK_DIGEST,
        lexemes=tuple(lexemes),
    )


def _grid() -> dict:
    fill = [
        "CAT############",
        "ARE############",
        "TEN############",
        *["###############"] * 12,
    ]
    slots = derive_xfill_slots(fill)
    return {
        "fill": fill,
        "entries": [
            {
                "num": slot.number,
                "dir": "A" if slot.direction == "across" else "D",
                "answer": slot.answer,
                "theme": False,
            }
            for slot in slots
        ],
    }


def _job() -> dict:
    job = {
        "version": 4,
        "profileId": "profile-synthetic",
        "weekdayDifficulty": "Wednesday",
        "puzzleLanguage": "en",
        "epistemeRevision": 3,
        "epistemeDigest": "c" * 64,
        "packId": "synthetic-pack",
        "packSha256": PACK_DIGEST,
        "sourcePins": [{
            "sourceId": SOURCE_ID,
            "version": SOURCE["version"],
            "artifactSha256": SOURCE_DIGEST,
            "contentClass": "synthetic",
        }],
        "seed": 4,
        "recipe": "admitted-xfill-wide-v1",
        "asOf": "2026-09-26T12:00:00.000Z",
        "briefCompilerVersion": "compile-episteme-brief-v1",
    }
    evidence_by_candidate = {
        f"lexeme-{word.lower()}": [f"retrieval-evidence-lexeme-{word.lower()}"]
        for word in ("CAT", "ARE", "TEN")
    }
    brief = {
        "briefVersion": "episteme-brief-v1",
        "profileId": job["profileId"],
        "profileRevision": job["epistemeRevision"],
        "asOf": job["asOf"],
        "mode": "play",
        "language": job["puzzleLanguage"],
        "selectionLimit": 3,
        "selected": [
            {"candidate": {"candidateId": candidate_id}, "evidenceIds": evidence_ids}
            for candidate_id, evidence_ids in evidence_by_candidate.items()
        ],
        "selectionLog": [
            {"candidateId": candidate_id, "evidenceIds": evidence_ids, "selected": True}
            for candidate_id, evidence_ids in evidence_by_candidate.items()
        ],
    }
    job["compiledBrief"] = brief
    job["compiledBriefDigest"] = _frozen_json_digest(brief)
    return job


def _version_inputs() -> dict:
    return {
        "generatedAt": "2026-09-26T12:00:00.000Z",
        "recipe": {"id": "admitted-xfill-wide-v1", "version": "1", "weekday": "Wednesday"},
        "runtime": {"id": "xfill-local", "version": "0.1.1", "artifactDigest": "d" * 64},
        "validators": [
            {"id": "personalized-manifest", "version": "1"},
            {"id": "admitted-content", "version": "1"},
        ],
    }


def _links(grid: dict | None = None) -> list[dict]:
    grid = grid or _grid()
    entries = grid["entries"]
    links = []
    for index, entry in enumerate(entries):
        answer = entry["answer"]
        lexeme_id = f"lexeme-{answer.lower()}"
        links.append({
            "entryNumber": entry["num"],
            "direction": "across" if entry["dir"] == "A" else "down",
            "answer": answer,
            "candidateIds": [lexeme_id],
            "sourceIds": [SOURCE_ID],
            "clueId": f"clue-{answer.lower()}",
            "senseId": f"sense-{answer.lower()}",
            "profileEvidenceIds": [f"retrieval-evidence-{lexeme_id}"],
        })
    return links


def _build(grid: dict | None = None, links: list[dict] | None = None, content=None):
    grid = grid or _grid()
    return build_personalized_manifest(
        grid,
        _links(grid) if links is None else links,
        content=content or _content(),
        frozen_job=_job(),
        version_inputs=_version_inputs(),
    )


def _plain_json(value):
    if hasattr(value, "items"):
        return {str(key): _plain_json(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(child) for child in value]
    return value


def test_builds_review_candidate_with_exact_grid_and_separate_private_profile_evidence():
    result = _build()
    manifest = result.manifest

    assert result.playable is False
    assert validate_personalized_manifest(manifest)
    assert manifest["quality"]["verdict"] == "review"
    assert manifest["quality"]["reasons"] == (
        "crossing-support-uncalibrated",
        "semantic-truth-not-established",
    )
    assert len(manifest["cells"]) == 225
    assert len(manifest["entries"]) == 6
    assert len(manifest["crossingSupport"]["edges"]) == 9
    assert manifest["provenance"]["sources"][0]["artifactSha256"] == SOURCE_DIGEST
    assert all("retrieval-evidence" not in str(clue) for clue in manifest["clues"])
    assert result.private_selection[0]["profileEvidenceIds"] == ("retrieval-evidence-lexeme-cat",)
    assert result.private_selection[0]["clueId"] == "clue-cat"
    assert result.private_selection[0]["clueVariantId"] == "clue-cat@1a"

    golden_path = Path(__file__).parent / "fixtures" / "personalized-review-v2.json"
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    assert _plain_json(manifest) == golden

    small_float = _plain_json(manifest)
    small_float["crossingSupport"]["version"] = "simulated-support-estimate-v1"
    for edge in small_float["crossingSupport"]["edges"]:
        edge["score"] = 1e-7
    small_float["crossingSupport"]["minimumScore"] = 1e-7
    small_float["crossingSupport"]["meanScore"] = 1e-7
    assert _digest({key: value for key, value in small_float.items() if key != "integrity"}) == (
        "sha256:5aa01bc48f330747694dce978c837199087a8dc8cb9fbb159e01355a142db583"
    )


def test_grid_derivation_rejects_unchecked_cells_and_short_runs():
    fill = ["CAT############", "A##############", "TEN############", *["###############"] * 12]
    with pytest.raises(PersonalizedManifestRejected, match="grid-entry-too-short|grid-open-cell-incomplete-coverage"):
        derive_xfill_slots(fill)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda grid: grid["entries"][0].update(answer="DOG"), "xfill-entry-grid-mismatch"),
        (lambda grid: grid["entries"].pop(), "xfill-entry-count-mismatch"),
        (lambda grid: grid.update(fill=["CAT############"]), "grid-fill-invalid"),
    ],
)
def test_rejects_malformed_or_grid_inconsistent_xfill_result(change, message):
    grid = _grid()
    change(grid)
    with pytest.raises(PersonalizedManifestRejected, match=message):
        _build(grid)


def test_rejects_missing_or_ambiguous_candidate_and_unpinned_language():
    links = _links()
    links[0]["candidateIds"] = []
    with pytest.raises(PersonalizedManifestRejected, match="entry-candidate-ambiguous"):
        _build(links=links)

    links = _links()
    links[0]["candidateIds"] = ["lexeme-cat", "lexeme-are"]
    with pytest.raises(PersonalizedManifestRejected, match="entry-candidate-ambiguous"):
        _build(links=links)

    job = _job()
    job["puzzleLanguage"] = "fr"
    job["compiledBrief"] = dict(job["compiledBrief"], language="fr")
    job["compiledBriefDigest"] = _frozen_json_digest(job["compiledBrief"])
    with pytest.raises(PersonalizedManifestRejected, match="entry-candidate-answer-or-language-mismatch"):
        build_personalized_manifest(
            _grid(), _links(), content=_content(), frozen_job=job, version_inputs=_version_inputs()
        )


def test_rejects_missing_clue_mismatched_source_pin_and_unreviewed_semantic_status():
    links = _links()
    links[0]["clueId"] = "no-such-clue"
    with pytest.raises(PersonalizedManifestRejected, match="entry-clue-missing-or-ambiguous"):
        _build(links=links)

    links = _links()
    links[0]["sourceIds"] = ["other-source"]
    with pytest.raises(PersonalizedManifestRejected, match="entry-candidate-source-pin-mismatch"):
        _build(links=links)

    content = _content()
    lexemes = list(content.lexemes)
    first = lexemes[0]
    changed = dict(first.clues[0].provenance)
    changed["semanticTruthStatus"] = "unreviewed"
    lexemes[0] = replace(first, clues=(replace(first.clues[0], provenance=changed),))
    changed_content = replace(content, lexemes=tuple(lexemes))
    with pytest.raises(PersonalizedManifestRejected, match="entry-clue-semantic-status-unrecognized"):
        _build(content=changed_content)


@pytest.mark.parametrize("generated_at", ["yesterday", "2026-02-31T12:00:00Z", "2026-09-26T12:00:00"])
def test_rejects_generated_at_values_that_the_v2_domain_contract_would_reject(generated_at):
    versions = _version_inputs()
    versions["generatedAt"] = generated_at
    with pytest.raises(PersonalizedManifestRejected, match="manifest-generated-at-invalid"):
        build_personalized_manifest(
            _grid(), _links(), content=_content(), frozen_job=_job(), version_inputs=versions
        )


@pytest.mark.parametrize(
    ("target", "field", "change", "message"),
    [
        ("recipe", "weekday", "remove", "manifest-recipe-shape-invalid"),
        ("recipe", "unexpected", "add", "manifest-recipe-shape-invalid"),
        ("runtime", "version", "remove", "manifest-runtime-shape-invalid"),
        ("runtime", "unexpected", "add", "manifest-runtime-shape-invalid"),
        ("validator", "version", "remove", "manifest-validator-shape-invalid"),
        ("validator", "unexpected", "add", "manifest-validator-shape-invalid"),
    ],
)
def test_builder_rejects_malformed_nested_receipt_version_records(target, field, change, message):
    versions = _version_inputs()
    record = versions["validators"][0] if target == "validator" else versions[target]
    if change == "remove":
        record.pop(field)
    else:
        record[field] = "unexpected-value"

    with pytest.raises(PersonalizedManifestRejected, match=message):
        build_personalized_manifest(
            _grid(), _links(), content=_content(), frozen_job=_job(), version_inputs=versions
        )


def test_manifest_validator_rejects_malformed_nested_receipt_even_with_matching_digest():
    altered = _plain_json(_build().manifest)
    altered["receipt"]["runtime"]["unexpected"] = "rejected"
    altered["integrity"]["value"] = _digest(
        {key: value for key, value in altered.items() if key != "integrity"}
    )
    with pytest.raises(PersonalizedManifestRejected, match="manifest-runtime-shape-invalid"):
        validate_personalized_manifest(altered)


def test_manifest_validator_rejects_tampered_integrity_and_crossing_mapping():
    result = _build()
    altered = dict(result.manifest)
    altered["integrity"] = dict(altered["integrity"])
    altered["integrity"]["value"] = "sha256:" + "0" * 64
    with pytest.raises(PersonalizedManifestRejected, match="manifest-integrity-mismatch"):
        validate_personalized_manifest(altered)

    altered = dict(result.manifest)
    altered["crossingSupport"] = dict(altered["crossingSupport"])
    altered["crossingSupport"]["edges"] = list(altered["crossingSupport"]["edges"])
    altered["crossingSupport"]["edges"][0] = dict(altered["crossingSupport"]["edges"][0])
    altered["crossingSupport"]["edges"][0]["downEntryId"] = "9d"
    with pytest.raises(PersonalizedManifestRejected, match="manifest-crossing-edge-invalid"):
        validate_personalized_manifest(altered)


def test_manifest_validator_rejects_player_support_claims_from_structural_crossings():
    altered = _plain_json(_build().manifest)
    crossing = altered["crossingSupport"]
    for edge in crossing["edges"]:
        edge["score"] = 1
        edge["confidence"] = 1
    crossing["minimumScore"] = 1
    crossing["meanScore"] = 1
    crossing["uncertainty"]["level"] = "medium"
    with pytest.raises(PersonalizedManifestRejected, match="manifest-structural-crossings-cannot-claim-player-support"):
        validate_personalized_manifest(altered)


def test_host_profile_evidence_must_match_the_digest_checked_v4_brief_or_normalized_v3_brief():
    links = _links()
    links[0]["profileEvidenceIds"] = ["injected-evidence"]
    with pytest.raises(PersonalizedManifestRejected, match="entry-profile-evidence-does-not-match-frozen-brief"):
        _build(links=links)

    job = _job()
    job["version"] = 3
    job["briefCompilerVersion"] = "worker-recompiled-v1"
    result = build_personalized_manifest(
        _grid(), _links(), content=_content(), frozen_job=job, version_inputs=_version_inputs()
    )
    assert result.playable is False

    corrupted = _job()
    corrupted["compiledBriefDigest"] = "0" * 64
    with pytest.raises(PersonalizedManifestRejected, match="frozen-compiled-brief-digest-mismatch"):
        build_personalized_manifest(
            _grid(), _links(), content=_content(), frozen_job=corrupted, version_inputs=_version_inputs()
        )
