create schema if not exists ct_generated;
create table if not exists ct_generated.surface_patch_surface_shopmelaninmagic_production (
  id uuid default gen_random_uuid() not null,
  operation_key text not null,
  state text not null,
  evidence jsonb not null,
  created_at timestamptz not null
);

