-- COS V1 GitHub provider readback v2
--
-- Purpose:
--   * remove stale coupling to the historical COS source PR/branch;
--   * bind provider readback to the caller-supplied exact GitHub main SHA;
--   * verify main remains stable across the readback, commit signature, branch
--     protection, check-runs, and legacy commit-status contexts;
--   * emit append-only provider evidence for independent PentaCertifier use;
--   * NEVER accept source, certify, deploy, release, or exercise D3 authority.
--
-- Governed pre-state fingerprint:
--   sha256(pg_get_functiondef(...)) =
--   2e59ac0c18d54c2dadfa1ac42ea41fc39534ecf9f1d8b82c15c18da9f43887a0
--
-- Rollback is bounded by the companion exact-prestate rollback artifact.

create or replace function integration_control.cos_v1_github_release_readback_v1(
  p_expected_source_sha text
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','public','extensions','chlom_runtime'
as $function$
declare
  v_main_resp extensions.http_response;
  v_main jsonb;
  v_confirm_resp extensions.http_response;
  v_confirm jsonb;
  v_checks_resp extensions.http_response;
  v_checks jsonb;
  v_status_resp extensions.http_response;
  v_status jsonb;
  v_main_sha text;
  v_confirm_sha text;
  v_branch_protected boolean:=false;
  v_commit_verified boolean:=false;
  v_check_total integer:=0;
  v_check_pending integer:=0;
  v_check_failed integer:=0;
  v_status_total integer:=0;
  v_status_state text;
  v_evidence_sha text;
  v_existing_evidence_sha text;
  v_event jsonb;
begin
  if current_user not in ('postgres','service_role') then
    raise exception 'service_role_required';
  end if;
  if p_expected_source_sha is null or p_expected_source_sha !~ '^[0-9a-f]{40}$' then
    raise exception 'invalid_expected_source_sha';
  end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:cos:v1:github-release-readback',0)) then
    return jsonb_build_object('ok',true,'state','skipped_concurrent_run');
  end if;

  perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS','30000');
  perform extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT_MS','5000');

  -- Exact current-main readback. No PR number, historical branch, or merge commit
  -- is authoritative for this predicate.
  v_main_resp:=chlom_runtime.dail_http_v1((
    'GET'::extensions.http_method,
    'https://api.github.com/repos/crownthrive1/CrownThrive-OS/branches/main'::varchar,
    array[
      extensions.http_header('Accept'::varchar,'application/vnd.github+json'::varchar),
      extensions.http_header('X-GitHub-Api-Version'::varchar,'2022-11-28'::varchar),
      extensions.http_header('User-Agent'::varchar,'CrownThrive-COS-GitHub-Readback/2.0'::varchar)
    ]::extensions.http_header[],null::varchar,null::varchar
  )::extensions.http_request);
  if v_main_resp.status<>200 then
    return jsonb_build_object(
      'ok',false,'state','hold','reason','github_main_read_failed',
      'http_status',v_main_resp.status,
      'response_sha256',encode(extensions.digest(convert_to(coalesce(v_main_resp.content,''),'UTF8'),'sha256'),'hex'),
      'release_authority',false,'source_acceptance',false,'certification',false
    );
  end if;

  begin
    v_main:=v_main_resp.content::jsonb;
  exception when others then
    return jsonb_build_object('ok',false,'state','hold','reason','github_main_response_invalid_json',
      'release_authority',false,'source_acceptance',false,'certification',false);
  end;

  v_main_sha:=v_main#>>'{commit,sha}';
  if v_main_sha is null or v_main_sha !~ '^[0-9a-f]{40}$' then
    return jsonb_build_object('ok',false,'state','hold','reason','github_main_sha_invalid',
      'observed_main_sha',v_main_sha,'release_authority',false,'source_acceptance',false,'certification',false);
  end if;
  if lower(v_main_sha)<>lower(p_expected_source_sha) then
    return jsonb_build_object('ok',false,'state','hold','reason','github_main_sha_mismatch',
      'expected_source_sha',lower(p_expected_source_sha),'observed_main_sha',lower(v_main_sha),
      'release_authority',false,'source_acceptance',false,'certification',false);
  end if;

  begin
    v_branch_protected:=coalesce((v_main->>'protected')::boolean,false);
  exception when others then
    v_branch_protected:=false;
  end;
  begin
    v_commit_verified:=coalesce((v_main#>>'{commit,commit,verification,verified}')::boolean,false);
  exception when others then
    v_commit_verified:=false;
  end;

  if not v_branch_protected then
    return jsonb_build_object('ok',false,'state','hold','reason','github_main_not_protected',
      'expected_source_sha',lower(p_expected_source_sha),'observed_main_sha',lower(v_main_sha),
      'branch_protected',false,'release_authority',false,'source_acceptance',false,'certification',false);
  end if;
  if not v_commit_verified then
    return jsonb_build_object('ok',false,'state','hold','reason','github_main_commit_unverified',
      'expected_source_sha',lower(p_expected_source_sha),'observed_main_sha',lower(v_main_sha),
      'commit_verified',false,'release_authority',false,'source_acceptance',false,'certification',false);
  end if;

  -- Modern checks are required. Pending or non-success-like conclusions HOLD.
  v_checks_resp:=chlom_runtime.dail_http_v1((
    'GET'::extensions.http_method,
    ('https://api.github.com/repos/crownthrive1/CrownThrive-OS/commits/'||lower(p_expected_source_sha)||'/check-runs?per_page=100')::varchar,
    array[
      extensions.http_header('Accept'::varchar,'application/vnd.github+json'::varchar),
      extensions.http_header('X-GitHub-Api-Version'::varchar,'2022-11-28'::varchar),
      extensions.http_header('User-Agent'::varchar,'CrownThrive-COS-GitHub-Readback/2.0'::varchar)
    ]::extensions.http_header[],null::varchar,null::varchar
  )::extensions.http_request);
  if v_checks_resp.status<>200 then
    return jsonb_build_object('ok',false,'state','hold','reason','github_check_runs_read_failed',
      'http_status',v_checks_resp.status,'expected_source_sha',lower(p_expected_source_sha),
      'response_sha256',encode(extensions.digest(convert_to(coalesce(v_checks_resp.content,''),'UTF8'),'sha256'),'hex'),
      'release_authority',false,'source_acceptance',false,'certification',false);
  end if;
  begin
    v_checks:=v_checks_resp.content::jsonb;
    v_check_total:=coalesce((v_checks->>'total_count')::integer,0);
  exception when others then
    return jsonb_build_object('ok',false,'state','hold','reason','github_check_runs_response_invalid',
      'release_authority',false,'source_acceptance',false,'certification',false);
  end;

  select
    count(*) filter (where coalesce(r->>'status','')<>'completed'),
    count(*) filter (where coalesce(r->>'status','')='completed'
      and coalesce(r->>'conclusion','') not in ('success','neutral','skipped'))
  into v_check_pending,v_check_failed
  from jsonb_array_elements(coalesce(v_checks->'check_runs','[]'::jsonb)) r;

  if v_check_total<=0 then
    return jsonb_build_object('ok',false,'state','hold','reason','github_check_runs_missing',
      'expected_source_sha',lower(p_expected_source_sha),'check_run_total',v_check_total,
      'release_authority',false,'source_acceptance',false,'certification',false);
  end if;
  if v_check_pending>0 or v_check_failed>0 then
    return jsonb_build_object('ok',false,'state','hold','reason','github_check_runs_not_green',
      'expected_source_sha',lower(p_expected_source_sha),'check_run_total',v_check_total,
      'check_run_pending',v_check_pending,'check_run_failed',v_check_failed,
      'release_authority',false,'source_acceptance',false,'certification',false);
  end if;

  -- Legacy commit statuses are a parallel compatibility predicate. If any
  -- exist, the combined state must be success. No legacy contexts is not a
  -- failure because check-runs above are mandatory.
  v_status_resp:=chlom_runtime.dail_http_v1((
    'GET'::extensions.http_method,
    ('https://api.github.com/repos/crownthrive1/CrownThrive-OS/commits/'||lower(p_expected_source_sha)||'/status')::varchar,
    array[
      extensions.http_header('Accept'::varchar,'application/vnd.github+json'::varchar),
      extensions.http_header('X-GitHub-Api-Version'::varchar,'2022-11-28'::varchar),
      extensions.http_header('User-Agent'::varchar,'CrownThrive-COS-GitHub-Readback/2.0'::varchar)
    ]::extensions.http_header[],null::varchar,null::varchar
  )::extensions.http_request);
  if v_status_resp.status<>200 then
    return jsonb_build_object('ok',false,'state','hold','reason','github_commit_status_read_failed',
      'http_status',v_status_resp.status,'expected_source_sha',lower(p_expected_source_sha),
      'response_sha256',encode(extensions.digest(convert_to(coalesce(v_status_resp.content,''),'UTF8'),'sha256'),'hex'),
      'release_authority',false,'source_acceptance',false,'certification',false);
  end if;
  begin
    v_status:=v_status_resp.content::jsonb;
    v_status_total:=jsonb_array_length(coalesce(v_status->'statuses','[]'::jsonb));
    v_status_state:=v_status->>'state';
  exception when others then
    return jsonb_build_object('ok',false,'state','hold','reason','github_commit_status_response_invalid',
      'release_authority',false,'source_acceptance',false,'certification',false);
  end;
  if v_status_total>0 and coalesce(v_status_state,'')<>'success' then
    return jsonb_build_object('ok',false,'state','hold','reason','github_commit_status_not_green',
      'expected_source_sha',lower(p_expected_source_sha),'status_context_total',v_status_total,
      'combined_status',v_status_state,'release_authority',false,'source_acceptance',false,'certification',false);
  end if;

  -- TOCTOU fence: main must still be exactly the expected SHA after all
  -- provider check reads complete.
  v_confirm_resp:=chlom_runtime.dail_http_v1((
    'GET'::extensions.http_method,
    'https://api.github.com/repos/crownthrive1/CrownThrive-OS/branches/main'::varchar,
    array[
      extensions.http_header('Accept'::varchar,'application/vnd.github+json'::varchar),
      extensions.http_header('X-GitHub-Api-Version'::varchar,'2022-11-28'::varchar),
      extensions.http_header('User-Agent'::varchar,'CrownThrive-COS-GitHub-Readback/2.0'::varchar)
    ]::extensions.http_header[],null::varchar,null::varchar
  )::extensions.http_request);
  if v_confirm_resp.status<>200 then
    return jsonb_build_object('ok',false,'state','hold','reason','github_main_confirm_read_failed',
      'http_status',v_confirm_resp.status,'release_authority',false,'source_acceptance',false,'certification',false);
  end if;
  begin
    v_confirm:=v_confirm_resp.content::jsonb;
    v_confirm_sha:=v_confirm#>>'{commit,sha}';
  exception when others then
    v_confirm_sha:=null;
  end;
  if v_confirm_sha is null or lower(v_confirm_sha)<>lower(p_expected_source_sha) then
    return jsonb_build_object('ok',false,'state','hold','reason','github_main_changed_during_readback',
      'expected_source_sha',lower(p_expected_source_sha),'initial_main_sha',lower(v_main_sha),
      'confirmed_main_sha',lower(coalesce(v_confirm_sha,'')),
      'release_authority',false,'source_acceptance',false,'certification',false);
  end if;

  v_evidence_sha:=public.penta_protocol_sha256_v1(jsonb_build_object(
    'contract','ct.cos.v1.github-source-readback.v2',
    'repository','crownthrive1/CrownThrive-OS',
    'branch','main',
    'expected_source_sha',lower(p_expected_source_sha),
    'initial_main_sha',lower(v_main_sha),
    'confirmed_main_sha',lower(v_confirm_sha),
    'branch_protected',v_branch_protected,
    'commit_verified',v_commit_verified,
    'check_run_total',v_check_total,
    'check_run_pending',v_check_pending,
    'check_run_failed',v_check_failed,
    'status_context_total',v_status_total,
    'combined_status',v_status_state,
    'main_response_sha256',encode(extensions.digest(convert_to(v_main_resp.content,'UTF8'),'sha256'),'hex'),
    'checks_response_sha256',encode(extensions.digest(convert_to(v_checks_resp.content,'UTF8'),'sha256'),'hex'),
    'status_response_sha256',encode(extensions.digest(convert_to(v_status_resp.content,'UTF8'),'sha256'),'hex'),
    'confirm_response_sha256',encode(extensions.digest(convert_to(v_confirm_resp.content,'UTF8'),'sha256'),'hex'),
    'release_authority',false,
    'source_acceptance',false,
    'certification',false,
    'D3_human_reserved',true
  ));

  select metadata#>>'{github_source_readback,evidence_sha256}'
  into v_existing_evidence_sha
  from integration_control.cos_release_registry_v1
  where release_id='ct.cos.release.1.0.0';

  if v_existing_evidence_sha=v_evidence_sha then
    return jsonb_build_object(
      'ok',true,'state','idempotent_ready_for_pentacertifier',
      'source_sha',lower(p_expected_source_sha),'production_main_sha',lower(v_main_sha),
      'branch_protected',v_branch_protected,'commit_verified',v_commit_verified,
      'check_run_total',v_check_total,'check_run_pending',v_check_pending,'check_run_failed',v_check_failed,
      'status_context_total',v_status_total,'combined_status',v_status_state,
      'evidence_sha256',v_evidence_sha,
      'release_authority',false,'source_acceptance',false,'certification',false,'D3_human_reserved',true
    );
  end if;

  update integration_control.cos_release_registry_v1
  set metadata=metadata||jsonb_build_object(
        'github_source_readback',jsonb_build_object(
          'contract','ct.cos.v1.github-source-readback.v2',
          'repository','crownthrive1/CrownThrive-OS','branch','main',
          'expected_source_sha',lower(p_expected_source_sha),
          'initial_main_sha',lower(v_main_sha),'confirmed_main_sha',lower(v_confirm_sha),
          'branch_protected',v_branch_protected,'commit_verified',v_commit_verified,
          'check_run_total',v_check_total,'check_run_pending',v_check_pending,'check_run_failed',v_check_failed,
          'status_context_total',v_status_total,'combined_status',v_status_state,
          'evidence_sha256',v_evidence_sha,'observed_at',clock_timestamp(),
          'release_authority',false,'source_acceptance',false,'certification',false,
          'D3_human_reserved',true,'authority_expansion',false
        )
      ),updated_at=clock_timestamp()
  where release_id='ct.cos.release.1.0.0';

  v_event:=chlom_runtime.append_dail_event(
    'cos.v1.github_source_readback.ready_for_certifier','release_readback','ct.cos.release.1.0.0',
    jsonb_build_object(
      'contract','ct.cos.v1.github-source-readback.v2',
      'source_sha',lower(p_expected_source_sha),'production_main_sha',lower(v_main_sha),
      'branch_protected',v_branch_protected,'commit_verified',v_commit_verified,
      'check_run_total',v_check_total,'check_run_pending',v_check_pending,'check_run_failed',v_check_failed,
      'status_context_total',v_status_total,'combined_status',v_status_state,
      'evidence_sha256',v_evidence_sha,'three_dail_logical_phase','DAIL-EVIDENCE',
      'next_owner','PentaCertify','release_authority',false,'source_acceptance',false,
      'certification',false,'D3_human_reserved',true,'authority_expansion',false
    ),
    'COS/PentaFederation/GitHubReadback',null,'PentaFederation','2.0.0',
    'ctcorr:cos-v1-github-source-readback-v2-'||lower(p_expected_source_sha),null,
    'D1_EVIDENCE',null,'internal'
  );

  return jsonb_build_object(
    'ok',true,'state','ready_for_pentacertifier',
    'source_sha',lower(p_expected_source_sha),'production_main_sha',lower(v_main_sha),
    'branch_protected',v_branch_protected,'commit_verified',v_commit_verified,
    'check_run_total',v_check_total,'check_run_pending',v_check_pending,'check_run_failed',v_check_failed,
    'status_context_total',v_status_total,'combined_status',v_status_state,
    'evidence_sha256',v_evidence_sha,'dail',v_event,
    'next_owner','PentaCertify','release_authority',false,'source_acceptance',false,
    'certification',false,'D3_human_reserved',true,'authority_expansion',false
  );
end
$function$;

comment on function integration_control.cos_v1_github_release_readback_v1(text) is
  'COS V1 exact-main GitHub provider evidence readback. Fail-closed; no source acceptance, certification, deployment, release, D3, or authority expansion. Successful evidence routes to independent PentaCertify.';
