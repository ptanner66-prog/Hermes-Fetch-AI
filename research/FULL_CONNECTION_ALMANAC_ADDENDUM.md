# Full Connection Almanac Addendum

Operator note, 2026-05-16:
The end goal is not only a mailbox demo. It is a full Hermes-native Fetch connection that can support the agentic economy: discoverability, manifests, protocol/model introspection, messaging, and safe payment negotiation.

## Required Agentverse / Almanac API source anchors

- Get manifest by digest:
  https://docs.agentverse.ai/api-reference/almanac/get-manifest
  - `GET https://agentverse.ai/almanac/manifest/:digest`
  - Digest path parameter must match a 64-character lowercase hex digest.
  - Response contains manifest `version`, `metadata`, `models`, `interactions`, `nodes`, and `edges`.

- Get manifest by name:
  https://docs.agentverse.ai/api-reference/almanac/get-manifest-by-name
  - `GET https://agentverse.ai/almanac/manifest/name/:name`
  - Returns the latest version for that manifest name.

- Upload manifest:
  https://docs.agentverse.ai/api-reference/almanac/upload-manifest
  - `POST https://agentverse.ai/almanac/manifest`
  - Used to publish protocol manifests; source docs currently describe the request body broadly, so implementation must verify shape from Fetch/uAgents source or runtime before relying on it.

- Get protocol model:
  https://docs.agentverse.ai/api-reference/almanac/get-protocol-model
  - `GET https://agentverse.ai/almanac/manifest/model/:digest`
  - Digest path parameter must match a 64-character lowercase hex digest.

## Acceptance impact

The final boss run must not call the integration "full connection" unless it explicitly answers:

1. How the Hermes Fetch AI bridge publishes or reuses a uAgent protocol manifest.
2. How a remote agent discovers the bridge and its protocol by name or digest.
3. How protocol model digests map back to the `ListTools`, `CallTool`, payment, and response message schemas.
4. Whether `uagents` / `uagents-core` already uploads manifests automatically when `publish_manifest=true`, and what exact config is required.
5. Whether the standalone repo needs a manual `manifest inspect`, `manifest upload`, or `manifest verify` command.
6. How Agentverse/Almanac discovery is used as identity and routing metadata, not authorization.
7. How this maps to the simplified upstream Hermes PR.

Do not ship a fake manifest story. If current Fetch/uAgents handles manifest publication automatically, prove it from source and document the proof. If a thin manual verification command is needed, implement it without secrets and with tests that mock network calls.
