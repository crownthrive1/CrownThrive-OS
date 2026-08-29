-- Fragment 2/5: deterministic agent/subagent materialization into CHLOM and PentaWorkforce.
create or replace function public.pentafactory_materialize_daily_entity_v1(
  p_date date,p_ref text,p_kind text,p_entity_parent text,p_template_parent text,p_parent_seq int,p_sub_seq int,
  p_lane text,p_name text,p_class text,p_autonomy text,p_authority text,p_role text,p_manager uuid,p_retire timestamptz
) returns uuid language plpgsql security definer
set search_path='pg_catalog','public','chlom_runtime','extensions' as $f$
declare
  v_policy public.pentafactory_daily_fleet_policy_v1%rowtype;
  v_assignment uuid; v_meta jsonb; v_evidence jsonb; v_layer text; v_receipts int;
  v_layers text[]:=array['penta-governance','chlom-authority','penta-police','penta-build','penta-certify','penta-nurture','penta-release'];
  v_expected text; v_source text; v_skill text;
begin
  select * into strict v_policy from public.pentafactory_daily_fleet_policy_v1
    where policy_id='ct.pentafactory.daily-agent-fleet.10x100.v1';
  if not exists(select 1 from chlom_runtime.agent_templates where agent_id=v_policy.shared_sidecar_id
    and lifecycle_state='active' and authority_ceiling='D2' and not vote_eligible and no_self_approval) then
    raise exception 'shared Agent D sidecar is not ready';
  end if;
  if p_kind='parent_agent' then
    v_expected:=format('ct.agent.factory.daily.%s.p%s',to_char(p_date,'YYYYMMDD'),lpad(p_parent_seq::text,2,'0'));
    if p_entity_parent is not null or p_sub_seq is not null then raise exception 'invalid parent hierarchy'; end if;
  elsif p_kind='subagent' then
    v_expected:=format('ct.subagent.factory.daily.%s.p%s.s%s',to_char(p_date,'YYYYMMDD'),lpad(p_parent_seq::text,2,'0'),lpad(p_sub_seq::text,2,'0'));
    if p_entity_parent is null or p_sub_seq is null then raise exception 'invalid subagent hierarchy'; end if;
  else raise exception 'invalid entity kind'; end if;
  if p_ref<>v_expected or p_authority='D3' then raise exception 'identifier or authority invariant failed: %',p_ref; end if;
  if not exists(select 1 from chlom_runtime.agent_templates where agent_id=p_template_parent and lifecycle_state='active') then
    raise exception 'template parent is not active: %',p_template_parent;
  end if;
  if exists(select 1 from chlom_runtime.agent_templates where agent_id=p_ref
    and coalesce(metadata->>'factory_policy_id','')<>'ct.pentafactory.daily-agent-fleet.10x100.v1') then
    raise exception 'agent identifier collision: %',p_ref;
  end if;

  v_source:=v_policy.source_ref||'#'||p_ref;
  v_skill:=case when p_kind='parent_agent' then replace(p_ref,'ct.agent.','ct.skill.')
                else replace(p_ref,'ct.subagent.','ct.skill.subagent.') end;
  v_meta:=jsonb_build_object(
    'suite_id','ct.agent-suite.pentafactory-daily-fleet.v1','factory_policy_id',v_policy.policy_id,
    'production_date',p_date,'entity_kind',p_kind,'entity_parent_ref',p_entity_parent,'lane_key',p_lane,
    'parent_seq',p_parent_seq,'subagent_seq',p_sub_seq,'state','production_active',
    'charter','penta.charter.democratic-governance.v1','branches',jsonb_build_array(
      'penta.branch.legislative','penta.branch.executive','penta.branch.judicial'),'layers',to_jsonb(v_layers),
    'vote_effect',false,'quorum_effect',false,'no_vote_proxy',true,'no_authority_inheritance',true,
    'no_self_approval',true,'d3_human_reserved',true,'no_recursive_spawn',true,'no_silent_delete',true,
    'no_direct_main_write',true,'merge_authority',false,'deploy_authority',false,'publish_authority',false,
    'provider_write',false,'money_movement',false,'rights_grant',false,'credential_export',false,
    'agent_d_sidecar_mode','shared','agent_d_sidecar_id',v_policy.shared_sidecar_id,
    'retirement_due_at',p_retire,'retirement_mode','non_destructive','source_ref',v_source);

  insert into chlom_runtime.agent_templates as t(
    agent_id,parent_agent_id,canonical_name,agent_class,autonomy_class,authority_ceiling,lifecycle_state,
    module_scope,tool_scope,schedule_profile,vote_eligible,self_healing_enabled,no_self_approval,heartbeat_ttl_seconds,metadata
  ) values(p_ref,p_template_parent,p_name,p_class,p_autonomy,p_authority,'active',
    array['pentafactory','penta-agentic','penta-governance',p_lane],
    jsonb_build_object('allowed',jsonb_build_array('read','analyze','plan','propose','bounded_execute','test','document','append_evidence','self_heal_within_scope'),
      'delete',false,'merge',false,'deploy',false,'publish',false,'provider_write',false,'money_movement',false,
      'rights_grant',false,'credential_export',false,'recursive_spawn',false),
    'pentafactory_daily_fleet_v1',false,true,true,3600,v_meta)
  on conflict(agent_id) do update set parent_agent_id=excluded.parent_agent_id,canonical_name=excluded.canonical_name,
    agent_class=excluded.agent_class,autonomy_class=excluded.autonomy_class,authority_ceiling=excluded.authority_ceiling,
    lifecycle_state='active',module_scope=excluded.module_scope,tool_scope=excluded.tool_scope,
    schedule_profile=excluded.schedule_profile,vote_eligible=false,self_healing_enabled=true,no_self_approval=true,
    metadata=t.metadata||excluded.metadata,updated_at=now();

  insert into chlom_runtime.agent_privilege_profiles as p(
    profile_id,suite_id,agent_id,operating_mode,authority_ceiling,allowed_capabilities,forbidden_capabilities,
    privilege_state,special_privilege_requested,expires_at,manifest_ref,source_ids,metadata
  ) values('ct.profile.pentafactory.daily.'||substr(md5(p_ref),1,24),'ct.agent-suite.pentafactory-daily-fleet.v1',
    p_ref,'rigid',p_authority,array['read','analyze','plan','propose','bounded_execute','test','document','append_evidence','self_heal_within_scope'],
    array['delete','self_approve','vote','merge','deploy','publish','d3','money_movement','rights_grant','credential_export','provider_write','recursive_spawn'],
    'active',false,p_retire,v_source,array['policy:'||v_policy.policy_id,'entity:'||p_ref],v_meta)
  on conflict(agent_id) do update set suite_id=excluded.suite_id,operating_mode='rigid',authority_ceiling=excluded.authority_ceiling,
    allowed_capabilities=excluded.allowed_capabilities,forbidden_capabilities=excluded.forbidden_capabilities,
    privilege_state='active',special_privilege_requested=false,special_privilege_receipt=null,expires_at=excluded.expires_at,
    manifest_ref=excluded.manifest_ref,source_ids=excluded.source_ids,metadata=p.metadata||excluded.metadata,updated_at=now();

  insert into chlom_runtime.agent_skill_packages as s(
    skill_id,suite_id,agent_id,install_name,semantic_version,generation_support,manifest_ref,manifest_sha256,
    mcp_state,commercial_state,checkout_enabled,entitlement_active,release_receipt,metadata
  ) values(v_skill,'ct.agent-suite.pentafactory-daily-fleet.v1',p_ref,replace(p_ref,'.','-'),'1.0.0',array['gen6','gen7'],
    v_source,encode(extensions.digest(convert_to(v_source,'UTF8'),'sha256'),'hex'),'active','hold',false,false,
    'dail:pentafactory:'||p_date::text||':'||p_ref,v_meta||jsonb_build_object('commercialization_state','hold'))
  on conflict(agent_id) do update set suite_id=excluded.suite_id,install_name=excluded.install_name,
    semantic_version=excluded.semantic_version,generation_support=excluded.generation_support,manifest_ref=excluded.manifest_ref,
    manifest_sha256=excluded.manifest_sha256,mcp_state='active',commercial_state='hold',price_credits=null,
    checkout_enabled=false,entitlement_active=false,release_receipt=excluded.release_receipt,
    metadata=s.metadata||excluded.metadata,updated_at=now();

  insert into public.pentafactory_daily_fleet_entities_v1 as e(
    entity_ref,production_date,policy_id,entity_kind,parent_entity_ref,parent_seq,subagent_seq,lane_key,canonical_name,
    agent_class,autonomy_class,authority_ceiling,lifecycle_state,retirement_due_at,metadata
  ) values(p_ref,p_date,v_policy.policy_id,p_kind,p_entity_parent,p_parent_seq,p_sub_seq,p_lane,p_name,p_class,
    p_autonomy,p_authority,'active',p_retire,v_meta)
  on conflict(entity_ref) do update set production_date=excluded.production_date,policy_id=excluded.policy_id,
    entity_kind=excluded.entity_kind,parent_entity_ref=excluded.parent_entity_ref,parent_seq=excluded.parent_seq,
    subagent_seq=excluded.subagent_seq,lane_key=excluded.lane_key,canonical_name=excluded.canonical_name,
    agent_class=excluded.agent_class,autonomy_class=excluded.autonomy_class,authority_ceiling=excluded.authority_ceiling,
    lifecycle_state='active',retirement_due_at=excluded.retirement_due_at,retired_at=null,
    metadata=e.metadata||excluded.metadata,updated_at=now();

  insert into public.penta_workforce_subjects as w(subject_ref,subject_type,display_name,source_system,source_ref,lifecycle_state,metadata)
  values(p_ref,'agent',p_name,'PentaFactory',v_source,'active',v_meta)
  on conflict(subject_ref) do update set display_name=excluded.display_name,source_system=excluded.source_system,
    source_ref=excluded.source_ref,lifecycle_state='active',metadata=w.metadata||excluded.metadata,updated_at=now();

  insert into public.penta_workforce_assignments as a(
    assignment_key,subject_ref,role_key,unit_key,manager_assignment_id,scope,starts_at,ends_at,state,source_ref,metadata
  ) values('penta.assignment.'||md5(p_ref),p_ref,p_role,'penta.unit.managers',p_manager,v_meta,clock_timestamp(),p_retire,'active',v_source,v_meta)
  on conflict(assignment_key) do update set role_key=excluded.role_key,unit_key=excluded.unit_key,
    manager_assignment_id=excluded.manager_assignment_id,scope=excluded.scope,ends_at=excluded.ends_at,state='active',
    source_ref=excluded.source_ref,metadata=a.metadata||excluded.metadata,updated_at=now()
  returning assignment_id into v_assignment;

  update public.penta_governance_memberships set branch_key=null,civic_role='observer',voting_status='nonvoting',vote_weight=1,
    metadata=metadata||jsonb_build_object('factory_policy_id',v_policy.policy_id,'nonvoting',true,'d3_human_reserved',true),updated_at=now()
  where subject_ref=p_ref;

  foreach v_layer in array v_layers loop
    v_evidence:=jsonb_build_object('contract','ct.pentafactory.daily-fleet.receipt.v1','entity_ref',p_ref,
      'production_date',p_date,'layer',v_layer,'decision','pass','authority_ceiling',p_authority,
      'charter','penta.charter.democratic-governance.v1','nonvoting',true,'no_self_approval',true,
      'd3_human_reserved',true,'shared_sidecar_id',v_policy.shared_sidecar_id,'observed_at',clock_timestamp());
    insert into public.pentafactory_daily_fleet_receipts_v1 as r(entity_ref,layer_key,decision,evidence,evidence_sha256)
    values(p_ref,v_layer,'pass',v_evidence,encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex'))
    on conflict(entity_ref,layer_key) do update set decision='pass',evidence=excluded.evidence,
      evidence_sha256=excluded.evidence_sha256,created_at=clock_timestamp();
  end loop;
  select count(*) into v_receipts from public.pentafactory_daily_fleet_receipts_v1 where entity_ref=p_ref and decision='pass';
  if v_receipts<>7 then raise exception 'governance receipt invariant failed for %',p_ref; end if;
  return v_assignment;
end $f$;
