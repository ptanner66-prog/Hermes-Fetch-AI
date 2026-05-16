# Fetch uAgents Surface

Date accessed: 2026-05-16

## Package baseline

Live PyPI metadata verified:

- `uagents==0.24.2`, Python `>=3.10,<4.0`, repo `https://github.com/fetchai/uAgents`.
- `uagents-core==0.4.4`, Python `>=3.10,<4.0`.
- `uagents-adapter==0.6.2`, Python `>=3.10,<4.0`, summary says adapters for LangChain, CrewAI, MCP, and A2A.
- `mcp==1.27.1`, Python `>=3.10`.

Recommended reproducible bridge pins:

```text
uagents==0.24.2
uagents-core==0.4.4
uagents-adapter==0.6.2
mcp==1.27.1
python-dotenv>=1
pydantic>=2.8,<3
```

Avoid prerelease drift. The local clone of `fetchai/uAgents` is at commit `6d7008971eaff74e0a0ca564c19d666f5047ef1a`; GitHub releases show newer beta core tags than stable PyPI.

## Stable-looking uAgent API

Official docs and source use this shape:

```python
from uagents import Agent, Context, Model, Protocol

class Message(Model):
    message: str

agent = Agent(
    name="hermes_fetch_ai",
    seed=os.environ["UAGENT_SEED"],
    port=8000,
    endpoint=["http://127.0.0.1:8000/submit"],
)

@agent.on_message(model=Message)
async def handler(ctx: Context, sender: str, msg: Message):
    await ctx.send(sender, Message(message="reply"))

agent.run()
```

Official docs:

- Quickstart: https://uagents.fetch.ai/docs/quickstart
- Create: https://uagents.fetch.ai/docs/getting-started/create
- Communication: https://uagents.fetch.ai/docs/guides/communication
- Protocols: https://uagents.fetch.ai/docs/guides/protocols

Source `python/src/uagents/agent.py` in `0.24.2` accepts many production-relevant init fields: `name`, `port`, `seed`, `endpoint`, `agentverse`, `mailbox`, `proxy`, `resolve`, `registration_policy`, wallet messaging options, `version`, `network`, `enable_agent_inspector`, metadata/readme/description/handle/avatar, and publish flags.

## Identity, seeds, and addresses

- Seed controls cryptographic identity/address. Stable public agents need stable seeds.
- Anyone with the seed can impersonate the agent and access wallet-linked identity. Treat as a private key.
- Agent addresses are identity and routing handles, not authorization.
- Source config defines mainnet `agent...`, testnet `test-agent...`, and ledger prefixes.

Docs:

- Seed: https://uagents.fetch.ai/docs/getting-started/seed
- Address: https://uagents.fetch.ai/docs/getting-started/address
- Source: `python/src/uagents/config.py`

## Registration and discovery

uAgents can register endpoints/protocols with Almanac and expose agents through Agentverse/Inspector.

Source paths:

- `python/src/uagents/registration.py`: API registration posts signed `AgentRegistrationAttestation` to Almanac API; contract registration uses configured contract/version and retries/intervals.
- `python/src/uagents/resolver.py`: resolves through Almanac API and Name Service, validating address prefixes.
- `python/src/uagents/config.py`: contains default Agentverse/Almanac config and `ALMANAC_CONTRACT_VERSION = "2.2.0"`.

Docs:

- Create output and Inspector logs: https://uagents.fetch.ai/docs/getting-started/create
- Remote communication/Almanac: https://uagents.fetch.ai/docs/guides/communication

Bridge rule: Almanac/Agentverse discovery proves where to send envelopes and what protocol manifests an address advertises. It does not prove the sender should be allowed to invoke a Hermes tool.

## Endpoint, mailbox, and proxy modes

### Direct endpoint

Docs use local endpoints such as `http://127.0.0.1:8000/submit` or `http://localhost:8000/submit` with `port=8000`. Source `parse_endpoint_config()` accepts strings, lists, weighted dictionaries, `mailbox=True`, or `proxy=True`.

Use for:

- CI/local E2E.
- Two local agents.
- Self-hosted public endpoint when reachable over HTTPS.

### Mailbox mode

Docs: https://uagents.fetch.ai/docs/agentverse/mailbox

Mailbox is a store-and-forward middleman in Agentverse for agents behind firewalls or not always online. Code path is `Agent(..., mailbox=True)`. Logs should show Agentverse mailbox client startup, access token acquisition, and mailbox registration after Inspector linking.

Use for:

- CEO/laptop/NAT demo.
- Agentverse visibility without public inbound networking.

Requirements:

- Stable seed.
- Agentverse account/login flow and mailbox token. Never commit or log token.
- Dedicated mailbox per local agent.

### Proxy mode

Docs: https://uagents.fetch.ai/docs/agentverse/proxy

Proxy mode uses `Agent(..., proxy=True)` and assumes a public URL/IP supplied through Agent Inspector. Docs describe it as useful for visibility/marketplace ranking/search.

Use later for:

- Always-on deployed bridge with public HTTPS endpoint.
- Not required for v1 CI or first local demo.

## uagents-adapter MCP rail

`uagents-adapter==0.6.2` contains `uagents_adapter.mcp` and exports:

- `MCPServerAdapter`
- `ListTools`
- `ListToolsResponse`
- `CallTool`
- `CallToolResponse`

Adapter source at `python/uagents-adapter/src/uagents_adapter/mcp/adapter.py` proves:

- `MCPServerAdapter.__init__(mcp_server, asi1_api_key, model, asi1_base_url=...)` stores a Python object, not a transport config.
- Direct MCP protocol handler receives `sender`, but current `uagents-adapter==0.6.2` calls `await self.mcp.list_tools()` and `await self.mcp.call_tool(...)` without passing sender to the MCP object. Therefore a sender-blind shim cannot enforce sender-aware authorization.
- `MCPServerAdapter.protocols` returns both direct MCP and chat protocols. V1 should publish only a bridge-owned policy-aware direct protocol by default; chat must be explicit opt-in.
- Direct MCP protocol handler calls `await self.mcp.call_tool(msg.tool, msg.args)`.
- Chat protocol converts MCP tools to OpenAI/ASI tool schemas and calls ASI:One chat completions.
- `run(agent)` starts `agent.run()` in a daemon thread and then calls `self.mcp.run(transport="stdio")`.

Conclusion: the adapter already provides most of the uAgent/MCP bridge, but only for an in-process FastMCP-like object. It does not directly wrap a stdio command, SSE URL, or streamable HTTP URL.

## ASI:One / Chat Protocol

The adapter's chat path is optional for v1. It requires `asi1_api_key` and an ASI model such as `asi1-mini`, `asi1-fast`, or `asi1-extended` per adapter README examples. It receives Agentverse chat messages, asks ASI:One to choose a tool, calls the MCP tool, then sends a final chat response.

Risks:

- Adds model-service credential and hosted service dependency.
- Adapter uses synchronous `requests.post` in async handler, which can block the event loop under load.
- Chat logs may include user messages, tool schemas, raw model responses, selected tools, and tool responses. Redaction and log-level defaults matter.

V1 rule: support direct uAgent `ListTools`/`CallTool` without ASI through a bridge-owned policy-aware protocol. Document chat as optional demo and do not publish it unless explicitly enabled and keyed.

## Inbound/outbound message flow

Inbound direct protocol:

1. Remote sender knows or discovers bridge agent address and MCP protocol manifest.
2. Remote sends signed/routed uAgent envelope to endpoint/mailbox/proxy.
3. uAgents runtime dispatches to bridge-owned policy-aware direct protocol handler.
4. Handler treats sender as untrusted identity and applies sender-filtered inventory/authorization before shim access.
5. On allow, handler calls Hermes MCP shim over stdio/HTTP/SSE as configured; on deny, it returns safe error and records audit without MCP invocation.
6. Result is normalized to direct protocol response model.
7. uAgents runtime sends response back to sender.

Outbound from Hermes/bridge:

- v1 only sends responses to direct requests.
- Proactive outbound messages should be deferred unless a demo requires them, because they add scheduling, consent, and spam/abuse concerns.

## Required, optional, deferred rails

Required for v1:

- uAgent identity from stable seed.
- Direct endpoint mode for local tests.
- Adapter `ListTools`/`CallTool` protocol.
- Hermes MCP shim.
- Almanac/manifest publication where local network allows it, but test should not rely on hosted success.

Optional for demo:

- Agentverse Mailbox.
- Agent Inspector linking.
- ASI:One chat flow.
- Public HTTPS endpoint/proxy.

Deferred:

- Payments/billing/marketplace pricing.
- Wallet UX beyond seed/address identity handling.
- Per-skill commercial manifests.
- Complex multi-agent marketplace strategy.
- Any domain-specific use case examples.
