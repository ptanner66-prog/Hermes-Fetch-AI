import re
import tomllib
from pathlib import Path

from hermes_fetch_ai.version_pins import check_pins, declared_pins


def _pyproject_pins():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    pins = {}
    for requirement in project["dependencies"]:
        match = re.match(r"^([A-Za-z0-9._-]+)(?:\[[^\]]*\])?==(\S+)$", requirement)
        if match:
            pins[match.group(1).lower()] = match.group(2)
    return pins


def test_declared_pins_come_from_package_metadata():
    pins = declared_pins()
    assert {"uagents", "uagents-core", "uagents-adapter", "mcp"} <= set(pins)
    assert pins == _pyproject_pins(), "reinstall the package after editing pyproject.toml"


def test_installed_versions_match_the_declared_pins():
    assert check_pins() == []


def test_readme_badges_match_the_pins_and_protocol_versions():
    from uagents_core.contrib.protocols.chat import chat_protocol_spec
    from uagents_core.contrib.protocols.payment import payment_protocol_spec

    readme = Path("README.md").read_text(encoding="utf-8")
    assert f"badge/uAgents-{declared_pins()['uagents']}-" in readme
    assert f"badge/Agent_Chat_Protocol-{chat_protocol_spec.version}-" in readme
    assert f"badge/Agent_Payment_Protocol-{payment_protocol_spec.version}-" in readme
