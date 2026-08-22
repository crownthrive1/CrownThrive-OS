-- CANDIDATE ROLLBACK — use only after dependency/readback review.
begin;
drop schema if exists institutional_ip cascade;
commit;
