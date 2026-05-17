from __future__ import annotations

import importlib.util
import sys
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
    try:
        mcp_serve_spec = importlib.util.find_spec("mcp_serve")
    except ModuleNotFoundError:
        mcp_serve_spec = None
    info["hermes_mcp_serve_module"] = "importable" if mcp_serve_spec else "not importable"
    try:
        cli_spec = importlib.util.find_spec("hermes_cli.main")
    except ModuleNotFoundError:
        cli_spec = None
    info["hermes_cli_main"] = "importable" if cli_spec else "not importable"
    try:
        server = _build_fake_server()
        info["fake_tools"] = 2 if server else 0
    except Exception as e:
        info["fake_mode"] = f"failed: {e}"
    hermes = info["hermes_console"]
    if hermes != "not found":
        try:
            res = subprocess.run(
                [hermes, "mcp", "serve", "--help"], text=True, capture_output=True, timeout=5
            )
            info["hermes_mcp_serve_help"] = f"exit={res.returncode}"
            if "mcp_serve" in (res.stderr + res.stdout):
                info["hermes_mcp_serve_help"] += " ModuleNotFoundError: mcp_serve"
        except Exception as e:
            info["hermes_mcp_serve_help"] = type(e).__name__
    elif cli_spec is not None:
        try:
            res = subprocess.run(
                [sys.executable, "-m", "hermes_cli.main", "mcp", "serve", "--help"],
                text=True,
                capture_output=True,
                timeout=5,
            )
            info["hermes_mcp_serve_help"] = f"python-module exit={res.returncode}"
        except Exception as e:
            info["hermes_mcp_serve_help"] = type(e).__name__
    else:
        info["hermes_mcp_serve_help"] = "not checked"
    return info
