-- No-op rollback: the prerequisite migration performs read-only topology assertions only.
begin;
select 1;
commit;
