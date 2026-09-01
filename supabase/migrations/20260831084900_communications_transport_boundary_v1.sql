-- CrownThrive Communications Transport Boundary v1
-- Runtime source-control projection of production repair applied 2026-08-31.
-- Contract: ct.communications.transport-boundary.v1

create or replace function public.penta_mail_transport_boundary_v1()
returns jsonb
language sql
stable
set search_path = 'pg_catalog', 'public'
as $$
  select jsonb_build_object(
    'contract_id','ct.communications.transport-boundary.v1',
    'canonical_control_plane','PentaMarketer',
    'canonical_outbound_transport','PentaMail/PentaMailer',
    'provider_transport','Mailgun',
    'mailbox_connectors',jsonb_build_array('Gmail','Outlook'),
    'mailbox_connector_role','ingest_read_normalize_thread_handoff_only',
    'direct_business_send_allowed',false,
    'direct_persona_send_allowed',false,
    'mailbox_fallback_allowed',false,
    'universal_copy_policy','ct.pentamailer.policy.universal-copy.v1',
    'support_transactional_first_class',true,
    'support_precedes_marketing',true,
    'scheduler_creates_authority',false,
    'provider_acceptance_is_institutional_completion',false,
    'required_hold_when_transport_unavailable','HOLD_PENTAMAIL_TRANSPORT_UNAVAILABLE',
    'required_hold_on_direct_mailbox_attempt','HOLD_DIRECT_MAILBOX_SEND_PROHIBITED'
  );
$$;

comment on function public.penta_mail_transport_boundary_v1() is
'Public-safe machine-readable CrownThrive communications transport invariant. Gmail/Outlook are mailbox connector boundaries; CrownThrive business/persona outbound is PentaMarketer -> PentaMail/PentaMailer -> governed provider transport. No direct-mailbox fallback.';

create or replace function crm.penta_marketer_claim_outbox_v2(p_limit integer default 2)
returns setof public.penta_mail_outbox_v1
language plpgsql
security definer
set search_path to 'pg_catalog', 'crm', 'public', 'integration_control', 'pg_temp'
as $function$
declare
  v_status jsonb;
  v_pool jsonb;
  v_now timestamptz:=clock_timestamp();
  v_limit integer:=greatest(1,least(coalesce(p_limit,2),2));
  v_global integer;
  v_loct integer;
  v_other integer;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  perform integration_control.penta_mail_reconcile_trigger_probation_v1();
  v_status:=public.penta_mail_provider_status_v1(null);
  if v_status->>'route_state' not in ('closed','controlled_release') then return; end if;
  v_pool:=public.penta_mail_pool_status_v2();
  v_global:=coalesce((v_pool#>>'{dynamic,global_remaining}')::integer,0);
  v_loct:=coalesce((v_pool#>>'{dynamic,locticians_available_now}')::integer,0);
  v_other:=coalesce((v_pool#>>'{dynamic,other_marketing_available_now}')::integer,0);
  v_limit:=least(v_limit,v_global);
  if v_limit<1 then return; end if;

  update public.penta_mail_outbox_v1 o
     set state='queued',available_at=greatest(o.available_at,v_now),
         metadata=o.metadata||jsonb_build_object('provider_release_mode','controlled','trigger_probation_expired_at',v_now,'released_by','PentaMail'),
         updated_at=v_now
   where o.state='held'
     and o.metadata->>'provider_hold_policy'='ct.pentamailer.policy.mailgun-delivery-resilience.v1@1.0.0'
     and (lower(o.message_type)='locticians_claim'
          or (lower(coalesce(o.metadata->>'origin_penta',''))='pentamarketer'
              and lower(coalesce(o.metadata->>'recipient_scope',''))='governed_external'))
     and not exists(select 1 from integration_control.penta_mail_trigger_probation_v1 p where p.trigger_ref=o.trigger_ref and p.probation_until>v_now);

  update public.penta_mail_outbox_v1 o
     set state='retry',lease_id=null,lease_expires_at=null,available_at=greatest(o.available_at,v_now),
         metadata=o.metadata||jsonb_build_object('lease_recovered_at',v_now,'recovered_by','PentaMail'),updated_at=v_now
   where o.state='dispatching'
     and (lower(o.message_type)='locticians_claim'
          or (lower(coalesce(o.metadata->>'origin_penta',''))='pentamarketer'
              and lower(coalesce(o.metadata->>'recipient_scope',''))='governed_external'))
     and o.lease_expires_at<=v_now;

  return query
  with eligible as (
    select o.message_id,o.severity,o.created_at,
           public.penta_mail_traffic_class_v2(o.message_type,o.metadata) as traffic_class,
           (o.metadata->>'campaign_ref'='locticians-digital-product-newsletter-syndication') as is_newsletter_release
    from public.penta_mail_outbox_v1 o
    where o.state in ('queued','pending','retry') and o.available_at<=v_now
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
  ), ranked as (
    select e.*,
           row_number() over(partition by traffic_class order by
             case upper(severity) when 'CRITICAL' then 1 when 'P0' then 1 when 'HIGH' then 2 when 'P1' then 2 when 'MEDIUM' then 3 when 'P2' then 3 when 'INFO' then 4 when 'P3' then 4 else 5 end,
             created_at,message_id) as class_rank
    from eligible e
  ), newsletter_slot as (
    select r.message_id
    from ranked r
    where r.is_newsletter_release=true
      and r.traffic_class='marketing_other'
      and r.class_rank<=v_other
      and not exists (
        select 1 from ranked priority
        where priority.traffic_class in ('system_internal','support_transactional')
      )
    order by r.class_rank
    limit case when v_limit>=1 then 1 else 0 end
  ), remaining_slots as (
    select r.message_id
    from ranked r
    where (
      (r.traffic_class='system_internal' and r.class_rank<=v_global)
      or (r.traffic_class='support_transactional' and r.class_rank<=v_global)
      or (r.traffic_class='marketing_locticians' and r.class_rank<=v_loct)
      or (r.traffic_class='marketing_other' and r.class_rank<=v_other)
    )
      and not exists(select 1 from newsletter_slot n where n.message_id=r.message_id)
    order by case r.traffic_class when 'system_internal' then 0 when 'support_transactional' then 1 when 'marketing_locticians' then 2 else 3 end,r.class_rank
    limit greatest(v_limit-(select count(*) from newsletter_slot),0)
  ), candidates as (
    select message_id,0 as ord from remaining_slots
    union all
    select message_id,1 as ord from newsletter_slot
  ), leases as (
    select c.message_id,gen_random_uuid() lease_id,c.ord from candidates c order by c.ord,c.message_id
  )
  update public.penta_mail_outbox_v1 o
     set state='dispatching',lease_id=l.lease_id,lease_expires_at=v_now+interval '5 minutes',
         metadata=o.metadata||jsonb_build_object(
           'claimed_at',v_now,
           'claimed_by','PentaMail',
           'communication_control_plane','PentaMarketer',
           'transport_owner','PentaMail',
           'transport_boundary_contract','ct.communications.transport-boundary.v1',
           'controlled_release_batch_limit',2,
           'pool_policy','ct.pentamailer.pool.40k.v1',
           'dynamic_allocation',true,
           'support_transactional_first_class',true,
           'newsletter_backlog_fair_share',case when o.metadata->>'campaign_ref'='locticians-digital-product-newsletter-syndication' then true else false end,
           'fair_share_policy','ct.pentamail.locticians-newsletter-backlog-release.v1'
         ),updated_at=v_now
    from leases l
   where o.message_id=l.message_id
  returning o.*;
end;
$function$;

comment on function crm.penta_marketer_claim_outbox_v2(integer) is
'Canonical PentaMail/PentaMarketer outbox claimant. CrownThrive business/persona outbound must use PentaMail/PentaMailer; support_transactional is first-class and prioritized ahead of marketing. Direct Gmail/Outlook business-send fallback is prohibited by ct.communications.transport-boundary.v1.';
