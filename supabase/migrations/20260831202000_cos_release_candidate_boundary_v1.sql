-- CrownThrive COS immutable release-candidate boundary v1
-- Additive control-plane schema. Creates no release/provider-write/D3/money/rights/certification authority.

create table if not exists integration_control.cos_release_candidates_v1 (
  candidate_id text primary key,
  release_id text not null,
  branch_ref text not null unique,
  source_sha text not null check (source_sha ~ '^[0-9a-f]{40}$'),
  source_tree_sha text not null check (source_tree_sha ~ '^[0-9a-f]{40}$'),
  manifest_sha256 text not null check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  selected_from_main_sha text not null check (selected_from_main_sha ~ '^[0-9a-f]{40}$'),
  deployment_provider text,
  deployment_id text,
  deployment_source_sha text check (deployment_source_sha is null or deployment_source_sha ~ '^[0-9a-f]{40}$'),
  state text not null default 'frozen' check (state in ('selected','frozen','build_test','security','provider_readback','chlom_cie','governed_docs','certifying','release_ready','released','superseded','invalidated')),
  manifest jsonb not null,
  supersedes_candidate_id text references integration_control.cos_release_candidates_v1(candidate_id),
  invalidation_reason text,
  originator_actor text not null,
  frozen_at timestamptz not null default clock_timestamp(),
  released_at timestamptz,
  invalidated_at timestamptz,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  authority_created boolean not null default false check (authority_created = false),
  d3_authorized boolean not null default false check (d3_authorized = false),
  unique(source_sha, source_tree_sha, manifest_sha256)
);

create table if not exists integration_control.cos_release_candidate_events_v1 (
  event_id uuid primary key default gen_random_uuid(),
  candidate_id text not null references integration_control.cos_release_candidates_v1(candidate_id),
  event_type text not null,
  prior_state text,
  new_state text,
  actor_ref text not null,
  payload jsonb not null default '{}'::jsonb,
  dail_event_id uuid,
  observed_at timestamptz not null default clock_timestamp()
);

create index if not exists cos_release_candidates_v1_release_state_idx
  on integration_control.cos_release_candidates_v1(release_id,state,created_at desc);
create index if not exists cos_release_candidate_events_v1_candidate_idx
  on integration_control.cos_release_candidate_events_v1(candidate_id,observed_at desc);

alter table integration_control.cos_release_candidates_v1 enable row level security;
alter table integration_control.cos_release_candidates_v1 force row level security;
alter table integration_control.cos_release_candidate_events_v1 enable row level security;
alter table integration_control.cos_release_candidate_events_v1 force row level security;

revoke all on integration_control.cos_release_candidates_v1 from public, anon, authenticated;
revoke all on integration_control.cos_release_candidate_events_v1 from public, anon, authenticated;
grant select, insert, update on integration_control.cos_release_candidates_v1 to service_role;
grant select, insert on integration_control.cos_release_candidate_events_v1 to service_role;

create or replace function integration_control.cos_release_candidate_immutable_guard_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'COS release candidates are append/supersede only';
  end if;
  if old.state <> 'selected' then
    if new.candidate_id is distinct from old.candidate_id
       or new.release_id is distinct from old.release_id
       or new.branch_ref is distinct from old.branch_ref
       or new.source_sha is distinct from old.source_sha
       or new.source_tree_sha is distinct from old.source_tree_sha
       or new.manifest_sha256 is distinct from old.manifest_sha256
       or new.selected_from_main_sha is distinct from old.selected_from_main_sha
       or new.manifest is distinct from old.manifest
       or new.originator_actor is distinct from old.originator_actor
       or new.frozen_at is distinct from old.frozen_at then
      raise exception 'Frozen COS release-candidate identity/manifest is immutable';
    end if;
  end if;
  new.updated_at := clock_timestamp();
  return new;
end;
$$;

create or replace function integration_control.cos_release_candidate_event_immutable_guard_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $$
begin
  raise exception 'COS release-candidate events are immutable';
end;
$$;

drop trigger if exists trg_cos_release_candidate_immutable_guard_v1 on integration_control.cos_release_candidates_v1;
create trigger trg_cos_release_candidate_immutable_guard_v1
before update or delete on integration_control.cos_release_candidates_v1
for each row execute function integration_control.cos_release_candidate_immutable_guard_v1();

drop trigger if exists trg_cos_release_candidate_event_immutable_guard_v1 on integration_control.cos_release_candidate_events_v1;
create trigger trg_cos_release_candidate_event_immutable_guard_v1
before update or delete on integration_control.cos_release_candidate_events_v1
for each row execute function integration_control.cos_release_candidate_event_immutable_guard_v1();

create or replace function integration_control.cos_release_candidate_freeze_v1(
  p_candidate_id text,
  p_release_id text,
  p_branch_ref text,
  p_source_sha text,
  p_source_tree_sha text,
  p_manifest_sha256 text,
  p_selected_from_main_sha text,
  p_deployment_provider text,
  p_deployment_id text,
  p_deployment_source_sha text,
  p_manifest jsonb,
  p_originator_actor text
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, integration_control, chlom_runtime
as $$
declare
  v_existing integration_control.cos_release_candidates_v1%rowtype;
  v_dail jsonb;
  v_dail_id uuid;
begin
  if coalesce(btrim(p_candidate_id),'')='' or coalesce(btrim(p_release_id),'')='' or coalesce(btrim(p_branch_ref),'')='' or coalesce(btrim(p_originator_actor),'')='' then
    raise exception 'candidate_id, release_id, branch_ref and originator_actor are required';
  end if;
  if p_source_sha !~ '^[0-9a-f]{40}$' or p_source_tree_sha !~ '^[0-9a-f]{40}$' or p_manifest_sha256 !~ '^[0-9a-f]{64}$' or p_selected_from_main_sha !~ '^[0-9a-f]{40}$' then
    raise exception 'invalid digest format';
  end if;
  if p_deployment_source_sha is not null and p_deployment_source_sha <> p_source_sha then
    raise exception 'deployment source SHA must equal frozen candidate source SHA';
  end if;

  select * into v_existing from integration_control.cos_release_candidates_v1 where candidate_id=p_candidate_id;
  if found then
    if v_existing.source_sha=p_source_sha and v_existing.source_tree_sha=p_source_tree_sha and v_existing.manifest_sha256=p_manifest_sha256 and v_existing.branch_ref=p_branch_ref then
      return jsonb_build_object('ok',true,'state','idempotent','candidate_id',p_candidate_id,'source_sha',p_source_sha,'manifest_sha256',p_manifest_sha256);
    end if;
    raise exception 'candidate_id already exists with different immutable identity';
  end if;

  insert into integration_control.cos_release_candidates_v1(
    candidate_id,release_id,branch_ref,source_sha,source_tree_sha,manifest_sha256,selected_from_main_sha,
    deployment_provider,deployment_id,deployment_source_sha,state,manifest,originator_actor
  ) values (
    p_candidate_id,p_release_id,p_branch_ref,p_source_sha,p_source_tree_sha,p_manifest_sha256,p_selected_from_main_sha,
    p_deployment_provider,p_deployment_id,p_deployment_source_sha,'frozen',p_manifest,p_originator_actor
  );

  v_dail := chlom_runtime.append_dail_event(
    'cos.release_candidate.frozen','cos_release_candidate',p_candidate_id,
    jsonb_build_object('release_id',p_release_id,'branch_ref',p_branch_ref,'source_sha',p_source_sha,'source_tree_sha',p_source_tree_sha,'manifest_sha256',p_manifest_sha256,'deployment_provider',p_deployment_provider,'deployment_id',p_deployment_id,'authority_created',false,'d3_authorized',false),
    p_originator_actor,null,p_originator_actor,'1.0.0',p_candidate_id,null,'ct.cos.release-candidate-boundary.v1',null,'institutional'
  );
  v_dail_id := nullif(v_dail->>'event_id','')::uuid;

  insert into integration_control.cos_release_candidate_events_v1(candidate_id,event_type,new_state,actor_ref,payload,dail_event_id)
  values(p_candidate_id,'frozen','frozen',p_originator_actor,jsonb_build_object('manifest_sha256',p_manifest_sha256,'source_sha',p_source_sha),v_dail_id);

  return jsonb_build_object('ok',true,'state','frozen','candidate_id',p_candidate_id,'source_sha',p_source_sha,'manifest_sha256',p_manifest_sha256,'dail_event_id',v_dail_id);
end;
$$;

create or replace function integration_control.cos_release_candidate_transition_v1(
  p_candidate_id text,
  p_expected_state text,
  p_new_state text,
  p_actor_ref text,
  p_reason text,
  p_payload jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, integration_control, chlom_runtime
as $$
declare
  v_row integration_control.cos_release_candidates_v1%rowtype;
  v_dail jsonb;
  v_dail_id uuid;
begin
  select * into v_row from integration_control.cos_release_candidates_v1 where candidate_id=p_candidate_id for update;
  if not found then raise exception 'unknown candidate_id'; end if;
  if v_row.state <> p_expected_state then raise exception 'candidate CAS mismatch: expected %, found %',p_expected_state,v_row.state; end if;
  if p_new_state not in ('build_test','security','provider_readback','chlom_cie','governed_docs','certifying','release_ready','released','superseded','invalidated') then
    raise exception 'unsupported candidate transition';
  end if;

  update integration_control.cos_release_candidates_v1
     set state=p_new_state,
         released_at=case when p_new_state='released' then clock_timestamp() else released_at end,
         invalidated_at=case when p_new_state='invalidated' then clock_timestamp() else invalidated_at end,
         invalidation_reason=case when p_new_state='invalidated' then p_reason else invalidation_reason end
   where candidate_id=p_candidate_id;

  v_dail := chlom_runtime.append_dail_event(
    'cos.release_candidate.'||p_new_state,'cos_release_candidate',p_candidate_id,
    jsonb_build_object('prior_state',p_expected_state,'new_state',p_new_state,'reason',p_reason,'payload',coalesce(p_payload,'{}'::jsonb),'source_sha',v_row.source_sha,'manifest_sha256',v_row.manifest_sha256,'authority_created',false,'d3_authorized',false),
    p_actor_ref,null,p_actor_ref,'1.0.0',p_candidate_id,null,'ct.cos.release-candidate-boundary.v1',null,'institutional'
  );
  v_dail_id := nullif(v_dail->>'event_id','')::uuid;

  insert into integration_control.cos_release_candidate_events_v1(candidate_id,event_type,prior_state,new_state,actor_ref,payload,dail_event_id)
  values(p_candidate_id,'transition',p_expected_state,p_new_state,p_actor_ref,jsonb_build_object('reason',p_reason,'payload',coalesce(p_payload,'{}'::jsonb)),v_dail_id);

  return jsonb_build_object('ok',true,'candidate_id',p_candidate_id,'prior_state',p_expected_state,'state',p_new_state,'dail_event_id',v_dail_id);
end;
$$;

create or replace function integration_control.cos_release_candidate_status_v1(p_candidate_id text default null)
returns jsonb
language sql
security definer
set search_path = pg_catalog, integration_control
as $$
  select jsonb_build_object(
    'contract','ct.cos.release-candidate-boundary.v1',
    'candidate',(
      select to_jsonb(c) from integration_control.cos_release_candidates_v1 c
      where p_candidate_id is null or c.candidate_id=p_candidate_id
      order by c.created_at desc limit 1
    ),
    'events',coalesce((
      select jsonb_agg(to_jsonb(e) order by e.observed_at desc)
      from (select * from integration_control.cos_release_candidate_events_v1 e
            where p_candidate_id is null or e.candidate_id=p_candidate_id
            order by e.observed_at desc limit 20) e
    ),'[]'::jsonb),
    'authority_created',false,
    'd3_human_reserved',true,
    'observed_at',clock_timestamp()
  );
$$;

revoke all on function integration_control.cos_release_candidate_freeze_v1(text,text,text,text,text,text,text,text,text,text,jsonb,text) from public, anon, authenticated;
revoke all on function integration_control.cos_release_candidate_transition_v1(text,text,text,text,text,jsonb) from public, anon, authenticated;
revoke all on function integration_control.cos_release_candidate_status_v1(text) from public, anon, authenticated;
grant execute on function integration_control.cos_release_candidate_freeze_v1(text,text,text,text,text,text,text,text,text,text,jsonb,text) to service_role;
grant execute on function integration_control.cos_release_candidate_transition_v1(text,text,text,text,text,jsonb) to service_role;
grant execute on function integration_control.cos_release_candidate_status_v1(text) to service_role;

comment on table integration_control.cos_release_candidates_v1 is 'Immutable COS V1 release-candidate identity and manifest boundary. Moving main does not invalidate a frozen candidate absent explicit material invalidation.';
comment on function integration_control.cos_release_candidate_freeze_v1(text,text,text,text,text,text,text,text,text,text,jsonb,text) is 'Idempotently freezes an exact COS release candidate and emits a bounded canonical DAIL receipt after expensive evidence preparation is complete.';
