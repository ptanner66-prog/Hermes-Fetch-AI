from __future__ import annotations

import argparse
import asyncio
import sys
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


def _is_source_checkout() -> bool:
    return (ROOT / "pyproject.toml").is_file() and (ROOT / "src" / "hermes_fetch_ai").is_dir()


def _contamination_scan() -> tuple[bool, str]:
    forbidden = ["Open" + "Claw", "market" + "place", "bill" + "ing", "pay" + "ment"]
    paths = [
        ROOT / "src",
        ROOT / "docs",
        ROOT / "examples",
        ROOT / "hermes-plugin",
        ROOT / "upstream",
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


def _load_or_report(path: str | Path) -> BridgeConfig | None:
    try:
        return load_config(path)
    except ValidationError as exc:
        print(f"config: FAIL: {format_validation_error(exc)}", file=sys.stderr)
    except ValueError as exc:
        print(f"config: FAIL: {exc}", file=sys.stderr)
    return None


def doctor(args: argparse.Namespace) -> int:
    config_path = args.config or default_config_path()
    ok, msg = validate_config_file(config_path)
    if not ok:
        print(f"config: FAIL: {msg}")
        return 1
    pin_problems = check_pins()
    if pin_problems:
        print("pins: WARN: " + "; ".join(pin_problems))
    seed_warning = load_config(config_path).ignored_seed_warning()
    if seed_warning:
        print(f"seed: WARN: {seed_warning}")
    if args.contamination_scan:
        if not _is_source_checkout():
            print("contamination: SKIP (only meaningful in a source checkout)")
        else:
            clean, detail = _contamination_scan()
            print(f"contamination: {'ok' if clean else 'FAIL'}")
            if not clean:
                print(detail)
                return 1
    print("doctor: ok")
    return 0


def probe_hermes(args: argparse.Namespace) -> int:
    for k, v in probe().items():
        print(f"{k}: {v}")
    return 0


async def _demo_local() -> int:
    cfg = load_config(default_config_path())
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
    from .uagent_app import run_bridge

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
    return 0


def build_parser() -> argparse.ArgumentParser:
    from . import __version__

    p = argparse.ArgumentParser(prog="hermes-fetch-ai")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("doctor")
    d.add_argument("--config", default=None)
    d.add_argument("--contamination-scan", action="store_true")
    d.set_defaults(func=doctor)
    ph = sub.add_parser("probe-hermes")
    ph.set_defaults(func=probe_hermes)
    s = sub.add_parser("serve")
    s.add_argument("--config", required=True)
    s.set_defaults(func=serve)
    dm = sub.add_parser("demo")
    dm.add_argument("kind", choices=["local", "mailbox"])
    dm.set_defaults(func=demo)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
