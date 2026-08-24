-- Canonical live migration: 20260823235410 / framework_production_promotion_and_cie_activation_v1
-- Applied to ThriveBase before source projection; this file institutionalizes the exact production-control contract.

create table if not exists chlom_runtime.framework_production_receipts_v1 (
  receipt_id uuid primary key default extensions.gen_random_uuid(),
  package_id text not null references institutional_federation.framework_package_registry(package_id) on delete restrict,
  framework_id text not null,
  event_type text not null check (event_type in ('activation','rollback')),
  authority_mode text not null check (authority_mode in ('agent_d_certification','founder_override','rollback_only')),
  founder_request_id uuid null references chlom_runtime.founder_continuity_requests(request_id) on delete restrict,
  exact_version_ref text not null,
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  authority_evidence_ref text not null,
  pre_state jsonb not null default '{}'::jsonb,
  post_state jsonb not null default '{}'::jsonb,
  canary_result jsonb not null default '{}'::jsonb,
  rollback_state text not null default 'ready' check (rollback_state in ('ready','not_required','executed','failed')),
  receipt_sha256 text not null check (receipt_sha256 ~ '^[0-9a-f]{64}$'),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp()
);
alter table chlom_runtime.framework_production_receipts_v1 enable row level security;
alter table chlom_runtime.framework_production_receipts_v1 force row level security;
revoke all on table chlom_runtime.framework_production_receipts_v1 from public, anon, authenticated;
grant select on table chlom_runtime.framework_production_receipts_v1 to service_role;

create or replace function chlom_runtime.reject_framework_production_receipt_mutation_v1()
returns trigger language plpgsql set search_path=pg_catalog as $$
begin
  raise exception 'framework_production_receipts_append_only' using errcode='42501';
end $$;
drop trigger if exists trg_framework_production_receipt_immutable_v1 on chlom_runtime.framework_production_receipts_v1;
create trigger trg_framework_production_receipt_immutable_v1 before update or delete on chlom_runtime.framework_production_receipts_v1 for each row execute function chlom_runtime.reject_framework_production_receipt_mutation_v1();

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
  if not v.technical_pass or not v.governance_deadlock or not v.founder_confirmation_required or not v.no_auto_invoke then raise exception 'preflight_not_eligible_for_founder_confirmation'; end if;
  if v.founder_confirmation_state not in ('awaiting','confirmed') then raise exception 'preflight_confirmation_state_invalid'; end if;
  update chlom_runtime.founder_override_deadlock_preflights_v1
  set founder_confirmation_state='confirmed', override_executable=true,
      evidence=coalesce(evidence,'{}'::jsonb)||jsonb_build_object('founder_confirmation_evidence_ref',p_authority_evidence_ref,'founder_confirmed_at',clock_timestamp(),'explicit_confirmation_required',true)
  where preflight_id=p_preflight_id;
  d:=chlom_runtime.append_dail_event('founder.override.deadlock.confirmed','governance_preflight',p_preflight_id::text,jsonb_build_object('subject_ref',v.subject_ref,'exact_version_ref',v.exact_version_ref,'content_sha256',v.content_sha256,'override_executable',true,'no_auto_invoke',true),'human_founder',null,null,'1.0.0',null,null,'Explicit Founder confirmation after ask-first deadlock preflight',p_authority_evidence_ref,'restricted');
  return jsonb_build_object('preflight_id',p_preflight_id,'state','CONFIRMED','override_executable',true,'dail_event_id',d->>'event_id');
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
    if not found or f.subject_ref<>p_authority_subject_ref or f.exact_version_ref<>p_exact_version_ref or f.content_sha256<>p_content_sha256 or not f.technical_pass or not f.governance_deadlock or f.founder_confirmation_state<>'confirmed' or not f.override_executable or not f.no_auto_invoke then raise exception 'confirmed_exact_deadlock_preflight_required'; end if;
    v_verify:=chlom_runtime.founder_continuity_verify_human_override_v1(p_founder_request_id,p_exact_version_ref,p_content_sha256);
    if not coalesce((v_verify->>'valid')::boolean,false) then raise exception 'founder_override_verification_failed'; end if;
    return jsonb_build_object('valid',true,'mode','founder_override','founder_request_id',p_founder_request_id,'deadlock_preflight_id',v_preflight_id,'authority_evidence_ref',coalesce(r.human_authority_evidence_ref,'human_founder'));
  else
    raise exception 'unsupported_production_authority_mode';
  end if;
end $$;
revoke all on function chlom_runtime.framework_production_authority_v1(text,text,text,text,text,uuid) from public,anon,authenticated;
grant execute on function chlom_runtime.framework_production_authority_v1(text,text,text,text,text,uuid) to service_role;

create or replace function chlom_runtime.activate_repository_guardian_production_v1(
  p_exact_version_ref text,
  p_content_sha256 text,
  p_authority_mode text,
  p_founder_request_id uuid default null
) returns jsonb language plpgsql security definer
set search_path=pg_catalog,chlom_runtime,institutional_federation,cron,extensions as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  p institutional_federation.framework_package_registry%rowtype;
  h chlom_runtime.agent_health%rowtype;
  v_auth jsonb; v_canary jsonb; v_pre jsonb; v_post jsonb; v_sha text; v_receipt uuid; d jsonb;
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  v_auth:=chlom_runtime.framework_production_authority_v1('ct.framework-package.repository-child-guardian-ad-litem','ct.framework.repository-child-guardian-ad-litem',p_exact_version_ref,p_content_sha256,p_authority_mode,p_founder_request_id);
  select * into p from institutional_federation.framework_package_registry where package_id='ct.framework-package.repository-child-guardian-ad-litem' for update;
  select * into h from chlom_runtime.agent_health where agent_id='ct.agent.repository-child-guardian-ad-litem';
  if not found or h.health_state<>'healthy' or h.last_success_at is null or h.last_success_at<now()-interval '2 hours' or h.last_error_code is not null then raise exception 'guardian_runtime_not_healthy'; end if;
  if not exists(select 1 from cron.job where jobname='ct-repository-child-guardian-30m' and active and command like '%repository_child_guardian_family_cycle_v1%') then raise exception 'guardian_cron_not_active'; end if;
  if coalesce((p.metadata->>'framework_test_state'),'')<>'pass' or coalesce((p.metadata->>'vaulted_count')::int,0)<33 or coalesce((p.metadata->>'interop_agents_aware')::int,0)<6 then raise exception 'guardian_factory_evidence_incomplete'; end if;
  v_pre:=jsonb_build_object('package_state',p.package_state,'parent_certification_state',p.parent_certification_state,'operationally_enabled',p.operationally_enabled,'public_activation_allowed',p.public_activation_allowed,'api_state',p.api_state,'mcp_state',p.mcp_state,'commercial_state',p.commercial_state);
  update institutional_federation.framework_package_registry
  set package_state='maintained', operationally_enabled=true, public_activation_allowed=false,
      metadata=metadata||jsonb_build_object('production_runtime_state','active','production_authority_mode',p_authority_mode,'production_authority_request_id',p_founder_request_id,'production_exact_version_ref',p_exact_version_ref,'production_content_sha256',p_content_sha256,'production_activated_at',clock_timestamp(),'authority_expansion',false,'public_activation',false,'merge_authority',false,'delete_authority',false,'child_self_activation',false), updated_at=now()
  where package_id=p.package_id;
  v_canary:=chlom_runtime.repository_child_guardian_family_cycle_v1();
  if coalesce(v_canary->>'state','')<>'PASS_CONTROLLED_TEST' or coalesce((v_canary->>'authority_from_titles')::boolean,false) then raise exception 'guardian_production_canary_failed'; end if;
  v_post:=jsonb_build_object('package_state','maintained','operationally_enabled',true,'public_activation_allowed',false,'production_runtime_state','active');
  v_sha:=encode(extensions.digest(convert_to(p.package_id||'|'||p_exact_version_ref||'|'||p_content_sha256||'|'||p_authority_mode||'|'||coalesce(p_founder_request_id::text,'')||'|'||v_canary::text,'UTF8'),'sha256'),'hex');
  insert into chlom_runtime.framework_production_receipts_v1(package_id,framework_id,event_type,authority_mode,founder_request_id,exact_version_ref,content_sha256,authority_evidence_ref,pre_state,post_state,canary_result,rollback_state,receipt_sha256,metadata)
  values(p.package_id,p.framework_id,'activation',p_authority_mode,p_founder_request_id,p_exact_version_ref,p_content_sha256,coalesce(v_auth->>'authority_evidence_ref','ct.relay.agent-d'),v_pre,v_post,jsonb_build_object('state',v_canary->>'state','family_root_sha256',v_canary#>>'{family,family_root_sha256}','authority_from_titles',coalesce((v_canary->>'authority_from_titles')::boolean,false)),'ready',v_sha,jsonb_build_object('agent_id','ct.agent.repository-child-guardian-ad-litem','D3_auto',false,'vote_effect',false)) returning receipt_id into v_receipt;
  d:=chlom_runtime.append_dail_event('framework.production.activated','framework_package',p.package_id,jsonb_build_object('framework_id',p.framework_id,'authority_mode',p_authority_mode,'production_receipt_id',v_receipt,'receipt_sha256',v_sha,'operationally_enabled',true,'public_activation_allowed',false,'authority_expansion',false),'ct.agent.repository-child-guardian-ad-litem',null,'ct.agent.repository-child-guardian-ad-litem','1.0.0',null,null,'Exact governed production promotion with bounded authority',coalesce(v_auth->>'authority_evidence_ref','ct.relay.agent-d'),'restricted');
  return jsonb_build_object('state','PRODUCTION_ACTIVE','package_id',p.package_id,'production_receipt_id',v_receipt,'receipt_sha256',v_sha,'canary_state',v_canary->>'state','operationally_enabled',true,'public_activation_allowed',false,'authority_expansion',false,'D3_auto',false,'vote_effect',false,'dail_event_id',d->>'event_id');
end $$;
revoke all on function chlom_runtime.activate_repository_guardian_production_v1(text,text,text,uuid) from public,anon,authenticated;
grant execute on function chlom_runtime.activate_repository_guardian_production_v1(text,text,text,uuid) to service_role;

create or replace function chlom_runtime.activate_cie_production_v1(
  p_parent_head text,
  p_child_head text,
  p_exact_version_ref text,
  p_content_sha256 text,
  p_authority_mode text,
  p_founder_request_id uuid default null
) returns jsonb language plpgsql security definer
set search_path=pg_catalog,chlom_runtime,institutional_federation,integration_control,chlom_identity,vault,extensions,public as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  p institutional_federation.framework_package_registry%rowtype;
  r institutional_federation.repository_registry%rowtype;
  b institutional_federation.repository_agent_bindings%rowtype;
  a institutional_federation.algorithm_registry%rowtype;
  v_auth jsonb; v_gate jsonb; v_pre jsonb; v_post jsonb; v_canary jsonb; v_policy jsonb; v_bundle text; v_evidence jsonb; v_subject jsonb; v_sha text; v_receipt uuid; d jsonb; v_blockers int;
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if p_parent_head !~ '^[0-9a-f]{40}$' or p_child_head !~ '^[0-9a-f]{40}$' then raise exception 'exact_git_sha_required'; end if;
  v_auth:=chlom_runtime.framework_production_authority_v1('ct.framework-package.cie','ct.framework.cultural-imprint-engine',p_exact_version_ref,p_content_sha256,p_authority_mode,p_founder_request_id);
  v_gate:=chlom_runtime.cie_wave4_activation_evidence_gate_v1(p_child_head,p_parent_head,'e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2');
  if v_gate->>'source_integration_state'<>'SOURCE_INTEGRATION_READY' then raise exception 'cie_source_integration_not_ready:%',v_gate->>'source_integration_state'; end if;
  if p_authority_mode='agent_d_certification' and not coalesce((v_gate->>'parent_certified')::boolean,false) then raise exception 'cie_parent_certification_required'; end if;
  if not exists(select 1 from integration_control.ecosystem_rollout_platforms where platform_key='cie' and stable_platform_id='ct.platform.cie' and identity_state='resolved') then raise exception 'cie_stable_identity_not_resolved'; end if;
  select count(*) into v_blockers from integration_control.platform_certification_dimensions where platform_key='cie' and state not in ('pass','not_applicable');
  if v_blockers>0 then raise exception 'cie_certification_dimensions_not_closed:%',v_blockers; end if;
  select * into p from institutional_federation.framework_package_registry where package_id='ct.framework-package.cie' for update;
  select * into r from institutional_federation.repository_registry where repo_id='ct.repo.cie' for update;
  select * into a from institutional_federation.algorithm_registry where algorithm_id='ct.algorithm.cie.v1' for update;
  select * into b from institutional_federation.repository_agent_bindings where repo_id='ct.repo.cie' and agent_id='ct.framework-agent.cie' for update;
  if not found then raise exception 'cie_framework_agent_binding_missing'; end if;
  v_pre:=jsonb_build_object('package',jsonb_build_object('package_state',p.package_state,'parent_certification_state',p.parent_certification_state,'operationally_enabled',p.operationally_enabled,'public_activation_allowed',p.public_activation_allowed,'private_runtime_state',p.private_runtime_state,'api_state',p.api_state,'mcp_state',p.mcp_state,'commercial_state',p.commercial_state),'repository',jsonb_build_object('governance_state',r.governance_state,'operationally_enabled',r.operationally_enabled,'can_vote',r.can_vote),'algorithm',jsonb_build_object('invocation_state',a.invocation_state),'binding',jsonb_build_object('binding_state',b.binding_state,'algorithm_enabled',b.algorithm_enabled,'vote_eligible',b.vote_eligible));
  update institutional_federation.repository_registry set governance_state='linked_governed',operationally_enabled=true,can_vote=false,voter_agent_id=null,last_parent_sha=p_parent_head,last_child_sha=p_child_head,metadata=metadata||jsonb_build_object('production_runtime_state','active','production_authority_mode',p_authority_mode,'production_authority_request_id',p_founder_request_id,'production_exact_version_ref',p_exact_version_ref,'production_content_sha256',p_content_sha256,'production_activated_at',clock_timestamp(),'sovereign_vote_created',false,'D3_auto',false),updated_at=now() where repo_id='ct.repo.cie';
  update institutional_federation.framework_package_registry set package_state='maintained',operationally_enabled=true,public_activation_allowed=false,private_runtime_state='available',api_state='enabled',mcp_state='enabled',commercial_state='hold',exact_price_authorized=false,checkout_enabled=false,customer_entitlement_active=false,metadata=metadata||jsonb_build_object('production_runtime_state','active','production_authority_mode',p_authority_mode,'production_authority_request_id',p_founder_request_id,'production_exact_version_ref',p_exact_version_ref,'production_content_sha256',p_content_sha256,'production_parent_head',p_parent_head,'production_child_head',p_child_head,'production_activated_at',clock_timestamp(),'api_exposure','governed_internal_only','mcp_exposure','governed_internal_only','commerce_activation',false,'authority_expansion',false),updated_at=now() where package_id='ct.framework-package.cie';
  update institutional_federation.repository_agent_bindings set binding_state='active',authority_ceiling='D2',vote_eligible=false,algorithm_enabled=true,heartbeat_enabled=true,publish_enabled=true,ack_enabled=true,reference_enabled=true,certify_enabled=false,sync_agents_enabled=false,source_ref='production:ct.framework.cultural-imprint-engine',metadata=metadata||jsonb_build_object('production_algorithm_invocation',true,'production_limited',true,'authority_expansion',false,'vote_effect',false,'enabled_at',clock_timestamp()),updated_at=now() where repo_id='ct.repo.cie' and agent_id='ct.framework-agent.cie';
  update institutional_federation.algorithm_registry set invocation_state='production_limited',metadata=metadata||jsonb_build_object('production_runtime_state','production_limited','production_authority_mode',p_authority_mode,'production_authority_request_id',p_founder_request_id,'production_child_head',p_child_head,'production_activated_at',clock_timestamp(),'provider_write_effect',false,'economic_effect',false,'rights_effect',false,'D3_auto',false),updated_at=now() where algorithm_id='ct.algorithm.cie.v1';
  select decrypted_secret into v_bundle from vault.decrypted_secrets where name=a.sealed_bundle_secret_name limit 1;
  if v_bundle is null then raise exception 'cie_production_canary_bundle_unavailable'; end if;
  if encode(extensions.digest(convert_to(v_bundle,'UTF8'),'sha256'),'hex')<>coalesce(a.metadata->>'sealed_bundle_sha256','') then raise exception 'cie_production_canary_bundle_integrity_failure'; end if;
  v_policy:=v_bundle::jsonb;
  select coalesce(jsonb_object_agg(x,jsonb_build_array(jsonb_build_object('evidence_ref','ct.cie.production-canary.v1','state','verified'))),'{}'::jsonb) into v_evidence from jsonb_array_elements_text(v_policy->'dimensions') x;
  v_subject:=jsonb_build_object('subject_id','ct.cie.canary.production.'||replace(extensions.gen_random_uuid()::text,'-',''),'subject_type','canary','dimension_evidence',v_evidence,'findings','[]'::jsonb);
  v_canary:=public.ct_cie_score_private_impl('crownthrive1/CrownThrive-CIE',1341314455,'ct.framework-agent.cie',v_subject);
  if coalesce(v_canary->>'verdict','')<>'PASS' or v_canary->>'score' is null then raise exception 'cie_production_score_canary_failed'; end if;
  v_post:=jsonb_build_object('package_state','maintained','repository_state','linked_governed','algorithm_invocation_state','production_limited','framework_agent_algorithm_enabled',true,'operationally_enabled',true,'public_activation_allowed',false,'commercial_state','hold');
  v_sha:=encode(extensions.digest(convert_to(p.package_id||'|'||p_exact_version_ref||'|'||p_content_sha256||'|'||p_authority_mode||'|'||coalesce(p_founder_request_id::text,'')||'|'||p_parent_head||'|'||p_child_head||'|'||coalesce(v_canary->>'score','')||'|'||coalesce(v_canary->>'verdict',''),'UTF8'),'sha256'),'hex');
  insert into chlom_runtime.framework_production_receipts_v1(package_id,framework_id,event_type,authority_mode,founder_request_id,exact_version_ref,content_sha256,authority_evidence_ref,pre_state,post_state,canary_result,rollback_state,receipt_sha256,metadata)
  values(p.package_id,p.framework_id,'activation',p_authority_mode,p_founder_request_id,p_exact_version_ref,p_content_sha256,coalesce(v_auth->>'authority_evidence_ref','ct.relay.agent-d'),v_pre,v_post,jsonb_build_object('verdict',v_canary->>'verdict','score',v_canary->>'score','algorithm_id',v_canary->>'algorithm_id','algorithm_version',v_canary->>'algorithm_version','chain_event_hash',v_canary->>'chain_event_hash','policy_contract_digest',v_canary->>'policy_contract_digest'),'ready',v_sha,jsonb_build_object('D3_auto',false,'vote_effect',false,'provider_write_effect',false,'economic_effect',false,'rights_effect',false,'commercial_activation',false)) returning receipt_id into v_receipt;
  d:=chlom_runtime.append_dail_event('cie.production.activated','framework_package',p.package_id,jsonb_build_object('production_receipt_id',v_receipt,'receipt_sha256',v_sha,'parent_head',p_parent_head,'child_head',p_child_head,'authority_mode',p_authority_mode,'canary_verdict',v_canary->>'verdict','canary_score',v_canary->>'score','algorithm_invocation_state','production_limited','public_activation_allowed',false,'commercial_activation',false,'authority_expansion',false),'ct.framework-agent.cie',null,'ct.framework-agent.cie','1.0.0',null,null,'Exact governed CIE production activation',coalesce(v_auth->>'authority_evidence_ref','ct.relay.agent-d'),'restricted');
  return jsonb_build_object('state','PRODUCTION_ACTIVE','package_id',p.package_id,'repository_state','linked_governed','algorithm_invocation_state','production_limited','production_receipt_id',v_receipt,'receipt_sha256',v_sha,'canary_verdict',v_canary->>'verdict','canary_score',v_canary->>'score','operationally_enabled',true,'public_activation_allowed',false,'commercial_activation',false,'authority_expansion',false,'D3_auto',false,'vote_effect',false,'dail_event_id',d->>'event_id');
end $$;
revoke all on function chlom_runtime.activate_cie_production_v1(text,text,text,text,text,uuid) from public,anon,authenticated;
grant execute on function chlom_runtime.activate_cie_production_v1(text,text,text,text,text,uuid) to service_role;

create or replace function public.ct_cie_score(p_repo_full_name text,p_github_repository_id bigint,p_agent_id text,p_subject jsonb)
returns jsonb language plpgsql security definer
set search_path=institutional_federation,chlom_runtime,pg_catalog,pg_temp as $$
declare
  r institutional_federation.repository_registry%rowtype;
  a institutional_federation.algorithm_registry%rowtype;
  p institutional_federation.framework_package_registry%rowtype;
  v_override_ok boolean:=false;
  v_request_id uuid;
begin
  select * into r from institutional_federation.repository_registry where repo_full_name=p_repo_full_name;
  if not found or r.github_repository_id<>p_github_repository_id then raise exception 'repository_not_authorized'; end if;
  select * into a from institutional_federation.algorithm_registry where algorithm_id='ct.algorithm.cie.v1';
  if not found or a.implementation_repo_id<>r.repo_id then raise exception 'algorithm_implementation_repository_mismatch'; end if;
  if r.governance_state<>'linked_governed' or not r.operationally_enabled or r.child_contract_digest is null then raise exception 'algorithm_repository_not_linked_governed'; end if;
  select * into p from institutional_federation.framework_package_registry where package_id=a.implementation_package_id;
  if not found or not p.operationally_enabled or p.can_vote then raise exception 'algorithm_package_not_operational'; end if;
  if p.parent_certification_agent='ct.relay.agent-d' and p.parent_certification_state='certified' then
    v_override_ok:=true;
  elsif p.metadata->>'production_authority_mode'='founder_override' then
    begin v_request_id:=(p.metadata->>'production_authority_request_id')::uuid; exception when others then v_request_id:=null; end;
    if v_request_id is not null and exists(select 1 from chlom_runtime.founder_override_execution_receipts_v1 x join chlom_runtime.founder_continuity_requests q on q.request_id=x.request_id where x.request_id=v_request_id and x.execution_state='succeeded' and x.exact_version_ref=p.metadata->>'production_exact_version_ref' and x.content_sha256=p.metadata->>'production_content_sha256' and q.human_signal_state='approved') then v_override_ok:=true; end if;
  end if;
  if not v_override_ok then raise exception 'algorithm_package_production_authority_not_verified'; end if;
  return public.ct_cie_score_private_impl(p_repo_full_name,p_github_repository_id,p_agent_id,p_subject);
end $$;
revoke all on function public.ct_cie_score(text,bigint,text,jsonb) from public,anon,authenticated;
grant execute on function public.ct_cie_score(text,bigint,text,jsonb) to service_role;

create or replace function chlom_runtime.rollback_framework_production_v1(p_activation_receipt_id uuid,p_reason text)
returns jsonb language plpgsql security definer
set search_path=pg_catalog,chlom_runtime,institutional_federation,extensions as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  x chlom_runtime.framework_production_receipts_v1%rowtype; v_sha text; v_receipt uuid; d jsonb;
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if coalesce(p_reason,'')='' then raise exception 'rollback_reason_required'; end if;
  select * into x from chlom_runtime.framework_production_receipts_v1 where receipt_id=p_activation_receipt_id and event_type='activation';
  if not found then raise exception 'unknown_activation_receipt'; end if;
  if exists(select 1 from chlom_runtime.framework_production_receipts_v1 where metadata->>'rolled_back_activation_receipt_id'=p_activation_receipt_id::text) then raise exception 'activation_already_rolled_back'; end if;
  update institutional_federation.framework_package_registry set package_state=coalesce(x.pre_state->>'package_state',package_state),parent_certification_state=coalesce(x.pre_state->>'parent_certification_state',parent_certification_state),operationally_enabled=coalesce((x.pre_state->>'operationally_enabled')::boolean,false),public_activation_allowed=coalesce((x.pre_state->>'public_activation_allowed')::boolean,false),private_runtime_state=coalesce(x.pre_state#>>'{package,private_runtime_state}',private_runtime_state),api_state=coalesce(x.pre_state#>>'{package,api_state}',x.pre_state->>'api_state',api_state),mcp_state=coalesce(x.pre_state#>>'{package,mcp_state}',x.pre_state->>'mcp_state',mcp_state),commercial_state=coalesce(x.pre_state#>>'{package,commercial_state}',x.pre_state->>'commercial_state',commercial_state),metadata=metadata||jsonb_build_object('production_runtime_state','rolled_back','rolled_back_at',clock_timestamp(),'rolled_back_activation_receipt_id',p_activation_receipt_id,'rollback_reason',p_reason),updated_at=now() where package_id=x.package_id;
  if x.package_id='ct.framework-package.cie' then
    update institutional_federation.repository_registry set governance_state=coalesce(x.pre_state#>>'{repository,governance_state}',governance_state),operationally_enabled=coalesce((x.pre_state#>>'{repository,operationally_enabled}')::boolean,false),can_vote=false,voter_agent_id=null,metadata=metadata||jsonb_build_object('production_runtime_state','rolled_back','rolled_back_at',clock_timestamp(),'rolled_back_activation_receipt_id',p_activation_receipt_id),updated_at=now() where repo_id='ct.repo.cie';
    update institutional_federation.algorithm_registry set invocation_state=coalesce(x.pre_state#>>'{algorithm,invocation_state}',invocation_state),metadata=metadata||jsonb_build_object('production_runtime_state','rolled_back','rolled_back_at',clock_timestamp(),'rolled_back_activation_receipt_id',p_activation_receipt_id),updated_at=now() where algorithm_id='ct.algorithm.cie.v1';
    update institutional_federation.repository_agent_bindings set binding_state=coalesce(x.pre_state#>>'{binding,binding_state}',binding_state),algorithm_enabled=coalesce((x.pre_state#>>'{binding,algorithm_enabled}')::boolean,false),vote_eligible=false,metadata=metadata||jsonb_build_object('production_algorithm_invocation',false,'rolled_back_at',clock_timestamp(),'rolled_back_activation_receipt_id',p_activation_receipt_id),updated_at=now() where repo_id='ct.repo.cie' and agent_id='ct.framework-agent.cie';
  end if;
  v_sha:=encode(extensions.digest(convert_to(x.package_id||'|'||p_activation_receipt_id::text||'|'||p_reason||'|'||clock_timestamp()::text,'UTF8'),'sha256'),'hex');
  insert into chlom_runtime.framework_production_receipts_v1(package_id,framework_id,event_type,authority_mode,founder_request_id,exact_version_ref,content_sha256,authority_evidence_ref,pre_state,post_state,canary_result,rollback_state,receipt_sha256,metadata)
  values(x.package_id,x.framework_id,'rollback','rollback_only',x.founder_request_id,x.exact_version_ref,x.content_sha256,'authority_reducing_rollback',x.post_state,x.pre_state,jsonb_build_object('rollback_reason',p_reason),'executed',v_sha,jsonb_build_object('rolled_back_activation_receipt_id',p_activation_receipt_id)) returning receipt_id into v_receipt;
  d:=chlom_runtime.append_dail_event('framework.production.rolled_back','framework_package',x.package_id,jsonb_build_object('activation_receipt_id',p_activation_receipt_id,'rollback_receipt_id',v_receipt,'receipt_sha256',v_sha,'reason',p_reason),'ct.agent.architecture-refactor-optimizer',null,'ct.agent.architecture-refactor-optimizer','1.0.0',null,null,'Authority-reducing production rollback',null,'restricted');
  return jsonb_build_object('state','ROLLED_BACK','package_id',x.package_id,'activation_receipt_id',p_activation_receipt_id,'rollback_receipt_id',v_receipt,'receipt_sha256',v_sha,'dail_event_id',d->>'event_id');
end $$;
revoke all on function chlom_runtime.rollback_framework_production_v1(uuid,text) from public,anon,authenticated;
grant execute on function chlom_runtime.rollback_framework_production_v1(uuid,text) to service_role;
