"""Fail-closed admission gate for small, pinned crossword content packs.

This module deliberately does not import or transform an external word list.
It accepts an explicit JSON manifest, verifies each pinned source artifact,
then admits only reviewed records with complete source/evidence provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "lexicon-pack-admission-v1"
MANIFEST_SCHEMA_VERSION = 1
ALLOWED_SPDX = frozenset(
    {
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "CC-BY-4.0",
        "CC-BY-SA-4.0",
        "CC0-1.0",
        "ISC",
        "MIT",
    }
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_CLUE_GRAMMAR_PROGRAM = r"""
import { readFileSync } from 'node:fs';
import { validateClueGrammar } from './packages/domain/src/clueGrammar.ts';
const items = JSON.parse(readFileSync(0, 'utf8'));
const results = items.map(({ annotation, context }) => {
  try {
    const value = validateClueGrammar(annotation, context ?? {});
    return {
      valid: value.valid,
      issues: value.issues.map(({ code }) => code).sort(),
    };
  } catch {
    return { valid: false, issues: ['validator-error'] };
  }
});
process.stdout.write(JSON.stringify(results));
"""


class PackBuildError(ValueError):
    """The global input manifest cannot safely be interpreted."""


def canonical_json(value: Any) -> bytes:
    """Serialize JSON values deterministically for stable content hashes."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_record(value: Any) -> bool:
    return isinstance(value, dict)


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _date(value: Any) -> bool:
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        return False
    try:
        from datetime import date

        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _normalize_surface(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip().casefold()


def _record_id(record: Any) -> str:
    if _is_record(record) and _text(record.get("id")):
        return record["id"].strip() if isinstance(record["id"], str) else "<invalid-id>"
    return "<missing-id>"


def _quarantine(
    bucket: list[dict[str, Any]],
    record_type: str,
    record_id: str,
    reason_code: str,
    details: list[str] | None = None,
) -> None:
    item: dict[str, Any] = {
        "recordType": record_type,
        "recordId": record_id,
        "reasonCode": reason_code,
    }
    if details:
        item["details"] = sorted(set(details))
    bucket.append(item)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PackBuildError("manifest-unreadable") from error


def _validate_manifest_shape(manifest: Any) -> dict[str, Any]:
    if not _is_record(manifest):
        raise PackBuildError("manifest-not-object")
    if manifest.get("schemaVersion") != MANIFEST_SCHEMA_VERSION:
        raise PackBuildError("manifest-unsupported-version")
    if not _text(manifest.get("packId")) or not _text(manifest.get("admissionStatus")):
        raise PackBuildError("manifest-missing-pack-metadata")
    if manifest.get("admissionStatus") != "approved":
        raise PackBuildError("manifest-not-approved")
    if not isinstance(manifest.get("sources"), list) or not isinstance(
        manifest.get("records"), dict
    ):
        raise PackBuildError("manifest-missing-source-or-record-list")
    for name in ("lexemes", "senses", "facts", "clues"):
        if not isinstance(manifest["records"].get(name), list):
            raise PackBuildError(f"manifest-invalid-{name}-list")
    return manifest


def _source_ids_with_duplicates(sources: list[Any]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for source in sources:
        source_id = str(source.get("id", "")).strip() if _is_record(source) else ""
        if source_id and source_id in seen:
            duplicates.add(source_id)
        seen.add(source_id)
    return duplicates


def _record_ids_with_duplicates(records: list[Any]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for record in records:
        record_id = _record_id(record)
        if record_id != "<missing-id>" and record_id in seen:
            duplicates.add(record_id)
        seen.add(record_id)
    return duplicates


def _source_reason(source: Any, root: Path) -> str | None:
    if not _is_record(source):
        return "source-record-invalid"
    required = (
        "id",
        "version",
        "artifactPath",
        "artifactSha256",
        "spdx",
        "licenseReview",
        "redistribution",
        "admissionStatus",
        "attribution",
        "contentClass",
        "isPrivate",
        "historicalPrivate",
    )
    if any(key not in source for key in required):
        return "source-metadata-incomplete"
    if not _text(source.get("id")) or not _text(source.get("version")):
        return "source-metadata-incomplete"
    if source.get("contentClass") not in {"public", "synthetic"}:
        return "source-content-class-ineligible"
    if source.get("isPrivate") is not False:
        return "source-private-content"
    if source.get("historicalPrivate") is not False:
        return "source-historical-private-content"
    if not _text(source.get("spdx")) or source.get("spdx", "").strip().upper() == "NOASSERTION":
        return "source-spdx-unasserted"
    if source.get("spdx") not in ALLOWED_SPDX:
        return "source-spdx-not-allowlisted"
    if source.get("licenseReview") != "approved":
        return "source-license-not-approved"
    if source.get("redistribution") != "permitted":
        return "source-redistribution-not-permitted"
    if source.get("admissionStatus") != "approved":
        return "source-admission-not-approved"
    if not _text(source.get("attribution")):
        return "source-attribution-missing"
    digest = source.get("artifactSha256")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        return "source-artifact-digest-invalid"
    relative = source.get("artifactPath")
    if not isinstance(relative, str) or not relative:
        return "source-artifact-path-invalid"
    artifact_path = Path(relative)
    if artifact_path.is_absolute() or ".." in artifact_path.parts:
        return "source-artifact-path-unsafe"
    try:
        resolved_root = root.resolve(strict=True)
        resolved_artifact = (resolved_root / artifact_path).resolve(strict=True)
    except OSError:
        return "source-artifact-missing"
    if not resolved_artifact.is_relative_to(resolved_root):
        return "source-artifact-path-unsafe"
    if not resolved_artifact.is_file():
        return "source-artifact-not-file"
    try:
        actual_digest = _sha256(resolved_artifact.read_bytes())
    except OSError:
        return "source-artifact-unreadable"
    if actual_digest != digest:
        return "source-artifact-sha256-mismatch"
    return None


def _source_projection(source: dict[str, Any]) -> dict[str, Any]:
    """Return provenance safe for inclusion in a content artifact."""

    return {
        "sourceId": source["id"],
        "version": source["version"],
        "artifactSha256": source["artifactSha256"],
        "spdx": source["spdx"],
        "attribution": source["attribution"],
        "contentClass": source["contentClass"],
    }


def _check_records_shape(
    record_lists: dict[str, list[Any]],
    quarantine: list[dict[str, Any]],
) -> dict[str, set[str]]:
    duplicate_ids: dict[str, set[str]] = {}
    for record_type, records in record_lists.items():
        blocked = _record_ids_with_duplicates(records)
        for record_id in sorted(blocked):
            _quarantine(quarantine, record_type, record_id, "duplicate-record-id")
        for record in records:
            if not _is_record(record):
                _quarantine(quarantine, record_type, "<invalid-record>", "record-not-object")
            elif not _text(record.get("id")):
                _quarantine(quarantine, record_type, "<missing-id>", "record-id-missing")
                blocked.add(_record_id(record))
            elif not isinstance(record.get("id"), str) or record["id"] != record["id"].strip():
                _quarantine(quarantine, record_type, _record_id(record), "record-id-invalid")
                blocked.add(_record_id(record))
        duplicate_ids[record_type] = blocked
    return duplicate_ids


def _eligible_record_source(
    record: Any,
    record_type: str,
    source_by_id: dict[str, dict[str, Any]],
    valid_source_ids: set[str],
    quarantine: list[dict[str, Any]],
) -> dict[str, Any] | None:
    record_id = _record_id(record)
    if not _is_record(record):
        return None
    source_id = record.get("sourceId")
    if not _text(source_id):
        _quarantine(quarantine, record_type, record_id, "record-source-id-missing")
        return None
    source_id = source_id.strip()
    if source_id not in source_by_id:
        _quarantine(quarantine, record_type, record_id, "record-source-unknown")
        return None
    if source_id not in valid_source_ids:
        _quarantine(quarantine, record_type, record_id, "record-source-ineligible")
        return None
    return source_by_id[source_id]


def _review_metadata_valid(record: Any) -> bool:
    return (
        record.get("admissionStatus") == "reviewed"
        and _text(record.get("reviewerId"))
        and _date(record.get("reviewedAt"))
        and isinstance(record.get("evidenceRefs"), list)
        and bool(record["evidenceRefs"])
        and all(_text(reference) for reference in record["evidenceRefs"])
    )


def _run_clue_grammar(annotations: list[dict[str, Any]], timeout: float = 20.0) -> list[dict[str, Any]] | None:
    """Use the repository's TypeScript validator through the installed Node runtime.

    ``None`` means the validator could not be run. The caller fails closed for
    every clue candidate in that case while still admitting safe fill records.
    """

    if not annotations:
        return []
    repository_root = Path(__file__).resolve().parents[2]
    try:
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", _CLUE_GRAMMAR_PROGRAM],
            cwd=repository_root,
            input=canonical_json(annotations),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        result = json.loads(completed.stdout)
    except (UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(result, list) or len(result) != len(annotations):
        return None
    if any(not _is_record(item) or not isinstance(item.get("valid"), bool) for item in result):
        return None
    return result


def build_pack(manifest: Any, manifest_directory: Path) -> dict[str, Any]:
    """Validate and deterministically build an admitted content pack.

    Invalid individual sources and records are quarantined. Invalid top-level
    manifest structure is a hard error because its scope cannot be trusted.
    """

    value = _validate_manifest_shape(manifest)
    root = manifest_directory.resolve()
    source_rows = value["sources"]
    records = value["records"]
    quarantine: list[dict[str, Any]] = []

    duplicate_source_ids = _source_ids_with_duplicates(source_rows)
    source_by_id: dict[str, dict[str, Any]] = {}
    valid_source_ids: set[str] = set()
    source_quarantine: list[dict[str, Any]] = []
    for source in source_rows:
        source_id = str(source.get("id", "")).strip() if _is_record(source) else "<invalid-source>"
        if source_id in duplicate_source_ids:
            _quarantine(source_quarantine, "source", source_id, "duplicate-source-id")
            continue
        if _is_record(source) and source_id:
            source_by_id[source_id] = source
        reason = _source_reason(source, root)
        if reason:
            _quarantine(source_quarantine, "source", source_id or "<missing-id>", reason)
            continue
        assert isinstance(source, dict)
        valid_source_ids.add(source_id)
    quarantine.extend(source_quarantine)

    record_lists = {name: records[name] for name in ("lexemes", "senses", "facts", "clues")}
    duplicate_ids = _check_records_shape(record_lists, quarantine)
    blocked: dict[str, set[str]] = {
        record_type: ids for record_type, ids in duplicate_ids.items()
    }

    admitted_lexemes: dict[str, dict[str, Any]] = {}
    for lexeme in record_lists["lexemes"]:
        lexeme_id = _record_id(lexeme)
        if not _is_record(lexeme) or lexeme_id in blocked["lexemes"]:
            continue
        source = _eligible_record_source(
            lexeme, "lexeme", source_by_id, valid_source_ids, quarantine
        )
        if source is None:
            continue
        if lexeme.get("admissionStatus") != "reviewed":
            _quarantine(quarantine, "lexeme", lexeme_id, "lexeme-not-reviewed")
            continue
        headword = lexeme.get("headword")
        language = lexeme.get("language")
        if not _text(headword) or not _text(language):
            _quarantine(quarantine, "lexeme", lexeme_id, "lexeme-surface-or-language-missing")
            continue
        if headword != headword.strip() or any(ord(char) < 32 for char in headword):
            _quarantine(quarantine, "lexeme", lexeme_id, "lexeme-surface-invalid")
            continue
        if not _review_metadata_valid(lexeme):
            _quarantine(quarantine, "lexeme", lexeme_id, "lexeme-review-evidence-incomplete")
            continue
        admitted_lexemes[lexeme_id] = {
            "id": lexeme_id,
            "headword": unicodedata.normalize("NFC", headword),
            "language": language,
            "provenance": {
                "source": _source_projection(source),
                "evidenceRefs": sorted(set(lexeme["evidenceRefs"])),
                "reviewerId": lexeme["reviewerId"],
                "reviewedAt": lexeme["reviewedAt"],
            },
        }

    admitted_senses: dict[str, dict[str, Any]] = {}
    for sense in record_lists["senses"]:
        sense_id = _record_id(sense)
        if not _is_record(sense) or sense_id in blocked["senses"]:
            continue
        source = _eligible_record_source(sense, "sense", source_by_id, valid_source_ids, quarantine)
        if source is None:
            continue
        lexeme_id = sense.get("lexemeId")
        if not _text(lexeme_id) or lexeme_id not in admitted_lexemes:
            _quarantine(quarantine, "sense", sense_id, "sense-lexeme-ineligible")
            continue
        if sense.get("admissionStatus") != "reviewed":
            _quarantine(quarantine, "sense", sense_id, "sense-not-reviewed")
            continue
        if not _review_metadata_valid(sense):
            _quarantine(quarantine, "sense", sense_id, "sense-review-evidence-incomplete")
            continue
        resolution = sense.get("resolutionStatus")
        if resolution not in {"resolved", "unresolved"}:
            _quarantine(quarantine, "sense", sense_id, "sense-resolution-status-invalid")
            continue
        gloss = sense.get("gloss")
        if resolution == "resolved" and not _text(gloss):
            _quarantine(quarantine, "sense", sense_id, "sense-gloss-missing")
            continue
        if resolution == "unresolved" and gloss is not None and not isinstance(gloss, str):
            _quarantine(quarantine, "sense", sense_id, "sense-gloss-invalid")
            continue
        admitted_senses[sense_id] = {
            "id": sense_id,
            "lexemeId": lexeme_id,
            "gloss": gloss,
            "resolutionStatus": resolution,
            "clueEligible": resolution == "resolved",
            "fillOnly": resolution == "unresolved",
            "provenance": {
                "source": _source_projection(source),
                "evidenceRefs": sorted(set(sense["evidenceRefs"])),
                "reviewerId": sense["reviewerId"],
                "reviewedAt": sense["reviewedAt"],
            },
        }

    admitted_facts: dict[str, dict[str, Any]] = {}
    for fact in record_lists["facts"]:
        fact_id = _record_id(fact)
        if not _is_record(fact) or fact_id in blocked["facts"]:
            continue
        source = _eligible_record_source(fact, "fact", source_by_id, valid_source_ids, quarantine)
        if source is None:
            continue
        lexeme_id = fact.get("lexemeId")
        if not _text(lexeme_id) or lexeme_id not in admitted_lexemes:
            _quarantine(quarantine, "fact", fact_id, "fact-lexeme-ineligible")
            continue
        if fact.get("admissionStatus") != "reviewed":
            _quarantine(quarantine, "fact", fact_id, "fact-not-reviewed")
            continue
        if not _text(fact.get("statement")):
            _quarantine(quarantine, "fact", fact_id, "fact-statement-missing")
            continue
        if not _review_metadata_valid(fact):
            _quarantine(quarantine, "fact", fact_id, "fact-review-evidence-incomplete")
            continue
        admitted_facts[fact_id] = {
            "id": fact_id,
            "lexemeId": lexeme_id,
            "statement": fact["statement"].strip(),
            "provenance": {
                "source": _source_projection(source),
                "evidenceRefs": sorted(set(fact["evidenceRefs"])),
                "reviewerId": fact["reviewerId"],
                "reviewedAt": fact["reviewedAt"],
            },
        }

    # Structural clue/source/evidence checks happen before invoking the grammar
    # validator. The final pass is batched for one deterministic Node process.
    pending_clues: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]] = []
    for clue in record_lists["clues"]:
        clue_id = _record_id(clue)
        if not _is_record(clue) or clue_id in blocked["clues"]:
            continue
        clue_source = _eligible_record_source(clue, "clue", source_by_id, valid_source_ids, quarantine)
        if clue_source is None:
            continue
        if clue.get("admissionStatus") != "reviewed":
            _quarantine(quarantine, "clue", clue_id, "clue-not-reviewed")
            continue
        if not _review_metadata_valid(clue):
            _quarantine(quarantine, "clue", clue_id, "clue-review-evidence-incomplete")
            continue
        has_sense = _text(clue.get("senseId"))
        has_fact = _text(clue.get("factId"))
        if has_sense == has_fact:
            _quarantine(quarantine, "clue", clue_id, "clue-evidence-link-invalid")
            continue
        if has_sense:
            evidence_id = clue["senseId"].strip()
            evidence = admitted_senses.get(evidence_id)
            if evidence is None:
                _quarantine(quarantine, "clue", clue_id, "clue-sense-ineligible")
                continue
            if not evidence["clueEligible"]:
                _quarantine(quarantine, "clue", clue_id, "clue-sense-unresolved")
                continue
            lexeme_id = evidence["lexemeId"]
            evidence_type = "sense"
        else:
            evidence_id = clue["factId"].strip()
            evidence = admitted_facts.get(evidence_id)
            if evidence is None:
                _quarantine(quarantine, "clue", clue_id, "clue-fact-ineligible")
                continue
            lexeme_id = evidence["lexemeId"]
            evidence_type = "fact"
        grammar = clue.get("grammar")
        if not _is_record(grammar):
            _quarantine(quarantine, "clue", clue_id, "clue-grammar-annotation-missing")
            continue
        if grammar.get("clueId") != clue_id or grammar.get("clueText") != clue.get("text"):
            _quarantine(quarantine, "clue", clue_id, "clue-grammar-record-mismatch")
            continue
        if not _text(clue.get("text")):
            _quarantine(quarantine, "clue", clue_id, "clue-text-missing")
            continue
        answer = grammar.get("answer")
        headword = admitted_lexemes[lexeme_id]["headword"]
        if not isinstance(answer, str) or _normalize_surface(answer) != _normalize_surface(headword):
            _quarantine(quarantine, "clue", clue_id, "clue-answer-evidence-mismatch")
            continue
        pending_clues.append((clue, clue_source, evidence, evidence_type))

    # Keep candidate order stable by ID regardless of source manifest array order.
    pending_clues.sort(key=lambda item: _record_id(item[0]))
    grammar_results = _run_clue_grammar(
        [
            {"annotation": clue["grammar"], "context": clue.get("grammarContext", {})}
            for clue, _, _, _ in pending_clues
        ]
    )
    admitted_clues: list[dict[str, Any]] = []
    if grammar_results is None:
        for clue, _, _, _ in pending_clues:
            _quarantine(quarantine, "clue", _record_id(clue), "clue-grammar-validator-unavailable")
    else:
        for (clue, clue_source, evidence, evidence_type), grammar_result in zip(
            pending_clues, grammar_results, strict=True
        ):
            clue_id = _record_id(clue)
            if not grammar_result["valid"]:
                _quarantine(
                    quarantine,
                    "clue",
                    clue_id,
                    "clue-grammar-invalid",
                    grammar_result.get("issues", []),
                )
                continue
            evidence_source = evidence["provenance"]["source"]
            provenance_sources = {clue_source["id"]: clue_source, evidence_source["sourceId"]: source_by_id[evidence_source["sourceId"]]}
            admitted_clues.append(
                {
                    "id": clue_id,
                    "text": clue["text"].strip(),
                    "answerLexemeId": evidence["lexemeId"],
                    "evidence": {"type": evidence_type, "id": evidence["id"]},
                    "grammar": clue["grammar"],
                    "provenance": {
                        "sources": [
                            _source_projection(provenance_sources[source_id])
                            for source_id in sorted(provenance_sources)
                        ],
                        "evidenceRefs": sorted(set(clue["evidenceRefs"])),
                        "evidenceProvenance": evidence["provenance"],
                        "reviewerId": clue["reviewerId"],
                        "reviewedAt": clue["reviewedAt"],
                        "semanticTruthStatus": "not-established-by-grammar-validator",
                    },
                }
            )

    quarantine = list({canonical_json(item): item for item in quarantine}.values())
    quarantine.sort(key=lambda item: (item["recordType"], item["recordId"], item["reasonCode"], item.get("details", [])))
    pack_without_digest: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "packId": value["packId"],
        "manifestSha256": _sha256(canonical_json(value)),
        "sources": [
            _source_projection(source_by_id[source_id])
            for source_id in sorted(valid_source_ids)
        ],
        "lexemes": [admitted_lexemes[key] for key in sorted(admitted_lexemes)],
        "senses": [admitted_senses[key] for key in sorted(admitted_senses)],
        "facts": [admitted_facts[key] for key in sorted(admitted_facts)],
        "clues": sorted(admitted_clues, key=lambda clue: clue["id"]),
        "quarantine": quarantine,
    }
    return {
        **pack_without_digest,
        "artifactSha256": _sha256(canonical_json(pack_without_digest)),
    }


def build_from_file(manifest_path: Path) -> dict[str, Any]:
    """Read and build one pack using paths relative to the manifest directory."""

    manifest = _load_json(manifest_path)
    return build_pack(manifest, manifest_path.resolve().parent)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="pinned JSON source/record manifest")
    parser.add_argument("output", type=Path, help="deterministic output pack JSON")
    arguments = parser.parse_args(argv)
    try:
        manifest_path = arguments.manifest.resolve(strict=True)
        manifest = _validate_manifest_shape(_load_json(manifest_path))
        output_path = arguments.output.resolve()
        if output_path == manifest_path:
            raise PackBuildError("output-overwrites-input")
        for source in manifest["sources"]:
            if not _is_record(source) or not isinstance(source.get("artifactPath"), str):
                continue
            artifact_path = Path(source["artifactPath"])
            if artifact_path.is_absolute() or ".." in artifact_path.parts:
                continue
            try:
                pinned_path = (manifest_path.parent / artifact_path).resolve(strict=True)
            except OSError:
                continue
            if output_path == pinned_path:
                raise PackBuildError("output-overwrites-input")
        pack = build_pack(manifest, manifest_path.parent)
        encoded = canonical_json(pack) + b"\n"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(encoded)
    except (PackBuildError, OSError) as error:
        reason = str(error) if isinstance(error, PackBuildError) else "output-write-failed"
        print(json.dumps({"error": reason}, sort_keys=True), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "artifactSha256": pack["artifactSha256"],
                "clues": len(pack["clues"]),
                "facts": len(pack["facts"]),
                "lexemes": len(pack["lexemes"]),
                "quarantined": len(pack["quarantine"]),
                "senses": len(pack["senses"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
