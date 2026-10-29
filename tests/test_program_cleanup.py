"""Real process tests for service cancellation and descendant cleanup."""

import asyncio
import os
import sys
import time

import pytest

from hermes_fetch_ai.config import CommandRunnerConfig
from hermes_fetch_ai.services import CommandRunner


@pytest.mark.skipif(os.name != "nt", reason="Windows process-tree regression")
@pytest.mark.parametrize("stop", ["timeout", "cancel", "exit"])
async def test_service_descendants_do_not_outlive_the_run(tmp_path, stop):
    marker = tmp_path / "child.pid"
    parent = tmp_path / "parent.py"
    parent.write_text(
        "import subprocess, sys, time\n"
        "from pathlib import Path\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"Path({str(marker)!r}).write_text(str(child.pid))\n"
        + ("print('done')\n" if stop == "exit" else "time.sleep(60)\n"),
        encoding="utf-8",
    )
    runner = CommandRunner(
        CommandRunnerConfig(
            type="command",
            argv=[sys.executable, str(parent)],
            timeout_seconds=10 if stop == "timeout" else 30,
        )
    )
    task = asyncio.create_task(runner.run("hello"))
    handle = None
    try:
        deadline = time.monotonic() + 20
        while not marker.exists() and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        assert marker.exists(), "service did not start its child"
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        handle = kernel.OpenProcess(0x100001, False, int(marker.read_text()))
        if stop == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            result = await asyncio.wait_for(task, 40)
            assert result.ok == (stop == "exit")
        if handle:
            assert await asyncio.to_thread(kernel.WaitForSingleObject, handle, 3000) == 0
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if handle:
            # This handle identifies our exact child even if Windows later reuses its PID.
            if kernel.WaitForSingleObject(handle, 0) != 0:
                kernel.TerminateProcess(handle, 1)
                await asyncio.to_thread(kernel.WaitForSingleObject, handle, 3000)
            kernel.CloseHandle(handle)
