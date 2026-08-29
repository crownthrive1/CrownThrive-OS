-- Converge duplicate hourly founder reports into one reserved PentaSELF healing report.
-- Preserve the governed 10/hour Mailgun ceiling and one reserved founder-report slot.

create or replace function public.penta_mail_reserve_mailgun_rate_v2(p_request_key text,p_trigger_ref text)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','public','integration_control'
as $$
declare
  v_status jsonb;
  v_batch_count integer;
  v_batch_oldest timestamptz;
  v_hour_count integer;
  v_hour_oldest timestamptz;
  v_is_founder_report boolean := coalesce(p_trigger_ref,'') in (
    'scheduled:penta-mail-state-architecture-report-v1',
    'penta-self-hourly-healing-v1'
  );
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  v_status:=public.penta_mail_provider_status_v1(p_trigger_ref);
  select count(*)::integer,min(reserved_at) into v_hour_count,v_hour_oldest
  from integration_control.penta_mail_rate_reservations_v1
  where provider_route_id='mailgun:relay.crownthrive.com' and reserved_at>clock_timestamp()-interval '1 hour';

  if not v_is_founder_report and v_hour_count>=9 then
    return jsonb_build_object('allowed',false,'reason','founder_report_capacity_reserved','window_count',v_hour_count,
      'rolling_hour_limit',10,'reserved_founder_report_slots',1,
      'retry_at',coalesce(v_hour_oldest+interval '1 hour',clock_timestamp()+interval '5 minutes'),'control',v_status);
  end if;

  if v_status->>'route_state'='controlled_release' then
    select count(*)::integer,min(reserved_at) into v_batch_count,v_batch_oldest
    from integration_control.penta_mail_rate_reservations_v1
    where provider_route_id='mailgun:relay.crownthrive.com' and reserved_at>clock_timestamp()-interval '1 minute';
    if v_batch_count>=2 then
      return jsonb_build_object('allowed',false,'reason','controlled_release_batch_limit','window_count',v_batch_count,
        'controlled_batch_size',2,'retry_at',v_batch_oldest+interval '1 minute','control',v_status);
    end if;
  end if;
  return public.penta_mail_reserve_mailgun_rate_v1(p_request_key,p_trigger_ref);
end $$;

create or replace function public.penta_hourly_update_enforce_v1()
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','public','integration_control','cron','extensions'
as $$
declare
  p integration_control.penta_hourly_update_policy_v1%rowtype;
  j record;
  v_action text:='verified';
  v_jobid bigint;
  v_prev text;
  v_payload jsonb;
  v_chain text;
  v_command constant text:='select public.penta_self_hourly_report_v1();';
begin
  select * into p from integration_control.penta_hourly_update_policy_v1 where enabled=true order by effective_at desc,created_at desc limit 1;
  if not found then raise exception 'PENTA_HOURLY_POLICY_MISSING'; end if;
  select jobid,jobname,schedule,active,command into j from cron.job where jobname='penta-mail-state-architecture-hourly-v1' limit 1;
  if not found then
    v_jobid:=cron.schedule('penta-mail-state-architecture-hourly-v1',p.cron_expression,v_command);
    v_action:='recreated_as_pentaself_healing_report';
  else
    v_jobid:=j.jobid;
    if j.schedule is distinct from p.cron_expression or j.active is distinct from true or j.command is distinct from v_command then
      perform cron.alter_job(j.jobid,schedule=>p.cron_expression,command=>v_command,active=>true);
      v_action:='repaired_as_pentaself_healing_report';
    end if;
  end if;
  select chain_sha256 into v_prev from integration_control.penta_hourly_update_receipts_v1 order by created_at desc,receipt_id desc limit 1;
  v_payload:=jsonb_build_object('policy_version',p.policy_version,'cron_expression',p.cron_expression,'recipient',p.recipient,
    'job_id',v_jobid,'action',v_action,'mandatory',p.mandatory,'report_contract','ct.penta.self.hourly-healing-report.v1',
    'single_founder_report_lane',true,'authority_expansion',false);
  v_chain:=encode(extensions.digest(convert_to(coalesce(v_prev,'GENESIS')||'|policy_enforcement|'||v_payload::text||'|'||clock_timestamp()::text,'UTF8'),'sha256'),'hex');
  insert into integration_control.penta_hourly_update_receipts_v1(event_kind,source_pentas,recipient,payload,previous_chain_sha256,chain_sha256)
  values('policy_enforcement',jsonb_build_array('PentaSELF','PentaStatus','PentaNurture','PentaMail'),p.recipient,v_payload,v_prev,v_chain);
  return jsonb_build_object('ok',true,'action',v_action,'job_id',v_jobid,'policy_version',p.policy_version,
    'cron_expression',p.cron_expression,'recipient',p.recipient,'report_contract','ct.penta.self.hourly-healing-report.v1',
    'single_founder_report_lane',true,'append_only',true,'authority_expansion',false,'observed_at',clock_timestamp());
end $$;

update penta_self.continuity_policy_v1
set hourly_report_schedule='0 * * * *',metadata=metadata||jsonb_build_object('single_founder_report_lane',true,'hourly_jobname','penta-mail-state-architecture-hourly-v1'),updated_at=now()
where policy_key='ct.penta.self.continuous-healing.v1';

delete from penta_self.required_jobs_v1 where jobname='penta-self-healing-hourly-v1';

insert into penta_self.required_jobs_v1(jobname,expected_schedule,expected_command,auto_repair,risk_class,metadata)
values('penta-mail-state-architecture-hourly-v1','0 * * * *','select public.penta_self_hourly_report_v1();',true,'D1',
  jsonb_build_object('owner','PentaSELF/PentaMail','recipient','jones.usmc.kj@gmail.com','mandatory',true,
    'single_founder_report_lane',true,'report_contract','ct.penta.self.hourly-healing-report.v1'))
on conflict(jobname) do update set expected_schedule=excluded.expected_schedule,expected_command=excluded.expected_command,
  auto_repair=true,risk_class='D1',metadata=penta_self.required_jobs_v1.metadata||excluded.metadata,updated_at=now();

do $$
declare v_jobid bigint;
begin
  select jobid into v_jobid from cron.job where jobname='penta-self-healing-hourly-v1' limit 1;
  if v_jobid is not null then perform cron.unschedule(v_jobid); end if;
  perform public.penta_hourly_update_enforce_v1();
end $$;
