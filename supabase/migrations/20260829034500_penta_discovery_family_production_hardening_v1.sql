-- PentaDiscovery family production hardening v1
-- Corrects/extends the additive routing migration with canonical Penta wire compatibility,
-- governed PentaPay service-value policies, anti-abuse, work-cost causality,
-- dynamic governance reconciliation, automated maintenance, and certification.

create table if not exists penta_runtime.penta_pay_route_compensation_policy_v1 (
  policy_key text primary key,
  route_class text not null,
  compensation_minor_per_1000_metered_units bigint not null check (compensation_minor_per_1000_metered_units >= 0),
  minimum_obligation_minor bigint not null default 0 check (minimum_obligation_minor >= 0),
  maximum_obligation_minor bigint not null default 100000 check (maximum_obligation_minor >= minimum_obligation_minor),
  currency text not null default 'USD' check (length(currency)=3),
  auto_adjustment_cap_pct numeric(8,4) not null default 0.2000 check (auto_adjustment_cap_pct between 0 and 1),
  governance_state text not null default 'active' check (governance_state in ('proposed','active','held','retired')),
  authority_ref text not null,
  evidence_refs jsonb not null default '[]'::jsonb,
  metadata jsonb not null default jsonb_build_object('internal_units_are_currency',false,'basis','service_value_per_1000_metered_units'),
  effective_at timestamptz not null default now(),
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_runtime.penta_route_abuse_state_v1 (
  subject_penta_ref text not null,
  route_class text not null,
  abuse_score numeric(8,4) not null default 0 check (abuse_score between 0 and 10),
  price_multiplier numeric(8,4) not null default 1 check (price_multiplier between 1 and 10),
  duplicate_events bigint not null default 0 check (duplicate_events >= 0),
  failed_events bigint not null default 0 check (failed_events >= 0),
  infrastructure_retry_events bigint not null default 0 check (infrastructure_retry_events >= 0),
  policy_retry_events bigint not null default 0 check (policy_retry_events >= 0),
  action_state text not null default 'normal' check (action_state in ('normal','watch','throttled','blocked','quarantined')),
  evidence_refs jsonb not null default '[]'::jsonb,
  last_evaluated_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key(subject_penta_ref,route_class)
);

create table if not exists penta_runtime.penta_route_governance_reconciliations_v1 (
  reconciliation_id uuid primary key default gen_random_uuid(),
  reconciliation_key text not null unique,
  policy_kind text not null check (policy_kind in ('route_rate','penta_pay_compensation','anti_abuse')),
  policy_key text not null,
  source_penta_ref text not null,
  requested_change_pct numeric(10,4),
  confidence numeric(5,4) not null default 0 check (confidence between 0 and 1),
  evidence_refs jsonb not null default '[]'::jsonb,
  executive_ref text,
  legislative_ref text,
  judicial_ref text,
  reconciliation_mode text not null check (reconciliation_mode in ('automatic_bounded','three_branch','held')),
  disposition text not null check (disposition in ('applied','queued','held','rejected')),
  before_state jsonb not null default '{}'::jsonb,
  after_state jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  created_at timestamptz not null default now()
);

create table if not exists penta_runtime.penta_route_work_cost_links_v1 (
  link_id uuid primary key default gen_random_uuid(),
  link_key text not null unique,
  packet_id text not null,
  reservation_id uuid references penta_runtime.penta_route_reservations_v1(reservation_id),
  source_kind text not null check (source_kind in ('patch','upgrade','build','release','issue','provider_job','task','other')),
  source_ref text not null,
  task_id uuid,
  release_version text,
  repository_ref text,
  provider_usage_refs jsonb not null default '[]'::jsonb,
  routing_internal_units bigint not null default 0 check (routing_internal_units >= 0),
  provider_cost_minor bigint not null default 0 check (provider_cost_minor >= 0),
  penta_pay_obligation_minor bigint not null default 0 check (penta_pay_obligation_minor >= 0),
  currency text not null default 'USD',
  cost_basis text not null default 'actual_reconciled',
  evidence_sha256 text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_runtime.penta_discovery_certifications_v1 (
  certification_id uuid primary key default gen_random_uuid(),
  certification_key text not null unique,
  release_version text not null,
  verdict text not null check (verdict in ('PASS','FAIL')),
  checks jsonb not null,
  canary_receipt_id uuid,
  independent_verifier_ref text not null,
  evidence_sha256 text not null,
  certified_at timestamptz not null default now(),
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

alter table penta_runtime.penta_route_quotes_v1
  add column if not exists compensation_policy_key text,
  add column if not exists dynamic_multiplier numeric(10,4) not null default 1 check (dynamic_multiplier between 1 and 100);

alter table penta_runtime.penta_route_pay_obligations_v1
  add column if not exists compensation_policy_key text,
  add column if not exists service_value_basis text not null default 'governed_route_compensation';

create unique index if not exists penta_route_quotes_one_live_per_packet_uidx
  on penta_runtime.penta_route_quotes_v1(packet_id)
  where state in ('quoted','reserved');

create index if not exists penta_route_work_cost_source_idx
  on penta_runtime.penta_route_work_cost_links_v1(source_kind,source_ref);

create or replace function penta_runtime.validate_penta_economic_envelope_v1(p_event jsonb)
returns jsonb
language plpgsql
stable
set search_path=penta_runtime,pg_catalog
as $$
declare
  v_validated jsonb;
  v_econ jsonb;
  v_state text;
  v_hops int;
  v_max_hops int;
begin
  v_validated := penta_runtime.validate_penta_envelope_v1(p_event);
  if not (p_event ? 'economics') then
    return v_validated;
  end if;
  v_econ := p_event->'economics';
  if jsonb_typeof(v_econ) <> 'object' then raise exception 'economics must be object'; end if;
  if coalesce(v_econ->>'route_class','')='' then raise exception 'economics.route_class required'; end if;
  if coalesce(v_econ->>'sender_penta_id','')='' then raise exception 'economics.sender_penta_id required'; end if;
  if coalesce(v_econ->>'receiver_penta_id','')='' then raise exception 'economics.receiver_penta_id required'; end if;
  if coalesce((v_econ->>'provider_money_movement')::boolean,false) then raise exception 'provider money movement cannot be inherited by Penta packet'; end if;
  if (v_econ ? 'currency') and length(v_econ->>'currency')<>3 then raise exception 'economics.currency invalid'; end if;
  v_hops := coalesce((v_econ->>'hop_count')::int,0);
  v_max_hops := coalesce((v_econ->>'max_hops')::int,8);
  if v_hops < 0 or v_max_hops < v_hops then raise exception 'economics hop bounds invalid'; end if;
  if coalesce((v_econ->>'estimated_route_units')::bigint,0) < 0 or coalesce((v_econ->>'actual_route_units')::bigint,0) < 0 then raise exception 'negative route units rejected'; end if;
  if coalesce((v_econ->>'provider_cost_minor')::bigint,0) < 0 then raise exception 'negative provider cost rejected'; end if;
  v_state := coalesce(v_econ->>'settlement_state','legacy_unpriced');
  if v_state not in ('legacy_unpriced','unquoted','quoted','reserved','in_transit','internal_reconciled','pay_obligation_created','externally_settled','held') then
    raise exception 'invalid settlement state %',v_state;
  end if;
  if v_state in ('reserved','in_transit','internal_reconciled','pay_obligation_created','externally_settled') and coalesce(v_econ->>'treasury_reservation_id','')='' then
    raise exception 'treasury reservation required for settlement state %',v_state;
  end if;
  return p_event;
end;
$$;

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
  v_comp penta_runtime.penta_pay_route_compensation_policy_v1%rowtype;
  v_abuse penta_runtime.penta_route_abuse_state_v1%rowtype;
  v_units numeric;
  v_dynamic numeric;
  v_quote_id uuid;
  v_quote_key text;
  v_evidence text;
  v_kib bigint;
begin
  if p_packet_id is null or length(trim(p_packet_id))=0 then raise exception 'packet_id required'; end if;
  if p_sender_penta_ref is null or p_receiver_penta_ref is null then raise exception 'sender and receiver required'; end if;
  if p_hop_count < 0 or p_max_hops < p_hop_count or p_max_hops > 64 then raise exception 'invalid hop bounds'; end if;
  if p_payload_bytes < 0 or p_estimated_provider_cost_minor < 0 then raise exception 'negative cost inputs rejected'; end if;
  if exists(select 1 from penta_runtime.penta_route_quotes_v1 where packet_id=p_packet_id and state in ('quoted','reserved')) then raise exception 'active quote already exists for packet'; end if;

  select * into v_rate from penta_runtime.penta_route_rate_policy_v1
   where route_class=p_route_class and governance_state='active' and effective_at<=now() and (expires_at is null or expires_at>now())
   order by effective_at desc limit 1;
  if not found then raise exception 'no active route pricing policy for %',p_route_class; end if;

  select * into v_comp from penta_runtime.penta_pay_route_compensation_policy_v1
   where route_class=p_route_class and governance_state='active' and effective_at<=now() and (expires_at is null or expires_at>now())
   order by effective_at desc limit 1;
  if not found then raise exception 'no active PentaPay route compensation policy for %',p_route_class; end if;

  select * into v_abuse from penta_runtime.penta_route_abuse_state_v1
   where subject_penta_ref=p_sender_penta_ref and route_class=p_route_class;
  if found and v_abuse.action_state in ('blocked','quarantined') then raise exception 'route blocked by anti-abuse policy'; end if;

  v_kib := case when p_payload_bytes=0 then 0 else ceil(p_payload_bytes::numeric/1024.0)::bigint end;
  v_dynamic := greatest(1::numeric,
    (1 + least(4::numeric,greatest(0::numeric,p_risk_score))) *
    (1 + least(4::numeric,greatest(0::numeric,p_congestion_score))) *
    (1 + least(4::numeric,greatest(0::numeric,p_urgency_score))) *
    (1 + least(4::numeric,greatest(0::numeric,p_abuse_score))) *
    coalesce(v_abuse.price_multiplier,1));
  v_dynamic := least(v_dynamic,100::numeric);

  v_units := (v_rate.base_internal_units + v_rate.per_hop_internal_units*p_hop_count + v_rate.per_kib_internal_units*v_kib)::numeric;
  v_units := v_units * v_rate.risk_multiplier * v_rate.congestion_multiplier * v_rate.urgency_multiplier * v_rate.abuse_multiplier * v_dynamic;

  v_quote_key := 'route-quote:'||encode(digest(concat_ws('|',p_packet_id,p_sender_penta_ref,p_receiver_penta_ref,v_rate.rate_key,v_comp.policy_key,p_hop_count,p_payload_bytes,clock_timestamp()::text),'sha256'),'hex');
  v_evidence := encode(digest(concat_ws('|',v_quote_key,ceil(v_units)::bigint,p_estimated_provider_cost_minor,upper(p_currency),v_dynamic),'sha256'),'hex');

  insert into penta_runtime.penta_route_quotes_v1(
    quote_key,packet_id,sender_penta_ref,receiver_penta_ref,rate_key,compensation_policy_key,route_class,
    hop_count,max_hops,payload_bytes,risk_score,congestion_score,urgency_score,abuse_score,dynamic_multiplier,
    estimated_internal_units,estimated_provider_cost_minor,currency,evidence_sha256
  ) values(
    v_quote_key,p_packet_id,p_sender_penta_ref,p_receiver_penta_ref,v_rate.rate_key,v_comp.policy_key,p_route_class,
    p_hop_count,p_max_hops,p_payload_bytes,least(4,greatest(0,p_risk_score)),least(4,greatest(0,p_congestion_score)),least(4,greatest(0,p_urgency_score)),least(4,greatest(0,p_abuse_score)),v_dynamic,
    ceil(v_units)::bigint,p_estimated_provider_cost_minor,upper(p_currency),v_evidence
  ) returning quote_id into v_quote_id;

  return jsonb_build_object('quoted',true,'quote_id',v_quote_id,'quote_key',v_quote_key,'packet_id',p_packet_id,
    'rate_key',v_rate.rate_key,'compensation_policy_key',v_comp.policy_key,'dynamic_multiplier',v_dynamic,
    'estimated_internal_units',ceil(v_units)::bigint,'estimated_provider_cost_minor',p_estimated_provider_cost_minor,
    'currency',upper(p_currency),'expires_in_seconds',900,'provider_money_movement',false,'evidence_sha256',v_evidence);
end;
$$;

create or replace function penta_runtime.reconcile_penta_route_v1(
  p_reservation_id uuid,
  p_beneficiary_ref text default 'PentaFabric',
  p_pay_rate_minor_per_1000_units bigint default null,
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
  v_comp penta_runtime.penta_pay_route_compensation_policy_v1%rowtype;
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
  if p_pay_rate_minor_per_1000_units is not null then raise exception 'caller-supplied PentaPay conversion prohibited; governed policy required'; end if;
  select * into v_r from penta_runtime.penta_route_reservations_v1 where reservation_id=p_reservation_id for update;
  if not found then raise exception 'reservation not found'; end if;
  if v_r.state not in ('reserved','partially_consumed') then raise exception 'reservation not reconcilable: %',v_r.state; end if;
  select * into v_q from penta_runtime.penta_route_quotes_v1 where quote_id=v_r.quote_id;
  select * into v_comp from penta_runtime.penta_pay_route_compensation_policy_v1 where policy_key=v_q.compensation_policy_key and governance_state='active';
  if not found then raise exception 'active governed PentaPay compensation policy missing'; end if;

  select coalesce(sum(case when billable_internal then actual_internal_units else 0 end),0),coalesce(sum(actual_provider_cost_minor),0)
    into v_actual,v_provider from penta_runtime.penta_route_usage_events_v1 where reservation_id=p_reservation_id;
  if v_actual > v_r.reserved_internal_units then raise exception 'actual route units exceed reservation; reprice required'; end if;
  v_release := v_r.reserved_internal_units-v_actual;
  v_pay_minor := case when v_actual=0 then 0 else greatest(v_comp.minimum_obligation_minor,ceil(v_actual::numeric*v_comp.compensation_minor_per_1000_metered_units/1000.0)::bigint) end;
  v_pay_minor := least(v_pay_minor,v_comp.maximum_obligation_minor);

  select * into v_treasury from penta_os20.pentas where canonical_name='PentaTreasury' and status='active' limit 1;
  if not found then raise exception 'active PentaTreasury missing'; end if;
  select * into v_budget from penta_os20.execution_budgets where penta_id=v_treasury.id and budget_date=(now() at time zone 'America/New_York')::date for update;
  if not found then raise exception 'PentaTreasury daily budget missing'; end if;

  update penta_os20.execution_budgets set reserved_units=greatest(0,reserved_units-v_r.reserved_internal_units),spent_units=spent_units+v_actual,returned_units=returned_units+v_release where id=v_budget.id;
  if v_actual>0 then
    insert into penta_os20.execution_transactions(penta_id,budget_id,transaction_type,units,task_key,reason,receipt_hash)
    values(v_treasury.id,v_budget.id,'spend',v_actual,'route:'||v_r.packet_id,'PentaFabric route settlement',encode(digest(concat_ws('|',v_r.packet_id,p_reservation_id::text,'spend',v_actual::text),'sha256'),'hex'));
  end if;
  if v_release>0 then
    insert into penta_os20.execution_transactions(penta_id,budget_id,transaction_type,units,task_key,reason,receipt_hash)
    values(v_treasury.id,v_budget.id,'return',v_release,'route:'||v_r.packet_id,'unused PentaFabric reservation returned',encode(digest(concat_ws('|',v_r.packet_id,p_reservation_id::text,'return',v_release::text),'sha256'),'hex'));
  end if;

  v_obligation_key := 'route-pay:'||encode(digest(concat_ws('|',v_r.packet_id,p_reservation_id::text,v_actual::text,v_pay_minor::text,v_provider::text,v_comp.policy_key),'sha256'),'hex');
  v_evidence := encode(digest(concat_ws('|',v_obligation_key,coalesce(p_chlom_authority_ref,''),coalesce(p_dail_evidence_ref,'')),'sha256'),'hex');
  insert into penta_runtime.penta_route_pay_obligations_v1(
    obligation_key,packet_id,reservation_id,beneficiary_ref,internal_units,amount_minor,currency,compensation_policy_key,
    economic_effect,state,chlom_authority_ref,evidence_sha256
  ) values(v_obligation_key,v_r.packet_id,p_reservation_id,p_beneficiary_ref,v_actual,v_pay_minor,v_comp.currency,v_comp.policy_key,
    case when (v_provider+v_pay_minor)>0 then 'external_settlement_candidate' else 'obligation_only' end,'proposed',p_chlom_authority_ref,v_evidence)
  returning obligation_id into v_obligation_id;

  v_receipt_key := 'route-receipt:'||encode(digest(concat_ws('|',v_r.packet_id,v_obligation_id::text,clock_timestamp()::text),'sha256'),'hex');
  insert into penta_runtime.penta_route_receipts_v1(
    receipt_key,packet_id,quote_id,reservation_id,obligation_id,sender_penta_ref,receiver_penta_ref,route_class,hop_count,
    estimated_internal_units,actual_internal_units,provider_cost_minor,pay_amount_minor,currency,settlement_state,provider_money_movement,
    chlom_authority_ref,dail_evidence_ref,evidence_sha256,metadata
  ) values(v_receipt_key,v_r.packet_id,v_q.quote_id,p_reservation_id,v_obligation_id,v_q.sender_penta_ref,v_q.receiver_penta_ref,v_q.route_class,v_q.hop_count,
    v_q.estimated_internal_units,v_actual,v_provider,v_pay_minor,v_comp.currency,'internal_reconciled',false,p_chlom_authority_ref,p_dail_evidence_ref,v_evidence,
    jsonb_build_object('unused_reserved_units_returned',v_release,'infrastructure_retries_nonbillable',true,'internal_units_are_currency',false,'compensation_policy_key',v_comp.policy_key))
  returning receipt_id into v_receipt_id;

  update penta_runtime.penta_route_reservations_v1 set state='consumed',reconciled_at=now() where reservation_id=p_reservation_id;
  update penta_runtime.penta_route_quotes_v1 set state='consumed',updated_at=now() where quote_id=v_q.quote_id;

  return jsonb_build_object('reconciled',true,'packet_id',v_r.packet_id,'actual_internal_units',v_actual,'unused_internal_units_returned',v_release,
    'provider_cost_minor',v_provider,'penta_pay_amount_minor',v_pay_minor,'currency',v_comp.currency,'compensation_policy_key',v_comp.policy_key,
    'obligation_id',v_obligation_id,'receipt_id',v_receipt_id,'provider_money_movement',false,
    'chlom_authority_required_for_external_settlement',true,'internal_units_are_currency',false,'evidence_sha256',v_evidence);
end;
$$;

create or replace function penta_runtime.materialize_route_penta_pay_v1(
  p_obligation_id uuid,
  p_beneficiary_subject_ref text,
  p_contract_instrument_id uuid,
  p_approved_by_assignment_id uuid
) returns jsonb
language plpgsql
security definer
set search_path=penta_runtime,public,pg_catalog,extensions
as $$
declare
  v_o penta_runtime.penta_route_pay_obligations_v1%rowtype;
  v_pay_id uuid;
  v_pay_key text;
begin
  select * into v_o from penta_runtime.penta_route_pay_obligations_v1 where obligation_id=p_obligation_id for update;
  if not found then raise exception 'route obligation not found'; end if;
  if v_o.pay_entry_id is not null then return jsonb_build_object('materialized',true,'existing',true,'pay_entry_id',v_o.pay_entry_id); end if;
  if not exists(select 1 from public.penta_workforce_subjects where subject_ref=p_beneficiary_subject_ref and lifecycle_state='active') then raise exception 'active beneficiary subject required'; end if;
  if not exists(select 1 from public.penta_governance_instruments where instrument_id=p_contract_instrument_id) then raise exception 'governance contract instrument required'; end if;
  if not exists(select 1 from public.penta_workforce_assignments where assignment_id=p_approved_by_assignment_id) then raise exception 'valid independent approving assignment required'; end if;
  v_pay_key := 'route-pay-entry:'||encode(digest(concat_ws('|',v_o.obligation_id::text,p_beneficiary_subject_ref,v_o.amount_minor::text,v_o.currency),'sha256'),'hex');
  insert into public.penta_pay_entries(pay_key,beneficiary_subject_ref,contract_instrument_id,approved_by_assignment_id,currency,gross_minor,entry_type,state,provider_money_movement,metadata)
  values(v_pay_key,p_beneficiary_subject_ref,p_contract_instrument_id,p_approved_by_assignment_id,v_o.currency,v_o.amount_minor,'routing_service','approved',false,
    jsonb_build_object('route_obligation_id',v_o.obligation_id,'packet_id',v_o.packet_id,'internal_units_are_currency',false,'provider_dispatch_inherited',false))
  returning pay_entry_id into v_pay_id;
  update penta_runtime.penta_route_pay_obligations_v1 set pay_entry_id=v_pay_id,state='approved',updated_at=now() where obligation_id=v_o.obligation_id;
  return jsonb_build_object('materialized',true,'pay_entry_id',v_pay_id,'provider_money_movement',false,'external_settlement_requires_exact_authority',true);
end;
$$;

create or replace function penta_runtime.reconcile_route_rate_signal_v1(
  p_rate_key text,
  p_source_penta_ref text,
  p_requested_change_pct numeric,
  p_confidence numeric,
  p_evidence_refs jsonb,
  p_executive_ref text default null,
  p_legislative_ref text default null,
  p_judicial_ref text default null
) returns jsonb
language plpgsql
security definer
set search_path=penta_runtime,pg_catalog,extensions
as $$
declare
  v_rate penta_runtime.penta_route_rate_policy_v1%rowtype;
  v_mode text;
  v_disposition text;
  v_key text;
  v_evidence text;
  v_before jsonb;
  v_after jsonb;
  v_factor numeric;
begin
  if p_source_penta_ref not in ('PentaDiscovery','PentaSignal','PentaCensus','PentaCosts','PentaLoad','PentaBalancer') then raise exception 'unauthorized policy evidence source'; end if;
  if p_confidence<0 or p_confidence>1 then raise exception 'invalid confidence'; end if;
  if p_evidence_refs is null or jsonb_typeof(p_evidence_refs)<>'array' or jsonb_array_length(p_evidence_refs)=0 then raise exception 'evidence required'; end if;
  select * into v_rate from penta_runtime.penta_route_rate_policy_v1 where rate_key=p_rate_key for update;
  if not found then raise exception 'rate policy not found'; end if;
  v_before:=to_jsonb(v_rate);
  if abs(p_requested_change_pct)<=0.20 and p_confidence>=0.80 then
    v_mode:='automatic_bounded'; v_disposition:='applied';
  elsif p_executive_ref is not null and p_legislative_ref is not null and p_judicial_ref is not null and p_confidence>=0.70 then
    v_mode:='three_branch'; v_disposition:='applied';
  else
    v_mode:='held'; v_disposition:='queued';
  end if;
  if v_disposition='applied' then
    v_factor:=greatest(0.25,least(4.0,1+p_requested_change_pct));
    update penta_runtime.penta_route_rate_policy_v1
      set base_internal_units=ceil(base_internal_units*v_factor),per_hop_internal_units=ceil(per_hop_internal_units*v_factor),
          per_kib_internal_units=ceil(per_kib_internal_units*v_factor),updated_at=now(),
          evidence_refs=coalesce(evidence_refs,'[]'::jsonb)||p_evidence_refs
      where rate_key=p_rate_key returning to_jsonb(penta_runtime.penta_route_rate_policy_v1.*) into v_after;
  else v_after:=v_before; end if;
  v_key:='route-policy-reconcile:'||encode(digest(concat_ws('|',p_rate_key,p_source_penta_ref,p_requested_change_pct::text,clock_timestamp()::text),'sha256'),'hex');
  v_evidence:=encode(digest(concat_ws('|',v_key,p_evidence_refs::text,v_mode,v_disposition),'sha256'),'hex');
  insert into penta_runtime.penta_route_governance_reconciliations_v1(reconciliation_key,policy_kind,policy_key,source_penta_ref,requested_change_pct,confidence,evidence_refs,executive_ref,legislative_ref,judicial_ref,reconciliation_mode,disposition,before_state,after_state,evidence_sha256)
  values(v_key,'route_rate',p_rate_key,p_source_penta_ref,p_requested_change_pct,p_confidence,p_evidence_refs,p_executive_ref,p_legislative_ref,p_judicial_ref,v_mode,v_disposition,v_before,v_after,v_evidence);
  return jsonb_build_object('disposition',v_disposition,'mode',v_mode,'policy_key',p_rate_key,'evidence_sha256',v_evidence,'after',v_after);
end;
$$;

create or replace function penta_runtime.reconcile_route_pay_signal_v1(
  p_policy_key text,
  p_source_penta_ref text,
  p_requested_change_pct numeric,
  p_confidence numeric,
  p_evidence_refs jsonb,
  p_executive_ref text default null,
  p_legislative_ref text default null,
  p_judicial_ref text default null
) returns jsonb
language plpgsql
security definer
set search_path=penta_runtime,pg_catalog,extensions
as $$
declare
  v_pol penta_runtime.penta_pay_route_compensation_policy_v1%rowtype;
  v_mode text; v_disposition text; v_key text; v_evidence text; v_before jsonb; v_after jsonb; v_factor numeric;
begin
  if p_source_penta_ref not in ('PentaDiscovery','PentaSignal','PentaCensus','PentaCosts','PentaLoad','PentaBalancer') then raise exception 'unauthorized pay evidence source'; end if;
  if p_evidence_refs is null or jsonb_typeof(p_evidence_refs)<>'array' or jsonb_array_length(p_evidence_refs)=0 then raise exception 'evidence required'; end if;
  select * into v_pol from penta_runtime.penta_pay_route_compensation_policy_v1 where policy_key=p_policy_key for update;
  if not found then raise exception 'pay compensation policy not found'; end if;
  v_before:=to_jsonb(v_pol);
  if abs(p_requested_change_pct)<=v_pol.auto_adjustment_cap_pct and p_confidence>=0.85 then v_mode:='automatic_bounded';v_disposition:='applied';
  elsif p_executive_ref is not null and p_legislative_ref is not null and p_judicial_ref is not null and p_confidence>=0.70 then v_mode:='three_branch';v_disposition:='applied';
  else v_mode:='held';v_disposition:='queued'; end if;
  if v_disposition='applied' then
    v_factor:=greatest(0.25,least(4.0,1+p_requested_change_pct));
    update penta_runtime.penta_pay_route_compensation_policy_v1
      set compensation_minor_per_1000_metered_units=ceil(compensation_minor_per_1000_metered_units*v_factor),
          evidence_refs=coalesce(evidence_refs,'[]'::jsonb)||p_evidence_refs,updated_at=now()
      where policy_key=p_policy_key returning to_jsonb(penta_runtime.penta_pay_route_compensation_policy_v1.*) into v_after;
  else v_after:=v_before; end if;
  v_key:='route-pay-reconcile:'||encode(digest(concat_ws('|',p_policy_key,p_source_penta_ref,p_requested_change_pct::text,clock_timestamp()::text),'sha256'),'hex');
  v_evidence:=encode(digest(concat_ws('|',v_key,p_evidence_refs::text,v_mode,v_disposition),'sha256'),'hex');
  insert into penta_runtime.penta_route_governance_reconciliations_v1(reconciliation_key,policy_kind,policy_key,source_penta_ref,requested_change_pct,confidence,evidence_refs,executive_ref,legislative_ref,judicial_ref,reconciliation_mode,disposition,before_state,after_state,evidence_sha256)
  values(v_key,'penta_pay_compensation',p_policy_key,p_source_penta_ref,p_requested_change_pct,p_confidence,p_evidence_refs,p_executive_ref,p_legislative_ref,p_judicial_ref,v_mode,v_disposition,v_before,v_after,v_evidence);
  return jsonb_build_object('disposition',v_disposition,'mode',v_mode,'policy_key',p_policy_key,'evidence_sha256',v_evidence,'after',v_after);
end;
$$;

create or replace function penta_runtime.link_penta_route_work_cost_v1(
  p_packet_id text,p_reservation_id uuid,p_source_kind text,p_source_ref text,p_task_id uuid default null,p_release_version text default null,p_repository_ref text default null,p_provider_usage_refs jsonb default '[]'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path=penta_runtime,pg_catalog,extensions
as $$
declare v_units bigint;v_provider bigint;v_pay bigint;v_currency text;v_key text;v_hash text;v_id uuid;
begin
  select r.actual_internal_units,r.provider_cost_minor,r.pay_amount_minor,r.currency into v_units,v_provider,v_pay,v_currency
  from penta_runtime.penta_route_receipts_v1 r where r.packet_id=p_packet_id and (p_reservation_id is null or r.reservation_id=p_reservation_id) order by r.created_at desc limit 1;
  if not found then raise exception 'reconciled route receipt required'; end if;
  v_key:='route-work-cost:'||encode(digest(concat_ws('|',p_packet_id,p_source_kind,p_source_ref,coalesce(p_release_version,'')),'sha256'),'hex');
  v_hash:=encode(digest(concat_ws('|',v_key,v_units,v_provider,v_pay,v_currency),'sha256'),'hex');
  insert into penta_runtime.penta_route_work_cost_links_v1(link_key,packet_id,reservation_id,source_kind,source_ref,task_id,release_version,repository_ref,provider_usage_refs,routing_internal_units,provider_cost_minor,penta_pay_obligation_minor,currency,evidence_sha256)
  values(v_key,p_packet_id,p_reservation_id,p_source_kind,p_source_ref,p_task_id,p_release_version,p_repository_ref,coalesce(p_provider_usage_refs,'[]'::jsonb),v_units,v_provider,v_pay,v_currency,v_hash)
  on conflict(link_key) do update set routing_internal_units=excluded.routing_internal_units,provider_cost_minor=excluded.provider_cost_minor,penta_pay_obligation_minor=excluded.penta_pay_obligation_minor,updated_at=now()
  returning link_id into v_id;
  return jsonb_build_object('linked',true,'link_id',v_id,'routing_internal_units',v_units,'provider_cost_minor',v_provider,'penta_pay_obligation_minor',v_pay,'currency',v_currency,'evidence_sha256',v_hash);
end;
$$;

create or replace function penta_runtime.maintain_penta_route_economy_v1()
returns jsonb
language plpgsql
security definer
set search_path=penta_runtime,pg_catalog
as $$
declare v_r record;v_reconciled int:=0;v_expired_quotes int:=0;v_abuse_rows int:=0;
begin
  for v_r in select reservation_id from penta_runtime.penta_route_reservations_v1 where state in ('reserved','partially_consumed') and expires_at<=now() order by expires_at for update skip locked loop
    perform penta_runtime.reconcile_penta_route_v1(v_r.reservation_id,'PentaFabric',null,'chlom-intent-penta-route-expiry-reconcile-v1','dail:penta-route-expiry-reconcile');
    v_reconciled:=v_reconciled+1;
  end loop;
  update penta_runtime.penta_route_quotes_v1 set state='expired',updated_at=now() where state='quoted' and expires_at<=now(); get diagnostics v_expired_quotes=row_count;
  insert into penta_runtime.penta_route_abuse_state_v1(subject_penta_ref,route_class,failed_events,infrastructure_retry_events,policy_retry_events,abuse_score,price_multiplier,action_state,last_evaluated_at,updated_at)
  select q.sender_penta_ref,q.route_class,
    count(*) filter(where u.disposition='failed'),count(*) filter(where u.disposition='infrastructure_retry'),count(*) filter(where u.disposition='policy_retry'),
    least(10::numeric,(count(*) filter(where u.disposition='failed')*0.5+count(*) filter(where u.disposition='policy_retry')*0.25)::numeric),
    least(10::numeric,greatest(1::numeric,1+(count(*) filter(where u.disposition='failed')*0.10)::numeric)),
    case when count(*) filter(where u.disposition='failed')>=20 then 'blocked' when count(*) filter(where u.disposition='failed')>=10 then 'throttled' when count(*) filter(where u.disposition='failed')>=5 then 'watch' else 'normal' end,
    now(),now()
  from penta_runtime.penta_route_usage_events_v1 u join penta_runtime.penta_route_quotes_v1 q on q.packet_id=u.packet_id
  where u.observed_at>=now()-interval '24 hours' group by q.sender_penta_ref,q.route_class
  on conflict(subject_penta_ref,route_class) do update set failed_events=excluded.failed_events,infrastructure_retry_events=excluded.infrastructure_retry_events,policy_retry_events=excluded.policy_retry_events,abuse_score=excluded.abuse_score,price_multiplier=excluded.price_multiplier,action_state=excluded.action_state,last_evaluated_at=now(),updated_at=now();
  get diagnostics v_abuse_rows=row_count;
  return jsonb_build_object('reconciled_expired_reservations',v_reconciled,'expired_unreserved_quotes',v_expired_quotes,'anti_abuse_rows_refreshed',v_abuse_rows,'ran_at',now());
end;
$$;

-- Canonical wire-compatible PentaDiscovery intake. The economic layer is additive.
create or replace function penta_discovery.intake_v1(
  p_source_ref text,p_source_kind text,p_observed_subject text,p_observation jsonb,p_confidence numeric default 0.5,
  p_receiver_penta_ref text default 'PentaCensus',p_objective text default 'classify and register discovery',p_route_class text default 'local_internal'
) returns jsonb
language plpgsql
security definer
set search_path=penta_discovery,penta_runtime,pg_catalog,extensions
as $$
declare
  v_fp text;v_obs_id uuid;v_obs_key text;v_packet_id text;v_trace_id text;v_packet jsonb;v_packet_sha text;v_handoff_id uuid;v_handoff_key text;v_quote jsonb;
begin
  if p_source_ref is null or p_observed_subject is null or p_observation is null then raise exception 'source, subject and observation required'; end if;
  v_fp:=encode(digest(convert_to(jsonb_strip_nulls(p_observation)::text,'UTF8'),'sha256'),'hex');
  v_obs_key:='discovery:'||encode(digest(concat_ws('|',p_source_ref,p_source_kind,p_observed_subject,v_fp),'sha256'),'hex');
  insert into penta_discovery.observations_v1(observation_key,source_ref,source_kind,observed_subject,observation,content_fingerprint_sha256,confidence)
  values(v_obs_key,p_source_ref,p_source_kind,p_observed_subject,p_observation,v_fp,least(1,greatest(0,p_confidence)))
  on conflict(observation_key) do update set updated_at=now(),confidence=greatest(penta_discovery.observations_v1.confidence,excluded.confidence)
  returning observation_id into v_obs_id;

  v_packet_id:='penta_'||replace(gen_random_uuid()::text,'-','');v_trace_id:='ptrace_'||replace(gen_random_uuid()::text,'-','');
  v_packet:=jsonb_build_object(
    'id',v_packet_id,'specversion','1.0','type','penta.discovery.observed','source','urn:crownthrive:penta:discovery','subject',p_observed_subject,
    'time',to_char(now() at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),'datacontenttype','application/json',
    'data',jsonb_build_object('protocol','PentaDiscovery','status','ADMITTED','payload',jsonb_build_object('observation',p_observation,'objective',p_objective,'confidence',least(1,greatest(0,p_confidence)))) ,
    'mesh',jsonb_build_object('family','PentaFamily','contract','crownthrive.penta.event.v1','architecture_version','1.3.0','layer','discovery',
      'fabric',jsonb_build_object('name','PentaFabric','schema','crownthrive.pentafabric.v1','version','1.0.0','protocol','PentaDiscovery','route','penta-discovery','corridor','discovery','lane','hot','ttl_seconds',900,'expires_at',to_char((now()+interval '15 minutes') at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')),
      'chlom',jsonb_build_object('governed',true,'binding','crownthrive.chlom.pentafabric.v1','intent_id','chlom-intent-penta-discovery-routing-v1','rights_scope','discovery-routing-only','policy_refs',jsonb_build_array('ct.penta.discovery.family.v1','ct.penta.route.v3'))),
    'trace',jsonb_build_object('trace_id',v_trace_id,'sequence',0,'causation_id',null),
    'economics',jsonb_build_object('route_class',p_route_class,'sender_penta_id','PentaDiscovery','receiver_penta_id',p_receiver_penta_ref,'estimated_route_units',0,'actual_route_units',0,'provider_cost_minor',0,'currency','USD','hop_count',1,'max_hops',8,'settlement_state','unquoted','provider_money_movement',false,'usage_event_ids',jsonb_build_array(),'receipt_refs',jsonb_build_array()),
    'integrity',jsonb_build_object('algorithm','SHA-256','key_id','penta-discovery-db-v1','digest',repeat('0',64),'signature',null));
  v_packet_sha:=encode(digest(convert_to((v_packet-'integrity')::text,'UTF8'),'sha256'),'hex');
  v_packet:=jsonb_set(v_packet,'{integrity,digest}',to_jsonb(v_packet_sha),true);
  perform penta_runtime.validate_penta_economic_envelope_v1(v_packet);

  v_handoff_key:='discovery-handoff:'||encode(digest(concat_ws('|',v_obs_id::text,v_packet_id,p_receiver_penta_ref),'sha256'),'hex');
  insert into penta_discovery.handoffs_v1(handoff_key,observation_id,packet_id,receiver_penta_ref,objective,route_class,chlom_intent_ref,packet,packet_sha256)
  values(v_handoff_key,v_obs_id,v_packet_id,p_receiver_penta_ref,p_objective,p_route_class,'chlom-intent-penta-discovery-routing-v1',v_packet,v_packet_sha)
  returning handoff_id into v_handoff_id;
  v_quote:=penta_runtime.quote_penta_route_v1(v_packet_id,'PentaDiscovery',p_receiver_penta_ref,p_route_class,1,8,length(v_packet::text),0,0,0,0,0,'USD');
  update penta_discovery.handoffs_v1 set state='priced',updated_at=now() where handoff_id=v_handoff_id;
  update penta_discovery.observations_v1 set state='packaged',updated_at=now() where observation_id=v_obs_id;
  return jsonb_build_object('accepted',true,'observation_id',v_obs_id,'handoff_id',v_handoff_id,'packet_id',v_packet_id,'packet_sha256',v_packet_sha,'quote',v_quote,'packet',v_packet);
end;
$$;

-- Governed baseline PentaPay service-value schedules. These are pricing/compensation policies, not currency exchange rates.
insert into penta_runtime.penta_pay_route_compensation_policy_v1(policy_key,route_class,compensation_minor_per_1000_metered_units,minimum_obligation_minor,maximum_obligation_minor,currency,authority_ref,evidence_refs,metadata)
values
 ('pentapay:route:local_internal:v1','local_internal',10,0,1000,'USD','founder-directive:penta-discovery-routing:2026-08-28',jsonb_build_array('ct.penta.discovery.family.v1'),jsonb_build_object('internal_units_are_currency',false,'basis','routing_service_value')),
 ('pentapay:route:cross_plane:v1','cross_plane',20,0,2500,'USD','founder-directive:penta-discovery-routing:2026-08-28',jsonb_build_array('ct.penta.discovery.family.v1'),jsonb_build_object('internal_units_are_currency',false,'basis','routing_service_value')),
 ('pentapay:route:provider_read:v1','provider_read',30,0,5000,'USD','founder-directive:penta-discovery-routing:2026-08-28',jsonb_build_array('ct.penta.discovery.family.v1'),jsonb_build_object('internal_units_are_currency',false,'provider_cost_separate',true)),
 ('pentapay:route:provider_write:v1','provider_write',50,0,10000,'USD','founder-directive:penta-discovery-routing:2026-08-28',jsonb_build_array('ct.penta.discovery.family.v1'),jsonb_build_object('internal_units_are_currency',false,'provider_cost_separate',true,'authority_required',true)),
 ('pentapay:route:human_escalation:v1','human_escalation',100,0,25000,'USD','founder-directive:penta-discovery-routing:2026-08-28',jsonb_build_array('ct.penta.discovery.family.v1'),jsonb_build_object('internal_units_are_currency',false,'governance_reconciliation',true)),
 ('pentapay:route:legacy_unpriced:v1','legacy_unpriced',0,0,0,'USD','compatibility:penta-event-v1',jsonb_build_array('crownthrive.penta.event.v1'),jsonb_build_object('internal_units_are_currency',false,'fake_obligation_forbidden',true))
on conflict(policy_key) do update set governance_state='active',updated_at=now();

-- Register the complete family in the runtime component registry with explicit packet inheritance.
with family(component_key,canonical_name,role,axis) as (values
 ('penta.discovery','PentaDiscovery','systemwide discovery coordinator, fingerprinting, classification, registration, pricing handoff and governed packet dispatch','sensing'),
 ('penta.crawler','PentaCrawler','bounded acquisition from approved public and registered system surfaces','sensing'),
 ('penta.search','PentaSearch','broad source and location discovery across approved registries and surfaces','sensing'),
 ('penta.query','PentaQuery','structured interrogation of allowlisted registries, APIs, databases and graphs','sensing'),
 ('penta.fetch','PentaFetch','bounded retrieval of known resources from approved endpoints','interoperation'),
 ('penta.get','PentaGet','exact object retrieval by known identifiers','interoperation'),
 ('penta.parse','PentaParse','deterministic normalization and extraction of discovery observations','execution'),
 ('penta.resolve','PentaResolve','entity resolution, deduplication, aliases, DID and fingerprint correlation','identity'),
 ('penta.signal','PentaSignal','weak-signal, anomaly and early-warning sensing for discovery and economics','sensing'),
 ('penta.context','PentaContext','scoped provenance-aware context-pack assembly','memory'),
 ('penta.census','PentaCensus','institutional registration, census accounting and discovery propagation','assurance'),
 ('penta.harvestor','PentaHarvestor','bounded evidence harvest and immutable evidence preservation','assurance')
)
insert into penta_runtime.component_registry_v1(component_key,canonical_name,role,primary_axis,stable_contract_id,implementation_state,backing_refs,metadata,enabled)
select component_key,canonical_name,role,axis,'ct.penta.discovery.family.v1','active',jsonb_build_object('family_registry','penta_discovery.family_registry_v1','runtime','penta_discovery.intake_v1'),
 jsonb_build_object('family_head','PentaDiscovery','output_validator','penta_runtime.validate_penta_economic_envelope_v1(jsonb)','output_packet_name','Penta','chlom_binding_required','crownthrive.chlom.pentafabric.v1','delivery_fabric_required','ct.fabric.penta.v1','output_contract_required','crownthrive.penta.event.v1','packet_contract_enforced',true,'pentafabric_schema_required','crownthrive.pentafabric.v1','provider_money_movement_inherited',false,'authority_manufacture',false),true
from family
on conflict(component_key) do update set canonical_name=excluded.canonical_name,role=excluded.role,primary_axis=excluded.primary_axis,stable_contract_id=excluded.stable_contract_id,implementation_state='active',backing_refs=penta_runtime.component_registry_v1.backing_refs||excluded.backing_refs,metadata=penta_runtime.component_registry_v1.metadata||excluded.metadata,enabled=true,updated_at=now();

-- Register/update family systems without replacing existing operational metadata.
with family(system_key,canonical_name,category,purpose,runtime_ref) as (values
 ('penta.discovery','PentaDiscovery','discovery','Systemwide discovery, identity/fingerprint resolution, classification, registration, governed packet assembly, route pricing and handoff coordination.','penta_discovery.intake_v1'),
 ('penta.crawler','PentaCrawler','discovery','Bounded acquisition from approved public-web and registered system surfaces.','ct.penta.crawler.systemwide.v2'),
 ('penta.search','PentaSearch','discovery','Broad source and location discovery across approved surfaces.','ct.penta.discovery.search.v1'),
 ('penta.query','PentaQuery','discovery','Structured interrogation of allowlisted registries, APIs, databases and graphs.','ct.penta.discovery.query.v1'),
 ('penta.fetch','PentaFetch','discovery','Bounded retrieval of known resources from approved endpoints.','ct.penta.discovery.fetch.v1'),
 ('penta.get','PentaGet','discovery','Exact object retrieval by known identifiers.','ct.penta.discovery.get.v1'),
 ('penta.parse','PentaParse','discovery','Normalize and extract observations into governed machine facts.','ct.penta.discovery.parse.v1'),
 ('penta.resolve','PentaResolve','discovery','Resolve duplicates, aliases, DIDs, fingerprints and institutional entities.','ct.penta.discovery.resolve.v1'),
 ('penta.signal','PentaSignal','discovery','Weak-signal, anomaly and early-warning sensing feeding discovery and economic policy.','ct.penta.signal.v1'),
 ('penta.context','PentaContext','discovery','Assemble scoped provenance-aware context packs for discovery and routing.','penta-context'),
 ('penta.census','PentaCensus','discovery','Maintain institutional census, register discoveries and propagate governed topology.','ct.penta.census.v1.1'),
 ('penta.harvestor','PentaHarvestor','discovery','Preserve bounded discovery and incident evidence with immutable hashes.','ct.penta.harvestor.v1')
)
insert into public.penta_system_registry(system_key,canonical_name,category,purpose,authority_boundary,risk_ceiling,maturity,version,public_exposure,docs_ref,runtime_ref,metadata,last_verified_at)
select system_key,canonical_name,category,purpose,'No authority manufacture, no inherited provider money movement, bounded source and route scope.','D2','production','1.0.0',false,'docs/penta/PENTA_DISCOVERY_SMART_TREASURY_ROUTING_V1.md',runtime_ref,
 jsonb_build_object('family','PentaDiscovery','family_contract','ct.penta.discovery.family.v1','packet_contract','crownthrive.penta.event.v1','economic_validator','penta_runtime.validate_penta_economic_envelope_v1(jsonb)','smart_treasury_metered',true,'penta_pay_real_currency_obligation',true,'chlom_bridge',true),now()
from family
on conflict(system_key) do update set canonical_name=excluded.canonical_name,category=excluded.category,purpose=excluded.purpose,authority_boundary=excluded.authority_boundary,risk_ceiling=excluded.risk_ceiling,maturity='production',version=excluded.version,docs_ref=excluded.docs_ref,runtime_ref=coalesce(public.penta_system_registry.runtime_ref,excluded.runtime_ref),metadata=public.penta_system_registry.metadata||excluded.metadata,last_verified_at=now(),updated_at=now();

-- Economic actors: each family member receives a bounded machine-execution budget.
with family(canonical_name,class,department,daily_budget,discretionary,max_task) as (values
 ('PentaDiscovery','research','discovery',6000::bigint,1000::bigint,3000::bigint),
 ('PentaCrawler','research','discovery_acquisition',4000,500,2000),
 ('PentaSearch','research','discovery_search',3500,500,1750),
 ('PentaQuery','research','discovery_query',3500,500,1750),
 ('PentaFetch','cyberspace','discovery_fetch',3000,400,1500),
 ('PentaGet','cyberspace','discovery_get',2500,300,1250),
 ('PentaParse','cyberspace','discovery_parse',3000,400,1500),
 ('PentaResolve','research','discovery_resolution',3500,500,1750),
 ('PentaSignal','research','discovery_signal',4000,500,2000),
 ('PentaContext','cyberspace','discovery_context',4000,500,2000),
 ('PentaCensus','governance','discovery_census',4500,500,2250),
 ('PentaHarvestor','cyberspace','discovery_evidence',3000,400,1500)
)
insert into penta_os20.pentas(canonical_name,class,department,status,daily_budget_units,discretionary_budget_units,max_single_task_units,authority_scope,capabilities)
select canonical_name,class,department,'active',daily_budget,discretionary,max_task,
 jsonb_build_object('family','PentaDiscovery','authority_manufacture',false,'provider_money_movement',false,'provider_write',false,'max_decision','D2'),
 jsonb_build_object('packet_contract','crownthrive.penta.event.v1','family_contract','ct.penta.discovery.family.v1','metered_routing',true)
from family
where not exists(select 1 from penta_os20.pentas p where p.canonical_name=family.canonical_name);

select penta_os20.midnight_issue((now() at time zone 'America/New_York')::date);

-- Security: server-side control plane only.
alter table penta_runtime.penta_pay_route_compensation_policy_v1 enable row level security;
alter table penta_runtime.penta_route_abuse_state_v1 enable row level security;
alter table penta_runtime.penta_route_governance_reconciliations_v1 enable row level security;
alter table penta_runtime.penta_route_work_cost_links_v1 enable row level security;
alter table penta_runtime.penta_discovery_certifications_v1 enable row level security;

revoke all on all tables in schema penta_discovery from anon,authenticated;
revoke all on penta_runtime.penta_route_rate_policy_v1,penta_runtime.penta_route_quotes_v1,penta_runtime.penta_route_reservations_v1,penta_runtime.penta_route_usage_events_v1,penta_runtime.penta_route_pay_obligations_v1,penta_runtime.penta_route_receipts_v1,penta_runtime.penta_pay_route_compensation_policy_v1,penta_runtime.penta_route_abuse_state_v1,penta_runtime.penta_route_governance_reconciliations_v1,penta_runtime.penta_route_work_cost_links_v1,penta_runtime.penta_discovery_certifications_v1 from anon,authenticated;
revoke execute on function penta_runtime.quote_penta_route_v1(text,text,text,text,integer,integer,bigint,numeric,numeric,numeric,numeric,bigint,text) from public,anon,authenticated;
revoke execute on function penta_runtime.reserve_penta_route_v1(uuid,jsonb) from public,anon,authenticated;
revoke execute on function penta_runtime.record_penta_route_usage_v1(uuid,integer,text,text,bigint,bigint,text,jsonb) from public,anon,authenticated;
revoke execute on function penta_runtime.reconcile_penta_route_v1(uuid,text,bigint,text,text) from public,anon,authenticated;
revoke execute on function penta_runtime.materialize_route_penta_pay_v1(uuid,text,uuid,uuid) from public,anon,authenticated;
revoke execute on function penta_runtime.reconcile_route_rate_signal_v1(text,text,numeric,numeric,jsonb,text,text,text) from public,anon,authenticated;
revoke execute on function penta_runtime.reconcile_route_pay_signal_v1(text,text,numeric,numeric,jsonb,text,text,text) from public,anon,authenticated;
revoke execute on function penta_runtime.link_penta_route_work_cost_v1(text,uuid,text,text,uuid,text,text,jsonb) from public,anon,authenticated;
revoke execute on function penta_runtime.maintain_penta_route_economy_v1() from public,anon,authenticated;
revoke execute on function penta_discovery.intake_v1(text,text,text,jsonb,numeric,text,text,text) from public,anon,authenticated;

grant usage on schema penta_discovery to service_role;
grant all on all tables in schema penta_discovery to service_role;
grant all on penta_runtime.penta_route_rate_policy_v1,penta_runtime.penta_route_quotes_v1,penta_runtime.penta_route_reservations_v1,penta_runtime.penta_route_usage_events_v1,penta_runtime.penta_route_pay_obligations_v1,penta_runtime.penta_route_receipts_v1,penta_runtime.penta_pay_route_compensation_policy_v1,penta_runtime.penta_route_abuse_state_v1,penta_runtime.penta_route_governance_reconciliations_v1,penta_runtime.penta_route_work_cost_links_v1,penta_runtime.penta_discovery_certifications_v1 to service_role;
grant execute on function penta_runtime.validate_penta_economic_envelope_v1(jsonb) to service_role;
grant execute on function penta_runtime.quote_penta_route_v1(text,text,text,text,integer,integer,bigint,numeric,numeric,numeric,numeric,bigint,text) to service_role;
grant execute on function penta_runtime.reserve_penta_route_v1(uuid,jsonb) to service_role;
grant execute on function penta_runtime.record_penta_route_usage_v1(uuid,integer,text,text,bigint,bigint,text,jsonb) to service_role;
grant execute on function penta_runtime.reconcile_penta_route_v1(uuid,text,bigint,text,text) to service_role;
grant execute on function penta_runtime.materialize_route_penta_pay_v1(uuid,text,uuid,uuid) to service_role;
grant execute on function penta_runtime.reconcile_route_rate_signal_v1(text,text,numeric,numeric,jsonb,text,text,text) to service_role;
grant execute on function penta_runtime.reconcile_route_pay_signal_v1(text,text,numeric,numeric,jsonb,text,text,text) to service_role;
grant execute on function penta_runtime.link_penta_route_work_cost_v1(text,uuid,text,text,uuid,text,text,jsonb) to service_role;
grant execute on function penta_runtime.maintain_penta_route_economy_v1() to service_role;
grant execute on function penta_discovery.intake_v1(text,text,text,jsonb,numeric,text,text,text) to service_role;

-- Automated economic maintenance every five minutes. Existing external clocks remain untouched.
do $$
begin
  if not exists(select 1 from cron.job where jobname='penta-route-economy-maintenance-v1') then
    perform cron.schedule('penta-route-economy-maintenance-v1','*/5 * * * *','select penta_runtime.maintain_penta_route_economy_v1();');
  end if;
end $$;

insert into penta_runtime.crons_v1(schedule_id,job_name,cron_expression,timezone_name,purpose,strict_window_minutes,cron_jobid,state,metadata)
select 'ct-penta-route-economy-maintenance-v1','penta-route-economy-maintenance-v1','*/5 * * * *','UTC','Expire/reconcile route reservations, return unused Smart Treasury units, refresh anti-abuse state',10,j.jobid,'active',jsonb_build_object('owner','PentaTreasury','family','PentaDiscovery','external_scheduler_slot_delta',0)
from cron.job j where j.jobname='penta-route-economy-maintenance-v1'
on conflict(schedule_id) do update set cron_jobid=excluded.cron_jobid,state='active',metadata=excluded.metadata,updated_at=now();

create or replace function penta_runtime.certify_penta_discovery_family_v1(p_release_version text,p_canary_receipt_id uuid,p_independent_verifier_ref text)
returns jsonb
language plpgsql
security definer
set search_path=penta_runtime,penta_discovery,penta_os20,public,pg_catalog,extensions
as $$
declare v_checks jsonb;v_pass boolean;v_key text;v_hash text;v_id uuid;
begin
  v_checks:=jsonb_build_object(
   'family_registry_count',(select count(*) from penta_discovery.family_registry_v1 where lifecycle_state='active'),
   'runtime_component_count',(select count(*) from penta_runtime.component_registry_v1 where stable_contract_id='ct.penta.discovery.family.v1' and enabled),
   'production_system_count',(select count(*) from public.penta_system_registry where metadata->>'family'='PentaDiscovery' and maturity='production'),
   'economic_actor_count',(select count(*) from penta_os20.pentas where canonical_name in ('PentaDiscovery','PentaCrawler','PentaSearch','PentaQuery','PentaFetch','PentaGet','PentaParse','PentaResolve','PentaSignal','PentaContext','PentaCensus','PentaHarvestor') and status='active'),
   'active_route_rates',(select count(*) from penta_runtime.penta_route_rate_policy_v1 where governance_state='active'),
   'active_pay_policies',(select count(*) from penta_runtime.penta_pay_route_compensation_policy_v1 where governance_state='active'),
   'smart_treasury_active',exists(select 1 from penta_os20.pentas where canonical_name='PentaTreasury' and status='active'),
   'smart_treasury_today_budget',exists(select 1 from penta_os20.execution_budgets b join penta_os20.pentas p on p.id=b.penta_id where p.canonical_name='PentaTreasury' and b.budget_date=(now() at time zone 'America/New_York')::date),
   'canary_receipt_exists',exists(select 1 from penta_runtime.penta_route_receipts_v1 where receipt_id=p_canary_receipt_id and provider_money_movement=false),
   'packet_validator_present',to_regprocedure('penta_runtime.validate_penta_economic_envelope_v1(jsonb)') is not null,
   'maintenance_cron_active',exists(select 1 from penta_runtime.crons_v1 where schedule_id='ct-penta-route-economy-maintenance-v1' and state='active'),
   'internal_units_are_currency',false,
   'provider_money_movement_inherited',false
  );
  v_pass:=(v_checks->>'family_registry_count')::int=12 and (v_checks->>'runtime_component_count')::int=12 and (v_checks->>'production_system_count')::int>=12 and (v_checks->>'economic_actor_count')::int=12 and (v_checks->>'active_route_rates')::int>=6 and (v_checks->>'active_pay_policies')::int>=6 and (v_checks->>'smart_treasury_active')::boolean and (v_checks->>'smart_treasury_today_budget')::boolean and (v_checks->>'canary_receipt_exists')::boolean and (v_checks->>'packet_validator_present')::boolean and (v_checks->>'maintenance_cron_active')::boolean;
  v_key:='penta-discovery-cert:'||p_release_version||':'||encode(digest(concat_ws('|',p_release_version,p_canary_receipt_id::text,p_independent_verifier_ref,clock_timestamp()::text),'sha256'),'hex');
  v_hash:=encode(digest(concat_ws('|',v_key,v_checks::text),'sha256'),'hex');
  insert into penta_runtime.penta_discovery_certifications_v1(certification_key,release_version,verdict,checks,canary_receipt_id,independent_verifier_ref,evidence_sha256,expires_at)
  values(v_key,p_release_version,case when v_pass then 'PASS' else 'FAIL' end,v_checks,p_canary_receipt_id,p_independent_verifier_ref,v_hash,now()+interval '24 hours') returning certification_id into v_id;
  return jsonb_build_object('certification_id',v_id,'verdict',case when v_pass then 'PASS' else 'FAIL' end,'checks',v_checks,'evidence_sha256',v_hash,'expires_at',now()+interval '24 hours');
end;
$$;
revoke execute on function penta_runtime.certify_penta_discovery_family_v1(text,uuid,text) from public,anon,authenticated;
grant execute on function penta_runtime.certify_penta_discovery_family_v1(text,uuid,text) to service_role;

comment on table penta_runtime.penta_pay_route_compensation_policy_v1 is 'Governed PentaPay routing-service value policy in real currency. Internal Smart Treasury units remain non-currency and non-redeemable.';
comment on table penta_runtime.penta_route_work_cost_links_v1 is 'Causal link from metered Penta routing to patch/upgrade/build/release/provider work cost evidence.';
comment on function penta_runtime.validate_penta_economic_envelope_v1(jsonb) is 'Backward-compatible validator: canonical Penta v1 contract plus optional metered economic envelope.';
comment on function penta_runtime.materialize_route_penta_pay_v1(uuid,text,uuid,uuid) is 'Fail-closed bridge from route obligation to canonical PentaPay. Requires beneficiary, governance instrument and independent approving assignment; grants no provider dispatch authority.';
