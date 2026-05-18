# Agentverse Operator Handoff

This is the live operator checklist for taking Hermes Fetch AI from local proof to an Agentverse-facing mailbox proof.

It is not legal advice and it does not authorize payment, production deployment, mainnet action, or real-value transfer. It is the safe handoff so the operator can sign in, connect the right Agentverse surface, and capture proof without exposing secrets.

## Current State

Local repo status is ready for operator-owned hosted proof after the local gates are re-run in the operator shell.

- Current final status is `BLOCKED_OPERATOR_ONLY`, not `DONE_AGREED`.
- Remaining blockers require Agentverse account access, process-local seed material, mailbox linking, controlled remote sender proof, optional separately approved payment proof, and PR/merge authority.
- The repo's default Agentverse-facing config keeps `policy.public_tools: []`.

## Official Agentverse Decision

Use mailbox/Inspector first for this repo's immediate live proof.

Why:

- The implemented bridge exposes Hermes MCP through uAgents protocol handling. Chat/ACP is not the v1 proof surface.
- Agentverse external uAgent registration is a separate ACP-compatible path that requires a public reachable endpoint, API key, and seed material.
- Hosted Agentverse agents are useful later as wrappers or demos, but they are not the first proof path for a local Hermes runtime.

Official source anchors:

- External uAgent / ACP registration: https://docs.agentverse.ai/documentation/launch-agents/external-agents/u-agents
- Agentverse mailbox submit API: https://docs.agentverse.ai/api-reference/agents/submit-mailbox-message
- Agentverse mailbox/errors and quota behavior: https://docs.agentverse.ai/documentation/advanced-usages/agent-logs-errors
- Agent Payment Protocol: https://uagents.fetch.ai/docs/guides/agent-payment-protocol

## Proof Surface Decision Table

| Surface | Use for first sign-in? | Use when | Stop if |
| --- | --- | --- | --- |
| Mailbox + Inspector | Yes | Linking the operator-owned uAgent identity and proving signed remote delivery. | Agentverse asks for paid quota, wallet authorization, or unknown broad access. |
| Real Hermes mailbox bridge | Yes, after linking | Running `examples\agentverse-mailbox-hermes.yaml` against the local Hermes MCP backend. | Any secret-shaped value is printed or public tools are unexpectedly non-empty. |
| External ACP registration | Later | A public ACP-compatible endpoint exists and the operator approves public registration. | The flow requires changing this repo into a chat/ACP implementation. |
| Hosted Agentverse agent | Later | A wrapper/demo should run inside Agentverse rather than on the local Hermes runtime. | It would duplicate Hermes or store operator secrets in hosted code. |

## Pre-Login Local Checks

Run these before signing in. Use local placeholders; do not put machine-specific absolute paths into committed docs.

```powershell
$repoRoot = "<path-to-Hermes-Fetch-AI>"
$hermesRepo = "<path-to-hermes-agent-main>"
Set-Location $repoRoot

$bridgePython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$env:HERMES_FETCH_HERMES_PYTHON = Join-Path $hermesRepo ".venv\Scripts\python.exe"

& $bridgePython -m pytest -q
& $bridgePython -m ruff check .
& $bridgePython -m mypy src
& $bridgePython -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --probe-backend
& $bridgePython -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --contamination-scan
& $bridgePython -m hermes_fetch_ai.cli demo local
& $bridgePython -m hermes_fetch_ai.cli demo payment --config examples\payment-dry-run.yaml
```

Then confirm the no-seed failure still fails closed:

```powershell
Remove-Item Env:\UAGENT_SEED -ErrorAction SilentlyContinue
& $bridgePython -m hermes_fetch_ai.cli demo mailbox --config examples\agentverse-mailbox-hermes.yaml --duration-seconds 5
```

Expected result: non-zero exit caused by missing `UAGENT_SEED`.

## Secret Handling

Never paste these into chat, YAML, docs, screenshots, commit messages, or issue comments:

- `UAGENT_SEED`
- seed/recovery material
- Agentverse API credential
- mailbox credential
- wallet signing material
- payment processor secret

Do not inspect `.env`.

Use a clean PowerShell session with only the proof variables needed. Enter `UAGENT_SEED` process-locally:

```powershell
$seedInput = Read-Host "Enter UAGENT_SEED" -AsSecureString
$seedPtr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($seedInput)
try {
  $env:UAGENT_SEED = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($seedPtr)
} finally {
  [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($seedPtr)
  $seedInput.Dispose()
}
```

If Agentverse gives you an API credential or generated registration script, keep it process-local or in a private ignored file only if the tool requires it. Do not commit it.

## Phase 1: Link Mailbox With Inspector

Use the first-linking config only for Agentverse/Inspector setup:

```powershell
& $bridgePython -m hermes_fetch_ai.cli serve --config examples\agentverse-mailbox.yaml
```

This config uses the fake MCP backend, Inspector enabled, and an empty public tool policy. Its job is to create or link the mailbox identity, not to prove Hermes.

In Agentverse:

1. Sign in.
2. Open Agentverse Inspector or the local Inspector URL printed by the uAgents runtime.
3. Choose the mailbox connection path.
4. Link the agent identity for `hermes_fetch_mailbox`.
5. Verify Agentverse shows the mailbox-linked agent.

Stop if Agentverse asks for paid quota, wallet authorization, registration fees, production deployment, or any unrelated permissions.

## Phase 2: Start The Real Hermes Mailbox Bridge

After mailbox linking, stop the first-link process and start the Hermes bridge:

```powershell
& $bridgePython -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --probe-backend
& $bridgePython -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --contamination-scan
& $bridgePython -m hermes_fetch_ai.cli serve --config examples\agentverse-mailbox-hermes.yaml
```

Expected startup evidence:

- bridge/uAgent address is visible;
- no secret material is printed;
- `policy.public_tools` remains empty;
- side-effecting tools remain denied.

`demo mailbox --duration-seconds 180` is acceptable as a startup smoke window, but `serve` is the live proof mode for remote mailbox traffic.

## Phase 3: Remote Proof

Use a controlled remote sender.

Start with deny-first discovery:

1. Send `ListTools`.
2. Confirm the response exposes no broad public tool surface.
3. Capture sanitized evidence in `research/HOSTED_HOOKUP_EVIDENCE.md`.

For a positive one-tool proof, copy `examples\agentverse-mailbox-hermes.yaml` to a private ignored local path or outside the repo. Add exactly one reviewed sender and one low-risk tool:

```yaml
policy:
  public_tools: []
  allowed_senders:
    agent1...remote-sender-address...: [conversations_list]
  denied_tools:
    - messages_send
    - permissions_respond
```

Then rerun doctor, start `serve`, send `ListTools`, and send one allowed `CallTool`.

Do not allow:

- message sending;
- permission response;
- filesystem write;
- shell execution;
- wallet/payment execution;
- broad Hermes conversation access;
- any tool not explicitly reviewed for the sender.

## Evidence To Capture

Capture only non-secret evidence:

- command names and exit codes;
- bridge/uAgent address or redacted Agentverse identifier;
- remote sender address if safe to publish;
- sanitized request/response transcript;
- proof that `policy.public_tools` remained empty or minimal;
- proof that denied tools stayed denied;
- confirmation that missing `UAGENT_SEED` still fails closed;
- confirmation that no seed/API/mailbox/wallet/payment credential appeared in logs, docs, commits, or screenshots.

Store evidence in `research/HOSTED_HOOKUP_EVIDENCE.md` only after sanitizing it.

## Payment Boundary

The current payment proof is a CLI dry-run protocol-model proof only. It does not prove remote hosted payment negotiation or settlement.

Do not run testnet, sandbox, mainnet, FET, Stripe, Skyfire, or any other payment rail unless the operator gives a separate approval that names:

- rail/network;
- maximum amount and currency;
- recipient category or address;
- credential/wallet custody plan;
- fee tolerance;
- exact config path;
- one-time authorization sentence.

Until then, the only allowed payment command is:

```powershell
& $bridgePython -m hermes_fetch_ai.cli demo payment --config examples\payment-dry-run.yaml
```

## Cleanup

After the proof:

```powershell
Remove-Item Env:\UAGENT_SEED -ErrorAction SilentlyContinue
Remove-Item Env:\HERMES_FETCH_HERMES_PYTHON -ErrorAction SilentlyContinue
```

Then update:

- `research/HOSTED_HOOKUP_EVIDENCE.md` for sanitized proof evidence; or
- `research/HOSTED_DEMO_BLOCKER.md` if Agentverse remains blocked by exact account/endpoint/linking steps.

Only after hosted proof is captured or explicitly deferred should the PR package claim readiness beyond `BLOCKED_OPERATOR_ONLY`.
