-- Live migration: 20260824044508 / append_chain_event_production_authority_v2
-- Extends algorithm chain evidence to recognize exact verified Founder production authority
-- and the production_limited invocation state. Superseded/strengthened by the v3 migration below.

create or replace function institutional_federation.append_chain_event(p_repo_id text, p_agent_id text, p_event_type text, p_subject_ref text, p_payload jsonb)
returns text
language plpgsql
security definer
set search_path to 'institutional_federation','chlom_runtime','extensions','pg_catalog','pg_temp'
as $$
declare
  v_prev text; v_hash text; v_payload_sha text; v_now timestamptz:=clock_timestamp();
  v_required_capability text; v_binding_repo_id text:=p_repo_id;
  v_binding institutional_federation.repository_agent_bindings%rowtype;
  v_repo institutional_federation.repository_registry%rowtype;
  v_algorithm institutional_federation.algorithm_registry%rowtype;
  v_package institutional_federation.framework_package_registry%rowtype;
  v_binding_rank integer; v_algorithm_rank integer; v_request_id uuid; v_authority jsonb;
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
    select * into v_package from institutional_federation.framework_package_registry where package_id=v_algorithm.implementation_package_id and canonical_host_repo_id=p_repo_id;
    if not found or not v_package.operationally_enabled then raise exception 'algorithm_package_not_operational'; end if;
    if v_package.parent_certification_state<>'certified' then
      if coalesce(v_package.metadata->>'production_authority_mode','')<>'founder_override' then raise exception 'algorithm_package_not_operational'; end if;
      begin v_request_id:=(v_package.metadata->>'production_authority_request_id')::uuid; exception when others then raise exception 'algorithm_package_founder_request_invalid'; end;
      v_authority:=chlom_runtime.framework_production_authority_v1(v_package.package_id,v_package.framework_id,v_package.metadata->>'production_exact_version_ref',v_package.metadata->>'production_content_sha256','founder_override',v_request_id);
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
end;
$$;
revoke all on function institutional_federation.append_chain_event(text,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function institutional_federation.append_chain_event(text,text,text,text,jsonb) to service_role;
