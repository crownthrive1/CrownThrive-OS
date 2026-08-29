create or replace function public.penta_mail_reserve_mailgun_rate_v2(p_request_key text, p_trigger_ref text)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','public','integration_control'
as $function$
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

  if not v_is_founder_report and not v_is_priority_customer_reply and v_hour_count>=9 then
    return jsonb_build_object('allowed',false,'reason','founder_report_capacity_reserved','window_count',v_hour_count,
      'rolling_hour_limit',10,'reserved_founder_report_slots',1,
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
