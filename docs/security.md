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

## Payments

Selling services for testnet FET ([`payments.md`](payments.md)) and buying from other agents ([`buying.md`](buying.md)) add money, so each has its own threat model below.

### Selling: threats and controls

| Threat | Control |
|--------|---------|
| A buyer claims a payment it did not make, or claims a larger amount | The bridge reads every transaction from the ledger itself and ignores what the buyer says it paid. It accepts only a successful, included transaction of plain transfers from one payer, sums only the transfers to the payout address in `atestfet`, and compares whole numbers of `atestfet`, never floating point. |
| A buyer pays less, in another token, or to another address | Each is refused (`payment invalid: ...`) and nothing is recorded. |
| One payment is used twice, by the same buyer or across a restart | Used transaction hashes are stored in SQLite. Checking and recording a payment happen in one `BEGIN IMMEDIATE` transaction, so two requests racing with the same hash cannot both pass, and the record survives restarts. |
| A stranger copies a transaction hash from the public ledger (front-running) | The memo must be the quote reference, and the reference is bound to the buyer's agent address: another agent presenting it gets `quote does not match this call`, and presenting the hash with its own quote gets `payment already used`. |
| An old payment, or one made for another quote or request, is presented | The reference is a signed token (HMAC with a key derived from the seed) that carries the buyer, the service, a digest of the exact arguments, the amount, the recipient, the chain, and the expiry. The transaction's block time must fall between the quote's creation (minus 30 seconds) and its expiry (plus 120 seconds). |
| A flood of quote requests from throwaway identities fills storage | Quotes are stateless signed tokens: asking for a price stores nothing. Quote requests pass the bridge's normal per-sender and global rate limits. |
| A flood of fake payment proofs drives ledger lookups | Proofs are checked against the token and the used-hash table first; ledger lookups are rate-limited per sender (6 per minute) and globally (60 per minute). |
| A misconfigured or malicious ledger endpoint | `ledger_url` must be `https://` (or `http://` on this machine). Before verifying anything, the bridge checks once that the endpoint reports chain `dorado-1`, and refuses payments otherwise. `payments.network` accepts only `testnet`. |
| A paid request is lost when the service or the bridge fails | A verified payment becomes a credit: `paid → running → done`. A failure on the seller's side returns it to `paid` for a retry, up to `max_attempts`; a run interrupted by a crash or a shutdown (which also kills the service program) returns to `paid` at the next start. A buyer who missed a delivered answer can collect it again for an hour. |
| Someone else collects a paid answer | The reference and transaction are public on the ledger, so a kept answer goes only to the agent the quote was issued to, and only in a new message: an exact copy of an earlier message is refused by the replay check. Answers are kept in memory only, at most 64 of them, for an hour. |
| One long job holds up everyone | A selling bridge handles each message in its own task (`tests/test_serve_paid.py` lists tools while a three-second job runs). Each service runs at most `max_running` requests at once with `max_waiting` in line; beyond that, callers are told it is busy before they pay. |
| Strangers run up the owner's costs or abuse a service | Each service has a daily run limit, input size limit, and URL checks; buyers are rate-limited; the owner can `pause` all selling or `ban` one agent. Service programs run without a shell, in an empty temporary folder, with a short environment allowlist, a timeout, and an output cap, and their standard error never reaches the buyer. |
| A service that cannot run takes payments | `doctor` and `serve` fail when a service program, or a file named by absolute path in its arguments, is missing. |
| Payment details leak into logs | The audit log records only short forms: the first 8 and last 4 characters of a transaction hash and payer address, and the signed tail of a reference. |
| Through chat, a payment without our reference is claimed for another order | ASI:One's wallet is not known to set a memo, so chat prices carry an order code: a random surcharge of 1 to 65,535 billionths of a FET. Without the memo, the amount must match the order's to within a tenth of a code step, so a copied transaction cannot pay for someone else's order. |
| A stranger in chat reaches the owner's Hermes | Chat sells only the configured services; Hermes' tools stay behind the MCP protocol's default-deny policy. Chat requests pass the same checks as MCP calls (owner controls, size, URL checks, daily limit, the busy line) and the per-sender rate limit. |
| A forged commit cancels a buyer's order | An order is dropped on a failed payment only when the buyer who ordered sent the commit; anyone else's failed commit gets only a `CancelPayment`. |
| A flood of chat orders fills memory | Quotes are stateless; orders waiting for payment are kept in a bounded table (256, oldest dropped first). A payment for a dropped order is still accepted, and the buyer resends the request. |
| A published bridge spends from its wallet on its own | It registers through the Almanac API only and never looks up the Almanac contract, unless the owner sets `agent.ledger_registration: true`. |
| A buyer's request turns a research service's Hermes against the owner | The work runs in a guest Hermes ([`guest-hermes.md`](guest-hermes.md)): a fresh Hermes home per request, never the owner's, with only the `web` toolset (or none), every other toolset also switched off by name, no memory, plugins, or rules files, and an environment allowlist that keeps out the seed and the owner's keys. The model's own key comes from the guest's keys file. A terminal call the model asks for is refused. |
| A buyer makes a guest fetch addresses inside the owner's network (SSRF) | The bridge writes `security.allow_private_urls: false` into the guest's settings, and Hermes refuses private, loopback, link-local, and cloud metadata addresses for web tools. The bridge refuses to start when a `.env` that Hermes loads into guests (the guest's keys file, the one in Hermes' install folder, or `/etc/hermes`) sets any `HERMES_...` variable, or when `/etc/hermes` pins private addresses or MCP servers. |
| One buyer's words reach later buyers | Each request's Hermes home is deleted when it ends; memory, the background self-review that saves memories and skills, and the skill curator are off. |
| A guest runs up the owner's model bill, or never ends | `max_turns`, the bridge's `timeout_seconds` (Hermes keeps retrying a model server that does not answer, so the bridge kills it), session titles off, the daily run limit, rate limits, and the price. |
| A guest installs software or changes Hermes' own install | `HERMES_DISABLE_LAZY_INSTALLS=1` and `security.allow_lazy_installs: false`; without them a fresh Hermes home starts background downloads and syncs Hermes' packages. |

These are covered by tests: `tests/test_guest.py` (the command, environment, settings, and keys file a guest gets, failures, limits, and the startup checks) and `tests/test_field_guest_hermes.py` (against real Hermes in CI: only the web tools are offered, a terminal call is refused, a page on 127.0.0.1 is not fetched, nothing is left behind), `tests/test_chat_protocol.py` and `tests/test_chat_flow.py` (chat sales, order codes, someone else's payment, slow payments, restarts), `tests/test_check_transfer.py` (every transfer rule), `tests/test_ledger.py` (reading real Dorado responses saved as fixtures), `tests/test_seller.py` (including two redeems racing with one payment), `tests/test_store.py` (including two bridges sharing one database, and restarts), `tests/test_paid_protocol.py`, and `tests/test_serve_paid.py`, which runs `serve` in its own process against a ledger on 127.0.0.1 and checks that the bridge makes no ledger request before a paid call arrives. The results of a manual run on the real testnet are in [`payments.md`](payments.md#tested-on-the-real-testnet).

### Selling: residual risks

- **Refunds are manual.** Failed, lapsed, and extra payments are listed by `seller credits`; the owner sends the FET back by hand.
- **Refused payments are not recorded.** A buyer who underpays or uses the wrong memo has paid, but the bridge has no record of it; refunds need the buyer's transaction hash.
- **The seed signs quotes and holds the income.** A leaked `UAGENT_SEED` lets someone forge quotes and spend the income wallet. Set `payout_address` to a wallet whose key lives elsewhere to keep income away from the seed.
- **Service programs run as the bridge's user.** The runner's allowlisted environment and empty working folder limit what reaches a program; they are not a sandbox. Sell only programs you trust with that user's files.
- **A model can be talked into things.** A buyer's request can try to make an AI-backed service ignore its instructions. The example code review gives its model no tools, and a guest Hermes has at most the web tools, so the worst cases are an answer its own buyer should not have gotten, and searches or page reads on the public web.
- **A guest's isolation relies on Hermes.** The `-t` list, the switched-off toolsets, and the private-address check are Hermes' own behavior. CI checks them against Hermes 0.21.5 and a pinned `main`; check again after a Hermes upgrade (`tests/test_field_guest_hermes.py`). A guest runs as the bridge's user, so it is not a sandbox: a bug in Hermes itself would run with that user's permissions.
- **A proxy weakens the private-address check.** With `HTTPS_PROXY` set for a guest, Hermes lets host names through without resolving them, and the proxy decides where they lead.
- **Guests send buyers' requests to others.** Requests go to the guest's model provider, and searches to the search service Hermes uses (the free tiers of public search services when no search key is set).
- **The ledger endpoint is trusted for what it reports.** The bridge checks the chain ID, not proofs of inclusion; a compromised endpoint could report fake transactions. Use Fetch's endpoint or your own node.
- **Order codes can be guessed, slowly.** A stranger who, within 30 seconds after a buyer's payment, gets a quote carrying the same order code, and commits the buyer's payment for it before the buyer's own commit arrives, could claim it. With 65,535 codes and the rate limits that is unlikely, and it moves only test FET.
- **ASI:One's side is unconfirmed.** Whether ASI:One sends the reference back, how it rounds amounts, and whether its payment card needs more fields are not yet tested with a real ASI:One user ([`asi-one.md`](asi-one.md#what-is-tested)).
- **Agentverse sees chat traffic in mailbox mode.** Messages between ASI:One users and the bridge pass through Agentverse.

### Buying: threats and controls

Hermes can buy from other agents through the plugin's tools and the running bridge ([`buying.md`](buying.md)). The approval prompt is the user experience; the bridge's limits are the boundary, because Hermes runs as the same user as the bridge.

| Threat | Control |
|--------|---------|
| Hermes is tricked into paying (prompt injection from a web page, a file, or another agent) | Every payment shows the owner the request as the bridge recorded it (amount, seller, its Agentverse listing, recipient, the seller's own description, labeled as such) in Hermes' confirmation prompt, which Hermes shows even in YOLO mode, never remembers, and declines when nobody can answer. Only "accept" pays. |
| Another agent's reply steers Hermes while it runs without approvals | The plugin's tools refuse while YOLO mode is on (`tools.approval.is_approval_bypass_active`: `--yolo`, `/yolo`, `HERMES_YOLO_MODE`, `approvals.mode: off`), and also when Hermes cannot say. Replies and listings are returned as information, never as instructions, and the `buy` skill says so. |
| A payment for something other than what the owner approved | Approval carries a one-time code issued when the request was shown, plus the exact amount and recipient; the bridge pays only if all three still match its record, and each code pays once. |
| Paying too much, too often, or the wrong agent | Per-payment, per-seller-per-day, and per-day limits (defaults 1, 2, 5 testnet FET) and an optional list of allowed sellers, checked in the same `BEGIN IMMEDIATE` transaction that marks the payment as being sent, so two payments, or two bridges sharing records, cannot both slip under a limit. |
| A stranger fills the owner's records with payment requests | Requests are accepted only from agents Hermes is talking to, at most 20 open per agent, in testnet FET (`fet_direct`) to a `fetch1` wallet, with a deadline of at most an hour; anything else is refused and the seller is told. |
| A payment is sent twice | The transaction hash is recorded before the payment leaves the machine; a payment whose outcome is unknown waits (`needs_review`), still counts against the limits, and is never resent on its own; `buyer check` settles it from the ledger. |
| Spending touches the income | Payments come from the buying wallet (key index 1), never from the income wallet (index 0). |
| Mainnet funds | Buying runs on Fetch's testnet only; the config refuses anything else. |
| Something on the machine or a web page drives the bridge's buying | The control channel listens on 127.0.0.1 only, on a random port, speaks one JSON line per request (not HTTP, so a browser cannot reach it), and requires a 256-bit token from a file only the owner can read (0600), removed on shutdown. |
| Replies display misleading text | Control characters and Unicode direction overrides are removed from replies, listings, and descriptions; lengths are capped. |
| Another agent floods Hermes with replies | One answer to Hermes holds at most 50 replies and 60,000 characters; the rest wait in the bridge's records, which keep the newest 500 messages. |
| Other users of the computer read what Hermes sends | The plugin passes messages to the bridge on standard input, not in the command line, which other users can list. |
| The model slips an option into a bridge command (`--config ...`) | The plugin passes the bridge only an agent address, a conversation id, and a payment request id in their exact shapes, removes leading dashes from searches, and sends messages on standard input. |

Tests: `tests/test_buyer.py`, `tests/test_control.py`, `tests/test_buy_flow.py`, `tests/test_serve_buying.py`, `tests/test_hermes_directory_plugin.py`, and, against real Hermes, `tests/test_field_hermes_buyer.py`. The results of the manual runs on the real testnet are in [`buying.md`](buying.md#what-is-tested).

### Buying: residual risks

- **The seed is in Hermes' `.env`.** The owner chose to keep `UAGENT_SEED` there. Hermes masks `.env` reads but does not treat that as a boundary, so a Hermes tricked into using its terminal could read the seed and spend the buying wallet (and the income wallet) without asking. That is why buying is testnet only, the buying wallet should hold small amounts, and where the seed lives is on the mainnet checklist.
- **The same user can drive the bridge.** Anything running as the owner's user (including Hermes' terminal tool) can read the control channel's token and run `buyer pay` after `buyer show`, without Hermes' prompt. The bridge's limits still hold.
- **A seller can take the money and not deliver.** The payment protocol has no escrow; a seller can cancel after being paid or never answer. The bridge records it (`cancelled`) and tells Hermes to ask for a refund, but cannot force one.
- **Messages can leak what Hermes sends.** Messages go to the agent Hermes writes to (and through Agentverse for mailbox agents). The `buy` skill tells Hermes to send only what the task needs; it is guidance, not enforcement.
- **The prompt's details come from the seller.** The amount and recipient are checked at payment time; the seller's name, rating, and description are the seller's and Agentverse's words.
- **The approval prompt has been tested by a person only in the planned real-world test.** CI checks that it declines when nobody can answer; answering it in Hermes' terminal and in a messaging app is part of [the real-world test](agent-economy.md#status).

## Reporting vulnerabilities

See [`SECURITY.md`](../SECURITY.md).
