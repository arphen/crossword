"""Deterministic candidate admission for clue selection (Q07).

Whole-board single-request clue JSON fails wholesale on small models: one
malformed clue poisons all seventy. The candidate path instead drafts k
short batches per entry with distinct seeds, admits them through the same
deterministic guards that score single drafts (leak, morphology,
information, risk), rejects near-duplicates, and lets one comparison call
pick among the survivors. Rejected drafts stay in the receipt.

Admission rejects deterministic failures and duplicates only. Witness and
genre status steer survivor selection; they are measurement, not gates, so a
plain definition is always admissible. Everything here is pure and offline;
model calls live in ``private_puzzle_generation._make_candidate_clues``.
"""

from __future__ import annotations

import re

CANDIDATE_VERSION = "private-clue-candidate-admission-v1"
CANDIDATE_DRAFT_ROUNDS = 4
CANDIDATE_BATCH_SIZE = 24
CANDIDATE_DRAFT_TOKENS_PER_ENTRY = 60
CANDIDATE_DRAFT_TEMPERATURE = 0.7
CANDIDATE_COMPARE_TOKENS = 200
CANDIDATE_COMPARE_TEMPERATURE = 0.2
CANDIDATE_REDRAFT_ROUNDS = 1
DUPLICATE_OVERLAP_THRESHOLD = 0.8
COMPARISON_SURVIVOR_LIMIT = 3


def _tokens(text: str) -> set:
    return set(re.findall(r"[A-Z]{2,}", str(text).upper()))


def token_overlap(first: str, second: str) -> float:
    """Jaccard overlap over letter tokens; 1.0 means the same word bag."""
    left, right = _tokens(first), _tokens(second)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def shape_admit(raw) -> dict:
    """Strictly validate one draft's shape; malformed drafts die here alone."""
    if not isinstance(raw, dict):
        return {"admitted": False, "reason": "malformed-draft"}
    clue_id, text = raw.get("id"), raw.get("text")
    if not isinstance(clue_id, str) or not clue_id:
        return {"admitted": False, "reason": "malformed-draft-id"}
    if not isinstance(text, str) or not 2 <= len(text.strip()) <= 180 or "\n" in text:
        return {"admitted": False, "reason": "malformed-draft-text"}
    return {"admitted": True, "id": clue_id, "text": text.strip()}


def admit_candidate(text, *, issue_codes, witnessed_family, admitted_texts) -> dict:
    """Admit one well-formed draft: no deterministic issue, no duplicate.

    ``issue_codes`` are the caller's deterministic findings (leak,
    morphology, information, risk). ``witnessed_family`` is recorded for
    survivor selection, never used to reject. Near-duplicates of an already
    admitted draft for the same entry are rejected so k drafts cannot all be
    one draft.
    """
    issues = [code for code in (issue_codes or []) if isinstance(code, str) and code]
    if issues:
        return {"admitted": False, "reasons": sorted(set(issues))}
    for prior in admitted_texts or []:
        if token_overlap(text, prior) >= DUPLICATE_OVERLAP_THRESHOLD:
            return {"admitted": False, "reasons": ["duplicate-draft"]}
    return {"admitted": True, "reasons": [], "witnessedFamily": witnessed_family}


def select_survivors(candidates, limit=COMPARISON_SURVIVOR_LIMIT) -> list:
    """Order admitted drafts for comparison: witnessed first, then earliest."""
    admitted = [c for c in (candidates or []) if c.get("admitted") is True]
    witnessed = [c for c in admitted if (c.get("witnessedFamily") or "definition") != "definition"]
    plain = [c for c in admitted if (c.get("witnessedFamily") or "definition") == "definition"]
    return (witnessed + plain)[: max(1, limit)]


def comparison_payload(answer, length, survivors) -> dict:
    """Build the answer-aware comparison request over surviving drafts."""
    return {
        "answer": answer,
        "length": length,
        "candidates": [
            {"id": candidate["draftId"], "text": candidate["text"]} for candidate in survivors
        ],
        "instruction": (
            "Pick the best crossword clue for the answer. Reply JSON "
            "{pick: <id>, difference: <one sentence naming what distinguishes it>}."
        ),
    }


def validate_comparison_response(value, survivor_ids) -> dict:
    """Validate the comparison pick; an invalid pick falls back explicitly."""
    ids = [sid for sid in (survivor_ids or []) if isinstance(sid, str)]
    if not isinstance(value, dict):
        return {"pick": None, "difference": None, "valid": False, "reason": "comparison-unparseable"}
    pick, difference = value.get("pick"), value.get("difference")
    if pick not in ids:
        return {"pick": None, "difference": None, "valid": False, "reason": "comparison-pick-invalid"}
    if not isinstance(difference, str) or not difference.strip():
        return {"pick": None, "difference": None, "valid": False, "reason": "comparison-difference-missing"}
    return {"pick": pick, "difference": difference.strip(), "valid": True, "reason": None}


def score_surface_set(diagnostics) -> dict:
    """Score clue surfaces on deterministic rules only, for A/B comparison.

    ``diagnostics`` is a list of ``{answer, clue, issues, witnessedFamily,
    genre}`` records. No model, no preference corpus: leak rate, witnessed
    rate, genre mix, and grammar-clean share. Semantic fairness and player
    quality are explicitly out of scope.
    """
    total = 0
    leak = 0
    grammar_issues = 0
    witnessed_non_definition = 0
    pseudo_pun = 0
    genres: dict = {}
    for item in diagnostics or []:
        if not isinstance(item, dict):
            continue
        total += 1
        issues = [c for c in (item.get("issues") or []) if isinstance(c, str)]
        if any("answer" in code or "tautological" in code or "giveaway" in code for code in issues):
            leak += 1
        if issues:
            grammar_issues += 1
        family = item.get("witnessedFamily") or "definition"
        if family == "pseudo-pun":
            pseudo_pun += 1
        elif family != "definition":
            witnessed_non_definition += 1
        genre = item.get("genre") or "plain-definition"
        genres[genre] = genres.get(genre, 0) + 1
    return {
        "surfaces": total,
        "leakCount": leak,
        "leakRate": round(leak / total, 4) if total else 0.0,
        "grammarIssueCount": grammar_issues,
        "grammarCleanRate": round((total - grammar_issues) / total, 4) if total else 0.0,
        "witnessedNonDefinitionCount": witnessed_non_definition,
        "witnessedNonDefinitionRate": round(witnessed_non_definition / total, 4) if total else 0.0,
        "pseudoPunCount": pseudo_pun,
        "genreCounts": dict(sorted(genres.items())),
    }
