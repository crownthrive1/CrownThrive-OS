-- CrownThrive Penta Assignment Institutionalization Runtime v1

alter table integration_control.penta_assignment_institutionalization_v1
  add column if not exists activation_event_id uuid,
  add column if not exists activation_event_hash text,
  add column if not exists activation_readback boolean not null default false;

create table if not exists integration_control.penta_assignment_os_projection_v1 (
  assignment_id uuid primary key references integration_control.penta_assignment_contracts_v1(assignment_id),
  assignment_key text not null,
  stable_identity text not null,
  exact_artifact_ref text not null,
  exact_artifact_sha256 text,
  exact_head_sha text,
  risk_class text not null,
  lifecycle_state text not null,
  owner_pentas jsonb not null,
  certification_id text,
  certification_state text not null,
  certification_event_id uuid,
  evidence_event_id uuid,
  decision_event_id uuid,
  execution_event_id uuid,
  drive_refs jsonb not null default '{}'::jsonb,
  pentadocs_ref text,
  rollback_state text not null default 'PRESERVED',
  production_status text not null default 'NOT_CLAIMED',
  projection_state text not null default 'PROJECTED',
  projection_event_id uuid,
  projection_event_hash text,
  projected_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

revoke all on integration_control.penta_assignment_os_projection_v1 from public,anon,authenticated;

create or replace function penta_docs.project_assignment_v1(p_assignment_id uuid)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','penta_docs','integration_control','extensions'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  i integration_control.penta_assignment_institutionalization_v1%rowtype;
  v_body jsonb;
  v_sha text;
  v_id uuid;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id;
  if not found then raise exception 'assignment_not_found'; end if;
  select * into i from integration_control.penta_assignment_institutionalization_v1 where assignment_id=p_assignment_id;
  if not found then raise exception 'institutionalization_row_not_found'; end if;

  v_body:=jsonb_build_object(
    'contract','ct.penta.institutionalization.v1',
    'assignment_id',a.assignment_id,'assignment_key',a.assignment_key,
    'subject_kind',a.subject_kind,'subject_ref',a.subject_ref,'task_kind',a.task_kind,
    'title',a.title,'summary',a.summary,'family_key',a.owning_family_key,
    'owner_pentas',a.owner_pentas,'risk_class',a.risk_class,
    'exact_artifact_ref',a.exact_artifact_ref,'exact_artifact_sha256',a.exact_artifact_sha256,
    'exact_head_sha',a.exact_head_sha,'state',a.state,'acceptance_criteria',a.acceptance_criteria,
    'owner_results',(
      select coalesce(jsonb_agg(jsonb_build_object(
        'owner_penta',r.owner_penta,'state',r.result_state,'exact_artifact_ref',r.exact_artifact_ref,
        'evidence_sha256',r.evidence_sha256,'dail_event_id',r.dail_event_id,'observed_at',r.observed_at
      ) order by r.owner_penta,r.observed_at),'[]'::jsonb)
      from integration_control.penta_assignment_owner_results_v1 r where r.assignment_id=a.assignment_id
    ),
    'dail',jsonb_build_object(
      'evidence_event_id',i.evidence_event_id,'decision_event_id',i.decision_event_id,
      'execution_event_id',i.execution_event_id,'activation_event_id',i.activation_event_id
    ),
    'drive_refs',jsonb_build_object(
      'folder_id',i.drive_folder_id,
      'human_doc_id',i.drive_human_doc_id,'human_url',i.drive_human_doc_url,
      'hybrid_doc_id',i.drive_hybrid_doc_id,'hybrid_url',i.drive_hybrid_doc_url,
      'machine_sheet_id',i.drive_machine_sheet_id,'machine_url',i.drive_machine_sheet_url
    ),
    'certification_id',i.certification_id,'certification_state',i.certification_state,
    'os_projection_state',i.os_projection_state,'chain_state',i.chain_state,
    'terminal_gate_state',i.terminal_gate_state,
    'history_preserved',true,'originator_cannot_self_certify',true,
    'projected_at',clock_timestamp()
  );
  v_sha:=encode(extensions.digest(convert_to(v_body::text,'UTF8'),'sha256'),'hex');
  insert into penta_docs.assignment_institutionalization_v1(
    assignment_id,assignment_key,title,summary,family_key,owner_pentas,risk_class,
    exact_artifact_ref,exact_artifact_sha256,exact_head_sha,lifecycle_state,
    evidence_refs,drive_refs,certification_ref,body,body_sha256,docs_path
  ) values (
    a.assignment_id,a.assignment_key,a.title,a.summary,a.owning_family_key,a.owner_pentas,a.risk_class,
    a.exact_artifact_ref,a.exact_artifact_sha256,a.exact_head_sha,a.state,
    jsonb_build_array(i.evidence_event_id,i.decision_event_id,i.execution_event_id,i.activation_event_id),
    jsonb_build_object(
      'folder_id',i.drive_folder_id,
      'human_doc_id',i.drive_human_doc_id,'human_url',i.drive_human_doc_url,
      'hybrid_doc_id',i.drive_hybrid_doc_id,'hybrid_url',i.drive_hybrid_doc_url,
      'machine_sheet_id',i.drive_machine_sheet_id,'machine_url',i.drive_machine_sheet_url
    ),
    i.certification_id,v_body,v_sha,'/internal/penta-assignments/'||a.assignment_key
  ) on conflict(assignment_id) do update set
    lifecycle_state=excluded.lifecycle_state,evidence_refs=excluded.evidence_refs,
    drive_refs=excluded.drive_refs,certification_ref=excluded.certification_ref,
    body=excluded.body,body_sha256=excluded.body_sha256,updated_at=now()
  returning record_id into v_id;
  update integration_control.penta_assignment_institutionalization_v1 set
    pentadocs_record_id=v_id,pentadocs_state='READBACK_PASS',
    pentadocs_ref='/internal/penta-assignments/'||a.assignment_key,
    pentadocs_sha256=v_sha,updated_at=now()
  where assignment_id=a.assignment_id;
  return jsonb_build_object(
    'record_id',v_id,'assignment_id',a.assignment_id,'state','READBACK_PASS',
    'docs_path','/internal/penta-assignments/'||a.assignment_key,'body_sha256',v_sha
  );
end $$;

create or replace function integration_control.penta_assignment_institutionalize_v1(p_assignment_id uuid)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','penta_docs','extensions','chlom_runtime'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  i integration_control.penta_assignment_institutionalization_v1%rowtype;
  v_missing jsonb:='[]'::jsonb;
  v_required integer:=0;
  v_pass integer:=0;
  v_payload jsonb;
  v_sha text;
  v_evidence jsonb;
  v_decision jsonb;
  v_execution jsonb;
  v_docs jsonb;
  v_evidence_ok boolean;
  v_decision_ok boolean;
  v_execution_ok boolean;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id for update;
  if not found then raise exception 'assignment_not_found'; end if;
  select * into i from integration_control.penta_assignment_institutionalization_v1 where assignment_id=p_assignment_id for update;
  if not found then raise exception 'institutionalization_row_not_found'; end if;

  v_required:=jsonb_array_length(a.owner_pentas);
  select count(*) into v_pass
  from jsonb_array_elements_text(a.owner_pentas) owner_name
  where (
    select r.result_state
    from integration_control.penta_assignment_owner_results_v1 r
    where r.assignment_id=a.assignment_id and lower(r.owner_penta)=lower(owner_name.value)
    order by r.observed_at desc,r.created_at desc,r.result_id desc
    limit 1
  )='PASS';
  if v_pass<v_required then v_missing:=v_missing||jsonb_build_array('owner_results:'||v_pass::text||'/'||v_required::text); end if;
  if i.provider_projection_state<>'READBACK_PASS' then v_missing:=v_missing||jsonb_build_array('drive_three_way_readback'); end if;
  if a.exact_head_sha is not null and not exists(
    select 1 from integration_control.penta_assignment_pr_links_v1 l
    where l.assignment_id=a.assignment_id and l.exact_head_sha=a.exact_head_sha and l.state<>'SUPERSEDED'
  ) then v_missing:=v_missing||jsonb_build_array('exact_head_pr_link'); end if;

  if jsonb_array_length(v_missing)>0 then
    update integration_control.penta_assignment_contracts_v1 set
      state=case when state in ('FAILED','HOLD') then state else 'AWAITING_PROJECTION' end,updated_at=now()
    where assignment_id=a.assignment_id;
    return jsonb_build_object('assignment_id',a.assignment_id,'state','HOLD','missing',v_missing);
  end if;

  if i.evidence_event_id is null then
    v_payload:=jsonb_build_object(
      'assignment_id',a.assignment_id,'assignment_key',a.assignment_key,
      'exact_artifact_ref',a.exact_artifact_ref,'exact_artifact_sha256',a.exact_artifact_sha256,
      'exact_head_sha',a.exact_head_sha,
      'owner_results',(
        select jsonb_agg(jsonb_build_object(
          'owner_penta',owner_name.value,
          'result',(
            select jsonb_build_object(
              'result_state',r.result_state,'evidence_sha256',r.evidence_sha256,
              'dail_event_id',r.dail_event_id,'dail_event_hash',r.dail_event_hash,
              'exact_artifact_ref',r.exact_artifact_ref,'exact_artifact_sha256',r.exact_artifact_sha256,
              'observed_at',r.observed_at
            ) from integration_control.penta_assignment_owner_results_v1 r
            where r.assignment_id=a.assignment_id and lower(r.owner_penta)=lower(owner_name.value)
            order by r.observed_at desc,r.created_at desc,r.result_id desc limit 1
          )
        ) order by owner_name.value)
        from jsonb_array_elements_text(a.owner_pentas) owner_name
      ),
      'drive_projection',jsonb_build_object(
        'folder_id',i.drive_folder_id,
        'human_doc_id',i.drive_human_doc_id,'human_sha256',i.drive_human_sha256,'human_readback',i.drive_human_readback,
        'hybrid_doc_id',i.drive_hybrid_doc_id,'hybrid_sha256',i.drive_hybrid_sha256,'hybrid_readback',i.drive_hybrid_readback,
        'machine_sheet_id',i.drive_machine_sheet_id,'machine_sha256',i.drive_machine_sha256,'machine_readback',i.drive_machine_readback
      ),
      'observed_at',clock_timestamp(),'authority_expansion',false
    );
    v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
    v_evidence:=chlom_runtime.append_dail_event(
      'penta.institutionalization.evidence.v1','institutional_evidence',a.assignment_id::text,
      v_payload||jsonb_build_object('evidence_sha256',v_sha),
      'PentaDocs/PentaDrive/PentaCensus/PentaSerialized',null,'PentaDocs','1.0.0',
      'ctcorr:penta-assignment:'||a.assignment_id::text,null,'ct.penta.institutionalization.v1',null,'internal'
    );
    v_evidence_ok:=exists(select 1 from chlom_runtime.dail_events d where d.event_id=(v_evidence->>'event_id')::uuid and d.event_hash=v_evidence->>'event_hash');
    update integration_control.penta_assignment_institutionalization_v1 set
      evidence_event_id=(v_evidence->>'event_id')::uuid,evidence_event_hash=v_evidence->>'event_hash',
      evidence_readback=v_evidence_ok,updated_at=now()
    where assignment_id=a.assignment_id;
  else
    v_evidence:=jsonb_build_object('event_id',i.evidence_event_id,'event_hash',i.evidence_event_hash);
    v_evidence_ok:=i.evidence_readback;
  end if;
  if not v_evidence_ok then return jsonb_build_object('assignment_id',a.assignment_id,'state','HOLD','missing',jsonb_build_array('dail_evidence_readback')); end if;

  select * into i from integration_control.penta_assignment_institutionalization_v1 where assignment_id=a.assignment_id;
  if i.decision_event_id is null then
    v_decision:=chlom_runtime.append_dail_event(
      'penta.institutionalization.decision.v1','institutional_decision',a.assignment_id::text,
      jsonb_build_object(
        'assignment_key',a.assignment_key,
        'decision','OWNER_WORK_COMPLETE_AND_PROVIDER_PROJECTIONS_BOUND',
        'risk_class',a.risk_class,'independent_certification_required',a.independent_certification_required,
        'certifier',a.certifier_penta,'originator_cannot_self_certify',true,
        'evidence_event_id',i.evidence_event_id,'authority_expansion',false,'decided_at',clock_timestamp()
      ),
      'PentaPM/PentaGovernance/PentaCertify',null,'PentaPM','1.0.0',
      'ctcorr:penta-assignment:'||a.assignment_id::text,i.evidence_event_id::text,
      'ct.penta.institutionalization.v1',null,'internal'
    );
    v_decision_ok:=exists(select 1 from chlom_runtime.dail_events d where d.event_id=(v_decision->>'event_id')::uuid and d.event_hash=v_decision->>'event_hash');
    update integration_control.penta_assignment_institutionalization_v1 set
      decision_event_id=(v_decision->>'event_id')::uuid,decision_event_hash=v_decision->>'event_hash',
      decision_readback=v_decision_ok,updated_at=now()
    where assignment_id=a.assignment_id;
  else
    v_decision:=jsonb_build_object('event_id',i.decision_event_id,'event_hash',i.decision_event_hash);
    v_decision_ok:=i.decision_readback;
  end if;
  if not v_decision_ok then return jsonb_build_object('assignment_id',a.assignment_id,'state','HOLD','missing',jsonb_build_array('dail_decision_readback')); end if;

  v_docs:=penta_docs.project_assignment_v1(a.assignment_id);
  select * into i from integration_control.penta_assignment_institutionalization_v1 where assignment_id=a.assignment_id;
  if i.execution_event_id is null then
    v_execution:=chlom_runtime.append_dail_event(
      'penta.institutionalization.execution.v1','institutional_execution',a.assignment_id::text,
      jsonb_build_object(
        'assignment_key',a.assignment_key,'owner_work_complete',true,
        'drive_projection_state',i.provider_projection_state,'pentadocs_projection',v_docs,
        'next_state',case when a.independent_certification_required then 'AWAITING_CERTIFICATION' else 'CERTIFIED' end,
        'evidence_event_id',i.evidence_event_id,'decision_event_id',i.decision_event_id,
        'authority_expansion',false,'executed_at',clock_timestamp()
      ),
      'PentaDocs/PentaDrive/PentaSync/PentaCensus/PentaSerialized',null,'PentaDocs','1.0.0',
      'ctcorr:penta-assignment:'||a.assignment_id::text,i.decision_event_id::text,
      'ct.penta.institutionalization.v1',null,'internal'
    );
    v_execution_ok:=exists(select 1 from chlom_runtime.dail_events d where d.event_id=(v_execution->>'event_id')::uuid and d.event_hash=v_execution->>'event_hash');
    update integration_control.penta_assignment_institutionalization_v1 set
      execution_event_id=(v_execution->>'event_id')::uuid,execution_event_hash=v_execution->>'event_hash',
      execution_readback=v_execution_ok,institutionalized_at=now(),
      certification_state=case when a.independent_certification_required then 'PENDING' else 'NOT_REQUIRED' end,
      updated_at=now()
    where assignment_id=a.assignment_id;
  else
    v_execution:=jsonb_build_object('event_id',i.execution_event_id,'event_hash',i.execution_event_hash);
    v_execution_ok:=i.execution_readback;
  end if;
  if not v_execution_ok then return jsonb_build_object('assignment_id',a.assignment_id,'state','HOLD','missing',jsonb_build_array('dail_execution_readback')); end if;

  update integration_control.penta_assignment_contracts_v1 set
    state=case when independent_certification_required then 'AWAITING_CERTIFICATION' else 'CERTIFIED' end,
    updated_at=now()
  where assignment_id=a.assignment_id;
  v_docs:=penta_docs.project_assignment_v1(a.assignment_id);
  return jsonb_build_object(
    'assignment_id',a.assignment_id,
    'state',case when a.independent_certification_required then 'AWAITING_CERTIFICATION' else 'CERTIFIED' end,
    'evidence',v_evidence,'decision',v_decision,'execution',v_execution,'pentadocs',v_docs
  );
end $$;

create or replace function integration_control.penta_assignment_record_certification_v1(
  p_assignment_id uuid,
  p_certification_id text,
  p_disposition text,
  p_certifier_ref text,
  p_certification_event_id uuid,
  p_certification_event_hash text,
  p_evidence jsonb default '{}'::jsonb
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
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id for update;
  if not found then raise exception 'assignment_not_found'; end if;
  if a.owner_pentas ? p_certifier_ref then raise exception 'originator_cannot_self_certify'; end if;
  if lower(p_certifier_ref) not in ('pentacertify','pentacertifier','ct.penta.certifier') then raise exception 'independent_certifier_required'; end if;
  if p_disposition not in ('CERTIFIED','HOLD','INVALIDATED') then raise exception 'certification_disposition_invalid'; end if;
  if not exists(select 1 from chlom_runtime.dail_events d where d.event_id=p_certification_event_id and d.event_hash=p_certification_event_hash) then raise exception 'certification_dail_readback_required'; end if;
  v_state:=case p_disposition when 'CERTIFIED' then 'CERTIFIED' when 'INVALIDATED' then 'INVALIDATED' else 'HOLD' end;
  update integration_control.penta_assignment_institutionalization_v1 set
    certification_id=p_certification_id,certification_state=v_state,certifier_ref=p_certifier_ref,
    certification_event_id=p_certification_event_id,certification_event_hash=p_certification_event_hash,updated_at=now()
  where assignment_id=a.assignment_id;
  update integration_control.penta_assignment_contracts_v1 set
    state=case when p_disposition='CERTIFIED' then 'CERTIFIED' else 'HOLD' end,updated_at=now()
  where assignment_id=a.assignment_id;
  v_payload:=jsonb_build_object(
    'assignment_id',a.assignment_id,'assignment_key',a.assignment_key,
    'certification_id',p_certification_id,'disposition',p_disposition,'certifier_ref',p_certifier_ref,
    'certification_event_id',p_certification_event_id,'evidence',coalesce(p_evidence,'{}'::jsonb),
    'originator_certifier_separation',true,'authority_expansion',false,'recorded_at',clock_timestamp()
  );
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  v_event:=chlom_runtime.append_dail_event(
    'penta.assignment.certification.'||lower(p_disposition),'penta_assignment_certification',a.assignment_id::text,
    v_payload||jsonb_build_object('evidence_sha256',v_sha),p_certifier_ref,null,'PentaCertify','1.0.0',
    'ctcorr:penta-assignment:'||a.assignment_id::text,p_certification_event_id::text,
    'ct.penta.assignment-fulfillment.v1',null,'internal'
  );
  return jsonb_build_object('assignment_id',a.assignment_id,'state',v_state,'evidence_sha256',v_sha,'dail',v_event);
end $$;

create or replace function integration_control.penta_assignment_project_os_v1(p_assignment_id uuid)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','extensions','chlom_runtime'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  i integration_control.penta_assignment_institutionalization_v1%rowtype;
  v_payload jsonb;
  v_sha text;
  v_event jsonb;
  v_readback boolean;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id;
  if not found then raise exception 'assignment_not_found'; end if;
  select * into i from integration_control.penta_assignment_institutionalization_v1 where assignment_id=p_assignment_id;
  if not found then raise exception 'institutionalization_row_not_found'; end if;
  if i.evidence_event_id is null or i.decision_event_id is null or i.execution_event_id is null then raise exception 'three_dail_required'; end if;
  if i.pentadocs_state<>'READBACK_PASS' or i.provider_projection_state<>'READBACK_PASS' then raise exception 'projection_readback_required'; end if;
  if i.certification_state not in ('CERTIFIED','NOT_REQUIRED','ACTIVE') then raise exception 'certification_required'; end if;

  insert into integration_control.penta_assignment_os_projection_v1(
    assignment_id,assignment_key,stable_identity,exact_artifact_ref,exact_artifact_sha256,exact_head_sha,
    risk_class,lifecycle_state,owner_pentas,certification_id,certification_state,certification_event_id,
    evidence_event_id,decision_event_id,execution_event_id,drive_refs,pentadocs_ref,
    rollback_state,production_status,projection_state,updated_at
  ) values (
    a.assignment_id,a.assignment_key,'did:ct:penta-assignment:'||a.assignment_id::text,
    a.exact_artifact_ref,a.exact_artifact_sha256,a.exact_head_sha,a.risk_class,a.state,a.owner_pentas,
    i.certification_id,i.certification_state,i.certification_event_id,
    i.evidence_event_id,i.decision_event_id,i.execution_event_id,
    jsonb_build_object(
      'folder_id',i.drive_folder_id,'human_doc_id',i.drive_human_doc_id,
      'hybrid_doc_id',i.drive_hybrid_doc_id,'machine_sheet_id',i.drive_machine_sheet_id
    ),i.pentadocs_ref,'PRESERVED','NOT_CLAIMED','PROJECTED',now()
  ) on conflict(assignment_id) do update set
    exact_artifact_ref=excluded.exact_artifact_ref,exact_artifact_sha256=excluded.exact_artifact_sha256,
    exact_head_sha=excluded.exact_head_sha,lifecycle_state=excluded.lifecycle_state,
    certification_id=excluded.certification_id,certification_state=excluded.certification_state,
    certification_event_id=excluded.certification_event_id,evidence_event_id=excluded.evidence_event_id,
    decision_event_id=excluded.decision_event_id,execution_event_id=excluded.execution_event_id,
    drive_refs=excluded.drive_refs,pentadocs_ref=excluded.pentadocs_ref,
    projection_state='PROJECTED',updated_at=now();

  v_payload:=jsonb_build_object(
    'assignment_id',a.assignment_id,'assignment_key',a.assignment_key,
    'stable_identity','did:ct:penta-assignment:'||a.assignment_id::text,
    'exact_artifact_ref',a.exact_artifact_ref,'exact_artifact_sha256',a.exact_artifact_sha256,
    'exact_head_sha',a.exact_head_sha,'risk_class',a.risk_class,
    'certification_id',i.certification_id,'certification_state',i.certification_state,
    'three_dail',jsonb_build_object('evidence',i.evidence_event_id,'decision',i.decision_event_id,'execution',i.execution_event_id),
    'pentadocs_ref',i.pentadocs_ref,
    'drive_refs',jsonb_build_object('folder_id',i.drive_folder_id,'human_doc_id',i.drive_human_doc_id,'hybrid_doc_id',i.drive_hybrid_doc_id,'machine_sheet_id',i.drive_machine_sheet_id),
    'rollback_state','PRESERVED','production_status','NOT_CLAIMED',
    'authority_expansion',false,'projected_at',clock_timestamp()
  );
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  v_event:=chlom_runtime.append_dail_event(
    'crownthrive_os.penta_assignment.projected.v1','os_assignment_projection',a.assignment_id::text,
    v_payload||jsonb_build_object('evidence_sha256',v_sha),
    'CrownThriveOS/PentaDocs/PentaCertify',null,'CrownThriveOS','1.0.0',
    'ctcorr:penta-assignment:'||a.assignment_id::text,coalesce(i.certification_event_id,i.execution_event_id)::text,
    'ct.penta.institutionalization.v1',null,'internal'
  );
  update integration_control.penta_assignment_os_projection_v1 set
    projection_event_id=(v_event->>'event_id')::uuid,projection_event_hash=v_event->>'event_hash',updated_at=now()
  where assignment_id=a.assignment_id;
  v_readback:=exists(
    select 1 from integration_control.penta_assignment_os_projection_v1 o
    join chlom_runtime.dail_events d on d.event_id=o.projection_event_id and d.event_hash=o.projection_event_hash
    where o.assignment_id=a.assignment_id and o.exact_artifact_ref=a.exact_artifact_ref
      and o.certification_state=i.certification_state and o.projection_state='PROJECTED'
  );
  update integration_control.penta_assignment_institutionalization_v1 set
    os_projection_state=case when v_readback then 'READBACK_PASS' else 'HOLD' end,
    os_projection_event_id=(v_event->>'event_id')::uuid,updated_at=now()
  where assignment_id=a.assignment_id;
  return jsonb_build_object('assignment_id',a.assignment_id,'state',case when v_readback then 'READBACK_PASS' else 'HOLD' end,'evidence_sha256',v_sha,'dail',v_event);
end $$;

create or replace function integration_control.penta_assignment_refresh_chain_gate_v1(p_assignment_id uuid)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','chlom_runtime'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  i integration_control.penta_assignment_institutionalization_v1%rowtype;
  v_pre jsonb;
  v_final jsonb;
  v_predicates boolean;
  v_activation jsonb;
  v_activation_ok boolean:=false;
  v_terminal text:='HOLD';
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id for update;
  if not found then raise exception 'assignment_not_found'; end if;
  select * into i from integration_control.penta_assignment_institutionalization_v1 where assignment_id=p_assignment_id for update;
  if not found then raise exception 'institutionalization_row_not_found'; end if;

  v_predicates:=i.evidence_readback and i.decision_readback and i.execution_readback
    and i.pentadocs_state='READBACK_PASS'
    and i.provider_projection_state='READBACK_PASS'
    and i.os_projection_state='READBACK_PASS'
    and i.certification_state in ('CERTIFIED','NOT_REQUIRED','ACTIVE');
  v_pre:=chlom_runtime.verify_dail_chain_v3();

  if v_predicates and coalesce((v_pre->>'ok')::boolean,false) and coalesce((v_pre->>'failure_count')::integer,1)=0 then
    if i.activation_event_id is null then
      v_activation:=chlom_runtime.append_dail_event(
        'penta.assignment.activated.v1','penta_assignment_activation',a.assignment_id::text,
        jsonb_build_object(
          'assignment_key',a.assignment_key,'exact_artifact_ref',a.exact_artifact_ref,
          'exact_artifact_sha256',a.exact_artifact_sha256,'exact_head_sha',a.exact_head_sha,
          'certification_id',i.certification_id,'certification_state',i.certification_state,
          'os_projection_event_id',i.os_projection_event_id,
          'three_dail',jsonb_build_object('evidence',i.evidence_event_id,'decision',i.decision_event_id,'execution',i.execution_event_id),
          'pentadocs_ref',i.pentadocs_ref,
          'drive_readback',jsonb_build_object('human',i.drive_human_readback,'hybrid',i.drive_hybrid_readback,'machine',i.drive_machine_readback),
          'pre_activation_chain',v_pre,'authority_expansion',false,'activated_at',clock_timestamp()
        ),
        'PentaCertify/CrownThriveOS/DAIL',null,'PentaCertify','1.0.0',
        'ctcorr:penta-assignment:'||a.assignment_id::text,coalesce(i.certification_event_id,i.os_projection_event_id)::text,
        'ct.penta.assignment-fulfillment.v1',null,'internal'
      );
      v_activation_ok:=exists(select 1 from chlom_runtime.dail_events d where d.event_id=(v_activation->>'event_id')::uuid and d.event_hash=v_activation->>'event_hash');
      update integration_control.penta_assignment_institutionalization_v1 set
        activation_event_id=(v_activation->>'event_id')::uuid,
        activation_event_hash=v_activation->>'event_hash',activation_readback=v_activation_ok,updated_at=now()
      where assignment_id=a.assignment_id;
    else
      v_activation:=jsonb_build_object('event_id',i.activation_event_id,'event_hash',i.activation_event_hash);
      v_activation_ok:=i.activation_readback and exists(select 1 from chlom_runtime.dail_events d where d.event_id=i.activation_event_id and d.event_hash=i.activation_event_hash);
    end if;
    v_final:=chlom_runtime.verify_dail_chain_v3();
    if v_activation_ok and coalesce((v_final->>'ok')::boolean,false) and coalesce((v_final->>'failure_count')::integer,1)=0 then
      v_terminal:='PASS';
    end if;
  else
    v_final:=v_pre;
  end if;

  update integration_control.penta_assignment_institutionalization_v1 set
    chain_state=case when coalesce((v_final->>'ok')::boolean,false) and coalesce((v_final->>'failure_count')::integer,1)=0 then 'PASS' else 'FAIL' end,
    chain_checked_at=now(),chain_head_hash=v_final->>'head_hash',
    chain_checked_events=coalesce((v_final->>'checked_events')::bigint,0),
    terminal_gate_state=v_terminal,
    certification_state=case when v_terminal='PASS' and certification_state='CERTIFIED' then 'ACTIVE' else certification_state end,
    updated_at=now()
  where assignment_id=a.assignment_id;
  if v_terminal='PASS' then
    update integration_control.penta_assignment_contracts_v1 set state='COMPLETED',completed_at=coalesce(completed_at,now()),updated_at=now() where assignment_id=a.assignment_id;
    update integration_control.penta_assignment_os_projection_v1 set lifecycle_state='COMPLETED',certification_state=case when certification_state='CERTIFIED' then 'ACTIVE' else certification_state end,updated_at=now() where assignment_id=a.assignment_id;
    perform penta_docs.project_assignment_v1(a.assignment_id);
  end if;
  return jsonb_build_object('assignment_id',a.assignment_id,'terminal_gate_state',v_terminal,'activation',v_activation,'chain',v_final,'predicates_complete',v_predicates);
end $$;

create or replace function integration_control.penta_assignment_link_pr_v1(
  p_assignment_id uuid,p_repo text,p_pr_number bigint,p_exact_head_sha text,p_terminal_action text,p_classification text
) returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_id uuid;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if p_exact_head_sha !~ '^[0-9a-f]{40}$' then raise exception 'head_sha_invalid'; end if;
  if p_terminal_action not in ('MERGE','CLOSE','NONE') then raise exception 'terminal_action_invalid'; end if;
  update integration_control.penta_assignment_contracts_v1 set
    source_repo=p_repo,source_pr_number=p_pr_number,exact_head_sha=p_exact_head_sha,updated_at=now()
  where assignment_id=p_assignment_id;
  if not found then raise exception 'assignment_not_found'; end if;
  update integration_control.penta_assignment_pr_links_v1 set state='SUPERSEDED',updated_at=now()
  where assignment_id=p_assignment_id and state not in ('TERMINALIZED','SUPERSEDED') and exact_head_sha<>p_exact_head_sha;
  insert into integration_control.penta_assignment_pr_links_v1(
    assignment_id,repo,pr_number,exact_head_sha,terminal_action,classification
  ) values (p_assignment_id,p_repo,p_pr_number,p_exact_head_sha,p_terminal_action,p_classification)
  on conflict(repo,pr_number,exact_head_sha,terminal_action) do update set
    assignment_id=excluded.assignment_id,classification=excluded.classification,updated_at=now()
  returning link_id into v_id;
  return jsonb_build_object('link_id',v_id,'assignment_id',p_assignment_id,'state','LINKED','repo',p_repo,'pr_number',p_pr_number,'head_sha',p_exact_head_sha,'action',p_terminal_action);
end $$;

create or replace function public.penta_assignment_pr_terminal_gate_v1(
  p_repo text,p_pr_number bigint,p_head_sha text,p_action text
) returns jsonb
language sql stable security definer
set search_path to 'pg_catalog','integration_control','public'
as $$
select coalesce((
  select jsonb_build_object(
    'eligible',
      a.state='COMPLETED'
      and i.terminal_gate_state='PASS'
      and i.chain_state='PASS'
      and i.chain_checked_at>=now()-interval '30 minutes'
      and i.evidence_readback and i.decision_readback and i.execution_readback and i.activation_readback
      and i.pentadocs_state='READBACK_PASS'
      and i.provider_projection_state='READBACK_PASS'
      and i.os_projection_state='READBACK_PASS'
      and i.certification_state in ('ACTIVE','NOT_REQUIRED'),
    'state',case when
      a.state='COMPLETED' and i.terminal_gate_state='PASS' and i.chain_state='PASS'
      and i.chain_checked_at>=now()-interval '30 minutes'
      and i.evidence_readback and i.decision_readback and i.execution_readback and i.activation_readback
      and i.pentadocs_state='READBACK_PASS' and i.provider_projection_state='READBACK_PASS'
      and i.os_projection_state='READBACK_PASS' and i.certification_state in ('ACTIVE','NOT_REQUIRED')
      then 'PASS' else 'HOLD' end,
    'assignment_id',a.assignment_id,'assignment_key',a.assignment_key,'assignment_state',a.state,
    'repo',l.repo,'pr_number',l.pr_number,'exact_head_sha',l.exact_head_sha,'terminal_action',l.terminal_action,
    'certification_id',i.certification_id,'certification_state',i.certification_state,
    'evidence_event_id',i.evidence_event_id,'decision_event_id',i.decision_event_id,
    'execution_event_id',i.execution_event_id,'activation_event_id',i.activation_event_id,
    'os_projection_event_id',i.os_projection_event_id,'pentadocs_ref',i.pentadocs_ref,
    'drive_refs',jsonb_build_object('folder_id',i.drive_folder_id,'human_doc_id',i.drive_human_doc_id,'hybrid_doc_id',i.drive_hybrid_doc_id,'machine_sheet_id',i.drive_machine_sheet_id),
    'chain_state',i.chain_state,'chain_checked_at',i.chain_checked_at,'chain_head_hash',i.chain_head_hash,
    'terminal_gate_state',i.terminal_gate_state,'authority_expansion',false
  )
  from integration_control.penta_assignment_pr_links_v1 l
  join integration_control.penta_assignment_contracts_v1 a using(assignment_id)
  join integration_control.penta_assignment_institutionalization_v1 i using(assignment_id)
  where l.repo=p_repo and l.pr_number=p_pr_number and l.exact_head_sha=p_head_sha
    and l.terminal_action=p_action and l.state<>'SUPERSEDED'
  order by l.updated_at desc limit 1
),jsonb_build_object('eligible',false,'state','HOLD','reason','institutional_assignment_receipt_not_found','repo',p_repo,'pr_number',p_pr_number,'head_sha',p_head_sha,'action',p_action));
$$;

create or replace function integration_control.penta_assignment_terminal_dispatch_v1(p_assignment_id uuid)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','penta_pr','public'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  l integration_control.penta_assignment_pr_links_v1%rowtype;
  v_gate jsonb;
  v_request bigint;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into l from integration_control.penta_assignment_pr_links_v1
  where assignment_id=p_assignment_id and state not in ('TERMINALIZED','SUPERSEDED')
  order by updated_at desc limit 1 for update;
  if not found or l.terminal_action='NONE' then return jsonb_build_object('assignment_id',p_assignment_id,'state','NO_TERMINAL_ACTION'); end if;
  v_gate:=public.penta_assignment_pr_terminal_gate_v1(l.repo,l.pr_number,l.exact_head_sha,l.terminal_action);
  if not coalesce((v_gate->>'eligible')::boolean,false) then
    update integration_control.penta_assignment_pr_links_v1 set state='GATE_HOLD',updated_at=now() where link_id=l.link_id;
    return jsonb_build_object('assignment_id',p_assignment_id,'state','GATE_HOLD','gate',v_gate);
  end if;
  v_request:=penta_pr.invoke_terminal_provider_v3(
    case when l.terminal_action='MERGE' then 'merge_exact' else 'close_exact' end,
    jsonb_build_object(
      'repo',l.repo,'pr_number',l.pr_number,'expected_head_sha',l.exact_head_sha,
      'classification',case when l.terminal_action='CLOSE' then 'TASK_COMPLETED' else l.classification end,
      'reason','task completed and institutionally certified',
      'evidence',v_gate||jsonb_build_object('exact_head_certified',true,'institutional_gate_pass',true)
    )
  );
  update integration_control.penta_assignment_pr_links_v1 set
    state='DISPATCHED',terminal_request_id=v_request,updated_at=now()
  where link_id=l.link_id;
  return jsonb_build_object('assignment_id',p_assignment_id,'state','DISPATCHED','request_id',v_request,'gate',v_gate);
end $$;

create or replace function integration_control.penta_assignment_reconcile_terminal_v1(p_assignment_id uuid)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','penta_pr','extensions','chlom_runtime'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  l integration_control.penta_assignment_pr_links_v1%rowtype;
  p penta_pr.lifecycle%rowtype;
  v_payload jsonb;
  v_sha text;
  v_event jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into l from integration_control.penta_assignment_pr_links_v1
  where assignment_id=p_assignment_id and state='DISPATCHED' order by updated_at desc limit 1 for update;
  if not found then return jsonb_build_object('assignment_id',p_assignment_id,'state','NO_DISPATCHED_TERMINAL'); end if;
  select * into p from penta_pr.lifecycle where repo=l.repo and pr_number=l.pr_number;
  if not found or p.head_sha is distinct from l.exact_head_sha or p.terminal_state not in ('MERGED','CLOSED') then
    return jsonb_build_object('assignment_id',p_assignment_id,'state','PENDING_PROVIDER_READBACK','provider_head',p.head_sha,'provider_terminal_state',p.terminal_state);
  end if;
  update integration_control.penta_assignment_pr_links_v1 set
    state='TERMINALIZED',provider_state=p.terminal_state,provider_merged=p.terminal_state='MERGED',
    provider_readback=jsonb_build_object('head_sha',p.head_sha,'terminal_state',p.terminal_state,'terminal_at',p.terminal_at,'metadata',p.metadata),
    terminalized_at=now(),updated_at=now()
  where link_id=l.link_id;
  update integration_control.penta_assignment_contracts_v1 set terminalized_at=now(),updated_at=now() where assignment_id=p_assignment_id;
  update integration_control.penta_assignment_institutionalization_v1 set terminal_gate_state='TERMINALIZED',updated_at=now() where assignment_id=p_assignment_id;
  v_payload:=jsonb_build_object('assignment_id',p_assignment_id,'repo',l.repo,'pr_number',l.pr_number,'head_sha',p.head_sha,'terminal_state',p.terminal_state,'terminal_at',p.terminal_at,'provider_readback',p.metadata,'authority_expansion',false,'observed_at',clock_timestamp());
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  v_event:=chlom_runtime.append_dail_event(
    'penta.assignment.pr_terminalized.v1','penta_assignment_pr_terminal',p_assignment_id::text,
    v_payload||jsonb_build_object('evidence_sha256',v_sha),
    'PentaPR/PentaMerge/PentaCloser/PentaDocs',null,'PentaPR','1.0.0',
    'ctcorr:penta-assignment:'||p_assignment_id::text,null,'ct.penta.pr-terminalization.v4',null,'internal'
  );
  perform penta_docs.project_assignment_v1(p_assignment_id);
  return jsonb_build_object('assignment_id',p_assignment_id,'state','TERMINALIZED','evidence_sha256',v_sha,'dail',v_event);
end $$;

create or replace function integration_control.penta_assignment_fulfillment_tick_v1(p_limit integer default 25)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','public'
as $$
declare
  a record;
  v_routed integer:=0;
  v_institutionalized integer:=0;
  v_os_projected integer:=0;
  v_activated integer:=0;
  v_dispatched integer:=0;
  v_terminalized integer:=0;
  v_result jsonb;
begin
  if session_user not in ('postgres','supabase_admin')
     and coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'')<>'service_role'
  then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta:assignment-fulfillment:v1',0)) then return jsonb_build_object('state','DEFERRED_CONTENTION'); end if;
  for a in
    select assignment_id,state from integration_control.penta_assignment_contracts_v1
    where state not in ('FAILED','SUPERSEDED','RETIRED')
    order by case priority when 'P0' then 0 when 'P1' then 1 when 'P2' then 2 else 3 end,created_at
    for update skip locked limit greatest(1,least(coalesce(p_limit,25),100))
  loop
    if a.state='DISCOVERED' then
      v_result:=integration_control.penta_assignment_route_v1(a.assignment_id); v_routed:=v_routed+1;
    elsif a.state in ('ROUTED','IN_PROGRESS','AWAITING_PROJECTION') then
      v_result:=integration_control.penta_assignment_institutionalize_v1(a.assignment_id);
      if v_result->>'state' in ('AWAITING_CERTIFICATION','CERTIFIED') then v_institutionalized:=v_institutionalized+1; end if;
    elsif a.state='CERTIFIED' then
      v_result:=integration_control.penta_assignment_project_os_v1(a.assignment_id);
      if v_result->>'state'='READBACK_PASS' then v_os_projected:=v_os_projected+1; end if;
      v_result:=integration_control.penta_assignment_refresh_chain_gate_v1(a.assignment_id);
      if v_result->>'terminal_gate_state'='PASS' then
        v_activated:=v_activated+1;
        v_result:=integration_control.penta_assignment_terminal_dispatch_v1(a.assignment_id);
        if v_result->>'state'='DISPATCHED' then v_dispatched:=v_dispatched+1; end if;
      end if;
    elsif a.state='COMPLETED' then
      if exists(select 1 from integration_control.penta_assignment_pr_links_v1 l where l.assignment_id=a.assignment_id and l.state in ('LINKED','GATE_HOLD')) then
        v_result:=integration_control.penta_assignment_terminal_dispatch_v1(a.assignment_id);
        if v_result->>'state'='DISPATCHED' then v_dispatched:=v_dispatched+1; end if;
      elsif exists(select 1 from integration_control.penta_assignment_pr_links_v1 l where l.assignment_id=a.assignment_id and l.state='DISPATCHED') then
        v_result:=integration_control.penta_assignment_reconcile_terminal_v1(a.assignment_id);
        if v_result->>'state'='TERMINALIZED' then v_terminalized:=v_terminalized+1; end if;
      end if;
    end if;
  end loop;
  return jsonb_build_object(
    'state','COMPLETE','routed',v_routed,'institutionalized',v_institutionalized,
    'os_projected',v_os_projected,'activated',v_activated,'terminal_dispatched',v_dispatched,
    'terminalized',v_terminalized,'observed_at',clock_timestamp(),'authority_expansion',false
  );
end $$;

create or replace function integration_control.penta_assignment_status_v1(p_assignment_id uuid default null)
returns jsonb
language sql stable security definer
set search_path to 'pg_catalog','integration_control','penta_docs'
as $$
select jsonb_build_object(
 'contract','ct.penta.assignment-fulfillment.v1',
 'policy',(select to_jsonb(p) from integration_control.penta_assignment_policy_v1 p where policy_key='ct.penta.change-institutionalization.rule.v1'),
 'counts',(select coalesce(jsonb_object_agg(state,n),'{}'::jsonb) from (select state,count(*) n from integration_control.penta_assignment_contracts_v1 where p_assignment_id is null or assignment_id=p_assignment_id group by state)s),
 'assignments',(
   select coalesce(jsonb_agg(jsonb_build_object(
     'assignment_id',a.assignment_id,'assignment_key',a.assignment_key,'title',a.title,
     'family_key',a.owning_family_key,'owner_pentas',a.owner_pentas,'risk_class',a.risk_class,
     'state',a.state,'exact_artifact_ref',a.exact_artifact_ref,'exact_head_sha',a.exact_head_sha,
     'institutionalization',to_jsonb(i),
     'os_projection',(select to_jsonb(o) from integration_control.penta_assignment_os_projection_v1 o where o.assignment_id=a.assignment_id),
     'pr_links',(select coalesce(jsonb_agg(to_jsonb(l) order by l.created_at),'[]'::jsonb) from integration_control.penta_assignment_pr_links_v1 l where l.assignment_id=a.assignment_id)
   ) order by a.created_at),'[]'::jsonb)
   from integration_control.penta_assignment_contracts_v1 a
   left join integration_control.penta_assignment_institutionalization_v1 i using(assignment_id)
   where p_assignment_id is null or a.assignment_id=p_assignment_id
 ),
 'family_obligations',(select count(*) from integration_control.penta_family_obligation_contracts_v1 where state='ACTIVE'),
 'history_preserved',true,'d3_human_reserved',true,'authority_expansion',false,'generated_at',clock_timestamp()
);
$$;

create or replace function integration_control.penta_assignment_regression_v1()
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','public'
as $$
declare
  v_results jsonb:='[]'::jsonb;
  v_failed integer:=0;
begin
  v_results:=v_results||jsonb_build_array(jsonb_build_object('check','policy_active','passed',exists(select 1 from integration_control.penta_assignment_policy_v1 where policy_key='ct.penta.change-institutionalization.rule.v1' and state='ACTIVE')));
  v_results:=v_results||jsonb_build_array(jsonb_build_object('check','fifteen_family_obligations','passed',(select count(*)=15 from integration_control.penta_family_obligation_contracts_v1 where state='ACTIVE')));
  v_results:=v_results||jsonb_build_array(jsonb_build_object('check','terminal_gate_requires_assignment','passed',not coalesce((public.penta_assignment_pr_terminal_gate_v1('crownthrive1/CrownThrive-OS',0,repeat('0',40),'CLOSE')->>'eligible')::boolean,true)));
  v_results:=v_results||jsonb_build_array(jsonb_build_object('check','originator_self_certification_forbidden','passed',position('originator_cannot_self_certify' in pg_get_functiondef('integration_control.penta_assignment_record_certification_v1(uuid,text,text,text,uuid,text,jsonb)'::regprocedure))>0));
  v_results:=v_results||jsonb_build_array(jsonb_build_object('check','three_dail_lanes_required','passed',(select required_dail_lanes=array['EVIDENCE','DECISION','EXECUTION']::text[] from integration_control.penta_assignment_policy_v1 where policy_key='ct.penta.change-institutionalization.rule.v1')));
  v_results:=v_results||jsonb_build_array(jsonb_build_object('check','drive_three_way_required','passed',(select required_projections @> array['DRIVE_HUMAN','DRIVE_HYBRID','DRIVE_MACHINE_SHEET']::text[] from integration_control.penta_assignment_policy_v1 where policy_key='ct.penta.change-institutionalization.rule.v1')));
  v_results:=v_results||jsonb_build_array(jsonb_build_object('check','public_mutation_execute_revoked','passed',
    not has_function_privilege('anon','integration_control.penta_assignment_create_v1(text,text,text,text,text,text,text,jsonb,text,text,text,text,text,bigint,text,jsonb,boolean,text,jsonb)','EXECUTE')
    and not has_function_privilege('authenticated','integration_control.penta_assignment_create_v1(text,text,text,text,text,text,text,jsonb,text,text,text,text,text,bigint,text,jsonb,boolean,text,jsonb)','EXECUTE')
  ));
  v_results:=v_results||jsonb_build_array(jsonb_build_object('check','chain_gate_requires_os_projection','passed',position("i.os_projection_state='READBACK_PASS'" in pg_get_functiondef('integration_control.penta_assignment_refresh_chain_gate_v1(uuid)'::regprocedure))>0));
  select count(*) into v_failed from jsonb_array_elements(v_results) x where not coalesce((x->>'passed')::boolean,false);
  return jsonb_build_object('contract','ct.penta.assignment-fulfillment.v1','checks',jsonb_array_length(v_results),'passed',jsonb_array_length(v_results)-v_failed,'failed',v_failed,'all_passed',v_failed=0,'results',v_results,'observed_at',clock_timestamp());
end $$;

create or replace view public.penta_assignment_institutionalization_status_v1 as
select a.assignment_id,a.assignment_key,a.title,a.owning_family_key,a.owner_pentas,a.risk_class,a.state,
 a.exact_artifact_ref,a.exact_artifact_sha256,a.exact_head_sha,
 i.pentadocs_state,i.provider_projection_state,i.certification_id,i.certification_state,
 i.os_projection_state,i.chain_state,i.chain_checked_at,i.terminal_gate_state,
 i.institutionalized_at,a.completed_at,a.terminalized_at,a.updated_at
from integration_control.penta_assignment_contracts_v1 a
join integration_control.penta_assignment_institutionalization_v1 i using(assignment_id);
