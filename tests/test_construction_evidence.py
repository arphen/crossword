"""Focused tests for the private structural construction receipt."""

from src.crossword.construction_evidence import evaluate_private_board


def _grid():
    return {
        "fill": ["CAT", "ARE", "TEN", "###", "TEN"],
        "entries": [
            {"num": 1, "dir": "A", "row": 0, "col": 0, "len": 3, "answer": "CAT"},
            {"num": 1, "dir": "D", "row": 0, "col": 1, "len": 3, "answer": "ARE"},
            {
                "num": 2,
                "dir": "A",
                "row": 4,
                "col": 0,
                "len": 3,
                "answer": "TEN",
            },
        ],
    }


def test_private_evidence_is_deterministic_and_labels_player_uncertainty():
    grid = _grid()
    clues = [
        {"id": "1A", "needsFoothold": True},
        {"id": "1D", "needsFoothold": False},
        {"id": "2A", "needsFoothold": True},
    ]

    first = evaluate_private_board(grid, clues, source_digest="sha256:" + "a" * 64)
    second = evaluate_private_board(grid, clues, source_digest="sha256:" + "a" * 64)

    assert first == second
    assert first["status"] == "measured"
    assert first["entryCount"] == 3
    assert first["crossingCellCount"] == 1
    assert first["crossingEdgeCount"] == 1
    assert first["weakWithoutCrossing"] == ["2A"]
    assert first["isolatedEntries"] == ["2A"]
    assert first["footholdSeedPlan"]["version"] == "private-foothold-seed-plan-v1"
    assert first["footholdSeedPlan"]["targetCount"] == 2
    assert first["footholdSeedPlan"]["seededTargetCount"] == 1
    seed = next(
        item
        for item in first["footholdSeedPlan"]["entries"]
        if item["targetEntryId"] == "1A"
    )
    assert seed["status"] == "candidate-nonweak-neighbor"
    assert seed["supportEntryId"] == "1D"
    assert seed["crossingCells"] == [{"row": 0, "col": 1}]
    assert seed["supportSurfaceRisk"] == "unflagged-or-unavailable"
    unseeded = next(
        item
        for item in first["footholdSeedPlan"]["entries"]
        if item["targetEntryId"] == "2A"
    )
    assert unseeded["status"] == "unseeded-no-crossing-neighbor"
    assert first["uncertainty"] == {
        "playerSupport": "unmeasured",
        "semanticFairness": "unverified",
        "humanPlaytest": "not-run",
        "siblingEvaluator": "not-invoked",
    }
    assert first["siblingEvaluator"]["status"] == "not-invoked"
    assert "weak-entry-without-crossing" in first["flags"]
    assert first["boardDigest"].startswith("sha256:")


def test_private_evidence_reports_invalid_topology_without_failing_generation():
    report = evaluate_private_board(
        {
            "fill": ["AA"],
            "entries": [
                {"num": 1, "dir": "A", "row": 0, "col": 0, "len": 2},
                {"num": 1, "dir": "A", "row": 0, "col": 0, "len": 2},
                {"num": 1, "dir": "D", "row": 0, "col": 0, "len": 2},
            ],
        }
    )

    assert report["status"] == "invalid-topology"
    assert "duplicate-entry:1A" in report["errors"]
    assert "topology-validation-error" in report["flags"]
    assert report["uncertainty"]["playerSupport"] == "unmeasured"


def test_foothold_seed_prefers_an_unflagged_support_surface():
    report = evaluate_private_board(
        {
            "fill": ["ABC", "AB#"],
            "entries": [
                {"num": 1, "dir": "A", "row": 0, "col": 0, "len": 3},
                {"num": 1, "dir": "D", "row": 0, "col": 0, "len": 2},
                {"num": 2, "dir": "D", "row": 0, "col": 1, "len": 2},
            ],
        },
        [
            {"id": "1A", "needsFoothold": True},
            {"id": "1D", "needsFoothold": False},
            {"id": "2D", "needsFoothold": False},
        ],
        clue_quality={
            "grounding": {
                "entries": [
                    {"id": "1D", "riskFlags": ["unsupported-factual-surface"]},
                    {"id": "2D", "riskFlags": []},
                ]
            }
        },
    )

    seed = report["footholdSeedPlan"]["entries"][0]
    assert seed["targetEntryId"] == "1A"
    assert seed["supportEntryId"] == "2D"
    assert seed["supportSurfaceRisk"] == "unflagged-or-unavailable"


def test_clue_text_is_not_in_the_board_digest_or_report():
    grid = _grid()
    report = evaluate_private_board(
        grid,
        [{"id": "1A", "needsFoothold": False, "clue": "A private clue"}],
    )

    assert "clue" not in report
    assert "A private clue" not in report["boardDigest"]
