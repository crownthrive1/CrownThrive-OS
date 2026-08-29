-- CrownThrive Stripe reliability fabric v3
-- Production-applied source projection. Secrets remain in Vault and are never emitted.

create table if not exists integration_control.stripe_event_receipts_v3 (
  receipt_id uuid primary key default gen_random_uuid(),
  provider_event_id text not null unique,
  lane text not null check (lane in ('thrivetickets','kjv_sermon_toolkit','crownthrive_default')),
  event_type text not null,
  livemode boolean not null default false,
  api_version text,
  provider_created_at timestamptz,
  object_id text,
  account_id text,
  request_id text,
  payload_sha256 text not null check (payload_sha256 ~ '^[0-9a-f]{64}$'),
  signature_timestamp bigint not null,
  signature_verified boolean not null default true,
  receipt_state text not null default 'accepted' check (receipt_state in ('accepted','processing','processed','held','failed')),
  processing_attempts integer not null default 0,
  last_error text,
  received_at timestamptz not null default now(),
  processed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.stripe_event_payloads_v3 (
  receipt_id uuid primary key references integration_control.stripe_event_receipts_v3(receipt_id) on delete restrict,
  event_payload jsonb not null,
  event_projection jsonb not null default '{}'::jsonb,
  payload_sha256 text not null check (payload_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now()
);

create table if not exists integration_control.stripe_webhook_endpoints_v3 (
  provider_endpoint_id text primary key,
  provider_url text not null,
  description text,
  provider_status text,
  enabled_events jsonb not null default '[]'::jsonb,
  livemode boolean,
  api_version text,
  application text,
  metadata jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.stripe_webhook_reconciliation_events_v3 (
  event_id uuid primary key default gen_random_uuid(),
  lane text not null,
  provider_endpoint_id text,
  event_type text not null,
  prior_url text,
  desired_url text,
  provider_http_status integer,
  disposition text not null,
  evidence jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now()
);

alter table integration_control.stripe_event_receipts_v3 enable row level security;
alter table integration_control.stripe_event_payloads_v3 enable row level security;
alter table integration_control.stripe_webhook_endpoints_v3 enable row level security;
alter table integration_control.stripe_webhook_reconciliation_events_v3 enable row level security;
revoke all on integration_control.stripe_event_receipts_v3,integration_control.stripe_event_payloads_v3,integration_control.stripe_webhook_endpoints_v3,integration_control.stripe_webhook_reconciliation_events_v3 from public,anon,authenticated;
grant select,insert,update on integration_control.stripe_event_receipts_v3 to service_role;
grant select,insert on integration_control.stripe_event_payloads_v3 to service_role;
grant select,insert,update on integration_control.stripe_webhook_endpoints_v3 to service_role;
grant select,insert on integration_control.stripe_webhook_reconciliation_events_v3 to service_role;

create policy stripe_event_receipts_service_v3 on integration_control.stripe_event_receipts_v3 for all to service_role using (true) with check (true);
create policy stripe_event_payloads_service_v3 on integration_control.stripe_event_payloads_v3 for select to service_role using (true);
create policy stripe_event_payloads_insert_service_v3 on integration_control.stripe_event_payloads_v3 for insert to service_role with check (true);
create policy stripe_webhook_endpoints_service_v3 on integration_control.stripe_webhook_endpoints_v3 for all to service_role using (true) with check (true);
create policy stripe_webhook_reconciliation_events_service_v3 on integration_control.stripe_webhook_reconciliation_events_v3 for select to service_role using (true);
create policy stripe_webhook_reconciliation_events_insert_service_v3 on integration_control.stripe_webhook_reconciliation_events_v3 for insert to service_role with check (true);

create index if not exists stripe_event_receipts_lane_state_received_idx on integration_control.stripe_event_receipts_v3(lane,receipt_state,received_at desc);
create index if not exists stripe_event_receipts_event_type_received_idx on integration_control.stripe_event_receipts_v3(event_type,received_at desc);

create or replace function integration_control.get_stripe_webhook_secret_v3(p_lane text)
returns text
language plpgsql
security definer
set search_path=pg_catalog,vault,integration_control
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_secret text;
  v_count int;
  v_pattern text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  v_pattern := case p_lane
    when 'thrivetickets' then '(thrive.?tickets|thrivetickets|ticket)'
    when 'kjv_sermon_toolkit' then '(kjv|sermon.?toolkit|sermon)'
    when 'crownthrive_default' then '(crownthrive|default)'
    else null end;
  if v_pattern is null then raise exception 'unsupported_stripe_lane'; end if;
  select count(*),max(d.decrypted_secret)
    into v_count,v_secret
    from vault.decrypted_secrets d
   where d.decrypted_secret like 'whsec\_%' escape '\'
     and lower(coalesce(d.name,'')||' '||coalesce(d.description,'')) ~ v_pattern;
  if v_count <> 1 then raise exception 'stripe_webhook_secret_resolution_%_%',p_lane,v_count; end if;
  return v_secret;
end $$;

create or replace function integration_control.get_stripe_live_api_key_v3()
returns text
language plpgsql
security definer
set search_path=pg_catalog,vault,integration_control
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_secret text;
  v_count int;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  select count(*),max(d.decrypted_secret)
    into v_count,v_secret
    from vault.decrypted_secrets d
   where d.decrypted_secret like 'sk\_live\_%' escape '\'
     and lower(coalesce(d.name,'')||' '||coalesce(d.description,'')) like '%stripe%';
  if v_count <> 1 then raise exception 'stripe_live_api_key_resolution_%',v_count; end if;
  return v_secret;
end $$;

revoke all on function integration_control.get_stripe_webhook_secret_v3(text) from public,anon,authenticated;
revoke all on function integration_control.get_stripe_live_api_key_v3() from public,anon,authenticated;
grant execute on function integration_control.get_stripe_webhook_secret_v3(text) to service_role;
grant execute on function integration_control.get_stripe_live_api_key_v3() to service_role;

create or replace function integration_control.stripe_event_accept_v3(
  p_lane text,
  p_event jsonb,
  p_payload_sha256 text,
  p_signature_timestamp bigint
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,chlom_runtime
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_receipt_id uuid;
  v_event_id text := p_event->>'id';
  v_event_type text := p_event->>'type';
  v_projection jsonb;
  v_inserted boolean := false;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  if p_lane not in ('thrivetickets','kjv_sermon_toolkit','crownthrive_default') then raise exception 'unsupported_stripe_lane'; end if;
  if v_event_id is null or v_event_id !~ '^evt_' then raise exception 'invalid_stripe_event_id'; end if;
  if v_event_type is null or length(v_event_type)>160 then raise exception 'invalid_stripe_event_type'; end if;
  if p_payload_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'invalid_payload_sha256'; end if;

  v_projection := jsonb_strip_nulls(jsonb_build_object(
    'id',v_event_id,
    'type',v_event_type,
    'livemode',coalesce((p_event->>'livemode')::boolean,false),
    'api_version',p_event->>'api_version',
    'created',p_event->>'created',
    'object_id',p_event#>>'{data,object,id}',
    'object_type',p_event#>>'{data,object,object}',
    'account',p_event->>'account',
    'request_id',p_event#>>'{request,id}'
  ));

  insert into integration_control.stripe_event_receipts_v3(
    provider_event_id,lane,event_type,livemode,api_version,provider_created_at,object_id,account_id,request_id,payload_sha256,signature_timestamp,signature_verified,receipt_state
  ) values(
    v_event_id,p_lane,v_event_type,coalesce((p_event->>'livemode')::boolean,false),p_event->>'api_version',
    case when (p_event->>'created') ~ '^[0-9]+$' then to_timestamp((p_event->>'created')::double precision) else null end,
    p_event#>>'{data,object,id}',p_event->>'account',p_event#>>'{request,id}',p_payload_sha256,p_signature_timestamp,true,'accepted'
  )
  on conflict(provider_event_id) do update set
    updated_at=now(),
    signature_verified=integration_control.stripe_event_receipts_v3.signature_verified or excluded.signature_verified
  returning receipt_id,(xmax=0) into v_receipt_id,v_inserted;

  insert into integration_control.stripe_event_payloads_v3(receipt_id,event_payload,event_projection,payload_sha256)
  values(v_receipt_id,p_event,v_projection,p_payload_sha256)
  on conflict(receipt_id) do nothing;

  if v_inserted then
    perform chlom_runtime.append_dail_event(
      'stripe.webhook.accepted','provider_event',p_lane,
      jsonb_build_object('receipt_id',v_receipt_id,'provider_event_id',v_event_id,'event_type',v_event_type,'lane',p_lane,'livemode',coalesce((p_event->>'livemode')::boolean,false),'payload_sha256',p_payload_sha256,'signature_verified',true,'money_movement_executed',false),
      'PentaHook/PentaLedger',null,'PentaHook','3.0.0',p_payload_sha256,null,'ct.stripe.webhook.fabric.v3',null,'restricted'
    );
  end if;

  return jsonb_build_object('ok',true,'receipt_id',v_receipt_id,'provider_event_id',v_event_id,'duplicate',not v_inserted,'receipt_state','accepted');
end $$;

revoke all on function integration_control.stripe_event_accept_v3(text,jsonb,text,bigint) from public,anon,authenticated;
grant execute on function integration_control.stripe_event_accept_v3(text,jsonb,text,bigint) to service_role;

create or replace function integration_control.stripe_webhook_inventory_refresh_v3()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_key text;
  v_resp extensions.http_response;
  v_json jsonb;
  v_row jsonb;
  v_count int:=0;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  v_key:=integration_control.get_stripe_live_api_key_v3();
  v_resp:=extensions.http((
    'GET'::extensions.http_method,
    'https://api.stripe.com/v1/webhook_endpoints?limit=100'::varchar,
    array[row('Authorization','Bearer '||v_key)::extensions.http_header,row('Accept','application/json')::extensions.http_header],
    null::varchar,null::varchar
  )::extensions.http_request);
  if v_resp.status < 200 or v_resp.status >= 300 then raise exception 'stripe_webhook_inventory_http_%',v_resp.status; end if;
  v_json:=v_resp.content::jsonb;
  for v_row in select value from jsonb_array_elements(coalesce(v_json->'data','[]'::jsonb)) loop
    insert into integration_control.stripe_webhook_endpoints_v3(provider_endpoint_id,provider_url,description,provider_status,enabled_events,livemode,api_version,application,metadata,observed_at,updated_at)
    values(v_row->>'id',v_row->>'url',v_row->>'description',v_row->>'status',coalesce(v_row->'enabled_events','[]'::jsonb),coalesce((v_row->>'livemode')::boolean,false),v_row->>'api_version',v_row->>'application',coalesce(v_row->'metadata','{}'::jsonb),now(),now())
    on conflict(provider_endpoint_id) do update set provider_url=excluded.provider_url,description=excluded.description,provider_status=excluded.provider_status,enabled_events=excluded.enabled_events,livemode=excluded.livemode,api_version=excluded.api_version,application=excluded.application,metadata=excluded.metadata,observed_at=now(),updated_at=now();
    v_count:=v_count+1;
  end loop;
  return jsonb_build_object('ok',true,'provider_http_status',v_resp.status,'endpoints_observed',v_count,'observed_at',now());
end $$;

create or replace function integration_control.stripe_webhook_reconcile_v3()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_key text;
  r record;
  v_lane text;
  v_desired text;
  v_resp extensions.http_response;
  v_updated int:=0;
  v_held int:=0;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  perform integration_control.stripe_webhook_inventory_refresh_v3();
  v_key:=integration_control.get_stripe_live_api_key_v3();

  for r in
    select * from integration_control.stripe_webhook_endpoints_v3
    where lower(coalesce(provider_url,'')||' '||coalesce(description,'')||' '||coalesce(metadata::text,'')) ~ '(thrivetickets|thrive.?tickets|sermon.?toolkit|kjv)'
    order by provider_endpoint_id
  loop
    if lower(coalesce(r.provider_url,'')||' '||coalesce(r.description,'')||' '||coalesce(r.metadata::text,'')) ~ '(thrivetickets|thrive.?tickets)' then
      v_lane:='thrivetickets';
      v_desired:='https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/thrive-tickets-stripe-webhook';
    elsif lower(coalesce(r.provider_url,'')||' '||coalesce(r.description,'')||' '||coalesce(r.metadata::text,'')) ~ '(sermon.?toolkit|kjv)' then
      v_lane:='kjv_sermon_toolkit';
      v_desired:='https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/kjv-sermon-toolkit-stripe-webhook';
    else
      continue;
    end if;

    if r.provider_url=v_desired and r.provider_status='enabled' then
      insert into integration_control.stripe_webhook_reconciliation_events_v3(lane,provider_endpoint_id,event_type,prior_url,desired_url,provider_http_status,disposition,evidence)
      values(v_lane,r.provider_endpoint_id,'READBACK_CURRENT',r.provider_url,v_desired,200,'NOOP_CURRENT',jsonb_build_object('provider_status',r.provider_status));
      continue;
    end if;

    v_resp:=extensions.http((
      'POST'::extensions.http_method,
      ('https://api.stripe.com/v1/webhook_endpoints/'||r.provider_endpoint_id)::varchar,
      array[row('Authorization','Bearer '||v_key)::extensions.http_header,row('Content-Type','application/x-www-form-urlencoded')::extensions.http_header],
      'application/x-www-form-urlencoded'::varchar,
      ('url='||replace(replace(v_desired,':','%3A'),'/','%2F')||'&disabled=false')::varchar
    )::extensions.http_request);

    if v_resp.status between 200 and 299 then
      v_updated:=v_updated+1;
      insert into integration_control.stripe_webhook_reconciliation_events_v3(lane,provider_endpoint_id,event_type,prior_url,desired_url,provider_http_status,disposition,evidence)
      values(v_lane,r.provider_endpoint_id,'PROVIDER_URL_UPDATED',r.provider_url,v_desired,v_resp.status,'UPDATED',jsonb_build_object('provider_object_sha256',encode(extensions.digest(v_resp.content,'sha256'),'hex')));
    else
      v_held:=v_held+1;
      insert into integration_control.stripe_webhook_reconciliation_events_v3(lane,provider_endpoint_id,event_type,prior_url,desired_url,provider_http_status,disposition,evidence)
      values(v_lane,r.provider_endpoint_id,'PROVIDER_URL_UPDATE_FAILED',r.provider_url,v_desired,v_resp.status,'HOLD',jsonb_build_object('response_sha256',encode(extensions.digest(coalesce(v_resp.content,''),'sha256'),'hex')));
    end if;
  end loop;

  perform integration_control.stripe_webhook_inventory_refresh_v3();
  return jsonb_build_object('ok',v_held=0,'updated',v_updated,'held',v_held,'reconciled_at',now());
end $$;

create or replace function integration_control.stripe_webhook_signed_canary_v3(p_lane text)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_secret text;
  v_event_id text;
  v_payload jsonb;
  v_raw text;
  v_ts bigint;
  v_sig text;
  v_url text;
  v_resp extensions.http_response;
  v_receipt uuid;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  if p_lane not in ('thrivetickets','kjv_sermon_toolkit') then raise exception 'unsupported_stripe_lane'; end if;
  v_secret:=integration_control.get_stripe_webhook_secret_v3(p_lane);
  v_event_id:='evt_ctcanary_'||replace(gen_random_uuid()::text,'-','');
  v_ts:=extract(epoch from clock_timestamp())::bigint;
  v_payload:=jsonb_build_object(
    'id',v_event_id,'object','event','api_version','2026-08-27','created',v_ts,'livemode',false,'pending_webhooks',1,
    'type','crownthrive.webhook.canary','data',jsonb_build_object('object',jsonb_build_object('id','ctcanary_'||p_lane,'object','crownthrive_canary','lane',p_lane)),
    'request',jsonb_build_object('id','ctreq_'||replace(gen_random_uuid()::text,'-',''),'idempotency_key',null)
  );
  v_raw:=v_payload::text;
  v_sig:=encode(extensions.hmac((v_ts::text||'.'||v_raw)::bytea,v_secret::bytea,'sha256'),'hex');
  v_url:=case p_lane when 'thrivetickets' then 'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/thrive-tickets-stripe-webhook' else 'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/kjv-sermon-toolkit-stripe-webhook' end;
  v_resp:=extensions.http((
    'POST'::extensions.http_method,v_url::varchar,
    array[row('Content-Type','application/json')::extensions.http_header,row('Stripe-Signature','t='||v_ts||',v1='||v_sig)::extensions.http_header,row('User-Agent','CrownThrive-PentaCertify/3.0')::extensions.http_header],
    'application/json'::varchar,v_raw::varchar
  )::extensions.http_request);
  select receipt_id into v_receipt from integration_control.stripe_event_receipts_v3 where provider_event_id=v_event_id;
  return jsonb_build_object('lane',p_lane,'event_id',v_event_id,'edge_http_status',v_resp.status,'edge_ok',case when v_resp.status between 200 and 299 then coalesce(((v_resp.content::jsonb)->>'ok')::boolean,false) else false end,'receipt_id',v_receipt,'receipt_persisted',v_receipt is not null,'payload_sha256',encode(extensions.digest(v_raw,'sha256'),'hex'),'livemode',false,'money_movement',false,'observed_at',now());
end $$;

create or replace function integration_control.stripe_webhook_certify_and_resolve_v3()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,penta_self,chlom_runtime,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_lane text;v_title text;v_url text;v_canary_count int;v_endpoint_count int;v_problem_id uuid;v_resolved int:=0;v_held jsonb:='[]'::jsonb;v_evidence jsonb;v_sha text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  begin perform integration_control.stripe_webhook_reconcile_v3(); exception when others then v_held:=v_held||jsonb_build_array(jsonb_build_object('stage','provider_reconcile','error_class',sqlstate,'error_message',sqlerrm)); end;
  for v_lane,v_title,v_url in values
    ('thrivetickets'::text,'ThriveTickets Stripe webhook returning HTTP 404'::text,'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/thrive-tickets-stripe-webhook'::text),
    ('kjv_sermon_toolkit'::text,'KJV/Sermon Toolkit Stripe webhook returning HTTP 503'::text,'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/kjv-sermon-toolkit-stripe-webhook'::text)
  loop
    select count(*) into v_canary_count from integration_control.stripe_event_receipts_v3 where lane=v_lane and event_type='crownthrive.webhook.canary' and signature_verified and receipt_state in ('accepted','processing','processed') and received_at>now()-interval '2 hours';
    select count(*) into v_endpoint_count from integration_control.stripe_webhook_endpoints_v3 where provider_url=v_url and coalesce(provider_status,'enabled')='enabled';
    v_evidence:=jsonb_build_object('lane',v_lane,'desired_url',v_url,'signed_canary_receipts',v_canary_count,'provider_endpoint_matches',v_endpoint_count,'signature_verified',v_canary_count>0,'durable_receipt_persisted',v_canary_count>0,'provider_binding_verified',v_endpoint_count=1,'money_movement',false,'certified_at',now());
    v_sha:=encode(extensions.digest(v_evidence::text,'sha256'),'hex');
    if v_canary_count>0 and v_endpoint_count=1 then
      select problem_id into v_problem_id from penta_self.problem_ledger_v1 where title=v_title order by created_at desc limit 1;
      if v_problem_id is not null then perform penta_self.certify_problem_resolution_v2(v_problem_id,'verified_resolved',v_evidence||jsonb_build_object('evidence_sha256',v_sha),'PentaHook/PentaCertify',3);v_resolved:=v_resolved+1; end if;
      perform chlom_runtime.append_dail_event('stripe.webhook.production_certified','provider_webhook',v_lane,v_evidence||jsonb_build_object('evidence_sha256',v_sha),'PentaHook/PentaCertify',null,'PentaCertify','3.0.0',v_sha,null,'ct.stripe.webhook.fabric.v3',null,'restricted');
    else
      v_held:=v_held||jsonb_build_array(v_evidence||jsonb_build_object('disposition','HOLD'));
    end if;
  end loop;
  return jsonb_build_object('resolved',v_resolved,'held',v_held,'certified_at',now());
end $$;

revoke all on function integration_control.stripe_webhook_inventory_refresh_v3() from public,anon,authenticated;
revoke all on function integration_control.stripe_webhook_reconcile_v3() from public,anon,authenticated;
revoke all on function integration_control.stripe_webhook_signed_canary_v3(text) from public,anon,authenticated;
revoke all on function integration_control.stripe_webhook_certify_and_resolve_v3() from public,anon,authenticated;
grant execute on function integration_control.stripe_webhook_inventory_refresh_v3() to service_role;
grant execute on function integration_control.stripe_webhook_reconcile_v3() to service_role;
grant execute on function integration_control.stripe_webhook_signed_canary_v3(text) to service_role;
grant execute on function integration_control.stripe_webhook_certify_and_resolve_v3() to service_role;

-- Governed product inventory and crosswalk.
create table if not exists integration_control.stripe_product_inventory_v3 (
  stripe_product_id text primary key,
  product_name text not null,
  active boolean not null,
  description text,
  default_price_id text,
  provider_created_at timestamptz,
  provider_updated_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  raw_projection jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.commerce_candidate_projection_v3 (
  source_schema text not null,
  source_table text not null,
  source_row_key text not null,
  candidate_key text,
  candidate_name text,
  sku text,
  stripe_product_id text,
  stripe_price_id text,
  candidate_state text,
  source_projection jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now(),
  primary key(source_schema,source_table,source_row_key)
);

create table if not exists integration_control.stripe_product_crosswalk_v3 (
  crosswalk_id uuid primary key default gen_random_uuid(),
  stripe_product_id text,
  source_schema text,
  source_table text,
  source_row_key text,
  candidate_key text,
  match_method text not null check(match_method in ('exact_provider_id','exact_metadata_key','exact_sku_metadata','normalized_name','unmatched_provider','unmatched_internal')),
  confidence numeric(5,4) not null check(confidence between 0 and 1),
  certification_state text not null check(certification_state in ('verified','candidate','hold')),
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null check(evidence_sha256 ~ '^[0-9a-f]{64}$'),
  observed_at timestamptz not null default now(),
  unique(stripe_product_id,source_schema,source_table,source_row_key,match_method)
);

create table if not exists integration_control.stripe_product_crosswalk_receipts_v3 (
  receipt_id uuid primary key default gen_random_uuid(),
  provider_products integer not null,
  internal_candidates integer not null,
  verified_matches integer not null,
  candidate_matches integer not null,
  unmatched_provider integer not null,
  unmatched_internal integer not null,
  completeness numeric(8,6) not null,
  disposition text not null,
  payload_sha256 text not null check(payload_sha256 ~ '^[0-9a-f]{64}$'),
  observed_at timestamptz not null default now()
);

alter table integration_control.stripe_product_inventory_v3 enable row level security;
alter table integration_control.commerce_candidate_projection_v3 enable row level security;
alter table integration_control.stripe_product_crosswalk_v3 enable row level security;
alter table integration_control.stripe_product_crosswalk_receipts_v3 enable row level security;
revoke all on integration_control.stripe_product_inventory_v3,integration_control.commerce_candidate_projection_v3,integration_control.stripe_product_crosswalk_v3,integration_control.stripe_product_crosswalk_receipts_v3 from public,anon,authenticated;
grant select,insert,update,delete on integration_control.stripe_product_inventory_v3,integration_control.commerce_candidate_projection_v3,integration_control.stripe_product_crosswalk_v3 to service_role;
grant select,insert on integration_control.stripe_product_crosswalk_receipts_v3 to service_role;
create policy stripe_product_inventory_service_v3 on integration_control.stripe_product_inventory_v3 for all to service_role using(true) with check(true);
create policy commerce_candidate_projection_service_v3 on integration_control.commerce_candidate_projection_v3 for all to service_role using(true) with check(true);
create policy stripe_product_crosswalk_service_v3 on integration_control.stripe_product_crosswalk_v3 for all to service_role using(true) with check(true);
create policy stripe_product_crosswalk_receipts_service_v3 on integration_control.stripe_product_crosswalk_receipts_v3 for select to service_role using(true);
create policy stripe_product_crosswalk_receipts_insert_service_v3 on integration_control.stripe_product_crosswalk_receipts_v3 for insert to service_role with check(true);
create index if not exists stripe_product_inventory_name_idx on integration_control.stripe_product_inventory_v3(lower(product_name));
create index if not exists commerce_candidate_projection_candidate_idx on integration_control.commerce_candidate_projection_v3(candidate_key);
create index if not exists commerce_candidate_projection_product_idx on integration_control.commerce_candidate_projection_v3(stripe_product_id);
create index if not exists stripe_product_crosswalk_state_idx on integration_control.stripe_product_crosswalk_v3(certification_state,match_method);

-- The exact production refresh/crosswalk functions are defined in the paired restricted runtime bundle.
-- Public source records the database interface and safety contract without exposing provider-key retrieval internals.

select cron.unschedule(jobid) from cron.job where jobname in ('ct-stripe-webhook-inventory-v3','ct-stripe-webhook-reconcile-v3','ct-stripe-webhook-certify-v3','ct-stripe-product-crosswalk-v3');
select cron.schedule('ct-stripe-webhook-inventory-v3','17 * * * *','select integration_control.stripe_webhook_inventory_refresh_v3();');
select cron.schedule('ct-stripe-webhook-reconcile-v3','23 * * * *','select integration_control.stripe_webhook_reconcile_v3();');
select cron.schedule('ct-stripe-webhook-certify-v3','29 * * * *','select integration_control.stripe_webhook_certify_and_resolve_v3();');
select cron.schedule('ct-stripe-product-crosswalk-v3','41 7 * * *','select integration_control.stripe_product_crosswalk_refresh_v3();');
