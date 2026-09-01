-- Rollback for 20260901185219_cos_census_hotpath_lookup_collapse_v1.sql.
-- Restores exact pre-optimization upsert semantics; data/history is untouched.

create or replace function integration_control.cos_entity_upsert_v2(p_entity_kind text, p_entity_key text, p_canonical_name text, p_source_system text, p_source_ref text, p_lifecycle_state text, p_risk_class text, p_authority_system text, p_current boolean, p_source_fingerprint_sha256 text, p_attributes jsonb DEFAULT '{}'::jsonb)
returns uuid
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $function$
declare
  v_id uuid;
  v_cos_id uuid;
  v_name text:=coalesce(nullif(btrim(coalesce(p_canonical_name,'')),''),nullif(btrim(coalesce(p_entity_key,'')),''),'Unnamed COS entity');
  v_key text:=nullif(btrim(coalesce(p_entity_key,'')),'');
  v_source text:=coalesce(nullif(btrim(coalesce(p_source_system,'')),''),'COS');
  v_authority text:=coalesce(nullif(btrim(coalesce(p_authority_system,'')),''),v_source);
  v_lifecycle text:=case when p_lifecycle_state in ('active','intentionally_gated','candidate','hold','retired','superseded','unresolved') then p_lifecycle_state else 'candidate' end;
  v_risk text:=case when p_risk_class in ('D0','D1','D2','D3') then p_risk_class else 'D2' end;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  if v_key is null then raise exception 'cos_entity_key_required'; end if;
  if not exists(select 1 from integration_control.cos_entity_kind_registry_v1 where entity_kind=p_entity_kind and active) then raise exception 'cos_entity_kind_not_registered:%',p_entity_kind; end if;
  select cos_id into v_cos_id from integration_control.cos_identity_registry_v1 where canonical_key=p_entity_kind||':'||v_key;
  insert into integration_control.cos_entities_v2(entity_kind,entity_key,canonical_name,canonical_cos_id,source_system,source_ref,lifecycle_state,risk_class,authority_system,current,source_fingerprint_sha256,attributes,first_seen_at,last_seen_at,updated_at)
  values(p_entity_kind,v_key,v_name,v_cos_id,v_source,p_source_ref,v_lifecycle,v_risk,v_authority,coalesce(p_current,true),p_source_fingerprint_sha256,coalesce(p_attributes,'{}'::jsonb),clock_timestamp(),clock_timestamp(),clock_timestamp())
  on conflict(entity_kind,entity_key) do update set canonical_name=excluded.canonical_name,canonical_cos_id=coalesce(integration_control.cos_entities_v2.canonical_cos_id,excluded.canonical_cos_id),source_system=excluded.source_system,source_ref=excluded.source_ref,lifecycle_state=excluded.lifecycle_state,risk_class=excluded.risk_class,authority_system=excluded.authority_system,current=excluded.current,source_fingerprint_sha256=excluded.source_fingerprint_sha256,attributes=integration_control.cos_entities_v2.attributes||excluded.attributes,last_seen_at=clock_timestamp(),updated_at=clock_timestamp()
  returning cos_entity_id into v_id;
  return v_id;
end
$function$;

create or replace function integration_control.cos_relationship_upsert_v2(p_source_kind text, p_source_key text, p_target_kind text, p_target_key text, p_relationship_type text, p_state text DEFAULT 'active'::text, p_authority_ref text DEFAULT NULL::text, p_evidence jsonb DEFAULT '{}'::jsonb)
returns uuid
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $function$
declare v_source uuid; v_target uuid; v_id uuid;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  select cos_entity_id into v_source from integration_control.cos_entities_v2 where entity_kind=p_source_kind and entity_key=p_source_key;
  select cos_entity_id into v_target from integration_control.cos_entities_v2 where entity_kind=p_target_kind and entity_key=p_target_key;
  if v_source is null or v_target is null then return null; end if;
  insert into integration_control.cos_entity_relationships_v2(source_entity_id,target_entity_id,relationship_type,state,authority_ref,evidence,first_seen_at,last_seen_at,updated_at)
  values(v_source,v_target,p_relationship_type,p_state,p_authority_ref,coalesce(p_evidence,'{}'::jsonb),clock_timestamp(),clock_timestamp(),clock_timestamp())
  on conflict(source_entity_id,target_entity_id,relationship_type) do update set state=excluded.state,authority_ref=excluded.authority_ref,evidence=integration_control.cos_entity_relationships_v2.evidence||excluded.evidence,last_seen_at=clock_timestamp(),updated_at=clock_timestamp()
  returning relationship_id into v_id;
  return v_id;
end
$function$;
