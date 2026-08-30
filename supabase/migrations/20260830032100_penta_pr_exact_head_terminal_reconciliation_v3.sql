-- CrownThrive PentaPR terminal reconciliation v3
-- Production-first convergence of PentaPR/PentaPM/PentaCloser/PentaMerge.
-- Historical Vergence remains append-only but only exact-current-head evidence is authoritative.

create table if not exists penta_pr.terminal_reconciliation_v3 (
  decision_id uuid primary key default gen_random_uuid(),
  repo text not null,
  pr_number bigint not null,
  head_sha text not null,
  classification text not null,
  terminal_action text not null check (terminal_action in ('CLOSE','MERGE','NONE')),
  decision_state text not null default 'PLANNED' check (decision_state in ('PLANNED','DISPATCHED','SUCCEEDED','FAILED','DEFERRED')),
  reason text,
  evidence jsonb not null default '{}'::jsonb,
  provider_http_status integer,
  provider_state text,
  provider_merged boolean,
  provider_merge_commit_sha text,
  provider_readback jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  terminal_at timestamptz,
  unique(repo,pr_number,head_sha,terminal_action)
);

create index if not exists terminal_reconciliation_v3_state_idx
  on penta_pr.terminal_reconciliation_v3(decision_state,terminal_action,updated_at);

create or replace view penta_runtime.current_vergence_repairs_v3 as
select v.*
from penta_runtime.vergence_repairs_v1 v
join penta_pr.lifecycle l
  on l.repo=v.repository_full_name
 and l.pr_number=v.pr_number
 and l.head_sha=v.head_sha
where l.terminal_state is null;

create or replace view penta_pr.current_zero_delta_candidates_v3 as
select l.repo,l.pr_number,l.head_sha,q.execution_id,q.finding_id,q.updated_at as verified_at,q.receipt
from penta_pr.lifecycle l
join lateral (
  select q.*
  from penta_runtime.remediation_execution_queue_v1 q
  where q.pr_number=l.pr_number
    and q.state='verified'
    and q.head_sha=l.head_sha
    and coalesce((q.receipt->>'no_code_delta')::boolean,false)=true
  order by q.updated_at desc limit 1
) q on true
where l.terminal_state is null;

create or replace function penta_pr.record_provider_truth_v3(
  p_repo text,p_pr_number bigint,p_head_sha text,p_state text,p_merged boolean,
  p_merge_commit_sha text default null,p_http_status integer default null,p_readback jsonb default '{}'::jsonb
) returns jsonb
language plpgsql security definer
set search_path='pg_catalog','penta_pr','integration_control','extensions'
as $$
declare v_sha text;
begin
  v_sha:=encode(extensions.digest(convert_to(coalesce(p_readback,'{}'::jsonb)::text,'UTF8'),'sha256'),'hex');
  insert into integration_control.github_pr_truth_receipts_v2(repo_full_name,pr_number,state,merged,head_sha,merge_commit_sha,http_status,evidence_sha256,observed_at)
  values(p_repo,p_pr_number,p_state,coalesce(p_merged,false),p_head_sha,p_merge_commit_sha,p_http_status,v_sha,now());
  update penta_pr.lifecycle set
    head_sha=p_head_sha,last_observed_at=now(),provider_updated_at=now(),
    terminal_state=case when lower(p_state)='closed' then case when p_merged then 'MERGED' else 'CLOSED' end else terminal_state end,
    terminal_at=case when lower(p_state)='closed' then coalesce(terminal_at,now()) else terminal_at end,
    metadata=metadata||jsonb_build_object('last_provider_truth_sha256',v_sha,'last_provider_truth_at',now())
  where repo=p_repo and pr_number=p_pr_number;
  insert into penta_pr.events(repo,pr_number,event_type,actor,payload)
  values(p_repo,p_pr_number,'PROVIDER_TRUTH','PentaPR/PentaCloser',jsonb_build_object('head_sha',p_head_sha,'state',p_state,'merged',coalesce(p_merged,false),'merge_commit_sha',p_merge_commit_sha,'http_status',p_http_status,'evidence_sha256',v_sha));
  return jsonb_build_object('state','RECORDED','repo',p_repo,'pr_number',p_pr_number,'head_sha',p_head_sha,'provider_state',p_state,'merged',coalesce(p_merged,false),'evidence_sha256',v_sha);
end $$;

create or replace function penta_pr.invoke_terminal_provider_v3(p_op text,p_payload jsonb default '{}'::jsonb)
returns bigint language plpgsql security definer
set search_path='penta_pr','vault','net','public'
as $$
declare v_jwt text; v_id bigint;
begin
  select decrypted_secret into v_jwt from vault.decrypted_secrets where name='PENTA_PM_EDGE_INVOKE_JWT' limit 1;
  if v_jwt is null then raise exception 'penta_pr_edge_invoke_jwt_missing'; end if;
  select net.http_post(
    url := 'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-pr-terminal-provider',
    body := coalesce(p_payload,'{}'::jsonb)||jsonb_build_object('op',p_op),
    headers := jsonb_build_object('Authorization','Bearer '||v_jwt,'Content-Type','application/json'),
    timeout_milliseconds := 60000
  ) into v_id;
  return v_id;
end $$;

create or replace function public.penta_pr_repo_allowed_v3(p_repo text)
returns boolean language sql stable security definer
set search_path='pg_catalog','integration_control'
as $$
  select exists(select 1 from integration_control.cos_repository_census_v1
    where repository_full_name=p_repo and owner_login='crownthrive1'
      and archived=false and operationally_enabled=true and lifecycle_state='active');
$$;

create or replace function public.penta_pr_latest_zero_delta_v3(p_repo text,p_pr_number bigint)
returns jsonb language sql stable security definer
set search_path='pg_catalog','penta_runtime'
as $$
 select coalesce((select jsonb_build_object('eligible',true,'execution_id',q.execution_id,'finding_id',q.finding_id,'head_sha',q.head_sha,'verified_at',q.updated_at,'receipt',q.receipt)
   from penta_runtime.remediation_execution_queue_v1 q
   where p_repo='crownthrive1/CrownThrive-OS' and q.pr_number=p_pr_number and q.state='verified'
     and coalesce((q.receipt->>'no_code_delta')::boolean,false)=true
   order by q.updated_at desc limit 1),jsonb_build_object('eligible',false));
$$;

create or replace function public.penta_pr_record_terminal_decision_v3(
 p_repo text,p_pr_number bigint,p_head_sha text,p_classification text,p_action text,p_state text,p_reason text,p_evidence jsonb default '{}'::jsonb,
 p_http_status integer default null,p_provider_state text default null,p_merged boolean default false,p_merge_commit_sha text default null,p_readback jsonb default '{}'::jsonb
) returns jsonb language plpgsql security definer
set search_path='pg_catalog','penta_pr'
as $$
declare v_id uuid;
begin
 insert into penta_pr.terminal_reconciliation_v3(repo,pr_number,head_sha,classification,terminal_action,decision_state,reason,evidence,provider_http_status,provider_state,provider_merged,provider_merge_commit_sha,provider_readback,terminal_at,updated_at)
 values(p_repo,p_pr_number,p_head_sha,p_classification,p_action,p_state,p_reason,coalesce(p_evidence,'{}'::jsonb),p_http_status,p_provider_state,coalesce(p_merged,false),p_merge_commit_sha,coalesce(p_readback,'{}'::jsonb),case when p_state='SUCCEEDED' then now() end,now())
 on conflict(repo,pr_number,head_sha,terminal_action) do update set
  classification=excluded.classification,decision_state=excluded.decision_state,reason=excluded.reason,evidence=penta_pr.terminal_reconciliation_v3.evidence||excluded.evidence,
  provider_http_status=excluded.provider_http_status,provider_state=excluded.provider_state,provider_merged=excluded.provider_merged,
  provider_merge_commit_sha=excluded.provider_merge_commit_sha,provider_readback=excluded.provider_readback,
  terminal_at=case when excluded.decision_state='SUCCEEDED' then coalesce(penta_pr.terminal_reconciliation_v3.terminal_at,now()) else penta_pr.terminal_reconciliation_v3.terminal_at end,updated_at=now()
 returning decision_id into v_id;
 return jsonb_build_object('decision_id',v_id,'state',p_state,'repo',p_repo,'pr_number',p_pr_number,'head_sha',p_head_sha,'action',p_action);
end $$;

create or replace function public.penta_pr_record_provider_truth_v3(
 p_repo text,p_pr_number bigint,p_head_sha text,p_state text,p_merged boolean,p_merge_commit_sha text default null,p_http_status integer default null,p_readback jsonb default '{}'::jsonb
) returns jsonb language sql security definer set search_path='pg_catalog','penta_pr'
as $$ select penta_pr.record_provider_truth_v3(p_repo,p_pr_number,p_head_sha,p_state,p_merged,p_merge_commit_sha,p_http_status,p_readback); $$;

create or replace function pentatime.executor_penta_pr_terminal_v3()
returns jsonb language plpgsql security definer set search_path='pg_catalog','penta_pr'
as $$
declare v_id bigint;
begin
  v_id:=penta_pr.invoke_terminal_provider_v3('reconcile',jsonb_build_object('limit',100));
  return jsonb_build_object('state','DISPATCHED','request_id',v_id,'service','ct.penta-pr-terminal-reconciliation.v3','authority_created',false);
end $$;

insert into pentatime.operation_registry_v2(operation_key,domain_key,owner_penta,enabled,base_backoff_seconds,max_backoff_seconds,metadata)
values('penta_pr_terminal_reconcile','ct:production-governance-write-lane','PentaPR/PentaPM/PentaCloser/PentaMerge',true,30,900,
 jsonb_build_object('contract','ct.penta-pr-terminal-reconciliation.v3','exact_head_required',true,'zero_delta_closes_without_merge',true,'historical_vergence_non_authoritative',true,'D3_human_reserved',true))
on conflict(operation_key) do update set domain_key=excluded.domain_key,owner_penta=excluded.owner_penta,enabled=true,metadata=pentatime.operation_registry_v2.metadata||excluded.metadata,updated_at=now();

insert into pentatime.operation_executors_v3(operation_key,executor_regprocedure,authority_ceiling,enabled,metadata)
values('penta_pr_terminal_reconcile','pentatime.executor_penta_pr_terminal_v3()'::regprocedure,'D2',true,jsonb_build_object('provider','penta-pr-terminal-provider','exact_head_fenced',true,'no_force_merge',true))
on conflict(operation_key) do update set executor_regprocedure=excluded.executor_regprocedure,authority_ceiling='D2',enabled=true,metadata=pentatime.operation_executors_v3.metadata||excluded.metadata,updated_at=now();

-- PentaCrons/PentaTime performs the durable assignment after provider deployment:
-- select pentatime.pentacrons_assign_operation_v1('penta-pr-terminal-reconcile-v3','*/2 * * * *','penta_pr_terminal_reconcile','D2','ct.penta-pr-terminal-reconciliation.v3');

revoke all on function penta_pr.record_provider_truth_v3(text,bigint,text,text,boolean,text,integer,jsonb) from public,anon,authenticated;
revoke all on function penta_pr.invoke_terminal_provider_v3(text,jsonb) from public,anon,authenticated;
revoke all on function public.penta_pr_repo_allowed_v3(text) from public,anon,authenticated;
revoke all on function public.penta_pr_latest_zero_delta_v3(text,bigint) from public,anon,authenticated;
grant execute on function penta_pr.record_provider_truth_v3(text,bigint,text,text,boolean,text,integer,jsonb) to service_role;
grant execute on function penta_pr.invoke_terminal_provider_v3(text,jsonb) to service_role;
grant execute on function public.penta_pr_repo_allowed_v3(text) to service_role;
grant execute on function public.penta_pr_latest_zero_delta_v3(text,bigint) to service_role;
