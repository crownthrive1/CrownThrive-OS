-- Prerequisite readback for Execution Builder capability registration.
-- `chlom_runtime.capability_contracts` is a public-safe view over the governed base registry.
-- No DDL mutation is needed here; fail closed unless the expected storage topology is present.
begin;
do $preflight$
declare
  v_view text;
  v_pk integer;
begin
  if to_regclass('chlom_runtime.capability_contracts') is null
     or to_regclass('chlom_runtime.vaulted_capability_registry') is null
     or to_regclass('chlom_secrets.trade_secret_assets') is null
  then raise exception 'HOLD_EXECUTION_BUILDER_CAPABILITY_DEPENDENCY_MISSING'; end if;

  select pg_get_viewdef('chlom_runtime.capability_contracts'::regclass,true) into v_view;
  if v_view not ilike '%chlom_runtime.vaulted_capability_registry%' then
    raise exception 'HOLD_CAPABILITY_VIEW_STORAGE_DRIFT';
  end if;

  select count(*) into v_pk
  from pg_constraint c
  join pg_class t on t.oid=c.conrelid
  join pg_namespace n on n.oid=t.relnamespace
  where n.nspname='chlom_runtime'
    and t.relname='vaulted_capability_registry'
    and c.contype='p'
    and pg_get_constraintdef(c.oid) ilike '%capability_id%';
  if v_pk<>1 then raise exception 'HOLD_CAPABILITY_BASE_PRIMARY_KEY_MISSING'; end if;
end
$preflight$;
commit;
