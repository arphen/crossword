"""Contract tests for the specimen labeling API (Q02 browser tool).

Same-origin local writes, bounded bodies, closed verdicts, and an
attestation that commits counts plus a digest — never clue text. Offline,
no model; the ledger and attestation dir are isolated per test.
"""

from __future__ import annotations

import json

from tests.test_api_isolated import api, no_network  # noqa: F401

ORIGIN = {"Origin": "http://localhost"}


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("CROSSWORD_CLUE_SPECIMEN_PATH", str(tmp_path / "ledger.local.json"))
    monkeypatch.setenv("CROSSWORD_SPECIMEN_ATTEST_DIR", str(tmp_path / "evidence"))


def test_empty_ledger_reports_missing(api, monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    assert api.app.test_client().get("/api/future/specimens").status_code == 404
    assert api.app.test_client().get("/api/future/specimens/status").status_code == 404


def test_seed_label_pair_and_status_flow(api, monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    client = api.app.test_client()

    seeded = client.post(
        "/api/future/specimens/seed", json={"corpusN": 0}, headers=ORIGIN
    )
    assert seeded.status_code == 200, seeded.json
    assert seeded.json["summary"]["records"] == 14
    assert seeded.json["summary"]["unlabeled"] == 14

    listed = client.get("/api/future/specimens")
    assert listed.status_code == 200
    assert listed.json["verdicts"] == [
        "leak",
        "tautology",
        "name-slot",
        "pseudo-pun",
        "acceptable",
        "better-of-pair",
    ]
    assert len(listed.json["records"]) == 14

    verdict = client.post(
        "/api/future/specimens/sp-tautology-shadier/verdict",
        json={"verdict": "tautology"},
        headers=ORIGIN,
    )
    assert verdict.status_code == 200, verdict.json
    assert verdict.json["summary"]["labeled"] == 1

    assert (
        client.post(
            "/api/future/specimens/sp-plain-dark/verdict",
            json={"verdict": "wrong"},
            headers=ORIGIN,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/future/specimens/no-such-id/verdict",
            json={"verdict": "leak"},
            headers=ORIGIN,
        ).status_code
        == 404
    )

    pair = client.post(
        "/api/future/specimens/pairs",
        json={"a": "sp-pair-bright-a", "b": "sp-pair-bright-b"},
        headers=ORIGIN,
    )
    assert pair.status_code == 200, pair.json
    assert pair.json["pairId"] == "pair-sp-pair-bright-a-sp-pair-bright-b"


def test_attest_refuses_partial_and_commits_closed_ledger(api, monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    client = api.app.test_client()
    client.post("/api/future/specimens/seed", json={"corpusN": 0}, headers=ORIGIN)

    partial = client.post("/api/future/specimens/attest", json={}, headers=ORIGIN)
    assert partial.status_code == 422
    assert partial.json["attested"] is False
    assert partial.json["unlabeled"] == 14

    verdicts = {
        "sp-tautology-shadier": "tautology",
        "sp-leak-shady": "leak",
        "sp-pun-auctioneer": "acceptable",
        "sp-pun-teller": "acceptable",
        "sp-pseudo-den": "pseudo-pun",
        "sp-name-singer": "name-slot",
        "sp-name-writer": "name-slot",
        "sp-fill-voyage": "acceptable",
        "sp-spoken-greeting": "acceptable",
        "sp-spoken-bare": "acceptable",
        "sp-plain-dark": "acceptable",
        "sp-plain-are": "acceptable",
        "sp-pair-bright-a": "tautology",
        "sp-pair-bright-b": "better-of-pair",
    }
    for record_id, verdict in verdicts.items():
        response = client.post(
            f"/api/future/specimens/{record_id}/verdict",
            json={"verdict": verdict},
            headers=ORIGIN,
        )
        assert response.status_code == 200, (record_id, response.json)

    done = client.post("/api/future/specimens/attest", json={}, headers=ORIGIN)
    assert done.status_code == 200, done.json
    assert done.json["attested"] is True
    assert done.json["pairs"] == 14
    assert done.json["digest"].startswith("sha256-")

    written = tmp_path / "evidence" / done.json["out"]
    assert written.is_file()
    attestation = json.loads(written.read_text(encoding="utf-8"))
    assert attestation["ledger"]["verdictCounts"]["acceptable"] == 7
    serialised = json.dumps(attestation)
    assert "more shady" not in serialised
    assert "SHADIER" not in serialised


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
