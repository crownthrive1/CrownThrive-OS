create table if not exists integration_control.stripe_webhook_lane_bindings_v1 (
  lane_key text primary key,
  system_ref text not null,
  provider_account_mode text not null check (provider_account_mode in ('live','test')),
  stripe_api_secret_alias text not null,
  provider_endpoint_id text,
  provider_endpoint_url text not null,
  provider_endpoint_status text,
  webhook_secret_alias text not null unique,
  old_provider_endpoint_id text,
  old_provider_endpoint_url text,
  enabled_events jsonb not null default '["*"]'::jsonb,
  state text not null default 'planned' check (state in ('planned','provisioning','canary_verified','production','hold','retired')),
  signature_verification_required boolean not null default true,
  dedupe_required boolean not null default true,
  canary_http_status integer,
  canary_verified_at timestamptz,
  provider_readback_at timestamptz,
  old_endpoint_disabled boolean not null default false,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.stripe_institutional_event_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  lane_key text not null references integration_control.stripe_webhook_lane_bindings_v1(lane_key),
  stripe_event_id text not null,
  event_type text not null,
  event_created_at timestamptz,
  livemode boolean not null,
  object_type text,
  object_id text,
  customer_ref text,
  subscription_ref text,
  payment_intent_ref text,
  checkout_session_ref text,
  amount_minor bigint,
  currency text,
  canary boolean not null default false,
  signature_timestamp bigint not null,
  payload_sha256 text not null,
  safe_event jsonb not null default '{}'::jsonb,
  state text not null default 'received' check (state in ('received','routed','processed','held','canary_verified','failed')),
  received_at timestamptz not null default now(),
  processed_at timestamptz,
  created_at timestamptz not null default now(),
  unique(lane_key,stripe_event_id)
);

create table if not exists integration_control.stripe_event_handoffs_v1 (
  handoff_id uuid primary key default gen_random_uuid(),
  receipt_id uuid not null unique references integration_control.stripe_institutional_event_receipts_v1(receipt_id),
  lane_key text not null,
  target_system text not null,
  event_type text not null,
  state text not null default 'queued' check (state in ('queued','claimed','processed','held','failed','canary_noop')),
  attempt_count integer not null default 0,
  next_attempt_at timestamptz not null default now(),
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists stripe_event_receipts_lane_state_idx
  on integration_control.stripe_institutional_event_receipts_v1(lane_key,state,received_at desc);
create index if not exists stripe_event_receipts_type_idx
  on integration_control.stripe_institutional_event_receipts_v1(event_type,received_at desc);
create index if not exists stripe_event_handoffs_due_idx
  on integration_control.stripe_event_handoffs_v1(state,next_attempt_at)
  where state in ('queued','failed');

alter table integration_control.stripe_webhook_lane_bindings_v1 enable row level security;
alter table integration_control.stripe_institutional_event_receipts_v1 enable row level security;
alter table integration_control.stripe_event_handoffs_v1 enable row level security;
revoke all on integration_control.stripe_webhook_lane_bindings_v1 from public, anon, authenticated;
revoke all on integration_control.stripe_institutional_event_receipts_v1 from public, anon, authenticated;
revoke all on integration_control.stripe_event_handoffs_v1 from public, anon, authenticated;
grant select, insert, update on integration_control.stripe_webhook_lane_bindings_v1 to service_role;
grant select, insert, update on integration_control.stripe_institutional_event_receipts_v1 to service_role;
grant select, insert, update on integration_control.stripe_event_handoffs_v1 to service_role;

drop policy if exists stripe_webhook_lane_bindings_service_role_v1 on integration_control.stripe_webhook_lane_bindings_v1;
create policy stripe_webhook_lane_bindings_service_role_v1 on integration_control.stripe_webhook_lane_bindings_v1 for all to service_role using (true) with check (true);
drop policy if exists stripe_event_receipts_service_role_v1 on integration_control.stripe_institutional_event_receipts_v1;
create policy stripe_event_receipts_service_role_v1 on integration_control.stripe_institutional_event_receipts_v1 for all to service_role using (true) with check (true);
drop policy if exists stripe_event_handoffs_service_role_v1 on integration_control.stripe_event_handoffs_v1;
create policy stripe_event_handoffs_service_role_v1 on integration_control.stripe_event_handoffs_v1 for all to service_role using (true) with check (true);

create or replace function integration_control.reject_stripe_receipt_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path=pg_catalog,integration_control
as $$
begin
  if tg_op='DELETE' then
    raise exception 'stripe institutional receipts are append-preserving';
  end if;
  if new.lane_key<>old.lane_key
     or new.stripe_event_id<>old.stripe_event_id
     or new.payload_sha256<>old.payload_sha256
     or new.safe_event<>old.safe_event
     or new.received_at<>old.received_at then
    raise exception 'immutable Stripe receipt evidence cannot be rewritten';
  end if;
  return new;
end $$;
revoke all on function integration_control.reject_stripe_receipt_mutation_v1() from public, anon, authenticated;
grant execute on function integration_control.reject_stripe_receipt_mutation_v1() to service_role;
drop trigger if exists stripe_receipt_immutability_v1 on integration_control.stripe_institutional_event_receipts_v1;
create trigger stripe_receipt_immutability_v1
  before update or delete on integration_control.stripe_institutional_event_receipts_v1
  for each row execute function integration_control.reject_stripe_receipt_mutation_v1();

create or replace function integration_control.stripe_webhook_repair_plan_v1()
returns jsonb
language sql
security definer
set search_path=pg_catalog,integration_control
as $$
with latest_observation as (
  select distinct on (key_fingerprint,endpoint_id)
    secret_alias,key_mode,provider_http_status,endpoint_id,endpoint_url,
    endpoint_status,livemode,api_version,enabled_events,observed_at
  from integration_control.stripe_webhook_provider_inventory_v1
  where endpoint_id is not null
  order by key_fingerprint,endpoint_id,observed_at desc
), classified as (
  select *,
    case
      when lower(endpoint_url) ~ '(thrivetickets|thrive[-_]?tickets|ticket)' then 'thrivetickets'
      when lower(endpoint_url) ~ '(kjv|sermon[-_]?toolkit|sermontoolkit)' then 'sermon-toolkit'
      else null
    end as lane_key
  from latest_observation
  where endpoint_status='enabled'
), ranked as (
  select *,
    row_number() over(partition by lane_key order by livemode desc,observed_at desc,endpoint_id) as rn,
    count(*) over(partition by lane_key) as lane_count
  from classified
  where lane_key is not null
)
select jsonb_build_object(
  'candidates',coalesce(jsonb_agg(jsonb_build_object(
    'lane_key',lane_key,
    'candidate_count',lane_count,
    'stripe_api_secret_alias',secret_alias,
    'provider_account_mode',case when livemode then 'live' else 'test' end,
    'old_provider_endpoint_id',endpoint_id,
    'old_provider_endpoint_url',endpoint_url,
    'old_provider_endpoint_status',endpoint_status,
    'enabled_events',coalesce(enabled_events,'["*"]'::jsonb),
    'api_version',api_version,
    'provider_inventory_http_status',provider_http_status,
    'observed_at',observed_at
  ) order by lane_key),'[]'::jsonb),
  'candidate_count',count(*),
  'ambiguous_lanes',coalesce(jsonb_agg(lane_key) filter(where lane_count<>1),'[]'::jsonb),
  'raw_credentials_exposed',false,
  'generated_at',now()
)
from ranked where rn=1
$$;
revoke all on function integration_control.stripe_webhook_repair_plan_v1() from public, anon, authenticated;
grant execute on function integration_control.stripe_webhook_repair_plan_v1() to service_role;

create or replace function integration_control.stripe_webhook_store_replacement_v1(
  p_lane_key text,
  p_system_ref text,
  p_provider_account_mode text,
  p_stripe_api_secret_alias text,
  p_new_endpoint_id text,
  p_new_endpoint_url text,
  p_new_endpoint_status text,
  p_webhook_secret text,
  p_old_endpoint_id text,
  p_old_endpoint_url text,
  p_enabled_events jsonb,
  p_provider_response_sha256 text
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,vault,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_secret_alias text;
  v_id uuid;
  v_webhook_sha text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if p_lane_key='thrivetickets' then
    v_secret_alias:='stripe_thrivetickets_webhook_signing_secret_v1';
  elsif p_lane_key='sermon-toolkit' then
    v_secret_alias:='stripe_sermon_toolkit_webhook_signing_secret_v1';
  else
    raise exception 'stripe_lane_not_allowed';
  end if;
  if p_provider_account_mode not in ('live','test') then raise exception 'invalid_account_mode'; end if;
  if p_new_endpoint_id !~ '^we_' or p_new_endpoint_status not in ('enabled','active') then raise exception 'provider_endpoint_not_enabled'; end if;
  if p_new_endpoint_url !~ '^https://tzajnzshmtzjenqulehq\.supabase\.co/functions/v1/stripe-institutional-webhook-v1\?lane=' then raise exception 'endpoint_url_not_canonical'; end if;
  if p_webhook_secret is null or p_webhook_secret !~ '^whsec_' or length(p_webhook_secret)>4096 then raise exception 'invalid_webhook_secret'; end if;
  if not exists(select 1 from vault.secrets where name=p_stripe_api_secret_alias) then raise exception 'stripe_api_secret_alias_missing'; end if;
  v_webhook_sha:=encode(extensions.digest(p_webhook_secret,'sha256'),'hex');

  select id into v_id from vault.secrets where name=v_secret_alias limit 1;
  if v_id is null then
    perform vault.create_secret(
      p_webhook_secret,
      v_secret_alias,
      format('Stripe webhook signing secret for CrownThrive lane %s / endpoint %s. Restricted server-side custody.',p_lane_key,p_new_endpoint_id),
      null
    );
  else
    perform vault.update_secret(
      v_id,
      p_webhook_secret,
      v_secret_alias,
      format('Stripe webhook signing secret for CrownThrive lane %s / endpoint %s. Restricted server-side custody.',p_lane_key,p_new_endpoint_id),
      null
    );
  end if;

  insert into integration_control.stripe_webhook_lane_bindings_v1(
    lane_key,system_ref,provider_account_mode,stripe_api_secret_alias,
    provider_endpoint_id,provider_endpoint_url,provider_endpoint_status,
    webhook_secret_alias,old_provider_endpoint_id,old_provider_endpoint_url,
    enabled_events,state,evidence
  ) values (
    p_lane_key,p_system_ref,p_provider_account_mode,p_stripe_api_secret_alias,
    p_new_endpoint_id,p_new_endpoint_url,p_new_endpoint_status,
    v_secret_alias,p_old_endpoint_id,p_old_endpoint_url,
    coalesce(p_enabled_events,'["*"]'::jsonb),'provisioning',
    jsonb_build_object(
      'provider_response_sha256',p_provider_response_sha256,
      'webhook_secret_sha256',v_webhook_sha,
      'raw_secret_exposed',false,
      'stored_at',now()
    )
  )
  on conflict(lane_key) do update set
    system_ref=excluded.system_ref,
    provider_account_mode=excluded.provider_account_mode,
    stripe_api_secret_alias=excluded.stripe_api_secret_alias,
    provider_endpoint_id=excluded.provider_endpoint_id,
    provider_endpoint_url=excluded.provider_endpoint_url,
    provider_endpoint_status=excluded.provider_endpoint_status,
    webhook_secret_alias=excluded.webhook_secret_alias,
    old_provider_endpoint_id=excluded.old_provider_endpoint_id,
    old_provider_endpoint_url=excluded.old_provider_endpoint_url,
    enabled_events=excluded.enabled_events,
    state='provisioning',
    signature_verification_required=true,
    dedupe_required=true,
    evidence=integration_control.stripe_webhook_lane_bindings_v1.evidence||excluded.evidence,
    updated_at=now();

  return jsonb_build_object(
    'stored',true,
    'lane_key',p_lane_key,
    'endpoint_id',p_new_endpoint_id,
    'webhook_secret_alias',v_secret_alias,
    'webhook_secret_sha256',v_webhook_sha,
    'raw_secret_exposed',false
  );
end $$;
revoke all on function integration_control.stripe_webhook_store_replacement_v1(text,text,text,text,text,text,text,text,text,text,jsonb,text) from public, anon, authenticated;
grant execute on function integration_control.stripe_webhook_store_replacement_v1(text,text,text,text,text,text,text,text,text,text,jsonb,text) to service_role;

create or replace function integration_control.stripe_webhook_runtime_binding_v1(p_lane_key text)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,vault
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  b integration_control.stripe_webhook_lane_bindings_v1%rowtype;
  v_secret text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into b
  from integration_control.stripe_webhook_lane_bindings_v1
  where lane_key=p_lane_key and state in ('provisioning','canary_verified','production');
  if not found then raise exception 'stripe_webhook_lane_not_bound'; end if;
  select decrypted_secret into v_secret from vault.decrypted_secrets where name=b.webhook_secret_alias limit 1;
  if v_secret is null then raise exception 'stripe_webhook_signing_secret_missing'; end if;
  return jsonb_build_object(
    'lane_key',b.lane_key,
    'system_ref',b.system_ref,
    'provider_account_mode',b.provider_account_mode,
    'provider_endpoint_id',b.provider_endpoint_id,
    'webhook_secret',v_secret,
    'signature_verification_required',b.signature_verification_required,
    'state',b.state
  );
end $$;
revoke all on function integration_control.stripe_webhook_runtime_binding_v1(text) from public, anon, authenticated;
grant execute on function integration_control.stripe_webhook_runtime_binding_v1(text) to service_role;

create or replace function integration_control.stripe_ingest_verified_event_v1(
  p_lane_key text,
  p_event jsonb,
  p_payload_sha256 text,
  p_signature_timestamp bigint
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_event_id text:=p_event->>'id';
  v_type text:=p_event->>'type';
  v_live boolean:=coalesce((p_event->>'livemode')::boolean,false);
  v_created timestamptz;
  v_object jsonb:=coalesce(p_event->'data'->'object','{}'::jsonb);
  v_canary boolean:=coalesce(v_event_id like 'evt_ct_canary_%',false) or v_type='crownthrive.webhook.canary';
  v_receipt uuid;
  v_existing uuid;
  v_safe jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if p_lane_key not in ('thrivetickets','sermon-toolkit') then raise exception 'stripe_lane_not_allowed'; end if;
  if v_event_id is null or v_event_id !~ '^evt_' or v_type is null or length(v_type)>200 then raise exception 'invalid_stripe_event'; end if;
  if p_payload_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'invalid_payload_sha256'; end if;
  begin
    v_created:=to_timestamp((p_event->>'created')::double precision);
  exception when others then
    v_created:=null;
  end;

  v_safe:=jsonb_strip_nulls(jsonb_build_object(
    'event_id',v_event_id,
    'event_type',v_type,
    'livemode',v_live,
    'object_type',v_object->>'object',
    'object_id',v_object->>'id',
    'customer_ref',coalesce(v_object->>'customer',v_object->>'customer_id'),
    'subscription_ref',coalesce(v_object->>'subscription',v_object->>'subscription_id'),
    'payment_intent_ref',coalesce(v_object->>'payment_intent',v_object->>'payment_intent_id'),
    'checkout_session_ref',case when v_object->>'object'='checkout.session' then v_object->>'id' end,
    'amount_minor',coalesce(v_object->>'amount_total',v_object->>'amount_received',v_object->>'amount_paid',v_object->>'amount'),
    'currency',lower(v_object->>'currency'),
    'canary',v_canary
  ));

  select receipt_id into v_existing
  from integration_control.stripe_institutional_event_receipts_v1
  where lane_key=p_lane_key and stripe_event_id=v_event_id;
  if found then
    return jsonb_build_object('accepted',true,'idempotent_replay',true,'receipt_id',v_existing,'canary',v_canary);
  end if;

  insert into integration_control.stripe_institutional_event_receipts_v1(
    lane_key,stripe_event_id,event_type,event_created_at,livemode,object_type,
    object_id,customer_ref,subscription_ref,payment_intent_ref,checkout_session_ref,
    amount_minor,currency,canary,signature_timestamp,payload_sha256,safe_event,state
  ) values (
    p_lane_key,v_event_id,v_type,v_created,v_live,v_object->>'object',
    v_object->>'id',
    coalesce(v_object->>'customer',v_object->>'customer_id'),
    coalesce(v_object->>'subscription',v_object->>'subscription_id'),
    coalesce(v_object->>'payment_intent',v_object->>'payment_intent_id'),
    case when v_object->>'object'='checkout.session' then v_object->>'id' end,
    case
      when coalesce(v_object->>'amount_total',v_object->>'amount_received',v_object->>'amount_paid',v_object->>'amount') ~ '^-?[0-9]+$'
      then coalesce(v_object->>'amount_total',v_object->>'amount_received',v_object->>'amount_paid',v_object->>'amount')::bigint
    end,
    lower(v_object->>'currency'),
    v_canary,
    p_signature_timestamp,
    p_payload_sha256,
    v_safe,
    case when v_canary then 'canary_verified' else 'received' end
  ) returning receipt_id into v_receipt;

  insert into integration_control.stripe_event_handoffs_v1(
    receipt_id,lane_key,target_system,event_type,state,evidence
  ) values (
    v_receipt,
    p_lane_key,
    case when p_lane_key='thrivetickets' then 'ThriveTickets' else 'KJV/Sermon Toolkit' end,
    v_type,
    case when v_canary then 'canary_noop' else 'queued' end,
    jsonb_build_object(
      'payload_sha256',p_payload_sha256,
      'money_movement',false,
      'raw_event_stored',false,
      'signature_verified',true
    )
  );

  return jsonb_build_object(
    'accepted',true,
    'idempotent_replay',false,
    'receipt_id',v_receipt,
    'canary',v_canary,
    'raw_event_stored',false
  );
end $$;
revoke all on function integration_control.stripe_ingest_verified_event_v1(text,jsonb,text,bigint) from public, anon, authenticated;
grant execute on function integration_control.stripe_ingest_verified_event_v1(text,jsonb,text,bigint) to service_role;

create or replace function integration_control.stripe_webhook_finalize_replacement_v1(
  p_lane_key text,
  p_canary_http_status integer,
  p_old_endpoint_disabled boolean,
  p_provider_readback jsonb
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,penta_self,extensions
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_title text;
  v_problem record;
  v_evidence jsonb;
  v_hash text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if p_canary_http_status<>200 then raise exception 'stripe_webhook_canary_not_verified'; end if;
  if coalesce(p_provider_readback->>'status','') not in ('enabled','active') then raise exception 'stripe_provider_readback_not_enabled'; end if;

  update integration_control.stripe_webhook_lane_bindings_v1
     set state='production',
         provider_endpoint_status=coalesce(p_provider_readback->>'status',provider_endpoint_status),
         canary_http_status=p_canary_http_status,
         canary_verified_at=now(),
         provider_readback_at=now(),
         old_endpoint_disabled=p_old_endpoint_disabled,
         evidence=evidence||jsonb_build_object(
           'provider_readback',p_provider_readback,
           'finalized_at',now(),
           'raw_secret_exposed',false
         ),
         updated_at=now()
   where lane_key=p_lane_key;
  if not found then raise exception 'stripe_lane_binding_missing'; end if;

  v_title:=case
    when p_lane_key='thrivetickets' then 'ThriveTickets Stripe webhook returning HTTP 404'
    else 'KJV/Sermon Toolkit Stripe webhook returning HTTP 503'
  end;

  for v_problem in
    select * from penta_self.problem_ledger_v1
    where title=v_title and state not in ('resolved','closed','retired')
  loop
    v_evidence:=jsonb_build_object(
      'lane_key',p_lane_key,
      'canonical_endpoint',(select provider_endpoint_url from integration_control.stripe_webhook_lane_bindings_v1 where lane_key=p_lane_key),
      'provider_endpoint_id',(select provider_endpoint_id from integration_control.stripe_webhook_lane_bindings_v1 where lane_key=p_lane_key),
      'provider_status',p_provider_readback->>'status',
      'signed_canary_http_status',p_canary_http_status,
      'old_endpoint_disabled',p_old_endpoint_disabled,
      'institutional_receipt_count',(select count(*) from integration_control.stripe_institutional_event_receipts_v1 where lane_key=p_lane_key),
      'verified_at',now(),
      'money_movement',false
    );
    v_hash:=encode(extensions.digest(v_evidence::text,'sha256'),'hex');
    update penta_self.problem_ledger_v1
       set state='resolved',
           resolved_at=now(),
           blocked_reason=null,
           last_error=null,
           verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||v_evidence||jsonb_build_object('verification_sha256',v_hash),
           updated_at=now()
     where problem_id=v_problem.problem_id;
    perform penta_self.register_permanent_repair_v1(
      'ct.repair.stripe-webhook.'||p_lane_key||'.v1',
      'Stripe/'||p_lane_key,
      v_problem.fingerprint,
      jsonb_build_object(
        'state','production',
        'signed_webhook_required',true,
        'canonical_endpoint',(select provider_endpoint_url from integration_control.stripe_webhook_lane_bindings_v1 where lane_key=p_lane_key)
      ),
      v_evidence,
      now(),
      'runtime:stripe-institutional-webhook-v1',
      'newer_provider_or_signed-canary-failure-only'
    );
  end loop;

  return jsonb_build_object(
    'finalized',true,
    'lane_key',p_lane_key,
    'state','production',
    'canary_http_status',p_canary_http_status,
    'old_endpoint_disabled',p_old_endpoint_disabled,
    'raw_secret_exposed',false
  );
end $$;
revoke all on function integration_control.stripe_webhook_finalize_replacement_v1(text,integer,boolean,jsonb) from public, anon, authenticated;
grant execute on function integration_control.stripe_webhook_finalize_replacement_v1(text,integer,boolean,jsonb) to service_role;

create or replace function integration_control.stripe_webhook_health_v1()
returns jsonb
language sql
security definer
set search_path=pg_catalog,integration_control
as $$
select jsonb_build_object(
  'lanes',coalesce(jsonb_agg(jsonb_build_object(
    'lane_key',lane_key,
    'system_ref',system_ref,
    'mode',provider_account_mode,
    'endpoint_id',provider_endpoint_id,
    'endpoint_url',provider_endpoint_url,
    'provider_status',provider_endpoint_status,
    'state',state,
    'signature_verification_required',signature_verification_required,
    'canary_http_status',canary_http_status,
    'canary_verified_at',canary_verified_at,
    'provider_readback_at',provider_readback_at,
    'old_endpoint_disabled',old_endpoint_disabled,
    'receipt_count',(select count(*) from integration_control.stripe_institutional_event_receipts_v1 r where r.lane_key=b.lane_key),
    'non_canary_receipt_count',(select count(*) from integration_control.stripe_institutional_event_receipts_v1 r where r.lane_key=b.lane_key and not r.canary)
  ) order by lane_key),'[]'::jsonb),
  'production_lanes',count(*) filter(where state='production'),
  'total_lanes',count(*),
  'raw_credentials_exposed',false,
  'observed_at',now()
)
from integration_control.stripe_webhook_lane_bindings_v1 b
$$;
revoke all on function integration_control.stripe_webhook_health_v1() from public, anon, authenticated;
grant execute on function integration_control.stripe_webhook_health_v1() to service_role;

insert into vault.secrets(secret,name,description)
select
  encode(extensions.gen_random_bytes(32),'hex'),
  'crownthrive_stripe_webhook_repair_control_v1',
  'Internal control secret for the bounded Stripe webhook repair edge. Restricted server-side use only.'
where not exists(
  select 1 from vault.secrets where name='crownthrive_stripe_webhook_repair_control_v1'
);
