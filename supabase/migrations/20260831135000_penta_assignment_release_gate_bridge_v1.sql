-- CrownThrive PentaAssignment / CHLOM / PentaSecurity
-- Exact-subject release-gate bridge for assignments awaiting independent certification.
--
-- This is an additive extension of the existing penta_assignment fabric. It does not
-- create a new security authority, CHLOM authority, CIE authority, certifier, provider,
-- credential, money-movement capability, D3 authority, or merge/release authority.
-- It only binds already-existing external gate receipts to an exact assignment subject
-- and queues PentaCertify after all required upstream gates are genuinely present.

create table if not exists integration_control.penta_assignment_release_gate_bindings_v1 (
  binding_id uuid primary key default gen_random_uuid(),
  assignment_id uuid not null references integration_control.penta_assignment_contracts_v1(assignment_id),
  gate_kind text not null check (gate_kind in ('PENTASECURITY','CHLOM_RIGHTS','CIE')),
  disposition text not null check (disposition in ('PASS','NOT_APPLICABLE','HOLD','FAIL')),
  authority_system_key text not null,
  exact_head_sha text not null check (exact_head_sha ~ '^[0-9a-f]{40}$'),
  subject_sha256 text not null check (subject_sha256 ~ '^[0-9a-f]{64}$'),
  evidence_ref text not null,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  dail_event_id uuid not null,
  dail_event_hash text not null check (dail_event_hash ~ '^[0-9a-f]{64}$'),
  supersedes_binding_id uuid references integration_control.penta_assignment_release_gate_bindings_v1(binding_id),
  metadata jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default clock_timestamp(),
  created_at timestamptz not null default clock_timestamp(),
  unique(assignment_id,gate_kind,evidence_sha256)
);

create or replace function integration_control.penta_assignment_release_gate_binding_immutable_v1()
returns trigger
language plpgsql
security definer
set search_path='pg_catalog','integration_control'
as $fn$
begin
  raise exception 'append_only_assignment_release_gate_binding';
end
$fn$;

drop trigger if exists penta_assignment_release_gate_bindings_immutable_v1
  on integration_control.penta_assignment_release_gate_bindings_v1;
create trigger penta_assignment_release_gate_bindings_immutable_v1
before update or delete on integration_control.penta_assignment_release_gate_bindings_v1
for each row execute function integration_control.penta_assignment_release_gate_binding_immutable_v1();

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
  v_expected_authority text;
  v_authority_current boolean:=false;
  v_id uuid;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required';
  end if;

  select * into a from integration_control.penta_assignment_contracts_v1
  where assignment_id=p_assignment_id;
  if not found then raise exception 'assignment_not_found'; end if;

  if p_gate_kind not in ('PENTASECURITY','CHLOM_RIGHTS','CIE') then
    raise exception 'release_gate_kind_invalid';
  end if;
  if p_disposition not in ('PASS','NOT_APPLICABLE','HOLD','FAIL') then
    raise exception 'release_gate_disposition_invalid';
  end if;

  -- These identifiers are resolved from current authoritative runtime/census truth,
  -- not invented aliases. PentaSecurity is registered in penta_system_registry;
  -- CHLOM core is the current PentaCensus entity `chlom_core`; CIE's framework id
  -- is `ct.framework.cultural-imprint-engine` in the maintained framework package.
  v_expected_authority:=case p_gate_kind
    when 'PENTASECURITY' then 'penta.security'
    when 'CHLOM_RIGHTS' then 'chlom_core'
    when 'CIE' then 'ct.framework.cultural-imprint-engine'
  end;
  if lower(coalesce(p_authority_system_key,''))<>v_expected_authority then
    raise exception 'release_gate_authority_mismatch';
  end if;

  if p_gate_kind='PENTASECURITY' then
    select exists(
      select 1 from public.penta_system_registry s
      where s.system_key='penta.security' and s.canonical_name='PentaSecurity'
    ) into v_authority_current;
  elsif p_gate_kind='CHLOM_RIGHTS' then
    select exists(
      select 1 from integration_control.penta_census_entities_v1 e
      where e.current and e.entity_key='chlom_core' and e.canonical_name='CHLOM Metaprotocol Control Plane'
    ) into v_authority_current;
  elsif p_gate_kind='CIE' then
    select exists(
      select 1 from institutional_federation.framework_package_registry p
      where p.package_id='ct.framework-package.cie'
        and p.framework_id='ct.framework.cultural-imprint-engine'
        and lower(p.package_state)='maintained'
        and p.authority_ceiling='D2'
        and p.d3_human_reserved
    ) into v_authority_current;
  end if;
  if not v_authority_current then raise exception 'release_gate_authority_registry_not_current'; end if;

  if a.exact_head_sha !~ '^[0-9a-f]{40}$' or p_exact_head_sha<>a.exact_head_sha then
    raise exception 'release_gate_exact_head_mismatch';
  end if;
  if a.exact_artifact_sha256 !~ '^[0-9a-f]{64}$' or p_subject_sha256<>a.exact_artifact_sha256 then
    raise exception 'release_gate_subject_digest_mismatch';
  end if;
  if coalesce(p_evidence_ref,'')='' or p_evidence_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception 'release_gate_evidence_invalid';
  end if;

  if not exists(
    select 1 from chlom_runtime.dail_events d
    where d.event_id=p_dail_event_id and d.event_hash=p_dail_event_hash
  ) then
    raise exception 'release_gate_dail_readback_required';
  end if;

  if p_supersedes_binding_id is not null and not exists(
    select 1 from integration_control.penta_assignment_release_gate_bindings_v1 b
    where b.binding_id=p_supersedes_binding_id
      and b.assignment_id=p_assignment_id
      and b.gate_kind=p_gate_kind
  ) then
    raise exception 'release_gate_supersession_invalid';
  end if;

  insert into integration_control.penta_assignment_release_gate_bindings_v1(
    assignment_id,gate_kind,disposition,authority_system_key,exact_head_sha,subject_sha256,
    evidence_ref,evidence_sha256,dail_event_id,dail_event_hash,supersedes_binding_id,metadata
  ) values (
    p_assignment_id,p_gate_kind,p_disposition,lower(p_authority_system_key),p_exact_head_sha,p_subject_sha256,
    p_evidence_ref,p_evidence_sha256,p_dail_event_id,p_dail_event_hash,p_supersedes_binding_id,
    coalesce(p_metadata,'{}'::jsonb)||jsonb_build_object('authority_created',false,'binding_only',true)
  )
  on conflict(assignment_id,gate_kind,evidence_sha256) do nothing
  returning binding_id into v_id;

  if v_id is null then
    select binding_id into v_id
    from integration_control.penta_assignment_release_gate_bindings_v1
    where assignment_id=p_assignment_id and gate_kind=p_gate_kind and evidence_sha256=p_evidence_sha256;
  end if;

  return jsonb_build_object(
    'binding_id',v_id,'assignment_id',p_assignment_id,'gate_kind',p_gate_kind,
    'disposition',p_disposition,'authority_system_key',lower(p_authority_system_key),
    'exact_head_sha',p_exact_head_sha,'subject_sha256',p_subject_sha256,
    'authority_created',false,'certification_issued',false,'release_authorized',false
  );
end
$fn$;

create or replace function integration_control.penta_assignment_certifier_preflight_v1(p_assignment_id uuid)
returns jsonb
language plpgsql
stable
security definer
set search_path='pg_catalog','integration_control'
as $fn$
declare
  a integration_control.penta_assignment_contracts_v1%rowtype;
  i integration_control.penta_assignment_institutionalization_v1%rowtype;
  v_missing jsonb:='[]'::jsonb;
  v_required integer:=0;
  v_pass integer:=0;
  v_security text;
  v_chlom text;
  v_cie text;
begin
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id;
  if not found then
    return jsonb_build_object('contract','ct.penta.assignment.certifier-preflight.v1','ready',false,'missing',jsonb_build_array('ASSIGNMENT_NOT_FOUND'));
  end if;
  select * into i from integration_control.penta_assignment_institutionalization_v1 where assignment_id=p_assignment_id;

  if a.state<>'AWAITING_CERTIFICATION' then v_missing:=v_missing||jsonb_build_array('STATE_AWAITING_CERTIFICATION'); end if;
  if not coalesce(a.independent_certification_required,false) then v_missing:=v_missing||jsonb_build_array('INDEPENDENT_CERTIFICATION_REQUIRED'); end if;
  if a.risk_class not in ('D0','D1','D2') then v_missing:=v_missing||jsonb_build_array('D3_HUMAN_RESERVED'); end if;
  if coalesce(a.provider_write_allowed,false) or coalesce(a.money_movement_allowed,false) or coalesce(a.credential_change_allowed,false) or coalesce(a.authority_expansion,false) then
    v_missing:=v_missing||jsonb_build_array('RESERVED_EFFECT');
  end if;
  if lower(coalesce(a.certifier_penta,'')) not in ('pentacertify','pentacertifier','penta.certify','ct.penta.certifier') then
    v_missing:=v_missing||jsonb_build_array('INDEPENDENT_CERTIFIER_IDENTITY');
  end if;
  if exists(select 1 from jsonb_array_elements_text(coalesce(a.owner_pentas,'[]'::jsonb)) o where lower(o.value)=lower(coalesce(a.certifier_penta,''))) then
    v_missing:=v_missing||jsonb_build_array('CERTIFIER_OWNER_COLLISION');
  end if;
  if a.exact_head_sha !~ '^[0-9a-f]{40}$' then v_missing:=v_missing||jsonb_build_array('EXACT_HEAD'); end if;
  if a.exact_artifact_sha256 !~ '^[0-9a-f]{64}$' then v_missing:=v_missing||jsonb_build_array('EXACT_SUBJECT_DIGEST'); end if;

  if i.assignment_id is null or not coalesce(i.evidence_readback,false) then v_missing:=v_missing||jsonb_build_array('DAIL_EVIDENCE'); end if;
  if i.assignment_id is null or not coalesce(i.decision_readback,false) then v_missing:=v_missing||jsonb_build_array('DAIL_DECISION'); end if;
  if i.assignment_id is null or not coalesce(i.execution_readback,false) then v_missing:=v_missing||jsonb_build_array('DAIL_EXECUTION'); end if;
  if i.assignment_id is null or i.pentadocs_state<>'READBACK_PASS' then v_missing:=v_missing||jsonb_build_array('PENTADOCS'); end if;
  if i.assignment_id is null or i.provider_projection_state<>'READBACK_PASS' or not coalesce(i.drive_human_readback,false) or not coalesce(i.drive_hybrid_readback,false) or not coalesce(i.drive_machine_readback,false) then
    v_missing:=v_missing||jsonb_build_array('THREE_WAY_PROVIDER_PROJECTION');
  end if;

  v_required:=jsonb_array_length(coalesce(a.owner_pentas,'[]'::jsonb));
  select count(*) into v_pass
  from jsonb_array_elements_text(coalesce(a.owner_pentas,'[]'::jsonb)) owner_name
  where (
    select r.result_state from integration_control.penta_assignment_owner_results_v1 r
    where r.assignment_id=a.assignment_id and lower(r.owner_penta)=lower(owner_name.value)
    order by r.observed_at desc,r.created_at desc,r.result_id desc limit 1
  )='PASS';
  if v_pass<v_required then v_missing:=v_missing||jsonb_build_array('OWNER_RESULTS:'||v_pass::text||'/'||v_required::text); end if;

  if a.source_pr_number is not null and not exists(
    select 1 from integration_control.penta_assignment_pr_links_v1 l
    where l.assignment_id=a.assignment_id and l.exact_head_sha=a.exact_head_sha and l.state<>'SUPERSEDED'
  ) then v_missing:=v_missing||jsonb_build_array('EXACT_HEAD_PR_LINK'); end if;

  select disposition into v_security from integration_control.penta_assignment_release_gate_bindings_v1
  where assignment_id=a.assignment_id and gate_kind='PENTASECURITY' and exact_head_sha=a.exact_head_sha and subject_sha256=a.exact_artifact_sha256
  order by observed_at desc,created_at desc limit 1;
  select disposition into v_chlom from integration_control.penta_assignment_release_gate_bindings_v1
  where assignment_id=a.assignment_id and gate_kind='CHLOM_RIGHTS' and exact_head_sha=a.exact_head_sha and subject_sha256=a.exact_artifact_sha256
  order by observed_at desc,created_at desc limit 1;
  select disposition into v_cie from integration_control.penta_assignment_release_gate_bindings_v1
  where assignment_id=a.assignment_id and gate_kind='CIE' and exact_head_sha=a.exact_head_sha and subject_sha256=a.exact_artifact_sha256
  order by observed_at desc,created_at desc limit 1;

  if coalesce(v_security,'')<>'PASS' then v_missing:=v_missing||jsonb_build_array('PENTASECURITY_EXACT_SUBJECT_PASS'); end if;
  if coalesce(v_chlom,'') not in ('PASS','NOT_APPLICABLE') then v_missing:=v_missing||jsonb_build_array('CHLOM_RIGHTS_AUTHORITY'); end if;
  if coalesce(v_cie,'') not in ('PASS','NOT_APPLICABLE') then v_missing:=v_missing||jsonb_build_array('CIE_APPLICABILITY_OR_PASS'); end if;

  return jsonb_build_object(
    'contract','ct.penta.assignment.certifier-preflight.v1',
    'assignment_id',a.assignment_id,'assignment_key',a.assignment_key,
    'exact_head_sha',a.exact_head_sha,'subject_sha256',a.exact_artifact_sha256,
    'ready',jsonb_array_length(v_missing)=0,'missing',v_missing,
    'gate_dispositions',jsonb_build_object('PENTASECURITY',v_security,'CHLOM_RIGHTS',v_chlom,'CIE',v_cie),
    'owner_pass_count',v_pass,'owner_required_count',v_required,
    'authority_created',false,'certification_issued',false,'release_authorized',false
  );
end
$fn$;

create or replace function integration_control.penta_assignment_enqueue_independent_certifier_v1(p_assignment_id uuid)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','integration_control','extensions','chlom_runtime'
as $fn$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  v_pre jsonb;
  v_snapshot jsonb;
  v_digest text;
  v_task_key text;
  v_task_id uuid;
  v_dail jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id;
  if not found then raise exception 'assignment_not_found'; end if;

  v_pre:=integration_control.penta_assignment_certifier_preflight_v1(p_assignment_id);
  if not coalesce((v_pre->>'ready')::boolean,false) then
    return jsonb_build_object('state','HOLD','reason','UPSTREAM_RELEASE_GATES_MISSING','preflight',v_pre,'authority_created',false);
  end if;

  if a.source_repo is null or a.source_pr_number is null then
    return jsonb_build_object('state','HOLD','reason','EXACT_PROVIDER_SUBJECT_REQUIRED','preflight',v_pre,'authority_created',false);
  end if;

  v_snapshot:=jsonb_build_object(
    'contract','ct.penta.assignment.independent-certifier-work.v1',
    'assignment_id',a.assignment_id,'assignment_key',a.assignment_key,
    'repository',a.source_repo,'pr_number',a.source_pr_number,
    'head_sha',a.exact_head_sha,'exact_artifact_ref',a.exact_artifact_ref,
    'subject_sha256',a.exact_artifact_sha256,'preflight',v_pre,
    'certifier',a.certifier_penta,'authority_expansion',false,'production_deploy',false
  );
  v_digest:=encode(extensions.digest(convert_to(v_snapshot::text,'UTF8'),'sha256'),'hex');
  v_task_key:='assignment-independent-certifier:'||a.assignment_id::text||':'||a.exact_head_sha||':'||left(v_digest,16);

  insert into integration_control.penta_certify_tasks_v3(
    task_key,surface_id,provider_system,source_certification_state,task_kind,owner_component_key,
    risk_class,state,attempt_count,max_attempts,available_at,source_snapshot,evidence,software_generation
  ) values (
    v_task_key,'github-pr:'||a.source_repo||'#'||a.source_pr_number::text,'ThriveBase+GitHub',
    'assignment_awaiting_independent_certification','inspect','penta.certify',a.risk_class,
    'queued',0,3,now(),v_snapshot,
    jsonb_build_object('assignment_id',a.assignment_id,'preflight_contract','ct.penta.assignment.certifier-preflight.v1','source_snapshot_sha256',v_digest,'authority_created',false,'certification_issued',false),
    1
  ) on conflict(task_key) do nothing returning task_id into v_task_id;

  if v_task_id is null then select task_id into v_task_id from integration_control.penta_certify_tasks_v3 where task_key=v_task_key; end if;

  v_dail:=chlom_runtime.append_dail_event(
    'penta.assignment.independent-certifier.queued.v1','penta_assignment_certifier_work',a.assignment_id::text,
    jsonb_build_object('task_id',v_task_id,'task_key',v_task_key,'exact_head_sha',a.exact_head_sha,'subject_sha256',a.exact_artifact_sha256,'source_snapshot_sha256',v_digest,'authority_created',false,'certification_issued',false,'release_authorized',false),
    'PentaAssignment/PentaCertify',null,'PentaAssignment','1.0.0','ctcorr:penta-assignment:'||a.assignment_id::text,null,
    'ct.penta.assignment.independent-certifier-work.v1',null,'internal'
  );

  return jsonb_build_object('state','QUEUED','task_id',v_task_id,'task_key',v_task_key,'source_snapshot_sha256',v_digest,'dail',v_dail,'authority_created',false,'certification_issued',false,'release_authorized',false);
end
$fn$;

revoke all on table integration_control.penta_assignment_release_gate_bindings_v1 from public,anon,authenticated;
grant select on table integration_control.penta_assignment_release_gate_bindings_v1 to service_role;
revoke all on function integration_control.penta_assignment_bind_release_gate_v1(uuid,text,text,text,text,text,text,text,uuid,text,uuid,jsonb) from public,anon,authenticated;
revoke all on function integration_control.penta_assignment_certifier_preflight_v1(uuid) from public,anon,authenticated;
revoke all on function integration_control.penta_assignment_enqueue_independent_certifier_v1(uuid) from public,anon,authenticated;
grant execute on function integration_control.penta_assignment_bind_release_gate_v1(uuid,text,text,text,text,text,text,text,uuid,text,uuid,jsonb) to service_role;
grant execute on function integration_control.penta_assignment_certifier_preflight_v1(uuid) to service_role;
grant execute on function integration_control.penta_assignment_enqueue_independent_certifier_v1(uuid) to service_role;
