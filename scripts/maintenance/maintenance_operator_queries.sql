-- CrownThrive targeted maintenance operator queries
-- Public-safe interface examples. No credentials or private evidence values.

-- Current maintenance state
select chlom_runtime.maintenance_state_v1();

-- Release readiness
select chlom_runtime.maintenance_release_ready_v1(
  'ct.maintenance.2026-08-24.targeted-quiescence.v1'
);

-- Staged reactivation plan
select chlom_runtime.maintenance_reactivation_plan_v1(
  'ct.maintenance.2026-08-24.targeted-quiescence.v1'
);

-- Current external projection for maintenance event
select
  external_task_id,
  external_task_title,
  canonical_agent_id,
  maintenance_disposition,
  control_state,
  reactivation_wave,
  scheduler_equivalence_state,
  final_disposition
from chlom_runtime.maintenance_automation_state_v1
where event_id='ct.maintenance.2026-08-24.targeted-quiescence.v1'
order by reactivation_wave, external_task_title;

-- Current pg_cron projection for maintenance event
select
  pg_cron_jobid,
  jobname,
  maintenance_disposition,
  reactivation_wave,
  scheduler_equivalence_state,
  final_disposition
from chlom_runtime.maintenance_cron_state_v1
where event_id='ct.maintenance.2026-08-24.targeted-quiescence.v1'
order by reactivation_wave, pg_cron_jobid;

-- Latest gate decision per gate
select distinct on(gate_name)
  gate_name,
  decision,
  evidence_digest_sha256,
  actor_id,
  created_at,
  notes
from chlom_runtime.maintenance_gate_receipts_v1
where event_id='ct.maintenance.2026-08-24.targeted-quiescence.v1'
order by gate_name, created_at desc;

-- DAIL integrity
select chlom_runtime.verify_dail_chain();

-- Preflight examples
select chlom_runtime.maintenance_preflight_v1(
  'ct.relay.agent-a',
  'ct.capability.portfolio.execute.v1',
  true,
  false
);

select chlom_runtime.maintenance_preflight_v1(
  'ct.maintenance.coordinator.sol',
  'ct.capability.maintenance.control.v1',
  true,
  false
);

-- Gate receipt template: substitute only evidence actually obtained.
-- select chlom_runtime.maintenance_record_gate_v1(
--   'ct.maintenance.2026-08-24.targeted-quiescence.v1',
--   '<gate_name>',
--   'PASS',
--   '["<evidence_ref>"]'::jsonb,
--   'ct.maintenance.coordinator.sol',
--   '<notes>'
-- );

-- Closing is intentionally guarded by maintenance_release_ready_v1.
-- select chlom_runtime.maintenance_close_v1(
--   'ct.maintenance.2026-08-24.targeted-quiescence.v1',
--   'ct.maintenance.coordinator.sol',
--   '["<close_evidence_ref>"]'::jsonb
-- );
