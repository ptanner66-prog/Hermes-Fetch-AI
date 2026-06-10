from __future__ import annotations

import argparse
import asyncio
from importlib import resources
from pathlib import Path

from .config import load_config, validate_config_file
from .hermes_probe import probe
from .uagent_app import run_local_roundtrip
from .version_pins import check_pins

ROOT = Path(__file__).resolve().parents[2]


def default_config_path() -> Path:
    repo_example = ROOT / "examples" / "local-direct.yaml"
    if repo_example.is_file():
        return repo_example
    packaged = Path(str(resources.files("hermes_fetch_ai").joinpath("data/local-direct.yaml")))
    if packaged.is_file():
        return packaged
    raise FileNotFoundError(
        "no default config found; pass --config explicitly "
        f"(looked at {repo_example} and packaged data/local-direct.yaml)"
    )


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
    ok, msg = validate_config_file(args.config or default_config_path())
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
        cfg = ROOT / "examples" / "agentverse-mailbox.yaml"
        ok, msg = validate_config_file(cfg)
        if not ok:
            print(f"mailbox demo requires UAGENT_SEED and hosted mailbox setup: {msg}")
            return 1
        print(
            "mailbox demo is manual hosted setup only; see research/FETCH_ACCOUNT_REQUIREMENTS.md"
        )
        return 0
    return asyncio.run(_demo_local())


def serve(args: argparse.Namespace) -> int:
    from .uagent_app import run_bridge

    cfg = load_config(args.config)
    run_bridge(cfg)
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
