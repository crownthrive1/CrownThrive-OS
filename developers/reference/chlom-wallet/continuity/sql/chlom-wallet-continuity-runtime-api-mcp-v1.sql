-- CHLOM Wallet Continuity Runtime API + MCP v1
-- Private service-role-only controlled-test execution surface.
-- No provider write, money movement, Rights grant, chain broadcast, destructive recovery,
-- checkout, production activation, authority manufacture, merge authorization, or phase advancement.

create table if not exists chlom_wallet.continuity_api_request_receipts_v1 (
  request_id uuid primary key default gen_random_uuid(),
  suite_ref text not null references chlom_wallet.continuity_suite_versions_v1(suite_ref),
  transport text not null check (transport in ('HTTP','MCP')),
  method text not null,
  tool_name text,
  request_sha256 text not null check (request_sha256 ~ '^[a-f0-9]{64}$'),
  response_sha256 text not null check (response_sha256 ~ '^[a-f0-9]{64}$'),
  disposition text not null check (disposition in ('ECAC','HOLD','DENY')),
  protocol_version text not null,
  source_head_sha text not null check (source_head_sha ~ '^[a-f0-9]{40}$'),
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.continuity_runtime_releases_v1 (
  release_ref text primary key,
  parent_suite_ref text not null references chlom_wallet.continuity_suite_versions_v1(suite_ref),
  source_head_sha text not null check (source_head_sha ~ '^[a-f0-9]{40}$'),
  semantic_version text not null,
  edge_function_name text not null,
  edge_function_version bigint,
  deployment_ref text,
  endpoint_ref text not null,
  authorization_mode text not null default 'SERVICE_ROLE_ONLY',
  mcp_protocol_version text not null default '2026-07-28',
  state text not null default 'DEPLOYED_CANARY_PENDING',
  api_binding_state text not null default 'DEPLOYED_CANARY_PENDING',
  mcp_binding_state text not null default 'DEPLOYED_CANARY_PENDING',
  production_activation boolean not null default false check (not production_activation),
  authority_granted boolean not null default false check (not authority_granted),
  created_at timestamptz not null default now(),
  unique (source_head_sha, semantic_version)
);

create table if not exists chlom_wallet.continuity_runtime_canary_runs_v1 (
  canary_id uuid primary key default gen_random_uuid(),
  release_ref text not null references chlom_wallet.continuity_runtime_releases_v1(release_ref),
  source_head_sha text not null check (source_head_sha ~ '^[a-f0-9]{40}$'),
  canary_class text not null,
  result text not null,
  http_status integer,
  mcp_protocol_version text,
  authenticated_service_role boolean not null default false,
  response_sha256 text check (response_sha256 is null or response_sha256 ~ '^[a-f0-9]{64}$'),
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists continuity_api_receipts_suite_created_idx
  on chlom_wallet.continuity_api_request_receipts_v1(suite_ref,created_at desc);
create index if not exists continuity_api_receipts_tool_created_idx
  on chlom_wallet.continuity_api_request_receipts_v1(tool_name,created_at desc);
create index if not exists continuity_runtime_releases_parent_idx
  on chlom_wallet.continuity_runtime_releases_v1(parent_suite_ref);
create index if not exists continuity_runtime_canary_release_idx
  on chlom_wallet.continuity_runtime_canary_runs_v1(release_ref,created_at desc);

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'continuity_api_request_receipts_v1','continuity_runtime_releases_v1','continuity_runtime_canary_runs_v1'
  ] LOOP
    EXECUTE format('alter table chlom_wallet.%I enable row level security',t);
    EXECUTE format('alter table chlom_wallet.%I force row level security',t);
    EXECUTE format('revoke all on chlom_wallet.%I from public, anon, authenticated',t);
    EXECUTE format('drop trigger if exists continuity_append_only_guard on chlom_wallet.%I',t);
    EXECUTE format('create trigger continuity_append_only_guard before update or delete on chlom_wallet.%I for each row execute function chlom_wallet.reject_continuity_history_mutation_v1()',t);
  END LOOP;
END $$;

grant select,insert on chlom_wallet.continuity_api_request_receipts_v1 to service_role;
grant select,insert on chlom_wallet.continuity_runtime_releases_v1 to service_role;
grant select,insert on chlom_wallet.continuity_runtime_canary_runs_v1 to service_role;

create or replace function public.chlom_wallet_continuity_runtime_status_v1()
returns jsonb
language sql
stable
security invoker
set search_path = pg_catalog, chlom_wallet
as $$
  select chlom_wallet.continuity_status_v1();
$$;

create or replace function public.chlom_wallet_continuity_runtime_assets_v1(p_limit integer default 100,p_offset integer default 0)
returns jsonb
language plpgsql
stable
security invoker
set search_path = pg_catalog, chlom_wallet
as $$
declare v_suite text; v_limit integer;
begin
  v_limit := least(greatest(coalesce(p_limit,100),1),200);
  p_offset := greatest(coalesce(p_offset,0),0);
  select suite_ref into v_suite from chlom_wallet.continuity_suite_versions_v1 order by created_at desc limit 1;
  if v_suite is null then return jsonb_build_object('disposition','HOLD','reason','no_continuity_suite','items','[]'::jsonb); end if;
  return jsonb_build_object(
    'suite_ref',v_suite,
    'source_head_sha',(select source_head_sha from chlom_wallet.continuity_suite_versions_v1 where suite_ref=v_suite),
    'limit',v_limit,'offset',p_offset,
    'total',(select count(*) from chlom_wallet.continuity_asset_registry_v1 where suite_ref=v_suite),
    'items',coalesce((select jsonb_agg(to_jsonb(x) order by x.asset_id) from (
      select asset_id,asset_type,canonical_name,semantic_version,lifecycle_state,factory_domain_slug,
             factory_generation_binding,public_contract,candidate_only,asset_sha256
      from chlom_wallet.continuity_asset_registry_v1
      where suite_ref=v_suite order by asset_id limit v_limit offset p_offset
    ) x),'[]'::jsonb),
    'disposition','ECAC','authority_granted',false,'production_activation',false
  );
end;
$$;

create or replace function public.chlom_wallet_continuity_runtime_dependencies_v1()
returns jsonb
language plpgsql
stable
security invoker
set search_path = pg_catalog, chlom_wallet
as $$
declare v_suite text;
begin
  select suite_ref into v_suite from chlom_wallet.continuity_suite_versions_v1 order by created_at desc limit 1;
  if v_suite is null then return jsonb_build_object('disposition','HOLD','reason','no_continuity_suite','items','[]'::jsonb); end if;
  return jsonb_build_object(
    'suite_ref',v_suite,
    'items',coalesce((select jsonb_agg(to_jsonb(x) order by x.edge_ref) from (
      select edge_ref,source_ref,target_ref,dependency_class,required,fail_closed,source_head_sha
      from chlom_wallet.continuity_dependency_edges_v1 where suite_ref=v_suite
    ) x),'[]'::jsonb),
    'disposition','ECAC','authority_granted',false
  );
end;
$$;

create or replace function public.chlom_wallet_continuity_runtime_expiry_v1(
  p_observed_at timestamptz,
  p_ttl_seconds integer,
  p_explicit_state text default 'PASS'
)
returns jsonb
language plpgsql
stable
security invoker
set search_path = pg_catalog
as $$
declare v_age numeric; v_state text; v_reason text;
begin
  if p_explicit_state not in ('PASS','HOLD','DENY') then return jsonb_build_object('disposition','DENY','reason','invalid_explicit_state'); end if;
  if p_explicit_state='DENY' then return jsonb_build_object('disposition','DENY','reason','explicit_deny'); end if;
  if p_observed_at is null or p_ttl_seconds is null or p_ttl_seconds<=0 then return jsonb_build_object('disposition','HOLD','reason','missing_freshness_contract'); end if;
  v_age := extract(epoch from (clock_timestamp()-p_observed_at));
  if v_age<0 then v_state:='HOLD'; v_reason:='future_timestamp';
  elsif v_age>p_ttl_seconds then v_state:='HOLD'; v_reason:='stale_evidence';
  elsif p_explicit_state='HOLD' then v_state:='HOLD'; v_reason:='explicit_hold';
  else v_state:='ECAC'; v_reason:='fresh_evidence'; end if;
  return jsonb_build_object('disposition',v_state,'reason',v_reason,'age_seconds',floor(v_age),'ttl_seconds',p_ttl_seconds,'authority_granted',false);
end;
$$;

create or replace function public.chlom_wallet_continuity_runtime_oracle_observe_v1(
  p_oracle_id text,
  p_observed_at timestamptz,
  p_payload_digest text,
  p_source_confidence numeric
)
returns jsonb
language plpgsql
volatile
security invoker
set search_path = pg_catalog, chlom_wallet
as $$
declare
  v_suite text; v_connection chlom_wallet.continuity_oracle_connections_v1%rowtype;
  v_age numeric; v_disposition text; v_reason text; v_observation uuid;
begin
  if p_payload_digest is null or p_payload_digest !~ '^[a-fA-F0-9]{64}$' then return jsonb_build_object('disposition','DENY','reason','invalid_payload_digest'); end if;
  if p_source_confidence is null or p_source_confidence<0 or p_source_confidence>1 then return jsonb_build_object('disposition','DENY','reason','invalid_source_confidence'); end if;
  select suite_ref into v_suite from chlom_wallet.continuity_suite_versions_v1 order by created_at desc limit 1;
  select * into v_connection from chlom_wallet.continuity_oracle_connections_v1 where suite_ref=v_suite and oracle_id=p_oracle_id limit 1;
  if v_connection.connection_ref is null then return jsonb_build_object('disposition','HOLD','reason','oracle_not_registered'); end if;
  if v_connection.read_only is not true then v_disposition:='DENY'; v_reason:='oracle_not_read_only';
  elsif v_connection.connection_state like 'DENY%' or v_connection.connection_state like 'REVOKED%' then v_disposition:='DENY'; v_reason:='oracle_connection_denied';
  elsif p_observed_at is null then v_disposition:='HOLD'; v_reason:='missing_observed_at';
  else
    v_age:=extract(epoch from (clock_timestamp()-p_observed_at));
    if v_age<0 then v_disposition:='HOLD'; v_reason:='future_timestamp';
    elsif v_age>v_connection.freshness_ttl_seconds then v_disposition:='HOLD'; v_reason:='stale_oracle_observation';
    elsif v_connection.connection_state like 'HOLD%' then v_disposition:='HOLD'; v_reason:='oracle_runtime_binding_hold';
    elsif p_source_confidence<0.75 then v_disposition:='HOLD'; v_reason:='low_source_confidence';
    else v_disposition:='ECAC'; v_reason:='read_only_oracle_observation_accepted'; end if;
  end if;
  insert into chlom_wallet.continuity_oracle_observations_v1(connection_ref,observed_at,payload_digest,source_confidence,disposition,evidence)
  values(v_connection.connection_ref,coalesce(p_observed_at,clock_timestamp()),lower(p_payload_digest),p_source_confidence,v_disposition,
    jsonb_build_object('reason',v_reason,'raw_payload_stored',false,'credential_material_stored',false,'provider_write',false))
  returning observation_id into v_observation;
  return jsonb_build_object('observation_id',v_observation,'oracle_id',p_oracle_id,'disposition',v_disposition,'reason',v_reason,
    'raw_payload_stored',false,'provider_write',false,'authority_granted',false);
end;
$$;

create or replace function public.chlom_wallet_continuity_runtime_recovery_plan_v1(
  p_incident_ref text,
  p_backup_verified boolean,
  p_rollback_verified boolean,
  p_independent_review_state text,
  p_source_head_match boolean
)
returns jsonb
language plpgsql
volatile
security invoker
set search_path = pg_catalog, chlom_wallet
as $$
declare v_suite chlom_wallet.continuity_suite_versions_v1%rowtype; v_state text; v_plan uuid;
begin
  if p_incident_ref is null or length(p_incident_ref)<1 or length(p_incident_ref)>300 then return jsonb_build_object('disposition','DENY','reason','invalid_incident_ref'); end if;
  if p_independent_review_state not in ('ECAC','HOLD','DENY') then return jsonb_build_object('disposition','DENY','reason','invalid_independent_review_state'); end if;
  select * into v_suite from chlom_wallet.continuity_suite_versions_v1 order by created_at desc limit 1;
  if v_suite.suite_ref is null then return jsonb_build_object('disposition','HOLD','reason','no_continuity_suite'); end if;
  if p_independent_review_state='DENY' then v_state:='DENY';
  elsif coalesce(p_backup_verified,false) and coalesce(p_rollback_verified,false) and p_independent_review_state='ECAC' and coalesce(p_source_head_match,false) then v_state:='ECAC';
  else v_state:='HOLD'; end if;
  insert into chlom_wallet.continuity_recovery_plans_v1(
    suite_ref,incident_ref,source_head_sha,backup_verified,rollback_verified,independent_review_state,plan_state,
    automatic_destructive_action,provider_write,money_movement,rights_grant,chain_broadcast,plan
  ) values(
    v_suite.suite_ref,p_incident_ref,v_suite.source_head_sha,coalesce(p_backup_verified,false),coalesce(p_rollback_verified,false),p_independent_review_state,v_state,
    false,false,false,false,false,jsonb_build_object('mode',case when v_state='ECAC' then 'RECOVERY_PLAN_ELIGIBLE' else v_state end,'execution_authorized',false,'reversible_required',true)
  ) returning plan_id into v_plan;
  return jsonb_build_object('plan_id',v_plan,'disposition',v_state,'execution_authorized',false,'automatic_destructive_action',false,
    'provider_write',false,'money_movement',false,'rights_grant',false,'chain_broadcast',false);
end;
$$;

create or replace function public.chlom_wallet_continuity_runtime_truth_snapshot_v1()
returns jsonb
language plpgsql
volatile
security invoker
set search_path = pg_catalog, chlom_wallet
as $$
declare v_tick jsonb; v_status jsonb;
begin
  v_tick:=chlom_wallet.continuity_tick_v1();
  v_status:=chlom_wallet.continuity_status_v1();
  return jsonb_build_object('tick',v_tick,'status',v_status,'authority_granted',false,'production_activation',false);
end;
$$;

create or replace function public.chlom_wallet_continuity_runtime_factory_projection_v1()
returns jsonb
language plpgsql
stable
security invoker
set search_path = pg_catalog, chlom_wallet, extensions
as $$
declare v_suite chlom_wallet.continuity_suite_versions_v1%rowtype; v_root text;
begin
  select * into v_suite from chlom_wallet.continuity_suite_versions_v1 order by created_at desc limit 1;
  if v_suite.suite_ref is null then return jsonb_build_object('disposition','HOLD','reason','no_continuity_suite'); end if;
  select encode(digest(coalesce(string_agg(asset_id||':'||asset_sha256,'|' order by asset_id),''),'sha256'),'hex') into v_root
  from chlom_wallet.continuity_asset_registry_v1 where suite_ref=v_suite.suite_ref;
  return jsonb_build_object('suite_ref',v_suite.suite_ref,'source_head_sha',v_suite.source_head_sha,'factory_generation_binding',v_suite.factory_generation_binding,
    'generated_assets',(select count(*) from chlom_wallet.continuity_asset_registry_v1 where suite_ref=v_suite.suite_ref),
    'direct_components',(select count(*) from chlom_wallet.continuity_component_registry_v1 where suite_ref=v_suite.suite_ref),
    'projection_root_sha256',v_root,'factory_generation_advanced',false,'disposition','ECAC','authority_granted',false);
end;
$$;

create or replace function public.chlom_wallet_continuity_runtime_record_request_v1(
  p_transport text,
  p_method text,
  p_tool_name text,
  p_request_sha256 text,
  p_response_sha256 text,
  p_disposition text,
  p_protocol_version text
)
returns uuid
language plpgsql
volatile
security invoker
set search_path = pg_catalog, chlom_wallet
as $$
declare v_suite chlom_wallet.continuity_suite_versions_v1%rowtype; v_id uuid;
begin
  if p_transport not in ('HTTP','MCP') then raise exception 'invalid_transport'; end if;
  if p_disposition not in ('ECAC','HOLD','DENY') then raise exception 'invalid_disposition'; end if;
  if p_request_sha256 !~ '^[a-f0-9]{64}$' or p_response_sha256 !~ '^[a-f0-9]{64}$' then raise exception 'invalid_receipt_digest'; end if;
  select * into v_suite from chlom_wallet.continuity_suite_versions_v1 order by created_at desc limit 1;
  if v_suite.suite_ref is null then raise exception 'no_continuity_suite'; end if;
  insert into chlom_wallet.continuity_api_request_receipts_v1(
    suite_ref,transport,method,tool_name,request_sha256,response_sha256,disposition,protocol_version,source_head_sha
  ) values(v_suite.suite_ref,p_transport,p_method,p_tool_name,p_request_sha256,p_response_sha256,p_disposition,p_protocol_version,v_suite.source_head_sha)
  returning request_id into v_id;
  return v_id;
end;
$$;

create or replace function chlom_wallet.register_continuity_runtime_release_v1(
  p_source_head_sha text,
  p_edge_function_version bigint,
  p_deployment_ref text,
  p_endpoint_ref text,
  p_api_binding_state text default 'DEPLOYED_CANARY_PENDING',
  p_mcp_binding_state text default 'DEPLOYED_CANARY_PENDING'
)
returns jsonb
language plpgsql
volatile
security invoker
set search_path = pg_catalog, chlom_wallet
as $$
declare v_parent text; v_ref text;
begin
  if p_source_head_sha !~ '^[a-f0-9]{40}$' then raise exception 'invalid_source_head_sha'; end if;
  if p_endpoint_ref is null or length(p_endpoint_ref)<1 then raise exception 'missing_endpoint_ref'; end if;
  select suite_ref into v_parent from chlom_wallet.continuity_suite_versions_v1 order by created_at desc limit 1;
  if v_parent is null then raise exception 'no_parent_continuity_suite'; end if;
  v_ref:='ct.release.chlom-wallet.continuity-runtime-api-mcp.v1:'||p_source_head_sha;
  insert into chlom_wallet.continuity_runtime_releases_v1(
    release_ref,parent_suite_ref,source_head_sha,semantic_version,edge_function_name,edge_function_version,deployment_ref,endpoint_ref,
    authorization_mode,mcp_protocol_version,state,api_binding_state,mcp_binding_state,production_activation,authority_granted
  ) values(v_ref,v_parent,p_source_head_sha,'1.0.0','chlom-wallet-continuity',p_edge_function_version,p_deployment_ref,p_endpoint_ref,
    'SERVICE_ROLE_ONLY','2026-07-28','DEPLOYED_CANARY_PENDING',p_api_binding_state,p_mcp_binding_state,false,false);
  return jsonb_build_object('release_ref',v_ref,'source_head_sha',p_source_head_sha,'state','DEPLOYED_CANARY_PENDING',
    'api_binding_state',p_api_binding_state,'mcp_binding_state',p_mcp_binding_state,'authorization_mode','SERVICE_ROLE_ONLY','production_activation',false);
end;
$$;

create or replace function chlom_wallet.record_continuity_runtime_canary_v1(
  p_release_ref text,
  p_canary_class text,
  p_result text,
  p_http_status integer,
  p_mcp_protocol_version text,
  p_authenticated_service_role boolean,
  p_response_sha256 text,
  p_details jsonb default '{}'::jsonb
)
returns uuid
language plpgsql
volatile
security invoker
set search_path = pg_catalog, chlom_wallet
as $$
declare v_release chlom_wallet.continuity_runtime_releases_v1%rowtype; v_id uuid;
begin
  select * into v_release from chlom_wallet.continuity_runtime_releases_v1 where release_ref=p_release_ref;
  if v_release.release_ref is null then raise exception 'unknown_release_ref'; end if;
  insert into chlom_wallet.continuity_runtime_canary_runs_v1(
    release_ref,source_head_sha,canary_class,result,http_status,mcp_protocol_version,authenticated_service_role,response_sha256,details
  ) values(v_release.release_ref,v_release.source_head_sha,p_canary_class,p_result,p_http_status,p_mcp_protocol_version,coalesce(p_authenticated_service_role,false),p_response_sha256,coalesce(p_details,'{}'::jsonb))
  returning canary_id into v_id;
  return v_id;
end;
$$;

-- Public Data API RPCs are discoverable by name but executable only by service_role.
DO $$
DECLARE fn regprocedure;
BEGIN
  FOREACH fn IN ARRAY ARRAY[
    'public.chlom_wallet_continuity_runtime_status_v1()'::regprocedure,
    'public.chlom_wallet_continuity_runtime_assets_v1(integer,integer)'::regprocedure,
    'public.chlom_wallet_continuity_runtime_dependencies_v1()'::regprocedure,
    'public.chlom_wallet_continuity_runtime_expiry_v1(timestamptz,integer,text)'::regprocedure,
    'public.chlom_wallet_continuity_runtime_oracle_observe_v1(text,timestamptz,text,numeric)'::regprocedure,
    'public.chlom_wallet_continuity_runtime_recovery_plan_v1(text,boolean,boolean,text,boolean)'::regprocedure,
    'public.chlom_wallet_continuity_runtime_truth_snapshot_v1()'::regprocedure,
    'public.chlom_wallet_continuity_runtime_factory_projection_v1()'::regprocedure,
    'public.chlom_wallet_continuity_runtime_record_request_v1(text,text,text,text,text,text,text)'::regprocedure
  ] LOOP
    EXECUTE format('revoke all on function %s from public, anon, authenticated',fn);
    EXECUTE format('grant execute on function %s to service_role',fn);
  END LOOP;
END $$;

revoke all on function chlom_wallet.register_continuity_runtime_release_v1(text,bigint,text,text,text,text) from public,anon,authenticated;
revoke all on function chlom_wallet.record_continuity_runtime_canary_v1(text,text,text,integer,text,boolean,text,jsonb) from public,anon,authenticated;
grant execute on function chlom_wallet.register_continuity_runtime_release_v1(text,bigint,text,text,text,text) to service_role;
grant execute on function chlom_wallet.record_continuity_runtime_canary_v1(text,text,text,integer,text,boolean,text,jsonb) to service_role;
