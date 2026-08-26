# ADR — Targeted Maintenance Coordinator and Quiescent Scheduler Boundary

**ADR ID:** `ct.adr.2026-08-24.targeted-maintenance-coordinator.v1`  
**Status:** Adopted / current reusable control  
**Historical event:** `ct.maintenance.2026-08-24.targeted-quiescence.v1` — CLOSED  
**Current operating owner:** PentaTime

## Decision

CrownThrive uses a bounded maintenance coordinator while ordinary mutating automations and internal schedulers are quiesced. The August 24, 2026 event is historical and closed; this ADR remains the reusable architectural decision for future authorized targeted-maintenance events.

PentaTime owns current coordination. PentaStatus supplies health/state visibility, PentaNurture supports recovery and continuity, PentaCertify verifies eligible recovery/execution paths, and PentaRelease governs staged return of release-capable workloads. These systems do not inherit authority merely by participating.

## Why

A maintenance mechanism cannot depend exclusively on the same application schedulers it must pause, reconcile, repair, or retire. The maintenance control therefore exists in a distinct failure domain and progresses only through evidence-backed backup, readback, restore, scheduler-reconciliation and DAIL gates.

`paused scheduler -> cannot reactivate itself`

is replaced by:

`bounded maintenance control -> evidence gates -> staged reactivation -> ordinary scheduler`

## Authority boundary

The maintenance control:

- is non-voting and has no quorum effect;
- has D2 maximum machine authority and keeps D3 human-reserved;
- cannot manufacture rights, licenses, entitlements, economic state, payments, customer assent, provider-write authority, credentials or production certification;
- may perform only maintenance actions for which underlying authority and recoverability already exist;
- fails closed when a required gate is missing, stale or contradictory.

## Time is not a release gate

Elapsed time never authorizes reactivation. Release is based on `chlom_runtime.maintenance_release_ready_v1` and the staged reactivation plan.

## Scheduler consolidation

Before restoring each external clock, compare it to ThriveBase/pg_cron/event scheduling and current PentaTime ownership. If internal scheduling provides equivalent governed cadence, authority, evidence, rollback and failure-domain behavior, preserve the external schedule disabled as `RETIRED_SCHEDULING_SCAFFOLDING`.

## Current Foundry reconciliation

The August 24 maintenance release is complete. CHLOM Agentic Foundry source has been accepted into current source lineage, but the runtime apply remains `HOLD_RUNTIME_APPLY_PENDING`. Maintenance closure does not manufacture that runtime apply or `PASS_PRODUCTION_RUNTIME`.

## Rollback

Remove only additive maintenance-control objects after dependency checks. Never use rollback to erase DAIL, scheduler, queue, rights, financial, identity, release or prior institutional history.