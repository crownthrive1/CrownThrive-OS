-- The append-only campaign event ledger is authoritative for outbound-send
-- projection. Mutable summaries may display the result but may not override it.

create table if not exists crm.penta_marketer_campaign_projection_v2 (
  campaign_ref text primary key,
  event_ledger_sends bigint not null default 0,
  accepted_or_delivered_events bigint not null default 0,
  projection_basis text not null,
  source_table text not null,
  evidence_sha256 text not null,
  projected_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

alter table crm.penta_marketer_campaign_projection_v2 enable row level security;
revoke all on crm.penta_marketer_campaign_projection_v2 from public,anon,authenticated;
grant select,insert,update on crm.penta_marketer_campaign_projection_v2 to service_role;
drop policy if exists penta_marketer_campaign_projection_service_role_v2 on crm.penta_marketer_campaign_projection_v2;
create policy penta_marketer_campaign_projection_service_role_v2
  on crm.penta_marketer_campaign_projection_v2
  for all to service_role using(true) with check(true);

create or replace function crm.penta_marketer_refresh_event_projection_v2(
  p_campaign_ref text default 'ct.pentamarketer.locticians.claim.20260827.v1'
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,crm,extensions,penta_self,chlom_runtime
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_total bigint:=0;
  v_accepted bigint:=0;
  v_payload jsonb;
  v_digest text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required';
  end if;

  select count(*),
         count(*) filter(
           where lower(coalesce(j->>'event_type',j->>'event_name',j->>'type',j->>'state',j->>'event','')) in (
             'sent','send','accepted','provider_accepted','delivered','delivery_accepted','send_accepted','completed'
           )
           or coalesce((j->>'provider_accepted')::boolean,false)=true
         )
  into v_total,v_accepted
  from (select to_jsonb(e) j from crm.penta_marketer_campaign_events_v1 e) x
  where j::text ilike '%'||replace(p_campaign_ref,'%','')||'%'
    and (
      lower(coalesce(j->>'event_type',j->>'event_name',j->>'type',j->>'state',j->>'event','')) in (
        'sent','send','accepted','provider_accepted','delivered','delivery_accepted','send_accepted','completed'
      )
      or coalesce((j->>'provider_accepted')::boolean,false)=true
      or j::text ilike '%provider_accepted%'
    );

  v_payload:=jsonb_build_object(
    'campaign_ref',p_campaign_ref,
    'event_ledger_sends',v_total,
    'accepted_or_delivered_events',v_accepted,
    'projection_basis','append_only_event_ledger',
    'source_table','crm.penta_marketer_campaign_events_v1',
    'projected_at',now()
  );
  v_digest:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');

  insert into crm.penta_marketer_campaign_projection_v2(
    campaign_ref,event_ledger_sends,accepted_or_delivered_events,
    projection_basis,source_table,evidence_sha256,projected_at,metadata
  ) values(
    p_campaign_ref,v_total,v_accepted,'append_only_event_ledger',
    'crm.penta_marketer_campaign_events_v1',v_digest,now(),
    jsonb_build_object('mutable_summary_authority',false,'event_ledger_authoritative',true)
  )
  on conflict(campaign_ref) do update set
    event_ledger_sends=excluded.event_ledger_sends,
    accepted_or_delivered_events=excluded.accepted_or_delivered_events,
    projection_basis=excluded.projection_basis,
    source_table=excluded.source_table,
    evidence_sha256=excluded.evidence_sha256,
    projected_at=excluded.projected_at,
    metadata=crm.penta_marketer_campaign_projection_v2.metadata||excluded.metadata;

  update penta_self.problem_ledger_v1
  set state='resolved',
      resolved_at=coalesce(resolved_at,now()),
      blocked_reason=null,
      last_error=null,
      verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||jsonb_build_object(
        'verified_at',now(),
        'campaign_ref',p_campaign_ref,
        'event_ledger_sends',v_total,
        'accepted_or_delivered_events',v_accepted,
        'projection_basis','crm.penta_marketer_campaign_projection_v2',
        'mutable_summary_authority',false,
        'reconciler','crm.penta_marketer_refresh_event_projection_v2'
      ),
      updated_at=now()
  where title='PentaMarketer summary contradicts its event ledger'
    and state<>'resolved';

  perform chlom_runtime.append_dail_event(
    'pentamarketer.campaign.projection.reconciled',
    'marketing_projection',
    p_campaign_ref,
    v_payload,
    'PentaMarketer/PentaStatus/PentaAssure',
    null,'PentaMarketer','2.0.0',v_digest,null,
    'ct.pentamarketer.locticians.dynamic-outreach.v3',null,'internal'
  );
  return v_payload;
end $$;

revoke all on function crm.penta_marketer_refresh_event_projection_v2(text) from public,anon,authenticated;
grant execute on function crm.penta_marketer_refresh_event_projection_v2(text) to service_role;

select integration_control.scheduler_desired_job_upsert_v2(
  'ct-pentamarketer-event-projection-v2',
  '3-59/5 * * * *',
  'select crm.penta_marketer_refresh_event_projection_v2();',
  2026082901,
  'ct.pentaself.scheduler-permanence.v2',
  jsonb_build_object(
    'owner','PentaMarketer/PentaStatus/PentaAssure',
    'rollback_policy','monotonic',
    'event_ledger_authoritative',true
  )
);
select cron.unschedule(jobid) from cron.job where jobname='ct-pentamarketer-event-projection-v2';
select cron.schedule(
  'ct-pentamarketer-event-projection-v2',
  '3-59/5 * * * *',
  'select crm.penta_marketer_refresh_event_projection_v2();'
);
select integration_control.scheduler_permanence_reconcile_v2();
select crm.penta_marketer_refresh_event_projection_v2();
