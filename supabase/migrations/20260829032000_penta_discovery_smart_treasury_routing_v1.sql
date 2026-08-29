-- PentaDiscovery + Smart Treasury metered routing v1
-- Additive/backward-compatible production migration.

create schema if not exists penta_discovery;

create table if not exists penta_discovery.family_registry_v1 (
  member_key text primary key,
  canonical_name text not null,
  family_role text not null,
  execution_role text not null,
  lifecycle_state text not null default 'active',
  packet_contract text not null default 'crownthrive.penta.event.v1',
  fabric_contract text not null default 'crownthrive.pentafabric.v1',
  authority_manufacture boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_discovery.observations_v1 (
  observation_id uuid primary key default gen_random_uuid(),
  observation_key text not null unique,
  source_ref text not null,
  source_kind text not null,
  observed_subject text not null,
  observation jsonb not null,
  content_fingerprint_sha256 text not null,
  confidence numeric(5,4) not null default 0.5000 check (confidence >= 0 and confidence <= 1),
  state text not null default 'observed' check (state in ('observed','resolved','classified','registered','packaged','routed','closed','quarantined')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists penta_discovery_observations_fingerprint_idx
  on penta_discovery.observations_v1(content_fingerprint_sha256);
create index if not exists penta_discovery_observations_state_idx
  on penta_discovery.observations_v1(state, created_at);

create table if not exists penta_discovery.entities_v1 (
  entity_id uuid primary key default gen_random_uuid(),
  entity_key text not null unique,
  canonical_name text not null,
  entity_kind text not null,
  institutional_did text,
  fingerprint_sha256 text not null,
  owner_penta_ref text,
  registry_state text not null default 'candidate' check (registry_state in ('candidate','registered','active','retired','quarantined')),
  evidence_refs jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists penta_discovery_entities_fingerprint_uidx
  on penta_discovery.entities_v1(fingerprint_sha256);

create table if not exists penta_discovery.handoffs_v1 (
  handoff_id uuid primary key default gen_random_uuid(),
  handoff_key text not null unique,
  observation_id uuid references penta_discovery.observations_v1(observation_id),
  entity_id uuid references penta_discovery.entities_v1(entity_id),
  packet_id text not null,
  sender_penta_ref text not null default 'PentaDiscovery',
  receiver_penta_ref text not null,
  objective text not null,
  route_class text not null,
  priority integer not null default 50 check (priority between 0 and 100),
  state text not null default 'prepared' check (state in ('prepared','priced','reserved','dispatched','acknowledged','reconciled','failed','quarantined')),
  chlom_intent_ref text,
  dail_evidence_ref text,
  packet jsonb not null,
  packet_sha256 text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists penta_discovery_handoffs_state_idx
  on penta_discovery.handoffs_v1(state, priority desc, created_at);

create table if not exists penta_runtime.penta_route_rate_policy_v1 (
  rate_key text primary key,
  route_class text not null,
  base_internal_units bigint not null check (base_internal_units >= 0),
  per_hop_internal_units bigint not null default 0 check (per_hop_internal_units >= 0),
  per_kib_internal_units bigint not null default 0 check (per_kib_internal_units >= 0),
  risk_multiplier numeric(10,4) not null default 1.0000 check (risk_multiplier >= 0),
  congestion_multiplier numeric(10,4) not null default 1.0000 check (congestion_multiplier >= 0),
  urgency_multiplier numeric(10,4) not null default 1.0000 check (urgency_multiplier >= 0),
  abuse_multiplier numeric(10,4) not null default 1.0000 check (abuse_multiplier >= 0),
  provider_cost_passthrough boolean not null default true,
  governance_state text not null default 'active' check (governance_state in ('proposed','active','held','retired')),
  evidence_refs jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  effective_at timestamptz not null default now(),
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_runtime.penta_route_quotes_v1 (
  quote_id uuid primary key default gen_random_uuid(),
  quote_key text not null unique,
  packet_id text not null,
  sender_penta_ref text not null,
  receiver_penta_ref text not null,
  rate_key text not null references penta_runtime.penta_route_rate_policy_v1(rate_key),
  route_class text not null,
  hop_count integer not null check (hop_count >= 0),
  max_hops integer not null check (max_hops >= hop_count),
  payload_bytes bigint not null default 0 check (payload_bytes >= 0),
  risk_score numeric(8,4) not null default 0 check (risk_score >= 0),
  congestion_score numeric(8,4) not null default 0 check (congestion_score >= 0),
  urgency_score numeric(8,4) not null default 0 check (urgency_score >= 0),
  abuse_score numeric(8,4) not null default 0 check (abuse_score >= 0),
  estimated_internal_units bigint not null check (estimated_internal_units >= 0),
  estimated_provider_cost_minor bigint not null default 0 check (estimated_provider_cost_minor >= 0),
  currency text not null default 'USD',
  state text not null default 'quoted' check (state in ('quoted','reserved','expired','consumed','released','held')),
  evidence_sha256 text not null,
  expires_at timestamptz not null default (now() + interval '15 minutes'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists penta_route_quotes_packet_idx on penta_runtime.penta_route_quotes_v1(packet_id);
create index if not exists penta_route_quotes_state_idx on penta_runtime.penta_route_quotes_v1(state, expires_at);

create table if not exists penta_runtime.penta_route_reservations_v1 (
  reservation_id uuid primary key default gen_random_uuid(),
  reservation_key text not null unique,
  quote_id uuid not null references penta_runtime.penta_route_quotes_v1(quote_id),
  packet_id text not null,
  treasury_penta_ref text not null default 'PentaTreasury',
  reserved_internal_units bigint not null check (reserved_internal_units >= 0),
  state text not null default 'reserved' check (state in ('reserved','partially_consumed','consumed','released','held','expired')),
  authority_evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  reconciled_at timestamptz
);

create unique index if not exists penta_route_reservation_packet_active_uidx
  on penta_runtime.penta_route_reservations_v1(packet_id)
  where state in ('reserved','partially_consumed');

create table if not exists penta_runtime.penta_route_usage_events_v1 (
  usage_event_id uuid primary key default gen_random_uuid(),
  event_key text not null unique,
  reservation_id uuid not null references penta_runtime.penta_route_reservations_v1(reservation_id),
  packet_id text not null,
  hop_no integer not null check (hop_no >= 0),
  route_edge_ref text,
  disposition text not null check (disposition in ('delivered','provider_consumed','infrastructure_retry','policy_retry','failed','acknowledged')),
  billable_internal boolean not null default true,
  actual_internal_units bigint not null default 0 check (actual_internal_units >= 0),
  actual_provider_cost_minor bigint not null default 0 check (actual_provider_cost_minor >= 0),
  currency text not null default 'USD',
  evidence_sha256 text not null,
  metadata jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now()
);

create index if not exists penta_route_usage_packet_idx on penta_runtime.penta_route_usage_events_v1(packet_id, observed_at);

create table if not exists penta_runtime.penta_route_pay_obligations_v1 (
  obligation_id uuid primary key default gen_random_uuid(),
  obligation_key text not null unique,
  packet_id text not null,
  reservation_id uuid not null references penta_runtime.penta_route_reservations_v1(reservation_id),
  beneficiary_ref text not null,
  obligation_basis text not null default 'penta_route_usage',
  internal_units bigint not null default 0 check (internal_units >= 0),
  amount_minor bigint not null default 0 check (amount_minor >= 0),
  currency text not null default 'USD',
  pay_entry_id uuid,
  economic_effect text not null default 'obligation_only' check (economic_effect in ('obligation_only','provider_cost_reimbursement','external_settlement_candidate')),
  state text not null default 'proposed' check (state in ('proposed','approved','settled','waived','held','rejected')),
  chlom_authority_ref text,
  governance_reconciliation jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_runtime.penta_route_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  receipt_key text not null unique,
  packet_id text not null,
  quote_id uuid references penta_runtime.penta_route_quotes_v1(quote_id),
  reservation_id uuid references penta_runtime.penta_route_reservations_v1(reservation_id),
  obligation_id uuid references penta_runtime.penta_route_pay_obligations_v1(obligation_id),
  sender_penta_ref text not null,
  receiver_penta_ref text not null,
  route_class text not null,
  hop_count integer not null default 0,
  estimated_internal_units bigint not null default 0,
  actual_internal_units bigint not null default 0,
  provider_cost_minor bigint not null default 0,
  pay_amount_minor bigint not null default 0,
  currency text not null default 'USD',
  settlement_state text not null default 'internal_reconciled',
  provider_money_movement boolean not null default false,
  chlom_authority_ref text,
  dail_evidence_ref text,
  evidence_sha256 text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create or replace function penta_runtime.quote_penta_route_v1(
  p_packet_id text,
  p_sender_penta_ref text,
  p_receiver_penta_ref text,
  p_route_class text default 'local_internal',
  p_hop_count integer default 1,
  p_max_hops integer default 8,
  p_payload_bytes bigint default 0,
  p_risk_score numeric default 0,
  p_congestion_score numeric default 0,
  p_urgency_score numeric default 0,
  p_abuse_score numeric default 0,
  p_estimated_provider_cost_minor bigint default 0,
  p_currency text default 'USD'
) returns jsonb
language plpgsql
security definer
set search_path = penta_runtime, pg_catalog, extensions
as $$
declare
  v_rate penta_runtime.penta_route_rate_policy_v1%rowtype;
  v_units numeric;
  v_quote_id uuid;
  v_quote_key text;
  v_evidence text;
  v_kib bigint;
begin
  if p_packet_id is null or length(trim(p_packet_id)) = 0 then raise exception 'packet_id required'; end if;
  if p_sender_penta_ref is null or p_receiver_penta_ref is null then raise exception 'sender and receiver required'; end if;
  if p_hop_count < 0 or p_max_hops < p_hop_count then raise exception 'invalid hop bounds'; end if;
  if p_payload_bytes < 0 or p_estimated_provider_cost_minor < 0 then raise exception 'negative cost inputs rejected'; end if;

  select * into v_rate
  from penta_runtime.penta_route_rate_policy_v1
  where route_class = p_route_class
    and governance_state = 'active'
    and effective_at <= now()
    and (expires_at is null or expires_at > now())
  order by effective_at desc
  limit 1;

  if not found then raise exception 'no active route pricing policy for %', p_route_class; end if;

  v_kib := case when p_payload_bytes = 0 then 0 else ceil(p_payload_bytes::numeric / 1024.0)::bigint end;
  v_units := (v_rate.base_internal_units
              + (v_rate.per_hop_internal_units * p_hop_count)
              + (v_rate.per_kib_internal_units * v_kib))::numeric;
  v_units := v_units
      * greatest(1::numeric, v_rate.risk_multiplier * (1 + greatest(0::numeric, p_risk_score)))
      * greatest(1::numeric, v_rate.congestion_multiplier * (1 + greatest(0::numeric, p_congestion_score)))
      * greatest(1::numeric, v_rate.urgency_multiplier * (1 + greatest(0::numeric, p_urgency_score)))
      * greatest(1::numeric, v_rate.abuse_multiplier * (1 + greatest(0::numeric, p_abuse_score)));

  v_quote_key := 'route-quote:' || encode(digest(
    concat_ws('|',p_packet_id,p_sender_penta_ref,p_receiver_penta_ref,v_rate.rate_key,p_hop_count,p_payload_bytes,clock_timestamp()::text), 'sha256'),'hex');
  v_evidence := encode(digest(concat_ws('|',v_quote_key,ceil(v_units)::bigint,p_estimated_provider_cost_minor,p_currency),'sha256'),'hex');

  insert into penta_runtime.penta_route_quotes_v1(
    quote_key, packet_id, sender_penta_ref, receiver_penta_ref, rate_key, route_class,
    hop_count, max_hops, payload_bytes, risk_score, congestion_score, urgency_score, abuse_score,
    estimated_internal_units, estimated_provider_cost_minor, currency, evidence_sha256
  ) values (
    v_quote_key,p_packet_id,p_sender_penta_ref,p_receiver_penta_ref,v_rate.rate_key,p_route_class,
    p_hop_count,p_max_hops,p_payload_bytes,greatest(0,p_risk_score),greatest(0,p_congestion_score),greatest(0,p_urgency_score),greatest(0,p_abuse_score),
    ceil(v_units)::bigint,p_estimated_provider_cost_minor,upper(p_currency),v_evidence
  ) returning quote_id into v_quote_id;

  return jsonb_build_object(
    'quoted',true,'quote_id',v_quote_id,'quote_key',v_quote_key,'packet_id',p_packet_id,
    'rate_key',v_rate.rate_key,'estimated_internal_units',ceil(v_units)::bigint,
    'estimated_provider_cost_minor',p_estimated_provider_cost_minor,'currency',upper(p_currency),
    'expires_in_seconds',900,'evidence_sha256',v_evidence
  );
end;
$$;

create or replace function penta_runtime.reserve_penta_route_v1(
  p_quote_id uuid,
  p_authority_evidence jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path = penta_runtime, penta_os20, pg_catalog, extensions
as $$
declare
  v_q penta_runtime.penta_route_quotes_v1%rowtype;
  v_treasury penta_os20.pentas%rowtype;
  v_budget penta_os20.execution_budgets%rowtype;
  v_available bigint;
  v_res_id uuid;
  v_res_key text;
  v_evidence text;
begin
  select * into v_q from penta_runtime.penta_route_quotes_v1 where quote_id=p_quote_id for update;
  if not found then raise exception 'quote not found'; end if;
  if v_q.state <> 'quoted' then raise exception 'quote is not reservable: %',v_q.state; end if;
  if v_q.expires_at <= now() then
    update penta_runtime.penta_route_quotes_v1 set state='expired',updated_at=now() where quote_id=p_quote_id;
    raise exception 'quote expired';
  end if;

  select * into v_treasury from penta_os20.pentas where canonical_name='PentaTreasury' and status='active' limit 1;
  if not found then raise exception 'active PentaTreasury missing'; end if;

  select * into v_budget from penta_os20.execution_budgets
  where penta_id=v_treasury.id and budget_date=(now() at time zone 'America/New_York')::date
  for update;
  if not found then raise exception 'PentaTreasury daily budget missing'; end if;

  v_available := v_budget.issued_units + v_budget.discretionary_units - v_budget.reserved_units - v_budget.spent_units;
  if v_available < v_q.estimated_internal_units then raise exception 'INSUFFICIENT_TREASURY_UNITS'; end if;

  update penta_os20.execution_budgets
    set reserved_units=reserved_units+v_q.estimated_internal_units
    where id=v_budget.id;

  insert into penta_os20.execution_transactions(penta_id,budget_id,transaction_type,units,task_key,reason,receipt_hash)
    values(v_treasury.id,v_budget.id,'reserve',v_q.estimated_internal_units,'route:'||v_q.packet_id,'PentaFabric route reservation',
      encode(digest(concat_ws('|',v_q.packet_id,p_quote_id::text,v_q.estimated_internal_units::text),'sha256'),'hex'));

  v_res_key := 'route-reservation:' || encode(digest(concat_ws('|',p_quote_id::text,v_q.packet_id,clock_timestamp()::text),'sha256'),'hex');
  v_evidence := encode(digest(concat_ws('|',v_res_key,v_q.evidence_sha256,p_authority_evidence::text),'sha256'),'hex');

  insert into penta_runtime.penta_route_reservations_v1(
    reservation_key,quote_id,packet_id,reserved_internal_units,authority_evidence,evidence_sha256,expires_at
  ) values(v_res_key,p_quote_id,v_q.packet_id,v_q.estimated_internal_units,coalesce(p_authority_evidence,'{}'::jsonb),v_evidence,v_q.expires_at)
  returning reservation_id into v_res_id;

  update penta_runtime.penta_route_quotes_v1 set state='reserved',updated_at=now() where quote_id=p_quote_id;

  return jsonb_build_object('reserved',true,'reservation_id',v_res_id,'packet_id',v_q.packet_id,
    'reserved_internal_units',v_q.estimated_internal_units,'evidence_sha256',v_evidence);
end;
$$;

create or replace function penta_runtime.record_penta_route_usage_v1(
  p_reservation_id uuid,
  p_hop_no integer,
  p_route_edge_ref text,
  p_disposition text,
  p_actual_internal_units bigint,
  p_actual_provider_cost_minor bigint default 0,
  p_currency text default 'USD',
  p_metadata jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path = penta_runtime, pg_catalog, extensions
as $$
declare
  v_r penta_runtime.penta_route_reservations_v1%rowtype;
  v_billable boolean;
  v_event_id uuid;
  v_event_key text;
  v_evidence text;
begin
  select * into v_r from penta_runtime.penta_route_reservations_v1 where reservation_id=p_reservation_id;
  if not found then raise exception 'reservation not found'; end if;
  if v_r.state not in ('reserved','partially_consumed') then raise exception 'reservation not active'; end if;
  if p_disposition not in ('delivered','provider_consumed','infrastructure_retry','policy_retry','failed','acknowledged') then raise exception 'invalid disposition'; end if;
  if p_actual_internal_units < 0 or p_actual_provider_cost_minor < 0 then raise exception 'negative usage rejected'; end if;

  v_billable := p_disposition <> 'infrastructure_retry';
  if not v_billable then p_actual_internal_units := 0; end if;

  v_event_key := 'route-usage:' || encode(digest(concat_ws('|',p_reservation_id::text,p_hop_no,p_route_edge_ref,p_disposition,clock_timestamp()::text),'sha256'),'hex');
  v_evidence := encode(digest(concat_ws('|',v_event_key,p_actual_internal_units,p_actual_provider_cost_minor,coalesce(p_metadata,'{}'::jsonb)::text),'sha256'),'hex');

  insert into penta_runtime.penta_route_usage_events_v1(
    event_key,reservation_id,packet_id,hop_no,route_edge_ref,disposition,billable_internal,
    actual_internal_units,actual_provider_cost_minor,currency,evidence_sha256,metadata
  ) values(v_event_key,p_reservation_id,v_r.packet_id,p_hop_no,p_route_edge_ref,p_disposition,v_billable,
    p_actual_internal_units,p_actual_provider_cost_minor,upper(p_currency),v_evidence,coalesce(p_metadata,'{}'::jsonb))
  returning usage_event_id into v_event_id;

  update penta_runtime.penta_route_reservations_v1 set state='partially_consumed' where reservation_id=p_reservation_id and state='reserved';
  return jsonb_build_object('recorded',true,'usage_event_id',v_event_id,'billable_internal',v_billable,
    'actual_internal_units',p_actual_internal_units,'actual_provider_cost_minor',p_actual_provider_cost_minor,'evidence_sha256',v_evidence);
end;
$$;

create or replace function penta_runtime.reconcile_penta_route_v1(
  p_reservation_id uuid,
  p_beneficiary_ref text default 'PentaFabric',
  p_pay_rate_minor_per_1000_units bigint default 1,
  p_chlom_authority_ref text default null,
  p_dail_evidence_ref text default null
) returns jsonb
language plpgsql
security definer
set search_path = penta_runtime, penta_os20, pg_catalog, extensions
as $$
declare
  v_r penta_runtime.penta_route_reservations_v1%rowtype;
  v_q penta_runtime.penta_route_quotes_v1%rowtype;
  v_treasury penta_os20.pentas%rowtype;
  v_budget penta_os20.execution_budgets%rowtype;
  v_actual bigint;
  v_provider bigint;
  v_pay_minor bigint;
  v_release bigint;
  v_obligation_id uuid;
  v_obligation_key text;
  v_receipt_id uuid;
  v_receipt_key text;
  v_evidence text;
begin
  if p_pay_rate_minor_per_1000_units < 0 then raise exception 'negative pay conversion rejected'; end if;
  select * into v_r from penta_runtime.penta_route_reservations_v1 where reservation_id=p_reservation_id for update;
  if not found then raise exception 'reservation not found'; end if;
  if v_r.state not in ('reserved','partially_consumed') then raise exception 'reservation not reconcilable: %',v_r.state; end if;
  select * into v_q from penta_runtime.penta_route_quotes_v1 where quote_id=v_r.quote_id;

  select coalesce(sum(case when billable_internal then actual_internal_units else 0 end),0),
         coalesce(sum(actual_provider_cost_minor),0)
    into v_actual,v_provider
  from penta_runtime.penta_route_usage_events_v1
  where reservation_id=p_reservation_id;

  if v_actual > v_r.reserved_internal_units then raise exception 'actual route units exceed reservation; reprice required'; end if;
  v_release := v_r.reserved_internal_units - v_actual;
  v_pay_minor := ceil((v_actual::numeric * p_pay_rate_minor_per_1000_units::numeric)/1000.0)::bigint;

  select * into v_treasury from penta_os20.pentas where canonical_name='PentaTreasury' and status='active' limit 1;
  select * into v_budget from penta_os20.execution_budgets
   where penta_id=v_treasury.id and budget_date=(now() at time zone 'America/New_York')::date for update;
  if not found then raise exception 'PentaTreasury daily budget missing'; end if;

  update penta_os20.execution_budgets
   set reserved_units=greatest(0,reserved_units-v_r.reserved_internal_units),
       spent_units=spent_units+v_actual,
       returned_units=returned_units+v_release
   where id=v_budget.id;

  if v_actual > 0 then
    insert into penta_os20.execution_transactions(penta_id,budget_id,transaction_type,units,task_key,reason,receipt_hash)
    values(v_treasury.id,v_budget.id,'spend',v_actual,'route:'||v_r.packet_id,'PentaFabric route settlement',
      encode(digest(concat_ws('|',v_r.packet_id,p_reservation_id::text,'spend',v_actual::text),'sha256'),'hex'));
  end if;
  if v_release > 0 then
    insert into penta_os20.execution_transactions(penta_id,budget_id,transaction_type,units,task_key,reason,receipt_hash)
    values(v_treasury.id,v_budget.id,'return',v_release,'route:'||v_r.packet_id,'unused PentaFabric reservation returned',
      encode(digest(concat_ws('|',v_r.packet_id,p_reservation_id::text,'return',v_release::text),'sha256'),'hex'));
  end if;

  v_obligation_key := 'route-pay:' || encode(digest(concat_ws('|',v_r.packet_id,p_reservation_id::text,v_actual::text,v_pay_minor::text,v_provider::text),'sha256'),'hex');
  v_evidence := encode(digest(concat_ws('|',v_obligation_key,coalesce(p_chlom_authority_ref,''),coalesce(p_dail_evidence_ref,'')),'sha256'),'hex');

  insert into penta_runtime.penta_route_pay_obligations_v1(
    obligation_key,packet_id,reservation_id,beneficiary_ref,internal_units,amount_minor,currency,
    economic_effect,state,chlom_authority_ref,evidence_sha256
  ) values(v_obligation_key,v_r.packet_id,p_reservation_id,p_beneficiary_ref,v_actual,v_pay_minor,upper(v_q.currency),
    case when (v_provider+v_pay_minor)>0 then 'external_settlement_candidate' else 'obligation_only' end,
    'proposed',p_chlom_authority_ref,v_evidence)
  returning obligation_id into v_obligation_id;

  v_receipt_key := 'route-receipt:' || encode(digest(concat_ws('|',v_r.packet_id,v_obligation_id::text,clock_timestamp()::text),'sha256'),'hex');
  insert into penta_runtime.penta_route_receipts_v1(
    receipt_key,packet_id,quote_id,reservation_id,obligation_id,sender_penta_ref,receiver_penta_ref,route_class,
    hop_count,estimated_internal_units,actual_internal_units,provider_cost_minor,pay_amount_minor,currency,
    settlement_state,provider_money_movement,chlom_authority_ref,dail_evidence_ref,evidence_sha256,
    metadata
  ) values(v_receipt_key,v_r.packet_id,v_q.quote_id,p_reservation_id,v_obligation_id,v_q.sender_penta_ref,v_q.receiver_penta_ref,v_q.route_class,
    v_q.hop_count,v_q.estimated_internal_units,v_actual,v_provider,v_pay_minor,upper(v_q.currency),
    'internal_reconciled',false,p_chlom_authority_ref,p_dail_evidence_ref,v_evidence,
    jsonb_build_object('unused_reserved_units_returned',v_release,'infrastructure_retries_nonbillable',true))
  returning receipt_id into v_receipt_id;

  update penta_runtime.penta_route_reservations_v1 set state='consumed',reconciled_at=now() where reservation_id=p_reservation_id;
  update penta_runtime.penta_route_quotes_v1 set state='consumed',updated_at=now() where quote_id=v_q.quote_id;

  return jsonb_build_object('reconciled',true,'packet_id',v_r.packet_id,'actual_internal_units',v_actual,
    'unused_internal_units_returned',v_release,'provider_cost_minor',v_provider,'penta_pay_amount_minor',v_pay_minor,
    'currency',upper(v_q.currency),'obligation_id',v_obligation_id,'receipt_id',v_receipt_id,
    'provider_money_movement',false,'chlom_authority_required_for_external_settlement',true,'evidence_sha256',v_evidence);
end;
$$;

create or replace function penta_discovery.intake_v1(
  p_source_ref text,
  p_source_kind text,
  p_observed_subject text,
  p_observation jsonb,
  p_confidence numeric default 0.5,
  p_receiver_penta_ref text default 'PentaCensus',
  p_objective text default 'classify and register discovery',
  p_route_class text default 'local_internal'
) returns jsonb
language plpgsql
security definer
set search_path = penta_discovery, penta_runtime, pg_catalog, extensions
as $$
declare
  v_fp text;
  v_obs_id uuid;
  v_obs_key text;
  v_packet_id text;
  v_packet jsonb;
  v_packet_sha text;
  v_handoff_id uuid;
  v_handoff_key text;
  v_quote jsonb;
begin
  if p_source_ref is null or p_observed_subject is null or p_observation is null then raise exception 'source, subject and observation required'; end if;
  v_fp := encode(digest(convert_to(jsonb_strip_nulls(p_observation)::text,'UTF8'),'sha256'),'hex');
  v_obs_key := 'discovery:' || encode(digest(concat_ws('|',p_source_ref,p_source_kind,p_observed_subject,v_fp),'sha256'),'hex');

  insert into penta_discovery.observations_v1(observation_key,source_ref,source_kind,observed_subject,observation,content_fingerprint_sha256,confidence)
  values(v_obs_key,p_source_ref,p_source_kind,p_observed_subject,p_observation,v_fp,least(1,greatest(0,p_confidence)))
  on conflict(observation_key) do update set updated_at=now(), confidence=greatest(penta_discovery.observations_v1.confidence,excluded.confidence)
  returning observation_id into v_obs_id;

  v_packet_id := 'penta_' || replace(gen_random_uuid()::text,'-','');
  v_packet := jsonb_build_object(
    'id',v_packet_id,
    'specversion','1.0',
    'type','penta.discovery.observed',
    'source','urn:crownthrive:penta:discovery',
    'subject',p_observed_subject,
    'time',now(),
    'datacontenttype','application/json',
    'data',jsonb_build_object('protocol','PentaDiscovery','status','PREPARED','payload',p_observation),
    'mesh',jsonb_build_object(
      'family','PentaDiscoveryFamily','contract','crownthrive.penta.event.v1','architecture_version','1.3.0',
      'fabric',jsonb_build_object('name','PentaFabric','schema','crownthrive.pentafabric.v1','route','penta-discovery','corridor','discovery','lane','hot'),
      'chlom',jsonb_build_object('governed',true,'binding','crownthrive.chlom.pentafabric.v1','rights_scope','discovery-routing-only')
    ),
    'trace',jsonb_build_object('trace_id','ptrace_'||replace(gen_random_uuid()::text,'-',''),'sequence',0),
    'economics',jsonb_build_object('route_class',p_route_class,'settlement_state','unquoted','provider_money_movement',false),
    'integrity',jsonb_build_object('algorithm','SHA-256')
  );
  v_packet_sha := encode(digest(convert_to(v_packet::text,'UTF8'),'sha256'),'hex');
  v_packet := jsonb_set(v_packet,'{integrity,digest}',to_jsonb(v_packet_sha),true);

  v_handoff_key := 'discovery-handoff:' || encode(digest(concat_ws('|',v_obs_id::text,v_packet_id,p_receiver_penta_ref),'sha256'),'hex');
  insert into penta_discovery.handoffs_v1(handoff_key,observation_id,packet_id,receiver_penta_ref,objective,route_class,packet,packet_sha256)
    values(v_handoff_key,v_obs_id,v_packet_id,p_receiver_penta_ref,p_objective,p_route_class,v_packet,v_packet_sha)
  returning handoff_id into v_handoff_id;

  v_quote := penta_runtime.quote_penta_route_v1(v_packet_id,'PentaDiscovery',p_receiver_penta_ref,p_route_class,1,8,length(v_packet::text),0,0,0,0,0,'USD');
  update penta_discovery.handoffs_v1 set state='priced',updated_at=now() where handoff_id=v_handoff_id;
  update penta_discovery.observations_v1 set state='packaged',updated_at=now() where observation_id=v_obs_id;

  return jsonb_build_object('accepted',true,'observation_id',v_obs_id,'handoff_id',v_handoff_id,'packet_id',v_packet_id,
    'packet_sha256',v_packet_sha,'quote',v_quote,'packet',v_packet);
end;
$$;

-- Initial governed route classes. Values are internal machine-economic units, not dollars.
insert into penta_runtime.penta_route_rate_policy_v1(rate_key,route_class,base_internal_units,per_hop_internal_units,per_kib_internal_units,metadata)
values
 ('pentafabric:route:local_internal:v1','local_internal',1,1,1,jsonb_build_object('policy','baseline','provider_money_movement',false)),
 ('pentafabric:route:cross_plane:v1','cross_plane',2,2,1,jsonb_build_object('policy','baseline','provider_money_movement',false)),
 ('pentafabric:route:provider_read:v1','provider_read',3,2,1,jsonb_build_object('policy','baseline','provider_cost_separate',true)),
 ('pentafabric:route:provider_write:v1','provider_write',5,3,2,jsonb_build_object('policy','baseline','provider_cost_separate',true,'requires_authority',true)),
 ('pentafabric:route:human_escalation:v1','human_escalation',8,3,1,jsonb_build_object('policy','baseline','requires_governance_reconciliation',true)),
 ('pentafabric:route:legacy_unpriced:v1','legacy_unpriced',0,0,0,jsonb_build_object('compatibility',true,'fake_obligation_forbidden',true))
on conflict(rate_key) do update set updated_at=now(), governance_state='active';

insert into penta_discovery.family_registry_v1(member_key,canonical_name,family_role,execution_role,metadata)
values
 ('penta.discovery','PentaDiscovery','coordinator','discover-identify-classify-register-package-price-route',jsonb_build_object('head',true)),
 ('penta.crawler','PentaCrawler','acquisition','bounded-source-acquisition','{}'::jsonb),
 ('penta.search','PentaSearch','acquisition','broad-source-discovery','{}'::jsonb),
 ('penta.query','PentaQuery','acquisition','structured-registry-api-query','{}'::jsonb),
 ('penta.fetch','PentaFetch','acquisition','known-resource-fetch','{}'::jsonb),
 ('penta.get','PentaGet','acquisition','exact-object-get','{}'::jsonb),
 ('penta.parse','PentaParse','normalization','parse-normalize-observations','{}'::jsonb),
 ('penta.resolve','PentaResolve','resolution','entity-dedup-alias-fingerprint-resolution','{}'::jsonb),
 ('penta.signal','PentaSignal','sensing','weak-signal-anomaly-early-warning','{}'::jsonb),
 ('penta.context','PentaContext','context','scoped-context-pack-assembly','{}'::jsonb),
 ('penta.census','PentaCensus','registration','institutional-census-registration','{}'::jsonb),
 ('penta.harvestor','PentaHarvestor','evidence','evidence-preservation','{}'::jsonb)
on conflict(member_key) do update set canonical_name=excluded.canonical_name,family_role=excluded.family_role,execution_role=excluded.execution_role,lifecycle_state='active',updated_at=now();

insert into public.penta_system_registry(system_key,canonical_name,category,purpose,authority_boundary,risk_ceiling,maturity,version,public_exposure,docs_ref,runtime_ref,metadata,last_verified_at)
values(
 'penta.discovery','PentaDiscovery','discovery',
 'Systemwide discovery, identification, fingerprinting, resolution, classification, registration, governed Penta packet assembly, route pricing and handoff coordination.',
 'Discovers/packages/routes evidence; does not manufacture authority, expose credentials, self-approve, deploy arbitrary writes, or move money.',
 'D2','production','1.0.0',false,'docs/penta/PENTA_DISCOVERY_SMART_TREASURY_ROUTING_V1.md','penta_discovery.intake_v1',
 jsonb_build_object('family_registry','penta_discovery.family_registry_v1','packet_contract','crownthrive.penta.event.v1','fabric_contract','crownthrive.pentafabric.v1','chlom_bridge',true,'penta_pay_real_currency_obligation',true,'smart_treasury_machine_banking',true,'provider_money_movement_inherited',false),now()
)
on conflict(system_key) do update set canonical_name=excluded.canonical_name,category=excluded.category,purpose=excluded.purpose,authority_boundary=excluded.authority_boundary,risk_ceiling=excluded.risk_ceiling,maturity='production',version=excluded.version,docs_ref=excluded.docs_ref,runtime_ref=excluded.runtime_ref,metadata=excluded.metadata,last_verified_at=now(),updated_at=now();

insert into penta_os20.pentas(canonical_name,class,department,status,daily_budget_units,discretionary_budget_units,max_single_task_units,authority_scope,capabilities)
select 'PentaDiscovery','research','discovery','active',6000,1000,3000,
       jsonb_build_object('authority_manufacture',false,'provider_money_movement',false,'provider_write',false,'classification_and_routing',true),
       jsonb_build_array('discover','fingerprint','resolve','classify','register','package','price_route','handoff')
where not exists(select 1 from penta_os20.pentas where canonical_name='PentaDiscovery');

-- RLS: server/control-plane only. No blanket public policies are created.
alter table penta_discovery.family_registry_v1 enable row level security;
alter table penta_discovery.observations_v1 enable row level security;
alter table penta_discovery.entities_v1 enable row level security;
alter table penta_discovery.handoffs_v1 enable row level security;
alter table penta_runtime.penta_route_rate_policy_v1 enable row level security;
alter table penta_runtime.penta_route_quotes_v1 enable row level security;
alter table penta_runtime.penta_route_reservations_v1 enable row level security;
alter table penta_runtime.penta_route_usage_events_v1 enable row level security;
alter table penta_runtime.penta_route_pay_obligations_v1 enable row level security;
alter table penta_runtime.penta_route_receipts_v1 enable row level security;

comment on table penta_runtime.penta_route_pay_obligations_v1 is 'PentaPay routing obligations denominated in real currency; obligation creation never grants money-movement authority.';
comment on table penta_runtime.penta_route_reservations_v1 is 'Smart Treasury machine-banking reservation ledger for governed Penta packet routing.';
comment on function penta_runtime.reconcile_penta_route_v1(uuid,text,bigint,text,text) is 'Reconciles internal route units and creates a PentaPay real-currency obligation. Does not dispatch external money.';
