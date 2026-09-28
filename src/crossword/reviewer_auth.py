"""Local-first authentication boundary for configured crossword reviewers.

The host may configure one required primary reviewer and an optional strict
JSON roster of additional blind raters. This is suitable for a trusted local
installation; a public deployment still needs account authentication,
credential rotation, and a broader authorization model.
"""

from __future__ import annotations

import hmac
import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


_MIN_TOKEN_LENGTH = 32
_MAX_TOKEN_LENGTH = 512
_MAX_REVIEWER_ID_LENGTH = 128
_MAX_ADDITIONAL_REVIEWERS = 128
_MAX_ROSTER_JSON_LENGTH = 64 * 1024
# RFC 6750's b64token character set. Enforcing it for configured and presented
# credentials keeps comparison behavior unambiguous and ASCII-only.
_BEARER_TOKEN = re.compile(r"[A-Za-z0-9\-._~+/]+=*")


class ReviewerAuthConfigError(RuntimeError):
    """The host has no usable reviewer credential configuration."""

    code = "reviewer-auth-unavailable"

    def __init__(self) -> None:
        # Never include a secret or its source value in the exception text.
        super().__init__(self.code)


class ReviewerAuthenticationError(RuntimeError):
    """The supplied Authorization header does not authenticate a reviewer."""

    code = "reviewer-auth-required"

    def __init__(self) -> None:
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class ReviewerPrincipal:
    """Immutable identity resolved from a host-configured credential."""

    reviewer_id: str


def _valid_reviewer_id(value: Any) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > _MAX_REVIEWER_ID_LENGTH
        or value != value.strip()
    ):
        return False
    return not any(
        unicodedata.category(character) in {"Cc", "Cf", "Cs"}
        for character in value
    )


def _valid_token(value: Any) -> bool:
    return (
        isinstance(value, str)
        and _MIN_TOKEN_LENGTH <= len(value) <= _MAX_TOKEN_LENGTH
        and _BEARER_TOKEN.fullmatch(value) is not None
    )


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _parse_additional_reviewers(value: Any) -> list[tuple[str, str]]:
    # An unset environment variable means no extra reviewers. An explicitly
    # configured empty string is malformed and therefore disables auth.
    if value is None:
        return []
    if not isinstance(value, str) or len(value) > _MAX_ROSTER_JSON_LENGTH:
        raise ReviewerAuthConfigError

    try:
        roster = json.loads(value, object_pairs_hook=_reject_duplicate_json_keys)
    except (TypeError, ValueError, RecursionError):
        raise ReviewerAuthConfigError from None

    if not isinstance(roster, list) or len(roster) > _MAX_ADDITIONAL_REVIEWERS:
        raise ReviewerAuthConfigError

    credentials: list[tuple[str, str]] = []
    reviewer_ids: set[str] = set()
    for item in roster:
        if (
            not isinstance(item, dict)
            or set(item) != {"reviewerId", "token"}
            or not _valid_reviewer_id(item.get("reviewerId"))
            or not _valid_token(item.get("token"))
        ):
            raise ReviewerAuthConfigError

        reviewer_id = item["reviewerId"]
        token = item["token"]
        if reviewer_id in reviewer_ids:
            raise ReviewerAuthConfigError
        reviewer_ids.add(reviewer_id)

        # Check every prior token without using ordinary string equality for
        # secret material. Invalid duplicate rosters fail closed.
        duplicate_token = False
        candidate = token.encode("ascii")
        for _, previous in credentials:
            duplicate_token = hmac.compare_digest(
                candidate, previous.encode("ascii")
            ) or duplicate_token
        if duplicate_token:
            raise ReviewerAuthConfigError
        credentials.append((reviewer_id, token))
    return credentials


def _configured_credentials(config: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    if not isinstance(config, Mapping):
        raise ReviewerAuthConfigError

    primary_token = config.get("CROSSWORD_REVIEWER_TOKEN")
    primary_id = config.get("CROSSWORD_REVIEWER_ID")
    if not _valid_token(primary_token) or not _valid_reviewer_id(primary_id):
        raise ReviewerAuthConfigError

    additional = _parse_additional_reviewers(
        config.get("CROSSWORD_ADDITIONAL_REVIEWERS_JSON")
    )
    credentials = [(primary_id, primary_token), *additional]

    reviewer_ids: set[str] = set()
    for reviewer_id, _ in credentials:
        if reviewer_id in reviewer_ids:
            raise ReviewerAuthConfigError
        reviewer_ids.add(reviewer_id)

    # The primary credential participates in duplicate detection too.
    primary_bytes = primary_token.encode("ascii")
    duplicate_token = False
    for _, additional_token in additional:
        duplicate_token = hmac.compare_digest(
            primary_bytes, additional_token.encode("ascii")
        ) or duplicate_token
    if duplicate_token:
        raise ReviewerAuthConfigError

    return tuple(credentials)


def resolve_reviewer_principal(
    config: Mapping[str, Any], authorization_header: str | None
) -> ReviewerPrincipal:
    """Resolve identity from trusted host config and the HTTP auth header.

    Request JSON, query parameters, profile IDs, and other caller-controlled
    identity fields do not participate in this mapping. All configured tokens
    are compared before a principal is returned, so roster order does not
    short-circuit successful authentication.
    """

    credentials = _configured_credentials(config)
    if not isinstance(authorization_header, str):
        raise ReviewerAuthenticationError

    # A single ASCII space and a valid b64token are required. Scheme matching
    # is case-insensitive as specified by HTTP authentication syntax.
    scheme, separator, supplied_token = authorization_header.partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not _valid_token(supplied_token)
    ):
        raise ReviewerAuthenticationError

    supplied = supplied_token.encode("ascii")
    match: str | None = None
    for reviewer_id, configured_token in credentials:
        is_match = hmac.compare_digest(
            configured_token.encode("ascii"), supplied
        )
        if is_match:
            match = reviewer_id
    if match is None:
        raise ReviewerAuthenticationError
    return ReviewerPrincipal(reviewer_id=match)
