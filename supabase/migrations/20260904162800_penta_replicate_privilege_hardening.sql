-- PentaReplicate public access is Edge-only. Keep the integration_control substrate service-role/private.
revoke all privileges on function integration_control.penta_replicate_capture_source_change_v1() from public, anon, authenticated;
revoke all privileges on function integration_control.penta_replicate_cycle_v1(boolean) from public, anon, authenticated;
revoke all privileges on function integration_control.penta_replicate_manifest_v1(text) from public, anon, authenticated;
revoke all privileges on function integration_control.penta_replicate_refresh_targets_v1() from public, anon, authenticated;
revoke all privileges on function integration_control.penta_replicate_status_v1() from public, anon, authenticated;

grant execute on function integration_control.penta_replicate_cycle_v1(boolean) to service_role;
grant execute on function integration_control.penta_replicate_manifest_v1(text) to service_role;
grant execute on function integration_control.penta_replicate_refresh_targets_v1() to service_role;
grant execute on function integration_control.penta_replicate_status_v1() to service_role;

revoke all privileges on table integration_control.penta_replicate_policy_v1 from public, anon, authenticated;
revoke all privileges on table integration_control.penta_replicate_events_v1 from public, anon, authenticated;
revoke all privileges on table integration_control.penta_replicate_targets_v1 from public, anon, authenticated;
revoke all privileges on table integration_control.penta_replicate_manifests_v1 from public, anon, authenticated;
revoke all privileges on table integration_control.penta_replicate_jobs_v1 from public, anon, authenticated;
revoke all privileges on table integration_control.penta_replicate_receipts_v1 from public, anon, authenticated;
revoke all privileges on table integration_control.penta_replicate_public_mcp_servers_v1 from public, anon, authenticated;

grant select,insert,update,delete on table integration_control.penta_replicate_policy_v1 to service_role;
grant select,insert,update,delete on table integration_control.penta_replicate_events_v1 to service_role;
grant select,insert,update,delete on table integration_control.penta_replicate_targets_v1 to service_role;
grant select,insert,update,delete on table integration_control.penta_replicate_manifests_v1 to service_role;
grant select,insert,update,delete on table integration_control.penta_replicate_jobs_v1 to service_role;
grant select,insert,update,delete on table integration_control.penta_replicate_receipts_v1 to service_role;
grant select on table integration_control.penta_replicate_public_mcp_servers_v1 to service_role;
