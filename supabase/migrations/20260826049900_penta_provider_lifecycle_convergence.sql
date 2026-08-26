-- Phase 3 provider lifecycle convergence for PentaSELF.
-- Replaces the superseded/conflicted provider-lifecycle source branch with a
-- replayable current-main migration. No secret values or provider authority are manufactured.

insert into public.penta_system_registry(system_key,canonical_name,category,purpose,authority_boundary,risk_ceiling,maturity,version,public_exposure,runtime_ref,metadata,last_verified_at,updated_at)
values
('penta.build','PentaBuild','software_asset_adapter_plugin_build','Build and maintain bounded software assets, provider adapters, plugins, probes, contracts, tests, readback/rollback helpers and evidence manifests.','May build/package software within existing factory contracts; may not invent credentials, self-certify provider writes, bypass D3 governance, or manufacture authority.','D2','production','1.0.0',false,'function:public.ct_factory_continuity_cycle(integer)',jsonb_build_object('phase',3,'priority','software','mark','TM'),now(),now()),
('penta.certify','PentaCertify','provider_adapter_certification','Certify bounded provider adapters and operations using live read, canary, readback, rollback/compensation, runtime-binding and risk evidence.','Evidence-based and fail-closed. Cannot create credentials, waive canaries, or auto-promote D3.','D3','production','1.0.0',false,'function:integration_control.penta_certify_cycle_v3(integer)',jsonb_build_object('phase',3,'mark','TM'),now(),now()),
('penta.credentials','PentaCredentials','credential_custody_and_readiness','Own credential-reference readiness, custody health, continuity, runtime-consumer binding and non-secret credential evidence.','Never manufactures, logs, returns or publishes raw credentials.','D3','production','1.0.0',false,'table:integration_control.credential_continuity_registry',jsonb_build_object('phase',3,'secret_material_exposure',false,'mark','TM'),now(),now()),
('penta.nurture','PentaNurture','software_runtime_nursing_and_maintenance','Nurse and maintain provider/software fabric health and route remediation into PentaBuild/PentaCertify.','May observe, reconcile, retry bounded work and create receipts; may not bypass certification or expose credentials.','D2','production','1.0.0',false,'function:public.penta_nurture_tick_v1()',jsonb_build_object('phase',3,'priority','software','mark','TM','cookie_model','opaque first-party operational session id; server stores SHA-256 only'),now(),now())
on conflict(system_key) do update set canonical_name=excluded.canonical_name,category=excluded.category,purpose=excluded.purpose,authority_boundary=excluded.authority_boundary,risk_ceiling=excluded.risk_ceiling,maturity='production',version=excluded.version,runtime_ref=excluded.runtime_ref,metadata=public.penta_system_registry.metadata||excluded.metadata,last_verified_at=now(),updated_at=now();

create table if not exists integration_control.penta_nurture_checks_v1(check_id uuid primary key default gen_random_uuid(),cycle_id uuid not null,checked_at timestamptz not null default now(),surface_id text not null,provider_system text not null,adapter_key text,certification_state text,credential_reference_state text not null,provider_health_state text,binding_state text,owner_component_key text,result_state text not null check(result_state in('healthy','watch','remediate','blocked')),evidence jsonb not null default '{}'::jsonb);
create table if not exists integration_control.penta_nurture_cookie_events_v1(event_id uuid primary key default gen_random_uuid(),occurred_at timestamptz not null default now(),cookie_sha256 text,consent_state text not null default 'necessary' check(consent_state in('necessary','analytics','declined','unknown')),event_type text not null,surface_id text,provider_system text,actor_class text not null default 'software',metadata jsonb not null default '{}'::jsonb,check(cookie_sha256 is null or cookie_sha256 ~ '^[0-9a-f]{64}$'));
create table if not exists integration_control.penta_nurture_cycle_receipts_v1(receipt_id uuid primary key default gen_random_uuid(),cycle_id uuid not null unique,started_at timestamptz not null,completed_at timestamptz not null default now(),state text not null check(state in('healthy','degraded','blocked','failed')),summary jsonb not null default '{}'::jsonb,evidence jsonb not null default '{}'::jsonb);
create table if not exists integration_control.penta_build_quality_receipts_v1(receipt_id uuid primary key default gen_random_uuid(),task_id uuid references integration_control.penta_certify_tasks_v3(task_id) on delete set null,build_request_id uuid references public.ct_factory_build_requests(id) on delete set null,checked_at timestamptz not null default now(),result_state text not null check(result_state in('complete_contract','scaffold_only','not_applicable')),required_kinds jsonb not null default '[]'::jsonb,observed_kinds jsonb not null default '[]'::jsonb,evidence jsonb not null default '{}'::jsonb);
create index if not exists penta_nurture_checks_surface_time_idx on integration_control.penta_nurture_checks_v1(surface_id,checked_at desc);
create index if not exists penta_nurture_checks_result_time_idx on integration_control.penta_nurture_checks_v1(result_state,checked_at desc);
create index if not exists penta_nurture_cookie_events_time_idx on integration_control.penta_nurture_cookie_events_v1(occurred_at desc);
alter table integration_control.penta_nurture_checks_v1 enable row level security;
alter table integration_control.penta_nurture_cookie_events_v1 enable row level security;
alter table integration_control.penta_nurture_cycle_receipts_v1 enable row level security;
alter table integration_control.penta_build_quality_receipts_v1 enable row level security;
revoke all on integration_control.penta_nurture_checks_v1,integration_control.penta_nurture_cookie_events_v1,integration_control.penta_nurture_cycle_receipts_v1,integration_control.penta_build_quality_receipts_v1 from public,anon,authenticated;

create or replace function integration_control.penta_credential_reference_state_v1(p_provider_system text)
returns text language plpgsql stable security definer set search_path='pg_catalog','integration_control' as $$
declare v_norm text; v_state text;
begin
 v_norm:=regexp_replace(lower(coalesce(p_provider_system,'')),'[^a-z0-9]+','_','g');
 select case when bool_or(continuity_state='provider_managed_only') then 'provider_managed' when bool_or(primary_present and continuity_state like 'verified%') and max(last_verified_at)>=now()-interval '24 hours' then 'verified_reference' when bool_or(primary_present and continuity_state like 'verified%') then 'stale_reference' when bool_or(primary_present) then 'present_unverified' else 'absent' end into v_state
 from integration_control.credential_continuity_registry where regexp_replace(lower(coalesce(provider_system,'')),'[^a-z0-9]+','_','g')=v_norm or regexp_replace(lower(coalesce(service_id,'')),'[^a-z0-9]+','_','g')=v_norm;
 return coalesce(v_state,'absent');
end $$;

create or replace function integration_control.penta_nurture_record_cookie_event_v1(p_cookie_sha256 text,p_event_type text,p_surface_id text default null,p_provider_system text default null,p_consent_state text default 'necessary',p_actor_class text default 'software',p_metadata jsonb default '{}'::jsonb)
returns uuid language plpgsql security definer set search_path='pg_catalog','integration_control' as $$
declare v_id uuid; v_meta jsonb;
begin
 if p_cookie_sha256 is not null and p_cookie_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'COOKIE_HASH_REQUIRED'; end if;
 if p_consent_state not in('necessary','analytics','declined','unknown') then raise exception 'INVALID_CONSENT_STATE'; end if;
 v_meta:=coalesce(p_metadata,'{}'::jsonb)-'authorization'-'cookie'-'set-cookie'-'token'-'access_token'-'refresh_token'-'api_key'-'apikey'-'secret'-'password'-'credential'-'credential_value';
 insert into integration_control.penta_nurture_cookie_events_v1(cookie_sha256,consent_state,event_type,surface_id,provider_system,actor_class,metadata) values(p_cookie_sha256,p_consent_state,left(coalesce(p_event_type,'unknown'),160),p_surface_id,p_provider_system,left(coalesce(p_actor_class,'software'),80),v_meta) returning event_id into v_id;
 return v_id;
end $$;

create or replace function integration_control.penta_certify_activate_control_evidence_v1()
returns jsonb language plpgsql security definer set search_path='pg_catalog','integration_control','public' as $$
declare v_read int:=0; v_write int:=0; v_readback int:=0; v_rollback int:=0; v_queue jsonb;
begin
 with x as(select q.candidate_adapter_key,b.read_state,b.evidence,b.last_checked_at from public.ct_factory_adapter_certification_queue q join public.ct_factory_provider_control_bindings b on b.surface_id=q.surface_id and b.enabled where q.candidate_adapter_key is not null),u as(update integration_control.site_provider_adapters a set read_capability_state='pass',evidence=coalesce(a.evidence,'{}'::jsonb)||jsonb_build_object('penta_certify_live_read',x.evidence->'latest_read_certification','penta_certify_live_read_at',x.last_checked_at),updated_at=now() from x where a.adapter_id=x.candidate_adapter_key and x.read_state='pass' and coalesce((x.evidence->'latest_read_certification'->>'passed')::boolean,false)=true and a.read_capability_state<>'pass' returning 1) select count(*) into v_read from u;
 with x as(select q.candidate_adapter_key,b.write_state,b.evidence,b.last_checked_at from public.ct_factory_adapter_certification_queue q join public.ct_factory_provider_control_bindings b on b.surface_id=q.surface_id and b.enabled where q.candidate_adapter_key is not null),u as(update integration_control.site_provider_adapters a set write_canary_state='pass',evidence=coalesce(a.evidence,'{}'::jsonb)||jsonb_build_object('penta_certify_write_canary',x.evidence,'penta_certify_write_canary_at',x.last_checked_at),updated_at=now() from x where a.adapter_id=x.candidate_adapter_key and x.write_state='pass' and a.write_canary_state<>'pass' returning 1) select count(*) into v_write from u;
 with x as(select q.candidate_adapter_key,b.readback_state,b.evidence,b.last_checked_at from public.ct_factory_adapter_certification_queue q join public.ct_factory_provider_control_bindings b on b.surface_id=q.surface_id and b.enabled where q.candidate_adapter_key is not null),u as(update integration_control.site_provider_adapters a set read_after_write_state='pass',supports_read_after_write=true,evidence=coalesce(a.evidence,'{}'::jsonb)||jsonb_build_object('penta_certify_readback',x.evidence,'penta_certify_readback_at',x.last_checked_at),updated_at=now() from x where a.adapter_id=x.candidate_adapter_key and x.readback_state='pass' and a.read_after_write_state<>'pass' returning 1) select count(*) into v_readback from u;
 with x as(select q.candidate_adapter_key,b.rollback_state,b.evidence,b.last_checked_at from public.ct_factory_adapter_certification_queue q join public.ct_factory_provider_control_bindings b on b.surface_id=q.surface_id and b.enabled where q.candidate_adapter_key is not null),u as(update integration_control.site_provider_adapters a set rollback_canary_state='pass',supports_rollback=true,evidence=coalesce(a.evidence,'{}'::jsonb)||jsonb_build_object('penta_certify_rollback',x.evidence,'penta_certify_rollback_at',x.last_checked_at),updated_at=now() from x where a.adapter_id=x.candidate_adapter_key and x.rollback_state='pass' and a.rollback_canary_state<>'pass' returning 1) select count(*) into v_rollback from u;
 v_queue:=public.ct_factory_reconcile_adapter_certifications();
 return jsonb_build_object('service','ct.penta.certify.evidence-bridge.v1','read_promoted',v_read,'write_promoted',v_write,'readback_promoted',v_readback,'rollback_promoted',v_rollback,'queue_reconcile',v_queue,'at',now());
end $$;

create or replace function public.penta_build_enrich_provider_request_v1()
returns trigger language plpgsql security definer set search_path='pg_catalog','public' as $$
declare v_task text; v_provider text; v_surface text; v_service text;
begin
 if new.source_type<>'penta_certify' or coalesce(new.requirements->>'work_type','')<>'provider_certification_software' then return new; end if;
 if new.requirements?'blueprint' then return new; end if;
 v_task:=coalesce(new.requirements->>'task_kind','provider_gap');v_provider:=coalesce(new.requirements->>'provider_system','provider');v_surface:=coalesce(new.requirements->>'surface_id',new.source_ref,'surface');v_service:=left('PentaBuild '||v_provider||' '||v_task||' Contract',120);
 new.requirements:=new.requirements||jsonb_build_object('penta_build_output_contract','ct.penta.build.provider-assets.v1','blueprint',jsonb_build_object('service_name',v_service,'version','1.0.0','capabilities',jsonb_build_array('provider_adapter_contract',v_task,'readback_contract','rollback_or_compensation_contract','evidence_manifest','fail_closed'),'endpoints',jsonb_build_array(jsonb_build_object('path','/health','method','get','operation_id','health','summary','PentaBuild provider-contract health'),jsonb_build_object('path','/status','method','get','operation_id','status','summary','Read provider-contract status')),'mcp_tools',jsonb_build_array(jsonb_build_object('name','adapter_status','description','Read bounded adapter status'),jsonb_build_object('name','adapter_evidence','description','Read non-secret certification evidence')),'environment',jsonb_build_array(jsonb_build_object('name','PROVIDER_API_BASE','required',false,'secret',false,'description','Provider API base when required'),jsonb_build_object('name','CREDENTIAL_REFERENCE_ID','required',false,'secret',false,'description','PentaCredentials custody reference, never secret value')),'events',jsonb_build_array(jsonb_build_object('name','provider_certification_updated','properties',jsonb_build_object('surface_id',jsonb_build_object('type','string'),'state',jsonb_build_object('type','string')),'required',jsonb_build_array('surface_id','state'))),'policy',jsonb_build_object('policy_id','ct.penta.provider-gap.v1','risk_class',coalesce(new.governance_class,'D1'),'authority','PentaCertify / CHLOM','fail_closed',true,'required_evidence',jsonb_build_array('provider_read','bounded_write_canary','read_after_write','rollback_or_compensation','sha256'),'rules',jsonb_build_array('PentaBuild does not self-certify provider authority','No secret values in generated artifacts','No provider mutation before certification','D3 remains human-governed'))));
 return new;
end $$;
drop trigger if exists trg_penta_build_enrich_provider_request_v1 on public.ct_factory_build_requests;
create trigger trg_penta_build_enrich_provider_request_v1 before insert or update of requirements on public.ct_factory_build_requests for each row execute function public.penta_build_enrich_provider_request_v1();

create or replace function integration_control.penta_build_quality_sweep_v1()
returns jsonb language plpgsql security definer set search_path='pg_catalog','integration_control','public' as $$
declare r record; v_kinds jsonb; v_ok boolean; v_complete int:=0; v_scaffold int:=0; v_requeued int:=0;
begin
 for r in select t.task_id,t.task_kind,t.build_request_id from integration_control.penta_certify_tasks_v3 t join public.ct_factory_build_requests b on b.id=t.build_request_id where t.task_kind in('build_adapter','build_write_canary_contract','build_readback_contract','build_rollback_contract') and b.status='implemented' and t.state='completed' loop
  select coalesce(jsonb_agg(distinct a.metadata->>'kind') filter(where a.artifact_type='source_file'),'[]'::jsonb) into v_kinds from public.ct_factory_build_runs br left join public.ct_factory_artifacts a on a.build_run_id=br.id where br.build_request_id=r.build_request_id and br.status='implemented';
  v_ok:=v_kinds?'policy_manifest' and v_kinds?'env_contract' and v_kinds?'event_contract' and v_kinds?'github_workflow' and v_kinds?'openapi_spec' and v_kinds?'edge_api';
  insert into integration_control.penta_build_quality_receipts_v1(task_id,build_request_id,result_state,required_kinds,observed_kinds,evidence) values(r.task_id,r.build_request_id,case when v_ok then 'complete_contract' else 'scaffold_only' end,jsonb_build_array('policy_manifest','env_contract','event_contract','github_workflow','openapi_spec','edge_api'),v_kinds,jsonb_build_object('task_kind',r.task_kind,'software_priority',true,'provider_certification_granted',false));
  if v_ok then v_complete:=v_complete+1; else update public.ct_factory_build_requests set status='queued',requirements=requirements||jsonb_build_object('penta_rebuild_reason','scaffold_only','penta_rebuild_at',now()),updated_at=now() where id=r.build_request_id; update integration_control.penta_certify_tasks_v3 set state='queued',build_request_id=null,completed_at=null,available_at=now(),last_error='penta_build_scaffold_only_rebuild_required',updated_at=now() where task_id=r.task_id; v_scaffold:=v_scaffold+1;v_requeued:=v_requeued+1; end if;
 end loop;
 return jsonb_build_object('service','ct.penta.build.quality.v1','complete_contract',v_complete,'scaffold_only',v_scaffold,'requeued',v_requeued,'at',now());
end $$;

create or replace function integration_control.penta_nurture_tick_v1()
returns jsonb language plpgsql security definer set search_path='pg_catalog','integration_control','public' as $$
declare v_cycle uuid:=gen_random_uuid();v_started timestamptz:=clock_timestamp();v_cert jsonb:='{}';v_seed jsonb:='{}';v_reconcile jsonb:='{}';v_ingest jsonb:='{}';r record;v_cred text;v_owner text;v_health text;v_result text;v_checked int:=0;v_healthy int:=0;v_watch int:=0;v_remediate int:=0;v_blocked int:=0;v_state text;
begin
 begin v_cert:=public.ct_factory_reconcile_adapter_certifications();exception when others then v_cert:=jsonb_build_object('state','error','error',sqlerrm);end;
 begin v_seed:=integration_control.penta_certify_seed_v3();exception when others then v_seed:=jsonb_build_object('state','error','error',sqlerrm);end;
 begin v_reconcile:=integration_control.penta_certify_reconcile_v3();exception when others then v_reconcile:=jsonb_build_object('state','error','error',sqlerrm);end;
 begin v_ingest:=public.ct_factory_ingest_backlog();exception when others then v_ingest:=jsonb_build_object('state','error','error',sqlerrm);end;
 for r in select q.surface_id,q.provider_system,q.runtime_adapter_key,q.candidate_adapter_key,q.certification_state,q.missing_requirements,q.evidence,b.binding_state,b.adapter_key,b.deployment_policy,b.config,w.health_state,w.provider_connection_state from public.ct_factory_adapter_certification_queue q left join public.ct_factory_surface_bindings b on b.surface_id=q.surface_id left join integration_control.website_surfaces w on w.surface_id=q.surface_id order by q.priority_score desc,q.surface_id loop
  v_cred:=integration_control.penta_credential_reference_state_v1(r.provider_system);select t.owner_component_key into v_owner from integration_control.penta_certify_tasks_v3 t where t.surface_id=r.surface_id and t.state not in('completed','failed') order by t.updated_at desc limit 1;v_owner:=coalesce(v_owner,case when r.certification_state='certified' then 'penta.nurture' else 'penta.certify' end);v_health:=coalesce(r.health_state,r.config->>'health_state','unknown');
  if r.certification_state='certified' and v_health not in('degraded','failed','offline','unknown') and v_cred not in('absent','present_unverified') then v_result:='healthy';v_healthy:=v_healthy+1;elsif exists(select 1 from integration_control.penta_certify_tasks_v3 t where t.surface_id=r.surface_id and t.state='blocked') then v_result:='blocked';v_blocked:=v_blocked+1;elsif r.certification_state='certified' then v_result:='watch';v_watch:=v_watch+1;else v_result:='remediate';v_remediate:=v_remediate+1;end if;
  insert into integration_control.penta_nurture_checks_v1(cycle_id,surface_id,provider_system,adapter_key,certification_state,credential_reference_state,provider_health_state,binding_state,owner_component_key,result_state,evidence) values(v_cycle,r.surface_id,r.provider_system,coalesce(r.runtime_adapter_key,r.candidate_adapter_key,r.adapter_key),r.certification_state,v_cred,v_health,r.binding_state,v_owner,v_result,jsonb_build_object('missing_requirements',coalesce(r.missing_requirements,'[]'::jsonb),'deployment_policy',r.deployment_policy,'provider_connection_state',r.provider_connection_state,'secret_material_exposed',false));v_checked:=v_checked+1;
 end loop;
 v_state:=case when v_blocked>0 then 'blocked' when v_remediate>0 then 'degraded' else 'healthy' end;
 insert into integration_control.penta_nurture_cycle_receipts_v1(cycle_id,started_at,completed_at,state,summary,evidence) values(v_cycle,v_started,clock_timestamp(),v_state,jsonb_build_object('checked',v_checked,'healthy',v_healthy,'watch',v_watch,'remediate',v_remediate,'blocked',v_blocked),jsonb_build_object('adapter_reconcile',v_cert,'certify_seed',v_seed,'certify_reconcile',v_reconcile,'backlog_ingest',v_ingest,'software_priority',true,'secret_material_exposed',false));
 return jsonb_build_object('service','ct.penta.nurture.v1','cycle_id',v_cycle,'state',v_state,'checked',v_checked,'healthy',v_healthy,'watch',v_watch,'remediate',v_remediate,'blocked',v_blocked,'at',now());
end $$;

create or replace function integration_control.penta_nurture_status_v1() returns jsonb language sql stable security definer set search_path='pg_catalog','integration_control','public' as $$ select jsonb_build_object('service','ct.penta.nurture.v1','state','ACTIVE_AUTONOMOUS','phase',3,'priority','software','latest_cycle',(select to_jsonb(r) from integration_control.penta_nurture_cycle_receipts_v1 r order by completed_at desc limit 1),'certify',integration_control.penta_certify_status_v3(),'generated_at',now()); $$;
create or replace function public.penta_nurture_tick_v1() returns jsonb language sql security definer set search_path='pg_catalog','integration_control' as $$select integration_control.penta_nurture_tick_v1();$$;
create or replace function public.penta_nurture_status_v1() returns jsonb language sql stable security definer set search_path='pg_catalog','integration_control' as $$select integration_control.penta_nurture_status_v1();$$;
create or replace function public.penta_nurture_record_cookie_event_v1(p_cookie_sha256 text,p_event_type text,p_surface_id text default null,p_provider_system text default null,p_consent_state text default 'necessary',p_actor_class text default 'software',p_metadata jsonb default '{}'::jsonb) returns uuid language sql security definer set search_path='pg_catalog','integration_control' as $$select integration_control.penta_nurture_record_cookie_event_v1(p_cookie_sha256,p_event_type,p_surface_id,p_provider_system,p_consent_state,p_actor_class,p_metadata);$$;

revoke all on function integration_control.penta_credential_reference_state_v1(text) from public,anon,authenticated;
revoke all on function integration_control.penta_nurture_record_cookie_event_v1(text,text,text,text,text,text,jsonb) from public,anon,authenticated;
revoke all on function integration_control.penta_certify_activate_control_evidence_v1() from public,anon,authenticated;
revoke all on function integration_control.penta_build_quality_sweep_v1() from public,anon,authenticated;
revoke all on function integration_control.penta_nurture_tick_v1() from public,anon,authenticated;
revoke all on function integration_control.penta_nurture_status_v1() from public,anon,authenticated;
revoke all on function public.penta_build_enrich_provider_request_v1() from public,anon,authenticated;
revoke all on function public.penta_nurture_tick_v1() from public,anon,authenticated;
revoke all on function public.penta_nurture_status_v1() from public,anon,authenticated;
revoke all on function public.penta_nurture_record_cookie_event_v1(text,text,text,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function integration_control.penta_credential_reference_state_v1(text) to service_role;
grant execute on function integration_control.penta_nurture_record_cookie_event_v1(text,text,text,text,text,text,jsonb) to service_role;
grant execute on function integration_control.penta_certify_activate_control_evidence_v1() to service_role;
grant execute on function integration_control.penta_build_quality_sweep_v1() to service_role;
grant execute on function integration_control.penta_nurture_tick_v1() to service_role;
grant execute on function integration_control.penta_nurture_status_v1() to service_role;
grant execute on function public.penta_build_enrich_provider_request_v1() to service_role;
grant execute on function public.penta_nurture_tick_v1() to service_role;
grant execute on function public.penta_nurture_status_v1() to service_role;
grant execute on function public.penta_nurture_record_cookie_event_v1(text,text,text,text,text,text,jsonb) to service_role;

do $$declare v_job bigint;begin
 foreach v_job in array array(select jobid from cron.job where jobname in('ct-penta-provider-evidence-bridge-v1','ct-penta-build-quality-v1','ct-penta-nurture-v1')) loop perform cron.unschedule(v_job);end loop;
 perform cron.schedule('ct-penta-provider-evidence-bridge-v1','*/2 * * * *','select integration_control.penta_certify_activate_control_evidence_v1();');
 perform cron.schedule('ct-penta-build-quality-v1','*/5 * * * *','select integration_control.penta_build_quality_sweep_v1();');
 perform cron.schedule('ct-penta-nurture-v1','*/5 * * * *','select public.penta_nurture_tick_v1();');
end$$;
