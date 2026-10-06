"""Call a running bridge from another uAgent: list its tools, then call echo.

Start a bridge with fake tools (no Hermes, no secrets) and note the address it logs:

    hermes-fetch-ai serve --config examples/local-direct.yaml
    # INFO: [hermes_fetch_local]: Starting agent with address: agent1q...

Then, in another terminal:

    python examples/call_bridge.py agent1q... http://127.0.0.1:8001/submit

Against a Hermes-backed bridge, call a tool it exposes, such as skills_list
with no arguments. The client signs with a throwaway identity, so the bridge
sees an unknown sender and offers only its public tools.
"""

from __future__ import annotations

import argparse
import asyncio

from uagents.communication import send_sync_message
from uagents.resolver import RulesBasedResolver
from uagents_adapter.mcp.protocol import CallTool, CallToolResponse, ListTools, ListToolsResponse

from hermes_fetch_ai.direct_protocol import replay_args


async def main(address: str, endpoint: str, tool: str, text: str | None) -> None:
    # Reach the bridge at a known endpoint instead of looking it up in the Almanac.
    resolver = RulesBasedResolver({address: endpoint})

    listed = await send_sync_message(
        address, ListTools(), response_type=ListToolsResponse, resolver=resolver, timeout=20
    )
    if not isinstance(listed, ListToolsResponse):
        raise SystemExit(f"no ListTools response: {listed}")
    print("tools:", [t["name"] for t in listed.tools or []])

    # Every call carries replay-protection metadata: a fresh request ID and issue time.
    args = replay_args({} if text is None else {"text": text})
    called = await send_sync_message(
        address,
        CallTool(tool=tool, args=args),
        response_type=CallToolResponse,
        resolver=resolver,
        timeout=20,
    )
    if not isinstance(called, CallToolResponse):
        raise SystemExit(f"no CallTool response: {called}")
    print("result:", called.result)
    print("error:", called.error)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("address", help="the bridge's agent address (agent1q...)")
    parser.add_argument("endpoint", help="for example http://127.0.0.1:8001/submit")
    parser.add_argument("--tool", default="echo")
    parser.add_argument("--text", default="hello", help="the text argument; '' sends no arguments")
    options = parser.parse_args()
    asyncio.run(main(options.address, options.endpoint, options.tool, options.text or None))
