import ipaddress
import socket
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


@pytest.fixture(autouse=True)
def no_owner_config(monkeypatch, tmp_path_factory):
    """Commands without --config read the config `setup` wrote; never the developer's own."""
    config_home = tmp_path_factory.mktemp("config-home")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("APPDATA", str(config_home))  # where it lives on Windows


def _is_loopback(address) -> bool:
    if not isinstance(address, tuple):  # a Unix socket path
        return True
    host = str(address[0]).split("%", 1)[0]
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def no_outside_network(request, monkeypatch):
    """Fail any test that connects outside this machine, even if the code under test
    swallows the error. Mark a test `network` to allow it (opt-in live tests only)."""
    if request.node.get_closest_marker("network"):
        yield None
        return
    attempts = []
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def check(address):
        if not _is_loopback(address):
            attempts.append(address)
            raise OSError(f"tests may not connect outside this machine: {address!r}")

    def connect(self, address):
        check(address)
        return real_connect(self, address)

    def connect_ex(self, address):
        check(address)
        return real_connect_ex(self, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    yield attempts
    assert not attempts, f"test tried to connect outside this machine: {attempts}"


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
