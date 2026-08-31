-- CrownThrive PentaAssignment / CHLOM / PentaSecurity
-- Exact DAIL receipt binding hardening for the release-gate bridge.
-- Prevents substitution of an unrelated valid DAIL event as gate evidence.

create or replace function integration_control.penta_assignment_bind_release_gate_v1(
  p_assignment_id uuid,
  p_gate_kind text,
  p_disposition text,
  p_authority_system_key text,
  p_exact_head_sha text,
  p_subject_sha256 text,
  p_evidence_ref text,
  p_evidence_sha256 text,
  p_dail_event_id uuid,
  p_dail_event_hash text,
  p_supersedes_binding_id uuid default null,
  p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','integration_control','chlom_runtime'
as $fn$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  d chlom_runtime.dail_events%rowtype;
  v_expected_authority text;
  v_authority_current boolean:=false;
  v_id uuid;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id;
  if not found then raise exception 'assignment_not_found'; end if;
  if p_gate_kind not in ('PENTASECURITY','CHLOM_RIGHTS','CIE') then raise exception 'release_gate_kind_invalid'; end if;
  if p_disposition not in ('PASS','NOT_APPLICABLE','HOLD','FAIL') then raise exception 'release_gate_disposition_invalid'; end if;

  v_expected_authority:=case p_gate_kind when 'PENTASECURITY' then 'penta.security' when 'CHLOM_RIGHTS' then 'chlom_core' when 'CIE' then 'ct.framework.cultural-imprint-engine' end;
  if lower(coalesce(p_authority_system_key,''))<>v_expected_authority then raise exception 'release_gate_authority_mismatch'; end if;

  if p_gate_kind='PENTASECURITY' then
    select exists(select 1 from public.penta_system_registry s where s.system_key='penta.security' and s.canonical_name='PentaSecurity') into v_authority_current;
  elsif p_gate_kind='CHLOM_RIGHTS' then
    select exists(select 1 from integration_control.penta_census_entities_v1 e where e.current and e.entity_key='chlom_core' and e.canonical_name='CHLOM Metaprotocol Control Plane') into v_authority_current;
  else
    select exists(select 1 from institutional_federation.framework_package_registry p where p.package_id='ct.framework-package.cie' and p.framework_id='ct.framework.cultural-imprint-engine' and lower(p.package_state)='maintained' and p.authority_ceiling='D2' and p.d3_human_reserved) into v_authority_current;
  end if;
  if not v_authority_current then raise exception 'release_gate_authority_registry_not_current'; end if;

  if a.exact_head_sha !~ '^[0-9a-f]{40}$' or p_exact_head_sha<>a.exact_head_sha then raise exception 'release_gate_exact_head_mismatch'; end if;
  if a.exact_artifact_sha256 !~ '^[0-9a-f]{64}$' or p_subject_sha256<>a.exact_artifact_sha256 then raise exception 'release_gate_subject_digest_mismatch'; end if;
  if coalesce(p_evidence_ref,'')='' or p_evidence_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'release_gate_evidence_invalid'; end if;

  select * into d from chlom_runtime.dail_events where event_id=p_dail_event_id and event_hash=p_dail_event_hash;
  if not found then raise exception 'release_gate_dail_readback_required'; end if;

  if coalesce(d.payload->>'release_gate_contract','')<>'ct.penta.release-gate.receipt.v1'
     or coalesce(d.payload->>'assignment_id','')<>p_assignment_id::text
     or coalesce(d.payload->>'gate_kind','')<>p_gate_kind
     or lower(coalesce(d.payload->>'authority_system_key',''))<>v_expected_authority
     or coalesce(d.payload->>'exact_head_sha','')<>p_exact_head_sha
     or coalesce(d.payload->>'subject_sha256','')<>p_subject_sha256
     or coalesce(d.payload->>'disposition','')<>p_disposition
     or coalesce(d.payload->>'evidence_sha256','')<>p_evidence_sha256
     or coalesce((d.payload->>'authority_created')::boolean,true) then
    raise exception 'release_gate_dail_payload_contract_mismatch';
  end if;

  if p_supersedes_binding_id is not null and not exists(select 1 from integration_control.penta_assignment_release_gate_bindings_v1 b where b.binding_id=p_supersedes_binding_id and b.assignment_id=p_assignment_id and b.gate_kind=p_gate_kind) then raise exception 'release_gate_supersession_invalid'; end if;

  insert into integration_control.penta_assignment_release_gate_bindings_v1(assignment_id,gate_kind,disposition,authority_system_key,exact_head_sha,subject_sha256,evidence_ref,evidence_sha256,dail_event_id,dail_event_hash,supersedes_binding_id,metadata)
  values(p_assignment_id,p_gate_kind,p_disposition,lower(p_authority_system_key),p_exact_head_sha,p_subject_sha256,p_evidence_ref,p_evidence_sha256,p_dail_event_id,p_dail_event_hash,p_supersedes_binding_id,coalesce(p_metadata,'{}'::jsonb)||jsonb_build_object('authority_created',false,'binding_only',true,'dail_payload_contract_verified',true))
  on conflict(assignment_id,gate_kind,evidence_sha256) do nothing returning binding_id into v_id;
  if v_id is null then select binding_id into v_id from integration_control.penta_assignment_release_gate_bindings_v1 where assignment_id=p_assignment_id and gate_kind=p_gate_kind and evidence_sha256=p_evidence_sha256; end if;

  return jsonb_build_object('binding_id',v_id,'assignment_id',p_assignment_id,'gate_kind',p_gate_kind,'disposition',p_disposition,'authority_system_key',lower(p_authority_system_key),'exact_head_sha',p_exact_head_sha,'subject_sha256',p_subject_sha256,'dail_payload_contract_verified',true,'authority_created',false,'certification_issued',false,'release_authorized',false);
end
$fn$;

revoke all on function integration_control.penta_assignment_bind_release_gate_v1(uuid,text,text,text,text,text,text,text,uuid,text,uuid,jsonb) from public,anon,authenticated;
grant execute on function integration_control.penta_assignment_bind_release_gate_v1(uuid,text,text,text,text,text,text,text,uuid,text,uuid,jsonb) to service_role;
