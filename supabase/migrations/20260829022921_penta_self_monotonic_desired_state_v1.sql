create table if not exists penta_self.desired_state_contracts_v1 (
  contract_key text not null,
  generation bigint not null check (generation > 0),
  contract_kind text not null check (contract_kind in ('cron_job','control')),
  target_key text not null,
  desired_state jsonb not null,
  source_ref text not null,
  authority_ref text not null,
  actor_ref text not null,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  primary key (contract_key,generation)
);

create table if not exists penta_self.desired_state_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  contract_key text not null,
  generation bigint not null,
  target_key text not null,
  observed_state jsonb not null,
  desired_state jsonb not null,
  disposition text not null check (disposition in ('in_sync','repaired','held','failed')),
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  observed_at timestamptz not null default now()
);
create index if not exists desired_state_receipts_target_observed_idx on penta_self.desired_state_receipts_v1(target_key,observed_at desc);

alter table penta_self.desired_state_contracts_v1 enable row level security;
alter table penta_self.desired_state_receipts_v1 enable row level security;
revoke all on penta_self.desired_state_contracts_v1 from public,anon,authenticated;
revoke all on penta_self.desired_state_receipts_v1 from public,anon,authenticated;
grant select,insert on penta_self.desired_state_contracts_v1 to service_role;
grant select,insert on penta_self.desired_state_receipts_v1 to service_role;

drop policy if exists desired_state_contracts_service_role_v1 on penta_self.desired_state_contracts_v1;
create policy desired_state_contracts_service_role_v1 on penta_self.desired_state_contracts_v1 for select to service_role using (true);
drop policy if exists desired_state_contracts_insert_service_role_v1 on penta_self.desired_state_contracts_v1;
create policy desired_state_contracts_insert_service_role_v1 on penta_self.desired_state_contracts_v1 for insert to service_role with check (true);
drop policy if exists desired_state_receipts_service_role_v1 on penta_self.desired_state_receipts_v1;
create policy desired_state_receipts_service_role_v1 on penta_self.desired_state_receipts_v1 for select to service_role using (true);
drop policy if exists desired_state_receipts_insert_service_role_v1 on penta_self.desired_state_receipts_v1;
create policy desired_state_receipts_insert_service_role_v1 on penta_self.desired_state_receipts_v1 for insert to service_role with check (true);

create or replace function penta_self.reject_desired_state_mutation_v1()
returns trigger language plpgsql security definer set search_path=pg_catalog,penta_self as $$
begin
  raise exception 'PentaSELF desired-state evidence is append-only; publish a higher generation to supersede it';
end $$;
revoke all on function penta_self.reject_desired_state_mutation_v1() from public,anon,authenticated;
grant execute on function penta_self.reject_desired_state_mutation_v1() to service_role;

drop trigger if exists desired_state_contracts_immutable_v1 on penta_self.desired_state_contracts_v1;
create trigger desired_state_contracts_immutable_v1 before update or delete on penta_self.desired_state_contracts_v1 for each row execute function penta_self.reject_desired_state_mutation_v1();
drop trigger if exists desired_state_receipts_immutable_v1 on penta_self.desired_state_receipts_v1;
create trigger desired_state_receipts_immutable_v1 before update or delete on penta_self.desired_state_receipts_v1 for each row execute function penta_self.reject_desired_state_mutation_v1();

create or replace function penta_self.enforce_desired_state_v1()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_self,cron,crm,integration_control,extensions,public
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_contract record;
  v_job record;
  v_checked integer := 0;
  v_repaired integer := 0;
  v_in_sync integer := 0;
  v_failed integer := 0;
  v_rowcount integer := 0;
  v_observed jsonb;
  v_disposition text;
  v_digest text;
  v_payload jsonb;
  v_schedule text;
  v_command text;
  v_expected_active boolean;
  v_failures jsonb := '[]'::jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;

  for v_contract in
    select distinct on (contract_key) contract_key,generation,contract_kind,target_key,desired_state,source_ref,authority_ref,actor_ref,evidence_sha256
    from penta_self.desired_state_contracts_v1 order by contract_key,generation desc
  loop
    v_checked:=v_checked+1;
    begin
      v_disposition:='in_sync'; v_observed:='{}'::jsonb; v_rowcount:=0;
      if v_contract.contract_kind='cron_job' then
        v_schedule:=v_contract.desired_state->>'schedule';
        v_command:=v_contract.desired_state->>'command';
        v_expected_active:=coalesce((v_contract.desired_state->>'active')::boolean,true);
        if coalesce(v_schedule,'')='' or coalesce(v_command,'')='' then raise exception 'invalid_cron_desired_state'; end if;
        select jsonb_build_object('count',count(*),'schedules',coalesce(jsonb_agg(schedule order by jobid),'[]'::jsonb),'commands',coalesce(jsonb_agg(command order by jobid),'[]'::jsonb),'active',coalesce(jsonb_agg(active order by jobid),'[]'::jsonb))
        into v_observed from cron.job where jobname=v_contract.target_key;
        if (select count(*) from cron.job where jobname=v_contract.target_key)<>1
           or not exists(select 1 from cron.job where jobname=v_contract.target_key and schedule=v_schedule and command=v_command and active=v_expected_active) then
          for v_job in select jobid from cron.job where jobname=v_contract.target_key loop perform cron.unschedule(v_job.jobid); end loop;
          perform cron.schedule(v_contract.target_key,v_schedule,v_command);
          if not v_expected_active then update cron.job set active=false where jobname=v_contract.target_key; end if;
          v_disposition:='repaired'; v_repaired:=v_repaired+1;
        else v_in_sync:=v_in_sync+1; end if;
        insert into penta_self.required_jobs_v1(jobname,expected_schedule,expected_command,auto_repair,risk_class,metadata)
        values(v_contract.target_key,v_schedule,v_command,true,coalesce(v_contract.desired_state->>'risk_class','D1'),jsonb_build_object('monotonic_contract_key',v_contract.contract_key,'monotonic_generation',v_contract.generation,'source_ref',v_contract.source_ref,'authority_ref',v_contract.authority_ref,'rollback_rule','higher_generation_supersession_only','persistent',true))
        on conflict(jobname) do update set expected_schedule=excluded.expected_schedule,expected_command=excluded.expected_command,auto_repair=true,risk_class=excluded.risk_class,metadata=penta_self.required_jobs_v1.metadata||excluded.metadata,updated_at=now();
      else
        if v_contract.target_key='persona_execution_default' then
          select to_jsonb(x) into v_observed from (select control_key,active,automation_enabled,kill_switch,max_batch_size,max_attempts,component_version,certification_state from crm.penta_persona_execution_control_v1 where control_key='default') x;
          update crm.penta_persona_execution_control_v1 set active=true,automation_enabled=true,kill_switch=false,metadata=metadata||jsonb_build_object('monotonic_contract_key',v_contract.contract_key,'monotonic_generation',v_contract.generation,'rollback_rule','higher_generation_supersession_only'),updated_at=now()
          where control_key='default' and (active is distinct from true or automation_enabled is distinct from true or kill_switch is distinct from false or case when coalesce(metadata->>'monotonic_generation','')~'^[0-9]+$' then (metadata->>'monotonic_generation')::bigint else 0 end<v_contract.generation);
          get diagnostics v_rowcount=row_count;
        elsif v_contract.target_key='locticians_growth_campaign' then
          select jsonb_build_object('campaign_id',campaign_id,'state',state,'daily_cap',daily_cap,'monthly_cap',monthly_cap,'provider_write_authority',provider_write_authority,'money_movement_authority',money_movement_authority,'rights_disposition_authority',rights_disposition_authority,'credential_authority',credential_authority) into v_observed from crm.penta_marketer_campaign_v1 where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1';
          update crm.penta_marketer_campaign_v1 set state='active',daily_cap=200,monthly_cap=5000,expires_at=null,nonrenewing=false,provider_write_authority=true,money_movement_authority=false,rights_disposition_authority=false,credential_authority=false,metadata=(metadata-'daily_cap_restored'-'wave5_gate_state'-'temporary_hourly_ceiling')||jsonb_build_object('monotonic_contract_key',v_contract.contract_key,'monotonic_generation',v_contract.generation,'rollback_rule','higher_generation_supersession_only','production_contract','200_per_day_5000_per_month')
          where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1' and (lower(state)<>'active' or daily_cap<>200 or monthly_cap<>5000 or expires_at is not null or nonrenewing is distinct from false or provider_write_authority is distinct from true or money_movement_authority is distinct from false or rights_disposition_authority is distinct from false or credential_authority is distinct from false or case when coalesce(metadata->>'monotonic_generation','')~'^[0-9]+$' then (metadata->>'monotonic_generation')::bigint else 0 end<v_contract.generation);
          get diagnostics v_rowcount=row_count;
        elsif v_contract.target_key='locticians_queue_watermark' then
          select to_jsonb(x) into v_observed from (select campaign_id,active,low_watermark,target_depth,plan_batch_limit,spacing_seconds,send_start_local,send_end_local from crm.penta_marketer_queue_policy_v1 where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1') x;
          update crm.penta_marketer_queue_policy_v1 set active=true,low_watermark=40,target_depth=80,plan_batch_limit=40,send_start_local='06:00'::time,send_end_local='21:00'::time,updated_at=now()
          where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1' and (active is distinct from true or low_watermark<>40 or target_depth<>80 or plan_batch_limit<>40 or send_start_local<>'06:00'::time or send_end_local<>'21:00'::time);
          get diagnostics v_rowcount=row_count;
        elsif v_contract.target_key='pentamail_growth_policy' then
          select jsonb_build_object('policy_key',policy_key,'provider_monthly_cap',provider_monthly_cap,'marketing_monthly_cap',marketing_monthly_cap,'controlled_batch_per_minute',controlled_batch_per_minute,'state',state,'temporary_authorization_ceiling',crownthrive_temporary_authorization_ceiling,'provider_limit_removed_at',provider_limit_removed_at) into v_observed from integration_control.penta_mail_growth_policy_v1 where policy_key='mailgun-foundation-growth-v1';
          update integration_control.penta_mail_growth_policy_v1 set provider_monthly_cap=50000,marketing_monthly_cap=12500,controlled_batch_per_minute=2,crownthrive_temporary_authorization_ceiling=null,state='active',metadata=metadata||jsonb_build_object('monotonic_contract_key',v_contract.contract_key,'monotonic_generation',v_contract.generation,'rollback_rule','higher_generation_supersession_only','provider_limit_removed_preserved',true),updated_at=now()
          where policy_key='mailgun-foundation-growth-v1' and (provider_monthly_cap<>50000 or marketing_monthly_cap<>12500 or controlled_batch_per_minute<>2 or crownthrive_temporary_authorization_ceiling is not null or state<>'active' or case when coalesce(metadata->>'monotonic_generation','')~'^[0-9]+$' then (metadata->>'monotonic_generation')::bigint else 0 end<v_contract.generation);
          get diagnostics v_rowcount=row_count;
        else raise exception 'unsupported_control_target:%',v_contract.target_key; end if;
        if v_rowcount>0 then v_disposition:='repaired';v_repaired:=v_repaired+1; else v_disposition:='in_sync';v_in_sync:=v_in_sync+1; end if;
      end if;
      v_payload:=jsonb_build_object('contract_key',v_contract.contract_key,'generation',v_contract.generation,'target_key',v_contract.target_key,'observed_state',coalesce(v_observed,'{}'::jsonb),'desired_state',v_contract.desired_state,'disposition',v_disposition,'source_ref',v_contract.source_ref,'authority_ref',v_contract.authority_ref,'observed_at',now());
      v_digest:=encode(extensions.digest(v_payload::text,'sha256'),'hex');
      insert into penta_self.desired_state_receipts_v1(contract_key,generation,target_key,observed_state,desired_state,disposition,evidence_sha256) values(v_contract.contract_key,v_contract.generation,v_contract.target_key,coalesce(v_observed,'{}'::jsonb),v_contract.desired_state,v_disposition,v_digest);
    exception when others then
      v_failed:=v_failed+1;
      v_payload:=jsonb_build_object('contract_key',v_contract.contract_key,'generation',v_contract.generation,'target_key',v_contract.target_key,'desired_state',v_contract.desired_state,'disposition','failed','sqlstate',sqlstate,'error',sqlerrm,'observed_at',now());
      v_digest:=encode(extensions.digest(v_payload::text,'sha256'),'hex');
      insert into penta_self.desired_state_receipts_v1(contract_key,generation,target_key,observed_state,desired_state,disposition,evidence_sha256) values(v_contract.contract_key,v_contract.generation,v_contract.target_key,jsonb_build_object('sqlstate',sqlstate,'error',sqlerrm),v_contract.desired_state,'failed',v_digest);
      v_failures:=v_failures||jsonb_build_array(jsonb_build_object('contract_key',v_contract.contract_key,'target_key',v_contract.target_key,'sqlstate',sqlstate,'error',sqlerrm));
    end;
  end loop;
  return jsonb_build_object('service','ct.penta.self.monotonic-desired-state.v1','state',case when v_failed=0 then 'healthy' else 'degraded' end,'contracts_checked',v_checked,'in_sync',v_in_sync,'repaired',v_repaired,'failed',v_failed,'failures',v_failures,'rollback_rule','higher_generation_supersession_only','observed_at',now());
end $$;
revoke all on function penta_self.enforce_desired_state_v1() from public,anon,authenticated;
grant execute on function penta_self.enforce_desired_state_v1() to service_role;

with contracts(contract_key,generation,contract_kind,target_key,desired_state,source_ref,authority_ref,actor_ref) as (
values
('ct.pentaself.job.monotonic-enforcer',1,'cron_job','ct-penta-self-monotonic-state-v1',jsonb_build_object('schedule','* * * * *','command','select penta_self.enforce_desired_state_v1();','active',true,'risk_class','D1'),'production:2026-08-29:pentaself-permanence','ct.penta.self.v1','PentaSELF/PentaTime'),
('ct.pentaself.job.continuous-healing',1,'cron_job','ct-penta-self-continuous-healing-v1',jsonb_build_object('schedule','1-59/2 * * * *','command','select public.penta_self_continuous_healing_tick_v1();','active',true,'risk_class','D1'),'production:2026-08-29:pentaself-permanence','ct.penta.self.v1','PentaSELF/PentaTime'),
('ct.pentaself.job.main-tick',1,'cron_job','ct-penta-self-v1',jsonb_build_object('schedule','*/2 * * * *','command','select public.penta_self_tick_v1();','active',true,'risk_class','D1'),'production:2026-08-29:pentaself-permanence','ct.penta.self.v1','PentaSELF/PentaTime'),
('ct.pentaself.job.factory-continuity',1,'cron_job','ct-software-factory-continuity-v5',jsonb_build_object('schedule','*/2 * * * *','command','select public.ct_factory_continuity_cycle(1);','active',true,'risk_class','D1'),'production:2026-08-29:pentaself-permanence','ct.penta.factory.v1','PentaSELF/PentaFactory'),
('ct.pentaself.job.factory-dispatch',1,'cron_job','ct-software-factory-dispatch-v3',jsonb_build_object('schedule','* * * * *','command','select public.ct_factory_dispatch_tick();','active',true,'risk_class','D1'),'production:2026-08-29:pentaself-permanence','ct.penta.factory.v1','PentaSELF/PentaFactory'),
('ct.pentaself.job.persona-execution',1,'cron_job','penta-persona-execution-v1',jsonb_build_object('schedule','* * * * *','command','select crm.penta_marketer_growth_factory_seed_v1(); select crm.penta_persona_execution_scheduler_tick_v1(25); select crm.penta_persona_execution_tick_v1(10);','active',true,'risk_class','D2'),'production:2026-08-29:pentaself-permanence','ct.pentamarketer.persona-execution-bridge','PentaSELF/PentaMarketer'),
('ct.pentaself.job.outreach-planner',1,'cron_job','ct-outreach-daily-planner-v1',jsonb_build_object('schedule','*/5 * * * *','command','select crm.penta_marketer_batch_planner_v2();','active',true,'risk_class','D2'),'production:2026-08-29:pentaself-permanence','ct.pentamarketer.locticians.dynamic-outreach.v3','PentaSELF/PentaMarketer'),
('ct.pentaself.job.outreach-scheduler',1,'cron_job','ct-outreach-scheduler-tick-v1',jsonb_build_object('schedule','* * * * *','command','select crm.penta_marketer_scheduler_tick_v1();','active',true,'risk_class','D2'),'production:2026-08-29:pentaself-permanence','ct.pentamarketer.locticians.dynamic-outreach.v3','PentaSELF/PentaMarketer'),
('ct.pentaself.job.census',1,'cron_job','ct-penta-census-native-due-v1',jsonb_build_object('schedule','*/5 * * * *','command','select integration_control.penta_census_scheduler_tick_v1();','active',true,'risk_class','D1'),'production:2026-08-29:pentaself-permanence','ct.penta.census.v1.1','PentaSELF/PentaCensus'),
('ct.pentaself.job.bd-article-dispatch',1,'cron_job','ct-locticians-article-schedule-dispatch-v1',jsonb_build_object('schedule','5,15,25,35,45,55 * * * *','command','select public.locticians_article_schedule_dispatch_v1(5);','active',true,'risk_class','D2'),'production:2026-08-29:pentaself-permanence','ct.locticians.brilliant-directories.api-fabric.v3','PentaSELF/PentaMarketer'),
('ct.pentaself.job.bd-article-verifier',1,'cron_job','ct-locticians-article-live-verifier-v1',jsonb_build_object('schedule','*/10 * * * *','command','select public.locticians_article_schedule_due_verifier_v1(10);','active',true,'risk_class','D1'),'production:2026-08-29:pentaself-permanence','ct.locticians.brilliant-directories.api-fabric.v3','PentaSELF/PentaCertify'),
('ct.pentaself.control.persona-execution',1,'control','persona_execution_default',jsonb_build_object('active',true,'automation_enabled',true,'kill_switch',false,'rollback_rule','higher_generation_supersession_only'),'production:2026-08-29:pentaself-permanence','ct.pentamarketer.persona-execution-bridge','PentaSELF/PentaMarketer'),
('ct.pentaself.control.locticians-campaign',1,'control','locticians_growth_campaign',jsonb_build_object('state','active','daily_cap',200,'monthly_cap',5000,'provider_write_authority',true,'money_movement_authority',false,'credential_authority',false,'rollback_rule','higher_generation_supersession_only'),'production:2026-08-29:pentaself-permanence','ct.pentamarketer.locticians.dynamic-outreach.v3','PentaSELF/PentaMarketer'),
('ct.pentaself.control.locticians-watermark',1,'control','locticians_queue_watermark',jsonb_build_object('active',true,'low_watermark',40,'target_depth',80,'plan_batch_limit',40,'send_start_local','06:00','send_end_local','21:00','rollback_rule','higher_generation_supersession_only'),'production:2026-08-29:pentaself-permanence','ct.pentamarketer.locticians.dynamic-outreach.v3','PentaSELF/PentaMarketer'),
('ct.pentaself.control.pentamail-growth',1,'control','pentamail_growth_policy',jsonb_build_object('state','active','provider_monthly_cap',50000,'marketing_monthly_cap',12500,'controlled_batch_per_minute',2,'temporary_authorization_ceiling',null,'rollback_rule','higher_generation_supersession_only'),'production:2026-08-29:pentaself-permanence','ct.penta.mail.v1','PentaSELF/PentaMail')
)
insert into penta_self.desired_state_contracts_v1(contract_key,generation,contract_kind,target_key,desired_state,source_ref,authority_ref,actor_ref,evidence_sha256)
select contract_key,generation,contract_kind,target_key,desired_state,source_ref,authority_ref,actor_ref,encode(extensions.digest(jsonb_build_object('contract_key',contract_key,'generation',generation,'contract_kind',contract_kind,'target_key',target_key,'desired_state',desired_state,'source_ref',source_ref,'authority_ref',authority_ref,'actor_ref',actor_ref)::text,'sha256'),'hex') from contracts;

select cron.unschedule(jobid) from cron.job where jobname='ct-penta-self-monotonic-state-v1';
select cron.schedule('ct-penta-self-monotonic-state-v1','* * * * *','select penta_self.enforce_desired_state_v1();');