-- CrownThrive targeted maintenance control v1 — guarded rollback
-- Removes only additive maintenance-control objects. Never re-enables schedulers,
-- rewrites DAIL, or deletes institutional history.
begin;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM chlom_runtime.maintenance_events_v1 WHERE status IN ('active','closing')) THEN
    RAISE EXCEPTION 'Refusing rollback: an open maintenance event still exists';
  END IF;
END
$$;
DROP FUNCTION IF EXISTS chlom_runtime.maintenance_close_v1(text,text,jsonb);
DROP FUNCTION IF EXISTS chlom_runtime.maintenance_reactivation_plan_v1(text);
DROP FUNCTION IF EXISTS chlom_runtime.maintenance_release_ready_v1(text);
DROP FUNCTION IF EXISTS chlom_runtime.maintenance_record_gate_v1(text,text,text,jsonb,text,text);
DROP FUNCTION IF EXISTS chlom_runtime.maintenance_preflight_v1(text,text,boolean,boolean);
DROP FUNCTION IF EXISTS chlom_runtime.maintenance_state_v1();
DROP TRIGGER IF EXISTS maintenance_gate_receipts_v1_append_only ON chlom_runtime.maintenance_gate_receipts_v1;
DROP FUNCTION IF EXISTS chlom_runtime.reject_maintenance_receipt_mutation_v1();
DROP TABLE IF EXISTS chlom_runtime.maintenance_gate_receipts_v1;
DROP TABLE IF EXISTS chlom_runtime.maintenance_cron_state_v1;
DROP TABLE IF EXISTS chlom_runtime.maintenance_automation_state_v1;
DROP TABLE IF EXISTS chlom_runtime.maintenance_events_v1;
commit;
-- Scheduler restoration is intentionally out-of-band and evidence-gated through PentaTime.
