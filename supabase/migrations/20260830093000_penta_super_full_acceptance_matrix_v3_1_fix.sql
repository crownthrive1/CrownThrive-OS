-- PentaSuper full acceptance matrix v3.1 repair.
-- Root cause: v3 used an unsupported collision target_kind and referenced
-- explicit acceptance workers that were not registered in the agent template fabric.
-- This patch does not weaken collision constraints. It registers bounded non-voting
-- canary actors and rewrites only the two v3 target-kind argument literals.

insert into chlom_runtime.agent_templates(
  agent_id,parent_agent_id,canonical_name,agent_class,autonomy_class,authority_ceiling,
  lifecycle_state,module_scope,tool_scope,schedule_profile,vote_eligible,
  self_healing_enabled,no_self_approval,heartbeat_ttl_seconds,metadata
) values
(
  'ct.automation.penta-super-build',null,'PentaSuper Temporary Build Executor','builder','A1','D2',
  'active',array['ct.penta.super.v1'],
  jsonb_build_object('read',true,'write','governed_candidate_only','merge',false,'deploy',false,'provider_write',false),
  'external_temporary',false,false,true,3600,
  jsonb_build_object(
    'temporary_external_builder',true,
    'retire_with_build_clock',true,
    'no_vote_effect',true,
    'no_quorum_effect',true,
    'd3_human_reserved',true,
    'no_self_certification',true,
    'no_credential_operation',true,
    'no_money_movement',true,
    'source_pr',1388,
    'source_ref','supabase/migrations/20260830093000_penta_super_full_acceptance_matrix_v3_1_fix.sql'
  )
),
(
  'ct.penta.super.acceptance.worker-a','ct.automation.penta-super-build','PentaSuper Acceptance Canary Worker A','other','A0','D1',
  'test',array['ct.penta.super.v1'],
  jsonb_build_object('read',true,'write','synthetic_acceptance_state_only','merge',false,'deploy',false,'provider_write',false),
  'none',false,false,true,3600,
  jsonb_build_object('acceptance_canary_only',true,'synthetic_actor',true,'no_vote_effect',true,'no_quorum_effect',true,'d3_human_reserved',true,'production_authority',false,'source_pr',1388)
),
(
  'ct.penta.super.acceptance.worker-b','ct.automation.penta-super-build','PentaSuper Acceptance Canary Worker B','other','A0','D1',
  'test',array['ct.penta.super.v1'],
  jsonb_build_object('read',true,'write','synthetic_acceptance_state_only','merge',false,'deploy',false,'provider_write',false),
  'none',false,false,true,3600,
  jsonb_build_object('acceptance_canary_only',true,'synthetic_actor',true,'no_vote_effect',true,'no_quorum_effect',true,'d3_human_reserved',true,'production_authority',false,'source_pr',1388)
)
on conflict(agent_id) do update set
  canonical_name=excluded.canonical_name,
  agent_class=excluded.agent_class,
  autonomy_class=excluded.autonomy_class,
  authority_ceiling=excluded.authority_ceiling,
  lifecycle_state=excluded.lifecycle_state,
  module_scope=excluded.module_scope,
  tool_scope=excluded.tool_scope,
  schedule_profile=excluded.schedule_profile,
  vote_eligible=false,
  self_healing_enabled=false,
  no_self_approval=true,
  metadata=chlom_runtime.agent_templates.metadata||excluded.metadata,
  updated_at=clock_timestamp();

do $penta_super_acceptance_fix$
declare
  v_def text;
  v_fixed text;
  v_needle text := ',''acceptance_canary'',''penta-super-task-runtime''';
  v_replacement text := ',''runtime_packet'',''penta-super-task-runtime''';
  v_occurrences integer;
begin
  select pg_get_functiondef('penta_task_runtime.run_full_acceptance_matrix_v3(text)'::regprocedure)
    into v_def;

  v_occurrences := (length(v_def)-length(replace(v_def,v_needle,'')))/length(v_needle);
  if v_occurrences <> 2 then
    raise exception 'unexpected_acceptance_target_literal_count:%',v_occurrences;
  end if;

  v_fixed := replace(v_def,v_needle,v_replacement);
  execute v_fixed;
end
$penta_super_acceptance_fix$;

select chlom_runtime.append_dail_event(
  'penta.super.full-acceptance-matrix.v3_1.fixed',
  'penta_super_runtime',
  'ct.penta.task-runtime-family.v1',
  jsonb_build_object(
    'root_cause','unsupported collision target_kind plus unregistered synthetic canary actors',
    'fix','register bounded non-voting canary identities and map only synthetic collision target arguments to runtime_packet',
    'collision_constraint_weakened',false,
    'production_certified',false,
    'independent_certification_required',true,
    'three_dail_logical_phase','DAIL-EXECUTION',
    'source_pr',1388
  ),
  'ct.automation.penta-super-build',null,'PentaSuper','1.0.3',
  'ctcorr:penta-super:full-matrix-v3-1-fix',null,'D2',null,'internal'
);
