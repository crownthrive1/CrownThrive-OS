create or replace function penta_self.message_intake_v1(
  p_cycle_id uuid default gen_random_uuid(),
  p_limit integer default 500
) returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','penta_self','os_v2','public','integration_control','cron','extensions'
as $$
declare
  v_state penta_self.message_scan_state_v1%rowtype;
  r record;
  v_count int:=0;
  v_problem_count int:=0;
  v_total_count int:=0;
  v_total_problems int:=0;
  v_last_ts timestamptz;
  v_last_uuid uuid;
  v_last_bigint bigint;
  v_first_cursor jsonb;
  v_last_cursor jsonb;
  v_evidence jsonb;
  v_sha text;
  v_category text;
  v_handler text;
  v_problem uuid;
  v_source text;
  v_priority text;
  v_owner text;
  v_cycle penta_self.cycle_receipts_v1%rowtype;
begin
  p_limit:=greatest(10,least(coalesce(p_limit,500),2000));

  -- Every recorded system-change message is inspected. Only actual problem candidates enter the durable problem ledger.
  v_source:='os_v2.system_change_events';
  insert into penta_self.message_scan_state_v1(source_name,last_occurred_at,last_uuid,metadata)
  values(v_source,now()-interval '24 hours','00000000-0000-0000-0000-000000000000'::uuid,jsonb_build_object('initial_window','24 hours'))
  on conflict(source_name) do nothing;
  select * into v_state from penta_self.message_scan_state_v1 where source_name=v_source for update;
  v_count:=0; v_problem_count:=0; v_last_ts:=v_state.last_occurred_at; v_last_uuid:=coalesce(v_state.last_uuid,'00000000-0000-0000-0000-000000000000'::uuid);
  v_first_cursor:=jsonb_build_object('occurred_at',v_last_ts,'event_id',v_last_uuid);
  for r in
    select event_id,source_system,event_type,entity_ref,severity,title,summary,details,occurred_at
    from os_v2.system_change_events
    where occurred_at>v_state.last_occurred_at
       or (occurred_at=v_state.last_occurred_at and event_id>coalesce(v_state.last_uuid,'00000000-0000-0000-0000-000000000000'::uuid))
    order by occurred_at,event_id
    limit p_limit
  loop
    v_count:=v_count+1; v_last_ts:=r.occurred_at; v_last_uuid:=r.event_id;
    if penta_self.message_is_problem_v1(r.severity,r.title,r.summary,r.event_type,r.details) then
      v_problem_count:=v_problem_count+1;
      v_category:=penta_self.problem_category_v1(r.source_system,coalesce(r.entity_ref,r.event_id::text),r.title,r.summary,r.event_type);
      v_handler:=penta_self.problem_handler_for_v1(v_category,r.source_system,coalesce(r.entity_ref,r.event_id::text),r.title,r.summary);
      v_priority:=case when lower(coalesce(r.severity,''))='critical' then 'P0' when v_category in ('provider_webhook','payout','security') then 'P1' else 'P2' end;
      v_owner:=(select owner_penta from penta_self.problem_handler_registry_v1 where handler_key=v_handler);
      v_problem:=penta_self.register_problem_v1(
        'system_message',coalesce(r.source_system,'unknown'),coalesce(r.entity_ref,'event:'||r.event_id::text),v_category,r.severity,v_priority,
        coalesce(r.title,'System event problem'),coalesce(r.summary,'System event classified as a problem candidate'),coalesce(v_owner,'PentaSELF'),v_handler,
        (select max_risk_class from penta_self.problem_handler_registry_v1 where handler_key=v_handler),'detected',true,null,
        jsonb_build_object('event_id',r.event_id,'event_type',r.event_type,'occurred_at',r.occurred_at,
                           'details_sha256',encode(extensions.digest(convert_to(coalesce(r.details,'{}'::jsonb)::text,'UTF8'),'sha256'),'hex'),
                           'raw_secret_material_preserved',false)
      );
    end if;
  end loop;
  if v_count>0 then
    update penta_self.message_scan_state_v1 set last_occurred_at=v_last_ts,last_uuid=v_last_uuid,
      total_messages_scanned=total_messages_scanned+v_count,total_problem_candidates=total_problem_candidates+v_problem_count,updated_at=now()
    where source_name=v_source;
  end if;
  v_last_cursor:=jsonb_build_object('occurred_at',v_last_ts,'event_id',v_last_uuid);
  v_evidence:=jsonb_build_object('source',v_source,'message_count',v_count,'problem_count',v_problem_count,'every_message_inspected',true,'secrets_stored',false);
  v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');
  insert into penta_self.message_scan_receipts_v1(cycle_id,source_name,window_start,window_end,first_cursor,last_cursor,message_count,problem_count,evidence_sha256,evidence)
  values(p_cycle_id,v_source,v_state.last_occurred_at,v_last_ts,v_first_cursor,v_last_cursor,v_count,v_problem_count,v_sha,v_evidence);
  v_total_count:=v_total_count+v_count; v_total_problems:=v_total_problems+v_problem_count;

  -- Every PentaFabric packet is inspected, while only bounded metadata and a digest are retained.
  v_source:='public.pentafabric_events';
  insert into penta_self.message_scan_state_v1(source_name,last_occurred_at,last_bigint,metadata)
  select v_source,now()-interval '24 hours',coalesce(max(id),0),jsonb_build_object('initial_window','24 hours')
  from public.pentafabric_events where received_at<now()-interval '24 hours'
  on conflict(source_name) do nothing;
  select * into v_state from penta_self.message_scan_state_v1 where source_name=v_source for update;
  v_count:=0; v_problem_count:=0; v_last_bigint:=coalesce(v_state.last_bigint,0); v_last_ts:=v_state.last_occurred_at;
  v_first_cursor:=jsonb_build_object('id',v_last_bigint,'received_at',v_last_ts);
  for r in
    select id,penta_id,trace_id,lane,route,event,received_at
    from public.pentafabric_events
    where id>coalesce(v_state.last_bigint,0)
    order by id
    limit p_limit
  loop
    v_count:=v_count+1; v_last_bigint:=r.id; v_last_ts:=r.received_at;
    if penta_self.message_is_problem_v1(r.event->>'severity',r.event->>'title',coalesce(r.event->>'summary',r.event->>'message'),r.event->>'type',r.event) then
      v_problem_count:=v_problem_count+1;
      v_category:=penta_self.problem_category_v1(r.penta_id,coalesce(r.route,'fabric-event:'||r.id::text),r.event->>'title',coalesce(r.event->>'summary',r.event->>'message'),r.event->>'type');
      v_handler:=penta_self.problem_handler_for_v1(v_category,r.penta_id,coalesce(r.route,'fabric-event:'||r.id::text),r.event->>'title',coalesce(r.event->>'summary',r.event->>'message'));
      v_owner:=(select owner_penta from penta_self.problem_handler_registry_v1 where handler_key=v_handler);
      v_problem:=penta_self.register_problem_v1(
        'pentafabric_message',coalesce(r.penta_id,'PentaFabric'),coalesce(r.route,'fabric-event:'||r.id::text),v_category,coalesce(r.event->>'severity','warning'),
        case when lower(coalesce(r.event->>'severity','')) in ('critical','fatal') then 'P0' else 'P2' end,
        coalesce(r.event->>'title','PentaFabric problem event'),coalesce(r.event->>'summary',r.event->>'message','PentaFabric packet classified as a problem candidate'),
        coalesce(v_owner,'PentaSELF'),v_handler,(select max_risk_class from penta_self.problem_handler_registry_v1 where handler_key=v_handler),'detected',true,null,
        jsonb_build_object('fabric_event_id',r.id,'trace_id',r.trace_id,'lane',r.lane,'route',r.route,'received_at',r.received_at,
                           'event_sha256',encode(extensions.digest(convert_to(coalesce(r.event,'{}'::jsonb)::text,'UTF8'),'sha256'),'hex'),
                           'raw_secret_material_preserved',false)
      );
    end if;
  end loop;
  if v_count>0 then
    update penta_self.message_scan_state_v1 set last_occurred_at=v_last_ts,last_bigint=v_last_bigint,
      total_messages_scanned=total_messages_scanned+v_count,total_problem_candidates=total_problem_candidates+v_problem_count,updated_at=now()
    where source_name=v_source;
  end if;
  v_last_cursor:=jsonb_build_object('id',v_last_bigint,'received_at',v_last_ts);
  v_evidence:=jsonb_build_object('source',v_source,'message_count',v_count,'problem_count',v_problem_count,'every_message_inspected',true,'secrets_stored',false);
  v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');
  insert into penta_self.message_scan_receipts_v1(cycle_id,source_name,window_start,window_end,first_cursor,last_cursor,message_count,problem_count,evidence_sha256,evidence)
  values(p_cycle_id,v_source,v_state.last_occurred_at,v_last_ts,v_first_cursor,v_last_cursor,v_count,v_problem_count,v_sha,v_evidence);
  v_total_count:=v_total_count+v_count; v_total_problems:=v_total_problems+v_problem_count;

  -- Provider-mail incident records are messages too and receive durable ownership.
  v_source:='integration_control.penta_mail_provider_incidents_v1';
  insert into penta_self.message_scan_state_v1(source_name,last_occurred_at,last_uuid,metadata)
  values(v_source,now()-interval '24 hours','00000000-0000-0000-0000-000000000000'::uuid,jsonb_build_object('initial_window','24 hours'))
  on conflict(source_name) do nothing;
  select * into v_state from penta_self.message_scan_state_v1 where source_name=v_source for update;
  v_count:=0; v_problem_count:=0; v_last_ts:=v_state.last_occurred_at; v_last_uuid:=coalesce(v_state.last_uuid,'00000000-0000-0000-0000-000000000000'::uuid);
  v_first_cursor:=jsonb_build_object('occurred_at',v_last_ts,'incident_id',v_last_uuid);
  for r in
    select incident_id,provider_route_id,provider_event_id,incident_type,evidence_kind,trigger_ref,observed_at,created_at
    from integration_control.penta_mail_provider_incidents_v1
    where created_at>v_state.last_occurred_at
       or (created_at=v_state.last_occurred_at and incident_id>coalesce(v_state.last_uuid,'00000000-0000-0000-0000-000000000000'::uuid))
    order by created_at,incident_id limit p_limit
  loop
    v_count:=v_count+1; v_problem_count:=v_problem_count+1; v_last_ts:=r.created_at; v_last_uuid:=r.incident_id;
    v_problem:=penta_self.register_problem_v1(
      'provider_mail_incident','PentaMail',coalesce(r.trigger_ref,'mail-incident:'||r.incident_id::text),'mail','degraded','P1',
      'PentaMail provider incident requires healing',coalesce(r.incident_type,'Provider mail incident')||' on route '||coalesce(r.provider_route_id,'unknown'),
      'PentaSELF/PentaMail','repair.pentamail.v1','D1','detected',true,null,
      jsonb_build_object('incident_id',r.incident_id,'provider_route_id',r.provider_route_id,'provider_event_id',r.provider_event_id,
                         'incident_type',r.incident_type,'evidence_kind',r.evidence_kind,'observed_at',r.observed_at)
    );
  end loop;
  if v_count>0 then
    update penta_self.message_scan_state_v1 set last_occurred_at=v_last_ts,last_uuid=v_last_uuid,
      total_messages_scanned=total_messages_scanned+v_count,total_problem_candidates=total_problem_candidates+v_problem_count,updated_at=now()
    where source_name=v_source;
  end if;
  v_last_cursor:=jsonb_build_object('occurred_at',v_last_ts,'incident_id',v_last_uuid);
  v_evidence:=jsonb_build_object('source',v_source,'message_count',v_count,'problem_count',v_problem_count,'every_message_inspected',true);
  v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');
  insert into penta_self.message_scan_receipts_v1(cycle_id,source_name,window_start,window_end,first_cursor,last_cursor,message_count,problem_count,evidence_sha256,evidence)
  values(p_cycle_id,v_source,v_state.last_occurred_at,v_last_ts,v_first_cursor,v_last_cursor,v_count,v_problem_count,v_sha,v_evidence);
  v_total_count:=v_total_count+v_count; v_total_problems:=v_total_problems+v_problem_count;

  -- Latest failed active cron jobs remain owned even when the next job succeeds.
  v_count:=0; v_problem_count:=0;
  for r in
    select * from (
      select distinct on (j.jobid) j.jobid,j.jobname,j.active,d.status,d.start_time,d.end_time,d.return_message
      from cron.job j join cron.job_run_details d on d.jobid=j.jobid
      where j.active and d.start_time>=now()-interval '24 hours'
      order by j.jobid,d.start_time desc
    ) x where status='failed'
  loop
    v_count:=v_count+1; v_problem_count:=v_problem_count+1;
    v_category:=case when lower(coalesce(r.return_message,'')) like '%deadlock%' then 'concurrency' else 'scheduler' end;
    v_handler:=penta_self.problem_handler_for_v1(v_category,'pg_cron','cron:'||r.jobname,'Latest active cron execution failed',coalesce(r.return_message,''));
    v_owner:=(select owner_penta from penta_self.problem_handler_registry_v1 where handler_key=v_handler);
    v_problem:=penta_self.register_problem_v1(
      'cron_failure','pg_cron','cron:'||r.jobname,v_category,case when r.jobname like '%commercial_release%' then 'critical' else 'degraded' end,
      case when r.jobname like '%commercial_release%' then 'P1' else 'P2' end,
      'Latest active cron execution failed: '||r.jobname,'PentaSELF retained the failed execution for repair and independent successful readback.',
      coalesce(v_owner,'PentaSELF/PentaTime'),v_handler,(select max_risk_class from penta_self.problem_handler_registry_v1 where handler_key=v_handler),'detected',true,null,
      jsonb_build_object('jobid',r.jobid,'failed_at',r.start_time,'status',r.status,
                         'return_message_sha256',encode(extensions.digest(convert_to(coalesce(r.return_message,''),'UTF8'),'sha256'),'hex'),
                         'raw_return_message_preserved',false)
    );
  end loop;
  v_evidence:=jsonb_build_object('source','cron.latest_active','message_count',v_count,'problem_count',v_problem_count,'latest_failure_persists_until_successful_readback',true);
  v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');
  insert into penta_self.message_scan_receipts_v1(cycle_id,source_name,window_start,window_end,first_cursor,last_cursor,message_count,problem_count,evidence_sha256,evidence)
  values(p_cycle_id,'cron.latest_active',now()-interval '24 hours',now(),'{}'::jsonb,'{}'::jsonb,v_count,v_problem_count,v_sha,v_evidence);
  v_total_count:=v_total_count+v_count; v_total_problems:=v_total_problems+v_problem_count;

  -- Every failed substep in the latest PentaSELF cycle becomes a durable problem; aggregate health cannot hide it.
  v_count:=0; v_problem_count:=0;
  select * into v_cycle from penta_self.cycle_receipts_v1 where cycle_id<>p_cycle_id and coalesce(evidence->>'cycle_kind','base')<>'continuous_healing' order by started_at desc limit 1;
  if found then
    for r in select key,value from jsonb_each(coalesce(v_cycle.evidence,'{}'::jsonb)) loop
      v_count:=v_count+1;
      if coalesce(r.value->>'state','')='failed' or r.value ? 'error' then
        v_problem_count:=v_problem_count+1;
        v_handler:=case when r.key='discovery' then 'repair.pentaself_discovery.v1' else 'diagnose.generic.v1' end;
        v_problem:=penta_self.register_problem_v1(
          'pentaself_substep','PentaSELF','pentaself-cycle:'||v_cycle.cycle_id::text||':'||r.key,
          case when lower(coalesce(r.value->>'error','')) like '%deadlock%' then 'concurrency' else 'operational' end,
          'degraded','P1','PentaSELF substep failed: '||r.key,
          'A failed PentaSELF substep was promoted into durable ownership instead of being masked by aggregate cycle health.',
          (select owner_penta from penta_self.problem_handler_registry_v1 where handler_key=v_handler),v_handler,
          (select max_risk_class from penta_self.problem_handler_registry_v1 where handler_key=v_handler),'detected',true,null,
          jsonb_build_object('cycle_id',v_cycle.cycle_id::text,'substep',r.key,'error',left(coalesce(r.value->>'error','unknown'),300),'cycle_state',v_cycle.state)
        );
      end if;
    end loop;
  end if;
  v_evidence:=jsonb_build_object('source','penta_self.latest_cycle_substeps','message_count',v_count,'problem_count',v_problem_count,'aggregate_health_masking_prohibited',true);
  v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');
  insert into penta_self.message_scan_receipts_v1(cycle_id,source_name,window_start,window_end,first_cursor,last_cursor,message_count,problem_count,evidence_sha256,evidence)
  values(p_cycle_id,'penta_self.latest_cycle_substeps',v_cycle.started_at,coalesce(v_cycle.completed_at,now()),'{}'::jsonb,'{}'::jsonb,v_count,v_problem_count,v_sha,v_evidence);
  v_total_count:=v_total_count+v_count; v_total_problems:=v_total_problems+v_problem_count;

  -- Current institutional incidents and active PentaMail conditions are continuously reconciled.
  for r in select incident_id,system_key,incident_code,severity,priority,state,title,summary,source_event_ref,failure_evidence from public.penta_incidents_v1 where state not in ('resolved','closed') loop
    v_category:=penta_self.problem_category_v1(r.system_key,r.source_event_ref,r.title,r.summary,r.incident_code);
    v_handler:=penta_self.problem_handler_for_v1(v_category,r.system_key,r.source_event_ref,r.title,r.summary);
    v_problem:=penta_self.register_problem_v1('institutional_incident',r.system_key,coalesce(r.source_event_ref,'incident:'||r.incident_id::text),v_category,r.severity,r.priority,r.title,r.summary,
      (select owner_penta from penta_self.problem_handler_registry_v1 where handler_key=v_handler),v_handler,
      (select max_risk_class from penta_self.problem_handler_registry_v1 where handler_key=v_handler),'detected',true,null,
      jsonb_build_object('incident_id',r.incident_id,'incident_code',r.incident_code,'incident_state',r.state,
                         'failure_evidence_sha256',encode(extensions.digest(convert_to(coalesce(r.failure_evidence,'{}'::jsonb)::text,'UTF8'),'sha256'),'hex')));
    v_total_problems:=v_total_problems+1;
  end loop;

  for r in select condition_key,severity,first_seen_at,last_seen_at,details from public.penta_mail_incident_state_v1 where active loop
    v_problem:=penta_self.register_problem_v1('mail_incident_state','PentaMail','mail-condition:'||r.condition_key,'mail',r.severity,'P1',
      'Active PentaMail condition: '||r.condition_key,'PentaSELF must heal or retain this mail condition until provider recovery is verified.',
      'PentaSELF/PentaMail','repair.pentamail.v1','D1','detected',true,null,
      jsonb_build_object('condition_key',r.condition_key,'first_seen_at',r.first_seen_at,'last_seen_at',r.last_seen_at,
                         'details_sha256',encode(extensions.digest(convert_to(coalesce(r.details,'{}'::jsonb)::text,'UTF8'),'sha256'),'hex')));
    v_total_problems:=v_total_problems+1;
  end loop;

  return jsonb_build_object('service','ct.penta.self.message-intake.v1','cycle_id',p_cycle_id,'messages_inspected',v_total_count,
    'problem_candidates',v_total_problems,'every_message_inspected',true,'problem_ownership_persistent',true,'secrets_stored',false,'at',now());
end $$;

