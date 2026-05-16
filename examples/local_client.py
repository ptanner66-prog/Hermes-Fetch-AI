from __future__ import annotations

import subprocess
import sys

if __name__ == "__main__":
    raise SystemExit(
        subprocess.call([sys.executable, "-m", "hermes_fetch_ai.cli", "demo", "local"])
    )
