# Fetch.ai uAgents / Agentverse / Almanac / MCP adapter research

Date accessed: 2026-05-16
Scope: current public Fetch.ai uAgents APIs, Agentverse, Almanac, mailbox/proxy/endpoint modes, credentials/registration, and examples relevant to exposing an MCP server as a uAgent.

## Key package/version facts

- `uagents` latest on PyPI: 0.24.2, uploaded 2026-04-17, Python `>=3.10,<4.0`, summary "Lightweight framework for rapid agent-based development". Project URLs point to docs and `https://github.com/fetchai/uAgents`.
  Source: https://pypi.org/project/uagents/ and JSON API https://pypi.org/pypi/uagents/json
- `uagents-core` latest on PyPI: 0.4.4, uploaded 2026-02-26, Python `>=3.10,<4.0`.
  Source: https://pypi.org/project/uagents-core/ and https://pypi.org/pypi/uagents-core/json
- `uagents-adapter` latest on PyPI: 0.6.2, uploaded 2025-10-21, Python `>=3.10,<4.0`, summary "Adapters for uAgents to integrate with LangChain, CrewAI, MCP, and A2A". It has no PyPI project URLs in metadata.
  Source: https://pypi.org/project/uagents-adapter/ and https://pypi.org/pypi/uagents-adapter/json
- `mcp` Python SDK latest on PyPI: 1.27.1, uploaded 2026-05-08, Python `>=3.10`, summary "Model Context Protocol SDK".
  Source: https://pypi.org/project/mcp/ and https://pypi.org/pypi/mcp/json
- `uagents` 0.24.2 dependencies from wheel metadata: `uagents-core>=0.4.3`, `pydantic>=2.8,<3.0`, `uvicorn>=0.30.1,<1.0`, `aiohttp>=3.8.3,<4.0`, `cosmpy>=0.11.0,<0.12.0`; optional extras include `fetchai-babble>=0.4.5` for wallet and `litellm>=1.78.6,<2.0` for LLM.
- `uagents-adapter` 0.6.2 dependencies from wheel metadata: always `click`, `httpx`, `openai`, `pydantic`, `python-dotenv`, `requests`, `uagents>=0.22.3`, `uvicorn`; extras include `mcp>=1.8.1` for `mcp`, LangChain/CrewAI/A2A extras. Pinning `uagents==0.24.2`, `uagents-core==0.4.4`, `uagents-adapter==0.6.2`, `mcp==1.27.1` is the safest reproducible baseline.
- Public GitHub `main` currently has `python/pyproject.toml` version `uagents` 0.24.2, while latest GitHub release is `core@0.4.5b2` (published 2026-05-14), a beta core release. This is a version-risk signal: avoid unpinned prereleases and test against exact PyPI versions.
  Sources: https://github.com/fetchai/uAgents, https://raw.githubusercontent.com/fetchai/uAgents/main/python/pyproject.toml, https://github.com/fetchai/uAgents/releases/tag/core%400.4.5b2

## Stable-looking uAgents API surface

Official docs use these imports and patterns repeatedly:

```python
from uagents import Agent, Context, Model, Protocol

class Message(Model):
    message: str

agent = Agent(
    name="alice",
    seed="secret_seed_phrase",
    port=8000,
    endpoint=["http://localhost:8000/submit"],
)

@agent.on_message(model=Message)
async def handler(ctx: Context, sender: str, msg: Message):
    await ctx.send(sender, Message(message="reply"))

if __name__ == "__main__":
    agent.run()
```

Docs sources:
- Quickstart: https://uagents.fetch.ai/docs/quickstart
- Create an Agent: https://uagents.fetch.ai/docs/getting-started/create
- Communication: https://uagents.fetch.ai/docs/guides/communication
- Protocols: https://uagents.fetch.ai/docs/guides/protocols

In 0.24.2 source, `Agent.__init__` accepts: `name`, `port`, `seed`, `endpoint`, `agentverse`, `mailbox`, `proxy`, `resolve`, `registration_policy`, wallet messaging options, `version`, `network='mainnet'`, `enable_agent_inspector=True`, `metadata`, `readme_path`, `description`, `handle`, `avatar_url`, `publish_agent_details=True`, message-history/concurrency/shutdown options. This is more current than many examples that show older versions.
Source: https://raw.githubusercontent.com/fetchai/uAgents/main/python/src/uagents/agent.py

## Agent identity, seed, wallet/security

- uAgents derive a cryptographic agent address/identity from the `seed`; without a fixed seed, docs say random addresses are generated on each run. For discoverable/persistent agents, use a stable seed.
- Docs warn: anyone with the seed phrase can impersonate the agent and access the agent wallet. Treat it like a private key, load from secrets/env, never commit it, and rotate by creating a new agent address.
- Agent addresses are `agent...` on mainnet; source also defines `test-agent` prefix for testnet and `fetch` ledger prefix.
Sources:
- Seed phrase docs: https://uagents.fetch.ai/docs/getting-started/seed
- Address docs: https://uagents.fetch.ai/docs/getting-started/address
- Source config constants: https://raw.githubusercontent.com/fetchai/uAgents/main/python/src/uagents/config.py

## Registration and discovery: Almanac and Agentverse

- When a uAgent runs with endpoints or mailbox/proxy, docs show automatic registration logs: `Registration on Almanac API successful`, `Registering on almanac contract...complete`, and an Agent Inspector URL on `https://agentverse.ai/inspect/...`.
- 0.24.2 source has two registration paths:
  - `AlmanacApiRegistrationPolicy.register()` posts a signed `AgentRegistrationAttestation` to `{almanac_api}/agents` containing `agent_identifier`, protocols, endpoints, and metadata.
  - Contract registration uses configured mainnet/testnet Almanac contracts. `config.py` has `ALMANAC_CONTRACT_VERSION = "2.2.0"`, registration update interval 3600s, retry interval 60s, and default Almanac API from `AgentverseConfig().almanac_api`.
- Resolver source resolves through Almanac API and Name Service and validates prefixes `agent`, `test-agent`, or empty.
Sources:
- Create Agent output example: https://uagents.fetch.ai/docs/getting-started/create
- Communication remote/Almanac: https://uagents.fetch.ai/docs/guides/communication
- Registration source: https://raw.githubusercontent.com/fetchai/uAgents/main/python/src/uagents/registration.py
- Resolver source: https://raw.githubusercontent.com/fetchai/uAgents/main/python/src/uagents/resolver.py
- Config source: https://raw.githubusercontent.com/fetchai/uAgents/main/python/src/uagents/config.py

## Endpoint, mailbox, and proxy modes

Endpoint/self-hosted mode:
- Docs use `endpoint=["http://127.0.0.1:8000/submit"]` or `http://localhost:8000/submit` with `port=8000` for direct HTTP envelope delivery.
- `parse_endpoint_config()` in 0.24.2 accepts string, list, dict-with-weight, `mailbox=True`, or `proxy=True`; explicit `endpoint` overrides mailbox/proxy settings.
- This is best for local two-agent demos and self-hosted public deployments where the endpoint is reachable by other agents.
Sources: https://uagents.fetch.ai/docs/quickstart, https://uagents.fetch.ai/docs/guides/run_local_agents, https://raw.githubusercontent.com/fetchai/uAgents/main/python/src/uagents/config.py

Mailbox mode:
- Official mailbox docs define Agentverse Mailbox as a middleman that temporarily stores communications; agents collect messages when online. It is intended for agents behind firewalls or not always online.
- Code path is simply `Agent(name="alice", seed="...", port=8000, mailbox=True)`. Logs show `Starting mailbox client for https://agentverse.ai`, `Mailbox access token acquired`, and `Successfully registered as mailbox agent in Agentverse` after connecting through Inspector.
- Docs note each local agent needs its own dedicated mailbox.
Source: https://uagents.fetch.ai/docs/agentverse/mailbox

Proxy mode:
- Docs show `Agent(name="alice", seed="...", proxy=True)` and then Agent Inspector connection flow where user selects Proxy and supplies a public URL/IP where the agent is accessible.
- Proxy is described as improving Agentverse marketplace ranking/search by tracking operation/visibility. It assumes the local agent has a public URL or IP; mailbox is more appropriate for NAT/firewall/offline tolerance.
Source: https://uagents.fetch.ai/docs/agentverse/proxy

Agentverse credentials/registration:
- Mailbox source uses `AgentverseConnectRequest(user_token, agent_type, endpoint=None, team=None)`, fetches a challenge from `{identity_api}/{identity.address}/challenge`, signs/proves identity, and uses `Authorization: Bearer {user_token}` plus optional `x-team` header.
- Architecture implication: local agent seed proves agent identity; Agentverse user token authorizes linking/publishing in the user's Agentverse account/team. Do not store the Agentverse token in repo or logs.
Source: https://raw.githubusercontent.com/fetchai/uAgents/main/python/src/uagents/mailbox.py

## MCP server as a uAgent: closest public package path

`uagents-adapter` 0.6.2 includes `uagents_adapter.mcp` in the wheel:
- Public exports: `MCPServerAdapter`, `ListTools`, `ListToolsResponse`, `CallTool`, `CallToolResponse`.
- `MCPServerAdapter(mcp_server, asi1_api_key, model, asi1_base_url="https://api.asi1.ai/v1")` creates two protocols:
  - `MCPProtocol` version `0.1.0`: `ListTools -> ListToolsResponse`, `CallTool -> CallToolResponse`.
  - `AgentChatProtocol` version `0.3.0`, using `uagents_core.contrib.protocols.chat`.
- Direct MCP protocol handlers call `await self.mcp.list_tools()` and `await self.mcp.call_tool(tool, args)` and return uAgent messages.
- Chat handler receives Agentverse chat messages, calls ASI:One Chat Completions with OpenAI-compatible `tools`, requires a tool choice, executes the selected MCP tool, then sends the final answer back as `ChatMessage`.
- `run(agent)` starts `agent.run()` in a daemon thread and then calls `self.mcp.run(transport="stdio")`.
Source: PyPI wheel source for `uagents-adapter==0.6.2`; package page https://pypi.org/project/uagents-adapter/

The adapter wheel contains an MCP README with this minimal shape:

```python
from mcp.server.fastmcp import FastMCP
from uagents import Agent
from uagents_adapter import MCPServerAdapter

mcp = FastMCP("weather")

@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location."""
    return "..."

mcp_adapter = MCPServerAdapter(
    mcp_server=mcp,
    asi1_api_key="your-asi1-api-key",
    model="asi1-fast",  # README lists asi1-mini, asi1-extended, asi1-fast
)

agent = Agent()
for protocol in mcp_adapter.protocols:
    agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    mcp_adapter.run(agent)
```

Important caveat: the README example uses `agent = Agent()` with no seed/mailbox/endpoint. For a real discoverable Hermes/MCP bridge, supply `name`, stable `seed`, and either `mailbox=True` for local/NAT demos or a public `endpoint`/`proxy=True` for production discoverability.

## Recommended E2E demo path for local/no-paid baseline

No-paid/local transport demo:
1. Create FastMCP server with a harmless local tool, e.g. echo/time/fileless calculation.
2. Create a uAgent with stable dev seed, `port=8000`, and direct endpoint `http://127.0.0.1:8000/submit`.
3. Include `MCPServerAdapter.protocols` with `publish_manifest=True`.
4. Start a second local uAgent client that sends `ListTools` then `CallTool` to the MCP-uAgent address. This exercises uAgents local HTTP/Almanac registration and the adapter's direct MCP protocol without ASI:One API key dependency.

Agentverse chat demo:
1. Same MCP server and adapter.
2. Use `Agent(name="hermes-mcp", seed=os.environ["UAGENT_SEED"], port=8000, mailbox=True, publish_agent_details=True, description=..., readme_path=...)`.
3. Provide `ASI1_API_KEY` to `MCPServerAdapter` if using the adapter's chat-to-tool path.
4. Run locally, open Agent Inspector URL, connect via Mailbox, then chat from Agentverse/ASI UI.

Production-ish demo:
- Use a public HTTPS endpoint/proxy rather than mailbox if low latency and always-on service are required. Keep mailbox as fallback for laptops/NAT/offline demos.

## Architecture/security notes for Hermes MCP exposure

- Separate trust boundaries:
  - uAgent identity seed: cryptographic identity and wallet; secret.
  - Agentverse user token/mailbox access token: account/linking credential; secret.
  - ASI:One API key: model/tool-selection service credential; secret and billable/ratelimited if applicable.
  - MCP server tools: high-risk execution boundary; expose only whitelisted tools.
- Do not expose arbitrary Hermes Agent CLI abilities directly as MCP tools without policy enforcement. Add allowlists, parameter schemas, per-tool timeouts, max output sizes, concurrency limits, audit logs, and confirmation gates for side-effecting tools.
- Validate all `CallTool.args` with schema-level and application-level checks; uAgent message models only ensure envelope shape, not business authorization.
- Treat incoming uAgent messages as untrusted even when signed. Verify sender allowlists for admin tools; keep public tools read-only where possible.
- The adapter's chat path logs user messages, available tool schemas, raw LLM responses, selected tools, and tool responses. Scrub secrets and consider disabling verbose logs in production.
- `MCPServerAdapter` uses synchronous `requests.post` inside async handlers, which can block the event loop under load. For production, consider a fork/wrapper using `httpx.AsyncClient`, timeouts, retries, circuit breakers, and bounded task queues.
- Adapter direct `CallToolResponse.result` is a string; large/binary/structured MCP outputs should be summarized or stored out-of-band with references.
- `mcp_adapter.run()` combines agent thread plus stdio MCP server run. For embedding an existing Hermes MCP server, evaluate whether importing a FastMCP instance is feasible; if the server is a separate process, a custom adapter using MCP client sessions may be cleaner than the packaged adapter's in-process assumption.

## API stability/version risks

- uAgents docs are current-looking and most pages show "Last updated on January 19, 2026", but some docs examples still include old dependency snippets such as `uagents ^0.13.0` in Docker guide. Prefer PyPI/source over example pins.
- GitHub latest release is a beta core release (`core@0.4.5b2`) newer than stable PyPI `uagents-core 0.4.4`; avoid prerelease drift.
- `uagents-adapter` has no official repo URL in PyPI metadata and MCP protocol version is `0.1.0`; treat it as less stable than core `uagents`.
- Adapter README says "Model Control Protocol" although current MCP is "Model Context Protocol"; another signal that adapter docs may lag terminology.
- Adapter depends on `mcp>=1.8.1` while current SDK is 1.27.1. The FastMCP APIs may have changed; pin and run integration tests.
- Agentverse Mailbox/Proxy flows rely on hosted `https://agentverse.ai` and browser Inspector. Local direct endpoint mode avoids paid/hosted feature assumptions for CI, but discovery/chat marketplace testing requires Agentverse availability and login.

## Most relevant official/public URLs

- uAgents docs home: https://uagents.fetch.ai/docs/quickstart
- Install/create: https://uagents.fetch.ai/docs/getting-started/create
- Seed: https://uagents.fetch.ai/docs/getting-started/seed
- Address: https://uagents.fetch.ai/docs/getting-started/address
- Communication/Almanac: https://uagents.fetch.ai/docs/guides/communication
- Protocols: https://uagents.fetch.ai/docs/guides/protocols
- Local agents/Docker: https://uagents.fetch.ai/docs/guides/run_local_agents
- Mailbox: https://uagents.fetch.ai/docs/agentverse/mailbox
- Proxy: https://uagents.fetch.ai/docs/agentverse/proxy
- ASI chat-protocol example: https://uagents.fetch.ai/docs/examples/asi-1
- uAgents PyPI: https://pypi.org/project/uagents/
- uAgents-core PyPI: https://pypi.org/project/uagents-core/
- uAgents-adapter PyPI: https://pypi.org/project/uagents-adapter/
- MCP Python SDK PyPI: https://pypi.org/project/mcp/
- uAgents GitHub: https://github.com/fetchai/uAgents
