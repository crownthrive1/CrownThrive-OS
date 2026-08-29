-- CrownThrive OS / Locticians Digital Product Syndication v1
--
-- The executable runtime is already installed and provider-verified in
-- ThriveBase. This source-controlled migration refuses convergence when the
-- Digital Products provider binding, ten-listing launch batch, Stripe
-- authority, nurture fabric, agent mesh, or canonical clocks drift.

begin;

do $guard$
declare
  v_sources integer;
  v_listings integer;
  v_provider_bound integer;
  v_verified integer;
  v_hash_matches integer;
  v_required_readback integer;
  v_held integer;
  v_nurture integer;
  v_jobs integer;
  v_agents integer;
  v_capabilities integer;
  v_playbooks integer;
  v_snapshot_runs integer;
  v_snapshot_records integer;
  v_snapshot_active integer;
  v_candidates integer;
  v_blocked integer;
  v_status jsonb;
begin
  if to_regclass('integration_control.locticians_digital_product_policy_v1') is null
     or to_regclass('integration_control.locticians_digital_product_sources_v1') is null
     or to_regclass('integration_control.locticians_digital_product_listings_v1') is null
     or to_regclass('integration_control.locticians_digital_product_nurture_v1') is null
     or to_regclass('integration_control.stripe_payment_link_sync_runs_v4') is null
     or to_regclass('integration_control.stripe_payment_link_inventory_v4') is null
     or to_regclass('integration_control.locticians_digital_product_mesh_candidates_v1') is null then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_CONTROL_PLANE_INCOMPLETE';
  end if;

  if to_regprocedure('integration_control.locticians_digital_product_checkout_verify_v1(uuid,boolean)') is null
     or to_regprocedure('public.locticians_digital_product_checkout_verify_tick_v1(integer,boolean)') is null
     or to_regprocedure('public.locticians_digital_product_schedule_batch_v1(date,integer)') is null
     or to_regprocedure('public.locticians_digital_product_audit_tick_v1(integer)') is null
     or to_regprocedure('public.locticians_digital_product_publish_tick_v1(integer)') is null
     or to_regprocedure('public.locticians_digital_product_nurture_tick_v1(integer)') is null
     or to_regprocedure('public.locticians_digital_product_orchestration_tick_v1()') is null
     or to_regprocedure('public.locticians_digital_product_status_v1()') is null
     or to_regprocedure('integration_control.locticians_digital_product_stripe_snapshot_reconcile_v1()') is null
     or to_regprocedure('integration_control.stripe_payment_link_sync_dispatch_v4()') is null
     or to_regprocedure('integration_control.locticians_universal_provider_create_or_reconcile_v4(uuid)') is null
     or to_regprocedure('integration_control.locticians_universal_reverify_one_v4(uuid)') is null then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_RUNTIME_INCOMPLETE';
  end if;

  if not exists(
    select 1
    from integration_control.locticians_digital_product_policy_v1
    where policy_key='ct.locticians.digital-products.v1'
      and enabled
      and daily_listing_limit=10
      and publication_start_hour_et=8
      and publication_end_hour_et=17
      and timezone_name='America/New_York'
      and homepage_features_per_day=2
      and checkout_reverify_hours=6
      and listing_refresh_days=30
      and nurture_after_hours=array[24,168,336,720]::integer[]
      and payment_authority='external_stripe_authoritative'
      and bd_native_payment_state='documented_ui_only_api_unverified'
      and bd_form_payment_state='checkout_form_governed_no_parallel_authority'
      and auto_enqueue and auto_audit and auto_dispatch
  ) then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_POLICY_DRIFT';
  end if;

  if not exists(
    select 1
    from integration_control.locticians_content_type_registry_v1 t
    join integration_control.locticians_content_type_release_contract_v2 c using(content_type_key)
    where t.surface_key='digital_products'
      and t.provider_data_id=73
      and t.provider_data_type=4
      and t.state='production_active'
      and t.production_contract_state='production_ready'
      and t.provider_catalog_state='verified'
      and t.provider_schema_state='verified'
      and c.production_state='production_ready'
      and c.required_provider_fields @> array['post_url','post_promo']::text[]
      and c.required_evidence_keys @> array[
        'verified_product_entitlement_and_checkout','checkout_readback'
      ]::text[]
      and c.minimum_media_assets=1
      and c.requires_primary_media_url
      and c.requires_source_url
      and c.requires_checkout_readback
  ) then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_PROVIDER_CONTRACT_DRIFT';
  end if;

  select count(*) into v_sources
  from integration_control.locticians_digital_product_sources_v1
  where source_state='listed'
    and checkout_state='verified'
    and rights_state='verified'
    and entitlement_state in ('verified','manual_verified')
    and payment_mode='external_stripe'
    and stripe_account_id='acct_1MENDxCJFUeGxc8S'
    and stripe_payment_link_id~'^plink_'
    and stripe_product_id~'^prod_'
    and stripe_price_id~'^price_'
    and checkout_url~'^https://';
  if v_sources<>10 then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_VERIFIED_SOURCE_COUNT=%',v_sources;
  end if;

  select count(*),
         count(*) filter(where provider_post_id is not null),
         count(*) filter(where state in ('scheduled','live_verified','nurture_active') and provider_post_id is not null),
         count(*) filter(where state in ('held','quarantined'))
  into v_listings,v_provider_bound,v_verified,v_held
  from integration_control.locticians_digital_product_listings_v1
  where batch_ref='locticians.digital-products.20260829.v1';

  if v_listings<>10 or v_provider_bound<>10 or v_verified<>10 or v_held<>0 then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_LISTING_STATE listings=% provider_bound=% verified=% held=%',
      v_listings,v_provider_bound,v_verified,v_held;
  end if;

  if not exists(
    select 1
    from integration_control.locticians_digital_product_listings_v1
    group by (scheduled_for at time zone 'America/New_York')::date
    having count(*)=10
       and min((scheduled_for at time zone 'America/New_York')::time)=time '08:00:00'
       and max((scheduled_for at time zone 'America/New_York')::time)=time '17:00:00'
  ) then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_DAILY_SCHEDULE_DRIFT';
  end if;

  if (select count(*) from integration_control.locticians_digital_product_listings_v1
      where batch_ref='locticians.digital-products.20260829.v1' and feature_homepage)<>2 then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_HOMEPAGE_FEATURE_COUNT_DRIFT';
  end if;

  select count(*) into v_hash_matches
  from integration_control.locticians_digital_product_listings_v1 l
  join integration_control.locticians_article_schedule_v1 s on s.schedule_id=l.schedule_id
  join integration_control.locticians_editorial_package_v1 p on p.package_id=l.package_id
  where l.batch_ref='locticians.digital-products.20260829.v1'
    and s.provider_user_id=5 and s.provider_data_id=73 and s.provider_data_type=4
    and s.enrichment_state='verified' and s.release_contract_state='pass'
    and s.provider_content_sha256=s.content_sha256
    and s.provider_reverification_state='pass'
    and s.image_asset_id is not null and s.image_present and s.image_rights_state='verified'
    and p.audit_decision='approve' and p.release_contract_state='pass'
    and p.state in ('scheduled','published');
  if v_hash_matches<>10 then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_EXACT_READBACK_COUNT=%',v_hash_matches;
  end if;

  select count(*) into v_required_readback
  from integration_control.locticians_digital_product_listings_v1 l
  join integration_control.locticians_article_schedule_v1 s on s.schedule_id=l.schedule_id
  where l.batch_ref='locticians.digital-products.20260829.v1'
    and coalesce((s.provider_required_field_readback#>>'{post_url,pass}')::boolean,false)
    and coalesce((s.provider_required_field_readback#>>'{post_promo,pass}')::boolean,false);
  if v_required_readback<>10 then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_REQUIRED_FIELD_READBACK_COUNT=%',v_required_readback;
  end if;

  if (select array_agg(provider_post_id order by sequence_no)
      from integration_control.locticians_digital_product_listings_v1
      where batch_ref='locticians.digital-products.20260829.v1')
     <>array[4202,4203,4204,4205,4206,4207,4208,4209,4210,4211]::bigint[] then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_PROVIDER_POST_ID_DRIFT';
  end if;

  select count(*) into v_nurture
  from integration_control.locticians_digital_product_nurture_v1;
  if v_nurture<>60 then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_NURTURE_ACTION_COUNT=%',v_nurture;
  end if;

  if exists(
    select listing_id
    from integration_control.locticians_digital_product_nurture_v1
    group by listing_id
    having count(*)<>6
  ) then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_NURTURE_PER_LISTING_DRIFT';
  end if;

  select count(*) into v_snapshot_runs
  from integration_control.stripe_payment_link_sync_runs_v4
  where state='complete'
    and provider_account_id='acct_1MENDxCJFUeGxc8S'
    and payload_sha256='e0025953cc78db5bd64bfc01ce4f0b6f970db1a76526de9cacf8d4a5f0214518';
  if v_snapshot_runs<1 then
    raise exception 'STRIPE_PAYMENT_LINK_COMPLETE_SYNC_MISSING';
  end if;

  select count(*),count(*) filter(where active)
  into v_snapshot_records,v_snapshot_active
  from integration_control.stripe_payment_link_inventory_v4
  where provider_account_id='acct_1MENDxCJFUeGxc8S';
  if v_snapshot_records<>32 or v_snapshot_active<>28 then
    raise exception 'STRIPE_PAYMENT_LINK_SNAPSHOT_COUNTS records=% active=%',
      v_snapshot_records,v_snapshot_active;
  end if;

  select count(*),count(*) filter(where readiness_state='blocked')
  into v_candidates,v_blocked
  from integration_control.locticians_digital_product_mesh_candidates_v1;
  if v_candidates<>1042 or v_blocked<>1042 then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_MESH_CANDIDATE_COUNTS candidates=% blocked=%',
      v_candidates,v_blocked;
  end if;

  select count(*) into v_jobs
  from cron.job
  where active and jobname in (
    'ct-stripe-payment-link-sync-v4',
    'ct-locticians-digital-products-checkout-v1',
    'ct-locticians-digital-products-orchestration-v1',
    'ct-locticians-digital-products-nurture-v1'
  );
  if v_jobs<>4 then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_CANONICAL_JOB_COUNT=%',v_jobs;
  end if;

  select count(*) into v_agents
  from crm.penta_marketer_agents_v2
  where agent_id in (
    'ct.pentamarketer.agent.product-syndicator-v1',
    'ct.pentamarketer.agent.checkout-monitor-v1',
    'ct.pentamarketer.agent.digital-product-nurture-v1',
    'ct.pentamarketer.agent.digital-product-certifier-v1'
  ) and enabled and autonomous and state='active';
  if v_agents<>4 then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_AGENT_COUNT=%',v_agents;
  end if;

  select count(*) into v_capabilities
  from crm.penta_persona_execution_capabilities_v1
  where capability_key like 'locticians.digital_product.%'
    and enabled and certification_state='production';
  if v_capabilities<9 then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_CAPABILITY_COUNT=%',v_capabilities;
  end if;

  select count(*) into v_playbooks
  from crm.penta_persona_execution_playbooks_v1
  where playbook_key like 'ct.playbook.locticians.digital-product.%'
    and enabled and auto_enqueue;
  if v_playbooks<7 then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_PLAYBOOK_COUNT=%',v_playbooks;
  end if;

  v_status:=public.locticians_digital_product_status_v1();
  if v_status->>'state'<>'production_active' then
    raise exception 'LOCTICIANS_DIGITAL_PRODUCT_STATUS=%',v_status->>'state';
  end if;

  if exists(
    select 1
    from integration_control.locticians_digital_product_sources_v1
    where payment_mode='bd_native'
  ) then
    raise exception 'BD_NATIVE_PAYMENT_ACTIVATED_WITHOUT_CERTIFICATION';
  end if;
end
$guard$;

select chlom_runtime.append_dail_event(
  'locticians.digital_products.source_convergence_guard.v1',
  'source_control_convergence',
  'ct.locticians.digital-products.v1',
  jsonb_build_object(
    'manifest','data/penta/locticians-digital-product-syndication.v1.json',
    'provider_binding',jsonb_build_object('user_id',5,'data_id',73,'data_type',4),
    'listing_count',10,
    'provider_post_ids',jsonb_build_array(4202,4203,4204,4205,4206,4207,4208,4209,4210,4211),
    'daily_limit',10,
    'schedule_hours_et','08:00-17:00',
    'nurture_actions',60,
    'stripe_snapshot_records',32,
    'stripe_active_records',28,
    'stripe_snapshot_sha256','e0025953cc78db5bd64bfc01ce4f0b6f970db1a76526de9cacf8d4a5f0214518',
    'mesh_candidates_evaluated',1042,
    'mesh_candidates_blocked',1042,
    'canonical_jobs',4,
    'specialized_agents',4,
    'native_bd_payment_state','documented_ui_only_api_unverified',
    'payment_authority','external_stripe_authoritative',
    'automatic_blind_retry',false,
    'delete_authority','D3_HUMAN_RESERVED',
    'verified_at',clock_timestamp()
  ),
  'PentaProductSyndicator/PentaCheckoutMonitor/PentaProductNurture/PentaDigitalProductCertifier/PentaUniversalPublish/PentaCertify',
  null,
  'PentaCertify',
  '1.0.0',
  'ctcorr:locticians-digital-products-source-v1',
  null,
  'D2_FOUNDER_DIRECTIVE',
  null,
  'internal'
);

commit;
