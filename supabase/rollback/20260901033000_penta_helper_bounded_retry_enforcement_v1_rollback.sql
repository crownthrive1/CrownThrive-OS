-- Fail-closed recovery for PentaHelper bounded retry enforcement v1.
-- The pre-repair behavior is a known production defect: exhausted requests can be selected
-- again and can grow far beyond max_attempts. Recovery must never restore that vulnerable
-- scheduler shape. If the forward implementation must be withdrawn, disable autonomous
-- PentaHelper task preparation while preserving request/evidence history for governed repair.

create or replace function public.penta_helper_prepare_cycle_v1(p_limit integer default 2)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'penta_help'
as $function$
begin
  return jsonb_build_object(
    'state','recovery_hold',
    'reason','PENTA_HELP_AUTONOMOUS_RETRY_DISABLED_FAIL_CLOSED',
    'tasks','[]'::jsonb,
    'task_count',0,
    'max_requested',greatest(1,least(coalesce(p_limit,2),2)),
    'automatic_retry_enabled',false,
    'authority_created',false,
    'at',clock_timestamp()
  );
end
$function$;

revoke all on function public.penta_helper_prepare_cycle_v1(integer)
  from public, anon, authenticated;
grant execute on function public.penta_helper_prepare_cycle_v1(integer)
  to service_role;

comment on function public.penta_helper_prepare_cycle_v1(integer) is
'Fail-closed PentaHelper recovery mode. Autonomous task preparation is disabled rather than restoring the known unbounded-retry defect.';

DO $readback$
DECLARE
  v_result jsonb;
BEGIN
  v_result:=public.penta_helper_prepare_cycle_v1(2);
  IF v_result->>'state' <> 'recovery_hold'
     OR coalesce((v_result->>'automatic_retry_enabled')::boolean,true)
     OR coalesce((v_result->>'task_count')::integer,-1) <> 0 THEN
    RAISE EXCEPTION 'PENTA_HELP_FAIL_CLOSED_RECOVERY_READBACK_FAILED:%',v_result;
  END IF;
  IF has_function_privilege('anon','public.penta_helper_prepare_cycle_v1(integer)','EXECUTE')
     OR has_function_privilege('authenticated','public.penta_helper_prepare_cycle_v1(integer)','EXECUTE')
     OR NOT has_function_privilege('service_role','public.penta_helper_prepare_cycle_v1(integer)','EXECUTE') THEN
    RAISE EXCEPTION 'PENTA_HELP_FAIL_CLOSED_RECOVERY_ACL_FAILED';
  END IF;
END
$readback$;
