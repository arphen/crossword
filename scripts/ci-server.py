"""Local-only E2E backend: disposable SQLite and original synthetic puzzles.

Never import the production app before setting CROSSWORD_DATABASE_URI: it creates
its tables at import time. This harness is not a production entry point.
"""

from __future__ import annotations

import atexit
from datetime import datetime, timedelta
import os
from pathlib import Path
import signal
import socket
import sys
import tempfile

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def deny_outbound(*args, **kwargs):
    raise AssertionError("Live outbound network is disabled by the CI harness")


def synthetic_puzzle(date: str) -> dict:
    # An original 3x3 word square, not copied from any puzzle/provider.
    rows = ("CAT", "ARE", "TEN")
    entries = []
    for index, word in enumerate(rows):
        for direction in ("across", "down"):
            entries.append(
                {
                    "clue_number": (1 if index == 0 else index + 3)
                    if direction == "across"
                    else index + 1,
                    "clue_text": f"Synthetic {direction} row {index + 1}: {word}",
                    "direction": direction,
                    "start_x": 0 if direction == "across" else index,
                    "start_y": index if direction == "across" else 0,
                    "characters": [{"letters": letter} for letter in word],
                }
            )
    return {
        "metadata": {
            "date": date,
            "title": "Synthetic CI word square",
            "authors": ["CI fixture author"],
            "width": 3,
            "height": 3,
        },
        "entries": entries,
    }


def main() -> None:
    temporary = tempfile.TemporaryDirectory(prefix="crossword-e2e-")
    atexit.register(temporary.cleanup)
    database_path = Path(temporary.name) / "completed.sqlite"
    # Deliberately override any inherited URI; this process must never use real data.
    os.environ["CROSSWORD_DATABASE_URI"] = f"sqlite:///{database_path}"
    requests.sessions.Session.request = deny_outbound
    socket.socket.connect = deny_outbound
    socket.socket.connect_ex = deny_outbound
    socket.create_connection = deny_outbound

    from flask import jsonify
    from sqlalchemy import text
    from src.crossword.app import app, db, CompletedPuzzle, socketio

    app.config.update(TESTING=True)

    @app.get("/api/health")
    def health():
        # Read the real table, not just a static ready flag or SELECT 1.
        db.session.execute(text("SELECT count(*) FROM completed_puzzles")).scalar_one()
        return jsonify(status="ok", database="temporary-sqlite", fixture="synthetic")

    def by_date(date):
        try:
            datetime.strptime(date, "%y%m%d")
        except ValueError:
            return jsonify(error="Invalid fixture date"), 400
        return jsonify(synthetic_puzzle(date))

    def random_puzzle(weekday):
        days = (
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        )
        if weekday.lower() not in days:
            return jsonify(error="Invalid weekday"), 400
        date = datetime(2024, 1, 1) + timedelta(days=days.index(weekday.lower()))
        # Stable initial puzzle, then next week after completion so the UI can
        # load a new unsolved puzzle without retries or random provider access.
        while CompletedPuzzle.query.filter_by(
            puzzle_date=date.strftime("%y%m%d")
        ).first():
            date += timedelta(days=7)
        return jsonify(synthetic_puzzle(date.strftime("%y%m%d")))

    app.view_functions["get_random_crossword"] = random_puzzle
    app.view_functions["get_crossword_by_date"] = by_date
    app.view_functions["get_crossword"] = by_date

    def stop(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    try:
        print(
            "CI backend: temporary SQLite, synthetic puzzles, outbound network blocked",
            flush=True,
        )
        socketio.run(
            app,
            host="127.0.0.1",
            port=int(os.environ.get("CROSSWORD_E2E_BACKEND_PORT", "5002")),
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True,
        )
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        temporary.cleanup()


if __name__ == "__main__":
    main()
