begin;

-- PentaSuper consumes canonical PentaDND; it never creates DND leases for acceptance.
-- Preserve existing public function identities while correcting their runtime semantics.

create or replace function penta_task_runtime.run_acceptance_canary_v2(
  p_actor_ref text default 'ct.relay.agent-c'
) returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','extensions','penta_task_runtime','penta_dnd','penta_translate','chlom_runtime'
as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_run uuid:=gen_random_uuid();
  v_scope text:='ct.penta.super.v1:acceptance-consumer:'||v_run::text;
  v_snapshot jsonb;
  v_snapshot_id uuid;
  v_drift jsonb;
  v_restored jsonb;
  v_translate jsonb;
  v_decision jsonb;
  v_execution jsonb;
  v_dnd_preflight jsonb;
  v_pass boolean;
  v_before jsonb;
  v_after jsonb;
  v_assertions integer;
  v_dnd_rows_before integer;
  v_dnd_rows_after integer;
begin
  if session_user<>'postgres' and v_role<>'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  select count(*) into v_dnd_rows_before
  from penta_dnd.leases_v1
  where program_id ilike '%penta-super%' or scope_ref like 'ct.penta.super.v1:acceptance%';

  insert into penta_task_runtime.acceptance_runs_v1(run_id,state,actor_ref,source_ref)
  values(v_run,'running',p_actor_ref,'supabase/migrations/20260830205300_penta_super_dnd_consumer_boundary_acceptance_v4.sql');

  v_decision:=chlom_runtime.append_dail_event(
    'penta.super.task-runtime.acceptance.started','penta_super_acceptance',v_run::text,
    jsonb_build_object(
      'scope',v_scope,
      'three_dail_logical_phase','DAIL-DECISION',
      'production_certification',false,
      'penta_dnd_mode','consumer_only',
      'penta_dnd_owner','Penta Activation/System Architecture'
    ),
    p_actor_ref,null,'PentaSuper','1.0.3','ctcorr:penta-super:acceptance:'||v_run::text,null,'D2',null,'internal'
  );

  -- Read-only DND interoperability check. No lease is opened, renewed, altered, or closed.
  v_dnd_preflight:=penta_dnd.preflight_v1(
    'penta_super_acceptance_consumer',v_scope,p_actor_ref,'dnd.scope',false,false,false
  );

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

  v_translate:=penta_translate.run_round_trip_canary_v1(p_actor_ref);

  select count(*) into v_dnd_rows_after
  from penta_dnd.leases_v1
  where program_id ilike '%penta-super%' or scope_ref like 'ct.penta.super.v1:acceptance%';

  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed) values
    (v_run,'dnd_consumer_read_only_preflight',
      coalesce((v_dnd_preflight->>'allowed')::boolean,false)
      and v_dnd_preflight->>'decision'='PASS_NO_DND_SCOPE',v_dnd_preflight),
    (v_run,'dnd_consumer_does_not_activate',
      v_dnd_rows_after=v_dnd_rows_before,
      jsonb_build_object('before',v_dnd_rows_before,'after',v_dnd_rows_after,'dnd_activated_by_pentasuper',false)),
    (v_run,'snapshot_captured',coalesce((v_snapshot->>'ok')::boolean,false),v_snapshot-'dail'),
    (v_run,'snapshot_drift_detected',coalesce((v_drift->>'matches_snapshot')::boolean,true)=false,v_drift),
    (v_run,'restore_canary_exact',coalesce((v_restored->>'matches_snapshot')::boolean,false),v_restored),
    (v_run,'translate_transport_round_trip',coalesce((v_translate->>'round_trip_verified')::boolean,false),v_translate-'record'),
    (v_run,'translate_transport_no_confidentiality_claim',coalesce((v_translate->>'confidentiality')::boolean,true)=false,jsonb_build_object('confidentiality',v_translate->'confidentiality'));

  select bool_and(passed),count(*) into v_pass,v_assertions
  from penta_task_runtime.acceptance_assertions_v1 where run_id=v_run;

  v_execution:=chlom_runtime.append_dail_event(
    'penta.super.task-runtime.acceptance.completed','penta_super_acceptance',v_run::text,
    jsonb_build_object(
      'passed',coalesce(v_pass,false),
      'assertion_count',v_assertions,
      'snapshot_id',v_snapshot_id,
      'three_dail_logical_phase','DAIL-EXECUTION',
      'production_certification',false,
      'penta_dnd_activated',false,
      'penta_dnd_mode','consumer_only'
    ),
    p_actor_ref,null,'PentaSuper','1.0.3','ctcorr:penta-super:acceptance:'||v_run::text,v_decision->>'event_id','D2',null,'internal'
  );

  update penta_task_runtime.acceptance_runs_v1
  set state=case when v_pass then 'pass' else 'fail' end,
      snapshot_id=v_snapshot_id,
      dnd_lease_id=null,
      decision_dail_event_id=(v_decision->>'event_id')::uuid,
      execution_dail_event_id=(v_execution->>'event_id')::uuid,
      evidence=jsonb_build_object(
        'translation_projection_id',v_translate#>>'{record,projection_id}',
        'independent_certification_required',true,
        'production_certified',false,
        'penta_dnd_mode','consumer_only',
        'penta_dnd_activated',false
      )
  where run_id=v_run;

  return jsonb_build_object(
    'ok',coalesce(v_pass,false),'run_id',v_run,'assertion_count',v_assertions,
    'state',case when v_pass then 'pass' else 'fail' end,'snapshot_id',v_snapshot_id,
    'dail_decision',v_decision,'dail_execution',v_execution,
    'penta_dnd_activated',false,'production_certified',false
  );
exception when others then
  update penta_task_runtime.acceptance_runs_v1
  set state='fail',evidence=jsonb_build_object(
    'error_class',sqlstate,'error_message',left(sqlerrm,400),
    'production_certified',false,'penta_dnd_activated',false
  )
  where run_id=v_run and state='running';
  raise;
end;
$$;

create or replace function penta_task_runtime.run_full_acceptance_matrix_v3(
  p_actor_ref text default 'ct.automation.penta-super-build'
) returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','extensions','public','penta_task_runtime','penta_translate','institutional_federation','penta_dnd','chlom_runtime'
as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_run uuid:=gen_random_uuid();
  v_corr text:='ctcorr:penta-super:full-matrix:'||v_run::text;
  v_decision jsonb;
  v_execution jsonb;
  v_baseline jsonb;
  v_dnd_preflight jsonb;
  v_dnd_registry_ok boolean:=false;
  v_dnd_rows_before integer;
  v_dnd_rows_after integer;
  v_t1 jsonb; v_t2 jsonb;
  v_protected_rejected boolean:=false; v_protected_error text;
  v_intent_a uuid:=gen_random_uuid(); v_intent_b uuid:=gen_random_uuid();
  v_inst_a uuid:=gen_random_uuid(); v_inst_b uuid:=gen_random_uuid();
  v_col_corr uuid:=gen_random_uuid();
  v_base_sha text:='f6c0a2927ffceb1e19950fb796b234174361d863';
  v_head_sha text:='3f7aaeb7a9b857cefadb5170884b8c111222c45f';
  v_wrong_head text:='3333333333333333333333333333333333333333';
  v_domain text:='ct.penta.super.acceptance.domain:'||v_run::text;
  v_domain_exp text:=v_domain||':expiry';
  v_la jsonb; v_lr jsonb; v_lrelease jsonb; v_exp_la jsonb; v_exp_lb jsonb;
  v_race_blocked boolean:=false; v_head_mismatch_rejected boolean:=false;
  v_stale_fence_rejected boolean:=false; v_rogue_write_blocked boolean:=false;
  v_fence bigint;
  v_dail_chain boolean:=false; v_census_count integer:=0; v_authority_ok boolean:=false;
  v_pass boolean:=false; v_assertions integer:=0;
  v_hash_a text; v_hash_b text; v_hash_c text; v_hash_d text;
begin
  if session_user<>'postgres' and v_role<>'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  select count(*) into v_dnd_rows_before
  from penta_dnd.leases_v1
  where program_id ilike '%penta-super%' or scope_ref like 'ct.penta.super.v1:acceptance%';

  insert into penta_task_runtime.acceptance_runs_v1(run_id,state,actor_ref,source_ref)
  values(v_run,'running',p_actor_ref,'supabase/migrations/20260830205300_penta_super_dnd_consumer_boundary_acceptance_v4.sql');

  v_decision:=chlom_runtime.append_dail_event(
    'penta.super.task-runtime.full-matrix.started','penta_super_acceptance',v_run::text,
    jsonb_build_object(
      'three_dail_logical_phase','DAIL-DECISION','production_certification',false,
      'matrix_version','v4-consumer-boundary','penta_dnd_mode','consumer_only'
    ),
    p_actor_ref,null,'PentaSuper','1.0.3',v_corr,null,'D2',null,'internal'
  );

  v_baseline:=penta_task_runtime.run_acceptance_canary_v2(p_actor_ref);
  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed)
  values(v_run,'baseline_v2_pass',coalesce((v_baseline->>'ok')::boolean,false),v_baseline);

  -- DND is observed only. No PentaSuper acceptance lease is created.
  v_dnd_preflight:=penta_dnd.preflight_v1(
    'penta_super_full_acceptance_consumer','ct.penta.super.v1:full-matrix-consumer:'||v_run::text,
    p_actor_ref,'dnd.scope',false,false,false
  );
  select exists(
    select 1 from public.penta_system_registry
    where system_key='penta.dnd'
      and metadata->>'canonical_id'='penta.dnd'
      and metadata->>'not_child_of_penta_super'='true'
      and metadata->>'activation_mode'='explicit_on_demand'
      and metadata->>'global_maintenance_mode'='false'
      and metadata->>'scheduler_tick_creates_lease'='false'
  ) into v_dnd_registry_ok;

  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed) values
    (v_run,'dnd_consumer_boundary_registered',v_dnd_registry_ok,jsonb_build_object('canonical_identity','penta.dnd','owner','Penta Activation/System Architecture')),
    (v_run,'dnd_consumer_preflight_without_activation',coalesce((v_dnd_preflight->>'allowed')::boolean,false) and v_dnd_preflight->>'decision'='PASS_NO_DND_SCOPE',v_dnd_preflight);

  -- PentaTranslate: reversible transport/idempotency/non-leakage.
  v_t1:=penta_translate.run_round_trip_canary_v1(p_actor_ref);
  v_t2:=penta_translate.run_round_trip_canary_v1(p_actor_ref);
  begin
    perform penta_translate.record_projection_v1(
      'ct.penta.translate.protected-rejection:'||v_run::text,
      'internal://penta-translate/protected-canary/source',repeat('a',64),
      'internal://penta-translate/protected-canary/projection',repeat('b',64),
      'en','penta-machine','machine','ct.penta.translate.project.v1','ct.penta.translate.synthetic-rejection.v1',false,null,'restricted',
      jsonb_build_object('secret','synthetic-canary-value'),'PentaTranslateVerify',v_corr
    );
  exception when others then
    v_protected_error:=left(sqlerrm,240);
    v_protected_rejected:=position('protected_material_rejected' in sqlerrm)>0;
  end;
  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed) values
    (v_run,'translate_duplicate_idempotency',v_t1#>>'{record,projection_id}'=v_t2#>>'{record,projection_id}',jsonb_build_object('first',v_t1#>>'{record,projection_id}','second',v_t2#>>'{record,projection_id}')),
    (v_run,'translate_protected_material_rejected',v_protected_rejected and not exists(select 1 from penta_translate.projections_v1 where idempotency_key='ct.penta.translate.protected-rejection:'||v_run::text),jsonb_build_object('rejected',v_protected_rejected,'error_class',v_protected_error)),
    (v_run,'translate_source_body_not_stored',not exists(select 1 from information_schema.columns where table_schema='penta_translate' and table_name='projections_v1' and column_name in ('source_body','raw_source','cipher_map','raw_mapping')),jsonb_build_object('immutable_source_by_hash',true,'body_column_absent',true));

  -- PentaLease/PentaCollision own TTL/race/CAS/fencing/stale-owner acceptance.
  v_hash_a:=encode(extensions.digest(convert_to('penta-super-acceptance-executable-a|'||v_run::text,'UTF8'),'sha256'),'hex');
  v_hash_b:=encode(extensions.digest(convert_to('penta-super-acceptance-config|'||v_run::text,'UTF8'),'sha256'),'hex');
  v_hash_c:=encode(extensions.digest(convert_to('penta-super-acceptance-policy|'||v_run::text,'UTF8'),'sha256'),'hex');
  v_hash_d:=encode(extensions.digest(convert_to('penta-super-acceptance-intent-a|'||v_run::text,'UTF8'),'sha256'),'hex');
  perform institutional_federation.register_collision_intent_v2(v_intent_a,'crownthrive1/CrownThrive-OS','runtime_packet','penta-super-task-runtime','ct.penta.super.acceptance.worker-a',v_inst_a,v_base_sha,v_head_sha,v_hash_a,v_hash_b,v_hash_c,v_hash_d,v_col_corr,'D1',jsonb_build_array(jsonb_build_object('capability','acceptance_canary')),jsonb_build_object('canary',true,'run_id',v_run));
  v_hash_a:=encode(extensions.digest(convert_to('penta-super-acceptance-executable-b|'||v_run::text,'UTF8'),'sha256'),'hex');
  v_hash_d:=encode(extensions.digest(convert_to('penta-super-acceptance-intent-b|'||v_run::text,'UTF8'),'sha256'),'hex');
  perform institutional_federation.register_collision_intent_v2(v_intent_b,'crownthrive1/CrownThrive-OS','runtime_packet','penta-super-task-runtime','ct.penta.super.acceptance.worker-b',v_inst_b,v_base_sha,v_head_sha,v_hash_a,v_hash_b,v_hash_c,v_hash_d,v_col_corr,'D1',jsonb_build_array(jsonb_build_object('capability','acceptance_canary')),jsonb_build_object('canary',true,'run_id',v_run));

  v_la:=institutional_federation.acquire_collision_domain_lease_v2(v_domain,'ct.penta.super.acceptance.worker-a',v_inst_a,v_intent_a,v_base_sha,v_head_sha,300,v_col_corr);
  v_fence:=(v_la->>'fence_token')::bigint;
  begin
    perform institutional_federation.acquire_collision_domain_lease_v2(v_domain,'ct.penta.super.acceptance.worker-b',v_inst_b,v_intent_b,v_base_sha,v_head_sha,300,v_col_corr);
  exception when others then
    v_race_blocked:=position('collision_domain_already_leased' in sqlerrm)>0 or sqlstate='55P03';
  end;
  v_lr:=institutional_federation.renew_collision_domain_lease_v2((v_la->>'lease_id')::uuid,v_inst_a,v_fence,v_base_sha,v_head_sha,300,v_col_corr);
  begin
    perform institutional_federation.renew_collision_domain_lease_v2((v_la->>'lease_id')::uuid,v_inst_a,v_fence,v_base_sha,v_wrong_head,300,v_col_corr);
  exception when others then
    v_head_mismatch_rejected:=position('collision_lease_version_mismatch' in sqlerrm)>0;
  end;
  begin
    perform institutional_federation.release_collision_domain_lease_v2((v_la->>'lease_id')::uuid,v_inst_a,v_fence+1,'CANARY_STALE_FENCE',v_col_corr);
  exception when others then
    v_stale_fence_rejected:=position('stale_collision_lease_fence' in sqlerrm)>0;
  end;
  perform set_config('chlom_runtime.collision_rpc_v2','off',true);
  begin
    update institutional_federation.collision_domain_leases_v2 set updated_at=updated_at where lease_id=(v_la->>'lease_id')::uuid;
  exception when others then
    v_rogue_write_blocked:=true;
  end;
  v_lrelease:=institutional_federation.release_collision_domain_lease_v2((v_la->>'lease_id')::uuid,v_inst_a,v_fence,'CANARY_COMPLETE',v_col_corr);

  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed) values
    (v_run,'lease_two_worker_race_single_owner',v_race_blocked,jsonb_build_object('owner_lease',v_la->>'lease_id','second_worker_blocked',v_race_blocked)),
    (v_run,'lease_safe_renewal',v_lr->>'state'='active',v_lr-'event'),
    (v_run,'lease_exact_head_cas_abort',v_head_mismatch_rejected,jsonb_build_object('wrong_head_rejected',v_head_mismatch_rejected)),
    (v_run,'lease_stale_fence_rejected',v_stale_fence_rejected,jsonb_build_object('stale_fence_rejected',v_stale_fence_rejected)),
    (v_run,'collision_rogue_direct_write_fail_closed',v_rogue_write_blocked,jsonb_build_object('rogue_write_blocked',v_rogue_write_blocked)),
    (v_run,'lease_release_resume',v_lrelease->>'state'='released',v_lrelease-'event');

  -- Synthetic stale-owner TTL recovery is exercised only on PentaLease/PentaCollision.
  v_exp_la:=institutional_federation.acquire_collision_domain_lease_v2(v_domain_exp,'ct.penta.super.acceptance.worker-a',v_inst_a,v_intent_a,v_base_sha,v_head_sha,300,v_col_corr);
  perform set_config('chlom_runtime.collision_rpc_v2','on',true);
  update institutional_federation.collision_domain_leases_v2
  set acquired_at=clock_timestamp()-interval '10 minutes',renewed_at=clock_timestamp()-interval '10 minutes',expires_at=clock_timestamp()-interval '1 second',updated_at=clock_timestamp()
  where lease_id=(v_exp_la->>'lease_id')::uuid;
  v_exp_lb:=institutional_federation.acquire_collision_domain_lease_v2(v_domain_exp,'ct.penta.super.acceptance.worker-b',v_inst_b,v_intent_b,v_base_sha,v_head_sha,300,v_col_corr);
  perform institutional_federation.release_collision_domain_lease_v2((v_exp_lb->>'lease_id')::uuid,v_inst_b,(v_exp_lb->>'fence_token')::bigint,'CANARY_STALE_RECOVERY_COMPLETE',v_col_corr);
  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed)
  values(v_run,'lease_stale_owner_ttl_recovery',
    exists(select 1 from institutional_federation.collision_domain_leases_v2 where lease_id=(v_exp_la->>'lease_id')::uuid and state='expired')
    and (v_exp_lb->>'lease_id')<>(v_exp_la->>'lease_id'),
    jsonb_build_object('expired_lease',v_exp_la->>'lease_id','replacement_lease',v_exp_lb->>'lease_id'));

  select exists(
    select 1 from chlom_runtime.dail_events e
    where e.event_type='penta.snapshot.captured' and e.entity_id=v_baseline->>'snapshot_id'
      and e.payload->>'three_dail_logical_phase'='DAIL-EVIDENCE'
  ) and exists(
    select 1 from chlom_runtime.dail_events d
    join chlom_runtime.dail_events x on x.causation_id=d.event_id::text
    where d.event_id=(v_baseline#>>'{dail_decision,event_id}')::uuid
      and x.event_id=(v_baseline#>>'{dail_execution,event_id}')::uuid
      and d.payload->>'three_dail_logical_phase'='DAIL-DECISION'
      and x.payload->>'three_dail_logical_phase'='DAIL-EXECUTION'
  ) into v_dail_chain;

  select count(*) into v_census_count from public.penta_system_registry
  where system_key in (
    'penta.super','penta.dnd','penta.snapshot','penta.translate','penta.lease','penta.collision',
    'penta.translate.encode','penta.translate.decode','penta.translate.project','penta.translate.verify'
  );

  select count(*)=4 into v_authority_ok from penta_task_runtime.components_v1
  where component_id in ('ct.penta.snapshot.v1','ct.penta.translate.v1','ct.penta.lease.v1','ct.penta.collision.v1')
    and authority_ceiling='D2' and d3_human_reserved and no_self_certification;

  select count(*) into v_dnd_rows_after
  from penta_dnd.leases_v1
  where program_id ilike '%penta-super%' or scope_ref like 'ct.penta.super.v1:acceptance%';

  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed) values
    (v_run,'three_dail_append_readback_chain',v_dail_chain,jsonb_build_object('baseline_run_id',v_baseline->>'run_id','evidence_decision_execution',v_dail_chain)),
    (v_run,'penta_census_registry_readback',v_census_count=10,jsonb_build_object('registered_expected',10,'registered_observed',v_census_count,'penta_dnd_canonical_identity','penta.dnd')),
    (v_run,'negative_authority_boundaries',v_authority_ok,jsonb_build_object('four_pentas_d2_d3_reserved_no_self_certification',v_authority_ok,'penta_dnd_excluded_from_pentasuper_owned_components',true)),
    (v_run,'dnd_zero_activation_by_pentasuper',v_dnd_rows_after=v_dnd_rows_before,jsonb_build_object('before',v_dnd_rows_before,'after',v_dnd_rows_after,'penta_dnd_owned_by_pentasuper',false));

  select bool_and(passed),count(*) into v_pass,v_assertions
  from penta_task_runtime.acceptance_assertions_v1 where run_id=v_run;

  v_execution:=chlom_runtime.append_dail_event(
    'penta.super.task-runtime.full-matrix.completed','penta_super_acceptance',v_run::text,
    jsonb_build_object(
      'passed',coalesce(v_pass,false),'assertion_count',v_assertions,'baseline_run_id',v_baseline->>'run_id',
      'three_dail_logical_phase','DAIL-EXECUTION','production_certification',false,
      'independent_certification_required',true,'matrix_version','v4-consumer-boundary',
      'penta_dnd_activated',false,'penta_dnd_mode','consumer_only'
    ),
    p_actor_ref,null,'PentaSuper','1.0.3',v_corr,v_decision->>'event_id','D2',null,'internal'
  );

  update penta_task_runtime.acceptance_runs_v1 set
    state=case when v_pass then 'pass' else 'fail' end,
    decision_dail_event_id=(v_decision->>'event_id')::uuid,
    execution_dail_event_id=(v_execution->>'event_id')::uuid,
    evidence=jsonb_build_object(
      'matrix_version','v4-consumer-boundary','baseline_run_id',v_baseline->>'run_id','assertion_count',v_assertions,
      'production_certified',false,'independent_certification_required',true,
      'penta_dnd_mode','consumer_only','penta_dnd_activated',false
    ),
    completed_at=clock_timestamp()
  where run_id=v_run;

  return jsonb_build_object(
    'ok',coalesce(v_pass,false),'state',case when v_pass then 'pass' else 'fail' end,
    'run_id',v_run,'assertion_count',v_assertions,'baseline_run_id',v_baseline->>'run_id',
    'dail_decision',v_decision,'dail_execution',v_execution,
    'penta_dnd_activated',false,'production_certified',false,'independent_certification_required',true
  );
exception when others then
  update penta_task_runtime.acceptance_runs_v1
  set state='fail',evidence=jsonb_build_object(
    'matrix_version','v4-consumer-boundary','error_class',sqlstate,'error_message',left(sqlerrm,400),
    'production_certified',false,'penta_dnd_activated',false
  ),completed_at=clock_timestamp()
  where run_id=v_run and state='running';
  raise;
end;
$$;

revoke all on function penta_task_runtime.run_acceptance_canary_v2(text) from public, anon, authenticated;
revoke all on function penta_task_runtime.run_full_acceptance_matrix_v3(text) from public, anon, authenticated;
grant execute on function penta_task_runtime.run_acceptance_canary_v2(text) to service_role;
grant execute on function penta_task_runtime.run_full_acceptance_matrix_v3(text) to service_role;

commit;
