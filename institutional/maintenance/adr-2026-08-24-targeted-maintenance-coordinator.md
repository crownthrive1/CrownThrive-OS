# ADR — Targeted Maintenance Coordinator and Quiescent Scheduler Boundary

**ADR ID:** `ct.adr.2026-08-24.targeted-maintenance-coordinator.v1`  
**Status:** Adopted for controlled maintenance  
**Event:** `ct.maintenance.2026-08-24.targeted-quiescence.v1`

## Decision

CrownThrive uses a temporary, bounded maintenance coordinator while ordinary mutating external automations and internal schedulers are quiesced. This coordinator is allowed as a separate failure-domain control even though CrownThrive normally consolidates recurring schedules into ThriveBase.

## Why

A maintenance mechanism cannot depend exclusively on the same application schedulers it must pause, reconcile, repair, or retire. The coordinator therefore has a distinct continuity role: it observes the maintenance event, verifies backup/readback/restore/scheduler gates, and orchestrates staged reactivation without inheriting ordinary agent authority.

This exception prevents circular dependency:

`paused scheduler → needed to reactivate itself → cannot run`

and replaces it with:

`maintenance coordinator → evidence gates → staged reactivation → ordinary scheduler`

## Authority boundary

The coordinator:

- is non-voting;
- has no quorum effect;
- cannot self-create D3 authority;
- cannot manufacture rights, licenses, entitlements, economic state, payments, customer assent, provider-write authority, or production certification;
- may perform only maintenance actions for which underlying authority and recoverability already exist;
- must fail closed when a required gate is missing or contradictory.

## Time is not a release gate

A six-hour or other elapsed window may be used operationally, but it never authorizes reactivation. Release is based on `chlom_runtime.maintenance_release_ready_v1` and the staged reactivation plan.

## Scheduler consolidation after maintenance

Before restoring each external clock, compare it to ThriveBase/pg_cron/event scheduling. When internal scheduling is equivalently governed and certified, the external schedule stays disabled as `RETIRED_SCHEDULING_SCAFFOLDING`. History remains preserved.

## Consequences

Positive:

- deterministic golden-snapshot boundary;
- lower duplicate-write risk;
- explicit recovery control;
- auditable reactivation;
- no dependency on one vendor scheduler for institutional continuity.

Tradeoffs:

- liveness dashboards must understand intentional maintenance pause semantics;
- work queues may accumulate without execution during quiescence;
- stale-heartbeat alerts must not automatically classify maintenance as failure;
- reactivation is slower than a blind mass enable, by design.

## Rollback

Close or roll back the maintenance event only after current evidence is preserved. Remove additive maintenance-control schema only after dependency checks. Never use rollback to erase DAIL or scheduler history.
