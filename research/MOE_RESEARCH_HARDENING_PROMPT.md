You are Hermes running a second-stage MOE research and hardening pass after the final-boss implementation pass.

Working directory:
C:\Users\ptann\OneDrive\Work\Hermes Fetch AI

Related Hermes upstream checkout:
C:\Users\ptann\OneDrive\Work\hermes-agent-main

This pass must harden the project after the implementation run. Treat the current implementation and research as draft material to be audited, simplified, and upgraded. Do not stop at "looks good"; prove it.

Runtime requirement:
This run should be launched with the strongest available Hermes runtime settings: `model=gpt-5.5`, `provider=openai-codex`, `api_mode=codex_responses`, and `reasoning_config={"enabled": true, "effort": "xhigh"}`. Record the observed/declared runtime in `research/MOE_HARDENING_STATUS.md`. If the launcher did not provide these settings, stop and say so.

Known final-boss blockers to fix first:
- `research/FINAL_BOSS_STATUS.md` was not written.
- The mailbox proof reported success while a child process emitted an import traceback involving `cosmpy` and `google.protobuf`.
- Mailbox child-process startup failure must propagate to the parent; do not allow a false-green mailbox demo.
- Full verification was not completed.
- No commit/push state was finalized.

Primary source anchors:
- Fetch.ai GitHub organization: https://github.com/fetchai
- Fetch.ai homepage / developer platform: https://www.fetch.ai/
- Fetch concepts: https://fetch.ai/docs/concepts
- Fetch Network docs: https://network.fetch.ai/docs
- Agentverse docs: https://docs.agentverse.ai/
- Agentverse A2A external agent docs: https://docs.agentverse.ai/documentation/launch-agents/external-agents/a-2-a-agents
- Agentverse Almanac manifest docs: https://docs.agentverse.ai/api-reference/almanac/get-manifest
- uAgents source: https://github.com/fetchai/uAgents
- cosmpy source: https://github.com/fetchai/cosmpy
- fetchd source: https://github.com/fetchai/fetchd
- ASI Alliance wallet source: https://github.com/fetchai/asi-alliance-wallet
- Nous Hermes upstream: https://github.com/NousResearch/hermes-agent

Non-negotiable end goal:
Hermes must connect natively to Fetch in a way that unlocks the agentic economy: discovery, manifests, addressability, structured agent-to-agent messages, safe remote invocation of allowed Hermes capabilities, optional payment negotiation, and a narrow upstream Hermes PR that Teknium could actually accept.

Use an explicit MOE strategy. Write `research/MOE_HARDENING_REPORT.md` with one section per expert lane, then a final integrated decision.

Expert lanes:

1. Teknium / Hermes maintainer persona
   - Think like the maintainer receiving the PR.
   - Minimize diff size.
   - Respect Hermes plugin/CLI/profile/config/test conventions from `C:\Users\ptann\OneDrive\Work\hermes-agent-main\AGENTS.md`.
   - Reject anything that feels like a wholesale standalone repo dump.
   - Require clean docs, exact optional dependency boundaries, and no hardcoded plugin-specific core hacks.
   - Decide the smallest Hermes-native upstream slice.

2. Senior Fetch.ai engineer persona
   - Think like someone who knows uAgents, Agentverse, Almanac, A2A, payment protocols, wallet/network realities, and agent discovery.
   - Use Fetch.ai GitHub and docs, not vague memory.
   - Confirm whether the project uses existing Fetch rails correctly.
   - Identify missing native pieces: manifests, protocol digests, Agentverse launch, A2A adapter, endpoint/mailbox/proxy registration, payment models, settlement boundaries.
   - Reject any fake "full connection" claim.

3. Security / abuse-resistance reviewer
   - Treat Agentverse/uAgent identity as routing identity, not authorization.
   - Review tool allowlists, denied side-effecting Hermes tools, redaction, audit, payment authorization, replay/idempotency, rate limits, schema/model digest validation, network calls, secret handling, and CI isolation.
   - Check that payment never automatically authorizes dangerous tool calls.

4. Product / agentic-economy reviewer
   - Ask whether the demo actually shows the economy: discoverable Hermes agent, filtered capabilities, request/quote/commit/complete dry-run, audit trail, and operator path to hosted proof.
   - Make docs useful for a CEO demo without hype or unsupported claims.

5. Release / CI reviewer
   - Run tests.
   - Verify Windows commands.
   - Verify local fake, real Hermes stdio, payment dry-run, mailbox-startup or exact hosted blocker.
   - Verify no forbidden files, logs, caches, secrets, or private content are staged.

Research tasks:

1. Fetch GitHub sweep:
   - Inspect the Fetch org and identify which repos matter to this integration.
   - At minimum cover `uAgents`, `cosmpy`, `fetchd`, `asi-alliance-wallet`, and any Agentverse/API/client repo that is current and relevant.
   - Record in `research/FETCH_GITHUB_SWEEP.md`:
     - repo URL;
     - relevance;
     - exact source/docs files inspected;
     - what should affect Hermes Fetch AI;
     - what is explicitly out of scope for the first PR.

2. Hermes upstream sweep:
   - Inspect current NousResearch/hermes-agent source and recent merged PRs.
   - Validate the upstream shape against actual code.
   - Record in `research/HERMES_UPSTREAM_SWEEP.md`.

3. Full connection gap audit:
   - Update or create `research/FULL_CONNECTION_GAP_AUDIT.md`.
   - Include a table: capability, current proof, missing proof, owner, exact next command/file, upstream PR relevance.
   - Capabilities must include:
     - uAgent identity/addressing;
     - endpoint mode;
     - mailbox mode;
     - proxy mode if relevant;
     - Agentverse launch;
     - A2A external-agent path;
     - Almanac registration;
     - manifest upload;
     - manifest lookup by digest/name;
     - protocol model lookup;
     - MCP tool list/call;
     - Hermes MCP stdio;
     - payment request/commit/complete/cancel/reject dry-run;
     - real FET/payment operator boundary.

4. Code hardening:
   - Clean any drafty code from the final-boss run.
   - Keep the bridge thin.
   - Add tests if the audit finds missing safety or proof.
   - Do not expand into real wallet custody, production spend, or broad marketplace.

5. Upstream PR hardening:
   - Update `research/UPSTREAM_PR_EXECUTION_PLAN.md`.
   - Add `research/TEKNIUM_PR_ONE_PAGER.md` with:
     - one-line thesis;
     - why Fetch is the right native rail;
     - why the PR is small;
     - exact files;
     - tests;
     - demo commands;
     - what is deliberately out of scope;
     - maintainer questions and crisp answers.

Verification commands:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src\hermes_fetch_ai --ignore-missing-imports
.\.venv\Scripts\python.exe -m hermes_fetch_ai.cli doctor --contamination-scan
$env:HERMES_FETCH_HERMES_PYTHON='C:\Users\ptann\OneDrive\Work\hermes-agent-main\.venv\Scripts\python.exe'
.\.venv\Scripts\python.exe -m hermes_fetch_ai.cli doctor --config examples\hermes-stdio-env.yaml --probe-backend
.\.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo hermes --config examples\hermes-stdio-env.yaml
.\.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo payment-dry-run --config examples/payment-dry-run.yaml
.\.venv\Scripts\python.exe -m hermes_fetch_ai.cli demo mailbox --config examples/agentverse-mailbox-hermes.yaml --duration-seconds 1
```

If mailbox startup requires `UAGENT_SEED`, do not invent one unless the config supports safe dev mode. If operator-owned setup is required, keep the blocker exact and do not ask for secrets.

Final acceptance:
- MOE report exists and is adversarial.
- Fetch GitHub sweep exists.
- Hermes upstream sweep exists.
- Full connection gap audit exists.
- Teknium PR one-pager exists.
- Tests and verification commands pass, or every failure is operator-owned and documented with exact next action.
- No real FET moved.
- No secrets inspected, printed, stored, or committed.
- Final status updated in `research/MOE_HARDENING_STATUS.md`.
- Commit locally if safe. Attempt push only if environment allows it; record if blocked.
