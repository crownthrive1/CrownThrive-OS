create table if not exists integration_control.stripe_webhook_bindings_v1 (
  binding_key text primary key,
  system_key text not null,
  lane text not null,
  target_url text not null,
  secret_vault_alias text not null,
  legacy_endpoint_id text,
  provider_endpoint_id text,
  connect_scope boolean not null default false,
  state text not null default 'pending' check (state in ('pending','active','held','retired')),
  provider_http_status integer,
  canary_http_status integer,
  canary_state text not null default 'not_run',
  enabled_events_sha256 text,
  provider_readback jsonb not null default '{}'::jsonb,
  last_verified_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.stripe_institutional_event_queue_v1 (
  queue_id uuid primary key default gen_random_uuid(),
  event_id text not null unique,
  system_key text not null,
  event_type text not null,
  object_type text,
  object_id text,
  connected_account text,
  livemode boolean not null,
  payload_sha256 text not null check (payload_sha256 ~ '^[0-9a-f]{64}$'),
  state text not null default 'queued' check (state in ('queued','processing','processed','held','ignored')),
  safe_summary jsonb not null default '{}'::jsonb,
  received_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists thivebase_private.stripe_institutional_event_payloads_v1 (
  event_id text primary key,
  system_key text not null,
  payload jsonb not null,
  payload_sha256 text not null check (payload_sha256 ~ '^[0-9a-f]{64}$'),
  received_at timestamptz not null default now()
);

create table if not exists integration_control.stripe_webhook_reconciliation_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  binding_key text not null,
  disposition text not null,
  legacy_endpoint_id text,
  provider_endpoint_id text,
  target_url text not null,
  provider_http_status integer,
  canary_http_status integer,
  evidence jsonb not null,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  observed_at timestamptz not null default now()
);

create index if not exists stripe_event_queue_state_received_idx on integration_control.stripe_institutional_event_queue_v1(state,received_at);
create index if not exists stripe_webhook_receipts_binding_observed_idx on integration_control.stripe_webhook_reconciliation_receipts_v1(binding_key,observed_at desc);

alter table integration_control.stripe_webhook_bindings_v1 enable row level security;
alter table integration_control.stripe_institutional_event_queue_v1 enable row level security;
alter table thivebase_private.stripe_institutional_event_payloads_v1 enable row level security;
alter table integration_control.stripe_webhook_reconciliation_receipts_v1 enable row level security;

revoke all on integration_control.stripe_webhook_bindings_v1 from public,anon,authenticated;
revoke all on integration_control.stripe_institutional_event_queue_v1 from public,anon,authenticated;
revoke all on thivebase_private.stripe_institutional_event_payloads_v1 from public,anon,authenticated;
revoke all on integration_control.stripe_webhook_reconciliation_receipts_v1 from public,anon,authenticated;
grant select,insert,update on integration_control.stripe_webhook_bindings_v1 to service_role;
grant select,insert,update on integration_control.stripe_institutional_event_queue_v1 to service_role;
grant select,insert on thivebase_private.stripe_institutional_event_payloads_v1 to service_role;
grant select,insert on integration_control.stripe_webhook_reconciliation_receipts_v1 to service_role;

drop policy if exists stripe_webhook_bindings_service_role_v1 on integration_control.stripe_webhook_bindings_v1;
create policy stripe_webhook_bindings_service_role_v1 on integration_control.stripe_webhook_bindings_v1 for all to service_role using (true) with check (true);
drop policy if exists stripe_event_queue_service_role_v1 on integration_control.stripe_institutional_event_queue_v1;
create policy stripe_event_queue_service_role_v1 on integration_control.stripe_institutional_event_queue_v1 for all to service_role using (true) with check (true);
drop policy if exists stripe_event_payloads_service_role_v1 on thivebase_private.stripe_institutional_event_payloads_v1;
create policy stripe_event_payloads_service_role_v1 on thivebase_private.stripe_institutional_event_payloads_v1 for select to service_role using (true);
drop policy if exists stripe_event_payloads_insert_service_role_v1 on thivebase_private.stripe_institutional_event_payloads_v1;
create policy stripe_event_payloads_insert_service_role_v1 on thivebase_private.stripe_institutional_event_payloads_v1 for insert to service_role with check (true);
drop policy if exists stripe_webhook_reconciliation_receipts_service_role_v1 on integration_control.stripe_webhook_reconciliation_receipts_v1;
create policy stripe_webhook_reconciliation_receipts_service_role_v1 on integration_control.stripe_webhook_reconciliation_receipts_v1 for select to service_role using (true);
drop policy if exists stripe_webhook_reconciliation_receipts_insert_service_role_v1 on integration_control.stripe_webhook_reconciliation_receipts_v1;
create policy stripe_webhook_reconciliation_receipts_insert_service_role_v1 on integration_control.stripe_webhook_reconciliation_receipts_v1 for insert to service_role with check (true);

create or replace function integration_control.reject_stripe_webhook_evidence_mutation_v1()
returns trigger language plpgsql security definer set search_path=pg_catalog,integration_control,thivebase_private as $$
begin raise exception 'Stripe webhook evidence is append-only'; end $$;
revoke all on function integration_control.reject_stripe_webhook_evidence_mutation_v1() from public,anon,authenticated;
grant execute on function integration_control.reject_stripe_webhook_evidence_mutation_v1() to service_role;

drop trigger if exists stripe_event_payloads_immutable_v1 on thivebase_private.stripe_institutional_event_payloads_v1;
create trigger stripe_event_payloads_immutable_v1 before update or delete on thivebase_private.stripe_institutional_event_payloads_v1 for each row execute function integration_control.reject_stripe_webhook_evidence_mutation_v1();
drop trigger if exists stripe_webhook_reconciliation_receipts_immutable_v1 on integration_control.stripe_webhook_reconciliation_receipts_v1;
create trigger stripe_webhook_reconciliation_receipts_immutable_v1 before update or delete on integration_control.stripe_webhook_reconciliation_receipts_v1 for each row execute function integration_control.reject_stripe_webhook_evidence_mutation_v1();

insert into integration_control.stripe_webhook_bindings_v1(binding_key,system_key,lane,target_url,secret_vault_alias,legacy_endpoint_id,connect_scope,state,metadata)
values
('ct.stripe.webhook.kjv-commerce.v1','ct.platform.kjv-sermon-toolkit','commerce','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/kjv-commerce-webhook?lane=commerce','kjv_stripe_commerce_webhook_secret_live','we_1U2zNpCJFUeGxc8StTnUBDUp',false,'pending',jsonb_build_object('authority','PentaHook/PentaCertify','money_movement',false,'provider_mutation_scope','webhook_endpoint_only')),
('ct.stripe.webhook.kjv-connect.v1','ct.platform.kjv-sermon-toolkit','connect','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/kjv-commerce-webhook?lane=connect','kjv_stripe_connect_webhook_secret_live','we_1U4SWCCJFUeGxc8StJW4IkD1',true,'pending',jsonb_build_object('authority','PentaHook/PentaCertify','money_movement',false,'provider_mutation_scope','webhook_endpoint_only')),
('ct.stripe.webhook.thrivetickets.v1','ct.platform.thrivetickets','institutional','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/thrivetickets-stripe-webhook','thrivetickets_stripe_webhook_secret_live','we_1PlvbcCJFUeGxc8SufIxZMXZ',true,'pending',jsonb_build_object('authority','PentaHook/PentaCertify','money_movement',false,'fulfillment_mode','institutional_receipt_and_governed_queue'))
on conflict(binding_key) do update set target_url=excluded.target_url,secret_vault_alias=excluded.secret_vault_alias,legacy_endpoint_id=excluded.legacy_endpoint_id,connect_scope=excluded.connect_scope,metadata=integration_control.stripe_webhook_bindings_v1.metadata||excluded.metadata,updated_at=now();
