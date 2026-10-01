"""Closed genre census for private clue surfaces (Q05).

Family (Q04) asks what witness a surface carries; genre asks what *kind of
boring* a surface is. The guards in ``private_puzzle_generation.py`` are six
anchored ``fullmatch`` regexes over closed vocabularies, so ``Famous
singer's name`` is rejected while any other name-shaped clue — ``Name of the
singer in a 1980s British band`` — passes every rule in the file. Nothing
counts name-shaped clues, so nothing caps them.

The taxonomy below is closed and is reported before it is enforced:
``name-slot``, ``role-plus-name``, ``common-term``, ``x-e-g``,
``fill-blank``, ``quotational``, ``sound-or-action-cue``, ``abbreviation``,
``plain-definition``. First match wins, in that order. The two v1 caps are
narrow and both exist because the corpus already found them: ``name-slot``
is disallowed where the entry has no source-backed sense, and ``fill-blank``
is capped at one quarter of a board (study v5 satisfied a diversity floor
with ``fill-blank: 57`` of 74 surfaces).

Name-shape patterns mirror the canonical ``_GENERIC_NAME_*`` guards in
``private_puzzle_generation.py``; the loose name-shape rule is new here and
is what the anchored guards miss. Update the two together.
"""

from __future__ import annotations

import re

GENRE_VERSION = "private-clue-genre-v1"

GENRES = (
    "name-slot",
    "role-plus-name",
    "common-term",
    "x-e-g",
    "fill-blank",
    "quotational",
    "sound-or-action-cue",
    "abbreviation",
    "plain-definition",
)

# Closed role vocabulary, formerly shared with the retired generic name
# guards; the genre census is now its home.
_ROLES = (
    "actor", "actress", "artist", "author", "band", "character", "comedian",
    "composer", "director", "king", "queen", "singer", "scientist", "scholar",
    "surname", "writer", "novelist", "poet", "person", "president", "saint",
    "celebrity", "drummer", "guitarist", "bassist", "vocalist", "rapper",
    "pianist", "trumpeter", "violinist", "cellist", "saxophonist", "star",
    "idol", "legend", "icon", "diva", "maestro",
)
_ROLE_RE = re.compile(r"\b(?:" + "|".join(_ROLES) + r")\b", re.IGNORECASE)
_NAME_WORD_RE = re.compile(r"\bname[ds]?\b", re.IGNORECASE)
_NAME_OF_RE = re.compile(r"\bname\s+of\s+(?:a|an|the)\b", re.IGNORECASE)
# Anchored dead-end shapes, formerly also enforced as generic-clue blockers
# in _clue_wordplay_issue (retired in Q08). They survive here as detectors
# (anchored-name-guard), where they count instead of blocking.
_ANCHORED_NAME_RES = (
    re.compile(
        r"^\s*(?:(?:a|an|the)\s+)?"
        r"(?:(?:famous|well[- ]known|notable|popular|renowned|celebrated|"
        r"italian|french|german|spanish|japanese|portuguese|dutch)\s+)?"
        r"(?:actor|actress|artist|author|band|character|comedian|composer|"
        r"director|king|queen|singer|scientist|scholar|surname|writer|"
        r"novelist|poet|person|president|saint|celebrity)"
        r"(?:'s|’s)?\s+name"
        r"(?:\s*,?\s*perhaps)?\s*[?.]?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*name\s+of\s+(?:(?:a|an|the)\s+)?"
        r"(?:(?:famous|well[- ]known|notable|popular|renowned|celebrated|"
        r"classic|italian|french|german|spanish|japanese|portuguese|dutch)\s+)?"
        r"(?:actor|actress|artist|author|comedian|composer|director|king|queen|"
        r"singer|scientist|scholar|writer|novelist|poet|person|president|saint|"
        r"celebrity)\s*[?.]?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:a\s+)?name\s+(?:that|which)\s+"
        r"(?:(?:might|could|would|can)\s+)?"
        r"(?:follow|precede|come\s+(?:after|before))\b.*[?.]?\s*$",
        re.IGNORECASE,
    ),
)
_CAPITALIZED_AFTER_FIRST_RE = re.compile(r"^\s*\S+\s+.*\b[A-Z][a-z]+\b")

# Mirrors _GENERIC_CLUE_RE, _GENERIC_TEMPLATE_PHRASE_RE,
# _GENERIC_NO_ROUTE_CLUE_RE and _LOW_INFORMATION_CLUE_TEXTS.
_GENERIC_FULL_RE = re.compile(
    r"^\s*(?:(?:a|an|the)\s+)?"
    r"(?:common|usual|ordinary|generic|standard)\s+"
    r"(?:names?|terms?|words?|designations?|labels?|abbreviations?|acronyms?|"
    r"initialisms?|synonyms?|nicknames?|responses?|replies?|answers?|entries?|"
    r"examples?|expressions?|phrases?|symbols?|titles?|slogans?|spellings?|forms?)"
    r"\s*[?.]?\s*$",
    re.IGNORECASE,
)
_GENERIC_PHRASE_RE = re.compile(
    r"\b(?:common|usual|ordinary|generic|standard)\s+"
    r"(?:(?:[\w][\w'’/-]*|\d+)\s+){0,3}"
    r"(?:names?|terms?|words?|designations?|labels?|abbreviations?|acronyms?|"
    r"initialisms?|synonyms?|nicknames?|responses?|replies?|answers?|entries?|"
    r"examples?|expressions?|phrases?|symbols?|titles?|slogans?|spellings?|forms?)\b",
    re.IGNORECASE,
)
_LOW_INFORMATION_TEXTS = frozenset(
    {
        "a thing", "an item", "an object", "a word", "a term", "a name",
        "a person", "a place", "a sound", "a noise", "an answer", "an entry",
        "something", "someone", "somebody", "one thing",
    }
)
_EG_RE = re.compile(r"\be\.?\s*g\.?", re.IGNORECASE)
_FILL_MARKER_RE = re.compile(r"(?:_{3,}|\.{3,}|…+|\b(?:and|or|to|of)\s+_{3,}\b)", re.IGNORECASE)
_QUOTE_RE = re.compile(
    r'"[^"\n]+"|[“”][^“”\n]+|[‘’][^‘’\n]+|(?<!\w)\'[^\'\n]+?\'(?!\w)'
)
_SPOKEN_LABEL_RE = re.compile(
    r"[\[(]\s*(?:spoken(?:\s+equivalent)?|utterance|said\s+aloud)\s*[\])]",
    re.IGNORECASE,
)
_BRACKET_WRAP_RE = re.compile(r"^\[.*\]$", re.DOTALL)
_SOUND_CUE_RE = re.compile(
    r"\b(?:sounds?|noises?|cr(?:y|ies)|calls?|utterance|exclamation|gesture|"
    r"signals?|beeps?|buzz(?:es)?|roars?|shouts?|cheers?|groans?|sighs?)\b",
    re.IGNORECASE,
)
_ABBREVIATION_RE = re.compile(r"[\[(]\s*abbr\.?\s*[\])]|\bbriefly\b", re.IGNORECASE)


def _text(value) -> str:
    return value if isinstance(value, str) else ""


def observe_clue_genre(clue) -> dict:
    """Classify one surface into the closed genre taxonomy.

    First match wins in taxonomy order. Returns ``genre`` plus the witness
    detail (span, marker, or matched rule) that admitted it.
    """
    text = _text(clue)
    stripped = text.strip()
    lowered = stripped.casefold()

    if any(rx.match(stripped) is not None for rx in _ANCHORED_NAME_RES):
        return {"genre": "name-slot", "rule": "anchored-name-guard"}
    # The loose shape is what the anchored guards miss: any role noun beside
    # a name word, or a "name of the <role>" construction with fillers the
    # closed vocabularies never listed.
    if (
        _NAME_WORD_RE.search(stripped) is not None
        and _ROLE_RE.search(stripped) is not None
    ) or (
        _NAME_OF_RE.search(stripped) is not None
        and _ROLE_RE.search(stripped) is not None
    ):
        return {"genre": "name-slot", "rule": "loose-name-shape"}

    if _ROLE_RE.search(stripped) is not None and (
        _CAPITALIZED_AFTER_FIRST_RE.search(stripped) is not None
    ):
        return {"genre": "role-plus-name", "rule": "role-plus-capitalized-name"}

    if (
        _GENERIC_FULL_RE.match(stripped) is not None
        or _GENERIC_PHRASE_RE.search(stripped) is not None
        or lowered.strip("?.! ") in _LOW_INFORMATION_TEXTS
    ):
        return {"genre": "common-term", "rule": "generic-template"}

    if _EG_RE.search(stripped) is not None:
        return {"genre": "x-e-g", "rule": "exempli-gratia-marker"}

    fill = _FILL_MARKER_RE.search(stripped)
    if fill is not None:
        return {
            "genre": "fill-blank",
            "rule": "blank-marker",
            "span": {"start": fill.start(), "end": fill.end()},
        }

    if _QUOTE_RE.search(stripped) is not None:
        return {"genre": "quotational", "rule": "quotation-marks"}

    if _BRACKET_WRAP_RE.match(stripped) is not None:
        return {"genre": "sound-or-action-cue", "rule": "bracket-span"}
    sound = _SOUND_CUE_RE.search(stripped)
    if sound is not None:
        return {
            "genre": "sound-or-action-cue",
            "rule": "sound-cue-word",
            "cue": sound.group(0),
        }

    abbreviation = _ABBREVIATION_RE.search(stripped)
    if abbreviation is not None:
        return {"genre": "abbreviation", "rule": "abbreviation-indicator"}

    return {"genre": "plain-definition", "rule": "no-genre-marker"}


def census_genres(records) -> dict:
    """Count genres over (id, clue) records; report-only, never enforcement."""
    counts: dict = {}
    total = 0
    for record in records or []:
        if isinstance(record, dict):
            clue = record.get("clue", "")
        elif isinstance(record, str):
            clue = record
        else:
            continue
        genre = observe_clue_genre(clue)["genre"]
        counts[genre] = counts.get(genre, 0) + 1
        total += 1
    return {
        "version": GENRE_VERSION,
        "pairs": total,
        "genreCounts": dict(sorted(counts.items())),
        "nameSlotCount": counts.get("name-slot", 0),
        "nameSlotRate": round(counts.get("name-slot", 0) / total, 4) if total else 0.0,
        "fillBlankCount": counts.get("fill-blank", 0),
        "fillBlankRate": round(counts.get("fill-blank", 0) / total, 4) if total else 0.0,
    }
