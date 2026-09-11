-- ct.chlom.execution-builder-structural-replay-bridge.v1
-- Purpose: restore only the historical structural prerequisites required by
-- 20260823203649_execution_builder_agent_v1_0_1 on a blank replay database.
--
-- Production guard: current production already has chlom_runtime.agent_templates.
-- If that authoritative relation exists, this migration returns without mutation.
-- The replay bootstrap creates no credential, provider activation, sovereign vote,
-- certification effect, money movement, rights grant, D3 authority or durable DAIL write.

begin;

do $bridge$
declare
  v_replay_bootstrap boolean := to_regclass('chlom_runtime.agent_templates') is null;
begin
  if not v_replay_bootstrap then
    return;
  end if;

  create schema if not exists chlom_runtime;
  create schema if not exists institutional_federation;
  revoke all on schema chlom_runtime from public, anon, authenticated;
  revoke all on schema institutional_federation from public, anon, authenticated;

  create table chlom_runtime.agent_templates (
    agent_id text primary key,
    parent_agent_id text,
    canonical_name text not null,
    agent_class text not null,
    sovereignty_tier text,
    autonomy_class text not null,
    authority_ceiling text not null check (authority_ceiling in ('D0','D1','D2')),
    lifecycle_state text not null,
    module_scope text[] not null default '{}',
    tool_scope jsonb not null default '{}'::jsonb,
    allowed_actions text[] not null default '{}',
    denied_actions text[] not null default '{}',
    schedule_profile text,
    vote_eligible boolean not null default false check (not vote_eligible),
    self_healing_enabled boolean not null default false,
    no_self_approval boolean not null default true check (no_self_approval),
    heartbeat_ttl_seconds integer not null default 3600,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb
  );

  create table chlom_runtime.agent_suite_registry (
    suite_id text primary key,
    semantic_version text not null,
    canonical_name text not null,
    release_state text not null,
    manifest_ref text,
    manifest_sha256 text,
    parent_agent_id text,
    parent_certifier_id text,
    vote_eligible boolean not null default false check (not vote_eligible),
    quorum_eligible boolean not null default false check (not quorum_eligible),
    d3_human_reserved boolean not null default true check (d3_human_reserved),
    no_self_approval boolean not null default true check (no_self_approval),
    no_silent_delete boolean not null default true,
    drive_custody_required boolean not null default true,
    supabase_storage_required boolean not null default true,
    vault_secret_ref text,
    source_ids text[] not null default '{}',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
  );

  create table chlom_runtime.agent_skill_packages (
    skill_id text primary key,
    suite_id text not null,
    agent_id text not null,
    install_name text not null,
    semantic_version text not null,
    generation_support text[] not null default '{}',
    manifest_ref text,
    manifest_sha256 text,
    mcp_state text not null default 'candidate',
    commercial_state text not null default 'hold',
    price_credits numeric,
    checkout_enabled boolean not null default false check (not checkout_enabled),
    entitlement_active boolean not null default false check (not entitlement_active),
    release_receipt jsonb,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
  );

  create table chlom_runtime.agent_health (
    agent_id text primary key,
    health_state text not null,
    current_task text,
    resource_state jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
  );

  create table chlom_runtime.construction_work_queue (
    work_id text primary key,
    state text not null default 'hold',
    owner_agent_id text,
    verifier_agent_id text,
    scope_id text,
    required_outputs jsonb not null default '{}'::jsonb,
    workstream text,
    scope_type text,
    closes_gates jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
  );

  create table institutional_federation.capability_execution_queue (
    queue_id uuid primary key default extensions.gen_random_uuid(),
    risk_class text not null default 'D0' check (risk_class in ('D0','D1','D2')),
    requires_human boolean not null default false,
    execution_mode text not null default 'hold',
    queue_state text not null default 'hold',
    assigned_agent_id text,
    verifier_agent_id text,
    capability_id text,
    semantic_version text,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
  );

  alter table chlom_runtime.agent_templates enable row level security;
  alter table chlom_runtime.agent_templates force row level security;
  alter table chlom_runtime.agent_suite_registry enable row level security;
  alter table chlom_runtime.agent_suite_registry force row level security;
  alter table chlom_runtime.agent_skill_packages enable row level security;
  alter table chlom_runtime.agent_skill_packages force row level security;
  alter table chlom_runtime.agent_health enable row level security;
  alter table chlom_runtime.agent_health force row level security;
  alter table chlom_runtime.construction_work_queue enable row level security;
  alter table chlom_runtime.construction_work_queue force row level security;
  alter table institutional_federation.capability_execution_queue enable row level security;
  alter table institutional_federation.capability_execution_queue force row level security;

  revoke all on chlom_runtime.agent_templates from public, anon, authenticated, service_role;
  revoke all on chlom_runtime.agent_suite_registry from public, anon, authenticated, service_role;
  revoke all on chlom_runtime.agent_skill_packages from public, anon, authenticated, service_role;
  revoke all on chlom_runtime.agent_health from public, anon, authenticated, service_role;
  revoke all on chlom_runtime.construction_work_queue from public, anon, authenticated, service_role;
  revoke all on institutional_federation.capability_execution_queue from public, anon, authenticated, service_role;

  insert into chlom_runtime.agent_templates(
    agent_id,parent_agent_id,canonical_name,agent_class,autonomy_class,
    authority_ceiling,lifecycle_state,module_scope,schedule_profile,
    vote_eligible,self_healing_enabled,no_self_approval,metadata
  ) values
  ('ct.relay.agent-c',null,'Agent C — Replay Structural Parent','replay_compatibility','A0','D2','active','{}','replay_only',false,false,true,
    jsonb_build_object('replay_only_structural_bridge',true,'execution_authority',false,'provider_activation',false,'authority_created',false)),
  ('ct.relay.agent-d',null,'Agent D — Replay Structural Certifier Parent','replay_compatibility','A0','D2','active','{}','replay_only',false,false,true,
    jsonb_build_object('replay_only_structural_bridge',true,'certification_effect',false,'execution_authority',false,'authority_created',false));

  execute $fn$
    create function chlom_runtime.append_dail_event(
      p_event_type text,p_entity_type text,p_entity_id text,p_payload jsonb,
      p_actor_ref text,p_actor_did text,p_agent_id text,p_entity_version text,
      p_correlation_id text,p_causation_id text,p_authority_basis text,
      p_approval_id text,p_visibility_class text
    ) returns jsonb
    language sql
    security definer
    set search_path=pg_catalog
    as $body$
      select jsonb_build_object(
        'state','REPLAY_ONLY_NOOP',
        'event_type',p_event_type,
        'entity_type',p_entity_type,
        'entity_id',p_entity_id,
        'durable_write',false,
        'certification_effect',false,
        'authority_created',false
      )
    $body$
  $fn$;
  revoke all on function chlom_runtime.append_dail_event(text,text,text,jsonb,text,text,text,text,text,text,text,text,text) from public, anon, authenticated, service_role;
end
$bridge$;

do $verify$
declare
  v_replay boolean;
begin
  select exists(
    select 1 from chlom_runtime.agent_templates
    where agent_id='ct.relay.agent-c'
      and metadata->>'replay_only_structural_bridge'='true'
  ) into v_replay;

  if v_replay then
    if not exists(select 1 from chlom_runtime.agent_templates where agent_id='ct.relay.agent-c' and lifecycle_state='active' and authority_ceiling='D2' and vote_eligible=false and no_self_approval=true)
       or not exists(select 1 from chlom_runtime.agent_templates where agent_id='ct.relay.agent-d' and lifecycle_state='active' and authority_ceiling='D2' and vote_eligible=false and no_self_approval=true)
       or to_regclass('chlom_runtime.agent_suite_registry') is null
       or to_regclass('chlom_runtime.agent_skill_packages') is null
       or to_regclass('chlom_runtime.agent_health') is null
       or to_regclass('chlom_runtime.construction_work_queue') is null
       or to_regclass('institutional_federation.capability_execution_queue') is null
       or to_regprocedure('chlom_runtime.append_dail_event(text,text,text,jsonb,text,text,text,text,text,text,text,text,text)') is null
    then raise exception 'HOLD_EXECUTION_BUILDER_REPLAY_BRIDGE_INCOMPLETE'; end if;
  end if;
end
$verify$;

commit;
