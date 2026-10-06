# Governance

Hermes Fetch AI is a standalone project with a thin Hermes plugin. It is kept small so that listing the plugin in Hermes adds little risk to Hermes.

## Principles

1. Hermes core stays unchanged unless Hermes maintainers ask for a core contribution.
2. Network exposure is opt-in.
3. Tool access is default-deny.
4. Secrets come from the environment, never from config files or examples.
5. Security claims need tests or documented procedures.
6. Residual risks are written down, not hidden.

## Maintainers

The project has one maintainer today. Changes to policy, replay protection, argument checks, redaction, subprocess handling, release workflows, or the examples need tests, and every change goes through a pull request with green CI. If a secret is ever exposed, it is rotated or revoked immediately. Confirmed vulnerabilities get a GitHub security advisory.

## Releases

1. Run the local gate in [`CONTRIBUTING.md`](CONTRIBUTING.md).
2. Set the release date in `CHANGELOG.md`.
3. Confirm that no build artifacts or secrets are staged and that the dependency-audit exceptions are still documented.
4. Once CI is green on `main`, tag `vX.Y.Z`. The release workflow verifies, builds, attests, and publishes the artifacts.

## Repository settings

- Pull requests required for `main`, with force pushes and deletion blocked.
- Required checks: `verify` (all six OS and Python jobs), `package smoke`, `test coverage`, `dependency audit`, both `hermes plugin + field test` jobs, and CodeQL.
- An approving review, once there is a second maintainer.
- `v*` tags protected.
- Dependabot security updates and private vulnerability reporting enabled.
