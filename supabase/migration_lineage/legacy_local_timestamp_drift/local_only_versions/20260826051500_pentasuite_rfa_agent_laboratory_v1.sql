-- PentaSuite v1: PentaRFA-only agent laboratory, lease, remediation, rollback, and appeals substrate.

create table if not exists public.pentarfa_agent_requests (
  id uuid primary key default gen_random_uuid(),
  request_key text not null unique,
  request_kind text not null default 'new_agent' check (request_kind in ('new_agent','amendment','renewal','reapplication')),
  parent_request_id uuid references public.pentarfa_agent_requests(id) on delete set null,
  requester_ref text not null,
  agent_key text not null,
  display_name text not null,
  purpose text not null,
  job_contract jsonb not null default '{}'::jsonb,
  requested_scope jsonb not null default '{}'::jsonb,
  requested_scale jsonb not null default '{}'::jsonb,
  requested_ttl_seconds integer not null check (requested_ttl_seconds > 0),
  authority_class text not null default 'D1' check (authority_class in ('D0','D1','D2','D3')),
  state text not null default 'submitted' check (state in ('submitted','under_review','granted','conditional_grant','denied','withdrawn','expired','superseded')),
  adjudication jsonb not null default '{}'::jsonb,
  adjudicated_by text,
  adjudicator_class text,
  adjudicated_at timestamptz,
  granted_ttl_seconds integer check (granted_ttl_seconds is null or granted_ttl_seconds > 0),
  granted_scope jsonb,
  granted_scale jsonb,
  conditions jsonb not null default '[]'::jsonb,
  lockout_seconds integer check (lockout_seconds is null or lockout_seconds > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.pentasuite_agent_blueprints (
  id uuid primary key default gen_random_uuid(),
  request_id uuid not null unique references public.pentarfa_agent_requests(id) on delete cascade,
  agent_key text not null,
  blueprint_version integer not null default 1 check (blueprint_version > 0),
  state text not null default 'materializing' check (state in ('materializing','factory_dispatched','built','validated','failed','superseded')),
  manifest jsonb not null default '{}'::jsonb,
  factory_build_request_id uuid references public.ct_factory_build_requests(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.pentasuite_agent_leases (
  id uuid primary key default gen_random_uuid(),
  request_id uuid not null unique references public.pentarfa_agent_requests(id) on delete cascade,
  blueprint_id uuid not null unique references public.pentasuite_agent_blueprints(id) on delete cascade,
  agent_key text not null,
  state text not null default 'staged' check (state in ('staged','active','conditional','remediation','restricted','suspended','rollback_pending','rolled_back','expired','revoked','barred','completed')),
  lease_generation integer not null default 1 check (lease_generation > 0),
  ttl_seconds integer not null check (ttl_seconds > 0),
  starts_at timestamptz,
  expires_at timestamptz,
  remediation_due_at timestamptz,
  scope_envelope jsonb not null default '{}'::jsonb,
  scale_ceiling jsonb not null default '{}'::jsonb,
  conditions jsonb not null default '[]'::jsonb,
  strike_count integer not null default 0 check (strike_count >= 0),
  last_heartbeat_at timestamptz,
  rollback_contract jsonb not null default '{}'::jsonb,
  rollback_build_request_id uuid references public.ct_factory_build_requests(id) on delete set null,
  reapply_after timestamptz,
  status_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.pentasuite_agent_assets (
  id uuid primary key default gen_random_uuid(),
  blueprint_id uuid not null references public.pentasuite_agent_blueprints(id) on delete cascade,
  asset_key text not null,
  asset_type text not null,
  state text not null default 'planned' check (state in ('planned','generated','validated','active','failed','rolled_back','superseded')),
  payload jsonb not null default '{}'::jsonb,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (blueprint_id, asset_key)
);

create table if not exists public.pentasuite_remediation_items (
  id uuid primary key default gen_random_uuid(),
  lease_id uuid not null references public.pentasuite_agent_leases(id) on delete cascade,
  issue_key text not null,
  severity text not null default 'medium' check (severity in ('low','medium','high','critical')),
  requirement text not null,
  state text not null default 'open' check (state in ('open','evidence_submitted','verified','failed','waived_by_governance')),
  due_at timestamptz not null,
  evidence jsonb not null default '{}'::jsonb,
  verified_by text,
  verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (lease_id, issue_key)
);

create table if not exists public.pentasuite_lockouts (
  id uuid primary key default gen_random_uuid(),
  requester_ref text not null,
  agent_key text not null,
  lease_id uuid references public.pentasuite_agent_leases(id) on delete set null,
  reason text not null,
  strike_count integer not null default 1 check (strike_count > 0),
  starts_at timestamptz not null default now(),
  ends_at timestamptz not null,
  state text not null default 'active' check (state in ('active','expired','lifted_by_governance')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.pentasuite_appeals (
  id uuid primary key default gen_random_uuid(),
  appeal_key text not null unique,
  request_id uuid references public.pentarfa_agent_requests(id) on delete set null,
  lease_id uuid references public.pentasuite_agent_leases(id) on delete set null,
  lockout_id uuid references public.pentasuite_lockouts(id) on delete set null,
  appellant_ref text not null,
  appealed_action text not null,
  grounds text not null,
  state text not null default 'filed' check (state in ('filed','accepted_for_review','denied','remanded','modified','upheld','withdrawn','board_escalation')),
  governance_layer text not null default 'ThriveAlumni - The Governmental Layer',
  primary_body text not null default 'Membership and Ethics Committee',
  final_body text not null default 'Board of Directors',
  stay_requested boolean not null default false,
  stay_granted boolean not null default false,
  decision jsonb not null default '{}'::jsonb,
  decided_by text,
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (request_id is not null or lease_id is not null or lockout_id is not null)
);

create table if not exists public.pentasuite_lifecycle_events (
  id bigint generated always as identity primary key,
  request_id uuid references public.pentarfa_agent_requests(id) on delete set null,
  lease_id uuid references public.pentasuite_agent_leases(id) on delete set null,
  event_type text not null,
  actor_ref text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists pentarfa_agent_state_idx on public.pentarfa_agent_requests(state, authority_class, created_at);
create index if not exists pentasuite_lease_state_idx on public.pentasuite_agent_leases(state, expires_at, remediation_due_at);
create index if not exists pentasuite_lockout_active_idx on public.pentasuite_lockouts(requester_ref, agent_key, state, ends_at);
create index if not exists pentasuite_appeal_state_idx on public.pentasuite_appeals(state, created_at);
create index if not exists pentasuite_events_request_idx on public.pentasuite_lifecycle_events(request_id, created_at desc);
create index if not exists pentasuite_events_lease_idx on public.pentasuite_lifecycle_events(lease_id, created_at desc);

alter table public.pentarfa_agent_requests enable row level security;
alter table public.pentasuite_agent_blueprints enable row level security;
alter table public.pentasuite_agent_leases enable row level security;
alter table public.pentasuite_agent_assets enable row level security;
alter table public.pentasuite_remediation_items enable row level security;
alter table public.pentasuite_lockouts enable row level security;
alter table public.pentasuite_appeals enable row level security;
alter table public.pentasuite_lifecycle_events enable row level security;

create or replace function public.pentasuite_emit_event(
  p_request_id uuid,
  p_lease_id uuid,
  p_event_type text,
  p_actor_ref text,
  p_payload jsonb default '{}'::jsonb
) returns bigint
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare v_id bigint;
begin
  insert into public.pentasuite_lifecycle_events(request_id, lease_id, event_type, actor_ref, payload)
  values (p_request_id, p_lease_id, p_event_type, p_actor_ref, coalesce(p_payload,'{}'::jsonb))
  returning id into v_id;
  return v_id;
end;
$$;

create or replace function public.pentarfa_submit_agent_request(
  p_request_key text,
  p_request_kind text,
  p_parent_request_id uuid,
  p_requester_ref text,
  p_agent_key text,
  p_display_name text,
  p_purpose text,
  p_job_contract jsonb,
  p_requested_scope jsonb,
  p_requested_scale jsonb,
  p_requested_ttl_seconds integer,
  p_authority_class text default 'D1'
) returns uuid
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare v_id uuid;
begin
  if p_requested_ttl_seconds is null or p_requested_ttl_seconds <= 0 then
    raise exception 'PentaRFA requires a positive TTL';
  end if;
  if p_authority_class not in ('D0','D1','D2','D3') then
    raise exception 'invalid authority class';
  end if;
  if p_request_kind not in ('new_agent','amendment','renewal','reapplication') then
    raise exception 'invalid request kind';
  end if;
  if exists (
    select 1 from public.pentasuite_lockouts
    where requester_ref = p_requester_ref and agent_key = p_agent_key
      and state='active' and ends_at > now()
  ) then
    raise exception 'PentaRFA reapplication locked out for this requester/agent pair';
  end if;
  insert into public.pentarfa_agent_requests(
    request_key, request_kind, parent_request_id, requester_ref, agent_key, display_name,
    purpose, job_contract, requested_scope, requested_scale, requested_ttl_seconds, authority_class
  ) values (
    p_request_key, p_request_kind, p_parent_request_id, p_requester_ref, p_agent_key, p_display_name,
    p_purpose, coalesce(p_job_contract,'{}'::jsonb), coalesce(p_requested_scope,'{}'::jsonb),
    coalesce(p_requested_scale,'{}'::jsonb), p_requested_ttl_seconds, p_authority_class
  ) returning id into v_id;
  perform public.pentasuite_emit_event(v_id, null, 'pentarfa.submitted', p_requester_ref,
    jsonb_build_object('request_kind',p_request_kind,'authority_class',p_authority_class,'requested_ttl_seconds',p_requested_ttl_seconds));
  return v_id;
end;
$$;

create or replace function public.pentarfa_adjudicate_agent_request(
  p_request_id uuid,
  p_decision text,
  p_actor_ref text,
  p_actor_class text,
  p_granted_ttl_seconds integer default null,
  p_granted_scope jsonb default null,
  p_granted_scale jsonb default null,
  p_conditions jsonb default '[]'::jsonb,
  p_lockout_seconds integer default null,
  p_reason text default null
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare r public.pentarfa_agent_requests%rowtype;
begin
  select * into r from public.pentarfa_agent_requests where id=p_request_id for update;
  if not found then raise exception 'PentaRFA request not found'; end if;
  if r.state not in ('submitted','under_review') then raise exception 'request is not adjudicable from state %', r.state; end if;
  if p_decision not in ('granted','conditional_grant','denied') then raise exception 'invalid adjudication decision'; end if;
  if r.authority_class='D3' and p_actor_class <> 'human_governance' then
    raise exception 'D3 agent authority remains human-reserved';
  end if;
  if p_decision in ('granted','conditional_grant') then
    if p_granted_ttl_seconds is null or p_granted_ttl_seconds <= 0 then raise exception 'accepted PentaRFA requires granted TTL'; end if;
    if p_lockout_seconds is null or p_lockout_seconds <= 0 then raise exception 'accepted PentaRFA requires a lockout period for failed/revoked leases'; end if;
  end if;
  if p_decision='conditional_grant' and (p_conditions is null or jsonb_typeof(p_conditions) <> 'array' or jsonb_array_length(p_conditions)=0) then
    raise exception 'conditional grant requires at least one remediation condition';
  end if;
  update public.pentarfa_agent_requests
  set state=p_decision,
      adjudicated_by=p_actor_ref,
      adjudicator_class=p_actor_class,
      adjudicated_at=now(),
      granted_ttl_seconds=case when p_decision='denied' then null else p_granted_ttl_seconds end,
      granted_scope=case when p_decision='denied' then null else coalesce(p_granted_scope, requested_scope) end,
      granted_scale=case when p_decision='denied' then null else coalesce(p_granted_scale, requested_scale) end,
      conditions=case when p_decision='conditional_grant' then p_conditions else '[]'::jsonb end,
      lockout_seconds=case when p_decision='denied' then null else p_lockout_seconds end,
      adjudication=jsonb_build_object('decision',p_decision,'reason',p_reason,'actor_ref',p_actor_ref,'actor_class',p_actor_class,'at',now()),
      updated_at=now()
  where id=p_request_id;
  perform public.pentasuite_emit_event(p_request_id, null, 'pentarfa.'||p_decision, p_actor_ref,
    jsonb_build_object('reason',p_reason,'granted_ttl_seconds',p_granted_ttl_seconds,'conditions',coalesce(p_conditions,'[]'::jsonb)));
  return jsonb_build_object('request_id',p_request_id,'decision',p_decision);
end;
$$;

create or replace function public.pentasuite_materialize_agent(p_request_id uuid, p_actor_ref text default 'pentasuite')
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare r public.pentarfa_agent_requests%rowtype;
declare v_blueprint uuid;
declare v_lease uuid;
declare v_build uuid;
declare v_project uuid;
declare v_manifest jsonb;
declare v_due timestamptz;
begin
  select * into r from public.pentarfa_agent_requests where id=p_request_id for update;
  if not found then raise exception 'PentaRFA request not found'; end if;
  if r.state not in ('granted','conditional_grant') then raise exception 'PentaSuite may build only from granted or conditional PentaRFA'; end if;
  if exists (select 1 from public.pentasuite_agent_blueprints where request_id=p_request_id) then
    select b.id,l.id,b.factory_build_request_id into v_blueprint,v_lease,v_build
    from public.pentasuite_agent_blueprints b join public.pentasuite_agent_leases l on l.blueprint_id=b.id
    where b.request_id=p_request_id;
    return jsonb_build_object('request_id',p_request_id,'blueprint_id',v_blueprint,'lease_id',v_lease,'factory_build_request_id',v_build,'idempotent',true);
  end if;

  v_manifest := jsonb_build_object(
    'contract','ct.pentasuite.agent-blueprint.v1',
    'origin','PentaRFA-only',
    'request_id',p_request_id,
    'agent_key',r.agent_key,
    'display_name',r.display_name,
    'purpose',r.purpose,
    'job_contract',r.job_contract,
    'authority_class',r.authority_class,
    'scope',r.granted_scope,
    'scale_ceiling',r.granted_scale,
    'ttl_seconds',r.granted_ttl_seconds,
    'conditional',r.state='conditional_grant',
    'conditions',r.conditions,
    'governance',jsonb_build_object('appeals_layer','ThriveAlumni - The Governmental Layer','primary_body','Membership and Ethics Committee','final_body','Board of Directors'),
    'runtime_rule','no authority survives lease expiry, revocation, rollback, or bar'
  );

  insert into public.pentasuite_agent_blueprints(request_id,agent_key,manifest)
  values (p_request_id,r.agent_key,v_manifest) returning id into v_blueprint;

  v_due := case when r.state='conditional_grant' then now() + make_interval(secs => r.granted_ttl_seconds) else null end;
  insert into public.pentasuite_agent_leases(
    request_id, blueprint_id, agent_key, state, ttl_seconds, remediation_due_at,
    scope_envelope, scale_ceiling, conditions, rollback_contract
  ) values (
    p_request_id,v_blueprint,r.agent_key,
    case when r.state='conditional_grant' then 'conditional' else 'staged' end,
    r.granted_ttl_seconds,v_due,coalesce(r.granted_scope,'{}'::jsonb),coalesce(r.granted_scale,'{}'::jsonb),r.conditions,
    jsonb_build_object('contract','ct.pentasuite.rollback.v1','required',true,'mode','revoke-disable-restore-last-safe-baseline')
  ) returning id into v_lease;

  insert into public.pentasuite_agent_assets(blueprint_id,asset_key,asset_type,payload)
  select v_blueprint, x.asset_key, x.asset_type, x.payload
  from (values
    ('identity','identity',jsonb_build_object('agent_key',r.agent_key,'display_name',r.display_name,'request_id',p_request_id)),
    ('job-contract','mission_job_contract',r.job_contract),
    ('authority-policy','authority_policy',jsonb_build_object('authority_class',r.authority_class,'scope',r.granted_scope,'ttl_seconds',r.granted_ttl_seconds)),
    ('skills','skill_manifest',jsonb_build_object('derive_from_job_contract',true)),
    ('tools-adapters','tool_adapter_manifest',jsonb_build_object('derive_from_job_contract',true,'least_privilege',true)),
    ('data-access','data_access_contract',jsonb_build_object('scope',r.granted_scope,'default','deny')),
    ('secret-bindings','secret_binding_refs',jsonb_build_object('values_forbidden',true,'references_only',true)),
    ('runtime','runtime_config',jsonb_build_object('ttl_seconds',r.granted_ttl_seconds,'scale_ceiling',r.granted_scale)),
    ('tests','test_plan',jsonb_build_object('required',true,'job_contract_tests',true,'authority_boundary_tests',true,'rollback_tests',true)),
    ('observability','observability',jsonb_build_object('events',true,'heartbeat',true,'lease_monitor',true,'scope_monitor',true)),
    ('continuity','continuity_checkpoint',jsonb_build_object('checkpoint_required',true,'resume_from_evidence',true)),
    ('rollback','rollback_plan',jsonb_build_object('required',true,'on_expiry',true,'on_revocation',true,'on_failed_remediation',true)),
    ('documentation','documentation',jsonb_build_object('required',true,'public_safe_only',true)),
    ('scaling','scaling_contract',jsonb_build_object('ceiling',r.granted_scale,'expansion_requires_new_pentarfa',true)),
    ('remediation','remediation_contract',jsonb_build_object('conditional',r.state='conditional_grant','due_at',v_due,'lease_or_lose',true)),
    ('appeals','appeal_metadata',jsonb_build_object('layer','ThriveAlumni - The Governmental Layer','body','Membership and Ethics Committee','final_body','Board of Directors'))
  ) as x(asset_key,asset_type,payload);

  if r.state='conditional_grant' then
    insert into public.pentasuite_remediation_items(lease_id,issue_key,severity,requirement,due_at)
    select v_lease,
           coalesce(c->>'key','condition-'||ord::text),
           case when coalesce(c->>'severity','medium') in ('low','medium','high','critical') then coalesce(c->>'severity','medium') else 'medium' end,
           coalesce(c->>'requirement',c::text),
           v_due
    from jsonb_array_elements(r.conditions) with ordinality as t(c,ord)
    on conflict (lease_id, issue_key) do nothing;
  end if;

  select id into v_project from public.ct_factory_projects where project_key='crownthrive-os-v2-factory' order by created_at limit 1;
  if v_project is not null then
    insert into public.ct_factory_build_requests(
      project_id,request_key,source_type,source_ref,objective,requirements,requested_release_channel,priority,status,governance_class,evidence
    ) values (
      v_project,
      'pentasuite-'||p_request_id::text,
      'pentasuite_rfa',
      'pentarfa:'||p_request_id::text,
      'Materialize complete PentaSuite agent package for '||r.agent_key||' strictly from accepted PentaRFA '||p_request_id::text,
      jsonb_build_array(
        jsonb_build_object('type','agent_blueprint','blueprint_id',v_blueprint),
        jsonb_build_object('type','rfa_only_origin','request_id',p_request_id),
        jsonb_build_object('type','lease','ttl_seconds',r.granted_ttl_seconds,'conditional',r.state='conditional_grant'),
        jsonb_build_object('type','assets','required',jsonb_build_array('identity','mission_job_contract','authority_policy','skill_manifest','tool_adapter_manifest','data_access_contract','secret_binding_refs','runtime_config','test_plan','observability','continuity_checkpoint','rollback_plan','documentation','scaling_contract','remediation_contract','appeal_metadata'))
      ),
      'staging',
      1,
      'queued',
      r.authority_class,
      jsonb_build_object('pentasuite_blueprint_id',v_blueprint,'pentarfa_request_id',p_request_id)
    ) on conflict (request_key) do update set updated_at=now()
    returning id into v_build;
    update public.pentasuite_agent_blueprints set factory_build_request_id=v_build,state='factory_dispatched',updated_at=now() where id=v_blueprint;
  end if;

  perform public.pentasuite_emit_event(p_request_id,v_lease,'pentasuite.materialized',p_actor_ref,jsonb_build_object('blueprint_id',v_blueprint,'factory_build_request_id',v_build));
  return jsonb_build_object('request_id',p_request_id,'blueprint_id',v_blueprint,'lease_id',v_lease,'factory_build_request_id',v_build,'idempotent',false);
end;
$$;

create or replace function public.pentasuite_heartbeat(p_lease_id uuid, p_actor_ref text default 'agent-runtime', p_payload jsonb default '{}'::jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare l public.pentasuite_agent_leases%rowtype;
begin
  select * into l from public.pentasuite_agent_leases where id=p_lease_id for update;
  if not found then raise exception 'lease not found'; end if;
  if l.state not in ('active','conditional','remediation','restricted') then raise exception 'lease state % cannot heartbeat',l.state; end if;
  if l.expires_at is not null and l.expires_at <= now() then raise exception 'lease expired'; end if;
  update public.pentasuite_agent_leases set last_heartbeat_at=now(),updated_at=now() where id=p_lease_id;
  perform public.pentasuite_emit_event(l.request_id,p_lease_id,'pentasuite.heartbeat',p_actor_ref,p_payload);
  return jsonb_build_object('lease_id',p_lease_id,'state',l.state,'expires_at',l.expires_at);
end;
$$;

create or replace function public.pentasuite_submit_remediation(p_lease_id uuid,p_issue_key text,p_actor_ref text,p_evidence jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare v_request uuid;
begin
  update public.pentasuite_remediation_items
  set state='evidence_submitted',evidence=coalesce(p_evidence,'{}'::jsonb),updated_at=now()
  where lease_id=p_lease_id and issue_key=p_issue_key and state in ('open','failed');
  if not found then raise exception 'open remediation item not found'; end if;
  select request_id into v_request from public.pentasuite_agent_leases where id=p_lease_id;
  perform public.pentasuite_emit_event(v_request,p_lease_id,'pentasuite.remediation.evidence_submitted',p_actor_ref,jsonb_build_object('issue_key',p_issue_key));
  return jsonb_build_object('lease_id',p_lease_id,'issue_key',p_issue_key,'state','evidence_submitted');
end;
$$;

create or replace function public.pentasuite_verify_remediation(p_lease_id uuid,p_issue_key text,p_actor_ref text,p_pass boolean,p_note text default null)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare v_request uuid;
begin
  update public.pentasuite_remediation_items
  set state=case when p_pass then 'verified' else 'failed' end,
      verified_by=p_actor_ref,verified_at=now(),updated_at=now(),
      evidence=evidence || jsonb_build_object('verification_note',p_note,'verification_pass',p_pass)
  where lease_id=p_lease_id and issue_key=p_issue_key and state in ('evidence_submitted','failed','open');
  if not found then raise exception 'remediation item not found or already closed'; end if;
  select request_id into v_request from public.pentasuite_agent_leases where id=p_lease_id;
  perform public.pentasuite_emit_event(v_request,p_lease_id,'pentasuite.remediation.'||case when p_pass then 'verified' else 'failed' end,p_actor_ref,jsonb_build_object('issue_key',p_issue_key,'note',p_note));
  return jsonb_build_object('lease_id',p_lease_id,'issue_key',p_issue_key,'verified',p_pass);
end;
$$;

create or replace function public.pentasuite_enforce_lease(
  p_lease_id uuid,
  p_action text,
  p_actor_ref text,
  p_reason text,
  p_bar_ttl_seconds integer default null
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare l public.pentasuite_agent_leases%rowtype;
declare r public.pentarfa_agent_requests%rowtype;
declare v_lockout uuid;
declare v_until timestamptz;
begin
  if p_action not in ('remediation','restricted','suspended','revoked','barred') then raise exception 'invalid enforcement action'; end if;
  select * into l from public.pentasuite_agent_leases where id=p_lease_id for update;
  if not found then raise exception 'lease not found'; end if;
  select * into r from public.pentarfa_agent_requests where id=l.request_id;
  update public.pentasuite_agent_leases
  set state=p_action,
      strike_count=strike_count+1,
      status_reason=p_reason,
      updated_at=now()
  where id=p_lease_id;

  if p_action in ('revoked','barred') then
    v_until := now() + make_interval(secs => coalesce(p_bar_ttl_seconds,r.lockout_seconds));
    if coalesce(p_bar_ttl_seconds,r.lockout_seconds) is null or coalesce(p_bar_ttl_seconds,r.lockout_seconds) <= 0 then
      raise exception 'revocation/bar requires lockout TTL';
    end if;
    insert into public.pentasuite_lockouts(requester_ref,agent_key,lease_id,reason,strike_count,ends_at)
    values (r.requester_ref,r.agent_key,p_lease_id,p_reason,l.strike_count+1,v_until)
    returning id into v_lockout;
    update public.pentasuite_agent_leases
    set state=case when p_action='barred' then 'barred' else 'rollback_pending' end,
        reapply_after=v_until,
        updated_at=now()
    where id=p_lease_id;
  end if;
  perform public.pentasuite_emit_event(l.request_id,p_lease_id,'pentasuite.enforcement.'||p_action,p_actor_ref,jsonb_build_object('reason',p_reason,'lockout_id',v_lockout,'reapply_after',v_until));
  return jsonb_build_object('lease_id',p_lease_id,'action',p_action,'lockout_id',v_lockout,'reapply_after',v_until);
end;
$$;

create or replace function public.pentasuite_file_appeal(
  p_appeal_key text,
  p_request_id uuid,
  p_lease_id uuid,
  p_lockout_id uuid,
  p_appellant_ref text,
  p_appealed_action text,
  p_grounds text,
  p_stay_requested boolean default false
) returns uuid
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare v_id uuid;
begin
  if p_request_id is null and p_lease_id is null and p_lockout_id is null then raise exception 'appeal requires a governed target'; end if;
  insert into public.pentasuite_appeals(appeal_key,request_id,lease_id,lockout_id,appellant_ref,appealed_action,grounds,stay_requested)
  values(p_appeal_key,p_request_id,p_lease_id,p_lockout_id,p_appellant_ref,p_appealed_action,p_grounds,p_stay_requested)
  returning id into v_id;
  perform public.pentasuite_emit_event(p_request_id,p_lease_id,'pentasuite.appeal.filed',p_appellant_ref,
    jsonb_build_object('appeal_id',v_id,'appeal_key',p_appeal_key,'governance_layer','ThriveAlumni - The Governmental Layer','primary_body','Membership and Ethics Committee'));
  return v_id;
end;
$$;

create or replace function public.pentasuite_decide_appeal(
  p_appeal_id uuid,
  p_state text,
  p_actor_ref text,
  p_decision jsonb default '{}'::jsonb,
  p_stay_granted boolean default false
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare a public.pentasuite_appeals%rowtype;
begin
  if p_state not in ('denied','remanded','modified','upheld','board_escalation') then raise exception 'invalid appeal decision state'; end if;
  select * into a from public.pentasuite_appeals where id=p_appeal_id for update;
  if not found then raise exception 'appeal not found'; end if;
  update public.pentasuite_appeals set state=p_state,stay_granted=p_stay_granted,decision=coalesce(p_decision,'{}'::jsonb),decided_by=p_actor_ref,decided_at=now(),updated_at=now() where id=p_appeal_id;
  perform public.pentasuite_emit_event(a.request_id,a.lease_id,'pentasuite.appeal.'||p_state,p_actor_ref,jsonb_build_object('appeal_id',p_appeal_id,'stay_granted',p_stay_granted,'decision',p_decision));
  return jsonb_build_object('appeal_id',p_appeal_id,'state',p_state,'stay_granted',p_stay_granted);
end;
$$;

create or replace function public.pentasuite_schedule_rollback(p_lease_id uuid,p_reason text,p_actor_ref text default 'pentasuite-sentinel')
returns uuid
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare l public.pentasuite_agent_leases%rowtype;
declare b public.pentasuite_agent_blueprints%rowtype;
declare v_project uuid;
declare v_build uuid;
begin
  select * into l from public.pentasuite_agent_leases where id=p_lease_id for update;
  if not found then raise exception 'lease not found'; end if;
  if l.rollback_build_request_id is not null then return l.rollback_build_request_id; end if;
  select * into b from public.pentasuite_agent_blueprints where id=l.blueprint_id;
  select id into v_project from public.ct_factory_projects where project_key='crownthrive-os-v2-factory' order by created_at limit 1;
  if v_project is null then return null; end if;
  insert into public.ct_factory_build_requests(
    project_id,request_key,source_type,source_ref,objective,requirements,requested_release_channel,priority,status,governance_class,evidence
  ) values (
    v_project,'pentasuite-rollback-'||p_lease_id::text,'pentasuite_lease','pentasuite-lease:'||p_lease_id::text,
    'Revoke and rollback PentaSuite agent '||l.agent_key||' to its last safe baseline because: '||p_reason,
    jsonb_build_array(jsonb_build_object('type','rollback','lease_id',p_lease_id,'blueprint_id',l.blueprint_id,'contract',l.rollback_contract)),
    'production',1,'queued','D2',jsonb_build_object('pentasuite_lease_id',p_lease_id,'reason',p_reason)
  ) on conflict (request_key) do update set updated_at=now()
  returning id into v_build;
  update public.pentasuite_agent_leases set rollback_build_request_id=v_build,state='rollback_pending',status_reason=p_reason,updated_at=now() where id=p_lease_id;
  perform public.pentasuite_emit_event(l.request_id,p_lease_id,'pentasuite.rollback.scheduled',p_actor_ref,jsonb_build_object('factory_build_request_id',v_build,'reason',p_reason));
  return v_build;
end;
$$;

create or replace function public.pentasuite_tick() returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare rec record;
declare v_activated integer := 0;
declare v_expired integer := 0;
declare v_revoked integer := 0;
declare v_lockouts integer := 0;
declare v_rollbacks integer := 0;
begin
  update public.pentasuite_lockouts set state='expired',updated_at=now() where state='active' and ends_at <= now();
  get diagnostics v_lockouts = row_count;

  for rec in
    select b.id as blueprint_id,b.request_id,b.factory_build_request_id,l.id as lease_id,l.state as lease_state,l.ttl_seconds,r.state as request_state
    from public.pentasuite_agent_blueprints b
    join public.pentasuite_agent_leases l on l.blueprint_id=b.id
    join public.pentarfa_agent_requests r on r.id=b.request_id
    join public.ct_factory_build_requests f on f.id=b.factory_build_request_id
    where b.state='factory_dispatched' and f.status='implemented'
  loop
    update public.pentasuite_agent_blueprints set state='validated',updated_at=now() where id=rec.blueprint_id;
    update public.pentasuite_agent_assets set state='validated',updated_at=now() where blueprint_id=rec.blueprint_id and state in ('planned','generated');
    update public.pentasuite_agent_leases
    set state=case when rec.request_state='conditional_grant' then 'conditional' else 'active' end,
        starts_at=coalesce(starts_at,now()),
        expires_at=coalesce(expires_at,now()+make_interval(secs=>ttl_seconds)),
        last_heartbeat_at=now(),
        updated_at=now()
    where id=rec.lease_id and state in ('staged','conditional');
    perform public.pentasuite_emit_event(rec.request_id,rec.lease_id,'pentasuite.activated','pentasuite-sentinel',jsonb_build_object('factory_build_request_id',rec.factory_build_request_id));
    v_activated := v_activated + 1;
  end loop;

  for rec in
    select l.*,r.requester_ref,r.lockout_seconds
    from public.pentasuite_agent_leases l join public.pentarfa_agent_requests r on r.id=l.request_id
    where l.state in ('active','conditional','remediation','restricted','suspended') and l.expires_at is not null and l.expires_at <= now()
  loop
    update public.pentasuite_agent_leases set state='expired',status_reason='lease_ttl_expired',updated_at=now() where id=rec.id;
    perform public.pentasuite_schedule_rollback(rec.id,'lease_ttl_expired','pentasuite-sentinel');
    v_expired := v_expired + 1;
    v_rollbacks := v_rollbacks + 1;
  end loop;

  for rec in
    select distinct l.id,l.request_id,l.agent_key,l.strike_count,r.requester_ref,r.lockout_seconds
    from public.pentasuite_agent_leases l
    join public.pentarfa_agent_requests r on r.id=l.request_id
    where l.state in ('conditional','remediation','restricted')
      and l.remediation_due_at is not null and l.remediation_due_at <= now()
      and exists (select 1 from public.pentasuite_remediation_items m where m.lease_id=l.id and m.state not in ('verified','waived_by_governance'))
  loop
    perform public.pentasuite_enforce_lease(rec.id,'revoked','pentasuite-sentinel','remediation_ttl_missed',rec.lockout_seconds);
    perform public.pentasuite_schedule_rollback(rec.id,'remediation_ttl_missed','pentasuite-sentinel');
    v_revoked := v_revoked + 1;
    v_rollbacks := v_rollbacks + 1;
  end loop;

  for rec in
    select l.id,l.request_id,l.rollback_build_request_id,f.status
    from public.pentasuite_agent_leases l join public.ct_factory_build_requests f on f.id=l.rollback_build_request_id
    where l.state='rollback_pending' and f.status='implemented'
  loop
    update public.pentasuite_agent_leases set state='rolled_back',updated_at=now() where id=rec.id;
    update public.pentasuite_agent_assets set state='rolled_back',updated_at=now() where blueprint_id=(select blueprint_id from public.pentasuite_agent_leases where id=rec.id) and state in ('validated','active');
    perform public.pentasuite_emit_event(rec.request_id,rec.id,'pentasuite.rollback.completed','pentasuite-sentinel',jsonb_build_object('factory_build_request_id',rec.rollback_build_request_id));
  end loop;

  return jsonb_build_object('at',now(),'activated',v_activated,'expired',v_expired,'revoked_for_missed_remediation',v_revoked,'lockouts_expired',v_lockouts,'rollbacks_scheduled',v_rollbacks);
end;
$$;

do $$
declare j record;
begin
  begin
    for j in select jobid from cron.job where jobname='pentasuite-lifecycle-tick-v1' loop
      perform cron.unschedule(j.jobid);
    end loop;
    perform cron.schedule('pentasuite-lifecycle-tick-v1','* * * * *','select public.pentasuite_tick();');
  exception when undefined_table then
    null;
  end;
end $$;
