-- CrownThrive scheduled-agent contract v3 production-readiness hardening
-- Source-controls the already-applied migration: scheduled_agent_contract_v3_liveness_split.
-- Separates scheduler liveness from domain success. A live task may clear HEARTBEAT_STALE only;
-- it may never erase substantive security/failure/quarantine/D3/domain holds.

create or replace function chlom_runtime.scheduled_agent_contract_v3(
  p_binding_id text,
  p_cycle_id text,
  p_execution_mode text default 'canary'
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, extensions, chlom_runtime
as $$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role',true),'');
  v_binding chlom_runtime.automation_agent_bindings%rowtype;
  v_agent chlom_runtime.agent_templates%rowtype;
  v_health chlom_runtime.agent_health%rowtype;
  v_binding_probe jsonb;
  v_agent_probe jsonb;
  v_before_binding text;
  v_before_agent text;
  v_after_binding text;
  v_after_agent text;
  v_state text;
  v_reasons text[] := array[]::text[];
  v_subroutes integer := 0;
  v_receipt_digest text;
  v_actor text := 'ct.chlom.agent.orchestrator';
  v_payload jsonb;
  v_now timestamptz := clock_timestamp();
  v_health_found boolean := false;
  v_liveness_before text := 'unknown';
begin
  if session_user <> 'postgres'
     and current_user not in ('postgres','service_role')
     and v_role <> 'service_role' then
    raise exception 'service_role_required';
  end if;
  if coalesce(btrim(p_binding_id),'')='' or coalesce(btrim(p_cycle_id),'')='' then
    raise exception 'binding_id_and_cycle_id_required';
  end if;
  if p_execution_mode not in ('canary','live') then
    raise exception 'execution_mode_must_be_canary_or_live';
  end if;

  if not pg_try_advisory_xact_lock(hashtext('scheduled_agent_contract_v3|'||p_binding_id)) then
    v_payload := jsonb_build_object(
      'cycle_id',p_cycle_id,'execution_mode',p_execution_mode,'state','SKIPPED_LOCKED',
      'binding_id',p_binding_id,'reason_codes',jsonb_build_array('CONCURRENT_PREFLIGHT_LOCK'),
      'parent_action_executed',false,'vote_effect',false,'quorum_effect',false,
      'provider_write_authority',false,'money_movement_authority',false,
      'rights_grant_authority',false,'credential_authority',false,
      'merge_authority',false,'D3_auto',false
    );
    perform chlom_runtime.append_dail_event(
      'SCHEDULED_AGENT_CONTRACT_V3','automation_binding',p_binding_id,v_payload,
      'chlom_runtime.scheduled_agent_contract_v3',null,v_actor,'3.0.0',p_cycle_id,null,
      'scheduled agent contract preflight; concurrent lock fail-closed',null,'restricted'
    );
    return v_payload;
  end if;

  select * into v_binding
  from chlom_runtime.automation_agent_bindings
  where binding_id=p_binding_id;
  if not found or not v_binding.task_enabled or v_binding.canonical_agent_id is null then
    v_payload := jsonb_build_object(
      'cycle_id',p_cycle_id,'execution_mode',p_execution_mode,'state','HOLD_BINDING_INACTIVE',
      'binding_id',p_binding_id,'reason_codes',jsonb_build_array('BINDING_INACTIVE_OR_UNBOUND'),
      'parent_action_executed',false,'vote_effect',false,'quorum_effect',false,
      'provider_write_authority',false,'money_movement_authority',false,
      'rights_grant_authority',false,'credential_authority',false,
      'merge_authority',false,'D3_auto',false
    );
    perform chlom_runtime.append_dail_event(
      'SCHEDULED_AGENT_CONTRACT_V3','automation_binding',p_binding_id,v_payload,
      'chlom_runtime.scheduled_agent_contract_v3',null,v_actor,'3.0.0',p_cycle_id,null,
      'scheduled agent contract preflight; binding inactive fail-closed',null,'restricted'
    );
    return v_payload;
  end if;

  v_actor := v_binding.canonical_agent_id;
  select * into v_agent from chlom_runtime.agent_templates where agent_id=v_actor;
  if not found then
    v_payload := jsonb_build_object(
      'cycle_id',p_cycle_id,'execution_mode',p_execution_mode,'state','HOLD_AGENT_MISSING',
      'binding_id',p_binding_id,'agent_id',v_actor,
      'reason_codes',jsonb_build_array('CANONICAL_AGENT_MISSING'),
      'parent_action_executed',false,'vote_effect',false,'quorum_effect',false,
      'provider_write_authority',false,'money_movement_authority',false,
      'rights_grant_authority',false,'credential_authority',false,
      'merge_authority',false,'D3_auto',false
    );
    perform chlom_runtime.append_dail_event(
      'SCHEDULED_AGENT_CONTRACT_V3','automation_binding',p_binding_id,v_payload,
      'chlom_runtime.scheduled_agent_contract_v3',null,v_actor,'3.0.0',p_cycle_id,null,
      'scheduled agent contract preflight; canonical agent missing',null,'restricted'
    );
    return v_payload;
  end if;

  if v_agent.lifecycle_state='test' then
    v_payload := jsonb_build_object(
      'cycle_id',p_cycle_id,'execution_mode',p_execution_mode,'state','HOLD_AGENT_TEST',
      'binding_id',p_binding_id,'agent_id',v_agent.agent_id,
      'reason_codes',jsonb_build_array('INTENTIONAL_CONTROLLED_TEST_LIFECYCLE'),
      'production_fault',false,'parent_action_executed',false,
      'vote_effect',false,'quorum_effect',false,'provider_write_authority',false,
      'money_movement_authority',false,'rights_grant_authority',false,
      'credential_authority',false,'merge_authority',false,'D3_auto',false
    );
    perform chlom_runtime.append_dail_event(
      'SCHEDULED_AGENT_CONTRACT_V3','automation_binding',p_binding_id,v_payload,
      'chlom_runtime.scheduled_agent_contract_v3',null,v_actor,'3.0.0',p_cycle_id,null,
      'scheduled agent contract preflight; intentional controlled-test parent',null,'restricted'
    );
    return v_payload;
  elsif v_agent.lifecycle_state <> 'active' then
    v_payload := jsonb_build_object(
      'cycle_id',p_cycle_id,'execution_mode',p_execution_mode,'state','HOLD_AGENT_INACTIVE',
      'binding_id',p_binding_id,'agent_id',v_agent.agent_id,
      'reason_codes',jsonb_build_array('CANONICAL_AGENT_NOT_ACTIVE'),
      'production_fault',true,'parent_action_executed',false,
      'vote_effect',false,'quorum_effect',false,'provider_write_authority',false,
      'money_movement_authority',false,'rights_grant_authority',false,
      'credential_authority',false,'merge_authority',false,'D3_auto',false
    );
    perform chlom_runtime.append_dail_event(
      'SCHEDULED_AGENT_CONTRACT_V3','automation_binding',p_binding_id,v_payload,
      'chlom_runtime.scheduled_agent_contract_v3',null,v_actor,'3.0.0',p_cycle_id,null,
      'scheduled agent contract preflight; parent inactive fail-closed',null,'restricted'
    );
    return v_payload;
  end if;

  if v_agent.authority_ceiling='D3' or not v_binding.d3_human_reserved then
    v_reasons := array_append(v_reasons,'AUTOMATED_D3_BOUNDARY_VIOLATION');
  end if;
  if exists(
    select 1 from chlom_runtime.agent_emergency_kill_state_v1 k
    where k.target_agent_id=v_agent.agent_id
      and (k.is_killed or coalesce(k.quarantine_state,'clear')<>'clear')
  ) then
    v_reasons := array_append(v_reasons,'AGENT_KILLED_OR_QUARANTINED');
  end if;

  v_before_binding := chlom_runtime.contract_source_digest_v1('automation_binding',p_binding_id);
  v_before_agent := chlom_runtime.contract_source_digest_v1('agent',v_agent.agent_id);
  v_binding_probe := chlom_runtime.contract_object_probe_v1('automation_binding',p_binding_id,p_cycle_id||':binding');
  v_agent_probe := chlom_runtime.contract_object_probe_v1('agent',v_agent.agent_id,p_cycle_id||':agent');
  v_subroutes := coalesce(jsonb_array_length(v_agent.metadata #> '{complete_mesh,subroutes}'),0);

  if v_binding_probe->>'state' <> 'PASS_CONTROLLED_TEST' then
    v_reasons := array_append(v_reasons,'AUTOMATION_BINDING_CONTRACT_NOT_PASS');
  end if;
  if v_agent_probe->>'state' <> 'PASS_CONTROLLED_TEST' then
    v_reasons := array_append(v_reasons,'AGENT_CONTRACT_NOT_PASS');
  end if;
  if v_subroutes <> 3 then
    v_reasons := array_append(v_reasons,'MESH_SUBROUTE_COUNT_NOT_THREE');
  elsif exists(
    select 1 from jsonb_array_elements(v_agent.metadata #> '{complete_mesh,subroutes}') x
    where coalesce((x->>'vote_eligible')::boolean,true)
       or coalesce((x->>'quorum_eligible')::boolean,true)
       or coalesce((x->>'independent_certifier')::boolean,true)
  ) then
    v_reasons := array_append(v_reasons,'MESH_SUBROUTE_AUTHORITY_VIOLATION');
  end if;

  select * into v_health from chlom_runtime.agent_health where agent_id=v_agent.agent_id;
  v_health_found := found;
  if v_health_found then
    v_liveness_before := coalesce(v_health.health_state,'unknown')||':'||coalesce(v_health.last_error_code,'none');
    if v_health.health_state in ('failed','paused','retired') then
      v_reasons := array_append(v_reasons,'PARENT_SUBSTANTIVE_HEALTH_HOLD');
    elsif v_health.health_state='degraded'
       and coalesce(v_health.last_error_code,'') <> 'HEARTBEAT_STALE' then
      v_reasons := array_append(v_reasons,'PARENT_SUBSTANTIVE_HEALTH_HOLD');
    elsif v_health.last_error_code is not null
       and v_health.last_error_code <> 'HEARTBEAT_STALE' then
      v_reasons := array_append(v_reasons,'PARENT_SUBSTANTIVE_HEALTH_HOLD');
    end if;
  end if;

  v_after_binding := chlom_runtime.contract_source_digest_v1('automation_binding',p_binding_id);
  v_after_agent := chlom_runtime.contract_source_digest_v1('agent',v_agent.agent_id);
  if v_before_binding is distinct from v_after_binding
     or v_before_agent is distinct from v_after_agent then
    v_reasons := array_append(v_reasons,'SECOND_READ_DRIFT');
  end if;

  if cardinality(v_reasons)=0 and p_execution_mode='live' then
    insert into chlom_runtime.agent_health(
      agent_id,run_id,health_state,current_task,last_heartbeat_at,last_success_at,
      last_error_code,current_commit_sha,current_policy_sha,resource_state,updated_at
    ) values (
      v_agent.agent_id,p_cycle_id,'healthy','scheduled_contract:'||p_binding_id,
      v_now,null,null,null,null,
      jsonb_build_object(
        'liveness_source','scheduled_agent_contract_v3_live_start',
        'binding_id',p_binding_id,'cycle_id',p_cycle_id,
        'contract_start_at',v_now,'domain_success_not_implied',true,
        'vote_effect',false,'quorum_effect',false,'D3_auto',false
      ),v_now
    )
    on conflict (agent_id) do update set
      run_id=excluded.run_id,
      health_state=case
        when chlom_runtime.agent_health.last_error_code is null
          or chlom_runtime.agent_health.last_error_code='HEARTBEAT_STALE'
          then 'healthy'
        else chlom_runtime.agent_health.health_state
      end,
      current_task=excluded.current_task,
      last_heartbeat_at=excluded.last_heartbeat_at,
      last_error_code=case
        when chlom_runtime.agent_health.last_error_code='HEARTBEAT_STALE' then null
        else chlom_runtime.agent_health.last_error_code
      end,
      resource_state=coalesce(chlom_runtime.agent_health.resource_state,'{}'::jsonb) || excluded.resource_state,
      updated_at=excluded.updated_at;
  end if;

  v_state := case
    when cardinality(v_reasons)>0 then 'HOLD'
    when p_execution_mode='live' then 'PASS_RUNTIME_PREFLIGHT'
    else 'PASS_CONTROLLED_TEST_CANARY'
  end;
  v_receipt_digest := encode(extensions.digest(convert_to(
    jsonb_build_object(
      'binding_id',p_binding_id,'agent_id',v_agent.agent_id,'cycle_id',p_cycle_id,
      'execution_mode',p_execution_mode,'state',v_state,'reasons',v_reasons,
      'binding_digest',v_after_binding,'agent_digest',v_after_agent,'at',v_now
    )::text,'UTF8'),'sha256'),'hex');
  v_payload := jsonb_build_object(
    'cycle_id',p_cycle_id,'execution_mode',p_execution_mode,'agent_id',v_agent.agent_id,
    'binding_id',p_binding_id,'state',v_state,'reason_codes',v_reasons,
    'binding_digest',v_after_binding,'agent_digest',v_after_agent,
    'subroute_count',v_subroutes,'receipt_digest',v_receipt_digest,
    'liveness_before',v_liveness_before,
    'live_heartbeat_written',p_execution_mode='live' and cardinality(v_reasons)=0,
    'domain_success_implied',false,
    'second_read_pass',not('SECOND_READ_DRIFT'=any(v_reasons)),
    'parent_action_executed',false,'vote_effect',false,'quorum_effect',false,
    'provider_write_authority',false,'money_movement_authority',false,
    'rights_grant_authority',false,'credential_authority',false,
    'merge_authority',false,'D3_auto',false
  );
  perform chlom_runtime.append_dail_event(
    'SCHEDULED_AGENT_CONTRACT_V3','automation_binding',p_binding_id,v_payload,
    'chlom_runtime.scheduled_agent_contract_v3',null,v_actor,'3.0.0',p_cycle_id,null,
    'scheduled agent contract preflight; liveness separated from domain success',null,'restricted'
  );
  return v_payload;
end
$$;

create or replace function chlom_runtime.scheduled_agent_contract_complete_v1(
  p_binding_id text,
  p_cycle_id text,
  p_outcome text,
  p_evidence_digest text default null
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, extensions, chlom_runtime
as $$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role',true),'');
  v_binding chlom_runtime.automation_agent_bindings%rowtype;
  v_now timestamptz := clock_timestamp();
  v_payload jsonb;
  v_state text;
begin
  if session_user <> 'postgres'
     and current_user not in ('postgres','service_role')
     and v_role <> 'service_role' then
    raise exception 'service_role_required';
  end if;
  if p_outcome not in ('SUCCESS','HOLD','NOOP','UNKNOWN','FAILURE') then
    raise exception 'unsupported_outcome';
  end if;
  if p_evidence_digest is not null and p_evidence_digest !~ '^[0-9a-f]{64}$' then
    raise exception 'evidence_digest_must_be_sha256';
  end if;
  select * into v_binding from chlom_runtime.automation_agent_bindings where binding_id=p_binding_id;
  if not found or v_binding.canonical_agent_id is null then raise exception 'binding_not_found'; end if;

  if not exists(
    select 1 from chlom_runtime.dail_events d
    where d.event_type='SCHEDULED_AGENT_CONTRACT_V3'
      and d.entity_type='automation_binding'
      and d.entity_id=p_binding_id
      and d.correlation_id=p_cycle_id
      and d.payload->>'state'='PASS_RUNTIME_PREFLIGHT'
  ) then
    v_payload := jsonb_build_object(
      'binding_id',p_binding_id,'agent_id',v_binding.canonical_agent_id,'cycle_id',p_cycle_id,
      'state','HOLD_NO_VALID_LIVE_START','outcome',p_outcome,
      'vote_effect',false,'quorum_effect',false,'provider_write_authority',false,
      'money_movement_authority',false,'rights_grant_authority',false,
      'credential_authority',false,'merge_authority',false,'D3_auto',false
    );
    perform chlom_runtime.append_dail_event(
      'SCHEDULED_AGENT_CONTRACT_COMPLETE_V1','automation_binding',p_binding_id,v_payload,
      'chlom_runtime.scheduled_agent_contract_complete_v1',null,v_binding.canonical_agent_id,
      '1.0.0',p_cycle_id,null,'completion refused without exact live-start receipt',null,'restricted'
    );
    return v_payload;
  end if;

  if p_outcome='FAILURE' then
    update chlom_runtime.agent_health
       set health_state=case when last_error_code is null or last_error_code='HEARTBEAT_STALE' then 'degraded' else health_state end,
           last_error_code=case when last_error_code is null or last_error_code='HEARTBEAT_STALE' then 'SCHEDULED_RUN_FAILURE' else last_error_code end,
           resource_state=coalesce(resource_state,'{}'::jsonb) || jsonb_build_object(
             'last_scheduled_cycle_id',p_cycle_id,'last_scheduled_outcome',p_outcome,
             'last_scheduled_completion_at',v_now,'evidence_digest',p_evidence_digest
           ),
           updated_at=v_now
     where agent_id=v_binding.canonical_agent_id;
    v_state := 'RECORDED_FAILURE';
  else
    update chlom_runtime.agent_health
       set health_state=case when last_error_code is null or last_error_code='HEARTBEAT_STALE' then 'healthy' else health_state end,
           last_heartbeat_at=v_now,
           last_success_at=v_now,
           last_error_code=case when last_error_code='HEARTBEAT_STALE' then null else last_error_code end,
           resource_state=coalesce(resource_state,'{}'::jsonb) || jsonb_build_object(
             'last_scheduled_cycle_id',p_cycle_id,'last_scheduled_outcome',p_outcome,
             'last_scheduled_completion_at',v_now,'evidence_digest',p_evidence_digest,
             'domain_gate_pass_not_implied',p_outcome in ('HOLD','UNKNOWN')
           ),
           updated_at=v_now
     where agent_id=v_binding.canonical_agent_id;
    v_state := 'RECORDED_COMPLETION';
  end if;

  v_payload := jsonb_build_object(
    'binding_id',p_binding_id,'agent_id',v_binding.canonical_agent_id,'cycle_id',p_cycle_id,
    'state',v_state,'outcome',p_outcome,'evidence_digest',p_evidence_digest,
    'vote_effect',false,'quorum_effect',false,'provider_write_authority',false,
    'money_movement_authority',false,'rights_grant_authority',false,
    'credential_authority',false,'merge_authority',false,'D3_auto',false
  );
  perform chlom_runtime.append_dail_event(
    'SCHEDULED_AGENT_CONTRACT_COMPLETE_V1','automation_binding',p_binding_id,v_payload,
    'chlom_runtime.scheduled_agent_contract_complete_v1',null,v_binding.canonical_agent_id,
    '1.0.0',p_cycle_id,null,'scheduled agent completion receipt; domain governance remains separate',null,'restricted'
  );
  return v_payload;
end
$$;

revoke execute on function chlom_runtime.scheduled_agent_contract_v3(text,text,text) from public, anon, authenticated;
revoke execute on function chlom_runtime.scheduled_agent_contract_complete_v1(text,text,text,text) from public, anon, authenticated;
grant execute on function chlom_runtime.scheduled_agent_contract_v3(text,text,text) to service_role;
grant execute on function chlom_runtime.scheduled_agent_contract_complete_v1(text,text,text,text) to service_role;
