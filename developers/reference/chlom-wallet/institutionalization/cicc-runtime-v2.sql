create extension if not exists pgcrypto;

create table if not exists chlom_wallet.institutionalization_packages_v2 (
  package_record_id uuid primary key default gen_random_uuid(),
  package_id text not null,
  semantic_version text not null,
  package_state text not null check (package_state in ('PASS_CONTROLLED_TEST_INSTITUTIONALIZATION','HOLD_INSTITUTIONALIZATION_GAPS')),
  source_repository text not null,
  source_branch text not null,
  source_head_sha text not null check (source_head_sha ~ '^[0-9a-f]{40}$'),
  source_observed_on date not null,
  compiler_tool_id text not null,
  compiler_algorithm_id text not null,
  compiler_semantic_version text not null,
  package_digest_sha256 text not null unique check (package_digest_sha256 ~ '^[0-9a-f]{64}$'),
  server_record_digest_sha256 text not null check (server_record_digest_sha256 ~ '^[0-9a-f]{64}$'),
  artifact_count integer not null check (artifact_count >= 11),
  algorithm_count integer not null check (algorithm_count >= 2),
  gap_count integer not null check (gap_count >= 0),
  completeness_score integer not null check (completeness_score between 0 and 100),
  docs_state text not null,
  security_state text not null,
  privacy_state text not null,
  rights_state text not null,
  commercialization_state text not null,
  rollback_state text not null,
  scheduler_state text not null,
  provenance_state text not null,
  ai_mode text not null,
  correlation_id text not null unique check (correlation_id ~ '^[A-Za-z0-9._:@-]{8,200}$'),
  manifest_ref text not null,
  manifest_body jsonb not null,
  is_canary boolean not null default false,
  provider_write boolean not null default false check (not provider_write),
  signing boolean not null default false check (not signing),
  custody boolean not null default false check (not custody),
  token_issuance boolean not null default false check (not token_issuance),
  money_movement boolean not null default false check (not money_movement),
  production_rights_grant boolean not null default false check (not production_rights_grant),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  effective_price_publication boolean not null default false check (not effective_price_publication),
  checkout_activation boolean not null default false check (not checkout_activation),
  phase_advancement boolean not null default false check (not phase_advancement),
  merge_authorized boolean not null default false check (not merge_authorized),
  created_at timestamptz not null default now(),
  unique (package_id, semantic_version)
);

create table if not exists chlom_wallet.institutionalization_package_artifacts_v2 (
  artifact_record_id uuid primary key default gen_random_uuid(),
  package_record_id uuid not null references chlom_wallet.institutionalization_packages_v2(package_record_id) on delete restrict,
  artifact_id text not null,
  artifact_path text not null,
  artifact_kind text not null,
  classification text not null check (classification in ('public','internal','restricted')),
  owner_agent_id text not null,
  artifact_state text not null,
  public_projection boolean not null,
  artifact_sha256 text not null check (artifact_sha256 ~ '^[0-9a-f]{64}$'),
  size_bytes bigint not null check (size_bytes > 0),
  secret_shape_detected boolean not null default false check (not secret_shape_detected),
  source_ref text not null,
  created_at timestamptz not null default now(),
  unique (package_record_id, artifact_id),
  unique (package_record_id, artifact_path),
  check (not public_projection or classification='public')
);

create table if not exists chlom_wallet.institutionalization_package_algorithms_v2 (
  algorithm_record_id uuid primary key default gen_random_uuid(),
  package_record_id uuid not null references chlom_wallet.institutionalization_packages_v2(package_record_id) on delete restrict,
  algorithm_id text not null,
  semantic_version text not null,
  classification text not null,
  source_paths jsonb not null,
  invariants jsonb not null,
  proprietary_scope text not null,
  external_dependencies jsonb not null,
  authority_effect text not null default 'none' check (authority_effect='none'),
  provider_write boolean not null default false check (not provider_write),
  money_movement boolean not null default false check (not money_movement),
  rights_grant boolean not null default false check (not rights_grant),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  created_at timestamptz not null default now(),
  unique (package_record_id, algorithm_id)
);

create table if not exists chlom_wallet.institutionalization_package_docs_impacts_v2 (
  docs_impact_record_id uuid primary key default gen_random_uuid(),
  package_record_id uuid not null unique references chlom_wallet.institutionalization_packages_v2(package_record_id) on delete restrict,
  docs_state text not null,
  public_pages jsonb not null,
  machine_pages jsonb not null,
  navigation_action text,
  editor_navigation_metadata_state text,
  fake_navigation_write_created boolean not null default false check (not fake_navigation_write_created),
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.institutionalization_package_gaps_v2 (
  gap_record_id uuid primary key default gen_random_uuid(),
  package_record_id uuid not null references chlom_wallet.institutionalization_packages_v2(package_record_id) on delete restrict,
  gap_sequence integer not null check (gap_sequence >= 1),
  gap_code text not null,
  gap_category text not null,
  severity text not null,
  artifact_id text,
  algorithm_id text,
  handoff_agent_id text,
  gap_body jsonb not null,
  created_at timestamptz not null default now(),
  unique (package_record_id, gap_sequence)
);

create table if not exists chlom_wallet.institutionalization_algorithm_crosswalk_v2 (
  crosswalk_id text primary key,
  legacy_registry_id text not null,
  legacy_algorithm_id text not null,
  current_algorithm_id text not null,
  relationship text not null,
  crosswalk_state text not null check (crosswalk_state in ('RECONCILED','SUPERSEDED_COMPONENT','DOMAIN_EXTENSION')),
  authority_effect text not null default 'none' check (authority_effect='none'),
  source_ref text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (legacy_registry_id, legacy_algorithm_id, current_algorithm_id)
);

create table if not exists chlom_wallet.institutionalization_package_canary_runs_v2 (
  canary_run_id uuid primary key default gen_random_uuid(),
  result text not null,
  valid_package_passed boolean not null,
  duplicate_idempotency_passed boolean not null,
  mutation_rejected boolean not null,
  secret_shape_rejected boolean not null,
  restricted_public_projection_rejected boolean not null,
  hard_boundary_rejected boolean not null,
  ai_authority_rejected boolean not null,
  duplicate_artifact_rejected boolean not null,
  gap_state_mismatch_rejected boolean not null,
  evidence jsonb not null default '{}'::jsonb,
  provider_write boolean not null default false check (not provider_write),
  signing boolean not null default false check (not signing),
  custody boolean not null default false check (not custody),
  token_issuance boolean not null default false check (not token_issuance),
  money_movement boolean not null default false check (not money_movement),
  production_rights_grant boolean not null default false check (not production_rights_grant),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  phase_advancement boolean not null default false check (not phase_advancement),
  merge_authorized boolean not null default false check (not merge_authorized),
  created_at timestamptz not null default now()
);

create or replace function chlom_wallet.reject_institutionalization_package_mutation_v2()
returns trigger
language plpgsql
set search_path=pg_catalog
as $$
begin
  raise exception 'institutionalization_package_records_are_append_only';
end;
$$;

do $$
declare t text;
begin
  foreach t in array array[
    'institutionalization_packages_v2',
    'institutionalization_package_artifacts_v2',
    'institutionalization_package_algorithms_v2',
    'institutionalization_package_docs_impacts_v2',
    'institutionalization_package_gaps_v2',
    'institutionalization_algorithm_crosswalk_v2',
    'institutionalization_package_canary_runs_v2'
  ] loop
    execute format('drop trigger if exists reject_%I_mutation_v2 on chlom_wallet.%I',t,t);
    execute format('create trigger reject_%I_mutation_v2 before update or delete on chlom_wallet.%I for each row execute function chlom_wallet.reject_institutionalization_package_mutation_v2()',t,t);
    execute format('alter table chlom_wallet.%I enable row level security',t);
    execute format('drop policy if exists deny_all_%I on chlom_wallet.%I',t,t);
    execute format('create policy deny_all_%I on chlom_wallet.%I as restrictive for all to public using(false) with check(false)',t,t);
    execute format('revoke all on chlom_wallet.%I from public,anon,authenticated',t);
  end loop;
end;
$$;

create or replace function chlom_wallet.validate_institutionalization_package_v2(p_manifest jsonb)
returns jsonb
language plpgsql
stable
security definer
set search_path=chlom_wallet,pg_catalog,pg_temp
as $$
declare
  v_errors jsonb:='[]'::jsonb;
  v_text text:=coalesce(p_manifest::text,'');
  v_artifact_count integer:=0;
  v_algorithm_count integer:=0;
  v_gap_count integer:=0;
  v_public_count integer:=0;
  v_internal_count integer:=0;
  v_restricted_count integer:=0;
  v_projection_count integer:=0;
  v_distinct_artifact_ids integer:=0;
  v_distinct_artifact_paths integer:=0;
  v_distinct_algorithm_ids integer:=0;
  v_key text;
begin
  if p_manifest is null or jsonb_typeof(p_manifest)<>'object' then
    return jsonb_build_object('result','FAIL','errors',jsonb_build_array('package_object_required'));
  end if;

  if p_manifest->>'schema_version'<>'1.0.0' then v_errors:=v_errors||jsonb_build_array('schema_version_invalid'); end if;
  if p_manifest->>'package_id' !~ '^ct[.]package[.][A-Za-z0-9._-]+$' then v_errors:=v_errors||jsonb_build_array('package_id_invalid'); end if;
  if p_manifest->>'semantic_version' !~ '^[0-9]+[.][0-9]+[.][0-9]+([.-][A-Za-z0-9.-]+)?$' then v_errors:=v_errors||jsonb_build_array('semantic_version_invalid'); end if;
  if p_manifest->>'state' not in ('PASS_CONTROLLED_TEST_INSTITUTIONALIZATION','HOLD_INSTITUTIONALIZATION_GAPS') then v_errors:=v_errors||jsonb_build_array('package_state_invalid'); end if;
  if p_manifest->>'package_digest_sha256' !~ '^[0-9a-f]{64}$' then v_errors:=v_errors||jsonb_build_array('package_digest_invalid'); end if;

  if jsonb_typeof(p_manifest->'source_snapshot') is distinct from 'object' then
    v_errors:=v_errors||jsonb_build_array('source_snapshot_required');
  else
    if p_manifest#>>'{source_snapshot,repository}'<>'crownthrive1/CrownThrive-Support' then v_errors:=v_errors||jsonb_build_array('source_repository_invalid'); end if;
    if p_manifest#>>'{source_snapshot,branch}' !~ '^chlom-wallet/[A-Za-z0-9._/-]+$' then v_errors:=v_errors||jsonb_build_array('source_branch_invalid'); end if;
    if p_manifest#>>'{source_snapshot,head_sha}' !~ '^[0-9a-f]{40}$' then v_errors:=v_errors||jsonb_build_array('source_head_sha_invalid'); end if;
    if p_manifest#>>'{source_snapshot,observed_on}' !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then v_errors:=v_errors||jsonb_build_array('source_observed_on_invalid'); end if;
  end if;

  if jsonb_typeof(p_manifest->'compiler') is distinct from 'object' then
    v_errors:=v_errors||jsonb_build_array('compiler_required');
  else
    if p_manifest#>>'{compiler,tool_id}'<>'ct.tool.chlom-institutionalization-compiler' then v_errors:=v_errors||jsonb_build_array('compiler_tool_invalid'); end if;
    if p_manifest#>>'{compiler,algorithm_id}'<>'ct.algorithm.chlom.institutionalization-compiler.v1' then v_errors:=v_errors||jsonb_build_array('compiler_algorithm_invalid'); end if;
    if coalesce((p_manifest#>>'{compiler,deterministic}')::boolean,false) is not true then v_errors:=v_errors||jsonb_build_array('compiler_not_deterministic'); end if;
    if coalesce((p_manifest#>>'{compiler,network_access}')::boolean,true)
       or coalesce((p_manifest#>>'{compiler,signing}')::boolean,true)
       or coalesce((p_manifest#>>'{compiler,provider_write}')::boolean,true)
       or coalesce((p_manifest#>>'{compiler,chain_broadcast}')::boolean,true)
       or coalesce((p_manifest#>>'{compiler,money_movement}')::boolean,true) then
      v_errors:=v_errors||jsonb_build_array('compiler_authority_boundary_invalid');
    end if;
  end if;

  if jsonb_typeof(p_manifest->'artifact_inventory') is distinct from 'array' then
    v_errors:=v_errors||jsonb_build_array('artifact_inventory_required');
  else
    v_artifact_count:=jsonb_array_length(p_manifest->'artifact_inventory');
    select count(distinct a->>'artifact_id'),count(distinct a->>'path'),
           count(*) filter(where a->>'classification'='public'),
           count(*) filter(where a->>'classification'='internal'),
           count(*) filter(where a->>'classification'='restricted'),
           count(*) filter(where a->'public_projection'='true'::jsonb)
      into v_distinct_artifact_ids,v_distinct_artifact_paths,v_public_count,v_internal_count,v_restricted_count,v_projection_count
    from jsonb_array_elements(p_manifest->'artifact_inventory') a;

    if v_artifact_count<11 then v_errors:=v_errors||jsonb_build_array('artifact_count_below_minimum'); end if;
    if v_distinct_artifact_ids<>v_artifact_count then v_errors:=v_errors||jsonb_build_array('duplicate_artifact_id'); end if;
    if v_distinct_artifact_paths<>v_artifact_count then v_errors:=v_errors||jsonb_build_array('duplicate_artifact_path'); end if;
    if exists(
      select 1 from jsonb_array_elements(p_manifest->'artifact_inventory') a
      where a->>'artifact_id' !~ '^ct[.]artifact[.][A-Za-z0-9._-]+$'
         or a->>'path' is null or a->>'path'='' or a->>'path' like '/%' or a->>'path' like '%..%'
         or a->>'kind' is null or a->>'kind'=''
         or a->>'classification' not in ('public','internal','restricted')
         or a->>'owner_agent_id' !~ '^ct[.][A-Za-z0-9._-]+$'
         or a->>'sha256' !~ '^[0-9a-f]{64}$'
         or case when a->>'size_bytes' ~ '^[0-9]+$' then (a->>'size_bytes')::bigint<=0 else true end
         or a->'secret_shape_detected'<>'false'::jsonb
         or (a->'public_projection'='true'::jsonb and a->>'classification'<>'public')
    ) then v_errors:=v_errors||jsonb_build_array('artifact_contract_invalid'); end if;

    if jsonb_typeof(p_manifest->'artifact_counts') is distinct from 'object'
       or p_manifest#>>'{artifact_counts,total}' !~ '^[0-9]+$'
       or (p_manifest#>>'{artifact_counts,total}')::integer<>v_artifact_count
       or (p_manifest#>>'{artifact_counts,public}')::integer<>v_public_count
       or (p_manifest#>>'{artifact_counts,internal}')::integer<>v_internal_count
       or (p_manifest#>>'{artifact_counts,restricted}')::integer<>v_restricted_count
       or (p_manifest#>>'{artifact_counts,public_projection}')::integer<>v_projection_count then
      v_errors:=v_errors||jsonb_build_array('artifact_counts_mismatch');
    end if;
  end if;

  if jsonb_typeof(p_manifest->'algorithm_registry') is distinct from 'array' then
    v_errors:=v_errors||jsonb_build_array('algorithm_registry_required');
  else
    v_algorithm_count:=jsonb_array_length(p_manifest->'algorithm_registry');
    select count(distinct a->>'algorithm_id') into v_distinct_algorithm_ids
    from jsonb_array_elements(p_manifest->'algorithm_registry') a;
    if v_algorithm_count<2 then v_errors:=v_errors||jsonb_build_array('algorithm_count_below_minimum'); end if;
    if v_distinct_algorithm_ids<>v_algorithm_count then v_errors:=v_errors||jsonb_build_array('duplicate_algorithm_id'); end if;
    if exists(
      select 1 from jsonb_array_elements(p_manifest->'algorithm_registry') a
      where a->>'algorithm_id' !~ '^ct[.]algorithm[.][A-Za-z0-9._-]+$'
         or a->>'semantic_version' is null
         or jsonb_typeof(a->'source_paths') is distinct from 'array'
         or jsonb_array_length(case when jsonb_typeof(a->'source_paths')='array' then a->'source_paths' else '[]'::jsonb end)<1
         or jsonb_typeof(a->'invariants') is distinct from 'array'
         or jsonb_array_length(case when jsonb_typeof(a->'invariants')='array' then a->'invariants' else '[]'::jsonb end)<1
         or a->>'authority_effect'<>'none'
         or a->'provider_write'<>'false'::jsonb
         or a->'money_movement'<>'false'::jsonb
         or a->'rights_grant'<>'false'::jsonb
         or a->'chain_broadcast'<>'false'::jsonb
    ) then v_errors:=v_errors||jsonb_build_array('algorithm_contract_invalid'); end if;

    if exists(
      select 1
      from jsonb_array_elements(p_manifest->'algorithm_registry') a
      cross join lateral jsonb_array_elements_text(case when jsonb_typeof(a->'source_paths')='array' then a->'source_paths' else '[]'::jsonb end) p(path)
      where not exists(select 1 from jsonb_array_elements(p_manifest->'artifact_inventory') i where i->>'path'=p.path)
    ) then v_errors:=v_errors||jsonb_build_array('algorithm_source_not_in_inventory'); end if;
  end if;

  foreach v_key in array array['docs_impact','security','privacy','rights','commercialization','rollback','scheduler','provenance','output_contract'] loop
    if jsonb_typeof(p_manifest->v_key) is distinct from 'object' or p_manifest->v_key='{}'::jsonb then
      v_errors:=v_errors||jsonb_build_array('missing_control_section_'||v_key);
    end if;
  end loop;
  if jsonb_typeof(p_manifest->'third_party_dependencies') is distinct from 'array'
     or jsonb_array_length(case when jsonb_typeof(p_manifest->'third_party_dependencies')='array' then p_manifest->'third_party_dependencies' else '[]'::jsonb end)<1 then
    v_errors:=v_errors||jsonb_build_array('third_party_dependencies_required');
  end if;

  if jsonb_typeof(p_manifest->'ai_governance') is distinct from 'object'
     or coalesce((p_manifest#>>'{ai_governance,advisory_only}')::boolean,false) is not true
     or coalesce((p_manifest#>>'{ai_governance,decision_authority}')::boolean,true)
     or coalesce((p_manifest#>>'{ai_governance,write_authority}')::boolean,true)
     or coalesce((p_manifest#>>'{ai_governance,output_requires_independent_review}')::boolean,false) is not true
     or coalesce((p_manifest#>>'{ai_governance,automatic_release}')::boolean,true) then
    v_errors:=v_errors||jsonb_build_array('ai_governance_boundary_invalid');
  end if;

  if jsonb_typeof(p_manifest->'hard_boundaries') is distinct from 'object'
     or exists(select 1 from jsonb_each(case when jsonb_typeof(p_manifest->'hard_boundaries')='object' then p_manifest->'hard_boundaries' else '{}'::jsonb end) e where e.value<>'false'::jsonb) then
    v_errors:=v_errors||jsonb_build_array('hard_boundary_true_or_missing');
  end if;

  if coalesce((p_manifest#>>'{commercialization,effective_offer}')::boolean,true)
     or coalesce((p_manifest#>>'{commercialization,public_price}')::boolean,true)
     or coalesce((p_manifest#>>'{commercialization,stripe_objects_created}')::boolean,true)
     or coalesce((p_manifest#>>'{commercialization,checkout_enabled}')::boolean,true) then
    v_errors:=v_errors||jsonb_build_array('commercialization_boundary_invalid');
  end if;
  if coalesce((p_manifest#>>'{rights,production_rights_grant}')::boolean,true) then
    v_errors:=v_errors||jsonb_build_array('rights_boundary_invalid');
  end if;
  if coalesce((p_manifest#>>'{docs_impact,fake_navigation_write_created}')::boolean,true) then
    v_errors:=v_errors||jsonb_build_array('documentation_navigation_boundary_invalid');
  end if;

  if jsonb_typeof(p_manifest->'gap_analysis') is distinct from 'object'
     or p_manifest#>>'{gap_analysis,gap_count}' !~ '^[0-9]+$'
     or p_manifest#>>'{gap_analysis,blocking_gap_count}' !~ '^[0-9]+$'
     or p_manifest#>>'{gap_analysis,completeness_score}' !~ '^[0-9]+$'
     or jsonb_typeof(p_manifest#>'{gap_analysis,gaps}') is distinct from 'array' then
    v_errors:=v_errors||jsonb_build_array('gap_analysis_invalid');
  else
    v_gap_count:=jsonb_array_length(p_manifest#>'{gap_analysis,gaps}');
    if (p_manifest#>>'{gap_analysis,gap_count}')::integer<>v_gap_count then v_errors:=v_errors||jsonb_build_array('gap_count_mismatch'); end if;
    if p_manifest#>>'{gap_analysis,disposition}'<>p_manifest->>'state' then v_errors:=v_errors||jsonb_build_array('gap_disposition_state_mismatch'); end if;
    if p_manifest->>'state'='PASS_CONTROLLED_TEST_INSTITUTIONALIZATION'
       and (v_gap_count<>0 or (p_manifest#>>'{gap_analysis,blocking_gap_count}')::integer<>0 or (p_manifest#>>'{gap_analysis,completeness_score}')::integer<>100) then
      v_errors:=v_errors||jsonb_build_array('pass_state_with_gaps');
    end if;
    if p_manifest->>'state'='HOLD_INSTITUTIONALIZATION_GAPS' and v_gap_count=0 then v_errors:=v_errors||jsonb_build_array('hold_state_without_gaps'); end if;
  end if;

  if v_text ~ 'sk_live_[A-Za-z0-9]{16,}'
     or v_text ~ 'rk_live_[A-Za-z0-9]{16,}'
     or v_text ~ 'whsec_[A-Za-z0-9]{16,}'
     or v_text ~ 'sb_secret_[A-Za-z0-9._-]{16,}'
     or v_text ~ '-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----' then
    v_errors:=v_errors||jsonb_build_array('secret_shaped_material_detected');
  end if;
  if v_text ~* '"(private_key|seed_phrase|mnemonic|credential_value|secret_manager_ref|provider_credential)"[[:space:]]*:' then
    v_errors:=v_errors||jsonb_build_array('private_material_key_detected');
  end if;

  return jsonb_build_object(
    'result',case when jsonb_array_length(v_errors)=0 then 'PASS' else 'FAIL' end,
    'errors',v_errors,
    'artifact_count',v_artifact_count,
    'algorithm_count',v_algorithm_count,
    'gap_count',v_gap_count,
    'public_artifact_count',v_public_count,
    'internal_artifact_count',v_internal_count,
    'restricted_artifact_count',v_restricted_count,
    'public_projection_count',v_projection_count
  );
end;
$$;

create or replace function chlom_wallet.register_institutionalization_package_v2(
  p_manifest jsonb,
  p_source_ref text,
  p_correlation_id text
)
returns jsonb
language plpgsql
security definer
set search_path=chlom_wallet,extensions,pg_catalog,pg_temp
as $$
declare
  v_validation jsonb;
  v_existing chlom_wallet.institutionalization_packages_v2%rowtype;
  v_record uuid;
  v_server_digest text;
  v_is_canary boolean;
  v_artifacts integer:=0;
  v_algorithms integer:=0;
  v_gaps integer:=0;
begin
  if p_source_ref is null or length(p_source_ref)<8 or length(p_source_ref)>1000 then raise exception 'source_ref_invalid'; end if;
  if p_correlation_id !~ '^[A-Za-z0-9._:@-]{8,200}$' then raise exception 'correlation_id_invalid'; end if;
  v_validation:=chlom_wallet.validate_institutionalization_package_v2(p_manifest);
  if v_validation->>'result'<>'PASS' then raise exception 'institutionalization_package_validation_failed:%',v_validation; end if;

  select * into v_existing from chlom_wallet.institutionalization_packages_v2 where correlation_id=p_correlation_id;
  if found then
    if v_existing.package_digest_sha256<>p_manifest->>'package_digest_sha256' then raise exception 'correlation_id_reuse_with_different_package'; end if;
    return jsonb_build_object('result','DUPLICATE_CORRELATION_PACKAGE','package_record_id',v_existing.package_record_id,'package_digest_sha256',v_existing.package_digest_sha256,'provider_write',false,'money_movement',false,'chain_broadcast',false,'phase_advancement',false,'merge_authorized',false);
  end if;
  select * into v_existing from chlom_wallet.institutionalization_packages_v2 where package_digest_sha256=p_manifest->>'package_digest_sha256';
  if found then
    return jsonb_build_object('result','DUPLICATE_PACKAGE_DIGEST','package_record_id',v_existing.package_record_id,'package_digest_sha256',v_existing.package_digest_sha256,'provider_write',false,'money_movement',false,'chain_broadcast',false,'phase_advancement',false,'merge_authorized',false);
  end if;
  select * into v_existing from chlom_wallet.institutionalization_packages_v2 where package_id=p_manifest->>'package_id' and semantic_version=p_manifest->>'semantic_version';
  if found then raise exception 'package_semantic_version_digest_conflict'; end if;

  v_server_digest:=encode(extensions.digest(p_manifest::text,'sha256'),'hex');
  v_is_canary:=(p_manifest->>'package_id') like 'ct.package.canary.%';
  insert into chlom_wallet.institutionalization_packages_v2(
    package_id,semantic_version,package_state,source_repository,source_branch,source_head_sha,source_observed_on,
    compiler_tool_id,compiler_algorithm_id,compiler_semantic_version,package_digest_sha256,server_record_digest_sha256,
    artifact_count,algorithm_count,gap_count,completeness_score,docs_state,security_state,privacy_state,rights_state,
    commercialization_state,rollback_state,scheduler_state,provenance_state,ai_mode,correlation_id,manifest_ref,manifest_body,is_canary
  ) values (
    p_manifest->>'package_id',p_manifest->>'semantic_version',p_manifest->>'state',p_manifest#>>'{source_snapshot,repository}',
    p_manifest#>>'{source_snapshot,branch}',p_manifest#>>'{source_snapshot,head_sha}',(p_manifest#>>'{source_snapshot,observed_on}')::date,
    p_manifest#>>'{compiler,tool_id}',p_manifest#>>'{compiler,algorithm_id}',p_manifest#>>'{compiler,semantic_version}',
    p_manifest->>'package_digest_sha256',v_server_digest,(p_manifest#>>'{artifact_counts,total}')::integer,
    jsonb_array_length(p_manifest->'algorithm_registry'),(p_manifest#>>'{gap_analysis,gap_count}')::integer,
    (p_manifest#>>'{gap_analysis,completeness_score}')::integer,coalesce(p_manifest#>>'{docs_impact,state}','UNSPECIFIED'),
    coalesce(p_manifest#>>'{security,state}','UNSPECIFIED'),coalesce(p_manifest#>>'{privacy,state}','UNSPECIFIED'),
    coalesce(p_manifest#>>'{rights,state}','UNSPECIFIED'),coalesce(p_manifest#>>'{commercialization,state}','UNSPECIFIED'),
    coalesce(p_manifest#>>'{rollback,state}','UNSPECIFIED'),coalesce(p_manifest#>>'{scheduler,state}','UNSPECIFIED'),
    coalesce(p_manifest#>>'{provenance,state}','UNSPECIFIED'),coalesce(p_manifest#>>'{ai_governance,mode}','UNSPECIFIED'),
    p_correlation_id,p_source_ref,p_manifest,v_is_canary
  ) returning package_record_id into v_record;

  insert into chlom_wallet.institutionalization_package_artifacts_v2(
    package_record_id,artifact_id,artifact_path,artifact_kind,classification,owner_agent_id,artifact_state,
    public_projection,artifact_sha256,size_bytes,secret_shape_detected,source_ref
  )
  select v_record,a->>'artifact_id',a->>'path',a->>'kind',a->>'classification',a->>'owner_agent_id',a->>'status',
         (a->>'public_projection')::boolean,a->>'sha256',(a->>'size_bytes')::bigint,false,a->>'source_ref'
  from jsonb_array_elements(p_manifest->'artifact_inventory') a;
  get diagnostics v_artifacts=row_count;

  insert into chlom_wallet.institutionalization_package_algorithms_v2(
    package_record_id,algorithm_id,semantic_version,classification,source_paths,invariants,proprietary_scope,
    external_dependencies,authority_effect,provider_write,money_movement,rights_grant,chain_broadcast
  )
  select v_record,a->>'algorithm_id',a->>'semantic_version',a->>'classification',a->'source_paths',a->'invariants',
         a->>'proprietary_scope',coalesce(a->'external_dependencies','[]'::jsonb),a->>'authority_effect',false,false,false,false
  from jsonb_array_elements(p_manifest->'algorithm_registry') a;
  get diagnostics v_algorithms=row_count;

  insert into chlom_wallet.institutionalization_package_docs_impacts_v2(
    package_record_id,docs_state,public_pages,machine_pages,navigation_action,editor_navigation_metadata_state,fake_navigation_write_created
  ) values (
    v_record,coalesce(p_manifest#>>'{docs_impact,state}','UNSPECIFIED'),coalesce(p_manifest#>'{docs_impact,public_pages}','[]'::jsonb),
    coalesce(p_manifest#>'{docs_impact,machine_pages}','[]'::jsonb),p_manifest#>>'{docs_impact,mintlify_navigation_action}',
    p_manifest#>>'{docs_impact,editor_navigation_metadata_state}',false
  );

  insert into chlom_wallet.institutionalization_package_gaps_v2(
    package_record_id,gap_sequence,gap_code,gap_category,severity,artifact_id,algorithm_id,handoff_agent_id,gap_body
  )
  select v_record,ordinality,g->>'code',g->>'category',g->>'severity',g->>'artifact_id',g->>'algorithm_id',g->>'handoff_agent_id',g
  from jsonb_array_elements(p_manifest#>'{gap_analysis,gaps}') with ordinality as gaps(g,ordinality);
  get diagnostics v_gaps=row_count;

  return jsonb_build_object(
    'result','RECORDED_INSTITUTIONALIZATION_PACKAGE_V2',
    'package_record_id',v_record,
    'package_id',p_manifest->>'package_id',
    'semantic_version',p_manifest->>'semantic_version',
    'package_digest_sha256',p_manifest->>'package_digest_sha256',
    'artifact_count',v_artifacts,
    'algorithm_count',v_algorithms,
    'gap_count',v_gaps,
    'is_canary',v_is_canary,
    'provider_write',false,'signing',false,'custody',false,'token_issuance',false,'money_movement',false,
    'production_rights_grant',false,'chain_broadcast',false,'effective_price_publication',false,
    'checkout_activation',false,'phase_advancement',false,'merge_authorized',false
  );
end;
$$;

create or replace function public.chlom_wallet_institutionalization_package_status_v2()
returns jsonb
language plpgsql
stable
security definer
set search_path=chlom_wallet,pg_catalog,pg_temp
as $$
declare
  p chlom_wallet.institutionalization_packages_v2%rowtype;
  v_public integer:=0;
  v_internal integer:=0;
  v_restricted integer:=0;
  v_crosswalk integer:=0;
  v_canary text;
  v_legacy_policies integer:=0;
  v_legacy_algorithms integer:=0;
  v_legacy_runs integer:=0;
begin
  select * into p from chlom_wallet.institutionalization_packages_v2 where not is_canary order by created_at desc limit 1;
  select count(*) into v_crosswalk from chlom_wallet.institutionalization_algorithm_crosswalk_v2;
  select result into v_canary from chlom_wallet.institutionalization_package_canary_runs_v2 order by created_at desc limit 1;
  select count(*) into v_legacy_policies from chlom_wallet.institutionalization_policies_v1;
  select count(*) into v_legacy_algorithms from chlom_wallet.institutionalization_algorithms_v1;
  select count(*) into v_legacy_runs from chlom_wallet.institutionalization_runs_v1 where not is_canary;

  if not found then
    return jsonb_build_object(
      'contract','ct.wallet.institutionalization-package-status.v2','state','NO_RECORDED_PACKAGE_V2','phase','2.99',
      'legacy_runtime',jsonb_build_object('policies',v_legacy_policies,'algorithm_rows',v_legacy_algorithms,'recorded_runs',v_legacy_runs,'reconciliation_state','V2_RUNTIME_READY_PACKAGE_NOT_REGISTERED'),
      'algorithm_crosswalk_count',v_crosswalk,'latest_canary',v_canary,
      'hard_boundaries',jsonb_build_object('provider_write',false,'signing',false,'custody',false,'token_issuance',false,'money_movement',false,'production_rights_grant',false,'chain_broadcast',false,'effective_price_publication',false,'checkout_activation',false,'phase_advancement',false,'merge_authorized',false)
    );
  end if;

  select count(*) filter(where classification='public'),count(*) filter(where classification='internal'),count(*) filter(where classification='restricted')
    into v_public,v_internal,v_restricted
  from chlom_wallet.institutionalization_package_artifacts_v2 where package_record_id=p.package_record_id;

  return jsonb_build_object(
    'contract','ct.wallet.institutionalization-package-status.v2','state',p.package_state,'phase','2.99',
    'package_id',p.package_id,'semantic_version',p.semantic_version,'package_digest_sha256',p.package_digest_sha256,
    'source_snapshot',jsonb_build_object('repository',p.source_repository,'branch',p.source_branch,'head_sha',p.source_head_sha,'observed_on',p.source_observed_on),
    'compiler',jsonb_build_object('tool_id',p.compiler_tool_id,'algorithm_id',p.compiler_algorithm_id,'semantic_version',p.compiler_semantic_version),
    'counts',jsonb_build_object('artifacts',p.artifact_count,'public',v_public,'internal',v_internal,'restricted',v_restricted,'algorithms',p.algorithm_count,'gaps',p.gap_count,'completeness_score',p.completeness_score),
    'control_states',jsonb_build_object('docs',p.docs_state,'security',p.security_state,'privacy',p.privacy_state,'rights',p.rights_state,'commercialization',p.commercialization_state,'rollback',p.rollback_state,'scheduler',p.scheduler_state,'provenance',p.provenance_state,'ai_mode',p.ai_mode),
    'manifest_ref',p.manifest_ref,'recorded_at',p.created_at,'algorithm_crosswalk_count',v_crosswalk,'latest_canary',v_canary,
    'legacy_runtime',jsonb_build_object('policies',v_legacy_policies,'algorithm_rows',v_legacy_algorithms,'recorded_runs',v_legacy_runs,'reconciliation_state','V2_PACKAGE_INDEXED_LEGACY_V1_PRESERVED'),
    'hard_boundaries',jsonb_build_object('provider_write',false,'signing',false,'custody',false,'token_issuance',false,'money_movement',false,'production_rights_grant',false,'chain_broadcast',false,'effective_price_publication',false,'checkout_activation',false,'phase_advancement',false,'merge_authorized',false)
  );
end;
$$;

create or replace function chlom_wallet.run_institutionalization_package_canary_v2()
returns jsonb
language plpgsql
security definer
set search_path=chlom_wallet,extensions,pg_catalog,pg_temp
as $$
declare
  v_uuid text:=replace(gen_random_uuid()::text,'-','');
  v_artifacts jsonb;
  v_manifest jsonb;
  v_valid boolean:=false;
  v_duplicate boolean:=false;
  v_mutation boolean:=false;
  v_secret boolean:=false;
  v_restricted boolean:=false;
  v_boundary boolean:=false;
  v_ai boolean:=false;
  v_duplicate_artifact boolean:=false;
  v_gap boolean:=false;
  v_record jsonb;
  v_package_record uuid;
  v_run uuid;
begin
  select jsonb_agg(jsonb_build_object(
    'artifact_id','ct.artifact.canary.'||v_uuid||'.'||replace(kind,'_','-'),
    'path','canary/'||ordinality||'-'||kind||'.txt','kind',kind,'classification','public',
    'owner_agent_id','ct.agent.chlom-wallet-settlement','status','CONTROLLED_TEST','public_projection',true,
    'sha256',encode(extensions.digest(v_uuid||':'||kind,'sha256'),'hex'),'size_bytes',ordinality,
    'secret_shape_detected',false,'source_ref','canary:institutionalization-package-v2'
  ) order by ordinality) into v_artifacts
  from unnest(array['algorithm','source_code','test','documentation','machine_manifest','schema','threat_model','recovery','pricing','agent_handoff','ci_workflow']) with ordinality as k(kind,ordinality);

  v_manifest:=jsonb_build_object(
    'schema_version','1.0.0','package_id','ct.package.canary.'||v_uuid,'semantic_version','0.0.0','state','PASS_CONTROLLED_TEST_INSTITUTIONALIZATION',
    'source_snapshot',jsonb_build_object('repository','crownthrive1/CrownThrive-Support','branch','chlom-wallet/canary','head_sha',repeat('a',40),'observed_on','2026-08-22'),
    'compiler',jsonb_build_object('tool_id','ct.tool.chlom-institutionalization-compiler','algorithm_id','ct.algorithm.chlom.institutionalization-compiler.v1','semantic_version','1.0.0','deterministic',true,'canonicalization','sorted-json','hash','SHA-256','network_access',false,'signing',false,'provider_write',false,'chain_broadcast',false,'money_movement',false),
    'artifact_inventory',v_artifacts,
    'artifact_counts',jsonb_build_object('total',11,'public',11,'internal',0,'restricted',0,'public_projection',11),
    'algorithm_registry',jsonb_build_array(
      jsonb_build_object('algorithm_id','ct.algorithm.canary.compiler.'||v_uuid,'semantic_version','1.0.0','classification','proprietary_controlled_test','source_paths',jsonb_build_array('canary/1-algorithm.txt'),'invariants',jsonb_build_array('deterministic'),'proprietary_scope','canary','external_dependencies','[]'::jsonb,'authority_effect','none','provider_write',false,'money_movement',false,'rights_grant',false,'chain_broadcast',false),
      jsonb_build_object('algorithm_id','ct.algorithm.canary.resolver.'||v_uuid,'semantic_version','1.0.0','classification','proprietary_controlled_test','source_paths',jsonb_build_array('canary/2-source_code.txt'),'invariants',jsonb_build_array('hold-on-gap'),'proprietary_scope','canary','external_dependencies','[]'::jsonb,'authority_effect','none','provider_write',false,'money_movement',false,'rights_grant',false,'chain_broadcast',false)
    ),
    'docs_impact',jsonb_build_object('state','DOCS_UPDATED','public_pages',jsonb_build_array('canary'),'machine_pages',jsonb_build_array('canary.json'),'mintlify_navigation_action','none','editor_navigation_metadata_state','none','fake_navigation_write_created',false),
    'security',jsonb_build_object('state','CONTROLLED_TEST'),'privacy',jsonb_build_object('state','CONTROLLED_TEST'),
    'rights',jsonb_build_object('state','HOLD_INDEPENDENT_RIGHTS_REVIEW','production_rights_grant',false),
    'commercialization',jsonb_build_object('state','PRICE_REVIEW','effective_offer',false,'public_price',false,'stripe_objects_created',false,'checkout_enabled',false),
    'rollback',jsonb_build_object('state','CONTROLLED_TEST'),'scheduler',jsonb_build_object('state','NO_NEW_EXTERNAL_SLOT'),'provenance',jsonb_build_object('state','SOURCE_CONTROLLED'),
    'third_party_dependencies',jsonb_build_array(jsonb_build_object('name','Node.js','version','22')),
    'ai_governance',jsonb_build_object('mode','AI_ADVISORY_EXTENSION_CANDIDATE','advisory_only',true,'decision_authority',false,'write_authority',false,'output_requires_independent_review',true,'automatic_release',false),
    'gap_analysis',jsonb_build_object('algorithm_id','ct.algorithm.chlom.institutionalization-gap-resolver.v1','algorithm_version','1.0.0','mode','deterministic_policy_engine','ai_extension_mode','advisory_only_no_authority','gap_count',0,'blocking_gap_count',0,'completeness_score',100,'disposition','PASS_CONTROLLED_TEST_INSTITUTIONALIZATION','gaps','[]'::jsonb,'required_handoffs','[]'::jsonb,'authority_effect','none','automatic_remediation',false,'automatic_release',false),
    'output_contract',jsonb_build_object('path','canary.json','committed_manifest_required',true,'deterministic_rebuild_required',true),
    'hard_boundaries',jsonb_build_object('originator_self_approval',false,'automatic_authority_grant',false,'automatic_reviewer_heartbeat',false,'automatic_review_receipt',false,'provider_write',false,'signing',false,'custody',false,'token_issuance',false,'money_movement',false,'production_rights_grant',false,'chain_broadcast',false,'effective_price_publication',false,'checkout_activation',false,'phase_advancement',false,'merge_authorized',false),
    'package_digest_sha256',encode(extensions.digest('cicc-v2-canary:'||v_uuid,'sha256'),'hex')
  );

  v_valid:=chlom_wallet.validate_institutionalization_package_v2(v_manifest)->>'result'='PASS';
  v_record:=chlom_wallet.register_institutionalization_package_v2(v_manifest,'canary:institutionalization-package-v2','canary.register.'||v_uuid);
  v_package_record:=(v_record->>'package_record_id')::uuid;
  v_duplicate:=chlom_wallet.register_institutionalization_package_v2(v_manifest,'canary:institutionalization-package-v2','canary.register.'||v_uuid)->>'result'='DUPLICATE_CORRELATION_PACKAGE';

  begin update chlom_wallet.institutionalization_packages_v2 set docs_state='MUTATED' where package_record_id=v_package_record; exception when others then v_mutation:=position('append_only' in sqlerrm)>0; end;
  v_secret:=chlom_wallet.validate_institutionalization_package_v2(jsonb_set(v_manifest,'{private_key}',to_jsonb('forbidden'::text)))->>'result'='FAIL';
  v_restricted:=chlom_wallet.validate_institutionalization_package_v2(jsonb_set(v_manifest,'{artifact_inventory,0,classification}',to_jsonb('restricted'::text)))->>'result'='FAIL';
  v_boundary:=chlom_wallet.validate_institutionalization_package_v2(jsonb_set(v_manifest,'{hard_boundaries,money_movement}','true'::jsonb))->>'result'='FAIL';
  v_ai:=chlom_wallet.validate_institutionalization_package_v2(jsonb_set(v_manifest,'{ai_governance,decision_authority}','true'::jsonb))->>'result'='FAIL';
  v_duplicate_artifact:=chlom_wallet.validate_institutionalization_package_v2(jsonb_set(v_manifest,'{artifact_inventory,1,artifact_id}',v_manifest#>'{artifact_inventory,0,artifact_id}'))->>'result'='FAIL';
  v_gap:=chlom_wallet.validate_institutionalization_package_v2(jsonb_set(v_manifest,'{gap_analysis,gap_count}','1'::jsonb))->>'result'='FAIL';

  if not v_valid or not v_duplicate or not v_mutation or not v_secret or not v_restricted or not v_boundary or not v_ai or not v_duplicate_artifact or not v_gap then
    raise exception 'institutionalization_package_v2_canary_failed valid=% duplicate=% mutation=% secret=% restricted=% boundary=% ai=% duplicate_artifact=% gap=%',v_valid,v_duplicate,v_mutation,v_secret,v_restricted,v_boundary,v_ai,v_duplicate_artifact,v_gap;
  end if;

  insert into chlom_wallet.institutionalization_package_canary_runs_v2(
    result,valid_package_passed,duplicate_idempotency_passed,mutation_rejected,secret_shape_rejected,
    restricted_public_projection_rejected,hard_boundary_rejected,ai_authority_rejected,duplicate_artifact_rejected,gap_state_mismatch_rejected,evidence
  ) values (
    'PASS_CHLOM_INSTITUTIONALIZATION_PACKAGE_V2_CANARY',true,true,true,true,true,true,true,true,true,
    jsonb_build_object('package_record_id',v_package_record,'raw_artifact_bodies_stored',false,'public_private_projection_separated',true,'automatic_release',false,'provider_write',false,'money_movement',false,'chain_broadcast',false,'phase_advancement',false,'merge_authorized',false)
  ) returning canary_run_id into v_run;

  return jsonb_build_object(
    'result','PASS_CHLOM_INSTITUTIONALIZATION_PACKAGE_V2_CANARY','canary_run_id',v_run,
    'valid_package_passed',true,'duplicate_idempotency_passed',true,'mutation_rejected',true,
    'secret_shape_rejected',true,'restricted_public_projection_rejected',true,'hard_boundary_rejected',true,
    'ai_authority_rejected',true,'duplicate_artifact_rejected',true,'gap_state_mismatch_rejected',true,
    'raw_artifact_bodies_stored',false,'provider_write',false,'signing',false,'custody',false,'token_issuance',false,
    'money_movement',false,'production_rights_grant',false,'chain_broadcast',false,'phase_advancement',false,'merge_authorized',false
  );
end;
$$;

insert into chlom_wallet.institutionalization_algorithm_crosswalk_v2(
  crosswalk_id,legacy_registry_id,legacy_algorithm_id,current_algorithm_id,relationship,crosswalk_state,source_ref,metadata
) values
('ct.crosswalk.institutionalization.airs-cicc.v2','ct.registry.chlom-wallet-institutionalization-algorithms.v1','ct.algorithm.airs.v1','ct.algorithm.chlom.institutionalization-compiler.v1','artifact identity and byte inventory become the CICC artifact compiler','RECONCILED','github:crownthrive1/CrownThrive-Support:pull/233',jsonb_build_object('authority_effect','none')),
('ct.crosswalk.institutionalization.dime-gap.v2','ct.registry.chlom-wallet-institutionalization-algorithms.v1','ct.algorithm.dime.v1','ct.algorithm.chlom.institutionalization-gap-resolver.v1','documentation impact enforcement becomes a required CICC control section and gap rule','RECONCILED','github:crownthrive1/CrownThrive-Support:pull/233',jsonb_build_object('authority_effect','none')),
('ct.crosswalk.institutionalization.garm-gap.v2','ct.registry.chlom-wallet-institutionalization-algorithms.v1','ct.algorithm.garm.v1','ct.algorithm.chlom.institutionalization-gap-resolver.v1','gate and specialist routing becomes deterministic gap handoff routing','RECONCILED','github:crownthrive1/CrownThrive-Support:pull/233',jsonb_build_object('authority_effect','none')),
('ct.crosswalk.institutionalization.mosaic-cicc.v2','ct.registry.chlom-wallet-institutionalization-algorithms.v1','ct.algorithm.mosaic.v1','ct.algorithm.chlom.institutionalization-compiler.v1','candidate monetization remains a compiled control section without activation','RECONCILED','github:crownthrive1/CrownThrive-Support:pull/233',jsonb_build_object('authority_effect','none')),
('ct.crosswalk.institutionalization.prov-cicc.v2','ct.registry.chlom-wallet-institutionalization-algorithms.v1','ct.algorithm.prov-chain.v1','ct.algorithm.chlom.institutionalization-compiler.v1','provenance chain becomes exact artifact hashes plus package digest','RECONCILED','github:crownthrive1/CrownThrive-Support:pull/233',jsonb_build_object('authority_effect','none')),
('ct.crosswalk.institutionalization.safe-cicc.v2','ct.registry.chlom-wallet-institutionalization-algorithms.v1','ct.algorithm.safe-fence.v1','ct.algorithm.chlom.institutionalization-compiler.v1','secret and authority fences become compiler and runtime validation invariants','RECONCILED','github:crownthrive1/CrownThrive-Support:pull/233',jsonb_build_object('authority_effect','none')),
('ct.crosswalk.institutionalization.harp-domain.v2','ct.registry.chlom-wallet-institutionalization-algorithms.v1','ct.algorithm.prov-chain.v1','ct.algorithm.chlom.harp-proof-capsule.v1','HARP remains a domain proof algorithm registered inside the institutional package','DOMAIN_EXTENSION','github:crownthrive1/CrownThrive-Support:pull/233',jsonb_build_object('authority_effect','none')),
('ct.crosswalk.institutionalization.easor-domain.v2','ct.registry.chlom-wallet-institutionalization-algorithms.v1','ct.algorithm.mosaic.v1','ct.algorithm.chlom.easor-settlement-plan.v1','EASOR remains a domain planning algorithm with no settlement execution','DOMAIN_EXTENSION','github:crownthrive1/CrownThrive-Support:pull/233',jsonb_build_object('authority_effect','none')),
('ct.crosswalk.institutionalization.portability-domain.v2','ct.registry.chlom-wallet-institutionalization-algorithms.v1','ct.algorithm.airs.v1','ct.algorithm.chlom.portable-wallet-capsule.v1','portable wallet capsules preserve stable identity without provider writes','DOMAIN_EXTENSION','github:crownthrive1/CrownThrive-Support:pull/233',jsonb_build_object('authority_effect','none'))
on conflict (crosswalk_id) do nothing;

revoke all on function chlom_wallet.validate_institutionalization_package_v2(jsonb) from public,anon,authenticated;
revoke all on function chlom_wallet.register_institutionalization_package_v2(jsonb,text,text) from public,anon,authenticated;
revoke all on function chlom_wallet.run_institutionalization_package_canary_v2() from public,anon,authenticated;
grant execute on function chlom_wallet.validate_institutionalization_package_v2(jsonb) to service_role;
grant execute on function chlom_wallet.register_institutionalization_package_v2(jsonb,text,text) to service_role;
grant execute on function chlom_wallet.run_institutionalization_package_canary_v2() to service_role;
revoke all on function public.chlom_wallet_institutionalization_package_status_v2() from public;
grant execute on function public.chlom_wallet_institutionalization_package_status_v2() to anon,authenticated,service_role;
