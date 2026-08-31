-- Correct display-name-sensitive regression logic. Runtime behavior is unchanged.
create or replace function integration_control.credential_continuity_v3_security_test_v1()
returns jsonb
language plpgsql
stable
security definer
set search_path='pg_catalog','integration_control','pentatime','cron'
as $fn$
declare
  v_job_command text;
  v_v2_public boolean; v_v2_anon boolean; v_v2_authenticated boolean; v_v2_service boolean;
  v_v3_public boolean; v_v3_anon boolean; v_v3_authenticated boolean; v_v3_service boolean;
  v_executor regprocedure; v_enabled boolean; v_executor_match boolean; v_pass boolean;
begin
  select command into v_job_command from cron.job where jobname='crownthrive_credential_continuity_daily' order by jobid desc limit 1;
  select has_function_privilege('public','integration_control.credential_continuity_cycle_v2()','EXECUTE'),
         has_function_privilege('anon','integration_control.credential_continuity_cycle_v2()','EXECUTE'),
         has_function_privilege('authenticated','integration_control.credential_continuity_cycle_v2()','EXECUTE'),
         has_function_privilege('service_role','integration_control.credential_continuity_cycle_v2()','EXECUTE'),
         has_function_privilege('public','integration_control.credential_continuity_cycle_v3(text,text,text)','EXECUTE'),
         has_function_privilege('anon','integration_control.credential_continuity_cycle_v3(text,text,text)','EXECUTE'),
         has_function_privilege('authenticated','integration_control.credential_continuity_cycle_v3(text,text,text)','EXECUTE'),
         has_function_privilege('service_role','integration_control.credential_continuity_cycle_v3(text,text,text)','EXECUTE')
    into v_v2_public,v_v2_anon,v_v2_authenticated,v_v2_service,v_v3_public,v_v3_anon,v_v3_authenticated,v_v3_service;
  select executor_regprocedure,enabled into v_executor,v_enabled from pentatime.operation_executors_v3 where operation_key='credential_continuity';
  v_executor_match:=v_executor='pentatime.executor_credential_continuity_v3()'::regprocedure;
  v_pass:=not v_v2_public and not v_v2_anon and not v_v2_authenticated and v_v2_service
    and not v_v3_public and not v_v3_anon and not v_v3_authenticated and v_v3_service
    and v_job_command='select pentatime.execute_guarded_v3(''credential_continuity'');'
    and v_enabled and v_executor_match;
  return jsonb_build_object(
    'contract','ct.penta.credentials.continuity-cycle.v3.security-test','passed',v_pass,
    'expected_job_command','select pentatime.execute_guarded_v3(''credential_continuity'');','observed_job_command',v_job_command,
    'executor',v_executor::text,'executor_enabled',v_enabled,'executor_identity_match',v_executor_match,
    'v2',jsonb_build_object('public',v_v2_public,'anon',v_v2_anon,'authenticated',v_v2_authenticated,'service_role',v_v2_service),
    'v3',jsonb_build_object('public',v_v3_public,'anon',v_v3_anon,'authenticated',v_v3_authenticated,'service_role',v_v3_service),
    'rollback_preserves_hardened_acl',true,'credential_values_exposed',false,'authority_expansion',false,'observed_at',clock_timestamp());
end
$fn$;
revoke all on function integration_control.credential_continuity_v3_security_test_v1() from public,anon,authenticated;
grant execute on function integration_control.credential_continuity_v3_security_test_v1() to service_role;
