"""Read-only, non-production report of machine-evidence prerequisites.

This diagnostic follows an exact V2 candidate digest through its stored row,
durable personalized V4 job, frozen inputs, worker result, and embedded review
manifest. Existing validators establish structure and byte linkage only. The
report deliberately leaves build identity, trajectory artifact binding,
source authenticity/editorial review, and real-player calibration unresolved.

There is no writer, persistence, receipt issuance, or publication decision in
this module.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from .database import db
from .future_puzzles import (
    FuturePuzzleV2CandidateRecord,
    PersonalizedV2CandidateRejected,
    validate_personalized_v2_review_candidate,
)
from .personalized_manifest import derive_xfill_slots
from . import future_grid_jobs as grid_jobs


_CANDIDATE_DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")
_MAX_CANDIDATE_ROWS_PER_DIGEST = 16
_UNRESOLVED_PREREQUISITES = (
    ("running-build-identity", "running-build-identity-not-resolved"),
    (
        "trajectory-artifact-binding",
        "trajectory-artifact-not-bound-to-machine-identity",
    ),
    (
        "source-authenticity-and-review",
        "source-authenticity-and-editorial-review-not-established",
    ),
    ("real-player-calibration", "real-player-calibration-not-available"),
)


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _report(
    candidate_digest: str | None, *, status: str, checks: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema": "machine-evidence-prerequisites-v1",
        "assessmentClass": "non-production-prerequisite-report",
        "candidateDigest": candidate_digest,
        "status": status,
        "checks": checks,
        "unresolvedPrerequisites": [
            {"id": key, "status": "unresolved", "reasonCode": reason}
            for key, reason in _UNRESOLVED_PREREQUISITES
        ],
        "claimBoundary": (
            "Integrity linkage is diagnostic only. This report is not a machine receipt, "
            "accepted document, completion estimate, or publication decision."
        ),
    }


def _blocked_report(
    candidate_digest: str | None,
    check_id: str,
    reason_code: str,
    *,
    detail: str | None = None,
    checks: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report_checks = dict(checks or {})
    failed: dict[str, str] = {"status": "blocked", "reasonCode": reason_code}
    if detail:
        failed["detail"] = detail
    report_checks[check_id] = failed
    return _report(
        candidate_digest, status="prerequisites-unresolved", checks=report_checks
    )


def _expected_job_result_receipt(frozen: dict[str, Any]) -> dict[str, Any]:
    return {
        key: frozen[key]
        for key in (
            "profileId",
            "profileUpdatedAt",
            "profileDigest",
            "startingDraftDigest",
            "weekdayDifficulty",
            "learningLanguage",
            "puzzleLanguage",
            "languageMapVersion",
            "epistemeRevision",
            "epistemeUpdatedAt",
            "epistemeDigest",
            "epistemeDigestAlgorithm",
            "packId",
            "packSha256",
            "sourcePins",
            "asOf",
        )
    } | {
        "briefVersion": grid_jobs.EXPECTED_BRIEF_VERSION,
        "briefCompilerVersion": frozen["briefCompilerVersion"],
        "compiledBriefDigest": frozen["compiledBriefDigest"],
    }


def _validate_result_and_manifest(
    *,
    result: Any,
    frozen: dict[str, Any],
    pack: Any,
    brief: dict[str, Any],
    candidate: dict[str, Any],
) -> None:
    """Raise on any inconsistency between the durable result and candidate."""
    if not isinstance(result, dict) or not isinstance(
        result.get("personalization"), dict
    ):
        raise ValueError("job-result-missing-personalization")
    personalization = result["personalization"]
    if (
        personalization.get("stage") != "answer-grid-draft"
        or personalization.get("playable") is not False
        or personalization.get("receipt") != _expected_job_result_receipt(frozen)
    ):
        raise ValueError("job-result-frozen-receipt-mismatch")

    raw_wordlist, answer_map, answers, selected, themes = grid_jobs._wordlist_for_brief(
        pack, brief, frozen["puzzleLanguage"]
    )
    wordlist_sha256 = grid_jobs.hashlib.sha256(raw_wordlist).hexdigest()
    expected_options = {**frozen["options"], "themes": themes}
    admitted_receipt = {
        "packId": pack.pack_id,
        "packSha256": pack.pack_sha256,
        "sha256": wordlist_sha256,
    }
    expected_links = grid_jobs._validate_personalized_runtime_result(
        result,
        expected_options,
        admitted_receipt,
        answer_map,
    )
    if personalization.get("entrySourceLinks") != expected_links:
        raise ValueError("job-result-entry-source-links-mismatch")
    expected_wordlist_receipt = {
        "sha256": wordlist_sha256,
        "answerCount": len(answers),
        "selectedAnswerCount": len(selected),
        "selectedAnswers": selected,
        "themeAnswers": themes,
    }
    if personalization.get("wordlistReceipt") != expected_wordlist_receipt:
        raise ValueError("job-result-wordlist-receipt-mismatch")

    envelope = personalization.get("manifestCandidate")
    if (
        not isinstance(envelope, dict)
        or envelope.get("status") != "review"
        or envelope.get("playable") is not False
        or envelope.get("manifest") != candidate
    ):
        raise ValueError("job-result-candidate-link-mismatch")

    manifest = candidate
    manifest_rows = [
        "".join(
            "#" if cell["block"] else cell["token"]
            for cell in manifest["cells"][row * 15 : (row + 1) * 15]
        )
        for row in range(15)
    ]
    if manifest_rows != result["grid"].get("fill"):
        raise ValueError("candidate-grid-result-mismatch")
    template = result["grid"].get("template")
    if (
        not isinstance(template, list)
        or len(template) != 15
        or any(
            not isinstance(row, str)
            or len(row) != 15
            or any(token not in ".ABCDEFGHIJKLMNOPQRSTUVWXYZ#" for token in row)
            for row in template
        )
        or any(
            (template[row][column] == "#")
            != (manifest_rows[row][column] == "#")
            for row in range(15)
            for column in range(15)
        )
    ):
        raise ValueError("candidate-template-geometry-mismatch")
    expected_candidate_id = (
        "personalized-"
        + grid_jobs.hashlib.sha256(
            grid_jobs._canonical(
                {
                    "pack": pack.pack_sha256,
                    "seed": frozen["seed"],
                    "fill": result["grid"]["fill"],
                }
            ).encode("utf-8")
        ).hexdigest()[:32]
    )
    if manifest.get("id") != expected_candidate_id:
        raise ValueError("candidate-construction-identity-mismatch")

    slots = derive_xfill_slots(manifest_rows)
    slot_answers = {(slot.number, slot.direction): slot.answer for slot in slots}
    manifest_answers = {
        (entry.get("number"), entry.get("direction")): entry.get("answer")
        for entry in manifest.get("entries", [])
        if isinstance(entry, dict)
    }
    result_answers = {
        (entry.get("num"), "across" if entry.get("dir") == "A" else "down"): entry.get(
            "answer"
        )
        for entry in result["grid"].get("entries", [])
        if isinstance(entry, dict)
    }
    if slot_answers != manifest_answers or slot_answers != result_answers:
        raise ValueError("candidate-entry-result-mismatch")

    receipt = manifest["receipt"]
    runtime = receipt["runtime"]
    projection = receipt["profileProjection"]
    recipe = receipt["recipe"]
    if (
        receipt.get("constructionSeed") != str(frozen["seed"])
        or projection.get("revision") != frozen["epistemeRevision"]
        or projection.get("digest") != frozen["epistemeDigest"]
        or recipe.get("id") != frozen["recipe"]
        or recipe.get("weekday") != str(frozen["weekdayDifficulty"]).title()
        or runtime.get("artifactDigest")
        != result["sourceDigest"].removeprefix("sha256:")
    ):
        raise ValueError("candidate-frozen-result-receipt-mismatch")


def _validate_private_selection(
    *, sidecar: Any, job: Any, candidate: dict[str, Any], brief: dict[str, Any]
) -> dict[str, int]:
    """Verify the private row's redacted linkage without returning its IDs."""
    if sidecar is None:
        raise ValueError("private-selection-sidecar-missing")
    if sidecar.job_id != job.id or sidecar.profile_id != job.profile_id:
        raise ValueError("private-selection-sidecar-owner-mismatch")
    selection = sidecar.selection_json
    if not isinstance(selection, list):
        raise ValueError("private-selection-sidecar-shape-invalid")

    evidence_by_candidate = {
        row["candidateId"]: list(row["evidenceIds"]) for row in brief["selectionLog"]
    }
    entries_by_id = {entry["id"]: entry for entry in candidate["entries"]}
    clues_by_entry = {clue["entryId"]: clue for clue in candidate["clues"]}
    expected = {}
    for entry_id, entry in entries_by_id.items():
        clue = clues_by_entry.get(entry_id)
        if clue is None:
            raise ValueError("private-selection-candidate-clue-missing")
        fact_ids = clue["support"]["factIds"]
        if not isinstance(fact_ids, list) or len(fact_ids) > 1:
            raise ValueError("private-selection-candidate-fact-ambiguous")
        candidate_id = entry["lexemeId"]
        profile_evidence_ids = evidence_by_candidate.get(candidate_id)
        if profile_evidence_ids is None:
            raise ValueError("private-selection-profile-evidence-missing")
        expected[entry_id] = {
            "entryId": entry_id,
            "candidateId": candidate_id,
            "clueId": clue["sourceClueId"],
            "clueVariantId": clue["clueVariantId"],
            "senseId": entry["senseId"],
            "factId": fact_ids[0] if fact_ids else None,
            "profileEvidenceIds": profile_evidence_ids,
        }
    actual_by_entry = {}
    for item in selection:
        if not isinstance(item, dict) or set(item) != {
            "entryId",
            "candidateId",
            "clueId",
            "clueVariantId",
            "senseId",
            "factId",
            "profileEvidenceIds",
        }:
            raise ValueError("private-selection-sidecar-shape-invalid")
        entry_id = item["entryId"]
        if not isinstance(entry_id, str) or entry_id in actual_by_entry:
            raise ValueError("private-selection-sidecar-entry-conflict")
        actual_by_entry[entry_id] = item
    if set(actual_by_entry) != set(expected) or any(
        actual_by_entry[entry_id] != row for entry_id, row in expected.items()
    ):
        raise ValueError("private-selection-sidecar-candidate-link-mismatch")
    return {
        "entryCount": len(expected),
        "profileEvidenceReferenceCount": sum(
            len(row["profileEvidenceIds"]) for row in expected.values()
        ),
    }


def build_machine_evidence_prerequisite_report(
    candidate_digest: object,
) -> dict[str, Any]:
    """Inspect a stored candidate and linked V4 job without changing the DB.

    The argument must be the exact canonical ``sha256:<64 lowercase hex>``
    value and an active Flask application context. SQLAlchemy autoflush is
    disabled for the read scope so invoking this diagnostic cannot flush
    pending ORM changes as a side effect.
    """
    match = (
        _CANDIDATE_DIGEST.fullmatch(candidate_digest)
        if isinstance(candidate_digest, str)
        else None
    )
    if match is None:
        return _blocked_report(None, "candidate", "candidate-digest-invalid")
    exact_digest = candidate_digest
    raw_digest = match.group(1)

    try:
        with db.session.no_autoflush:
            rows = (
                db.session.query(FuturePuzzleV2CandidateRecord)
                .filter(FuturePuzzleV2CandidateRecord.candidate_hash == raw_digest)
                .limit(_MAX_CANDIDATE_ROWS_PER_DIGEST + 1)
                .all()
            )
    except SQLAlchemyError:
        return _blocked_report(exact_digest, "candidate", "candidate-store-unavailable")
    if not rows:
        return _blocked_report(exact_digest, "candidate", "candidate-not-found")
    if len(rows) > _MAX_CANDIDATE_ROWS_PER_DIGEST:
        return _blocked_report(exact_digest, "candidate", "candidate-identity-conflict")

    validated: list[tuple[Any, dict[str, Any]]] = []
    try:
        for row in rows:
            manifest = validate_personalized_v2_review_candidate(row.manifest_json)
            if (
                row.candidate_hash != raw_digest
                or manifest["integrity"]["value"] != exact_digest
                or row.candidate_id != manifest["id"]
            ):
                raise PersonalizedV2CandidateRejected(
                    "candidate-storage-digest-mismatch"
                )
            validated.append((row, manifest))
    except (
        PersonalizedV2CandidateRejected,
        TypeError,
        ValueError,
        KeyError,
        RecursionError,
        UnicodeError,
    ):
        return _blocked_report(exact_digest, "candidate", "candidate-integrity-invalid")

    canonical_candidate = _canonical(validated[0][1])
    if any(
        _canonical(manifest) != canonical_candidate for _, manifest in validated[1:]
    ):
        return _blocked_report(exact_digest, "candidate", "candidate-identity-conflict")
    row_profiles = {row.profile_id for row, _ in validated}
    row_jobs = {row.job_id for row, _ in validated}
    if len(row_profiles) != 1 or len(row_jobs) != 1:
        return _blocked_report(
            exact_digest, "candidateJobLink", "candidate-job-link-conflict"
        )
    candidate_row, candidate = validated[0]
    checks: dict[str, Any] = {
        "candidate": {
            "status": "validated",
            "reasonCode": "candidate-integrity-validated",
        }
    }

    try:
        with db.session.no_autoflush:
            job = db.session.get(grid_jobs.FutureGridDraftJob, candidate_row.job_id)
    except SQLAlchemyError:
        return _blocked_report(
            exact_digest,
            "durableJob",
            "job-store-unavailable",
            checks=checks,
        )
    if job is None:
        return _blocked_report(
            exact_digest, "durableJob", "candidate-job-not-found", checks=checks
        )
    if job.profile_id != candidate_row.profile_id:
        return _blocked_report(
            exact_digest,
            "candidateJobLink",
            "candidate-job-profile-mismatch",
            checks=checks,
        )
    if job.state != "ready":
        return _blocked_report(
            exact_digest, "durableJob", "job-not-ready", checks=checks
        )
    if not isinstance(job.request_json, dict) or job.request_json.get("version") != 4:
        return _blocked_report(
            exact_digest, "frozenInputs", "frozen-v4-inputs-required", checks=checks
        )
    frozen = job.request_json
    if frozen.get("profileId") != job.profile_id:
        return _blocked_report(
            exact_digest, "frozenInputs", "frozen-profile-link-mismatch", checks=checks
        )
    try:
        expected_request_digest = grid_jobs._digest(
            {
                "profileId": job.profile_id,
                "seed": frozen.get("seed"),
                "mode": "personalized",
            }
        )
    except (TypeError, ValueError, RecursionError, UnicodeError):
        return _blocked_report(
            exact_digest, "frozenInputs", "frozen-job-request-invalid", checks=checks
        )
    if job.request_digest != expected_request_digest:
        return _blocked_report(
            exact_digest, "frozenInputs", "job-request-digest-mismatch", checks=checks
        )

    try:
        pack = grid_jobs._load_pinned_pack()
        as_of = grid_jobs._verify_personalized_snapshot(frozen, job.profile_id, pack)
        brief = grid_jobs._frozen_compiled_brief(frozen, job.profile_id, pack, as_of)
    except Exception:
        return _blocked_report(
            exact_digest,
            "frozenInputs",
            "frozen-v4-input-validation-failed",
            checks=checks,
        )
    checks["candidateJobLink"] = {
        "status": "validated",
        "reasonCode": "candidate-job-profile-link-validated",
    }
    checks["frozenInputs"] = {
        "status": "validated",
        "reasonCode": "frozen-v4-inputs-validated",
    }
    checks["durableJob"] = {
        "status": "validated",
        "reasonCode": "ready-job-record-resolved",
    }

    try:
        _validate_result_and_manifest(
            result=job.result_json,
            frozen=frozen,
            pack=pack,
            brief=brief,
            candidate=candidate,
        )
    except (
        TypeError,
        ValueError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
        UnicodeError,
    ):
        return _blocked_report(
            exact_digest,
            "resultAndManifest",
            "frozen-result-manifest-link-invalid",
            checks=checks,
        )

    checks["resultAndManifest"] = {
        "status": "validated",
        "reasonCode": "result-and-manifest-linkage-validated",
    }
    try:
        with db.session.no_autoflush:
            sidecar = db.session.get(grid_jobs.FutureGridDraftPrivateSelection, job.id)
        sidecar_summary = _validate_private_selection(
            sidecar=sidecar,
            job=job,
            candidate=candidate,
            brief=brief,
        )
    except (
        SQLAlchemyError,
        TypeError,
        ValueError,
        KeyError,
        AttributeError,
        RecursionError,
        UnicodeError,
    ):
        return _blocked_report(
            exact_digest,
            "privateSelection",
            "private-selection-linkage-invalid",
            checks=checks,
        )
    checks["privateSelection"] = {
        "status": "validated",
        "reasonCode": "private-selection-linkage-validated",
        **sidecar_summary,
    }
    return _report(exact_digest, status="prerequisites-unresolved", checks=checks)
