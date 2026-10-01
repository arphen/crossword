import os
import sys

import pytest

# Add the src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))


@pytest.fixture(autouse=True)
def _isolated_clue_corpus(tmp_path, monkeypatch):
    """Keep synthetic test generations out of the operator's local corpus.

    Several suites call the real ``_generate`` with fixture models; without
    this redirect their boards would append to the answer-bearing corpus the
    Q05 census reads, polluting the denominator with seed-42 duplicates.
    """
    monkeypatch.setenv(
        "CROSSWORD_CLUE_CORPUS_PATH", str(tmp_path / "test-clue-corpus.local.json")
    )


def pytest_collection_modifyitems(config, items):
    """Keep provider-backed diagnostics opt-in even outside Make targets."""

    del config  # pytest passes the config for hook compatibility.
    if os.environ.get("CROSSWORD_ALLOW_LIVE_PROVIDER") == "1":
        return

    skip_live = pytest.mark.skip(
        reason="live provider tests require CROSSWORD_ALLOW_LIVE_PROVIDER=1"
    )
    for item in items:
        if "live_provider" in item.keywords:
            item.add_marker(skip_live)
