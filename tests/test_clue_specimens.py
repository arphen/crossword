"""Tests for the closed specimen ledger and label tool (Q02).

The ledger is answer-bearing and local-only; only counts plus a digest are
committed. Verdicts are closed, pairs link exactly two records, and the
winner of a pair is the only better-of-pair. Offline, no model.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from crossword.clue_specimens import (
    SPECIMEN_VERSION,
    VERDICTS,
    agreement_report,
    ledger_attestation,
    ledger_path,
    load_ledger,
    make_record,
    save_ledger,
    validate_ledger,
)


def test_verdicts_are_closed():
    assert VERDICTS == (
        "leak",
        "tautology",
        "name-slot",
        "pseudo-pun",
        "acceptable",
        "better-of-pair",
    )


def test_records_start_unlabeled():
    record = make_record("sp-1", "SHADIER", "more shady")
    assert record["verdict"] is None
    assert record["labeledAt"] is None
    assert record["source"] == "hand-listed"


def test_ledger_rejects_open_verdicts_duplicates_and_empties():
    problems = validate_ledger(
        [
            make_record("a", "X", "y"),
            make_record("a", "X", "y"),
            {"id": "b", "answer": "", "clue": "", "verdict": "fine", "pairId": None},
            {"id": "c", "answer": "X", "clue": "y", "verdict": "better-of-pair", "pairId": None},
        ]
    )
    assert any("duplicate id" in problem for problem in problems)
    assert any("outside" in problem for problem in problems)
    assert any("no pair" in problem for problem in problems)
    assert any("needs an answer" in problem for problem in problems)


def test_pairs_link_exactly_two_with_at_most_one_winner():
    lone = make_record("a", "X", "y", pair_id="p1")
    assert any("exactly 2" in problem for problem in validate_ledger([lone]))
    first = make_record("a", "X", "y", pair_id="p1")
    second = make_record("b", "X", "z", pair_id="p1")
    first["verdict"] = "better-of-pair"
    assert validate_ledger([first, second]) == []
    second["verdict"] = "better-of-pair"
    assert any("at most 1" in problem for problem in validate_ledger([first, second]))


def test_missing_ledger_is_empty_not_an_error(tmp_path):
    assert load_ledger(tmp_path / "absent.json") == {
        "version": SPECIMEN_VERSION,
        "records": [],
        "present": False,
    }


def test_attestation_commits_counts_and_digest_only(tmp_path):
    target = tmp_path / "ledger.local.json"
    first = make_record("a", "SHADIER", "more shady")
    first["verdict"] = "tautology"
    second = make_record("b", "DARK", "Without light")
    second["verdict"] = "acceptable"
    save_ledger([first, second, make_record("c", "X", "y")], target)
    attestation = ledger_attestation(load_ledger(target)["records"])
    assert attestation["pairs"] == 3
    assert attestation["labeled"] == 2
    assert attestation["unlabeled"] == 1
    assert attestation["verdictCounts"] == {"acceptable": 1, "tautology": 1}
    assert attestation["digest"].startswith("sha256-")
    serialised = json.dumps(attestation, sort_keys=True)
    assert "more shady" not in serialised
    assert "SHADIER" not in serialised


def test_env_override_selects_ledger_path(tmp_path, monkeypatch):
    target = tmp_path / "override.local.json"
    monkeypatch.setenv("CROSSWORD_CLUE_SPECIMEN_PATH", str(target))
    assert ledger_path() == target


def test_agreement_report_scores_claims_against_stable_ids():
    first = make_record("a", "SHADIER", "more shady")
    first["verdict"] = "tautology"
    second = make_record("b", "DARK", "Without light")
    second["verdict"] = "acceptable"
    report = agreement_report(
        [first, second], {"a": "tautology", "b": "pseudo-pun", "zzz": "leak"}
    )
    assert report["scored"] == 2
    assert report["agreed"] == 1
    assert report["disagreed"] == 1
    assert report["unknownIds"] == 1
    assert report["agreementRate"] == 0.5
    assert report["disagreements"] == [
        {"id": "b", "expected": "acceptable", "claimed": "pseudo-pun"}
    ]


def _script():
    return Path(__file__).resolve().parents[1] / "scripts" / "private-clue-specimen-label.py"


def _env(ledger):
    return dict(os.environ, CROSSWORD_CLUE_SPECIMEN_PATH=str(ledger))


def test_label_cli_workflow_seed_status_attest(tmp_path, monkeypatch):
    ledger = tmp_path / "ledger.local.json"
    env = _env(ledger)

    def run(*args):
        completed = subprocess.run(
            [sys.executable, str(_script()), *args],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        assert completed.returncode == 0, completed.stderr
        return json.loads(completed.stdout)

    seeded = run("seed", "--corpus-n", "0")
    assert seeded["records"] == seeded["handListed"] > 10
    specimens = {record["id"]: record for record in load_ledger(ledger)["records"]}
    assert specimens["sp-tautology-shadier"]["verdict"] is None
    assert specimens["sp-pair-bright-a"]["pairId"] == specimens["sp-pair-bright-b"]["pairId"]

    run("label", "--id", "sp-tautology-shadier", "--verdict", "tautology")
    run("label", "--id", "sp-pair-bright-b", "--verdict", "better-of-pair")
    status = run("status")
    assert status["unlabeled"] == status["records"] - 2

    with pytest.raises(AssertionError):
        run("label", "--id", "sp-plain-dark", "--verdict", "wrong")


def test_attest_requires_a_closed_ledger(tmp_path, monkeypatch):
    ledger = tmp_path / "ledger.local.json"
    env = _env(ledger)
    subprocess.run([sys.executable, str(_script()), "seed", "--corpus-n", "0"], check=True, env=env, timeout=60)
    partial = subprocess.run(
        [sys.executable, str(_script()), "attest", "--out", str(tmp_path / "att.json")],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert partial.returncode == 1
    assert "unlabeled" in partial.stdout
