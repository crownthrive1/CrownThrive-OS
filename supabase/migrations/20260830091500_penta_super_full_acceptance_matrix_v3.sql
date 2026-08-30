-- PentaSuper task-runtime full acceptance matrix v3.
-- Registers the runtime family in the institutional registry and adds bounded
-- acceptance coverage for leases, DND, collision/CAS, translation, DAIL and Census.
-- Passing this canary is necessary but NOT sufficient for production certification.

insert into public.penta_system_registry(
  system_key,canonical_name,category,purpose,authority_boundary,risk_ceiling,maturity,version,public_exposure,docs_ref,runtime_ref,metadata,last_verified_at
) values
('penta.super','PentaSuper','supervisory_control','Bounded CrownThrive supervisory intelligence and meta-orchestration.','Supervises and delegates; no self-certification, D3 manufacture, credential invention, rights grant or material money movement.','D2','implemented','1.0.0',false,'penta/super/README.md','penta_task_runtime.run_full_acceptance_matrix_v3',jsonb_build_object('canonical_id','ct.penta.super.v1','family','ct.penta.super.v1','source_pr',1388,'implementation_state','runtime_active_unverified','no_self_certification',true,'d3_human_reserved',true),clock_timestamp()),
('penta.dnd','PentaDND','task_runtime_control','Scoped do-not-disturb lease and mutation-isolation controller.','Resource-scoped TTL/priority leases; never global authority manufacture.','D2','implemented','1.1.0',false,'penta/super/task-runtime-acceptance-v1.md','penta_dnd.open_lease_v2 + penta_dnd.renew_lease_v2',jsonb_build_object('canonical_id','ct.penta.dnd.v1','family','ct.penta.super.task-runtime-family.v1','implementation_state','runtime_active_unverified','no_self_certification',true,'d3_human_reserved',true),clock_timestamp()),
('penta.snapshot','PentaSnapshot','task_runtime_control','Bounded pre-mutation rollback checkpoint coordinator.','Captures fingerprints and rollback evidence; does not create mutation authority.','D2','implemented','1.0.0',false,'penta/super/task-runtime-acceptance-v1.md','penta_task_runtime.capture_snapshot_v1',jsonb_build_object('canonical_id','ct.penta.snapshot.v1','family','ct.penta.super.task-runtime-family.v1','implementation_state','runtime_active_unverified','no_self_certification',true,'d3_human_reserved',true),clock_timestamp()),
('penta.translate','PentaTranslate','task_runtime_control','Governed reversible source/projection translation boundary.','Derived projections only; protected mappings/keys remain restricted and source evidence remains immutable.','D2','implemented','1.0.0',false,'penta/super/task-runtime-acceptance-v1.md','penta_translate.record_projection_v1',jsonb_build_object('canonical_id','ct.penta.translate.v1','family','ct.penta.super.task-runtime-family.v1','implementation_state','runtime_active_unverified','no_self_certification',true,'d3_human_reserved',true,'transport_confidentiality',false),clock_timestamp()),
('penta.lease','PentaLease','task_runtime_control','Exact work/resource ownership lease and fencing controller.','CAS/fencing/idempotency only; does not create underlying mutation authority.','D2','implemented','1.0.0',false,'penta/super/task-runtime-acceptance-v1.md','institutional_federation.acquire_collision_domain_lease_v2',jsonb_build_object('canonical_id','ct.penta.lease.v1','family','ct.penta.super.task-runtime-family.v1','implementation_state','runtime_active_unverified','no_self_certification',true,'d3_human_reserved',true),clock_timestamp()),
('penta.collision','PentaCollision','task_runtime_control','Detects and fail-closes duplicate/conflicting agent mutations.','No counter-write against rogue writers; evidence/hold/routing only.','D2','implemented','1.0.0',false,'penta/super/task-runtime-acceptance-v1.md','institutional_federation.collision_events_v2',jsonb_build_object('canonical_id','ct.penta.collision.v1','family','ct.penta.super.task-runtime-family.v1','implementation_state','runtime_active_unverified','no_self_certification',true,'d3_human_reserved',true),clock_timestamp()),
('penta.translate.encode','PentaTranslate Encode','task_runtime_component','Deterministic machine transport projection.','No confidentiality claim; no protected key or mapping custody.','D1','implemented','1.0.0',false,'penta/super/task-runtime-acceptance-v1.md','penta_translate.encode_transport_v1',jsonb_build_object('canonical_id','ct.penta.translate.encode.v1','family','ct.penta.translate.v1','implementation_state','runtime_active_unverified'),clock_timestamp()),
('penta.translate.decode','PentaTranslate Decode','task_runtime_component','Deterministic transport decode and source reconstruction.','Derived view only; immutable source provenance required.','D1','implemented','1.0.0',false,'penta/super/task-runtime-acceptance-v1.md','penta_translate.decode_transport_v1',jsonb_build_object('canonical_id','ct.penta.translate.decode.v1','family','ct.penta.translate.v1','implementation_state','runtime_active_unverified'),clock_timestamp()),
('penta.translate.project','PentaTranslate Project','task_runtime_component','Records governed machine/human/hybrid projection identities.','No protected material in projection provenance.','D1','implemented','1.0.0',false,'penta/super/task-runtime-acceptance-v1.md','penta_translate.record_projection_v1',jsonb_build_object('canonical_id','ct.penta.translate.project.v1','family','ct.penta.translate.v1','implementation_state','runtime_active_unverified'),clock_timestamp()),
('penta.translate.verify','PentaTranslate Verify','task_runtime_component','Verifies round-trip identity and projection provenance.','Verification is non-originating evidence, not certification authority.','D1','implemented','1.0.0',false,'penta/super/task-runtime-acceptance-v1.md','penta_translate.run_round_trip_canary_v1',jsonb_build_object('canonical_id','ct.penta.translate.verify.v1','family','ct.penta.translate.v1','implementation_state','runtime_active_unverified'),clock_timestamp())
on conflict(system_key) do update set
  purpose=excluded.purpose,
  authority_boundary=excluded.authority_boundary,
  risk_ceiling=excluded.risk_ceiling,
  maturity=case when public.penta_system_registry.maturity in ('certified','production') then public.penta_system_registry.maturity else 'implemented' end,
  version=excluded.version,
  public_exposure=excluded.public_exposure,
  docs_ref=excluded.docs_ref,
  runtime_ref=excluded.runtime_ref,
  metadata=public.penta_system_registry.metadata||excluded.metadata,
  last_verified_at=clock_timestamp(),
  updated_at=clock_timestamp();

create or replace function penta_task_runtime.run_full_acceptance_matrix_v3(p_actor_ref text default 'ct.automation.penta-super-build')
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','extensions','public','penta_task_runtime','penta_dnd','penta_translate','institutional_federation','chlom_runtime'
as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_run uuid:=gen_random_uuid();
  v_corr text:='ctcorr:penta-super:full-matrix:'||v_run::text;
  v_decision jsonb;
  v_execution jsonb;
  v_baseline jsonb;
  v_scope text:='ct.penta.super.v1:full-matrix:'||v_run::text;
  v_exp_scope text:=v_scope||':expiry';
  v_dnd jsonb; v_dnd_idem jsonb; v_dnd_high jsonb; v_dnd_renew jsonb; v_dnd_close jsonb;
  v_pre_cert jsonb; v_pre_d3 jsonb; v_pre_resume jsonb;
  v_exp_a jsonb; v_exp_b jsonb; v_exp_a_state text;
  v_t1 jsonb; v_t2 jsonb; v_protected_rejected boolean:=false; v_protected_error text;
  v_intent_a uuid:=gen_random_uuid(); v_intent_b uuid:=gen_random_uuid();
  v_inst_a uuid:=gen_random_uuid(); v_inst_b uuid:=gen_random_uuid();
  v_col_corr uuid:=gen_random_uuid();
  v_base_sha text:='f6c0a2927ffceb1e19950fb796b234174361d863';
  v_head_sha text:='3f7aaeb7a9b857cefadb5170884b8c111222c45f';
  v_wrong_head text:='3333333333333333333333333333333333333333';
  v_domain text:='ct.penta.super.acceptance.domain:'||v_run::text;
  v_domain_exp text:=v_domain||':expiry';
  v_la jsonb; v_lb jsonb; v_lr jsonb; v_lrelease jsonb; v_exp_la jsonb; v_exp_lb jsonb;
  v_race_blocked boolean:=false; v_head_mismatch_rejected boolean:=false; v_stale_fence_rejected boolean:=false; v_rogue_write_blocked boolean:=false;
  v_fence bigint; v_exp_fence bigint;
  v_dail_chain boolean:=false; v_census_count integer:=0; v_authority_ok boolean:=false;
  v_pass boolean:=false; v_assertions integer:=0;
  v_hash_a text; v_hash_b text; v_hash_c text; v_hash_d text;
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;

  insert into penta_task_runtime.acceptance_runs_v1(run_id,state,actor_ref,source_ref)
  values(v_run,'running',p_actor_ref,'PR#1388/supabase/migrations/20260830091500_penta_super_full_acceptance_matrix_v3.sql');

  v_decision:=chlom_runtime.append_dail_event(
    'penta.super.task-runtime.full-matrix.started','penta_super_acceptance',v_run::text,
    jsonb_build_object('three_dail_logical_phase','DAIL-DECISION','production_certification',false,'matrix_version','v3'),
    p_actor_ref,null,'PentaSuper','1.0.2',v_corr,null,'D2',null,'internal'
  );

  v_baseline:=penta_task_runtime.run_acceptance_canary_v2(p_actor_ref);
  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed)
  values(v_run,'baseline_v2_pass',coalesce((v_baseline->>'ok')::boolean,false),v_baseline);

  -- PentaDND: exact scope, replay idempotency, higher-priority non-preemption,
  -- renewal, verifier access, D3 reservation, release and resume.
  v_dnd:=penta_dnd.open_lease_v2('ct.program.penta-super-build-dnd','full_acceptance',v_scope,p_actor_ref,'full matrix owner',60::smallint,300,'matrix','verify');
  v_dnd_idem:=penta_dnd.open_lease_v2('ct.program.penta-super-build-dnd','full_acceptance',v_scope,p_actor_ref,'full matrix owner replay',60::smallint,300,'matrix','verify');
  v_dnd_high:=penta_dnd.open_lease_v2('ct.program.penta-super-build-dnd','full_acceptance',v_scope,'ct.penta.super.acceptance.worker-b','higher priority collision canary',90::smallint,300,'matrix','verify');
  v_dnd_renew:=penta_dnd.renew_lease_v2((v_dnd->>'lease_id')::uuid,p_actor_ref,300);
  v_pre_cert:=penta_dnd.preflight_v1('full_acceptance',v_scope,'penta.certify','penta.certify',true,false,false);
  v_pre_d3:=penta_dnd.preflight_v1('full_acceptance',v_scope,p_actor_ref,'dnd.scope',true,false,true);
  v_dnd_close:=penta_dnd.close_lease_v1((v_dnd->>'lease_id')::uuid,'full_matrix_release_resume');
  v_pre_resume:=penta_dnd.preflight_v1('full_acceptance',v_scope,p_actor_ref,'dnd.scope',true,false,false);

  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed) values
    (v_run,'dnd_duplicate_idempotency',(v_dnd_idem->>'lease_id')=(v_dnd->>'lease_id') and v_dnd_idem->>'state'='idempotent_active',v_dnd_idem),
    (v_run,'dnd_priority_no_silent_preemption',coalesce((v_dnd_high->>'ok')::boolean,false)=false and v_dnd_high->>'state'='held_by_active_owner' and (v_dnd_high->>'requested_priority')::integer=90,v_dnd_high),
    (v_run,'dnd_safe_renewal',coalesce((v_dnd_renew->>'ok')::boolean,false) and v_dnd_renew->>'state'='renewed',v_dnd_renew-'dail'),
    (v_run,'verifier_not_suppressed',coalesce((v_pre_cert->>'allowed')::boolean,false) and v_pre_cert->>'decision'='PASS_DND_SCOPED_MUTATION',v_pre_cert),
    (v_run,'d3_remains_human_reserved',coalesce((v_pre_d3->>'allowed')::boolean,true)=false and v_pre_d3->>'decision'='HOLD_D3_HUMAN_RESERVED',v_pre_d3),
    (v_run,'dnd_release_and_resume',coalesce((v_dnd_close->>'ok')::boolean,false) and coalesce((v_pre_resume->>'allowed')::boolean,false) and v_pre_resume->>'decision'='PASS_NO_DND_SCOPE',jsonb_build_object('close',v_dnd_close-'dail','resume',v_pre_resume));

  -- Synthetic expiry boundary on canary-only rows proves TTL expiry and stale-owner recovery
  -- without waiting five minutes or touching a production work scope.
  v_exp_a:=penta_dnd.open_lease_v2('ct.program.penta-super-build-dnd','full_acceptance',v_exp_scope,'ct.penta.super.acceptance.worker-a','synthetic ttl canary',50::smallint,300,'matrix','verify');
  update penta_dnd.leases_v1 set expires_at=clock_timestamp()-interval '1 second',updated_at=clock_timestamp() where lease_id=(v_exp_a->>'lease_id')::uuid;
  v_exp_b:=penta_dnd.open_lease_v2('ct.program.penta-super-build-dnd','full_acceptance',v_exp_scope,'ct.penta.super.acceptance.worker-b','stale owner recovery canary',50::smallint,300,'matrix','verify');
  select state into v_exp_a_state from penta_dnd.leases_v1 where lease_id=(v_exp_a->>'lease_id')::uuid;
  perform penta_dnd.close_lease_v1((v_exp_b->>'lease_id')::uuid,'full_matrix_expiry_canary_complete');
  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed) values
    (v_run,'dnd_ttl_expiry_boundary',v_exp_a_state='expired',jsonb_build_object('old_lease_id',v_exp_a->>'lease_id','old_state',v_exp_a_state)),
    (v_run,'dnd_stale_owner_recovery',coalesce((v_exp_b->>'ok')::boolean,false) and (v_exp_b->>'lease_id')<>(v_exp_a->>'lease_id'),v_exp_b-'dail');

  -- PentaTranslate: deterministic replay plus protected-material rejection.
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

  -- PentaLease/PentaCollision: two-worker lease race, renewal, exact-head CAS,
  -- fence rejection, controlled rogue direct-write rejection, and stale-owner recovery.
  v_hash_a:=encode(extensions.digest(convert_to('penta-super-acceptance-executable-a|'||v_run::text,'UTF8'),'sha256'),'hex');
  v_hash_b:=encode(extensions.digest(convert_to('penta-super-acceptance-config|'||v_run::text,'UTF8'),'sha256'),'hex');
  v_hash_c:=encode(extensions.digest(convert_to('penta-super-acceptance-policy|'||v_run::text,'UTF8'),'sha256'),'hex');
  v_hash_d:=encode(extensions.digest(convert_to('penta-super-acceptance-intent-a|'||v_run::text,'UTF8'),'sha256'),'hex');
  perform institutional_federation.register_collision_intent_v2(v_intent_a,'crownthrive1/CrownThrive-OS','acceptance_canary','penta-super-task-runtime', 'ct.penta.super.acceptance.worker-a',v_inst_a,v_base_sha,v_head_sha,v_hash_a,v_hash_b,v_hash_c,v_hash_d,v_col_corr,'D1',jsonb_build_array(jsonb_build_object('capability','acceptance_canary')),jsonb_build_object('canary',true,'run_id',v_run));
  v_hash_a:=encode(extensions.digest(convert_to('penta-super-acceptance-executable-b|'||v_run::text,'UTF8'),'sha256'),'hex');
  v_hash_d:=encode(extensions.digest(convert_to('penta-super-acceptance-intent-b|'||v_run::text,'UTF8'),'sha256'),'hex');
  perform institutional_federation.register_collision_intent_v2(v_intent_b,'crownthrive1/CrownThrive-OS','acceptance_canary','penta-super-task-runtime', 'ct.penta.super.acceptance.worker-b',v_inst_b,v_base_sha,v_head_sha,v_hash_a,v_hash_b,v_hash_c,v_hash_d,v_col_corr,'D1',jsonb_build_array(jsonb_build_object('capability','acceptance_canary')),jsonb_build_object('canary',true,'run_id',v_run));

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
  exception when others then v_head_mismatch_rejected:=position('collision_lease_version_mismatch' in sqlerrm)>0; end;
  begin
    perform institutional_federation.release_collision_domain_lease_v2((v_la->>'lease_id')::uuid,v_inst_a,v_fence+1,'CANARY_STALE_FENCE',v_col_corr);
  exception when others then v_stale_fence_rejected:=position('stale_collision_lease_fence' in sqlerrm)>0; end;
  perform set_config('chlom_runtime.collision_rpc_v2','off',true);
  begin
    update institutional_federation.collision_domain_leases_v2 set updated_at=updated_at where lease_id=(v_la->>'lease_id')::uuid;
  exception when others then v_rogue_write_blocked:=true; end;
  v_lrelease:=institutional_federation.release_collision_domain_lease_v2((v_la->>'lease_id')::uuid,v_inst_a,v_fence,'CANARY_COMPLETE',v_col_corr);

  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed) values
    (v_run,'lease_two_worker_race_single_owner',v_race_blocked,jsonb_build_object('owner_lease',v_la->>'lease_id','second_worker_blocked',v_race_blocked)),
    (v_run,'lease_safe_renewal',v_lr->>'state'='active',v_lr-'event'),
    (v_run,'lease_exact_head_cas_abort',v_head_mismatch_rejected,jsonb_build_object('wrong_head_rejected',v_head_mismatch_rejected)),
    (v_run,'lease_stale_fence_rejected',v_stale_fence_rejected,jsonb_build_object('stale_fence_rejected',v_stale_fence_rejected)),
    (v_run,'collision_rogue_direct_write_fail_closed',v_rogue_write_blocked,jsonb_build_object('rogue_write_blocked',v_rogue_write_blocked));

  v_exp_la:=institutional_federation.acquire_collision_domain_lease_v2(v_domain_exp,'ct.penta.super.acceptance.worker-a',v_inst_a,v_intent_a,v_base_sha,v_head_sha,300,v_col_corr);
  v_exp_fence:=(v_exp_la->>'fence_token')::bigint;
  perform set_config('chlom_runtime.collision_rpc_v2','on',true);
  update institutional_federation.collision_domain_leases_v2 set expires_at=clock_timestamp()-interval '1 second',updated_at=clock_timestamp() where lease_id=(v_exp_la->>'lease_id')::uuid;
  v_exp_lb:=institutional_federation.acquire_collision_domain_lease_v2(v_domain_exp,'ct.penta.super.acceptance.worker-b',v_inst_b,v_intent_b,v_base_sha,v_head_sha,300,v_col_corr);
  perform institutional_federation.release_collision_domain_lease_v2((v_exp_lb->>'lease_id')::uuid,v_inst_b,(v_exp_lb->>'fence_token')::bigint,'CANARY_STALE_RECOVERY_COMPLETE',v_col_corr);
  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed)
  values(v_run,'lease_stale_owner_recovery',
    exists(select 1 from institutional_federation.collision_domain_leases_v2 where lease_id=(v_exp_la->>'lease_id')::uuid and state='expired')
    and (v_exp_lb->>'lease_id')<>(v_exp_la->>'lease_id'),
    jsonb_build_object('expired_lease',v_exp_la->>'lease_id','replacement_lease',v_exp_lb->>'lease_id'));

  -- Three logical DAIL lanes: EVIDENCE from baseline snapshot, DECISION and EXECUTION
  -- from the baseline acceptance run, with causal binding.
  select exists(
    select 1 from chlom_runtime.dail_events e
    where e.event_type='penta.snapshot.captured' and e.entity_id=v_baseline->>'snapshot_id'
      and e.payload->>'three_dail_logical_phase'='DAIL-EVIDENCE'
  ) and exists(
    select 1 from chlom_runtime.dail_events d join chlom_runtime.dail_events x on x.causation_id=d.event_id::text
    where d.event_id=(v_baseline#>>'{dail_decision,event_id}')::uuid
      and x.event_id=(v_baseline#>>'{dail_execution,event_id}')::uuid
      and d.payload->>'three_dail_logical_phase'='DAIL-DECISION'
      and x.payload->>'three_dail_logical_phase'='DAIL-EXECUTION'
  ) into v_dail_chain;

  select count(*) into v_census_count from public.penta_system_registry
  where metadata->>'canonical_id' in (
    'ct.penta.super.v1','ct.penta.dnd.v1','ct.penta.snapshot.v1','ct.penta.translate.v1','ct.penta.lease.v1','ct.penta.collision.v1',
    'ct.penta.translate.encode.v1','ct.penta.translate.decode.v1','ct.penta.translate.project.v1','ct.penta.translate.verify.v1'
  );
  select count(*)=5 into v_authority_ok from penta_task_runtime.components_v1
  where component_id in ('ct.penta.dnd.v1','ct.penta.snapshot.v1','ct.penta.translate.v1','ct.penta.lease.v1','ct.penta.collision.v1')
    and authority_ceiling='D2' and d3_human_reserved and no_self_certification;

  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed) values
    (v_run,'three_dail_append_readback_chain',v_dail_chain,jsonb_build_object('baseline_run_id',v_baseline->>'run_id','evidence_decision_execution',v_dail_chain)),
    (v_run,'penta_census_registry_readback',v_census_count=10,jsonb_build_object('registered_expected',10,'registered_observed',v_census_count)),
    (v_run,'negative_authority_boundaries',v_authority_ok,jsonb_build_object('five_components_d2_d3_reserved_no_self_certification',v_authority_ok));

  select bool_and(passed),count(*) into v_pass,v_assertions from penta_task_runtime.acceptance_assertions_v1 where run_id=v_run;
  v_execution:=chlom_runtime.append_dail_event(
    'penta.super.task-runtime.full-matrix.completed','penta_super_acceptance',v_run::text,
    jsonb_build_object('passed',coalesce(v_pass,false),'assertion_count',v_assertions,'baseline_run_id',v_baseline->>'run_id','three_dail_logical_phase','DAIL-EXECUTION','production_certification',false,'independent_certification_required',true),
    p_actor_ref,null,'PentaSuper','1.0.2',v_corr,v_decision->>'event_id','D2',null,'internal'
  );
  update penta_task_runtime.acceptance_runs_v1 set
    state=case when v_pass then 'pass' else 'fail' end,
    decision_dail_event_id=(v_decision->>'event_id')::uuid,
    execution_dail_event_id=(v_execution->>'event_id')::uuid,
    evidence=jsonb_build_object('matrix_version','v3','baseline_run_id',v_baseline->>'run_id','assertion_count',v_assertions,'production_certified',false,'independent_certification_required',true),
    completed_at=clock_timestamp()
  where run_id=v_run;
  return jsonb_build_object('ok',coalesce(v_pass,false),'state',case when v_pass then 'pass' else 'fail' end,'run_id',v_run,'assertion_count',v_assertions,'baseline_run_id',v_baseline->>'run_id','dail_decision',v_decision,'dail_execution',v_execution,'production_certified',false,'independent_certification_required',true);
exception when others then
  begin
    if coalesce(v_dnd->>'lease_id','')<>'' then perform penta_dnd.close_lease_v1((v_dnd->>'lease_id')::uuid,'full_matrix_exception'); end if;
    if coalesce(v_exp_b->>'lease_id','')<>'' then perform penta_dnd.close_lease_v1((v_exp_b->>'lease_id')::uuid,'full_matrix_exception'); end if;
  exception when others then null; end;
  update penta_task_runtime.acceptance_runs_v1 set state='fail',evidence=jsonb_build_object('matrix_version','v3','error_class',sqlstate,'error_message',left(sqlerrm,400),'production_certified',false),completed_at=clock_timestamp() where run_id=v_run and state='running';
  raise;
end;
$$;

select chlom_runtime.append_dail_event(
  'penta.super.full-acceptance-matrix.v3.installed','penta_super_runtime','ct.penta.task-runtime-family.v1',
  jsonb_build_object('runtime','penta_task_runtime.run_full_acceptance_matrix_v3','census_registration',true,'matrix_version','v3','three_dail_logical_phase','DAIL-EXECUTION','independent_certification_required',true,'production_certified',false),
  'ct.automation.penta-super-build',null,'PentaSuper','1.0.2','ctcorr:penta-super:full-matrix-v3-install',null,'D2',null,'internal'
);