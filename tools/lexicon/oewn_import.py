"""Offline, deterministic importer for the pinned OEWN 2025 JSON archive.

The result is source-imported staging data only. It does not review, verify,
or admit words, senses, or glosses into a crossword content pack.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import unicodedata
import zipfile
import zlib
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "oewn-staged-import-v1"
SOURCE_ID = "open-english-wordnet-2025-json"
SOURCE_URL = "https://en-word.net/downloads/english-wordnet-2025-json.zip"
DOWNLOADS_PAGE = "https://en-word.net/downloads/"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
SOURCE_VERSION = "2025-12-31"
EXPECTED_SHA256 = "7d749f6e2c39e6970e4997839dcf6e42fd281f3c2fae0171d2192bae8cfa4b51"
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 96 * 1024 * 1024
MAX_MEMBER_BYTES = 12 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 128
MAX_COMPRESSION_RATIO = 100
MAX_OUTPUT_BYTES = 256 * 1024 * 1024
MAX_SURFACE_CODEPOINTS = 4096
GRID_MAX_LENGTH = 21
_OFFICIAL_SOURCE = {
    "id": SOURCE_ID,
    "title": "Open English Wordnet 2025 JSON export",
    "publisher": "Open English Wordnet Community",
    "edition": "Open English Wordnet 2025",
    "editionDate": SOURCE_VERSION,
    "artifactFilename": "english-wordnet-2025-json.zip",
    "artifactUrl": SOURCE_URL,
    "licenseSpdx": "CC-BY-4.0",
    "licenseEvidence": "Official OEWN downloads page states that Open English Wordnet is released under CC-BY-4.0; the downloaded ZIP itself contains no standalone license or notice member.",
    "licenseEvidenceUrl": DOWNLOADS_PAGE,
    "licenseUrl": LICENSE_URL,
    "attribution": "Open English Wordnet 2025 by the Open English Wordnet Community, derived from Princeton WordNet; licensed under CC BY 4.0. This import preserves source spellings and glosses; indicate normalization/transformation when redistributing derived data and link the license. No endorsement is implied.",
    "status": "source-terms-stated-by-official-download-page",
}
_ENTRY_FILE = re.compile(r"^entries-[0-9a-z]\.json$")
_SYNSET_FILE = re.compile(r"^(noun|verb|adj|adv)\.[A-Za-z]+\.json$")
_SYNSET_ID = re.compile(r"^\d{8}-[nvars]$")
_LEXICAL_POS = re.compile(r"^(?:n|v|a|s|r)(?:-[1-9]\d*)?$")


class OEWNImportError(ValueError):
    """The pinned source archive cannot be imported within the fixed limits."""


@dataclass(frozen=True)
class ImportLimits:
    """Hard stop limits; exceeding one rejects the import rather than truncating."""

    max_lexemes: int = 300_000
    max_forms: int = 600_000
    max_senses: int = 750_000
    max_quarantine: int = 250_000
    max_output_bytes: int = MAX_OUTPUT_BYTES


def canonical_json(value: Any) -> bytes:
    """Serialize strict JSON stably while safely escaping unusual Unicode."""

    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_chunks(value: Any):
    encoder = json.JSONEncoder(
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    for chunk in encoder.iterencode(value):
        yield chunk.encode("utf-8")


def _canonical_digest(value: Any, max_bytes: int) -> str:
    digest = hashlib.sha256()
    byte_count = 0
    for chunk in _canonical_chunks(value):
        byte_count += len(chunk)
        if byte_count > max_bytes:
            raise OEWNImportError("output-size-limit-exceeded")
        digest.update(chunk)
    return digest.hexdigest()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable_id(namespace: str, *parts: str) -> str:
    digest = _sha256(canonical_json(list(parts)))[:32]
    return f"oewn2025:{namespace}:{digest}"


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OEWNImportError("json-duplicate-key")
        result[key] = value
    return result


def _parse_json(data: bytes) -> Any:
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                OEWNImportError("json-non-finite-number")
            ),
        )
    except OEWNImportError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise OEWNImportError("json-member-invalid") from error


def _safe_members(archive: zipfile.ZipFile, archive_size: int) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise OEWNImportError("archive-member-limit-exceeded")
    if not members:
        raise OEWNImportError("archive-empty")

    names: set[str] = set()
    total_size = 0
    for info in members:
        name = info.filename
        if name in names:
            raise OEWNImportError("archive-duplicate-member")
        names.add(name)
        if (
            not name
            or name.startswith(("/", "\\"))
            or "\\" in name
            or ".." in Path(name).parts
            or "/" in name
        ):
            raise OEWNImportError("archive-member-path-unsafe")
        if info.is_dir() or info.flag_bits & 0x1:
            raise OEWNImportError("archive-member-type-unsupported")
        if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
            raise OEWNImportError("archive-compression-unsupported")
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise OEWNImportError("archive-symlink-unsupported")
        if info.file_size > MAX_MEMBER_BYTES:
            raise OEWNImportError("archive-member-size-limit-exceeded")
        total_size += info.file_size
        if total_size > MAX_UNCOMPRESSED_BYTES:
            raise OEWNImportError("archive-total-size-limit-exceeded")
        if info.compress_size == 0:
            if info.file_size:
                raise OEWNImportError("archive-compression-ratio-limit-exceeded")
        elif info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise OEWNImportError("archive-compression-ratio-limit-exceeded")
        if not (_ENTRY_FILE.fullmatch(name) or _SYNSET_FILE.fullmatch(name) or name == "frames.json"):
            raise OEWNImportError("archive-member-name-unsupported")

    if archive_size > MAX_ARCHIVE_BYTES:
        raise OEWNImportError("archive-size-limit-exceeded")
    if not any(_ENTRY_FILE.fullmatch(name) for name in names):
        raise OEWNImportError("archive-entry-files-missing")
    if not any(_SYNSET_FILE.fullmatch(name) for name in names):
        raise OEWNImportError("archive-synset-files-missing")
    return sorted(members, key=lambda item: item.filename)


def _read_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    try:
        chunks = bytearray()
        with archive.open(info) as stream:
            while chunk := stream.read(64 * 1024):
                next_size = len(chunks) + len(chunk)
                if next_size > MAX_MEMBER_BYTES or next_size > info.file_size:
                    raise OEWNImportError("archive-member-size-mismatch")
                chunks.extend(chunk)
    except (
        OSError,
        RuntimeError,
        ValueError,
        EOFError,
        NotImplementedError,
        zipfile.BadZipFile,
        zlib.error,
    ) as error:
        raise OEWNImportError("archive-member-unreadable") from error
    if len(chunks) != info.file_size:
        raise OEWNImportError("archive-member-size-mismatch")
    return bytes(chunks)


def _lexical_pos_base(value: str) -> str:
    return value.split("-", maxsplit=1)[0]


def _pos_compatible(lexical_pos: str, synset_pos: str) -> bool:
    base = _lexical_pos_base(lexical_pos)
    if base in {"a", "s"}:
        return synset_pos in {"a", "s"}
    return base == synset_pos


def _normalized_surface(surface: str) -> str:
    return unicodedata.normalize("NFC", surface).casefold()


def _form_shape(surface: str) -> tuple[str | None, str | None]:
    """Return a grid-shape projection or a stable quarantine reason."""

    if len(surface) > MAX_SURFACE_CODEPOINTS:
        raise OEWNImportError("source-surface-import-limit-exceeded")
    if any(unicodedata.category(character).startswith("C") for character in surface):
        return None, "surface-contains-control-or-format-character"
    if len(surface) > GRID_MAX_LENGTH:
        return None, "grid-form-too-long"
    if not surface.isascii() or not surface.isalpha():
        return None, "grid-form-not-ascii-letters-only"
    if len(surface) < 2:
        return None, "grid-form-too-short"
    return surface.upper(), None


def _quarantine(
    rows: list[dict[str, Any]],
    *,
    record_type: str,
    record_id: str,
    reason_code: str,
    source_surface: str | None = None,
) -> None:
    row: dict[str, Any] = {
        "recordType": record_type,
        "recordId": record_id,
        "reasonCode": reason_code,
    }
    if source_surface is not None:
        row["sourceSurface"] = source_surface
    rows.append(row)


def _load_synsets(
    archive: zipfile.ZipFile,
    members: list[zipfile.ZipInfo],
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    synsets: dict[str, dict[str, Any]] = {}
    by_file_family: dict[str, int] = {}
    for info in members:
        if not _SYNSET_FILE.fullmatch(info.filename):
            continue
        family = info.filename.split(".", maxsplit=1)[0]
        payload = _parse_json(_read_member(archive, info))
        if not isinstance(payload, dict):
            raise OEWNImportError("synset-member-not-object")
        by_file_family[family] = by_file_family.get(family, 0) + len(payload)
        for synset_id, raw in payload.items():
            if not isinstance(synset_id, str) or not _SYNSET_ID.fullmatch(synset_id):
                raise OEWNImportError("synset-id-invalid")
            if synset_id in synsets:
                raise OEWNImportError("synset-id-duplicate")
            if not isinstance(raw, dict):
                raise OEWNImportError("synset-record-invalid")
            derived_pos = synset_id[-1]
            source_pos = raw.get("partOfSpeech")
            definitions = raw.get("definition", [])
            if not isinstance(definitions, list) or any(not isinstance(item, str) for item in definitions):
                raise OEWNImportError("synset-glosses-invalid")
            if len(definitions) > 16 or any(len(item) > 16_384 for item in definitions):
                raise OEWNImportError("synset-gloss-limit-exceeded")
            if source_pos is not None and (not isinstance(source_pos, str) or len(source_pos) > 8):
                raise OEWNImportError("synset-pos-invalid")
            synsets[synset_id] = {
                "derivedPos": derived_pos,
                "sourcePos": source_pos,
                "glosses": definitions,
            }
    return synsets, by_file_family


def _import_archive_bytes(
    archive_bytes: bytes,
    digest: str,
    source_metadata: dict[str, Any],
    *,
    limits: ImportLimits = ImportLimits(),
) -> dict[str, Any]:
    """Parse bytes already verified by the caller, with explicit provenance."""

    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise OEWNImportError("archive-size-limit-exceeded")
    if _sha256(archive_bytes) != digest:
        raise OEWNImportError("archive-sha256-mismatch")

    try:
        archive = zipfile.ZipFile(BytesIO(archive_bytes))
    except (OSError, zipfile.BadZipFile) as error:
        raise OEWNImportError("archive-invalid-zip") from error

    with archive:
        members = _safe_members(archive, len(archive_bytes))
        synsets, synset_counts = _load_synsets(archive, members)
        forms_by_id: dict[str, dict[str, Any]] = {}
        lexemes: dict[str, dict[str, Any]] = {}
        senses: dict[str, dict[str, Any]] = {}
        quarantine: list[dict[str, Any]] = []
        raw_entry_surface_count = 0
        raw_lexical_entry_count = 0
        raw_sense_reference_count = 0

        for info in members:
            if not _ENTRY_FILE.fullmatch(info.filename):
                continue
            payload = _parse_json(_read_member(archive, info))
            if not isinstance(payload, dict):
                raise OEWNImportError("entry-member-not-object")
            for source_surface, pos_rows in payload.items():
                raw_entry_surface_count += 1
                if (
                    not isinstance(source_surface, str)
                    or not source_surface
                    or len(source_surface) > MAX_SURFACE_CODEPOINTS
                    or not isinstance(pos_rows, dict)
                ):
                    raise OEWNImportError("entry-record-invalid")
                for lexical_pos, lexical_data in pos_rows.items():
                    raw_lexical_entry_count += 1
                    if (
                        not isinstance(lexical_pos, str)
                        or not _LEXICAL_POS.fullmatch(lexical_pos)
                        or not isinstance(lexical_data, dict)
                    ):
                        raise OEWNImportError("entry-pos-record-invalid")
                    source_senses = lexical_data.get("sense", [])
                    if not isinstance(source_senses, list):
                        raise OEWNImportError("entry-senses-invalid")
                    raw_sense_reference_count += len(source_senses)
                    lexeme_id = _stable_id("lexeme", source_surface, lexical_pos)
                    form_values: list[tuple[str, str]] = [(source_surface, "lemma")]
                    raw_inflections = lexical_data.get("form", [])
                    if raw_inflections is not None:
                        if not isinstance(raw_inflections, list):
                            raise OEWNImportError("entry-inflections-invalid")
                        for inflection in raw_inflections:
                            if not isinstance(inflection, str) or not inflection:
                                _quarantine(
                                    quarantine,
                                    record_type="form",
                                    record_id=_stable_id("invalid-form", lexeme_id, str(len(form_values))),
                                    reason_code="source-inflection-invalid",
                                )
                                continue
                            if len(inflection) > MAX_SURFACE_CODEPOINTS:
                                raise OEWNImportError("source-surface-import-limit-exceeded")
                            form_values.append((inflection, "inflection"))

                    lexeme = lexemes.get(lexeme_id)
                    if lexeme is not None and (
                        lexeme["sourceSurface"] != source_surface
                        or lexeme["lexicalPartOfSpeech"] != lexical_pos
                    ):
                        raise OEWNImportError("stable-id-collision")
                    if lexeme is None:
                        lexeme = {
                            "id": lexeme_id,
                            "sourceId": source_metadata["id"],
                            "sourceSurface": source_surface,
                            "normalizedSurface": _normalized_surface(source_surface),
                            "language": "en",
                            "lexicalPartOfSpeech": lexical_pos,
                        }
                        lexemes[lexeme_id] = lexeme
                    seen_form_values: set[tuple[str, str]] = set()
                    for surface, form_kind in form_values:
                        identity = (surface, form_kind)
                        if identity in seen_form_values:
                            continue
                        seen_form_values.add(identity)
                        form_id = _stable_id("form", lexeme_id, surface, form_kind)
                        grid_form, reason = _form_shape(surface)
                        existing_form = forms_by_id.get(form_id)
                        if existing_form is not None and (
                            existing_form["lexemeId"] != lexeme_id
                            or existing_form["sourceSurface"] != surface
                            or existing_form["formKind"] != form_kind
                        ):
                            raise OEWNImportError("stable-id-collision")
                        form_record: dict[str, Any] = {
                            "id": form_id,
                            "lexemeId": lexeme_id,
                            "sourceSurface": surface,
                            "normalizedSurface": _normalized_surface(surface),
                            "formKind": form_kind,
                            "gridForm": grid_form,
                            "gridShapeStatus": "candidate" if reason is None else "quarantined",
                        }
                        forms_by_id[form_id] = form_record
                        if reason:
                            _quarantine(
                                quarantine,
                                record_type="form",
                                record_id=form_id,
                                reason_code=reason,
                                source_surface=surface,
                            )
                    for sense_index, source_sense in enumerate(source_senses):
                        if not isinstance(source_sense, dict):
                            _quarantine(
                                quarantine,
                                record_type="sense-reference",
                                record_id=_stable_id("invalid-sense-ref", lexeme_id, str(sense_index)),
                                reason_code="source-sense-reference-invalid",
                            )
                            continue
                        sense_key = source_sense.get("id")
                        synset_id = source_sense.get("synset")
                        if (
                            not isinstance(sense_key, str)
                            or not sense_key
                            or len(sense_key) > 512
                            or not isinstance(synset_id, str)
                            or not _SYNSET_ID.fullmatch(synset_id)
                        ):
                            _quarantine(
                                quarantine,
                                record_type="sense-reference",
                                record_id=_stable_id("invalid-sense-ref", lexeme_id, str(sense_index)),
                                reason_code="source-sense-reference-invalid",
                            )
                            continue
                        sense_id = _stable_id("sense", lexeme_id, sense_key)
                        if sense_id in senses:
                            existing_sense = senses[sense_id]
                            if (
                                existing_sense["lexemeId"] != lexeme_id
                                or existing_sense["sourceSenseKey"] != sense_key
                            ):
                                raise OEWNImportError("stable-id-collision")
                            _quarantine(
                                quarantine,
                                record_type="sense-reference",
                                record_id=sense_id,
                                reason_code="duplicate-source-sense-reference",
                            )
                            continue
                        synset = synsets.get(synset_id)
                        reason_codes: list[str] = []
                        if synset is None:
                            glosses: list[str] = []
                            synset_pos = synset_id[-1]
                            reason_codes.append("source-synset-unresolved")
                        else:
                            glosses = synset["glosses"]
                            synset_pos = synset["sourcePos"] or synset["derivedPos"]
                            if not glosses:
                                reason_codes.append("source-gloss-missing")
                            if synset_pos != synset["derivedPos"]:
                                reason_codes.append("source-synset-pos-mismatch")
                        if not _pos_compatible(lexical_pos, synset_pos):
                            reason_codes.append("source-lexical-synset-pos-mismatch")
                        sense_record = {
                            "id": sense_id,
                            "lexemeId": lexeme_id,
                            "sourceSenseKey": sense_key,
                            "synsetId": synset_id,
                            "lexicalPartOfSpeech": lexical_pos,
                            "synsetPartOfSpeech": synset_pos,
                            "sourceGlosses": glosses,
                        }
                        senses[sense_id] = sense_record
                        for reason in reason_codes:
                            _quarantine(
                                quarantine,
                                record_type="sense",
                                record_id=sense_id,
                                reason_code=reason,
                            )

                    if len(lexemes) > limits.max_lexemes:
                        raise OEWNImportError("lexeme-limit-exceeded")
                    if len(forms_by_id) > limits.max_forms:
                        raise OEWNImportError("form-limit-exceeded")
                    if len(senses) > limits.max_senses:
                        raise OEWNImportError("sense-limit-exceeded")
                    if len(quarantine) > limits.max_quarantine:
                        raise OEWNImportError("quarantine-limit-exceeded")

        reason_counts: dict[str, int] = {}
        for row in quarantine:
            reason_counts[row["reasonCode"]] = reason_counts.get(row["reasonCode"], 0) + 1
        quarantine.sort(
            key=lambda row: (
                row["recordType"],
                row["recordId"],
                row["reasonCode"],
                row.get("sourceSurface", ""),
            )
        )
        raw_members = [item.filename for item in members]
        notices = [
            name
            for name in raw_members
            if any(term in name.casefold() for term in ("license", "licence", "notice", "readme"))
        ]
        metadata_files = [
            name for name in raw_members if any(term in name.casefold() for term in ("metadata", "manifest"))
        ]
        result_without_digest: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "status": "staged-source-imported",
            "admissionStatus": "not-admitted",
            "semanticReviewStatus": "unreviewed",
            "relationModel": "Forms and senses reference lexemes; every lexeme references the single pinned source above.",
            "source": {
                **source_metadata,
                "artifactSha256": digest,
                "artifactSizeBytes": len(archive_bytes),
            },
            "artifactInspection": {
                "zipCommentPresent": bool(archive.comment),
                "licenseOrNoticeMembers": notices,
                "metadataMembers": metadata_files,
                "memberNames": raw_members,
                "entrySurfaceCount": raw_entry_surface_count,
                "lexicalEntryCount": raw_lexical_entry_count,
                "senseReferenceCount": raw_sense_reference_count,
                "synsetCountsByFileFamily": dict(sorted(synset_counts.items())),
                "synsetCount": len(synsets),
            },
            "normalization": {
                "surfaceKey": "NFC then Unicode casefold; original sourceSurface is preserved.",
                "gridForm": "Projection only for 2–21 ASCII letters; it is not a content-admission decision.",
                "pos": "Preserve OEWN lexical POS suffixes (such as n-1) and source synset POS separately.",
            },
            "counts": {
                "lexemes": len(lexemes),
                "forms": len(forms_by_id),
                "shapeCandidateForms": sum(row["gridShapeStatus"] == "candidate" for row in forms_by_id.values()),
                "quarantinedForms": sum(row["gridShapeStatus"] == "quarantined" for row in forms_by_id.values()),
                "senses": len(senses),
                "quarantineRecords": len(quarantine),
                "quarantineReasons": dict(sorted(reason_counts.items())),
            },
            "lexemes": [lexemes[key] for key in sorted(lexemes)],
            "forms": [forms_by_id[key] for key in sorted(forms_by_id)],
            "senses": [senses[key] for key in sorted(senses)],
            "quarantine": quarantine,
        }
        return {
            **result_without_digest,
            "artifactSha256": _canonical_digest(result_without_digest, limits.max_output_bytes),
        }


def import_archive(archive_path: Path, *, limits: ImportLimits = ImportLimits()) -> dict[str, Any]:
    """Import the exact pinned official archive without admitting semantic content."""

    try:
        archive_bytes = archive_path.read_bytes()
    except OSError as error:
        raise OEWNImportError("archive-unreadable") from error
    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise OEWNImportError("archive-size-limit-exceeded")
    digest = _sha256(archive_bytes)
    if digest != EXPECTED_SHA256:
        raise OEWNImportError("archive-sha256-mismatch")
    return _import_archive_bytes(archive_bytes, digest, _OFFICIAL_SOURCE, limits=limits)


def import_to_file(archive_path: Path, output_path: Path) -> dict[str, Any]:
    """Import the pinned artifact and write canonical staged JSON."""

    try:
        source_resolved = archive_path.resolve(strict=True)
        output_resolved = output_path.resolve()
    except OSError as error:
        raise OEWNImportError("archive-unreadable") from error
    if source_resolved == output_resolved:
        raise OEWNImportError("output-overwrites-input")
    result = import_archive(source_resolved)
    temporary_path: Path | None = None
    try:
        output_resolved.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=output_resolved.parent,
            prefix=f".{output_resolved.name}.",
            suffix=".tmp",
            delete=False,
        ) as output_file:
            temporary_path = Path(output_file.name)
            byte_count = 0
            for chunk in _canonical_chunks(result):
                byte_count += len(chunk)
                if byte_count > MAX_OUTPUT_BYTES:
                    raise OEWNImportError("output-size-limit-exceeded")
                output_file.write(chunk)
            output_file.write(b"\n")
        os.replace(temporary_path, output_resolved)
    except OSError as error:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise OEWNImportError("output-write-failed") from error
    except OEWNImportError:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="downloaded official OEWN JSON ZIP")
    parser.add_argument("output", type=Path, help="staged JSON output path")
    arguments = parser.parse_args(argv)
    try:
        result = import_to_file(arguments.archive, arguments.output)
    except (OEWNImportError, OSError) as error:
        reason = str(error) if isinstance(error, OEWNImportError) else "import-failed"
        print(json.dumps({"error": reason}, sort_keys=True), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "artifactSha256": result["artifactSha256"],
                "forms": result["counts"]["forms"],
                "lexemes": result["counts"]["lexemes"],
                "quarantineRecords": result["counts"]["quarantineRecords"],
                "senses": result["counts"]["senses"],
                "status": result["status"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
