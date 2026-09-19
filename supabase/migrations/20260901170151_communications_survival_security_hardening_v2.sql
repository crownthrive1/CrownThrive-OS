-- Scoped least-privilege and performance hardening for the Communications Survival Fabric.
-- No runtime semantics, authority, scheduler, campaign, recipient, or provider state are changed.

create index if not exists communications_survival_cycles_contract_v1_idx
on integration_control.communications_survival_cycles_v1(contract_key,contract_generation);

revoke all on function crm.bd_next_page_descriptor_v1(text) from public,anon,authenticated;
revoke all on function crm.bd_opaque_page_descriptor_v2(text) from public,anon,authenticated;
revoke all on function crm.enforce_safe_ready_contact_v1() from public,anon,authenticated;
revoke all on function crm.validate_bd_provider_page_cursor_v2() from public,anon,authenticated;

revoke all on function integration_control.guard_communications_survival_contract_insert_v1() from public,anon,authenticated;
revoke all on function integration_control.reject_communications_survival_mutation_v1() from public,anon,authenticated;
revoke all on function integration_control.guard_communications_survival_operation_registry_v1() from public,anon,authenticated;
revoke all on function integration_control.guard_communications_survival_executor_v1() from public,anon,authenticated;
revoke all on function integration_control.guard_communications_survival_scheduler_v1() from public,anon,authenticated;
revoke all on function integration_control.reject_scheduler_desired_truncate_with_survival_v1() from public,anon,authenticated;
revoke all on function integration_control.reject_pentatime_truncate_with_survival_v1() from public,anon,authenticated;

-- Service role requires the pure cursor validators for bounded diagnostics only.
grant execute on function crm.bd_next_page_descriptor_v1(text) to service_role;
grant execute on function crm.bd_opaque_page_descriptor_v2(text) to service_role;