-- Prevent substring and generic-health false positives in Locticians cold outreach.
-- Strong beauty/wellness terms are word-aware; verified research terms stored in
-- prospect enrichment may preserve legitimate massage/acupuncture/wellness targets.

create or replace function crm.locticians_research_candidate_v1(p crm.prospects)
returns boolean
language sql
immutable
set search_path to 'pg_catalog','crm','pg_temp'
as $function$
  with t as (
    select lower(
      coalesce(p.category,'')||' '||
      coalesce(p.subcategory,'')||' '||
      coalesce(p.listing_name,'')||' '||
      coalesce(p.enrichment::text,'')
    ) as corpus
  )
  select
    lower(coalesce(p.source_platform,''))='locticians'
    and lower(coalesce(p.claim_status,''))='claimable'
    and coalesce(p.risk_score,0)<=20
    and lower(coalesce(p.compliance_status,''))<>'suppressed'
    and corpus !~ '(^|[^a-z])(music|entertainment|record[[:space:]-]*label|sponsor|partnership)([^a-z]|$)'
    and corpus ~ '(^|[^a-z])(beauty|hair|hairstyl[a-z]*|salon|lash[a-z]*|skin|skincare|esthetic[a-z]*|aesthetic[a-z]*|cosmet[a-z]*|wellness|spa|barber[a-z]*|makeup|brow[a-z]*|massage|acupuncture|holistic|loctician[a-z]*|locs|locks|braid[a-z]*|nail[a-z]*|tattoo[a-z]*|scalp|tricholog[a-z]*)([^a-z]|$)'
  from t;
$function$;

update crm.outreach_schedule_v1 s
set state='cancelled',
    reason='relevance_classifier_v2_5_fail_closed',
    updated_at=now()
from crm.outreach_contacts_v1 c
join crm.prospects p on p.id=(c.metadata->>'prospect_id')::uuid
where s.contact_id=c.contact_id
  and s.campaign_ref='ct.pentamarketer.locticians.claim.20260827.v1'
  and s.state='scheduled'
  and not crm.locticians_research_candidate_v1(p);

update crm.outreach_contacts_v1 c
set copy_state='hold',
    risk_hold_at=coalesce(c.risk_hold_at,now()),
    metadata=coalesce(c.metadata,'{}'::jsonb)||jsonb_build_object(
      'risk_reason','relevance_classifier_v2_5_fail_closed',
      'relevance_reconciled_at',now()
    ),
    updated_at=now()
from crm.prospects p
where p.id=(c.metadata->>'prospect_id')::uuid
  and c.metadata->>'campaign_ref'='ct.pentamarketer.locticians.claim.20260827.v1'
  and not crm.locticians_research_candidate_v1(p)
  and not exists (
    select 1 from crm.outreach_events_v1 e
    where e.contact_id=c.contact_id and e.event_type in ('cold_enqueued','cold_sent')
  );

insert into crm.penta_marketer_campaign_events_v1(campaign_id,event_type,actor_ref,evidence,created_at)
select
  'ct.pentamarketer.locticians.claim.20260827.v1',
  'config_updated',
  'PentaMarketer/PentaResearch/PentaSecure',
  jsonb_build_object(
    'reason','word_aware_relevance_classifier_bound',
    'classifier_version','2.5.0',
    'generic_health_keyword_removed',true,
    'substring_false_positive_prevention',true,
    'known_false_positive','Studio Espanol matched spa substring under legacy classifier',
    'scheduled_revalidation',true
  ),
  now()
where not exists (
  select 1 from crm.penta_marketer_campaign_events_v1 e
  where e.campaign_id='ct.pentamarketer.locticians.claim.20260827.v1'
    and e.evidence->>'reason'='word_aware_relevance_classifier_bound'
);

grant execute on function crm.locticians_research_candidate_v1(crm.prospects) to service_role;
