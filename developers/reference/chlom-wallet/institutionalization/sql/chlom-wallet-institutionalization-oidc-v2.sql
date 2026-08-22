-- CHLOM Wallet Institutionalization OIDC Subject Contract v2
-- CONTROLLED TEST: exact GitHub OIDC subject reconciliation and negative canary.
-- This migration creates no provider write, credential access, money movement,
-- production rights grant, chain broadcast, phase advancement, or merge authority.

create extension if not exists pgcrypto;

do $$
declare
  v_oid oid;
  v_definition text;
  v_old text := $old$if p_claims->>'oidc_subject' !~ '^repo:crownthrive1/CrownThrive-Support:' then v_errors:=v_errors||jsonb_build_array('oidc_subject_invalid'); end if;$old$;
  v_new text := $new$if not (
    (p_claims->>'event_name'='pull_request' and p_claims->>'oidc_subject' in (
      'repo:crownthrive1/CrownThrive-Support:pull_request',
      'repo:crownthrive1@315660018/CrownThrive-Support@1336348391:pull_request'
    ))
    or
    (p_claims->>'event_name'='workflow_dispatch' and p_claims->>'oidc_subject' in (
      'repo:crownthrive1/CrownThrive-Support:ref:refs/heads/'||(p_manifest#>>'{source_snapshot,branch}'),
      'repo:crownthrive1@315660018/CrownThrive-Support@1336348391:ref:refs/heads/'||(p_manifest#>>'{source_snapshot,branch}')
    ))
  ) then v_errors:=v_errors||jsonb_build_array('oidc_subject_invalid'); end if;$new$;
begin
  select p.oid into v_oid
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_wallet'
    and p.proname='validate_institutionalization_ingest_claims_v2'
    and pg_get_function_identity_arguments(p.oid)='p_manifest jsonb, p_claims jsonb, p_token_fingerprint_sha256 text, p_request_digest_sha256 text';
  if v_oid is null then raise exception 'institutionalization_v2_validator_not_found'; end if;
  v_definition:=pg_get_functiondef(v_oid);
  if position(v_old in v_definition)=0 then raise exception 'institutionalization_v2_subject_clause_not_found'; end if;
  execute replace(v_definition,v_old,v_new);
end;
$$;

create table if not exists chlom_wallet.institutionalization_oidc_subject_canary_runs_v2 (
  canary_run_id uuid primary key default gen_random_uuid(),
  result text not null,
  legacy_pull_request_subject_accepted boolean not null,
  immutable_pull_request_subject_accepted boolean not null,
  legacy_dispatch_subject_accepted boolean not null,
  immutable_dispatch_subject_accepted boolean not null,
  wrong_owner_id_rejected boolean not null,
  wrong_repository_id_rejected boolean not null,
  wrong_branch_rejected boolean not null,
  evidence jsonb not null default '{}'::jsonb,
  token_value_persisted boolean not null default false check (not token_value_persisted),
  provider_write boolean not null default false check (not provider_write),
  credential_access boolean not null default false check (not credential_access),
  money_movement boolean not null default false check (not money_movement),
  production_rights_grant boolean not null default false check (not production_rights_grant),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  phase_advancement boolean not null default false check (not phase_advancement),
  merge_authorized boolean not null default false check (not merge_authorized),
  created_at timestamptz not null default now()
);

alter table chlom_wallet.institutionalization_oidc_subject_canary_runs_v2 enable row level security;
drop policy if exists deny_all_institutionalization_oidc_subject_canary_runs_v2
  on chlom_wallet.institutionalization_oidc_subject_canary_runs_v2;
create policy deny_all_institutionalization_oidc_subject_canary_runs_v2
  on chlom_wallet.institutionalization_oidc_subject_canary_runs_v2
  as restrictive for all to public using(false) with check(false);
revoke all on chlom_wallet.institutionalization_oidc_subject_canary_runs_v2 from public,anon,authenticated;

drop trigger if exists reject_institutionalization_oidc_subject_canary_mutation_v2
  on chlom_wallet.institutionalization_oidc_subject_canary_runs_v2;
create trigger reject_institutionalization_oidc_subject_canary_mutation_v2
before update or delete on chlom_wallet.institutionalization_oidc_subject_canary_runs_v2
for each row execute function chlom_wallet.reject_institutionalization_ingest_mutation_v2();

create or replace function chlom_wallet.run_institutionalization_oidc_subject_canary_v2()
returns jsonb
language plpgsql
security definer
set search_path=chlom_wallet,extensions,pg_catalog,pg_temp
as $$
declare
  p chlom_wallet.institutionalization_packages_v2%rowtype;
  c jsonb;
  v_token text:=encode(extensions.digest('oidc-subject-token:'||gen_random_uuid()::text,'sha256'),'hex');
  v_request text:=encode(extensions.digest('oidc-subject-request:'||gen_random_uuid()::text,'sha256'),'hex');
  v_legacy_pr boolean:=false;
  v_immutable_pr boolean:=false;
  v_legacy_dispatch boolean:=false;
  v_immutable_dispatch boolean:=false;
  v_wrong_owner boolean:=false;
  v_wrong_repo boolean:=false;
  v_wrong_branch boolean:=false;
  v_run uuid;
begin
  select * into p
  from chlom_wallet.institutionalization_packages_v2
  where is_canary order by created_at desc limit 1;
  if not found then raise exception 'package_v2_canary_required'; end if;

  c:=jsonb_build_object(
    'repository','crownthrive1/CrownThrive-Support','repository_id','1336348391',
    'repository_owner','crownthrive1','repository_owner_id','315660018','repository_visibility','public',
    'event_name','pull_request','source_branch',p.source_branch,
    'target_branch','chlom-wallet/phase-b-webhook-passkey-contracts-20260822','pull_request_number','233',
    'verified_current_head_sha',repeat('b',40),'verified_source_head_sha',p.source_head_sha,
    'source_head_ancestor_verified',true,
    'manifest_path','developers/manifests/chlom-wallet-phase-c-institutionalization.v1.json',
    'manifest_content_sha256',encode(extensions.digest('content','sha256'),'hex'),
    'manifest_canonical_sha256',encode(extensions.digest('canonical','sha256'),'hex'),
    'manifest_package_digest_sha256',p.package_digest_sha256,
    'workflow','CHLOM Institutionalization Package v2',
    'workflow_ref','crownthrive1/CrownThrive-Support/.github/workflows/chlom-wallet-institutionalization-v2.yml@refs/heads/'||p.source_branch,
    'workflow_sha',repeat('c',40),'github_event_sha',repeat('d',40),
    'github_run_id','123456789','github_run_number','42','github_run_attempt','1',
    'github_actor','crownthrive1','github_actor_id','315660018',
    'oidc_jti','cicc-v2-subject-canary-'||replace(gen_random_uuid()::text,'-',''),
    'oidc_issuer','https://token.actions.githubusercontent.com',
    'oidc_audience','chlom-wallet-institutionalization-v2',
    'oidc_subject','repo:crownthrive1/CrownThrive-Support:pull_request',
    'runner_environment','github-hosted',
    'provider_write',false,'credential_access',false,'effective_offer',false,
    'stripe_objects_created',false,'checkout_enabled',false,'custody',false,
    'token_issuance',false,'money_movement',false,'production_rights_grant',false,
    'chain_broadcast',false,'phase_advancement',false,'merge_authorized',false,
    'automatic_profile_promotion',false
  );

  v_legacy_pr:=chlom_wallet.validate_institutionalization_ingest_claims_v2(p.manifest_body,c,v_token,v_request)->>'result'='PASS';
  v_immutable_pr:=chlom_wallet.validate_institutionalization_ingest_claims_v2(
    p.manifest_body,
    jsonb_set(c,'{oidc_subject}',to_jsonb('repo:crownthrive1@315660018/CrownThrive-Support@1336348391:pull_request'::text)),
    v_token,v_request
  )->>'result'='PASS';

  c:=jsonb_set(c,'{event_name}',to_jsonb('workflow_dispatch'::text));
  c:=jsonb_set(c,'{target_branch}','null'::jsonb);
  c:=jsonb_set(c,'{pull_request_number}','null'::jsonb);
  v_legacy_dispatch:=chlom_wallet.validate_institutionalization_ingest_claims_v2(
    p.manifest_body,
    jsonb_set(c,'{oidc_subject}',to_jsonb(('repo:crownthrive1/CrownThrive-Support:ref:refs/heads/'||p.source_branch)::text)),
    v_token,v_request
  )->>'result'='PASS';
  v_immutable_dispatch:=chlom_wallet.validate_institutionalization_ingest_claims_v2(
    p.manifest_body,
    jsonb_set(c,'{oidc_subject}',to_jsonb(('repo:crownthrive1@315660018/CrownThrive-Support@1336348391:ref:refs/heads/'||p.source_branch)::text)),
    v_token,v_request
  )->>'result'='PASS';
  v_wrong_owner:=chlom_wallet.validate_institutionalization_ingest_claims_v2(
    p.manifest_body,
    jsonb_set(c,'{oidc_subject}',to_jsonb(('repo:crownthrive1@999/CrownThrive-Support@1336348391:ref:refs/heads/'||p.source_branch)::text)),
    v_token,v_request
  )->>'result'='FAIL';
  v_wrong_repo:=chlom_wallet.validate_institutionalization_ingest_claims_v2(
    p.manifest_body,
    jsonb_set(c,'{oidc_subject}',to_jsonb(('repo:crownthrive1@315660018/CrownThrive-Support@999:ref:refs/heads/'||p.source_branch)::text)),
    v_token,v_request
  )->>'result'='FAIL';
  v_wrong_branch:=chlom_wallet.validate_institutionalization_ingest_claims_v2(
    p.manifest_body,
    jsonb_set(c,'{oidc_subject}',to_jsonb('repo:crownthrive1@315660018/CrownThrive-Support@1336348391:ref:refs/heads/wrong-branch'::text)),
    v_token,v_request
  )->>'result'='FAIL';

  if not v_legacy_pr or not v_immutable_pr or not v_legacy_dispatch or not v_immutable_dispatch
     or not v_wrong_owner or not v_wrong_repo or not v_wrong_branch then
    raise exception 'institutionalization_oidc_subject_canary_failed';
  end if;

  insert into chlom_wallet.institutionalization_oidc_subject_canary_runs_v2(
    result,legacy_pull_request_subject_accepted,immutable_pull_request_subject_accepted,
    legacy_dispatch_subject_accepted,immutable_dispatch_subject_accepted,
    wrong_owner_id_rejected,wrong_repository_id_rejected,wrong_branch_rejected,evidence
  ) values (
    'PASS_CHLOM_INSTITUTIONALIZATION_OIDC_SUBJECT_V2_CANARY',true,true,true,true,true,true,true,
    jsonb_build_object(
      'github_immutable_subject_cutover_supported',true,
      'repository_id','1336348391','repository_owner_id','315660018',
      'token_value_persisted',false,'provider_write',false,'credential_access',false,
      'money_movement',false,'chain_broadcast',false,'phase_advancement',false,'merge_authorized',false
    )
  ) returning canary_run_id into v_run;

  return jsonb_build_object(
    'result','PASS_CHLOM_INSTITUTIONALIZATION_OIDC_SUBJECT_V2_CANARY',
    'canary_run_id',v_run,
    'legacy_pull_request_subject_accepted',true,
    'immutable_pull_request_subject_accepted',true,
    'legacy_dispatch_subject_accepted',true,
    'immutable_dispatch_subject_accepted',true,
    'wrong_owner_id_rejected',true,
    'wrong_repository_id_rejected',true,
    'wrong_branch_rejected',true,
    'token_value_persisted',false,'provider_write',false,'credential_access',false,
    'money_movement',false,'production_rights_grant',false,'chain_broadcast',false,
    'phase_advancement',false,'merge_authorized',false
  );
end;
$$;

revoke all on function chlom_wallet.run_institutionalization_oidc_subject_canary_v2()
  from public,anon,authenticated;
grant execute on function chlom_wallet.run_institutionalization_oidc_subject_canary_v2()
  to service_role;
