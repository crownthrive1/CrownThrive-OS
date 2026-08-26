create schema if not exists ct_generated;
create table if not exists ct_generated.soundcloud_adapter_receipts (
  id uuid default gen_random_uuid() not null,
  surface_id text not null,
  state text not null,
  evidence jsonb not null,
  created_at timestamptz not null
);

