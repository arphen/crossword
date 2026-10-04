"""Load admitted-pack candidates from strict deployment configuration.

Configuration values are trust pins, not hints. This boundary never falls
back to generated, synthetic, or pack-declared alternatives when settings or
the pinned artifact fail validation.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .admitted_pack import AdmittedPackContent, AdmittedPackError, SourcePin
from .admitted_pack_loader import (
    AdmittedPackLoadError,
    load_admitted_pack_file,
    load_admitted_pack_file_with_content,
)


MAX_SOURCE_PINS_JSON_BYTES = 16 * 1024
_MAX_SOURCE_PINS = 256
_MAX_ID_LENGTH = 200
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_PIN_KEYS = {"version", "artifactSha256", "contentClass"}


class AdmittedPackConfigError(RuntimeError):
    """A configured admitted-pack source is missing or failed verification.

    ``code`` is deliberately stable and does not expose filesystem details,
    malformed values, or source metadata to an API caller. The route can map
    every instance of this error to the same unavailable response.
    """

    code = "future-admitted-pack-unavailable"

    def __init__(self) -> None:
        super().__init__(self.code)


@dataclass(frozen=True)
class ConfiguredAdmittedPack:
    """Verified pack candidates plus the exact non-secret configuration pins.

    ``source_pins`` uses stable, source-ID-sorted JSON-ready records. The
    filesystem path is intentionally omitted from the receipt.
    """

    candidates: list[dict[str, Any]]
    content: AdmittedPackContent
    pack_id: str
    pack_sha256: str
    source_pins: tuple[dict[str, str], ...]


class _DuplicatePinKey(ValueError):
    """Raised for duplicate keys in the source-pins JSON document."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicatePinKey
        value[key] = item
    return value


def _reject_json_constant(_value: str) -> None:
    raise ValueError("non-json constant")


def _required_string(config: Mapping[str, Any], key: str, *, maximum: int | None = None) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AdmittedPackConfigError
    if maximum is not None and len(value) > maximum:
        raise AdmittedPackConfigError
    return value


def _parse_source_pins(raw: str) -> dict[str, SourcePin]:
    try:
        raw_size = len(raw.encode("utf-8", errors="strict"))
    except UnicodeEncodeError as error:
        raise AdmittedPackConfigError from error
    if raw_size > MAX_SOURCE_PINS_JSON_BYTES:
        raise AdmittedPackConfigError

    try:
        parsed = json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, _DuplicatePinKey, RecursionError, ValueError) as error:
        raise AdmittedPackConfigError from error

    if not isinstance(parsed, dict) or not parsed or len(parsed) > _MAX_SOURCE_PINS:
        raise AdmittedPackConfigError

    pins: dict[str, SourcePin] = {}
    for source_id, value in parsed.items():
        if (
            not isinstance(source_id, str)
            or not source_id.strip()
            or len(source_id) > _MAX_ID_LENGTH
            or not isinstance(value, dict)
            or set(value) != _SOURCE_PIN_KEYS
        ):
            raise AdmittedPackConfigError

        version = value["version"]
        digest = value["artifactSha256"]
        content_class = value["contentClass"]
        if (
            not isinstance(version, str)
            or not version.strip()
            or len(version) > _MAX_ID_LENGTH
            or not isinstance(digest, str)
            or _SHA256.fullmatch(digest) is None
            or not isinstance(content_class, str)
            or content_class not in {"public", "synthetic"}
        ):
            raise AdmittedPackConfigError
        pins[source_id] = SourcePin(
            version=version,
            artifact_sha256=digest,
            content_class=content_class,
        )
    return pins


def _configured_pack_pins(
    config: Mapping[str, Any],
) -> tuple[Path, str, str, dict[str, SourcePin]]:
    if not isinstance(config, Mapping):
        raise AdmittedPackConfigError

    path = _required_string(config, "FUTURE_ADMITTED_PACK_PATH")
    pack_id = _required_string(
        config, "FUTURE_ADMITTED_PACK_ID", maximum=_MAX_ID_LENGTH
    )
    pack_digest = _required_string(config, "FUTURE_ADMITTED_PACK_SHA256")
    if _SHA256.fullmatch(pack_digest) is None:
        raise AdmittedPackConfigError
    pins_json = _required_string(config, "FUTURE_ADMITTED_SOURCE_PINS_JSON")
    source_pins = _parse_source_pins(pins_json)
    return Path(path), pack_id, pack_digest, source_pins


def load_configured_admitted_pack(config: Mapping[str, Any]) -> ConfiguredAdmittedPack:
    """Load candidates, reviewed content, and the exact configuration pins.

    Expected Flask config keys are ``FUTURE_ADMITTED_PACK_PATH``,
    ``FUTURE_ADMITTED_PACK_ID``, ``FUTURE_ADMITTED_PACK_SHA256``, and
    ``FUTURE_ADMITTED_SOURCE_PINS_JSON``. Every missing or invalid setting and
    every artifact-verification failure raises ``AdmittedPackConfigError``
    with the stable ``future-admitted-pack-unavailable`` code.
    """

    path, pack_id, pack_digest, source_pins = _configured_pack_pins(config)
    try:
        loaded = load_admitted_pack_file_with_content(
            path,
            expected_pack_id=pack_id,
            expected_artifact_sha256=pack_digest,
            expected_sources=source_pins,
        )
        receipt_pins = tuple(
            {
                "sourceId": source_id,
                "version": pin.version,
                "artifactSha256": pin.artifact_sha256,
                "contentClass": pin.content_class,
            }
            for source_id, pin in sorted(source_pins.items())
        )
        return ConfiguredAdmittedPack(
            candidates=loaded.candidates,
            content=loaded.content,
            pack_id=pack_id,
            pack_sha256=pack_digest,
            source_pins=receipt_pins,
        )
    except (AdmittedPackLoadError, AdmittedPackError) as error:
        raise AdmittedPackConfigError from error


def load_configured_admitted_candidates(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Compatibility wrapper returning only candidates from the verified pack."""

    path, pack_id, pack_digest, source_pins = _configured_pack_pins(config)
    try:
        return load_admitted_pack_file(
            path,
            expected_pack_id=pack_id,
            expected_artifact_sha256=pack_digest,
            expected_sources=source_pins,
        )
    except (AdmittedPackLoadError, AdmittedPackError) as error:
        raise AdmittedPackConfigError from error
