-- Guarded rollback for COS V1 stale-execution guard.
-- Removing stale-execution protection after phase history exists would weaken
-- certification semantics, so rollback is allowed only before first execution.

begin;

do $$
begin
  if exists(select 1 from integration_control.cos_phase_executions_v1) then
    raise exception 'rollback_blocked_cos_phase_execution_history_exists';
  end if;
end
$$;

drop trigger if exists cos_phase_execution_current_mutation_guard_v1
  on integration_control.cos_phase_executions_v1;
drop trigger if exists cos_phase_gate_receipt_current_execution_guard_v1
  on integration_control.cos_phase_gate_receipts_v1;

drop function if exists integration_control.cos_phase_execution_current_mutation_guard_v1();
drop function if exists integration_control.cos_phase_gate_receipt_current_execution_guard_v1();

commit;
