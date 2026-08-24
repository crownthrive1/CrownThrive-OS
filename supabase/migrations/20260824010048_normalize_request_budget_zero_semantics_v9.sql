-- Applied to the canonical ThriveBase Supabase project as migration
-- 20260824010048 normalize_request_budget_zero_semantics_v9.
-- Founder semantics: -1=unlimited local; 0=exactly zero; positive=N/month; null=fail-closed.
-- Provider-native throttles, quotas, billing and governance remain independent.

create or replace function integration_control.enforce_request_budget_semantics()
returns trigger
language plpgsql
set search_path to 'pg_catalog','integration_control'
as $function$
begin
  new.metadata:=coalesce(new.metadata,'{}'::jsonb) || jsonb_build_object(
    'local_monthly_budget_semantics','-1=unlimited_local_ceiling;0=exactly_zero;positive=literal_local_monthly_ceiling;null=unresolved_fail_closed',
    'provider_throttles_still_apply',true,
    'provider_limits_billing_quotas_separate',true,
    'budget_semantics_generation',9,
    'founder_directive','v4-minus-one-unlimited'
  );
  if new.monthly_request_limit=-1 then
    new.metadata:=new.metadata||jsonb_build_object('local_budget_enabled',true,'local_monthly_budget_value',-1,'request_budget_model','unlimited_local_monthly_ceiling');
  elsif new.monthly_request_limit=0 then
    new.metadata:=new.metadata||jsonb_build_object('local_budget_enabled',false,'local_monthly_budget_value',0,'request_budget_model','exactly_zero_requests');
  elsif new.monthly_request_limit>0 then
    new.metadata:=new.metadata||jsonb_build_object('local_budget_enabled',true,'local_monthly_budget_value',new.monthly_request_limit,'request_budget_model','literal_positive_local_monthly_ceiling');
  else
    new.metadata:=new.metadata||jsonb_build_object('local_budget_enabled',false,'local_monthly_budget_value',null,'request_budget_model','unresolved_fail_closed');
  end if;
  new.updated_at:=now();
  return new;
end
$function$;

create or replace function integration_control.enforce_founder_request_budget_semantics_v4()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control'
as $function$
declare
  p integration_control.request_budget_policies%rowtype;
  v_has_policy boolean := false;
begin
  select * into p
  from integration_control.request_budget_policies
  where service_id=new.service_id and policy_state='active'
  order by policy_version desc
  limit 1;
  v_has_policy := found;

  if v_has_policy then
    new.monthly_request_limit := p.local_monthly_limit;
  elsif new.credential_state='blocked' or new.integration_state='retired' then
    new.monthly_request_limit := 0;
  else
    new.monthly_request_limit := null;
  end if;

  new.metadata := coalesce(new.metadata,'{}'::jsonb) || jsonb_build_object(
    'local_monthly_budget_semantics','-1=unlimited_local_ceiling;0=exactly_zero;positive=literal_local_monthly_ceiling;null=unresolved_fail_closed',
    'request_budget_policy_present',v_has_policy,
    'request_budget_policy_version',case when v_has_policy then p.policy_version else null end,
    'request_budget_policy_mode',case
      when v_has_policy then p.budget_mode
      when new.monthly_request_limit=0 then 'derived_zero_fail_closed'
      else 'unresolved_fail_closed'
    end,
    'request_budget_authority_source',case
      when v_has_policy then 'explicit_active_policy'
      when new.monthly_request_limit=0 then 'service_state_fail_closed'
      else 'none_fail_closed'
    end,
    'request_budget_model',case
      when new.monthly_request_limit=-1 then 'unlimited_local_monthly_ceiling'
      when new.monthly_request_limit=0 then 'exactly_zero_requests'
      when new.monthly_request_limit>0 then 'literal_positive_local_monthly_ceiling'
      else 'unresolved_fail_closed'
    end,
    'local_budget_enabled',new.monthly_request_limit is not null and new.monthly_request_limit<>0,
    'local_monthly_budget_value',new.monthly_request_limit,
    'provider_throttles_still_apply',true,
    'provider_limits_billing_quotas_separate',true,
    'founder_directive','v4-minus-one-unlimited',
    'founder_override_actor','Kavonte Jones Sr.',
    'missing_policy_fail_closed',not v_has_policy,
    'budget_guard_last_applied_at',now()
  );

  if new.service_id in ('adserver_online','adluxe_network') then
    new.metadata := new.metadata || jsonb_build_object(
      'included_plan_requests',3000000,
      'included_plan_threshold_not_hard_stop',true,
      'overage_billed',true,
      'provider_hard_stop',false,
      'finops_monitor_required',true
    );
  end if;

  if new.service_id='locticians' then
    new.metadata := new.metadata || jsonb_build_object(
      'provider_default_rate_limit','100 per 60 seconds website-wide',
      'provider_throttled',true,
      'provider_throttle_authoritative',true
    );
  end if;

  new.updated_at := now();
  return new;
end
$function$;

create or replace function integration_control.enforce_founder_request_budget_semantics_v3()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control'
as $function$
declare
  p integration_control.request_budget_policies%rowtype;
  v_has_policy boolean := false;
begin
  select * into p
  from integration_control.request_budget_policies
  where service_id=new.service_id and policy_state='active'
  order by policy_version desc
  limit 1;
  v_has_policy := found;

  if v_has_policy then
    new.monthly_request_limit := p.local_monthly_limit;
  elsif new.credential_state='blocked' or new.integration_state='retired' then
    new.monthly_request_limit := 0;
  else
    new.monthly_request_limit := null;
  end if;

  new.metadata := coalesce(new.metadata,'{}'::jsonb) || jsonb_build_object(
    'local_monthly_budget_semantics','-1=unlimited_local_ceiling;0=exactly_zero;positive=literal_local_monthly_ceiling;null=unresolved_fail_closed',
    'request_budget_policy_present',v_has_policy,
    'request_budget_policy_version',case when v_has_policy then p.policy_version else null end,
    'request_budget_policy_mode',case
      when v_has_policy then p.budget_mode
      when new.monthly_request_limit=0 then 'derived_zero_fail_closed'
      else 'unresolved_fail_closed'
    end,
    'request_budget_authority_source',case
      when v_has_policy then 'explicit_active_policy'
      when new.monthly_request_limit=0 then 'service_state_fail_closed'
      else 'none_fail_closed'
    end,
    'request_budget_model',case
      when new.monthly_request_limit=-1 then 'unlimited_local_monthly_ceiling'
      when new.monthly_request_limit=0 then 'exactly_zero_requests'
      when new.monthly_request_limit>0 then 'literal_positive_local_monthly_ceiling'
      else 'unresolved_fail_closed'
    end,
    'local_budget_enabled',new.monthly_request_limit is not null and new.monthly_request_limit<>0,
    'local_monthly_budget_value',new.monthly_request_limit,
    'provider_throttles_still_apply',true,
    'provider_limits_billing_quotas_separate',true,
    'founder_directive','v4-minus-one-unlimited',
    'legacy_entrypoint','v3-superseded-compatibility',
    'missing_policy_fail_closed',not v_has_policy,
    'budget_guard_last_applied_at',now()
  );
  new.updated_at := now();
  return new;
end
$function$;

create or replace function integration_control.reconcile_founder_request_budget_semantics_v4()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control'
as $function$
declare
  v_changed integer := 0;
  v_total integer := 0;
  v_drift integer := 0;
begin
  select count(*) into v_total from integration_control.services;

  with expected as (
    select s.service_id,
           case
             when p.policy_id is not null then p.local_monthly_limit
             when s.credential_state='blocked' or s.integration_state='retired' then 0
             else null
           end as expected_limit
    from integration_control.services s
    left join lateral (
      select p.*
      from integration_control.request_budget_policies p
      where p.service_id=s.service_id and p.policy_state='active'
      order by p.policy_version desc
      limit 1
    ) p on true
  )
  select count(*) into v_drift
  from integration_control.services s
  join expected e using(service_id)
  where s.monthly_request_limit is distinct from e.expected_limit
     or coalesce(s.metadata->>'local_monthly_budget_semantics','') <> '-1=unlimited_local_ceiling;0=exactly_zero;positive=literal_local_monthly_ceiling;null=unresolved_fail_closed'
     or coalesce(s.metadata->>'founder_directive','') <> 'v4-minus-one-unlimited';

  with expected as (
    select s.service_id,
           case
             when p.policy_id is not null then p.local_monthly_limit
             when s.credential_state='blocked' or s.integration_state='retired' then 0
             else null
           end as expected_limit
    from integration_control.services s
    left join lateral (
      select p.*
      from integration_control.request_budget_policies p
      where p.service_id=s.service_id and p.policy_state='active'
      order by p.policy_version desc
      limit 1
    ) p on true
  )
  update integration_control.services s
  set monthly_request_limit=s.monthly_request_limit
  from expected e
  where s.service_id=e.service_id
    and (
      s.monthly_request_limit is distinct from e.expected_limit
      or coalesce(s.metadata->>'local_monthly_budget_semantics','') <> '-1=unlimited_local_ceiling;0=exactly_zero;positive=literal_local_monthly_ceiling;null=unresolved_fail_closed'
      or coalesce(s.metadata->>'founder_directive','') <> 'v4-minus-one-unlimited'
    );
  get diagnostics v_changed=row_count;

  return jsonb_build_object(
    'checked_services',v_total,
    'drift_detected',v_drift,
    'services_reconciled',v_changed,
    'canonical_semantics','-1 unlimited local; 0 exactly zero requests; positive integer N means N requests per month; null unresolved/fail-closed',
    'missing_policy_semantics','null/fail-closed unless service state explicitly forces exactly zero',
    'provider_limits_authoritative',true,
    'founder_directive','v4-minus-one-unlimited',
    'checked_at',now()
  );
end
$function$;