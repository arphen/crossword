"""A bounded semantic challenge projection for private clue surfaces.

Private Ollama clues do not have a reviewed sense or fact ledger.  The local
host can still separate a clue that is already a safe crossing scaffold, one
with a narrow mechanical witness, and one that needs a human or source-bound
review.  This module records that distinction without attempting to decide
whether an ordinary definition is true.

The projection is deliberately diagnostic.  It never gates private play and
``semanticStatus`` stays ``not-established`` for every classification.  An
optional local-model recommendation may be attached when an existing caller
already has one, but it cannot promote a clue or override deterministic
fallback safety.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


CLUE_SEMANTIC_CHALLENGER_VERSION = "private-clue-semantic-challenger-v1"

CLASSIFICATIONS = frozenset({"safe-fallback", "needs-review", "mechanically-supported"})

_SAFE_MECHANICAL_ISSUES = frozenset(
    {
        "answer-giveaway",
        "anagram-mismatch",
        "reversal-mismatch",
        "hidden-word-mismatch",
        "language-answer-mismatch",
    }
)
_MODEL_DISPOSITIONS = frozenset({"keep", "fallback", "review"})
_MODEL_CONFIDENCE = frozenset({"low", "medium", "high"})


def _codes(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _mechanical_statuses(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    validators = value.get("validators")
    if not isinstance(validators, Mapping):
        return []
    return [
        item.get("status")
        for item in validators.values()
        if isinstance(item, Mapping) and isinstance(item.get("status"), str)
    ]


def _model_projection(value: Any) -> dict[str, Any]:
    """Keep an already-produced local critique bounded and answer-free.

    This function deliberately accepts a small recommendation envelope rather
    than invoking a model.  Existing repair/model callers can pass a response
    for provenance, while malformed or overlong content is ignored.  Model
    language is never treated as semantic evidence.
    """

    base = {
        "status": "not-provided",
        "semanticStatus": "not-established",
        "uncertainty": ["model-judgment-unverified"],
    }
    if value is None:
        return base
    if not isinstance(value, Mapping):
        return {
            **base,
            "status": "ignored-invalid",
            "reason": "response-must-be-an-object",
        }
    disposition = value.get("disposition")
    confidence = value.get("confidence")
    reason = value.get("reason")
    if (
        disposition not in _MODEL_DISPOSITIONS
        or confidence not in _MODEL_CONFIDENCE
        or not isinstance(reason, str)
        or not 1 <= len(reason.strip()) <= 240
    ):
        return {
            **base,
            "status": "ignored-invalid",
            "reason": "response-shape-unaccepted",
        }
    result = {
        **base,
        "status": "accepted-advisory",
        "disposition": disposition,
        "confidence": confidence,
        "reason": reason.strip(),
        "source": value.get("source", "local-model")
        if isinstance(value.get("source", "local-model"), str)
        else "local-model",
    }
    return result


def challenge_private_clue_pair(
    entry: Any,
    clue: Any,
    *,
    mechanical_issue: Any = None,
    risk_flags: Any = None,
    surface_issues: Any = None,
    witness_validators: Any = None,
    grammar_bridge: Any = None,
    fallback_used: Any = None,
    model_response: Any = None,
) -> dict[str, Any]:
    """Classify one private clue/answer pair using bounded local signals.

    ``mechanically-supported`` means that a narrow validator passed (for
    example, the clue's anagram letters match the supplied answer).  It does
    not mean that the clue is semantically fair.  ``safe-fallback`` means the
    visible clue is already answer-free or has a deterministic failure that
    should use the crossing scaffold.  Everything else is ``needs-review``.
    """

    entry_map = entry if isinstance(entry, Mapping) else {}
    clue_text = clue.strip() if isinstance(clue, str) else ""
    issues = _codes(surface_issues)
    flags = _codes(risk_flags)
    mechanical_statuses = _mechanical_statuses(witness_validators)
    mechanical_issue_code = (
        mechanical_issue if isinstance(mechanical_issue, str) else None
    )
    is_fallback = bool(fallback_used)
    if fallback_used is None:
        is_fallback = clue_text.startswith("Entry supported by its crossings")

    reasons: list[str] = []
    classification = "needs-review"
    basis: list[str] = ["semantic-meaning-unverified"]

    if not clue_text or not isinstance(entry_map.get("answer"), str):
        classification = "safe-fallback"
        reasons.append("missing-clue-or-answer")
        basis.append("invalid-pair")
    elif is_fallback:
        classification = "safe-fallback"
        reasons.append("answer-free-crossing-scaffold")
        basis.append("answer-free-fallback")
    elif mechanical_issue_code in _SAFE_MECHANICAL_ISSUES:
        classification = "safe-fallback"
        reasons.append(f"mechanical-check-failed:{mechanical_issue_code}")
        basis.append("deterministic-mechanical-failure")
    elif "failed" in mechanical_statuses:
        classification = "safe-fallback"
        reasons.append("witness-validator-failed")
        basis.append("deterministic-witness-failure")
    elif "passed" in mechanical_statuses and not issues:
        bridge_valid = (
            not isinstance(grammar_bridge, Mapping)
            or grammar_bridge.get("valid", True) is True
        )
        if bridge_valid:
            classification = "mechanically-supported"
            reasons.append("witness-validator-passed")
            basis.append("narrow-mechanical-witness")
        else:
            reasons.append("clue-surface-bridge-invalid")
    else:
        if flags:
            reasons.extend(f"risk:{flag}" for flag in flags)
        if issues:
            reasons.extend(f"surface:{issue}" for issue in issues)
        if not reasons:
            reasons.append("no-reviewed-semantic-witness")
        basis.append("no-semantic-ledger")

    model = _model_projection(model_response)
    if model["status"] == "accepted-advisory":
        basis.append("advisory-model-recommendation")

    return {
        "version": CLUE_SEMANTIC_CHALLENGER_VERSION,
        "classification": classification,
        "status": "diagnostic",
        "reasons": reasons,
        "basis": basis,
        "mechanicalIssue": mechanical_issue_code,
        "mechanicalStatuses": mechanical_statuses,
        "riskFlags": flags,
        "surfaceIssues": issues,
        "modelRecommendation": model,
        "semanticStatus": "not-established",
        "truth": "not-established",
        "uncertainty": [
            "semantic-sense-unverified",
            "factual-support-unverified",
            "player-support-unmeasured",
        ],
        "playPolicy": "never-gates-private-play",
    }


def summarize_challenge_classifications(
    records: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Return stable counts for the private clue-quality report."""

    counts = {classification: 0 for classification in sorted(CLASSIFICATIONS)}
    checked = 0
    for record in records or []:
        if not isinstance(record, Mapping):
            continue
        classification = record.get("classification")
        if classification in counts:
            counts[classification] += 1
            checked += 1
    return {
        "version": CLUE_SEMANTIC_CHALLENGER_VERSION,
        "checkedCount": checked,
        "classificationCounts": counts,
        "semanticStatus": "not-established",
        "uncertainty": ["semantic-sense-unverified", "factual-support-unverified"],
        "playPolicy": "never-gates-private-play",
    }
