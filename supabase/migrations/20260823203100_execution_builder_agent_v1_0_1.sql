-- CrownThrive Execution Builder Agent v1.0.1
-- Dedicated cross-agent materialization lane. Controlled-test, D2 maximum, non-voting.
-- No direct-main, force-push, self-merge, self-certification, D3, secret export, provider activation,
-- money movement, rights grant, checkout or sovereign authority.
begin;

do $preflight$
begin
  if not exists(select 1 from chlom_runtime.agent_templates where agent_id='ct.relay.agent-c' and lifecycle_state='active') then
    raise exception 'HOLD_PARENT_AGENT_C_NOT_ACTIVE';
  end if;
  if not exists(select 1 from chlom_runtime.agent_templates where agent_id='ct.relay.agent-d' and lifecycle_state='active') then
    raise exception 'HOLD_PARENT_CERTIFIER_D_NOT_ACTIVE';
  end if;
  if to_regclass('chlom_runtime.vaulted_capability_registry') is null
     or to_regclass('chlom_secrets.trade_secret_assets') is null
     or to_regclass('chlom_runtime.construction_work_queue') is null
     or to_regclass('institutional_federation.capability_execution_queue') is null
  then raise exception 'HOLD_EXECUTION_BUILDER_DEPENDENCY_MISSING'; end if;
end
$preflight$;

insert into chlom_runtime.agent_templates(
  agent_id,parent_agent_id,canonical_name,agent_class,autonomy_class,authority_ceiling,lifecycle_state,
  module_scope,tool_scope,schedule_profile,vote_eligible,self_healing_enabled,no_self_approval,heartbeat_ttl_seconds,metadata
) values (
  'ct.agent.execution-builder','ct.relay.agent-c','CrownThrive Execution Builder Agent','builder','A3','D2','test',
  array['framework_factory','construction_work_queue','capability_execution_queue','candidate_repositories','documentation','api_mcp_candidates'],
  jsonb_build_object(
    'read_exact_requests',true,'candidate_branch_write',true,'candidate_commit_write',true,'candidate_pr_prepare',true,
    'tests_and_evals',true,'docs_and_contracts',true,'migration_candidate_prepare',true,'rollback_prepare',true,
    'direct_main_write',false,'force_push',false,'self_merge',false,'provider_write',false,'credential_write',false,
    'money_movement',false,'rights_grant',false,'d3',false,'sovereign_vote',false
  ),'internal_event_driven',false,true,true,3600,
  jsonb_build_object(
    'sole_mission','materialize bounded accepted build requests from agents',
    'completion_state','BUILT_PENDING_INDEPENDENT_VERIFICATION','independent_certifier',false,
    'originator_builder',true,'protected_inputs','opaque_refs_only','parent_certifier','ct.relay.agent-d',
    'manifest_sha256','b763604e2ecb28374ae7d8be7228ece566703e898900effcd6c6cb7fe4f0ea26',
    'source_pr',301,'source_head_binding','EXACT_HEAD_READBACK_REQUIRED'
  )
) on conflict(agent_id) do update set
  parent_agent_id=excluded.parent_agent_id,canonical_name=excluded.canonical_name,agent_class='builder',
  autonomy_class='A3',authority_ceiling='D2',lifecycle_state='test',module_scope=excluded.module_scope,
  tool_scope=excluded.tool_scope,schedule_profile='internal_event_driven',vote_eligible=false,
  no_self_approval=true,metadata=chlom_runtime.agent_templates.metadata||excluded.metadata,updated_at=now();

insert into chlom_runtime.agent_suite_registry(
  suite_id,semantic_version,canonical_name,release_state,manifest_ref,manifest_sha256,parent_agent_id,parent_certifier_id,
  vote_eligible,quorum_eligible,d3_human_reserved,no_self_approval,no_silent_delete,drive_custody_required,
  supabase_storage_required,vault_secret_ref,source_ids,metadata
) values (
  'ct.agent-suite.execution-builder.v1','1.0.1','CrownThrive Execution Builder Suite','controlled_test',
  'developers/manifests/execution-builder-agent.v1.json','b763604e2ecb28374ae7d8be7228ece566703e898900effcd6c6cb7fe4f0ea26',
  'ct.relay.agent-c','ct.relay.agent-d',false,false,true,true,true,true,true,
  'ct.vaultref.execution-builder-suite.primary',array['ct.relay.agent-c','ct.agent.execution-builder','ct.relay.agent-d'],
  jsonb_build_object('commercial_activation',false,'provider_activation',false,'originator_cannot_certify',true,'event_driven',true)
) on conflict(suite_id) do update set
  semantic_version='1.0.1',release_state='controlled_test',manifest_ref=excluded.manifest_ref,
  manifest_sha256=excluded.manifest_sha256,parent_agent_id='ct.relay.agent-c',parent_certifier_id='ct.relay.agent-d',
  vote_eligible=false,quorum_eligible=false,d3_human_reserved=true,no_self_approval=true,no_silent_delete=true,
  metadata=chlom_runtime.agent_suite_registry.metadata||excluded.metadata,updated_at=now();

insert into chlom_runtime.agent_skill_packages(
  skill_id,suite_id,agent_id,install_name,semantic_version,generation_support,manifest_ref,manifest_sha256,
  mcp_state,commercial_state,price_credits,checkout_enabled,entitlement_active,release_receipt,metadata
) values (
  'ct.skill.execution-builder.v1','ct.agent-suite.execution-builder.v1','ct.agent.execution-builder','execution-builder','1.0.1',
  array['gen7','framework_factory'],'skills/execution-builder-agent/SKILL.md','b763604e2ecb28374ae7d8be7228ece566703e898900effcd6c6cb7fe4f0ea26',
  'candidate','hold',null,false,false,null,
  jsonb_build_object('sole_mission','materialize_build_requests','certification_effect',false,'checkout_effect',false)
) on conflict(skill_id) do update set
  suite_id=excluded.suite_id,agent_id=excluded.agent_id,semantic_version='1.0.1',generation_support=excluded.generation_support,
  manifest_ref=excluded.manifest_ref,manifest_sha256=excluded.manifest_sha256,mcp_state='candidate',commercial_state='hold',
  price_credits=null,checkout_enabled=false,entitlement_active=false,release_receipt=null,
  metadata=chlom_runtime.agent_skill_packages.metadata||excluded.metadata,updated_at=now();

insert into chlom_secrets.trade_secret_assets(
  asset_id,asset_kind,classification,canonical_name,version,vault_secret_id,vault_secret_name,
  public_reference_digest,public_body_allowed,drive_archive_required,lifecycle_state,source_ref,metadata
) values (
  'ct.asset.agent.execution-builder.v1','agent_capability','PUBLIC_CONTRACT_RESTRICTED_IMPLEMENTATION',
  'CrownThrive Execution Builder Agent Runtime','1.0.1',null,null,
  'b763604e2ecb28374ae7d8be7228ece566703e898900effcd6c6cb7fe4f0ea26',false,true,'controlled_test',
  'developers/manifests/execution-builder-agent.v1.json',
  jsonb_build_object('raw_secret_return',false,'public_contract_only',true,'private_body_required',false,'custody_required',true)
) on conflict(asset_id) do update set
  classification='PUBLIC_CONTRACT_RESTRICTED_IMPLEMENTATION',canonical_name=excluded.canonical_name,version='1.0.1',
  public_reference_digest=excluded.public_reference_digest,public_body_allowed=false,drive_archive_required=true,
  lifecycle_state='controlled_test',source_ref=excluded.source_ref,metadata=chlom_secrets.trade_secret_assets.metadata||excluded.metadata;

insert into chlom_runtime.vaulted_capability_registry(
  capability_id,asset_id,capability_kind,handler_ref,authority_ceiling,allowed_agent_ids,invocation_state,
  requires_independent_verifier,body_exposure_allowed,output_class,immutable_digest,metadata
) values (
  'ct.capability.agent-build-execution.v1','ct.asset.agent.execution-builder.v1','sql_rpc',
  'chlom_runtime.route_construction_work_to_execution_builder','D2',array['ct.agent.execution-builder'],'controlled_test',
  true,false,'sanitized','b763604e2ecb28374ae7d8be7228ece566703e898900effcd6c6cb7fe4f0ea26',
  jsonb_build_object('candidate_artifact_bundle',true,'direct_main_write',false,'self_certification',false,'provider_write',false,'d3',false)
) on conflict(capability_id) do update set
  asset_id=excluded.asset_id,capability_kind='sql_rpc',handler_ref=excluded.handler_ref,authority_ceiling='D2',
  allowed_agent_ids=array['ct.agent.execution-builder'],invocation_state='controlled_test',requires_independent_verifier=true,
  body_exposure_allowed=false,output_class='sanitized',immutable_digest=excluded.immutable_digest,
  metadata=chlom_runtime.vaulted_capability_registry.metadata||excluded.metadata,updated_at=now();

insert into chlom_runtime.agent_health(agent_id,health_state,current_task,resource_state,updated_at)
values('ct.agent.execution-builder','pending','awaiting_build_request',jsonb_build_object('mode','event_driven','candidate_only',true,'certification_effect',false),now())
on conflict(agent_id) do update set health_state='pending',current_task='awaiting_build_request',resource_state=excluded.resource_state,updated_at=now();

create table if not exists chlom_runtime.agent_build_requests(
  request_id uuid primary key default extensions.gen_random_uuid(),
  request_key text not null unique,
  source_work_id text,
  source_queue_id uuid,
  requester_agent_id text not null references chlom_runtime.agent_templates(agent_id) on delete restrict,
  assigned_executor_id text not null default 'ct.agent.execution-builder' references chlom_runtime.agent_templates(agent_id) on delete restrict,
  verifier_agent_id text not null references chlom_runtime.agent_templates(agent_id) on delete restrict,
  target_repository text not null,
  target_base_head text not null check(target_base_head ~ '^[0-9a-f]{40}$'),
  authority_ceiling text not null check(authority_ceiling in('D0','D1','D2')),
  risk_class text not null check(risk_class in('D0','D1','D2')),
  build_scope jsonb not null default '{}'::jsonb,
  required_outputs jsonb not null default '{}'::jsonb,
  protected_input_refs jsonb not null default '[]'::jsonb,
  input_sha256 text not null check(input_sha256 ~ '^[0-9a-f]{64}$'),
  request_state text not null default 'queued' check(request_state in('queued','claimed','building','built_pending_verification','hold','cancelled','superseded')),
  direct_main_write boolean not null default false check(not direct_main_write),
  force_push boolean not null default false check(not force_push),
  self_merge boolean not null default false check(not self_merge),
  d3_allowed boolean not null default false check(not d3_allowed),
  created_at timestamptz not null default now(),updated_at timestamptz not null default now(),
  check(assigned_executor_id='ct.agent.execution-builder'),
  check(requester_agent_id<>assigned_executor_id),
  check(verifier_agent_id<>assigned_executor_id),
  check(verifier_agent_id<>requester_agent_id)
);
create index if not exists agent_build_requests_state_idx on chlom_runtime.agent_build_requests(request_state,created_at);
alter table chlom_runtime.agent_build_requests enable row level security;
alter table chlom_runtime.agent_build_requests force row level security;
revoke all on chlom_runtime.agent_build_requests from public,anon,authenticated;
grant select,insert,update on chlom_runtime.agent_build_requests to service_role;

create table if not exists chlom_runtime.agent_build_receipts(
  receipt_id uuid primary key default extensions.gen_random_uuid(),
  request_id uuid not null references chlom_runtime.agent_build_requests(request_id) on delete restrict,
  executor_agent_id text not null default 'ct.agent.execution-builder' references chlom_runtime.agent_templates(agent_id) on delete restrict,
  verifier_agent_id text not null references chlom_runtime.agent_templates(agent_id) on delete restrict,
  candidate_branch text not null,
  exact_head text not null check(exact_head ~ '^[0-9a-f]{40}$'),
  output_sha256 text not null check(output_sha256 ~ '^[0-9a-f]{64}$'),
  output_manifest jsonb not null,tests jsonb not null,rollback jsonb not null,custody jsonb not null,
  receipt_state text not null default 'BUILT_PENDING_INDEPENDENT_VERIFICATION' check(receipt_state='BUILT_PENDING_INDEPENDENT_VERIFICATION'),
  certification_effect boolean not null default false check(not certification_effect),
  sovereign_vote_created boolean not null default false check(not sovereign_vote_created),
  operational_activation boolean not null default false check(not operational_activation),
  created_at timestamptz not null default now(),
  check(executor_agent_id='ct.agent.execution-builder'),check(verifier_agent_id<>executor_agent_id)
);
create index if not exists agent_build_receipts_request_idx on chlom_runtime.agent_build_receipts(request_id,created_at desc);
alter table chlom_runtime.agent_build_receipts enable row level security;
alter table chlom_runtime.agent_build_receipts force row level security;
revoke all on chlom_runtime.agent_build_receipts from public,anon,authenticated;
grant select,insert on chlom_runtime.agent_build_receipts to service_role;

create or replace function chlom_runtime.reject_agent_build_receipt_mutation()
returns trigger language plpgsql set search_path='pg_catalog' as $$
begin raise exception 'AGENT_BUILD_RECEIPTS_APPEND_ONLY'; end $$;
revoke all on function chlom_runtime.reject_agent_build_receipt_mutation() from public,anon,authenticated,service_role;
drop trigger if exists agent_build_receipts_append_only on chlom_runtime.agent_build_receipts;
create trigger agent_build_receipts_append_only before update or delete on chlom_runtime.agent_build_receipts
for each row execute function chlom_runtime.reject_agent_build_receipt_mutation();

create or replace function chlom_runtime.route_construction_work_to_execution_builder(
  p_work_id text,p_target_repository text,p_target_base_head text
) returns jsonb
language plpgsql security definer
set search_path='pg_catalog','extensions','chlom_runtime'
as $$
declare w chlom_runtime.construction_work_queue%rowtype; v_key text; v_input text; v_id uuid; v_dail jsonb;
begin
  select * into w from chlom_runtime.construction_work_queue where work_id=p_work_id;
  if not found then raise exception 'BUILD_SOURCE_WORK_NOT_FOUND'; end if;
  if w.state<>'ready' then raise exception 'BUILD_SOURCE_WORK_NOT_READY:%',w.state; end if;
  if p_target_base_head !~ '^[0-9a-f]{40}$' then raise exception 'EXACT_TARGET_BASE_HEAD_REQUIRED'; end if;
  if w.owner_agent_id='ct.agent.execution-builder' or w.verifier_agent_id in(w.owner_agent_id,'ct.agent.execution-builder') then raise exception 'INDEPENDENT_REQUESTER_VERIFIER_REQUIRED'; end if;
  v_input:=jsonb_build_object('work_id',w.work_id,'scope_id',w.scope_id,'required_outputs',w.required_outputs,'target_repository',p_target_repository,'target_base_head',p_target_base_head)::text;
  v_key:='ct.build.'||encode(extensions.digest(convert_to(v_input,'UTF8'),'sha256'),'hex');
  insert into chlom_runtime.agent_build_requests(
    request_key,source_work_id,requester_agent_id,verifier_agent_id,target_repository,target_base_head,
    authority_ceiling,risk_class,build_scope,required_outputs,protected_input_refs,input_sha256
  ) values (
    v_key,w.work_id,w.owner_agent_id,w.verifier_agent_id,p_target_repository,p_target_base_head,
    'D2','D2',jsonb_build_object('workstream',w.workstream,'scope_type',w.scope_type,'scope_id',w.scope_id,'closes_gates',w.closes_gates),
    w.required_outputs,'[]'::jsonb,encode(extensions.digest(convert_to(v_input,'UTF8'),'sha256'),'hex')
  ) on conflict(request_key) do update set updated_at=now() returning request_id into v_id;
  v_dail:=chlom_runtime.append_dail_event('agent_build.request_routed','agent_build_request',v_id::text,
    jsonb_build_object('request_key',v_key,'source_work_id',w.work_id,'requester_agent_id',w.owner_agent_id,
      'executor_agent_id','ct.agent.execution-builder','verifier_agent_id',w.verifier_agent_id,
      'target_repository',p_target_repository,'target_base_head',p_target_base_head,'candidate_only',true,'certification_effect',false),
    'CrownThrive Execution Builder','did:ct:system:thrivebase','ct.agent.execution-builder','1.0.1',v_key,null,
    'D2 bounded materialization',null,'restricted');
  return jsonb_build_object('request_id',v_id,'request_key',v_key,'state','queued','executor_agent_id','ct.agent.execution-builder','dail',v_dail,'certification_effect',false);
end $$;
revoke all on function chlom_runtime.route_construction_work_to_execution_builder(text,text,text) from public,anon,authenticated;
grant execute on function chlom_runtime.route_construction_work_to_execution_builder(text,text,text) to service_role;

create or replace function chlom_runtime.route_capability_execution_to_execution_builder(
  p_queue_id uuid,p_target_repository text,p_target_base_head text
) returns jsonb
language plpgsql security definer
set search_path='pg_catalog','extensions','chlom_runtime','institutional_federation'
as $$
declare q institutional_federation.capability_execution_queue%rowtype; v_key text; v_input text; v_id uuid;
begin
  select * into q from institutional_federation.capability_execution_queue where queue_id=p_queue_id;
  if not found then raise exception 'CAPABILITY_EXECUTION_NOT_FOUND'; end if;
  if q.risk_class='D3' or q.requires_human then raise exception 'D3_OR_HUMAN_GATE_NOT_BUILDABLE'; end if;
  if q.execution_mode<>'agent_dispatch' or q.queue_state not in('queued','dispatched','running') then raise exception 'CAPABILITY_EXECUTION_NOT_BUILDABLE:%:%',q.execution_mode,q.queue_state; end if;
  if q.assigned_agent_id is null or q.verifier_agent_id is null or q.assigned_agent_id='ct.agent.execution-builder' or q.verifier_agent_id in(q.assigned_agent_id,'ct.agent.execution-builder') then raise exception 'INDEPENDENT_REQUESTER_VERIFIER_REQUIRED'; end if;
  if p_target_base_head !~ '^[0-9a-f]{40}$' then raise exception 'EXACT_TARGET_BASE_HEAD_REQUIRED'; end if;
  v_input:=jsonb_build_object('queue_id',q.queue_id,'capability_id',q.capability_id,'payload',q.payload,'target_repository',p_target_repository,'target_base_head',p_target_base_head)::text;
  v_key:='ct.build.'||encode(extensions.digest(convert_to(v_input,'UTF8'),'sha256'),'hex');
  insert into chlom_runtime.agent_build_requests(
    request_key,source_queue_id,requester_agent_id,verifier_agent_id,target_repository,target_base_head,
    authority_ceiling,risk_class,build_scope,required_outputs,protected_input_refs,input_sha256
  ) values (
    v_key,q.queue_id,q.assigned_agent_id,q.verifier_agent_id,p_target_repository,p_target_base_head,
    q.risk_class,q.risk_class,jsonb_build_object('capability_id',q.capability_id,'semantic_version',q.semantic_version,'execution_mode',q.execution_mode),
    q.payload,'[]'::jsonb,encode(extensions.digest(convert_to(v_input,'UTF8'),'sha256'),'hex')
  ) on conflict(request_key) do update set updated_at=now() returning request_id into v_id;
  return jsonb_build_object('request_id',v_id,'request_key',v_key,'state','queued','executor_agent_id','ct.agent.execution-builder','certification_effect',false);
end $$;
revoke all on function chlom_runtime.route_capability_execution_to_execution_builder(uuid,text,text) from public,anon,authenticated;
grant execute on function chlom_runtime.route_capability_execution_to_execution_builder(uuid,text,text) to service_role;

create or replace function chlom_runtime.complete_agent_build_request(
  p_request_id uuid,p_candidate_branch text,p_exact_head text,p_output_sha256 text,
  p_output_manifest jsonb,p_tests jsonb,p_rollback jsonb,p_custody jsonb
) returns jsonb
language plpgsql security definer
set search_path='pg_catalog','chlom_runtime'
as $$
declare r chlom_runtime.agent_build_requests%rowtype; v_receipt uuid; v_dail jsonb;
begin
  select * into r from chlom_runtime.agent_build_requests where request_id=p_request_id for update;
  if not found then raise exception 'BUILD_REQUEST_NOT_FOUND'; end if;
  if r.request_state not in('queued','claimed','building') then raise exception 'BUILD_REQUEST_NOT_COMPLETABLE:%',r.request_state; end if;
  if p_exact_head !~ '^[0-9a-f]{40}$' or p_output_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'EXACT_OUTPUT_BINDING_REQUIRED'; end if;
  insert into chlom_runtime.agent_build_receipts(request_id,verifier_agent_id,candidate_branch,exact_head,output_sha256,output_manifest,tests,rollback,custody)
  values(p_request_id,r.verifier_agent_id,p_candidate_branch,p_exact_head,p_output_sha256,p_output_manifest,p_tests,p_rollback,p_custody)
  returning receipt_id into v_receipt;
  update chlom_runtime.agent_build_requests set request_state='built_pending_verification',updated_at=now() where request_id=p_request_id;
  v_dail:=chlom_runtime.append_dail_event('agent_build.materialized','agent_build_request',p_request_id::text,
    jsonb_build_object('receipt_id',v_receipt,'executor_agent_id','ct.agent.execution-builder','verifier_agent_id',r.verifier_agent_id,
      'candidate_branch',p_candidate_branch,'exact_head',p_exact_head,'output_sha256',p_output_sha256,
      'state','BUILT_PENDING_INDEPENDENT_VERIFICATION','certification_effect',false,'sovereign_vote_created',false),
    'CrownThrive Execution Builder','did:ct:system:thrivebase','ct.agent.execution-builder','1.0.1',
    'agent-build:'||p_request_id::text,null,'D2 bounded materialization',null,'restricted');
  return jsonb_build_object('receipt_id',v_receipt,'request_id',p_request_id,'state','BUILT_PENDING_INDEPENDENT_VERIFICATION',
    'verifier_agent_id',r.verifier_agent_id,'dail',v_dail,'certification_effect',false,'sovereign_vote_created',false);
end $$;
revoke all on function chlom_runtime.complete_agent_build_request(uuid,text,text,text,jsonb,jsonb,jsonb,jsonb) from public,anon,authenticated;
grant execute on function chlom_runtime.complete_agent_build_request(uuid,text,text,text,jsonb,jsonb,jsonb,jsonb) to service_role;

select chlom_runtime.append_dail_event(
  'agent.execution_builder.institutionalized','agent','ct.agent.execution-builder',
  jsonb_build_object('parent_agent_id','ct.relay.agent-c','authority_ceiling','D2','vote_eligible',false,
    'quorum_eligible',false,'d3_human_reserved',true,'sole_mission','materialize bounded build requests',
    'manifest_sha256','b763604e2ecb28374ae7d8be7228ece566703e898900effcd6c6cb7fe4f0ea26',
    'completion_state','BUILT_PENDING_INDEPENDENT_VERIFICATION','certification_effect',false),
  'Kavonte Jones Sr. Founder Directive 2026-08-23','did:ct:founder:kavonte-jones-sr','ct.relay.agent-c','1.0.1',
  'execution-builder-agent-v1-20260823',null,'Founder directive: close agent-to-build execution gap without authority expansion',null,'restricted'
);

commit;
