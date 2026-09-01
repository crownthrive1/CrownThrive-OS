create or replace view integration_control.penta_wire_secure_runtime_health_v1 as
select
  s.service_id,
  s.canary_operation_key,
  s.last_state,
  s.last_http_status,
  s.last_route_tier,
  s.last_checked_at,
  s.next_check_at,
  s.consecutive_failures,
  s.last_error_code,
  a.state as adapter_state,
  a.allowed_operations,
  integration_control.penta_wire_secure_adapter_status_v1(s.service_id) as adapter_status,
  false as secret_values_returned,
  false as provider_write,
  'none'::text as authority_effect
from integration_control.penta_wire_secure_runtime_state_v1 s
left join integration_control.penta_wire_read_adapters_v1 a using(service_id);

revoke all on table integration_control.penta_wire_secure_runtime_health_v1
  from public,anon,authenticated;
grant select on table integration_control.penta_wire_secure_runtime_health_v1 to service_role;
