-- Rollback CrownThrive Execution Builder Agent v1. Preserve DAIL history.
begin;
revoke execute on function chlom_runtime.complete_agent_build_request(uuid,text,text,text,jsonb,jsonb,jsonb,jsonb) from service_role;
revoke execute on function chlom_runtime.route_capability_execution_to_execution_builder(uuid,text,text) from service_role;
revoke execute on function chlom_runtime.route_construction_work_to_execution_builder(text,text,text) from service_role;
drop function if exists chlom_runtime.complete_agent_build_request(uuid,text,text,text,jsonb,jsonb,jsonb,jsonb);
drop function if exists chlom_runtime.route_capability_execution_to_execution_builder(uuid,text,text);
drop function if exists chlom_runtime.route_construction_work_to_execution_builder(text,text,text);
drop trigger if exists agent_build_receipts_append_only on chlom_runtime.agent_build_receipts;
drop function if exists chlom_runtime.reject_agent_build_receipt_mutation();
drop table if exists chlom_runtime.agent_build_receipts;
drop table if exists chlom_runtime.agent_build_requests;
delete from chlom_runtime.agent_skill_packages where skill_id='ct.skill.execution-builder.v1';
delete from chlom_runtime.agent_suite_registry where suite_id='ct.agent-suite.execution-builder.v1';
delete from chlom_runtime.capability_contracts where capability_id='ct.capability.agent-build-execution.v1';
update chlom_runtime.agent_templates set lifecycle_state='superseded',updated_at=now(),metadata=metadata||jsonb_build_object('rollback_at',now(),'rollback_reason','execution_builder_v1_reverted_history_preserved') where agent_id='ct.agent.execution-builder';
commit;
