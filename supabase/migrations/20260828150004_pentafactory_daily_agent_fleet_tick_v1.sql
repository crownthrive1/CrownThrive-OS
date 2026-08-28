-- Fragment 4/5: exact daily 10-parent/100-subagent production tick and DAIL sealing.
create or replace function public.pentafactory_daily_fleet_tick_v1(
  p_date date default((now() at time zone 'America/New_York')::date),p_force boolean default false
) returns jsonb language plpgsql security definer
set search_path='pg_catalog','public','chlom_runtime','integration_control','extensions' as $f$
declare
  p public.pentafactory_daily_fleet_policy_v1%rowtype; i int; j int; d text; parent_ref text; child_ref text;
  manager_id uuid; retire_at timestamptz; core jsonb; evidence jsonb; sha text;
  lanes text[]:=array['orchestration_planning','build_integration','research_intelligence','verification_certification','security_risk','rights_culture','sre_continuity','documentation_dail','commerce_licensing','ecosystem_community'];
  parent_names text[]:=array['Planning & Orchestration','Build & Integration','Research & Intelligence','Verification & Certification','Security & Risk','Rights & Culture','SRE & Continuity','Documentation & DAIL','Commerce & Licensing','Ecosystem & Community'];
  parent_classes text[]:=array['planner','builder','researcher','verifier','security','rights','sre','documentation','commerce','continuity'];
  child_names text[]:=array['Scope Recon','Evidence Worker','Contract Builder','Test Runner','Drift Guard','Security Checker','Rights Checker','Cost Guard','Documentation Scribe','Recovery Verifier'];
  child_classes text[]:=array['researcher','documentation','builder','tevv','verifier','security','rights','reviewer','documentation','recovery'];
begin
  if not pg_try_advisory_xact_lock(hashtextextended('ct.pentafactory.daily.10x100:'||p_date::text,0)) then
    return jsonb_build_object('state','concurrency_hold','production_date',p_date); end if;
  select * into strict p from public.pentafactory_daily_fleet_policy_v1
    where policy_id='ct.pentafactory.daily-agent-fleet.10x100.v1' for update;
  if p_date<p.start_date then return jsonb_build_object('state','hold','reason','before_start_date'); end if;
  if not p.enabled and not p_force then
    insert into public.pentafactory_daily_fleet_runs_v1(production_date,policy_id,state,error)
    values(p_date,p.policy_id,'hold','policy_disabled') on conflict(production_date) do update set state='hold',error='policy_disabled',updated_at=now();
    return jsonb_build_object('state','hold','reason','policy_disabled'); end if;
  if p.parent_quota<>10 or p.subagent_quota<>100 or p.subagents_per_parent<>10 or not p.d3_human_reserved then
    raise exception '10x100 policy invariant drift'; end if;
  if not exists(select 1 from chlom_runtime.agent_templates where agent_id=p.shared_sidecar_id and lifecycle_state='active'
    and authority_ceiling='D2' and not vote_eligible and no_self_approval) then raise exception 'shared sidecar not ready'; end if;
  if exists(select 1 from public.pentafactory_daily_fleet_runs_v1 where production_date=p_date and state='pass') and not p_force then
    return public.pentafactory_daily_fleet_status_v1(p_date); end if;

  perform public.pentafactory_retire_daily_fleet_v1(p_date);
  insert into public.pentafactory_daily_fleet_runs_v1(production_date,policy_id,state,started_at,error,metadata)
  values(p_date,p.policy_id,'running',clock_timestamp(),null,jsonb_build_object('forced',p_force,'shared_sidecar_id',p.shared_sidecar_id))
  on conflict(production_date) do update set state='running',parent_count=0,subagent_count=0,receipt_count=0,
    receipt_sha256=null,error=null,started_at=clock_timestamp(),finished_at=null,
    metadata=pentafactory_daily_fleet_runs_v1.metadata||excluded.metadata,updated_at=now();
  d:=to_char(p_date,'YYYYMMDD'); retire_at:=(p_date+p.retention_days)::timestamp at time zone p.timezone;
  for i in 1..10 loop
    parent_ref:=format('ct.agent.factory.daily.%s.p%s',d,lpad(i::text,2,'0'));
    manager_id:=public.pentafactory_materialize_daily_entity_v1(p_date,parent_ref,'parent_agent',null,
      'ct.agent.factory.orchestrator',i,null,lanes[i],format('PentaFactory Daily %s Agent — %s P%s',parent_names[i],p_date,lpad(i::text,2,'0')),
      parent_classes[i],'A2','D2','penta.role.manager',null,retire_at);
    for j in 1..10 loop
      child_ref:=format('ct.subagent.factory.daily.%s.p%s.s%s',d,lpad(i::text,2,'0'),lpad(j::text,2,'0'));
      perform public.pentafactory_materialize_daily_entity_v1(p_date,child_ref,'subagent',parent_ref,parent_ref,i,j,lanes[i],
        format('PentaFactory Daily %s Subagent — %s P%s/S%s',child_names[j],p_date,lpad(i::text,2,'0'),lpad(j::text,2,'0')),
        child_classes[j],'A1','D1','penta.role.worker',manager_id,retire_at);
    end loop;
  end loop;

  select jsonb_build_object(
    'parents',(select count(*) from public.pentafactory_daily_fleet_entities_v1 where production_date=p_date and entity_kind='parent_agent' and lifecycle_state='active'),
    'subagents',(select count(*) from public.pentafactory_daily_fleet_entities_v1 where production_date=p_date and entity_kind='subagent' and lifecycle_state='active'),
    'templates',(select count(*) from chlom_runtime.agent_templates where lifecycle_state='active' and(agent_id like 'ct.agent.factory.daily.'||d||'.%' or agent_id like 'ct.subagent.factory.daily.'||d||'.%')),
    'privileges',(select count(*) from chlom_runtime.agent_privilege_profiles where privilege_state='active' and(agent_id like 'ct.agent.factory.daily.'||d||'.%' or agent_id like 'ct.subagent.factory.daily.'||d||'.%')),
    'skills',(select count(*) from chlom_runtime.agent_skill_packages where mcp_state='active' and(agent_id like 'ct.agent.factory.daily.'||d||'.%' or agent_id like 'ct.subagent.factory.daily.'||d||'.%')),
    'workforce',(select count(*) from public.penta_workforce_subjects where lifecycle_state='active' and(subject_ref like 'ct.agent.factory.daily.'||d||'.%' or subject_ref like 'ct.subagent.factory.daily.'||d||'.%')),
    'nonvoting',(select count(distinct subject_ref) from public.penta_governance_memberships where voting_status='nonvoting' and civic_role='observer' and branch_key is null and(subject_ref like 'ct.agent.factory.daily.'||d||'.%' or subject_ref like 'ct.subagent.factory.daily.'||d||'.%')),
    'receipts',(select count(*) from public.pentafactory_daily_fleet_receipts_v1 r join public.pentafactory_daily_fleet_entities_v1 e using(entity_ref) where e.production_date=p_date and r.decision='pass'),
    'authority_violations',(select count(*) from chlom_runtime.agent_templates a where(a.agent_id like 'ct.agent.factory.daily.'||d||'.%' or a.agent_id like 'ct.subagent.factory.daily.'||d||'.%') and(a.vote_eligible or not a.no_self_approval or a.authority_ceiling='D3' or a.metadata->>'agent_d_sidecar_mode' is distinct from 'shared')),
    'membership_violations',(select count(*) from public.penta_governance_memberships where(subject_ref like 'ct.agent.factory.daily.'||d||'.%' or subject_ref like 'ct.subagent.factory.daily.'||d||'.%') and(voting_status<>'nonvoting' or civic_role<>'observer' or branch_key is not null)),
    'dedicated_sidecars',(select count(*) from chlom_runtime.agent_templates where agent_id like 'ct.subagent.d-surrogate.%' and(metadata->>'execution_host_agent_id' like 'ct.agent.factory.daily.'||d||'.%' or metadata->>'execution_host_agent_id' like 'ct.subagent.factory.daily.'||d||'.%'))
  ) into core;
  if(core->>'parents')::int<>10 or(core->>'subagents')::int<>100 or(core->>'templates')::int<>110
    or(core->>'privileges')::int<>110 or(core->>'skills')::int<>110 or(core->>'workforce')::int<>110
    or(core->>'nonvoting')::int<>110 or(core->>'receipts')::int<>770 or(core->>'authority_violations')::int<>0
    or(core->>'membership_violations')::int<>0 or(core->>'dedicated_sidecars')::int<>0 then
    raise exception 'PentaFactory exact production invariant failed: %',core; end if;
  evidence:=core||jsonb_build_object('contract','ct.pentafactory.daily-fleet.run.v1','production_date',p_date,
    'policy_id',p.policy_id,'shared_sidecar_id',p.shared_sidecar_id,'retirement_due_at',retire_at,
    'd3_human_reserved',true,'observed_at',clock_timestamp());
  sha:=encode(extensions.digest(convert_to(evidence::text,'UTF8'),'sha256'),'hex');
  update public.pentafactory_daily_fleet_runs_v1 set state='pass',parent_count=10,subagent_count=100,
    receipt_count=770,receipt_sha256=sha,finished_at=clock_timestamp(),metadata=metadata||jsonb_build_object('evidence',evidence),updated_at=now()
    where production_date=p_date;
  perform chlom_runtime.append_dail_event('pentafactory.daily_fleet.completed','fleet',p_date::text,
    evidence||jsonb_build_object('receipt_sha256',sha),'ct.agent.factory.orchestrator',null,'ct.agent.factory.orchestrator',
    '1.0.0','pentafactory-daily:'||p_date::text,null,p.policy_id,null,'internal');
  perform integration_control.penta_police_reconcile_v1();
  return public.pentafactory_daily_fleet_status_v1(p_date);
exception when others then
  insert into public.pentafactory_daily_fleet_runs_v1(production_date,policy_id,state,error,finished_at,metadata)
  values(p_date,'ct.pentafactory.daily-agent-fleet.10x100.v1','failed',sqlerrm,clock_timestamp(),jsonb_build_object('sqlstate',sqlstate))
  on conflict(production_date) do update set state='failed',error=excluded.error,finished_at=excluded.finished_at,
    metadata=pentafactory_daily_fleet_runs_v1.metadata||excluded.metadata,updated_at=now();
  return jsonb_build_object('state','failed','production_date',p_date,'error',sqlerrm,'sqlstate',sqlstate);
end $f$;
