-- PentaCrawler bounded same-domain contact-page follow v1
-- Extends public business contact discovery without cross-domain crawling or
-- weakening public-email confidence, suppression, or transport controls.

create or replace function crm.contact_discovery_process_batch_v1(p_limit integer default 10)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','crm','public','extensions','pg_temp'
as $function$
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
  v_followup_seeded integer:=0;
  v_new integer:=0;
  v_origin text;
  v_host text;
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
      v_resp:=chlom_runtime.dail_http_v1((
        'GET',v_url,
        array[
          extensions.http_header('accept','text/html,application/xhtml+xml'),
          extensions.http_header('user-agent','CrownThrive-PentaCrawler/2.1 (+https://crownthrive.com)')
        ]::extensions.http_header[],
        null,null
      )::extensions.http_request);
    exception when others then
      perform crm.contact_discovery_complete_v1(v_queue_id,'[]'::jsonb,'http_transport_error');
      v_retried:=v_retried+1;
      continue;
    end;

    if v_resp.status < 200 or v_resp.status >= 300 then
      if v_kind in ('official_contact_page','official_booking_page') and v_resp.status in (404,410) then
        perform crm.contact_discovery_complete_v1(v_queue_id,'[]'::jsonb,null);
        v_skipped:=v_skipped+1;
      else
        perform crm.contact_discovery_complete_v1(v_queue_id,'[]'::jsonb,'http_'||v_resp.status::text);
        v_retried:=v_retried+1;
      end if;
      continue;
    end if;

    v_html:=left(coalesce(v_resp.content,''),1000000);

    with emails as (
      select distinct lower(m.match[1]) as email
      from regexp_matches(v_html,'(?i)mailto:([A-Z0-9._%+\\-]+@[A-Z0-9.\\-]+\\.[A-Z]{2,})','g') as m(match)
      union
      select distinct lower(m.match[1]) as email
      from regexp_matches(v_html,'(?i)([A-Z0-9._%+\\-]+@[A-Z0-9.\\-]+\\.[A-Z]{2,})','g') as m(match)
    ), filtered as (
      select email
      from emails
      where email not in ('user@domain.com','email@example.com','name@example.com')
        and lower(split_part(email,'@',2)) !~ '(wixpress|sentry|ndiscovered|example|domain\\.com|w3\\.org|cloudflare|schema\\.org|wordpress|shopify)'
      order by case when split_part(email,'@',1) in ('info','hello','contact','bookings','booking','appointments','owner') then 0 else 1 end,email
      limit 5
    )
    select coalesce(jsonb_agg(jsonb_build_object(
      'email',email,'source_url',v_url,'source_type',v_kind,'page_title',null,
      'confidence',case when v_kind='official_business_site' then 95 else 90 end,
      'is_public_business_contact',true,
      'evidence_sha256',encode(extensions.digest(v_url||'|'||email,'sha256'),'hex'),
      'evidence',jsonb_build_object('collector','PentaCrawler SQL bounded public-contact pass','http_status',v_resp.status,'body_archived',false,'crawler_version','2.1'),
      'observed_at',now()
    )),'[]'::jsonb)
    into v_obs
    from filtered;

    if v_kind='official_business_site' then
      v_origin:=substring(v_url from '^(https?://[^/]+)');
      v_host:=lower(substring(v_url from '^https?://([^/:]+)'));
      if v_origin is not null and v_host is not null then
        with hrefs as (
          select distinct replace(split_part(m[1],'#',1),'&amp;','&') as href
          from regexp_matches(v_html,'href[[:space:]]*=[[:space:]]*["'']([^"'']+)["'']','gi') as m
          where lower(m[1]) ~ '(contact|book|booking|appointment|about|connect)'
          limit 12
        ), normalized as (
          select case
            when href ~* '^https?://' then href
            when href like '//%' then 'https:'||href
            when href like '/%' then v_origin||href
            else null
          end as target_url
          from hrefs
        ), safe_links as (
          select distinct target_url,
                 case when lower(target_url) ~ '(book|booking|appointment)' then 'official_booking_page' else 'official_contact_page' end as source_kind
          from normalized
          where target_url is not null
            and crm.public_http_target_safe_v1(target_url)
            and lower(substring(target_url from '^https?://([^/:]+)'))=v_host
          limit 3
        )
        insert into crm.contact_discovery_queue_v1(prospect_id,target_url,source_kind,priority,state,available_at,metadata)
        select (v_item->>'prospect_id')::uuid,target_url,source_kind,
               case when source_kind='official_booking_page' then 118 else 116 end,
               'pending',now(),jsonb_build_object('seed','PentaCrawler observed same-domain link','version','2.1','followed_from',v_url,'campaign_ref','ct.pentamarketer.locticians.claim.20260827.v1')
        from safe_links
        on conflict (prospect_id,target_url) do nothing;
        get diagnostics v_new=row_count;
        v_followup_seeded:=v_followup_seeded+v_new;
      end if;
    end if;

    perform crm.contact_discovery_complete_v1(v_queue_id,v_obs,null);
    v_completed:=v_completed+1;
  end loop;

  return jsonb_build_object(
    'state','COMPLETE','claimed',jsonb_array_length(v_claims),'completed',v_completed,'retried',v_retried,
    'directory_or_terminal_skipped',v_skipped,'same_domain_followups_seeded',v_followup_seeded,'crawler_version','2.1'
  );
end;
$function$;
