-- Guarded rollback for COS V1 phase/certification control plane.
-- This rollback is valid only before any phase execution has been recorded.

begin;

do $$
begin
  if to_regclass('integration_control.cos_phase_executions_v1') is not null
     and exists (select 1 from integration_control.cos_phase_executions_v1) then
    raise exception 'rollback_blocked_cos_phase_execution_history_exists';
  end if;
end
$$;

drop trigger if exists cos_phase_gate_receipts_immutable_v1 on integration_control.cos_phase_gate_receipts_v1;
drop function if exists integration_control.cos_reject_gate_receipt_mutation_v1();
drop function if exists integration_control.cos_phase_status_v1(text);
drop function if exists integration_control.cos_phase_finalize_v1(uuid,text);
drop function if exists integration_control.cos_phase_evaluate_v1(uuid);
drop function if exists integration_control.cos_phase_record_gate_v1(uuid,text,text,text,jsonb,text,text);
drop function if exists integration_control.cos_phase_begin_v1(text,text,text,text,jsonb,jsonb,jsonb);

alter table if exists integration_control.cos_phase_registry_v1
  drop constraint if exists cos_phase_registry_latest_execution_fk;

drop table if exists integration_control.cos_phase_gate_receipts_v1;
drop table if exists integration_control.cos_phase_gate_requirements_v1;
drop table if exists integration_control.cos_phase_executions_v1;
drop table if exists integration_control.cos_phase_registry_v1;

commit;
