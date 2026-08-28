CREATE OR REPLACE FUNCTION public.penta_mail_provider_status_v1(p_trigger_ref text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'integration_control'
AS $function$
declare
  v_control integration_control.penta_mail_provider_control_v1%rowtype;
  v_probation_until timestamptz;
  v_now timestamptz := clock_timestamp();
  v_state text;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  select * into v_control
  from integration_control.penta_mail_provider_control_v1
  where provider_route_id = 'mailgun:relay.crownthrive.com';
  if not found then
    v_state := 'closed';
  elsif v_now < v_control.hold_until then
    v_state := 'open';
  elsif v_control.state <> 'controlled_release'
    or v_control.last_readback_enabled is not true
    or v_control.enabled_readback_at is null
    or v_control.enabled_readback_at < v_control.readback_required_after
    or v_control.last_readback_at is distinct from v_control.enabled_readback_at then
    v_state := 'awaiting_provider_readback';
  else
    v_state := 'controlled_release';
  end if;
  if nullif(btrim(coalesce(p_trigger_ref, '')), '') is not null then
    select probation_until into v_probation_until
    from integration_control.penta_mail_trigger_probation_v1
    where trigger_ref = p_trigger_ref and probation_until > v_now;
  end if;
  return jsonb_build_object(
    'provider_route_id', 'mailgun:relay.crownthrive.com',
    'route_state', v_state,
    'active_incident_id', v_control.active_incident_id,
    'hold_until', v_control.hold_until,
    'readback_required_after', v_control.readback_required_after,
    'enabled_readback_at', v_control.enabled_readback_at,
    'last_readback_at', v_control.last_readback_at,
    'last_readback_enabled', v_control.last_readback_enabled,
    'seconds_until_hold_boundary', greatest(0, ceil(extract(epoch from (coalesce(v_control.hold_until, v_now) - v_now)))::integer),
    'provider_readback_required', v_state = 'awaiting_provider_readback',
    'trigger_ref', p_trigger_ref,
    'trigger_state', case when v_probation_until is not null then 'probation' else 'eligible' end,
    'trigger_probation_until', v_probation_until,
    'controlled_batch_size', 2,
    'rolling_hour_limit', 50,
    'policy_id', 'ct.pentamailer.policy.mailgun-delivery-resilience.v1',
    'policy_version', '1.1.0',
    'as_of', v_now
  );
end
$function$;

CREATE OR REPLACE FUNCTION public.penta_mail_reserve_mailgun_rate_v1(p_request_key text, p_trigger_ref text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'integration_control'
AS $function$
declare
  v_status jsonb;
  v_count integer;
  v_oldest timestamptz;
  v_now timestamptz := clock_timestamp();
  v_existing timestamptz;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform integration_control.penta_mail_reconcile_trigger_probation_v1();
  if length(coalesce(p_request_key, '')) = 0 or length(p_request_key) > 240 then
    raise exception 'PENTAMAIL_INVALID_RATE_REQUEST_KEY';
  end if;
  if coalesce(p_trigger_ref, '') !~ '^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$' then
    raise exception 'PENTAMAIL_INVALID_TRIGGER_REF';
  end if;
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:rolling-hour-rate'));
  v_status := public.penta_mail_provider_status_v1(p_trigger_ref);
  if v_status ->> 'route_state' <> 'controlled_release' and v_status ->> 'route_state' <> 'closed' then
    return jsonb_build_object(
      'allowed', false,
      'reason', 'provider_circuit_' || (v_status ->> 'route_state'),
      'retry_at', v_status ->> 'hold_until',
      'control', v_status
    );
  end if;
  if v_status ->> 'trigger_state' = 'probation' then
    return jsonb_build_object(
      'allowed', false,
      'reason', 'trigger_probation',
      'retry_at', v_status ->> 'trigger_probation_until',
      'control', v_status
    );
  end if;
  select reserved_at into v_existing
  from integration_control.penta_mail_rate_reservations_v1
  where provider_route_id = 'mailgun:relay.crownthrive.com' and request_key = p_request_key;
  if found then
    return jsonb_build_object('allowed', false, 'reason', 'request_already_reserved', 'reserved_at', v_existing);
  end if;
  select count(*)::integer, min(reserved_at)
  into v_count, v_oldest
  from integration_control.penta_mail_rate_reservations_v1
  where provider_route_id = 'mailgun:relay.crownthrive.com'
    and reserved_at > v_now - interval '1 hour';
  if v_count >= 50 then
    return jsonb_build_object(
      'allowed', false,
      'reason', 'rolling_hour_limit',
      'window_count', v_count,
      'rolling_hour_limit', 50,
      'retry_at', v_oldest + interval '1 hour'
    );
  end if;
  insert into integration_control.penta_mail_rate_reservations_v1(
    provider_route_id, request_key, trigger_ref, reserved_at
  ) values ('mailgun:relay.crownthrive.com', p_request_key, p_trigger_ref, v_now);
  return jsonb_build_object(
    'allowed', true,
    'window_count', v_count + 1,
    'remaining', 49 - v_count,
    'rolling_hour_limit', 50,
    'window_seconds', 3600,
    'reserved_at', v_now
  );
end
$function$;

CREATE OR REPLACE FUNCTION public.penta_mail_reserve_mailgun_rate_v2(p_request_key text, p_trigger_ref text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public', 'integration_control'
AS $function$
declare
  v_status jsonb;
  v_batch_count integer;
  v_batch_oldest timestamptz;
  v_hour_count integer;
  v_hour_oldest timestamptz;
  v_is_founder_report boolean := coalesce(p_trigger_ref,'') in (
    'scheduled:penta-mail-state-architecture-report-v1',
    'penta-self-hourly-healing-v1'
  );
  v_is_priority_customer_reply boolean := lower(coalesce(p_trigger_ref,'')) ~ '^penta-marketer:[a-z0-9._-]+:(support_|customer_|member_|reply_)';
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  v_status:=public.penta_mail_provider_status_v1(p_trigger_ref);
  select count(*)::integer,min(reserved_at) into v_hour_count,v_hour_oldest
  from integration_control.penta_mail_rate_reservations_v1
  where provider_route_id='mailgun:relay.crownthrive.com' and reserved_at>clock_timestamp()-interval '1 hour';

  if not v_is_founder_report and not v_is_priority_customer_reply and v_hour_count>=49 then
    return jsonb_build_object('allowed',false,'reason','founder_report_capacity_reserved','window_count',v_hour_count,
      'rolling_hour_limit',50,'reserved_founder_report_slots',1,
      'retry_at',coalesce(v_hour_oldest+interval '1 hour',clock_timestamp()+interval '5 minutes'),'control',v_status);
  end if;

  if v_status->>'route_state'='controlled_release' then
    select count(*)::integer,min(reserved_at) into v_batch_count,v_batch_oldest
    from integration_control.penta_mail_rate_reservations_v1
    where provider_route_id='mailgun:relay.crownthrive.com' and reserved_at>clock_timestamp()-interval '1 minute';
    if v_batch_count>=2 then
      return jsonb_build_object('allowed',false,'reason','controlled_release_batch_limit','window_count',v_batch_count,
        'controlled_batch_size',2,'retry_at',v_batch_oldest+interval '1 minute','control',v_status);
    end if;
  end if;
  return public.penta_mail_reserve_mailgun_rate_v1(p_request_key,p_trigger_ref);
end $function$;

CREATE OR REPLACE FUNCTION public.penta_mail_record_mailgun_readback_v1(p_readback_event_id text, p_enabled boolean, p_regular_disabled boolean, p_scheduled_disabled boolean, p_provider_http_status integer, p_response_sha256 text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public', 'integration_control'
AS $function$
declare
  v_control integration_control.penta_mail_provider_control_v1%rowtype;
  v_now timestamptz := clock_timestamp();
  v_verified_enabled boolean;
  v_new_event boolean;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  if length(coalesce(p_readback_event_id, '')) = 0 or length(p_readback_event_id) > 240 then
    raise exception 'PENTAMAIL_INVALID_READBACK_EVENT_ID';
  end if;
  if coalesce(p_response_sha256, '') !~ '^[0-9a-f]{64}$' then
    raise exception 'PENTAMAIL_INVALID_READBACK_SHA256';
  end if;
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:probation-control'));
  select * into v_control
  from integration_control.penta_mail_provider_control_v1
  where provider_route_id = 'mailgun:relay.crownthrive.com'
  for update;
  if not found then
    return public.penta_mail_provider_status_v1(null) || jsonb_build_object('readback_recorded', false, 'reason', 'no_active_control');
  end if;
  v_verified_enabled := coalesce(p_enabled, false)
    and coalesce(p_provider_http_status, 0) between 200 and 299
    and not coalesce(p_regular_disabled, true)
    and not coalesce(p_scheduled_disabled, true);
  v_new_event := integration_control.penta_mail_append_control_event_v1(
    'readback:' || p_readback_event_id,
    'mail.provider_readback',
    v_control.active_incident_id,
    null,
    jsonb_build_object(
      'provider_route_id', 'mailgun:relay.crownthrive.com',
      'enabled', v_verified_enabled,
      'regular_disabled', p_regular_disabled,
      'scheduled_disabled', p_scheduled_disabled,
      'provider_http_status', p_provider_http_status,
      'response_sha256', p_response_sha256,
      'raw_provider_body_retained', false
    ),
    'ct-founder-directive-pentamail-provider-probation-20260826-v1'
  );
  if not v_new_event then
    return public.penta_mail_provider_status_v1(null) || jsonb_build_object('readback_recorded', false, 'idempotent_replay', true);
  end if;
  update integration_control.penta_mail_provider_control_v1
  set last_readback_at = v_now,
      last_readback_enabled = v_verified_enabled,
      last_readback_http_status = p_provider_http_status,
      last_readback_sha256 = p_response_sha256,
      enabled_readback_at = case
        when v_verified_enabled and v_now >= readback_required_after then v_now
        else enabled_readback_at
      end,
      state = case
        when v_now < hold_until then 'open'
        when v_verified_enabled and v_now >= readback_required_after then 'controlled_release'
        else 'awaiting_provider_readback'
      end,
      updated_at = v_now
  where provider_route_id = 'mailgun:relay.crownthrive.com';
  if v_verified_enabled and v_now >= v_control.readback_required_after then
    update public.penta_mail_outbox_v1 o
    set state = case when exists (
          select 1 from integration_control.penta_mail_trigger_probation_v1 p
          where p.trigger_ref = o.trigger_ref and p.probation_until > v_now
        ) then 'held' else 'queued' end,
        available_at = case when exists (
          select 1 from integration_control.penta_mail_trigger_probation_v1 p
          where p.trigger_ref = o.trigger_ref and p.probation_until > v_now
        ) then greatest(o.available_at, (
          select p.probation_until from integration_control.penta_mail_trigger_probation_v1 p
          where p.trigger_ref = o.trigger_ref
        )) else greatest(o.available_at, v_now) end,
        metadata = o.metadata || jsonb_build_object(
          'provider_release_readback_at', v_now,
          'provider_release_readback_sha256', p_response_sha256,
          'provider_release_mode', 'controlled'
        ),
        updated_at = v_now
    where o.state = 'held'
      and o.metadata ->> 'provider_hold_policy' = 'ct.pentamailer.policy.mailgun-delivery-resilience.v1@1.0.0';
    perform integration_control.penta_mail_append_control_event_v1(
      'readback:' || p_readback_event_id || ':controlled-release',
      'mail.controlled_release_started',
      v_control.active_incident_id,
      null,
      jsonb_build_object('batch_size', 2, 'rolling_hour_limit', 50, 'enabled_readback_at', v_now),
      'ct-founder-directive-pentamail-provider-probation-20260826-v1'
    );
  end if;
  return public.penta_mail_provider_status_v1(null) || jsonb_build_object('readback_recorded', true, 'verified_enabled', v_verified_enabled);
end
$function$;

NOTIFY pgrst, 'reload schema';
