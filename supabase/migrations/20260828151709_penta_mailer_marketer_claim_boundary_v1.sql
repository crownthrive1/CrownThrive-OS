-- Keep generic PentaMail claims internal/system. Governed external PentaMarketer mail is claimed by a PentaMail-owned external lane.

create or replace function public.penta_mail_claim_outbox_v2(p_limit integer default 2)
returns setof public.penta_mail_outbox_v1
language plpgsql
security definer
set search_path='pg_catalog','public','integration_control'
as $function$
declare
  v_status jsonb; v_now timestamptz:=clock_timestamp(); v_limit integer:=greatest(1,least(coalesce(p_limit,2),2));
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform pg_advisory_xact_lock(hashtext('public.penta_mail_claim_outbox_v2'));
  perform integration_control.penta_mail_reconcile_trigger_probation_v1();
  v_status:=public.penta_mail_provider_status_v1(null);
  if v_status->>'route_state' not in ('closed','controlled_release') then return; end if;

  update public.penta_mail_outbox_v1 o
  set state='queued',available_at=greatest(o.available_at,v_now),metadata=o.metadata||jsonb_build_object('provider_release_mode','controlled','trigger_probation_expired_at',v_now),updated_at=v_now
  where o.state='held'
    and lower(o.message_type) not in ('locticians_claim','sales_outreach','lead_nurture')
    and not (lower(coalesce(o.metadata->>'origin_penta',''))='pentamarketer' and lower(coalesce(o.metadata->>'recipient_scope',''))='governed_external')
    and o.metadata->>'provider_hold_policy'='ct.pentamailer.policy.mailgun-delivery-resilience.v1@1.0.0'
    and not exists(select 1 from integration_control.penta_mail_trigger_probation_v1 p where p.trigger_ref=o.trigger_ref and p.probation_until>v_now);

  update public.penta_mail_outbox_v1 o
  set state='retry',lease_id=null,lease_expires_at=null,available_at=greatest(o.available_at,v_now),metadata=o.metadata||jsonb_build_object('lease_recovered_at',v_now),updated_at=v_now
  where o.state='dispatching'
    and lower(o.message_type) not in ('locticians_claim','sales_outreach','lead_nurture')
    and not (lower(coalesce(o.metadata->>'origin_penta',''))='pentamarketer' and lower(coalesce(o.metadata->>'recipient_scope',''))='governed_external')
    and o.lease_expires_at<=v_now;

  return query
  with candidates as (
    select o.message_id
    from public.penta_mail_outbox_v1 o
    where o.state in ('queued','pending','retry') and o.available_at<=v_now
      and lower(o.message_type) not in ('locticians_claim','sales_outreach','lead_nurture')
      and not (lower(coalesce(o.metadata->>'origin_penta',''))='pentamarketer' and lower(coalesce(o.metadata->>'recipient_scope',''))='governed_external')
      and not exists(select 1 from integration_control.penta_mail_trigger_probation_v1 p where p.trigger_ref=o.trigger_ref and p.probation_until>v_now)
    order by
      case when o.trigger_ref='scheduled:penta-mail-state-architecture-report-v1' then 0 else 1 end,
      case when o.trigger_ref='scheduled:penta-mail-state-architecture-report-v1' then o.created_at end desc,
      case upper(o.severity) when 'CRITICAL' then 1 when 'P0' then 1 when 'HIGH' then 2 when 'P1' then 2 when 'MEDIUM' then 3 when 'P2' then 3 when 'INFO' then 4 when 'P3' then 4 else 5 end,
      o.created_at asc
    for update skip locked limit v_limit
  ),leases as (select message_id,gen_random_uuid() lease_id from candidates)
  update public.penta_mail_outbox_v1 o
  set state='dispatching',lease_id=l.lease_id,lease_expires_at=v_now+interval '5 minutes',metadata=o.metadata||jsonb_build_object('claimed_at',v_now,'claimed_by','PentaMail','controlled_release_batch_limit',2,'priority_normalization','latest_founder_state_report_first_then_P0/P1/P2/P3','commercial_lane','governed_external_claimed_separately'),updated_at=v_now
  from leases l where o.message_id=l.message_id returning o.*;
end
$function$;

create or replace function crm.penta_marketer_claim_outbox_v2(p_limit integer default 2)
returns setof public.penta_mail_outbox_v1
language plpgsql
security definer
set search_path='pg_catalog','crm','public','integration_control','pg_temp'
as $function$
declare
  v_status jsonb;
  v_now timestamptz:=clock_timestamp();
  v_limit integer:=greatest(1,least(coalesce(p_limit,2),2));
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  perform integration_control.penta_mail_reconcile_trigger_probation_v1();
  v_status:=public.penta_mail_provider_status_v1(null);
  if v_status->>'route_state' not in ('closed','controlled_release') then return; end if;

  update public.penta_mail_outbox_v1 o
     set state='queued',available_at=greatest(o.available_at,v_now),
         metadata=o.metadata||jsonb_build_object('provider_release_mode','controlled','trigger_probation_expired_at',v_now,'released_by','PentaMail'),updated_at=v_now
   where o.state='held'
     and o.metadata->>'provider_hold_policy'='ct.pentamailer.policy.mailgun-delivery-resilience.v1@1.0.0'
     and (
       lower(o.message_type)='locticians_claim'
       or (lower(coalesce(o.metadata->>'origin_penta',''))='pentamarketer' and lower(coalesce(o.metadata->>'recipient_scope',''))='governed_external')
     )
     and not exists(select 1 from integration_control.penta_mail_trigger_probation_v1 p where p.trigger_ref=o.trigger_ref and p.probation_until>v_now);

  update public.penta_mail_outbox_v1 o
     set state='retry',lease_id=null,lease_expires_at=null,available_at=greatest(o.available_at,v_now),
         metadata=o.metadata||jsonb_build_object('lease_recovered_at',v_now,'recovered_by','PentaMail'),updated_at=v_now
   where o.state='dispatching'
     and (
       lower(o.message_type)='locticians_claim'
       or (lower(coalesce(o.metadata->>'origin_penta',''))='pentamarketer' and lower(coalesce(o.metadata->>'recipient_scope',''))='governed_external')
     )
     and o.lease_expires_at<=v_now;

  return query
  with candidates as (
    select o.message_id
      from public.penta_mail_outbox_v1 o
     where o.state in ('queued','pending','retry')
       and o.available_at<=v_now
       and not exists(select 1 from integration_control.penta_mail_trigger_probation_v1 p where p.trigger_ref=o.trigger_ref and p.probation_until>v_now)
       and (
         (lower(o.message_type)='locticians_claim' and crm.penta_marketer_outbox_eligible_v1(o.message_id))
         or (
           lower(coalesce(o.metadata->>'origin_penta',''))='pentamarketer'
           and lower(coalesce(o.metadata->>'recipient_scope',''))='governed_external'
           and coalesce(o.metadata->>'work_id','') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
           and crm.penta_marketer_external_recipient_allowed_v1(o.recipient,(o.metadata->>'work_id')::uuid)
         )
       )
     order by case upper(o.severity) when 'CRITICAL' then 1 when 'P0' then 1 when 'HIGH' then 2 when 'P1' then 2 when 'MEDIUM' then 3 when 'P2' then 3 when 'INFO' then 4 when 'P3' then 4 else 5 end,o.created_at
     for update skip locked limit v_limit
  ),leases as (select message_id,gen_random_uuid() lease_id from candidates)
  update public.penta_mail_outbox_v1 o
     set state='dispatching',lease_id=l.lease_id,lease_expires_at=v_now+interval '5 minutes',
         metadata=o.metadata||jsonb_build_object('claimed_at',v_now,'claimed_by','PentaMail','communication_control_plane','PentaMarketer','transport_owner','PentaMail','controlled_release_batch_limit',2),updated_at=v_now
    from leases l where o.message_id=l.message_id returning o.*;
end
$function$;

revoke all on function crm.penta_marketer_claim_outbox_v2(integer) from public,anon,authenticated;
grant execute on function crm.penta_marketer_claim_outbox_v2(integer) to service_role;
