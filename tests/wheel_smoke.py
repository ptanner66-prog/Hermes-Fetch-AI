"""Install and exercise a wheel outside its source tree and development environment.

Run: python tests/wheel_smoke.py dist/hermes_fetch_ai-1.0.0-py3-none-any.whl
This intentionally resolves the wheel's published requirements as an end user would.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
import venv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve(strict=True)
    if wheel.suffix != ".whl":
        parser.error("supply one built .whl file")
    with tempfile.TemporaryDirectory(prefix="hermes-fetch-wheel-") as directory:
        root = Path(directory)
        environment = root / "venv"
        work = root / "work"
        work.mkdir()
        venv.EnvBuilder(with_pip=True).create(environment)
        binary = environment / ("Scripts" if os.name == "nt" else "bin")
        python = binary / ("python.exe" if os.name == "nt" else "python")
        cli = binary / ("hermes-fetch-ai.exe" if os.name == "nt" else "hermes-fetch-ai")
        env = os.environ.copy()
        for name in (
            "PYTHONPATH",
            "PYTHONHOME",
            "UAGENT_SEED",
            "HERMES_FETCH_PAYER_SEED",
            "HERMES_FETCH_FIELD_TEST",
            "HERMES_FETCH_LIVE_TESTNET",
        ):
            env.pop(name, None)
        env["HERMES_HOME"] = str(root / "hermes-home")
        for name in (
            "HOME",
            "USERPROFILE",
            "APPDATA",
            "LOCALAPPDATA",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
        ):
            location = root / name.lower()
            location.mkdir()
            env[name] = str(location)

        def run(*command: str | Path) -> None:
            subprocess.run(
                [str(part) for part in command],
                cwd=work,
                env=env,
                check=True,
                timeout=600,
            )

        run(python, "-m", "pip", "install", "--disable-pip-version-check", wheel)
        run(python, "-m", "pip", "check")
        run(
            python,
            "-c",
            "from pathlib import Path; import sys, hermes_fetch_ai; "
            "from hermes_fetch_ai.cli import default_config_path; "
            "assert Path(hermes_fetch_ai.__file__).is_relative_to(sys.prefix); "
            "assert default_config_path().parent.name == 'data'; "
            "print('Installed package and bundled default config verified')",
        )
        run(cli, "--version")
        run(cli, "doctor")
        for demo in ("local", "paid", "chat", "buy"):
            run(cli, "demo", demo)
        print("Wheel smoke passed outside the source checkout.")


if __name__ == "__main__":
    main()
