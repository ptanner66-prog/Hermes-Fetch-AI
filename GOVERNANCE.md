# Governance

Hermes Fetch AI is a standalone plugin project. Its goal is to be small enough for Hermes maintainers to bless or list without inheriting unnecessary core risk.

## Project principles

1. Hermes core stays unchanged unless maintainers explicitly request a core contribution.
2. Network exposure is opt-in.
3. Tool access is default-deny.
4. Production secrets come from the environment, never YAML examples.
5. Security claims require tests or documented operator procedures.
6. Residual risks are documented rather than hidden.

## Maintainer responsibilities

Maintainers should:

- keep CI, CodeQL, dependency audit, and package checks green;
- require review for changes to policy, replay protection, validation, redaction, subprocess handling, release workflows, and examples;
- rotate or revoke any accidentally exposed secret immediately;
- publish security advisories for confirmed vulnerabilities;
- keep the upstream Hermes contribution path aligned with Hermes plugin policy.

## Release process

1. Run the full local gate in `CONTRIBUTING.md`.
2. Confirm no untracked build artifacts or secrets are staged.
3. Confirm dependency-audit exceptions are documented.
4. Tag with `vX.Y.Z` only after CI is green on `main`.
5. Let the release workflow build, verify, attest, and publish artifacts.

## Required repository settings

Before public release, configure GitHub rulesets/branch protection:

- PR required for `main`.
- Required checks: CI matrix, security-audit, package, CodeQL.
- At least one approving review.
- Dismiss stale approvals.
- Block force pushes and deletions.
- Protect or require review for `v*` tags.
- Enable Dependabot security updates and GitHub Security Advisories.
