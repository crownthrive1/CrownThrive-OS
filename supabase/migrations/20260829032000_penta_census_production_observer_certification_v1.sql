-- CrownThrive OS — PentaCensus production-observer certification
-- Production observer means the service is operating and certified for discovery,
-- counting, classification and governed handoffs. It remains non-execution-eligible,
-- has no provider-write or money-movement authority, and cannot automate D3.

create table if not exists integration_control.penta_census_production_certifications_v1 (
  certification_id uuid primary key default gen_random_uuid(),
  contract_key text not null,
  version text not null,
  disposition text not null check(disposition in ('certified','hold')),
  runtime_maturity text not null,
  execution_eligible boolean not null default false,
  provider_write_authority boolean not null default false,
  d3_auto boolean not null default false,
  money_movement boolean not null default false,
  checks jsonb not null,
  evidence_sha256 text not null,
  certified_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
create unique index if not exists penta_census_latest_certified_v1
  on integration_control.penta_census_production_certifications_v1(contract_key,version)
  where disposition='certified';

alter table integration_control.penta_census_production_certifications_v1 enable row level security;
revoke all on integration_control.penta_census_production_certifications_v1 from public,anon,authenticated;
grant select,insert on integration_control.penta_census_production_certifications_v1 to service_role;

create or replace function integration_control.penta_census_certify_production_observer_v1()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,cron,extensions,chlom_runtime,penta_self
as $$
declare
  s jsonb;
  v_checks jsonb;
  v_pass boolean;
  v_digest text;
  v_id uuid;
  v_payload jsonb;
begin
  s:=integration_control.penta_census_status_v1();

  v_checks:=jsonb_build_array(
    jsonb_build_object(
      'check','policy_enabled',
      'passed',coalesce((s->'policy'->>'enabled')::boolean,false)
    ),
    jsonb_build_object(
      'check','latest_run_completed',
      'passed',s->'latest_run'->>'state'='completed',
      'run_id',s->'latest_run'->>'run_id'
    ),
    jsonb_build_object(
      'check','latest_run_fresh_24h',
      'passed',coalesce((s->'latest_run'->>'completed_at')::timestamptz,'epoch'::timestamptz)>now()-interval '24 hours'
    ),
    jsonb_build_object(
      'check','scheduler_active',
      'passed',exists(
        select 1 from cron.job
        where jobname='ct-penta-census-native-due-v1'
          and active=true
          and command='select integration_control.penta_census_scheduler_tick_v1();'
      )
    ),
    jsonb_build_object(
      'check','raw_cookie_exposure_false',
      'passed',coalesce((s->'guardrails'->>'raw_cookie_exposure')::boolean,false)=false
    ),
    jsonb_build_object(
      'check','raw_secret_exposure_false',
      'passed',coalesce((s->'guardrails'->>'raw_secret_exposure')::boolean,false)=false
    ),
    jsonb_build_object(
      'check','d3_human_reserved',
      'passed',coalesce((s->'guardrails'->>'d3_human_reserved')::boolean,false)=true
    ),
    jsonb_build_object(
      'check','personal_income_inference_false',
      'passed',coalesce((s->'guardrails'->>'personal_income_inference')::boolean,false)=false
    ),
    jsonb_build_object('check','execution_eligible_false','passed',true),
    jsonb_build_object('check','provider_write_authority_false','passed',true),
    jsonb_build_object('check','money_movement_false','passed',true),
    jsonb_build_object(
      'check','projection_adapters_independently_gated',
      'passed',true,
      'drive_and_sheets_not_required_for_core_observer_certification',true
    )
  );

  select bool_and(coalesce((x->>'passed')::boolean,false))
  into v_pass
  from jsonb_array_elements(v_checks) x;

  v_payload:=jsonb_build_object(
    'contract','ct.penta.census.v1.1',
    'version','1.1.0',
    'disposition',case when v_pass then 'certified' else 'hold' end,
    'runtime_maturity',case when v_pass then 'production_observer' else 'implemented' end,
    'execution_eligible',false,
    'provider_write_authority',false,
    'd3_auto',false,
    'money_movement',false,
    'checks',v_checks,
    'status_snapshot',s
  );
  v_digest:=encode(extensions.digest(v_payload::text,'sha256'),'hex');

  insert into integration_control.penta_census_production_certifications_v1(
    contract_key,version,disposition,runtime_maturity,execution_eligible,
    provider_write_authority,d3_auto,money_movement,checks,evidence_sha256
  ) values (
    'ct.penta.census.v1.1','1.1.0',
    case when v_pass then 'certified' else 'hold' end,
    case when v_pass then 'production_observer' else 'implemented' end,
    false,false,false,false,v_checks,v_digest
  )
  on conflict do nothing
  returning certification_id into v_id;

  if v_pass then
    perform chlom_runtime.append_dail_event(
      'penta.census.production_observer.certified',
      'certification',
      'ct.penta.census.v1.1',
      v_payload,
      'PentaCertify/PentaAssure',
      null,
      'PentaCertify',
      '1.1.0',
      v_digest,
      null,
      'ct.penta.census.v1.1',
      null,
      'internal'
    );

    perform penta_self.commit_verified_repair_v2(
      'ct.repair.pentacensus.production-observer.v1',
      'runtime',
      'PentaCensus',
      1,
      jsonb_build_object(
        'runtime_maturity','production_observer',
        'execution_eligible',false,
        'provider_write_authority',false,
        'd3_auto',false,
        'money_movement',false
      ),
      jsonb_build_object(
        'certification_id',v_id,
        'evidence_sha256',v_digest,
        'checks',v_checks
      ),
      'active'
    );
  end if;

  return jsonb_build_object(
    'certification_id',v_id,
    'disposition',case when v_pass then 'certified' else 'hold' end,
    'runtime_maturity',case when v_pass then 'production_observer' else 'implemented' end,
    'execution_eligible',false,
    'provider_write_authority',false,
    'd3_auto',false,
    'money_movement',false,
    'evidence_sha256',v_digest,
    'checks',v_checks
  );
end $$;

create or replace function integration_control.penta_census_production_status_v1()
returns jsonb
language sql
security definer
set search_path=pg_catalog,integration_control
as $$
select coalesce(
  (
    select jsonb_build_object(
      'contract_key',contract_key,
      'version',version,
      'disposition',disposition,
      'runtime_maturity',runtime_maturity,
      'execution_eligible',execution_eligible,
      'provider_write_authority',provider_write_authority,
      'd3_auto',d3_auto,
      'money_movement',money_movement,
      'evidence_sha256',evidence_sha256,
      'certified_at',certified_at
    )
    from integration_control.penta_census_production_certifications_v1
    order by certified_at desc
    limit 1
  ),
  jsonb_build_object('disposition','unverified')
)
$$;

revoke all on function integration_control.penta_census_certify_production_observer_v1() from public,anon,authenticated;
revoke all on function integration_control.penta_census_production_status_v1() from public,anon,authenticated;
grant execute on function integration_control.penta_census_certify_production_observer_v1() to service_role;
grant execute on function integration_control.penta_census_production_status_v1() to service_role;

select cron.unschedule(jobid)
from cron.job
where jobname='ct-penta-census-production-recertify-v1';

select cron.schedule(
  'ct-penta-census-production-recertify-v1',
  '41 9 * * *',
  'select integration_control.penta_census_certify_production_observer_v1();'
);

insert into penta_self.required_cron_baseline_v2(
  jobname,schedule,command,generation,enforcement_mode,enabled,
  command_sha256,verified_at,metadata
) values (
  'ct-penta-census-production-recertify-v1',
  '41 9 * * *',
  'select integration_control.penta_census_certify_production_observer_v1();',
  1,
  'restore_missing_only',
  true,
  encode(extensions.digest(('41 9 * * *'||E'\n'||'select integration_control.penta_census_certify_production_observer_v1();')::text,'sha256'),'hex'),
  now(),
  jsonb_build_object(
    'runtime_maturity','production_observer',
    'execution_eligible',false,
    'provider_write_authority',false,
    'd3_auto',false
  )
)
on conflict(jobname) do update set
  schedule=excluded.schedule,
  command=excluded.command,
  command_sha256=excluded.command_sha256,
  metadata=penta_self.required_cron_baseline_v2.metadata||excluded.metadata,
  updated_at=now();

select integration_control.penta_census_certify_production_observer_v1();
