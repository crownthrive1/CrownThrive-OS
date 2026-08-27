-- CrownThrive production security containment.
-- Provider migration: 20260827234114_contain_public_security_definer_execute_v1
-- Purpose: remove public/client EXECUTE from privileged SECURITY DEFINER RPCs while preserving service_role execution.

revoke execute on function public.ct_self_funding_route_health_v1() from public, anon, authenticated;
revoke execute on function public.ct_self_funding_route_plan_v1(boolean) from public, anon, authenticated;
revoke execute on function public.penta_fabric_mesh_convergence_status_v1() from public, anon, authenticated;

grant execute on function public.ct_self_funding_route_health_v1() to service_role;
grant execute on function public.ct_self_funding_route_plan_v1(boolean) to service_role;
grant execute on function public.penta_fabric_mesh_convergence_status_v1() to service_role;
