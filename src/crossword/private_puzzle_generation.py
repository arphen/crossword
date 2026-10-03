"""Private, local Ollama + xfill puzzle creation for the /future play lane.

This is deliberately separate from the admitted-pack publication pipeline.
Generated puzzles are experimental, local play artifacts; no content review or
publication claim is made here.
"""

from datetime import datetime, timezone
from collections.abc import Mapping
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import re
from time import monotonic
from uuid import UUID, uuid4

import requests
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import IntegrityError

from .construction_runtime import (
    FullSizeDraftRejected,
    FullSizeRuntimeUnavailable,
    generate_full_size_draft,
)
from .construction_evidence import evaluate_private_board
from .construction_simulation_adapter import evaluate_sibling_adapter
from .weekday_mechanics_evaluation import evaluate_thursday_mechanic_board
from .clue_grammar_bridge import (
    summarize_surface_clue_families,
    validate_surface_clue_family,
)
from .clue_grounding_validators import validate_private_clue_witnesses
from .clue_genre import observe_clue_genre
from .clue_witness import witness_clue_family
from .private_clue_corpus import append_corpus_records, build_corpus_records
from .clue_semantic_challenger import (
    challenge_private_clue_pair,
    summarize_challenge_classifications,
)
from .database import db
from .admitted_pack_config import (
    AdmittedPackConfigError,
    load_configured_admitted_pack,
)
from .episteme_store import (
    EpistemeCommandRejected,
    EpistemeRuntimeUnavailable,
    get_or_create_episteme_profile,
)
from .future import StartingProfile, catalog
from .future_grid_jobs import FutureGridDraftJob, _digest, _response, _stamp
from .future_puzzles import register_legacy_puzzle, store_private_puzzle_provenance
from .language_signals import has_explicit_language_signal
from .language_task_pack import private_display_text_for_review, task_pair_for_review
from .private_domain_hints import (
    load_private_domain_hints,
    private_domain_hint_receipt,
)
from .token_construction import (
    construct_native_token_grid,
    emit_single_cell_language_tokens,
    native_token_hints,
    validate_native_token_cells,
)
from .models import Crossword


private_puzzle_api = Blueprint("private_puzzle_api", __name__)

MAX_BODY_BYTES = 4096
MAX_OLLAMA_RESPONSE_BYTES = 256 * 1024
MAX_THEME_WORDS = 6
DEFAULT_CLUE_TOKENS_PER_ENTRY = 56
PRIVATE_CLUE_CHALLENGE_ENV = "CROSSWORD_PRIVATE_CLUE_CHALLENGE"
PRIVATE_CLUE_CHALLENGE_VERSION = "private-clue-model-challenge-v1"
THURSDAY_MECHANIC_MAX_IFFY = 12
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_ANSWER = re.compile(r"^[A-Z]{3,15}$")
_CLUE_ID = re.compile(r"^[1-9][0-9]{0,2}[AD]$")
_WEEKDAYS = {day["id"] for day in catalog["days"]}

# Visible clue conventions promised by the private Tuesday recipe. These are
# surface observations only; they do not establish semantic truth or fairness.
_DIVERSITY_FAMILY_ORDER = (
    "pun",
    "fill-blank",
    "nonverbal-expression",
    "spoken-equivalent",
    "metalinguistic",
)

# These are prompt-facing surface contracts for the bounded Tuesday diversity
# pass.  The validators below remain authoritative; the examples are only
# there to make the requested house style legible to a local model.
_DIVERSITY_REQUIRED_SURFACE = {
    "pun": (
        "end with ? AND hinge on a word with two real senses present in the "
        "surface, e.g. `One with a lot to say?` (LOT: a quantity / an auction "
        "item) or `Branch specialist?` (BRANCH: a tree limb / a bank office). "
        "A bare ? with no double-meaning word is not a pun."
    ),
    "fill-blank": "contain ___ or an ellipsis blank, e.g. `___ voyage`",
    "nonverbal-expression": "be fully bracketed like [Sound heard nearby]",
    "spoken-equivalent": (
        "be a whole quoted utterance plus its spoken label, e.g. `\"Hello "
        "there\" (Spoken equivalent)`. A quote without a label is not one."
    ),
    "metalinguistic": "include (abbr.) or the word briefly, e.g. `Doctor, briefly`",
}

# A private crossword can be strange, slangy, or occasionally adult when the
# player asks for that register. These are construction artefacts that should
# never be surfaced accidentally: one misspelled slang variant and one model
# hallucination observed in the bundled xfill vocabulary. Keep this list
# intentionally small and explainable; it is not a general content filter.
_PRIVATE_FILL_BLOCKLIST = frozenset({"FUCCBOIS", "METAPIEMAN"})
_CLUE_FACT_TERMS = (
    "airport",
    "actor",
    "actress",
    "biblical",
    "brand",
    "character",
    "broadcasting",
    "botanical",
    "company",
    "country",
    "famous",
    "film",
    "godfather",
    "greek god",
    "hamlet",
    "major",
    "nickname",
    "nintendo",
    "nation",
    "palindrome",
    "river",
    "rose",
    "singer",
    "skull",
    "sportswear",
    "surname",
    "television",
    "tv",
    "world conflict",
    "zodiac",
)
_CLUE_IDENTITY_SURFACE_RE = re.compile(
    r"\b(?:agency|capital|city|conference|director|film|franchise|leader|"
    r"middle\s+name|organization|poet|representative|senator|team|"
    r"university|mayor|governor|minister)\b",
    re.IGNORECASE,
)
_CLUE_ROLE_NAME_RE = re.compile(
    r"\b(?i:actor|actress|artist|author|comedian|composer|director|king|queen|"
    r"singer|scientist|scholar|writer|novelist|poet|president|saint|celebrity)"
    r"\s+[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'-]{2,}\b"
)
# These verbs and relation words are useful signals, but they are not proof
# that a model's assertion is true.  The private generator has no source
# ledger for a generated clue, so a factual-looking surface deserves a second
# look whenever it makes a specific relation (``singer with ...``, ``river in
# ...``).  Keeping the detector small and explainable is preferable to
# pretending that a broad NER pass could establish truth.
_CLUE_FACT_RELATIONS = (
    "born",
    "died",
    "founded",
    "known for",
    "member of",
    "played",
    "portrayed",
    "starred",
    "wrote",
    "sang",
    "located",
    "capital of",
    "home of",
    "with",
    "from",
    "in",
    "of",
)
_CLUE_FACT_RELATION_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in _CLUE_FACT_RELATIONS) + r")\b",
    re.IGNORECASE,
)
# These templates do not give a player a usable route into the fill. Allow a
# short descriptor between the generic qualifier and noun so variants such as
# "common male name" cannot slip through as nominally specific clues.
_GENERIC_CLUE_RE = re.compile(
    r"^\s*(?:(?:a|an|the)\s+)?"
    r"(?:common|usual|ordinary|generic|standard)\s+"
    r"(?:names?|terms?|words?|designations?|labels?)"
    r"(?:\s+(?:for|of))?\s*[?.]?\s*$",
    re.IGNORECASE,
)
_GENERIC_TEMPLATE_PHRASE_RE = re.compile(
    r"\b(?:common|usual|ordinary|generic|standard)\s+"
    r"(?:(?:[\w][\w'’/-]*|\d+)\s+){0,3}"
    r"(?:names?|terms?|words?|designations?|labels?)\b",
    re.IGNORECASE,
)
# A language qualifier turns a content-free template into a genuine route:
# "Common Latin word" is standard Monday crosswordese with a real solving
# path, while "Common male name" names no route at all. The census over
# 1.2M published pairs confirms editors use the qualified form routinely.
_GENERIC_LANGUAGE_ROUTE_RE = re.compile(
    r"\b(?:latin|french|german|spanish|italian|dutch|portuguese|japanese|"
    r"greek|hebrew|yiddish|russian|chinese|arabic)\b",
    re.IGNORECASE,
)


def _is_generic_template(text):
    """Decide whether a clue is a content-free generic template.

    The anchored fullmatch forms always count. The broader phrase form
    counts unless a language qualifier inside the matched span supplies a
    route to the solver.
    """
    if not isinstance(text, str):
        return False
    if _GENERIC_CLUE_RE.fullmatch(text) or _GENERIC_NO_ROUTE_CLUE_RE.fullmatch(text):
        return True
    match = _GENERIC_TEMPLATE_PHRASE_RE.search(text)
    if match is None:
        return False
    span = match.group(0)
    if _GENERIC_LANGUAGE_ROUTE_RE.search(span):
        return False
    # A possessed qualifier names its route ("Common dog's name" -> SPOT),
    # as does a for/of phrase with a definite referent ("Common name for
    # sodium hydroxide" -> LYE). An indefinite object ("a gas") stays
    # generic: it points at no route.
    if re.search(r"['’]s\b", span):
        return False
    tail = text[match.end():]
    if re.match(r"\s+(?:for|of)\s+(?!a\b|an\b)\S", tail, re.IGNORECASE):
        return False
    return True


# The three anchored name-shape guards lived here and were retired in Q08:
# name-shaped clues without a source-backed sense are refused downstream by
# the factual-surface guard and the genre cap (name-slot-without-source),
# which additionally spare reviewed source-backed senses. The anchored
# shapes survive as detectors in clue_genre.py (anchored-name-guard), where
# they count instead of blocking.
# A few other noun-only templates have the same failure mode as ``common
# name``: they describe the *kind* of answer without giving the solver a
# referent, sense, or signalled mechanism.  Keep this detector anchored to the
# whole clue so useful authored surfaces such as ``Common abbreviation for
# New York`` remain available.  The existing phrase detector intentionally
# remains broader for the especially common ``common name/term/word`` family.
_GENERIC_NO_ROUTE_CLUE_RE = re.compile(
    r"^\s*(?:(?:a|an|the|one|some|any)\s+)?"
    r"(?:common|usual|ordinary|generic|standard)\s+"
    r"(?:abbreviations?|acronyms?|initialisms?|synonyms?|nicknames?|"
    r"responses?|replies?|answers?|entries?|examples?|expressions?|"
    r"phrases?|symbols?|titles?|slogans?|spellings?|forms?)"
    r"\s*[?.]?\s*$",
    re.IGNORECASE,
)
# These surfaces contain grammatical words but give the solver no usable
# route into the fill.  Keep the list deliberately narrow and apply it only to
# Tuesday's stricter recipe; a later reviewed clue pack can still provide an
# exact authored surface when it is intentional.
_LOW_INFORMATION_CLUE_TEXTS = frozenset(
    {
        "a thing",
        "an item",
        "an object",
        "a word",
        "a term",
        "a name",
        "a person",
        "a place",
        "a sound",
        "a noise",
        "an answer",
        "an entry",
        "something",
        "someone",
        "somebody",
        "one thing",
    }
)
_LANGUAGE_YES = {
    "dutch": {"JA"},
    "french": {"OUI"},
    "german": {"JA"},
    "italian": {"SI"},
    "japanese": {"HAI"},
    "portuguese": {"SIM"},
    "spanish": {"SI"},
}
# One optional first-thread form per setup language. These are deliberately
# ordinary, three-or-more-letter forms so the current ASCII crossword engine
# can place them; they remain private synthetic starters until a reviewed
# language pack supplies source and native-speaker evidence.
_LANGUAGE_STARTER_FORMS = {
    "dutch": ("JA", "HUIS", "WATER"),
    "french": ("OUI",),
    "german": ("NEIN", "GUT", "HALLO"),
    "spanish": ("HOLA",),
    "italian": ("CIAO",),
    "portuguese": ("SIM",),
    "japanese": ("SUSHI", "HAI"),
}
# The opening uses human-readable language names while episteme tasks use
# stable language tags. Keep the bridge local and explicit so a selected
# language can create a small, reversible review thread without treating
# exposure as mastery.
_LANGUAGE_CODES = {
    "Dutch": "nl",
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Italian": "it",
    "Portuguese": "pt",
    "Japanese": "ja",
}
# These are the reviewed, reversible clue-family mappings currently emitted by
# the authored reflection cards. Keep the bridge explicit: arbitrary prose in
# the profile must never become a generation control merely because it happens
# to contain a familiar word.
_REFLECTION_CLUE_FAMILIES = {
    "clue-wordplay": "wordplay",
    "crossing-supported-discovery": "discovery",
    "earned-crossword-challenge": "challenge",
}
# ClueQualityNotes writes these labels as explicit association-field controls.
# Keep the translation closed and literal: arbitrary prose in a profile must
# never become a model steering instruction merely because it contains a clue
# word.
_EXPLICIT_CLUE_FEEDBACK_FAMILIES = {
    "factual surface is unverified": "factual-relation",
    "answer giveaway removed": "answer-giveaway",
    "anagram needs repair": "wordplay",
    "reversal needs repair": "wordplay",
    "language relation needs repair": "factual-relation",
    "quotation mark was normalized": "spoken-equivalent",
    "brackets were normalized": "nonverbal-expression",
    "bracket scope was normalized": "nonverbal-expression",
    "question mark was normalized": "pun",
    "local challenger recommends review": "factual-relation",
    "local challenger recommends a safer foothold": "discovery",
}
_ANAGRAM_RE = re.compile(
    r"\b(?:anagram|scramble|mixed[- ]up letters?)\s+of\s+[\"'“‘]?([A-Za-z]+)",
    re.IGNORECASE,
)
_REVERSE_RE = re.compile(
    r"[\"'“‘]?([A-Za-z]+)[\"'”’]?\s+(?:spelled|written)\s+"
    r"(?:backward|backwards|in reverse)|\b(?:reverse|backward|backwards)\s+of\s+"
    r"[\"'“‘]?([A-Za-z]+)",
    re.IGNORECASE,
)
_HIDDEN_RE = re.compile(
    r"\b(?:hidden|found|inside)\s+in\s+[\"“‘]([^\"”’\n]{2,96})[\"”’]",
    re.IGNORECASE,
)
# These are deliberately surface-level conventions.  They let provenance say
# what a deterministic checker actually observed without turning a model clue
# into a sourced fact.  The first two can be checked against the answer; the
# remaining labels only describe an explicit clue convention.
_SAFE_CLUE_RELATIONS = (
    ("anagram", _ANAGRAM_RE, "mechanical"),
    ("reversal", _REVERSE_RE, "mechanical"),
    ("hidden-word", _HIDDEN_RE, "mechanical"),
    (
        "language-label",
        re.compile(
            r"\b(?:in\s+)?(?:Dutch|French|German|Italian|Portuguese|Spanish|Japanese)\b",
            re.IGNORECASE,
        ),
        "surface",
    ),
    (
        "abbreviation-label",
        re.compile(r"[\[(]\s*abbr\.?\s*[\])]", re.IGNORECASE),
        "surface",
    ),
    (
        "plural-label",
        re.compile(
            r"\bplural(?:\s+(?:form|of))?\b|[\[(]\s*pl\.?\s*[\])]",
            re.IGNORECASE,
        ),
        "surface",
    ),
    (
        "tense-label",
        re.compile(
            r"\b(?:past|present|future)(?:\s+tense)?\b|[\[(]\s*(?:past|present|future)(?:\s+tense)?\s*[\])]",
            re.IGNORECASE,
        ),
        "surface",
    ),
)

_CLUE_FAMILY_LANGUAGE_RE = re.compile(
    r"\b(?:in\s+)?(Dutch|French|German|Italian|Portuguese|Spanish|Japanese)\b",
    re.IGNORECASE,
)
_CLUE_FAMILY_FILL_RE = re.compile(
    r"(?:_{3,}|\.{3,}|…+|\b(?:and|or|to|of)\s+_{3,}\b)", re.IGNORECASE
)
_CLUE_FAMILY_ABBR_RE = re.compile(r"[\[(]\s*abbr\.?\s*[\])]|\bbriefly\b", re.IGNORECASE)
_CLUE_FAMILY_SPOKEN_RE = re.compile(
    r"[\[(]\s*(?:spoken(?:\s+equivalent)?|utterance|said\s+aloud)\s*[\])]",
    re.IGNORECASE,
)
_CLUE_FAMILY_TENSE_RE = re.compile(
    r"(?:\b(?:past|present|future)\s+tense\b|[\[(]\s*(?:past|present|future)(?:\s+tense)?\s*[\])])",
    re.IGNORECASE,
)

# This is a provenance contract for the private clue pass.  It is deliberately
# separate from the published V2/editorial contracts: the local model has no
# source ledger, so the bundle can report what was observed and what remains
# unknown, but it cannot certify a sense or a fact.
GROUNDED_CLUE_BUNDLE_VERSION = "private-grounded-clue-bundle-v1"
REVIEWED_CLUE_PACK_VERSION = "private-reviewed-clue-pack-v1"
# v2 makes the requested family a hard visible-surface contract. Older v1
# receipts remain readable as historical, advisory runs.
CLUE_DIVERSITY_REPAIR_VERSION = "private-clue-diversity-repair-v2"
CLUE_DIVERSITY_REPAIR_ENV = "CROSSWORD_PRIVATE_CLUE_DIVERSITY_REPAIR"
FILL_QUALITY_POLICY_VERSION = "private-fill-quality-policy-v1"
_NATIVE_THEME_LOCK_LIMIT = 4
_FILL_RETRY_MAX_ATTEMPTS = 4
_FILL_RETRY_SEED_STEP = 104_729
_SUNDAY_FALLBACK_SEED = 20260931
_SUNDAY_FALLBACK_THEMES = ["ECHO", "SOUND", "SONIC", "VOICE"]
_SOURCE_FREE_FALLBACK_RE = re.compile(
    r"^Entry supported by its crossings \([1-9][0-9]* letters\)$"
)
_CLUE_PROPER_NAME_RE = re.compile(
    r"\b(?:actor|actress|author|band|character|director|king|queen|singer|"
    r"surname|writer|person|president|saint|celebrity)\b",
    re.IGNORECASE,
)
_PLURAL_MARKER_RE = re.compile(
    r"\bplural(?:\s+(?:form|of))?\b|[\[(]\s*pl\.?\s*[\])]",
    re.IGNORECASE,
)
_PAST_TENSE_MARKER_RE = re.compile(
    r"\bpast\s+tense\b|[\[(]\s*past(?:\s+tense)?\s*[\])]",
    re.IGNORECASE,
)
_PRESENT_TENSE_MARKER_RE = re.compile(
    r"\bpresent\s+tense\b|[\[(]\s*present(?:\s+tense)?\s*[\])]",
    re.IGNORECASE,
)
_FUTURE_TENSE_MARKER_RE = re.compile(
    r"\bfuture\s+tense\b|[\[(]\s*future(?:\s+tense)?\s*[\])]",
    re.IGNORECASE,
)
_COMPARATIVE_MARKER_RE = re.compile(
    r"\bcomparative\b|[\[(]\s*comp\.?\s*[\])]", re.IGNORECASE
)
_SUPERLATIVE_MARKER_RE = re.compile(
    r"\bsuperlative\b|[\[(]\s*superl\.?\s*[\])]", re.IGNORECASE
)
# An unglossed comparative/superlative phrase: "more shady", "most kindly".
# Captured because the answer can itself be the comparative the phrase
# describes, which no marker-based convention check can see.
_DEGREE_PHRASE_RE = re.compile(
    r"\b(?:more|most|less|least)\s+([A-Za-z][A-Za-z]{2,})\b", re.IGNORECASE
)
# A short-vowel monosyllable such as BIG, FAT or HOT: single consonant, single
# vowel, single consonant. Those are the bases that double the final consonant
# before -ER/-EST. A final W, X or Y is excluded because those letters do not
# double and a base ending in them is not gradable by this rule. Length is
# capped at three letters on purpose: OPEN and MINT also look like CVC shapes
# but take no doubling, because the stress decides and this guard does not
# model stress.
_SHORT_VOWEL_CVC_RE = re.compile(
    r"[BCDFGHJKLMNPQRSTVZW][AEIOU][BCDFGHJKLMNPQRSTVZ]", re.IGNORECASE
)
_COMMON_IRREGULAR_PLURALS = frozenset(
    {
        "CHILDREN",
        "FEET",
        "GEese".upper(),
        "MEN",
        "MICE",
        "PEOPLE",
        "TEETH",
        "WOMEN",
        "OXEN",
    }
)
_COMMON_INVARIANT_PLURALS = frozenset(
    {
        "AIRCRAFT",
        "BISON",
        "COD",
        "DEER",
        "FISH",
        "MOOSE",
        "OFFSPRING",
        "REINDEER",
        "SALMON",
        "SHEEP",
        "SHRIMP",
        "SWINE",
        "TROUT",
    }
)
_COMMON_PAST_FORMS = frozenset(
    {
        "ATE",
        "BEGAN",
        "BENT",
        "BOUGHT",
        "BROUGHT",
        "BUILT",
        "CAME",
        "DID",
        "DREW",
        "DRANK",
        "DROVE",
        "FELT",
        "FLEW",
        "FOUND",
        "GAVE",
        "GOT",
        "GREW",
        "HAD",
        "HEARD",
        "HELD",
        "KEPT",
        "KNEW",
        "LEFT",
        "LOST",
        "MADE",
        "MET",
        "PAID",
        "PUT",
        "RAN",
        "READ",
        "ROSE",
        "SAID",
        "SAW",
        "SANG",
        "SENT",
        "SLEPT",
        "SOLD",
        "SPENT",
        "STOOD",
        "SWAM",
        "TAKEN",
        "TAUGHT",
        "THOUGHT",
        "TOOK",
        "TOLD",
        "WAS",
        "WERE",
        "WENT",
        "WON",
        "WORE",
        "WROTE",
    }
)
_COMMON_COMPARATIVE_FORMS = frozenset(
    {"BETTER", "FARTHER", "FURTHER", "LESS", "MORE", "WORSE"}
)
_COMMON_SUPERLATIVE_FORMS = frozenset(
    {"BEST", "FARTHEST", "FURTHEST", "LEAST", "MOST", "WORST"}
)


def _clue_family_observation(clue, answer=None):
    """Classify visible clue signals without asserting the intended meaning.

    Private generated clues do not have a reviewed sense annotation.  This
    observation records only text-visible conventions so a reviewer or future
    challenger can select the right validator.  ``confidence`` deliberately
    stays structural: a question mark may signal a pun, but it cannot prove
    one.  The attached witness verdict (see ``clue_witness.py``) states which
    claimed family the surface actually carries a witness for; a trailing
    ``?`` alone is ``pseudo-pun``, never ``pun``.
    """
    text = clue if isinstance(clue, str) else ""
    stripped = text.strip()
    signals = []
    fact_pattern_matched = False

    if (
        len(stripped) >= 2
        and stripped[0] in {'"', "“", "'", "‘"}
        and stripped[-1] in {'"', "”", "'", "’"}
    ):
        signals.append(
            {
                "kind": "quote",
                "start": 0,
                "end": len(stripped),
                "role": "spoken-equivalent",
            }
        )
        family = "spoken-equivalent"
    elif (
        stripped.startswith("[")
        and stripped.endswith("]")
        and not _PLURAL_MARKER_RE.fullmatch(stripped)
    ):
        signals.append(
            {
                "kind": "brackets",
                "start": 0,
                "end": len(stripped),
                "role": "nonverbal-expression",
            }
        )
        family = "nonverbal-expression"
    else:
        # A quoted phrase may carry a trailing editorial annotation such as
        # ``(Fill-in)``. Preserve the quote signal before choosing the primary
        # family so the renderer and answer-free receipts can explain both
        # visible conventions.
        quoted_end = _leading_quoted_surface(stripped)
        if quoted_end:
            signals.append(
                {
                    "kind": "quote",
                    "start": 0,
                    "end": quoted_end,
                    "role": "spoken-equivalent",
                }
            )
        spoken_annotation = _CLUE_FAMILY_SPOKEN_RE.search(stripped)
        plural = _PLURAL_MARKER_RE.search(stripped)
        language = _CLUE_FAMILY_LANGUAGE_RE.search(stripped)
        fill = _CLUE_FAMILY_FILL_RE.search(stripped)
        abbreviation = _CLUE_FAMILY_ABBR_RE.search(stripped)
        tense = _CLUE_FAMILY_TENSE_RE.search(stripped)
        if plural:
            signals.append(
                {
                    "kind": "plural-marker",
                    "start": plural.start(),
                    "end": plural.end(),
                }
            )
        if tense:
            signals.append(
                {
                    "kind": "tense-marker",
                    "start": tense.start(),
                    "end": tense.end(),
                }
            )
        if spoken_annotation and quoted_end:
            signals.append(
                {
                    "kind": "spoken-equivalent-marker",
                    "start": spoken_annotation.start(),
                    "end": spoken_annotation.end(),
                }
            )
            family = "spoken-equivalent"
        elif language:
            signals.append(
                {
                    "kind": "language-indicator",
                    "start": language.start(),
                    "end": language.end(),
                    "language": language.group(1).casefold(),
                }
            )
            family = "factual-relation"
        elif fill:
            signals.append(
                {"kind": "fill-blank", "start": fill.start(), "end": fill.end()}
            )
            family = "fill-blank"
        elif abbreviation:
            signals.append(
                {
                    "kind": "abbreviation-indicator",
                    "start": abbreviation.start(),
                    "end": abbreviation.end(),
                }
            )
            family = "metalinguistic"
        elif stripped.endswith("?"):
            signals.append(
                {
                    "kind": "question-mark",
                    "start": len(stripped) - 1,
                    "end": len(stripped),
                }
            )
            family = "pun"
        elif _contains_clue_fact_term(stripped) and _CLUE_FACT_RELATION_RE.search(
            stripped
        ):
            family = "factual-relation"
            fact_pattern_matched = True
        else:
            family = "definition"

    witness = witness_clue_family(
        family, text, answer=answer, relation_pattern_matched=fact_pattern_matched
    )
    return {
        "family": family,
        "witnessedFamily": witness["family"],
        "witness": witness["witness"],
        "senseSource": witness["senseSource"],
        "confidence": "surface-signal-only",
        "signals": signals,
        "uncertainty": ["semantic-family-unverified"],
    }


def _leading_quoted_surface(text):
    """Return the end offset of a leading quoted span with an annotation."""
    if not isinstance(text, str) or len(text) < 3:
        return None
    opening = text[0]
    closing = {"'": "'", '"': '"', "“": "”", "‘": "’"}.get(opening)
    if closing is None:
        return None
    end = text.rfind(closing)
    if end <= 1:
        return None
    suffix = text[end + 1 :].strip()
    if suffix and not re.fullmatch(r"(?:\([^\n)]*\)|\[[^\n]]*\])", suffix):
        return None
    return end + 1


_DIFFICULTY = {
    "monday": {"candidates": 40, "time": 1, "voice": "welcoming, direct, familiar"},
    "tuesday": {
        # Keep the weekday budget inside the native xfill build's practical
        # candidate ceiling.  The visible Tuesday step comes from its longer
        # time budget and clue-language floor; sending 90 here makes the
        # native runner reject every themed attempt before it can be measured.
        "candidates": 75,
        "time": 2.5,
        "voice": "playful, with alternate senses, fair second readings, and a clear step beyond literal definitions",
    },
    "wednesday": {
        "candidates": 75,
        "time": 2,
        "voice": "varied, with fair misdirection and wordplay",
    },
    "thursday": {
        "candidates": 100,
        "time": 3,
        "voice": "layered, lateral, and rewarding to untangle",
    },
    "friday": {
        "candidates": 125,
        "time": 4,
        "voice": "indirect, nuanced, and less literal",
    },
    "saturday": {
        "candidates": 150,
        "time": 5,
        "voice": "the most demanding, still fair and precisely worded",
    },
    "sunday": {
        "candidates": 200,
        "time": 5,
        "voice": "roomy, playful, and connected by a light theme",
    },
}

# The first locally playable weekday recipes are intentionally honest about
# what the current full-size builder can express: themed answer entries and a
# standard letter grid.  These settings steer both model prompts and the
# number of theme locks passed to xfill; they are not review or playability
# gates.
_WEEKDAY_RECIPES = {
    "monday": {
        "id": "monday-private-v1",
        "intent": "Clear clues and approachable theme entries aim to offer several early footholds.",
        "themeAnswerCount": 3,
        "themeDirection": "Choose a small, immediately legible cluster with familiar answer forms and a clear shared connection.",
        "clueDirection": "Favor direct senses, clear signals, and gentle wordplay. Give unfamiliar answers especially accessible footholds.",
        "themeMode": "approachable-cluster",
    },
    "tuesday": {
        "id": "tuesday-private-v1",
        "intent": "Familiar material with a visible layer of fair second readings makes Tuesday a clear step beyond Monday while preserving dependable footholds.",
        "themeAnswerCount": 5,
        "themeDirection": "Choose a coherent cluster of up to five approachable answers whose connection is discoverable after one or two entries; let the pattern add a little lift without requiring specialist trivia.",
        "clueDirection": "Use alternate senses, conversational surfaces, and several fair second readings. Keep a small set of direct footholds, then prefer less literal but precise surfaces so the board does not read like Monday with different answers. Make at least forty clues visibly use a fair second reading, pun, fill-in, bracketed cue, quotation, spoken equivalent, language signal, or abbreviation across at least five distinct surface families, and aim for roughly three-quarters of the board to carry one of those signals. Do not rely on obscure trivia.",
        "themeMode": "approachable-cluster-with-a-turn",
        "minimumNonDefinitionFamilies": 5,
        # Tuesday should feel like a real step beyond Monday even when the
        # model happens to return fluent direct definitions.  Keep the five
        # family floor, and require the denser surface target that makes a
        # Tuesday feel like a real step beyond Monday even on a fluent model
        # run. The target remains a construction direction, not a semantic or
        # player-difficulty guarantee.
        "minimumNonDefinitionCount": 40,
        "requiredNonDefinitionFamilySet": _DIVERSITY_FAMILY_ORDER,
        # The count floor protects small fixture boards. On a full 15x15,
        # the editorial contract asks for roughly three-quarters of the visible
        # surfaces to carry a fair convention or second reading so
        # Tuesday does not collapse into Monday-style direct definitions.
        "targetNonDefinitionRate": 0.72,
    },
    "wednesday": {
        "id": "wednesday-private-v1",
        "intent": "Varied clues and fair misdirection aim for a satisfying middle-distance solve with dependable crossings.",
        "themeAnswerCount": 4,
        "themeDirection": "Choose a varied but coherent cluster whose relationship is inferable with a little thought; avoid obscure trivia.",
        "clueDirection": "Mix clue forms and use fair semantic misdirection while preserving clear footholds and dependable crossings.",
        "themeMode": "inferable-cluster",
    },
    "thursday": {
        "id": "thursday-private-v1",
        "intent": "Layered clues and a connected theme aim to reward spotting a pattern; this recipe uses a standard letter grid.",
        "themeAnswerCount": 5,
        "themeDirection": "Choose several theme answers connected by one surprising but inferable pattern. The grid uses ordinary letters only; do not rely on rebus or special-cell mechanics.",
        "clueDirection": "Use layered, lateral clues for the shared theme while keeping ordinary clues trustworthy and the pattern inferable from multiple entries.",
        "themeMode": "shared-affix-when-validated",
    },
    "friday": {
        "id": "friday-private-v1",
        "intent": "A fluent, less literal private Friday uses expressive entries and precise misdirection while keeping a few clean ways in.",
        "themeAnswerCount": 3,
        "themeDirection": "Choose a loose cluster of three or four expressive, clueable answers with a light connection; let the entries feel fresh without requiring specialist trivia or a hidden theme rule.",
        "clueDirection": "Use indirect but precise wording, alternate parts of speech, collocations, and clean question-mark wordplay. Keep several direct footholds and generous crossings so the difficulty comes from language, not inaccessible facts.",
        "themeMode": "long-form-cluster",
    },
    "saturday": {
        "id": "saturday-private-v1",
        "intent": "The most demanding private day uses economical, layered clues and patient crossings while preserving fair routes into the grid.",
        "themeAnswerCount": 3,
        "themeDirection": "Choose a compact cluster of clueable answers whose connection is optional rather than a required trick; favor vivid language over obscure names or unsupported facts.",
        "clueDirection": "Use the most oblique fair wording in the weekday set: compact surfaces, layered second readings, and restrained wordplay. Preserve a small set of direct footholds and never make a clue difficult by repeating an answer or inventing trivia.",
        "themeMode": "dense-cluster",
    },
    "sunday": {
        "id": "sunday-private-v1",
        "intent": "A larger, roomy themed journey keeps midweek clue density while giving the theme space to breathe.",
        "themeAnswerCount": 4,
        "themeDirection": "Choose a broad, connected cluster that can sustain a larger Sunday grid; let the theme feel discoverable without requiring specialist trivia.",
        "clueDirection": "Keep the clue voice around Wednesday difficulty: varied, fair, and playful, with extra room coming from the 21×21 grid rather than arbitrary obscurity.",
        "themeMode": "large-themed-journey",
    },
}


def _weekday_recipe(weekday):
    recipe = _WEEKDAY_RECIPES.get(weekday)
    if recipe is not None:
        return recipe
    return {
        "id": f"{weekday}-private-v1",
        "intent": f"A locally made {weekday.title()} crossword shaped by its selected clue voice.",
        "themeAnswerCount": 4,
        "themeDirection": "Choose a coherent, clueable theme cluster.",
        "clueDirection": "Follow the selected weekday clue voice.",
        "themeMode": "coherent-cluster",
    }


def _effective_weekday_recipe(weekday, context=None):
    """Apply explicit difficulty feedback without rewriting the base recipe.

    A player pulse of ``harder-stretch`` is represented upstream as the
    reversible ``gentle-stretch`` play calibration recommendation.  For
    Tuesday, make that signal concrete by asking for a little more visible
    clue-language variety.  The default recipe and every other day remain
    unchanged; this is a difficulty control, never a taste or mastery claim.
    """
    recipe = dict(_weekday_recipe(weekday))
    calibration = context.get("play_calibration") if isinstance(context, Mapping) else None
    if weekday != "tuesday" or not isinstance(calibration, Mapping):
        return recipe
    if calibration.get("recommendation") != "gentle-stretch":
        return recipe
    recipe["difficultyVariant"] = "gentle-stretch"
    recipe["intent"] = (
        f"{recipe['intent']} An explicit stretch signal asks for a slightly denser "
        "layer of fair second readings."
    )
    recipe["clueDirection"] = (
        f"{recipe['clueDirection']} For this gentle stretch, favor a little more "
        "indirect but precise wording while preserving footholds."
    )
    recipe["minimumNonDefinitionCount"] = max(
        int(recipe.get("minimumNonDefinitionCount", 0)), 44
    )
    recipe["targetNonDefinitionRate"] = max(
        float(recipe.get("targetNonDefinitionRate", 0.0)), 0.80
    )
    return recipe


def _error(message, status):
    response = jsonify(error=message)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _local_origin():
    origin = request.headers.get("Origin")
    return origin is not None and origin == request.host_url.rstrip("/")


def _response_json(response, *, lenient=False):
    if len(response.content) > MAX_OLLAMA_RESPONSE_BYTES:
        raise ValueError("Local model response is too large")
    response.raise_for_status()
    value = response.json()
    content = (
        value.get("message", {}).get("content") if isinstance(value, dict) else None
    )
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Local model response is empty")
    if not lenient:
        return json.loads(content)
    value, _salvaged = _lenient_json_loads(content)
    return value


def _extract_json_candidate(content):
    """Return the most plausible JSON document span inside model prose.

    Strict parsing always runs first; this only runs after it fails. It
    strips markdown fences, then brace-matches from the first ``{`` while
    respecting string literals. Returns None when no balanced span exists.
    Truncated JSON is never completed — guessing the model's ending would
    fabricate clue text.
    """
    if not isinstance(content, str):
        return None
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence and fence.group(1).strip():
        text = fence.group(1).strip()
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _lenient_json_loads(content):
    """Parse JSON strictly first, then from an extracted document span.

    Returns ``(value, salvaged)`` where salvaged flags the lenient path.
    Raises the original error when nothing parses, so callers that cannot
    use partial content keep their existing fallback reason.
    """
    try:
        return json.loads(content), False
    except (ValueError, TypeError) as strict_error:
        candidate = _extract_json_candidate(content)
        if candidate is None:
            raise strict_error
        return json.loads(candidate), True


_EXPLICIT_MODEL_TAGS = (
    "gemma4:26b",
    "qwen3.8:27b",
    "gemma4:31b",
    "gemma3:27b",
    "llama3.2:3b",
    "gemma3:4b",
)

# Model tiers: large tags exceed a 16 GB host and only run where ~15-18 GB
# of weights fit; local-small tags are the lane this host can run. Order
# matters: selection prefers large where installed (quality incumbents keep
# their default) and falls through to local-small where large do not fit.
# The fixture tier carries no tag; synthetic doubles run without a model.
_MODEL_TIERS = {
    "large": ("gemma4:26b", "qwen3.8:27b", "gemma4:31b", "gemma3:27b"),
    "local-small": ("llama3.2:3b", "gemma3:4b"),
    "fixture": (),
}

# Steady-state resident bytes including KV cache, per tag. Large tags exceed
# this host's ~10.2 GiB Metal budget; that is an admissibility fact, not a
# quality ranking.
_MODEL_MEMORY_CEILINGS = {
    "gemma4:26b": 18_000_000_000,
    "qwen3.8:27b": 18_000_000_000,
    "gemma4:31b": 20_000_000_000,
    "gemma3:27b": 18_000_000_000,
    "llama3.2:3b": 3_000_000_000,
    "gemma3:4b": 4_500_000_000,
}

# Explicit sampling parameters per tier, sent on every /api/chat call.
# Temperature stays per call (0.2 challenger … 0.8 theme proposal) because it
# encodes the call's role, not the tier; top_p stays host-default in both
# tiers. num_ctx is pinned only for local-small, whose whole-board
# structured JSON needs the room; the large path keeps its proven host
# defaults untouched. Seed is per-call random until Q07 passes per-candidate
# seeds for comparison ranking.
_TIER_SAMPLING = {
    "large": {"topP": None, "numCtx": None, "seed": None},
    "local-small": {"topP": None, "numCtx": 8192, "seed": None},
    "fixture": {"topP": None, "numCtx": None, "seed": None},
}


def _model_tier(model) -> str:
    """Return the registry tier for a tag, or unlisted for unknown tags."""
    normalized = model.casefold() if isinstance(model, str) else ""
    for tier, tags in _MODEL_TIERS.items():
        if normalized in [tag.casefold() for tag in tags]:
            return tier
    return "unlisted"


def _tier_sampling(model) -> dict:
    """Return the explicit sampling defaults for a tag's tier."""
    return dict(_TIER_SAMPLING.get(_model_tier(model), _TIER_SAMPLING["large"]))

# Large local models do not have the same useful latency envelope. Keep the
# generic policy conservative, give the installed Gemma path a shorter
# structured-output budget, and make Qwen's optional repair passes bounded
# enough that a slow decode cannot turn a playable private board into a
# multi-minute request. Tuesday's required surface-family pass remains an
# exception even after batching. These are execution budgets, never quality
# scores.
_MODEL_GENERATION_POLICIES = {
    "default": {
        "themeTimeout": 90,
        "primaryClueTimeout": 180,
        "clueTokensPerEntry": 56,
        "riskRepairMaxEntries": 20,
        "repairTimeout": 90,
        "diversityTimeout": 90,
        "challengeTimeout": 90,
        "tuesdayDiversityAttempts": 4,
        "tuesdayPostSafetyRepair": True,
        "qwenClueBatchThreshold": 48,
        "qwenClueBatchSize": 24,
        "qwenClueBatchTimeout": 60,
        "qwenClueBatchTokensPerEntry": 40,
        "qwenClueBatchMaxTokens": 1400,
        "qwenSkipOptionalRepairsAfterBatch": True,
        "candidateDraftRounds": 4,
        "candidateBatchSize": 24,
        "candidateDraftTokensPerEntry": 60,
        "candidateDraftTemperature": 0.7,
        "candidateCompareTokens": 200,
        "candidateCompareTemperature": 0.2,
        "candidateRedraftRounds": 1,
    },
    "gemma4:26b": {
        "themeTimeout": 90,
        "primaryClueTimeout": 180,
        # Gemma's structured decoder spends a noticeable tail on unused
        # output budget for full boards. Keep enough room for concise
        # crossword surfaces and the exact id envelope; the same host
        # validators and bounded Tuesday repair still decide what reaches
        # the player.
        "clueTokensPerEntry": 48,
        "riskRepairMaxEntries": 12,
        "repairTimeout": 90,
        "diversityTimeout": 90,
        "challengeTimeout": 90,
        "tuesdayDiversityAttempts": 4,
        "tuesdayPostSafetyRepair": True,
        "qwenClueBatchThreshold": 48,
        "qwenClueBatchSize": 24,
        "qwenClueBatchTimeout": 60,
        "qwenClueBatchTokensPerEntry": 40,
        "qwenClueBatchMaxTokens": 1400,
        "qwenSkipOptionalRepairsAfterBatch": True,
    },
    "qwen3.8:27b": {
        "themeTimeout": 75,
        "primaryClueTimeout": 120,
        "clueTokensPerEntry": 56,
        "riskRepairMaxEntries": 20,
        "repairTimeout": 60,
        "diversityTimeout": 60,
        "challengeTimeout": 60,
        # One initial diversity pass plus one follow-up is enough to preserve
        # a chance at the Tuesday floor without replaying the same slow model
        # call three more times.
        "tuesdayDiversityAttempts": 2,
        "tuesdayPostSafetyRepair": False,
        "qwenClueBatchThreshold": 48,
        "qwenClueBatchSize": 24,
        "qwenClueBatchTimeout": 60,
        "qwenClueBatchTokensPerEntry": 40,
        "qwenClueBatchMaxTokens": 1400,
        "qwenSkipOptionalRepairsAfterBatch": True,
    },
    # Local-small tags decode fast enough that the generic budgets hold; the
    # entries below make the choice deliberate rather than inherited, so a
    # future tuning pass has a named place to record measured per-tag costs.
    "llama3.2:3b": {
        "themeTimeout": 90,
        "primaryClueTimeout": 180,
        "clueTokensPerEntry": 56,
        "riskRepairMaxEntries": 20,
        "repairTimeout": 90,
        "diversityTimeout": 90,
        "challengeTimeout": 90,
        "tuesdayDiversityAttempts": 4,
        "tuesdayPostSafetyRepair": True,
        "qwenClueBatchThreshold": 48,
        "qwenClueBatchSize": 24,
        "qwenClueBatchTimeout": 60,
        "qwenClueBatchTokensPerEntry": 40,
        "qwenClueBatchMaxTokens": 1400,
        "qwenSkipOptionalRepairsAfterBatch": True,
        "candidateDraftRounds": 4,
        "candidateBatchSize": 24,
        "candidateDraftTokensPerEntry": 60,
        "candidateDraftTemperature": 0.7,
        "candidateCompareTokens": 200,
        "candidateCompareTemperature": 0.2,
        "candidateRedraftRounds": 1,
    },
    "gemma3:4b": {
        "themeTimeout": 90,
        "primaryClueTimeout": 180,
        "clueTokensPerEntry": 56,
        "riskRepairMaxEntries": 20,
        "repairTimeout": 90,
        "diversityTimeout": 90,
        "challengeTimeout": 90,
        "tuesdayDiversityAttempts": 4,
        "tuesdayPostSafetyRepair": True,
        "qwenClueBatchThreshold": 48,
        "qwenClueBatchSize": 24,
        "qwenClueBatchTimeout": 60,
        "qwenClueBatchTokensPerEntry": 40,
        "qwenClueBatchMaxTokens": 1400,
        "qwenSkipOptionalRepairsAfterBatch": True,
        "candidateDraftRounds": 4,
        "candidateBatchSize": 24,
        "candidateDraftTokensPerEntry": 60,
        "candidateDraftTemperature": 0.7,
        "candidateCompareTokens": 200,
        "candidateCompareTemperature": 0.2,
        "candidateRedraftRounds": 1,
    },
}


def _model_generation_policy(model):
    """Return a bounded local execution policy for a selected model tag."""
    if isinstance(model, str):
        normalized = model.casefold()
        if normalized == "qwen3.8:27b":
            return dict(_MODEL_GENERATION_POLICIES["qwen3.8:27b"])
        if normalized == "gemma4:26b":
            return dict(_MODEL_GENERATION_POLICIES["gemma4:26b"])
        if normalized in ("llama3.2:3b", "gemma3:4b"):
            return dict(_MODEL_GENERATION_POLICIES[normalized])
    return dict(_MODEL_GENERATION_POLICIES["default"])


def _model_runtime_policy_receipt(model):
    """Expose execution limits without implying a model-quality ranking."""
    policy = _model_generation_policy(model)
    return {
        "version": "private-model-runtime-policy-v1",
        "model": model,
        "themeTimeoutSeconds": policy["themeTimeout"],
        "primaryClueTimeoutSeconds": policy["primaryClueTimeout"],
        "clueTokensPerEntry": policy["clueTokensPerEntry"],
        "riskRepairMaxEntries": policy["riskRepairMaxEntries"],
        "repairTimeoutSeconds": policy["repairTimeout"],
        "diversityTimeoutSeconds": policy["diversityTimeout"],
        "challengeTimeoutSeconds": policy["challengeTimeout"],
        "tuesdayDiversityAttempts": policy["tuesdayDiversityAttempts"],
        "tuesdayPostSafetyRepair": policy["tuesdayPostSafetyRepair"],
        "qwenClueBatchThreshold": policy["qwenClueBatchThreshold"],
        "qwenClueBatchSize": policy["qwenClueBatchSize"],
        "qwenClueBatchTimeoutSeconds": policy["qwenClueBatchTimeout"],
        "qwenClueBatchTokensPerEntry": policy["qwenClueBatchTokensPerEntry"],
        "qwenClueBatchMaxTokens": policy["qwenClueBatchMaxTokens"],
        "qwenSkipOptionalRepairsAfterBatch": policy[
            "qwenSkipOptionalRepairsAfterBatch"
        ],
        "tuesdayDiversityRequiredAfterBatch": True,
        "tier": _model_tier(model),
        "memoryCeilingBytes": _MODEL_MEMORY_CEILINGS.get(
            model.casefold() if isinstance(model, str) else ""
        ),
        "sampling": {
            **_tier_sampling(model),
            "temperaturePolicy": "per-call role (0.2 challenger … 0.8 theme proposal)",
        },
        "interpretation": "execution-budget-only",
        "qualityClaim": "none",
    }


def _saved_model_override(starting):
    """Return a validated profile model preference, if one was saved.

    Older profiles omit this field and retain automatic host selection. The
    request's explicit ``model`` still wins; this helper only supplies the
    default for clients that rely on the persisted profile setting.
    """
    profile = starting.profile if isinstance(starting.profile, Mapping) else {}
    preference = profile.get("modelPreference")
    return preference if preference in _EXPLICIT_MODEL_TAGS else None


def _ollama_installed_models():
    try:
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=(2, 4))
        response.raise_for_status()
        return {
            item.get("name")
            for item in response.json().get("models", [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
    except (requests.RequestException, ValueError, TypeError):
        raise RuntimeError("Ollama is unavailable on this device") from None


def _installed_model():
    installed = _ollama_installed_models()
    preferred = [
        os.environ.get("CROSSWORD_PUZZLE_MODEL"),
        os.environ.get("CROSSWORD_PROFILE_MODEL"),
        *_EXPLICIT_MODEL_TAGS,
    ]
    model = next((name for name in preferred if name and name in installed), None)
    if model is None:
        admissible = ", ".join(_EXPLICIT_MODEL_TAGS)
        raise RuntimeError(
            "No admissible local model is installed. This host can run the "
            f"local-small tier (llama3.2:3b, gemma3:4b); the large tier needs "
            f"~15-18 GB of weights, past a 16 GB host. Install one with "
            f"`ollama pull <tag>`. Admissible tags: {admissible}"
        )
    return model


def _resolve_model_override(value):
    """Resolve an optional browser-selected model against local Ollama state.

    The browser can ask for one of the supported local tags, but it cannot
    smuggle an arbitrary model name into the prompt boundary.  ``None`` keeps
    the existing environment-preferred selection behavior.
    """
    if value is None:
        return _installed_model()
    if not isinstance(value, str) or value not in _EXPLICIT_MODEL_TAGS:
        raise ValueError("Unsupported local writing model")
    if value not in _ollama_installed_models():
        raise RuntimeError(f"Install {value} in Ollama before selecting it")
    return value


def _learning_review_outcomes(starting, evidence, language_code):
    """Resolve local recall records back to source answer forms.

    Review rows intentionally store an opaque task handle.  The source form is
    recovered only inside the local generation brief by replaying the same
    evidence links that created that handle.  Missing profile context or an
    unavailable review table leaves the older exposure-only behavior intact.
    """
    profile_id = getattr(starting, "id", None)
    if not isinstance(profile_id, str) or not _UUID.fullmatch(profile_id):
        return None
    if not isinstance(evidence, list) or not language_code:
        return None
    try:
        from .learning_review import (
            FutureLearningReviewRecord,
            _due,
            _review_task_id,
        )

        records = FutureLearningReviewRecord.query.filter_by(
            profile_id=profile_id
        ).all()
    except (RuntimeError, AttributeError):
        # Unit-level context construction can run without Flask's app context.
        return None
    latest = {}
    for record in records:
        previous = latest.get(record.task_id)
        if previous is None or record.recorded_at > previous.recorded_at:
            latest[record.task_id] = record

    outcome_forms = {
        "pending": [],
        "notYet": [],
        "assisted": [],
        "remembered": [],
        # This is a construction hint, not a new mastery state.  It contains
        # forms whose host scheduler says are due now, including a previously
        # remembered form that has reached its next interval.
        "due": [],
        # Bounded scheduler metadata used only to order optional construction
        # candidates.  It is never a mastery estimate or a placement lock.
        "dueDetails": [],
    }
    seen = set()
    for item in reversed(evidence):
        if not isinstance(item, dict) or item.get("type") != "session-analysis":
            continue
        evidence_id = item.get("evidenceId")
        if not isinstance(evidence_id, str) or not evidence_id:
            continue
        links = item.get("taskLinks", [])
        for link in links if isinstance(links, list) else []:
            tasks = link.get("tasks", []) if isinstance(link, dict) else []
            for task in tasks if isinstance(tasks, list) else []:
                if not isinstance(task, dict) or task.get("language") != language_code:
                    continue
                source_task_id = task.get("taskId")
                if not isinstance(source_task_id, str) or not source_task_id.startswith(
                    "private-answer-form:"
                ):
                    continue
                answer = source_task_id.removeprefix("private-answer-form:")
                if not answer or answer in seen:
                    continue
                seen.add(answer)
                review_id = _review_task_id(profile_id, evidence_id, source_task_id)
                record = latest.get(review_id)
                if record is None:
                    outcome_forms["pending"].append(answer)
                elif record.response == "not-yet":
                    outcome_forms["notYet"].append(answer)
                elif record.input_mode == "assisted":
                    outcome_forms["assisted"].append(answer)
                elif record.response == "remembered":
                    outcome_forms["remembered"].append(answer)
    # The scheduler owns due-ness and interval policy.  Reuse its opaque queue
    # rather than reimplementing timestamps here; a due form is still only an
    # optional candidate for the next native fill.
    try:
        due_items = _due(profile_id)
    except Exception:
        # Context construction is also used by small unit-level callers that
        # do not have the learning tables available.  In that case retain the
        # exposure-only behavior above.
        due_items = []
    answer_by_task = {}
    due_details = []
    for item in due_items:
        source_task_id = item.get("sourceTaskId") if isinstance(item, dict) else None
        if not isinstance(source_task_id, str) or not source_task_id.startswith(
            "private-answer-form:"
        ):
            continue
        answer = source_task_id.removeprefix("private-answer-form:")
        if answer and answer not in answer_by_task.values():
            answer_by_task[item.get("taskId")] = answer
            stage = item.get("reviewStage")
            interval_hours = item.get("intervalHours")
            last_response = item.get("lastResponse")
            last_mode = item.get("lastMode")
            if type(stage) is int and 0 <= stage <= 12:
                detail = {
                    "form": answer,
                    "reviewStage": stage,
                }
                if type(interval_hours) is int and interval_hours > 0:
                    detail["intervalHours"] = min(interval_hours, 24 * 365)
                if last_response in {"remembered", "not-yet", "pass"}:
                    detail["lastResponse"] = last_response
                if last_mode in {"independent", "assisted"}:
                    detail["lastMode"] = last_mode
                overdue_hours = item.get("overdueHours")
                if isinstance(overdue_hours, (int, float)) and not isinstance(
                    overdue_hours, bool
                ) and overdue_hours >= 0:
                    detail["overdueHours"] = round(float(overdue_hours), 3)
                scheduler_priority = item.get("schedulerPriority")
                if isinstance(scheduler_priority, (int, float)) and not isinstance(
                    scheduler_priority, bool
                ) and scheduler_priority >= 0:
                    detail["schedulerPriority"] = round(float(scheduler_priority), 3)
                due_details.append(detail)
    outcome_forms["due"] = list(answer_by_task.values())[:12]
    outcome_forms["dueDetails"] = due_details[:12]
    return outcome_forms


def _playtest_calibration(evidence):
    """Collect at most six complete game pulses without interpreting them."""
    groups = {}
    for item in reversed(evidence if isinstance(evidence, list) else []):
        if not isinstance(item, dict) or item.get("type") != "performance":
            continue
        measure = item.get("measure")
        if measure not in {
            "playtest-worth",
            "playtest-return",
            "playtest-rough-edge",
        }:
            continue
        evidence_id = item.get("evidenceId")
        if not isinstance(evidence_id, str) or not evidence_id.startswith(
            "playtest-pulse:"
        ):
            continue
        parts = evidence_id.split(":")
        if len(parts) != 3:
            continue
        expected_measure = {
            "playtest-worth": "worth",
            "playtest-return": "return",
            "playtest-rough-edge": "rough-edge",
        }
        if parts[2] != expected_measure[measure]:
            continue
        session_id = item.get("sessionId")
        if not isinstance(session_id, str) or not session_id:
            continue
        values = groups.setdefault((session_id, parts[1]), {})
        key = {
            "playtest-worth": "worth",
            "playtest-return": "returnIntent",
            "playtest-rough-edge": "roughEdge",
        }[measure]
        if isinstance(item.get("value"), str):
            values[key] = item["value"]
    complete = []
    for (session_id, pulse_id), values in groups.items():
        if set(values) != {"worth", "returnIntent", "roughEdge"}:
            continue
        complete.append({"sessionId": session_id, "pulseId": pulse_id, **values})
        if len(complete) >= 6:
            break
    return complete


def _play_calibration(evidence):
    """Summarize recent solve behavior as a narrow difficulty signal.

    Solve evidence is useful for choosing how much scaffolding to ask the
    local model for, but it is not evidence about taste, identity, or mastery.
    Keep the summary small, deterministic, and capped so one noisy session
    cannot swing the next board.
    """
    if not isinstance(evidence, list):
        return {
            "status": "no-history",
            "source": "solve-behavior",
            "interpretation": "difficulty-only",
            "reversible": True,
        }
    summaries = []
    for item in reversed(evidence):
        if not isinstance(item, dict) or item.get("type") != "session-analysis":
            continue
        analysis = item.get("analysis")
        observations = (
            analysis.get("observations") if isinstance(analysis, dict) else None
        )
        if not isinstance(observations, list) or not observations:
            continue
        observations = [entry for entry in observations if isinstance(entry, dict)]
        if not observations:
            continue
        total = len(observations)
        correct = sum(entry.get("finalState") == "correct" for entry in observations)
        independent = sum(
            entry.get("outcome") == "independent-retrieval" for entry in observations
        )
        supported = sum(
            entry.get("outcome")
            in {
                "supported-retrieval",
                "check-assisted-correction",
                "reveal-assisted-correction",
            }
            for entry in observations
        )
        incorrect = sum(
            int(entry.get("incorrectAttemptCount", 0))
            for entry in observations
            if isinstance(entry.get("incorrectAttemptCount", 0), int)
        )
        summaries.append(
            {
                "completionRate": round(correct / total, 3),
                "independentRate": round(independent / total, 3),
                "supportRate": round(supported / total, 3),
                "mistakeRate": round(min(1.0, incorrect / max(1, total)), 3),
                "entryCount": total,
            }
        )
        if len(summaries) >= 6:
            break
    playtests = _playtest_calibration(evidence)
    if not summaries:
        return {
            "status": "no-history",
            "source": "solve-behavior",
            "interpretation": "difficulty-only",
            "reversible": True,
        }
    count = len(summaries)
    averages = {
        key: round(sum(item[key] for item in summaries) / count, 3)
        for key in ("completionRate", "independentRate", "supportRate", "mistakeRate")
    }
    if averages["supportRate"] >= 0.45 or averages["completionRate"] < 0.55:
        recommendation = "more-footholds"
    elif (
        averages["completionRate"] >= 0.82
        and averages["supportRate"] <= 0.18
        and averages["mistakeRate"] <= 0.15
    ):
        recommendation = "gentle-stretch"
    else:
        recommendation = "balanced"
    result = {
        "status": "calibrated",
        "source": "solve-behavior",
        "interpretation": "difficulty-only",
        "reversible": True,
        "sessions": count,
        **averages,
        "recommendation": recommendation,
        "recent": summaries,
    }
    if playtests:
        worth_counts = {}
        return_counts = {}
        rough_edge_counts = {}
        for pulse in playtests:
            for key, counts in (
                ("worth", worth_counts),
                ("returnIntent", return_counts),
                ("roughEdge", rough_edge_counts),
            ):
                value = pulse.get(key)
                if isinstance(value, str):
                    counts[value] = counts.get(value, 0) + 1
        asks_for_footholds = any(
            pulse.get("returnIntent") == "more-footholds"
            or pulse.get("roughEdge")
            in {"too-opaque", "too-obscure", "crossings-unhelpful"}
            for pulse in playtests
        )
        asks_for_stretch = any(
            pulse.get("returnIntent") == "harder-stretch"
            or pulse.get("roughEdge") == "too-easy"
            for pulse in playtests
        )
        if asks_for_footholds:
            result["recommendation"] = "more-footholds"
        elif asks_for_stretch and result["recommendation"] != "more-footholds":
            result["recommendation"] = "gentle-stretch"
        result["source"] = "solve-behavior+playtest-pulse"
        result["playtest"] = {
            "sessionCount": len(playtests),
            "worthCounts": dict(sorted(worth_counts.items())),
            "returnIntentCounts": dict(sorted(return_counts.items())),
            "roughEdgeCounts": dict(sorted(rough_edge_counts.items())),
            "interpretation": "game-specific-calibration-only",
            "reversible": True,
        }
    return result


def _recent_clue_family_exposures(evidence):
    """Count recent literal clue-family surfaces for gentle rotation.

    Finished-session task links are already profile-owned evidence. This
    projection only counts their bounded surface labels, never answers,
    meanings, or inferred taste. It is a construction hint so a run of
    question-mark or bracketed clues can cool temporarily; explicit authored
    clue-family targets still outrank it and no family is ever suppressed.
    """
    counts = {}
    session_count = 0
    task_count = 0
    if not isinstance(evidence, list):
        evidence = []
    for item in reversed(evidence):
        if not isinstance(item, dict) or item.get("type") != "session-analysis":
            continue
        links = item.get("taskLinks")
        if not isinstance(links, list):
            continue
        seen_in_session = False
        for link in links:
            tasks = link.get("tasks", []) if isinstance(link, dict) else []
            for task in tasks if isinstance(tasks, list) else []:
                if not isinstance(task, dict):
                    continue
                family = task.get("surfaceFamily") or task.get("clueFamily")
                if not isinstance(family, str) or not family:
                    continue
                counts[family] = counts.get(family, 0) + 1
                task_count += 1
                seen_in_session = True
                if task_count >= 48:
                    break
            if task_count >= 48:
                break
        if seen_in_session:
            session_count += 1
        if session_count >= 8 or task_count >= 48:
            break
    return {
        "version": "private-clue-family-fatigue-v1",
        "source": "finished-session-analysis",
        "sessions": session_count,
        "taskCount": task_count,
        "counts": dict(sorted(counts.items())),
        "policy": "rotation-hint-only",
        "reversible": True,
        "uncertainty": ["surface-family-only", "not-a-preference-claim"],
    }


def _profile_context(starting, episteme):
    """Give the model a bounded word-field, not a personality diagnosis."""
    projection = episteme.get("projection", {}) if isinstance(episteme, dict) else {}
    seed_profile = starting.profile if isinstance(starting.profile, dict) else {}
    claims = projection.get("claims", []) if isinstance(projection, dict) else []
    associations = (
        projection.get("associations", []) if isinstance(projection, dict) else []
    )
    knowledge = projection.get("knowledge", []) if isinstance(projection, dict) else []
    reflection_signal_ids = {
        item.get("evidenceId")
        for item in (episteme.get("evidence", []) if isinstance(episteme, dict) else [])
        if isinstance(item, dict)
        and item.get("type") == "preference-signal"
        and item.get("source") == "reflection-card"
        and isinstance(item.get("evidenceId"), str)
    }
    recent_private_answers = []
    evidence = episteme.get("evidence", []) if isinstance(episteme, dict) else []
    if isinstance(evidence, list):
        for item in reversed(evidence):
            if not isinstance(item, dict) or item.get("type") != "session-analysis":
                continue
            links = item.get("taskLinks", [])
            if not isinstance(links, list):
                continue
            for link in links:
                tasks = link.get("tasks", []) if isinstance(link, dict) else []
                for task in tasks if isinstance(tasks, list) else []:
                    task_id = task.get("taskId") if isinstance(task, dict) else None
                    if isinstance(task_id, str) and task_id.startswith(
                        "private-answer-form:"
                    ):
                        answer = task_id.removeprefix("private-answer-form:")
                        if answer and answer not in recent_private_answers:
                            recent_private_answers.append(answer)
                        if len(recent_private_answers) >= 24:
                            break
                if len(recent_private_answers) >= 24:
                    break
            if len(recent_private_answers) >= 24:
                break
    preference_tensions = [
        {
            "concept": (item.get("concept") or {}).get("label"),
            "kind": item.get("kind"),
            "stance": item.get("stance"),
        }
        for item in claims[:24]
        if isinstance(item, dict)
    ]
    avoid_topics = [
        item["concept"]
        for item in preference_tensions
        if isinstance(item.get("concept"), str)
        and item.get("stance") in {"avoid", "dislike", "turn-away", "not-for-me"}
    ][:12]
    clue_family_targets = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        concept = claim.get("concept")
        concept_id = concept.get("conceptId") if isinstance(concept, dict) else None
        family = _REFLECTION_CLUE_FAMILIES.get(concept_id)
        stance = claim.get("stance")
        evidence_ids = claim.get("evidenceIds")
        strength = claim.get("strength")
        claim_reflection_ids = [
            evidence_id
            for evidence_id in (evidence_ids if isinstance(evidence_ids, list) else [])
            if evidence_id in reflection_signal_ids
        ]
        if (
            family is None
            or stance not in {"seek", "avoid"}
            or not isinstance(evidence_ids, list)
            or not claim_reflection_ids
            or not isinstance(strength, (int, float))
            or not 0 < strength <= 1
        ):
            continue
        clue_family_targets.append(
            {
                "family": family,
                "direction": "include" if stance == "seek" else "avoid",
                "strength": round(float(strength), 3),
                "evidenceCount": min(8, len(claim_reflection_ids)),
                # This signal comes only from an authored card response and
                # can be reversed by the card's retract/restore action.
                "source": "reviewed-reflection",
                "reversible": True,
            }
        )
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        concept = claim.get("concept")
        if not isinstance(concept, dict):
            continue
        concept_id = concept.get("conceptId")
        label = concept.get("label")
        if (
            not isinstance(concept_id, str)
            or not concept_id.startswith("association:en:clue%20surfaces%3A")
            or not isinstance(label, str)
        ):
            continue
        family = _EXPLICIT_CLUE_FEEDBACK_FAMILIES.get(
            label.removeprefix("clue surfaces:").strip().casefold()
        )
        stance = claim.get("stance")
        strength = claim.get("strength")
        evidence_ids = claim.get("evidenceIds")
        if (
            family is None
            or stance not in {"seek", "avoid"}
            or not isinstance(strength, (int, float))
            or not 0 < strength <= 1
            or not isinstance(evidence_ids, list)
        ):
            continue
        clue_family_targets.append(
            {
                "family": family,
                "direction": "include" if stance == "seek" else "avoid",
                "strength": round(float(strength), 3),
                "evidenceCount": min(8, len(evidence_ids)),
                "source": "explicit-clue-feedback",
                "reversible": True,
            }
        )
    clue_family_targets.sort(
        key=lambda item: (
            0 if item.get("source") == "explicit-clue-feedback" else 1,
            item["family"],
            item["direction"],
            -item["strength"],
        )
    )
    learning_language = seed_profile.get("learningLanguage")
    language_code = _LANGUAGE_CODES.get(learning_language)
    language_review_forms = []
    if language_code and isinstance(evidence, list):
        for item in reversed(evidence):
            if not isinstance(item, dict) or item.get("type") != "session-analysis":
                continue
            links = item.get("taskLinks", [])
            for link in links if isinstance(links, list) else []:
                tasks = link.get("tasks", []) if isinstance(link, dict) else []
                for task in tasks if isinstance(tasks, list) else []:
                    if (
                        not isinstance(task, dict)
                        or task.get("language") != language_code
                    ):
                        continue
                    task_id = task.get("taskId")
                    if not isinstance(task_id, str) or not task_id.startswith(
                        "private-answer-form:"
                    ):
                        continue
                    answer = task_id.removeprefix("private-answer-form:")
                    if answer and answer not in language_review_forms:
                        language_review_forms.append(answer)
                    if len(language_review_forms) >= 12:
                        break
                if len(language_review_forms) >= 12:
                    break
            if len(language_review_forms) >= 12:
                break
    review_outcomes = _learning_review_outcomes(starting, evidence, language_code)
    starter_forms = []
    if (
        language_code
        and not language_review_forms
        and review_outcomes is None
        and isinstance(learning_language, str)
    ):
        starter_forms = _eligible_language_review_forms(
            _LANGUAGE_STARTER_FORMS.get(learning_language.casefold(), ())
        )[:1]
    due_review_forms = []
    if review_outcomes is not None:
        language_review_forms = []
        for answer in (
            review_outcomes["notYet"]
            + review_outcomes["assisted"]
            + review_outcomes["pending"]
        ):
            if answer not in language_review_forms:
                language_review_forms.append(answer)
            if len(language_review_forms) >= 12:
                break
        due_review_forms = [
            answer
            for answer in review_outcomes.get("due", [])
            if answer not in due_review_forms
        ][:12]
    candidate_review_forms = []
    for answer in due_review_forms + language_review_forms + starter_forms:
        if answer not in candidate_review_forms:
            candidate_review_forms.append(answer)
    language_learning = None
    if language_code:
        language_learning = {
            "language": learning_language,
            "code": language_code,
            "mode": "gentle-recurrence",
            "reviewDue": bool(candidate_review_forms),
            "reviewForms": language_review_forms,
            "exposureCount": len(language_review_forms),
            "source": "explicit-setup",
            "masteryClaim": "none",
            "reversible": True,
        }
        if review_outcomes is not None:
            language_learning.update(
                {
                    "pendingForms": review_outcomes["pending"][:12],
                    "notYetForms": review_outcomes["notYet"][:12],
                    "assistedForms": review_outcomes["assisted"][:12],
                    "rememberedForms": review_outcomes["remembered"][:12],
                    "reviewOutcomeVersion": "language-recall-v1",
                    "dueForms": due_review_forms,
                    "candidateForms": candidate_review_forms[:12],
                    "dueDetails": review_outcomes.get("dueDetails", [])[:12],
                }
            )
        elif starter_forms:
            # A selected language gets one tiny, explicit first thread when a
            # local fill dictionary can support it. This is an unadmitted
            # private starter, never a reviewed translation or a mastery claim;
            # later exposure evidence owns recurrence.
            language_learning.update(
                {
                    "reviewDue": False,
                    "starterForms": starter_forms[:2],
                    "candidateForms": candidate_review_forms[:2],
                    "starterPolicy": "private-language-starter-v1",
                    "starterStatus": "synthetic-unadmitted-not-established",
                }
            )
        candidate_weights = (
            _language_candidate_weights(language_learning)
            if review_outcomes is not None
            else []
        )
        if review_outcomes is not None:
            language_learning["candidateWeights"] = candidate_weights
        eligible_review_forms = _eligible_language_review_forms(
            [item["form"] for item in candidate_weights]
            if review_outcomes is not None
            else candidate_review_forms
        )
        language_learning["eligibleReviewForms"] = eligible_review_forms[:4]
    play_calibration = _play_calibration(evidence)
    clue_family_fatigue = _recent_clue_family_exposures(evidence)
    association_steering = _association_steering_receipt(associations)
    domain_hints = load_private_domain_hints(fill_words=_local_fill_word_set())
    return {
        "opening_associations": seed_profile.get("associations", [])[:24],
        "opening_observations": seed_profile.get("observations", [])[:8],
        "language_interest": seed_profile.get("learningLanguage"),
        "language_learning": language_learning,
        "opening_choices": {
            key: starting.draft.get(key)
            for key in (
                "firstStimulus",
                "object",
                "companion",
                "variation",
                "traces",
                "learningLanguage",
            )
            if starting.draft.get(key) not in (None, [], "None for now")
        },
        "active_associations": [
            {
                "phrase": item.get("phrase"),
                "response": item.get("response"),
                "origin": item.get("origin"),
            }
            for item in associations
            if isinstance(item, dict)
            and not _association_is_expired(item)
            and item.get("response") not in {"rejected", "passed"}
        ][:24],
        "association_steering": association_steering,
        "preference_tensions": preference_tensions,
        "avoid_topics": avoid_topics,
        "clue_family_targets": clue_family_targets[:8],
        "recent_clue_family_exposures": clue_family_fatigue,
        "recent_private_answers": recent_private_answers,
        "domain_hints": domain_hints,
        "play_calibration": play_calibration,
        "recent_word_exposures": [
            {
                "concept": (item.get("task") or {}).get("taskId"),
                "kind": (item.get("task") or {}).get("taskKind"),
                "exposures": (item.get("independent") or {}).get("evidenceCount", 0),
            }
            for item in knowledge[:20]
            if isinstance(item, dict)
        ],
    }


def _association_is_expired(item):
    """Read reducer expiry without turning an association into a diagnosis."""
    if not isinstance(item, dict):
        return False
    for key in ("calibrationProvenance", "modelProvenance"):
        provenance = item.get(key)
        if isinstance(provenance, dict) and provenance.get("expired") is True:
            return True
    return False


def _association_steering_receipt(associations):
    """Return bounded, answer-free association steering provenance.

    Association phrases stay in the private model context, but the puzzle
    receipt only records the reversible status, source and relation lanes.
    Expired or explicitly rejected/passed proposals are excluded from the
    active steering count before generation.
    """
    records = [item for item in (associations if isinstance(associations, list) else [])[:24] if isinstance(item, dict)]
    response_counts = {}
    origin_counts = {}
    relation_counts = {}
    expired_count = 0
    excluded_response_count = 0
    eligible_count = 0
    for item in records:
        response = item.get("response") if item.get("response") in {"kept", "rejected", "passed"} else "untested"
        response_counts[response] = response_counts.get(response, 0) + 1
        origin = item.get("origin") if isinstance(item.get("origin"), str) else "unknown"
        origin_counts[origin] = origin_counts.get(origin, 0) + 1
        relation = item.get("relation") if isinstance(item.get("relation"), str) else "unknown"
        relation_counts[relation] = relation_counts.get(relation, 0) + 1
        expired = _association_is_expired(item)
        if expired:
            expired_count += 1
        if item.get("response") in {"rejected", "passed"}:
            excluded_response_count += 1
        if not expired and item.get("response") not in {"rejected", "passed"}:
            eligible_count += 1
    unique_relations = len([key for key in relation_counts if key != "unknown"])
    return {
        "version": "private-association-steering-v1",
        "projectionCount": len(records),
        "eligibleCount": eligible_count,
        "expiredCount": expired_count,
        "excludedResponseCount": excluded_response_count,
        "responseCounts": dict(sorted(response_counts.items())),
        "originCounts": dict(sorted(origin_counts.items())),
        "relationCounts": dict(sorted(relation_counts.items())),
        "diversity": {
            "uniqueRelations": unique_relations,
            "status": "varied" if unique_relations >= 2 else ("narrow" if records else "none"),
        },
        "reversible": True,
        "interpretation": "bounded-association-steering-not-a-personality-claim",
    }


def _personalization_receipt(episteme, context, *, seed, weekday, model):
    """Return a compact, answer-free receipt for why this board was made.

    The full episteme remains host-owned.  This receipt is safe to carry with
    the private puzzle/job result: it binds the board to one exact profile
    revision and digest, while exposing only bounded category counts and the
    difficulty/language lanes that influenced construction.
    """
    projection = episteme.get("projection", {}) if isinstance(episteme, dict) else {}
    evidence = episteme.get("evidence", []) if isinstance(episteme, dict) else []
    claims = projection.get("claims", []) if isinstance(projection, dict) else []
    associations = projection.get("associations", []) if isinstance(projection, dict) else []
    knowledge = projection.get("knowledge", []) if isinstance(projection, dict) else []
    language_learning = context.get("language_learning") if isinstance(context, dict) else None
    play_calibration = context.get("play_calibration") if isinstance(context, dict) else None
    association_steering = (
        context.get("association_steering")
        if isinstance(context, dict) and isinstance(context.get("association_steering"), dict)
        else _association_steering_receipt(associations)
    )
    domain_hints = private_domain_hint_receipt(
        context.get("domain_hints") if isinstance(context, dict) else None
    )
    return {
        "version": "private-personalization-receipt-v1",
        "profileId": episteme.get("profileId") if isinstance(episteme, dict) else None,
        "epistemeRevision": episteme.get("revision") if isinstance(episteme, dict) else None,
        "epistemeDigest": _digest(episteme),
        "epistemeDigestAlgorithm": "sha256-canonical-json-v1",
        "seed": seed,
        "weekday": weekday,
        "model": model,
        "associationSteering": association_steering,
        "domainHints": domain_hints,
        "inputs": {
            "claimCount": min(len(claims), 24) if isinstance(claims, list) else 0,
            "associationCount": min(len(associations), 24) if isinstance(associations, list) else 0,
            "knowledgeItemCount": min(len(knowledge), 20) if isinstance(knowledge, list) else 0,
            "evidenceCount": min(len(evidence), 64) if isinstance(evidence, list) else 0,
            "clueFamilyTargetCount": min(len(context.get("clue_family_targets", [])), 8)
            if isinstance(context, dict) and isinstance(context.get("clue_family_targets"), list)
            else 0,
            "recentExposureCount": min(len(context.get("recent_private_answers", [])), 24)
            if isinstance(context, dict) and isinstance(context.get("recent_private_answers"), list)
            else 0,
            "languageThread": bool(language_learning),
            "domainHintCount": domain_hints.get("placeableCount", 0),
            "difficultyRecommendation": play_calibration.get("recommendation")
            if isinstance(play_calibration, dict)
            else None,
        },
        "reversible": True,
        "interpretation": "generation-input-receipt-only",
    }


def _theme_exposure_receipt(context, theme_entries):
    """Explain exact-form cooling without exposing answer history in the UI."""
    recent = {
        answer.upper()
        for answer in (
            context.get("recent_private_answers", [])
            if isinstance(context, dict)
            else []
        )
        if isinstance(answer, str) and _ANSWER.fullmatch(answer.upper())
    }
    answers = [
        entry.get("answer", "").upper()
        for entry in (theme_entries if isinstance(theme_entries, list) else [])
        if isinstance(entry, dict)
        and entry.get("theme") is True
        and isinstance(entry.get("answer"), str)
        and _ANSWER.fullmatch(entry["answer"].upper())
    ]
    repeated = sum(answer in recent for answer in answers)
    return {
        "version": "private-theme-exposure-receipt-v1",
        "policy": "cool-exact-recent-answer-forms-when-fresh-candidates-exist",
        "recentExposureCount": min(len(recent), 24),
        "themeAnswerCount": len(answers),
        "freshThemeCount": max(0, len(answers) - repeated),
        "repeatedThemeCount": repeated,
        "reversible": True,
        "interpretation": "recent-exposure-steering-only",
        "masteryClaim": "none",
    }


def _chat(model, messages, schema, *, timeout, tokens, temperature, seed=None, top_p=None, num_ctx=None, lenient=False):
    sampling = _tier_sampling(model)
    if top_p is None:
        top_p = sampling.get("topP")
    if num_ctx is None:
        num_ctx = sampling.get("numCtx")
    if seed is None:
        seed = sampling.get("seed")
    options = {"temperature": temperature, "num_predict": tokens}
    if top_p is not None:
        options["top_p"] = top_p
    if num_ctx is not None:
        options["num_ctx"] = num_ctx
    if seed is not None:
        options["seed"] = seed
    response = requests.post(
        "http://127.0.0.1:11434/api/chat",
        timeout=(2, timeout),
        json={
            "model": model,
            "stream": False,
            "think": False,
            "format": schema,
            "options": options,
            "messages": messages,
        },
    )
    return _response_json(response, lenient=lenient)


def _clue_token_budget(entry_count, *, per_entry=None):
    """Bound clue output without making the model's budget a hidden gate.

    Clues are deliberately short and the structured response repeats the entry
    id, so the old 72-token-per-entry ceiling left a large unused decode tail
    on full-size boards. Keep a host override for unusual local models, but
    clamp it to a range that still leaves enough room for a concise clue set.
    """
    override = os.environ.get("CROSSWORD_PRIVATE_CLUE_TOKENS_PER_ENTRY")
    if isinstance(override, str) and override.strip():
        try:
            per_entry = int(override)
        except (TypeError, ValueError):
            # An invalid host override should leave the model-specific policy
            # intact when one was supplied, while the direct helper retains
            # its historical generic default.
            per_entry = (
                per_entry if per_entry is not None else DEFAULT_CLUE_TOKENS_PER_ENTRY
            )
    elif per_entry is None:
        per_entry = DEFAULT_CLUE_TOKENS_PER_ENTRY
    else:
        try:
            per_entry = int(per_entry)
        except (TypeError, ValueError):
            per_entry = DEFAULT_CLUE_TOKENS_PER_ENTRY
    per_entry = max(32, min(96, per_entry))
    return min(5200, max(1800, entry_count * per_entry))


def _qwen_batched_clue_value(model, base_messages, entries, reviewed_by_id, context):
    """Write a large Qwen clue set in bounded structured batches.

    Qwen's long-board response can spend its whole context/decode budget before
    returning any JSON. Smaller batches preserve exact entry ids and let the
    existing outer validator, repair pass, and answer-safety guard treat the
    combined result exactly like a single response. A failed batch raises so
    the caller uses the established answer-free scaffold for the whole board;
    partial model text is never mixed into a playable clue set.
    """
    policy = _model_generation_policy(model)
    batch_size = policy["qwenClueBatchSize"]
    raw_user = base_messages[1].get("content") if len(base_messages) > 1 else None
    payload = json.loads(raw_user) if isinstance(raw_user, str) else None
    if not isinstance(payload, dict):
        raise ValueError("qwen-clue-batch-prompt-invalid")
    system = base_messages[0]
    combined = []
    title = None
    for offset in range(0, len(entries), batch_size):
        batch = entries[offset : offset + batch_size]
        batch_ids = [
            entry.get("id")
            for entry in batch
            if isinstance(entry, Mapping) and isinstance(entry.get("id"), str)
        ]
        ids = set(batch_ids)
        if not batch_ids:
            continue
        batch_payload = dict(payload)
        batch_payload["entries"] = batch
        batch_payload["groundingBundle"] = _clue_generation_bundle(batch)
        for key in ("reviewedClues", "reviewedContent"):
            records = batch_payload.get(key)
            if isinstance(records, list):
                batch_payload[key] = [
                    record
                    for record in records
                    if isinstance(record, Mapping) and record.get("id") in ids
                ]
        value = _chat(
            model,
            [
                system,
                {
                    "role": "user",
                    "content": json.dumps(
                        batch_payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
            _qwen_clue_batch_schema(),
            timeout=policy["qwenClueBatchTimeout"],
            tokens=min(
                policy["qwenClueBatchMaxTokens"],
                max(600, len(batch) * policy["qwenClueBatchTokensPerEntry"]),
            ),
            temperature=0.65,
        )
        if not isinstance(value, dict) or not isinstance(value.get("clues"), list):
            raise ValueError("qwen-clue-batch-response-invalid")
        if title is None:
            title = value.get("title")
        returned = value["clues"]
        if len(returned) != len(ids):
            raise ValueError("qwen-clue-batch-incomplete")
        combined.extend(returned)
    if title is None:
        raise ValueError("qwen-clue-batch-empty")
    return {"title": title, "clues": combined}


def _qwen_clue_batch_schema():
    """Use a light schema for Qwen batches; host validation stays strict.

    Enumerating every entry id and exact array length in Ollama's constrained
    decoder makes this particular model spend its budget before producing any
    response. The host still enforces the exact id set, text bounds, grammar,
    and answer-safety checks immediately after the batch returns.
    """
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "clues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["id", "text"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["title", "clues"],
        "additionalProperties": False,
    }


def _make_themes(model, context, weekday):
    recipe = _weekday_recipe(weekday)
    schema = {
        "type": "object",
        "properties": {
            "themes": {
                "type": "array",
                "minItems": 2,
                "maxItems": MAX_THEME_WORDS,
                "items": {"type": "string", "pattern": "^[A-Z]{3,15}$"},
            }
        },
        "required": ["themes"],
        "additionalProperties": False,
    }
    value = _chat(
        model,
        [
            {
                "role": "system",
                "content": (
                    "Create a small set of crossword theme answers from this evolving word-field. "
                    f"{recipe['themeDirection']} "
                    "They should feel surprising but recognizable, with at least one bridge from the player's associations. "
                    "Choose answer forms likely to appear in a crossword dictionary. Mostly use ordinary English words, but allow a small minority of proper names or culturally specific terms when the player's word-field clearly invites them and the grid can give fair crossing support; never invent a spelling or identity. "
                    "Do not use accidental slang variants or sexualized fill unless the player's word-field explicitly calls for that register. "
                    "Treat preference tensions as steering: avoid topics listed with an avoid/dislike/turn-away stance, while using seek/keep topics as invitations rather than proof of identity. "
                    "Use clue_family_targets as explicit, reversible editorial steering from authored reflection responses or direct clue feedback: include targets should shape a visible minority of clue surfaces, and avoid targets should reduce that family. Do not invent targets from behavior or silence. "
                    "Use recent_clue_family_exposures only as a small rotation hint: cool a heavily repeated visible surface family when several equally fair options exist, never suppress a family, and never infer that repetition means dislike. Explicit clue-family targets outrank this hint. "
                    "Do not infer a preference from silence, and do not turn the avoid list into a personality diagnosis. "
                    "If language_interest is set, let a small minority of entries or clue surfaces invite that language with an explicit language signal; keep the rest in clear English so the crossword remains playable. "
                    "When language_learning.reviewDue is true, gently revisit no more than two candidateForms when they fit the word-field; dueForms are the first optional candidates, followed by notYetForms, assistedForms, and pendingForms. A remembered form may re-enter candidateForms only after the host scheduler marks it due. This is spaced exposure only and never evidence that the player has mastered them. When reviewDue is false, introduce at most two clearly signalled language moments. "
                    "eligibleReviewForms are optional candidates already present in the local fill dictionary; prefer them only when they fit the theme and clue budget, never force them as locks, and never use a missing candidate as evidence of mastery. "
                    "candidateWeights are bounded host hints (higher means earlier optional consideration); due items may also carry a scheduler-history priority that only orders equally due forms. They never require a form to appear in the grid. "
                    "Avoid repeating exact answer forms listed in recent_private_answers when at least two fresh candidates are available; recent exposure is not mastery and a deliberate review is still allowed when the word-field calls for it. "
                    "Use play_calibration only to tune accessibility: more-footholds means favor ordinary answers and clearer crossings, balanced means keep the recipe as written, and gentle-stretch means allow a small amount of extra misdirection. Never infer taste, identity, intelligence, or mastery from it, and never mention this signal in a clue. "
                    "If domain_hints.status is loaded, treat its placeableTerms as a small explicit subject invitation: prefer up to two of those terms when they fit the selected weekday, but do not invent a fact, sense, or expertise claim from the domain label. The terms are private and unadmitted; ordinary clues must still use a reliable lexical route or clearly signalled wordplay. Never use a term that is not in placeableTerms. "
                    "Return 3 to 6 distinct, clueable single words, ASCII A-Z only, 3-15 letters, never 12 letters. "
                    "Do not describe the player or claim what they know or desire. Return only the requested JSON."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "difficulty": weekday.title(),
                        "weekdayRecipe": recipe["id"],
                        "wordField": context,
                        "domainHints": context.get("domain_hints", {}),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ],
        schema,
        timeout=_model_generation_policy(model)["themeTimeout"],
        tokens=240,
        temperature=0.8,
    )
    themes = value.get("themes") if isinstance(value, dict) else None
    if not isinstance(themes, list):
        raise ValueError("Local model returned no theme answers")
    normalized = []
    for answer in themes:
        answer = answer.upper() if isinstance(answer, str) else ""
        if _ANSWER.fullmatch(answer) and len(answer) != 12 and answer not in normalized:
            normalized.append(answer)
    domain_hints = context.get("domain_hints") if isinstance(context, Mapping) else None
    domain_terms = (
        [
            term
            for term in domain_hints.get("placeableTerms", [])
            if isinstance(term, str)
            and _ANSWER.fullmatch(term.upper())
            and len(term) != 12
        ][:2]
        if isinstance(domain_hints, Mapping)
        and domain_hints.get("status") == "loaded"
        and isinstance(domain_hints.get("placeableTerms"), list)
        else []
    )
    if domain_terms:
        normalized = domain_terms + [answer for answer in normalized if answer not in domain_terms]
    recent = {
        answer.upper()
        for answer in context.get("recent_private_answers", [])
        if isinstance(answer, str) and _ANSWER.fullmatch(answer)
    }
    fresh = [answer for answer in normalized if answer not in recent]
    if len(fresh) >= 2:
        normalized = fresh
    if len(normalized) < 2:
        raise ValueError("Local model returned too few usable theme answers")
    return normalized[:MAX_THEME_WORDS]


def _validate_shared_affix_mechanic(themes, mechanic):
    """Accept only a simple rule that every supplied theme answer obeys."""
    if not isinstance(themes, list) or not 3 <= len(themes) <= 5:
        return None
    if not all(
        isinstance(answer, str) and _ANSWER.fullmatch(answer) and len(answer) != 12
        for answer in themes
    ) or len(set(themes)) != len(themes):
        return None
    if (
        not isinstance(mechanic, dict)
        or set(mechanic) != {"type", "affix", "position"}
        or mechanic.get("type") != "shared-affix"
    ):
        return None
    affix = mechanic.get("affix")
    position = mechanic.get("position")
    if (
        not isinstance(affix, str)
        or not re.fullmatch(r"[A-Z]{2,4}", affix)
        or position not in {"prefix", "suffix"}
        or not all(
            answer.startswith(affix) if position == "prefix" else answer.endswith(affix)
            for answer in themes
        )
    ):
        return None
    return {"type": "shared-affix", "affix": affix, "position": position}


@lru_cache(maxsize=1)
def _local_fill_word_set():
    """Return the normalized words available to the native xfill runtime."""
    root = os.environ.get("CROSSWORD_XFILL_ROOT")
    if not isinstance(root, str) or not root.strip():
        return frozenset()
    words = set()
    for filename in ("data/xwordlist.dict", "data/supplemental.txt"):
        path = Path(root) / filename
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for line in raw.splitlines():
            if not line or line.startswith("#"):
                continue
            word = line.split(";", 1)[0].strip().upper()
            if _ANSWER.fullmatch(word) and len(word) != 12:
                words.add(word)
    return frozenset(words)


def _eligible_language_review_forms(forms):
    """Keep due language forms optional and construction-compatible."""
    fill_words = _local_fill_word_set()
    if not fill_words:
        return []
    return [
        form
        for form in forms
        if isinstance(form, str)
        and _ANSWER.fullmatch(form.upper())
        and form.upper() in fill_words
    ]


def _language_candidate_weights(learning):
    """Attach bounded, explainable preference weights to optional forms.

    These are ordering hints for the local model and fill-candidate lane.  A
    weight never becomes a theme lock, a placement requirement, or a claim
    that the player knows a form.  Due status comes from the scheduler; the
    remaining weights only preserve the existing outcome ordering.
    """
    if not isinstance(learning, dict):
        return []
    candidates = learning.get("candidateForms", learning.get("reviewForms", []))
    due = {
        form.upper()
        for form in learning.get("dueForms", [])
        if isinstance(form, str) and _ANSWER.fullmatch(form.upper())
    }
    due_details = {}
    for detail in learning.get("dueDetails", []):
        if not isinstance(detail, dict):
            continue
        form = detail.get("form")
        if isinstance(form, str) and _ANSWER.fullmatch(form.upper()):
            due_details.setdefault(form.upper(), detail)
    category_weights = (
        ("notYetForms", 0.9, "not-yet"),
        ("assistedForms", 0.8, "assisted"),
        ("pendingForms", 0.65, "pending"),
        ("rememberedForms", 0.5, "remembered"),
    )
    category_by_form = {}
    for key, weight, reason in category_weights:
        for form in learning.get(key, []):
            if isinstance(form, str) and _ANSWER.fullmatch(form.upper()):
                category_by_form.setdefault(form.upper(), (weight, reason))
    weighted = []
    seen = set()
    for form in candidates if isinstance(candidates, list) else []:
        if not isinstance(form, str):
            continue
        normalized = form.upper()
        if not _ANSWER.fullmatch(normalized) or normalized in seen:
            continue
        seen.add(normalized)
        weight, reason = category_by_form.get(normalized, (0.5, "optional"))
        if normalized in due:
            weight, reason = 1.0, "due"
        weighted_item = {
            "form": normalized,
            "weight": weight,
            "reason": reason,
        }
        if normalized in due and normalized in due_details:
            detail = due_details[normalized]
            stage = detail.get("reviewStage", 0)
            response = detail.get("lastResponse")
            stage_bonus = min(0.12, max(0, stage) * 0.03)
            response_bonus = {
                "not-yet": 0.12,
                "assisted": 0.08,
                "remembered": 0.02,
            }.get(response, 0.04)
            overdue_hours = detail.get("overdueHours", 0)
            interval_hours = detail.get("intervalHours", 24)
            overdue_bonus = 0.0
            if (
                isinstance(overdue_hours, (int, float))
                and not isinstance(overdue_hours, bool)
                and isinstance(interval_hours, (int, float))
                and not isinstance(interval_hours, bool)
                and interval_hours > 0
            ):
                overdue_bonus = min(0.15, max(0.0, overdue_hours / interval_hours) * 0.15)
            # Priority is an ordering signal, deliberately separate from the
            # category weight so existing bounded category semantics remain
            # stable.  It never becomes a probability or a grid constraint.
            weighted_item["priority"] = round(
                min(1.4, 1.0 + stage_bonus + response_bonus + overdue_bonus), 3
            )
            weighted_item["priorityReason"] = (
                "scheduler-history-and-overdue"
                if overdue_bonus
                else "scheduler-history"
            )
            if overdue_bonus:
                weighted_item["overdueBonus"] = round(overdue_bonus, 3)
        weighted.append(weighted_item)
    # Keep the context bounded and make the preference measurable: a due form
    # is always ordered before lower-priority optional candidates while ties
    # retain the deterministic scheduler/category order above.
    weighted.sort(key=lambda item: (-item.get("weight", 0), -item.get("priority", 0)))
    return weighted[:12]


def _language_learning_generation_record(context, entries, clues):
    """Record optional due-form use without turning it into mastery."""
    learning = context.get("language_learning") if isinstance(context, dict) else None
    if not isinstance(learning, dict):
        return None
    review_forms = [
        form.upper()
        for form in learning.get("candidateForms", learning.get("reviewForms", []))
        if isinstance(form, str) and _ANSWER.fullmatch(form.upper())
    ]
    eligible = {
        form.upper()
        for form in learning.get("eligibleReviewForms", [])
        if isinstance(form, str) and _ANSWER.fullmatch(form.upper())
    }
    language = learning.get("language")
    used = []
    token_hints = []
    token_hint_source = None
    task_pair_sources = []
    if isinstance(language, str):
        for entry in entries if isinstance(entries, list) else []:
            answer = entry.get("answer") if isinstance(entry, dict) else None
            clue_id = entry.get("id") if isinstance(entry, dict) else None
            clue = clues.get(clue_id) if isinstance(clues, dict) else None
            if (
                isinstance(answer, str)
                and answer.upper() in eligible
                and isinstance(clue, str)
                and has_explicit_language_signal(clue, language)
                and answer.upper() not in used
            ):
                used.append(answer.upper())
                pair = task_pair_for_review(language, answer)
                if isinstance(pair, Mapping):
                    task_pair_sources.append(
                        {
                            "entryId": (
                                f"{entry.get('direction')}-{entry.get('number')}"
                                if entry.get("direction") in {"across", "down"}
                                and isinstance(entry.get("number"), int)
                                else clue_id
                            ),
                            "pairId": pair.get("pairId"),
                            "packId": pair.get("packId"),
                            "packDigest": pair.get("packDigest"),
                            "sourceText": pair.get("sourceText"),
                            "semanticStatus": pair.get("semanticStatus"),
                            "reviewStatus": pair.get("reviewStatus"),
                        }
                    )
                display, display_source = private_display_text_for_review(language, answer)
                direction = entry.get("direction")
                number = entry.get("number")
                entry_id = (
                    f"{direction}-{number}"
                    if direction in {"across", "down"} and isinstance(number, int)
                    else None
                )
                if display and entry_id and len(display) == len(answer):
                    token_hint_source = display_source
                    for index, display_token in enumerate(display):
                        if display_token != answer[index]:
                            token_hints.append(
                                {
                                    "entryId": entry_id,
                                    "cellIndex": index,
                                    "displayToken": display_token,
                                }
                            )
    record = {
        **learning,
        "candidatePolicy": "optional-local-fill",
        "usedForms": used[:2],
        "unplacedForms": [form for form in review_forms if form not in used][:12],
        "usageEvidence": "answer-and-explicit-language-clue",
        **(
            {
                "tokenHints": token_hints[:8],
                "tokenHintSource": token_hint_source,
            }
            if token_hints
            else {}
        ),
    }
    if task_pair_sources:
        record["taskPairSources"] = task_pair_sources[:2]
    return record


@lru_cache(maxsize=1)
def _local_shared_affix_groups():
    """Return a small deterministic view of words the native filler can use.

    Thursday's pattern proposal must be grounded in the same local vocabulary
    that xfill receives.  The runtime already pins that vocabulary through
    ``CROSSWORD_XFILL_ROOT``; reading only its two line-oriented dictionaries
    here keeps the proposal bounded and avoids presenting the model with words
    that the fill stage cannot place.  Missing/invalid files simply disable
    this hint; the existing proposal and honest fallback remain available.
    """
    root = os.environ.get("CROSSWORD_XFILL_ROOT")
    if not isinstance(root, str) or not root.strip():
        return []
    scored_words = {}
    for filename in ("data/xwordlist.dict", "data/supplemental.txt"):
        path = Path(root) / filename
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for line in raw.splitlines():
            if not line or line.startswith("#") or ";" not in line:
                continue
            word = line.split(";", 1)[0].strip().upper()
            try:
                score = int(line.split(";", 1)[1].strip())
            except ValueError:
                continue
            # Very low-scoring entries are useful for ordinary fill but make
            # poor anchors for a Thursday pattern. Keep the proposal pool
            # conservative; the ordinary route still has the complete list.
            if _ANSWER.fullmatch(word) and len(word) != 12 and score >= 70:
                scored_words[word] = max(score, scored_words.get(word, 0))
    if not scored_words:
        return []
    groups = []
    for position in ("prefix", "suffix"):
        for size in (2, 3, 4):
            grouped = {}
            for word in scored_words:
                affix = word[:size] if position == "prefix" else word[-size:]
                grouped.setdefault(affix, []).append(word)
            for affix, members in grouped.items():
                preferred = [
                    word
                    for word in members
                    if 4 <= len(word) <= 9 and scored_words[word] >= 80
                ]
                if len(preferred) < 3:
                    preferred = members
                if len(preferred) < 3:
                    continue
                groups.append(
                    {
                        "type": "shared-affix",
                        "affix": affix,
                        "position": position,
                        "answers": sorted(
                            preferred,
                            key=lambda word: (
                                -scored_words[word],
                                abs(len(word) - 6),
                                word,
                            ),
                        )[:8],
                        "count": len(members),
                    }
                )
    groups.sort(key=lambda item: (-item["count"], item["position"], item["affix"]))
    return groups[:32]


def _deterministic_thursday_theme_proposal(context):
    """Choose a checked local affix group when the model proposal is unusable.

    This is deliberately a construction fallback, not a model-quality claim:
    every answer comes from the same local vocabulary that native xfill sees,
    and the final filled board still has to validate the mechanic.  A small
    overlap with the player's bounded word field only ranks groups; it never
    turns an association into a claim about the player.
    """
    groups = _local_shared_affix_groups()
    if not groups:
        raise ValueError("No local Thursday affix group is available")
    signals = set()
    if isinstance(context, Mapping):
        for key in ("opening_associations", "opening_observations"):
            values = context.get(key)
            if isinstance(values, list):
                signals.update(
                    value.upper()
                    for value in values
                    if isinstance(value, str) and value.strip()
                )
        active = context.get("active_associations")
        if isinstance(active, list):
            for item in active:
                if isinstance(item, Mapping) and isinstance(item.get("phrase"), str):
                    signals.add(item["phrase"].upper())
    recent = {
        answer.upper()
        for answer in context.get("recent_private_answers", [])
        if isinstance(answer, str) and _ANSWER.fullmatch(answer.upper())
    } if isinstance(context, Mapping) else set()

    ranked = []
    for group in groups:
        answers = [
            answer.upper()
            for answer in group.get("answers", [])
            if isinstance(answer, str) and _ANSWER.fullmatch(answer.upper())
        ]
        fresh = [answer for answer in answers if answer not in recent]
        if len(fresh) < 3:
            fresh = answers
        if len(fresh) < 3:
            continue
        overlap = sum(
            1
            for answer in fresh
            if answer in signals or any(signal in answer for signal in signals)
        )
        ranked.append((
            -overlap,
            -int(group.get("count", len(fresh))),
            str(group.get("position", "")),
            str(group.get("affix", "")),
            fresh[:5],
            group,
        ))
    if not ranked:
        raise ValueError("No usable local Thursday affix group is available")
    ranked.sort(key=lambda item: item[:4])
    _, _, _, _, themes, group = ranked[0]
    mechanic = _validate_shared_affix_mechanic(themes, {
        "type": group.get("type"),
        "affix": group.get("affix"),
        "position": group.get("position"),
    })
    if mechanic is None:
        raise ValueError("Local Thursday affix group failed validation")
    return themes, mechanic


def _make_thursday_theme_proposal(model, context):
    """Ask for a small theme set and an explicit, mechanically checkable rule."""
    schema = {
        "type": "object",
        "properties": {
            "themes": {
                "type": "array",
                "minItems": 3,
                "maxItems": 5,
                "items": {"type": "string", "pattern": "^[A-Z]{3,15}$"},
            },
            "mechanic": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["shared-affix"]},
                    "affix": {"type": "string", "pattern": "^[A-Z]{2,4}$"},
                    "position": {
                        "type": "string",
                        "enum": ["prefix", "suffix"],
                    },
                },
                "required": ["type", "affix", "position"],
                "additionalProperties": False,
            },
        },
        "required": ["themes", "mechanic"],
        "additionalProperties": False,
    }
    value = _chat(
        model,
        [
            {
                "role": "system",
                "content": (
                    "Propose three to five clueable theme answers for a Thursday crossword and one typed shared-affix rule. "
                    "Every proposed answer must begin or end with the exact same 2-4 letter A-Z affix; state whether it is a prefix or suffix. "
                    "Prefer ordinary English words with a plausible, inferable relationship. A small, clearly signalled proper-name cluster is allowed when the word-field invites it and the local fill supports it; never invent names, spellings, or biographical trivia. "
                    "Choose a rule that gives solvers a fair pattern to notice from multiple entries. The grid uses ordinary letters only. "
                    "When local fill candidates are supplied, choose every theme answer from one supplied group and copy that group's affix and position exactly. "
                    "When domain_hints.status is loaded, prefer a placeable domain term only when it fits the shared-affix group; these are private unadmitted invitations, not evidence for a fact or a player's expertise. Never invent a domain relation. "
                    "Use the word-field only as a source of motifs, never to make claims about the player. Return only the requested JSON."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "difficulty": "Thursday",
                        "weekdayRecipe": _weekday_recipe("thursday")["id"],
                        "wordField": context,
                        "domainHints": context.get("domain_hints", {}),
                        "localFillCandidates": _local_shared_affix_groups(),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ],
        schema,
        timeout=_model_generation_policy(model)["themeTimeout"],
        tokens=300,
        temperature=0.8,
    )
    raw_themes = value.get("themes") if isinstance(value, dict) else None
    if not isinstance(raw_themes, list):
        raise ValueError("Local model returned no Thursday theme answers")
    themes = []
    for answer in raw_themes:
        if not isinstance(answer, str) or not _ANSWER.fullmatch(answer):
            raise ValueError("Local model returned an invalid Thursday theme answer")
        answer = answer.upper()
        if len(answer) == 12 or answer in themes:
            raise ValueError(
                "Local model returned duplicate or invalid Thursday themes"
            )
        themes.append(answer)
    if not 3 <= len(themes) <= 5:
        raise ValueError("Local model returned too few Thursday theme answers")
    recent = {
        answer.upper()
        for answer in context.get("recent_private_answers", [])
        if isinstance(answer, str) and _ANSWER.fullmatch(answer)
    }
    fresh = [answer for answer in themes if answer not in recent]
    if len(fresh) >= 3:
        themes = fresh
    local_candidates = {
        answer
        for group in _local_shared_affix_groups()
        for answer in group.get("answers", [])
    }
    if local_candidates and not set(themes).issubset(local_candidates):
        raise ValueError("Thursday theme answers are outside the local fill vocabulary")
    mechanic = _validate_shared_affix_mechanic(themes, value.get("mechanic"))
    if mechanic is None:
        raise ValueError("Thursday shared-affix proposal did not match its answers")
    return themes, mechanic


def _clue_schema(entry_ids):
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string", "minLength": 2, "maxLength": 64},
            "clues": {
                "type": "array",
                "minItems": len(entry_ids),
                "maxItems": len(entry_ids),
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "enum": entry_ids},
                        "text": {"type": "string", "minLength": 2, "maxLength": 180},
                    },
                    "required": ["id", "text"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["title", "clues"],
        "additionalProperties": False,
    }


_SALVAGE_VERSION = "private-clue-salvage-v1"


def _normalize_salvage_text(text):
    """Collapse whitespace runs so newline-bearing drafts stay usable.

    A newline inside a clue is never meaningful; repairing it here keeps a
    structurally fine draft out of the scaffold instead of rejecting it.
    """
    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _salvage_clue_entries(raw_clues, entry_ids):
    """Split one clue list into usable drafts plus per-id salvage reasons.

    Returns ``(clues, report)`` where clues maps entry id to draft text and
    report carries ``reasons`` (scaffolded entry id to short reason) and an
    ``ignored`` count for items that name no known entry. Validation is as
    strict as the old whole-board gate — same id shape, same text bounds —
    but applies per entry: one bad draft scaffolds its own entry instead of
    the board. The first valid text wins a duplicated id; extra object keys
    are ignored. Downstream repair and safety run unchanged over whatever
    survives, so a blurting draft still meets the leak gate per entry.
    """
    clues: dict = {}
    reasons: dict = {}
    ignored = 0
    items = raw_clues if isinstance(raw_clues, list) else []
    for item in items:
        if not isinstance(item, dict):
            ignored += 1
            continue
        clue_id = item.get("id")
        if (
            not isinstance(clue_id, str)
            or not _CLUE_ID.fullmatch(clue_id)
            or clue_id not in entry_ids
        ):
            ignored += 1
            continue
        if clue_id in clues or clue_id in reasons:
            ignored += 1
            continue
        text = _normalize_salvage_text(item.get("text"))
        if not 2 <= len(text) <= 180:
            reasons[clue_id] = "invalid-clue-text"
            continue
        if _has_syntax_debris(text):
            reasons[clue_id] = "syntax-debris"
            continue
        clues[clue_id] = text
    for clue_id in entry_ids:
        if clue_id not in clues and clue_id not in reasons:
            reasons[clue_id] = "missing-clue"
    return clues, {"reasons": reasons, "ignored": ignored}


def _clue_challenge_schema(entry_ids):
    """Return the bounded schema for the optional advisory clue pass."""
    return {
        "type": "object",
        "properties": {
            "checks": {
                "type": "array",
                "minItems": len(entry_ids),
                "maxItems": len(entry_ids),
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "enum": entry_ids},
                        "disposition": {
                            "type": "string",
                            "enum": ["keep", "fallback", "review"],
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                        "reason": {"type": "string", "minLength": 1, "maxLength": 240},
                    },
                    "required": ["id", "disposition", "confidence", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["checks"],
        "additionalProperties": False,
    }


def _contains_clue_fact_term(clue):
    text = clue.casefold() if isinstance(clue, str) else ""
    return any(
        re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", text)
        for term in _CLUE_FACT_TERMS
    )


# JSON-structural brace debris from a fumbled model response. Braces only
# survive spaced as ordinary set-notation subjects ("{ }, in mathematics",
# "using { and }"); anything else brace-shaped is model debris.
_SPACED_BRACE_SUBJECT_RE = re.compile(r"\{\s+[^{}]*\s*\}|\{[^{}]*\s+\}")


def _has_syntax_debris(text):
    if not isinstance(text, str):
        return False
    bare = _SPACED_BRACE_SUBJECT_RE.sub("", text)
    return "{" in bare or "}" in bare


def _clue_surface_issues(clue):
    """Check visible punctuation conventions without claiming semantics."""
    text = clue if isinstance(clue, str) else ""
    issues = []
    quote_count = text.count('"') + text.count("“") + text.count("”")
    if quote_count % 2:
        issues.append("unbalanced-quotation")
    left_brackets = text.count("[")
    right_brackets = text.count("]")
    if left_brackets != right_brackets:
        issues.append("unbalanced-brackets")
    elif left_brackets:
        # A bracketed aside may wrap the clue whole or trail it to the end
        # ("Air ... [cough, cough]", "... [hic]?"); a span stranded
        # mid-clue is not a convention.
        core = re.sub(r"\s*[:—–-]\s+(?=[A-Z0-9“\"])[^?]*$", "", text.rstrip()).rstrip()
        core = core.rstrip("\"'“”‘’").rstrip()
        core = re.sub(r"[?!]+$", "", core).rstrip()
        if not (text.strip().startswith("[") or core.endswith("]")):
            issues.append("bracket-scope")
    if "?" in text:
        # The question must terminate its clause: end of clue, before
        # closers, inside a parenthetical aside, or before an attribution
        # tail (": Hamlet", "(1957 hit)"). A closing quotation belongs to
        # the quoted cue.
        tail = re.sub(r"\s*[:—–-]\s+(?=[A-Z0-9“\"])[^?]*$", "", text.rstrip()).rstrip()
        tail = re.sub(r"\s*\([^()?]*\)\s*$", "", tail).rstrip()
        tail = re.sub(r"[\)\]}>\"'“”‘’\s]+$", "", tail)
        if not tail.endswith("?"):
            # A quoted question with a short role tail ("Quo Vadis?"
            # character) still asks at its quote.
            quoted = re.match(
                r"""^(['"])(?P<inner>.*)\1\s+\S+(?:\s+\S+){0,2}\s*$""",
                text.rstrip(),
            )
            inner = quoted.group("inner").rstrip() if quoted else ""
            if not inner.endswith("?"):
                issues.append("question-mark-placement")
    if _has_syntax_debris(text):
        issues.append("syntax-debris")
    return issues


def _clue_risk_flags(entry, clue):
    """Return small, explainable risks for a generated clue surface.

    This is a triage signal, not a semantic truth engine.  It deliberately
    combines a factual vocabulary term with a relation word before calling a
    clue source-less.  Thus a clue such as ``Sound that bounces back`` remains
    an ordinary lexical foothold, while ``Singer with a hit song?`` receives a
    conservative repair request.  The answer is never used as evidence for a
    factual claim.
    """
    text = clue if isinstance(clue, str) else ""
    flags = []
    if (
        _contains_clue_fact_term(text)
        or _CLUE_IDENTITY_SURFACE_RE.search(text)
        or _CLUE_ROLE_NAME_RE.search(text)
    ) and (
        _CLUE_FACT_RELATION_RE.search(text)
        or _CLUE_IDENTITY_SURFACE_RE.search(text)
        or _CLUE_ROLE_NAME_RE.search(text)
    ):
        flags.append("unsupported-factual-surface")
    # A weak fill entry is precisely where a surprising proper-name or trivia
    # assertion is least useful.  Keep this separate from a quality defect so
    # the provenance can say that a foothold was requested without claiming a
    # semantic failure.
    if isinstance(entry, dict) and entry.get("needsFoothold") is True:
        flags.append("foothold-required")
    flags.extend(_clue_surface_issues(clue))
    return flags


def _clue_fact_risk(entry, clue):
    """Classify the *surface risk* of a clue without judging its truth.

    The private model does not receive a source ledger.  A clue which mentions
    a singer, place, work, or other relation can therefore be useful prose but
    cannot be called grounded merely because it sounds plausible.  Keep this
    separate from ``_clue_risk_flags`` so the older, small issue vocabulary
    remains stable for callers while provenance gets a more useful category.
    """
    flags = _clue_risk_flags(entry, clue)
    if "unsupported-factual-surface" not in flags:
        return {
            "status": "no-factual-signal-observed",
            "category": None,
            "source": "surface-detector-v1",
            "truth": "not-established",
        }
    text = clue if isinstance(clue, str) else ""
    category = (
        "proper-name-or-biography"
        if _CLUE_PROPER_NAME_RE.search(text) or _CLUE_ROLE_NAME_RE.search(text)
        else "factual-relation"
    )
    return {
        "status": "source-free-factual-signal",
        "category": category,
        "source": "surface-detector-v1",
        "truth": "not-established",
        "flags": ["unsupported-factual-surface"],
    }


def _risky_clue_entries(entries, clues, *, limit=20, weekday=None):
    """Select clues that deserve a second, conservative model pass."""
    risky = []
    for entry in entries:
        clue_id = entry["id"]
        answer = entry["answer"]
        risk_flags = _clue_risk_flags(entry, clues.get(clue_id, ""))
        factual_surface = "unsupported-factual-surface" in risk_flags
        # Short answers are not automatically risky: the deterministic
        # answer-safety and morphology guards already cover leakage, while a
        # high-scoring short fill often has a perfectly ordinary clue. Keep
        # the model repair pass for actual foothold requests and explicit
        # factual/mechanical/surface signals.
        short_or_iffy = entry.get("needsFoothold") is True
        wordplay_issue = _clue_wordplay_issue(entry, clues.get(clue_id, ""))
        morphology_issue = _clue_morphology_issue(entry, clues.get(clue_id, ""))
        surface_issues = _clue_surface_issues(clues.get(clue_id, ""))
        information_issue = _clue_information_issue(
            entry, clues.get(clue_id, ""), weekday=weekday
        )
        if (
            factual_surface
            or short_or_iffy
            or wordplay_issue
            or morphology_issue
            or surface_issues
            or information_issue
        ):
            risky.append(entry)
    # Keep the repair pass bounded. Factual surfaces take priority, followed
    # by low-score footholds; the ordinary clue bundle remains the fast path.
    risky.sort(
        key=lambda entry: (
            not any(
                flag == "unsupported-factual-surface"
                for flag in _clue_risk_flags(entry, clues.get(entry["id"], ""))
            ),
            _clue_wordplay_issue(entry, clues.get(entry["id"], "")) is None,
            not _clue_surface_issues(clues.get(entry["id"], "")),
            not entry.get("needsFoothold"),
            len(entry["answer"]),
        )
    )
    try:
        limit = max(0, min(20, int(limit)))
    except (TypeError, ValueError):
        limit = 20
    return risky[:limit]


def _letters_only(value):
    return re.sub(r"[^A-Z]", "", str(value).upper())


def _stem_clue_word(word):
    """Reduce one word to a coarse stem for leak comparison.

    A tiny deterministic stemmer (plural/inflection stripping with the
    common e-restoration and double-consonant rules). It over-stems by
    design: both clue and answer pass through it, so only shared stems
    match, and the census validates the fallout.
    """
    word = re.sub(r"[^A-Z]", "", str(word).upper())
    if len(word) > 4 and word.endswith("IES"):
        return word[:-3] + "Y"
    if len(word) > 5 and word.endswith("ING"):
        base = word[:-3]
        if len(base) >= 2 and base[-1] == base[-2]:
            return base[:-1]
        if len(base) == 3:
            return base + "E"
        return base
    if len(word) > 4 and word.endswith("ED"):
        base = word[:-2]
        if len(base) >= 2 and base[-1] == base[-2]:
            return base[:-1]
        return base
    if len(word) > 4 and word.endswith("ES") and (
        word[-3] in "SXZO" or word[-4:-2] in ("CH", "SH")
    ):
        return word[:-2]
    if len(word) > 3 and word.endswith("S") and not word.endswith("SS"):
        return word[:-1]
    return word


def _segmented_stem_overlap(answer, text):
    """Catch the answer distributed across clue words sharing its stems.

    "Making a nice impression" for MAKESNICE never places the answer in
    one token, but every answer part (MAKES/NICE) shares a stem with a
    clue word (making/nice). Returns the answer when its stem matches one
    clue word whole, or when the answer splits into 2-4 parts (each at
    least 2 letters) whose stems each match a clue word or a join of up to
    three consecutive clue words ("i can't" covers ICANT). Single-token and
    fairness behavior is unchanged: genus words, double-duty words, and
    fill-blank completions do not fully cover their answers.
    """
    bare = _letters_only(answer)
    if len(bare) < 4 or not isinstance(text, str):
        return None
    words = re.findall(r"[A-Za-z]+", text)
    stems = [_stem_clue_word(word) for word in words]
    answer_stem = _stem_clue_word(bare)
    if len(answer_stem) >= 4 and answer_stem in stems:
        return bare
    joins = set()
    for index, stem in enumerate(stems):
        joins.add(stem)
        if index + 1 < len(stems):
            joins.add(stem + stems[index + 1])
        if index + 2 < len(stems):
            joins.add(stem + stems[index + 1] + stems[index + 2])
    covers = {part for part in joins if len(part) >= 2}

    def _split(position, parts, best):
        if position == len(bare):
            return best if parts >= 2 else 0
        top = 0
        for end in range(position + 2, min(len(bare), position + 8) + 1):
            piece = bare[position:end]
            if _stem_clue_word(piece) in covers:
                top = max(top, _split(end, parts + 1, max(best, len(piece))))
        return top

    # Glue-only coverage ("to"+"to" for TOTO) hands the solver nothing:
    # some matched piece must carry real content. Theme entries whose full
    # wording sits in the clue ("Read between the lines") still fire.
    if _split(0, 0, 0) >= 4:
        return bare
    return None


def _answer_lexical_forms(answer):
    """Return high-confidence lexical forms that must stay out of a clue.

    The private model is allowed to propose unusual fill, but a clue cannot
    simply repeat the answer or its obvious inflection.  This is intentionally
    a small orthographic guard rather than a stemmer: token boundaries keep
    short fills from matching inside unrelated words, and the generated forms
    cover the ordinary plural/tense variants that most often leak through.
    """
    answer = _letters_only(answer)
    if not answer:
        return set()
    forms = {answer}
    irregular_counterparts = {
        "CHILDREN": "CHILD",
        "FEET": "FOOT",
        "GEESE": "GOOSE",
        "MEN": "MAN",
        "MICE": "MOUSE",
        "PEOPLE": "PERSON",
        "TEETH": "TOOTH",
        "WOMEN": "WOMAN",
        "OXEN": "OX",
    }
    irregular = irregular_counterparts.get(answer)
    if irregular:
        forms.add(irregular)
    if len(answer) < 3:
        return forms

    if answer.endswith("IES") and len(answer) > 3:
        forms.add(answer[:-3] + "Y")
    if answer.endswith("ES") and len(answer) > 4:
        forms.add(answer[:-2])
    if answer.endswith("S") and not answer.endswith("SS") and len(answer) > 3:
        forms.add(answer[:-1])
    if not answer.endswith("S"):
        forms.add(answer + "S")
    if not answer.endswith("ES"):
        forms.add(answer + "ES")

    if answer.endswith("ING") and len(answer) > 5:
        forms.add(answer[:-3])
    if answer.endswith("ED") and len(answer) > 4:
        forms.add(answer[:-2])
    if answer.endswith("E") and len(answer) > 3:
        forms.add(answer[:-1] + "ED")
    else:
        forms.add(answer + "ED")
    if not answer.endswith("ING"):
        forms.add(answer + "ING")
    # Degree forms. A clue that contains "shadier" is as much a leak for
    # SHADY as one that contains "shady", and the comparative phrase check
    # below handles the reverse direction. Only ordinary gradable shapes are
    # produced; a four-letter floor keeps short fill from generating forms
    # that collide with unrelated words.
    if len(answer) >= 4 and not answer.endswith(("S", "ED", "ING")):
        forms.update(_degree_forms(answer) - {answer})
    # The reverse direction: an answer that is itself a comparative hands its
    # base back, so a clue for SHADIER that prints "shady" leaks the stem.
    # Only -IER/-IEST are reversed. Plain -ER is not, because COVER would yield
    # the unrelated word COVE, and a doubled consonant is not either, because
    # BUTTER would yield the word BUT - which appears in ordinary clue prose
    # constantly. Those surfaces are still caught when the clue actually
    # compares, because _clue_degree_issue gradates the clue's own base.
    if len(answer) > 4 and answer.endswith("IER"):
        forms.add(answer[:-3] + "Y")
    if len(answer) > 5 and answer.endswith("IEST"):
        forms.add(answer[:-4] + "Y")
    return {form for form in forms if len(form) >= 3}


# Hedged definitions refuse to commit ("Academic achievement, in some
# circles" for ACE): the qualifier spends words to say less. Census
# discipline narrowed this hard: "kind of", "in a way" and "so to speak"
# are legitimate NYT categorizers and play-signals (12k hits), while the
# unverifiable-circles qualifier never appears in 1.2M pairs. Only the
# circles shape counts.
_HEDGED_DEFINITION_RE = re.compile(
    r"\bin\s+(?:some|certain)\s+circles\b",
    re.IGNORECASE,
)


def _hedged_definition(text):
    """Detect qualifier hedges that dilute a definition into vagueness."""
    return isinstance(text, str) and _HEDGED_DEFINITION_RE.search(text) is not None


# Abbreviation frames whose expansion hands the answer's head:
# "Short for notification" for NOTI quotes the answer's first four
# letters. Exact initialisms ("Portable document format" for PDF) stay
# fair: the expansion never contains the answer, only its initials.
_ABBREV_FRAME_RE = re.compile(
    r"\bshort\s+for\s+[\"“”']?([A-Za-z][A-Za-z'’\s-]*?)[\"“”']?\s*$"
    r"|\bfor\s+short\s*$",
    re.IGNORECASE,
)
_ENUM_LETTER_FRAME_RE = re.compile(
    r"\b(?:\w+)-letter\s+(.+?)\s*$",
    re.IGNORECASE,
)


def _abbreviation_head_overlap(answer, text):
    """Catch expansions that start with the answer itself."""
    if not isinstance(answer, str) or not isinstance(text, str):
        return None
    bare = _letters_only(answer)
    if len(bare) < 4:
        return None
    expansions = []
    match = _ABBREV_FRAME_RE.search(text)
    if match is not None and match.group(1):
        expansions.append(match.group(1))
    enum = _ENUM_LETTER_FRAME_RE.search(text)
    if enum is not None:
        expansions.append(enum.group(1))
    for expansion in expansions:
        headed = _letters_only(expansion)
        if len(headed) >= 4 and headed[:4] == bare[:4]:
            return bare
    return None


# Grammatical glue carries no answer information: matching "AND" inside a
# clue is a stopword coincidence, not a leak (census: ANDES / "Locale of
# Pular and Pili").
_OVERLAP_STOPWORDS = frozenset(
    {"A", "AN", "THE", "AND", "OR", "OF", "TO", "IN", "ON", "AT", "FOR", "WITH", "FROM"}
)


def _clue_answer_overlap(entry, clue):
    """Return the answer form leaked into a clue, if any."""
    if not isinstance(entry, dict) or not isinstance(clue, str):
        return None
    answer = entry.get("answer", "")
    text = clue.upper()
    # Preserve word boundaries for multiword answers. Joining ``NO WAY`` to
    # ``NOWAY`` before matching would miss the exact phrase in ``No way!``.
    # Punctuation and whitespace may vary, but every answer word must remain
    # present in order.
    answer_words = re.findall(r"[A-Z]+", str(answer).upper())
    if len(answer_words) > 1:
        phrase = r"[^A-Z]+".join(re.escape(word) for word in answer_words)
        if re.search(rf"(?<![A-Z]){phrase}(?![A-Z])", text):
            return _letters_only(answer)
    for form in sorted(_answer_lexical_forms(answer), key=len, reverse=True):
        if form in _OVERLAP_STOPWORDS:
            continue
        if re.search(rf"(?<![A-Z]){re.escape(form)}(?![A-Z])", text):
            return form
    head = _abbreviation_head_overlap(answer, text)
    if head is not None:
        return head
    segmented = _segmented_stem_overlap(answer, text)
    if segmented is not None:
        return segmented
    bare = _letters_only(answer)
    if len(bare) >= 6:
        # Single-token answers that are really phrases ("MAKESNICE",
        # "ICANTGOON"): the clue spaces what the grid joins, so match the
        # letter stream, not tokens. The match must run token-boundary to
        # token-boundary — "HAMLIN" spanning "AbraHAM"+"LINcoln" is two
        # words apart, not a leak. Short answers stay exempt: tiny strings
        # cross word boundaries by coincidence constantly.
        stream = re.sub(r"[^A-Z]+", "", text)
        boundaries = set()
        cursor = 0
        for token in re.findall(r"[A-Z]+", text):
            boundaries.add(cursor)
            cursor += len(token)
        boundaries.add(cursor)
        index = stream.find(bare)
        while index >= 0:
            if index in boundaries and index + len(bare) in boundaries:
                return bare
            index = stream.find(bare, index + 1)
    if len(bare) >= 5:
        # A stem smuggled in as a simile vehicle ("smooth as a seam" for
        # SEAMLESS) restates the answer instead of clueing it. Narrow to the
        # as/like frame: shared genus words ("evil" in "Evil spirit") and
        # double-duty words ("part" in "Part of G.O.P.") are fair routes.
        for token in set(re.findall(r"[A-Z]{4,}", text)):
            if (
                token != bare
                and token in bare
                and len(token) >= len(bare) - 4
                and re.search(
                    rf"\b(?:as|like)\s+(?:a\s+)?{re.escape(token)}\b",
                    text,
                    re.IGNORECASE,
                )
            ):
                return token
    return None


def _clue_information_issue(entry, clue, *, weekday=None):
    """Reject a tiny set of answer-free surfaces with no solving route.

    This is a recipe-specific quality guard, not a semantic judge.  Tuesday
    asks for a visible step beyond Monday, so surfaces such as ``A thing`` or
    ``A word`` should be repaired or replaced instead of counting as fair
    direct clues.  Keep the vocabulary closed and conservative: longer
    definitions, theme surfaces, and all other weekdays retain their existing
    behavior.
    """
    if weekday != "tuesday" or not isinstance(clue, str):
        return None
    text = re.sub(r"[.!?,:;]+$", "", clue.strip().casefold())
    text = " ".join(text.split())
    if text in _LOW_INFORMATION_CLUE_TEXTS:
        return "low-information-surface"
    return None


def _degree_forms(base):
    """Return the ordinary English degree forms of a gradable base.

    ``SHADY`` yields ``SHADIER``/``SHADIEST``; ``NICE`` yields ``NICER`` and
    ``NICEST``.  This is an orthographic rule, not a grammar: irregular forms
    such as ``GOOD``/``BETTER`` are deliberately not invented here, because a
    wrong degree pair would reject an unrelated clue.  Both the leak guard and
    the tautology check below share this one rule so they cannot disagree.
    """
    base = _letters_only(base)
    if len(base) < 3:
        return set()
    forms = {base}
    doubling = _SHORT_VOWEL_CVC_RE.fullmatch(base)
    if base.endswith("Y") and len(base) > 3:
        stem = base[:-1]
        forms.update({stem + "IER", stem + "IEST"})
    elif doubling:
        # Short-vowel monosyllables double the final consonant: FAT gives
        # FATTER, never FATER. Emitting the undoubled spelling as well would
        # only add a non-word to the ban list, so it is left out.
        forms.update({base + base[2] + "ER", base + base[2] + "EST"})
    elif base.endswith("E"):
        forms.update({base + "R", base + "ST"})
    else:
        forms.update({base + "ER", base + "EST"})
    return forms


def _clue_degree_issue(entry, clue):
    """Reject a clue that defines an answer with the answer's own gradation.

    A clue such as ``more shady`` for ``SHADIER`` states the answer's meaning
    by repeating the answer's own comparative construction. It is not a near
    miss: the comparative of the base *is* the answer. The existing morphology
    guard only sees an explicit ``(comp.)``/``comparative`` convention marker,
    so an unglossed comparative phrase reaches the player untouched.

    The check is intentionally one-directional. It fires only when the clue
    contains a ``more``/``most`` phrase whose complement is a base that
    gradates into exactly this answer, which keeps unrelated comparatives
    such as ``more bright`` for ``DULLER`` legal.
    """
    if not isinstance(entry, dict) or not isinstance(clue, str):
        return None
    answer = _letters_only(entry.get("answer", ""))
    if len(answer) < 4:
        return None
    phrase = _DEGREE_PHRASE_RE.search(clue)
    if phrase is None:
        return None
    complement = _letters_only(phrase.group(1))
    if len(complement) < 3 or complement == answer:
        return None
    if answer in _degree_forms(complement):
        return "tautological-degree-form"
    return None


def _clue_wordplay_issue(entry, clue):
    """Catch mechanically checkable clue/answer mismatches before play.

    This intentionally stays small. It does not pretend to prove semantic
    fairness; it only rejects a few high-confidence model failures observed in
    local boards, such as a false anagram or an answer that is not the stated
    reversal. Returning a reason lets the repair pass and provenance expose
    unresolved issues without turning private play into a publication gate.
    """
    if not isinstance(entry, dict) or not isinstance(clue, str):
        return "invalid-clue"
    answer = _letters_only(entry.get("answer", ""))
    text = clue.strip()
    if not answer or not text:
        return "invalid-clue"
    overlap = _clue_answer_overlap(entry, text)
    if overlap == answer:
        return "answer-giveaway"
    if overlap is not None:
        return "answer-form-in-clue"
    degree = _clue_degree_issue(entry, text)
    if degree is not None:
        return degree
    # The three anchored name-shape guards lived here and were removed in
    # Q08: name-shaped clues without a source-backed sense are refused
    # downstream by the factual-surface guard and the genre cap
    # (name-slot-without-source), which additionally spare reviewed
    # source-backed senses instead of scaffolding them. The generic and
    # low-information blockers below stay: nothing else catches a bare
    # "Common name", and removing them would admit it to players.
    if _is_generic_template(text):
        return "generic-clue"

    anagram = _ANAGRAM_RE.search(text)
    if anagram and sorted(_letters_only(anagram.group(1))) != sorted(answer):
        return "anagram-mismatch"

    reverse = _REVERSE_RE.search(text)
    source = (
        next((group for group in reverse.groups() if group), None) if reverse else None
    )
    if source and _letters_only(source)[::-1] != answer:
        return "reversal-mismatch"

    hidden = _HIDDEN_RE.search(text)
    if hidden and answer not in _letters_only(hidden.group(1)):
        return "hidden-word-mismatch"

    lowered = text.casefold()
    for language, expected in _LANGUAGE_YES.items():
        if re.search(rf"\b{re.escape(language)}\b.*\b(?:yes|affirmative)\b", lowered):
            if answer not in expected:
                return "language-answer-mismatch"
    return None


def _clue_morphology_issue(entry, clue):
    """Catch explicit plural/past markers attached to an obvious mismatch.

    Private clues do not carry a reviewed part-of-speech record, so this is
    intentionally narrow. It checks the crossword conventions the player can
    see directly: ``(pl.)``/``[pl.]`` and an explicit past-tense marker.
    Irregular plural and past forms are kept in small allow-lists; all other
    morphology remains explicitly unknown.
    """
    if not isinstance(entry, dict) or not isinstance(clue, str):
        return "invalid-clue"
    answer = _letters_only(entry.get("answer", ""))
    if not answer:
        return "invalid-clue"
    has_plural_marker = _PLURAL_MARKER_RE.search(clue) is not None
    has_past_marker = _PAST_TENSE_MARKER_RE.search(clue) is not None
    has_present_marker = _PRESENT_TENSE_MARKER_RE.search(clue) is not None
    has_future_marker = _FUTURE_TENSE_MARKER_RE.search(clue) is not None
    has_comparative_marker = _COMPARATIVE_MARKER_RE.search(clue) is not None
    has_superlative_marker = _SUPERLATIVE_MARKER_RE.search(clue) is not None
    if (
        not has_plural_marker
        and not has_past_marker
        and not has_present_marker
        and not has_future_marker
        and not has_comparative_marker
        and not has_superlative_marker
    ):
        return None
    if has_plural_marker and answer not in (
        _COMMON_IRREGULAR_PLURALS | _COMMON_INVARIANT_PLURALS
    ):
        # A terminal S is only a weak shape signal, but it is enough to avoid
        # replacing ordinary plural entries such as CATS. Do not assert that
        # it proves number; this helper only flags the obvious opposite case.
        if not answer.endswith("S") or answer.endswith(("SS", "US", "IS")):
            return "plural-marker-with-singular-shape"
    if has_past_marker:
        if not answer.endswith("ED") and answer not in _COMMON_PAST_FORMS:
            return "past-tense-marker-with-nonpast-shape"
    looks_past = answer.endswith("ED") or answer in _COMMON_PAST_FORMS
    if has_present_marker and looks_past:
        return "present-tense-marker-with-past-shape"
    if has_future_marker and looks_past:
        return "future-tense-marker-with-past-shape"
    if has_comparative_marker:
        if answer not in _COMMON_COMPARATIVE_FORMS and not answer.endswith("ER"):
            return "comparative-marker-with-noncomparative-shape"
    if has_superlative_marker:
        if answer not in _COMMON_SUPERLATIVE_FORMS and not answer.endswith("EST"):
            return "superlative-marker-with-nonsuperlative-shape"
    return None


def _answer_structure(entry):
    """Return structural answer metadata without exposing the answer itself.

    Length and repeated-letter count are properties of the supplied fill, not
    guesses about its meaning.  They are useful for explaining a crossing
    scaffold and for checking that a generated clue is being evaluated against
    the same answer that xfill produced.
    """
    answer = _letters_only(entry.get("answer", "")) if isinstance(entry, dict) else ""
    counts = {}
    for letter in answer:
        counts[letter] = counts.get(letter, 0) + 1
    return {
        "answerLength": len(answer) if answer else None,
        "answerShape": "letters-only" if answer else "unknown",
        "repeatedLetterCount": sum(1 for count in counts.values() if count > 1),
    }


def _clue_generation_bundle(entries):
    """Build the bounded, answer-aware brief supplied to the clue model.

    This is intentionally a *policy* bundle, not a semantic answer key.  The
    fill engine supplies answer shape and support signals; no source-backed
    sense is available at this stage.  Making that distinction explicit in the
    prompt prevents a model from treating a low fill score or a short answer
    as evidence for a name, biography, or obscure fact.
    """
    records = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        structure = _answer_structure(entry)
        score = entry.get("fillScore")
        weak = entry.get("needsFoothold") is True
        support_band = (
            "weak"
            if weak
            else "ordinary"
            if isinstance(score, (int, float))
            else "unknown"
        )
        risk_reasons = []
        if weak:
            risk_reasons.append("low-fill-score-or-explicit-foothold")
        if structure["answerLength"] is not None and structure["answerLength"] <= 4:
            risk_reasons.append("short-answer")
        records.append(
            {
                "id": entry.get("id"),
                **structure,
                "fillScore": score,
                "supportBand": support_band,
                "theme": entry.get("theme") is True,
                "cluePolicy": entry.get(
                    "cluePolicy", "ordinary-definition-or-signalled-wordplay"
                ),
                "factRisk": {
                    "status": "unassessed-before-clue-surface",
                    "source": "no-source-ledger",
                    "truth": "not-established",
                    "reasons": risk_reasons,
                },
                "semanticStatus": "not-established",
                "allowedBasis": [
                    "answer-shape",
                    "mechanical-wordplay-when-checkable",
                    "visible-clue-convention",
                    "ordinary-lexical-sense-proposed-by-model",
                ],
                "forbiddenInference": [
                    "proper-name-from-short-answer",
                    "fact-from-fill-score",
                    "sense-truth-from-model-confidence",
                ],
            }
        )
    return {
        "version": GROUNDED_CLUE_BUNDLE_VERSION,
        "status": "brief-only",
        "sourcePolicy": "private-model-without-source-ledger",
        "semanticStatus": "not-established",
        "entries": records,
        "uncertainty": [
            "semantic-sense-unverified",
            "factual-support-unverified",
            "player-support-unmeasured",
        ],
    }


def _reviewed_grounding_projection(reviewed_content, clue):
    """Return a bounded source witness when the visible clue is pack-backed.

    The pack loader has already validated the source pins and child records.
    This projection only marks an exact visible clue/sense/fact join; it never
    promotes a model paraphrase or a partial answer match into reviewed truth.
    """
    if not isinstance(reviewed_content, Mapping) or not isinstance(clue, str):
        return None
    text = reviewed_content.get("text")
    if not isinstance(text, str) or text.strip() != clue.strip():
        return None
    senses = reviewed_content.get("senses")
    facts = reviewed_content.get("facts")
    senses = [item for item in senses if isinstance(item, Mapping)] if isinstance(senses, list) else []
    facts = [item for item in facts if isinstance(item, Mapping)] if isinstance(facts, list) else []
    if not senses and not facts:
        return None
    return {
        "status": "reviewed-source",
        "semanticStatus": "reviewed-source",
        "truth": "source-backed",
        "lexemeId": reviewed_content.get("lexemeId"),
        "clueId": reviewed_content.get("clueId"),
        "evidenceType": reviewed_content.get("evidenceType"),
        "evidenceId": reviewed_content.get("evidenceId"),
        "packId": reviewed_content.get("packId"),
        "packSha256": reviewed_content.get("packSha256"),
        "senseIds": [item.get("senseId") for item in senses if isinstance(item.get("senseId"), str)],
        "factIds": [item.get("factId") for item in facts if isinstance(item.get("factId"), str)],
        "senses": len(senses),
        "facts": len(facts),
        "uncertainty": ["player-support-unmeasured"],
    }


def _clue_grounding(entry, clue, *, model_response=None, reviewed_content=None):
    """Describe what local deterministic checks know about one clue.

    This is intentionally an uncertainty-bearing diagnostic.  A matching
    anagram or reversal proves only that mechanical relation; it does not
    prove a definition, biography, translation, or the model's broader clue
    claim.  For ordinary clues the semantic meaning remains explicitly
    unverified.
    """
    structure = _answer_structure(entry)
    text = clue if isinstance(clue, str) else ""
    family_observation = _clue_family_observation(text, entry.get("answer"))
    grammar_bridge = validate_surface_clue_family(text, family_observation)
    witness_validators = validate_private_clue_witnesses(entry, text)
    issue = _clue_wordplay_issue(entry, text)
    relation = None
    relation_kind = None
    relation_verification = "not-present"
    morphology = "unclassified"
    morphology_issue = _clue_morphology_issue(entry, text)
    surface_issues = _clue_surface_issues(text)
    for label, pattern, kind in _SAFE_CLUE_RELATIONS:
        if pattern.search(text):
            relation = label
            relation_kind = kind
            if kind == "mechanical":
                relation_verification = "consistent" if issue is None else "failed"
            else:
                relation_verification = "surface-only"
            if label == "plural-label":
                morphology = (
                    morphology_issue
                    if morphology_issue
                    else "plural-marker-present; answer morphology unverified"
                )
            elif label == "tense-label":
                morphology = (
                    morphology_issue
                    if morphology_issue
                    else "tense-marker-present; answer tense unverified"
                )
            break

    fallback = text.startswith("Entry supported by its crossings")
    if fallback:
        status = "crossing-scaffold"
    elif relation_kind == "mechanical" and relation_verification == "consistent":
        status = "mechanically-consistent"
    elif relation_kind == "mechanical":
        status = "mechanical-relation-failed"
    elif relation_kind == "surface":
        status = (
            "surface-convention-invalid"
            if surface_issues
            else "surface-convention-only"
        )
        if morphology_issue:
            status = "morphology-check-failed"
    elif surface_issues:
        status = "surface-convention-invalid"
    elif issue:
        status = "mechanical-check-failed"
    else:
        status = "semantic-unverified"

    semantic_challenge = challenge_private_clue_pair(
        entry,
        text,
        mechanical_issue=issue,
        risk_flags=_clue_risk_flags(entry, text),
        surface_issues=surface_issues,
        witness_validators=witness_validators,
        grammar_bridge=grammar_bridge,
        fallback_used=fallback,
        model_response=model_response,
    )

    reviewed = _reviewed_grounding_projection(reviewed_content, text)
    semantic_status = (
        reviewed["semanticStatus"] if isinstance(reviewed, Mapping) else "not-established"
    )
    uncertainty = (
        reviewed["uncertainty"]
        if isinstance(reviewed, Mapping)
        else [
            "semantic-meaning-unverified",
            "factual-support-unverified",
        ]
    )
    grounding_basis = [
        "answer-shape",
        "visible-clue-convention",
        "mechanical-checks-when-applicable",
    ]
    if reviewed is not None:
        grounding_basis.append("exact-reviewed-sense-or-fact-join")
    return {
        **structure,
        "familyObservation": family_observation,
        "grammarBridge": grammar_bridge,
        "witnessValidators": witness_validators,
        "factRisk": _clue_fact_risk(entry, text),
        "status": status,
        "relation": relation,
        "relationKind": relation_kind,
        "relationVerification": relation_verification,
        "morphology": morphology,
        "morphologyIssue": morphology_issue,
        "surfaceIssues": surface_issues,
        "riskFlags": _clue_risk_flags(entry, text),
        "semanticStatus": semantic_status,
        "groundingBasis": grounding_basis,
        "reviewedSource": reviewed,
        "uncertainty": uncertainty,
        "mechanicalIssue": issue,
        "semanticChallenge": semantic_challenge,
    }


def _source_free_fallback_record(entry, clue, grounding, *, reason_codes=None):
    """Return explicit fallback provenance for an answer-free clue surface."""
    used = isinstance(clue, str) and bool(_SOURCE_FREE_FALLBACK_RE.fullmatch(clue))
    if not used:
        return {
            "used": False,
            "kind": None,
            "reasonCodes": [],
            "answerDisclosure": "none",
            "semanticStatus": "not-established",
        }

    reasons = [
        reason
        for reason in reason_codes or []
        if isinstance(reason, str) and reason
    ]
    if isinstance(entry, dict) and entry.get("needsFoothold") is True:
        reasons.append("weak-or-obscure-fill")
    fact_risk = grounding.get("factRisk", {})
    if fact_risk.get("status") == "source-free-factual-signal":
        reasons.append("unsupported-factual-surface")
    if grounding.get("mechanicalIssue"):
        reasons.append("mechanical-clue-check-failed")
    if grounding.get("morphologyIssue"):
        reasons.append("morphology-check-failed")
    if not reasons:
        reasons.append("conservative-private-safety-fallback")
    reasons = list(dict.fromkeys(reasons))
    return {
        "used": True,
        "kind": "crossing-scaffold",
        "reasonCodes": reasons,
        "answerDisclosure": "none",
        "semanticStatus": "not-established",
        "textPolicy": "source-free-and-answer-free",
    }


def _surface_signal_counts(records):
    """Count literal clue markers without inferring what the clue means."""

    counts = {}
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, Mapping):
            continue
        observation = record.get("familyObservation")
        signals = observation.get("signals") if isinstance(observation, Mapping) else None
        for signal in signals if isinstance(signals, list) else []:
            kind = signal.get("kind") if isinstance(signal, Mapping) else None
            if isinstance(kind, str) and kind:
                counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items()))


def _grounded_clue_bundle(
    entries,
    clues,
    *,
    model_challenges=None,
    reviewed_pack=None,
    safety_fallbacks=None,
):
    """Produce the provenance bundle for the final, visible clue surfaces.

    The bundle combines the existing answer-shape, fact-risk, and family
    diagnostics into one stable record.  ``semanticStatus`` is intentionally
    negative/uncertain for every entry: deterministic surface checks cannot
    establish that a proposed definition, translation, or biography is true.
    """
    records = []
    fallback_records = []
    fact_risk_counts = {}
    family_counts = {}
    status_counts = {}
    challenge_records = []
    reviewed_count = 0
    reviewed_by_id = (
        reviewed_pack.get("byId")
        if isinstance(reviewed_pack, Mapping)
        and isinstance(reviewed_pack.get("byId"), Mapping)
        else {}
    )
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("id")
        clue = clues.get(entry_id, "") if isinstance(clues, dict) else ""
        model_response = (
            model_challenges.get(entry_id)
            if isinstance(model_challenges, dict)
            else None
        )
        grounding = _clue_grounding(
            entry,
            clue,
            model_response=model_response,
            reviewed_content=reviewed_by_id.get(entry_id),
        )
        if grounding.get("semanticStatus") == "reviewed-source":
            reviewed_count += 1
        forced_fallback_reasons = (
            safety_fallbacks.get(entry_id, [])
            if isinstance(safety_fallbacks, Mapping)
            else []
        )
        fallback = _source_free_fallback_record(
            entry,
            clue,
            grounding,
            reason_codes=forced_fallback_reasons,
        )
        fact_risk = grounding["factRisk"]
        fact_category = fact_risk.get("category") or "none-observed"
        family = grounding["familyObservation"]["family"]
        status = grounding["status"]
        challenge_records.append(grounding["semanticChallenge"])
        fact_risk_counts[fact_category] = fact_risk_counts.get(fact_category, 0) + 1
        family_counts[family] = family_counts.get(family, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
        record = {
            "id": entry_id,
            "answerLength": grounding["answerLength"],
            "answerShape": grounding["answerShape"],
            "repeatedLetterCount": grounding["repeatedLetterCount"],
            "fillScore": entry.get("fillScore"),
            "supportBand": (
                "weak"
                if entry.get("needsFoothold") is True
                else "ordinary"
                if isinstance(entry.get("fillScore"), (int, float))
                else "unknown"
            ),
            "familyObservation": grounding["familyObservation"],
            "grammarBridge": grounding["grammarBridge"],
            "witnessValidators": grounding["witnessValidators"],
            "factRisk": fact_risk,
            "status": status,
            "relation": grounding["relation"],
            "relationVerification": grounding["relationVerification"],
            "surfaceIssues": grounding["surfaceIssues"],
            "riskFlags": grounding["riskFlags"],
            "mechanicalIssue": grounding["mechanicalIssue"],
            "morphologyIssue": grounding["morphologyIssue"],
            "semanticChallenge": grounding["semanticChallenge"],
            "semanticStatus": grounding["semanticStatus"],
            "reviewedSource": grounding["reviewedSource"],
            "fallback": fallback,
        }
        records.append(record)
        if fallback["used"]:
            fallback_records.append(
                {
                    "id": entry_id,
                    "kind": fallback["kind"],
                    "reasonCodes": fallback["reasonCodes"],
                    "answerDisclosure": fallback["answerDisclosure"],
                    "semanticStatus": fallback["semanticStatus"],
                }
            )
    return {
        "version": GROUNDED_CLUE_BUNDLE_VERSION,
        "status": "diagnostic",
        "sourcePolicy": (
            "private-model-with-reviewed-source"
            if reviewed_count
            else "private-model-without-source-ledger"
        ),
        "semanticStatus": "reviewed-source-present" if reviewed_count else "not-established",
        "entryCount": len(records),
        "reviewedCount": reviewed_count,
        "fallbackCount": len(fallback_records),
        "safetyFallbacks": {
            entry_id: sorted(
                {
                    reason
                    for reason in reasons
                    if isinstance(reason, str) and reason
                }
            )
            for entry_id, reasons in (safety_fallbacks or {}).items()
            if isinstance(entry_id, str) and isinstance(reasons, list) and reasons
        },
        "factRiskCounts": fact_risk_counts,
        "familyCounts": family_counts,
        "signalCounts": _surface_signal_counts(records),
        "statusCounts": status_counts,
        "semanticChallenge": summarize_challenge_classifications(challenge_records),
        "grammarBridge": summarize_surface_clue_families(
            [{"grammarBridge": item["grammarBridge"]} for item in records]
        ),
        "fallbacks": fallback_records,
        "entries": records,
        "uncertainty": (
            ["player-support-unmeasured"]
            if reviewed_count
            else [
                "semantic-sense-unverified",
                "factual-support-unverified",
                "player-support-unmeasured",
            ]
        ),
    }


def _clue_quality_summary(
    entries,
    clues,
    *,
    weekday=None,
    model_challenges=None,
    reviewed_pack=None,
    safety_fallbacks=None,
):
    issue_counts = {}
    fallback_count = 0
    grounding_entries = []
    grounding_status_counts = {}
    grounding_relation_counts = {}
    grounding_family_counts = {}
    challenge_records = []
    grammar_bridge_entries = []
    reviewed_count = 0
    reviewed_by_id = (
        reviewed_pack.get("byId")
        if isinstance(reviewed_pack, Mapping)
        and isinstance(reviewed_pack.get("byId"), Mapping)
        else {}
    )
    for entry in entries:
        clue = clues.get(entry["id"], "")
        issue = _clue_wordplay_issue(entry, clue)
        if issue:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        morphology_issue = _clue_morphology_issue(entry, clue)
        if morphology_issue:
            issue_counts[morphology_issue] = issue_counts.get(morphology_issue, 0) + 1
        information_issue = _clue_information_issue(
            entry, clue, weekday=weekday
        )
        if information_issue:
            issue_counts[information_issue] = issue_counts.get(information_issue, 0) + 1
        for flag in _clue_risk_flags(entry, clue):
            if flag == "foothold-required":
                continue
            issue_counts[flag] = issue_counts.get(flag, 0) + 1
        if isinstance(clue, str) and clue.startswith(
            "Entry supported by its crossings"
        ):
            fallback_count += 1
        model_response = (
            model_challenges.get(entry.get("id"))
            if isinstance(model_challenges, dict)
            else None
        )
        grounding = _clue_grounding(
            entry,
            clue,
            model_response=model_response,
            reviewed_content=reviewed_by_id.get(entry.get("id")),
        )
        if grounding.get("semanticStatus") == "reviewed-source":
            reviewed_count += 1
        grounding_entries.append({"id": entry["id"], **grounding})
        challenge_records.append(grounding["semanticChallenge"])
        status = grounding["status"]
        grounding_status_counts[status] = grounding_status_counts.get(status, 0) + 1
        relation = grounding["relation"]
        if relation:
            grounding_relation_counts[relation] = (
                grounding_relation_counts.get(relation, 0) + 1
            )
        family = grounding["familyObservation"]["family"]
        grounding_family_counts[family] = grounding_family_counts.get(family, 0) + 1
        grammar_bridge_entries.append(grounding["grammarBridge"])
    summary = {
        "checkedCount": len(entries),
        "issueCount": sum(issue_counts.values()),
        "fallbackCount": fallback_count,
        "issueCounts": issue_counts,
        "signalCounts": _surface_signal_counts(grounding_entries),
        "grounding": {
            "version": GROUNDED_CLUE_BUNDLE_VERSION,
            "entryCount": len(grounding_entries),
            "statusCounts": grounding_status_counts,
            "relationCounts": grounding_relation_counts,
            "familyCounts": grounding_family_counts,
            "signalCounts": _surface_signal_counts(grounding_entries),
            "entries": grounding_entries,
            "grammarBridge": summarize_surface_clue_families(
                [{"grammarBridge": item} for item in grammar_bridge_entries]
            ),
            "semanticChallenge": summarize_challenge_classifications(challenge_records),
            "reviewedCount": reviewed_count,
            "semanticStatus": "reviewed-source-present" if reviewed_count else "not-established",
            "fallbackCount": fallback_count,
            "safetyFallbacks": {
                entry_id: sorted(
                    {
                        reason
                        for reason in reasons
                        if isinstance(reason, str) and reason
                    }
                )
                for entry_id, reasons in (safety_fallbacks or {}).items()
                if isinstance(entry_id, str) and isinstance(reasons, list) and reasons
            },
        },
        # Keep a richer, machine-readable bundle beside the older compact
        # grounding projection used by the local UI.  It is still diagnostic:
        # no field here establishes a clue sense or factual truth.
        "groundedClueBundle": _grounded_clue_bundle(
            entries,
            clues,
            model_challenges=model_challenges,
            reviewed_pack=reviewed_pack,
            safety_fallbacks=safety_fallbacks,
        ),
    }
    return summary


def _theme_mechanic_direction(mechanic):
    if not isinstance(mechanic, dict) or mechanic.get("type") != "shared-affix":
        return ""
    position = mechanic.get("position")
    affix = mechanic.get("affix")
    if position not in {"prefix", "suffix"} or not isinstance(affix, str):
        return ""
    relation = "begin with" if position == "prefix" else "end with"
    return (
        f"The host validated that every themed answer {relation} {affix}. "
        "Clue each theme answer fairly as an ordinary word while leaving the shared pattern inferable across entries. "
        "Do not imply special cells or altered letter entry."
    )


def _repair_risky_clues(model, entries, clues, context, weekday):
    """Repair likely factual hallucinations without blocking private play."""
    if isinstance(context, Mapping) and isinstance(
        context.get("_clue_generation_batches"), Mapping
    ):
        return clues
    risky = _risky_clue_entries(
        entries,
        clues,
        limit=_model_generation_policy(model)["riskRepairMaxEntries"],
        weekday=weekday,
    )
    if not risky:
        return clues
    entry_ids = [entry["id"] for entry in risky]
    schema = _clue_schema(entry_ids)
    theme_mechanic = context.get("_weekday_theme_mechanic")
    mechanic_direction = _theme_mechanic_direction(theme_mechanic)
    try:
        value = _chat(
            model,
            [
                {
                    "role": "system",
                    "content": (
                        "Audit and, where needed, rewrite these crossword clues for a private experimental puzzle. "
                        f"Keep the {weekday.title()} voice. The supplied answer is authoritative. "
                        f"{mechanic_direction} "
                        "A draft clue may be kept only when its factual assertion is certainly true for that exact answer. "
                        "groundingDiagnostics are deterministic surface observations, not evidence of a sense or fact; "
                        "treat source-free-factual-signal as a reason to remove the assertion, not as a fact to repeat. "
                        "Never invent a celebrity credit, fictional character, airport, country, brand, surname, or title. "
                        "When a fact is uncertain, replace it with a direct definition, function, sound, spelling, or "
                        "clearly signalled wordplay that does not require outside trivia. Keep clues concise and fair, "
                        "preserve part of speech/number/tense, and use (abbr.), quotation marks, brackets, or ? only when fitting. "
                        "Honor each entry's cluePolicy. For source-free-foothold entries, remove proper names and factual relation claims entirely; use an ordinary lexical sense, sound, spelling, function, or clearly signalled wordplay that benefits from crossings. "
                        "Check every stated anagram, reversal, and foreign-language translation against the supplied answer; "
                        "never keep a mechanically false wordplay clue. Do not put the answer, its obvious stem, or an "
                        "inflected form in the clue. Do not use vague template clues such as 'common name', 'common term', "
                        "'usual name', or 'generic word'; add a real definition, relation, or signalled mechanism instead. "
                        "For Tuesday, also replace answer-free surfaces such as 'A thing', 'A word', or 'Something' with a concise, usable route into the fill. "
                        "Return exactly one clue for every supplied id and no extra keys."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "difficulty": weekday.title(),
                            "themeMechanic": theme_mechanic,
                            "wordField": {
                                key: value
                                for key, value in context.items()
                                if not key.startswith("_")
                            },
                            "entries": [
                                {
                                    **entry,
                                    "draftClue": clues[entry["id"]],
                                    # Give the repair pass the same
                                    # deterministic observations that will be
                                    # retained in provenance.  They are
                                    # warnings and policy signals, never
                                    # semantic evidence.
                                    "groundingDiagnostics": _clue_grounding(
                                        entry, clues[entry["id"]]
                                    ),
                                }
                                for entry in risky
                            ],
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
            schema,
            timeout=_model_generation_policy(model)["repairTimeout"],
            tokens=min(2600, max(600, len(risky) * 42)),
            temperature=0.35,
        )
        entries_by_id = {entry["id"]: entry for entry in risky}
        repaired = {}
        for clue in value.get("clues", []) if isinstance(value, dict) else []:
            if not isinstance(clue, dict) or set(clue) != {"id", "text"}:
                continue
            clue_id = clue["id"]
            text = clue["text"].strip() if isinstance(clue["text"], str) else ""
            if clue_id in entry_ids and 2 <= len(text) <= 180 and "\n" not in text:
                # Do not allow the repair pass to introduce a mechanically
                # false anagram/reversal or an answer giveaway of its own.
                if _clue_wordplay_issue(
                    entries_by_id[clue_id], text
                ) is None and not _clue_surface_issues(text) and _clue_information_issue(
                    entries_by_id[clue_id], text, weekday=weekday
                ) is None:
                    repaired[clue_id] = text
                else:
                    repaired[clue_id] = clues[clue_id]
        if set(repaired) == set(entry_ids):
            return {**clues, **repaired}
    except (requests.RequestException, ValueError, TypeError, KeyError, RecursionError):
        # The first clue bundle is already playable. A conservative repair is
        # an enhancement, never a reason to make local play unavailable.
        pass
    return clues


def _clue_diversity_report(entries, clues, *, repair=None):
    """Summarize visible clue conventions without asserting their meaning."""
    family_counts = {}
    witnessed_counts = {}
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, Mapping):
            continue
        clue = clues.get(entry.get("id"), "") if isinstance(clues, Mapping) else ""
        observation = _clue_family_observation(clue)
        family = observation.get("family", "definition")
        family_counts[family] = family_counts.get(family, 0) + 1
        witnessed = observation.get("witnessedFamily", family)
        witnessed_counts[witnessed] = witnessed_counts.get(witnessed, 0) + 1
    # The gap between claimed and witnessed counts is reported, never
    # reconciled by assumption: a family counted but not witnessed stays
    # visible instead of being folded into another bucket.
    witness_gap = {
        family: family_counts.get(family, 0) - witnessed_counts.get(family, 0)
        for family in sorted(set(family_counts) | set(witnessed_counts))
        if family_counts.get(family, 0) != witnessed_counts.get(family, 0)
    }
    non_definition = sorted(
        family for family in family_counts if family != "definition"
    )
    non_definition_count = sum(
        count for family, count in family_counts.items() if family != "definition"
    )
    result = {
        "version": CLUE_DIVERSITY_REPAIR_VERSION,
        "entryCount": sum(family_counts.values()),
        "familyCounts": dict(sorted(family_counts.items())),
        "familyCountsClaimed": dict(sorted(family_counts.items())),
        "familyCountsWitnessed": dict(sorted(witnessed_counts.items())),
        "witnessGap": witness_gap,
        "nonDefinitionFamilies": non_definition,
        "nonDefinitionCount": non_definition_count,
        "nonDefinitionRate": round(
            non_definition_count / sum(family_counts.values()), 3
        )
        if family_counts
        else 0.0,
        "status": (
            "varied"
            if len(non_definition) >= 2
            else "definition-heavy"
            if family_counts
            else "empty"
        ),
        "policy": "visible-convention-diversity-only",
        "semanticStatus": "not-established",
        "playPolicy": "never-gates-private-play",
    }
    if isinstance(repair, Mapping):
        result["repair"] = dict(repair)
        required = repair.get("minimumFamilies")
        required_family_set = repair.get("requiredNonDefinitionFamilySet")
        if isinstance(required_family_set, (list, tuple)):
            required_family_set = list(dict.fromkeys(
                family
                for family in required_family_set
                if isinstance(family, str) and family
            ))
            if required_family_set:
                result["requiredNonDefinitionFamilySet"] = required_family_set
                result["missingNonDefinitionFamilies"] = [
                    family
                    for family in required_family_set
                    if family not in non_definition
                ]
        if isinstance(required, int) and required >= 0:
            result["requiredNonDefinitionFamilies"] = required
            required_count = repair.get("minimumClueCount")
            target_rate = repair.get("targetNonDefinitionRate")
            if isinstance(target_rate, (int, float)) and not isinstance(target_rate, bool):
                target_count = math.ceil(sum(family_counts.values()) * float(target_rate))
                if isinstance(required_count, int):
                    required_count = max(required_count, target_count)
                else:
                    required_count = target_count
                result["targetNonDefinitionRate"] = round(float(target_rate), 3)
                result["targetNonDefinitionClues"] = target_count
            count_met = not isinstance(required_count, int) or non_definition_count >= required_count
            if isinstance(required_count, int):
                result["requiredNonDefinitionClues"] = required_count
            family_set_met = not result.get("missingNonDefinitionFamilies")
            floor_met = len(non_definition) >= required and family_set_met and count_met
            result["floorMet"] = floor_met
            if not floor_met and result["status"] in {"varied", "definition-heavy"} and non_definition_count:
                result["status"] = "varied-below-recipe-floor"
    return result


def _desired_clue_family_matches(clue, desired_family):
    """Return whether a repaired clue carries the requested house signal.

    The diversity pass is allowed to fail open, but it must not call a pile of
    fill-ins a five-family Tuesday.  This check stays at the visible grammar
    boundary: it does not claim that the clue is semantically fair or true.
    """
    if not isinstance(desired_family, str):
        return False
    return _clue_family_observation(clue).get("family") == desired_family


def _repair_clue_diversity(model, entries, clues, context, weekday, reviewed_by_id):
    """Add a few safe clue surfaces when a large board is definition-only.

    This is intentionally a small, fail-open second pass. It never rewrites
    exact reviewed text, never blocks a playable board, and accepts only
    visibly signalled non-definition surfaces that pass the existing
    mechanical/surface guards.
    """
    initial = _clue_diversity_report(entries, clues)
    recipe = _effective_weekday_recipe(weekday, context)
    minimum_families = recipe.get("minimumNonDefinitionFamilies", 2)
    required_family_set = recipe.get("requiredNonDefinitionFamilySet")
    if isinstance(required_family_set, (list, tuple)):
        required_family_set = list(dict.fromkeys(
            family
            for family in required_family_set
            if isinstance(family, str) and family
        ))
        minimum_families = max(minimum_families, len(required_family_set))
    else:
        required_family_set = []
    base = {
        "version": CLUE_DIVERSITY_REPAIR_VERSION,
        "status": "not-needed",
        "attempted": False,
        "selectedCount": 0,
        "rewrittenCount": 0,
        "minimumFamilies": minimum_families,
        **(
            {"requiredNonDefinitionFamilySet": required_family_set}
            if required_family_set
            else {}
        ),
        **(
            {"targetNonDefinitionRate": recipe["targetNonDefinitionRate"]}
            if isinstance(recipe.get("targetNonDefinitionRate"), (int, float))
            and not isinstance(recipe.get("targetNonDefinitionRate"), bool)
            else {}
        ),
        **(
            {"minimumClueCount": recipe["minimumNonDefinitionCount"]}
            if isinstance(recipe.get("minimumNonDefinitionCount"), int)
            else {}
        ),
        "reason": "sufficient-surface-variety",
    }
    if len(entries) < 24:
        return clues, {**base, "reason": "small-board"}
    minimum_clue_count = recipe.get("minimumNonDefinitionCount")
    target_rate = recipe.get("targetNonDefinitionRate")
    target_clue_count = minimum_clue_count if isinstance(minimum_clue_count, int) else None
    if isinstance(target_rate, (int, float)) and not isinstance(target_rate, bool):
        target_clue_count = max(
            target_clue_count or 0,
            math.ceil(len(entries) * float(target_rate)),
        )
    if isinstance(target_clue_count, int):
        base["targetNonDefinitionClues"] = target_clue_count
    if (
        weekday != "tuesday"
        and isinstance(context, Mapping)
        and isinstance(context.get("_clue_generation_batches"), Mapping)
    ):
        return clues, {
            **base,
            "status": "skipped-model-batch",
            "reason": "qwen-batched-clue-writer",
            "playPolicy": "deterministic-safety-still-runs",
        }
    missing_required_families = [
        family
        for family in required_family_set
        if family not in initial.get("nonDefinitionFamilies", [])
    ]
    if (
        len(initial["nonDefinitionFamilies"]) >= minimum_families
        and not missing_required_families
        and (
            not isinstance(target_clue_count, int)
            or initial.get("nonDefinitionCount", 0) >= target_clue_count
        )
    ):
        return clues, base
    enabled = os.environ.get(CLUE_DIVERSITY_REPAIR_ENV, "1").strip().casefold()
    if enabled in {"0", "false", "no", "off"}:
        return clues, {**base, "status": "disabled", "reason": "host-disabled"}
    reviewed_ids = {
        clue_id
        for clue_id, record in (reviewed_by_id.items() if isinstance(reviewed_by_id, Mapping) else ())
        if isinstance(record, Mapping) and isinstance(record.get("text"), str) and record.get("text").strip()
    }
    candidates = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or entry_id in reviewed_ids:
            continue
        clue = clues.get(entry_id, "") if isinstance(clues, Mapping) else ""
        # Theme and weak entries already have dedicated clue policies; leave
        # those surfaces to the main writer and foothold repair pass.
        if entry.get("theme") is True or entry.get("needsFoothold") is True:
            continue
        current_family = _clue_family_observation(clue).get("family")
        candidates.append((current_family != "definition", entry))
    # Prefer direct definitions first, then allow the repair pass to rotate an
    # existing surface into a missing family when a model has already spent
    # the eligible definition pool on one convention.
    candidates.sort(
        key=lambda item: (
            item[0],
            len(str(item[1].get("answer", ""))),
            item[1].get("id", ""),
        )
    )
    candidates = [entry for _, entry in candidates]
    # Tuesday needs a visibly broader clue language than Monday. Give the
    # writer enough eligible entries to reach the full-board target in one
    # bounded response; safety and surface validators still discard anything
    # that does not fit.
    repair_limit = 48 if weekday == "tuesday" else 4
    candidates = candidates[:repair_limit]
    if not candidates:
        return clues, {**base, "status": "not-needed", "reason": "no-eligible-entries"}
    existing_families = {
        _clue_family_observation(clue).get("family")
        for clue in clues.values()
        if isinstance(clue, str)
    }
    target_families = required_family_set or list(_DIVERSITY_FAMILY_ORDER)
    missing_families = [
        family for family in target_families if family not in existing_families
    ]
    # A missing family used to receive only the first slot in each retry
    # batch.  On a large Tuesday board that gave Gemma one spoken-equivalent
    # opportunity per pass while the remaining slots were spent on families
    # already present.  Give every missing family a small bounded run of fresh
    # candidates first, then spend the remainder on the ordinary rotation.
    # This changes only the request shape; every returned clue still has to
    # pass the exact visible-family and answer-safety validators below.
    attempted_by_family = (
        context.setdefault("_clue_diversity_attempted_ids", {})
        if isinstance(context, dict)
        else {}
    )
    if not isinstance(attempted_by_family, dict) and isinstance(context, dict):
        attempted_by_family = {}
        context["_clue_diversity_attempted_ids"] = attempted_by_family
    selected_entries = []
    desired_families = []
    missing_family_quota = min(
        4,
        max(1, len(candidates) // max(1, len(missing_families)))
        if missing_families
        else 0,
    )
    for family in missing_families:
        used_ids = {
            item_id
            for item_id in attempted_by_family.get(family, [])
            if isinstance(item_id, str)
        }
        fresh = [
            entry
            for entry in candidates
            if entry.get("id") not in used_ids
            and entry.get("id") not in {item.get("id") for item in selected_entries}
        ]
        chosen = fresh[:missing_family_quota]
        # Once the fresh pool is exhausted, reuse an eligible entry rather
        # than silently pretending that the family was satisfied. The receipt
        # will report the family as unresolved if no safe rewrite is returned.
        if len(chosen) < missing_family_quota:
            reusable = [
                entry
                for entry in candidates
                if entry.get("id") not in {item.get("id") for item in selected_entries}
            ]
            chosen.extend(reusable[: missing_family_quota - len(chosen)])
        selected_entries.extend(chosen)
        desired_families.extend([family] * len(chosen))
    remaining = [
        entry
        for entry in candidates
        if entry.get("id") not in {item.get("id") for item in selected_entries}
    ]
    remaining_slots = max(0, len(candidates) - len(selected_entries))
    selected_entries.extend(remaining[:remaining_slots])
    rotation_families = [
        family
        for family in _DIVERSITY_FAMILY_ORDER
        if family not in missing_families
    ] or list(missing_families) or list(_DIVERSITY_FAMILY_ORDER)
    desired_families.extend(
        rotation_families[index % len(rotation_families)]
        for index in range(remaining_slots)
    )
    candidates = selected_entries[:repair_limit]
    desired_families = desired_families[: len(candidates)]
    selected = [
        {
            "id": entry["id"],
            "answer": entry.get("answer"),
            "length": entry.get("length"),
            "draftClue": clues.get(entry["id"], ""),
            "desiredFamily": desired_families[index],
            "requiredSurface": _DIVERSITY_REQUIRED_SURFACE[desired_families[index]],
        }
        for index, entry in enumerate(candidates)
    ]
    for item in selected:
        family = item.get("desiredFamily")
        entry_id = item.get("id")
        if isinstance(family, str) and isinstance(entry_id, str):
            ids = attempted_by_family.setdefault(family, [])
            if isinstance(ids, list) and entry_id not in ids:
                ids.append(entry_id)
    schema = _clue_schema([item["id"] for item in selected])
    try:
        target_instruction = (
            f"On this board, target at least {target_clue_count} safe non-definition surfaces "
            f"({float(target_rate):.0%}); this is a target for repair, never a semantic claim. "
            if isinstance(target_clue_count, int)
            and isinstance(target_rate, (int, float))
            and not isinstance(target_rate, bool)
            else ""
        )
        missing_family_instruction = (
            "The board is currently missing these required visible families: "
            f"{', '.join(missing_families)}. Spend the first requested entries on those families. "
            "For spoken-equivalent, the entire clue must be one natural quoted utterance: begin and end with matching quotation marks; an optional (Spoken equivalent) annotation may follow. "
            "Do not add an unquoted label or explanatory prefix, and do not use a quotation merely to repeat the answer. "
            if missing_families
            else ""
        )
        value = _chat(
            model,
            [
                {
                    "role": "system",
                    "content": (
                        "Increase visible crossword clue variety for this private board. "
                        f"Keep the {weekday.title()} voice and the supplied answers. "
                        f"The selected recipe asks for at least {minimum_families} distinct non-definition clue families. "
                        f"{target_instruction}"
                        f"{missing_family_instruction}"
                        f"{recipe['clueDirection']} "
                        "Rewrite only the selected entries, preserving fair grammar and answer shape. "
                        "The requested desiredFamily is mandatory for each selected id; do not silently substitute another family. "
                        "Use its requiredSurface literally. For a pun, the question mark is not enough: hinge the surface on a word with two real senses, e.g. `One with a lot to say?` (LOT: a quantity / an auction item); the surface example `Branch specialist?` shows the shape only, and must be adapted to the supplied answer without spelling that answer. "
                        "A fill-in contains ___ or an ellipsis, a nonverbal cue is fully bracketed, a spoken-equivalent is a whole quoted utterance plus its spoken label (a bare quote does not qualify), and a metalinguistic clue says abbr. or briefly. "
                        "Prefer these surface conventions over unsupported factual relations; do not invent facts, proper names, translations, or wordplay. Do not put an answer in its clue. "
                        "Return exactly one clue for every supplied id and no extra keys."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "difficulty": weekday.title(),
                            "wordField": {
                                key: value
                                for key, value in context.items()
                                if not key.startswith("_")
                            },
                            "entries": selected,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
            schema,
            timeout=_model_generation_policy(model)["diversityTimeout"],
            tokens=min(2800, max(800, len(selected) * 52)),
            temperature=0.6,
        )
        returned = value.get("clues") if isinstance(value, Mapping) else None
        if not isinstance(value, Mapping) or not isinstance(value.get("title"), str) or not isinstance(returned, list):
            raise ValueError("clue-diversity-response-invalid")
        by_id = {}
        selected_by_id = {item["id"]: item for item in selected}
        for clue in returned:
            if not isinstance(clue, Mapping) or set(clue) != {"id", "text"}:
                continue
            clue_id = clue.get("id")
            text = clue.get("text").strip() if isinstance(clue.get("text"), str) else ""
            entry = selected_by_id.get(clue_id)
            if entry is None or not 2 <= len(text) <= 180 or "\n" in text:
                continue
            if not _desired_clue_family_matches(text, entry.get("desiredFamily")):
                continue
            if _clue_surface_issues(text) or _clue_wordplay_issue(entry, text) is not None:
                continue
            if "answer-giveaway" in _clue_risk_flags(entry, text):
                continue
            by_id[clue_id] = text
        if not by_id:
            return clues, {
                **base,
                "status": "no-safe-rewrite",
                "attempted": True,
                "selectedCount": len(selected),
                "reason": "model-returned-no-safe-surface",
            }
        return {
            **clues,
            **by_id,
        }, {
            **base,
            "status": "repaired",
            "attempted": True,
            "selectedCount": len(selected),
            "rewrittenCount": len(by_id),
            "achievedFamilies": len(
                {
                    _clue_family_observation(text).get("family")
                    for text in {**clues, **by_id}.values()
                    if _clue_family_observation(text).get("family") != "definition"
                }
            ),
                "reason": (
                    "definition-heavy-board"
                    if minimum_families <= 2
                    else "weekday-surface-floor"
                ),
        }
    except (requests.RequestException, ValueError, TypeError, KeyError, RecursionError):
        return clues, {
            **base,
            "status": "unavailable",
            "attempted": True,
            "selectedCount": len(selected),
            "reason": "local-model-repair-unavailable",
        }


def _source_free_foothold(entry):
    """Return an honest last-resort surface for an ungrounded weak entry.

    A generated clue is private-play content, so we do not fail an otherwise
    playable board because a local model repeated an unsupported fact.  For a
    low-scoring entry, however, retaining that fact would make the crossing
    scaffold look like evidence for a hallucination.  This short metaclue is
    intentionally answer-free and lets crossings or the assistance ladder
    carry the solve.  The provenance quality summary exposes its use.
    """
    length = entry.get("length") if isinstance(entry, dict) else None
    if not isinstance(length, int) or length < 1:
        answer = entry.get("answer", "") if isinstance(entry, dict) else ""
        length = len(answer) if isinstance(answer, str) else 0
    return f"Entry supported by its crossings ({length} letters)"


def _normalize_clue_surface(clue):
    """Repair punctuation-only defects after the model's conservative pass."""
    if not isinstance(clue, str):
        return clue
    text = clue.strip()
    # A dangling short-for frame names no expansion ("Stance or opinion,
    # short for that"): the definition stands alone without it, so drop the
    # frame rather than scaffolding a fair definition.
    text = re.sub(
        r",\s*short\s+for\s+(?:that|this|it)\s*[?.]?\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    issues = _clue_surface_issues(text)
    if not issues:
        return text
    if any(issue in issues for issue in ("unbalanced-brackets", "bracket-scope")):
        text = text.replace("[", "").replace("]", "")
    if "unbalanced-quotation" in issues:
        text = text.replace('"', "").replace("“", "").replace("”", "")
    if "question-mark-placement" in issues:
        text = text.replace("?", "")
    return " ".join(text.split())


def _enforce_private_clue_safety(
    entries,
    clues,
    *,
    weekday=None,
    reviewed_by_id=None,
    fallback_reasons=None,
):
    """Remove unsupported trivia after the model repair pass.

    ``_repair_risky_clues`` asks the model for a conservative rewrite.  This
    A source-free factual relation cannot be distinguished from a hallucinated
    relation by fill score. Replace it for ordinary entries unless the exact
    visible text came from the configured reviewed clue pack. Theme entries
    remain available for private thematic play; their uncertainty is retained
    in ``clueQuality``. This keeps local play fail-open while preventing a
    plausible but unsupported biography from becoming the only route into a
    fill.
    """
    safe = {clue_id: _normalize_clue_surface(clue) for clue_id, clue in clues.items()}
    reviewed_text_by_id = (
        {
            clue_id: record.get("text")
            for clue_id, record in reviewed_by_id.items()
            if isinstance(record, Mapping) and isinstance(record.get("text"), str)
        }
        if isinstance(reviewed_by_id, Mapping)
        else {}
    )
    # Q05 genre caps. Fill-blank is capped at one quarter of the board: keep
    # the first surfaces in entry order, scaffold the rest. Reviewed exact
    # surfaces are exempt from the count and the replacement alike.
    fill_blank_ids = []
    for entry in entries:
        clue_id = entry.get("id") if isinstance(entry, dict) else None
        if not isinstance(clue_id, str) or clue_id not in safe:
            continue
        clue = safe[clue_id]
        exact_reviewed_text = reviewed_text_by_id.get(clue_id)
        if isinstance(exact_reviewed_text, str) and exact_reviewed_text.strip() == clue.strip():
            continue
        if observe_clue_genre(clue).get("genre") == "fill-blank":
            fill_blank_ids.append(clue_id)
    fill_blank_over_cap = set(fill_blank_ids[len(entries) // 4 :])
    for entry in entries:
        clue_id = entry.get("id") if isinstance(entry, dict) else None
        if not isinstance(clue_id, str) or clue_id not in safe:
            continue
        clue = safe[clue_id]
        flags = _clue_risk_flags(entry, clue)
        mechanical_issue = _clue_wordplay_issue(entry, clue)
        morphology_issue = _clue_morphology_issue(entry, clue)
        information_issue = _clue_information_issue(
            entry, clue, weekday=weekday
        )
        exact_reviewed_text = reviewed_text_by_id.get(clue_id)
        reviewed_surface = (
            isinstance(exact_reviewed_text, str)
            and exact_reviewed_text.strip() == clue.strip()
        )
        reason_codes = []
        if (
            "unsupported-factual-surface" in flags
            and not reviewed_surface
            and entry.get("theme") is not True
        ):
            reason_codes.append("unsupported-factual-surface")
        if mechanical_issue in {
            "answer-giveaway",
            "answer-form-in-clue",
            "generic-clue",
            "anagram-mismatch",
            "reversal-mismatch",
            "hidden-word-mismatch",
            "language-answer-mismatch",
        }:
            reason_codes.append(mechanical_issue)
        if morphology_issue in {
            "plural-marker-with-singular-shape",
            "past-tense-marker-with-nonpast-shape",
            "present-tense-marker-with-past-shape",
            "future-tense-marker-with-past-shape",
            "comparative-marker-with-noncomparative-shape",
            "superlative-marker-with-nonsuperlative-shape",
        }:
            reason_codes.append(morphology_issue)
        if information_issue == "low-information-surface" and not reviewed_surface:
            reason_codes.append(information_issue)
        genre = observe_clue_genre(clue).get("genre")
        if genre == "name-slot" and not reviewed_surface:
            # Anchored name shapes were already scaffolded as generic clues;
            # this extends the rule to loose name shapes, exempting entries
            # whose reviewed record carries source-backed senses or facts.
            reviewed_record = (
                reviewed_by_id.get(clue_id)
                if isinstance(reviewed_by_id, Mapping)
                else None
            )
            has_source = isinstance(reviewed_record, Mapping) and bool(
                reviewed_record.get("senses") or reviewed_record.get("facts")
            )
            if not has_source:
                reason_codes.append("name-slot-without-source")
        if genre == "fill-blank" and clue_id in fill_blank_over_cap and not reviewed_surface:
            reason_codes.append("fill-blank-over-cap")
        if (
            reason_codes
        ):
            if isinstance(fallback_reasons, dict):
                fallback_reasons[clue_id] = list(dict.fromkeys(reason_codes))
            # A private board must never leave a clue that gives away its
            # answer or asserts a mechanically false relation. If the repair
            # pass could not produce a safe replacement, keep the crossing
            # scaffold and let the assistance ladder do the teaching.
            safe[clue_id] = _source_free_foothold(entry)
    return safe


def _reviewed_clue_pack_projection(entries, configured_pack):
    """Project exact reviewed clues for answers present in a configured pack.

    The private route may run without a pack. When one is configured, this
    helper copies only the already validated clue text and a compact evidence
    receipt; it never turns a raw lexicon answer into a semantic claim.
    """
    content = getattr(configured_pack, "content", None)
    by_answer = {}
    for lexeme in getattr(content, "lexemes", ()):
        answer = _letters_only(getattr(lexeme, "answer", ""))
        if not answer:
            continue
        record = by_answer.setdefault(
            answer,
            {
                "text": None,
                "clueId": None,
                "evidenceType": None,
                "evidenceId": None,
                "lexemeId": getattr(lexeme, "lexeme_id", None),
                "senses": [],
                "facts": [],
            },
        )
        for sense in getattr(lexeme, "senses", ()):
            gloss = getattr(sense, "gloss", None)
            if isinstance(gloss, str) and gloss.strip():
                record["senses"].append(
                    {
                        "senseId": getattr(sense, "sense_id", None),
                        "gloss": gloss.strip(),
                        "resolutionStatus": getattr(sense, "resolution_status", None),
                    }
                )
        for fact in getattr(lexeme, "facts", ()):
            statement = getattr(fact, "statement", None)
            if isinstance(statement, str) and statement.strip():
                record["facts"].append(
                    {
                        "factId": getattr(fact, "fact_id", None),
                        "statement": statement.strip(),
                    }
                )
        for clue in getattr(lexeme, "clues", ()):
            text = getattr(clue, "text", None)
            if not isinstance(text, str) or not 2 <= len(text.strip()) <= 180:
                continue
            provenance = getattr(clue, "provenance", {})
            source = provenance.get("source", {}) if isinstance(provenance, Mapping) else {}
            if record["text"] is None:
                record.update(
                    {
                        "text": text.strip(),
                        "clueId": getattr(clue, "clue_id", None),
                        "evidenceType": getattr(clue, "evidence_type", None),
                        "evidenceId": getattr(clue, "evidence_id", None),
                        "grammarVersion": (
                            getattr(clue, "grammar", {}).get("grammarVersion")
                            if isinstance(getattr(clue, "grammar", {}), Mapping)
                            else None
                        ),
                        "sourceId": source.get("sourceId") if isinstance(source, Mapping) else None,
                        "sourceVersion": source.get("version") if isinstance(source, Mapping) else None,
                        "sourceArtifactSha256": (
                            source.get("artifactSha256") if isinstance(source, Mapping) else None
                        ),
                        "evidenceRefs": (
                            list(provenance.get("evidenceRefs", []))
                            if isinstance(provenance, Mapping)
                            and isinstance(provenance.get("evidenceRefs"), (list, tuple))
                            else []
                        ),
                        "reviewerId": provenance.get("reviewerId")
                        if isinstance(provenance, Mapping)
                        else None,
                        "reviewedAt": provenance.get("reviewedAt")
                        if isinstance(provenance, Mapping)
                        else None,
                    }
                )
            break

    by_id = {}
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            continue
        answer = _letters_only(entry.get("answer", ""))
        if answer in by_answer:
            by_id[entry["id"]] = dict(by_answer[answer])
    pack_id = getattr(configured_pack, "pack_id", None)
    pack_sha256 = getattr(configured_pack, "pack_sha256", None)
    for record in by_id.values():
        record["packId"] = pack_id
        record["packSha256"] = pack_sha256
    return {
        "version": REVIEWED_CLUE_PACK_VERSION,
        "status": "configured" if by_id else "configured-no-matches",
        "packId": pack_id,
        "packSha256": pack_sha256,
        "byId": by_id,
    }


def _load_reviewed_clue_pack(entries):
    """Load an optional verified pack without making it a private-play gate."""
    try:
        config = current_app.config
    except RuntimeError:
        return {
            "version": REVIEWED_CLUE_PACK_VERSION,
            "status": "not-configured",
            "byId": {},
        }
    required = (
        "FUTURE_ADMITTED_PACK_PATH",
        "FUTURE_ADMITTED_PACK_ID",
        "FUTURE_ADMITTED_PACK_SHA256",
        "FUTURE_ADMITTED_SOURCE_PINS_JSON",
    )
    # Flask's base configuration always contains these keys with ``None``
    # values. Treat that default state as genuinely absent; only a non-empty
    # setting should switch the optional pack into its configured/fail-open
    # loading path. A partially populated configuration still attempts the
    # strict loader and reports ``unavailable``.
    if not any(
        isinstance(config.get(key), str) and config.get(key).strip()
        for key in required
    ):
        return {
            "version": REVIEWED_CLUE_PACK_VERSION,
            "status": "not-configured",
            "byId": {},
        }
    try:
        configured = load_configured_admitted_pack(config)
    except (AdmittedPackConfigError, OSError, TypeError, ValueError, RecursionError):
        return {
            "version": REVIEWED_CLUE_PACK_VERSION,
            "status": "unavailable",
            "byId": {},
            "uncertainty": "configured-pack-could-not-be-loaded",
        }
    return _reviewed_clue_pack_projection(entries, configured)


def _reviewed_clue_pack_summary(pack):
    """Return a bounded public provenance summary without clue text."""
    value = pack if isinstance(pack, dict) else {}
    by_id = value.get("byId") if isinstance(value.get("byId"), dict) else {}
    context_count = sum(
        bool(
            isinstance(record, dict)
            and (record.get("senses") or record.get("facts"))
        )
        for record in by_id.values()
    )
    summary = {
        "version": REVIEWED_CLUE_PACK_VERSION,
        "status": value.get("status", "not-configured"),
        "matchedCount": len(by_id),
        "contextCount": context_count,
        "uncertainty": "reviewed-source-provenance-is-not-a-publication-claim",
    }
    for key in ("packId", "packSha256"):
        if isinstance(value.get(key), str):
            summary[key] = value[key]
    if value.get("status") == "unavailable":
        summary["uncertainty"] = value.get(
            "uncertainty", "configured-pack-could-not-be-loaded"
        )
    return summary


def _ensure_language_clue_signal(clue, language):
    """Repair a private language clue into one of the explicit signal forms."""
    text = clue.strip() if isinstance(clue, str) else ""
    language_name = language.strip() if isinstance(language, str) else ""
    if not text or not language_name or has_explicit_language_signal(text, language_name):
        return text
    prefix = re.match(
        rf"^{re.escape(language_name)}\s+(?P<surface>.+)$",
        text,
        re.IGNORECASE,
    )
    if prefix:
        surface = prefix.group("surface").strip(" ,:;-\t")
        if surface:
            return f"{language_name} for {surface}"
    return f"{text}, in {language_name}"


def _fallback_private_clues(entries, weekday, context, reason):
    """Keep a structurally valid board playable when the clue model misfires.

    A malformed model response cannot be repaired safely because the host no
    longer has a complete clue set to validate. An answer-free crossing
    scaffold preserves the grid and lets the assistance ladder carry the solve
    while the receipt records why clue writing fell back.
    """
    reason = str(reason).strip()[:160] or "model-response-invalid"
    context["_clue_generation_fallback"] = reason
    context["_clue_safety_fallbacks"] = {
        entry.get("id"): ["model-response-invalid"]
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    recipe = _effective_weekday_recipe(weekday, context)
    required_family_set = recipe.get("requiredNonDefinitionFamilySet", ())
    required_family_set = list(dict.fromkeys(
        family
        for family in required_family_set
        if isinstance(family, str) and family
    )) if isinstance(required_family_set, (list, tuple)) else []
    context["_clue_diversity_repair"] = {
        "version": CLUE_DIVERSITY_REPAIR_VERSION,
        "status": "not-attempted",
        "attempted": False,
        "selectedCount": 0,
        "rewrittenCount": 0,
        "minimumFamilies": max(
            recipe.get("minimumNonDefinitionFamilies", 2),
            len(required_family_set),
        ),
        **(
            {"requiredNonDefinitionFamilySet": required_family_set}
            if required_family_set
            else {}
        ),
        "reason": "model-response-invalid",
    }
    return (
        f"{weekday.title()} Clues",
        {
            entry["id"]: _source_free_foothold(entry)
            for entry in entries
            if isinstance(entry, dict) and isinstance(entry.get("id"), str)
        },
    )


def _use_candidate_path(model) -> bool:
    """Select the candidate-set clue path: tier-driven, env-overridable.

    Local-small models fumble whole-board single-request JSON (74/74
    scaffolded on both small tags here) while writing clean small batches, so
    they draft per-entry candidates. Salvage recovers the usable entries from
    a fumbled single response, but the candidate path stays the default lane.
    Large tags keep the proven single-draft path byte-identical. ``CROSSWORD_CLUE_CANDIDATES=1`` forces the candidate
    path (A/B runs), ``=0`` forces the legacy path.
    """
    override = os.environ.get("CROSSWORD_CLUE_CANDIDATES", "").strip().casefold()
    if override in {"1", "true", "yes", "on"}:
        return True
    if override in {"0", "false", "no", "off"}:
        return False
    return _model_tier(model) == "local-small"


def _bounded_rounds(override, default, *, low, high):
    """Clamp a host round-budget override into a sane range.

    Invalid values fall back to the policy default; the loop uses this for
    ablations without touching model policy tables.
    """
    try:
        value = int(str(override).strip())
    except (TypeError, ValueError, AttributeError):
        return int(default)
    return max(low, min(high, value))


_ROUTE_INDEX_CACHE: dict = {}


def _route_signifiers(answer, limit=2, divergent=False):
    """Sample historical routes for one answer from the local-only index.

    Returns up to ``limit`` published clue texts as sense material. Empty
    when the index is absent or the answer is unknown. With ``divergent``,
    picks the least-overlapping pair (maximum domain divergence on the
    exact answer string) instead of the first entries. Local prompt context
    only; never committed, never redistributed.
    """
    if not isinstance(answer, str) or not answer.isalpha():
        return []
    override = os.environ.get("CROSSWORD_CLUE_ROUTE_INDEX_PATH", "").strip()
    from pathlib import Path as _Path

    path = str(_Path(override) if override else "private-clue-routes-v1.local.json")
    if path not in _ROUTE_INDEX_CACHE:
        root = _Path(__file__).resolve().parents[2]
        target = _Path(path) if _Path(path).is_absolute() else root / path
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
            records = payload.get("routes") if isinstance(payload, dict) else None
        except (OSError, ValueError):
            records = None
        _ROUTE_INDEX_CACHE[path] = records if isinstance(records, dict) else {}
    entries = _ROUTE_INDEX_CACHE[path].get(answer.upper(), [])
    texts = [
        entry["clue"]
        for entry in entries[: max(limit, 4)]
        if isinstance(entry, dict) and isinstance(entry.get("clue"), str)
    ]
    if divergent and len(texts) >= 2:
        from .clue_candidate_admission import token_overlap

        best, best_score = (texts[0], texts[1]), 1.0
        for left in texts:
            for right in texts:
                if left >= right:
                    continue
                score = token_overlap(left, right)
                if score < best_score:
                    best, best_score = (left, right), score
        return list(best[:limit])
    return texts[:limit]


def _candidate_draft_seed(base_seed, round_index, batch_index):
    """Deterministic per-round seed so candidate receipts replay."""
    try:
        base = int(base_seed)
    except (TypeError, ValueError):
        return None
    return (base + round_index * 7919 + batch_index * 131) % 2147483647


# Rejection reason families mapped to redraft avoidance lines. The redraft
# prompt repeats the failure mode back as a constraint so a failing entry
# gets a steered retry, not another blind roll of the same dice.
_REDRAFT_AVOIDANCE = (
    (
        "unsupported-factual-surface",
        "State no facts about the answer: no cities it is, teams it has, "
        "people or works it names, no translations claimed. Clue spelling, "
        "sound, function, or clearly signalled wordplay instead.",
    ),
    (
        "answer-giveaway",
        "Do not repeat the answer, its parts, or its inflected forms "
        "anywhere in the clue.",
    ),
    (
        "answer-form-in-clue",
        "Do not repeat the answer, its parts, or its inflected forms "
        "anywhere in the clue.",
    ),
    (
        "name-slot-without-source",
        "Do not clue this as a famous name; clue spelling, sound, or "
        "wordplay instead.",
    ),
    (
        "low-information-surface",
        "Give a concrete definition or mechanism, not a vague template.",
    ),
    (
        "duplicate-draft",
        "Vary the approach from the rejected drafts below.",
    ),
)

_REDRAFT_AVOIDANCE_FALLBACK = (
    "Vary the approach from the rejected drafts below; when in doubt write "
    "a direct definition."
)

# Reasons that carry no steerable signal: a bare retry is the only move.
_REDRAFT_UNSTEERABLE_PREFIXES = ("draft-call-failed", "malformed-draft")


def _redraft_steering(rejected):
    """Build avoidance steering from an entry's rejected drafts.

    ``rejected`` is the entry's receipt item list. Returns a dict with
    ``avoid`` (up to three constraint lines plus the fallback when a
    steerable reason exists) and ``examples`` (up to three rejected
    ``{text, reasons}`` pairs), or None when nothing steerable failed.
    Pure and offline.
    """
    seen: dict = {}
    for item in rejected or []:
        if not isinstance(item, dict) or item.get("admitted") is not False:
            continue
        reasons = item.get("reasons")
        if not isinstance(reasons, list):
            continue
        for reason in reasons:
            if isinstance(reason, str) and reason:
                seen.setdefault(reason, item.get("text"))
    steerable = [
        reason
        for reason in seen
        if not reason.startswith(_REDRAFT_UNSTEERABLE_PREFIXES)
    ]
    if not steerable:
        return None
    lines: list = []
    for family, line in _REDRAFT_AVOIDANCE:
        if any(reason == family or reason.startswith(family + ":") for reason in steerable):
            lines.append(line)
        if len(lines) >= 2:
            break
    if not lines:
        lines.append(_REDRAFT_AVOIDANCE_FALLBACK)
    examples = []
    for item in rejected or []:
        if not isinstance(item, dict) or item.get("admitted") is not False:
            continue
        text = item.get("text")
        reasons = item.get("reasons")
        if isinstance(text, str) and text and isinstance(reasons, list) and reasons:
            examples.append({"text": text[:120], "reasons": sorted(set(
                r for r in reasons if isinstance(r, str)
            ))[:4]})
        if len(examples) >= 3:
            break
    return {"avoid": lines[:3], "examples": examples}


def _make_candidate_clues(model, entries, context, weekday, *, reviewed_pack=None):
    """Draft k shortlisted clues per entry, admit deterministically, compare.

    Replaces the single-draft plus model repair passes for the candidate
    path: failed entries get one bounded re-draft round, and anything still
    unadmitted falls back to the answer-free scaffold through the same safety
    pass every other board uses. Reviewed exact surfaces are preserved
    without drafting. Fail-open throughout: any model misfire scaffolds only
    the entries it touched, never the board.
    """
    from .clue_candidate_admission import (
        CANDIDATE_BATCH_SIZE,
        CANDIDATE_COMPARE_TEMPERATURE,
        CANDIDATE_COMPARE_TOKENS,
        CANDIDATE_DRAFT_ROUNDS,
        CANDIDATE_DRAFT_TEMPERATURE,
        CANDIDATE_DRAFT_TOKENS_PER_ENTRY,
        CANDIDATE_REDRAFT_ROUNDS,
        admit_candidate,
        comparison_payload,
        select_survivors,
        shape_admit,
        validate_comparison_response,
    )
    from .clue_genre import observe_clue_genre
    from .clue_witness import witness_clue_family

    policy = _model_generation_policy(model)
    rounds = _bounded_rounds(
        os.environ.get("CROSSWORD_CANDIDATE_DRAFT_ROUNDS"),
        policy.get("candidateDraftRounds", CANDIDATE_DRAFT_ROUNDS),
        low=1,
        high=8,
    )
    batch_size = int(policy.get("candidateBatchSize", CANDIDATE_BATCH_SIZE))
    draft_tokens = int(
        policy.get("candidateDraftTokensPerEntry", CANDIDATE_DRAFT_TOKENS_PER_ENTRY)
    )
    draft_temperature = float(
        policy.get("candidateDraftTemperature", CANDIDATE_DRAFT_TEMPERATURE)
    )
    compare_tokens = int(
        policy.get("candidateCompareTokens", CANDIDATE_COMPARE_TOKENS)
    )
    compare_temperature = float(
        policy.get("candidateCompareTemperature", CANDIDATE_COMPARE_TEMPERATURE)
    )
    redraft_rounds = _bounded_rounds(
        os.environ.get("CROSSWORD_CANDIDATE_REDRAFT_ROUNDS"),
        policy.get("candidateRedraftRounds", CANDIDATE_REDRAFT_ROUNDS),
        low=0,
        high=4,
    )
    # Strict admission rejects bare-? surfaces the witness cannot ground
    # ("Alpine town?"). Off by default: witness is measurement, and flipping
    # it into a gate costs scaffolds — the loop measures exactly that cost.
    strict_admission = (
        os.environ.get("CROSSWORD_STRICT_ADMISSION", "").strip().casefold()
        in {"1", "true", "yes", "on"}
    )
    # Strict also holds every weekday to Tuesday's low-information floor:
    # content-free surfaces ("A thing") are scaffolds anywhere.
    voice = _DIFFICULTY[weekday]["voice"]
    base_seed = context.get("_candidate_base_seed") if isinstance(context, dict) else None
    clue_timing = {
        "version": "private-clue-generation-timing-v1",
        "primaryWriter": 0.0,
        "riskRepair": 0.0,
        "diversityRepair": 0.0,
        "safetyNormalization": 0.0,
        "candidateDrafts": 0.0,
        "candidateCompare": 0.0,
    }

    def publish_timing():
        context["_clue_generation_timing"] = dict(clue_timing)

    reviewed_by_id = (
        reviewed_pack.get("byId")
        if isinstance(reviewed_pack, dict)
        and isinstance(reviewed_pack.get("byId"), dict)
        else {}
    )
    reviewed_text_by_id = {
        clue_id: record.get("text")
        for clue_id, record in reviewed_by_id.items()
        if isinstance(record, dict) and isinstance(record.get("text"), str)
    }
    draft_started = monotonic()
    title = f"{weekday.title()} Crossword"
    records: dict = {}
    safety_fallbacks: dict = {}
    draft_calls = 0
    compare_calls = 0

    def draftable(entry):
        clue_id = entry.get("id") if isinstance(entry, dict) else None
        return (
            isinstance(clue_id, str)
            and clue_id not in reviewed_text_by_id
            and isinstance(entry.get("answer"), str)
            and bool(entry.get("answer"))
        )

    def draft_instruction():
        return (
            f"Write original, lively crossword clues ({weekday.title()} difficulty: {voice}). "
            "One concise clue per entry id, fair and grammatical, matching the answer's "
            "part of speech, number, and tense. Never repeat the answer or its stem. "
            "Reply as JSON with a short title and a clues array of {id, text}."
        )

    # Route context: published historical clues as sense material for the
    # small model to absorb, never to copy. Off by default; the loop
    # ablates it. Signifiers also seed duplicate detection, so a verbatim
    # reproduction is rejected as a duplicate draft, not admitted.
    routes_enabled = (
        os.environ.get("CROSSWORD_ROUTE_CONTEXT", "").strip().casefold()
        in {"1", "true", "yes", "on"}
    )
    routes_divergent = (
        os.environ.get("CROSSWORD_ROUTE_DIVERGE", "").strip().casefold()
        in {"1", "true", "yes", "on"}
    )
    routes_by_id: dict = {}
    base_instruction = draft_instruction()
    if routes_enabled:
        base_instruction += (
            " Each entry may carry signifiers: published historical clues "
            "showing senses and routes editors used. Absorb their senses and "
            "write fresh clues in your own words; never copy a signifier."
        )
        if routes_divergent:
            base_instruction += (
                " Collide two senses: frame one signifier's meaning inside "
                "the other's domain, and end with ? only when the "
                "misdirection is real."
            )

    def run_draft_round(round_index, target_entries, instruction=None, avoid_by_id=None):
        nonlocal title, draft_calls
        ids = [entry["id"] for entry in target_entries]
        for batch_index in range(0, len(target_entries), batch_size):
            batch = target_entries[batch_index : batch_index + batch_size]
            batch_ids = [entry["id"] for entry in batch]
            seed = _candidate_draft_seed(base_seed, round_index, batch_index)
            system = instruction or base_instruction
            payload_entries = []
            for entry in batch:
                item = {
                    "id": entry["id"],
                    "answer": entry["answer"],
                    "length": entry.get("length"),
                }
                signifiers = routes_by_id.get(entry["id"], [])
                if signifiers:
                    item["signifiers"] = signifiers
                if isinstance(avoid_by_id, dict) and entry["id"] in avoid_by_id:
                    item["avoid"] = avoid_by_id[entry["id"]]
                payload_entries.append(item)
            try:
                value = _chat(
                    model,
                    [
                        {"role": "system", "content": system},
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "entries": payload_entries,
                                },
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        },
                    ],
                    _clue_schema(batch_ids),
                    timeout=policy["primaryClueTimeout"],
                    tokens=max(600, len(batch) * draft_tokens),
                    temperature=draft_temperature,
                    seed=seed,
                )
            except (requests.RequestException, ValueError, TypeError, KeyError) as error:
                for entry in batch:
                    records.setdefault(entry["id"], []).append(
                        {
                            "round": round_index,
                            "seed": seed,
                            "text": None,
                            "admitted": False,
                            "reasons": [f"draft-call-failed:{type(error).__name__}"],
                        }
                    )
                continue
            draft_calls += 1
            if (
                isinstance(value, dict)
                and isinstance(value.get("title"), str)
                and 2 <= len(value["title"].strip()) <= 64
                and title == f"{weekday.title()} Crossword"
            ):
                title = value["title"].strip()
            for raw in value.get("clues", []) if isinstance(value, dict) else []:
                shaped = shape_admit(raw)
                if not shaped["admitted"] or shaped["id"] not in ids:
                    continue
                records.setdefault(shaped["id"], []).append(
                    {
                        "round": round_index,
                        "seed": seed,
                        "text": shaped["text"],
                        "admitted": None,
                    }
                )

    def admit_round():
        for entry in entries:
            clue_id = entry.get("id") if isinstance(entry, dict) else None
            if clue_id is None or clue_id in reviewed_text_by_id:
                continue
            admitted_texts = [
                item["text"]
                for item in records.get(clue_id, [])
                if item.get("admitted") is True
            ]
            # Seed duplicate detection with the entry's signifiers so a
            # verbatim reproduction of published text is rejected here.
            for signifier in routes_by_id.get(clue_id, []):
                if signifier not in admitted_texts:
                    admitted_texts.append(signifier)
            for item in records.get(clue_id, []):
                if item.get("admitted") is not None or item.get("text") is None:
                    continue
                text = item["text"]
                issue_codes = [
                    code
                    for code in (
                        _clue_wordplay_issue(entry, text),
                        _clue_morphology_issue(entry, text),
                        _clue_information_issue(
                            entry,
                            text,
                            weekday="tuesday" if strict_admission else weekday,
                        ),
                    )
                    if isinstance(code, str) and code
                ]
                for flag in _clue_risk_flags(entry, text) or []:
                    if isinstance(flag, str) and flag and flag != "foothold-required":
                        issue_codes.append(flag)
                verdict = witness_clue_family(
                    _clue_family_observation(text).get("family", "definition"), text
                )
                genre = observe_clue_genre(text).get("genre")
                if strict_admission and verdict["family"] == "pseudo-pun":
                    decision = {"admitted": False, "reasons": ["pseudo-pun"]}
                elif strict_admission and _hedged_definition(text):
                    decision = {"admitted": False, "reasons": ["hedged-definition"]}
                else:
                    decision = admit_candidate(
                        text,
                        issue_codes=issue_codes,
                        witnessed_family=verdict["family"],
                        admitted_texts=admitted_texts,
                    )
                item["admitted"] = decision["admitted"]
                item["reasons"] = decision["reasons"]
                item["witnessedFamily"] = verdict["family"]
                item["genre"] = genre
                if decision["admitted"]:
                    admitted_texts.append(text)

    pour = [entry for entry in entries if draftable(entry)]
    if routes_enabled:
        for entry in pour:
            clue_id = entry.get("id") if isinstance(entry, dict) else None
            answer = entry.get("answer") if isinstance(entry, dict) else None
            if isinstance(clue_id, str):
                routes_by_id[clue_id] = _route_signifiers(
                    answer, divergent=routes_divergent
                )
    for round_index in range(max(1, rounds)):
        run_draft_round(round_index, pour)
        admit_round()
    failed = [
        entry
        for entry in pour
        if not any(item.get("admitted") is True for item in records.get(entry["id"], []))
    ]
    steering_enabled = (
        os.environ.get("CROSSWORD_REDRAFT_STEERING", "").strip().casefold()
        not in {"0", "false", "no", "off"}
    )
    redraft_steering: list = []
    for extra in range(max(0, redraft_rounds)):
        if not failed:
            break
        # Group failures by avoidance lines so each redraft batch carries the
        # constraints its entries actually tripped. Unsteerable failures
        # (call errors, malformed drafts) retry with the base instruction.
        # CROSSWORD_REDRAFT_STEERING=0 disables steering for ablation runs;
        # production default is steered.
        groups: dict = {}
        for entry in failed:
            clue_id = entry.get("id")
            steering = _redraft_steering(records.get(clue_id, [])) if steering_enabled else None
            key = "\n".join(steering["avoid"]) if steering else ""
            slot = groups.setdefault(key, {"avoid": {}, "entries": []})
            slot["entries"].append(entry)
            if steering:
                slot["avoid"][clue_id] = {
                    "constraints": steering["avoid"],
                    "rejected": steering["examples"],
                }
        for key, slot in groups.items():
            instruction = (
                f"{draft_instruction()} Avoid the rejected routes: {key}"
                if key
                else None
            )
            run_draft_round(
                rounds + extra, slot["entries"],
                instruction=instruction, avoid_by_id=slot["avoid"] or None,
            )
        redraft_steering.append(
            {
                "round": rounds + extra,
                "groups": [
                    {"avoid": key.split("\n") if key else [], "ids": [e.get("id") for e in slot["entries"]]}
                    for key, slot in groups.items()
                ],
            }
        )
        admit_round()
        failed = [
            entry
            for entry in failed
            if not any(item.get("admitted") is True for item in records.get(entry["id"], []))
        ]
    clue_timing["candidateDrafts"] = round(max(0.0, monotonic() - draft_started), 3)

    compare_started = monotonic()
    clues = {}
    for entry in entries:
        clue_id = entry.get("id") if isinstance(entry, dict) else None
        if not isinstance(clue_id, str):
            continue
        if clue_id in reviewed_text_by_id:
            clues[clue_id] = reviewed_text_by_id[clue_id]
            continue
        survivors = select_survivors(
            [
                {**item, "draftId": f"r{item['round']}-{index}"}
                for index, item in enumerate(records.get(clue_id, []))
            ]
        )
        if not survivors:
            clues[clue_id] = _source_free_foothold(entry)
            safety_fallbacks[clue_id] = ["no-admitted-candidate"]
            continue
        if len(survivors) == 1:
            clues[clue_id] = survivors[0]["text"]
            continue
        seed = _candidate_draft_seed(base_seed, 4242, abs(hash(clue_id)) % 1000)
        try:
            verdict = validate_comparison_response(
                _chat(
                    model,
                    [
                        {
                            "role": "user",
                            "content": json.dumps(
                                comparison_payload(
                                    entry.get("answer"), entry.get("length"), survivors
                                ),
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        }
                    ],
                    {"type": "object"},
                    timeout=policy["challengeTimeout"],
                    tokens=compare_tokens,
                    temperature=compare_temperature,
                    seed=seed,
                ),
                [item["draftId"] for item in survivors],
            )
            compare_calls += 1
        except (requests.RequestException, ValueError, TypeError, KeyError):
            verdict = {"pick": None, "valid": False, "reason": "comparison-unavailable"}
        if verdict["valid"]:
            picked = next(item for item in survivors if item["draftId"] == verdict["pick"])
            clues[clue_id] = picked["text"]
        else:
            clues[clue_id] = survivors[0]["text"]
            verdict = {**verdict, "pick": survivors[0]["draftId"], "fallback": True}
        records[clue_id].append({"comparison": verdict})
    clue_timing["candidateCompare"] = round(max(0.0, monotonic() - compare_started), 3)

    challenge_raw = os.environ.get(PRIVATE_CLUE_CHALLENGE_ENV, "")
    context["_candidate_generation"] = {
        "version": "private-clue-candidate-lane-v1",
        "model": model,
        "weekday": weekday,
        "rounds": rounds,
        "redraftRounds": redraft_rounds,
        "batchSize": batch_size,
        "baseSeed": base_seed,
        "draftCalls": draft_calls,
        "compareCalls": compare_calls,
        "redraftSteering": redraft_steering,
        "routeContext": {
            "enabled": routes_enabled,
            "divergent": routes_divergent,
            "entriesWithRoutes": sum(1 for routes in routes_by_id.values() if routes),
        },
        "challengeEnv": challenge_raw,
        "challengeEnabled": challenge_raw.strip().casefold() in {"1", "true", "yes", "on"},
        "entries": {
            entry.get("id"): {
                "reviewed": entry.get("id") in reviewed_text_by_id,
                "selected": clues.get(entry.get("id")),
                "candidates": records.get(entry.get("id"), []),
            }
            for entry in entries
            if isinstance(entry, dict) and isinstance(entry.get("id"), str)
        },
    }
    safety_started = monotonic()
    safe_clues = _enforce_private_clue_safety(
        entries,
        clues,
        weekday=weekday,
        reviewed_by_id=reviewed_by_id,
        fallback_reasons=safety_fallbacks,
    )
    clue_timing["safetyNormalization"] = round(max(0.0, monotonic() - safety_started), 3)
    context["_clue_safety_fallbacks"] = safety_fallbacks
    publish_timing()
    return title.strip(), safe_clues


def _make_clues(model, entries, context, weekday, *, reviewed_pack=None):
    if _use_candidate_path(model):
        return _make_candidate_clues(
            model, entries, context, weekday, reviewed_pack=reviewed_pack
        )
    recipe = _effective_weekday_recipe(weekday, context)
    clue_timing = {
        "version": "private-clue-generation-timing-v1",
        "primaryWriter": 0.0,
        "riskRepair": 0.0,
        "diversityRepair": 0.0,
        "safetyNormalization": 0.0,
    }

    def publish_timing():
        context["_clue_generation_timing"] = dict(clue_timing)

    theme_mechanic = context.get("_weekday_theme_mechanic")
    mechanic_direction = _theme_mechanic_direction(theme_mechanic)
    voice = _DIFFICULTY[weekday]["voice"]
    entry_ids = [entry["id"] for entry in entries]
    schema = _clue_schema(entry_ids)
    reviewed_by_id = (
        reviewed_pack.get("byId")
        if isinstance(reviewed_pack, dict)
        and isinstance(reviewed_pack.get("byId"), dict)
        else {}
    )
    primary_started = monotonic()
    try:
        base_messages = [
            {
                "role": "system",
                "content": (
                    "Write original, lively crossword clues for a private experimental puzzle. "
                    f"Target {weekday.title()} difficulty: {voice}. "
                    f"{recipe['clueDirection']} "
                    f"{mechanic_direction} "
                    "Clues must be fair, concise, grammatical, and match the answer's part of speech, number, and tense. "
                    "Vary clue forms: direct definitions, quotations for exact utterances, bracketed sound/action cues, "
                    "abbreviation labels, wordplay, and question marks for puns or playful definitions. Use those conventions "
                    "only when they fit. Treat plural, plural form, plural of, (pl.), and [pl.] as hard visible number conventions; "
                    "treat past, present, and future tense markers as hard visible tense conventions. Make the answer conform, "
                    "or rewrite the marker rather than leaving a contradictory clue. "
                    "Make crossings helpful: clue unusual answers accessibly and avoid stacking obscure trivia. "
                    "If the word-field includes a learning language, use explicit labels such as '___, in German' for foreign-language material and never pretend an English clue is a translation. "
                    "Use language_learning as a small recurrence lane: when reviewDue is true, prefer at most two listed candidateForms if they fit, with the explicit language label; dueForms are the first optional candidates, then notYetForms and assistedForms. Do not claim the player knows, remembers, or has mastered any form. "
                    "If eligibleReviewForms are present, use at most two only when they fit the frozen grid and label the clue with the explicit language; they are optional candidates, not mandatory entries. "
                    "Treat candidateWeights as bounded ordering hints only; never turn them into a placement requirement or mastery claim. "
                    "Use play_calibration only to tune accessibility: more-footholds means make weak entries more transparent and crossings generous, balanced means follow the weekday recipe, and gentle-stretch means permit a small amount of fair misdirection. It is a difficulty signal only, never a claim about the player. "
                    "Do not invent biographies, credits, titles, brands, places, or historical facts. Before emitting a clue, "
                    "silently check that every factual assertion matches the supplied answer. If you are not certain of a fact, "
                    "use a transparent definition, sound, spelling, function, or clearly signalled wordplay instead. Never write "
                    "a made-up 'singer with', 'character from', or surname association just to make a clue sound specific. "
                    "Each entry includes a cluePolicy. For a source-free foothold, use only an ordinary lexical sense, sound, spelling, function, or clearly signalled wordplay; do not name a person, work, place, brand, or event and do not make a relation claim such as 'with', 'from', or 'in'. "
                    "Treat fill score as a support signal: a low-scoring entry needs a generous foothold and must not be made difficult by obscure trivia. "
                    "Use the personal word-field as a source of motifs, never as a basis for claims about the player. "
                    "Honor clue_family_targets when present: they are explicit, reversible steering from prior reflection responses or direct clue feedback, so an include target may shape a small visible set of clue mechanisms and an avoid target should be downweighted. Do not infer a target from solve behavior. "
                    "Use recent_clue_family_exposures only for gentle rotation across visible clue mechanisms; it is exposure history, not taste, and must never override a fair clue or an explicit target. "
                    "If uncertain about a proper name or fact, clue the word through a reliable wordplay/definition instead. "
                    "domain_hints are private, unadmitted subject invitations only; they are not a source of facts, senses, expertise, "
                    "or biographies. Never turn a domain label into a clue assertion. "
                    "Never repeat the answer, its obvious stem, or an inflected form in the clue, and never emit a vague "
                    "template such as 'common name' or 'common term' as the whole clue. "
                    "The groundingBundle is a host policy brief, not a source of meaning: use answer shape and support bands "
                    "to choose a generous route, but never promote its factRisk or semanticStatus fields into a claim. "
                    "When footholdSeedPlan is present, use its candidate support entries as early, transparent crossing seeds: "
                    "keep those support clues more gettable than the weak target they seed, without calling the relationship a "
                    "solve-probability estimate or revealing a target answer in the support clue. "
                    "When reviewedContent is present, treat its senses and facts as the only supplied source context for that entry; do not add a new biographical or factual detail. An exact reviewed clueText is authoritative and will be preserved after this pass. "
                    "Return exactly one clue for every supplied id, preserving each id exactly, and no extra keys."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "difficulty": weekday.title(),
                        "themeMechanic": theme_mechanic,
                        "wordField": {
                            key: value
                            for key, value in context.items()
                            if not key.startswith("_")
                        },
                        "entries": entries,
                        # Keep the answer-aware policy separate from the
                        # entries themselves.  It tells the model what the
                        # host can actually support and what remains unknown.
                        "groundingBundle": _clue_generation_bundle(entries),
                        "footholdSeedPlan": context.get("_foothold_seed_plan"),
                        "reviewedClues": [
                            {
                                "id": clue_id,
                                "text": record.get("text"),
                                "evidenceType": record.get("evidenceType"),
                                "evidenceId": record.get("evidenceId"),
                            }
                            for clue_id, record in sorted(reviewed_by_id.items())
                            if isinstance(record, dict)
                            and isinstance(record.get("text"), str)
                        ],
                        "reviewedContent": [
                            {
                                "id": clue_id,
                                "senses": record.get("senses", [])[:3],
                                "facts": record.get("facts", [])[:3],
                            }
                            for clue_id, record in sorted(reviewed_by_id.items())
                            if isinstance(record, dict)
                            and (record.get("senses") or record.get("facts"))
                        ],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ]
        policy = _model_generation_policy(model)
        if (
            isinstance(model, str)
            and model.casefold() == "qwen3.8:27b"
            and len(entries) > policy["qwenClueBatchThreshold"]
        ):
            batch_receipt = {
                "version": "private-qwen-clue-batching-v1",
                "status": "attempted",
                "batchSize": policy["qwenClueBatchSize"],
                "batchCount": math.ceil(len(entries) / policy["qwenClueBatchSize"]),
                "timeoutSeconds": policy["qwenClueBatchTimeout"],
                "tokensPerEntry": policy["qwenClueBatchTokensPerEntry"],
                "maxTokens": policy["qwenClueBatchMaxTokens"],
                "interpretation": "execution-optimization-only",
            }
            context["_clue_generation_batches"] = batch_receipt
            try:
                value = _qwen_batched_clue_value(
                    model,
                    base_messages,
                    entries,
                    reviewed_by_id,
                    context,
                )
            except Exception as error:
                context["_clue_generation_batches"] = {
                    **batch_receipt,
                    "status": "failed",
                    "reason": f"{type(error).__name__}: {error}"[:240],
                }
                raise
            context["_clue_generation_batches"] = {
                **batch_receipt,
                "status": "completed",
            }
        else:
            value = _chat(
                model,
                base_messages,
                schema,
                timeout=policy["primaryClueTimeout"],
                tokens=_clue_token_budget(
                    len(entries), per_entry=policy["clueTokensPerEntry"]
                ),
                temperature=0.65,
                lenient=True,
            )
        clue_timing["primaryWriter"] = round(
            max(0.0, monotonic() - primary_started), 3
        )
    except (
        requests.RequestException,
        ValueError,
        TypeError,
        KeyError,
        RecursionError,
    ) as error:
        clue_timing["primaryWriter"] = round(
            max(0.0, monotonic() - primary_started), 3
        )
        publish_timing()
        return _fallback_private_clues(
            entries, weekday, context, f"{type(error).__name__}: {error}"
        )
    if not isinstance(value, dict):
        publish_timing()
        return _fallback_private_clues(
            entries, weekday, context, "Local model returned an incomplete clue set"
        )
    # Salvage what the model actually delivered: one malformed draft used to
    # scaffold the whole board. Valid entries continue through repair and
    # safety; invalid or missing ones scaffold individually with per-id
    # reasons in the receipt. Only a payload with zero usable clues keeps
    # the whole-board fallback.
    clues, salvage = _salvage_clue_entries(value.get("clues"), entry_ids)
    salvage_reasons = dict(salvage["reasons"])
    title = value.get("title")
    title_defaulted = False
    if not isinstance(title, str) or not 2 <= len(title.strip()) <= 64:
        title = f"{weekday.title()} Clues"
        title_defaulted = True
    if not clues:
        publish_timing()
        return _fallback_private_clues(
            entries, weekday, context, "Local model returned no usable clues"
        )
    by_id = {
        entry["id"]: entry
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    for clue_id in entry_ids:
        if clue_id not in clues:
            clues[clue_id] = _source_free_foothold(by_id.get(clue_id) or {})
    context["_clue_generation_salvage"] = {
        "version": _SALVAGE_VERSION,
        "requested": len(entry_ids),
        "usable": len(entry_ids) - len(salvage_reasons),
        "scaffolded": sorted(salvage_reasons),
        "reasons": salvage_reasons,
        "ignoredItems": salvage["ignored"],
        "titleDefaulted": title_defaulted,
    }
    repair_started = monotonic()
    repaired = _repair_risky_clues(model, entries, clues, context, weekday)
    clue_timing["riskRepair"] = round(max(0.0, monotonic() - repair_started), 3)
    learning = context.get("language_learning") if isinstance(context, dict) else None
    language = learning.get("language") if isinstance(learning, dict) else None
    eligible_forms = {
        form.upper()
        for form in learning.get("eligibleReviewForms", [])
        if isinstance(form, str) and _ANSWER.fullmatch(form.upper())
    } if isinstance(learning, dict) else set()
    if isinstance(language, str) and eligible_forms:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            answer = entry.get("answer")
            clue_id = entry.get("id")
            if (
                isinstance(answer, str)
                and answer.upper() in eligible_forms
                and isinstance(clue_id, str)
                and isinstance(repaired.get(clue_id), str)
            ):
                pair = task_pair_for_review(language, answer)
                source_text = pair.get("sourceText") if isinstance(pair, Mapping) else None
                if isinstance(source_text, str) and source_text.strip():
                    # The task pack owns this narrow source cue. Exact
                    # reviewed clue text, when present, is restored below.
                    repaired[clue_id] = f"{language} for {source_text.strip()}"
                else:
                    repaired[clue_id] = _ensure_language_clue_signal(
                        repaired[clue_id], language
                    )
    # Exact reviewed clue text wins over the model's paraphrase. The model
    # still writes the uncovered entries and the title, while source-backed
    # entries retain their validated evidence wording and receipt.
    for clue_id, record in reviewed_by_id.items():
        text = record.get("text") if isinstance(record, dict) else None
        if isinstance(text, str) and text:
            repaired[clue_id] = text
    diversity_started = monotonic()
    repaired, diversity_repair = _repair_clue_diversity(
        model,
        entries,
        repaired,
        context,
        weekday,
        reviewed_by_id,
    )
    clue_timing["diversityRepair"] += max(0.0, monotonic() - diversity_started)
    # Tuesday's visible variety floor is a real step-up target. If the first
    # bounded pass lands below it, give the writer one more fresh set of
    # ordinary entries. This remains fail-open: the final receipt records both
    # attempts and the board stays playable even when the second pass is
    # unavailable or still below the floor.
    if weekday == "tuesday":
        model_policy = _model_generation_policy(model)
        max_diversity_attempts = model_policy["tuesdayDiversityAttempts"]
        attempts = [diversity_repair]
        # A local writer may return only the subset of requested rewrites that
        # it can make safe. Give it a model-specific number of follow-up
        # batches so a slow local model cannot turn a playable board into an
        # unbounded retry loop.
        for _ in range(max(0, max_diversity_attempts - 1)):
            report = _clue_diversity_report(
                entries, repaired, repair=attempts[-1]
            )
            if report.get("floorMet") is not False:
                break
            diversity_started = monotonic()
            next_repaired, next_report = _repair_clue_diversity(
                model,
                entries,
                repaired,
                context,
                weekday,
                reviewed_by_id,
            )
            clue_timing["diversityRepair"] += max(
                0.0, monotonic() - diversity_started
            )
            repaired = next_repaired
            attempts.append(next_report)
        if len(attempts) > 1:
            diversity_repair = {
                **attempts[-1],
                "attemptCount": len(attempts),
                "attempts": attempts,
                "maxAttempts": max_diversity_attempts,
            }
        else:
            diversity_repair = {
                **diversity_repair,
                "maxAttempts": max_diversity_attempts,
            }
    context["_clue_diversity_repair"] = diversity_repair
    safety_fallbacks = {}
    # Carry the parse-stage salvage reasons into the safety receipt so every
    # visible scaffold names its cause. Safety overwrites an id's reasons
    # when it replaces that id's surface itself.
    for clue_id, reason in salvage_reasons.items():
        safety_fallbacks[clue_id] = [f"salvage:{reason}"]
    safety_started = monotonic()
    safe_clues = _enforce_private_clue_safety(
        entries,
        repaired,
        weekday=weekday,
        reviewed_by_id=reviewed_by_id,
        fallback_reasons=safety_fallbacks,
    )
    clue_timing["safetyNormalization"] += max(0.0, monotonic() - safety_started)
    # Safety normalization can conservatively replace a generated surface
    # after the diversity pass (for example when a model's language signal is
    # mechanically false).  Give Tuesday one final bounded repair opportunity
    # against the actually safe clue set, so the recorded floor describes the
    # clues the player will see rather than the pre-safety draft.
    if weekday == "tuesday":
        post_safety = _clue_diversity_report(
            entries, safe_clues, repair=diversity_repair
        )
        max_diversity_attempts = _model_generation_policy(model)[
            "tuesdayDiversityAttempts"
        ]
        allow_post_safety_repair = _model_generation_policy(model)[
            "tuesdayPostSafetyRepair"
        ]
        attempts = list(diversity_repair.get("attempts", []))
        if (
            post_safety.get("floorMet") is False
            and (allow_post_safety_repair or len(attempts) < max_diversity_attempts)
        ):
            diversity_started = monotonic()
            post_repaired, post_report = _repair_clue_diversity(
                model,
                entries,
                safe_clues,
                context,
                weekday,
                reviewed_by_id,
            )
            clue_timing["diversityRepair"] += max(
                0.0, monotonic() - diversity_started
            )
            post_fallbacks = {}
            safety_started = monotonic()
            safe_clues = _enforce_private_clue_safety(
                entries,
                post_repaired,
                weekday=weekday,
                reviewed_by_id=reviewed_by_id,
                fallback_reasons=post_fallbacks,
            )
            clue_timing["safetyNormalization"] += max(
                0.0, monotonic() - safety_started
            )
            safety_fallbacks.update(post_fallbacks)
            if not attempts:
                attempts = [diversity_repair]
            attempts.append(post_report)
            diversity_repair = {
                **post_report,
                "attemptCount": len(attempts),
                "attempts": attempts,
                "maxAttempts": max_diversity_attempts,
                "postSafetyRepair": True,
            }
        elif attempts and "maxAttempts" not in diversity_repair:
            diversity_repair = {
                **diversity_repair,
                "maxAttempts": max_diversity_attempts,
            }
        # Keep an explicit answer-free receipt when the bounded retry budget
        # still cannot produce one of the required visible families. This is
        # an honest availability signal, not a reason to synthesize a clue or
        # lower the family floor in the report.
        final_diversity = _clue_diversity_report(entries, safe_clues)
        unresolved_families = [
            family
            for family in _effective_weekday_recipe(weekday, context).get(
                "requiredNonDefinitionFamilySet", ()
            )
            if family not in final_diversity.get("nonDefinitionFamilies", [])
        ]
        if unresolved_families:
            diversity_repair = {
                **diversity_repair,
                "unavailableFamilies": unresolved_families,
                "familyRetryStatus": "bounded-exhausted",
            }
        context["_clue_diversity_repair"] = diversity_repair
    context["_clue_safety_fallbacks"] = safety_fallbacks
    clue_timing = {
        **clue_timing,
        "diversityRepair": round(clue_timing["diversityRepair"], 3),
        "safetyNormalization": round(clue_timing["safetyNormalization"], 3),
    }
    context["_clue_generation_timing"] = clue_timing
    return title.strip(), safe_clues


def _challenge_private_clues(model, entries, clues, context, weekday):
    """Run an optional, fail-open model critique over the visible clue set.

    The deterministic challenger remains the source of classification.  This
    pass only supplies a bounded recommendation envelope to that challenger,
    so a local model can call out a suspicious clue without turning its own
    unverified judgment into a safety gate or a semantic fact.
    """
    enabled = os.environ.get(PRIVATE_CLUE_CHALLENGE_ENV, "").strip().casefold()
    base = {
        "version": PRIVATE_CLUE_CHALLENGE_VERSION,
        "status": "disabled",
        "enabled": False,
        "model": model,
        "weekday": weekday,
        "checkedCount": 0,
        "scope": "all-entries",
        "byId": {},
        "uncertainty": "advisory-model-output-unverified",
        "playPolicy": "never-gates-private-play",
    }
    if enabled not in {"1", "true", "yes", "on"}:
        return base
    if isinstance(context, Mapping) and isinstance(
        context.get("_clue_generation_batches"), Mapping
    ):
        return {
            **base,
            "status": "skipped-model-batch",
            "requested": True,
            "reason": "qwen-batched-clue-writer",
        }
    if not isinstance(entries, list) or not isinstance(clues, dict):
        return {**base, "status": "invalid-input", "enabled": True}
    all_entry_ids = [
        entry.get("id")
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    ]
    if not all_entry_ids:
        return {**base, "status": "empty", "enabled": True}
    entry_ids = all_entry_ids
    scope = "all-entries"
    # A full Wednesday/Sunday board can contain dozens of ordinary clues. The
    # challenger is useful where deterministic policy already found a reason
    # to look twice, but a second model pass over every clean definition adds
    # latency without adding evidence. Keep small fixtures exhaustive for
    # contract coverage; bound real boards to risky, weak, or mechanically
    # questionable entries and make that scope visible in provenance.
    if len(all_entry_ids) > 12:
        selected_ids = []
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("id") not in all_entry_ids:
                continue
            clue = clues.get(entry["id"], "")
            if (
                entry.get("needsFoothold") is True
                or _clue_risk_flags(entry, clue)
                or _clue_wordplay_issue(entry, clue) is not None
                or _clue_morphology_issue(entry, clue) is not None
            ):
                selected_ids.append(entry["id"])
        entry_ids = selected_ids
        scope = "deterministic-risk-selection"
        if not entry_ids:
            return {
                **base,
                "status": "skipped-no-risk",
                "enabled": True,
                "scope": scope,
            }
    payload_entries = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("id") not in entry_ids:
            continue
        clue = clues.get(entry["id"], "")
        payload_entries.append(
            {
                "id": entry["id"],
                "answer": entry.get("answer"),
                "clue": clue,
                "theme": entry.get("theme") is True,
                "supportBand": (
                    "weak" if entry.get("needsFoothold") is True else "ordinary"
                ),
                "deterministicSignals": {
                    "riskFlags": _clue_risk_flags(entry, clue),
                    "mechanicalIssue": _clue_wordplay_issue(entry, clue),
                    "morphologyIssue": _clue_morphology_issue(entry, clue),
                    "family": _clue_family_observation(clue).get("family"),
                },
            }
        )
    schema = _clue_challenge_schema(entry_ids)
    try:
        value = _chat(
            model,
            [
                {
                    "role": "system",
                    "content": (
                        "You are an advisory crossword clue challenger for a private local puzzle. "
                        "For each supplied id, classify only the visible clue surface as keep, fallback, or review. "
                        "Use fallback for a clue that gives away the answer or makes a plainly false mechanical claim; "
                        "use review when a definition, fact, translation, or proper-name assertion may be uncertain. "
                        "Use keep only for a clue that appears ordinary and fair. This is a recommendation, not proof: "
                        "do not invent sources, do not claim semantic certainty, and do not omit any id. Keep each reason short."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "difficulty": weekday.title(),
                            "wordField": {
                                key: value
                                for key, value in context.items()
                                if not key.startswith("_")
                            },
                            "entries": payload_entries,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
            schema,
            timeout=_model_generation_policy(model)["challengeTimeout"],
            tokens=min(2400, max(600, len(entry_ids) * 32)),
            temperature=0.2,
        )
    except Exception as error:  # optional diagnostics must never block play
        return {
            **base,
            "status": "failed",
            "enabled": True,
            "scope": scope,
            "error": str(error)[:240],
        }
    checks = value.get("checks") if isinstance(value, dict) else None
    if not isinstance(checks, list):
        return {
            **base,
            "status": "invalid-response",
            "enabled": True,
            "scope": scope,
        }
    by_id = {}
    for item in checks:
        if not isinstance(item, dict):
            return {
                **base,
                "status": "invalid-response",
                "enabled": True,
                "scope": scope,
            }
        item_id = item.get("id")
        if (
            item_id not in entry_ids
            or item_id in by_id
            or item.get("disposition") not in {"keep", "fallback", "review"}
            or item.get("confidence") not in {"low", "medium", "high"}
            or not isinstance(item.get("reason"), str)
            or not 1 <= len(item["reason"].strip()) <= 240
        ):
            return {
                **base,
                "status": "invalid-response",
                "enabled": True,
                "scope": scope,
            }
        by_id[item_id] = {
            "disposition": item["disposition"],
            "confidence": item["confidence"],
            "reason": item["reason"].strip(),
            "source": "local-model-advisory",
        }
    if set(by_id) != set(entry_ids):
        return {
            **base,
            "status": "incomplete-response",
            "enabled": True,
            "scope": scope,
        }
    return {
        **base,
        "status": "completed",
        "enabled": True,
        "scope": scope,
        "checkedCount": len(by_id),
        "byId": by_id,
    }


def _legacy_puzzle(
    grid, themes, title, clues, model, weekday, seed, language_interest=None
):
    native_tokens = {
        (cell["row"], cell["column"]): cell
        for cell in validate_native_token_cells(grid).get("cells", [])
    }
    entries = []
    for raw in grid["entries"]:
        direction = "across" if raw["dir"] == "A" else "down"
        answer = raw["answer"]
        cell_tokens = raw.get("cellTokens")
        if cell_tokens is None:
            if not _ANSWER.fullmatch(answer) or len(answer) != raw.get("len"):
                raise ValueError("Native fill returned an invalid entry")
            cell_tokens = list(answer)
        elif (
            not isinstance(cell_tokens, list)
            or len(cell_tokens) != raw.get("len")
            or any(
                not isinstance(token, str)
                or not re.fullmatch(r"[A-Z]{1,8}", token)
                for token in cell_tokens
            )
            or answer != "".join(cell_tokens)
            or not re.fullmatch(r"[A-Z]{3,30}", answer)
        ):
            raise ValueError("Native fill returned an invalid token sequence")
        if raw.get("row", -1) < 0 or raw.get("col", -1) < 0:
            raise ValueError("Native fill returned an invalid entry")
        key = f"{raw['num']}{raw['dir']}"
        clue = clues.get(key)
        if not isinstance(clue, str):
            raise ValueError("A generated entry has no clue")
        characters = []
        row, column = raw["row"], raw["col"]
        for index, letter in enumerate(cell_tokens):
            coordinate = (
                row if raw["dir"] == "A" else row + index,
                column + index if raw["dir"] == "A" else column,
            )
            token = native_tokens.get(coordinate)
            characters.append({"letters": token["fillToken"] if token else letter})
        entries.append(
            {
                "clue_number": raw["num"],
                "clue_text": clue,
                "direction": direction,
                "start_x": raw["col"],
                "start_y": raw["row"],
                "characters": characters,
            }
        )
    now = datetime.now(timezone.utc)
    notepad = f"Private local generation · {weekday.title()} · {model} · seed {seed}"
    if isinstance(language_interest, str) and language_interest in _LANGUAGE_CODES:
        notepad += f" · language thread: {language_interest}"
    dimension = len(grid.get("fill", []))
    if dimension < 1 or any(
        not isinstance(row, str) or len(row) != dimension
        for row in grid.get("fill", [])
    ):
        raise ValueError("Native fill returned inconsistent grid dimensions")
    metadata = {
        "date": now.strftime("%y%m%d"),
        "title": title,
        "authors": ["Local model + xfill"],
        "width": dimension,
        "height": dimension,
        "notepad": notepad,
    }
    crossword = Crossword.model_validate({"metadata": metadata, "entries": entries})
    manifest = register_legacy_puzzle(
        crossword,
        allow_token_cells=any(
            len(cell["fillToken"]) > 1 for cell in native_tokens.values()
        )
        or any(
            len(token) > 1
            for raw in grid["entries"]
            if isinstance(raw, dict)
            for token in (raw.get("cellTokens") or [])
            if isinstance(token, str)
        ),
    )
    return crossword, manifest


def _private_fill_violations(grid):
    """Return accidental construction artefacts before clue writing begins."""
    entries = grid.get("entries") if isinstance(grid, dict) else None
    if not isinstance(entries, list):
        return []
    return [
        entry.get("answer")
        for entry in entries
        if isinstance(entry, dict) and entry.get("answer") in _PRIVATE_FILL_BLOCKLIST
    ]


def _fill_quality_number(value):
    """Return whether a native xfill quality value is finite and numeric."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _fill_board_digest(grid):
    """Identify an attempted board without copying its answer fill into provenance."""
    if not isinstance(grid, dict):
        return None
    fill = grid.get("fill")
    entries = grid.get("entries")
    if not isinstance(fill, list) or not isinstance(entries, list):
        return None
    projection = {
        "fill": fill,
        "entries": [
            {
                key: entry.get(key)
                for key in ("num", "dir", "row", "col", "len", "answer", "theme")
            }
            for entry in entries
            if isinstance(entry, dict)
        ],
    }
    return _digest(projection)


def _fill_quality_report(grid):
    """Read the xfill score receipt without turning it into human quality.

    The native runtime reports scores from its pinned word list.  They are
    useful for comparing deterministic retry candidates, but they do not
    establish clue fairness or a player's chance of solving the board.  When a
    caller supplies a fixture without those fields, report that fact instead
    of manufacturing a score or applying a private-play rejection gate.
    """
    if not isinstance(grid, dict) or not isinstance(grid.get("entries"), list):
        return {
            "version": FILL_QUALITY_POLICY_VERSION,
            "status": "unavailable",
            "reason": "grid-quality-fields-unavailable",
            "uncertainty": "xfill-heuristic-not-human-quality",
        }
    fields = {
        "entryCount": len(grid["entries"]),
        "meanScore": grid.get("mean_score"),
        "minimumScore": grid.get("min_score"),
        "iffyCount": grid.get("iffy"),
        "weakCount": grid.get("weak"),
    }
    if not all(
        _fill_quality_number(fields[key]) for key in fields if key != "entryCount"
    ):
        return {
            "version": FILL_QUALITY_POLICY_VERSION,
            "status": "unavailable",
            "reason": "native-quality-receipt-missing-or-invalid",
            "entryCount": fields["entryCount"],
            "uncertainty": "xfill-heuristic-not-human-quality",
        }
    weak_without_crossing = _native_weak_without_crossing(grid)
    theme_count = sum(
        1
        for entry in grid["entries"]
        if isinstance(entry, dict) and entry.get("theme") is True
    )
    return {
        "version": FILL_QUALITY_POLICY_VERSION,
        "status": "measured",
        **fields,
        "weakWithoutCrossing": weak_without_crossing,
        "weakWithoutCrossingCount": len(weak_without_crossing),
        "themeCount": theme_count,
        "source": "native-xfill-reported",
        "uncertainty": "xfill-heuristic-not-human-quality",
    }


def _native_weak_without_crossing(grid, *, weak_threshold=60):
    """Return weak native entries with no crossing cells.

    This is a topology-only construction signal. It is answer-free and is
    never interpreted as a solve-probability or familiarity estimate.
    """
    raw_entries = grid.get("entries") if isinstance(grid, dict) else None
    if not isinstance(raw_entries, list):
        return []
    cells = {}
    weak_entries = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        entry_id = f"{raw.get('num')}{raw.get('dir')}"
        row, col, length, direction = (
            raw.get("row"), raw.get("col"), raw.get("len"), raw.get("dir")
        )
        score = raw.get("score")
        if (
            not isinstance(row, int)
            or isinstance(row, bool)
            or not isinstance(col, int)
            or isinstance(col, bool)
            or not isinstance(length, int)
            or isinstance(length, bool)
            or length < 1
            or direction not in {"A", "D"}
        ):
            continue
        coordinates = []
        for offset in range(length):
            coordinate = (
                row if direction == "A" else row + offset,
                col + offset if direction == "A" else col,
            )
            coordinates.append(coordinate)
            cells.setdefault(coordinate, []).append(entry_id)
        if (
            isinstance(score, (int, float))
            and not isinstance(score, bool)
            and math.isfinite(float(score))
            and float(score) < weak_threshold
        ):
            weak_entries.append((entry_id, coordinates))
    return sorted(
        entry_id
        for entry_id, coordinates in weak_entries
        if not any(len(cells.get(coordinate, ())) > 1 for coordinate in coordinates)
    )


def _fill_quality_selection_key(report, attempt_index, *, theme_floor=0):
    """Return deterministic ordering among measured retry candidates.

    Preserve a small amount of authored/personalized theme when a candidate
    survives with a reasonable weak-entry band. A theme floor is only a
    preference among candidates with the same iffy count; it never rejects a
    playable board and it falls back to the older score ordering when no
    candidate meets the floor.
    """
    if report.get("status") != "measured":
        # An unmeasured fixture is retained as a safe compatibility fallback,
        # but it never outranks a measured native-runtime candidate.
        return (1, 0, 1, 0, 0, 0, 0, attempt_index)
    entry_count = report.get("entryCount", 0)
    weak_limit = max(12, math.ceil(entry_count * 0.25))
    if theme_floor >= 3:
        # A Thursday mechanic is the day's discoverable content. Once a
        # candidate has the required instances, preserve it even when its
        # structural weak-entry band is wider than the ordinary policy. Iffy
        # count still leads the ordering, and the uncertainty stays visible.
        retains_theme = report.get("themeCount", 0) >= theme_floor
    else:
        retains_theme = (
            theme_floor <= 0
            or (
                report.get("themeCount", 0) >= theme_floor
                and report.get("weakCount", weak_limit + 1) <= weak_limit
            )
        )
    if theme_floor >= 3:
        # Thursday should keep its discoverable rule when the themed board is
        # still within a bounded mechanical-risk budget. If every themed
        # candidate exceeds that budget, ordinary fill quality wins and the
        # mechanic is truthfully reported unavailable.
        mechanic_candidate = (
            retains_theme
            and report.get("iffyCount", THURSDAY_MECHANIC_MAX_IFFY + 1)
            <= THURSDAY_MECHANIC_MAX_IFFY
        )
        return (
            0 if mechanic_candidate else 1,
            report["iffyCount"],
            report.get("weakWithoutCrossingCount", 0),
            report["weakCount"],
            -report["meanScore"],
            -report["minimumScore"],
            -report.get("themeCount", 0),
            attempt_index,
        )
    return (
        0,
        report["iffyCount"],
        0 if retains_theme else 1,
        report.get("weakWithoutCrossingCount", 0),
        report["weakCount"],
        -report["meanScore"],
        -report["minimumScore"],
        -report["themeCount"],
        attempt_index,
    )


def _fill_retry_options(seed, options):
    """Build a small deterministic set of quality alternatives.

    Every option is still a native xfill request.  The final two candidates
    progressively release theme locks so a difficult personalized theme does
    not make the full grid unavailable.  This is selection, not a quality
    gate: if every valid candidate is weak, the best one remains playable and
    its uncertainty is retained in provenance.
    """
    themes = options.get("themes", [])
    # The bundled native runtime accepts at most four theme locks. Keep the
    # full model proposal available for the local-anchor retry, but never send
    # an invalid five-lock request to xfill.
    native_themes = list(themes[:_NATIVE_THEME_LOCK_LIMIT])
    if options.get("gridSize") == 21:
        # A large Sunday board needs a reliable escape from an unlucky model
        # theme set. Try the player's set first, then a known placeable local
        # theme package before spending the expensive open-grid search.
        specs = [
            ("theme-locked-primary", seed, native_themes),
            (
                "sunday-anchor-fallback",
                _SUNDAY_FALLBACK_SEED,
                list(_SUNDAY_FALLBACK_THEMES),
            ),
            (
                "reduced-theme-fallback",
                seed,
                list(themes[:1]),
            ),
            (
                "open-grid-reseed",
                (seed + 2 * _FILL_RETRY_SEED_STEP) % 2_147_483_648,
                [],
            ),
        ]
    else:
        local_words = _local_fill_word_set()
        local_candidates = [
            theme
            for theme in themes
            if isinstance(theme, str) and theme in local_words
        ]
        local_anchor = sorted(
            local_candidates,
            key=lambda theme: (len(theme), theme),
        )[:2]
        theme_relief = (
            [("local-theme-anchor", seed, local_anchor)]
            if local_anchor
            else [("reduced-theme-fallback", seed, list(themes[:1]))]
        )
        specs = [
            ("theme-locked-primary", seed, native_themes),
            *theme_relief,
            (
                "theme-locked-reseed",
                (seed + _FILL_RETRY_SEED_STEP) % 2_147_483_648,
                native_themes,
            ),
            (
                "open-grid-reseed",
                (seed + 2 * _FILL_RETRY_SEED_STEP) % 2_147_483_648,
                [],
            ),
        ]
    attempts = []
    seen = set()
    for label, attempt_seed, attempt_themes in specs:
        identity = (attempt_seed, tuple(attempt_themes))
        if identity in seen:
            continue
        seen.add(identity)
        attempt_options = {
            **options,
            "seed": attempt_seed,
            "themes": attempt_themes,
        }
        # Sunday has four times the cells. Give its final open-grid rescue a
        # larger native search budget so an unlucky thematic proposal does not
        # make the 21×21 lane appear unavailable. The budget is still bounded
        # by the runtime contract and is retained in the attempt receipt.
        if options.get("gridSize") == 21:
            if label == "theme-locked-primary":
                # Probe the personalized locks briefly. A full Sunday search
                # can spend minutes proving an unlucky theme set impossible;
                # the deterministic anchor below is the bounded playable
                # fallback for local-first sessions.
                attempt_options.update({"candidates": 10, "time": 0.25})
            elif label == "open-grid-reseed":
                attempt_options.update({"candidates": 400, "time": 10})
            elif label == "sunday-anchor-fallback":
                # The larger board's xfill score is intentionally advisory:
                # this known-placeable anchor has a healthy mean score but
                # more weak fills than the 15x15 gate. Keep it playable and
                # retain the measured uncertainty in provenance.
                attempt_options.update({"candidates": 200, "time": 5, "maxIffy": 100})
            elif label in {"theme-locked-reseed"}:
                attempt_options.update({"candidates": 250, "time": 7})
        attempts.append(
            {
                "label": label,
                "seed": attempt_seed,
                "options": attempt_options,
            }
        )
        if len(attempts) >= _FILL_RETRY_MAX_ATTEMPTS:
            break
    return attempts


def _fill_quality_policy(attempts, selected_index, *, theme_floor=0):
    """Freeze the bounded comparison receipt for the selected fill."""
    measured = [
        attempt
        for attempt in attempts
        if attempt.get("quality", {}).get("status") == "measured"
    ]
    return {
        "version": FILL_QUALITY_POLICY_VERSION,
        "status": "measured" if measured else "unavailable",
        "attemptCount": len(attempts),
        "selectedAttempt": selected_index + 1 if selected_index is not None else None,
        "themeFloor": theme_floor,
        "selectionBasis": (
            "fewest-iffy-then-theme-floor-then-isolated-weak-then-weak-then-mean-then-min"
            if measured
            else "first-valid-board-without-native-quality-receipt"
        ),
        "attempts": attempts,
        "uncertainty": "xfill-heuristic-not-human-quality",
    }


def _crossing_support_summary(grid, entries):
    """Report structural crossing access without claiming player support."""
    raw_entries = grid.get("entries") if isinstance(grid, dict) else None
    fill = grid.get("fill") if isinstance(grid, dict) else None
    if not isinstance(raw_entries, list) or not isinstance(fill, list):
        return {
            "version": "structural-crossing-v1",
            "status": "unavailable",
            "entryCount": 0,
            "weakEntryCount": 0,
            "weakWithoutCrossing": [],
            "minimumScore": None,
            "meanScore": None,
            "uncertainty": "player-support-unmeasured",
        }
    cells = {}
    by_id = {}
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        entry_id = f"{raw.get('num')}{raw.get('dir')}"
        row, col, length = raw.get("row"), raw.get("col"), raw.get("len")
        if (
            not isinstance(row, int)
            or not isinstance(col, int)
            or not isinstance(length, int)
            or length < 1
            or raw.get("dir") not in {"A", "D"}
        ):
            continue
        by_id[entry_id] = raw
        for offset in range(length):
            coordinate = (
                row if raw["dir"] == "A" else row + offset,
                col + offset if raw["dir"] == "A" else col,
            )
            cells.setdefault(coordinate, []).append(entry_id)
    scores = []
    weak_without_crossing = []
    edges = []
    weak_count = 0
    for entry in entries if isinstance(entries, list) else []:
        entry_id = entry.get("id") if isinstance(entry, dict) else None
        raw = by_id.get(entry_id)
        if not isinstance(entry_id, str) or not isinstance(raw, dict):
            continue
        row, col, length = raw["row"], raw["col"], raw["len"]
        crossing_cells = []
        support_ids = set()
        for offset in range(length):
            coordinate = (
                row if raw["dir"] == "A" else row + offset,
                col + offset if raw["dir"] == "A" else col,
            )
            other_ids = [item for item in cells.get(coordinate, []) if item != entry_id]
            if other_ids:
                crossing_cells.append(coordinate)
                support_ids.update(other_ids)
        score = round(len(crossing_cells) / length, 3) if length else 0
        scores.append(score)
        is_weak = entry.get("needsFoothold") is True
        if is_weak:
            weak_count += 1
            if not crossing_cells:
                weak_without_crossing.append(entry_id)
        edges.append(
            {
                "entryId": entry_id,
                "crossingCellCount": len(crossing_cells),
                "crossingScore": score,
                "supportEntryIds": sorted(support_ids),
            }
        )
    return {
        "version": "structural-crossing-v1",
        "status": "measured",
        "entryCount": len(scores),
        "weakEntryCount": weak_count,
        "weakWithoutCrossing": sorted(weak_without_crossing),
        "minimumScore": min(scores) if scores else None,
        "meanScore": round(sum(scores) / len(scores), 3) if scores else None,
        "edges": edges,
        "uncertainty": "player-support-unmeasured",
    }


def _fallback_support_receipt(fallback_reasons, crossing_support):
    """Bind answer-free clue fallbacks to structural crossing metadata.

    This receipt gives the client a useful route into an ungrounded clue
    without exposing its answer or pretending that topology predicts a solve.
    Entry IDs and crossing counts are structural only; semantic meaning and
    player support remain explicitly unknown.
    """
    if not isinstance(fallback_reasons, Mapping):
        return {
            "version": "private-clue-fallback-support-v1",
            "status": "empty",
            "entryCount": 0,
            "withCrossingCount": 0,
            "entries": [],
            "uncertainty": "player-support-unmeasured",
        }
    edges = {
        edge.get("entryId"): edge
        for edge in (crossing_support.get("edges", []) if isinstance(crossing_support, Mapping) else [])
        if isinstance(edge, Mapping) and isinstance(edge.get("entryId"), str)
    }
    receipt_entries = []
    for entry_id in sorted(fallback_reasons):
        if not isinstance(entry_id, str):
            continue
        edge = edges.get(entry_id, {})
        support_ids = edge.get("supportEntryIds", [])
        receipt_entries.append(
            {
                "entryId": entry_id,
                "reasonCodes": sorted(
                    {
                        reason
                        for reason in (fallback_reasons.get(entry_id, []) or [])
                        if isinstance(reason, str)
                    }
                ),
                "crossingCellCount": edge.get("crossingCellCount", 0),
                "supportEntryIds": sorted(
                    item for item in support_ids if isinstance(item, str)
                ),
            }
        )
    return {
        "version": "private-clue-fallback-support-v1",
        "status": "measured" if isinstance(crossing_support, Mapping) and crossing_support.get("status") == "measured" else "structural-only",
        "entryCount": len(receipt_entries),
        "withCrossingCount": sum(
            1 for entry in receipt_entries if entry["crossingCellCount"] > 0
        ),
        "entries": receipt_entries[:64],
        "uncertainty": "player-support-unmeasured",
    }


def _generate(
    seed,
    weekday,
    starting,
    episteme,
    *,
    stage_callback=None,
    model_override=None,
):
    def report_stage(stage):
        if callable(stage_callback):
            try:
                stage_callback(stage)
            except Exception:
                # Progress is advisory. A temporary status-write failure must
                # never discard an otherwise playable local puzzle.
                pass

    total_started = monotonic()
    model = _resolve_model_override(model_override)
    context = _profile_context(starting, episteme.profile_json)
    recipe = _effective_weekday_recipe(weekday, context)
    report_stage("theme-proposal")
    theme_started = monotonic()
    theme_mechanic = None
    mechanic_unavailable_reason = None
    theme_proposal_source = "model"
    if weekday == "thursday":
        try:
            themes, theme_mechanic = _make_thursday_theme_proposal(model, context)
        except Exception:
            # Keep Thursday useful when the model misses its structured
            # response: choose a checked local vocabulary group and let the
            # final native fill validate it. If that local lane is unavailable,
            # preserve the ordinary-theme fail-open route.
            try:
                themes, theme_mechanic = _deterministic_thursday_theme_proposal(
                    context
                )
                theme_proposal_source = "deterministic-local-affix-group"
            except Exception:
                mechanic_unavailable_reason = "proposal-unavailable"
                theme_proposal_source = "ordinary-theme-fallback"
                themes = _make_themes(model, context, weekday)
    else:
        themes = _make_themes(model, context, weekday)
    theme_proposal_seconds = max(0.0, monotonic() - theme_started)
    difficulty = _DIFFICULTY[weekday]
    grid_size = 21 if weekday == "sunday" else 15
    options = {
        "seed": seed,
        "candidates": difficulty["candidates"],
        "time": difficulty["time"],
        "keepMean": 50,
        "minScore": 40,
        "maxIffy": 20,
        "themes": themes[: recipe["themeAnswerCount"]],
    }
    if grid_size == 21:
        options["gridSize"] = 21
    report_stage("native-xfill")
    xfill_started = monotonic()
    # Generated theme tokens can be unfamiliar to the bundled fill list, and a
    # local lexicon can contain an accidental artefact. Evaluate a bounded,
    # deterministic set of native retries and choose the best measured board;
    # this improves the usual case without turning heuristic scores into a
    # private-play rejection gate.
    result = None
    selected_attempt_index = None
    selected_seed = seed
    last_fill_error = None
    fill_attempts = []
    successful_fills = []
    # Tuesday keeps up to two surviving theme locks when the native fill can
    # support them. Base that floor on locally placeable invitations: a model
    # may propose five words while only one is available to the native list.
    # A single placeable invitation still receives a one-theme floor, and an
    # unplaceable set releases to the ordinary fallback candidates.
    local_fill_words = _local_fill_word_set()
    theme_candidates = [
        theme
        for theme in options.get("themes", [])
        if isinstance(theme, str) and theme in local_fill_words
    ]
    if weekday == "tuesday":
        theme_floor = min(2, len(theme_candidates)) or min(
            1, len(options.get("themes", []))
        )
    else:
        theme_floor = min(2, len(options.get("themes", [])))
    # A validated Thursday proposal is only meaningful when at least three
    # instances survive the fill. Prefer that stronger floor during candidate
    # selection; if no candidate meets it, the ordinary open-grid fallback
    # remains playable and the provenance records the unavailable mechanic.
    mechanic_theme_floor = (
        3
        if weekday == "thursday" and theme_mechanic is not None
        else theme_floor
    )
    for attempt_index, retry in enumerate(_fill_retry_options(seed, options)):
        retry_options = retry["options"]
        attempt_record = {
            "attempt": attempt_index + 1,
            "label": retry["label"],
            "seed": retry["seed"],
            "options": retry_options,
            "themeLocks": list(retry_options["themes"]),
            "status": "pending",
        }
        try:
            candidate = generate_full_size_draft(
                seed=retry["seed"], options=retry_options
            )
            candidate_grid = (
                candidate.get("grid") if isinstance(candidate, dict) else None
            )
            if not isinstance(candidate_grid, dict) or not isinstance(
                candidate_grid.get("entries"), list
            ):
                raise FullSizeRuntimeUnavailable(
                    "Native fill returned no usable entry list"
                )
            violations = _private_fill_violations(candidate_grid)
            if violations:
                attempt_record.update(
                    {
                        "status": "rejected",
                        "reason": "private-fill-blocklist",
                        "violations": violations,
                        "quality": _fill_quality_report(candidate_grid),
                        "boardDigest": _fill_board_digest(candidate_grid),
                        "sourceDigest": candidate.get("sourceDigest")
                        if isinstance(candidate, dict)
                        else None,
                    }
                )
                fill_attempts.append(attempt_record)
                last_fill_error = FullSizeDraftRejected(
                    "Native fill contained an accidental construction artefact"
                )
                continue
            quality = _fill_quality_report(candidate_grid)
            attempt_record.update(
                {
                    "status": "candidate",
                    "quality": quality,
                    "boardDigest": _fill_board_digest(candidate_grid),
                    "sourceDigest": candidate.get("sourceDigest")
                    if isinstance(candidate, dict)
                    else None,
                }
            )
            fill_attempts.append(attempt_record)
            successful_fills.append(
                {
                    "index": attempt_index,
                    "seed": retry["seed"],
                    "options": retry_options,
                    "candidate": candidate,
                    "quality": quality,
                }
            )
            # Sunday generation is already a large native search. Once a
            # measured 21x21 candidate clears the runtime's own gates, keep
            # the first playable board instead of launching another bounded
            # search just to make a heuristic comparison. The attempt receipt
            # still records every try made before this success.
            if options.get("gridSize") == 21 and quality["status"] == "measured":
                break
            # A fixture or older runtime without native quality fields cannot
            # be ranked honestly. Retain the first valid board and record that
            # comparison was unavailable; production xfill always reports the
            # measured fields above.
            if quality["status"] != "measured":
                break
        except (FullSizeDraftRejected, FullSizeRuntimeUnavailable) as error:
            last_fill_error = error
            attempt_record.update({"status": "failed", "reason": str(error)[:240]})
            fill_attempts.append(attempt_record)
    if result is None:
        if not successful_fills:
            raise last_fill_error or FullSizeRuntimeUnavailable(
                "The local construction runtime did not return a usable fill"
            )
        selected = min(
            successful_fills,
            key=lambda item: _fill_quality_selection_key(
                item["quality"],
                item["index"],
                theme_floor=mechanic_theme_floor,
            ),
        )
        result = selected["candidate"]
        selected_attempt_index = selected["index"]
        selected_seed = selected["seed"]
        options = selected["options"]
    fill_policy = _fill_quality_policy(
        fill_attempts, selected_attempt_index, theme_floor=mechanic_theme_floor
    )
    native_xfill_seconds = max(0.0, monotonic() - xfill_started)
    grid = result.get("grid") if isinstance(result, dict) else None
    if not isinstance(grid, dict) or not isinstance(grid.get("entries"), list):
        raise ValueError("Native fill returned no entries")
    grid = construct_native_token_grid(grid)
    token_construction = validate_native_token_cells(grid)
    active_theme_mechanic = None
    mechanic_theme_answers = [
        entry.get("answer")
        for entry in grid["entries"]
        if isinstance(entry, dict) and entry.get("theme") is True
    ]
    if theme_mechanic is not None:
        active_theme_mechanic = _validate_shared_affix_mechanic(
            mechanic_theme_answers, theme_mechanic
        )
        if active_theme_mechanic is None:
            mechanic_unavailable_reason = (
                "insufficient-themed-entries"
                if len(mechanic_theme_answers) < 3
                else "fill-pattern-mismatch"
            )
    clue_entries = [
        {
            "id": f"{entry['num']}{entry['dir']}",
            "number": entry["num"],
            "direction": "across" if entry["dir"] == "A" else "down",
            "answer": entry["answer"],
            "length": entry["len"],
            "theme": entry.get("theme") is True,
            "fillScore": entry.get("score"),
            "needsFoothold": isinstance(entry.get("score"), (int, float))
            and entry.get("score", 100) < 60,
            "cluePolicy": (
                "source-free-foothold"
                if (
                    isinstance(entry.get("score"), (int, float))
                    and entry.get("score", 100) < 60
                )
                else "ordinary-definition-or-signalled-wordplay"
            ),
        }
        for entry in grid["entries"]
    ]
    pre_clue_construction = evaluate_private_board(
        grid,
        clue_entries,
        source_digest=result.get("sourceDigest") if isinstance(result, dict) else None,
    )
    clue_context = {
        **context,
        "_foothold_seed_plan": pre_clue_construction.get("footholdSeedPlan"),
        "_candidate_base_seed": selected_seed,
    }
    if active_theme_mechanic is not None:
        clue_context["_weekday_theme_mechanic"] = active_theme_mechanic
    reviewed_clue_pack = _load_reviewed_clue_pack(clue_entries)
    report_stage("clue-generation")
    clue_started = monotonic()
    if reviewed_clue_pack.get("byId"):
        title, clues = _make_clues(
            model,
            clue_entries,
            clue_context,
            weekday,
            reviewed_pack=reviewed_clue_pack,
        )
    else:
        title, clues = _make_clues(model, clue_entries, clue_context, weekday)
    clue_generation_seconds = max(0.0, monotonic() - clue_started)
    challenge_enabled = os.environ.get(
        PRIVATE_CLUE_CHALLENGE_ENV, ""
    ).strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if challenge_enabled:
        report_stage("clue-challenge")
    clue_challenge_started = monotonic() if challenge_enabled else None
    clue_challenge = _challenge_private_clues(
        model,
        clue_entries,
        clues,
        clue_context,
        weekday,
    )
    clue_challenge_seconds = (
        max(0.0, monotonic() - clue_challenge_started)
        if clue_challenge_started is not None
        else 0.0
    )
    report_stage("finalizing")
    clue_quality = _clue_quality_summary(
        clue_entries,
        clues,
        weekday=weekday,
        model_challenges=clue_challenge.get("byId", {}),
        reviewed_pack=reviewed_clue_pack,
        safety_fallbacks=clue_context.get("_clue_safety_fallbacks"),
    )
    clue_quality["reviewedCluePack"] = _reviewed_clue_pack_summary(
        reviewed_clue_pack
    )
    if isinstance(clue_context.get("_clue_generation_fallback"), str):
        clue_quality["generationFallback"] = {
            "status": "answer-free-scaffold",
            "reason": clue_context["_clue_generation_fallback"],
            "playPolicy": "fail-open-private-play",
        }
    clue_diversity = _clue_diversity_report(
        clue_entries,
        clues,
        repair=clue_context.get("_clue_diversity_repair"),
    )
    clue_quality["diversity"] = clue_diversity
    crossing_support = _crossing_support_summary(grid, clue_entries)
    clue_quality["fallbackSupport"] = _fallback_support_receipt(
        clue_context.get("_clue_safety_fallbacks"), crossing_support
    )
    # Q03: keep every generated surface in a local answer-bearing corpus so
    # later guards and scorers have a denominator. Fail-open and local-only;
    # the committed artifact carries counts plus a digest, never clue text.
    corpus_issues_by_id = {}
    for _corpus_entry in clue_entries:
        _corpus_clue = clues.get(_corpus_entry["id"], "")
        _corpus_codes = []
        for _corpus_issue in (
            _clue_wordplay_issue(_corpus_entry, _corpus_clue),
            _clue_morphology_issue(_corpus_entry, _corpus_clue),
            _clue_information_issue(_corpus_entry, _corpus_clue, weekday=weekday),
        ):
            if isinstance(_corpus_issue, str) and _corpus_issue:
                _corpus_codes.append(_corpus_issue)
        for _corpus_flag in _clue_risk_flags(_corpus_entry, _corpus_clue) or []:
            if (
                isinstance(_corpus_flag, str)
                and _corpus_flag
                and _corpus_flag != "foothold-required"
            ):
                _corpus_codes.append(_corpus_flag)
        if _corpus_codes:
            corpus_issues_by_id[_corpus_entry["id"]] = sorted(set(_corpus_codes))
    _corpus_safety = clue_context.get("_clue_safety_fallbacks")
    _corpus_challenge_by_id = {}
    for _grounding_entry in (
        clue_quality.get("grounding", {}).get("entries", []) or []
    ):
        _challenge = _grounding_entry.get("semanticChallenge")
        _classification = (
            _challenge.get("classification") if isinstance(_challenge, dict) else None
        )
        if isinstance(_grounding_entry.get("id"), str) and isinstance(
            _classification, str
        ):
            _corpus_challenge_by_id[_grounding_entry["id"]] = _classification
    _corpus_reviewed_by_id = reviewed_clue_pack.get("byId")
    clue_corpus_receipt = append_corpus_records(
        build_corpus_records(
            clue_entries,
            clues,
            weekday=weekday,
            seed=selected_seed,
            model_tag=model,
            issues_by_id=corpus_issues_by_id,
            fallback_ids=[
                _entry_id
                for _entry_id, _reasons in (
                    _corpus_safety.items()
                    if isinstance(_corpus_safety, dict)
                    else []
                )
                if isinstance(_reasons, list) and _reasons
            ],
            reviewed_ids=list(_corpus_reviewed_by_id.keys())
            if isinstance(_corpus_reviewed_by_id, dict)
            else [],
            challenge_by_id=_corpus_challenge_by_id,
        )
    )
    construction_evidence = evaluate_private_board(
        grid,
        clue_entries,
        source_digest=result.get("sourceDigest") if isinstance(result, dict) else None,
        clue_quality=clue_quality,
    )
    sibling_evaluator_adapter = evaluate_sibling_adapter(
        grid,
        clue_entries,
        clues,
        board_digest=construction_evidence.get("boardDigest"),
        source_digest=result.get("sourceDigest") if isinstance(result, dict) else None,
    )
    construction_evidence["siblingEvaluatorAdapter"] = sibling_evaluator_adapter
    fill_quality = {
        "entryCount": len(grid["entries"]),
        "meanScore": grid.get("mean_score"),
        "minimumScore": grid.get("min_score"),
        "iffyCount": grid.get("iffy"),
        "weakCount": grid.get("weak"),
        "footholdCount": sum(1 for item in clue_entries if item["needsFoothold"]),
        "weakWithoutCrossing": crossing_support.get("weakWithoutCrossing", []),
        "weakWithoutCrossingCount": len(
            crossing_support.get("weakWithoutCrossing", [])
        ),
        "qualityPolicy": fill_policy,
    }
    timings = {
        "themeProposal": round(theme_proposal_seconds, 3),
        "nativeXfill": round(native_xfill_seconds, 3),
        "clueGeneration": round(clue_generation_seconds, 3),
        "total": round(max(0.0, monotonic() - total_started), 3),
    }
    if clue_challenge.get("enabled") is True:
        timings["clueChallenge"] = round(clue_challenge_seconds, 3)
        # Preserve the historical ordering used by local diagnostics.
        timings = {
            "themeProposal": timings["themeProposal"],
            "nativeXfill": timings["nativeXfill"],
            "clueGeneration": timings["clueGeneration"],
            "clueChallenge": timings["clueChallenge"],
            "total": timings["total"],
        }
    language_learning = _language_learning_generation_record(
        context, clue_entries, clues
    )
    if isinstance(language_learning, dict):
        language_cells = emit_single_cell_language_tokens(
            grid,
            language_learning.get("tokenHints"),
            language=language_learning.get("language")
            or context.get("language_interest"),
            source=language_learning.get("tokenHintSource"),
        )
        if language_cells:
            grid["tokenCells"] = language_cells
    grid = construct_native_token_grid(grid)
    token_construction = validate_native_token_cells(grid)
    crossword, manifest = _legacy_puzzle(
        grid,
        themes,
        title,
        clues,
        model,
        weekday,
        selected_seed,
        context.get("language_interest"),
    )
    native_hints = native_token_hints(grid)
    if native_hints and isinstance(language_learning, dict):
        existing_hints = language_learning.get("tokenHints", [])
        combined_hints = []
        for hint in [*existing_hints, *native_hints]:
            if hint not in combined_hints:
                combined_hints.append(hint)
        language_learning = {
            **language_learning,
            "tokenHints": combined_hints[:16],
            "tokenHintSource": "native-constructor",
        }
    theme_proposal_receipt = {
        "source": theme_proposal_source,
        "mechanicRequested": weekday == "thursday" and theme_mechanic is not None,
    }
    domain_hint_receipt = private_domain_hint_receipt(context.get("domain_hints"))
    if domain_hint_receipt.get("status") == "loaded":
        theme_proposal_receipt["domainHints"] = domain_hint_receipt
    provenance = {
        "source": "local-ollama-xfill",
        "model": model,
        "engine": "xfill",
        "seed": seed,
        "weekday": weekday,
        "modelRuntimePolicy": _model_runtime_policy_receipt(model),
        "personalizationReceipt": _personalization_receipt(
            episteme.profile_json,
            context,
            seed=seed,
            weekday=weekday,
            model=model,
        ),
        "weekdayRecipe": {
            "id": recipe["id"],
            "intent": recipe["intent"],
            "themeMode": (
                "shared-affix"
                if active_theme_mechanic is not None
                else (
                    "standard-theme" if weekday == "thursday" else recipe["themeMode"]
                )
            ),
            "themeAnswerTarget": recipe["themeAnswerCount"],
            "themeLocksUsed": len(options["themes"]),
            "themeEntriesUsed": sum(1 for entry in clue_entries if entry["theme"]),
            **(
                {"difficultyVariant": recipe["difficultyVariant"]}
                if isinstance(recipe.get("difficultyVariant"), str)
                else {}
            ),
            **(
                {
                    "minimumNonDefinitionFamilies": recipe["minimumNonDefinitionFamilies"],
                    "minimumNonDefinitionCount": recipe["minimumNonDefinitionCount"],
                    "requiredNonDefinitionFamilySet": list(
                        recipe.get("requiredNonDefinitionFamilySet", ())
                    ),
                }
                if isinstance(recipe.get("minimumNonDefinitionFamilies"), int)
                and isinstance(recipe.get("minimumNonDefinitionCount"), int)
                else {}
            ),
            "gridMechanic": "ordinary-letter-grid",
        },
        "themeProposal": theme_proposal_receipt,
        "themeExposure": _theme_exposure_receipt(context, clue_entries),
        "languageInterest": context.get("language_interest"),
        "languageLearning": language_learning,
        "playCalibration": context.get("play_calibration"),
        "clueFamilyTargets": context.get("clue_family_targets", []),
        "clueFamilyFatigue": context.get("recent_clue_family_exposures"),
        "themeAnswers": [item["answer"] for item in clue_entries if item["theme"]],
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "experimental": True,
        "fillQuality": {
            **fill_quality,
        },
        "crossingSupport": crossing_support,
        # This is a local structural receipt.  It intentionally records the
        # sibling evaluator boundary and never turns topology into player
        # support or a completion prediction.
        "constructionEvidence": construction_evidence,
        # The adapter is a lab-only diagnostic.  Missing explicit estimates
        # produce ``not-invoked`` and an unavailable sibling runtime produces
        # ``failed``; neither state affects playable private generation.
        "siblingEvaluatorAdapter": sibling_evaluator_adapter,
        "clueQuality": clue_quality,
        "clueCorpus": clue_corpus_receipt,
        "clueGenerationBatches": context.get("_clue_generation_batches"),
        "candidateGeneration": context.get("_candidate_generation"),
        "clueGenerationTiming": clue_context.get("_clue_generation_timing"),
        "clueGenerationFallback": (
            {
                "status": "answer-free-scaffold",
                "reason": clue_context["_clue_generation_fallback"],
                "playPolicy": "fail-open-private-play",
            }
            if isinstance(clue_context.get("_clue_generation_fallback"), str)
            else None
        ),
        "clueDiversity": clue_diversity,
        "clueBundle": clue_quality["groundedClueBundle"],
        "reviewedCluePack": _reviewed_clue_pack_summary(reviewed_clue_pack),
        # Optional local-model recommendations are retained as advisory
        # evidence. The deterministic challenger still owns classification,
        # and private play never waits on or gates on this pass.
        "semanticClueChallenge": {
            key: value for key, value in clue_challenge.items() if key != "byId"
        },
        "timingsSeconds": timings,
        "tokenConstruction": {
            **token_construction,
            "language": context.get("language_interest"),
            "hints": native_hints[:16],
        },
    }
    if grid_size == 21:
        provenance["weekdayRecipe"]["gridSize"] = 21
    if weekday == "thursday":
        if active_theme_mechanic is not None:
            provenance["themeMechanic"] = {
                "status": "validated",
                **active_theme_mechanic,
                "themeAnswers": mechanic_theme_answers,
            }
        else:
            provenance["themeMechanic"] = {
                "status": "unavailable",
                "type": "shared-affix",
                "reason": mechanic_unavailable_reason or "fill-pattern-mismatch",
            }
        # Keep a digest-bound, answer-structural receipt beside the mechanic
        # declaration.  This is an inspection artifact for real generated
        # boards; it does not gate private play or make a fairness claim.
        provenance["mechanicEvaluation"] = evaluate_thursday_mechanic_board(
            {"entries": grid["entries"]},
            provenance,
            board_id=f"thursday-{selected_seed}",
        )
    return crossword, manifest, provenance


def _json_copy(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


@private_puzzle_api.post("/api/future/private-puzzle-jobs")
def create_private_puzzle_job():
    """Queue a playable local puzzle while the browser keeps its solver alive."""
    if not _local_origin():
        return _error("Cross-origin puzzle job creation is not allowed", 403)
    request.max_content_length = MAX_BODY_BYTES
    if (request.content_length or 0) > MAX_BODY_BYTES:
        return _error("Puzzle job request is too large", 413)
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not set(body).issubset(
        {"profileId", "idempotencyKey", "seed", "weekday", "model"}
    ) or not {"profileId", "idempotencyKey", "seed", "weekday"}.issubset(body):
        return _error(
            "Puzzle job request must include profileId, idempotencyKey, seed and weekday",
            400,
        )
    profile_id = body["profileId"]
    idempotency_key = body["idempotencyKey"]
    seed = body["seed"]
    weekday = body["weekday"]
    requested_model = body.get("model")
    if (
        not isinstance(profile_id, str)
        or not _UUID.fullmatch(profile_id)
        or str(UUID(profile_id)) != profile_id
        or not isinstance(idempotency_key, str)
        or not _UUID.fullmatch(idempotency_key)
        or str(UUID(idempotency_key)) != idempotency_key
        or type(seed) is not int
        or not 0 <= seed <= 2_147_483_647
        or weekday not in _WEEKDAYS
        or (requested_model is not None and not isinstance(requested_model, str))
    ):
        return _error("Invalid profile, idempotency key, seed or difficulty", 400)
    if requested_model is not None and requested_model not in _EXPLICIT_MODEL_TAGS:
        return _error("Unsupported local writing model", 400)

    intent = {
        "mode": "private-puzzle",
        "profileId": profile_id,
        "idempotencyKey": idempotency_key,
        "seed": seed,
        "weekday": weekday,
    }
    if requested_model is not None:
        intent["model"] = requested_model
    request_digest = _digest(intent)
    existing = FutureGridDraftJob.query.filter_by(
        profile_id=profile_id,
        idempotency_key=idempotency_key,
    ).one_or_none()
    if existing is not None:
        if existing.request_digest != request_digest:
            return _error(
                "Idempotency key was already used for a different request", 409
            )
        return _response(existing)

    starting = db.session.get(StartingProfile, profile_id)
    if starting is None:
        return _error("Profile not found; save the opening first", 404)
    effective_model = requested_model or _saved_model_override(starting)
    try:
        episteme = get_or_create_episteme_profile(profile_id, starting.updated_at)
    except (EpistemeCommandRejected, EpistemeRuntimeUnavailable):
        db.session.rollback()
        return _error("The local episteme could not be loaded", 503)
    if (
        not isinstance(episteme.profile_json, dict)
        or episteme.profile_json.get("profileId") != profile_id
        or episteme.profile_json.get("updatedAt") != episteme.updated_at
    ):
        db.session.rollback()
        return _error("The stored local episteme snapshot is inconsistent", 409)

    if effective_model is not None:
        try:
            _resolve_model_override(effective_model)
        except RuntimeError as error:
            db.session.rollback()
            return _error(str(error)[:240], 503)

    frozen = {
        "version": 1,
        "mode": "private-puzzle",
        "profileId": profile_id,
        "profileUpdatedAt": starting.updated_at,
        "startingProfile": _json_copy(starting.profile),
        "startingDraft": _json_copy(starting.draft),
        "epistemeRevision": episteme.revision,
        "epistemeUpdatedAt": episteme.updated_at,
        "epistemeProfile": _json_copy(episteme.profile_json),
        "weekday": weekday,
        "seed": seed,
        "stage": "private-puzzle",
    }
    if effective_model is not None:
        frozen["model"] = effective_model
    now = _stamp()
    job = FutureGridDraftJob(
        id=str(uuid4()),
        profile_id=profile_id,
        idempotency_key=idempotency_key,
        request_digest=request_digest,
        request_json=frozen,
        state="queued",
        created_at=now,
        updated_at=now,
    )
    db.session.add(job)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = FutureGridDraftJob.query.filter_by(
            profile_id=profile_id,
            idempotency_key=idempotency_key,
        ).one_or_none()
        if existing is None:
            raise
        if existing.request_digest != request_digest:
            return _error(
                "Idempotency key was already used for a different request", 409
            )
        return _response(existing)
    return _response(job, 202)


@private_puzzle_api.post("/api/future/private-puzzles")
def create_private_puzzle():
    """Make and return one immediately playable profile-personalized puzzle."""
    if not _local_origin():
        return _error("Cross-origin puzzle creation is not allowed", 403)
    request.max_content_length = MAX_BODY_BYTES
    if (request.content_length or 0) > MAX_BODY_BYTES:
        return _error("Puzzle request is too large", 413)
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not set(body).issubset(
        {"profileId", "seed", "weekday", "model"}
    ) or not {"profileId", "seed", "weekday"}.issubset(body):
        return _error("Puzzle request must include profileId, seed and weekday", 400)
    profile_id, seed, weekday = body["profileId"], body["seed"], body["weekday"]
    requested_model = body.get("model")
    if (
        not isinstance(profile_id, str)
        or not _UUID.fullmatch(profile_id)
        or str(UUID(profile_id)) != profile_id
        or type(seed) is not int
        or not 0 <= seed <= 2_147_483_647
        or weekday not in _WEEKDAYS
        or (requested_model is not None and not isinstance(requested_model, str))
    ):
        return _error("Invalid profile, seed or difficulty", 400)
    if requested_model is not None and requested_model not in _EXPLICIT_MODEL_TAGS:
        return _error("Unsupported local writing model", 400)
    starting = db.session.get(StartingProfile, profile_id)
    if starting is None:
        return _error("Profile not found; save the opening first", 404)
    effective_model = requested_model or _saved_model_override(starting)
    try:
        episteme = get_or_create_episteme_profile(profile_id, starting.updated_at)
        if effective_model is None:
            crossword, manifest, provenance = _generate(seed, weekday, starting, episteme)
        else:
            crossword, manifest, provenance = _generate(
                seed,
                weekday,
                starting,
                episteme,
                model_override=effective_model,
            )
    except (EpistemeCommandRejected, EpistemeRuntimeUnavailable):
        db.session.rollback()
        return _error("The local episteme could not be loaded", 503)
    except requests.RequestException:
        db.session.rollback()
        return _error("The local writing model did not finish; try again", 503)
    except RuntimeError as error:
        db.session.rollback()
        return _error(str(error)[:240], 503)
    except (
        ValueError,
        TypeError,
        KeyError,
        RecursionError,
        FullSizeDraftRejected,
        FullSizeRuntimeUnavailable,
    ) as error:
        db.session.rollback()
        message = str(error).strip()
        return _error(message[:240] or "Local puzzle generation failed", 422)
    # The playable manifest is the replay contract; keep the richer
    # experimental clue/fill receipt beside it for reload and postgame review.
    # A storage failure remains fail-open for local play.
    try:
        store_private_puzzle_provenance(
            profile_id=profile_id,
            manifest=manifest,
            provenance=provenance,
        )
    except (ValueError, TypeError, KeyError, RecursionError, IntegrityError):
        db.session.rollback()
    response = jsonify(
        {
            **crossword.model_dump(exclude={"across_entries", "down_entries"}),
            "puzzleManifest": manifest,
            "provenance": provenance,
        }
    )
    response.headers["Cache-Control"] = "no-store"
    return response
