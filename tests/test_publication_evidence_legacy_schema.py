"""Ensure startup adds evidence-claim tables without rewriting legacy bytes."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text


def _seed_pre_claim_database(path: Path, candidate_digest: str) -> tuple[str, bytes]:
    """Create the evidence table as it existed before claim-path assignments."""
    artifact_id = str(uuid4())
    body = b"legacy synthetic evidence bytes"
    digest = hashlib.sha256(body).hexdigest()
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE future_publication_evidence_v2 (
                artifact_id VARCHAR(36) NOT NULL PRIMARY KEY,
                sha256 VARCHAR(64) NOT NULL,
                kind VARCHAR(40) NOT NULL,
                candidate_digest VARCHAR(71) NOT NULL,
                media_type VARCHAR(129) NOT NULL,
                reviewer_id VARCHAR(128) NOT NULL,
                recorded_at VARCHAR(40) NOT NULL,
                artifact_bytes BLOB NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX ix_future_publication_evidence_v2_sha256 "
            "ON future_publication_evidence_v2 (sha256)"
        )
        connection.execute(
            "CREATE INDEX ix_future_publication_evidence_v2_candidate_digest "
            "ON future_publication_evidence_v2 (candidate_digest)"
        )
        connection.execute(
            """
            INSERT INTO future_publication_evidence_v2 (
                artifact_id, sha256, kind, candidate_digest, media_type,
                reviewer_id, recorded_at, artifact_bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                digest,
                "source-artifact",
                candidate_digest,
                "application/pdf",
                "legacy-reviewer",
                "2026-09-26T12:00:00.000+00:00",
                body,
            ),
        )
    return artifact_id, body


def _load_isolated_app():
    app_path = Path(__file__).resolve().parents[1] / "src/crossword/app.py"
    spec = importlib.util.spec_from_file_location(
        "src.crossword._legacy_evidence_schema_app", app_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.config.update(TESTING=True)
    return module


def test_startup_adds_claim_table_without_losing_legacy_evidence(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "pre-claim.sqlite"
    fixture_path = Path(__file__).parent / "fixtures/personalized-review-v2.json"
    manifest = json.loads(fixture_path.read_text())
    candidate_digest = manifest["integrity"]["value"]
    artifact_id, body = _seed_pre_claim_database(database_path, candidate_digest)
    monkeypatch.setenv("CROSSWORD_DATABASE_URI", f"sqlite:///{database_path}")

    api = _load_isolated_app()
    try:
        from src.crossword.future_puzzles import FuturePuzzleV2CandidateRecord
        from src.crossword.publication_evidence import (
            PublicationEvidenceArtifact,
            PublicationEvidenceArtifactClaim,
            PublicationEvidenceRejected,
            resolve_publication_packet_evidence,
        )

        with api.app.app_context():
            record = api.db.session.get(PublicationEvidenceArtifact, artifact_id)
            assert record is not None
            assert record.artifact_bytes == body
            assert record.sha256 == hashlib.sha256(body).hexdigest()
            assert record.candidate_digest == candidate_digest

            assert api.db.session.get(PublicationEvidenceArtifactClaim, artifact_id) is None
            table_names = set(
                api.db.session.execute(
                    text("SELECT name FROM sqlite_master WHERE type = 'table'")
                ).scalars()
            )
            assert "future_publication_evidence_claim_v2" in table_names
            foreign_keys = api.db.session.execute(
                text("PRAGMA foreign_key_list('future_publication_evidence_claim_v2')")
            ).all()
            assert any(
                row[2] == "future_publication_evidence_v2"
                and row[3] == "artifact_id"
                and row[4] == "artifact_id"
                for row in foreign_keys
            )

            # A pre-claim row remains readable, but cannot resolve into a
            # packet until an explicit immutable location claim is recorded.
            valid_candidate_digest = candidate_digest
            candidate = FuturePuzzleV2CandidateRecord(
                profile_id=str(uuid4()),
                candidate_hash=valid_candidate_digest.removeprefix("sha256:"),
                candidate_id=manifest["id"],
                job_id=str(uuid4()),
                manifest_json=manifest,
                created_at="2026-09-26T12:00:00.000+00:00",
            )
            api.db.session.add(candidate)
            api.db.session.commit()

            ref = {
                "artifactId": artifact_id,
                "sha256": record.sha256,
                "kind": "source-artifact",
            }
            packet = {
                "schema": "puzzle-v2-publication-review-v1",
                "candidateDigest": valid_candidate_digest,
                "sourceAttestations": [
                    {"reviewerId": "legacy-reviewer", "evidenceRefs": [ref]}
                ],
                "clueAdjudications": [
                    {"evidenceRefs": [ref], "challenger": {"evidenceRefs": [ref]}}
                ],
                "crossingReview": {
                    "candidateDigest": valid_candidate_digest,
                    "certificates": [{"evidenceRefs": [ref]}],
                    "simulation": {"evidenceRefs": [ref]},
                },
                "weekdayReview": {
                    "candidateDigest": valid_candidate_digest,
                    "evidenceRefs": [ref],
                    "blindClassifications": [{"rationale": ref}],
                },
            }
            with pytest.raises(
                PublicationEvidenceRejected,
                match="artifact-unresolved-or-corrupt:sourceAttestations",
            ):
                resolve_publication_packet_evidence(packet, valid_candidate_digest)
    finally:
        with api.app.app_context():
            api.db.session.remove()
            api.db.engine.dispose()
