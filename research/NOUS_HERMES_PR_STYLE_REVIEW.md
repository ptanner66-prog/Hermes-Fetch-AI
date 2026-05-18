# Nous Hermes PR Style Review

Source access: `gh` against `NousResearch/hermes-agent` succeeded. Inspected 20 recent merged PRs: #27189, #27188, #27187, #27185, #27184, #27176, #27175, #27162, #27151, #27110, #27105, #27104, #27102, #27101, #27069, #27055, #27053, #27051, #27050, #27035.

## PRs inspected

| PR | Title | Size/files | Pattern |
| --- | --- | --- | --- |
| #27189 | fix(compressor): strip historical media after compression | +382/-0, 2 files | Focused core fix plus regression test. |
| #27188 | feat(cli): add `hermes send` | +1091/-3, 6 files | CLI wrapper over existing send tool, docs, tests. |
| #27187 | fix(plugins): surface category-namespaced plugins | +200/-121, 10 files | Plugin CLI mirrors runtime loader; docs/tests. |
| #27185 | fix(agent): reset fallback index | +28/-0, 2 files | Tiny surgical bug fix plus regression. |
| #27184 | fix(xai): surface provider SSE error | +209/-0, 2 files | Provider edge case in core with test. |
| #27176 | feat(status): append session recap | +532/-0, 4 files | Folded into existing `/status`, not new command. |
| #27175 | feat(cli): background indicator | +129/-0, 2 files | Small UX using existing source of truth. |
| #27162 | fix(codex): rotate pool on 429 | +57/-2, 2 files | Runtime retry classification plus regression. |
| #27151 | fix(telegram): DM topic typing | +10/-17, 2 files | Minimal platform-specific fix. |
| #27110 | fix(xai): drop stale hint | +24/-118, 2 files | Removes editorialized stale behavior; notes what stays. |
| #27105 | fix(mcp): validate remote URLs | +207/-0, 2 files | Fail-fast at transport boundary plus tests. |
| #27104 | fix(moonshot): schema transform | +194/-0, 2 files | Provider-specific compatibility module. |
| #27102 | feat(gateway): memory logging | +398/-0, 4 files | Optional config-gated operational feature. |
| #27101 | feat(cli): `/exit --delete` | +150/-3, 4 files | Wires existing SessionDB API; docs/test. |
| #27069 | fix(update): stream npm output | +36/-6, 2 files | Targeted update UX; unrelated path untouched. |
| #27055 | fix(update): lazy-install Camofox | +110/-2642, 4 files | Optional dependency moved out of eager install. |
| #27053 | docs(release): expand highlights | +32/-35, 1 file | Teknium feedback: explain value to newcomers. |
| #27051 | fix(signal): groupV2 id | +172/-3, 2 files | Platform protocol drift fix plus tests. |
| #27050 | docs(tools): video docs | +17/-2, 2 files | User-facing docs gap only. |
| #27035 | docs(release): excitement framing | +34/-29, 1 file | Teknium feedback: lead with exciting things. |

## Maintainer style extracted

- Keep PRs narrow. Median inspected PR changed about two files and ~164 lines; larger changes explained why.
- Pair behavior changes with focused regression tests. 17 of 20 inspected PRs included tests.
- Put optional integrations behind existing surfaces: plugin, tool, config, or CLI command.
- Avoid eager optional dependencies. Lazy or extras-based install is preferred.
- Prefer “thin wrapper over existing X” to new subsystems.
- For config-gated runtime features, default off and document the config.
- Docs update when user-visible command/tool behavior changes.
- PR bodies explain root cause, change shape, what remains untouched, and exact validation commands.

## What not to touch

- Do not add a gateway platform adapter unless maintainers explicitly say uAgent traffic belongs in gateway platform routing.
- Do not copy this standalone repo into Hermes.
- Do not add wallet custody or payment settlement to Hermes core.
- Do not make Fetch/uAgents dependencies eager core dependencies.
- Do not change Hermes prompt/tool defaults or system-wide authorization semantics.
- Do not hardcode `~/.hermes`; Hermes code must use `get_hermes_home()` and `display_hermes_home()`.

## PR wording for Teknium

Recommended title:

`feat(plugins): add optional uAgents bridge proof for Hermes MCP tools`

Recommended framing:

Hermes remains the local execution agent. Fetch/uAgents supplies identity, discovery, signed addressing, transport/mailbox, and payment protocol rails. This PR adds a narrow, optional, default-off bridge surface that routes uAgent messages into existing Hermes MCP/tool boundaries without adding a new agent framework, wallet custody, or marketplace subsystem.

Use accepted style phrases:

- “Zero new platform code.”
- “Thin wrapper over existing Hermes MCP/tool surfaces.”
- “Optional dependency, default off.”
- “No wallet custody or real fund movement.”
- “What stays untouched: gateway platform adapters, core prompt/tool defaults, production payment settlement.”
