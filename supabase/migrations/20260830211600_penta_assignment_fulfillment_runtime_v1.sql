-- CrownThrive Penta Assignment Fulfillment Runtime v1

create or replace function integration_control.penta_assignment_create_v1(
  p_assignment_key text,
  p_subject_kind text,
  p_subject_ref text,
  p_task_kind text,
  p_title text,
  p_summary text,
  p_family_key text,
  p_owner_pentas jsonb,
  p_risk_class text,
  p_authority_ceiling text,
  p_exact_artifact_ref text,
  p_exact_artifact_sha256 text default null,
  p_source_repo text default null,
  p_source_pr_number bigint default null,
  p_exact_head_sha text default null,
  p_acceptance_criteria jsonb default '[]'::jsonb,
  p_provider_write_allowed boolean default false,
  p_priority text default 'P2',
  p_metadata jsonb default '{}'::jsonb
) returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','extensions','chlom_runtime'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_id uuid;
  v_event jsonb;
  v_payload jsonb;
  v_sha text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if nullif(btrim(coalesce(p_assignment_key,'')),'') is null or nullif(btrim(coalesce(p_exact_artifact_ref,'')),'') is null then raise exception 'assignment_identity_required'; end if;
  if p_risk_class not in ('D0','D1','D2') or p_authority_ceiling not in ('D0','D1','D2') then raise exception 'D3_human_reserved'; end if;
  if jsonb_typeof(coalesce(p_owner_pentas,'[]'::jsonb))<>'array' or jsonb_array_length(coalesce(p_owner_pentas,'[]'::jsonb))=0 then raise exception 'owner_pentas_required'; end if;
  if not exists(select 1 from integration_control.penta_family_obligation_contracts_v1 where family_key=p_family_key and state='ACTIVE') then raise exception 'family_contract_not_active'; end if;
  if p_exact_artifact_sha256 is not null and p_exact_artifact_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'artifact_digest_invalid'; end if;
  if p_exact_head_sha is not null and p_exact_head_sha !~ '^[0-9a-f]{40}$' then raise exception 'head_sha_invalid'; end if;

  insert into integration_control.penta_assignment_contracts_v1(
    assignment_key,subject_kind,subject_ref,task_kind,title,summary,owning_family_key,owner_pentas,
    risk_class,authority_ceiling,source_repo,source_pr_number,exact_head_sha,exact_artifact_ref,
    exact_artifact_sha256,acceptance_criteria,independent_certification_required,provider_write_allowed,
    priority,metadata,state
  ) values (
    p_assignment_key,p_subject_kind,p_subject_ref,p_task_kind,p_title,p_summary,p_family_key,p_owner_pentas,
    p_risk_class,p_authority_ceiling,p_source_repo,p_source_pr_number,p_exact_head_sha,p_exact_artifact_ref,
    p_exact_artifact_sha256,coalesce(p_acceptance_criteria,'[]'::jsonb),p_risk_class in ('D1','D2'),
    coalesce(p_provider_write_allowed,false),coalesce(p_priority,'P2'),coalesce(p_metadata,'{}'::jsonb),'DISCOVERED'
  ) on conflict(assignment_key) do update set
    subject_ref=excluded.subject_ref,title=excluded.title,summary=excluded.summary,
    owner_pentas=excluded.owner_pentas,exact_head_sha=excluded.exact_head_sha,
    exact_artifact_ref=excluded.exact_artifact_ref,exact_artifact_sha256=excluded.exact_artifact_sha256,
    acceptance_criteria=excluded.acceptance_criteria,
    metadata=integration_control.penta_assignment_contracts_v1.metadata||excluded.metadata,
    state=case
      when integration_control.penta_assignment_contracts_v1.state in ('COMPLETED','SUPERSEDED','RETIRED')
       and integration_control.penta_assignment_contracts_v1.exact_head_sha is distinct from excluded.exact_head_sha
      then 'DISCOVERED'
      else integration_control.penta_assignment_contracts_v1.state end,
    updated_at=now()
  returning assignment_id into v_id;

  insert into integration_control.penta_assignment_institutionalization_v1(assignment_id)
  values(v_id) on conflict(assignment_id) do nothing;

  v_payload:=jsonb_build_object(
    'assignment_id',v_id,'assignment_key',p_assignment_key,'subject_kind',p_subject_kind,'subject_ref',p_subject_ref,
    'task_kind',p_task_kind,'family_key',p_family_key,'owner_pentas',p_owner_pentas,'risk_class',p_risk_class,
    'authority_ceiling',p_authority_ceiling,'exact_artifact_ref',p_exact_artifact_ref,
    'exact_artifact_sha256',p_exact_artifact_sha256,'source_repo',p_source_repo,'source_pr_number',p_source_pr_number,
    'exact_head_sha',p_exact_head_sha,'provider_write_allowed',coalesce(p_provider_write_allowed,false),
    'money_movement',false,'credential_change',false,'d3_execution',false,'authority_expansion',false,
    'created_at',clock_timestamp()
  );
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  insert into integration_control.penta_assignment_events_v1(assignment_id,event_type,actor_ref,state,payload,payload_sha256)
  values(v_id,'ASSIGNMENT_CREATED','PentaAssignmentFabric','DISCOVERED',v_payload,v_sha);
  v_event:=chlom_runtime.append_dail_event(
    'penta.assignment.created','penta_assignment',v_id::text,
    v_payload||jsonb_build_object('evidence_sha256',v_sha),
    'PentaAssignmentFabric/PentaCensus/PentaWire',null,'PentaAssignmentFabric','1.0.0',
    'ctcorr:penta-assignment:'||v_id::text,null,'ct.penta.assignment-fulfillment.v1',null,'internal'
  );
  return jsonb_build_object('assignment_id',v_id,'state','DISCOVERED','event',v_event,'evidence_sha256',v_sha);
end $$;

create or replace function integration_control.penta_assignment_route_v1(p_assignment_id uuid)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','penta_os20','extensions','chlom_runtime','public'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  v_owner text;
  v_penta_id uuid;
  v_task_id uuid;
  v_discovery_key text;
  v_handoff_key text;
  v_payload jsonb;
  v_sha text;
  v_dispatches integer:=0;
  v_event jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id for update;
  if not found then raise exception 'assignment_not_found'; end if;
  if a.state in ('COMPLETED','SUPERSEDED','RETIRED') then return jsonb_build_object('assignment_id',a.assignment_id,'state',a.state,'dispatches',0); end if;

  v_discovery_key:='penta-assignment:'||a.assignment_id::text;
  insert into integration_control.penta_census_discoveries_v1(
    discovery_key,entity_kind,entity_key,canonical_name,source_ref,tags,rationale,risk_class,state,evidence
  ) values (
    v_discovery_key,'penta_assignment',a.assignment_key,a.title,a.exact_artifact_ref,
    array['assignment',a.owning_family_key,a.task_kind]::text[],
    'Governed assignment accepted for owner execution and institutional completion.',a.risk_class,'routed',
    jsonb_build_object('assignment_id',a.assignment_id,'owner_pentas',a.owner_pentas,'authority_expansion',false)
  ) on conflict(discovery_key) do update set
    last_seen_at=now(),state=case when integration_control.penta_census_discoveries_v1.state='resolved' then 'resolved' else 'routed' end,
    evidence=integration_control.penta_census_discoveries_v1.evidence||excluded.evidence;

  for v_owner in select jsonb_array_elements_text(a.owner_pentas) loop
    v_payload:=jsonb_build_object(
      'contract','ct.penta.assignment-fulfillment.v1','assignment_id',a.assignment_id,'assignment_key',a.assignment_key,
      'subject_ref',a.subject_ref,'task_kind',a.task_kind,'title',a.title,'summary',a.summary,
      'family_key',a.owning_family_key,'owner_penta',v_owner,'risk_class',a.risk_class,
      'authority_ceiling',a.authority_ceiling,'exact_artifact_ref',a.exact_artifact_ref,
      'exact_artifact_sha256',a.exact_artifact_sha256,'source_repo',a.source_repo,
      'source_pr_number',a.source_pr_number,'exact_head_sha',a.exact_head_sha,
      'acceptance_criteria',a.acceptance_criteria,'required_projections',to_jsonb(a.required_projections),
      'money_movement',false,'credential_change',false,'d3_execution',false,'authority_expansion',false
    );
    v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
    select id into v_penta_id from penta_os20.pentas where lower(canonical_name)=lower(v_owner) and status='active' limit 1;
    if v_penta_id is not null then
      insert into penta_os20.execution_tasks(task_key,penta_id,release_version,operation_key,estimated_units,status,authority_check)
      values('assignment:'||a.assignment_id::text||':'||lower(regexp_replace(v_owner,'[^A-Za-z0-9]+','-','g')),v_penta_id,'OS-2.0.0',a.task_kind,1,'queued',v_payload)
      on conflict(task_key) do update set authority_check=penta_os20.execution_tasks.authority_check||excluded.authority_check
      returning id into v_task_id;
      begin perform public.penta_os20_authorize_task(v_task_id); exception when others then null; end;
      insert into integration_control.penta_assignment_dispatches_v1(assignment_id,owner_penta,family_key,dispatch_kind,external_ref,state,evidence,evidence_sha256)
      values(a.assignment_id,v_owner,a.owning_family_key,'OS20_TASK',v_task_id::text,'ROUTED',v_payload,v_sha)
      on conflict(assignment_id,owner_penta,dispatch_kind) do update set external_ref=excluded.external_ref,evidence=excluded.evidence,evidence_sha256=excluded.evidence_sha256,updated_at=now();
    else
      v_handoff_key:='assignment:'||a.assignment_id::text||':'||lower(regexp_replace(v_owner,'[^A-Za-z0-9]+','-','g'));
      insert into integration_control.penta_census_handoffs_v1(handoff_key,discovery_key,tag,target_ref,risk_class,state,authority_note,payload)
      values(v_handoff_key,v_discovery_key,'assignment:'||a.task_kind,v_owner,a.risk_class,'queued','D0-D2 owner obligation route; no authority expansion',v_payload)
      on conflict(handoff_key) do update set
        payload=excluded.payload,
        state=case when integration_control.penta_census_handoffs_v1.state='completed' then 'completed' else 'queued' end,
        updated_at=now();
      insert into integration_control.penta_assignment_dispatches_v1(assignment_id,owner_penta,family_key,dispatch_kind,external_ref,state,evidence,evidence_sha256)
      values(a.assignment_id,v_owner,a.owning_family_key,'CENSUS_HANDOFF',v_handoff_key,'ROUTED',v_payload,v_sha)
      on conflict(assignment_id,owner_penta,dispatch_kind) do update set evidence=excluded.evidence,evidence_sha256=excluded.evidence_sha256,updated_at=now();
    end if;
    v_dispatches:=v_dispatches+1;
  end loop;

  update integration_control.penta_assignment_contracts_v1
  set state=case when state='DISCOVERED' then 'ROUTED' else state end,updated_at=now()
  where assignment_id=a.assignment_id;
  v_event:=chlom_runtime.append_dail_event(
    'penta.assignment.routed','penta_assignment',a.assignment_id::text,
    jsonb_build_object('assignment_key',a.assignment_key,'family_key',a.owning_family_key,'owner_pentas',a.owner_pentas,'dispatch_count',v_dispatches,'authority_expansion',false,'routed_at',clock_timestamp()),
    'PentaAssignmentFabric/PentaCensus/PentaWire/PentaRoute',null,'PentaAssignmentFabric','1.0.0',
    'ctcorr:penta-assignment:'||a.assignment_id::text,null,'ct.penta.assignment-fulfillment.v1',null,'internal'
  );
  return jsonb_build_object('assignment_id',a.assignment_id,'state','ROUTED','dispatches',v_dispatches,'event',v_event);
end $$;

create or replace function integration_control.penta_assignment_record_owner_result_v1(
  p_assignment_id uuid,
  p_owner_penta text,
  p_result_state text,
  p_exact_artifact_ref text,
  p_exact_artifact_sha256 text,
  p_exact_head_sha text,
  p_evidence jsonb default '{}'::jsonb
) returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','extensions','chlom_runtime'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  v_payload jsonb;
  v_sha text;
  v_event jsonb;
  v_result_id uuid;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id;
  if not found then raise exception 'assignment_not_found'; end if;
  if not (a.owner_pentas ? p_owner_penta) then raise exception 'owner_not_assigned'; end if;
  if p_result_state not in ('PASS','HOLD','FAIL','SUPERSEDED') then raise exception 'result_state_invalid'; end if;
  if p_exact_artifact_sha256 is not null and p_exact_artifact_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'artifact_digest_invalid'; end if;
  if a.exact_head_sha is not null and p_exact_head_sha is distinct from a.exact_head_sha then raise exception 'exact_head_mismatch'; end if;
  v_payload:=jsonb_build_object(
    'assignment_id',a.assignment_id,'assignment_key',a.assignment_key,'owner_penta',p_owner_penta,
    'result_state',p_result_state,'exact_artifact_ref',p_exact_artifact_ref,
    'exact_artifact_sha256',p_exact_artifact_sha256,'exact_head_sha',p_exact_head_sha,
    'evidence',coalesce(p_evidence,'{}'::jsonb),'observed_at',clock_timestamp(),'authority_expansion',false
  );
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  v_event:=chlom_runtime.append_dail_event(
    'penta.assignment.owner_result.'||lower(p_result_state),'penta_assignment_owner_result',
    a.assignment_id::text||':'||p_owner_penta,v_payload||jsonb_build_object('evidence_sha256',v_sha),
    p_owner_penta,null,p_owner_penta,'1.0.0','ctcorr:penta-assignment:'||a.assignment_id::text,null,
    'ct.penta.assignment-fulfillment.v1',null,'internal'
  );
  insert into integration_control.penta_assignment_owner_results_v1(
    assignment_id,owner_penta,result_state,exact_artifact_ref,exact_artifact_sha256,exact_head_sha,
    evidence,evidence_sha256,dail_event_id,dail_event_hash
  ) values (
    a.assignment_id,p_owner_penta,p_result_state,p_exact_artifact_ref,p_exact_artifact_sha256,p_exact_head_sha,
    coalesce(p_evidence,'{}'::jsonb),v_sha,(v_event->>'event_id')::uuid,v_event->>'event_hash'
  ) returning result_id into v_result_id;
  update integration_control.penta_assignment_dispatches_v1 set
    state=case when p_result_state='PASS' then 'COMPLETED' when p_result_state='HOLD' then 'HOLD' when p_result_state='FAIL' then 'FAILED' else 'SUPERSEDED' end,
    completed_at=case when p_result_state in ('PASS','SUPERSEDED') then now() else completed_at end,
    updated_at=now()
  where assignment_id=a.assignment_id and lower(owner_penta)=lower(p_owner_penta);
  update integration_control.penta_assignment_contracts_v1 set
    state=case when p_result_state='FAIL' then 'FAILED' when p_result_state='HOLD' then 'HOLD' else 'IN_PROGRESS' end,
    updated_at=now()
  where assignment_id=a.assignment_id and state not in ('COMPLETED','SUPERSEDED','RETIRED');
  return jsonb_build_object('result_id',v_result_id,'assignment_id',a.assignment_id,'state',p_result_state,'evidence_sha256',v_sha,'dail',v_event);
end $$;

create or replace function integration_control.penta_assignment_bind_provider_projection_v1(
  p_assignment_id uuid,
  p_drive_folder_id text,
  p_human_doc_id text,p_human_doc_url text,p_human_sha256 text,p_human_readback boolean,
  p_hybrid_doc_id text,p_hybrid_doc_url text,p_hybrid_sha256 text,p_hybrid_readback boolean,
  p_machine_sheet_id text,p_machine_sheet_url text,p_machine_sha256 text,p_machine_readback boolean,
  p_provider_evidence jsonb default '{}'::jsonb
) returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','extensions','chlom_runtime'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  v_state text;
  v_payload jsonb;
  v_sha text;
  v_event jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id;
  if not found then raise exception 'assignment_not_found'; end if;
  if nullif(p_drive_folder_id,'') is null or nullif(p_human_doc_id,'') is null or nullif(p_hybrid_doc_id,'') is null or nullif(p_machine_sheet_id,'') is null then raise exception 'three_way_drive_projection_required'; end if;
  if p_human_sha256 !~ '^[0-9a-f]{64}$' or p_hybrid_sha256 !~ '^[0-9a-f]{64}$' or p_machine_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'projection_digest_invalid'; end if;
  v_state:=case when p_human_readback and p_hybrid_readback and p_machine_readback then 'READBACK_PASS' else 'PARTIAL' end;
  update integration_control.penta_assignment_institutionalization_v1 set
    drive_folder_id=p_drive_folder_id,
    drive_human_doc_id=p_human_doc_id,drive_human_doc_url=p_human_doc_url,drive_human_sha256=p_human_sha256,drive_human_readback=p_human_readback,
    drive_hybrid_doc_id=p_hybrid_doc_id,drive_hybrid_doc_url=p_hybrid_doc_url,drive_hybrid_sha256=p_hybrid_sha256,drive_hybrid_readback=p_hybrid_readback,
    drive_machine_sheet_id=p_machine_sheet_id,drive_machine_sheet_url=p_machine_sheet_url,drive_machine_sha256=p_machine_sha256,drive_machine_readback=p_machine_readback,
    provider_projection_state=v_state,updated_at=now()
  where assignment_id=a.assignment_id;
  v_payload:=jsonb_build_object(
    'assignment_id',a.assignment_id,'assignment_key',a.assignment_key,'drive_folder_id',p_drive_folder_id,
    'human',jsonb_build_object('doc_id',p_human_doc_id,'url',p_human_doc_url,'sha256',p_human_sha256,'readback',p_human_readback),
    'hybrid',jsonb_build_object('doc_id',p_hybrid_doc_id,'url',p_hybrid_doc_url,'sha256',p_hybrid_sha256,'readback',p_hybrid_readback),
    'machine',jsonb_build_object('sheet_id',p_machine_sheet_id,'url',p_machine_sheet_url,'sha256',p_machine_sha256,'readback',p_machine_readback),
    'provider_evidence',coalesce(p_provider_evidence,'{}'::jsonb),'projection_state',v_state,
    'raw_secret_material',false,'observed_at',clock_timestamp()
  );
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  v_event:=chlom_runtime.append_dail_event(
    'penta.assignment.drive_projection.'||lower(v_state),'penta_assignment_provider_projection',a.assignment_id::text,
    v_payload||jsonb_build_object('evidence_sha256',v_sha),'PentaDrive/PentaDocs/PentaSync/PentaSerialized',
    null,'PentaDrive','1.0.0','ctcorr:penta-assignment:'||a.assignment_id::text,null,
    'ct.penta.institutionalization.v1',null,'internal'
  );
  return jsonb_build_object('assignment_id',a.assignment_id,'state',v_state,'evidence_sha256',v_sha,'dail',v_event);
end $$;
