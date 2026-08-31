-- Locticians Brilliant Directories webhook provider certification / 33-route convergence
-- Captures production behavior observed 2026-08-31. No raw API tokens or webhook hook ID are stored here.

update integration_control.locticians_bd_webhook_routes_v1
set enabled=false,
    notes=coalesce(notes,'')||' | Disabled: no Custom Forms row present in active Brilliant Directories Developer Hub default webhook screen.',
    updated_at=now()
where event_code='custom_form';

update integration_control.locticians_bd_webhook_bindings_v1
set metadata=metadata||jsonb_build_object(
      'all_default_routes',33,
      'default_route_count',33,
      'provider_visible_default_rows',33,
      'custom_form_route_enabled',false,
      'provider_configuration_certified',true,
      'provider_total_rows',33,
      'provider_enabled_rows',33,
      'provider_exact_host_path_rows',33,
      'provider_exact_event_rows',33,
      'provider_unique_event_codes',33,
      'provider_common_hook_count',1,
      'provider_missing_event_codes','[]'::jsonb,
      'provider_unexpected_event_codes','[]'::jsonb,
      'provider_stored_link_canary_http',202,
      'router_certified_lane','ct.locticians.bd.personas.hot.v1',
      'router_certified_provider_http',200,
      'router_certified_version','6.0.0',
      'raw_api_key_projected',false,
      'raw_hook_projected',false
    ),
    updated_at=now()
where binding_key='ct.locticians.bd.webhook.v1';

create or replace function public.locticians_bd_select_warm_credential_v3(p_failure_class text default 'none')
returns jsonb
language sql
security definer
set search_path to 'pg_catalog','integration_control'
as $function$
  select integration_control.locticians_bd_select_warm_credential_v3(p_failure_class)
$function$;
revoke all on function public.locticians_bd_select_warm_credential_v3(text) from public;
grant execute on function public.locticians_bd_select_warm_credential_v3(text) to service_role;

create or replace function integration_control.locticians_bd_webhook_dispatch_tick_v1(p_limit integer default 100)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','public','crm'
as $function$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  r record;
  v_email text;
  v_signal_id text;
  v_completed integer:=0;
  v_failed integer:=0;
  v_suppressed integer:=0;
  v_signals integer:=0;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  p_limit:=least(greatest(coalesce(p_limit,100),1),500);
  for r in
    select * from integration_control.locticians_bd_webhook_dispatch_v1
    where state='queued'
    order by created_at,dispatch_id
    for update skip locked
    limit p_limit
  loop
    begin
      update integration_control.locticians_bd_webhook_dispatch_v1 set state='in_progress',updated_at=now() where dispatch_id=r.dispatch_id;
      if r.target_ref='chlom.dail' then
        update integration_control.locticians_bd_webhook_dispatch_v1
        set state='completed',authority_note=authority_note||' DAIL receipt already appended during durable ingest.',
            payload=payload||jsonb_build_object('dispatch_result','dail_already_appended_at_ingest','authority_expansion',false),
            completed_at=clock_timestamp(),updated_at=now()
        where dispatch_id=r.dispatch_id;
        v_completed:=v_completed+1;
        continue;
      end if;
      if r.target_ref='penta.mail.suppression' then
        v_email:=lower(trim(coalesce(
          r.payload->'sanitized_payload'->>'email',r.payload->'sanitized_payload'->>'email_address',
          r.payload->'sanitized_payload'->>'member_email',r.payload->'sanitized_payload'->>'user_email','')));
        if v_email<>'' and v_email ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' then
          perform pg_advisory_xact_lock(hashtext('crm.suppression:'||v_email));
          if exists(select 1 from crm.suppression_list where lower(email)=v_email) then
            update crm.suppression_list set reason='unsubscribe',source='locticians_bd_webhook',
              notes='Brilliant Directories unsubscribe webhook; receipt '||r.receipt_id::text,expires_at=null
            where lower(email)=v_email;
          else
            insert into crm.suppression_list(email,reason,source,notes)
            values(v_email,'unsubscribe','locticians_bd_webhook','Brilliant Directories unsubscribe webhook; receipt '||r.receipt_id::text);
          end if;
          v_suppressed:=v_suppressed+1;
        else
          update integration_control.locticians_bd_webhook_dispatch_v1
          set state='held',authority_note=authority_note||' Suppression handoff held: no valid email in sanitized provider payload.',
              payload=payload||jsonb_build_object('dispatch_result','held_missing_valid_email','authority_expansion',false),updated_at=now()
          where dispatch_id=r.dispatch_id;
          continue;
        end if;
      end if;
      v_signal_id:='ct.signal.locticians.bd.webhook.'||replace(r.receipt_id::text,'-','')||'.'||regexp_replace(lower(r.target_ref),'[^a-z0-9]+','-','g');
      insert into public.penta_signal_observations(signal_id,observed_at,source_refs,claim,confidence,corroboration_state,risk_class,disposition,linked_research_id,evidence_refs)
      values(v_signal_id,clock_timestamp(),jsonb_build_array(jsonb_build_object('service','locticians','provider','Brilliant Directories','receipt_id',r.receipt_id,'event_code',r.event_code)),
        'Locticians Brilliant Directories webhook event '||r.event_code||' routed to '||r.target_ref,
        1.0,'corroborated',r.risk_class,'observe',null,
        jsonb_build_array(jsonb_build_object('target_ref',r.target_ref,'dispatch_id',r.dispatch_id,'payload_sha256',r.payload->>'payload_sha256','authority_expansion',false,'provider_write',false)))
      on conflict(signal_id) do nothing;
      if found then v_signals:=v_signals+1; end if;
      update integration_control.locticians_bd_webhook_dispatch_v1
      set state='completed',payload=payload||jsonb_build_object('dispatch_result','penta_signal_observation','signal_id',v_signal_id,'authority_expansion',false,'provider_write',false),
          completed_at=clock_timestamp(),updated_at=now()
      where dispatch_id=r.dispatch_id;
      v_completed:=v_completed+1;
    exception when others then
      update integration_control.locticians_bd_webhook_dispatch_v1
      set state='failed',authority_note=authority_note||' Dispatch failure: '||sqlstate,
          payload=payload||jsonb_build_object('dispatch_result','failed','sqlstate',sqlstate,'authority_expansion',false),updated_at=now()
      where dispatch_id=r.dispatch_id;
      v_failed:=v_failed+1;
    end;
  end loop;
  return jsonb_build_object('contract','ct.locticians.bd.webhook.target-dispatch.v1','completed',v_completed,'failed',v_failed,'signals_written',v_signals,'suppressions_applied',v_suppressed,'authority_expansion',false,'provider_write',false,'observed_at',clock_timestamp());
end
$function$;

create or replace function public.locticians_bd_webhook_dispatch_tick_v1(p_limit integer default 100)
returns jsonb language sql security definer set search_path to 'pg_catalog','integration_control'
as $function$ select integration_control.locticians_bd_webhook_dispatch_tick_v1(p_limit) $function$;
revoke all on function public.locticians_bd_webhook_dispatch_tick_v1(integer) from public;
grant execute on function public.locticians_bd_webhook_dispatch_tick_v1(integer) to service_role;

select cron.unschedule(jobid) from cron.job where jobname='ct-locticians-bd-webhook-target-dispatch-v1';
select cron.schedule('ct-locticians-bd-webhook-target-dispatch-v1','* * * * *','select integration_control.locticians_bd_webhook_dispatch_tick_v1(250);');
