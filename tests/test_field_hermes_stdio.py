"""Field integration test against a real hermes-agent install.

Skipped unless both env vars are set:

  HERMES_FETCH_FIELD_TEST=1
  HERMES_FETCH_HERMES_PYTHON=/path/to/hermes-venv/bin/python

Operator setup (one time). hermes-agent only supports installs from a
checkout. Use the Python version its checkout names in .python-version (3.11
for the 0.21.5 release, 3.14 for main); on an older interpreter its
dependencies are skipped and the tools server fails to start:

  uv venv -p <version> /tmp/hermes-venv
  uv pip install --python /tmp/hermes-venv/bin/python -e "<hermes-agent checkout>[mcp]"
  mkdir -p $HERMES_HOME/skills && copy at least one bundled skill there

CI's hermes-plugin job runs this against Hermes 0.21.5 and a pinned main.

Callers must follow the served inputSchema. hermes-agent v0.16.x wrapped
every tool's arguments in one required ``kwargs`` object; newer releases
(mcp 2.0 based) serve flat parameters. ``_args_for`` handles both.
"""

import os

import pytest
from uagents.dispatch import dispatcher
from uagents_adapter.mcp.protocol import (
    CallTool,
    CallToolResponse,
    ListTools,
    ListToolsResponse,
)

from hermes_fetch_ai.config import HERMES_PYTHON_VAR, load_config
from hermes_fetch_ai.direct_protocol import replay_args
from hermes_fetch_ai.mcp_shim import HermesMCPClientShim
from hermes_fetch_ai.uagent_app import build_agent, local_dispatch_request

pytestmark = pytest.mark.skipif(
    os.environ.get("HERMES_FETCH_FIELD_TEST") != "1"
    or not os.environ.get("HERMES_FETCH_HERMES_PYTHON"),
    reason="field test requires HERMES_FETCH_FIELD_TEST=1 and HERMES_FETCH_HERMES_PYTHON",
)


def _args_for(tool, flat_args):
    """Shape arguments the way the served inputSchema expects."""
    if "kwargs" in (tool["inputSchema"].get("required") or []):
        return {"kwargs": flat_args}
    return flat_args


def _field_cfg(tmp_path, monkeypatch):
    # The production config requires a stable identity; use test-only material.
    monkeypatch.setenv("UAGENT_SEED", "field-test-" + "identity-material-not-a-real-seed")
    # Hand over Hermes' interpreter the way the fetchai-bridge plugin does, so the
    # example config's unset `command` resolves to it.
    monkeypatch.setenv(HERMES_PYTHON_VAR, os.environ["HERMES_FETCH_HERMES_PYTHON"])
    cfg = load_config("examples/hermes-stdio.yaml")
    cfg.logging.audit_path = str(tmp_path / "field-audit.jsonl")
    return cfg


@pytest.mark.asyncio
async def test_real_hermes_roundtrip_policy_and_skills_list(tmp_path, monkeypatch):
    cfg = _field_cfg(tmp_path, monkeypatch)
    # Startup raises HermesBackendError if the Hermes tools server is unusable.
    async with HermesMCPClientShim(cfg) as shim:
        inventory = {t["name"] for t in await shim.list_tools()}
        assert "skills_list" in inventory

        bridge = build_agent(cfg, shim)
        client_cfg = cfg.model_copy(deep=True)
        client_cfg.agent.name += "_client"
        client_cfg.agent.dev_random_seed = True  # distinct, ephemeral client identity
        client = build_agent(client_cfg, shim)
        try:
            listed = await local_dispatch_request(
                bridge, client, ListTools(), ListToolsResponse, timeout=30
            )
            visible = {t["name"] for t in (listed.tools or [])}
            # Behavior contract: an unknown sender sees exactly the public
            # subset of whatever the live server actually serves.
            assert visible == {"skills_list"} & inventory

            skills_tool = next(t for t in listed.tools if t["name"] == "skills_list")

            call = await local_dispatch_request(
                bridge,
                client,
                CallTool(tool="skills_list", args=replay_args(_args_for(skills_tool, {}))),
                CallToolResponse,
                timeout=60,
            )
            assert call.error is None
            assert '"success": true' in str(call.result)

            denied = await local_dispatch_request(
                bridge,
                client,
                # Denied by policy before any schema check, so the shape is irrelevant.
                CallTool(tool="web_search", args=replay_args({"query": "x"})),
                CallToolResponse,
                timeout=30,
            )
            assert denied.result is None and denied.error
        finally:
            dispatcher.unregister(bridge.address, bridge)
            dispatcher.unregister(client.address, client)

    audit_lines = (tmp_path / "field-audit.jsonl").read_text().strip().splitlines()
    assert len(audit_lines) >= 6
