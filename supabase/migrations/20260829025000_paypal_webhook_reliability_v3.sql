-- CrownThrive PayPal webhook reliability v3
-- Provider credentials remain in Vault. No money movement is performed by this fabric.

create table if not exists integration_control.paypal_event_receipts_v3 (
  receipt_id uuid primary key default gen_random_uuid(),
  provider_event_id text not null unique,
  event_type text not null,
  resource_type text,
  resource_id text,
  summary text,
  provider_created_at timestamptz,
  verification_status text not null,
  payload_sha256 text not null check(payload_sha256 ~ '^[0-9a-f]{64}$'),
  receipt_state text not null default 'accepted' check(receipt_state in ('accepted','processing','processed','held','failed')),
  received_at timestamptz not null default now(),
  processed_at timestamptz,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.paypal_event_payloads_v3 (
  receipt_id uuid primary key references integration_control.paypal_event_receipts_v3(receipt_id) on delete restrict,
  event_payload jsonb not null,
  event_projection jsonb not null default '{}'::jsonb,
  payload_sha256 text not null check(payload_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now()
);

create table if not exists integration_control.paypal_webhook_inventory_v3 (
  webhook_id text primary key,
  provider_url text not null,
  event_types jsonb not null default '[]'::jsonb,
  api_base text not null,
  observed_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.paypal_webhook_events_v3 (
  event_id uuid primary key default gen_random_uuid(),
  event_type text not null,
  webhook_id text,
  prior_url text,
  desired_url text,
  provider_http_status integer,
  disposition text not null,
  evidence jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now()
);

alter table integration_control.paypal_event_receipts_v3 enable row level security;
alter table integration_control.paypal_event_payloads_v3 enable row level security;
alter table integration_control.paypal_webhook_inventory_v3 enable row level security;
alter table integration_control.paypal_webhook_events_v3 enable row level security;
revoke all on integration_control.paypal_event_receipts_v3,integration_control.paypal_event_payloads_v3,integration_control.paypal_webhook_inventory_v3,integration_control.paypal_webhook_events_v3 from public,anon,authenticated;
grant select,insert,update on integration_control.paypal_event_receipts_v3 to service_role;
grant select,insert on integration_control.paypal_event_payloads_v3 to service_role;
grant select,insert,update,delete on integration_control.paypal_webhook_inventory_v3 to service_role;
grant select,insert on integration_control.paypal_webhook_events_v3 to service_role;
create policy paypal_event_receipts_service_v3 on integration_control.paypal_event_receipts_v3 for all to service_role using(true) with check(true);
create policy paypal_event_payloads_service_v3 on integration_control.paypal_event_payloads_v3 for select to service_role using(true);
create policy paypal_event_payloads_insert_service_v3 on integration_control.paypal_event_payloads_v3 for insert to service_role with check(true);
create policy paypal_webhook_inventory_service_v3 on integration_control.paypal_webhook_inventory_v3 for all to service_role using(true) with check(true);
create policy paypal_webhook_events_service_v3 on integration_control.paypal_webhook_events_v3 for select to service_role using(true);
create policy paypal_webhook_events_insert_service_v3 on integration_control.paypal_webhook_events_v3 for insert to service_role with check(true);
create index if not exists paypal_event_receipts_type_received_idx on integration_control.paypal_event_receipts_v3(event_type,received_at desc);

create or replace function integration_control.get_paypal_webhook_config_v3()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,vault
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_client_id text;v_client_secret text;v_webhook_id text;v_client_id_count int;v_client_secret_count int;v_webhook_count int;v_api_base text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  select count(*),max(decrypted_secret) into v_client_id_count,v_client_id from vault.decrypted_secrets where lower(coalesce(name,'')||' '||coalesce(description,'')) ~ 'paypal.*client.*id|client.*id.*paypal';
  select count(*),max(decrypted_secret) into v_client_secret_count,v_client_secret from vault.decrypted_secrets where lower(coalesce(name,'')||' '||coalesce(description,'')) ~ 'paypal.*client.*secret|client.*secret.*paypal';
  select count(*),max(decrypted_secret) into v_webhook_count,v_webhook_id from vault.decrypted_secrets where lower(coalesce(name,'')||' '||coalesce(description,'')) ~ 'paypal.*webhook.*id|webhook.*id.*paypal' or decrypted_secret like 'WH-%';
  if v_client_id_count<>1 then raise exception 'paypal_client_id_resolution_%',v_client_id_count; end if;
  if v_client_secret_count<>1 then raise exception 'paypal_client_secret_resolution_%',v_client_secret_count; end if;
  if v_webhook_count<>1 then raise exception 'paypal_webhook_id_resolution_%',v_webhook_count; end if;
  select case when bool_or(lower(coalesce(name,'')||' '||coalesce(description,'')) like '%sandbox%') then 'https://api-m.sandbox.paypal.com' else 'https://api-m.paypal.com' end into v_api_base from vault.decrypted_secrets where decrypted_secret in (v_client_id,v_client_secret,v_webhook_id);
  return jsonb_build_object('client_id',v_client_id,'client_secret',v_client_secret,'webhook_id',v_webhook_id,'api_base',v_api_base);
end $$;

revoke all on function integration_control.get_paypal_webhook_config_v3() from public,anon,authenticated;
grant execute on function integration_control.get_paypal_webhook_config_v3() to service_role;

create or replace function integration_control.paypal_event_accept_v3(p_event jsonb,p_payload_sha256 text,p_verification_status text)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,chlom_runtime
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_id text:=p_event->>'id';v_type text:=p_event->>'event_type';v_receipt uuid;v_inserted boolean:=false;v_projection jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  if p_verification_status<>'SUCCESS' then raise exception 'paypal_signature_not_verified'; end if;
  if v_id is null or length(v_id)>160 then raise exception 'invalid_paypal_event_id'; end if;
  if v_type is null or length(v_type)>200 then raise exception 'invalid_paypal_event_type'; end if;
  if p_payload_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'invalid_payload_sha256'; end if;
  v_projection:=jsonb_strip_nulls(jsonb_build_object('id',v_id,'event_type',v_type,'resource_type',p_event->>'resource_type','resource_id',p_event#>>'{resource,id}','summary',p_event->>'summary','create_time',p_event->>'create_time'));
  insert into integration_control.paypal_event_receipts_v3(provider_event_id,event_type,resource_type,resource_id,summary,provider_created_at,verification_status,payload_sha256)
  values(v_id,v_type,p_event->>'resource_type',p_event#>>'{resource,id}',left(p_event->>'summary',500),nullif(p_event->>'create_time','')::timestamptz,p_verification_status,p_payload_sha256)
  on conflict(provider_event_id) do update set updated_at=now(),verification_status=excluded.verification_status
  returning receipt_id,(xmax=0) into v_receipt,v_inserted;
  insert into integration_control.paypal_event_payloads_v3(receipt_id,event_payload,event_projection,payload_sha256)
  values(v_receipt,p_event,v_projection,p_payload_sha256) on conflict(receipt_id) do nothing;
  if v_inserted then
    perform chlom_runtime.append_dail_event('paypal.webhook.accepted','provider_event','paypal',jsonb_build_object('receipt_id',v_receipt,'provider_event_id',v_id,'event_type',v_type,'payload_sha256',p_payload_sha256,'signature_verified',true,'money_movement_executed',false),'PentaHook/PentaLedger',null,'PentaHook','3.0.0',p_payload_sha256,null,'ct.paypal.webhook.fabric.v3',null,'restricted');
  end if;
  return jsonb_build_object('ok',true,'receipt_id',v_receipt,'provider_event_id',v_id,'duplicate',not v_inserted);
end $$;

revoke all on function integration_control.paypal_event_accept_v3(jsonb,text,text) from public,anon,authenticated;
grant execute on function integration_control.paypal_event_accept_v3(jsonb,text,text) to service_role;

create or replace function integration_control.paypal_webhook_reconcile_v3()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_cfg jsonb;v_base text;v_id text;v_secret text;v_wh text;v_token_resp extensions.http_response;v_token text;v_resp extensions.http_response;v_json jsonb;v_row jsonb;v_desired text:='https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/paypal-webhook-v3';v_found boolean:=false;v_updated boolean:=false;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  v_cfg:=integration_control.get_paypal_webhook_config_v3();v_base:=v_cfg->>'api_base';v_id:=v_cfg->>'client_id';v_secret:=v_cfg->>'client_secret';v_wh:=v_cfg->>'webhook_id';
  v_token_resp:=extensions.http((
    'POST'::extensions.http_method,(v_base||'/v1/oauth2/token')::varchar,
    array[row('Authorization','Basic '||encode(convert_to(v_id||':'||v_secret,'UTF8'),'base64'))::extensions.http_header,row('Content-Type','application/x-www-form-urlencoded')::extensions.http_header,row('Accept','application/json')::extensions.http_header],
    'application/x-www-form-urlencoded'::varchar,'grant_type=client_credentials'::varchar
  )::extensions.http_request);
  if v_token_resp.status<200 or v_token_resp.status>=300 then raise exception 'paypal_oauth_http_%',v_token_resp.status; end if;
  v_token:=v_token_resp.content::jsonb->>'access_token';
  v_resp:=extensions.http((
    'GET'::extensions.http_method,(v_base||'/v1/notifications/webhooks')::varchar,
    array[row('Authorization','Bearer '||v_token)::extensions.http_header,row('Accept','application/json')::extensions.http_header],null::varchar,null::varchar
  )::extensions.http_request);
  if v_resp.status<200 or v_resp.status>=300 then raise exception 'paypal_webhooks_http_%',v_resp.status; end if;
  v_json:=v_resp.content::jsonb;
  delete from integration_control.paypal_webhook_inventory_v3;
  for v_row in select value from jsonb_array_elements(coalesce(v_json->'webhooks','[]'::jsonb)) loop
    insert into integration_control.paypal_webhook_inventory_v3(webhook_id,provider_url,event_types,api_base)
    values(v_row->>'id',v_row->>'url',coalesce(v_row->'event_types','[]'::jsonb),v_base)
    on conflict(webhook_id) do update set provider_url=excluded.provider_url,event_types=excluded.event_types,api_base=excluded.api_base,observed_at=now(),updated_at=now();
    if v_row->>'id'=v_wh then v_found:=true; end if;
  end loop;
  if not v_found then
    insert into integration_control.paypal_webhook_events_v3(event_type,webhook_id,desired_url,disposition,evidence)
    values('WEBHOOK_ID_NOT_FOUND',v_wh,v_desired,'HOLD',jsonb_build_object('provider_inventory_count',jsonb_array_length(coalesce(v_json->'webhooks','[]'::jsonb))));
    return jsonb_build_object('ok',false,'disposition','HOLD_WEBHOOK_ID_NOT_FOUND','webhook_id',v_wh);
  end if;
  if exists(select 1 from integration_control.paypal_webhook_inventory_v3 where webhook_id=v_wh and provider_url=v_desired) then
    return jsonb_build_object('ok',true,'disposition','NOOP_CURRENT','webhook_id',v_wh,'desired_url',v_desired);
  end if;
  v_resp:=extensions.http((
    'PATCH'::extensions.http_method,(v_base||'/v1/notifications/webhooks/'||v_wh)::varchar,
    array[row('Authorization','Bearer '||v_token)::extensions.http_header,row('Content-Type','application/json')::extensions.http_header,row('Accept','application/json')::extensions.http_header],
    'application/json'::varchar,jsonb_build_array(jsonb_build_object('op','replace','path','/url','value',v_desired))::text::varchar
  )::extensions.http_request);
  v_updated:=v_resp.status between 200 and 299;
  insert into integration_control.paypal_webhook_events_v3(event_type,webhook_id,prior_url,desired_url,provider_http_status,disposition,evidence)
  select 'PROVIDER_URL_RECONCILE',v_wh,provider_url,v_desired,v_resp.status,case when v_updated then 'UPDATED' else 'HOLD' end,jsonb_build_object('response_sha256',encode(extensions.digest(coalesce(v_resp.content,''),'sha256'),'hex'))
  from integration_control.paypal_webhook_inventory_v3 where webhook_id=v_wh;
  return jsonb_build_object('ok',v_updated,'disposition',case when v_updated then 'UPDATED' else 'HOLD_PROVIDER_UPDATE_FAILED' end,'provider_http_status',v_resp.status,'webhook_id',v_wh,'desired_url',v_desired);
end $$;

create or replace function integration_control.paypal_webhook_simulate_v3(p_event_type text default 'PAYMENT.CAPTURE.COMPLETED')
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_cfg jsonb;v_base text;v_id text;v_secret text;v_wh text;v_token text;v_token_resp extensions.http_response;v_resp extensions.http_response;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  if p_event_type not in ('PAYMENT.CAPTURE.COMPLETED','CHECKOUT.ORDER.APPROVED','PAYMENT.CAPTURE.DENIED') then raise exception 'simulator_event_not_allowed'; end if;
  v_cfg:=integration_control.get_paypal_webhook_config_v3();v_base:=v_cfg->>'api_base';v_id:=v_cfg->>'client_id';v_secret:=v_cfg->>'client_secret';v_wh:=v_cfg->>'webhook_id';
  v_token_resp:=extensions.http((
    'POST'::extensions.http_method,(v_base||'/v1/oauth2/token')::varchar,
    array[row('Authorization','Basic '||encode(convert_to(v_id||':'||v_secret,'UTF8'),'base64'))::extensions.http_header,row('Content-Type','application/x-www-form-urlencoded')::extensions.http_header],
    'application/x-www-form-urlencoded'::varchar,'grant_type=client_credentials'::varchar
  )::extensions.http_request);
  if v_token_resp.status<200 or v_token_resp.status>=300 then raise exception 'paypal_oauth_http_%',v_token_resp.status; end if;
  v_token:=v_token_resp.content::jsonb->>'access_token';
  v_resp:=extensions.http((
    'POST'::extensions.http_method,(v_base||'/v1/notifications/simulate-event')::varchar,
    array[row('Authorization','Bearer '||v_token)::extensions.http_header,row('Content-Type','application/json')::extensions.http_header,row('Accept','application/json')::extensions.http_header],
    'application/json'::varchar,jsonb_build_object('event_type',p_event_type,'webhook_id',v_wh,'resource_version','2.0')::text::varchar
  )::extensions.http_request);
  insert into integration_control.paypal_webhook_events_v3(event_type,webhook_id,desired_url,provider_http_status,disposition,evidence)
  values('SIMULATOR_REQUESTED',v_wh,'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/paypal-webhook-v3',v_resp.status,case when v_resp.status between 200 and 299 then 'REQUESTED' else 'HOLD' end,jsonb_build_object('simulated_event_type',p_event_type,'money_movement',false,'response_sha256',encode(extensions.digest(coalesce(v_resp.content,''),'sha256'),'hex')));
  return jsonb_build_object('ok',v_resp.status between 200 and 299,'provider_http_status',v_resp.status,'event_type',p_event_type,'money_movement',false,'webhook_id',v_wh);
end $$;

create or replace function integration_control.paypal_webhook_certify_and_resolve_v3()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,penta_self,chlom_runtime,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_count int;v_problem uuid;v_payload jsonb;v_sha text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  select count(*) into v_count from integration_control.paypal_event_receipts_v3 where verification_status='SUCCESS';
  v_payload:=jsonb_build_object('verified_receipt_count',v_count,'provider_signature_verified',v_count>0,'ledger','integration_control.paypal_event_receipts_v3','observed_at',now());
  v_sha:=encode(extensions.digest(v_payload::text,'sha256'),'hex');
  if v_count>0 then
    select problem_id into v_problem from penta_self.problem_ledger_v1 where title='PayPal end-to-end event receipt evidence is absent' and state not in ('resolved','verified_resolved','closed','superseded') order by created_at desc limit 1;
    if v_problem is not null then perform penta_self.certify_problem_resolution_v2(v_problem,'verified_resolved',v_payload||jsonb_build_object('payload_sha256',v_sha),'PentaHook/PentaCertify/PentaLedger',3); end if;
    perform chlom_runtime.append_dail_event('paypal.webhook.production_certified','provider_webhook','paypal',v_payload||jsonb_build_object('payload_sha256',v_sha),'PentaHook/PentaCertify/PentaLedger',null,'PentaCertify','3.0.0',v_sha,null,'ct.paypal.webhook.fabric.v3',null,'restricted');
  end if;
  return v_payload||jsonb_build_object('payload_sha256',v_sha,'resolved',v_count>0 and v_problem is not null);
end $$;

revoke all on function integration_control.paypal_webhook_reconcile_v3() from public,anon,authenticated;
revoke all on function integration_control.paypal_webhook_simulate_v3(text) from public,anon,authenticated;
revoke all on function integration_control.paypal_webhook_certify_and_resolve_v3() from public,anon,authenticated;
grant execute on function integration_control.paypal_webhook_reconcile_v3() to service_role;
grant execute on function integration_control.paypal_webhook_simulate_v3(text) to service_role;
grant execute on function integration_control.paypal_webhook_certify_and_resolve_v3() to service_role;

select cron.unschedule(jobid) from cron.job where jobname in ('ct-paypal-webhook-reconcile-v3','ct-paypal-webhook-certify-v3');
select cron.schedule('ct-paypal-webhook-reconcile-v3','47 7 * * *','select integration_control.paypal_webhook_reconcile_v3();');
select cron.schedule('ct-paypal-webhook-certify-v3','*/10 * * * *','select integration_control.paypal_webhook_certify_and_resolve_v3();');
