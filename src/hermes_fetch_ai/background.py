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
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, BinaryIO

import psutil

RUN_FILE = "serve.json"
STOP_FILE = "serve.stop"
LOG_FILE = "serve.log"
LOCK_FILE = "serve.lock"
# Keep the operating-system lock open for the entire bridge lifetime. Crashes
# release it automatically; the lock file itself is never deleted.
_claims: dict[Path, BinaryIO] = {}
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
    created: float | None = None


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
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.Error:
        return False


def is_bridge(pid: int) -> bool:
    """Recognize older run records that did not include process creation time."""
    try:
        process = psutil.Process(pid)
        command = " ".join(process.cmdline())
        return process.is_running() and (
            "hermes_fetch_ai" in command or "hermes-fetch-ai" in command
        )
    except psutil.Error:
        return False


def _running_process(info: RunInfo) -> psutil.Process | None:
    """Return the recorded process, excluding a process that reused its PID.

    psutil also rechecks this identity before terminate/kill, closing the race
    between our check and a later stop attempt.
    """
    try:
        process = psutil.Process(info.pid)
        if info.created is None:
            if process.create_time() > info.started or not is_bridge(info.pid):
                return None
        elif process.create_time() != info.created:
            return None
        return (
            process if process.is_running() and process.status() != psutil.STATUS_ZOMBIE else None
        )
    except psutil.Error:
        return None


def _read_run_file(state: Path) -> RunInfo | None:
    try:
        data = json.loads((state / RUN_FILE).read_text(encoding="utf-8"))
        return RunInfo(
            pid=int(data["pid"]),
            started=float(data["started"]),
            config=str(data["config"]),
            log=data.get("log"),
            ready=bool(data.get("ready", False)),
            created=float(data["created"]) if data.get("created") is not None else None,
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _lock(state: Path) -> BinaryIO:
    state.mkdir(parents=True, exist_ok=True)
    lock = os.fdopen(os.open(state / LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o600), "r+b")
    try:
        if sys.platform == "win32":
            import msvcrt

            # Windows locks a byte range, even when the file has no data yet.
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        lock.close()
        raise
    return lock


def read_running(state: Path) -> RunInfo | None:
    """The recorded bridge, verified against its process creation identity."""
    info = _read_run_file(state)
    if info is None:
        return None
    if _running_process(info) is not None:
        return info
    # Do not delete metadata underneath a starting bridge or another owner.
    try:
        lock = _lock(state)
    except OSError:
        return None
    try:
        if _read_run_file(state) == info:
            with contextlib.suppress(OSError):
                (state / RUN_FILE).unlink()
    finally:
        lock.close()
    return None


def claim(state: Path, config: Path) -> RunInfo:
    """Own ``state`` until release or process exit, before opening any records."""
    state = state.resolve()
    if state in _claims:
        raise AlreadyRunning(
            _read_run_file(state) or RunInfo(os.getpid(), time.time(), str(config))
        )
    try:
        lock = _lock(state)
    except OSError as exc:
        if exc.errno not in (11, 13, 35):
            raise
        pending = _read_run_file(state) or RunInfo(0, time.time(), str(config))
        raise AlreadyRunning(pending) from None
    try:
        other = _read_run_file(state)
        if other is not None and _running_process(other) is not None:
            raise AlreadyRunning(other)
        info = RunInfo(
            pid=os.getpid(),
            started=time.time(),
            config=str(config),
            log=os.environ.get(LOG_VAR) or None,
            created=psutil.Process().create_time(),
        )
        with contextlib.suppress(OSError):
            (state / STOP_FILE).unlink()
        _write_run_file(state, info)
        _claims[state] = lock
        return info
    except BaseException:
        lock.close()
        raise


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
    """Release only the claim this process actually holds."""
    state = state.resolve()
    lock = _claims.pop(state, None)
    if lock is None:
        return
    try:
        info = _read_run_file(state)
        if info is not None and info.pid == os.getpid():
            with contextlib.suppress(OSError):
                (state / RUN_FILE).unlink()
        with contextlib.suppress(OSError):
            (state / STOP_FILE).unlink()
    finally:
        lock.close()


def request_stop(state: Path, info: RunInfo) -> None:
    """Write an atomic request for this exact process, never its successor."""
    temp = state / f".{STOP_FILE}.{uuid.uuid4().hex}"
    try:
        with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
            json.dump({"pid": info.pid, "created": info.created}, f)
        os.replace(temp, state / STOP_FILE)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temp.unlink()


def stop_requested(state: Path) -> bool:
    """Only a request for this process may stop it; legacy sentinels fail closed."""
    try:
        target = json.loads((state / STOP_FILE).read_text(encoding="utf-8"))
        return bool(
            target["pid"] == os.getpid() and target["created"] == psutil.Process().create_time()
        )
    except (OSError, ValueError, KeyError, TypeError, psutil.Error):
        return False


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


def _spawned_process(pid: int, info: RunInfo) -> bool:
    """Windows venv launchers can run the actual interpreter as a child."""
    if info.pid == pid:
        return True
    try:
        return any(child.pid == info.pid for child in psutil.Process(pid).children(recursive=True))
    except psutil.Error:
        return False


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
        if running is not None and running.ready and _spawned_process(process.pid, running):
            ready_since = ready_since or time.monotonic()
            if time.monotonic() - ready_since >= settle:
                out(f"Your agent is running (process {running.pid}).")
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
    """Ask the recorded process to stop; never signal a reused process id."""
    running = read_running(state)
    process = _running_process(running) if running is not None else None
    if running is None or process is None:
        out("Your agent is not running.")
        return 0
    if sys.platform == "win32":
        request_stop(state, replace(running, created=process.create_time()))
    else:
        with contextlib.suppress(psutil.NoSuchProcess):
            process.terminate()
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        if sys.platform != "win32":
            with contextlib.suppress(ChildProcessError, OSError):
                os.waitpid(running.pid, os.WNOHANG)
        try:
            alive = process.is_running() and process.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            alive = False
        if not alive:
            out("Your agent stopped.")
            # release() or the next claim clears its stop request under the lock.
            return 0
        time.sleep(0.25)
    out(f"Your agent did not stop within {wait:.0f} seconds; stopping it now.")
    # Each Process object retains its creation time and rechecks it on kill.
    # Never invoke taskkill with an unchecked PID that might now be unrelated.
    with contextlib.suppress(psutil.Error):
        children = process.children(recursive=True)
        process.kill()
        for child in reversed(children):
            with contextlib.suppress(psutil.Error):
                child.kill()
        # Do not reap a child owned by a caller's Popen object on Unix.
        deadline = time.monotonic() + 5
        while _running_process(running) is not None and time.monotonic() < deadline:
            time.sleep(0.05)
    read_running(state)  # safely remove the old record only after the process is gone
    return 1


def follow(path: Path, out: Callable[[str], None] = print, *, poll: float = 0.5) -> None:
    """Print what is added to ``path`` until interrupted."""
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if line:  # on Windows, lines end with \r\n
                out(line.decode("utf-8", errors="replace").rstrip("\r\n"))
            else:
                time.sleep(poll)
