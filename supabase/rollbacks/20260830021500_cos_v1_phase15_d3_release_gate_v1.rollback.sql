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

create or replace function integration_control.cos_phase_record_gate_v1(
  p_execution_id uuid,
  p_gate_name text,
  p_gate_state text,
  p_verifier_actor text,
  p_evidence_refs jsonb,
  p_evidence_sha256 text,
  p_notes text default null
) returns uuid
language plpgsql
security definer
set search_path to pg_catalog,integration_control
as $$
declare
  v_receipt_id uuid;
  v_phase_id text;
  v_originator_actor text;
  v_independent_required boolean;
begin
  if current_user not in ('postgres','service_role') then
    raise exception 'service_role_required';
  end if;
  if p_gate_state not in ('PASS','HOLD','FAIL','UNKNOWN') then raise exception 'invalid_gate_state'; end if;
  if p_evidence_sha256 is null or p_evidence_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'evidence_sha256_required'; end if;
  select e.phase_id,e.originator_actor,r.independent_required
    into v_phase_id,v_originator_actor,v_independent_required
  from integration_control.cos_phase_executions_v1 e
  join integration_control.cos_phase_gate_requirements_v1 r on r.phase_id=e.phase_id and r.gate_name=p_gate_name
  where e.execution_id=p_execution_id;
  if not found then raise exception 'unknown_execution_or_gate'; end if;
  if v_independent_required and p_verifier_actor=v_originator_actor then
    raise exception 'originator_cannot_verify_independent_gate:%',p_gate_name;
  end if;
  insert into integration_control.cos_phase_gate_receipts_v1(
    execution_id,phase_id,gate_name,gate_state,verifier_actor,evidence_refs,evidence_sha256,notes
  ) values (
    p_execution_id,v_phase_id,p_gate_name,p_gate_state,p_verifier_actor,coalesce(p_evidence_refs,'[]'::jsonb),p_evidence_sha256,p_notes
  ) returning receipt_id into v_receipt_id;
  update integration_control.cos_phase_executions_v1
  set state=case when p_gate_state in ('FAIL','HOLD') then 'hold' else state end,updated_at=now()
  where execution_id=p_execution_id;
  return v_receipt_id;
end
$$;

create or replace function integration_control.cos_phase_finalize_v1(
  p_execution_id uuid,
  p_actor text
) returns jsonb
language plpgsql
security definer
set search_path to pg_catalog,integration_control,chlom_runtime
as $$
declare
  v_eval jsonb;
  v_phase_id text;
  v_release_id text;
  v_source_sha text;
  v_dail jsonb;
  v_phase_state text;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  v_eval:=integration_control.cos_phase_evaluate_v1(p_execution_id);
  if coalesce((v_eval->>'ready')::boolean,false) is not true then
    raise exception 'phase_not_ready:%',v_eval::text;
  end if;
  select phase_id,release_id,source_sha into v_phase_id,v_release_id,v_source_sha
  from integration_control.cos_phase_executions_v1 where execution_id=p_execution_id for update;
  if not found then raise exception 'unknown_execution'; end if;
  v_phase_state:=case when v_phase_id='15' then 'production_certified' else 'certified' end;
  v_dail:=chlom_runtime.append_dail_event(
    'cos.phase.certified','cos_phase',v_phase_id,
    jsonb_build_object('release_id',v_release_id,'execution_id',p_execution_id,'source_sha',v_source_sha,'evaluation',v_eval,'phase_state',v_phase_state),
    p_actor,null,'ct.penta.certifier','cos-v1-phase-'||v_phase_id,v_release_id,p_execution_id::text,
    case when v_phase_id='15' then 'D3 human-reserved final release authority plus independently satisfied technical gates' else 'COS V1 immutable phase protocol' end,
    null,'restricted'
  );
  update integration_control.cos_phase_executions_v1
  set state='passed',ended_at=now(),dail_event_id=v_dail->>'event_id',updated_at=now()
  where execution_id=p_execution_id;
  update integration_control.cos_phase_registry_v1
  set state=v_phase_state,latest_dail_event_id=v_dail->>'event_id',source_sha=v_source_sha,updated_at=now()
  where phase_id=v_phase_id;
  if v_phase_id='15' then
    update integration_control.cos_release_registry_v1
    set state='released',production_sha=v_source_sha,released_at=now(),updated_at=now(),
        metadata=metadata || jsonb_build_object('cos_phase_15_execution_id',p_execution_id,'cos_phase_15_dail_event_id',v_dail->>'event_id','production_certification',true)
    where release_id=v_release_id;
  end if;
  return jsonb_build_object('ok',true,'phase_id',v_phase_id,'phase_state',v_phase_state,'dail_receipt',v_dail,'evaluation',v_eval);
end
$$;

revoke all on function integration_control.cos_phase_record_gate_v1(uuid,text,text,text,jsonb,text,text) from public,anon,authenticated;
revoke all on function integration_control.cos_phase_finalize_v1(uuid,text) from public,anon,authenticated;
grant execute on function integration_control.cos_phase_record_gate_v1(uuid,text,text,text,jsonb,text,text) to service_role;
grant execute on function integration_control.cos_phase_finalize_v1(uuid,text) to service_role;

commit;
