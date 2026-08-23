-- Private service-role readback for CHLOM Wallet Continuity Factory & Automation v1.
select chlom_wallet.continuity_status_v1();

select
  s.source_head_sha,
  count(*) filter (where a.candidate_only) as candidate_assets,
  count(*) filter (where a.production_activation) as production_assets,
  count(*) filter (where a.authority_granted) as authority_assets,
  count(*) filter (where a.provider_write) as provider_write_assets,
  count(*) filter (where a.money_movement) as money_movement_assets,
  count(*) filter (where a.rights_grant) as rights_grant_assets,
  count(*) filter (where a.chain_broadcast) as chain_broadcast_assets,
  count(*) filter (where a.checkout_enabled) as checkout_assets
from chlom_wallet.continuity_suite_versions_v1 s
join chlom_wallet.continuity_asset_registry_v1 a on a.suite_ref=s.suite_ref
group by s.source_head_sha
order by max(s.created_at) desc limit 1;

select component_class,count(*) as component_count,
       count(*) filter (where runtime_binding_state like 'HOLD%') as held_runtime_bindings
from chlom_wallet.continuity_component_registry_v1
where suite_ref=(select suite_ref from chlom_wallet.continuity_suite_versions_v1 order by created_at desc limit 1)
group by component_class order by component_class;

select
  b.agent_id,b.agent_did,b.fingerprint_sha256,b.lane,b.heartbeat_ttl_minutes,
  h.last_heartbeat_at,h.next_heartbeat_due_at,h.heartbeat_state,
  case when h.next_heartbeat_due_at is null or h.next_heartbeat_due_at < now() then 'STALE' else 'FRESH' end as derived_freshness
from chlom_wallet.continuity_agent_bindings_v1 b
left join chlom_runtime.proprietary_factory_agent_heartbeats h on h.agent_id=b.agent_id
where b.suite_ref=(select suite_ref from chlom_wallet.continuity_suite_versions_v1 order by created_at desc limit 1)
order by b.lane;

select definition_ref,job_id,lane,cadence_minutes,enabled,candidate_only,fail_closed,production_activation
from chlom_wallet.continuity_automation_definitions_v1
where suite_ref=(select suite_ref from chlom_wallet.continuity_suite_versions_v1 order by created_at desc limit 1)
order by cadence_minutes,job_id;

select oracle_id,connection_ref,oracle_class,connection_state,read_only,freshness_ttl_seconds,authority_ceiling
from chlom_wallet.continuity_oracle_connections_v1
where suite_ref=(select suite_ref from chlom_wallet.continuity_suite_versions_v1 order by created_at desc limit 1)
order by oracle_id;

select result,generated_assets,direct_components,agent_bindings,automation_jobs,oracle_connections,stale_agents,
       budget_semantics_correct,public_access,production_activation,invariant_failures,created_at
from chlom_wallet.continuity_canary_runs_v1
order by created_at desc limit 1;

select service_id,display_name,integration_state,write_gate,monthly_request_limit,
       metadata->>'mcp_runtime_binding' as mcp_runtime_binding,
       metadata->>'api_runtime_binding' as api_runtime_binding
from integration_control.services where service_id='chlom_wallet_continuity';

select tool_name,service_id,operation_key,risk_class,enabled,requires_human_approval
from integration_control.mcp_tools
where service_id='chlom_wallet_continuity'
order by risk_class,tool_name;

select policy_id,policy_version,policy_state,current_generation,next_generation,maximum_generation,
       metadata->>'local_budget_semantics' as local_budget_semantics,
       metadata->>'factory_generation_advanced' as factory_generation_advanced
from chlom_runtime.proprietary_factory_fleet_policy
where policy_id='ct.policy.chlom-proprietary-factory-100k-plus-continuity-v4';

select jobid,jobname,schedule,active,command
from cron.job
where jobname='chlom-wallet-continuity-controlled-test-hourly-v1';
