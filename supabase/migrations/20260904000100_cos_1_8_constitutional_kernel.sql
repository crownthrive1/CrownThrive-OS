-- COS 1.8 constitutional kernel.
-- This migration creates fail-closed control-plane records. It does not ratify,
-- certify, release, deploy, or grant provider authority.
begin;

create schema if not exists pentagovernance;

create table if not exists pentagovernance.constitutions_v1 (
  constitution_id text not null,
  edition text not null,
  package_sha256 text not null check (package_sha256 ~ '^[0-9a-f]{64}$'),
  manifest_sha256 text not null check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  scope text not null,
  adoption_state text not null,
  constitutional_effectiveness boolean not null default false,
  authority_created boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  primary key (constitution_id, edition),
  check (not constitutional_effectiveness or adoption_state = 'RATIFIED'),
  check (authority_created = false)
);

create table if not exists pentagovernance.ratification_cases_v1 (
  case_id text primary key,
  constitution_id text not null,
  constitution_edition text not null,
  release_id text not null,
  exact_candidate_sha text,
  artifact_digest_sha256 text,
  founder_assent_state text not null,
  institutional_enactment_state text not null,
  constituency_state text not null,
  independent_certification_state text not null,
  human_dail_state text not null,
  machine_dail_state text not null,
  hybrid_dail_state text not null,
  disposition text not null,
  constitutional_effectiveness boolean not null default false,
  production_eligible boolean not null default false,
  authority_created boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  foreign key (constitution_id, constitution_edition)
    references pentagovernance.constitutions_v1(constitution_id, edition),
  check (exact_candidate_sha is null or exact_candidate_sha ~ '^[0-9a-f]{40}$'),
  check (artifact_digest_sha256 is null or artifact_digest_sha256 ~ '^[0-9a-f]{64}$'),
  check (authority_created = false)
);

create table if not exists pentagovernance.constituencies_v1 (
  case_id text not null references pentagovernance.ratification_cases_v1(case_id),
  constituency_id text not null,
  required boolean not null default true,
  approval_fraction numeric(7,6) not null check (approval_fraction > 0 and approval_fraction <= 1),
  quorum_required boolean not null default true,
  human_floor_required boolean not null default true,
  electorate_state text not null,
  eligible_humans integer not null default 0 check (eligible_humans >= 0),
  ballots_cast integer not null default 0 check (ballots_cast >= 0),
  approvals integer not null default 0 check (approvals >= 0),
  rejections integer not null default 0 check (rejections >= 0),
  abstentions integer not null default 0 check (abstentions >= 0),
  ratified boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default clock_timestamp(),
  primary key (case_id, constituency_id),
  check (not ratified or (eligible_humans > 0 and ballots_cast > 0))
);

create table if not exists pentagovernance.ballots_v1 (
  ballot_id uuid primary key default gen_random_uuid(),
  case_id text not null,
  constituency_id text not null,
  human_subject_ref text not null,
  ballot text not null check (ballot in ('approve','reject','abstain')),
  exact_candidate_sha text not null check (exact_candidate_sha ~ '^[0-9a-f]{40}$'),
  artifact_digest_sha256 text not null check (artifact_digest_sha256 ~ '^[0-9a-f]{64}$'),
  identity_evidence_ref text not null,
  eligibility_evidence_ref text not null,
  recusal_state text not null check (recusal_state in ('clear','recused')),
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default clock_timestamp(),
  unique (case_id, constituency_id, human_subject_ref),
  foreign key (case_id, constituency_id)
    references pentagovernance.constituencies_v1(case_id, constituency_id)
);

create table if not exists pentagovernance.survival_contracts_v1 (
  contract_id text primary key,
  penta_id text not null,
  exact_candidate_sha text,
  artifact_digest_sha256 text,
  declaration_state text not null,
  domains jsonb not null,
  certification_state text not null,
  independent_certifier_ref text,
  evidence_bundle_sha256 text,
  production_eligible boolean not null default false,
  authority_created boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  check (jsonb_object_length(domains) = 13),
  check (exact_candidate_sha is null or exact_candidate_sha ~ '^[0-9a-f]{40}$'),
  check (artifact_digest_sha256 is null or artifact_digest_sha256 ~ '^[0-9a-f]{64}$'),
  check (evidence_bundle_sha256 is null or evidence_bundle_sha256 ~ '^[0-9a-f]{64}$'),
  check (not production_eligible or certification_state = 'VERIFIED'),
  check (authority_created = false)
);

create table if not exists pentagovernance.independent_certifications_v1 (
  certification_id uuid primary key default gen_random_uuid(),
  case_id text not null references pentagovernance.ratification_cases_v1(case_id),
  certifier_ref text not null,
  certifier_independence_ref text not null,
  exact_candidate_sha text not null check (exact_candidate_sha ~ '^[0-9a-f]{40}$'),
  artifact_digest_sha256 text not null check (artifact_digest_sha256 ~ '^[0-9a-f]{64}$'),
  evidence_bundle_sha256 text not null check (evidence_bundle_sha256 ~ '^[0-9a-f]{64}$'),
  disposition text not null check (disposition in ('PASS','FAIL','STALE')),
  created_at timestamptz not null default clock_timestamp(),
  unique (case_id, certifier_ref, exact_candidate_sha, artifact_digest_sha256)
);

create or replace function pentagovernance.evaluate_ratification_v1(p_case_id text)
returns jsonb
language plpgsql
stable
as $$
declare
  c pentagovernance.ratification_cases_v1%rowtype;
  required_count integer;
  ratified_count integer;
  human_floor_ok boolean;
  subject_bound boolean;
  independent_ok boolean;
  three_dail_ok boolean;
  effective boolean;
begin
  select * into c from pentagovernance.ratification_cases_v1 where case_id = p_case_id;
  if not found then
    raise exception 'unknown ratification case %', p_case_id;
  end if;

  select count(*) filter (where required),
         count(*) filter (where required and ratified),
         coalesce(bool_and((not required) or (not human_floor_required) or eligible_humans > 0), false)
    into required_count, ratified_count, human_floor_ok
    from pentagovernance.constituencies_v1
   where case_id = p_case_id;

  subject_bound := c.exact_candidate_sha is not null and c.artifact_digest_sha256 is not null;
  select exists (
    select 1 from pentagovernance.independent_certifications_v1 i
     where i.case_id = p_case_id
       and i.exact_candidate_sha = c.exact_candidate_sha
       and i.artifact_digest_sha256 = c.artifact_digest_sha256
       and i.disposition = 'PASS'
  ) into independent_ok;
  three_dail_ok := c.human_dail_state='PASS' and c.machine_dail_state='PASS' and c.hybrid_dail_state='PASS';

  effective := subject_bound
    and required_count > 0
    and ratified_count = required_count
    and human_floor_ok
    and independent_ok
    and three_dail_ok
    and c.founder_assent_state='PASS'
    and c.institutional_enactment_state='PASS';

  return jsonb_build_object(
    'case_id', p_case_id,
    'subject_bound', subject_bound,
    'required_constituencies', required_count,
    'ratified_constituencies', ratified_count,
    'human_floor_satisfied', human_floor_ok,
    'independent_certification', independent_ok,
    'three_dail', three_dail_ok,
    'constitutional_effectiveness', effective,
    'production_eligible', false,
    'authority_created', false
  );
end;
$$;

create or replace function pentagovernance.guard_release_v1(
  p_case_id text,
  p_penta_id text,
  p_exact_candidate_sha text,
  p_artifact_digest_sha256 text,
  p_survival_contract_id text
) returns jsonb
language plpgsql
stable
as $$
declare
  evaluation jsonb;
  survival_ok boolean;
begin
  evaluation := pentagovernance.evaluate_ratification_v1(p_case_id);
  select exists (
    select 1 from pentagovernance.survival_contracts_v1 s
     where s.contract_id=p_survival_contract_id
       and s.penta_id=p_penta_id
       and s.exact_candidate_sha=p_exact_candidate_sha
       and s.artifact_digest_sha256=p_artifact_digest_sha256
       and s.certification_state='VERIFIED'
       and s.production_eligible
  ) into survival_ok;

  return jsonb_build_object(
    'allowed', coalesce((evaluation->>'constitutional_effectiveness')::boolean,false) and survival_ok,
    'ratification', evaluation,
    'survival_verified', survival_ok,
    'reason', case
      when not coalesce((evaluation->>'constitutional_effectiveness')::boolean,false)
        then 'HOLD_CONSTITUTION_NOT_EFFECTIVE'
      when not survival_ok then 'HOLD_PENTAGOVERNANCE_SURVIVAL_NOT_VERIFIED'
      else 'PASS_EXACT_SUBJECT_RELEASE_GUARD'
    end
  );
end;
$$;

insert into pentagovernance.constitutions_v1(
  constitution_id, edition, package_sha256, manifest_sha256, scope,
  adoption_state, constitutional_effectiveness, authority_created, metadata
) values (
  'ct.os.pentagovernance.constitution','1.0.0',
  '9088509ff0da6f5b5590f4151559ba6652092acc479e9e388fb6bcd80a4b2f77',
  'c2a01d877ac54ebf13a56a75583a293fcedc16c45c4e83e580a07e155f86c22e',
  'CROWNTHRIVE_OS_INTERNAL_ONLY','EXACT_EDITION_RATIFICATION_PENDING',false,false,
  jsonb_build_object('release_id','ct.cos.release.1.8.0-rc.1','migration','20260904000100')
) on conflict (constitution_id,edition) do update set
  package_sha256=excluded.package_sha256,
  manifest_sha256=excluded.manifest_sha256,
  scope=excluded.scope,
  updated_at=clock_timestamp();

insert into pentagovernance.ratification_cases_v1(
  case_id, constitution_id, constitution_edition, release_id,
  founder_assent_state, institutional_enactment_state, constituency_state,
  independent_certification_state, human_dail_state, machine_dail_state,
  hybrid_dail_state, disposition, constitutional_effectiveness,
  production_eligible, authority_created, metadata
) values (
  'ct.ratification.pentagovernance-constitution-os-1.0.0.cos-1.8',
  'ct.os.pentagovernance.constitution','1.0.0','ct.cos.release.1.8.0-rc.1',
  'DIRECTIVE_RECEIVED_PENDING_DAIL_BINDING','AUTHORIZED_PENDING_EXACT_SUBJECT',
  'HOLD_LAWFUL_HUMAN_ELECTORATES_REQUIRED','PENDING','PENDING','PENDING','PENDING',
  'INSTITUTIONALLY_ENACTED_PENDING_LAWFUL_HUMAN_ELECTORATES',
  false,false,false,
  jsonb_build_object('selected_from_main_sha','9977723fbce2666d66524815c648566c37c948ce')
) on conflict (case_id) do update set
  disposition=excluded.disposition,
  metadata=pentagovernance.ratification_cases_v1.metadata || excluded.metadata,
  updated_at=clock_timestamp();

insert into pentagovernance.constituencies_v1(
  case_id,constituency_id,required,approval_fraction,quorum_required,
  human_floor_required,electorate_state,eligible_humans,ratified,metadata
)
select
  'ct.ratification.pentagovernance-constitution-os-1.0.0.cos-1.8',
  x.constituency_id,true,0.6667,true,true,
  'ELECTORATE_NOT_RATIFICATION_READY',0,false,
  jsonb_build_object('machine_votes_may_satisfy_human_floor',false)
from (values
  ('penta.constituency.affected'),
  ('penta.constituency.house-of-families'),
  ('penta.constituency.independent-establishments'),
  ('penta.constituency.senate-of-systems'),
  ('penta.constituency.workforce')
) as x(constituency_id)
on conflict (case_id,constituency_id) do nothing;

insert into pentagovernance.survival_contracts_v1(
  contract_id,penta_id,declaration_state,domains,certification_state,
  production_eligible,authority_created,metadata
) values (
  'ct.penta.survival.pentagovernance.cos-1.8.v1',
  'ct.gov.system.a76413df5625c289741a06cb',
  'DECLARED_UNPROVEN',
  jsonb_build_object(
    'persistent_identity',jsonb_build_object('state','PENDING_EXACT_SUBJECT_EXERCISE'),
    'persistent_state',jsonb_build_object('state','PENDING_EXACT_SUBJECT_EXERCISE'),
    'deterministic_functions',jsonb_build_object('state','PENDING_EXACT_SUBJECT_EXERCISE'),
    'queues',jsonb_build_object('state','PENDING_EXACT_SUBJECT_EXERCISE'),
    'leases',jsonb_build_object('state','PENDING_EXACT_SUBJECT_EXERCISE'),
    'recovery',jsonb_build_object('state','PENDING_EXACT_SUBJECT_EXERCISE'),
    'evidence',jsonb_build_object('state','PENDING_EXACT_SUBJECT_EXERCISE'),
    'authority_enforcement',jsonb_build_object('state','PENDING_EXACT_SUBJECT_EXERCISE'),
    'health_check',jsonb_build_object('state','PENDING_EXACT_SUBJECT_EXERCISE'),
    'model_dependency',jsonb_build_object('state','PENDING_EXACT_SUBJECT_EXERCISE'),
    'degraded_without_model',jsonb_build_object('state','PENDING_EXACT_SUBJECT_EXERCISE'),
    'replaceable_model',jsonb_build_object('state','PENDING_EXACT_SUBJECT_EXERCISE'),
    'restart_behavior',jsonb_build_object('state','PENDING_EXACT_SUBJECT_EXERCISE')
  ),
  'NOT_CERTIFIED',false,false,
  jsonb_build_object('release_id','ct.cos.release.1.8.0-rc.1')
) on conflict (contract_id) do nothing;

revoke all on schema pentagovernance from anon, authenticated;
revoke all on all tables in schema pentagovernance from anon, authenticated;
revoke all on all functions in schema pentagovernance from anon, authenticated;

commit;
