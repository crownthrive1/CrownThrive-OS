-- CrownThrive OS live Command Center readback and append-only intervention ledger.
-- Provider-applied in ThriveBase as migration 20260904020559.

create table if not exists public.crownthrive_os_interventions_v1 (
  intervention_id uuid primary key default gen_random_uuid(),
  occurred_at timestamptz not null default now(),
  stage text not null check (stage in ('OBSERVE','PLAN','APPLY','READBACK')),
  visibility text not null default 'internal' check (visibility in ('internal','public')),
  target_system text not null,
  target_ref text,
  action text not null,
  state text not null,
  authority_class text,
  source_ref text,
  evidence_sha256 text,
  metadata jsonb not null default '{}'::jsonb
);

alter table public.crownthrive_os_interventions_v1 enable row level security;
revoke all on public.crownthrive_os_interventions_v1 from public, anon, authenticated;
grant select, insert on public.crownthrive_os_interventions_v1 to service_role;

create or replace function public.crownthrive_os_interventions_reject_mutation_v1()
returns trigger
language plpgsql
security invoker
set search_path = pg_catalog
as $$
begin
  raise exception 'crownthrive_os_interventions_v1 is append-only';
end;
$$;

revoke all on function public.crownthrive_os_interventions_reject_mutation_v1() from public, anon, authenticated;

drop trigger if exists crownthrive_os_interventions_append_only_v1 on public.crownthrive_os_interventions_v1;
create trigger crownthrive_os_interventions_append_only_v1
before update or delete on public.crownthrive_os_interventions_v1
for each row execute function public.crownthrive_os_interventions_reject_mutation_v1();

grant usage on schema penta_pm_fabric, pentatime, penta_runtime, chlom_runtime, communications_evidence, pentamocracy to service_role;
grant select on penta_pm_fabric.providers, penta_pm_fabric.routes to service_role;
grant select on pentatime.operation_state_v2, pentatime.wake_requests_v1 to service_role;
grant select on penta_runtime.penta_super_runs_v1, penta_runtime.remediation_execution_queue_v1 to service_role;
grant select on chlom_runtime.dail_system_registry_v1, chlom_runtime.dail_event_lanes_v1 to service_role;
grant select on communications_evidence.lifecycle_events_v1 to service_role;
grant select on pentamocracy.activation_receipts_v1 to service_role;

create or replace function public.crownthrive_os_live_readback_v1(
  p_window_hours integer default 24,
  p_limit integer default 160
)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog
as $$
declare
  v_hours integer := least(greatest(coalesce(p_window_hours,24),1),168);
  v_limit integer := least(greatest(coalesce(p_limit,160),20),500);
  v_cutoff timestamptz := now() - make_interval(hours => least(greatest(coalesce(p_window_hours,24),1),168));
  v_ledger jsonb := '[]'::jsonb;
  v_providers jsonb := '[]'::jsonb;
  v_routes jsonb := '[]'::jsonb;
  v_operations jsonb := '[]'::jsonb;
  v_interventions jsonb := '[]'::jsonb;
  v_dail jsonb := '[]'::jsonb;
  v_stats jsonb := '{}'::jsonb;
begin
  select coalesce(jsonb_agg(to_jsonb(q) order by q.occurred_at desc), '[]'::jsonb)
  into v_ledger
  from (
    select * from (
      select received_at as occurred_at,
             'PentaFabric'::text as source,
             coalesce(protocol,'PentaFabric')::text as protocol,
             coalesce(route,'unknown')::text as route,
             coalesce(lane,'unknown')::text as lane,
             penta_id::text as penta,
             trace_id::text as trace,
             'PERSISTED'::text as state,
             left(coalesce(integrity_digest,''),16)::text as evidence,
             'D2'::text as authority,
             'public'::text as visibility
      from public.pentafabric_events
      where received_at >= v_cutoff
      order by received_at desc
      limit v_limit
    ) a
    union all
    select * from (
      select coalesce(completed_at,started_at,created_at) as occurred_at,
             'PentaRuntime'::text as source,
             'PentaSuperRun'::text as protocol,
             execution_key::text as route,
             coalesce(cycle_id,'runtime')::text as lane,
             null::text as penta,
             run_id::text as trace,
             coalesce(status,'UNKNOWN')::text as state,
             left(coalesce(dail_event_id,''),16)::text as evidence,
             'D2'::text as authority,
             'internal'::text as visibility
      from penta_runtime.penta_super_runs_v1
      where coalesce(completed_at,started_at,created_at) >= v_cutoff
      order by coalesce(completed_at,started_at,created_at) desc
      limit v_limit
    ) b
    union all
    select * from (
      select updated_at as occurred_at,
             'PentaTime'::text as source,
             'PentaTimeWake'::text as protocol,
             coalesce(target_kind,'unknown')::text as route,
             coalesce(source_system_key,'scheduler')::text as lane,
             case when lower(coalesce(target_kind,'')) like '%penta%' then target_ref else null end::text as penta,
             request_id::text as trace,
             coalesce(state,'UNKNOWN')::text as state,
             left(coalesce(packet_id::text,''),16)::text as evidence,
             coalesce(authority_class,'D1')::text as authority,
             'internal'::text as visibility
      from pentatime.wake_requests_v1
      where updated_at >= v_cutoff
      order by updated_at desc
      limit v_limit
    ) c
    union all
    select * from (
      select updated_at as occurred_at,
             'PentaRemediation'::text as source,
             'PentaRemediation'::text as protocol,
             coalesce(target_ref,'unknown')::text as route,
             coalesce(lane,'remediation')::text as lane,
             null::text as penta,
             execution_id::text as trace,
             coalesce(state,'UNKNOWN')::text as state,
             left(coalesce(dail_event_id::text,head_sha,''),16)::text as evidence,
             case when lower(coalesce(risk,'')) in ('critical','high') then 'D2' else 'D1' end::text as authority,
             'internal'::text as visibility
      from penta_runtime.remediation_execution_queue_v1
      where updated_at >= v_cutoff
      order by updated_at desc
      limit v_limit
    ) d
    union all
    select * from (
      select occurred_at,
             'CrownThriveOS'::text as source,
             ('Intervention.' || stage)::text as protocol,
             coalesce(target_system,'unknown')::text as route,
             coalesce(target_ref,'control-plane')::text as lane,
             null::text as penta,
             intervention_id::text as trace,
             state::text,
             left(coalesce(evidence_sha256,''),16)::text as evidence,
             coalesce(authority_class,'D1')::text as authority,
             visibility::text
      from public.crownthrive_os_interventions_v1
      where occurred_at >= v_cutoff
      order by occurred_at desc
      limit v_limit
    ) e
    union all
    select * from (
      select created_at as occurred_at,
             'CommunicationsEvidence'::text as source,
             'EvidenceLifecycle'::text as protocol,
             concat_ws('→',from_state,to_state)::text as route,
             coalesce(authority_basis,'evidence')::text as lane,
             null::text as penta,
             lifecycle_event_id::text as trace,
             coalesce(to_state,'UNKNOWN')::text as state,
             left(coalesce(dail_event_id::text,evidence_id::text,''),16)::text as evidence,
             coalesce(authority_basis,'D1')::text as authority,
             'internal'::text as visibility
      from communications_evidence.lifecycle_events_v1
      where created_at >= v_cutoff
      order by created_at desc
      limit v_limit
    ) f
    union all
    select * from (
      select created_at as occurred_at,
             'Pentamocracy'::text as source,
             'PentaActivation'::text as protocol,
             coalesce(source_ref,'governance')::text as route,
             coalesce(event_type,'activation')::text as lane,
             citizen_id::text as penta,
             receipt_id::text as trace,
             coalesce(state,'UNKNOWN')::text as state,
             left(coalesce(digest,''),16)::text as evidence,
             'D3'::text as authority,
             'internal'::text as visibility
      from pentamocracy.activation_receipts_v1
      where created_at >= v_cutoff
      order by created_at desc
      limit v_limit
    ) g
    union all
    select * from (
      select e.assigned_at as occurred_at,
             'DAIL'::text as source,
             'DAIL.Highwater'::text as protocol,
             s.system_key::text as route,
             coalesce(e.lane_class,s.lane_class,'evidence')::text as lane,
             null::text as penta,
             e.event_id::text as trace,
             coalesce(s.state,'UNKNOWN')::text as state,
             e.sequence_id::text as evidence,
             coalesce(s.authority_ceiling,'D1')::text as authority,
             'internal'::text as visibility
      from chlom_runtime.dail_system_registry_v1 s
      left join lateral (
        select d.event_id,d.sequence_id,d.lane_class,d.assigned_at
        from chlom_runtime.dail_event_lanes_v1 d
        where d.system_key=s.system_key
        order by d.sequence_id desc
        limit 1
      ) e on true
      where e.assigned_at is not null
    ) h
    order by occurred_at desc
    limit v_limit
  ) q;

  select coalesce(jsonb_agg(to_jsonb(q) order by q.provider_key), '[]'::jsonb)
  into v_providers
  from (
    select p.provider_key,p.provider_class,p.protocol_version,p.authority_mode,p.state,
           p.last_probe_at,p.updated_at,
           (select count(*) from penta_pm_fabric.routes r where r.provider_key=p.provider_key) as route_count
    from penta_pm_fabric.providers p
    order by p.provider_key
  ) q;

  select coalesce(jsonb_agg(to_jsonb(q) order by q.route_key), '[]'::jsonb)
  into v_routes
  from (
    select route_key,provider_key,protocol,transport,state,updated_at
    from penta_pm_fabric.routes
    order by route_key
  ) q;

  select coalesce(jsonb_agg(to_jsonb(q) order by q.updated_at desc), '[]'::jsonb)
  into v_operations
  from (
    select operation_key,run_count,success_count,deferred_count,failure_count,
           consecutive_deferrals,last_state,last_started_at,last_completed_at,last_failed_at,backoff_until,updated_at
    from pentatime.operation_state_v2
    order by updated_at desc
    limit v_limit
  ) q;

  select coalesce(jsonb_agg(to_jsonb(q) order by q.occurred_at desc), '[]'::jsonb)
  into v_interventions
  from (
    select occurred_at,'os_intervention'::text as source,intervention_id::text as id,stage,visibility,target_system,target_ref,action,state,authority_class,source_ref,left(coalesce(evidence_sha256,''),16) as evidence,metadata
    from public.crownthrive_os_interventions_v1
    where occurred_at >= v_cutoff
    union all
    select updated_at,'remediation_queue'::text as source,execution_id::text as id,'APPLY'::text as stage,'internal'::text as visibility,
           'penta_runtime.remediation_execution_queue_v1'::text as target_system,target_ref,
           'remediation_execution'::text as action,state,
           case when lower(coalesce(risk,'')) in ('critical','high') then 'D2' else 'D1' end::text as authority_class,
           case when pr_number is not null then 'github:pr:'||pr_number::text when issue_number is not null then 'github:issue:'||issue_number::text else null end::text as source_ref,
           left(coalesce(dail_event_id::text,head_sha,''),16)::text as evidence,
           jsonb_build_object('risk',risk,'issue_number',issue_number,'pr_number',pr_number,'attempt_count',attempt_count,'has_error',last_error is not null) as metadata
    from penta_runtime.remediation_execution_queue_v1
    where updated_at >= v_cutoff
    order by occurred_at desc
    limit v_limit
  ) q;

  select coalesce(jsonb_agg(to_jsonb(q) order by q.system_key), '[]'::jsonb)
  into v_dail
  from (
    select s.system_key,s.canonical_name,s.lane_class,s.authority_ceiling,s.state,
           e.event_id,e.sequence_id,e.assigned_at
    from chlom_runtime.dail_system_registry_v1 s
    left join lateral (
      select d.event_id,d.sequence_id,d.assigned_at
      from chlom_runtime.dail_event_lanes_v1 d
      where d.system_key=s.system_key
      order by d.sequence_id desc
      limit 1
    ) e on true
    order by s.system_key
  ) q;

  select jsonb_build_object(
    'penta_events_window',(select count(*) from public.pentafabric_events where received_at >= v_cutoff),
    'penta_super_runs_window',(select count(*) from penta_runtime.penta_super_runs_v1 where coalesce(completed_at,started_at,created_at) >= v_cutoff),
    'wake_requests_window',(select count(*) from pentatime.wake_requests_v1 where updated_at >= v_cutoff),
    'remediation_window',(select count(*) from penta_runtime.remediation_execution_queue_v1 where updated_at >= v_cutoff),
    'interventions_window',(select count(*) from public.crownthrive_os_interventions_v1 where occurred_at >= v_cutoff),
    'registered_providers',(select count(*) from penta_pm_fabric.providers),
    'active_providers',(select count(*) from penta_pm_fabric.providers where lower(state) like '%production%' or lower(state) like '%connected%' or lower(state)='active'),
    'registered_routes',(select count(*) from penta_pm_fabric.routes),
    'active_routes',(select count(*) from penta_pm_fabric.routes where lower(state) like '%production%' or lower(state) like '%connected%' or lower(state)='active'),
    'dail_systems',(select count(*) from chlom_runtime.dail_system_registry_v1),
    'dail_active_systems',(select count(*) from chlom_runtime.dail_system_registry_v1 where lower(state)='active'),
    'operation_count',(select count(*) from pentatime.operation_state_v2)
  ) into v_stats;

  return jsonb_build_object(
    'schema','ct.crownthrive.os.live-readback.v1',
    'status','OPERATIONAL',
    'window_hours',v_hours,
    'window_start',v_cutoff,
    'generated_at',now(),
    'stats',v_stats,
    'ledger',v_ledger,
    'providers',v_providers,
    'routes',v_routes,
    'operations',v_operations,
    'interventions',v_interventions,
    'dail',v_dail,
    'public_safe',true,
    'secret_material_exposed',false
  );
end;
$$;

revoke all on function public.crownthrive_os_live_readback_v1(integer,integer) from public, anon, authenticated;
grant execute on function public.crownthrive_os_live_readback_v1(integer,integer) to service_role;
