-- CrownThrive OS: second-pass containment of client-callable SECURITY DEFINER RPCs.
--
-- Forward-only. This migration deliberately changes ACLs only. It does not
-- change RLS enablement, FORCE RLS, policies, function bodies, triggers, cron
-- commands, or extension-owned objects.
--
-- Live preflight captured 2026-09-08 UTC on ThriveBase tzajnzshmtzjenqulehq:
--   anon SECURITY DEFINER effective EXECUTE:             364
--   anon + schema USAGE:                                  95
--   custom anon + schema USAGE:                           86
--   public custom anon + schema USAGE:                    85
--   pgsodium extension-owned anon + schema USAGE:          8
--   supabase_functions platform helper:                    1
--   authenticated SECURITY DEFINER effective EXECUTE:    387
--   authenticated + schema USAGE:                        115
--   custom authenticated + schema USAGE:                 106
--
-- Expected after this migration:
--   anon SECURITY DEFINER effective EXECUTE:             306
--   anon + schema USAGE:                                  37
--   custom anon + schema USAGE:                           28
--   public custom anon + schema USAGE:                    27
--   pgsodium extension-owned anon + schema USAGE:          8
--   supabase_functions platform helper:                    1
--   authenticated SECURITY DEFINER effective EXECUTE:    329
--   authenticated + schema USAGE:                         57
--   custom authenticated + schema USAGE:                  48

begin;

select pg_advisory_xact_lock(
  hashtextextended('ct:security:secdef-client-allowlist-second-batch:v1', 0)
);

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
revoke all on table integration_control.security_hardening_snapshots_v1
  from public, anon, authenticated;
grant select, insert, update, delete
  on table integration_control.security_hardening_snapshots_v1
  to service_role;

do $snapshot_policy$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname = 'integration_control'
      and tablename = 'security_hardening_snapshots_v1'
      and policyname = 'security_hardening_snapshots_service_role_v1'
  ) then
    create policy security_hardening_snapshots_service_role_v1
      on integration_control.security_hardening_snapshots_v1
      for all to service_role
      using (true)
      with check (true);
  end if;
end
$snapshot_policy$;

create temporary table ct_secdef_batch2_targets_v1 (
  function_identity text primary key,
  action text not null check (
    action in (
      'client_revoke',
      'public_allowlist',
      'authenticated_rls_helper',
      'managed_exclusion'
    )
  )
) on commit drop;

-- Fifty-eight custom functions with zero top-level anon calls in
-- pg_stat_statements since its 2026-08-23 reset. None is required to retain a
-- client grant for an RLS policy, trigger, cron job, or invoker dependency.
insert into ct_secdef_batch2_targets_v1(function_identity, action) values
  ('public.app_factory_certify_if_evidenced()', 'client_revoke'),
  ('public.app_factory_provider_public_status(text)', 'client_revoke'),
  ('public.app_factory_publish_production_readback()', 'client_revoke'),
  ('public.go_flipbooks_block_item_delete_v1()', 'client_revoke'),
  ('public.go_flipbooks_build_it_governed_status_v1()', 'client_revoke'),
  ('public.go_flipbooks_coverage_library_status_v1()', 'client_revoke'),
  ('public.go_flipbooks_cpanel_deployment_status_v1()', 'client_revoke'),
  ('public.go_flipbooks_cpanel_installer_bootstrap_v2(text)', 'client_revoke'),
  ('public.go_flipbooks_cpanel_installer_finalize_v2(text,jsonb)', 'client_revoke'),
  ('public.go_flipbooks_playbook_factory_300_private_delivery_status_v1()', 'client_revoke'),
  ('public.go_flipbooks_playbook_factory_300_release_status_v1()', 'client_revoke'),
  ('public.go_flipbooks_playbook_factory_300_worker_blobs_v1(text,jsonb)', 'client_revoke'),
  ('public.go_flipbooks_playbook_factory_300_worker_finalize_v1(text)', 'client_revoke'),
  ('public.go_flipbooks_playbook_factory_300_worker_metadata_v1(text,jsonb)', 'client_revoke'),
  ('public.go_flipbooks_playbook_factory_300_worker_status_v1(text)', 'client_revoke'),
  ('public.go_flipbooks_pressure_books_wave_002_finalize_v1()', 'client_revoke'),
  ('public.go_flipbooks_pressure_books_wave_002_register_v1(integer,jsonb)', 'client_revoke'),
  ('public.go_flipbooks_pressure_books_wave_002_status_v1()', 'client_revoke'),
  ('public.go_flipbooks_source_export_file_v1(uuid,integer)', 'client_revoke'),
  ('public.go_flipbooks_source_export_manifest_v1(uuid)', 'client_revoke'),
  ('public.go_flipbooks_storefront_facets_v1()', 'client_revoke'),
  ('public.go_flipbooks_tier_allocation_status_v1()', 'client_revoke'),
  ('public.locticians_bd_select_warm_credential_v3(text)', 'client_revoke'),
  ('public.locticians_bd_webhook_dispatch_tick_v1(integer)', 'client_revoke'),
  ('public.operation_clean_audio_reconcile_custody_ledger_v1(text,text)', 'client_revoke'),
  ('public.operation_clean_recovery_snapshot_v1()', 'client_revoke'),
  ('public.penta_ads_bd_canary_get_v1(uuid)', 'client_revoke'),
  ('public.penta_ads_bd_canary_start_v1(text,jsonb)', 'client_revoke'),
  ('public.penta_ads_bd_canary_update_v1(uuid,text,text,text,jsonb,jsonb,jsonb,jsonb,text,boolean)', 'client_revoke'),
  ('public.penta_ads_cpanel_runtime_context_v1(bigint)', 'client_revoke'),
  ('public.penta_ads_cpanel_runtime_finalize_v1(bigint,uuid[],text,text,text,jsonb)', 'client_revoke'),
  ('public.penta_ads_vm_whm_context_v1()', 'client_revoke'),
  ('public.penta_all_production_contract_status_v1()', 'client_revoke'),
  ('public.penta_all_production_status_v1()', 'client_revoke'),
  ('public.penta_mail_sensitivity_class_v1(text,text,text,jsonb)', 'client_revoke'),
  ('public.penta_mail_template_route_v1(text,jsonb)', 'client_revoke'),
  ('public.penta_mail_zaza_media_deck_v1(text,integer)', 'client_revoke'),
  ('public.penta_mail_zaza_session_render_v1(text,text,text,text,jsonb)', 'client_revoke'),
  ('public.penta_marketer_newsletter_sender_for_v1(text)', 'client_revoke'),
  ('public.penta_pm_enqueue_remediation_execution_v1(uuid,integer,integer,text,text,text,text,jsonb)', 'client_revoke'),
  ('public.penta_registry_runtime_reference_sweep_v2(integer)', 'client_revoke'),
  ('public.penta_release_footer_v1(text)', 'client_revoke'),
  ('public.penta_remediation_execute_known_v1(uuid)', 'client_revoke'),
  ('public.penta_remediation_execute_known_v2(uuid)', 'client_revoke'),
  ('public.penta_remediation_execute_known_v3(uuid)', 'client_revoke'),
  ('public.penta_remediation_execution_claim_v1(integer)', 'client_revoke'),
  ('public.penta_remediation_execution_read_v1(integer)', 'client_revoke'),
  ('public.penta_remediation_execution_reconcile_v1()', 'client_revoke'),
  ('public.penta_remediation_execution_status_v1()', 'client_revoke'),
  ('public.penta_runtime_reference_check_v2(text,text)', 'client_revoke'),
  ('public.penta_runtime_reference_regression_v2()', 'client_revoke'),
  ('public.penta_self_hard_repair_status_v1()', 'client_revoke'),
  ('public.thrivebase_sheet_mirror_next_provision_v1(integer)', 'client_revoke'),
  ('public.thrivebase_sheet_mirror_record_failure_v1(uuid,uuid,text,text,jsonb)', 'client_revoke'),
  ('public.thrivebase_sheet_mirror_record_progress_v1(uuid,uuid,text,text,integer,integer,bigint,boolean,text,text,jsonb)', 'client_revoke'),
  ('public.thrivebase_sheet_mirror_record_provision_v1(uuid,uuid,integer,text,text,text,jsonb)', 'client_revoke'),
  ('public.thrivebase_sheet_mirror_status_v1()', 'client_revoke'),
  ('public.thrivebase_sheets_mirror_invoke_v1(text,integer,integer)', 'client_revoke');

-- Exact public/token projection allowlist. PUBLIC is removed and the API roles
-- are granted explicitly so this list is reviewable and machine-testable.
insert into ct_secdef_batch2_targets_v1(function_identity, action) values
  ('public.chlom_control_plane_release_status_v1()', 'public_allowlist'),
  ('public.chlom_dail_assurance_status_v4()', 'public_allowlist'),
  ('public.chlom_protocol_status_v1()', 'public_allowlist'),
  ('public.chlom_protocol_status_v2()', 'public_allowlist'),
  ('public.chlom_verify_tokenized_object_v1(text)', 'public_allowlist'),
  ('public.chlom_wallet_production_status_v3()', 'public_allowlist'),
  ('public.ct_pentabrain_memory_put(text,text,text,jsonb,text[],text,numeric,numeric,timestamp with time zone)', 'public_allowlist'),
  ('public.ct_pentabrain_memory_recall(text,text[])', 'public_allowlist'),
  ('public.ct_pentabrain_mesh_claim_nonce(text,text,text,text,integer)', 'public_allowlist'),
  ('public.ct_pentabrain_receipt_write(text,uuid,text,text,text,boolean,jsonb)', 'public_allowlist'),
  ('public.ct_pentabrain_state_read(text,uuid)', 'public_allowlist'),
  ('public.ct_pentabrain_state_write(text,uuid,text,text,text,text,text[],jsonb,jsonb)', 'public_allowlist'),
  ('public.ct_pentabrain_validate_edge_token(text)', 'public_allowlist'),
  ('public.go_flipbooks_cpanel_catalog_page_v2(integer,integer)', 'public_allowlist'),
  ('public.go_flipbooks_governed_document_catalog_v1()', 'public_allowlist'),
  ('public.go_flipbooks_public_catalog_item_v2(text)', 'public_allowlist'),
  ('public.go_flipbooks_public_catalog_v2()', 'public_allowlist'),
  ('public.go_flipbooks_runtime_bundle_public_v3()', 'public_allowlist'),
  ('public.go_flipbooks_static_reader_public_v1(text)', 'public_allowlist'),
  ('public.go_flipbooks_storefront_collections_public_v1()', 'public_allowlist'),
  ('public.go_flipbooks_storefront_facets_public_v1()', 'public_allowlist'),
  ('public.go_flipbooks_storefront_health_public_v1()', 'public_allowlist'),
  ('public.go_flipbooks_storefront_home_public_v1()', 'public_allowlist'),
  ('public.go_flipbooks_storefront_item_public_v1(text)', 'public_allowlist'),
  ('public.go_flipbooks_storefront_items_public_v1(text,text,text,text,text,text,text,integer,integer)', 'public_allowlist'),
  ('public.pentabrain_marketplace_catalog_v1()', 'public_allowlist'),
  ('public.virality_transactional_email_relay_v1(jsonb)', 'public_allowlist'),
  ('virality_site_private.project_intake_credential_gate_v1(jsonb)', 'public_allowlist');

-- These exact authenticated grants are required by live RLS policies.
insert into ct_secdef_batch2_targets_v1(function_identity, action) values
  ('public.pentapersonas_is_workspace_member_v1(uuid,text[])', 'authenticated_rls_helper'),
  ('public.ct_realtime_workflow_topic_allowed_v1(text)', 'authenticated_rls_helper');

-- Extension/platform objects are audited for drift but intentionally untouched.
insert into ct_secdef_batch2_targets_v1(function_identity, action) values
  ('pgsodium.create_key(pgsodium.key_type,text,bytea,bytea,uuid,bytea,timestamp with time zone,text)', 'managed_exclusion'),
  ('pgsodium.disable_security_label_trigger()', 'managed_exclusion'),
  ('pgsodium.enable_security_label_trigger()', 'managed_exclusion'),
  ('pgsodium.get_key_by_id(uuid)', 'managed_exclusion'),
  ('pgsodium.get_key_by_name(text)', 'managed_exclusion'),
  ('pgsodium.get_named_keys(text)', 'managed_exclusion'),
  ('pgsodium.mask_role(regrole,text,text)', 'managed_exclusion'),
  ('pgsodium.update_mask(oid,boolean)', 'managed_exclusion'),
  ('supabase_functions.http_request()', 'managed_exclusion');

do $targets$
declare
  v_missing text;
  v_wrong text;
begin
  select string_agg(function_identity, ', ' order by function_identity)
    into v_missing
  from ct_secdef_batch2_targets_v1
  where to_regprocedure(function_identity) is null;

  if v_missing is not null then
    raise exception 'SECDEF second-batch target missing: %', v_missing;
  end if;

  if (select count(*) from ct_secdef_batch2_targets_v1 where action='client_revoke') <> 58
     or (select count(*) from ct_secdef_batch2_targets_v1 where action='public_allowlist') <> 28
     or (select count(*) from ct_secdef_batch2_targets_v1 where action='authenticated_rls_helper') <> 2
     or (select count(*) from ct_secdef_batch2_targets_v1 where action='managed_exclusion') <> 9 then
    raise exception 'SECDEF second-batch target cardinality mismatch';
  end if;

  select string_agg(t.function_identity, ', ' order by t.function_identity)
    into v_wrong
  from ct_secdef_batch2_targets_v1 t
  join pg_proc p on p.oid=to_regprocedure(t.function_identity)
  where not p.prosecdef;

  if v_wrong is not null then
    raise exception 'SECDEF second-batch target is not SECURITY DEFINER: %', v_wrong;
  end if;

  select string_agg(t.function_identity, ', ' order by t.function_identity)
    into v_wrong
  from ct_secdef_batch2_targets_v1 t
  join pg_proc p on p.oid=to_regprocedure(t.function_identity)
  where t.action <> 'managed_exclusion'
    and exists (
      select 1
      from pg_depend d
      where d.classid='pg_proc'::regclass
        and d.objid=p.oid
        and d.deptype='e'
    );

  if v_wrong is not null then
    raise exception 'custom SECDEF target unexpectedly extension-owned: %', v_wrong;
  end if;

  -- The rollback appendix replays the effective EXECUTE ACL multiset as
  -- postgres. Refuse the forward change unless every application target has
  -- the ownership/grantor shape that makes that replay lossless.
  select string_agg(t.function_identity, ', ' order by t.function_identity)
    into v_wrong
  from ct_secdef_batch2_targets_v1 t
  join pg_proc p on p.oid=to_regprocedure(t.function_identity)
  where t.action <> 'managed_exclusion'
    and (
      p.proowner <> 'postgres'::regrole::oid
      or exists (
        select 1
        from aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
        where a.privilege_type <> 'EXECUTE'
           or a.grantor <> 'postgres'::regrole::oid
      )
    );

  if v_wrong is not null then
    raise exception
      'custom SECDEF ACL cannot be replayed exactly by rollback appendix: %',
      v_wrong;
  end if;

  if exists (
    select 1
    from integration_control.security_hardening_snapshots_v1
    where change_key='20260908_secdef_client_allowlist_second_batch_v1'
  ) then
    raise exception
      'SECDEF second-batch snapshot key already exists; refusing to overwrite it';
  end if;
end
$targets$;

create temporary table ct_secdef_counts_pre_v1 on commit drop as
with f as (
  select
    p.oid,
    n.oid as namespace_oid,
    n.nspname,
    exists (
      select 1
      from pg_depend d
      where d.classid='pg_proc'::regclass
        and d.objid=p.oid
        and d.deptype='e'
    ) as extension_owned
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where p.prosecdef
)
select
  count(*) filter (
    where has_function_privilege('anon',oid,'execute')
  )::integer as anon_raw,
  count(*) filter (
    where has_function_privilege('anon',oid,'execute')
      and has_schema_privilege('anon',namespace_oid,'usage')
  )::integer as anon_reachable,
  count(*) filter (
    where has_function_privilege('anon',oid,'execute')
      and has_schema_privilege('anon',namespace_oid,'usage')
      and not extension_owned
      and nspname <> 'supabase_functions'
  )::integer as anon_custom_reachable,
  count(*) filter (
    where has_function_privilege('anon',oid,'execute')
      and has_schema_privilege('anon',namespace_oid,'usage')
      and not extension_owned
      and nspname='public'
  )::integer as anon_public_custom_reachable,
  count(*) filter (
    where has_function_privilege('anon',oid,'execute')
      and has_schema_privilege('anon',namespace_oid,'usage')
      and extension_owned
  )::integer as anon_extension_reachable,
  count(*) filter (
    where has_function_privilege('anon',oid,'execute')
      and has_schema_privilege('anon',namespace_oid,'usage')
      and nspname='supabase_functions'
  )::integer as anon_platform_reachable,
  count(*) filter (
    where has_function_privilege('authenticated',oid,'execute')
  )::integer as auth_raw,
  count(*) filter (
    where has_function_privilege('authenticated',oid,'execute')
      and has_schema_privilege('authenticated',namespace_oid,'usage')
  )::integer as auth_reachable,
  count(*) filter (
    where has_function_privilege('authenticated',oid,'execute')
      and has_schema_privilege('authenticated',namespace_oid,'usage')
      and not extension_owned
      and nspname <> 'supabase_functions'
  )::integer as auth_custom_reachable
from f;

do $baseline$
declare
  v ct_secdef_counts_pre_v1%rowtype;
  v_live_anon_calls bigint;
begin
  select * into strict v from ct_secdef_counts_pre_v1;

  if row(
    v.anon_raw,
    v.anon_reachable,
    v.anon_custom_reachable,
    v.anon_public_custom_reachable,
    v.anon_extension_reachable,
    v.anon_platform_reachable,
    v.auth_raw,
    v.auth_reachable,
    v.auth_custom_reachable
  ) is distinct from row(364,95,86,85,8,1,387,115,106) then
    raise exception
      'SECDEF second-batch baseline drift: anon raw/reachable/custom/public/ext/platform=%/%/%/%/%/%, auth raw/reachable/custom=%/%/%',
      v.anon_raw,v.anon_reachable,v.anon_custom_reachable,
      v.anon_public_custom_reachable,v.anon_extension_reachable,
      v.anon_platform_reachable,v.auth_raw,v.auth_reachable,
      v.auth_custom_reachable;
  end if;

  select coalesce(sum(s.calls),0)::bigint
    into v_live_anon_calls
  from ct_secdef_batch2_targets_v1 t
  join pg_proc p on p.oid=to_regprocedure(t.function_identity)
  join pg_stat_statements s
    on s.query ~* ('(^|[^a-zA-Z0-9_])'||p.proname||'([^a-zA-Z0-9_]|$)')
  join pg_roles r on r.oid=s.userid and r.rolname='anon'
  where t.action='client_revoke';

  if v_live_anon_calls <> 0 then
    raise exception
      'SECDEF second-batch abort: revoke targets now have % anon calls since pg_stat_statements reset',
      v_live_anon_calls;
  end if;
end
$baseline$;

-- Freeze the RLS/policy state byte-for-byte for the duration of this migration.
create temporary table ct_secdef_rls_fingerprint_pre_v1 on commit drop as
with objects as (
  select
    'table'::text as object_kind,
    format('%I.%I',n.nspname,c.relname) as object_identity,
    concat_ws('|',c.relrowsecurity::text,c.relforcerowsecurity::text) as definition
  from pg_class c
  join pg_namespace n on n.oid=c.relnamespace
  where c.relkind in ('r','p')
    and n.nspname in ('public','realtime')
  union all
  select
    'policy',
    format('%I.%I:%s',n.nspname,c.relname,p.polname),
    concat_ws('|',p.polcmd,p.polpermissive::text,p.polroles::text,
      pg_get_expr(p.polqual,p.polrelid),pg_get_expr(p.polwithcheck,p.polrelid))
  from pg_policy p
  join pg_class c on c.oid=p.polrelid
  join pg_namespace n on n.oid=c.relnamespace
  where n.nspname in ('public','realtime')
)
select md5(coalesce(string_agg(
  object_kind||'|'||object_identity||'|'||coalesce(definition,''),
  E'\n' order by object_kind,object_identity
),'')) as fingerprint
from objects;

create temporary table ct_secdef_managed_pre_v1 on commit drop as
select
  t.function_identity,
  p.proacl::text as acl_before,
  md5(pg_get_functiondef(p.oid)) as definition_hash_before
from ct_secdef_batch2_targets_v1 t
join pg_proc p on p.oid=to_regprocedure(t.function_identity)
where t.action='managed_exclusion';

insert into integration_control.security_hardening_snapshots_v1(
  change_key,
  object_kind,
  object_identity,
  owner_name,
  acl_before,
  settings_before,
  definition_hash_md5
)
select
  '20260908_secdef_client_allowlist_second_batch_v1',
  case when t.action='managed_exclusion' then 'managed_function' else 'function' end,
  t.function_identity,
  p.proowner::regrole::text,
  p.proacl::text,
  jsonb_build_object(
    'action',t.action,
    'acl_is_null',p.proacl is null,
    'proconfig',p.proconfig,
    'anon_execute',has_function_privilege('anon',p.oid,'execute'),
    'authenticated_execute',has_function_privilege('authenticated',p.oid,'execute'),
    'service_role_execute',has_function_privilege('service_role',p.oid,'execute'),
    'anon_calls_since_pgss_reset',coalesce((
      select sum(s.calls)::bigint
      from pg_stat_statements s
      join pg_roles r on r.oid=s.userid and r.rolname='anon'
      where s.query ~* ('(^|[^a-zA-Z0-9_])'||p.proname||'([^a-zA-Z0-9_]|$)')
    ),0)
  ),
  md5(pg_get_functiondef(p.oid))
from ct_secdef_batch2_targets_v1 t
join pg_proc p on p.oid=to_regprocedure(t.function_identity);

insert into integration_control.security_hardening_snapshots_v1(
  change_key,object_kind,object_identity,owner_name,acl_before,
  settings_before,definition_hash_md5
)
select
  '20260908_secdef_client_allowlist_second_batch_v1',
  'catalog_count',
  'security_definer_privilege_counts',
  current_user,
  concat_ws('/',anon_raw,anon_reachable,anon_custom_reachable,
    anon_public_custom_reachable,anon_extension_reachable,
    anon_platform_reachable,auth_raw,auth_reachable,auth_custom_reachable),
  to_jsonb(ct_secdef_counts_pre_v1),
  md5(to_jsonb(ct_secdef_counts_pre_v1)::text)
from ct_secdef_counts_pre_v1;

-- Normalize the allowlist away from PUBLIC inheritance to explicit API roles.
do $allowlist_acl$
declare
  v record;
begin
  for v in
    select p.oid
    from ct_secdef_batch2_targets_v1 t
    join pg_proc p on p.oid=to_regprocedure(t.function_identity)
    where t.action='public_allowlist'
    order by t.function_identity
  loop
    execute format('revoke execute on function %s from public',v.oid::regprocedure);
    execute format('grant execute on function %s to anon, authenticated, service_role',v.oid::regprocedure);
  end loop;
end
$allowlist_acl$;

-- Remove client execution from the exact second-batch set. Postgres ownership
-- and explicit service_role execution preserve nested, Edge, worker, and cron
-- paths without relying on RLS bypass as the public authorization boundary.
do $revoke_acl$
declare
  v record;
begin
  for v in
    select p.oid
    from ct_secdef_batch2_targets_v1 t
    join pg_proc p on p.oid=to_regprocedure(t.function_identity)
    where t.action='client_revoke'
    order by t.function_identity
  loop
    execute format(
      'revoke execute on function %s from public, anon, authenticated',
      v.oid::regprocedure
    );
    execute format(
      'grant execute on function %s to service_role',
      v.oid::regprocedure
    );
  end loop;
end
$revoke_acl$;

-- Preserve only authenticated/service execution on policy-critical helpers.
do $rls_helper_acl$
declare
  v record;
begin
  for v in
    select p.oid
    from ct_secdef_batch2_targets_v1 t
    join pg_proc p on p.oid=to_regprocedure(t.function_identity)
    where t.action='authenticated_rls_helper'
    order by t.function_identity
  loop
    execute format('revoke execute on function %s from public, anon',v.oid::regprocedure);
    execute format('grant execute on function %s to authenticated, service_role',v.oid::regprocedure);
  end loop;
end
$rls_helper_acl$;

-- The public SECURITY INVOKER relay calls this private gate as the API caller.
grant usage on schema virality_site_private to anon, authenticated, service_role;

-- Capture the exact post-state ACLs as the rollback guard. The companion
-- operator-only rollback appendix refuses to run if any one of these ACLs has
-- changed since this migration committed.
insert into integration_control.security_hardening_snapshots_v1(
  change_key,
  object_kind,
  object_identity,
  owner_name,
  acl_before,
  settings_before,
  definition_hash_md5
)
select
  '20260908_secdef_client_allowlist_second_batch_v1',
  'function_acl_post',
  t.function_identity,
  p.proowner::regrole::text,
  p.proacl::text,
  jsonb_build_object('action',t.action,'acl_is_null',p.proacl is null),
  md5(pg_get_functiondef(p.oid))
from ct_secdef_batch2_targets_v1 t
join pg_proc p on p.oid=to_regprocedure(t.function_identity)
where t.action in (
  'client_revoke','public_allowlist','authenticated_rls_helper'
);

do $verify$
declare
  v_bad text;
  v_rls_after text;
  v_counts record;
begin
  select string_agg(t.function_identity, ', ' order by t.function_identity)
    into v_bad
  from ct_secdef_batch2_targets_v1 t
  join pg_proc p on p.oid=to_regprocedure(t.function_identity)
  where t.action='client_revoke'
    and (
      has_function_privilege('anon',p.oid,'execute')
      or has_function_privilege('authenticated',p.oid,'execute')
      or not has_function_privilege('service_role',p.oid,'execute')
    );
  if v_bad is not null then
    raise exception 'SECDEF second-batch client revoke verification failed: %',v_bad;
  end if;

  select string_agg(t.function_identity, ', ' order by t.function_identity)
    into v_bad
  from ct_secdef_batch2_targets_v1 t
  join pg_proc p on p.oid=to_regprocedure(t.function_identity)
  where t.action='public_allowlist'
    and (
      not has_function_privilege('anon',p.oid,'execute')
      or not has_function_privilege('authenticated',p.oid,'execute')
      or not has_function_privilege('service_role',p.oid,'execute')
      or exists (
        select 1
        from aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
        where a.grantee=0 and a.privilege_type='EXECUTE'
      )
    );
  if v_bad is not null then
    raise exception 'SECDEF public allowlist verification failed: %',v_bad;
  end if;

  select string_agg(t.function_identity, ', ' order by t.function_identity)
    into v_bad
  from ct_secdef_batch2_targets_v1 t
  join pg_proc p on p.oid=to_regprocedure(t.function_identity)
  where t.action='authenticated_rls_helper'
    and (
      has_function_privilege('anon',p.oid,'execute')
      or not has_function_privilege('authenticated',p.oid,'execute')
      or not has_function_privilege('service_role',p.oid,'execute')
    );
  if v_bad is not null then
    raise exception 'authenticated RLS helper ACL verification failed: %',v_bad;
  end if;

  -- Six unique PentaPersonas policies and two realtime receive policies must
  -- still depend on their respective helpers.
  if (
    select count(distinct pol.oid)
    from pg_depend d
    join pg_policy pol on pol.oid=d.objid and d.classid='pg_policy'::regclass
    where d.refclassid='pg_proc'::regclass
      and d.refobjid=to_regprocedure('public.pentapersonas_is_workspace_member_v1(uuid,text[])')
      and pol.polroles @> array['authenticated'::regrole::oid]::oid[]
  ) <> 6 then
    raise exception 'PentaPersonas RLS helper dependency count changed';
  end if;

  if (
    select count(distinct pol.oid)
    from pg_depend d
    join pg_policy pol on pol.oid=d.objid and d.classid='pg_policy'::regclass
    join pg_class c on c.oid=pol.polrelid
    join pg_namespace n on n.oid=c.relnamespace
    where d.refclassid='pg_proc'::regclass
      and d.refobjid=to_regprocedure('public.ct_realtime_workflow_topic_allowed_v1(text)')
      and n.nspname='realtime'
      and c.relname='messages'
      and pol.polroles @> array['authenticated'::regrole::oid]::oid[]
  ) <> 2 then
    raise exception 'Realtime RLS helper dependency count changed';
  end if;

  if not has_schema_privilege('anon','virality_site_private','usage')
     or not has_schema_privilege('authenticated','virality_site_private','usage')
     or not has_function_privilege(
       'anon','virality_site_private.project_intake_credential_gate_v1(jsonb)','execute'
     )
     or not has_function_privilege(
       'authenticated','virality_site_private.project_intake_credential_gate_v1(jsonb)','execute'
     )
     or to_regprocedure('public.virality_project_intake_relay_v1(jsonb)') is null
     or (
       select p.prosecdef
       from pg_proc p
       where p.oid=to_regprocedure('public.virality_project_intake_relay_v1(jsonb)')
     ) then
    raise exception 'Virality invoker-to-private-gate path was not preserved';
  end if;

  -- Managed function ACLs and definitions must be byte-identical.
  select string_agg(m.function_identity, ', ' order by m.function_identity)
    into v_bad
  from ct_secdef_managed_pre_v1 m
  join pg_proc p on p.oid=to_regprocedure(m.function_identity)
  where p.proacl::text is distinct from m.acl_before
     or md5(pg_get_functiondef(p.oid)) is distinct from m.definition_hash_before;
  if v_bad is not null then
    raise exception 'managed function drift detected: %',v_bad;
  end if;

  -- Trigger execution is independent of client EXECUTE, but its binding must
  -- remain enabled and postgres must retain execution authority.
  if not exists (
    select 1
    from pg_trigger t
    join pg_class c on c.oid=t.tgrelid
    join pg_namespace n on n.oid=c.relnamespace
    where not t.tgisinternal
      and t.tgenabled <> 'D'
      and n.nspname='public'
      and c.relname='go_flipbooks_storefront_items_v1'
      and t.tgfoid=to_regprocedure('public.go_flipbooks_block_item_delete_v1()')
  )
  or not has_function_privilege(
    'postgres','public.go_flipbooks_block_item_delete_v1()','execute'
  )
  or not has_function_privilege(
    'postgres','public.penta_mail_sensitivity_class_v1(text,text,text,jsonb)','execute'
  )
  or not has_function_privilege(
    'postgres','public.penta_mail_template_route_v1(text,jsonb)','execute'
  ) then
    raise exception 'trigger/internal postgres execution path was not preserved';
  end if;

  -- The active cron calls the private integration_control function, not the
  -- same-named public wrapper contained by this migration.
  if not exists (
    select 1
    from cron.job
    where jobname='ct-locticians-bd-webhook-target-dispatch-v1'
      and active
      and username='postgres'
      and command ~ 'integration_control[.]locticians_bd_webhook_dispatch_tick_v1'
  ) then
    raise exception 'Locticians webhook cron path changed or is inactive';
  end if;

  with objects as (
    select
      'table'::text as object_kind,
      format('%I.%I',n.nspname,c.relname) as object_identity,
      concat_ws('|',c.relrowsecurity::text,c.relforcerowsecurity::text) as definition
    from pg_class c
    join pg_namespace n on n.oid=c.relnamespace
    where c.relkind in ('r','p')
      and n.nspname in ('public','realtime')
    union all
    select
      'policy',
      format('%I.%I:%s',n.nspname,c.relname,p.polname),
      concat_ws('|',p.polcmd,p.polpermissive::text,p.polroles::text,
        pg_get_expr(p.polqual,p.polrelid),pg_get_expr(p.polwithcheck,p.polrelid))
    from pg_policy p
    join pg_class c on c.oid=p.polrelid
    join pg_namespace n on n.oid=c.relnamespace
    where n.nspname in ('public','realtime')
  )
  select md5(coalesce(string_agg(
    object_kind||'|'||object_identity||'|'||coalesce(definition,''),
    E'\n' order by object_kind,object_identity
  ),'')) into v_rls_after
  from objects;

  if v_rls_after is distinct from (
    select fingerprint from ct_secdef_rls_fingerprint_pre_v1
  ) then
    raise exception 'RLS table/policy fingerprint changed during ACL migration';
  end if;

  with f as (
    select
      p.oid,
      n.oid as namespace_oid,
      n.nspname,
      exists (
        select 1
        from pg_depend d
        where d.classid='pg_proc'::regclass
          and d.objid=p.oid
          and d.deptype='e'
      ) as extension_owned
    from pg_proc p
    join pg_namespace n on n.oid=p.pronamespace
    where p.prosecdef
  )
  select
    count(*) filter (where has_function_privilege('anon',oid,'execute'))::integer as anon_raw,
    count(*) filter (
      where has_function_privilege('anon',oid,'execute')
        and has_schema_privilege('anon',namespace_oid,'usage')
    )::integer as anon_reachable,
    count(*) filter (
      where has_function_privilege('anon',oid,'execute')
        and has_schema_privilege('anon',namespace_oid,'usage')
        and not extension_owned and nspname <> 'supabase_functions'
    )::integer as anon_custom_reachable,
    count(*) filter (
      where has_function_privilege('anon',oid,'execute')
        and has_schema_privilege('anon',namespace_oid,'usage')
        and not extension_owned and nspname='public'
    )::integer as anon_public_custom_reachable,
    count(*) filter (
      where has_function_privilege('anon',oid,'execute')
        and has_schema_privilege('anon',namespace_oid,'usage')
        and extension_owned
    )::integer as anon_extension_reachable,
    count(*) filter (
      where has_function_privilege('anon',oid,'execute')
        and has_schema_privilege('anon',namespace_oid,'usage')
        and nspname='supabase_functions'
    )::integer as anon_platform_reachable,
    count(*) filter (
      where has_function_privilege('authenticated',oid,'execute')
    )::integer as auth_raw,
    count(*) filter (
      where has_function_privilege('authenticated',oid,'execute')
        and has_schema_privilege('authenticated',namespace_oid,'usage')
    )::integer as auth_reachable,
    count(*) filter (
      where has_function_privilege('authenticated',oid,'execute')
        and has_schema_privilege('authenticated',namespace_oid,'usage')
        and not extension_owned and nspname <> 'supabase_functions'
    )::integer as auth_custom_reachable
  into v_counts
  from f;

  if row(
    v_counts.anon_raw,
    v_counts.anon_reachable,
    v_counts.anon_custom_reachable,
    v_counts.anon_public_custom_reachable,
    v_counts.anon_extension_reachable,
    v_counts.anon_platform_reachable,
    v_counts.auth_raw,
    v_counts.auth_reachable,
    v_counts.auth_custom_reachable
  ) is distinct from row(306,37,28,27,8,1,329,57,48) then
    raise exception
      'SECDEF second-batch postcondition mismatch: anon raw/reachable/custom/public/ext/platform=%/%/%/%/%/%, auth raw/reachable/custom=%/%/%',
      v_counts.anon_raw,v_counts.anon_reachable,v_counts.anon_custom_reachable,
      v_counts.anon_public_custom_reachable,v_counts.anon_extension_reachable,
      v_counts.anon_platform_reachable,v_counts.auth_raw,v_counts.auth_reachable,
      v_counts.auth_custom_reachable;
  end if;
end
$verify$;

notify pgrst, 'reload schema';

commit;

-- Operator rollback appendix:
--   20260908155000_secdef_client_allowlist_second_batch_v1.rollback.sql
-- It is intentionally a separate executable file so a normal migration run
-- cannot cross the forward-only commit boundary and undo itself. The appendix
-- is armed only by an explicit session GUC and restores the ACLITEM snapshot;
-- it restores the exact effective EXECUTE multiset without GRANT ALL or direct
-- PostgreSQL system-catalog updates. A NULL proacl may normalize to an explicit
-- equivalent ACL array during rollback; effective privileges remain identical.
