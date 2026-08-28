-- CrownThrive OS / PentaMail
-- Separate founder authorization from provider-enforced rate, correct the
-- Mailgun email gateway to exact seconds, and require fresh provider readback.

begin;

alter table integration_control.penta_mail_provider_limit_notice_v1
  alter column gateway_multiplier set default 1.00;

alter table integration_control.penta_mail_growth_policy_v1
  add column if not exists crownthrive_temporary_authorization_ceiling integer;

do $constraint$
begin
  if not exists (
    select 1
    from pg_constraint
    where conrelid='integration_control.penta_mail_growth_policy_v1'::regclass
      and conname='penta_mail_growth_policy_temporary_authorization_ceiling_v1'
  ) then
    alter table integration_control.penta_mail_growth_policy_v1
      add constraint penta_mail_growth_policy_temporary_authorization_ceiling_v1
      check (
        crownthrive_temporary_authorization_ceiling is null
        or crownthrive_temporary_authorization_ceiling > 0
      );
  end if;
end
$constraint$;

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
  v_gateway_active boolean:=false;
  v_authorized integer;
  v_provider integer;
  v_effective integer;
  v_batch integer:=2;
begin
  perform integration_control.penta_mail_assert_service_role_v1();

  select * into v_growth
  from integration_control.penta_mail_growth_policy_v1
  where policy_key='mailgun-foundation-growth-v1' and state='active';

  select * into v_notice
  from integration_control.penta_mail_provider_limit_notice_v1
  where provider_route_id='mailgun:relay.crownthrive.com'
  order by received_at desc,created_at desc,notice_id desc
  limit 1;
  v_notice_found:=found;

  v_gateway_active:=v_notice_found
    and v_notice.gateway_until is not null
    and v_notice.gateway_until>v_now;

  v_authorized:=case
    when v_gateway_active then
      coalesce(nullif(v_growth.crownthrive_temporary_authorization_ceiling,0),180)
    else null
  end;

  v_provider:=case
    when v_notice_found then nullif(v_notice.observed_hourly_cap,0)
    else nullif(v_growth.provider_hourly_hard_cap,0)
  end;

  v_effective:=case
    when v_authorized is not null and v_provider is not null
      then least(v_authorized,v_provider)
    when v_provider is not null then v_provider
    when v_authorized is not null then v_authorized
    else null
  end;

  v_batch:=case
    when v_effective is not null
      then greatest(1,ceil(v_effective::numeric/60)::integer)
    else greatest(1,coalesce(v_growth.controlled_batch_per_minute,2))
  end;

  return jsonb_build_object(
    'rate_mode',case
      when v_gateway_active then 'temporary_provider_email_gateway'
      when v_provider is not null then 'provider_adaptive_no_crownthrive_static_cap'
      else 'adaptive_no_hourly_hard_cap'
    end,
    'gateway_active',v_gateway_active,
    'gateway_until',case when v_notice_found then v_notice.gateway_until else null end,
    'gateway_seconds',case when v_notice_found then v_notice.gateway_seconds else null end,
    'provider_retry_after_seconds',
      case when v_notice_found then v_notice.provider_retry_after_seconds else null end,
    'gateway_multiplier',case when v_notice_found then v_notice.gateway_multiplier else null end,
    'configured_temporary_authorization_ceiling',
      v_growth.crownthrive_temporary_authorization_ceiling,
    'crownthrive_temporary_hourly_authorization_ceiling',v_authorized,
    'crownthrive_static_hourly_hard_cap',null,
    'crownthrive_static_hourly_hard_cap_removed',not v_gateway_active,
    'legacy_provider_safe_effective_cap',v_growth.crownthrive_hourly_hard_cap,
    'provider_observed_hourly_cap',v_provider,
    'provider_limit_active',v_provider is not null,
    'provider_ceiling_remains_authoritative',true,
    'effective_hourly_hard_cap',v_effective,
    'temporary_hourly_hard_cap',v_effective,
    'controlled_batch_per_minute',v_batch,
    'source_system',case when v_notice_found then v_notice.source_system else null end,
    'source_message_id',case when v_notice_found then v_notice.source_message_id else null end,
    'last_provider_notice_received_at',
      case when v_notice_found then v_notice.received_at else null end,
    'hard_hourly_limit_removed',not v_gateway_active,
    'provider_throttle_evasion_forbidden',true
  );
end
$function$;

create or replace function public.penta_mail_provider_status_v1(
  p_trigger_ref text default null
)
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
  v_gateway_until timestamptz;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  v_rate:=public.penta_mail_effective_rate_policy_v1();
  v_gateway:=coalesce((v_rate->>'gateway_active')::boolean,false);
  v_gateway_until:=nullif(v_rate->>'gateway_until','')::timestamptz;

  select * into v_control
  from integration_control.penta_mail_provider_control_v1
  where provider_route_id='mailgun:relay.crownthrive.com';
  v_control_found:=found;

  if v_gateway then
    v_state:='provider_notice_gateway';
  elsif not v_control_found or v_control.state='closed' then
    v_state:='closed';
  elsif v_now<v_control.hold_until then
    v_state:='open';
  elsif v_control.state<>'controlled_release'
    or v_control.last_readback_enabled is not true
    or v_control.enabled_readback_at is null
    or v_control.enabled_readback_at<v_control.readback_required_after
    or v_control.last_readback_at is distinct from v_control.enabled_readback_at then
    v_state:='awaiting_provider_readback';
  else
    v_state:='controlled_release';
  end if;

  if nullif(btrim(coalesce(p_trigger_ref,'')),'') is not null then
    select probation_until into v_probation_until
    from integration_control.penta_mail_trigger_probation_v1
    where trigger_ref=p_trigger_ref and probation_until>v_now;
  end if;

  return jsonb_build_object(
    'provider_route_id','mailgun:relay.crownthrive.com',
    'route_state',v_state,
    'active_incident_id',case when v_control_found then v_control.active_incident_id else null end,
    'hold_until',case
      when v_gateway then v_gateway_until
      when v_control_found then v_control.hold_until
      else null
    end,
    'readback_required_after',
      case when v_control_found then v_control.readback_required_after else null end,
    'enabled_readback_at',
      case when v_control_found then v_control.enabled_readback_at else null end,
    'last_readback_at',
      case when v_control_found then v_control.last_readback_at else null end,
    'last_readback_enabled',
      case when v_control_found then v_control.last_readback_enabled else null end,
    'seconds_until_hold_boundary',case
      when v_gateway then greatest(0,ceil(extract(epoch from (v_gateway_until-v_now)))::integer)
      when v_control_found then
        greatest(0,ceil(extract(epoch from (coalesce(v_control.hold_until,v_now)-v_now)))::integer)
      else 0
    end,
    'provider_readback_required',v_state='awaiting_provider_readback',
    'trigger_ref',p_trigger_ref,
    'trigger_state',case when v_probation_until is not null then 'probation' else 'eligible' end,
    'trigger_probation_until',v_probation_until,
    'controlled_batch_size',coalesce((v_rate->>'controlled_batch_per_minute')::integer,2),
    'rolling_hour_limit',nullif(v_rate->>'effective_hourly_hard_cap','')::integer,
    'effective_hourly_hard_cap',nullif(v_rate->>'effective_hourly_hard_cap','')::integer,
    'configured_temporary_authorization_ceiling',
      nullif(v_rate->>'configured_temporary_authorization_ceiling','')::integer,
    'crownthrive_temporary_hourly_authorization_ceiling',
      nullif(v_rate->>'crownthrive_temporary_hourly_authorization_ceiling','')::integer,
    'crownthrive_static_hourly_hard_cap_removed',
      coalesce((v_rate->>'crownthrive_static_hourly_hard_cap_removed')::boolean,false),
    'provider_observed_hourly_cap',
      nullif(v_rate->>'provider_observed_hourly_cap','')::integer,
    'provider_ceiling_remains_authoritative',true,
    'rate_mode',v_rate->>'rate_mode',
    'adaptive_rate_policy',v_rate,
    'policy_id','ct.pentamailer.policy.mailgun-delivery-resilience.v1',
    'policy_version','1.3.0',
    'as_of',v_now
  );
end
$function$;

update integration_control.penta_mail_provider_limit_notice_v1
set gateway_multiplier=1.00,
    gateway_seconds=provider_retry_after_seconds,
    gateway_until=case
      when provider_retry_after_seconds is null then null
      else received_at+make_interval(secs=>provider_retry_after_seconds)
    end,
    notice_state=case
      when provider_retry_after_seconds is null then 'observed'
      when received_at+make_interval(secs=>provider_retry_after_seconds)>clock_timestamp()
        then 'active'
      else 'expired'
    end,
    evidence=(coalesce(evidence,'{}'::jsonb)
      -'gateway_rule'
      -'hourly_hard_limit_removed_after_gateway')
      || jsonb_build_object(
        'gateway_rule','provider email seconds exactly',
        'crownthrive_temporary_hourly_authorization_ceiling',180,
        'provider_ceiling_remains_authoritative',true,
        'hard_hourly_limit_temporary',true,
        'crownthrive_static_hourly_limit_removed_after_gateway',true,
        'fresh_provider_readback_required_after_gateway',
          provider_retry_after_seconds is not null,
        'corrected_by',
          'ct-founder-directive-pentamail-adaptive-gateway-20260828-v3'
      ),
    updated_at=clock_timestamp()
where provider_route_id='mailgun:relay.crownthrive.com';

with latest as (
  select *
  from integration_control.penta_mail_provider_limit_notice_v1
  where provider_route_id='mailgun:relay.crownthrive.com'
  order by received_at desc,created_at desc,notice_id desc
  limit 1
)
update integration_control.penta_mail_growth_policy_v1 g
set crownthrive_hourly_hard_cap=g.provider_hourly_hard_cap,
    crownthrive_temporary_authorization_ceiling=180,
    metadata=(coalesce(g.metadata,'{}'::jsonb)-'adaptive_provider_gateway')
      || jsonb_build_object(
        'adaptive_rate_mode',
          'provider_email_seconds_then_remove_crownthrive_static_hourly_cap',
        'fixed_hourly_hard_cap_deprecated',true,
        'provider_throttle_evasion_forbidden',true,
        'adaptive_provider_gateway',jsonb_build_object(
          'source_system',l.source_system,
          'source_message_id',l.source_message_id,
          'observed_hourly_cap',l.observed_hourly_cap,
          'provider_retry_after_seconds',l.provider_retry_after_seconds,
          'gateway_multiplier',1,
          'gateway_seconds',l.gateway_seconds,
          'gateway_until',l.gateway_until,
          'notice_state',case
            when l.gateway_until is null then 'observed'
            when l.gateway_until>clock_timestamp() then 'active'
            else 'expired'
          end,
          'crownthrive_temporary_hourly_authorization_ceiling',180,
          'provider_ceiling_remains_authoritative',true,
          'fresh_provider_readback_required_after_gateway',
            l.provider_retry_after_seconds is not null,
          'rule',
            'Mailgun email seconds are the exact gateway; CrownThrive temporary authorization is 180/hour; CrownThrive static cap expires after the gateway; provider limits remain authoritative'
        ),
        'provider_probation_observed_hourly_cap',
          coalesce(l.observed_hourly_cap,g.provider_hourly_hard_cap),
        'provider_probation_observed_disable_seconds',
          l.provider_retry_after_seconds
      ),
    updated_at=clock_timestamp()
from latest l
where g.policy_key='mailgun-foundation-growth-v1';

with latest as (
  select *
  from integration_control.penta_mail_provider_limit_notice_v1
  where provider_route_id='mailgun:relay.crownthrive.com'
    and gateway_until is not null
  order by received_at desc,created_at desc,notice_id desc
  limit 1
)
update integration_control.penta_mail_provider_control_v1 c
set state='awaiting_provider_readback',
    readback_required_after=greatest(c.hold_until,l.gateway_until),
    enabled_readback_at=null,
    last_readback_at=null,
    last_readback_enabled=null,
    last_readback_http_status=null,
    last_readback_sha256=null,
    last_readback_probe_started_at=null,
    readback_probe_generation=c.readback_probe_generation+1,
    active_readback_probe_id=null,
    active_readback_probe_generation=null,
    active_readback_probe_started_at=null,
    active_readback_probe_expires_at=null,
    updated_at=clock_timestamp()
from latest l
where c.provider_route_id='mailgun:relay.crownthrive.com'
  and (
    c.last_readback_at is null
    or c.last_readback_at<l.gateway_until
    or c.last_readback_enabled is not true
  );

do $evidence$
declare
  v_notice integration_control.penta_mail_provider_limit_notice_v1%rowtype;
  v_incident uuid;
begin
  select * into v_notice
  from integration_control.penta_mail_provider_limit_notice_v1
  where provider_route_id='mailgun:relay.crownthrive.com'
  order by received_at desc,created_at desc,notice_id desc
  limit 1;

  if found then
    select active_incident_id into v_incident
    from integration_control.penta_mail_provider_control_v1
    where provider_route_id='mailgun:relay.crownthrive.com';

    perform integration_control.penta_mail_append_control_event_v1(
      'provider-limit-notice:'||v_notice.notice_id::text||':semantics-v3',
      'mailgun.provider_limit_notice.semantics_corrected',
      v_incident,
      null,
      jsonb_build_object(
        'notice_id',v_notice.notice_id,
        'source_system',v_notice.source_system,
        'source_message_id',v_notice.source_message_id,
        'received_at',v_notice.received_at,
        'provider_retry_after_seconds',v_notice.provider_retry_after_seconds,
        'gateway_seconds',v_notice.gateway_seconds,
        'gateway_until',v_notice.gateway_until,
        'observed_hourly_cap',v_notice.observed_hourly_cap,
        'configured_temporary_authorization_ceiling',180,
        'provider_ceiling_remains_authoritative',true,
        'fresh_provider_readback_required_after_gateway',true,
        'body_sha256',v_notice.body_sha256,
        'raw_provider_body_retained',false
      ),
      'ct-founder-directive-pentamail-adaptive-gateway-20260828-v3'
    );
  end if;
end
$evidence$;

comment on column
  integration_control.penta_mail_growth_policy_v1.crownthrive_temporary_authorization_ceiling
is
'Founder-authorized temporary CrownThrive ceiling, distinct from the provider-safe effective cap. It applies only while an authenticated provider-email gateway is active.';

commit;