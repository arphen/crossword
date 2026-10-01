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
    assert record["origin"] == "blind"


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
    assert attestation["blindUnlabeled"] == 1
    assert attestation["origins"] == {"blind": 2}
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
    assert report["byOrigin"] == {
        "blind": {"scored": 2, "agreed": 1, "disagreed": 1, "agreementRate": 0.5}
    }
    assert report["disagreements"] == [
        {"id": "b", "expected": "acceptable", "claimed": "pseudo-pun"}
    ]


def test_agreement_report_splits_spec_calibration_from_blind():
    spec = make_record("s", "SHADIER", "more shady", origin="spec", verdict="tautology")
    blind = make_record("q", "DARK", "Without light")
    blind["verdict"] = "acceptable"
    report = agreement_report(
        [spec, blind], {"s": "tautology", "q": "pseudo-pun"}
    )
    assert report["byOrigin"]["spec"] == {
        "scored": 1,
        "agreed": 1,
        "disagreed": 0,
        "agreementRate": 1.0,
    }
    assert report["byOrigin"]["blind"] == {
        "scored": 1,
        "agreed": 0,
        "disagreed": 1,
        "agreementRate": 0.0,
    }


def test_seed_marks_spec_reference_and_skips_scaffold():
    from crossword.clue_specimens import is_scaffold_surface, seed_records

    assert is_scaffold_surface("Entry supported by its crossings (3 letters)")
    assert not is_scaffold_surface("Without light")
    records, report = seed_records(
        10,
        [
            {"answer": "X", "clue": "Entry supported by its crossings (1 letters)", "seed": 1, "id": "1"},
            {"answer": "DARK", "clue": "Without light", "seed": 1, "id": "2"},
        ],
        [
            {"answer": "MOSS", "clue": "Green stuff", "arm": "candidate", "weekday": "monday", "modelTag": "t"},
            {"answer": "MOSS", "clue": "Green stuff", "arm": "single", "weekday": "monday", "modelTag": "t"},
            {"answer": "MOSS", "clue": "Lawn cover", "arm": "single", "weekday": "monday", "modelTag": "t"},
        ],
        10,
    )
    assert report["reference"] == 14
    assert report["scaffoldSkipped"] == 1
    assert report["corpusSampled"] == 1
    assert report["harvestPairs"] == 1
    assert report["blind"] == 3
    reference = {record["id"]: record for record in records if record["origin"] == "spec"}
    assert reference["sp-tautology-shadier"]["verdict"] == "tautology"
    assert reference["sp-pair-bright-b"]["verdict"] == "better-of-pair"
    assert all(record["verdict"] is None for record in records if record["origin"] == "blind")
    assert "Entry supported" not in json.dumps(records)


def _script():
    return Path(__file__).resolve().parents[1] / "scripts" / "private-clue-specimen-label.py"


def _env(ledger, real=None):
    env = dict(os.environ, CROSSWORD_CLUE_SPECIMEN_PATH=str(ledger))
    # Isolate the real-surface harvest: the operator file stays out of tests.
    env["CROSSWORD_CLUE_REAL_PATH"] = str(
        real if real is not None else (Path(ledger).parent / "absent-real.local.json")
    )
    return env


def test_label_cli_workflow_seed_status_attest(tmp_path, monkeypatch):
    ledger = tmp_path / "ledger.local.json"
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
    env = _env(ledger, real)

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
    assert seeded["records"] == 14 + 3
    assert seeded["reference"] == 14
    assert seeded["blind"] == 3
    assert seeded["harvestPairs"] == 1
    specimens = {record["id"]: record for record in load_ledger(ledger)["records"]}
    assert specimens["sp-tautology-shadier"]["verdict"] == "tautology"
    assert specimens["sp-tautology-shadier"]["origin"] == "spec"
    assert specimens["sp-pair-bright-a"]["pairId"] == specimens["sp-pair-bright-b"]["pairId"]

    with pytest.raises(AssertionError):
        run("label", "--id", "sp-plain-dark", "--verdict", "acceptable")

    blind_ids = [rid for rid, rec in specimens.items() if rec["origin"] == "blind"]
    assert len(blind_ids) == 3
    pair_members = [
        rid for rid in blind_ids if (specimens[rid].get("pairId") or "").startswith("pair-real-")
    ]
    assert len(pair_members) == 2
    run("label", "--id", pair_members[0], "--verdict", "acceptable")
    run("label", "--id", pair_members[1], "--verdict", "better-of-pair")
    status = run("status")
    assert status["blindUnlabeled"] == 1
    assert len(status["unlabeledIds"]) == 1

    with pytest.raises(AssertionError):
        run("label", "--id", blind_ids[0], "--verdict", "wrong")

    partial = subprocess.run(
        [sys.executable, str(_script()), "attest", "--out", str(tmp_path / "att.json")],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert partial.returncode == 1
    assert json.loads(partial.stdout)["unlabeled"] == 1

    single = next(rid for rid in blind_ids if rid not in pair_members)
    run("label", "--id", single, "--verdict", "acceptable")
    done = subprocess.run(
        [sys.executable, str(_script()), "attest", "--out", str(tmp_path / "att.json")],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert done.returncode == 0, done.stderr
    attestation = json.loads((tmp_path / "att.json").read_text(encoding="utf-8"))
    assert attestation["ledger"]["blindUnlabeled"] == 0
    assert attestation["ledger"]["origins"]["blind"] == 3
    assert "Green stuff" not in json.dumps(attestation)


def test_attest_requires_a_closed_blind_queue(tmp_path, monkeypatch):
    ledger = tmp_path / "ledger.local.json"
    env = _env(ledger)
    subprocess.run(
        [sys.executable, str(_script()), "seed", "--corpus-n", "0"],
        check=True,
        env=env,
        timeout=60,
    )
    vacant = subprocess.run(
        [sys.executable, str(_script()), "attest", "--out", str(tmp_path / "att.json")],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert vacant.returncode == 1
    assert "no blind queue" in vacant.stdout
