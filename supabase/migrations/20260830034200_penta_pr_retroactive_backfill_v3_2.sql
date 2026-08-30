-- CrownThrive PentaPR terminal reconciliation v3.2 retroactive backfill
-- Historical provider truth is reconstructed without reopening or retroactively force-merging PRs.

create table if not exists penta_pr.retroactive_backfill_v3 (
  repo text primary key,
  next_page integer not null default 1 check (next_page >= 1),
  per_page integer not null default 100 check (per_page between 1 and 100),
  completed boolean not null default false,
  pages_processed bigint not null default 0,
  prs_observed bigint not null default 0,
  truth_backfilled bigint not null default 0,
  zero_delta_closed bigint not null default 0,
  lease_until timestamptz,
  attempt_count bigint not null default 0,
  last_page_count integer,
  last_run_at timestamptz,
  completed_at timestamptz,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into penta_pr.retroactive_backfill_v3(repo)
select repository_full_name
from integration_control.cos_repository_census_v1
where owner_login='crownthrive1'
  and archived=false
  and operationally_enabled=true
  and lifecycle_state='active'
on conflict(repo) do nothing;

create or replace function public.penta_pr_claim_retroactive_backfill_v3()
returns jsonb
language plpgsql security definer
set search_path='pg_catalog','penta_pr','integration_control'
as $$
declare r penta_pr.retroactive_backfill_v3%rowtype;
begin
  insert into penta_pr.retroactive_backfill_v3(repo)
  select repository_full_name
  from integration_control.cos_repository_census_v1
  where owner_login='crownthrive1' and archived=false and operationally_enabled=true and lifecycle_state='active'
  on conflict(repo) do nothing;

  select b.* into r
  from penta_pr.retroactive_backfill_v3 b
  join integration_control.cos_repository_census_v1 c on c.repository_full_name=b.repo
  where not b.completed
    and (b.lease_until is null or b.lease_until < now())
    and c.owner_login='crownthrive1' and c.archived=false and c.operationally_enabled=true and c.lifecycle_state='active'
  order by b.last_run_at nulls first,b.repo
  for update of b skip locked
  limit 1;

  if r.repo is null then return jsonb_build_object('claimed',false); end if;

  update penta_pr.retroactive_backfill_v3
  set lease_until=now()+interval '90 seconds',attempt_count=attempt_count+1,last_run_at=now(),updated_at=now()
  where repo=r.repo;

  return jsonb_build_object('claimed',true,'repo',r.repo,'page',r.next_page,'per_page',r.per_page,'attempt',r.attempt_count+1);
end $$;

create or replace function public.penta_pr_advance_retroactive_backfill_v3(
  p_repo text,p_page integer,p_page_count integer,p_truth_backfilled integer,p_zero_delta_closed integer,p_has_more boolean,p_evidence jsonb default '{}'::jsonb
) returns jsonb
language plpgsql security definer
set search_path='pg_catalog','penta_pr'
as $$
declare r penta_pr.retroactive_backfill_v3%rowtype;
begin
  update penta_pr.retroactive_backfill_v3
  set next_page=case when p_has_more then next_page+1 else next_page end,
      completed=not p_has_more,
      pages_processed=pages_processed+1,
      prs_observed=prs_observed+greatest(coalesce(p_page_count,0),0),
      truth_backfilled=truth_backfilled+greatest(coalesce(p_truth_backfilled,0),0),
      zero_delta_closed=zero_delta_closed+greatest(coalesce(p_zero_delta_closed,0),0),
      last_page_count=greatest(coalesce(p_page_count,0),0),
      completed_at=case when not p_has_more then coalesce(completed_at,now()) else completed_at end,
      lease_until=null,
      evidence=evidence||coalesce(p_evidence,'{}'::jsonb),
      updated_at=now()
  where repo=p_repo and next_page=p_page and not completed
  returning * into r;
  if r.repo is null then return jsonb_build_object('advanced',false,'reason','cursor_mismatch_or_complete','repo',p_repo,'page',p_page); end if;
  return jsonb_build_object('advanced',true,'repo',r.repo,'next_page',r.next_page,'completed',r.completed,'pages_processed',r.pages_processed,'prs_observed',r.prs_observed,'truth_backfilled',r.truth_backfilled,'zero_delta_closed',r.zero_delta_closed);
end $$;

create or replace function public.penta_pr_retroactive_backfill_status_v3()
returns jsonb
language sql stable security definer
set search_path='pg_catalog','penta_pr'
as $$
 select jsonb_build_object(
   'repos',coalesce(jsonb_agg(jsonb_build_object(
      'repo',repo,'next_page',next_page,'per_page',per_page,'completed',completed,'pages_processed',pages_processed,
      'prs_observed',prs_observed,'truth_backfilled',truth_backfilled,'zero_delta_closed',zero_delta_closed,
      'lease_until',lease_until,'last_run_at',last_run_at,'completed_at',completed_at,'last_page_count',last_page_count
    ) order by repo),'[]'::jsonb),
   'repo_count',count(*),
   'completed_count',count(*) filter(where completed),
   'pending_count',count(*) filter(where not completed),
   'total_prs_observed',coalesce(sum(prs_observed),0),
   'total_truth_backfilled',coalesce(sum(truth_backfilled),0),
   'total_zero_delta_closed',coalesce(sum(zero_delta_closed),0)
 ) from penta_pr.retroactive_backfill_v3;
$$;

create or replace function penta_pr.record_provider_truth_v3(
  p_repo text,p_pr_number bigint,p_head_sha text,p_state text,p_merged boolean,
  p_merge_commit_sha text default null,p_http_status integer default null,p_readback jsonb default '{}'::jsonb
) returns jsonb
language plpgsql security definer
set search_path='pg_catalog','penta_pr','integration_control','extensions'
as $$
declare v_sha text; v_terminal text;
begin
  if not exists(select 1 from integration_control.cos_repository_census_v1 where repository_full_name=p_repo and owner_login='crownthrive1' and archived=false and operationally_enabled=true and lifecycle_state='active') then
    raise exception 'repository_not_allowed';
  end if;
  v_sha:=encode(extensions.digest(convert_to(coalesce(p_readback,'{}'::jsonb)::text,'UTF8'),'sha256'),'hex');
  v_terminal:=case when lower(p_state)='closed' then case when coalesce(p_merged,false) then 'MERGED' else 'CLOSED' end else null end;

  insert into integration_control.github_pr_truth_receipts_v2(repo_full_name,pr_number,state,merged,head_sha,merge_commit_sha,http_status,evidence_sha256,observed_at)
  values(p_repo,p_pr_number,p_state,coalesce(p_merged,false),p_head_sha,p_merge_commit_sha,p_http_status,v_sha,now());

  insert into penta_pr.lifecycle(repo,pr_number,head_sha,terminal_state,terminal_at,last_observed_at,provider_updated_at,metadata)
  values(p_repo,p_pr_number,p_head_sha,v_terminal,case when v_terminal is not null then now() end,now(),now(),jsonb_build_object('retroactive_provider_truth',true,'last_provider_truth_sha256',v_sha,'last_provider_truth_at',now()))
  on conflict(repo,pr_number) do update set
    head_sha=excluded.head_sha,
    last_observed_at=excluded.last_observed_at,
    provider_updated_at=excluded.provider_updated_at,
    terminal_state=case when excluded.terminal_state is not null then excluded.terminal_state else null end,
    terminal_at=case when excluded.terminal_state is not null then coalesce(penta_pr.lifecycle.terminal_at,excluded.terminal_at) else null end,
    metadata=penta_pr.lifecycle.metadata||excluded.metadata;

  insert into penta_pr.events(repo,pr_number,event_type,actor,payload)
  values(p_repo,p_pr_number,'PROVIDER_TRUTH','PentaPR/PentaCloser',jsonb_build_object('head_sha',p_head_sha,'state',p_state,'merged',coalesce(p_merged,false),'merge_commit_sha',p_merge_commit_sha,'http_status',p_http_status,'evidence_sha256',v_sha,'retroactive_capable',true));
  return jsonb_build_object('state','RECORDED','repo',p_repo,'pr_number',p_pr_number,'head_sha',p_head_sha,'provider_state',p_state,'merged',coalesce(p_merged,false),'evidence_sha256',v_sha);
end $$;

update pentatime.operation_registry_v2
set metadata=metadata||jsonb_build_object('retroactive_backfill',true,'retroactive_merge',false,'historical_truth_upsert',true,'backfill_cursor','penta_pr.retroactive_backfill_v3'),updated_at=now()
where operation_key='penta_pr_terminal_reconcile';

revoke all on function public.penta_pr_claim_retroactive_backfill_v3() from public,anon,authenticated;
revoke all on function public.penta_pr_advance_retroactive_backfill_v3(text,integer,integer,integer,integer,boolean,jsonb) from public,anon,authenticated;
revoke all on function public.penta_pr_retroactive_backfill_status_v3() from public,anon,authenticated;
grant execute on function public.penta_pr_claim_retroactive_backfill_v3() to service_role;
grant execute on function public.penta_pr_advance_retroactive_backfill_v3(text,integer,integer,integer,integer,boolean,jsonb) to service_role;
grant execute on function public.penta_pr_retroactive_backfill_status_v3() to service_role;
