-- CrownThrive COS V1 sprint certifier critical-path repair.
-- PentaOFAC current_truth_v4 records a provider-read receipt and appends DAIL.
-- Certification must evaluate current truth without generating provider-evidence
-- writes before its final bounded certification append. This helper preserves
-- the decision semantics as a pure read and the certifier consumes it.

create or replace function integration_control.pentaofac_current_truth_read_v1()
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','integration_control','public','extensions'
as $fn$
declare
  v_status jsonb;
  v_source_count integer:=0;
  v_source_pass integer:=0;
  v_refresh_minutes integer:=15;
  v_last_success timestamptz;
  v_state text;
  v_pass boolean:=false;
  v_sha text;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  v_status:=public.penta_ofac_status_v1();
  v_state:=coalesce(v_status->>'state','UNKNOWN');
  v_refresh_minutes:=greatest(1,coalesce((v_status->>'refresh_interval_minutes')::integer,15));
  begin v_last_success:=nullif(v_status->>'last_success_at','')::timestamptz;
  exception when others then v_last_success:=null; end;
  if jsonb_typeof(v_status->'sources')='array' then
    v_source_count:=jsonb_array_length(v_status->'sources');
    select count(*) into v_source_pass
    from jsonb_array_elements(v_status->'sources') s
    where coalesce((s->>'enabled')::boolean,false)
      and coalesce((s#>>'{latest,http_status}')::integer,0)=200
      and coalesce((s#>>'{latest,valid_xml}')::boolean,false)
      and coalesce((s#>>'{latest,namespace_valid}')::boolean,false)
      and coalesce(s#>>'{latest,sha256}','')~'^[0-9a-f]{64}$'
      and coalesce((s#>>'{latest,bytes}')::bigint,0)>0
      and nullif(s#>>'{latest,fetched_at}','')::timestamptz
          >=clock_timestamp()-make_interval(mins=>greatest(45,v_refresh_minutes*3));
  end if;
  v_pass:=v_state='ACTIVE'
    and v_source_count>0
    and v_source_pass=v_source_count
    and v_last_success is not null
    and v_last_success>=clock_timestamp()-make_interval(mins=>greatest(45,v_refresh_minutes*3));
  v_sha:=encode(extensions.digest(convert_to(v_status::text,'UTF8'),'sha256'),'hex');
  return jsonb_build_object('ok',v_pass,'decision',case when v_pass then 'pass' else 'hold' end,
    'service_state',v_state,'source_count',v_source_count,'source_pass_count',v_source_pass,
    'last_success_at',v_last_success,'response_sha256',v_sha,
    'truth_basis','direct_internal_provider_status_read_only',
    'provider_write',false,'evidence_write',false,'dail_append',false);
end
$fn$;

revoke all on function integration_control.pentaofac_current_truth_read_v1() from public,anon,authenticated;
grant execute on function integration_control.pentaofac_current_truth_read_v1() to service_role;

do $repair$
declare
  v_definition text;
  v_pre_sha text;
  v_post_sha text;
  v_old constant text := $$begin v_ofac:=integration_control.pentaofac_current_truth_v4();$$;
  v_new constant text := $$begin v_ofac:=integration_control.pentaofac_current_truth_read_v1();$$;
begin
  select pg_get_functiondef('public.cos_v1_certify_v2(text,text,boolean)'::regprocedure) into v_definition;
  v_pre_sha:=encode(extensions.digest(v_definition,'sha256'),'hex');
  if v_pre_sha <> '62d0b00f940a1403dda5c01cc51dbbfcb381b1040ab9245d4120c8cb3457b5f6' then
    raise exception 'cos_v1_certify_v2 predecessor drift: expected %, found %',
      '62d0b00f940a1403dda5c01cc51dbbfcb381b1040ab9245d4120c8cb3457b5f6',v_pre_sha;
  end if;
  if position(v_old in v_definition)=0 then raise exception 'expected PentaOFAC current-truth call absent'; end if;
  v_definition:=replace(v_definition,v_old,v_new);
  execute v_definition;
  select encode(extensions.digest(pg_get_functiondef('public.cos_v1_certify_v2(text,text,boolean)'::regprocedure),'sha256'),'hex') into v_post_sha;
  if v_post_sha=v_pre_sha then raise exception 'PentaOFAC read-only certifier repair made no change'; end if;
end
$repair$;

comment on function integration_control.pentaofac_current_truth_read_v1() is
  'Read-only PentaOFAC current truth for certification/status consumers. No receipt write and no DAIL append.';
comment on function public.cos_v1_certify_v2(text,text,boolean) is
  'COS V1 certification v2. Evaluates materialized truth without synchronous convergence or provider-evidence writes; final certification DAIL append remains bounded.';
