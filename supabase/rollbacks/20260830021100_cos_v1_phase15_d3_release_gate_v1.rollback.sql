-- Guarded rollback for Phase 15 D3 release-authority hardening.
-- Valid only before any Phase 15 execution exists.

begin;

do $$
begin
  if exists(
    select 1 from integration_control.cos_phase_executions_v1 where phase_id='15'
  ) then
    raise exception 'rollback_blocked_phase15_execution_history_exists';
  end if;
end
$$;

drop function if exists integration_control.cos_phase_bind_d3_approval_v1(uuid,text);

delete from integration_control.cos_phase_gate_requirements_v1
where phase_id='15' and gate_name='d3_human_release_approval';

alter table integration_control.cos_phase_executions_v1
  drop column if exists d3_approval_ref;

-- Restore the generic gate recorder/finalizer from the immediately preceding
-- COS phase-control migration by applying its source-controlled definitions.
-- This file intentionally refuses to re-embed older function bodies so rollback
-- cannot silently create a divergent third copy of the constitutional contract.

commit;
