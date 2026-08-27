-- PentaBuild provider contract quality v1
-- PentaBuild software packages must contain a real governed provider contract,
-- not only metadata and CI. Secret values are never generated or embedded.

create table if not exists integration_control.penta_build_quality_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  task_id uuid references integration_control.penta_certify_tasks_v3(task_id) on delete set null,
  build_request_id uuid references public.ct_factory_build_requests(id) on delete set null,
  checked_at timestamptz not null default now(),
  result_state text not null check(result_state in ('complete_contract','scaffold_only','not_applicable')),
  required_kinds jsonb not null default '[]'::jsonb,
  observed_kinds jsonb not null default '[]'::jsonb,
  evidence jsonb not null default '{}'::jsonb
);
alter table integration_control.penta_build_quality_receipts_v1 enable row level security;
revoke all on integration_control.penta_build_quality_receipts_v1 from anon,authenticated;

create or replace function public.penta_build_enrich_provider_request_v1()
returns trigger
language plpgsql
security definer
set search_path='pg_catalog','public'
as $$
declare v_task text; v_provider text; v_surface text; v_service text;
begin
  if new.source_type <> 'penta_certify' or coalesce(new.requirements->>'work_type','') <> 'provider_certification_software' then return new; end if;
  if new.requirements ? 'blueprint' then return new; end if;
  v_task:=coalesce(new.requirements->>'task_kind','provider_gap');
  v_provider:=coalesce(new.requirements->>'provider_system','provider');
  v_surface:=coalesce(new.requirements->>'surface_id',new.source_ref,'surface');
  v_service:=left('PentaBuild '||v_provider||' '||v_task||' Contract',120);
  new.requirements:=new.requirements || jsonb_build_object('penta_build_output_contract','ct.penta.build.provider-assets.v1','blueprint',jsonb_build_object(
    'service_name',v_service,'version','1.0.0',
    'capabilities',jsonb_build_array('provider_adapter_contract',v_task,'readback_contract','rollback_or_compensation_contract','evidence_manifest','fail_closed'),
    'endpoints',jsonb_build_array(
      jsonb_build_object('path','/health','method','get','operation_id','health','summary','PentaBuild adapter-contract health'),
      jsonb_build_object('path','/status','method','get','operation_id','status','summary','Read adapter contract status')
    ),
    'data_entities',jsonb_build_array(jsonb_build_object('schema','ct_generated','table','penta_provider_contract_receipts','columns',jsonb_build_array(
      jsonb_build_object('name','id','type','uuid','default','gen_random_uuid()'),jsonb_build_object('name','surface_id','type','text'),jsonb_build_object('name','state','type','text'),jsonb_build_object('name','evidence','type','jsonb'),jsonb_build_object('name','created_at','type','timestamptz')))),
    'mcp_tools',jsonb_build_array(jsonb_build_object('name','adapter_status','description','Read bounded adapter status'),jsonb_build_object('name','adapter_evidence','description','Read non-secret certification evidence')),
    'docs',jsonb_build_array(jsonb_build_object('slug','provider-contract','title',v_provider||' Provider Contract','description','PentaBuild bounded provider-gap contract','body','Surface: '||v_surface||'. Task: '||v_task||'. Software contract only; provider authority remains fail-closed until PentaCertify records live provider evidence.')),
    'environment',jsonb_build_array(jsonb_build_object('name','PROVIDER_API_BASE','required',false,'secret',false,'description','Provider API base when required'),jsonb_build_object('name','CREDENTIAL_REFERENCE_ID','required',false,'secret',false,'description','Reference to PentaCredentials custody record; never a secret value')),
    'events',jsonb_build_array(jsonb_build_object('name','provider_certification_updated','properties',jsonb_build_object('surface_id',jsonb_build_object('type','string'),'state',jsonb_build_object('type','string'),'evidence_ref',jsonb_build_object('type','string')),'required',jsonb_build_array('surface_id','state'))),
    'policy',jsonb_build_object('policy_id','ct.penta.provider-gap.v1','risk_class',coalesce(new.governance_class,'D1'),'authority','PentaCertify / CHLOM','fail_closed',true,'required_evidence',jsonb_build_array('provider_read','bounded_write_canary','read_after_write','rollback_or_compensation','sha256'),'rules',jsonb_build_array('PentaBuild builds software but does not self-certify provider authority','No secret values in generated artifacts','No provider mutation before certification','D3 remains human-governed'))
  ));
  return new;
end $$;

drop trigger if exists trg_penta_build_enrich_provider_request_v1 on public.ct_factory_build_requests;
create trigger trg_penta_build_enrich_provider_request_v1 before insert or update of requirements on public.ct_factory_build_requests for each row execute function public.penta_build_enrich_provider_request_v1();

create or replace function integration_control.penta_build_quality_sweep_v1()
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','integration_control','public'
as $$
declare r record; v_kinds jsonb; v_ok boolean; v_complete int:=0; v_scaffold int:=0; v_requeued int:=0;
begin
  for r in select t.task_id,t.task_kind,t.build_request_id from integration_control.penta_certify_tasks_v3 t join public.ct_factory_build_requests b on b.id=t.build_request_id where t.task_kind in ('build_adapter','build_write_canary_contract','build_readback_contract','build_rollback_contract') and b.status='implemented' and t.state='completed'
  loop
    select coalesce(jsonb_agg(distinct a.metadata->>'kind') filter(where a.artifact_type='source_file'),'[]'::jsonb) into v_kinds from public.ct_factory_build_runs br left join public.ct_factory_artifacts a on a.build_run_id=br.id where br.build_request_id=r.build_request_id and br.status='implemented';
    v_ok:=v_kinds ? 'policy_manifest' and v_kinds ? 'env_contract' and v_kinds ? 'event_contract' and v_kinds ? 'github_workflow' and v_kinds ? 'openapi_spec' and v_kinds ? 'edge_api';
    insert into integration_control.penta_build_quality_receipts_v1(task_id,build_request_id,result_state,required_kinds,observed_kinds,evidence) values(r.task_id,r.build_request_id,case when v_ok then 'complete_contract' else 'scaffold_only' end,jsonb_build_array('policy_manifest','env_contract','event_contract','github_workflow','openapi_spec','edge_api'),v_kinds,jsonb_build_object('task_kind',r.task_kind,'software_priority',true,'provider_certification_granted',false));
    if v_ok then v_complete:=v_complete+1; else
      update public.ct_factory_build_requests set status='queued',requirements=requirements||jsonb_build_object('penta_rebuild_reason','scaffold_only','penta_rebuild_at',now()),updated_at=now() where id=r.build_request_id;
      update integration_control.penta_certify_tasks_v3 set state='queued',build_request_id=null,completed_at=null,available_at=now(),last_error='penta_build_scaffold_only_rebuild_required',updated_at=now() where task_id=r.task_id;
      v_scaffold:=v_scaffold+1; v_requeued:=v_requeued+1;
    end if;
  end loop;
  return jsonb_build_object('service','ct.penta.build.quality.v1','complete_contract',v_complete,'scaffold_only',v_scaffold,'requeued',v_requeued,'at',now());
end $$;
revoke all on function integration_control.penta_build_quality_sweep_v1() from public,anon,authenticated;
grant execute on function integration_control.penta_build_quality_sweep_v1() to service_role;

select integration_control.penta_build_quality_sweep_v1();
