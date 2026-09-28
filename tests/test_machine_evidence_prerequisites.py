"""Synthetic-only tests for the read-only machine-prerequisite report.

Fixtures intentionally use fabricated vocabulary, clues, source labels, and
runtime digests. They exercise integrity linkage, not production provenance.
"""

from __future__ import annotations

from copy import deepcopy
import json
from uuid import uuid4

import pytest
from sqlalchemy import event, text

from tests.test_api_isolated import api, no_network  # noqa: F401
from tests.test_future_grid_jobs import (
    _add_episteme_control,
    _complete_synthetic_review_pack,
    _complete_synthetic_runtime_result,
    _create_profile,
    _job_body,
    _personalized_profile_payload,
)
from src.crossword.future_grid_jobs import (
    FutureGridDraftJob,
    FutureGridDraftPrivateSelection,
    process_next_grid_draft,
)
from src.crossword.future_puzzles import FuturePuzzleV2CandidateRecord
from src.crossword.machine_evidence_prerequisites import (
    build_machine_evidence_prerequisite_report,
)
import src.crossword.future_grid_jobs as grid_jobs


def _ready_candidate(api, monkeypatch):
    """Create a complete ready job/candidate using synthetic CI-only data."""
    pack = _complete_synthetic_review_pack()
    monkeypatch.setattr(grid_jobs, "_load_pinned_pack", lambda: pack)
    client = api.app.test_client()
    profile = _personalized_profile_payload()
    _create_profile(client, profile)
    _add_episteme_control(client, profile["id"], "topic:synthetic", action="seek")
    created = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(profile["id"], seed=873),
    )
    assert created.status_code == 202, created.json

    def runtime(**kwargs):
        return _complete_synthetic_runtime_result(
            kwargs["seed"], kwargs["options"], kwargs["admitted_wordlist"]
        )

    assert process_next_grid_draft(api.app, generator=runtime)
    with api.app.app_context():
        job = api.db.session.get(FutureGridDraftJob, created.json["id"])
        assert job is not None and job.state == "ready"
        # The synthetic construction helper omits xfill's template. Add the
        # corresponding legitimate block mask to the persisted result so the
        # report exercises the same result/candidate geometry relationship.
        result = deepcopy(job.result_json)
        result["grid"]["template"] = [
            "".join("#" if token == "#" else "." for token in row)
            for row in result["grid"]["fill"]
        ]
        job.result_json = result
        api.db.session.commit()
        row = (
            api.db.session.query(FuturePuzzleV2CandidateRecord)
            .filter_by(job_id=job.id)
            .one()
        )
        return row.manifest_json["integrity"]["value"], row.profile_id, row.job_id


def _reason(report, check):
    return report["checks"][check]["reasonCode"]


def _assess(api, digest):
    with api.app.app_context():
        return build_machine_evidence_prerequisite_report(digest)


def test_invalid_and_missing_candidate_digest_fail_closed_without_writes(api):
    assert _reason(_assess(api, "sha256:" + "A" * 64), "candidate") == (
        "candidate-digest-invalid"
    )
    missing = _assess(api, "sha256:" + "0" * 64)
    assert _reason(missing, "candidate") == "candidate-not-found"
    assert len(missing["unresolvedPrerequisites"]) == 4


def test_candidate_with_missing_job_is_reported_as_unresolved(api, monkeypatch):
    digest, _profile_id, _job_id = _ready_candidate(api, monkeypatch)
    with api.app.app_context():
        candidate_hash = digest.removeprefix("sha256:")
        row = (
            api.db.session.query(FuturePuzzleV2CandidateRecord)
            .filter_by(candidate_hash=candidate_hash)
            .one()
        )
        row.job_id = str(uuid4())
        api.db.session.commit()

    report = _assess(api, digest)
    assert _reason(report, "durableJob") == "candidate-job-not-found"
    assert report["status"] == "prerequisites-unresolved"


def test_tampered_stored_candidate_is_rejected(api, monkeypatch):
    digest, _profile_id, _job_id = _ready_candidate(api, monkeypatch)
    with api.app.app_context():
        row = (
            api.db.session.query(FuturePuzzleV2CandidateRecord)
            .filter_by(candidate_hash=digest.removeprefix("sha256:"))
            .one()
        )
        manifest = deepcopy(row.manifest_json)
        manifest["title"] = "Tampered synthetic title"
        row.manifest_json = manifest
        api.db.session.commit()

    report = _assess(api, digest)
    assert _reason(report, "candidate") == "candidate-integrity-invalid"


def test_candidate_job_profile_link_mismatch_is_blocked(api, monkeypatch):
    digest, _profile_id, job_id = _ready_candidate(api, monkeypatch)
    with api.app.app_context():
        job = api.db.session.get(FutureGridDraftJob, job_id)
        job.profile_id = str(uuid4())
        api.db.session.commit()

    report = _assess(api, digest)
    assert _reason(report, "candidateJobLink") == "candidate-job-profile-mismatch"


def test_conflicting_profile_scoped_candidate_rows_do_not_pick_an_arbitrary_job(
    api, monkeypatch
):
    digest, _profile_id, job_id = _ready_candidate(api, monkeypatch)
    with api.app.app_context():
        original = (
            api.db.session.query(FuturePuzzleV2CandidateRecord)
            .filter_by(candidate_hash=digest.removeprefix("sha256:"))
            .one()
        )
        api.db.session.add(
            FuturePuzzleV2CandidateRecord(
                profile_id=str(uuid4()),
                candidate_hash=original.candidate_hash,
                candidate_id=original.candidate_id,
                job_id=job_id,
                manifest_json=deepcopy(original.manifest_json),
                created_at=original.created_at,
            )
        )
        api.db.session.commit()

    report = _assess(api, digest)
    assert _reason(report, "candidateJobLink") == "candidate-job-link-conflict"


def test_frozen_v4_input_tampering_is_detected(api, monkeypatch):
    digest, _profile_id, job_id = _ready_candidate(api, monkeypatch)
    with api.app.app_context():
        job = api.db.session.get(FutureGridDraftJob, job_id)
        request_json = deepcopy(job.request_json)
        request_json["compiledBriefDigest"] = "0" * 64
        job.request_json = request_json
        api.db.session.commit()

    report = _assess(api, digest)
    assert _reason(report, "frozenInputs") == "frozen-v4-input-validation-failed"
    assert "resultAndManifest" not in report["checks"]


def test_result_receipt_tampering_is_detected(api, monkeypatch):
    digest, _profile_id, job_id = _ready_candidate(api, monkeypatch)
    with api.app.app_context():
        job = api.db.session.get(FutureGridDraftJob, job_id)
        result = deepcopy(job.result_json)
        result["personalization"]["receipt"]["epistemeRevision"] += 1
        job.result_json = result
        api.db.session.commit()

    report = _assess(api, digest)
    assert _reason(report, "resultAndManifest") == "frozen-result-manifest-link-invalid"


def test_result_template_block_mask_must_match_candidate_geometry(api, monkeypatch):
    digest, _profile_id, job_id = _ready_candidate(api, monkeypatch)
    with api.app.app_context():
        job = api.db.session.get(FutureGridDraftJob, job_id)
        result = deepcopy(job.result_json)
        template = result["grid"]["template"]
        block = next(
            (row, column)
            for row, line in enumerate(template)
            for column, token in enumerate(line)
            if token == "#"
        )
        row, column = block
        template[row] = template[row][:column] + "." + template[row][column + 1 :]
        job.result_json = result
        api.db.session.commit()

    report = _assess(api, digest)
    assert _reason(report, "resultAndManifest") == "frozen-result-manifest-link-invalid"


def test_private_selection_sidecar_mismatch_is_redacted_and_blocked(api, monkeypatch):
    digest, _profile_id, job_id = _ready_candidate(api, monkeypatch)
    with api.app.app_context():
        sidecar = api.db.session.get(FutureGridDraftPrivateSelection, job_id)
        selection = deepcopy(sidecar.selection_json)
        selection[0]["candidateId"] = "tampered-private-value"
        sidecar.selection_json = selection
        api.db.session.commit()

    report = _assess(api, digest)
    assert _reason(report, "privateSelection") == "private-selection-linkage-invalid"
    assert "tampered-private-value" not in json.dumps(report)


def test_valid_synthetic_chain_reports_integrity_and_keeps_real_evidence_unresolved(
    api, monkeypatch
):
    digest, _profile_id, _job_id = _ready_candidate(api, monkeypatch)
    with api.app.app_context():
        before_candidates = [
            (
                row.profile_id,
                row.candidate_hash,
                row.candidate_id,
                row.job_id,
                json.dumps(row.manifest_json, sort_keys=True),
            )
            for row in api.db.session.query(FuturePuzzleV2CandidateRecord).order_by(
                FuturePuzzleV2CandidateRecord.profile_id
            )
        ]
        before_jobs = [
            (
                row.id,
                row.profile_id,
                row.state,
                json.dumps(row.request_json, sort_keys=True),
                json.dumps(row.result_json, sort_keys=True),
            )
            for row in api.db.session.query(FutureGridDraftJob).order_by(
                FutureGridDraftJob.id
            )
        ]
        before_sidecars = [
            (row.job_id, row.profile_id, json.dumps(row.selection_json, sort_keys=True))
            for row in api.db.session.query(FutureGridDraftPrivateSelection).order_by(
                FutureGridDraftPrivateSelection.job_id
            )
        ]
        private_evidence_ids = {
            evidence_id
            for row in api.db.session.query(FutureGridDraftPrivateSelection).all()
            for item in row.selection_json
            for evidence_id in item["profileEvidenceIds"]
        }
        dml = []

        def record_statement(_conn, _cursor, statement, _parameters, _context, _many):
            if statement.lstrip().split(None, 1)[0].upper() in {
                "INSERT",
                "UPDATE",
                "DELETE",
                "REPLACE",
            }:
                dml.append(statement)

        event.listen(api.db.engine, "before_cursor_execute", record_statement)
        try:
            report = build_machine_evidence_prerequisite_report(digest)
        finally:
            event.remove(api.db.engine, "before_cursor_execute", record_statement)

        after_candidates = [
            (
                row.profile_id,
                row.candidate_hash,
                row.candidate_id,
                row.job_id,
                json.dumps(row.manifest_json, sort_keys=True),
            )
            for row in api.db.session.query(FuturePuzzleV2CandidateRecord).order_by(
                FuturePuzzleV2CandidateRecord.profile_id
            )
        ]
        after_jobs = [
            (
                row.id,
                row.profile_id,
                row.state,
                json.dumps(row.request_json, sort_keys=True),
                json.dumps(row.result_json, sort_keys=True),
            )
            for row in api.db.session.query(FutureGridDraftJob).order_by(
                FutureGridDraftJob.id
            )
        ]
        after_sidecars = [
            (row.job_id, row.profile_id, json.dumps(row.selection_json, sort_keys=True))
            for row in api.db.session.query(FutureGridDraftPrivateSelection).order_by(
                FutureGridDraftPrivateSelection.job_id
            )
        ]
        table_counts = api.db.session.execute(
            text(
                "SELECT "
                "(SELECT count(*) FROM future_puzzle_v2_candidates), "
                "(SELECT count(*) FROM future_grid_draft_jobs), "
                "(SELECT count(*) FROM future_grid_draft_private_selections)"
            )
        ).one()

    assert report["assessmentClass"] == "non-production-prerequisite-report"
    assert report["status"] == "prerequisites-unresolved"
    assert all(check["status"] == "validated" for check in report["checks"].values()), (
        json.dumps(report, indent=2)
    )
    assert report["checks"]["privateSelection"]["entryCount"] == 78
    assert [item["id"] for item in report["unresolvedPrerequisites"]] == [
        "running-build-identity",
        "trajectory-artifact-binding",
        "source-authenticity-and-review",
        "real-player-calibration",
    ]
    assert all(
        item["status"] == "unresolved" and item["reasonCode"]
        for item in report["unresolvedPrerequisites"]
    )
    forbidden_fields = {
        "machineReceipt",
        "completionProbability",
        "acceptedDocument",
        "publicationEligibility",
    }
    assert forbidden_fields.isdisjoint(report)
    report_json = json.dumps(report)
    assert "pass" not in report_json.lower()
    assert private_evidence_ids
    assert all(evidence_id not in report_json for evidence_id in private_evidence_ids)
    assert dml == []
    assert before_candidates == after_candidates
    assert before_jobs == after_jobs
    assert before_sidecars == after_sidecars
    assert tuple(table_counts) == (1, 1, 1)
