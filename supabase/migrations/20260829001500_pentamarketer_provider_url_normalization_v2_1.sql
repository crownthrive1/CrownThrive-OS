create or replace function crm.url_percent_decode_basic_v1(p_url text)
returns text
language sql
immutable
set search_path to 'pg_catalog'
as $$
  select replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(coalesce(p_url,''),
    '%3A',':'),'%3a',':'),'%2F','/'),'%2f','/'),'%3F','?'),'%3f','?'),'%3D','='),'%3d','='),
    '%26','&'),'%20',' '),'%2B','+'),'%2b','+'),'%23','#'),'%40','@'),'%25','%'),'%5F','_');
$$;

create or replace function crm.public_http_target_safe_v1(p_url text)
returns boolean
language sql
immutable
set search_path to 'pg_catalog','crm'
as $$
  select
    nullif(btrim(crm.url_percent_decode_basic_v1(coalesce(p_url,''))),'') is not null
    and crm.url_percent_decode_basic_v1(p_url) ~* '^https?://'
    and crm.url_percent_decode_basic_v1(p_url) !~* '^https?://[^/]*@'
    and crm.url_percent_decode_basic_v1(p_url) !~* '^https?://(localhost|0\.0\.0\.0|127\.|10\.|169\.254\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|\[?::1\]?|metadata\.google\.internal)([:/]|$)';
$$;

update crm.prospects
set website_url=crm.url_percent_decode_basic_v1(website_url),
    email_source_url=case when email_source_url is null then null else crm.url_percent_decode_basic_v1(email_source_url) end,
    updated_at=now()
where website_url like '%\%%' escape '\'
   or email_source_url like '%\%%' escape '\';

update crm.contact_discovery_queue_v1
set target_url=crm.url_percent_decode_basic_v1(target_url),
    state=case when state='retry' and last_error='unsafe_target_url' then 'retry' else state end,
    available_at=case when state='retry' and last_error='unsafe_target_url' then now() else available_at end,
    last_error=case when state='retry' and last_error='unsafe_target_url' then null else last_error end,
    updated_at=now()
where target_url like '%\%%' escape '\';

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
    v_resp := extensions.http(('GET',v_url,v_headers,null,null)::extensions.http_request);
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

  begin v_body := v_resp.content::jsonb;
  exception when others then
    return jsonb_build_object('state','PROVIDER_HOLD','reason','provider_non_json','http_status',v_resp.status);
  end;

  if jsonb_typeof(v_body)='array' then v_records:=v_body;
  elsif jsonb_typeof(v_body->'message')='array' then v_records:=v_body->'message';
  elsif jsonb_typeof(v_body->'message')='object' then v_records:=jsonb_build_array(v_body->'message');
  end if;

  v_next_cursor:=nullif(v_body->>'next_page','');
  begin v_current_page:=nullif(v_body->>'current_page','')::integer; exception when others then v_current_page:=null; end;
  begin v_total:=nullif(v_body->>'total','')::bigint; exception when others then v_total:=null; end;

  update crm.penta_marketer_queue_policy_v1
  set provider_page_cursor=v_next_cursor,
      provider_current_page=v_current_page,
      provider_total=v_total,
      updated_at=now()
  where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1';

  with source_rows as (
    select value as r from jsonb_array_elements(v_records) limit v_limit
  ), normalized as (
    select
      r,
      coalesce(nullif(btrim(r->>'company'),''),nullif(btrim(concat_ws(' ',r->>'first_name',r->>'last_name')),'')) listing_name,
      nullif(btrim(r->>'filename'),'') filename,
      nullif(btrim(crm.url_percent_decode_basic_v1(r->>'website')),'') website_url,
      nullif(btrim(r->>'city'),'') city,
      nullif(btrim(r->>'state_code'),'') region,
      nullif(btrim(r->>'country_code'),'') country
    from source_rows
  ), eligible as (
    select * from normalized
    where listing_name is not null
      and filename is not null
      and coalesce(r->>'subscription_id','')='14'
      and coalesce(r->>'active','')='2'
  )
  insert into crm.prospects(
    source_platform,source_listing_url,listing_name,category,city,region,country,website_url,
    claim_status,lifecycle,lead_score,risk_score,compliance_status,enrichment,created_at,updated_at
  )
  select
    'locticians','https://locticians.com/'||regexp_replace(filename,'^/+','','g'),listing_name,
    initcap(replace(substring(filename from '.*/([^/]+)/[^/]+$'),'-',' ')),city,region,country,website_url,
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
    )),now(),now()
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
    'state','COMPLETE','http_status',v_resp.status,'provider_records',jsonb_array_length(v_records),
    'prospects_touched',v_touched,'source_filter','verified=0 then subscription_id=14 and active=2',
    'current_page',v_current_page,'next_page_present',v_next_cursor is not null,'provider_total',v_total
  );
end;
$$;

grant execute on function crm.url_percent_decode_basic_v1(text) to service_role;
grant execute on function crm.public_http_target_safe_v1(text) to service_role;
grant execute on function crm.locticians_claimable_prospect_ingest_v1(integer) to service_role;