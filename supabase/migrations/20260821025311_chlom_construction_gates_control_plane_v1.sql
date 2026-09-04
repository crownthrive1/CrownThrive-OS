create table if not exists chlom_runtime.construction_gate_definitions (
  gate_id text primary key,
  gate_family text not null,
  canonical_name text not null,
  description text not null,
  required_for_stages text[] not null default '{}',
  scope_types text[] not null default array['module'],
  applies_to_module_classes text[] not null default '{}',
  risk_class text not null check (risk_class in ('D0','D1','D2','D3')),
  d3_human_reserved boolean not null default false,
  specialist_domains text[] not null default '{}',
  auto_evaluable boolean not null default false,
  evaluation_method text,
  sequence_no integer not null,
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists chlom_runtime.construction_tracks (
  track_id uuid primary key default gen_random_uuid(),
  scope_type text not null check (scope_type in ('protocol','module','platform','binding','agent','algorithm','oracle','release','paper')),
  scope_id text not null,
  current_stage text not null,
  target_stage text not null,
  overall_state text not null default 'pending' check (overall_state in ('pending','building','verifying','pass','watch','blocked','hold','superseded')),
  owner_agent_id text,
  parent_track_id uuid references chlom_runtime.construction_tracks(track_id) on delete set null,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(scope_type,scope_id,target_stage)
);

create table if not exists chlom_runtime.construction_gate_results (
  gate_result_id uuid primary key default gen_random_uuid(),
  scope_type text not null check (scope_type in ('protocol','module','platform','binding','agent','algorithm','oracle','release','paper')),
  scope_id text not null,
  target_stage text not null,
  gate_id text not null references chlom_runtime.construction_gate_definitions(gate_id) on delete restrict,
  disposition text not null check (disposition in ('pending','pass','watch','fail','blocked','hold','not_applicable','superseded')),
  score numeric(5,2),
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  evaluator_agent_id text,
  authority_basis text,
  specialist_reviews jsonb not null default '{}'::jsonb,
  human_approval_ref text,
  blocker_reason text,
  supersedes_gate_result_id uuid references chlom_runtime.construction_gate_results(gate_result_id) on delete set null,
  created_at timestamptz not null default now()
);

create index if not exists idx_chlom_gate_results_scope on chlom_runtime.construction_gate_results(scope_type,scope_id,target_stage,gate_id,created_at desc);
create index if not exists idx_chlom_gate_results_disposition on chlom_runtime.construction_gate_results(disposition,created_at desc);
create index if not exists idx_chlom_tracks_state on chlom_runtime.construction_tracks(overall_state,target_stage);

create or replace view chlom_runtime.construction_gate_current as
select distinct on (scope_type,scope_id,target_stage,gate_id)
  gate_result_id, scope_type, scope_id, target_stage, gate_id, disposition, score,
  evidence, evidence_sha256, evaluator_agent_id, authority_basis, specialist_reviews,
  human_approval_ref, blocker_reason, created_at
from chlom_runtime.construction_gate_results
where disposition <> 'superseded'
order by scope_type,scope_id,target_stage,gate_id,created_at desc;

revoke all on chlom_runtime.construction_gate_definitions from public, anon, authenticated;
revoke all on chlom_runtime.construction_tracks from public, anon, authenticated;
revoke all on chlom_runtime.construction_gate_results from public, anon, authenticated;
revoke all on chlom_runtime.construction_gate_current from public, anon, authenticated;