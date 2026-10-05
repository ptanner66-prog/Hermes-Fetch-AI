from __future__ import annotations

import importlib.util
import shutil
import subprocess
from importlib import metadata
from typing import Any

from .config import BridgeConfig
from .fake_mcp import _build_fake_server
from .version_pins import check_pins


def probe(cfg: BridgeConfig | None = None) -> dict[str, Any]:
    info: dict[str, Any] = {"fake_mode": "ok", "pins": check_pins()}
    for pkg in ("uagents", "mcp"):
        try:
            info[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            info[pkg] = "not installed"
    info["hermes_console"] = shutil.which("hermes") or "not found"
    try:
        spec = importlib.util.find_spec("agent.transports.hermes_tools_mcp_server")
    except ModuleNotFoundError:
        spec = None
    info["hermes_build_server"] = "importable" if spec else "not importable"
    info["fake_tools"] = len(_build_fake_server().tools)
    hermes = info["hermes_console"]
    if hermes != "not found":
        try:
            res = subprocess.run(
                [hermes, "mcp", "serve", "--help"],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
            info["hermes_mcp_serve_help"] = f"exit={res.returncode}"
            if "mcp_serve" in (res.stderr + res.stdout):
                info["hermes_mcp_serve_help"] += " ModuleNotFoundError: mcp_serve"
        except (OSError, subprocess.SubprocessError) as e:
            info["hermes_mcp_serve_help"] = type(e).__name__
    else:
        info["hermes_mcp_serve_help"] = "not checked"
    return info
