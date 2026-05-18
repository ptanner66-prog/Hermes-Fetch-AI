# Hosted Hookup Evidence

Status: NOT_CAPTURED

Use this file only after operator-owned Agentverse mailbox proof has been run. Do not paste secrets, `.env` values, raw generated registration scripts, API credentials, seed material, wallet signing material, mailbox credentials, or payment processor secrets.

## Operator-Owned Inputs

- Agentverse account signed in: TODO
- Mailbox/Inspector path used: TODO
- Controlled remote sender: TODO
- Positive tool proof authorized: TODO
- Payment proof authorized beyond dry-run: NO

## Local Environment

- Repo path: TODO
- Bridge Python: TODO
- Hermes Python source: TODO
- Config used for first mailbox linking: `examples\agentverse-mailbox.yaml`
- Config used for real Hermes proof: `examples\agentverse-mailbox-hermes.yaml`
- Private allowlist config path, if used: TODO

## Preflight Commands

| Command | Exit code | Sanitized result |
| --- | ---: | --- |
| `python -m pytest -q` | TODO | TODO |
| `python -m ruff check .` | TODO | TODO |
| `python -m mypy src` | TODO | TODO |
| `python -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --probe-backend` | TODO | TODO |
| `python -m hermes_fetch_ai.cli doctor --config examples\agentverse-mailbox-hermes.yaml --contamination-scan` | TODO | TODO |
| `python -m hermes_fetch_ai.cli demo payment --config examples\payment-dry-run.yaml` | TODO | TODO |
| `python -m hermes_fetch_ai.cli demo mailbox --config examples\agentverse-mailbox-hermes.yaml --duration-seconds 5` without `UAGENT_SEED` | TODO | Expected fail-closed. |

## Mailbox Linking Evidence

- Command used: `python -m hermes_fetch_ai.cli serve --config examples\agentverse-mailbox.yaml`
- Agentverse/Inspector status: TODO
- Bridge/uAgent address or redacted identifier: TODO
- Screenshot/transcript stored elsewhere: TODO
- Secret redaction check completed: TODO

## Real Hermes Mailbox Evidence

- Command used: `python -m hermes_fetch_ai.cli serve --config examples\agentverse-mailbox-hermes.yaml`
- Backend probe result: TODO
- Bridge/uAgent address or redacted identifier: TODO
- `policy.public_tools` value: TODO
- Denied tools confirmed: TODO

## Remote Transcript

### `ListTools`

- Sender: TODO
- Response: TODO
- Expected: empty or minimal reviewed surface.

### Optional Positive `CallTool`

- Sender: TODO
- Tool: TODO
- Args summary: TODO
- Response summary: TODO
- Private allowlist config used: TODO
- Reason tool was safe: TODO

## Stop Conditions Encountered

- Paid quota prompt: TODO
- Wallet authorization prompt: TODO
- Production deployment prompt: TODO
- Secret-shaped output: TODO
- Unexpected public tool exposure: TODO
- Disk below 2 GB: TODO

## Final Evidence Verdict

- `BLOCKED_OPERATOR_ONLY`: TODO
- `DONE_AGREED`: TODO
- Remaining exact operator action: TODO
