-- ct.cos candidate exact PentaSecurity review v1
-- Bounded D1 read-only decision consumer for immutable COS release candidates.
-- Creates no release/certification/provider/money/rights/D3 authority.

create table if not exists penta_security.cos_release_candidate_review_receipts_v1 (
  review_id uuid primary key default gen_random_uuid(),
  candidate_id text not null,
  source_sha text not null,
  source_tree_sha text not null,
  manifest_sha256 text not null,
  branch_ref text not null,
  security_transition_event_id uuid,
  github_security_receipt_id uuid,
  disposition text not null,
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  dail_event_id uuid not null,
  dail_event_hash text not null,
  reviewer_system_key text not null default 'penta.security',
  provider_write boolean not null default false,
  credential_change boolean not null default false,
  money_movement boolean not null default false,
  rights_disposition boolean not null default false,
  d3_execution boolean not null default false,
  authority_expansion boolean not null default false,
  independent_certification boolean not null default false,
  reviewed_at timestamptz not null default clock_timestamp(),
  check (source_sha ~ '^[0-9a-f]{40}$'),
  check (source_tree_sha ~ '^[0-9a-f]{40}$'),
  check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  check (dail_event_hash ~ '^[0-9a-f]{64}$'),
  unique(candidate_id,source_sha,source_tree_sha,manifest_sha256,security_transition_event_id,github_security_receipt_id,disposition)
);

alter table penta_security.cos_release_candidate_review_receipts_v1 enable row level security;
revoke all on penta_security.cos_release_candidate_review_receipts_v1 from public, anon, authenticated;
grant select on penta_security.cos_release_candidate_review_receipts_v1 to service_role;

create or replace function penta_security.reject_cos_release_candidate_review_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog'
as $$
begin
  raise exception 'PENTASECURITY_COS_CANDIDATE_REVIEW_APPEND_ONLY';
end;
$$;

revoke all on function penta_security.reject_cos_release_candidate_review_mutation_v1() from public, anon, authenticated;

drop trigger if exists cos_release_candidate_review_append_only_v1 on penta_security.cos_release_candidate_review_receipts_v1;
create trigger cos_release_candidate_review_append_only_v1
before update or delete on penta_security.cos_release_candidate_review_receipts_v1
for each row execute function penta_security.reject_cos_release_candidate_review_mutation_v1();

create or replace function penta_security.review_cos_release_candidate_v1(p_candidate_id text)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_security','integration_control','public','chlom_runtime','extensions'
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_candidate integration_control.cos_release_candidates_v1%rowtype;
  v_security_event integration_control.cos_release_candidate_events_v1%rowtype;
  v_gh integration_control.github_security_check_receipts_v2%rowtype;
  v_existing penta_security.cos_release_candidate_review_receipts_v1%rowtype;
  v_disposition text;
  v_payload jsonb;
  v_sha text;
  v_dail jsonb;
  v_dail_event_id uuid;
  v_dail_event_hash text;
  v_review_id uuid;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then
    raise exception 'service_role_required';
  end if;
  if p_candidate_id is null or btrim(p_candidate_id)='' then
    raise exception 'candidate_id_required';
  end if;

  select * into v_candidate
  from integration_control.cos_release_candidates_v1
  where candidate_id=p_candidate_id;
  if not found then
    raise exception 'candidate_not_found';
  end if;

  select * into v_security_event
  from integration_control.cos_release_candidate_events_v1
  where candidate_id=p_candidate_id
    and prior_state='security'
    and new_state='provider_readback'
  order by observed_at desc
  limit 1;

  select * into v_gh
  from integration_control.github_security_check_receipts_v2
  where main_sha=v_candidate.source_sha
    and repository='crownthrive1/CrownThrive-OS'
  order by observed_at desc
  limit 1;

  if v_security_event.event_id is not null and v_gh.receipt_id is not null then
    select * into v_existing
    from penta_security.cos_release_candidate_review_receipts_v1
    where candidate_id=v_candidate.candidate_id
      and source_sha=v_candidate.source_sha
      and source_tree_sha=v_candidate.source_tree_sha
      and manifest_sha256=v_candidate.manifest_sha256
      and security_transition_event_id=v_security_event.event_id
      and github_security_receipt_id=v_gh.receipt_id
      and disposition='PASS'
    order by reviewed_at desc
    limit 1;
    if found then
      return v_existing.evidence || jsonb_build_object(
        'review_id',v_existing.review_id,
        'evidence_sha256',v_existing.evidence_sha256,
        'dail_event_id',v_existing.dail_event_id,
        'dail_event_hash',v_existing.dail_event_hash,
        'reused_current_review',true
      );
    end if;
  end if;

  if v_candidate.source_sha !~ '^[0-9a-f]{40}$'
     or v_candidate.source_tree_sha !~ '^[0-9a-f]{40}$'
     or v_candidate.manifest_sha256 !~ '^[0-9a-f]{64}$' then
    v_disposition := 'HOLD_CANDIDATE_IDENTITY_INVALID';
  elsif v_candidate.state not in ('provider_readback','chlom_cie','governed_docs','certifying','release_decision') then
    v_disposition := 'HOLD_CANDIDATE_NOT_SECURITY_ACCEPTED';
  elsif v_security_event.event_id is null then
    v_disposition := 'HOLD_EXACT_CANDIDATE_SECURITY_TRANSITION_MISSING';
  elsif coalesce(v_security_event.payload#>>'{payload,candidate_source_sha}','') <> v_candidate.source_sha
     or coalesce(v_security_event.payload#>>'{payload,candidate_tree_sha}','') <> v_candidate.source_tree_sha
     or not coalesce((v_security_event.payload#>>'{payload,candidate_tree_exact_match}')::boolean,false) then
    v_disposition := 'HOLD_SECURITY_TRANSITION_SUBJECT_MISMATCH';
  elsif coalesce(v_security_event.payload#>>'{payload,security_policy_job}','') <> 'success'
     or coalesce(v_security_event.payload#>>'{payload,codeql_compatibility_job}','') <> 'success' then
    v_disposition := 'HOLD_SECURITY_GOVERNANCE_JOBS_NOT_PASS';
  elsif v_gh.receipt_id is null then
    v_disposition := 'HOLD_GITHUB_SECURITY_RECEIPT_MISSING';
  elsif v_gh.disposition <> 'CURRENT_MAIN_SECURITY_GREEN'
     or coalesce(v_gh.open_provider_issue_count,-1) <> 0
     or coalesce(v_gh.provider_http_status,0) <> 200 then
    v_disposition := 'HOLD_GITHUB_SECURITY_NOT_GREEN';
  else
    v_disposition := 'PASS';
  end if;

  v_payload := jsonb_build_object(
    'contract','ct.penta.security.cos-release-candidate-review.v1',
    'candidate_id',v_candidate.candidate_id,
    'candidate_state',v_candidate.state,
    'branch_ref',v_candidate.branch_ref,
    'exact_source_sha',v_candidate.source_sha,
    'exact_tree_sha',v_candidate.source_tree_sha,
    'manifest_sha256',v_candidate.manifest_sha256,
    'security_transition_event_id',v_security_event.event_id,
    'security_transition_dail_event_id',v_security_event.dail_event_id,
    'security_subject_head_sha',v_security_event.payload#>>'{payload,security_subject_head_sha}',
    'security_subject_tree_sha',v_security_event.payload#>>'{payload,security_subject_tree_sha}',
    'candidate_tree_exact_match',coalesce((v_security_event.payload#>>'{payload,candidate_tree_exact_match}')::boolean,false),
    'security_policy_job',v_security_event.payload#>>'{payload,security_policy_job}',
    'codeql_compatibility_job',v_security_event.payload#>>'{payload,codeql_compatibility_job}',
    'github_security_receipt_id',v_gh.receipt_id,
    'github_security_disposition',v_gh.disposition,
    'github_open_provider_issue_count',v_gh.open_provider_issue_count,
    'github_provider_http_status',v_gh.provider_http_status,
    'disposition',v_disposition,
    'security_decision',true,
    'independent_certification',false,
    'release_decision',false,
    'provider_write',false,
    'credential_change',false,
    'money_movement',false,
    'rights_disposition',false,
    'd3_execution',false,
    'authority_expansion',false,
    'reviewer_system_key','penta.security',
    'reviewed_at',clock_timestamp()
  );
  v_sha := encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');

  v_dail := public.chlom_append_dail_event(
    p_event_type=>'penta.security.cos-release-candidate-review.completed.v1',
    p_entity_type=>'cos_release_candidate',
    p_entity_id=>v_candidate.candidate_id,
    p_payload=>v_payload || jsonb_build_object('evidence_sha256',v_sha),
    p_actor_ref=>'PentaSecurity',
    p_actor_did=>null,
    p_agent_id=>'penta.security',
    p_entity_version=>'1.0.0',
    p_correlation_id=>'penta-security-cos-candidate:'||v_candidate.candidate_id||':'||v_candidate.source_sha,
    p_causation_id=>null,
    p_authority_basis=>'Bounded D1 exact-candidate security decision using immutable candidate identity, tree-exact Security Governance evidence, and exact-source GitHub security readback; independent certification and CHLOM/CIE authority remain separate',
    p_approval_id=>null,
    p_visibility_class=>'internal'
  );
  v_dail_event_id := nullif(v_dail->>'event_id','')::uuid;
  select event_hash into v_dail_event_hash
  from chlom_runtime.dail_events
  where event_id=v_dail_event_id;
  if v_dail_event_hash is null then
    raise exception 'DAIL_PENTASECURITY_COS_CANDIDATE_REVIEW_READBACK_FAILED';
  end if;

  insert into penta_security.cos_release_candidate_review_receipts_v1(
    candidate_id,source_sha,source_tree_sha,manifest_sha256,branch_ref,
    security_transition_event_id,github_security_receipt_id,disposition,
    evidence,evidence_sha256,dail_event_id,dail_event_hash
  ) values (
    v_candidate.candidate_id,v_candidate.source_sha,v_candidate.source_tree_sha,v_candidate.manifest_sha256,v_candidate.branch_ref,
    v_security_event.event_id,v_gh.receipt_id,v_disposition,
    v_payload,v_sha,v_dail_event_id,v_dail_event_hash
  )
  returning review_id into v_review_id;

  return v_payload || jsonb_build_object(
    'review_id',v_review_id,
    'evidence_sha256',v_sha,
    'dail_event_id',v_dail_event_id,
    'dail_event_hash',v_dail_event_hash,
    'reused_current_review',false
  );
end;
$$;

revoke all on function penta_security.review_cos_release_candidate_v1(text) from public, anon, authenticated;
grant execute on function penta_security.review_cos_release_candidate_v1(text) to service_role;
