-- CHLOM Institutionalization Package Runtime v2 corrective migration.
-- Preserves v1/v2 evidence and fixes the no-record public status branch.

create or replace function public.chlom_wallet_institutionalization_package_status_v2()
returns jsonb
language plpgsql
stable
security definer
set search_path=chlom_wallet,pg_catalog,pg_temp
as $$
declare
  p chlom_wallet.institutionalization_packages_v2%rowtype;
  v_package_found boolean:=false;
  v_public integer:=0;
  v_internal integer:=0;
  v_restricted integer:=0;
  v_projection integer:=0;
  v_crosswalk integer:=0;
  v_canary text;
  v_legacy_policies integer:=0;
  v_legacy_algorithms integer:=0;
  v_legacy_runs integer:=0;
begin
  select * into p
  from chlom_wallet.institutionalization_packages_v2
  where not is_canary
  order by created_at desc
  limit 1;
  v_package_found:=found;

  select count(*) into v_crosswalk
  from chlom_wallet.institutionalization_algorithm_crosswalk_v2;

  select result into v_canary
  from chlom_wallet.institutionalization_package_canary_runs_v2
  order by created_at desc
  limit 1;

  select count(*) into v_legacy_policies
  from chlom_wallet.institutionalization_policies_v1;

  select count(*) into v_legacy_algorithms
  from chlom_wallet.institutionalization_algorithms_v1;

  select count(*) into v_legacy_runs
  from chlom_wallet.institutionalization_runs_v1
  where not is_canary;

  if not v_package_found then
    return jsonb_build_object(
      'contract','ct.wallet.institutionalization-package-status.v2',
      'state','NO_RECORDED_PACKAGE_V2',
      'phase','2.99',
      'package_id',null,
      'semantic_version',null,
      'package_digest_sha256',null,
      'source_snapshot',null,
      'compiler',jsonb_build_object(
        'tool_id','ct.tool.chlom-institutionalization-compiler',
        'algorithm_id','ct.algorithm.chlom.institutionalization-compiler.v1',
        'semantic_version','1.0.0'
      ),
      'counts',jsonb_build_object(
        'artifacts',0,'public',0,'internal',0,'restricted',0,
        'public_projection',0,'algorithms',0,'gaps',0,'completeness_score',0
      ),
      'control_states',null,
      'manifest_ref',null,
      'recorded_at',null,
      'algorithm_crosswalk_count',v_crosswalk,
      'latest_canary',v_canary,
      'legacy_runtime',jsonb_build_object(
        'policies',v_legacy_policies,
        'algorithm_rows',v_legacy_algorithms,
        'recorded_runs',v_legacy_runs,
        'reconciliation_state','V2_RUNTIME_READY_PACKAGE_NOT_REGISTERED'
      ),
      'hard_boundaries',jsonb_build_object(
        'provider_write',false,'signing',false,'custody',false,
        'token_issuance',false,'money_movement',false,
        'production_rights_grant',false,'chain_broadcast',false,
        'effective_price_publication',false,'checkout_activation',false,
        'phase_advancement',false,'merge_authorized',false
      )
    );
  end if;

  select
    count(*) filter(where classification='public'),
    count(*) filter(where classification='internal'),
    count(*) filter(where classification='restricted'),
    count(*) filter(where public_projection)
  into v_public,v_internal,v_restricted,v_projection
  from chlom_wallet.institutionalization_package_artifacts_v2
  where package_record_id=p.package_record_id;

  return jsonb_build_object(
    'contract','ct.wallet.institutionalization-package-status.v2',
    'state',p.package_state,
    'phase','2.99',
    'package_id',p.package_id,
    'semantic_version',p.semantic_version,
    'package_digest_sha256',p.package_digest_sha256,
    'source_snapshot',jsonb_build_object(
      'repository',p.source_repository,
      'branch',p.source_branch,
      'head_sha',p.source_head_sha,
      'observed_on',p.source_observed_on
    ),
    'compiler',jsonb_build_object(
      'tool_id',p.compiler_tool_id,
      'algorithm_id',p.compiler_algorithm_id,
      'semantic_version',p.compiler_semantic_version
    ),
    'counts',jsonb_build_object(
      'artifacts',p.artifact_count,
      'public',v_public,
      'internal',v_internal,
      'restricted',v_restricted,
      'public_projection',v_projection,
      'algorithms',p.algorithm_count,
      'gaps',p.gap_count,
      'completeness_score',p.completeness_score
    ),
    'control_states',jsonb_build_object(
      'docs',p.docs_state,
      'security',p.security_state,
      'privacy',p.privacy_state,
      'rights',p.rights_state,
      'commercialization',p.commercialization_state,
      'rollback',p.rollback_state,
      'scheduler',p.scheduler_state,
      'provenance',p.provenance_state,
      'ai_mode',p.ai_mode
    ),
    'manifest_ref',p.manifest_ref,
    'recorded_at',p.created_at,
    'algorithm_crosswalk_count',v_crosswalk,
    'latest_canary',v_canary,
    'legacy_runtime',jsonb_build_object(
      'policies',v_legacy_policies,
      'algorithm_rows',v_legacy_algorithms,
      'recorded_runs',v_legacy_runs,
      'reconciliation_state','V2_PACKAGE_INDEXED_LEGACY_V1_PRESERVED'
    ),
    'hard_boundaries',jsonb_build_object(
      'provider_write',false,'signing',false,'custody',false,
      'token_issuance',false,'money_movement',false,
      'production_rights_grant',false,'chain_broadcast',false,
      'effective_price_publication',false,'checkout_activation',false,
      'phase_advancement',false,'merge_authorized',false
    )
  );
end;
$$;

revoke all on function public.chlom_wallet_institutionalization_package_status_v2() from public;
grant execute on function public.chlom_wallet_institutionalization_package_status_v2() to anon,authenticated,service_role;
