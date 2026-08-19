# Phase 2.99 — GitHub Actions Node 24 Runtime and Self-Healing Gate

**Date:** 2026-08-18  
**State:** implementation packet; merge remains subject to governed validation/quorum state.

## Trigger

GitHub Actions surfaced Node 20 deprecation warnings for action dependencies. A temporary platform-side force to Node 24 was treated as warning evidence, not as proof that CrownThrive's workflow dependencies were actually migrated.

Concurrent reconciliation also found that PR #63 had already advanced `actions/checkout` and `actions/setup-python` to v7 and had correctly moved CodeQL to the repository's provider-managed default setup. That work was preserved rather than overwritten.

## Reconciled implementation

- `actions/checkout` is pinned to `3d3c42e5aac5ba805825da76410c181273ba90b1` (`v7.0.1`, Node 24).
- `actions/setup-python` is pinned to `5fda3b95a4ea91299a34e894583c3862153e4b97` (`v7`, Node 24).
- Dependency Review moves from v4 to `a1d282b36b6f3519aa1f3fc636f609c47dddb294` (`v5.0.0`, Node 24).
- CodeQL remains provider-managed default setup; duplicate advanced CodeQL workflow actions remain prohibited.
- every remote workflow action is full-SHA pinned;
- the Node-24/runtime/supply-chain validator runs in Documentation Governance and Security Governance;
- Node-runtime forcing/unsafe escape hatches and unverified self-hosted runners fail closed;
- Dependabot is configured for daily GitHub Actions update proposals;
- dependency self-healing remains pull-request based, with no direct-to-main mutation;
- agent-sovereign governance now requires the runtime gate before merge;
- Phase 2.99 exit and Phase 3 entry remain blocked on runtime/supply-chain drift.

## Self-healing model

The repair loop is detect → propose → verify upstream → reconcile policy and workflow → rerun original runtime gate → rerun institutional/security suites → independent verification → quorum/authority decision.

A warning cannot be healed by suppressing the warning, forcing an outdated action to a runtime, weakening the validator or auto-merging an unverified dependency update.

## Downstream effect

Phase 3 inherits immutable action references, Node-24-compatible action lines and runner attestation. Later phases inherit the same pattern for CI/CD, deployment, adapter, package and infrastructure automation so provider/toolchain drift cannot silently alter CrownThrive institutional execution.
