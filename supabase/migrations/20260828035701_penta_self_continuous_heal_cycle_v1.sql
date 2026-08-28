create or replace function penta_self.problem_heal_cycle_v1(
  p_cycle_id uuid default gen_random_uuid(),
  p_limit integer default 20
) returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','penta_self','public','integration_control','penta_runtime','cron','extensions'
as $$
declare
  r record;
  h penta_self.problem_handler_registry_v1%rowtype;
  v_started timestamptz;
  v_result jsonb;
  v_result_state text;
  v_new_state text;
  v_error text;
  v_delay int;
  v_latest record;
  v_schedule text;
  v_command text;
  v_active boolean;
  v_success_after timestamptz;
  v_attempt_sha text;
  v_attempts int:=0;
  v_applied int:=0;
  v_verified int:=0;
  v_blocked int:=0;
  v_failed int:=0;
  v_delegated int:=0;
  v_now timestamptz:=clock_timestamp();
begin
  p_limit:=greatest(1,least(coalesce(p_limit,20),100));
  for r in
    select p.* from penta_self.problem_ledger_v1 p
    where p.state not in ('resolved','false_positive','retired') and p.next_attempt_at<=now()
    order by case p.priority when 'P0' then 0 when 'P1' then 1 when 'P2' then 2 else 3 end,p.first_seen_at
    limit p_limit for update skip locked
  loop
    v_attempts:=v_attempts+1; v_started:=clock_timestamp(); v_error:=null; v_result:='{}'::jsonb;
    select * into h from penta_self.problem_handler_registry_v1 where handler_key=r.handler_key and enabled;
    if not found then
      v_result_state:='blocked'; v_new_state:='blocked_external'; v_error:='HANDLER_MISSING_OR_DISABLED'; v_blocked:=v_blocked+1; v_delay:=3600;
    elsif r.authority_class='D3' or h.action_mode='d3_reserved' then
      v_result_state:='blocked'; v_new_state:='blocked_d3'; v_error:='D3_HUMAN_RESERVED'; v_blocked:=v_blocked+1; v_delay:=least(h.retry_max_seconds,greatest(h.retry_base_seconds,3600));
      v_result:=jsonb_build_object('state','blocked_d3','d3_human_reserved',true,'authority_manufactured',false);
    elsif not r.auto_heal_allowed then
      v_result_state:='blocked'; v_new_state:='blocked_external'; v_error:='AUTO_HEAL_NOT_ALLOWED'; v_blocked:=v_blocked+1; v_delay:=h.retry_max_seconds;
    else
      begin
        update penta_self.problem_ledger_v1 set state='healing',last_attempt_at=v_started,attempt_count=attempt_count+1,updated_at=now() where problem_id=r.problem_id;

        case r.handler_key
          when 'repair.commercial_packager_schedule.v1' then
            select schedule,command,active into v_schedule,v_command,v_active from cron.job where jobname='crownthrive_commercial_release_packager_hourly' limit 1;
            if v_command is null then
              v_result_state:='blocked'; v_new_state:='blocked_external'; v_error:='COMMERCIAL_PACKAGER_CRON_MISSING'; v_blocked:=v_blocked+1; v_delay:=600;
            else
              if v_schedule is distinct from '33 * * * *' or coalesce(v_active,false)=false then
                perform cron.alter_job((select jobid from cron.job where jobname='crownthrive_commercial_release_packager_hourly' limit 1),schedule=>'33 * * * *',command=>v_command,active=>true);
                update penta_self.problem_ledger_v1 set evidence=evidence||jsonb_build_object('schedule_repaired_at',clock_timestamp(),'prior_schedule',v_schedule,'new_schedule','33 * * * *') where problem_id=r.problem_id;
              end if;
              insert into penta_self.required_jobs_v1(jobname,expected_schedule,expected_command,auto_repair,risk_class,metadata)
              values('crownthrive_commercial_release_packager_hourly','33 * * * *',v_command,true,'D1',jsonb_build_object('owner','PentaSELF/PentaTime','reason','staggered from developer commerce reconciliation to prevent minute-27 deadlocks','authority_expansion',false))
              on conflict(jobname) do update set expected_schedule=excluded.expected_schedule,expected_command=excluded.expected_command,auto_repair=true,risk_class='D1',metadata=penta_self.required_jobs_v1.metadata||excluded.metadata,updated_at=now();
              select schedule,active into v_schedule,v_active from cron.job where jobname='crownthrive_commercial_release_packager_hourly' limit 1;
              select d.status,d.start_time,d.end_time into v_latest
              from cron.job j join cron.job_run_details d on d.jobid=j.jobid
              where j.jobname='crownthrive_commercial_release_packager_hourly'
              order by d.start_time desc limit 1;
              v_success_after:=coalesce((select nullif(evidence->>'schedule_repaired_at','')::timestamptz from penta_self.problem_ledger_v1 where problem_id=r.problem_id),v_started);
              if v_schedule='33 * * * *' and v_active and v_latest.status='succeeded' and v_latest.start_time>=v_success_after then
                v_result_state:='verified'; v_new_state:='resolved'; v_verified:=v_verified+1; v_delay:=3600;
              else
                v_result_state:='applied'; v_new_state:='verification'; v_applied:=v_applied+1; v_delay:=600;
              end if;
              v_result:=jsonb_build_object('schedule',v_schedule,'active',v_active,'latest_status',v_latest.status,'latest_started_at',v_latest.start_time,
                'verification_requires_success_after',v_success_after,'money_movement',false,'authority_expansion',false);
            end if;

          when 'recover.required_cron.v1' then
            v_result:=jsonb_build_object('scheduler',penta_self.scheduler_reconcile_v1(p_cycle_id),'recovery',penta_self.failed_job_recovery_v1(p_cycle_id));
            select d.status,d.start_time,d.end_time into v_latest from cron.job j join cron.job_run_details d on d.jobid=j.jobid
            where 'cron:'||j.jobname=r.source_ref order by d.start_time desc limit 1;
            if v_latest.status='succeeded' and v_latest.start_time>=r.last_seen_at then
              v_result_state:='verified'; v_new_state:='resolved'; v_verified:=v_verified+1; v_delay:=1800;
            else
              v_result_state:='applied'; v_new_state:='verification'; v_applied:=v_applied+1; v_delay:=300;
            end if;
            v_result:=v_result||jsonb_build_object('latest_status',v_latest.status,'latest_started_at',v_latest.start_time);

          when 'repair.pentaself_discovery.v1' then
            v_result:=public.ct_phase3_self_discovery_tick_v3();
            if coalesce(v_result->>'state','failed') not in ('failed','blocked') and not (v_result ? 'error') then
              v_result_state:='verified'; v_new_state:='resolved'; v_verified:=v_verified+1; v_delay:=1800;
            else
              v_result_state:='failed'; v_new_state:='verification'; v_failed:=v_failed+1; v_error:=left(coalesce(v_result->>'error','DISCOVERY_RETRY_NOT_VERIFIED'),300); v_delay:=300;
            end if;

          when 'repair.pentamail.v1' then
            v_result:=jsonb_build_object('outage_watch',public.penta_mail_outage_watch_v1(),'outbox',public.penta_mail_outbox_dispatch_v1());
            if not exists(select 1 from public.penta_mail_incident_state_v1 where active) then
              v_result_state:='verified'; v_new_state:='resolved'; v_verified:=v_verified+1; v_delay:=1800;
            else
              v_result_state:='applied'; v_new_state:='verification'; v_applied:=v_applied+1; v_delay:=300;
            end if;

          when 'reconcile.provider_evidence.v1' then
            v_result:=jsonb_build_object('evidence_bridge',integration_control.penta_certify_activate_control_evidence_v1(),'nurture',public.penta_nurture_tick_v1());
            v_result_state:='delegated'; v_new_state:='verification'; v_delegated:=v_delegated+1; v_delay:=900;

          when 'repair.software.via_pentabuild.v1' then
            v_result:=integration_control.penta_build_quality_sweep_v1();
            v_result_state:='delegated'; v_new_state:='verification'; v_delegated:=v_delegated+1; v_delay:=900;

          when 'reconcile.release.via_pentarelease.v1' then
            v_result:=jsonb_build_object('build_quality',integration_control.penta_build_quality_sweep_v1(),'route',integration_control.pentaroute_autonomy_cycle_v3(),
              'release_gate_bypassed',false,'verification_required','GitHub exact-head governed readback');
            v_result_state:='delegated'; v_new_state:='verification'; v_delegated:=v_delegated+1; v_delay:=900;

          when 'reconcile.projection.v1' then
            v_result:=jsonb_build_object('hourly_policy',public.penta_hourly_update_enforce_v1(),'status','delegated_to_PentaStatus_PentaScribe_PentaDocs');
            v_result_state:='delegated'; v_new_state:='verification'; v_delegated:=v_delegated+1; v_delay:=1800;

          when 'reconcile.source_custody.v1' then
            v_result:=jsonb_build_object('build_quality',integration_control.penta_build_quality_sweep_v1(),'status','source_custody_requires_ordered_repository_and_provider_replay_evidence');
            v_result_state:='delegated'; v_new_state:='verification'; v_delegated:=v_delegated+1; v_delay:=1800;

          when 'external.provider_recheck.v1' then
            if r.source_ref='thrivebase:stripe_event_receipts' and exists(select 1 from integration_control.stripe_event_receipts) then
              v_result_state:='verified'; v_new_state:='resolved'; v_verified:=v_verified+1; v_delay:=3600;
              v_result:=jsonb_build_object('stripe_event_receipts',(select count(*) from integration_control.stripe_event_receipts),'verified',true);
            elsif r.source_ref='thrivebase:paypal_webhook_receipts' and exists(select 1 from integration_control.paypal_webhook_receipts_v1) then
              v_result_state:='verified'; v_new_state:='resolved'; v_verified:=v_verified+1; v_delay:=3600;
              v_result:=jsonb_build_object('paypal_webhook_receipts',(select count(*) from integration_control.paypal_webhook_receipts_v1),'verified',true);
            else
              v_result_state:='blocked'; v_new_state:='blocked_external'; v_blocked:=v_blocked+1; v_delay:=3600;
              v_result:=jsonb_build_object('state','blocked_external','reason','CERTIFIED_PROVIDER_ADAPTER_OR_HUMAN_PROVIDER_ACTION_REQUIRED','persistent_ownership',true,
                'next_recheck_seconds',3600,'provider_write_performed',false,'authority_manufactured',false);
            end if;

          when 'external.human_action.v1' then
            v_result_state:='blocked'; v_new_state:='blocked_d3'; v_blocked:=v_blocked+1; v_delay:=3600;
            v_result:=jsonb_build_object('state','blocked_d3','reason','HUMAN_PROVIDER_ACTION_REQUIRED','persistent_ownership',true,'d3_human_reserved',true);

          else
            v_result:=public.thrivebase_safe_self_heal_run_v1();
            v_result_state:='delegated'; v_new_state:='verification'; v_delegated:=v_delegated+1; v_delay:=900;
        end case;
      exception when others then
        v_result_state:='failed'; v_new_state:='detected'; v_error:=left(sqlerrm,500); v_failed:=v_failed+1;
        v_delay:=least(coalesce(h.retry_max_seconds,3600),greatest(coalesce(h.retry_base_seconds,60),60*power(2,least(r.attempt_count,5))::int));
        v_result:=jsonb_build_object('state','failed','sqlstate',sqlstate,'error',v_error,'persistent_retry',true);
      end;
    end if;

    v_delay:=least(coalesce(h.retry_max_seconds,3600),greatest(coalesce(v_delay,h.retry_base_seconds,60),5));
    v_attempt_sha:=encode(extensions.digest(convert_to(jsonb_build_object('problem_id',r.problem_id,'handler',r.handler_key,'result_state',v_result_state,'result',v_result,'error',v_error,'completed_at',clock_timestamp())::text,'UTF8'),'sha256'),'hex');
    insert into penta_self.problem_attempts_v1(cycle_id,problem_id,attempt_no,handler_key,owner_penta,authority_class,result_state,reversible,evidence,evidence_sha256,started_at,completed_at)
    values(p_cycle_id,r.problem_id,r.attempt_count+1,r.handler_key,r.owner_penta,r.authority_class,v_result_state,true,
      coalesce(v_result,'{}'::jsonb)||jsonb_build_object('error',v_error,'next_retry_seconds',v_delay,'d3_human_reserved',true,'authority_manufactured',false),
      v_attempt_sha,v_started,clock_timestamp());

    insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence)
    values(p_cycle_id,'self.heal','continuous_problem_'||regexp_replace(r.handler_key,'[^a-zA-Z0-9_.-]+','_','g'),r.source_ref,
      case when v_result_state='verified' then 'applied' when v_result_state in ('applied','delegated','blocked','failed','no_change') then v_result_state else 'delegated' end,
      true,case when r.authority_class='D3' then 'D2' else r.authority_class end,
      jsonb_build_object('problem_id',r.problem_id,'handler_key',r.handler_key,'problem_state',v_new_state,'attempt_result',v_result_state,
                         'evidence_sha256',v_attempt_sha,'persistent_ownership',true,'d3_human_reserved',true,'authority_manufactured',false));

    update penta_self.problem_ledger_v1 set
      state=v_new_state,
      next_attempt_at=case when v_new_state='resolved' then now()+interval '100 years' else now()+make_interval(secs=>v_delay) end,
      last_error=v_error,
      blocked_reason=case when v_new_state='blocked_d3' then 'D3_HUMAN_RESERVED' when v_new_state='blocked_external' then coalesce(v_error,'EXTERNAL_PROVIDER_OR_ADAPTER_REQUIRED') else null end,
      verification_evidence=verification_evidence||case when v_result_state='verified' then coalesce(v_result,'{}'::jsonb)||jsonb_build_object('verified_at',clock_timestamp(),'attempt_sha256',v_attempt_sha) else '{}'::jsonb end,
      evidence=evidence||jsonb_build_object('latest_attempt_sha256',v_attempt_sha,'latest_attempt_result',v_result_state,'latest_handler',r.handler_key),
      resolved_at=case when v_new_state='resolved' then clock_timestamp() else null end,
      updated_at=now()
    where problem_id=r.problem_id;
  end loop;

  return jsonb_build_object('service','ct.penta.self.problem-heal-cycle.v1','cycle_id',p_cycle_id,'attempted',v_attempts,
    'applied',v_applied,'verified_resolved',v_verified,'delegated',v_delegated,'blocked',v_blocked,'failed',v_failed,
    'persistent_retry',true,'d3_human_reserved',true,'authority_manufactured',false,'at',now());
end $$;

