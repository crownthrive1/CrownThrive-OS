-- ct.penta.pr-restack-execution-adapter.v2
-- Purpose: provide a bounded, provider-write-authorized handoff from immutable
-- PentaAssignment contracts to the native PentaPR/PentaMerge GitHub provider lane.
-- This migration creates no merge/close/certification/credential/D3 authority.

create table if not exists integration_control.penta_pr_restack_requests_v2 (
  request_id uuid primary key default gen_random_uuid(),
  assignment_id uuid not null references integration_control.penta_assignment_contracts_v1(assignment_id),
  assignment_key text not null,
  source_repo text not null,
  source_pr_number bigint not null,
  predecessor_head_sha text not null,
  expected_main_sha text not null,
  state text not null default 'QUEUED' check (state in ('QUEUED','RUNNING','HOLD','SUCCEEDED','FAILED','SUPERSEDED')),
  dedupe_key text not null unique,
  successor_pr_number bigint,
  successor_head_sha text,
  successor_branch text,
  provider_http_status integer,
  hold_code text,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  completed_at timestamptz,
  check (source_repo='crownthrive1/CrownThrive-OS'),
  check (length(predecessor_head_sha)=40),
  check (length(expected_main_sha)=40),
  check (successor_head_sha is null or length(successor_head_sha)=40)
);

create index if not exists penta_pr_restack_requests_v2_state_idx
  on integration_control.penta_pr_restack_requests_v2(state, updated_at);
create index if not exists penta_pr_restack_requests_v2_assignment_idx
  on integration_control.penta_pr_restack_requests_v2(assignment_id, created_at desc);

alter table integration_control.penta_pr_restack_requests_v2 enable row level security;
revoke all on integration_control.penta_pr_restack_requests_v2 from anon, authenticated;
grant select, insert, update on integration_control.penta_pr_restack_requests_v2 to service_role;

drop function if exists integration_control.penta_assignment_pr_restack_request_v2(uuid,text);
create function integration_control.penta_assignment_pr_restack_request_v2(
  p_assignment_id uuid,
  p_expected_main_sha text
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,chlom_runtime
as $function$
declare
  a integration_control.penta_assignment_contracts_v1%rowtype;
  r integration_control.penta_pr_restack_requests_v2%rowtype;
  v_main text:=lower(btrim(coalesce(p_expected_main_sha,'')));
  v_dedupe text;
  v_event jsonb;
begin
  if session_user not in ('postgres','supabase_admin')
     and coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'')<>'service_role'
  then raise exception 'service_role_required'; end if;

  if v_main !~ '^[0-9a-f]{40}$' then raise exception 'expected_main_sha_invalid'; end if;

  select * into a
  from integration_control.penta_assignment_contracts_v1
  where assignment_id=p_assignment_id
  for update;
  if not found then raise exception 'assignment_not_found'; end if;

  if a.task_kind<>'PR_RESTACK_CURRENT_MAIN' then raise exception 'assignment_task_kind_forbidden'; end if;
  if not a.provider_write_allowed then raise exception 'assignment_provider_write_forbidden'; end if;
  if a.risk_class not in ('D0','D1','D2') or a.authority_ceiling not in ('D0','D1','D2') then
    raise exception 'assignment_authority_ceiling_forbidden';
  end if;
  if a.source_repo is distinct from 'crownthrive1/CrownThrive-OS' then raise exception 'assignment_repo_forbidden'; end if;
  if a.source_pr_number is null or a.exact_head_sha is null or a.exact_head_sha !~ '^[0-9a-f]{40}$' then
    raise exception 'assignment_exact_source_required';
  end if;

  -- Never execute an assignment against a different main than the immutable subject
  -- it explicitly names. A new current-main assignment must be created instead.
  if coalesce(a.metadata->>'current_main_sha','')<>v_main then
    return jsonb_build_object(
      'state','HOLD_CURRENT_MAIN_ASSIGNMENT_DRIFT',
      'assignment_id',a.assignment_id,
      'assignment_main_sha',a.metadata->>'current_main_sha',
      'provider_main_sha',v_main,
      'authority_created',false
    );
  end if;

  v_dedupe:='ct:penta-pr-restack:'||a.assignment_id::text||':main:'||v_main;
  insert into integration_control.penta_pr_restack_requests_v2(
    assignment_id,assignment_key,source_repo,source_pr_number,predecessor_head_sha,
    expected_main_sha,state,dedupe_key,evidence
  ) values (
    a.assignment_id,a.assignment_key,a.source_repo,a.source_pr_number,a.exact_head_sha,
    v_main,'QUEUED',v_dedupe,
    jsonb_build_object(
      'contract','ct.penta.pr-terminalization-policy.v2',
      'assignment_contract','ct.penta.assignment-fulfillment.v1',
      'draft_successor_required',true,
      'predecessor_branch_delete_forbidden',true,
      'predecessor_close_performed',false,
      'merge_performed',false,
      'self_certification',false,
      'D3_human_reserved',true,
      'authority_created',false
    )
  ) on conflict(dedupe_key) do update set
    state=case when integration_control.penta_pr_restack_requests_v2.state='SUCCEEDED' then 'SUCCEEDED' else 'QUEUED' end,
    hold_code=null,
    updated_at=clock_timestamp(),
    evidence=integration_control.penta_pr_restack_requests_v2.evidence||excluded.evidence
  returning * into r;

  v_event:=chlom_runtime.append_dail_event(
    'penta.pr.restack.requested.v2','penta_pr_restack_request',r.request_id::text,
    jsonb_build_object(
      'assignment_id',a.assignment_id,'assignment_key',a.assignment_key,
      'source_repo',a.source_repo,'source_pr_number',a.source_pr_number,
      'predecessor_head_sha',a.exact_head_sha,'expected_main_sha',v_main,
      'request_id',r.request_id,'dedupe_key',r.dedupe_key,
      'merge_authority_created',false,'close_authority_created',false,
      'certification_authority_created',false,'D3_human_reserved',true,
      'authority_created',false,'requested_at',clock_timestamp()
    ),
    'PentaPR/PentaMerge/PentaPM',null,'PentaPR','2.0.0',
    'ctcorr:penta-pr-restack:'||r.request_id::text,null,
    'ct.penta.pr-terminalization-policy.v2',null,'internal'
  );

  return jsonb_build_object(
    'state',r.state,'request_id',r.request_id,'assignment_id',a.assignment_id,
    'expected_main_sha',v_main,'dail',v_event,'authority_created',false
  );
end
$function$;

drop function if exists public.penta_pr_restack_request_get_v2(uuid);
create function public.penta_pr_restack_request_get_v2(p_request_id uuid)
returns jsonb
language sql
stable
security definer
set search_path=pg_catalog,integration_control
as $function$
  select case when r.request_id is null then null else jsonb_build_object(
    'request_id',r.request_id,'assignment_id',r.assignment_id,'assignment_key',r.assignment_key,
    'source_repo',r.source_repo,'source_pr_number',r.source_pr_number,
    'predecessor_head_sha',r.predecessor_head_sha,'expected_main_sha',r.expected_main_sha,
    'state',r.state,'dedupe_key',r.dedupe_key,
    'successor_pr_number',r.successor_pr_number,'successor_head_sha',r.successor_head_sha,
    'successor_branch',r.successor_branch,'evidence',r.evidence,
    'authority_created',false
  ) end
  from integration_control.penta_pr_restack_requests_v2 r
  where r.request_id=p_request_id
$function$;
revoke all on function public.penta_pr_restack_request_get_v2(uuid) from public,anon,authenticated;
grant execute on function public.penta_pr_restack_request_get_v2(uuid) to service_role;

drop function if exists public.penta_pr_restack_record_provider_result_v2(uuid,text,integer,text,bigint,text,text,jsonb);
create function public.penta_pr_restack_record_provider_result_v2(
  p_request_id uuid,
  p_state text,
  p_provider_http_status integer default null,
  p_hold_code text default null,
  p_successor_pr_number bigint default null,
  p_successor_head_sha text default null,
  p_successor_branch text default null,
  p_evidence jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,chlom_runtime
as $function$
declare
  r integration_control.penta_pr_restack_requests_v2%rowtype;
  v_state text:=upper(btrim(coalesce(p_state,'')));
  v_event jsonb;
begin
  if session_user not in ('postgres','supabase_admin')
     and coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'')<>'service_role'
  then raise exception 'service_role_required'; end if;
  if v_state not in ('RUNNING','HOLD','SUCCEEDED','FAILED') then raise exception 'provider_result_state_invalid'; end if;
  if p_successor_head_sha is not null and p_successor_head_sha !~ '^[0-9a-f]{40}$' then raise exception 'successor_head_sha_invalid'; end if;
  if v_state='SUCCEEDED' and (p_successor_pr_number is null or p_successor_head_sha is null or p_successor_branch is null) then
    raise exception 'successor_readback_required';
  end if;

  update integration_control.penta_pr_restack_requests_v2
  set state=v_state,
      provider_http_status=p_provider_http_status,
      hold_code=p_hold_code,
      successor_pr_number=coalesce(p_successor_pr_number,successor_pr_number),
      successor_head_sha=coalesce(p_successor_head_sha,successor_head_sha),
      successor_branch=coalesce(p_successor_branch,successor_branch),
      evidence=evidence||coalesce(p_evidence,'{}'::jsonb)||jsonb_build_object(
        'merge_performed',false,'predecessor_close_performed',false,
        'certification_claimed',false,'authority_created',false,'provider_recorded_at',clock_timestamp()),
      completed_at=case when v_state in ('SUCCEEDED','FAILED') then clock_timestamp() else completed_at end,
      updated_at=clock_timestamp()
  where request_id=p_request_id
  returning * into r;
  if not found then raise exception 'restack_request_not_found'; end if;

  v_event:=chlom_runtime.append_dail_event(
    'penta.pr.restack.provider_result.v2','penta_pr_restack_request',r.request_id::text,
    jsonb_build_object(
      'request_id',r.request_id,'assignment_id',r.assignment_id,'state',r.state,
      'provider_http_status',r.provider_http_status,'hold_code',r.hold_code,
      'successor_pr_number',r.successor_pr_number,'successor_head_sha',r.successor_head_sha,
      'successor_branch',r.successor_branch,
      'predecessor_close_performed',false,'merge_performed',false,
      'certification_claimed',false,'D3_human_reserved',true,'authority_created',false,
      'observed_at',clock_timestamp()
    ),
    'PentaPR/PentaMerge/PentaPM',null,'PentaPR','2.0.0',
    'ctcorr:penta-pr-restack:'||r.request_id::text,null,
    'ct.penta.pr-terminalization-policy.v2',null,'internal'
  );

  return jsonb_build_object(
    'request_id',r.request_id,'state',r.state,'successor_pr_number',r.successor_pr_number,
    'successor_head_sha',r.successor_head_sha,'successor_branch',r.successor_branch,
    'dail',v_event,'authority_created',false
  );
end
$function$;
revoke all on function public.penta_pr_restack_record_provider_result_v2(uuid,text,integer,text,bigint,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.penta_pr_restack_record_provider_result_v2(uuid,text,integer,text,bigint,text,text,jsonb) to service_role;

drop function if exists integration_control.penta_assignment_supersede_stale_restack_v2(uuid,uuid,text);
create function integration_control.penta_assignment_supersede_stale_restack_v2(
  p_predecessor_assignment_id uuid,
  p_successor_assignment_id uuid,
  p_reason text
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,chlom_runtime
as $function$
declare
  a integration_control.penta_assignment_contracts_v1%rowtype;
  s integration_control.penta_assignment_contracts_v1%rowtype;
  v_event jsonb;
begin
  if session_user not in ('postgres','supabase_admin')
     and coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'')<>'service_role'
  then raise exception 'service_role_required'; end if;
  if p_predecessor_assignment_id=p_successor_assignment_id then raise exception 'successor_must_differ'; end if;

  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_predecessor_assignment_id for update;
  select * into s from integration_control.penta_assignment_contracts_v1 where assignment_id=p_successor_assignment_id;
  if a.assignment_id is null or s.assignment_id is null then raise exception 'assignment_not_found'; end if;
  if a.task_kind<>'PR_RESTACK_CURRENT_MAIN' or s.task_kind<>'PR_RESTACK_CURRENT_MAIN' then raise exception 'restack_assignment_required'; end if;
  if a.source_repo is distinct from s.source_repo or a.source_pr_number is distinct from s.source_pr_number or a.exact_head_sha is distinct from s.exact_head_sha then
    raise exception 'successor_lineage_mismatch';
  end if;

  update integration_control.penta_assignment_contracts_v1
  set state='SUPERSEDED',metadata=metadata||jsonb_build_object(
    'superseded_by_assignment_id',s.assignment_id,'superseded_reason',left(coalesce(p_reason,'current_main_drift'),1000),
    'history_preserved',true,'authority_created',false),updated_at=clock_timestamp()
  where assignment_id=a.assignment_id and state not in ('COMPLETED','RETIRED');

  v_event:=chlom_runtime.append_dail_event(
    'penta.assignment.restack.superseded.v2','penta_assignment',a.assignment_id::text,
    jsonb_build_object(
      'predecessor_assignment_id',a.assignment_id,'successor_assignment_id',s.assignment_id,
      'source_repo',a.source_repo,'source_pr_number',a.source_pr_number,
      'exact_head_sha',a.exact_head_sha,'reason',left(coalesce(p_reason,'current_main_drift'),1000),
      'history_preserved',true,'provider_write_performed',false,'authority_created',false,
      'observed_at',clock_timestamp()),
    'PentaPR/PentaPM',null,'PentaPR','2.0.0',
    'ctcorr:penta-assignment:'||a.assignment_id::text,null,
    'ct.penta.assignment-fulfillment.v1',null,'internal'
  );

  return jsonb_build_object('state','SUPERSEDED','predecessor_assignment_id',a.assignment_id,
    'successor_assignment_id',s.assignment_id,'dail',v_event,'authority_created',false);
end
$function$;

comment on table integration_control.penta_pr_restack_requests_v2 is
  'Fail-closed current-main PR restack requests. Success creates a draft successor only; merge, predecessor close, review and certification remain separate predicates.';
