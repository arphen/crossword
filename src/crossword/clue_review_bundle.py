"""Create a bounded, answer-bearing local review bundle for private puzzles.

The playable private route remains fail-open and model-driven.  This module is
the separate handoff to an editor or another model: it binds the exact puzzle
manifest, visible clue, answer, deterministic grammar observations, and the
semantic uncertainty receipt into one immutable local artifact.  A bundle is
explicitly not a publication approval and never becomes a playable route.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from typing import Any

from .legacy_manifest import verify_integrity


CLUE_REVIEW_BUNDLE_VERSION = "private-clue-review-bundle-v1"
CLUE_REVIEW_BUNDLE_SCOPE = "local-answer-bearing-editorial-review"
MAX_REVIEW_ENTRIES = 500
MAX_REVIEW_TEXT = 4000


def canonical_review_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_review_json(value).encode("utf-8")
    ).hexdigest()


def _text(value: Any, path: str, *, max_length: int = MAX_REVIEW_TEXT) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    value = value.strip()
    if len(value) > max_length:
        raise ValueError(f"{path} exceeds the review bundle limit")
    return value


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be an object")
    return value


def _json_copy(value: Any) -> Any:
    try:
        return json.loads(canonical_review_json(value))
    except (TypeError, ValueError, RecursionError, UnicodeError) as error:
        raise ValueError("review bundle input is not canonical JSON") from error


def build_clue_review_bundle(response: Mapping[str, Any]) -> dict[str, Any]:
    """Project one generated response into a local answer-bearing review file.

    The exact manifest digest is checked before answers are copied.  Every
    manifest entry must have a visible clue and a matching grounding record;
    silently dropping a clue would make a review appear cleaner than the board.
    """

    root = _mapping(response, "response")
    manifest = _mapping(root.get("puzzleManifest"), "response.puzzleManifest")
    if not verify_integrity(manifest):
        raise ValueError("puzzle manifest failed its integrity check")
    provenance = _mapping(root.get("provenance"), "response.provenance")
    quality = _mapping(provenance.get("clueQuality"), "provenance.clueQuality")
    grounded = _mapping(
        quality.get("groundedClueBundle"),
        "provenance.clueQuality.groundedClueBundle",
    )
    grounded_entries = grounded.get("entries")
    if not isinstance(grounded_entries, list):
        raise ValueError("grounded clue bundle entries must be a list")
    grounded_by_id: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(grounded_entries):
        item = _mapping(item, f"groundedClueBundle.entries[{index}]")
        entry_id = _text(item.get("id"), f"groundedClueBundle.entries[{index}].id", max_length=80)
        if entry_id in grounded_by_id:
            raise ValueError(f"duplicate grounding entry id: {entry_id}")
        grounded_by_id[entry_id] = item

    manifest_entries = manifest.get("entries")
    if not isinstance(manifest_entries, list) or not manifest_entries:
        raise ValueError("puzzle manifest entries must be a non-empty list")
    if len(manifest_entries) > MAX_REVIEW_ENTRIES:
        raise ValueError("puzzle manifest has too many review entries")

    entries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(manifest_entries):
        item = _mapping(raw, f"puzzleManifest.entries[{index}]")
        entry_id = _text(item.get("id"), f"puzzleManifest.entries[{index}].id", max_length=80)
        if entry_id in seen_ids:
            raise ValueError(f"duplicate puzzle entry id: {entry_id}")
        seen_ids.add(entry_id)
        if entry_id not in grounded_by_id:
            raise ValueError(f"missing grounding record for {entry_id}")
        answer = _text(item.get("answer"), f"puzzleManifest.entries[{index}].answer", max_length=80)
        clue = _text(item.get("clue"), f"puzzleManifest.entries[{index}].clue")
        grounding = grounded_by_id[entry_id]
        grammar = _mapping(grounding.get("grammarBridge"), f"grounding[{entry_id}].grammarBridge")
        challenge = _mapping(
            grounding.get("semanticChallenge"),
            f"grounding[{entry_id}].semanticChallenge",
        )
        entries.append(
            {
                "id": entry_id,
                "number": item.get("number"),
                "direction": item.get("direction"),
                "answer": answer,
                "clue": clue,
                "grammar": _json_copy(grammar),
                "surfaceIssues": _json_copy(grounding.get("surfaceIssues", [])),
                "riskFlags": _json_copy(grounding.get("riskFlags", [])),
                "mechanicalIssue": grounding.get("mechanicalIssue"),
                "morphologyIssue": grounding.get("morphologyIssue"),
                "semanticChallenge": _json_copy(challenge),
                "semanticStatus": grounding.get("semanticStatus", "not-established"),
                "supportBand": grounding.get("supportBand", "unknown"),
                "review": {
                    "status": "unreviewed",
                    "semanticVerdict": None,
                    "grammarVerdict": None,
                    "notes": None,
                },
            }
        )
    if set(grounded_by_id) != seen_ids:
        missing = sorted(set(grounded_by_id) - seen_ids)
        raise ValueError(f"grounding contains entries absent from manifest: {missing}")

    body = {
        "schemaVersion": CLUE_REVIEW_BUNDLE_VERSION,
        "scope": CLUE_REVIEW_BUNDLE_SCOPE,
        "publishable": False,
        "answerDisclosure": "answers-and-clues",
        "manifestDigest": manifest["integrity"]["value"],
        "puzzle": {
            "id": manifest.get("id"),
            "title": manifest.get("title"),
            "width": manifest.get("width"),
            "height": manifest.get("height"),
            "weekday": provenance.get("weekday"),
            "seed": provenance.get("seed"),
            "model": provenance.get("model"),
        },
        "qualityReceipt": {
            "clueQuality": _json_copy(quality),
            "clueDiversity": _json_copy(provenance.get("clueDiversity", {})),
            "timingsSeconds": _json_copy(provenance.get("timingsSeconds", {})),
        },
        "entries": entries,
        "reviewPolicy": {
            "grammar": "Check answer leakage, clue markers, plurality, tense, and punctuation against clue-grammar-v1.",
            "semantics": "Verify the clue's intended sense or fact independently; deterministic receipts do not establish truth.",
            "difficulty": "Record whether the clue fits the requested weekday and gives a fair crossing path.",
            "publication": "A human/editorial decision is required before any admitted or published pack.",
        },
    }
    body["bundleDigest"] = _digest(body)
    return body


def verify_clue_review_bundle(bundle: Mapping[str, Any]) -> bool:
    """Check the immutable envelope without accepting any review verdict."""

    if not isinstance(bundle, Mapping) or bundle.get("schemaVersion") != CLUE_REVIEW_BUNDLE_VERSION:
        return False
    digest = bundle.get("bundleDigest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        return False
    body = {key: value for key, value in bundle.items() if key != "bundleDigest"}
    try:
        return digest == _digest(body)
    except (TypeError, ValueError, RecursionError, UnicodeError):
        return False
