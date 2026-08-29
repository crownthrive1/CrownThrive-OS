-- Promote PentaCensus as a production observability service without execution authority.

create table if not exists integration_control.penta_census_certifications_v2 (
  certification_id uuid primary key default gen_random_uuid(),
  contract_ref text not null,
  disposition text not null,
  execution_eligible boolean not null default false,
  authority_ceiling text not null,
  checks jsonb not null,
  evidence_sha256 text not null,
  certified_at timestamptz not null default now(),
  supersedes uuid references integration_control.penta_census_certifications_v2(certification_id)
);
create table if not exists integration_control.penta_census_maturity_projection_v2 (
  system_key text primary key,
  maturity text not null,
  production_service boolean not null,
  execution_eligible boolean not null,
  authority_ceiling text not null,
  certification_id uuid,
  evidence_sha256 text not null,
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table integration_control.penta_census_certifications_v2 enable row level security;
alter table integration_control.penta_census_maturity_projection_v2 enable row level security;
revoke all on integration_control.penta_census_certifications_v2,integration_control.penta_census_maturity_projection_v2 from public,anon,authenticated;
grant select,insert on integration_control.penta_census_certifications_v2 to service_role;
grant select,insert,update on integration_control.penta_census_maturity_projection_v2 to service_role;
do $$ begin
 if not exists(select 1 from pg_policies where schemaname='integration_control' and tablename='penta_census_certifications_v2' and policyname='penta_census_certifications_select_service_role_v2') then create policy penta_census_certifications_select_service_role_v2 on integration_control.penta_census_certifications_v2 for select to service_role using(true); end if;
 if not exists(select 1 from pg_policies where schemaname='integration_control' and tablename='penta_census_certifications_v2' and policyname='penta_census_certifications_insert_service_role_v2') then create policy penta_census_certifications_insert_service_role_v2 on integration_control.penta_census_certifications_v2 for insert to service_role with check(true); end if;
 if not exists(select 1 from pg_policies where schemaname='integration_control' and tablename='penta_census_maturity_projection_v2' and policyname='penta_census_maturity_projection_service_role_v2') then create policy penta_census_maturity_projection_service_role_v2 on integration_control.penta_census_maturity_projection_v2 for all to service_role using(true) with check(true); end if;
end $$;
create or replace function integration_control.penta_census_certifications_immutable_v2() returns trigger language plpgsql security definer set search_path=pg_catalog,integration_control as $$ begin raise exception 'penta_census_certifications_v2 is append-only'; end $$;
revoke all on function integration_control.penta_census_certifications_immutable_v2() from public,anon,authenticated;
grant execute on function integration_control.penta_census_certifications_immutable_v2() to service_role;
drop trigger if exists penta_census_certifications_immutable_v2 on integration_control.penta_census_certifications_v2;
create trigger penta_census_certifications_immutable_v2 before update or delete on integration_control.penta_census_certifications_v2 for each row execute function integration_control.penta_census_certifications_immutable_v2();

create or replace function integration_control.penta_census_certify_production_observability_v2()
returns jsonb language plpgsql security definer
set search_path=pg_catalog,integration_control,cron,extensions,chlom_runtime
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  s jsonb; root jsonb; v_cron_active boolean; v_cron_status text; v_cron_started timestamptz; v_checks jsonb; v_pass boolean; v_disposition text; v_digest text; v_id uuid; v_prev uuid;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  s:=integration_control.penta_census_status_v1(); root:=coalesce(s->'status',s);
  select j.active,r.status,r.start_time into v_cron_active,v_cron_status,v_cron_started
  from cron.job j left join lateral(select status,start_time from cron.job_run_details where jobid=j.jobid order by start_time desc limit 1) r on true
  where j.jobname='ct-penta-census-native-due-v1' order by j.jobid desc limit 1;
  v_checks:=jsonb_build_object(
    'policy_enabled',coalesce((root->'policy'->>'enabled')::boolean,false),
    'latest_run_completed',coalesce(root->'latest_run'->>'state','')='completed',
    'latest_run_id',root->'latest_run'->>'run_id',
    'latest_run_completed_at',root->'latest_run'->>'completed_at',
    'scheduler_active',coalesce(v_cron_active,false),
    'scheduler_latest_status',v_cron_status,
    'scheduler_latest_started_at',v_cron_started,
    'd3_human_reserved',coalesce((root->'guardrails'->>'d3_human_reserved')::boolean,false),
    'raw_cookie_exposure',coalesce((root->'guardrails'->>'raw_cookie_exposure')::boolean,true),
    'raw_secret_exposure',coalesce((root->'guardrails'->>'raw_secret_exposure')::boolean,true),
    'personal_income_inference',coalesce((root->'guardrails'->>'personal_income_inference')::boolean,true),
    'report_recipient',root->'policy'->>'report_recipient',
    'major_update_slo',root->'policy'->'metadata'->>'major_update_slo',
    'execution_eligible',false,
    'provider_write_authority',false,
    'money_movement_authority',false,
    'credential_authority',false
  );
  v_pass:=coalesce((v_checks->>'policy_enabled')::boolean,false) and coalesce((v_checks->>'latest_run_completed')::boolean,false) and coalesce((v_checks->>'scheduler_active')::boolean,false) and coalesce(v_cron_status,'')='succeeded' and coalesce((v_checks->>'d3_human_reserved')::boolean,false) and not coalesce((v_checks->>'raw_cookie_exposure')::boolean,true) and not coalesce((v_checks->>'raw_secret_exposure')::boolean,true) and not coalesce((v_checks->>'personal_income_inference')::boolean,true);
  v_disposition:=case when v_pass then 'PRODUCTION_OBSERVABILITY_CERTIFIED' else 'HOLD' end;
  v_digest:=encode(extensions.digest(convert_to(jsonb_build_object('contract','ct.penta.census.v1.1','disposition',v_disposition,'checks',v_checks)::text,'UTF8'),'sha256'),'hex');
  select certification_id into v_prev from integration_control.penta_census_certifications_v2 order by certified_at desc limit 1;
  insert into integration_control.penta_census_certifications_v2(contract_ref,disposition,execution_eligible,authority_ceiling,checks,evidence_sha256,supersedes) values('ct.penta.census.v1.1',v_disposition,false,'D2',v_checks,v_digest,v_prev) returning certification_id into v_id;
  if v_pass then
    insert into integration_control.penta_census_maturity_projection_v2(system_key,maturity,production_service,execution_eligible,authority_ceiling,certification_id,evidence_sha256,metadata)
    values('penta.census','production_observability',true,false,'D2',v_id,v_digest,jsonb_build_object('canonical_identity',true,'d3_human_reserved',true,'provider_write_authority',false,'money_movement_authority',false,'raw_cookie_values_stored',false,'promotion_basis','runtime plus scheduler plus guardrails'))
    on conflict(system_key) do update set maturity=excluded.maturity,production_service=excluded.production_service,execution_eligible=excluded.execution_eligible,authority_ceiling=excluded.authority_ceiling,certification_id=excluded.certification_id,evidence_sha256=excluded.evidence_sha256,metadata=integration_control.penta_census_maturity_projection_v2.metadata||excluded.metadata,updated_at=now();
  end if;
  perform chlom_runtime.append_dail_event('pentacensus.production_observability.certified','certification','penta.census',jsonb_build_object('certification_id',v_id,'disposition',v_disposition,'execution_eligible',false,'authority_ceiling','D2','checks',v_checks),'PentaCensus/PentaAssure/PentaCertify',null,'PentaCertify','2.0.0',v_digest,null,'ct.penta.census.v1.1',null,'internal');
  return jsonb_build_object('certification_id',v_id,'disposition',v_disposition,'execution_eligible',false,'authority_ceiling','D2','evidence_sha256',v_digest,'checks',v_checks);
end $$;
revoke all on function integration_control.penta_census_certify_production_observability_v2() from public,anon,authenticated;
grant execute on function integration_control.penta_census_certify_production_observability_v2() to service_role;

select integration_control.penta_census_certify_production_observability_v2();
select integration_control.scheduler_desired_job_upsert_v2('ct-penta-census-certify-v2','13 * * * *','select integration_control.penta_census_certify_production_observability_v2();',2026082902,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaCensus/PentaAssure/PentaCertify','rollback_policy','monotonic'));
select cron.unschedule(jobid) from cron.job where jobname='ct-penta-census-certify-v2';
select cron.schedule('ct-penta-census-certify-v2','13 * * * *','select integration_control.penta_census_certify_production_observability_v2();');
select integration_control.scheduler_permanence_reconcile_v2();
