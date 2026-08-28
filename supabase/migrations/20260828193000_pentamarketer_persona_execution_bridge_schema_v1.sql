-- CrownThrive OS / PentaMarketer Persona Execution Bridge v1
-- Stable component: ct.pentamarketer.persona-execution-bridge
-- Risk ceiling: D2. D3 is always fail-closed.
-- Side effects: internal queue/event writes and fixed calls to already-governed Penta RPCs.
-- Provider writes, money movement, rights grants, credential body access, and merge authority
-- are not implemented by this bridge.

create schema if not exists crm;

create table if not exists crm.penta_persona_execution_control_v1 (
  control_key text primary key default 'default',
  active boolean not null default true,
  automation_enabled boolean not null default false,
  kill_switch boolean not null default false,
  max_batch_size integer not null default 10 check (max_batch_size between 1 and 100),
  max_attempts integer not null default 5 check (max_attempts between 1 and 10),
  component_version text not null default '1.0.0',
  certification_state text not null default 'controlled_test'
    check (certification_state in ('controlled_test','certified','production','hold')),
  certification_id text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (control_key='default')
);

insert into crm.penta_persona_execution_control_v1(control_key)
values ('default') on conflict (control_key) do nothing;

create table if not exists crm.penta_persona_execution_capabilities_v1 (
  persona_id text not null references crm.penta_marketer_personas_v1(persona_id),
  capability_key text not null,
  handler_key text not null,
  penta_system_key text not null,
  risk_class text not null check (risk_class in ('D0','D1','D2')),
  authority_ceiling text not null check (authority_ceiling in ('D0','D1','D2')),
  requires_entitlement boolean not null default false,
  requires_chlom_invocation boolean not null default false,
  requires_readback boolean not null default true,
  reversible boolean not null default true,
  enabled boolean not null default true,
  certification_state text not null default 'controlled_test'
    check (certification_state in ('controlled_test','certified','production','hold')),
  config jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key(persona_id, capability_key)
);

create table if not exists crm.penta_persona_execution_playbooks_v1 (
  playbook_key text primary key,
  persona_id text references crm.penta_marketer_personas_v1(persona_id),
  work_class text,
  purpose text,
  capability_key text not null,
  risk_class text not null default 'D1' check (risk_class in ('D0','D1','D2')),
  authority_class text not null default 'D1' check (authority_class in ('D0','D1','D2')),
  input_template jsonb not null default '{}'::jsonb,
  auto_enqueue boolean not null default true,
  priority integer not null default 100,
  enabled boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (persona_id is not null or work_class is not null or purpose is not null)
);

create table if not exists crm.penta_persona_execution_requests_v1 (
  request_id uuid primary key default gen_random_uuid(),
  work_id uuid references crm.penta_marketer_work_queue_v1(work_id) on delete set null,
  persona_id text not null references crm.penta_marketer_personas_v1(persona_id),
  agent_id text not null references crm.penta_marketer_agents_v2(agent_id),
  capability_key text not null,
  idempotency_key text not null unique,
  correlation_id text not null,
  risk_class text not null check (risk_class in ('D0','D1','D2','D3')),
  authority_class text not null check (authority_class in ('D0','D1','D2','D3')),
  state text not null default 'queued'
    check (state in ('queued','held_authority','held_entitlement','held_chlom','running','retry_wait','succeeded','failed_terminal','cancelled')),
  entitlement_flow_id uuid,
  chlom_invocation_id uuid,
  input jsonb not null default '{}'::jsonb,
  context jsonb not null default '{}'::jsonb,
  attempt_count integer not null default 0 check (attempt_count >= 0),
  max_attempts integer not null default 5 check (max_attempts between 1 and 10),
  next_attempt_at timestamptz not null default now(),
  claimed_by text,
  lease_expires_at timestamptz,
  result jsonb not null default '{}'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  error_code text,
  error_message text,
  simulation boolean not null default false,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key(persona_id, capability_key)
    references crm.penta_persona_execution_capabilities_v1(persona_id, capability_key)
);

create table if not exists crm.penta_persona_execution_events_v1 (
  event_id uuid primary key default gen_random_uuid(),
  request_id uuid references crm.penta_persona_execution_requests_v1(request_id) on delete restrict,
  event_type text not null,
  actor_ref text not null,
  correlation_id text not null,
  state text,
  details jsonb not null default '{}'::jsonb,
  event_sha256 text not null unique,
  created_at timestamptz not null default now()
);

create index if not exists idx_penta_persona_exec_requests_ready_v1
  on crm.penta_persona_execution_requests_v1(state,next_attempt_at,created_at)
  where state in ('queued','retry_wait');
create index if not exists idx_penta_persona_exec_requests_work_v1
  on crm.penta_persona_execution_requests_v1(work_id,created_at desc);
create index if not exists idx_penta_persona_exec_events_request_v1
  on crm.penta_persona_execution_events_v1(request_id,created_at);
create index if not exists idx_penta_persona_exec_capability_system_v1
  on crm.penta_persona_execution_capabilities_v1(penta_system_key,enabled);

alter table crm.penta_persona_execution_control_v1 enable row level security;
alter table crm.penta_persona_execution_capabilities_v1 enable row level security;
alter table crm.penta_persona_execution_playbooks_v1 enable row level security;
alter table crm.penta_persona_execution_requests_v1 enable row level security;
alter table crm.penta_persona_execution_events_v1 enable row level security;

drop policy if exists penta_persona_execution_control_service_role_v1 on crm.penta_persona_execution_control_v1;
create policy penta_persona_execution_control_service_role_v1 on crm.penta_persona_execution_control_v1
for all to service_role using (true) with check (true);
drop policy if exists penta_persona_execution_capabilities_service_role_v1 on crm.penta_persona_execution_capabilities_v1;
create policy penta_persona_execution_capabilities_service_role_v1 on crm.penta_persona_execution_capabilities_v1
for all to service_role using (true) with check (true);
drop policy if exists penta_persona_execution_playbooks_service_role_v1 on crm.penta_persona_execution_playbooks_v1;
create policy penta_persona_execution_playbooks_service_role_v1 on crm.penta_persona_execution_playbooks_v1
for all to service_role using (true) with check (true);
drop policy if exists penta_persona_execution_requests_service_role_v1 on crm.penta_persona_execution_requests_v1;
create policy penta_persona_execution_requests_service_role_v1 on crm.penta_persona_execution_requests_v1
for all to service_role using (true) with check (true);
drop policy if exists penta_persona_execution_events_service_role_v1 on crm.penta_persona_execution_events_v1;
create policy penta_persona_execution_events_service_role_v1 on crm.penta_persona_execution_events_v1
for all to service_role using (true) with check (true);

revoke all on crm.penta_persona_execution_control_v1 from anon, authenticated;
revoke all on crm.penta_persona_execution_capabilities_v1 from anon, authenticated;
revoke all on crm.penta_persona_execution_playbooks_v1 from anon, authenticated;
revoke all on crm.penta_persona_execution_requests_v1 from anon, authenticated;
revoke all on crm.penta_persona_execution_events_v1 from anon, authenticated;

create or replace function crm.penta_persona_authority_rank_v1(p_class text)
returns integer language sql immutable
set search_path='pg_catalog'
as $$
  select case p_class when 'D0' then 0 when 'D1' then 1 when 'D2' then 2 when 'D3' then 3 else 99 end
$$;

create or replace function crm.penta_persona_payload_safe_v1(p_payload jsonb)
returns boolean language plpgsql immutable
set search_path='pg_catalog'
as $$
declare r record;
begin
  if p_payload is null then return true; end if;
  if jsonb_typeof(p_payload)='object' then
    for r in select key,value from jsonb_each(p_payload) loop
      if lower(r.key) ~ '(^|[_-])(password|passwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|private[_-]?key|client[_-]?secret|credential)([_-]|$)'
         and lower(r.key) not like '%_ref'
         and lower(r.key) not like '%_id'
         and lower(r.key) not in ('opaque_handle','fingerprint','public_key_fingerprint','secret_exposure_indicator') then
        return false;
      end if;
      if not crm.penta_persona_payload_safe_v1(r.value) then return false; end if;
    end loop;
  elsif jsonb_typeof(p_payload)='array' then
    for r in select value from jsonb_array_elements(p_payload) loop
      if not crm.penta_persona_payload_safe_v1(r.value) then return false; end if;
    end loop;
  end if;
  return true;
end $$;

create or replace function crm.penta_persona_append_execution_event_v1(
  p_request_id uuid,p_event_type text,p_actor_ref text,p_correlation_id text,p_state text,p_details jsonb default '{}'::jsonb
) returns uuid language plpgsql security definer
set search_path='pg_catalog','crm','extensions'
as $$
declare v_id uuid:=gen_random_uuid(); v_sha text;
begin
  v_sha:=encode(extensions.digest(convert_to(
    coalesce(p_request_id::text,'none')||'|'||coalesce(p_event_type,'')||'|'||
    coalesce(p_actor_ref,'')||'|'||coalesce(p_correlation_id,'')||'|'||
    coalesce(p_state,'')||'|'||coalesce(p_details,'{}'::jsonb)::text||'|'||v_id::text,'UTF8'
  ),'sha256'),'hex');
  insert into crm.penta_persona_execution_events_v1(
    event_id,request_id,event_type,actor_ref,correlation_id,state,details,event_sha256
  ) values(v_id,p_request_id,p_event_type,p_actor_ref,p_correlation_id,p_state,coalesce(p_details,'{}'::jsonb),v_sha);
  return v_id;
end $$;

create or replace function crm.penta_persona_execution_event_immutable_v1()
returns trigger language plpgsql
set search_path='pg_catalog'
as $$ begin raise exception 'PENTA_PERSONA_EXECUTION_EVENTS_APPEND_ONLY'; end $$;
drop trigger if exists penta_persona_execution_events_immutable_v1 on crm.penta_persona_execution_events_v1;
create trigger penta_persona_execution_events_immutable_v1
before update or delete on crm.penta_persona_execution_events_v1
for each row execute function crm.penta_persona_execution_event_immutable_v1();

create or replace function crm.penta_persona_capability_sync_v1()
returns jsonb language plpgsql security definer
set search_path='pg_catalog','crm'
as $$
declare v_count integer;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;

  insert into crm.penta_persona_execution_capabilities_v1(
    persona_id,capability_key,handler_key,penta_system_key,risk_class,authority_ceiling,
    requires_entitlement,requires_chlom_invocation,requires_readback,reversible,enabled,config
  )
  select a.persona_id,x.capability_key,x.handler_key,x.penta_system_key,x.risk_class,
         case when crm.penta_persona_authority_rank_v1(a.risk_ceiling) < crm.penta_persona_authority_rank_v1(x.authority_ceiling)
              then a.risk_ceiling else x.authority_ceiling end,
         false,false,true,true,true,x.config
  from crm.penta_marketer_agents_v2 a
  cross join lateral (values
    ('penta.system.status','penta_system_status','penta.reports','D0','D1','{}'::jsonb),
    ('penta.maker.select','penta_maker_select','penta.maker','D0','D1','{}'::jsonb),
    ('penta.mation.run','penta_mation_run','penta.mation','D1','D2','{}'::jsonb),
    ('chlom.mesh.request','chlom_mesh_request','penta.meshes','D1','D2','{"allowed_actions":["inspect","reconcile","bind","repair","heartbeat","publication_request"]}'::jsonb),
    ('persona.handoff','persona_handoff','penta.workforce','D1','D2','{}'::jsonb)
  ) as x(capability_key,handler_key,penta_system_key,risk_class,authority_ceiling,config)
  where a.enabled=true and a.autonomous=true and a.state='active'
  on conflict(persona_id,capability_key) do update set
    handler_key=excluded.handler_key,penta_system_key=excluded.penta_system_key,
    risk_class=excluded.risk_class,authority_ceiling=excluded.authority_ceiling,
    enabled=true,config=excluded.config,updated_at=now();

  insert into crm.penta_persona_execution_capabilities_v1(
    persona_id,capability_key,handler_key,penta_system_key,risk_class,authority_ceiling,
    requires_entitlement,requires_chlom_invocation,requires_readback,reversible,enabled,config
  )
  select a.persona_id,'penta.service.quote','penta_service_quote','penta.flow','D0','D1',
         false,false,true,true,true,'{}'::jsonb
  from crm.penta_marketer_agents_v2 a
  where a.enabled=true and a.autonomous=true and a.state='active'
    and a.lane in ('sales_closing','sales_engineering','sales_leadership','business_operations',
                   'customer_success','custom_music_services','programming_sponsorship',
                   'licensing_sync','ip_adaptation','artist_submission')
  on conflict(persona_id,capability_key) do update set enabled=true,updated_at=now();

  insert into crm.penta_persona_execution_capabilities_v1(
    persona_id,capability_key,handler_key,penta_system_key,risk_class,authority_ceiling,
    requires_entitlement,requires_chlom_invocation,requires_readback,reversible,enabled,config
  )
  select a.persona_id,'virality.knowledge','virality_knowledge','penta.flow','D0','D1',
         false,false,true,true,true,'{}'::jsonb
  from crm.penta_marketer_agents_v2 a
  where a.persona_id in (
    'ct.persona.backroad.artist-relations.sierra.v1',
    'ct.persona.backroad.programming.malik.v1',
    'ct.persona.virality.licensing.tessa.v1',
    'ct.persona.virality.commissions.ellis.v1',
    'ct.persona.virality.ip.camille.v1'
  )
  on conflict(persona_id,capability_key) do update set enabled=true,updated_at=now();

  insert into crm.penta_persona_execution_capabilities_v1(
    persona_id,capability_key,handler_key,penta_system_key,risk_class,authority_ceiling,
    requires_entitlement,requires_chlom_invocation,requires_readback,reversible,enabled,config
  )
  select a.persona_id,'virality.service.quote','virality_service_quote','penta.green','D0','D1',
         false,false,true,true,true,'{}'::jsonb
  from crm.penta_marketer_agents_v2 a
  where a.persona_id in (
    'ct.persona.backroad.artist-relations.sierra.v1',
    'ct.persona.backroad.programming.malik.v1',
    'ct.persona.virality.licensing.tessa.v1',
    'ct.persona.virality.commissions.ellis.v1',
    'ct.persona.virality.ip.camille.v1'
  )
  on conflict(persona_id,capability_key) do update set enabled=true,updated_at=now();

  insert into crm.penta_persona_execution_capabilities_v1(
    persona_id,capability_key,handler_key,penta_system_key,risk_class,authority_ceiling,
    requires_entitlement,requires_chlom_invocation,requires_readback,reversible,enabled,config
  )
  select a.persona_id,'go.flipbooks.quote','go_flipbooks_quote','go.flipbooks','D0','D1',
         false,false,true,true,true,'{}'::jsonb
  from crm.penta_marketer_agents_v2 a
  where a.persona_id='ct.persona.locticians.lead-concierge.maya.v1'
  on conflict(persona_id,capability_key) do update set enabled=true,updated_at=now();

  select count(*) into v_count from crm.penta_persona_execution_capabilities_v1 where enabled;
  return jsonb_build_object('status','ok','enabled_capability_bindings',v_count,'d3_auto',false,'authority_expansion',false,'at',now());
end $$;
