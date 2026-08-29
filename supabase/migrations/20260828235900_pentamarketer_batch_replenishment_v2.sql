create table if not exists crm.penta_marketer_queue_policy_v1 (
  campaign_id text primary key references crm.penta_marketer_campaign_v1(campaign_id) on delete cascade,
  active boolean not null default true,
  low_watermark integer not null default 40 check (low_watermark between 1 and 500),
  target_depth integer not null default 80 check (target_depth between 1 and 1000),
  plan_batch_limit integer not null default 50 check (plan_batch_limit between 1 and 500),
  discovery_seed_limit integer not null default 200 check (discovery_seed_limit between 1 and 500),
  discovery_process_limit integer not null default 10 check (discovery_process_limit between 1 and 25),
  provider_ingest_limit integer not null default 100 check (provider_ingest_limit between 1 and 100),
  provider_retry_minutes integer not null default 15 check (provider_retry_minutes between 1 and 1440),
  spacing_seconds integer not null default 240 check (spacing_seconds between 30 and 3600),
  send_start_local time without time zone not null default time '06:00',
  send_end_local time without time zone not null default time '21:00',
  last_provider_ingest_at timestamptz,
  last_provider_ingest_state text,
  provider_page_cursor text,
  provider_current_page integer,
  provider_total bigint,
  last_planner_at timestamptz,
  last_queue_depth integer,
  updated_at timestamptz not null default now(),
  check (target_depth >= low_watermark),
  check (send_end_local > send_start_local)
);

insert into crm.penta_marketer_queue_policy_v1(
  campaign_id,active,low_watermark,target_depth,plan_batch_limit,
  discovery_seed_limit,discovery_process_limit,provider_ingest_limit,
  provider_retry_minutes,spacing_seconds,send_start_local,send_end_local,updated_at
) values (
  'ct.pentamarketer.locticians.claim.20260827.v1',true,40,80,50,200,10,100,15,240,time '06:00',time '21:00',now()
)
on conflict (campaign_id) do update set
  active=excluded.active,
  low_watermark=excluded.low_watermark,
  target_depth=excluded.target_depth,
  plan_batch_limit=excluded.plan_batch_limit,
  discovery_seed_limit=excluded.discovery_seed_limit,
  discovery_process_limit=excluded.discovery_process_limit,
  provider_ingest_limit=excluded.provider_ingest_limit,
  provider_retry_minutes=excluded.provider_retry_minutes,
  spacing_seconds=excluded.spacing_seconds,
  send_start_local=excluded.send_start_local,
  send_end_local=excluded.send_end_local,
  updated_at=now();

create or replace function crm.public_http_target_safe_v1(p_url text)
returns boolean
language sql
immutable
set search_path to 'pg_catalog'
as $$
  select
    nullif(btrim(coalesce(p_url,'')),'') is not null
    and p_url ~* '^https?://'
    and p_url !~* '^https?://[^/]*@'
    and p_url !~* '^https?://(localhost|0\.0\.0\.0|127\.|10\.|169\.254\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|\[?::1\]?|metadata\.google\.internal)([:/]|$)';
$$;

create or replace function crm.locticians_claimable_prospect_ingest_v1(p_limit integer default 100)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','crm','public','integration_control','extensions','pg_temp'
as $$
declare
  v_limit integer := greatest(1,least(coalesce(p_limit,100),100));
  v_key text;
  v_headers extensions.http_header[];
  v_resp extensions.http_response;
  v_body jsonb;
  v_records jsonb := '[]'::jsonb;
  v_touched integer := 0;
  v_reason text;
  v_cursor text;
  v_url text;
  v_next_cursor text;
  v_current_page integer;
  v_total bigint;
begin
  if current_user not in ('postgres','service_role')
     and coalesce(current_setting('request.jwt.claim.role',true),'') <> 'service_role' then
    raise exception 'service_role_required';
  end if;

  if not exists (
    select 1
    from integration_control.locticians_endpoint_catalog_v2
    where endpoint_id='locticians:user:get'
      and internal_enabled=true
      and state='verified_read'
  ) then
    return jsonb_build_object('state','PROVIDER_HOLD','reason','user_get_not_certified');
  end if;

  v_key := public.get_runtime_secret('locticians_brilliant_directories_api_key');
  if nullif(v_key,'') is null then
    return jsonb_build_object('state','PROVIDER_HOLD','reason','provider_key_missing');
  end if;

  v_headers := array[
    extensions.http_header('X-Api-Key',v_key),
    extensions.http_header('accept','application/json')
  ]::extensions.http_header[];

  select provider_page_cursor into v_cursor
  from crm.penta_marketer_queue_policy_v1
  where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1';

  v_url := 'https://www.locticians.com/api/v2/user/get?property=verified&property_value=0&limit='||v_limit::text;
  if nullif(v_cursor,'') is not null then
    v_url := v_url||'&page='||replace(replace(replace(v_cursor,'+','%2B'),'/','%2F'),'=','%3D');
  end if;

  begin
    v_resp := extensions.http((
      'GET',
      v_url,
      v_headers,
      null,
      null
    )::extensions.http_request);
  exception when others then
    return jsonb_build_object('state','PROVIDER_HOLD','reason','provider_transport_error');
  end;

  if v_resp.status <> 200 then
    v_reason := case
      when lower(coalesce(v_resp.content,'')) like '%expired api key%' then 'provider_key_expired'
      else 'provider_read_failed'
    end;
    return jsonb_build_object('state','PROVIDER_HOLD','reason',v_reason,'http_status',v_resp.status);
  end if;

  begin
    v_body := v_resp.content::jsonb;
  exception when others then
    return jsonb_build_object('state','PROVIDER_HOLD','reason','provider_non_json','http_status',v_resp.status);
  end;

  if jsonb_typeof(v_body)='array' then
    v_records := v_body;
  elsif jsonb_typeof(v_body->'message')='array' then
    v_records := v_body->'message';
  elsif jsonb_typeof(v_body->'message')='object' then
    v_records := jsonb_build_array(v_body->'message');
  end if;

  v_next_cursor:=nullif(v_body->>'next_page','');
  begin v_current_page:=nullif(v_body->>'current_page','')::integer; exception when others then v_current_page:=null; end;
  begin v_total:=nullif(v_body->>'total','')::bigint; exception when others then v_total:=null; end;

  update crm.penta_marketer_queue_policy_v1
  set provider_page_cursor=case when v_next_cursor is null then null else v_next_cursor end,
      provider_current_page=v_current_page,
      provider_total=v_total,
      updated_at=now()
  where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1';

  with source_rows as (
    select value as r
    from jsonb_array_elements(v_records)
    limit v_limit
  ),
  normalized as (
    select
      r,
      coalesce(
        nullif(btrim(r->>'company'),''),
        nullif(btrim(concat_ws(' ',r->>'first_name',r->>'last_name')),'')
      ) as listing_name,
      nullif(btrim(r->>'filename'),'') as filename,
      nullif(btrim(r->>'website'),'') as website_url,
      nullif(btrim(r->>'city'),'') as city,
      nullif(btrim(r->>'state_code'),'') as region,
      nullif(btrim(r->>'country_code'),'') as country
    from source_rows
  ),
  eligible as (
    select *
    from normalized
    where listing_name is not null
      and filename is not null
      and coalesce(r->>'subscription_id','')='14'
      and coalesce(r->>'active','')='2'
  )
  insert into crm.prospects(
    source_platform,source_listing_url,listing_name,category,city,region,country,
    website_url,claim_status,lifecycle,lead_score,risk_score,compliance_status,
    enrichment,created_at,updated_at
  )
  select
    'locticians',
    'https://locticians.com/'||regexp_replace(filename,'^/+','','g'),
    listing_name,
    initcap(replace(substring(filename from '.*/([^/]+)/[^/]+$'),'-',' ')),
    city,region,country,website_url,
    'claimable','new',70,0,'hold',
    jsonb_strip_nulls(jsonb_build_object(
      'provider_user_id',nullif(r->>'user_id',''),
      'provider_subscription_id',nullif(r->>'subscription_id',''),
      'provider_active',nullif(r->>'active',''),
      'provider_verified',nullif(r->>'verified',''),
      'provider_profession_id',nullif(r->>'profession_id',''),
      'provider_source','bd_filtered_verified_0',
      'claim_evidence_observed',true,
      'provider_ingested_at',now()
    )),
    now(),now()
  from eligible
  on conflict (source_platform,source_listing_url) do update set
    listing_name=excluded.listing_name,
    category=coalesce(excluded.category,crm.prospects.category),
    city=coalesce(excluded.city,crm.prospects.city),
    region=coalesce(excluded.region,crm.prospects.region),
    country=coalesce(excluded.country,crm.prospects.country),
    website_url=coalesce(excluded.website_url,crm.prospects.website_url),
    claim_status=case when crm.prospects.claim_status='claimed' then 'claimed' else 'claimable' end,
    enrichment=crm.prospects.enrichment||excluded.enrichment,
    updated_at=now();

  get diagnostics v_touched=row_count;

  return jsonb_build_object(
    'state','COMPLETE',
    'http_status',v_resp.status,
    'provider_records',jsonb_array_length(v_records),
    'prospects_touched',v_touched,
    'source_filter','verified=0 then subscription_id=14 and active=2',
    'current_page',v_current_page,
    'next_page_present',v_next_cursor is not null,
    'provider_total',v_total
  );
end;
$$;

create or replace function crm.contact_discovery_claim_v1(p_limit integer default 10)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','crm','pg_temp'
as $$
declare
  v_limit integer:=greatest(1,least(coalesce(p_limit,10),25));
  v_result jsonb;
begin
  if current_user not in ('postgres','service_role')
     and coalesce(current_setting('request.jwt.claim.role',true),'')<>'service_role' then
    raise exception 'service_role_required';
  end if;

  update crm.contact_discovery_queue_v1
  set state='retry',lease_id=null,lease_expires_at=null,available_at=now(),updated_at=now(),
      last_error=concat_ws(';',nullif(last_error,''),'lease_expired')
  where state='leased' and lease_expires_at<=now();

  with candidates as (
    select q.queue_id
    from crm.contact_discovery_queue_v1 q
    where q.state in ('pending','retry')
      and q.available_at<=now()
      and q.attempt_count<q.max_attempts
    order by q.priority desc,q.available_at,q.created_at
    for update skip locked
    limit v_limit
  ),
  leased as (
    update crm.contact_discovery_queue_v1 q
    set state='leased',lease_id=gen_random_uuid(),lease_expires_at=now()+interval '5 minutes',updated_at=now()
    from candidates c
    where q.queue_id=c.queue_id
    returning q.*
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'queue_id',l.queue_id,'lease_id',l.lease_id,'prospect_id',l.prospect_id,'target_url',l.target_url,
    'source_kind',l.source_kind,'attempt_count',l.attempt_count,'max_attempts',l.max_attempts,
    'listing_name',p.listing_name,'website_url',p.website_url,'source_listing_url',p.source_listing_url,'public_email',p.public_email
  ) order by l.priority desc,l.created_at),'[]'::jsonb)
  into v_result
  from leased l
  join crm.prospects p on p.id=l.prospect_id;

  return v_result;
end;
$$;

create or replace function crm.contact_discovery_process_batch_v1(p_limit integer default 10)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','crm','public','extensions','pg_temp'
as $$
declare
  v_claims jsonb;
  v_item jsonb;
  v_queue_id uuid;
  v_url text;
  v_kind text;
  v_resp extensions.http_response;
  v_html text;
  v_obs jsonb;
  v_completed integer:=0;
  v_retried integer:=0;
  v_skipped integer:=0;
begin
  if current_user not in ('postgres','service_role')
     and coalesce(current_setting('request.jwt.claim.role',true),'')<>'service_role' then
    raise exception 'service_role_required';
  end if;

  v_claims:=crm.contact_discovery_claim_v1(greatest(1,least(coalesce(p_limit,10),25)));

  for v_item in select value from jsonb_array_elements(v_claims)
  loop
    v_queue_id:=(v_item->>'queue_id')::uuid;
    v_url:=v_item->>'target_url';
    v_kind:=v_item->>'source_kind';

    if v_kind='directory_listing' then
      perform crm.contact_discovery_complete_v1(v_queue_id,'[]'::jsonb,null);
      v_skipped:=v_skipped+1;
      continue;
    end if;

    if not crm.public_http_target_safe_v1(v_url) then
      perform crm.contact_discovery_complete_v1(v_queue_id,'[]'::jsonb,'unsafe_target_url');
      v_retried:=v_retried+1;
      continue;
    end if;

    begin
      v_resp:=extensions.http((
        'GET',v_url,
        array[
          extensions.http_header('accept','text/html,application/xhtml+xml'),
          extensions.http_header('user-agent','CrownThrive-PentaCrawler/2.0 (+https://crownthrive.com)')
        ]::extensions.http_header[],
        null,null
      )::extensions.http_request);
    exception when others then
      perform crm.contact_discovery_complete_v1(v_queue_id,'[]'::jsonb,'http_transport_error');
      v_retried:=v_retried+1;
      continue;
    end;

    if v_resp.status < 200 or v_resp.status >= 300 then
      perform crm.contact_discovery_complete_v1(v_queue_id,'[]'::jsonb,'http_'||v_resp.status::text);
      v_retried:=v_retried+1;
      continue;
    end if;

    v_html:=left(coalesce(v_resp.content,''),1000000);

    with emails as (
      select distinct lower(m.match[1]) as email
      from regexp_matches(v_html,'(?i)mailto:([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})','g') as m(match)
      union
      select distinct lower(m.match[1]) as email
      from regexp_matches(v_html,'(?i)([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})','g') as m(match)
    ),
    filtered as (
      select email
      from emails
      where email not in ('user@domain.com','email@example.com','name@example.com')
        and lower(split_part(email,'@',2)) !~ '(wixpress|sentry|ndiscovered|example|domain\.com|w3\.org|cloudflare|schema\.org|wordpress|shopify)'
      order by case when split_part(email,'@',1) in ('info','hello','contact','bookings','booking','appointments','owner') then 0 else 1 end,email
      limit 5
    )
    select coalesce(jsonb_agg(jsonb_build_object(
      'email',email,
      'source_url',v_url,
      'source_type',v_kind,
      'page_title',null,
      'confidence',case when v_kind='official_business_site' then 95 else 90 end,
      'is_public_business_contact',true,
      'evidence_sha256',encode(extensions.digest(v_url||'|'||email,'sha256'),'hex'),
      'evidence',jsonb_build_object('collector','PentaCrawler SQL bounded public-contact pass','http_status',v_resp.status,'body_archived',false),
      'observed_at',now()
    )),'[]'::jsonb)
    into v_obs
    from filtered;

    perform crm.contact_discovery_complete_v1(v_queue_id,v_obs,null);
    v_completed:=v_completed+1;
  end loop;

  return jsonb_build_object(
    'state','COMPLETE',
    'claimed',jsonb_array_length(v_claims),
    'completed',v_completed,
    'retried',v_retried,
    'directory_skipped',v_skipped
  );
end;
$$;

create or replace function crm.penta_marketer_promote_researched_prospects_v1(p_limit integer default 50)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','crm','public','pg_temp'
as $$
declare
  v_limit integer:=greatest(1,least(coalesce(p_limit,50),200));
  cfg crm.outbound_config%rowtype;
  v_inserted integer:=0;
begin
  if current_user not in ('postgres','service_role')
     and coalesce(current_setting('request.jwt.claim.role',true),'')<>'service_role' then
    raise exception 'service_role_required';
  end if;

  select * into cfg from crm.outbound_config where singleton=true;

  with candidates as (
    select p.*
    from crm.prospects p
    where crm.locticians_research_candidate_v1(p)
      and nullif(btrim(p.public_email),'') is not null
      and p.last_researched_at >= now()-interval '30 days'
      and not exists (
        select 1 from crm.outreach_contacts_v1 c
        where lower(c.email)=lower(p.public_email)
           or c.metadata->>'prospect_id'=p.id::text
      )
      and not exists (
        select 1 from crm.suppression_list s
        where (s.expires_at is null or s.expires_at>now())
          and (
            lower(coalesce(s.email,''))=lower(p.public_email)
            or lower(coalesce(s.domain,''))=lower(split_part(p.public_email,'@',2))
          )
      )
    order by coalesce(p.lead_score,0) desc,p.updated_at desc
    limit v_limit
  )
  insert into crm.outreach_contacts_v1(
    email,display_name,organization,source_url,research_state,legitimacy_score,fit_score,
    research_evidence,claimable_profile,relationship_state,copy_state,draft_subject,draft_body,
    metadata,created_at,updated_at
  )
  select
    lower(p.public_email),
    p.listing_name,
    p.listing_name,
    coalesce(p.email_source_url,p.website_url,p.source_listing_url),
    'verified',
    95,
    greatest(60,least(100,coalesce(p.lead_score,75))),
    jsonb_build_object(
      'prospect_id',p.id,
      'public_email_source',coalesce(p.email_source_url,p.website_url),
      'last_researched_at',p.last_researched_at,
      'claim_status',p.claim_status
    ),
    true,
    'prospect',
    'ready',
    'Is '||p.listing_name||' yours on Locticians?',
    'Hello,'||E'\n\n'||
      'I am reaching out from CrownThrive about the public '||p.listing_name||' profile on Locticians'||
      case when nullif(btrim(p.city),'') is not null then ' in '||p.city else '' end||
      '. The profile currently appears claimable, and this email address was verified from a public business source.'||
      E'\n\n'||
      'Claiming the profile lets you review and manage how your business is represented on Locticians.'||
      E'\n\n'||
      'Current promotion: 50% off eligible recurring membership payments. Verify your eligible plan at checkout.'||
      E'\n\n'||
      'Promotional message from CrownThrive.'||
      E'\n\n'||
      cfg.verified_postal_address||
      E'\n\n'||
      cfg.optout_copy,
    jsonb_build_object(
      'prospect_id',p.id,
      'campaign_ref','ct.pentamarketer.locticians.claim.20260827.v1',
      'offer_ref','locticians.claimmonth50.v1',
      'promoted_by','PentaMarketer/PentaCrawler',
      'promoted_at',now(),
      'source_listing_url',p.source_listing_url
    ),
    now(),now()
  from candidates p
  on conflict do nothing;

  get diagnostics v_inserted=row_count;

  return jsonb_build_object('state','COMPLETE','promoted',v_inserted,'limit',v_limit);
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
  v_committed integer:=0;
  v_enqueued_today integer:=0;
  v_scheduled_today integer:=0;
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
  if not found then
    return jsonb_build_object('state','HOLD','reason','queue_policy_missing_or_inactive');
  end if;

  select * into c from crm.penta_marketer_campaign_v1 where campaign_id=p_campaign_id;
  if not found then
    return jsonb_build_object('state','HOLD','reason','campaign_not_found');
  end if;

  select count(*) into v_inventory
  from crm.outreach_contacts_v1 x
  where x.relationship_state='prospect'
    and x.research_state='verified'
    and x.claimable_profile
    and x.copy_state='ready'
    and x.opted_out_at is null
    and x.complaint_at is null
    and x.hard_bounced_at is null
    and x.risk_hold_at is null
    and x.replied_at is null
    and x.converted_at is null
    and x.wrong_person_at is null
    and not exists (
      select 1 from crm.outreach_events_v1 e
      where e.contact_id=x.contact_id and e.event_type in ('cold_enqueued','cold_sent')
    )
    and not exists (
      select 1 from crm.outreach_schedule_v1 s
      where s.contact_id=x.contact_id and s.state in ('scheduled','enqueued','sent')
    );

  if v_inventory < p.target_depth*2
     and (
       p.last_provider_ingest_at is null
       or p.last_provider_ingest_at <= v_now-make_interval(mins=>case when p.last_provider_ingest_state='COMPLETE' then 5 else p.provider_retry_minutes end)
     ) then
    v_provider:=crm.locticians_claimable_prospect_ingest_v1(p.provider_ingest_limit);
    update crm.penta_marketer_queue_policy_v1
    set last_provider_ingest_at=v_now,
        last_provider_ingest_state=coalesce(v_provider->>'state','UNKNOWN'),
        updated_at=v_now
    where campaign_id=p_campaign_id;
  end if;

  v_seed:=crm.contact_discovery_seed_v1(p.discovery_seed_limit);
  v_discovery:=crm.contact_discovery_process_batch_v1(p.discovery_process_limit);
  v_promote:=crm.penta_marketer_promote_researched_prospects_v1(p.target_depth*2);

  select count(*) into v_inventory
  from crm.outreach_contacts_v1 x
  where x.relationship_state='prospect'
    and x.research_state='verified'
    and x.claimable_profile
    and x.copy_state='ready'
    and x.opted_out_at is null
    and x.complaint_at is null
    and x.hard_bounced_at is null
    and x.risk_hold_at is null
    and x.replied_at is null
    and x.converted_at is null
    and x.wrong_person_at is null
    and not exists (
      select 1 from crm.outreach_events_v1 e
      where e.contact_id=x.contact_id and e.event_type in ('cold_enqueued','cold_sent')
    )
    and not exists (
      select 1 from crm.outreach_schedule_v1 s
      where s.contact_id=x.contact_id and s.state in ('scheduled','enqueued','sent')
    );

  v_campaign:=crm.penta_marketer_campaign_status_v1(p_campaign_id);
  if not coalesce((v_campaign->>'active')::boolean,false) then
    update crm.penta_marketer_queue_policy_v1 set last_planner_at=v_now,last_queue_depth=0,updated_at=v_now where campaign_id=p_campaign_id;
    return jsonb_build_object(
      'state','HOLD','reason','campaign_authority_inactive','campaign',v_campaign,
      'provider_ingest',v_provider,'seed',v_seed,'discovery',v_discovery,'promote',v_promote,'ready_inventory',v_inventory
    );
  end if;

  v_local_now:=v_now at time zone c.business_timezone;

  if c.business_days_only and extract(isodow from v_local_now)>5 then
    update crm.penta_marketer_queue_policy_v1 set last_planner_at=v_now,last_queue_depth=0,updated_at=v_now where campaign_id=p_campaign_id;
    return jsonb_build_object(
      'state','WEEKEND_INVENTORY_ONLY','provider_ingest',v_provider,'seed',v_seed,'discovery',v_discovery,
      'promote',v_promote,'ready_inventory',v_inventory
    );
  end if;

  v_open_at := (v_local_now::date + p.send_start_local) at time zone c.business_timezone;
  v_close_at := (v_local_now::date + p.send_end_local) at time zone c.business_timezone;

  if v_now >= v_close_at then
    update crm.penta_marketer_queue_policy_v1 set last_planner_at=v_now,last_queue_depth=0,updated_at=v_now where campaign_id=p_campaign_id;
    return jsonb_build_object(
      'state','WINDOW_CLOSED_INVENTORY_ONLY','provider_ingest',v_provider,'seed',v_seed,'discovery',v_discovery,
      'promote',v_promote,'ready_inventory',v_inventory,'next_open_local',p.send_start_local
    );
  end if;

  select count(*) into v_queue_depth
  from crm.outreach_schedule_v1 s
  where s.campaign_ref=p_campaign_id
    and s.state in ('scheduled','enqueued')
    and (s.scheduled_for at time zone c.business_timezone)::date=v_local_now::date;

  if v_queue_depth >= p.low_watermark then
    update crm.penta_marketer_queue_policy_v1 set last_planner_at=v_now,last_queue_depth=v_queue_depth,updated_at=v_now where campaign_id=p_campaign_id;
    return jsonb_build_object(
      'state','WATERMARK_HEALTHY','queue_depth',v_queue_depth,'low_watermark',p.low_watermark,'target_depth',p.target_depth,
      'ready_inventory',v_inventory,'provider_ingest',v_provider,'seed',v_seed,'discovery',v_discovery,'promote',v_promote
    );
  end if;

  select count(*) into v_enqueued_today
  from crm.outreach_events_v1 e
  where e.event_type='cold_enqueued'
    and e.metadata->>'campaign_ref'=p_campaign_id
    and (e.created_at at time zone c.business_timezone)::date=v_local_now::date;

  select count(*) into v_scheduled_today
  from crm.outreach_schedule_v1 s
  where s.campaign_ref=p_campaign_id
    and s.state='scheduled'
    and (s.scheduled_for at time zone c.business_timezone)::date=v_local_now::date;

  v_committed:=v_enqueued_today+v_scheduled_today;

  select max(s.scheduled_for) into v_last_slot
  from crm.outreach_schedule_v1 s
  where s.campaign_ref=p_campaign_id
    and s.state in ('scheduled','enqueued')
    and (s.scheduled_for at time zone c.business_timezone)::date=v_local_now::date;

  v_base:=greatest(v_now,v_open_at,coalesce(v_last_slot,v_open_at));
  v_slots:=greatest(0,floor(extract(epoch from (v_close_at-v_base))/p.spacing_seconds)::integer);

  v_to_add:=greatest(0,least(
    p.target_depth-v_queue_depth,
    c.daily_cap-v_committed,
    p.plan_batch_limit,
    v_slots
  ));

  if v_to_add<=0 then
    update crm.penta_marketer_queue_policy_v1 set last_planner_at=v_now,last_queue_depth=v_queue_depth,updated_at=v_now where campaign_id=p_campaign_id;
    return jsonb_build_object(
      'state','NO_CAPACITY','queue_depth',v_queue_depth,'committed_today',v_committed,'daily_cap',c.daily_cap,
      'slots_before_close',v_slots,'ready_inventory',v_inventory,'provider_ingest',v_provider
    );
  end if;

  v_last_slot:=v_base;

  for r in
    select x.contact_id
    from crm.outreach_contacts_v1 x
    where not exists (
      select 1 from crm.outreach_schedule_v1 s
      where s.contact_id=x.contact_id and s.state in ('scheduled','enqueued','sent')
    )
      and coalesce((crm.penta_marketer_eligibility_v1(x.contact_id,'cold')->>'eligible')::boolean,false)
    order by coalesce(x.fit_score,0) desc,coalesce(x.legitimacy_score,0) desc,x.created_at
    limit v_to_add
  loop
    v_slot:=v_last_slot+make_interval(secs=>p.spacing_seconds);
    exit when v_slot>v_close_at;

    insert into crm.outreach_schedule_v1(
      contact_id,send_kind,campaign_ref,offer_ref,scheduled_for,state,created_at,updated_at
    ) values (
      r.contact_id,'cold',p_campaign_id,c.offer_ref,v_slot,'scheduled',v_now,v_now
    );

    v_planned:=v_planned+1;
    v_last_slot:=v_slot;
  end loop;

  select count(*) into v_queue_depth
  from crm.outreach_schedule_v1 s
  where s.campaign_ref=p_campaign_id
    and s.state in ('scheduled','enqueued')
    and (s.scheduled_for at time zone c.business_timezone)::date=v_local_now::date;

  update crm.penta_marketer_queue_policy_v1
  set last_planner_at=v_now,last_queue_depth=v_queue_depth,updated_at=v_now
  where campaign_id=p_campaign_id;

  return jsonb_build_object(
    'state',case when v_planned>0 then 'REPLENISHED' else 'NO_ELIGIBLE_CONTACTS' end,
    'planned',v_planned,
    'queue_depth',v_queue_depth,
    'low_watermark',p.low_watermark,
    'target_depth',p.target_depth,
    'ready_inventory',v_inventory,
    'committed_today',v_committed,
    'daily_cap',c.daily_cap,
    'provider_ingest',v_provider,
    'seed',v_seed,
    'discovery',v_discovery,
    'promote',v_promote
  );
end;
$$;

create or replace function crm.outreach_daily_planner_v1()
returns jsonb
language sql
security definer
set search_path to 'pg_catalog','crm'
as $$
  select crm.penta_marketer_batch_planner_v2();
$$;

create or replace function crm.outreach_scheduler_tick_v1()
returns jsonb
language sql
security definer
set search_path to 'pg_catalog','crm'
as $$
  select crm.penta_marketer_scheduler_tick_v1();
$$;

create or replace function crm.penta_marketer_replenishment_status_v1(
  p_campaign_id text default 'ct.pentamarketer.locticians.claim.20260827.v1'
)
returns jsonb
language plpgsql
stable
security definer
set search_path to 'pg_catalog','crm','integration_control','cron','pg_temp'
as $$
declare
  p crm.penta_marketer_queue_policy_v1%rowtype;
  c crm.penta_marketer_campaign_v1%rowtype;
  v_local_date date;
  v_queue_depth integer;
  v_ready integer;
  v_prospects integer;
  v_discovery jsonb;
  v_crons jsonb;
  v_provider jsonb;
begin
  select * into p from crm.penta_marketer_queue_policy_v1 where campaign_id=p_campaign_id;
  select * into c from crm.penta_marketer_campaign_v1 where campaign_id=p_campaign_id;
  if c.campaign_id is null then return jsonb_build_object('state','HOLD','reason','campaign_not_found'); end if;
  v_local_date:=(now() at time zone c.business_timezone)::date;

  select count(*) into v_queue_depth
  from crm.outreach_schedule_v1 s
  where s.campaign_ref=p_campaign_id
    and s.state in ('scheduled','enqueued')
    and (s.scheduled_for at time zone c.business_timezone)::date=v_local_date;

  select count(*) into v_ready
  from crm.outreach_contacts_v1 x
  where x.relationship_state='prospect'
    and x.research_state='verified'
    and x.claimable_profile
    and x.copy_state='ready'
    and not exists (select 1 from crm.outreach_events_v1 e where e.contact_id=x.contact_id and e.event_type in ('cold_enqueued','cold_sent'))
    and not exists (select 1 from crm.outreach_schedule_v1 s where s.contact_id=x.contact_id and s.state in ('scheduled','enqueued','sent'));

  select count(*) into v_prospects from crm.prospects where source_platform='locticians' and claim_status='claimable';

  select coalesce(jsonb_object_agg(state,n),'{}'::jsonb) into v_discovery
  from (select state,count(*) n from crm.contact_discovery_queue_v1 group by state) x;

  select coalesce(jsonb_agg(jsonb_build_object('jobid',jobid,'jobname',jobname,'schedule',schedule,'command',command,'active',active) order by jobid),'[]'::jsonb)
  into v_crons
  from cron.job
  where jobname in ('ct-outreach-daily-planner-v1','ct-outreach-scheduler-tick-v1','ct-pentamarketer-intake-cycle-v1','ct-locticians-native-monitor-v1');

  select coalesce(jsonb_agg(to_jsonb(x)),'[]'::jsonb) into v_provider
  from (
    select provider_route_id,state,hold_until,last_readback_at,last_readback_enabled,last_readback_http_status,updated_at
    from integration_control.penta_mail_provider_control_v1
    where provider_route_id='mailgun:relay.crownthrive.com'
  ) x;

  return jsonb_build_object(
    'state','OK',
    'campaign',crm.penta_marketer_campaign_status_v1(p_campaign_id),
    'queue_policy',to_jsonb(p),
    'queue_depth',v_queue_depth,
    'ready_unscheduled_inventory',v_ready,
    'claimable_prospects',v_prospects,
    'discovery_queue',v_discovery,
    'mail_provider',v_provider,
    'crons',v_crons
  );
end;
$$;

update crm.penta_marketer_campaign_v1
set metadata =
  (
    metadata
    - 'daily_cap_restored'
    - 'wave5_gate_state'
    - 'wave5_gate_reasserted_at'
    - 'crownthrive_hourly_cap'
    - 'provider_probation_hourly_cap'
    - 'global_monthly_outreach_ceiling'
  )
  || jsonb_build_object(
    'planner_version','2.0.0',
    'planner_mode','watermark_batch_replenishment',
    'queue_low_watermark',40,
    'queue_target_depth',80,
    'planner_batch_limit',50,
    'prospect_seed_batch',200,
    'provider_source_filter','verified=0; then subscription_id=14 and active=2',
    'provider_source_fail_closed',true,
    'provider_key_issue_ref','github:#683',
    'rate_control','penta_mail_provider_adaptive',
    'cron_planner','ct-outreach-daily-planner-v1',
    'cron_scheduler','ct-outreach-scheduler-tick-v1',
    'reconciled_at',now()
  )
where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1';

insert into crm.penta_marketer_campaign_events_v1(campaign_id,event_type,actor_ref,evidence,created_at)
values
(
  'ct.pentamarketer.locticians.claim.20260827.v1',
  'config_updated',
  'PentaMarketer/PentaBuild',
  jsonb_build_object(
    'reason','planner_v2_production_reconciliation',
    'daily_cap',200,
    'monthly_cap',5000,
    'queue_low_watermark',40,
    'queue_target_depth',80,
    'legacy_daily_cap_removed',10,
    'wave5_residue_removed',true,
    'provider_key_issue_ref','github:#683'
  ),
  now()
),
(
  'ct.pentamarketer.locticians.claim.20260827.v1',
  'resumed',
  'PentaMarketer/PentaSELF',
  jsonb_build_object(
    'reason','batch_replenishment_enabled',
    'cold_outreach_enabled',true,
    'planner','crm.penta_marketer_batch_planner_v2',
    'scheduler','crm.penta_marketer_scheduler_tick_v1',
    'provider_transport','PentaMail',
    'provider_source_fail_closed',true
  ),
  now()+interval '1 millisecond'
);

do $$
begin
  if exists (select 1 from cron.job where jobname='ct-outreach-daily-planner-v1') then perform cron.unschedule('ct-outreach-daily-planner-v1'); end if;
  if exists (select 1 from cron.job where jobname='ct-outreach-scheduler-tick-v1') then perform cron.unschedule('ct-outreach-scheduler-tick-v1'); end if;
  if exists (select 1 from cron.job where jobname='ct-pentamarketer-intake-cycle-v1') then perform cron.unschedule('ct-pentamarketer-intake-cycle-v1'); end if;
  if exists (select 1 from cron.job where jobname='ct-locticians-native-monitor-v1') then perform cron.unschedule('ct-locticians-native-monitor-v1'); end if;

  perform cron.schedule(
    'ct-outreach-daily-planner-v1',
    '*/5 * * * *',
    'select crm.penta_marketer_batch_planner_v2();'
  );

  perform cron.schedule(
    'ct-outreach-scheduler-tick-v1',
    '* * * * *',
    'select crm.penta_marketer_scheduler_tick_v1();'
  );

  perform cron.schedule(
    'ct-pentamarketer-intake-cycle-v1',
    '7,22,37,52 * * * *',
    'select crm.locticians_native_action_cycle_v1(25); select crm.penta_marketer_external_email_cycle_v1(25); select crm.penta_marketer_promote_ready_external_email_v1(25); select crm.penta_marketer_service_form_cycle_v1(25);'
  );

  perform cron.schedule(
    'ct-locticians-native-monitor-v1',
    '*/15 * * * *',
    'select crm.locticians_native_monitor_cycle_v1();'
  );
end;
$$;

revoke all on crm.penta_marketer_queue_policy_v1 from anon,authenticated;
grant select,insert,update,delete on crm.penta_marketer_queue_policy_v1 to service_role;
grant execute on function crm.public_http_target_safe_v1(text) to service_role;
grant execute on function crm.locticians_claimable_prospect_ingest_v1(integer) to service_role;
grant execute on function crm.contact_discovery_claim_v1(integer) to service_role;
grant execute on function crm.contact_discovery_process_batch_v1(integer) to service_role;
grant execute on function crm.penta_marketer_promote_researched_prospects_v1(integer) to service_role;
grant execute on function crm.penta_marketer_batch_planner_v2(text) to service_role;
grant execute on function crm.outreach_daily_planner_v1() to service_role;
grant execute on function crm.outreach_scheduler_tick_v1() to service_role;
grant execute on function crm.penta_marketer_replenishment_status_v1(text) to service_role;