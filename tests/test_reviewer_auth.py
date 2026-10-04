"""Local configured-reviewer authentication tests; no real secrets are used."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

import crossword.reviewer_auth as reviewer_auth
from crossword.reviewer_auth import (
    ReviewerAuthenticationError,
    ReviewerAuthConfigError,
    ReviewerPrincipal,
    resolve_reviewer_principal,
)


_TOKEN = "synthetic-test-reviewer-token-0123456789"
_CONFIG = {
    "CROSSWORD_REVIEWER_TOKEN": _TOKEN,
    "CROSSWORD_REVIEWER_ID": "local-editor-1",
}
_SECOND_TOKEN = "synthetic-test-blind-rater-token-abcdefgh"
_THIRD_TOKEN = "synthetic-test-second-blind-rater-abcdefgh"


def _roster(*reviewers: tuple[str, str]) -> str:
    return json.dumps(
        [
            {"reviewerId": reviewer_id, "token": token}
            for reviewer_id, token in reviewers
        ]
    )


@pytest.mark.parametrize(
    "config",
    [
        {},
        {"CROSSWORD_REVIEWER_ID": "local-editor-1"},
        {"CROSSWORD_REVIEWER_TOKEN": _TOKEN},
        {
            "CROSSWORD_REVIEWER_TOKEN": "short",
            "CROSSWORD_REVIEWER_ID": "local-editor-1",
        },
        {
            "CROSSWORD_REVIEWER_TOKEN": (
                "not a valid bearer credential with enough length"
            ),
            "CROSSWORD_REVIEWER_ID": "local-editor-1",
        },
        {"CROSSWORD_REVIEWER_TOKEN": _TOKEN, "CROSSWORD_REVIEWER_ID": ""},
        {"CROSSWORD_REVIEWER_TOKEN": _TOKEN, "CROSSWORD_REVIEWER_ID": " editor "},
        {"CROSSWORD_REVIEWER_TOKEN": _TOKEN, "CROSSWORD_REVIEWER_ID": "editor\nforged"},
        {"CROSSWORD_REVIEWER_TOKEN": _TOKEN, "CROSSWORD_REVIEWER_ID": "x" * 129},
    ],
)
def test_missing_weak_or_malformed_configuration_fails_closed(
    config: dict[str, Any],
) -> None:
    with pytest.raises(ReviewerAuthConfigError) as error:
        resolve_reviewer_principal(config, f"Bearer {_TOKEN}")

    assert error.value.code == "reviewer-auth-unavailable"
    assert _TOKEN not in str(error.value)


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        _TOKEN,
        "Basic " + _TOKEN,
        "Bearer",
        "Bearer ",
        "Bearer  " + _TOKEN,
        "Bearer " + _TOKEN + " ",
        "Bearer " + _TOKEN + "\n",
        "Bearer bad:token",
    ],
)
def test_absent_or_malformed_bearer_fails_closed(authorization: str | None) -> None:
    with pytest.raises(ReviewerAuthenticationError) as error:
        resolve_reviewer_principal(_CONFIG, authorization)

    assert error.value.code == "reviewer-auth-required"
    assert _TOKEN not in str(error.value)


def test_wrong_bearer_fails_without_disclosing_either_credential() -> None:
    wrong_token = "synthetic-test-reviewer-token-xxxxxxxxxx"

    with pytest.raises(ReviewerAuthenticationError) as error:
        resolve_reviewer_principal(_CONFIG, f"Bearer {wrong_token}")

    assert _TOKEN not in str(error.value)
    assert wrong_token not in str(error.value)


def test_bearer_maps_to_immutable_host_configured_principal() -> None:
    # Caller-controlled identity data is deliberately not an input to the
    # resolver, so a forged reviewerId cannot override the host config.
    caller_payload = {"reviewerId": "attacker-chosen-reviewer"}
    principal = resolve_reviewer_principal(_CONFIG, f"Bearer {_TOKEN}")

    assert caller_payload["reviewerId"] != principal.reviewer_id
    assert principal == ReviewerPrincipal(reviewer_id="local-editor-1")
    with pytest.raises(FrozenInstanceError):
        principal.reviewer_id = caller_payload["reviewerId"]  # type: ignore[misc]


def test_bearer_scheme_is_case_insensitive() -> None:
    principal = resolve_reviewer_principal(_CONFIG, f"bEaReR {_TOKEN}")

    assert principal.reviewer_id == "local-editor-1"


def test_additional_roster_authenticates_distinct_blind_raters() -> None:
    config = {
        **_CONFIG,
        "CROSSWORD_ADDITIONAL_REVIEWERS_JSON": _roster(
            ("blind-rater-a", _SECOND_TOKEN),
            ("blind-rater-b", _THIRD_TOKEN),
        ),
    }

    assert resolve_reviewer_principal(config, f"Bearer {_SECOND_TOKEN}") == (
        ReviewerPrincipal(reviewer_id="blind-rater-a")
    )
    assert resolve_reviewer_principal(config, f"Bearer {_THIRD_TOKEN}") == (
        ReviewerPrincipal(reviewer_id="blind-rater-b")
    )


def test_authentication_compares_every_configured_token_without_early_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = {
        **_CONFIG,
        "CROSSWORD_ADDITIONAL_REVIEWERS_JSON": _roster(
            ("blind-rater-a", _SECOND_TOKEN),
            ("blind-rater-b", _THIRD_TOKEN),
        ),
    }
    original_compare = reviewer_auth.hmac.compare_digest
    calls: list[tuple[bytes, bytes]] = []

    def record_compare(left: bytes, right: bytes) -> bool:
        calls.append((left, right))
        return original_compare(left, right)

    monkeypatch.setattr(reviewer_auth.hmac, "compare_digest", record_compare)
    principal = resolve_reviewer_principal(config, f"Bearer {_TOKEN}")

    assert principal.reviewer_id == "local-editor-1"
    # Three duplicate-token checks validate the roster; auth then compares
    # primary and both additional tokens, even though the first one matched.
    assert len(calls) == 6
    assert calls[-3:] == [
        (_TOKEN.encode("ascii"), _TOKEN.encode("ascii")),
        (_SECOND_TOKEN.encode("ascii"), _TOKEN.encode("ascii")),
        (_THIRD_TOKEN.encode("ascii"), _TOKEN.encode("ascii")),
    ]


@pytest.mark.parametrize(
    "roster",
    [
        "",
        "not-json",
        "{}",
        "null",
        '[{"reviewerId":"a","reviewerId":"b","token":"'
        + _SECOND_TOKEN
        + '"}]',
        json.dumps(
            [{"reviewerId": "blind-rater-a", "token": _SECOND_TOKEN, "extra": 1}]
        ),
        json.dumps([{"reviewerId": "blind-rater-a"}]),
        json.dumps([{"reviewerId": "blind-rater-a", "token": "short"}]),
        json.dumps([{"reviewerId": "", "token": _SECOND_TOKEN}]),
    ],
)
def test_malformed_additional_roster_fails_closed_without_secret_leakage(
    roster: str,
) -> None:
    config = {**_CONFIG, "CROSSWORD_ADDITIONAL_REVIEWERS_JSON": roster}

    with pytest.raises(ReviewerAuthConfigError) as error:
        resolve_reviewer_principal(config, f"Bearer {_TOKEN}")

    assert str(error.value) == "reviewer-auth-unavailable"
    assert _TOKEN not in str(error.value)
    assert _SECOND_TOKEN not in str(error.value)


@pytest.mark.parametrize(
    "roster",
    [
        _roster(("duplicate-id", _SECOND_TOKEN), ("duplicate-id", _THIRD_TOKEN)),
        _roster(("local-editor-1", _SECOND_TOKEN)),
    ],
)
def test_duplicate_reviewer_ids_fail_closed(roster: str) -> None:
    with pytest.raises(ReviewerAuthConfigError):
        resolve_reviewer_principal(
            {**_CONFIG, "CROSSWORD_ADDITIONAL_REVIEWERS_JSON": roster},
            f"Bearer {_TOKEN}",
        )


@pytest.mark.parametrize(
    "roster",
    [
        _roster(("blind-rater-a", _SECOND_TOKEN), ("blind-rater-b", _SECOND_TOKEN)),
        _roster(("blind-rater-a", _TOKEN)),
    ],
)
def test_duplicate_tokens_fail_closed(roster: str) -> None:
    with pytest.raises(ReviewerAuthConfigError) as error:
        resolve_reviewer_principal(
            {**_CONFIG, "CROSSWORD_ADDITIONAL_REVIEWERS_JSON": roster},
            f"Bearer {_TOKEN}",
        )

    assert _TOKEN not in str(error.value)
    assert _SECOND_TOKEN not in str(error.value)


def test_primary_reviewer_remains_required_when_roster_is_present() -> None:
    config = {
        "CROSSWORD_ADDITIONAL_REVIEWERS_JSON": _roster(
            ("blind-rater-a", _SECOND_TOKEN)
        )
    }

    with pytest.raises(ReviewerAuthConfigError):
        resolve_reviewer_principal(config, f"Bearer {_SECOND_TOKEN}")


def test_configured_primary_still_authenticates_without_an_additional_roster() -> None:
    principal = resolve_reviewer_principal(_CONFIG, f"Bearer {_TOKEN}")

    assert principal == ReviewerPrincipal(reviewer_id="local-editor-1")
