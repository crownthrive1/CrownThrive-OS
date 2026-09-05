begin;

create or replace function penta_pr.reconcile_github_pr_detail_exact_v1(
  p_repo text,
  p_pr_number bigint,
  p_expected_head_sha text
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'penta_pr', 'chlom_runtime', 'vault', 'extensions'
as $fn$
declare
  v_row penta_pr.lifecycle%rowtype;
  v_token text;
  v_detail extensions.http_response;
  v_checks extensions.http_response;
  v_pr jsonb;
  v_check_json jsonb;
  v_check jsonb;
  v_observed_head text;
  v_base_ref text;
  v_mergeable boolean;
  v_mergeable_state text;
  v_check_state text := 'UNKNOWN';
  v_total integer := 0;
  v_returned integer := 0;
  v_logical_total integer := 0;
  v_pending integer := 0;
  v_bad integer := 0;
  v_detail_sha text;
  v_checks_sha text;
  v_event jsonb := '{}'::jsonb;
begin
  if p_repo is null or p_repo !~ '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' then
    raise exception 'INVALID_REPOSITORY';
  end if;
  if p_pr_number is null or p_pr_number <= 0 then
    raise exception 'INVALID_PR_NUMBER';
  end if;
  p_expected_head_sha := lower(coalesce(p_expected_head_sha,''));
  if p_expected_head_sha !~ '^[0-9a-f]{40}$' then
    raise exception 'INVALID_EXPECTED_HEAD_SHA';
  end if;

  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta-pr:exact-detail:'||p_repo||'#'||p_pr_number::text,0)) then
    return jsonb_build_object(
      'service','ct.penta.pr-exact-detail-readback.v1',
      'state','DEFERRED_CONTENTION',
      'repo',p_repo,
      'pr_number',p_pr_number,
      'expected_head_sha',p_expected_head_sha,
      'provider_write',false,
      'authority_created',false,
      'at',clock_timestamp()
    );
  end if;

  select * into v_row
  from penta_pr.lifecycle
  where repo=p_repo and pr_number=p_pr_number and terminal_state is null
  for update;

  if not found or lower(coalesce(v_row.head_sha,'')) <> p_expected_head_sha then
    return jsonb_build_object(
      'service','ct.penta.pr-exact-detail-readback.v1',
      'state','HOLD_PR_NOT_TRACKED_OR_HEAD_MISMATCH',
      'repo',p_repo,
      'pr_number',p_pr_number,
      'expected_head_sha',p_expected_head_sha,
      'tracked_head_sha',v_row.head_sha,
      'provider_write',false,
      'authority_created',false,
      'at',clock_timestamp()
    );
  end if;

  select decrypted_secret into v_token
  from vault.decrypted_secrets
  where name='PENTA_PM_GITHUB_TOKEN'
  order by created_at desc
  limit 1;

  if coalesce(v_token,'')='' then
    return jsonb_build_object(
      'service','ct.penta.pr-exact-detail-readback.v1',
      'state','HOLD_PROVIDER_CREDENTIAL_REFERENCE_UNAVAILABLE',
      'repo',p_repo,
      'pr_number',p_pr_number,
      'expected_head_sha',p_expected_head_sha,
      'provider_write',false,
      'authority_created',false,
      'at',clock_timestamp()
    );
  end if;

  v_detail:=chlom_runtime.dail_http_v1((
    'get'::extensions.http_method,
    ('https://api.github.com/repos/'||p_repo||'/pulls/'||p_pr_number::text)::varchar,
    array[
      extensions.http_header('accept','application/vnd.github+json'),
      extensions.http_header('authorization','Bearer '||v_token),
      extensions.http_header('x-github-api-version','2022-11-28'),
      extensions.http_header('user-agent','CrownThrive-PentaPR-ExactDetail/1.0')
    ]::extensions.http_header[],
    null,
    null
  )::extensions.http_request);

  if v_detail.status<>200 or v_detail.content is null then
    return jsonb_build_object(
      'service','ct.penta.pr-exact-detail-readback.v1',
      'state','HOLD_PROVIDER_DETAIL_UNAVAILABLE',
      'repo',p_repo,
      'pr_number',p_pr_number,
      'expected_head_sha',p_expected_head_sha,
      'http_status',v_detail.status,
      'provider_write',false,
      'authority_created',false,
      'at',clock_timestamp()
    );
  end if;

  begin
    v_pr:=v_detail.content::jsonb;
  exception when others then
    return jsonb_build_object(
      'service','ct.penta.pr-exact-detail-readback.v1',
      'state','HOLD_PROVIDER_DETAIL_PARSE',
      'repo',p_repo,
      'pr_number',p_pr_number,
      'expected_head_sha',p_expected_head_sha,
      'provider_write',false,
      'authority_created',false,
      'at',clock_timestamp()
    );
  end;

  v_observed_head:=lower(coalesce(v_pr#>>'{head,sha}',''));
  if v_observed_head <> p_expected_head_sha then
    insert into penta_pr.events(repo,pr_number,event_type,actor,payload)
    values(p_repo,p_pr_number,'HEAD_DRIFT_EXACT_DETAIL','ct.penta.pr-exact-detail-readback.v1',
      jsonb_build_object('expected_head_sha',p_expected_head_sha,'observed_head_sha',v_observed_head,'provider_write',false,'authority_created',false));
    return jsonb_build_object(
      'service','ct.penta.pr-exact-detail-readback.v1',
      'state','HOLD_HEAD_DRIFT',
      'repo',p_repo,
      'pr_number',p_pr_number,
      'expected_head_sha',p_expected_head_sha,
      'observed_head_sha',v_observed_head,
      'provider_write',false,
      'authority_created',false,
      'at',clock_timestamp()
    );
  end if;

  v_detail_sha:=encode(extensions.digest(convert_to(v_detail.content,'UTF8'),'sha256'),'hex');
  v_base_ref:=coalesce(v_pr#>>'{base,ref}',v_row.base_ref,'main');
  v_mergeable:=case when jsonb_typeof(v_pr->'mergeable')='boolean' then (v_pr->>'mergeable')::boolean else null end;
  v_mergeable_state:=nullif(v_pr->>'mergeable_state','');

  v_checks:=chlom_runtime.dail_http_v1((
    'get'::extensions.http_method,
    ('https://api.github.com/repos/'||p_repo||'/commits/'||p_expected_head_sha||'/check-runs?per_page=100')::varchar,
    array[
      extensions.http_header('accept','application/vnd.github+json'),
      extensions.http_header('authorization','Bearer '||v_token),
      extensions.http_header('x-github-api-version','2022-11-28'),
      extensions.http_header('user-agent','CrownThrive-PentaPR-ExactDetail/1.0')
    ]::extensions.http_header[],
    null,
    null
  )::extensions.http_request);

  if v_checks.status<>200 or v_checks.content is null then
    return jsonb_build_object(
      'service','ct.penta.pr-exact-detail-readback.v1',
      'state','HOLD_PROVIDER_CHECKS_UNAVAILABLE',
      'repo',p_repo,
      'pr_number',p_pr_number,
      'expected_head_sha',p_expected_head_sha,
      'http_status',v_checks.status,
      'provider_write',false,
      'authority_created',false,
      'at',clock_timestamp()
    );
  end if;

  begin
    v_check_json:=v_checks.content::jsonb;
  exception when others then
    return jsonb_build_object(
      'service','ct.penta.pr-exact-detail-readback.v1',
      'state','HOLD_PROVIDER_CHECKS_PARSE',
      'repo',p_repo,
      'pr_number',p_pr_number,
      'expected_head_sha',p_expected_head_sha,
      'provider_write',false,
      'authority_created',false,
      'at',clock_timestamp()
    );
  end;

  v_total:=coalesce((v_check_json->>'total_count')::integer,0);
  v_returned:=jsonb_array_length(coalesce(v_check_json->'check_runs','[]'::jsonb));
  if v_total>v_returned then
    return jsonb_build_object(
      'service','ct.penta.pr-exact-detail-readback.v1',
      'state','HOLD_CHECK_RUN_PAGINATION_REQUIRED',
      'repo',p_repo,
      'pr_number',p_pr_number,
      'expected_head_sha',p_expected_head_sha,
      'check_runs_total',v_total,
      'check_runs_returned',v_returned,
      'provider_write',false,
      'authority_created',false,
      'at',clock_timestamp()
    );
  end if;

  -- GitHub retains historical reruns for the same logical check on one commit.
  -- Evaluate only the newest run for each (GitHub App, check name) identity so a
  -- superseded cancelled/failed attempt cannot poison a later successful rerun.
  -- A currently-latest cancelled/failed check still fails closed.
  for v_check in
    select ranked.value
    from (
      select j.value,
             row_number() over (
               partition by
                 coalesce(nullif(j.value#>>'{app,slug}',''),'unknown-app'),
                 coalesce(nullif(j.value->>'name',''),'check-id:'||coalesce(j.value->>'id','unknown'))
               order by
                 coalesce(
                   nullif(j.value->>'completed_at','')::timestamptz,
                   nullif(j.value->>'started_at','')::timestamptz,
                   'epoch'::timestamptz
                 ) desc,
                 coalesce(nullif(j.value->>'id','')::bigint,0) desc
             ) as rn
      from jsonb_array_elements(coalesce(v_check_json->'check_runs','[]'::jsonb)) as j(value)
    ) as ranked
    where ranked.rn=1
  loop
    v_logical_total:=v_logical_total+1;
    if coalesce(v_check->>'status','')<>'completed' then
      v_pending:=v_pending+1;
    elsif coalesce(v_check->>'conclusion','') not in ('success','neutral','skipped') then
      v_bad:=v_bad+1;
    end if;
  end loop;

  v_check_state:=case
    when v_logical_total=0 then 'UNKNOWN'
    when v_pending>0 then 'PENDING'
    when v_bad>0 then 'FAILURE'
    else 'SUCCESS'
  end;
  v_checks_sha:=encode(extensions.digest(convert_to(v_checks.content,'UTF8'),'sha256'),'hex');

  update penta_pr.lifecycle
  set base_ref=v_base_ref,
      mergeable=v_mergeable,
      checks_state=v_check_state,
      provider_updated_at=coalesce(nullif(v_pr->>'updated_at','')::timestamptz,provider_updated_at),
      last_observed_at=clock_timestamp(),
      metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
        'detail_readback_state','complete_exact',
        'detail_observed_at',clock_timestamp(),
        'detail_observed_head_sha',p_expected_head_sha,
        'detail_response_sha256',v_detail_sha,
        'check_runs_response_sha256',v_checks_sha,
        'mergeable_state',v_mergeable_state,
        'check_runs_total',v_total,
        'check_runs_returned',v_returned,
        'check_runs_logical_total',v_logical_total,
        'check_runs_pending',v_pending,
        'check_runs_nonpass',v_bad,
        'check_run_identity','app_slug+name_latest',
        'raw_provider_body_stored',false,
        'provider_write',false,
        'authority_created',false,
        'exact_refresh',true
      )
  where id=v_row.id and head_sha=p_expected_head_sha and terminal_state is null;

  if not found then
    return jsonb_build_object(
      'service','ct.penta.pr-exact-detail-readback.v1',
      'state','HOLD_LIFECYCLE_CHANGED_DURING_READBACK',
      'repo',p_repo,
      'pr_number',p_pr_number,
      'expected_head_sha',p_expected_head_sha,
      'provider_write',false,
      'authority_created',false,
      'at',clock_timestamp()
    );
  end if;

  insert into penta_pr.events(repo,pr_number,event_type,actor,payload)
  values(p_repo,p_pr_number,'PROVIDER_DETAIL_READBACK_EXACT','ct.penta.pr-exact-detail-readback.v1',
    jsonb_build_object(
      'head_sha',p_expected_head_sha,
      'base_ref',v_base_ref,
      'mergeable',v_mergeable,
      'mergeable_state',v_mergeable_state,
      'checks_state',v_check_state,
      'check_runs_total',v_total,
      'check_runs_logical_total',v_logical_total,
      'check_runs_pending',v_pending,
      'check_runs_nonpass',v_bad,
      'check_run_identity','app_slug+name_latest',
      'detail_response_sha256',v_detail_sha,
      'check_runs_response_sha256',v_checks_sha,
      'provider_write',false,
      'authority_created',false
    ));

  v_event:=chlom_runtime.append_dail_event(
    'penta_pr.lifecycle.github_exact_detail_reconciliation',
    'penta_pr_lifecycle',
    p_repo||'#'||p_pr_number::text,
    jsonb_build_object(
      'repo',p_repo,
      'pr_number',p_pr_number,
      'head_sha',p_expected_head_sha,
      'mergeable',v_mergeable,
      'checks_state',v_check_state,
      'check_runs_total',v_total,
      'check_runs_logical_total',v_logical_total,
      'check_runs_pending',v_pending,
      'check_runs_nonpass',v_bad,
      'check_run_identity','app_slug+name_latest',
      'detail_response_sha256',v_detail_sha,
      'check_runs_response_sha256',v_checks_sha,
      'raw_provider_body_stored',false,
      'provider_write',false,
      'authority_created',false,
      'observed_at',clock_timestamp()
    ),
    'ct.penta.pr-exact-detail-readback.v1',null,'ct.penta.pr-exact-detail-readback.v1',
    'v1',p_repo||'#'||p_pr_number::text||':github-exact-detail',null,'ct.penta.pr.v1',null,'internal'
  );

  return jsonb_build_object(
    'service','ct.penta.pr-exact-detail-readback.v1',
    'state','PASS',
    'repo',p_repo,
    'pr_number',p_pr_number,
    'head_sha',p_expected_head_sha,
    'mergeable',v_mergeable,
    'checks_state',v_check_state,
    'check_runs_total',v_total,
    'check_runs_logical_total',v_logical_total,
    'check_runs_pending',v_pending,
    'check_runs_nonpass',v_bad,
    'check_run_identity','app_slug+name_latest',
    'dail_event_id',v_event->>'event_id',
    'provider_write',false,
    'authority_created',false,
    'at',clock_timestamp()
  );
end;
$fn$;

create or replace function public.penta_pr_refresh_exact_detail_v1(
  p_repo text,
  p_pr_number bigint,
  p_expected_head_sha text
)
returns jsonb
language sql
security definer
set search_path to 'pg_catalog', 'penta_pr'
as $fn$
  select penta_pr.reconcile_github_pr_detail_exact_v1(p_repo,p_pr_number,p_expected_head_sha);
$fn$;

revoke all on function penta_pr.reconcile_github_pr_detail_exact_v1(text,bigint,text) from public, anon, authenticated;
revoke all on function public.penta_pr_refresh_exact_detail_v1(text,bigint,text) from public, anon, authenticated;
grant execute on function public.penta_pr_refresh_exact_detail_v1(text,bigint,text) to service_role;

comment on function penta_pr.reconcile_github_pr_detail_exact_v1(text,bigint,text) is
  'Exact-head, read-only GitHub PR/check reconciliation for one tracked open PR. Collapses superseded reruns by latest GitHub App + check name and fails closed on the current logical check state, head drift, provider/readback failure, pagination, or lifecycle drift; does not mutate provider state or create authority.';
comment on function public.penta_pr_refresh_exact_detail_v1(text,bigint,text) is
  'Service-role wrapper for bounded exact-head PentaPR detail/check refresh.';

commit;
