# CrownThrive Targeted Maintenance Coordinator Runbook

## Institutional purpose

This runbook governs targeted quiescence, not a CrownThrive shutdown. It creates a stable recovery boundary before broad convergence or production mutation so moving scheduler, queue, provider, commerce or documentation state cannot invalidate backup manifests, hashes, restore tests or scheduler-equivalence evidence.

The August 24, 2026 maintenance event `ct.maintenance.2026-08-24.targeted-quiescence.v1` is **CLOSED** and remains historical evidence. The reusable current coordinator is **PentaTime**, operating under the D2 maximum/D3-human-reserved maintenance contract with PentaStatus, PentaNurture, PentaCertify and PentaRelease support.

## Mandatory sequence

1. Capture exact external and internal scheduler pre-state.
2. Preserve source/database rollback anchors.
3. Pause only the mutating workloads within the authorized maintenance scope.
4. Register the authorized maintenance event in ThriveBase.
5. Run maintenance preflight negative/control tests.
6. Create and verify the recovery manifest.
7. Read back critical recoverable artifacts.
8. Validate restore paths.
9. Reconcile duplicate/external/internal schedulers.
10. Verify DAIL integrity.
11. Resolve high-consequence unknowns or preserve explicit HOLD.
12. Stage reactivation wave by wave.
13. Close the event only when every required release gate is PASS.

## Database controls

- `chlom_runtime.maintenance_state_v1()`
- `chlom_runtime.maintenance_preflight_v1(actor_id, capability_id, mutation_requested, d3_requested)`
- `chlom_runtime.maintenance_record_gate_v1(...)`
- `chlom_runtime.maintenance_release_ready_v1(event_id)`
- `chlom_runtime.maintenance_reactivation_plan_v1(event_id)`
- `chlom_runtime.maintenance_close_v1(event_id, actor_id, evidence_refs)`

Maintenance preflight is an additional fail-closed ceiling. A maintenance PASS never grants an underlying capability the caller did not already possess.

## Quiescence policy

During strict snapshot/recovery work, preserve backup/recovery, genuinely read-only alerting and bounded maintenance control. Pause affected routine writers, builders, site automation, commerce/outbound work, release automation, queue dispatchers and stale actuators. Intentional pause state is `PAUSED_FOR_TARGETED_MAINTENANCE`, not failure.

## Backup gate

Release is evidence-based:

`BACKUP_GATE=PASS_RECOVERABLE`

Required evidence includes event-bound manifest, source SHAs/versions where applicable, destination references, readback proof, restore instructions, tested restore path, gap accounting and no plaintext-secret export.

## Scheduler reconciliation

For each external automation and internal scheduler, compare workload identity, cadence, authority ceiling, data access, secret boundary, failure domain, evidence/DAIL behavior, rollback and missed-run semantics. Final disposition is one of `RESTORE_EXTERNAL`, `RESTORE_INTERNAL`, `KEEP_ENABLED`, `RETIRED_SCHEDULING_SCAFFOLDING`, or `HOLD`. Never blindly re-enable every prior clock.

## Reactivation waves

0. maintenance core — backup/recovery/readback/restore.
1. observation and continuity — PentaStatus/PentaNurture/credential-health controls.
2. independent verification — PentaCertify/PentaAssure/security/domain verification.
3. bounded builders/executors — D0-D2 only with authority, rollback and independent verification.
4. documentation/site projection — PentaDocs/PentaScribe/PentaRoute projection reconciliation.
5. commercial/outbound/release — PentaRelease/PentaGreen-authorized customer-facing mutation last.

After every wave, re-read queue state, duplicate scheduling, stale leases, DAIL, provider/economic side effects and error state before advancing.

## CHLOM Agentic Foundry current handoff

The Foundry source package is accepted in the current source line. The maintenance event that previously blocked Wave 3 is closed, but the accepted ThriveBase migration has **not** been proven applied. Current state is `HOLD_RUNTIME_APPLY_PENDING`.

The canonical current source/public contract is the post-maintenance correction accepted through Support PR #474. Do not trust stale PR #375 or the old `HOLD_MAINTENANCE` label as current truth.

Before runtime apply, require exact accepted source, current Foundry/CIE governance evidence, DAIL integrity, rollback readiness, no newer supersession, provider/credential/security gates applicable to the target, and zero duplicate scheduler creation. Apply only the exact source-controlled migration; never reconstruct protected SQL from public documentation.

After an authorized apply, second-read and prove the expected plane/class boundaries, D2 maximum, non-voting/non-quorum/no-authority-inheritance invariants, Vault alias presence without raw-secret retrieval, protected-body exclusion, binding state, scheduler state and deterministic stress/negative tests. Only exact apply/readback evidence may advance runtime certification.

## Vault handling

Vault remains the secret custody plane. Public source and ordinary Drive artifacts may contain safe aliases/references, fingerprints and custody metadata, not plaintext secret values.

## Failure behavior

Missing, stale, contradictory or unavailable release evidence produces `HOLD`. A backup gap holds only the affected mutation; unrelated recovery can continue. Never widen authority to obtain PASS.

## Rollback

Maintenance-control changes are additive wherever possible. Rollback removes only maintenance-control objects after dependency checks and never deletes DAIL, scheduler history, queue history, rights records, financial evidence, identities or prior institutional evidence.