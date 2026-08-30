-- PentaGuardian active-family projection reconciliation v1
-- Reconciles already-active production truth into the agent/class/family projections.
-- Does not create new production authority, voting, merge, destructive, child-self-activation, provider-write, commerce, rights, or D3 authority.

update chlom_runtime.agent_templates
set canonical_name='PentaGuardian',
    lifecycle_state='active',
    metadata=coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
      'public_name','PentaGuardian',
      'prior_canonical_name','Repository Child Guardian ad Litem',
      'family_id','ct.family.repository-child-guardian.v1',
      'production_package_id','ct.framework-package.repository-child-guardian-ad-litem',
      'production_receipt_id','5885c86a-2bbc-42d0-b5e1-a5b104213010',
      'projection_reconciliation','existing_production_truth',
      'authority_expansion',false,
      'vote_effect',false,
      'D3_auto',false
    ),
    updated_at=clock_timestamp()
where agent_id='ct.agent.repository-child-guardian-ad-litem';

update institutional_federation.repository_guardian_classes_v1
set canonical_name='PentaGuardian Repository Child Guardian',
    class_state='active',
    metadata=coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
      'public_name','PentaGuardian',
      'prior_canonical_name','Repository Child Guardian ad Litem',
      'family_id','ct.family.repository-child-guardian.v1',
      'production_package_id','ct.framework-package.repository-child-guardian-ad-litem',
      'projection_reconciliation','existing_production_truth',
      'authority_expansion',false,
      'vote_effect',false,
      'D3_auto',false
    ),
    updated_at=clock_timestamp()
where class_id='ct.agent-class.repository-guardian-ad-litem.v1';

update institutional_federation.repository_family_units_v1
set canonical_name='PentaGuardian Technical Family',
    family_state='certified',
    metadata=coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
      'public_name','PentaGuardian Family',
      'prior_canonical_name','Repository Child Guardian Technical Family',
      'operational_state','active',
      'production_package_id','ct.framework-package.repository-child-guardian-ad-litem',
      'production_receipt_id','5885c86a-2bbc-42d0-b5e1-a5b104213010',
      'projection_reconciliation','existing_production_truth',
      'authority_from_titles',false,
      'legal_role',false,
      'authority_expansion',false,
      'vote_effect',false,
      'D3_auto',false
    ),
    updated_at=clock_timestamp()
where family_id='ct.family.repository-child-guardian.v1';

update institutional_federation.framework_package_registry
set metadata=coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
      'public_name','PentaGuardian',
      'family_public_name','PentaGuardian Family',
      'family_state','certified',
      'family_operational_state','active',
      'projection_reconciliation','existing_production_truth',
      'authority_expansion',false,
      'D3_auto',false
    ),
    updated_at=clock_timestamp()
where package_id='ct.framework-package.repository-child-guardian-ad-litem';

create or replace function chlom_runtime.repository_child_guardian_family_cycle_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','institutional_federation','chlom_runtime','extensions'
as $function$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_guard jsonb;
  v_family jsonb;
  v_sync jsonb;
  v_assurance jsonb;
  v_dail jsonb;
  v_state text;
  v_prod_active boolean:=false;
  v_agent_active boolean:=false;
  v_class_active boolean:=false;
  v_family_active boolean:=false;
begin
  if session_user<>'postgres' and v_role<>'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  v_guard:=chlom_runtime.repository_child_guardian_cycle_v1();
  v_family:=chlom_runtime.repository_family_rebuild_v1();
  v_sync:=chlom_runtime.repository_family_interop_sync_v1();
  v_assurance:=chlom_runtime.cie_post_activation_assurance_watch_v1();

  select exists(
    select 1 from institutional_federation.framework_package_registry
    where package_id='ct.framework-package.repository-child-guardian-ad-litem'
      and package_state='maintained'
      and operationally_enabled
      and coalesce(metadata->>'production_runtime_state','')='active'
  ) into v_prod_active;

  select exists(
    select 1 from chlom_runtime.agent_templates
    where agent_id='ct.agent.repository-child-guardian-ad-litem'
      and lifecycle_state='active'
  ) into v_agent_active;

  select exists(
    select 1 from institutional_federation.repository_guardian_classes_v1
    where class_id='ct.agent-class.repository-guardian-ad-litem.v1'
      and class_state='active'
  ) into v_class_active;

  select exists(
    select 1 from institutional_federation.repository_family_units_v1
    where family_id='ct.family.repository-child-guardian.v1'
      and family_state='certified'
      and coalesce(metadata->>'operational_state','')='active'
  ) into v_family_active;

  v_state:=case
    when v_guard->>'state' like 'PASS%'
      and v_family->>'state' like 'PASS%'
      and (v_assurance->>'state' like 'PASS%' or v_assurance->>'state'='SKIPPED_LOCKED')
      and v_prod_active and v_agent_active and v_class_active and v_family_active
      then 'PASS_ACTIVE'
    when v_guard->>'state' like 'PASS%'
      and v_family->>'state' like 'PASS%'
      and (v_assurance->>'state' like 'PASS%' or v_assurance->>'state'='SKIPPED_LOCKED')
      then 'PASS_CONTROLLED_TEST'
    else 'HOLD'
  end;

  v_dail:=chlom_runtime.append_dail_event(
    'repository.family.guardian.cycle','agent','ct.agent.repository-child-guardian-ad-litem',
    jsonb_build_object(
      'penta_name','PentaGuardian',
      'guardian',v_guard,
      'family',v_family,
      'interop_sync',v_sync,
      'cie_post_activation_assurance',v_assurance,
      'production_package_active',v_prod_active,
      'agent_projection_active',v_agent_active,
      'guardian_class_active',v_class_active,
      'family_certified_active',v_family_active,
      'family_id','ct.family.repository-child-guardian.v1',
      'family_state','certified',
      'operational_state','active',
      'human_titles_display_only',true,
      'authority_from_titles',false,
      'scheduler_slot_delta',0,
      'production_authority_rewritten',false,
      'authority_expansion',false,
      'D3_auto',false
    ),
    'ct.agent.repository-child-guardian-ad-litem',null,
    'ct.agent.repository-child-guardian-ad-litem','1.3.0',null,null,
    'Existing production PentaGuardian family cycle; state projection reconciliation only; no authority manufacture.',
    null,'restricted'
  );

  return jsonb_build_object(
    'state',v_state,
    'runtime_version','1.3.0',
    'penta_name','PentaGuardian',
    'family_id','ct.family.repository-child-guardian.v1',
    'family_state','certified',
    'operational_state','active',
    'guardian',v_guard,
    'family',v_family,
    'interop_sync',v_sync,
    'cie_post_activation_assurance',v_assurance,
    'dail_event_id',v_dail->>'event_id',
    'authority_from_titles',false,
    'scheduler_slot_delta',0,
    'production_authority_rewritten',false,
    'authority_expansion',false,
    'D3_auto',false
  );
end
$function$;

select public.chlom_append_dail_event(
  'pentaguardian.production_projection.reconciled',
  'penta',
  'ct.agent.repository-child-guardian-ad-litem',
  jsonb_build_object(
    'canonical_name','PentaGuardian',
    'agent_id','ct.agent.repository-child-guardian-ad-litem',
    'class_id','ct.agent-class.repository-guardian-ad-litem.v1',
    'family_id','ct.family.repository-child-guardian.v1',
    'package_id','ct.framework-package.repository-child-guardian-ad-litem',
    'production_receipt_id','5885c86a-2bbc-42d0-b5e1-a5b104213010',
    'reconciliation_basis','existing_production_truth',
    'agent_state','active',
    'class_state','active',
    'family_state','certified',
    'family_operational_state','active',
    'authority_expansion',false,
    'vote_effect',false,
    'merge_authority_added',false,
    'destructive_authority_added',false,
    'child_self_activation_added',false,
    'provider_write_effect',false,
    'D3_auto',false
  ),
  'ct.agent.pentacertifier',null,'ct.agent.pentacertifier','1.0.0',
  'ctcorr:pentaguardian-active-family-v1','5885c86a-2bbc-42d0-b5e1-a5b104213010',
  'D1_CONNECTOR_IMPLEMENTATION_ORIGINATOR',null,'restricted'
);