"""Delimited-draft prototype for gemma-editor lane.

Parses ``ID|ANSWER|clue`` lines without JSON or regex gates.
Dependency-free so Ollama/small-model harnesses can import it.
"""

from __future__ import annotations


def _parse_delimited_drafts(text, batch_ids):
    """Parse delimited drafts into (records, errors).

    records: [{"id": str, "text": str}]
    errors: [{"reason": str, "line": int}] with reason in
      malformed-draft / malformed-draft-id / malformed-draft-text.
    """
    allowed = set(batch_ids) if batch_ids else set()
    records: list = []
    errors: list = []
    if not isinstance(text, str):
        return records, [{"reason": "malformed-draft", "line": 0}]
    for n, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        parts = raw.split("|", 2)
        if len(parts) != 3:
            errors.append({"reason": "malformed-draft", "line": n})
            continue
        cid, _answer, clue = parts[0].strip(), parts[1], parts[2].strip()
        if cid not in allowed:
            errors.append({"reason": "malformed-draft-id", "line": n})
            continue
        if (
            not 2 <= len(clue) <= 180
            or "|" in clue
            or "{" in clue
            or "}" in clue
            or "\n" in clue
            or "\r" in clue
        ):
            errors.append({"reason": "malformed-draft-text", "line": n})
            continue
        records.append({"id": cid, "text": clue})
    return records, errors


GOOD = "\n".join(
    [
        "0A|ECHO|Sound that bounces back",
        "1A|MOSS|Soft green growth on rocks",
        "2A|DARK|Without light",
        "3A|SEATTLE|Pacific Northwest hub",
        "4A|BRAD|Actor Pitt, familiarly",
    ]
)
BATCH = ["0A", "1A", "2A", "3A", "4A"]


def _self_test():
    rec, err = _parse_delimited_drafts(GOOD, BATCH)
    print(f"good: records={len(rec)} errors={len(err)}")
    assert len(rec) == 5 and not err, (rec, err)
    cases = [
        ("no-pipes-here", "malformed-draft"),
        ("9Z|ECHO|Sound that bounces back", "malformed-draft-id"),
        ("0A|ECHO|X", "malformed-draft-text"),
    ]
    for i, (line, want) in enumerate(cases, start=1):
        r, e = _parse_delimited_drafts(line, BATCH)
        got = e[0]["reason"] if e else None
        print(f"neg{i}: records={len(r)} errors={len(e)} reason={got}")
        assert not r and got == want, (line, e)
    # Extra text-shape guards stay malformed-draft-text.
    for bad in ("0A|ECHO|pipe | here", "0A|ECHO|brace {here}"):
        _, e = _parse_delimited_drafts(bad, BATCH)
        assert e and e[0]["reason"] == "malformed-draft-text", bad
    print("self-test: ok")


if __name__ == "__main__":
    _self_test()
