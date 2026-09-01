-- Project live Stripe capability/adoption truth without treating provider
-- availability as CrownThrive authority or production certification.

create table if not exists integration_control.stripe_os_capability_adoption_v2 (
  capability_key text primary key references integration_control.stripe_os_capabilities_v1(capability_key) on update cascade on delete restrict,
  provider_availability text not null,
  crownthrive_state text not null,
  autonomy_state text not null,
  write_route text,
  hold_reason text,
  live_evidence jsonb not null default '{}'::jsonb,
  authority_ref text not null,
  observed_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp()
);

alter table integration_control.stripe_os_capability_adoption_v2 enable row level security;
revoke all on integration_control.stripe_os_capability_adoption_v2 from public,anon,authenticated;
grant select on integration_control.stripe_os_capability_adoption_v2 to service_role;

insert into integration_control.stripe_os_capabilities_v1(
  capability_key,capability_family,provider_resource,read_allowed,provider_write_allowed,
  monetization_write_allowed,d3_or_human_gate_required,penta_owner,penta_green_component,
  idempotency_required,read_after_write_required,rollback_or_compensation_required,
  authority_ref,metadata
) values
('stripe.billing_portal','billing','billing_portal',true,false,false,false,'PentaGreen/PentaInvoice','PentaInvoice',true,true,true,'founder_directive_stripe_os_monetization_2026-08-31','{"operations":["configuration_read","session_plan"],"typed_executor":"not_implemented"}'::jsonb),
('stripe.coupons','promotion','coupons',true,false,false,true,'PentaGreen/PentaPrice','PentaPrice',true,true,true,'founder_directive_stripe_os_monetization_2026-08-31','{"typed_executor":"not_implemented"}'::jsonb),
('stripe.promotion_codes','promotion','promotion_codes',true,false,false,true,'PentaGreen/PentaPrice','PentaPrice',true,true,true,'founder_directive_stripe_os_monetization_2026-08-31','{"typed_executor":"not_implemented"}'::jsonb),
('stripe.billing_meters','billing_usage','billing_meters_metronome',true,false,false,true,'PentaGreen/PentaInvoice','PentaMeter',true,true,true,'founder_directive_stripe_os_monetization_2026-08-31','{"typed_executor":"not_implemented","metered_prices_observed":0}'::jsonb),
('stripe.payouts','money_movement','payouts_external_accounts',true,false,false,true,'PentaGreen/PentaPayout','PentaPayout',true,true,true,'founder_directive_stripe_os_monetization_2026-08-31','{"money_movement":true,"autonomous_factory_forbidden":true}'::jsonb),
('stripe.terminal','in_person','terminal',true,false,false,true,'PentaGreen/PentaCheckout','PentaCheckout',true,true,true,'founder_directive_stripe_os_monetization_2026-08-31','{"typed_executor":"not_implemented"}'::jsonb),
('stripe.identity','identity','identity',true,false,false,true,'PentaID/PentaPolicy','PentaBridge',true,true,true,'founder_directive_stripe_os_monetization_2026-08-31','{"typed_executor":"not_implemented","privacy_review_required":true}'::jsonb),
('stripe.financial_connections','financial_data','financial_connections',true,false,false,true,'PentaCredentials/PentaPolicy','PentaBridge',true,true,true,'founder_directive_stripe_os_monetization_2026-08-31','{"typed_executor":"not_implemented","privacy_review_required":true}'::jsonb),
('stripe.issuing','issuing','issuing',true,false,false,true,'PentaGreen/PentaPolicy','PentaLedger',true,true,true,'founder_directive_stripe_os_monetization_2026-08-31','{"typed_executor":"not_implemented","money_effect":true}'::jsonb),
('stripe.treasury','treasury','money_management_treasury',true,false,false,true,'PentaGreen/PentaTreasury','PentaLedger',true,true,true,'founder_directive_stripe_os_monetization_2026-08-31','{"typed_executor":"not_implemented","money_effect":true}'::jsonb),
('stripe.radar','risk','radar_reviews_early_fraud_warnings',true,false,false,true,'PentaGreen/PentaRisk','PentaHold',true,true,true,'founder_directive_stripe_os_monetization_2026-08-31','{"typed_executor":"not_implemented"}'::jsonb),
('stripe.data_exports','analytics','sigma_reporting_data_pipeline',true,false,false,false,'PentaLedger/PentaLytics','PentaLedger',true,true,true,'founder_directive_stripe_os_monetization_2026-08-31','{"typed_executor":"read_only_not_certified"}'::jsonb)
on conflict(capability_key) do update set
  capability_family=excluded.capability_family,provider_resource=excluded.provider_resource,
  read_allowed=excluded.read_allowed,provider_write_allowed=excluded.provider_write_allowed,
  monetization_write_allowed=excluded.monetization_write_allowed,
  d3_or_human_gate_required=excluded.d3_or_human_gate_required,penta_owner=excluded.penta_owner,
  penta_green_component=excluded.penta_green_component,metadata=integration_control.stripe_os_capabilities_v1.metadata||excluded.metadata,
  updated_at=clock_timestamp();

update integration_control.stripe_os_capabilities_v1
set provider_write_allowed=capability_key in ('stripe.products','stripe.prices','stripe.payment_links','stripe.webhooks'),
    monetization_write_allowed=capability_key in ('stripe.products','stripe.prices','stripe.payment_links','stripe.webhooks'),
    d3_or_human_gate_required=case
      when capability_key in ('stripe.products','stripe.prices','stripe.payment_links','stripe.webhooks','stripe.account','stripe.reporting','stripe.data_exports','stripe.billing_portal') then false
      else true
    end,
    metadata=metadata||jsonb_build_object(
      'typed_runtime_executor',case when capability_key in ('stripe.products','stripe.prices','stripe.payment_links') then 'integration_control.stripe_os_provider_operation_v2' when capability_key='stripe.webhooks' then 'integration_control.stripe_webhook_provider_reconcile_v3' else null end,
      'capability_available_is_not_authority',true,
      'factory_clock_active',false,
      'truth_reconciled_at',clock_timestamp()
    ),
    updated_at=clock_timestamp();

update integration_control.stripe_os_capabilities_v1
set provider_write_allowed=false,monetization_write_allowed=false,d3_or_human_gate_required=true,
    metadata=metadata||jsonb_build_object('automatic_tax_hold','product types disabled for sale and legal taxability review required','active_registration_scope','US-VA only','registration_count',1)
where capability_key='stripe.tax';

update integration_control.stripe_os_capabilities_v1
set provider_write_allowed=false,monetization_write_allowed=false,d3_or_human_gate_required=true,
    metadata=metadata||jsonb_build_object('payout_rail_state','HOLD_DEFAULT_BANK_ERRORED','controlled_canary_required',true)
where capability_key in ('stripe.payouts','stripe.transfers');

insert into integration_control.stripe_os_capability_adoption_v2(capability_key,provider_availability,crownthrive_state,autonomy_state,write_route,hold_reason,live_evidence,authority_ref)
values
('stripe.account','active','verified_with_operational_hold','read_only',null,'default payout bank reports errored',jsonb_build_object('active_payment_capabilities',22,'charges_enabled',true,'payouts_enabled_account_flag',true,'requirements_due',0),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.products','active','active_needs_normalization','typed_ready_factory_paused','integration_control.stripe_os_provider_operation_v2','zero governed sale-ready factory candidates',jsonb_build_object('provider_total',459,'provider_active',434,'mirror_total',456,'active_without_default_price',131,'active_without_list_price',8,'duplicate_active_name_groups',48),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.prices','active','active_needs_normalization','typed_ready_factory_paused','integration_control.stripe_os_provider_operation_v2','107 mirror prices lack account scope and most live prices lack lookup keys',jsonb_build_object('provider_total',484,'provider_active',465,'mirror_total',478,'active_without_lookup_key',384,'active_prices_on_inactive_products',7),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.payment_links','active','degraded_normalization','typed_ready_factory_paused','integration_control.stripe_os_provider_operation_v2','entitlement/webhook binding absent across factory profiles',jsonb_build_object('total',48,'active',33,'inactive',15,'duplicate_groups',2,'promotion_enabled_without_codes',14),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.checkout','active','observed_not_factory_executed','held_specialized_executor',null,'typed Checkout executor and generic entitlement path not certified',jsonb_build_object('sessions',225,'complete_paid',11,'open_unpaid',12,'expired_unpaid',202,'dynamic_payment_methods_required',true),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.customers','active','observed','held_specialized_executor',null,'typed customer executor not implemented',jsonb_build_object('customers',36),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.subscriptions','active','limited_licensed_only','held_specialized_executor',null,'subscription executor and lifecycle canary not certified',jsonb_build_object('total',4,'active',1,'canceled',1,'incomplete_expired',2,'recurring_prices',257,'metered_prices',0),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.invoices','active','observed','held_specialized_executor',null,'invoice executor not certified',jsonb_build_object('total',11,'paid',8,'open',1,'void',2,'metadata_missing',11),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.quotes','available','not_certified','held_specialized_executor',null,'typed quote executor not implemented','{}'::jsonb,'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.billing_portal','active','configured','read_only',null,null,jsonb_build_object('active_configurations',1,'plan_changes_enabled',false,'pause_enabled',false,'cancel_at_period_end',true),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.tax','active','configured_us_va_only','held_legal_tax_gate',null,'all product types disabled for sale and all tax profiles require jurisdiction review',jsonb_build_object('active_registrations',1,'registration_scope','US-VA','product_tax_code_missing_active_products',420),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.connect','active','partial_v2_readback','d3_gated',null,'one connected account inaccessible and no typed Accounts v2 mutation executor',jsonb_build_object('v2_accounts_observed',4,'accessible',3,'inaccessible',1),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.application_fees','available','not_certified','d3_gated',null,'charge model and liability must be exact-offer approved','{}'::jsonb,'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.transfers','active','provider_capability_active','d3_gated',null,'money movement separately gated',jsonb_build_object('account_capability','active'),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.payouts','active','hold_default_bank_errored','d3_gated',null,'controlled payout canary required before healthy certification',jsonb_build_object('account_flag',true,'default_bank_state','errored'),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.refunds','active','observed_read_only','d3_gated',null,'customer remedy and money effect',jsonb_build_object('successful_refunds',9,'total_minor_units',3197),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.disputes','active','observed_none','d3_gated',null,'legal and financial effect',jsonb_build_object('observed',0),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.webhooks','active','degraded_topology','typed_reconcile_factory_paused','integration_control.stripe_webhook_provider_reconcile_v3','wildcard canary failure, endpoint redundancy and API-version fragmentation',jsonb_build_object('enabled_endpoints',16,'wildcard_endpoints',1,'account_default_api_version_endpoints',13,'missing_descriptions',10,'missing_metadata',9),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.reporting','active','read_available','read_only',null,null,jsonb_build_object('reconciliation_role','PentaLedger'),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.data_exports','available','not_certified','read_only',null,'analytics/report tool route not certified','{}'::jsonb,'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.coupons','active','needs_normalization','d3_gated',null,'two duplicate 25 percent forever coupons',jsonb_build_object('valid',3,'duplicate_groups',1,'redemptions',0),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.promotion_codes','active','not_configured','d3_gated',null,'no promotion codes exist',jsonb_build_object('count',0),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.billing_meters','available','not_configured','d3_gated',null,'no metered or meter-linked prices',jsonb_build_object('metered_prices',0),'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.payment_intents','active','observed_via_checkout','d3_gated',null,'no standalone typed order executor certified','{}'::jsonb,'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.terminal','available','not_adopted','d3_gated',null,'not audited or configured','{}'::jsonb,'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.identity','available','not_adopted','d3_gated',null,'privacy and identity review required','{}'::jsonb,'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.financial_connections','available','not_adopted','d3_gated',null,'privacy and financial-data review required','{}'::jsonb,'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.issuing','available','not_adopted','d3_gated',null,'not audited or configured','{}'::jsonb,'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.treasury','available','not_adopted','d3_gated',null,'not audited or configured','{}'::jsonb,'founder_directive_stripe_os_monetization_2026-08-31'),
('stripe.radar','available','event_surface_observed','d3_gated',null,'risk action executor not certified','{}'::jsonb,'founder_directive_stripe_os_monetization_2026-08-31')
on conflict(capability_key) do update set provider_availability=excluded.provider_availability,crownthrive_state=excluded.crownthrive_state,autonomy_state=excluded.autonomy_state,write_route=excluded.write_route,hold_reason=excluded.hold_reason,live_evidence=excluded.live_evidence,authority_ref=excluded.authority_ref,observed_at=excluded.observed_at,updated_at=clock_timestamp();

insert into integration_control.stripe_os_adapter_registry_v1(adapter_key,adapter_class,transport,provider_surface,lifecycle_state,hot_warm_cold_policy_ref,penta_route_owner,penta_wire_owner,penta_bridge_owner,penta_green_owner,supports_read,supports_write,supports_webhook,supports_factory,no_secret_projection,metadata)
values('ct.adapter.stripe.v1','canonical_provider_adapter','typed multi-transport','Stripe API / MCP / signed webhooks / provider mirrors','active_with_holds','integration_control.stripe_live_secret_lanes_v1','PentaRoute','PentaWire','PentaBridge','PentaGreen',true,true,true,true,true,jsonb_build_object('version','2.0.0','canonical_registry','runtime/penta-provider-control-plane/providers.json','typed_runtime','integration_control.stripe_os_provider_operation_v2','operator_mcp','https://mcp.stripe.com','mcp_auth','OAuth or restricted key outside source','variants',jsonb_build_array('ct.adapter.stripe.mcp.v1','ct.adapter.stripe.runtime.v1','ct.adapter.stripe.webhook.v3','ct.adapter.stripe.catalog-mirror.v2'),'factory_clock_active',false,'no_secret_projection',true))
on conflict(adapter_key) do update set lifecycle_state=excluded.lifecycle_state,supports_read=excluded.supports_read,supports_write=excluded.supports_write,supports_webhook=excluded.supports_webhook,supports_factory=excluded.supports_factory,no_secret_projection=true,metadata=integration_control.stripe_os_adapter_registry_v1.metadata||excluded.metadata,updated_at=clock_timestamp();

update integration_control.stripe_os_adapter_registry_v1
set lifecycle_state=case adapter_key when 'ct.adapter.stripe.mcp.v1' then 'active_operator_oauth' when 'ct.adapter.stripe.runtime.v1' then 'active_typed_catalog_factory_paused' when 'ct.adapter.stripe.webhook.v3' then 'degraded_topology' when 'ct.adapter.stripe.catalog-mirror.v2' then 'active_with_reconciliation_lag' else lifecycle_state end,
    metadata=metadata||jsonb_build_object('canonical_adapter','ct.adapter.stripe.v1','variant_not_independent_authority',true,'truth_reconciled_at',clock_timestamp()),updated_at=clock_timestamp()
where adapter_key in ('ct.adapter.stripe.mcp.v1','ct.adapter.stripe.runtime.v1','ct.adapter.stripe.webhook.v3','ct.adapter.stripe.catalog-mirror.v2');

update integration_control.stripe_os_accounts_v1
set capabilities=jsonb_build_object(
  'acss_debit_payments','active','affirm_payments','active','afterpay_clearpay_payments','active','amazon_pay_payments','active',
  'bancontact_payments','active','blik_payments','active','card_payments','active','cashapp_payments','active','eps_payments','active',
  'giropay_payments','active','ideal_payments','active','klarna_payments','active','kr_card_payments','active','link_payments','active',
  'multibanco_payments','active','p24_payments','active','sepa_bank_transfer_payments','active','sepa_debit_payments','active',
  'sofort_payments','active','transfers','active','us_bank_account_ach_payments','active','us_bank_transfer_payments','active'
),metadata=metadata||jsonb_build_object('active_capability_count',22,'payout_account_flag',true,'payout_rail_state','HOLD_DEFAULT_BANK_ERRORED','live_audit_at',clock_timestamp()),observed_at=clock_timestamp(),updated_at=clock_timestamp()
where account_role='COMMERCE_PRIMARY';

update integration_control.pentagreen_stripe_mesh_v3
set mesh_state='RUNTIME_REPAIRED_FACTORY_PAUSED_GOVERNED_GATES',
    provider_write_state='TYPED_CATALOG_ADAPTER_READY_FACTORY_CLOCK_PAUSED',
    money_movement_state='D3_SEPARATELY_GATED_PAYOUT_RAIL_HOLD',
    capability_registry_ref='integration_control.stripe_os_capabilities_v1',
    adapter_registry_ref='integration_control.stripe_os_adapter_registry_v1',
    metadata=metadata||jsonb_build_object(
      'typed_adapter','integration_control.stripe_os_provider_operation_v2',
      'canonical_adapter','ct.adapter.stripe.v1',
      'capability_adoption_registry','integration_control.stripe_os_capability_adoption_v2',
      'provider_operation_receipts','integration_control.stripe_os_provider_operation_receipts_v2',
      'factory_clock_active',false,'factory_ready_candidates',0,'profiles_total',1042,
      'product_types_enabled_for_sale',0,'legal_tax_profiles_ready',0,
      'provider_inventory',jsonb_build_object('products',459,'prices',484,'payment_links',48,'webhook_endpoints',16),
      'mirror_inventory',jsonb_build_object('products',456,'prices',478,'payment_links',48,'webhook_endpoints',15),
      'payout_rail_state','HOLD_DEFAULT_BANK_ERRORED','truth_reconciled_at',clock_timestamp()
    ),updated_at=clock_timestamp()
where binding_id='ct.binding.pentagreen-stripe-mesh.v3';

update integration_control.crownthrive_partner_registry_v1
set relationship_state='active_integrated_with_holds',
    capability_refs=(select array_agg(capability_key order by capability_key) from integration_control.stripe_os_capabilities_v1),
    metadata=metadata||jsonb_build_object('canonical_adapter','ct.adapter.stripe.v1','mcp_operator_available',true,'mcp_runtime_url','https://mcp.stripe.com','factory_clock_active',false,'factory_ready_candidates',0,'payout_rail_state','HOLD_DEFAULT_BANK_ERRORED','partner_sheet_exists',true,'truth_reconciled_at',clock_timestamp()),updated_at=clock_timestamp()
where partner_key='ct.partner.stripe';

alter view integration_control.pentagreen_stripe_catalog_bridge_v1 set (security_invoker=true);
revoke all on integration_control.pentagreen_stripe_catalog_bridge_v1 from public,anon,authenticated;
grant select on integration_control.pentagreen_stripe_catalog_bridge_v1 to service_role;

create or replace function integration_control.thriveevergreen_commerce_mesh_cycle_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog'
as $fn$
declare
  v_id uuid:=gen_random_uuid(); a jsonb; b jsonb; c jsonb; d jsonb; e jsonb; f jsonb; s jsonb; v_state text;
begin
  if not pg_try_advisory_xact_lock(hashtextextended('ct.pentagreen.commerce-mesh-cycle.v1',0)) then return jsonb_build_object('state','SKIPPED_LOCKED','money_movement',false,'observed_at',clock_timestamp()); end if;
  insert into integration_control.thriveevergreen_mesh_cycle_receipts_v1(cycle_id,authority_ref) values(v_id,'founder_directive_stripe_os_monetization_2026-08-31');
  a:=integration_control.thriveevergreen_mesh_seed_catalog_v1();
  b:=integration_control.thriveevergreen_mesh_reconcile_routes_v1();
  c:=integration_control.thriveevergreen_mesh_enqueue_gaps_v1();
  d:=integration_control.thriveevergreen_mesh_reconcile_replicas_v1();
  e:=integration_control.pentagreen_stripe_autowire_v1(10);
  f:=integration_control.pentagreen_stripe_commerce_binder_tick_v1(1);
  v_state:=case when e->>'state'='IDLE' and f->>'state'='IDLE' then 'idle' when e->>'state' in ('DEGRADED','HOLD') or f->>'state' in ('DEGRADED','HOLD_NO_ACTIVE_REPLICA') then 'degraded' else 'pass' end;
  s:=public.thriveevergreen_commerce_mesh_status_v1()||jsonb_build_object('stripe_autowire',e,'stripe_commerce_binder',f,'stripe_mesh','ct.binding.pentagreen-stripe-mesh.v3','factory_clock_active',false);
  update integration_control.thriveevergreen_mesh_cycle_receipts_v1 set cycle_completed_at=clock_timestamp(),seed_result=a,route_result=b,queue_result=c,replica_result=d,status_snapshot=s,result_state=v_state where cycle_id=v_id;
  return jsonb_build_object('cycle_id',v_id,'state',upper(v_state),'seed',a,'routes',b,'queue',c,'replicas',d,'stripe_autowire',e,'stripe_commerce_binder',f,'status',s,'money_movement',false);
exception when others then
  update integration_control.thriveevergreen_mesh_cycle_receipts_v1 set cycle_completed_at=clock_timestamp(),result_state='error',status_snapshot=jsonb_build_object('error_sha256',encode(extensions.digest(convert_to(coalesce(sqlerrm,''),'UTF8'),'sha256'),'hex'),'sqlstate',sqlstate) where cycle_id=v_id;
  raise;
end
$fn$;

revoke all on function integration_control.thriveevergreen_commerce_mesh_cycle_v1() from public,anon,authenticated;
grant execute on function integration_control.thriveevergreen_commerce_mesh_cycle_v1() to service_role;

create or replace function integration_control.stripe_os_runtime_readiness_v2()
returns jsonb
language sql
security definer
set search_path to 'pg_catalog'
as $fn$
select jsonb_build_object(
  'state',(select mesh_state from integration_control.pentagreen_stripe_mesh_v3 where binding_id='ct.binding.pentagreen-stripe-mesh.v3'),
  'factory_clock_active',coalesce((select active from integration_control.scheduler_desired_jobs_v2 where jobname='ct-pentagreen-commerce-mesh-cycle-v1'),false),
  'live_clock_rows',(select count(*) from cron.job where jobname='ct-pentagreen-commerce-mesh-cycle-v1'),
  'typed_adapter',to_regprocedure('integration_control.stripe_os_provider_operation_v2(uuid,text,text,jsonb)')::text,
  'provider_adapter_api_roles',(select coalesce(jsonb_agg(jsonb_build_object('function',routine_name,'grantee',grantee)),'[]'::jsonb) from information_schema.routine_privileges where specific_schema='integration_control' and routine_name in ('stripe_os_provider_request_v1','stripe_os_provider_operation_v2') and grantee<>'postgres'),
  'factory_ready_candidates',(select count(*) from integration_control.pentagreen_mesh_product_profiles_v1 p join developer_commerce.product_type_registry pt on pt.product_type=p.product_type join developer_commerce.tax_profile_registry tr on tr.tax_profile_code=pt.default_tax_profile_code where pt.enabled_for_sale=true and tr.stripe_code_state='provider_code_verified' and lower(coalesce(tr.legal_taxability_state,'')) in ('ready','verified','approved','certified','taxable_verified','not_taxable_verified') and lower(coalesce(p.rights_state,'')) in ('ready','verified','approved','certified') and lower(coalesce(p.fulfillment_state,'')) in ('ready','verified','approved','certified') and lower(coalesce(p.quality_state,'')) in ('ready','verified','approved','certified') and lower(coalesce(p.route_state,'')) in ('ready','verified','approved','certified') and lower(coalesce(p.custody_state,'')) in ('ready','verified','approved','certified') and lower(coalesce(p.docs_state,'')) in ('ready','verified','approved','certified') and lower(coalesce(p.metadata->>'tax_behavior','')) in ('inclusive','exclusive') and nullif(p.metadata->>'stripe_entitlement_handler_ref','') is not null and nullif(p.metadata->>'stripe_webhook_binding_key','') is not null),
  'queued_requests',(select count(*) from integration_control.pentagreen_stripe_monetization_requests_v1 where request_state='queued'),
  'provider_receipts',(select count(*) from integration_control.stripe_os_provider_operation_receipts_v2),
  'payout_rail_state','HOLD_DEFAULT_BANK_ERRORED',
  'money_movement_separately_gated',true,'no_self_approval',true,'observed_at',clock_timestamp()
)
$fn$;

revoke all on function integration_control.stripe_os_runtime_readiness_v2() from public,anon,authenticated;
grant execute on function integration_control.stripe_os_runtime_readiness_v2() to service_role;
