-- CrownThrive OS / PentaMail
-- Correct Mailgun email-timed gateway semantics:
--   provider email seconds = gateway seconds
--   CrownThrive temporary authorization ceiling = 180/hour
--   CrownThrive static hourly ceiling expires after the gateway
--   provider-advertised ceilings remain authoritative
--   a fresh post-notice provider readback is required before release

begin;

alter table integration_control.penta_mail_provider_limit_notice_v1
  alter column gateway_multiplier set default 1.00;

create or replace function public.penta_mail_ingest_provider_limit_notice_v1(
  p_source_system text,
  p_source_message_id text,
  p_sender text,
  p_subject text,
  p_body_text text,
  p_received_at timestamptz,
  p_body_sha256 text default null
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','integration_control','extensions'
as $function$
declare
  v_text text := lower(coalesce(p_subject,'') || E'\n' || coalesce(p_body_text,''));
  v_cap_match text[];
  v_retry_match text[];
  v_cap integer;
  v_retry integer;
  v_gateway integer;
  v_received timestamptz := coalesce(p_received_at, clock_timestamp());
  v_until timestamptz;
  v_sha text;
  v_state text;
  v_sender text := lower(coalesce(p_sender,''));
  v_source_system text := lower(btrim(coalesce(p_source_system,'')));
  v_source_message_id text := btrim(coalesce(p_source_message_id,''));
  v_notice_id uuid;
  v_existing integration_control.penta_mail_provider_limit_notice_v1%rowtype;
  v_is_latest boolean := false;
  v_active_incident_id uuid;
  v_source_fingerprint text;
begin
  perform integration_control.penta_mail_assert_service_role_v1();

  if length(v_source_system)=0 or length(v_source_message_id)=0 then
    raise exception 'PENTAMAIL_PROVIDER_NOTICE_SOURCE_REQUIRED';
  end if;
  if length(v_source_system)>80 or length(v_source_message_id)>500 then
    raise exception 'PENTAMAIL_PROVIDER_NOTICE_SOURCE_TOO_LONG';
  end if;
  if not (
    v_sender like '%support@mailgun.net%'
    or v_sender like '%help@mailgun.com%'
    or v_sender='mailgun-api'
    or v_source_system='mailgun_api'
  ) then
    return jsonb_build_object('accepted',false,'reason','sender_not_mailgun');
  end if;

  v_sha := coalesce(
    nullif(lower(btrim(coalesce(p_body_sha256,''))),''),
    encode(extensions.digest(convert_to(coalesce(p_body_text,''),'UTF8'),'sha256'),'hex')
  );
  if v_sha !~ '^[0-9a-f]{64}$' then
    v_sha := encode(extensions.digest(convert_to(coalesce(p_body_text,''),'UTF8'),'sha256'),'hex');
  end if;

  select * into v_existing
  from integration_control.penta_mail_provider_limit_notice_v1
  where source_system=v_source_system
    and source_message_id=v_source_message_id;

  if found then
    if v_existing.body_sha256<>v_sha
       or v_existing.received_at<>v_received then
      raise exception 'PENTAMAIL_PROVIDER_NOTICE_CONFLICT';
    end if;
    return jsonb_build_object(
      'accepted',true,
      'idempotent_replay',true,
      'notice_id',v_existing.notice_id,
      'notice_state',case
        when v_existing.gateway_until is null then 'observed'
        when v_existing.gateway_until>clock_timestamp() then 'active'
        else 'expired'
      end,
      'observed_hourly_cap',v_existing.observed_hourly_cap,
      'provider_retry_after_seconds',v_existing.provider_retry_after_seconds,
      'gateway_multiplier',v_existing.gateway_multiplier,
      'gateway_seconds',v_existing.gateway_seconds,
      'gateway_until',v_existing.gateway_until,
      'source_message_id',v_existing.source_message_id
    );
  end if;

  select regexp_match(
    v_text,
    'limited to[^0-9]{0,40}([0-9]{1,6})[[:space:]]+messages?[[:space:]]*(/|per)[[:space:]]*hour'
  ) into v_cap_match;
  if v_cap_match is not null then
    v_cap := greatest(1,least(v_cap_match[1]::integer,1000000));
  end if;

  select regexp_match(
    v_text,
    'enabled[^0-9]{0,40}([0-9]{1,6})[[:space:]]+seconds?'
  ) into v_retry_match;
  if v_retry_match is null then
    select regexp_match(
      v_text,
      'retry-after[^0-9]{0,20}([0-9]{1,6})'
    ) into v_retry_match;
  end if;
  if v_retry_match is null then
    select regexp_match(
      v_text,
      'retry[^0-9]{0,40}([0-9]{1,6})[[:space:]]+seconds?'
    ) into v_retry_match;
  end if;
  if v_retry_match is null then
    select regexp_match(
      v_text,
      'in[[:space:]]+([0-9]{1,6})[[:space:]]+seconds?'
    ) into v_retry_match;
  end if;
  if v_retry_match is not null then
    v_retry := greatest(1,least(v_retry_match[1]::integer,86400));
  end if;

  if v_cap is null and v_retry is null then
    return jsonb_build_object('accepted',false,'reason','no_rate_or_gateway_signal');
  end if;

  v_gateway := v_retry;
  v_until := case
    when v_gateway is null then null
    else v_received + make_interval(secs=>v_gateway)
  end;
  v_state := case
    when v_until is null then 'observed'
    when v_until>clock_timestamp() then 'active'
    else 'expired'
  end;
  v_source_fingerprint := encode(
    extensions.digest(
      convert_to(v_source_system || '|' || v_source_message_id || '|' || v_sha,'UTF8'),
      'sha256'
    ),
    'hex'
  );

  insert into integration_control.penta_mail_provider_limit_notice_v1(
    source_system,source_message_id,sender,subject,received_at,
    observed_hourly_cap,provider_retry_after_seconds,
    gateway_multiplier,gateway_seconds,gateway_until,
    body_sha256,notice_state,evidence,updated_at
  ) values (
    v_source_system,v_source_message_id,left(coalesce(p_sender,''),320),
    left(coalesce(p_subject,''),500),v_received,
    v_cap,v_retry,1.00,v_gateway,v_until,v_sha,v_state,
    jsonb_build_object(
      'transport_owner','PentaMail',
      'control_plane','PentaMarketer',
      'gateway_rule','provider email seconds exactly',
      'crownthrive_temporary_hourly_authorization_ceiling',180,
      'provider_ceiling_remains_authoritative',true,
      'hard_hourly_limit_temporary',true,
      'crownthrive_static_hourly_limit_removed_after_gateway',true,
      'fresh_provider_readback_required_after_gateway',v_retry is not null,
      'source_fingerprint_sha256',v_source_fingerprint,
      'raw_body_retained_in_notice_table',false
    ),
    clock_timestamp()
  )
  on conflict (source_system,source_message_id) do nothing
  returning notice_id into v_notice_id;

  if v_notice_id is null then
    select * into v_existing
    from integration_control.penta_mail_provider_limit_notice_v1
    where source_system=v_source_system
      and source_message_id=v_source_message_id;
    if not found or v_existing.body_sha256<>v_sha or v_existing.received_at<>v_received then
      raise exception 'PENTAMAIL_PROVIDER_NOTICE_CONFLICT';
    end if;
    return jsonb_build_object(
      'accepted',true,'idempotent_replay',true,
      'notice_id',v_existing.notice_id,
      'notice_state',v_existing.notice_state,
      'observed_hourly_cap',v_existing.observed_hourly_cap,
      'provider_retry_after_seconds',v_existing.provider_retry_after_seconds,
      'gateway_multiplier',v_existing.gateway_multiplier,
      'gateway_seconds',v_existing.gateway_seconds,
      'gateway_until',v_existing.gateway_until,
      'source_message_id',v_existing.source_message_id
    );
  end if;

  select n.notice_id=v_notice_id into v_is_latest
  from integration_control.penta_mail_provider_limit_notice_v1 n
  where n.provider_route_id='mailgun:relay.crownthrive.com'
  order by n.received_at desc,n.created_at desc,n.notice_id desc
  limit 1;

  if coalesce(v_is_latest,false) then
    update integration_control.penta_mail_growth_policy_v1
    set crownthrive_hourly_hard_cap=180,
        metadata=(coalesce(metadata,'{}'::jsonb)-'adaptive_provider_gateway')
          || jsonb_build_object(
            'adaptive_rate_mode','provider_email_seconds_then_remove_crownthrive_static_hourly_cap',
            'fixed_hourly_hard_cap_deprecated',true,
            'provider_throttle_evasion_forbidden',true,
            'adaptive_provider_gateway',jsonb_build_object(
              'source_system',v_source_system,
              'source_message_id',v_source_message_id,
              'observed_hourly_cap',v_cap,
              'provider_retry_after_seconds',v_retry,
              'gateway_multiplier',1,
              'gateway_seconds',v_gateway,
              'gateway_until',v_until,
              'notice_state',v_state,
              'crownthrive_temporary_hourly_authorization_ceiling',180,
              'provider_ceiling_remains_authoritative',true,
              'fresh_provider_readback_required_after_gateway',v_retry is not null,
              'rule','Mailgun email seconds are the exact timed gateway; CrownThrive temporary authorization ceiling is 180/hour; the CrownThrive static cap is removed after the gateway while provider limits remain authoritative'
            ),
            'provider_probation_observed_hourly_cap',
              coalesce(v_cap,provider_hourly_hard_cap),
            'provider_probation_observed_disable_seconds',v_retry
          ),
        updated_at=clock_timestamp()
    where policy_key='mailgun-foundation-growth-v1';

    if v_until is not null then
      update integration_control.penta_mail_provider_control_v1
      set state='awaiting_provider_readback',
          readback_required_after=greatest(hold_until,v_until),
          enabled_readback_at=null,
          last_readback_at=null,
          last_readback_enabled=null,
          last_readback_http_status=null,
          last_readback_sha256=null,
          last_readback_probe_started_at=null,
          readback_probe_generation=readback_probe_generation+1,
          active_readback_probe_id=null,
          active_readback_probe_generation=null,
          active_readback_probe_started_at=null,
          active_readback_probe_expires_at=null,
          updated_at=clock_timestamp()
      where provider_route_id='mailgun:relay.crownthrive.com';
      if not found then
        raise exception 'PENTAMAIL_PROVIDER_CONTROL_MISSING';
      end if;
    end if;
  end if;

  select active_incident_id into v_active_incident_id
  from integration_control.penta_mail_provider_control_v1
  where provider_route_id='mailgun:relay.crownthrive.com';

  perform integration_control.penta_mail_append_control_event_v1(
    'provider-limit-notice:' || left(v_source_fingerprint,64),
    'mailgun.provider_limit_notice.ingested',
    v_active_incident_id,
    null,
    jsonb_build_object(
      'notice_id',v_notice_id,
      'source_system',v_source_system,
      'source_message_id',v_source_message_id,
      'sender',left(coalesce(p_sender,''),320),
      'subject',left(coalesce(p_subject,''),500),
      'received_at',v_received,
      'observed_hourly_cap',v_cap,
      'provider_retry_after_seconds',v_retry,
      'gateway_seconds',v_gateway,
      'gateway_until',v_until,
      'notice_state',v_state,
      'is_latest_authoritative_notice',coalesce(v_is_latest,false),
      'body_sha256',v_sha,
      'source_fingerprint_sha256',v_source_fingerprint,
      'crownthrive_temporary_hourly_authorization_ceiling',180,
      'provider_ceiling_remains_authoritative',true,
      'raw_provider_body_retained',false
    ),
    'ct-founder-directive-pentamail-adaptive-gateway-20260828-v2'
  );

  return jsonb_build_object(
    'accepted',true,
    'idempotent_replay',false,
    'notice_id',v_notice_id,
    'notice_state',v_state,
    'is_latest_authoritative_notice',coalesce(v_is_latest,false),
    'observed_hourly_cap',v_cap,
    'provider_retry_after_seconds',v_retry,
    'gateway_multiplier',1,
    'gateway_seconds',v_gateway,
    'gateway_until',v_until,
    'crownthrive_temporary_hourly_authorization_ceiling',180,
    'provider_ceiling_remains_authoritative',true,
    'crownthrive_static_hourly_limit_removed_after_gateway',true,
    'fresh_provider_readback_required_after_gateway',v_retry is not null,
    'source_message_id',v_source_message_id,
    'body_sha256',v_sha,
    'source_fingerprint_sha256',v_source_fingerprint
  );
end
$function$;

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
  v_gateway_active boolean:=false;
  v_crownthrive_temporary integer;
  v_provider_cap integer;
  v_effective_cap integer;
  v_batch integer:=2;
  v_rate_mode text;
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

  v_gateway_active:=found
    and v_notice.gateway_until is not null
    and v_notice.gateway_until>v_now;

  v_provider_cap:=case
    when found then nullif(v_notice.observed_hourly_cap,0)
    else null
  end;

  v_crownthrive_temporary:=case
    when v_gateway_active then coalesce(nullif(v_growth.crownthrive_hourly_hard_cap,0),180)
    else null
  end;

  v_effective_cap:=case
    when v_provider_cap is not null and v_crownthrive_temporary is not null
      then least(v_provider_cap,v_crownthrive_temporary)
    when v_provider_cap is not null then v_provider_cap
    when v_crownthrive_temporary is not null then v_crownthrive_temporary
    else null
  end;

  v_batch:=case
    when v_effective_cap is not null
      then greatest(1,ceil(v_effective_cap::numeric/60)::integer)
    else coalesce(nullif(v_growth.controlled_batch_per_minute,0),2)
  end;

  v_rate_mode:=case
    when v_gateway_active then 'temporary_provider_gateway'
    when v_provider_cap is not null then 'provider_adaptive_no_crownthrive_static_cap'
    else 'adaptive_no_hourly_hard_cap'
  end;

  return jsonb_build_object(
    'rate_mode',v_rate_mode,
    'gateway_active',v_gateway_active,
    'gateway_until',case when found then v_notice.gateway_until else null end,
    'gateway_seconds',case when found then v_notice.gateway_seconds else null end,
    'provider_retry_after_seconds',case when found then v_notice.provider_retry_after_seconds else null end,
    'gateway_multiplier',case when found then v_notice.gateway_multiplier else null end,
    'crownthrive_temporary_hourly_authorization_ceiling',v_crownthrive_temporary,
    'crownthrive_static_hourly_hard_cap',null,
    'crownthrive_static_hourly_hard_cap_removed',not v_gateway_active,
    'provider_observed_hourly_cap',v_provider_cap,
    'provider_limit_active',v_provider_cap is not null,
    'provider_ceiling_remains_authoritative',true,
    'effective_hourly_hard_cap',v_effective_cap,
    'temporary_hourly_hard_cap',v_effective_cap,
    'controlled_batch_per_minute',v_batch,
    'source_system',case when found then v_notice.source_system else null end,
    'source_message_id',case when found then v_notice.source_message_id else null end,
    'last_provider_notice_received_at',case when found then v_notice.received_at else null end,
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
  v_gateway_active boolean:=false;
  v_gateway_until timestamptz;
begin
  perform integration_control.penta_mail_assert_service_role_v1();

  v_rate:=public.penta_mail_effective_rate_policy_v1();
  v_gateway_active:=coalesce((v_rate->>'gateway_active')::boolean,false);
  v_gateway_until:=nullif(v_rate->>'gateway_until','')::timestamptz;

  select * into v_control
  from integration_control.penta_mail_provider_control_v1
  where provider_route_id='mailgun:relay.crownthrive.com';
  v_control_found:=found;

  if v_gateway_active then
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
      when v_gateway_active then v_gateway_until
      when v_control_found then v_control.hold_until
      else null
    end,
    'readback_required_after',case when v_control_found then v_control.readback_required_after else null end,
    'enabled_readback_at',case when v_control_found then v_control.enabled_readback_at else null end,
    'last_readback_at',case when v_control_found then v_control.last_readback_at else null end,
    'last_readback_enabled',case when v_control_found then v_control.last_readback_enabled else null end,
    'seconds_until_hold_boundary',case
      when v_gateway_active then greatest(0,ceil(extract(epoch from (v_gateway_until-v_now)))::integer)
      when v_control_found then greatest(0,ceil(extract(epoch from (coalesce(v_control.hold_until,v_now)-v_now)))::integer)
      else 0
    end,
    'provider_readback_required',v_state='awaiting_provider_readback',
    'trigger_ref',p_trigger_ref,
    'trigger_state',case when v_probation_until is not null then 'probation' else 'eligible' end,
    'trigger_probation_until',v_probation_until,
    'controlled_batch_size',coalesce((v_rate->>'controlled_batch_per_minute')::integer,2),
    'rolling_hour_limit',nullif(v_rate->>'effective_hourly_hard_cap','')::integer,
    'effective_hourly_hard_cap',nullif(v_rate->>'effective_hourly_hard_cap','')::integer,
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
      when received_at+make_interval(secs=>provider_retry_after_seconds)>clock_timestamp() then 'active'
      else 'expired'
    end,
    evidence=(coalesce(evidence,'{}'::jsonb)
      -'gateway_rule'
      -'hard_hourly_limit_temporary'
      -'hourly_hard_limit_removed_after_gateway')
      || jsonb_build_object(
        'gateway_rule','provider email seconds exactly',
        'crownthrive_temporary_hourly_authorization_ceiling',180,
        'provider_ceiling_remains_authoritative',true,
        'hard_hourly_limit_temporary',true,
        'crownthrive_static_hourly_limit_removed_after_gateway',true,
        'fresh_provider_readback_required_after_gateway',provider_retry_after_seconds is not null,
        'corrected_by','ct-founder-directive-pentamail-adaptive-gateway-20260828-v2'
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
set crownthrive_hourly_hard_cap=180,
    metadata=(coalesce(g.metadata,'{}'::jsonb)-'adaptive_provider_gateway')
      || jsonb_build_object(
        'adaptive_rate_mode','provider_email_seconds_then_remove_crownthrive_static_hourly_cap',
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
          'fresh_provider_readback_required_after_gateway',l.provider_retry_after_seconds is not null,
          'rule','Mailgun email seconds are the exact timed gateway; CrownThrive temporary authorization ceiling is 180/hour; the CrownThrive static cap is removed after the gateway while provider limits remain authoritative'
        ),
        'provider_probation_observed_hourly_cap',
          coalesce(l.observed_hourly_cap,g.provider_hourly_hard_cap),
        'provider_probation_observed_disable_seconds',l.provider_retry_after_seconds
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

do $block$
declare
  v_notice integration_control.penta_mail_provider_limit_notice_v1%rowtype;
  v_incident_id uuid;
begin
  select * into v_notice
  from integration_control.penta_mail_provider_limit_notice_v1
  where provider_route_id='mailgun:relay.crownthrive.com'
  order by received_at desc,created_at desc,notice_id desc
  limit 1;

  if found then
    select active_incident_id into v_incident_id
    from integration_control.penta_mail_provider_control_v1
    where provider_route_id='mailgun:relay.crownthrive.com';

    perform integration_control.penta_mail_append_control_event_v1(
      'provider-limit-notice:' || v_notice.notice_id::text || ':semantics-v2',
      'mailgun.provider_limit_notice.semantics_corrected',
      v_incident_id,
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
        'crownthrive_temporary_hourly_authorization_ceiling',180,
        'provider_ceiling_remains_authoritative',true,
        'fresh_provider_readback_required_after_gateway',true,
        'body_sha256',v_notice.body_sha256,
        'raw_provider_body_retained',false
      ),
      'ct-founder-directive-pentamail-adaptive-gateway-20260828-v2'
    );
  end if;
end
$block$;

comment on function public.penta_mail_ingest_provider_limit_notice_v1(
  text,text,text,text,text,timestamptz,text
) is
'Service-role-only authenticated Mailgun notice intake. Uses provider email seconds exactly as the timed gateway, records fingerprints/DAIL evidence, sets a temporary CrownThrive 180/hour authorization ceiling, and requires a fresh post-gateway provider readback.';

comment on function public.penta_mail_effective_rate_policy_v1() is
'Provider-adaptive PentaMail rate policy. Removes CrownThrive static hourly hard cap after the gateway while preserving provider-advertised ceilings and dynamic minute burst controls.';

comment on function public.penta_mail_provider_status_v1(text) is
'PentaMail provider/readback status including exact email gateway, provider-aware effective rate, temporary CrownThrive ceiling, and static-cap expiry state.';

commit;
