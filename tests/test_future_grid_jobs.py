"""Durable answer-grid draft queue; no native runtime or model is needed."""

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import sqlite3
import subprocess
from types import MappingProxyType, SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import event

from tests.test_api_isolated import api, no_network  # noqa: F401
from src.crossword.construction_runtime import DEFAULT_OPTIONS, FullSizeDraftCancelled
from src.crossword import construction_runtime
from src.crossword.future_grid_jobs import (
    FutureGridDraftJob,
    FutureGridDraftPrivateSelection,
    process_next_grid_draft,
)
from src.crossword.future_puzzles import (
    FuturePuzzleV2CandidateRecord,
    validate_personalized_v2_review_candidate,
)
from src.crossword.v2_session_journal import FuturePuzzleV2PublishedRecord
from src.crossword.episteme_store import EpistemeProfileRecord
from src.crossword.admitted_pack import (
    AdmittedClueContent,
    AdmittedLexemeContent,
    AdmittedPackContent,
    AdmittedSenseContent,
    canonical_json,
)
from src.crossword.personalized_manifest import derive_xfill_slots
from tests.test_admitted_pack_loader import _fixture as _synthetic_pack_fixture, _resign
import src.crossword.future_grid_jobs as grid_jobs_module


def _profile_payload():
    return {
        "version": 1,
        "id": str(uuid4()),
        "step": 4,
        "object": "thread",
        "companion": "fork",
        "traces": ["echo", "moss"],
        "weekday": "thursday",
        "learningLanguage": "German",
        "excluded": ["tension"],
        "complete": True,
    }


def _create_profile(client, value):
    response = client.put(
        f"/api/future/profile/{value['id']}",
        json=value,
        headers={"If-None-Match": "*"},
    )
    assert response.status_code == 200


def _add_episteme_control(client, profile_id, concept_id, *, action="exclude"):
    current = client.get(f"/api/future/profile/{profile_id}/episteme")
    assert current.status_code == 200, current.json
    revision = current.json["revision"]
    evidence = {
        "evidenceId": str(uuid4()),
        "recordedAt": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "type": "explicit-preference",
        "concept": {
            "conceptId": concept_id,
            "label": concept_id.replace("-", " "),
            "language": "en",
        },
        "kind": "taste" if action == "seek" else "context",
        "action": action,
        "scope": {"mode": "play", "language": "en"},
        "supersedesEvidenceIds": [],
        "userText": (
            f"More {concept_id.replace('-', ' ')} clues"
            if action == "seek"
            else f"Fewer {concept_id.replace('-', ' ')} clues"
        ),
    }
    updated = client.post(
        f"/api/future/profile/{profile_id}/episteme/updates",
        json={
            "expectedRevision": revision,
            "updateId": str(uuid4()),
            "recordedAt": evidence["recordedAt"],
            "evidence": [evidence],
            "evidenceActions": [],
        },
        headers={"Origin": "http://localhost"},
    )
    assert updated.status_code == 200, updated.json
    return updated.json


def _configure_synthetic_personalized_pack(api, tmp_path):
    # All fixture vocabulary and source records here are synthetic CI data.
    pack, pins = _synthetic_pack_fixture()
    source_lexeme = pack["lexemes"][0]
    for lexeme_id, answer, concept_id in (
        ("lexeme-cloudnine", "CLOUDNINE", "topic:animals"),
        ("lexeme-moonlight", "MOONLIGHT", "topic:night"),
        ("lexeme-crosswording", "CROSSWORDING", "topic:wordplay"),
    ):
        lexeme = copy.deepcopy(source_lexeme)
        lexeme["id"] = lexeme_id
        lexeme["headword"] = answer
        lexeme["provenance"]["evidenceRefs"] = [f"synthetic:lexeme/{answer}"]
        lexeme["personalization"] = {
            "conceptIds": [concept_id],
            "pool": "exploration",
        }
        pack["lexemes"].append(lexeme)
    _resign(pack)
    path = tmp_path / "synthetic-personalized-pack.json"
    path.write_bytes(canonical_json(pack))
    source_pins = {
        source_id: {
            "version": pin.version,
            "artifactSha256": pin.artifact_sha256,
            "contentClass": pin.content_class,
        }
        for source_id, pin in pins.items()
    }
    api.app.config.update(
        FUTURE_ADMITTED_PACK_PATH=str(path),
        FUTURE_ADMITTED_PACK_ID=pack["packId"],
        FUTURE_ADMITTED_PACK_SHA256=pack["artifactSha256"],
        FUTURE_ADMITTED_SOURCE_PINS_JSON=json.dumps(source_pins, separators=(",", ":")),
    )
    return pack, path


def _personalized_profile_payload(*, weekday="thursday"):
    profile = _profile_payload()
    profile["learningLanguage"] = "None for now"
    profile["weekday"] = weekday
    return profile


def _admitted_runtime_result(seed, options, admitted_wordlist, answer):
    themes = list(options["themes"])
    entry_answers = list(dict.fromkeys([*themes, answer]))
    entry_answers.extend([answer] * (50 - len(entry_answers)))
    return {
        "engine": "xfill",
        "options": options,
        "durationMs": 27,
        "sourceDigest": "sha256:" + "b" * 64,
        "provenance": {
            "admittedPack": {
                "packId": admitted_wordlist["packId"],
                "packSha256": admitted_wordlist["packSha256"],
                "wordlistSha256": admitted_wordlist["sha256"],
            }
        },
        "grid": {
            "fill": ["A" * 15 for _ in range(15)],
            "template": ["." * 15 for _ in range(15)],
            "entries": [
                {
                    "num": index + 1,
                    "dir": "A" if index % 2 == 0 else "D",
                    "answer": entry_answer,
                    "theme": entry_answer in themes,
                }
                for index, entry_answer in enumerate(entry_answers)
            ],
        },
    }


def _complete_synthetic_review_pack():
    """Purpose-built pinned pack with exact synthetic sense-backed clues."""
    source_id = "synthetic-worker-review-source"
    source_digest = "a" * 64
    pack_id = "synthetic-worker-review-pack"
    pack_digest = "b" * 64
    source = {
        "sourceId": source_id,
        "version": "synthetic-v1",
        "artifactSha256": source_digest,
        "spdx": "CC0-1.0",
        "attribution": "Synthetic worker review fixture only.",
        "contentClass": "synthetic",
    }

    def provenance(reference):
        return MappingProxyType(
            {
                "source": MappingProxyType(dict(source)),
                "evidenceRefs": (reference,),
                "reviewerId": "synthetic-reviewer",
                "reviewedAt": "2026-09-26",
            }
        )

    lexemes = []
    candidates = []
    for answer in ("AAA", "AAAAA"):
        lexeme_id = f"lexeme-{answer.lower()}"
        sense_id = f"sense-{answer.lower()}"
        clue_id = f"clue-{answer.lower()}"
        sense_provenance = provenance(f"synthetic:sense/{answer}")
        sense = AdmittedSenseContent(
            sense_id=sense_id,
            gloss=f"Synthetic clue sense for {answer}.",
            resolution_status="resolved",
            clue_eligible=True,
            fill_only=False,
            provenance=sense_provenance,
        )
        clue_text = f"Synthetic clue for {answer}"
        grammar = MappingProxyType(
            {
                "grammarVersion": "clue-grammar-v1",
                "clueId": clue_id,
                "entryId": "source-entry",
                "clueText": clue_text,
                "answer": answer,
                "variantRole": "standard",
                "primaryFamily": "definition",
                "morphology": MappingProxyType(
                    {
                        "clue": MappingProxyType(
                            {"partOfSpeech": "noun", "number": "singular"}
                        ),
                        "answer": MappingProxyType(
                            {"partOfSpeech": "noun", "number": "singular"}
                        ),
                        "substitutionWitness": MappingProxyType(
                            {
                                "frame": "A synthetic answer: {0}.",
                                "cluePhrase": clue_text,
                                "answerPhrase": answer,
                                "editorialNote": "Synthetic worker fixture only.",
                                "reviewerId": "synthetic-reviewer",
                            }
                        ),
                    }
                ),
                "signalSpans": (),
            }
        )
        clue_provenance = MappingProxyType(
            {
                "sources": (MappingProxyType(dict(source)),),
                "evidenceRefs": (f"synthetic:clue/{answer}",),
                "evidenceProvenance": sense_provenance,
                "reviewerId": "synthetic-reviewer",
                "reviewedAt": "2026-09-26",
                "semanticTruthStatus": "not-established-by-grammar-validator",
            }
        )
        clue = AdmittedClueContent(
            clue_id=clue_id,
            text=clue_text,
            answer_lexeme_id=lexeme_id,
            evidence_type="sense",
            evidence_id=sense_id,
            grammar=grammar,
            provenance=clue_provenance,
        )
        lexemes.append(
            AdmittedLexemeContent(
                lexeme_id=lexeme_id,
                answer=answer,
                language="en",
                provenance=provenance(f"synthetic:lexeme/{answer}"),
                senses=(sense,),
                facts=(),
                clues=(clue,),
            )
        )
        candidates.append(
            {
                "candidateId": lexeme_id,
                "answer": answer,
                "language": "en",
                "conceptIds": ["topic:synthetic"],
                "knowledgeTaskIds": [],
                "associationIds": [],
                "pool": "broad",
                "eligibility": {
                    "status": "eligible",
                    "packId": pack_id,
                    "packVersion": pack_digest,
                    "sourceIds": [source_id],
                },
            }
        )

    return SimpleNamespace(
        candidates=candidates,
        content=AdmittedPackContent(pack_id, pack_digest, tuple(lexemes)),
        pack_id=pack_id,
        pack_sha256=pack_digest,
        source_pins=(
            {
                "sourceId": source_id,
                "version": source["version"],
                "artifactSha256": source_digest,
                "contentClass": "synthetic",
            },
        ),
    )


def _complete_synthetic_runtime_result(seed, options, admitted_wordlist):
    row_separators = {5, 11}
    column_separators = {5, 11}
    fill = [
        "".join(
            "#" if row in row_separators or column in column_separators else "A"
            for column in range(15)
        )
        for row in range(15)
    ]
    slots = derive_xfill_slots(fill)
    assert len(slots) == 78
    return {
        "engine": "xfill",
        "options": options,
        "durationMs": 27,
        "sourceDigest": "sha256:" + "d" * 64,
        "provenance": {
            "admittedPack": {
                "packId": admitted_wordlist["packId"],
                "packSha256": admitted_wordlist["packSha256"],
                "wordlistSha256": admitted_wordlist["sha256"],
            }
        },
        "grid": {
            "fill": fill,
            "template": [row.replace("A", ".") for row in fill],
            "entries": [
                {
                    "num": slot.number,
                    "dir": "A" if slot.direction == "across" else "D",
                    "answer": slot.answer,
                    "theme": False,
                }
                for slot in slots
            ],
        },
    }


def _synthetic_native_wire_shaped_runtime_result(seed, options, admitted_wordlist):
    """Synthetic grid data carrying the pinned runtime's richer wire shape.

    The letters and scores below are synthetic test values; this fixture does
    not claim to be an xfill engine output. It mirrors GeneratedGrid's field
    names to exercise the production host adapter that receives that shape.
    """
    result = _complete_synthetic_runtime_result(seed, options, admitted_wordlist)
    grid = result["grid"]
    slots = derive_xfill_slots(grid["fill"])
    grid.update(
        {
            "id": 17,
            "blocks": sum(row.count("#") for row in grid["fill"]),
            "themed": False,
            "mean_score": 73.5,
            "min_score": 61.0,
            "iffy": 1,
            "weak": 2,
            "template": [row.replace("A", ".") for row in grid["fill"]],
        }
    )
    for entry, slot in zip(grid["entries"], slots, strict=True):
        entry.update(
            {
                "row": slot.cells[0][0],
                "col": slot.cells[0][1],
                "len": len(slot.cells),
                "score": 99.0,
            }
        )
    return result


def _job_body(profile_id, *, key=None, seed=27):
    return {
        "profileId": profile_id,
        "idempotencyKey": key or str(uuid4()),
        "seed": seed,
    }


def _runtime_result(seed=27):
    return {
        "engine": "xfill",
        "options": {"seed": seed},
        "durationMs": 27,
        "sourceDigest": "sha256:" + "b" * 64,
        "grid": {"fill": ["A" * 15 for _ in range(15)], "entries": []},
    }


def test_grid_draft_job_is_idempotent_profile_scoped_and_not_playable(api):
    client = api.app.test_client()
    profile = _profile_payload()
    _create_profile(client, profile)
    body = _job_body(profile["id"])

    created = client.post("/api/future/grid-draft-jobs", json=body)
    assert created.status_code == 202
    assert created.cache_control.no_store
    assert created.json["state"] == "queued"
    assert created.json["playable"] is False

    retry = client.post("/api/future/grid-draft-jobs", json=body)
    assert retry.status_code == 200
    assert retry.json["id"] == created.json["id"]
    assert (
        client.post(
            "/api/future/grid-draft-jobs",
            json={**body, "seed": 28},
        ).status_code
        == 409
    )

    url = f"/api/future/grid-draft-jobs/{created.json['id']}"
    assert client.get(url).status_code == 400
    assert client.get(url, query_string={"profileId": str(uuid4())}).status_code == 404
    assert (
        client.get(url, query_string={"profileId": profile["id"]}).json["state"]
        == "queued"
    )
    with api.app.app_context():
        job = api.db.session.get(FutureGridDraftJob, created.json["id"])
        episteme = api.db.session.get(EpistemeProfileRecord, profile["id"])
        assert job.request_json["weekdayDifficulty"] == "thursday"
        assert job.request_json["epistemeRevision"] == episteme.revision == 0
        assert job.request_json["epistemeUpdatedAt"] == episteme.updated_at
        assert job.request_json["epistemeDigest"] == grid_jobs_module._digest(
            episteme.profile_json
        )
        assert job.request_json["epistemeDigestAlgorithm"] == "sha256-canonical-json-v1"


def test_private_job_stage_is_reported_only_by_the_current_lease(api):
    client = api.app.test_client()
    profile = _profile_payload()
    _create_profile(client, profile)
    created = client.post(
        "/api/future/private-puzzle-jobs",
        json={
            "profileId": profile["id"],
            "idempotencyKey": str(uuid4()),
            "seed": 27,
            "weekday": "wednesday",
        },
        headers={"Origin": "http://localhost"},
    )
    assert created.status_code == 202, created.json

    with api.app.app_context():
        job = api.db.session.get(FutureGridDraftJob, created.json["id"])
        token = str(uuid4())
        job.state = "running"
        job.lease_token = token
        job.lease_until = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(
            timespec="milliseconds"
        )
        api.db.session.commit()

    grid_jobs_module._set_runtime_stage(api.app, created.json["id"], token, "native-xfill")
    running = client.get(
        f"/api/future/private-puzzle-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert running.json["stage"] == "native-xfill"
    assert isinstance(running.json["stageElapsedSeconds"], (int, float))
    assert running.json["stageElapsedSeconds"] >= 0
    with api.app.app_context():
        job = api.db.session.get(FutureGridDraftJob, created.json["id"])
        assert job.request_json["runtimeStage"] == "native-xfill"
        assert isinstance(job.request_json["runtimeStageStartedAt"], str)

    grid_jobs_module._set_runtime_stage(
        api.app, created.json["id"], str(uuid4()), "clue-generation"
    )
    unchanged = client.get(
        f"/api/future/private-puzzle-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert unchanged.json["stage"] == "native-xfill"


def test_lost_response_retry_returns_original_job_after_profile_changes(api):
    client = api.app.test_client()
    profile = _profile_payload()
    _create_profile(client, profile)
    assert (
        _add_episteme_control(client, profile["id"], "us-officeholders")["revision"]
        == 1
    )
    body = _job_body(profile["id"])

    created = client.post("/api/future/grid-draft-jobs", json=body)
    assert created.status_code == 202
    with api.app.app_context():
        saved = api.db.session.get(FutureGridDraftJob, created.json["id"])
        original_snapshot = dict(saved.request_json)
        assert original_snapshot["weekdayDifficulty"] == "thursday"
        assert original_snapshot["epistemeRevision"] == 1
    profile_url = f"/api/future/profile/{profile['id']}"
    current = client.get(profile_url)
    changed = client.put(
        profile_url,
        json={**current.json["draft"], "weekday": "wednesday"},
        headers={"If-Match": current.headers["ETag"]},
    )
    assert changed.status_code == 200
    assert _add_episteme_control(client, profile["id"], "sports-clues")["revision"] == 2

    retry = client.post("/api/future/grid-draft-jobs", json=body)
    assert retry.status_code == 200
    assert retry.json["id"] == created.json["id"]
    with api.app.app_context():
        saved = api.db.session.get(FutureGridDraftJob, created.json["id"])
        assert saved.request_json["profileUpdatedAt"] != changed.json["updatedAt"]
        assert saved.request_json == original_snapshot
        assert saved.request_digest
        current_episteme = api.db.session.get(EpistemeProfileRecord, profile["id"])
        assert current_episteme.revision == 2
        assert saved.request_json["epistemeDigest"] != grid_jobs_module._digest(
            current_episteme.profile_json
        )


def test_grid_draft_creation_returns_bounded_runtime_error_if_episteme_cannot_initialize(
    api, monkeypatch
):
    client = api.app.test_client()
    profile = _profile_payload()
    _create_profile(client, profile)

    def unavailable(*_args, **_kwargs):
        raise grid_jobs_module.EpistemeRuntimeUnavailable(
            "test runtime unavailable" * 100
        )

    monkeypatch.setattr(grid_jobs_module, "get_or_create_episteme_profile", unavailable)
    response = client.post("/api/future/grid-draft-jobs", json=_job_body(profile["id"]))
    assert response.status_code == 503
    assert len(response.json["error"]) <= 240
    with api.app.app_context():
        assert api.db.session.query(FutureGridDraftJob).count() == 0


def test_grid_draft_does_not_substitute_zero_for_an_inconsistent_stored_revision(api):
    client = api.app.test_client()
    profile = _profile_payload()
    _create_profile(client, profile)
    assert (
        client.get(f"/api/future/profile/{profile['id']}/episteme").status_code == 200
    )
    with api.app.app_context():
        episteme = api.db.session.get(EpistemeProfileRecord, profile["id"])
        episteme.revision = 5
        api.db.session.commit()

    response = client.post("/api/future/grid-draft-jobs", json=_job_body(profile["id"]))
    assert response.status_code == 409
    assert response.json["error"] == "The stored host episteme snapshot is inconsistent"
    with api.app.app_context():
        assert api.db.session.query(FutureGridDraftJob).count() == 0


def test_grid_draft_job_rejects_foreign_origins_and_invalid_requests(api):
    client = api.app.test_client()
    profile = _profile_payload()
    _create_profile(client, profile)
    body = _job_body(profile["id"])

    assert (
        client.post(
            "/api/future/grid-draft-jobs",
            json=body,
            headers={"Origin": "https://other.invalid"},
        ).status_code
        == 403
    )
    for payload in (
        {},
        {**body, "seed": True},
        {**body, "extra": "field"},
        {**body, "profileId": str(uuid4())},
    ):
        assert client.post("/api/future/grid-draft-jobs", json=payload).status_code in {
            400,
            404,
        }
    assert (
        client.post(
            "/api/future/grid-draft-jobs",
            data="x" * 17_000,
            content_type="application/json",
        ).status_code
        == 413
    )


def test_queued_job_can_be_cancelled_and_worker_skips_it(api):
    client = api.app.test_client()
    profile = _profile_payload()
    _create_profile(client, profile)
    body = _job_body(profile["id"])
    created = client.post("/api/future/grid-draft-jobs", json=body)
    cancelled = client.post(
        f"/api/future/grid-draft-jobs/{created.json['id']}/cancel",
        json={"profileId": profile["id"]},
    )

    assert cancelled.status_code == 200
    assert cancelled.json["state"] == "cancelled"
    assert (
        process_next_grid_draft(
            api.app,
            generator=lambda **kwargs: pytest.fail("cancelled job must not run"),
        )
        is False
    )


def test_worker_claims_persists_result_and_removes_live_lease(api):
    client = api.app.test_client()
    profile = _profile_payload()
    _create_profile(client, profile)
    created = client.post("/api/future/grid-draft-jobs", json=_job_body(profile["id"]))
    calls = []

    assert process_next_grid_draft(
        api.app,
        generator=lambda **kwargs: calls.append(kwargs)
        or _runtime_result(kwargs["seed"]),
    )
    assert len(calls) == 1
    assert calls[0]["seed"] == 27
    assert calls[0]["options"] == {**DEFAULT_OPTIONS, "seed": 27}
    assert set(calls[0]) == {"seed", "options", "cancel_requested"}
    assert not any(
        word in json.dumps(calls[0]["options"])
        for word in profile["traces"] + [profile["object"], profile["companion"]]
    )
    assert callable(calls[0]["cancel_requested"])
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.json["state"] == "ready"
    assert saved.json["playable"] is False
    assert saved.json["result"]["sourceDigest"] == "sha256:" + "b" * 64
    with api.app.app_context():
        record = api.db.session.get(FutureGridDraftJob, created.json["id"])
        assert record.attempt == 1
        assert record.request_json["recipe"] == "xfill-wide-v1"
        assert record.request_json["options"] == {**DEFAULT_OPTIONS, "seed": 27}
        assert record.lease_token is None
        assert record.lease_until is None


def test_worker_discards_result_when_running_job_is_cancelled(api):
    client = api.app.test_client()
    profile = _profile_payload()
    _create_profile(client, profile)
    created = client.post("/api/future/grid-draft-jobs", json=_job_body(profile["id"]))

    def cancel_during_fill(**kwargs):
        with api.app.app_context():
            record = api.db.session.get(FutureGridDraftJob, created.json["id"])
            record.cancel_requested = True
            api.db.session.commit()
        assert kwargs["cancel_requested"]() is True
        return _runtime_result(kwargs["seed"])

    assert process_next_grid_draft(api.app, generator=cancel_during_fill)
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.json["state"] == "cancelled"
    assert saved.json["result"] is None
    assert saved.json["cancelRequested"] is True


def test_worker_reclaims_expired_lease_and_persists_runtime_failure(api):
    client = api.app.test_client()
    profile = _profile_payload()
    _create_profile(client, profile)
    created = client.post("/api/future/grid-draft-jobs", json=_job_body(profile["id"]))
    old_expiry = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(
        timespec="milliseconds"
    )
    with api.app.app_context():
        record = api.db.session.get(FutureGridDraftJob, created.json["id"])
        record.state = "running"
        record.attempt = 1
        record.lease_token = str(uuid4())
        record.lease_until = old_expiry
        api.db.session.commit()

    assert process_next_grid_draft(
        api.app,
        generator=lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("xfill unavailable")
        ),
    )
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.json["state"] == "failed"
    assert saved.json["attempt"] == 2
    assert saved.json["error"] == "xfill unavailable"


def test_expired_cancelled_lease_becomes_terminal_without_running_again(api):
    client = api.app.test_client()
    profile = _profile_payload()
    _create_profile(client, profile)
    created = client.post("/api/future/grid-draft-jobs", json=_job_body(profile["id"]))
    expired = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(
        timespec="milliseconds"
    )
    with api.app.app_context():
        job = api.db.session.get(FutureGridDraftJob, created.json["id"])
        job.state = "running"
        job.attempt = 1
        job.lease_token = str(uuid4())
        job.lease_until = expired
        job.cancel_requested = True
        job.result_json = {"must": "be discarded"}
        api.db.session.commit()

    assert (
        process_next_grid_draft(
            api.app,
            generator=lambda **kwargs: pytest.fail(
                "expired cancelled job must not run"
            ),
        )
        is False
    )
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.json["state"] == "cancelled"
    assert saved.json["result"] is None
    with api.app.app_context():
        job = api.db.session.get(FutureGridDraftJob, created.json["id"])
        assert job.lease_token is None
        assert job.lease_until is None


def test_cancel_committed_between_generation_and_finalize_cannot_publish(api):
    client = api.app.test_client()
    profile = _profile_payload()
    _create_profile(client, profile)
    created = client.post("/api/future/grid-draft-jobs", json=_job_body(profile["id"]))
    with api.app.app_context():
        database_path = api.db.engine.url.database
        engine = api.db.engine
    injected = False

    def cancel_before_update(
        _connection, _cursor, statement, _parameters, _context, _many
    ):
        nonlocal injected
        lowered = statement.lower()
        if (
            injected
            or "update future_grid_draft_jobs" not in lowered
            or "result_json" not in lowered
            or "cancel_requested is 0" not in lowered
        ):
            return
        injected = True
        with sqlite3.connect(database_path, timeout=3) as connection:
            changed = connection.execute(
                "UPDATE future_grid_draft_jobs SET cancel_requested = 1 WHERE id = ? AND state = 'running'",
                (created.json["id"],),
            )
            assert changed.rowcount == 1

    event.listen(engine, "before_cursor_execute", cancel_before_update)
    try:
        assert process_next_grid_draft(
            api.app,
            generator=lambda **kwargs: _runtime_result(kwargs["seed"]),
        )
    finally:
        event.remove(engine, "before_cursor_execute", cancel_before_update)

    assert injected
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.json["state"] == "cancelled"
    assert saved.json["cancelRequested"] is True
    assert saved.json["result"] is None


def test_stale_worker_completion_cannot_overwrite_a_new_lease_result(api):
    client = api.app.test_client()
    profile = _profile_payload()
    _create_profile(client, profile)
    created = client.post("/api/future/grid-draft-jobs", json=_job_body(profile["id"]))
    expired = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(
        timespec="milliseconds"
    )

    def stale_worker(**kwargs):
        with api.app.app_context():
            job = api.db.session.get(FutureGridDraftJob, created.json["id"])
            job.lease_until = expired
            api.db.session.commit()
        assert process_next_grid_draft(
            api.app,
            generator=lambda **inner: {
                **_runtime_result(inner["seed"]),
                "grid": {"fill": ["N" * 15]},
            },
        )
        return {
            **_runtime_result(kwargs["seed"]),
            "grid": {"fill": ["O" * 15]},
        }

    assert process_next_grid_draft(api.app, generator=stale_worker)
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.json["state"] == "ready"
    assert saved.json["attempt"] == 2
    assert saved.json["result"]["grid"]["fill"] == ["N" * 15]


def test_worker_shutdown_stops_runtime_and_requeues_unless_cancelled(api):
    client = api.app.test_client()
    profile = _profile_payload()
    _create_profile(client, profile)
    created = client.post("/api/future/grid-draft-jobs", json=_job_body(profile["id"]))
    stopping = False

    def stop_during_fill(**kwargs):
        nonlocal stopping
        stopping = True
        assert kwargs["cancel_requested"]() is True
        raise FullSizeDraftCancelled("The answer-grid draft was cancelled")

    assert process_next_grid_draft(
        api.app,
        generator=stop_during_fill,
        shutdown_requested=lambda: stopping,
    )
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.json["state"] == "queued"
    assert saved.json["result"] is None
    with api.app.app_context():
        job = api.db.session.get(FutureGridDraftJob, created.json["id"])
        assert job.attempt == 1
        assert job.lease_token is None
        assert job.cancel_requested is False


def test_personalized_grid_jobs_fail_closed_when_pins_are_missing_or_wrong(
    api, monkeypatch, tmp_path
):
    client = api.app.test_client()
    profile = _personalized_profile_payload()
    _create_profile(client, profile)
    calls = []

    missing = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(profile["id"]),
    )
    assert missing.status_code == 503
    assert missing.json["playable"] is False
    assert missing.cache_control.no_store
    with api.app.app_context():
        assert api.db.session.query(FutureGridDraftJob).count() == 0
        assert api.db.session.get(EpistemeProfileRecord, profile["id"]) is None

    pack, path = _configure_synthetic_personalized_pack(api, tmp_path)
    api.app.config["FUTURE_ADMITTED_PACK_SHA256"] = "f" * 64
    wrong = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(profile["id"]),
    )
    assert wrong.status_code == 503
    assert (
        process_next_grid_draft(
            api.app,
            generator=lambda **kwargs: calls.append(kwargs)
            or pytest.fail("bad pins must fail before runtime"),
        )
        is False
    )
    assert calls == []
    assert path.exists()
    assert pack["artifactSha256"] != api.app.config["FUTURE_ADMITTED_PACK_SHA256"]
    with api.app.app_context():
        assert api.db.session.query(FutureGridDraftJob).count() == 0


def test_personalized_job_freezes_and_authenticates_the_compiled_brief(api, tmp_path):
    _configure_synthetic_personalized_pack(api, tmp_path)
    client = api.app.test_client()
    profile = _personalized_profile_payload()
    _create_profile(client, profile)
    _add_episteme_control(client, profile["id"], "topic:animals", action="seek")

    created = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(profile["id"]),
    )
    assert created.status_code == 202, created.json
    with api.app.app_context():
        job = api.db.session.get(FutureGridDraftJob, created.json["id"])
        frozen = dict(job.request_json)
        assert frozen["version"] == 4
        assert (
            frozen["briefCompilerVersion"]
            == grid_jobs_module.PERSONALIZED_BRIEF_COMPILER_VERSION
        )
        assert frozen["compiledBriefDigest"] == grid_jobs_module._digest(
            frozen["compiledBrief"]
        )
        assert frozen["compiledBrief"]["profileId"] == profile["id"]
        corrupted = dict(frozen)
        corrupted_brief = dict(frozen["compiledBrief"])
        corrupted_brief["profileId"] = str(uuid4())
        corrupted["compiledBrief"] = corrupted_brief
        job.request_json = corrupted
        api.db.session.commit()

    calls = []
    assert process_next_grid_draft(
        api.app,
        generator=lambda **kwargs: calls.append(kwargs)
        or pytest.fail("tampered brief must fail before runtime"),
    )
    assert calls == []
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.json["state"] == "failed"
    assert saved.json["playable"] is False


def test_legacy_v3_personalized_job_recompiles_from_its_frozen_inputs(
    api, monkeypatch, tmp_path
):
    _configure_synthetic_personalized_pack(api, tmp_path)
    client = api.app.test_client()
    profile = _personalized_profile_payload()
    _create_profile(client, profile)
    _add_episteme_control(client, profile["id"], "topic:animals", action="seek")

    created = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(profile["id"]),
    )
    assert created.status_code == 202, created.json
    with api.app.app_context():
        job = api.db.session.get(FutureGridDraftJob, created.json["id"])
        frozen = dict(job.request_json)
        legacy_brief = frozen["compiledBrief"]
        frozen["version"] = 3
        frozen.pop("briefCompilerVersion")
        frozen.pop("compiledBrief")
        frozen.pop("compiledBriefDigest")
        job.request_json = frozen
        api.db.session.commit()

    reducer_calls = []

    def legacy_reducer(operation):
        reducer_calls.append(operation)
        return {"brief": legacy_brief}

    monkeypatch.setattr(grid_jobs_module, "run_reducer", legacy_reducer)
    runtime_calls = []

    def runtime_stub(**kwargs):
        runtime_calls.append(kwargs)
        receipt = kwargs["admitted_wordlist"]
        return _admitted_runtime_result(
            kwargs["seed"],
            kwargs["options"],
            receipt,
            kwargs["options"]["themes"][0],
        )

    assert process_next_grid_draft(api.app, generator=runtime_stub)
    assert len(reducer_calls) == len(runtime_calls) == 1
    assert reducer_calls[0]["profile"] == frozen["epistemeProfile"]
    assert reducer_calls[0]["options"]["asOf"] == frozen["asOf"]
    assert reducer_calls[0]["options"]["language"] == frozen["puzzleLanguage"]
    assert runtime_calls[0]["admitted_wordlist"]["sha256"]
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.json["state"] == "ready"
    assert (
        saved.json["result"]["personalization"]["receipt"]["briefCompilerVersion"]
        == "worker-recompiled-v1"
    )
    assert saved.json["result"]["personalization"]["receipt"][
        "compiledBriefDigest"
    ] == grid_jobs_module._digest(legacy_brief)
    assert saved.json["result"]["personalization"][
        "manifestCandidateRejectionCode"
    ] == ("entry-clue-not-available")


def test_personalized_worker_freezes_profile_and_pack_and_rejects_changed_pins_before_runtime(
    api, monkeypatch, tmp_path
):
    client = api.app.test_client()
    _configure_synthetic_personalized_pack(api, tmp_path)
    profile = _personalized_profile_payload()
    _create_profile(client, profile)
    _add_episteme_control(client, profile["id"], "topic:animals", action="seek")
    body = _job_body(profile["id"])
    created = client.post("/api/future/personalized/grid-draft-jobs", json=body)
    assert created.status_code == 202, created.json

    # A deployment pin change after queueing makes the frozen job stale. The
    # worker rejects it before calling the native runtime.
    api.app.config["FUTURE_ADMITTED_PACK_ID"] = "different-synthetic-pack"
    calls = []
    assert process_next_grid_draft(
        api.app,
        generator=lambda **kwargs: calls.append(kwargs)
        or pytest.fail("changed pack must fail before runtime"),
    )
    assert calls == []
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.json["state"] == "failed"
    assert saved.json["result"] is None
    assert saved.json["playable"] is False


def test_personalized_profiles_order_themes_and_entry_sources_from_pinned_pack(
    api, tmp_path
):
    _configure_synthetic_personalized_pack(api, tmp_path)
    client = api.app.test_client()
    animals = _personalized_profile_payload(weekday="wednesday")
    night = _personalized_profile_payload(weekday="thursday")
    _create_profile(client, animals)
    _create_profile(client, night)
    _add_episteme_control(client, animals["id"], "topic:animals", action="seek")
    _add_episteme_control(client, night["id"], "topic:night", action="seek")
    _add_episteme_control(client, night["id"], "topic:animals", action="exclude")

    animals_job = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(animals["id"]),
    )
    night_job = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(night["id"]),
    )
    assert animals_job.status_code == night_job.status_code == 202
    with api.app.app_context():
        queued_animals = api.db.session.get(FutureGridDraftJob, animals_job.json["id"])
        frozen_animals_request = dict(queued_animals.request_json)
        assert frozen_animals_request[
            "compiledBriefDigest"
        ] == grid_jobs_module._digest(frozen_animals_request["compiledBrief"])
    profile_url = f"/api/future/profile/{animals['id']}"
    current_profile = client.get(profile_url)
    changed_profile = client.put(
        profile_url,
        json={**current_profile.json["draft"], "weekday": "friday"},
        headers={"If-Match": current_profile.headers["ETag"]},
    )
    assert changed_profile.status_code == 200
    _add_episteme_control(client, animals["id"], "topic:animals", action="exclude")
    calls = []

    def runtime_stub(**kwargs):
        receipt = kwargs["admitted_wordlist"]
        with open(receipt["path"], "rb") as wordlist:
            raw = wordlist.read()
        assert hashlib.sha256(raw).hexdigest() == receipt["sha256"]
        assert os.stat(receipt["path"]).st_mode & 0o777 == 0o400
        lines = raw.decode("ascii").splitlines()
        assert all(line.endswith(";100") for line in lines[:2])
        answer = kwargs["options"]["themes"][0]
        calls.append(
            {
                "themes": kwargs["options"]["themes"],
                "packId": receipt["packId"],
                "wordlist": raw,
                "answer": answer,
            }
        )
        return _admitted_runtime_result(
            kwargs["seed"], kwargs["options"], receipt, answer
        )

    assert process_next_grid_draft(api.app, generator=runtime_stub)
    assert process_next_grid_draft(api.app, generator=runtime_stub)
    assert len(calls) == 2, [
        client.get(
            f"/api/future/grid-draft-jobs/{job.json['id']}",
            query_string={"profileId": profile["id"]},
        ).json
        for job, profile in ((animals_job, animals), (night_job, night))
    ]
    assert calls[0]["themes"][0] == "CLOUDNINE"
    assert calls[1]["themes"][0] == "MOONLIGHT"
    assert b"CLOUDNINE;" not in calls[1]["wordlist"]

    animals_result = client.get(
        f"/api/future/grid-draft-jobs/{animals_job.json['id']}",
        query_string={"profileId": animals["id"]},
    )
    night_result = client.get(
        f"/api/future/grid-draft-jobs/{night_job.json['id']}",
        query_string={"profileId": night["id"]},
    )
    assert animals_result.json["state"] == night_result.json["state"] == "ready"
    assert animals_result.json["playable"] is night_result.json["playable"] is False
    animals_personalization = animals_result.json["result"]["personalization"]
    night_personalization = night_result.json["result"]["personalization"]
    assert animals_personalization["stage"] == "answer-grid-draft"
    assert animals_personalization["receipt"]["weekdayDifficulty"] == "wednesday"
    assert night_personalization["receipt"]["weekdayDifficulty"] == "thursday"
    assert animals_personalization["wordlistReceipt"]["themeAnswers"][0] == "CLOUDNINE"
    assert night_personalization["wordlistReceipt"]["themeAnswers"][0] == "MOONLIGHT"
    assert (
        "CROSSWORDING" not in animals_personalization["wordlistReceipt"]["themeAnswers"]
    )
    assert (
        "CROSSWORDING" not in night_personalization["wordlistReceipt"]["themeAnswers"]
    )
    assert (
        animals_personalization["receipt"]["packId"]
        == night_personalization["receipt"]["packId"]
    )
    assert (
        animals_personalization["receipt"]["epistemeDigest"]
        != night_personalization["receipt"]["epistemeDigest"]
    )
    assert (
        animals_personalization["receipt"]["epistemeDigest"]
        == frozen_animals_request["epistemeDigest"]
    )
    assert (
        animals_personalization["receipt"]["epistemeRevision"]
        == frozen_animals_request["epistemeRevision"]
    )
    assert (
        animals_personalization["receipt"]["compiledBriefDigest"]
        == frozen_animals_request["compiledBriefDigest"]
    )
    assert (
        animals_personalization["receipt"]["briefCompilerVersion"]
        == frozen_animals_request["briefCompilerVersion"]
    )
    assert "brief" not in animals_personalization
    assert "selection" not in animals_personalization
    assert "selectionLog" not in animals_personalization
    assert "brief" not in night_personalization
    assert "selection" not in night_personalization
    assert "selectionLog" not in night_personalization
    assert (
        animals_personalization["receipt"]["compiledBriefDigest"]
        != (night_personalization["receipt"]["compiledBriefDigest"])
    )
    assert animals_personalization["entrySourceLinks"][0] == {
        "entryNumber": 1,
        "direction": "across",
        "answer": "CLOUDNINE",
        "candidateIds": ["lexeme-cloudnine"],
        "sourceIds": ["synthetic-loader-source"],
    }
    assert {
        link["direction"] for link in animals_personalization["entrySourceLinks"]
    } == {"across", "down"}
    assert (
        "answer-vocabulary provenance only" in animals_personalization["evidenceScope"]
    )
    assert (
        "semantic truth still awaiting review"
        in animals_personalization["evidenceScope"]
    )


def test_personalized_worker_rejects_runtime_provenance_or_unmapped_answers(
    api, tmp_path
):
    _configure_synthetic_personalized_pack(api, tmp_path)
    client = api.app.test_client()
    profile = _personalized_profile_payload()
    _create_profile(client, profile)
    _add_episteme_control(client, profile["id"], "topic:animals", action="seek")
    created = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(profile["id"]),
    )
    assert created.status_code == 202

    def bad_runtime(**kwargs):
        result = _admitted_runtime_result(
            kwargs["seed"], kwargs["options"], kwargs["admitted_wordlist"], "NOTPINNED"
        )
        result["provenance"]["admittedPack"]["packSha256"] = "0" * 64
        return result

    assert process_next_grid_draft(api.app, generator=bad_runtime)
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.json["state"] == "failed"
    assert saved.json["result"] is None

    unmapped = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(profile["id"], seed=28),
    )
    assert unmapped.status_code == 202

    def unmapped_runtime(**kwargs):
        return _admitted_runtime_result(
            kwargs["seed"], kwargs["options"], kwargs["admitted_wordlist"], "NOTPINNED"
        )

    assert process_next_grid_draft(api.app, generator=unmapped_runtime)
    unmapped_saved = client.get(
        f"/api/future/grid-draft-jobs/{unmapped.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert unmapped_saved.json["state"] == "failed"
    assert unmapped_saved.json["result"] is None

    failed = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(profile["id"], seed=29),
    )
    assert failed.status_code == 202
    assert process_next_grid_draft(
        api.app,
        generator=lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("failed at /tmp/private/wordlist")
        ),
    )
    failed_saved = client.get(
        f"/api/future/grid-draft-jobs/{failed.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert failed_saved.json["state"] == "failed"
    assert "/tmp/private" not in failed_saved.json["error"]
    assert (
        failed_saved.json["error"]
        == "The personalized answer-grid draft failed local validation"
    )


@pytest.mark.parametrize(
    "native_wire_shape",
    [False, True],
    ids=["minimal-synthetic-adapter", "native-runtime-wire-shaped-synthetic"],
)
def test_personalized_worker_returns_public_review_manifest_and_private_selection_sidecar(
    api, monkeypatch, native_wire_shape
):
    pack = _complete_synthetic_review_pack()
    monkeypatch.setattr(grid_jobs_module, "_load_pinned_pack", lambda: pack)
    client = api.app.test_client()
    profile = _personalized_profile_payload()
    _create_profile(client, profile)
    _add_episteme_control(client, profile["id"], "topic:synthetic", action="seek")
    created = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(profile["id"]),
    )
    assert created.status_code == 202, created.json

    def runtime(**kwargs):
        result_factory = (
            _synthetic_native_wire_shaped_runtime_result
            if native_wire_shape
            else _complete_synthetic_runtime_result
        )
        return result_factory(
            kwargs["seed"], kwargs["options"], kwargs["admitted_wordlist"]
        )

    assert process_next_grid_draft(api.app, generator=runtime)
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.status_code == 200
    assert saved.json["state"] == "ready"
    assert saved.json["playable"] is False
    result = saved.json["result"]
    candidate = result["personalization"]["manifestCandidate"]
    assert candidate["status"] == "review"
    assert candidate["playable"] is False
    assert candidate["manifest"]["quality"]["verdict"] == "review"
    assert candidate["manifest"]["width"] == candidate["manifest"]["height"] == 15
    assert (
        validate_personalized_v2_review_candidate(candidate["manifest"])
        == candidate["manifest"]
    )
    assert all(
        edge["score"] == 0 and edge["confidence"] == 0
        for edge in candidate["manifest"]["crossingSupport"]["edges"]
    )
    assert "privateSelection" not in result["personalization"]
    assert "private_selection" not in json.dumps(result)
    assert "topic:synthetic" not in json.dumps(candidate["manifest"])

    with api.app.app_context():
        assert api.db.session.query(FuturePuzzleV2PublishedRecord).count() == 0
        sidecar = api.db.session.get(
            FutureGridDraftPrivateSelection, created.json["id"]
        )
        assert sidecar is not None
        assert sidecar.profile_id == profile["id"]
        assert len(sidecar.selection_json) == 78
        assert all("profileEvidenceIds" in row for row in sidecar.selection_json)
        assert any(row["profileEvidenceIds"] for row in sidecar.selection_json)
        private_ids = {
            evidence_id
            for row in sidecar.selection_json
            for evidence_id in row["profileEvidenceIds"]
        }
    assert private_ids
    serialized_job_response = json.dumps(saved.json, ensure_ascii=False, sort_keys=True)
    assert all(
        evidence_id not in serialized_job_response for evidence_id in private_ids
    )


def test_personalized_worker_rejects_native_template_block_mask_mismatch(
    api, monkeypatch
):
    pack = _complete_synthetic_review_pack()
    monkeypatch.setattr(grid_jobs_module, "_load_pinned_pack", lambda: pack)
    client = api.app.test_client()
    profile = _personalized_profile_payload()
    _create_profile(client, profile)
    _add_episteme_control(client, profile["id"], "topic:synthetic", action="seek")
    created = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(profile["id"]),
    )
    assert created.status_code == 202, created.json

    def runtime_with_mismatched_template(**kwargs):
        result = _synthetic_native_wire_shaped_runtime_result(
            kwargs["seed"], kwargs["options"], kwargs["admitted_wordlist"]
        )
        template = result["grid"]["template"]
        assert result["grid"]["fill"][0][0] != "#"
        template[0] = "#" + template[0][1:]
        return result

    assert process_next_grid_draft(api.app, generator=runtime_with_mismatched_template)
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.status_code == 200
    assert saved.json["state"] == "failed"
    assert saved.json["result"] is None
    assert saved.json["playable"] is False
    with api.app.app_context():
        assert api.db.session.query(FuturePuzzleV2CandidateRecord).count() == 0
        assert api.db.session.query(FuturePuzzleV2PublishedRecord).count() == 0


@pytest.mark.parametrize("fence", ["cancel", "lease"])
def test_personalized_candidate_sidecar_is_discarded_after_cancel_or_lease_loss(
    api, monkeypatch, fence
):
    pack = _complete_synthetic_review_pack()
    monkeypatch.setattr(grid_jobs_module, "_load_pinned_pack", lambda: pack)
    client = api.app.test_client()
    profile = _personalized_profile_payload()
    _create_profile(client, profile)
    created = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(profile["id"]),
    )
    assert created.status_code == 202, created.json

    def stale_or_cancelled_runtime(**kwargs):
        with api.app.app_context():
            job = api.db.session.get(FutureGridDraftJob, created.json["id"])
            if fence == "cancel":
                job.cancel_requested = True
            else:
                job.lease_token = str(uuid4())
            api.db.session.commit()
        # Deliberately ignore cancellation: the worker must fence persistence
        # even when a runtime returns a complete candidate after its lease ends.
        return _complete_synthetic_runtime_result(
            kwargs["seed"], kwargs["options"], kwargs["admitted_wordlist"]
        )

    assert process_next_grid_draft(api.app, generator=stale_or_cancelled_runtime)
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    with api.app.app_context():
        assert (
            api.db.session.get(FutureGridDraftPrivateSelection, created.json["id"])
            is None
        )
        assert api.db.session.query(FuturePuzzleV2CandidateRecord).count() == 0
    if fence == "cancel":
        assert saved.json["state"] == "cancelled"
        assert saved.json["result"] is None
    else:
        assert saved.json["state"] == "running"
        assert saved.json["result"] is None


def test_personalized_worker_rejects_malformed_frozen_brief_before_runtime(
    api, tmp_path
):
    _configure_synthetic_personalized_pack(api, tmp_path)
    client = api.app.test_client()
    profile = _personalized_profile_payload()
    _create_profile(client, profile)
    _add_episteme_control(client, profile["id"], "topic:animals", action="seek")
    created = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(profile["id"]),
    )
    assert created.status_code == 202
    with api.app.app_context():
        job = api.db.session.get(FutureGridDraftJob, created.json["id"])
        frozen = dict(job.request_json)
        frozen["compiledBrief"] = {"briefVersion": "stale"}
        frozen["compiledBriefDigest"] = grid_jobs_module._digest(
            frozen["compiledBrief"]
        )
        job.request_json = frozen
        api.db.session.commit()
    calls = []
    assert process_next_grid_draft(
        api.app,
        generator=lambda **kwargs: calls.append(kwargs)
        or pytest.fail("invalid brief must fail before runtime"),
    )
    assert calls == []
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.json["state"] == "failed"
    assert saved.json["result"] is None
    assert "malformed or stale brief" in saved.json["error"]


def test_construction_bridge_passes_and_verifies_private_admitted_wordlist_receipt(
    monkeypatch, tmp_path
):
    cli = tmp_path / "local-runtime.mjs"
    cli.write_text("", encoding="utf-8")
    monkeypatch.setattr(construction_runtime, "RUNTIME_CLI", cli)
    monkeypatch.setattr(
        construction_runtime.shutil, "which", lambda _name: "/usr/bin/node"
    )
    wordlist = tmp_path / "admitted.dict"
    raw = b"CAT;100\n"
    wordlist.write_bytes(raw)
    receipt = {
        "path": str(wordlist.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "packId": "synthetic-test-pack",
        "packSha256": "a" * 64,
    }
    options = {**DEFAULT_OPTIONS, "seed": 31}
    success = _runtime_result(31)
    success["options"] = options
    success["grid"]["entries"] = [
        {"num": index + 1, "dir": "A", "answer": "CAT", "theme": False}
        for index in range(50)
    ]
    success["provenance"] = {
        "admittedPack": {
            "packId": receipt["packId"],
            "packSha256": receipt["packSha256"],
            "wordlistSha256": receipt["sha256"],
        }
    }
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=json.dumps({"version": 1, "result": success}),
            stderr="",
        )

    monkeypatch.setattr(construction_runtime.subprocess, "run", run)
    result = construction_runtime.generate_full_size_draft(
        seed=31,
        options=options,
        admitted_wordlist=receipt,
    )
    operation = json.loads(calls[0][1]["input"])
    assert operation["admittedWordlist"] == receipt
    assert result["provenance"]["admittedPack"]["wordlistSha256"] == receipt["sha256"]

    calls.clear()
    receipt["sha256"] = "0" * 64
    with pytest.raises(construction_runtime.FullSizeDraftRejected, match="digest"):
        construction_runtime.generate_full_size_draft(
            seed=31,
            options=options,
            admitted_wordlist=receipt,
        )
    assert calls == []


def test_personalized_result_over_size_limit_is_failed_without_persisting_grid(
    api, monkeypatch, tmp_path
):
    _configure_synthetic_personalized_pack(api, tmp_path)
    client = api.app.test_client()
    profile = _personalized_profile_payload()
    _create_profile(client, profile)
    _add_episteme_control(client, profile["id"], "topic:animals", action="seek")
    created = client.post(
        "/api/future/personalized/grid-draft-jobs",
        json=_job_body(profile["id"]),
    )
    assert created.status_code == 202
    monkeypatch.setattr(grid_jobs_module, "MAX_PERSONALIZED_RESULT_BYTES", 512)
    calls = []

    def oversized_runtime(**kwargs):
        calls.append(kwargs)
        result = _admitted_runtime_result(
            kwargs["seed"],
            kwargs["options"],
            kwargs["admitted_wordlist"],
            kwargs["options"]["themes"][0],
        )
        result["runtimeNote"] = "synthetic" * 2_000
        return result

    assert process_next_grid_draft(api.app, generator=oversized_runtime)
    assert len(calls) == 1
    saved = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert saved.status_code == 200
    assert saved.json["state"] == "failed"
    assert saved.json["result"] is None
    assert saved.json["playable"] is False
    assert "size limit" in saved.json["error"]
    monkeypatch.setattr(grid_jobs_module, "MAX_GRID_RESPONSE_BYTES", 32)
    capped = client.get(
        f"/api/future/grid-draft-jobs/{created.json['id']}",
        query_string={"profileId": profile["id"]},
    )
    assert capped.status_code == 503
    assert capped.json["playable"] is False
    assert capped.cache_control.no_store
