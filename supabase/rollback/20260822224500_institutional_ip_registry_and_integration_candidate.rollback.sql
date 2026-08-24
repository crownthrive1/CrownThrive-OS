-- CANDIDATE ROLLBACK — execute only after dependency and readback review.
begin;
drop schema if exists institutional_ip cascade;
commit;
