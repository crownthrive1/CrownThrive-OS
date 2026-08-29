-- Export the exact PentaDND migration source retained by Supabase.
-- Run with psql from an authorized internal environment.
-- No secret values are selected.
--
-- Example:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -f scripts/export_penta_dnd_migration_ledger.sql \
--     > penta_dnd_migration_ledger_export.tsv
--
-- Output columns:
-- version, migration_name, ordinal, statement_bytes, statement_sha256, statement

\pset format unaligned
\pset fieldsep '\t'
\pset tuples_only on

with migration_source as (
  select
    m.version,
    m.name,
    u.ordinality::integer as ordinal,
    u.statement,
    octet_length(u.statement) as statement_bytes,
    encode(extensions.digest(convert_to(u.statement,'UTF8'),'sha256'),'hex') as statement_sha256
  from supabase_migrations.schema_migrations m
  cross join lateral unnest(m.statements) with ordinality as u(statement,ordinality)
  where m.name ilike 'penta_dnd%'
)
select
  version,
  name,
  ordinal,
  statement_bytes,
  statement_sha256,
  replace(replace(statement,E'\r',''),E'\t','  ')
from migration_source
order by version,ordinal;
