-- Exact immutable COS release-candidate CHLOM technical authority/rights review v1.
-- This contract can only attest that candidate-bound technical evidence shows no new
-- authority or rights mutation. It does not validate legal ownership, licenses,
-- third-party rights, professional conclusions, or create release/certification authority.

create table if not exists chlom_runtime.cos_release_candidate_authority_rights_receipts_v1 (
  review_id uuid primary key default gen_random_uuid(),
  candidate_id text not null,
  source_sha text not null,
  source_tree_sha text not null,
  manifest_sha256 text not null,
  chlom_transition_event_id uuid not null,
  disposition text not null,
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  dail_event_id uuid not null,
  dail_event_hash text not null,
  reviewer_system_key text not null default 'chlom.runtime',
  legal_rights_conclusion boolean not null default false,
  third_party_rights_validated boolean not null default false,
  new_rights_granted boolean not null default false,
  existing_rights_modified boolean not null default false,
  release_authority_created boolean not null default false,
  certification_created boolean not null default false,
  d3_execution boolean not null default false,
  authority_expansion boolean not null default false,
  reviewed_at timestamptz not null default clock_timestamp(),
  check (source_sha ~ '^[0-9a-f]{40}$'),
  check (source_tree_sha ~ '^[0-9a-f]{40}$'),
  check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  check (dail_event_hash ~ '^[0-9a-f]{64}$'),
  unique(candidate_id, source_sha, source_tree_sha, manifest_sha256, chlom_transition_event_id, disposition)
);

alter table chlom_runtime.cos_release_candidate_authority_rights_receipts_v1 enable row level security;
revoke all on chlom_runtime.cos_release_candidate_authority_rights_receipts_v1 from public, anon, authenticated;
grant select on chlom_runtime.cos_release_candidate_authority_rights_receipts_v1 to service_role;

create or replace function chlom_runtime.reject_cos_release_candidate_authority_rights_receipt_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog'
as $$
begin
  raise exception 'CHLOM_COS_CANDIDATE_AUTHORITY_RIGHTS_RECEIPT_APPEND_ONLY';
end;
$$;

revoke all on function chlom_runtime.reject_cos_release_candidate_authority_rights_receipt_mutation_v1() from public, anon, authenticated;

drop trigger if exists cos_release_candidate_authority_rights_receipt_append_only_v1 on chlom_runtime.cos_release_candidate_authority_rights_receipts_v1;
create trigger cos_release_candidate_authority_rights_receipt_append_only_v1
before update or delete on chlom_runtime.cos_release_candidate_authority_rights_receipts_v1
for each row execute function chlom_runtime.reject_cos_release_candidate_authority_rights_receipt_mutation_v1();

create or replace function chlom_runtime.review_cos_release_candidate_authority_rights_v1(p_candidate_id text)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','chlom_runtime','integration_control','public','extensions'
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_candidate integration_control.cos_release_candidates_v1%rowtype;
  v_event integration_control.cos_release_candidate_events_v1%rowtype;
  v_existing chlom_runtime.cos_release_candidate_authority_rights_receipts_v1%rowtype;
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

  select * into v_event
  from integration_control.cos_release_candidate_events_v1
  where candidate_id=p_candidate_id
    and prior_state='provider_readback'
    and new_state='chlom_cie'
  order by observed_at desc
  limit 1;

  if v_event.event_id is not null then
    select * into v_existing
    from chlom_runtime.cos_release_candidate_authority_rights_receipts_v1
    where candidate_id=v_candidate.candidate_id
      and source_sha=v_candidate.source_sha
      and source_tree_sha=v_candidate.source_tree_sha
      and manifest_sha256=v_candidate.manifest_sha256
      and chlom_transition_event_id=v_event.event_id
      and disposition='PASS_TECHNICAL_NO_AUTHORITY_OR_RIGHTS_MUTATION_OBSERVED'
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
  elsif v_candidate.state not in ('chlom_cie','governed_docs','certifying','release_decision') then
    v_disposition := 'HOLD_CANDIDATE_NOT_CHLOM_ACCEPTED';
  elsif v_event.event_id is null then
    v_disposition := 'HOLD_EXACT_CANDIDATE_CHLOM_TRANSITION_MISSING';
  elsif coalesce(v_event.payload#>>'{payload,chlom_operating_state}','') <> 'production_hot'
     or coalesce((v_event.payload#>>'{payload,chlom_hold}')::integer,-1) <> 0
     or coalesce((v_event.payload#>>'{payload,chlom_degraded}')::integer,-1) <> 0 then
    v_disposition := 'HOLD_CHLOM_RUNTIME_NOT_HEALTHY_AT_EXACT_TRANSITION';
  elsif coalesce((v_event.payload#>>'{payload,authority_created}')::boolean,true)
     or coalesce((v_event.payload#>>'{payload,release_authority_created}')::boolean,true)
     or coalesce((v_event.payload#>>'{payload,certification_created}')::boolean,true)
     or coalesce((v_event.payload#>>'{payload,runtime_material_drift}')::boolean,true) then
    v_disposition := 'HOLD_CHLOM_TRANSITION_AUTHORITY_OR_DRIFT';
  elsif coalesce((v_candidate.manifest#>>'{authority,D3_execution}')::boolean,true)
     or coalesce((v_candidate.manifest#>>'{authority,certification_created}')::boolean,true)
     or coalesce((v_candidate.manifest#>>'{authority,release_authority_created}')::boolean,true) then
    v_disposition := 'HOLD_CANDIDATE_MANIFEST_AUTHORITY_EXPANSION';
  else
    v_disposition := 'PASS_TECHNICAL_NO_AUTHORITY_OR_RIGHTS_MUTATION_OBSERVED';
  end if;

  v_payload := jsonb_build_object(
    'contract','ct.chlom.cos-release-candidate-authority-rights-review.v1',
    'candidate_id',v_candidate.candidate_id,
    'candidate_state',v_candidate.state,
    'branch_ref',v_candidate.branch_ref,
    'exact_source_sha',v_candidate.source_sha,
    'exact_tree_sha',v_candidate.source_tree_sha,
    'manifest_sha256',v_candidate.manifest_sha256,
    'chlom_transition_event_id',v_event.event_id,
    'chlom_transition_dail_event_id',v_event.dail_event_id,
    'chlom_operating_state',v_event.payload#>>'{payload,chlom_operating_state}',
    'chlom_hold',coalesce((v_event.payload#>>'{payload,chlom_hold}')::integer,-1),
    'chlom_degraded',coalesce((v_event.payload#>>'{payload,chlom_degraded}')::integer,-1),
    'transition_authority_created',coalesce((v_event.payload#>>'{payload,authority_created}')::boolean,true),
    'transition_release_authority_created',coalesce((v_event.payload#>>'{payload,release_authority_created}')::boolean,true),
    'transition_certification_created',coalesce((v_event.payload#>>'{payload,certification_created}')::boolean,true),
    'runtime_material_drift',coalesce((v_event.payload#>>'{payload,runtime_material_drift}')::boolean,true),
    'manifest_d3_execution',coalesce((v_candidate.manifest#>>'{authority,D3_execution}')::boolean,true),
    'manifest_certification_created',coalesce((v_candidate.manifest#>>'{authority,certification_created}')::boolean,true),
    'manifest_release_authority_created',coalesce((v_candidate.manifest#>>'{authority,release_authority_created}')::boolean,true),
    'disposition',v_disposition,
    'authority_rights_disposition','NO_NEW_AUTHORITY_OR_RIGHTS_MUTATION_OBSERVED_TECHNICAL_ONLY',
    'legal_rights_conclusion',false,
    'third_party_rights_validated',false,
    'new_rights_granted',false,
    'existing_rights_modified',false,
    'release_authority_created',false,
    'certification_created',false,
    'independent_certification',false,
    'd3_execution',false,
    'authority_expansion',false,
    'reviewer_system_key','chlom.runtime',
    'reviewed_at',clock_timestamp()
  );
  v_sha := encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');

  v_dail := public.chlom_append_dail_event(
    p_event_type=>'chlom.cos-release-candidate-authority-rights-review.completed.v1',
    p_entity_type=>'cos_release_candidate',
    p_entity_id=>v_candidate.candidate_id,
    p_payload=>v_payload || jsonb_build_object('evidence_sha256',v_sha),
    p_actor_ref=>'CHLOM',
    p_actor_did=>null,
    p_agent_id=>'chlom.runtime',
    p_entity_version=>'1.0.0',
    p_correlation_id=>'chlom-cos-candidate-authority-rights:'||v_candidate.candidate_id||':'||v_candidate.source_sha,
    p_causation_id=>v_event.dail_event_id::text,
    p_authority_basis=>'Bounded technical exact-candidate CHLOM disposition: verifies candidate evidence does not create or modify authority/rights; expressly does not validate legal ownership, licenses, third-party rights, or create release/certification authority',
    p_approval_id=>null,
    p_visibility_class=>'internal'
  );
  v_dail_event_id := nullif(v_dail->>'event_id','')::uuid;
  select event_hash into v_dail_event_hash
  from chlom_runtime.dail_events
  where event_id=v_dail_event_id;
  if v_dail_event_hash is null then
    raise exception 'DAIL_CHLOM_COS_CANDIDATE_AUTHORITY_RIGHTS_READBACK_FAILED';
  end if;

  insert into chlom_runtime.cos_release_candidate_authority_rights_receipts_v1(
    candidate_id,source_sha,source_tree_sha,manifest_sha256,chlom_transition_event_id,
    disposition,evidence,evidence_sha256,dail_event_id,dail_event_hash
  ) values (
    v_candidate.candidate_id,v_candidate.source_sha,v_candidate.source_tree_sha,v_candidate.manifest_sha256,v_event.event_id,
    v_disposition,v_payload,v_sha,v_dail_event_id,v_dail_event_hash
  ) returning review_id into v_review_id;

  return v_payload || jsonb_build_object(
    'review_id',v_review_id,
    'evidence_sha256',v_sha,
    'dail_event_id',v_dail_event_id,
    'dail_event_hash',v_dail_event_hash,
    'reused_current_review',false
  );
end;
$$;

revoke all on function chlom_runtime.review_cos_release_candidate_authority_rights_v1(text) from public, anon, authenticated;
grant execute on function chlom_runtime.review_cos_release_candidate_authority_rights_v1(text) to service_role;
