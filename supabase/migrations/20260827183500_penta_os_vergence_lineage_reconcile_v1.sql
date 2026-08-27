-- PentaOS / PentaVergence lineage reconciliation v1
-- Re-materializes the live PentaVergence control plane in Git without destructive rollback.
-- Canonical repository identity: crownthrive1/CrownThrive-OS.

begin;

create schema if not exists penta_runtime;

create table if not exists penta_runtime.repository_registry_v1 (
  repository_full_name text primary key,
  canonical_role text not null,
  enabled boolean not null default true,
  mutation_policy text not null default 'governed',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_runtime.vergence_jobs_v1 (
  job_id uuid primary key default gen_random_uuid(),
  cycle_key text not null,
  repository_full_name text not null references penta_runtime.repository_registry_v1(repository_full_name),
  mode text not null check (mode in ('continuity','deep','manual')),
  state text not null default 'queued' check (state in ('queued','claimed','completed','failed')),
  request jsonb not null default '{}'::jsonb,
  result jsonb,
  worker_run_id text,
  available_at timestamptz not null default now(),
  claimed_at timestamptz,
  completed_at timestamptz,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (cycle_key, repository_full_name)
);

create index if not exists vergence_jobs_v1_claim_idx
  on penta_runtime.vergence_jobs_v1(repository_full_name,state,available_at,created_at);

create table if not exists penta_runtime.vergence_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  job_id uuid not null references penta_runtime.vergence_jobs_v1(job_id) on delete cascade,
  repository_full_name text not null,
  mode text not null,
  disposition text not null,
  report jsonb not null,
  evidence_sha256 text,
  created_at timestamptz not null default now()
);

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
  unique (job_id, repository_full_name, pr_number, disposition)
);

create index if not exists vergence_repairs_v1_state_idx
  on penta_runtime.vergence_repairs_v1(state,created_at);

alter table penta_runtime.repository_registry_v1 enable row level security;
alter table penta_runtime.repository_registry_v1 force row level security;
alter table penta_runtime.vergence_jobs_v1 enable row level security;
alter table penta_runtime.vergence_jobs_v1 force row level security;
alter table penta_runtime.vergence_receipts_v1 enable row level security;
alter table penta_runtime.vergence_receipts_v1 force row level security;
alter table penta_runtime.vergence_repairs_v1 enable row level security;
alter table penta_runtime.vergence_repairs_v1 force row level security;

revoke all on table penta_runtime.repository_registry_v1 from public, anon, authenticated;
revoke all on table penta_runtime.vergence_jobs_v1 from public, anon, authenticated;
revoke all on table penta_runtime.vergence_receipts_v1 from public, anon, authenticated;
revoke all on table penta_runtime.vergence_repairs_v1 from public, anon, authenticated;

grant select,insert,update,delete on table penta_runtime.repository_registry_v1 to service_role;
grant select,insert,update,delete on table penta_runtime.vergence_jobs_v1 to service_role;
grant select,insert on table penta_runtime.vergence_receipts_v1 to service_role;
grant select,insert,update,delete on table penta_runtime.vergence_repairs_v1 to service_role;

-- Current canonical repository identity. Any competing root authority is preserved as disabled lineage only.
insert into penta_runtime.repository_registry_v1(repository_full_name,canonical_role,enabled,mutation_policy,metadata)
values (
  'crownthrive1/CrownThrive-OS',
  'canonical PentaOS institutional source and PentaDocs authority',
  true,
  'governed',
  jsonb_build_object('canonical_identity',true,'identity_version','CrownThrive-OS','lineage_reconciled_at',now())
)
on conflict (repository_full_name) do update set
  canonical_role=excluded.canonical_role,
  enabled=true,
  mutation_policy='governed',
  metadata=penta_runtime.repository_registry_v1.metadata||excluded.metadata,
  updated_at=now();

insert into penta_runtime.repository_registry_v1(repository_full_name,canonical_role,enabled,mutation_policy,metadata)
values
  ('crownthrive1/CrownThrive-CIE','CIE child framework repository',true,'governed','{}'::jsonb),
  ('crownthrive1/chlom-protocol','CHLOM protocol child repository',true,'governed','{}'::jsonb)
on conflict (repository_full_name) do update set
  canonical_role=excluded.canonical_role,
  enabled=true,
  mutation_policy='governed',
  updated_at=now();

update penta_runtime.repository_registry_v1
set enabled=false,
    canonical_role='historical compatibility lineage; superseded by CrownThrive-OS',
    mutation_policy='historical_read_only',
    metadata=metadata||jsonb_build_object(
      'legacy_identity',true,
      'active_authority',false,
      'superseded_by','crownthrive1/CrownThrive-OS',
      'preserve_historical_evidence',true,
      'lineage_reconciled_at',now()
    ),
    updated_at=now()
where repository_full_name <> 'crownthrive1/CrownThrive-OS'
  and canonical_role='canonical PentaOS institutional source and PentaDocs authority'
  and enabled;

create or replace function penta_runtime.penta_vergence_enqueue_v1(p_mode text default 'continuity')
returns jsonb
language plpgsql
security definer
set search_path to 'penta_runtime','pg_temp'
as $$
declare
  v_mode text:=lower(coalesce(p_mode,'continuity'));
  v_cycle text;
  v_count integer:=0;
begin
  if v_mode not in ('continuity','deep','manual') then raise exception 'unsupported mode: %',v_mode; end if;
  if v_mode='deep' then
    v_cycle:='deep:'||to_char(timezone('America/New_York',now()),'YYYY-MM-DD');
  elsif v_mode='continuity' then
    v_cycle:='continuity:'||floor(extract(epoch from now())/14400)::bigint::text;
  else
    v_cycle:='manual:'||to_char(now(),'YYYYMMDDHH24MISSMS');
  end if;

  insert into vergence_jobs_v1(cycle_key,repository_full_name,mode,request)
  select v_cycle,r.repository_full_name,v_mode,
         jsonb_build_object('contract','ct.penta.vergence.request.v1','source','PentaBase','mode',v_mode,'requested_at',now())
  from repository_registry_v1 r
  where r.enabled
  on conflict(cycle_key,repository_full_name) do nothing;
  get diagnostics v_count=row_count;
  return jsonb_build_object('contract','ct.penta.vergence.enqueue.v1','cycle_key',v_cycle,'mode',v_mode,'jobs_created',v_count,'scheduled_at',now());
end;
$$;

create or replace function penta_runtime.penta_vergence_deep_gate_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'penta_runtime','pg_temp'
as $$
declare
  v_local timestamp:=timezone('America/New_York',now());
begin
  if extract(hour from v_local)::integer <> 23 then
    return jsonb_build_object('contract','ct.penta.vergence.deep-gate.v1','result','NOOP_OUTSIDE_23_LOCAL','local_time',v_local);
  end if;
  return penta_runtime.penta_vergence_enqueue_v1('deep');
end;
$$;

create or replace function penta_runtime.penta_vergence_claim_v1(p_repository text,p_worker_run_id text default null)
returns jsonb
language plpgsql
security definer
set search_path to 'penta_runtime','pg_temp'
as $$
declare
  v_job vergence_jobs_v1%rowtype;
begin
  with candidate as (
    select job_id
    from vergence_jobs_v1
    where repository_full_name=p_repository
      and state='queued'
      and available_at<=now()
    order by case mode when 'deep' then 0 when 'manual' then 1 else 2 end,created_at
    for update skip locked
    limit 1
  )
  update vergence_jobs_v1 j
  set state='claimed',claimed_at=now(),worker_run_id=p_worker_run_id,updated_at=now()
  from candidate c
  where j.job_id=c.job_id
  returning j.* into v_job;

  if v_job.job_id is null then return jsonb_build_object('claimed',false,'repository',p_repository); end if;
  return jsonb_build_object('claimed',true,'job_id',v_job.job_id,'cycle_key',v_job.cycle_key,'repository',v_job.repository_full_name,'mode',v_job.mode,'request',v_job.request);
end;
$$;

create or replace function penta_runtime.penta_vergence_release_v1(p_job_id uuid,p_error text default 'worker_failed')
returns jsonb
language plpgsql
security definer
set search_path to 'penta_runtime','pg_temp'
as $$
declare
  v_released boolean:=false;
begin
  update penta_runtime.vergence_jobs_v1
  set state='queued',claimed_at=null,worker_run_id=null,available_at=now()+interval '15 minutes',
      error=left(coalesce(p_error,'worker_failed'),1000),updated_at=now()
  where job_id=p_job_id and state='claimed';
  v_released:=found;
  return jsonb_build_object('contract','ct.penta.vergence.release.v1','job_id',p_job_id,'released',v_released);
end;
$$;

create or replace function penta_runtime.penta_vergence_queue_repairs_v1(p_job_id uuid,p_report jsonb)
returns jsonb
language plpgsql
security definer
set search_path to 'penta_runtime','public','pg_temp'
as $$
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
      title=excluded.title,
      priority_score=greatest(public.ct_factory_backlog_items.priority_score,excluded.priority_score),
      priority_class=excluded.priority_class,
      last_seen_at=now(),
      payload=excluded.payload,
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
end;
$$;

create or replace function penta_runtime.penta_vergence_complete_v1(p_job_id uuid,p_report jsonb,p_evidence_sha256 text default null)
returns jsonb
language plpgsql
security definer
set search_path to 'penta_runtime','public','pg_temp'
as $$
declare
  v_job penta_runtime.vergence_jobs_v1%rowtype;
  v_disposition text;
  v_repairs jsonb;
begin
  select * into v_job from penta_runtime.vergence_jobs_v1 where job_id=p_job_id for update;
  if v_job.job_id is null then raise exception 'job not found'; end if;
  if v_job.state <> 'claimed' then raise exception 'job not claimed: %',v_job.state; end if;
  if coalesce(p_report->>'repository','') <> v_job.repository_full_name then raise exception 'report repository mismatch'; end if;
  v_repairs:=penta_runtime.penta_vergence_queue_repairs_v1(p_job_id,p_report);
  v_disposition:=case when coalesce((p_report->>'mutations')::integer,0)>0 then 'MUTATED' else 'OBSERVED' end;

  update penta_runtime.vergence_jobs_v1
  set state='completed',result=p_report||jsonb_build_object('repair_bridge',v_repairs),error=null,completed_at=now(),updated_at=now()
  where job_id=p_job_id;

  insert into penta_runtime.vergence_receipts_v1(job_id,repository_full_name,mode,disposition,report,evidence_sha256)
  values(p_job_id,v_job.repository_full_name,v_job.mode,v_disposition,p_report||jsonb_build_object('repair_bridge',v_repairs),p_evidence_sha256);

  return jsonb_build_object('contract','ct.penta.vergence.complete.v1','job_id',p_job_id,'state','completed','disposition',v_disposition,'repair_bridge',v_repairs);
end;
$$;

create or replace function penta_runtime.penta_vergence_status_v1()
returns jsonb
language sql
stable
security definer
set search_path to 'penta_runtime','pg_temp'
as $$
  select jsonb_build_object(
    'contract','ct.penta.vergence.status.v1',
    'queued',(select count(*) from vergence_jobs_v1 where state='queued'),
    'claimed',(select count(*) from vergence_jobs_v1 where state='claimed'),
    'completed',(select count(*) from vergence_jobs_v1 where state='completed'),
    'failed',(select count(*) from vergence_jobs_v1 where state='failed'),
    'last_completed_at',(select max(completed_at) from vergence_jobs_v1 where state='completed'),
    'cadence',jsonb_build_object('continuity','every_4_hours','deep','23:00 America/New_York'),
    'generated_at',now()
  );
$$;

create or replace function penta_runtime.penta_vergence_repairs_status_v1()
returns jsonb
language sql
stable
security definer
set search_path to 'penta_runtime','pg_temp'
as $$
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

revoke all on function penta_runtime.penta_vergence_enqueue_v1(text) from public, anon, authenticated;
revoke all on function penta_runtime.penta_vergence_deep_gate_v1() from public, anon, authenticated;
revoke all on function penta_runtime.penta_vergence_claim_v1(text,text) from public, anon, authenticated;
revoke all on function penta_runtime.penta_vergence_release_v1(uuid,text) from public, anon, authenticated;
revoke all on function penta_runtime.penta_vergence_queue_repairs_v1(uuid,jsonb) from public, anon, authenticated;
revoke all on function penta_runtime.penta_vergence_complete_v1(uuid,jsonb,text) from public, anon, authenticated;
revoke all on function penta_runtime.penta_vergence_status_v1() from public, anon, authenticated;
revoke all on function penta_runtime.penta_vergence_repairs_status_v1() from public, anon, authenticated;

grant execute on function penta_runtime.penta_vergence_enqueue_v1(text) to service_role;
grant execute on function penta_runtime.penta_vergence_deep_gate_v1() to service_role;
grant execute on function penta_runtime.penta_vergence_claim_v1(text,text) to service_role;
grant execute on function penta_runtime.penta_vergence_release_v1(uuid,text) to service_role;
grant execute on function penta_runtime.penta_vergence_queue_repairs_v1(uuid,jsonb) to service_role;
grant execute on function penta_runtime.penta_vergence_complete_v1(uuid,jsonb,text) to service_role;
grant execute on function penta_runtime.penta_vergence_status_v1() to service_role;
grant execute on function penta_runtime.penta_vergence_repairs_status_v1() to service_role;

-- Preserve the existing scheduler topology: no new external clock, only the two existing pg_cron internal jobs.
do $$
begin
  if not exists (select 1 from cron.job where jobname='penta-vergence-continuity-4h-v1') then
    perform cron.schedule('penta-vergence-continuity-4h-v1','23 */4 * * *',q$cron$select penta_runtime.penta_vergence_enqueue_v1('continuity');$cron$);
  end if;
  if not exists (select 1 from cron.job where jobname='penta-vergence-deep-local-gate-v1') then
    perform cron.schedule('penta-vergence-deep-local-gate-v1','0 * * * *',q$cron$select penta_runtime.penta_vergence_deep_gate_v1();$cron$);
  end if;
end;
$$;

commit;