"""Witness-based clue family admission (Q04).

A clue does not have a family; it has a witness. ``_clue_family_observation``
in ``private_puzzle_generation.py`` assigns a *claimed* family from visible
punctuation — a trailing ``?`` yields ``pun`` no matter what the words say.
This module checks whether the surface actually carries the witness the
claimed family requires:

- ``pun``: the surface ends in ``?`` AND a ledger pivot with two distinct
  senses appears as a token AND the pivot is not the answer itself. A bare
  ``?`` yields ``pseudo-pun``, never ``pun``.
- ``fill-blank``: a marked blank (``___``, ``...``/``…``). The mark is the
  witness, nearly the surface itself.
- ``spoken-equivalent``: a quoted utterance AND its spoken label
  (``(Spoken equivalent)``, ``(utterance)``, ``(said aloud)``). A quote
  without a label is a definition that says so.
- ``nonverbal-expression``: the bracket span. The brackets are the witness.
- ``metalinguistic``: the abbreviation indicator. The indicator is the witness.
- ``factual-relation``: the language indicator, or a caller-attested
  fact-relation pattern match. Without either, a definition.
- ``definition``: needs no witness; it is what a clue is when no witness
  exists, and it says so.

Where no witness exists the witnessed family is ``definition`` (or
``pseudo-pun`` for a bare ``?``); receipts report claimed and witnessed
counts side by side and the gap is reported, never reconciled by assumption.

Sense inventory: ``vendor/xfill/data/xwordlist.dict`` is a wordlist, not a
sense inventory, and the OEWN import staged under E04 is not admitted, so v1
uses the curated homograph ledger below and labels every pun verdict
``sense-source: curated-v1`` rather than leaving the gap silent.
"""

from __future__ import annotations

import re

WITNESS_VERSION = "private-clue-witness-v1"
SENSE_SOURCE_ID = "curated-v1"

# Curated homograph ledger: pivot word plus two distinct senses, hand-listed
# from ordinary English. Each entry is (PIVOT, sense A, sense B). This is a
# sense inventory of last resort: small, explicit, and labeled as such.
HOMOGRAPH_LEDGER = (
    ("LOT", "a large number or quantity", "an item offered for sale at auction"),
    ("BRANCH", "a limb of a tree", "a local office of a bank"),
    ("SPRING", "the season after winter", "a coiled wire that bounces back"),
    ("FALL", "the autumn season", "to drop suddenly"),
    ("BREAK", "to fracture", "a rest period"),
    ("STRIKE", "to hit", "a work stoppage"),
    ("CHARGE", "a price asked", "to rush at"),
    ("NOVEL", "new and unusual", "a long fiction book"),
    ("MINOR", "a youth under age", "lesser in importance"),
    ("MAJOR", "a military rank", "significant in scale"),
    ("FAIR", "just and even", "a traveling carnival"),
    ("FINE", "a monetary penalty", "of high quality"),
    ("GRAVE", "serious in manner", "a burial place"),
    ("LETTER", "a character of the alphabet", "a mailed message"),
    ("NOTE", "a brief written record", "a musical tone"),
    ("PRESENT", "a gift", "to introduce formally"),
    ("CURRENT", "a flow of water or air", "belonging to now"),
    ("RULER", "a measuring stick", "a monarch"),
    ("STICK", "to adhere", "a thin piece of wood"),
    ("FAN", "an admirer", "a device that moves air"),
    ("MINT", "a cool flavor", "a factory that makes coins"),
    ("BILL", "an invoice to pay", "a proposed law"),
    ("CHANGE", "to alter", "coins returned after payment"),
    ("CHECK", "to verify", "a written bank draft"),
    ("DRAFT", "a preliminary version", "compulsory military service"),
    ("COUNTER", "to oppose", "a shop surface"),
    ("TENDER", "to offer formally", "gentle and soft"),
    ("PATIENT", "willing to wait", "a person under medical care"),
    ("CONTENT", "satisfied", "the subject matter"),
    ("OBJECT", "to protest", "a physical thing"),
    ("SUBJECT", "a topic of study", "to expose to something"),
    ("CONSOLE", "to comfort", "a control panel"),
    ("DESERT", "to abandon", "an arid wasteland"),
    ("RECORD", "to capture sound or video", "the best performance so far"),
    ("PERMIT", "to allow", "an official license"),
    ("REBEL", "to defy authority", "an insurgent"),
    ("PLANE", "an aircraft", "a flat surface"),
    ("TRAIN", "to instruct", "a rail vehicle"),
    ("COACH", "an instructor", "a long-distance bus"),
    ("PUPIL", "a school student", "the opening of the eye"),
    ("BATTER", "to hit repeatedly", "a cake mixture"),
    ("BAT", "a flying mammal", "a club for hitting balls"),
    ("BARK", "a tree covering", "a dog sound"),
    ("WAVE", "a greeting gesture", "an ocean swell"),
    ("TIRE", "to grow exhausted", "a wheel covering"),
    ("NAIL", "to fasten with a pin", "a fingertip plate"),
    ("CROSS", "angry in manner", "to intersect"),
    ("CRANE", "a wading bird", "a lifting machine"),
    ("BOW", "to bend forward", "a ribbon knot"),
    ("TIE", "an equal score", "a neck garment"),
    ("MATCH", "a contest", "to be equal to"),
    ("LIGHT", "not heavy", "illumination"),
)

_LEDGER_INDEX = {pivot: (sense_a, sense_b) for pivot, sense_a, sense_b in HOMOGRAPH_LEDGER}

_QUOTE_OPEN = {'"': '"', "“": "”", "'": "'", "‘": "’"}

_FILL_MARKER_RE = re.compile(r"(?:_{3,}|\.{3,}|…+|\b(?:and|or|to|of)\s+_{3,}\b)", re.IGNORECASE)
_SPOKEN_LABEL_RE = re.compile(
    r"[\[(]\s*(?:spoken(?:\s+equivalent)?|utterance|said\s+aloud)\s*[\])]",
    re.IGNORECASE,
)
_ABBREVIATION_RE = re.compile(r"[\[(]\s*abbr\.?\s*[\])]|\bbriefly\b", re.IGNORECASE)
_LANGUAGE_RE = re.compile(
    r"\b(?:in\s+)?(Dutch|French|German|Italian|Portuguese|Spanish|Japanese)\b",
    re.IGNORECASE,
)
_BRACKET_WRAP_RE = re.compile(r"^\[.*\]$", re.DOTALL)
_HIDDEN_CUE_RE = re.compile(r"\b(?:hidden|concealed|inside|within|part\s+of|found\s+in)\b", re.IGNORECASE)
_QUOTED_SPAN_RE = re.compile(r"[\"“‘]([^\"”’\n]{2,96})[\"”’]")


def _letters_only(value) -> str:
    return re.sub(r"[^A-Z]", "", str(value).upper())


def _tokens(text: str) -> set:
    return {token for token in re.findall(r"[A-Za-z]+", text.upper()) if len(token) >= 3}


def ledger_senses(pivot: str):
    """Return the two curated senses for a pivot, or None if unlisted."""
    if not isinstance(pivot, str):
        return None
    return _LEDGER_INDEX.get(_letters_only(pivot) or pivot.upper())


def witness_pun(clue, answer=None) -> dict:
    """Witness a pun claim: trailing ``?`` plus a ledger pivot in the surface.

    The pivot must appear as a surface token, carry two ledger senses, and
    must not be the answer itself. A trailing ``?`` without a pivot yields
    ``pseudo-pun``, never ``pun``. No ``?`` at all is not a pun claim.
    """
    text = clue if isinstance(clue, str) else ""
    stripped = text.strip()
    if not stripped.endswith("?"):
        return {"witnessed": False, "family": "definition", "reason": "no-question-mark"}
    answer_letters = _letters_only(answer) if answer is not None else ""
    candidates = sorted(
        (token for token in _tokens(stripped) if token in _LEDGER_INDEX and token != answer_letters),
        key=len,
        reverse=True,
    )
    if not candidates:
        return {"witnessed": False, "family": "pseudo-pun", "reason": "no-ledger-pivot"}
    pivot = candidates[0]
    sense_a, sense_b = _LEDGER_INDEX[pivot]
    return {
        "witnessed": True,
        "family": "pun",
        "pivot": pivot,
        "senses": [sense_a, sense_b],
        "senseSource": SENSE_SOURCE_ID,
    }


def witness_fill_blank(clue) -> dict:
    """Witness a fill-blank claim: the marked blank is the witness."""
    text = clue if isinstance(clue, str) else ""
    match = _FILL_MARKER_RE.search(text)
    if match is None:
        return {"witnessed": False, "family": "definition", "reason": "no-blank-marker"}
    return {
        "witnessed": True,
        "family": "fill-blank",
        "span": {"start": match.start(), "end": match.end()},
    }


def _quoted_spans(text: str) -> list:
    return [
        {"start": match.start(), "end": match.end(), "utterance": match.group(1)}
        for match in _QUOTED_SPAN_RE.finditer(text)
    ]


def witness_spoken_equivalent(clue) -> dict:
    """Witness a spoken-equivalent claim: quoted utterance AND its label."""
    text = clue if isinstance(clue, str) else ""
    spans = _quoted_spans(text)
    if not spans:
        return {"witnessed": False, "family": "definition", "reason": "no-quoted-utterance"}
    label = _SPOKEN_LABEL_RE.search(text)
    if label is None:
        return {
            "witnessed": False,
            "family": "definition",
            "reason": "utterance-without-label",
            "utterance": spans[0]["utterance"],
        }
    return {
        "witnessed": True,
        "family": "spoken-equivalent",
        "utterance": spans[0]["utterance"],
        "labelSpan": {"start": label.start(), "end": label.end()},
    }


def witness_nonverbal_expression(clue) -> dict:
    """Witness a bracketed nonverbal cue: the bracket span is the witness."""
    text = clue if isinstance(clue, str) else ""
    stripped = text.strip()
    if _BRACKET_WRAP_RE.match(stripped):
        return {
            "witnessed": True,
            "family": "nonverbal-expression",
            "span": {"start": 0, "end": len(stripped)},
        }
    return {"witnessed": False, "family": "definition", "reason": "no-bracket-span"}


def witness_metalinguistic(clue) -> dict:
    """Witness a metalinguistic claim: the abbreviation indicator."""
    text = clue if isinstance(clue, str) else ""
    match = _ABBREVIATION_RE.search(text)
    if match is None:
        return {"witnessed": False, "family": "definition", "reason": "no-abbreviation-indicator"}
    return {
        "witnessed": True,
        "family": "metalinguistic",
        "span": {"start": match.start(), "end": match.end()},
    }


def witness_factual_relation(clue, relation_pattern_matched=False) -> dict:
    """Witness a factual-relation claim: language indicator or caller-attested pattern."""
    text = clue if isinstance(clue, str) else ""
    match = _LANGUAGE_RE.search(text)
    if match is not None:
        return {
            "witnessed": True,
            "family": "factual-relation",
            "language": match.group(1).casefold(),
            "span": {"start": match.start(), "end": match.end()},
        }
    if relation_pattern_matched is True:
        return {"witnessed": True, "family": "factual-relation", "kind": "fact-relation-pattern"}
    return {"witnessed": False, "family": "definition", "reason": "no-language-indicator"}


def witness_hidden_word_span(clue) -> dict:
    """Find a hidden-word witness: a quoted span beside a concealment cue.

    Used by the quoted hidden-word validator; a hidden word needs its span.
    """
    text = clue if isinstance(clue, str) else ""
    cue = _HIDDEN_CUE_RE.search(text)
    spans = _quoted_spans(text)
    if cue is None or not spans:
        return {"witnessed": False, "reason": "no-concealment-cue-or-span"}
    return {
        "witnessed": True,
        "span": {"start": spans[0]["start"], "end": spans[0]["end"]},
        "source": spans[0]["utterance"],
        "cue": cue.group(0),
    }


def witness_clue_family(claimed_family, clue, answer=None, relation_pattern_matched=False) -> dict:
    """Admit or reduce one claimed family to its witnessed family.

    Returns ``claimed``, ``witnessed`` (bool), ``family`` (the witnessed
    family), ``witness`` (details or None) and ``senseSource`` (``curated-v1``
    for ledger-backed pun verdicts, else None). Exactly one witnessed family
    is returned per call; where no witness exists it is ``definition`` (or
    ``pseudo-pun`` for a bare ``?``), and it says so.
    """
    if claimed_family == "pun":
        verdict = witness_pun(clue, answer)
    elif claimed_family == "fill-blank":
        verdict = witness_fill_blank(clue)
    elif claimed_family == "spoken-equivalent":
        verdict = witness_spoken_equivalent(clue)
    elif claimed_family == "nonverbal-expression":
        verdict = witness_nonverbal_expression(clue)
    elif claimed_family == "metalinguistic":
        verdict = witness_metalinguistic(clue)
    elif claimed_family == "factual-relation":
        verdict = witness_factual_relation(clue, relation_pattern_matched)
    else:
        verdict = {"witnessed": True, "family": "definition"}
    witness = {key: value for key, value in verdict.items() if key not in {"witnessed", "family"}}
    return {
        "claimed": claimed_family,
        "witnessed": verdict["witnessed"] is True,
        "family": verdict["family"],
        "witness": witness or None,
        "senseSource": verdict.get("senseSource"),
    }
