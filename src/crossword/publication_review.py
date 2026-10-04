"""Read-only host composition of the V2 publication gate and evidence store.

This service deliberately stops at ``evidence-unverified``. It does not decide
whether evidence is truthful, publish a puzzle, or change any registry state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import re
from typing import Literal

from .future_puzzles import validate_personalized_v2_review_candidate
from .publication_evidence import (
    MAX_PUBLICATION_REVIEW_PACKET_BYTES,
    PublicationEvidenceArtifact,
    _candidate_digest,
    _validated_candidate,
    resolve_publication_packet_evidence,
)
from .solve_replay import evaluate_puzzle_v2_publication_gate


_PACKET_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_GATE_VERSION = "puzzle-v2-publication-gate-v1"
_RESIDUAL_REASON = "reviewer-evidence-unverified"
_MAX_PACKET_JSON_NODES = 250_000
_MAX_PACKET_JSON_DEPTH = 64


class PublicationReviewRejected(ValueError):
    """The host could not safely evaluate this review packet."""


@dataclass(frozen=True, slots=True)
class PublicationReviewDiagnostic:
    """Immutable, redacted summary; never an eligibility or publication token."""

    status: Literal["blocked", "evidence-unverified"]
    gate_candidate_digest: str | None
    packet_digest: str | None
    reason_codes: tuple[str, ...]
    evidence_artifact_count: int
    authenticated_uploader_count: int
    declared_blind_reviewer_count: int
    human_attestation_expected_count: int
    human_attestation_verified_count: int

    def to_dict(self) -> dict[str, object]:
        """Return a detached JSON-ready copy without artifact or identity data."""
        return asdict(self)


def review_publication_packet(packet: object) -> PublicationReviewDiagnostic:
    """Evaluate one packet against its exact stored candidate and evidence.

    The candidate identity is derived only from ``packet.candidateDigest``.
    The same packet object and digest are passed first to the shared TypeScript
    gate and then to the immutable evidence resolver. The resolver is reached
    only for the gate's sole residual ``reviewer-evidence-unverified`` reason.
    """
    if type(packet) is not dict:
        raise PublicationReviewRejected("packet-invalid")
    packet = _snapshot_packet(packet)
    try:
        candidate_digest, _ = _candidate_digest(
            packet.get("candidateDigest")
        )
        stored_candidate = _validated_candidate(candidate_digest)
        if stored_candidate is None:
            raise PublicationReviewRejected("candidate-not-found")
        candidate = validate_personalized_v2_review_candidate(
            stored_candidate.manifest_json
        )
    except PublicationReviewRejected:
        raise
    except Exception:
        raise PublicationReviewRejected("candidate-integrity-invalid") from None

    if candidate.get("integrity", {}).get("value") != candidate_digest:
        raise PublicationReviewRejected("candidate-digest-mismatch")

    try:
        evaluation = evaluate_puzzle_v2_publication_gate(candidate, packet)
    except Exception:
        # Keep bridge/runtime failures closed and redact implementation details.
        raise PublicationReviewRejected("publication-gate-unavailable") from None

    _validate_gate_evaluation(evaluation, candidate_digest)
    if evaluation["status"] == "blocked":
        return PublicationReviewDiagnostic(
            status="blocked",
            gate_candidate_digest=candidate_digest,
            # A blocked gate may have rejected this very digest. Do not echo
            # a syntactically plausible but unverified client claim.
            packet_digest=None,
            reason_codes=tuple(reason["code"] for reason in evaluation["reasons"]),
            evidence_artifact_count=0,
            authenticated_uploader_count=0,
            declared_blind_reviewer_count=0,
            human_attestation_expected_count=0,
            human_attestation_verified_count=0,
        )

    # A bridge result with anything except this exact sole residual state must
    # never cause evidence resolution or be represented as review progress.
    if len(evaluation["reasons"]) != 1 or evaluation["reasons"][0]["code"] != _RESIDUAL_REASON:
        raise PublicationReviewRejected("publication-gate-residual-invalid")
    packet_digest = _packet_digest_for_diagnostic(packet)
    if packet_digest is None:
        raise PublicationReviewRejected("packet-digest-invalid")

    try:
        resolved = resolve_publication_packet_evidence(packet, candidate_digest)
    except Exception:
        raise PublicationReviewRejected("evidence-resolution-failed") from None

    if type(resolved) is not tuple or any(
        type(record) is not PublicationEvidenceArtifact for record in resolved
    ):
        raise PublicationReviewRejected("evidence-resolution-output-invalid")
    if any(record.candidate_digest != candidate_digest for record in resolved):
        raise PublicationReviewRejected("evidence-candidate-mismatch")

    reviewer_count = len({record.reviewer_id for record in resolved})
    weekday_review = packet.get("weekdayReview")
    blind_classifications = (
        weekday_review.get("blindClassifications")
        if type(weekday_review) is dict
        else None
    )
    # The TypeScript gate guarantees at least two unique declared reviewer IDs
    # before this point. This count does not prove independent human identities
    # or a blinding process.
    declared_blind_reviewer_count = len(
        {
            item["reviewerId"]
            for item in blind_classifications
            if type(item) is dict and isinstance(item.get("reviewerId"), str)
        }
    ) if type(blind_classifications) is list else 0
    if declared_blind_reviewer_count < 2:
        raise PublicationReviewRejected("blind-reviewer-count-invalid")

    # Import locally to avoid a module cycle: receipt creation itself first
    # calls this read-only service, while this composition verifies any receipts
    # already present for the exact packet. Missing human receipts are progress
    # information only; they never change the structural gate's residual state.
    try:
        from .publication_attestation import (
            PublicationAttestationCoverage,
            PublicationAttestationRejected,
            resolve_publication_packet_attestations,
        )

        coverage = resolve_publication_packet_attestations(
            packet, candidate_digest, packet_digest
        )
    except PublicationAttestationRejected:
        raise PublicationReviewRejected("attestation-resolution-failed") from None
    except Exception:
        raise PublicationReviewRejected("attestation-resolution-unavailable") from None

    if (
        type(coverage) is not PublicationAttestationCoverage
        or type(coverage.complete) is not bool
        or type(coverage.expected_claim_count) is not int
        or type(coverage.attested_claim_count) is not int
        or type(coverage.missing_claim_paths) is not tuple
        or coverage.expected_claim_count < 1
        or coverage.attested_claim_count < 0
        or coverage.attested_claim_count > coverage.expected_claim_count
        or coverage.complete != (coverage.attested_claim_count == coverage.expected_claim_count)
        or len(coverage.missing_claim_paths)
        != coverage.expected_claim_count - coverage.attested_claim_count
    ):
        raise PublicationReviewRejected("attestation-coverage-output-invalid")

    reason_codes = (_RESIDUAL_REASON,)
    if not coverage.complete:
        reason_codes += ("human-attestation-incomplete",)

    return PublicationReviewDiagnostic(
        status="evidence-unverified",
        gate_candidate_digest=candidate_digest,
        packet_digest=packet_digest,
        reason_codes=reason_codes,
        evidence_artifact_count=len(resolved),
        authenticated_uploader_count=reviewer_count,
        declared_blind_reviewer_count=declared_blind_reviewer_count,
        human_attestation_expected_count=coverage.expected_claim_count,
        human_attestation_verified_count=coverage.attested_claim_count,
    )


def _validate_gate_evaluation(value: object, expected_candidate_digest: str) -> None:
    if (
        type(value) is not dict
        or set(value) != {"gateVersion", "candidateDigest", "status", "reasons"}
        or value.get("gateVersion") != _GATE_VERSION
        or value.get("candidateDigest") != expected_candidate_digest
        or not isinstance(value.get("status"), str)
        or value.get("status") not in {"blocked", "evidence-unverified"}
        or type(value.get("reasons")) is not list
        or not value["reasons"]
        or any(
            type(reason) is not dict
            or set(reason) != {"code", "path", "message"}
            or any(not isinstance(reason.get(key), str) for key in ("code", "path", "message"))
            for reason in value["reasons"]
        )
    ):
        raise PublicationReviewRejected("publication-gate-output-invalid")
    if value["status"] == "evidence-unverified" and any(
        reason["code"] != _RESIDUAL_REASON for reason in value["reasons"]
    ):
        raise PublicationReviewRejected("publication-gate-residual-invalid")


def _packet_digest_for_diagnostic(packet: dict) -> str | None:
    value = packet.get("packetDigest")
    return value if isinstance(value, str) and _PACKET_DIGEST.fullmatch(value) else None


def _snapshot_packet(packet: dict) -> dict:
    """Freeze one bounded JSON snapshot for gate and resolver composition."""
    try:
        _measure_packet_json_size(packet)
        serialized = json.dumps(
            packet,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        if len(serialized.encode("utf-8")) > MAX_PUBLICATION_REVIEW_PACKET_BYTES:
            raise PublicationReviewRejected("packet-size-limit-exceeded")
        snapshot = json.loads(serialized)
    except PublicationReviewRejected:
        raise
    except (TypeError, ValueError, RecursionError, UnicodeError):
        raise PublicationReviewRejected("packet-invalid") from None
    if type(snapshot) is not dict:
        raise PublicationReviewRejected("packet-invalid")
    return snapshot


def _measure_packet_json_size(root: dict) -> int:
    """Preflight size/depth/shape without constructing a serialized copy."""
    size = 0
    nodes = 0
    active_containers: set[int] = set()
    tasks: list[tuple] = [("value", root, 0)]

    def add(amount: int) -> None:
        nonlocal size
        size += amount
        if size > MAX_PUBLICATION_REVIEW_PACKET_BYTES:
            raise PublicationReviewRejected("packet-size-limit-exceeded")

    def string_size(value: str) -> int:
        encoded_size = 2  # surrounding quotation marks
        for character in value:
            codepoint = ord(character)
            if character in {'"', "\\"}:
                encoded_size += 2
            elif codepoint < 0x20:
                encoded_size += 2 if character in "\b\f\n\r\t" else 6
            else:
                encoded_size += len(character.encode("utf-8"))
            if encoded_size > MAX_PUBLICATION_REVIEW_PACKET_BYTES:
                raise PublicationReviewRejected("packet-size-limit-exceeded")
        return encoded_size

    while tasks:
        task = tasks.pop()
        action, value, depth = task[:3]
        if action == "mapping":
            _action, iterator, depth, identity, first = task
            try:
                key, child = next(iterator)
            except StopIteration:
                active_containers.remove(identity)
                continue
            if type(key) is not str:
                raise PublicationReviewRejected("packet-invalid")
            nodes += 1
            if nodes > _MAX_PACKET_JSON_NODES:
                raise PublicationReviewRejected("packet-structure-limit-exceeded")
            add(string_size(key) + 1 + (0 if first else 1))
            tasks.append(("mapping", iterator, depth, identity, False))
            tasks.append(("value", child, depth + 1))
            continue
        if action == "sequence":
            _action, iterator, depth, identity, first = task
            try:
                child = next(iterator)
            except StopIteration:
                active_containers.remove(identity)
                continue
            tasks.append(("sequence", iterator, depth, identity, False))
            if not first:
                add(1)
            tasks.append(("value", child, depth + 1))
            continue

        nodes += 1
        if nodes > _MAX_PACKET_JSON_NODES or depth > _MAX_PACKET_JSON_DEPTH:
            raise PublicationReviewRejected("packet-structure-limit-exceeded")
        if type(value) is dict:
            identity = id(value)
            if identity in active_containers:
                raise PublicationReviewRejected("packet-invalid")
            active_containers.add(identity)
            add(2)
            tasks.append(("mapping", iter(value.items()), depth, identity, True))
        elif type(value) is list:
            if len(value) > MAX_PUBLICATION_REVIEW_PACKET_BYTES:
                raise PublicationReviewRejected("packet-size-limit-exceeded")
            identity = id(value)
            if identity in active_containers:
                raise PublicationReviewRejected("packet-invalid")
            active_containers.add(identity)
            add(2)
            tasks.append(("sequence", iter(value), depth, identity, True))
        elif type(value) is str:
            add(string_size(value))
        elif value is None:
            add(4)
        elif type(value) is bool:
            add(4 if value else 5)
        elif type(value) is int:
            # Avoid converting an enormous Python integer to a huge decimal
            # string merely to discover it cannot fit this packet budget.
            decimal_bytes_upper_bound = (
                value.bit_length() * 30103 // 100000
                + 1
                + int(value < 0)
            )
            if decimal_bytes_upper_bound > MAX_PUBLICATION_REVIEW_PACKET_BYTES:
                raise PublicationReviewRejected("packet-size-limit-exceeded")
            add(len(str(value)))
        elif type(value) is float and math.isfinite(value):
            add(len(repr(value)))
        else:
            raise PublicationReviewRejected("packet-invalid")

    return size
