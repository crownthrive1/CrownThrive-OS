-- COS V1 immutable release-candidate scoped runtime boundary.
--
-- Problem:
--   Candidate manifests historically pinned the entire global Supabase migration
--   ledger. Any unrelated migration appended after freeze therefore looked like
--   material candidate drift, even when no migration/function consumed by COS
--   changed. That violates the immutable-candidate contract: unrelated main or
--   runtime work is a next-candidate input, not an automatic invalidator.
--
-- This migration introduces an explicit v3 manifest validation contract and a
-- read-only dependency status function. A v3 candidate pins only the migrations
-- and function definitions it declares as required dependencies. The global
-- migration ledger remains observable evidence, but extra unrelated migrations
-- do not create material drift.
--
-- This migration does not rewrite any historical candidate or certificate.

create or replace function integration_control.cos_release_candidate_manifest_validate_v3(
  p_manifest jsonb
)
returns jsonb
language plpgsql
stable
security invoker
set search_path = pg_catalog, integration_control
as $function$
declare
  v_required jsonb;
  v_functions jsonb;
  v_required_count integer := 0;
  v_function_count integer := 0;
  v_duplicate_versions integer := 0;
  v_bad_required integer := 0;
  v_bad_functions integer := 0;
  v_expected_set_sha text;
  v_computed_set_sha text;
begin
  if p_manifest is null or jsonb_typeof(p_manifest) <> 'object' then
    return jsonb_build_object('ok', false, 'decision', 'HOLD_MANIFEST_NOT_OBJECT');
  end if;

  if coalesce(p_manifest->>'contract','') <> 'ct.cos.release-candidate.manifest.v3' then
    return jsonb_build_object(
      'ok', false,
      'decision', 'HOLD_MANIFEST_CONTRACT_UNSUPPORTED',
      'observed_contract', p_manifest->>'contract',
      'required_contract', 'ct.cos.release-candidate.manifest.v3'
    );
  end if;

  if coalesce(p_manifest#>>'{runtime,dependency_scope_contract}','') <> 'ct.cos.runtime-dependency-scope.v1' then
    return jsonb_build_object(
      'ok', false,
      'decision', 'HOLD_RUNTIME_DEPENDENCY_SCOPE_CONTRACT',
      'observed_contract', p_manifest#>>'{runtime,dependency_scope_contract}',
      'required_contract', 'ct.cos.runtime-dependency-scope.v1'
    );
  end if;

  -- Scoped v3 manifests must explicitly declare that the global migration
  -- ledger is observation-only. Missing, true, string, numeric, or other values
  -- fail closed so a v3 candidate can never silently regress to global pinning.
  if p_manifest#>'{runtime,global_ledger_pinned}' is distinct from 'false'::jsonb then
    return jsonb_build_object(
      'ok', false,
      'decision', 'HOLD_GLOBAL_LEDGER_PIN_UNSUPPORTED',
      'observed_value', p_manifest#>'{runtime,global_ledger_pinned}',
      'required_value', false
    );
  end if;

  if coalesce(p_manifest#>>'{runtime,migration_statement_digest_contract}','') <> 'ct.cos.required-migration-statements-sha256.v1.jsonb-text' then
    return jsonb_build_object(
      'ok', false,
      'decision', 'HOLD_MIGRATION_STATEMENT_DIGEST_CONTRACT',
      'observed_contract', p_manifest#>>'{runtime,migration_statement_digest_contract}'
    );
  end if;

  if coalesce(p_manifest#>>'{runtime,function_digest_contract}','') <> 'ct.cos.function-definition-sha256.v1.pg_get_functiondef-utf8' then
    return jsonb_build_object(
      'ok', false,
      'decision', 'HOLD_FUNCTION_DIGEST_CONTRACT',
      'observed_contract', p_manifest#>>'{runtime,function_digest_contract}'
    );
  end if;

  v_required := p_manifest#>'{runtime,required_migrations}';
  v_functions := p_manifest#>'{runtime,function_digests}';

  if v_required is null or jsonb_typeof(v_required) <> 'array' or jsonb_array_length(v_required) = 0 then
    return jsonb_build_object('ok', false, 'decision', 'HOLD_REQUIRED_MIGRATIONS_MISSING');
  end if;

  if v_functions is null or jsonb_typeof(v_functions) <> 'object' or v_functions = '{}'::jsonb then
    return jsonb_build_object('ok', false, 'decision', 'HOLD_REQUIRED_FUNCTIONS_MISSING');
  end if;

  select count(*)::integer,
         count(*) filter (
           where coalesce(x->>'version','') !~ '^[0-9]{14}$'
              or coalesce(x->>'name','') = ''
              or coalesce(x->>'statements_sha256','') !~ '^[0-9a-f]{64}$'
         )::integer
    into v_required_count, v_bad_required
    from jsonb_array_elements(v_required) x;

  select count(*)::integer
    into v_duplicate_versions
    from (
      select x->>'version' as version
      from jsonb_array_elements(v_required) x
      group by x->>'version'
      having count(*) > 1
    ) d;

  if v_bad_required > 0 or v_duplicate_versions > 0 then
    return jsonb_build_object(
      'ok', false,
      'decision', 'HOLD_REQUIRED_MIGRATION_SET_INVALID',
      'required_count', v_required_count,
      'invalid_entries', v_bad_required,
      'duplicate_versions', v_duplicate_versions
    );
  end if;

  select count(*)::integer,
         count(*) filter (
           where coalesce(key,'') = ''
              or coalesce(value,'') !~ '^[0-9a-f]{64}$'
         )::integer
    into v_function_count, v_bad_functions
    from jsonb_each_text(v_functions);

  if v_bad_functions > 0 then
    return jsonb_build_object(
      'ok', false,
      'decision', 'HOLD_REQUIRED_FUNCTION_SET_INVALID',
      'function_count', v_function_count,
      'invalid_entries', v_bad_functions
    );
  end if;

  v_expected_set_sha := p_manifest#>>'{runtime,required_migration_set_sha256}';
  if coalesce(v_expected_set_sha,'') !~ '^[0-9a-f]{64}$' then
    return jsonb_build_object('ok', false, 'decision', 'HOLD_REQUIRED_MIGRATION_SET_DIGEST_MISSING');
  end if;

  select encode(
           extensions.digest(
             convert_to(
               coalesce(
                 jsonb_agg(
                   jsonb_build_object(
                     'version', x->>'version',
                     'name', x->>'name',
                     'statements_sha256', x->>'statements_sha256'
                   ) order by x->>'version'
                 ),
                 '[]'::jsonb
               )::text,
               'UTF8'
             ),
             'sha256'
           ),
           'hex'
         )
    into v_computed_set_sha
    from jsonb_array_elements(v_required) x;

  if v_computed_set_sha <> v_expected_set_sha then
    return jsonb_build_object(
      'ok', false,
      'decision', 'HOLD_REQUIRED_MIGRATION_SET_DIGEST_MISMATCH',
      'expected_sha256', v_expected_set_sha,
      'computed_sha256', v_computed_set_sha
    );
  end if;

  return jsonb_build_object(
    'ok', true,
    'decision', 'PASS_MANIFEST_SCOPE_VALID',
    'required_migration_count', v_required_count,
    'required_function_count', v_function_count,
    'required_migration_set_sha256', v_computed_set_sha,
    'global_ledger_pinned', false,
    'authority_created', false
  );
end;
$function$;

create or replace function integration_control.cos_release_candidate_dependency_status_v2(
  p_candidate_id text
)
returns jsonb
language plpgsql
stable
security invoker
set search_path = pg_catalog, integration_control, supabase_migrations
as $function$
declare
  v_manifest jsonb;
  v_candidate_state text;
  v_manifest_sha text;
  v_validation jsonb;
  v_required_results jsonb := '[]'::jsonb;
  v_function_results jsonb := '[]'::jsonb;
  v_required_mismatch_count integer := 0;
  v_function_mismatch_count integer := 0;
  v_missing_required_count integer := 0;
  v_missing_function_count integer := 0;
  v_required_set_live_sha text;
  v_required_set_expected_sha text;
  v_global_count bigint := 0;
  v_global_latest_version text;
  v_global_latest_name text;
  v_material_drift boolean := true;
begin
  if coalesce(btrim(p_candidate_id),'') = '' then
    return jsonb_build_object('ok', false, 'decision', 'HOLD_CANDIDATE_ID_REQUIRED');
  end if;

  select c.manifest, c.state, c.manifest_sha256
    into v_manifest, v_candidate_state, v_manifest_sha
    from integration_control.cos_release_candidates_v1 c
   where c.candidate_id = p_candidate_id;

  if not found then
    return jsonb_build_object('ok', false, 'decision', 'HOLD_CANDIDATE_NOT_FOUND', 'candidate_id', p_candidate_id);
  end if;

  v_validation := integration_control.cos_release_candidate_manifest_validate_v3(v_manifest);
  if coalesce((v_validation->>'ok')::boolean, false) is not true then
    return jsonb_build_object(
      'ok', false,
      'decision', 'HOLD_MANIFEST_SCOPE_INVALID',
      'candidate_id', p_candidate_id,
      'candidate_state', v_candidate_state,
      'manifest_sha256', v_manifest_sha,
      'validation', v_validation,
      'material_drift', true,
      'authority_created', false
    );
  end if;

  with required as (
    select x->>'version' as version,
           x->>'name' as expected_name,
           x->>'statements_sha256' as expected_statements_sha256
      from jsonb_array_elements(v_manifest#>'{runtime,required_migrations}') x
  ), live as (
    select r.version,
           r.expected_name,
           r.expected_statements_sha256,
           m.name as observed_name,
           case when m.version is null then null else
             encode(
               extensions.digest(
                 convert_to(to_jsonb(m.statements)::text,'UTF8'),
                 'sha256'
               ),
               'hex'
             )
           end as observed_statements_sha256
      from required r
      left join supabase_migrations.schema_migrations m on m.version = r.version
  ), classified as (
    select *,
           observed_name is null as missing,
           observed_name is distinct from expected_name as name_mismatch,
           observed_statements_sha256 is distinct from expected_statements_sha256 as digest_mismatch
      from live
  )
  select coalesce(
           jsonb_agg(
             jsonb_build_object(
               'version', version,
               'expected_name', expected_name,
               'observed_name', observed_name,
               'expected_statements_sha256', expected_statements_sha256,
               'observed_statements_sha256', observed_statements_sha256,
               'missing', missing,
               'name_mismatch', name_mismatch,
               'digest_mismatch', digest_mismatch,
               'match', not missing and not name_mismatch and not digest_mismatch
             ) order by version
           ),
           '[]'::jsonb
         ),
         count(*) filter (where missing or name_mismatch or digest_mismatch)::integer,
         count(*) filter (where missing)::integer,
         encode(
           extensions.digest(
             convert_to(
               coalesce(
                 jsonb_agg(
                   jsonb_build_object(
                     'version', version,
                     'name', observed_name,
                     'statements_sha256', observed_statements_sha256
                   ) order by version
                 ),
                 '[]'::jsonb
               )::text,
               'UTF8'
             ),
             'sha256'
           ),
           'hex'
         )
    into v_required_results,
         v_required_mismatch_count,
         v_missing_required_count,
         v_required_set_live_sha
    from classified;

  v_required_set_expected_sha := v_manifest#>>'{runtime,required_migration_set_sha256}';

  with expected as (
    select key as function_identity, value as expected_sha256
      from jsonb_each_text(v_manifest#>'{runtime,function_digests}')
  ), matched as (
    select e.function_identity,
           e.expected_sha256,
           p.oid,
           case when p.oid is null then null else
             encode(
               extensions.digest(
                 convert_to(pg_get_functiondef(p.oid),'UTF8'),
                 'sha256'
               ),
               'hex'
             )
           end as observed_sha256
      from expected e
      left join lateral (
        select p0.oid
          from pg_proc p0
          join pg_namespace n0 on n0.oid = p0.pronamespace
         where n0.nspname || '.' || p0.proname || '(' || pg_get_function_identity_arguments(p0.oid) || ')' = e.function_identity
           and p0.prokind = 'f'
         limit 1
      ) p on true
  ), classified as (
    select *,
           oid is null as missing,
           observed_sha256 is distinct from expected_sha256 as digest_mismatch
      from matched
  )
  select coalesce(
           jsonb_agg(
             jsonb_build_object(
               'function_identity', function_identity,
               'expected_sha256', expected_sha256,
               'observed_sha256', observed_sha256,
               'missing', missing,
               'digest_mismatch', digest_mismatch,
               'match', not missing and not digest_mismatch
             ) order by function_identity
           ),
           '[]'::jsonb
         ),
         count(*) filter (where missing or digest_mismatch)::integer,
         count(*) filter (where missing)::integer
    into v_function_results,
         v_function_mismatch_count,
         v_missing_function_count
    from classified;

  select count(*),
         (array_agg(m.version order by m.version desc))[1],
         (array_agg(m.name order by m.version desc))[1]
    into v_global_count, v_global_latest_version, v_global_latest_name
    from supabase_migrations.schema_migrations m;

  -- A v3 manifest deliberately treats the global ledger as observation-only.
  -- Only the explicitly included dependency set can create runtime drift.
  v_material_drift := v_required_mismatch_count > 0 or v_function_mismatch_count > 0;

  return jsonb_build_object(
    'ok', not v_material_drift,
    'decision', case when v_material_drift then 'HOLD_INCLUDED_RUNTIME_DEPENDENCY_DRIFT' else 'PASS_EXACT_INCLUDED_RUNTIME_DEPENDENCIES' end,
    'candidate_id', p_candidate_id,
    'candidate_state', v_candidate_state,
    'manifest_sha256', v_manifest_sha,
    'material_drift', v_material_drift,
    'required_migration_mismatch_count', v_required_mismatch_count,
    'required_migration_missing_count', v_missing_required_count,
    'required_function_mismatch_count', v_function_mismatch_count,
    'required_function_missing_count', v_missing_function_count,
    'required_migration_set_expected_sha256', v_required_set_expected_sha,
    'required_migration_set_observed_sha256', v_required_set_live_sha,
    'required_migrations', v_required_results,
    'required_functions', v_function_results,
    'global_runtime_observation', jsonb_build_object(
      'migration_count', v_global_count,
      'latest_migration_version', v_global_latest_version,
      'latest_migration_name', v_global_latest_name,
      'blocking', false
    ),
    'dependency_scope_contract', 'ct.cos.runtime-dependency-scope.v1',
    'authority_created', false
  );
end;
$function$;

comment on function integration_control.cos_release_candidate_manifest_validate_v3(jsonb)
is 'Validates ct.cos.release-candidate.manifest.v3 scoped runtime dependency semantics. It creates no release, certification, provider-write, money, rights, credential, vote/quorum, or D3 authority.';

comment on function integration_control.cos_release_candidate_dependency_status_v2(text)
is 'Read-only exact included-dependency drift status for immutable COS release candidates. Unrelated global migrations are observation-only under the v3 scope contract.';

revoke all on function integration_control.cos_release_candidate_manifest_validate_v3(jsonb) from public;
revoke all on function integration_control.cos_release_candidate_dependency_status_v2(text) from public;
grant execute on function integration_control.cos_release_candidate_manifest_validate_v3(jsonb) to service_role;
grant execute on function integration_control.cos_release_candidate_dependency_status_v2(text) to service_role;
