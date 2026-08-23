-- Prerequisite for Execution Builder capability registration.
-- Existing live readback showed zero duplicate non-null capability_id values.
begin;
do $preflight$
declare v_duplicates integer;
begin
  select count(*) into v_duplicates from (
    select capability_id from chlom_runtime.capability_contracts
    where capability_id is not null group by capability_id having count(*)>1
  ) d;
  if v_duplicates<>0 then raise exception 'HOLD_CAPABILITY_ID_DUPLICATES:%',v_duplicates; end if;
end
$preflight$;
create unique index if not exists capability_contracts_capability_id_uq
  on chlom_runtime.capability_contracts(capability_id);
commit;
