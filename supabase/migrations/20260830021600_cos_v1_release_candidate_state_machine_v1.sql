-- COS V1 release candidate state machine binding.
-- Keeps release registry semantics synchronized with phase execution state.

begin;

create or replace function integration_control.cos_phase_execution_release_sync_v1()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog,integration_control
as $$
declare
  v_state text;
  v_repo text;
begin
  select state,source_repository into v_state,v_repo
  from integration_control.cos_release_registry_v1
  where release_id=new.release_id
  for update;

  if not found then raise exception 'unknown_cos_release:%',new.release_id; end if;
  if v_state in ('released','superseded') then
    raise exception 'release_not_mutable:%:%',new.release_id,v_state;
  end if;
  if v_repo='crownthrive1/CrownThrive-OS' and new.source_sha !~ '^[0-9a-f]{40}$' then
    raise exception 'github_release_source_sha_must_be_40_hex';
  end if;

  update integration_control.cos_release_registry_v1
  set state='converging',
      source_sha=new.source_sha,
      updated_at=now(),
      metadata=metadata || jsonb_build_object(
        'cos_current_execution_id',new.execution_id,
        'cos_current_phase_id',new.phase_id,
        'cos_candidate_source_sha',new.source_sha,
        'cos_release_state_source','phase_execution'
      )
  where release_id=new.release_id;

  return new;
end
$$;

drop trigger if exists cos_phase_execution_release_sync_v1 on integration_control.cos_phase_executions_v1;
create trigger cos_phase_execution_release_sync_v1
before insert on integration_control.cos_phase_executions_v1
for each row execute function integration_control.cos_phase_execution_release_sync_v1();

create or replace function integration_control.cos_phase_execution_hold_sync_v1()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog,integration_control
as $$
begin
  if new.state in ('hold','failed','rolled_back') and old.state is distinct from new.state then
    update integration_control.cos_release_registry_v1
    set state='hold',updated_at=now(),
        metadata=metadata || jsonb_build_object(
          'cos_hold_execution_id',new.execution_id,
          'cos_hold_phase_id',new.phase_id,
          'cos_hold_execution_state',new.state,
          'cos_release_state_source','phase_execution'
        )
    where release_id=new.release_id and state not in ('released','superseded');
  end if;
  return new;
end
$$;

drop trigger if exists cos_phase_execution_hold_sync_v1 on integration_control.cos_phase_executions_v1;
create trigger cos_phase_execution_hold_sync_v1
after update of state on integration_control.cos_phase_executions_v1
for each row execute function integration_control.cos_phase_execution_hold_sync_v1();

create or replace function integration_control.cos_phase_certified_release_sync_v1()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog,integration_control
as $$
declare
  v_release_id text;
  v_source_sha text;
begin
  if new.phase_id <> '15'
     and new.state='certified'
     and old.state is distinct from new.state
     and new.latest_execution_id is not null then
    select release_id,source_sha into v_release_id,v_source_sha
    from integration_control.cos_phase_executions_v1
    where execution_id=new.latest_execution_id;

    if v_release_id is not null then
      update integration_control.cos_release_registry_v1
      set state='certification_pending',
          source_sha=v_source_sha,
          updated_at=now(),
          metadata=metadata || jsonb_build_object(
            'cos_last_certified_phase_id',new.phase_id,
            'cos_last_certified_execution_id',new.latest_execution_id,
            'cos_candidate_source_sha',v_source_sha,
            'cos_release_state_source','phase_certification'
          )
      where release_id=v_release_id and state not in ('released','superseded');
    end if;
  end if;
  return new;
end
$$;

drop trigger if exists cos_phase_certified_release_sync_v1 on integration_control.cos_phase_registry_v1;
create trigger cos_phase_certified_release_sync_v1
after update of state on integration_control.cos_phase_registry_v1
for each row execute function integration_control.cos_phase_certified_release_sync_v1();

revoke all on function integration_control.cos_phase_execution_release_sync_v1() from public,anon,authenticated;
revoke all on function integration_control.cos_phase_execution_hold_sync_v1() from public,anon,authenticated;
revoke all on function integration_control.cos_phase_certified_release_sync_v1() from public,anon,authenticated;

commit;
