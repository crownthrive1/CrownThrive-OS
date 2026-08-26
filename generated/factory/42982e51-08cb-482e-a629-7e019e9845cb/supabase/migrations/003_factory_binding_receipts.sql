create schema if not exists ct_generated;
create table if not exists ct_generated.factory_binding_receipts (
  id uuid default gen_random_uuid() not null,
  surface_id text not null,
  provider_system text not null,
  created_at timestamptz not null
);

