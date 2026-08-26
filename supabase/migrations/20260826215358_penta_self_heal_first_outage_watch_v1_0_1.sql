create or replace function public.penta_mail_outage_watch_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public'
as $function$
declare
  s jsonb;
  h jsonb;
  private_state jsonb;
  green jsonb;
  v_heal_attempt jsonb := '{}'::jsonb;
  v_pre_scheduler_gaps integer := 0;
  v_post_scheduler_gaps integer := 0;
  r record;
  v_prev_active boolean;
  v_prev_fp text;
  v_prev_notified timestamptz;
  v_notify boolean;
  v_enqueued integer := 0;
  v_resolved integer := 0;
begin
  s := public.penta_self_status_v1();
  h := coalesce(s->'health','{}'::jsonb);
  v_pre_scheduler_gaps := coalesce((h->>'scheduler_gaps')::integer,0);

  -- Heal first, then independently re-read. Persistent gaps still fail closed and alert.
  if v_pre_scheduler_gaps > 0 then
    begin
      v_heal_attempt := public.penta_self_tick_v1();
    exception when others then
      v_heal_attempt := jsonb_build_object(
        'state','FAILED',
        'sqlstate',sqlstate,
        'error',left(sqlerrm,300),
        'at',clock_timestamp()
      );
    end;
    s := public.penta_self_status_v1();
    h := coalesce(s->'health','{}'::jsonb);
  else
    v_heal_attempt := jsonb_build_object('state','NOT_NEEDED','at',clock_timestamp());
  end if;

  v_post_scheduler_gaps := coalesce((h->>'scheduler_gaps')::integer,0);
  private_state := public.penta_state_report_private_subsystems_v1();
  green := coalesce(private_state->'pentagreen','{}'::jsonb);

  create temporary table if not exists pg_temp.penta_mail_conditions(
    condition_key text,
    active boolean,
    severity text,
    fingerprint text,
    subject text,
    body_text text,
    details jsonb
  ) on commit drop;
  truncate pg_temp.penta_mail_conditions;

  insert into pg_temp.penta_mail_conditions values
   (
     'scheduler_gap',
     v_post_scheduler_gaps > 0,
     'CRITICAL',
     md5(v_post_scheduler_gaps::text||':'||coalesce(v_heal_attempt->>'state','unknown')),
     'PentaMail Alert: Scheduler Gap',
     'State Architecture outage watcher detected a scheduler gap and invoked PentaSELF bounded reconciliation before notification. Initial gap count: '
       ||v_pre_scheduler_gaps::text||'. Remaining gap count after reconciliation/readback: '
       ||v_post_scheduler_gaps::text||'. Persistent gaps remain fail-closed; inspect the State Architecture Report for full evidence.',
     jsonb_build_object(
       'pre_reconcile_scheduler_gaps',v_pre_scheduler_gaps,
       'scheduler_gaps',v_post_scheduler_gaps,
       'heal_first',true,
       'heal_attempt',v_heal_attempt
     )
   ),
   ('required_job_failure',coalesce((h->>'unrecovered_required_job_failures_30m')::int,0)>0,'CRITICAL',md5(coalesce(h->>'unrecovered_required_job_failures_30m','0')),'PentaMail Alert: Required Job Failure','PentaSELF detected unrecovered required-job failures in the last 30 minutes: '||coalesce(h->>'unrecovered_required_job_failures_30m','0')||'.',jsonb_build_object('count',coalesce((h->>'unrecovered_required_job_failures_30m')::int,0))),
   ('authority_manufacture',coalesce((h->>'authority_manufacture')::boolean,false),'CRITICAL',md5(coalesce(h->>'authority_manufacture','false')),'PentaMail Alert: Authority Guardrail','Authority-manufacture guardrail reported true. Automated authority expansion must remain blocked pending human governance.',jsonb_build_object('authority_manufacture',coalesce((h->>'authority_manufacture')::boolean,false))),
   ('certification_plane_degraded',coalesce((h->>'failed_certification_tasks')::int,0)>0,'HIGH',md5(coalesce(h->>'failed_certification_tasks','0')||coalesce((h->'provider_certification_queue')::text,'')),'PentaMail Alert: Certification Plane Degraded','PentaSELF reports failed provider-certification tasks: '||coalesce(h->>'failed_certification_tasks','0')||'. Core runtime may remain operational while provider promotions stay fail-closed.',jsonb_build_object('failed_certification_tasks',coalesce((h->>'failed_certification_tasks')::int,0),'queue',h->'provider_certification_queue')),
   ('pentagreen_execution_failed',coalesce(green->>'run_state','')='failed','HIGH',md5(coalesce(green->>'run_id','none')||':'||coalesce(green->>'error_code','none')),'PentaMail Alert: PentaGreen Execution Failed','PentaGreen latest hourly execution is failed/HOLD. Error code: '||coalesce(green->>'error_code','unknown')||'. Publication count: '||coalesce(green->>'publication_count','0')||'. Economic activation remains held pending successful governed execution.',jsonb_build_object('run_id',green->>'run_id','error_code',green->>'error_code','economic_verdict',green->>'economic_verdict','publication_decision',green->>'publication_decision','publication_count',green->>'publication_count'));

  for r in select * from pg_temp.penta_mail_conditions loop
    select active,fingerprint,last_notified_at
      into v_prev_active,v_prev_fp,v_prev_notified
    from public.penta_mail_incident_state_v1
    where condition_key=r.condition_key;

    if r.active then
      v_notify := coalesce(v_prev_active,false)=false
        or v_prev_fp is distinct from r.fingerprint
        or v_prev_notified is null
        or v_prev_notified < now()-interval '1 hour';

      insert into public.penta_mail_incident_state_v1(
        condition_key,active,fingerprint,severity,first_seen_at,last_seen_at,details,updated_at
      ) values(
        r.condition_key,true,r.fingerprint,r.severity,now(),now(),r.details,now()
      )
      on conflict(condition_key) do update set
        active=true,
        fingerprint=excluded.fingerprint,
        severity=excluded.severity,
        first_seen_at=coalesce(public.penta_mail_incident_state_v1.first_seen_at,excluded.first_seen_at),
        last_seen_at=now(),
        details=excluded.details,
        updated_at=now();

      if v_notify then
        perform public.penta_mail_enqueue_v1(
          'outage',r.severity,r.subject,r.body_text,
          'incident:'||r.condition_key||':'||r.fingerprint||':'||to_char(date_trunc('hour',now()),'YYYYMMDDHH24'),
          jsonb_build_object('condition_key',r.condition_key,'details',r.details)
        );
        update public.penta_mail_incident_state_v1
          set last_notified_at=now()
        where condition_key=r.condition_key;
        v_enqueued := v_enqueued+1;
      end if;
    elsif coalesce(v_prev_active,false)=true then
      perform public.penta_mail_enqueue_v1(
        'recovery','INFO','PentaMail Recovery: '||replace(r.condition_key,'_',' '),
        'Previously active condition '||r.condition_key||' is now resolved according to current PentaSELF/runtime evidence.',
        'recovery:'||r.condition_key||':'||to_char(now(),'YYYYMMDDHH24MI'),
        jsonb_build_object('condition_key',r.condition_key,'details',r.details)
      );
      update public.penta_mail_incident_state_v1
        set active=false,last_seen_at=now(),last_resolved_at=now(),details=r.details,updated_at=now()
      where condition_key=r.condition_key;
      v_resolved := v_resolved+1;
    else
      insert into public.penta_mail_incident_state_v1(
        condition_key,active,fingerprint,severity,last_seen_at,details,updated_at
      ) values(
        r.condition_key,false,r.fingerprint,r.severity,now(),r.details,now()
      )
      on conflict(condition_key) do update set
        last_seen_at=now(),details=excluded.details,updated_at=now();
    end if;
  end loop;

  return jsonb_build_object(
    'service','ct.penta.mail.outage-watch.v1.1.0',
    'heal_first',true,
    'pre_scheduler_gaps',v_pre_scheduler_gaps,
    'post_scheduler_gaps',v_post_scheduler_gaps,
    'heal_attempt',v_heal_attempt,
    'enqueued',v_enqueued,
    'resolved',v_resolved,
    'at',now()
  );
end
$function$;

-- Stagger the outage watcher away from the even-minute PentaSELF cadence to reduce lock/race collisions.
do $block$
declare v_jobid bigint;
begin
  select jobid into v_jobid from cron.job where jobname='penta-mail-outage-watch-v1' order by jobid desc limit 1;
  if v_jobid is null then
    perform cron.schedule(
      'penta-mail-outage-watch-v1',
      '1-55/6 * * * *',
      'select public.penta_mail_outage_watch_v1();'
    );
  else
    perform cron.alter_job(
      v_jobid,
      schedule => '1-55/6 * * * *',
      command => 'select public.penta_mail_outage_watch_v1();',
      active => true
    );
  end if;
end
$block$;

-- Make the watcher itself part of PentaSELF's owned/repairable scheduler contract.
insert into penta_self.required_jobs_v1(
  jobname,expected_schedule,expected_command,auto_repair,risk_class,metadata,updated_at
) values(
  'penta-mail-outage-watch-v1',
  '1-55/6 * * * *',
  'select public.penta_mail_outage_watch_v1();',
  true,
  'D1',
  jsonb_build_object(
    'owner','PentaSELF',
    'system','PentaMail',
    'purpose','heal_first_state_architecture_outage_watch',
    'staggered_from_pentaself',true
  ),
  now()
)
on conflict(jobname) do update set
  expected_schedule=excluded.expected_schedule,
  expected_command=excluded.expected_command,
  auto_repair=true,
  risk_class='D1',
  metadata=penta_self.required_jobs_v1.metadata||excluded.metadata,
  updated_at=now();

update public.penta_system_registry
set version='1.0.1',
    metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
      'heal_first_outage_watch',true,
      'outage_watcher_required_job',true,
      'outage_watcher_schedule','1-55/6 * * * *',
      'persistent_scheduler_gap_fail_closed',true,
      'updated_at',now()
    ),
    last_verified_at=now(),updated_at=now()
where system_key='penta.self';

update public.penta_system_registry
set version='1.1.0',
    metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
      'heal_first_scheduler_gap_alerting',true,
      'scheduler_gap_recheck_after_pentaself',true,
      'outage_watcher_schedule','1-55/6 * * * *',
      'updated_at',now()
    ),
    last_verified_at=now(),updated_at=now()
where system_key='ct.penta.mail.v1';
