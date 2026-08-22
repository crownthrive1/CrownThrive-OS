-- CHLOM Institutionalization Package Runtime v2 GitHub OIDC ingest.
-- Stores verified claims and digests only. Raw OIDC tokens and artifact bodies are prohibited.

create extension if not exists pgcrypto;

create table if not exists chlom_wallet.institutionalization_package_ingest_receipts_v2 (
  receipt_id uuid primary key default gen_random_uuid(),
  package_record_id uuid not null references chlom_wallet.institutionalization_packages_v2(package_record_id) on delete restrict,
  package_id text not null,
  semantic_version text not null,
  package_digest_sha256 text not null check (package_digest_sha256 ~ '^[0-9a-f]{64}$'),
  oidc_jti text not null unique,
  oidc_issuer text not null,
  oidc_audience text not null,
  oidc_subject text not null,
  token_fingerprint_sha256 text not null check (token_fingerprint_sha256 ~ '^[0-9a-f]{64}$'),
  request_digest_sha256 text not null unique check (request_digest_sha256 ~ '^[0-9a-f]{64}$'),
  claims_digest_sha256 text not null check (claims_digest_sha256 ~ '^[0-9a-f]{64}$'),
  repository text not null,
  repository_id text not null,
  repository_owner text not null,
  repository_owner_id text not null,
  repository_visibility text not null,
  event_name text not null check (event_name in ('pull_request','workflow_dispatch')),
  source_branch text not null,
  target_branch text,
  pull_request_number integer,
  verified_current_head_sha text not null check (verified_current_head_sha ~ '^[0-9a-f]{40}$'),
  verified_source_head_sha text not null check (verified_source_head_sha ~ '^[0-9a-f]{40}$'),
  source_head_ancestor_verified boolean not null check (source_head_ancestor_verified),
  manifest_path text not null,
  manifest_content_sha256 text not null check (manifest_content_sha256 ~ '^[0-9a-f]{64}$'),
  manifest_canonical_sha256 text not null check (manifest_canonical_sha256 ~ '^[0-9a-f]{64}$'),
  workflow text not null,
  workflow_ref text not null,
  workflow_sha text not null check (workflow_sha ~ '^[0-9a-f]{40}$'),
  github_event_sha text not null check (github_event_sha ~ '^[0-9a-f]{40}$'),
  github_run_id text not null,
  github_run_number text,
  github_run_attempt integer not null check (github_run_attempt >= 1),
  github_actor text not null,
  github_actor_id text not null,
  runner_environment text not null,
  record_result text not null,
  source_ref text not null,
  token_value_persisted boolean not null default false check (not token_value_persisted),
  raw_artifact_body_persisted boolean not null default false check (not raw_artifact_body_persisted),
  provider_write boolean not null default false check (not provider_write),
  credential_access boolean not null default false check (not credential_access),
  effective_offer boolean not null default false check (not effective_offer),
  stripe_objects_created boolean not null default false check (not stripe_objects_created),
  checkout_enabled boolean not null default false check (not checkout_enabled),
  custody boolean not null default false check (not custody),
  token_issuance boolean not null default false check (not token_issuance),
  money_movement boolean not null default false check (not money_movement),
  production_rights_grant boolean not null default false check (not production_rights_grant),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  phase_advancement boolean not null default false check (not phase_advancement),
  merge_authorized boolean not null default false check (not merge_authorized),
  created_at timestamptz not null default now(),
  unique (github_run_id, github_run_attempt, package_digest_sha256)
);

create table if not exists chlom_wallet.institutionalization_package_ingest_canary_runs_v2 (
  canary_run_id uuid primary key default gen_random_uuid(),
  result text not null,
  valid_claims_passed boolean not null,
  duplicate_oidc_idempotency_passed boolean not null,
  wrong_repository_rejected boolean not null,
  wrong_workflow_rejected boolean not null,
  source_head_drift_rejected boolean not null,
  ancestor_claim_rejected boolean not null,
  manifest_digest_drift_rejected boolean not null,
  authority_escalation_rejected boolean not null,
  token_value_persisted boolean not null default false check (not token_value_persisted),
  raw_artifact_body_persisted boolean not null default false check (not raw_artifact_body_persisted),
  provider_write boolean not null default false check (not provider_write),
  credential_access boolean not null default false check (not credential_access),
  effective_offer boolean not null default false check (not effective_offer),
  stripe_objects_created boolean not null default false check (not stripe_objects_created),
  checkout_enabled boolean not null default false check (not checkout_enabled),
  custody boolean not null default false check (not custody),
  token_issuance boolean not null default false check (not token_issuance),
  money_movement boolean not null default false check (not money_movement),
  production_rights_grant boolean not null default false check (not production_rights_grant),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  phase_advancement boolean not null default false check (not phase_advancement),
  merge_authorized boolean not null default false check (not merge_authorized),
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create or replace function chlom_wallet.reject_institutionalization_ingest_mutation_v2()
returns trigger
language plpgsql
set search_path=pg_catalog
as $$
begin
  raise exception 'institutionalization_ingest_records_are_append_only';
end;
$$;

do $$
declare t text;
begin
  foreach t in array array[
    'institutionalization_package_ingest_receipts_v2',
    'institutionalization_package_ingest_canary_runs_v2'
  ] loop
    execute format('drop trigger if exists reject_%I_mutation_v2 on chlom_wallet.%I',t,t);
    execute format('create trigger reject_%I_mutation_v2 before update or delete on chlom_wallet.%I for each row execute function chlom_wallet.reject_institutionalization_ingest_mutation_v2()',t,t);
    execute format('alter table chlom_wallet.%I enable row level security',t);
    execute format('drop policy if exists deny_all_%I on chlom_wallet.%I',t,t);
    execute format('create policy deny_all_%I on chlom_wallet.%I as restrictive for all to public using(false) with check(false)',t,t);
    execute format('revoke all on chlom_wallet.%I from public,anon,authenticated',t);
  end loop;
end;
$$;

create or replace function chlom_wallet.validate_institutionalization_ingest_claims_v2(
  p_manifest jsonb,
  p_claims jsonb,
  p_token_fingerprint_sha256 text,
  p_request_digest_sha256 text
)
returns jsonb
language plpgsql
stable
security definer
set search_path=chlom_wallet,pg_catalog,pg_temp
as $$
declare
  v_errors jsonb:='[]'::jsonb;
  v_manifest_validation jsonb;
  v_key text;
begin
  v_manifest_validation:=chlom_wallet.validate_institutionalization_package_v2(p_manifest);
  if v_manifest_validation->>'result'<>'PASS' then
    v_errors:=v_errors||jsonb_build_array('manifest_validation_failed');
  end if;
  if p_claims is null or jsonb_typeof(p_claims)<>'object' then
    return jsonb_build_object('result','FAIL','errors',jsonb_build_array('claims_object_required'));
  end if;

  if p_token_fingerprint_sha256 !~ '^[0-9a-f]{64}$' then v_errors:=v_errors||jsonb_build_array('token_fingerprint_invalid'); end if;
  if p_request_digest_sha256 !~ '^[0-9a-f]{64}$' then v_errors:=v_errors||jsonb_build_array('request_digest_invalid'); end if;
  if p_claims->>'repository'<>'crownthrive1/CrownThrive-Support' then v_errors:=v_errors||jsonb_build_array('repository_invalid'); end if;
  if p_claims->>'repository_id'<>'1336348391' then v_errors:=v_errors||jsonb_build_array('repository_id_invalid'); end if;
  if p_claims->>'repository_owner'<>'crownthrive1' then v_errors:=v_errors||jsonb_build_array('repository_owner_invalid'); end if;
  if p_claims->>'repository_owner_id'<>'315660018' then v_errors:=v_errors||jsonb_build_array('repository_owner_id_invalid'); end if;
  if p_claims->>'repository_visibility'<>'public' then v_errors:=v_errors||jsonb_build_array('repository_visibility_invalid'); end if;
  if p_claims->>'event_name' not in ('pull_request','workflow_dispatch') then v_errors:=v_errors||jsonb_build_array('event_name_invalid'); end if;
  if p_claims->>'source_branch'<>p_manifest#>>'{source_snapshot,branch}' then v_errors:=v_errors||jsonb_build_array('source_branch_mismatch'); end if;
  if p_claims->>'verified_source_head_sha'<>p_manifest#>>'{source_snapshot,head_sha}' then v_errors:=v_errors||jsonb_build_array('source_head_mismatch'); end if;
  if p_claims->>'verified_current_head_sha' !~ '^[0-9a-f]{40}$' then v_errors:=v_errors||jsonb_build_array('current_head_invalid'); end if;
  if coalesce((p_claims->>'source_head_ancestor_verified')::boolean,false) is not true then v_errors:=v_errors||jsonb_build_array('source_head_ancestor_not_verified'); end if;
  if p_claims->>'manifest_path'<>'developers/manifests/chlom-wallet-phase-c-institutionalization.v1.json' then v_errors:=v_errors||jsonb_build_array('manifest_path_invalid'); end if;
  if p_claims->>'manifest_content_sha256' !~ '^[0-9a-f]{64}$' then v_errors:=v_errors||jsonb_build_array('manifest_content_digest_invalid'); end if;
  if p_claims->>'manifest_canonical_sha256' !~ '^[0-9a-f]{64}$' then v_errors:=v_errors||jsonb_build_array('manifest_canonical_digest_invalid'); end if;
  if p_claims->>'manifest_package_digest_sha256'<>p_manifest->>'package_digest_sha256' then v_errors:=v_errors||jsonb_build_array('manifest_package_digest_mismatch'); end if;
  if p_claims->>'workflow'<>'CHLOM Institutionalization Package v2' then v_errors:=v_errors||jsonb_build_array('workflow_name_invalid'); end if;
  if p_claims->>'workflow_ref' !~ '^crownthrive1/CrownThrive-Support/[.]github/workflows/chlom-wallet-institutionalization-v2[.]yml@refs/' then v_errors:=v_errors||jsonb_build_array('workflow_ref_invalid'); end if;
  if p_claims->>'workflow_sha' !~ '^[0-9a-f]{40}$' then v_errors:=v_errors||jsonb_build_array('workflow_sha_invalid'); end if;
  if p_claims->>'github_event_sha' !~ '^[0-9a-f]{40}$' then v_errors:=v_errors||jsonb_build_array('github_event_sha_invalid'); end if;
  if p_claims->>'github_run_id' !~ '^[0-9]+$' then v_errors:=v_errors||jsonb_build_array('github_run_id_invalid'); end if;
  if p_claims->>'github_run_attempt' !~ '^[0-9]+$' or (p_claims->>'github_run_attempt')::integer<1 then v_errors:=v_errors||jsonb_build_array('github_run_attempt_invalid'); end if;
  if p_claims->>'github_actor' !~ '^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$' then v_errors:=v_errors||jsonb_build_array('github_actor_invalid'); end if;
  if p_claims->>'github_actor_id' !~ '^[0-9]+$' then v_errors:=v_errors||jsonb_build_array('github_actor_id_invalid'); end if;
  if p_claims->>'oidc_jti' !~ '^[A-Za-z0-9._:-]{8,240}$' then v_errors:=v_errors||jsonb_build_array('oidc_jti_invalid'); end if;
  if p_claims->>'oidc_issuer'<>'https://token.actions.githubusercontent.com' then v_errors:=v_errors||jsonb_build_array('oidc_issuer_invalid'); end if;
  if p_claims->>'oidc_audience'<>'chlom-wallet-institutionalization-v2' then v_errors:=v_errors||jsonb_build_array('oidc_audience_invalid'); end if;
  if p_claims->>'oidc_subject' !~ '^repo:crownthrive1/CrownThrive-Support:' then v_errors:=v_errors||jsonb_build_array('oidc_subject_invalid'); end if;
  if p_claims->>'runner_environment'<>'github-hosted' then v_errors:=v_errors||jsonb_build_array('runner_environment_invalid'); end if;
  if p_claims->>'event_name'='pull_request' then
    if p_claims->>'pull_request_number' !~ '^[0-9]+$' then v_errors:=v_errors||jsonb_build_array('pull_request_number_invalid'); end if;
    if p_claims->>'target_branch'<>'chlom-wallet/phase-b-webhook-passkey-contracts-20260822' then v_errors:=v_errors||jsonb_build_array('target_branch_invalid'); end if;
  end if;

  foreach v_key in array array[
    'provider_write','credential_access','effective_offer','stripe_objects_created','checkout_enabled',
    'custody','token_issuance','money_movement','production_rights_grant','chain_broadcast',
    'phase_advancement','merge_authorized','automatic_profile_promotion'
  ] loop
    if coalesce((p_claims->>v_key)::boolean,true) then
      v_errors:=v_errors||jsonb_build_array('authority_boundary_invalid_'||v_key);
    end if;
  end loop;

  return jsonb_build_object(
    'result',case when jsonb_array_length(v_errors)=0 then 'PASS' else 'FAIL' end,
    'errors',v_errors,
    'manifest_validation',v_manifest_validation
  );
end;
$$;

create or replace function chlom_wallet.ingest_institutionalization_package_v2(
  p_manifest jsonb,
  p_claims jsonb,
  p_token_fingerprint_sha256 text,
  p_request_digest_sha256 text
)
returns jsonb
language plpgsql
security definer
set search_path=chlom_wallet,extensions,pg_catalog,pg_temp
as $$
declare
  v_validation jsonb;
  v_existing chlom_wallet.institutionalization_package_ingest_receipts_v2%rowtype;
  v_package_result jsonb;
  v_package_record uuid;
  v_receipt uuid;
  v_claims_digest text;
  v_correlation text;
begin
  v_validation:=chlom_wallet.validate_institutionalization_ingest_claims_v2(p_manifest,p_claims,p_token_fingerprint_sha256,p_request_digest_sha256);
  if v_validation->>'result'<>'PASS' then raise exception 'institutionalization_ingest_claims_failed:%',v_validation; end if;

  select * into v_existing from chlom_wallet.institutionalization_package_ingest_receipts_v2 where oidc_jti=p_claims->>'oidc_jti';
  if found then
    if v_existing.request_digest_sha256<>p_request_digest_sha256
       or v_existing.package_digest_sha256<>p_manifest->>'package_digest_sha256' then
      raise exception 'oidc_jti_reuse_with_different_request';
    end if;
    return jsonb_build_object(
      'result','DUPLICATE_OIDC_INGEST_RECEIPT',
      'receipt_id',v_existing.receipt_id,
      'package_record_id',v_existing.package_record_id,
      'package_digest_sha256',v_existing.package_digest_sha256,
      'token_value_persisted',false,'raw_artifact_body_persisted',false,
      'provider_write',false,'credential_access',false,'money_movement',false,
      'production_rights_grant',false,'chain_broadcast',false,'phase_advancement',false,'merge_authorized',false
    );
  end if;

  v_correlation:='github-v2.'||(p_claims->>'github_run_id')||'.'||(p_claims->>'github_run_attempt')||'.'||substr(p_manifest->>'package_digest_sha256',1,32);
  v_package_result:=chlom_wallet.register_institutionalization_package_v2(
    p_manifest,
    'github:crownthrive1/CrownThrive-Support:'||(p_claims->>'verified_current_head_sha')||':'||(p_claims->>'manifest_path'),
    v_correlation
  );
  v_package_record:=(v_package_result->>'package_record_id')::uuid;
  v_claims_digest:=encode(extensions.digest(p_claims::text,'sha256'),'hex');

  insert into chlom_wallet.institutionalization_package_ingest_receipts_v2(
    package_record_id,package_id,semantic_version,package_digest_sha256,
    oidc_jti,oidc_issuer,oidc_audience,oidc_subject,token_fingerprint_sha256,
    request_digest_sha256,claims_digest_sha256,repository,repository_id,
    repository_owner,repository_owner_id,repository_visibility,event_name,
    source_branch,target_branch,pull_request_number,verified_current_head_sha,
    verified_source_head_sha,source_head_ancestor_verified,manifest_path,
    manifest_content_sha256,manifest_canonical_sha256,workflow,workflow_ref,
    workflow_sha,github_event_sha,github_run_id,github_run_number,
    github_run_attempt,github_actor,github_actor_id,runner_environment,
    record_result,source_ref
  ) values (
    v_package_record,p_manifest->>'package_id',p_manifest->>'semantic_version',p_manifest->>'package_digest_sha256',
    p_claims->>'oidc_jti',p_claims->>'oidc_issuer',p_claims->>'oidc_audience',p_claims->>'oidc_subject',p_token_fingerprint_sha256,
    p_request_digest_sha256,v_claims_digest,p_claims->>'repository',p_claims->>'repository_id',
    p_claims->>'repository_owner',p_claims->>'repository_owner_id',p_claims->>'repository_visibility',p_claims->>'event_name',
    p_claims->>'source_branch',nullif(p_claims->>'target_branch',''),nullif(p_claims->>'pull_request_number','')::integer,p_claims->>'verified_current_head_sha',
    p_claims->>'verified_source_head_sha',(p_claims->>'source_head_ancestor_verified')::boolean,p_claims->>'manifest_path',
    p_claims->>'manifest_content_sha256',p_claims->>'manifest_canonical_sha256',p_claims->>'workflow',p_claims->>'workflow_ref',
    p_claims->>'workflow_sha',p_claims->>'github_event_sha',p_claims->>'github_run_id',nullif(p_claims->>'github_run_number',''),
    (p_claims->>'github_run_attempt')::integer,p_claims->>'github_actor',p_claims->>'github_actor_id',p_claims->>'runner_environment',
    v_package_result->>'result','github:crownthrive1/CrownThrive-Support:'||(p_claims->>'verified_current_head_sha')
  ) returning receipt_id into v_receipt;

  return jsonb_build_object(
    'result','RECORDED_INSTITUTIONALIZATION_PACKAGE_INGEST_V2',
    'receipt_id',v_receipt,
    'package_record_id',v_package_record,
    'package_record_result',v_package_result->>'result',
    'package_digest_sha256',p_manifest->>'package_digest_sha256',
    'token_value_persisted',false,'raw_artifact_body_persisted',false,
    'provider_write',false,'credential_access',false,'effective_offer',false,
    'stripe_objects_created',false,'checkout_enabled',false,'custody',false,
    'token_issuance',false,'money_movement',false,'production_rights_grant',false,
    'chain_broadcast',false,'phase_advancement',false,'merge_authorized',false
  );
end;
$$;

create or replace function public.chlom_wallet_ingest_institutionalization_package_v2(
  p_manifest jsonb,
  p_claims jsonb,
  p_token_fingerprint_sha256 text,
  p_request_digest_sha256 text
)
returns jsonb
language sql
security definer
set search_path=pg_catalog
as $$
  select chlom_wallet.ingest_institutionalization_package_v2(
    p_manifest,p_claims,p_token_fingerprint_sha256,p_request_digest_sha256
  );
$$;

create or replace function public.chlom_wallet_institutionalization_ingest_status_v2()
returns jsonb
language plpgsql
stable
security definer
set search_path=chlom_wallet,pg_catalog,pg_temp
as $$
declare
  r chlom_wallet.institutionalization_package_ingest_receipts_v2%rowtype;
  v_count integer:=0;
  v_canary text;
begin
  select count(*) into v_count from chlom_wallet.institutionalization_package_ingest_receipts_v2;
  select result into v_canary from chlom_wallet.institutionalization_package_ingest_canary_runs_v2 order by created_at desc limit 1;
  select * into r from chlom_wallet.institutionalization_package_ingest_receipts_v2 order by created_at desc limit 1;

  return jsonb_build_object(
    'contract','ct.wallet.institutionalization-ingest-status.v2',
    'state',case when r.receipt_id is null then 'NO_RECORDED_INGEST_V2' else 'RECORDED_CONTROLLED_TEST_EVIDENCE' end,
    'phase','2.99',
    'receipt_count',v_count,
    'latest_receipt',case when r.receipt_id is null then null else jsonb_build_object(
      'receipt_id',r.receipt_id,'package_id',r.package_id,'semantic_version',r.semantic_version,
      'package_digest_sha256',r.package_digest_sha256,'event_name',r.event_name,
      'source_branch',r.source_branch,'target_branch',r.target_branch,
      'pull_request_number',r.pull_request_number,'verified_current_head_sha',r.verified_current_head_sha,
      'verified_source_head_sha',r.verified_source_head_sha,'source_head_ancestor_verified',r.source_head_ancestor_verified,
      'workflow',r.workflow,'github_run_id',r.github_run_id,'github_run_attempt',r.github_run_attempt,
      'github_actor',r.github_actor,'record_result',r.record_result,'created_at',r.created_at
    ) end,
    'latest_canary',v_canary,
    'hard_boundaries',jsonb_build_object(
      'token_value_persisted',false,'raw_artifact_body_persisted',false,
      'provider_write',false,'credential_access',false,'effective_offer',false,
      'stripe_objects_created',false,'checkout_enabled',false,'custody',false,
      'token_issuance',false,'money_movement',false,'production_rights_grant',false,
      'chain_broadcast',false,'phase_advancement',false,'merge_authorized',false
    )
  );
end;
$$;

create or replace function chlom_wallet.run_institutionalization_ingest_canary_v2()
returns jsonb
language plpgsql
security definer
set search_path=chlom_wallet,extensions,pg_catalog,pg_temp
as $$
declare
  p chlom_wallet.institutionalization_packages_v2%rowtype;
  v_claims jsonb;
  v_token text;
  v_request text;
  v_valid boolean:=false;
  v_duplicate boolean:=false;
  v_repo boolean:=false;
  v_workflow boolean:=false;
  v_source boolean:=false;
  v_ancestor boolean:=false;
  v_manifest boolean:=false;
  v_authority boolean:=false;
  v_uuid text:=replace(gen_random_uuid()::text,'-','');
  v_result jsonb;
  v_run uuid;
begin
  select * into p from chlom_wallet.institutionalization_packages_v2 where is_canary order by created_at desc limit 1;
  if not found then raise exception 'package_v2_canary_required_before_ingest_canary'; end if;

  v_token:=encode(extensions.digest('token:'||v_uuid,'sha256'),'hex');
  v_request:=encode(extensions.digest('request:'||v_uuid,'sha256'),'hex');
  v_claims:=jsonb_build_object(
    'repository','crownthrive1/CrownThrive-Support','repository_id','1336348391',
    'repository_owner','crownthrive1','repository_owner_id','315660018','repository_visibility','public',
    'event_name','pull_request','source_branch',p.source_branch,
    'target_branch','chlom-wallet/phase-b-webhook-passkey-contracts-20260822','pull_request_number','233',
    'verified_current_head_sha',repeat('b',40),'verified_source_head_sha',p.source_head_sha,'source_head_ancestor_verified',true,
    'manifest_path','developers/manifests/chlom-wallet-phase-c-institutionalization.v1.json',
    'manifest_content_sha256',encode(extensions.digest('content:'||v_uuid,'sha256'),'hex'),
    'manifest_canonical_sha256',encode(extensions.digest('canonical:'||v_uuid,'sha256'),'hex'),
    'manifest_package_digest_sha256',p.package_digest_sha256,
    'workflow','CHLOM Institutionalization Package v2',
    'workflow_ref','crownthrive1/CrownThrive-Support/.github/workflows/chlom-wallet-institutionalization-v2.yml@refs/pull/233/merge',
    'workflow_sha',repeat('c',40),'github_event_sha',repeat('d',40),
    'github_run_id','123456789','github_run_number','42','github_run_attempt','1',
    'github_actor','crownthrive1','github_actor_id','315660018',
    'oidc_jti','cicc-v2-canary-'||v_uuid,'oidc_issuer','https://token.actions.githubusercontent.com',
    'oidc_audience','chlom-wallet-institutionalization-v2',
    'oidc_subject','repo:crownthrive1/CrownThrive-Support:pull_request',
    'runner_environment','github-hosted',
    'provider_write',false,'credential_access',false,'effective_offer',false,'stripe_objects_created',false,
    'checkout_enabled',false,'custody',false,'token_issuance',false,'money_movement',false,
    'production_rights_grant',false,'chain_broadcast',false,'phase_advancement',false,
    'merge_authorized',false,'automatic_profile_promotion',false
  );

  v_result:=chlom_wallet.ingest_institutionalization_package_v2(p.manifest_body,v_claims,v_token,v_request);
  v_valid:=v_result->>'result'='RECORDED_INSTITUTIONALIZATION_PACKAGE_INGEST_V2';
  v_duplicate:=chlom_wallet.ingest_institutionalization_package_v2(p.manifest_body,v_claims,v_token,v_request)->>'result'='DUPLICATE_OIDC_INGEST_RECEIPT';
  v_repo:=chlom_wallet.validate_institutionalization_ingest_claims_v2(p.manifest_body,jsonb_set(v_claims,'{repository}',to_jsonb('wrong/repository'::text)),v_token,v_request)->>'result'='FAIL';
  v_workflow:=chlom_wallet.validate_institutionalization_ingest_claims_v2(p.manifest_body,jsonb_set(v_claims,'{workflow}',to_jsonb('Wrong Workflow'::text)),v_token,v_request)->>'result'='FAIL';
  v_source:=chlom_wallet.validate_institutionalization_ingest_claims_v2(p.manifest_body,jsonb_set(v_claims,'{verified_source_head_sha}',to_jsonb(repeat('e',40))),v_token,v_request)->>'result'='FAIL';
  v_ancestor:=chlom_wallet.validate_institutionalization_ingest_claims_v2(p.manifest_body,jsonb_set(v_claims,'{source_head_ancestor_verified}','false'::jsonb),v_token,v_request)->>'result'='FAIL';
  v_manifest:=chlom_wallet.validate_institutionalization_ingest_claims_v2(p.manifest_body,jsonb_set(v_claims,'{manifest_package_digest_sha256}',to_jsonb(repeat('f',64))),v_token,v_request)->>'result'='FAIL';
  v_authority:=chlom_wallet.validate_institutionalization_ingest_claims_v2(p.manifest_body,jsonb_set(v_claims,'{money_movement}','true'::jsonb),v_token,v_request)->>'result'='FAIL';

  if not v_valid or not v_duplicate or not v_repo or not v_workflow or not v_source or not v_ancestor or not v_manifest or not v_authority then
    raise exception 'institutionalization_ingest_v2_canary_failed valid=% duplicate=% repo=% workflow=% source=% ancestor=% manifest=% authority=%',v_valid,v_duplicate,v_repo,v_workflow,v_source,v_ancestor,v_manifest,v_authority;
  end if;

  insert into chlom_wallet.institutionalization_package_ingest_canary_runs_v2(
    result,valid_claims_passed,duplicate_oidc_idempotency_passed,wrong_repository_rejected,
    wrong_workflow_rejected,source_head_drift_rejected,ancestor_claim_rejected,
    manifest_digest_drift_rejected,authority_escalation_rejected,evidence
  ) values (
    'PASS_CHLOM_INSTITUTIONALIZATION_INGEST_V2_CANARY',true,true,true,true,true,true,true,true,
    jsonb_build_object('package_record_id',p.package_record_id,'token_value_persisted',false,'raw_artifact_body_persisted',false,'provider_write',false,'credential_access',false,'money_movement',false,'chain_broadcast',false,'phase_advancement',false,'merge_authorized',false)
  ) returning canary_run_id into v_run;

  return jsonb_build_object(
    'result','PASS_CHLOM_INSTITUTIONALIZATION_INGEST_V2_CANARY','canary_run_id',v_run,
    'valid_claims_passed',true,'duplicate_oidc_idempotency_passed',true,
    'wrong_repository_rejected',true,'wrong_workflow_rejected',true,
    'source_head_drift_rejected',true,'ancestor_claim_rejected',true,
    'manifest_digest_drift_rejected',true,'authority_escalation_rejected',true,
    'token_value_persisted',false,'raw_artifact_body_persisted',false,
    'provider_write',false,'credential_access',false,'effective_offer',false,
    'stripe_objects_created',false,'checkout_enabled',false,'custody',false,
    'token_issuance',false,'money_movement',false,'production_rights_grant',false,
    'chain_broadcast',false,'phase_advancement',false,'merge_authorized',false
  );
end;
$$;

revoke all on function chlom_wallet.validate_institutionalization_ingest_claims_v2(jsonb,jsonb,text,text) from public,anon,authenticated;
revoke all on function chlom_wallet.ingest_institutionalization_package_v2(jsonb,jsonb,text,text) from public,anon,authenticated;
revoke all on function chlom_wallet.run_institutionalization_ingest_canary_v2() from public,anon,authenticated;
revoke all on function public.chlom_wallet_ingest_institutionalization_package_v2(jsonb,jsonb,text,text) from public,anon,authenticated;
revoke all on function public.chlom_wallet_institutionalization_ingest_status_v2() from public;

grant execute on function chlom_wallet.validate_institutionalization_ingest_claims_v2(jsonb,jsonb,text,text) to service_role;
grant execute on function chlom_wallet.ingest_institutionalization_package_v2(jsonb,jsonb,text,text) to service_role;
grant execute on function chlom_wallet.run_institutionalization_ingest_canary_v2() to service_role;
grant execute on function public.chlom_wallet_ingest_institutionalization_package_v2(jsonb,jsonb,text,text) to service_role;
grant execute on function public.chlom_wallet_institutionalization_ingest_status_v2() to anon,authenticated,service_role;
