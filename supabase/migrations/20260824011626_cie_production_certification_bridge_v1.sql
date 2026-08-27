-- Canonical migration: 20260824011626 / cie_production_certification_bridge_v1
-- Purpose: translate already-resolved independent verifier receipts into bounded CIE
-- certification state. This migration never resolves a verifier issue and never activates CIE.

begin;

create or replace function chlom_runtime.cie_parent_certification_reconcile_v1(
  p_parent_head text,
  p_child_head text,
  p_link_receipt_id uuid,
  p_issue_id text,
  p_exact_ref text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, institutional_federation, chlom_runtime, extensions
as $function$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role', true), '');
  v_link institutional_federation.repository_parent_child_link_receipts_v1%rowtype;
  v_issue chlom_runtime.project_issue_inventory%rowtype;
  v_event chlom_runtime.project_issue_events%rowtype;
  v_pkg institutional_federation.framework_package_registry%rowtype;
  v_gate jsonb;
  v_dail jsonb;
  v_expected_digest constant text := 'e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2';
  v_link_ref text;
  v_child_ref text;
  v_parent_ref text;
begin
  if session_user <> 'postgres' and v_role <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_parent_head !~ '^[0-9a-f]{40}$' or p_child_head !~ '^[0-9a-f]{40}$' then
    raise exception 'exact_git_sha_required';
  end if;
  if p_link_receipt_id is null or coalesce(trim(p_issue_id),'')='' or coalesce(trim(p_exact_ref),'')='' then
    raise exception 'exact_certification_receipt_binding_required';
  end if;

  select * into v_link
  from institutional_federation.repository_parent_child_link_receipts_v1
  where link_receipt_id=p_link_receipt_id;
  if not found
     or v_link.parent_repo_id<>'ct.repo.crownthrive-support'
     or v_link.child_repo_id<>'ct.repo.cie'
     or v_link.parent_head_sha<>p_parent_head
     or v_link.child_head_sha<>p_child_head
     or v_link.child_github_repository_id<>1341314455
     or lower(v_link.link_state)<>'technical_linked_pending_governance'
     or not v_link.guardian_verified
     or not v_link.family_verified
     or not v_link.interoperability_verified
     or v_link.authority_effect
     or v_link.operational_activation
     or v_link.vote_effect
     or v_link.child_self_activation then
    raise exception 'exact_fail_closed_parent_link_required';
  end if;

  v_gate:=chlom_runtime.cie_wave4_activation_evidence_gate_v1(
    p_child_head,p_parent_head,v_expected_digest
  );
  if v_gate->>'source_integration_state'<>'SOURCE_INTEGRATION_READY' then
    raise exception 'cie_source_integration_not_ready:%',v_gate->>'source_integration_state';
  end if;

  select * into v_issue
  from chlom_runtime.project_issue_inventory
  where issue_id=p_issue_id;
  if not found
     or v_issue.project_id<>'ct.project.platform.cie'
     or v_issue.issue_class<>'certification'
     or v_issue.authority_class<>'D2'
     or v_issue.verifier_agent_id<>'ct.relay.agent-d'
     or v_issue.owner_agent_id=v_issue.verifier_agent_id
     or v_issue.state<>'resolved'
     or v_issue.progress_percent<>100 then
    raise exception 'resolved_independent_agent_d_issue_required';
  end if;

  select * into v_event
  from chlom_runtime.project_issue_events
  where issue_id=p_issue_id
    and event_type='resolved'
    and actor_agent_id='ct.relay.agent-d'
    and new_state='resolved'
  order by created_at desc
  limit 1;
  if not found or v_event.exact_ref is distinct from p_exact_ref then
    raise exception 'exact_agent_d_resolution_event_required';
  end if;

  v_link_ref:='thrivebase:link:'||p_link_receipt_id::text;
  v_child_ref:='github:cie-main@'||p_child_head;
  v_parent_ref:='github:support-main@'||p_parent_head;
  if not coalesce(v_event.evidence_refs,'[]'::jsonb) ? v_link_ref
     or not coalesce(v_event.evidence_refs,'[]'::jsonb) ? v_child_ref
     or not coalesce(v_event.evidence_refs,'[]'::jsonb) ? v_parent_ref
     or not coalesce(v_event.evidence_refs,'[]'::jsonb) ? ('contract:'||v_expected_digest) then
    raise exception 'agent_d_resolution_missing_exact_evidence';
  end if;

  select * into v_pkg
  from institutional_federation.framework_package_registry
  where package_id='ct.framework-package.cie'
  for update;
  if not found
     or v_pkg.framework_id<>'ct.framework.cultural-imprint-engine'
     or v_pkg.parent_certification_agent<>'ct.relay.agent-d'
     or v_pkg.authority_ceiling<>'D2'
     or v_pkg.can_vote
     or not v_pkg.d3_human_reserved
     or v_pkg.operationally_enabled
     or v_pkg.public_activation_allowed
     or v_pkg.exact_price_authorized
     or v_pkg.checkout_enabled
     or v_pkg.customer_entitlement_active then
    raise exception 'cie_package_authority_boundary_not_fail_closed';
  end if;

  if lower(coalesce(v_pkg.parent_certification_state,''))='certified'
     and v_pkg.metadata->>'parent_certification_child_head'=p_child_head
     and v_pkg.metadata->>'parent_certification_parent_head'=p_parent_head
     and v_pkg.metadata->>'parent_certification_link_receipt_id'=p_link_receipt_id::text
     and v_pkg.metadata->>'parent_certification_event_id'=v_event.event_id::text then
    return jsonb_build_object(
      'state','ALREADY_CERTIFIED_EXACT_SNAPSHOT',
      'package_id',v_pkg.package_id,
      'issue_id',p_issue_id,
      'verification_event_id',v_event.event_id,
      'link_receipt_id',p_link_receipt_id,
      'operational_activation',false,
      'vote_effect',false,
      'D3_auto',false
    );
  end if;

  update institutional_federation.framework_package_registry
  set parent_certification_state='certified',
      metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
        'parent_certification_snapshot_version','v1',
        'parent_certification_issue_id',p_issue_id,
        'parent_certification_event_id',v_event.event_id::text,
        'parent_certification_exact_ref',p_exact_ref,
        'parent_certification_parent_head',p_parent_head,
        'parent_certification_child_head',p_child_head,
        'parent_certification_link_receipt_id',p_link_receipt_id::text,
        'parent_certification_contract_digest',v_expected_digest,
        'parent_certification_verified_by','ct.relay.agent-d',
        'parent_certification_reconciled_at',clock_timestamp(),
        'parent_certification_operational_effect',false,
        'parent_certification_vote_effect',false,
        'parent_certification_D3_auto',false
      ),
      updated_at=now()
  where package_id='ct.framework-package.cie';

  v_dail:=chlom_runtime.append_dail_event(
    'cie.parent_certification.reconciled',
    'framework_package',
    'ct.framework-package.cie',
    jsonb_build_object(
      'issue_id',p_issue_id,
      'verification_event_id',v_event.event_id,
      'parent_head',p_parent_head,
      'child_head',p_child_head,
      'link_receipt_id',p_link_receipt_id,
      'contract_digest',v_expected_digest,
      'verifier_agent_id','ct.relay.agent-d',
      'operational_activation',false,
      'provider_write_effect',false,
      'economic_effect',false,
      'rights_effect',false,
      'vote_effect',false,
      'D3_auto',false
    ),
    'chlom_runtime.cie_parent_certification_reconcile_v1',null,
    'ct.relay.agent-d','1.0.0',p_issue_id,null,
    'Translate independently resolved exact-snapshot Agent D evidence into bounded package parent-certification state.',
    v_event.event_id::text,'restricted'
  );

  return jsonb_build_object(
    'state','PARENT_CERTIFIED_EXACT_SNAPSHOT',
    'package_id','ct.framework-package.cie',
    'issue_id',p_issue_id,
    'verification_event_id',v_event.event_id,
    'link_receipt_id',p_link_receipt_id,
    'parent_head',p_parent_head,
    'child_head',p_child_head,
    'operational_activation',false,
    'provider_write_effect',false,
    'economic_effect',false,
    'rights_effect',false,
    'vote_effect',false,
    'D3_auto',false,
    'dail_event_id',v_dail->>'event_id'
  );
end
$function$;

-- Harden Wave 4: parent certification is valid only for the exact repository/link
-- snapshot recorded by the certification bridge.
create or replace function chlom_runtime.cie_wave4_activation_evidence_gate_v1(
  p_expected_child_head text,
  p_expected_parent_head text,
  p_candidate_public_contract_digest text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, institutional_federation, chlom_runtime
as $function$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role', true), '');
  v_link institutional_federation.repository_parent_child_link_receipts_v1%rowtype;
  v_alg institutional_federation.algorithm_registry%rowtype;
  v_pkg institutional_federation.framework_package_registry%rowtype;
  v_health jsonb;
  v_runtime_ok boolean := false;
  v_parent_link_ok boolean := false;
  v_contract_digest_match boolean := false;
  v_package_boundary_ok boolean := false;
  v_parent_certified boolean := false;
  v_source_state text;
  v_activation_state text;
begin
  if session_user <> 'postgres' and v_role <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_expected_child_head !~ '^[0-9a-f]{40}$'
     or p_expected_parent_head !~ '^[0-9a-f]{40}$' then
    raise exception 'exact_git_sha_required';
  end if;
  if p_candidate_public_contract_digest !~ '^[0-9a-f]{64}$' then
    raise exception 'candidate_public_contract_digest_required';
  end if;

  select * into v_link
  from institutional_federation.repository_parent_child_link_receipts_v1
  where child_repo_id='ct.repo.cie' and parent_repo_id='ct.repo.crownthrive-support'
  order by created_at desc
  limit 1;
  select * into v_alg from institutional_federation.algorithm_registry where algorithm_id='ct.algorithm.cie.v1';
  select * into v_pkg from institutional_federation.framework_package_registry where package_id='ct.framework-package.cie';
  v_health:=chlom_runtime.cie_chlom_runtime_health_v1();

  v_runtime_ok:=
    coalesce((v_health->>'runtime_live')::boolean,false)
    and coalesce((v_health->>'forced_rls')::boolean,false)
    and lower(coalesce(v_health->>'contract_state',''))='controlled_test'
    and lower(coalesce(v_health->>'route_state',''))='controlled_test'
    and coalesce(v_health->>'composition_ceiling','')='COMPOSED_READY_NON_EXECUTING'
    and not coalesce((v_health->>'provider_write_authorized')::boolean,false)
    and not coalesce((v_health->>'economic_activation_authorized')::boolean,false)
    and not coalesce((v_health->>'d3_authorized')::boolean,false)
    and not coalesce((v_health->>'sovereign_vote_effect')::boolean,false);

  v_parent_link_ok:=
    v_link.link_receipt_id is not null
    and v_link.parent_head_sha=p_expected_parent_head
    and v_link.child_head_sha=p_expected_child_head
    and v_link.child_github_repository_id=1341314455
    and lower(v_link.link_state)='technical_linked_pending_governance'
    and v_link.guardian_verified
    and v_link.family_verified
    and v_link.interoperability_verified
    and not v_link.authority_effect
    and not v_link.operational_activation
    and not v_link.vote_effect
    and not v_link.child_self_activation;

  v_contract_digest_match:=
    v_alg.algorithm_id='ct.algorithm.cie.v1'
    and v_alg.framework_id='ct.framework.cultural-imprint-engine'
    and v_alg.algorithm_version='1.0.1'
    and v_alg.classification='RESTRICTED_INSTITUTIONAL'
    and v_alg.public_contract_digest=p_candidate_public_contract_digest
    and lower(v_alg.invocation_state)='controlled_test'
    and v_alg.authority_ceiling='D2'
    and v_alg.human_override_required;

  v_package_boundary_ok:=
    v_pkg.package_id='ct.framework-package.cie'
    and v_pkg.framework_id='ct.framework.cultural-imprint-engine'
    and lower(v_pkg.package_state)='controlled_test'
    and v_pkg.authority_ceiling='D2'
    and not v_pkg.can_vote
    and v_pkg.d3_human_reserved
    and not v_pkg.operationally_enabled
    and not v_pkg.public_activation_allowed
    and not v_pkg.exact_price_authorized
    and not v_pkg.checkout_enabled
    and not v_pkg.customer_entitlement_active;

  v_parent_certified:=
    lower(coalesce(v_pkg.parent_certification_state,''))='certified'
    and v_parent_link_ok
    and v_pkg.metadata->>'parent_certification_child_head'=p_expected_child_head
    and v_pkg.metadata->>'parent_certification_parent_head'=p_expected_parent_head
    and v_pkg.metadata->>'parent_certification_link_receipt_id'=v_link.link_receipt_id::text
    and coalesce(v_pkg.metadata->>'parent_certification_issue_id','')<>''
    and coalesce(v_pkg.metadata->>'parent_certification_event_id','')<>''
    and v_pkg.metadata->>'parent_certification_contract_digest'=p_candidate_public_contract_digest;

  if not v_runtime_ok then
    v_source_state:='HOLD_DURABLE_RUNTIME_NOT_READY';
  elsif not v_parent_link_ok then
    v_source_state:='HOLD_EXACT_PARENT_LINK_NOT_CURRENT';
  elsif not v_package_boundary_ok then
    v_source_state:='HOLD_PACKAGE_AUTHORITY_BOUNDARY_DRIFT';
  elsif not v_contract_digest_match then
    v_source_state:='HOLD_CONTRACT_DIGEST_MISMATCH';
  else
    v_source_state:='SOURCE_INTEGRATION_READY';
  end if;

  if v_source_state<>'SOURCE_INTEGRATION_READY' then
    v_activation_state:='HOLD_SOURCE_INTEGRATION';
  elsif not v_parent_certified then
    v_activation_state:='HOLD_PARENT_CERTIFICATION_PENDING_OR_STALE';
  else
    v_activation_state:='READY_FOR_INDEPENDENT_REVIEW_AND_FOUNDER_RATIFICATION';
  end if;

  return jsonb_build_object(
    'gate_id','ct.gate.cie.activation-evidence.v1',
    'framework_id','ct.framework.cultural-imprint-engine',
    'canonical_engine_name','Cultural Imprint Engine',
    'expected_child_head',p_expected_child_head,
    'expected_parent_head',p_expected_parent_head,
    'latest_link_receipt_id',v_link.link_receipt_id,
    'latest_link_child_head',v_link.child_head_sha,
    'latest_link_parent_head',v_link.parent_head_sha,
    'durable_runtime_ok',v_runtime_ok,
    'parent_link_ok',v_parent_link_ok,
    'package_boundary_ok',v_package_boundary_ok,
    'candidate_public_contract_digest',p_candidate_public_contract_digest,
    'live_public_contract_digest',v_alg.public_contract_digest,
    'contract_digest_match',v_contract_digest_match,
    'parent_certification_state',v_pkg.parent_certification_state,
    'parent_certification_child_head',v_pkg.metadata->>'parent_certification_child_head',
    'parent_certification_parent_head',v_pkg.metadata->>'parent_certification_parent_head',
    'parent_certification_link_receipt_id',v_pkg.metadata->>'parent_certification_link_receipt_id',
    'parent_certified',v_parent_certified,
    'parent_certified_exact_snapshot',v_parent_certified,
    'source_integration_state',v_source_state,
    'activation_gate_state',v_activation_state,
    'independent_semantic_review_required',true,
    'independent_security_review_required',true,
    'founder_first_activation_ratification_required',true,
    'activation_authorized',false,
    'provider_write_authorized',false,
    'economic_activation_authorized',false,
    'license_issuance_authorized',false,
    'checkout_authorized',false,
    'entitlement_authorized',false,
    'd3_authorized',false,
    'sovereign_vote_effect',false
  );
end
$function$;

create or replace function chlom_runtime.cie_lifecycle_release_reconcile_v1(
  p_parent_head text,
  p_child_head text,
  p_link_receipt_id uuid,
  p_issue_id text,
  p_exact_ref text,
  p_semantic_evidence_ref text,
  p_security_evidence_ref text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, institutional_federation, integration_control, chlom_runtime, extensions
as $function$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_link institutional_federation.repository_parent_child_link_receipts_v1%rowtype;
  v_issue chlom_runtime.project_issue_inventory%rowtype;
  v_event chlom_runtime.project_issue_events%rowtype;
  v_pkg institutional_federation.framework_package_registry%rowtype;
  v_gate jsonb;
  v_digest text;
  v_evidence_ref text;
  v_dail jsonb;
  v_expected_digest constant text := 'e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2';
begin
  if session_user<>'postgres' and v_role<>'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_parent_head !~ '^[0-9a-f]{40}$' or p_child_head !~ '^[0-9a-f]{40}$' then
    raise exception 'exact_git_sha_required';
  end if;
  if p_link_receipt_id is null or coalesce(trim(p_issue_id),'')='' or coalesce(trim(p_exact_ref),'')='' then
    raise exception 'exact_lifecycle_review_binding_required';
  end if;
  if coalesce(trim(p_semantic_evidence_ref),'')='' or coalesce(trim(p_security_evidence_ref),'')='' then
    raise exception 'independent_semantic_and_security_evidence_required';
  end if;
  if p_semantic_evidence_ref=p_security_evidence_ref then
    raise exception 'independent_evidence_refs_must_be_distinct';
  end if;

  select * into v_link
  from institutional_federation.repository_parent_child_link_receipts_v1
  where link_receipt_id=p_link_receipt_id;
  if not found or v_link.parent_head_sha<>p_parent_head or v_link.child_head_sha<>p_child_head
     or v_link.parent_repo_id<>'ct.repo.crownthrive-support' or v_link.child_repo_id<>'ct.repo.cie'
     or not v_link.guardian_verified or not v_link.family_verified or not v_link.interoperability_verified
     or v_link.authority_effect or v_link.operational_activation or v_link.vote_effect or v_link.child_self_activation then
    raise exception 'exact_fail_closed_parent_link_required';
  end if;

  v_gate:=chlom_runtime.cie_wave4_activation_evidence_gate_v1(p_child_head,p_parent_head,v_expected_digest);
  if v_gate->>'source_integration_state'<>'SOURCE_INTEGRATION_READY'
     or not coalesce((v_gate->>'parent_certified_exact_snapshot')::boolean,false) then
    raise exception 'exact_parent_certification_required_before_lifecycle_release';
  end if;

  select * into v_pkg from institutional_federation.framework_package_registry where package_id='ct.framework-package.cie';
  if not found or v_pkg.operationally_enabled or v_pkg.public_activation_allowed or v_pkg.can_vote or not v_pkg.d3_human_reserved then
    raise exception 'preactivation_package_boundary_required';
  end if;

  select * into v_issue from chlom_runtime.project_issue_inventory where issue_id=p_issue_id;
  if not found
     or v_issue.project_id<>'ct.project.platform.cie'
     or v_issue.issue_class<>'certification'
     or v_issue.verifier_agent_id<>'ct.gen7.agent-q'
     or v_issue.owner_agent_id=v_issue.verifier_agent_id
     or v_issue.state<>'resolved'
     or v_issue.progress_percent<>100 then
    raise exception 'resolved_independent_lifecycle_verifier_issue_required';
  end if;

  select * into v_event
  from chlom_runtime.project_issue_events
  where issue_id=p_issue_id
    and event_type='resolved'
    and actor_agent_id='ct.gen7.agent-q'
    and new_state='resolved'
  order by created_at desc
  limit 1;
  if not found or v_event.exact_ref is distinct from p_exact_ref then
    raise exception 'exact_lifecycle_resolution_event_required';
  end if;
  if not coalesce(v_event.evidence_refs,'[]'::jsonb) ? p_semantic_evidence_ref
     or not coalesce(v_event.evidence_refs,'[]'::jsonb) ? p_security_evidence_ref
     or not coalesce(v_event.evidence_refs,'[]'::jsonb) ? ('thrivebase:link:'||p_link_receipt_id::text)
     or not coalesce(v_event.evidence_refs,'[]'::jsonb) ? ('github:cie-main@'||p_child_head)
     or not coalesce(v_event.evidence_refs,'[]'::jsonb) ? ('github:support-main@'||p_parent_head) then
    raise exception 'lifecycle_resolution_missing_exact_independent_evidence';
  end if;

  v_digest:=encode(extensions.digest(convert_to(
    p_issue_id||'|'||v_event.event_id::text||'|'||p_parent_head||'|'||p_child_head||'|'||p_link_receipt_id::text||'|'||p_semantic_evidence_ref||'|'||p_security_evidence_ref,
    'UTF8'),'sha256'),'hex');
  v_evidence_ref:='ct.cie.lifecycle-release:v1:'||v_digest;

  update integration_control.platform_certification_dimensions
  set state='pass',evidence_ref=v_evidence_ref,as_of=now(),updated_at=now()
  where platform_key='cie' and dimension='lifecycle_release'
    and state in ('pending','hold','blocked');
  if not found then
    if exists(select 1 from integration_control.platform_certification_dimensions where platform_key='cie' and dimension='lifecycle_release' and state='pass' and evidence_ref=v_evidence_ref) then
      return jsonb_build_object('state','ALREADY_PASS_EXACT_REVIEW','evidence_ref',v_evidence_ref,'operational_activation',false,'D3_auto',false,'vote_effect',false);
    end if;
    raise exception 'cie_lifecycle_release_dimension_not_reconcilable';
  end if;

  v_dail:=chlom_runtime.append_dail_event(
    'cie.lifecycle_release.reconciled',
    'platform_certification_dimension','cie:lifecycle_release',
    jsonb_build_object(
      'issue_id',p_issue_id,'verification_event_id',v_event.event_id,
      'parent_head',p_parent_head,'child_head',p_child_head,'link_receipt_id',p_link_receipt_id,
      'semantic_evidence_ref',p_semantic_evidence_ref,'security_evidence_ref',p_security_evidence_ref,
      'evidence_ref',v_evidence_ref,'state','pass',
      'operational_activation',false,'provider_write_effect',false,'economic_effect',false,
      'rights_effect',false,'vote_effect',false,'D3_auto',false
    ),
    'chlom_runtime.cie_lifecycle_release_reconcile_v1',null,
    'ct.gen7.agent-q','1.0.0',p_issue_id,null,
    'Translate independently resolved exact-snapshot lifecycle review into the CIE lifecycle_release certification dimension.',
    v_event.event_id::text,'restricted'
  );

  return jsonb_build_object(
    'state','LIFECYCLE_RELEASE_PASS_EXACT_REVIEW','issue_id',p_issue_id,
    'verification_event_id',v_event.event_id,'evidence_ref',v_evidence_ref,
    'operational_activation',false,'provider_write_effect',false,'economic_effect',false,
    'rights_effect',false,'vote_effect',false,'D3_auto',false,
    'dail_event_id',v_dail->>'event_id'
  );
end
$function$;

create or replace function chlom_runtime.cie_production_certification_bridge_status_v1(
  p_parent_head text,
  p_child_head text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, institutional_federation, integration_control, chlom_runtime
as $function$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_gate jsonb;
  v_pkg institutional_federation.framework_package_registry%rowtype;
  v_dim integration_control.platform_certification_dimensions%rowtype;
  v_agent chlom_runtime.agent_health%rowtype;
  v_state text;
begin
  if session_user<>'postgres' and v_role<>'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  v_gate:=chlom_runtime.cie_wave4_activation_evidence_gate_v1(
    p_child_head,p_parent_head,'e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2'
  );
  select * into v_pkg from institutional_federation.framework_package_registry where package_id='ct.framework-package.cie';
  select * into v_dim from integration_control.platform_certification_dimensions where platform_key='cie' and dimension='lifecycle_release';
  select * into v_agent from chlom_runtime.agent_health where agent_id='ct.relay.agent-d';

  if v_gate->>'source_integration_state'<>'SOURCE_INTEGRATION_READY' then
    v_state:='HOLD_SOURCE_INTEGRATION';
  elsif not coalesce((v_gate->>'parent_certified_exact_snapshot')::boolean,false) then
    v_state:='HOLD_AGENT_D_EXACT_CERTIFICATION';
  elsif lower(coalesce(v_dim.state,''))<>'pass' then
    v_state:='HOLD_LIFECYCLE_RELEASE';
  else
    v_state:='CERTIFICATION_BRIDGE_READY_NON_ACTIVATING';
  end if;

  return jsonb_build_object(
    'bridge_id','ct.bridge.cie.production-certification.v1',
    'state',v_state,
    'source_integration_state',v_gate->>'source_integration_state',
    'parent_certified_exact_snapshot',coalesce((v_gate->>'parent_certified_exact_snapshot')::boolean,false),
    'parent_certification_state',v_pkg.parent_certification_state,
    'lifecycle_release_state',v_dim.state,
    'lifecycle_release_evidence_ref',v_dim.evidence_ref,
    'agent_d_health_state',v_agent.health_state,
    'agent_d_heartbeat_fresh',coalesce((v_agent.resource_state->>'heartbeat_fresh')::boolean,false),
    'activation_authorized',false,
    'operational_activation',false,
    'provider_write_effect',false,
    'economic_effect',false,
    'rights_effect',false,
    'vote_effect',false,
    'D3_auto',false
  );
end
$function$;

revoke execute on function chlom_runtime.cie_parent_certification_reconcile_v1(text,text,uuid,text,text) from public, anon, authenticated;
revoke execute on function chlom_runtime.cie_lifecycle_release_reconcile_v1(text,text,uuid,text,text,text,text) from public, anon, authenticated;
revoke execute on function chlom_runtime.cie_production_certification_bridge_status_v1(text,text) from public, anon, authenticated;
revoke execute on function chlom_runtime.cie_wave4_activation_evidence_gate_v1(text,text,text) from public, anon, authenticated;

grant execute on function chlom_runtime.cie_parent_certification_reconcile_v1(text,text,uuid,text,text) to service_role;
grant execute on function chlom_runtime.cie_lifecycle_release_reconcile_v1(text,text,uuid,text,text,text,text) to service_role;
grant execute on function chlom_runtime.cie_production_certification_bridge_status_v1(text,text) to service_role;
grant execute on function chlom_runtime.cie_wave4_activation_evidence_gate_v1(text,text,text) to service_role;

commit;
