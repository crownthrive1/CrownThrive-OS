-- COS V1 release-candidate freeze v2: fail-closed manifest/runtime boundary enforcement.
-- Additive; historical v1 candidates and evidence are not rewritten.

create or replace function integration_control.cos_release_candidate_freeze_v2(
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
  p_originator_actor text,
  p_supersedes_candidate_id text default null
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, integration_control, chlom_runtime, extensions
as $function$
declare
  v_existing integration_control.cos_release_candidates_v1%rowtype;
  v_predecessor integration_control.cos_release_candidates_v1%rowtype;
  v_manifest_validation jsonb;
  v_dependency_status jsonb;
  v_computed_manifest_sha text;
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

  v_manifest_validation := integration_control.cos_release_candidate_manifest_validate_v3(p_manifest);
  if coalesce((v_manifest_validation->>'ok')::boolean,false) is not true then
    raise exception 'candidate manifest v3 validation failed: %', coalesce(v_manifest_validation->>'decision','UNKNOWN');
  end if;

  v_computed_manifest_sha := encode(extensions.digest(convert_to(p_manifest::text,'UTF8'),'sha256'),'hex');
  if v_computed_manifest_sha <> p_manifest_sha256 then
    raise exception 'manifest SHA mismatch: supplied %, computed %', p_manifest_sha256, v_computed_manifest_sha;
  end if;

  if coalesce(p_manifest->>'candidate_id','') <> p_candidate_id
     or coalesce(p_manifest->>'release_id','') <> p_release_id
     or coalesce(p_manifest->>'branch_ref','') <> p_branch_ref
     or coalesce(p_manifest#>>'{source,sha}','') <> p_source_sha
     or coalesce(p_manifest#>>'{source,tree_sha}','') <> p_source_tree_sha
     or coalesce(p_manifest->>'selected_from_main_sha','') <> p_selected_from_main_sha
     or coalesce(p_manifest#>>'{deployment,provider}','') <> coalesce(p_deployment_provider,'')
     or coalesce(p_manifest#>>'{deployment,id}','') <> coalesce(p_deployment_id,'')
     or coalesce(p_manifest#>>'{deployment,source_sha}','') <> coalesce(p_deployment_source_sha,'')
     or coalesce(p_manifest->>'supersedes_candidate_id','') <> coalesce(p_supersedes_candidate_id,'') then
    raise exception 'manifest immutable identity does not match freeze arguments';
  end if;

  if p_supersedes_candidate_id is not null then
    if p_supersedes_candidate_id = p_candidate_id then
      raise exception 'candidate cannot supersede itself';
    end if;
    select * into v_predecessor
      from integration_control.cos_release_candidates_v1
     where candidate_id=p_supersedes_candidate_id;
    if not found then
      raise exception 'superseded candidate does not exist: %', p_supersedes_candidate_id;
    end if;
    if v_predecessor.state <> 'invalidated' then
      raise exception 'superseded candidate must be invalidated; observed %', v_predecessor.state;
    end if;
  end if;

  select * into v_existing
    from integration_control.cos_release_candidates_v1
   where candidate_id=p_candidate_id;
  if found then
    if v_existing.source_sha=p_source_sha
       and v_existing.source_tree_sha=p_source_tree_sha
       and v_existing.manifest_sha256=p_manifest_sha256
       and v_existing.branch_ref=p_branch_ref
       and v_existing.supersedes_candidate_id is not distinct from p_supersedes_candidate_id then
      return jsonb_build_object(
        'ok',true,
        'state','idempotent',
        'candidate_id',p_candidate_id,
        'source_sha',p_source_sha,
        'manifest_sha256',p_manifest_sha256,
        'supersedes_candidate_id',p_supersedes_candidate_id,
        'manifest_contract','ct.cos.release-candidate.manifest.v3'
      );
    end if;
    raise exception 'candidate_id already exists with different immutable identity';
  end if;

  insert into integration_control.cos_release_candidates_v1(
    candidate_id,release_id,branch_ref,source_sha,source_tree_sha,manifest_sha256,selected_from_main_sha,
    deployment_provider,deployment_id,deployment_source_sha,state,manifest,supersedes_candidate_id,originator_actor
  ) values (
    p_candidate_id,p_release_id,p_branch_ref,p_source_sha,p_source_tree_sha,p_manifest_sha256,p_selected_from_main_sha,
    p_deployment_provider,p_deployment_id,p_deployment_source_sha,'frozen',p_manifest,p_supersedes_candidate_id,p_originator_actor
  );

  -- Validate the inserted immutable subject against live explicitly included
  -- dependencies before any DAIL evidence is serialized. A failure raises and
  -- rolls back the row atomically.
  v_dependency_status := integration_control.cos_release_candidate_dependency_status_v2(p_candidate_id);
  if coalesce((v_dependency_status->>'ok')::boolean,false) is not true then
    raise exception 'included runtime dependency validation failed: %', coalesce(v_dependency_status->>'decision','UNKNOWN');
  end if;

  v_dail := chlom_runtime.append_dail_event(
    'cos.release_candidate.frozen.v2','cos_release_candidate',p_candidate_id,
    jsonb_build_object(
      'release_id',p_release_id,
      'branch_ref',p_branch_ref,
      'source_sha',p_source_sha,
      'source_tree_sha',p_source_tree_sha,
      'manifest_sha256',p_manifest_sha256,
      'deployment_provider',p_deployment_provider,
      'deployment_id',p_deployment_id,
      'supersedes_candidate_id',p_supersedes_candidate_id,
      'manifest_contract','ct.cos.release-candidate.manifest.v3',
      'dependency_scope_contract','ct.cos.runtime-dependency-scope.v1',
      'dependency_decision',v_dependency_status->>'decision',
      'authority_created',false,
      'd3_authorized',false
    ),
    p_originator_actor,null,p_originator_actor,'2.0.0',p_candidate_id,null,'ct.cos.release-candidate-boundary.v2',null,'internal'
  );
  v_dail_id := nullif(v_dail->>'event_id','')::uuid;

  insert into integration_control.cos_release_candidate_events_v1(candidate_id,event_type,new_state,actor_ref,payload,dail_event_id)
  values(
    p_candidate_id,'frozen_v2','frozen',p_originator_actor,
    jsonb_build_object(
      'manifest_sha256',p_manifest_sha256,
      'source_sha',p_source_sha,
      'supersedes_candidate_id',p_supersedes_candidate_id,
      'manifest_contract','ct.cos.release-candidate.manifest.v3',
      'dependency_decision',v_dependency_status->>'decision'
    ),v_dail_id
  );

  return jsonb_build_object(
    'ok',true,
    'state','frozen',
    'candidate_id',p_candidate_id,
    'source_sha',p_source_sha,
    'manifest_sha256',p_manifest_sha256,
    'supersedes_candidate_id',p_supersedes_candidate_id,
    'manifest_contract','ct.cos.release-candidate.manifest.v3',
    'dependency_status',v_dependency_status,
    'dail_event_id',v_dail_id
  );
end;
$function$;

comment on function integration_control.cos_release_candidate_freeze_v2(text,text,text,text,text,text,text,text,text,text,jsonb,text,text)
is 'Freezes a COS V1 manifest-v3 candidate only after exact manifest hash/identity, predecessor, and explicitly included runtime dependencies validate. DAIL append occurs only after expensive validation. Creates no D3 authority.';

revoke all on function integration_control.cos_release_candidate_freeze_v2(text,text,text,text,text,text,text,text,text,text,jsonb,text,text) from public;
grant execute on function integration_control.cos_release_candidate_freeze_v2(text,text,text,text,text,text,text,text,text,text,jsonb,text,text) to service_role;
