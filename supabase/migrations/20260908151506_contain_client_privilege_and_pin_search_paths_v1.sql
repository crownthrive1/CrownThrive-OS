-- CrownThrive OS: contain client privilege escalation without relaxing RLS.
-- Preflight: 2026-09-08T15:04:57Z, ThriveBase tzajnzshmtzjenqulehq.
-- This migration is intentionally allowlist-based for existing functions.

select pg_advisory_xact_lock(hashtextextended('ct:security:client-privilege-containment:v1', 0));

create table if not exists integration_control.security_hardening_snapshots_v1 (
  change_key text not null,
  object_kind text not null,
  object_identity text not null,
  owner_name text,
  acl_before text,
  settings_before jsonb,
  definition_hash_md5 text,
  captured_at timestamptz not null default clock_timestamp(),
  primary key (change_key, object_kind, object_identity)
);

alter table integration_control.security_hardening_snapshots_v1 enable row level security;
alter table integration_control.security_hardening_snapshots_v1 force row level security;
revoke all on table integration_control.security_hardening_snapshots_v1 from public, anon, authenticated;
grant select, insert, update, delete on table integration_control.security_hardening_snapshots_v1 to service_role;

do $policy$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'integration_control'
      and tablename = 'security_hardening_snapshots_v1'
      and policyname = 'security_hardening_snapshots_service_role_v1'
  ) then
    create policy security_hardening_snapshots_service_role_v1
      on integration_control.security_hardening_snapshots_v1
      for all to service_role
      using (true) with check (true);
  end if;
end
$policy$;

create temporary table ct_security_function_targets_v1 (
  function_identity text primary key,
  action text not null check (action in ('client_revoke', 'anon_revoke', 'pin_search_path'))
) on commit drop;

insert into ct_security_function_targets_v1(function_identity, action) values
  ('public.app_factory_android_canary_upsert(jsonb)', 'client_revoke'),
  ('public.app_factory_certify_release(text)', 'client_revoke'),
  ('public.app_factory_closeout_gate_upsert(text,text,text,jsonb)', 'client_revoke'),
  ('public.app_factory_collect_edge_responses(text)', 'client_revoke'),
  ('public.app_factory_recertify_after_root_route(text)', 'client_revoke'),
  ('public.app_factory_recertify_v1_2(text)', 'client_revoke'),
  ('public.go_flipbooks_claim_execution_ticket_v1(text,text,text)', 'client_revoke'),
  ('public.go_flipbooks_playbook_factory_300_delivery_blob_v1(text,text)', 'client_revoke'),
  ('public.go_flipbooks_pressure_books_wave_002_claim_v1(integer,integer)', 'client_revoke'),
  ('public.go_flipbooks_pressure_books_wave_002_fail_v1(integer,text)', 'client_revoke'),
  ('public.go_flipbooks_pressure_books_wave_002_reset_stale_v1()', 'client_revoke'),
  ('public.go_flipbooks_sync_authoritative_marketplace_v1()', 'client_revoke'),
  ('public.penta_mail_apply_persona_html_v1()', 'client_revoke'),
  ('public.thrivebase_sheet_mirror_record_folder_v1(text,text,text,jsonb)', 'client_revoke'),
  ('public.cos_v1_convergence_cycle_v4()', 'client_revoke'),
  ('public.cos_v1_convergence_cycle_v5()', 'client_revoke'),
  ('public.go_flipbooks_request_source_export_v1(text)', 'client_revoke'),
  ('public.google_api_keys_readback_invoke_v1(text,text)', 'client_revoke'),
  ('public.google_cloud_readback_invoke_v1(text,text)', 'client_revoke'),
  ('public.locticians_editorial_orchestration_tick_v1()', 'client_revoke'),
  ('public.oc_temp_runner_dispatch(text,text,text)', 'client_revoke'),
  ('public.oc_temp_segment5_dispatch()', 'client_revoke'),
  ('public.operation_clean_audio_wave_invoke_v3(text,text,text,integer,integer)', 'client_revoke'),
  ('public.operation_clean_audio_wave_qc_segmented_v4(text)', 'client_revoke'),
  ('public.operation_clean_duplicate_disposition_probe_invoke_v1()', 'client_revoke'),
  ('public.operation_clean_finalize_protection_v1(text,text)', 'client_revoke'),
  ('public.operation_clean_google_ledger_inspect_v1(text)', 'client_revoke'),
  ('public.operation_clean_mark_custody_v1(text,text,text,text,text,jsonb)', 'client_revoke'),
  ('public.operation_clean_provider_probe_invoke_v1()', 'client_revoke'),
  ('public.operation_clean_record_duplicate_disposition_v1(text,text,text,text,text,text,jsonb)', 'client_revoke'),
  ('public.operation_clean_recover_cohort2_db_v1()', 'client_revoke'),
  ('public.penta_factory_tomorrow_prestage_v1()', 'client_revoke'),
  ('public.penta_release_packet_consumer_v1(integer,uuid)', 'client_revoke'),
  ('public.app_factory_android_canary_reconcile()', 'client_revoke'),
  ('public.app_factory_android_canary_status_sync()', 'client_revoke'),
  ('public.app_factory_android_canary_sync()', 'client_revoke'),
  ('public.app_factory_android_sdk_canary_reconcile()', 'client_revoke'),
  ('public.app_factory_github_canary_reconcile()', 'client_revoke'),
  ('public.app_factory_github_canary_retry()', 'client_revoke'),
  ('public.app_factory_https_probe_sync()', 'client_revoke'),
  ('public.app_factory_provider_finalize_sync()', 'client_revoke'),
  ('public.app_factory_public_android_canary_reconcile()', 'client_revoke'),
  ('public.penta_mail_executive_send_v2(text,text,text,text,text,jsonb,text,text,text,text,text)', 'client_revoke'),
  ('public.penta_governance_cursor_emergency_release_v1(text,text)', 'client_revoke'),
  ('public.pentachat_dail_readback_v1(text,text)', 'client_revoke'),
  ('public.locticians_bd_route_decision_v3(text,text,boolean)', 'client_revoke'),
  ('public.deal_ready_repair_finalize_v2(uuid,uuid,text,text,text,text,text,jsonb,jsonb,jsonb)', 'client_revoke'),
  ('public.pentapersonas_is_workspace_member_v1(uuid,text[])', 'anon_revoke'),
  ('crm.penta_brand_email_thumbnail_inject_v1(text,jsonb,text)', 'pin_search_path'),
  ('crm.penta_brand_recipient_html_sanitize_v1(text)', 'pin_search_path'),
  ('gretna.calculate_listing_fee(text,text,boolean,boolean,boolean,integer)', 'pin_search_path'),
  ('gretna.marketplace_split(bigint,integer,integer)', 'pin_search_path'),
  ('gretna.resolve_marketplace_fees(text)', 'pin_search_path'),
  ('gretna.seller_is_eligible(uuid)', 'pin_search_path'),
  ('integration_control.locticians_bd_image_import_url_v2(text)', 'pin_search_path'),
  ('integration_control.locticians_bd_infer_field_role_v1(text)', 'pin_search_path'),
  ('integration_control.locticians_bd_normalize_payload_v1(jsonb,text)', 'pin_search_path'),
  ('integration_control.locticians_content_type_field_matches_v2(text,text,text)', 'pin_search_path'),
  ('integration_control.locticians_content_type_test_value_v2(text,text,text,text)', 'pin_search_path'),
  ('integration_control.locticians_editorial_normalize_csv_v1(text)', 'pin_search_path'),
  ('integration_control.locticians_evidence_item_pass_v3(jsonb,text)', 'pin_search_path'),
  ('integration_control.locticians_html_escape_v1(text)', 'pin_search_path'),
  ('integration_control.normalize_commerce_name_v2(text)', 'pin_search_path'),
  ('integration_control.penta_ads_dynamic_floor_v1(numeric,numeric,numeric,numeric,numeric,numeric,numeric,numeric)', 'pin_search_path'),
  ('integration_control.penta_assignment_immutable_v1()', 'pin_search_path'),
  ('integration_control.penta_authority_rank_v2(text)', 'pin_search_path'),
  ('integration_control.penta_brand_brand_key_v1(text)', 'pin_search_path'),
  ('integration_control.penta_brand_role_archetype_v1(text)', 'pin_search_path'),
  ('integration_control.penta_factory_canary_output_kind_v1(text,text)', 'pin_search_path'),
  ('integration_control.penta_government_slug_v1(text)', 'pin_search_path'),
  ('integration_control.penta_government_subject_ref_v1(text,text)', 'pin_search_path'),
  ('integration_control.pentas_risk_rank_v2(text)', 'pin_search_path'),
  ('penta_pm.pr_roles_for_v1(text,text,text)', 'pin_search_path'),
  ('penta_self.hard_repair_json_bool_v1(jsonb,text,boolean)', 'pin_search_path'),
  ('penta_self.hard_repair_redact_json_v1(jsonb,boolean)', 'pin_search_path'),
  ('penta_self.hard_repair_risk_rank_v1(text)', 'pin_search_path'),
  ('penta_self.remediation_lane_v1(text,text)', 'pin_search_path'),
  ('pentagovernance.evaluate_ratification_v1(text)', 'pin_search_path'),
  ('pentagovernance.guard_release_v1(text,text,text,text,text)', 'pin_search_path'),
  ('pentas.authority_rank_v2(text)', 'pin_search_path'),
  ('pentas.block_receipt_mutation_v2()', 'pin_search_path'),
  ('pentatime.cron_field_matches_v2(text,integer,integer,integer)', 'pin_search_path'),
  ('pentatime.cron_minute_matches_v1(text,integer)', 'pin_search_path'),
  ('pentatime.cron_offset_field_v1(integer,integer)', 'pin_search_path'),
  ('pentatime.cron_schedule_matches_v2(text,timestamp with time zone)', 'pin_search_path'),
  ('pentatime.cron_uniform_interval_v1(text)', 'pin_search_path'),
  ('public.cos_storefront_events_immutable()', 'pin_search_path'),
  ('public.cos_touch_updated_at()', 'pin_search_path'),
  ('public.penta_mail_traffic_class_v2(text,jsonb)', 'pin_search_path'),
  ('stripe.check_rate_limit(text,integer,integer)', 'pin_search_path'),
  ('stripe.set_updated_at()', 'pin_search_path'),
  ('stripe.set_updated_at_metadata()', 'pin_search_path');

do $targets$
declare
  v_missing text;
begin
  select string_agg(function_identity, ', ' order by function_identity)
    into v_missing
  from ct_security_function_targets_v1
  where to_regprocedure(function_identity) is null;

  if v_missing is not null then
    raise exception 'security hardening target missing: %', v_missing;
  end if;
end
$targets$;

insert into integration_control.security_hardening_snapshots_v1(
  change_key, object_kind, object_identity, owner_name, acl_before,
  settings_before, definition_hash_md5
)
select
  '20260908_client_privilege_containment_v1',
  'function',
  t.function_identity,
  p.proowner::regrole::text,
  p.proacl::text,
  jsonb_build_object('proconfig', p.proconfig, 'action', t.action),
  md5(pg_get_functiondef(p.oid))
from ct_security_function_targets_v1 t
join pg_proc p on p.oid = to_regprocedure(t.function_identity)
on conflict do nothing;

insert into integration_control.security_hardening_snapshots_v1(
  change_key, object_kind, object_identity, owner_name, acl_before,
  settings_before, definition_hash_md5
)
select
  '20260908_client_privilege_containment_v1',
  'default_acl',
  concat(d.defaclrole::regrole::text, ':', coalesce(n.nspname, '*global*'), ':', d.defaclobjtype),
  d.defaclrole::regrole::text,
  d.defaclacl::text,
  jsonb_build_object('schema', coalesce(n.nspname, '*global*'), 'object_type', d.defaclobjtype),
  md5(coalesce(d.defaclacl::text, ''))
from pg_default_acl d
left join pg_namespace n on n.oid = d.defaclnamespace
where d.defaclrole = 'postgres'::regrole
  and (n.nspname = 'public' or n.nspname is null)
on conflict do nothing;

-- Remove the built-in global PUBLIC execute default, then remove named client
-- defaults in public. Intended RPCs must be granted explicitly in migrations.
alter default privileges for role postgres
  revoke execute on functions from public;
alter default privileges for role postgres in schema public
  revoke execute on functions from public, anon, authenticated;
alter default privileges for role postgres in schema public
  grant execute on functions to service_role;

-- Future public relations are private until their migration explicitly grants
-- the minimum Data API operations. Existing REST CRUD is not changed here.
alter default privileges for role postgres in schema public
  revoke all privileges on tables from public, anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all privileges on sequences from public, anon, authenticated;

do $internal_defaults$
declare
  v_schema text;
begin
  foreach v_schema in array array[
    'crm', 'pentatime', 'penta_self', 'pentamocracy', 'penta_pm',
    'chlom_wallet', 'penta_treasury', 'penta_task_runtime', 'penta_os20',
    'penta_discovery', 'penta_security', 'public_bridge', 'thrivebeacons'
  ] loop
    if to_regnamespace(v_schema) is not null then
      execute format(
        'alter default privileges for role postgres in schema %I revoke execute on functions from public, anon, authenticated',
        v_schema
      );
      execute format(
        'alter default privileges for role postgres in schema %I grant execute on functions to service_role',
        v_schema
      );
    end if;
  end loop;
end
$internal_defaults$;

-- RLS does not govern these table privileges. REST CRUD grants are preserved.
revoke truncate, references, trigger, maintain on all tables in schema public
  from public, anon, authenticated;

do $function_acl$
declare
  v record;
begin
  for v in
    select t.function_identity, t.action, p.oid
    from ct_security_function_targets_v1 t
    join pg_proc p on p.oid = to_regprocedure(t.function_identity)
    where t.action in ('client_revoke', 'anon_revoke')
    order by t.function_identity
  loop
    if v.action = 'client_revoke' then
      execute format('revoke execute on function %s from public, anon, authenticated', v.oid::regprocedure);
      execute format('grant execute on function %s to service_role', v.oid::regprocedure);
    else
      execute format('revoke execute on function %s from public, anon', v.oid::regprocedure);
      execute format('grant execute on function %s to authenticated, service_role', v.oid::regprocedure);
    end if;
  end loop;
end
$function_acl$;

do $search_path$
declare
  v record;
begin
  for v in
    select t.function_identity, p.oid, n.nspname
    from ct_security_function_targets_v1 t
    join pg_proc p on p.oid = to_regprocedure(t.function_identity)
    join pg_namespace n on n.oid = p.pronamespace
    where t.action = 'pin_search_path'
    order by t.function_identity
  loop
    execute format(
      'alter function %s set search_path to pg_catalog, %I, public, extensions',
      v.oid::regprocedure,
      v.nspname
    );
  end loop;
end
$search_path$;

create temporary table ct_security_view_targets_v1(view_identity text primary key) on commit drop;
insert into ct_security_view_targets_v1(view_identity) values
  ('public.penta_ads_ad_summary_v1'),
  ('public.penta_ads_blueprints_v1'),
  ('public.penta_ads_bonus_programs_v1'),
  ('public.penta_ads_campaign_summary_v1'),
  ('public.penta_ads_creative_capabilities_v1'),
  ('public.penta_ads_credential_lanes_v2'),
  ('public.penta_ads_credit_balances_v1'),
  ('public.penta_ads_finance_reconciliation_v1'),
  ('public.penta_ads_inventory_v1'),
  ('public.penta_ads_manager_health_v2'),
  ('public.penta_ads_programmatic_inventory_v1'),
  ('public.penta_ads_publisher_readbacks_v2'),
  ('public.penta_ads_publisher_zone_stats_v2'),
  ('public.penta_ads_release_receipts_v1'),
  ('public.penta_ads_release_receipts_v2'),
  ('public.penta_ads_zone_factory_status_v1'),
  ('public.penta_ads_zone_metrics_latest_v1'),
  ('public.penta_ads_zone_metrics_latest_v2'),
  ('public.penta_ads_zone_pricing_v1'),
  ('public.penta_docs_hard_repair_reports_v1'),
  ('public.penta_production_census_public_v1');

do $views$
declare
  v record;
  v_missing text;
begin
  select string_agg(view_identity, ', ' order by view_identity)
    into v_missing
  from ct_security_view_targets_v1
  where to_regclass(view_identity) is null;
  if v_missing is not null then
    raise exception 'security hardening view target missing: %', v_missing;
  end if;

  for v in
    select t.view_identity, c.oid, c.relowner, c.relacl, c.reloptions
    from ct_security_view_targets_v1 t
    join pg_class c on c.oid = to_regclass(t.view_identity)
    order by t.view_identity
  loop
    insert into integration_control.security_hardening_snapshots_v1(
      change_key, object_kind, object_identity, owner_name, acl_before,
      settings_before, definition_hash_md5
    ) values (
      '20260908_client_privilege_containment_v1',
      'view',
      v.view_identity,
      v.relowner::regrole::text,
      v.relacl::text,
      jsonb_build_object('reloptions', v.reloptions),
      md5(pg_get_viewdef(v.oid, true))
    ) on conflict do nothing;

    -- These views read private relations that do not grant direct SELECT to
    -- service_role. Converting them to invoker mode would create an outage.
    -- Contain the surface by ACL and keep the definer behavior service-only.
    execute format('revoke all on table %s from public, anon, authenticated', v.oid::regclass);
    execute format('grant select on table %s to service_role', v.oid::regclass);
  end loop;
end
$views$;

do $verify$
declare
  v_bad integer;
begin
  select count(*) into v_bad
  from ct_security_function_targets_v1 t
  join pg_proc p on p.oid = to_regprocedure(t.function_identity)
  where t.action = 'client_revoke'
    and (
      has_function_privilege('anon', p.oid, 'execute')
      or has_function_privilege('authenticated', p.oid, 'execute')
      or not has_function_privilege('service_role', p.oid, 'execute')
    );
  if v_bad <> 0 then raise exception 'client function ACL verification failed: %', v_bad; end if;

  select count(*) into v_bad
  from ct_security_function_targets_v1 t
  join pg_proc p on p.oid = to_regprocedure(t.function_identity)
  where t.action = 'pin_search_path'
    and not exists (
      select 1 from unnest(coalesce(p.proconfig, '{}'::text[])) c
      where c like 'search_path=%'
    );
  if v_bad <> 0 then raise exception 'function search_path verification failed: %', v_bad; end if;

  select count(*) into v_bad
  from ct_security_view_targets_v1 t
  join pg_class c on c.oid = to_regclass(t.view_identity)
  where has_table_privilege('anon', c.oid, 'select')
     or has_table_privilege('authenticated', c.oid, 'select')
     or not has_table_privilege('service_role', c.oid, 'select');
  if v_bad <> 0 then raise exception 'view containment verification failed: %', v_bad; end if;

  select count(*) into v_bad
  from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind in ('r', 'p')
    and (
      has_table_privilege('anon', c.oid, 'truncate')
      or has_table_privilege('anon', c.oid, 'references')
      or has_table_privilege('anon', c.oid, 'trigger')
      or has_table_privilege('anon', c.oid, 'maintain')
      or has_table_privilege('authenticated', c.oid, 'truncate')
      or has_table_privilege('authenticated', c.oid, 'references')
      or has_table_privilege('authenticated', c.oid, 'trigger')
      or has_table_privilege('authenticated', c.oid, 'maintain')
    );
  if v_bad <> 0 then raise exception 'non-Data-API table privilege verification failed: %', v_bad; end if;
end
$verify$;

notify pgrst, 'reload schema';
