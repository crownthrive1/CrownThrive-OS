create table if not exists public.pentafabric_events (
  id bigint generated always as identity primary key,
  penta_id text not null unique,
  trace_id text not null,
  protocol text not null,
  lane text not null check (lane in ('hot','cold')),
  route text not null,
  chlom_intent_id text not null,
  chlom_binding text not null default 'crownthrive.chlom.pentafabric.v1' check (chlom_binding = 'crownthrive.chlom.pentafabric.v1'),
  event_contract text not null default 'crownthrive.penta.event.v1' check (event_contract = 'crownthrive.penta.event.v1'),
  fabric_schema text not null default 'crownthrive.pentafabric.v1' check (fabric_schema = 'crownthrive.pentafabric.v1'),
  integrity_algorithm text not null check (integrity_algorithm in ('HMAC-SHA256','SHA-256')),
  integrity_digest text not null check (integrity_digest ~ '^[a-f0-9]{64}$'),
  build_sha text,
  event jsonb not null,
  received_at timestamptz not null default now(),
  constraint pentafabric_event_id_match check (event ->> 'id' = penta_id),
  constraint pentafabric_trace_id_match check (event #>> '{trace,trace_id}' = trace_id),
  constraint pentafabric_protocol_match check (event #>> '{mesh,fabric,protocol}' = protocol),
  constraint pentafabric_lane_match check (event #>> '{mesh,fabric,lane}' = lane),
  constraint pentafabric_route_match check (event #>> '{mesh,fabric,route}' = route),
  constraint pentafabric_chlom_intent_match check (event #>> '{mesh,chlom,intent_id}' = chlom_intent_id),
  constraint pentafabric_chlom_binding_match check (event #>> '{mesh,chlom,binding}' = chlom_binding),
  constraint pentafabric_contract_match check (event #>> '{mesh,contract}' = event_contract),
  constraint pentafabric_schema_match check (event #>> '{mesh,fabric,schema}' = fabric_schema),
  constraint pentafabric_integrity_algorithm_match check (event #>> '{integrity,algorithm}' = integrity_algorithm),
  constraint pentafabric_integrity_digest_match check (event #>> '{integrity,digest}' = integrity_digest)
);

comment on table public.pentafabric_events is 'Append-only PentaFabric v1 evidence ledger for canonical CHLOM-governed Penta delivery events.';

create index if not exists pentafabric_events_trace_idx on public.pentafabric_events(trace_id);
create index if not exists pentafabric_events_protocol_idx on public.pentafabric_events(protocol);
create index if not exists pentafabric_events_received_idx on public.pentafabric_events(received_at desc);

alter table public.pentafabric_events enable row level security;
revoke all on table public.pentafabric_events from anon, authenticated;
grant select, insert on table public.pentafabric_events to service_role;
grant usage, select on sequence public.pentafabric_events_id_seq to service_role;

create or replace function public.pentafabric_events_immutable()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  raise exception 'pentafabric_events is append-only; update/delete are prohibited';
end;
$$;

revoke all on function public.pentafabric_events_immutable() from public;

create trigger pentafabric_events_block_update
before update on public.pentafabric_events
for each row execute function public.pentafabric_events_immutable();

create trigger pentafabric_events_block_delete
before delete on public.pentafabric_events
for each row execute function public.pentafabric_events_immutable();
