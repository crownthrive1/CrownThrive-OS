-- CrownThrive COS V1 / PentaDND execution privilege hardening.
-- Preserve internal pg_cron/service-role execution while removing generic API callers.

do $$
declare
  v_source_ref constant text := 'ct.penta.dnd.execution-privilege-hardening.v1';
  v_receipt uuid;
begin
  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta-dnd:privilege-hardening',0)) then
    raise exception 'penta_dnd_privilege_hardening_contention';
  end if;

  revoke all on schema penta_dnd from public, anon, authenticated;
  grant usage on schema penta_dnd to service_role;

  revoke all on all tables in schema penta_dnd from public, anon, authenticated;
  grant select, insert, update on all tables in schema penta_dnd to service_role;

  revoke execute on all functions in schema penta_dnd from public, anon, authenticated;
  grant execute on all functions in schema penta_dnd to service_role;

  revoke execute on function public.penta_dnd_hourly_orchestrator_v1() from public, anon, authenticated;
  revoke execute on function public.penta_dnd_status_v1() from public, anon, authenticated;
  revoke execute on function public.penta_dnd_preflight_v1(text,text,text,text,boolean,boolean,boolean) from public, anon, authenticated;

  grant execute on function public.penta_dnd_hourly_orchestrator_v1() to service_role;
  grant execute on function public.penta_dnd_status_v1() to service_role;
  grant execute on function public.penta_dnd_preflight_v1(text,text,text,text,boolean,boolean,boolean) to service_role;

  alter function public.penta_dnd_hourly_orchestrator_v1() set search_path = pg_catalog, penta_dnd;
  alter function public.penta_dnd_status_v1() set search_path = pg_catalog, penta_dnd;
  alter function public.penta_dnd_preflight_v1(text,text,text,text,boolean,boolean,boolean) set search_path = pg_catalog, penta_dnd;

  alter default privileges for role postgres in schema penta_dnd revoke all on tables from public, anon, authenticated;
  alter default privileges for role postgres in schema penta_dnd grant select, insert, update on tables to service_role;
  alter default privileges for role postgres in schema penta_dnd revoke execute on functions from public, anon, authenticated;
  alter default privileges for role postgres in schema penta_dnd grant execute on functions to service_role;

  update penta_dnd.programs_v1
     set metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
       'execution_privilege_state','internal_only',
       'execution_roles',jsonb_build_array('postgres','service_role'),
       'api_anon_execute',false,
       'api_authenticated_execute',false,
       'privilege_hardening_source_ref',v_source_ref,
       'privilege_hardened_at',clock_timestamp()
     ),
     updated_at = clock_timestamp()
   where program_id='ct.program.cos-v1.hourly-convergence-dnd';

  v_receipt := penta_dnd.append_receipt_v1(
    'ct.program.cos-v1.hourly-convergence-dnd',null,null,
    'security.execution-privileges.hardened','penta.dnd',
    jsonb_build_object(
      'source_ref',v_source_ref,
      'public_wrappers',jsonb_build_array(
        'public.penta_dnd_hourly_orchestrator_v1()',
        'public.penta_dnd_status_v1()',
        'public.penta_dnd_preflight_v1(text,text,text,text,boolean,boolean,boolean)'
      ),
      'revoked_from',jsonb_build_array('PUBLIC','anon','authenticated'),
      'retained_for',jsonb_build_array('postgres','service_role'),
      'pg_cron_preserved',true,
      'global_maintenance_required',false,
      'authority_created',false,
      'd3_human_reserved',true,
      'no_silent_delete',true,
      'observed_at',clock_timestamp()
    )
  );
end
$$;
