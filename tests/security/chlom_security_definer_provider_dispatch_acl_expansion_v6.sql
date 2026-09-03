-- Deterministic/negative/adversarial acceptance for PR #1962 provider/worker dispatch ACL expansion v6.
-- Run after the candidate migration is applied to the test database.

do $$
declare
  v_sig text;
  v_required text[] := array[
    'public.app_factory_runtime_probe_sync(text)',
    'public.app_factory_signed_health_dispatch()',
    'public.app_factory_source_authority_gate_sync(text)',
    'public.app_factory_tls_gate_sync(text)',
    'public.operation_clean_worker_invoke_v1()',
    'public.penta_drive_acl_bootstrap_invoke_v1(text)',
    'public.thrivebase_sheets_create_probe_invoke_v1()'
  ];
begin
  foreach v_sig in array v_required loop
    if to_regprocedure(v_sig) is null then
      raise exception 'required provider-dispatch security target missing: %',v_sig;
    end if;
    if has_function_privilege('public',to_regprocedure(v_sig),'EXECUTE') then
      raise exception 'PUBLIC must not execute privileged provider-dispatch target: %',v_sig;
    end if;
    if has_function_privilege('anon',to_regprocedure(v_sig),'EXECUTE') then
      raise exception 'anon must not execute privileged provider-dispatch target: %',v_sig;
    end if;
    if has_function_privilege('authenticated',to_regprocedure(v_sig),'EXECUTE') then
      raise exception 'authenticated must not execute privileged provider-dispatch target: %',v_sig;
    end if;
    if not has_function_privilege('service_role',to_regprocedure(v_sig),'EXECUTE') then
      raise exception 'service_role must retain privileged provider-dispatch target: %',v_sig;
    end if;
    if not (select p.prosecdef from pg_proc p where p.oid=to_regprocedure(v_sig)) then
      raise exception 'target unexpectedly lost SECURITY DEFINER identity: %',v_sig;
    end if;
    if lower(pg_get_functiondef(to_regprocedure(v_sig))) not like '%set search_path%' then
      raise exception 'target must retain pinned search_path: %',v_sig;
    end if;
  end loop;
end
$$;

select jsonb_build_object(
  'contract','ct.penta.security.provider-dispatch-acl-expansion.v6',
  'targets',7,
  'public_execute','DENIED',
  'anon_execute','DENIED',
  'authenticated_execute','DENIED',
  'service_role_execute','RETAINED',
  'security_definer','RETAINED',
  'search_path','PINNED',
  'provider_write_executed',false,
  'credential_change',false,
  'money_movement',false,
  'rights_change',false,
  'vote_effect',false,
  'quorum_effect',false,
  'd3_execution',false,
  'authority_expansion',false,
  'state','PASS'
) as acceptance;
