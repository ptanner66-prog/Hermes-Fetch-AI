"""Running the bridge in the background: ``start``, ``stop``, ``restart``, ``status``, ``logs``.

``start`` runs ``serve`` as a background process with its output in
``serve.log`` in the bridge's records folder. ``serve``, however it was
started, writes ``serve.json`` there (its process id, start time, config, and
log) and removes it when it stops, so there is at most one running bridge per
records folder. ``stop`` asks it to finish its work and stop: with SIGTERM, or
on Windows, where a background process gets no console signals, by creating
``serve.stop``, which ``serve`` watches for.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

RUN_FILE = "serve.json"
STOP_FILE = "serve.stop"
LOG_FILE = "serve.log"
# Set by `start` so `serve` can say where its output goes.
LOG_VAR = "HERMES_FETCH_AI_SERVE_LOG"
MAX_LOG_BYTES = 5 * 1024 * 1024
START_WAIT_SECONDS = 60.0
# After `serve` says it is ready, how long it must keep running for `start` to
# report success: a port someone else holds fails it within moments.
SETTLE_SECONDS = 2.0
STOP_WAIT_SECONDS = 40.0  # serve's own grace for work in progress is 20 s


@dataclass(frozen=True)
class RunInfo:
    pid: int
    started: float
    config: str
    log: str | None = None
    # Set once the agent is up (its backend, records, and control channel).
    ready: bool = False


class AlreadyRunning(Exception):
    """Another bridge is running with the same records folder."""

    def __init__(self, info: RunInfo) -> None:
        super().__init__(
            f"another bridge is already running with these records (process {info.pid}, "
            "started " + _clock(info.started) + "); stop it first: hermes fetchai-bridge stop"
        )
        self.info = info


def pid_alive(pid: int) -> bool:
    """True if a process with this id is running (never signals it)."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and (
                code.value == 259  # STILL_ACTIVE
            )
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def is_bridge(pid: int) -> bool:
    """True if ``pid`` is a running bridge (not another process that got its id)."""
    if not pid_alive(pid):
        return False
    proc = Path(f"/proc/{pid}/cmdline")
    if proc.exists():
        with contextlib.suppress(OSError):
            command_line = proc.read_bytes()
            return b"hermes_fetch_ai" in command_line or b"hermes-fetch-ai" in command_line
    if sys.platform != "win32":
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            command = subprocess.run(
                ["ps", "-o", "command=", "-p", str(pid)],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            ).stdout
            return "hermes_fetch_ai" in command or "hermes-fetch-ai" in command
    return True  # Windows: the id is all there is to go on


def read_running(state: Path) -> RunInfo | None:
    """The bridge running with the records in ``state``, if one is (a stale file is removed)."""
    path = state / RUN_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        info = RunInfo(
            pid=int(data["pid"]),
            started=float(data["started"]),
            config=str(data["config"]),
            log=data.get("log"),
            ready=bool(data.get("ready", False)),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if is_bridge(info.pid):
        return info
    with contextlib.suppress(OSError):
        path.unlink()
    return None


def claim(state: Path, config: Path) -> RunInfo:
    """Record this process as the bridge running with ``state``; raises AlreadyRunning."""
    other = read_running(state)
    if other is not None and other.pid != os.getpid():
        raise AlreadyRunning(other)
    info = RunInfo(
        pid=os.getpid(),
        started=time.time(),
        config=str(config),
        log=os.environ.get(LOG_VAR) or None,
    )
    state.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        (state / STOP_FILE).unlink()  # a stop request meant for an earlier run
    _write_run_file(state, info)
    return info


def _write_run_file(state: Path, info: RunInfo) -> None:
    temp = state / f".{RUN_FILE}.{os.getpid()}"
    temp.write_text(json.dumps(asdict(info)), encoding="utf-8")
    os.replace(temp, state / RUN_FILE)


def mark_ready(state: Path) -> None:
    """Note in the run file that this bridge is up (``start`` waits for it)."""
    with contextlib.suppress(OSError, ValueError, KeyError, TypeError):
        data = json.loads((state / RUN_FILE).read_text(encoding="utf-8"))
        if int(data["pid"]) == os.getpid():
            _write_run_file(state, RunInfo(**{**data, "ready": True}))


def release(state: Path) -> None:
    """Forget this process as the running bridge (only if it is the one recorded)."""
    path = state / RUN_FILE
    with contextlib.suppress(OSError, ValueError, KeyError, TypeError):
        if int(json.loads(path.read_text(encoding="utf-8"))["pid"]) == os.getpid():
            path.unlink()
    with contextlib.suppress(OSError):
        (state / STOP_FILE).unlink()


def stop_requested(state: Path) -> bool:
    return (state / STOP_FILE).exists()


def _clock(epoch: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch))


def _rotate(log: Path) -> None:
    with contextlib.suppress(OSError):
        if log.stat().st_size > MAX_LOG_BYTES:
            os.replace(log, log.with_name(log.name + ".1"))


def tail(path: Path, lines: int) -> list[str]:
    """The last ``lines`` lines of ``path`` (none if it cannot be read)."""
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(size - 256 * 1024, 0))
            text = f.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    return text.splitlines()[-lines:] if lines > 0 else []


def start(
    config: Path,
    state: Path,
    *,
    wait: float = START_WAIT_SECONDS,
    settle: float = SETTLE_SECONDS,
    out: Callable[[str], None] = print,
) -> int:
    """Start ``serve --config config`` in the background; 0 once it is up and stays up."""
    running = read_running(state)
    if running is not None:
        out(f"Your agent is already running (since {_clock(running.started)}).")
        out("To apply changes: hermes fetchai-bridge restart")
        return 0
    state.mkdir(parents=True, exist_ok=True)
    log = state / LOG_FILE
    _rotate(log)
    env = dict(os.environ)
    env[LOG_VAR] = str(log)
    command = [sys.executable, "-m", "hermes_fetch_ai.cli", "serve", "--config", str(config)]
    options: dict[str, Any] = {}
    if sys.platform == "win32":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        options["start_new_session"] = True  # keeps running when the terminal closes
    # The log stays private: it names the agents this one deals with.
    with os.fdopen(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), "ab") as output:
        output.write(f"\n--- started {_clock(time.time())} ---\n".encode())
        output.flush()
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            cwd=state,
            env=env,
            close_fds=True,
            **options,
        )
    deadline = time.monotonic() + wait
    ready_since: float | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            out("Your agent could not start. The end of its log:")
            for line in tail(log, 20):
                out(f"  {line}")
            return 1
        running = read_running(state)
        if running is not None and running.ready and running.pid == process.pid:
            ready_since = ready_since or time.monotonic()
            if time.monotonic() - ready_since >= settle:
                out(f"Your agent is running (process {process.pid}).")
                out(f"Its log: {log}")
                out("See what it is doing: hermes fetchai-bridge status")
                return 0
        time.sleep(0.25)
    out(f"Your agent is still starting (process {process.pid}); check in a moment:")
    out("  hermes fetchai-bridge status")
    return 0


def stop(
    state: Path, *, wait: float = STOP_WAIT_SECONDS, out: Callable[[str], None] = print
) -> int:
    """Ask the running bridge to stop, and wait for it; 0 once it has."""
    running = read_running(state)
    if running is None:
        out("Your agent is not running.")
        return 0
    if sys.platform == "win32":
        (state / STOP_FILE).write_text("stop", encoding="utf-8")
    else:
        with contextlib.suppress(ProcessLookupError):
            os.kill(running.pid, signal.SIGTERM)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        if sys.platform != "win32":
            # Started by this very process (`restart`): collect it once it exits.
            with contextlib.suppress(ChildProcessError, OSError):
                os.waitpid(running.pid, os.WNOHANG)
        if not pid_alive(running.pid):
            out("Your agent stopped.")
            with contextlib.suppress(OSError):
                (state / STOP_FILE).unlink()
            return 0
        time.sleep(0.25)
    out(f"Your agent did not stop within {wait:.0f} seconds; stopping it now.")
    with contextlib.suppress(OSError):
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(running.pid)],
                capture_output=True,
                check=False,
                timeout=30,
            )
        else:
            os.kill(running.pid, signal.SIGKILL)
    with contextlib.suppress(OSError):
        (state / RUN_FILE).unlink()
    return 1


def follow(path: Path, out: Callable[[str], None] = print, *, poll: float = 0.5) -> None:
    """Print what is added to ``path`` until interrupted."""
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if line:
                out(line.decode("utf-8", errors="replace").rstrip("\n"))
            else:
                time.sleep(poll)
