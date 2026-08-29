-- CrownThrive OS / PentaMail
-- Mailgun Compliance Operations ticket #4248764 states the sending limitation
-- was removed, the account is fully enabled, the prior 100/hour restriction
-- is removed, and associated restrictions are removed. This newer provider
-- evidence supersedes the earlier probation notices for runtime enforcement.

begin;

alter table integration_control.penta_mail_growth_policy_v1
  add column if not exists provider_limit_removed_at timestamptz,
  add column if not exists provider_limit_removed_source_system text,
  add column if not exists provider_limit_removed_source_message_id text;

update integration_control.penta_mail_growth_policy_v1
set crownthrive_temporary_authorization_ceiling=null,
    provider_limit_removed_at='2026-08-28T20:50:06Z'::timestamptz,
    provider_limit_removed_source_system='outlook_mailgun_support',
    provider_limit_removed_source_message_id='AAMkADMwYWMyYWMyLWRlOWMtNDI4YS04MzJhLWU2MTYyNTlkZTI4OQBGAAAAAACysqQwDp21R54CTq6mtbiLBwB4_zpzw7z2RaFOqgUbknAtAAAAAAEMAAB4_zpzw7z2RaFOqgUbknAtAAGRDA4VAAA=',
    metadata=(coalesce(metadata,'{}'::jsonb)
      -'adaptive_provider_gateway'
      -'provider_probation_observed_hourly_cap'
      -'provider_probation_observed_disable_seconds')
      || jsonb_build_object(
        'provider_unrestriction',jsonb_build_object(
          'provider','Mailgun',
          'ticket','4248764',
          'sender','support@mailgun.zendesk.com',
          'received_at','2026-08-28T20:50:06Z',
          'source_system','outlook_mailgun_support',
          'source_message_id','AAMkADMwYWMyYWMyLWRlOWMtNDI4YS04MzJhLWU2MTYyNTlkZTI4OQBGAAAAAACysqQwDp21R54CTq6mtbiLBwB4_zpzw7z2RaFOqgUbknAtAAAAAAEMAAB4_zpzw7z2RaFOqgUbknAtAAGRDA4VAAA=',
          'sending_limitation_removed',true,
          'account_fully_enabled',true,
          'old_100_per_hour_restriction_removed',true,
          'associated_restrictions_removed',true,
          'evidence_class','provider_compliance_support_authoritative_email'
        ),
        'adaptive_rate_mode','provider_unrestricted_governed_campaign_pacing',
        'fixed_hourly_hard_cap_deprecated',true,
        'legacy_numeric_hourly_fields_non_authoritative',true,
        'provider_hourly_cap_active',false,
        'provider_throttle_evasion_forbidden',true,
        'campaign_monthly_and_daily_quotas_preserved',true,
        'suppression_and_unsubscribe_preserved',true,
        'working_hours_preserved',jsonb_build_object('timezone','America/New_York','start_hour',6,'end_hour',21)
      ),
    updated_at=clock_timestamp()
where policy_key='mailgun-foundation-growth-v1';

create or replace function public.penta_mail_effective_rate_policy_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','public'
as $function$
declare
  v_now timestamptz:=clock_timestamp();
  v_notice integration_control.penta_mail_provider_limit_notice_v1%rowtype;
  v_growth integration_control.penta_mail_growth_policy_v1%rowtype;
  v_notice_found boolean:=false;
  v_provider_limit_removed boolean:=false;
  v_gateway_active boolean:=false;
  v_authorized integer;
  v_provider integer;
  v_effective integer;
  v_batch integer:=2;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  select * into v_growth from integration_control.penta_mail_growth_policy_v1
  where policy_key='mailgun-foundation-growth-v1' and state='active';
  select * into v_notice from integration_control.penta_mail_provider_limit_notice_v1
  where provider_route_id='mailgun:relay.crownthrive.com'
  order by received_at desc,created_at desc,notice_id desc limit 1;
  v_notice_found:=found;
  v_provider_limit_removed:=v_growth.provider_limit_removed_at is not null
    and (not v_notice_found or v_growth.provider_limit_removed_at>v_notice.received_at);
  v_gateway_active:=not v_provider_limit_removed and v_notice_found
    and v_notice.gateway_until is not null and v_notice.gateway_until>v_now;
  v_authorized:=case when v_gateway_active then v_growth.crownthrive_temporary_authorization_ceiling else null end;
  v_provider:=case when v_provider_limit_removed then null
    when v_notice_found then nullif(v_notice.observed_hourly_cap,0)
    else nullif(v_growth.provider_hourly_hard_cap,0) end;
  v_effective:=case when v_authorized is not null and v_provider is not null then least(v_authorized,v_provider)
    when v_provider is not null then v_provider when v_authorized is not null then v_authorized else null end;
  v_batch:=case when v_effective is not null then greatest(1,ceil(v_effective::numeric/60)::integer)
    else greatest(1,coalesce(v_growth.controlled_batch_per_minute,2)) end;
  return jsonb_build_object(
    'rate_mode',case when v_provider_limit_removed then 'provider_unrestricted_governed_campaign_pacing'
      when v_gateway_active then 'temporary_provider_email_gateway'
      when v_provider is not null then 'provider_adaptive_no_crownthrive_static_cap'
      else 'adaptive_no_hourly_hard_cap' end,
    'provider_limit_removed',v_provider_limit_removed,
    'provider_limit_removed_at',v_growth.provider_limit_removed_at,
    'provider_limit_removed_source_system',v_growth.provider_limit_removed_source_system,
    'provider_limit_removed_source_message_id',v_growth.provider_limit_removed_source_message_id,
    'gateway_active',v_gateway_active,
    'gateway_until',case when v_gateway_active then v_notice.gateway_until else null end,
    'gateway_seconds',case when v_gateway_active then v_notice.gateway_seconds else null end,
    'provider_retry_after_seconds',case when v_gateway_active then v_notice.provider_retry_after_seconds else null end,
    'configured_temporary_authorization_ceiling',v_growth.crownthrive_temporary_authorization_ceiling,
    'crownthrive_temporary_hourly_authorization_ceiling',v_authorized,
    'crownthrive_static_hourly_hard_cap',null,
    'crownthrive_static_hourly_hard_cap_removed',true,
    'legacy_provider_hourly_field',v_growth.provider_hourly_hard_cap,
    'legacy_crownthrive_hourly_soft_field',v_growth.crownthrive_hourly_soft_cap,
    'legacy_crownthrive_hourly_hard_field',v_growth.crownthrive_hourly_hard_cap,
    'legacy_numeric_hourly_fields_non_authoritative',v_provider_limit_removed,
    'provider_observed_hourly_cap',v_provider,
    'provider_limit_active',v_provider is not null,
    'effective_hourly_hard_cap',v_effective,
    'temporary_hourly_hard_cap',v_effective,
    'controlled_batch_per_minute',v_batch,
    'last_provider_limit_notice_received_at',case when v_notice_found then v_notice.received_at else null end,
    'hard_hourly_limit_removed',v_provider_limit_removed or (not v_gateway_active),
    'provider_throttle_evasion_forbidden',true,
    'marketing_monthly_cap',v_growth.marketing_monthly_cap,
    'provider_monthly_cap',v_growth.provider_monthly_cap,
    'working_hours',jsonb_build_object('timezone',v_growth.timezone,'start_hour',v_growth.send_start_hour,'end_hour',v_growth.send_end_hour)
  );
end
$function$;

create or replace function public.penta_mail_provider_status_v1(p_trigger_ref text default null)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','public'
as $function$
declare
  v_control integration_control.penta_mail_provider_control_v1%rowtype;
  v_control_found boolean:=false;
  v_probation_until timestamptz;
  v_now timestamptz:=clock_timestamp();
  v_state text;
  v_rate jsonb;
  v_gateway boolean:=false;
  v_limit_removed boolean:=false;
  v_gateway_until timestamptz;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  v_rate:=public.penta_mail_effective_rate_policy_v1();
  v_gateway:=coalesce((v_rate->>'gateway_active')::boolean,false);
  v_limit_removed:=coalesce((v_rate->>'provider_limit_removed')::boolean,false);
  v_gateway_until:=nullif(v_rate->>'gateway_until','')::timestamptz;
  select * into v_control from integration_control.penta_mail_provider_control_v1
  where provider_route_id='mailgun:relay.crownthrive.com';
  v_control_found:=found;
  if v_limit_removed then v_state:='controlled_release';
  elsif v_gateway then v_state:='provider_notice_gateway';
  elsif not v_control_found or v_control.state='closed' then v_state:='closed';
  elsif v_now<v_control.hold_until then v_state:='open';
  elsif v_control.state<>'controlled_release' or v_control.last_readback_enabled is not true
    or v_control.enabled_readback_at is null or v_control.enabled_readback_at<v_control.readback_required_after
    or v_control.last_readback_at is distinct from v_control.enabled_readback_at then v_state:='awaiting_provider_readback';
  else v_state:='controlled_release'; end if;
  if nullif(btrim(coalesce(p_trigger_ref,'')),'') is not null then
    select probation_until into v_probation_until from integration_control.penta_mail_trigger_probation_v1
    where trigger_ref=p_trigger_ref and probation_until>v_now;
  end if;
  return jsonb_build_object(
    'provider_route_id','mailgun:relay.crownthrive.com','route_state',v_state,
    'provider_limit_removed',v_limit_removed,'provider_limit_removed_at',v_rate->>'provider_limit_removed_at',
    'provider_limit_removed_source_system',v_rate->>'provider_limit_removed_source_system',
    'provider_limit_removed_source_message_id',v_rate->>'provider_limit_removed_source_message_id',
    'active_incident_id',case when v_control_found then v_control.active_incident_id else null end,
    'hold_until',case when v_gateway then v_gateway_until else null end,
    'seconds_until_hold_boundary',case when v_gateway then greatest(0,ceil(extract(epoch from (v_gateway_until-v_now)))::integer) else 0 end,
    'provider_readback_required',false,'trigger_ref',p_trigger_ref,
    'trigger_state',case when v_probation_until is not null then 'probation' else 'eligible' end,
    'trigger_probation_until',v_probation_until,
    'controlled_batch_size',coalesce((v_rate->>'controlled_batch_per_minute')::integer,2),
    'rolling_hour_limit',nullif(v_rate->>'effective_hourly_hard_cap','')::integer,
    'effective_hourly_hard_cap',nullif(v_rate->>'effective_hourly_hard_cap','')::integer,
    'provider_observed_hourly_cap',nullif(v_rate->>'provider_observed_hourly_cap','')::integer,
    'rate_mode',v_rate->>'rate_mode','adaptive_rate_policy',v_rate,
    'policy_id','ct.pentamailer.policy.mailgun-delivery-resilience.v1','policy_version','1.4.0','as_of',v_now
  );
end
$function$;

update integration_control.penta_mail_provider_control_v1
set state='controlled_release', hold_until=least(coalesce(hold_until,clock_timestamp()),clock_timestamp()), updated_at=clock_timestamp()
where provider_route_id='mailgun:relay.crownthrive.com';

select integration_control.penta_mail_append_control_event_v1(
  'mailgun-unrestriction:4248764:20260828','mailgun.provider_sending_limit.removed',c.active_incident_id,null,
  jsonb_build_object('ticket','4248764','source_system','outlook_mailgun_support',
    'source_message_id','AAMkADMwYWMyYWMyLWRlOWMtNDI4YS04MzJhLWU2MTYyNTlkZTI4OQBGAAAAAACysqQwDp21R54CTq6mtbiLBwB4_zpzw7z2RaFOqgUbknAtAAAAAAEMAAB4_zpzw7z2RaFOqgUbknAtAAGRDA4VAAA=',
    'received_at','2026-08-28T20:50:06Z','sender','support@mailgun.zendesk.com',
    'sending_limitation_removed',true,'account_fully_enabled',true,'old_100_per_hour_restriction_removed',true,
    'associated_restrictions_removed',true,'effective_hourly_hard_cap',null,'marketing_monthly_cap',12500,
    'provider_monthly_plan_cap',50000,'provider_throttle_evasion_forbidden',true),
  'ct-founder-mailgun-unrestriction-20260828-v5')
from integration_control.penta_mail_provider_control_v1 c
where c.provider_route_id='mailgun:relay.crownthrive.com';

commit;