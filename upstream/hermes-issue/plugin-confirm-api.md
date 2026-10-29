# Hermes feature request: a plugin API to ask the user to confirm

Ready to post at <https://github.com/NousResearch/hermes-agent/issues/new?template=feature_request.yml>
from the repository owner's account. Hermes' catalog rule 9 asks for exactly this ("If the hook you
need does not exist, open an issue describing it: we would rather add the seam than list a patch"),
and `CONTRIBUTING.md` calls it a request to widen the generic plugin surface with a new `ctx` method.
Search the issues for "confirm" and "elicitation" first, in case one already exists.

Checked against hermes-agent `main` at `bb236287` and 0.21.5 on 2026-10-06; re-check the function
names before posting.

**Title:** `[Feature]: ctx.confirm(), a plugin API to ask the user before an irreversible action`

**Feature Type:** Developer experience (tests, docs, CI). The template has no plugin option; say so in
the description.

**Scope:** Small (single file, < 50 lines): a wrapper over the existing elicitation path, plus tests
and docs.

**Contribution:** tick "I'd like to implement this myself and submit a PR" only if you mean to.

---

### Problem or Use Case

Some plugin tools do things the user cannot take back: pay another agent, send a message in the
user's name, delete remote data. Such a tool should ask the user every time, even in YOLO mode, and
never remember the answer. Plugins have no supported way to do that today:

- The documented route, a `pre_tool_call` hook that returns `approve`, goes through the approval
  gate, which approves on its own under YOLO and after an "always" answer. That is right for terminal
  commands and wrong for a payment.
- `input()` inside a tool does not reach the TUI or the messaging gateways, and blocks unattended
  runs.

[fetchai-bridge](https://github.com/ptanner66-prog/Hermes-Fetch-AI/tree/main/hermes-plugin/fetchai-bridge),
a catalog candidate that lets Hermes pay other agents on Fetch.ai's testnet, works around this by
calling two internals:

- `tools.approval_prompt.request_elicitation_consent(message, description, title=...)`, the MCP
  elicitation prompt: shown on the surface that owns the session, even in YOLO mode, with no "always",
  failing closed (decline) when nobody can answer, and returning `accept`, `decline`, or `cancel`;
- `tools.approval.is_approval_bypass_active()`, to refuse to work with other agents at all while YOLO
  is on.

Both do what is needed on 0.21.5 and `main` (on 0.21.5 the classic CLI declines without showing the
prompt; the TUI and the gateways show it), and the plugin's CI field-tests them on both. But they are
not a published plugin API, so the plugin checks the prompt's signature on every call and refuses to
pay if anything changed. Under `plugins.isolation: host` the tools run in a process that cannot see
the session, so the plugin refuses there too.

### Proposed Solution

Two small additions to the plugin context, thin wrappers over what already exists:

```python
ctx.confirm(
    title: str,
    message: str,
    details: str = "",
    *,
    timeout_seconds: int | None = None,
) -> Literal["accept", "decline", "cancel"]

ctx.approvals_bypassed() -> bool | None  # read-only: is YOLO or approvals.mode: off in effect?
```

`ctx.confirm()` would behave like `request_elicitation_consent` does today:

- shown on the surface that owns the session (TUI, classic CLI, messaging gateways, a `/v1/runs` run
  with an approval callback), even in YOLO mode;
- never remembered, with no "always" choice;
- `decline` at once, never blocking, when nobody can answer (cron, `-q`, a gateway without a notify
  callback) or on timeout;
- under `plugins.isolation: host`, either routed to the session that owns the call or `decline`,
  documented either way.

`ctx.approvals_bypassed()` returns `None` when the plugin cannot know (for example in the plugin
host), so a careful plugin can refuse.

### Alternatives Considered

- **`pre_tool_call` returning `approve`:** auto-approves under YOLO and after "always", so a payment
  could go through unasked.
- **`input()` in the tool:** does not reach the TUI or gateways, and hangs unattended runs.
- **Keep calling the internals:** works today; a refactor would make the plugin refuse to pay (it
  fails closed) until it is updated, and the plugin host stays out of reach.

A public `ctx.confirm()` keeps the safety properties in Hermes, where they are maintained and tested,
and gives every plugin that moves money, sends messages, or deploys the same prompt.

### Debug Report

Not applicable. The plugin's field test shows the current behavior on both versions:
[`tests/test_field_hermes_buyer.py`](https://github.com/ptanner66-prog/Hermes-Fetch-AI/blob/main/tests/test_field_hermes_buyer.py).
