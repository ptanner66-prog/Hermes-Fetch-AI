"""Running a local program for each service request, with limits.

No shell is involved, the program starts in an empty temporary folder with a
short environment, and both time and output size are capped. A program that
runs too long, or that the bridge stops, is killed together with everything
it started.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import sys
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass

from .logging import get_logger

logger = get_logger("hermes_fetch_ai")

# How long a killed program gets to finish going away.
_STOP_SECONDS = 5.0
# Environment a program always gets; anything else must be passed on purpose.
_BASE_ENV = ("PATH", "LANG", "LANGUAGE", "TZ", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT")


@dataclass(frozen=True)
class ServiceResult:
    text: str
    # False when the runner itself failed; the buyer keeps the payment and may retry.
    ok: bool
    problem: str = ""


def base_env(workdir: str, pass_env: Iterable[str] = ()) -> dict[str, str]:
    """A program's environment: the basics, the ``pass_env`` names, and ``workdir`` as home."""
    env = {name: os.environ[name] for name in _BASE_ENV if name in os.environ}
    env.update({name: value for name, value in os.environ.items() if name.startswith("LC_")})
    env.update({name: os.environ[name] for name in pass_env if name in os.environ})
    env["HOME"] = workdir
    env["TMPDIR"] = workdir
    return env


class ProgramRunner:
    """Runs one program per request and turns what it prints into the answer.

    Subclasses say what to run (``command``), what it reads on stdin
    (``payload``), and how its output becomes the answer (``answer``).
    """

    # How logs name the program.
    label = "service program"

    def __init__(self, *, timeout_seconds: float, read_limit: int, show_errors: bool) -> None:
        self.timeout_seconds = timeout_seconds
        # Bytes of output read before the program is stopped, so a runaway
        # program cannot fill memory.
        self.read_limit = read_limit
        # Only for the owner's own test runs: buyers never see the program's stderr.
        self.show_errors = show_errors

    def command(self, workdir: str) -> tuple[list[str], dict[str, str]]:
        raise NotImplementedError

    def payload(self, request: str) -> bytes:
        raise NotImplementedError

    def answer(self, output: bytes, returncode: int | None, overflowed: bool) -> ServiceResult:
        raise NotImplementedError

    async def run(self, request: str) -> ServiceResult:
        # Windows cannot delete a folder a leftover process still uses; never fail on that.
        with tempfile.TemporaryDirectory(
            prefix="hermes-fetch-ai-service-", ignore_cleanup_errors=True
        ) as workdir:
            argv, env = self.command(workdir)
            try:
                process = await asyncio.create_subprocess_exec(
                    *argv,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=None if self.show_errors else asyncio.subprocess.DEVNULL,
                    cwd=workdir,
                    env=env,
                    start_new_session=os.name != "nt",
                )
            except OSError as exc:
                logger.warning("%s %s could not start (%s)", self.label, argv[0], exc)
                return ServiceResult("", ok=False, problem=f"the {self.label} could not start")
            try:
                output, overflowed = await asyncio.wait_for(
                    self._exchange(process, self.payload(request)), self.timeout_seconds
                )
            except TimeoutError:
                await self._stop(process)
                return ServiceResult("", ok=False, problem="the service took too long")
            except asyncio.CancelledError:
                # The bridge is stopping: never leave the program running behind it.
                self._kill(process)
                raise
            return self.answer(output, process.returncode, overflowed)

    async def _exchange(
        self, process: asyncio.subprocess.Process, payload: bytes
    ) -> tuple[bytes, bool]:
        """Send the request and read the output; True if the program wrote too much."""
        assert process.stdin is not None and process.stdout is not None
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            process.stdin.write(payload)
            await process.stdin.drain()
        process.stdin.close()
        chunks: list[bytes] = []
        size = 0
        while size < self.read_limit:
            chunk = await process.stdout.read(min(65536, self.read_limit - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        overflowed = size >= self.read_limit
        if overflowed:
            await self._stop(process)
        else:
            await process.wait()
        return b"".join(chunks), overflowed

    async def _stop(self, process: asyncio.subprocess.Process) -> None:
        """Kill the program (and anything it started) and wait for it to go.

        asyncio's ``wait()`` also waits for the output pipe to close, and a pipe
        we stopped reading never does, so the leftover output is read and
        dropped. A process that escaped the kill and still holds the pipe open
        is given up on after a few seconds rather than hanging the bridge.
        """
        self._kill(process)
        stdout = process.stdout
        assert stdout is not None

        async def drain() -> None:
            while await stdout.read(65536):
                pass
            await process.wait()

        try:
            await asyncio.wait_for(drain(), _STOP_SECONDS)
        except TimeoutError:
            logger.warning("a %s left a process holding its output open", self.label)

    @staticmethod
    def _kill(process: asyncio.subprocess.Process) -> None:
        with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
            if sys.platform == "win32":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
