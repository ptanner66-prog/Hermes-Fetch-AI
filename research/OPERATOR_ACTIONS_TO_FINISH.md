# Operator Actions To Finish

Updated: 2026-05-18T18:20:00Z

Final agreement status: BLOCKED_OPERATOR_ONLY

These are the only remaining blockers after the overnight until-done adversarial pass. They are external/operator-owned because they require account login, process-local secrets, remote Agentverse/mailbox setup, payment approval, or merge authority.

Local repo gates are green. The repo now fails closed if a seed is missing, blank, or attempted through YAML/direct config. Do not add `agent.seed` or `agent.mailbox_key` to any config file; the loader intentionally rejects them.

Primary live handoff: `docs/agentverse-operator-handoff.md`.

## A. Hosted Agentverse / mailbox proof

Goal: prove a real remote path without exposing secrets:

remote uAgent or Agentverse/Inspector -> Agentverse mailbox/proxy/endpoint -> Hermes Fetch AI bridge -> local Hermes MCP backend -> response transcript.

Recommended live path: mailbox/Inspector linking first, then the real Hermes mailbox bridge. External ACP registration is a later public-endpoint proof because this repo currently proves Hermes MCP over uAgents mailbox rails, not a Chat/ACP implementation.

Operator-owned prerequisites:

1. Agentverse/Fetch account access.
2. A mailbox-capable agent identity or Agentverse entry for the bridge.
3. A stable uAgent seed supplied only in the operator's local shell as `UAGENT_SEED`.
4. The Hermes source checkout Python path supplied as `HERMES_FETCH_HERMES_PYTHON`, or an installed Hermes console script that can run `hermes mcp serve`.
5. A remote sender identity/address for the caller.
6. Any required mailbox link, quota, subscription, or Agentverse Inspector setup.

Safe local PowerShell setup:

```powershell
cd "C:\Users\ptann\OneDrive\Work\Hermes Fetch AI"
$bridgePython = "C:\Users\ptann\OneDrive\Work\Hermes Fetch AI\.venv\Scripts\python.exe"
$env:HERMES_FETCH_HERMES_PYTHON = "C:\Users\ptann\OneDrive\Work\hermes-agent-main\.venv\Scripts\python.exe"

$seedInput = Read-Host "Enter UAGENT_SEED" -AsSecureString
$seedPtr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($seedInput)
try {
  $env:UAGENT_SEED = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($seedPtr)
} finally {
  [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($seedPtr)
  $seedInput.Dispose()
}
```

Do not paste the seed into chat, YAML, docs, screenshots, issue comments, commits, or shell-history-bearing commands. Do not inspect `.env`.

Phase 1 mailbox linking:

```powershell
& $bridgePython -m hermes_fetch_ai.cli serve --config examples\agentverse-mailbox.yaml
```

This first-linking config uses fake MCP, Inspector enabled, and an empty public tool policy. Use it only to connect/link the mailbox identity in Agentverse. Stop it after the mailbox is linked.

Phase 2 real Hermes bridge checks with the process-local seed:

```powershell
& $bridgePython -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --probe-backend
& $bridgePython -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --contamination-scan
& $bridgePython -m hermes_fetch_ai.cli serve --config examples\agentverse-mailbox-hermes.yaml
```

Expected local hosted-startup evidence:

- command starts and remains ready for remote traffic;
- bridge address is printed;
- seed, mailbox key, API key, wallet key, token, and recovery material are not printed;
- public tools remain empty unless the operator has reviewed and configured a specific sender allowlist.

If a positive remote tool-call proof is required, do not expose broad public tools. Create a private, operator-local copy of `examples\agentverse-mailbox-hermes.yaml` outside the repo or in an ignored local path and add only the chosen remote sender and reviewed low-risk tool(s), for example:

```yaml
policy:
  public_tools: []
  allowed_senders:
    agent1...remote-sender-address...: [conversations_list]
  denied_tools:
    - messages_send
    - permissions_respond
```

Then rerun the doctor checks, start `serve`, send ListTools and one allowed CallTool from the remote sender through Agentverse/mailbox/Inspector, and capture only non-secret evidence in `research/HOSTED_HOOKUP_EVIDENCE.md`:

- bridge address or redacted hosted agent identifier;
- remote sender address if safe to publish;
- command names and exit codes;
- sanitized transcript showing request and response;
- confirmation that no seed/API token/mailbox key/wallet secret was printed or stored;
- confirmation that missing `UAGENT_SEED` still fails closed.

Stop and ask for explicit operator approval if Agentverse asks for payment, registration fees, paid quota changes, production deployment, or wallet authorization.

Cleanup after proof:

```powershell
Remove-Item Env:\UAGENT_SEED -ErrorAction SilentlyContinue
Remove-Item Env:\HERMES_FETCH_HERMES_PYTHON -ErrorAction SilentlyContinue
```

## B. Testnet or sandbox payment proof

Current repo-local proof is dry-run only. It uses official uAgents payment message models and does not connect to wallets, chains, Stripe, Skyfire, payment processors, or real settlement.

Implementation guardrail: `payment.mode: testnet` and `payment.mode: real_operator_approved` intentionally fail config validation in this repo-local proof. Any sandbox/testnet implementation must be a separate operator-approved change with a runbook and limits before execution.

Before any testnet/sandbox proof, the operator must provide all of the following in the current context:

1. Exact rail: e.g. FET testnet, Stripe test mode, Skyfire sandbox, or another named sandbox rail.
2. Maximum amount and currency.
3. Recipient category/address or sandbox account identifier.
4. Process-local credentials or wallet/testnet setup, never pasted into chat or committed.
5. Explicit approval sentence for that exact test, for example:

```text
I authorize one sandbox payment proof on [RAIL/NETWORK], max amount [AMOUNT CURRENCY], to [RECIPIENT CATEGORY/ADDRESS], using config [PATH]. Do not proceed with any other amount, rail, or recipient.
```

Without those items, no testnet/sandbox transaction should be attempted and no repo-local claim should say settlement was proven.

## C. Real-value / mainnet payment proof

Real-value or mainnet movement remains out of automatic scope.

Before any real-value step, the operator must separately approve the exact action in the current context and provide:

1. Named rail/network.
2. Exact max amount and currency.
3. Recipient category/address.
4. Wallet custody/signing plan owned by the operator.
5. Fee tolerance.
6. Settlement verifier.
7. Rollback/cancel/incident plan.
8. Legal/commercial/security review where applicable.
9. Secret-handling plan.

Required approval sentence before any real-value movement:

```text
I authorize one real-value payment test on [RAIL/NETWORK], amount [AMOUNT CURRENCY], to recipient [CATEGORY/ADDRESS], using config [PATH], and accept any stated settlement/network fees. Do not proceed with any other amount, recipient, rail, or repeated transfer.
```

No real FET/mainnet/production settlement is authorized by the current done-agreement pass.

## D. Human review / PR / merge action

The worktree is intentionally dirty with tracked and untracked implementation, tests, examples, docs, and research artifacts. A human/operator must decide whether to:

1. Review the dirty tree as a single branch/PR.
2. Split implementation vs research/docs into separate commits/PRs.
3. Open an upstream Hermes PR only after maintainer direction.
4. Merge or discard any artifacts.

No commit, push, production deploy, or merge was performed in this pass.
