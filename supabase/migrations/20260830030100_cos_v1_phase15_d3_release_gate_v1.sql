-- COS V1 Phase 15 D3 founder-release authority hardening.
-- This migration makes D3 release approval a separately proven gate and prevents
-- a service actor from manufacturing it through the generic gate-receipt path.

begin;

alter table integration_control.cos_phase_executions_v1
  add column if not exists d3_approval_ref text null;

insert into integration_control.cos_phase_gate_requirements_v1(
  phase_id,gate_name,gate_order,required,independent_required,provider_readback_required,description
) values (
  '15','d3_human_release_approval',18,true,true,false,
  'Exact-source founder D3 production-release authority is current, unheld, nonrenewing, and independently bound. This gate cannot be recorded through the generic receipt function.'
)
on conflict (phase_id,gate_name) do update set
  gate_order=excluded.gate_order,
  required=excluded.required,
  independent_required=excluded.independent_required,
  provider_readback_required=excluded.provider_readback_required,
  description=excluded.description,
  updated_at=now();

create unique index if not exists cos_phase_gate_receipts_d3_once_idx
  on integration_control.cos_phase_gate_receipts_v1(execution_id,evidence_sha256)
  where gate_name='d3_human_release_approval';

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
  if p_gate_name='d3_human_release_approval' then
    raise exception 'use_cos_phase_bind_d3_approval_v1';
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

create or replace function integration_control.cos_phase_bind_d3_approval_v1(
  p_execution_id uuid,
  p_campaign_id text
) returns uuid
language plpgsql
security definer
set search_path to pg_catalog,integration_control,penta_runtime,extensions
as $$
declare
  v_phase_id text;
  v_source_sha text;
  v_existing_d3_approval_ref text;
  v_founder_ref text;
  v_binding jsonb;
  v_evidence_sha256 text;
  v_receipt_id uuid;
begin
  select phase_id,source_sha,d3_approval_ref
    into v_phase_id,v_source_sha,v_existing_d3_approval_ref
  from integration_control.cos_phase_executions_v1
  where execution_id=p_execution_id
  for update;
  if not found then raise exception 'unknown_execution'; end if;
  if v_phase_id <> '15' then raise exception 'd3_release_approval_phase15_only'; end if;
  if v_existing_d3_approval_ref is not null and v_existing_d3_approval_ref <> p_campaign_id then
    raise exception 'd3_release_approval_already_bound:%',v_existing_d3_approval_ref;
  end if;

  select to_jsonb(b),b.founder_ref
    into v_binding,v_founder_ref
  from penta_runtime.d3_campaign_bindings_v1 b
  where b.campaign_id=p_campaign_id
    and b.founder_ref='ct.person.founder.kavonte-jones-sr'
    and nullif(btrim(coalesce(b.directive_id,'')),'') is not null
    and b.directive_source_sha256 ~ '^[0-9a-f]{64}$'
    and b.scope_sha256 ~ '^[0-9a-f]{64}$'
    and b.max_cost_minor=0
    and clock_timestamp() >= b.starts_at
    and clock_timestamp() < b.expires_at
    and b.nonrenewing is true
    and b.independent_evidence_required is true
    and b.provider_write_authority is false
    and b.money_movement_authority is false
    and b.rights_disposition_authority is false
    and b.credential_authority is false
    and 'cos.production_release' = any(b.authorized_actions)
    and b.repository_snapshot @> jsonb_build_array(jsonb_build_object(
      'repository','crownthrive1/CrownThrive-OS',
      'source_sha',v_source_sha
    ))
    and not exists(
      select 1 from penta_runtime.d3_campaign_holds_v1 h where h.campaign_id=b.campaign_id
    );

  if v_binding is null then
    raise exception 'no_current_exact_source_d3_release_authority:%',p_campaign_id;
  end if;
  if v_founder_ref <> 'ct.person.founder.kavonte-jones-sr' then
    raise exception 'canonical_d3_founder_ref_required';
  end if;

  v_evidence_sha256:=encode(extensions.digest(convert_to(v_binding::text,'UTF8'),'sha256'),'hex');

  select receipt_id into v_receipt_id
  from integration_control.cos_phase_gate_receipts_v1
  where execution_id=p_execution_id
    and gate_name='d3_human_release_approval'
    and gate_state='PASS'
    and evidence_sha256=v_evidence_sha256
    and evidence_refs @> jsonb_build_array(jsonb_build_object(
      'campaign_id',p_campaign_id,
      'repository','crownthrive1/CrownThrive-OS',
      'source_sha',v_source_sha,
      'authority','cos.production_release'
    ))
  order by observed_at desc,created_at desc
  limit 1;

  if v_receipt_id is not null then
    if v_existing_d3_approval_ref is null then
      update integration_control.cos_phase_executions_v1
      set d3_approval_ref=p_campaign_id,updated_at=now()
      where execution_id=p_execution_id;
    end if;
    return v_receipt_id;
  end if;

  insert into integration_control.cos_phase_gate_receipts_v1(
    execution_id,phase_id,gate_name,gate_state,verifier_actor,evidence_refs,evidence_sha256,notes
  ) values (
    p_execution_id,'15','d3_human_release_approval','PASS',v_founder_ref,
    jsonb_build_array(jsonb_build_object(
      'campaign_id',p_campaign_id,
      'repository','crownthrive1/CrownThrive-OS',
      'source_sha',v_source_sha,
      'authority','cos.production_release'
    )),
    v_evidence_sha256,
    'Bound from current governed D3 campaign with canonical founder identity and exact directive/scope/source evidence; generic gate recording is prohibited.'
  ) returning receipt_id into v_receipt_id;

  update integration_control.cos_phase_executions_v1
  set d3_approval_ref=p_campaign_id,updated_at=now()
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
set search_path to pg_catalog,integration_control,chlom_runtime,penta_runtime
as $$
declare
  v_eval jsonb;
  v_phase_id text;
  v_release_id text;
  v_source_sha text;
  v_d3_approval_ref text;
  v_dail jsonb;
  v_phase_state text;
begin
  v_eval:=integration_control.cos_phase_evaluate_v1(p_execution_id);
  if coalesce((v_eval->>'ready')::boolean,false) is not true then
    raise exception 'phase_not_ready:%',v_eval::text;
  end if;

  select phase_id,release_id,source_sha,d3_approval_ref
    into v_phase_id,v_release_id,v_source_sha,v_d3_approval_ref
  from integration_control.cos_phase_executions_v1
  where execution_id=p_execution_id
  for update;
  if not found then raise exception 'unknown_execution'; end if;

  if v_phase_id='15' then
    if v_d3_approval_ref is null then raise exception 'phase15_d3_approval_not_bound'; end if;
    if not exists(
      select 1
      from penta_runtime.d3_campaign_bindings_v1 b
      where b.campaign_id=v_d3_approval_ref
        and b.founder_ref='ct.person.founder.kavonte-jones-sr'
        and nullif(btrim(coalesce(b.directive_id,'')),'') is not null
        and b.directive_source_sha256 ~ '^[0-9a-f]{64}$'
        and b.scope_sha256 ~ '^[0-9a-f]{64}$'
        and b.max_cost_minor=0
        and clock_timestamp() >= b.starts_at
        and clock_timestamp() < b.expires_at
        and b.nonrenewing is true
        and b.independent_evidence_required is true
        and b.provider_write_authority is false
        and b.money_movement_authority is false
        and b.rights_disposition_authority is false
        and b.credential_authority is false
        and 'cos.production_release'=any(b.authorized_actions)
        and b.repository_snapshot @> jsonb_build_array(jsonb_build_object(
          'repository','crownthrive1/CrownThrive-OS',
          'source_sha',v_source_sha
        ))
        and not exists(select 1 from penta_runtime.d3_campaign_holds_v1 h where h.campaign_id=b.campaign_id)
    ) then
      raise exception 'phase15_d3_approval_expired_held_or_drifted:%',v_d3_approval_ref;
    end if;
  end if;

  v_phase_state:=case when v_phase_id='15' then 'production_certified' else 'certified' end;

  v_dail:=chlom_runtime.append_dail_event(
    'cos.phase.certified','cos_phase',v_phase_id,
    jsonb_build_object(
      'release_id',v_release_id,
      'execution_id',p_execution_id,
      'source_sha',v_source_sha,
      'evaluation',v_eval,
      'phase_state',v_phase_state,
      'd3_approval_ref',v_d3_approval_ref
    ),
    p_actor,null,'ct.penta.certifier','cos-v1-phase-'||v_phase_id,v_release_id,p_execution_id::text,
    case when v_phase_id='15' then 'Exact-source founder D3 production-release authority plus independently satisfied technical gates' else 'COS V1 immutable phase protocol' end,
    v_d3_approval_ref,'restricted'
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
        metadata=metadata || jsonb_build_object(
          'cos_phase_15_execution_id',p_execution_id,
          'cos_phase_15_dail_event_id',v_dail->>'event_id',
          'cos_phase_15_d3_approval_ref',v_d3_approval_ref,
          'production_certification',true
        )
    where release_id=v_release_id;
  end if;

  return jsonb_build_object(
    'ok',true,
    'phase_id',v_phase_id,
    'phase_state',v_phase_state,
    'd3_approval_ref',v_d3_approval_ref,
    'dail_receipt',v_dail,
    'evaluation',v_eval
  );
end
$$;

revoke all on function integration_control.cos_phase_bind_d3_approval_v1(uuid,text) from public,anon,authenticated;
grant execute on function integration_control.cos_phase_bind_d3_approval_v1(uuid,text) to service_role;

commit;
