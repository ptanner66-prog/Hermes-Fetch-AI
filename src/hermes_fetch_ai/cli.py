from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from importlib import resources
from pathlib import Path

from pydantic import ValidationError

from .config import BridgeConfig, format_validation_error, load_config, validate_config_file
from .hermes_probe import probe
from .uagent_app import run_local_roundtrip
from .version_pins import check_pins

ROOT = Path(__file__).resolve().parents[2]
MAILBOX_GUIDE = (
    "https://github.com/ptanner66-prog/Hermes-Fetch-AI/blob/main/docs/agentverse-mailbox.md"
)


def example_config_path(name: str) -> Path:
    """Return an example config from a source checkout, else the packaged copy."""
    repo_example = ROOT / "examples" / name
    if repo_example.is_file():
        return repo_example
    packaged = Path(str(resources.files("hermes_fetch_ai").joinpath(f"data/{name}")))
    if packaged.is_file():
        return packaged
    raise FileNotFoundError(
        "no default config found; pass --config explicitly "
        f"(looked at {repo_example} and packaged data/{name})"
    )


def default_config_path() -> Path:
    return example_config_path("local-direct.yaml")


def _load_or_report(path: str | Path) -> BridgeConfig | None:
    try:
        return load_config(path)
    except ValidationError as exc:
        print(f"config: FAIL: {format_validation_error(exc)}", file=sys.stderr)
    except ValueError as exc:
        print(f"config: FAIL: {exc}", file=sys.stderr)
    return None


def doctor(args: argparse.Namespace) -> int:
    from . import __version__

    print(f"hermes-fetch-ai {__version__}")
    config_path = Path(args.config) if args.config else default_config_path()
    cfg = _load_or_report(config_path)
    if cfg is None:
        return 1
    note = "" if args.config else " (the demo config; pass --config to check yours)"
    print(f"config: ok: {config_path}{note}")
    pin_problems = check_pins()
    if pin_problems:
        print("pins: WARN: " + "; ".join(pin_problems))
    seed_warning = cfg.ignored_seed_warning()
    if seed_warning:
        print(f"seed: WARN: {seed_warning}")
    print("doctor: ok")
    return 0


def probe_hermes(args: argparse.Namespace) -> int:
    info = probe()
    for k, v in info.items():
        print(f"{k}: {v}")
    return 0 if info["hermes_tools_server"] == "importable" else 1


async def _demo_local() -> int:
    cfg = load_config(default_config_path())
    # The demo audits to a throwaway file, never to a real bridge's audit log.
    with tempfile.TemporaryDirectory(prefix="hermes-fetch-ai-demo-") as tmp:
        cfg.logging.audit_path = str(Path(tmp) / "audit.jsonl")
        bridge_address, visible_count, echo_result, audit_count = await run_local_roundtrip(cfg)
    print(f"bridge address: {bridge_address}")
    print(f"visible tool count: {visible_count}")
    print(f"echo result: {echo_result}")
    print(f"audit event count: {audit_count}")
    return 0 if echo_result == "hello" else 1


def demo(args: argparse.Namespace) -> int:
    if args.kind == "mailbox":
        ok, msg = validate_config_file(example_config_path("agentverse-mailbox.yaml"))
        if not ok:
            print(f"mailbox demo requires UAGENT_SEED and hosted mailbox setup: {msg}")
            print(f"setup guide: {MAILBOX_GUIDE}")
            return 1
        print(f"mailbox demo is a manual hosted setup; follow {MAILBOX_GUIDE}")
        return 0
    return asyncio.run(_demo_local())


def serve(args: argparse.Namespace) -> int:
    from .mcp_shim import HermesBackendError
    from .uagent_app import ServeError, run_bridge

    cfg = _load_or_report(args.config)
    if cfg is None:
        return 1
    seed_warning = cfg.ignored_seed_warning()
    if seed_warning:
        print(f"seed: WARN: {seed_warning}", file=sys.stderr)
    try:
        run_bridge(cfg)
    except HermesBackendError as exc:
        print(f"hermes backend: FAIL: {exc}", file=sys.stderr)
        return 1
    except ServeError as exc:
        print(f"serve: FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    from . import __version__

    p = argparse.ArgumentParser(prog="hermes-fetch-ai")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("doctor", help="check a config file and the installed dependency pins")
    d.add_argument("--config", default=None, help="config to check (default: the demo config)")
    d.set_defaults(func=doctor)
    ph = sub.add_parser("probe-hermes", help="check that Hermes' tools MCP server can be imported")
    ph.set_defaults(func=probe_hermes)
    s = sub.add_parser("serve", help="run the bridge uAgent until interrupted")
    s.add_argument("--config", required=True)
    s.set_defaults(func=serve)
    dm = sub.add_parser("demo", help="run the local demo, or check the mailbox demo setup")
    dm.add_argument("kind", choices=["local", "mailbox"])
    dm.set_defaults(func=demo)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
