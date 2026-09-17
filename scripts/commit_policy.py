"""Heuristic commit hygiene, not a security boundary or a semantic policy auditor.

By default inspect HEAD -> index, never working-tree content. CI may pass --base
SHA to inspect base...HEAD, reading the merge-base and HEAD blobs. Only added
lines are checked; deletions and unchanged historical debt are allowed. Changed
blobs over 1 MiB and generated outputs are rejected regardless of their contents.
There is no exemption mechanism (including for changed vendor archives).

The small source lexer recognizes ordinary strings and comments, not complete
Python/JS/TS grammars. Aliases, computed properties, template interpolation and
obfuscated credentials can evade these checks. Enforcement changes always need
human review: this script cannot prove that configuration retains its meaning.
"""

from __future__ import annotations

import argparse
import difflib
import os
from pathlib import PurePosixPath
import re
import subprocess
import sys


MAX_BLOB_BYTES = 1024 * 1024
SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts", ".py"}
GENERATED_DIRS = {
    "node_modules",
    ".venv",
    "reports",
    "coverage",
    "playwright-report",
    "test-results",
}
GENERATED_PREFIXES = ("src/crossword/static/lib/", "src/crossword/static/react/")
DATABASE = re.compile(r"\.(?:db|sqlite|sqlite3)(?:-(?:wal|shm|journal))?$", re.I)
CONFLICT = re.compile(r"^(?:<{7,}(?: .*)?|>{7,}(?: .*)?|\|{7,}(?: .*)?|={7,})\s*$")
SECRETS = (
    re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,255}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
)
JS_FOCUS = re.compile(
    r"\b(?:test|it|describe|suite|context|specify)"
    r"(?:\s*\.\s*[A-Za-z_$][\w$]*)*\s*\.\s*(?:only|skip|todo)\b"
    r"|\b(?:xit|xdescribe|fit|fdescribe)\s*(?=\(|\.)"
)
PY_FOCUS = re.compile(
    r"\bpytest\s*\.\s*(?:mark\s*\.\s*skip(?:if)?|skip)\b"
    r"|\bunittest\s*\.\s*skip(?:If|Unless)?\b"
)
SUPPRESSION = re.compile(
    r"^\s*(?://|/\*+|\*|#)\s*(?:"
    r"@ts-(?:ignore|nocheck)\b|eslint-disable(?:-next-line|-line)?\b|"
    r"prettier-ignore\b|noqa\b|type:\s*ignore\b|"
    r"(?:istanbul|v8)\s+ignore\b|pragma:\s*no\s+cover\b)",
    re.I,
)
# Preserve line positions while removing literal and comment contents from code.
# Keeping comments separately lets directives be checked without matching strings
# in this guard or fixture definitions. This is intentionally a lexer heuristic.
STRINGS = (
    r"(?P<string>'''[\s\S]*?(?:'''|\Z)|\"\"\"[\s\S]*?(?:\"\"\"|\Z)|"
    r"'(?:\\[\s\S]|[^'\\\r\n])*'|\"(?:\\[\s\S]|[^\"\\\r\n])*\"|"
    r"`(?:\\[\s\S]|[^`\\])*`)"
)
PY_TOKENS = re.compile(STRINGS + r"|(?P<comment>\#[^\r\n]*)")
JS_TOKENS = re.compile(STRINGS + r"|(?P<comment>//[^\r\n]*|/\*[\s\S]*?(?:\*/|\Z))")


class PolicyError(Exception):
    """A snapshot could not be safely inspected."""


def git(*args: str, cwd: str | None = None) -> bytes:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=False)
    if result.returncode:
        # Git diagnostics can contain sensitive filenames or blob contents.
        raise PolicyError(
            "Git could not read the requested snapshot; check the repository, "
            "base commit availability, and unresolved index entries."
        )
    return result.stdout


def display_path(path: str) -> str:
    for pattern in SECRETS:
        path = pattern.sub("[REDACTED]", path)
    return repr(path)  # Escape newlines and terminal controls in Git filenames.


def changed_paths(raw: bytes) -> list[tuple[str, str]]:
    """Parse --name-status -z with --no-renames: status NUL path NUL."""
    fields = raw.split(b"\0")
    if fields[-1] != b"" or (len(fields) - 1) % 2:
        raise PolicyError("Git returned an unexpected changed-path record.")
    changes = []
    for index in range(0, len(fields) - 1, 2):
        status = fields[index].decode("ascii")
        if status not in {"A", "M", "D", "T"}:
            raise PolicyError(
                "Resolve unmerged or unsupported index entries before committing."
            )
        changes.append((status, os.fsdecode(fields[index + 1])))
    return changes


def snapshot(base: str | None) -> tuple[str, str | None, str, list[tuple[str, str]]]:
    root = os.fsdecode(git("rev-parse", "--show-toplevel")).rstrip("\n")
    if base is not None:
        if not re.fullmatch(r"[0-9a-fA-F]{4,64}", base):
            raise PolicyError("--base must be a commit SHA, not a ref or an option.")
        old = (
            git("rev-parse", "--verify", f"{base}^{{commit}}", cwd=root)
            .decode()
            .strip()
        )
        new = git("rev-parse", "--verify", "HEAD^{commit}", cwd=root).decode().strip()
        ancestor = git("merge-base", old, new, cwd=root).decode().strip()
        raw = git(
            "diff",
            "--no-ext-diff",
            "--no-renames",
            "--name-status",
            "-z",
            f"{old}...{new}",
            "--",
            cwd=root,
        )
        return root, ancestor, new, changed_paths(raw)

    head = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "HEAD"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if head.returncode not in {0, 1}:
        raise PolicyError("Git could not resolve HEAD.")
    old = head.stdout.decode().strip() if head.returncode == 0 else None
    # Capture an immutable index tree so an edit or restage during scanning cannot
    # mix snapshots. write-tree also fails closed for unresolved conflicts.
    new = git("write-tree", cwd=root).decode().strip()
    if old is not None:
        raw = git(
            "diff",
            "--no-ext-diff",
            "--no-renames",
            "--name-status",
            "-z",
            old,
            new,
            "--",
            cwd=root,
        )
    else:
        # All paths of the captured tree are additions on an unborn branch.
        raw = b"".join(
            b"A\0" + path + b"\0"
            for path in git("ls-tree", "-r", "--name-only", "-z", new, cwd=root).split(
                b"\0"
            )
            if path
        )
    return root, old, new, changed_paths(raw)


def blob(root: str, revision: str, path: str) -> bytes:
    return git("show", "--no-ext-diff", "--no-textconv", f"{revision}:{path}", cwd=root)


def added_line_numbers(old: str, new: str) -> set[int]:
    matcher = difflib.SequenceMatcher(
        None, old.splitlines(), new.splitlines(), autojunk=False
    )
    return {
        number + 1
        for tag, _, _, start, end in matcher.get_opcodes()
        if tag in {"insert", "replace"}
        for number in range(start, end)
    }


def blank(text: str) -> str:
    return re.sub(r"[^\r\n]", " ", text)


def source_views(text: str, python: bool) -> tuple[str, str]:
    tokens = PY_TOKENS if python else JS_TOKENS
    comments = []
    cursor = 0
    for match in tokens.finditer(text):
        comments.append(blank(text[cursor : match.start()]))
        comments.append(
            match.group() if match.lastgroup == "comment" else blank(match.group())
        )
        cursor = match.end()
    comments.append(blank(text[cursor:]))
    return tokens.sub(lambda match: blank(match.group()), text), "".join(comments)


def generated(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return (
        bool(set(parts[:-1]) & GENERATED_DIRS)
        or path.startswith(GENERATED_PREFIXES)
        or bool(DATABASE.search(path))
    )


def enforcement_file(path: str) -> bool:
    name = PurePosixPath(path).name
    return (
        path.startswith((".github/workflows/", ".githooks/", "scripts/"))
        or path == "tests/test_commit_policy.py"
        or name
        in {
            "Makefile",
            "pyproject.toml",
            "package.json",
            ".gitignore",
            ".prettierignore",
            ".prettierrc",
            ".prettierrc.json",
            ".eslintignore",
            ".pre-commit-config.yaml",
        }
        or ".config." in name
        or name.startswith(("tsconfig", ".eslintrc", ".prettierrc"))
    )


def check_file(path: str, old_bytes: bytes, new_bytes: bytes) -> list[str]:
    location = display_path(path)
    issues = []
    if generated(path):
        issues.append(
            f"{location}: generated output/database must not be committed; remove it from the index"
        )
    if len(new_bytes) > MAX_BLOB_BYTES:
        issues.append(
            f"{location}: changed blob exceeds 1 MiB; keep generated/bulk data outside Git"
        )
        return issues
    old, new = (
        data.decode("utf-8", errors="replace") for data in (old_bytes, new_bytes)
    )
    added = added_line_numbers(old, new)
    lines = new.splitlines()
    for number in sorted(added):
        line = lines[number - 1]
        if CONFLICT.fullmatch(line):
            issues.append(
                f"{location}:{number}: unresolved conflict marker; resolve the merge"
            )
        if any(pattern.search(line) for pattern in SECRETS):
            issues.append(
                f"{location}:{number}: possible credential/private key [REDACTED]; "
                "remove it and revoke/rotate it if exposed"
            )
    suffix = PurePosixPath(path).suffix.lower()
    if suffix not in SOURCE_SUFFIXES:
        return issues
    code, comments = source_views(new, python=suffix == ".py")
    focus = PY_FOCUS if suffix == ".py" else JS_FOCUS
    # Match the full code view to support ordinary whitespace/line breaks, but
    # report only when the actual focus/skip expression touches added lines.
    for match in focus.finditer(code):
        start = code.count("\n", 0, match.start()) + 1
        end = start + match.group().count("\n")
        changed = sorted(added.intersection(range(start, end + 1)))
        if changed:
            issues.append(
                f"{location}:{changed[0]}: focused/skipped test; restore normal test execution"
            )
    for number, line in enumerate(comments.splitlines(), 1):
        if number in added and SUPPRESSION.search(line):
            issues.append(
                f"{location}:{number}: new suppression directive; fix the underlying issue"
            )
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base", metavar="SHA", help="check base...HEAD using committed files (CI)"
    )
    args = parser.parse_args(argv)
    try:
        root, old, new, changes = snapshot(args.base)
        issues = []
        for status, path in changes:
            if enforcement_file(path):
                print(
                    f"REVIEW {display_path(path)}: enforcement/configuration changed; human review "
                    "must confirm checks and thresholds were not weakened."
                )
            if status == "D":
                continue
            previous = b"" if status == "A" or old is None else blob(root, old, path)
            issues.extend(check_file(path, previous, blob(root, new, path)))
    except (PolicyError, OSError, UnicodeError) as error:
        # Do not surface subprocess output, filenames, or exception reprs.
        detail = (
            str(error)
            if isinstance(error, PolicyError)
            else "Unable to read the Git snapshot."
        )
        print(f"Commit policy BLOCKED: {detail}", file=sys.stderr)
        print(
            "Resolve the blocker, stage the fixes, and rerun make precommit. "
            "Report blockers; do not bypass checks, add suppressions, or lower thresholds.",
            file=sys.stderr,
        )
        return 1
    if issues:
        print("Commit policy failed:", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        print(
            "Fix the findings, stage the fixes, and rerun make precommit. "
            "Report blockers; do not bypass checks, add suppressions, or lower thresholds.",
            file=sys.stderr,
        )
        return 1
    print(
        f"Commit policy passed ({len(changes)} changed paths; "
        f"{'base...HEAD' if args.base else 'staged snapshot'}). "
        "Heuristic checks are not a security boundary."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
