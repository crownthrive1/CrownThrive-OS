create or replace function public.chlom_list_modules()
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog, chlom_runtime
as $$
  select coalesce(jsonb_agg(jsonb_build_object(
    'module_id', module_id,
    'canonical_name', canonical_name,
    'module_class', module_class,
    'version', semantic_version,
    'state', lifecycle_state,
    'authority_ceiling', authority_ceiling,
    'self_healing_class', self_healing_class,
    'mcp_enabled', mcp_enabled,
    'api_enabled', api_enabled,
    'public_contract', public_contract
  ) order by module_id), '[]'::jsonb)
  from chlom_runtime.modules
  where lifecycle_state not in ('retired')
$$;

grant execute on function public.chlom_list_modules() to anon, authenticated, service_role;

create or replace function public.chlom_query_dail_admin(
  p_entity_type text,
  p_entity_id text,
  p_limit integer default 50
) returns jsonb
language sql
stable
security definer
set search_path = pg_catalog, chlom_runtime
as $$
  select coalesce(jsonb_agg(to_jsonb(x) order by x.sequence_id desc), '[]'::jsonb)
  from (
    select sequence_id,event_id,event_type,schema_version,actor_ref,actor_did,agent_id,source_system,
           entity_type,entity_id,entity_version,correlation_id,causation_id,authority_basis,approval_id,
           visibility_class,payload,payload_sha256,previous_event_hash,event_hash,chain_anchor_state,
           signature_ref,created_at
    from chlom_runtime.dail_events
    where entity_type=p_entity_type and entity_id=p_entity_id
    order by sequence_id desc
    limit greatest(1,least(coalesce(p_limit,50),100))
  ) x
$$;

revoke all on function public.chlom_query_dail_admin(text,text,integer) from public, anon, authenticated;
grant execute on function public.chlom_query_dail_admin(text,text,integer) to service_role;

create or replace function public.chlom_query_public_dail(
  p_entity_type text,
  p_entity_id text,
  p_limit integer default 50
) returns jsonb
language sql
stable
security definer
set search_path = pg_catalog, chlom_runtime
as $$
  select coalesce(jsonb_agg(jsonb_build_object(
    'event_id', event_id,
    'event_type', event_type,
    'schema_version', schema_version,
    'entity_type', entity_type,
    'entity_id', entity_id,
    'entity_version', entity_version,
    'payload_sha256', payload_sha256,
    'previous_event_hash', previous_event_hash,
    'event_hash', event_hash,
    'chain_anchor_state', chain_anchor_state,
    'created_at', created_at
  ) order by sequence_id desc), '[]'::jsonb)
  from (
    select * from chlom_runtime.dail_events
    where entity_type=p_entity_type and entity_id=p_entity_id and visibility_class='public'
    order by sequence_id desc
    limit greatest(1,least(coalesce(p_limit,50),100))
  ) x
$$;

grant execute on function public.chlom_query_public_dail(text,text,integer) to anon, authenticated, service_role;

create or replace function public.chlom_append_dail_event(
  p_event_type text,
  p_entity_type text,
  p_entity_id text,
  p_payload jsonb default '{}'::jsonb,
  p_actor_ref text default null,
  p_actor_did text default null,
  p_agent_id text default null,
  p_entity_version text default null,
  p_correlation_id text default null,
  p_causation_id text default null,
  p_authority_basis text default null,
  p_approval_id text default null,
  p_visibility_class text default 'internal'
) returns jsonb
language sql
volatile
security definer
set search_path = pg_catalog, chlom_runtime
as $$
  select chlom_runtime.append_dail_event(
    p_event_type,p_entity_type,p_entity_id,p_payload,p_actor_ref,p_actor_did,p_agent_id,
    p_entity_version,p_correlation_id,p_causation_id,p_authority_basis,p_approval_id,p_visibility_class
  )
$$;

revoke all on function public.chlom_append_dail_event(text,text,text,jsonb,text,text,text,text,text,text,text,text,text) from public, anon, authenticated;
grant execute on function public.chlom_append_dail_event(text,text,text,jsonb,text,text,text,text,text,text,text,text,text) to service_role;

create or replace function public.chlom_backup_status()
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog, chlom_runtime, integration_control
as $$
  select jsonb_build_object(
    'manifests', coalesce((select jsonb_agg(jsonb_build_object(
      'backup_id',backup_id,
      'backup_class',backup_class,
      'source_system',source_system,
      'destination_system',destination_system,
      'destination_ref',destination_ref,
      'encryption_profile',encryption_profile,
      'secret_reference',secret_reference,
      'backup_state',backup_state,
      'contains_secrets',contains_secrets,
      'content_sha256',content_sha256,
      'manifest_sha256',manifest_sha256,
      'created_at',created_at,
      'verified_at',verified_at
    ) order by created_at desc) from chlom_runtime.backup_manifests), '[]'::jsonb),
    'credential_continuity', coalesce((select jsonb_agg(jsonb_build_object(
      'credential_id',credential_id,
      'primary_present',primary_present,
      'recovery_present',recovery_present,
      'continuity_state',continuity_state,
      'fingerprint_sha256',fingerprint_sha256,
      'last_verified_at',last_verified_at
    )) from integration_control.credential_continuity_registry where service_id='chlom_core'), '[]'::jsonb)
  )
$$;

revoke all on function public.chlom_backup_status() from public, anon, authenticated;
grant execute on function public.chlom_backup_status() to service_role;