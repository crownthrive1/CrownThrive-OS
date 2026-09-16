-- Command Operating Suite v1. Core applied 2026-09-16; source bindings seeded immediately afterward.
-- Metadata only. No new scheduler, provider mutation, permission grant to users, or source deletion.
create table if not exists integration_control.command_suite_sources_v1(source_key text primary key,category text not null,label text not null,relation_name text not null unique,key_columns text[] not null,field_columns text[] not null,owner_label text not null,version text not null default '1.0.0',updated_at timestamptz not null default now(),check(source_key ~ '^[a-z][a-z0-9-]{0,63}$'),check(relation_name ~ '^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$'));
alter table integration_control.command_suite_sources_v1 enable row level security;
revoke all on integration_control.command_suite_sources_v1 from public,anon,authenticated;
create table if not exists integration_control.command_suite_observations_v1(source_key text primary key references integration_control.command_suite_sources_v1,checked_at timestamptz not null,binding_state text not null,sample_rows integer not null,sample_sha256 text not null,request_id uuid,evidence jsonb not null);
alter table integration_control.command_suite_observations_v1 enable row level security;
revoke all on integration_control.command_suite_observations_v1 from public,anon,authenticated;
create table if not exists integration_control.command_suite_change_snapshots_v1(change_key text primary key,observed_at timestamptz not null default now(),source_definition text not null,source_sha256 text not null);
alter table integration_control.command_suite_change_snapshots_v1 enable row level security;
revoke all on integration_control.command_suite_change_snapshots_v1 from public,anon,authenticated;
create or replace view integration_control.command_suite_relations_v1 as select c.oid::bigint object_oid,n.nspname::text schema_name,c.relname::text object_name,c.relkind::text object_kind,case when c.relkind in ('r','m') and c.reltuples>=0 then c.reltuples::bigint else null end records_estimate,c.relrowsecurity row_security_enabled,s.source_key mapped_source from pg_class c join pg_namespace n on n.oid=c.relnamespace left join integration_control.command_suite_sources_v1 s on s.relation_name=n.nspname||'.'||c.relname where n.nspname not in ('pg_catalog','information_schema','vault','auth','extensions','supabase_migrations','realtime') and n.nspname not like 'pg_%' and c.relkind in ('r','p','v','m','f');
revoke all on integration_control.command_suite_relations_v1 from public,anon,authenticated;
create or replace view integration_control.command_suite_routines_v1 as select p.oid::bigint object_oid,n.nspname::text schema_name,p.proname::text object_name,p.prokind::text routine_kind,p.pronargs::integer argument_count,p.prosecdef security_definer,'INVENTORY_ONLY_NO_EXECUTOR_EXPOSED'::text callability from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname not in ('pg_catalog','information_schema','vault','auth','extensions','supabase_migrations','realtime') and n.nspname not like 'pg_%';
revoke all on integration_control.command_suite_routines_v1 from public,anon,authenticated;
create or replace function integration_control.command_suite_binding_v1(p_source text) returns jsonb language plpgsql stable security definer set search_path=pg_catalog,integration_control as $f$
declare s integration_control.command_suite_sources_v1%rowtype; rid regclass; missing text[]; estimate bigint; kind "char"; sample_at timestamptz;
begin
 select * into s from integration_control.command_suite_sources_v1 where source_key=p_source;
 if not found then raise exception 'UNKNOWN_SOURCE' using errcode='22023'; end if;
 rid:=to_regclass(s.relation_name);
 if rid is not null then
 select array_agg(c) into missing from unnest(s.key_columns||s.field_columns)c where not exists(select 1 from pg_attribute a where a.attrelid=rid and a.attname=c and a.attnum>0 and not a.attisdropped);
 select c.relkind,case when c.relkind in ('r','m') and c.reltuples>=0 then c.reltuples::bigint else null end into kind,estimate from pg_class c where c.oid=rid;
 end if;
 select checked_at into sample_at from integration_control.command_suite_observations_v1 where source_key=p_source;
 return jsonb_build_object('source',s.source_key,'category',s.category,'label',s.label,'owner',s.owner_label,'version',s.version,'binding_state',case when rid is null then 'SOURCE_MISSING' when cardinality(missing)>0 then 'SCHEMA_DRIFT' else 'BOUND' end,'records_estimate',estimate,'count_kind','POSTGRES_PLANNER_ESTIMATE_NOT_EXACT','missing_fields',coalesce(to_jsonb(missing),'[]'::jsonb),'last_command_reconciliation_at',sample_at,'provider_verified_by_this_read',false,'new_rows_automatically_visible',true,'pagination',case when p_source='mcp' then 'OFFSET_VIEW_NO_UNIQUE_KEY_PROOF' when p_source in ('relation-discovery','routine-discovery') then 'UNIQUE_CATALOG_OID_KEYSET' else 'PRIMARY_KEY_KEYSET' end,'keys',to_jsonb(s.key_columns),'fields',to_jsonb(s.field_columns));
end $f$;
revoke all on function integration_control.command_suite_binding_v1(text) from public,anon,authenticated;
create or replace function public.ct_command_suite_overview_v1() returns jsonb language plpgsql stable security definer set search_path=pg_catalog,integration_control as $f$
declare sources jsonb; unmapped integer;
begin
 if coalesce(auth.role(),'')<>'service_role' then raise exception 'SERVICE_ROLE_REQUIRED' using errcode='42501'; end if;
 select jsonb_agg(integration_control.command_suite_binding_v1(source_key) order by category,label) into sources from integration_control.command_suite_sources_v1;
 select count(*) into unmapped from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname in ('integration_control','penta_runtime','chlom_runtime','penta_os20','developer_commerce','crm') and c.relkind in ('r','p','v','m') and c.relname ~ '(registry|catalog|control|cursor|inventory|reconciliation)' and c.relname not like 'command_suite_%' and not exists(select 1 from integration_control.command_suite_sources_v1 s where s.relation_name=n.nspname||'.'||c.relname);
 return jsonb_build_object('schema','ct.command.operating-suite.v1','status','OBSERVED','observed_at',clock_timestamp(),'sources',coalesce(sources,'[]'::jsonb),'coverage',jsonb_build_object('mapped_sources',coalesce(jsonb_array_length(sources),0),'other_candidate_relations',unmapped,'complete_universe_claimed',false,'candidate_count_is_not_missing_entities',true,'scope','Explicit metadata adapters; no arbitrary table exposure; direct source rows, not a second canonical ledger'),'controls',jsonb_build_object('private_records_require_existing_operator_grant',true,'management_mode','SOURCE_METADATA_RECONCILIATION_VIA_EXISTING_CHLOM_WORKER','provider_mutations_enabled',false,'new_scheduler_created',false));
end $f$;
revoke all on function public.ct_command_suite_overview_v1() from public,anon,authenticated;
grant execute on function public.ct_command_suite_overview_v1() to service_role;
create or replace function integration_control.command_suite_records_core_v1(p_source text,p_query text default '',p_cursor jsonb default null,p_limit integer default 50) returns jsonb language plpgsql stable security definer set search_path=pg_catalog,integration_control as $f$
declare s integration_control.command_suite_sources_v1%rowtype; b jsonb; q text; cols text; ks text; ordering text; predicate text; fromsql text; searchsql text; rows jsonb; nextc jsonb; take integer:=least(greatest(coalesce(p_limit,50),1),100); off integer:=0; record_columns text[];
begin
 if length(coalesce(p_query,''))>120 or octet_length(coalesce(p_cursor,'{}'::jsonb)::text)>4096 or (p_cursor is not null and jsonb_typeof(p_cursor)<>'object') then raise exception 'INVALID_QUERY' using errcode='22023'; end if;
 select * into s from integration_control.command_suite_sources_v1 where source_key=p_source;
 if not found then raise exception 'UNKNOWN_SOURCE' using errcode='22023'; end if;
 b:=integration_control.command_suite_binding_v1(p_source);
 if b->>'binding_state'<>'BOUND' then return jsonb_build_object('schema','ct.command.operating-suite.records.v1','status',b->>'binding_state','source',b,'rows','[]'::jsonb,'next_cursor',null,'observed_at',clock_timestamp()); end if;
 select array_agg(distinct c) into record_columns from unnest(s.key_columns||s.field_columns)c;
 select string_agg(format('%L,case when pg_typeof(t.%I)::text in (''text'',''character varying'') then to_jsonb(left(t.%I::text,2000)) else to_jsonb(t.%I) end',c,c,c,c),',') into cols from unnest(record_columns)c;
 select string_agg(format('%L,to_jsonb(t.%I)',c,c),','),string_agg(format('t.%I desc',c),',') into ks,ordering from unnest(s.key_columns)c;
 fromsql:=s.relation_name||' t';
 if p_source='activity' and coalesce(p_query,'')<>'' then fromsql:='(select sequence_id,event_id,event_type,source_system,entity_type,chain_anchor_state,created_at from chlom_runtime.dail_events order by sequence_id desc limit 10000) t'; end if;
 searchsql:='($1='''' or concat_ws('' '', '||(select string_agg(format('left(t.%I::text,2000)',c),',') from unnest(record_columns)c)||') ilike ''%''||$1||''%'' escape ''\'')';
 q:=replace(replace(replace(coalesce(p_query,''),'\','\\'),'%','\%'),'_','\_');
 if p_source='mcp' then off:=coalesce((p_cursor->>'offset')::integer,0); if off<0 or off>1000000 then raise exception 'INVALID_CURSOR'; end if; predicate:='true';
 else
 if p_cursor is not null and (not (p_cursor ?& s.key_columns) or exists(select 1 from jsonb_each(p_cursor) e where not(e.key=any(s.key_columns)) or e.value='null'::jsonb)) then raise exception 'INVALID_CURSOR' using errcode='22023'; end if;
 predicate:='($2 is null or ROW('||(select string_agg(format('t.%I',c),',') from unnest(s.key_columns)c)||') < ROW('||(select string_agg(format('(jsonb_populate_record(null::%s,$2)).%I',s.relation_name,c),',') from unnest(s.key_columns)c)||'))';
 end if;
 execute 'select coalesce(jsonb_agg(j),''[]''::jsonb) from (select jsonb_build_object('||cols||')||jsonb_build_object(''_cursor'',jsonb_build_object('||ks||')) j from '||fromsql||' where '||predicate||' and '||searchsql||' order by '||ordering||' limit $3 offset $4) z' into rows using q,p_cursor,take+1,off;
 if jsonb_array_length(rows)>take then rows:=rows-take; nextc:=case when p_source='mcp' then jsonb_build_object('offset',off+take) else rows->(take-1)->'_cursor' end; end if;
 return jsonb_build_object('schema','ct.command.operating-suite.records.v1','status','OBSERVED','source',b,'rows',rows,'next_cursor',nextc,'returned',jsonb_array_length(rows),'observed_at',clock_timestamp(),'search_scope',case when p_source='activity' and coalesce(p_query,'')<>'' then 'LATEST_10000_ACTUAL_EVENTS' else 'FULL_SELECTED_SOURCE_KEYSET' end,'consistency','LIVE_READ_COMMITTED; records can change between pages','provider_probe_performed',false);
end $f$;
revoke all on function integration_control.command_suite_records_core_v1(text,text,jsonb,integer) from public,anon,authenticated;
create or replace function public.ct_command_suite_records_v1(p_user_id uuid,p_source text,p_query text default '',p_cursor jsonb default null,p_limit integer default 50) returns jsonb language plpgsql stable security definer set search_path=pg_catalog,public,integration_control as $f$
begin
 if not public.ct_pentabrain_operator_authorized_v1(p_user_id,'pentabrain.state.read') then raise exception 'OPERATOR_GRANT_REQUIRED' using errcode='42501'; end if;
 return integration_control.command_suite_records_core_v1(p_source,p_query,p_cursor,p_limit);
end $f$;
revoke all on function public.ct_command_suite_records_v1(uuid,text,text,jsonb,integer) from public,anon,authenticated;
grant execute on function public.ct_command_suite_records_v1(uuid,text,text,jsonb,integer) to service_role;
create or replace function public.ct_command_suite_request_v1(p_user_id uuid,p_source text,p_action text,p_request_id uuid) returns jsonb language plpgsql security definer set search_path=pg_catalog,public,integration_control as $f$
declare v jsonb; saved text:=current_setting('request.jwt.claims',true); existing jsonb;
begin
 if not public.ct_pentabrain_operator_authorized_v1(p_user_id,'pentabrain.operator.manage') then raise exception 'OPERATOR_GRANT_REQUIRED' using errcode='42501'; end if;
 if p_action not in ('inspect','reconcile') or p_request_id is null then raise exception 'ACTION_NOT_ALLOWED' using errcode='22023'; end if;
 if not exists(select 1 from integration_control.command_suite_sources_v1 where source_key=p_source) then raise exception 'UNKNOWN_SOURCE' using errcode='22023'; end if;
 perform pg_advisory_xact_lock(hashtextextended('command-suite:'||p_user_id::text||':'||p_source,0));
 select jsonb_build_object('request_id',request_id,'state',state,'decision',decision,'idempotent_replay',true,'execution_effect',execution_effect) into existing from integration_control.chlom_mesh_action_requests_v1 where idempotency_key='command-suite:'||p_user_id::text||':'||p_request_id::text;
 if existing is not null then return existing; end if;
 if (select count(*) from integration_control.chlom_mesh_action_requests_v1 where requested_by=p_user_id::text and target_ref like 'command-source:%' and created_at>now()-interval '1 minute')>=10 then raise exception 'RATE_LIMITED' using errcode='54000'; end if;
 select jsonb_build_object('request_id',request_id,'state',state,'decision',decision,'idempotent_replay',true,'execution_effect',execution_effect) into existing from integration_control.chlom_mesh_action_requests_v1 where requested_by=p_user_id::text and target_ref='command-source:'||p_source and action_type=p_action and state in ('queued','running') order by created_at desc limit 1;
 if existing is not null then return existing; end if;
 perform set_config('request.jwt.claims',jsonb_build_object('role','service_role','sub',p_user_id)::text,true);
 v:=public.chlom_mesh_request_action_v1('command-suite:'||p_user_id::text||':'||p_request_id::text,p_action,'command-source:'||p_source,'Founder Command source-metadata reconciliation; no provider mutation.',jsonb_build_object('source',p_source,'contract','ct.command.operating-suite.v1','correlation_id','command-suite:'||p_request_id::text),'D1','A2');
 perform set_config('request.jwt.claims',coalesce(saved,''),true);
 return v;
end $f$;
revoke all on function public.ct_command_suite_request_v1(uuid,text,text,uuid) from public,anon,authenticated;
grant execute on function public.ct_command_suite_request_v1(uuid,text,text,uuid) to service_role;
create or replace function public.ct_command_suite_request_read_v1(p_user_id uuid,p_request_id uuid) returns jsonb language plpgsql stable security definer set search_path=pg_catalog,public,integration_control as $f$
declare v jsonb;
begin
 if not public.ct_pentabrain_operator_authorized_v1(p_user_id,'pentabrain.state.read') then raise exception 'OPERATOR_GRANT_REQUIRED' using errcode='42501'; end if;
 select jsonb_build_object('request_id',request_id,'action',action_type,'source',substring(target_ref from 16),'state',state,'decision',decision,'attempt_count',attempt_count,'execution_effect',execution_effect,'error_code',error_code,'created_at',created_at,'updated_at',updated_at,'completed_at',completed_at,'dail_event_id',dail_event_id) into v from integration_control.chlom_mesh_action_requests_v1 where request_id=p_request_id and target_ref like 'command-source:%';
 return coalesce(v,jsonb_build_object('state','NOT_FOUND'));
end $f$;
revoke all on function public.ct_command_suite_request_read_v1(uuid,uuid) from public,anon,authenticated;
grant execute on function public.ct_command_suite_request_read_v1(uuid,uuid) to service_role;
do $b$
declare d text; h text;
begin
 d:=pg_get_functiondef('integration_control.chlom_mesh_action_execute_one_v1(uuid,text)'::regprocedure);
 h:=encode(extensions.digest(convert_to(d,'UTF8'),'sha256'),'hex');
 if h<>'48b6523e2e0c792f5bff0dc2d0becd4f9dc3070d34802524fa21f09e1c17c034' then raise exception 'WORKER_SOURCE_CHANGED_REVIEW_REQUIRED'; end if;
 insert into integration_control.command_suite_change_snapshots_v1(change_key,source_definition,source_sha256) values('mesh-worker-before-command-suite-v1',d,h);
 execute replace(d,'FUNCTION integration_control.chlom_mesh_action_execute_one_v1(','FUNCTION integration_control.chlom_mesh_action_execute_one_before_suite_v1(');
end $b$;
revoke all on function integration_control.chlom_mesh_action_execute_one_before_suite_v1(uuid,text) from public,anon,authenticated;
create or replace function integration_control.chlom_mesh_action_execute_one_v1(p_request_id uuid,p_worker_ref text default 'ct.chlom.mesh-action-worker.v1') returns jsonb language plpgsql security definer set search_path=pg_catalog,integration_control,public,extensions as $f$
declare r integration_control.chlom_mesh_action_requests_v1%rowtype; sourcekey text; data jsonb; h text; vstate text;
begin
 select * into r from integration_control.chlom_mesh_action_requests_v1 where request_id=p_request_id;
 if not found or r.target_ref not like 'command-source:%' then return integration_control.chlom_mesh_action_execute_one_before_suite_v1(p_request_id,p_worker_ref); end if;
 if coalesce(auth.role(),'')<>'service_role' and session_user not in ('postgres','supabase_admin') then raise exception 'SERVICE_ROLE_REQUIRED' using errcode='42501'; end if;
 select * into r from integration_control.chlom_mesh_action_requests_v1 where request_id=p_request_id for update;
 if r.state in ('completed','failed','hold','quarantined') or (r.state='running' and r.lease_expires_at>clock_timestamp()) then return jsonb_build_object('request_id',r.request_id,'state',r.state,'execution_effect',r.execution_effect,'idempotent_replay',true); end if;
 if r.decision<>'ALLOW' or r.risk_class<>'D1' or r.action_type not in ('inspect','reconcile') or r.attempt_count>=r.max_attempts then
 update integration_control.chlom_mesh_action_requests_v1 set state='hold',decision='HOLD',error_code='COMMAND_SOURCE_GATE',updated_at=clock_timestamp() where request_id=r.request_id;
 return jsonb_build_object('request_id',r.request_id,'state','hold');
 end if;
 sourcekey:=substring(r.target_ref from 16);
 if not exists(select 1 from integration_control.command_suite_sources_v1 where source_key=sourcekey) or r.payload->>'source' is distinct from sourcekey then raise exception 'COMMAND_SOURCE_BINDING_INVALID'; end if;
 update integration_control.chlom_mesh_action_requests_v1 set state='running',attempt_count=attempt_count+1,started_at=coalesce(started_at,clock_timestamp()),updated_at=clock_timestamp() where request_id=r.request_id;
 begin data:=integration_control.command_suite_records_core_v1(sourcekey,'',null,1);
 exception when others then
 update integration_control.chlom_mesh_action_requests_v1 set state='hold',decision='HOLD',error_code='COMMAND_SOURCE_READ_FAILED',execution_effect='NO_EXTERNAL_EFFECT',completed_at=clock_timestamp(),updated_at=clock_timestamp() where request_id=r.request_id;
 perform integration_control.chlom_mesh_action_append_event_v1(r.request_id,'command.source.read_failed','hold',p_worker_ref,jsonb_build_object('source',sourcekey,'code','COMMAND_SOURCE_READ_FAILED'));
 return jsonb_build_object('request_id',r.request_id,'state','hold','error_code','COMMAND_SOURCE_READ_FAILED');
 end;
 h:=encode(extensions.digest(convert_to((data-'observed_at')::text,'UTF8'),'sha256'),'hex');
 vstate:=case when data->>'status'='OBSERVED' then 'completed' else 'hold' end;
 insert into integration_control.command_suite_observations_v1(source_key,checked_at,binding_state,sample_rows,sample_sha256,request_id,evidence) values(sourcekey,clock_timestamp(),data->>'status',jsonb_array_length(data->'rows'),h,r.request_id,jsonb_build_object('scope','SCHEMA_AND_ONE_ROW_METADATA_READBACK','provider_probe_performed',false,'source_mutation_performed',false,'sample_sha256',h)) on conflict(source_key) do update set checked_at=excluded.checked_at,binding_state=excluded.binding_state,sample_rows=excluded.sample_rows,sample_sha256=excluded.sample_sha256,request_id=excluded.request_id,evidence=excluded.evidence;
 update integration_control.chlom_mesh_action_requests_v1 set state=vstate,completed_at=clock_timestamp(),lease_expires_at=null,claimed_by=null,result=jsonb_build_object('source',sourcekey,'binding_state',data->>'status','metadata_sample_sha256',h,'scope','SCHEMA_AND_ONE_ROW_METADATA_READBACK','provider_probe_performed',false,'provider_mutation_performed',false),execution_effect='COMMAND_SOURCE_METADATA_READBACK',error_code=case when vstate='hold' then data->>'status' else null end,updated_at=clock_timestamp() where request_id=r.request_id;
 perform integration_control.chlom_mesh_action_append_event_v1(r.request_id,'command.source.reconciliation',vstate,p_worker_ref,jsonb_build_object('source',sourcekey,'metadata_sample_sha256',h,'scope','SCHEMA_AND_ONE_ROW_METADATA_READBACK','no_provider_mutation',true));
 return jsonb_build_object('request_id',r.request_id,'state',vstate,'execution_effect','COMMAND_SOURCE_METADATA_READBACK','sample_sha256',h,'provider_probe_performed',false);
end $f$;
comment on table integration_control.command_suite_sources_v1 is 'Explicit metadata-only Command adapters. New source rows are visible without snapshot regeneration. Not a complete universe claim.';
comment on function public.ct_command_suite_records_v1(uuid,text,text,jsonb,integer) is 'Validated server-side operator identity required. No raw config, credential, mail body, or document body projection.';
-- The finite source seed is maintained next to this migration in command_operating_suite_sources_v1.sql.
-- Run that seed after the core migration when initializing an equivalent estate.
notify pgrst,'reload schema';
