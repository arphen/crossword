"""Host-side bridge for private clue-family observations.

The domain package owns the reviewed ``clue-grammar-v1`` annotation validator.
Private Ollama clues do not have editor-authored morphology, sense witnesses,
or source evidence, so they cannot be promoted to that annotation merely from
their text.  This module checks the smaller boundary that the private route can
actually observe: whether a generated family label agrees with the literal
surface signal that caused it.

The result is diagnostic provenance only.  A failed check never rejects a
private puzzle and no result establishes that a clue is true, fair, or
semantically equivalent to its answer.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


CLUE_GRAMMAR_BRIDGE_VERSION = "private-clue-grammar-bridge-v1"
HOUSE_GRAMMAR_VERSION = "clue-grammar-v1"

_FAMILIES = frozenset(
    {
        "definition",
        "factual-relation",
        "fill-blank",
        "spoken-equivalent",
        "nonverbal-expression",
        "semantic-misdirection",
        "pun",
        "metalinguistic",
        "linked",
        "theme-dependent",
    }
)

_REQUIRED_SURFACE_SIGNAL = {
    "spoken-equivalent": "quote",
    "nonverbal-expression": "brackets",
    "fill-blank": "fill-blank",
    "metalinguistic": "abbreviation-indicator",
    # The domain validator treats a question mark as optional for a reviewed
    # pun.  The private observer only chooses the pun family when it sees one,
    # so this is a consistency check on the observer, not a new house rule.
    "pun": "question-mark",
}

_NO_SURFACE_RULE = frozenset(
    {
        "definition",
        "factual-relation",
        "semantic-misdirection",
        "linked",
        "theme-dependent",
    }
)

_QUOTE_START = frozenset({'"', "“", "'", "‘"})
_QUOTE_END = frozenset({'"', "”", "'", "’"})
_ANNOTATED_SPOKEN_RE = re.compile(
    r"^[\"“'‘].+[\"”'’]\s*[\[(]\s*(?:spoken(?:\s+equivalent)?|utterance|said\s+aloud)\s*[\])]$",
    re.I,
)
_FILL_MARKER_RE = re.compile(r"(?:_{2,}|\b(?:and|or|to|of)\s+___\b)", re.I)
_ABBREVIATION_RE = re.compile(r"[\[(]\s*abbr\.?\s*[\])] |\bbriefly\b", re.I | re.X)


def _issue(code: str, message: str, path: str | None = None) -> dict[str, str]:
    result = {"code": code, "message": message}
    if path:
        result["path"] = path
    return result


def _signals(observation: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = observation.get("signals")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _surface_signal_present(
    clue: str, family: str, signals: list[Mapping[str, Any]]
) -> bool:
    """Return whether the literal surface contains the observed family cue."""

    text = clue.strip()
    if family == "spoken-equivalent":
        return (
            len(text) >= 2
            and text[0] in _QUOTE_START
            and text[-1] in _QUOTE_END
        ) or bool(_ANNOTATED_SPOKEN_RE.fullmatch(text))
    if family == "nonverbal-expression":
        return bool(re.fullmatch(r"\[[^\]]+\]", text))
    if family == "fill-blank":
        return bool(_FILL_MARKER_RE.search(text))
    if family == "metalinguistic":
        return bool(_ABBREVIATION_RE.search(text))
    if family == "pun":
        return text.endswith("?")
    return True


def _signal_matches_literal(clue: str, signal: Mapping[str, Any]) -> bool:
    """Check offsets when an observer supplied them, without inferring meaning."""

    if not isinstance(signal.get("kind"), str):
        return False
    start = signal.get("start")
    end = signal.get("end")
    if not isinstance(start, int) or not isinstance(end, int):
        return False
    text = clue.strip()
    if start < 0 or end <= start or end > len(text):
        return False
    # The private observer currently omits a copied text field.  When a future
    # producer includes one, keep it tied to the literal surface just like the
    # TypeScript validator does.
    supplied = signal.get("text")
    return supplied is None or supplied == text[start:end]


def validate_surface_clue_family(
    clue: Any,
    observation: Any,
) -> dict[str, Any]:
    """Validate an observed private family against visible clue punctuation.

    ``valid`` means only that the observation is internally consistent at the
    surface boundary.  ``semanticStatus`` intentionally remains
    ``not-established`` for both valid and invalid results.
    """

    issues: list[dict[str, str]] = []
    text = clue.strip() if isinstance(clue, str) else ""
    if not isinstance(observation, Mapping):
        issues.append(
            _issue("invalid-observation", "A family observation must be an object.")
        )
        family = None
        signals: list[Mapping[str, Any]] = []
    else:
        family = observation.get("family")
        signals = _signals(observation)
        if observation.get("confidence") != "surface-signal-only":
            issues.append(
                _issue(
                    "confidence-boundary",
                    "Private family observations must remain surface-signal-only.",
                    "confidence",
                )
            )
        uncertainty = observation.get("uncertainty")
        if (
            not isinstance(uncertainty, list)
            or "semantic-family-unverified" not in uncertainty
        ):
            issues.append(
                _issue(
                    "semantic-boundary",
                    "Family observations must retain semantic-family-unverified uncertainty.",
                    "uncertainty",
                )
            )

    if family not in _FAMILIES:
        issues.append(
            _issue(
                "unknown-family",
                "The private observer must use a family from clue-grammar-v1.",
                "family",
            )
        )
        family = None

    for index, signal in enumerate(signals):
        if not _signal_matches_literal(text, signal):
            issues.append(
                _issue(
                    "invalid-signal-span",
                    "Observed signal offsets must point into the literal clue surface.",
                    f"signals[{index}]",
                )
            )

    checked_rules: list[str] = []
    status = "surface-checked"
    if family in _REQUIRED_SURFACE_SIGNAL:
        required = _REQUIRED_SURFACE_SIGNAL[family]
        checked_rules.append(f"required-signal:{required}")
        if not any(signal.get("kind") == required for signal in signals):
            issues.append(
                _issue(
                    "missing-observed-signal",
                    f"The {family} observation is missing its {required} surface signal.",
                    "signals",
                )
            )
        if not _surface_signal_present(text, family, signals):
            issues.append(
                _issue(
                    "surface-family-mismatch",
                    f"The literal clue does not carry the visible signal for {family}.",
                    "clue",
                )
            )
    elif family in _NO_SURFACE_RULE:
        checked_rules.append("no-required-surface-signal")
        status = "surface-unconstrained"

    return {
        "version": CLUE_GRAMMAR_BRIDGE_VERSION,
        "houseGrammarVersion": HOUSE_GRAMMAR_VERSION,
        "status": status,
        "valid": not issues,
        "family": family,
        "checkedRules": checked_rules,
        "issues": issues,
        "semanticStatus": "not-established",
        "uncertainty": [
            "semantic-family-unverified",
            "semantic-meaning-unverified",
        ],
    }


def summarize_surface_clue_families(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize bridge outcomes while preserving individual diagnostics."""

    checks = [
        item.get("grammarBridge")
        for item in records
        if isinstance(item, Mapping) and isinstance(item.get("grammarBridge"), Mapping)
    ]
    valid_count = sum(item.get("valid") is True for item in checks)
    invalid_count = sum(item.get("valid") is False for item in checks)
    status_counts: dict[str, int] = {}
    issue_counts: dict[str, int] = {}
    for item in checks:
        status = item.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        for problem in item.get("issues", []):
            if isinstance(problem, Mapping) and isinstance(problem.get("code"), str):
                code = problem["code"]
                issue_counts[code] = issue_counts.get(code, 0) + 1
    return {
        "version": CLUE_GRAMMAR_BRIDGE_VERSION,
        "houseGrammarVersion": HOUSE_GRAMMAR_VERSION,
        "checkedCount": len(checks),
        "validCount": valid_count,
        "invalidCount": invalid_count,
        "statusCounts": status_counts,
        "issueCounts": issue_counts,
        "semanticStatus": "not-established",
        "uncertainty": [
            "semantic-family-unverified",
            "semantic-meaning-unverified",
        ],
    }
