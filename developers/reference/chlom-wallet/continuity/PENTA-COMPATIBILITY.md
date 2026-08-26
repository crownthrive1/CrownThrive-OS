# CHLOM Wallet Continuity — Penta Phase 3

## Production state

CHLOM Wallet Continuity is a **production-available private control-plane service**. The provider binding is the Supabase Edge Function `chlom-wallet-continuity`, observed `ACTIVE` with `verify_jwt=true` plus an in-function service-role equality gate. The eight HTTP/MCP continuity operations are bound for server-to-server use only.

Production service availability does **not** manufacture operational authority. The latest continuity suite remains `CONTROLLED_TEST`; provider writes, money movement, rights grants, chain broadcasts, destructive recovery, checkout, credential return, AI final authority, and autonomous production activation remain false.

## Penta ownership

- PentaNurture — continuity maintenance, drift, and recovery-plan stewardship.
- PentaStatus — fresh runtime readback and status projection.
- PentaCredentials — credential and server-binding health.
- PentaCertify — exact-operation certification and certification evidence.
- PentaFactory / PentaBuild — software, adapters, and candidate projections.
- PentaTriage — incident routing.
- CHLOM — authority/governance boundary.

## Live evidence

The August 26, 2026 certification verified service-role-only RPC execution, ECAC for fresh evidence, HOLD for stale or invalid freshness, an ECAC continuity truth tick with zero stale agents/source mismatches/unresolved oracles/dependency holds, and a reversible recovery canary that remained HOLD with execution authorization and destructive action both false. The canary ran inside a transaction and left zero residue.

The legacy `chlom_wallet` continuity schema remains a shared continuity substrate. Historical Wallet Phase-E 600-asset/48-component suites and Gen6 agent bindings remain dated `CONTROLLED_TEST` lineage and are not current production authority. The latest suite observed in the shared substrate is PentaGreen lineage under the legacy ThriveEvergreen runtime identifier.

## Source reconciliation

The safe Edge implementation from the Phase-E lineage is preserved in this successor under `supabase/functions/chlom-wallet-continuity/`. Historical Phase-E SQL is intentionally **not** replayed. Source presence never expands privileges.

## Verification

- `test-continuity-penta-v2.mjs` validates deterministic invariants plus the production-private binding contract.
- `continuity-chaos-v1.mjs` executes 50,000 deterministic fail-closed cases and requires zero unsafe ECAC and zero invariant failures.
- `continuity-runtime-certification-20260826.penta.json` is the PentaCertify evidence packet for the private production service.

GitHub-hosted workflow startup failure is provider/scheduler evidence, not a semantic pass. Exact Git objects were independently executed and the provider/runtime canaries were separately verified; no failed GitHub run is relabeled as successful.
