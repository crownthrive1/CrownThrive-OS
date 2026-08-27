-- Canonical migration: 20260824073728 / cie_post_activation_assurance_watch_v1
-- Purpose: bind a fail-closed CIE post-activation current-head assurance watcher into the
-- existing Repository Child Guardian 30-minute cycle. No new scheduler slot and no authority expansion.

begin;

create or replace function chlom_runtime.cie_post_activation_assurance_watch_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, institutional_federation, chlom_runtime, extensions
as $function$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role',true),'');
  v_pkg institutional_federation.framework_package_registry%rowtype;
  v_repo institutional_federation.repository_registry%rowtype;
  v_alg institutional_federation.algorithm_registry%rowtype;
  v_prod chlom_runtime.framework_production_receipts_v1%rowtype;
  v_parent_obs institutional_federation.repository_external_observations_v1%rowtype;
  v_child_obs institutional_federation.repository_external_observations_v1%rowtype;
  v_link institutional_federation.repository_parent_child_link_receipts_v1%rowtype;
  v_activation_parent text;
  v_activation_child text;
  v_state text;
  v_action_class text;
  v_priority smallint := 3;
  v_reason text;
  v_unlock text;
  v_refresh jsonb := '{}'::jsonb;
  v_refresh_performed boolean := false;
  v_action_key text;
  v_dail jsonb;
  v_evidence jsonb := '{}'::jsonb;
  v_error_code text;
  v_error_message text;
  v_now timestamptz := clock_timestamp();
begin
  if session_user <> 'postgres' and v_role <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct.cie.post-activation-assurance-watch.v1',0)) then
    return jsonb_build_object('state','SKIPPED_LOCKED','authority_effect',false,'D3_auto',false);
  end if;

  select * into v_pkg from institutional_federation.framework_package_registry
  where package_id='ct.framework-package.cie';
  select * into v_repo from institutional_federation.repository_registry
  where repo_id='ct.repo.cie';
  select * into v_alg from institutional_federation.algorithm_registry
  where algorithm_id='ct.algorithm.cie.v1';
  select * into v_prod from chlom_runtime.framework_production_receipts_v1
  where package_id='ct.framework-package.cie' and event_type='activation'
  order by created_at desc limit 1;
  select * into v_parent_obs from institutional_federation.repository_external_observations_v1
  where repo_id='ct.repo.CrownThrive-OS' order by observed_at desc limit 1;
  select * into v_child_obs from institutional_federation.repository_external_observations_v1
  where repo_id='ct.repo.cie' order by observed_at desc limit 1;
  select * into v_link from institutional_federation.repository_parent_child_link_receipts_v1
  where child_repo_id='ct.repo.cie' order by created_at desc limit 1;

  v_activation_parent := v_pkg.metadata->>'production_parent_head';
  v_activation_child := v_pkg.metadata->>'production_child_head';

  v_evidence := jsonb_build_object(
    'activation_receipt_id',v_prod.receipt_id,
    'activation_parent_head',v_activation_parent,
    'activation_child_head',v_activation_child,
    'production_authority_mode',v_prod.authority_mode,
    'latest_parent_observation_id',v_parent_obs.observation_id,
    'latest_parent_observation_head',v_parent_obs.head_sha,
    'latest_parent_observed_at',v_parent_obs.observed_at,
    'latest_child_observation_id',v_child_obs.observation_id,
    'latest_child_observation_head',v_child_obs.head_sha,
    'latest_child_observed_at',v_child_obs.observed_at,
    'latest_link_receipt_id',v_link.link_receipt_id,
    'latest_link_parent_head',v_link.parent_head_sha,
    'latest_link_child_head',v_link.child_head_sha,
    'scheduler_slot_delta',0,
    'external_network_call_performed',false,
    'production_authority_rewritten',false,
    'operational_activation',false,
    'authority_effect',false,
    'vote_effect',false,
    'D3_auto',false
  );

  if v_prod.receipt_id is null
     or v_prod.authority_mode <> 'founder_direct'
     or v_prod.rollback_state <> 'ready'
     or coalesce(v_prod.canary_result->>'verdict','') <> 'PASS'
     or v_pkg.package_state <> 'maintained'
     or not v_pkg.operationally_enabled
     or v_pkg.public_activation_allowed
     or v_pkg.commercial_state <> 'hold'
     or v_pkg.can_vote
     or not v_pkg.d3_human_reserved
     or v_repo.governance_state <> 'linked_governed'
     or not v_repo.operationally_enabled
     or v_repo.can_vote
     or v_alg.invocation_state <> 'production_limited'
     or v_alg.authority_ceiling <> 'D2'
     or v_alg.public_contract_digest <> 'e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2' then
    v_state := 'HOLD_PRODUCTION_BOUNDARY_DRIFT';
    v_action_class := 'POST_ACTIVATION_ASSURANCE_PRODUCTION_BOUNDARY_DRIFT';
    v_priority := 5;
    v_reason := 'Bounded CIE production invariants or immutable Founder-direct production receipt are not in the expected state.';
    v_unlock := 'Reconcile the production boundary and immutable activation receipt; this watcher may not manufacture or expand authority.';

  elsif v_parent_obs.observation_id is null or v_child_obs.observation_id is null
     or v_parent_obs.source_system <> 'github' or v_child_obs.source_system <> 'github'
     or not v_parent_obs.repository_exists or not v_child_obs.repository_exists
     or coalesce(v_parent_obs.archived,false) or coalesce(v_child_obs.archived,false)
     or v_parent_obs.default_branch is distinct from 'main' or v_child_obs.default_branch is distinct from 'main'
     or v_parent_obs.head_sha !~ '^[0-9a-f]{40}$' or v_child_obs.head_sha !~ '^[0-9a-f]{40}$'
     or v_parent_obs.observed_at < v_now-interval '90 minutes'
     or v_child_obs.observed_at < v_now-interval '90 minutes' then
    v_state := 'HOLD_EXTERNAL_GITHUB_EVIDENCE_STALE';
    v_action_class := 'POST_ACTIVATION_ASSURANCE_EXTERNAL_EVIDENCE_STALE';
    v_priority := 3;
    v_reason := 'Fresh exact service-ingested GitHub observations for Support and CIE are required; SQL does not synthesize external repository state.';
    v_unlock := 'Refresh exact GitHub main/head observations through the trusted external observation producer, including descendant proof for Support if its head changed.';

  elsif v_child_obs.evidence->>'repository' <> 'crownthrive1/CrownThrive-CIE'
     or coalesce((v_child_obs.evidence->>'github_repository_id')::bigint,0) <> 1341314455
     or coalesce((v_child_obs.evidence->>'production_authority_rewritten')::boolean,false) then
    v_state := 'HOLD_CIE_CHILD_OBSERVATION_TRUST_MISMATCH';
    v_action_class := 'POST_ACTIVATION_ASSURANCE_CHILD_OBSERVATION_TRUST_MISMATCH';
    v_priority := 4;
    v_reason := 'The newest CIE observation does not satisfy the trusted repository identity/evidence contract.';
    v_unlock := 'Ingest a fresh exact CIE GitHub observation for immutable repository ID 1341314455 with production_authority_rewritten=false.';

  elsif v_child_obs.head_sha <> v_activation_child then
    v_state := 'HOLD_CIE_CHILD_HEAD_CHANGED_REAUTH_REQUIRED';
    v_action_class := 'POST_ACTIVATION_ASSURANCE_CHILD_HEAD_CHANGED_REAUTH_REQUIRED';
    v_priority := 5;
    v_reason := 'CIE main moved beyond the Founder-authorized production child SHA; a child-code change cannot be auto-assured as parent continuity.';
    v_unlock := 'Run a new governed CIE production-source review and exact human/authorized production decision for the new child SHA before changing production authority.';

  elsif v_parent_obs.evidence->>'repository' <> 'crownthrive1/CrownThrive-OS'
     or coalesce((v_parent_obs.evidence->>'repository_id')::bigint,0) <> 1336348391
     or coalesce((v_parent_obs.evidence->>'production_authority_rewritten')::boolean,false) then
    v_state := 'HOLD_SUPPORT_PARENT_OBSERVATION_TRUST_MISMATCH';
    v_action_class := 'POST_ACTIVATION_ASSURANCE_PARENT_OBSERVATION_TRUST_MISMATCH';
    v_priority := 4;
    v_reason := 'The newest Support observation does not satisfy the trusted repository identity/evidence contract.';
    v_unlock := 'Ingest a fresh exact Support GitHub observation for repository ID 1336348391 with production_authority_rewritten=false.';

  elsif v_link.link_receipt_id is not null
     and v_link.parent_head_sha = v_parent_obs.head_sha
     and v_link.child_head_sha = v_child_obs.head_sha
     and v_link.link_state = 'linked_governed'
     and v_link.guardian_verified and v_link.family_verified and v_link.interoperability_verified
     and not v_link.authority_effect and not v_link.operational_activation and not v_link.vote_effect and not v_link.child_self_activation then
    v_state := 'PASS_CURRENT_ASSURANCE';
    v_reason := 'Latest exact service-ingested GitHub observations already match the current linked_governed post-activation assurance receipt.';
    v_unlock := null;

  elsif coalesce(v_parent_obs.evidence->>'compare_status','') <> 'ahead'
     or coalesce(v_parent_obs.evidence->>'compare_base_sha','') <> v_activation_parent
     or coalesce(v_parent_obs.evidence->>'compare_head_sha','') <> v_parent_obs.head_sha
     or coalesce((v_parent_obs.evidence->>'compare_behind_by')::integer,-1) <> 0
     or coalesce((v_parent_obs.evidence->>'compare_ahead_by')::integer,0) < 1 then
    v_state := 'HOLD_SUPPORT_DESCENDANT_PROOF_REQUIRED';
    v_action_class := 'POST_ACTIVATION_ASSURANCE_SUPPORT_DESCENDANT_PROOF_REQUIRED';
    v_priority := 4;
    v_reason := 'Support main changed, but the newest GitHub observation lacks exact descendant proof from the immutable activation parent.';
    v_unlock := 'Ingest a fresh Support GitHub observation with compare_status=ahead, compare_base_sha equal to the activation parent, compare_head_sha equal to current Support main, compare_behind_by=0 and compare_ahead_by>=1.';

  else
    begin
      v_refresh := chlom_runtime.refresh_cie_parent_child_production_assurance_v1(
        v_parent_obs.head_sha,
        v_child_obs.head_sha,
        '7f3b82e501770a22b02f0d14a842df9c6dc76d95789bfc799a976e9290407958',
        'guardian-watch:ct.schedule.repository-child-guardian-30m|parent-observation:'||v_parent_obs.observation_id::text||'|child-observation:'||v_child_obs.observation_id::text,
        jsonb_build_object(
          'github_compare_status',v_parent_obs.evidence->>'compare_status',
          'github_compare_base_sha',v_parent_obs.evidence->>'compare_base_sha',
          'github_compare_head_sha',v_parent_obs.evidence->>'compare_head_sha',
          'github_compare_ahead_by',(v_parent_obs.evidence->>'compare_ahead_by')::integer,
          'github_compare_behind_by',(v_parent_obs.evidence->>'compare_behind_by')::integer,
          'source_parent_observation_id',v_parent_obs.observation_id,
          'source_child_observation_id',v_child_obs.observation_id,
          'watcher_function','chlom_runtime.cie_post_activation_assurance_watch_v1',
          'guardian_schedule_id','ct.schedule.repository-child-guardian-30m',
          'automatic_assurance_refresh',true,
          'scheduler_slot_delta',0,
          'production_authority_rewritten',false,
          'public_activation',false,
          'commerce_activation',false
        )
      );
      if v_refresh->>'state' <> 'LINKED_GOVERNED_POST_ACTIVATION_ASSURANCE' then
        raise exception 'unexpected_assurance_refresh_result';
      end if;
      v_refresh_performed := true;
      v_state := 'PASS_ASSURANCE_REFRESHED';
      v_reason := 'Guardian watcher refreshed post-activation parent continuity from fresh exact GitHub descendant evidence.';
      v_unlock := null;
      v_evidence := v_evidence || jsonb_build_object(
        'refreshed_link_receipt_id',v_refresh->>'link_receipt_id',
        'refresh_dail_event_id',v_refresh->>'dail_event_id'
      );
    exception when others then
      v_error_code := sqlstate;
      v_error_message := left(sqlerrm,240);
      v_state := 'HOLD_ASSURANCE_REFRESH_FAILED';
      v_action_class := 'POST_ACTIVATION_ASSURANCE_REFRESH_FAILED';
      v_priority := 4;
      v_reason := 'The bounded assurance refresh rejected the candidate evidence; fail closed and require reconciliation.';
      v_unlock := 'Review the restricted watcher receipt and reconcile the evidence or production boundary before retry.';
      v_evidence := v_evidence || jsonb_build_object('refresh_error_code',v_error_code,'refresh_error_message',v_error_message);
    end;
  end if;

  -- Resolve only this watcher's prior non-destructive nurture actions when current assurance is healthy.
  if v_state in ('PASS_CURRENT_ASSURANCE','PASS_ASSURANCE_REFRESHED') then
    update institutional_federation.repository_guardian_actions_v1
    set action_state='resolved',
        evidence=coalesce(evidence,'{}'::jsonb)||v_evidence||jsonb_build_object('resolved_by','cie_post_activation_assurance_watch_v1','resolved_state',v_state),
        updated_at=now()
    where repo_id='ct.repo.cie'
      and action_class like 'POST_ACTIVATION_ASSURANCE_%'
      and action_state not in ('resolved','superseded');
  else
    v_action_key := 'guardian:ct.repo.cie:'||v_action_class;
    insert into institutional_federation.repository_guardian_actions_v1(
      action_key,repo_id,guardian_agent_id,action_class,action_state,priority,destructive,
      merge_authority_required,parent_approval_required,recommended_action,evidence
    ) values (
      v_action_key,'ct.repo.cie','ct.agent.repository-child-guardian-ad-litem',v_action_class,'open',v_priority,false,
      false,true,
      jsonb_build_object(
        'mode','NON_DESTRUCTIVE_POST_ACTIVATION_ASSURANCE_NURTURE',
        'reason',v_reason,
        'unlock_condition',v_unlock,
        'allowed',jsonb_build_array('observe','refresh_external_evidence','reconcile_registry','open_handoff','prepare_patch_candidate'),
        'forbidden',jsonb_build_array('activate','reactivate','rewrite_founder_authority','merge','delete','archive','transfer','visibility_change','self_activate_child','D3_auto')
      ),
      v_evidence||jsonb_build_object('watch_state',v_state,'refresh_performed',v_refresh_performed)
    )
    on conflict(action_key) do update set
      action_state=case when institutional_federation.repository_guardian_actions_v1.action_state='superseded' then 'superseded' else 'open' end,
      priority=excluded.priority,
      recommended_action=excluded.recommended_action,
      evidence=coalesce(institutional_federation.repository_guardian_actions_v1.evidence,'{}'::jsonb)||excluded.evidence,
      updated_at=now();
  end if;

  v_dail := chlom_runtime.append_dail_event(
    'cie.post_activation.assurance_watch.evaluated','repository','ct.repo.cie',
    v_evidence||jsonb_build_object(
      'state',v_state,
      'reason',v_reason,
      'unlock_condition',v_unlock,
      'refresh_performed',v_refresh_performed,
      'guardian_agent_id','ct.agent.repository-child-guardian-ad-litem',
      'schedule_id','ct.schedule.repository-child-guardian-30m',
      'scheduler_slot_delta',0,
      'external_network_call_performed',false,
      'production_authority_rewritten',false,
      'operational_activation',false,
      'provider_write_effect',false,
      'economic_effect',false,
      'rights_effect',false,
      'vote_effect',false,
      'D3_auto',false
    ),
    'ct.agent.repository-child-guardian-ad-litem',null,'ct.agent.repository-child-guardian-ad-litem','1.0.0',
    coalesce(v_link.link_receipt_id::text,v_parent_obs.observation_id::text),null,
    'Existing Guardian 30-minute cycle; post-activation assurance observation/refresh only; external GitHub evidence must already be present.',
    v_prod.receipt_id::text,'restricted'
  );

  return jsonb_build_object(
    'state',v_state,
    'reason',v_reason,
    'unlock_condition',v_unlock,
    'refresh_performed',v_refresh_performed,
    'current_parent_head',v_parent_obs.head_sha,
    'current_child_head',v_child_obs.head_sha,
    'current_link_receipt_id',case when v_refresh_performed then v_refresh->>'link_receipt_id' else v_link.link_receipt_id::text end,
    'nurture_action_key',v_action_key,
    'dail_event_id',v_dail->>'event_id',
    'scheduler_slot_delta',0,
    'external_network_call_performed',false,
    'production_authority_rewritten',false,
    'operational_activation',false,
    'authority_effect',false,
    'provider_write_effect',false,
    'economic_effect',false,
    'rights_effect',false,
    'vote_effect',false,
    'D3_auto',false,
    'checked_at',v_now
  );
end
$function$;

-- Preserve the existing Guardian/family/interop cycle and add the assurance watcher as a bounded subroute.
create or replace function chlom_runtime.repository_child_guardian_family_cycle_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, institutional_federation, chlom_runtime, extensions
as $function$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_guard jsonb;
  v_family jsonb;
  v_sync jsonb;
  v_assurance jsonb;
  v_dail jsonb;
  v_state text;
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  v_guard:=chlom_runtime.repository_child_guardian_cycle_v1();
  v_family:=chlom_runtime.repository_family_rebuild_v1();
  v_sync:=chlom_runtime.repository_family_interop_sync_v1();
  v_assurance:=chlom_runtime.cie_post_activation_assurance_watch_v1();
  v_state:=case
    when v_guard->>'state' like 'PASS%'
      and v_family->>'state' like 'PASS%'
      and (v_assurance->>'state' like 'PASS%' or v_assurance->>'state'='SKIPPED_LOCKED')
    then 'PASS_CONTROLLED_TEST'
    else 'HOLD'
  end;
  v_dail:=chlom_runtime.append_dail_event(
    'repository.family.guardian.cycle','agent','ct.agent.repository-child-guardian-ad-litem',
    jsonb_build_object(
      'guardian',v_guard,
      'family',v_family,
      'interop_sync',v_sync,
      'cie_post_activation_assurance',v_assurance,
      'human_titles_display_only',true,
      'authority_from_titles',false,
      'scheduler_slot_delta',0,
      'production_authority_rewritten',false,
      'D3_auto',false
    ),
    'ct.agent.repository-child-guardian-ad-litem',null,'ct.agent.repository-child-guardian-ad-litem','1.2.0',null,null,
    'Technical family ontology and CIE current-head assurance reconciliation; no legal/gender inference and no authority manufacture.',null,'restricted'
  );
  return jsonb_build_object(
    'state',v_state,
    'runtime_version','1.2.0',
    'guardian',v_guard,
    'family',v_family,
    'interop_sync',v_sync,
    'cie_post_activation_assurance',v_assurance,
    'dail_event_id',v_dail->>'event_id',
    'authority_from_titles',false,
    'scheduler_slot_delta',0,
    'production_authority_rewritten',false,
    'D3_auto',false
  );
end
$function$;

-- Reuse the existing 30-minute Guardian schedule; do not create a cron job or external task slot.
update chlom_runtime.agent_schedule_definitions
set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
      'post_activation_assurance_watch',true,
      'post_activation_assurance_watch_function','chlom_runtime.cie_post_activation_assurance_watch_v1',
      'post_activation_assurance_mode','fresh_external_evidence_consumer_fail_closed',
      'external_github_evidence_required',true,
      'auto_refresh_parent_descendant_only',true,
      'auto_refresh_child_head_changes',false,
      'child_head_change_requires_reauthorization',true,
      'scheduler_slot_delta',0,
      'production_authority_rewrite',false,
      'provider_write_effect',false,
      'economic_effect',false,
      'rights_effect',false,
      'vote_effect',false,
      'D3_auto',false
    ),
    source_ref='chlom_runtime.repository_child_guardian_family_cycle_v1@1.2.0',
    updated_at=now()
where schedule_id='ct.schedule.repository-child-guardian-30m'
  and execution_state='active'
  and external_task_id='pg_cron:ct-repository-child-guardian-30m';

revoke all on function chlom_runtime.cie_post_activation_assurance_watch_v1() from public,anon,authenticated;
grant execute on function chlom_runtime.cie_post_activation_assurance_watch_v1() to service_role;
revoke all on function chlom_runtime.repository_child_guardian_family_cycle_v1() from public,anon,authenticated;
grant execute on function chlom_runtime.repository_child_guardian_family_cycle_v1() to service_role;

commit;
