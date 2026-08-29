-- CrownThrive COS V1 — PentaDND provider-ledger source guard
--
-- Purpose:
--   Prove that the exact production bootstrap and corrective migration bodies
--   remain recoverable from Supabase's append-only migration ledger while the
--   byte-exact bootstrap files are exported into repository custody.
--
-- This file DOES NOT pretend to be the original bootstrap source. It fails
-- closed when the provider ledger is missing, changed, or incomplete.
-- Historical migrations remain immutable and are never rewritten.

do $$
declare
  v_missing jsonb;
  v_changed jsonb;
begin
  with expected(version,name,statement_bytes,statement_sha256) as (
    values
      ('20260829221916','penta_dnd_core_v1',18401,'52a14f1beefe4d3e09f88bc5261826e0a995519baefcb584c405362b55c82078'),
      ('20260829222237','penta_dnd_topology_v1',29094,'a28a0ea2cc6e9a79c95272d054256334960bb34a3e72e426a754640db075aa0c'),
      ('20260829222334','penta_dnd_leases_redundancy_v1',13268,'4effb8701fb500093f76c48a12426988827852ee1bc6640ca442bca3f8bebd2f'),
      ('20260829222538','penta_dnd_hourly_pass_v1',19509,'a2ec89c09d7e0a10f96949975f69b5c0f60c3463468707c1fb343ec83834f954'),
      ('20260829222630','penta_dnd_hourly_wiring_v1',8703,'199726b1b70b1e9ef176c6b67e61ce22b43d716b53755fc408eda852b2ef187e'),
      ('20260829224200','penta_dnd_hourly_clock_rebind_v2',14456,'690e4651281d02453ea158d7f339536f842f0c6fb72900b9facb9af778298e69'),
      ('20260829224743','penta_dnd_monotonic_hourly_contract_v3',5101,'25499d3ec400121b1b20e72a2697d6826e278f32b56b3c428af69e73cbdb0f7f'),
      ('20260829225159','penta_dnd_execution_privilege_hardening_v1',3631,'a68a6b0a44ba4455a418ccbab5edcf3acf20062f8f9cb710fa3403c0ec783769')
  ), observed as (
    select
      m.version,
      m.name,
      octet_length(coalesce(array_to_string(m.statements,E'\n\n'),'')) as statement_bytes,
      encode(
        extensions.digest(
          convert_to(coalesce(array_to_string(m.statements,E'\n\n'),''),'UTF8'),
          'sha256'
        ),
        'hex'
      ) as statement_sha256
    from supabase_migrations.schema_migrations m
    where m.name ilike 'penta_dnd%'
  )
  select coalesce(jsonb_agg(to_jsonb(e)),'[]'::jsonb)
    into v_missing
  from expected e
  left join observed o using(version,name)
  where o.version is null;

  with expected(version,name,statement_bytes,statement_sha256) as (
    values
      ('20260829221916','penta_dnd_core_v1',18401,'52a14f1beefe4d3e09f88bc5261826e0a995519baefcb584c405362b55c82078'),
      ('20260829222237','penta_dnd_topology_v1',29094,'a28a0ea2cc6e9a79c95272d054256334960bb34a3e72e426a754640db075aa0c'),
      ('20260829222334','penta_dnd_leases_redundancy_v1',13268,'4effb8701fb500093f76c48a12426988827852ee1bc6640ca442bca3f8bebd2f'),
      ('20260829222538','penta_dnd_hourly_pass_v1',19509,'a2ec89c09d7e0a10f96949975f69b5c0f60c3463468707c1fb343ec83834f954'),
      ('20260829222630','penta_dnd_hourly_wiring_v1',8703,'199726b1b70b1e9ef176c6b67e61ce22b43d716b53755fc408eda852b2ef187e'),
      ('20260829224200','penta_dnd_hourly_clock_rebind_v2',14456,'690e4651281d02453ea158d7f339536f842f0c6fb72900b9facb9af778298e69'),
      ('20260829224743','penta_dnd_monotonic_hourly_contract_v3',5101,'25499d3ec400121b1b20e72a2697d6826e278f32b56b3c428af69e73cbdb0f7f'),
      ('20260829225159','penta_dnd_execution_privilege_hardening_v1',3631,'a68a6b0a44ba4455a418ccbab5edcf3acf20062f8f9cb710fa3403c0ec783769')
  ), observed as (
    select
      m.version,
      m.name,
      octet_length(coalesce(array_to_string(m.statements,E'\n\n'),'')) as statement_bytes,
      encode(
        extensions.digest(
          convert_to(coalesce(array_to_string(m.statements,E'\n\n'),''),'UTF8'),
          'sha256'
        ),
        'hex'
      ) as statement_sha256
    from supabase_migrations.schema_migrations m
    where m.name ilike 'penta_dnd%'
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'version',e.version,
    'name',e.name,
    'expected_bytes',e.statement_bytes,
    'observed_bytes',o.statement_bytes,
    'expected_sha256',e.statement_sha256,
    'observed_sha256',o.statement_sha256
  )),'[]'::jsonb)
    into v_changed
  from expected e
  join observed o using(version,name)
  where e.statement_bytes <> o.statement_bytes
     or e.statement_sha256 <> o.statement_sha256;

  if jsonb_array_length(v_missing) > 0 then
    raise exception 'PENTADND_PROVIDER_LEDGER_MISSING:%',v_missing;
  end if;

  if jsonb_array_length(v_changed) > 0 then
    raise exception 'PENTADND_PROVIDER_LEDGER_DRIFT:%',v_changed;
  end if;
end
$$;
