-- Live repair migration: 20260824001624 / framework_production_ask_first_confirmation_repair_v2
-- The preflight remains permanently non-executable. Explicit Founder confirmation is recorded
-- as `confirmed_external`; the separate exact Founder Continuity request is execution authority.

create or replace function chlom_runtime.confirm_founder_override_deadlock_preflight_v1(p_preflight_id uuid, p_authority_evidence_ref text)
returns jsonb language plpgsql security definer
set search_path=pg_catalog,chlom_runtime as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v chlom_runtime.founder_override_deadlock_preflights_v1%rowtype;
  d jsonb;
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if coalesce(p_authority_evidence_ref,'')='' then raise exception 'authority_evidence_required'; end if;
  select * into v from chlom_runtime.founder_override_deadlock_preflights_v1 where preflight_id=p_preflight_id for update;
  if not found then raise exception 'unknown_deadlock_preflight'; end if;
  if not v.technical_pass or not v.governance_deadlock or not v.founder_confirmation_required or not v.no_auto_invoke or v.override_executable then raise exception 'preflight_not_eligible_for_founder_confirmation'; end if;
  if v.founder_confirmation_state not in ('awaiting','confirmed_external') then raise exception 'preflight_confirmation_state_invalid'; end if;
  update chlom_runtime.founder_override_deadlock_preflights_v1
  set founder_confirmation_state='confirmed_external', override_executable=false,
      evidence=coalesce(evidence,'{}'::jsonb)||jsonb_build_object('founder_confirmation_evidence_ref',p_authority_evidence_ref,'founder_confirmed_at',clock_timestamp(),'explicit_confirmation_required',true,'preflight_remains_non_executable',true,'execution_authority_source','separate_exact_founder_continuity_request')
  where preflight_id=p_preflight_id;
  d:=chlom_runtime.append_dail_event('founder.override.deadlock.confirmed_external','governance_preflight',p_preflight_id::text,jsonb_build_object('subject_ref',v.subject_ref,'exact_version_ref',v.exact_version_ref,'content_sha256',v.content_sha256,'override_executable',false,'no_auto_invoke',true,'execution_authority_source','separate_exact_founder_continuity_request'),'human_founder',null,null,'1.0.1',null,null,'Explicit Founder confirmation after ask-first deadlock preflight; preflight itself remains non-executable.',p_authority_evidence_ref,'restricted');
  return jsonb_build_object('preflight_id',p_preflight_id,'state','CONFIRMED_EXTERNAL','override_executable',false,'execution_authority_source','separate_exact_founder_continuity_request','dail_event_id',d->>'event_id');
end $$;
revoke all on function chlom_runtime.confirm_founder_override_deadlock_preflight_v1(uuid,text) from public,anon,authenticated;
grant execute on function chlom_runtime.confirm_founder_override_deadlock_preflight_v1(uuid,text) to service_role;

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
  else
    raise exception 'unsupported_production_authority_mode';
  end if;
end $$;
revoke all on function chlom_runtime.framework_production_authority_v1(text,text,text,text,text,uuid) from public,anon,authenticated;
grant execute on function chlom_runtime.framework_production_authority_v1(text,text,text,text,text,uuid) to service_role;
