"""Small, explicit signals used to identify language-learning clues.

Private clue generation is intentionally allowed to vary its surface wording.
This helper keeps the learning ledger and the solve-session linker in sync
without guessing a language from arbitrary clue text.  A clue must mention the
configured language in one of the few unambiguous forms below.
"""

import re


def has_explicit_language_signal(clue, language):
    """Return whether *clue* explicitly names *language* as a language cue.

    Supported forms include ``"hello, in German"``, ``"yes in German"``,
    ``"German for yes"``, and ``"German word for yes"``.  The language name
    is escaped so configured values cannot change the regular expression.
    """

    if not isinstance(clue, str) or not isinstance(language, str):
        return False
    normalized_language = language.strip()
    if not normalized_language:
        return False
    escaped = re.escape(normalized_language)
    patterns = (
        rf"\b(?:in|into)\s+{escaped}\b",
        rf"\b{escaped}\s+(?:for|word\s+for|translation\s+of|equivalent\s+of)\b",
    )
    return any(re.search(pattern, clue, re.IGNORECASE) for pattern in patterns)
