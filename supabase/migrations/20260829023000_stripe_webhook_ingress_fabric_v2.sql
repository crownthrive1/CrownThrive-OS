create schema if not exists integration_control;

create table if not exists integration_control.stripe_webhook_targets_v2 (
  target_key text primary key,
  system_ref text not null,
  endpoint_url text not null unique,
  signing_secret_alias text not null unique,
  provider_endpoint_id text unique,
  provider_state text not null default 'UNBOUND',
  ingress_state text not null default 'PENDING',
  desired_enabled_events text[] not null,
  last_provider_sync_at timestamptz,
  last_local_canary_at timestamptz,
  last_live_event_at timestamptz,
  retired_provider_endpoint_ids text[] not null default '{}'::text[],
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint stripe_webhook_target_key_v2 check (target_key in ('thrivetickets','sermon_toolkit'))
);

create table if not exists integration_control.stripe_webhook_events_v2 (
  stripe_event_id text primary key,
  target_key text not null references integration_control.stripe_webhook_targets_v2(target_key),
  event_type text not null,
  livemode boolean not null,
  api_version text,
  provider_created_at timestamptz,
  object_id text,
  payload jsonb not null,
  payload_sha256 text not null,
  signature_timestamp bigint not null,
  signature_verified boolean not null,
  source_kind text not null,
  processing_state text not null default 'RECEIVED',
  received_at timestamptz not null default now(),
  expires_at timestamptz not null default (now()+interval '90 days'),
  created_at timestamptz not null default now()
);
create index if not exists stripe_webhook_events_target_time_v2 on integration_control.stripe_webhook_events_v2(target_key,received_at desc);
create index if not exists stripe_webhook_events_type_time_v2 on integration_control.stripe_webhook_events_v2(event_type,received_at desc);
create index if not exists stripe_webhook_events_processing_v2 on integration_control.stripe_webhook_events_v2(processing_state,received_at);

create table if not exists integration_control.stripe_webhook_outbox_v2 (
  outbox_id uuid primary key default gen_random_uuid(),
  stripe_event_id text not null references integration_control.stripe_webhook_events_v2(stripe_event_id),
  target_key text not null,
  handler_ref text not null,
  state text not null default 'QUEUED',
  attempt_count integer not null default 0,
  max_attempts integer not null default 8,
  next_attempt_at timestamptz not null default now(),
  lease_expires_at timestamptz,
  last_error_code text,
  result jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(stripe_event_id,handler_ref)
);
create index if not exists stripe_webhook_outbox_due_v2 on integration_control.stripe_webhook_outbox_v2(state,next_attempt_at) where state in ('QUEUED','RETRY');

create table if not exists integration_control.stripe_webhook_receipts_v2 (
  receipt_id uuid primary key default gen_random_uuid(),
  receipt_kind text not null,
  target_key text not null,
  stripe_event_id text,
  provider_endpoint_id text,
  state text not null,
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  observed_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
create index if not exists stripe_webhook_receipts_target_time_v2 on integration_control.stripe_webhook_receipts_v2(target_key,observed_at desc);

alter table integration_control.stripe_webhook_targets_v2 enable row level security;
alter table integration_control.stripe_webhook_events_v2 enable row level security;
alter table integration_control.stripe_webhook_outbox_v2 enable row level security;
alter table integration_control.stripe_webhook_receipts_v2 enable row level security;
revoke all on integration_control.stripe_webhook_targets_v2,integration_control.stripe_webhook_events_v2,integration_control.stripe_webhook_outbox_v2,integration_control.stripe_webhook_receipts_v2 from public,anon,authenticated;
grant select,insert,update,delete on integration_control.stripe_webhook_targets_v2,integration_control.stripe_webhook_events_v2,integration_control.stripe_webhook_outbox_v2 to service_role;
grant select,insert on integration_control.stripe_webhook_receipts_v2 to service_role;

create policy stripe_webhook_targets_service_v2 on integration_control.stripe_webhook_targets_v2 for all to service_role using(true) with check(true);
create policy stripe_webhook_events_service_v2 on integration_control.stripe_webhook_events_v2 for all to service_role using(true) with check(true);
create policy stripe_webhook_outbox_service_v2 on integration_control.stripe_webhook_outbox_v2 for all to service_role using(true) with check(true);
create policy stripe_webhook_receipts_select_service_v2 on integration_control.stripe_webhook_receipts_v2 for select to service_role using(true);
create policy stripe_webhook_receipts_insert_service_v2 on integration_control.stripe_webhook_receipts_v2 for insert to service_role with check(true);

create or replace function integration_control.stripe_webhook_immutable_v2()
returns trigger language plpgsql security definer set search_path=pg_catalog,integration_control as $$
begin raise exception 'Stripe webhook event/receipt evidence is append-only'; end $$;
revoke all on function integration_control.stripe_webhook_immutable_v2() from public,anon,authenticated;
grant execute on function integration_control.stripe_webhook_immutable_v2() to service_role;
drop trigger if exists stripe_webhook_events_immutable_v2 on integration_control.stripe_webhook_events_v2;
create trigger stripe_webhook_events_immutable_v2 before update or delete on integration_control.stripe_webhook_events_v2 for each row execute function integration_control.stripe_webhook_immutable_v2();
drop trigger if exists stripe_webhook_receipts_immutable_v2 on integration_control.stripe_webhook_receipts_v2;
create trigger stripe_webhook_receipts_immutable_v2 before update or delete on integration_control.stripe_webhook_receipts_v2 for each row execute function integration_control.stripe_webhook_immutable_v2();

insert into integration_control.stripe_webhook_targets_v2(target_key,system_ref,endpoint_url,signing_secret_alias,desired_enabled_events,metadata)
values
('thrivetickets','ct.system.thrivetickets','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/stripe-webhook-ingress-v2/thrivetickets','stripe_webhook_thrivetickets_v2',array['checkout.session.completed','checkout.session.async_payment_succeeded','checkout.session.async_payment_failed','payment_intent.succeeded','payment_intent.payment_failed','charge.refunded','charge.dispute.created'],jsonb_build_object('owner','PentaHook/PentaLedger/PentaCertify','money_movement_authority',false,'fulfillment_effect','outbox_only')),
('sermon_toolkit','ct.system.kjv-sermon-toolkit','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/stripe-webhook-ingress-v2/sermon_toolkit','stripe_webhook_sermon_toolkit_v2',array['checkout.session.completed','checkout.session.async_payment_succeeded','checkout.session.async_payment_failed','payment_intent.succeeded','payment_intent.payment_failed','charge.refunded','charge.dispute.created','customer.subscription.created','customer.subscription.updated','customer.subscription.deleted','invoice.paid','invoice.payment_failed'],jsonb_build_object('owner','PentaHook/PentaLedger/PentaCertify','money_movement_authority',false,'fulfillment_effect','outbox_only'))
on conflict(target_key) do update set system_ref=excluded.system_ref,endpoint_url=excluded.endpoint_url,signing_secret_alias=excluded.signing_secret_alias,desired_enabled_events=excluded.desired_enabled_events,metadata=integration_control.stripe_webhook_targets_v2.metadata||excluded.metadata,updated_at=now();

do $$
begin
  if not exists(select 1 from vault.secrets where name='stripe_webhook_bootstrap_control_v2') then
    perform vault.create_secret(encode(extensions.gen_random_bytes(32),'hex'),'stripe_webhook_bootstrap_control_v2','CrownThrive Stripe webhook bootstrap control. Server-side only; no user-facing exposure.',null);
  end if;
end $$;

create or replace function public.stripe_webhook_resolve_live_secret_alias_v2()
returns text language sql security definer set search_path=pg_catalog,vault as $$
select name from vault.decrypted_secrets
where lower(name) like '%stripe%' and decrypted_secret like 'sk_live_%'
order by case when lower(name) in ('stripe_secret_key','stripe_live_secret_key') then 0 when lower(name) like '%live%' then 1 else 2 end, updated_at desc
limit 1
$$;
revoke all on function public.stripe_webhook_resolve_live_secret_alias_v2() from public,anon,authenticated;
grant execute on function public.stripe_webhook_resolve_live_secret_alias_v2() to service_role;

create or replace function public.ct_provider_secret_upsert_v2(p_name text,p_secret text,p_description text)
returns jsonb language plpgsql security definer set search_path=pg_catalog,vault,extensions as $$
declare v_id uuid; v_sha text;
begin
  if p_name is null or p_secret is null or length(p_secret)<16 then raise exception 'invalid_secret_material'; end if;
  if p_name not in ('stripe_webhook_thrivetickets_v2','stripe_webhook_sermon_toolkit_v2') then raise exception 'secret_alias_not_allowed'; end if;
  select id into v_id from vault.secrets where name=p_name limit 1;
  if v_id is null then
    perform vault.create_secret(p_secret,p_name,p_description,null);
  else
    perform vault.update_secret(v_id,p_secret,p_name,p_description,null);
  end if;
  v_sha:=encode(extensions.digest(p_secret,'sha256'),'hex');
  return jsonb_build_object('stored',true,'name',p_name,'fingerprint_sha256',v_sha,'secret_exposed',false);
end $$;
revoke all on function public.ct_provider_secret_upsert_v2(text,text,text) from public,anon,authenticated;
grant execute on function public.ct_provider_secret_upsert_v2(text,text,text) to service_role;

create or replace function public.stripe_webhook_target_config_v2(p_target_key text)
returns jsonb language sql security definer set search_path=pg_catalog,integration_control as $$
select jsonb_build_object('target_key',target_key,'system_ref',system_ref,'endpoint_url',endpoint_url,'signing_secret_alias',signing_secret_alias,'provider_endpoint_id',provider_endpoint_id,'provider_state',provider_state,'ingress_state',ingress_state,'desired_enabled_events',to_jsonb(desired_enabled_events))
from integration_control.stripe_webhook_targets_v2 where target_key=p_target_key
$$;
revoke all on function public.stripe_webhook_target_config_v2(text) from public,anon,authenticated;
grant execute on function public.stripe_webhook_target_config_v2(text) to service_role;

create or replace function public.stripe_webhook_target_list_v2()
returns jsonb language sql security definer set search_path=pg_catalog,integration_control as $$
select coalesce(jsonb_agg(jsonb_build_object('target_key',target_key,'system_ref',system_ref,'endpoint_url',endpoint_url,'signing_secret_alias',signing_secret_alias,'provider_endpoint_id',provider_endpoint_id,'desired_enabled_events',to_jsonb(desired_enabled_events)) order by target_key),'[]'::jsonb)
from integration_control.stripe_webhook_targets_v2
$$;
revoke all on function public.stripe_webhook_target_list_v2() from public,anon,authenticated;
grant execute on function public.stripe_webhook_target_list_v2() to service_role;

create or replace function public.stripe_webhook_record_event_v2(p_target_key text,p_event jsonb,p_payload_sha256 text,p_signature_timestamp bigint,p_signature_verified boolean,p_source_kind text)
returns jsonb language plpgsql security definer set search_path=pg_catalog,integration_control,extensions,chlom_runtime as $$
declare
  v_event_id text:=p_event->>'id';
  v_event_type text:=p_event->>'type';
  v_inserted boolean:=false;
  v_receipt uuid;
  v_receipt_sha text;
  v_payload jsonb;
  v_created_at timestamptz;
  v_object_id text;
begin
  if p_target_key not in ('thrivetickets','sermon_toolkit') then raise exception 'unknown_target'; end if;
  if not p_signature_verified then raise exception 'signature_not_verified'; end if;
  if coalesce(v_event_id,'')='' or coalesce(v_event_type,'')='' then raise exception 'invalid_stripe_event'; end if;
  if coalesce((p_event->>'created')::bigint,0)>0 then v_created_at:=to_timestamp((p_event->>'created')::bigint); end if;
  v_object_id:=p_event#>>'{data,object,id}';
  insert into integration_control.stripe_webhook_events_v2(stripe_event_id,target_key,event_type,livemode,api_version,provider_created_at,object_id,payload,payload_sha256,signature_timestamp,signature_verified,source_kind)
  values(v_event_id,p_target_key,v_event_type,coalesce((p_event->>'livemode')::boolean,false),p_event->>'api_version',v_created_at,v_object_id,p_event,p_payload_sha256,p_signature_timestamp,true,p_source_kind)
  on conflict(stripe_event_id) do nothing;
  get diagnostics v_inserted=row_count;
  if v_inserted then
    insert into integration_control.stripe_webhook_outbox_v2(stripe_event_id,target_key,handler_ref)
    values(v_event_id,p_target_key,case when p_target_key='thrivetickets' then 'ct.handler.thrivetickets.stripe.v2' else 'ct.handler.sermon-toolkit.stripe.v2' end)
    on conflict do nothing;
  end if;
  v_payload:=jsonb_build_object('stripe_event_id',v_event_id,'target_key',p_target_key,'event_type',v_event_type,'livemode',coalesce((p_event->>'livemode')::boolean,false),'object_id',v_object_id,'payload_sha256',p_payload_sha256,'signature_verified',true,'source_kind',p_source_kind,'duplicate',not v_inserted,'received_at',now(),'money_movement_authority',false);
  v_receipt_sha:=encode(extensions.digest(v_payload::text,'sha256'),'hex');
  insert into integration_control.stripe_webhook_receipts_v2(receipt_kind,target_key,stripe_event_id,state,evidence,evidence_sha256)
  values('EVENT_INGRESS',p_target_key,v_event_id,case when v_inserted then 'RECEIVED' else 'DUPLICATE_ACK' end,v_payload,v_receipt_sha) returning receipt_id into v_receipt;
  if v_inserted then
    update integration_control.stripe_webhook_targets_v2 set last_live_event_at=case when coalesce((p_event->>'livemode')::boolean,false) and p_source_kind='stripe_provider' then now() else last_live_event_at end,updated_at=now() where target_key=p_target_key;
    begin
      perform chlom_runtime.append_dail_event('stripe.webhook.event.received','provider_event','stripe:'||v_event_id,v_payload,'PentaHook/PentaLedger',null,'PentaHook','2.0.0',v_receipt_sha,null,'ct.stripe.webhook-ingress.v2',null,'restricted');
    exception when others then null;
    end;
  end if;
  return jsonb_build_object('ok',true,'duplicate',not v_inserted,'receipt_id',v_receipt,'event_id',v_event_id,'target_key',p_target_key,'processing_state','QUEUED','secret_exposed',false);
end $$;
revoke all on function public.stripe_webhook_record_event_v2(text,jsonb,text,bigint,boolean,text) from public,anon,authenticated;
grant execute on function public.stripe_webhook_record_event_v2(text,jsonb,text,bigint,boolean,text) to service_role;

create or replace function public.stripe_webhook_record_bootstrap_v2(p_target_key text,p_provider_endpoint_id text,p_provider_state text,p_canary_http_status integer,p_retired_ids text[],p_evidence jsonb)
returns jsonb language plpgsql security definer set search_path=pg_catalog,integration_control,extensions,penta_self,chlom_runtime as $$
declare v_sha text; v_receipt uuid; v_title text; v_state text;
begin
  v_state:=case when p_provider_state='enabled' and p_canary_http_status between 200 and 299 then 'PRODUCTION_HEALTHY' else 'HOLD' end;
  v_sha:=encode(extensions.digest(coalesce(p_evidence,'{}'::jsonb)::text,'sha256'),'hex');
  update integration_control.stripe_webhook_targets_v2
     set provider_endpoint_id=p_provider_endpoint_id,provider_state=p_provider_state,ingress_state=v_state,last_provider_sync_at=now(),last_local_canary_at=case when p_canary_http_status between 200 and 299 then now() else last_local_canary_at end,retired_provider_endpoint_ids=coalesce(p_retired_ids,'{}'::text[]),metadata=metadata||jsonb_build_object('bootstrap_evidence_sha256',v_sha,'local_signed_canary_http_status',p_canary_http_status,'provider_endpoint_id',p_provider_endpoint_id,'broken_predecessors_retired',coalesce(array_length(p_retired_ids,1),0),'secret_exposed',false),updated_at=now()
   where target_key=p_target_key;
  insert into integration_control.stripe_webhook_receipts_v2(receipt_kind,target_key,provider_endpoint_id,state,evidence,evidence_sha256)
  values('ENDPOINT_BOOTSTRAP',p_target_key,p_provider_endpoint_id,v_state,coalesce(p_evidence,'{}'::jsonb)||jsonb_build_object('canary_http_status',p_canary_http_status,'retired_ids',coalesce(to_jsonb(p_retired_ids),'[]'::jsonb),'secret_exposed',false),v_sha) returning receipt_id into v_receipt;
  begin
    perform chlom_runtime.append_dail_event('stripe.webhook.endpoint.bootstrap','provider_configuration','stripe:'||p_provider_endpoint_id,jsonb_build_object('target_key',p_target_key,'provider_state',p_provider_state,'ingress_state',v_state,'canary_http_status',p_canary_http_status,'retired_count',coalesce(array_length(p_retired_ids,1),0),'evidence_sha256',v_sha,'money_movement_authority',false),'PentaHook/PentaCredentials/PentaCertify',null,'PentaHook','2.0.0',v_sha,null,'ct.stripe.webhook-ingress.v2',null,'internal');
  exception when others then null;
  end;
  if v_state='PRODUCTION_HEALTHY' then
    v_title:=case when p_target_key='thrivetickets' then 'ThriveTickets Stripe webhook returning HTTP 404' else 'KJV/Sermon Toolkit Stripe webhook returning HTTP 503' end;
    perform penta_self.resolve_problem_verified_v2(v_title,'Broken Stripe webhook endpoint replaced by a provider-enabled centralized signed ingress; predecessor endpoint(s) retired after a valid signed local canary returned 2xx.',jsonb_build_object('target_key',p_target_key,'provider_endpoint_id',p_provider_endpoint_id,'provider_state',p_provider_state,'local_signed_canary_http_status',p_canary_http_status,'retired_provider_endpoint_ids',coalesce(to_jsonb(p_retired_ids),'[]'::jsonb),'event_ledger','integration_control.stripe_webhook_events_v2','money_movement_authority',false),'stripe-api+supabase-edge:ct.stripe.webhook-ingress.v2','NEWER_PROVIDER_ENDPOINT_FAILURE_ONLY');
  end if;
  return jsonb_build_object('target_key',p_target_key,'state',v_state,'receipt_id',v_receipt,'evidence_sha256',v_sha,'secret_exposed',false);
end $$;
revoke all on function public.stripe_webhook_record_bootstrap_v2(text,text,text,integer,text[],jsonb) from public,anon,authenticated;
grant execute on function public.stripe_webhook_record_bootstrap_v2(text,text,text,integer,text[],jsonb) to service_role;

create or replace function public.stripe_webhook_status_v2()
returns jsonb language sql security definer set search_path=pg_catalog,integration_control as $$
select jsonb_build_object(
 'contract','ct.stripe.webhook-ingress.v2',
 'targets',(select coalesce(jsonb_agg(jsonb_build_object('target_key',target_key,'system_ref',system_ref,'endpoint_url',endpoint_url,'provider_endpoint_id',provider_endpoint_id,'provider_state',provider_state,'ingress_state',ingress_state,'last_provider_sync_at',last_provider_sync_at,'last_local_canary_at',last_local_canary_at,'last_live_event_at',last_live_event_at,'retired_count',coalesce(array_length(retired_provider_endpoint_ids,1),0)) order by target_key),'[]'::jsonb) from integration_control.stripe_webhook_targets_v2),
 'event_count',(select count(*) from integration_control.stripe_webhook_events_v2 where source_kind='stripe_provider'),
 'canary_count',(select count(*) from integration_control.stripe_webhook_events_v2 where source_kind='bootstrap_canary'),
 'queued_outbox',(select count(*) from integration_control.stripe_webhook_outbox_v2 where state in ('QUEUED','RETRY')),
 'money_movement_authority',false,
 'secret_exposed',false,
 'observed_at',now()
) $$;
revoke all on function public.stripe_webhook_status_v2() from public,anon,authenticated;
grant execute on function public.stripe_webhook_status_v2() to service_role;
