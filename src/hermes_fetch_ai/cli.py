from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .config import load_config, validate_config_file
from .hermes_probe import probe
from .mcp_shim import HermesMCPClientShim
from .uagent_app import run_local_roundtrip, run_local_tool_roundtrip
from .version_pins import check_pins

ROOT = Path(__file__).resolve().parents[2]


def _contamination_scan() -> tuple[bool, str]:
    forbidden = ["Open" + "Claw", "market" + "place", "bill" + "ing", "pay" + "ment"]
    paths = [
        ROOT / "src",
        ROOT / "docs",
        ROOT / "examples",
        ROOT / "README.md",
        ROOT / ".env.example",
        ROOT / "pyproject.toml",
    ]
    hits: list[str] = []
    for p in paths:
        files = [p] if p.is_file() else list(p.rglob("*")) if p.exists() else []
        for f in files:
            if not f.is_file() or f.suffix.lower() in {".pyc", ".png", ".jpg"}:
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            for term in forbidden:
                if term.lower() in text.lower():
                    hits.append(f"{f}: {term}")
    return (not hits, "ok" if not hits else "\n".join(hits))


def doctor(args: argparse.Namespace) -> int:
    ok, msg = validate_config_file(args.config)
    if not ok:
        print(f"config: FAIL: {msg}")
        return 1
    pin_problems = check_pins()
    if pin_problems:
        print("pins: WARN: " + "; ".join(pin_problems))
    if args.contamination_scan:
        clean, detail = _contamination_scan()
        print(f"contamination: {'ok' if clean else 'FAIL'}")
        if not clean:
            print(detail)
            return 1
    if args.probe_backend:
        backend_ok, backend_msg = asyncio.run(_probe_backend(args.config))
        print(f"backend: {'ok' if backend_ok else 'FAIL'}: {backend_msg}")
        if not backend_ok:
            return 1
    print("doctor: ok")
    return 0


async def _probe_backend(config_path: str) -> tuple[bool, str]:
    cfg = load_config(config_path)
    async with HermesMCPClientShim(cfg) as shim:
        if shim.startup_error is not None:
            return False, f"{type(shim.startup_error).__name__}: {shim.startup_error}"
        tools = await shim.list_tools()
    if not tools:
        return False, "backend listed zero tools"
    return True, f"{len(tools)} tools"


def probe_hermes(args: argparse.Namespace) -> int:
    for k, v in probe().items():
        print(f"{k}: {v}")
    return 0


async def _demo_local(config_path: str | Path | None = None) -> int:
    cfg = load_config(config_path or ROOT / "examples" / "local-direct.yaml")
    bridge_address, visible_count, echo_result, audit_count = await run_local_roundtrip(cfg)
    print(f"bridge address: {bridge_address}")
    print(f"visible tool count: {visible_count}")
    print(f"echo result: {echo_result}")
    print(f"audit event count: {audit_count}")
    return 0 if echo_result == "hello" else 1


async def _demo_tool(config_path: str | Path, tool: str, args_json: str) -> int:
    cfg = load_config(config_path)
    try:
        tool_args = json.loads(args_json)
    except json.JSONDecodeError as exc:
        print(f"args-json: FAIL: {exc}")
        return 1
    if not isinstance(tool_args, dict):
        print("args-json: FAIL: expected a JSON object")
        return 1
    bridge_address, visible_count, result, audit_count = await run_local_tool_roundtrip(
        cfg, tool, tool_args
    )
    print(f"bridge address: {bridge_address}")
    print(f"visible tool count: {visible_count}")
    print(f"{tool} result: {result}")
    print(f"audit event count: {audit_count}")
    return 0


def demo(args: argparse.Namespace) -> int:
    if args.kind == "mailbox":
        cfg = ROOT / "examples" / "agentverse-mailbox.yaml"
        ok, msg = validate_config_file(cfg)
        if not ok:
            print(f"mailbox demo requires UAGENT_SEED and hosted mailbox setup: {msg}")
            return 1
        print(
            "mailbox demo is manual hosted setup only; see research/FETCH_ACCOUNT_REQUIREMENTS.md"
        )
        return 0
    if args.kind == "hermes":
        cfg_path = args.config or ROOT / "examples" / "hermes-stdio.yaml"
        return asyncio.run(_demo_tool(cfg_path, args.tool, args.args_json))
    return asyncio.run(_demo_local(args.config))


def serve(args: argparse.Namespace) -> int:
    from .uagent_app import run_bridge

    cfg = load_config(args.config)
    asyncio.run(run_bridge(cfg))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hermes-fetch-ai")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("doctor")
    d.add_argument("--config", default=str(ROOT / "examples" / "local-direct.yaml"))
    d.add_argument("--contamination-scan", action="store_true")
    d.add_argument("--probe-backend", action="store_true")
    d.set_defaults(func=doctor)
    ph = sub.add_parser("probe-hermes")
    ph.set_defaults(func=probe_hermes)
    s = sub.add_parser("serve")
    s.add_argument("--config", required=True)
    s.set_defaults(func=serve)
    dm = sub.add_parser("demo")
    dm.add_argument("kind", choices=["local", "hermes", "mailbox"])
    dm.add_argument("--config", default=None)
    dm.add_argument("--tool", default="conversations_list")
    dm.add_argument("--args-json", default='{"limit": 1}')
    dm.set_defaults(func=demo)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
