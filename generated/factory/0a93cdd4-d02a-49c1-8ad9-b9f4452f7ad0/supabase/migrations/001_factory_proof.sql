create schema if not exists ct_generated;
create table if not exists ct_generated.factory_proof (
  id uuid not null,
  created_at timestamptz not null
);

