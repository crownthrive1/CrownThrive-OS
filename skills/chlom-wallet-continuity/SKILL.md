# CHLOM Wallet Continuity — Penta Skill

## Purpose

Operate and reconcile the Wallet continuity control plane without reviving obsolete Phase-E authority assumptions.

## Current baseline

The `chlom-wallet-continuity` Supabase Edge Function is a production-available private server-to-server control plane. Its eight HTTP/MCP operations are service-role-only. The underlying continuity suite remains controlled-test and no privileged authority is implied by service availability.

## Required behavior

1. Read current source head and ThriveBase/Edge state before making a runtime claim.
2. Treat historical Wallet Phase-E suites, Gen6 agent bindings, counts, and automations as lineage unless fresh PentaStatus evidence proves current relevance.
3. Preserve deterministic invariants: freshness, heartbeat validity, read-only oracle enforcement, strictest ECAC/HOLD/DENY composition, fail-closed recovery planning, and advisory-only scoring.
4. Route maintenance/drift to PentaNurture; status to PentaStatus; credential health to PentaCredentials; operation certification to PentaCertify; software/adapters to PentaFactory/PentaBuild; incidents to PentaTriage.
5. Keep the production control plane private. Never expose service-role credentials or relax JWT/service-role enforcement to make a client integration easier.
6. Never replay historical Phase-E SQL over the shared continuity substrate without a new, explicit migration and independent certification.
7. Never manufacture provider-write, money, rights, chain, destructive-recovery, checkout, D3, voting, self-approval, phase-advance, or final-authority permissions.
8. ECAC recovery output is plan eligibility only, never execution authority.
9. Stale/ambiguous evidence resolves to HOLD; explicit forbidden boundaries resolve to DENY.
10. GitHub startup/queue failures must remain reported as provider failures; resilience verification may supplement them but never relabel them.

## Production change prerequisites

Any change that expands beyond the current private service envelope requires current provider readback, PentaCredentials readiness, exact-operation PentaCertify evidence, rollback/backup evidence when applicable, and CHLOM authority for the exact source head and operation.
