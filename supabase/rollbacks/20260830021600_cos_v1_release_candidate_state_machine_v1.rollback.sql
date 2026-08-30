-- Guarded rollback for COS V1 release candidate state synchronization.
-- Blocked after phase execution history exists because removing these guards
-- would make subsequent release-state semantics non-equivalent.

begin;

do $$
begin
  if exists(select 1 from integration_control.cos_phase_executions_v1) then
    raise exception 'rollback_blocked_cos_phase_execution_history_exists';
  end if;
end
$$;

drop trigger if exists cos_phase_certified_release_sync_v1 on integration_control.cos_phase_registry_v1;
drop trigger if exists cos_phase_execution_hold_sync_v1 on integration_control.cos_phase_executions_v1;
drop trigger if exists cos_phase_execution_release_sync_v1 on integration_control.cos_phase_executions_v1;

drop function if exists integration_control.cos_phase_certified_release_sync_v1();
drop function if exists integration_control.cos_phase_execution_hold_sync_v1();
drop function if exists integration_control.cos_phase_execution_release_sync_v1();

commit;
