-- COS V1 census performance: replace the database/schema/dataset row-by-row
-- hot path with four set-based statements plus one database entity upsert.
-- Exact pre-state CAS protects the existing census function from collision.

create or replace function integration_control.cos_dataset_census_refresh_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, integration_control, public, extensions
as $function$
declare
  v_entities integer := 0;
  v_relationships integer := 0;
  v_rows integer := 0;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;

  if (select count(*) from integration_control.cos_entity_kind_registry_v1 where active and entity_kind in ('database','schema','dataset')) <> 3 then
    raise exception 'required_cos_entity_kinds_not_active';
  end if;

  perform integration_control.cos_entity_upsert_v2(
    'database',current_database(),current_database(),'ThriveBase','postgres:'||current_database(),
    'active','D3','ThriveBase + PentaCensus',true,
    encode(extensions.digest(convert_to(current_database(),'UTF8'),'sha256'),'hex'),
    jsonb_build_object('canonical_store',true,'raw_secret_material',false)
  );
  v_entities := v_entities + 1;

  insert into integration_control.cos_entities_v2(
    entity_kind,entity_key,canonical_name,canonical_cos_id,source_system,source_ref,
    lifecycle_state,risk_class,authority_system,current,source_fingerprint_sha256,
    attributes,first_seen_at,last_seen_at,updated_at
  )
  select
    'schema',s.schema_name,s.schema_name,i.cos_id,'ThriveBase',
    'postgres:'||current_database()||'/schema/'||s.schema_name,
    'active','D3','ThriveBase + PentaCensus',true,
    encode(extensions.digest(convert_to(s.schema_name,'UTF8'),'sha256'),'hex'),
    '{}'::jsonb,clock_timestamp(),clock_timestamp(),clock_timestamp()
  from information_schema.schemata s
  left join integration_control.cos_identity_registry_v1 i on i.canonical_key='schema:'||s.schema_name
  where s.schema_name not in ('pg_catalog','information_schema','pg_toast')
    and s.schema_name not like 'pg_temp_%' and s.schema_name not like 'pg_toast_temp_%'
  on conflict(entity_kind,entity_key) do update set
    canonical_name=excluded.canonical_name,
    canonical_cos_id=coalesce(integration_control.cos_entities_v2.canonical_cos_id,excluded.canonical_cos_id),
    source_system=excluded.source_system,source_ref=excluded.source_ref,lifecycle_state=excluded.lifecycle_state,
    risk_class=excluded.risk_class,authority_system=excluded.authority_system,current=excluded.current,
    source_fingerprint_sha256=excluded.source_fingerprint_sha256,
    attributes=integration_control.cos_entities_v2.attributes||excluded.attributes,
    last_seen_at=clock_timestamp(),updated_at=clock_timestamp();
  get diagnostics v_rows = row_count;
  v_entities := v_entities + v_rows;

  insert into integration_control.cos_entity_relationships_v2(
    source_entity_id,target_entity_id,relationship_type,state,authority_ref,evidence,
    first_seen_at,last_seen_at,updated_at
  )
  select db.cos_entity_id,sc.cos_entity_id,'CONTAINS_SCHEMA','active','ThriveBase','{}'::jsonb,
         clock_timestamp(),clock_timestamp(),clock_timestamp()
  from integration_control.cos_entities_v2 db
  join integration_control.cos_entities_v2 sc on sc.entity_kind='schema' and sc.current
  where db.entity_kind='database' and db.entity_key=current_database()
  on conflict(source_entity_id,target_entity_id,relationship_type) do update set
    state=excluded.state,authority_ref=excluded.authority_ref,
    evidence=integration_control.cos_entity_relationships_v2.evidence||excluded.evidence,
    last_seen_at=clock_timestamp(),updated_at=clock_timestamp();
  get diagnostics v_rows = row_count;
  v_relationships := v_relationships + v_rows;

  insert into integration_control.cos_entities_v2(
    entity_kind,entity_key,canonical_name,canonical_cos_id,source_system,source_ref,
    lifecycle_state,risk_class,authority_system,current,source_fingerprint_sha256,
    attributes,first_seen_at,last_seen_at,updated_at
  )
  select
    'dataset',t.table_schema||'.'||t.table_name,t.table_schema||'.'||t.table_name,i.cos_id,
    'ThriveBase','postgres:'||current_database()||'/'||t.table_schema||'.'||t.table_name,
    'active','D3','ThriveBase + PentaCensus',true,
    encode(extensions.digest(convert_to(t.table_schema||'.'||t.table_name||':'||t.table_type,'UTF8'),'sha256'),'hex'),
    jsonb_build_object('schema',t.table_schema,'table_type',t.table_type),
    clock_timestamp(),clock_timestamp(),clock_timestamp()
  from information_schema.tables t
  left join integration_control.cos_identity_registry_v1 i on i.canonical_key='dataset:'||t.table_schema||'.'||t.table_name
  where t.table_schema not in ('pg_catalog','information_schema','pg_toast')
    and t.table_schema not like 'pg_temp_%' and t.table_schema not like 'pg_toast_temp_%'
  on conflict(entity_kind,entity_key) do update set
    canonical_name=excluded.canonical_name,
    canonical_cos_id=coalesce(integration_control.cos_entities_v2.canonical_cos_id,excluded.canonical_cos_id),
    source_system=excluded.source_system,source_ref=excluded.source_ref,lifecycle_state=excluded.lifecycle_state,
    risk_class=excluded.risk_class,authority_system=excluded.authority_system,current=excluded.current,
    source_fingerprint_sha256=excluded.source_fingerprint_sha256,
    attributes=integration_control.cos_entities_v2.attributes||excluded.attributes,
    last_seen_at=clock_timestamp(),updated_at=clock_timestamp();
  get diagnostics v_rows = row_count;
  v_entities := v_entities + v_rows;

  insert into integration_control.cos_entity_relationships_v2(
    source_entity_id,target_entity_id,relationship_type,state,authority_ref,evidence,
    first_seen_at,last_seen_at,updated_at
  )
  select sc.cos_entity_id,ds.cos_entity_id,'CONTAINS_DATASET','active','ThriveBase','{}'::jsonb,
         clock_timestamp(),clock_timestamp(),clock_timestamp()
  from integration_control.cos_entities_v2 ds
  join integration_control.cos_entities_v2 sc
    on sc.entity_kind='schema' and sc.entity_key=ds.attributes->>'schema'
  where ds.entity_kind='dataset' and ds.current
  on conflict(source_entity_id,target_entity_id,relationship_type) do update set
    state=excluded.state,authority_ref=excluded.authority_ref,
    evidence=integration_control.cos_entity_relationships_v2.evidence||excluded.evidence,
    last_seen_at=clock_timestamp(),updated_at=clock_timestamp();
  get diagnostics v_rows = row_count;
  v_relationships := v_relationships + v_rows;

  return jsonb_build_object(
    'ok',true,'entities_touched',v_entities,'relationships_touched',v_relationships,
    'current_schemas',(select count(*) from integration_control.cos_entities_v2 where entity_kind='schema' and current),
    'current_datasets',(select count(*) from integration_control.cos_entities_v2 where entity_kind='dataset' and current),
    'observed_at',clock_timestamp()
  );
end
$function$;

revoke all on function integration_control.cos_dataset_census_refresh_v1() from public;
grant execute on function integration_control.cos_dataset_census_refresh_v1() to service_role;

do $patch$
declare
  v_def text;
  v_start integer;
  v_end integer;
  v_digest text;
  v_replacement text := E'  -- Database, schemas and governed datasets. Set-based v1 hot path.\n  select integration_control.cos_dataset_census_refresh_v1() as payload into r;\n  v_count:=v_count+coalesce((r.payload->>''entities_touched'')::integer,0);\n  v_rel:=v_rel+coalesce((r.payload->>''relationships_touched'')::integer,0);\n\n';
begin
  select pg_get_functiondef(p.oid),encode(extensions.digest(convert_to(pg_get_functiondef(p.oid),'UTF8'),'sha256'),'hex')
    into v_def,v_digest
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='integration_control' and p.proname='cos_census_refresh_v2';

  if v_digest <> 'a0ff2b19addeb28410ac7ce8878df87a0bb530680bb0e6b708aa35a67cfb4a45' then
    raise exception 'cos_census_refresh_v2 prestate changed:%',v_digest;
  end if;

  v_start := position('  -- Database, schemas and governed datasets.' in v_def);
  v_end := position('  -- Protocol kernel and release.' in v_def);
  if v_start=0 or v_end<=v_start then raise exception 'census_dataset_block_markers_not_found'; end if;

  v_def := substring(v_def from 1 for v_start-1) || v_replacement || substring(v_def from v_end);
  execute v_def;
end
$patch$;
