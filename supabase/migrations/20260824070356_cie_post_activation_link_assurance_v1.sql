-- Canonical migration: 20260824070356 / cie_post_activation_link_assurance_v1
-- Purpose: refresh exact current Support<->CIE parent/child evidence after CIE is already
-- production-active, without rewriting or extending the Founder production authority snapshot.

begin;

create or replace function chlom_runtime.refresh_cie_parent_child_production_assurance_v1(
  p_parent_head text,
  p_child_head text,
  p_link_contract_sha256 text,
  p_source_ref text,
  p_evidence jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, institutional_federation, chlom_runtime, extensions
as $function$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role',true),'');
  v_parent institutional_federation.repository_registry%rowtype;
  v_child institutional_federation.repository_registry%rowtype;
  v_pkg institutional_federation.framework_package_registry%rowtype;
  v_alg institutional_federation.algorithm_registry%rowtype;
  v_prod chlom_runtime.framework_production_receipts_v1%rowtype;
  v_po institutional_federation.repository_external_observations_v1%rowtype;
  v_co institutional_federation.repository_external_observations_v1%rowtype;
  v_guard institutional_federation.repository_child_guardian_bindings_v1%rowtype;
  v_family_parent boolean := false;
  v_family_guardian boolean := false;
  v_interop boolean := false;
  v_arch text;
  v_receipt uuid;
  v_dail jsonb;
  v_activation_parent text;
  v_activation_child text;
  v_activation_request text;
begin
  if session_user <> 'postgres' and v_role <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_parent_head !~ '^[0-9a-f]{40}$' or p_child_head !~ '^[0-9a-f]{40}$' then
    raise exception 'exact_git_sha_required';
  end if;
  if p_link_contract_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception 'link_contract_sha256_required';
  end if;
  if coalesce(trim(p_source_ref),'')='' or jsonb_typeof(coalesce(p_evidence,'{}'::jsonb)) <> 'object' then
    raise exception 'source_and_evidence_required';
  end if;

  select * into v_parent from institutional_federation.repository_registry
  where repo_id='ct.repo.crownthrive-support';
  select * into v_child from institutional_federation.repository_registry
  where repo_id='ct.repo.cie';
  select * into v_pkg from institutional_federation.framework_package_registry
  where package_id='ct.framework-package.cie';
  select * into v_alg from institutional_federation.algorithm_registry
  where algorithm_id='ct.algorithm.cie.v1';
  select * into v_prod from chlom_runtime.framework_production_receipts_v1
  where package_id='ct.framework-package.cie' and event_type='activation'
  order by created_at desc limit 1;

  if v_parent.repo_id is null or v_child.repo_id is null or v_pkg.package_id is null or v_alg.algorithm_id is null then
    raise exception 'cie_production_registry_records_required';
  end if;
  if v_child.parent_repo_id is distinct from v_parent.repo_id
     or v_child.github_repository_id is distinct from 1341314455
     or not v_child.parent_governance_required
     or not v_child.child_self_activation_prohibited then
    raise exception 'cie_parent_child_registry_boundary_mismatch';
  end if;

  -- Post-activation assurance is legal only when CIE is already bounded production.
  if v_child.governance_state <> 'linked_governed'
     or not v_child.operationally_enabled
     or v_child.can_vote
     or v_pkg.package_state <> 'maintained'
     or not v_pkg.operationally_enabled
     or v_pkg.can_vote
     or not v_pkg.d3_human_reserved
     or v_pkg.public_activation_allowed
     or v_pkg.commercial_state <> 'hold'
     or v_pkg.exact_price_authorized
     or v_pkg.checkout_enabled
     or v_pkg.customer_entitlement_active
     or v_alg.invocation_state <> 'production_limited'
     or v_alg.authority_ceiling <> 'D2'
     or v_alg.public_contract_digest <> 'e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2' then
    raise exception 'cie_bounded_production_state_required';
  end if;

  if v_prod.receipt_id is null
     or v_prod.authority_mode <> 'founder_direct'
     or v_prod.rollback_state <> 'ready'
     or coalesce(v_prod.canary_result->>'verdict','') <> 'PASS'
     or coalesce(v_prod.canary_result->>'score','') = '' then
    raise exception 'valid_founder_direct_production_receipt_required';
  end if;

  v_activation_parent := v_pkg.metadata->>'production_parent_head';
  v_activation_child := v_pkg.metadata->>'production_child_head';
  v_activation_request := v_pkg.metadata->>'production_authority_request_id';
  if v_activation_parent !~ '^[0-9a-f]{40}$'
     or v_activation_child !~ '^[0-9a-f]{40}$'
     or v_activation_child <> p_child_head
     or v_activation_request is distinct from v_prod.founder_request_id::text
     or v_prod.exact_version_ref is distinct from v_pkg.metadata->>'production_exact_version_ref'
     or v_prod.content_sha256 is distinct from v_pkg.metadata->>'production_content_sha256' then
    raise exception 'production_authority_snapshot_integrity_failure';
  end if;

  -- A new parent SHA is assurance evidence only. It must be proven by external GitHub readback
  -- as a descendant of the original activation parent; the original Founder authority is retained.
  if coalesce(p_evidence->>'github_compare_status','') <> 'ahead'
     or coalesce(p_evidence->>'github_compare_base_sha','') <> v_activation_parent
     or coalesce(p_evidence->>'github_compare_head_sha','') <> p_parent_head
     or coalesce((p_evidence->>'github_compare_behind_by')::integer,-1) <> 0
     or coalesce((p_evidence->>'github_compare_ahead_by')::integer,0) < 1 then
    raise exception 'github_descendant_evidence_required';
  end if;

  select * into v_po from institutional_federation.repository_external_observations_v1
  where repo_id='ct.repo.crownthrive-support' order by observed_at desc limit 1;
  select * into v_co from institutional_federation.repository_external_observations_v1
  where repo_id='ct.repo.cie' order by observed_at desc limit 1;
  if v_po.observation_id is null or not v_po.repository_exists or coalesce(v_po.archived,false)
     or v_po.head_sha is distinct from p_parent_head
     or v_po.observed_at < now()-interval '30 minutes'
     or v_co.observation_id is null or not v_co.repository_exists or coalesce(v_co.archived,false)
     or v_co.head_sha is distinct from p_child_head
     or v_co.observed_at < now()-interval '30 minutes' then
    raise exception 'fresh_exact_repository_observations_required';
  end if;

  select * into v_guard from institutional_federation.repository_child_guardian_bindings_v1
  where repo_id='ct.repo.cie' and parent_repo_id='ct.repo.crownthrive-support' and binding_state='active'
  order by updated_at desc limit 1;
  if v_guard.repo_id is null or not v_guard.can_observe or not v_guard.can_nurture or not v_guard.can_open_handoff
     or v_guard.can_merge or v_guard.can_delete or v_guard.can_archive or v_guard.can_change_visibility
     or v_guard.can_self_activate_child then
    raise exception 'guardian_binding_not_fail_closed';
  end if;

  select exists(
    select 1 from institutional_federation.repository_family_relationships_v1
    where family_id='ct.family.repository-child-guardian.v1'
      and source_resource_id='ct.repo.crownthrive-support'
      and target_resource_id='ct.repo.cie'
      and machine_relation='PARENT_OF'
      and relationship_state='active'
      and authority_inference_prohibited
  ) into v_family_parent;
  select exists(
    select 1 from institutional_federation.repository_family_relationships_v1
    where family_id='ct.family.repository-child-guardian.v1'
      and source_resource_id=v_guard.guardian_agent_id
      and target_resource_id='ct.repo.cie'
      and machine_relation='GUARDIAN_OF'
      and relationship_state='active'
      and authority_inference_prohibited
  ) into v_family_guardian;
  if not v_family_parent or not v_family_guardian then
    raise exception 'family_relationship_evidence_missing';
  end if;

  select exists(
    select 1 from chlom_runtime.interop_contracts
    where contract_id='ct.interop.contract.repository-parent-child-link.v1'
      and lifecycle_state in ('controlled_test','active')
      and public_contract_digest=p_link_contract_sha256
  ) into v_interop;
  if not v_interop then raise exception 'interop_parent_child_link_contract_not_registered'; end if;

  select root_sha256 into v_arch from institutional_federation.architecture_snapshots_v1
  order by created_at desc limit 1;

  insert into institutional_federation.repository_parent_child_link_receipts_v1(
    contract_id,parent_repo_id,child_repo_id,parent_head_sha,child_head_sha,child_github_repository_id,
    link_contract_sha256,link_state,guardian_agent_id,guardian_verified,family_verified,
    interoperability_verified,architecture_root_sha256,evidence,source_ref,
    authority_effect,operational_activation,vote_effect,child_self_activation
  ) values (
    'ct.contract.repository-parent-child-technical-link.v1','ct.repo.crownthrive-support','ct.repo.cie',
    p_parent_head,p_child_head,1341314455,p_link_contract_sha256,'linked_governed',v_guard.guardian_agent_id,
    true,true,true,v_arch,
    coalesce(p_evidence,'{}'::jsonb)||jsonb_build_object(
      'assurance_mode','POST_ACTIVATION_DESCENDANT_HEAD',
      'activation_receipt_id',v_prod.receipt_id,
      'activation_parent_head',v_activation_parent,
      'activation_child_head',v_activation_child,
      'production_authority_request_id',v_prod.founder_request_id,
      'production_authority_rewritten',false,
      'operational_activation',false,
      'authority_effect',false,
      'vote_effect',false,
      'D3_auto',false
    ),p_source_ref,false,false,false,false
  )
  on conflict(parent_repo_id,child_repo_id,parent_head_sha,child_head_sha) do nothing
  returning link_receipt_id into v_receipt;
  if v_receipt is null then
    select link_receipt_id into v_receipt
    from institutional_federation.repository_parent_child_link_receipts_v1
    where parent_repo_id='ct.repo.crownthrive-support' and child_repo_id='ct.repo.cie'
      and parent_head_sha=p_parent_head and child_head_sha=p_child_head
    order by created_at desc limit 1;
  end if;

  -- Update only current-head assurance projections. Never rewrite the immutable production authority snapshot.
  update institutional_federation.repository_registry
  set last_parent_sha=p_parent_head,
      metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
        'canonical_main_sha',p_parent_head,
        'post_activation_child_link_state','LINKED_GOVERNED_ASSURANCE_CURRENT',
        'post_activation_child_link_receipt_id',v_receipt,
        'post_activation_child_head_sha',p_child_head,
        'post_activation_link_authority_effect',false,
        'production_authority_snapshot_rewritten',false
      ),updated_at=now()
  where repo_id='ct.repo.crownthrive-support';

  update institutional_federation.repository_registry
  set last_parent_sha=p_parent_head,last_child_sha=p_child_head,
      metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
        'post_activation_link_state','LINKED_GOVERNED_ASSURANCE_CURRENT',
        'post_activation_link_receipt_id',v_receipt,
        'post_activation_parent_head',p_parent_head,
        'post_activation_child_head',p_child_head,
        'technical_link_contract_sha256',p_link_contract_sha256,
        'technical_link_is_not_activation',true,
        'production_authority_snapshot_rewritten',false
      ),updated_at=now()
  where repo_id='ct.repo.cie';

  v_dail:=chlom_runtime.append_dail_event(
    'repository.parent_child.production_assurance_refreshed','repository','ct.repo.cie',
    jsonb_build_object(
      'parent_repo_id','ct.repo.crownthrive-support','parent_head_sha',p_parent_head,
      'child_head_sha',p_child_head,'link_receipt_id',v_receipt,
      'activation_receipt_id',v_prod.receipt_id,'activation_parent_head',v_activation_parent,
      'production_authority_mode',v_prod.authority_mode,'production_authority_rewritten',false,
      'guardian_verified',true,'family_verified',true,'interoperability_verified',true,
      'operational_activation',false,'authority_effect',false,'vote_effect',false,'D3_auto',false
    ),'chlom_runtime.refresh_cie_parent_child_production_assurance_v1',null,v_guard.guardian_agent_id,
    '1.0.0',v_receipt::text,null,p_source_ref,v_prod.receipt_id::text,'restricted'
  );

  return jsonb_build_object(
    'state','LINKED_GOVERNED_POST_ACTIVATION_ASSURANCE',
    'link_receipt_id',v_receipt,'parent_head_sha',p_parent_head,'child_head_sha',p_child_head,
    'activation_receipt_id',v_prod.receipt_id,'activation_parent_head',v_activation_parent,
    'production_authority_mode',v_prod.authority_mode,'production_authority_rewritten',false,
    'operational_activation',false,'authority_effect',false,'vote_effect',false,'D3_auto',false,
    'dail_event_id',v_dail->>'event_id'
  );
end
$function$;

create or replace function chlom_runtime.cie_post_activation_link_assurance_status_v1(
  p_expected_parent_head text,
  p_expected_child_head text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, institutional_federation, chlom_runtime
as $function$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role',true),'');
  v_link institutional_federation.repository_parent_child_link_receipts_v1%rowtype;
  v_repo institutional_federation.repository_registry%rowtype;
  v_pkg institutional_federation.framework_package_registry%rowtype;
  v_alg institutional_federation.algorithm_registry%rowtype;
  v_prod chlom_runtime.framework_production_receipts_v1%rowtype;
  v_state text;
begin
  if session_user <> 'postgres' and v_role <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_expected_parent_head !~ '^[0-9a-f]{40}$' or p_expected_child_head !~ '^[0-9a-f]{40}$' then
    raise exception 'exact_git_sha_required';
  end if;

  select * into v_link from institutional_federation.repository_parent_child_link_receipts_v1
  where child_repo_id='ct.repo.cie' order by created_at desc limit 1;
  select * into v_repo from institutional_federation.repository_registry where repo_id='ct.repo.cie';
  select * into v_pkg from institutional_federation.framework_package_registry where package_id='ct.framework-package.cie';
  select * into v_alg from institutional_federation.algorithm_registry where algorithm_id='ct.algorithm.cie.v1';
  select * into v_prod from chlom_runtime.framework_production_receipts_v1
  where package_id='ct.framework-package.cie' and event_type='activation' order by created_at desc limit 1;

  if v_prod.receipt_id is null or v_prod.authority_mode<>'founder_direct' or v_prod.rollback_state<>'ready' then
    v_state:='HOLD_NO_LIVE_PRODUCTION_RECEIPT';
  elsif v_repo.governance_state<>'linked_governed' or not v_repo.operationally_enabled or v_repo.can_vote
     or v_pkg.package_state<>'maintained' or not v_pkg.operationally_enabled or v_pkg.public_activation_allowed
     or v_pkg.can_vote or not v_pkg.d3_human_reserved or v_alg.invocation_state<>'production_limited' then
    v_state:='HOLD_PRODUCTION_BOUNDARY_DRIFT';
  elsif v_link.link_receipt_id is null or v_link.parent_head_sha<>p_expected_parent_head
     or v_link.child_head_sha<>p_expected_child_head or v_link.link_state<>'linked_governed'
     or not v_link.guardian_verified or not v_link.family_verified or not v_link.interoperability_verified
     or v_link.authority_effect or v_link.operational_activation or v_link.vote_effect or v_link.child_self_activation then
    v_state:='HOLD_CURRENT_LINK_ASSURANCE_STALE';
  else
    v_state:='PRODUCTION_ACTIVE_CURRENT_LINK_ASSURED';
  end if;

  return jsonb_build_object(
    'state',v_state,'expected_parent_head',p_expected_parent_head,'expected_child_head',p_expected_child_head,
    'latest_link_receipt_id',v_link.link_receipt_id,'latest_link_parent_head',v_link.parent_head_sha,
    'latest_link_child_head',v_link.child_head_sha,'production_receipt_id',v_prod.receipt_id,
    'production_authority_mode',v_prod.authority_mode,'production_exact_version_ref',v_prod.exact_version_ref,
    'production_authority_rewritten',false,'operationally_enabled',v_pkg.operationally_enabled,
    'public_activation_allowed',v_pkg.public_activation_allowed,'can_vote',v_pkg.can_vote,'D3_auto',false,
    'authority_effect',false,'provider_write_effect',false,'economic_effect',false,'rights_effect',false
  );
end
$function$;

revoke all on function chlom_runtime.refresh_cie_parent_child_production_assurance_v1(text,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function chlom_runtime.refresh_cie_parent_child_production_assurance_v1(text,text,text,text,jsonb) to service_role;
revoke all on function chlom_runtime.cie_post_activation_link_assurance_status_v1(text,text) from public,anon,authenticated;
grant execute on function chlom_runtime.cie_post_activation_link_assurance_status_v1(text,text) to service_role;

commit;
