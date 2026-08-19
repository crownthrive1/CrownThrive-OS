# Phase 2.99 — GitHub Actions Node 24 Runtime, Self-Healing and Main Merge Perimeter

**Date:** 2026-08-19  
**State:** implementation/bootstrap packet; merge remains subject to governed validation/quorum state.

## Trigger

GitHub Actions surfaced Node 20 deprecation warnings for action dependencies. A temporary platform-side force to Node 24 was treated as warning evidence, not as proof that CrownThrive's workflow dependencies were actually migrated.

Concurrent reconciliation also found that PR #63 had already advanced `actions/checkout` and `actions/setup-python` to v7 and had correctly moved CodeQL to the repository's provider-managed default setup. That work was preserved rather than overwritten.

A subsequent provider audit identified a second enforcement gap: canonical `main` reported `protected=false`, branch protection disabled, status-check enforcement off and zero required checks. CrownThrive therefore had strong Governance-as-Code detection without a GitHub-enforced fail-closed merge perimeter.

## Reconciled runtime implementation

- `actions/checkout` is pinned to `3d3c42e5aac5ba805825da76410c181273ba90b1` (`v7.0.1`, Node 24).
- `actions/setup-python` is pinned to `5fda3b95a4ea91299a34e894583c3862153e4b97` (`v7`, Node 24).
- Dependency Review moves to `a1d282b36b6f3519aa1f3fc636f609c47dddb294` (`v5.0.0`, Node 24).
- CodeQL remains provider-managed default setup; duplicate advanced CodeQL workflow actions remain prohibited.
- every remote workflow action is full-SHA pinned;
- the Node-24/runtime/supply-chain validator runs in Documentation Governance, Security Governance and the stable Governed Merge Gate;
- Node-runtime forcing/unsafe escape hatches and unverified self-hosted runners fail closed;
- Dependabot is configured for daily GitHub Actions update proposals;
- dependency self-healing remains pull-request based, with no direct-to-main mutation;
- agent-sovereign governance requires the runtime gate before merge;
- Phase 2.99 exit and Phase 3 entry remain blocked on runtime/supply-chain drift.

## Always-run merge-gate bootstrap

The packet adds `.github/workflows/governed-merge-gate.yml` with the stable job context:

`CrownThrive governed merge gate`

It runs on every pull request without path filtering and re-executes the deterministic institutional, Collab, registry, API/MCP, security, runtime, repository-enforcement, dependency-review, whitespace and conflict controls.

Documentation Governance and Security Governance are also changed so their pull-request workflows emit on every PR. Push-to-main path filtering remains available for efficient post-merge revalidation, but a future required PR check can no longer be stranded because a pull-request path filter skipped the workflow.

## GitHub main enforcement target

`developers/manifests/github-main-enforcement-target.v1.json` now records the provider target:

- pull request required before merge;
- required status `CrownThrive governed merge gate`;
- strict/current-with-main status enforcement;
- force pushes blocked;
- branch deletion blocked;
- routine administrative bypass disabled;
- bypass limited to explicit D3 break-glass authority with evidence and post-event revalidation.

GitHub remains technical infrastructure and provider evidence, not CrownThrive's sovereign authority. CT-ADR-GOV-011 quorum, Agent D, specialist, risk, rollback, documentation/downstream and reserved D3 controls remain independently required.

The current observed provider state remains unprotected until GitHub repository settings are changed and independently re-read. This PR is the bootstrap that must land before the stable required check can be safely configured on `main`. After bootstrap merge, provider enforcement becomes a separate hard activation/verification step and Phase 3 remains blocked until it passes.

## Self-healing model

The repair loop is detect → propose → verify upstream → reconcile policy and workflow → rerun original runtime gate → rerun institutional/security suites → independent verification → quorum/authority decision.

A warning cannot be healed by suppressing the warning, forcing an outdated action to a runtime, weakening the validator or auto-merging an unverified dependency update.

Likewise, a repository-enforcement gap cannot be “fixed” by merely documenting that a ruleset should exist. Provider state must be enabled, independently observed and validated after this bootstrap is merged.

## Downstream effect

Phase 3 inherits immutable action references, Node-24-compatible action lines, runner attestation and a required GitHub main merge perimeter. Later phases inherit the same pattern for CI/CD, deployment, adapter, package and infrastructure automation so provider/toolchain drift cannot silently alter CrownThrive institutional execution.
