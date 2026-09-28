"""Bounded strict loader for pinned admitted-pack artifacts.

This loader does not establish trust from a self-reported digest. Callers must
provide the expected pack ID/digest and the complete exact source-pin mapping;
the existing resolver verifies those pins and all pack content before any
candidate is returned.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .admitted_pack import (
    AdmittedPackContent,
    AdmittedPackError,
    SourcePin,
    project_admitted_pack_content,
    resolve_admitted_pack,
)


MAX_ADMITTED_PACK_BYTES = 64 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class AdmittedPackLoadError(ValueError):
    """The file/byte input cannot be safely decoded as a pinned pack."""


class _DuplicateObjectKey(ValueError):
    """JSON object contains a repeated key."""


@dataclass(frozen=True)
class LoadedAdmittedPack:
    """Candidate and reviewed-content views of one parsed, pinned artifact."""

    candidates: list[dict[str, Any]]
    content: AdmittedPackContent


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateObjectKey("duplicate-json-object-key")
        result[key] = value
    return result


def _reject_non_json_constant(value: str) -> None:
    raise AdmittedPackLoadError(f"non-json-constant:{value}")


def _validate_pins(
    expected_pack_id: str,
    expected_artifact_sha256: str,
    expected_sources: Mapping[str, SourcePin],
) -> None:
    if not isinstance(expected_pack_id, str) or not expected_pack_id.strip() or len(expected_pack_id) > 200:
        raise AdmittedPackLoadError("expected-pack-id-required")
    if not isinstance(expected_artifact_sha256, str) or not _SHA256.fullmatch(expected_artifact_sha256):
        raise AdmittedPackLoadError("expected-pack-digest-required")
    if not isinstance(expected_sources, Mapping) or not expected_sources:
        raise AdmittedPackLoadError("exact-source-pins-required")
    for source_id, pin in expected_sources.items():
        if not isinstance(source_id, str) or not source_id.strip() or len(source_id) > 200 or not isinstance(pin, SourcePin):
            raise AdmittedPackLoadError("exact-source-pins-invalid")
        if (
            not isinstance(pin.version, str)
            or not pin.version.strip()
            or not isinstance(pin.artifact_sha256, str)
            or not _SHA256.fullmatch(pin.artifact_sha256)
            or not isinstance(pin.content_class, str)
            or pin.content_class not in {"public", "synthetic"}
        ):
            raise AdmittedPackLoadError("exact-source-pins-invalid")


def _parse_and_resolve(
    raw: bytes,
    *,
    expected_pack_id: str,
    expected_artifact_sha256: str,
    expected_sources: Mapping[str, SourcePin],
) -> list[dict[str, Any]]:
    if len(raw) > MAX_ADMITTED_PACK_BYTES:
        raise AdmittedPackLoadError("pack-size-limit-exceeded")
    _validate_pins(expected_pack_id, expected_artifact_sha256, expected_sources)
    try:
        pack = _parse_pack(raw)
        return resolve_admitted_pack(
            pack,
            expected_pack_id=expected_pack_id,
            expected_artifact_sha256=expected_artifact_sha256,
            expected_sources=expected_sources,
        )
    except AdmittedPackError:
        raise


def _parse_pack(raw: bytes) -> Any:
    """Decode one already bounded artifact, rejecting ambiguous JSON."""

    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise AdmittedPackLoadError("pack-utf8-invalid") from error
    try:
        return json.loads(
            text,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except _DuplicateObjectKey as error:
        raise AdmittedPackLoadError("pack-json-duplicate-key") from error
    except AdmittedPackLoadError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as error:
        raise AdmittedPackLoadError("pack-json-invalid") from error


def _parse_resolve_and_project(
    raw: bytes,
    *,
    expected_pack_id: str,
    expected_artifact_sha256: str,
    expected_sources: Mapping[str, SourcePin],
) -> LoadedAdmittedPack:
    """Create both views from one bounded, strictly parsed JSON object."""

    if len(raw) > MAX_ADMITTED_PACK_BYTES:
        raise AdmittedPackLoadError("pack-size-limit-exceeded")
    _validate_pins(expected_pack_id, expected_artifact_sha256, expected_sources)
    pack = _parse_pack(raw)
    try:
        candidates = resolve_admitted_pack(
            pack,
            expected_pack_id=expected_pack_id,
            expected_artifact_sha256=expected_artifact_sha256,
            expected_sources=expected_sources,
        )
        content = project_admitted_pack_content(
            pack,
            expected_pack_id=expected_pack_id,
            expected_artifact_sha256=expected_artifact_sha256,
            expected_sources=expected_sources,
        )
    except AdmittedPackError:
        raise
    return LoadedAdmittedPack(candidates=candidates, content=content)


def load_admitted_pack_bytes(
    raw: bytes,
    *,
    expected_pack_id: str,
    expected_artifact_sha256: str,
    expected_sources: Mapping[str, SourcePin],
) -> list[dict[str, Any]]:
    """Decode and resolve one bounded UTF-8 JSON artifact from bytes."""

    if not isinstance(raw, bytes):
        raise AdmittedPackLoadError("pack-bytes-required")
    if len(raw) > MAX_ADMITTED_PACK_BYTES:
        raise AdmittedPackLoadError("pack-size-limit-exceeded")
    return _parse_and_resolve(
        raw,
        expected_pack_id=expected_pack_id,
        expected_artifact_sha256=expected_artifact_sha256,
        expected_sources=expected_sources,
    )


def load_admitted_pack_bytes_with_content(
    raw: bytes,
    *,
    expected_pack_id: str,
    expected_artifact_sha256: str,
    expected_sources: Mapping[str, SourcePin],
) -> LoadedAdmittedPack:
    """Decode a pinned byte artifact into candidates and immutable content."""

    if not isinstance(raw, bytes):
        raise AdmittedPackLoadError("pack-bytes-required")
    return _parse_resolve_and_project(
        raw,
        expected_pack_id=expected_pack_id,
        expected_artifact_sha256=expected_artifact_sha256,
        expected_sources=expected_sources,
    )


def load_admitted_pack_file(
    path: str | Path,
    *,
    expected_pack_id: str,
    expected_artifact_sha256: str,
    expected_sources: Mapping[str, SourcePin],
) -> list[dict[str, Any]]:
    """Read at most 64 MiB plus one byte, then strictly decode and resolve."""

    _validate_pins(expected_pack_id, expected_artifact_sha256, expected_sources)
    try:
        with Path(path).open("rb") as artifact:
            raw = artifact.read(MAX_ADMITTED_PACK_BYTES + 1)
    except (OSError, TypeError, ValueError) as error:
        raise AdmittedPackLoadError("pack-file-unreadable") from error
    if len(raw) > MAX_ADMITTED_PACK_BYTES:
        raise AdmittedPackLoadError("pack-size-limit-exceeded")
    return _parse_and_resolve(
        raw,
        expected_pack_id=expected_pack_id,
        expected_artifact_sha256=expected_artifact_sha256,
        expected_sources=expected_sources,
    )


def load_admitted_pack_file_with_content(
    path: str | Path,
    *,
    expected_pack_id: str,
    expected_artifact_sha256: str,
    expected_sources: Mapping[str, SourcePin],
) -> LoadedAdmittedPack:
    """Read once, then derive both views from that exact verified byte buffer."""

    _validate_pins(expected_pack_id, expected_artifact_sha256, expected_sources)
    try:
        with Path(path).open("rb") as artifact:
            raw = artifact.read(MAX_ADMITTED_PACK_BYTES + 1)
    except (OSError, TypeError, ValueError) as error:
        raise AdmittedPackLoadError("pack-file-unreadable") from error
    if len(raw) > MAX_ADMITTED_PACK_BYTES:
        raise AdmittedPackLoadError("pack-size-limit-exceeded")
    return _parse_resolve_and_project(
        raw,
        expected_pack_id=expected_pack_id,
        expected_artifact_sha256=expected_artifact_sha256,
        expected_sources=expected_sources,
    )
