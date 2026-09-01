-- COS V1 census hot-path optimization.
-- Collapse per-entity kind+identity lookups and per-relationship endpoint lookups
-- into their corresponding upsert statements. Preserve all existing semantics,
-- constraints, DAIL routing triggers, append-only history, and authority bounds.

do $preflight$
declare
  v_entity_digest text;
  v_rel_digest text;
begin
  select encode(extensions.digest(convert_to(pg_get_functiondef(p.oid),'UTF8'),'sha256'),'hex') into v_entity_digest
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='integration_control' and p.proname='cos_entity_upsert_v2';
  select encode(extensions.digest(convert_to(pg_get_functiondef(p.oid),'UTF8'),'sha256'),'hex') into v_rel_digest
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='integration_control' and p.proname='cos_relationship_upsert_v2';
  if v_entity_digest <> 'df7f2700e9c4cb2bf255bad6695709f7dc9e00d722c2fff4c8a2ca41431730bb' then
    raise exception 'cos_entity_upsert_v2 prestate changed:%',v_entity_digest;
  end if;
  if v_rel_digest <> '8d0c869172b5e29411d27f3e3629412ab8f793f5c638146f574a2beee752196d' then
    raise exception 'cos_relationship_upsert_v2 prestate changed:%',v_rel_digest;
  end if;
end
$preflight$;

create or replace function integration_control.cos_entity_upsert_v2(
  p_entity_kind text,
  p_entity_key text,
  p_canonical_name text,
  p_source_system text,
  p_source_ref text,
  p_lifecycle_state text,
  p_risk_class text,
  p_authority_system text,
  p_current boolean,
  p_source_fingerprint_sha256 text,
  p_attributes jsonb default '{}'::jsonb
)
returns uuid
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $function$
declare
  v_id uuid;
  v_name text:=coalesce(nullif(btrim(coalesce(p_canonical_name,'')),''),nullif(btrim(coalesce(p_entity_key,'')),''),'Unnamed COS entity');
  v_key text:=nullif(btrim(coalesce(p_entity_key,'')),'');
  v_source text:=coalesce(nullif(btrim(coalesce(p_source_system,'')),''),'COS');
  v_authority text:=coalesce(nullif(btrim(coalesce(p_authority_system,'')),''),v_source);
  v_lifecycle text:=case when p_lifecycle_state in ('active','intentionally_gated','candidate','hold','retired','superseded','unresolved') then p_lifecycle_state else 'candidate' end;
  v_risk text:=case when p_risk_class in ('D0','D1','D2','D3') then p_risk_class else 'D2' end;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  if v_key is null then raise exception 'cos_entity_key_required'; end if;

  insert into integration_control.cos_entities_v2(
    entity_kind,entity_key,canonical_name,canonical_cos_id,source_system,source_ref,
    lifecycle_state,risk_class,authority_system,current,source_fingerprint_sha256,
    attributes,first_seen_at,last_seen_at,updated_at
  )
  select
    p_entity_kind,v_key,v_name,
    (select i.cos_id from integration_control.cos_identity_registry_v1 i where i.canonical_key=p_entity_kind||':'||v_key),
    v_source,p_source_ref,v_lifecycle,v_risk,v_authority,coalesce(p_current,true),
    p_source_fingerprint_sha256,coalesce(p_attributes,'{}'::jsonb),
    clock_timestamp(),clock_timestamp(),clock_timestamp()
  from integration_control.cos_entity_kind_registry_v1 k
  where k.entity_kind=p_entity_kind and k.active
  on conflict(entity_kind,entity_key) do update set
    canonical_name=excluded.canonical_name,
    canonical_cos_id=coalesce(integration_control.cos_entities_v2.canonical_cos_id,excluded.canonical_cos_id),
    source_system=excluded.source_system,source_ref=excluded.source_ref,
    lifecycle_state=excluded.lifecycle_state,risk_class=excluded.risk_class,
    authority_system=excluded.authority_system,current=excluded.current,
    source_fingerprint_sha256=excluded.source_fingerprint_sha256,
    attributes=integration_control.cos_entities_v2.attributes||excluded.attributes,
    last_seen_at=clock_timestamp(),updated_at=clock_timestamp()
  returning cos_entity_id into v_id;

  if v_id is null then raise exception 'cos_entity_kind_not_registered:%',p_entity_kind; end if;
  return v_id;
end
$function$;

create or replace function integration_control.cos_relationship_upsert_v2(
  p_source_kind text,
  p_source_key text,
  p_target_kind text,
  p_target_key text,
  p_relationship_type text,
  p_state text default 'active',
  p_authority_ref text default null,
  p_evidence jsonb default '{}'::jsonb
)
returns uuid
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $function$
declare
  v_id uuid;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;

  insert into integration_control.cos_entity_relationships_v2(
    source_entity_id,target_entity_id,relationship_type,state,authority_ref,evidence,
    first_seen_at,last_seen_at,updated_at
  )
  select
    s.cos_entity_id,t.cos_entity_id,p_relationship_type,p_state,p_authority_ref,
    coalesce(p_evidence,'{}'::jsonb),clock_timestamp(),clock_timestamp(),clock_timestamp()
  from integration_control.cos_entities_v2 s
  join integration_control.cos_entities_v2 t on true
  where s.entity_kind=p_source_kind and s.entity_key=p_source_key
    and t.entity_kind=p_target_kind and t.entity_key=p_target_key
  on conflict(source_entity_id,target_entity_id,relationship_type) do update set
    state=excluded.state,authority_ref=excluded.authority_ref,
    evidence=integration_control.cos_entity_relationships_v2.evidence||excluded.evidence,
    last_seen_at=clock_timestamp(),updated_at=clock_timestamp()
  returning relationship_id into v_id;
  return v_id;
end
$function$;

revoke all on function integration_control.cos_entity_upsert_v2(text,text,text,text,text,text,text,text,boolean,text,jsonb) from public;
revoke all on function integration_control.cos_relationship_upsert_v2(text,text,text,text,text,text,text,jsonb) from public;
grant execute on function integration_control.cos_entity_upsert_v2(text,text,text,text,text,text,text,text,boolean,text,jsonb) to service_role;
grant execute on function integration_control.cos_relationship_upsert_v2(text,text,text,text,text,text,text,jsonb) to service_role;
