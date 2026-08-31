-- CrownThrive PentaSELF delegation / PentaMocracy family convergence v1
-- Resolves four previously owner-unmapped discovery identities as bounded,
-- non-executable job/family contracts. It does not create runtime authority.

-- When the canonical Penta OS registry explicitly marks a record as an
-- unresolved_reference, an accepted PentaMocracy job assignment is the more
-- specific governing source for its job role. All other source precedence is
-- unchanged.
do $body$
declare
  v_def text;
  v_old text := $q$roletext:=coalesce(sys->>'role',r.job_role,r.live_attrs->>'category',cname||' institutional capability');$q$;
  v_new text := $q$roletext:=case when sys is not null and sys->>'intake_state'='unresolved_reference' and nullif(r.job_role,'') is not null then r.job_role else coalesce(sys->>'role',r.job_role,r.live_attrs->>'category',cname||' institutional capability') end;$q$;
begin
  select pg_get_functiondef(p.oid) into v_def
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='integration_control' and p.proname='penta_identity_refresh_v1'
  limit 1;

  if v_def is null then
    raise exception 'PENTA_IDENTITY_REFRESH_FUNCTION_MISSING';
  end if;
  if position(v_new in v_def)>0 then
    null; -- idempotent
  elsif position(v_old in v_def)=0 then
    raise exception 'PENTA_IDENTITY_REFRESH_ROLE_PRECEDENCE_UNEXPECTED';
  else
    v_def:=replace(v_def,v_old,v_new);
    execute v_def;
  end if;
end
$body$;

with cfg(identity_key,canonical_name,family_key,job_key,axis,job_role) as (
  values
  ('penta.prioritize','PentaPrioritize','AUTOMATION_AGENTIC','penta.prioritize.advisory-priority','execution',
   'Rank bounded work using declared priority, dependency, risk, urgency, impact and readiness evidence. It may recommend ordering and holds but cannot dispatch work, mutate providers, certify outcomes, deploy releases or exercise D3.'),
  ('penta.overseer','PentaOverseer','OBSERVABILITY_ORGANIC','penta.overseer.readonly-oversight','authority',
   'Perform read-only oversight of governed workflows, health, evidence and policy conformance. It may surface holds and escalation needs but cannot approve, dispatch, deploy, certify, mutate providers or exercise D3.'),
  ('penta.clean','PentaClean','RESILIENCE_CONTINUITY','penta.clean.safe-cleanup-planning','continuity',
   'Plan and verify bounded cleanup of explicitly noncanonical, stale or ephemeral state. Canonical identity history, aliases, DAIL events, CHLOM evidence and immutable records are never deletion targets; any mutation requires a separately authorized handler.'),
  ('penta.hydrate','PentaHydrate','RESILIENCE_CONTINUITY','penta.hydrate.state-rehydration-planning','execution',
   'Plan and coordinate rehydration of state, context or caches from verified canonical sources and receipts, requiring post-operation readback. It does not itself gain provider-write, restore, deployment, certification or D3 authority.')
), targets as (
  select cfg.*,c.citizen_id,f.family_id,f.name as family_name,r.source_sha256,to_jsonb(r) as before_state
  from cfg
  join pentamocracy.citizens_v1 c on c.penta_identity=cfg.identity_key and c.active
  join pentamocracy.families_v1 f on f.family_key=cfg.family_key and f.status='ACTIVE'
  join integration_control.penta_identity_registry_v1 r on r.identity_key=cfg.identity_key and r.current and r.active
  where r.activation_state='HOLD_FAMILY'
), job_upsert as (
  insert into pentamocracy.penta_job_assignments_v1(
    citizen_id,job_key,job_role,axis,family_key,authority_ceiling,source_registry,source_state,
    activation_state,execution_eligible,metadata
  )
  select citizen_id,job_key,job_role,axis,family_key,'D2',
         'data/penta/pentaself-delegation-contracts.20260830.v1.json',
         'FOUNDER_DIRECTED_NONEXECUTABLE','ACTIVE_FAIL_CLOSED',false,
         jsonb_build_object(
           'contract','ct.penta.self-delegations.resolution.v1',
           'founder_directive','2026-08-30 clear eligible Penta Family and activation holds',
           'provider_write_authority',false,'credential_authority',false,'financial_authority',false,
           'deployment_authority',false,'certification_authority',false,'vote_or_quorum_authority',false,
           'd3_human_reserved',true,'history_preserved',true,'authority_expansion',false
         )
  from targets
  on conflict(citizen_id,job_key) do update set
    job_role=excluded.job_role,axis=excluded.axis,family_key=excluded.family_key,
    authority_ceiling=excluded.authority_ceiling,source_registry=excluded.source_registry,
    source_state=excluded.source_state,activation_state=excluded.activation_state,
    execution_eligible=false,
    metadata=pentamocracy.penta_job_assignments_v1.metadata||excluded.metadata,
    assigned_at=now()
  returning citizen_id,job_key
), citizen_update as (
  update pentamocracy.citizens_v1 c
  set family_id=t.family_id,
      metadata=c.metadata||jsonb_build_object(
        'raw_family',t.family_name,
        'canonical_family_key',t.family_key,
        'family_resolution_state','FOUNDER_DIRECTED_CANONICAL',
        'family_resolution_source','data/penta/pentaself-delegation-contracts.20260830.v1.json',
        'family_resolved_at',clock_timestamp(),
        'job_contract',t.job_key,
        'execution_eligible',false,
        'd3_human_reserved',true,
        'authority_expansion',false
      )
  from targets t
  where c.citizen_id=t.citizen_id
  returning c.citizen_id
), identity_history as (
  insert into integration_control.penta_identity_history_v1(
    identity_key,event_type,before_state,after_state,source_ref,source_sha256,event_sha256
  )
  select t.identity_key,'JOB_FAMILY_CONTRACT_ACCEPTED',t.before_state,
         jsonb_build_object(
           'identity_key',t.identity_key,'canonical_name',t.canonical_name,'family_key',t.family_key,
           'family_name',t.family_name,'job_key',t.job_key,'job_role',t.job_role,
           'activation_state','ACTIVE_FAIL_CLOSED','execution_eligible',false,
           'source_ref','data/penta/pentaself-delegation-contracts.20260830.v1.json',
           'history_preserved',true,'authority_expansion',false,'accepted_at',clock_timestamp()
         ),
         'data/penta/pentaself-delegation-contracts.20260830.v1.json',t.source_sha256,
         encode(extensions.digest(convert_to(jsonb_build_object(
           'identity_key',t.identity_key,'family_key',t.family_key,'job_key',t.job_key,
           'execution_eligible',false,'source','ct.penta.self-delegations.resolution.v1'
         )::text,'UTF8'),'sha256'),'hex')
  from targets t
  returning identity_key
), evidence_evt as (
  select chlom_runtime.append_dail_event(
    'penta.delegation.contract.evidence','penta_delegation_resolution','ct.penta.self-delegations.resolution.v1',
    jsonb_build_object(
      'target_count',(select count(*) from targets),
      'job_assignments',(select count(*) from job_upsert),
      'citizens_updated',(select count(*) from citizen_update),
      'identity_history_events',(select count(*) from identity_history),
      'identities',(select jsonb_agg(jsonb_build_object('identity_key',identity_key,'family_key',family_key,'job_key',job_key) order by identity_key) from targets),
      'execution_eligible',false,'d3_human_reserved',true,'history_preserved',true,'authority_expansion',false,
      'observed_at',clock_timestamp()
    ),
    'PentaActivation/PentaMocracy/PentaSELF',null,'PentaActivation','1.0.0',
    'ctcorr:penta-self-delegation-resolution:20260830',null,
    'Founder directive 2026-08-30; role/family resolution only; no runtime/provider/certification authority',null,'internal'
  ) event
), decision_evt as (
  select chlom_runtime.append_dail_event(
    'penta.delegation.contract.decision','penta_delegation_resolution','ct.penta.self-delegations.resolution.v1',
    jsonb_build_object(
      'decision','ACCEPT_FOUR_BOUNDED_NONEXECUTABLE_JOB_FAMILY_CONTRACTS',
      'accepted',jsonb_build_array('penta.prioritize','penta.overseer','penta.clean','penta.hydrate'),
      'still_unresolved',jsonb_build_array('PentaRG','PentaTLR'),
      'execution_eligible',false,'provider_write_authority',false,'d3_human_reserved',true,
      'history_preserved',true,'authority_expansion',false,'decided_at',clock_timestamp()
    ),
    'PentaActivation/PentaMocracy/PentaSELF',null,'PentaMocracy','1.0.0',
    'ctcorr:penta-self-delegation-resolution:20260830',null,
    'Founder directive 2026-08-30; unresolved acronyms remain HOLD',null,'internal'
  ) event
)
select 1;

comment on function integration_control.penta_identity_refresh_v1(text) is
'Canonical Identity Fabric refresh. For Penta OS records explicitly marked unresolved_reference, accepted PentaMocracy job assignments may supply the job role; all other registry precedence and fail-closed authority boundaries remain unchanged.';
