-- CrownThrive Targeted Maintenance Control v1 — deterministic contract tests
-- Read-only except the final append-only trigger negative test, which must fail.

-- 1. Maintenance is active.
select chlom_runtime.maintenance_state_v1();

-- 2. Ordinary mutating agent must fail closed.
select chlom_runtime.maintenance_preflight_v1(
  'ct.relay.agent-a',
  'ct.capability.portfolio.execute.v1',
  true,
  false
);
-- Expected: allowed=false / HOLD_PAUSED_FOR_TARGETED_MAINTENANCE

-- 3. Read-only operation remains allowed.
select chlom_runtime.maintenance_preflight_v1(
  'ct.relay.agent-a',
  'ct.capability.portfolio.observe.v1',
  false,
  false
);
-- Expected: allowed=true / PASS_READ_ONLY

-- 4. Bounded maintenance coordinator scope passes the maintenance ceiling.
select chlom_runtime.maintenance_preflight_v1(
  'ct.maintenance.coordinator.sol',
  'ct.capability.maintenance.control.v1',
  true,
  false
);
-- Expected: allowed=true / PASS_MAINTENANCE_SCOPE
-- This does NOT grant any underlying capability authority.

-- 5. D3 can never be authorized by maintenance.
select chlom_runtime.maintenance_preflight_v1(
  'ct.maintenance.coordinator.sol',
  'ct.capability.maintenance.control.v1',
  true,
  true
);
-- Expected: allowed=false / HOLD_D3_HUMAN_RESERVED

-- 6. Release must remain HOLD until every required gate is PASS.
select chlom_runtime.maintenance_release_ready_v1(
  'ct.maintenance.2026-08-24.targeted-quiescence.v1'
);
-- Expected during active baseline work: ready=false.

-- 7. Reactivation plan is inspectable and wave-scoped.
select chlom_runtime.maintenance_reactivation_plan_v1(
  'ct.maintenance.2026-08-24.targeted-quiescence.v1'
);

-- 8. Append-only gate receipt mutation must fail.
-- Run only in an isolated negative-test transaction if desired:
-- begin;
-- update chlom_runtime.maintenance_gate_receipts_v1
-- set notes='MUTATION_SHOULD_FAIL'
-- where receipt_id=(select receipt_id from chlom_runtime.maintenance_gate_receipts_v1 limit 1);
-- rollback;
-- Expected: ERROR maintenance gate receipts are append-only.
