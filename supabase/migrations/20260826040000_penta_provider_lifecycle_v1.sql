-- Penta provider lifecycle v1
-- Institutionalizes PentaBuild, PentaCertify, PentaCredentials, and PentaNurture
-- over the existing CrownThrive Phase 3 software-factory/provider-certification fabric.
-- No secret values are stored here. No certification or provider authority is manufactured.

insert into public.penta_system_registry(
  system_key,canonical_name,category,purpose,authority_boundary,risk_ceiling,maturity,version,public_exposure,docs_ref,runtime_ref,metadata,last_verified_at,updated_at
) values
(
  'penta.build','PentaBuild','software_asset_adapter_plugin_build',
  'Builds and maintains bounded software assets, provider adapters, plugins, probes, contracts, tests, readback helpers, rollback/compensation helpers, and evidence manifests required to close executable provider gaps.',
  'May generate and package software within existing factory contracts. It may not invent credentials, certify its own consequential provider write, bypass D3 human governance, or manufacture provider authority.',
  'D2','production','1.0.0',false,'software-factory-v4/PENTA-PROVIDER-LIFECYCLE.md','function:public.ct_factory_continuity_cycle(integer)',
  jsonb_build_object('mark','TM','phase',3,'component_key','penta.build','task_source','integration_control.penta_certify_tasks_v3','factory','crownthrive-os-v2-factory','priority','software'),now(),now()
),
(
  'penta.certify','PentaCertify','provider_adapter_certification',
  'Certifies bounded provider adapters and operation capabilities using read, write-canary, read-after-write, rollback/compensation, runtime-binding, evidence, and risk gates.',
  'Certification is evidence-based and fail-closed. PentaCertify cannot self-create provider credentials, waive required canaries, or auto-promote D3 authority.',
  'D3','production','1.0.0',false,'software-factory-v4/PENTA-PROVIDER-LIFECYCLE.md','function:integration_control.penta_certify_cycle_v3(integer)',
  jsonb_build_object('mark','TM','phase',3,'component_key','penta.certify','service','ct.penta.certify.v3','scheduler','ct-penta-certify-v3'),now(),now()
),
(
  'penta.credentials','PentaCredentials','credential_custody_and_readiness',
  'Owns credential-reference readiness, custody health, continuity, runtime-consumer binding, and credential evidence needed by provider adapters without exposing secret material.',
  'Stores and reasons over credential references, custody evidence, fingerprints, and provider-managed auth state only. It never manufactures, logs, returns, or publishes raw credentials.',
  'D3','production','1.0.0',false,'software-factory-v4/PENTA-PROVIDER-LIFECYCLE.md','table:integration_control.credential_continuity_registry',
  jsonb_build_object('mark','TM','phase',3,'component_key','penta.credentials','secret_material_exposure',false,'custody_health','integration_control.run_credential_custody_health()'),now(),now()
),
(
  'penta.nurture','PentaNurture','software_runtime_nursing_and_maintenance',
  'Nurses and maintains the provider/software fabric by checking adapter state, certification state, credential-reference health, provider health, task drift, and operational interaction telemetry, then routes remediation back into the software factory.',
  'Maintenance may observe, reconcile, retry bounded work, and create remediation evidence. It may not bypass certification, reveal credentials, track sensitive content in cookies, or manufacture write authority.',
  'D2','production','1.0.0',false,'software-factory-v4/PENTA-PROVIDER-LIFECYCLE.md','function:integration_control.penta_nurture_tick_v1()',
  jsonb_build_object('mark','TM','phase',3,'component_key','penta.nurture','priority','software','cookie_model','opaque first-party operational session id; server stores SHA-256 only','secret_material_exposure',false),now(),now()
)
on conflict(system_key) do update set
 canonical_name=excluded.canonical_name,category=excluded.category,purpose=excluded.purpose,
 authority_boundary=excluded.authority_boundary,risk_ceiling=excluded.risk_ceiling,maturity=excluded.maturity,
 version=excluded.version,public_exposure=excluded.public_exposure,docs_ref=excluded.docs_ref,runtime_ref=excluded.runtime_ref,
 metadata=public.penta_system_registry.metadata||excluded.metadata,last_verified_at=now(),updated_at=now();

create table if not exists integration_control.penta_nurture_checks_v1 (
  check_id uuid primary key default gen_random_uuid(),
  cycle_id uuid not null,
  checked_at timestamptz not null default now(),
  surface_id text not null,
  provider_system text not null,
  adapter_key text,
  certification_state text,
  credential_reference_state text not null,
  provider_health_state text,
  binding_state text,
  owner_component_key text,
  result_state text not null check(result_state in ('healthy','watch','remediate','blocked')),
  evidence jsonb not null default '{}'::jsonb
);
create index if not exists penta_nurture_checks_surface_time_idx on integration_control.penta_nurture_checks_v1(surface_id,checked_at desc);
create index if not exists penta_nurture_checks_result_time_idx on integration_control.penta_nurture_checks_v1(result_state,checked_at desc);
alter table integration_control.penta_nurture_checks_v1 enable row level security;
revoke all on integration_control.penta_nurture_checks_v1 from anon,authenticated;

create table if not exists integration_control.penta_nurture_cookie_events_v1 (
  event_id uuid primary key default gen_random_uuid(),
  occurred_at timestamptz not null default now(),
  cookie_sha256 text,
  consent_state text not null default 'necessary' check(consent_state in ('necessary','analytics','declined','unknown')),
  event_type text not null,
  surface_id text,
  provider_system text,
  actor_class text not null default 'software',
  metadata jsonb not null default '{}'::jsonb,
  check(cookie_sha256 is null or cookie_sha256 ~ '^[0-9a-f]{64}$')
);
create index if not exists penta_nurture_cookie_events_time_idx on integration_control.penta_nurture_cookie_events_v1(occurred_at desc);
create index if not exists penta_nurture_cookie_events_hash_time_idx on integration_control.penta_nurture_cookie_events_v1(cookie_sha256,occurred_at desc) where cookie_sha256 is not null;
alter table integration_control.penta_nurture_cookie_events_v1 enable row level security;
revoke all on integration_control.penta_nurture_cookie_events_v1 from anon,authenticated;

create table if not exists integration_control.penta_nurture_cycle_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  cycle_id uuid not null unique,
  started_at timestamptz not null,
  completed_at timestamptz not null default now(),
  state text not null check(state in ('healthy','degraded','blocked','failed')),
  summary jsonb not null default '{}'::jsonb,
  evidence jsonb not null default '{}'::jsonb
);
alter table integration_control.penta_nurture_cycle_receipts_v1 enable row level security;
revoke all on integration_control.penta_nurture_cycle_receipts_v1 from anon,authenticated;

create or replace function integration_control.penta_credential_reference_state_v1(p_provider_system text)
returns text
language plpgsql
stable
security definer
set search_path='pg_catalog','integration_control'
as $$
declare v_norm text; v_state text;
begin
  v_norm:=regexp_replace(lower(coalesce(p_provider_system,'')),'[^a-z0-9]+','_','g');
  select case
    when bool_or(continuity_state='provider_managed_only') then 'provider_managed'
    when bool_or(primary_present and continuity_state like 'verified%') and max(last_verified_at)>=now()-interval '24 hours' then 'verified_reference'
    when bool_or(primary_present and continuity_state like 'verified%') then 'stale_reference'
    when bool_or(primary_present) then 'present_unverified'
    else 'absent'
  end into v_state
  from integration_control.credential_continuity_registry
  where regexp_replace(lower(coalesce(provider_system,'')),'[^a-z0-9]+','_','g')=v_norm
     or regexp_replace(lower(coalesce(service_id,'')),'[^a-z0-9]+','_','g')=v_norm;
  return coalesce(v_state,'absent');
end $$;
revoke all on function integration_control.penta_credential_reference_state_v1(text) from public,anon,authenticated;
grant execute on function integration_control.penta_credential_reference_state_v1(text) to service_role;

create or replace function integration_control.penta_nurture_record_cookie_event_v1(
  p_cookie_sha256 text,
  p_event_type text,
  p_surface_id text default null,
  p_provider_system text default null,
  p_consent_state text default 'necessary',
  p_actor_class text default 'software',
  p_metadata jsonb default '{}'::jsonb
) returns uuid
language plpgsql
security definer
set search_path='pg_catalog','integration_control'
as $$
declare v_id uuid; v_meta jsonb;
begin
  if p_cookie_sha256 is not null and p_cookie_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'COOKIE_HASH_REQUIRED'; end if;
  if p_consent_state not in ('necessary','analytics','declined','unknown') then raise exception 'INVALID_CONSENT_STATE'; end if;
  v_meta:=coalesce(p_metadata,'{}'::jsonb)
    - 'authorization' - 'cookie' - 'set-cookie' - 'token' - 'access_token' - 'refresh_token'
    - 'api_key' - 'apikey' - 'secret' - 'password' - 'credential' - 'credential_value';
  insert into integration_control.penta_nurture_cookie_events_v1(cookie_sha256,consent_state,event_type,surface_id,provider_system,actor_class,metadata)
  values(p_cookie_sha256,p_consent_state,left(coalesce(p_event_type,'unknown'),160),p_surface_id,p_provider_system,left(coalesce(p_actor_class,'software'),80),v_meta)
  returning event_id into v_id;
  return v_id;
end $$;
revoke all on function integration_control.penta_nurture_record_cookie_event_v1(text,text,text,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function integration_control.penta_nurture_record_cookie_event_v1(text,text,text,text,text,text,jsonb) to service_role;

create or replace function integration_control.penta_nurture_tick_v1()
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','integration_control','public'
as $$
declare
  v_cycle uuid:=gen_random_uuid(); v_started timestamptz:=clock_timestamp();
  v_cert jsonb:='{}'::jsonb; v_seed jsonb:='{}'::jsonb; v_reconcile jsonb:='{}'::jsonb; v_ingest jsonb:='{}'::jsonb;
  r record; v_cred text; v_owner text; v_health text; v_result text; v_checked int:=0; v_healthy int:=0; v_watch int:=0; v_remediate int:=0; v_blocked int:=0; v_state text;
begin
  begin v_cert:=public.ct_factory_reconcile_adapter_certifications(); exception when others then v_cert:=jsonb_build_object('state','error','error',sqlerrm); end;
  begin v_seed:=integration_control.penta_certify_seed_v3(); exception when others then v_seed:=jsonb_build_object('state','error','error',sqlerrm); end;
  begin v_reconcile:=integration_control.penta_certify_reconcile_v3(); exception when others then v_reconcile:=jsonb_build_object('state','error','error',sqlerrm); end;
  begin v_ingest:=public.ct_factory_ingest_backlog(); exception when others then v_ingest:=jsonb_build_object('state','error','error',sqlerrm); end;

  for r in
    select q.surface_id,q.provider_system,q.runtime_adapter_key,q.candidate_adapter_key,q.certification_state,q.missing_requirements,q.evidence,
           b.binding_state,b.adapter_key,b.deployment_policy,b.config,
           w.health_state,w.provider_connection_state
    from public.ct_factory_adapter_certification_queue q
    left join public.ct_factory_surface_bindings b on b.surface_id=q.surface_id
    left join integration_control.website_surfaces w on w.surface_id=q.surface_id
    order by q.priority_score desc,q.surface_id
  loop
    v_cred:=integration_control.penta_credential_reference_state_v1(r.provider_system);
    select t.owner_component_key into v_owner
      from integration_control.penta_certify_tasks_v3 t
      where t.surface_id=r.surface_id and t.state not in ('completed','failed')
      order by t.updated_at desc limit 1;
    v_owner:=coalesce(v_owner,case when r.certification_state='certified' then 'penta.nurture' else 'penta.certify' end);
    v_health:=coalesce(r.health_state,r.config->>'health_state','unknown');
    if r.certification_state='certified' and v_health not in ('degraded','failed','offline','unknown') and v_cred not in ('absent','present_unverified') then
      v_result:='healthy'; v_healthy:=v_healthy+1;
    elsif exists(select 1 from integration_control.penta_certify_tasks_v3 t where t.surface_id=r.surface_id and t.state='blocked') then
      v_result:='blocked'; v_blocked:=v_blocked+1;
    elsif r.certification_state='certified' then
      v_result:='watch'; v_watch:=v_watch+1;
    else
      v_result:='remediate'; v_remediate:=v_remediate+1;
    end if;
    insert into integration_control.penta_nurture_checks_v1(
      cycle_id,surface_id,provider_system,adapter_key,certification_state,credential_reference_state,provider_health_state,binding_state,owner_component_key,result_state,evidence
    ) values(
      v_cycle,r.surface_id,r.provider_system,coalesce(r.runtime_adapter_key,r.candidate_adapter_key,r.adapter_key),r.certification_state,v_cred,v_health,r.binding_state,v_owner,v_result,
      jsonb_build_object('missing_requirements',coalesce(r.missing_requirements,'[]'::jsonb),'deployment_policy',r.deployment_policy,'provider_connection_state',r.provider_connection_state,'queue_evidence',coalesce(r.evidence,'{}'::jsonb),'secret_material_exposed',false)
    );
    v_checked:=v_checked+1;
  end loop;

  v_state:=case when v_blocked>0 then 'blocked' when v_remediate>0 then 'degraded' else 'healthy' end;
  insert into integration_control.penta_nurture_cycle_receipts_v1(cycle_id,started_at,completed_at,state,summary,evidence)
  values(v_cycle,v_started,clock_timestamp(),v_state,
    jsonb_build_object('checked',v_checked,'healthy',v_healthy,'watch',v_watch,'remediate',v_remediate,'blocked',v_blocked),
    jsonb_build_object('adapter_reconcile',v_cert,'certify_seed',v_seed,'certify_reconcile',v_reconcile,'backlog_ingest',v_ingest,'software_priority',true,'secret_material_exposed',false));
  return jsonb_build_object('service','ct.penta.nurture.v1','cycle_id',v_cycle,'state',v_state,'checked',v_checked,'healthy',v_healthy,'watch',v_watch,'remediate',v_remediate,'blocked',v_blocked,'adapter_reconcile',v_cert,'certify_seed',v_seed,'certify_reconcile',v_reconcile,'backlog_ingest',v_ingest,'at',now());
end $$;
revoke all on function integration_control.penta_nurture_tick_v1() from public,anon,authenticated;
grant execute on function integration_control.penta_nurture_tick_v1() to service_role;

create or replace function integration_control.penta_nurture_status_v1()
returns jsonb
language sql
stable
security definer
set search_path='pg_catalog','integration_control','public'
as $$
  select jsonb_build_object(
    'service','ct.penta.nurture.v1','state','ACTIVE_AUTONOMOUS','phase',3,'priority','software',
    'components',jsonb_build_array('PentaBuild','PentaCertify','PentaCredentials','PentaNurture'),
    'latest_cycle',(select to_jsonb(r) from integration_control.penta_nurture_cycle_receipts_v1 r order by completed_at desc limit 1),
    'certify',integration_control.penta_certify_status_v3(),
    'checks_24h',jsonb_build_object(
      'healthy',(select count(*) from integration_control.penta_nurture_checks_v1 where checked_at>now()-interval '24 hours' and result_state='healthy'),
      'watch',(select count(*) from integration_control.penta_nurture_checks_v1 where checked_at>now()-interval '24 hours' and result_state='watch'),
      'remediate',(select count(*) from integration_control.penta_nurture_checks_v1 where checked_at>now()-interval '24 hours' and result_state='remediate'),
      'blocked',(select count(*) from integration_control.penta_nurture_checks_v1 where checked_at>now()-interval '24 hours' and result_state='blocked')
    ),
    'cookie_telemetry',jsonb_build_object('cookie_value_stored',false,'server_side_hash','SHA-256','secret_fields_allowed',false,'scope','provider-fabric operational interactions'),
    'generated_at',now()
  );
$$;
revoke all on function integration_control.penta_nurture_status_v1() from public,anon,authenticated;
grant execute on function integration_control.penta_nurture_status_v1() to service_role;

create or replace function public.penta_nurture_tick_v1() returns jsonb
language sql security definer set search_path='pg_catalog','integration_control' as $$ select integration_control.penta_nurture_tick_v1(); $$;
create or replace function public.penta_nurture_status_v1() returns jsonb
language sql stable security definer set search_path='pg_catalog','integration_control' as $$ select integration_control.penta_nurture_status_v1(); $$;
create or replace function public.penta_nurture_record_cookie_event_v1(p_cookie_sha256 text,p_event_type text,p_surface_id text default null,p_provider_system text default null,p_consent_state text default 'necessary',p_actor_class text default 'software',p_metadata jsonb default '{}'::jsonb) returns uuid
language sql security definer set search_path='pg_catalog','integration_control' as $$ select integration_control.penta_nurture_record_cookie_event_v1(p_cookie_sha256,p_event_type,p_surface_id,p_provider_system,p_consent_state,p_actor_class,p_metadata); $$;
revoke all on function public.penta_nurture_tick_v1() from public,anon,authenticated;
revoke all on function public.penta_nurture_status_v1() from public,anon,authenticated;
revoke all on function public.penta_nurture_record_cookie_event_v1(text,text,text,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.penta_nurture_tick_v1() to service_role;
grant execute on function public.penta_nurture_status_v1() to service_role;
grant execute on function public.penta_nurture_record_cookie_event_v1(text,text,text,text,text,text,jsonb) to service_role;

-- PentaNurture observes/reconciles every five minutes. PentaBuild/PentaCertify retain their existing higher-frequency workers.
do $$
declare v_job bigint;
begin
  if to_regclass('cron.job') is not null then
    select jobid into v_job from cron.job where jobname='ct-penta-nurture-v1' limit 1;
    if v_job is not null then perform cron.unschedule(v_job); end if;
    perform cron.schedule('ct-penta-nurture-v1','*/5 * * * *','select public.penta_nurture_tick_v1();');
  end if;
end $$;

select public.penta_nurture_tick_v1();
