-- CrownThrive CHLOM provider-agent-runtime replay topology readback v2.
-- Terminal, fail-closed structural assertion for a newly provisioned data-less preview.
-- This receipt does not authorize production deployment, commerce, or Penta advancement by itself.

begin;

create schema if not exists chlom_runtime;

create table if not exists chlom_runtime.replay_topology_receipts (
  receipt_id text primary key,
  contract_version text not null,
  status text not null check (status in ('PASS','HOLD')),
  migration_version text not null,
  provider_versions jsonb not null,
  topology_evidence jsonb not null,
  data_boundary text not null,
  penta_gate text not null,
  observed_at timestamptz not null default now()
);

alter table chlom_runtime.replay_topology_receipts enable row level security;
alter table chlom_runtime.replay_topology_receipts force row level security;
revoke all on chlom_runtime.replay_topology_receipts from public, anon, authenticated;
grant select, insert, update on chlom_runtime.replay_topology_receipts to service_role;

comment on table chlom_runtime.replay_topology_receipts is
  'Fail-closed structural replay evidence. External branch metadata must independently prove a data-less preview and terminal MIGRATIONS_PASSED before dependent Penta advancement.';

do $assert$
declare
  v_problem text;
  v_count integer;
begin
  with expected(version,name) as (
    values
      ('20260819020805','integration_control_plane_v1'),
      ('20260819164517','credential_continuity_registry_v1'),
      ('20260820182344','chlom_identity_foundation'),
      ('20260821021521','chlom_modular_metaprotocol_control_plane_v1'),
      ('20260821021702','chlom_runtime_rpc_surface_v1'),
      ('20260821021745','chlom_dedicated_mcp_server_scope_v1'),
      ('20260821021758','chlom_public_identity_admin_rpc_v1'),
      ('20260821022105','chlom_runtime_deployment_evidence_v1'),
      ('20260821022237','chlom_google_drive_recovery_capsule_verified_v1'),
      ('20260821022535','chlom_fluid_module_agent_oracle_registry_v1'),
      ('20260821030452','chlom_construction_work_queue_v1'),
      ('20260821050436','agent_capability_master_suite_v1'),
      ('20260822193302','institutional_capability_runtime_v1'),
      ('20260823203546','execution_builder_capability_contract_identity_v1'),
      ('20260823203649','execution_builder_agent_v1_0_1')
  )
  select string_agg(e.version || ':' || e.name, ', ' order by e.version)
  into v_problem
  from expected e
  left join supabase_migrations.schema_migrations m
    on m.version=e.version and m.name=e.name
  where m.version is null;
  if v_problem is not null then
    raise exception 'HOLD_PROVIDER_MIGRATION_IDENTITIES_MISSING: %', v_problem;
  end if;

  select count(*) into v_count
  from supabase_migrations.schema_migrations
  where version in ('20260823202950','20260823203100');
  if v_count<>0 then
    raise exception 'HOLD_NONPROVIDER_EXECUTION_BUILDER_IDENTITIES_ACTIVE: %', v_count;
  end if;

  with expected(schema_name,object_name,relkind) as (
    values
      ('integration_control','services','r'::"char"),
      ('integration_control','mcp_tools','r'::"char"),
      ('integration_control','credential_continuity_registry','r'::"char"),
      ('integration_control','runtime_variable_registry','r'::"char"),
      ('chlom_identity','subjects','r'::"char"),
      ('chlom_identity','key_registry','r'::"char"),
      ('chlom_identity','public_identity_records','r'::"char"),
      ('chlom_identity','fingerprints','r'::"char"),
      ('chlom_secrets','trade_secret_assets','r'::"char"),
      ('chlom_runtime','modules','r'::"char"),
      ('chlom_runtime','module_capabilities','r'::"char"),
      ('chlom_runtime','platform_bindings','r'::"char"),
      ('chlom_runtime','vaulted_capability_registry','r'::"char"),
      ('chlom_runtime','capability_contracts','v'::"char"),
      ('chlom_runtime','agent_templates','r'::"char"),
      ('chlom_runtime','agent_health','r'::"char"),
      ('chlom_runtime','agent_suite_registry','r'::"char"),
      ('chlom_runtime','agent_skill_packages','r'::"char"),
      ('chlom_runtime','construction_work_queue','r'::"char"),
      ('chlom_runtime','dail_events','r'::"char"),
      ('institutional_federation','continuity_compiler_runs','r'::"char"),
      ('institutional_federation','capability_execution_queue','r'::"char")
  ), observed as (
    select n.nspname schema_name,c.relname object_name,c.relkind
    from pg_class c join pg_namespace n on n.oid=c.relnamespace
  )
  select string_agg(
    e.schema_name || '.' || e.object_name ||
    ':expected=' || e.relkind::text ||
    ':actual=' || coalesce(o.relkind::text,'MISSING'),
    ', ' order by e.schema_name,e.object_name
  )
  into v_problem
  from expected e
  left join observed o using(schema_name,object_name)
  where o.object_name is null or o.relkind<>e.relkind;
  if v_problem is not null then
    raise exception 'HOLD_REPLAY_RELATION_TOPOLOGY_DRIFT: %', v_problem;
  end if;

  with expected(schema_name,table_name,pk_column) as (
    values
      ('integration_control','services','service_id'),
      ('integration_control','mcp_tools','tool_name'),
      ('integration_control','credential_continuity_registry','credential_id'),
      ('integration_control','runtime_variable_registry','variable_key'),
      ('chlom_identity','subjects','subject_id'),
      ('chlom_identity','key_registry','key_id'),
      ('chlom_identity','public_identity_records','public_id'),
      ('chlom_identity','fingerprints','fingerprint_id'),
      ('chlom_secrets','trade_secret_assets','asset_id'),
      ('chlom_runtime','modules','module_id'),
      ('chlom_runtime','module_capabilities','capability_id'),
      ('chlom_runtime','platform_bindings','binding_id'),
      ('chlom_runtime','vaulted_capability_registry','capability_id'),
      ('chlom_runtime','agent_templates','agent_id'),
      ('chlom_runtime','agent_health','agent_id'),
      ('chlom_runtime','agent_suite_registry','suite_id'),
      ('chlom_runtime','agent_skill_packages','skill_id'),
      ('chlom_runtime','construction_work_queue','work_id'),
      ('chlom_runtime','dail_events','sequence_id'),
      ('institutional_federation','continuity_compiler_runs','run_id'),
      ('institutional_federation','capability_execution_queue','queue_id')
  ), observed as (
    select n.nspname schema_name,t.relname table_name,
           pg_get_constraintdef(k.oid,true) definition
    from pg_constraint k
    join pg_class t on t.oid=k.conrelid
    join pg_namespace n on n.oid=t.relnamespace
    where k.contype='p'
  )
  select string_agg(e.schema_name || '.' || e.table_name || '(' || e.pk_column || ')', ', '
                    order by e.schema_name,e.table_name)
  into v_problem
  from expected e
  left join observed o
    on o.schema_name=e.schema_name
   and o.table_name=e.table_name
   and o.definition ilike '%(' || e.pk_column || ')%'
  where o.table_name is null;
  if v_problem is not null then
    raise exception 'HOLD_REPLAY_PRIMARY_KEY_DRIFT: %', v_problem;
  end if;

  with expected(schema_name,table_name) as (
    values
      ('integration_control','services'),
      ('integration_control','mcp_tools'),
      ('integration_control','credential_continuity_registry'),
      ('integration_control','runtime_variable_registry'),
      ('chlom_identity','subjects'),
      ('chlom_identity','key_registry'),
      ('chlom_identity','public_identity_records'),
      ('chlom_identity','fingerprints'),
      ('chlom_secrets','trade_secret_assets'),
      ('chlom_runtime','modules'),
      ('chlom_runtime','module_capabilities'),
      ('chlom_runtime','platform_bindings'),
      ('chlom_runtime','vaulted_capability_registry'),
      ('chlom_runtime','agent_templates'),
      ('chlom_runtime','agent_health'),
      ('chlom_runtime','agent_suite_registry'),
      ('chlom_runtime','agent_skill_packages'),
      ('chlom_runtime','construction_work_queue'),
      ('chlom_runtime','dail_events'),
      ('institutional_federation','continuity_compiler_runs'),
      ('institutional_federation','capability_execution_queue')
  )
  select string_agg(e.schema_name || '.' || e.table_name, ', '
                    order by e.schema_name,e.table_name)
  into v_problem
  from expected e
  join pg_namespace n on n.nspname=e.schema_name
  join pg_class c on c.relnamespace=n.oid and c.relname=e.table_name
  where not c.relrowsecurity;
  if v_problem is not null then
    raise exception 'HOLD_REPLAY_RLS_MISSING: %', v_problem;
  end if;

  with expected(schema_name,table_name) as (
    values
      ('chlom_identity','subjects'),
      ('chlom_identity','key_registry'),
      ('chlom_identity','public_identity_records'),
      ('chlom_identity','fingerprints'),
      ('chlom_secrets','trade_secret_assets'),
      ('chlom_runtime','modules'),
      ('chlom_runtime','module_capabilities'),
      ('chlom_runtime','platform_bindings'),
      ('chlom_runtime','vaulted_capability_registry'),
      ('chlom_runtime','agent_templates'),
      ('chlom_runtime','agent_health'),
      ('chlom_runtime','agent_suite_registry'),
      ('chlom_runtime','agent_skill_packages'),
      ('chlom_runtime','construction_work_queue'),
      ('chlom_runtime','dail_events'),
      ('institutional_federation','continuity_compiler_runs'),
      ('institutional_federation','capability_execution_queue')
  )
  select string_agg(e.schema_name || '.' || e.table_name, ', '
                    order by e.schema_name,e.table_name)
  into v_problem
  from expected e
  join pg_namespace n on n.nspname=e.schema_name
  join pg_class c on c.relnamespace=n.oid and c.relname=e.table_name
  where not c.relforcerowsecurity;
  if v_problem is not null then
    raise exception 'HOLD_REPLAY_FORCE_RLS_MISSING: %', v_problem;
  end if;

  select count(*) into v_count
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_runtime'
    and p.proname='append_dail_event'
    and pg_get_function_identity_arguments(p.oid)=
      'p_event_type text, p_entity_type text, p_entity_id text, p_payload jsonb, p_actor_ref text, p_actor_did text, p_agent_id text, p_entity_version text, p_correlation_id text, p_causation_id text, p_authority_basis text, p_approval_id text, p_visibility_class text'
    and pg_get_function_result(p.oid)='jsonb';
  if v_count<>1 then
    raise exception 'HOLD_DAIL_APPEND_CONTRACT_DRIFT: %', v_count;
  end if;

  with expected(agent_id,agent_class,authority_ceiling) as (
    values
      ('ct.relay.agent-c','builder','D2'),
      ('ct.relay.agent-d','verifier','D2')
  )
  select string_agg(
    e.agent_id || ':expected=' || e.agent_class || '/' || e.authority_ceiling ||
    ':actual=' || coalesce(a.agent_class || '/' || a.authority_ceiling || '/' || a.lifecycle_state,'MISSING'),
    ', ' order by e.agent_id
  )
  into v_problem
  from expected e
  left join chlom_runtime.agent_templates a on a.agent_id=e.agent_id
  where a.agent_id is null
     or a.agent_class<>e.agent_class
     or a.authority_ceiling<>e.authority_ceiling
     or a.lifecycle_state<>'active'
     or not a.no_self_approval;
  if v_problem is not null then
    raise exception 'HOLD_EXECUTION_BUILDER_RELAY_AGENT_DRIFT: %', v_problem;
  end if;

  if pg_get_viewdef('chlom_runtime.capability_contracts'::regclass,true)
       not ilike '%chlom_runtime.vaulted_capability_registry%' then
    raise exception 'HOLD_CAPABILITY_CONTRACT_VIEW_STORAGE_DRIFT';
  end if;
end
$assert$;

insert into chlom_runtime.replay_topology_receipts (
  receipt_id,
  contract_version,
  status,
  migration_version,
  provider_versions,
  topology_evidence,
  data_boundary,
  penta_gate,
  observed_at
)
select
  'ct.supabase.chlom-agent-runtime-replay-topology.20260904.v2',
  'crownthrive.supabase.chlom-agent-runtime-replay-topology/v2',
  'PASS',
  '20260904150000',
  (
    select jsonb_agg(jsonb_build_object('version',version,'name',name) order by version)
    from supabase_migrations.schema_migrations
    where version in (
      '20260819020805','20260819164517','20260820182344',
      '20260821021521','20260821021702','20260821021745',
      '20260821021758','20260821022105','20260821022237',
      '20260821022535','20260821030452','20260821050436',
      '20260822193302','20260823203546','20260823203649'
    )
  ),
  jsonb_build_object(
    'relations', (
      select jsonb_agg(jsonb_build_object(
        'schema',n.nspname,
        'object',c.relname,
        'relkind',c.relkind,
        'rls',c.relrowsecurity,
        'force_rls',c.relforcerowsecurity
      ) order by n.nspname,c.relname)
      from pg_class c join pg_namespace n on n.oid=c.relnamespace
      where (n.nspname,c.relname) in (
        ('integration_control','services'),
        ('integration_control','mcp_tools'),
        ('integration_control','credential_continuity_registry'),
        ('integration_control','runtime_variable_registry'),
        ('chlom_identity','subjects'),
        ('chlom_identity','key_registry'),
        ('chlom_identity','public_identity_records'),
        ('chlom_identity','fingerprints'),
        ('chlom_secrets','trade_secret_assets'),
        ('chlom_runtime','modules'),
        ('chlom_runtime','module_capabilities'),
        ('chlom_runtime','platform_bindings'),
        ('chlom_runtime','vaulted_capability_registry'),
        ('chlom_runtime','capability_contracts'),
        ('chlom_runtime','agent_templates'),
        ('chlom_runtime','agent_health'),
        ('chlom_runtime','agent_suite_registry'),
        ('chlom_runtime','agent_skill_packages'),
        ('chlom_runtime','construction_work_queue'),
        ('chlom_runtime','dail_events'),
        ('institutional_federation','continuity_compiler_runs'),
        ('institutional_federation','capability_execution_queue')
      )
    ),
    'primary_keys', (
      select jsonb_agg(jsonb_build_object(
        'schema',n.nspname,
        'table',t.relname,
        'constraint',k.conname,
        'definition',pg_get_constraintdef(k.oid,true)
      ) order by n.nspname,t.relname)
      from pg_constraint k
      join pg_class t on t.oid=k.conrelid
      join pg_namespace n on n.oid=t.relnamespace
      where k.contype='p'
        and (n.nspname,t.relname) in (
          ('integration_control','services'),
          ('integration_control','mcp_tools'),
          ('integration_control','credential_continuity_registry'),
          ('integration_control','runtime_variable_registry'),
          ('chlom_identity','subjects'),
          ('chlom_identity','key_registry'),
          ('chlom_identity','public_identity_records'),
          ('chlom_identity','fingerprints'),
          ('chlom_secrets','trade_secret_assets'),
          ('chlom_runtime','modules'),
          ('chlom_runtime','module_capabilities'),
          ('chlom_runtime','platform_bindings'),
          ('chlom_runtime','vaulted_capability_registry'),
          ('chlom_runtime','agent_templates'),
          ('chlom_runtime','agent_health'),
          ('chlom_runtime','agent_suite_registry'),
          ('chlom_runtime','agent_skill_packages'),
          ('chlom_runtime','construction_work_queue'),
          ('chlom_runtime','dail_events'),
          ('institutional_federation','continuity_compiler_runs'),
          ('institutional_federation','capability_execution_queue')
        )
    ),
    'relay_agents', (
      select jsonb_agg(jsonb_build_object(
        'agent_id',agent_id,
        'canonical_name',canonical_name,
        'agent_class',agent_class,
        'autonomy_class',autonomy_class,
        'authority_ceiling',authority_ceiling,
        'lifecycle_state',lifecycle_state,
        'no_self_approval',no_self_approval
      ) order by agent_id)
      from chlom_runtime.agent_templates
      where agent_id in ('ct.relay.agent-c','ct.relay.agent-d')
    ),
    'dail_append_contract_count', (
      select count(*)
      from pg_proc p join pg_namespace n on n.oid=p.pronamespace
      where n.nspname='chlom_runtime' and p.proname='append_dail_event'
    ),
    'nonprovider_execution_builder_identity_count', (
      select count(*)
      from supabase_migrations.schema_migrations
      where version in ('20260823202950','20260823203100')
    ),
    'foundation_provider_identity_count', (
      select count(*)
      from supabase_migrations.schema_migrations
      where version in (
        '20260819020805','20260819164517','20260820182344',
        '20260821021521','20260821021702','20260821021745',
        '20260821021758','20260821022105','20260821022237'
      )
    ),
    'agent_runtime_provider_identity_count', (
      select count(*)
      from supabase_migrations.schema_migrations
      where version in (
        '20260821022535','20260821030452','20260821050436',
        '20260822193302','20260823203546','20260823203649'
      )
    ),
    'capability_contract_view_definition',
      pg_get_viewdef('chlom_runtime.capability_contracts'::regclass,true)
  ),
  'MIGRATION_DEFINED_SEED_DATA_ONLY; EXTERNAL BRANCH METADATA MUST CONFIRM with_data=false',
  'HOLD_PENDING_EXTERNAL_MIGRATIONS_PASSED_AND_INDEPENDENT_READBACK',
  now()
on conflict (receipt_id) do update
set
  status=excluded.status,
  provider_versions=excluded.provider_versions,
  topology_evidence=excluded.topology_evidence,
  data_boundary=excluded.data_boundary,
  penta_gate=excluded.penta_gate,
  observed_at=excluded.observed_at;

commit;
