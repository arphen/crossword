"""Tests for the Q09 traps: scratch-proof map and pinned challenger flag.

An untracked scratch file in a source tree must never enter the repository
map or block a push; and study receipts must state the challenger state of
every run, since mixed states are incomparable. Offline, no model.
"""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / ".scripts" / "generate-repo-map.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_repo_map", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_map_ignores_untracked_scratch_but_indexes_tracked_sources():
    generator = _load_generator()
    scratch = REPO_ROOT / "tools" / "scratch-q09-probe.tmp.py"
    assert not scratch.exists()
    scratch.write_text("MARKER = 1\n", encoding="utf-8")
    try:
        rels = {path.relative_to(REPO_ROOT).as_posix() for path in generator.candidates()}
        assert "tools/scratch-q09-probe.tmp.py" not in rels
        assert "conftest.py" in rels
        assert "src/crossword/private_puzzle_generation.py" in rels
    finally:
        scratch.unlink(missing_ok=True)


def test_map_falls_back_to_walk_without_git(monkeypatch):
    generator = _load_generator()
    scratch = REPO_ROOT / "tools" / "scratch-q09-probe.tmp.py"
    scratch.write_text("MARKER = 1\n", encoding="utf-8")
    try:

        def _missing(*args, **kwargs):
            raise OSError("no git here")

        monkeypatch.setattr(subprocess, "run", _missing)
        rels = {path.relative_to(REPO_ROOT).as_posix() for path in generator.candidates()}
        assert "tools/scratch-q09-probe.tmp.py" in rels
    finally:
        scratch.unlink(missing_ok=True)


def _provenance(challenge=None):
    provenance = {
        "clueQuality": {
            "diversity": {
                "familyCounts": {"definition": 2},
                "nonDefinitionCount": 0,
                "nonDefinitionFamilies": [],
            },
            "groundedClueBundle": {
                "entryCount": 2,
                "grammarBridge": {"checkedCount": 2},
            },
            "issueCount": 0,
        },
        "timingsSeconds": {},
    }
    if challenge is not None:
        provenance["semanticClueChallenge"] = {"enabled": challenge}
    return provenance


def test_study_case_pins_challenger_state():
    from crossword.clue_quality_evaluation import clue_case_from_provenance

    assert clue_case_from_provenance(_provenance(True), 1)["challengeEnabled"] is True
    assert clue_case_from_provenance(_provenance(False), 2)["challengeEnabled"] is False
    # Older provenances predate the field and stay valid without it.
    assert clue_case_from_provenance(_provenance(), 3)["challengeEnabled"] is None


def test_study_summary_flags_mixed_challenger_states():
    from crossword.clue_quality_evaluation import evaluate_clue_quality_study

    def case(seed, challenge):
        item = {
            "seed": seed,
            "entryCount": 2,
            "grammarCheckedCount": 2,
            "grammarIssueCount": 0,
            "fallbackCount": 0,
            "familyCounts": {"definition": 2},
            "nonDefinitionCount": 0,
            "nonDefinitionFamilies": [],
            "floorMet": True,
        }
        if challenge is not None:
            item["challengeEnabled"] = challenge
        return item

    mixed = evaluate_clue_quality_study(
        [case(1, True), case(2, False)], study_id="mixed-challenge"
    )
    assert mixed["summary"]["challengeStates"] == [False, True]
    assert mixed["summary"]["challengeComparable"] is False

    uniform = evaluate_clue_quality_study(
        [case(1, True), case(2, True)], study_id="uniform-challenge"
    )
    assert uniform["summary"]["challengeStates"] == [True]
    assert uniform["summary"]["challengeComparable"] is True

    legacy = evaluate_clue_quality_study([case(1, None)], study_id="legacy")
    assert legacy["summary"]["challengeStates"] == []
    assert legacy["summary"]["challengeComparable"] is True
