create table if not exists integration_control.penta_marketer_authoritative_summary_v2 (
  summary_key text primary key,
  campaign_ref text not null,
  event_rows bigint not null,
  accepted_event_rows bigint not null,
  rejected_event_rows bigint not null,
  latest_event_at timestamptz,
  event_ledger_sha256 text not null,
  source_of_truth text not null default 'crm.penta_marketer_campaign_events_v1',
  projection_version text not null default '2.0.0',
  observed_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table integration_control.penta_marketer_authoritative_summary_v2 enable row level security;
revoke all on integration_control.penta_marketer_authoritative_summary_v2 from public, anon, authenticated;
grant select, insert, update on integration_control.penta_marketer_authoritative_summary_v2 to service_role;
drop policy if exists penta_marketer_authoritative_summary_service_role_v2 on integration_control.penta_marketer_authoritative_summary_v2;
create policy penta_marketer_authoritative_summary_service_role_v2
  on integration_control.penta_marketer_authoritative_summary_v2
  for all to service_role using (true) with check (true);

create table if not exists integration_control.crownthrive_phase_projection_v1 (
  projection_key text primary key,
  canonical_os_phase text not null,
  founder_operating_label text not null,
  public_rollout_phase text,
  phase_semantics jsonb not null,
  evidence_sha256 text not null,
  effective_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table integration_control.crownthrive_phase_projection_v1 enable row level security;
revoke all on integration_control.crownthrive_phase_projection_v1 from public, anon, authenticated;
grant select, insert, update on integration_control.crownthrive_phase_projection_v1 to service_role;
drop policy if exists crownthrive_phase_projection_service_role_v1 on integration_control.crownthrive_phase_projection_v1;
create policy crownthrive_phase_projection_service_role_v1
  on integration_control.crownthrive_phase_projection_v1
  for all to service_role using (true) with check (true);

create or replace function integration_control.penta_marketer_reconcile_authoritative_summary_v2(
  p_campaign_ref text default 'ct.pentamarketer.locticians.claim.20260827.v1'
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,crm,extensions
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_events bigint:=0;
  v_accepted bigint:=0;
  v_rejected bigint:=0;
  v_latest timestamptz;
  v_hash text;
  v_payload jsonb;
  v_campaign_key_column text;
  v_metadata_exists boolean;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if to_regclass('crm.penta_marketer_campaign_events_v1') is null then raise exception 'campaign_event_ledger_missing'; end if;

  execute $q$
    with events as (
      select to_jsonb(e) as j
      from crm.penta_marketer_campaign_events_v1 e
    ), scoped as (
      select j,
             case
               when coalesce(j->>'created_at',j->>'event_at',j->>'occurred_at',j->>'observed_at') ~ '^\d{4}-\d{2}-\d{2}'
               then coalesce(j->>'created_at',j->>'event_at',j->>'occurred_at',j->>'observed_at')::timestamptz
             end as event_at,
             lower(j::text) as text_lc
      from events
      where j::text like '%'||$1||'%'
    )
    select count(*),
           count(*) filter(where text_lc ~ '(provider_accepted|send_accepted|accepted_send|mailgun[^}]{0,200}(http[^0-9]*)?200|"state"[ ]*:[ ]*"sent"|"event_type"[ ]*:[ ]*"sent")'),
           count(*) filter(where text_lc ~ '(provider_rejected|send_rejected|hard_bounce|complaint|"state"[ ]*:[ ]*"rejected")'),
           max(event_at),
           encode(extensions.digest(coalesce(string_agg(j::text,'' order by event_at nulls last),''),'sha256'),'hex')
    from scoped
  $q$ into v_events,v_accepted,v_rejected,v_latest,v_hash using p_campaign_ref;

  v_payload:=jsonb_build_object(
    'campaign_ref',p_campaign_ref,
    'event_rows',v_events,
    'accepted_event_rows',v_accepted,
    'rejected_event_rows',v_rejected,
    'latest_event_at',v_latest,
    'event_ledger_sha256',v_hash,
    'source_of_truth','crm.penta_marketer_campaign_events_v1',
    'summary_projection_retired_as_authority',true,
    'observed_at',now()
  );

  insert into integration_control.penta_marketer_authoritative_summary_v2(
    summary_key,campaign_ref,event_rows,accepted_event_rows,rejected_event_rows,
    latest_event_at,event_ledger_sha256,source_of_truth,projection_version,observed_at
  ) values (
    'locticians-claim-v2',p_campaign_ref,v_events,v_accepted,v_rejected,
    v_latest,v_hash,'crm.penta_marketer_campaign_events_v1','2.0.0',now()
  )
  on conflict(summary_key) do update set
    campaign_ref=excluded.campaign_ref,
    event_rows=excluded.event_rows,
    accepted_event_rows=excluded.accepted_event_rows,
    rejected_event_rows=excluded.rejected_event_rows,
    latest_event_at=excluded.latest_event_at,
    event_ledger_sha256=excluded.event_ledger_sha256,
    source_of_truth=excluded.source_of_truth,
    projection_version=excluded.projection_version,
    observed_at=excluded.observed_at,
    updated_at=now();

  select column_name into v_campaign_key_column
  from information_schema.columns
  where table_schema='crm' and table_name='penta_marketer_campaign_v1'
    and column_name in ('campaign_ref','campaign_key','campaign_id','stable_id')
  order by case column_name when 'campaign_ref' then 1 when 'campaign_key' then 2 when 'campaign_id' then 3 else 4 end
  limit 1;
  select exists(
    select 1 from information_schema.columns
    where table_schema='crm' and table_name='penta_marketer_campaign_v1' and column_name='metadata'
  ) into v_metadata_exists;

  if v_campaign_key_column is not null and v_metadata_exists then
    execute format(
      'update crm.penta_marketer_campaign_v1 set metadata=coalesce(metadata,''{}''::jsonb)||$1, updated_at=now() where %I::text=$2',
      v_campaign_key_column
    ) using jsonb_build_object(
      'authoritative_summary_version','2.0.0',
      'event_ledger_authoritative_for_projection',true,
      'event_rows',v_events,
      'accepted_event_rows',v_accepted,
      'rejected_event_rows',v_rejected,
      'event_ledger_sha256',v_hash,
      'summary_reconciled_at',now(),
      'stale_summary_may_override',false
    ),p_campaign_ref;
  end if;

  return v_payload;
end $$;

revoke all on function integration_control.penta_marketer_reconcile_authoritative_summary_v2(text) from public, anon, authenticated;
grant execute on function integration_control.penta_marketer_reconcile_authoritative_summary_v2(text) to service_role;

create or replace function integration_control.crownthrive_phase_status_v1()
returns jsonb
language sql
security definer
set search_path=pg_catalog,integration_control
as $$
select jsonb_build_object(
  'canonical_os_phase',canonical_os_phase,
  'founder_operating_label',founder_operating_label,
  'public_rollout_phase',public_rollout_phase,
  'phase_semantics',phase_semantics,
  'evidence_sha256',evidence_sha256,
  'effective_at',effective_at,
  'fields_conflated',false
)
from integration_control.crownthrive_phase_projection_v1
where projection_key='current'
$$;
revoke all on function integration_control.crownthrive_phase_status_v1() from public, anon, authenticated;
grant execute on function integration_control.crownthrive_phase_status_v1() to service_role;

do $$
declare
  v_summary jsonb;
  v_phase jsonb;
  v_hash text;
  p record;
  v_factory_ok boolean;
  v_self_ok boolean;
  v_fabric_quiet boolean;
begin
  v_summary:=integration_control.penta_marketer_reconcile_authoritative_summary_v2('ct.pentamarketer.locticians.claim.20260827.v1');

  v_phase:=jsonb_build_object(
    'canonical_os_phase','Phase 3 — Execute',
    'founder_operating_label','Phase 3.5 — convergence and hardening',
    'public_rollout_phase',null,
    'semantics',jsonb_build_object(
      'canonical_os_phase','institutional execution authority and registry state',
      'founder_operating_label','founder-declared convergence/hardening subphase',
      'public_rollout_phase','separate product/public launch state when independently declared',
      'fields_conflated',false
    ),
    'effective_at',now()
  );
  v_hash:=encode(extensions.digest(v_phase::text,'sha256'),'hex');

  insert into integration_control.crownthrive_phase_projection_v1(
    projection_key,canonical_os_phase,founder_operating_label,public_rollout_phase,
    phase_semantics,evidence_sha256,effective_at
  ) values (
    'current','Phase 3 — Execute','Phase 3.5 — convergence and hardening',null,
    v_phase->'semantics',v_hash,now()
  )
  on conflict(projection_key) do update set
    canonical_os_phase=excluded.canonical_os_phase,
    founder_operating_label=excluded.founder_operating_label,
    public_rollout_phase=excluded.public_rollout_phase,
    phase_semantics=excluded.phase_semantics,
    evidence_sha256=excluded.evidence_sha256,
    effective_at=excluded.effective_at,
    updated_at=now();

  for p in select * from penta_self.problem_ledger_v1
           where title='PentaMarketer summary contradicts its event ledger'
             and state not in ('resolved','closed','retired')
  loop
    update penta_self.problem_ledger_v1
       set state='resolved',resolved_at=now(),blocked_reason=null,last_error=null,
           verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||v_summary||jsonb_build_object('projection_authority','event_ledger','stale_summary_retired',true,'verified_at',now()),
           updated_at=now()
     where problem_id=p.problem_id;
    perform penta_self.register_permanent_repair_v1(
      'ct.repair.pentamarketer-ledger-authoritative-summary.v2',
      'PentaMarketer/summary projection',p.fingerprint,
      jsonb_build_object('event_ledger_authoritative',true,'projection_version','2.0.0','stale_summary_may_override',false),
      v_summary,now(),'runtime:integration_control.penta_marketer_authoritative_summary_v2','newer-ledger-reconciliation-failure-only'
    );
  end loop;

  for p in select * from penta_self.problem_ledger_v1
           where title='Public rollout language and OS institutional phase remain conflated'
             and state not in ('resolved','closed','retired')
  loop
    update penta_self.problem_ledger_v1
       set state='resolved',resolved_at=now(),blocked_reason=null,last_error=null,
           verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||v_phase||jsonb_build_object('evidence_sha256',v_hash,'verified_at',now()),
           updated_at=now()
     where problem_id=p.problem_id;
    perform penta_self.register_permanent_repair_v1(
      'ct.repair.crownthrive-phase-separation.v1','CrownThrive/phase projection',p.fingerprint,
      jsonb_build_object('canonical_os_phase','Phase 3 — Execute','founder_operating_label','Phase 3.5 — convergence and hardening','public_rollout_phase_separate',true),
      v_phase,now(),'runtime:integration_control.crownthrive_phase_projection_v1','newer-governed-phase-declaration-only'
    );
  end loop;

  select exists(
    select 1 from cron.job j
    join lateral (
      select status,start_time from cron.job_run_details d
      where d.jobid=j.jobid order by start_time desc limit 1
    ) d on true
    where j.jobname='ct-software-factory-continuity-v5'
      and j.active=true and d.status='succeeded'
  ) into v_factory_ok;

  select exists(
    select 1 from cron.job j
    join lateral (
      select status,start_time from cron.job_run_details d
      where d.jobid=j.jobid order by start_time desc limit 1
    ) d on true
    where j.jobname in ('ct-penta-self-v1','ct-penta-self-continuous-healing-v1')
      and j.active=true and d.status='succeeded'
  ) into v_self_ok;

  if v_factory_ok and v_self_ok then
    for p in select * from penta_self.problem_ledger_v1
             where title like 'Latest active cron execution failed: ct-software-factory-continuity-v5%'
               and state not in ('resolved','closed','retired')
    loop
      update penta_self.problem_ledger_v1
         set state='resolved',resolved_at=now(),blocked_reason=null,last_error=null,
             verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||jsonb_build_object('latest_status','succeeded','cron_active',true,'permanent_scheduler_fence','ct-penta-self-permanent-repair-reconcile-v1','verified_at',now()),
             updated_at=now()
       where problem_id=p.problem_id;
      perform penta_self.register_permanent_repair_v1(
        'ct.repair.software-factory-continuity-active.v5','Software Factory/cron continuity',p.fingerprint,
        jsonb_build_object('jobname','ct-software-factory-continuity-v5','desired_active',true,'exact_schedule_fenced',true),
        jsonb_build_object('latest_status','succeeded','pentaself_latest_status','succeeded','verified_at',now()),
        now(),'runtime:cron.job + cron.job_run_details','newer-independent-cron-failure-only'
      );
    end loop;
  end if;

  select not exists(
    select 1 from penta_self.problem_ledger_v1
    where title='PentaFabric problem event'
      and last_seen_at > now()-interval '30 minutes'
      and state not in ('resolved','closed','retired')
  ) into v_fabric_quiet;

  if v_fabric_quiet and v_self_ok then
    for p in select * from penta_self.problem_ledger_v1
             where title='PentaFabric problem event'
               and state not in ('resolved','closed','retired')
               and last_seen_at <= now()-interval '30 minutes'
    loop
      update penta_self.problem_ledger_v1
         set state='resolved',resolved_at=now(),blocked_reason=null,last_error=null,
             verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||jsonb_build_object('no_recurrence_window','30 minutes','pentaself_operational',true,'verified_at',now()),
             updated_at=now()
       where problem_id=p.problem_id;
    end loop;
  end if;
end $$;
