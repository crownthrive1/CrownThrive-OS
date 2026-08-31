-- CrownThrive CHLOM / PentaSecurity
-- Direct-callable SECURITY DEFINER App Factory authority-surface hardening v4.
--
-- Fresh ThriveBase runtime readback on 2026-08-31 proved the targets below are
-- SECURITY DEFINER, directly callable by anon/authenticated through public schema
-- reachability, and lack an explicit caller/service-role guard in their function
-- bodies. This cohort prioritizes authority-bearing release/certification/evidence
-- mutation and vaulted provider/GitHub dispatch surfaces instead of expanding raw
-- census counts.
--
-- Authority boundary: ACL-only. Function bodies, vaulted values, provider state,
-- release state, credentials, D3/sovereign authority, money and rights/legal state
-- are not modified by this migration.

begin;

do $$
declare
  v_sig text;
  v_required text[] := array[
    'public.app_factory_merge_receipt_pr(text,text,boolean)',
    'public.app_factory_publish_final_release_receipts()',
    'public.app_factory_certify_release(text)',
    'public.app_factory_certify_if_evidenced()',
    'public.app_factory_recertify_after_root_route(text)',
    'public.app_factory_recertify_v1_2(text)',
    'public.app_factory_closeout_gate_upsert(text,text,text,jsonb)',
    'public.app_factory_android_canary_upsert(jsonb)',
    'public.app_factory_collect_edge_responses(text)',
    'public.app_factory_android_canary_reconcile()',
    'public.app_factory_android_canary_status_sync()',
    'public.app_factory_android_canary_sync()',
    'public.app_factory_github_canary_reconcile()',
    'public.app_factory_github_canary_retry()',
    'public.app_factory_institutionalize_recertification_dispatch()',
    'public.app_factory_merge_recertification_dispatch()',
    'public.app_factory_operational_cleanup_dispatch(text)',
    'public.app_factory_provider_finalize_sync()'
  ];
begin
  foreach v_sig in array v_required loop
    if to_regprocedure(v_sig) is null then
      raise exception 'PentaSecurity App Factory authority ACL expansion source/runtime drift: required function missing: %', v_sig;
    end if;
    if not (select p.prosecdef from pg_proc p where p.oid=to_regprocedure(v_sig)) then
      raise exception 'PentaSecurity App Factory authority ACL expansion expected SECURITY DEFINER function: %', v_sig;
    end if;
    if lower(pg_get_functiondef(to_regprocedure(v_sig))) not like '%set search_path%' then
      raise exception 'PentaSecurity App Factory authority ACL expansion requires pinned search_path: %', v_sig;
    end if;
  end loop;
end
$$;

revoke execute on function public.app_factory_merge_receipt_pr(text,text,boolean) from public, anon, authenticated;
revoke execute on function public.app_factory_publish_final_release_receipts() from public, anon, authenticated;
revoke execute on function public.app_factory_certify_release(text) from public, anon, authenticated;
revoke execute on function public.app_factory_certify_if_evidenced() from public, anon, authenticated;
revoke execute on function public.app_factory_recertify_after_root_route(text) from public, anon, authenticated;
revoke execute on function public.app_factory_recertify_v1_2(text) from public, anon, authenticated;
revoke execute on function public.app_factory_closeout_gate_upsert(text,text,text,jsonb) from public, anon, authenticated;
revoke execute on function public.app_factory_android_canary_upsert(jsonb) from public, anon, authenticated;
revoke execute on function public.app_factory_collect_edge_responses(text) from public, anon, authenticated;
revoke execute on function public.app_factory_android_canary_reconcile() from public, anon, authenticated;
revoke execute on function public.app_factory_android_canary_status_sync() from public, anon, authenticated;
revoke execute on function public.app_factory_android_canary_sync() from public, anon, authenticated;
revoke execute on function public.app_factory_github_canary_reconcile() from public, anon, authenticated;
revoke execute on function public.app_factory_github_canary_retry() from public, anon, authenticated;
revoke execute on function public.app_factory_institutionalize_recertification_dispatch() from public, anon, authenticated;
revoke execute on function public.app_factory_merge_recertification_dispatch() from public, anon, authenticated;
revoke execute on function public.app_factory_operational_cleanup_dispatch(text) from public, anon, authenticated;
revoke execute on function public.app_factory_provider_finalize_sync() from public, anon, authenticated;

grant execute on function public.app_factory_merge_receipt_pr(text,text,boolean) to service_role;
grant execute on function public.app_factory_publish_final_release_receipts() to service_role;
grant execute on function public.app_factory_certify_release(text) to service_role;
grant execute on function public.app_factory_certify_if_evidenced() to service_role;
grant execute on function public.app_factory_recertify_after_root_route(text) to service_role;
grant execute on function public.app_factory_recertify_v1_2(text) to service_role;
grant execute on function public.app_factory_closeout_gate_upsert(text,text,text,jsonb) to service_role;
grant execute on function public.app_factory_android_canary_upsert(jsonb) to service_role;
grant execute on function public.app_factory_collect_edge_responses(text) to service_role;
grant execute on function public.app_factory_android_canary_reconcile() to service_role;
grant execute on function public.app_factory_android_canary_status_sync() to service_role;
grant execute on function public.app_factory_android_canary_sync() to service_role;
grant execute on function public.app_factory_github_canary_reconcile() to service_role;
grant execute on function public.app_factory_github_canary_retry() to service_role;
grant execute on function public.app_factory_institutionalize_recertification_dispatch() to service_role;
grant execute on function public.app_factory_merge_recertification_dispatch() to service_role;
grant execute on function public.app_factory_operational_cleanup_dispatch(text) to service_role;
grant execute on function public.app_factory_provider_finalize_sync() to service_role;

commit;
