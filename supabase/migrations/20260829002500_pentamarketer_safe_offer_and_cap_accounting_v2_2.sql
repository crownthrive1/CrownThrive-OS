update crm.offer_registry
set public_copy='Claimable listings only: use CLAIMMONTH50 for 50% off eligible recurring membership payments. Verify your eligible plan at checkout. Public offer evidence currently shows Community+ Member and Basic; exact eligibility and current terms are shown at checkout.',
    evidence=coalesce(evidence,'{}'::jsonb)||jsonb_build_object(
      'safe_copy_v2_reconciled_at',now(),
      'safe_copy_v2_basis',jsonb_build_array(
        'public_evidence_state=verified',
        'public join evidence shows Community+ Member and Basic',
        'provider/admin evidence records recurring discount enabled',
        'checkout verification remains pending and is explicitly deferred to checkout'
      ),
      'checkout_verification_state_preserved','pending',
      'no_broader_plan_scope_claim',true,
      'no_scarcity_claim',true
    ),
    updated_at=now()
where offer_key='locticians.claimmonth50.v1';

insert into crm.penta_marketer_campaign_events_v1(campaign_id,event_type,actor_ref,evidence,created_at)
values(
  'ct.pentamarketer.locticians.claim.20260827.v1',
  'safe_offer_bound',
  'PentaMarketer/PentaCertify',
  jsonb_build_object(
    'offer_ref','locticians.claimmonth50.v1',
    'mode','SAFE_CONFLICT_COPY_ONLY',
    'required_safe_phrases',array['50% off eligible recurring membership payments','verify your eligible plan at checkout'],
    'checkout_verification_state','pending',
    'public_evidence_state','verified',
    'no_broader_plan_scope_claim',true
  ),
  now()
);

create or replace function crm.penta_marketer_campaign_status_v1(
  p_campaign_id text default 'ct.pentamarketer.locticians.claim.20260827.v1'
)
returns jsonb
language plpgsql
stable
security definer
set search_path to 'pg_catalog','crm','chlom_runtime','pg_temp'
as $$
declare
  c crm.penta_marketer_campaign_v1%rowtype;
  cfg crm.outbound_config%rowtype;
  maintenance jsonb;
  local_today date;
  local_month date;
  sent_today integer:=0;
  queued_today integer:=0;
  committed_today integer:=0;
  sent_month integer:=0;
  queued_month integer:=0;
  committed_month integer:=0;
  total_attempted integer:=0;
  authority_reasons jsonb:='[]'::jsonb;
  capacity_reasons jsonb:='[]'::jsonb;
  authority_active boolean;
  can_enqueue boolean;
begin
  select * into c from crm.penta_marketer_campaign_v1 where campaign_id=p_campaign_id;
  if not found then
    return jsonb_build_object('active',false,'can_enqueue',false,'state','HOLD','authority_reasons',jsonb_build_array('campaign_not_found'),'capacity_reasons','[]'::jsonb);
  end if;

  select * into cfg from crm.outbound_config where singleton=true;
  maintenance:=chlom_runtime.maintenance_state_v1();
  local_today:=(now() at time zone c.business_timezone)::date;
  local_month:=date_trunc('month',now() at time zone c.business_timezone)::date;

  select count(*) into sent_today
  from crm.outreach_events_v1 e
  where e.event_type='cold_sent'
    and e.metadata->>'campaign_ref'=c.campaign_id
    and (e.created_at at time zone c.business_timezone)::date=local_today;

  select count(*) into queued_today
  from crm.outreach_schedule_v1 s
  where s.campaign_ref=c.campaign_id
    and s.state in ('scheduled','enqueued')
    and (s.scheduled_for at time zone c.business_timezone)::date=local_today;

  committed_today:=sent_today+queued_today;

  select count(*) into sent_month
  from crm.outreach_events_v1 e
  where e.event_type='cold_sent'
    and e.metadata->>'campaign_ref'=c.campaign_id
    and date_trunc('month',e.created_at at time zone c.business_timezone)::date=local_month;

  select count(*) into queued_month
  from crm.outreach_schedule_v1 s
  where s.campaign_ref=c.campaign_id
    and s.state in ('scheduled','enqueued')
    and date_trunc('month',s.scheduled_for at time zone c.business_timezone)::date=local_month;

  committed_month:=sent_month+queued_month;

  select count(*) into total_attempted
  from crm.outreach_events_v1 e
  where e.event_type='cold_enqueued'
    and e.metadata->>'campaign_ref'=c.campaign_id;

  if coalesce((maintenance->>'maintenance_active')::boolean,false) then authority_reasons:=authority_reasons||'"maintenance_active"'::jsonb; end if;
  if c.state<>'active' then authority_reasons:=authority_reasons||to_jsonb('campaign_'||c.state); end if;
  if now()<c.starts_at then authority_reasons:=authority_reasons||'"campaign_not_started"'::jsonb; end if;
  if now()>=c.expires_at then authority_reasons:=authority_reasons||'"campaign_expired"'::jsonb; end if;
  if not c.provider_write_authority then authority_reasons:=authority_reasons||'"provider_write_not_authorized"'::jsonb; end if;
  if not cfg.cold_outreach_enabled then authority_reasons:=authority_reasons||'"cold_outreach_disabled"'::jsonb; end if;
  if nullif(btrim(cfg.verified_postal_address),'') is null then authority_reasons:=authority_reasons||'"postal_address_missing"'::jsonb; end if;
  if cfg.max_new_cold_emails_per_day<>c.daily_cap then authority_reasons:=authority_reasons||'"daily_cap_drift"'::jsonb; end if;
  if cfg.max_new_cold_emails_per_month<>c.monthly_cap then authority_reasons:=authority_reasons||'"monthly_cap_drift"'::jsonb; end if;

  if committed_today>=c.daily_cap then capacity_reasons:=capacity_reasons||'"daily_cap_committed"'::jsonb; end if;
  if committed_month>=c.monthly_cap then capacity_reasons:=capacity_reasons||'"monthly_cap_committed"'::jsonb; end if;
  if total_attempted>=c.total_cap then capacity_reasons:=capacity_reasons||'"campaign_total_cap_reached"'::jsonb; end if;

  authority_active:=jsonb_array_length(authority_reasons)=0;
  can_enqueue:=authority_active and jsonb_array_length(capacity_reasons)=0;

  return jsonb_build_object(
    'active',authority_active,
    'can_enqueue',can_enqueue,
    'state',case when authority_active then case when can_enqueue then 'ACTIVE' else 'CAPACITY_HOLD' end else 'HOLD' end,
    'campaign_id',c.campaign_id,
    'directive_id',c.directive_id,
    'canonical_agent_id',c.canonical_agent_id,
    'specialist_id',c.specialist_id,
    'offer_ref',c.offer_ref,
    'daily_cap',c.daily_cap,
    'sent_today',sent_today,
    'queued_today',queued_today,
    'committed_today',committed_today,
    'remaining_today',greatest(0,c.daily_cap-committed_today),
    'monthly_cap',c.monthly_cap,
    'sent_month',sent_month,
    'queued_month',queued_month,
    'committed_month',committed_month,
    'remaining_month',greatest(0,c.monthly_cap-committed_month),
    'total_attempted',total_attempted,
    'total_cap',c.total_cap,
    'starts_at',c.starts_at,
    'expires_at',c.expires_at,
    'nonrenewing',c.nonrenewing,
    'maintenance',maintenance,
    'authority_reasons',authority_reasons,
    'capacity_reasons',capacity_reasons,
    'tracking_sheet_id',c.tracking_sheet_id
  );
end;
$$;

create or replace function crm.penta_marketer_batch_planner_v2(
  p_campaign_id text default 'ct.pentamarketer.locticians.claim.20260827.v1'
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','crm','public','chlom_runtime','pg_temp'
as $$
declare
  p crm.penta_marketer_queue_policy_v1%rowtype;
  c crm.penta_marketer_campaign_v1%rowtype;
  v_now timestamptz:=clock_timestamp();
  v_local_now timestamp;
  v_open_at timestamptz;
  v_close_at timestamptz;
  v_base timestamptz;
  v_last_slot timestamptz;
  v_slot timestamptz;
  v_campaign jsonb;
  v_provider jsonb:='{"state":"SKIPPED"}'::jsonb;
  v_seed jsonb;
  v_discovery jsonb;
  v_promote jsonb;
  v_inventory integer:=0;
  v_queue_depth integer:=0;
  v_sent_today integer:=0;
  v_queued_today integer:=0;
  v_committed_today integer:=0;
  v_sent_month integer:=0;
  v_queued_month integer:=0;
  v_committed_month integer:=0;
  v_slots integer:=0;
  v_to_add integer:=0;
  v_planned integer:=0;
  r record;
begin
  if current_user not in ('postgres','service_role')
     and coalesce(current_setting('request.jwt.claim.role',true),'')<>'service_role' then
    raise exception 'service_role_required';
  end if;

  perform pg_advisory_xact_lock(hashtext('crm.penta_marketer_batch_planner_v2:'||p_campaign_id));

  select * into p from crm.penta_marketer_queue_policy_v1 where campaign_id=p_campaign_id and active=true;
  if not found then return jsonb_build_object('state','HOLD','reason','queue_policy_missing_or_inactive'); end if;
  select * into c from crm.penta_marketer_campaign_v1 where campaign_id=p_campaign_id;
  if not found then return jsonb_build_object('state','HOLD','reason','campaign_not_found'); end if;

  select count(*) into v_inventory
  from crm.outreach_contacts_v1 x
  where x.relationship_state='prospect' and x.research_state='verified' and x.claimable_profile and x.copy_state='ready'
    and x.opted_out_at is null and x.complaint_at is null and x.hard_bounced_at is null and x.risk_hold_at is null
    and x.replied_at is null and x.converted_at is null and x.wrong_person_at is null
    and not exists (select 1 from crm.outreach_events_v1 e where e.contact_id=x.contact_id and e.event_type in ('cold_enqueued','cold_sent'))
    and not exists (select 1 from crm.outreach_schedule_v1 s where s.contact_id=x.contact_id and s.state in ('scheduled','enqueued','sent'));

  if v_inventory < p.target_depth*2
     and (p.last_provider_ingest_at is null or p.last_provider_ingest_at <= v_now-make_interval(mins=>case when p.last_provider_ingest_state='COMPLETE' then 5 else p.provider_retry_minutes end)) then
    v_provider:=crm.locticians_claimable_prospect_ingest_v1(p.provider_ingest_limit);
    update crm.penta_marketer_queue_policy_v1
    set last_provider_ingest_at=v_now,last_provider_ingest_state=coalesce(v_provider->>'state','UNKNOWN'),updated_at=v_now
    where campaign_id=p_campaign_id;
  end if;

  v_seed:=crm.contact_discovery_seed_v1(p.discovery_seed_limit);
  v_discovery:=crm.contact_discovery_process_batch_v1(p.discovery_process_limit);
  v_promote:=crm.penta_marketer_promote_researched_prospects_v1(p.target_depth*2);

  select count(*) into v_inventory
  from crm.outreach_contacts_v1 x
  where x.relationship_state='prospect' and x.research_state='verified' and x.claimable_profile and x.copy_state='ready'
    and x.opted_out_at is null and x.complaint_at is null and x.hard_bounced_at is null and x.risk_hold_at is null
    and x.replied_at is null and x.converted_at is null and x.wrong_person_at is null
    and not exists (select 1 from crm.outreach_events_v1 e where e.contact_id=x.contact_id and e.event_type in ('cold_enqueued','cold_sent'))
    and not exists (select 1 from crm.outreach_schedule_v1 s where s.contact_id=x.contact_id and s.state in ('scheduled','enqueued','sent'));

  v_campaign:=crm.penta_marketer_campaign_status_v1(p_campaign_id);
  if not coalesce((v_campaign->>'active')::boolean,false) then
    update crm.penta_marketer_queue_policy_v1 set last_planner_at=v_now,last_queue_depth=0,updated_at=v_now where campaign_id=p_campaign_id;
    return jsonb_build_object('state','HOLD','reason','campaign_authority_inactive','campaign',v_campaign,'provider_ingest',v_provider,'seed',v_seed,'discovery',v_discovery,'promote',v_promote,'ready_inventory',v_inventory);
  end if;

  v_local_now:=v_now at time zone c.business_timezone;
  if c.business_days_only and extract(isodow from v_local_now)>5 then
    update crm.penta_marketer_queue_policy_v1 set last_planner_at=v_now,last_queue_depth=0,updated_at=v_now where campaign_id=p_campaign_id;
    return jsonb_build_object('state','WEEKEND_INVENTORY_ONLY','provider_ingest',v_provider,'seed',v_seed,'discovery',v_discovery,'promote',v_promote,'ready_inventory',v_inventory);
  end if;

  v_open_at := (v_local_now::date + p.send_start_local) at time zone c.business_timezone;
  v_close_at := (v_local_now::date + p.send_end_local) at time zone c.business_timezone;
  if v_now >= v_close_at then
    update crm.penta_marketer_queue_policy_v1 set last_planner_at=v_now,last_queue_depth=0,updated_at=v_now where campaign_id=p_campaign_id;
    return jsonb_build_object('state','WINDOW_CLOSED_INVENTORY_ONLY','provider_ingest',v_provider,'seed',v_seed,'discovery',v_discovery,'promote',v_promote,'ready_inventory',v_inventory,'next_open_local',p.send_start_local);
  end if;

  select count(*) into v_queue_depth
  from crm.outreach_schedule_v1 s
  where s.campaign_ref=p_campaign_id and s.state in ('scheduled','enqueued')
    and (s.scheduled_for at time zone c.business_timezone)::date=v_local_now::date;

  if v_queue_depth >= p.low_watermark then
    update crm.penta_marketer_queue_policy_v1 set last_planner_at=v_now,last_queue_depth=v_queue_depth,updated_at=v_now where campaign_id=p_campaign_id;
    return jsonb_build_object('state','WATERMARK_HEALTHY','queue_depth',v_queue_depth,'low_watermark',p.low_watermark,'target_depth',p.target_depth,'ready_inventory',v_inventory,'provider_ingest',v_provider,'seed',v_seed,'discovery',v_discovery,'promote',v_promote);
  end if;

  v_sent_today:=coalesce((v_campaign->>'sent_today')::integer,0);
  v_queued_today:=coalesce((v_campaign->>'queued_today')::integer,0);
  v_committed_today:=coalesce((v_campaign->>'committed_today')::integer,0);
  v_sent_month:=coalesce((v_campaign->>'sent_month')::integer,0);
  v_queued_month:=coalesce((v_campaign->>'queued_month')::integer,0);
  v_committed_month:=coalesce((v_campaign->>'committed_month')::integer,0);

  select max(s.scheduled_for) into v_last_slot
  from crm.outreach_schedule_v1 s
  where s.campaign_ref=p_campaign_id and s.state in ('scheduled','enqueued')
    and (s.scheduled_for at time zone c.business_timezone)::date=v_local_now::date;

  v_base:=greatest(v_now,v_open_at,coalesce(v_last_slot,v_open_at));
  v_slots:=greatest(0,floor(extract(epoch from (v_close_at-v_base))/p.spacing_seconds)::integer);

  v_to_add:=greatest(0,least(
    p.target_depth-v_queue_depth,
    c.daily_cap-v_committed_today,
    c.monthly_cap-v_committed_month,
    p.plan_batch_limit,
    v_slots
  ));

  if v_to_add<=0 then
    update crm.penta_marketer_queue_policy_v1 set last_planner_at=v_now,last_queue_depth=v_queue_depth,updated_at=v_now where campaign_id=p_campaign_id;
    return jsonb_build_object('state','NO_CAPACITY','queue_depth',v_queue_depth,'sent_today',v_sent_today,'queued_today',v_queued_today,'committed_today',v_committed_today,'daily_cap',c.daily_cap,'committed_month',v_committed_month,'monthly_cap',c.monthly_cap,'slots_before_close',v_slots,'ready_inventory',v_inventory,'provider_ingest',v_provider);
  end if;

  v_last_slot:=v_base;
  for r in
    select x.contact_id
    from crm.outreach_contacts_v1 x
    where not exists (select 1 from crm.outreach_schedule_v1 s where s.contact_id=x.contact_id and s.state in ('scheduled','enqueued','sent'))
      and coalesce((crm.penta_marketer_eligibility_v1(x.contact_id,'cold')->>'eligible')::boolean,false)
    order by coalesce(x.fit_score,0) desc,coalesce(x.legitimacy_score,0) desc,x.created_at
    limit v_to_add
  loop
    v_slot:=v_last_slot+make_interval(secs=>p.spacing_seconds);
    exit when v_slot>v_close_at;
    insert into crm.outreach_schedule_v1(contact_id,send_kind,campaign_ref,offer_ref,scheduled_for,state,created_at,updated_at)
    values(r.contact_id,'cold',p_campaign_id,c.offer_ref,v_slot,'scheduled',v_now,v_now);
    v_planned:=v_planned+1;
    v_last_slot:=v_slot;
  end loop;

  select count(*) into v_queue_depth
  from crm.outreach_schedule_v1 s
  where s.campaign_ref=p_campaign_id and s.state in ('scheduled','enqueued')
    and (s.scheduled_for at time zone c.business_timezone)::date=v_local_now::date;

  update crm.penta_marketer_queue_policy_v1
  set last_planner_at=v_now,last_queue_depth=v_queue_depth,updated_at=v_now
  where campaign_id=p_campaign_id;

  return jsonb_build_object(
    'state',case when v_planned>0 then 'REPLENISHED' else 'NO_ELIGIBLE_CONTACTS' end,
    'planned',v_planned,'queue_depth',v_queue_depth,'low_watermark',p.low_watermark,'target_depth',p.target_depth,
    'ready_inventory',v_inventory,'sent_today',v_sent_today,'committed_today',v_committed_today,'daily_cap',c.daily_cap,
    'committed_month',v_committed_month,'monthly_cap',c.monthly_cap,'provider_ingest',v_provider,'seed',v_seed,'discovery',v_discovery,'promote',v_promote
  );
end;
$$;

grant execute on function crm.penta_marketer_campaign_status_v1(text) to service_role;
grant execute on function crm.penta_marketer_batch_planner_v2(text) to service_role;