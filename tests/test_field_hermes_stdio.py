"""Field integration test against a real hermes-agent install.

Skipped unless both env vars are set:

  HERMES_FETCH_FIELD_TEST=1
  HERMES_FETCH_HERMES_PYTHON=/path/to/hermes-venv/bin/python

Operator setup (one time):

  python -m venv /tmp/hermes-venv
  /tmp/hermes-venv/bin/pip install -e "<hermes-agent checkout>[mcp]"
  mkdir -p $HERMES_HOME/skills && copy at least one bundled skill there

The hermes tools MCP server wraps every tool's arguments in a single
required ``kwargs`` object (its FastMCP handlers take ``**kwargs``), so
callers must follow the served inputSchema: ``args={"kwargs": {...}}``.
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

from hermes_fetch_ai.config import load_config
from hermes_fetch_ai.mcp_shim import HermesMCPClientShim
from hermes_fetch_ai.uagent_app import build_agent, local_dispatch_request

pytestmark = pytest.mark.skipif(
    os.environ.get("HERMES_FETCH_FIELD_TEST") != "1"
    or not os.environ.get("HERMES_FETCH_HERMES_PYTHON"),
    reason="field test requires HERMES_FETCH_FIELD_TEST=1 and HERMES_FETCH_HERMES_PYTHON",
)


def _field_cfg(tmp_path):
    cfg = load_config("examples/hermes-stdio.yaml")
    cfg.hermes_mcp.command = os.environ["HERMES_FETCH_HERMES_PYTHON"]
    cfg.logging.audit_path = str(tmp_path / "field-audit.jsonl")
    return cfg


@pytest.mark.asyncio
async def test_real_hermes_roundtrip_policy_and_skills_list(tmp_path):
    cfg = _field_cfg(tmp_path)
    async with HermesMCPClientShim(cfg) as shim:
        assert shim._startup_error is None, f"hermes MCP startup failed: {shim._startup_error}"

        inventory = {t["name"] for t in await shim.list_tools()}
        assert "skills_list" in inventory

        bridge = build_agent(cfg, shim)
        client_cfg = cfg.model_copy(deep=True)
        client_cfg.agent.name += "_client"
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
            assert "kwargs" in (skills_tool["inputSchema"].get("required") or [])

            call = await local_dispatch_request(
                bridge,
                client,
                CallTool(tool="skills_list", args={"kwargs": {}}),
                CallToolResponse,
                timeout=60,
            )
            assert call.error is None
            assert '"success": true' in str(call.result)

            denied = await local_dispatch_request(
                bridge,
                client,
                CallTool(tool="web_search", args={"kwargs": {"query": "x"}}),
                CallToolResponse,
                timeout=30,
            )
            assert denied.result is None and denied.error
        finally:
            dispatcher.unregister(bridge.address, bridge)
            dispatcher.unregister(client.address, client)

    audit_lines = (tmp_path / "field-audit.jsonl").read_text().strip().splitlines()
    assert len(audit_lines) >= 6
