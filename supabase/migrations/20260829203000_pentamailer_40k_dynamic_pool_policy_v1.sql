begin;

alter table crm.outbound_config
  drop constraint if exists outbound_config_max_new_cold_emails_per_day_check;
alter table crm.outbound_config
  add constraint outbound_config_max_new_cold_emails_per_day_check
  check (max_new_cold_emails_per_day >= 0 and max_new_cold_emails_per_day <= 500);

create table if not exists integration_control.penta_mail_pool_policy_v2 (
  policy_key text primary key,
  generation bigint not null,
  provider_plan_monthly_cap integer not null check (provider_plan_monthly_cap > 0),
  operational_monthly_cap integer not null check (operational_monthly_cap > 0),
  system_internal_protected_monthly integer not null check (system_internal_protected_monthly >= 0),
  marketing_nominal_monthly_cap integer not null check (marketing_nominal_monthly_cap >= 0),
  locticians_monthly_cap integer not null check (locticians_monthly_cap >= 0),
  locticians_daily_cap integer not null check (locticians_daily_cap >= 0),
  locticians_total_cap integer not null check (locticians_total_cap >= 0),
  other_marketing_nominal_monthly integer not null check (other_marketing_nominal_monthly >= 0),
  timezone text not null default 'America/New_York',
  state text not null check (state in ('active','hold','retired')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  check (operational_monthly_cap <= provider_plan_monthly_cap),
  check (system_internal_protected_monthly + marketing_nominal_monthly_cap <= operational_monthly_cap),
  check (locticians_monthly_cap + other_marketing_nominal_monthly <= marketing_nominal_monthly_cap),
  check (locticians_daily_cap <= locticians_monthly_cap)
);

alter table integration_control.penta_mail_pool_policy_v2 enable row level security;
revoke all on integration_control.penta_mail_pool_policy_v2 from public,anon,authenticated;
grant select,insert,update on integration_control.penta_mail_pool_policy_v2 to service_role;

create or replace function integration_control.penta_mail_pool_policy_guard_v2()
returns trigger
language plpgsql
security definer
set search_path=pg_catalog,integration_control,pg_temp
as $$
begin
  if tg_op='UPDATE' and new.generation < old.generation then
    raise exception 'PENTAMAIL_POOL_STALE_GENERATION:%<%',new.generation,old.generation;
  end if;
  new.updated_at:=clock_timestamp();
  return new;
end;
$$;

drop trigger if exists penta_mail_pool_policy_guard_v2 on integration_control.penta_mail_pool_policy_v2;
create trigger penta_mail_pool_policy_guard_v2
before update on integration_control.penta_mail_pool_policy_v2
for each row execute function integration_control.penta_mail_pool_policy_guard_v2();

insert into integration_control.penta_mail_pool_policy_v2(
  policy_key,generation,provider_plan_monthly_cap,operational_monthly_cap,
  system_internal_protected_monthly,marketing_nominal_monthly_cap,
  locticians_monthly_cap,locticians_daily_cap,locticians_total_cap,
  other_marketing_nominal_monthly,timezone,state,metadata
) values (
  'ct.pentamailer.pool.40k.v1',2026082913,50000,40000,10000,30000,10000,500,120000,20000,
  'America/New_York','active',
  jsonb_build_object(
    'founder_directive','2026-08-29:500/day:10k/month:40k-pentamailer-pool',
    'precedence',jsonb_build_array('system_internal','support_transactional','locticians_marketing','other_marketing'),
    'system_internal_has_first_claim_on_entire_pool',true,
    'marketing_is_residual_after_system_internal_demand',true,
    'locticians_has_protected_marketing_target',true,
    'unused_locticians_quota_releases_only_when_daily_ceiling_makes_it_unspendable',true,
    'provider_plan_headroom',10000,
    'scheduler_clock_authority',false,
    'provider_throttle_evasion_forbidden',true,
    'rollback_rule','higher_generation_supersession_only',
    'authority_expansion',false
  )
)
on conflict(policy_key) do update set
  generation=excluded.generation,
  provider_plan_monthly_cap=excluded.provider_plan_monthly_cap,
  operational_monthly_cap=excluded.operational_monthly_cap,
  system_internal_protected_monthly=excluded.system_internal_protected_monthly,
  marketing_nominal_monthly_cap=excluded.marketing_nominal_monthly_cap,
  locticians_monthly_cap=excluded.locticians_monthly_cap,
  locticians_daily_cap=excluded.locticians_daily_cap,
  locticians_total_cap=excluded.locticians_total_cap,
  other_marketing_nominal_monthly=excluded.other_marketing_nominal_monthly,
  timezone=excluded.timezone,
  state='active',
  metadata=integration_control.penta_mail_pool_policy_v2.metadata||excluded.metadata,
  updated_at=clock_timestamp()
where excluded.generation >= integration_control.penta_mail_pool_policy_v2.generation;

create or replace function integration_control.penta_mail_pool_apply_to_campaign_v2()
returns trigger
language plpgsql
security definer
set search_path=pg_catalog,integration_control,pg_temp
as $$
declare p integration_control.penta_mail_pool_policy_v2%rowtype;
begin
  if new.campaign_id<>'ct.pentamarketer.locticians.claim.20260827.v1' then return new; end if;
  select * into p from integration_control.penta_mail_pool_policy_v2
  where policy_key='ct.pentamailer.pool.40k.v1' and state='active';
  if not found then return new; end if;
  new.daily_cap:=p.locticians_daily_cap;
  new.monthly_cap:=p.locticians_monthly_cap;
  new.total_cap:=p.locticians_total_cap;
  new.metadata:=(coalesce(new.metadata,'{}'::jsonb)-'marketing_monthly_allocation')||jsonb_build_object(
    'production_contract','500_per_day_10000_per_month_dynamic_40k_pool',
    'cold_outreach_daily_soft_cap',p.locticians_daily_cap,
    'cold_outreach_monthly_budget',p.locticians_monthly_cap,
    'pentamailer_operational_pool',p.operational_monthly_cap,
    'marketing_monthly_allocation',p.marketing_nominal_monthly_cap,
    'other_marketing_nominal_monthly',p.other_marketing_nominal_monthly,
    'system_internal_protected_monthly',p.system_internal_protected_monthly,
    'system_internal_precedence',true,
    'pool_policy_key',p.policy_key,
    'pool_policy_generation',p.generation,
    'rollback_rule','higher_generation_supersession_only'
  );
  return new;
end;
$$;

drop trigger if exists penta_mail_pool_apply_to_campaign_v2 on crm.penta_marketer_campaign_v1;
create trigger penta_mail_pool_apply_to_campaign_v2
before insert or update on crm.penta_marketer_campaign_v1
for each row execute function integration_control.penta_mail_pool_apply_to_campaign_v2();

create or replace function integration_control.penta_mail_pool_apply_to_outbound_config_v2()
returns trigger
language plpgsql
security definer
set search_path=pg_catalog,integration_control,pg_temp
as $$
declare p integration_control.penta_mail_pool_policy_v2%rowtype;
begin
  if not coalesce(new.singleton,false) then return new; end if;
  select * into p from integration_control.penta_mail_pool_policy_v2
  where policy_key='ct.pentamailer.pool.40k.v1' and state='active';
  if not found then return new; end if;
  new.max_new_cold_emails_per_day:=p.locticians_daily_cap;
  new.max_new_cold_emails_per_month:=p.locticians_monthly_cap;
  new.updated_at:=clock_timestamp();
  return new;
end;
$$;

drop trigger if exists penta_mail_pool_apply_to_outbound_config_v2 on crm.outbound_config;
create trigger penta_mail_pool_apply_to_outbound_config_v2
before insert or update on crm.outbound_config
for each row execute function integration_control.penta_mail_pool_apply_to_outbound_config_v2();

create or replace function integration_control.penta_mail_pool_apply_to_growth_policy_v2()
returns trigger
language plpgsql
security definer
set search_path=pg_catalog,integration_control,pg_temp
as $$
declare p integration_control.penta_mail_pool_policy_v2%rowtype;
begin
  if new.policy_key<>'mailgun-foundation-growth-v1' then return new; end if;
  select * into p from integration_control.penta_mail_pool_policy_v2
  where policy_key='ct.pentamailer.pool.40k.v1' and state='active';
  if not found then return new; end if;
  new.provider_monthly_cap:=p.provider_plan_monthly_cap;
  new.marketing_monthly_cap:=p.marketing_nominal_monthly_cap;
  new.shared_marketing_reserve:=p.marketing_nominal_monthly_cap;
  new.metadata:=(coalesce(new.metadata,'{}'::jsonb)-'marketing_monthly_cap_preserved')||jsonb_build_object(
    'allocation_basis','40,000 CrownThrive PentaMailer operational pool; system/internal traffic has first claim; marketing nominal 30,000 residual; Locticians target 10,000',
    'crownthrive_operational_monthly_cap',p.operational_monthly_cap,
    'system_internal_protected_monthly',p.system_internal_protected_monthly,
    'marketing_nominal_monthly_cap',p.marketing_nominal_monthly_cap,
    'locticians_monthly_cap',p.locticians_monthly_cap,
    'locticians_daily_cap',p.locticians_daily_cap,
    'other_marketing_nominal_monthly',p.other_marketing_nominal_monthly,
    'dynamic_rebalance',true,
    'system_internal_precedence',true,
    'pool_policy_key',p.policy_key,
    'pool_policy_generation',p.generation,
    'rollback_rule','higher_generation_supersession_only'
  );
  new.updated_at:=clock_timestamp();
  return new;
end;
$$;

drop trigger if exists penta_mail_pool_apply_to_growth_policy_v2 on integration_control.penta_mail_growth_policy_v1;
create trigger penta_mail_pool_apply_to_growth_policy_v2
before insert or update on integration_control.penta_mail_growth_policy_v1
for each row execute function integration_control.penta_mail_pool_apply_to_growth_policy_v2();

create or replace function integration_control.penta_mail_pool_reconcile_v2()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,crm,chlom_runtime,extensions,pg_temp
as $$
declare
  p integration_control.penta_mail_pool_policy_v2%rowtype;
  v_before jsonb;
  v_after jsonb;
  v_changed boolean:=false;
  v_count integer;
  v_event jsonb;
begin
  perform pg_advisory_xact_lock(hashtext('ct:pentamailer:40k-pool-policy'));
  select * into p from integration_control.penta_mail_pool_policy_v2
  where policy_key='ct.pentamailer.pool.40k.v1' and state='active';
  if not found then return jsonb_build_object('state','HOLD','reason','pool_policy_missing'); end if;

  v_before:=jsonb_build_object(
    'campaign',(select jsonb_build_object('daily_cap',daily_cap,'monthly_cap',monthly_cap,'total_cap',total_cap,'state',state) from crm.penta_marketer_campaign_v1 where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1'),
    'outbound',(select jsonb_build_object('daily_cap',max_new_cold_emails_per_day,'monthly_cap',max_new_cold_emails_per_month,'enabled',cold_outreach_enabled) from crm.outbound_config where singleton=true),
    'growth',(select jsonb_build_object('provider_monthly_cap',provider_monthly_cap,'marketing_monthly_cap',marketing_monthly_cap,'shared_marketing_reserve',shared_marketing_reserve,'state',state) from integration_control.penta_mail_growth_policy_v1 where policy_key='mailgun-foundation-growth-v1')
  );

  update crm.penta_marketer_campaign_v1
  set daily_cap=p.locticians_daily_cap,
      monthly_cap=p.locticians_monthly_cap,
      total_cap=p.locticians_total_cap,
      state='active',
      provider_write_authority=true,
      money_movement_authority=false,
      rights_disposition_authority=false,
      credential_authority=false,
      metadata=metadata||jsonb_build_object('pool_policy_key',p.policy_key,'pool_policy_generation',p.generation)
  where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1'
    and (
      daily_cap is distinct from p.locticians_daily_cap
      or monthly_cap is distinct from p.locticians_monthly_cap
      or total_cap is distinct from p.locticians_total_cap
      or state<>'active'
    );
  get diagnostics v_count=row_count;
  v_changed:=v_changed or v_count>0;

  update crm.outbound_config
  set max_new_cold_emails_per_day=p.locticians_daily_cap,
      max_new_cold_emails_per_month=p.locticians_monthly_cap,
      updated_at=clock_timestamp()
  where singleton=true
    and (
      max_new_cold_emails_per_day is distinct from p.locticians_daily_cap
      or max_new_cold_emails_per_month is distinct from p.locticians_monthly_cap
    );
  get diagnostics v_count=row_count;
  v_changed:=v_changed or v_count>0;

  update integration_control.penta_mail_growth_policy_v1
  set provider_monthly_cap=p.provider_plan_monthly_cap,
      marketing_monthly_cap=p.marketing_nominal_monthly_cap,
      shared_marketing_reserve=p.marketing_nominal_monthly_cap,
      metadata=metadata||jsonb_build_object(
        'pool_policy_key',p.policy_key,
        'pool_policy_generation',p.generation,
        'system_internal_precedence',true,
        'dynamic_rebalance',true
      ),
      updated_at=clock_timestamp()
  where policy_key='mailgun-foundation-growth-v1'
    and (
      provider_monthly_cap is distinct from p.provider_plan_monthly_cap
      or marketing_monthly_cap is distinct from p.marketing_nominal_monthly_cap
      or shared_marketing_reserve is distinct from p.marketing_nominal_monthly_cap
    );
  get diagnostics v_count=row_count;
  v_changed:=v_changed or v_count>0;

  update integration_control.penta_mail_growth_channel_budget_v1
  set monthly_cap=p.locticians_monthly_cap,
      daily_soft_cap=p.locticians_daily_cap,
      priority=10,
      metadata=metadata||jsonb_build_object(
        'allocation','protected_locticians_target',
        'borrowable',false,
        'pool_policy_generation',p.generation
      ),
      updated_at=clock_timestamp()
  where channel_key='cold_outreach';

  update integration_control.penta_mail_growth_channel_budget_v1
  set monthly_cap=p.marketing_nominal_monthly_cap,
      daily_soft_cap=case
        when channel_key='newsletter_nurture' then 750
        when channel_key='content_distribution' then 750
        when channel_key='experiments' then 500
        else daily_soft_cap
      end,
      metadata=metadata||jsonb_build_object(
        'allocation','dynamic_other_marketing',
        'borrowable',true,
        'group_nominal_cap',p.other_marketing_nominal_monthly,
        'pool_policy_generation',p.generation
      ),
      updated_at=clock_timestamp()
  where channel_key in ('newsletter_nurture','content_distribution','experiments');

  v_after:=jsonb_build_object(
    'campaign',(select jsonb_build_object('daily_cap',daily_cap,'monthly_cap',monthly_cap,'total_cap',total_cap,'state',state) from crm.penta_marketer_campaign_v1 where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1'),
    'outbound',(select jsonb_build_object('daily_cap',max_new_cold_emails_per_day,'monthly_cap',max_new_cold_emails_per_month,'enabled',cold_outreach_enabled) from crm.outbound_config where singleton=true),
    'growth',(select jsonb_build_object('provider_monthly_cap',provider_monthly_cap,'marketing_monthly_cap',marketing_monthly_cap,'shared_marketing_reserve',shared_marketing_reserve,'state',state) from integration_control.penta_mail_growth_policy_v1 where policy_key='mailgun-foundation-growth-v1'),
    'pool',jsonb_build_object(
      'operational_monthly_cap',p.operational_monthly_cap,
      'system_internal_protected',p.system_internal_protected_monthly,
      'marketing_nominal',p.marketing_nominal_monthly_cap,
      'locticians_monthly',p.locticians_monthly_cap,
      'locticians_daily',p.locticians_daily_cap,
      'other_marketing_nominal',p.other_marketing_nominal_monthly
    )
  );

  if v_changed then
    v_event:=chlom_runtime.append_dail_event(
      'communications.pentamailer.pool_policy.reconciled',
      'communications_policy',
      p.policy_key,
      jsonb_build_object(
        'before',v_before,
        'after',v_after,
        'generation',p.generation,
        'authority_expansion',false,
        'scheduler_clock_authority',false,
        'observed_at',clock_timestamp()
      ),
      'PentaMailer/PentaMarketer/PentaTime/PentaSELF',
      null,
      'PentaMailer',
      '2.0.0',
      encode(extensions.digest(convert_to(v_before::text||v_after::text,'UTF8'),'sha256'),'hex'),
      null,
      'founder-directive:2026-08-29:40k-dynamic-pool',
      null,
      'internal'
    );
  end if;

  return jsonb_build_object(
    'state','ENFORCED',
    'changed',v_changed,
    'generation',p.generation,
    'before',v_before,
    'after',v_after,
    'dail_receipt',v_event,
    'observed_at',clock_timestamp()
  );
end;
$$;
revoke all on function integration_control.penta_mail_pool_reconcile_v2() from public,anon,authenticated;
grant execute on function integration_control.penta_mail_pool_reconcile_v2() to service_role;

insert into penta_self.desired_state_contracts_v1(
  contract_key,generation,contract_kind,target_key,desired_state,source_ref,authority_ref,actor_ref,evidence_sha256
) values
(
  'ct.pentaself.control.locticians-campaign',
  5,
  'control',
  'locticians_growth_campaign',
  jsonb_build_object(
    'state','active','daily_cap',500,'monthly_cap',10000,'total_cap',120000,
    'nonrenewing',false,'rollback_rule','higher_generation_supersession_only',
    'provider_write_authority',true,'money_movement_authority',false,'credential_authority',false,
    'pool_policy_key','ct.pentamailer.pool.40k.v1','pool_policy_generation',2026082913
  ),
  'production:2026-08-29:pentamailer-40k-dynamic-pool',
  'founder-directive:2026-08-29:500-day-10k-month',
  'PentaSELF/PentaMarketer',
  encode(extensions.digest(convert_to(
    'ct.pentaself.control.locticians-campaign|5|500|10000|120000|2026082913',
    'UTF8'
  ),'sha256'),'hex')
),
(
  'ct.pentaself.control.pentamail-growth',
  2,
  'control',
  'pentamail_growth_policy',
  jsonb_build_object(
    'state','active','provider_monthly_cap',50000,'operational_monthly_cap',40000,
    'system_internal_protected_monthly',10000,'marketing_monthly_cap',30000,
    'locticians_monthly_cap',10000,'locticians_daily_cap',500,
    'other_marketing_nominal_monthly',20000,'controlled_batch_per_minute',2,
    'temporary_authorization_ceiling',null,'rollback_rule','higher_generation_supersession_only',
    'pool_policy_key','ct.pentamailer.pool.40k.v1','pool_policy_generation',2026082913
  ),
  'production:2026-08-29:pentamailer-40k-dynamic-pool',
  'founder-directive:2026-08-29:40k-dynamic-pool',
  'PentaSELF/PentaMail/PentaMailer',
  encode(extensions.digest(convert_to(
    'ct.pentaself.control.pentamail-growth|2|50000|40000|10000|30000|10000|500|20000|2026082913',
    'UTF8'
  ),'sha256'),'hex')
)
on conflict(contract_key,generation) do nothing;

select integration_control.penta_mail_pool_reconcile_v2();

commit;
