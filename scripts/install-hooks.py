"""Install the tracked hook without silently replacing another hook manager."""

from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
result = subprocess.run(
    ["git", "config", "--get", "core.hooksPath"],
    cwd=root,
    text=True,
    capture_output=True,
)
if result.returncode not in (0, 1):
    sys.exit(result.returncode)
current = result.stdout.strip()
if current and current != ".githooks":
    sys.exit(
        f"Refusing to overwrite core.hooksPath={current!r}. Ask the maintainer to migrate it."
    )
subprocess.run(
    ["git", "config", "--local", "core.hooksPath", ".githooks"], cwd=root, check=True
)
hook = root / ".githooks/pre-commit"
hook.chmod(hook.stat().st_mode | 0o111)
print("Installed .githooks/pre-commit. Run make precommit to check the staged changes.")
