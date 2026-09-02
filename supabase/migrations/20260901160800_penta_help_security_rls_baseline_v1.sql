-- PentaSecurity S2/S13 defense-in-depth baseline for service-only PentaHelp/security receipt state.
-- Production pre-state observed 2026-09-01: RLS disabled, no policies, no anon/authenticated
-- direct table grants; postgres and service_role are BYPASSRLS. This migration intentionally
-- enables (but does not FORCE) RLS so existing service-only SECURITY DEFINER/BYPASSRLS paths
-- keep working while future non-bypass direct access fails closed.

begin;

do $preflight$
declare
  v_missing text[];
  v_bad_roles text[];
  v_policy_count integer;
  v_end_user_acl_count integer;
begin
  select array_agg(t.fq order by t.fq)
    into v_missing
  from (values
    ('penta_help.requests_v1'),
    ('penta_help.routes_v1'),
    ('penta_help.liaison_threads_v1'),
    ('penta_help.receipts_v1'),
    ('penta_security.runtime_review_receipts_v1')
  ) as t(fq)
  where to_regclass(t.fq) is null;

  if coalesce(cardinality(v_missing),0) > 0 then
    raise exception 'PENTA_SECURITY_RLS_BASELINE_TABLE_MISSING:%', array_to_string(v_missing,',');
  end if;

  select array_agg(x.rolname order by x.rolname)
    into v_bad_roles
  from (
    select rolname,rolbypassrls
    from pg_roles
    where rolname in ('postgres','service_role','anon','authenticated')
  ) x
  where (x.rolname in ('postgres','service_role') and not x.rolbypassrls)
     or (x.rolname in ('anon','authenticated') and x.rolbypassrls);

  if coalesce(cardinality(v_bad_roles),0) > 0
     or (select count(*) from pg_roles where rolname in ('postgres','service_role','anon','authenticated')) <> 4 then
    raise exception 'PENTA_SECURITY_RLS_BASELINE_ROLE_SEMANTICS_UNEXPECTED:%',coalesce(array_to_string(v_bad_roles,','),'missing_role');
  end if;

  select count(*) into v_policy_count
  from pg_policy p
  where p.polrelid = any(array[
    'penta_help.requests_v1'::regclass,
    'penta_help.routes_v1'::regclass,
    'penta_help.liaison_threads_v1'::regclass,
    'penta_help.receipts_v1'::regclass,
    'penta_security.runtime_review_receipts_v1'::regclass
  ]);

  if v_policy_count <> 0 then
    raise exception 'PENTA_SECURITY_RLS_BASELINE_PREEXISTING_POLICY:%',v_policy_count;
  end if;

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

  if v_end_user_acl_count <> 0 then
    raise exception 'PENTA_SECURITY_RLS_BASELINE_END_USER_DIRECT_GRANT_PRESENT:%',v_end_user_acl_count;
  end if;
end
$preflight$;

revoke all on table penta_help.requests_v1 from public, anon, authenticated;
revoke all on table penta_help.routes_v1 from public, anon, authenticated;
revoke all on table penta_help.liaison_threads_v1 from public, anon, authenticated;
revoke all on table penta_help.receipts_v1 from public, anon, authenticated;
revoke all on table penta_security.runtime_review_receipts_v1 from public, anon, authenticated;

alter table penta_help.requests_v1 enable row level security;
alter table penta_help.routes_v1 enable row level security;
alter table penta_help.liaison_threads_v1 enable row level security;
alter table penta_help.receipts_v1 enable row level security;
alter table penta_security.runtime_review_receipts_v1 enable row level security;

create or replace function penta_security.penta_help_rls_baseline_status_v1()
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog,penta_security,penta_help
as $function$
with target as (
  select c.oid,n.nspname||'.'||c.relname as fq,c.relrowsecurity,c.relforcerowsecurity,c.relacl
  from pg_class c
  join pg_namespace n on n.oid=c.relnamespace
  where c.oid = any(array[
    'penta_help.requests_v1'::regclass,
    'penta_help.routes_v1'::regclass,
    'penta_help.liaison_threads_v1'::regclass,
    'penta_help.receipts_v1'::regclass,
    'penta_security.runtime_review_receipts_v1'::regclass
  ])
), summary as (
  select count(*)::int as target_count,
         count(*) filter(where relrowsecurity)::int as rls_enabled_count,
         count(*) filter(where relforcerowsecurity)::int as force_rls_count,
         coalesce((select count(*)::int from pg_policy p where p.polrelid in(select oid from target)),0) as policy_count,
         coalesce((
           select count(*)::int
           from target t
           cross join lateral aclexplode(coalesce(t.relacl,'{}'::aclitem[])) a
           where a.grantee in (
             0,
             (select oid from pg_roles where rolname='anon'),
             (select oid from pg_roles where rolname='authenticated')
           )
         ),0) as end_user_direct_grant_count
  from target
), roles as (
  select bool_and(case
           when rolname in ('postgres','service_role') then rolbypassrls
           when rolname in ('anon','authenticated') then not rolbypassrls
           else false end) as role_semantics_ok,
         count(*)::int as role_count
  from pg_roles
  where rolname in ('postgres','service_role','anon','authenticated')
)
select jsonb_build_object(
  'contract','ct.penta.security.penta-help-rls-baseline.v1',
  'target_count',s.target_count,
  'rls_enabled_count',s.rls_enabled_count,
  'force_rls_count',s.force_rls_count,
  'policy_count',s.policy_count,
  'end_user_direct_grant_count',s.end_user_direct_grant_count,
  'role_semantics_ok',(r.role_semantics_ok and r.role_count=4),
  'disposition',case when s.target_count=5 and s.rls_enabled_count=5 and s.force_rls_count=0
                          and s.policy_count=0 and s.end_user_direct_grant_count=0
                          and r.role_semantics_ok and r.role_count=4
                     then 'PASS_RLS_DENY_BY_DEFAULT_BASELINE'
                     else 'HOLD_RLS_BASELINE_DRIFT' end,
  'force_rls_intentionally_deferred',true,
  'authority_created',false,
  'observed_at',now()
)
from summary s cross join roles r;
$function$;

revoke all on function penta_security.penta_help_rls_baseline_status_v1() from public, anon, authenticated;
grant execute on function penta_security.penta_help_rls_baseline_status_v1() to service_role;

comment on function penta_security.penta_help_rls_baseline_status_v1()
is 'Service-only PentaSecurity readback for the PentaHelp/security receipt RLS deny-by-default baseline. Does not grant provider, money, rights, D3, vote, or certification authority.';

commit;
