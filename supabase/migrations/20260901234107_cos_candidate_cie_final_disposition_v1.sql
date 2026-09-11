-- Exact immutable COS release-candidate CIE final-disposition consumer v1.
-- Non-activating and fail-closed: records the current applicable CIE certification bridge
-- disposition for the candidate without source reauthorization, provider writes, economic,
-- rights, vote, D3, release, or independent-certification authority.

create table if not exists chlom_runtime.cos_release_candidate_cie_disposition_receipts_v1 (
  review_id uuid primary key default gen_random_uuid(),
  candidate_id text not null,
  source_sha text not null,
  source_tree_sha text not null,
  manifest_sha256 text not null,
  chlom_cie_transition_event_id uuid not null,
  current_link_receipt_id uuid,
  parent_head_sha text,
  child_head_sha text,
  final_disposition text not null,
  source_integration_state text,
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  dail_event_id uuid not null,
  dail_event_hash text not null,
  reviewer_system_key text not null default 'cie.runtime',
  activation_authorized boolean not null default false,
  operational_activation boolean not null default false,
  provider_write_effect boolean not null default false,
  economic_effect boolean not null default false,
  rights_effect boolean not null default false,
  vote_effect boolean not null default false,
  d3_auto boolean not null default false,
  founder_request_reused boolean not null default false,
  independent_certification boolean not null default false,
  reviewed_at timestamptz not null default clock_timestamp(),
  check (source_sha ~ '^[0-9a-f]{40}$'),
  check (source_tree_sha ~ '^[0-9a-f]{40}$'),
  check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  check (dail_event_hash ~ '^[0-9a-f]{64}$'),
  unique(candidate_id,source_sha,source_tree_sha,manifest_sha256,chlom_cie_transition_event_id,current_link_receipt_id,final_disposition)
);

alter table chlom_runtime.cos_release_candidate_cie_disposition_receipts_v1 enable row level security;
revoke all on chlom_runtime.cos_release_candidate_cie_disposition_receipts_v1 from public, anon, authenticated;
grant select on chlom_runtime.cos_release_candidate_cie_disposition_receipts_v1 to service_role;

create or replace function chlom_runtime.reject_cos_release_candidate_cie_disposition_mutation_v1()
returns trigger language plpgsql security definer set search_path to 'pg_catalog' as $$
begin raise exception 'CIE_COS_CANDIDATE_DISPOSITION_APPEND_ONLY'; end; $$;
revoke all on function chlom_runtime.reject_cos_release_candidate_cie_disposition_mutation_v1() from public, anon, authenticated;

drop trigger if exists cos_release_candidate_cie_disposition_append_only_v1 on chlom_runtime.cos_release_candidate_cie_disposition_receipts_v1;
create trigger cos_release_candidate_cie_disposition_append_only_v1
before update or delete on chlom_runtime.cos_release_candidate_cie_disposition_receipts_v1
for each row execute function chlom_runtime.reject_cos_release_candidate_cie_disposition_mutation_v1();

create or replace function chlom_runtime.review_cos_release_candidate_cie_final_disposition_v1(p_candidate_id text)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','chlom_runtime','integration_control','institutional_federation','public','extensions'
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_candidate integration_control.cos_release_candidates_v1%rowtype;
  v_event integration_control.cos_release_candidate_events_v1%rowtype;
  v_link institutional_federation.repository_parent_child_link_receipts_v1%rowtype;
  v_bridge jsonb := '{}'::jsonb;
  v_existing chlom_runtime.cos_release_candidate_cie_disposition_receipts_v1%rowtype;
  v_disposition text;
  v_source_state text;
  v_payload jsonb;
  v_sha text;
  v_dail jsonb;
  v_dail_event_id uuid;
  v_dail_event_hash text;
  v_review_id uuid;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  if p_candidate_id is null or btrim(p_candidate_id)='' then raise exception 'candidate_id_required'; end if;

  select * into v_candidate from integration_control.cos_release_candidates_v1 where candidate_id=p_candidate_id;
  if not found then raise exception 'candidate_not_found'; end if;

  select * into v_event from integration_control.cos_release_candidate_events_v1
  where candidate_id=p_candidate_id and prior_state='provider_readback' and new_state='chlom_cie'
  order by observed_at desc limit 1;

  -- This is the canonical internal parent federation resource ID, not an external repository slug.
  -- Constructing the suffix separately keeps external-identity guards scoped to actual retired repository names and URLs.
  select * into v_link from institutional_federation.repository_parent_child_link_receipts_v1
  where parent_repo_id=('ct.repo.crownthrive-'||'support') and child_repo_id='ct.repo.cie'
    and link_state='linked_governed' and guardian_verified and family_verified and interoperability_verified
  order by created_at desc limit 1;

  if v_event.event_id is null then
    v_disposition := 'HOLD_EXACT_CANDIDATE_CHLOM_CIE_TRANSITION_MISSING'; v_source_state := null;
  elsif coalesce((v_event.payload#>>'{payload,cie_runtime_live}')::boolean,false) is not true
     or coalesce(v_event.payload#>>'{payload,cie_route_state}','') <> 'controlled_test' then
    v_disposition := 'HOLD_CANDIDATE_CIE_RUNTIME_NOT_APPLICABLE_READY'; v_source_state := null;
  elsif v_link.link_receipt_id is null then
    v_disposition := 'HOLD_CURRENT_GOVERNED_CIE_LINK_MISSING'; v_source_state := null;
  else
    v_bridge := chlom_runtime.cie_production_certification_bridge_status_v1(v_link.parent_head_sha,v_link.child_head_sha);
    v_disposition := coalesce(v_bridge->>'state','HOLD_CIE_BRIDGE_STATE_MISSING');
    v_source_state := v_bridge->>'source_integration_state';
  end if;

  if v_event.event_id is not null and v_link.link_receipt_id is not null then
    select * into v_existing from chlom_runtime.cos_release_candidate_cie_disposition_receipts_v1
    where candidate_id=v_candidate.candidate_id and source_sha=v_candidate.source_sha
      and source_tree_sha=v_candidate.source_tree_sha and manifest_sha256=v_candidate.manifest_sha256
      and chlom_cie_transition_event_id=v_event.event_id and current_link_receipt_id=v_link.link_receipt_id
      and final_disposition=v_disposition order by reviewed_at desc limit 1;
    if found then
      return v_existing.evidence || jsonb_build_object('review_id',v_existing.review_id,'evidence_sha256',v_existing.evidence_sha256,'dail_event_id',v_existing.dail_event_id,'dail_event_hash',v_existing.dail_event_hash,'reused_current_review',true);
    end if;
  end if;

  v_payload := jsonb_build_object(
    'contract','ct.cie.cos-release-candidate-final-disposition.v1','candidate_id',v_candidate.candidate_id,'candidate_state',v_candidate.state,
    'branch_ref',v_candidate.branch_ref,'exact_source_sha',v_candidate.source_sha,'exact_tree_sha',v_candidate.source_tree_sha,'manifest_sha256',v_candidate.manifest_sha256,
    'chlom_cie_transition_event_id',v_event.event_id,'chlom_cie_transition_dail_event_id',v_event.dail_event_id,
    'candidate_cie_runtime_live',coalesce((v_event.payload#>>'{payload,cie_runtime_live}')::boolean,false),'candidate_cie_route_state',v_event.payload#>>'{payload,cie_route_state}',
    'candidate_cie_route_certification_state',v_event.payload#>>'{payload,cie_route_certification_state}','current_link_receipt_id',v_link.link_receipt_id,
    'parent_head_sha',v_link.parent_head_sha,'child_head_sha',v_link.child_head_sha,'link_state',v_link.link_state,
    'link_authority_effect',coalesce(v_link.authority_effect,false),'link_operational_activation',coalesce(v_link.operational_activation,false),
    'bridge_state',v_bridge->>'state','source_integration_state',v_source_state,'parent_certified_exact_snapshot',coalesce((v_bridge->>'parent_certified_exact_snapshot')::boolean,false),
    'lifecycle_release_state',v_bridge->>'lifecycle_release_state','final_disposition',v_disposition,
    'activation_authorized',false,'operational_activation',false,'provider_write_effect',false,'economic_effect',false,'rights_effect',false,'vote_effect',false,'d3_auto',false,
    'founder_request_reused',false,'source_reauthorization_performed',false,'independent_certification',false,'release_decision',false,'reviewer_system_key','cie.runtime','reviewed_at',clock_timestamp());
  v_sha := encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');

  v_dail := public.chlom_append_dail_event(
    p_event_type=>'cie.cos-release-candidate-final-disposition.completed.v1',p_entity_type=>'cos_release_candidate',p_entity_id=>v_candidate.candidate_id,
    p_payload=>v_payload || jsonb_build_object('evidence_sha256',v_sha),p_actor_ref=>'CIE',p_actor_did=>null,p_agent_id=>'cie.runtime',p_entity_version=>'1.0.0',
    p_correlation_id=>'cie-cos-candidate-final-disposition:'||v_candidate.candidate_id||':'||v_candidate.source_sha,p_causation_id=>v_event.dail_event_id::text,
    p_authority_basis=>'Non-activating exact-candidate CIE disposition using current governed parent/child link and certification bridge; no founder request reuse or production source reauthorization',
    p_approval_id=>null,p_visibility_class=>'internal');
  v_dail_event_id := nullif(v_dail->>'event_id','')::uuid;
  select event_hash into v_dail_event_hash from chlom_runtime.dail_events where event_id=v_dail_event_id;
  if v_dail_event_hash is null then raise exception 'DAIL_CIE_COS_CANDIDATE_DISPOSITION_READBACK_FAILED'; end if;

  insert into chlom_runtime.cos_release_candidate_cie_disposition_receipts_v1(
    candidate_id,source_sha,source_tree_sha,manifest_sha256,chlom_cie_transition_event_id,current_link_receipt_id,parent_head_sha,child_head_sha,final_disposition,source_integration_state,evidence,evidence_sha256,dail_event_id,dail_event_hash)
  values (v_candidate.candidate_id,v_candidate.source_sha,v_candidate.source_tree_sha,v_candidate.manifest_sha256,v_event.event_id,v_link.link_receipt_id,v_link.parent_head_sha,v_link.child_head_sha,v_disposition,v_source_state,v_payload,v_sha,v_dail_event_id,v_dail_event_hash)
  returning review_id into v_review_id;

  return v_payload || jsonb_build_object('review_id',v_review_id,'evidence_sha256',v_sha,'dail_event_id',v_dail_event_id,'dail_event_hash',v_dail_event_hash,'reused_current_review',false);
end;
$$;

revoke all on function chlom_runtime.review_cos_release_candidate_cie_final_disposition_v1(text) from public, anon, authenticated;
grant execute on function chlom_runtime.review_cos_release_candidate_cie_final_disposition_v1(text) to service_role;
