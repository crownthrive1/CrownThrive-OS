-- CrownThrive CHLOM / PentaSecurity
-- Direct-callable SECURITY DEFINER write-surface hardening expansion v2.
--
-- Fresh ThriveBase catalog/runtime readback on 2026-08-31 established a broader
-- SECURITY DEFINER role-EXECUTE least-privilege surface. Most private-schema
-- functions remain separately classified by schema reachability and internal
-- authorization guards. This bounded expansion does NOT claim universal closure.
--
-- This revision hardens ten verified public-schema state-changing/provider-dispatch
-- functions outside the original 22-function PR #1962 cohort. The five App Factory
-- dispatchers are especially sensitive: fresh exact function-definition readback
-- shows they consume a vaulted provider dispatch token and perform provider HTTP
-- dispatch while having no caller-role guard in the function body, yet production
-- currently permits anon/authenticated EXECUTE.
--
-- Authority boundary: ACL-only. No function body, credential, provider write,
-- money movement, D3/sovereign state, rights/legal commitment, or authority
-- expansion is created by this migration.

begin;

do $$
declare
  v_sig text;
  v_required text[] := array[
    'public.thrivebase_sheet_mirror_record_failure_v1(uuid,uuid,text,text,jsonb)',
    'public.thrivebase_sheet_mirror_record_folder_v1(text,text,text,jsonb)',
    'public.thrivebase_sheet_mirror_record_progress_v1(uuid,uuid,text,text,integer,integer,bigint,boolean,text,text,jsonb)',
    'public.thrivebase_sheet_mirror_record_provision_v1(uuid,uuid,integer,text,text,text,jsonb)',
    'public.penta_ads_scan_ingest_v1(bigint,text,integer,text,text,jsonb,text,jsonb)',
    'public.app_factory_bootstrap_inspect_dispatch()',
    'public.app_factory_dcv_control_dispatch(text)',
    'public.app_factory_php_runtime_probe_dispatch(text)',
    'public.app_factory_provider_dispatch_sync(text,text)',
    'public.app_factory_ssl_control_dispatch(text)'
  ];
begin
  foreach v_sig in array v_required loop
    if to_regprocedure(v_sig) is null then
      raise exception 'PentaSecurity direct-write ACL expansion source/runtime drift: required function missing: %', v_sig;
    end if;
    if not (select p.prosecdef from pg_proc p where p.oid=to_regprocedure(v_sig)) then
      raise exception 'PentaSecurity direct-write ACL expansion expected SECURITY DEFINER function: %', v_sig;
    end if;
  end loop;
end
$$;

revoke execute on function public.thrivebase_sheet_mirror_record_failure_v1(uuid,uuid,text,text,jsonb) from public, anon, authenticated;
revoke execute on function public.thrivebase_sheet_mirror_record_folder_v1(text,text,text,jsonb) from public, anon, authenticated;
revoke execute on function public.thrivebase_sheet_mirror_record_progress_v1(uuid,uuid,text,text,integer,integer,bigint,boolean,text,text,jsonb) from public, anon, authenticated;
revoke execute on function public.thrivebase_sheet_mirror_record_provision_v1(uuid,uuid,integer,text,text,text,jsonb) from public, anon, authenticated;
revoke execute on function public.penta_ads_scan_ingest_v1(bigint,text,integer,text,text,jsonb,text,jsonb) from public, anon, authenticated;
revoke execute on function public.app_factory_bootstrap_inspect_dispatch() from public, anon, authenticated;
revoke execute on function public.app_factory_dcv_control_dispatch(text) from public, anon, authenticated;
revoke execute on function public.app_factory_php_runtime_probe_dispatch(text) from public, anon, authenticated;
revoke execute on function public.app_factory_provider_dispatch_sync(text,text) from public, anon, authenticated;
revoke execute on function public.app_factory_ssl_control_dispatch(text) from public, anon, authenticated;

grant execute on function public.thrivebase_sheet_mirror_record_failure_v1(uuid,uuid,text,text,jsonb) to service_role;
grant execute on function public.thrivebase_sheet_mirror_record_folder_v1(text,text,text,jsonb) to service_role;
grant execute on function public.thrivebase_sheet_mirror_record_progress_v1(uuid,uuid,text,text,integer,integer,bigint,boolean,text,text,jsonb) to service_role;
grant execute on function public.thrivebase_sheet_mirror_record_provision_v1(uuid,uuid,integer,text,text,text,jsonb) to service_role;
grant execute on function public.penta_ads_scan_ingest_v1(bigint,text,integer,text,text,jsonb,text,jsonb) to service_role;
grant execute on function public.app_factory_bootstrap_inspect_dispatch() to service_role;
grant execute on function public.app_factory_dcv_control_dispatch(text) to service_role;
grant execute on function public.app_factory_php_runtime_probe_dispatch(text) to service_role;
grant execute on function public.app_factory_provider_dispatch_sync(text,text) to service_role;
grant execute on function public.app_factory_ssl_control_dispatch(text) to service_role;

commit;
