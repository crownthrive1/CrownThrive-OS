-- PentaCrawler™ Communications Research Runtime v1
-- Autonomous public-business research and planning with fail-closed commercial delivery.
-- Canonical repository: crownthrive1/CrownThrive-OS

begin;

create table if not exists crm.contact_discovery_queue_v1 (
  queue_id uuid primary key default gen_random_uuid(),
  prospect_id uuid not null references crm.prospects(id) on delete restrict,
  target_url text not null,
  source_kind text not null check (source_kind in ('official_business_site','email_evidence_page','directory_listing')),
  state text not null default 'pending' check (state in ('pending','leased','retry','complete','hold')),
  priority integer not null default 50 check (priority between 0 and 1000),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  max_attempts integer not null default 5 check (max_attempts between 1 and 20),
  available_at timestamptz not null default now(),
  lease_id uuid,
  lease_expires_at timestamptz,
  last_error text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (prospect_id, target_url)
);

create index if not exists contact_discovery_queue_v1_due_idx
  on crm.contact_discovery_queue_v1(state, available_at, priority desc);
create index if not exists contact_discovery_queue_v1_prospect_idx
  on crm.contact_discovery_queue_v1(prospect_id);

alter table crm.contact_discovery_queue_v1 enable row level security;
revoke all on table crm.contact_discovery_queue_v1 from public, anon, authenticated;
grant select, insert, update on table crm.contact_discovery_queue_v1 to service_role;

create table if not exists crm.contact_discovery_observations_v1 (
  observation_id uuid primary key default gen_random_uuid(),
  prospect_id uuid not null references crm.prospects(id) on delete restrict,
  queue_id uuid references crm.contact_discovery_queue_v1(queue_id) on delete restrict,
  source_url text not null,
  source_type text not null,
  observed_email text,
  contact_name text,
  page_title text,
  confidence integer not null default 0 check (confidence between 0 and 100),
  is_public_business_contact boolean not null default false,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  evidence_json jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now(),
  unique (prospect_id, evidence_sha256)
);

create index if not exists contact_discovery_observations_v1_prospect_idx
  on crm.contact_discovery_observations_v1(prospect_id, observed_at desc);
create index if not exists contact_discovery_observations_v1_email_idx
  on crm.contact_discovery_observations_v1(lower(observed_email))
  where observed_email is not null;

alter table crm.contact_discovery_observations_v1 enable row level security;
revoke all on table crm.contact_discovery_observations_v1 from public, anon, authenticated;
grant select, insert on table crm.contact_discovery_observations_v1 to service_role;

create or replace function crm.reject_contact_discovery_observation_mutation_v1()
returns trigger
language plpgsql
set search_path = pg_catalog, crm, pg_temp
as $$
begin
  raise exception 'contact_discovery_observations_v1_is_append_only';
end;
$$;

revoke all on function crm.reject_contact_discovery_observation_mutation_v1() from public;

drop trigger if exists contact_discovery_observations_v1_append_only on crm.contact_discovery_observations_v1;
create trigger contact_discovery_observations_v1_append_only
before update or delete on crm.contact_discovery_observations_v1
for each row execute function crm.reject_contact_discovery_observation_mutation_v1();

create or replace function crm.locticians_research_candidate_v1(p crm.prospects)
returns boolean
language sql
immutable
set search_path = pg_catalog, crm, pg_temp
as $$
  select
    p.source_platform = 'locticians'
    and p.claim_status = 'claimable'
    and lower(coalesce(p.category,'')) !~ '(music|entertainment|partnership|sponsor)'
    and lower(
      coalesce(p.listing_name,'') || ' ' ||
      coalesce(p.category,'') || ' ' ||
      coalesce(p.subcategory,'') || ' ' ||
      coalesce(p.enrichment::text,'')
    ) ~ '(beauty|hair|salon|lash|skin|esthetic|cosmet|wellness|spa|barber|makeup|brow|massage|loctician|locs|locks)';
$$;

revoke all on function crm.locticians_research_candidate_v1(crm.prospects) from public;
grant execute on function crm.locticians_research_candidate_v1(crm.prospects) to service_role;

create or replace function crm.commercial_send_authority_v1(
  p_principal_id text default 'ct.ops.agent.email-attention'
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, crm, chlom_runtime, pg_temp
as $$
declare
  v_lease chlom_runtime.agent_authority_leases_v1%rowtype;
begin
  select * into v_lease
  from chlom_runtime.agent_authority_leases_v1 l
  where l.principal_kind = 'agent'
    and l.principal_id = p_principal_id
    and l.capability = 'commercial_outbound.send'
    and l.resource_type = 'communications_lane'
    and l.resource_id = 'crm.outreach'
    and l.sensitivity_level >= 3
    and l.plaintext_return = false
    and l.key_material_return = false
    and l.issuer_kind = 'founder'
    and l.state = 'active'
    and l.expires_at > clock_timestamp()
    and exists (
      select 1
      from chlom_runtime.dail_events d
      where d.event_type = 'authority.lease.issued'
        and d.entity_type = 'agent_authority_lease'
        and d.entity_id = l.lease_id::text
        and d.approval_id = l.lease_id::text
    )
  order by l.issued_at desc
  limit 1;

  if not found then
    return jsonb_build_object(
      'authorized', false,
      'state', 'HOLD',
      'reason', 'exact_scope_founder_issued_wave5_commercial_authority_missing',
      'principal_id', p_principal_id,
      'capability', 'commercial_outbound.send',
      'resource_type', 'communications_lane',
      'resource_id', 'crm.outreach',
      'sensitivity', 3
    );
  end if;

  return jsonb_build_object(
    'authorized', true,
    'state', 'AUTHORIZED',
    'principal_id', p_principal_id,
    'lease_id', v_lease.lease_id,
    'expires_at', v_lease.expires_at,
    'capability', v_lease.capability,
    'resource_type', v_lease.resource_type,
    'resource_id', v_lease.resource_id,
    'sensitivity', v_lease.sensitivity_level
  );
end;
$$;

revoke all on function crm.commercial_send_authority_v1(text) from public;
grant execute on function crm.commercial_send_authority_v1(text) to service_role;

create or replace function crm.outreach_offer_ready_v1(p_offer_ref text)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, crm, pg_temp
as $$
declare
  o crm.offer_registry%rowtype;
  reasons jsonb := '[]'::jsonb;
begin
  select * into o from crm.offer_registry where offer_key = p_offer_ref;
  if not found then
    return jsonb_build_object('ready',false,'offer_ref',p_offer_ref,'reasons',jsonb_build_array('offer_not_found'));
  end if;

  if current_date < o.start_date then reasons := reasons || '"offer_not_started"'::jsonb; end if;
  if o.expiration_date is not null and current_date > o.expiration_date then reasons := reasons || '"offer_expired"'::jsonb; end if;
  if coalesce(o.public_evidence_state,'') not in ('verified','certified') then reasons := reasons || to_jsonb('public_evidence_' || coalesce(o.public_evidence_state,'missing')); end if;
  if coalesce(o.checkout_verification_state,'') not in ('verified','certified') then reasons := reasons || to_jsonb('checkout_' || coalesce(o.checkout_verification_state,'missing')); end if;
  if coalesce(o.lifecycle_state,'') not in ('configured','active','production') then reasons := reasons || to_jsonb('lifecycle_' || coalesce(o.lifecycle_state,'missing')); end if;

  return jsonb_build_object(
    'ready', jsonb_array_length(reasons)=0,
    'offer_ref', p_offer_ref,
    'reasons', reasons,
    'public_evidence_state', o.public_evidence_state,
    'checkout_verification_state', o.checkout_verification_state,
    'expiration_date', o.expiration_date
  );
end;
$$;

revoke all on function crm.outreach_offer_ready_v1(text) from public;
grant execute on function crm.outreach_offer_ready_v1(text) to service_role;

create or replace function crm.contact_discovery_seed_v1(p_limit integer default 100)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, crm, pg_temp
as $$
declare
  v_count integer := 0;
  v_limit integer := greatest(1, least(coalesce(p_limit,100),500));
begin
  with eligible as (
    select p.*
    from crm.prospects p
    where crm.locticians_research_candidate_v1(p)
    order by case when p.public_email is null then 0 else 1 end, p.lead_score desc, p.created_at
    limit v_limit
  ), targets as (
    select id as prospect_id, email_source_url as target_url, 'email_evidence_page'::text as source_kind, 120 as priority
    from eligible where nullif(btrim(email_source_url),'') is not null
    union all
    select id, website_url, 'official_business_site', case when public_email is null then 110 else 90 end
    from eligible where nullif(btrim(website_url),'') is not null
    union all
    select id, source_listing_url, 'directory_listing', 70
    from eligible where nullif(btrim(source_listing_url),'') is not null
  )
  insert into crm.contact_discovery_queue_v1(prospect_id,target_url,source_kind,priority,state,available_at,metadata)
  select prospect_id,target_url,source_kind,priority,'pending',now(),jsonb_build_object('seed','PentaCrawler','version','1.0.0')
  from targets
  on conflict (prospect_id,target_url) do update set
    source_kind = case when excluded.priority >= crm.contact_discovery_queue_v1.priority then excluded.source_kind else crm.contact_discovery_queue_v1.source_kind end,
    priority = greatest(crm.contact_discovery_queue_v1.priority, excluded.priority),
    state = case
      when crm.contact_discovery_queue_v1.state='complete' and crm.contact_discovery_queue_v1.updated_at < now()-interval '30 days' then 'pending'
      when crm.contact_discovery_queue_v1.state='hold' and crm.contact_discovery_queue_v1.updated_at < now()-interval '30 days' then 'retry'
      else crm.contact_discovery_queue_v1.state
    end,
    available_at = case
      when crm.contact_discovery_queue_v1.state in ('complete','hold') and crm.contact_discovery_queue_v1.updated_at < now()-interval '30 days' then now()
      else crm.contact_discovery_queue_v1.available_at
    end,
    updated_at = now();

  get diagnostics v_count = row_count;
  return jsonb_build_object('state','SEEDED','touched',v_count,'candidate_limit',v_limit);
end;
$$;

revoke all on function crm.contact_discovery_seed_v1(integer) from public;
grant execute on function crm.contact_discovery_seed_v1(integer) to service_role;

create or replace function crm.contact_discovery_claim_v1(p_limit integer default 5)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, crm, pg_temp
as $$
declare
  v_limit integer := greatest(1,least(coalesce(p_limit,5),10));
  v_result jsonb;
begin
  if current_user not in ('postgres','service_role') and coalesce(current_setting('request.jwt.claim.role',true),'') <> 'service_role' then
    raise exception 'service_role_required';
  end if;

  update crm.contact_discovery_queue_v1
  set state='retry', lease_id=null, lease_expires_at=null, available_at=now(), updated_at=now(),
      last_error=coalesce(last_error,'') || case when coalesce(last_error,'')='' then '' else ';' end || 'lease_expired'
  where state='leased' and lease_expires_at <= now();

  with candidates as (
    select q.queue_id
    from crm.contact_discovery_queue_v1 q
    where q.state in ('pending','retry')
      and q.available_at <= now()
      and q.attempt_count < q.max_attempts
    order by q.priority desc, q.available_at, q.created_at
    for update skip locked
    limit v_limit
  ), leased as (
    update crm.contact_discovery_queue_v1 q
    set state='leased', lease_id=gen_random_uuid(), lease_expires_at=now()+interval '5 minutes', updated_at=now()
    from candidates c
    where q.queue_id=c.queue_id
    returning q.*
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'queue_id',l.queue_id,
    'lease_id',l.lease_id,
    'prospect_id',l.prospect_id,
    'target_url',l.target_url,
    'source_kind',l.source_kind,
    'attempt_count',l.attempt_count,
    'max_attempts',l.max_attempts,
    'listing_name',p.listing_name,
    'website_url',p.website_url,
    'source_listing_url',p.source_listing_url,
    'public_email',p.public_email
  ) order by l.priority desc,l.created_at),'[]'::jsonb)
  into v_result
  from leased l join crm.prospects p on p.id=l.prospect_id;

  return v_result;
end;
$$;

revoke all on function crm.contact_discovery_claim_v1(integer) from public;
grant execute on function crm.contact_discovery_claim_v1(integer) to service_role;

create or replace function crm.contact_discovery_complete_v1(
  p_queue_id uuid,
  p_observations jsonb default '[]'::jsonb,
  p_error text default null
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, crm, pg_temp
as $$
declare
  q crm.contact_discovery_queue_v1%rowtype;
  v_obs jsonb;
  v_email text;
  v_hash text;
  v_conf integer;
  v_public boolean;
  v_source_type text;
  v_inserted integer := 0;
  v_best_email text;
  v_best_url text;
begin
  if current_user not in ('postgres','service_role') and coalesce(current_setting('request.jwt.claim.role',true),'') <> 'service_role' then
    raise exception 'service_role_required';
  end if;

  select * into q from crm.contact_discovery_queue_v1 where queue_id=p_queue_id for update;
  if not found then raise exception 'discovery_queue_not_found'; end if;
  if q.state <> 'leased' then raise exception 'discovery_queue_not_leased'; end if;

  if nullif(btrim(coalesce(p_error,'')),'') is not null then
    update crm.contact_discovery_queue_v1
    set attempt_count=attempt_count+1,
        state=case when attempt_count+1 >= max_attempts then 'hold' else 'retry' end,
        available_at=now() + interval '30 minutes' * greatest(1,attempt_count+1),
        lease_id=null,lease_expires_at=null,last_error=left(p_error,2000),updated_at=now()
    where queue_id=p_queue_id;
    return jsonb_build_object('state','RETRY_OR_HOLD','queue_id',p_queue_id,'error',left(p_error,500));
  end if;

  if jsonb_typeof(coalesce(p_observations,'[]'::jsonb)) <> 'array' then raise exception 'observations_must_be_array'; end if;

  for v_obs in select value from jsonb_array_elements(coalesce(p_observations,'[]'::jsonb))
  loop
    v_email := lower(nullif(btrim(v_obs->>'email'),''));
    if v_email is not null and v_email !~ '^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$' then
      continue;
    end if;
    v_hash := lower(coalesce(v_obs->>'evidence_sha256',''));
    if v_hash !~ '^[0-9a-f]{64}$' then continue; end if;
    v_conf := greatest(0,least(coalesce((v_obs->>'confidence')::integer,0),100));
    v_public := coalesce((v_obs->>'is_public_business_contact')::boolean,false);
    v_source_type := coalesce(nullif(v_obs->>'source_type',''),q.source_kind);

    insert into crm.contact_discovery_observations_v1(
      prospect_id,queue_id,source_url,source_type,observed_email,contact_name,page_title,
      confidence,is_public_business_contact,evidence_sha256,evidence_json,observed_at
    ) values (
      q.prospect_id,p_queue_id,coalesce(nullif(v_obs->>'source_url',''),q.target_url),v_source_type,v_email,
      nullif(v_obs->>'contact_name',''),nullif(v_obs->>'page_title',''),v_conf,v_public,v_hash,
      coalesce(v_obs->'evidence','{}'::jsonb),coalesce((v_obs->>'observed_at')::timestamptz,now())
    ) on conflict (prospect_id,evidence_sha256) do nothing;
    if found then
      v_inserted := v_inserted + 1;
      insert into crm.research_evidence(prospect_id,source_url,source_type,observed_claim,evidence_json,observed_at)
      values(
        q.prospect_id,
        coalesce(nullif(v_obs->>'source_url',''),q.target_url),
        'PentaCrawler:'||v_source_type,
        case when v_email is null then 'public_business_contact_scan_no_email_observed' else 'public_business_email_observed:'||v_email end,
        jsonb_build_object('evidence_sha256',v_hash,'confidence',v_conf,'public_business_contact',v_public,'page_title',v_obs->>'page_title','evidence',coalesce(v_obs->'evidence','{}'::jsonb)),
        coalesce((v_obs->>'observed_at')::timestamptz,now())
      );
    end if;
  end loop;

  select o.observed_email,o.source_url into v_best_email,v_best_url
  from crm.contact_discovery_observations_v1 o
  where o.prospect_id=q.prospect_id
    and o.observed_email is not null
    and o.is_public_business_contact
    and o.confidence >= 85
    and o.source_type in ('official_business_site','email_evidence_page','official_contact_page','official_booking_page')
  order by o.observed_at desc,o.confidence desc
  limit 1;

  update crm.prospects p
  set public_email=coalesce(v_best_email,p.public_email),
      email_source_url=coalesce(v_best_url,p.email_source_url),
      last_researched_at=now(),
      enrichment=p.enrichment || jsonb_build_object(
        'penta_crawler_last_verified_at',now(),
        'penta_crawler_last_queue_id',p_queue_id,
        'penta_crawler_verified_email',v_best_email,
        'penta_crawler_version','1.0.0'
      ),
      updated_at=now()
  where p.id=q.prospect_id;

  update crm.contact_discovery_queue_v1
  set state='complete',attempt_count=attempt_count+1,lease_id=null,lease_expires_at=null,last_error=null,
      metadata=metadata||jsonb_build_object('completed_at',now(),'observation_count',v_inserted),updated_at=now()
  where queue_id=p_queue_id;

  return jsonb_build_object('state','COMPLETE','queue_id',p_queue_id,'observations_inserted',v_inserted,'verified_email',v_best_email);
end;
$$;

revoke all on function crm.contact_discovery_complete_v1(uuid,jsonb,text) from public;
grant execute on function crm.contact_discovery_complete_v1(uuid,jsonb,text) to service_role;

create or replace function crm.promote_verified_prospects_v1(p_limit integer default 100)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, crm, pg_temp
as $$
declare
  cfg crm.outbound_config%rowtype;
  off crm.offer_registry%rowtype;
  offer_state jsonb;
  offer_ready boolean := false;
  v_count integer := 0;
  v_limit integer := greatest(1,least(coalesce(p_limit,100),500));
begin
  select * into cfg from crm.outbound_config where singleton=true;
  select * into off from crm.offer_registry where offer_key='locticians.claimmonth50.v1';
  offer_state := crm.outreach_offer_ready_v1('locticians.claimmonth50.v1');
  offer_ready := coalesce((offer_state->>'ready')::boolean,false);

  insert into crm.outreach_contacts_v1(
    email,display_name,organization,source_url,research_state,legitimacy_score,fit_score,research_evidence,
    claimable_profile,relationship_state,copy_state,draft_subject,draft_body,metadata,created_at,updated_at
  )
  select
    lower(p.public_email),
    nullif(p.enrichment->>'verified_public_contact_name',''),
    p.listing_name,
    coalesce(p.email_source_url,p.website_url,p.source_listing_url),
    'verified',
    case when exists(
      select 1 from crm.contact_discovery_observations_v1 o
      where o.prospect_id=p.id and o.is_public_business_contact and o.confidence>=85 and o.observed_email is not null
    ) then 95 else 82 end,
    greatest(60,least(100,case when p.lead_score>0 then p.lead_score else 75 end)),
    jsonb_build_array(jsonb_build_object(
      'prospect_id',p.id,
      'source_listing_url',p.source_listing_url,
      'email_source_url',p.email_source_url,
      'last_researched_at',p.last_researched_at,
      'penta_crawler_verified',exists(select 1 from crm.contact_discovery_observations_v1 o where o.prospect_id=p.id and o.is_public_business_contact and o.confidence>=85)
    )),
    true,
    'prospect',
    case when offer_ready then 'ready' else 'hold' end,
    'Claim your '||p.listing_name||' profile on Locticians',
    'Hello'||case when nullif(p.enrichment->>'verified_public_contact_name','') is not null then ' '||(p.enrichment->>'verified_public_contact_name') else '' end||E',\n\n'||
    'I’m reaching out from CrownThrive about the public '||p.listing_name||' profile on Locticians. The profile is currently listed as claimable, and this business contact was sourced from a public business-owned page.'||E'\n\n'||
    'Claiming the profile lets your team review and maintain its listing details, services, contact information, and discovery presence:'||E'\n'||coalesce(p.source_listing_url,'')||E'\n\n'||
    case when offer_ready then coalesce(off.public_copy,'')||E'\n\n' else '' end||
    coalesce(cfg.optout_copy,'Reply if this is not the right contact or if you would rather not receive messages like this.')||E'\n\n'||
    'CrownThrive'||E'\n'||coalesce(cfg.verified_postal_address,''),
    jsonb_build_object(
      'prospect_id',p.id,
      'source_platform',p.source_platform,
      'offer_ref','locticians.claimmonth50.v1',
      'offer_ready',offer_ready,
      'research_runtime','ct.penta.crawler.communications.v1',
      'send_authority_inherited',false
    ),
    now(),now()
  from crm.prospects p
  where crm.locticians_research_candidate_v1(p)
    and nullif(btrim(p.public_email),'') is not null
    and p.risk_score <= 20
    and p.compliance_status <> 'suppressed'
    and not exists (
      select 1 from crm.suppression_list s
      where (s.expires_at is null or s.expires_at>now())
        and (
          lower(coalesce(s.email,''))=lower(p.public_email)
          or lower(coalesce(s.domain,''))=lower(split_part(p.public_email,'@',2))
        )
    )
    and lower(coalesce(p.enrichment::text,'')) not like '%secondary_source_email_requires_reverification%'
    and (
      coalesce(p.enrichment->>'email_source_type','') in ('official_website','official_booking_page','official_contact_page')
      or exists (
        select 1 from crm.contact_discovery_observations_v1 o
        where o.prospect_id=p.id and o.is_public_business_contact and o.confidence>=85 and o.observed_email is not null
      )
      or (
        p.email_source_url is not null
        and p.website_url is not null
        and lower(split_part(regexp_replace(p.email_source_url,'^https?://','','i'), '/', 1)) = lower(split_part(regexp_replace(p.website_url,'^https?://','','i'), '/', 1))
      )
    )
  order by p.lead_score desc,p.created_at
  limit v_limit
  on conflict ((lower(email))) do update set
    display_name=coalesce(excluded.display_name,crm.outreach_contacts_v1.display_name),
    organization=excluded.organization,
    source_url=excluded.source_url,
    research_state='verified',
    legitimacy_score=greatest(coalesce(crm.outreach_contacts_v1.legitimacy_score,0),coalesce(excluded.legitimacy_score,0)),
    fit_score=greatest(coalesce(crm.outreach_contacts_v1.fit_score,0),coalesce(excluded.fit_score,0)),
    research_evidence=crm.outreach_contacts_v1.research_evidence||excluded.research_evidence,
    claimable_profile=true,
    copy_state=case when crm.outreach_contacts_v1.copy_state='ready' then 'ready' else excluded.copy_state end,
    draft_subject=case when crm.outreach_contacts_v1.copy_state='ready' then crm.outreach_contacts_v1.draft_subject else excluded.draft_subject end,
    draft_body=case when crm.outreach_contacts_v1.copy_state='ready' then crm.outreach_contacts_v1.draft_body else excluded.draft_body end,
    metadata=crm.outreach_contacts_v1.metadata||excluded.metadata,
    updated_at=now();

  get diagnostics v_count = row_count;
  return jsonb_build_object('state','PROMOTED_RESEARCH_ONLY','contacts_touched',v_count,'offer_ready',offer_ready,'offer_state',offer_state,'send_authority_inherited',false);
end;
$$;

revoke all on function crm.promote_verified_prospects_v1(integer) from public;
grant execute on function crm.promote_verified_prospects_v1(integer) to service_role;

create or replace function crm.outreach_eligibility_v1(p_contact_id uuid, p_send_kind text)
returns jsonb
language plpgsql
security definer
set search_path to 'crm','public','chlom_runtime','pg_temp'
as $$
declare
  c crm.outreach_contacts_v1%rowtype;
  cfg crm.outbound_config%rowtype;
  stop_reason text;
  month_count integer;
  recent_nurture_count integer;
  maintenance jsonb;
  authority jsonb;
  eligible boolean := false;
  reasons jsonb := '[]'::jsonb;
begin
  select * into c from crm.outreach_contacts_v1 where contact_id=p_contact_id;
  if not found then return jsonb_build_object('eligible',false,'reasons',jsonb_build_array('contact_not_found')); end if;
  select * into cfg from crm.outbound_config where singleton=true;
  maintenance := chlom_runtime.maintenance_state_v1();
  authority := crm.commercial_send_authority_v1('ct.ops.agent.email-attention');
  if coalesce((maintenance->>'maintenance_active')::boolean,false) then reasons := reasons || '"maintenance_active"'::jsonb; end if;
  if p_send_kind in ('cold','nurture') and not coalesce((authority->>'authorized')::boolean,false) then reasons := reasons || '"commercial_send_authority_missing"'::jsonb; end if;
  stop_reason := crm.outreach_stop_reason_v1(c);
  if stop_reason is not null then reasons := reasons || to_jsonb(stop_reason); end if;

  if p_send_kind='cold' then
    if not cfg.cold_outreach_enabled then reasons := reasons || '"cold_outreach_disabled"'::jsonb; end if;
    if nullif(trim(cfg.verified_postal_address),'') is null then reasons := reasons || '"postal_address_missing"'::jsonb; end if;
    if cfg.research_required and c.research_state <> 'verified' then reasons := reasons || '"research_not_verified"'::jsonb; end if;
    if coalesce(c.legitimacy_score,0) < 70 then reasons := reasons || '"legitimacy_below_70"'::jsonb; end if;
    if coalesce(c.fit_score,0) < 60 then reasons := reasons || '"fit_below_60"'::jsonb; end if;
    if cfg.require_claimable_profile and not c.claimable_profile then reasons := reasons || '"profile_not_claimable"'::jsonb; end if;
    if c.copy_state <> 'ready' or nullif(trim(c.draft_subject),'') is null or nullif(trim(c.draft_body),'') is null then reasons := reasons || '"copy_not_ready"'::jsonb; end if;
    select count(*) into month_count from crm.outreach_events_v1 where event_type='cold_enqueued' and created_at>=date_trunc('month',now()) and created_at<date_trunc('month',now())+interval '1 month';
    if month_count >= cfg.max_new_cold_emails_per_month then reasons := reasons || '"monthly_cap_reached"'::jsonb; end if;
    if exists(select 1 from crm.outreach_events_v1 where contact_id=p_contact_id and event_type='cold_enqueued') then reasons := reasons || '"cold_already_attempted_for_contact"'::jsonb; end if;
  elsif p_send_kind='nurture' then
    if c.relationship_state not in ('engaged','consented','subscriber','customer','partner','former_customer') then reasons := reasons || '"relationship_not_nurture_eligible"'::jsonb; end if;
    if c.copy_state <> 'ready' or nullif(trim(c.draft_subject),'') is null or nullif(trim(c.draft_body),'') is null then reasons := reasons || '"copy_not_ready"'::jsonb; end if;
    select count(*) into recent_nurture_count from crm.outreach_events_v1 where contact_id=p_contact_id and event_type in ('nurture_enqueued','nurture_sent') and created_at>=now()-make_interval(hours=>cfg.min_nurture_interval_hours);
    if recent_nurture_count>0 then reasons := reasons || '"nurture_frequency_hold"'::jsonb; end if;
  else
    reasons := reasons || '"invalid_send_kind"'::jsonb;
  end if;

  eligible := jsonb_array_length(reasons)=0;
  return jsonb_build_object('eligible',eligible,'send_kind',p_send_kind,'reasons',reasons,'authority',authority,'cold_month_count',coalesce(month_count,0),'cold_month_cap',cfg.max_new_cold_emails_per_month,'nurture_unlimited',cfg.nurture_unlimited);
end;
$$;

create or replace function crm.outreach_daily_planner_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'crm','public','chlom_runtime','pg_temp'
as $$
declare
  cfg crm.outbound_config%rowtype;
  local_now timestamp;
  c record;
  scheduled_id uuid;
  month_used integer;
  seed_state jsonb;
  promote_state jsonb;
  authority jsonb;
  offer_state jsonb;
begin
  select * into cfg from crm.outbound_config where singleton=true;
  if coalesce((chlom_runtime.maintenance_state_v1()->>'maintenance_active')::boolean,false) then return jsonb_build_object('state','HOLD','reason','maintenance_active'); end if;

  seed_state := crm.contact_discovery_seed_v1(100);
  promote_state := crm.promote_verified_prospects_v1(100);
  authority := crm.commercial_send_authority_v1('ct.ops.agent.email-attention');
  offer_state := crm.outreach_offer_ready_v1('locticians.claimmonth50.v1');

  if not cfg.cold_outreach_enabled then return jsonb_build_object('state','RESEARCH_ACTIVE_SEND_HOLD','reason','cold_outreach_disabled','discovery',seed_state,'promotion',promote_state,'authority',authority,'offer',offer_state); end if;
  if not coalesce((authority->>'authorized')::boolean,false) then return jsonb_build_object('state','RESEARCH_ACTIVE_SEND_HOLD','reason','commercial_send_authority_missing','discovery',seed_state,'promotion',promote_state,'authority',authority,'offer',offer_state); end if;
  if not coalesce((offer_state->>'ready')::boolean,false) then return jsonb_build_object('state','RESEARCH_ACTIVE_SEND_HOLD','reason','offer_evidence_not_ready','discovery',seed_state,'promotion',promote_state,'authority',authority,'offer',offer_state); end if;

  local_now := now() at time zone cfg.business_timezone;
  if extract(isodow from local_now)>5 then return jsonb_build_object('state','WEEKEND_HOLD','discovery',seed_state,'promotion',promote_state); end if;
  if exists(select 1 from crm.outreach_schedule_v1 where send_kind='cold' and (scheduled_for at time zone cfg.business_timezone)::date=local_now::date and state in ('scheduled','enqueued','sent')) then return jsonb_build_object('state','TODAY_ALREADY_PLANNED','discovery',seed_state,'promotion',promote_state); end if;
  select count(*) into month_used from crm.outreach_events_v1 where event_type='cold_enqueued' and created_at>=date_trunc('month',now()) and created_at<date_trunc('month',now())+interval '1 month';
  if month_used>=cfg.max_new_cold_emails_per_month then return jsonb_build_object('state','MONTHLY_CAP_REACHED','used',month_used,'cap',cfg.max_new_cold_emails_per_month,'discovery',seed_state,'promotion',promote_state); end if;
  select x.contact_id into c from crm.outreach_contacts_v1 x where coalesce((crm.outreach_eligibility_v1(x.contact_id,'cold')->>'eligible')::boolean,false) order by coalesce(x.fit_score,0) desc,coalesce(x.legitimacy_score,0) desc,x.created_at limit 1;
  if not found then return jsonb_build_object('state','NO_ELIGIBLE_RESEARCHED_LEAD','used',month_used,'cap',cfg.max_new_cold_emails_per_month,'discovery',seed_state,'promotion',promote_state); end if;
  insert into crm.outreach_schedule_v1(contact_id,send_kind,campaign_ref,offer_ref,scheduled_for) values(c.contact_id,'cold','ct.ops.agent.email-attention','locticians.claimmonth50.v1',now()+interval '10 minutes') returning schedule_id into scheduled_id;
  return jsonb_build_object('state','PLANNED','schedule_id',scheduled_id,'used',month_used,'cap',cfg.max_new_cold_emails_per_month,'discovery',seed_state,'promotion',promote_state,'authority',authority,'offer',offer_state);
end;
$$;

create or replace function crm.outreach_scheduler_tick_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'crm','public','chlom_runtime','pg_temp'
as $$
declare
  r record;
  e jsonb;
  offer_state jsonb;
  mid uuid;
  enqueued integer := 0;
  held integer := 0;
begin
  if coalesce((chlom_runtime.maintenance_state_v1()->>'maintenance_active')::boolean,false) then return jsonb_build_object('state','READ_ONLY_MAINTENANCE','enqueued',0,'held',0); end if;
  for r in
    select s.*,c.email,c.draft_subject,c.draft_body
    from crm.outreach_schedule_v1 s join crm.outreach_contacts_v1 c using(contact_id)
    where s.state='scheduled' and s.scheduled_for<=now()
    order by s.scheduled_for,s.created_at
    for update of s skip locked
  loop
    e := crm.outreach_eligibility_v1(r.contact_id,r.send_kind);
    if r.offer_ref is not null then
      offer_state := crm.outreach_offer_ready_v1(r.offer_ref);
      if not coalesce((offer_state->>'ready')::boolean,false) then
        e := jsonb_set(e,'{eligible}','false'::jsonb,true);
        e := jsonb_set(e,'{reasons}',coalesce(e->'reasons','[]'::jsonb)||'"offer_evidence_not_ready"'::jsonb,true);
        e := e||jsonb_build_object('offer',offer_state);
      end if;
    end if;
    if coalesce((e->>'eligible')::boolean,false) then
      mid := gen_random_uuid();
      insert into public.penta_mail_outbox_v1(message_id,message_type,severity,recipient,subject,body_text,dedupe_key,metadata,state,attempt_count,max_attempts,available_at,created_at,updated_at)
      values(mid,case when r.send_kind='cold' then 'sales_outreach' else 'lead_nurture' end,'INFO',r.email,r.draft_subject,r.draft_body,
        'crm-outreach:'||r.schedule_id::text,
        jsonb_build_object('schedule_id',r.schedule_id,'contact_id',r.contact_id,'campaign_ref',r.campaign_ref,'offer_ref',r.offer_ref,'send_kind',r.send_kind,'archive_policy','minimal_metadata_only','commercial_authority_checked',true),
        'pending',0,3,now(),now(),now());
      update crm.outreach_schedule_v1 set state='enqueued',message_id=mid,updated_at=now() where schedule_id=r.schedule_id;
      insert into crm.outreach_events_v1(contact_id,schedule_id,event_type,metadata) values(r.contact_id,r.schedule_id,case when r.send_kind='cold' then 'cold_enqueued' else 'nurture_enqueued' end,jsonb_build_object('message_id',mid));
      enqueued := enqueued+1;
    else
      update crm.outreach_schedule_v1 set state='hold',reason=e::text,updated_at=now() where schedule_id=r.schedule_id;
      held := held+1;
    end if;
  end loop;
  return jsonb_build_object('state','COMPLETE','enqueued',enqueued,'held',held,'authority',crm.commercial_send_authority_v1('ct.ops.agent.email-attention'));
end;
$$;

create or replace function crm.outreach_control_plane_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, crm, public, chlom_runtime, pg_temp
as $$
declare
  v_plan jsonb;
  v_due integer;
  v_queued integer;
begin
  v_plan := crm.outreach_daily_planner_v1();
  select count(*) into v_due from crm.contact_discovery_queue_v1 where state in ('pending','retry') and available_at<=now();
  select count(*) into v_queued from crm.outreach_schedule_v1 where state='scheduled' and scheduled_for<=now();
  return jsonb_build_object(
    'software','PentaCrawler Communications Research Runtime',
    'version','1.0.0',
    'state','PRODUCTION_FAIL_CLOSED',
    'planner',v_plan,
    'discovery_due',v_due,
    'commercial_schedule_due',v_queued,
    'commercial_authority',crm.commercial_send_authority_v1('ct.ops.agent.email-attention'),
    'offer',crm.outreach_offer_ready_v1('locticians.claimmonth50.v1')
  );
end;
$$;

revoke all on function crm.outreach_control_plane_v1() from public;
grant execute on function crm.outreach_control_plane_v1() to service_role;

-- Delivery boundary: commercial mail remains unclaimable without an exact-scope founder-issued lease.
create or replace function public.penta_mail_claim_outbox_v2(p_limit integer default 2)
returns setof public.penta_mail_outbox_v1
language plpgsql
security definer
set search_path to 'pg_catalog','public','integration_control'
as $$
declare
  v_status jsonb;
  v_now timestamptz := clock_timestamp();
  v_limit integer := greatest(1,least(coalesce(p_limit,2),2));
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform pg_advisory_xact_lock(hashtext('public.penta_mail_claim_outbox_v2'));
  perform integration_control.penta_mail_reconcile_trigger_probation_v1();
  v_status := public.penta_mail_provider_status_v1(null);
  if v_status->>'route_state' not in ('closed','controlled_release') then return; end if;
  update public.penta_mail_outbox_v1 o
  set state='queued',available_at=greatest(o.available_at,v_now),metadata=o.metadata||jsonb_build_object('provider_release_mode','controlled','trigger_probation_expired_at',v_now),updated_at=v_now
  where o.state='held'
    and o.metadata->>'provider_hold_policy'='ct.pentamailer.policy.mailgun-delivery-resilience.v1@1.0.0'
    and not exists(select 1 from integration_control.penta_mail_trigger_probation_v1 p where p.trigger_ref=o.trigger_ref and p.probation_until>v_now);
  update public.penta_mail_outbox_v1
  set state='retry',lease_id=null,lease_expires_at=null,available_at=greatest(available_at,v_now),metadata=metadata||jsonb_build_object('lease_recovered_at',v_now),updated_at=v_now
  where state='dispatching' and lease_expires_at<=v_now;
  return query
  with candidates as (
    select o.message_id
    from public.penta_mail_outbox_v1 o
    where o.state in ('queued','pending','retry')
      and o.available_at<=v_now
      and not exists(select 1 from integration_control.penta_mail_trigger_probation_v1 p where p.trigger_ref=o.trigger_ref and p.probation_until>v_now)
      and (
        lower(o.message_type) not in ('sales_outreach','lead_nurture','locticians_claim')
        or coalesce((crm.commercial_send_authority_v1('ct.ops.agent.email-attention')->>'authorized')::boolean,false)
      )
    order by case upper(o.severity) when 'CRITICAL' then 1 when 'HIGH' then 2 when 'MEDIUM' then 3 else 4 end,o.created_at asc
    for update skip locked
    limit v_limit
  ), leases as (
    select message_id,gen_random_uuid() as lease_id from candidates
  )
  update public.penta_mail_outbox_v1 o
  set state='dispatching',lease_id=l.lease_id,lease_expires_at=v_now+interval '5 minutes',metadata=o.metadata||jsonb_build_object('claimed_at',v_now,'controlled_release_batch_limit',2),updated_at=v_now
  from leases l where o.message_id=l.message_id returning o.*;
end;
$$;

create or replace function public.penta_mail_claim_outbox_v3(p_limit integer default 2)
returns setof public.penta_mail_outbox_v1
language plpgsql
security definer
set search_path to 'pg_catalog','public','integration_control'
as $$
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  return query select * from public.penta_mail_claim_outbox_v2(least(coalesce(p_limit,2),2));
end;
$$;

insert into public.penta_system_registry(
  system_key,canonical_name,category,purpose,authority_boundary,risk_ceiling,maturity,version,public_exposure,docs_ref,runtime_ref,metadata,last_verified_at,updated_at
) values (
  'ct.penta.crawler.communications.v1',
  'PentaCrawler™ Communications Research Runtime',
  'communications_research',
  'Autonomously discover and revalidate public business contact evidence, classify Locticians research candidates, promote verified CRM research records, and feed the existing communications control plane.',
  'Research and planning only by default. No commercial delivery authority is inherited. Commercial send requires a D3 exact-scope founder-issued CHLOM authority lease plus verified offer evidence and existing compliance gates.',
  'D3','production','1.0.0',false,
  'docs/penta/pentacrawler-communications-research-runtime-v1.md',
  'supabase/functions/penta-crawler',
  jsonb_build_object('canonical_repo','crownthrive1/CrownThrive-OS','canonical_agent','ct.ops.agent.email-attention','external_scheduler_slots_added',0,'wave5_required_for_commercial_send',true,'provider_write_authority_inherited',false,'evidence_ledger','DAIL + crm.research_evidence'),
  now(),now()
)
on conflict (system_key) do update set
  canonical_name=excluded.canonical_name,category=excluded.category,purpose=excluded.purpose,authority_boundary=excluded.authority_boundary,
  risk_ceiling=excluded.risk_ceiling,maturity=excluded.maturity,version=excluded.version,public_exposure=excluded.public_exposure,
  docs_ref=excluded.docs_ref,runtime_ref=excluded.runtime_ref,metadata=public.penta_system_registry.metadata||excluded.metadata,last_verified_at=now(),updated_at=now();

update chlom_runtime.automation_agent_bindings
set metadata = metadata || jsonb_build_object(
      'communications_research_runtime','ct.penta.crawler.communications.v1',
      'communications_control_plane_rpc','crm.outreach_control_plane_v1',
      'website_discovery_rpc','crm.contact_discovery_claim_v1',
      'website_discovery_completion_rpc','crm.contact_discovery_complete_v1',
      'external_scheduler_slots_added',0,
      'outbound_authority_added',false,
      'wave5_mutation_required_for_outbound',true,
      'research_autonomy','ACTIVE_FAIL_CLOSED_DELIVERY'
    ),
    updated_at=now()
where binding_id='ct.automation.email-attention.v1'
  and canonical_agent_id='ct.ops.agent.email-attention';

commit;
