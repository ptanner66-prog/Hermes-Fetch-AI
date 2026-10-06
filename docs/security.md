# Security

Hermes Fetch AI puts part of a local Hermes install on an agent network, so it is conservative by default: a small surface, default deny, replay protection, bounded resources, and a redacted audit log.

## Threat model

Remote senders may:

- enumerate tools to learn what the local install can do;
- replay signed `CallTool` messages;
- rotate sender identities to get around per-sender rate limits;
- submit expensive or sensitive tool calls;
- pass unsupported URL schemes, private or local URLs, shell-control characters, oversized payloads, or schema-invalid arguments;
- trigger outputs that contain secrets or very large content;
- try to exploit the subprocess transport, for example through its environment or stderr.

## Controls

- Tool calls are default-deny, and the denylist wins over allowlists and public tools.
- A verified signature proves which agent address sent a message (uAgents checks every envelope) but grants nothing by itself: an address can call a tool only if the tool is in `public_tools` or listed for that address in `allowed_senders`.
- `ListTools` is filtered, size-capped, and rate-limited per sender and globally.
- `CallTool` is rate-limited per sender and globally before any expensive work. A request only counts against the global limit once it passes the sender's own, so one sender cannot lock others out.
- `CallTool` requires replay-protection metadata by default, under the reserved argument key `_hermes_fetch_ai`:
  - `request_id` must be unique per sender while the call could still be accepted;
  - `issued_at_ms` must be a finite number, no older than `replay_ttl_seconds` and no further ahead than `max_replay_clock_skew_seconds`;
  - duplicate, stale, future-dated, malformed, or oversized calls are denied before the tool runs;
  - accepted request IDs are remembered for `replay_ttl_seconds + max_replay_clock_skew_seconds`, the longest time a copy could still pass the freshness check;
  - a schema-invalid call does not use up its request ID, so a corrected retry works.
- Tool names must be plain ASCII identifiers of at most 128 characters, so a displayed name is always the authorized one. Policy names are checked when the config loads.
- Arguments are size-capped and validated against the tool's JSON schema.
- URL checks:
  - only `http` and `https` are allowed; `file:`, `data:`, `javascript:`, `ftp://` and hostless URLs are rejected;
  - a string counts as a URL when it starts with `scheme:/`, with `http:` or `https:` (even without slashes), or with a non-hierarchical scheme such as `data:`; ordinary text such as `Note: hello` is not a URL;
  - URLs embedded in longer text (`see http://10.0.0.1/admin`) are checked too, as are strings that are only a local or IP host (`localhost:8080`, `169.254.169.254/latest`, `[::1]:80`, `127.1/admin`);
  - IPv4 literals are parsed the way the C library parses them, so encodings such as `0x7f.0.0.1`, `0177.0.0.1`, `127.1` and `2130706433` are recognized;
  - URLs with backslashes, whitespace, or control characters are rejected, because URL parsers disagree about them;
  - targets that are local, private, link-local, multicast, unspecified, reserved, or shared (CGNAT) are rejected, both as literals and after DNS resolution;
  - DNS lookups run off the event loop, after the cheap checks, at most once per host, for at most 16 hosts per call, and within `hermes_mcp.timeout_seconds`.
- Shell control characters (including newlines) and shell metacharacters (`; & | $ < > \` and backticks) are rejected unless the tool is listed in `policy.trusted_shell_tools`. This is strict on purpose: it also rejects URLs whose query string contains `&`, and multi-line text. List a tool there only if it never passes arguments to a shell.
- Tool responses are size-capped. They are not redacted, so expose only tools whose output is safe for the caller.
- Audit records hold only an allowlist of fields (no arguments, outputs, full sender addresses, seeds, tokens, or keys). Each value is redacted before the record is written, so caller-supplied text cannot corrupt the log.
- Backend transport errors reach the caller as `tool call failed`; the details go to the bridge's log.
- The tools server runs with `shell=False`, a short environment allowlist (`PATH`, `HOME`, `TMPDIR`, `HERMES_HOME`, locale), and its stderr discarded, because stderr is outside the redaction boundary.
- With `publish_manifest: false` the bridge makes no outbound calls of its own. uAgents looks up the Almanac contract on the Fetch ledger whenever an agent is created, and reports every agent as active or inactive to Agentverse's Almanac API even with registration disabled; the bridge's `PrivateAgent` skips both. Replying to a remote agent can still look up that agent's endpoint in the Almanac.
- Production seeds come only from `UAGENT_SEED` and must be at least 32 characters. Config files are scanned for credential-shaped values anywhere, including inside lists such as `hermes_mcp.args`: bearer tokens, `sk-`/`pk-` keys, JWTs, long hex keys, `token=...`-style assignments, and flags such as `--api-key`. Ordinary words such as "token" in a description are allowed.
- In mailbox mode, the uAgents Agent Inspector endpoints (`/connect`, `/disconnect`) are unauthenticated. Keep the port firewalled and disable the inspector after connecting; see [`agentverse-mailbox.md`](agentverse-mailbox.md).

## Hermes boundary

The bridge uses Hermes' tools MCP server (`agent.transports.hermes_tools_mcp_server`) and nothing else. That server never serves terminal, file, process, messaging, or approval tools, so the bridge cannot expose them even if a config allowlists them. Of what it does serve (web, browser, vision, image, text-to-speech, skills, kanban), only `skills_list` is public in `examples/hermes-stdio.yaml`. `skills_list` returns the name, description, and category of every installed skill, including skills the user or the agent wrote; remove it from `public_tools` if that is sensitive. `skill_view` (full skill content) is denylisted.

The server module is version-dependent, and Hermes treats it as an internal interface. CI checks it against Hermes 0.21.5 and a pinned `main`; check again before upgrading Hermes.

Hermes' conversations and messaging MCP surface (`hermes mcp serve`: conversation reads, message sends, approvals) is out of scope and must never be bridged onto an agent network.

The `fetchai-bridge` Hermes plugin adds no tools, hooks, or middleware, so it changes nothing the Hermes agent can do on its own. What it does is listed in its [README](../hermes-plugin/fetchai-bridge/README.md).

## Residual risks

- **DNS rebinding and redirects.** URL checks run when a call is validated. The tool resolves the host again when it connects, and may follow redirects, so a name whose answer changes, or a redirect, can still reach a private address. Treat the URL checks as defense in depth and run fetching tools where private addresses are not reachable.
- **Bare numbers are not hosts.** A string that is only a number, such as `2130706433`, is treated as text, because treating every number as an address would reject ordinary arguments. A tool that turns bare input into a URL must do its own checks.
- **Replay cache in memory.** A restart clears the cache, so a captured call can be replayed until its issue time is older than `replay_ttl_seconds` (300 seconds by default). Wall-clock jumps on the bridge host have a similar effect.
- **Same user as Hermes.** The tools server runs as the user who runs the bridge, with that user's access to `HERMES_HOME`. The separate process and filtered environment limit what reaches it; they are not a sandbox.
- **Dependency audit exceptions.** The audit currently ignores two transitive vulnerabilities until uAgents' dependencies allow a fix:
  - `PyNaCl==1.6.0` through `uagents`/`cosmpy`: `CVE-2025-69277`.
  - `ecdsa` through `uagents-core` and `cosmpy`: `PYSEC-2026-1325`, a Minerva timing side channel in python-ecdsa signing and key generation (verification is not affected). python-ecdsa treats side channels as out of scope, so no fixed version exists. The bridge signs every response envelope with its agent key through this library. Remote timing over a network is far noisier than local timing, and the rate limits cap how many signatures a caller can trigger; an attacker who can time signing precisely on the same host is the realistic threat. Run the bridge on a host you control. Remove this exception when uAgents moves to a constant-time signing backend.

Do not remove an audit exception without confirming that `uagents`, `cosmpy`, signing, and wallet behavior still work with the fixed dependency.

## Payments (in development)

The agent-economy work ([`agent-economy.md`](agent-economy.md)) adds money, so it gets its own threat model. None of it is released yet; this section records the threats the design must close, and each item moves to "Controls" when its code lands with tests.

Threats when Hermes sells:
- a buyer pays less than the price, or pays a different denomination or recipient, and claims the full service;
- one payment is used twice, by the same buyer or by a stranger who copies the transaction hash from the public chain (front-running);
- an old payment, or one made for another quote, is presented for a new request;
- a flood of quote requests from throwaway agent identities fills storage or locks out paying buyers;
- strangers' requests drive the owner's model account (cost, abuse, provider terms) or try to escape the service's tool limits.

Threats when Hermes buys:
- a reply from another agent carries instructions that a tricked Hermes follows, more dangerous in YOLO mode, so agent conversations are refused in YOLO mode;
- the model is tricked into paying, or into paying more or to someone else, so every payment asks the owner, shows the terms from the bridge's own records, and is capped per payment, per seller, and per day;
- a payment whose broadcast outcome is unknown is retried and paid twice, so such payments wait for the owner;
- the agent's seed in Hermes' `.env` is read through the terminal tool (Hermes masks `.env` reads but does not treat that as a boundary), which is why wallets hold small testnet balances and mainnet requires revisiting where the seed lives.

## Reporting vulnerabilities

See [`SECURITY.md`](../SECURITY.md).
