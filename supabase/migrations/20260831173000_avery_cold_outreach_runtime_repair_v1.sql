-- CrownThrive / Locticians Avery cold-outreach runtime repair v1
-- Production defect closure captured after live repair on 2026-08-31.
-- Scope: provider health truthfulness, canonical BD host, discovery seed starvation,
-- and explicit Avery persona campaign binding. Does not weaken suppression, prior-attempt,
-- complaint, bounce, reply, risk, send-window, spacing, or PentaMail transport controls.

create or replace function integration_control.locticians_bd_warm_failover_reconcile_v3()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','vault','extensions','public','chlom_runtime'
as $function$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_primary text;
  v_recovery text;
  v_cold text;
  v_candidate record;
  v_candidate_secret text;
  v_primary_http_status integer;
  v_http_status integer;
  v_ready boolean;
  v_promoted integer := 0;
  v_primary_present boolean;
  v_primary_ready boolean := false;
  v_recovery_present boolean;
  v_cold_present boolean;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then
    raise exception 'service_role_required';
  end if;

  select decrypted_secret into v_primary from vault.decrypted_secrets where name='locticians_brilliant_directories_api_key' limit 1;
  select decrypted_secret into v_recovery from vault.decrypted_secrets where name='locticians_brilliant_directories_api_key_recovery' limit 1;
  select decrypted_secret into v_cold from vault.decrypted_secrets where name='LOCTICIANS_BD_API_KEY_COLD_PENTA' limit 1;
  v_primary_present := v_primary is not null;
  v_recovery_present := v_recovery is not null;
  v_cold_present := v_cold is not null;

  if v_primary_present then
    begin
      select (chlom_runtime.dail_http_v1((
        'GET'::extensions.http_method,
        'https://www.locticians.com/api/v2/data_categories/get?limit=1'::varchar,
        array[row('X-Api-Key',v_primary)::extensions.http_header,row('accept','application/json')::extensions.http_header],
        null::varchar,
        null::varchar
      )::extensions.http_request)).status into v_primary_http_status;
    exception when others then
      v_primary_http_status := 599;
    end;
    v_primary_ready := v_primary_http_status between 200 and 299;

    update integration_control.locticians_provider_key_lanes_v1
       set enabled=v_primary_ready,
           provider_status=case when v_primary_ready then 'provider_verified_operational' else 'provider_verify_failed' end,
           dispatch_state=case when v_primary_ready then 'WARM_PRIMARY' else 'HOLD_PROVIDER_VERIFY_FAILED' end,
           last_verified_at=case when v_primary_ready then now() else null end,
           metadata=metadata||jsonb_build_object(
             'custody_recovery_present',v_recovery_present,
             'custody_cold_copy_present',v_cold_present,
             'recovery_same_provider_credential',v_recovery_present and v_recovery=v_primary,
             'cold_copy_same_provider_credential',v_cold_present and v_cold=v_primary,
             'primary_live_verified',v_primary_ready,
             'last_provider_http_status',v_primary_http_status,
             'switch_on_429',false),
           updated_at=now()
     where lane_id='ct.locticians.bd.hot.a.v3';
  else
    update integration_control.locticians_provider_key_lanes_v1
       set enabled=false,
           provider_status='vault_primary_missing',
           dispatch_state='HOLD',
           last_verified_at=null,
           metadata=metadata||jsonb_build_object('primary_live_verified',false,'switch_on_429',false),
           updated_at=now()
     where lane_id='ct.locticians.bd.hot.a.v3';
  end if;

  for v_candidate in select * from integration_control.locticians_bd_failover_candidates_v3 order by provider_key_id loop
    v_candidate_secret := null;
    select decrypted_secret into v_candidate_secret from vault.decrypted_secrets where name=v_candidate.expected_vault_alias limit 1;
    v_http_status := null;
    v_ready := false;

    if v_candidate_secret is null then
      update integration_control.locticians_bd_failover_candidates_v3
         set vault_material_state='absent',distinctness_state='unknown',provider_verify_state='unverified',failover_ready=false,last_provider_http_status=null,last_reconciled_at=now(),updated_at=now()
       where candidate_key=v_candidate.candidate_key;
      update integration_control.locticians_provider_key_lanes_v1
         set enabled=false,provider_status='provider_issued_unbound',dispatch_state='AWAITING_VAULT_MATERIAL',last_verified_at=null,metadata=metadata||jsonb_build_object('failover_ready',false),updated_at=now()
       where lane_id=v_candidate.target_lane_id;
      continue;
    end if;

    if v_primary is not null and v_candidate_secret=v_primary then
      update integration_control.locticians_bd_failover_candidates_v3
         set vault_material_state='present',distinctness_state='same_as_primary',provider_verify_state='not_independent',failover_ready=false,last_provider_http_status=null,last_reconciled_at=now(),updated_at=now()
       where candidate_key=v_candidate.candidate_key;
      update integration_control.locticians_provider_key_lanes_v1
         set enabled=false,provider_status='vaulted_but_not_independent',dispatch_state='HOLD_SAME_CREDENTIAL',last_verified_at=null,metadata=metadata||jsonb_build_object('failover_ready',false,'independent_credential',false),updated_at=now()
       where lane_id=v_candidate.target_lane_id;
      continue;
    end if;

    begin
      select (chlom_runtime.dail_http_v1((
        'GET'::extensions.http_method,
        'https://www.locticians.com/api/v2/data_categories/get?limit=1'::varchar,
        array[row('X-Api-Key',v_candidate_secret)::extensions.http_header,row('accept','application/json')::extensions.http_header],
        null::varchar,
        null::varchar
      )::extensions.http_request)).status into v_http_status;
    exception when others then
      v_http_status := 599;
    end;
    v_ready := v_http_status between 200 and 299;

    update integration_control.locticians_bd_failover_candidates_v3
       set vault_material_state='present',
           distinctness_state='distinct_from_primary',
           provider_verify_state=case when v_ready then 'verified_read' else 'provider_verify_failed' end,
           failover_ready=v_ready,
           last_provider_http_status=v_http_status,
           last_reconciled_at=now(),updated_at=now()
     where candidate_key=v_candidate.candidate_key;
    update integration_control.locticians_provider_key_lanes_v1
       set enabled=v_ready,
           provider_status=case when v_ready then 'provider_verified_operational' else 'provider_verify_failed' end,
           dispatch_state=case when v_ready then 'WARM_STANDBY' else 'HOLD_PROVIDER_VERIFY_FAILED' end,
           last_verified_at=case when v_ready then now() else null end,
           metadata=metadata||jsonb_build_object('failover_ready',v_ready,'independent_credential',true,'last_provider_http_status',v_http_status,'switch_on_429',false),
           updated_at=now()
     where lane_id=v_candidate.target_lane_id;
    if v_ready then v_promoted := v_promoted+1; end if;
  end loop;

  return jsonb_build_object(
    'primary_present',v_primary_present,
    'primary_live_verified',v_primary_ready,
    'primary_http_status',v_primary_http_status,
    'recovery_present',v_recovery_present,
    'cold_copy_present',v_cold_present,
    'recovery_same_credential',v_recovery_present and v_recovery=v_primary,
    'cold_copy_same_credential',v_cold_present and v_cold=v_primary,
    'independent_standbys_ready',v_promoted,
    'sitewide_quota_shared',true,
    'switch_on_429',false,
    'authority','ct.locticians.brilliant-directories.api-fabric.v3',
    'reconciled_at',now());
end
$function$;

create or replace function crm.locticians_claimable_prospect_ingest_v1(p_limit integer default 100)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','crm','public','integration_control','extensions','pg_temp'
as $function$
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
  if current_user not in ('postgres','service_role') and coalesce(current_setting('request.jwt.claim.role',true),'') <> 'service_role' then
    raise exception 'service_role_required';
  end if;
  if not exists (select 1 from integration_control.locticians_endpoint_catalog_v2 where endpoint_id='locticians:user:get' and internal_enabled=true and state='verified_read') then
    return jsonb_build_object('state','PROVIDER_HOLD','reason','user_get_not_certified');
  end if;
  v_key := public.get_runtime_secret('locticians_brilliant_directories_api_key');
  if nullif(v_key,'') is null then return jsonb_build_object('state','PROVIDER_HOLD','reason','provider_key_missing'); end if;
  v_headers := array[extensions.http_header('X-Api-Key',v_key),extensions.http_header('accept','application/json')]::extensions.http_header[];
  select provider_page_cursor into v_cursor from crm.penta_marketer_queue_policy_v1 where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1';
  v_url := 'https://www.locticians.com/api/v2/user/get?property=verified&property_value=0&limit='||v_limit::text;
  if nullif(v_cursor,'') is not null then v_url := v_url||'&page='||replace(replace(replace(v_cursor,'+','%2B'),'/','%2F'),'=','%3D'); end if;
  begin
    v_resp := chlom_runtime.dail_http_v1(('GET',v_url,v_headers,null,null)::extensions.http_request);
  exception when others then
    return jsonb_build_object('state','PROVIDER_HOLD','reason','provider_transport_error','provider_host','www.locticians.com');
  end;
  if v_resp.status <> 200 then
    v_reason := case when lower(coalesce(v_resp.content,'')) like '%expired api key%' then 'provider_key_expired' when v_resp.status in (401,403) then 'provider_auth_failed' else 'provider_read_failed' end;
    return jsonb_build_object('state','PROVIDER_HOLD','reason',v_reason,'http_status',v_resp.status,'provider_host','www.locticians.com');
  end if;
  begin v_body := v_resp.content::jsonb; exception when others then return jsonb_build_object('state','PROVIDER_HOLD','reason','provider_non_json','http_status',v_resp.status,'provider_host','www.locticians.com'); end;
  if jsonb_typeof(v_body)='array' then v_records:=v_body;
  elsif jsonb_typeof(v_body->'message')='array' then v_records:=v_body->'message';
  elsif jsonb_typeof(v_body->'message')='object' then v_records:=jsonb_build_array(v_body->'message');
  end if;
  v_next_cursor:=nullif(v_body->>'next_page','');
  begin v_current_page:=nullif(v_body->>'current_page','')::integer; exception when others then v_current_page:=null; end;
  begin v_total:=nullif(v_body->>'total','')::bigint; exception when others then v_total:=null; end;
  update crm.penta_marketer_queue_policy_v1 set provider_page_cursor=v_next_cursor,provider_current_page=v_current_page,provider_total=v_total,updated_at=now() where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1';
  with source_rows as (select value as r from jsonb_array_elements(v_records) limit v_limit), normalized as (
    select r,coalesce(nullif(btrim(r->>'company'),''),nullif(btrim(concat_ws(' ',r->>'first_name',r->>'last_name')),'')) listing_name,
      nullif(btrim(r->>'filename'),'') filename,nullif(btrim(crm.url_percent_decode_basic_v1(r->>'website')),'') website_url,
      nullif(btrim(r->>'city'),'') city,nullif(btrim(r->>'state_code'),'') region,nullif(btrim(r->>'country_code'),'') country from source_rows
  ), eligible as (
    select * from normalized where listing_name is not null and filename is not null and coalesce(r->>'subscription_id','')='14' and coalesce(r->>'active','')='2'
  )
  insert into crm.prospects(source_platform,source_listing_url,listing_name,category,city,region,country,website_url,claim_status,lifecycle,lead_score,risk_score,compliance_status,enrichment,created_at,updated_at)
  select 'locticians','https://locticians.com/'||regexp_replace(filename,'^/+','','g'),listing_name,initcap(replace(substring(filename from '.*/([^/]+)/[^/]+$'),'-',' ')),city,region,country,website_url,'claimable','new',70,0,'hold',
    jsonb_strip_nulls(jsonb_build_object('provider_user_id',nullif(r->>'user_id',''),'provider_subscription_id',nullif(r->>'subscription_id',''),'provider_active',nullif(r->>'active',''),'provider_verified',nullif(r->>'verified',''),'provider_profession_id',nullif(r->>'profession_id',''),'provider_source','bd_filtered_verified_0','provider_host','www.locticians.com','claim_evidence_observed',true,'provider_ingested_at',now())),now(),now()
  from eligible
  on conflict (source_platform,source_listing_url) do update set listing_name=excluded.listing_name,category=coalesce(excluded.category,crm.prospects.category),city=coalesce(excluded.city,crm.prospects.city),region=coalesce(excluded.region,crm.prospects.region),country=coalesce(excluded.country,crm.prospects.country),website_url=coalesce(excluded.website_url,crm.prospects.website_url),claim_status=case when crm.prospects.claim_status='claimed' then 'claimed' else 'claimable' end,enrichment=crm.prospects.enrichment||excluded.enrichment,updated_at=now();
  get diagnostics v_touched=row_count;
  return jsonb_build_object('state','COMPLETE','http_status',v_resp.status,'provider_records',jsonb_array_length(v_records),'prospects_touched',v_touched,'source_filter','verified=0 then subscription_id=14 and active=2','current_page',v_current_page,'next_page_present',v_next_cursor is not null,'provider_total',v_total,'provider_host','www.locticians.com');
end;
$function$;

create or replace function crm.contact_discovery_seed_v1(p_limit integer default 100)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','crm','pg_temp'
as $function$
declare v_count integer:=0; v_limit integer:=greatest(1,least(coalesce(p_limit,100),500));
begin
  with eligible as (
    select p.* from crm.prospects p
    where crm.locticians_research_candidate_v1(p)
      and (
        (nullif(btrim(p.email_source_url),'') is not null and not exists (select 1 from crm.contact_discovery_queue_v1 q where q.prospect_id=p.id and q.target_url=p.email_source_url and q.state in ('complete','hold') and q.updated_at>=now()-interval '30 days'))
        or (nullif(btrim(p.website_url),'') is not null and not exists (select 1 from crm.contact_discovery_queue_v1 q where q.prospect_id=p.id and q.target_url=p.website_url and q.state in ('complete','hold') and q.updated_at>=now()-interval '30 days'))
        or (nullif(btrim(p.source_listing_url),'') is not null and not exists (select 1 from crm.contact_discovery_queue_v1 q where q.prospect_id=p.id and q.target_url=p.source_listing_url and q.state in ('complete','hold') and q.updated_at>=now()-interval '30 days'))
      )
    order by case when p.public_email is null then 0 else 1 end,coalesce(p.lead_score,0) desc,p.created_at
    limit v_limit
  ), raw_targets as (
    select id prospect_id,email_source_url target_url,'email_evidence_page'::text source_kind,120 priority from eligible where nullif(btrim(email_source_url),'') is not null
    union all select id,website_url,'official_business_site',case when public_email is null then 110 else 90 end from eligible where nullif(btrim(website_url),'') is not null
    union all select id,source_listing_url,'directory_listing',70 from eligible where nullif(btrim(source_listing_url),'') is not null
  ), targets as (
    select distinct on (prospect_id,target_url) prospect_id,target_url,source_kind,priority from raw_targets order by prospect_id,target_url,priority desc,source_kind
  )
  insert into crm.contact_discovery_queue_v1(prospect_id,target_url,source_kind,priority,state,available_at,metadata)
  select prospect_id,target_url,source_kind,priority,'pending',now(),jsonb_build_object('seed','PentaMarketer/PentaCrawler','version','1.2.0','campaign_ref','ct.pentamarketer.locticians.claim.20260827.v1','selection','actionable_target_first') from targets
  on conflict (prospect_id,target_url) do update set
    source_kind=case when excluded.priority>=crm.contact_discovery_queue_v1.priority then excluded.source_kind else crm.contact_discovery_queue_v1.source_kind end,
    priority=greatest(crm.contact_discovery_queue_v1.priority,excluded.priority),
    state=case when crm.contact_discovery_queue_v1.state='complete' and crm.contact_discovery_queue_v1.updated_at<now()-interval '30 days' then 'pending' when crm.contact_discovery_queue_v1.state='hold' and crm.contact_discovery_queue_v1.updated_at<now()-interval '30 days' then 'retry' else crm.contact_discovery_queue_v1.state end,
    available_at=case when crm.contact_discovery_queue_v1.state in ('complete','hold') and crm.contact_discovery_queue_v1.updated_at<now()-interval '30 days' then now() else crm.contact_discovery_queue_v1.available_at end,
    metadata=crm.contact_discovery_queue_v1.metadata||excluded.metadata,updated_at=now();
  get diagnostics v_count=row_count;
  return jsonb_build_object('state','SEEDED','touched',v_count,'candidate_limit',v_limit,'selection','actionable_target_first','version','1.2.0');
end;
$function$;

update crm.penta_marketer_campaign_v1
set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
  'persona_id','ct.persona.locticians.member-success.avery.v1',
  'persona_role','Locticians Member Success',
  'persona_binding','explicit_renderer_and_campaign',
  'transport_authority','ct.ops.agent.email-attention',
  'specialist','PentaMarketer',
  'source_repair','20260831173000_avery_cold_outreach_runtime_repair_v1.sql')
where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1';
