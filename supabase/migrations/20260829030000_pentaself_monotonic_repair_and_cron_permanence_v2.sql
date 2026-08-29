-- CrownThrive OS — PentaSELF monotonic repair and cron permanence v2
-- Production-convergence source. This migration does not rewrite historical provider migrations.
-- Verified repair rollback is allowed only after failed verification, a newer governed generation,
-- or explicit founder authority. Unknown newer configuration is held, never overwritten.

create schema if not exists penta_self;

create table if not exists penta_self.repair_commitments_v2 (
  commitment_key text primary key,
  target_kind text not null,
  target_ref text not null,
  generation bigint not null check (generation > 0),
  desired_state jsonb not null default '{}'::jsonb,
  state text not null default 'verified' check (state in ('candidate','verified','active','held','superseded')),
  persistence_mode text not null default 'monotonic_after_verification',
  rollback_policy text not null default 'failed_verification_or_founder_explicit_only',
  verification_evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  verified_at timestamptz,
  last_reconciled_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_self.repair_commitment_events_v2 (
  event_id uuid primary key default gen_random_uuid(),
  commitment_key text not null,
  generation bigint not null,
  event_type text not null,
  details jsonb not null default '{}'::jsonb,
  event_sha256 text not null,
  created_at timestamptz not null default now()
);
create index if not exists repair_commitment_events_key_time_v2
  on penta_self.repair_commitment_events_v2(commitment_key,created_at desc);

create table if not exists penta_self.problem_resolution_fences_v2 (
  problem_fingerprint text primary key,
  problem_title text not null,
  resolved_generation bigint not null check (resolved_generation > 0),
  verified_through timestamptz not null,
  resolution_evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_self.required_cron_baseline_v2 (
  jobname text primary key,
  schedule text not null,
  command text not null,
  generation bigint not null default 1 check (generation > 0),
  enforcement_mode text not null default 'restore_missing_only'
    check (enforcement_mode in ('restore_missing_only','enforce_known_superseded','observe_only')),
  enabled boolean not null default true,
  command_sha256 text not null,
  verified_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_self.required_cron_versions_v2 (
  jobname text not null,
  command_sha256 text not null,
  disposition text not null check (disposition in ('current','superseded','allowed_compatibility')),
  generation bigint not null,
  command text,
  created_at timestamptz not null default now(),
  primary key(jobname,command_sha256)
);

create table if not exists penta_self.cron_permanence_events_v2 (
  event_id uuid primary key default gen_random_uuid(),
  jobname text not null,
  event_type text not null,
  prior_sha256 text,
  desired_sha256 text,
  details jsonb not null default '{}'::jsonb,
  event_sha256 text not null,
  created_at timestamptz not null default now()
);
create index if not exists cron_permanence_events_job_time_v2
  on penta_self.cron_permanence_events_v2(jobname,created_at desc);

alter table penta_self.repair_commitments_v2 enable row level security;
alter table penta_self.repair_commitment_events_v2 enable row level security;
alter table penta_self.problem_resolution_fences_v2 enable row level security;
alter table penta_self.required_cron_baseline_v2 enable row level security;
alter table penta_self.required_cron_versions_v2 enable row level security;
alter table penta_self.cron_permanence_events_v2 enable row level security;

revoke all on penta_self.repair_commitments_v2 from public,anon,authenticated;
revoke all on penta_self.repair_commitment_events_v2 from public,anon,authenticated;
revoke all on penta_self.problem_resolution_fences_v2 from public,anon,authenticated;
revoke all on penta_self.required_cron_baseline_v2 from public,anon,authenticated;
revoke all on penta_self.required_cron_versions_v2 from public,anon,authenticated;
revoke all on penta_self.cron_permanence_events_v2 from public,anon,authenticated;

grant select,insert,update on penta_self.repair_commitments_v2 to service_role;
grant select,insert on penta_self.repair_commitment_events_v2 to service_role;
grant select,insert,update on penta_self.problem_resolution_fences_v2 to service_role;
grant select,insert,update on penta_self.required_cron_baseline_v2 to service_role;
grant select,insert,update on penta_self.required_cron_versions_v2 to service_role;
grant select,insert on penta_self.cron_permanence_events_v2 to service_role;

create or replace function penta_self.reject_append_only_mutation_v2()
returns trigger
language plpgsql
security definer
set search_path=pg_catalog,penta_self
as $$
begin
  raise exception 'append-only PentaSELF evidence cannot be updated or deleted';
end $$;

revoke all on function penta_self.reject_append_only_mutation_v2() from public,anon,authenticated;
grant execute on function penta_self.reject_append_only_mutation_v2() to service_role;

drop trigger if exists repair_commitment_events_immutable_v2 on penta_self.repair_commitment_events_v2;
create trigger repair_commitment_events_immutable_v2
before update or delete on penta_self.repair_commitment_events_v2
for each row execute function penta_self.reject_append_only_mutation_v2();

drop trigger if exists cron_permanence_events_immutable_v2 on penta_self.cron_permanence_events_v2;
create trigger cron_permanence_events_immutable_v2
before update or delete on penta_self.cron_permanence_events_v2
for each row execute function penta_self.reject_append_only_mutation_v2();

create or replace function penta_self.commit_verified_repair_v2(
  p_commitment_key text,
  p_target_kind text,
  p_target_ref text,
  p_generation bigint,
  p_desired_state jsonb,
  p_verification_evidence jsonb,
  p_state text default 'active'
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_self,extensions
as $$
declare
  v_existing_generation bigint;
  v_payload jsonb;
  v_digest text;
begin
  select generation into v_existing_generation
  from penta_self.repair_commitments_v2
  where commitment_key=p_commitment_key
  for update;

  if found and p_generation < v_existing_generation then
    return jsonb_build_object(
      'accepted',false,
      'reason','stale_generation_rejected',
      'current_generation',v_existing_generation,
      'requested_generation',p_generation
    );
  end if;

  v_payload:=jsonb_build_object(
    'commitment_key',p_commitment_key,
    'target_kind',p_target_kind,
    'target_ref',p_target_ref,
    'generation',p_generation,
    'desired_state',coalesce(p_desired_state,'{}'::jsonb),
    'verification_evidence',coalesce(p_verification_evidence,'{}'::jsonb),
    'state',p_state,
    'persistence_mode','monotonic_after_verification',
    'rollback_policy','failed_verification_or_founder_explicit_only'
  );
  v_digest:=encode(extensions.digest(v_payload::text,'sha256'),'hex');

  insert into penta_self.repair_commitments_v2(
    commitment_key,target_kind,target_ref,generation,desired_state,state,
    persistence_mode,rollback_policy,verification_evidence,evidence_sha256,
    verified_at,last_reconciled_at
  ) values (
    p_commitment_key,p_target_kind,p_target_ref,p_generation,
    coalesce(p_desired_state,'{}'::jsonb),p_state,
    'monotonic_after_verification','failed_verification_or_founder_explicit_only',
    coalesce(p_verification_evidence,'{}'::jsonb),v_digest,now(),now()
  )
  on conflict(commitment_key) do update set
    target_kind=excluded.target_kind,
    target_ref=excluded.target_ref,
    generation=excluded.generation,
    desired_state=excluded.desired_state,
    state=excluded.state,
    persistence_mode=excluded.persistence_mode,
    rollback_policy=excluded.rollback_policy,
    verification_evidence=excluded.verification_evidence,
    evidence_sha256=excluded.evidence_sha256,
    verified_at=excluded.verified_at,
    last_reconciled_at=excluded.last_reconciled_at,
    updated_at=now()
  where excluded.generation>=penta_self.repair_commitments_v2.generation;

  insert into penta_self.repair_commitment_events_v2(
    commitment_key,generation,event_type,details,event_sha256
  ) values (p_commitment_key,p_generation,'VERIFIED_COMMITMENT',v_payload,v_digest);

  return jsonb_build_object(
    'accepted',true,
    'commitment_key',p_commitment_key,
    'generation',p_generation,
    'evidence_sha256',v_digest,
    'rollback_policy','failed_verification_or_founder_explicit_only'
  );
end $$;

revoke all on function penta_self.commit_verified_repair_v2(text,text,text,bigint,jsonb,jsonb,text)
  from public,anon,authenticated;
grant execute on function penta_self.commit_verified_repair_v2(text,text,text,bigint,jsonb,jsonb,text)
  to service_role;

create or replace function penta_self.register_problem_resolution_fence_v2(
  p_problem_title text,
  p_verified_through timestamptz,
  p_evidence jsonb,
  p_generation bigint default 1
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_self,extensions
as $$
declare
  v_problem penta_self.problem_ledger_v1%rowtype;
  v_payload jsonb;
  v_digest text;
begin
  select * into v_problem
  from penta_self.problem_ledger_v1
  where title=p_problem_title
  order by updated_at desc
  limit 1
  for update;

  if not found then
    return jsonb_build_object('resolved',false,'reason','problem_not_found','title',p_problem_title);
  end if;

  v_payload:=jsonb_build_object(
    'problem_id',v_problem.problem_id,
    'fingerprint',v_problem.fingerprint,
    'title',v_problem.title,
    'verified_through',p_verified_through,
    'generation',p_generation,
    'evidence',coalesce(p_evidence,'{}'::jsonb)
  );
  v_digest:=encode(extensions.digest(v_payload::text,'sha256'),'hex');

  insert into penta_self.problem_resolution_fences_v2(
    problem_fingerprint,problem_title,resolved_generation,verified_through,
    resolution_evidence,evidence_sha256,active
  ) values (
    v_problem.fingerprint,v_problem.title,p_generation,p_verified_through,
    coalesce(p_evidence,'{}'::jsonb),v_digest,true
  )
  on conflict(problem_fingerprint) do update set
    problem_title=excluded.problem_title,
    resolved_generation=greatest(
      penta_self.problem_resolution_fences_v2.resolved_generation,
      excluded.resolved_generation
    ),
    verified_through=greatest(
      penta_self.problem_resolution_fences_v2.verified_through,
      excluded.verified_through
    ),
    resolution_evidence=excluded.resolution_evidence,
    evidence_sha256=excluded.evidence_sha256,
    active=true,
    updated_at=now();

  update penta_self.problem_ledger_v1 set
    state='resolved',
    verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||jsonb_build_object(
      'durable_resolution_v2',p_evidence,
      'verified_through',p_verified_through,
      'evidence_sha256',v_digest
    ),
    resolved_at=coalesce(resolved_at,now()),
    blocked_reason=null,
    last_error=null,
    updated_at=now()
  where problem_id=v_problem.problem_id
    and coalesce(last_seen_at,'epoch'::timestamptz)<=p_verified_through;

  return jsonb_build_object(
    'resolved',true,
    'problem_id',v_problem.problem_id,
    'fingerprint',v_problem.fingerprint,
    'verified_through',p_verified_through,
    'evidence_sha256',v_digest
  );
end $$;

revoke all on function penta_self.register_problem_resolution_fence_v2(text,timestamptz,jsonb,bigint)
  from public,anon,authenticated;
grant execute on function penta_self.register_problem_resolution_fence_v2(text,timestamptz,jsonb,bigint)
  to service_role;

create or replace function penta_self.enforce_resolution_fences_v2()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_self
as $$
declare v_count integer;
begin
  update penta_self.problem_ledger_v1 p set
    state='resolved',
    resolved_at=coalesce(p.resolved_at,now()),
    blocked_reason=null,
    last_error=null,
    verification_evidence=coalesce(p.verification_evidence,'{}'::jsonb)||jsonb_build_object(
      'resolution_fence_reapplied',true,
      'fence_verified_through',f.verified_through,
      'fence_sha256',f.evidence_sha256
    ),
    updated_at=now()
  from penta_self.problem_resolution_fences_v2 f
  where f.active=true
    and p.fingerprint=f.problem_fingerprint
    and coalesce(p.last_seen_at,'epoch'::timestamptz)<=f.verified_through
    and p.state<>'resolved';
  get diagnostics v_count=row_count;
  return jsonb_build_object('reapplied',v_count,'checked_at',now());
end $$;

revoke all on function penta_self.enforce_resolution_fences_v2() from public,anon,authenticated;
grant execute on function penta_self.enforce_resolution_fences_v2() to service_role;

create or replace function penta_self.reconcile_required_crons_v2()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_self,cron,extensions
as $$
declare
  r record;
  j record;
  v_current_sha text;
  v_event jsonb;
  v_event_sha text;
  v_restored integer:=0;
  v_healthy integer:=0;
  v_held integer:=0;
begin
  for r in
    select * from penta_self.required_cron_baseline_v2
    where enabled=true
    order by jobname
  loop
    select jobid,schedule,command,active into j
    from cron.job
    where jobname=r.jobname
    order by jobid desc
    limit 1;

    if not found then
      perform cron.schedule(r.jobname,r.schedule,r.command);
      v_event:=jsonb_build_object(
        'jobname',r.jobname,
        'action','RESTORED_MISSING',
        'desired_sha256',r.command_sha256,
        'generation',r.generation
      );
      v_event_sha:=encode(extensions.digest(v_event::text,'sha256'),'hex');
      insert into penta_self.cron_permanence_events_v2(
        jobname,event_type,desired_sha256,details,event_sha256
      ) values (r.jobname,'RESTORED_MISSING',r.command_sha256,v_event,v_event_sha);
      v_restored:=v_restored+1;
      continue;
    end if;

    v_current_sha:=encode(
      extensions.digest((j.schedule||E'\n'||j.command)::text,'sha256'),
      'hex'
    );

    if j.active and v_current_sha=r.command_sha256 then
      v_healthy:=v_healthy+1;
      continue;
    end if;

    if not j.active then
      perform cron.unschedule(j.jobid);
      perform cron.schedule(r.jobname,r.schedule,r.command);
      v_event:=jsonb_build_object(
        'jobname',r.jobname,
        'action','RESTORED_INACTIVE',
        'prior_sha256',v_current_sha,
        'desired_sha256',r.command_sha256,
        'generation',r.generation
      );
      v_event_sha:=encode(extensions.digest(v_event::text,'sha256'),'hex');
      insert into penta_self.cron_permanence_events_v2(
        jobname,event_type,prior_sha256,desired_sha256,details,event_sha256
      ) values (
        r.jobname,'RESTORED_INACTIVE',v_current_sha,r.command_sha256,v_event,v_event_sha
      );
      v_restored:=v_restored+1;
      continue;
    end if;

    if r.enforcement_mode='enforce_known_superseded'
       and exists(
         select 1 from penta_self.required_cron_versions_v2 v
         where v.jobname=r.jobname
           and v.command_sha256=v_current_sha
           and v.disposition='superseded'
       ) then
      perform cron.unschedule(j.jobid);
      perform cron.schedule(r.jobname,r.schedule,r.command);
      v_event:=jsonb_build_object(
        'jobname',r.jobname,
        'action','REPAIRED_KNOWN_ROLLBACK',
        'prior_sha256',v_current_sha,
        'desired_sha256',r.command_sha256,
        'generation',r.generation
      );
      v_event_sha:=encode(extensions.digest(v_event::text,'sha256'),'hex');
      insert into penta_self.cron_permanence_events_v2(
        jobname,event_type,prior_sha256,desired_sha256,details,event_sha256
      ) values (
        r.jobname,'REPAIRED_KNOWN_ROLLBACK',v_current_sha,r.command_sha256,v_event,v_event_sha
      );
      v_restored:=v_restored+1;
    else
      v_event:=jsonb_build_object(
        'jobname',r.jobname,
        'action','UNKNOWN_DRIFT_HOLD',
        'prior_sha256',v_current_sha,
        'desired_sha256',r.command_sha256,
        'generation',r.generation,
        'automatic_overwrite',false
      );
      v_event_sha:=encode(extensions.digest(v_event::text,'sha256'),'hex');
      if not exists(
        select 1 from penta_self.cron_permanence_events_v2 e
        where e.jobname=r.jobname
          and e.event_type='UNKNOWN_DRIFT_HOLD'
          and e.prior_sha256=v_current_sha
          and e.desired_sha256=r.command_sha256
          and e.created_at>now()-interval '1 hour'
      ) then
        insert into penta_self.cron_permanence_events_v2(
          jobname,event_type,prior_sha256,desired_sha256,details,event_sha256
        ) values (
          r.jobname,'UNKNOWN_DRIFT_HOLD',v_current_sha,r.command_sha256,v_event,v_event_sha
        );
      end if;
      v_held:=v_held+1;
    end if;
  end loop;

  return jsonb_build_object(
    'healthy',v_healthy,
    'restored',v_restored,
    'unknown_drift_held',v_held,
    'automatic_unknown_overwrite',false,
    'checked_at',now()
  );
end $$;

revoke all on function penta_self.reconcile_required_crons_v2() from public,anon,authenticated;
grant execute on function penta_self.reconcile_required_crons_v2() to service_role;

create or replace function public.penta_self_tick_durable_v2()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,public,penta_self
as $$
declare v_fence jsonb; v_cron jsonb;
begin
  perform public.penta_self_tick_v1();
  v_fence:=penta_self.enforce_resolution_fences_v2();
  v_cron:=penta_self.reconcile_required_crons_v2();
  return jsonb_build_object(
    'status','completed',
    'base_tick','public.penta_self_tick_v1',
    'resolution_fences',v_fence,
    'cron_permanence',v_cron,
    'rollback_policy','failed_verification_or_founder_explicit_only',
    'successful_repair_monotonic',true,
    'at',now()
  );
end $$;

create or replace function public.penta_self_continuous_healing_tick_durable_v2()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,public,penta_self
as $$
declare v_fence jsonb; v_cron jsonb;
begin
  perform public.penta_self_continuous_healing_tick_v1();
  v_fence:=penta_self.enforce_resolution_fences_v2();
  v_cron:=penta_self.reconcile_required_crons_v2();
  return jsonb_build_object(
    'status','completed',
    'base_tick','public.penta_self_continuous_healing_tick_v1',
    'resolution_fences',v_fence,
    'cron_permanence',v_cron,
    'rollback_policy','failed_verification_or_founder_explicit_only',
    'successful_repair_monotonic',true,
    'at',now()
  );
end $$;

create or replace function public.penta_self_permanence_guard_v2()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_self,public
as $$
begin
  return jsonb_build_object(
    'cron',penta_self.reconcile_required_crons_v2(),
    'fences',penta_self.enforce_resolution_fences_v2(),
    'successful_repair_monotonic',true,
    'unknown_newer_change_policy','HOLD_NOT_OVERWRITE',
    'at',now()
  );
end $$;

revoke all on function public.penta_self_tick_durable_v2() from public,anon,authenticated;
revoke all on function public.penta_self_continuous_healing_tick_durable_v2() from public,anon,authenticated;
revoke all on function public.penta_self_permanence_guard_v2() from public,anon,authenticated;
grant execute on function public.penta_self_tick_durable_v2() to service_role;
grant execute on function public.penta_self_continuous_healing_tick_durable_v2() to service_role;
grant execute on function public.penta_self_permanence_guard_v2() to service_role;

insert into penta_self.required_cron_baseline_v2(
  jobname,schedule,command,generation,enforcement_mode,enabled,
  command_sha256,verified_at,metadata
)
select
  jobname,schedule,command,1,'restore_missing_only',true,
  encode(extensions.digest((schedule||E'\n'||command)::text,'sha256'),'hex'),
  now(),
  jsonb_build_object(
    'captured_from_live_cron',true,
    'rollback_policy','do_not_overwrite_unknown_newer_configuration'
  )
from cron.job
where active=true
on conflict(jobname) do nothing;

insert into penta_self.required_cron_baseline_v2(
  jobname,schedule,command,generation,enforcement_mode,enabled,
  command_sha256,verified_at,metadata
) values
(
  'ct-penta-self-v1','*/2 * * * *',
  'select public.penta_self_tick_durable_v2();',2,'enforce_known_superseded',true,
  encode(extensions.digest(('*/2 * * * *'||E'\n'||'select public.penta_self_tick_durable_v2();')::text,'sha256'),'hex'),
  now(),jsonb_build_object('permanent',true,'successful_repair_monotonic',true)
),
(
  'ct-penta-self-continuous-healing-v1','1-59/2 * * * *',
  'select public.penta_self_continuous_healing_tick_durable_v2();',2,'enforce_known_superseded',true,
  encode(extensions.digest(('1-59/2 * * * *'||E'\n'||'select public.penta_self_continuous_healing_tick_durable_v2();')::text,'sha256'),'hex'),
  now(),jsonb_build_object('permanent',true,'successful_repair_monotonic',true)
),
(
  'ct-penta-self-permanence-v2','* * * * *',
  'select public.penta_self_permanence_guard_v2();',1,'enforce_known_superseded',true,
  encode(extensions.digest(('* * * * *'||E'\n'||'select public.penta_self_permanence_guard_v2();')::text,'sha256'),'hex'),
  now(),jsonb_build_object('redundancy_lane','primary')
),
(
  'ct-penta-self-permanence-watch-v2','2-59/5 * * * *',
  'select public.penta_self_permanence_guard_v2();',1,'enforce_known_superseded',true,
  encode(extensions.digest(('2-59/5 * * * *'||E'\n'||'select public.penta_self_permanence_guard_v2();')::text,'sha256'),'hex'),
  now(),jsonb_build_object('redundancy_lane','watch')
)
on conflict(jobname) do update set
  schedule=excluded.schedule,
  command=excluded.command,
  generation=excluded.generation,
  enforcement_mode=excluded.enforcement_mode,
  enabled=excluded.enabled,
  command_sha256=excluded.command_sha256,
  verified_at=excluded.verified_at,
  metadata=penta_self.required_cron_baseline_v2.metadata||excluded.metadata,
  updated_at=now();

insert into penta_self.required_cron_versions_v2(
  jobname,command_sha256,disposition,generation,command
) values
(
  'ct-penta-self-v1',
  encode(extensions.digest(('*/2 * * * *'||E'\n'||'select public.penta_self_tick_v1();')::text,'sha256'),'hex'),
  'superseded',1,'select public.penta_self_tick_v1();'
),
(
  'ct-penta-self-v1',
  encode(extensions.digest(('*/2 * * * *'||E'\n'||'select public.penta_self_tick_durable_v2();')::text,'sha256'),'hex'),
  'current',2,'select public.penta_self_tick_durable_v2();'
),
(
  'ct-penta-self-continuous-healing-v1',
  encode(extensions.digest(('1-59/2 * * * *'||E'\n'||'select public.penta_self_continuous_healing_tick_v1();')::text,'sha256'),'hex'),
  'superseded',1,'select public.penta_self_continuous_healing_tick_v1();'
),
(
  'ct-penta-self-continuous-healing-v1',
  encode(extensions.digest(('1-59/2 * * * *'||E'\n'||'select public.penta_self_continuous_healing_tick_durable_v2();')::text,'sha256'),'hex'),
  'current',2,'select public.penta_self_continuous_healing_tick_durable_v2();'
)
on conflict(jobname,command_sha256) do update set
  disposition=excluded.disposition,
  generation=excluded.generation,
  command=excluded.command;

select cron.unschedule(jobid)
from cron.job
where jobname in ('ct-penta-self-v1','ct-penta-self-continuous-healing-v1','ct-penta-self-permanence-v2','ct-penta-self-permanence-watch-v2');

select cron.schedule('ct-penta-self-v1','*/2 * * * *','select public.penta_self_tick_durable_v2();');
select cron.schedule('ct-penta-self-continuous-healing-v1','1-59/2 * * * *','select public.penta_self_continuous_healing_tick_durable_v2();');
select cron.schedule('ct-penta-self-permanence-v2','* * * * *','select public.penta_self_permanence_guard_v2();');
select cron.schedule('ct-penta-self-permanence-watch-v2','2-59/5 * * * *','select public.penta_self_permanence_guard_v2();');

select penta_self.reconcile_required_crons_v2();
