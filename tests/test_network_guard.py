"""The default test run stays on this machine (see the no_outside_network fixture)."""

import socket

import pytest


def test_connections_outside_this_machine_are_blocked(no_outside_network):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(OSError, match="outside this machine"):
            sock.connect(("203.0.113.1", 9))  # TEST-NET-3: documentation range, never routed
    finally:
        sock.close()
    assert no_outside_network == [("203.0.113.1", 9)]
    no_outside_network.clear()


def test_loopback_connections_are_allowed(no_outside_network):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(server.getsockname())
    finally:
        client.close()
        server.close()
    assert no_outside_network == []


@pytest.mark.network
def test_network_marker_turns_the_guard_off(no_outside_network):
    assert no_outside_network is None
