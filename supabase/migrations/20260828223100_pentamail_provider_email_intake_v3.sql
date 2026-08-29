-- CrownThrive OS / PentaMail
-- Authenticated Mailgun email intake: exact email seconds, idempotent evidence,
-- temporary 180/hour CrownThrive authorization, provider-aware enforcement.

begin;

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
  v_text text:=lower(coalesce(p_subject,'')||E'\n'||coalesce(p_body_text,''));
  v_cap_match text[];
  v_seconds_match text[];
  v_cap integer;
  v_seconds integer;
  v_received timestamptz:=coalesce(p_received_at,clock_timestamp());
  v_gateway_until timestamptz;
  v_notice_state text;
  v_sender text:=lower(btrim(coalesce(p_sender,'')));
  v_source_system text:=lower(btrim(coalesce(p_source_system,'')));
  v_source_message_id text:=btrim(coalesce(p_source_message_id,''));
  v_body_sha text;
  v_fingerprint text;
  v_notice_id uuid;
  v_existing integration_control.penta_mail_provider_limit_notice_v1%rowtype;
  v_is_latest boolean:=false;
  v_incident uuid;
begin
  perform integration_control.penta_mail_assert_service_role_v1();

  if v_source_system='' or v_source_message_id='' then
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

  v_body_sha:=coalesce(
    nullif(lower(btrim(coalesce(p_body_sha256,''))),'') ,
    encode(
      extensions.digest(convert_to(coalesce(p_body_text,''),'UTF8'),'sha256'),
      'hex'
    )
  );
  if v_body_sha!~'^[0-9a-f]{64}$' then
    raise exception 'PENTAMAIL_PROVIDER_NOTICE_INVALID_SHA256';
  end if;

  select * into v_existing
  from integration_control.penta_mail_provider_limit_notice_v1
  where source_system=v_source_system
    and source_message_id=v_source_message_id;

  if found then
    if v_existing.body_sha256<>v_body_sha
      or v_existing.received_at<>v_received then
      raise exception 'PENTAMAIL_PROVIDER_NOTICE_CONFLICT';
    end if;
    return jsonb_build_object(
      'accepted',true,
      'idempotent_replay',true,
      'notice_id',v_existing.notice_id,
      'source_message_id',v_existing.source_message_id,
      'received_at',v_existing.received_at,
      'observed_hourly_cap',v_existing.observed_hourly_cap,
      'provider_retry_after_seconds',v_existing.provider_retry_after_seconds,
      'gateway_multiplier',v_existing.gateway_multiplier,
      'gateway_seconds',v_existing.gateway_seconds,
      'gateway_until',v_existing.gateway_until,
      'notice_state',case
        when v_existing.gateway_until is null then 'observed'
        when v_existing.gateway_until>clock_timestamp() then 'active'
        else 'expired'
      end,
      'configured_temporary_authorization_ceiling',180,
      'provider_ceiling_remains_authoritative',true
    );
  end if;

  select regexp_match(
    v_text,
    'limited to[^0-9]{0,40}([0-9]{1,6})[[:space:]]+messages?[[:space:]]*(/|per)[[:space:]]*hour'
  ) into v_cap_match;
  if v_cap_match is not null then
    v_cap:=greatest(1,least(v_cap_match[1]::integer,1000000));
  end if;

  select regexp_match(
    v_text,
    'enabled[^0-9]{0,40}([0-9]{1,6})[[:space:]]+seconds?'
  ) into v_seconds_match;
  if v_seconds_match is null then
    select regexp_match(
      v_text,
      'retry-after[^0-9]{0,20}([0-9]{1,6})'
    ) into v_seconds_match;
  end if;
  if v_seconds_match is null then
    select regexp_match(
      v_text,
      'retry[^0-9]{0,40}([0-9]{1,6})[[:space:]]+seconds?'
    ) into v_seconds_match;
  end if;
  if v_seconds_match is null then
    select regexp_match(
      v_text,
      'in[[:space:]]+([0-9]{1,6})[[:space:]]+seconds?'
    ) into v_seconds_match;
  end if;
  if v_seconds_match is not null then
    v_seconds:=greatest(1,least(v_seconds_match[1]::integer,86400));
  end if;

  if v_cap is null and v_seconds is null then
    return jsonb_build_object(
      'accepted',false,
      'reason','no_rate_or_gateway_signal'
    );
  end if;

  v_gateway_until:=case
    when v_seconds is null then null
    else v_received+make_interval(secs=>v_seconds)
  end;
  v_notice_state:=case
    when v_gateway_until is null then 'observed'
    when v_gateway_until>clock_timestamp() then 'active'
    else 'expired'
  end;
  v_fingerprint:=encode(
    extensions.digest(
      convert_to(v_source_system||'|'||v_source_message_id||'|'||v_body_sha,'UTF8'),
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
    v_source_system,v_source_message_id,left(p_sender,320),
    left(coalesce(p_subject,''),500),v_received,
    v_cap,v_seconds,1.00,v_seconds,v_gateway_until,
    v_body_sha,v_notice_state,
    jsonb_build_object(
      'transport_owner','PentaMail',
      'control_plane','PentaMarketer',
      'gateway_rule','provider email seconds exactly',
      'configured_temporary_authorization_ceiling',180,
      'provider_ceiling_remains_authoritative',true,
      'crownthrive_static_hourly_limit_removed_after_gateway',true,
      'fresh_provider_readback_required_after_gateway',v_seconds is not null,
      'source_fingerprint_sha256',v_fingerprint,
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
    if not found or v_existing.body_sha256<>v_body_sha
      or v_existing.received_at<>v_received then
      raise exception 'PENTAMAIL_PROVIDER_NOTICE_CONFLICT';
    end if;
    return jsonb_build_object(
      'accepted',true,'idempotent_replay',true,
      'notice_id',v_existing.notice_id,
      'source_message_id',v_existing.source_message_id,
      'gateway_seconds',v_existing.gateway_seconds,
      'gateway_until',v_existing.gateway_until
    );
  end if;

  select n.notice_id=v_notice_id into v_is_latest
  from integration_control.penta_mail_provider_limit_notice_v1 n
  where n.provider_route_id='mailgun:relay.crownthrive.com'
  order by n.received_at desc,n.created_at desc,n.notice_id desc
  limit 1;

  if coalesce(v_is_latest,false) then
    update integration_control.penta_mail_growth_policy_v1
    set crownthrive_hourly_hard_cap=provider_hourly_hard_cap,
        crownthrive_temporary_authorization_ceiling=180,
        metadata=(coalesce(metadata,'{}'::jsonb)-'adaptive_provider_gateway')
          ||jsonb_build_object(
            'adaptive_rate_mode',
              'provider_email_seconds_then_remove_crownthrive_static_hourly_cap',
            'provider_throttle_evasion_forbidden',true,
            'fixed_hourly_hard_cap_deprecated',true,
            'adaptive_provider_gateway',jsonb_build_object(
              'source_system',v_source_system,
              'source_message_id',v_source_message_id,
              'observed_hourly_cap',v_cap,
              'provider_retry_after_seconds',v_seconds,
              'gateway_multiplier',1,
              'gateway_seconds',v_seconds,
              'gateway_until',v_gateway_until,
              'notice_state',v_notice_state,
              'configured_temporary_authorization_ceiling',180,
              'provider_ceiling_remains_authoritative',true,
              'fresh_provider_readback_required_after_gateway',
                v_seconds is not null,
              'rule',
                'Mailgun email seconds are the exact gateway; CrownThrive temporary authorization is 180/hour; CrownThrive static cap expires after the gateway; provider limits remain authoritative'
            ),
            'provider_probation_observed_hourly_cap',
              coalesce(v_cap,provider_hourly_hard_cap),
            'provider_probation_observed_disable_seconds',v_seconds
          ),
        updated_at=clock_timestamp()
    where policy_key='mailgun-foundation-growth-v1';

    if v_gateway_until is not null then
      update integration_control.penta_mail_provider_control_v1
      set state='awaiting_provider_readback',
          readback_required_after=greatest(hold_until,v_gateway_until),
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

  select active_incident_id into v_incident
  from integration_control.penta_mail_provider_control_v1
  where provider_route_id='mailgun:relay.crownthrive.com';

  perform integration_control.penta_mail_append_control_event_v1(
    'provider-limit-notice:'||v_fingerprint,
    'mailgun.provider_limit_notice.ingested',
    v_incident,
    null,
    jsonb_build_object(
      'notice_id',v_notice_id,
      'source_system',v_source_system,
      'source_message_id',v_source_message_id,
      'received_at',v_received,
      'observed_hourly_cap',v_cap,
      'provider_retry_after_seconds',v_seconds,
      'gateway_seconds',v_seconds,
      'gateway_until',v_gateway_until,
      'notice_state',v_notice_state,
      'is_latest_authoritative_notice',coalesce(v_is_latest,false),
      'body_sha256',v_body_sha,
      'source_fingerprint_sha256',v_fingerprint,
      'configured_temporary_authorization_ceiling',180,
      'provider_ceiling_remains_authoritative',true,
      'raw_provider_body_retained',false
    ),
    'ct-founder-directive-pentamail-adaptive-gateway-20260828-v3'
  );

  return jsonb_build_object(
    'accepted',true,
    'idempotent_replay',false,
    'notice_id',v_notice_id,
    'source_message_id',v_source_message_id,
    'received_at',v_received,
    'notice_state',v_notice_state,
    'is_latest_authoritative_notice',coalesce(v_is_latest,false),
    'observed_hourly_cap',v_cap,
    'provider_retry_after_seconds',v_seconds,
    'gateway_multiplier',1,
    'gateway_seconds',v_seconds,
    'gateway_until',v_gateway_until,
    'configured_temporary_authorization_ceiling',180,
    'provider_ceiling_remains_authoritative',true,
    'crownthrive_static_hourly_limit_removed_after_gateway',true,
    'fresh_provider_readback_required_after_gateway',v_seconds is not null,
    'body_sha256',v_body_sha,
    'source_fingerprint_sha256',v_fingerprint
  );
end
$function$;

comment on function public.penta_mail_ingest_provider_limit_notice_v1(
  text,text,text,text,text,timestamptz,text
) is
'Service-role-only Mailgun notice intake. Uses authenticated email seconds exactly as the timed gateway; records source ID, SHA-256, DAIL evidence; configures temporary 180/hour CrownThrive authorization; preserves provider ceilings; and requires fresh provider readback.';

commit;