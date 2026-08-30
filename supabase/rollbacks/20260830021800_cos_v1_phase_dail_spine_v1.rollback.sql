-- Guarded rollback for COS V1 phase DAIL evidence spine.
-- Removing lifecycle audit bindings after execution evidence exists would break
-- institutional continuity, so rollback is pre-history only.

begin;

do $$
begin
  if exists(select 1 from integration_control.cos_phase_executions_v1)
     or exists(select 1 from integration_control.cos_phase_gate_receipts_v1) then
    raise exception 'rollback_blocked_cos_phase_evidence_history_exists';
  end if;
end
$$;

drop trigger if exists cos_phase_execution_state_dail_v1
  on integration_control.cos_phase_executions_v1;
drop trigger if exists cos_phase_gate_receipt_dail_v1
  on integration_control.cos_phase_gate_receipts_v1;
drop trigger if exists cos_phase_execution_begin_dail_v1
  on integration_control.cos_phase_executions_v1;

drop function if exists integration_control.cos_phase_execution_state_dail_v1();
drop function if exists integration_control.cos_phase_gate_receipt_dail_v1();
drop function if exists integration_control.cos_phase_execution_begin_dail_v1();

alter table integration_control.cos_phase_gate_receipts_v1
  drop column if exists dail_event_id;

alter table integration_control.cos_phase_executions_v1
  drop column if exists last_state_dail_event_id,
  drop column if exists begin_dail_event_id;

commit;
