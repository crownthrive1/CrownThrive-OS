-- CrownThrive CHLOM / PentaSecurity
-- Direct-callable SECURITY DEFINER App Factory provider-dispatch hardening expansion v3.
--
-- Fresh ThriveBase catalog/runtime readback on 2026-08-31 established 2,408
-- application-owned SECURITY DEFINER functions, 244 with broad role EXECUTE,
-- 64 directly anon-callable and 71 directly authenticated-callable after schema-USAGE
-- evaluation. This supersedes the earlier 2,386 / 224 / 44 / 51 readback.
--
-- This bounded expansion continues canonical PR #1962 and hardens fifteen additional
-- public App Factory functions proven by exact production definition/ACL readback to:
-- * run SECURITY DEFINER with pinned search_path;
-- * remain directly callable by anon and authenticated;
-- * consume vaulted provider material;
-- * perform HTTP/provider dispatch; and
-- * lack an explicit caller-role/service-role guard in the function body.
--
-- Authority boundary: ACL-only. Function bodies, vaulted material, provider state,
-- money, credentials, D3/sovereign authority, rights/legal commitments and CHLOM
-- authority are not modified by this migration.

begin;

do $$
declare
  v_sig text;
  v_required text[] := array[
    'public.app_factory_android_closeout_dispatch(text)',
    'public.app_factory_docroot_control_dispatch(text)',
    'public.app_factory_existing_closeout_sync(text,text)',
    'public.app_factory_institutionalize_release_dispatch()',
    'public.app_factory_merge_institutionalization_dispatch()',
    'public.app_factory_root_route_dispatch()',
    'public.app_factory_runtime_evidence_dispatch(text)',
    'public.app_factory_runtime_probe_sync(text)',
    'public.app_factory_signed_health_dispatch()',
    'public.app_factory_source_authority_gate_sync(text)',
    'public.app_factory_source_inspect_dispatch(jsonb)',
    'public.app_factory_source_inspect_sync(jsonb)',
    'public.app_factory_storage_repair_dispatch(text)',
    'public.app_factory_tls_gate_sync(text)',
    'public.app_factory_web_debug_dispatch()'
  ];
begin
  foreach v_sig in array v_required loop
    if to_regprocedure(v_sig) is null then
      raise exception 'PentaSecurity App Factory ACL expansion source/runtime drift: required function missing: %', v_sig;
    end if;
    if not (select p.prosecdef from pg_proc p where p.oid=to_regprocedure(v_sig)) then
      raise exception 'PentaSecurity App Factory ACL expansion expected SECURITY DEFINER function: %', v_sig;
    end if;
    if lower(pg_get_functiondef(to_regprocedure(v_sig))) not like '%set search_path%' then
      raise exception 'PentaSecurity App Factory ACL expansion requires pinned search_path: %', v_sig;
    end if;
  end loop;
end
$$;

revoke execute on function public.app_factory_android_closeout_dispatch(text) from public, anon, authenticated;
revoke execute on function public.app_factory_docroot_control_dispatch(text) from public, anon, authenticated;
revoke execute on function public.app_factory_existing_closeout_sync(text,text) from public, anon, authenticated;
revoke execute on function public.app_factory_institutionalize_release_dispatch() from public, anon, authenticated;
revoke execute on function public.app_factory_merge_institutionalization_dispatch() from public, anon, authenticated;
revoke execute on function public.app_factory_root_route_dispatch() from public, anon, authenticated;
revoke execute on function public.app_factory_runtime_evidence_dispatch(text) from public, anon, authenticated;
revoke execute on function public.app_factory_runtime_probe_sync(text) from public, anon, authenticated;
revoke execute on function public.app_factory_signed_health_dispatch() from public, anon, authenticated;
revoke execute on function public.app_factory_source_authority_gate_sync(text) from public, anon, authenticated;
revoke execute on function public.app_factory_source_inspect_dispatch(jsonb) from public, anon, authenticated;
revoke execute on function public.app_factory_source_inspect_sync(jsonb) from public, anon, authenticated;
revoke execute on function public.app_factory_storage_repair_dispatch(text) from public, anon, authenticated;
revoke execute on function public.app_factory_tls_gate_sync(text) from public, anon, authenticated;
revoke execute on function public.app_factory_web_debug_dispatch() from public, anon, authenticated;

grant execute on function public.app_factory_android_closeout_dispatch(text) to service_role;
grant execute on function public.app_factory_docroot_control_dispatch(text) to service_role;
grant execute on function public.app_factory_existing_closeout_sync(text,text) to service_role;
grant execute on function public.app_factory_institutionalize_release_dispatch() to service_role;
grant execute on function public.app_factory_merge_institutionalization_dispatch() to service_role;
grant execute on function public.app_factory_root_route_dispatch() to service_role;
grant execute on function public.app_factory_runtime_evidence_dispatch(text) to service_role;
grant execute on function public.app_factory_runtime_probe_sync(text) to service_role;
grant execute on function public.app_factory_signed_health_dispatch() to service_role;
grant execute on function public.app_factory_source_authority_gate_sync(text) to service_role;
grant execute on function public.app_factory_source_inspect_dispatch(jsonb) to service_role;
grant execute on function public.app_factory_source_inspect_sync(jsonb) to service_role;
grant execute on function public.app_factory_storage_repair_dispatch(text) to service_role;
grant execute on function public.app_factory_tls_gate_sync(text) to service_role;
grant execute on function public.app_factory_web_debug_dispatch() to service_role;

commit;
