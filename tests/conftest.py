import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def clear_seed(monkeypatch):
    monkeypatch.delenv("UAGENT_SEED", raising=False)


@pytest.fixture
def almanac_calls(monkeypatch):
    """Record every Almanac contract lookup (Fetch ledger) and Almanac API status report."""
    calls = []

    def contract_lookup(self):
        calls.append("contract lookup")
        return False

    async def status_report(status, almanac_api):
        calls.append("active" if status.is_active else "inactive")

    monkeypatch.setattr("uagents.network.AlmanacContract.check_version", contract_lookup)
    monkeypatch.setattr("uagents.agent.update_agent_status", status_report)
    return calls
