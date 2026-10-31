-- CrownThrive Penta Assignment Fabric security, registry and native-clock convergence v1

create or replace function integration_control.penta_assignment_regression_v1()
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','public'
as $$
declare
  v_results jsonb:='[]'::jsonb;
  v_failed integer:=0;
begin
  v_results:=v_results||jsonb_build_array(jsonb_build_object(
    'check','policy_active','passed',exists(
      select 1 from integration_control.penta_assignment_policy_v1
      where policy_key='ct.penta.change-institutionalization.rule.v1' and state='ACTIVE'
    )
  ));
  v_results:=v_results||jsonb_build_array(jsonb_build_object(
    'check','fifteen_family_obligations','passed',(
      select count(*)=15 from integration_control.penta_family_obligation_contracts_v1 where state='ACTIVE'
    )
  ));
  v_results:=v_results||jsonb_build_array(jsonb_build_object(
    'check','terminal_gate_requires_assignment','passed',not coalesce((
      public.penta_assignment_pr_terminal_gate_v1(
        'crownthrive1/CrownThrive-OS',0,repeat('0',40),'CLOSE'
      )->>'eligible'
    )::boolean,true)
  ));
  v_results:=v_results||jsonb_build_array(jsonb_build_object(
    'check','originator_self_certification_forbidden','passed',
    position('originator_cannot_self_certify' in pg_get_functiondef(
      'integration_control.penta_assignment_record_certification_v1(uuid,text,text,text,uuid,text,jsonb)'::regprocedure
    ))>0
  ));
  v_results:=v_results||jsonb_build_array(jsonb_build_object(
    'check','three_dail_lanes_required','passed',(
      select required_dail_lanes=array['EVIDENCE','DECISION','EXECUTION']::text[]
      from integration_control.penta_assignment_policy_v1
      where policy_key='ct.penta.change-institutionalization.rule.v1'
    )
  ));
  v_results:=v_results||jsonb_build_array(jsonb_build_object(
    'check','drive_three_way_required','passed',(
      select required_projections @> array['DRIVE_HUMAN','DRIVE_HYBRID','DRIVE_MACHINE_SHEET']::text[]
      from integration_control.penta_assignment_policy_v1
      where policy_key='ct.penta.change-institutionalization.rule.v1'
    )
  ));
  v_results:=v_results||jsonb_build_array(jsonb_build_object(
    'check','public_mutation_execute_revoked','passed',
    not has_function_privilege(
      'anon',
      'integration_control.penta_assignment_create_v1(text,text,text,text,text,text,text,jsonb,text,text,text,text,text,bigint,text,jsonb,boolean,text,jsonb)',
      'EXECUTE'
    ) and not has_function_privilege(
      'authenticated',
      'integration_control.penta_assignment_create_v1(text,text,text,text,text,text,text,jsonb,text,text,text,text,text,bigint,text,jsonb,boolean,text,jsonb)',
      'EXECUTE'
    )
  ));
  v_results:=v_results||jsonb_build_array(jsonb_build_object(
    'check','chain_gate_requires_os_projection','passed',
    position('i.os_projection_state=''READBACK_PASS''' in pg_get_functiondef(
      'integration_control.penta_assignment_refresh_chain_gate_v1(uuid)'::regprocedure
    ))>0
  ));
  v_results:=v_results||jsonb_build_array(jsonb_build_object(
    'check','native_clock_reused','passed',
    position('penta_assignment_fulfillment_tick_v1' in pg_get_functiondef('public.penta_self_tick_v1()'::regprocedure))>0
  ));
  select count(*) into v_failed
  from jsonb_array_elements(v_results) x
  where not coalesce((x->>'passed')::boolean,false);
  return jsonb_build_object(
    'contract','ct.penta.assignment-fulfillment.v1',
    'checks',jsonb_array_length(v_results),
    'passed',jsonb_array_length(v_results)-v_failed,
    'failed',v_failed,
    'all_passed',v_failed=0,
    'results',v_results,
    'observed_at',clock_timestamp()
  );
end $$;

-- Reuse the existing PentaSELF native clock. No new cron or external scheduler is created.
create or replace function public.penta_self_tick_v1()
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','penta_self','integration_control','public'
as $$
declare
  v_scheduler jsonb;
  v_failed_jobs jsonb;
  v_registry jsonb;
  v_pr_handoff jsonb;
  v_hard_repair jsonb;
  v_hard_repair_pr jsonb;
  v_assignments jsonb;
begin
  v_scheduler:=penta_self.scheduler_reconcile_v1();
  v_failed_jobs:=penta_self.failed_job_recovery_v2();
  v_registry:=public.penta_self_registry_refresh_v1();
  v_pr_handoff:=public.penta_self_pr_handoff_tick_v1();
  v_hard_repair:=penta_self.hard_repair_queue_tick_v1(3);
  v_hard_repair_pr:=penta_self.hard_repair_pr_tick_v1(10);
  v_assignments:=integration_control.penta_assignment_fulfillment_tick_v1(25);
  return jsonb_build_object(
    'service','ct.penta.self.tick.v3',
    'state',case
      when coalesce((v_hard_repair->>'held')::integer,0)>0
        or coalesce((v_hard_repair_pr->>'held')::integer,0)>0
      then 'degraded' else 'completed' end,
    'scheduler',v_scheduler,
    'failed_jobs',v_failed_jobs,
    'registry',v_registry,
    'pr_handoff',v_pr_handoff,
    'hard_repair',v_hard_repair,
    'hard_repair_pr',v_hard_repair_pr,
    'assignment_fulfillment',v_assignments,
    'assignment_contract','ct.penta.assignment-fulfillment.v1',
    'institutionalization_contract','ct.penta.institutionalization.v1',
    'pr_terminalization_contract','ct.penta.pr-terminalization.v4',
    'surgical_care_family','SURGICAL_CARE',
    'new_clock_created',false,
    'native_clock','ct-penta-self-v1',
    'rollback_rule','surgery_caused_regression_only',
    'immediate_retry_limit',1,
    'originator_self_certification',false,
    'direct_main',false,
    'authority_created',false,
    'at',clock_timestamp()
  );
end $$;

-- Targeted least-privilege controls for the new execution surface.
do $$
declare r record;
begin
  for r in
    select n.nspname,p.proname,pg_get_function_identity_arguments(p.oid) args
    from pg_proc p join pg_namespace n on n.oid=p.pronamespace
    where (n.nspname='integration_control' and p.proname like 'penta_assignment_%')
       or (n.nspname='penta_docs' and p.proname='project_assignment_v1')
       or (n.nspname='public' and p.proname='penta_assignment_pr_terminal_gate_v1')
  loop
    execute format('revoke execute on function %I.%I(%s) from public, anon, authenticated',r.nspname,r.proname,r.args);
    execute format('grant execute on function %I.%I(%s) to service_role',r.nspname,r.proname,r.args);
  end loop;
end $$;

revoke all on public.penta_assignment_institutionalization_status_v1 from public,anon,authenticated;
grant select on public.penta_assignment_institutionalization_status_v1 to service_role;

insert into public.penta_system_registry(
  system_key,canonical_name,category,purpose,risk_ceiling,maturity,version,runtime_ref,
  docs_ref,public_exposure,authority_boundary,metadata,last_verified_at,updated_at
) values
(
  'penta.assignment-fabric','Penta Assignment Fulfillment Fabric','coordination_control',
  'Routes D0-D2 assignments to owning Pentas and families, requires owner results, and blocks terminalization until institutional completion.',
  'D2','implemented','1.0.0','function:integration_control.penta_assignment_fulfillment_tick_v1(integer)',
  'docs/penta/PENTA_ASSIGNMENT_INSTITUTIONALIZATION_V1.md',false,
  'No self-certification, D3, money movement, credential creation, rights grant or authority expansion.',
  jsonb_build_object(
    'stable_contract_id','ct.penta.assignment-fulfillment.v1',
    'implementation_state','active_pending_independent_certification',
    'owner','PentaBuild/PentaCensus/PentaWire/PentaSELF',
    'certifier','PentaCertify','native_clock','ct-penta-self-v1',
    'new_clock_created',false,'authority_expansion',false
  ),now(),now()
),
(
  'penta.docs.institutionalization','PentaDocs Institutionalization Projection','knowledge_data',
  'Projects assignment and change evidence, three-DAIL lineage, Drive references and certification into canonical PentaDocs records.',
  'D2','implemented','1.0.0','function:penta_docs.project_assignment_v1(uuid)',
  'docs/penta/PENTA_ASSIGNMENT_INSTITUTIONALIZATION_V1.md',false,
  'Documentation projection only; no independent certification, provider authority or D3 authority.',
  jsonb_build_object(
    'stable_contract_id','ct.penta.institutionalization.v1',
    'implementation_state','active_pending_independent_certification',
    'owner','PentaDocs/PentaDrive/PentaSync/PentaSerialized',
    'certifier','PentaCertify','authority_expansion',false
  ),now(),now()
),
(
  'penta.pr-terminalization-v4','Penta PR Institutional Terminalization V4','github_lifecycle',
  'Allows merge or close only after exact-head task completion, three-DAIL, PentaDocs, Drive mirror, chain PASS and independent certification.',
  'D2','implemented','4.0.0','edge:penta-pr-terminal-provider@4',
  'docs/penta/PENTA_ASSIGNMENT_INSTITUTIONALIZATION_V1.md',false,
  'Exact-head provider terminal actions only after institutional gate PASS; no deadline-only closure.',
  jsonb_build_object(
    'stable_contract_id','ct.penta.pr-terminalization.v4',
    'implementation_state','pending_edge_deployment_and_independent_certification',
    'previous_provider_version',3,
    'previous_provider_sha256','c293663a3a82429722f09c80ea7842386006335bf3dc6385ab7bdcf00967d5fd',
    'owner','PentaPR/PentaMerge/PentaCloser/PentaBuild',
    'certifier','PentaCertify','authority_expansion',false
  ),now(),now()
)
on conflict(system_key) do update set
  canonical_name=excluded.canonical_name,category=excluded.category,purpose=excluded.purpose,
  risk_ceiling=excluded.risk_ceiling,maturity=excluded.maturity,version=excluded.version,
  runtime_ref=excluded.runtime_ref,docs_ref=excluded.docs_ref,
  public_exposure=excluded.public_exposure,authority_boundary=excluded.authority_boundary,
  metadata=public.penta_system_registry.metadata||excluded.metadata,updated_at=now();

update integration_control.penta_family_runtime_v1 set
  metadata=metadata||jsonb_build_object(
    'assignment_contract','ct.penta.assignment-fulfillment.v1',
    'institutionalization_contract','ct.penta.institutionalization.v1',
    'terminalization_contract','ct.penta.pr-terminalization.v4',
    'obligation_contract_bound',true,
    'member_runtime_authority_unchanged',true,
    'coordination_certification_pending',true,
    'new_clock_created',false,
    'authority_expansion',false
  ),
  updated_at=now();
