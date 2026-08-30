-- Correct PentaSuper acceptance canary DND priority typing.
-- This is an implementation fix only; it does not certify production.

create or replace function penta_task_runtime.run_acceptance_canary_v2(p_actor_ref text default 'ct.relay.agent-c')
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','extensions','penta_task_runtime','penta_dnd','penta_translate','chlom_runtime'
as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_run uuid:=gen_random_uuid();
  v_scope text:='ct.penta.super.v1:acceptance:'||v_run::text;
  v_scope_other text:=v_scope||':unrelated';
  v_dnd jsonb;
  v_conflict jsonb;
  v_unrelated jsonb;
  v_snapshot jsonb;
  v_snapshot_id uuid;
  v_drift jsonb;
  v_restored jsonb;
  v_translate jsonb;
  v_decision jsonb;
  v_execution jsonb;
  v_pass boolean;
  v_before jsonb;
  v_after jsonb;
  v_assertions integer;
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;

  insert into penta_task_runtime.acceptance_runs_v1(run_id,state,actor_ref,source_ref)
  values(v_run,'running',p_actor_ref,'PR#1388/supabase/migrations/20260830084500_penta_super_acceptance_canary_fix_v1.sql');

  v_decision:=chlom_runtime.append_dail_event(
    'penta.super.task-runtime.acceptance.started','penta_super_acceptance',v_run::text,
    jsonb_build_object('scope',v_scope,'three_dail_logical_phase','DAIL-DECISION','production_certification',false),
    p_actor_ref,null,'PentaSuper','1.0.1','ctcorr:penta-super:acceptance:'||v_run::text,null,'D2',null,'internal'
  );

  v_dnd:=penta_dnd.open_lease_v2(
    'ct.program.penta-super-build-dnd','acceptance_canary',v_scope,p_actor_ref,
    'task runtime acceptance',60::smallint,900,'source_discovery','certify_hold_classify'
  );
  if coalesce((v_dnd->>'ok')::boolean,false)=false then raise exception 'acceptance_dnd_unavailable: %',v_dnd; end if;

  v_conflict:=penta_dnd.open_lease_v2(
    'ct.program.penta-super-build-dnd','acceptance_canary',v_scope,'ct.relay.agent-b',
    'collision canary',40::smallint,900,'source_discovery','certify_hold_classify'
  );
  v_unrelated:=penta_dnd.open_lease_v2(
    'ct.program.penta-super-build-dnd','acceptance_canary',v_scope_other,'ct.relay.agent-b',
    'unrelated continuity canary',40::smallint,900,'source_discovery','certify_hold_classify'
  );

  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed) values
    (v_run,'dnd_exact_scope_acquired',coalesce((v_dnd->>'ok')::boolean,false),v_dnd),
    (v_run,'dnd_conflicting_owner_blocked',coalesce((v_conflict->>'ok')::boolean,false)=false and v_conflict->>'state'='held_by_active_owner',v_conflict),
    (v_run,'dnd_unrelated_scope_continues',coalesce((v_unrelated->>'ok')::boolean,false),v_unrelated),
    (v_run,'dnd_ttl_bounded',(v_dnd->>'expires_at')::timestamptz<=clock_timestamp()+interval '16 minutes',jsonb_build_object('expires_at',v_dnd->>'expires_at','requested_seconds',900)),
    (v_run,'dnd_priority_attached',coalesce((v_dnd->>'priority')::integer,-1)=60,jsonb_build_object('priority',v_dnd->>'priority','preemption',false));

  select jsonb_build_object('canary_key',canary_key,'canary_value',canary_value,'generation',generation)
  into v_before from penta_task_runtime.restore_canary_v1 where canary_key='task-runtime';

  v_snapshot:=penta_task_runtime.capture_snapshot_v1(
    'restore_canary','penta_task_runtime.restore_canary_v1:task-runtime',v_before,
    jsonb_build_object('restore_to',v_before),'PentaSnapshot','D1','ctcorr:penta-super:restore-canary:'||v_run::text
  );
  v_snapshot_id:=(v_snapshot->>'snapshot_id')::uuid;

  update penta_task_runtime.restore_canary_v1
  set canary_value='mutated:'||v_run::text,generation=generation+1,updated_at=clock_timestamp()
  where canary_key='task-runtime';
  select jsonb_build_object('canary_key',canary_key,'canary_value',canary_value,'generation',generation)
  into v_after from penta_task_runtime.restore_canary_v1 where canary_key='task-runtime';
  v_drift:=penta_task_runtime.verify_snapshot_v1(v_snapshot_id,v_after);

  update penta_task_runtime.restore_canary_v1
  set canary_value=v_before->>'canary_value',generation=(v_before->>'generation')::bigint,updated_at=clock_timestamp()
  where canary_key='task-runtime';
  select jsonb_build_object('canary_key',canary_key,'canary_value',canary_value,'generation',generation)
  into v_after from penta_task_runtime.restore_canary_v1 where canary_key='task-runtime';
  v_restored:=penta_task_runtime.verify_snapshot_v1(v_snapshot_id,v_after);

  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed) values
    (v_run,'snapshot_captured',coalesce((v_snapshot->>'ok')::boolean,false),v_snapshot-'dail'),
    (v_run,'snapshot_drift_detected',coalesce((v_drift->>'matches_snapshot')::boolean,true)=false,v_drift),
    (v_run,'restore_canary_exact',coalesce((v_restored->>'matches_snapshot')::boolean,false),v_restored);

  v_translate:=penta_translate.run_round_trip_canary_v1(p_actor_ref);
  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed) values
    (v_run,'translate_transport_round_trip',coalesce((v_translate->>'round_trip_verified')::boolean,false),v_translate-'record'),
    (v_run,'translate_transport_no_confidentiality_claim',coalesce((v_translate->>'confidentiality')::boolean,true)=false,jsonb_build_object('confidentiality',v_translate->'confidentiality'));

  if coalesce(v_unrelated->>'lease_id','')<>'' then
    perform penta_dnd.close_lease_v1((v_unrelated->>'lease_id')::uuid,'acceptance_unrelated_complete');
  end if;
  if coalesce(v_dnd->>'lease_id','')<>'' then
    perform penta_dnd.close_lease_v1((v_dnd->>'lease_id')::uuid,'acceptance_complete');
  end if;

  select bool_and(passed),count(*) into v_pass,v_assertions
  from penta_task_runtime.acceptance_assertions_v1 where run_id=v_run;

  v_execution:=chlom_runtime.append_dail_event(
    'penta.super.task-runtime.acceptance.completed','penta_super_acceptance',v_run::text,
    jsonb_build_object('passed',coalesce(v_pass,false),'assertion_count',v_assertions,'snapshot_id',v_snapshot_id,'three_dail_logical_phase','DAIL-EXECUTION','production_certification',false),
    p_actor_ref,null,'PentaSuper','1.0.1','ctcorr:penta-super:acceptance:'||v_run::text,v_decision->>'event_id','D2',null,'internal'
  );

  update penta_task_runtime.acceptance_runs_v1
  set state=case when v_pass then 'pass' else 'fail' end,
      snapshot_id=v_snapshot_id,
      dnd_lease_id=(v_dnd->>'lease_id')::uuid,
      decision_dail_event_id=(v_decision->>'event_id')::uuid,
      execution_dail_event_id=(v_execution->>'event_id')::uuid,
      evidence=jsonb_build_object('translation_projection_id',v_translate#>>'{record,projection_id}','independent_certification_required',true,'production_certified',false)
  where run_id=v_run;

  return jsonb_build_object('ok',coalesce(v_pass,false),'run_id',v_run,'assertion_count',v_assertions,'state',case when v_pass then 'pass' else 'fail' end,'snapshot_id',v_snapshot_id,'dail_decision',v_decision,'dail_execution',v_execution,'production_certified',false);
exception when others then
  begin
    if coalesce(v_unrelated->>'lease_id','')<>'' then perform penta_dnd.close_lease_v1((v_unrelated->>'lease_id')::uuid,'acceptance_exception'); end if;
    if coalesce(v_dnd->>'lease_id','')<>'' then perform penta_dnd.close_lease_v1((v_dnd->>'lease_id')::uuid,'acceptance_exception'); end if;
  exception when others then null; end;
  update penta_task_runtime.acceptance_runs_v1
  set state='fail',evidence=jsonb_build_object('error_class',sqlstate,'error_message',left(sqlerrm,400),'production_certified',false)
  where run_id=v_run and state='running';
  raise;
end;
$$;

select chlom_runtime.append_dail_event(
  'penta.super.acceptance-canary.fix.installed','penta_super_runtime','ct.penta.task-runtime-family.v1',
  jsonb_build_object('fix','explicit_smallint_priority_casts','acceptance_runtime','penta_task_runtime.run_acceptance_canary_v2','three_dail_logical_phase','DAIL-EXECUTION','independent_certification_required',true,'production_certified',false),
  'ct.relay.agent-c',null,'ct.relay.agent-c','1.0.1','ctcorr:penta-super:acceptance-fix-v1',null,'D2',null,'internal'
);