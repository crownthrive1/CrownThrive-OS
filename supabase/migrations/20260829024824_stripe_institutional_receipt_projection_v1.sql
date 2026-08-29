create or replace function integration_control.reject_stripe_event_receipt_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path=pg_catalog,integration_control
as $$
begin raise exception 'integration_control.stripe_event_receipts is append-only'; end $$;
revoke all on function integration_control.reject_stripe_event_receipt_mutation_v1() from public,anon,authenticated;
grant execute on function integration_control.reject_stripe_event_receipt_mutation_v1() to service_role;

drop trigger if exists stripe_event_receipts_immutable_v1 on integration_control.stripe_event_receipts;
create trigger stripe_event_receipts_immutable_v1 before update or delete on integration_control.stripe_event_receipts for each row execute function integration_control.reject_stripe_event_receipt_mutation_v1();

alter table integration_control.stripe_event_receipts enable row level security;
revoke all on integration_control.stripe_event_receipts from public,anon,authenticated;
revoke update,delete,truncate on integration_control.stripe_event_receipts from service_role;
grant select,insert on integration_control.stripe_event_receipts to service_role;

drop policy if exists stripe_event_receipts_service_role_select_v1 on integration_control.stripe_event_receipts;
create policy stripe_event_receipts_service_role_select_v1 on integration_control.stripe_event_receipts for select to service_role using (true);
drop policy if exists stripe_event_receipts_service_role_insert_v1 on integration_control.stripe_event_receipts;
create policy stripe_event_receipts_service_role_insert_v1 on integration_control.stripe_event_receipts for insert to service_role with check (true);

create or replace function integration_control.project_sermon_stripe_receipt_v1()
returns trigger language plpgsql security definer set search_path=pg_catalog,integration_control as $$
begin
  if new.signature_verified is not true then return new; end if;
  insert into integration_control.stripe_event_receipts(event_id,event_type,livemode,api_version,object_id,connected_account,event_created_at,signature_timestamp,signature_age_seconds,payload_sha256,processing_state,received_at,notes)
  values(new.stripe_event_id,new.event_type,new.livemode,new.evidence->>'api_version',new.object_id,new.connected_account_id,
    case when coalesce(new.evidence->>'event_created_at','')~'^\d{4}-\d{2}-\d{2}T' then (new.evidence->>'event_created_at')::timestamptz else null end,
    case when coalesce(new.evidence->>'signature_timestamp','')~'^\d+$' then (new.evidence->>'signature_timestamp')::bigint else null end,
    case when coalesce(new.evidence->>'signature_age_seconds','')~'^\d+$' then (new.evidence->>'signature_age_seconds')::integer else null end,
    new.payload_sha256,'observed',new.received_at,'source=sermon_commerce.webhook_receipts; source_processing_state='||new.processing_state||'; signature_verified=true')
  on conflict(event_id) do nothing;
  return new;
end $$;
revoke all on function integration_control.project_sermon_stripe_receipt_v1() from public,anon,authenticated;
grant execute on function integration_control.project_sermon_stripe_receipt_v1() to service_role;
drop trigger if exists project_sermon_stripe_receipt_v1 on sermon_commerce.webhook_receipts;
create trigger project_sermon_stripe_receipt_v1 after insert on sermon_commerce.webhook_receipts for each row execute function integration_control.project_sermon_stripe_receipt_v1();

create or replace function integration_control.project_credit_stripe_receipt_v1()
returns trigger language plpgsql security definer set search_path=pg_catalog,integration_control as $$
begin
  insert into integration_control.stripe_event_receipts(event_id,event_type,livemode,api_version,object_id,connected_account,event_created_at,signature_timestamp,signature_age_seconds,payload_sha256,processing_state,received_at,notes)
  values(new.provider_event_id,new.event_type,new.livemode,new.api_version,null,null,new.event_created_at,null,new.signature_age_seconds,new.payload_sha256,'observed',new.received_at,
    'source=developer_commerce.webhook_receipts; source_processing_state='||new.processing_state||'; signature_verified_by_ingress=true')
  on conflict(event_id) do nothing;
  return new;
end $$;
revoke all on function integration_control.project_credit_stripe_receipt_v1() from public,anon,authenticated;
grant execute on function integration_control.project_credit_stripe_receipt_v1() to service_role;
drop trigger if exists project_credit_stripe_receipt_v1 on developer_commerce.webhook_receipts;
create trigger project_credit_stripe_receipt_v1 after insert on developer_commerce.webhook_receipts for each row execute function integration_control.project_credit_stripe_receipt_v1();

create or replace function integration_control.project_commercial_gap_stripe_receipt_v1()
returns trigger language plpgsql security definer set search_path=pg_catalog,integration_control as $$
begin
  if new.signature_verified is not true then return new; end if;
  insert into integration_control.stripe_event_receipts(event_id,event_type,livemode,api_version,object_id,connected_account,event_created_at,signature_timestamp,signature_age_seconds,payload_sha256,processing_state,received_at,notes)
  values(new.stripe_event_id,new.event_type,new.livemode,new.api_version,new.object_id,null,new.provider_created_at,new.signature_timestamp,null,new.payload_sha256,'observed',new.received_at,
    'source=developer_commerce.commercial_gap_stripe_webhook_events; source_processing_state='||new.processing_state||'; signature_verified=true; cohort='||new.cohort_id)
  on conflict(event_id) do nothing;
  return new;
end $$;
revoke all on function integration_control.project_commercial_gap_stripe_receipt_v1() from public,anon,authenticated;
grant execute on function integration_control.project_commercial_gap_stripe_receipt_v1() to service_role;
drop trigger if exists project_commercial_gap_stripe_receipt_v1 on developer_commerce.commercial_gap_stripe_webhook_events;
create trigger project_commercial_gap_stripe_receipt_v1 after insert on developer_commerce.commercial_gap_stripe_webhook_events for each row execute function integration_control.project_commercial_gap_stripe_receipt_v1();

insert into integration_control.stripe_event_receipts(event_id,event_type,livemode,api_version,object_id,connected_account,event_created_at,signature_timestamp,signature_age_seconds,payload_sha256,processing_state,received_at,notes)
select stripe_event_id,event_type,livemode,evidence->>'api_version',object_id,connected_account_id,
       case when coalesce(evidence->>'event_created_at','')~'^\d{4}-\d{2}-\d{2}T' then (evidence->>'event_created_at')::timestamptz else null end,
       case when coalesce(evidence->>'signature_timestamp','')~'^\d+$' then (evidence->>'signature_timestamp')::bigint else null end,
       case when coalesce(evidence->>'signature_age_seconds','')~'^\d+$' then (evidence->>'signature_age_seconds')::integer else null end,
       payload_sha256,'observed',received_at,'backfill=sermon_commerce.webhook_receipts; source_processing_state='||processing_state||'; signature_verified=true'
from sermon_commerce.webhook_receipts where signature_verified is true on conflict(event_id) do nothing;

insert into integration_control.stripe_event_receipts(event_id,event_type,livemode,api_version,event_created_at,signature_age_seconds,payload_sha256,processing_state,received_at,notes)
select provider_event_id,event_type,livemode,api_version,event_created_at,signature_age_seconds,payload_sha256,'observed',received_at,
       'backfill=developer_commerce.webhook_receipts; source_processing_state='||processing_state||'; signature_verified_by_ingress=true'
from developer_commerce.webhook_receipts on conflict(event_id) do nothing;

insert into integration_control.stripe_event_receipts(event_id,event_type,livemode,api_version,object_id,event_created_at,signature_timestamp,payload_sha256,processing_state,received_at,notes)
select stripe_event_id,event_type,livemode,api_version,object_id,provider_created_at,signature_timestamp,payload_sha256,'observed',received_at,
       'backfill=developer_commerce.commercial_gap_stripe_webhook_events; source_processing_state='||processing_state||'; signature_verified=true; cohort='||cohort_id
from developer_commerce.commercial_gap_stripe_webhook_events where signature_verified is true on conflict(event_id) do nothing;