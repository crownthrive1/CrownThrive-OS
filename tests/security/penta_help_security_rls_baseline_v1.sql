-- Post-apply security readback for ct.penta.security.penta-help-rls-baseline.v1.
-- Execute only after the corresponding migration is applied to a test/canary database.

do $test$
declare
  v jsonb;
begin
  v := penta_security.penta_help_rls_baseline_status_v1();

  if v->>'disposition' <> 'PASS_RLS_DENY_BY_DEFAULT_BASELINE' then
    raise exception 'PENTA_HELP_RLS_BASELINE_STATUS_FAILED:%',v;
  end if;
  if (v->>'target_count')::int <> 5 then
    raise exception 'PENTA_HELP_RLS_TARGET_COUNT_FAILED:%',v;
  end if;
  if (v->>'rls_enabled_count')::int <> 5 then
    raise exception 'PENTA_HELP_RLS_ENABLED_COUNT_FAILED:%',v;
  end if;
  if (v->>'force_rls_count')::int <> 0 then
    raise exception 'PENTA_HELP_RLS_FORCE_UNEXPECTED:%',v;
  end if;
  if (v->>'policy_count')::int <> 0 then
    raise exception 'PENTA_HELP_RLS_POLICY_UNEXPECTED:%',v;
  end if;
  if (v->>'end_user_direct_grant_count')::int <> 0 then
    raise exception 'PENTA_HELP_RLS_END_USER_GRANT_UNEXPECTED:%',v;
  end if;
  if not (v->>'role_semantics_ok')::boolean then
    raise exception 'PENTA_HELP_RLS_ROLE_SEMANTICS_FAILED:%',v;
  end if;

  if has_table_privilege('anon','penta_help.requests_v1','select')
     or has_table_privilege('authenticated','penta_help.requests_v1','select')
     or has_table_privilege('anon','penta_help.receipts_v1','select')
     or has_table_privilege('authenticated','penta_help.receipts_v1','select')
     or has_table_privilege('anon','penta_security.runtime_review_receipts_v1','select')
     or has_table_privilege('authenticated','penta_security.runtime_review_receipts_v1','select') then
    raise exception 'PENTA_HELP_RLS_DIRECT_END_USER_SELECT_UNEXPECTED';
  end if;

  if not has_function_privilege('service_role','penta_security.penta_help_rls_baseline_status_v1()','execute')
     or has_function_privilege('anon','penta_security.penta_help_rls_baseline_status_v1()','execute')
     or has_function_privilege('authenticated','penta_security.penta_help_rls_baseline_status_v1()','execute') then
    raise exception 'PENTA_HELP_RLS_STATUS_ACL_FAILED';
  end if;
end
$test$;

select penta_security.penta_help_rls_baseline_status_v1();
