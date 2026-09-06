# DAIL Cursor + PentaBalancer Emergency Throughput Runbook v1

## Purpose

Operate bounded catch-up for the canonical CHLOM DAIL while preserving one writer, exact event identity, provider evidence, rights boundaries, and PentaBalancer admission.

## Normal operation

- Scheduler: `ct-dail-cursor-control-v1`
- Schedule: every minute
- Managed command: `penta_balancer.execute_managed_job_v1('ct-dail-cursor-control-v1')`
- Controller: `chlom_runtime.dail_cursor_tick_v1('auto', false)`
- Expected steady state: `BOUND_COMPLETE` or a pressure/contention deferral with no partial persisted run.

## Operator checks

Read `chlom_runtime.dail_cursor_status_v1()` and verify:

- Registry system key is `ct.dail.cursor.v1`.
- Emergency is disabled unless an explicit incident is active.
- Three rail positions exist for Machine, Human, and Hybrid.
- PentaBalancer mode and pressure permit work.
- Latest material run has both input and terminal DAIL receipts.
- Route failures remain zero.
- Verification cursor has no unhandled error.

Use `chlom_runtime.dail_cursor_canary_v1()` for semantic production verification.

## Emergency activation

Emergency mode is temporary and must be DAIL-bound. Invoke `dail_cursor_set_emergency_v1(true, minutes)` with 5–120 minutes. The control automatically expires.

The emergency profile can use four serial virtual slices, but never more than one database writer. PentaBalancer may reduce the profile to constrained or normal mode. This is expected and must not be bypassed.

## Manual catch-up

Use `dail_cursor_tick_v1('emergency', true)` for an operator-directed cycle. A successful cycle must return:

- input DAIL event and readback
- terminal DAIL event and readback
- effective mode
- rail cursor before/after
- verification cursor before/after
- route/deferred delivery counts
- verified event count
- evidence SHA-256

If the canonical writer lock is busy, the cycle returns a deferral and records no partial run. Retry through the same bounded path; do not create another writer.

## Throughput profiles

| Profile | Virtual slices | Rail events | Route limit | Deferred limit | Verification |
|---|---:|---:|---:|---:|---:|
| Constrained | 1 | 5,000 | 250 | 15 | 2,500 |
| Normal | 2 | 20,000 total | 500 | 25 | 5,000 total |
| Emergency | 4 | 100,000 total | 600 | 50 | 20,000 total |

All figures are ceilings, not guarantees.

## Failure handling

- **PentaBalancer SHED/HOLD or pressure ≥70:** defer.
- **Writer-lock contention:** defer with no partial run.
- **Input DAIL readback failure:** rollback the transaction; do not execute catch-up.
- **Terminal DAIL readback failure:** rollback the run; do not represent completion.
- **Route failure count above zero:** contain, diagnose, and preserve exact route IDs.
- **Verification error:** keep chain assurance in HOLD and use the retained exhaustive verifier when necessary.
- **Provider failure:** not billable; reverse any prior service debit.

## Publication-throughput interaction

Provider-published Go Flipbooks items may remain live during DAIL congestion only when rights, entitlement, payment, capacity, and provider readback pass. Each item must enter the deferred publication evidence backlog and remain institutionally pending until exact append/readback succeeds.

Cursor may accelerate reconciliation but does not turn backlog status into a license, conversion, customer entitlement, or paid-fulfillment completion.

## Emergency shutdown

Invoke `dail_cursor_set_emergency_v1(false, 5)`. Verify:

- requested mode `normal`
- emergency enabled `false`
- shutdown DAIL event readback
- normal scheduler remains active
- retired overlapping jobs remain inactive

## Evidence references

- Production canary event: `ca948bbd-2b10-489d-ab4c-e2579fddccc2`
- Scheduler deployment event: `6a5a3c80-8a63-4f26-ba4d-570117ea460a`
- Emergency shutdown event: `71b2c0c0-32c6-45ec-ae53-0e8eb5633bc3`
- Assignment ID: `c51a9ffc-88ea-4faa-991d-13447223e99e`
