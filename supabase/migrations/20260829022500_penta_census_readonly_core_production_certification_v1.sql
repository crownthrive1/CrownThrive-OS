create table if not exists integration_control.penta_census_production_certification_v1 (
  certification_id text primary key,
  component_key text not null unique,
  version text not null,
  state text not null check (state in ('candidate','production','hold','retired')),
  certified_scope jsonb not null,
  excluded_scope jsonb not null,
  evidence jsonb not null,
  evidence_sha256 text not null,
  certified_at timestamptz,
  certifier_ref text not null,
  rollback_handle text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table integration_control.penta_census_production_certification_v1 enable row level security;
revoke all on integration_control.penta_census_production_certification_v1 from public, anon, authenticated;
grant select, insert, update on integration_control.penta_census_production_certification_v1 to service_role;
drop policy if exists penta_census_production_certification_service_role_v1 on integration_control.penta_census_production_certification_v1;
create policy penta_census_production_certification_service_role_v1
  on integration_control.penta_census_production_certification_v1
  for all to service_role using (true) with check (true);

do $$
declare
  v_status jsonb:=integration_control.penta_census_status_v1();
  v_latest jsonb;
  v_policy jsonb;
  v_evidence jsonb;
  v_hash text;
  v_cron_ok boolean;
  v_report_queued boolean;
  v_guardrails_ok boolean;
begin
  v_latest:=coalesce(v_status->'latest_run','{}'::jsonb);
  v_policy:=coalesce(v_status->'policy','{}'::jsonb);

  select exists(
    select 1
    from cron.job j
    join lateral (
      select status,start_time,end_time
      from cron.job_run_details d
      where d.jobid=j.jobid
      order by start_time desc
      limit 1
    ) d on true
    where j.jobname='ct-penta-census-native-due-v1'
      and j.active=true
      and j.schedule='*/5 * * * *'
      and d.status='succeeded'
  ) into v_cron_ok;

  v_report_queued:=coalesce((v_latest->'snapshot'->'mail'->>'queued')::boolean,false);
  v_guardrails_ok:=coalesce((v_status->'guardrails'->>'raw_cookie_exposure')::boolean,false)=false
    and coalesce((v_status->'guardrails'->>'raw_secret_exposure')::boolean,false)=false
    and coalesce((v_status->'guardrails'->>'personal_income_inference')::boolean,false)=false
    and coalesce((v_status->'guardrails'->>'d3_human_reserved')::boolean,true)=true;

  if coalesce((v_policy->>'enabled')::boolean,false)<>true then raise exception 'penta_census_policy_not_enabled'; end if;
  if coalesce(v_latest->>'state','')<>'completed' then raise exception 'penta_census_latest_run_not_completed'; end if;
  if not v_cron_ok then raise exception 'penta_census_scheduler_not_verified'; end if;
  if not v_report_queued then raise exception 'penta_census_founder_report_not_queued'; end if;
  if not v_guardrails_ok then raise exception 'penta_census_guardrails_failed'; end if;

  v_evidence:=jsonb_build_object(
    'status_contract',v_status->>'contract',
    'latest_run_id',v_latest->>'run_id',
    'latest_run_kind',v_latest->>'run_kind',
    'latest_run_state',v_latest->>'state',
    'pentas_count',v_latest->>'pentas_count',
    'systems_count',v_latest->>'systems_count',
    'providers_count',v_latest->>'providers_count',
    'handoffs_open',v_latest->>'handoffs_open',
    'discoveries_open',v_latest->>'discoveries_open',
    'scheduler_job','ct-penta-census-native-due-v1',
    'scheduler_active',true,
    'scheduler_latest_status','succeeded',
    'founder_report_queued',true,
    'guardrails',v_status->'guardrails',
    'provider_write_adapters_excluded',jsonb_build_array(
      'Google Drive unattended write',
      'Google Sheets unattended write',
      'arbitrary provider mutation'
    ),
    'd3_human_reserved',true,
    'certified_at',now()
  );
  v_hash:=encode(extensions.digest(v_evidence::text,'sha256'),'hex');

  insert into integration_control.penta_census_production_certification_v1(
    certification_id,component_key,version,state,certified_scope,excluded_scope,
    evidence,evidence_sha256,certified_at,certifier_ref,rollback_handle
  ) values (
    'ct.assure.penta-census-readonly-core.v1',
    'penta.census',
    '1.1.0',
    'production',
    jsonb_build_array(
      'repository namespace discovery',
      'registered system/provider census',
      'classification',
      'diffing',
      'governed handoff routing',
      'authorized economic aggregate capture',
      'founder report enqueue',
      'scheduled heartbeat and major census'
    ),
    jsonb_build_array(
      'D3 execution',
      'authority self-promotion',
      'raw cookie access',
      'raw secret access',
      'personal income inference',
      'unattended Google Drive write',
      'unattended Google Sheets write',
      'arbitrary provider write',
      'money movement'
    ),
    v_evidence,
    v_hash,
    now(),
    'PentaAssure/PentaCertify',
    'disable ct-penta-census-native-due-v1 and retain census history'
  )
  on conflict(component_key) do update set
    version=excluded.version,
    state='production',
    certified_scope=excluded.certified_scope,
    excluded_scope=excluded.excluded_scope,
    evidence=excluded.evidence,
    evidence_sha256=excluded.evidence_sha256,
    certified_at=excluded.certified_at,
    certifier_ref=excluded.certifier_ref,
    rollback_handle=excluded.rollback_handle,
    updated_at=now();

  perform penta_self.register_permanent_repair_v1(
    'ct.repair.penta-census-readonly-core-production.v1',
    'PentaCensus/read-only core',
    null,
    jsonb_build_object(
      'component_key','penta.census',
      'state','production',
      'version','1.1.0',
      'scheduler','ct-penta-census-native-due-v1',
      'certified_scope','read-only discovery/count/classify/route/report',
      'provider_write_adapters_excluded',true
    ),
    v_evidence,
    now(),
    'runtime:integration_control.penta_census_production_certification_v1',
    'newer-independent-runtime-or-guardrail-failure-only'
  );
end $$;

create or replace function integration_control.penta_census_production_status_v1()
returns jsonb
language sql
security definer
set search_path=pg_catalog,integration_control
as $$
select jsonb_build_object(
  'component_key',component_key,
  'version',version,
  'state',state,
  'certified_scope',certified_scope,
  'excluded_scope',excluded_scope,
  'evidence_sha256',evidence_sha256,
  'certified_at',certified_at,
  'certifier_ref',certifier_ref,
  'rollback_handle',rollback_handle,
  'authority_expansion',false
)
from integration_control.penta_census_production_certification_v1
where component_key='penta.census'
$$;
revoke all on function integration_control.penta_census_production_status_v1() from public, anon, authenticated;
grant execute on function integration_control.penta_census_production_status_v1() to service_role;
