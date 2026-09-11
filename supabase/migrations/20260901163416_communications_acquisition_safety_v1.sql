-- CrownThrive communications acquisition and recipient-safety repair.
-- Additive except for replacement of the existing bounded Locticians acquisition RPC.
-- No direct-send authority, suppression bypass, money movement, rights action, credential export, or D3 authority.

create table integration_control.provider_capability_health_v1 (
  service_id text not null,
  capability_key text not null,
  endpoint_id text not null,
  http_method text not null,
  path_template text not null,
  lane_id text,
  health_state text not null,
  last_http_status integer,
  last_success_at timestamptz,
  last_failure_at timestamptz,
  consecutive_failures integer not null default 0,
  credential_verified boolean not null default false,
  capability_verified boolean not null default false,
  last_error_code text,
  evidence_sha256 text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  primary key(service_id, capability_key),
  constraint provider_capability_health_state_v1_chk
    check (health_state in ('UNKNOWN','HEALTHY','DEGRADED','AUTH_FAILED','COOLDOWN','TRANSPORT_ERROR','INVALID_RESPONSE','HOLD')),
  constraint provider_capability_health_method_v1_chk
    check (http_method in ('GET','POST','PUT','PATCH','DELETE')),
  constraint provider_capability_health_status_v1_chk
    check (last_http_status is null or last_http_status between 100 and 599),
  constraint provider_capability_health_evidence_v1_chk
    check (evidence_sha256 is null or evidence_sha256 ~ '^[0-9a-f]{64}$'),
  constraint provider_capability_health_failure_count_v1_chk
    check (consecutive_failures >= 0)
);

alter table integration_control.provider_capability_health_v1 enable row level security;
revoke all on integration_control.provider_capability_health_v1 from public, anon, authenticated;
grant select on integration_control.provider_capability_health_v1 to service_role;
create policy provider_capability_health_service_read_v1
on integration_control.provider_capability_health_v1
for select to service_role using (true);

create or replace function crm.enforce_safe_ready_contact_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','crm','extensions'
as $function$
begin
  if new.relationship_state='prospect'
     and new.copy_state='ready'
     and not crm.public_business_email_safe_v2(new.email) then
    new.copy_state:='hold';
    new.research_state:='hold';
    new.claimable_profile:=false;
    new.risk_hold_at:=coalesce(new.risk_hold_at,clock_timestamp());
    new.metadata:=coalesce(new.metadata,'{}'::jsonb)||jsonb_build_object(
      'communications_safety_hold_v1',jsonb_build_object(
        'reason','public_business_email_unsafe',
        'detected_at',clock_timestamp(),
        'email_domain',lower(split_part(coalesce(new.email,''),'@',2)),
        'email_sha256',encode(
          extensions.digest(convert_to(lower(btrim(coalesce(new.email,''))),'UTF8'),'sha256'),
          'hex'
        ),
        'raw_email_copied',false,
        'auto_clear_forbidden',true
      )
    );
  end if;
  return new;
end;
$function$;

drop trigger if exists outreach_contacts_safe_ready_guard_v1 on crm.outreach_contacts_v1;
create trigger outreach_contacts_safe_ready_guard_v1
before insert or update of email,relationship_state,copy_state,research_state,claimable_profile
on crm.outreach_contacts_v1
for each row execute function crm.enforce_safe_ready_contact_v1();

update crm.outreach_contacts_v1
set copy_state='hold',
    research_state='hold',
    claimable_profile=false,
    risk_hold_at=coalesce(risk_hold_at,clock_timestamp()),
    metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
      'communications_safety_hold_v1',jsonb_build_object(
        'reason','public_business_email_unsafe',
        'detected_at',clock_timestamp(),
        'email_domain',lower(split_part(coalesce(email,''),'@',2)),
        'email_sha256',encode(
          extensions.digest(convert_to(lower(btrim(coalesce(email,''))),'UTF8'),'sha256'),
          'hex'
        ),
        'raw_email_copied',false,
        'auto_clear_forbidden',true,
        'backfill_generation',1
      )
    )
where relationship_state='prospect'
  and copy_state='ready'
  and not crm.public_business_email_safe_v2(email);

create or replace function crm.locticians_claimable_prospect_ingest_v1(p_limit integer default 100)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','crm','public','integration_control','chlom_runtime','extensions','pg_temp'
as $function$
declare
  v_endpoint integration_control.locticians_endpoint_catalog_v2%rowtype;
  v_limit integer:=greatest(1,least(coalesce(p_limit,100),100));
  v_selection jsonb;
  v_failover_selection jsonb;
  v_vault_alias text;
  v_lane_id text;
  v_initial_lane_id text;
  v_key text;
  v_headers extensions.http_header[];
  v_resp extensions.http_response;
  v_body jsonb;
  v_records jsonb:='[]'::jsonb;
  v_touched integer:=0;
  v_reason text;
  v_cursor text;
  v_url text;
  v_next_cursor text;
  v_current_page integer;
  v_total bigint;
  v_attempt integer:=0;
  v_failovers integer:=0;
  v_started_at timestamptz;
  v_latency_ms integer;
  v_response_sha text;
  v_error text;
begin
  if current_user not in ('postgres','service_role')
     and coalesce(current_setting('request.jwt.claim.role',true),'')<>'service_role' then
    raise exception 'service_role_required';
  end if;

  select * into v_endpoint
  from integration_control.locticians_endpoint_catalog_v2
  where endpoint_id='locticians:user:find'
    and capability='member_find'
    and http_method='GET'
    and path_template='/user/get?property={field}&property_value={value}'
    and internal_enabled=true
    and state='verified_read'
    and provider_http_status between 200 and 299;

  if not found then
    insert into integration_control.provider_capability_health_v1(
      service_id,capability_key,endpoint_id,http_method,path_template,health_state,
      credential_verified,capability_verified,last_error_code,evidence_sha256,metadata
    ) values (
      'locticians','member_find','locticians:user:find','GET',
      '/user/get?property={field}&property_value={value}','HOLD',
      false,false,'bounded_member_find_capability_not_verified',
      encode(extensions.digest(convert_to('bounded_member_find_capability_not_verified','UTF8'),'sha256'),'hex'),
      jsonb_build_object('raw_secret_exposed',false)
    )
    on conflict(service_id,capability_key) do update set
      health_state='HOLD',last_failure_at=clock_timestamp(),
      consecutive_failures=integration_control.provider_capability_health_v1.consecutive_failures+1,
      credential_verified=false,capability_verified=false,
      last_error_code='bounded_member_find_capability_not_verified',
      evidence_sha256=excluded.evidence_sha256,
      metadata=integration_control.provider_capability_health_v1.metadata||excluded.metadata,
      updated_at=clock_timestamp();
    return jsonb_build_object(
      'state','PROVIDER_HOLD','reason','bounded_member_find_capability_not_verified',
      'endpoint_id','locticians:user:find','credential_exposed',false
    );
  end if;

  v_selection:=integration_control.locticians_bd_select_warm_credential_v3('none');
  if coalesce(v_selection->>'action','')<>'use_credential'
     or nullif(v_selection->>'vault_alias','') is null then
    return jsonb_build_object(
      'state','PROVIDER_HOLD',
      'reason',coalesce(v_selection->>'reason','verified_primary_unavailable'),
      'endpoint_id',v_endpoint.endpoint_id,
      'credential_exposed',false
    );
  end if;

  v_vault_alias:=v_selection->>'vault_alias';
  v_lane_id:=v_selection->>'lane_id';
  v_initial_lane_id:=v_lane_id;
  v_key:=public.get_runtime_secret(v_vault_alias);

  if nullif(v_key,'') is null then
    v_failover_selection:=integration_control.locticians_bd_select_warm_credential_v3('vault_alias_unavailable');
    if coalesce(v_failover_selection->>'action','')<>'use_credential'
       or nullif(v_failover_selection->>'vault_alias','') is null
       or coalesce(v_failover_selection->>'lane_id','')=coalesce(v_lane_id,'') then
      return jsonb_build_object(
        'state','PROVIDER_HOLD','reason','verified_credential_unavailable',
        'endpoint_id',v_endpoint.endpoint_id,'credential_exposed',false
      );
    end if;
    v_selection:=v_failover_selection;
    v_vault_alias:=v_selection->>'vault_alias';
    v_lane_id:=v_selection->>'lane_id';
    v_key:=public.get_runtime_secret(v_vault_alias);
    v_failovers:=1;
  end if;

  if nullif(v_key,'') is null then
    return jsonb_build_object(
      'state','PROVIDER_HOLD','reason','verified_credential_secret_unavailable',
      'endpoint_id',v_endpoint.endpoint_id,'credential_exposed',false
    );
  end if;

  select provider_page_cursor into v_cursor
  from crm.penta_marketer_queue_policy_v1
  where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1';

  <<provider_attempt>>
  loop
    v_attempt:=v_attempt+1;
    v_url:='https://www.locticians.com/api/v2/user/get?property=verified&property_value=0&limit='||v_limit::text;
    if nullif(v_cursor,'') is not null then
      v_url:=v_url||'&page='||
        replace(replace(replace(v_cursor,'+','%2B'),'/','%2F'),'=','%3D');
    end if;
    v_headers:=array[
      extensions.http_header('X-Api-Key',v_key),
      extensions.http_header('accept','application/json')
    ]::extensions.http_header[];
    v_started_at:=clock_timestamp();

    begin
      v_resp:=chlom_runtime.dail_http_v1(
        ('GET',v_url,v_headers,null,null)::extensions.http_request
      );
      v_latency_ms:=greatest(
        0,
        floor(extract(epoch from (clock_timestamp()-v_started_at))*1000)::integer
      );
      v_response_sha:=encode(
        extensions.digest(convert_to(coalesce(v_resp.content,''),'UTF8'),'sha256'),
        'hex'
      );
      perform public.integration_record_request(
        'locticians','member_find','GET',
        '/user/get?property={field}&property_value={value}',
        v_resp.status,v_resp.status between 200 and 299,
        'ct.penta.marketer.locticians.v1',v_latency_ms,v_response_sha,
        'bounded claimable-profile acquisition; lane='||coalesce(v_lane_id,'unknown')||
        '; failovers='||v_failovers::text||'; secret_exposed=false'
      );
    exception when others then
      v_error:=left(sqlstate||':'||sqlerrm,240);
      insert into integration_control.provider_capability_health_v1(
        service_id,capability_key,endpoint_id,http_method,path_template,lane_id,
        health_state,last_failure_at,consecutive_failures,credential_verified,
        capability_verified,last_error_code,evidence_sha256,metadata
      ) values (
        'locticians','member_find',v_endpoint.endpoint_id,'GET',v_endpoint.path_template,
        v_lane_id,'TRANSPORT_ERROR',clock_timestamp(),1,true,false,sqlstate,
        encode(extensions.digest(convert_to(v_error,'UTF8'),'sha256'),'hex'),
        jsonb_build_object('attempts',v_attempt,'failovers',v_failovers,'raw_secret_exposed',false)
      )
      on conflict(service_id,capability_key) do update set
        endpoint_id=excluded.endpoint_id,http_method=excluded.http_method,
        path_template=excluded.path_template,lane_id=excluded.lane_id,
        health_state='TRANSPORT_ERROR',last_failure_at=excluded.last_failure_at,
        consecutive_failures=integration_control.provider_capability_health_v1.consecutive_failures+1,
        credential_verified=true,capability_verified=false,last_error_code=excluded.last_error_code,
        evidence_sha256=excluded.evidence_sha256,
        metadata=integration_control.provider_capability_health_v1.metadata||excluded.metadata,
        updated_at=clock_timestamp();
      return jsonb_build_object(
        'state','PROVIDER_HOLD','reason','provider_transport_error',
        'error_code',sqlstate,'error_sha256',
        encode(extensions.digest(convert_to(v_error,'UTF8'),'sha256'),'hex'),
        'attempts',v_attempt,'failovers',v_failovers,'credential_exposed',false
      );
    end;

    if v_resp.status between 200 and 299 then
      exit provider_attempt;
    end if;

    if v_resp.status=429 then
      insert into integration_control.provider_capability_health_v1(
        service_id,capability_key,endpoint_id,http_method,path_template,lane_id,
        health_state,last_http_status,last_failure_at,consecutive_failures,
        credential_verified,capability_verified,last_error_code,evidence_sha256,metadata
      ) values (
        'locticians','member_find',v_endpoint.endpoint_id,'GET',v_endpoint.path_template,
        v_lane_id,'COOLDOWN',429,clock_timestamp(),1,true,false,
        'shared_provider_rate_limit_or_cooldown',v_response_sha,
        jsonb_build_object('switch_key',false,'attempts',v_attempt,'raw_secret_exposed',false)
      )
      on conflict(service_id,capability_key) do update set
        lane_id=excluded.lane_id,health_state='COOLDOWN',last_http_status=429,
        last_failure_at=excluded.last_failure_at,
        consecutive_failures=integration_control.provider_capability_health_v1.consecutive_failures+1,
        credential_verified=true,capability_verified=false,
        last_error_code='shared_provider_rate_limit_or_cooldown',
        evidence_sha256=excluded.evidence_sha256,
        metadata=integration_control.provider_capability_health_v1.metadata||excluded.metadata,
        updated_at=clock_timestamp();
      return jsonb_build_object(
        'state','PROVIDER_HOLD','reason','shared_provider_rate_limit_or_cooldown',
        'http_status',429,'switch_key',false,'attempts',v_attempt,
        'failovers',v_failovers,'credential_exposed',false
      );
    end if;

    if v_resp.status in (401,403) and v_attempt=1 and v_failovers=0 then
      v_failover_selection:=integration_control.locticians_bd_select_warm_credential_v3(v_resp.status::text);
      if coalesce(v_failover_selection->>'action','')='use_credential'
         and nullif(v_failover_selection->>'vault_alias','') is not null
         and coalesce(v_failover_selection->>'lane_id','')<>coalesce(v_lane_id,'') then
        v_selection:=v_failover_selection;
        v_vault_alias:=v_selection->>'vault_alias';
        v_lane_id:=v_selection->>'lane_id';
        v_key:=public.get_runtime_secret(v_vault_alias);
        if nullif(v_key,'') is not null then
          v_failovers:=1;
          continue provider_attempt;
        end if;
      end if;
    end if;

    v_reason:=case
      when v_resp.status in (401,403) then 'provider_auth_failed_after_bounded_failover'
      else 'provider_http_error'
    end;
    insert into integration_control.provider_capability_health_v1(
      service_id,capability_key,endpoint_id,http_method,path_template,lane_id,
      health_state,last_http_status,last_failure_at,consecutive_failures,
      credential_verified,capability_verified,last_error_code,evidence_sha256,metadata
    ) values (
      'locticians','member_find',v_endpoint.endpoint_id,'GET',v_endpoint.path_template,
      v_lane_id,case when v_resp.status in (401,403) then 'AUTH_FAILED' else 'DEGRADED' end,
      v_resp.status,clock_timestamp(),1,v_resp.status not in (401,403),false,
      v_reason,v_response_sha,
      jsonb_build_object('attempts',v_attempt,'failovers',v_failovers,'switch_key',false,'raw_secret_exposed',false)
    )
    on conflict(service_id,capability_key) do update set
      lane_id=excluded.lane_id,health_state=excluded.health_state,
      last_http_status=excluded.last_http_status,last_failure_at=excluded.last_failure_at,
      consecutive_failures=integration_control.provider_capability_health_v1.consecutive_failures+1,
      credential_verified=excluded.credential_verified,capability_verified=false,
      last_error_code=excluded.last_error_code,evidence_sha256=excluded.evidence_sha256,
      metadata=integration_control.provider_capability_health_v1.metadata||excluded.metadata,
      updated_at=clock_timestamp();
    return jsonb_build_object(
      'state','PROVIDER_HOLD','reason',v_reason,'http_status',v_resp.status,
      'attempts',v_attempt,'failovers',v_failovers,'switch_key',false,
      'credential_exposed',false
    );
  end loop provider_attempt;

  begin
    v_body:=coalesce(nullif(v_resp.content,'')::jsonb,'{}'::jsonb);
  exception when others then
    insert into integration_control.provider_capability_health_v1(
      service_id,capability_key,endpoint_id,http_method,path_template,lane_id,
      health_state,last_http_status,last_failure_at,consecutive_failures,
      credential_verified,capability_verified,last_error_code,evidence_sha256,metadata
    ) values (
      'locticians','member_find',v_endpoint.endpoint_id,'GET',v_endpoint.path_template,
      v_lane_id,'INVALID_RESPONSE',v_resp.status,clock_timestamp(),1,true,false,
      'provider_response_invalid_json',v_response_sha,
      jsonb_build_object('attempts',v_attempt,'failovers',v_failovers,'raw_secret_exposed',false)
    )
    on conflict(service_id,capability_key) do update set
      lane_id=excluded.lane_id,health_state='INVALID_RESPONSE',
      last_http_status=excluded.last_http_status,last_failure_at=excluded.last_failure_at,
      consecutive_failures=integration_control.provider_capability_health_v1.consecutive_failures+1,
      credential_verified=true,capability_verified=false,
      last_error_code='provider_response_invalid_json',
      evidence_sha256=excluded.evidence_sha256,
      metadata=integration_control.provider_capability_health_v1.metadata||excluded.metadata,
      updated_at=clock_timestamp();
    return jsonb_build_object(
      'state','PROVIDER_HOLD','reason','provider_response_invalid_json',
      'http_status',v_resp.status,'response_sha256',v_response_sha,
      'attempts',v_attempt,'failovers',v_failovers,'credential_exposed',false
    );
  end;

  if jsonb_typeof(v_body)='array' then
    v_records:=v_body;
  elsif jsonb_typeof(v_body->'message')='array' then
    v_records:=v_body->'message';
  elsif jsonb_typeof(v_body->'message')='object' then
    v_records:=jsonb_build_array(v_body->'message');
  end if;

  v_next_cursor:=nullif(v_body->>'next_page','');
  begin
    v_current_page:=nullif(v_body->>'current_page','')::integer;
  exception when others then
    v_current_page:=null;
  end;
  begin
    v_total:=nullif(v_body->>'total','')::bigint;
  exception when others then
    v_total:=null;
  end;

  update crm.penta_marketer_queue_policy_v1
  set provider_page_cursor=v_next_cursor,
      provider_current_page=v_current_page,
      provider_total=v_total,
      updated_at=clock_timestamp()
  where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1';

  with source_rows as (
    select value as r from jsonb_array_elements(v_records) limit v_limit
  ), normalized as (
    select
      r,
      coalesce(
        nullif(btrim(r->>'company'),''),
        nullif(btrim(concat_ws(' ',r->>'first_name',r->>'last_name')),'')
      ) listing_name,
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
      'provider_capability','member_find',
      'provider_endpoint_id',v_endpoint.endpoint_id,
      'provider_host','www.locticians.com',
      'provider_lane_id',v_lane_id,
      'provider_failover_count',v_failovers,
      'claim_evidence_observed',true,
      'provider_ingested_at',clock_timestamp(),
      'raw_provider_payload_archived',false
    )),
    clock_timestamp(),clock_timestamp()
  from eligible
  on conflict(source_platform,source_listing_url) do update set
    listing_name=excluded.listing_name,
    category=coalesce(excluded.category,crm.prospects.category),
    city=coalesce(excluded.city,crm.prospects.city),
    region=coalesce(excluded.region,crm.prospects.region),
    country=coalesce(excluded.country,crm.prospects.country),
    website_url=coalesce(excluded.website_url,crm.prospects.website_url),
    claim_status=case when crm.prospects.claim_status='claimed' then 'claimed' else 'claimable' end,
    enrichment=coalesce(crm.prospects.enrichment,'{}'::jsonb)||excluded.enrichment,
    updated_at=clock_timestamp();

  get diagnostics v_touched=row_count;

  insert into integration_control.provider_capability_health_v1(
    service_id,capability_key,endpoint_id,http_method,path_template,lane_id,
    health_state,last_http_status,last_success_at,consecutive_failures,
    credential_verified,capability_verified,last_error_code,evidence_sha256,metadata
  ) values (
    'locticians','member_find',v_endpoint.endpoint_id,'GET',v_endpoint.path_template,
    v_lane_id,'HEALTHY',v_resp.status,clock_timestamp(),0,true,true,null,v_response_sha,
    jsonb_build_object(
      'attempts',v_attempt,'failovers',v_failovers,'initial_lane_id',v_initial_lane_id,
      'provider_records',jsonb_array_length(v_records),'prospects_touched',v_touched,
      'current_page',v_current_page,'next_page_present',v_next_cursor is not null,
      'provider_total',v_total,'raw_secret_exposed',false,'raw_payload_archived',false
    )
  )
  on conflict(service_id,capability_key) do update set
    endpoint_id=excluded.endpoint_id,http_method=excluded.http_method,
    path_template=excluded.path_template,lane_id=excluded.lane_id,
    health_state='HEALTHY',last_http_status=excluded.last_http_status,
    last_success_at=excluded.last_success_at,consecutive_failures=0,
    credential_verified=true,capability_verified=true,last_error_code=null,
    evidence_sha256=excluded.evidence_sha256,
    metadata=integration_control.provider_capability_health_v1.metadata||excluded.metadata,
    updated_at=clock_timestamp();

  return jsonb_build_object(
    'state','COMPLETE','endpoint_id',v_endpoint.endpoint_id,
    'provider_capability','member_find','http_status',v_resp.status,
    'provider_records',jsonb_array_length(v_records),'prospects_touched',v_touched,
    'source_filter','verified=0 then subscription_id=14 and active=2',
    'current_page',v_current_page,'next_page_present',v_next_cursor is not null,
    'provider_total',v_total,'provider_host','www.locticians.com',
    'lane_id',v_lane_id,'initial_lane_id',v_initial_lane_id,
    'failover_mode',v_selection->>'failover_mode','attempts',v_attempt,
    'failovers',v_failovers,'max_auth_failovers',1,'key_hop_on_429',false,
    'credential_exposed',false,'response_sha256',v_response_sha
  );
end;
$function$;

revoke all on function crm.locticians_claimable_prospect_ingest_v1(integer) from public, anon, authenticated;
grant execute on function crm.locticians_claimable_prospect_ingest_v1(integer) to service_role;