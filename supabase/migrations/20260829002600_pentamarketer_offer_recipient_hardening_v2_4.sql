-- Production follow-up for the Locticians PentaMarketer replenishment fabric.
-- Supersedes the hot-applied offer-gate and recipient-validation fixes with
-- an idempotent repository projection that runs after batch replenishment v2.2.

create or replace function crm.penta_marketer_offer_safe_ready_v1(
  p_offer_ref text default 'locticians.claimmonth50.v1',
  p_campaign_id text default 'ct.pentamarketer.locticians.claim.20260827.v1'
)
returns jsonb
language plpgsql
stable
security definer
set search_path to 'pg_catalog','crm','pg_temp'
as $function$
declare
  o crm.offer_registry%rowtype;
  c crm.penta_marketer_campaign_v1%rowtype;
  normalized text;
  reasons jsonb:='[]'::jsonb;
  scope_state text;
  checkout_deferred_safely boolean:=false;
begin
  select * into o from crm.offer_registry where offer_key=p_offer_ref;
  if not found then
    return jsonb_build_object('ready',false,'mode','HOLD','reasons',jsonb_build_array('offer_not_found'));
  end if;

  select * into c from crm.penta_marketer_campaign_v1 where campaign_id=p_campaign_id;
  if not found then
    return jsonb_build_object('ready',false,'mode','HOLD','reasons',jsonb_build_array('campaign_not_found'));
  end if;

  normalized:=lower(regexp_replace(coalesce(o.public_copy,''),'\s+',' ','g'));
  scope_state:=coalesce(o.evidence#>>'{resolved_public_scope,state}','');

  if current_date<o.start_date then reasons:=reasons||'"offer_not_started"'::jsonb; end if;
  if o.expiration_date is not null and current_date>o.expiration_date then reasons:=reasons||'"offer_expired"'::jsonb; end if;
  if coalesce(o.lifecycle_state,'') not in ('configured','active','production') then reasons:=reasons||to_jsonb('lifecycle_'||coalesce(o.lifecycle_state,'missing')); end if;
  if coalesce(o.public_evidence_state,'')<>'verified' then reasons:=reasons||'"public_evidence_not_verified"'::jsonb; end if;
  if scope_state<>'verified' then reasons:=reasons||'"public_scope_not_verified"'::jsonb; end if;
  if coalesce(o.coupon_code,'')<>'CLAIMMONTH50' then reasons:=reasons||'"coupon_code_mismatch"'::jsonb; end if;
  if coalesce(o.discount_type,'')<>'percentage' or coalesce(o.discount_value,0)<>50 then reasons:=reasons||'"discount_value_mismatch"'::jsonb; end if;
  if nullif(btrim(o.public_copy),'') is null then reasons:=reasons||'"public_copy_missing"'::jsonb; end if;

  if position('claimmonth50' in normalized)=0 then reasons:=reasons||'"coupon_missing_from_public_copy"'::jsonb; end if;
  if position('50% off' in normalized)=0 then reasons:=reasons||'"discount_missing_from_public_copy"'::jsonb; end if;
  if position('community+ member' in normalized)=0 or position('basic' in normalized)=0 then reasons:=reasons||'"verified_public_plan_scope_missing"'::jsonb; end if;

  checkout_deferred_safely :=
    position('checkout' in normalized)>0
    and (
      position('verify your eligible plan' in normalized)>0
      or position('exact eligibility' in normalized)>0
      or position('exact eligibility and current terms' in normalized)>0
      or position('exact eligibility and terms' in normalized)>0
    );

  if coalesce(o.checkout_verification_state,'')<>'verified' and not checkout_deferred_safely then
    reasons:=reasons||'"checkout_pending_without_safe_deferral"'::jsonb;
  end if;

  if normalized like '%all plans%'
     or normalized like '%lifetime discount%'
     or normalized like '%guaranteed recurring duration%'
     or normalized like '%higher-tier savings%' then
    reasons:=reasons||'"unsupported_broad_claim_present"'::jsonb;
  end if;

  return jsonb_build_object(
    'ready',jsonb_array_length(reasons)=0,
    'mode',case when jsonb_array_length(reasons)=0 then 'SAFE_CONFLICT_COPY_ONLY' else 'HOLD' end,
    'offer_ref',p_offer_ref,
    'coupon_code',o.coupon_code,
    'public_copy',o.public_copy,
    'public_evidence_state',o.public_evidence_state,
    'checkout_verification_state',o.checkout_verification_state,
    'resolved_public_scope_state',scope_state,
    'checkout_deferred_safely',checkout_deferred_safely,
    'evidence_states_preserved',true,
    'verified_public_scope_claimed',true,
    'broader_plan_scope_claimed',false,
    'scarcity_claimed',false,
    'reasons',reasons
  );
end;
$function$;

update crm.penta_marketer_campaign_v1
set required_safe_phrases=array['CLAIMMONTH50','checkout']::text[],
    metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
      'offer_gate_mode','structured_verified_evidence',
      'offer_gate_version','2.4.0',
      'offer_gate_reconciled_at',now()
    )
where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1';

update crm.outreach_contacts_v1 c
set draft_body=
      substring(c.draft_body from 1 for position('Current promotion:' in c.draft_body)-1)
      ||'Current promotion: '||o.public_copy
      ||substring(c.draft_body from position(E'\n\nPromotional message from CrownThrive.' in c.draft_body)),
    metadata=coalesce(c.metadata,'{}'::jsonb)||jsonb_build_object(
      'offer_copy_mode','canonical_verified_public_copy',
      'offer_copy_reconciled_at',now(),
      'offer_gate_version','2.4.0'
    ),
    updated_at=now()
from crm.offer_registry o
where o.offer_key='locticians.claimmonth50.v1'
  and c.metadata->>'campaign_ref'='ct.pentamarketer.locticians.claim.20260827.v1'
  and position('Current promotion:' in coalesce(c.draft_body,''))>0
  and position(E'\n\nPromotional message from CrownThrive.' in coalesce(c.draft_body,''))>0
  and not exists (
    select 1 from crm.outreach_events_v1 e
    where e.contact_id=c.contact_id and e.event_type in ('cold_enqueued','cold_sent')
  );

create or replace function crm.public_business_email_safe_v2(p_email text)
returns boolean
language sql
immutable
set search_path to 'pg_catalog'
as $function$
  with e as (
    select lower(btrim(coalesce(p_email,''))) as email
  ), parts as (
    select email,split_part(email,'@',1) as local_part,split_part(email,'@',2) as domain
    from e
  ), parsed as (
    select email,local_part,domain,reverse(split_part(reverse(domain),'.',1)) as tld
    from parts
  )
  select
    email ~ '^[a-z0-9.!#$%&''*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,63}$'
    and local_part !~ '^[.-]|[.-]$'
    and domain !~ '\.\.|^-|-$'
    and email not in ('user@domain.com','email@example.com','name@example.com')
    and domain !~ '(wixpress|sentry|ndiscovered|example|domain\.com|w3\.org|cloudflare|schema\.org|wordpress|shopify)'
    and tld not in ('png','jpg','jpeg','gif','svg','webp','ico','css','js','json','xml','pdf','woff','woff2','ttf','eot','map')
    and local_part !~ '^(instagram|facebook|twitter|x|linkedin|youtube|tiktok|pinterest)[._+\-]*$'
  from parsed;
$function$;

create or replace function crm.penta_marketer_eligibility_v1(
  p_contact_id uuid,
  p_send_kind text default 'cold'
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','crm','chlom_runtime','pg_temp'
as $function$
declare
  c crm.outreach_contacts_v1%rowtype;
  p crm.prospects%rowtype;
  cfg crm.outbound_config%rowtype;
  campaign jsonb;
  offer_state jsonb;
  stop_reason text;
  reasons jsonb:='[]'::jsonb;
  canonical_offer_copy text;
begin
  select * into c from crm.outreach_contacts_v1 where contact_id=p_contact_id;
  if not found then return jsonb_build_object('eligible',false,'reasons',jsonb_build_array('contact_not_found')); end if;

  select * into cfg from crm.outbound_config where singleton=true;
  campaign:=crm.penta_marketer_campaign_status_v1();
  offer_state:=crm.penta_marketer_offer_safe_ready_v1();
  stop_reason:=crm.outreach_stop_reason_v1(c);
  canonical_offer_copy:=nullif(btrim(coalesce(offer_state->>'public_copy','')),'');

  if p_send_kind<>'cold' then reasons:=reasons||'"invalid_send_kind"'::jsonb; end if;
  if not coalesce((campaign->>'active')::boolean,false) then reasons:=reasons||'"campaign_authority_inactive"'::jsonb; end if;
  if not coalesce((offer_state->>'ready')::boolean,false) then reasons:=reasons||'"safe_offer_not_ready"'::jsonb; end if;
  if stop_reason is not null then reasons:=reasons||to_jsonb(stop_reason); end if;
  if not crm.public_business_email_safe_v2(c.email) then reasons:=reasons||'"unsafe_recipient_email"'::jsonb; end if;
  if c.research_state<>'verified' then reasons:=reasons||'"research_not_verified"'::jsonb; end if;
  if coalesce(c.legitimacy_score,0)<85 then reasons:=reasons||'"legitimacy_below_85"'::jsonb; end if;
  if coalesce(c.fit_score,0)<60 then reasons:=reasons||'"fit_below_60"'::jsonb; end if;
  if not c.claimable_profile then reasons:=reasons||'"profile_not_claimable"'::jsonb; end if;
  if c.copy_state<>'ready' or nullif(btrim(c.draft_subject),'') is null or nullif(btrim(c.draft_body),'') is null then reasons:=reasons||'"copy_not_ready"'::jsonb; end if;
  if canonical_offer_copy is null or position(lower(canonical_offer_copy) in lower(coalesce(c.draft_body,'')))=0 then reasons:=reasons||'"canonical_offer_copy_missing"'::jsonb; end if;
  if c.draft_body not like '%'||cfg.verified_postal_address||'%' then reasons:=reasons||'"postal_address_missing_from_copy"'::jsonb; end if;
  if lower(c.draft_body) not like '%promotional message from crownthrive%' then reasons:=reasons||'"ad_identification_missing"'::jsonb; end if;
  if lower(c.draft_body) not like '%reply opt out%' then reasons:=reasons||'"optout_copy_missing"'::jsonb; end if;

  if nullif(c.metadata->>'prospect_id','') is null then
    reasons:=reasons||'"prospect_pointer_missing"'::jsonb;
  else
    select * into p from crm.prospects where id=(c.metadata->>'prospect_id')::uuid;
  end if;

  if p.id is null then
    reasons:=reasons||'"prospect_not_found"'::jsonb;
  else
    if not crm.locticians_research_candidate_v1(p) then reasons:=reasons||'"prospect_no_longer_claimable"'::jsonb; end if;
    if lower(c.email)<>lower(coalesce(p.public_email,'')) then reasons:=reasons||'"recipient_research_drift"'::jsonb; end if;
    if not crm.public_business_email_safe_v2(p.public_email) then reasons:=reasons||'"unsafe_researched_email"'::jsonb; end if;
  end if;

  if exists(
    select 1 from crm.suppression_list s
    where (s.expires_at is null or s.expires_at>now())
      and (lower(coalesce(s.email,''))=lower(c.email) or lower(coalesce(s.domain,''))=lower(split_part(c.email,'@',2)))
  ) then reasons:=reasons||'"suppressed"'::jsonb; end if;

  if exists(
    select 1 from crm.outreach_events_v1 e
    where e.contact_id=p_contact_id and e.event_type in ('cold_enqueued','cold_sent')
  ) then reasons:=reasons||'"cold_already_attempted_for_contact"'::jsonb; end if;

  return jsonb_build_object(
    'eligible',jsonb_array_length(reasons)=0,
    'send_kind',p_send_kind,
    'reasons',reasons,
    'campaign',campaign,
    'offer',offer_state,
    'contact_id',p_contact_id
  );
end;
$function$;

create or replace function crm.penta_marketer_promote_researched_prospects_v1(p_limit integer default 50)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','crm','public','pg_temp'
as $function$
declare
  v_limit integer:=greatest(1,least(coalesce(p_limit,50),200));
  cfg crm.outbound_config%rowtype;
  v_offer_state jsonb;
  v_offer_copy text;
  v_inserted integer:=0;
begin
  if current_user not in ('postgres','service_role')
     and coalesce(current_setting('request.jwt.claim.role',true),'')<>'service_role' then
    raise exception 'service_role_required';
  end if;

  select * into cfg from crm.outbound_config where singleton=true;
  v_offer_state:=crm.penta_marketer_offer_safe_ready_v1();
  if not coalesce((v_offer_state->>'ready')::boolean,false) then
    return jsonb_build_object('state','HOLD','reason','safe_offer_not_ready','offer',v_offer_state,'promoted',0);
  end if;
  v_offer_copy:=nullif(btrim(v_offer_state->>'public_copy'),'');
  if v_offer_copy is null then
    return jsonb_build_object('state','HOLD','reason','canonical_offer_copy_missing','promoted',0);
  end if;

  with candidates as (
    select p.*
    from crm.prospects p
    where crm.locticians_research_candidate_v1(p)
      and nullif(btrim(p.public_email),'') is not null
      and crm.public_business_email_safe_v2(p.public_email)
      and p.last_researched_at >= now()-interval '30 days'
      and not exists (
        select 1 from crm.outreach_contacts_v1 c
        where lower(c.email)=lower(p.public_email) or c.metadata->>'prospect_id'=p.id::text
      )
      and not exists (
        select 1 from crm.suppression_list s
        where (s.expires_at is null or s.expires_at>now())
          and (lower(coalesce(s.email,''))=lower(p.public_email) or lower(coalesce(s.domain,''))=lower(split_part(p.public_email,'@',2)))
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
    lower(p.public_email),p.listing_name,p.listing_name,
    coalesce(p.email_source_url,p.website_url,p.source_listing_url),
    'verified',95,greatest(60,least(100,coalesce(p.lead_score,75))),
    jsonb_build_object(
      'prospect_id',p.id,
      'public_email_source',coalesce(p.email_source_url,p.website_url),
      'last_researched_at',p.last_researched_at,
      'claim_status',p.claim_status
    ),
    true,'prospect','ready',
    'Is '||p.listing_name||' yours on Locticians?',
    'Hello,'||E'\n\n'||
      'I am reaching out from CrownThrive about the public '||p.listing_name||' profile on Locticians'||
      case when nullif(btrim(p.city),'') is not null then ' in '||p.city else '' end||
      '. The profile currently appears claimable, and this email address was verified from a public business source.'||
      E'\n\n'||
      'Claiming the profile lets you review and manage how your business is represented on Locticians.'||
      E'\n\n'||
      'Current promotion: '||v_offer_copy||
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
      'source_listing_url',p.source_listing_url,
      'offer_copy_mode','canonical_verified_public_copy',
      'recipient_validation','public_business_email_safe_v2'
    ),
    now(),now()
  from candidates p
  on conflict do nothing;

  get diagnostics v_inserted=row_count;
  return jsonb_build_object(
    'state','COMPLETE','promoted',v_inserted,'limit',v_limit,
    'offer_mode','canonical_verified_public_copy',
    'recipient_validation','public_business_email_safe_v2'
  );
end;
$function$;

update crm.outreach_schedule_v1 s
set state='cancelled',reason='unsafe_recipient_email_v2_4',updated_at=now()
from crm.outreach_contacts_v1 c
where s.contact_id=c.contact_id
  and s.campaign_ref='ct.pentamarketer.locticians.claim.20260827.v1'
  and s.state='scheduled'
  and not crm.public_business_email_safe_v2(c.email);

update crm.outreach_contacts_v1 c
set copy_state='hold',
    risk_hold_at=coalesce(risk_hold_at,now()),
    metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
      'risk_reason','unsafe_recipient_email_v2_4',
      'risk_reconciled_at',now()
    ),
    updated_at=now()
where not crm.public_business_email_safe_v2(c.email)
  and c.metadata->>'campaign_ref'='ct.pentamarketer.locticians.claim.20260827.v1';

insert into crm.penta_marketer_campaign_events_v1(campaign_id,event_type,actor_ref,evidence,created_at)
select
  'ct.pentamarketer.locticians.claim.20260827.v1',
  'config_updated',
  'PentaMarketer/PentaCertify',
  jsonb_build_object(
    'reason','structured_offer_evidence_gate_bound',
    'offer_ref','locticians.claimmonth50.v1',
    'offer_gate_version','2.4.0',
    'public_evidence_required','verified',
    'public_scope_required','verified',
    'checkout_pending_allowed_only_with_safe_deferral',true,
    'broad_plan_and_lifetime_claims_forbidden',true
  ),
  now()
where not exists (
  select 1 from crm.penta_marketer_campaign_events_v1 e
  where e.campaign_id='ct.pentamarketer.locticians.claim.20260827.v1'
    and e.evidence->>'reason'='structured_offer_evidence_gate_bound'
);

insert into crm.penta_marketer_campaign_events_v1(campaign_id,event_type,actor_ref,evidence,created_at)
select
  'ct.pentamarketer.locticians.claim.20260827.v1',
  'config_updated',
  'PentaMarketer/PentaSecure',
  jsonb_build_object(
    'reason','public_business_email_guard_bound',
    'validator','crm.public_business_email_safe_v2',
    'asset_tld_rejection',true,
    'final_send_revalidation',true,
    'unsafe_existing_schedules_cancelled',true
  ),
  now()
where not exists (
  select 1 from crm.penta_marketer_campaign_events_v1 e
  where e.campaign_id='ct.pentamarketer.locticians.claim.20260827.v1'
    and e.evidence->>'reason'='public_business_email_guard_bound'
);

grant execute on function crm.penta_marketer_offer_safe_ready_v1(text,text) to service_role;
grant execute on function crm.public_business_email_safe_v2(text) to service_role;
grant execute on function crm.penta_marketer_eligibility_v1(uuid,text) to service_role;
grant execute on function crm.penta_marketer_promote_researched_prospects_v1(integer) to service_role;
