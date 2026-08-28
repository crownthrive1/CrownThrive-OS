create or replace function crm.penta_marketer_promote_ready_external_email_v1(p_limit integer default 25)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','crm','public'
as $function$
declare
  r crm.penta_marketer_external_email_intake_v1%rowtype;
  v_route jsonb;
  v_work_id uuid;
  v_processed integer:=0;
  v_held integer:=0;
  v_results jsonb:='[]'::jsonb;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;

  for r in
    select * from crm.penta_marketer_external_email_intake_v1
    where state='ready'
    order by urgency_score desc,opportunity_score desc,created_at
    limit greatest(1,least(coalesce(p_limit,25),100))
    for update skip locked
  loop
    if public.penta_marketer_suppressed_v1(r.sender_email) then
      update crm.penta_marketer_external_email_intake_v1
         set state='held',metadata=metadata||jsonb_build_object('promotion_hold','suppressed_sender','promotion_checked_at',now()),updated_at=now()
       where intake_id=r.intake_id;
      v_held:=v_held+1;
      v_results:=v_results||jsonb_build_array(jsonb_build_object('intake_id',r.intake_id,'state','held','reason','suppressed_sender'));
      continue;
    end if;

    select work_id into v_work_id
    from crm.penta_marketer_work_queue_v1
    where source_event_id=r.source_message_id
       or payload->>'intake_id'=r.intake_id::text
    order by created_at desc limit 1;

    if v_work_id is null then
      v_route:=crm.penta_marketer_route_work_v1(r.classification,r.source_system,r.urgency_score,r.opportunity_score,r.metadata);
      insert into crm.penta_marketer_work_queue_v1(
        dedupe_key,source_system,source_event_id,channel,work_class,purpose,summary,recipient,
        assigned_agent_id,assigned_persona_id,opportunity_score,urgency_score,authority_class,
        requires_founder_attention,state,payload
      ) values(
        'external-intake:'||r.intake_id::text,
        r.source_system,r.source_message_id,'email',r.classification,'external_email_followup',r.summary,r.sender_email,
        v_route->>'agent_id',v_route->>'persona_id',r.opportunity_score,r.urgency_score,'D1',
        coalesce((v_route->>'requires_founder_attention')::boolean,false) or coalesce((r.metadata->>'founder_attention')::boolean,false),
        'routed',
        jsonb_build_object(
          'intake_id',r.intake_id,
          'source_thread_id',r.source_thread_id,
          'opportunity_brief',r.opportunity_brief,
          'recommended_action',r.recommended_action,
          'reply_needed',r.reply_needed,
          'execution_gate','specialist_verified_resolution_before_external_reply',
          'intake_metadata',r.metadata,
          'route',v_route
        )
      )
      on conflict(dedupe_key) do update set updated_at=now()
      returning work_id into v_work_id;
    end if;

    update crm.penta_marketer_external_email_intake_v1
       set state='processed',
           metadata=metadata||jsonb_build_object(
             'promoted_work_id',v_work_id,
             'promoted_at',now(),
             'promotion_control_plane','PentaMarketer',
             'execution_gate','specialist_verified_resolution_before_external_reply'
           ),
           updated_at=now()
     where intake_id=r.intake_id;

    v_processed:=v_processed+1;
    v_results:=v_results||jsonb_build_array(jsonb_build_object('intake_id',r.intake_id,'state','promoted','work_id',v_work_id));
  end loop;

  return jsonb_build_object('processed',v_processed,'held',v_held,'results',v_results,'at',now());
end
$function$;

revoke all on function crm.penta_marketer_promote_ready_external_email_v1(integer) from public,anon,authenticated;
grant execute on function crm.penta_marketer_promote_ready_external_email_v1(integer) to service_role;

select cron.alter_job(
  199,
  command := 'select crm.locticians_native_action_cycle_v1(25); select crm.penta_marketer_external_email_cycle_v1(25); select crm.penta_marketer_promote_ready_external_email_v1(25); select crm.penta_marketer_service_form_cycle_v1(25);'
);
