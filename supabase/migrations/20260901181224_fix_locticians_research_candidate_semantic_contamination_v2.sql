-- Permanent fix: provider/system metadata must never satisfy semantic beauty/wellness targeting.
-- Only prospect-facing classification fields may satisfy the relevance regex.
-- Existing queued rows that no longer qualify are held, never deleted.

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
      coalesce(p.listing_name,'')
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

update crm.contact_discovery_queue_v1 q
set state='hold',
    lease_id=null,
    lease_expires_at=null,
    last_error=concat_ws(';',nullif(q.last_error,''),'semantic_candidate_v2_not_relevant'),
    metadata=coalesce(q.metadata,'{}'::jsonb)||jsonb_build_object(
      'semantic_candidate_v2',jsonb_build_object(
        'relevant',false,
        'reason','provider_metadata_removed_from_semantic_targeting',
        'held_at',clock_timestamp(),
        'destructive',false
      )
    ),
    updated_at=clock_timestamp()
from crm.prospects p
where p.id=q.prospect_id
  and q.state in ('pending','retry','leased')
  and not crm.locticians_research_candidate_v1(p);

revoke all on function crm.locticians_research_candidate_v1(crm.prospects) from public,anon,authenticated;
grant execute on function crm.locticians_research_candidate_v1(crm.prospects) to service_role;