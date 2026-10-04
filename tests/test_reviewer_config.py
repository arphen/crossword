"""Flask wiring tests for the private, host-configured reviewer credentials."""

from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path


def test_reviewer_credentials_load_into_private_config_without_leaking(
    tmp_path, monkeypatch, caplog
):
    token = "synthetic-reviewer-config-token-0123456789"
    reviewer_id = "synthetic-local-reviewer"
    additional_token = "synthetic-additional-reviewer-token-0123456789"
    reviewer_roster = json.dumps(
        [{"reviewerId": "synthetic-blind-rater", "token": additional_token}]
    )
    database_path = tmp_path / "reviewer-config.sqlite"
    monkeypatch.setenv("CROSSWORD_DATABASE_URI", f"sqlite:///{database_path}")
    monkeypatch.setenv("CROSSWORD_REVIEWER_TOKEN", token)
    monkeypatch.setenv("CROSSWORD_REVIEWER_ID", reviewer_id)
    monkeypatch.setenv("CROSSWORD_ADDITIONAL_REVIEWERS_JSON", reviewer_roster)

    app_path = Path(__file__).resolve().parents[1] / "src/crossword/app.py"
    spec = importlib.util.spec_from_file_location(
        "src.crossword._isolated_reviewer_config", app_path
    )
    module = importlib.util.module_from_spec(spec)
    with caplog.at_level(logging.DEBUG):
        spec.loader.exec_module(module)

    assert module.app.config["CROSSWORD_REVIEWER_TOKEN"] == token
    assert module.app.config["CROSSWORD_REVIEWER_ID"] == reviewer_id
    assert module.app.config["CROSSWORD_ADDITIONAL_REVIEWERS_JSON"] == reviewer_roster

    response = module.app.test_client().get("/api/completed_puzzles")
    assert response.status_code == 200
    response_text = response.get_data(as_text=True)
    assert token not in response_text
    assert additional_token not in response_text
    assert reviewer_id not in response_text
    assert all(token not in record.getMessage() for record in caplog.records)
    assert all(additional_token not in record.getMessage() for record in caplog.records)
    assert all(reviewer_id not in record.getMessage() for record in caplog.records)

    with module.app.app_context():
        module.db.session.remove()
        module.db.engine.dispose()
