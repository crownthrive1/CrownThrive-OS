-- Rollback for 20260901185447_cos_census_dataset_bulk_refresh_v1.sql.
-- Restores the historical row-by-row database/schema/dataset census block and
-- removes only the set-based helper. Historical COS/DAIL rows are untouched.

do $rollback$
declare
  v_def text;
  v_start integer;
  v_end integer;
  v_old text := E'  -- Database, schemas and governed datasets.\n  perform integration_control.cos_entity_upsert_v2(''database'',current_database(),current_database(),\n    ''ThriveBase'',''postgres:''||current_database(),''active'',''D3'',''ThriveBase + PentaCensus'',true,\n    encode(extensions.digest(convert_to(current_database(),''UTF8''),''sha256''),''hex''),\n    jsonb_build_object(''canonical_store'',true,''raw_secret_material'',false));\n  v_count:=v_count+1;\n  for r in select schema_name from information_schema.schemata\n    where schema_name not in (''pg_catalog'',''information_schema'',''pg_toast'') and schema_name not like ''pg_temp_%'' and schema_name not like ''pg_toast_temp_%''\n  loop\n    perform integration_control.cos_entity_upsert_v2(''schema'',r.schema_name,r.schema_name,\n      ''ThriveBase'',''postgres:''||current_database()||''/schema/''||r.schema_name,\n      ''active'',''D3'',''ThriveBase + PentaCensus'',true,\n      encode(extensions.digest(convert_to(r.schema_name,''UTF8''),''sha256''),''hex''),''{}''::jsonb);\n    perform integration_control.cos_relationship_upsert_v2(''database'',current_database(),''schema'',r.schema_name,\n      ''CONTAINS_SCHEMA'',''active'',''ThriveBase'',''{}''::jsonb);\n    v_count:=v_count+1; v_rel:=v_rel+1;\n  end loop;\n  for r in select table_schema,table_name,table_type from information_schema.tables\n    where table_schema not in (''pg_catalog'',''information_schema'',''pg_toast'') and table_schema not like ''pg_temp_%'' and table_schema not like ''pg_toast_temp_%''\n  loop\n    perform integration_control.cos_entity_upsert_v2(''dataset'',r.table_schema||''.''||r.table_name,\n      r.table_schema||''.''||r.table_name,''ThriveBase'',''postgres:''||current_database()||''/''||r.table_schema||''.''||r.table_name,\n      ''active'',''D3'',''ThriveBase + PentaCensus'',true,\n      encode(extensions.digest(convert_to(r.table_schema||''.''||r.table_name||'':''||r.table_type,''UTF8''),''sha256''),''hex''),\n      jsonb_build_object(''schema'',r.table_schema,''table_type'',r.table_type));\n    perform integration_control.cos_relationship_upsert_v2(''schema'',r.table_schema,''dataset'',r.table_schema||''.''||r.table_name,\n      ''CONTAINS_DATASET'',''active'',''ThriveBase'',''{}''::jsonb);\n    v_count:=v_count+1; v_rel:=v_rel+1;\n  end loop;\n\n';
begin
  select pg_get_functiondef(p.oid) into v_def
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='integration_control' and p.proname='cos_census_refresh_v2';
  v_start := position('  -- Database, schemas and governed datasets. Set-based v1 hot path.' in v_def);
  v_end := position('  -- Protocol kernel and release.' in v_def);
  if v_start=0 or v_end<=v_start then raise exception 'set_based_census_block_not_current'; end if;
  v_def := substring(v_def from 1 for v_start-1) || v_old || substring(v_def from v_end);
  execute v_def;
end
$rollback$;

drop function if exists integration_control.cos_dataset_census_refresh_v1();
