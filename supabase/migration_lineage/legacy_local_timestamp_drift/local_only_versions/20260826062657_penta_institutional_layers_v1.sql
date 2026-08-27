-- Source-controlled representation of the already-applied production migration
-- penta_institutional_layers_v1 (production migration version 20260826062657).
-- The DDL is reset-safe and preserves the current fail-closed/public-safe intent.

create extension if not exists pgcrypto;

create table if not exists public.penta_system_registry (
  system_key text primary key,
  canonical_name text not null unique,
  category text not null,
  purpose text not null,
  authority_boundary text not null,
  risk_ceiling text not null check (risk_ceiling in ('D0','D1','D2','D3')),
  maturity text not null check (maturity in ('specified','implemented','certified','production','hold','retired')),
  version text not null default '1.0.0',
  public_exposure boolean not null default true,
  docs_ref text,
  runtime_ref text,
  metadata jsonb not null default '{}'::jsonb,
  last_verified_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.penta_system_aliases (
  alias text primary key,
  system_key text not null references public.penta_system_registry(system_key) on delete cascade,
  alias_class text not null default 'recognized' check (alias_class in ('recognized','historical','superseded','vendor_implementation')),
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists public.penta_mation_workflows (
  workflow_id text not null,
  version integer not null check (version >= 1),
  status text not null default 'specified' check (status in ('specified','active','hold','retired')),
  trigger_type text not null check (trigger_type in ('event','schedule','manual','dependency')),
  risk_class text not null check (risk_class in ('D0','D1','D2','D3')),
  authority_ref text not null,
  owner_ref text not null,
  definition jsonb not null,
  definition_sha256 text,
  schema_version text not null default '1',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (workflow_id, version)
);

create table if not exists public.penta_mation_runs (
  run_id uuid primary key default gen_random_uuid(),
  workflow_id text not null,
  workflow_version integer not null,
  idempotency_key text not null unique,
  state text not null check (state in ('registered','discovered','governance_pending','ready','running','human_gate','verifying','succeeded','governance_blocked','dependency_blocked','retry_wait','compensating','failed','held','cancelled')),
  trigger_context jsonb not null default '{}'::jsonb,
  inputs jsonb not null default '{}'::jsonb,
  outputs jsonb,
  error text,
  evidence_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  updated_at timestamptz not null default now(),
  foreign key (workflow_id, workflow_version) references public.penta_mation_workflows(workflow_id, version)
);

create index if not exists penta_mation_runs_state_idx on public.penta_mation_runs(state, updated_at desc);
create index if not exists penta_mation_runs_workflow_idx on public.penta_mation_runs(workflow_id, workflow_version, created_at desc);

create table if not exists public.penta_hybrid_decisions (
  decision_id text primary key,
  run_id uuid references public.penta_mation_runs(run_id) on delete set null,
  risk_class text not null check (risk_class in ('D0','D1','D2','D3')),
  requested_action text not null,
  machine_recommendation text not null,
  confidence numeric check (confidence is null or (confidence >= 0 and confidence <= 1)),
  required_human_role text not null,
  authority_ref text not null,
  conflict_check text not null check (conflict_check in ('pending','pass','fail')),
  quorum_required integer check (quorum_required is null or quorum_required >= 1),
  participants jsonb not null default '[]'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  disposition text not null check (disposition in ('pending','approved','approved_exact','approved_with_conditions','rejected','modified','recused','hold','expired')),
  override_reason text,
  receipts jsonb not null default '[]'::jsonb,
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.penta_alumni_charters (
  charter_id text primary key,
  body_id text not null unique,
  purpose text not null,
  authority_class text not null check (authority_class in ('advisory','delegated','binding')),
  scope text[] not null default '{}',
  risk_ceiling text not null check (risk_ceiling in ('D0','D1','D2','D3')),
  member_roles text[] not null default '{}',
  eligibility_rules jsonb not null default '[]'::jsonb,
  term_rules text not null,
  quorum integer not null check (quorum >= 1),
  vote_rule text,
  recusal_rules jsonb not null default '[]'::jsonb,
  conflict_rules jsonb not null default '[]'::jsonb,
  revocation_authority text not null,
  state text not null check (state in ('draft','active','suspended','expired','revoked','historical')),
  effective_at timestamptz,
  expires_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.penta_institute_research (
  research_id text not null,
  version integer not null check (version >= 1),
  research_class text not null check (research_class in ('rapid_brief','strategic_study','scenario_set','red_team_review','program_evaluation','research_paper','research_watch')),
  question text not null,
  sponsor_role text not null,
  sources jsonb not null default '[]'::jsonb,
  assumptions jsonb not null default '[]'::jsonb,
  competing_hypotheses jsonb not null default '[]'::jsonb,
  methods jsonb not null default '[]'::jsonb,
  findings jsonb not null default '[]'::jsonb,
  confidence text not null check (confidence in ('low','medium','high')),
  recommendations jsonb not null default '[]'::jsonb,
  known_unknowns jsonb not null default '[]'::jsonb,
  chlom_disposition text not null default 'pending' check (chlom_disposition in ('pending','accepted','rejected','modified','hold','archived')),
  preservation_targets text[] not null default array['PentaDocs','DAIL'],
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (research_id, version)
);

create table if not exists public.penta_signal_observations (
  signal_id text primary key,
  observed_at timestamptz not null,
  source_refs jsonb not null default '[]'::jsonb,
  claim text not null,
  confidence numeric not null check (confidence >= 0 and confidence <= 1),
  corroboration_state text not null check (corroboration_state in ('uncorroborated','partially_corroborated','corroborated','contradicted')),
  risk_class text not null check (risk_class in ('D0','D1','D2','D3')),
  disposition text not null check (disposition in ('observe','escalate','research_candidate','incident_candidate','dismissed','resolved')),
  linked_research_id text,
  evidence_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists penta_signal_open_idx on public.penta_signal_observations(disposition, risk_class, observed_at desc);

create table if not exists public.penta_assure_certifications (
  certification_id text primary key,
  subject_ref text not null,
  standard_ref text not null,
  risk_class text not null check (risk_class in ('D0','D1','D2','D3')),
  evidence_refs jsonb not null default '[]'::jsonb,
  independence_state text not null check (independence_state in ('independent','human_independent','separation_of_duties_satisfied','not_satisfied')),
  checks jsonb not null default '[]'::jsonb,
  disposition text not null check (disposition in ('certified','not_certified','hold','expired','revoked')),
  preserve text[] not null default array['PentaDocs','DAIL'],
  certified_at timestamptz,
  expires_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.penta_system_registry enable row level security;
alter table public.penta_system_aliases enable row level security;
alter table public.penta_mation_workflows enable row level security;
alter table public.penta_mation_runs enable row level security;
alter table public.penta_hybrid_decisions enable row level security;
alter table public.penta_alumni_charters enable row level security;
alter table public.penta_institute_research enable row level security;
alter table public.penta_signal_observations enable row level security;
alter table public.penta_assure_certifications enable row level security;

drop policy if exists penta_system_registry_public_read on public.penta_system_registry;
create policy penta_system_registry_public_read on public.penta_system_registry
  for select to anon, authenticated using (public_exposure = true);

drop policy if exists penta_system_aliases_public_read on public.penta_system_aliases;
create policy penta_system_aliases_public_read on public.penta_system_aliases
  for select to anon, authenticated using (
    exists (
      select 1
      from public.penta_system_registry r
      where r.system_key = penta_system_aliases.system_key
        and r.public_exposure = true
    )
  );

create or replace view public.penta_institutional_systems_public_v1
with (security_invoker = true) as
select system_key, canonical_name, category, purpose, risk_ceiling, maturity, version, docs_ref, last_verified_at
from public.penta_system_registry
where public_exposure = true;

grant select on public.penta_institutional_systems_public_v1 to anon, authenticated;

insert into public.penta_system_registry
(system_key, canonical_name, category, purpose, authority_boundary, risk_ceiling, maturity, version, public_exposure, docs_ref, runtime_ref, metadata)
values
('penta.mation','PentaMation','automation_orchestration','Governed event-driven and scheduled workflow orchestration across jobs, queues, dependencies, retries, compensation and convergence.','Automates already-authorized work; PentaTime owns temporal semantics, PentaRoute owns exact routing, PentaHybrid owns consequential human gates, and CHLOM remains authority.','D3','implemented','1.0.0',true,'docs/phase3/PENTAMATION.md','scripts/pentamation_runtime.py','{"doctrine":"Discover -> Govern -> Execute -> Verify -> Preserve"}'::jsonb),
('penta.hybrid','PentaHybrid','human_ai_integration','Human + AI handoff, review, approval, override, escalation, quorum, separation-of-duties and accountable decision lineage.','Resolves and records human gates but does not manufacture a human role, quorum or authority.','D3','implemented','1.0.0',true,'docs/phase3/PENTAHYBRID.md','scripts/penta_institutional_runtime.py','{}'::jsonb),
('penta.alumni','PentaAlumni','human_stewardship_governance','Machine-addressable ThriveAlumni councils, committees, stewardship, mentorship, succession participation and bounded human governance.','Membership alone creates no binding authority; binding authority requires a CHLOM-recognized charter, role, term, scope, quorum and capability.','D3','implemented','1.0.0',true,'docs/phase3/PENTAALUMNI.md','scripts/penta_institutional_runtime.py','{"public_identity":"ThriveAlumni governance and continuity layer"}'::jsonb),
('penta.institute','PentaInstitute','research_decision_science','CrownThrive institutional think tank for research, foresight, scenario planning, decision science, policy analysis, red-team challenge and evidence synthesis.','Produces evidence and recommendations but never execution authority; no external think-tank affiliation is implied.','D2','implemented','1.0.0',true,'docs/phase3/PENTAINSTITUTE.md','scripts/penta_institutional_runtime.py','{"external_affiliation":"none implied"}'::jsonb),
('penta.signal','PentaSignal','strategic_sensing','Strategic sensing, weak-signal detection, anomaly/early-warning and hypothesis routing across approved internal/external sources.','Signals are observations/hypotheses until corroborated; they do not replace CrownLytics/CrownPulse or verified evidence.','D1','implemented','1.0.0',true,'docs/phase3/PENTA_INSTITUTIONAL_LAYER_MAP.md','scripts/penta_institutional_runtime.py','{}'::jsonb),
('penta.assure','PentaAssure','assurance_certification','Independent evidence sufficiency, test aggregation, policy conformance, release readiness and bounded capability certification.','Certification requires explicit standards, evidence and independence/separation-of-duties; executors do not self-certify consequential work.','D3','implemented','1.0.0',true,'docs/phase3/PENTA_INSTITUTIONAL_LAYER_MAP.md','scripts/penta_institutional_runtime.py','{}'::jsonb),
('penta.federation','PentaFederation','federation_interoperability','Cross-system, cross-repository and cross-provider bindings, trust relationships, events, proofs and federation state.','Federation preserves participant and provider boundaries and does not create universal authority.','D3','implemented','1.0.0',true,'docs/phase3/PENTA_INSTITUTIONAL_LAYER_MAP.md',null,'{}'::jsonb)
on conflict (system_key) do update set
  canonical_name=excluded.canonical_name,
  category=excluded.category,
  purpose=excluded.purpose,
  authority_boundary=excluded.authority_boundary,
  risk_ceiling=excluded.risk_ceiling,
  maturity=excluded.maturity,
  version=excluded.version,
  public_exposure=excluded.public_exposure,
  docs_ref=excluded.docs_ref,
  runtime_ref=excluded.runtime_ref,
  metadata=excluded.metadata,
  last_verified_at=now(),
  updated_at=now();

insert into public.penta_system_aliases(alias, system_key, alias_class, notes)
values
('Penta Federation','penta.federation','historical','Canonical one-word spelling is PentaFederation.'),
('CrownThrive think tank','penta.institute','recognized','Human-readable description of PentaInstitute.'),
('ThriveAlumni governance layer','penta.alumni','recognized','Public CrownThrive governance/continuity layer bound through PentaAlumni.')
on conflict (alias) do update set system_key=excluded.system_key, alias_class=excluded.alias_class, notes=excluded.notes;
