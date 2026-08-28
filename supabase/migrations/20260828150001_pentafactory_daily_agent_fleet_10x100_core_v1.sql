-- Fragment 1/5: schema, policy, shared Agent D guard, PentaGovernance suite and authority registry.
create table if not exists public.pentafactory_daily_fleet_policy_v1(
  policy_id text primary key,
  enabled boolean not null default true,
  parent_quota int not null check(parent_quota=10),
  subagent_quota int not null check(subagent_quota=100),
  subagents_per_parent int not null check(subagents_per_parent=10),
  retention_days int not null check(retention_days between 1 and 365),
  timezone text not null default 'America/New_York',
  start_date date not null,
  shared_sidecar_id text not null,
  d3_human_reserved boolean not null default true check(d3_human_reserved),
  source_ref text not null,
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.pentafactory_daily_fleet_runs_v1(
  production_date date primary key,
  run_id uuid not null default extensions.gen_random_uuid(),
  policy_id text not null references public.pentafactory_daily_fleet_policy_v1(policy_id),
  state text not null check(state in('running','pass','hold','failed')),
  parent_count int not null default 0,
  subagent_count int not null default 0,
  receipt_count int not null default 0,
  receipt_sha256 text check(receipt_sha256 is null or receipt_sha256~'^[0-9a-f]{64}$'),
  error text,
  started_at timestamptz not null default clock_timestamp(),
  finished_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.pentafactory_daily_fleet_entities_v1(
  entity_ref text primary key,
  production_date date not null,
  policy_id text not null references public.pentafactory_daily_fleet_policy_v1(policy_id),
  entity_kind text not null check(entity_kind in('parent_agent','subagent')),
  parent_entity_ref text references public.pentafactory_daily_fleet_entities_v1(entity_ref),
  parent_seq int not null check(parent_seq between 1 and 10),
  subagent_seq int check(subagent_seq is null or subagent_seq between 1 and 10),
  lane_key text not null,
  canonical_name text not null,
  agent_class text not null,
  autonomy_class text not null check(autonomy_class in('A1','A2')),
  authority_ceiling text not null check(authority_ceiling in('D1','D2')),
  lifecycle_state text not null default 'active' check(lifecycle_state in('active','retired','failed')),
  activated_at timestamptz not null default clock_timestamp(),
  retirement_due_at timestamptz not null,
  retired_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  check((entity_kind='parent_agent' and parent_entity_ref is null and subagent_seq is null)
     or (entity_kind='subagent' and parent_entity_ref is not null and subagent_seq is not null))
);
create unique index if not exists pentafactory_daily_fleet_parent_slot_uq
  on public.pentafactory_daily_fleet_entities_v1(production_date,parent_seq) where entity_kind='parent_agent';
create unique index if not exists pentafactory_daily_fleet_sub_slot_uq
  on public.pentafactory_daily_fleet_entities_v1(production_date,parent_seq,subagent_seq) where entity_kind='subagent';
create index if not exists pentafactory_daily_fleet_retire_idx
  on public.pentafactory_daily_fleet_entities_v1(lifecycle_state,retirement_due_at);

create table if not exists public.pentafactory_daily_fleet_receipts_v1(
  entity_ref text not null references public.pentafactory_daily_fleet_entities_v1(entity_ref),
  layer_key text not null,
  decision text not null check(decision in('pass','hold','fail')),
  evidence jsonb not null,
  evidence_sha256 text not null check(evidence_sha256~'^[0-9a-f]{64}$'),
  created_at timestamptz not null default clock_timestamp(),
  primary key(entity_ref,layer_key)
);

alter table public.pentafactory_daily_fleet_policy_v1 enable row level security;
alter table public.pentafactory_daily_fleet_runs_v1 enable row level security;
alter table public.pentafactory_daily_fleet_entities_v1 enable row level security;
alter table public.pentafactory_daily_fleet_receipts_v1 enable row level security;
revoke all on public.pentafactory_daily_fleet_policy_v1,public.pentafactory_daily_fleet_runs_v1,
  public.pentafactory_daily_fleet_entities_v1,public.pentafactory_daily_fleet_receipts_v1 from public,anon,authenticated;
grant select,update on public.pentafactory_daily_fleet_policy_v1 to service_role;
grant select on public.pentafactory_daily_fleet_runs_v1,public.pentafactory_daily_fleet_entities_v1,
  public.pentafactory_daily_fleet_receipts_v1 to service_role;

insert into public.pentafactory_daily_fleet_policy_v1(
  policy_id,enabled,parent_quota,subagent_quota,subagents_per_parent,retention_days,timezone,start_date,
  shared_sidecar_id,d3_human_reserved,source_ref,metadata
) values(
  'ct.pentafactory.daily-agent-fleet.10x100.v1',true,10,100,10,30,'America/New_York','2026-08-28',
  'ct.subagent.d-surrogate.ct-agent-factory-orchestrator',true,
  'supabase/migrations/20260828150000_pentafactory_daily_agent_fleet_10x100_v1.sql',
  jsonb_build_object(
    'state','production_active','orchestrator','ct.agent.factory.orchestrator',
    'verifier','ct.agent.factory.independent-verification','enforcer','ct.agent.penta-police',
    'charter','penta.charter.democratic-governance.v1',
    'branches',jsonb_build_array('penta.branch.legislative','penta.branch.executive','penta.branch.judicial'),
    'layers',jsonb_build_array('penta-governance','chlom-authority','penta-police','penta-build','penta-certify','penta-nurture','penta-release'),
    'nonvoting',true,'no_vote_proxy',true,'no_quorum_effect',true,'no_authority_inheritance',true,
    'no_recursive_spawn',true,'no_self_approval',true,'no_silent_delete',true,'no_direct_main_write',true,
    'no_merge',true,'no_deploy',true,'no_publish',true,'no_provider_write',true,'no_money_movement',true,
    'no_rights_grant',true,'no_credential_export',true,'d3_human_reserved',true,'retirement','non_destructive'
  )
) on conflict(policy_id) do update set
  enabled=true,parent_quota=10,subagent_quota=100,subagents_per_parent=10,retention_days=30,
  timezone=excluded.timezone,start_date=excluded.start_date,shared_sidecar_id=excluded.shared_sidecar_id,
  d3_human_reserved=true,source_ref=excluded.source_ref,metadata=pentafactory_daily_fleet_policy_v1.metadata||excluded.metadata,
  updated_at=now();

-- Preserve the existing Agent D auto-sidecar function. The trigger skips it only for
-- this exact nonvoting D0-D2 factory contract using the verified shared factory sidecar.
drop trigger if exists trg_provision_agent_d_sidecar_v1 on chlom_runtime.agent_templates;
create trigger trg_provision_agent_d_sidecar_v1
after insert on chlom_runtime.agent_templates
for each row when(
  new.metadata->>'agent_d_sidecar_mode' is distinct from 'shared'
  or new.metadata->>'factory_policy_id' is distinct from 'ct.pentafactory.daily-agent-fleet.10x100.v1'
  or new.metadata->>'suite_id' is distinct from 'ct.agent-suite.pentafactory-daily-fleet.v1'
  or new.metadata->>'agent_d_sidecar_id' is distinct from 'ct.subagent.d-surrogate.ct-agent-factory-orchestrator'
  or new.vote_eligible is distinct from false
  or new.no_self_approval is distinct from true
  or new.authority_ceiling='D3'
)
execute function chlom_runtime.provision_agent_d_sidecar_v1();

create or replace function public.pentafactory_force_nonvoting_membership_v1()
returns trigger language plpgsql set search_path='pg_catalog','public' as $f$
begin
  if new.subject_ref like 'ct.agent.factory.daily.%' or new.subject_ref like 'ct.subagent.factory.daily.%' then
    new.branch_key:=null; new.civic_role:='observer'; new.vote_weight:=1;
    if new.voting_status not in('suspended','expired') then new.voting_status:='nonvoting'; end if;
    new.metadata:=coalesce(new.metadata,'{}')||jsonb_build_object(
      'factory_policy_id','ct.pentafactory.daily-agent-fleet.10x100.v1','nonvoting',true,
      'no_vote_proxy',true,'no_quorum_effect',true,'no_authority_inheritance',true,'d3_human_reserved',true);
  end if;
  return new;
end $f$;
drop trigger if exists trg_pentafactory_force_nonvoting_membership_v1 on public.penta_governance_memberships;
create trigger trg_pentafactory_force_nonvoting_membership_v1
before insert or update on public.penta_governance_memberships
for each row execute function public.pentafactory_force_nonvoting_membership_v1();

with m as(select jsonb_build_object(
  'suite_id','ct.agent-suite.pentafactory-daily-fleet.v1','version','1.0.0','policy_id','ct.pentafactory.daily-agent-fleet.10x100.v1',
  'parents_per_day',10,'subagents_per_day',100,'subagents_per_parent',10,'retention_days',30,'timezone','America/New_York',
  'authority_ceiling','D2','nonvoting',true,'d3_human_reserved',true,
  'shared_sidecar_id','ct.subagent.d-surrogate.ct-agent-factory-orchestrator') snapshot)
insert into chlom_runtime.agent_suite_registry(
  suite_id,semantic_version,canonical_name,release_state,manifest_ref,manifest_sha256,parent_agent_id,parent_certifier_id,
  vote_eligible,quorum_eligible,d3_human_reserved,no_self_approval,no_silent_delete,drive_custody_required,
  supabase_storage_required,vault_secret_ref,source_ids,metadata
)
select 'ct.agent-suite.pentafactory-daily-fleet.v1','1.0.0','PentaFactory Daily Governed Fleet 10x100','active',
  'supabase/migrations/20260828150000_pentafactory_daily_agent_fleet_10x100_v1.sql',
  encode(extensions.digest(convert_to(snapshot::text,'UTF8'),'sha256'),'hex'),
  'ct.agent.factory.orchestrator','ct.agent.factory.independent-verification',false,false,true,true,true,true,true,
  'vault://internal/pentafactory-daily-agent-fleet-v1',
  array['founder-directive:2026-08-28:10x100','thrivebase:pentafactory-daily-agent-fleet-v1']::text[],snapshot
from m on conflict(suite_id) do update set
  semantic_version=excluded.semantic_version,canonical_name=excluded.canonical_name,release_state='active',
  manifest_ref=excluded.manifest_ref,manifest_sha256=excluded.manifest_sha256,parent_agent_id=excluded.parent_agent_id,
  parent_certifier_id=excluded.parent_certifier_id,vote_eligible=false,quorum_eligible=false,d3_human_reserved=true,
  no_self_approval=true,no_silent_delete=true,drive_custody_required=true,supabase_storage_required=true,
  vault_secret_ref=excluded.vault_secret_ref,source_ids=excluded.source_ids,metadata=agent_suite_registry.metadata||excluded.metadata,
  updated_at=now();

with c as(select jsonb_build_object(
  'control_id','ct.pentafactory.daily-agent-fleet.10x100.v1','family','ct.pentafactory.daily-agent-fleet','version','1.0.0',
  'policy_id','ct.pentafactory.daily-agent-fleet.10x100.v1','suite_id','ct.agent-suite.pentafactory-daily-fleet.v1',
  'authority_model','autonomous_exact_evidence_d0_d2_human_d3','risk_ceiling','D2','d3_human_reserved',true,
  'charter','penta.charter.democratic-governance.v1','parents_per_day',10,'subagents_per_day',100,'nonvoting',true) snapshot)
insert into integration_control.penta_control_authority_registry_v1(
  control_id,control_family,semantic_version,control_kind,authority_model,state,risk_ceiling,effective_at,
  source_ref,control_snapshot,control_sha256,registered_by_agent_id,metadata
)
select 'ct.pentafactory.daily-agent-fleet.10x100.v1','ct.pentafactory.daily-agent-fleet','1.0.0',
  'production_runtime_policy','autonomous_exact_evidence_d0_d2_human_d3','current','D2',clock_timestamp(),
  'supabase/migrations/20260828150000_pentafactory_daily_agent_fleet_10x100_v1.sql',snapshot,
  encode(extensions.digest(convert_to(snapshot::text,'UTF8'),'sha256'),'hex'),'ct.agent.penta-police',
  jsonb_build_object('state','production_active','receipt_layers_per_entity',7,'external_scheduler_slot_delta',0,
    'money_movement',false,'checkout_activation',false,'d3_human_reserved',true)
from c on conflict(control_id) do update set
  state='current',risk_ceiling='D2',effective_at=excluded.effective_at,source_ref=excluded.source_ref,
  control_snapshot=excluded.control_snapshot,control_sha256=excluded.control_sha256,
  registered_by_agent_id=excluded.registered_by_agent_id,metadata=penta_control_authority_registry_v1.metadata||excluded.metadata,
  updated_at=now();
