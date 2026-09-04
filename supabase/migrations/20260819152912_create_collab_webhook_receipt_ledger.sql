create table if not exists integration_control.webhook_receipts (
  receipt_id uuid primary key default extensions.gen_random_uuid(),
  service_id text not null references integration_control.services(service_id),
  event_hint text,
  project_uid uuid,
  body_sha256 text not null,
  body_bytes integer not null check (body_bytes >= 0 and body_bytes <= 65536),
  idempotency_key text,
  duplicate boolean not null default false,
  accepted boolean not null default false,
  notes text,
  received_at timestamptz not null default now()
);
alter table integration_control.webhook_receipts enable row level security;
revoke all on integration_control.webhook_receipts from public, anon, authenticated;
grant select, insert, update, delete on integration_control.webhook_receipts to service_role;
drop policy if exists webhook_receipts_service_role_all on integration_control.webhook_receipts;
create policy webhook_receipts_service_role_all on integration_control.webhook_receipts for all to service_role using (true) with check (true);

create or replace function public.integration_record_webhook_receipt(
  p_service_id text,
  p_event_hint text,
  p_project_uid uuid,
  p_body_sha256 text,
  p_body_bytes integer,
  p_idempotency_key text,
  p_accepted boolean,
  p_notes text
) returns jsonb
language plpgsql
security definer
set search_path=''
as $$
declare
  v_duplicate boolean;
  v_id uuid;
begin
  if auth.role() <> 'service_role' then raise exception 'forbidden'; end if;
  select exists(select 1 from integration_control.webhook_receipts where service_id=p_service_id and body_sha256=p_body_sha256 and received_at > now()-interval '24 hours') into v_duplicate;
  insert into integration_control.webhook_receipts(service_id,event_hint,project_uid,body_sha256,body_bytes,idempotency_key,duplicate,accepted,notes)
  values(p_service_id,left(p_event_hint,120),p_project_uid,p_body_sha256,p_body_bytes,left(p_idempotency_key,200),v_duplicate,(p_accepted and not v_duplicate),left(p_notes,500))
  returning receipt_id into v_id;
  return jsonb_build_object('receipt_id',v_id,'duplicate',v_duplicate,'accepted',(p_accepted and not v_duplicate));
end;
$$;
revoke all on function public.integration_record_webhook_receipt(text,text,uuid,text,integer,text,boolean,text) from public, anon, authenticated;
grant execute on function public.integration_record_webhook_receipt(text,text,uuid,text,integer,text,boolean,text) to service_role;