# CHLOM Wallet Continuity — Penta Skill

## Purpose

Use this skill to reconcile Wallet continuity state without replaying obsolete Phase-E runtime assumptions.

## Required operating behavior

1. Read current source head and current ThriveBase continuity state before making a runtime claim.
2. Treat historical Wallet Phase-E suites, Gen6 agent bindings, asset counts, and automation rows as lineage unless current PentaStatus readback proves they remain current.
3. Preserve deterministic continuity invariants: evidence freshness, heartbeat freshness, read-only oracle validation, strictest-disposition composition, fail-closed recovery eligibility, and advisory-only risk scoring.
4. Route continuity maintenance/drift to PentaNurture, current-state projection to PentaStatus, credentials/server readiness to PentaCredentials, exact-operation certification to PentaCertify, software/adapters to PentaFactory/PentaBuild, and incidents to PentaTriage.
5. Never enable an MCP tool or API route from source presence alone.
6. Never replay historical Phase-E SQL over the shared continuity substrate without an explicit current migration plan and independent certification.
7. Never manufacture provider-write, money-movement, rights, chain-broadcast, destructive-recovery, checkout, D3, voting, self-approval, or final-authority permissions.
8. Ambiguous or stale evidence resolves to HOLD; explicit forbidden boundaries resolve to DENY.

## Production promotion prerequisites

A runtime operation may become production-eligible only when current provider readback, credential readiness, exact-operation PentaCertify evidence, rollback/backup evidence where applicable, and CHLOM authority are all present for the exact source head and operation.
