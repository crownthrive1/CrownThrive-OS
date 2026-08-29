begin;

create or replace function public.penta_mail_growth_reserve_v1(
  p_request_key text,
  p_persona_id text,
  p_agent_id text,
  p_channel_key text,
  p_recipient_sha256 text default null
)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,crm,public,pg_temp
as $$
declare
  v_policy integration_control.penta_mail_growth_policy_v1%rowtype;
  v_identity crm.penta_marketer_sender_identities_v1%rowtype;
  v_channel integration_control.penta_mail_growth_channel_budget_v1%rowtype;
  v_pool jsonb;
  v_now timestamptz:=clock_timestamp();
  v_local timestamp;
  v_month_start timestamptz;
  v_day_start timestamptz;
  v_persona_month integer;
  v_persona_hour integer;
  v_shared_month integer;
  v_channel_month integer;
  v_channel_day integer;
  v_total_month integer;
  v_sanction_until timestamptz;
  v_quota_source text;
  v_pool_available integer;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  if length(coalesce(p_request_key,''))=0 or length(p_request_key)>240 then
    raise exception 'PENTAMAIL_GROWTH_INVALID_REQUEST_KEY';
  end if;
  if coalesce(p_persona_id,'')='' then
    return jsonb_build_object('allowed',false,'reason','persona_required');
  end if;

  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:growth-governor'));

  if exists(
    select 1
    from integration_control.penta_mail_growth_reservations_v1
    where request_key=p_request_key and released_at is null
  ) then
    return jsonb_build_object('allowed',false,'reason','request_already_reserved');
  end if;

  select * into v_policy
  from integration_control.penta_mail_growth_policy_v1
  where policy_key='mailgun-foundation-growth-v1' and state='active';
  if not found then return jsonb_build_object('allowed',false,'reason','growth_policy_hold'); end if;

  select * into v_identity
  from crm.penta_marketer_sender_identities_v1
  where persona_id=p_persona_id;
  if not found or v_identity.identity_state in ('hold','retired') then
    return jsonb_build_object('allowed',false,'reason','sender_identity_hold');
  end if;

  select * into v_channel
  from integration_control.penta_mail_growth_channel_budget_v1
  where channel_key=p_channel_key and state='active';
  if not found then return jsonb_build_object('allowed',false,'reason','growth_channel_hold'); end if;

  select max(sanction_until) into v_sanction_until
  from integration_control.penta_mail_sender_sanctions_v1
  where persona_id=p_persona_id and sanction_until>v_now;
  if v_identity.timeout_until>v_now then
    v_sanction_until:=greatest(coalesce(v_sanction_until,v_identity.timeout_until),v_identity.timeout_until);
  end if;
  if v_sanction_until is not null and v_sanction_until>v_now then
    return jsonb_build_object('allowed',false,'reason','sender_timeout','retry_at',v_sanction_until);
  end if;

  v_local:=v_now at time zone v_policy.timezone;
  if extract(hour from v_local)::integer < v_policy.send_start_hour
     or extract(hour from v_local)::integer >= v_policy.send_end_hour then
    return jsonb_build_object(
      'allowed',false,
      'reason','outside_working_hours',
      'timezone',v_policy.timezone,
      'send_start_hour',v_policy.send_start_hour,
      'send_end_hour',v_policy.send_end_hour,
      'retry_policy','next working window'
    );
  end if;

  v_pool:=public.penta_mail_pool_status_v2();
  if v_pool->>'state'='HOLD' then
    return jsonb_build_object('allowed',false,'reason','pentamailer_pool_hold','pool',v_pool);
  end if;
  if coalesce((v_pool#>>'{dynamic,global_remaining}')::integer,0)<=0 then
    return jsonb_build_object('allowed',false,'reason','pentamailer_40k_pool_exhausted','pool',v_pool);
  end if;

  if p_channel_key='cold_outreach' then
    v_pool_available:=coalesce((v_pool#>>'{dynamic,locticians_available_now}')::integer,0);
    if v_pool_available<=0 then
      return jsonb_build_object('allowed',false,'reason','locticians_dynamic_pool_or_daily_cap','pool',v_pool);
    end if;
  else
    v_pool_available:=coalesce((v_pool#>>'{dynamic,other_marketing_available_now}')::integer,0);
    if v_pool_available<=0 then
      return jsonb_build_object('allowed',false,'reason','other_marketing_dynamic_residual_exhausted','pool',v_pool);
    end if;
  end if;

  v_month_start:=(date_trunc('month',v_local) at time zone v_policy.timezone);
  v_day_start:=(date_trunc('day',v_local) at time zone v_policy.timezone);

  select count(*)::integer into v_persona_month
  from integration_control.penta_mail_growth_reservations_v1
  where persona_id=p_persona_id and released_at is null and reserved_at>=v_month_start;

  select count(*)::integer into v_persona_hour
  from integration_control.penta_mail_growth_reservations_v1
  where persona_id=p_persona_id and released_at is null and reserved_at>v_now-interval '1 hour';

  select count(*)::integer into v_shared_month
  from integration_control.penta_mail_growth_reservations_v1
  where quota_source='shared_reserve' and released_at is null and reserved_at>=v_month_start;

  select count(*)::integer into v_channel_month
  from integration_control.penta_mail_growth_reservations_v1
  where channel_key=p_channel_key and released_at is null and reserved_at>=v_month_start;

  select count(*)::integer into v_channel_day
  from integration_control.penta_mail_growth_reservations_v1
  where channel_key=p_channel_key and released_at is null and reserved_at>=v_day_start;

  select count(*)::integer into v_total_month
  from integration_control.penta_mail_growth_reservations_v1
  where released_at is null and reserved_at>=v_month_start;

  if v_total_month>=v_policy.marketing_monthly_cap then
    return jsonb_build_object(
      'allowed',false,'reason','marketing_nominal_monthly_cap',
      'used',v_total_month,'cap',v_policy.marketing_monthly_cap,'pool',v_pool
    );
  end if;

  if v_channel_month>=v_channel.monthly_cap then
    return jsonb_build_object(
      'allowed',false,'reason','channel_monthly_cap','channel',p_channel_key,
      'used',v_channel_month,'cap',v_channel.monthly_cap,'pool',v_pool
    );
  end if;

  if v_channel_day>=v_channel.daily_soft_cap then
    return jsonb_build_object(
      'allowed',false,'reason','channel_daily_soft_cap','channel',p_channel_key,
      'used',v_channel_day,'cap',v_channel.daily_soft_cap,'pool',v_pool
    );
  end if;

  if v_persona_hour>=v_identity.hourly_soft_cap then
    insert into integration_control.penta_mail_sender_sanctions_v1(
      persona_id,agent_id,reason_code,strike_count,sanction_until,evidence
    ) values(
      p_persona_id,p_agent_id,'persona_hourly_soft_cap_abuse',1,
      v_now+make_interval(secs=>v_policy.abuse_timeout_seconds),
      jsonb_build_object('hour_count',v_persona_hour,'hourly_soft_cap',v_identity.hourly_soft_cap)
    );
    update crm.penta_marketer_sender_identities_v1
    set identity_state='timeout',
        timeout_until=v_now+make_interval(secs=>v_policy.abuse_timeout_seconds),
        updated_at=v_now
    where persona_id=p_persona_id;
    return jsonb_build_object(
      'allowed',false,
      'reason','persona_hourly_soft_cap_timeout',
      'retry_at',v_now+make_interval(secs=>v_policy.abuse_timeout_seconds)
    );
  end if;

  if v_persona_month < v_identity.monthly_quota then
    v_quota_source:='persona';
  elsif v_shared_month < v_policy.shared_marketing_reserve then
    v_quota_source:='shared_reserve';
  else
    return jsonb_build_object(
      'allowed',false,
      'reason','persona_and_shared_quota_exhausted',
      'persona_used',v_persona_month,
      'persona_cap',v_identity.monthly_quota,
      'shared_used',v_shared_month,
      'shared_cap',v_policy.shared_marketing_reserve,
      'pool',v_pool
    );
  end if;

  insert into integration_control.penta_mail_growth_reservations_v1(
    request_key,persona_id,channel_key,recipient_sha256,quota_source,
    reserved_at,metadata,accepted_at,released_at,release_reason
  ) values(
    p_request_key,p_persona_id,p_channel_key,p_recipient_sha256,v_quota_source,v_now,
    jsonb_build_object(
      'agent_id',p_agent_id,
      'working_timezone',v_policy.timezone,
      'pool_policy','ct.pentamailer.pool.40k.v1',
      'dynamic_pool_available_at_reserve',v_pool_available
    ),
    null,null,null
  )
  on conflict(request_key) do update set
    persona_id=excluded.persona_id,
    channel_key=excluded.channel_key,
    recipient_sha256=excluded.recipient_sha256,
    quota_source=excluded.quota_source,
    reserved_at=excluded.reserved_at,
    metadata=excluded.metadata,
    accepted_at=null,
    released_at=null,
    release_reason=null;

  return jsonb_build_object(
    'allowed',true,
    'quota_source',v_quota_source,
    'persona_id',p_persona_id,
    'channel',p_channel_key,
    'identity',v_identity.email_address,
    'display_name',v_identity.display_name,
    'reply_to',v_identity.reply_to,
    'marketing_month_reserved',v_total_month+1,
    'marketing_nominal_cap',v_policy.marketing_monthly_cap,
    'persona_month_reserved',v_persona_month+1,
    'persona_month_soft_quota',v_identity.monthly_quota,
    'shared_marketing_reserved',case when v_quota_source='shared_reserve' then v_shared_month+1 else v_shared_month end,
    'shared_marketing_cap',v_policy.shared_marketing_reserve,
    'channel_day_reserved',v_channel_day+1,
    'channel_daily_soft_cap',v_channel.daily_soft_cap,
    'pool',v_pool
  );
end;
$$;

commit;
