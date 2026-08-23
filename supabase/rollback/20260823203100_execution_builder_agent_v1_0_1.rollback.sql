-- History-preserving rollback for CrownThrive Execution Builder Agent v1.0.1.
-- Disable/supersede execution surfaces while retaining requests, receipts and DAIL history.
begin;

revoke execute on function chlom_runtime.complete_agent_build_request(uuid,text,text,text,jsonb,jsonb,jsonb,jsonb) from service_role;
revoke execute on function chlom_runtime.route_capability_execution_to_execution_builder(uuid,text,text) from service_role;
revoke execute on function chlom_runtime.route_construction_work_to_execution_builder(text,text,text) from service_role;

update chlom_runtime.vaulted_capability_registry
set invocation_state='revoked',allowed_agent_ids='{}'::text[],metadata=metadata||jsonb_build_object('rollback_at',now(),'rollback_state','revoked_history_preserved'),updated_at=now()
where capability_id='ct.capability.agent-build-execution.v1';

update chlom_secrets.trade_secret_assets
set lifecycle_state='superseded',metadata=metadata||jsonb_build_object('rollback_at',now(),'rollback_state','superseded_history_preserved')
where asset_id='ct.asset.agent.execution-builder.v1';

update chlom_runtime.agent_skill_packages
set mcp_state='superseded',commercial_state='superseded',checkout_enabled=false,entitlement_active=false,
    metadata=metadata||jsonb_build_object('rollback_at',now(),'rollback_state','superseded_history_preserved'),updated_at=now()
where skill_id='ct.skill.execution-builder.v1';

update chlom_runtime.agent_suite_registry
set release_state='superseded',metadata=metadata||jsonb_build_object('rollback_at',now(),'rollback_state','superseded_history_preserved'),updated_at=now()
where suite_id='ct.agent-suite.execution-builder.v1';

update chlom_runtime.agent_templates
set lifecycle_state='superseded',vote_eligible=false,no_self_approval=true,
    metadata=metadata||jsonb_build_object('rollback_at',now(),'rollback_state','superseded_history_preserved'),updated_at=now()
where agent_id='ct.agent.execution-builder';

update chlom_runtime.agent_health
set health_state='degraded',current_task='execution_builder_rolled_back',resource_state=resource_state||jsonb_build_object('rollback_at',now(),'routing_disabled',true),updated_at=now()
where agent_id='ct.agent.execution-builder';

update chlom_runtime.agent_build_requests
set request_state='hold',updated_at=now()
where request_state in('queued','claimed','building');

select chlom_runtime.append_dail_event(
  'agent.execution_builder.rollback','agent','ct.agent.execution-builder',
  jsonb_build_object('history_preserved',true,'request_receipts_preserved',true,'routing_disabled',true,'vote_eligible',false,'d3_human_reserved',true),
  'CrownThrive controlled rollback','did:ct:system:thrivebase','ct.relay.agent-c','1.0.1','execution-builder-agent-v1-rollback',null,
  'D2 bounded rollback; no deletion of institutional evidence',null,'restricted'
);

commit;
