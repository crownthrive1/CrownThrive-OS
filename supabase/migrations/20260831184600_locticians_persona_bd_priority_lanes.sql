-- CrownThrive Locticians persona Brilliant Directories credential lanes — 2026-08-31
-- IMPORTANT: no raw credential material is stored in source. Vault aliases must already exist.
-- Runtime evidence: all five provider-issued credentials authenticate on bounded reads
-- (`user/fields` and `data_categories` HTTP 200) while Site Info remains permission-gated HTTP 403.
-- Lanes stay disabled until provider permissions are updated and exact promotion canaries pass.

begin;

insert into integration_control.locticians_provider_key_lanes_v1(
  lane_id,service_id,credential_id,provider_key_name,vault_alias,lane_class,priority,
  enabled,provider_status,permission_profile,allowed_methods,d3_delete_allowed,
  requires_d3_for_delete,dispatch_state,last_verified_at,metadata
) values
('ct.locticians.bd.personas.hot.v1','locticians','locticians_bd_personas_hot_v1','Personas 1 Hot','locticians_bd_personas_hot_v1','hot',1,false,'provider_authenticated_pending_permission','bounded_reads_verified_site_info_advanced_pending',array['GET']::text[],false,true,'HOLD_PENDING_PERMISSION',now(),jsonb_build_object('persona_fabric',true,'future_priority',1,'promotion_after_permission_canary',true,'shared_provider_quota',true,'switch_on_429',false,'independent_credential',true,'authentication_verified',true,'user_fields_http_status',200,'data_categories_http_status',200,'site_info_http_status',403,'site_info_permission_pending',true,'failover_ready',false,'secret_material_exposed',false,'requested_priority_class','HOT')),
('ct.locticians.bd.personas.warm.v1','locticians','locticians_bd_personas_warm_v1','Personas 2 Warm','locticians_bd_personas_warm_v1','warm',2,false,'provider_authenticated_pending_permission','bounded_reads_verified_site_info_advanced_pending',array['GET']::text[],false,true,'HOLD_PENDING_PERMISSION',now(),jsonb_build_object('persona_fabric',true,'future_priority',2,'promotion_after_permission_canary',true,'shared_provider_quota',true,'switch_on_429',false,'independent_credential',true,'authentication_verified',true,'user_fields_http_status',200,'data_categories_http_status',200,'site_info_http_status',403,'site_info_permission_pending',true,'failover_ready',false,'secret_material_exposed',false,'requested_priority_class','WARM')),
('ct.locticians.bd.personas.cold.v1','locticians','locticians_bd_personas_cold_v1','Personas 3 Cold','locticians_bd_personas_cold_v1','cold',3,false,'provider_authenticated_pending_permission','bounded_reads_verified_site_info_advanced_pending',array['GET']::text[],false,true,'HOLD_PENDING_PERMISSION',now(),jsonb_build_object('persona_fabric',true,'future_priority',3,'promotion_after_permission_canary',true,'shared_provider_quota',true,'switch_on_429',false,'independent_credential',true,'authentication_verified',true,'user_fields_http_status',200,'data_categories_http_status',200,'site_info_http_status',403,'site_info_permission_pending',true,'failover_ready',false,'secret_material_exposed',false,'requested_priority_class','COLD')),
('ct.locticians.bd.personas.emergency.1.v1','locticians','locticians_bd_emergency_penta_fallback_1_v1','Emergency Penta Fallback 1','locticians_bd_emergency_penta_fallback_1_v1','cold',4,false,'provider_authenticated_pending_permission','bounded_reads_verified_site_info_advanced_pending',array['GET']::text[],false,true,'HOLD_PENDING_PERMISSION',now(),jsonb_build_object('persona_fabric',true,'emergency_fallback',true,'future_priority',4,'promotion_after_permission_canary',true,'shared_provider_quota',true,'switch_on_429',false,'independent_credential',true,'authentication_verified',true,'user_fields_http_status',200,'data_categories_http_status',200,'site_info_http_status',403,'site_info_permission_pending',true,'failover_ready',false,'secret_material_exposed',false,'requested_priority_class','EMERGENCY_FALLBACK_1')),
('ct.locticians.bd.personas.emergency.2.v1','locticians','locticians_bd_emergency_penta_fallback_2_v1','Emergency Penta Fallback 2','locticians_bd_emergency_penta_fallback_2_v1','cold',5,false,'provider_authenticated_pending_permission','bounded_reads_verified_site_info_advanced_pending',array['GET']::text[],false,true,'HOLD_PENDING_PERMISSION',now(),jsonb_build_object('persona_fabric',true,'emergency_fallback',true,'future_priority',5,'promotion_after_permission_canary',true,'shared_provider_quota',true,'switch_on_429',false,'independent_credential',true,'authentication_verified',true,'user_fields_http_status',200,'data_categories_http_status',200,'site_info_http_status',403,'site_info_permission_pending',true,'failover_ready',false,'secret_material_exposed',false,'requested_priority_class','EMERGENCY_FALLBACK_2'))
on conflict(lane_id) do update set
  credential_id=excluded.credential_id,
  provider_key_name=excluded.provider_key_name,
  vault_alias=excluded.vault_alias,
  lane_class=excluded.lane_class,
  priority=excluded.priority,
  enabled=false,
  provider_status=excluded.provider_status,
  permission_profile=excluded.permission_profile,
  allowed_methods=excluded.allowed_methods,
  d3_delete_allowed=false,
  requires_d3_for_delete=true,
  dispatch_state='HOLD_PENDING_PERMISSION',
  last_verified_at=excluded.last_verified_at,
  metadata=integration_control.locticians_provider_key_lanes_v1.metadata||excluded.metadata,
  updated_at=now();

insert into integration_control.credential_continuity_registry(
  credential_id,service_id,credential_class,provider_system,provider_location_note,
  primary_vault_name,recovery_vault_name,primary_present,recovery_present,fingerprint_sha256,
  runtime_consumers,continuity_state,recovery_note,last_verified_at
) values
('locticians_bd_personas_hot_v1','locticians','api_key','Brilliant Directories','Provider-issued persona credential: Personas 1 Hot','locticians_bd_personas_hot_v1',null,true,false,'a3be24c83780ff65e7e72b74c80b396890f2136f1c60ee483e698eb4382916a2',jsonb_build_array('locticians-bd-router-v2','PentaPersonas','PentaPersonaFactory','PentaMarketer','PentaWire','PentaCredentials','PentaCertify'),'verified_primary_only','Credential authenticates on bounded reads; dispatch remains held until required provider permission and promotion canary pass.',now()),
('locticians_bd_personas_warm_v1','locticians','api_key','Brilliant Directories','Provider-issued persona credential: Personas 2 Warm','locticians_bd_personas_warm_v1',null,true,false,'5d9d99587dd59d8fe5f7226a4e8d3db8eb98f3ec3fa9ce77bd98bef99a89220d',jsonb_build_array('locticians-bd-router-v2','PentaPersonas','PentaPersonaFactory','PentaMarketer','PentaWire','PentaCredentials','PentaCertify'),'verified_primary_only','Credential authenticates on bounded reads; dispatch remains held until required provider permission and promotion canary pass.',now()),
('locticians_bd_personas_cold_v1','locticians','api_key','Brilliant Directories','Provider-issued persona credential: Personas 3 Cold','locticians_bd_personas_cold_v1',null,true,false,'e775103884a1482eceedccf20a80641e52b3c48bada669c4198511802f5af971',jsonb_build_array('locticians-bd-router-v2','PentaPersonas','PentaPersonaFactory','PentaMarketer','PentaWire','PentaCredentials','PentaCertify'),'verified_primary_only','Credential authenticates on bounded reads; dispatch remains held until required provider permission and promotion canary pass.',now()),
('locticians_bd_emergency_penta_fallback_1_v1','locticians','api_key','Brilliant Directories','Provider-issued emergency credential: Emergency Penta Fallback 1','locticians_bd_emergency_penta_fallback_1_v1',null,true,false,'7a5381aaa1aecb5542c7b46b914d0d86a812b5a2f7c0866ed685c4ff828983b9',jsonb_build_array('locticians-bd-router-v2','PentaPersonas','PentaPersonaFactory','PentaMarketer','PentaWire','PentaCredentials','PentaCertify'),'verified_primary_only','Emergency credential authenticates on bounded reads; dispatch remains held until required provider permission and promotion canary pass.',now()),
('locticians_bd_emergency_penta_fallback_2_v1','locticians','api_key','Brilliant Directories','Provider-issued emergency credential: Emergency Penta Fallback 2','locticians_bd_emergency_penta_fallback_2_v1',null,true,false,'3bece83306a47fa7fef13364a774a9ea7ff00e82fe3c752e19f4f39897122ddc',jsonb_build_array('locticians-bd-router-v2','PentaPersonas','PentaPersonaFactory','PentaMarketer','PentaWire','PentaCredentials','PentaCertify'),'verified_primary_only','Emergency credential authenticates on bounded reads; dispatch remains held until required provider permission and promotion canary pass.',now())
on conflict(credential_id) do update set
  primary_vault_name=excluded.primary_vault_name,
  primary_present=true,
  fingerprint_sha256=excluded.fingerprint_sha256,
  runtime_consumers=excluded.runtime_consumers,
  continuity_state='verified_primary_only',
  recovery_note=excluded.recovery_note,
  last_verified_at=excluded.last_verified_at,
  updated_at=now();

insert into integration_control.runtime_variable_registry(
  variable_key,service_id,value_class,public_value,secret_reference,canonical_source,
  recovery_source,runtime_consumers,notes
) values
('locticians.bd.personas.hot','locticians','secret_reference',null,'locticians_bd_personas_hot_v1','ThriveBase Vault',null,jsonb_build_array('locticians-bd-router-v2','PentaPersonas','PentaPersonaFactory','PentaMarketer'),'Priority 1 after permission and promotion canary; raw secret never projected.'),
('locticians.bd.personas.warm','locticians','secret_reference',null,'locticians_bd_personas_warm_v1','ThriveBase Vault',null,jsonb_build_array('locticians-bd-router-v2','PentaPersonas','PentaPersonaFactory','PentaMarketer'),'Priority 2 after permission and promotion canary; raw secret never projected.'),
('locticians.bd.personas.cold','locticians','secret_reference',null,'locticians_bd_personas_cold_v1','ThriveBase Vault',null,jsonb_build_array('locticians-bd-router-v2','PentaPersonas','PentaPersonaFactory','PentaMarketer'),'Priority 3 after permission and promotion canary; raw secret never projected.'),
('locticians.bd.personas.emergency.1','locticians','secret_reference',null,'locticians_bd_emergency_penta_fallback_1_v1','ThriveBase Vault',null,jsonb_build_array('locticians-bd-router-v2','PentaPersonas','PentaPersonaFactory','PentaMarketer'),'Priority 4 emergency fallback after permission and promotion canary; raw secret never projected.'),
('locticians.bd.personas.emergency.2','locticians','secret_reference',null,'locticians_bd_emergency_penta_fallback_2_v1','ThriveBase Vault',null,jsonb_build_array('locticians-bd-router-v2','PentaPersonas','PentaPersonaFactory','PentaMarketer'),'Priority 5 emergency fallback after permission and promotion canary; raw secret never projected.')
on conflict(variable_key) do update set
  secret_reference=excluded.secret_reference,
  canonical_source=excluded.canonical_source,
  runtime_consumers=excluded.runtime_consumers,
  notes=excluded.notes;

commit;
