-- PentaVergence -> PentaFactory bounded repair bridge.
-- This migration also normalizes the release function to the exact live implementation.

create table if not exists penta_runtime.vergence_repairs_v1 (
  repair_id uuid primary key default gen_random_uuid(),
  job_id uuid not null references penta_runtime.vergence_jobs_v1(job_id) on delete cascade,
  repository_full_name text not null,
  pr_number integer not null,
  head_sha text,
  disposition text not null check (disposition in ('REPAIR_REQUIRED','RESTACK_REQUIRED')),
  state text not null default 'queued' check (state in ('queued','factory_bound','implemented','hold','failed')),
  factory_backlog_id uuid references public.ct_factory_backlog_items(id) on delete set null,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(job_id, repository_full_name, pr_number, disposition)
);
create index if not exists vergence_repairs_v1_state_idx on penta_runtime.vergence_repairs_v1(state,created_at);
alter table penta_runtime.vergence_repairs_v1 enable row level security;
alter table penta_runtime.vergence_repairs_v1 force row level security;
revoke all on penta_runtime.vergence_repairs_v1 from public,anon,authenticated;
grant select,insert,update,delete on penta_runtime.vergence_repairs_v1 to service_role;

create or replace function penta_runtime.penta_vergence_queue_repairs_v1(p_job_id uuid,p_report jsonb)
returns jsonb language plpgsql security definer set search_path=penta_runtime,public,pg_temp as $$
declare
  v_job penta_runtime.vergence_jobs_v1%rowtype;
  v_decision jsonb;
  v_disposition text;
  v_pr integer;
  v_head text;
  v_source_ref text;
  v_backlog_id uuid;
  v_repair_id uuid;
  v_queued integer:=0;
begin
  select * into v_job from penta_runtime.vergence_jobs_v1 where job_id=p_job_id;
  if v_job.job_id is null then raise exception 'job not found'; end if;
  if coalesce(p_report->>'repository','') <> v_job.repository_full_name then raise exception 'report repository mismatch'; end if;

  for v_decision in select value from jsonb_array_elements(coalesce(p_report->'decisions','[]'::jsonb))
  loop
    v_disposition:=coalesce(v_decision->>'disposition','');
    if v_disposition not in ('REPAIR_REQUIRED','RESTACK_REQUIRED') then continue; end if;
    v_pr:=nullif(v_decision->>'number','')::integer;
    if v_pr is null then continue; end if;
    v_head:=nullif(v_decision->>'head_sha','');
    v_source_ref:=v_job.repository_full_name||'#'||v_pr::text||':'||lower(v_disposition)||':'||coalesce(v_head,'unknown');

    insert into public.ct_factory_backlog_items(
      source_system,source_ref,item_type,surface_id,provider_system,operation_key,title,
      priority_score,priority_class,governance_class,autonomous_eligible,requires_human_approval,
      deployment_policy,state,payload,last_seen_at,next_eligible_at
    ) values (
      'PentaVergence',v_source_ref,'continuity_repair',v_job.repository_full_name,'github',
      case when v_disposition='RESTACK_REQUIRED' then 'restack_pull_request' else 'repair_pull_request' end,
      'PentaVergence '||replace(lower(v_disposition),'_',' ')||' for '||v_job.repository_full_name||' PR #'||v_pr::text,
      case when v_disposition='REPAIR_REQUIRED' then 820 else 760 end,
      case when v_disposition='REPAIR_REQUIRED' then 'P1' else 'P2' end,
      'D1',true,false,'governed','candidate',
      jsonb_build_object(
        'contract','ct.penta.vergence.factory-repair.v1','job_id',p_job_id,'repository',v_job.repository_full_name,
        'pr_number',v_pr,'head_sha',v_head,'disposition',v_disposition,'reasons',coalesce(v_decision->'reasons','[]'::jsonb),
        'continuity_rule','preserve_head_and_main; no force push; replacement PR before stale closure'
      ),now(),now()
    )
    on conflict(source_system,source_ref,item_type) do update set
      title=excluded.title,priority_score=greatest(public.ct_factory_backlog_items.priority_score,excluded.priority_score),
      priority_class=excluded.priority_class,last_seen_at=now(),payload=excluded.payload,
      next_eligible_at=least(public.ct_factory_backlog_items.next_eligible_at,now())
    returning id into v_backlog_id;

    insert into penta_runtime.vergence_repairs_v1(job_id,repository_full_name,pr_number,head_sha,disposition,state,factory_backlog_id,evidence)
    values(p_job_id,v_job.repository_full_name,v_pr,v_head,v_disposition,'factory_bound',v_backlog_id,v_decision)
    on conflict(job_id,repository_full_name,pr_number,disposition) do update set
      head_sha=excluded.head_sha,state='factory_bound',factory_backlog_id=excluded.factory_backlog_id,evidence=excluded.evidence,updated_at=now()
    returning repair_id into v_repair_id;
    v_queued:=v_queued+1;
  end loop;

  return jsonb_build_object('contract','ct.penta.vergence.queue-repairs.v1','job_id',p_job_id,'repairs_queued',v_queued);
end;$$;
revoke all on function penta_runtime.penta_vergence_queue_repairs_v1(uuid,jsonb) from public,anon,authenticated;
grant execute on function penta_runtime.penta_vergence_queue_repairs_v1(uuid,jsonb) to service_role;

create or replace function penta_runtime.penta_vergence_complete_v1(p_job_id uuid,p_report jsonb,p_evidence_sha256 text default null)
returns jsonb language plpgsql security definer set search_path=penta_runtime,public,pg_temp as $$
declare v_job penta_runtime.vergence_jobs_v1%rowtype; v_disposition text; v_repairs jsonb;
begin
  select * into v_job from penta_runtime.vergence_jobs_v1 where job_id=p_job_id for update;
  if v_job.job_id is null then raise exception 'job not found'; end if;
  if v_job.state <> 'claimed' then raise exception 'job not claimed: %',v_job.state; end if;
  if coalesce(p_report->>'repository','') <> v_job.repository_full_name then raise exception 'report repository mismatch'; end if;
  v_repairs:=penta_runtime.penta_vergence_queue_repairs_v1(p_job_id,p_report);
  v_disposition:=case when coalesce((p_report->>'mutations')::integer,0)>0 then 'MUTATED' else 'OBSERVED' end;
  update penta_runtime.vergence_jobs_v1 set state='completed',result=p_report||jsonb_build_object('repair_bridge',v_repairs),error=null,completed_at=now(),updated_at=now() where job_id=p_job_id;
  insert into penta_runtime.vergence_receipts_v1(job_id,repository_full_name,mode,disposition,report,evidence_sha256)
  values(p_job_id,v_job.repository_full_name,v_job.mode,v_disposition,p_report||jsonb_build_object('repair_bridge',v_repairs),p_evidence_sha256);
  return jsonb_build_object('contract','ct.penta.vergence.complete.v1','job_id',p_job_id,'state','completed','disposition',v_disposition,'repair_bridge',v_repairs);
end;$$;
revoke all on function penta_runtime.penta_vergence_complete_v1(uuid,jsonb,text) from public,anon,authenticated;
grant execute on function penta_runtime.penta_vergence_complete_v1(uuid,jsonb,text) to service_role;

create or replace function penta_runtime.penta_vergence_release_v1(p_job_id uuid,p_error text default 'worker_failed')
returns jsonb language plpgsql security definer set search_path=penta_runtime,pg_temp as $$
declare v_released boolean:=false;
begin
  update penta_runtime.vergence_jobs_v1 set state='queued',claimed_at=null,worker_run_id=null,available_at=now()+interval '15 minutes',error=left(coalesce(p_error,'worker_failed'),1000),updated_at=now()
  where job_id=p_job_id and state='claimed';
  v_released:=found;
  return jsonb_build_object('contract','ct.penta.vergence.release.v1','job_id',p_job_id,'released',v_released);
end;$$;
revoke all on function penta_runtime.penta_vergence_release_v1(uuid,text) from public,anon,authenticated;
grant execute on function penta_runtime.penta_vergence_release_v1(uuid,text) to service_role;

create or replace function penta_runtime.penta_vergence_repairs_status_v1()
returns jsonb language sql stable security definer set search_path=penta_runtime,pg_temp as $$
  select jsonb_build_object(
    'contract','ct.penta.vergence.repairs-status.v1',
    'total',(select count(*) from vergence_repairs_v1),
    'factory_bound',(select count(*) from vergence_repairs_v1 where state='factory_bound'),
    'implemented',(select count(*) from vergence_repairs_v1 where state='implemented'),
    'hold',(select count(*) from vergence_repairs_v1 where state='hold'),
    'failed',(select count(*) from vergence_repairs_v1 where state='failed'),
    'generated_at',now()
  );
$$;
revoke all on function penta_runtime.penta_vergence_repairs_status_v1() from public,anon,authenticated;
grant execute on function penta_runtime.penta_vergence_repairs_status_v1() to service_role;
