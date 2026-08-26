-- CrownThrive targeted maintenance operator queries
-- Public-safe examples; no credentials or private evidence values.
select chlom_runtime.maintenance_state_v1();
-- For a CURRENT authorized event, substitute the current event id below.
-- Historical August-24 example is retained for forensic readback only.
select chlom_runtime.maintenance_release_ready_v1('ct.maintenance.2026-08-24.targeted-quiescence.v1');
select chlom_runtime.maintenance_reactivation_plan_v1('ct.maintenance.2026-08-24.targeted-quiescence.v1');
select distinct on(gate_name)
  gate_name, decision, evidence_digest_sha256, actor_id, created_at, notes
from chlom_runtime.maintenance_gate_receipts_v1
where event_id='ct.maintenance.2026-08-24.targeted-quiescence.v1'
order by gate_name, created_at desc;
select chlom_runtime.verify_dail_chain();
-- Preflight examples. The legacy actor id is retained as an API compatibility identity;
-- current orchestration ownership is PentaTime.
select chlom_runtime.maintenance_preflight_v1('ct.maintenance.coordinator.sol','ct.capability.maintenance.control.v1',true,false);
-- D3 must fail closed:
select chlom_runtime.maintenance_preflight_v1('ct.maintenance.coordinator.sol','ct.capability.maintenance.control.v1',true,true);
