insert into integration_control.services(service_id,display_name,base_url,docs_url,auth_scheme,credential_ref,credential_state,integration_state,write_gate,monthly_request_limit,timezone,metadata)
values(
  'chlom_public_resolver','CHLOM Public Identity Resolver',
  'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/chlom-public-resolver',
  'https://crown-thrive.mintlify.io/chlom/overview',
  'public_safe_resolver','none','verified','read_verified',false,null,'UTC',
  '{"framework_id":"ct.framework.chlom","function_slug":"chlom-public-resolver","function_version":1,"ezbr_sha256":"cfd569fa937f6123f270db2aa8472ba5b6ee1d2e34954dbe11c337ac9e011516","public_safe":true,"verified_http_status":200}'::jsonb
)
on conflict(service_id) do update set display_name=excluded.display_name,base_url=excluded.base_url,docs_url=excluded.docs_url,auth_scheme=excluded.auth_scheme,credential_ref=excluded.credential_ref,credential_state=excluded.credential_state,integration_state=excluded.integration_state,write_gate=excluded.write_gate,metadata=integration_control.services.metadata||excluded.metadata,updated_at=now();

update integration_control.services
set metadata=metadata || '{"function_slug":"chlom-api-control","function_version":1,"ezbr_sha256":"f8111eff9b2e9128394ce8d3bd4af3ae925b8f33b936b0de41b0f77540e3e359","deployment_state":"active_uninvoked_admin_runtime"}'::jsonb,
    updated_at=now()
where service_id='chlom_core';

update chlom_runtime.modules
set implementation_ref=case module_id
  when 'ct.chlom.api-mcp' then 'supabase-edge:chlom-api-control@v1'
  when 'ct.chlom.identity' then 'supabase-edge:chlom-public-resolver@v1 + chlom_identity schema'
  when 'ct.chlom.dail' then 'postgres:chlom_runtime.dail_events + public RPC wrappers'
  else implementation_ref end,
  updated_at=now()
where module_id in ('ct.chlom.api-mcp','ct.chlom.identity','ct.chlom.dail');

update institutional_federation.framework_package_registry
set package_state='controlled_test',
    private_runtime_state='available',
    api_state='controlled_test',
    mcp_state='controlled_test',
    metadata=metadata || jsonb_build_object(
      'runtime_evidence','Supabase chlom_runtime schema + chlom-api-control@v1 + chlom-public-resolver@v1',
      'public_resolver_http_verified',true,
      'admin_mcp_deployment_verified',true,
      'admin_mcp_invocation_verified',false,
      'd3_remains_reserved',true
    ),
    updated_at=now()
where package_id='ct.framework-package.chlom';

select chlom_runtime.append_dail_event(
  'chlom.runtime.controlled_test.promoted','framework','ct.framework.chlom',
  jsonb_build_object(
    'package_state','controlled_test',
    'api_state','controlled_test',
    'mcp_state','controlled_test',
    'public_resolver_http_verified',true,
    'admin_mcp_invocation_verified',false,
    'public_activation_allowed',false,
    'operationally_enabled',false
  ),
  'founder-directive-2026-08-20',null,'ct.agent.founder-orchestrator','0.1.0',null,null,'D2 controlled test evidence',null,'internal'
);