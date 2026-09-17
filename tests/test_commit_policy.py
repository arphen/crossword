"""Exercise the real CLI against disposable Git indexes, not working trees."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


GUARD = Path(__file__).resolve().parents[1] / "scripts" / "commit_policy.py"


def git(repo, *args):
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True)
    return result.stdout.decode().strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "policy@example.invalid")
    git(tmp_path, "config", "user.name", "Policy Test")
    git(tmp_path, "config", "commit.gpgsign", "false")
    git(tmp_path, "config", "core.hooksPath", str(tmp_path / "no-hooks"))
    git(tmp_path, "commit", "--allow-empty", "-qm", "baseline")
    return tmp_path


def stage(repo, path, content):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content if isinstance(content, bytes) else content.encode())
    git(repo, "add", "-f", "--", path)
    return target


def run(repo, *args):
    return subprocess.run([sys.executable, str(GUARD), *args], cwd=repo,
                          text=True, capture_output=True, check=False)


def assert_failed(result, message):
    assert result.returncode == 1, result.stdout + result.stderr
    assert message in result.stderr
    assert "stage the fixes" in result.stderr
    assert "make precommit" in result.stderr


def js_focus(modifier="only", runner="test"):
    return runner + "." + modifier + "('case', () => {});\n"


def test_index_not_worktree_in_both_directions(repo):
    target = stage(repo, "example.ts", js_focus())
    target.write_text("test('case', () => {});\n")
    assert_failed(run(repo), "focused/skipped test")
    git(repo, "add", "example.ts")
    target.write_text(js_focus())
    assert run(repo).returncode == 0


def test_unchanged_historical_debt_allowed(repo):
    debt = js_focus() + "// " + "eslint-" + "disable\n"
    stage(repo, "existing.js", debt)
    stage(repo, "old.txt", "ghp_" + "A" * 36 + "\n")
    git(repo, "commit", "-qm", "historical debt")
    stage(repo, "existing.js", debt + "const newValue = 42;\n")
    stage(repo, "old.txt", "ghp_" + "A" * 36 + "\nsafe addition\n")
    assert run(repo).returncode == 0


@pytest.mark.parametrize("runner", ["test", "it", "describe", "suite", "context", "specify"])
@pytest.mark.parametrize("modifier", ["only", "skip", "todo"])
@pytest.mark.parametrize("suffix", ["js", "ts", "jsx", "tsx"])
def test_js_focus(repo, runner, modifier, suffix):
    stage(repo, "test." + suffix, js_focus(modifier, runner))
    assert_failed(run(repo), "focused/skipped test")


@pytest.mark.parametrize("runner", ["xit", "xdescribe", "fit", "fdescribe"])
def test_js_aliases(repo, runner):
    stage(repo, "test.js", runner + "('case', () => {});\n")
    assert_failed(run(repo), "focused/skipped test")


def test_multiline_chained_js_focus(repo):
    stage(repo, "test.ts", "test.describe\n ." + "only('case', () => {});\n")
    assert_failed(run(repo), "focused/skipped test")


@pytest.mark.parametrize("expression", [
    "pytest." + "mark." + "skip", "pytest." + "mark." + "skipif(True)",
    "pytest." + "skip('reason')", "unittest." + "skip('reason')",
    "unittest." + "skipIf(True, 'reason')", "unittest." + "skipUnless(False, 'reason')",
])
def test_python_skip(repo, expression):
    stage(repo, "test_case.py", "@" + expression + "\ndef test_case(): pass\n")
    assert_failed(run(repo), "focused/skipped test")


@pytest.mark.parametrize("directive", [
    "@ts-" + "ignore", "@ts-" + "nocheck", "eslint-" + "disable",
    "eslint-" + "disable-next-line", "eslint-" + "disable-line", "prettier-" + "ignore",
    "istanbul " + "ignore next", "v8 " + "ignore next",
])
def test_js_suppressions(repo, directive):
    stage(repo, "example.ts", "// " + directive + "\nconst value = 1;\n")
    assert_failed(run(repo), "new suppression directive")


@pytest.mark.parametrize("directive", ["no" + "qa", "type:" + " ignore", "pragma:" + " no cover"])
def test_python_inline_suppressions(repo, directive):
    stage(repo, "example.py", "value = 1  # " + directive + "\n")
    assert_failed(run(repo), "new suppression directive")


def test_block_comment_suppression(repo):
    stage(repo, "example.js", "/*\n * " + "eslint-" + "disable\n */\n")
    assert_failed(run(repo), "new suppression directive")


def test_strings_comments_docs_and_unrelated_methods_are_not_test_focus(repo):
    stage(repo, "example.py", 'description = "pytest.' + 'skip(1)"\n'
          + '# pytest.' + 'mark.skip\n' + 'text = "# ' + 'noqa"\n')
    stage(repo, "example.ts", 'const description = "test.' + 'only(1)";\n'
          + '// test.' + 'skip(1)\nconst sample = "// @ts-' + 'ignore";\n'
          + 'store.only(1);\nconst x = `test.' + 'todo(1)`;\n')
    stage(repo, "README.md", js_focus() + "// @ts-" + "ignore\n")
    assert run(repo).returncode == 0


@pytest.mark.parametrize("path", [
    "node_modules/pkg/index.js", ".venv/lib/code.py", "reports/a.json", "coverage/lcov.info",
    "playwright-report/index.html", "test-results/test.txt", "pkg/node_modules/x.js",
    "src/crossword/static/lib/x.js", "src/crossword/static/react/x.js", "instance/data.db",
    "data.sqlite", "data.sqlite3", "data.sqlite3-wal",
])
def test_generated_outputs(repo, path):
    stage(repo, path, "safe\n")
    assert_failed(run(repo), "generated output/database")


def test_tracked_generated_change_rejected_but_deletion_allowed(repo):
    stage(repo, "reports/old.json", "old\n")
    git(repo, "commit", "-qm", "old report")
    stage(repo, "reports/old.json", "new\n")
    assert_failed(run(repo), "generated output/database")
    git(repo, "rm", "-f", "reports/old.json")
    assert run(repo).returncode == 0


@pytest.mark.parametrize("path", ["new.bin", "vendor/archive.tgz"])
def test_large_new_and_modified_blobs(repo, path):
    stage(repo, path, b"a" * (1024 * 1024 + 1))
    assert_failed(run(repo), "exceeds 1 MiB")
    git(repo, "commit", "-qm", "historical large blob")
    assert run(repo).returncode == 0
    stage(repo, path, b"b" * (1024 * 1024 + 1))
    assert_failed(run(repo), "exceeds 1 MiB")
    git(repo, "rm", "-f", path)
    assert run(repo).returncode == 0


def test_size_boundary(repo):
    stage(repo, "exact.bin", b"a" * (1024 * 1024))
    assert run(repo).returncode == 0


@pytest.mark.parametrize("marker", ["<" * 7 + " HEAD", "=" * 7, ">" * 7 + " branch", "|" * 7 + " base"])
def test_conflict_markers(repo, marker):
    stage(repo, "notes.txt", marker + "\n")
    assert_failed(run(repo), "conflict marker")


@pytest.mark.parametrize("secret", [
    "ghp_" + "A" * 36, "github_pat_" + "A" * 82, "AKIA" + "A" * 16,
    "ASIA" + "A" * 16, "xoxb-" + "1234567890-1234567890-abcdefghijklmno",
    "-----BEGIN " + "PRIVATE KEY-----", "-----BEGIN " + "RSA PRIVATE KEY-----",
    "-----BEGIN " + "OPENSSH PRIVATE KEY-----",
])
def test_secret_redaction(repo, secret):
    stage(repo, "credentials.txt", "secret=" + secret + "\n")
    result = run(repo)
    assert_failed(result, "[REDACTED]")
    assert secret not in result.stdout + result.stderr
    assert "secret=" not in result.stdout + result.stderr


def test_secret_in_filename_redacted(repo):
    secret = "ghp_" + "A" * 36
    stage(repo, secret + ".js", js_focus())
    result = run(repo)
    assert_failed(result, "[REDACTED]")
    assert secret not in result.stdout + result.stderr


def test_null_delimited_unusual_names(repo):
    for path in ["a space.ts", "tab\tname.py", "line\nname.ts", "-option.ts", "colon:name.ts", "é.ts"]:
        stage(repo, path, js_focus() if path.endswith("ts") else "pytest." + "skip('reason')\n")
    result = run(repo)
    assert_failed(result, "focused/skipped test")
    assert result.stderr.count("focused/skipped test") == 6
    assert "line\\nname.ts" in result.stderr


def test_rename_is_addition_and_deletion(repo):
    stage(repo, "old.js", js_focus())
    git(repo, "commit", "-qm", "historical focused test")
    git(repo, "mv", "old.js", "new.js")
    assert_failed(run(repo), "focused/skipped test")
    git(repo, "rm", "-f", "new.js")
    assert run(repo).returncode == 0


def test_ci_reads_head_not_index_or_worktree(repo):
    base = git(repo, "rev-parse", "HEAD")
    target = stage(repo, "example.ts", js_focus())
    git(repo, "commit", "-qm", "bad commit")
    stage(repo, "example.ts", "const safe = 1;\n")
    assert run(repo).returncode == 0
    assert_failed(run(repo, "--base", base), "focused/skipped test")
    git(repo, "commit", "-qm", "fix")
    target.write_text(js_focus())
    git(repo, "add", "example.ts")
    assert run(repo, "--base", base).returncode == 0


def test_ci_triple_dot_uses_merge_base(repo):
    base = git(repo, "rev-parse", "HEAD")
    stage(repo, "example.ts", js_focus())
    git(repo, "commit", "-qm", "side branch")
    side = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "--detach", base)
    stage(repo, "example.ts", js_focus())
    git(repo, "commit", "-qm", "head branch")
    # side and HEAD have equal file contents, but both differ from merge-base.
    assert_failed(run(repo, "--base", side), "focused/skipped test")


def test_ci_deletion_allowed(repo):
    stage(repo, "old.py", "pytest." + "skip('old')\n")
    git(repo, "commit", "-qm", "old")
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "rm", "old.py")
    git(repo, "commit", "-qm", "delete")
    assert run(repo, "--base", base).returncode == 0


def test_enforcement_changes_advisory_not_semantic_rejection(repo):
    stage(repo, "pyproject.toml", "[tool.example]\nthreshold = 99\n")
    result = run(repo)
    assert result.returncode == 0
    assert "REVIEW" in result.stdout
    assert "human review" in result.stdout
    git(repo, "commit", "-qm", "config")
    git(repo, "rm", "pyproject.toml")
    assert "REVIEW" in run(repo).stdout


def test_invalid_base_fails_closed(repo):
    for base in ["", "HEAD", "--all", "0" * 40]:
        assert_failed(run(repo, "--base=" + base), "BLOCKED")


def test_no_global_bypass(repo):
    result = run(repo, "--ignore-all")
    assert result.returncode == 2


def test_unborn_repository(tmp_path):
    git(tmp_path, "init", "-q")
    stage(tmp_path, "test.js", js_focus())
    assert_failed(run(tmp_path), "focused/skipped test")


def test_unmerged_index_fails_closed(repo):
    stage(repo, "a.txt", "base\n")
    git(repo, "commit", "-qm", "base")
    base = git(repo, "rev-parse", "HEAD")
    stage(repo, "a.txt", "side\n")
    git(repo, "commit", "-qm", "side")
    side = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "--detach", base)
    stage(repo, "a.txt", "head\n")
    git(repo, "commit", "-qm", "head")
    result = subprocess.run(["git", "merge", side], cwd=repo, capture_output=True, check=False)
    assert result.returncode == 1
    assert_failed(run(repo), "BLOCKED")


def test_guard_and_its_tests_can_be_staged(repo):
    stage(repo, "scripts/commit_policy.py", GUARD.read_bytes())
    stage(repo, "tests/test_commit_policy.py", Path(__file__).read_bytes())
    result = run(repo)
    assert result.returncode == 0, result.stdout + result.stderr
