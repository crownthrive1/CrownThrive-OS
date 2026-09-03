-- Deterministic/negative/adversarial acceptance for PR #1962 App Factory provider/control ACL expansion v5.
-- Run after the candidate migration has been applied to the test database.

do $$
declare
  v_sig text;
  v_def text;
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
      raise exception 'required App Factory provider/control security target missing: %', v_sig;
    end if;
    if has_function_privilege('public',to_regprocedure(v_sig),'EXECUTE') then
      raise exception 'PUBLIC must not execute App Factory provider/control target: %', v_sig;
    end if;
    if has_function_privilege('anon',to_regprocedure(v_sig),'EXECUTE') then
      raise exception 'anon must not execute App Factory provider/control target: %', v_sig;
    end if;
    if has_function_privilege('authenticated',to_regprocedure(v_sig),'EXECUTE') then
      raise exception 'authenticated must not execute App Factory provider/control target: %', v_sig;
    end if;
    if not has_function_privilege('service_role',to_regprocedure(v_sig),'EXECUTE') then
      raise exception 'service_role must retain App Factory provider/control execution: %', v_sig;
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
  'contract','ct.penta.security.app-factory-provider-control-acl-expansion.v5',
  'targets',14,
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
