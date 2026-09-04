-- CrownThrive Stripe OS Monetization Mesh v3
-- Production-applied 2026-09-01. Additive institutional source capture.
-- Stripe is a replaceable execution provider; PentaGreen retains economic authority.
-- No raw Stripe credential material is stored in this migration.

create table if not exists integration_control.stripe_os_accounts_v1 (
  account_ref text primary key,
  account_role text not null,
  route_priority integer not null,
  livemode boolean not null default true,
  country text not null default 'US',
  default_currency text not null default 'usd',
  charges_enabled boolean not null,
  payouts_enabled boolean not null,
  provider_state text not null,
  credential_policy_ref text not null default 'integration_control.stripe_live_secret_lanes_v1',
  capabilities jsonb not null default '{}'::jsonb,
  authority_ref text not null,
  metadata jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (account_role in ('COMMERCE_PRIMARY','SECONDARY_COMMERCE_EXPANSION','CONNECTED_ACCOUNT','SPECIALIZED'))
);

create table if not exists integration_control.stripe_os_capabilities_v1 (
  capability_key text primary key,
  capability_family text not null,
  provider_resource text not null,
  read_allowed boolean not null default true,
  provider_write_allowed boolean not null default false,
  monetization_write_allowed boolean not null default false,
  d3_or_human_gate_required boolean not null default false,
  penta_owner text not null,
  penta_green_component text not null,
  idempotency_required boolean not null default true,
  read_after_write_required boolean not null default true,
  rollback_or_compensation_required boolean not null default true,
  authority_ref text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.stripe_os_adapter_registry_v1 (
  adapter_key text primary key,
  adapter_class text not null,
  transport text not null,
  provider_surface text not null,
  lifecycle_state text not null,
  hot_warm_cold_policy_ref text not null,
  penta_route_owner text not null,
  penta_wire_owner text not null,
  penta_bridge_owner text not null,
  penta_green_owner text not null,
  supports_read boolean not null default true,
  supports_write boolean not null default false,
  supports_webhook boolean not null default false,
  supports_factory boolean not null default false,
  no_secret_projection boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.pentagreen_stripe_mesh_v3 (
  binding_id text primary key,
  supersedes_binding_id text,
  provider_system text not null default 'stripe',
  mesh_state text not null,
  primary_account_ref text not null references integration_control.stripe_os_accounts_v1(account_ref),
  secondary_account_ref text references integration_control.stripe_os_accounts_v1(account_ref),
  credential_lanes_ref text not null,
  product_inventory_ref text not null,
  price_inventory_ref text not null,
  payment_link_inventory_ref text not null,
  webhook_inventory_ref text not null,
  capability_registry_ref text not null,
  adapter_registry_ref text not null,
  factory_request_contract text not null,
  provider_write_state text not null,
  money_movement_state text not null,
  no_self_approval boolean not null default true,
  authority_ref text not null,
  provider_evidence_ref text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.pentagreen_stripe_monetization_requests_v1 (
  request_id uuid primary key default gen_random_uuid(),
  idempotency_key text unique not null,
  request_type text not null,
  subject_type text not null,
  subject_ref text not null,
  requested_output text not null,
  account_role text not null default 'COMMERCE_PRIMARY',
  request_state text not null default 'queued',
  authority_ref text not null,
  owner_role_id text not null default 'ct.role.thriveevergreen.commerce-binder',
  work_id uuid,
  stripe_product_id text,
  stripe_price_id text,
  stripe_payment_link_id text,
  stripe_subscription_id text,
  stripe_invoice_id text,
  payload jsonb not null default '{}'::jsonb,
  result jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (request_type in ('PRODUCT_PRICE','PAYMENT_LINK','CHECKOUT_BINDING','SUBSCRIPTION_PLAN','INVOICE_OFFER','WEBHOOK_BINDING','CONNECT_PLAN','REPRICE','CATALOG_SYNC')),
  check (requested_output in ('product_price','payment_link','checkout','subscription','invoice','webhook_binding','connect_plan','catalog_sync')),
  check (request_state in ('queued','claimed','executing','provider_accepted','readback_verified','complete','hold','failed','cancelled'))
);

create table if not exists integration_control.crownthrive_partner_registry_v1 (
  partner_key text primary key,
  partner_name text not null,
  partner_class text not null,
  relationship_state text not null,
  canonical_system_ref text,
  provider_account_refs text[] not null default array[]::text[],
  capability_refs text[] not null default array[]::text[],
  credential_policy_ref text,
  docs_ref text,
  repo_ref text,
  drive_ref text,
  penta_owner text,
  economic_owner text,
  authority_ref text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into integration_control.stripe_os_accounts_v1(account_ref,account_role,route_priority,livemode,country,default_currency,charges_enabled,payouts_enabled,provider_state,capabilities,authority_ref,metadata,observed_at,updated_at)
values
('acct_1MENDxCJFUeGxc8S','COMMERCE_PRIMARY',10,true,'US','usd',true,true,'provider_live_verified',
 jsonb_build_object('card_payments','active','transfers','active','ach','active','us_bank_transfer','active','sepa_debit','active','sepa_bank_transfer','active','link','active','cashapp','active','affirm','active','afterpay_clearpay','active','amazon_pay','active','bancontact','active','blik','active','eps','active','ideal','active','klarna','active','multibanco','active','p24','active','sofort','active'),
 'founder_directive_stripe_os_monetization_2026-08-31',
 jsonb_build_object('purpose','first_party_crownthrive_commerce_and_billing','mcp_account_verified',true,'source','Stripe MCP live account readback'),now(),now()),
('acct_1PlvdLAfFd6y22C1','SECONDARY_COMMERCE_EXPANSION',20,true,'US','usd',true,true,'provider_live_verified_direct',
 jsonb_build_object('card_payments','active','transfers','active','ach','active','link','active','cashapp','active','affirm','active','afterpay_clearpay','active','amazon_pay','active','bancontact','active','blik','active','crypto','active','eps','active','klarna','active','mb_way','active','multibanco','active','pay_by_bank','active','pix','active','satispay','active','zip','active','cartes_bancaires','pending'),
 'founder_directive_stripe_os_monetization_2026-08-31',
 jsonb_build_object('purpose','platform_connect_and_expansion','mcp_account_verified',true,'legacy_oauth_binding_state','hold_separate_from_direct_mcp_account_health','source','Stripe MCP live account readback'),now(),now())
on conflict(account_ref) do update set
 account_role=excluded.account_role,route_priority=excluded.route_priority,charges_enabled=excluded.charges_enabled,payouts_enabled=excluded.payouts_enabled,provider_state=excluded.provider_state,capabilities=excluded.capabilities,authority_ref=excluded.authority_ref,metadata=integration_control.stripe_os_accounts_v1.metadata||excluded.metadata,observed_at=excluded.observed_at,updated_at=now();

insert into integration_control.stripe_os_capabilities_v1(capability_key,capability_family,provider_resource,read_allowed,provider_write_allowed,monetization_write_allowed,d3_or_human_gate_required,penta_owner,penta_green_component,authority_ref,metadata)
values
('stripe.account','account','accounts',true,false,false,false,'PentaCredentials/PentaRoute','PentaBridge','founder_directive_stripe_os_monetization_2026-08-31','{"operations":["retrieve","capabilities","requirements"]}'::jsonb),
('stripe.customers','crm_commerce','customers',true,true,true,false,'PentaGreen/PentaCRM','PentaCatalog','founder_directive_stripe_os_monetization_2026-08-31','{"operations":["create","retrieve","update","list"]}'::jsonb),
('stripe.products','catalog','products',true,true,true,false,'PentaGreen/PentaFactory','PentaCatalog','founder_directive_stripe_os_monetization_2026-08-31','{"operations":["create","update","list","search"]}'::jsonb),
('stripe.prices','pricing','prices',true,true,true,false,'PentaGreen/PentaFactory','PentaPrice','founder_directive_stripe_os_monetization_2026-08-31','{"operations":["create","update","list","search"],"immutable_amount_change_rule":"new_price_object"}'::jsonb),
('stripe.payment_links','checkout','payment_links',true,true,true,false,'PentaGreen/PentaFactory','PentaCheckout','founder_directive_stripe_os_monetization_2026-08-31','{"operations":["create","update","list"]}'::jsonb),
('stripe.checkout','checkout','checkout_sessions',true,true,true,false,'PentaGreen/PentaCheckout','PentaCheckout','founder_directive_stripe_os_monetization_2026-08-31','{"operations":["create","retrieve","expire"],"fulfillment":"signed_webhook_only"}'::jsonb),
('stripe.payment_intents','payments','payment_intents',true,true,true,true,'PentaGreen/PentaCheckout','PentaReceipt','founder_directive_stripe_os_monetization_2026-08-31','{"money_effect":"customer_charge_or_authorization","execution_gate":"exact_order_authority"}'::jsonb),
('stripe.subscriptions','billing','subscriptions',true,true,true,false,'PentaGreen/PentaInvoice','PentaInvoice','founder_directive_stripe_os_monetization_2026-08-31','{"operations":["create_plan_binding","update","cancel_at_period_end"],"revenue_recovery":"webhook_driven"}'::jsonb),
('stripe.invoices','invoicing','invoices',true,true,true,false,'PentaGreen/PentaInvoice','PentaInvoice','founder_directive_stripe_os_monetization_2026-08-31','{"operations":["create","finalize","send","retrieve"],"automatic_collection":"policy_bound"}'::jsonb),
('stripe.quotes','sales_led','quotes',true,true,true,false,'PentaGreen/PentaMarketer','PentaPrice','founder_directive_stripe_os_monetization_2026-08-31','{"operations":["create","finalize","acceptance_handoff"]}'::jsonb),
('stripe.tax','tax','tax',true,true,true,false,'PentaGreen/PentaTax','PentaPolicy','founder_directive_stripe_os_monetization_2026-08-31','{"operations":["tax_code_binding","automatic_tax","threshold_monitoring"]}'::jsonb),
('stripe.connect','platform','connected_accounts',true,true,true,true,'PentaGreen/PentaBridge','PentaMarket','founder_directive_stripe_os_monetization_2026-08-31','{"operations":["account_plan","onboarding","capability_readback"],"money_routing_gate":"separate"}'::jsonb),
('stripe.application_fees','platform_monetization','application_fees',true,true,true,true,'PentaGreen/PentaMarket','PentaLedger','founder_directive_stripe_os_monetization_2026-08-31','{"operations":["application_fee_binding"],"charge_type_policy":"marketplace_or_saas_specific"}'::jsonb),
('stripe.transfers','money_movement','transfers',true,true,false,true,'PentaGreen/PentaPayout','PentaPayout','founder_directive_stripe_os_monetization_2026-08-31','{"money_movement":true,"autonomous_factory_forbidden":true}'::jsonb),
('stripe.refunds','post_sale','refunds',true,true,false,true,'PentaGreen/PentaCompensate','PentaCompensate','founder_directive_stripe_os_monetization_2026-08-31','{"money_movement":true,"customer_remedy":true}'::jsonb),
('stripe.disputes','risk','disputes',true,true,false,true,'PentaGreen/PentaRisk','PentaHold','founder_directive_stripe_os_monetization_2026-08-31','{"legal_financial_effect":true}'::jsonb),
('stripe.webhooks','events','webhook_endpoints_events',true,true,true,false,'PentaHook/PentaWire/PentaGreen','PentaBridge','founder_directive_stripe_os_monetization_2026-08-31','{"operations":["endpoint_readback","event_ingest","signed_canary","route_binding"],"endpoint_create_delete":"capacity_and_topology_bound"}'::jsonb),
('stripe.reporting','analytics','balance_transactions_events_reporting',true,false,false,false,'PentaLedger/PentaLytics','PentaLedger','founder_directive_stripe_os_monetization_2026-08-31','{"operations":["read","reconcile","forecast_inputs"]}'::jsonb)
on conflict(capability_key) do update set
 capability_family=excluded.capability_family,provider_resource=excluded.provider_resource,read_allowed=excluded.read_allowed,provider_write_allowed=excluded.provider_write_allowed,monetization_write_allowed=excluded.monetization_write_allowed,d3_or_human_gate_required=excluded.d3_or_human_gate_required,penta_owner=excluded.penta_owner,penta_green_component=excluded.penta_green_component,authority_ref=excluded.authority_ref,metadata=integration_control.stripe_os_capabilities_v1.metadata||excluded.metadata,updated_at=now();

insert into integration_control.stripe_os_adapter_registry_v1(adapter_key,adapter_class,transport,provider_surface,lifecycle_state,hot_warm_cold_policy_ref,penta_route_owner,penta_wire_owner,penta_bridge_owner,penta_green_owner,supports_read,supports_write,supports_webhook,supports_factory,metadata)
values
('ct.adapter.stripe.mcp.v1','operator_mcp','Stripe MCP','Stripe API','active','integration_control.stripe_live_secret_lanes_v1','PentaRoute','PentaWire','PentaBridge','PentaGreen',true,true,false,true,'{"purpose":"operator/provider API discovery and governed execution","secret_projection":false}'::jsonb),
('ct.adapter.stripe.runtime.v1','runtime_api','HTTPS REST','Stripe API','active','integration_control.stripe_live_secret_lanes_v1','PentaRoute','PentaWire','PentaBridge','PentaGreen',true,true,false,true,'{"purpose":"server-side runtime provider calls","idempotency_required":true,"read_after_write":true}'::jsonb),
('ct.adapter.stripe.webhook.v3','event_ingress','signed webhook','Stripe events','active','integration_control.stripe_live_secret_lanes_v1','PentaRoute','PentaWire','PentaHook/PentaBridge','PentaGreen',true,true,true,false,'{"source_of_truth":"signed_provider_event","existing_lane_registry":"integration_control.stripe_webhook_lanes_v3"}'::jsonb),
('ct.adapter.stripe.catalog-mirror.v2','provider_mirror','ThriveBase projection','Stripe products/prices/payment_links','active','integration_control.stripe_live_secret_lanes_v1','PentaRoute','PentaWire','PentaBridge','PentaGreen',true,false,false,true,'{"products":"integration_control.stripe_catalog_products_v2","prices":"integration_control.stripe_catalog_prices_v2","payment_links":"integration_control.stripe_payment_link_inventory_v4"}'::jsonb)
on conflict(adapter_key) do update set lifecycle_state=excluded.lifecycle_state,supports_read=excluded.supports_read,supports_write=excluded.supports_write,supports_webhook=excluded.supports_webhook,supports_factory=excluded.supports_factory,metadata=integration_control.stripe_os_adapter_registry_v1.metadata||excluded.metadata,updated_at=now();

insert into integration_control.pentagreen_stripe_mesh_v3(binding_id,supersedes_binding_id,mesh_state,primary_account_ref,secondary_account_ref,credential_lanes_ref,product_inventory_ref,price_inventory_ref,payment_link_inventory_ref,webhook_inventory_ref,capability_registry_ref,adapter_registry_ref,factory_request_contract,provider_write_state,money_movement_state,no_self_approval,authority_ref,provider_evidence_ref,metadata)
values('ct.binding.pentagreen-stripe-mesh.v3','ct.binding.thriveevergreen-stripe-live.v2','ACTIVE_MONETIZATION_READY','acct_1MENDxCJFUeGxc8S','acct_1PlvdLAfFd6y22C1','integration_control.stripe_live_secret_lanes_v1','integration_control.stripe_catalog_products_v2','integration_control.stripe_catalog_prices_v2','integration_control.stripe_payment_link_inventory_v4','integration_control.stripe_webhook_lanes_v3','integration_control.stripe_os_capabilities_v1','integration_control.stripe_os_adapter_registry_v1','integration_control.pentagreen_stripe_prepare_monetization_v1','AUTHORIZED_FOR_CATALOG_CHECKOUT_BILLING_BINDINGS','SEPARATELY_GATED',true,'founder_directive_stripe_os_monetization_2026-08-31','integration_control.stripe_webhook_provider_receipts_v3',jsonb_build_object('legacy_hold_superseded_not_rewritten',true,'penta_green_authority','ct.pentagreen.core.v1','factory_role','ct.role.thriveevergreen.commerce-binder','products_mirrored',456,'prices_mirrored',478,'payment_links_mirrored',48,'webhook_lanes',4,'webhook_endpoints',15,'stripe_provider_is_replaceable_execution_system',true,'clone_policy','CrownThrive-owned adapters/contracts/mirrors only; no Stripe proprietary backend replication'))
on conflict(binding_id) do update set mesh_state=excluded.mesh_state,primary_account_ref=excluded.primary_account_ref,secondary_account_ref=excluded.secondary_account_ref,provider_write_state=excluded.provider_write_state,money_movement_state=excluded.money_movement_state,authority_ref=excluded.authority_ref,provider_evidence_ref=excluded.provider_evidence_ref,metadata=integration_control.pentagreen_stripe_mesh_v3.metadata||excluded.metadata,updated_at=now();

insert into integration_control.crownthrive_partner_registry_v1(partner_key,partner_name,partner_class,relationship_state,canonical_system_ref,provider_account_refs,capability_refs,credential_policy_ref,docs_ref,repo_ref,penta_owner,economic_owner,authority_ref,metadata)
select 'ct.partner.stripe','Stripe','payments_financial_infrastructure','active_integrated','stripe',array['acct_1MENDxCJFUeGxc8S','acct_1PlvdLAfFd6y22C1']::text[],array_agg(capability_key order by capability_key),'integration_control.stripe_live_secret_lanes_v1','/commerce/stripe-os-monetization-fabric','github:crownthrive1/CrownThrive-OS','PentaBridge/PentaHook/PentaCredentials/PentaRoute/PentaWire','PentaGreen','founder_directive_stripe_os_monetization_2026-08-31',jsonb_build_object('mcp_available',true,'api_available',true,'webhooks_active',true,'no_secret_projection',true,'partner_sheet_required',true)
from integration_control.stripe_os_capabilities_v1
on conflict(partner_key) do update set relationship_state=excluded.relationship_state,provider_account_refs=excluded.provider_account_refs,capability_refs=excluded.capability_refs,credential_policy_ref=excluded.credential_policy_ref,docs_ref=excluded.docs_ref,repo_ref=excluded.repo_ref,penta_owner=excluded.penta_owner,economic_owner=excluded.economic_owner,authority_ref=excluded.authority_ref,metadata=integration_control.crownthrive_partner_registry_v1.metadata||excluded.metadata,updated_at=now();

create or replace view integration_control.pentagreen_stripe_catalog_bridge_v1 as
select p.provider_account_id,
       p.provider_product_id,
       p.name as product_name,
       p.description as product_description,
       p.active as product_active,
       p.tax_code,
       pr.provider_price_id,
       pr.active as price_active,
       pr.currency,
       pr.unit_amount,
       pr.billing_type,
       pr.recurring_interval,
       pr.recurring_interval_count,
       pr.lookup_key,
       pl.payment_link_id,
       pl.url as payment_link_url,
       pl.active as payment_link_active,
       coalesce(p.metadata,'{}'::jsonb)||jsonb_build_object('provider','stripe','economic_authority','PentaGreen','provider_product_alias',p.provider_product_id,'provider_price_alias',pr.provider_price_id) as metadata,
       greatest(p.updated_at,pr.updated_at,coalesce(pl.updated_at,'epoch'::timestamptz)) as observed_at
from integration_control.stripe_catalog_products_v2 p
join integration_control.stripe_catalog_prices_v2 pr on pr.provider_product_id=p.provider_product_id
left join integration_control.stripe_payment_link_inventory_v4 pl on pl.price_id=pr.provider_price_id and pl.provider_account_id=p.provider_account_id;

create or replace function integration_control.pentagreen_stripe_prepare_monetization_v1(
  p_subject_type text,
  p_subject_ref text,
  p_request_type text,
  p_requested_output text,
  p_payload jsonb default '{}'::jsonb,
  p_account_role text default 'COMMERCE_PRIMARY',
  p_priority smallint default 40,
  p_authority_ref text default 'founder_directive_stripe_os_monetization_2026-08-31'
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','public','extensions'
as $fn$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_idem text;
  v_request uuid;
  v_work uuid;
  v_existing integration_control.pentagreen_stripe_monetization_requests_v1%rowtype;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if p_request_type not in ('PRODUCT_PRICE','PAYMENT_LINK','CHECKOUT_BINDING','SUBSCRIPTION_PLAN','INVOICE_OFFER','WEBHOOK_BINDING','CONNECT_PLAN','REPRICE','CATALOG_SYNC') then raise exception 'unsupported_monetization_request_type'; end if;
  if p_requested_output not in ('product_price','payment_link','checkout','subscription','invoice','webhook_binding','connect_plan','catalog_sync') then raise exception 'unsupported_monetization_output'; end if;
  if lower(coalesce(p_payload::text,'')) ~ '(refund|payout|bank[_ -]?account|external[_ -]?account|dispute[_ -]?accept|transfer[_ -]?funds|rights[_ -]?grant)' then raise exception 'reserved_effect_requires_separate_authority_lane'; end if;
  if not exists(select 1 from integration_control.pentagreen_mesh_agent_roles_v1 where role_id='ct.role.thriveevergreen.commerce-binder' and lifecycle_state='active' and provider_write_allowed=true and no_self_approval=true) then raise exception 'commerce_binder_unavailable'; end if;
  v_idem:=encode(extensions.digest(convert_to(coalesce(p_subject_type,'')||'|'||coalesce(p_subject_ref,'')||'|'||p_request_type||'|'||p_requested_output||'|'||coalesce(p_account_role,'')||'|'||coalesce(p_payload,'{}'::jsonb)::text,'UTF8'),'sha256'),'hex');
  select * into v_existing from integration_control.pentagreen_stripe_monetization_requests_v1 where idempotency_key=v_idem;
  if found then
    return jsonb_build_object('state','REUSE','request_id',v_existing.request_id,'work_id',v_existing.work_id,'request_state',v_existing.request_state,'idempotency_key',v_idem,'authority_created',false);
  end if;
  v_request:=gen_random_uuid();
  v_work:=gen_random_uuid();
  insert into integration_control.pentagreen_stripe_monetization_requests_v1(request_id,idempotency_key,request_type,subject_type,subject_ref,requested_output,account_role,request_state,authority_ref,work_id,payload)
  values(v_request,v_idem,p_request_type,p_subject_type,p_subject_ref,p_requested_output,p_account_role,'queued',p_authority_ref,v_work,coalesce(p_payload,'{}'::jsonb)||jsonb_build_object('stripe_mesh','ct.binding.pentagreen-stripe-mesh.v3','provider_execution_only',true,'economic_authority','PentaGreen','no_self_approval',true));
  insert into integration_control.thriveevergreen_mesh_work_queue_v1(work_id,work_type,subject_type,subject_ref,role_id,priority,work_state,idempotency_key,authority_ref,payload)
  values(v_work,'stripe_monetization',p_subject_type,p_subject_ref,'ct.role.thriveevergreen.commerce-binder',greatest(1,least(coalesce(p_priority,40),100)),'queued','stripe:'||v_idem,p_authority_ref,jsonb_build_object('request_id',v_request,'request_type',p_request_type,'requested_output',p_requested_output,'account_role',p_account_role,'payload',coalesce(p_payload,'{}'::jsonb),'stripe_mesh','ct.binding.pentagreen-stripe-mesh.v3'));
  return jsonb_build_object('state','QUEUED','request_id',v_request,'work_id',v_work,'idempotency_key',v_idem,'owner_role','ct.role.thriveevergreen.commerce-binder','authority_created',false,'money_movement',false);
end
$fn$;

create or replace function integration_control.stripe_os_mesh_status_v1() returns jsonb
language sql
security definer
set search_path to 'pg_catalog','integration_control'
as $fn$
select jsonb_build_object(
 'state',(select mesh_state from integration_control.pentagreen_stripe_mesh_v3 where binding_id='ct.binding.pentagreen-stripe-mesh.v3'),
 'accounts',(select coalesce(jsonb_agg(jsonb_build_object('account_ref',account_ref,'role',account_role,'priority',route_priority,'provider_state',provider_state,'charges_enabled',charges_enabled,'payouts_enabled',payouts_enabled) order by route_priority),'[]'::jsonb) from integration_control.stripe_os_accounts_v1),
 'credential_lanes',(select coalesce(jsonb_agg(jsonb_build_object('role',custody_role,'priority',priority,'alias',vault_alias,'eligible',platform_failover_eligible,'verification_state',verification_state) order by priority),'[]'::jsonb) from integration_control.stripe_live_secret_lanes_v1 where enabled=true),
 'capability_count',(select count(*) from integration_control.stripe_os_capabilities_v1),
 'factory_monetization_capabilities',(select count(*) from integration_control.stripe_os_capabilities_v1 where monetization_write_allowed=true),
 'catalog',jsonb_build_object('products',(select count(*) from integration_control.stripe_catalog_products_v2),'prices',(select count(*) from integration_control.stripe_catalog_prices_v2),'payment_links',(select count(*) from integration_control.stripe_payment_link_inventory_v4)),
 'webhooks',jsonb_build_object('lanes',(select count(*) from integration_control.stripe_webhook_lanes_v3),'endpoints',(select count(*) from integration_control.stripe_webhook_endpoints_v3),'latest_provider_receipt',(select max(observed_at) from integration_control.stripe_webhook_provider_receipts_v3)),
 'queued_monetization_requests',(select count(*) from integration_control.pentagreen_stripe_monetization_requests_v1 where request_state='queued'),
 'no_self_approval',true,
 'money_movement_separately_gated',true,
 'observed_at',now()
)
$fn$;

revoke all on integration_control.stripe_os_accounts_v1, integration_control.stripe_os_capabilities_v1, integration_control.stripe_os_adapter_registry_v1, integration_control.pentagreen_stripe_mesh_v3, integration_control.pentagreen_stripe_monetization_requests_v1, integration_control.crownthrive_partner_registry_v1 from public, anon, authenticated;
revoke all on function integration_control.pentagreen_stripe_prepare_monetization_v1(text,text,text,text,jsonb,text,smallint,text) from public, anon, authenticated;
revoke all on function integration_control.stripe_os_mesh_status_v1() from public, anon, authenticated;
grant select on integration_control.stripe_os_accounts_v1, integration_control.stripe_os_capabilities_v1, integration_control.stripe_os_adapter_registry_v1, integration_control.pentagreen_stripe_mesh_v3, integration_control.pentagreen_stripe_monetization_requests_v1, integration_control.crownthrive_partner_registry_v1, integration_control.pentagreen_stripe_catalog_bridge_v1 to service_role;
grant execute on function integration_control.pentagreen_stripe_prepare_monetization_v1(text,text,text,text,jsonb,text,smallint,text), integration_control.stripe_os_mesh_status_v1() to service_role;
