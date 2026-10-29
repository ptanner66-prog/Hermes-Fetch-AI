# Integration verification — 2026-10-29

This records verification of the unreleased 1.0.0 integration on branch
`codex/finish-hermes-fetch`, based on PR #28 at
`8f039f26f11db9cd750ac9c7c008f6105cbaa569`. The earlier working checkout and its
uncommitted changes were preserved separately and checked against their backup.

## Changes verified

- Replay and rate-limit caches retain live entries and refuse excess admissions
  rather than losing protection at capacity. URL validation handles malformed,
  nested, and protocol-relative inputs; numeric time limits must be finite.
- Payment reconciliation checks the locally signed transaction hash and exact
  transfer. An uncertain broadcast keeps its spending reservation across day
  boundaries and is never automatically sent again.
- Daily service quotas are reserved atomically before execution. Refusing a run
  preserves paid retry credit. An authenticated buyer can retrieve an existing
  cached answer after the quota is exhausted without consuming another run.
- Background bridges hold an operating-system lock, identify processes by birth
  time, and accept stop requests only for the intended process. Windows virtual
  environment launchers are handled explicitly.
- Windows service runners place their descendants in a Job Object before the
  target program starts. Tests exercise timeout, cancellation, and normal exit.
- MCP initialization has a separate 60-second startup budget; tool deadlines
  apply to both backends. Cancelled initialization releases its resources.
- Local model review refuses redirects and credential-bearing URLs and bounds
  response size. Buying control messages validate token and response types.
- MCP is upgraded to 1.30.0, dependencies are locked, CI covers stacked PRs,
  Actions are pinned by commit, and publication depends on CI and CodeQL.

## Local gates

These results were obtained locally. Earlier runs made while implementation was
changing are retained as diagnostic evidence and are not acceptance results.

| Gate | Result |
| --- | --- |
| Windows Python 3.11.15 full suite | 822 passed, 22 skipped; 92.60% coverage, above the 90% gate |
| Windows Python 3.12.13 full suite on frozen source | 823 passed, 21 skipped |
| Ubuntu 24.04 / Python 3.12.3 process lifecycle checks | 15 passed in the HP's existing WSL environment; copied production source matched byte for byte |
| Ruff lint and formatting | Passed; 144 Python files checked for formatting |
| Strict mypy | Passed; 107 source files |
| Universal lock consistency | Passed |
| Doctor and public-tree contamination check | Passed |
| Four offline demos | Passed on Python 3.12 and from the independently installed wheel |
| Built wheel | Fresh installation outside the checkout passed dependency consistency, bundled config, doctor, and all four demos; all 46 package source/data files matched the final tree |
| Windows background lifecycle | 23 passed, including concurrent ownership, crash recovery, start/restart/stop, and targeted stop requests |
| Independent implementation review | Passed; two reproduced findings fixed and independently rechecked |

The Python 3.11 full run began before the last background-process adjustment
(excluding zombie processes and avoiding reaping a caller-owned child on POSIX).
The final background suite was then run separately: all 23 cases passed. The
coverage percentage is the observed whole-run result, not a separately recomputed
percentage for that later adjustment.

The later clean Python 3.12 run covered the frozen production source. The Linux
subset also exercised the final POSIX change: forced shutdown preserves the
caller's child exit status. Windows startup test fixtures now use the production
readiness/stop budgets, retain startup diagnostics, and wait for the actual
interpreter child when cleaning up a virtual-environment launcher.

The 21 skips in the final Python 3.12 run comprise eight real-Hermes opt-in cases
(run separately below), five live-testnet cases, and eight platform-dependent
cases. All 112 production/test file hashes were unchanged during that run.

The independent review covered runtime and security changes, the new Windows
helper, payment and quota boundaries, CI/release configuration, and wheel-test
isolation. Its final focused run passed nine tests; an earlier independent
71-test run exercised the remaining changed boundaries. This is a bounded review,
not a claim that every possible defect has been eliminated.

## Real Hermes integration

Both Hermes installations were isolated from the user's existing installation.
Model-backed field tests used a loopback model fixture, without spending API
credits. They exercise real Hermes code, but do not establish hosted model quality
or a completed interaction with a human approving a payment.

| Hermes target | Verification |
| --- | --- |
| 0.21.5, `f97608f178d1ffeca59860195ab7da295f7c8e5f`, Python 3.11 | All eight field cases passed across the seven-case run and the final stdio rerun. Native plugin validate, doctor, enable, bridge doctor, and local demo passed. |
| Pinned main, `bb2362878b33e14e8b7d24d621510e087269fdce`, Python 3.14.6 | Eight field tests passed together. The same native plugin and CLI checks passed. |

The release's first stdio attempt exceeded the former startup deadline. The final
rerun passed with the separate startup budget. The ordinary tool deadline remains
10 seconds by default.

## Dependency audit

The final dependency audit passes with only the two existing upstream exceptions
documented in [security.md](security.md): ecdsa's unresolved Minerva timing issue
and cosmpy's PyNaCl 1.6.0 pin. The unfiltered audit still reports these issues,
including advisory aliases. No new exception was added. A passing exception-aware
audit does not mean the dependency graph has no known vulnerabilities.

## Boundaries of this verification

- No branch was pushed, PR merged, release tagged, PyPI package published, or
  upstream catalog submission sent as part of this local verification.
- The configured GitHub matrix and CodeQL must run on the eventual submitted
  commit. The focused Linux run is not the complete Linux matrix; macOS was not
  executed locally.
- Live Dorado transactions were not repeated. The October 6 testnet reports
  remain historical evidence, not verification of this revision.
- Agentverse mailbox delivery, a real ASI:One purchase, and a human answering the
  Hermes payment prompt remain live-trial requirements. A hosted listing or
  simulated payment does not satisfy them.
- Mainnet remains disabled. Publishing a testnet release does not authorize or
  complete the separate [mainnet requirements](agent-economy.md#before-mainnet).

The local evidence bundle retains original-state backups, diagnostic and final
test logs, JUnit results, coverage reports, dependency audits, the independent
review, source hashes, and built package checksums. It is separate from the public
package because raw machine paths and diagnostic logs are not product content.
