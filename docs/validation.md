# Checked against Hermes' and Fetch.ai's documentation

On 2026-10-06 the plugin and the bridge were checked, requirement by requirement, against Hermes' documentation and code (release 0.21.5 and `main` at `bb236287`) and against Fetch.ai's documentation and official examples for uAgents, Agentverse, ASI:One, and the testnet. This page records what was checked, what was fixed as a result, and what only the real-world trial with a real ASI:One user and an Agentverse account can settle.

## Hermes

Sources: Hermes' plugin guide (`website/docs/developer-guide/plugins/index.md`), the tool guide (`adding-tools.md`), the catalog submission guide (`plugins/catalog-submission.md`) and `plugin-catalog/README.md` with its admission rules (9 in 0.21.5, 16 on `main`; the catalog PR goes to `main`), the hooks and security guides (`user-guide/features/hooks.md`, `user-guide/security.md`, `user-guide/configuration.md`), and, where the docs are silent, Hermes' code: `hermes_cli/plugin_validate.py`, `plugins_manifest.py`, `plugin_isolation.py`, `plugin_host_child.py`, `tools/approval.py`, `tools/approval_prompt.py`, `tools/skill_linter.py`, and `scripts/validate_plugin_catalog.py`.

### Fixed

| What the docs say | What was wrong | Now |
|-------------------|----------------|-----|
| "Never raise: catch all exceptions, return error JSON instead" (plugin guide) | An answer from the bridge in an unexpected shape raised out of a tool, in `fetchai_pay` even after the user approved | Every tool answers with an error; after approval, any failure says the payment may or may not have been made and to run `buyer check` |
| With `plugins.isolation: host` (`main`), tools run in a separate host process (`plugin_host_child.py`) | There, a session's `/yolo` is invisible and the payment prompt cannot be shown, so the YOLO refusal could be skipped | The tools detect the host and refuse, saying they need `plugins.isolation: in_process` |
| Plugin skills load under namespaced names (`plugin:skill`) | The `buy` skill named `operate` as its related skill | `fetchai-bridge:operate` |
| Rule 12: no disabling Hermes' guards | A guest Hermes runs with Tirith off, without saying why | The setting says why: Tirith scans terminal commands, a guest has none, and left on, Hermes may download it |
| Rule 13: say what the plugin does and which Hermes surfaces it uses, in the PR and README | The submission text still described 1.0 (no tools, nothing prompts, no funds) | [`upstream-hermes-pr.md`](upstream-hermes-pr.md) lists every surface, the three internals, all 16 rules, and the disclosures; the plugin README names the internals |
| Rule 14: truthful metadata | `plugin.yaml`'s one-line description still said "for allowlisted Hermes tools" | It says what the plugin does now |

### Meets

- **Manifest.** `name`, `version`, `description` present; `manifest_version: 2`, `api_version`, `license`, `homepage`, `tags`; `python_runtime: external`; `config_schema` types `bool`, `str`, and `secret` (with `env`), each with a label and a description, and a default for the ones that are not secrets. `hermes plugins validate --install-deps` passes on both versions, with the security scan's verdict `safe`.
- **Catalog entry.** Name, version, `requires_hermes`, `provides_tools`, and platforms agree with `plugin.yaml`; tier, category, and `subdir` are valid; `known_issues` is a known field. `scripts/validate_plugin_catalog.py` passes once the SHA is filled in.
- **Rules.** 6 (declared tools match the registered ones), 9 (no rebinding of Hermes code), 10 (no dependencies), 11 (only the plugin's own secrets; the bridge gets an allowlisted environment), 12 (YOLO refusal, the prompt fails safe, `install` and `setup` refuse without a terminal, `HERMES_YOLO_MODE` never passed on), 15 and 16 (no other Fetch.ai entry; original work).
- **Tools.** Schemas in the documented shape; handlers return JSON strings with `{"error": ...}`; a `check_fn` that returns a bool; free-form toolset name; no clash with built-in tools.
- **YOLO detection.** `is_approval_bypass_active` covers every way the docs list to turn YOLO on (`--yolo`, `/yolo`, `HERMES_YOLO_MODE`, `approvals.mode: off`); the field test checks each on both versions.
- **Skills.** Frontmatter fields, platforms, and a "When to Use" section, as the skill guide and linter expect.

### Open

- **Hermes internals.** The YOLO check, the payment prompt, and the `.env` writer are not a published plugin API (Hermes' compatibility notes say internal import paths are not stable). The documented alternative for approvals, a `pre_tool_call` hook returning `approve`, goes through a gate that approves on its own under YOLO or after a remembered answer, so it cannot ask before every payment. The plugin refuses if the internals disappear or change, the field test checks them on both versions, and the submission names them and suggests asking Hermes for a public "ask the user" seam.
- **The bridge's pin.** The catalog pins the plugin by commit SHA; the plugin installs the bridge from the tag `v<version>`, which can be moved. A SHA or PyPI would pin it as firmly ([`upstream-hermes-pr.md`](upstream-hermes-pr.md#open-questions-for-review)).
- **Hermes 0.21.5's prompt.** On 0.21.5 the payment prompt works in the TUI and messaging apps; in the classic CLI it may decline without being shown, and a one-shot run from a terminal can wait for the approval timeout before declining. Recorded in the README, the security guide, and the entry's `known_issues`.
- **The terminal path.** Hermes' terminal can run the bridge's `buyer pay` without the prompt, within the bridge's limits. Hermes' `approvals.deny` (in both versions) blocks it even under YOLO; the README shows the rule.
- **The SHA.** Filled in at submission (rule 2).

## Fetch.ai, Agentverse, and ASI:One

Sources: Fetch's FET payment example, the reference ASI:One's payment card is built from ([innovation-lab-examples `fet-example`](https://github.com/fetchai/innovation-lab-examples/tree/main/fet-example)); the uAgents docs ([ASI:One compatible agents](https://uagents.fetch.ai/docs/examples/asi-1), [mailbox](https://uagents.fetch.ai/docs/agentverse/mailbox), [payment protocol](https://uagents.fetch.ai/docs/guides/agent-payment-protocol)); Agentverse's docs ([enable the chat protocol](https://docs.agentverse.ai/documentation/getting-started/enable-chat-protocol), [agent profile](https://docs.agentverse.ai/documentation/agent-discovery/profile), [setup guide](https://docs.agentverse.ai/documentation/agent-discovery/setup-guide), [README guidelines](https://docs.agentverse.ai/documentation/agent-discovery/readme-guidelines), [search API](https://docs.agentverse.ai/v-1/api-reference/search/agents), [register an agent](https://docs.agentverse.ai/api-reference/agents/register-agent)); ASI:One's docs ([agent chat protocol](https://docs.asi1.ai/documentation/tutorials/agent-chat-protocol), [planner](https://docs.asi1.ai/documentation/build-with-asi-one/planner)); Fetch's network docs ([active networks](https://network.fetch.ai/docs/guides/ledger/references/active-networks), [faucet](https://network.fetch.ai/docs/guides/ledger/faucet)); the installed uAgents 0.25.5 and uagents-core 0.4.9; and read-only calls to Dorado's REST endpoint and Agentverse's handle and search APIs.

### Fixed

| What the source says | What was wrong | Now |
|----------------------|----------------|-----|
| ASI:One waits "from 60 seconds … extended to 240 seconds once one starts replying" (planner) | After a payment the bridge said nothing until the work was done, which can take more than a minute | It says "Payment confirmed. Working on … now." at once; Hermes, buying, waits for the seller to end the conversation rather than taking that note for the answer |
| Fetch's examples pass their own session as the payment reference, and nothing documents what ASI:One sends back | A commit with a reference the bridge did not issue went to the lost-order path, which could only cancel it | Such a reference counts as none, and the payment is matched to the order by its exact amount |
| The example's payment request carries `metadata.content` | Not sent | Sent: "Please complete the payment to start …" |
| Handles: Agentverse's handle API answers `ab-c1` for `a_b-c1` and `hermesreviews` for `hermes.reviews` | `_` was accepted, so the owner could be told a handle ASI:One would not find | Only lowercase letters, digits, and `-` |
| Starter prompts suggest how users can talk to the agent; the README guidelines ask for examples | The listing offered the prompt "<service>: <your request>", which ASI:One would send as written | Services take an `example`, which becomes a starter prompt and the README's Examples section |
| uagents-core caps an agent's short description at 300 characters | The config did not | It does |
| With `publish_manifest: true` the bridge registers through the Almanac API only | The mailbox guide said it also paid the Almanac contract | Corrected: only with `agent.ledger_registration: true` |
| Fetch expects to retire Dorado after the ASI migration, in favor of Eridanus (`eridanus-1`, `atestasi`) | Not mentioned | Noted in [`payments.md`](payments.md#dorados-future) |

### Meets

- **The payment request** matches Fetch's FET example field for field: `Funds(amount=<FET as a decimal string>, currency="FET", payment_method="fet_direct")`, the agent's wallet as `recipient`, and `metadata` with `provider_agent_wallet`, `fet_network: stable-testnet`, and `mainnet: "false"`. The installed message models are identical to the example's (uagents-core 0.4.0) and to upstream; `tests/test_protocol_canaries.py` pins them.
- **The payment flow.** Handlers for `CommitPayment` and `RejectPayment` on the seller's side; `CompletePayment(transaction_id)` and `CancelPayment(transaction_id, reason)`; the transaction id is the transaction hash, checked on the ledger. As a buyer, the bridge's `CommitPayment` carries the funds, the transaction id, and `metadata.buyer_fet_wallet`.
- **Chat.** Every `ChatMessage` acknowledged; the answer ends with `EndSessionContent`; mailbox agents include the chat protocol with `publish_manifest=True`. The chat protocol digest (AgentChatProtocol 0.3.0) matches the one Fetch's Innovation Lab gives for the chat protocol, shortened there to `proto:30a801ed...bd33d62` ([Agentverse Skills](https://innovationlab.fetch.ai/resources/docs/next/agentverse/agentverse-skills)).
- **Agentverse search.** `POST https://agentverse.ai/v1/search/agents` with `search_text`, `filters.protocol_digest`, `sort`, `direction`, `offset`, and `limit`; every response field the bridge reads is documented and present in a live answer.
- **Dorado.** Chain `dorado-1`, denomination `atestfet`, REST `https://rest-dorado.fetch.ai`; a gas price above the documented minimum; the faucet the documented one (through cosmpy). The live tests confirm all of it.
- **ASI:One's setup** for buyers (Developer mode, Manage payments, a wallet with testnet FET) is in [`asi-one.md`](asi-one.md).

### Open, for the real-world trial

- **Listing a mailbox agent with an API key.** Agentverse's registration docs list the agent types `uagent` and `a2a`, while uagents-core's own types include `mailbox`, which the bridge uses; Fetch's guides connect a mailbox through the Agent Inspector instead. The trial will show whether the API listing is enough for the mailbox to receive messages.
- **What ASI:One does with payments:** whether it sends a reference back, whether its wallet keeps all nine decimals of an order code, and whether its payment card reads `description`, `content`, or `deadline_seconds`. No Fetch source says.
- **Discoverability.** Whether ASI:One finds a mailbox agent by its protocols without the manifest published to the Almanac, and the effect of an avatar and keywords, which Agentverse's setup guide recommends ([`asi-one.md`](asi-one.md) says to add them).
- **Payment protocol digests.** Fetch publishes none; ours come from the same models as Fetch's example, so they should match.
