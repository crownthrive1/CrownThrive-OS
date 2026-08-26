# CHLOM Wallet Continuity — Penta Phase 3

## Purpose

This packet preserves the deterministic Wallet continuity algorithms while reconciling execution ownership to the current Penta control plane.

## Current operating truth

- The legacy `chlom_wallet` continuity schema remains live as a shared continuity substrate.
- The historical Wallet Phase-E suites remain `CONTROLLED_TEST`; they are not the latest suite and do not grant production authority.
- The observed hourly continuity cron remains active and healthy at the dated August 26, 2026 readback.
- The latest observed suite in the shared substrate is the PentaGreen lineage under the legacy ThriveEvergreen runtime identifier.
- The historical Phase-E SQL MUST NOT be replayed as a production migration.
- No API or MCP runtime release is asserted by this source packet.

## Penta ownership

- PentaNurture — continuity maintenance, drift, recovery-plan stewardship.
- PentaStatus — current-state projection and readback.
- PentaCredentials — credentials and server-binding readiness.
- PentaCertify — exact-operation certification before runtime enablement.
- PentaFactory / PentaBuild — software, adapters, and candidate projections.
- PentaTriage — incident routing.
- CHLOM — authority/governance boundary.

## Fail-closed boundaries

The eight historical continuity MCP tool identities are retained for compatibility but remain disabled until a current MCP/server binding and exact-scope certification exist. This packet does not authorize provider writes, money movement, rights grants, chain broadcasts, destructive recovery, checkout, credential disclosure, authority manufacture, AI final authority, or production activation.

## Verification

`test-continuity-penta-v2.mjs` verifies the deterministic invariants and the current compatibility contract. `continuity-chaos-v1.mjs` retains the 50,000-case fail-closed chaos test.

The dated runtime evidence file is evidence, not evergreen truth; PentaStatus must refresh it before any later production decision that depends on runtime state.
