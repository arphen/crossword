"""Bounded host bridge to the extracted local xfill runtime.

This bridge creates answer-grid drafts only. The fill word list does not carry
the sense and clue evidence required to publish a playable personalized puzzle.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import stat
import time

from .token_construction import validate_native_token_cells


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_CLI = PROJECT_ROOT / "node_modules" / "@crossword" / "local-runtime" / "bin" / "local-runtime.mjs"
MAX_REQUEST_BYTES = 16 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024
RUNTIME_TIMEOUT_SECONDS = 240
_SOURCE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_RAW_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_WORDLIST_LINE = re.compile(r"^([A-Z]{3,15});([0-9]{1,3})$")

DEFAULT_OPTIONS = {
    "seed": 1,
    # Grid-draft jobs are curator inputs, not playable puzzles. Use a wider
    # search and preserve the engine's measured scores for later validation.
    "candidates": 400,
    "time": 10,
    "keepMean": 50,
    "minScore": 40,
    "maxIffy": 20,
    "themes": [],
}
SUPPORTED_GRID_SIZES = frozenset({15, 21})


class FullSizeRuntimeUnavailable(RuntimeError):
    """The pinned local construction runtime could not complete a draft."""


class FullSizeDraftRejected(ValueError):
    """A request or runtime result failed the host protocol checks."""


class FullSizeDraftCancelled(RuntimeError):
    """The user cancelled an answer-grid draft while its native job was running."""


def _validated_options(seed, supplied=None):
    if type(seed) is not int or not 0 <= seed <= 2_147_483_647:
        raise FullSizeDraftRejected("Construction seed must be a nonnegative 31-bit integer")
    if supplied is None:
        supplied = {}
    if not isinstance(supplied, dict) or set(supplied) - (
        set(DEFAULT_OPTIONS) | {"gridSize"}
    ):
        raise FullSizeDraftRejected("Construction options are invalid")
    if "seed" in supplied and supplied["seed"] != seed:
        raise FullSizeDraftRejected("Construction options do not match the requested seed")
    options = {**DEFAULT_OPTIONS, **supplied, "seed": seed}
    grid_size = options.get("gridSize", 15)
    if (
        type(options["candidates"]) is not int
        or not 10 <= options["candidates"] <= 400
        or isinstance(options["time"], bool)
        or not isinstance(options["time"], (int, float))
        or not math.isfinite(options["time"])
        or not 0.25 <= options["time"] <= 10
        or type(options["keepMean"]) is not int
        or not 50 <= options["keepMean"] <= 95
        or type(options["minScore"]) is not int
        or not 40 <= options["minScore"] <= 80
        or type(options["maxIffy"]) is not int
        or not 0 <= options["maxIffy"] <= 100
        or grid_size not in SUPPORTED_GRID_SIZES
        or not isinstance(options["themes"], list)
        or len(options["themes"]) > 4
        or any(
            not isinstance(theme, str)
            or not re.fullmatch(r"[A-Z]{3,15}", theme)
            or len(theme) == 12
            for theme in options["themes"]
        )
    ):
        raise FullSizeDraftRejected("Construction options are outside the local runtime limits")
    return options


def _validate_result(value, expected_options):
    if not isinstance(value, dict) or value.get("version") != 1:
        raise FullSizeRuntimeUnavailable("The local construction runtime returned an unsupported response")
    result = value.get("result")
    if not isinstance(result, dict):
        error = value.get("error")
        message = error.get("message") if isinstance(error, dict) else None
        if isinstance(message, str) and message.strip():
            raise FullSizeRuntimeUnavailable(message[:240])
        raise FullSizeRuntimeUnavailable("The local construction runtime returned no result")
    grid = result.get("grid")
    grid_size = expected_options.get("gridSize", 15)
    if (
        result.get("engine") != "xfill"
        or result.get("options") != expected_options
        or type(result.get("durationMs")) is not int
        or not 0 <= result["durationMs"] <= RUNTIME_TIMEOUT_SECONDS * 1000
        or not isinstance(result.get("sourceDigest"), str)
        or not _SOURCE_DIGEST.fullmatch(result["sourceDigest"])
        or not isinstance(grid, dict)
        or not isinstance(grid.get("fill"), list)
        or len(grid["fill"]) != grid_size
        or any(
            not isinstance(row, str)
            or not re.fullmatch(rf"[A-Z#]{{{grid_size}}}", row)
            for row in grid["fill"]
        )
        or not isinstance(grid.get("entries"), list)
        or not 50 <= len(grid["entries"]) <= (220 if grid_size == 21 else 78)
    ):
        raise FullSizeRuntimeUnavailable("The local construction runtime returned an invalid draft")
    try:
        validate_native_token_cells(grid)
    except ValueError as error:
        raise FullSizeRuntimeUnavailable(
            f"The local construction runtime returned invalid token cells: {error}"
        ) from error
    return result


def _validate_admitted_wordlist(value):
    """Check the trusted worker's private wordlist receipt before spawning Node."""
    if not isinstance(value, dict) or set(value) != {"path", "sha256", "packId", "packSha256"}:
        raise FullSizeDraftRejected("The admitted wordlist receipt is invalid")
    path_value = value["path"]
    if (
        not isinstance(path_value, str)
        or not path_value
        or not Path(path_value).is_absolute()
        or not isinstance(value["packId"], str)
        or not value["packId"].strip()
        or len(value["packId"]) > 200
        or not isinstance(value["sha256"], str)
        or not _RAW_SHA256.fullmatch(value["sha256"])
        or not isinstance(value["packSha256"], str)
        or not _RAW_SHA256.fullmatch(value["packSha256"])
    ):
        raise FullSizeDraftRejected("The admitted wordlist receipt is invalid")
    path = Path(path_value)
    try:
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 2 * 1024 * 1024:
            raise FullSizeDraftRejected("The admitted wordlist file is invalid")
        with path.open("rb") as wordlist_file:
            opened = os.fstat(wordlist_file.fileno())
            if not stat.S_ISREG(opened.st_mode) or opened.st_size > 2 * 1024 * 1024:
                raise FullSizeDraftRejected("The admitted wordlist file is invalid")
            raw = wordlist_file.read(2 * 1024 * 1024 + 1)
        text = raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as error:
        raise FullSizeDraftRejected("The admitted wordlist file is unavailable") from error
    if hashlib.sha256(raw).hexdigest() != value["sha256"]:
        raise FullSizeDraftRejected("The admitted wordlist digest does not match")
    if len(raw) > 2 * 1024 * 1024 or not text or text.endswith("\n\n"):
        raise FullSizeDraftRejected("The admitted wordlist file is invalid")
    lines = text.removesuffix("\n").split("\n")
    seen = set()
    for line in lines:
        match = _WORDLIST_LINE.fullmatch(line)
        if match is None or int(match.group(2)) > 100 or match.group(1) in seen:
            raise FullSizeDraftRejected("The admitted wordlist file is invalid")
        seen.add(match.group(1))
    if not seen:
        raise FullSizeDraftRejected("The admitted wordlist file is empty")
    return {
        "path": str(path),
        "sha256": value["sha256"],
        "packId": value["packId"],
        "packSha256": value["packSha256"],
        "answers": seen,
    }


def _stop_process(process):
    # The CLI starts Cargo/xfill descendants in its own session. Signal the
    # entire owned group, even if its leader already exited but descendants
    # still hold stdout/stderr open (or otherwise survived the parent).
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except OSError:
            pass
    elif process.poll() is None:
        try:
            process.send_signal(signal.SIGTERM)
        except OSError:
            pass
    try:
        process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    # A grandchild can close inherited pipes yet keep running, in which case
    # communicate() alone does not establish that the process group is gone.
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
    elif process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    process.communicate()


def _run_cancellable(command, *, serialized, environment, cancel_requested):
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=PROJECT_ROOT,
            env=environment,
            start_new_session=(os.name == "posix"),
        )
    except OSError as error:
        raise FullSizeRuntimeUnavailable("The local construction runtime did not respond") from error
    deadline = time.monotonic() + RUNTIME_TIMEOUT_SECONDS
    pending_input = serialized
    try:
        while True:
            if cancel_requested():
                raise FullSizeDraftCancelled("The answer-grid draft was cancelled")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise FullSizeRuntimeUnavailable("The local construction runtime timed out")
            try:
                stdout, stderr = process.communicate(
                    input=pending_input,
                    timeout=min(0.25, remaining),
                )
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=process.returncode,
                    stdout=stdout,
                    stderr=stderr,
                )
            except subprocess.TimeoutExpired:
                pending_input = None
    except BaseException:
        _stop_process(process)
        raise


def generate_full_size_draft(
    *, seed=1, options=None, engine_root=None, cancel_requested=None, admitted_wordlist=None
):
    """Generate one validated 15×15 answer-grid draft through the fixed local CLI."""
    options = _validated_options(seed, options)
    admitted = _validate_admitted_wordlist(admitted_wordlist) if admitted_wordlist is not None else None
    node = shutil.which("node")
    if not node or not RUNTIME_CLI.is_file():
        raise FullSizeRuntimeUnavailable("The local full-size construction runtime is unavailable")
    operation = {"version": 1, "options": options}
    if engine_root is not None:
        if not isinstance(engine_root, str) or not engine_root.strip():
            raise FullSizeDraftRejected("The configured engine root is invalid")
        operation["engineRoot"] = engine_root
    if admitted is not None:
        operation["admittedWordlist"] = {
            key: admitted[key] for key in ("path", "sha256", "packId", "packSha256")
        }
    serialized = json.dumps(operation, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    if len(serialized.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise FullSizeDraftRejected("The local construction request is too large")

    environment = {"PATH": os.environ.get("PATH", ""), "CARGO_NET_OFFLINE": "true"}
    for key in ("HOME", "CARGO_HOME", "RUSTUP_HOME", "CROSSWORD_XFILL_ROOT"):
        value = os.environ.get(key)
        if value:
            environment[key] = value
    command = [node, str(RUNTIME_CLI)]
    if cancel_requested is None:
        try:
            completed = subprocess.run(
                command,
                input=serialized,
                text=True,
                capture_output=True,
                timeout=RUNTIME_TIMEOUT_SECONDS,
                cwd=PROJECT_ROOT,
                env=environment,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise FullSizeRuntimeUnavailable("The local construction runtime did not respond") from error
    elif not callable(cancel_requested):
        raise FullSizeDraftRejected("The cancellation monitor is invalid")
    else:
        completed = _run_cancellable(
            command,
            serialized=serialized,
            environment=environment,
            cancel_requested=cancel_requested,
        )
    if len(completed.stdout.encode("utf-8")) + len(completed.stderr.encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise FullSizeRuntimeUnavailable("The local construction runtime response is too large")
    try:
        response = json.loads(completed.stdout)
    except (ValueError, UnicodeDecodeError) as error:
        raise FullSizeRuntimeUnavailable("The local construction runtime returned invalid JSON") from error
    if completed.returncode != 0:
        error = response.get("error") if isinstance(response, dict) else None
        message = error.get("message") if isinstance(error, dict) else None
        raise FullSizeRuntimeUnavailable(message[:240] if isinstance(message, str) else "The local construction runtime failed")
    result = _validate_result(response, options)
    if admitted is not None:
        receipt = result.get("provenance", {}).get("admittedPack") if isinstance(result.get("provenance"), dict) else None
        if receipt != {
            "packId": admitted["packId"],
            "packSha256": admitted["packSha256"],
            "wordlistSha256": admitted["sha256"],
        }:
            raise FullSizeRuntimeUnavailable("The runtime admitted-pack receipt did not match the request")
        if any(
            not isinstance(entry, dict) or entry.get("answer") not in admitted["answers"]
            for entry in result["grid"]["entries"]
        ):
            raise FullSizeRuntimeUnavailable("The runtime returned an answer outside the admitted wordlist")
    return result
