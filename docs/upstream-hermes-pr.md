# Upstream Hermes PR shape

Preferred upstream shape: a Hermes-native uAgents serve command or plugin that constructs a bridge protocol around Hermes' existing tool registry and pre/post tool-call hooks.

A platform adapter should remain a fallback only if maintainers request that shape.

Suggested properties:

- Optional dependency group for Fetch/uAgents packages.
- Reuse Hermes configuration, redaction, and tool authorization hooks.
- Keep chat out of the first bridge surface unless maintainers explicitly request it later.
- Import uAgents adapter protocol models with attribution to their package license.
- Do not port private research prompts, audit notes, vendored evidence, or local-only investigation artifacts.
