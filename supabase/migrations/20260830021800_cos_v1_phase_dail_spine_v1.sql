-- COS V1 phase DAIL evidence spine.
-- Material phase lifecycle mutations become institutionally complete only when
-- canonical DAIL append succeeds in the same database transaction.

begin;

alter table integration_control.cos_phase_executions_v1
  add column if not exists begin_dail_event_id text null,
  add column if not exists last_state_dail_event_id text null;

alter table integration_control.cos_phase_gate_receipts_v1
  add column if not exists dail_event_id text null;

create or replace function integration_control.cos_phase_execution_begin_dail_v1()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog,integration_control,chlom_runtime,extensions
as $$
declare
  v_receipt jsonb;
  v_pre_state_sha text;
  v_rollback_sha text;
  v_scope_sha text;
begin
  v_pre_state_sha:=encode(extensions.digest(convert_to(new.pre_state::text,'UTF8'),'sha256'),'hex');
  v_rollback_sha:=encode(extensions.digest(convert_to(new.rollback_point::text,'UTF8'),'sha256'),'hex');
  v_scope_sha:=encode(extensions.digest(convert_to(new.mutation_scope::text,'UTF8'),'sha256'),'hex');

  v_receipt:=chlom_runtime.append_dail_event(
    'cos.phase.execution.started','cos_phase_execution',new.execution_id::text,
    jsonb_build_object(
      'release_id',new.release_id,
      'phase_id',new.phase_id,
      'execution_seq',new.execution_seq,
      'source_sha',new.source_sha,
      'originator_actor',new.originator_actor,
      'pre_state_sha256',v_pre_state_sha,
      'rollback_point_sha256',v_rollback_sha,
      'mutation_scope_sha256',v_scope_sha,
      'state',new.state
    ),
    new.originator_actor,null,'ct.cos.phase-control','cos-v1-phase-'||new.phase_id,
    new.release_id,new.execution_id::text,
    'COS V1 immutable phase protocol: exact pre-state plus R1 rollback required before mutation.',
    null,'restricted'
  );

  if nullif(v_receipt->>'event_id','') is null then
    raise exception 'phase_begin_dail_receipt_missing';
  end if;
  new.begin_dail_event_id:=v_receipt->>'event_id';
  return new;
end
$$;

drop trigger if exists cos_phase_execution_begin_dail_v1
  on integration_control.cos_phase_executions_v1;
create trigger cos_phase_execution_begin_dail_v1
before insert on integration_control.cos_phase_executions_v1
for each row execute function integration_control.cos_phase_execution_begin_dail_v1();

create or replace function integration_control.cos_phase_gate_receipt_dail_v1()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog,integration_control,chlom_runtime
as $$
declare
  v_receipt jsonb;
  v_release_id text;
  v_source_sha text;
  v_originator_actor text;
begin
  select release_id,source_sha,originator_actor
    into v_release_id,v_source_sha,v_originator_actor
  from integration_control.cos_phase_executions_v1
  where execution_id=new.execution_id;
  if not found then raise exception 'unknown_phase_execution:%',new.execution_id; end if;

  v_receipt:=chlom_runtime.append_dail_event(
    'cos.phase.gate.recorded','cos_phase_gate',new.phase_id||':'||new.gate_name,
    jsonb_build_object(
      'release_id',v_release_id,
      'phase_id',new.phase_id,
      'execution_id',new.execution_id,
      'gate_name',new.gate_name,
      'gate_state',new.gate_state,
      'verifier_actor',new.verifier_actor,
      'originator_actor',v_originator_actor,
      'source_sha',v_source_sha,
      'evidence_sha256',new.evidence_sha256,
      'observed_at',new.observed_at
    ),
    new.verifier_actor,null,'ct.cos.phase-control','cos-v1-phase-'||new.phase_id,
    v_release_id,new.execution_id::text,
    'COS V1 gate evidence; DAIL records digest/provenance rather than protected evidence bodies.',
    null,'restricted'
  );

  if nullif(v_receipt->>'event_id','') is null then
    raise exception 'phase_gate_dail_receipt_missing:%',new.gate_name;
  end if;
  new.dail_event_id:=v_receipt->>'event_id';
  return new;
end
$$;

drop trigger if exists cos_phase_gate_receipt_dail_v1
  on integration_control.cos_phase_gate_receipts_v1;
create trigger cos_phase_gate_receipt_dail_v1
before insert on integration_control.cos_phase_gate_receipts_v1
for each row execute function integration_control.cos_phase_gate_receipt_dail_v1();

create or replace function integration_control.cos_phase_execution_state_dail_v1()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog,integration_control,chlom_runtime
as $$
declare
  v_receipt jsonb;
begin
  if old.state is not distinct from new.state then
    return new;
  end if;

  v_receipt:=chlom_runtime.append_dail_event(
    'cos.phase.execution.state_changed','cos_phase_execution',new.execution_id::text,
    jsonb_build_object(
      'release_id',new.release_id,
      'phase_id',new.phase_id,
      'source_sha',new.source_sha,
      'from_state',old.state,
      'to_state',new.state,
      'originator_actor',new.originator_actor,
      'd3_approval_ref',new.d3_approval_ref
    ),
    'ct.cos.phase-control',null,'ct.cos.phase-control','cos-v1-phase-'||new.phase_id,
    new.release_id,new.execution_id::text,
    'COS V1 phase lifecycle state transition.',
    new.d3_approval_ref,'restricted'
  );

  if nullif(v_receipt->>'event_id','') is null then
    raise exception 'phase_state_dail_receipt_missing:%',new.state;
  end if;

  new.last_state_dail_event_id:=v_receipt->>'event_id';
  return new;
end
$$;

drop trigger if exists cos_phase_execution_state_dail_v1
  on integration_control.cos_phase_executions_v1;
create trigger cos_phase_execution_state_dail_v1
before update of state on integration_control.cos_phase_executions_v1
for each row execute function integration_control.cos_phase_execution_state_dail_v1();

revoke all on function integration_control.cos_phase_execution_begin_dail_v1() from public,anon,authenticated;
revoke all on function integration_control.cos_phase_gate_receipt_dail_v1() from public,anon,authenticated;
revoke all on function integration_control.cos_phase_execution_state_dail_v1() from public,anon,authenticated;

commit;
