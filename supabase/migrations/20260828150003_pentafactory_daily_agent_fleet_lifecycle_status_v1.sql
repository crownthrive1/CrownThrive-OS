-- Fragment 3/5: non-destructive retirement and exact production status certification.
create or replace function public.pentafactory_retire_daily_fleet_v1(
  p_as_of date default((now() at time zone 'America/New_York')::date)
) returns jsonb language plpgsql security definer
set search_path='pg_catalog','public','chlom_runtime' as $f$
declare v_refs text[]; v_count int:=0; v_cutoff timestamptz;
begin
  v_cutoff:=p_as_of::timestamp at time zone 'America/New_York';
  select array_agg(entity_ref order by entity_ref) into v_refs
  from public.pentafactory_daily_fleet_entities_v1 where lifecycle_state='active' and retirement_due_at<=v_cutoff;
  if v_refs is null then return jsonb_build_object('state','pass','retired',0,'as_of',p_as_of); end if;
  update chlom_runtime.agent_templates set lifecycle_state='retired',metadata=metadata||jsonb_build_object(
    'retired_at',clock_timestamp(),'retirement_mode','non_destructive'),updated_at=now() where agent_id=any(v_refs);
  update chlom_runtime.agent_privilege_profiles set privilege_state='retired',expires_at=least(expires_at,clock_timestamp()),
    metadata=metadata||jsonb_build_object('retired_at',clock_timestamp()),updated_at=now() where agent_id=any(v_refs);
  update chlom_runtime.agent_skill_packages set mcp_state='retired',commercial_state='retired',checkout_enabled=false,
    entitlement_active=false,metadata=metadata||jsonb_build_object('retired_at',clock_timestamp()),updated_at=now()
    where agent_id=any(v_refs);
  update public.penta_workforce_assignments set state='retired',ends_at=least(coalesce(ends_at,clock_timestamp()),clock_timestamp()),
    metadata=metadata||jsonb_build_object('retired_at',clock_timestamp()),updated_at=now() where subject_ref=any(v_refs);
  update public.penta_workforce_subjects set lifecycle_state='retired',metadata=metadata||jsonb_build_object(
    'retired_at',clock_timestamp(),'retirement_mode','non_destructive'),updated_at=now() where subject_ref=any(v_refs);
  update public.pentafactory_daily_fleet_entities_v1 set lifecycle_state='retired',retired_at=clock_timestamp(),
    metadata=metadata||jsonb_build_object('history_preserved',true),updated_at=now() where entity_ref=any(v_refs);
  get diagnostics v_count=row_count;
  perform chlom_runtime.append_dail_event('pentafactory.daily_fleet.retired','fleet',p_as_of::text,
    jsonb_build_object('retired_entities',v_count,'retirement_mode','non_destructive','history_preserved',true),
    'ct.agent.factory.orchestrator',null,'ct.agent.factory.orchestrator','1.0.0',
    'pentafactory-retire:'||p_as_of::text,null,'ct.pentafactory.daily-agent-fleet.10x100.v1',null,'internal');
  return jsonb_build_object('state','pass','retired',v_count,'as_of',p_as_of,'history_preserved',true);
end $f$;

create or replace function public.pentafactory_daily_fleet_status_v1(
  p_date date default((now() at time zone 'America/New_York')::date)
) returns jsonb language plpgsql security definer
set search_path='pg_catalog','public','chlom_runtime' as $f$
declare d text:=to_char(p_date,'YYYYMMDD'); x jsonb; ok boolean;
begin
  select jsonb_build_object(
    'policy_enabled',(select enabled from public.pentafactory_daily_fleet_policy_v1 where policy_id='ct.pentafactory.daily-agent-fleet.10x100.v1'),
    'run_state',(select state from public.pentafactory_daily_fleet_runs_v1 where production_date=p_date),
    'run_receipt_sha256',(select receipt_sha256 from public.pentafactory_daily_fleet_runs_v1 where production_date=p_date),
    'parent_agents',(select count(*) from public.pentafactory_daily_fleet_entities_v1 where production_date=p_date and entity_kind='parent_agent' and lifecycle_state='active'),
    'subagents',(select count(*) from public.pentafactory_daily_fleet_entities_v1 where production_date=p_date and entity_kind='subagent' and lifecycle_state='active'),
    'active_templates',(select count(*) from chlom_runtime.agent_templates where lifecycle_state='active' and(agent_id like 'ct.agent.factory.daily.'||d||'.%' or agent_id like 'ct.subagent.factory.daily.'||d||'.%')),
    'active_privileges',(select count(*) from chlom_runtime.agent_privilege_profiles where privilege_state='active' and(agent_id like 'ct.agent.factory.daily.'||d||'.%' or agent_id like 'ct.subagent.factory.daily.'||d||'.%')),
    'active_skills',(select count(*) from chlom_runtime.agent_skill_packages where mcp_state='active' and(agent_id like 'ct.agent.factory.daily.'||d||'.%' or agent_id like 'ct.subagent.factory.daily.'||d||'.%')),
    'active_workforce',(select count(*) from public.penta_workforce_subjects where lifecycle_state='active' and(subject_ref like 'ct.agent.factory.daily.'||d||'.%' or subject_ref like 'ct.subagent.factory.daily.'||d||'.%')),
    'nonvoting_memberships',(select count(distinct subject_ref) from public.penta_governance_memberships where voting_status='nonvoting' and civic_role='observer' and branch_key is null and(subject_ref like 'ct.agent.factory.daily.'||d||'.%' or subject_ref like 'ct.subagent.factory.daily.'||d||'.%')),
    'governance_receipts',(select count(*) from public.pentafactory_daily_fleet_receipts_v1 r join public.pentafactory_daily_fleet_entities_v1 e using(entity_ref) where e.production_date=p_date and r.decision='pass'),
    'linkage_violations',(select count(*) from public.pentafactory_daily_fleet_entities_v1 c left join public.pentafactory_daily_fleet_entities_v1 p on p.entity_ref=c.parent_entity_ref where c.production_date=p_date and c.entity_kind='subagent' and(p.entity_ref is null or p.entity_kind<>'parent_agent' or p.production_date<>c.production_date)),
    'authority_violations',(select count(*) from chlom_runtime.agent_templates a where(a.agent_id like 'ct.agent.factory.daily.'||d||'.%' or a.agent_id like 'ct.subagent.factory.daily.'||d||'.%') and(a.vote_eligible or not a.no_self_approval or a.authority_ceiling='D3' or coalesce((a.metadata->>'no_recursive_spawn')::boolean,false) is not true or a.metadata->>'agent_d_sidecar_mode' is distinct from 'shared')),
    'membership_violations',(select count(*) from public.penta_governance_memberships where(subject_ref like 'ct.agent.factory.daily.'||d||'.%' or subject_ref like 'ct.subagent.factory.daily.'||d||'.%') and(voting_status<>'nonvoting' or civic_role<>'observer' or branch_key is not null)),
    'dedicated_sidecars',(select count(*) from chlom_runtime.agent_templates where agent_id like 'ct.subagent.d-surrogate.%' and(metadata->>'execution_host_agent_id' like 'ct.agent.factory.daily.'||d||'.%' or metadata->>'execution_host_agent_id' like 'ct.subagent.factory.daily.'||d||'.%')),
    'cron_active',exists(select 1 from cron.job where jobname='pentafactory-daily-agent-fleet-10x100-v1' and active),
    'schedule_active',exists(select 1 from chlom_runtime.agent_schedule_definitions where schedule_id='ct.schedule.pentafactory.daily-agent-fleet.10x100.v1' and execution_state='active')
  ) into x;
  ok:=coalesce((x->>'policy_enabled')::boolean,false) and x->>'run_state'='pass'
    and(x->>'parent_agents')::int=10 and(x->>'subagents')::int=100
    and(x->>'active_templates')::int=110 and(x->>'active_privileges')::int=110
    and(x->>'active_skills')::int=110 and(x->>'active_workforce')::int=110
    and(x->>'nonvoting_memberships')::int=110 and(x->>'governance_receipts')::int=770
    and(x->>'linkage_violations')::int=0 and(x->>'authority_violations')::int=0
    and(x->>'membership_violations')::int=0 and(x->>'dedicated_sidecars')::int=0
    and(x->>'cron_active')::boolean and(x->>'schedule_active')::boolean;
  return x||jsonb_build_object('state',case when ok then 'pass' else 'hold' end,'production_date',p_date,
    'daily_parent_quota',10,'daily_subagent_quota',100,'retention_days',30,'d3_human_reserved',true,
    'shared_sidecar_id','ct.subagent.d-surrogate.ct-agent-factory-orchestrator','observed_at',clock_timestamp());
end $f$;
