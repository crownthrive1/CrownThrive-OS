-- Normalize captured intervention lifecycle stages and D1/D2/D3 authority classes.
-- Provider-applied in ThriveBase as migration 20260904022611.

create or replace function public.crownthrive_os_intervention_history_v1(p_limit integer default 500)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog
as $$
declare
  v_limit integer := least(greatest(coalesce(p_limit,500),20),1000);
  v_rows jsonb := '[]'::jsonb;
begin
  select coalesce(jsonb_agg(to_jsonb(q) order by q.occurred_at desc), '[]'::jsonb)
  into v_rows
  from (
    select occurred_at,
           'os_intervention'::text as source,
           intervention_id::text as id,
           stage,
           visibility,
           target_system,
           target_ref,
           action,
           state,
           authority_class,
           source_ref,
           left(coalesce(evidence_sha256,''),16) as evidence,
           metadata
    from public.crownthrive_os_interventions_v1

    union all

    select updated_at as occurred_at,
           'remediation_queue'::text as source,
           execution_id::text as id,
           case
             when upper(coalesce(state,'')) in ('VERIFIED','SUCCEEDED','COMPLETED','CLOSED') then 'READBACK'
             when upper(coalesce(state,'')) in ('RUNNING','EXECUTING','APPLYING') then 'APPLY'
             when upper(coalesce(state,'')) in ('QUEUED','READY','CLAIMED','PENDING') then 'PLAN'
             else 'OBSERVE'
           end::text as stage,
           'internal'::text as visibility,
           'penta_runtime.remediation_execution_queue_v1'::text as target_system,
           target_ref,
           'remediation_execution'::text as action,
           state,
           case
             when upper(coalesce(risk,'')) in ('D1','D2','D3') then upper(risk)
             when upper(coalesce(risk,'')) in ('CRITICAL','HIGH') then 'D2'
             else 'D1'
           end::text as authority_class,
           case
             when pr_number is not null then 'github:pr:'||pr_number::text
             when issue_number is not null then 'github:issue:'||issue_number::text
             else null
           end::text as source_ref,
           left(coalesce(dail_event_id::text,head_sha,''),16)::text as evidence,
           jsonb_build_object(
             'risk',risk,
             'issue_number',issue_number,
             'pr_number',pr_number,
             'attempt_count',attempt_count,
             'has_error',last_error is not null
           ) as metadata
    from penta_runtime.remediation_execution_queue_v1
    order by occurred_at desc
    limit v_limit
  ) q;

  return jsonb_build_object(
    'schema','ct.crownthrive.os.intervention-history.v1',
    'status','OPERATIONAL',
    'count',jsonb_array_length(v_rows),
    'rows',v_rows,
    'generated_at',now(),
    'public_safe',true,
    'secret_material_exposed',false
  );
end;
$$;

revoke all on function public.crownthrive_os_intervention_history_v1(integer) from public, anon, authenticated;
grant execute on function public.crownthrive_os_intervention_history_v1(integer) to service_role;
