-- Register the additive PentaDiscovery runtime authentication patch.
-- The public/stable contract remains 1.0.0 and the action contract remains 2.0.0.

update penta_runtime.penta_discovery_runtime_guard_state_v1
set expected_runtime_release='ct.penta.discovery.runtime.2.0.1',
    expected_source_control_ref='github:crownthrive1/CrownThrive-OS:main:supabase/functions/penta-discovery/index.ts+runtime.ts',
    state='HOLD',
    consecutive_passes=0,
    metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
      'runtime_patch_version','2.0.1',
      'auth_contract','gateway-jwt+exact-service-role+legacy-service-role-v1',
      'modern_service_credential_supported',true,
      'constant_time_exact_comparison',true,
      'legacy_service_role_jwt_compatible',true,
      'required_gateway_verify_jwt',true,
      'authority_manufacture',false,
      'provider_money_movement',false
    ),
    updated_at=clock_timestamp()
where runtime_component='penta-discovery-edge';

update public.penta_system_registry
set runtime_ref='supabase-edge:penta-discovery',
    metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
      'runtime_release','ct.penta.discovery.runtime.2.0.1',
      'runtime_patch_version','2.0.1',
      'runtime_source','supabase/functions/penta-discovery/index.ts+runtime.ts',
      'auth_contract','gateway-jwt+exact-service-role+legacy-service-role-v1',
      'modern_service_credential_supported',true,
      'constant_time_exact_comparison',true,
      'legacy_service_role_jwt_compatible',true,
      'required_gateway_verify_jwt',true,
      'runtime_guard_required',true,
      'authority_manufacture',false,
      'provider_money_movement_inherited',false
    ),
    updated_at=clock_timestamp()
where system_key='penta.discovery';

select penta_runtime.penta_discovery_runtime_guard_status_v1();
