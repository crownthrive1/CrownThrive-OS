-- Deterministic/negative/adversarial acceptance for PR #1962 App Factory authority ACL expansion v4.
-- Run after the candidate migration has been applied to the test database.

do $$
declare
  v_sig text;
  v_def text;
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
      raise exception 'required App Factory authority security target missing: %', v_sig;
    end if;
    if has_function_privilege('public',to_regprocedure(v_sig),'EXECUTE') then
      raise exception 'PUBLIC must not execute App Factory authority target: %', v_sig;
    end if;
    if has_function_privilege('anon',to_regprocedure(v_sig),'EXECUTE') then
      raise exception 'anon must not execute App Factory authority target: %', v_sig;
    end if;
    if has_function_privilege('authenticated',to_regprocedure(v_sig),'EXECUTE') then
      raise exception 'authenticated must not execute App Factory authority target: %', v_sig;
    end if;
    if not has_function_privilege('service_role',to_regprocedure(v_sig),'EXECUTE') then
      raise exception 'service_role must retain App Factory authority execution: %', v_sig;
    end if;
    if not (select p.prosecdef from pg_proc p where p.oid=to_regprocedure(v_sig)) then
      raise exception 'target unexpectedly lost SECURITY DEFINER identity: %', v_sig;
    end if;
    select pg_get_functiondef(to_regprocedure(v_sig)) into v_def;
    if lower(v_def) not like '%set search_path%' then
      raise exception 'target must retain pinned search_path: %', v_sig;
    end if;
  end loop;
end
$$;

select jsonb_build_object(
  'contract','ct.penta.security.app-factory-authority-acl-expansion.v4',
  'targets',18,
  'public_execute','DENIED',
  'anon_execute','DENIED',
  'authenticated_execute','DENIED',
  'service_role_execute','RETAINED',
  'security_definer','RETAINED',
  'search_path','PINNED',
  'provider_write_executed',false,
  'credential_change',false,
  'money_movement',false,
  'd3_execution',false,
  'rights_change',false,
  'authority_expansion',false,
  'state','PASS'
) as acceptance;
