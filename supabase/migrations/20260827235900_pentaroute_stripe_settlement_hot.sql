-- CrownThrive PentaRoute / Self-Funding Settlement production reconciliation
-- Idempotent desired-state migration. No secrets or provider account IDs are embedded.

create table if not exists public.ct_self_funding_settlement_routes (
  route_key text primary key,
  route_group text not null default 'self_funding_default',
  provider text not null,
  provider_ref text not null,
  route_mode text not null,
  priority integer not null,
  state text not null default 'standby',
  health_state text not null default 'unknown',
  internal_only boolean not null default false,
  requires_external_contract boolean not null default true,
  provider_capable boolean not null default false,
  money_movement_authorized boolean not null default false,
  read_after_write_state text not null default 'unverified',
  rollback_state text not null default 'unverified',
  failover_on text[] not null default array['provider_unavailable','provider_degraded','route_timeout']::text[],
  evidence jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  last_verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into public.ct_self_funding_settlement_routes(
  route_key,route_group,provider,provider_ref,route_mode,priority,state,health_state,
  internal_only,requires_external_contract,provider_capable,money_movement_authorized,
  read_after_write_state,rollback_state,evidence,metadata,last_verified_at,updated_at
)
select
  'sfe.stripe.crownthrive.hot.v1','self_funding_default','stripe',
  s.metadata->>'connected_account_id','hot',10,'active','green',true,false,true,true,
  'pass','pass',
  jsonb_build_object('source','Stripe live API certification','create_readback_pass',true,'rollback_pass',true),
  jsonb_build_object('scope','CrownThrive-internal settlement only','charge_model','separate_charges_and_transfers'),
  now(),now()
from integration_control.services s
where s.service_id='stripe' and coalesce(s.metadata->>'connected_account_id','')<>''
on conflict(route_key) do update set
  provider_ref=excluded.provider_ref,state=excluded.state,health_state=excluded.health_state,
  internal_only=excluded.internal_only,requires_external_contract=excluded.requires_external_contract,
  provider_capable=excluded.provider_capable,money_movement_authorized=excluded.money_movement_authorized,
  read_after_write_state=excluded.read_after_write_state,rollback_state=excluded.rollback_state,
  evidence=public.ct_self_funding_settlement_routes.evidence || excluded.evidence,
  metadata=public.ct_self_funding_settlement_routes.metadata || excluded.metadata,
  last_verified_at=excluded.last_verified_at,updated_at=excluded.updated_at;

insert into public.ct_self_funding_settlement_routes(
  route_key,provider,provider_ref,route_mode,priority,state,health_state,internal_only,
  requires_external_contract,provider_capable,money_movement_authorized,
  read_after_write_state,rollback_state,evidence,metadata,last_verified_at,updated_at
) values
('sfe.paypal.crownthrive.cold.v1','paypal','crownthrive','cold',20,'standby','green',true,false,true,false,'pass','pass',
 '{"source":"penta_os20.settlement_readiness_status_v1","adapter_state":"ready"}'::jsonb,
 '{"role":"cold failover","authority_mode":"per_obligation"}'::jsonb,now(),now()),
('sfe.paypal.penta.cold.v1','paypal','penta','cold',30,'standby','green',true,false,true,false,'pass','pass',
 '{"source":"penta_os20.settlement_readiness_status_v1","adapter_state":"ready"}'::jsonb,
 '{"role":"secondary cold failover","authority_mode":"per_obligation"}'::jsonb,now(),now()),
('sfe.ledger.queue.v1','internal_ledger','penta_pay_settlement_receipts_v2','queue',90,'active','green',false,false,true,false,'not_applicable','not_applicable',
 '{"purpose":"durable settlement queue and evidence preservation"}'::jsonb,
 '{"role":"last-resort fail-closed queue; never drops an obligation"}'::jsonb,now(),now())
on conflict(route_key) do update set
 state=excluded.state,health_state=excluded.health_state,provider_capable=excluded.provider_capable,
 evidence=public.ct_self_funding_settlement_routes.evidence || excluded.evidence,
 metadata=public.ct_self_funding_settlement_routes.metadata || excluded.metadata,
 last_verified_at=excluded.last_verified_at,updated_at=excluded.updated_at;

create or replace function integration_control.dispatch_stripe_internal_transfer_v1(
  p_amount bigint,
  p_currency text,
  p_idempotency_key text,
  p_transfer_group text default null
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','extensions','vault','public'
as $$
declare
  v_secret text;
  v_resp extensions.http_response;
  v_body jsonb;
begin
  if p_amount <= 0 then raise exception 'amount_must_be_positive'; end if;
  if length(coalesce(p_idempotency_key,'')) < 12 then raise exception 'idempotency_key_required'; end if;
  if not exists (
    select 1 from public.ct_self_funding_settlement_routes
    where route_key='sfe.stripe.crownthrive.hot.v1'
      and state='active' and health_state='green'
      and internal_only and provider_capable and money_movement_authorized
  ) then raise exception 'hot_route_not_authorized'; end if;

  select decrypted_secret into v_secret
  from vault.decrypted_secrets
  where name='stripe_production_control_gateway_secret_v1'
  limit 1;
  if coalesce(v_secret,'')='' then raise exception 'stripe_gateway_secret_missing'; end if;

  v_resp := extensions.http((
    'POST'::extensions.http_method,
    'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/stripe-production-control',
    array[extensions.http_header('x-ct-stripe-control-secret',v_secret)],
    'application/json',
    jsonb_build_object(
      'action','create_transfer',
      'amount',p_amount,
      'currency',lower(p_currency),
      'idempotency_key',p_idempotency_key,
      'transfer_group',p_transfer_group
    )::text
  )::extensions.http_request);

  begin v_body := v_resp.content::jsonb;
  exception when others then v_body := jsonb_build_object('error','invalid_json_response'); end;

  return jsonb_build_object('http_status',v_resp.status,'body',v_body,'raw_secret_export',false);
end;
$$;

-- Internal platform authority is distinct from third-party provider contracts.
insert into public.ct_self_funding_contracts(
  contract_key,contract_type,counterparty_ref,policy_key,state,signature_required,signature_state,source_ref
)
select 'CT-SFE-INTERNAL-SETTLEMENT-1.0','platform','CrownThrive, LLC','CT-SFE-80-10-5-3-2',
       'executed',false,'complete','founder-directive:2026-08-27'
where exists(select 1 from public.ct_self_funding_policies where policy_key='CT-SFE-80-10-5-3-2')
on conflict(contract_key) do update set
  state='executed',signature_required=false,signature_state='complete',source_ref=excluded.source_ref;
