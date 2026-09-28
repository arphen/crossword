"""Strict host-side adapter from an admitted xfill fill to a V2 candidate.

This module does not select or author vocabulary. It checks a construction
result against the independently derived crossword topology, then binds every
slot to an explicit host-owned source selection and an exact reviewed clue in
the pinned content projection. Current admitted clues explicitly say that
semantic truth has not been established, so results remain review candidates
and are never marked playable.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any

from .admitted_pack import AdmittedPackContent, AdmittedLexemeContent


GRID_SIZE = 15
_LETTER = re.compile(r"^[A-Z]$")
_ANSWER = re.compile(r"^[A-Z]{3,15}$")
_RAW_DIGEST = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
_ISO_DATE_TIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)
_WEEKDAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
_DIRECTIONS = ("across", "down")


class PersonalizedManifestRejected(ValueError):
    """An xfill result could not be safely bound into a candidate manifest."""


@dataclass(frozen=True)
class GridSlot:
    number: int
    direction: str
    answer: str
    cells: tuple[tuple[int, int], ...]

    @property
    def key(self) -> tuple[int, str]:
        return (self.number, self.direction)

    @property
    def entry_id(self) -> str:
        suffix = "a" if self.direction == "across" else "d"
        return f"{self.number}{suffix}"


@dataclass(frozen=True)
class PersonalizedManifestBuild:
    """Public candidate manifest plus a private retrieval-evidence sidecar."""

    manifest: Mapping[str, Any]
    private_selection: tuple[Mapping[str, Any], ...]
    playable: bool = False


def _reject(code: str) -> None:
    raise PersonalizedManifestRejected(code)


def _mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _reject(code)
    return value


def _text(value: Any, code: str, *, maximum: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        _reject(code)
    return value.strip()


def _freeze_json(value: Any) -> Any:
    """Return JSON-only data with immutable mappings and tuples."""
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    _reject("manifest-value-not-json")


def _plain(value: Any) -> Any:
    """Thaw mapping proxies and tuples while preserving deterministic order."""
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _canonical_number(value: int | float) -> str:
    """Serialize finite numbers using ECMAScript JSON number formatting.

    V2 digests are shared with JavaScript. Python's JSON encoder pads small
    exponents (``1e-07``) and switches to exponent form at a different
    threshold, so delegate the shortest decimal digits to ``repr``/Decimal
    and apply ECMAScript's fixed-versus-exponent thresholds explicitly.
    """
    if isinstance(value, bool):
        _reject("manifest-number-invalid")
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        _reject("manifest-number-non-finite")
    if value == 0:
        return "0"
    try:
        decimal = Decimal(repr(value))
    except InvalidOperation as error:
        raise PersonalizedManifestRejected("manifest-number-invalid") from error
    magnitude = abs(decimal)
    if Decimal("1e-6") <= magnitude < Decimal("1e21"):
        fixed = format(decimal, "f")
        if "." in fixed:
            fixed = fixed.rstrip("0").rstrip(".")
        return fixed
    mantissa, exponent = format(decimal.normalize(), "e").lower().split("e", 1)
    exponent_value = int(exponent)
    exponent_sign = "+" if exponent_value >= 0 else "-"
    return f"{mantissa}e{exponent_sign}{abs(exponent_value)}"


def _canonical_json(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, (int, float)):
        return _canonical_number(value)
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            _reject("manifest-object-key-invalid")
        pairs = (
            f"{_canonical_json(key)}:{_canonical_json(value[key])}"
            for key in sorted(value)
        )
        return "{" + ",".join(pairs) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_canonical_json(item) for item in value) + "]"
    _reject("manifest-value-not-json")


def _canonical_bytes(value: Any) -> bytes:
    try:
        return _canonical_json(value).encode("utf-8", errors="strict")
    except (TypeError, ValueError, RecursionError, UnicodeError) as error:
        raise PersonalizedManifestRejected("manifest-cannot-be-canonicalized") from error


def _is_iso_date_time(value: Any) -> bool:
    if not isinstance(value, str) or not _ISO_DATE_TIME.fullmatch(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _frozen_json_digest(value: Any) -> str:
    """Match the worker's raw canonical-JSON digest for frozen briefs."""
    try:
        encoded = json.dumps(
            _plain(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, RecursionError, UnicodeError) as error:
        raise PersonalizedManifestRejected("frozen-brief-not-canonicalizable") from error
    return hashlib.sha256(encoded).hexdigest()


def derive_xfill_slots(fill: Any) -> tuple[GridSlot, ...]:
    """Derive all maximal numbered across/down runs from a strict 15×15 fill.

    Every open cell must belong to exactly one across and one down run, and all
    runs must be at least three cells long. Entry numbers are derived row-major
    from start cells; engine-provided numbers are checked separately.
    """
    if (
        not isinstance(fill, list)
        or len(fill) != GRID_SIZE
        or any(not isinstance(row, str) or not re.fullmatch(r"[A-Z#]{15}", row) for row in fill)
    ):
        _reject("grid-fill-invalid")

    starts: dict[tuple[int, int], int] = {}
    row_starts = [[False] * GRID_SIZE for _ in range(GRID_SIZE)]
    col_starts = [[False] * GRID_SIZE for _ in range(GRID_SIZE)]
    for row in range(GRID_SIZE):
        for column in range(GRID_SIZE):
            if fill[row][column] == "#":
                continue
            row_starts[row][column] = column == 0 or fill[row][column - 1] == "#"
            col_starts[row][column] = row == 0 or fill[row - 1][column] == "#"
            if row_starts[row][column] or col_starts[row][column]:
                starts[(row, column)] = 0

    for number, coordinate in enumerate(sorted(starts), start=1):
        starts[coordinate] = number

    slots: list[GridSlot] = []
    coverage: dict[tuple[int, int], set[str]] = {
        (row, column): set()
        for row in range(GRID_SIZE)
        for column in range(GRID_SIZE)
        if fill[row][column] != "#"
    }
    for row in range(GRID_SIZE):
        for column in range(GRID_SIZE):
            if (row, column) not in starts:
                continue
            number = starts[(row, column)]
            for direction in _DIRECTIONS:
                is_start = row_starts[row][column] if direction == "across" else col_starts[row][column]
                if not is_start:
                    continue
                delta_row, delta_column = (0, 1) if direction == "across" else (1, 0)
                cells: list[tuple[int, int]] = []
                current_row, current_column = row, column
                while (
                    current_row < GRID_SIZE
                    and current_column < GRID_SIZE
                    and fill[current_row][current_column] != "#"
                ):
                    cells.append((current_row, current_column))
                    coverage[(current_row, current_column)].add(direction)
                    current_row += delta_row
                    current_column += delta_column
                if len(cells) < 3:
                    _reject("grid-entry-too-short")
                slots.append(
                    GridSlot(
                        number=number,
                        direction=direction,
                        answer="".join(fill[r][c] for r, c in cells),
                        cells=tuple(cells),
                    )
                )
    if not slots or any(directions != set(_DIRECTIONS) for directions in coverage.values()):
        _reject("grid-open-cell-incomplete-coverage")
    return tuple(sorted(slots, key=lambda slot: (slot.number, 0 if slot.direction == "across" else 1)))


def _validate_xfill_entries(raw_entries: Any, slots: tuple[GridSlot, ...]) -> None:
    if not isinstance(raw_entries, list) or len(raw_entries) != len(slots):
        _reject("xfill-entry-count-mismatch")
    expected = {slot.key: slot for slot in slots}
    actual: dict[tuple[int, str], str] = {}
    for raw in raw_entries:
        entry = _mapping(raw, "xfill-entry-invalid")
        number = entry.get("num")
        direction = entry.get("dir")
        if type(number) is not int or number < 1 or direction not in {"A", "D"}:
            _reject("xfill-entry-identity-invalid")
        key = (number, "across" if direction == "A" else "down")
        answer = entry.get("answer")
        if not isinstance(answer, str) or not _ANSWER.fullmatch(answer):
            _reject("xfill-entry-answer-invalid")
        if "theme" in entry and not isinstance(entry["theme"], bool):
            _reject("xfill-entry-theme-flag-invalid")
        if key in actual:
            _reject("xfill-entry-duplicate")
        actual[key] = answer
    if set(actual) != set(expected) or any(actual[key] != expected[key].answer for key in expected):
        _reject("xfill-entry-grid-mismatch")


def _source_ids(provenance: Any) -> tuple[str, ...]:
    record = _mapping(provenance, "content-provenance-invalid")
    source = _mapping(record.get("source"), "content-source-invalid")
    source_id = _text(source.get("sourceId"), "content-source-id-invalid", maximum=200)
    return (source_id,)


def _validate_source_references(value: Any, sources: Mapping[str, Any]) -> None:
    if (
        not isinstance(value, (list, tuple))
        or not value
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
        or any(item not in sources for item in value)
    ):
        _reject("manifest-provenance-source-reference-invalid")


def _validate_evidence_provenance(
    value: Any, source_ids: Sequence[str], sources: Mapping[str, Any]
) -> None:
    evidence = _mapping(value, "manifest-evidence-provenance-invalid")
    if set(evidence) != {"source", "evidenceRefs", "reviewerId", "reviewedAt"}:
        _reject("manifest-evidence-provenance-shape-invalid")
    source = _mapping(evidence.get("source"), "manifest-evidence-source-invalid")
    expected_source = {"sourceId", "version", "artifactSha256", "spdx", "attribution", "contentClass"}
    if (
        set(source) != expected_source
        or source.get("sourceId") not in source_ids
        or sources.get(source.get("sourceId")) != source
    ):
        _reject("manifest-evidence-source-invalid")
    refs = evidence.get("evidenceRefs")
    if not isinstance(refs, (list, tuple)) or not refs or any(not isinstance(ref, str) or not ref for ref in refs) or len(refs) != len(set(refs)):
        _reject("manifest-evidence-refs-invalid")
    if not isinstance(evidence.get("reviewerId"), str) or not evidence["reviewerId"].strip():
        _reject("manifest-evidence-reviewer-invalid")
    if not isinstance(evidence.get("reviewedAt"), str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", evidence["reviewedAt"]):
        _reject("manifest-evidence-reviewed-at-invalid")


def _source_projection(source: Mapping[str, Any]) -> dict[str, Any]:
    # Keep the exact pin and attribution fields; a digest alone is not the full
    # source record that was admitted by the host configuration.
    required = {"sourceId", "version", "artifactSha256", "spdx", "attribution", "contentClass"}
    if set(source) != required:
        _reject("content-source-pin-malformed")
    if not _RAW_DIGEST.fullmatch(str(source.get("artifactSha256", ""))):
        _reject("content-source-digest-invalid")
    return dict(source)


def _v2_source_pin(source: Mapping[str, Any]) -> dict[str, Any]:
    return _source_projection(source)


def _get_content_lexemes(content: Any) -> tuple[AdmittedLexemeContent, ...]:
    if not isinstance(content, AdmittedPackContent) or not content.lexemes:
        _reject("pinned-content-projection-required")
    return content.lexemes


def _frozen_profile_evidence(job: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    """Authenticate the frozen/recompiled brief and index exact evidence IDs."""
    job_version = job.get("version")
    brief = job.get("compiledBrief")
    if not isinstance(brief, Mapping):
        _reject("frozen-compiled-brief-required")
    digest = job.get("compiledBriefDigest")
    if not isinstance(digest, str) or digest != _frozen_json_digest(brief):
        _reject("frozen-compiled-brief-digest-mismatch")
    compiler_version = job.get("briefCompilerVersion")
    if job_version == 4:
        if compiler_version != "compile-episteme-brief-v1":
            _reject("frozen-brief-compiler-version-invalid")
    elif job_version == 3:
        if compiler_version not in {"worker-recompiled-v1", "compile-episteme-brief-v1"}:
            _reject("legacy-brief-recompile-receipt-invalid")
    else:
        _reject("frozen-job-version-unsupported")
    if (
        brief.get("briefVersion") != "episteme-brief-v1"
        or brief.get("profileId") != job.get("profileId")
        or brief.get("profileRevision") != job.get("epistemeRevision")
        or brief.get("asOf") != job.get("asOf")
        or brief.get("mode") != "play"
        or brief.get("language") != job.get("puzzleLanguage")
        or type(brief.get("selectionLimit")) is not int
    ):
        _reject("frozen-compiled-brief-snapshot-mismatch")
    log = brief.get("selectionLog")
    selected = brief.get("selected")
    if not isinstance(log, (list, tuple)) or not isinstance(selected, (list, tuple)):
        _reject("frozen-compiled-brief-selection-invalid")
    evidence_by_id: dict[str, tuple[str, ...]] = {}
    log_rows: dict[str, Mapping[str, Any]] = {}
    for raw_row in log:
        row = _mapping(raw_row, "frozen-brief-selection-log-invalid")
        candidate_id = row.get("candidateId")
        evidence_ids = row.get("evidenceIds")
        if (
            not isinstance(candidate_id, str)
            or not candidate_id
            or candidate_id in log_rows
            or not isinstance(evidence_ids, (list, tuple))
            or any(not isinstance(item, str) or not item for item in evidence_ids)
            or len(evidence_ids) != len(set(evidence_ids))
        ):
            _reject("frozen-brief-selection-log-invalid")
        log_rows[candidate_id] = row
        evidence_by_id[candidate_id] = tuple(evidence_ids)
    selected_ids: set[str] = set()
    for raw_row in selected:
        row = _mapping(raw_row, "frozen-brief-selected-row-invalid")
        candidate = _mapping(row.get("candidate"), "frozen-brief-selected-candidate-invalid")
        candidate_id = candidate.get("candidateId")
        if not isinstance(candidate_id, str) or candidate_id not in log_rows or candidate_id in selected_ids:
            _reject("frozen-brief-selected-candidate-invalid")
        log_row = log_rows[candidate_id]
        if (
            log_row.get("selected") is not True
            or row.get("evidenceIds") != list(evidence_by_id[candidate_id])
            or log_row.get("evidenceIds") != row.get("evidenceIds")
        ):
            _reject("frozen-brief-selected-evidence-mismatch")
        selected_ids.add(candidate_id)
    if {row_id for row_id, row in log_rows.items() if row.get("selected") is True} != selected_ids:
        _reject("frozen-brief-selection-log-mismatch")
    return evidence_by_id


def _select_entry_content(
    *,
    link: Mapping[str, Any],
    slot: GridSlot,
    lexemes_by_id: Mapping[str, AdmittedLexemeContent],
    language: str,
    profile_evidence_by_candidate: Mapping[str, tuple[str, ...]],
) -> tuple[AdmittedLexemeContent, Any, Any, str | None]:
    if link.get("entryNumber") != slot.number or link.get("direction") != slot.direction:
        _reject("entry-source-link-identity-mismatch")
    if link.get("answer") != slot.answer:
        _reject("entry-source-link-answer-mismatch")
    candidate_ids = link.get("candidateIds")
    if not isinstance(candidate_ids, (list, tuple)) or len(candidate_ids) != 1:
        _reject("entry-candidate-ambiguous")
    candidate_id = candidate_ids[0]
    if not isinstance(candidate_id, str) or candidate_id not in lexemes_by_id:
        _reject("entry-candidate-not-in-pinned-content")
    lexeme = lexemes_by_id[candidate_id]
    if lexeme.answer != slot.answer or lexeme.language != language:
        _reject("entry-candidate-answer-or-language-mismatch")
    source_ids = link.get("sourceIds")
    exact_source_ids = sorted(_source_ids(lexeme.provenance))
    if (
        not isinstance(source_ids, (list, tuple))
        or list(source_ids) != sorted(set(source_ids))
        or list(source_ids) != exact_source_ids
    ):
        _reject("entry-candidate-source-pin-mismatch")

    clue_id = link.get("clueId")
    if not isinstance(clue_id, str) or not clue_id:
        _reject("entry-clue-id-required")
    matches = [clue for clue in lexeme.clues if clue.clue_id == clue_id]
    if len(matches) != 1:
        _reject("entry-clue-missing-or-ambiguous")
    clue = matches[0]
    if clue.answer_lexeme_id != lexeme.lexeme_id:
        _reject("entry-clue-answer-reference-mismatch")

    explicit_sense_id = link.get("senseId")
    explicit_fact_id = link.get("factId")
    sense = None
    fact = None
    if clue.evidence_type == "sense":
        if explicit_sense_id != clue.evidence_id or explicit_fact_id is not None:
            _reject("entry-clue-sense-link-mismatch")
        senses = [row for row in lexeme.senses if row.sense_id == clue.evidence_id]
        if len(senses) != 1:
            _reject("entry-clue-sense-missing-or-ambiguous")
        sense = senses[0]
        if (
            sense.clue_eligible is not True
            or sense.fill_only is not False
            or sense.resolution_status != "resolved"
        ):
            _reject("entry-clue-sense-ineligible")
        if clue.provenance.get("evidenceProvenance") != sense.provenance:
            _reject("entry-clue-sense-provenance-mismatch")
    elif clue.evidence_type == "fact":
        if explicit_fact_id != clue.evidence_id or not isinstance(explicit_sense_id, str):
            _reject("entry-clue-fact-and-sense-links-required")
        senses = [row for row in lexeme.senses if row.sense_id == explicit_sense_id]
        facts = [row for row in lexeme.facts if row.fact_id == clue.evidence_id]
        if len(senses) != 1 or len(facts) != 1:
            _reject("entry-clue-fact-or-sense-missing-or-ambiguous")
        sense, fact = senses[0], facts[0]
        if (
            sense.clue_eligible is not True
            or sense.fill_only is not False
            or sense.resolution_status != "resolved"
        ):
            _reject("entry-clue-fact-sense-ineligible")
        if clue.provenance.get("evidenceProvenance") != facts[0].provenance:
            _reject("entry-clue-fact-provenance-mismatch")
    else:
        _reject("entry-clue-evidence-type-unsupported")

    profile_evidence_ids = link.get("profileEvidenceIds")
    if (
        not isinstance(profile_evidence_ids, (list, tuple))
        or any(not isinstance(item, str) or not item.strip() for item in profile_evidence_ids)
        or len(profile_evidence_ids) != len(set(profile_evidence_ids))
    ):
        _reject("entry-profile-evidence-invalid")
    if list(profile_evidence_ids) != list(profile_evidence_by_candidate.get(candidate_id, ())):
        _reject("entry-profile-evidence-does-not-match-frozen-brief")
    return lexeme, clue, sense, (fact.fact_id if fact is not None else None)


def build_personalized_manifest(
    grid: Any,
    entry_source_links: Any,
    *,
    content: AdmittedPackContent,
    frozen_job: Mapping[str, Any],
    version_inputs: Mapping[str, Any],
) -> PersonalizedManifestBuild:
    """Validate a host-selected xfill grid and make a non-playable V2 candidate.

    ``entry_source_links`` must be assembled by the trusted host and include an
    exact ``clueId`` plus the evidence ID(s) used by that clue. Raw client
    content is never accepted here. Current pack records have no separate
    semantic-truth attestation, so this adapter records ``review`` and never
    marks the resulting candidate playable.
    """
    grid = _mapping(grid, "xfill-grid-invalid")
    if set(grid) != {"fill", "entries"}:
        _reject("xfill-grid-shape-invalid")
    slots = derive_xfill_slots(grid.get("fill"))
    _validate_xfill_entries(grid.get("entries"), slots)
    if not isinstance(entry_source_links, (list, tuple)) or len(entry_source_links) != len(slots):
        _reject("entry-source-link-count-mismatch")
    link_by_key: dict[tuple[int, str], Mapping[str, Any]] = {}
    for raw_link in entry_source_links:
        link = _mapping(raw_link, "entry-source-link-invalid")
        number, direction = link.get("entryNumber"), link.get("direction")
        key = (number, direction)
        if type(number) is not int or direction not in _DIRECTIONS or key in link_by_key:
            _reject("entry-source-link-identity-invalid")
        link_by_key[key] = link
    if set(link_by_key) != {slot.key for slot in slots}:
        _reject("entry-source-link-slot-coverage-invalid")

    job = _mapping(frozen_job, "frozen-job-receipt-invalid")
    required_job = {
        "profileId", "weekdayDifficulty", "puzzleLanguage", "epistemeRevision",
        "epistemeDigest", "packId", "packSha256", "sourcePins", "seed", "recipe", "version", "asOf",
    }
    if not required_job.issubset(job):
        _reject("frozen-job-receipt-incomplete")
    language = _text(job.get("puzzleLanguage"), "frozen-language-invalid", maximum=32)
    if type(job.get("epistemeRevision")) is not int or job["epistemeRevision"] < 0:
        _reject("frozen-episteme-revision-invalid")
    if not _RAW_DIGEST.fullmatch(str(job.get("epistemeDigest", ""))):
        _reject("frozen-episteme-digest-invalid")
    if type(job.get("seed")) is not int or not 0 <= job["seed"] <= 2_147_483_647:
        _reject("frozen-construction-seed-invalid")
    if job.get("packId") != content.pack_id or job.get("packSha256") != content.pack_sha256:
        _reject("frozen-pack-receipt-mismatch")
    if not _RAW_DIGEST.fullmatch(str(job.get("packSha256", ""))):
        _reject("frozen-pack-digest-invalid")
    pins = job.get("sourcePins")
    if not isinstance(pins, (list, tuple)) or not pins:
        _reject("frozen-source-pins-missing")
    pin_by_id: dict[str, Mapping[str, Any]] = {}
    for raw_pin in pins:
        pin = _mapping(raw_pin, "frozen-source-pin-invalid")
        source_id = _text(pin.get("sourceId"), "frozen-source-pin-invalid", maximum=200)
        if (
            source_id in pin_by_id
            or not isinstance(pin.get("version"), str)
            or not isinstance(pin.get("artifactSha256"), str)
            or not _RAW_DIGEST.fullmatch(pin["artifactSha256"])
            or pin.get("contentClass") not in {"public", "synthetic"}
        ):
            _reject("frozen-source-pin-invalid")
        pin_by_id[source_id] = pin
    profile_evidence_by_candidate = _frozen_profile_evidence(job)

    versions = _mapping(version_inputs, "manifest-version-inputs-invalid")
    generated_at = _text(versions.get("generatedAt"), "manifest-generated-at-invalid", maximum=64)
    if not _is_iso_date_time(generated_at):
        _reject("manifest-generated-at-invalid")
    recipe = _mapping(versions.get("recipe"), "manifest-recipe-invalid")
    runtime = _mapping(versions.get("runtime"), "manifest-runtime-invalid")
    validators = versions.get("validators")
    if not isinstance(validators, (list, tuple)) or not validators:
        _reject("manifest-validator-versions-required")
    if set(recipe) != {"id", "version", "weekday"}:
        _reject("manifest-recipe-shape-invalid")
    if set(runtime) != {"id", "version", "artifactDigest"}:
        _reject("manifest-runtime-shape-invalid")
    validator_ids: set[str] = set()
    for raw_validator in validators:
        validator = _mapping(raw_validator, "manifest-validator-version-invalid")
        if set(validator) != {"id", "version"}:
            _reject("manifest-validator-shape-invalid")
        validator_id = _text(validator.get("id"), "manifest-version-id-invalid", maximum=200)
        if validator_id in validator_ids:
            _reject("manifest-validator-id-duplicate")
        validator_ids.add(validator_id)
    for versioned in [recipe, runtime, *validators]:
        record = _mapping(versioned, "manifest-version-record-invalid")
        if not _text(record.get("id"), "manifest-version-id-invalid", maximum=200):
            _reject("manifest-version-id-invalid")
        if not _text(record.get("version"), "manifest-version-number-invalid", maximum=100):
            _reject("manifest-version-number-invalid")
    if recipe.get("weekday") != job.get("weekdayDifficulty") or recipe.get("id") != job.get("recipe"):
        _reject("manifest-recipe-job-mismatch")
    runtime_digest = runtime.get("artifactDigest")
    if not isinstance(runtime_digest, str) or not _RAW_DIGEST.fullmatch(runtime_digest):
        _reject("manifest-runtime-digest-invalid")
    runtime = {**runtime, "artifactDigest": runtime_digest.removeprefix("sha256:")}

    lexemes = _get_content_lexemes(content)
    lexemes_by_id = {lexeme.lexeme_id: lexeme for lexeme in lexemes}
    if len(lexemes_by_id) != len(lexemes):
        _reject("pinned-content-lexeme-duplicate")

    entries: list[dict[str, Any]] = []
    clues: list[dict[str, Any]] = []
    lexeme_records: dict[str, dict[str, Any]] = {}
    sense_records: dict[str, dict[str, Any]] = {}
    fact_records: dict[str, dict[str, Any]] = {}
    clue_records: dict[str, dict[str, Any]] = {}
    source_records: dict[str, dict[str, Any]] = {}
    private_selection: list[dict[str, Any]] = []
    quality_reasons = {"semantic-truth-not-established"}

    for slot in slots:
        link = link_by_key[slot.key]
        lexeme, clue, sense, fact_id = _select_entry_content(
            link=link,
            slot=slot,
            lexemes_by_id=lexemes_by_id,
            language=language,
            profile_evidence_by_candidate=profile_evidence_by_candidate,
        )
        if clue.provenance.get("semanticTruthStatus") != "not-established-by-grammar-validator":
            _reject("entry-clue-semantic-status-unrecognized")
        lexeme_sources = _source_ids(lexeme.provenance)
        clue_provenance = _mapping(clue.provenance, "entry-clue-provenance-invalid")
        clue_sources = clue_provenance.get("sources")
        if not isinstance(clue_sources, (list, tuple)) or not clue_sources:
            _reject("entry-clue-source-provenance-missing")
        clue_source_ids: list[str] = []
        for raw_source in clue_sources:
            source = _source_projection(_mapping(raw_source, "entry-clue-source-invalid"))
            source_id = source["sourceId"]
            pin = pin_by_id.get(source_id)
            if pin is None or any(
                pin.get(key) != source[key]
                for key in ("version", "artifactSha256", "contentClass")
            ):
                _reject("entry-clue-source-pin-mismatch")
            v2_pin = _v2_source_pin(source)
            previous = source_records.get(source_id)
            if previous is not None and previous != v2_pin:
                _reject("pinned-source-record-conflict")
            source_records[source_id] = v2_pin
            clue_source_ids.append(source_id)
        for raw_source in [lexeme.provenance["source"]]:
            source = _source_projection(_mapping(raw_source, "entry-lexeme-source-invalid"))
            source_id = source["sourceId"]
            pin = pin_by_id.get(source_id)
            if pin is None or any(
                pin.get(key) != source[key]
                for key in ("version", "artifactSha256", "contentClass")
            ):
                _reject("entry-lexeme-source-pin-mismatch")
            v2_pin = _v2_source_pin(source)
            previous = source_records.get(source_id)
            if previous is not None and previous != v2_pin:
                _reject("pinned-source-record-conflict")
            source_records[source_id] = v2_pin

        entry_id = slot.entry_id
        clue_variant_id = f"{clue.clue_id}@{entry_id}"
        grammar = _plain(clue.grammar)
        if not isinstance(grammar, dict):
            _reject("entry-clue-grammar-invalid")
        if (
            grammar.get("grammarVersion") != "clue-grammar-v1"
            or grammar.get("clueId") != clue.clue_id
            or grammar.get("clueText") != clue.text
            or grammar.get("answer") != lexeme.answer
            or not isinstance(grammar.get("variantRole"), str)
            or not isinstance(grammar.get("primaryFamily"), str)
            or not isinstance(grammar.get("signalSpans"), (list, tuple))
        ):
            _reject("entry-clue-grammar-source-mismatch")
        grammar["entryId"] = entry_id
        grammar["clueId"] = clue_variant_id
        if grammar["answer"] != lexeme.answer or grammar["clueText"] != clue.text:
            _reject("entry-clue-grammar-answer-mismatch")

        entry = {
            "id": entry_id,
            "number": slot.number,
            "direction": slot.direction,
            "cellIds": [f"r{row}c{column}" for row, column in slot.cells],
            "answer": slot.answer,
            "lexemeId": lexeme.lexeme_id,
            "senseId": sense.sense_id,
        }
        retrieval_task_id = link.get("retrievalTaskId")
        if retrieval_task_id is not None:
            entry["retrievalTaskId"] = _text(retrieval_task_id, "entry-retrieval-task-invalid", maximum=200)
        entries.append(entry)

        support_sense_ids = [sense.sense_id]
        support_fact_ids = [fact_id] if fact_id is not None else []
        clues.append({
            "clueVariantId": clue_variant_id,
            "sourceClueId": clue.clue_id,
            "entryId": entry_id,
            "variantRole": grammar.get("variantRole"),
            "primaryFamily": grammar.get("primaryFamily"),
            "text": clue.text,
            "grammar": grammar,
            "support": {"senseIds": support_sense_ids, "factIds": support_fact_ids},
        })

        source_ids = sorted(set(lexeme_sources))
        existing_lexeme = lexeme_records.get(lexeme.lexeme_id)
        lexeme_record = {"id": lexeme.lexeme_id, "sourceIds": source_ids}
        if existing_lexeme is not None and existing_lexeme != lexeme_record:
            _reject("manifest-lexeme-provenance-conflict")
        lexeme_records[lexeme.lexeme_id] = lexeme_record

        sense_provenance = _mapping(sense.provenance, "entry-sense-provenance-invalid")
        sense_source_ids = sorted(_source_ids(sense.provenance))
        sense_record = {
            "id": sense.sense_id,
            "lexemeId": lexeme.lexeme_id,
            "sourceIds": sense_source_ids,
            "evidenceProvenance": _plain(sense_provenance),
        }
        sense_record["evidenceProvenance"] = {
            "source": _source_projection(_mapping(sense_provenance.get("source"), "entry-sense-source-invalid")),
            "evidenceRefs": list(sense_provenance.get("evidenceRefs", ())),
            "reviewerId": sense_provenance.get("reviewerId"),
            "reviewedAt": sense_provenance.get("reviewedAt"),
        }
        previous_sense = sense_records.get(sense.sense_id)
        if previous_sense is not None and previous_sense != sense_record:
            _reject("manifest-sense-provenance-conflict")
        sense_records[sense.sense_id] = sense_record
        for source_id in sense_source_ids:
            source = _source_projection(_mapping(sense_provenance["source"], "entry-sense-source-invalid"))
            if source["sourceId"] != source_id:
                _reject("entry-sense-source-reference-invalid")
            pin = pin_by_id.get(source_id)
            if pin is None or any(pin.get(key) != source[key] for key in ("version", "artifactSha256", "contentClass")):
                _reject("entry-sense-source-pin-mismatch")
            source_records[source_id] = _v2_source_pin(source)

        if fact_id is not None:
            fact = next(row for row in lexeme.facts if row.fact_id == fact_id)
            fact_provenance = _mapping(fact.provenance, "entry-fact-provenance-invalid")
            fact_source_ids = sorted(_source_ids(fact.provenance))
            fact_record = {
                "id": fact.fact_id,
                "lexemeId": lexeme.lexeme_id,
                "sourceIds": fact_source_ids,
                "evidenceProvenance": {
                    "source": _source_projection(_mapping(fact_provenance.get("source"), "entry-fact-source-invalid")),
                    "evidenceRefs": list(fact_provenance.get("evidenceRefs", ())),
                    "reviewerId": fact_provenance.get("reviewerId"),
                    "reviewedAt": fact_provenance.get("reviewedAt"),
                },
                "review": "verified",
            }
            previous_fact = fact_records.get(fact.fact_id)
            if previous_fact is not None and previous_fact != fact_record:
                _reject("manifest-fact-provenance-conflict")
            fact_records[fact.fact_id] = fact_record
            for source_id in fact_source_ids:
                source = _source_projection(_mapping(fact_provenance["source"], "entry-fact-source-invalid"))
                if source["sourceId"] != source_id:
                    _reject("entry-fact-source-reference-invalid")
                pin = pin_by_id.get(source_id)
                if pin is None or any(pin.get(key) != source[key] for key in ("version", "artifactSha256", "contentClass")):
                    _reject("entry-fact-source-pin-mismatch")
                source_records[source_id] = _v2_source_pin(source)

        evidence_provenance = clue_provenance.get("evidenceProvenance")
        evidence_provenance = _mapping(evidence_provenance, "entry-clue-evidence-provenance-invalid")
        exact_evidence_refs = clue_provenance.get("evidenceRefs")
        if not isinstance(exact_evidence_refs, (list, tuple)) or not exact_evidence_refs:
            _reject("entry-clue-evidence-refs-missing")
        evidence_source = _source_projection(_mapping(evidence_provenance.get("source"), "entry-clue-evidence-source-invalid"))
        evidence_source_id = evidence_source["sourceId"]
        evidence_pin = pin_by_id.get(evidence_source_id)
        if evidence_pin is None or any(
            evidence_pin.get(key) != evidence_source[key]
            for key in ("version", "artifactSha256", "contentClass")
        ):
            _reject("entry-clue-evidence-source-pin-mismatch")
        source_records[evidence_source_id] = _v2_source_pin(evidence_source)
        clue_source_ids_for_support = (
            clue_source_ids
            + sense_source_ids
            + (fact_source_ids if fact_id is not None else [])
        )
        clue_record = {
            "clueVariantId": clue_variant_id,
            "sourceClueId": clue.clue_id,
            "entryId": entry_id,
            "senseIds": support_sense_ids,
            "factIds": support_fact_ids,
            "sourceIds": sorted(set(clue_source_ids_for_support)),
            "evidenceKind": clue.evidence_type,
            "evidenceId": clue.evidence_id,
            "evidenceRefs": list(exact_evidence_refs),
            "evidenceProvenance": {
                "source": evidence_source,
                "evidenceRefs": list(evidence_provenance.get("evidenceRefs", ())),
                "reviewerId": evidence_provenance.get("reviewerId"),
                "reviewedAt": evidence_provenance.get("reviewedAt"),
            },
            "reviewerId": clue_provenance.get("reviewerId"),
            "reviewedAt": clue_provenance.get("reviewedAt"),
            "semanticTruthStatus": "not-established-by-grammar-validator",
        }
        if clue_variant_id in clue_records:
            _reject("manifest-clue-selected-more-than-once")
        clue_records[clue_variant_id] = clue_record

        profile_evidence_ids = link.get("profileEvidenceIds", [])
        private_selection.append({
            "entryId": entry_id,
            "candidateId": lexeme.lexeme_id,
            "clueId": clue.clue_id,
            "clueVariantId": clue_variant_id,
            "senseId": sense.sense_id,
            "factId": fact_id,
            "profileEvidenceIds": list(profile_evidence_ids),
        })

    cells = []
    for row in range(GRID_SIZE):
        for column in range(GRID_SIZE):
            token = grid["fill"][row][column]
            is_block = token == "#"
            cells.append({
                "id": f"r{row}c{column}",
                "row": row,
                "column": column,
                "block": is_block,
                "circled": False,
                "shaded": False,
                "token": None if is_block else token,
            })

    crossing_edges = []
    entry_by_cell: dict[tuple[int, int], dict[str, GridSlot]] = {}
    for slot in slots:
        for coordinate in slot.cells:
            entry_by_cell.setdefault(coordinate, {})[slot.direction] = slot
    for (row, column), paired in sorted(entry_by_cell.items()):
        if set(paired) == set(_DIRECTIONS):
            across, down = paired["across"], paired["down"]
            # Letter agreement is directly measured from the same pinned fill.
            crossing_edges.append({
                "acrossEntryId": across.entry_id,
                "downEntryId": down.entry_id,
                "cellId": f"r{row}c{column}",
                # Letter agreement is a construction invariant, not evidence
                # that a player can use this crossing. Until a calibrated
                # estimate bundle exists, expose only a conservative zero.
                "score": 0,
                "confidence": 0,
            })

    manifest_id_digest = hashlib.sha256(
        _canonical_bytes({"pack": content.pack_sha256, "seed": job["seed"], "fill": grid["fill"]})
    ).hexdigest()[:32]
    manifest: dict[str, Any] = {
        "schemaVersion": 2,
        "id": f"personalized-{manifest_id_digest}",
        "seed": str(job["seed"]),
        "title": "A crossword shaped by your episteme",
        "subtitle": f"{job['weekdayDifficulty']} · {language}",
        "width": GRID_SIZE,
        "height": GRID_SIZE,
        "language": language,
        "languagePolicy": {
            "version": "ascii-uppercase-v1",
            "cellTokenPolicy": "single-ascii-letter-v1",
        },
        "cells": cells,
        "entries": entries,
        "clues": clues,
        "mechanics": [],
        "provenance": {
            "sources": [source_records[key] for key in sorted(source_records)],
            "lexemes": [lexeme_records[key] for key in sorted(lexeme_records)],
            "senses": [sense_records[key] for key in sorted(sense_records)],
            "facts": [fact_records[key] for key in sorted(fact_records)],
            "clues": [clue_records[key] for key in sorted(clue_records)],
        },
        "topology": {
            "width": GRID_SIZE,
            "height": GRID_SIZE,
            "blockedCellIds": [cell["id"] for cell in cells if cell["block"]],
            "minEntryLength": 3,
            "numbering": "standard-row-major-v1",
        },
        "receipt": {
            "constructionSeed": str(job["seed"]),
            "recipe": dict(recipe),
            "runtime": dict(runtime),
            "validators": [dict(_mapping(row, "manifest-validator-version-invalid")) for row in validators],
            "generatedAt": generated_at,
            "profileProjection": {
                "revision": job["epistemeRevision"],
                "digest": str(job["epistemeDigest"]).removeprefix("sha256:"),
            },
        },
        "crossingSupport": {
            "version": "structural-letter-agreement-v1",
            "edges": crossing_edges,
            "minimumScore": 0,
            "meanScore": 0,
            "uncertainty": {
                "level": "unknown",
                "notes": "Crossing letters agree with the completed fill, but no calibrated player support estimate is available.",
            },
        },
        "quality": {
            "verdict": "review",
            "reasons": sorted(quality_reasons | {"crossing-support-uncalibrated"}),
        },
    }
    manifest["integrity"] = {
        "algorithm": "sha256",
        "canonicalization": "json-canonical-v1",
        "value": _digest(manifest),
    }
    validate_personalized_manifest(manifest)
    return PersonalizedManifestBuild(
        manifest=_freeze_json(manifest),
        private_selection=_freeze_json(private_selection),
        playable=False,
    )


def validate_personalized_manifest(value: Any) -> bool:
    """Validate the topology and conservative evidence shape of a V2 candidate."""
    manifest = _mapping(value, "manifest-invalid")
    expected_root = {
        "schemaVersion", "id", "seed", "title", "subtitle", "width", "height", "language",
        "languagePolicy", "cells", "entries", "clues", "mechanics", "provenance", "topology",
        "receipt", "crossingSupport", "quality", "integrity",
    }
    if set(manifest) != expected_root:
        _reject("manifest-root-shape-invalid")
    if manifest.get("schemaVersion") != 2 or manifest.get("width") != GRID_SIZE or manifest.get("height") != GRID_SIZE:
        _reject("manifest-version-or-dimensions-invalid")
    if manifest.get("languagePolicy") != {
        "version": "ascii-uppercase-v1",
        "cellTokenPolicy": "single-ascii-letter-v1",
    }:
        _reject("manifest-language-policy-invalid")
    cells = manifest.get("cells")
    if not isinstance(cells, (list, tuple)) or len(cells) != GRID_SIZE * GRID_SIZE:
        _reject("manifest-cell-count-invalid")
    fill = []
    for row in range(GRID_SIZE):
        chars = []
        for column in range(GRID_SIZE):
            cell = _mapping(cells[row * GRID_SIZE + column], "manifest-cell-invalid")
            if set(cell) != {"id", "row", "column", "block", "circled", "shaded", "token"}:
                _reject("manifest-cell-shape-invalid")
            expected_id = f"r{row}c{column}"
            if cell.get("id") != expected_id or cell.get("row") != row or cell.get("column") != column:
                _reject("manifest-cell-order-invalid")
            if not isinstance(cell.get("block"), bool) or not isinstance(cell.get("circled"), bool) or not isinstance(cell.get("shaded"), bool):
                _reject("manifest-cell-flags-invalid")
            if cell.get("block") is True:
                if cell.get("token") is not None:
                    _reject("manifest-block-token-invalid")
                chars.append("#")
            else:
                token = cell.get("token")
                if not isinstance(token, str) or not _LETTER.fullmatch(token):
                    _reject("manifest-open-cell-token-invalid")
                chars.append(token)
        fill.append("".join(chars))
    slots = derive_xfill_slots(fill)
    entries = manifest.get("entries")
    if not isinstance(entries, (list, tuple)) or len(entries) != len(slots):
        _reject("manifest-entry-count-invalid")
    expected = {slot.key: slot for slot in slots}
    seen = set()
    entries_by_id: dict[str, Mapping[str, Any]] = {}
    for raw in entries:
        entry = _mapping(raw, "manifest-entry-invalid")
        if set(entry) - {"id", "number", "direction", "cellIds", "answer", "lexemeId", "senseId", "retrievalTaskId"}:
            _reject("manifest-entry-shape-invalid")
        key = (entry.get("number"), entry.get("direction"))
        if key not in expected or key in seen:
            _reject("manifest-entry-identity-invalid")
        slot = expected[key]
        if (
            entry.get("id") != slot.entry_id
            or entry.get("answer") != slot.answer
            or list(entry.get("cellIds", ())) != [f"r{r}c{c}" for r, c in slot.cells]
            or not isinstance(entry.get("lexemeId"), str)
            or not isinstance(entry.get("senseId"), str)
        ):
            _reject("manifest-entry-topology-or-provenance-invalid")
        seen.add(key)
        if entry["id"] in entries_by_id:
            _reject("manifest-entry-id-duplicate")
        entries_by_id[entry["id"]] = entry

    topology = _mapping(manifest.get("topology"), "manifest-topology-invalid")
    if set(topology) != {"width", "height", "blockedCellIds", "minEntryLength", "numbering"}:
        _reject("manifest-topology-shape-invalid")
    blocked_ids = [cell["id"] for cell in cells if cell["block"] is True]
    if (
        topology.get("width") != GRID_SIZE
        or topology.get("height") != GRID_SIZE
        or list(topology.get("blockedCellIds", ())) != blocked_ids
        or topology.get("minEntryLength") != 3
        or topology.get("numbering") != "standard-row-major-v1"
    ):
        _reject("manifest-topology-mismatch")

    clues = manifest.get("clues")
    if not isinstance(clues, (list, tuple)) or len(clues) != len(entries):
        _reject("manifest-clue-count-invalid")
    clue_by_id: dict[str, Mapping[str, Any]] = {}
    for raw_clue in clues:
        clue = _mapping(raw_clue, "manifest-clue-invalid")
        required_clue = {"clueVariantId", "sourceClueId", "entryId", "variantRole", "primaryFamily", "text", "grammar", "support"}
        if set(clue) != required_clue:
            _reject("manifest-clue-shape-invalid")
        clue_id = clue.get("clueVariantId")
        entry = entries_by_id.get(clue.get("entryId"))
        grammar = _mapping(clue.get("grammar"), "manifest-clue-grammar-invalid")
        support = _mapping(clue.get("support"), "manifest-clue-support-invalid")
        if (
            not isinstance(clue_id, str)
            or clue_id in clue_by_id
            or entry is None
            or not isinstance(clue.get("sourceClueId"), str)
            or not isinstance(clue.get("text"), str)
            or set(support) != {"senseIds", "factIds"}
            or list(support.get("senseIds", ())) != [entry["senseId"]]
            or not isinstance(support.get("factIds"), (list, tuple))
            or any(not isinstance(item, str) for item in support.get("factIds", ()))
        ):
            _reject("manifest-clue-link-invalid")
        if (
            grammar.get("clueId") != clue_id
            or grammar.get("entryId") != entry["id"]
            or grammar.get("clueText") != clue["text"]
            or grammar.get("answer") != entry["answer"]
            or grammar.get("variantRole") != clue["variantRole"]
            or grammar.get("primaryFamily") != clue["primaryFamily"]
        ):
            _reject("manifest-clue-grammar-link-invalid")
        clue_by_id[clue_id] = clue
    if {clue["entryId"] for clue in clue_by_id.values()} != set(entries_by_id):
        _reject("manifest-clue-entry-coverage-invalid")

    provenance = _mapping(manifest.get("provenance"), "manifest-provenance-invalid")
    if set(provenance) != {"sources", "lexemes", "senses", "facts", "clues"}:
        _reject("manifest-provenance-shape-invalid")
    if any(not isinstance(provenance.get(key), (list, tuple)) for key in ("sources", "lexemes", "senses", "facts", "clues")):
        _reject("manifest-provenance-arrays-invalid")
    source_rows = [_mapping(row, "manifest-source-pin-invalid") for row in provenance["sources"]]
    source_by_id = {row.get("sourceId"): row for row in source_rows}
    if len(source_by_id) != len(source_rows) or any(
        not isinstance(source_id, str)
        or set(row) != {"sourceId", "version", "artifactSha256", "spdx", "attribution", "contentClass"}
        or not isinstance(row.get("artifactSha256"), str)
        or not _RAW_DIGEST.fullmatch(row["artifactSha256"])
        for source_id, row in source_by_id.items()
    ):
        _reject("manifest-source-pin-invalid")
    provenance_rows: dict[str, dict[str, Mapping[str, Any]]] = {}
    for kind in ("lexemes", "senses", "facts", "clues"):
        rows = [_mapping(row, f"manifest-{kind}-provenance-invalid") for row in provenance[kind]]
        id_key = "clueVariantId" if kind == "clues" else "id"
        by_id = {row.get(id_key): row for row in rows}
        if len(by_id) != len(rows) or any(not isinstance(row_id, str) for row_id in by_id):
            _reject(f"manifest-{kind}-provenance-duplicate")
        provenance_rows[kind] = by_id
    if set(provenance_rows["clues"]) != set(clue_by_id):
        _reject("manifest-clue-provenance-coverage-invalid")
    for lexeme in provenance_rows["lexemes"].values():
        if set(lexeme) != {"id", "sourceIds"}:
            _reject("manifest-lexeme-provenance-shape-invalid")
        _validate_source_references(lexeme.get("sourceIds"), source_by_id)
    for sense in provenance_rows["senses"].values():
        if set(sense) != {"id", "lexemeId", "sourceIds", "evidenceProvenance"}:
            _reject("manifest-sense-provenance-shape-invalid")
        _validate_source_references(sense.get("sourceIds"), source_by_id)
        _validate_evidence_provenance(sense.get("evidenceProvenance"), sense["sourceIds"], source_by_id)
    for fact in provenance_rows["facts"].values():
        if set(fact) != {"id", "lexemeId", "sourceIds", "review", "evidenceProvenance"}:
            _reject("manifest-fact-provenance-shape-invalid")
        _validate_source_references(fact.get("sourceIds"), source_by_id)
        _validate_evidence_provenance(fact.get("evidenceProvenance"), fact["sourceIds"], source_by_id)
    for clue_id, clue_row in provenance_rows["clues"].items():
        clue = clue_by_id[clue_id]
        entry = entries_by_id[clue["entryId"]]
        required_provenance = {
            "clueVariantId", "sourceClueId", "entryId", "senseIds", "factIds", "sourceIds",
            "evidenceKind", "evidenceId", "evidenceRefs", "evidenceProvenance", "reviewerId",
            "reviewedAt", "semanticTruthStatus",
        }
        if set(clue_row) != required_provenance:
            _reject("manifest-clue-provenance-shape-invalid")
        if (
            clue_row.get("sourceClueId") != clue.get("sourceClueId")
            or clue_row.get("entryId") != entry["id"]
            or list(clue_row.get("senseIds", ())) != list(clue["support"]["senseIds"])
            or list(clue_row.get("factIds", ())) != list(clue["support"]["factIds"])
            or entry["senseId"] not in clue_row["senseIds"]
            or clue_row.get("semanticTruthStatus") != "not-established-by-grammar-validator"
        ):
            _reject("manifest-clue-provenance-link-invalid")
        if (
            not isinstance(clue_row.get("reviewerId"), str)
            or not clue_row["reviewerId"].strip()
            or not isinstance(clue_row.get("reviewedAt"), str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", clue_row["reviewedAt"])
            or not isinstance(clue_row.get("evidenceRefs"), (list, tuple))
            or not clue_row["evidenceRefs"]
            or len(clue_row["evidenceRefs"]) != len(set(clue_row["evidenceRefs"]))
        ):
            _reject("manifest-clue-review-provenance-invalid")
        _validate_source_references(clue_row.get("sourceIds"), source_by_id)
        _validate_evidence_provenance(clue_row.get("evidenceProvenance"), clue_row["sourceIds"], source_by_id)
        if clue_row.get("evidenceKind") == "sense":
            if clue_row.get("evidenceId") not in clue_row["senseIds"]:
                _reject("manifest-clue-sense-evidence-invalid")
            linked_evidence = provenance_rows["senses"].get(clue_row["evidenceId"])
        elif clue_row.get("evidenceKind") == "fact":
            if clue_row.get("evidenceId") not in clue_row["factIds"]:
                _reject("manifest-clue-fact-evidence-invalid")
            linked_evidence = provenance_rows["facts"].get(clue_row["evidenceId"])
            if not linked_evidence or linked_evidence.get("lexemeId") != entry["lexemeId"]:
                _reject("manifest-clue-fact-lexeme-mismatch")
        else:
            _reject("manifest-clue-evidence-kind-invalid")
        if not linked_evidence or linked_evidence.get("evidenceProvenance") != clue_row.get("evidenceProvenance"):
            _reject("manifest-evidence-provenance-mismatch")
        if any(source_id not in clue_row["sourceIds"] for source_id in linked_evidence["sourceIds"]):
            _reject("manifest-clue-source-evidence-incomplete")

    for entry in entries_by_id.values():
        lexeme_record = provenance_rows["lexemes"].get(entry["lexemeId"])
        sense_record = provenance_rows["senses"].get(entry["senseId"])
        if not lexeme_record or not sense_record or sense_record["lexemeId"] != entry["lexemeId"]:
            _reject("manifest-entry-lexeme-sense-link-invalid")
        linked_clue = next(clue for clue in clues if clue["entryId"] == entry["id"])
        clue_provenance = provenance_rows["clues"][linked_clue["clueVariantId"]]
        if entry["senseId"] not in clue_provenance["senseIds"]:
            _reject("manifest-entry-clue-sense-link-invalid")

    crossing = _mapping(manifest.get("crossingSupport"), "manifest-crossing-support-invalid")
    if set(crossing) != {"version", "edges", "minimumScore", "meanScore", "uncertainty"}:
        _reject("manifest-crossing-support-shape-invalid")
    uncertainty = _mapping(crossing.get("uncertainty"), "manifest-crossing-uncertainty-invalid")
    if set(uncertainty) != {"level", "notes"} or uncertainty.get("level") not in {"low", "medium", "high", "unknown"}:
        _reject("manifest-crossing-uncertainty-invalid")
    if not isinstance(crossing.get("version"), str) or not crossing["version"].strip():
        _reject("manifest-crossing-version-invalid")
    edges = crossing.get("edges")
    if not isinstance(edges, (list, tuple)):
        _reject("manifest-crossing-edges-invalid")
    expected_open = {cell["id"] for cell in cells if not cell["block"]}
    seen_crossings: set[str] = set()
    scores: list[float] = []
    for raw_edge in edges:
        edge = _mapping(raw_edge, "manifest-crossing-edge-invalid")
        if set(edge) != {"acrossEntryId", "downEntryId", "cellId", "score", "confidence"}:
            _reject("manifest-crossing-edge-shape-invalid")
        across = entries_by_id.get(edge.get("acrossEntryId"))
        down = entries_by_id.get(edge.get("downEntryId"))
        score, confidence, cell_id = edge.get("score"), edge.get("confidence"), edge.get("cellId")
        if (
            across is None or across.get("direction") != "across"
            or down is None or down.get("direction") != "down"
            or cell_id not in expected_open or cell_id in seen_crossings
            or cell_id not in across.get("cellIds", ()) or cell_id not in down.get("cellIds", ())
            or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1
            or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1
        ):
            _reject("manifest-crossing-edge-invalid")
        seen_crossings.add(cell_id)
        scores.append(float(score))
    if seen_crossings != expected_open or not scores:
        _reject("manifest-crossing-coverage-invalid")
    if abs(float(crossing.get("minimumScore", -1)) - min(scores)) > 1e-9 or abs(float(crossing.get("meanScore", -1)) - (sum(scores) / len(scores))) > 1e-9:
        _reject("manifest-crossing-aggregate-invalid")
    if crossing["version"] == "structural-letter-agreement-v1" and (
        uncertainty.get("level") != "unknown"
        or any(edge["score"] != 0 or edge["confidence"] != 0 for edge in edges)
    ):
        _reject("manifest-structural-crossings-cannot-claim-player-support")

    receipt = _mapping(manifest.get("receipt"), "manifest-receipt-invalid")
    if set(receipt) != {"constructionSeed", "recipe", "runtime", "validators", "generatedAt", "profileProjection"}:
        _reject("manifest-receipt-shape-invalid")
    if receipt.get("constructionSeed") != manifest.get("seed"):
        _reject("manifest-construction-seed-mismatch")
    if not _is_iso_date_time(receipt.get("generatedAt")):
        _reject("manifest-generated-at-invalid")
    recipe = _mapping(receipt.get("recipe"), "manifest-recipe-invalid")
    if (
        set(recipe) != {"id", "version", "weekday"}
        or not isinstance(recipe.get("id"), str)
        or not recipe["id"].strip()
        or not isinstance(recipe.get("version"), str)
        or not recipe["version"].strip()
        or not isinstance(recipe.get("weekday"), str)
        or recipe["weekday"] not in _WEEKDAYS
    ):
        _reject("manifest-recipe-shape-invalid")
    runtime = _mapping(receipt.get("runtime"), "manifest-runtime-invalid")
    if (
        set(runtime) != {"id", "version", "artifactDigest"}
        or not isinstance(runtime.get("id"), str)
        or not runtime["id"].strip()
        or not isinstance(runtime.get("version"), str)
        or not runtime["version"].strip()
        or not isinstance(runtime.get("artifactDigest"), str)
        or not _RAW_DIGEST.fullmatch(runtime["artifactDigest"])
    ):
        _reject("manifest-runtime-shape-invalid")
    validators = receipt.get("validators")
    if not isinstance(validators, (list, tuple)) or not validators:
        _reject("manifest-validator-versions-required")
    validator_ids: set[str] = set()
    for raw_validator in validators:
        validator = _mapping(raw_validator, "manifest-validator-version-invalid")
        if (
            set(validator) != {"id", "version"}
            or not isinstance(validator.get("id"), str)
            or not validator["id"].strip()
            or not isinstance(validator.get("version"), str)
            or not validator["version"].strip()
            or validator["id"] in validator_ids
        ):
            _reject("manifest-validator-shape-invalid")
        validator_ids.add(validator["id"])
    profile_projection = _mapping(receipt.get("profileProjection"), "manifest-profile-projection-invalid")
    if (
        set(profile_projection) != {"revision", "digest"}
        or type(profile_projection.get("revision")) is not int
        or profile_projection["revision"] < 0
        or not isinstance(profile_projection.get("digest"), str)
        or not _RAW_DIGEST.fullmatch(profile_projection["digest"])
    ):
        _reject("manifest-profile-projection-invalid")
    quality = _mapping(manifest.get("quality"), "manifest-quality-invalid")
    if set(quality) != {"verdict", "reasons"} or not isinstance(quality.get("reasons"), (list, tuple)):
        _reject("manifest-quality-shape-invalid")
    if quality.get("verdict") == "accept":
        _reject("semantic-and-crossing-gates-not-proven")
    if quality.get("verdict") not in {"review", "reject"}:
        _reject("manifest-quality-verdict-invalid")
    integrity = _mapping(manifest.get("integrity"), "manifest-integrity-invalid")
    if integrity.get("algorithm") != "sha256" or integrity.get("canonicalization") != "json-canonical-v1" or set(integrity) != {"algorithm", "canonicalization", "value"}:
        _reject("manifest-integrity-algorithm-invalid")
    expected_digest = _digest({key: _plain(item) for key, item in manifest.items() if key != "integrity"})
    if integrity.get("value") != expected_digest:
        _reject("manifest-integrity-mismatch")
    return True
