import ipaddress
import os
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Proxy settings: a client given one connects to the proxy, which may be on this
# machine, so the network guard below would let its requests through.
PROXY_VARIABLES = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


@pytest.fixture(autouse=True)
def restore_environment():
    """Undo what the code under test sets in os.environ itself (the plugin keeps a secret
    it saved there, as Hermes does), which monkeypatch does not see."""
    saved = os.environ.copy()
    yield
    for name in set(os.environ) - set(saved):
        del os.environ[name]
    for name, value in saved.items():
        if os.environ.get(name) != value:
            os.environ[name] = value


@pytest.fixture(autouse=True)
def clear_seed(monkeypatch):
    """Tests never see the developer's own agent key or Agentverse key."""
    monkeypatch.delenv("UAGENT_SEED", raising=False)
    monkeypatch.delenv("AGENTVERSE_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def no_owner_files(monkeypatch, tmp_path_factory):
    """Commands use the config `setup` wrote and the default records folder: never the
    developer's own."""
    config_home = tmp_path_factory.mktemp("config-home")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("APPDATA", str(config_home))  # where it lives on Windows
    state_home = tmp_path_factory.mktemp("state-home")
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))
    monkeypatch.setenv("LOCALAPPDATA", str(state_home))


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
    for name in PROXY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
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
