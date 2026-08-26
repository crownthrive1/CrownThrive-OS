-- CrownThrive Targeted Maintenance Control v1 — deterministic contract tests
-- Use against an authorized test/open maintenance event; the historical August-24
-- event is closed and must not be reopened merely to satisfy this test file.

-- 1. Inspect current state.
select chlom_runtime.maintenance_state_v1();

-- 2. Ordinary mutation must fail closed while an applicable maintenance event is open.
select chlom_runtime.maintenance_preflight_v1('ct.relay.agent-a','ct.capability.portfolio.execute.v1',true,false);
-- Expected during applicable open maintenance: HOLD_PAUSED_FOR_TARGETED_MAINTENANCE.

-- 3. Read-only observation remains allowed.
select chlom_runtime.maintenance_preflight_v1('ct.relay.agent-a','ct.capability.portfolio.observe.v1',false,false);
-- Expected: PASS_READ_ONLY.

-- 4. Bounded maintenance scope may pass the maintenance ceiling but gains no underlying authority.
select chlom_runtime.maintenance_preflight_v1('ct.maintenance.coordinator.sol','ct.capability.maintenance.control.v1',true,false);

-- 5. D3 always fails closed.
select chlom_runtime.maintenance_preflight_v1('ct.maintenance.coordinator.sol','ct.capability.maintenance.control.v1',true,true);
-- Expected: HOLD_D3_HUMAN_RESERVED.

-- 6. Append-only receipt mutation must be rejected in an isolated negative-test transaction.
-- No test may fabricate PASS receipts or reopen the closed August-24 event.
