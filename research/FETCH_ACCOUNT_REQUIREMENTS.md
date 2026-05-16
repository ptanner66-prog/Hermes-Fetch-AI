# Hosted Fetch account requirements

The local test and local demo do not require a hosted account, mailbox, wallet balance, ASI key, or FET.

For a manual hosted Agentverse mailbox demo, the operator must provide:

1. Fetch.ai / Agentverse account access.
2. A uAgent seed supplied as an environment variable named UAGENT_SEED. Do not put it in YAML, docs, shell history, or commits.
3. A mailbox-enabled Agentverse agent entry or mailbox key associated with that account, if required by the current Agentverse UI.
4. Any testnet address or wallet setup required by the current Agentverse onboarding flow.
5. Any required testnet FET funding for hosted registration if Agentverse asks for it. Local CI must not depend on funding.

PowerShell example using a placeholder only:

$env:UAGENT_SEED = "replace-with-your-own-seed"
python -m hermes_fetch_ai.cli doctor --config examples/agentverse-mailbox.yaml
python -m hermes_fetch_ai.cli demo mailbox

Never share the real seed, mailbox key, recovery phrase, private key, API key, or funding transaction secrets with the agent.
