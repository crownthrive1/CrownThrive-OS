-- CrownThrive OS — Stripe + PayPal institutional event evidence
-- Source projection for production-deployed provider ingress/readback fabric.
-- No credential values, money movement, checkout activation, or synthetic success.

create table if not exists integration_control.stripe_webhook_lanes_v2 (
  lane_key text primary key,
  display_name text not null,
  endpoint_slug text not null unique,
  secret_alias_candidates text[] not null,
  provider_account_scope text,
  active boolean not null default true,
  state text not null default 'configured',
  processing_target text not null,
  signature_tolerance_seconds integer not null default 300 check(signature_tolerance_seconds between 60 and 900),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.stripe_institutional_event_receipts_v2 (
  receipt_id uuid primary key default gen_random_uuid(),
  lane_key text not null references integration_control.stripe_webhook_lanes_v2(lane_key),
  provider_event_id text not null,
  provider_event_type text not null,
  livemode boolean,
  api_version text,
  provider_account text,
  provider_object_id text,
  payload_sha256 text not null,
  signature_verified boolean not null,
  provider_read_verified boolean not null default false,
  evidence_source text not null default 'webhook_signature',
  processing_state text not null default 'queued' check(processing_state in ('queued','processing','processed','held','failed','duplicate')),
  first_received_at timestamptz not null default now(),
  last_received_at timestamptz not null default now(),
  delivery_attempts integer not null default 1,
  safe_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(lane_key,provider_event_id)
);
create index if not exists stripe_event_receipts_state_time_v2
  on integration_control.stripe_institutional_event_receipts_v2(processing_state,first_received_at);
create index if not exists stripe_event_receipts_type_time_v2
  on integration_control.stripe_institutional_event_receipts_v2(provider_event_type,first_received_at desc);

create table if not exists integration_control.stripe_event_dispatch_queue_v2 (
  dispatch_id uuid primary key default gen_random_uuid(),
  receipt_id uuid not null unique references integration_control.stripe_institutional_event_receipts_v2(receipt_id),
  lane_key text not null,
  provider_event_id text not null,
  provider_event_type text not null,
  target_ref text not null,
  state text not null default 'queued' check(state in ('queued','claimed','processed','held','failed')),
  attempt_count integer not null default 0,
  next_attempt_at timestamptz not null default now(),
  lease_expires_at timestamptz,
  claimed_by text,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists stripe_event_dispatch_due_v2
  on integration_control.stripe_event_dispatch_queue_v2(state,next_attempt_at)
  where state in ('queued','failed');

create table if not exists integration_control.stripe_webhook_provider_reconciliation_v2 (
  reconciliation_id uuid primary key default gen_random_uuid(),
  provider_key_alias text not null,
  provider_endpoint_id text not null,
  lane_key text not null,
  old_url text,
  desired_url text not null,
  provider_list_status integer,
  provider_update_status integer,
  provider_readback_status integer,
  exact_url_match boolean not null default false,
  endpoint_status text,
  livemode boolean,
  secret_material_exposed boolean not null default false,
  state text not null,
  evidence_sha256 text not null,
  observed_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
create index if not exists stripe_webhook_provider_reconcile_lane_time_v2
  on integration_control.stripe_webhook_provider_reconciliation_v2(lane_key,observed_at desc);

create table if not exists integration_control.stripe_webhook_transport_probes_v2 (
  probe_id uuid primary key default gen_random_uuid(),
  lane_key text not null,
  endpoint_url text not null,
  http_status integer not null,
  response_sha256 text not null,
  expected_unsigned_rejection boolean not null,
  transport_reachable boolean not null,
  state text not null,
  observed_at timestamptz not null default now()
);
create index if not exists stripe_webhook_transport_probe_lane_time_v2
  on integration_control.stripe_webhook_transport_probes_v2(lane_key,observed_at desc);

alter table integration_control.stripe_webhook_lanes_v2 enable row level security;
alter table integration_control.stripe_institutional_event_receipts_v2 enable row level security;
alter table integration_control.stripe_event_dispatch_queue_v2 enable row level security;
alter table integration_control.stripe_webhook_provider_reconciliation_v2 enable row level security;
alter table integration_control.stripe_webhook_transport_probes_v2 enable row level security;

revoke all on integration_control.stripe_webhook_lanes_v2 from public,anon,authenticated;
revoke all on integration_control.stripe_institutional_event_receipts_v2 from public,anon,authenticated;
revoke all on integration_control.stripe_event_dispatch_queue_v2 from public,anon,authenticated;
revoke all on integration_control.stripe_webhook_provider_reconciliation_v2 from public,anon,authenticated;
revoke all on integration_control.stripe_webhook_transport_probes_v2 from public,anon,authenticated;

grant select,insert,update on integration_control.stripe_webhook_lanes_v2 to service_role;
grant select,insert,update on integration_control.stripe_institutional_event_receipts_v2 to service_role;
grant select,insert,update on integration_control.stripe_event_dispatch_queue_v2 to service_role;
grant select,insert on integration_control.stripe_webhook_provider_reconciliation_v2 to service_role;
grant select,insert on integration_control.stripe_webhook_transport_probes_v2 to service_role;

insert into integration_control.stripe_webhook_lanes_v2(
  lane_key,display_name,endpoint_slug,secret_alias_candidates,processing_target,state,metadata
) values
(
  'thrivetickets','ThriveTickets Stripe','thrivetickets-stripe-webhook',
  array['thrivetickets_stripe_webhook_secret','THRIVETICKETS_STRIPE_WEBHOOK_SECRET','stripe_thrivetickets_webhook_secret','STRIPE_WEBHOOK_SECRET_THRIVETICKETS'],
  'PentaHook/PentaTickets','configured',
  jsonb_build_object('event_ingress_only',true,'money_movement',false)
),
(
  'sermon-toolkit','KJV / Sermon Toolkit Stripe','sermon-toolkit-stripe-webhook',
  array['sermon_toolkit_stripe_webhook_secret','SERMON_TOOLKIT_STRIPE_WEBHOOK_SECRET','kjv_sermon_toolkit_stripe_webhook_secret','KJV_SERMON_TOOLKIT_STRIPE_WEBHOOK_SECRET','stripe_sermon_toolkit_webhook_secret'],
  'PentaHook/PentaGreen/SermonToolkit','configured',
  jsonb_build_object('event_ingress_only',true,'money_movement',false)
),
(
  'kjv-sermon-toolkit','KJV / Sermon Toolkit Stripe compatibility','kjv-sermon-toolkit-stripe-webhook',
  array['kjv_sermon_toolkit_stripe_webhook_secret','KJV_SERMON_TOOLKIT_STRIPE_WEBHOOK_SECRET','sermon_toolkit_stripe_webhook_secret','SERMON_TOOLKIT_STRIPE_WEBHOOK_SECRET','stripe_sermon_toolkit_webhook_secret'],
  'PentaHook/PentaGreen/SermonToolkit','configured',
  jsonb_build_object('compatibility_alias',true,'canonical_lane','sermon-toolkit','event_ingress_only',true,'money_movement',false)
),
(
  'stripe-global','Stripe Global Provider Readback','provider-api-readback',array[]::text[],
  'PentaHook/PentaLedger','readback',
  jsonb_build_object('webhook_endpoint',false,'provider_api_reconciliation',true,'money_movement',false)
)
on conflict(lane_key) do update set
  display_name=excluded.display_name,
  endpoint_slug=excluded.endpoint_slug,
  secret_alias_candidates=excluded.secret_alias_candidates,
  processing_target=excluded.processing_target,
  state=excluded.state,
  metadata=integration_control.stripe_webhook_lanes_v2.metadata||excluded.metadata,
  updated_at=now();

create or replace function integration_control.stripe_webhook_lane_runtime_v2(p_lane_key text)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,vault
as $$
declare
  v_lane integration_control.stripe_webhook_lanes_v2%rowtype;
  v_alias text;
begin
  select * into v_lane
  from integration_control.stripe_webhook_lanes_v2
  where lane_key=p_lane_key and active=true;

  if not found then
    return jsonb_build_object('ready',false,'reason','lane_not_active');
  end if;

  select c.alias into v_alias
  from unnest(v_lane.secret_alias_candidates) with ordinality as c(alias,ord)
  where exists(select 1 from vault.secrets s where s.name=c.alias)
  order by c.ord
  limit 1;

  return jsonb_build_object(
    'ready',v_alias is not null,
    'lane_key',v_lane.lane_key,
    'endpoint_slug',v_lane.endpoint_slug,
    'secret_alias',v_alias,
    'signature_tolerance_seconds',v_lane.signature_tolerance_seconds,
    'processing_target',v_lane.processing_target,
    'secret_value_exposed',false,
    'reason',case when v_alias is null then 'webhook_signing_secret_alias_unbound' end
  );
end $$;

create or replace function integration_control.record_stripe_webhook_receipt_v2(
  p_lane_key text,
  p_provider_event_id text,
  p_provider_event_type text,
  p_livemode boolean,
  p_api_version text,
  p_provider_account text,
  p_provider_object_id text,
  p_payload_sha256 text,
  p_signature_verified boolean,
  p_safe_metadata jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,chlom_runtime,extensions
as $$
declare
  v_receipt_id uuid;
  v_inserted boolean:=false;
  v_target text;
  v_payload jsonb;
  v_digest text;
begin
  if not p_signature_verified then
    raise exception 'stripe_signature_not_verified';
  end if;
  if coalesce(p_provider_event_id,'')='' or coalesce(p_provider_event_type,'')=''
     or coalesce(p_payload_sha256,'')='' then
    raise exception 'missing_required_event_identity';
  end if;

  select processing_target into v_target
  from integration_control.stripe_webhook_lanes_v2
  where lane_key=p_lane_key and active=true;
  if v_target is null then raise exception 'stripe_lane_not_active'; end if;

  insert into integration_control.stripe_institutional_event_receipts_v2(
    lane_key,provider_event_id,provider_event_type,livemode,api_version,
    provider_account,provider_object_id,payload_sha256,signature_verified,
    provider_read_verified,evidence_source,processing_state,safe_metadata
  ) values (
    p_lane_key,p_provider_event_id,p_provider_event_type,p_livemode,p_api_version,
    p_provider_account,p_provider_object_id,p_payload_sha256,true,false,
    'webhook_signature','queued',coalesce(p_safe_metadata,'{}'::jsonb)
  )
  on conflict(lane_key,provider_event_id) do update set
    last_received_at=now(),
    delivery_attempts=integration_control.stripe_institutional_event_receipts_v2.delivery_attempts+1,
    safe_metadata=integration_control.stripe_institutional_event_receipts_v2.safe_metadata||excluded.safe_metadata
  returning receipt_id,(xmax=0) into v_receipt_id,v_inserted;

  insert into integration_control.stripe_event_dispatch_queue_v2(
    receipt_id,lane_key,provider_event_id,provider_event_type,target_ref,state,evidence
  ) values (
    v_receipt_id,p_lane_key,p_provider_event_id,p_provider_event_type,v_target,'queued',
    jsonb_build_object('payload_sha256',p_payload_sha256,'signature_verified',true,'money_movement',false)
  ) on conflict(receipt_id) do nothing;

  v_payload:=jsonb_build_object(
    'receipt_id',v_receipt_id,
    'lane_key',p_lane_key,
    'provider_event_id',p_provider_event_id,
    'provider_event_type',p_provider_event_type,
    'livemode',p_livemode,
    'payload_sha256',p_payload_sha256,
    'signature_verified',true,
    'inserted',v_inserted,
    'processing_target',v_target,
    'money_movement',false
  );
  v_digest:=encode(extensions.digest(v_payload::text,'sha256'),'hex');

  if v_inserted then
    perform chlom_runtime.append_dail_event(
      'stripe.webhook.verified','provider_event',p_lane_key,v_payload,
      'PentaHook/PentaLedger',null,'PentaHook','2.0.0',v_digest,null,
      'ct.stripe.institutional-event-ingress.v2',null,'restricted'
    );
  end if;

  return jsonb_build_object(
    'ok',true,
    'receipt_id',v_receipt_id,
    'inserted',v_inserted,
    'duplicate',not v_inserted,
    'processing_state','queued',
    'payload_sha256',p_payload_sha256
  );
end $$;

create or replace function integration_control.stripe_webhook_transport_probe_v2()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,extensions
as $$
declare
  r record;
  v_resp extensions.http_response;
  v_sha text;
  v_expected boolean;
  v_total integer:=0;
  v_reachable integer:=0;
begin
  for r in
    select lane_key,
      'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/'||endpoint_slug as endpoint_url
    from integration_control.stripe_webhook_lanes_v2
    where lane_key in ('thrivetickets','sermon-toolkit','kjv-sermon-toolkit')
      and active=true
  loop
    begin
      v_resp:=extensions.http((
        'POST'::extensions.http_method,
        r.endpoint_url::varchar,
        array[row('content-type','application/json')::extensions.http_header],
        'application/json'::varchar,
        '{}'::varchar
      )::extensions.http_request);
    exception when others then
      v_resp.status:=599;
      v_resp.content:='{}';
    end;

    v_sha:=encode(extensions.digest(coalesce(v_resp.content,'')::text,'sha256'),'hex');
    v_expected:=v_resp.status=400
      and lower(coalesce(v_resp.content,'')) like '%stripe_signature_missing%';

    insert into integration_control.stripe_webhook_transport_probes_v2(
      lane_key,endpoint_url,http_status,response_sha256,
      expected_unsigned_rejection,transport_reachable,state
    ) values (
      r.lane_key,r.endpoint_url,v_resp.status,v_sha,v_expected,v_expected,
      case when v_expected then 'TRANSPORT_READY_SIGNATURE_REQUIRED' else 'HOLD_TRANSPORT' end
    );

    v_total:=v_total+1;
    if v_expected then v_reachable:=v_reachable+1; end if;
  end loop;

  return jsonb_build_object(
    'probed',v_total,
    'transport_ready',v_reachable,
    'all_ready',v_total>0 and v_total=v_reachable,
    'unsigned_request_accepted',false,
    'money_movement',false,
    'observed_at',now()
  );
end $$;

-- Provider URL reconciliation and event backfill are intentionally server-only.
-- The production definitions preserve existing enabled-event subscriptions,
-- mutate only matching known endpoints, require exact readback, and never key-hop.
-- See the public machine contract data/penta/provider-event-evidence-stripe-paypal.v2.json
-- and the restricted PRIVATE-PentaOS runbook/source for the complete adapters.

create table if not exists integration_control.paypal_provider_credentials_v1 (
  environment text primary key check(environment in ('live','sandbox')),
  client_id_alias_candidates text[] not null,
  client_secret_alias_candidates text[] not null,
  api_base text not null,
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.paypal_institutional_event_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  environment text not null,
  provider_event_id text not null,
  provider_event_type text not null,
  provider_create_time timestamptz,
  resource_type text,
  resource_id text,
  payload_sha256 text not null,
  evidence_source text not null default 'provider_api_readback',
  provider_read_verified boolean not null default true,
  webhook_signature_verified boolean not null default false,
  processing_state text not null default 'queued' check(processing_state in ('queued','processing','processed','held','failed')),
  safe_metadata jsonb not null default '{}'::jsonb,
  first_observed_at timestamptz not null default now(),
  last_observed_at timestamptz not null default now(),
  unique(environment,provider_event_id)
);
create index if not exists paypal_event_receipts_state_time_v1
  on integration_control.paypal_institutional_event_receipts_v1(processing_state,first_observed_at);
create index if not exists paypal_event_receipts_type_time_v1
  on integration_control.paypal_institutional_event_receipts_v1(provider_event_type,provider_create_time desc);

create table if not exists integration_control.paypal_event_poll_receipts_v1 (
  poll_id uuid primary key default gen_random_uuid(),
  environment text not null,
  credential_state text not null,
  oauth_http_status integer,
  events_http_status integer,
  events_seen integer not null default 0,
  new_receipts integer not null default 0,
  state text not null,
  evidence_sha256 text not null,
  secret_material_exposed boolean not null default false,
  observed_at timestamptz not null default now()
);

alter table integration_control.paypal_provider_credentials_v1 enable row level security;
alter table integration_control.paypal_institutional_event_receipts_v1 enable row level security;
alter table integration_control.paypal_event_poll_receipts_v1 enable row level security;
revoke all on integration_control.paypal_provider_credentials_v1 from public,anon,authenticated;
revoke all on integration_control.paypal_institutional_event_receipts_v1 from public,anon,authenticated;
revoke all on integration_control.paypal_event_poll_receipts_v1 from public,anon,authenticated;
grant select,insert,update on integration_control.paypal_provider_credentials_v1 to service_role;
grant select,insert,update on integration_control.paypal_institutional_event_receipts_v1 to service_role;
grant select,insert on integration_control.paypal_event_poll_receipts_v1 to service_role;

insert into integration_control.paypal_provider_credentials_v1(
  environment,client_id_alias_candidates,client_secret_alias_candidates,api_base,metadata
) values
(
  'live',
  array['PAYPAL_LIVE_CLIENT_ID','paypal_live_client_id','PAYPAL_CLIENT_ID','paypal_client_id'],
  array['PAYPAL_LIVE_CLIENT_SECRET','paypal_live_client_secret','PAYPAL_CLIENT_SECRET','paypal_client_secret'],
  'https://api-m.paypal.com',
  jsonb_build_object('event_readback_only',true,'money_movement',false)
),
(
  'sandbox',
  array['PAYPAL_SANDBOX_CLIENT_ID','paypal_sandbox_client_id'],
  array['PAYPAL_SANDBOX_CLIENT_SECRET','paypal_sandbox_client_secret'],
  'https://api-m.sandbox.paypal.com',
  jsonb_build_object('event_readback_only',true,'money_movement',false)
)
on conflict(environment) do update set
  client_id_alias_candidates=excluded.client_id_alias_candidates,
  client_secret_alias_candidates=excluded.client_secret_alias_candidates,
  api_base=excluded.api_base,
  metadata=integration_control.paypal_provider_credentials_v1.metadata||excluded.metadata,
  updated_at=now();

revoke all on function integration_control.stripe_webhook_lane_runtime_v2(text) from public,anon,authenticated;
revoke all on function integration_control.record_stripe_webhook_receipt_v2(text,text,text,boolean,text,text,text,text,boolean,jsonb) from public,anon,authenticated;
revoke all on function integration_control.stripe_webhook_transport_probe_v2() from public,anon,authenticated;
grant execute on function integration_control.stripe_webhook_lane_runtime_v2(text) to service_role;
grant execute on function integration_control.record_stripe_webhook_receipt_v2(text,text,text,boolean,text,text,text,text,boolean,jsonb) to service_role;
grant execute on function integration_control.stripe_webhook_transport_probe_v2() to service_role;

-- Exact scheduled controls are protected by PentaSELF required_cron_baseline_v2:
-- ct-stripe-webhook-transport-watch-v2       */15 * * * *
-- ct-stripe-provider-event-backfill-v2       7 * * * *
-- ct-stripe-webhook-provider-reconcile-v2   23 * * * *
-- ct-stripe-p0-health-reconcile-v2          */10 * * * *
-- ct-paypal-provider-event-backfill-v1      13 * * * *
