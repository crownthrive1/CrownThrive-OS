# PentaBalancer Production Runtime

## Scope

PentaBalancer has one production responsibility: scheduler load balancing and exact temporal cohesion with PentaTime, PentaClock, PentaTick, and PentaCrons. It does not execute business workflows, move money, perform provider writes, generate content, or create authority.

## Runtime contract

- Pressure is measured from bounded PostgreSQL session, lock, cron-runner, and recent-failure observations.
- The controller uses deterministic hysteresis across NORMAL, WATCH, SHED, RECOVERY, and HOLD.
- Critical and high-priority lanes remain available. Normal and elastic lanes may be temporarily deferred under pressure.
- No operation or cron is permanently disabled by PentaBalancer.
- Managed jobs retain their original schedule, owner, original command, and SHA-256. `penta_balancer.restore_job_v1(text)` performs exact reversible restoration.
- Core temporal jobs are never wrapped.
- Exact cohesion is continuously checked across live cron, desired state, permanent state, PentaSELF repair expectations, scheduler registration, and operation enablement.

## Production evidence

The authoritative receipt set and current runtime readback are stored in `docs/evidence/PENTABALANCER_PRODUCTION_20260904.json`. The byte-exact applied migration replay is stored in `supabase/migrations/20260904070000_pentabalancer_production_replay.sql`.

## All-Penta maturation

The existing PentaCertify clock now invokes the specialist maturation controller. It routes each nonproduction Penta through the existing PentaHelper, PentaFactory, PentaTest, PentaSecurity, and PentaCertify chain according to deterministic evidence. Production promotion remains fail-closed and requires an exact system-version receipt. Blanket promotion is forbidden.

## Recovery

1. Read `penta_balancer.full_status_v1()`.
2. Confirm `cohesion_score = 100` and `actual_command_drift = 0`.
3. Use `penta_balancer.ensure_core_cohesion_v1()` only for core temporal drift.
4. Use `penta_balancer.restore_job_v1(jobname)` for an exact managed-job rollback.
5. Never modify an original command without updating and recertifying its SHA-256 custody record.

Generated: 2026-09-04 07:17:47.95232+00
