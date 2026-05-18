# NORMAL_HERMES_SECRET_TEST_RUNBOOK

Status: WAITING_FOR_OPERATOR_SECRETS

Objective: prove the normal-Hermes hosted mailbox path without exposing, persisting, logging, or committing any secret material.

## Scope

- This runbook is only for operator-owned hosted proof steps.
- Local gates are green from the prior no-secret verification; browser login and local secret entry remain operator-owned.
- No real FET movement is performed by this runbook.

## Runtime Route

- Model: `gpt-5.5`
- Provider: `openai-codex`
- API mode: `codex_responses`
- Reasoning effort: `xhigh`
- Non-ChatGPT fallback: disabled
- Do not switch models unless the operator explicitly says to switch.

## Pre-Conditions

- Bridge repo: `C:\Users\ptann\OneDrive\Work\Hermes Fetch AI`
- Normal Hermes checkout: `C:\Users\ptann\OneDrive\Work\hermes-agent-main`
- Bridge Python: `C:\Users\ptann\OneDrive\Work\Hermes Fetch AI\.venv\Scripts\python.exe`
- Hermes MCP Python: `C:\Users\ptann\OneDrive\Work\hermes-agent-main\.venv\Scripts\python.exe`
- No `.env` inspection.
- Never paste secrets into chat, YAML, docs, commits, screenshots, issue comments, or shell history.

## Browser Steps

Operator-owned only; Codex/Hermes should not handle login secrets.

1. Open Agentverse with your Fetch.ai/Agentverse credentials.
2. Confirm mailbox/agent identity availability for the bridge profile.
3. Create or select the mailbox-capable agent identity that will represent this bridge.
4. Confirm any subscription/quota requirement before test traffic.
5. Confirm wallet/network/funding settings, but do not approve value movement yet.
6. Stop before any UI prompt that asks for FET, wallet authorization, public registration, or paid quota action unless you explicitly intend that next step.

## Terminal Steps

Run these in a local PowerShell window. Secrets stay only in that process environment.

```powershell
cd "C:\Users\ptann\OneDrive\Work\Hermes Fetch AI"

$bridgePython = "C:\Users\ptann\OneDrive\Work\Hermes Fetch AI\.venv\Scripts\python.exe"
$env:HERMES_FETCH_HERMES_PYTHON = "C:\Users\ptann\OneDrive\Work\hermes-agent-main\.venv\Scripts\python.exe"
```

Enter `UAGENT_SEED` without writing it into shell history:

```powershell
$seedInput = Read-Host "Enter UAGENT_SEED" -AsSecureString
$seedPtr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($seedInput)
$env:UAGENT_SEED = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($seedPtr)
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($seedPtr)
$seedInput.Dispose()
```

Optional presence check that does not print the value:

```powershell
Get-ChildItem Env:UAGENT_SEED | Select-Object Name
```

Verify backend tooling:

```powershell
& $bridgePython -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --probe-backend
& $bridgePython -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --contamination-scan
```

Run the hosted mailbox proof in a bounded window:

```powershell
& $bridgePython -m hermes_fetch_ai.cli demo mailbox --config examples\agentverse-mailbox-hermes.yaml --duration-seconds 180
```

Cleanup the secret from the PowerShell session:

```powershell
Remove-Item Env:\UAGENT_SEED
```

## Expected Proof

- The bridge starts in mailbox mode with the normal Hermes MCP backend.
- Startup output does not print seed, mailbox key, wallet key, token, or recovery material.
- Public tool exposure remains restricted by `examples\agentverse-mailbox-hermes.yaml`.
- A missing `UAGENT_SEED` fails closed.
- Hosted proof is not complete until the mailbox demo runs with the operator-provided seed and shows the expected remote-reachable bridge behavior.

## Stop Point Before FET

Stop before any command or UI flow that triggers value settlement, wallet authorization, paid registration, paid quota change, or real FET movement.

Required approval sentence before any real transfer or settlement:

```text
I authorize one real-FET payment test on [NETWORK], amount [X FET], to recipient [CATEGORY/ADDRESS], using config [PATH], and accept any on-chain settlement fees. Do not proceed with any other amount or recipient than stated.
```
