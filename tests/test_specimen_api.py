"""Contract tests for the specimen labeling API (Q02 browser tool).

Same-origin blind judging with spec reference read-only: seed builds
reference plus the blind queue, verdicts land on blind records only,
attest requires a closed blind queue and commits counts plus a digest —
never clue text. Offline, no model; ledger, harvest, and attestation dir
are isolated per test.
"""

from __future__ import annotations

import json

from tests.test_api_isolated import api, no_network  # noqa: F401

ORIGIN = {"Origin": "http://localhost"}


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("CROSSWORD_CLUE_SPECIMEN_PATH", str(tmp_path / "ledger.local.json"))
    monkeypatch.setenv("CROSSWORD_SPECIMEN_ATTEST_DIR", str(tmp_path / "evidence"))
    real = tmp_path / "real.local.json"
    real.write_text(
        json.dumps(
            {
                "version": "private-clue-real-v1",
                "records": [
                    {"answer": "MOSS", "clue": "Green stuff", "arm": "candidate"},
                    {"answer": "MOSS", "clue": "Lawn cover", "arm": "single"},
                    {"answer": "DARK", "clue": "Without light", "arm": "candidate"},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CROSSWORD_CLUE_REAL_PATH", str(real))


def test_empty_ledger_reports_missing(api, monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    assert api.app.test_client().get("/api/future/specimens").status_code == 404
    assert api.app.test_client().get("/api/future/specimens/status").status_code == 404


def test_seed_builds_reference_plus_blind_queue(api, monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    client = api.app.test_client()

    seeded = client.post(
        "/api/future/specimens/seed", json={"corpusN": 0}, headers=ORIGIN
    )
    assert seeded.status_code == 200, seeded.json
    summary = seeded.json["summary"]
    assert summary["records"] == 14 + 3
    assert summary["reference"] == 14
    assert summary["blind"] == 3
    assert summary["blindUnlabeled"] == 3
    assert summary["seed"]["harvestPairs"] == 1

    listed = client.get("/api/future/specimens")
    assert listed.status_code == 200
    records = {record["id"]: record for record in listed.json["records"]}
    assert records["sp-tautology-shadier"]["origin"] == "spec"
    assert records["sp-tautology-shadier"]["verdict"] == "tautology"
    blind = [record for record in records.values() if record["origin"] == "blind"]
    assert len(blind) == 3
    assert all(record["verdict"] is None for record in blind)


def test_reference_records_reject_verdicts_and_pairs(api, monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    client = api.app.test_client()
    client.post("/api/future/specimens/seed", json={"corpusN": 0}, headers=ORIGIN)

    assert (
        client.post(
            "/api/future/specimens/sp-plain-dark/verdict",
            json={"verdict": "acceptable"},
            headers=ORIGIN,
        ).status_code
        == 422
    )
    listed = client.get("/api/future/specimens").json["records"]
    blind_id = next(record["id"] for record in listed if record["origin"] == "blind")
    assert (
        client.post(
            "/api/future/specimens/pairs",
            json={"a": "sp-pair-bright-a", "b": blind_id},
            headers=ORIGIN,
        ).status_code
        == 422
    )


def test_judge_blind_queue_then_attest(api, monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    client = api.app.test_client()
    client.post("/api/future/specimens/seed", json={"corpusN": 0}, headers=ORIGIN)

    listed = client.get("/api/future/specimens").json["records"]
    blind = [record for record in listed if record["origin"] == "blind"]
    pair_members = [
        record["id"]
        for record in blind
        if (record.get("pairId") or "").startswith("pair-real-")
    ]
    assert len(pair_members) == 2
    single = next(record["id"] for record in blind if record["id"] not in pair_members)

    partial = client.post("/api/future/specimens/attest", json={}, headers=ORIGIN)
    assert partial.status_code == 422
    assert partial.json["attested"] is False
    assert partial.json["unlabeled"] == 3

    verdicts = {pair_members[0]: "acceptable", pair_members[1]: "better-of-pair", single: "acceptable"}
    for record_id, verdict in verdicts.items():
        response = client.post(
            f"/api/future/specimens/{record_id}/verdict",
            json={"verdict": verdict},
            headers=ORIGIN,
        )
        assert response.status_code == 200, (record_id, response.json)
    assert response.json["summary"]["blindUnlabeled"] == 0

    done = client.post("/api/future/specimens/attest", json={}, headers=ORIGIN)
    assert done.status_code == 200, done.json
    assert done.json["attested"] is True
    assert done.json["digest"].startswith("sha256-")

    written = tmp_path / "evidence" / done.json["out"]
    assert written.is_file()
    attestation = json.loads(written.read_text(encoding="utf-8"))
    assert attestation["ledger"]["origins"]["blind"] == 3
    serialised = json.dumps(attestation)
    assert "Green stuff" not in serialised
    assert "MOSS" not in serialised


def test_attest_refuses_reference_only_ledger(api, monkeypatch, tmp_path):
    monkeypatch.setenv("CROSSWORD_CLUE_SPECIMEN_PATH", str(tmp_path / "ledger.local.json"))
    monkeypatch.setenv("CROSSWORD_SPECIMEN_ATTEST_DIR", str(tmp_path / "evidence"))
    monkeypatch.setenv("CROSSWORD_CLUE_REAL_PATH", str(tmp_path / "absent.local.json"))
    client = api.app.test_client()
    client.post("/api/future/specimens/seed", json={"corpusN": 0}, headers=ORIGIN)
    refused = client.post("/api/future/specimens/attest", json={}, headers=ORIGIN)
    assert refused.status_code == 422
    assert refused.json["attested"] is False


def test_cross_origin_writes_are_rejected(api, monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    evil = {"Origin": "https://example.invalid"}
    client = api.app.test_client()
    assert client.post("/api/future/specimens/seed", json={}, headers=evil).status_code == 403
    assert (
        client.post(
            "/api/future/specimens/sp-plain-dark/verdict",
            json={"verdict": "leak"},
            headers=evil,
        ).status_code
        == 403
    )
    assert client.post("/api/future/specimens/attest", json={}, headers=evil).status_code == 403
