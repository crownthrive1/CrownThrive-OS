-- Retire duplicate Penta external scheduler clocks after production-native
-- executors were independently read back healthy. Connector clocks do not own
-- internal PentaMail/PentaOD/PentaHeartbeat or vendor-version execution.

begin;

do $$
begin
  if (select count(*) from cron.job where active and jobname in (
      'penta-mail-state-architecture-hourly-v1',
      'penta-mail-outage-watch-v1',
      'penta-mail-outbox-dispatch-v1',
      'pentaod-reconcile-v1',
      'pentaod-heartbeat-v1',
      'penta-hourly-update-policy-enforcer-v1'
    )) <> 6 then
    raise exception 'required production-native Penta hourly executors are not all active';
  end if;

  if not exists (
    select 1 from chlom_runtime.agent_schedule_definitions
    where schedule_id='ct.schedule.version-threat.daily'
      and execution_state='active'
      and external_task_id='6a8620e935cc8191bbd31075e12dd22a'
      and metadata->>'canonical_parent_external_relay'='ct.schedule.external-evidence-relay.hourly.v1'
  ) then
    raise exception 'canonical version/vendor watch relay subroute is not active';
  end if;
end $$;

update chlom_runtime.scheduler_topology_v1
set metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'penta_hourly_delivery_external_task_id', '6a8f4c2dcc4c8191b14c35e5d175746b',
      'penta_hourly_delivery_external_state', 'RETIRED_SCHEDULING_SCAFFOLDING',
      'penta_hourly_delivery_internal_executors', jsonb_build_array(
        'pg_cron:penta-mail-state-architecture-hourly-v1',
        'pg_cron:penta-mail-outage-watch-v1',
        'pg_cron:penta-mail-outbox-dispatch-v1',
        'pg_cron:pentaod-reconcile-v1',
        'pg_cron:pentaod-heartbeat-v1',
        'pg_cron:penta-hourly-update-policy-enforcer-v1'
      ),
      'penta_reward_v5_review_external_task_id', '6a8f35f2b2a08191880db18a15bfa5b3',
      'penta_reward_v5_review_external_state', 'RETIRED_SCHEDULING_SCAFFOLDING',
      'penta_reward_v5_review_successor', 'ct.schedule.version-threat.daily via ct.schedule.external-evidence-relay.hourly.v1',
      'external_automation_connector_readback', 'both retired tasks disabled 2026-08-26',
      'retired_penta_external_clocks_reconciled_at', now(),
      'authority_expansion', false,
      'history_policy', 'append_or_supersede_never_silent_delete'
    )
where topology_id='ct.scheduler-topology.production.v1';

with evidence_doc as (
  select jsonb_build_object(
    'topology_id','ct.scheduler-topology.production.v1',
    'decision','RETIRED_DUPLICATE_EXTERNAL_CLOCKS',
    'retired_external_tasks',jsonb_build_array(
      jsonb_build_object(
        'task_id','6a8f4c2dcc4c8191b14c35e5d175746b',
        'disposition','RETIRED_SCHEDULING_SCAFFOLDING',
        'connector_readback_enabled',false,
        'successor','production-native PentaMail/PentaOD/PentaHeartbeat pg_cron fabric'
      ),
      jsonb_build_object(
        'task_id','6a8f35f2b2a08191880db18a15bfa5b3',
        'disposition','RETIRED_SCHEDULING_SCAFFOLDING',
        'connector_readback_enabled',false,
        'successor','ct.schedule.version-threat.daily via canonical external evidence relay'
      )
    ),
    'authority_expansion',false,
    'provider_write',false,
    'money_movement',false,
    'd3',false,
    'history_policy','append_or_supersede_never_silent_delete'
  ) as body
)
insert into chlom_runtime.scheduler_topology_receipts_v1(
  receipt_id,topology_id,receipt_type,decision,evidence_digest_sha256,evidence,actor_id,authority_ref
)
select gen_random_uuid(),
       'ct.scheduler-topology.production.v1',
       'EXTERNAL_CLOCK_RETIREMENT',
       'INFO',
       encode(digest(body::text,'sha256'),'hex'),
       body,
       'ct.ops.agent.vendor-engine-watch',
       'founder-directive-2026-08-26-current-topology-reconciliation'
from evidence_doc;

commit;
