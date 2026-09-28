"""Separately managed local worker for durable full-size grid-draft jobs.

Run with ``python -m src.crossword.future_worker`` from the product checkout.
The worker uses only the local Node/xfill runtime; it never calls a hosted model.
"""

import argparse
import signal
from threading import Event, Thread
import time

from .app import app
from .future_grid_jobs import process_next_grid_draft
from .runtime_readiness import clear_worker_heartbeat, write_worker_heartbeat


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once", action="store_true", help="process at most one queued job and exit"
    )
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    options = parser.parse_args()
    if not 0.1 <= options.poll_seconds <= 60:
        parser.error("--poll-seconds must be between 0.1 and 60")
    shutdown = Event()
    heartbeat_state = {"value": "idle"}
    heartbeat_stop = Event()
    previous_handlers = {}

    def request_shutdown(_signum, _frame):
        shutdown.set()

    for signal_number in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signal_number] = signal.signal(
            signal_number, request_shutdown
        )

    def refresh_heartbeat():
        # The grid worker can spend minutes in Ollama or native xfill. Keep a
        # tiny local heartbeat independent of those calls so readiness can
        # distinguish a live worker from a stale lease without touching jobs.
        with app.app_context():
            while not heartbeat_stop.is_set():
                write_worker_heartbeat(state=heartbeat_state["value"])
                heartbeat_stop.wait(2.0)

    heartbeat_thread = Thread(
        target=refresh_heartbeat, name="future-worker-heartbeat", daemon=True
    )
    heartbeat_thread.start()
    try:
        while not shutdown.is_set():
            heartbeat_state["value"] = "working"
            processed = process_next_grid_draft(
                app,
                shutdown_requested=shutdown.is_set,
            )
            heartbeat_state["value"] = "idle"
            if options.once:
                return 0
            if not processed:
                shutdown.wait(options.poll_seconds)
        return 0
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=3.0)
        with app.app_context():
            clear_worker_heartbeat()
        for signal_number, handler in previous_handlers.items():
            signal.signal(signal_number, handler)


if __name__ == "__main__":
    raise SystemExit(main())
