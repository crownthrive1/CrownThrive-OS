-- COS V1 stale-execution guard.
-- Prevents historical/superseded phase executions from receiving new gate evidence,
-- binding D3 authority, or transitioning to PASS after a newer execution is current.

begin;

create or replace function integration_control.cos_phase_gate_receipt_current_execution_guard_v1()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog,integration_control
as $$
declare
  v_phase_id text;
  v_execution_state text;
  v_latest_execution_id uuid;
begin
  select phase_id,state into v_phase_id,v_execution_state
  from integration_control.cos_phase_executions_v1
  where execution_id=new.execution_id;
  if not found then raise exception 'unknown_phase_execution:%',new.execution_id; end if;

  select latest_execution_id into v_latest_execution_id
  from integration_control.cos_phase_registry_v1
  where phase_id=v_phase_id;

  if v_latest_execution_id is distinct from new.execution_id then
    raise exception 'stale_phase_execution_gate_receipt:%:latest=%',new.execution_id,v_latest_execution_id;
  end if;

  if v_execution_state in ('passed','failed','rolled_back') then
    raise exception 'terminal_phase_execution_rejects_gate_receipt:%:%',new.execution_id,v_execution_state;
  end if;

  return new;
end
$$;

drop trigger if exists cos_phase_gate_receipt_current_execution_guard_v1
  on integration_control.cos_phase_gate_receipts_v1;
create trigger cos_phase_gate_receipt_current_execution_guard_v1
before insert on integration_control.cos_phase_gate_receipts_v1
for each row execute function integration_control.cos_phase_gate_receipt_current_execution_guard_v1();

create or replace function integration_control.cos_phase_execution_current_mutation_guard_v1()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog,integration_control
as $$
declare
  v_latest_execution_id uuid;
  v_release_source_sha text;
begin
  if (new.state='passed' and old.state is distinct from new.state)
     or (new.d3_approval_ref is distinct from old.d3_approval_ref) then
    select latest_execution_id into v_latest_execution_id
    from integration_control.cos_phase_registry_v1
    where phase_id=new.phase_id;

    if v_latest_execution_id is distinct from new.execution_id then
      raise exception 'stale_phase_execution_mutation:%:latest=%',new.execution_id,v_latest_execution_id;
    end if;

    select source_sha into v_release_source_sha
    from integration_control.cos_release_registry_v1
    where release_id=new.release_id;

    if v_release_source_sha is distinct from new.source_sha then
      raise exception 'phase_execution_release_source_drift:%:execution=%:release=%',new.execution_id,new.source_sha,v_release_source_sha;
    end if;
  end if;

  return new;
end
$$;

drop trigger if exists cos_phase_execution_current_mutation_guard_v1
  on integration_control.cos_phase_executions_v1;
create trigger cos_phase_execution_current_mutation_guard_v1
before update on integration_control.cos_phase_executions_v1
for each row execute function integration_control.cos_phase_execution_current_mutation_guard_v1();

revoke all on function integration_control.cos_phase_gate_receipt_current_execution_guard_v1() from public,anon,authenticated;
revoke all on function integration_control.cos_phase_execution_current_mutation_guard_v1() from public,anon,authenticated;

commit;
