-- ct.penta.pr-exact-head-detail-refresh.v1
-- Bounded read-only provider refresh for one exact GitHub PR head.
-- Repairs stale lifecycle/check snapshots without widening merge, certification,
-- credential, D3, money, rights, branch-delete, or authority boundaries.

begin;

create or replace function penta_pr.reconcile_github_pr_detail_exact_v1(
  p_repo text,
  p_pr_number bigint,
  p_expected_head_sha text
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_pr,integration_control,chlom_runtime,vault,extensions
as $function$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_canonical_repo text;
  v_token text;
  v_rate extensions.http_response;
  v_detail extensions.http_response;
  v_checks extensions.http_response;
  v_rate_json jsonb;
  v_pr jsonb;
  v_check_json jsonb;
  v_check jsonb;
  v_row penta_pr.lifecycle%rowtype;
  v_observed_head text;
  v_base_ref text;
  v_mergeable boolean;
  v_mergeable_state text;
  v_check_state text:='UNKNOWN';
  v_total integer:=0;
  v_returned integer:=0;
  v_pending integer:=0;
  v_bad integer:=0;
  v_remaining integer:=0;
  v_detail_sha text;
  v_checks_sha text;
  v_event jsonb:='{}'::jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required';
  end if;
  if p_repo is null or p_repo !~ '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' then
    raise exception 'INVALID_REPOSITORY';
  end if;
  if p_pr_number is null or p_pr_number<1 then raise exception 'INVALID_PR_NUMBER'; end if;
  if lower(coalesce(p_expected_head_sha,'')) !~ '^[0-9a-f]{40}$' then raise exception 'INVALID_EXPECTED_HEAD_SHA'; end if;

  select repository_full_name into v_canonical_repo
  from integration_control.cos_repository_census_v1
  where lower(repository_full_name)=lower(btrim(p_repo))
    and lower(owner_login)='crownthrive1'
    and archived=false and operationally_enabled=true and lifecycle_state='active'
  order by updated_at desc limit 1;
  if v_canonical_repo is null then raise exception 'repository_not_allowed'; end if;

  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta-pr:detail-exact:'||lower(v_canonical_repo)||':'||p_pr_number::text,0)) then
    return jsonb_build_object('service','ct.penta.pr-exact-head-detail-refresh.v1','state','DEFERRED_CONTENTION','repo',lower(v_canonical_repo),'pr_number',p_pr_number,'expected_head_sha',lower(p_expected_head_sha),'provider_write',false,'authority_created',false);
  end if;

  select * into v_row
  from penta_pr.lifecycle
  where repo=lower(v_canonical_repo) and pr_number=p_pr_number
  for update;
  if not found then
    return jsonb_build_object('service','ct.penta.pr-exact-head-detail-refresh.v1','state','HOLD_PR_NOT_TRACKED','repo',lower(v_canonical_repo),'pr_number',p_pr_number,'provider_write',false,'authority_created',false);
  end if;
  if v_row.terminal_state is not null then
    return jsonb_build_object('service','ct.penta.pr-exact-head-detail-refresh.v1','state','HOLD_PR_TERMINAL','repo',lower(v_canonical_repo),'pr_number',p_pr_number,'terminal_state',v_row.terminal_state,'provider_write',false,'authority_created',false);
  end if;
  if lower(coalesce(v_row.head_sha,'')) is distinct from lower(p_expected_head_sha) then
    return jsonb_build_object('service','ct.penta.pr-exact-head-detail-refresh.v1','state','HOLD_HEAD_MISMATCH','repo',lower(v_canonical_repo),'pr_number',p_pr_number,'expected_head_sha',lower(p_expected_head_sha),'tracked_head_sha',v_row.head_sha,'provider_write',false,'authority_created',false);
  end if;

  select decrypted_secret into v_token
  from vault.decrypted_secrets
  where name='PENTA_PM_GITHUB_TOKEN'
  order by created_at desc limit 1;
  if coalesce(v_token,'')='' then
    return jsonb_build_object('service','ct.penta.pr-exact-head-detail-refresh.v1','state','HOLD_PROVIDER_CREDENTIAL_REFERENCE_UNAVAILABLE','repo',lower(v_canonical_repo),'pr_number',p_pr_number,'provider_write',false,'authority_created',false);
  end if;

  v_rate:=chlom_runtime.dail_http_v1((
    'get'::extensions.http_method,
    'https://api.github.com/rate_limit'::varchar,
    array[
      extensions.http_header('accept','application/vnd.github+json'),
      extensions.http_header('authorization','Bearer '||v_token),
      extensions.http_header('x-github-api-version','2022-11-28'),
      extensions.http_header('user-agent','CrownThrive-PentaPR-ExactDetail/1.0')
    ]::extensions.http_header[],null,null
  )::extensions.http_request);
  if v_rate.status<>200 or v_rate.content is null then
    return jsonb_build_object('service','ct.penta.pr-exact-head-detail-refresh.v1','state','HOLD_PROVIDER_RATE_PREFLIGHT_UNAVAILABLE','repo',lower(v_canonical_repo),'pr_number',p_pr_number,'http_status',v_rate.status,'provider_write',false,'authority_created',false);
  end if;
  begin v_rate_json:=v_rate.content::jsonb; exception when others then v_rate_json:='{}'::jsonb; end;
  v_remaining:=coalesce((v_rate_json#>>'{resources,core,remaining}')::integer,0);
  if v_remaining<3 then
    return jsonb_build_object('service','ct.penta.pr-exact-head-detail-refresh.v1','state','HOLD_PROVIDER_RATE_BUDGET','repo',lower(v_canonical_repo),'pr_number',p_pr_number,'core_remaining',v_remaining,'provider_write',false,'authority_created',false);
  end if;

  v_detail:=chlom_runtime.dail_http_v1((
    'get'::extensions.http_method,
    ('https://api.github.com/repos/'||v_canonical_repo||'/pulls/'||p_pr_number::text)::varchar,
    array[
      extensions.http_header('accept','application/vnd.github+json'),
      extensions.http_header('authorization','Bearer '||v_token),
      extensions.http_header('x-github-api-version','2022-11-28'),
      extensions.http_header('user-agent','CrownThrive-PentaPR-ExactDetail/1.0')
    ]::extensions.http_header[],null,null
  )::extensions.http_request);
  if v_detail.status<>200 or v_detail.content is null then
    return jsonb_build_object('service','ct.penta.pr-exact-head-detail-refresh.v1','state','HOLD_PROVIDER_PR_READBACK','repo',lower(v_canonical_repo),'pr_number',p_pr_number,'http_status',v_detail.status,'provider_write',false,'authority_created',false);
  end if;
  begin v_pr:=v_detail.content::jsonb; exception when others then
    return jsonb_build_object('service','ct.penta.pr-exact-head-detail-refresh.v1','state','HOLD_PROVIDER_PR_PARSE','repo',lower(v_canonical_repo),'pr_number',p_pr_number,'provider_write',false,'authority_created',false);
  end;

  v_observed_head:=lower(coalesce(v_pr#>>'{head,sha}',''));
  if v_observed_head is distinct from lower(p_expected_head_sha) then
    return jsonb_build_object('service','ct.penta.pr-exact-head-detail-refresh.v1','state','HOLD_PROVIDER_HEAD_DRIFT','repo',lower(v_canonical_repo),'pr_number',p_pr_number,'expected_head_sha',lower(p_expected_head_sha),'observed_head_sha',v_observed_head,'provider_write',false,'authority_created',false);
  end if;
  if coalesce(v_pr->>'state','')<>'open' then
    return jsonb_build_object('service','ct.penta.pr-exact-head-detail-refresh.v1','state','HOLD_PROVIDER_PR_NOT_OPEN','repo',lower(v_canonical_repo),'pr_number',p_pr_number,'provider_state',v_pr->>'state','provider_write',false,'authority_created',false);
  end if;

  v_base_ref:=coalesce(v_pr#>>'{base,ref}',v_row.base_ref,'main');
  v_mergeable:=case when jsonb_typeof(v_pr->'mergeable')='boolean' then (v_pr->>'mergeable')::boolean else null end;
  v_mergeable_state:=nullif(v_pr->>'mergeable_state','');
  v_detail_sha:=encode(extensions.digest(convert_to(v_detail.content,'UTF8'),'sha256'),'hex');

  v_checks:=chlom_runtime.dail_http_v1((
    'get'::extensions.http_method,
    ('https://api.github.com/repos/'||v_canonical_repo||'/commits/'||v_observed_head||'/check-runs?per_page=100')::varchar,
    array[
      extensions.http_header('accept','application/vnd.github+json'),
      extensions.http_header('authorization','Bearer '||v_token),
      extensions.http_header('x-github-api-version','2022-11-28'),
      extensions.http_header('user-agent','CrownThrive-PentaPR-ExactDetail/1.0')
    ]::extensions.http_header[],null,null
  )::extensions.http_request);
  if v_checks.status<>200 or v_checks.content is null then
    return jsonb_build_object('service','ct.penta.pr-exact-head-detail-refresh.v1','state','HOLD_PROVIDER_CHECK_READBACK','repo',lower(v_canonical_repo),'pr_number',p_pr_number,'http_status',v_checks.status,'provider_write',false,'authority_created',false);
  end if;
  begin v_check_json:=v_checks.content::jsonb; exception when others then
    return jsonb_build_object('service','ct.penta.pr-exact-head-detail-refresh.v1','state','HOLD_PROVIDER_CHECK_PARSE','repo',lower(v_canonical_repo),'pr_number',p_pr_number,'provider_write',false,'authority_created',false);
  end;

  v_total:=coalesce((v_check_json->>'total_count')::integer,0);
  v_returned:=jsonb_array_length(coalesce(v_check_json->'check_runs','[]'::jsonb));
  if v_total>v_returned then
    return jsonb_build_object('service','ct.penta.pr-exact-head-detail-refresh.v1','state','HOLD_CHECK_RUN_PAGINATION_REQUIRED','repo',lower(v_canonical_repo),'pr_number',p_pr_number,'check_runs_total',v_total,'check_runs_returned',v_returned,'provider_write',false,'authority_created',false);
  end if;
  for v_check in select value from jsonb_array_elements(coalesce(v_check_json->'check_runs','[]'::jsonb)) loop
    if coalesce(v_check->>'status','')<>'completed' then
      v_pending:=v_pending+1;
    elsif coalesce(v_check->>'conclusion','') not in ('success','neutral','skipped') then
      v_bad:=v_bad+1;
    end if;
  end loop;
  v_check_state:=case when v_total=0 then 'UNKNOWN' when v_pending>0 then 'PENDING' when v_bad>0 then 'FAILURE' else 'SUCCESS' end;
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
        'detail_observed_head_sha',v_observed_head,
        'detail_response_sha256',v_detail_sha,
        'check_runs_response_sha256',v_checks_sha,
        'mergeable_state',v_mergeable_state,
        'check_runs_total',v_total,
        'check_runs_pending',v_pending,
        'check_runs_nonpass',v_bad,
        'exact_refresh',true,
        'raw_provider_body_stored',false,
        'provider_write',false,
        'authority_created',false
      )
  where repo=lower(v_canonical_repo) and pr_number=p_pr_number and head_sha=lower(p_expected_head_sha) and terminal_state is null;
  if not found then raise exception 'exact_head_update_lost_race'; end if;

  insert into penta_pr.events(repo,pr_number,event_type,actor,payload)
  values(lower(v_canonical_repo),p_pr_number,'PROVIDER_DETAIL_EXACT_READBACK','ct.penta.pr-exact-head-detail-refresh.v1',jsonb_build_object(
    'head_sha',v_observed_head,'base_ref',v_base_ref,'mergeable',v_mergeable,'mergeable_state',v_mergeable_state,
    'checks_state',v_check_state,'check_runs_total',v_total,'check_runs_pending',v_pending,'check_runs_nonpass',v_bad,
    'detail_response_sha256',v_detail_sha,'check_runs_response_sha256',v_checks_sha,
    'provider_write',false,'authority_created',false));

  v_event:=chlom_runtime.append_dail_event(
    'penta_pr.lifecycle.github_exact_detail_reconciliation','penta_pr_lifecycle',lower(v_canonical_repo)||'#'||p_pr_number::text,
    jsonb_build_object('repo',lower(v_canonical_repo),'pr_number',p_pr_number,'head_sha',v_observed_head,'checks_state',v_check_state,'check_runs_total',v_total,'check_runs_pending',v_pending,'check_runs_nonpass',v_bad,'mergeable',v_mergeable,'raw_provider_body_stored',false,'provider_write',false,'authority_created',false,'observed_at',clock_timestamp()),
    'ct.penta.pr-exact-head-detail-refresh.v1',null,'ct.penta.pr-exact-head-detail-refresh.v1','v1',lower(v_canonical_repo)||'#'||p_pr_number::text||'@'||v_observed_head,null,'ct.penta.pr.v1',null,'internal'
  );

  return jsonb_build_object('service','ct.penta.pr-exact-head-detail-refresh.v1','state','PASS','repo',lower(v_canonical_repo),'pr_number',p_pr_number,'head_sha',v_observed_head,'mergeable',v_mergeable,'checks_state',v_check_state,'check_runs_total',v_total,'check_runs_pending',v_pending,'check_runs_nonpass',v_bad,'detail_response_sha256',v_detail_sha,'check_runs_response_sha256',v_checks_sha,'dail_event_id',v_event->>'event_id','provider_write',false,'authority_created',false);
end
$function$;

revoke all on function penta_pr.reconcile_github_pr_detail_exact_v1(text,bigint,text) from public,anon,authenticated;
grant execute on function penta_pr.reconcile_github_pr_detail_exact_v1(text,bigint,text) to service_role;

create or replace function public.penta_pr_detail_refresh_exact_v1(
  p_repo text,
  p_pr_number bigint,
  p_expected_head_sha text
) returns jsonb
language sql
security definer
set search_path=pg_catalog,penta_pr
as $function$
  select penta_pr.reconcile_github_pr_detail_exact_v1(p_repo,p_pr_number,p_expected_head_sha);
$function$;

revoke all on function public.penta_pr_detail_refresh_exact_v1(text,bigint,text) from public,anon,authenticated;
grant execute on function public.penta_pr_detail_refresh_exact_v1(text,bigint,text) to service_role;

commit;
