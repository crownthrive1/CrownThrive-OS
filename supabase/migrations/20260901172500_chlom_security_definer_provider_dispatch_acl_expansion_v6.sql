-- CrownThrive CHLOM / PentaSecurity
-- Direct-callable SECURITY DEFINER provider/worker dispatch ACL hardening v6.
--
-- Fresh production readback on 2026-09-01 proved these seven public-schema
-- functions are SECURITY DEFINER, directly executable by anon/authenticated,
-- retain service_role execution, and can reach vaulted/internal credentials plus
-- provider or privileged worker surfaces. Four have no caller guard. Three use
-- `current_user` as a service-role guard; under SECURITY DEFINER, current_user is
-- the function owner and therefore is not a caller-authorization predicate.
--
-- This is authority contraction only. Function bodies, credentials, provider
-- state, rights, money, votes/quorum, D3 and release state are not modified.

begin;

do $$
declare
  v_sig text;
  v_expected_sha text;
  v_actual_sha text;
  v_sigs text[] := array[
    'public.app_factory_runtime_probe_sync(text)',
    'public.app_factory_signed_health_dispatch()',
    'public.app_factory_source_authority_gate_sync(text)',
    'public.app_factory_tls_gate_sync(text)',
    'public.operation_clean_worker_invoke_v1()',
    'public.penta_drive_acl_bootstrap_invoke_v1(text)',
    'public.thrivebase_sheets_create_probe_invoke_v1()'
  ];
  v_hashes text[] := array[
    '092d231eb98300bacfd9dc34a1fffad247f0e3570952ff1a4a156973b3a03aaf',
    '78090cde8e7a83ddcdb753e014dc5bf74a596775b51375613d0e27f9ed352c79',
    'a134e505ee8f195cbf839811a19a5dfcf571e47de13a1205a6e67ad336182b02',
    '88bf695907542d939269e902477c82df11b9cf85729e933bf59d91db64c36700',
    '01a1baa1959fa4629cbd07c4b0f471fd249c52ec6c97d082eae884a8e6c25414',
    'fa89c18ad75190cae58074d8cc9d394e68a91966473ff83e55ebfb3e1ce07914',
    'c96ba2997f1245b97f6f0edfb2ed77baab08019537915cc9ea68e81835b9411e'
  ];
  i integer;
begin
  for i in 1..array_length(v_sigs,1) loop
    v_sig:=v_sigs[i];
    v_expected_sha:=v_hashes[i];
    if to_regprocedure(v_sig) is null then
      raise exception 'PentaSecurity provider-dispatch ACL v6 source/runtime drift: required function missing: %',v_sig;
    end if;
    if not (select p.prosecdef from pg_proc p where p.oid=to_regprocedure(v_sig)) then
      raise exception 'PentaSecurity provider-dispatch ACL v6 expected SECURITY DEFINER: %',v_sig;
    end if;
    if lower(pg_get_functiondef(to_regprocedure(v_sig))) not like '%set search_path%' then
      raise exception 'PentaSecurity provider-dispatch ACL v6 requires pinned search_path: %',v_sig;
    end if;
    v_actual_sha:=encode(extensions.digest(convert_to(pg_get_functiondef(to_regprocedure(v_sig)),'UTF8'),'sha256'),'hex');
    if v_actual_sha<>v_expected_sha then
      raise exception 'PentaSecurity provider-dispatch ACL v6 exact function drift: % expected % actual %',v_sig,v_expected_sha,v_actual_sha;
    end if;
  end loop;
end
$$;

revoke execute on function public.app_factory_runtime_probe_sync(text) from public, anon, authenticated;
revoke execute on function public.app_factory_signed_health_dispatch() from public, anon, authenticated;
revoke execute on function public.app_factory_source_authority_gate_sync(text) from public, anon, authenticated;
revoke execute on function public.app_factory_tls_gate_sync(text) from public, anon, authenticated;
revoke execute on function public.operation_clean_worker_invoke_v1() from public, anon, authenticated;
revoke execute on function public.penta_drive_acl_bootstrap_invoke_v1(text) from public, anon, authenticated;
revoke execute on function public.thrivebase_sheets_create_probe_invoke_v1() from public, anon, authenticated;

grant execute on function public.app_factory_runtime_probe_sync(text) to service_role;
grant execute on function public.app_factory_signed_health_dispatch() to service_role;
grant execute on function public.app_factory_source_authority_gate_sync(text) to service_role;
grant execute on function public.app_factory_tls_gate_sync(text) to service_role;
grant execute on function public.operation_clean_worker_invoke_v1() to service_role;
grant execute on function public.penta_drive_acl_bootstrap_invoke_v1(text) to service_role;
grant execute on function public.thrivebase_sheets_create_probe_invoke_v1() to service_role;

commit;
