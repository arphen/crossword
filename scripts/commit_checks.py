"""Shared, read-only checks for pre-commit and GitHub CI.

pre-commit hides unstaged tracked edits before invoking this runner. No command
here stages files, changes thresholds, downloads tools, or applies automatic fixes.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
JS_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".json", ".yaml", ".yml"}
FAILURE = """
COMMIT BLOCKED — fix the reported cause, not the gate.
1. Read the FIRST failing command and its diagnostics above.
2. Fix the source/test/config; reproduce with that command. For formatting use
   node_modules/.bin/prettier --ignore-path /dev/null --write <file>
   or uv run --no-sync ruff format <file>, inspect the diff, then stage it.
3. Run make precommit again. Dependency errors: activate .node-version and the
   packageManager npm version, then make setup; update lockfiles deliberately.
DO NOT use --no-verify, SKIP, alternate core.hooksPath, or disable these checks.
DO NOT lower coverage/mutation thresholds, delete assertions, add skips or
suppressions just to turn this green. Hook/CI/lint/exception policy changes
require explicit human approval and a rationale in the PR.
If blocked by a tool/network/legacy issue: stop and report the exact command,
exit status and cause to the human. Never claim success from truncated output.
"""


def run(*command: str, env: dict[str, str] | None = None) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def changed_files(base: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "-z", base, "HEAD"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return [p for p in result.stdout.decode().split("\0") if p]


def format_files(files: list[str]) -> None:
    # Explicit filenames override the legacy Prettier allowlist: ALL touched
    # source/config files adopt formatting, without a repo-wide legacy rewrite.
    selected = [
        name
        for name in files
        if not name.startswith(
            (
                "vendor/",
                "reports/",
                "src/crossword/static/lib/",
                "src/crossword/static/react/",
            )
        )
        and name != "package-lock.json"
        and (ROOT / name).is_file()
        and not (ROOT / name).is_symlink()
    ]
    for name in selected:
        suffix = Path(name).suffix
        if suffix == ".py":
            # Pre-commit-scoped correctness rules; the full repo gate lives in CI.
            run(
                "uv",
                "run",
                "--no-sync",
                "ruff",
                "check",
                "--select",
                "E9,F63,F7,F82",
                "--",
                name,
            )
            # Scoped adoption: only the new pipeline scripts and isolated tests
            # are format-checked; legacy sources are not retro-formatted here.
            pipeline_files = {
                "scripts/commit_checks.py",
                "scripts/commit_policy.py",
                "scripts/install-hooks.py",
                "scripts/ci-server.py",
                "tests/test_api_isolated.py",
            }
            if name in pipeline_files:
                run("uv", "run", "--no-sync", "ruff", "format", "--check", "--", name)
        elif suffix in JS_SUFFIXES:
            run(
                "node_modules/.bin/prettier",
                "--ignore-path",
                "/dev/null",
                "--check",
                "--",
                name,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["policy", "format", "static", "tests", "ci"])
    parser.add_argument("files", nargs="*")
    parser.add_argument("--base", help="Trusted base commit for CI diff checks")
    args = parser.parse_args()
    try:
        if args.mode in ("policy", "ci"):
            command = ["uv", "run", "--no-sync", "python", "scripts/commit_policy.py"]
            if args.base:
                command += ["--base", args.base]
            run(*command)
        if args.mode in ("format", "ci"):
            if args.mode == "ci" and not args.base:
                parser.error("ci requires --base")
            format_files(changed_files(args.base) if args.base else args.files)
        if args.mode == "static":
            run("npm", "run", "typecheck")
            run("npm", "run", "lint")
            run("npm", "run", "format:check")
            run("uv", "run", "--no-sync", "ruff", "check", ".")
        if args.mode == "tests":
            env = {**os.environ, "CROSSWORD_ALLOW_LIVE_PROVIDER": "0"}
            run(
                "uv",
                "run",
                "--no-sync",
                "python",
                "-m",
                "pytest",
                "tests/",
                "-m",
                "not live_provider",
                env=env,
            )
            run("npm", "test", "--", "--runInBand", env=env)
            run(
                "node_modules/.bin/vitest",
                "run",
                "--config",
                "vitest.ci.config.mjs",
                env=env,
            )
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"\nFailed: {error}\n{FAILURE}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
