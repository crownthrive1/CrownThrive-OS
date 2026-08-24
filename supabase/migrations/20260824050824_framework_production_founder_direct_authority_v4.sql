-- Live migration: 20260824050824 / framework_production_founder_direct_authority_v4
-- Adds a separate explicit-human Founder production mode. This is not the deadlock override path.
-- founder_direct requires an exact approved Founder Continuity request, D2/A2 boundaries,
-- surrogate-ineligible state, tested rollback, and a fixed CIE governed-internal scope.

create or replace function chlom_runtime.framework_production_authority_v1(
  p_package_id text,
  p_authority_subject_ref text,
  p_exact_version_ref text,
  p_content_sha256 text,
  p_authority_mode text,
  p_founder_request_id uuid default null
) returns jsonb language plpgsql security definer
set search_path=pg_catalog,chlom_runtime,institutional_federation as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  p institutional_federation.framework_package_registry%rowtype;
  r chlom_runtime.founder_continuity_requests%rowtype;
  f chlom_runtime.founder_override_deadlock_preflights_v1%rowtype;
  v_verify jsonb;
  v_preflight_id uuid;
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if p_content_sha256 !~ '^[0-9a-f]{64}$' or coalesce(p_exact_version_ref,'')='' then raise exception 'exact_snapshot_required'; end if;
  select * into p from institutional_federation.framework_package_registry where package_id=p_package_id;
  if not found then raise exception 'unknown_framework_package'; end if;
  if p.can_vote or not p.d3_human_reserved or p.authority_ceiling not in ('D0','D1','D2') then raise exception 'production_authority_boundary_violation'; end if;

  if p_authority_mode='agent_d_certification' then
    if p.parent_certification_agent<>'ct.relay.agent-d' or p.parent_certification_state<>'certified' then raise exception 'agent_d_certification_required'; end if;
    return jsonb_build_object('valid',true,'mode','agent_d_certification','authority_evidence_ref','ct.relay.agent-d');

  elsif p_authority_mode='founder_override' then
    if p_founder_request_id is null then raise exception 'founder_request_required'; end if;
    select * into r from chlom_runtime.founder_continuity_requests where request_id=p_founder_request_id;
    if not found or r.subject_ref<>p_authority_subject_ref or r.exact_version_ref<>p_exact_version_ref or r.content_sha256<>p_content_sha256 then raise exception 'founder_request_snapshot_mismatch'; end if;
    if r.human_signal_state<>'approved' then raise exception 'explicit_founder_approval_required'; end if;
    begin v_preflight_id:=(r.metadata->>'deadlock_preflight_id')::uuid; exception when others then raise exception 'deadlock_preflight_binding_required'; end;
    select * into f from chlom_runtime.founder_override_deadlock_preflights_v1 where preflight_id=v_preflight_id;
    if not found or f.subject_ref<>p_authority_subject_ref or f.exact_version_ref<>p_exact_version_ref or f.content_sha256<>p_content_sha256 or not f.technical_pass or not f.governance_deadlock or f.founder_confirmation_state<>'confirmed_external' or f.override_executable or not f.no_auto_invoke then raise exception 'confirmed_external_exact_deadlock_preflight_required'; end if;
    v_verify:=chlom_runtime.founder_continuity_verify_human_override_v1(p_founder_request_id,p_exact_version_ref,p_content_sha256);
    if not coalesce((v_verify->>'valid')::boolean,false) then raise exception 'founder_override_verification_failed'; end if;
    return jsonb_build_object('valid',true,'mode','founder_override','founder_request_id',p_founder_request_id,'deadlock_preflight_id',v_preflight_id,'preflight_override_executable',false,'execution_authority_source','founder_continuity_request','authority_evidence_ref',coalesce(r.human_authority_evidence_ref,'human_founder'));

  elsif p_authority_mode='founder_direct' then
    if p_founder_request_id is null then raise exception 'founder_request_required'; end if;
    select * into r from chlom_runtime.founder_continuity_requests where request_id=p_founder_request_id;
    if not found or r.subject_ref<>p_authority_subject_ref or r.exact_version_ref<>p_exact_version_ref or r.content_sha256<>p_content_sha256 then raise exception 'founder_direct_request_snapshot_mismatch'; end if;
    if r.human_signal_state<>'approved' or r.request_state not in ('founder_approved','executing','completed') then raise exception 'explicit_founder_direct_approval_required'; end if;
    if r.authority_class<>'D2' or r.autonomy_class<>'A2' then raise exception 'founder_direct_d2_a2_required'; end if;
    if r.surrogate_state<>'ineligible' then raise exception 'founder_direct_surrogate_must_be_ineligible'; end if;
    if coalesce((r.metadata->>'founder_direct')::boolean,false) is not true or coalesce(r.metadata->>'direct_scope','')<>'CIE_GOVERNED_INTERNAL_PRODUCTION' then raise exception 'founder_direct_scope_contract_required'; end if;
    if r.rollback_test_state<>'pass' or r.rollback_state not in ('ready','required') then raise exception 'founder_direct_rollback_not_ready'; end if;
    v_verify:=chlom_runtime.founder_continuity_verify_human_override_v1(p_founder_request_id,p_exact_version_ref,p_content_sha256);
    if not coalesce((v_verify->>'valid')::boolean,false) then raise exception 'founder_direct_verification_failed'; end if;
    return jsonb_build_object('valid',true,'mode','founder_direct','founder_request_id',p_founder_request_id,'surrogate_used',false,'surrogate_state',r.surrogate_state,'execution_authority_source','explicit_human_founder','authority_evidence_ref',coalesce(r.human_authority_evidence_ref,'human_founder'));
  else
    raise exception 'unsupported_production_authority_mode';
  end if;
end $$;
revoke all on function chlom_runtime.framework_production_authority_v1(text,text,text,text,text,uuid) from public,anon,authenticated;
grant execute on function chlom_runtime.framework_production_authority_v1(text,text,text,text,text,uuid) to service_role;

create or replace function institutional_federation.append_chain_event(p_repo_id text,p_agent_id text,p_event_type text,p_subject_ref text,p_payload jsonb)
returns text language plpgsql security definer
set search_path=institutional_federation,chlom_runtime,extensions,pg_catalog,pg_temp as $$
declare
  v_prev text; v_hash text; v_payload_sha text; v_now timestamptz:=clock_timestamp();
  v_required_capability text; v_binding_repo_id text:=p_repo_id;
  v_binding institutional_federation.repository_agent_bindings%rowtype;
  v_repo institutional_federation.repository_registry%rowtype;
  v_algorithm institutional_federation.algorithm_registry%rowtype;
  v_package institutional_federation.framework_package_registry%rowtype;
  v_link institutional_federation.repository_parent_child_link_receipts_v1%rowtype;
  v_binding_rank integer; v_algorithm_rank integer; v_request_id uuid; v_authority jsonb; v_mode text;
begin
  select * into v_repo from institutional_federation.repository_registry where repo_id=p_repo_id for update;
  if not found then raise exception 'unknown_repository'; end if;
  v_required_capability:=case p_event_type when 'repository_bootstrap' then 'bootstrap' when 'heartbeat' then 'heartbeat' when 'message_publish' then 'publish' when 'message_ack' then 'ack' when 'reference_register' then 'reference' when 'algorithm_invocation' then 'algorithm' when 'parent_child_certification' then 'certify' when 'agent_bindings_sync' then 'sync_agents' else null end;
  if v_required_capability is null then raise exception 'event_type_capability_unmapped'; end if;
  if p_event_type='parent_child_certification' then v_binding_repo_id:=nullif(coalesce(p_payload,'{}'::jsonb)->>'parent_repo_id',''); if v_binding_repo_id is null then raise exception 'parent_repository_required_for_certification_event'; end if; end if;
  perform institutional_federation.assert_agent_binding(v_binding_repo_id,p_agent_id,v_required_capability);

  if p_event_type='algorithm_invocation' then
    select * into v_algorithm from institutional_federation.algorithm_registry where algorithm_id=p_subject_ref;
    if not found then raise exception 'unknown_algorithm'; end if;
    if v_algorithm.implementation_repo_id is distinct from p_repo_id then raise exception 'algorithm_implementation_repository_mismatch'; end if;
    if v_repo.repo_role='framework_child' and (v_repo.governance_state<>'linked_governed' or not v_repo.operationally_enabled) then raise exception 'algorithm_repository_not_parent_certified'; end if;
    if v_algorithm.implementation_package_id is null then raise exception 'algorithm_package_required'; end if;

    select * into v_package from institutional_federation.framework_package_registry where package_id=v_algorithm.implementation_package_id;
    if not found or not v_package.operationally_enabled then raise exception 'algorithm_package_not_operational'; end if;

    if v_package.canonical_host_repo_id is distinct from p_repo_id then
      if v_repo.repo_role<>'framework_child' or v_repo.parent_repo_id is distinct from v_package.canonical_host_repo_id then raise exception 'algorithm_package_host_repository_mismatch'; end if;
      select * into v_link from institutional_federation.repository_parent_child_link_receipts_v1 where parent_repo_id=v_package.canonical_host_repo_id and child_repo_id=p_repo_id order by created_at desc limit 1;
      if not found or v_link.parent_head_sha is distinct from v_repo.last_parent_sha or v_link.child_head_sha is distinct from v_repo.last_child_sha or not v_link.guardian_verified or not v_link.family_verified or not v_link.interoperability_verified or v_link.authority_effect or v_link.operational_activation or v_link.vote_effect or v_link.child_self_activation then raise exception 'algorithm_parent_hosted_package_link_not_verified'; end if;
    end if;

    if v_package.parent_certification_state<>'certified' then
      v_mode:=coalesce(v_package.metadata->>'production_authority_mode','');
      if v_mode not in ('founder_override','founder_direct') then raise exception 'algorithm_package_not_operational'; end if;
      begin v_request_id:=(v_package.metadata->>'production_authority_request_id')::uuid; exception when others then raise exception 'algorithm_package_founder_request_invalid'; end;
      v_authority:=chlom_runtime.framework_production_authority_v1(v_package.package_id,v_package.framework_id,v_package.metadata->>'production_exact_version_ref',v_package.metadata->>'production_content_sha256',v_mode,v_request_id);
      if not coalesce((v_authority->>'valid')::boolean,false) then raise exception 'algorithm_package_founder_authority_invalid'; end if;
    end if;

    if v_algorithm.invocation_state not in ('controlled_test','active','production_limited','production') then raise exception 'algorithm_invocation_state_denied'; end if;
    select * into v_binding from institutional_federation.repository_agent_bindings where repo_id=p_repo_id and agent_id=p_agent_id;
    v_binding_rank:=case v_binding.authority_ceiling when 'D0' then 0 when 'D1' then 1 when 'D2' then 2 when 'D3' then 3 else -1 end;
    v_algorithm_rank:=case v_algorithm.authority_ceiling when 'D0' then 0 when 'D1' then 1 when 'D2' then 2 when 'D3' then 3 else 99 end;
    if v_algorithm_rank>v_binding_rank then raise exception 'algorithm_authority_exceeds_caller_binding'; end if;
  end if;

  select event_hash into v_prev from institutional_federation.chain_events where repo_id=p_repo_id order by created_at desc,event_id desc limit 1;
  v_payload_sha:=encode(extensions.digest(convert_to(coalesce(p_payload,'{}'::jsonb)::text,'UTF8'),'sha256'),'hex');
  v_hash:=encode(extensions.digest(convert_to(coalesce(v_prev,'GENESIS')||'|'||p_repo_id||'|'||p_agent_id||'|'||p_event_type||'|'||coalesce(p_subject_ref,'')||'|'||v_payload_sha||'|'||v_now::text,'UTF8'),'sha256'),'hex');
  insert into institutional_federation.chain_events(repo_id,agent_id,event_type,subject_ref,payload,payload_sha256,previous_event_hash,event_hash,created_at) values(p_repo_id,p_agent_id,p_event_type,p_subject_ref,coalesce(p_payload,'{}'::jsonb),v_payload_sha,v_prev,v_hash,v_now);
  return v_hash;
end $$;
revoke all on function institutional_federation.append_chain_event(text,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function institutional_federation.append_chain_event(text,text,text,text,jsonb) to service_role;
