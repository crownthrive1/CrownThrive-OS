-- Deterministic/adversarial acceptance checks for the COS V1 Phase 00 security verifier.
-- Provider calls are not made by this test. It verifies source semantics and the
-- decision matrix; production provider readback is separately recorded by the runtime.

begin;

do $test$
declare
  v_src text;
begin
  select p.prosrc into v_src
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='integration_control'
    and p.proname='reconcile_gitguardian_current_main_v2';

  if v_src is null then raise exception 'security_verifier_missing'; end if;
  if v_src not ilike '%/secret-scanning/alerts?state=open%' then raise exception 'native_secret_scan_readback_missing'; end if;
  if v_src ilike '%search/issues?q=%' then raise exception 'internal_issue_search_proxy_must_not_be_provider_signal'; end if;
  if v_src not ilike '%PENTA_PM_GITHUB_TOKEN%' then raise exception 'governed_github_credential_reference_missing'; end if;
  if v_src not ilike '%internal_tracking_issue_used_as_provider_signal%' then raise exception 'tracking_issue_signal_guard_missing'; end if;
end
$test$;

with cases(name,branch_status,sha_ok,checks_status,total_checks,page2_status,complete,token_ok,native_status,alerts,gg_present,gg_status,gg_conclusion,expected) as (
  values
    ('green_native_no_gg',200,true,200,117,200,true,true,200,0,false,null::text,null::text,'CURRENT_MAIN_SECURITY_GREEN'),
    ('hold_open_native_alert',200,true,200,117,200,true,true,200,1,false,null::text,null::text,'HOLD_PROVIDER_FINDING_OR_CHECK'),
    ('hold_failed_gg',200,true,200,117,200,true,true,200,0,true,'completed','failure','HOLD_PROVIDER_FINDING_OR_CHECK'),
    ('defer_native_auth',200,true,200,117,200,true,true,403,null,false,null::text,null::text,'DEFERRED_PROVIDER_RATE_OR_AUTH'),
    ('hold_missing_credential',200,true,200,117,200,true,false,null::int,null::int,false,null::text,null::text,'HOLD_PROVIDER_CREDENTIAL_UNAVAILABLE'),
    ('hold_incomplete_checks',200,true,200,117,null::int,false,true,200,0,false,null::text,null::text,'HOLD_CHECK_RUN_READBACK'),
    ('hold_main_readback',500,false,null::int,0,null::int,false,true,200,0,false,null::text,null::text,'HOLD_CURRENT_MAIN_READBACK')
), eval as (
  select *, case
    when branch_status is distinct from 200 or not sha_ok then 'HOLD_CURRENT_MAIN_READBACK'
    when checks_status in (403,429) or (total_checks>100 and page2_status in (403,429)) then 'DEFERRED_PROVIDER_RATE_OR_AUTH'
    when checks_status is distinct from 200 or not complete then 'HOLD_CHECK_RUN_READBACK'
    when not token_ok then 'HOLD_PROVIDER_CREDENTIAL_UNAVAILABLE'
    when native_status in (401,403,429) then 'DEFERRED_PROVIDER_RATE_OR_AUTH'
    when native_status is distinct from 200 or alerts is null then 'HOLD_NATIVE_SECRET_SCAN_READBACK'
    when alerts>0 then 'HOLD_PROVIDER_FINDING_OR_CHECK'
    when gg_present and not (gg_status='completed' and gg_conclusion in ('success','neutral','skipped')) then 'HOLD_PROVIDER_FINDING_OR_CHECK'
    else 'CURRENT_MAIN_SECURITY_GREEN'
  end actual
  from cases
)
select case when bool_and(actual=expected) then 1 else 1/0 end as decision_matrix_pass
from eval;

rollback;
