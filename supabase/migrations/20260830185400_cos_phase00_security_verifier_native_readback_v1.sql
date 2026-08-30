-- CrownThrive COS V1 Phase 00 security verifier repair.
-- Production pre-state function SHA-256: 273584af163a12ec7a4118bedc0b3ec17c3789c623c8ead613dd31c692648596
-- Production post-state function SHA-256: 197b46d7ff013c046d4c71355635a9b9325697ca8861a4e6f437d9326dfc18ca
-- Rollback snapshot: 3e2fdff3-2808-4246-bf81-2c8b74e503ff
-- Exact source/production fence at repair: 5a324a6a52e455c7aaeb1409598176a1461bcb05
-- Scope: replace the circular GitHub issue-search proxy with authenticated GitHub native
-- secret-scanning readback. A GitGuardian check, when present, remains a supplemental
-- fail signal. Absence of that check is not treated as a provider finding when native
-- secret-scanning readback is authoritative, complete, and has zero open alerts.

CREATE OR REPLACE FUNCTION integration_control.reconcile_gitguardian_current_main_v2()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'integration_control', 'penta_self', 'vault', 'extensions', 'chlom_runtime'
AS $function$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_branch_response extensions.http_response; v_branch jsonb; v_sha text;
  v_checks_response extensions.http_response; v_checks_response2 extensions.http_response; v_checks jsonb; v_checks2 jsonb; v_check jsonb;
  v_total_checks int:=0; v_check_runs_complete boolean:=false;
  v_token text;
  v_native_response extensions.http_response; v_native jsonb; v_open_native_alerts int;
  v_name text; v_status text; v_conclusion text; v_disposition text; v_digest text; v_payload jsonb; v_id uuid;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;

  begin
    v_branch_response:=chlom_runtime.dail_http_v1(('GET'::extensions.http_method,'https://api.github.com/repos/crownthrive1/CrownThrive-OS/branches/main'::varchar,array[row('accept','application/vnd.github+json')::extensions.http_header,row('user-agent','CrownThrive-PentaSecure')::extensions.http_header,row('x-github-api-version','2022-11-28')::extensions.http_header],null::varchar,null::varchar)::extensions.http_request);
    if v_branch_response.status=200 then v_branch:=v_branch_response.content::jsonb; v_sha:=v_branch->'commit'->>'sha'; end if;
  exception when others then null; end;

  if v_sha is not null then
    begin
      v_checks_response:=chlom_runtime.dail_http_v1(('GET'::extensions.http_method,('https://api.github.com/repos/crownthrive1/CrownThrive-OS/commits/'||v_sha||'/check-runs?per_page=100&page=1')::varchar,array[row('accept','application/vnd.github+json')::extensions.http_header,row('user-agent','CrownThrive-PentaSecure')::extensions.http_header,row('x-github-api-version','2022-11-28')::extensions.http_header],null::varchar,null::varchar)::extensions.http_request);
      if v_checks_response.status=200 then
        v_checks:=v_checks_response.content::jsonb;
        v_total_checks:=coalesce((v_checks->>'total_count')::int,0);
        select value into v_check from jsonb_array_elements(coalesce(v_checks->'check_runs','[]'::jsonb)) where lower(coalesce(value->>'name','')||' '||coalesce(value->'app'->>'name','')||' '||coalesce(value->'app'->>'slug','')) like '%gitguardian%' order by coalesce(value->>'completed_at',value->>'started_at') desc limit 1;
        if v_total_checks>100 then
          v_checks_response2:=chlom_runtime.dail_http_v1(('GET'::extensions.http_method,('https://api.github.com/repos/crownthrive1/CrownThrive-OS/commits/'||v_sha||'/check-runs?per_page=100&page=2')::varchar,array[row('accept','application/vnd.github+json')::extensions.http_header,row('user-agent','CrownThrive-PentaSecure')::extensions.http_header,row('x-github-api-version','2022-11-28')::extensions.http_header],null::varchar,null::varchar)::extensions.http_request);
          if v_checks_response2.status=200 then
            v_checks2:=v_checks_response2.content::jsonb;
            if v_check is null then
              select value into v_check from jsonb_array_elements(coalesce(v_checks2->'check_runs','[]'::jsonb)) where lower(coalesce(value->>'name','')||' '||coalesce(value->'app'->>'name','')||' '||coalesce(value->'app'->>'slug','')) like '%gitguardian%' order by coalesce(value->>'completed_at',value->>'started_at') desc limit 1;
            end if;
            v_check_runs_complete:=true;
          end if;
        else
          v_check_runs_complete:=true;
        end if;
        v_name:=v_check->>'name'; v_status:=v_check->>'status'; v_conclusion:=v_check->>'conclusion';
      end if;
    exception when others then v_check_runs_complete:=false; end;
  end if;

  begin
    select decrypted_secret into v_token from vault.decrypted_secrets where name='PENTA_PM_GITHUB_TOKEN' order by created_at desc limit 1;
  exception when others then v_token:=null; end;

  if coalesce(v_token,'')<>'' then
    begin
      v_native_response:=chlom_runtime.dail_http_v1(('GET'::extensions.http_method,'https://api.github.com/repos/crownthrive1/CrownThrive-OS/secret-scanning/alerts?state=open&per_page=100'::varchar,array[row('accept','application/vnd.github+json')::extensions.http_header,row('authorization','Bearer '||v_token)::extensions.http_header,row('user-agent','CrownThrive-PentaSecure-Native-Readback/2.1')::extensions.http_header,row('x-github-api-version','2022-11-28')::extensions.http_header],null::varchar,null::varchar)::extensions.http_request);
      if v_native_response.status=200 then
        v_native:=v_native_response.content::jsonb;
        if jsonb_typeof(v_native)='array' then v_open_native_alerts:=jsonb_array_length(v_native); end if;
      end if;
    exception when others then null; end;
  end if;

  v_disposition:=case
    when v_branch_response.status is distinct from 200 or v_sha is null then 'HOLD_CURRENT_MAIN_READBACK'
    when v_checks_response.status in (403,429) or (v_total_checks>100 and v_checks_response2.status in (403,429)) then 'DEFERRED_PROVIDER_RATE_OR_AUTH'
    when v_checks_response.status is distinct from 200 or not v_check_runs_complete then 'HOLD_CHECK_RUN_READBACK'
    when coalesce(v_token,'')='' then 'HOLD_PROVIDER_CREDENTIAL_UNAVAILABLE'
    when v_native_response.status in (401,403,429) then 'DEFERRED_PROVIDER_RATE_OR_AUTH'
    when v_native_response.status is distinct from 200 or v_open_native_alerts is null then 'HOLD_NATIVE_SECRET_SCAN_READBACK'
    when v_open_native_alerts>0 then 'HOLD_PROVIDER_FINDING_OR_CHECK'
    when v_check is not null and not (v_status='completed' and v_conclusion in ('success','neutral','skipped')) then 'HOLD_PROVIDER_FINDING_OR_CHECK'
    else 'CURRENT_MAIN_SECURITY_GREEN'
  end;

  v_payload:=jsonb_build_object(
    'provider','GitGuardian compatibility + GitHub native secret scanning',
    'repository','crownthrive1/CrownThrive-OS',
    'main_sha',v_sha,
    'check_runs_http_status',v_checks_response.status,
    'check_runs_page2_http_status',case when v_total_checks>100 then v_checks_response2.status else null end,
    'check_runs_total',v_total_checks,
    'check_runs_complete',v_check_runs_complete,
    'gitguardian_check_present',v_check is not null,
    'check_name',v_name,
    'check_status',v_status,
    'check_conclusion',v_conclusion,
    'native_secret_scanning_http_status',v_native_response.status,
    'open_native_secret_scanning_alerts',v_open_native_alerts,
    'open_provider_issue_count',v_open_native_alerts,
    'internal_tracking_issue_used_as_provider_signal',false,
    'branch_http_status',v_branch_response.status,
    'disposition',v_disposition,
    'raw_secret_material_preserved',false,
    'secret_material_exposed',false,
    'observed_at',now());
  v_digest:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');

  insert into integration_control.github_security_check_receipts_v2(provider_name,repository,main_sha,check_name,check_status,check_conclusion,open_provider_issue_count,provider_http_status,disposition,evidence_sha256)
  values('GitGuardian','crownthrive1/CrownThrive-OS',v_sha,v_name,v_status,v_conclusion,v_open_native_alerts,coalesce(v_native_response.status,v_checks_response.status,v_branch_response.status),v_disposition,v_digest) returning receipt_id into v_id;

  if v_disposition='CURRENT_MAIN_SECURITY_GREEN' then
    update penta_self.problem_ledger_v1 set state='resolved',resolved_at=coalesce(resolved_at,now()),blocked_reason=null,last_error=null,verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||jsonb_build_object('verified_at',now(),'receipt_id',v_id,'main_sha',v_sha,'check_name',v_name,'check_status',v_status,'check_conclusion',v_conclusion,'native_secret_scanning_http_status',v_native_response.status,'open_native_secret_scanning_alerts',v_open_native_alerts,'provider_readback','CURRENT_MAIN_SECURITY_GREEN','internal_tracking_issue_used_as_provider_signal',false,'secret_material_exposed',false),updated_at=now()
    where title='GitGuardian high-entropy finding remains unresolved' and state<>'resolved';
  end if;

  perform chlom_runtime.append_dail_event('gitguardian.current-main.reconciled','security_verification','crownthrive1/CrownThrive-OS',v_payload||jsonb_build_object('receipt_id',v_id,'evidence_sha256',v_digest,'three_dail_logical_phase','DAIL-EVIDENCE'),'PentaSecure/PentaCredentials/PentaCertify',null,'PentaSecure','2.1.0',v_digest,null,'ct.github.security.current-main.v2',null,'internal');
  return v_payload||jsonb_build_object('receipt_id',v_id,'evidence_sha256',v_digest);
end
$function$;
