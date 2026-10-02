"""Small authored samples that keep the private solver playable offline.

The sample lane is deliberately separate from local model generation.  It is
not a source for the personalized lexicon and it never claims to reflect the
player's episteme; it is a reviewed, answer-bearing warm-up with an immutable
host manifest so the ordinary future journal can still record a solve.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from .future_puzzles import register_legacy_puzzle
from .models import Character, Crossword, CrosswordMetadata, Entry


reviewed_samples_api = Blueprint("reviewed_samples_api", __name__)

REVIEWED_SAMPLE_SOURCE = "reviewed-sample"
REVIEWED_SAMPLE_VERSION = "reviewed-sample-v1"
SATOR_SAMPLE_ID = "sator-square-v1"
_WEEKDAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}

# A hand-authored word square makes the fallback self-contained: every clue
# has a checked crossing and there is no external provider or model dependency.
_WORDS = ("SATOR", "AREPO", "TENET", "OPERA", "ROTAS")
_ACROSS_NUMBERS = (1, 6, 7, 8, 9)
# Every clue must stand on its own route: the old set described each line
# by its position in the square ("A line in the five-line square"), which
# is solvable only by solvers who already know the whole square. AREPO has
# no English meaning, so both its clues say so openly and let the crossings
# carry it — the one deliberate obscurity, flagged, not hidden.
_ACROSS_CLUES = (
    "Sower, in Latin",
    "Enigmatic second word of the Sator Square",
    "Principle",
    "Carmen, for one",
    "Wheels, in Latin",
)
_DOWN_CLUES = (
    "Planter",
    "Mysterious name in the Latin word square",
    "Creed",
    "La Scala offering",
    "Turns",
)


def _sample_crossword() -> Crossword:
    entries: list[Entry] = []
    for row, (number, answer, clue) in enumerate(
        zip(_ACROSS_NUMBERS, _WORDS, _ACROSS_CLUES, strict=True)
    ):
        entries.append(
            Entry(
                clue_number=number,
                clue_text=clue,
                direction="across",
                start_x=0,
                start_y=row,
                characters=[Character(letters=letter) for letter in answer],
            )
        )
    for column, (answer, clue) in enumerate(zip(_WORDS, _DOWN_CLUES, strict=True)):
        entries.append(
            Entry(
                clue_number=column + 1,
                clue_text=clue,
                direction="down",
                start_x=column,
                start_y=0,
                characters=[Character(letters=letter) for letter in answer],
            )
        )
    return Crossword(
        metadata=CrosswordMetadata(
            date="260928",
            title="The First Square",
            authors=["Crossword Workshop"],
            width=5,
            height=5,
            notepad="A small authored sample for learning the shape of the future solver.",
        ),
        entries=entries,
    )


def _sample_payload(weekday: str) -> dict:
    crossword = _sample_crossword()
    manifest = register_legacy_puzzle(crossword)
    return {
        **crossword.model_dump(exclude={"across_entries", "down_entries"}),
        "puzzleManifest": manifest,
        "provenance": {
            "source": REVIEWED_SAMPLE_SOURCE,
            "version": REVIEWED_SAMPLE_VERSION,
            "sampleId": SATOR_SAMPLE_ID,
            "weekday": weekday,
            "seed": 0,
            "experimental": False,
            "review": {
                "status": "reviewed-authored",
                "license": "CC0-1.0",
                "answerSource": "hand-authored-word-square",
                "semanticStatus": "authored-sample",
            },
        },
    }


@reviewed_samples_api.get("/api/future/reviewed-samples/<sample_id>")
def reviewed_sample(sample_id: str):
    """Return one immutable, answer-bearing warm-up for the future solver."""
    if sample_id != SATOR_SAMPLE_ID:
        return jsonify({"error": "Reviewed sample not found"}), 404
    weekday = request.args.get("weekday", "monday").lower()
    if weekday not in _WEEKDAYS:
        return jsonify({"error": "Invalid weekday"}), 400
    response = jsonify(_sample_payload(weekday))
    response.headers["Cache-Control"] = "no-store"
    return response
