-- ct.penta.certify.universal-pr-exact-head-intake.v2
-- Source custody for the production repair. Exact-head intake is separate from adapter dispatch.
-- Provider reads occur before any bounded DAIL summary append. No D3, money, rights, credential,
-- provider-write, merge, release, or self-certification authority is created.

create index if not exists idx_penta_pr_lifecycle_open_repo_head_v1
  on penta_pr.lifecycle(repo, pr_number, head_sha)
  where terminal_state is null;

create or replace function integration_control.penta_certify_pr_exact_head_seed_v1(
  p_repo text default 'crownthrive1/CrownThrive-OS'
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','penta_pr','penta_runtime','extensions'
as $function$
declare
  r record;
  v_task_id uuid;
  v_task_key text;
  v_surface text;
  v_originator text;
  v_risk text;
  v_disposition text;
  v_reason text;
  v_draft boolean;
  v_seeded integer:=0;
  v_refreshed integer:=0;
  v_invalidated integer:=0;
  v_rowcount integer:=0;
begin
  if p_repo is null or p_repo !~ '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' then raise exception 'INVALID_REPOSITORY'; end if;
  for r in
    select l.repo,l.pr_number,l.head_sha,l.base_ref,l.mergeable,l.checks_state,l.disposition as lifecycle_disposition,
           l.reason,l.labels,l.metadata,l.last_observed_at,l.provider_updated_at
    from penta_pr.lifecycle l
    where l.repo=p_repo and l.terminal_state is null and l.head_sha ~ '^[0-9a-f]{40}$'
    order by l.pr_number
  loop
    v_surface:='github_pr:'||r.repo||'#'||r.pr_number::text;
    v_task_key:='pr-exact-head:'||r.repo||'#'||r.pr_number::text||'@'||r.head_sha;
    v_draft:=coalesce((r.metadata->>'draft')::boolean,false);
    v_originator:=null; v_risk:=null;
    select c.originator_system_key,case when c.risk_class in ('D0','D1','D2') then c.risk_class else 'D2' end
      into v_originator,v_risk
    from integration_control.penta_change_current_v1 c
    where c.repository=r.repo and c.pr_number=r.pr_number and c.exact_head_sha=r.head_sha limit 1;
    v_risk:=coalesce(v_risk,'D2');
    if v_originator='penta.certify' then v_disposition:='HOLD_CERTIFICATION'; v_reason:='ORIGINATOR_SEPARATION_REQUIRED';
    elsif v_draft then v_disposition:='WAITING_DEPENDENCY'; v_reason:='DRAFT_PR';
    elsif r.mergeable is false then v_disposition:='WAITING_DEPENDENCY'; v_reason:='CURRENT_PROVIDER_MERGEABILITY_FALSE';
    elsif r.mergeable is null then v_disposition:='HOLD_CERTIFICATION'; v_reason:='PROVIDER_DETAIL_READBACK_REQUIRED';
    else v_disposition:='HOLD_CERTIFICATION'; v_reason:='READY_FOR_INDEPENDENT_GATE_EVALUATION'; end if;

    update integration_control.penta_certify_tasks_v3 t
       set state='cancelled',last_error='PR_HEAD_SUPERSEDED',lease_owner=null,lease_expires_at=null,
           evidence=coalesce(t.evidence,'{}'::jsonb)||jsonb_build_object(
             'invalidated',true,'invalidated_reason','PR_HEAD_CHANGED','superseded_by_head_sha',r.head_sha,
             'invalidated_at',clock_timestamp()),updated_at=now()
     where t.surface_id=v_surface and t.task_kind='inspect'
       and coalesce(t.source_snapshot->>'head_sha','')<>r.head_sha and t.state<>'cancelled';
    get diagnostics v_rowcount = row_count;
    v_invalidated:=v_invalidated+v_rowcount;

    insert into integration_control.penta_certify_tasks_v3(
      task_key,surface_id,provider_system,source_certification_state,task_kind,owner_component_key,risk_class,
      state,available_at,max_attempts,source_snapshot,evidence,last_error,software_generation)
    values(
      v_task_key,v_surface,'github','pr_exact_head','inspect','penta.certify',v_risk,'blocked',now(),1,
      jsonb_build_object('repo',r.repo,'pr_number',r.pr_number,'head_sha',r.head_sha,'base_ref',r.base_ref,
        'draft',v_draft,'mergeable',r.mergeable,'checks_state',r.checks_state,
        'provider_observed_at',r.last_observed_at,'provider_updated_at',r.provider_updated_at),
      jsonb_build_object('contract','ct.pentacertifier.universal-pr-intake.v1','disposition',v_disposition,
        'reason',v_reason,'originator_system_key',v_originator,'lifecycle_disposition',r.lifecycle_disposition,
        'provider_write',false,'authority_expansion',false,'d3_human_reserved',true,
        'generic_adapter_dispatch_prohibited',true,'exact_head_bound',true,'seeded_at',clock_timestamp()),
      v_reason,1)
    on conflict(task_key) do update set
      source_snapshot=excluded.source_snapshot,risk_class=excluded.risk_class,
      evidence=integration_control.penta_certify_tasks_v3.evidence||excluded.evidence,
      last_error=excluded.last_error,updated_at=now()
    returning task_id into v_task_id;

    if not exists(select 1 from integration_control.penta_certify_receipts_v3 x
                  where x.task_id=v_task_id and x.event_type='penta.certify.pr.intake') then
      insert into integration_control.penta_certify_receipts_v3(task_id,event_type,state,evidence)
      values(v_task_id,'penta.certify.pr.intake','recorded',jsonb_build_object(
        'repo',r.repo,'pr_number',r.pr_number,'head_sha',r.head_sha,'risk_class',v_risk,
        'disposition',v_disposition,'reason',v_reason,'exact_head_bound',true,
        'provider_write',false,'authority_created',false));
      v_seeded:=v_seeded+1;
    else
      v_refreshed:=v_refreshed+1;
    end if;
  end loop;
  return jsonb_build_object('service','ct.penta.certify.pr-exact-head-intake.v1','repo',p_repo,
    'seeded',v_seeded,'refreshed',v_refreshed,'invalidated_prior_heads',v_invalidated,
    'generic_adapter_dispatch_prohibited',true,'provider_write',false,'authority_created',false,'at',now());
end
$function$;

revoke all on function integration_control.penta_certify_pr_exact_head_seed_v1(text) from public,anon,authenticated;
grant execute on function integration_control.penta_certify_pr_exact_head_seed_v1(text) to service_role;

create or replace function penta_pr.reconcile_github_pr_details_v1(
  p_repo text default 'crownthrive1/CrownThrive-OS',
  p_limit integer default 24
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_pr','chlom_runtime','vault','extensions'
as $function$
declare
  r record; v_token text; v_detail extensions.http_response; v_checks extensions.http_response;
  v_pr jsonb; v_check_json jsonb; v_check jsonb; v_observed_head text; v_base_ref text;
  v_mergeable boolean; v_mergeable_state text; v_check_state text; v_total integer; v_pending integer;
  v_bad integer; v_updated integer:=0; v_holds integer:=0; v_head_changes integer:=0;
  v_unknown_mergeability integer:=0; v_detail_sha text; v_checks_sha text;
  v_event jsonb:='{}'::jsonb; v_now timestamptz:=clock_timestamp();
begin
  if p_repo is null or p_repo !~ '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' then raise exception 'INVALID_REPOSITORY'; end if;
  p_limit:=greatest(1,least(coalesce(p_limit,24),32));
  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta-pr:detail:'||p_repo,0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','repo',p_repo,'provider_write',false,'authority_created',false,'at',clock_timestamp());
  end if;
  select decrypted_secret into v_token from vault.decrypted_secrets where name='PENTA_PM_GITHUB_TOKEN' order by created_at desc limit 1;
  if coalesce(v_token,'')='' then
    return jsonb_build_object('state','HOLD','reason','PROVIDER_CREDENTIAL_REFERENCE_UNAVAILABLE','repo',p_repo,'provider_write',false,'authority_created',false,'at',clock_timestamp());
  end if;
  for r in
    select l.id,l.pr_number,l.head_sha,l.base_ref,l.mergeable,l.checks_state,l.metadata,l.provider_updated_at
    from penta_pr.lifecycle l
    where l.repo=p_repo and l.terminal_state is null and l.head_sha ~ '^[0-9a-f]{40}$'
      and (l.mergeable is null or l.checks_state is null
        or coalesce(l.metadata->>'detail_observed_head_sha','')<>l.head_sha
        or coalesce(nullif(l.metadata->>'detail_observed_at','')::timestamptz,'epoch'::timestamptz)<now()-interval '6 hours')
    order by case when l.mergeable is null then 0 else 1 end,
             case when l.checks_state is null then 0 else 1 end,
             coalesce(nullif(l.metadata->>'detail_observed_at','')::timestamptz,'epoch'::timestamptz),l.pr_number desc
    for update skip locked limit p_limit
  loop
    v_detail:=chlom_runtime.dail_http_v1(('get'::extensions.http_method,
      ('https://api.github.com/repos/'||p_repo||'/pulls/'||r.pr_number::text)::varchar,
      array[extensions.http_header('accept','application/vnd.github+json'),extensions.http_header('authorization','Bearer '||v_token),
        extensions.http_header('x-github-api-version','2022-11-28'),extensions.http_header('user-agent','CrownThrive-PentaPR-Detail/1.0')]::extensions.http_header[],null,null)::extensions.http_request);
    if v_detail.status<>200 or v_detail.content is null then
      v_holds:=v_holds+1;
      update penta_pr.lifecycle set metadata=metadata||jsonb_build_object('detail_readback_state','hold','detail_http_status',v_detail.status,
        'detail_error_sha256',encode(extensions.digest(convert_to(coalesce(v_detail.content,''),'UTF8'),'sha256'),'hex'),'detail_observed_at',clock_timestamp()) where id=r.id;
      continue;
    end if;
    begin v_pr:=v_detail.content::jsonb; exception when others then
      v_holds:=v_holds+1; update penta_pr.lifecycle set metadata=metadata||jsonb_build_object('detail_readback_state','hold_parse','detail_observed_at',clock_timestamp()) where id=r.id; continue;
    end;
    v_observed_head:=lower(coalesce(v_pr#>>'{head,sha}',''));
    if v_observed_head !~ '^[0-9a-f]{40}$' then
      v_holds:=v_holds+1; update penta_pr.lifecycle set metadata=metadata||jsonb_build_object('detail_readback_state','hold_invalid_head','detail_observed_at',clock_timestamp()) where id=r.id; continue;
    end if;
    if v_observed_head<>r.head_sha then
      v_head_changes:=v_head_changes+1;
      insert into penta_pr.events(repo,pr_number,event_type,actor,payload)
      values(p_repo,r.pr_number,'HEAD_REFRESH_DETAIL','ct.penta.pr-detail-readback.v1',jsonb_build_object('previous_head_sha',r.head_sha,'head_sha',v_observed_head,'authority_created',false,'provider_write',false));
    end if;
    v_base_ref:=coalesce(v_pr#>>'{base,ref}',r.base_ref,'main');
    v_mergeable:=case when jsonb_typeof(v_pr->'mergeable')='boolean' then (v_pr->>'mergeable')::boolean else null end;
    v_mergeable_state:=nullif(v_pr->>'mergeable_state','');
    if v_mergeable is null then v_unknown_mergeability:=v_unknown_mergeability+1; end if;
    v_detail_sha:=encode(extensions.digest(convert_to(v_detail.content,'UTF8'),'sha256'),'hex');
    v_checks:=chlom_runtime.dail_http_v1(('get'::extensions.http_method,
      ('https://api.github.com/repos/'||p_repo||'/commits/'||v_observed_head||'/check-runs?per_page=100')::varchar,
      array[extensions.http_header('accept','application/vnd.github+json'),extensions.http_header('authorization','Bearer '||v_token),
        extensions.http_header('x-github-api-version','2022-11-28'),extensions.http_header('user-agent','CrownThrive-PentaPR-Detail/1.0')]::extensions.http_header[],null,null)::extensions.http_request);
    v_check_state:='UNKNOWN'; v_total:=0; v_pending:=0; v_bad:=0; v_checks_sha:=null;
    if v_checks.status=200 and v_checks.content is not null then
      begin
        v_check_json:=v_checks.content::jsonb; v_total:=coalesce((v_check_json->>'total_count')::integer,0);
        for v_check in select value from jsonb_array_elements(coalesce(v_check_json->'check_runs','[]'::jsonb)) loop
          if coalesce(v_check->>'status','')<>'completed' then v_pending:=v_pending+1;
          elsif coalesce(v_check->>'conclusion','') not in ('success','neutral','skipped') then v_bad:=v_bad+1; end if;
        end loop;
        v_check_state:=case when v_total=0 then 'UNKNOWN' when v_pending>0 then 'PENDING' when v_bad>0 then 'FAILURE' else 'SUCCESS' end;
        v_checks_sha:=encode(extensions.digest(convert_to(v_checks.content,'UTF8'),'sha256'),'hex');
      exception when others then v_check_state:='UNKNOWN'; end;
    else v_holds:=v_holds+1; end if;
    update penta_pr.lifecycle set head_sha=v_observed_head,base_ref=v_base_ref,mergeable=v_mergeable,checks_state=v_check_state,
      provider_updated_at=coalesce(nullif(v_pr->>'updated_at','')::timestamptz,provider_updated_at),last_observed_at=clock_timestamp(),
      metadata=metadata||jsonb_build_object('detail_readback_state','complete','detail_observed_at',clock_timestamp(),
        'detail_observed_head_sha',v_observed_head,'detail_response_sha256',v_detail_sha,'check_runs_response_sha256',v_checks_sha,
        'mergeable_state',v_mergeable_state,'check_runs_total',v_total,'check_runs_pending',v_pending,'check_runs_nonpass',v_bad,
        'raw_provider_body_stored',false,'provider_write',false,'authority_created',false) where id=r.id;
    insert into penta_pr.events(repo,pr_number,event_type,actor,payload)
    values(p_repo,r.pr_number,'PROVIDER_DETAIL_READBACK','ct.penta.pr-detail-readback.v1',jsonb_build_object('head_sha',v_observed_head,'base_ref',v_base_ref,
      'mergeable',v_mergeable,'mergeable_state',v_mergeable_state,'checks_state',v_check_state,'check_runs_total',v_total,
      'detail_response_sha256',v_detail_sha,'check_runs_response_sha256',v_checks_sha,'provider_write',false,'authority_created',false));
    v_updated:=v_updated+1;
  end loop;
  if v_updated+v_holds+v_head_changes>0 then
    v_event:=chlom_runtime.append_dail_event('penta_pr.lifecycle.github_detail_reconciliation','penta_pr_lifecycle',p_repo,
      jsonb_build_object('updated',v_updated,'provider_holds',v_holds,'head_changes',v_head_changes,'unknown_mergeability',v_unknown_mergeability,
        'batch_limit',p_limit,'raw_provider_body_stored',false,'provider_write',false,'authority_created',false,'observed_at',v_now),
      'ct.penta.pr-detail-readback.v1',null,'ct.penta.pr-detail-readback.v1','v1',p_repo||':github-detail',null,'ct.penta.pr.v1',null,'internal');
  end if;
  return jsonb_build_object('service','ct.penta.pr-detail-readback.v1','state',case when v_holds>0 then 'PASS_WITH_PROVIDER_HOLDS' else 'PASS' end,
    'repo',p_repo,'updated',v_updated,'provider_holds',v_holds,'head_changes',v_head_changes,'unknown_mergeability',v_unknown_mergeability,
    'batch_limit',p_limit,'dail_event_id',v_event->>'event_id','provider_write',false,'authority_created',false,'at',clock_timestamp());
end
$function$;

revoke all on function penta_pr.reconcile_github_pr_details_v1(text,integer) from public,anon,authenticated;
grant execute on function penta_pr.reconcile_github_pr_details_v1(text,integer) to service_role;

create or replace function penta_pr.reconcile_github_pr_details_bounded_v2(
  p_repo text default 'crownthrive1/CrownThrive-OS',
  p_limit integer default 24
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_pr','chlom_runtime','vault','extensions'
as $function$
declare
  v_token text; v_rate extensions.http_response; v_json jsonb; v_remaining integer; v_limit integer;
  v_reset bigint; v_safe_prs integer; v_result jsonb;
begin
  if p_repo is null or p_repo !~ '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' then raise exception 'INVALID_REPOSITORY'; end if;
  p_limit:=greatest(1,least(coalesce(p_limit,24),32));
  select decrypted_secret into v_token from vault.decrypted_secrets where name='PENTA_PM_GITHUB_TOKEN' order by created_at desc limit 1;
  if coalesce(v_token,'')='' then
    return jsonb_build_object('service','ct.penta.pr-detail-readback.v2','state','HOLD_PROVIDER_CREDENTIAL_REFERENCE_UNAVAILABLE','repo',p_repo,'provider_write',false,'authority_created',false,'at',clock_timestamp());
  end if;
  v_rate:=chlom_runtime.dail_http_v1(('get'::extensions.http_method,'https://api.github.com/rate_limit'::varchar,
    array[extensions.http_header('accept','application/vnd.github+json'),extensions.http_header('authorization','Bearer '||v_token),
      extensions.http_header('x-github-api-version','2022-11-28'),extensions.http_header('user-agent','CrownThrive-PentaPR-RateBudget/2.0')]::extensions.http_header[],null,null)::extensions.http_request);
  if v_rate.status<>200 or v_rate.content is null then
    return jsonb_build_object('service','ct.penta.pr-detail-readback.v2','state','HOLD_PROVIDER_RATE_PREFLIGHT_UNAVAILABLE','repo',p_repo,'http_status',v_rate.status,'provider_write',false,'authority_created',false,'at',clock_timestamp());
  end if;
  begin v_json:=v_rate.content::jsonb; exception when others then v_json:='{}'::jsonb; end;
  v_remaining:=coalesce((v_json#>>'{resources,core,remaining}')::integer,0);
  v_limit:=coalesce((v_json#>>'{resources,core,limit}')::integer,0);
  v_reset:=coalesce((v_json#>>'{resources,core,reset}')::bigint,0);
  v_safe_prs:=least(p_limit,greatest(0,(v_remaining-1)/2));
  if v_safe_prs<1 then
    return jsonb_build_object('service','ct.penta.pr-detail-readback.v2','state','HOLD_PROVIDER_RATE_BUDGET','repo',p_repo,
      'core_remaining',v_remaining,'core_limit',v_limit,'core_reset_at',case when v_reset>0 then to_timestamp(v_reset) else null end,
      'requested_prs',p_limit,'safe_prs',0,'provider_write',false,'authority_created',false,'at',clock_timestamp());
  end if;
  v_result:=penta_pr.reconcile_github_pr_details_v1(p_repo,v_safe_prs);
  return jsonb_build_object('service','ct.penta.pr-detail-readback.v2','state',coalesce(v_result->>'state','UNKNOWN'),'repo',p_repo,
    'core_remaining_before',v_remaining,'core_limit',v_limit,'core_reset_at',case when v_reset>0 then to_timestamp(v_reset) else null end,
    'requested_prs',p_limit,'safe_prs',v_safe_prs,'detail_result',v_result,'provider_write',false,'authority_created',false,'at',clock_timestamp());
end
$function$;

revoke all on function penta_pr.reconcile_github_pr_details_bounded_v2(text,integer) from public,anon,authenticated;
grant execute on function penta_pr.reconcile_github_pr_details_bounded_v2(text,integer) to service_role;

do $jobs$
declare v_jobid bigint;
begin
  select jobid into v_jobid from cron.job where jobname='ct-penta-pr-lifecycle-sync-v1' limit 1;
  if v_jobid is not null then perform cron.unschedule(v_jobid); end if;
  perform cron.schedule('ct-penta-pr-lifecycle-sync-v1','2 * * * *',$cmd$select penta_pr.reconcile_github_lifecycle_v1('crownthrive1/CrownThrive-OS');$cmd$);

  select jobid into v_jobid from cron.job where jobname='ct-penta-pr-detail-readback-v1' limit 1;
  if v_jobid is not null then perform cron.unschedule(v_jobid); end if;
  select jobid into v_jobid from cron.job where jobname='ct-penta-pr-detail-readback-v2' limit 1;
  if v_jobid is not null then perform cron.unschedule(v_jobid); end if;
  perform cron.schedule('ct-penta-pr-detail-readback-v2','3 * * * *',$cmd$select penta_pr.reconcile_github_pr_details_bounded_v2('crownthrive1/CrownThrive-OS',24);$cmd$);

  select jobid into v_jobid from cron.job where jobname='ct-penta-certify-pr-exact-head-seed-v1' limit 1;
  if v_jobid is not null then perform cron.unschedule(v_jobid); end if;
  perform cron.schedule('ct-penta-certify-pr-exact-head-seed-v1','4 * * * *',$cmd$select integration_control.penta_certify_pr_exact_head_seed_v1('crownthrive1/CrownThrive-OS');$cmd$);

  select jobid into v_jobid from cron.job where jobname='ct-penta-certify-v3' limit 1;
  if v_jobid is not null then perform cron.unschedule(v_jobid); end if;
  perform cron.schedule('ct-penta-certify-v3','5 * * * *',$cmd$select pentatime.execute_guarded_v3('penta_certify');$cmd$);
end
$jobs$;
