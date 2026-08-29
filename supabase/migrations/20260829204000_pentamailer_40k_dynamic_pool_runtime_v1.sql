begin;

create or replace function public.penta_mail_traffic_class_v2(p_message_type text,p_metadata jsonb)
returns text
language sql
immutable
as $$
  select case
    when lower(coalesce(p_metadata->>'traffic_class','')) in ('system_internal','support_transactional') then 'system_internal'
    when lower(coalesce(p_metadata->>'send_kind','')) in (
      'founder_receipt','system_receipt','system_alert','provider_alert','security_alert','transactional',
      'support_reply','inbound_reply','customer_support','delivery_receipt','certification_receipt','backup_receipt'
    ) then 'system_internal'
    when lower(coalesce(p_message_type,''))='locticians_claim'
      or coalesce(p_metadata->>'campaign_ref','')='ct.pentamarketer.locticians.claim.20260827.v1'
      or lower(coalesce(p_metadata->>'channel_key',''))='cold_outreach'
      then 'marketing_locticians'
    when lower(coalesce(p_metadata->>'traffic_class','')) in ('marketing','marketing_other') then 'marketing_other'
    when lower(coalesce(p_metadata->>'channel_key','')) in ('newsletter_nurture','content_distribution','experiments') then 'marketing_other'
    when lower(coalesce(p_message_type,'')) in ('sales_outreach','lead_nurture','newsletter','marketing','content_distribution','campaign') then 'marketing_other'
    when lower(coalesce(p_metadata->>'origin_penta',''))='pentamarketer'
      and lower(coalesce(p_metadata->>'recipient_scope',''))='governed_external'
      then 'marketing_other'
    else 'system_internal'
  end;
$$;

create or replace function public.penta_mail_pool_status_v2()
returns jsonb
language plpgsql
stable
security definer
set search_path=pg_catalog,public,integration_control,pg_temp
as $$
declare
  p integration_control.penta_mail_pool_policy_v2%rowtype;
  v_now timestamptz:=clock_timestamp();
  v_local timestamp;
  v_month_start timestamptz;
  v_day_start timestamptz;
  v_days_remaining integer;
  v_total_sent integer:=0;
  v_total_dispatching integer:=0;
  v_system_sent integer:=0;
  v_system_dispatching integer:=0;
  v_system_due_pending integer:=0;
  v_loct_sent integer:=0;
  v_loct_dispatching integer:=0;
  v_loct_today integer:=0;
  v_other_sent integer:=0;
  v_other_dispatching integer:=0;
  v_total_committed integer;
  v_system_committed integer;
  v_marketing_committed integer;
  v_loct_committed integer;
  v_other_committed integer;
  v_global_remaining integer;
  v_effective_marketing_cap integer;
  v_marketing_remaining integer;
  v_loct_month_remaining integer;
  v_loct_day_remaining integer;
  v_loct_feasible_remaining integer;
  v_loct_protected_remaining integer;
  v_loct_available integer;
  v_other_available integer;
begin
  select * into p
  from integration_control.penta_mail_pool_policy_v2
  where policy_key='ct.pentamailer.pool.40k.v1' and state='active';
  if not found then return jsonb_build_object('state','HOLD','reason','pool_policy_missing'); end if;

  v_local:=v_now at time zone p.timezone;
  v_month_start:=(date_trunc('month',v_local) at time zone p.timezone);
  v_day_start:=(date_trunc('day',v_local) at time zone p.timezone);
  v_days_remaining:=greatest(1,((date_trunc('month',v_local)+interval '1 month')::date - v_local::date));

  select
    count(*) filter(where o.state='sent')::integer,
    count(*) filter(where o.state='dispatching' and coalesce(o.lease_expires_at,v_now+interval '1 second')>v_now)::integer,
    count(*) filter(where o.state='sent' and public.penta_mail_traffic_class_v2(o.message_type,o.metadata)='system_internal')::integer,
    count(*) filter(where o.state='dispatching' and coalesce(o.lease_expires_at,v_now+interval '1 second')>v_now and public.penta_mail_traffic_class_v2(o.message_type,o.metadata)='system_internal')::integer,
    count(*) filter(where o.state='sent' and public.penta_mail_traffic_class_v2(o.message_type,o.metadata)='marketing_locticians')::integer,
    count(*) filter(where o.state='dispatching' and coalesce(o.lease_expires_at,v_now+interval '1 second')>v_now and public.penta_mail_traffic_class_v2(o.message_type,o.metadata)='marketing_locticians')::integer,
    count(*) filter(where o.state='sent' and public.penta_mail_traffic_class_v2(o.message_type,o.metadata)='marketing_other')::integer,
    count(*) filter(where o.state='dispatching' and coalesce(o.lease_expires_at,v_now+interval '1 second')>v_now and public.penta_mail_traffic_class_v2(o.message_type,o.metadata)='marketing_other')::integer
  into v_total_sent,v_total_dispatching,v_system_sent,v_system_dispatching,
       v_loct_sent,v_loct_dispatching,v_other_sent,v_other_dispatching
  from public.penta_mail_outbox_v1 o
  where (o.state='sent' and coalesce(o.sent_at,o.updated_at)>=v_month_start)
     or (o.state='dispatching' and o.updated_at>=v_month_start);

  select count(*)::integer into v_system_due_pending
  from public.penta_mail_outbox_v1 o
  where o.state in ('queued','pending','retry')
    and o.available_at<=v_now
    and o.updated_at>=v_month_start
    and public.penta_mail_traffic_class_v2(o.message_type,o.metadata)='system_internal';

  select count(*)::integer into v_loct_today
  from public.penta_mail_outbox_v1 o
  where (
      (o.state='sent' and coalesce(o.sent_at,o.updated_at)>=v_day_start)
      or (
        o.state='dispatching'
        and coalesce(o.lease_expires_at,v_now+interval '1 second')>v_now
        and o.updated_at>=v_day_start
      )
    )
    and public.penta_mail_traffic_class_v2(o.message_type,o.metadata)='marketing_locticians';

  v_total_committed:=v_total_sent+v_total_dispatching;
  v_system_committed:=v_system_sent+v_system_dispatching;
  v_loct_committed:=v_loct_sent+v_loct_dispatching;
  v_other_committed:=v_other_sent+v_other_dispatching;
  v_marketing_committed:=v_loct_committed+v_other_committed;

  v_global_remaining:=greatest(0,p.operational_monthly_cap-v_total_committed);
  v_effective_marketing_cap:=greatest(0,least(
    p.marketing_nominal_monthly_cap,
    p.operational_monthly_cap-v_system_committed-v_system_due_pending
  ));
  v_marketing_remaining:=greatest(0,v_effective_marketing_cap-v_marketing_committed);
  v_loct_month_remaining:=greatest(0,p.locticians_monthly_cap-v_loct_committed);
  v_loct_day_remaining:=greatest(0,p.locticians_daily_cap-v_loct_today);
  v_loct_feasible_remaining:=v_loct_day_remaining + greatest(v_days_remaining-1,0)*p.locticians_daily_cap;
  v_loct_protected_remaining:=least(v_loct_month_remaining,v_loct_feasible_remaining);
  v_loct_available:=greatest(0,least(
    v_global_remaining,v_marketing_remaining,v_loct_month_remaining,v_loct_day_remaining
  ));
  v_other_available:=greatest(0,least(
    v_global_remaining,v_marketing_remaining-v_loct_protected_remaining
  ));

  return jsonb_build_object(
    'state',case when v_global_remaining=0 then 'POOL_EXHAUSTED' else 'ACTIVE' end,
    'policy_key',p.policy_key,
    'generation',p.generation,
    'timezone',p.timezone,
    'provider_plan_monthly_cap',p.provider_plan_monthly_cap,
    'operational_monthly_cap',p.operational_monthly_cap,
    'provider_headroom',p.provider_plan_monthly_cap-p.operational_monthly_cap,
    'system_internal_protected_monthly',p.system_internal_protected_monthly,
    'marketing_nominal_monthly_cap',p.marketing_nominal_monthly_cap,
    'locticians_monthly_cap',p.locticians_monthly_cap,
    'locticians_daily_cap',p.locticians_daily_cap,
    'other_marketing_nominal_monthly',p.other_marketing_nominal_monthly,
    'usage',jsonb_build_object(
      'total_sent',v_total_sent,
      'total_dispatching',v_total_dispatching,
      'total_committed',v_total_committed,
      'system_internal_sent',v_system_sent,
      'system_internal_dispatching',v_system_dispatching,
      'system_internal_committed',v_system_committed,
      'system_internal_due_pending',v_system_due_pending,
      'locticians_sent',v_loct_sent,
      'locticians_dispatching',v_loct_dispatching,
      'locticians_committed',v_loct_committed,
      'locticians_today_committed',v_loct_today,
      'other_marketing_sent',v_other_sent,
      'other_marketing_dispatching',v_other_dispatching,
      'other_marketing_committed',v_other_committed,
      'marketing_committed',v_marketing_committed
    ),
    'dynamic',jsonb_build_object(
      'global_remaining',v_global_remaining,
      'effective_marketing_cap',v_effective_marketing_cap,
      'marketing_remaining',v_marketing_remaining,
      'locticians_month_remaining',v_loct_month_remaining,
      'locticians_day_remaining',v_loct_day_remaining,
      'locticians_feasible_remaining',v_loct_feasible_remaining,
      'locticians_protected_remaining',v_loct_protected_remaining,
      'locticians_available_now',v_loct_available,
      'other_marketing_available_now',v_other_available,
      'days_remaining_in_month_including_today',v_days_remaining
    ),
    'precedence',jsonb_build_array(
      'system_internal','support_transactional','locticians_marketing','other_marketing'
    ),
    'system_internal_first_claim',true,
    'marketing_residual_dynamic',true,
    'observed_at',v_now
  );
end;
$$;
revoke all on function public.penta_mail_pool_status_v2() from public,anon,authenticated;
grant execute on function public.penta_mail_pool_status_v2() to service_role;

create or replace function public.penta_mail_pool_authorization_v2(p_message_id uuid)
returns jsonb
language plpgsql
stable
security definer
set search_path=pg_catalog,public,pg_temp
as $$
declare
  o public.penta_mail_outbox_v1%rowtype;
  v_class text;
  s jsonb;
  v_allowed boolean:=false;
  v_reason text;
begin
  select * into o from public.penta_mail_outbox_v1 where message_id=p_message_id;
  if not found then return jsonb_build_object('allowed',false,'reason','message_not_found'); end if;
  v_class:=public.penta_mail_traffic_class_v2(o.message_type,o.metadata);
  s:=public.penta_mail_pool_status_v2();
  if s->>'state'='HOLD' then
    return jsonb_build_object('allowed',false,'reason','pool_policy_hold','traffic_class',v_class,'pool',s);
  end if;
  if coalesce((s#>>'{dynamic,global_remaining}')::integer,0)<=0 then
    v_reason:='operational_40k_pool_exhausted';
  elsif v_class='system_internal' then
    v_allowed:=true;
  elsif v_class='marketing_locticians' then
    v_allowed:=coalesce((s#>>'{dynamic,locticians_available_now}')::integer,0)>0;
    if not v_allowed then v_reason:='locticians_dynamic_or_daily_cap'; end if;
  else
    v_allowed:=coalesce((s#>>'{dynamic,other_marketing_available_now}')::integer,0)>0;
    if not v_allowed then v_reason:='other_marketing_dynamic_residual_exhausted'; end if;
  end if;
  return jsonb_build_object(
    'allowed',v_allowed,'reason',v_reason,'traffic_class',v_class,'pool',s,'message_id',p_message_id
  );
end;
$$;
revoke all on function public.penta_mail_pool_authorization_v2(uuid) from public,anon,authenticated;
grant execute on function public.penta_mail_pool_authorization_v2(uuid) to service_role;

create or replace function public.penta_mail_claim_outbox_v2(p_limit integer default 2)
returns setof public.penta_mail_outbox_v1
language plpgsql
security definer
set search_path=pg_catalog,public,integration_control
as $$
declare
  v_status jsonb;
  v_pool jsonb;
  v_now timestamptz:=clock_timestamp();
  v_limit integer:=greatest(1,least(coalesce(p_limit,2),2));
  v_global integer;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform pg_advisory_xact_lock(hashtext('public.penta_mail_claim_outbox_v2'));
  perform integration_control.penta_mail_reconcile_trigger_probation_v1();
  v_status:=public.penta_mail_provider_status_v1(null);
  if v_status->>'route_state' not in ('closed','controlled_release') then return; end if;
  v_pool:=public.penta_mail_pool_status_v2();
  v_global:=coalesce((v_pool#>>'{dynamic,global_remaining}')::integer,0);
  v_limit:=least(v_limit,v_global);
  if v_limit<1 then return; end if;

  update public.penta_mail_outbox_v1 o
  set state='queued',
      available_at=greatest(o.available_at,v_now),
      metadata=o.metadata||jsonb_build_object(
        'provider_release_mode','controlled',
        'trigger_probation_expired_at',v_now
      ),
      updated_at=v_now
  where o.state='held'
    and lower(o.message_type) not in ('locticians_claim','sales_outreach','lead_nurture')
    and not (
      lower(coalesce(o.metadata->>'origin_penta',''))='pentamarketer'
      and lower(coalesce(o.metadata->>'recipient_scope',''))='governed_external'
    )
    and o.metadata->>'provider_hold_policy'='ct.pentamailer.policy.mailgun-delivery-resilience.v1@1.0.0'
    and not exists(
      select 1 from integration_control.penta_mail_trigger_probation_v1 p
      where p.trigger_ref=o.trigger_ref and p.probation_until>v_now
    );

  update public.penta_mail_outbox_v1 o
  set state='retry',
      lease_id=null,
      lease_expires_at=null,
      available_at=greatest(o.available_at,v_now),
      metadata=o.metadata||jsonb_build_object('lease_recovered_at',v_now),
      updated_at=v_now
  where o.state='dispatching'
    and lower(o.message_type) not in ('locticians_claim','sales_outreach','lead_nurture')
    and not (
      lower(coalesce(o.metadata->>'origin_penta',''))='pentamarketer'
      and lower(coalesce(o.metadata->>'recipient_scope',''))='governed_external'
    )
    and o.lease_expires_at<=v_now;

  return query
  with candidates as (
    select o.message_id
    from public.penta_mail_outbox_v1 o
    where o.state in ('queued','pending','retry')
      and o.available_at<=v_now
      and lower(o.message_type) not in ('locticians_claim','sales_outreach','lead_nurture')
      and not (
        lower(coalesce(o.metadata->>'origin_penta',''))='pentamarketer'
        and lower(coalesce(o.metadata->>'recipient_scope',''))='governed_external'
      )
      and not exists(
        select 1 from integration_control.penta_mail_trigger_probation_v1 p
        where p.trigger_ref=o.trigger_ref and p.probation_until>v_now
      )
    order by
      case when o.trigger_ref='scheduled:penta-mail-state-architecture-report-v1' then 0 else 1 end,
      case when o.trigger_ref='scheduled:penta-mail-state-architecture-report-v1' then o.created_at end desc,
      case upper(o.severity)
        when 'CRITICAL' then 1 when 'P0' then 1
        when 'HIGH' then 2 when 'P1' then 2
        when 'MEDIUM' then 3 when 'P2' then 3
        when 'INFO' then 4 when 'P3' then 4 else 5
      end,
      o.created_at asc
    for update skip locked
    limit v_limit
  ), leases as (
    select message_id,gen_random_uuid() lease_id from candidates
  )
  update public.penta_mail_outbox_v1 o
  set state='dispatching',
      lease_id=l.lease_id,
      lease_expires_at=v_now+interval '5 minutes',
      metadata=o.metadata||jsonb_build_object(
        'claimed_at',v_now,
        'claimed_by','PentaMail',
        'controlled_release_batch_limit',2,
        'pool_policy','ct.pentamailer.pool.40k.v1',
        'traffic_precedence','system_internal_first',
        'commercial_lane','governed_external_claimed_separately'
      ),
      updated_at=v_now
  from leases l
  where o.message_id=l.message_id
  returning o.*;
end;
$$;

create or replace function crm.penta_marketer_claim_outbox_v2(p_limit integer default 2)
returns setof public.penta_mail_outbox_v1
language plpgsql
security definer
set search_path=pg_catalog,crm,public,integration_control,pg_temp
as $$
declare
  v_status jsonb;
  v_pool jsonb;
  v_now timestamptz:=clock_timestamp();
  v_limit integer:=greatest(1,least(coalesce(p_limit,2),2));
  v_global integer;
  v_loct integer;
  v_other integer;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  perform integration_control.penta_mail_reconcile_trigger_probation_v1();
  v_status:=public.penta_mail_provider_status_v1(null);
  if v_status->>'route_state' not in ('closed','controlled_release') then return; end if;

  v_pool:=public.penta_mail_pool_status_v2();
  v_global:=coalesce((v_pool#>>'{dynamic,global_remaining}')::integer,0);
  v_loct:=coalesce((v_pool#>>'{dynamic,locticians_available_now}')::integer,0);
  v_other:=coalesce((v_pool#>>'{dynamic,other_marketing_available_now}')::integer,0);
  v_limit:=least(v_limit,v_global);
  if v_limit<1 then return; end if;

  update public.penta_mail_outbox_v1 o
  set state='queued',
      available_at=greatest(o.available_at,v_now),
      metadata=o.metadata||jsonb_build_object(
        'provider_release_mode','controlled',
        'trigger_probation_expired_at',v_now,
        'released_by','PentaMail'
      ),
      updated_at=v_now
  where o.state='held'
    and o.metadata->>'provider_hold_policy'='ct.pentamailer.policy.mailgun-delivery-resilience.v1@1.0.0'
    and (
      lower(o.message_type)='locticians_claim'
      or (
        lower(coalesce(o.metadata->>'origin_penta',''))='pentamarketer'
        and lower(coalesce(o.metadata->>'recipient_scope',''))='governed_external'
      )
    )
    and not exists(
      select 1 from integration_control.penta_mail_trigger_probation_v1 p
      where p.trigger_ref=o.trigger_ref and p.probation_until>v_now
    );

  update public.penta_mail_outbox_v1 o
  set state='retry',
      lease_id=null,
      lease_expires_at=null,
      available_at=greatest(o.available_at,v_now),
      metadata=o.metadata||jsonb_build_object('lease_recovered_at',v_now,'recovered_by','PentaMail'),
      updated_at=v_now
  where o.state='dispatching'
    and (
      lower(o.message_type)='locticians_claim'
      or (
        lower(coalesce(o.metadata->>'origin_penta',''))='pentamarketer'
        and lower(coalesce(o.metadata->>'recipient_scope',''))='governed_external'
      )
    )
    and o.lease_expires_at<=v_now;

  return query
  with eligible as (
    select
      o.message_id,
      o.severity,
      o.created_at,
      public.penta_mail_traffic_class_v2(o.message_type,o.metadata) as traffic_class
    from public.penta_mail_outbox_v1 o
    where o.state in ('queued','pending','retry')
      and o.available_at<=v_now
      and not exists(
        select 1 from integration_control.penta_mail_trigger_probation_v1 p
        where p.trigger_ref=o.trigger_ref and p.probation_until>v_now
      )
      and (
        (
          lower(o.message_type)='locticians_claim'
          and crm.penta_marketer_outbox_eligible_v1(o.message_id)
        )
        or (
          lower(coalesce(o.metadata->>'origin_penta',''))='pentamarketer'
          and lower(coalesce(o.metadata->>'recipient_scope',''))='governed_external'
          and coalesce(o.metadata->>'work_id','') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
          and crm.penta_marketer_external_recipient_allowed_v1(
            o.recipient,
            (o.metadata->>'work_id')::uuid
          )
        )
      )
  ), ranked as (
    select
      e.*,
      row_number() over(
        partition by traffic_class
        order by
          case upper(severity)
            when 'CRITICAL' then 1 when 'P0' then 1
            when 'HIGH' then 2 when 'P1' then 2
            when 'MEDIUM' then 3 when 'P2' then 3
            when 'INFO' then 4 when 'P3' then 4 else 5
          end,
          created_at
      ) as class_rank
    from eligible e
  ), candidates as (
    select message_id
    from ranked
    where (
      traffic_class='system_internal' and class_rank<=v_global
    ) or (
      traffic_class='marketing_locticians' and class_rank<=v_loct
    ) or (
      traffic_class='marketing_other' and class_rank<=v_other
    )
    order by
      case traffic_class
        when 'system_internal' then 0
        when 'marketing_locticians' then 1
        else 2
      end,
      class_rank
    for update skip locked
    limit v_limit
  ), leases as (
    select message_id,gen_random_uuid() lease_id from candidates
  )
  update public.penta_mail_outbox_v1 o
  set state='dispatching',
      lease_id=l.lease_id,
      lease_expires_at=v_now+interval '5 minutes',
      metadata=o.metadata||jsonb_build_object(
        'claimed_at',v_now,
        'claimed_by','PentaMail',
        'communication_control_plane','PentaMarketer',
        'transport_owner','PentaMail',
        'controlled_release_batch_limit',2,
        'pool_policy','ct.pentamailer.pool.40k.v1',
        'dynamic_allocation',true
      ),
      updated_at=v_now
  from leases l
  where o.message_id=l.message_id
  returning o.*;
end;
$$;

create or replace function crm.penta_marketer_claim_outbox_v1(p_limit integer default 2)
returns setof public.penta_mail_outbox_v1
language sql
security definer
set search_path=pg_catalog,crm,public
as $$select * from crm.penta_marketer_claim_outbox_v2(p_limit);$$;

create or replace function public.penta_marketer_claim_outbox_v1(p_limit integer default 2)
returns setof public.penta_mail_outbox_v1
language sql
security definer
set search_path=pg_catalog,crm,public
as $$select * from crm.penta_marketer_claim_outbox_v2(p_limit);$$;

commit;
