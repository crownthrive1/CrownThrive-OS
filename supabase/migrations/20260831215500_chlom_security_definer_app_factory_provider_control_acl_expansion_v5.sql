-- CrownThrive CHLOM / PentaSecurity
-- Direct-callable SECURITY DEFINER App Factory provider/control-surface hardening v5.
--
-- Fresh ThriveBase catalog readback on 2026-08-31 proved the targets below are
-- SECURITY DEFINER, directly executable by anon/authenticated, retain service_role,
-- have pinned search_path, and expose provider/control/write semantics without an
-- explicit caller/service-role guard in the function body.
--
-- Authority boundary: ACL-only. Function bodies, vaulted values, provider state,
-- release state, credentials, D3/sovereign authority, money and rights/legal state
-- are not modified by this migration.

begin;

do $$
declare
  v_sig text;
  v_required text[] := array[
    'public.app_factory_android_closeout_dispatch(text)',
    'public.app_factory_android_sdk_canary_reconcile()',
    'public.app_factory_dcv_control_dispatch(text)',
    'public.app_factory_docroot_control_dispatch(text)',
    'public.app_factory_github_create_new_file(text,text,text,text,text)',
    'public.app_factory_institutionalize_release_dispatch()',
    'public.app_factory_merge_institutionalization_dispatch()',
    'public.app_factory_merge_production_pr(text,text,boolean)',
    'public.app_factory_provider_dispatch_sync(text,text)',
    'public.app_factory_public_android_canary_apply_known_repairs()',
    'public.app_factory_root_route_dispatch()',
    'public.app_factory_runtime_evidence_dispatch(text)',
    'public.app_factory_ssl_control_dispatch(text)',
    'public.app_factory_storage_repair_dispatch(text)'
  ];
begin
  foreach v_sig in array v_required loop
    if to_regprocedure(v_sig) is null then
      raise exception 'PentaSecurity App Factory provider/control ACL source/runtime drift: required function missing: %', v_sig;
    end if;
    if not (select p.prosecdef from pg_proc p where p.oid=to_regprocedure(v_sig)) then
      raise exception 'PentaSecurity App Factory provider/control ACL expected SECURITY DEFINER function: %', v_sig;
    end if;
    if lower(pg_get_functiondef(to_regprocedure(v_sig))) not like '%set search_path%' then
      raise exception 'PentaSecurity App Factory provider/control ACL requires pinned search_path: %', v_sig;
    end if;
  end loop;
end
$$;

revoke execute on function public.app_factory_android_closeout_dispatch(text) from public, anon, authenticated;
revoke execute on function public.app_factory_android_sdk_canary_reconcile() from public, anon, authenticated;
revoke execute on function public.app_factory_dcv_control_dispatch(text) from public, anon, authenticated;
revoke execute on function public.app_factory_docroot_control_dispatch(text) from public, anon, authenticated;
revoke execute on function public.app_factory_github_create_new_file(text,text,text,text,text) from public, anon, authenticated;
revoke execute on function public.app_factory_institutionalize_release_dispatch() from public, anon, authenticated;
revoke execute on function public.app_factory_merge_institutionalization_dispatch() from public, anon, authenticated;
revoke execute on function public.app_factory_merge_production_pr(text,text,boolean) from public, anon, authenticated;
revoke execute on function public.app_factory_provider_dispatch_sync(text,text) from public, anon, authenticated;
revoke execute on function public.app_factory_public_android_canary_apply_known_repairs() from public, anon, authenticated;
revoke execute on function public.app_factory_root_route_dispatch() from public, anon, authenticated;
revoke execute on function public.app_factory_runtime_evidence_dispatch(text) from public, anon, authenticated;
revoke execute on function public.app_factory_ssl_control_dispatch(text) from public, anon, authenticated;
revoke execute on function public.app_factory_storage_repair_dispatch(text) from public, anon, authenticated;

grant execute on function public.app_factory_android_closeout_dispatch(text) to service_role;
grant execute on function public.app_factory_android_sdk_canary_reconcile() to service_role;
grant execute on function public.app_factory_dcv_control_dispatch(text) to service_role;
grant execute on function public.app_factory_docroot_control_dispatch(text) to service_role;
grant execute on function public.app_factory_github_create_new_file(text,text,text,text,text) to service_role;
grant execute on function public.app_factory_institutionalize_release_dispatch() to service_role;
grant execute on function public.app_factory_merge_institutionalization_dispatch() to service_role;
grant execute on function public.app_factory_merge_production_pr(text,text,boolean) to service_role;
grant execute on function public.app_factory_provider_dispatch_sync(text,text) to service_role;
grant execute on function public.app_factory_public_android_canary_apply_known_repairs() to service_role;
grant execute on function public.app_factory_root_route_dispatch() to service_role;
grant execute on function public.app_factory_runtime_evidence_dispatch(text) to service_role;
grant execute on function public.app_factory_ssl_control_dispatch(text) to service_role;
grant execute on function public.app_factory_storage_repair_dispatch(text) to service_role;

commit;
