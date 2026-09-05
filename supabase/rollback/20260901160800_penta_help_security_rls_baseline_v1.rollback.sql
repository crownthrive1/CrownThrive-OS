-- Guarded rollback for 20260901160800_penta_help_security_rls_baseline_v1.sql.
-- Refuse rollback if successor policies, FORCE RLS, or end-user direct grants appeared,
-- because disabling RLS in that state could create an access-control regression.

begin;

do $rollback_guard$
declare
  v_policy_count integer;
  v_force_count integer;
  v_end_user_acl_count integer;
begin
  select count(*) into v_policy_count
  from pg_policy p
  where p.polrelid = any(array[
    'penta_help.requests_v1'::regclass,
    'penta_help.routes_v1'::regclass,
    'penta_help.liaison_threads_v1'::regclass,
    'penta_help.receipts_v1'::regclass,
    'penta_security.runtime_review_receipts_v1'::regclass
  ]);

  select count(*) into v_force_count
  from pg_class c
  where c.oid = any(array[
    'penta_help.requests_v1'::regclass,
    'penta_help.routes_v1'::regclass,
    'penta_help.liaison_threads_v1'::regclass,
    'penta_help.receipts_v1'::regclass,
    'penta_security.runtime_review_receipts_v1'::regclass
  ]) and c.relforcerowsecurity;

  select count(*) into v_end_user_acl_count
  from pg_class c
  cross join lateral aclexplode(coalesce(c.relacl,'{}'::aclitem[])) a
  where c.oid = any(array[
    'penta_help.requests_v1'::regclass,
    'penta_help.routes_v1'::regclass,
    'penta_help.liaison_threads_v1'::regclass,
    'penta_help.receipts_v1'::regclass,
    'penta_security.runtime_review_receipts_v1'::regclass
  ])
    and a.grantee in (
      0,
      (select oid from pg_roles where rolname='anon'),
      (select oid from pg_roles where rolname='authenticated')
    );

  if v_policy_count <> 0 then
    raise exception 'PENTA_SECURITY_RLS_ROLLBACK_REFUSED_SUCCESSOR_POLICY:%',v_policy_count;
  end if;
  if v_force_count <> 0 then
    raise exception 'PENTA_SECURITY_RLS_ROLLBACK_REFUSED_FORCE_RLS_SUCCESSOR:%',v_force_count;
  end if;
  if v_end_user_acl_count <> 0 then
    raise exception 'PENTA_SECURITY_RLS_ROLLBACK_REFUSED_END_USER_GRANT:%',v_end_user_acl_count;
  end if;
end
$rollback_guard$;

drop function if exists penta_security.penta_help_rls_baseline_status_v1();

alter table penta_help.requests_v1 disable row level security;
alter table penta_help.routes_v1 disable row level security;
alter table penta_help.liaison_threads_v1 disable row level security;
alter table penta_help.receipts_v1 disable row level security;
alter table penta_security.runtime_review_receipts_v1 disable row level security;

commit;
