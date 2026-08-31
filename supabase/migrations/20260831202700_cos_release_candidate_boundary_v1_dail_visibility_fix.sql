-- COS release-candidate boundary v1: DAIL visibility-class compatibility repair.
-- The canonical DAIL visibility contract accepts public/internal/confidential/restricted/sealed.

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
    p_originator_actor,null,p_originator_actor,'1.0.0',p_candidate_id,null,'ct.cos.release-candidate-boundary.v1',null,'internal'
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
    p_actor_ref,null,p_actor_ref,'1.0.0',p_candidate_id,null,'ct.cos.release-candidate-boundary.v1',null,'internal'
  );
  v_dail_id := nullif(v_dail->>'event_id','')::uuid;
  insert into integration_control.cos_release_candidate_events_v1(candidate_id,event_type,prior_state,new_state,actor_ref,payload,dail_event_id)
  values(p_candidate_id,'transition',p_expected_state,p_new_state,p_actor_ref,jsonb_build_object('reason',p_reason,'payload',coalesce(p_payload,'{}'::jsonb)),v_dail_id);
  return jsonb_build_object('ok',true,'candidate_id',p_candidate_id,'prior_state',p_expected_state,'state',p_new_state,'dail_event_id',v_dail_id);
end;
$$;
